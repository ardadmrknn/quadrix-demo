"""Quadrix Online PvP — Steam P2P üzerinden 1v1 Tetris

Bu modül, yerel PvP (pvp_game.py) mantığını temel alarak
Steam Networking üzerinden online maç yapılmasını sağlar.

Akış:
  1. Lobi ekranı: oluştur / katıl / arkadaş davet et
  2. İki oyuncu hazır olunca host oyunu başlatır
  3. Oyun sırasında:
     - Kendi tahtanı normal oyna (sol tahta)
     - Rakibin tahta durumunu ağdan al ve sağ tahtada göster
     - Satır temizlediğinde rakibe çöp satır gönder
     - Biri elendiğinde / süre dolduğunda maç biter
"""
from __future__ import annotations

import json
import math
import time
import random
import os
import sys

import pygame

# Proje import'ları
from constants import (
    BOARD_WIDTH, BOARD_HEIGHT, BLACK, COLORS,
    INITIAL_FALL_SPEED,
    DEFAULT_LOCK_DELAY,
    LEVEL_SPEED_MIN_MS,
    get_level_fall_speed_ms,
)
from board import Board
from pieces import Piece, SHAPES, get_piece_spawn_y, skip_hidden_rows
from block_styles import BlockStyleManager, TextureSlice, TextureRenderCache
from sound import SoundManager
from background import BackgroundManager
from background_effects import get_shared_falling_blocks_layer
from themes import ThemeManager
from mode_skins import apply_board_tint, draw_board_overlay, get_mode_skin
from retro_style import retro_style as _rs
from renderers.jelly_renderer import draw_jelly_block, draw_jelly_border
from effect_surface_cache import EffectSurfaceCache
from sweep_effects import SweepCatState, draw_rainbow_cat_sweep
from line_clear_feedback import (
    queue_wave_effects as _queue_wave_effects,
    update_wave_effects as _update_wave_effects,
)
try:
    from sweep_effects import compute_line_sweep_progress_speed as _compute_line_sweep_progress_speed
except Exception:
    def _compute_line_sweep_progress_speed(base_block_speed: float, sweep_travel_px: float, level: int | float = 1) -> float:
        travel_px = max(1.0, float(sweep_travel_px))
        block_speed = max(0.001, float(base_block_speed))
        try:
            level_i = max(1, int(level))
        except Exception:
            level_i = 1
        base_duration = travel_px / (block_speed * 3600.0)
        duration_ratio = max(0.42, 0.965 ** max(0, level_i - 1))
        sweep_duration = max(0.0001, base_duration * duration_ratio)
        return 1.0 / sweep_duration
from screen_shake import (
    DEFAULT_SCREEN_SHAKE_DURATION_SECONDS,
    HARD_DROP_SCREEN_SHAKE_DURATION_SECONDS,
    HARD_DROP_SCREEN_SHAKE_INTENSITY,
    begin_screen_shake,
    sample_screen_shake_offset,
    step_screen_shake,
)

# Convenience aliases for retro_style singleton methods
get_font = _rs.get_font
draw_glass_panel = _rs.draw_glass_panel
get_fitting_font = _rs.get_fitting_font
from ui_theme import UIFonts, UIColors, UIStyle
from ui_scaling import get_projected_effective_scale
from localization import t, get_language
from text_cache import render_text
from combo_popup_style import (
    COMBO_POPUP_SHADOW_COLOR,
    get_combo_popup_alpha,
    get_combo_popup_color,
)
from steam_networking import (
    SteamNetworking, MsgType, NetEvent, NetMessage,
    CHANNEL_GAME, CHANNEL_STATE, CHANNEL_CONTROL,
    generate_lobby_code,
)


ONLINE_PVP_DAS_DELAY_MS = 160
ONLINE_PVP_DAS_REPEAT_MS = 105
ONLINE_PVP_SOFT_DROP_SPEED_MS = 55
ONLINE_PVP_GARBAGE_ENABLED = False
ONLINE_PVP_RESULT_SCORE_POINTS = 1
ONLINE_PVP_RESULT_LINES_POINTS = 1
ONLINE_PVP_RESULT_BOARD_OPEN_POINTS = 2
ONLINE_PVP_RESULT_WIN_THRESHOLD = 3


def _parse_lobby_bool(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None:
        return None

    normalized = str(value).strip().lower()
    if not normalized:
        return None
    if normalized in ('1', 'true', 'yes'):
        return True
    if normalized in ('0', 'false', 'no'):
        return False
    return None


def _normalize_lobby_visibility(
    visibility_value: object,
    requires_code_value: object,
    lobby_code: str,
    metadata_ready_value: object = None,
) -> tuple[str, bool, str, bool]:
    visibility = str(visibility_value or '').strip().lower()
    requires_code = _parse_lobby_bool(requires_code_value)
    normalized_code = (lobby_code or '').strip()
    metadata_ready = _parse_lobby_bool(metadata_ready_value)
    has_explicit_metadata = (
        visibility in ('public', 'private')
        or requires_code is not None
        or bool(normalized_code)
    )

    if metadata_ready is False and not has_explicit_metadata:
        return 'unknown', False, normalized_code, False

    if visibility in ('public', 'private'):
        if requires_code is None:
            requires_code = visibility == 'private'
        if visibility == 'private' or requires_code:
            return 'private', True, normalized_code, True
        return 'public', False, normalized_code, True

    if requires_code is not None:
        return ('private' if requires_code else 'public'), bool(requires_code), normalized_code, True

    if normalized_code:
        return 'private', True, normalized_code, True

    return 'unknown', False, normalized_code, False


def _resolve_lobby_display_state(
    visibility_value: object,
    requires_code_value: object,
    lobby_code: str,
) -> tuple[str, bool]:
    visibility = str(visibility_value or '').strip().lower()
    requires_code = bool(requires_code_value)
    normalized_code = (lobby_code or '').strip()

    if visibility in ('public', 'private'):
        if visibility == 'private' or requires_code:
            return 'private', True
        return 'public', False

    if visibility == 'stale_unknown':
        return 'stale_unknown', False

    if requires_code or normalized_code:
        return 'private', True
    return 'unknown', False


def _resolve_private_lobby_code(lobby_id: int, requires_code: bool, lobby_code: str) -> str:
    normalized_code = (lobby_code or '').strip()
    if normalized_code or not requires_code or not lobby_id:
        return normalized_code
    try:
        return generate_lobby_code(lobby_id)
    except Exception:
        return normalized_code


def _build_online_pvp_trailer_debug_lobbies() -> list[dict]:
    now = time.time()
    return [
        {
            'id': -1,
            'name': 'Trailer Private Lobby',
            'members': 1,
            'max_members': 2,
            'visibility': 'private',
            'requires_code': True,
            'code': 'STEAM1',
            'metadata_ready': True,
            'found_time': now - 8,
            'debug_lobby': True,
        },
        {
            'id': -2,
            'name': 'Trailer Public Lobby 1',
            'members': 2,
            'max_members': 2,
            'visibility': 'public',
            'requires_code': False,
            'code': '',
            'metadata_ready': True,
            'found_time': now - 15,
            'debug_lobby': True,
        },
        {
            'id': -3,
            'name': 'Trailer Public Lobby 2',
            'members': 1,
            'max_members': 2,
            'visibility': 'public',
            'requires_code': False,
            'code': '',
            'metadata_ready': True,
            'found_time': now - 22,
            'debug_lobby': True,
        },
        {
            'id': -4,
            'name': 'Trailer Public Lobby 3',
            'members': 1,
            'max_members': 2,
            'visibility': 'public',
            'requires_code': False,
            'code': '',
            'metadata_ready': True,
            'found_time': now - 36,
            'debug_lobby': True,
        },
    ]

# Steam pump thread kontrolü — bridge aktifken pump duraklatılır (race condition önleme)
try:
    from steam_integration import pause_pump as _pause_steam_pump
    from steam_integration import resume_pump as _resume_steam_pump
except ImportError:
    def _pause_steam_pump(): pass
    def _resume_steam_pump(): pass

# Steam overlay — doğrudan ctypes API çağrıları (C++ bridge gerektirmez)
try:
    from steam_integration import (
        activate_game_overlay as _activate_overlay,
        activate_game_overlay_invite_dialog as _activate_invite_dialog,
        activate_game_overlay_to_user as _activate_overlay_to_user,
    )
except ImportError:
    def _activate_overlay(panel='Friends'): return False
    def _activate_invite_dialog(lobby_id=0): return False
    def _activate_overlay_to_user(action='', sid=0): return False

try:
    from gamepad_manager import get_gamepad_manager as _get_gamepad_manager
except ImportError:
    _get_gamepad_manager = None

try:
    from platform_utils import create_display, set_app_icon, resource_path
    from platform_utils import normalize_mouse_pos, get_mouse_pos, resolve_frame_rate_cap
except ImportError:
    def create_display(w, h, **kw):
        flags = pygame.RESIZABLE
        if kw.get('fullscreen'):
            flags = pygame.FULLSCREEN | pygame.RESIZABLE
        return pygame.display.set_mode((w, h), flags)
    def resource_path(p):
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', p)
    def normalize_mouse_pos(pos):
        return pos
    def get_mouse_pos():
        return pygame.mouse.get_pos()
    def set_app_icon(path):
        pass
    def resolve_frame_rate_cap(requested_limit, fallback=60):
        try:
            limit = int(requested_limit or 0)
        except Exception:
            limit = 0
        if limit > 0:
            return max(1, limit)
        try:
            if hasattr(pygame.display, 'get_current_refresh_rate'):
                refresh_rate = int(pygame.display.get_current_refresh_rate() or 0)
                if 24 <= refresh_rate <= 1000:
                    return refresh_rate
        except Exception:
            pass
        try:
            if hasattr(pygame.display, 'get_desktop_refresh_rates'):
                rates = [
                    int(rate)
                    for rate in (pygame.display.get_desktop_refresh_rates() or [])
                    if 24 <= int(rate or 0) <= 1000
                ]
                if rates:
                    return max(rates)
        except Exception:
            pass
        return max(1, int(fallback or 60))


# ─────────────── Online PvP Durumları ───────────────

class OnlineState:
    LOBBY_MENU   = 'lobby_menu'    # Lobi oluştur / katıl ekranı
    WAITING      = 'waiting'       # Lobide rakip bekleniyor
    READY_CHECK  = 'ready_check'   # İki oyuncu da hazır mı?
    COUNTDOWN    = 'countdown'     # 3-2-1 geri sayım
    PLAYING      = 'playing'       # Oyun devam ediyor
    GAME_OVER    = 'game_over'     # Maç bitti
    DISCONNECTED = 'disconnected'  # Bağlantı koptu


class OnlinePvPGame:
    """Steam P2P üzerinden Online 1v1 Tetris maçı."""

    @staticmethod
    def _is_focus_loss_event(event) -> bool:
        event_type = getattr(event, 'type', None)
        if event_type is None:
            return False

        focus_loss_types = (
            getattr(pygame, 'WINDOWFOCUSLOST', None),
            getattr(pygame, 'WINDOWMINIMIZED', None),
            getattr(pygame, 'WINDOWHIDDEN', None),
            getattr(pygame, 'APP_WILLENTERBACKGROUND', None),
            getattr(pygame, 'APP_DIDENTERBACKGROUND', None),
        )
        if any(focus_type is not None and event_type == focus_type for focus_type in focus_loss_types):
            return True

        window_event_type = getattr(pygame, 'WINDOWEVENT', None)
        if window_event_type is not None and event_type == window_event_type:
            window_subtype = getattr(event, 'event', None)
            if any(
                focus_type is not None and window_subtype == focus_type
                for focus_type in focus_loss_types[:3]
            ):
                return True

        active_event_type = getattr(pygame, 'ACTIVEEVENT', None)
        if active_event_type is not None and event_type == active_event_type:
            gain = getattr(event, 'gain', 1)
            state = getattr(event, 'state', 0)
            focus_mask = 0
            for attr_name in ('APPINPUTFOCUS', 'APPACTIVE'):
                attr_value = getattr(pygame, attr_name, 0)
                if isinstance(attr_value, int):
                    focus_mask |= attr_value
            return gain == 0 and (state == 0 or focus_mask == 0 or bool(state & focus_mask))

        return False

    def _pause_for_focus_loss(self) -> bool:
        if self.online_state != OnlineState.PLAYING:
            return False
        if getattr(self, 'game_over', False) or getattr(self, 'paused', False) or getattr(self, 'opponent_paused', False):
            return False

        self.paused = True
        self._freeze_active_gameplay_input()
        try:
            self._send_control_message(MsgType.PAUSE_REQUEST, reason='focus_loss_pause')
        except Exception:
            pass
        return True

    # ── Responsive ölçek (pvp_game.py ile aynı pattern) ──

    def _ui_scale(self, min_scale: float = 0.72, max_scale: float = 1.20) -> float:
        """Pencere boyutuna bağlı genel UI ölçeği (Retina/HiDPI uyumlu)."""
        try:
            return get_projected_effective_scale(
                self.screen,
                min_scale=min_scale,
                max_scale=max_scale,
                reference_size=(1366.0, 768.0),
            )
        except Exception:
            return 1.0

    def _is_online_pvp_trailer_debug_enabled(self) -> bool:
        sm = getattr(self, 'settings_manager', None)
        if sm is None:
            return False
        try:
            return bool(sm.get('online_pvp_trailer_debug', False))
        except Exception:
            return False

    def _get_lobby_entries_for_display(self) -> list[dict]:
        if self._is_online_pvp_trailer_debug_enabled():
            entries = _build_online_pvp_trailer_debug_lobbies()
        else:
            entries = list(getattr(self, '_lobby_list', []))

        if getattr(self, '_lobby_list_filter', 'all') == 'public':
            entries = [
                lobby for lobby in entries
                if str(lobby.get('visibility', 'unknown') or 'unknown').lower()
                in ('public', 'unknown', 'stale_unknown')
            ]
        return entries

    def _sx(self, value, scale=None, minimum=1) -> int:
        """Sabit piksel değerini UI ölçeğine göre dönüştür."""
        if scale is None:
            scale = self._ui_scale()
        return max(minimum, int(round(float(value) * float(scale))))

    def __init__(
        self,
        screen=None,
        fullscreen=True,
        user_manager=None,
        achievement_manager=None,
        settings_manager=None,
        sound_manager=None,
    ):
        if not pygame.get_init():
            pygame.init()

        self.user_manager = user_manager
        self.achievement_manager = achievement_manager
        self.settings_manager = settings_manager

        # Ekran
        if screen is not None:
            self.screen = screen
            self.window_width = self.screen.get_width()
            self.window_height = self.screen.get_height()
        else:
            self.screen = create_display(0, 0, fullscreen=True, resizable=False, borderless=True)
            self.window_width = self.screen.get_width()
            self.window_height = self.screen.get_height()

        self.fullscreen = True
        self.clock = pygame.time.Clock()

        # Ses
        self.sound = sound_manager if sound_manager else SoundManager()
        if settings_manager:
            self.sound.music_enabled = settings_manager.get('music_enabled', True)
            self.sound.sfx_enabled = settings_manager.get('sound_enabled', True)
            self.sound.set_music_volume(settings_manager.get('music_volume', 0.3))
            self.sound.set_volume(settings_manager.get('sfx_volume', 0.5))
        if hasattr(self.sound, 'unduck_music'):
            self.sound.unduck_music()

        # Arka plan
        self.background = BackgroundManager()
        self.board_background = BackgroundManager()
        self.background.set_transparency(1.0)
        if settings_manager:
            self.board_background.set_transparency(settings_manager.get('bg_transparency', 1.0))
        else:
            self.board_background.set_transparency(1.0)
        self.background_fx = get_shared_falling_blocks_layer('default')
        self.load_board_background()

        # Tema
        self.theme_manager = ThemeManager(settings_manager)
        if self.settings_manager:
            active_theme = self.settings_manager.get('theme', self.settings_manager.get('active_theme', 'Classic'))
            self.theme_manager.set_theme(active_theme)
        self.mode_skin = get_mode_skin('pvp')
        self.block_style_manager = BlockStyleManager(self.settings_manager) if self.settings_manager else None
        self._texture_render_cache = TextureRenderCache()
        self._effect_surface_cache = EffectSurfaceCache()
        self._sweep_cat_state = SweepCatState()
        self._board_grid_cache = {'key': None, 'surface': None}
        self._board_accent_overlay_cache: dict[tuple[int, int, tuple[int, int, int]], pygame.Surface] = {}
        self._line_clear_flash_cache: dict[tuple[int, int], pygame.Surface] = {}
        self._line_clear_glow_cache: dict[tuple[int, int, str], pygame.Surface] = {}

        # Font'lar (retro_style üzerinden — CJK/HybridFont desteği)
        self.font_large = _rs.get_font(36)
        self.font_medium = _rs.get_font(24)
        self.font_small = _rs.get_font(18)
        self.font_tiny = _rs.get_font(14, bold=False)

        # ─── Steam Networking ───
        self.net = SteamNetworking()
        self._net_initialized = False
        self._auto_connect_attempted = False
        self._auto_connect_retry_timer = 0.0

        # ─── Gamepad ───
        self.gamepad = None
        if _get_gamepad_manager is not None:
            try:
                self.gamepad = _get_gamepad_manager()
            except Exception:
                self.gamepad = None

        # ─── Oyun durumu ───
        self.online_state = OnlineState.LOBBY_MENU
        self.my_board: Board | None = None
        self.opponent_board: Board | None = None
        self.my_piece: Piece | None = None
        self.my_next_piece: Piece | None = None
        self.piece_sequence: list[int] = []
        self.piece_index = 0
        self.game_seed = 0

        # Hold (saklama)
        self.hold_piece: Piece | None = None
        self.hold_used: bool = False  # Bu tur hold kullanıldı mı?
        self.hold_shape_index: int = -1

        # Rakip tahta snapshot'ı (ağdan gelen)
        self.opponent_grid_snapshot: list[list[tuple]] | None = None
        self.opponent_score = 0
        self.opponent_lines = 0
        self.opponent_level = 1

        # Rakip aktif parça (gerçek zamanlı ağ verisi)
        self.opponent_piece_data: dict | None = None
        self._opponent_piece_visual: dict | None = None
        self._opponent_piece_seq: int = 0   # Sıra numarası (out-of-order koruması)
        self._my_piece_seq: int = 0         # Gönderilen sıra numarası
        self._opponent_board_seq: int = -1  # Snapshot sıra numarası
        self._my_board_seq: int = 0
        self._opponent_clear_event_seq: int = -1
        self._my_clear_event_seq: int = 0
        self._opponent_piece_render_cache_key: tuple | None = None
        self._opponent_piece_render_cache: dict | None = None
        self._last_sent_piece_signature: tuple | None = None
        self._pending_piece_position_dirty = False
        self._piece_position_send_timer = 0.0
        self._PIECE_POSITION_INTERVAL_MS = 33.0

        # Zamanlama
        self.fall_timer = 0
        self.lock_timer = 0
        self.countdown_timer = 0.0
        self.countdown_value = 3
        self.state_snapshot_timer = 0.0
        self.STATE_SNAPSHOT_INTERVAL = 100  # ms — her 100ms'de tahta snapshot'ı gönder (daha akıcı)

        # Flags
        self.my_ready = False
        self.opponent_ready = False
        self._ready_resend_timer = 0.0
        self._READY_RESEND_INTERVAL_MS = 1000.0
        self._session_ping_timer = 0.0
        self._SESSION_PING_INTERVAL_MS = 2000.0
        self._SESSION_PING_BACKOFF_BASE_MS = 500.0
        self._SESSION_PING_BACKOFF_MAX_MS = 4000.0
        self._session_ping_backoff_ms = 0.0
        self._game_start_pending_payload: tuple[int, list[int]] | None = None
        self._game_start_retry_timer = 0.0
        self._GAME_START_RETRY_INTERVAL_MS = 1000.0
        self._session_established = False
        self._ready_send_pending = False
        self._pending_disconnect_steam_id = 0
        self._disconnect_grace_timer = 0.0
        self._DISCONNECT_GRACE_MS = 5000.0
        self.game_over = False
        self.winner: str = ''  # 'me', 'opponent', 'draw'
        self.my_eliminated = False
        self.opponent_eliminated = False
        self._my_final_board_filled = False
        self._opponent_final_board_filled = False
        self._opponent_final_score = 0
        self._opponent_final_lines = 0
        self._match_result_recorded = False
        self.paused = False
        self.opponent_paused = False

        # Pending garbage (sırada bekleyen çöp satırlar)
        self.pending_garbage = 0
        self._garbage_gap = 0  # Son gelen çöp satır gap sütunu

        # DAS
        self.das_direction = 0
        self.das_timer = 0
        self.das_active = False

        # Soft drop
        self.soft_dropping = False

        # Next piece referansı (draw'da kullanılır)
        self.next_piece = None  # _start_game'de set edilir

        # Lobi ekranı butonları
        self._lobby_buttons: list[dict] = []
        self._lobby_list: list[dict] = []
        self._lobby_list_filter: str = 'all'
        self._lobby_list_scroll = 0
        self._lobby_list_fetching = False
        self._lobby_list_fetch_start_time: float = 0
        self._auto_lobby_refresh_requested = False
        self._auto_lobby_refresh_timer = 0.0
        self._auto_lobby_refresh_interval = 8000.0
        self._pending_lobby_list: list[dict] = []  # Lobi listesi birikim tampon
        self._deferred_lobby_entries: dict[int, dict] = {}
        self._deferred_lobby_refresh_timer = 0.0
        self._DEFERRED_LOBBY_REFRESH_INTERVAL_MS = 500.0
        self._unknown_lobby_metadata_requests: dict[int, float] = {}
        self._UNKNOWN_LOBBY_DATA_REQUEST_INTERVAL_S = 1.25
        self._lobby_presence_probe_timer = 0.0
        self._LOBBY_PRESENCE_PROBE_INTERVAL_MS = 350.0

        # Durum mesajı (hata/bilgi)
        self._status_msg: str = ''
        self._status_timer: float = 0

        # Lobi oluşturulduktan sonra otomatik davet aç
        self._invite_after_lobby: bool = False
        self._creating_public_lobby: bool = False

        # ─── Lobi Kodu Sistemi ───
        self._lobby_code: str = ''          # Oluşturulan lobi kodu (6 haneli)
        self._lobby_id_str: str = ''        # Ham lobby ID (tam numara)
        self._join_code_input: str = ''     # "Kod ile Katıl" metin girişi
        self._join_code_active: bool = False  # Metin girişi aktif mi
        self._join_code_error: str = ''     # Giriş hata mesajı
        self._join_target_lobby_id: int = 0  # Listeden seçilen özel lobi hedefi
        self._pending_browser_join_lobby_id: int = 0
        self._searching_by_code: bool = False  # Kod ile arama yapılıyor mu
        self._search_code: str = ''         # Aranan kod (lobby_list_complete'de eşleşme için)
        self._code_search_retry_count: int = 0   # Kod araması retry sayacı
        self._code_search_retry_timer: float = 0.0  # Retry geri sayımı (ms)
        self._code_search_retry_code: str = ''   # Retry edilecek kod
        self._code_search_retry_use_full_scan: bool = False
        self._authorized_private_join_lobby_id: int = 0
        self._authorized_private_join_code: str = ''
        self._invite_authorized_lobby_id: int = 0
        self._pending_access_revalidation_lobby_id: int = 0
        self._pending_revalidation_start_time: float = 0.0
        self._lobby_access_validated_id: int = 0  # Erişim doğrulaması geçen lobi ID

        # ─── Görsel Efektler (local PvP ile birebir) ───
        self.effects_enabled = True
        self.particles: list[dict] = []
        self.ambient_particles: list[dict] = []
        self.drop_trails: list[dict] = []
        # Benim satır temizleme efektlerim
        self.my_line_flash_rows: list[int] = []
        self.my_line_flash_timer: float = 0
        self.my_line_glow_alpha: int = 0
        self.my_wave_effects: list[dict] = []
        self.my_line_sweep_rows: list[int] = []
        self.my_line_sweep_progress: float = 0.0
        self.my_line_sweep_active: bool = False
        self.my_falling_block_animations: list[dict] = []
        self._line_sweep_draw_error_reported: bool = False
        # Rakip satır temizleme efektleri (ağdan gelince tetiklenir)
        self.opp_line_flash_rows: list[int] = []
        self.opp_line_flash_timer: float = 0
        self.opp_line_glow_alpha: int = 0
        self.opp_wave_effects: list[dict] = []
        self.opp_line_sweep_rows: list[int] = []
        self.opp_line_sweep_progress: float = 0.0
        self.opp_line_sweep_active: bool = False
        self.opp_falling_block_animations: list[dict] = []
        # Combo mesaj sistemi
        self.my_combo_message: str = ""
        self.my_combo_message_time: float = 0
        self._pending_opp_particle_rows: list[int] = []
        self.block_fall_speed: float = 0.12
        self.cell_size: int = 24  # update() sweep animasyonu için; _draw_game() güncelleyecek
        # Ekran titremesi
        self.screen_shake: float = 0.0
        self.shake_intensity: int = 0
        self._screen_shake_initial: float = 0.0
        # Rakip önceki lines sayısı (satır artışını tespit için)
        self._opponent_lines_prev: int = 0
        # dt saklama
        self._last_dt_ms: float = 16.666

        # Müzik başlat (lobi ekranına girince)
        self._start_pvp_music()
        # Ambient parçacıkları başlat
        self.create_ambient_particles()

    # ============================================================
    #  BAŞLATMA
    # ============================================================

    def _particle_effects_enabled(self) -> bool:
        if not getattr(self, 'effects_enabled', True):
            return False
        sm = getattr(self, 'settings_manager', None)
        if sm is None:
            return True  # Ayar yoksa açık say
        helper = getattr(sm, 'particle_effects_enabled', None)
        if callable(helper):
            try:
                return bool(helper())
            except Exception:
                pass
        try:
            value = sm.get('particle_effects', True)
        except Exception:
            return True
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return int(value) > 0
        return str(value).strip().lower() not in ('off', 'false', '0', 'kapali', 'kapalı')

    def _particle_effects_multiplier(self) -> float:
        if not self._particle_effects_enabled():
            return 0.0
        sm = getattr(self, 'settings_manager', None)
        if sm is None:
            return 1.0
        helper = getattr(sm, 'get_particle_effects_multiplier', None)
        if callable(helper):
            try:
                return max(0.0, float(helper()))
            except Exception:
                pass
        try:
            value = sm.get('particle_effects', True)
        except Exception:
            return 1.0
        if isinstance(value, bool):
            return 1.0 if value else 0.0
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return {0: 0.0, 1: 0.55, 2: 1.0, 3: 1.7}.get(max(0, min(3, int(round(value)))), 1.0)
        return {
            'off': 0.0,
            'low': 0.55,
            'az': 0.55,
            'medium': 1.0,
            'orta': 1.0,
            'high': 1.7,
            'çok': 1.7,
            'cok': 1.7,
        }.get(str(value).strip().lower(), 1.0)

    def _apply_block_style(self, piece: Piece | None):
        if not piece:
            return
        base_color = self.theme_manager.get_piece_color(piece.name) if self.theme_manager else piece.color
        if self.block_style_manager:
            self.block_style_manager.apply_to_piece(
                piece,
                base_color,
            )
        else:
            piece.color = base_color
            piece.texture_path = None
            piece.texture_surface = None
            piece.texture_surface_original = None

    def load_board_background(self):
        """Online PvP oyun alanı arka planını yükle."""
        custom_bg = self.settings_manager.get('bg_pvp_board', None) if self.settings_manager else None
        if custom_bg and os.path.exists(custom_bg):
            if self.board_background.load_image(custom_bg):
                return

        possible_paths = [
            resource_path('backgrounds/game_background.png'),
            resource_path('backgrounds/game_background.jpg'),
            resource_path('backgrounds/board_background.png'),
            resource_path('backgrounds/board_background.jpg'),
            resource_path('backgrounds/board_bg.png'),
            resource_path('backgrounds/tetris_bg.png'),
            resource_path('backgrounds/game_bg.jpg'),
        ]
        for path in possible_paths:
            if self.board_background.load_image(path):
                break

    def _get_board_grid_surface(self, cell_size: int) -> pygame.Surface:
        skin = self.mode_skin
        key = (int(cell_size), tuple(getattr(skin, 'grid_color', (50, 50, 80))), BOARD_WIDTH, BOARD_HEIGHT)
        cached = self._board_grid_cache
        if cached.get('key') == key and cached.get('surface') is not None:
            return cached['surface']

        board_width = BOARD_WIDTH * cell_size
        board_height = BOARD_HEIGHT * cell_size
        surface = pygame.Surface((board_width, board_height), pygame.SRCALPHA)
        grid_color = getattr(skin, 'grid_color', (50, 50, 80))
        line_color = (*grid_color[:3], 70)
        for x in range(BOARD_WIDTH + 1):
            pygame.draw.line(surface, line_color, (x * cell_size, 0), (x * cell_size, board_height))
        for y in range(BOARD_HEIGHT + 1):
            pygame.draw.line(surface, line_color, (0, y * cell_size), (board_width, y * cell_size))

        cached['key'] = key
        cached['surface'] = surface
        return surface

    def _get_board_accent_overlay(self, width: int, height: int, color: tuple[int, int, int], alpha: int) -> pygame.Surface:
        key = (int(width), int(height), tuple(color[:3]), int(alpha))
        cached = self._board_accent_overlay_cache.get(key)
        if cached is not None:
            return cached
        surface = pygame.Surface((width, height), pygame.SRCALPHA)
        surface.fill((*color[:3], alpha))
        self._board_accent_overlay_cache[key] = surface
        return surface

    def _draw_line_clear_flash_overlay(self, board_x: int, board_y: int, board_width: int,
                                       cell_size: int, rows: list[int], glow_alpha: int) -> None:
        flash_cache = self._line_clear_flash_cache
        glow_cache = self._line_clear_glow_cache

        for row in rows:
            if not 0 <= row < BOARD_HEIGHT:
                continue
            flash_rect = pygame.Rect(board_x, board_y + row * cell_size, board_width, cell_size)
            flash_alpha = min(255, glow_alpha)
            flash_key = (int(board_width), int(cell_size))
            flash_surface = flash_cache.get(flash_key)
            if flash_surface is None or flash_surface.get_size() != (int(board_width), int(cell_size)):
                flash_surface = pygame.Surface((int(board_width), int(cell_size)), pygame.SRCALPHA)
                flash_surface.fill((255, 255, 255, 255))
                flash_cache[flash_key] = flash_surface
            flash_surface.set_alpha(int(flash_alpha))
            self.screen.blit(flash_surface, flash_rect.topleft)

            if glow_alpha > 100:
                glow_height = cell_size // 2
                glow_surf_alpha = int(flash_alpha * 0.5)
                if glow_height > 0 and glow_surf_alpha > 0:
                    top_key = (int(board_width), int(glow_height), 'top')
                    top_glow = glow_cache.get(top_key)
                    if top_glow is None or top_glow.get_size() != (int(board_width), int(glow_height)):
                        top_glow = pygame.Surface((int(board_width), int(glow_height)), pygame.SRCALPHA)
                        for i in range(int(glow_height)):
                            alpha = int(255 * (1.0 - (i / max(1, glow_height - 1))))
                            pygame.draw.line(top_glow, (255, 255, 200, alpha), (0, i), (int(board_width), i))
                        glow_cache[top_key] = top_glow
                    top_glow.set_alpha(glow_surf_alpha)
                    self.screen.blit(top_glow, (board_x, board_y + row * cell_size - glow_height))

                    bottom_key = (int(board_width), int(glow_height), 'bottom')
                    bottom_glow = glow_cache.get(bottom_key)
                    if bottom_glow is None or bottom_glow.get_size() != (int(board_width), int(glow_height)):
                        bottom_glow = pygame.Surface((int(board_width), int(glow_height)), pygame.SRCALPHA)
                        for i in range(int(glow_height)):
                            alpha = int(255 * (i / max(1, glow_height - 1)))
                            pygame.draw.line(bottom_glow, (255, 255, 200, alpha), (0, i), (int(board_width), i))
                        glow_cache[bottom_key] = bottom_glow
                    bottom_glow.set_alpha(glow_surf_alpha)
                    self.screen.blit(bottom_glow, (board_x, board_y + (row + 1) * cell_size))

    def _start_block_fall_animation(self, rows: list[int], cell_size: int,
                                    board: Board | None = None,
                                    snapshot_grid: list[list[object | None]] | None = None,
                                    is_opponent: bool = False) -> None:
        if not rows:
            return

        animations = []
        lines_count = len(rows)
        if board is not None:
            board_pixel_width = board.width * cell_size
            sweep_width = max(1, int(cell_size * 1.5))
            sweep_travel_px = max(1.0, float(board_pixel_width + sweep_width))
            for row in range(board.height):
                for col in range(board.width):
                    if board.occupancy[row][col]:
                        column_center_px = (col + 0.5) * cell_size
                        sweep_trigger = column_center_px / sweep_travel_px
                        sweep_trigger = max(0.0, min(1.0, sweep_trigger))
                        animations.append({
                            'row': row,
                            'col': col,
                            'current_offset': -lines_count * cell_size,
                            'target_offset': 0,
                            'sweep_trigger': sweep_trigger,
                            'started': False,
                        })
        elif snapshot_grid is not None:
            board_pixel_width = BOARD_WIDTH * cell_size
            sweep_width = max(1, int(cell_size * 1.5))
            sweep_travel_px = max(1.0, float(board_pixel_width + sweep_width))
            max_rows = min(BOARD_HEIGHT, len(snapshot_grid))
            for row in range(max_rows):
                max_cols = min(BOARD_WIDTH, len(snapshot_grid[row]))
                for col in range(max_cols):
                    if snapshot_grid[row][col] is not None:
                        column_center_px = (col + 0.5) * cell_size
                        sweep_trigger = column_center_px / sweep_travel_px
                        sweep_trigger = max(0.0, min(1.0, sweep_trigger))
                        animations.append({
                            'row': row,
                            'col': col,
                            'current_offset': -lines_count * cell_size,
                            'target_offset': 0,
                            'sweep_trigger': sweep_trigger,
                            'started': False,
                        })

        if is_opponent:
            self.opp_falling_block_animations = animations
        else:
            self.my_falling_block_animations = animations

    def _get_block_fall_offset(self, row: int, col: int, is_opponent: bool = False) -> float:
        animations = self.opp_falling_block_animations if is_opponent else self.my_falling_block_animations
        for anim in animations:
            if anim['row'] == row and anim['col'] == col:
                return anim['current_offset']
        return 0

    def _make_texture_slice(self, piece: Piece | None, rel_x: int, rel_y: int,
                             piece_width: int | None = None, piece_height: int | None = None) -> TextureSlice | None:
        if not piece or not getattr(piece, 'texture_surface', None):
            return None
        width = piece_width if piece_width is not None else (len(piece.shape[0]) if piece.shape else 1)
        height = piece_height if piece_height is not None else (len(piece.shape) if piece.shape else 1)
        width = width or 1
        height = height or 1
        rotation = getattr(piece, 'rotation_state', 0)
        style_key = getattr(piece, 'style_key', None) or piece.name
        return TextureSlice(style_key, rel_x, rel_y, width, height, rotation)

    def _get_rotated_surface(self, surface, rotation):
        return self._texture_render_cache.get_rotated_surface(surface, rotation)

    def _render_texture_slice(self, surface, slice_info, size):
        bounds = {'x': 0.0, 'y': 0.0, 'w': 1.0, 'h': 1.0}
        if self.block_style_manager:
            bounds = self.block_style_manager.get_slice_bounds(slice_info.piece_name)
        return self._texture_render_cache.render_slice(surface, slice_info, size, bounds)

    def _draw_texture_cell(self, x, y, size, texture_surface, texture_slice, dst):
        scaled = self._render_texture_slice(texture_surface, texture_slice, size)
        if scaled is None:
            return
        dst.blit(scaled, (x, y))

    def draw_textured_block(self, x, y, size, color, texture_surface=None, texture_slice=None, dst: pygame.Surface | None = None):
        target = dst or self.screen
        if texture_surface is not None and texture_slice is not None:
            self._draw_texture_cell(x, y, size, texture_surface, texture_slice, target)
            draw_jelly_border(target, x, y, size, color)
            return
        draw_jelly_block(target, x, y, size, color)

    def _start_pvp_music(self):
        """PvP müziğini başlat (local PvP ile aynı playlist mantığı)."""
        if not getattr(self.sound, 'music_enabled', True):
            return
        playlist_values = []
        if self.settings_manager:
            try:
                playlist_values = self.settings_manager.get_music_playlist_for_mode('pvp')
            except Exception:
                playlist_values = []
        if playlist_values:
            track_keys = []
            for value in playlist_values:
                track_key = self.sound.ensure_track_available(value)
                if track_key:
                    track_keys.append(track_key)
            if track_keys:
                do_shuffle = bool(self.settings_manager.get('music_shuffle', False)) if self.settings_manager else False
                start_index = 0 if do_shuffle else random.randrange(len(track_keys))
                self.sound.set_music_playlist(track_keys, loop=True, start_index=start_index, autoplay=True, force=True, shuffle=do_shuffle)
                return
        preferred = None
        if self.settings_manager:
            try:
                overrides = self.settings_manager.get_mode_music_overrides()
                preferred = overrides.get('pvp')
            except Exception:
                pass
            if not preferred:
                preferred = self.settings_manager.get('pvp_music')
            if not preferred:
                preferred = self.settings_manager.get('game_music')
        track_key = self.sound.ensure_track_available(preferred or 'pvp_1')
        if track_key:
            self.sound.set_music_playlist([track_key], loop=True, autoplay=True, force=True)

    def _init_networking(self) -> bool:
        """Steam networking'i başlat."""
        if self._net_initialized:
            return True

        if not self.net.available:
            print("[OnlinePvP] Steam net bridge mevcut değil!")
            self._status_msg = t('steam_bridge_not_available',
                                 'Steam ağ köprüsü yüklenemedi. Online PvP kullanılamıyor.')
            self._status_timer = 4.0
            return False

        # ÖNEMLİ: steam_integration.py pump thread'ini duraklat.
        # İki farklı thread'den SteamAPI_RunCallbacks() çağırmak
        # Steam SDK'da race condition/segfault oluşturur.
        try:
            _pause_steam_pump()
        except Exception as e:
            print(f"[OnlinePvP] Pump pause hatası: {e}")

        ok = self.net.init()
        if ok:
            self._net_initialized = True
            # Event handler'ları kaydet
            self.net.on('lobby_created', self._on_lobby_created)
            self.net.on('lobby_joined', self._on_lobby_joined)
            self.net.on('lobby_member_joined', self._on_member_joined)
            self.net.on('lobby_member_left', self._on_member_left)
            self.net.on('lobby_member_disconnected', self._on_member_disconnected)
            # Lobi listesi — C++ per-lobi event gönderiyor, tek JSON değil
            self.net.on('lobby_found', self._on_lobby_found)
            self.net.on('lobby_data_updated', self._on_lobby_data_updated)
            self.net.on('lobby_list_complete', self._on_lobby_list_complete)
            # Steam overlay "Oyuna Katıl" isteği
            self.net.on('join_requested', self._on_join_requested)
            # Hata olayları
            self.net.on('lobby_create_failed', self._on_lobby_error)
            self.net.on('lobby_join_failed', self._on_lobby_error)
            self.net.on('lobby_list_failed', self._on_lobby_list_error)
            # P2P session olayları
            self.net.on('session_accepted', self._on_session_accepted)
            self.net.on('session_rejected', self._on_session_rejected)
        else:
            # Init başarısız — pump'u tekrar başlat
            try:
                _resume_steam_pump()
            except Exception:
                pass
            self._status_msg = t('steam_net_init_failed',
                                 'Steam ağ bağlantısı kurulamadı!')
            self._status_timer = 4.0
        return ok

    # ============================================================
    #  LOBİ EVENT HANDLER'LARI
    # ============================================================

    def _on_lobby_created(self, ev: NetEvent):
        self.online_state = OnlineState.WAITING
        self._lobby_presence_probe_timer = 0.0
        self._lobby_access_validated_id = 0
        self._pending_access_revalidation_lobby_id = 0
        self._pending_revalidation_start_time = 0.0
        print(f"[OnlinePvP] Lobi oluşturuldu: {ev.steam_id}")

        self._lobby_id_str = str(ev.steam_id)
        # Eski C++ bridge uyumluluğu: C++ OnLobbyCreated metadata_ready=1
        # yazmış olabilir. Hassas alanları yazmadan önce metadata_ready=0'a çek;
        # böylece diğer platform geçici "public" metadata okumasını önle.
        try:
            self.net.set_lobby_data('metadata_ready', '0')
        except Exception:
            pass

        if self._creating_public_lobby:
            self._lobby_code = ''
            # Public lobi metadata'sını yaz.
            # C++ sadece game, version, host_name ve metadata_ready=0 yazar;
            # visibility/requires_code gibi hassas alanlar Python'dan yazılır
            # (race condition önlemi).
            try:
                self.net.set_lobby_data('visibility', 'public')
                self.net.set_lobby_data('requires_code', '0')
                self.net.set_lobby_data('lobby_code', '')
                self.net.set_lobby_data('lobby_code_full', '')
                self.net.set_lobby_data('metadata_ready', '1')
            except Exception as _meta_err:
                print(f"[OnlinePvP] Public lobi metadata hatası: {_meta_err}")
            print(f"[OnlinePvP] Public lobi hazır. Lobby ID: {self._lobby_id_str}")
        else:
            self._lobby_code = generate_lobby_code(ev.steam_id)
            self._remember_private_join_authorization(ev.steam_id, self._lobby_code)
            # Özel lobi metadata'sını yaz.
            # C++ lobi tipi Public olarak oluşturuldu (cross-platform keşif
            # güvenilirliği için). Tüm metadata Python'dan yazılır;
            # metadata_ready=1 en son set edilir — böylece diğer platform
            # "public" metadata okuduğu race window kapanır.
            try:
                self.net.set_lobby_data('visibility', 'private')
                self.net.set_lobby_data('requires_code', '1')
                self.net.set_lobby_data('lobby_code', self._lobby_code)
                self.net.set_lobby_data('lobby_code_full', self._lobby_id_str)
                self.net.set_lobby_data('metadata_ready', '1')
            except Exception as _meta_err:
                print(f"[OnlinePvP] Özel lobi metadata hatası: {_meta_err}")
            print(f"[OnlinePvP] Özel lobi hazır. Lobby ID: {self._lobby_id_str}")

        # Davet bekletilmişse şimdi aç
        if self._invite_after_lobby:
            self._invite_after_lobby = False
            invite_ok = False
            try:
                self.net.invite_friend()
                invite_ok = True
            except Exception:
                pass
            # C++ bridge başarısızsa ctypes overlay dene
            if not invite_ok and ev.steam_id:
                _activate_invite_dialog(ev.steam_id)
            self._status_msg = t('invite_sent', 'Steam davet penceresi açıldı')
            self._status_timer = 2.5

    def _create_lobby(self, public: bool = False):
        """Lobi oluşturma isteğini public/private bilgisiyle başlat."""
        self._creating_public_lobby = bool(public)
        self.net.create_lobby(public=public)

    def _on_lobby_joined(self, ev: NetEvent):
        self.online_state = OnlineState.WAITING
        self._lobby_presence_probe_timer = 0.0
        self._join_target_lobby_id = 0
        # Yeni lobiye her katılışta önceki doğrulama durumunu sıfırla.
        # Önceki lobiden kalan stale validated_id, aynı lobby_id'ye
        # tekrar katılırken yetkilendirilmemiş erişime izin verebilir.
        self._lobby_access_validated_id = 0
        self._pending_access_revalidation_lobby_id = 0
        self._pending_revalidation_start_time = 0.0

        # C++ bridge lobby_joined event'inde metadata payload gönderebilir.
        # Varsa parse et — _validate_joined_lobby_access tarafından
        # kullanılacak snapshot'a katkı sağlar.
        if ev.data:
            try:
                _parsed = json.loads(ev.data)
                if isinstance(_parsed, dict):
                    joined_lobby_id = int(getattr(self.net, 'lobby_id', 0) or 0)
                    if joined_lobby_id:
                        self._refresh_cached_lobby_metadata(
                            joined_lobby_id, _parsed, prefer_live=True)
            except (json.JSONDecodeError, ValueError, TypeError):
                pass

        # Cross-platform metadata propagasyonu: lobiye katıldıktan sonra
        # metadata'yı açıkça iste. macOS→Windows arası metadata
        # gecikebilir; RequestLobbyData, OnLobbyDataUpdate callback'ini
        # tetikleyerek güncel veriyi indirir.
        joined_lobby_id = int(getattr(self.net, 'lobby_id', 0) or 0)
        if joined_lobby_id:
            try:
                self.net.request_lobby_data(joined_lobby_id)
            except Exception:
                pass

        if not self._validate_joined_lobby_access():
            return
        # Rakip zaten lobideyse bul
        if self.net.opponent_steam_id:
            self._promote_to_ready_check(self.net.opponent_steam_id, self.net.opponent_name)

    def _on_member_joined(self, ev: NetEvent):
        if ev.steam_id != self.net.my_steam_id:
            print(f"[OnlinePvP] Rakip katıldı: {self.net.opponent_name}")
            self._promote_to_ready_check(ev.steam_id, ev.data or self.net.opponent_name, play_sound=True)

    def _on_member_disconnected(self, ev: NetEvent):
        my_id = int(getattr(self.net, 'my_steam_id', 0) or 0)
        opponent_id = int(getattr(self.net, 'opponent_steam_id', 0) or 0)
        target_id = int(ev.steam_id or opponent_id or getattr(self, '_pending_disconnect_steam_id', 0) or 0)
        if not target_id or target_id == my_id:
            return

        if opponent_id and ev.steam_id and int(ev.steam_id) != opponent_id:
            try:
                members = set(self.net.get_lobby_members() or [])
            except Exception:
                members = set()
            if members and target_id not in members:
                return

        if self.online_state == OnlineState.PLAYING:
            self._pending_disconnect_steam_id = target_id
            self._disconnect_grace_timer = float(self._DISCONNECT_GRACE_MS)
            self._session_established = False
            self._session_ping_timer = 0.0
            self._send_session_ping()
            self._status_msg = t(
                'opponent_connection_unstable',
                'Rakip baglantisi kararsiz, yeniden baglanmasi bekleniyor...',
            )
            self._status_timer = 2.5
            print(
                f"[OnlinePvP] lobby_member_disconnected alindi: {self._pending_disconnect_steam_id} "
                f"(grace={int(self._DISCONNECT_GRACE_MS)}ms)"
            )
            return

        self._on_member_left(ev)

    def _on_session_accepted(self, ev: NetEvent):
        self._session_established = True
        self._session_ping_backoff_ms = 0.0
        self._session_ping_timer = 0.0
        print(f"[OnlinePvP] P2P session kabul edildi: {ev.steam_id}")
        if self.online_state == OnlineState.READY_CHECK and self.my_ready and not self.opponent_ready:
            self._send_ready_signal(reason='session_accepted')

    def _on_session_rejected(self, ev: NetEvent):
        self._session_established = False
        print(f"[OnlinePvP] P2P session REDDEDİLDİ: {ev.steam_id} sebep={ev.data}")
        self._status_msg = t('p2p_session_rejected', 'P2P oturumu reddedildi, tekrar deneniyor...')
        self._status_timer = 3.0
        if self._session_ping_backoff_ms <= 0:
            self._session_ping_backoff_ms = self._SESSION_PING_BACKOFF_BASE_MS
        else:
            self._session_ping_backoff_ms = min(
                self._SESSION_PING_BACKOFF_MAX_MS,
                self._session_ping_backoff_ms * 2.0,
            )
        self._session_ping_timer = float(self._session_ping_backoff_ms)
        print(f"[OnlinePvP] session_ping backoff: {int(self._session_ping_backoff_ms)}ms")

    def _send_session_ping(self):
        """P2P session'ı erken kurmak için küçük bir ping gönder."""
        if not self._net_initialized:
            return False
        ok = self.net.send({'type': 'session_ping'}, reliable=True, channel=CHANNEL_CONTROL)
        if not ok:
            print("[OnlinePvP] session_ping gonderilemedi!")
        else:
            print("[OnlinePvP] session_ping gonderildi — P2P session kurulacak")
            self._session_ping_backoff_ms = 0.0
        return bool(ok)

    def _send_control_message(self, msg_type: str, reason: str = '') -> bool:
        """Kontrol kanalından mesaj gönder ve sonucu logla."""
        if getattr(self, '_net_initialized', True) is False:
            return False
        net = getattr(self, 'net', None)
        if net is None:
            return False
        ok = bool(net.send({'type': msg_type}, reliable=True, channel=CHANNEL_CONTROL))
        if not ok:
            print(f"[OnlinePvP] control send basarisiz: {msg_type} ({reason or 'no_reason'})")
        return ok

    def _send_ready_signal(self, reason: str = '') -> bool:
        """READY sinyalini gönder; session hazır değilse ping ile bootstrap da yap."""
        if not self._net_initialized:
            return False
        has_opponent_id = bool(getattr(self.net, 'opponent_steam_id', 0))

        if not has_opponent_id:
            self._ready_send_pending = True
            ok = bool(self.net.send_ready())
            if ok:
                self._ready_send_pending = False
                print(f"[OnlinePvP] READY lobby fallback gonderildi ({reason or 'no_reason'}).")
            else:
                print(f"[OnlinePvP] READY lobby fallback basarisiz ({reason or 'no_reason'}).")
            return ok

        if not self._session_established:
            self._ready_send_pending = True
            ping_ok = self._send_session_ping()
            ready_ok = bool(self.net.send_ready())
            lobby_ok = self._send_ready_lobby_fallback(reason=reason)
            if ready_ok or lobby_ok:
                self._ready_send_pending = False
                print(
                    f"[OnlinePvP] READY session-oncesi gonderildi "
                    f"({reason or 'no_reason'}), ping={ping_ok}, lobby_fallback={lobby_ok}."
                )
                return True
            if not ping_ok:
                print(f"[OnlinePvP] READY başarısız ({reason or 'no_reason'}): session yok, ping de başarısız.")
            else:
                print(f"[OnlinePvP] READY başarısız ({reason or 'no_reason'}): ping gitti, session onayı bekleniyor.")
            return False

        ok = bool(self.net.send_ready())
        if not ok:
            ok = self._send_ready_lobby_fallback(reason=reason)
        if ok:
            self._ready_send_pending = False
        else:
            print(f"[OnlinePvP] send_ready başarısız ({reason or 'no_reason'}).")
        return ok

    def _send_ready_lobby_fallback(self, reason: str = '') -> bool:
        """P2P hazır değilken READY bilgisini lobby broadcast ile de ulaştır."""
        net = getattr(self, 'net', None)
        if net is None:
            return False
        payload = {'type': MsgType.READY}
        try:
            my_id = int(getattr(net, 'my_steam_id', 0) or 0)
        except Exception:
            my_id = 0
        if my_id:
            payload['sender_id'] = my_id
        send_to_lobby = getattr(net, 'send_to_lobby', None)
        if callable(send_to_lobby):
            ok = bool(send_to_lobby(payload, reliable=True, channel=CHANNEL_CONTROL))
            if not ok:
                print(f"[OnlinePvP] READY lobby fallback basarisiz ({reason or 'no_reason'}).")
            return ok
        return False

    def _on_member_left(self, ev: NetEvent):
        my_id = int(getattr(self.net, 'my_steam_id', 0) or 0)
        target_id = int(
            ev.steam_id
            or getattr(self.net, 'opponent_steam_id', 0)
            or getattr(self, '_pending_disconnect_steam_id', 0)
            or 0
        )
        if not target_id or target_id == my_id:
            return

        # Rakip ayrılınca parça verisini temizle
        self._clear_opponent_piece_state()
        self._opponent_piece_seq = 0
        if self.online_state == OnlineState.PLAYING:
            self._pending_disconnect_steam_id = target_id
            self._disconnect_grace_timer = max(
                float(getattr(self, '_disconnect_grace_timer', 0.0)),
                float(self._DISCONNECT_GRACE_MS),
            )
            self._session_established = False
            self._session_ping_timer = 0.0
            self._send_session_ping()
            self._status_msg = t(
                'opponent_connection_unstable',
                'Rakip baglantisi kararsiz, yeniden baglanmasi bekleniyor...',
            )
            self._status_timer = 2.5
            print(
                f"[OnlinePvP] lobby_member_left alindi: {self._pending_disconnect_steam_id} "
                f"(grace={int(self._DISCONNECT_GRACE_MS)}ms)"
            )
            return
        elif self.online_state == OnlineState.COUNTDOWN:
            # Geri sayım sırasında rakip çıktı — lobiye dön
            self.online_state = OnlineState.WAITING
            self.countdown_value = 3
            self.countdown_timer = 0
            self._status_msg = t('opponent_left', 'Rakip ayrıldı')
            self._status_timer = 3.0
        else:
            self.online_state = OnlineState.WAITING
            self._status_msg = t('opponent_left', 'Rakip ayrıldı')
            self._status_timer = 3.0
        # Ready durumlarını sıfırla
        self.my_ready = False
        self.opponent_ready = False
        self._ready_resend_timer = 0.0
        self._session_established = False
        self._ready_send_pending = False
        self._pending_disconnect_steam_id = 0
        self._disconnect_grace_timer = 0.0
        self._session_ping_timer = 0.0
        self._session_ping_backoff_ms = 0.0
        self._game_start_pending_payload = None
        self._game_start_retry_timer = 0.0
        # Aynı lobide kalınıyor ama metadata revalidation gerekirse
        # pending flag'i korunsun — sadece match state temizleniyor.
        # _lobby_access_validated_id sıfırlanMAZ (lobiden ayrılmıyoruz).

    def _get_lobby_metadata_snapshot(
        self,
        lobby_id: int,
        payload: dict[str, object] | None = None,
        *,
        prefer_live: bool = False,
    ) -> dict[str, object]:
        payload_dict = payload if isinstance(payload, dict) else {}

        def _payload_value(key: str) -> object:
            return payload_dict.get(key)

        def _read_lobby_data(key: str, fallback: str = '') -> str:
            if not prefer_live:
                payload_value = _payload_value(key)
                if payload_value is not None:
                    return str(payload_value)
            try:
                value = self.net.get_lobby_data_for(lobby_id, key)
                if value:
                    return value
            except Exception:
                pass
            if prefer_live:
                payload_value = _payload_value(key)
                if payload_value is not None:
                    return str(payload_value)
            return fallback

        def _read_lobby_raw(key: str, fallback: object = '') -> object:
            if not prefer_live:
                payload_value = _payload_value(key)
                if payload_value is not None:
                    return payload_value
            try:
                value = self.net.get_lobby_data_for(lobby_id, key)
                if value != '':
                    return value
            except Exception:
                pass
            if prefer_live:
                payload_value = _payload_value(key)
                if payload_value is not None:
                    return payload_value
            return fallback

        host_name = _read_lobby_data('host_name', '')
        lobby_code = _read_lobby_data('lobby_code', '')
        visibility_value = _read_lobby_data('visibility', '')
        requires_code_value = _read_lobby_raw('requires_code', '')
        metadata_ready_value = _read_lobby_raw('metadata_ready', '')
        visibility, requires_code, lobby_code, metadata_ready = _normalize_lobby_visibility(
            visibility_value,
            requires_code_value,
            lobby_code,
            metadata_ready_value,
        )
        lobby_code = _resolve_private_lobby_code(lobby_id, requires_code, lobby_code)
        return {
            'id': lobby_id,
            'name': host_name,
            'code': lobby_code,
            'visibility': visibility,
            'requires_code': requires_code,
            'metadata_ready': metadata_ready,
        }

    def _update_cached_lobby_snapshot(self, lobby_id: int, snapshot: dict) -> bool:
        if not lobby_id or not isinstance(snapshot, dict):
            return False

        updated = False
        for collection_name in ('_pending_lobby_list', '_lobby_list'):
            collection = getattr(self, collection_name, None)
            if not isinstance(collection, list):
                continue
            for index, lobby in enumerate(collection):
                if int(lobby.get('id', 0) or 0) != lobby_id:
                    continue
                lobby['name'] = snapshot.get('name') or lobby.get('name') or f'Lobi #{index + 1}'
                lobby['code'] = snapshot.get('code', lobby.get('code', ''))
                lobby['visibility'] = snapshot.get('visibility', lobby.get('visibility', 'unknown'))
                lobby['requires_code'] = bool(snapshot.get('requires_code', lobby.get('requires_code', False)))
                lobby['metadata_ready'] = bool(snapshot.get('metadata_ready', lobby.get('metadata_ready', False)))
                updated = True
        return updated

    def _upsert_lobby_entry(self, collection_name: str, entry: dict):
        collection = getattr(self, collection_name, None)
        if not isinstance(collection, list):
            return
        lobby_id = int(entry.get('id', 0) or 0)
        if not lobby_id:
            return
        for index, lobby in enumerate(collection):
            if int(lobby.get('id', 0) or 0) == lobby_id:
                collection[index] = entry
                return
        collection.append(entry)

    def _remember_deferred_lobby_entry(self, entry: dict):
        lobby_id = int(entry.get('id', 0) or 0)
        if lobby_id:
            self._deferred_lobby_entries[lobby_id] = entry

    def _iter_known_lobby_entries(self) -> list[dict]:
        seen_ids: set[int] = set()
        entries: list[dict] = []
        for collection in (getattr(self, '_lobby_list', []), list(getattr(self, '_deferred_lobby_entries', {}).values())):
            for lobby in collection:
                lobby_id = int(lobby.get('id', 0) or 0)
                if not lobby_id or lobby_id in seen_ids:
                    continue
                seen_ids.add(lobby_id)
                entries.append(lobby)
        return entries

    def _promote_deferred_lobby_entry(self, lobby_id: int, snapshot: dict | None = None) -> bool:
        normalized_lobby_id = int(lobby_id or 0)
        if not normalized_lobby_id:
            return False
        deferred_entry = self._deferred_lobby_entries.get(normalized_lobby_id)
        if not deferred_entry:
            return False
        effective_snapshot = snapshot
        if effective_snapshot is None:
            # Deferred entry'yi payload olarak kullan AMA Python bool
            # varsayımlarını (requires_code=False, metadata_ready=False)
            # temizle. Bu değerler _parse_lobby_bool tarafından "açıkça
            # kod gerekmez" olarak yorumlanır ve yanlış 'public'
            # sınıflandırma üretir. Sadece STRING değerler payload'da kalır.
            sanitized_payload = {}
            for _k, _v in deferred_entry.items():
                if _k in ('requires_code', 'metadata_ready'):
                    # Python bool varsayımlarını dışla — sadece string kabul et
                    if isinstance(_v, str):
                        sanitized_payload[_k] = _v
                elif _k == 'visibility' and _v == 'unknown':
                    pass  # 'unknown' payload'da olmamalı
                else:
                    sanitized_payload[_k] = _v
            effective_snapshot = self._get_lobby_metadata_snapshot(
                normalized_lobby_id,
                sanitized_payload or None,
                prefer_live=True,
            )
        if effective_snapshot.get('visibility') == 'unknown':
            return False

        promoted_entry = dict(deferred_entry)
        promoted_entry['name'] = effective_snapshot.get('name') or deferred_entry.get('name') or promoted_entry.get('name', '')
        promoted_entry['code'] = effective_snapshot.get('code', deferred_entry.get('code', ''))
        promoted_entry['visibility'] = effective_snapshot.get('visibility', deferred_entry.get('visibility', 'unknown'))
        promoted_entry['requires_code'] = bool(effective_snapshot.get('requires_code', deferred_entry.get('requires_code', False)))
        promoted_entry['metadata_ready'] = bool(effective_snapshot.get('metadata_ready', deferred_entry.get('metadata_ready', False)))
        target_collection = '_pending_lobby_list' if self._lobby_list_fetching else '_lobby_list'
        self._upsert_lobby_entry(target_collection, promoted_entry)
        self._deferred_lobby_entries.pop(normalized_lobby_id, None)
        self._clear_lobby_metadata_refresh_request(normalized_lobby_id)
        return True

    def _refresh_deferred_lobby_entries(self):
        for lobby_id in list(getattr(self, '_deferred_lobby_entries', {}).keys()):
            self._promote_deferred_lobby_entry(lobby_id)

    def _request_lobby_metadata_refresh(self, lobby_id: int) -> bool:
        normalized_lobby_id = int(lobby_id or 0)
        if not normalized_lobby_id or not getattr(self, '_net_initialized', False):
            return False

        request_times = getattr(self, '_unknown_lobby_metadata_requests', None)
        if not isinstance(request_times, dict):
            request_times = {}
            self._unknown_lobby_metadata_requests = request_times

        min_interval = float(
            getattr(self, '_UNKNOWN_LOBBY_DATA_REQUEST_INTERVAL_S', 1.25) or 1.25)
        now = time.time()
        last_request = float(request_times.get(normalized_lobby_id, 0.0) or 0.0)
        if last_request > 0.0 and (now - last_request) < max(0.1, min_interval):
            return False

        request_fn = getattr(self.net, 'request_lobby_data', None)
        if not callable(request_fn):
            return False

        try:
            requested = bool(request_fn(normalized_lobby_id))
        except Exception:
            return False

        if requested:
            request_times[normalized_lobby_id] = now
        return requested

    def _clear_lobby_metadata_refresh_request(self, lobby_id: int | None = None):
        request_times = getattr(self, '_unknown_lobby_metadata_requests', None)
        if not isinstance(request_times, dict):
            return

        normalized_lobby_id = int(lobby_id or 0)
        if normalized_lobby_id:
            request_times.pop(normalized_lobby_id, None)
            return
        request_times.clear()

    def _remember_private_join_authorization(self, lobby_id: int, code: str):
        self._authorized_private_join_lobby_id = int(lobby_id or 0)
        self._authorized_private_join_code = str(code or '').strip()

    def _clear_private_join_authorization(self, lobby_id: int | None = None):
        normalized_lobby_id = int(lobby_id or 0)
        if not normalized_lobby_id or self._authorized_private_join_lobby_id == normalized_lobby_id:
            self._authorized_private_join_lobby_id = 0
            self._authorized_private_join_code = ''
        if not normalized_lobby_id or self._invite_authorized_lobby_id == normalized_lobby_id:
            self._invite_authorized_lobby_id = 0

    def _open_private_lobby_code_prompt(self, lobby_id: int):
        normalized_lobby_id = int(lobby_id or 0)
        self._pending_browser_join_lobby_id = 0
        self._join_target_lobby_id = normalized_lobby_id
        self._join_code_active = True
        self._join_code_input = ''
        self._join_code_error = ''
        self._status_msg = t('enter_lobby_code', 'Lobi kodu girin')
        self._status_timer = 2.5

    def _start_lobby_browser_join(self, lobby_id: int, snapshot: dict | None = None) -> bool:
        normalized_lobby_id = int(lobby_id or 0)
        if not normalized_lobby_id:
            return False

        effective_snapshot = snapshot
        if effective_snapshot is None:
            effective_snapshot = self._get_lobby_metadata_snapshot(
                normalized_lobby_id,
                prefer_live=True,
            )

        visibility = str(effective_snapshot.get('visibility', 'unknown') or 'unknown').lower()
        requires_code = bool(effective_snapshot.get('requires_code', False))

        if visibility == 'public' and not requires_code:
            self._pending_browser_join_lobby_id = 0
            self._join_target_lobby_id = 0
            self._join_code_active = False
            self.net.join_lobby(normalized_lobby_id)
            self._status_msg = t('joining_lobby', 'Lobiye katılınıyor...')
            self._status_timer = 2.0
            return True

        if visibility == 'private' or requires_code:
            self._open_private_lobby_code_prompt(normalized_lobby_id)
            return True

        self._pending_browser_join_lobby_id = normalized_lobby_id
        self._join_target_lobby_id = 0
        self._join_code_active = False
        self._request_lobby_metadata_refresh(normalized_lobby_id)
        self._status_msg = 'Lobi ayarlari kontrol ediliyor...'
        self._status_timer = 2.5
        return False

    def _complete_pending_browser_join(self, lobby_id: int, snapshot: dict | None = None) -> bool:
        pending_lobby_id = int(getattr(self, '_pending_browser_join_lobby_id', 0) or 0)
        normalized_lobby_id = int(lobby_id or 0)
        if not pending_lobby_id or pending_lobby_id != normalized_lobby_id:
            return False

        effective_snapshot = snapshot
        if effective_snapshot is None:
            effective_snapshot = self._get_lobby_metadata_snapshot(
                normalized_lobby_id,
                prefer_live=True,
            )

        visibility = str(effective_snapshot.get('visibility', 'unknown') or 'unknown').lower()
        requires_code = bool(effective_snapshot.get('requires_code', False))

        if visibility == 'public' and not requires_code:
            self._pending_browser_join_lobby_id = 0
            self._join_target_lobby_id = 0
            self._join_code_active = False
            self.net.join_lobby(normalized_lobby_id)
            self._status_msg = t('joining_lobby', 'Lobiye katılınıyor...')
            self._status_timer = 2.0
            return True

        if visibility == 'private' or requires_code:
            self._pending_browser_join_lobby_id = 0
            self._open_private_lobby_code_prompt(normalized_lobby_id)
            return True

        return False

    def _reject_private_lobby_join(self):
        # Private lobiden erişim reddedildi — lobi menüsüne dön ve
        # kullanıcıya kod giriş alanını aç, böylece kodla tekrar deneyebilir.
        rejected_lobby_id = int(getattr(self.net, 'lobby_id', 0) or 0)
        self._return_to_pvp_lobby_menu()
        if rejected_lobby_id:
            self._join_target_lobby_id = rejected_lobby_id
            self._join_code_active = True
            self._join_code_input = ''
            self._join_code_error = ''
            self._status_msg = t('private_lobby_code_required',
                                 'Bu özel lobi için geçerli kod veya davet gerekli')
        else:
            self._status_msg = t('private_lobby_code_required',
                                 'Bu özel lobi için geçerli kod veya davet gerekli')
        self._status_timer = 3.0

    def _validate_joined_lobby_access(self) -> bool:
        current_lobby_id = int(getattr(self.net, 'lobby_id', 0) or 0)
        if not current_lobby_id:
            return True

        # Daha önce bu lobi için erişim doğrulandıysa tekrar kontrol etme.
        # Bu sayede _on_lobby_data_updated'dan gelen tekrarlı çağrılar
        # temizlenmiş auth nedeniyle yanlış reject tetiklemez.
        if self._lobby_access_validated_id == current_lobby_id:
            return True

        my_steam_id = int(getattr(self.net, 'my_steam_id', 0) or 0)
        lobby_owner_id = 0
        try:
            lobby_owner_id = int(getattr(self.net, 'get_lobby_owner', lambda: 0)() or 0)
        except Exception:
            lobby_owner_id = 0
        if (my_steam_id and lobby_owner_id == my_steam_id) or bool(getattr(self.net, 'is_host', False)):
            self._clear_private_join_authorization(current_lobby_id)
            self._lobby_access_validated_id = current_lobby_id
            return True

        snapshot = self._get_lobby_metadata_snapshot(current_lobby_id, prefer_live=True)

        if snapshot.get('visibility') == 'unknown' and not snapshot.get('metadata_ready'):
            # Metadata henüz propague olmamış — geçici izin ver.
            # Davet yetkilendirmesi güvenilirdir — kalıcı onay ver.
            # Kod yetkilendirmesi ise metadata gelene kadar ERTELENMELİ;
            # girilen kod gerçek lobi koduyla karşılaştırılmadan onay
            # verilmemeli (yanlış kod ile giriş açığı).
            authorized_by_invite = self._invite_authorized_lobby_id == current_lobby_id
            if authorized_by_invite:
                self._clear_private_join_authorization(current_lobby_id)
                self._lobby_access_validated_id = current_lobby_id
                return True
            # Kod yetkilendirmesi veya yetkilendirme yok — geçici izin ver.
            # Kodu TEMİZLEME: metadata geldiğinde _on_lobby_data_updated
            # bu metodu tekrar çağıracak ve kod doğrulanacak.
            self._pending_access_revalidation_lobby_id = current_lobby_id
            self._pending_revalidation_start_time = time.time()
            return True

        if not snapshot.get('requires_code'):
            self._clear_private_join_authorization(current_lobby_id)
            self._lobby_access_validated_id = current_lobby_id
            return True

        expected_code = _resolve_private_lobby_code(
            current_lobby_id,
            True,
            str(snapshot.get('code', '') or ''),
        )
        authorized_by_code = (
            self._authorized_private_join_lobby_id == current_lobby_id
            and self._authorized_private_join_code
            and self._authorized_private_join_code == expected_code
        )
        authorized_by_invite = self._invite_authorized_lobby_id == current_lobby_id
        if authorized_by_code or authorized_by_invite:
            self._clear_private_join_authorization(current_lobby_id)
            self._lobby_access_validated_id = current_lobby_id
            return True

        self._reject_private_lobby_join()
        return False

    def _refresh_cached_lobby_metadata(
        self,
        lobby_id: int,
        payload: dict | None = None,
        *,
        prefer_live: bool = True,
    ) -> dict | None:
        normalized_lobby_id = int(lobby_id or 0)
        if not normalized_lobby_id:
            return None
        snapshot = self._get_lobby_metadata_snapshot(
            normalized_lobby_id,
            payload,
            prefer_live=prefer_live,
        )
        if self._update_cached_lobby_snapshot(normalized_lobby_id, snapshot):
            return snapshot
        return None

    def _try_resolve_pending_code_join(self, lobby_id: int, snapshot: dict | None = None) -> bool:
        pending_code = str(getattr(self, '_code_search_retry_code', '') or '').strip()
        if not pending_code:
            return False

        effective_snapshot = snapshot
        if effective_snapshot is None:
            effective_snapshot = self._get_lobby_metadata_snapshot(lobby_id, prefer_live=True)

        if not effective_snapshot.get('metadata_ready'):
            return False

        lobby_code = str(effective_snapshot.get('code', '') or '').strip()
        if lobby_code != pending_code:
            return False

        self._code_search_retry_count = 0
        self._code_search_retry_timer = 0.0
        self._code_search_retry_code = ''
        self._code_search_retry_use_full_scan = False
        self._join_target_lobby_id = 0
        self._remember_private_join_authorization(lobby_id, pending_code)
        self.net.join_lobby(lobby_id)
        self._status_msg = t('joining_lobby', 'Lobiye katılınıyor...')
        self._status_timer = 2.0
        return True

    def _promote_to_ready_check(self, opponent_id: int = 0, opponent_name: str = '', play_sound: bool = False):
        normalized_opponent_id = int(opponent_id or getattr(self.net, 'opponent_steam_id', 0) or 0)
        state_changed = self.online_state != OnlineState.READY_CHECK

        if normalized_opponent_id and not getattr(self.net, 'opponent_steam_id', 0):
            try:
                self.net._opponent_steam_id = normalized_opponent_id
            except Exception:
                pass
        if opponent_name and not getattr(self.net, 'opponent_name', ''):
            try:
                self.net._opponent_name = opponent_name
            except Exception:
                pass

        self.online_state = OnlineState.READY_CHECK
        self._pending_disconnect_steam_id = 0
        self._disconnect_grace_timer = 0.0

        if state_changed or not self._session_established:
            self._session_established = False
            self._session_ping_timer = 0.0
            self._send_session_ping()

        if play_sound and state_changed:
            try:
                self.sound.play('click')
            except Exception:
                pass

    def _sync_lobby_presence_from_members(self) -> bool:
        if self.online_state not in (OnlineState.WAITING, OnlineState.READY_CHECK):
            return False

        try:
            members = list(self.net.get_lobby_members() or [])
        except Exception:
            return False

        my_id = int(getattr(self.net, 'my_steam_id', 0) or 0)
        opponent_ids = [int(member_id) for member_id in members if int(member_id or 0) and int(member_id or 0) != my_id]
        if not opponent_ids:
            return False

        opponent_id = opponent_ids[0]
        opponent_name = getattr(self.net, 'opponent_name', '')
        if not opponent_name:
            try:
                opponent_name = self.net._get_name(opponent_id)
            except Exception:
                opponent_name = ''

        self._promote_to_ready_check(opponent_id, opponent_name, play_sound=self.online_state == OnlineState.WAITING)
        return True

    def _find_lobby_match_by_code(self, code: str) -> tuple[int, bool, bool]:
        normalized_code = (code or '').strip()
        if not normalized_code:
            return 0, False, False

        target_lobby_id = int(getattr(self, '_join_target_lobby_id', 0) or 0)
        matched_ids: list[int] = []
        pending_metadata = False

        for lobby in self._iter_known_lobby_entries():
            lobby_id = int(lobby.get('id', 0) or 0)
            if not lobby_id:
                continue
            if target_lobby_id and lobby_id != target_lobby_id:
                continue

            snapshot = self._get_lobby_metadata_snapshot(
                lobby_id,
                {
                    'host_name': lobby.get('name', ''),
                    'lobby_code': lobby.get('code', ''),
                    'visibility': lobby.get('visibility', ''),
                    'requires_code': lobby.get('requires_code'),
                    'metadata_ready': lobby.get('metadata_ready'),
                },
                prefer_live=True,
            )
            if snapshot['metadata_ready']:
                if snapshot['requires_code'] and snapshot['code'] == normalized_code:
                    if lobby_id not in matched_ids:
                        matched_ids.append(lobby_id)
                continue

            # Metadata henüz hazır değil — yine de kod eşleşmesi dene.
            # Cross-platform metadata propagasyonu gecikmeli olabilir;
            # lobby_code metadata'sı yoksa lobby_id'den derive edilen kodu
            # karşılaştırarak erken match sağla.
            snapshot_code = str(snapshot.get('code', '') or '').strip()
            if snapshot_code and snapshot_code == normalized_code:
                if lobby_id not in matched_ids:
                    matched_ids.append(lobby_id)
                continue
            # Snapshot'ta kod yoksa lobby_id'den hesapla ve dene
            try:
                derived_code = generate_lobby_code(lobby_id)
                if derived_code == normalized_code:
                    if lobby_id not in matched_ids:
                        matched_ids.append(lobby_id)
                    continue
            except Exception:
                pass

            pending_metadata = True

        if len(matched_ids) == 1:
            return matched_ids[0], pending_metadata, False
        if len(matched_ids) > 1:
            return 0, False, True
        return 0, pending_metadata, False

    def _on_lobby_found(self, ev: NetEvent):
        """Tek bir lobi bulundu — metadata ile birlikte biriktir."""
        payload = {}
        if ev.data:
            try:
                parsed = json.loads(ev.data)
                if isinstance(parsed, dict):
                    payload = parsed
            except Exception:
                payload = {}
        snapshot = self._get_lobby_metadata_snapshot(ev.steam_id, payload)

        # Payload'ta metadata gelmemişse (cross-platform propagasyon
        # gecikmesi), hemen live-read dene. Steam yerel cache'inde
        # metadata zaten bulunabilir; C++ bridge payload'u oluştururken
        # henüz replike olmamış olsa bile Python tarafından doğrudan
        # GetLobbyData çağrısı başarılı olabilir.
        if snapshot['visibility'] == 'unknown':
            live_snapshot = self._get_lobby_metadata_snapshot(
                ev.steam_id, payload, prefer_live=True)
            if live_snapshot['visibility'] != 'unknown':
                snapshot = live_snapshot

        member_count = 0
        try:
            if isinstance(payload.get('members'), int):
                member_count = int(payload.get('members', 0))
            elif ev.data and ev.data.isdigit():
                member_count = int(ev.data)
        except (ValueError, AttributeError, TypeError):
            member_count = 0

        max_members = 2
        try:
            if isinstance(payload.get('max_members'), int):
                max_members = max(2, int(payload.get('max_members', 2)))
        except (ValueError, TypeError):
            max_members = 2

        entry = {
            'id': ev.steam_id,
            'members': member_count,
            'max_members': max_members,
            'name': snapshot['name'] or f'Lobi #{len(self._pending_lobby_list) + 1}',
            'code': snapshot['code'],
            'visibility': snapshot['visibility'],
            'requires_code': snapshot['requires_code'],
            'metadata_ready': snapshot['metadata_ready'],
            'found_time': time.time(),
        }
        # Auto-refresh sonrası found_time sıfırlanmasını önle:
        # Önceki listede aynı lobi unknown olarak varsa eski found_time'ı koru.
        # Bu sayede stale_unknown timeout'u yeniden başlamaz.
        _prev_found_time = 0.0
        for _prev in getattr(self, '_lobby_list', []):
            if int(_prev.get('id', 0) or 0) == int(ev.steam_id or 0):
                _prev_found_time = float(_prev.get('found_time', 0) or 0)
                break
        if _prev_found_time and entry['visibility'] == 'unknown':
            entry['found_time'] = _prev_found_time
        if snapshot['visibility'] == 'unknown':
            # Metadata gecikse bile lobby kartini browse listesinde goster.
            # Boylece private lobby callback gelmediginde tamamen kaybolmaz;
            # sonraki live read / lobby_data_updated karti upgrade eder.
            self._remember_deferred_lobby_entry(entry)
        self._upsert_lobby_entry('_pending_lobby_list', entry)

    def _on_lobby_data_updated(self, ev: NetEvent):
        current_lobby_id = int(getattr(self.net, 'lobby_id', 0) or 0)

        # C++ bridge artık lobby_data_updated event'inde güncel metadata
        # payload'ını JSON olarak gönderebilir. Varsa parse et.
        payload = None
        if ev.data:
            try:
                parsed = json.loads(ev.data)
                if isinstance(parsed, dict):
                    payload = parsed
            except (json.JSONDecodeError, ValueError, TypeError):
                payload = None

        snapshot = self._get_lobby_metadata_snapshot(
            ev.steam_id, payload, prefer_live=True)
        self._refresh_cached_lobby_metadata(
            ev.steam_id, payload, prefer_live=True)
        self._promote_deferred_lobby_entry(ev.steam_id, snapshot)
        self._try_resolve_pending_code_join(ev.steam_id, snapshot)
        self._complete_pending_browser_join(ev.steam_id, snapshot)
        if current_lobby_id and int(ev.steam_id or 0) == current_lobby_id:
            # Ertelenmiş erişim yeniden-doğrulaması: _validate_joined_lobby_access
            # metadata unknown iken geçici izin vermiş olabilir. Metadata
            # artık hazır olduğunda tekrar doğrula.
            # SADECE pending revalidation aktifken doğrula. Aksi halde
            # her lobby_data_updated event'inde tekrar validation çalışır
            # ve daha önce temizlenmiş auth nedeniyle oyuncu kick yiyebilir.
            pending_revalidation = int(
                getattr(self, '_pending_access_revalidation_lobby_id', 0) or 0)
            if pending_revalidation == current_lobby_id:
                if snapshot.get('metadata_ready'):
                    self._pending_access_revalidation_lobby_id = 0
                    self._pending_revalidation_start_time = 0.0
                self._validate_joined_lobby_access()

    def _on_lobby_list_complete(self, ev: NetEvent):
        """Lobi listesi tamamlandı — sonuçları onayla."""
        self._lobby_list_fetching = False
        self._lobby_list_fetch_start_time = 0

        # Yeni sonuçları al
        new_entries = self._pending_lobby_list[:]
        self._pending_lobby_list.clear()

        # ── Mevcut lobi listesini merge et (flikör önleme) ──
        # Mevcut listeyi ID→entry map'e dönüştür
        _old_map: dict[int, dict] = {}
        for _ol in self._lobby_list:
            _oid = int(_ol.get('id', 0) or 0)
            if _oid:
                _old_map[_oid] = _ol

        # Yeni gelen listeyi ID→entry map'e dönüştür
        _new_map: dict[int, dict] = {}
        for _ne in new_entries:
            _nid = int(_ne.get('id', 0) or 0)
            if _nid:
                _new_map[_nid] = _ne

        # Merge stratejisi: mevcut entry'leri koru (found_time, scroll
        # pozisyonu), metadata'yı güncelle. Yeni lobiler sona ekle.
        merged: list[dict] = []
        for _ol in self._lobby_list:
            _oid = int(_ol.get('id', 0) or 0)
            if _oid in _new_map:
                # Mevcut lobi hâlâ var — metadata'yı güncelle
                _fresh = _new_map[_oid]
                _ol['members'] = _fresh.get('members', _ol.get('members', '?'))
                _ol['max_members'] = _fresh.get('max_members', _ol.get('max_members', 2))
                _ol['name'] = _fresh.get('name') or _ol.get('name', '')
                # Metadata ilerlemesini koru: unknown → resolved geçişi ok,
                # resolved → unknown geriye gitmemeli
                _old_vis = str(_ol.get('visibility', 'unknown') or 'unknown').lower()
                _new_vis = str(_fresh.get('visibility', 'unknown') or 'unknown').lower()
                if _new_vis not in ('unknown', 'stale_unknown') or _old_vis in ('unknown', 'stale_unknown'):
                    _ol['visibility'] = _fresh.get('visibility', _ol.get('visibility'))
                    _ol['requires_code'] = _fresh.get('requires_code', _ol.get('requires_code'))
                    _ol['code'] = _fresh.get('code', _ol.get('code', ''))
                    _ol['metadata_ready'] = _fresh.get('metadata_ready', _ol.get('metadata_ready'))
                merged.append(_ol)
            # else: lobi artık listede yok → kaldır (merged'e ekleme)

        # Yeni lobiler (önceki listede yoktu)
        for _nid, _ne in _new_map.items():
            if _nid not in _old_map:
                merged.append(_ne)

        self._lobby_list = merged
        # Scroll'u koru — sıfırlama

        # Kod ile arama yapılıyorsa filtre uygulamadan önce işle.
        # Kod araması private lobiler dahil tüm sonuçlara ihtiyaç duyar.
        if self._searching_by_code:
            count = len(self._lobby_list)
            print(f"[OnlinePvP] Kod araması: {count} lobi arasında aranıyor.")
            self._searching_by_code = False
            self._code_search_retry_use_full_scan = False
            matched_lobby_id, pending_metadata, ambiguous_match = self._find_lobby_match_by_code(self._search_code)
            if matched_lobby_id:
                self._code_search_retry_count = 0
                self._join_target_lobby_id = 0
                self._remember_private_join_authorization(matched_lobby_id, self._search_code)
                self.net.join_lobby(matched_lobby_id)
                self._status_msg = t('joining_lobby', 'Lobiye katılınıyor...')
                self._status_timer = 2.0
            elif ambiguous_match:
                self._code_search_retry_count = 0
                self._code_search_retry_timer = 0.0
                self._code_search_retry_code = ''
                self._code_search_retry_use_full_scan = False
                self._status_msg = t('lobby_code_ambiguous', 'Bu kod birden fazla lobiyle eslesiyor')
                self._status_timer = 3.0
            elif count == 0 or pending_metadata:
                self._code_search_fail_or_retry()
            else:
                self._code_search_retry_count = 0
                self._code_search_retry_timer = 0.0
                self._code_search_retry_code = ''
                self._code_search_retry_use_full_scan = False
                self._status_msg = t('lobby_not_found_by_code', 'Bu kodla lobi bulunamadı')
                self._status_timer = 3.0
            self._search_code = ''
            return

        # Client-side visibility filtreleme.
        # Sunucu tarafı filtre kaldırıldı (cross-platform metadata
        # propagasyonu güvenilmez). Filtreleme burada yapılır.
        # Not: 'public' filtresi unknown lobileri de gösterir —
        # metadata propague olduktan sonra private olanlar
        # _refresh_unknown_lobby_entries tarafından güncellenir
        # ve bir sonraki list refresh'te filtrelenir.
        if self._lobby_list_filter == 'public':
            self._lobby_list = [
                l for l in self._lobby_list
                if str(l.get('visibility', 'unknown') or 'unknown').lower()
                in ('public', 'unknown', 'stale_unknown')
            ]

        count = len(self._lobby_list)
        print(f"[OnlinePvP] {count} lobi bulundu (filtre={self._lobby_list_filter}).")

        if count == 0:
            self._status_msg = t('no_lobbies_found', 'Lobi bulunamadı')
            self._status_timer = 2.5

        # Unknown visibility'li entry'ler için ek metadata sorgusu başlat.
        # Cross-platform metadata propagasyonu gecikmeli olabilir; deferred
        # refresh zamanlayıcısını sıfırlayarak hemen tazeleme dene.
        self._refresh_unknown_lobby_entries()
        # Eğer public filtresi aktifse, refresh sonrası artık private olduğu
        # anlaşılan lobileri listeden kaldır.
        if self._lobby_list_filter == 'public':
            self._lobby_list = [
                l for l in self._lobby_list
                if str(l.get('visibility', 'unknown') or 'unknown').lower()
                in ('public', 'unknown', 'stale_unknown')
            ]

    def _refresh_unknown_lobby_entries(self):
        """_lobby_list'teki unknown visibility'li entry'leri live-read ile güncelle.

        Cross-platform metadata propagasyonu gecikmeli olabilir;
        her 500ms'de bir live read yaparak henüz çözülmemiş lobileri
        günceller. Ek olarak, eğer live read'lerden sadece lobby_code
        geldiyse visibility'yi türetir.
        """
        if not getattr(self, '_net_initialized', False):
            return
        for lobby in self._lobby_list:
            _vis = str(lobby.get('visibility', '') or '').lower()
            if _vis not in ('unknown', 'stale_unknown'):
                continue
            lobby_id = int(lobby.get('id', 0) or 0)
            if not lobby_id:
                continue
            self._request_lobby_metadata_refresh(lobby_id)
            snapshot = self._get_lobby_metadata_snapshot(lobby_id, prefer_live=True)
            if snapshot.get('visibility') not in (None, '', 'unknown'):
                lobby['name'] = snapshot.get('name') or lobby.get('name', '')
                lobby['code'] = snapshot.get('code', lobby.get('code', ''))
                lobby['visibility'] = snapshot.get('visibility', 'unknown')
                lobby['requires_code'] = bool(snapshot.get('requires_code', False))
                lobby['metadata_ready'] = bool(snapshot.get('metadata_ready', False))
                self._deferred_lobby_entries.pop(lobby_id, None)
                self._clear_lobby_metadata_refresh_request(lobby_id)
                self._complete_pending_browser_join(lobby_id, snapshot)
                continue

            # Live read hala unknown döndü — lobby_code veya
            # lobby_code_full alanlarını doğrudan oku ve türet.
            # Cross-platform'da bazen sadece bazı alanlar propague olur.
            try:
                raw_code = self.net.get_lobby_data_for(lobby_id, 'lobby_code')
                raw_code_full = self.net.get_lobby_data_for(lobby_id, 'lobby_code_full')
                raw_game = self.net.get_lobby_data_for(lobby_id, 'game')
            except Exception:
                raw_code = ''
                raw_code_full = ''
                raw_game = ''

            if raw_code or raw_code_full:
                # lobby_code var → private lobi olduğunu biliyoruz
                lobby['visibility'] = 'private'
                lobby['requires_code'] = True
                lobby['code'] = raw_code or _resolve_private_lobby_code(lobby_id, True, '')
                lobby['metadata_ready'] = True
                self._deferred_lobby_entries.pop(lobby_id, None)
                self._clear_lobby_metadata_refresh_request(lobby_id)
                self._complete_pending_browser_join(lobby_id, {
                    'id': lobby_id,
                    'name': lobby.get('name', ''),
                    'code': lobby['code'],
                    'visibility': lobby['visibility'],
                    'requires_code': lobby['requires_code'],
                    'metadata_ready': lobby['metadata_ready'],
                })
                try:
                    raw_host = self.net.get_lobby_data_for(lobby_id, 'host_name')
                    if raw_host:
                        lobby['name'] = raw_host
                except Exception:
                    pass
            elif raw_game == 'quadrix':
                # game=quadrix metadata'sı var ama visibility/lobby_code yok.
                # metadata_ready=1 olmalı; yoksa partial propagation olabilir
                # (game=quadrix server-side filtre olarak daima önce gelir,
                # diğer alanlar henüz propague olmamış olabilir).
                try:
                    raw_meta_ready = self.net.get_lobby_data_for(
                        lobby_id, 'metadata_ready')
                    raw_vis = self.net.get_lobby_data_for(
                        lobby_id, 'visibility')
                    raw_req = self.net.get_lobby_data_for(
                        lobby_id, 'requires_code')
                except Exception:
                    raw_meta_ready = ''
                    raw_vis = ''
                    raw_req = ''
                if raw_meta_ready == '1':
                    # metadata_ready=1 gelmiş. Ancak cross-platform'da
                    # SetLobbyData çağrıları bağımsız propagate olabilir;
                    # metadata_ready=1, visibility/requires_code'dan ÖNCE
                    # karşı platforma ulaşabilir. Bu nedenle visibility
                    # ve requires_code boşsa "public" varsaymıyoruz —
                    # partial propagation olarak unknown bırakıyoruz.
                    if raw_vis == 'private' or raw_req == '1':
                        # Private lobi ama lobby_code henüz propague olmamış
                        lobby['visibility'] = 'private'
                        lobby['requires_code'] = True
                        lobby['code'] = _resolve_private_lobby_code(
                            lobby_id, True, '')
                    elif raw_vis == 'public' or raw_req == '0':
                        # Açıkça public olarak işaretlenmiş
                        lobby['visibility'] = 'public'
                        lobby['requires_code'] = False
                        lobby['code'] = ''
                    else:
                        # metadata_ready=1 var ama visibility/requires_code
                        # henüz propague olmamış — partial propagation.
                        # Cross-platform'da SetLobbyData çağrıları bağımsız
                        # propagate olabilir; metadata_ready=1 diğer
                        # alanlardan ÖNCE karşı platforma ulaşabilir.
                        # 'public' varsaymak TAHLİKELİ — private lobi
                        # kodsuz giriş açığına yol açar. Unknown bırak;
                        # sonraki refresh veya lobby_data_updated çözecek.
                        continue
                    lobby['metadata_ready'] = True
                    self._deferred_lobby_entries.pop(lobby_id, None)
                    self._clear_lobby_metadata_refresh_request(lobby_id)
                    self._complete_pending_browser_join(lobby_id, {
                        'id': lobby_id,
                        'name': lobby.get('name', ''),
                        'code': lobby.get('code', ''),
                        'visibility': lobby['visibility'],
                        'requires_code': lobby['requires_code'],
                        'metadata_ready': lobby['metadata_ready'],
                    })
                    try:
                        raw_host = self.net.get_lobby_data_for(
                            lobby_id, 'host_name')
                        if raw_host:
                            lobby['name'] = raw_host
                    except Exception:
                        pass
                elif raw_vis in ('public', 'private') or raw_req in ('0', '1'):
                    # metadata_ready henüz yok ama visibility/requires_code
                    # gelmiş — türet
                    is_private = raw_vis == 'private' or raw_req == '1'
                    lobby['visibility'] = 'private' if is_private else 'public'
                    lobby['requires_code'] = is_private
                    lobby['metadata_ready'] = False
                    lobby['code'] = (
                        _resolve_private_lobby_code(lobby_id, True, '')
                        if is_private else ''
                    )
                    self._deferred_lobby_entries.pop(lobby_id, None)
                    self._clear_lobby_metadata_refresh_request(lobby_id)
                    self._complete_pending_browser_join(lobby_id, {
                        'id': lobby_id,
                        'name': lobby.get('name', ''),
                        'code': lobby.get('code', ''),
                        'visibility': lobby['visibility'],
                        'requires_code': lobby['requires_code'],
                        'metadata_ready': lobby['metadata_ready'],
                    })
                    try:
                        raw_host = self.net.get_lobby_data_for(
                            lobby_id, 'host_name')
                        if raw_host:
                            lobby['name'] = raw_host
                    except Exception:
                        pass
                # else: metadata henüz tam propague olmamış —
                # unknown bırak, sonraki refresh'te çözülür

    def _on_lobby_error(self, ev: NetEvent):
        """Lobi oluşturma/katılma hatası."""
        print(f"[OnlinePvP] Lobi hatası: {ev.type} — {ev.data}")
        self.online_state = OnlineState.LOBBY_MENU
        self._lobby_list_fetching = False
        self._lobby_list_fetch_start_time = 0
        # Detaylı hata mesajı oluştur
        error_detail = ''
        if ev.data:
            try:
                # C++ "result=X,visibility=...,requires_code=..." formatında gönderir
                for part in str(ev.data).split(','):
                    if part.startswith('result='):
                        code = part.split('=', 1)[1]
                        error_detail = f' (kod: {code})'
                        break
            except Exception:
                pass
        self._status_msg = t('lobby_error', 'Lobi işlemi başarısız oldu!') + error_detail
        self._status_timer = 4.0

    def _on_lobby_list_error(self, ev: NetEvent):
        """Lobi listesi alınamadı."""
        self._lobby_list_fetching = False
        self._lobby_list_fetch_start_time = 0
        self._lobby_list = []
        self._code_search_retry_count = 0
        self._code_search_retry_timer = 0.0
        self._code_search_retry_code = ''
        self._code_search_retry_use_full_scan = False
        if self._searching_by_code:
            self._searching_by_code = False
            self._search_code = ''
            self._status_msg = t('lobby_not_found_by_code', 'Bu kodla lobi bulunamadı')
            self._status_timer = 3.0
        else:
            self._status_msg = t('lobby_list_error', 'Lobi listesi alınamadı')
            self._status_timer = 3.0

    def _on_join_requested(self, ev: NetEvent):
        """Steam overlay'den 'Oyuna Katıl' tıklandı.

        steam_networking.py zaten otomatik JoinLobby() yapıyor.
        Burada UI durumunu güncelliyoruz — eğer lobi menüsündeysek
        bekleme ekranına geçiş yapılmalı.
        """
        print(f"[OnlinePvP] Steam overlay katılım isteği: lobby={ev.steam_id}")
        # UI'ı güncelle — gelen join_requested sonrası lobby_joined event'i
        # otomatik olarak WAITING state'e geçirecek.
        # Burada sadece kullanıcıya geri bildirim veriyoruz.
        self._invite_authorized_lobby_id = int(ev.steam_id or 0)
        self._status_msg = t('joining_lobby', 'Lobiye katılınıyor...')
        self._status_timer = 2.0

    def _request_lobby_list(self) -> bool:
        """Seçili filtreye göre lobi listesini yenile.

        'public' filter: Server-side + client-side visibility filtresi.
        'all' filter: Tüm Quadrix lobileri (private dahil).

        Sunucu tarafı filtre cross-platform metadata propagasyonuna
        bağlıdır; yeni oluşturulan lobiler metadata replicate olana
        kadar filtre tarafından yanlış elenebilir. Bu nedenle 'public'
        filtre mod yalnızca UI'daki ek client-side filtreyle desteklenir.
        """
        if self._is_online_pvp_trailer_debug_enabled():
            self._lobby_list_fetching = False
            self._lobby_list_fetch_start_time = 0
            self._pending_lobby_list.clear()
            self._deferred_lobby_entries.clear()
            self._clear_lobby_metadata_refresh_request()
            return True
        if not self._init_networking():
            return False
        if self._lobby_list_fetching:
            return True
        self._lobby_list_fetching = True
        self._lobby_list_fetch_start_time = time.time()
        self._auto_lobby_refresh_timer = self._auto_lobby_refresh_interval
        self._pending_lobby_list.clear()
        self._deferred_lobby_entries.clear()
        self._clear_lobby_metadata_refresh_request()
        # Not: Sunucu tarafı visibility filtresi kaldırıldı.
        # Cross-platform metadata propagasyon gecikmeleri nedeniyle
        # sunucu tarafı filtre özel lobileri herkese açık gibi
        # gösterebilir veya yeni oluşturulan lobileri tamamen gizleyebilir.
        # Filtreleme artık _on_lobby_list_complete içinde client-side yapılır.
        self.net.request_lobby_list(worldwide=True)
        return True

    def _begin_code_search(self, code: str, fallback_scan: bool = False):
        normalized_code = (code or '').strip()
        if not normalized_code:
            return
        self._searching_by_code = True
        self._search_code = normalized_code
        self._lobby_list_fetching = True
        self._lobby_list_fetch_start_time = time.time()
        self._pending_lobby_list.clear()
        self._deferred_lobby_entries.clear()
        self._clear_lobby_metadata_refresh_request()
        self._code_search_retry_use_full_scan = bool(fallback_scan)
        if fallback_scan:
            # Tam tarama: Tüm Quadrix lobilerini getir, client-side kod eşleştir
            self.net.request_lobby_list(worldwide=True)
            return
        # Önce sunucu tarafı lobby_code filtresi dene (hızlı ama
        # cross-platform metadata gecikmelerinde başarısız olabilir)
        self.net.search_lobby_by_code(normalized_code)

    def _set_lobby_list_filter(self, lobby_filter: str, refresh: bool = True) -> bool:
        """Lobi listesi filtresini güncelle."""
        normalized = 'public' if str(lobby_filter).lower() == 'public' else 'all'
        changed = normalized != self._lobby_list_filter
        self._lobby_list_filter = normalized
        if changed:
            self._lobby_list_scroll = 0
        if refresh:
            return self._request_lobby_list()
        return changed

    def _code_search_fail_or_retry(self):
        """Kod araması başarısız — retry hakkı varsa zamanlayıcı kur, yoksa hata göster.

        İlk retry'dan itibaren full scan (worldwide, filtre yok) kullanır.
        Cross-platform metadata propagasyon gecikmelerinde sunucu tarafı
        lobby_code filtresi boş döner; full scan + client-side kod karşılaştırma
        + lobby_id türetmeli eşleştirme çok daha güvenilirdir.
        """
        if self._code_search_retry_count < 2 and self._search_code:
            self._code_search_retry_count += 1
            self._code_search_retry_timer = 1200.0  # 1.2 saniye (daha hızlı retry)
            self._code_search_retry_code = self._search_code
            # İlk retry'dan itibaren full scan kullan — sunucu tarafı
            # lobby_code filtresi cross-platform'da güvenilmez
            self._code_search_retry_use_full_scan = True
            self._status_msg = t('searching_by_code', 'Lobi kodu aranıyor...')
            self._status_timer = 3.0
            print(f"[OnlinePvP] Kod araması retry #{self._code_search_retry_count} — full scan ile 1.2s sonra tekrar denenecek")
        else:
            self._code_search_retry_count = 0
            self._code_search_retry_timer = 0.0
            self._code_search_retry_code = ''
            self._code_search_retry_use_full_scan = False
            self._status_msg = t('lobby_not_found_by_code', 'Bu kodla lobi bulunamadı')
            self._status_timer = 3.0

    def _return_to_pvp_lobby_menu(self):
        """Aktif lobiden ayrıl ve Online PvP giriş ekranına dön."""
        self.net.leave_lobby()
        self.online_state = OnlineState.LOBBY_MENU
        self.my_ready = False
        self.opponent_ready = False
        self._ready_resend_timer = 0.0
        self._session_established = False
        self._ready_send_pending = False
        self._pending_disconnect_steam_id = 0
        self._disconnect_grace_timer = 0.0
        self._session_ping_timer = 0.0
        self._session_ping_backoff_ms = 0.0
        self._game_start_pending_payload = None
        self._game_start_retry_timer = 0.0
        self._reset_match_result_state()
        self.paused = False
        self.opponent_paused = False
        self._clear_opponent_piece_state()
        self._opponent_piece_seq = 0
        self._lobby_code = ''
        self._lobby_id_str = ''
        self._join_code_active = False
        self._join_code_input = ''
        self._join_code_error = ''
        self._join_target_lobby_id = 0
        self._pending_browser_join_lobby_id = 0
        self._searching_by_code = False
        self._search_code = ''
        self._code_search_retry_count = 0
        self._code_search_retry_timer = 0.0
        self._code_search_retry_code = ''
        self._code_search_retry_use_full_scan = False
        self._clear_private_join_authorization()
        self._pending_access_revalidation_lobby_id = 0
        self._pending_revalidation_start_time = 0.0
        self._lobby_access_validated_id = 0
        self._lobby_list_filter = 'all'
        self._lobby_list_fetching = False
        self._lobby_list_fetch_start_time = 0
        self._auto_lobby_refresh_requested = False
        self._auto_lobby_refresh_timer = 0.0
        self._auto_connect_retry_timer = 0.0
        self._pending_lobby_list.clear()
        self._deferred_lobby_entries.clear()
        self._status_msg = ''
        self._status_timer = 0
        self._invite_after_lobby = False
        self._creating_public_lobby = False

    # ============================================================
    #  MESAJ İŞLEME
    # ============================================================

    # ── Mesaj doğrulama yardımcıları ────────────────────────────────────

    @staticmethod
    def _clamp_int(value, lo: int, hi: int, field: str = '') -> int:
        """value'yu int'e cast et ve [lo, hi] aralığına clamp et.
        Dönüştürme başarısız olursa lo döner (sessiz ignore)."""
        try:
            v = int(value)
        except (TypeError, ValueError):
            print(f"[OnlinePvP] Alan doğrulama: '{field}' int'e dönüştürülemedi — {value!r}")
            return lo
        return max(lo, min(v, hi))

    def _reset_match_result_state(self):
        """Maç sonu sonucunu belirleyen bayrakları sıfırla."""
        self.game_over = False
        self.winner = ''
        self.my_eliminated = False
        self.opponent_eliminated = False
        self._my_final_board_filled = False
        self._opponent_final_board_filled = False
        self._opponent_final_score = 0
        self._opponent_final_lines = 0
        self._match_result_recorded = False

    def _record_match_result(self):
        """Online PvP galibiyetini achievement stats'a tek sefer yansıt."""
        if getattr(self, '_match_result_recorded', False):
            return
        self._match_result_recorded = True

        if self.winner != 'me':
            return

        achievement_manager = getattr(self, 'achievement_manager', None)
        if not achievement_manager:
            return

        try:
            stats = achievement_manager.stats
            stats['pvp_wins'] = int(stats.get('pvp_wins', 0) or 0) + 1
            achievement_manager.update_stats()
        except Exception as exc:
            print(f"[OnlinePvP] Başarım istatistiği güncellenemedi: {exc}")

    def _get_opponent_result_metrics(self) -> tuple[int, int, bool]:
        """Rakibin final değerlendirmede kullanılacak metriklerini döndür."""
        live_score = int(getattr(self, 'opponent_score', 0) or 0)
        live_lines = int(getattr(self, 'opponent_lines', 0) or 0)
        if getattr(self, 'opponent_eliminated', False):
            final_score = int(getattr(self, '_opponent_final_score', 0) or 0)
            final_lines = int(getattr(self, '_opponent_final_lines', 0) or 0)
            # Eski/eksik payload'larda final skor gelmeyebilir; o durumda son bilinen
            # canlı değeri koru. Skor ve temizlenen satırlar monoton arttığı için max güvenlidir.
            opp_score = max(live_score, final_score)
            opp_lines = max(live_lines, final_lines)
        else:
            opp_score = live_score
            opp_lines = live_lines

        opp_board_filled = bool(
            getattr(self, '_opponent_final_board_filled', False)
            or getattr(self, 'opponent_eliminated', False)
        )
        return opp_score, opp_lines, opp_board_filled

    def _get_result_player_names(self) -> tuple[str, str]:
        """Sonuç ekranı için oyuncu adlarını güvenli biçimde döndür."""
        lang = get_language()
        my_name = 'Sen' if lang == 'tr' else 'You'
        try:
            my_steam_id = int(getattr(self.net, 'my_steam_id', 0) or 0)
        except Exception:
            my_steam_id = 0

        try:
            if my_steam_id and hasattr(self.net, '_get_name'):
                resolved = self.net._get_name(my_steam_id)
                if resolved:
                    my_name = str(resolved)
        except Exception:
            pass

        try:
            opp_name = getattr(self.net, 'opponent_name', None) or ('Rakip' if lang == 'tr' else 'Opponent')
        except Exception:
            opp_name = 'Rakip' if lang == 'tr' else 'Opponent'
        return str(my_name), str(opp_name)

    def _build_majority_result_breakdown(self) -> dict[str, object]:
        """Ağırlıklı sonuç hesabı için tüm karşılaştırma verisini çıkar."""
        my_score = int(getattr(self.my_board, 'score', 0) or 0)
        my_lines = int(getattr(self.my_board, 'lines_cleared', 0) or 0)
        my_board_filled = bool(
            getattr(self, '_my_final_board_filled', False)
            or getattr(self, 'my_eliminated', False)
        )
        opp_score, opp_lines, opp_board_filled = self._get_opponent_result_metrics()
        my_name, opp_name = self._get_result_player_names()

        if my_score > opp_score:
            score_state = 'me'
            my_score_point = ONLINE_PVP_RESULT_SCORE_POINTS
            opp_score_point = 0
        elif opp_score > my_score:
            score_state = 'opponent'
            my_score_point = 0
            opp_score_point = ONLINE_PVP_RESULT_SCORE_POINTS
        else:
            score_state = 'draw'
            my_score_point = 0
            opp_score_point = 0

        if my_lines > opp_lines:
            lines_state = 'me'
            my_lines_point = ONLINE_PVP_RESULT_LINES_POINTS
            opp_lines_point = 0
        elif opp_lines > my_lines:
            lines_state = 'opponent'
            my_lines_point = 0
            opp_lines_point = ONLINE_PVP_RESULT_LINES_POINTS
        else:
            lines_state = 'draw'
            my_lines_point = 0
            opp_lines_point = 0

        if not my_board_filled and not opp_board_filled:
            board_state = 'both'
            my_board_point = ONLINE_PVP_RESULT_BOARD_OPEN_POINTS
            opp_board_point = ONLINE_PVP_RESULT_BOARD_OPEN_POINTS
        elif not my_board_filled and opp_board_filled:
            board_state = 'me'
            my_board_point = ONLINE_PVP_RESULT_BOARD_OPEN_POINTS
            opp_board_point = 0
        elif my_board_filled and not opp_board_filled:
            board_state = 'opponent'
            my_board_point = 0
            opp_board_point = ONLINE_PVP_RESULT_BOARD_OPEN_POINTS
        else:
            board_state = 'none'
            my_board_point = 0
            opp_board_point = 0

        my_points = my_score_point + my_lines_point + my_board_point
        opp_points = opp_score_point + opp_lines_point + opp_board_point

        if my_points >= ONLINE_PVP_RESULT_WIN_THRESHOLD and opp_points < ONLINE_PVP_RESULT_WIN_THRESHOLD:
            winner = 'me'
        elif opp_points >= ONLINE_PVP_RESULT_WIN_THRESHOLD and my_points < ONLINE_PVP_RESULT_WIN_THRESHOLD:
            winner = 'opponent'
        else:
            winner = 'draw'

        return {
            'winner': winner,
            'my_name': my_name,
            'opp_name': opp_name,
            'my_score': my_score,
            'opp_score': opp_score,
            'my_lines': my_lines,
            'opp_lines': opp_lines,
            'score_state': score_state,
            'lines_state': lines_state,
            'board_state': board_state,
            'my_board_filled': my_board_filled,
            'opp_board_filled': opp_board_filled,
            'my_board_point': my_board_point,
            'opp_board_point': opp_board_point,
            'my_points': my_points,
            'opp_points': opp_points,
        }

    @staticmethod
    def _pick_result_text_variant(options: list[str], seed: int) -> str:
        """Deterministik metin varyasyonu seç."""
        if not options:
            return ''
        return options[abs(int(seed)) % len(options)]

    @staticmethod
    def _join_result_fragments(parts: list[str]) -> str:
        """Kısa ifade listelerini doğal cümle parçasına çevir."""
        clean_parts = [str(part).strip() for part in parts if str(part).strip()]
        if not clean_parts:
            return ''
        if len(clean_parts) == 1:
            return clean_parts[0]
        if len(clean_parts) == 2:
            return f"{clean_parts[0]} ve {clean_parts[1]}"
        return f"{', '.join(clean_parts[:-1])} ve {clean_parts[-1]}"

    def _build_majority_result_reason_text(self, result: dict[str, object] | None = None) -> str:
        """Kazanan/kaybeden nedenini 2-3 cümlelik kalıp metinle açıkla."""
        if result is None:
            result = self._build_majority_result_breakdown()

        lang = get_language()
        my_name = str(result.get('my_name', 'Sen' if lang == 'tr' else 'You'))
        opp_name = str(result.get('opp_name', 'Rakip' if lang == 'tr' else 'Opponent'))
        winner = str(result.get('winner', 'draw'))
        score_state = str(result.get('score_state', 'draw'))
        lines_state = str(result.get('lines_state', 'draw'))
        board_state = str(result.get('board_state', 'none'))
        my_points = int(result.get('my_points', 0) or 0)
        opp_points = int(result.get('opp_points', 0) or 0)
        rule_text_tr = 'Skor ve satır 1, alan ise 2 puan sayıldı.'
        rule_text_en = 'Score and lines counted as 1 point each, while board control counted as 2.'
        seed = (
            int(result.get('my_score', 0) or 0) * 3
            + int(result.get('opp_score', 0) or 0) * 5
            + int(result.get('my_lines', 0) or 0) * 7
            + int(result.get('opp_lines', 0) or 0) * 11
            + my_points * 13
            + opp_points * 17
        )

        if lang != 'tr':
            def side_name_en(side: str) -> str:
                return my_name if side == 'me' else opp_name

            def join_en(parts: list[str]) -> str:
                clean_parts = [str(part).strip() for part in parts if str(part).strip()]
                if not clean_parts:
                    return ''
                if len(clean_parts) == 1:
                    return clean_parts[0]
                if len(clean_parts) == 2:
                    return f"{clean_parts[0]} and {clean_parts[1]}"
                return f"{', '.join(clean_parts[:-1])}, and {clean_parts[-1]}"

            my_unique_en: list[str] = []
            opp_unique_en: list[str] = []
            shared_en: list[str] = []

            if score_state == 'me':
                my_unique_en.append('finished with the higher score')
            elif score_state == 'opponent':
                opp_unique_en.append('finished with the higher score')
            else:
                shared_en.append('the score stayed tied')

            if lines_state == 'me':
                my_unique_en.append('cleared more lines')
            elif lines_state == 'opponent':
                opp_unique_en.append('cleared more lines')
            else:
                shared_en.append('line clears stayed even')

            if board_state == 'me':
                my_unique_en.append('kept the board open')
            elif board_state == 'opponent':
                opp_unique_en.append('kept the board open')
            elif board_state == 'both':
                shared_en.append('both players kept their boards open')
            else:
                shared_en.append('both players topped out')

            if winner == 'draw':
                summary_options = [
                    'The weighted result check ended without a winner.',
                    'The result points finished level, so the round ended in a draw.',
                    'Neither side built enough of an edge in the weighted scoring.',
                ]
                summary = self._pick_result_text_variant(summary_options, seed)
                detail_parts = []
                if my_unique_en:
                    detail_parts.append(f"{my_name} {join_en(my_unique_en)}")
                if opp_unique_en:
                    detail_parts.append(f"{opp_name} {join_en(opp_unique_en)}")
                if shared_en:
                    detail_parts.append(join_en(shared_en).capitalize())
                if detail_parts:
                    return f"{summary} {rule_text_en} {'. '.join(detail_parts)}.".strip()
                return f"{summary} {rule_text_en}".strip()

            winner_side = winner
            loser_side = 'opponent' if winner_side == 'me' else 'me'
            winner_name = side_name_en(winner_side)
            loser_name = side_name_en(loser_side)
            winner_points = my_points if winner_side == 'me' else opp_points
            loser_points = opp_points if winner_side == 'me' else my_points
            winner_unique_en = my_unique_en if winner_side == 'me' else opp_unique_en
            loser_unique_en = opp_unique_en if winner_side == 'me' else my_unique_en

            summary_options = [
                f"{winner_name} won the match by reaching {winner_points} weighted result points.",
                f"The weighted decision score finished {winner_points}-{loser_points} in favor of {winner_name}.",
                f"{winner_name} secured the round with {winner_points} result points in the weighted check.",
            ]
            summary = self._pick_result_text_variant(summary_options, seed)
            winner_clause = f"{winner_name} {join_en(winner_unique_en)}"
            if loser_unique_en:
                detail_options = [
                    f"Even though {loser_name} {join_en(loser_unique_en)}, {winner_clause}.",
                    f"{loser_name} {join_en(loser_unique_en)}, but {winner_clause}.",
                ]
            elif shared_en:
                detail_options = [
                    f"{join_en(shared_en).capitalize()}, but {winner_clause}.",
                    f"{join_en(shared_en).capitalize()}. That still left the edge to {winner_clause}.",
                ]
            else:
                detail_options = [
                    f"{winner_clause}. {loser_name} fell behind on all three criteria.",
                    f"{winner_clause} and left {loser_name} without a single decision point.",
                ]
            detail = self._pick_result_text_variant(detail_options, seed + 23)
            return f"{summary} {rule_text_en} {detail}".strip()

        def side_name(side: str) -> str:
            return my_name if side == 'me' else opp_name

        def subject_clause(side: str, criteria: list[str], *, concessive: bool, seed_offset: int) -> str:
            name = side_name(side)
            option_map = {
                'score': {
                    False: ['skorda öne geçti', 'daha yüksek puana ulaştı', 'skor üstünlüğünü aldı'],
                    True: ['skorda önde olsa da', 'daha yüksek puana ulaşsa da', 'skor üstünlüğünü alsa da'],
                },
                'lines': {
                    False: ['daha çok satır temizledi', 'satır temizliğinde öne geçti', 'satır sayısında üstün kaldı'],
                    True: ['daha çok satır temizlese de', 'satır temizliğinde önde olsa da', 'satır sayısında üstün görünse de'],
                },
                'board': {
                    False: ['oyun alanını açık tuttu', 'tahtasını taşırmadı', 'alan kontrolünü korudu'],
                    True: ['oyun alanını açık tutsa da', 'tahtasını taşırmasa da', 'alan kontrolünü korusa da'],
                },
            }
            fragments = []
            for idx, criterion in enumerate(criteria):
                fragments.append(
                    self._pick_result_text_variant(
                        option_map[criterion][concessive],
                        seed + seed_offset + idx * 9,
                    )
                )
            return f"{name} {self._join_result_fragments(fragments)}"

        def shared_clause(tokens: list[str], *, seed_offset: int) -> str:
            option_map = {
                'score_tie': ['skor başlığı eşit kaldı', 'skor taraflara üstünlük vermedi'],
                'lines_tie': ['satır temizliği dengede kaldı', 'satır sayısı eşitlendi'],
                'board_both': ['iki oyuncu da oyun alanını açık tuttu', 'iki tahta da dolmadan kaldı'],
                'board_none': ['iki oyuncu da oyun alanını doldurdu', 'iki tahta da taşınca alan puanı çıkmadı'],
            }
            fragments = []
            for idx, token in enumerate(tokens):
                fragments.append(
                    self._pick_result_text_variant(option_map[token], seed + seed_offset + idx * 7)
                )
            return self._join_result_fragments(fragments)

        my_unique: list[str] = []
        opp_unique: list[str] = []
        shared: list[str] = []

        if score_state == 'me':
            my_unique.append('score')
        elif score_state == 'opponent':
            opp_unique.append('score')
        else:
            shared.append('score_tie')

        if lines_state == 'me':
            my_unique.append('lines')
        elif lines_state == 'opponent':
            opp_unique.append('lines')
        else:
            shared.append('lines_tie')

        if board_state == 'me':
            my_unique.append('board')
        elif board_state == 'opponent':
            opp_unique.append('board')
        elif board_state == 'both':
            shared.append('board_both')
        else:
            shared.append('board_none')

        if winner == 'draw':
            summary_options = [
                'Ağırlıklı sonuç puanlaması kazanan çıkarmadı.',
                'Sonuç puanları dengede kaldığı için maç berabere bitti.',
                'Taraflar ağırlıklı karar hesabında üstünlük kuramadı.',
            ]
            summary = self._pick_result_text_variant(summary_options, seed)
            details: list[str] = []
            if my_unique:
                details.append(subject_clause('me', my_unique, concessive=False, seed_offset=41))
            if opp_unique:
                details.append(subject_clause('opponent', opp_unique, concessive=False, seed_offset=53))
            shared_text = shared_clause(shared, seed_offset=67) if shared else ''
            if details and shared_text:
                detail = f"{'. '.join(details)}. {shared_text.capitalize()} ve üç puanlık eşik aşılmadı."
            elif details:
                detail = f"{'. '.join(details)}. Bu yüzden denge bozulmadı."
            else:
                detail = f"{shared_text.capitalize()}. Bu yüzden denge bozulmadı." if shared_text else 'Başlıklar dengede kaldı.'
            return f"{summary} {rule_text_tr} {detail}".strip()

        winner_side = winner
        loser_side = 'opponent' if winner_side == 'me' else 'me'
        winner_name = side_name(winner_side)
        winner_points = my_points if winner_side == 'me' else opp_points
        loser_points = opp_points if winner_side == 'me' else my_points
        winner_unique = my_unique if winner_side == 'me' else opp_unique
        loser_unique = opp_unique if winner_side == 'me' else my_unique

        summary_options = [
            f"{winner_name}, ağırlıklı sonuç puanlamasında {winner_points} puana ulaşarak maçı kazandı.",
            f"Ağırlıklı karar puanı {winner_points}-{loser_points} bitti; üstünlük {winner_name} tarafına yazıldı.",
            f"{winner_name}, ağırlıklı sonuç hesabında {winner_points} puan toplayıp raundu kapattı.",
        ]
        summary = self._pick_result_text_variant(summary_options, seed)
        winner_text = subject_clause(winner_side, winner_unique, concessive=False, seed_offset=79)
        shared_text = shared_clause(shared, seed_offset=97) if shared else ''

        if loser_unique:
            loser_text = subject_clause(loser_side, loser_unique[:1], concessive=True, seed_offset=89)
            if shared_text:
                detail_options = [
                    f"{loser_text} {winner_text}. {shared_text.capitalize()}.",
                    f"{loser_text} {winner_text}; {shared_text}.",
                ]
            else:
                detail_options = [
                    f"{winner_text}. Buna rağmen {'senin taraf' if loser_side == 'me' else 'rakip taraf'} galibiyet eşiğini geçemedi.",
                    f"{winner_text}. {'Senin tarafın' if loser_side == 'me' else 'Rakip taraf'} bu yüzden sonuç puanında geride kaldı.",
                ]
        elif shared_text:
            detail_options = [
                f"{shared_text.capitalize()}. Buna rağmen {winner_text} maçı belirledi.",
                f"{shared_text.capitalize()} ama farkı {winner_text} yarattı.",
            ]
        else:
            detail_options = [
                f"{winner_text}. {side_name(loser_side)} bu turda hiç ölçüt alamadı.",
                f"{winner_text}. {side_name(loser_side)} üç başlığın tamamında geride kaldı.",
            ]

        detail = self._pick_result_text_variant(detail_options, seed + 23)
        return f"{summary} {rule_text_tr} {detail}".strip()

    def _resolve_majority_match_winner(self) -> tuple[str, dict[str, object]]:
        """Ağırlıklı sonuç puanlamasıyla kazananı belirle."""
        result = self._build_majority_result_breakdown()
        return str(result['winner']), result

    def _finalize_elimination_result(self):
        """Ağırlıklı sonuç puanlamasıyla kazananı hesapla."""
        if not self.my_eliminated and not self.opponent_eliminated:
            return

        self.winner, result = self._resolve_majority_match_winner()
        was_game_over = self.online_state == OnlineState.GAME_OVER

        print(
            "[OnlinePvP] Agirlikli sonuc puanlama "
            f"my(score={result['my_score']}, lines={result['my_lines']}, board={result['my_board_point']}) "
            f"opp(score={result['opp_score']}, lines={result['opp_lines']}, board={result['opp_board_point']}) "
            f"=> totals {result['my_points']}-{result['opp_points']} winner={self.winner}"
        )

        self.game_over = True
        self.online_state = OnlineState.GAME_OVER

        if not was_game_over:
            sound_name = 'tetris' if self.winner == 'me' else 'gameover'
            try:
                self.sound.play(sound_name)
            except Exception:
                pass

        self._record_match_result()

    def _mark_local_eliminated(self):
        """Kendi elenmeni işle ve final skorunu rakibe gönder."""
        if self.my_eliminated:
            return

        already_game_over = bool(getattr(self, 'game_over', False))
        self.my_eliminated = True
        self._my_final_board_filled = True
        # Gamepad titreşimi - game over (uzun, güçlü)
        try:
            from gamepad_manager import get_gamepad_manager
            get_gamepad_manager().rumble(1.0, 1.0, 600)
        except Exception:
            pass
        if (
            self.my_board
            and getattr(self, 'net', None)
            and self.online_state in (OnlineState.PLAYING, OnlineState.GAME_OVER)
        ):
            try:
                self.net.send_game_over(
                    self.my_board.score,
                    self.my_board.lines_cleared,
                    board_filled=True,
                )
            except Exception as exc:
                print(f"[OnlinePvP] Final GAME_OVER gonderimi basarisiz: {exc}")
        if not already_game_over:
            self._finalize_elimination_result()

    def _mark_opponent_eliminated(
        self,
        score: int | None = None,
        lines: int | None = None,
        board_filled: bool = True,
    ):
        """Rakibin elendiğini işle."""
        self._clear_opponent_piece_state()
        self.opponent_eliminated = True
        self._opponent_final_board_filled = bool(board_filled)
        if score is not None:
            self._opponent_final_score = int(score)
            self.opponent_score = int(score)
        if lines is not None:
            self._opponent_final_lines = int(lines)
            self.opponent_lines = int(lines)
        if not getattr(self, 'game_over', False):
            self._finalize_elimination_result()

    @staticmethod
    def _validate_grid(grid) -> bool:
        """grid'in beklenen boyutlarda olduğunu doğrula."""
        if not isinstance(grid, list):
            return False
        if len(grid) != BOARD_HEIGHT:
            return False
        for row in grid:
            if not isinstance(row, list) or len(row) != BOARD_WIDTH:
                return False
        return True

    # ────────────────────────────────────────────────────────────────────

    def _process_messages(self):
        """Gelen ağ mesajlarını işle."""
        for msg in self.net.get_messages():
            try:
                data = msg.data
                msg_type = data.get('type', '')
            except Exception:
                continue

            # ── Gönderici doğrulaması ──────────────────────────────────
            # Rakip ID biliniyorsa yalnızca ondan gelen mesajları işle.
            opponent_id = self.net.opponent_steam_id
            my_id = int(getattr(self.net, 'my_steam_id', 0) or 0)
            try:
                sender = int(getattr(msg, 'sender', 0) or 0)
            except (TypeError, ValueError):
                sender = 0
            if not sender and isinstance(data, dict):
                try:
                    payload_sender = int(data.get('sender_id', 0) or 0)
                except (TypeError, ValueError):
                    payload_sender = 0
                if payload_sender and payload_sender != my_id:
                    sender = payload_sender

            if (not opponent_id) and sender and sender != my_id:
                can_bind_from_sender = True
                try:
                    members = set(self.net.get_lobby_members() or [])
                    if members:
                        can_bind_from_sender = sender in members
                except Exception:
                    can_bind_from_sender = True

                if can_bind_from_sender:
                    try:
                        self.net._opponent_steam_id = sender
                        opponent_id = sender
                        print(f"[OnlinePvP] opponent_steam_id mesajdan set edildi: {sender}")
                    except Exception:
                        pass

            if opponent_id and sender != opponent_id:
                rebound = False
                if self.online_state in (OnlineState.WAITING, OnlineState.READY_CHECK, OnlineState.COUNTDOWN):
                    try:
                        members = set(self.net.get_lobby_members() or [])
                    except Exception:
                        members = set()
                    if sender in members and sender != my_id:
                        try:
                            self.net._opponent_steam_id = sender
                            opponent_id = sender
                            rebound = True
                            print(f"[OnlinePvP] opponent sender rebind: {sender}")
                        except Exception:
                            rebound = False
                if not rebound:
                    print(f"[OnlinePvP] Bilinmeyen gönderici {sender} — mesaj ignore edildi.")
                    continue

            pending_disconnect_id = int(getattr(self, '_pending_disconnect_steam_id', 0) or 0)
            if sender and (sender == opponent_id or (pending_disconnect_id and sender == pending_disconnect_id)):
                self._pending_disconnect_steam_id = 0
                self._disconnect_grace_timer = 0.0

            if (not bool(getattr(self, '_session_established', False))) and opponent_id and sender == opponent_id:
                self._session_established = True
                print(f"[OnlinePvP] P2P session mesajla doğrulandı: {sender}")
                if self.online_state == OnlineState.READY_CHECK and self.my_ready and not self.opponent_ready:
                    self._send_ready_signal(reason='message_session_established')

            if msg_type == MsgType.READY:
                self.opponent_ready = True
                self._check_both_ready()

            elif msg_type == 'session_ping':
                if self.online_state == OnlineState.READY_CHECK and self.my_ready and not self.opponent_ready:
                    self._send_ready_signal(reason='peer_session_ping')

            elif msg_type == MsgType.GAME_START:
                try:
                    seed = int(data.get('seed', 0))
                except (TypeError, ValueError):
                    seed = 0
                self.game_seed = seed
                pieces = data.get('pieces', [])
                if isinstance(pieces, list):
                    # Aşırı uzun listeyi kırp (max 500)
                    self.piece_sequence = pieces[:500]
                self._start_countdown()

            elif msg_type == MsgType.GARBAGE_ATTACK:
                lines = self._clamp_int(data.get('lines', 0), 0, 20, 'lines')
                raw_gap = data.get('gap', -1)
                # gap: -1 sentinel (rastgele gap) ya da [0, BOARD_WIDTH-1]
                try:
                    gap_int = int(raw_gap)
                except (TypeError, ValueError):
                    gap_int = -1
                if gap_int < -1:
                    gap_int = -1
                elif gap_int > BOARD_WIDTH - 1:
                    gap_int = BOARD_WIDTH - 1
                self._receive_garbage(lines, gap_int)

            elif msg_type == MsgType.BOARD_STATE:
                # Grid boyut doğrulaması — hatalı boyutsa tüm mesajı ignore et
                grid = data.get('grid')
                if grid is not None and not self._validate_grid(grid):
                    print(
                        f"[OnlinePvP] BOARD_STATE: geçersiz grid boyutu "
                        f"(rows={len(grid) if isinstance(grid, list) else 'N/A'}) — ignore."
                    )
                    continue
                self._update_opponent_display(data)

            elif msg_type == MsgType.PIECE_POSITION:
                # Gerçek zamanlı rakip parça pozisyonu
                seq = data.get('seq', 0)
                try:
                    seq = int(seq)
                except (TypeError, ValueError):
                    seq = 0
                if seq >= self._opponent_piece_seq:
                    piece_payload = {
                        'si': data.get('si', 0),
                        'x': data.get('x', 0),
                        'y': data.get('y', 0),
                        'r': data.get('r', 0),
                    }
                    if self._normalize_opponent_piece_payload(piece_payload) is None:
                        print(f"[OnlinePvP] PIECE_POSITION: gecersiz parca payload'u (seq={seq}) - ignore.")
                        continue
                    if self._set_opponent_piece_state(piece_payload):
                        self._opponent_piece_seq = seq

            elif msg_type == MsgType.SCORE_UPDATE:
                self.opponent_score = self._clamp_int(data.get('score', 0), 0, 999999, 'score')
                self.opponent_lines = self._clamp_int(data.get('lines', 0), 0, 999999, 'opponent_lines')
                self.opponent_level = self._clamp_int(data.get('level', 1), 0, 30, 'level')

            elif msg_type == MsgType.GAME_OVER:
                if self.online_state in (OnlineState.PLAYING, OnlineState.GAME_OVER):
                    self._mark_opponent_eliminated(
                        score=self._clamp_int(data.get('score', self.opponent_score), 0, 999999, 'opp_final_score'),
                        lines=self._clamp_int(data.get('lines', self.opponent_lines), 0, 999999, 'opp_final_lines'),
                        board_filled=bool(self._clamp_int(data.get('board_filled', 1), 0, 1, 'opp_board_filled')),
                    )

            elif msg_type == MsgType.ELIMINATED:
                if self.online_state in (OnlineState.PLAYING, OnlineState.GAME_OVER):
                    self._mark_opponent_eliminated()

            elif msg_type == MsgType.PAUSE_REQUEST:
                self.opponent_paused = True
                self._freeze_active_gameplay_input()

            elif msg_type == MsgType.RESUME:
                self.opponent_paused = False
                self._freeze_active_gameplay_input()

            elif msg_type == MsgType.REMATCH:
                # Rakip rematch istiyor
                self.opponent_ready = False
                self.my_ready = False
                self._ready_resend_timer = 0.0
                self._reset_match_result_state()
                self.online_state = OnlineState.READY_CHECK
                self._status_msg = t('opponent_wants_rematch', 'Rakip tekrar oynamak istiyor!')
                self._status_timer = 3.0

    def _check_both_ready(self):
        """İki oyuncu da hazırsa oyun başlamayı tetikle."""
        if self.my_ready and self.opponent_ready:
            if self.net.is_host:
                # Host başlama sinyalini hazırlar ve gönderir.
                pending_payload = getattr(self, '_game_start_pending_payload', None)
                if not pending_payload:
                    self.game_seed = random.randint(1, 999999)
                    self._generate_pieces(self.game_seed, 200)
                    self._game_start_pending_payload = (self.game_seed, self.piece_sequence[:200])
                    self._game_start_retry_timer = 0.0
                    pending_payload = self._game_start_pending_payload

                if float(getattr(self, '_game_start_retry_timer', 0.0)) <= 0:
                    seed, pieces = pending_payload
                    start_ok = bool(self.net.send_game_start(seed, pieces))
                    if start_ok:
                        self._game_start_pending_payload = None
                        self._game_start_retry_timer = 0.0
                        self._start_countdown()
                    else:
                        self._game_start_retry_timer = self._GAME_START_RETRY_INTERVAL_MS
                        print("[OnlinePvP] GAME_START gonderilemedi (host), retry planlandi.")

    def _freeze_active_gameplay_input(self):
        """Pause geçişlerinde aktif gameplay input durumlarını temizle."""
        self.soft_dropping = False
        self.das_direction = 0
        self.das_timer = 0
        self.das_active = False

    # ============================================================
    #  OYUN BAŞLATMA
    # ============================================================

    def _generate_pieces(self, seed: int, count: int):
        """Deterministik parça dizisi oluştur."""
        rng = random.Random(seed)
        self.piece_sequence = []
        total = len(SHAPES)
        bag_copies = 3
        generated = 0
        while generated < count:
            bag = list(range(total)) * bag_copies
            rng.shuffle(bag)
            for idx in bag:
                self.piece_sequence.append(idx)
                generated += 1
                if generated >= count:
                    break
        self.piece_index = 0

    def _start_countdown(self):
        """3-2-1 geri sayım başlat."""
        self.online_state = OnlineState.COUNTDOWN
        self.countdown_value = 3
        self.countdown_timer = 0
        # Menü müziğini geri sayım başlayınca durdur
        try:
            self.sound.stop_music()
        except Exception:
            pass

    def _start_game(self):
        """Oyunu fiilen başlat."""
        self.online_state = OnlineState.PLAYING
        self.my_board = Board()
        self.opponent_board = Board()
        self.piece_index = 0
        # Geri sayım sırasında müzik durdurulmuştu — oyun başlayınca yeniden başlat
        self._start_pvp_music()

        if not self.piece_sequence:
            self._generate_pieces(self.game_seed, 200)

        self.my_piece = self._get_next_piece()
        skip_hidden_rows(self.my_piece, self.my_board)
        self.my_next_piece = self._get_next_piece()
        self.next_piece = self.my_next_piece  # side panel referansı
        self.hold_piece = None
        self.hold_used = False
        self.hold_shape_index = -1
        self.fall_timer = 0
        self.lock_timer = 0
        self._reset_match_result_state()
        self.pending_garbage = 0
        self._garbage_gap = 0
        self._pending_disconnect_steam_id = 0
        self._disconnect_grace_timer = 0.0
        self.state_snapshot_timer = 0
        self.soft_dropping = False
        self.paused = False
        self.opponent_paused = False
        self.das_direction = 0
        self.das_timer = 0
        self.das_active = False
        self.opponent_grid_snapshot = None
        self.opponent_score = 0
        self.opponent_lines = 0
        self.opponent_level = 1
        self._opponent_lines_prev = 0
        self.opponent_piece_data = None
        self._opponent_piece_visual = None
        self._opponent_piece_seq = 0
        self._my_piece_seq = 0
        self._opponent_board_seq = -1
        self._my_board_seq = 0
        self._opponent_clear_event_seq = -1
        self._my_clear_event_seq = 0
        self._opponent_piece_render_cache_key = None
        self._opponent_piece_render_cache = None
        self._last_sent_piece_signature = None
        self._pending_piece_position_dirty = False
        self._piece_position_send_timer = float(self._PIECE_POSITION_INTERVAL_MS)
        self.my_line_flash_rows = []
        self.my_line_flash_timer = 0
        self.my_line_glow_alpha = 0
        self.my_wave_effects = []
        self.my_line_sweep_rows = []
        self.my_line_sweep_progress = 0.0
        self.my_line_sweep_active = False
        self.my_falling_block_animations = []
        self._line_sweep_draw_error_reported = False
        self.opp_line_flash_rows = []
        self.opp_line_flash_timer = 0
        self.opp_line_glow_alpha = 0
        self.opp_wave_effects = []
        self.opp_line_sweep_rows = []
        self.opp_line_sweep_progress = 0.0
        self.opp_line_sweep_active = False
        self.opp_falling_block_animations = []
        self._pending_opp_particle_rows = []
        self.particles.clear()
        self.drop_trails.clear()
        self.screen_shake = 0.0
        self.shake_intensity = 0
        self._screen_shake_initial = 0.0
        self._send_piece_position(force=True)
        self._send_board_snapshot()

    def _get_next_piece(self) -> Piece:
        """Sıradaki parçayı al."""
        if self.piece_index >= len(self.piece_sequence):
            # Daha fazla parça üret (aynı seed)
            self._generate_pieces(self.game_seed + self.piece_index, 100)
        idx = self.piece_sequence[self.piece_index]
        self.piece_index += 1
        piece = Piece(x=3, y=0, shape_index=idx)
        piece.y = get_piece_spawn_y(piece)
        self._apply_block_style(piece)
        return piece

    def trigger_hard_drop_screen_shake(self) -> None:
        self.trigger_screen_shake(
            intensity=HARD_DROP_SCREEN_SHAKE_INTENSITY,
            duration=HARD_DROP_SCREEN_SHAKE_DURATION_SECONDS,
        )

    def trigger_screen_shake(self, intensity=10, duration=DEFAULT_SCREEN_SHAKE_DURATION_SECONDS):
        """Ekran titremesi efekti başlat (saniye tabanlı)."""
        begin_screen_shake(self, intensity=intensity, duration=duration)

    def update_screen_shake(self, dt_ms: float | None = None):
        """Ekran titremesini güncelle (ms tabanlı)."""
        step_screen_shake(self, dt_ms=dt_ms)

    def get_shake_offset(self) -> tuple[int, int]:
        """Ekran titremesi için offset hesapla."""
        return sample_screen_shake_offset(self)

    def create_particles(self, count, x=None, y=None, colors=None, speed=5):
        """Genel amaçlı parçacık oluşturucu."""
        if not self._particle_effects_enabled():
            return
        if x is None:
            x = random.randint(0, self.window_width)
        if y is None:
            y = random.randint(0, self.window_height // 2)
        if colors is None:
            colors = [(0, 255, 255), (255, 215, 0), (255, 0, 255), (0, 255, 120), (255, 90, 90)]
        for _ in range(max(1, int(count * self._particle_effects_multiplier()))):
            particle = {
                'x': float(x),
                'y': float(y),
                'vx': speed * (random.random() * 2 - 1),
                'vy': speed * (random.random() * 2 - 1),
                'life': random.randint(20, 40),
                'max_life': 40,
                'color': random.choice(colors),
                'size': random.randint(2, 4),
                'glow': True,
            }
            self.particles.append(particle)

    def create_lock_explosion(self, x, y, color, cell_size=25):
        """Ana oyundaki gibi hücre bazlı kilitlenme patlaması oluştur."""
        if not self._particle_effects_enabled():
            return

        base_color = tuple(color[:3]) if color else (128, 128, 128)
        bright_color = tuple(min(255, int(c * 1.3)) for c in base_color)
        dim_color = tuple(max(0, int(c * 0.7)) for c in base_color)
        white_tint = tuple(min(255, c + 80) for c in base_color)
        color_palette = [base_color, bright_color, dim_color, white_tint, (255, 255, 255)]

        particle_count = max(1, int(random.randint(6, 10) * self._particle_effects_multiplier()))
        for i in range(particle_count):
            angle = (i / particle_count) * 2 * math.pi + random.uniform(-0.3, 0.3)
            speed = random.uniform(2, 5)
            self.particles.append({
                'x': float(x + random.uniform(-3, 3)),
                'y': float(y + random.uniform(-3, 3)),
                'vx': math.cos(angle) * speed,
                'vy': math.sin(angle) * speed - 1,
                'life': random.randint(20, 40),
                'max_life': 40,
                'color': random.choice(color_palette),
                'size': random.randint(2, 4),
                'glow': True,
            })

        self.particles.append({
            'x': float(x),
            'y': float(y),
            'vx': 0,
            'vy': -0.5,
            'life': 12,
            'max_life': 12,
            'color': white_tint,
            'size': int(cell_size * 0.4),
            'glow': True,
        })

    def _create_drop_trail(self, piece: Piece | None, board_x: int, board_y: int,
                           cell_size: int, start_y: int, distance: int,
                           trail_type: str = 'hard'):
        """Ana oyundaki gibi sert düşüş izi oluştur."""
        if not self.effects_enabled or not piece or distance <= 0:
            return

        for row_idx, row in enumerate(piece.shape):
            for col_idx, cell in enumerate(row):
                if not cell:
                    continue
                block_x = board_x + (piece.x + col_idx) * cell_size
                block_y = board_y + start_y * cell_size + row_idx * cell_size
                trail_height = distance * cell_size
                if trail_height <= 0:
                    continue

                if trail_type == 'hard':
                    alpha = 180
                    trail_width = cell_size - 4
                    fade_speed = 15
                else:
                    alpha = 80
                    trail_width = max(2, cell_size // 2)
                    fade_speed = 20

                color = tuple(getattr(piece, 'color', (128, 128, 128))[:3])
                bright_color = (
                    min(255, color[0] + 50),
                    min(255, color[1] + 50),
                    min(255, color[2] + 50),
                )
                self.drop_trails.append({
                    'x': block_x + (cell_size - trail_width) // 2,
                    'y': block_y,
                    'width': trail_width,
                    'height': trail_height,
                    'color': bright_color,
                    'alpha': alpha,
                    'fade_speed': fade_speed,
                })

    def _update_drop_trails(self, dt_frames: float):
        """Drop trail efektlerini güncelle."""
        for trail in self.drop_trails:
            trail['alpha'] -= trail['fade_speed'] * dt_frames
        self.drop_trails = [trail for trail in self.drop_trails if trail['alpha'] > 0]

    def _draw_drop_trails(self):
        """Drop trail efektlerini çiz."""
        for trail in self.drop_trails:
            if trail['alpha'] <= 0:
                continue
            trail_surface = pygame.Surface((int(trail['width']), int(trail['height'])), pygame.SRCALPHA)
            segments = max(1, int(trail['height'] // 4))
            segment_height = trail['height'] / segments
            for i in range(segments):
                segment_alpha = int(trail['alpha'] * (1 - i / segments))
                if segment_alpha <= 0:
                    continue
                y_pos = int(i * segment_height)
                height = max(1, int(segment_height + 1))
                color_with_alpha = (*trail['color'], segment_alpha)
                pygame.draw.rect(
                    trail_surface,
                    color_with_alpha,
                    (0, y_pos, int(trail['width']), height),
                    border_radius=max(1, int(trail['width']) // 4),
                )
            self.screen.blit(trail_surface, (int(trail['x']), int(trail['y'])))

    def create_line_clear_particles(self, cleared_rows, board_offset_x, board_offset_y, cell_size, board=None):
        """Satır temizlendiğinde local PvP benzeri güçlü partikül efekti oluştur."""
        if not self._particle_effects_enabled():
            return
        sparkle_colors = [
            (255, 255, 255),
            (255, 255, 200),
            (255, 215, 0),
            (0, 255, 255),
            (255, 100, 255),
        ]
        for row in cleared_rows:
            for col in range(BOARD_WIDTH):
                cell_x = board_offset_x + col * cell_size + cell_size // 2
                cell_y = board_offset_y + row * cell_size + cell_size // 2
                try:
                    if board and hasattr(board, 'last_cleared_colors') and row in board.last_cleared_colors:
                        row_colors = board.last_cleared_colors[row]
                        if col < len(row_colors) and row_colors[col] != BLACK:
                            cell_color = row_colors[col]
                        else:
                            cell_color = random.choice(sparkle_colors)
                    else:
                        cell_color = random.choice(sparkle_colors)
                except Exception:
                    cell_color = random.choice(sparkle_colors)

                for _ in range(max(1, int(random.randint(6, 10) * self._particle_effects_multiplier()))):
                    speed = random.uniform(4, 12)
                    self.particles.append({
                        'x': float(cell_x + random.randint(-3, 3)),
                        'y': float(cell_y + random.randint(-3, 3)),
                        'vx': speed * random.uniform(-1.5, 1.5),
                        'vy': speed * random.uniform(-1, 0.5) - 2,
                        'life': random.randint(40, 80),
                        'max_life': 80,
                        'color': cell_color,
                        'size': random.randint(3, 7),
                        'glow': True,
                    })

                if col % 2 == 0:
                    for _ in range(max(1, int(random.randint(2, 4) * self._particle_effects_multiplier()))):
                        spark_color = random.choice(sparkle_colors)
                        spark_speed = random.uniform(8, 15)
                        self.particles.append({
                            'x': float(cell_x),
                            'y': float(cell_y),
                            'vx': spark_speed * random.uniform(-1, 1),
                            'vy': -spark_speed * random.uniform(0.3, 1) - 5,
                            'life': random.randint(20, 40),
                            'max_life': 40,
                            'color': spark_color,
                            'size': random.randint(2, 4),
                            'glow': True,
                            'spark': True,
                        })

            center_x = board_offset_x + (BOARD_WIDTH * cell_size) // 2
            center_y = board_offset_y + row * cell_size + cell_size // 2
            star_count = max(4, int(16 * self._particle_effects_multiplier()))
            for i in range(star_count):
                angle = (i / star_count) * 2 * math.pi
                star_speed = random.uniform(6, 14)
                self.particles.append({
                    'x': float(center_x),
                    'y': float(center_y),
                    'vx': math.cos(angle) * star_speed,
                    'vy': math.sin(angle) * star_speed - 2,
                    'life': random.randint(30, 60),
                    'max_life': 60,
                    'color': random.choice(sparkle_colors),
                    'size': random.randint(4, 8),
                    'glow': True,
                })

    def update_particles(self, dt_ms: float | None = None):
        """Parçacıkları güncelle."""
        if not self.particles:
            return
        try:
            dt = float(dt_ms) if dt_ms is not None else float(getattr(self, '_last_dt_ms', 16.666))
        except Exception:
            dt = 16.666
        dt = max(0.0, min(100.0, dt))
        dt_frames = dt / 16.666

        alive = []
        for particle in self.particles:
            particle['x'] += particle.get('vx', 0) * dt_frames
            particle['y'] += particle.get('vy', 0) * dt_frames
            particle['vy'] += 0.5 * dt_frames
            particle['vx'] *= 0.98 ** dt_frames
            particle['life'] = float(particle.get('life', 0)) - dt_frames
            if particle['life'] > 0:
                alive.append(particle)
        self.particles = alive

    def create_ambient_particles(self):
        """Arka plan için ambient parçacıklar oluştur."""
        if not self._particle_effects_enabled():
            return
        self.ambient_particles.clear()
        for _ in range(max(10, int(random.randint(50, 100) * self._particle_effects_multiplier()))):
            self.ambient_particles.append({
                'x': random.uniform(0, self.window_width),
                'y': random.uniform(0, self.window_height),
                'vx': random.uniform(-0.5, 0.5),
                'vy': random.uniform(0.2, 0.8),
                'size': random.randint(1, 3),
                'alpha': random.randint(50, 150),
                'pulse': random.uniform(0, 6.28),
                'pulse_speed': random.uniform(0.02, 0.05),
            })

    def update_ambient_particles(self, dt_ms: float | None = None):
        """Ambient parçacıkları güncelle."""
        try:
            dt = float(dt_ms) if dt_ms is not None else float(getattr(self, '_last_dt_ms', 16.666))
        except Exception:
            dt = 16.666
        dt = max(0.0, min(100.0, dt))
        dt_frames = dt / 16.666

        for particle in self.ambient_particles:
            particle['x'] += particle['vx'] * dt_frames
            particle['y'] += particle['vy'] * dt_frames
            particle['pulse'] += particle['pulse_speed'] * dt_frames
            if particle['y'] > self.window_height:
                particle['y'] = -10
                particle['x'] = random.uniform(0, self.window_width)
            if particle['x'] < -10:
                particle['x'] = self.window_width + 10
            elif particle['x'] > self.window_width + 10:
                particle['x'] = -10

    def draw_ambient_particles(self):
        """Ambient parçacıkları çiz."""
        for particle in self.ambient_particles:
            pulse_alpha = int(particle['alpha'] + math.sin(particle['pulse']) * 30)
            pulse_alpha = max(30, min(180, pulse_alpha))
            color = (200, 200, 255)
            pos = (int(particle['x']), int(particle['y']))
            size = particle['size']
            if size > 1:
                glow_surface = self._effect_surface_cache.get_circle_surface(size * 2, (*color, pulse_alpha // 3))
                self.screen.blit(glow_surface, (pos[0] - size * 2, pos[1] - size * 2))
            particle_surface = self._effect_surface_cache.get_circle_surface(size, (*color, pulse_alpha))
            self.screen.blit(particle_surface, (pos[0] - size, pos[1] - size))

    def draw_particles(self):
        """Parçacıkları çiz."""
        for particle in self.particles:
            alpha_ratio = particle['life'] / particle['max_life']
            alpha = int(255 * alpha_ratio)
            size = max(1, int(particle['size'] * alpha_ratio))
            color = particle['color']
            pos = (int(particle['x']), int(particle['y']))
            if particle.get('glow', False) and size > 2:
                halo_size = size + 4
                halo_color = tuple(min(255, int(c * 0.6)) for c in color[:3])
                halo_surface = self._effect_surface_cache.get_circle_surface(halo_size, (*halo_color, int(alpha * 0.3)))
                self.screen.blit(halo_surface, (pos[0] - halo_size, pos[1] - halo_size))

                mid_size = size + 2
                mid_color = tuple(min(255, int(c * 0.8)) for c in color[:3])
                mid_surface = self._effect_surface_cache.get_circle_surface(mid_size, (*mid_color, int(alpha * 0.5)))
                self.screen.blit(mid_surface, (pos[0] - mid_size, pos[1] - mid_size))

            pygame.draw.circle(self.screen, color, pos, size)
            if size > 2:
                inner_size = max(1, size - 1)
                inner_color = tuple(min(255, c + 80) for c in color[:3])
                pygame.draw.circle(self.screen, inner_color, pos, inner_size)
                if size > 3:
                    core_color = tuple(min(255, c + 120) for c in color[:3])
                    pygame.draw.circle(self.screen, core_color, pos, 1)

    def _trigger_line_clear_feedback(self, rows, board_x, board_y, cell_size, board, is_opponent=False):
        """Satır temizleme flash, wave, particle ve shake efektlerini tetikle."""
        if not rows or not self.effects_enabled:
            return
        if is_opponent:
            self.opp_line_flash_rows = list(rows)
            self.opp_line_flash_timer = 20
            self.opp_line_glow_alpha = 255
            wave_list = self.opp_wave_effects
            self.opp_line_sweep_rows = list(rows)
            self.opp_line_sweep_progress = 0.0
            self.opp_line_sweep_active = True
        else:
            self.my_line_flash_rows = list(rows)
            self.my_line_flash_timer = 20
            self.my_line_glow_alpha = 255
            wave_list = self.my_wave_effects
            self.my_line_sweep_rows = list(rows)
            self.my_line_sweep_progress = 0.0
            self.my_line_sweep_active = True

        self.create_line_clear_particles(rows, board_x, board_y, cell_size, board=board)
        if is_opponent:
            if self.opponent_grid_snapshot:
                self._start_block_fall_animation(rows, cell_size, snapshot_grid=self.opponent_grid_snapshot, is_opponent=True)
        else:
            self._start_block_fall_animation(rows, cell_size, board=board, is_opponent=False)
        for row in rows:
            wave_list.append({
                'x': board_x + (BOARD_WIDTH * cell_size) // 2,
                'y': board_y + row * cell_size + cell_size // 2,
                'radius': 0,
                'max_radius': BOARD_WIDTH * cell_size,
                'alpha': 200,
                'color': (255, 255, 255),
                'speed': 15,
            })

        lines = len(rows)

        # Gamepad titreşimi - satır temizleme
        if not is_opponent:
            try:
                from gamepad_manager import get_gamepad_manager
                if lines >= 4:
                    get_gamepad_manager().rumble(0.8, 1.0, 400)
                elif lines >= 2:
                    get_gamepad_manager().rumble(0.4, 0.5, 200)
            except Exception:
                pass

        if lines < 4:
            self.trigger_screen_shake(intensity=3 + lines * 2, duration=8 / 60.0)
            # Multi-line parçacık efekti (2-3 satır)
            if lines >= 2:
                center_x = board_x + (BOARD_WIDTH * cell_size) // 2
                center_y = board_y + (BOARD_HEIGHT * cell_size) // 2
                self.create_particles(50 * lines, center_x, center_y,
                                      [(0, 255, 255), (100, 200, 255), (150, 220, 255)], speed=6)
        else:
            center_x = board_x + (BOARD_WIDTH * cell_size) // 2
            center_y = board_y + (BOARD_HEIGHT * cell_size) // 2
            extra_colors = [(255, 215, 0), (255, 165, 0), (255, 255, 255), (0, 255, 255)]
            self.create_particles(150, center_x, center_y, extra_colors, speed=10)
            self.trigger_screen_shake(intensity=15, duration=20 / 60.0)

    def _reset_line_clear_feedback_state(self, is_opponent: bool = False) -> None:
        if is_opponent:
            self.opp_line_flash_rows = []
            self.opp_line_flash_timer = 0
            self.opp_line_glow_alpha = 0
            self.opp_wave_effects = []
            self.opp_line_sweep_rows = []
            self.opp_line_sweep_progress = 0.0
            self.opp_line_sweep_active = False
            self.opp_falling_block_animations = []
        else:
            self.my_line_flash_rows = []
            self.my_line_flash_timer = 0
            self.my_line_glow_alpha = 0
            self.my_wave_effects = []
            self.my_line_sweep_rows = []
            self.my_line_sweep_progress = 0.0
            self.my_line_sweep_active = False
            self.my_falling_block_animations = []

    def _safe_trigger_line_clear_feedback(self, rows, board_x, board_y, cell_size, board, is_opponent=False):
        try:
            self._trigger_line_clear_feedback(rows, board_x, board_y, cell_size, board, is_opponent=is_opponent)
        except Exception as exc:
            side = 'opponent' if is_opponent else 'local'
            print(f"[OnlinePvP] line clear feedback hatasi ({side}) atlandi: {exc}")
            self._reset_line_clear_feedback_state(is_opponent=is_opponent)

    def _safe_draw_rainbow_cat_sweep(self, board_group_rect, sweep_x, sweep_width, phase, is_opponent=False):
        try:
            draw_rainbow_cat_sweep(
                self.screen,
                self._sweep_cat_state,
                board_group_rect,
                sweep_x,
                sweep_width,
                phase,
                BOARD_WIDTH,
            )
            return True
        except Exception as exc:
            side = 'opponent' if is_opponent else 'local'
            if not getattr(self, '_line_sweep_draw_error_reported', False):
                print(f"[OnlinePvP] line sweep draw hatasi ({side}) atlandi: {exc}")
                self._line_sweep_draw_error_reported = True
            self._reset_line_clear_feedback_state(is_opponent=is_opponent)
            return False

    # ============================================================
    #  ÇÖP SATIR MEKANİĞİ
    # ============================================================

    def _send_garbage(self, lines_cleared: int):
        """Satır temizlediğimizde rakibe çöp gönder."""
        if not ONLINE_PVP_GARBAGE_ENABLED:
            return

        garbage_table = {
            1: 0,
            2: 1,
            3: 2,
            4: 4,
        }
        garbage_lines = garbage_table.get(lines_cleared, 0)
        if garbage_lines > 0:
            gap_col = random.randint(0, BOARD_WIDTH - 1)
            self.net.send_garbage(garbage_lines, gap_col)

    def _receive_garbage(self, lines: int, gap_col: int = -1):
        """Rakipten gelen çöp satırları kuyruğa al — parça kilitlenince uygulanır."""
        if not ONLINE_PVP_GARBAGE_ENABLED:
            self.pending_garbage = 0
            self._garbage_gap = 0
            return
        if lines <= 0:
            return
        if gap_col < 0:
            gap_col = random.randint(0, BOARD_WIDTH - 1)

        self.pending_garbage += lines
        self._garbage_gap = gap_col  # Son gap sütunu (uygulamada kullanılacak)

    def _apply_pending_garbage(self):
        """Kuyrukta bekleyen çöp satırları tahtaya uygula."""
        if not ONLINE_PVP_GARBAGE_ENABLED:
            self.pending_garbage = 0
            self._garbage_gap = 0
            return
        if self.pending_garbage <= 0 or not self.my_board:
            return

        gap_col = getattr(self, '_garbage_gap', random.randint(0, BOARD_WIDTH - 1))
        lines = self.pending_garbage

        for _ in range(lines):
            # Üst satırı kaldır
            self.my_board.grid.pop(0)
            self.my_board.occupancy.pop(0)
            self.my_board.texture_grid.pop(0)
            self.my_board.owners.pop(0)
            self.my_board.gold.pop(0)
            # Yeni çöp satır ekle (gap hariç dolu)
            garbage_color = (128, 128, 128)
            new_row = [garbage_color if x != gap_col else BLACK
                       for x in range(BOARD_WIDTH)]
            new_occ = [x != gap_col for x in range(BOARD_WIDTH)]
            self.my_board.grid.append(new_row)
            self.my_board.occupancy.append(new_occ)
            self.my_board.texture_grid.append([None] * BOARD_WIDTH)
            self.my_board.owners.append([None] * BOARD_WIDTH)
            self.my_board.gold.append([False] * BOARD_WIDTH)

        self.pending_garbage = 0
        self._garbage_gap = 0

        # Garbage sonrası aktif parça geçerli pozisyonda mı kontrol et
        # Tahta yukarı kayınca parça var olan bloklarla çakışabilir
        if self.my_piece:
            if not self.my_board.is_valid_position(self.my_piece):
                # Parçayı yukarı kaydırmayı dene
                saved = False
                for offset in range(1, lines + 3):
                    self.my_piece.y -= 1
                    if self.my_piece.y < -2:
                        break
                    if self.my_board.is_valid_position(self.my_piece):
                        saved = True
                        break
                if not saved:
                    # Parça kurtarılamadı — Local PvP ile aynı elenme mantığı
                    self._mark_local_eliminated()

    def _update_opponent_display(self, data: dict):
        """Rakip tahta snapshot'ını güncelle."""
        try:
            snapshot_seq = int(data.get('seq', -1))
        except (TypeError, ValueError):
            snapshot_seq = -1
        if snapshot_seq >= 0 and snapshot_seq < self._opponent_board_seq:
            return
        if snapshot_seq >= 0:
            self._opponent_board_seq = snapshot_seq

        grid = data.get('grid')
        if grid:
            self.opponent_grid_snapshot = grid
        self.opponent_score = data.get('score', self.opponent_score)
        new_lines = data.get('lines', self.opponent_lines)
        try:
            new_lines = int(new_lines)
        except (TypeError, ValueError):
            new_lines = self.opponent_lines
        clear_rows = data.get('clear_rows')
        try:
            clear_event_seq = int(data.get('clear_event_seq', -1))
        except (TypeError, ValueError):
            clear_event_seq = -1
        if (
            isinstance(clear_rows, list)
            and clear_rows
            and clear_event_seq > self._opponent_clear_event_seq
        ):
            effect_rows = []
            for row in clear_rows:
                try:
                    row_i = int(row)
                except (TypeError, ValueError):
                    continue
                if 0 <= row_i < BOARD_HEIGHT:
                    effect_rows.append(row_i)
            if effect_rows:
                self._opponent_clear_event_seq = clear_event_seq
                self._pending_opp_particle_rows = list(effect_rows)
        self.opponent_lines = new_lines
        self._opponent_lines_prev = new_lines
        self.opponent_level = data.get('level', self.opponent_level)
        # Board snapshot'tan gelen aktif parça bilgisi (fallback sync)
        piece = data.get('piece')
        if piece:
            try:
                piece_seq = int(data.get('piece_seq', -1))
            except (TypeError, ValueError):
                piece_seq = -1
            if self._normalize_opponent_piece_payload(piece) is None:
                print("[OnlinePvP] BOARD_STATE: gecersiz snapshot parca payload'u - ignore.")
            elif piece_seq >= 0:
                if piece_seq >= self._opponent_piece_seq:
                    if self._set_opponent_piece_state(piece, from_snapshot=True):
                        self._opponent_piece_seq = piece_seq
            elif getattr(self, 'opponent_piece_data', None) is None:
                self._set_opponent_piece_state(piece, from_snapshot=True)

    def _normalize_opponent_piece_payload(self, piece_data: dict | None) -> dict | None:
        if not isinstance(piece_data, dict):
            return None
        try:
            si = int(piece_data.get('si', -1))
            x = float(piece_data.get('x', 0) or 0)
            y = float(piece_data.get('y', 0) or 0)
            rotation = int(piece_data.get('r', 0)) % 4
        except (TypeError, ValueError):
            return None
        if not (0 <= si < len(SHAPES)):
            return None
        return {
            'si': si,
            'x': x,
            'y': y,
            'r': rotation,
        }

    def _clear_opponent_piece_state(self) -> None:
        self.opponent_piece_data = None
        self._opponent_piece_visual = None
        self._opponent_piece_render_cache_key = None
        self._opponent_piece_render_cache = None

    def _set_opponent_piece_state(self, piece_data: dict | None, from_snapshot: bool = False) -> bool:
        normalized = self._normalize_opponent_piece_payload(piece_data)
        if normalized is None:
            self._clear_opponent_piece_state()
            return False

        int_state = {
            'si': int(normalized['si']),
            'x': int(round(normalized['x'])),
            'y': int(round(normalized['y'])),
            'r': int(normalized['r']),
        }
        self.opponent_piece_data = int_state

        snap_x = float(int_state['x'])
        snap_y = float(int_state['y'])
        self._opponent_piece_visual = {
            'si': int_state['si'],
            'r': int_state['r'],
            'draw_x': snap_x,
            'draw_y': snap_y,
            'target_x': snap_x,
            'target_y': snap_y,
        }
        return True

    def _get_opponent_piece_draw_state(self) -> dict | None:
        visual = getattr(self, '_opponent_piece_visual', None)
        if isinstance(visual, dict):
            try:
                si = int(visual.get('si', -1))
            except (TypeError, ValueError):
                si = -1
            return {
                'si': si,
                'x': float(visual.get('draw_x', visual.get('target_x', 0.0)) or 0.0),
                'y': float(visual.get('draw_y', visual.get('target_y', 0.0)) or 0.0),
                'r': int(visual.get('r', 0) or 0) % 4,
            }
        normalized = self._normalize_opponent_piece_payload(getattr(self, 'opponent_piece_data', None))
        if normalized is None:
            return None
        return normalized

    def _get_cached_opponent_piece_render(self, shape_index: int, rotation: int) -> dict | None:
        cache_key = (int(shape_index), int(rotation) % 4)
        if getattr(self, '_opponent_piece_render_cache_key', None) != cache_key:
            if not (0 <= cache_key[0] < len(SHAPES)):
                return None
            temp = Piece(x=0, y=0, shape_index=cache_key[0])
            self._apply_block_style(temp)
            for _ in range(cache_key[1]):
                temp.rotate(1)
            shape = temp.get_shape()
            self._opponent_piece_render_cache_key = cache_key
            self._opponent_piece_render_cache = {
                'piece': temp,
                'shape': shape,
                'texture': getattr(temp, 'texture_surface', None),
                'color_matrix': getattr(temp, 'color_matrix', None),
                'height': len(shape),
                'width': len(shape[0]) if shape else 1,
            }
        return getattr(self, '_opponent_piece_render_cache', None)

    # ============================================================
    #  HOLD (SAKLAMA) MEKANİĞİ
    # ============================================================

    def _do_hold(self):
        """Aktif parçayı sakla, saklı parçayı aktif yap."""
        if self.hold_used or not self.my_piece or not self.my_board:
            return  # Bu turda zaten hold kullanıldı

        current_shape_index = self.my_piece.shape_index

        if self.hold_shape_index < 0:
            # İlk hold — saklı parça yok, sıradakini al
            self.hold_shape_index = current_shape_index
            self.hold_piece = Piece(x=0, y=0, shape_index=current_shape_index)
            self._apply_block_style(self.hold_piece)
            self.my_piece = self.my_next_piece
            self.my_next_piece = self._get_next_piece()
            self.next_piece = self.my_next_piece
        else:
            # Swap
            old_hold = self.hold_shape_index
            self.hold_shape_index = current_shape_index
            self.hold_piece = Piece(x=0, y=0, shape_index=current_shape_index)
            self._apply_block_style(self.hold_piece)
            self.my_piece = Piece(x=3, y=0, shape_index=old_hold)
            self.my_piece.y = get_piece_spawn_y(self.my_piece)
            self._apply_block_style(self.my_piece)

        self.hold_used = True
        self.lock_timer = 0
        try:
            self.sound.play('hold')
        except Exception:
            pass

        # Instantly drop through hidden rows, then validate
        skip_hidden_rows(self.my_piece, self.my_board)

        # Hold sonrası parça geçerli pozisyonda mı kontrol et
        if not self.my_board.is_valid_position(self.my_piece):
            # Yukarı kaydır — spawn Y'den daha negatife git
            spawn_y = self.my_piece.y
            for offset in range(1, 4):
                self.my_piece.y = spawn_y - offset
                if self.my_board.is_valid_position(self.my_piece):
                    break

        # Pozisyon düzeltmesinden SONRA gönder
        self._send_piece_position(force=True)

    # ============================================================
    #  GHOST PIECE (HAYALET PARÇA)
    # ============================================================

    def _get_ghost_y(self) -> int:
        """Parçanın düşeceği en alt y koordinatını hesapla."""
        if not self.my_board or not self.my_piece:
            return 0
        ghost_y = self.my_piece.y
        while self.my_board.is_valid_position(self.my_piece, dy=ghost_y - self.my_piece.y + 1):
            ghost_y += 1
        return ghost_y

    def _send_board_snapshot(self, clear_rows: list[int] | None = None):
        """Kendi tahta durumunu rakibe gönder."""
        if not self.my_board:
            return
        self._my_board_seq += 1
        # Grid'i kompakt formata çevir (sadece dolu hücreler)
        compact_grid = []
        for y in range(BOARD_HEIGHT):
            row = []
            for x in range(BOARD_WIDTH):
                if self.my_board.occupancy[y][x]:
                    c = self.my_board.grid[y][x]
                    row.append([c[0], c[1], c[2]])
                else:
                    row.append(None)
            compact_grid.append(row)

        data = {
            'seq': self._my_board_seq,
            'grid': compact_grid,
            'score': self.my_board.score,
            'lines': self.my_board.lines_cleared,
            'level': self.my_board.level,
        }

        if clear_rows:
            self._my_clear_event_seq += 1
            sanitized_rows = []
            for row in clear_rows:
                try:
                    row_i = int(row)
                except (TypeError, ValueError):
                    continue
                if 0 <= row_i < BOARD_HEIGHT:
                    sanitized_rows.append(row_i)
            data['clear_rows'] = sanitized_rows
            data['clear_event_seq'] = self._my_clear_event_seq

        # Aktif parça bilgisini de ekle (fallback sync noktası)
        if self.my_piece:
            data['piece'] = {
                'si': self.my_piece.shape_index,
                'x': self.my_piece.x,
                'y': self.my_piece.y,
                'r': self.my_piece.rotation_state,
            }
            data['piece_seq'] = int(getattr(self, '_my_piece_seq', 0) or 0)

        self.net.send_board_state(data)

    def _send_piece_position(self, force: bool = False):
        """Aktif parçanın pozisyonunu coalescing ile rakibe gönder."""
        return self._flush_piece_position(force=force)

    def _current_piece_network_signature(self) -> tuple | None:
        piece = getattr(self, 'my_piece', None)
        if not piece:
            return None
        try:
            shape_index = int(getattr(piece, 'shape_index', -1))
        except (TypeError, ValueError):
            shape_index = -1
        return (
            shape_index,
            int(getattr(piece, 'x', 0) or 0),
            int(getattr(piece, 'y', 0) or 0),
            int(getattr(piece, 'rotation_state', 0) or 0),
        )

    def _flush_piece_position(self, force: bool = False) -> bool:
        signature = self._current_piece_network_signature()
        if signature is None or not self._net_initialized:
            return False
        if not force:
            if signature == getattr(self, '_last_sent_piece_signature', None):
                self._pending_piece_position_dirty = False
                return False
            interval_ms = max(1.0, float(getattr(self, '_PIECE_POSITION_INTERVAL_MS', 33.0) or 33.0))
            if getattr(self, '_last_sent_piece_signature', None) is not None:
                if float(getattr(self, '_piece_position_send_timer', 0.0) or 0.0) < interval_ms:
                    self._pending_piece_position_dirty = True
                    return False
        self._my_piece_seq += 1
        self.net.send_piece_position(
            signature[0],
            signature[1],
            signature[2],
            signature[3],
            self._my_piece_seq,
        )
        self._last_sent_piece_signature = signature
        self._pending_piece_position_dirty = False
        self._piece_position_send_timer = 0.0
        return True

    # ============================================================
    #  OYUN GÜNCELLEMESİ
    # ============================================================

    def update(self, delta_time: int):
        """Her frame çağrılır."""
        self._last_dt_ms = delta_time

        # Online PvP ekranına girildiğinde Steam'e otomatik bağlan.
        # İlk deneme geçici olarak başarısız olursa kısa aralıklarla tekrar dene.
        if not self._net_initialized:
            if self._auto_connect_retry_timer > 0:
                self._auto_connect_retry_timer = max(0.0, self._auto_connect_retry_timer - float(delta_time))
            if not self._auto_connect_attempted or self._auto_connect_retry_timer <= 0:
                self._auto_connect_attempted = True
                if not self._init_networking():
                    self._auto_connect_retry_timer = 2000.0

        # Lobi menüsüne gelince önce bir kez, sonra da her 10 saniyede bir seçili filtreyi yenile.
        if (
            self.online_state == OnlineState.LOBBY_MENU
            and self._net_initialized
            and not self._auto_lobby_refresh_requested
        ):
            if self._request_lobby_list():
                self._auto_lobby_refresh_requested = True
        elif (
            self.online_state == OnlineState.LOBBY_MENU
            and self._net_initialized
            and self._auto_lobby_refresh_requested
            and not self._lobby_list_fetching
            and not self._searching_by_code
        ):
            self._auto_lobby_refresh_timer = max(0.0, self._auto_lobby_refresh_timer - float(delta_time))
            if self._auto_lobby_refresh_timer <= 0:
                self._request_lobby_list()

        # Lobby list fetching timeout — eğer 8+ saniye boyunca callback
        # gelmezse (lobby_list_complete veya lobby_list_failed kaybolmuş),
        # _lobby_list_fetching'i sıfırla. Aksi halde UI sonsuza kadar
        # "Aranıyor..." durumunda takılır.
        if (
            self._lobby_list_fetching
            and self._lobby_list_fetch_start_time > 0
            and (time.time() - self._lobby_list_fetch_start_time) > 8.0
        ):
            print("[OnlinePvP] Lobi listesi fetch timeout (8s) — sıfırlanıyor")
            self._lobby_list_fetching = False
            if self._searching_by_code:
                self._searching_by_code = False
                self._code_search_fail_or_retry()
            elif not self._lobby_list:
                self._lobby_list = self._pending_lobby_list[:]
                self._pending_lobby_list.clear()
            self._lobby_list_fetch_start_time = 0

        # Kod araması retry zamanlayıcısı — sadece LOBBY_MENU'deyken çalışır
        if (
            self.online_state == OnlineState.LOBBY_MENU
            and self._code_search_retry_timer > 0
            and self._code_search_retry_code
        ):
            self._code_search_retry_timer = max(0.0, self._code_search_retry_timer - float(delta_time))
            if self._code_search_retry_timer <= 0:
                code = self._code_search_retry_code
                use_full_scan = bool(self._code_search_retry_use_full_scan)
                self._code_search_retry_code = ''
                self._code_search_retry_use_full_scan = False
                if self._net_initialized and code:
                    self._begin_code_search(code, fallback_scan=use_full_scan)
                    print(f"[OnlinePvP] Kod araması retry tetiklendi (full_scan={use_full_scan})")

        # Steam callback'leri işle
        if self._net_initialized:
            self.net.tick()
            self._process_messages()

        _has_unknown_lobbies = (
            bool(self._deferred_lobby_entries)
            or any(
                str(l.get('visibility', '') or '').lower() in ('unknown', 'stale_unknown')
                for l in getattr(self, '_lobby_list', [])
            )
        )
        if (
            self.online_state == OnlineState.LOBBY_MENU
            and self._net_initialized
            and _has_unknown_lobbies
        ):
            self._deferred_lobby_refresh_timer = max(
                0.0,
                float(getattr(self, '_deferred_lobby_refresh_timer', 0.0)) - float(delta_time),
            )
            if self._deferred_lobby_refresh_timer <= 0.0:
                self._refresh_deferred_lobby_entries()
                self._refresh_unknown_lobby_entries()
                # Unknown lobiler çözülmezse stale_unknown olarak işaretle.
                # UI bu durumda private/public varsaymaz; join isteği önce
                # metadata'yı yeniden doğrular ve ancak sonra public/private
                # akışını açar.
                _now = time.time()
                _UNKNOWN_LOBBY_JOINABLE_TIMEOUT_S = 2.0
                _UNKNOWN_LOBBY_REMOVE_TIMEOUT_S = 120.0
                _stale_ids: set[int] = set()
                for _lobby in getattr(self, '_lobby_list', []):
                    _lvis = str(_lobby.get('visibility', '') or '').lower()
                    if _lvis not in ('unknown', 'stale_unknown'):
                        continue
                    _found_t = float(_lobby.get('found_time', 0) or 0)
                    if not _found_t:
                        continue
                    _elapsed = _now - _found_t
                    _lid = int(_lobby.get('id', 0) or 0)
                    if _elapsed > _UNKNOWN_LOBBY_REMOVE_TIMEOUT_S:
                        # 2 dakikadan uzun süredir çözülemedi → kaldır
                        _stale_ids.add(_lid)
                    elif _lvis == 'unknown' and _elapsed > _UNKNOWN_LOBBY_JOINABLE_TIMEOUT_S:
                        # Metadata gecikmesi uzadı — kartı stale_unknown yap,
                        # böylece kullanıcı aksiyonuna rağmen private/public
                        # varsayımı yapılmasın.
                        _lobby['visibility'] = 'stale_unknown'
                if _stale_ids:
                    self._lobby_list = [
                        l for l in self._lobby_list
                        if int(l.get('id', 0) or 0) not in _stale_ids
                    ]
                    for _sid in _stale_ids:
                        self._deferred_lobby_entries.pop(_sid, None)
                        self._clear_lobby_metadata_refresh_request(_sid)
                    print(f"[OnlinePvP] {len(_stale_ids)} stale unknown lobi kaldırıldı")
                self._deferred_lobby_refresh_timer = self._DEFERRED_LOBBY_REFRESH_INTERVAL_MS

        # ── Ertelenmiş erişim yeniden-doğrulama timeout'u ──
        # _validate_joined_lobby_access metadata unknown iken geçici izin
        # vermiş olabilir. Cross-platform'da OnLobbyDataUpdate callback'i
        # gelmeyebilir. 3 saniye sonra metadata'yı tekrar oku; 5 saniye
        # sonra hala unknown ise otomatik kabul et (kullanıcı bilinçli katıldı).
        _pending_reval = int(
            getattr(self, '_pending_access_revalidation_lobby_id', 0) or 0)
        if (
            _pending_reval
            and self._net_initialized
            and self.online_state == OnlineState.WAITING
        ):
            _reval_start = float(
                getattr(self, '_pending_revalidation_start_time', 0) or 0)
            _reval_elapsed = time.time() - _reval_start if _reval_start else 0.0
            # Saniyede en fazla bir kez kontrol et (her frame değil)
            _reval_last_check = float(
                getattr(self, '_pending_reval_last_check_time', 0) or 0)
            _reval_check_due = (time.time() - _reval_last_check) >= 1.0
            if _reval_elapsed > 3.0 and _reval_check_due:
                self._pending_reval_last_check_time = time.time()
                # Metadata'yı tekrar iste ve live-read dene
                try:
                    self.net.request_lobby_data(_pending_reval)
                except Exception:
                    pass
                _snap = self._get_lobby_metadata_snapshot(
                    _pending_reval, prefer_live=True)
                if _snap.get('visibility') not in (None, '', 'unknown'):
                    # Metadata geldi — normal validasyona devam et
                    self._pending_access_revalidation_lobby_id = 0
                    self._pending_revalidation_start_time = 0.0
                    self._validate_joined_lobby_access()
                elif _reval_elapsed > 5.0:
                    # 5 saniye doldu, metadata hala unknown.
                    # Kod yetkilendirmesi varsa kabul et (kullanıcı kodu
                    # biliyordu ama metadata doğrulama yapılamadı).
                    # Yetkilendirme yoksa güvenli tarafta kal — reddet.
                    _has_code_auth = (
                        self._authorized_private_join_lobby_id == _pending_reval
                        and bool(self._authorized_private_join_code)
                    )
                    if _has_code_auth:
                        print("[OnlinePvP] Pending revalidation timeout (5s) — "
                              f"kod yetkilendirmesi var, kabul: lobby={_pending_reval}")
                        self._pending_access_revalidation_lobby_id = 0
                        self._pending_revalidation_start_time = 0.0
                        self._clear_private_join_authorization(_pending_reval)
                        self._lobby_access_validated_id = _pending_reval
                    else:
                        print("[OnlinePvP] Pending revalidation timeout (5s) — "
                              f"yetkilendirme yok, red: lobby={_pending_reval}")
                        self._pending_access_revalidation_lobby_id = 0
                        self._pending_revalidation_start_time = 0.0
                        self._reject_private_lobby_join()

        if self._net_initialized and self.online_state in (OnlineState.WAITING, OnlineState.READY_CHECK):
            self._lobby_presence_probe_timer = max(
                0.0,
                float(getattr(self, '_lobby_presence_probe_timer', 0.0)) - float(delta_time),
            )
            if self._lobby_presence_probe_timer <= 0.0:
                self._sync_lobby_presence_from_members()
                self._lobby_presence_probe_timer = self._LOBBY_PRESENCE_PROBE_INTERVAL_MS

        if (
            self.online_state == OnlineState.PLAYING
            and int(getattr(self, '_pending_disconnect_steam_id', 0) or 0)
            and float(getattr(self, '_disconnect_grace_timer', 0.0)) > 0
        ):
            self._disconnect_grace_timer -= float(delta_time)
            if self._disconnect_grace_timer <= 0:
                pending_id = int(getattr(self, '_pending_disconnect_steam_id', 0) or 0)
                try:
                    members = set(self.net.get_lobby_members() or [])
                except Exception:
                    members = set()

                if pending_id and pending_id in members:
                    self._pending_disconnect_steam_id = 0
                    self._disconnect_grace_timer = 0.0
                    if not getattr(self.net, 'opponent_steam_id', 0):
                        try:
                            self.net._opponent_steam_id = pending_id
                        except Exception:
                            pass
                elif pending_id:
                    print(f"[OnlinePvP] Disconnect grace timeout: {pending_id}")
                    self.online_state = OnlineState.DISCONNECTED
                    self.game_over = True
                    self.winner = 'me'
                    self._record_match_result()
                    self._pending_disconnect_steam_id = 0
                    self._disconnect_grace_timer = 0.0

        # READY_CHECK: hazır sinyalini her saniyede bir yeniden gönder
        if (
            self.online_state == OnlineState.READY_CHECK
            and self._net_initialized
            and not self._session_established
        ):
            self._session_ping_timer -= float(delta_time)
            if self._session_ping_timer <= 0:
                self._send_session_ping()
                self._session_ping_timer = max(
                    self._SESSION_PING_INTERVAL_MS,
                    float(self._session_ping_backoff_ms or 0.0),
                )

        if (
            self.online_state == OnlineState.READY_CHECK
            and self._net_initialized
            and self.my_ready
            and self._ready_send_pending
            and self.net.opponent_steam_id
            and self._session_established
        ):
            self._send_ready_signal(reason='pending_flush')

        if (
            self.online_state == OnlineState.READY_CHECK
            and self.my_ready
            and not self.opponent_ready
            and self._net_initialized
        ):
            self._ready_resend_timer -= float(delta_time)
            if self._ready_resend_timer <= 0:
                self._send_ready_signal(reason='ready_resend')
                self._ready_resend_timer = self._READY_RESEND_INTERVAL_MS

        if (
            self.online_state == OnlineState.READY_CHECK
            and self._net_initialized
            and self.net.is_host
            and self.my_ready
            and self.opponent_ready
            and bool(getattr(self, '_game_start_pending_payload', None))
        ):
            self._game_start_retry_timer = float(getattr(self, '_game_start_retry_timer', 0.0)) - float(delta_time)
            if self._game_start_retry_timer <= 0:
                seed, pieces = self._game_start_pending_payload
                start_ok = bool(self.net.send_game_start(seed, pieces))
                if start_ok:
                    self._game_start_pending_payload = None
                    self._game_start_retry_timer = 0.0
                    self._start_countdown()
                else:
                    self._game_start_retry_timer = self._GAME_START_RETRY_INTERVAL_MS
                    print("[OnlinePvP] GAME_START retry basarisiz, tekrar denenecek.")

        self.update_particles(dt_ms=delta_time)
        self.update_ambient_particles(dt_ms=delta_time)
        self.update_screen_shake(dt_ms=delta_time)

        dt_frames = delta_time / 16.67 if delta_time > 0 else 1.0
        dt_seconds = max(0.0, float(delta_time or 0.0)) / 1000.0
        if self.my_line_flash_timer > 0:
            self.my_line_flash_timer = max(0, self.my_line_flash_timer - dt_frames)
            ratio = max(0.0, min(1.0, self.my_line_flash_timer / 20.0))
            self.my_line_glow_alpha = int(255 * ratio)
            if self.my_line_flash_timer <= 0:
                self.my_line_flash_rows = []
                self.my_line_glow_alpha = 0

        if self.opp_line_flash_timer > 0:
            self.opp_line_flash_timer = max(0, self.opp_line_flash_timer - dt_frames)
            ratio = max(0.0, min(1.0, self.opp_line_flash_timer / 20.0))
            self.opp_line_glow_alpha = int(255 * ratio)
            if self.opp_line_flash_timer <= 0:
                self.opp_line_flash_rows = []
                self.opp_line_glow_alpha = 0

        # Combo mesaj timer
        if self.my_combo_message_time > 0:
            self.my_combo_message_time = max(0, self.my_combo_message_time - dt_frames)
            if self.my_combo_message_time <= 0:
                self.my_combo_message = ""

        if self.my_line_sweep_active:
            board_pixel_width = BOARD_WIDTH * self.cell_size
            sweep_width = max(1, int(self.cell_size * 1.5))
            sweep_travel_px = max(1.0, float(board_pixel_width + sweep_width))
            my_level = max(1, int(getattr(self.my_board, 'level', 1)))
            sweep_speed = _compute_line_sweep_progress_speed(self.block_fall_speed, sweep_travel_px, my_level)
            self.my_line_sweep_progress += dt_seconds * sweep_speed
            if self.my_line_sweep_progress >= 1.0:
                self.my_line_sweep_progress = 1.0
                self.my_line_sweep_active = False
                self.my_line_sweep_rows = []

        if self.opp_line_sweep_active:
            board_pixel_width = BOARD_WIDTH * self.cell_size
            sweep_width = max(1, int(self.cell_size * 1.5))
            sweep_travel_px = max(1.0, float(board_pixel_width + sweep_width))
            opponent_board = getattr(self, 'opponent_board', None)
            opp_level = max(1, int(getattr(opponent_board, 'level', 1)))
            sweep_speed = _compute_line_sweep_progress_speed(self.block_fall_speed, sweep_travel_px, opp_level)
            self.opp_line_sweep_progress += dt_seconds * sweep_speed
            if self.opp_line_sweep_progress >= 1.0:
                self.opp_line_sweep_progress = 1.0
                self.opp_line_sweep_active = False
                self.opp_line_sweep_rows = []

        _update_wave_effects(self.my_wave_effects, dt_frames)
        _update_wave_effects(self.opp_wave_effects, dt_frames)

        if self.my_falling_block_animations:
            fall_speed = self.block_fall_speed * dt_frames * 60
            for anim in self.my_falling_block_animations:
                if not anim.get('started', False) and self.my_line_sweep_progress >= anim.get('sweep_trigger', 0):
                    anim['started'] = True
                if anim.get('started', False):
                    anim['current_offset'] += fall_speed
                    if anim['current_offset'] >= 0:
                        anim['current_offset'] = 0
            self.my_falling_block_animations = [
                anim for anim in self.my_falling_block_animations
                if not (anim['current_offset'] >= 0 and anim.get('started', False))
            ]

        if self.opp_falling_block_animations:
            fall_speed = self.block_fall_speed * dt_frames * 60
            for anim in self.opp_falling_block_animations:
                if not anim.get('started', False) and self.opp_line_sweep_progress >= anim.get('sweep_trigger', 0):
                    anim['started'] = True
                if anim.get('started', False):
                    anim['current_offset'] += fall_speed
                    if anim['current_offset'] >= 0:
                        anim['current_offset'] = 0
            self.opp_falling_block_animations = [
                anim for anim in self.opp_falling_block_animations
                if not (anim['current_offset'] >= 0 and anim.get('started', False))
            ]

        if self.drop_trails:
            self._update_drop_trails(dt_frames)

        # Durum mesajı zamanlayıcı
        if self._status_timer > 0:
            self._status_timer -= delta_time / 1000.0
            if self._status_timer <= 0:
                self._status_msg = ''

        if self.online_state == OnlineState.COUNTDOWN:
            self.countdown_timer += delta_time
            if self.countdown_timer >= 1000:
                self.countdown_timer -= 1000
                self.countdown_value -= 1
                if self.countdown_value <= 0:
                    self._start_game()
            return

        if self.online_state != OnlineState.PLAYING:
            return

        if self.game_over or self.paused or self.opponent_paused:
            return

        # Düşüş hızı
        level = self.my_board.level if self.my_board else 1
        fall_speed = get_level_fall_speed_ms(
            level,
            initial_speed=INITIAL_FALL_SPEED,
            min_speed=LEVEL_SPEED_MIN_MS,
        )

        # Soft drop hızlandırma
        if self.soft_dropping:
            fall_speed = min(fall_speed, ONLINE_PVP_SOFT_DROP_SPEED_MS)

        # Satır temizleme animasyonu oynarken otomatik gravity duraklatılır;
        # oyuncu soft drop tutuyorsa (veya hard drop yaptıysa, o ayrı işlenir)
        # parça yine de iner. Sadece kendi tahtamın animasyonu beni etkiler;
        # rakip parçası ağ üzerinden sürülür.
        my_anim_active = bool(self.my_line_sweep_active) or bool(self.my_falling_block_animations)
        gravity_paused = my_anim_active and not bool(self.soft_dropping)

        if gravity_paused:
            self.fall_timer = 0
        else:
            self.fall_timer += delta_time

        if not gravity_paused and self.fall_timer >= fall_speed:
            self.fall_timer = 0
            # Parçayı aşağı düşür
            if self.my_board and self.my_piece:
                if self.my_board.is_valid_position(self.my_piece, dy=1):
                    self.my_piece.y += 1
                    if self.soft_dropping:
                        self.my_board.score += 1
                    self.lock_timer = 0
                    self._send_piece_position()

        # Kilitleme gecikmesi — her frame kontrol et (fall_timer dışında)
        if self.my_board and self.my_piece:
            if not self.my_board.is_valid_position(self.my_piece, dy=1):
                self.lock_timer += delta_time
                if self.lock_timer >= DEFAULT_LOCK_DELAY:
                    self._lock_piece()
            else:
                self.lock_timer = 0

        # DAS (yatay basılı tutma)
        self._update_das(delta_time)

        # Periyodik tahta snapshot'ı gönder
        self.state_snapshot_timer += delta_time
        self._piece_position_send_timer += float(delta_time)
        if self._pending_piece_position_dirty:
            self._flush_piece_position(force=False)
        if self.state_snapshot_timer >= self.STATE_SNAPSHOT_INTERVAL:
            self.state_snapshot_timer = 0
            self._send_board_snapshot()

    def _lock_piece(self):
        """Parçayı kilitle, satır temizle, bekleyen çöpleri uygula, yeni parça al."""
        if not self.my_board or not self.my_piece:
            return

        my_board_rect = getattr(self, '_my_board_rect', None)
        if self.effects_enabled and my_board_rect:
            cell_size = max(1, my_board_rect.width // BOARD_WIDTH)
            piece_shape = self.my_piece.get_shape()
            color_matrix = getattr(self.my_piece, 'color_matrix', None)
            for row_i, row in enumerate(piece_shape):
                for col_i, cell in enumerate(row):
                    if not cell:
                        continue
                    board_col = self.my_piece.x + col_i
                    board_row = self.my_piece.y + row_i
                    if not (0 <= board_col < BOARD_WIDTH and 0 <= board_row < BOARD_HEIGHT):
                        continue
                    cell_color = self.my_piece.color
                    if color_matrix is not None:
                        try:
                            matrix_color = color_matrix[row_i][col_i]
                            if matrix_color is not None:
                                cell_color = matrix_color
                        except Exception:
                            pass
                    screen_x = my_board_rect.x + board_col * cell_size + cell_size // 2
                    screen_y = my_board_rect.y + board_row * cell_size + cell_size // 2
                    self.create_lock_explosion(screen_x, screen_y, cell_color, cell_size=cell_size)

        lines = self.my_board.lock_piece(self.my_piece)
        cleared_rows = list(self.my_board.last_cleared_lines) if lines > 0 else []

        # Lock-out kontrolü (Tetris Guideline)
        if self.my_board.is_game_over():
            self._mark_local_eliminated()
            return

        # Satır temizlenmiyorsa blok kilitlenme sesi çal (çakışma önlenir)
        if lines == 0:
            try:
                self.sound.play('lock')
            except Exception:
                pass

        if lines > 0:
            if ONLINE_PVP_GARBAGE_ENABLED:
                self.pending_garbage = max(0, self.pending_garbage - lines)
                self._send_garbage(lines)
            self.net.send_score_update(
                self.my_board.score,
                self.my_board.lines_cleared,
                self.my_board.level
            )
            try:
                self.sound.play('line' if lines < 4 else 'tetris')
            except Exception:
                pass
            # Combo mesajı (DOUBLE/TRIPLE/QUADRIX)
            if lines == 4:
                self.my_combo_message = "QUADRIX!"
                self.my_combo_message_time = 120
            elif lines >= 2:
                if lines == 2:
                    self.my_combo_message = "DOUBLE!"
                elif lines == 3:
                    self.my_combo_message = "TRIPLE!"
                else:
                    self.my_combo_message = f"{lines}x CLEAR!"
                combo_count = getattr(self.my_board, 'combo', 0)
                if combo_count > 1:
                    self.my_combo_message += f"  x{combo_count} Combo"
                self.my_combo_message_time = 120
            else:
                combo_count = getattr(self.my_board, 'combo', 0)
                if combo_count > 1:
                    self.my_combo_message = f"x{combo_count} Combo!"
                    self.my_combo_message_time = 90
            if self.my_board.last_cleared_lines and self.effects_enabled and my_board_rect:
                cell_size = my_board_rect.width // BOARD_WIDTH
                self._safe_trigger_line_clear_feedback(
                    list(self.my_board.last_cleared_lines),
                    my_board_rect.x,
                    my_board_rect.y,
                    cell_size,
                    self.my_board,
                    is_opponent=False,
                )

        # Kalan bekleyen çöp satırları uygula (Online garbage kapalıysa bu blok atlanır)
        if ONLINE_PVP_GARBAGE_ENABLED and self.pending_garbage > 0:
            self._apply_pending_garbage()
            if self.game_over:
                return  # Garbage oyunu bitirdi

        # Yeni parça
        self.my_piece = self.my_next_piece
        skip_hidden_rows(self.my_piece, self.my_board)
        self.my_next_piece = self._get_next_piece()
        self.next_piece = self.my_next_piece
        self.lock_timer = 0
        self.hold_used = False  # Yeni parçada hold tekrar kullanılabilir

        # Yeni parça pozisyonunu hemen gönder
        self._send_piece_position(force=True)
        self._send_board_snapshot(clear_rows=cleared_rows)

    def _update_das(self, delta_time: int):
        """DAS (Delayed Auto Shift) güncelle."""
        if self.das_direction == 0:
            self.das_timer = 0
            self.das_active = False
            return

        self.das_timer += delta_time
        if not self.das_active:
            if self.das_timer >= ONLINE_PVP_DAS_DELAY_MS:
                self.das_active = True
                self.das_timer = 0
                self._move_horizontal(self.das_direction)
        else:
            if self.das_timer >= ONLINE_PVP_DAS_REPEAT_MS:
                self.das_timer = 0
                self._move_horizontal(self.das_direction)

    def _move_horizontal(self, dx: int):
        """Parçayı yatay hareket ettir."""
        if self.my_board and self.my_piece:
            if self.my_board.is_valid_position(self.my_piece, dx=dx):
                self.my_piece.x += dx
                self._send_piece_position()

    # ============================================================
    #  INPUT İŞLEME
    # ============================================================

    def handle_input(self):
        """Pygame event'lerini işle."""
        # Gamepad sentetik eventleri
        gamepad_events = []
        if self.gamepad:
            try:
                delta = self.clock.get_time() if hasattr(self, 'clock') else 16
                if (
                    self.online_state == OnlineState.PLAYING
                    and not self.game_over
                    and not self.paused
                    and not self.opponent_paused
                ):
                    self.gamepad.set_context('game')
                else:
                    self.gamepad.set_context('menu')
                gamepad_events = self.gamepad.update(delta)
            except Exception:
                pass

        all_events = list(pygame.event.get()) + gamepad_events

        for event in all_events:
            if event.type == pygame.QUIT:
                return False

            if self._is_focus_loss_event(event):
                self._pause_for_focus_loss()
                continue

            # Gamepad hot-plug: bağlantı kopması durumunda otomatik pause.
            try:
                from gamepad_manager import handle_gamepad_hotplug_event as _gp_hotplug
                hotplug_result = _gp_hotplug(event)
            except Exception:
                hotplug_result = None
            if hotplug_result is not None:
                if hotplug_result == 'disconnected':
                    self._pause_for_focus_loss()
                continue

            if event.type == pygame.VIDEORESIZE:
                self.window_width = max(800, event.w)
                self.window_height = max(600, event.h)
                # Tek-context GL aktifken ve boyut sabitse create_display ÇAĞIRMA.
                _gl_skip = False
                try:
                    import gl_compat as _glc
                    _gl_skip = _glc.should_skip_display_rebuild(self.window_width, self.window_height)
                    if _gl_skip:
                        _gs = _glc.get_game_surface()
                        if _gs is not None:
                            self.screen = _gs
                except Exception:
                    _gl_skip = False
                if not _gl_skip:
                    self.screen = create_display(self.window_width, self.window_height,
                                                 fullscreen=True, resizable=False, borderless=True)
                # Surface'tan gerçek piksel boyutunu al (macOS HiDPI)
                self.window_width = self.screen.get_width()
                self.window_height = self.screen.get_height()
                continue

            if event.type == pygame.KEYDOWN:
                result = self._handle_keydown(event)
                if result is not None:
                    return result

            if event.type == pygame.KEYUP:
                self._handle_keyup(event)

            # Metin girişi — Lobi kodu text input
            if event.type == pygame.TEXTINPUT and self._join_code_active:
                for ch in event.text:
                    if ch.isdigit() and len(self._join_code_input) < 6:
                        self._join_code_input += ch
                        self._join_code_error = ''

            if event.type == pygame.MOUSEBUTTONDOWN:
                result = self._handle_mouse_click(event)
                if result is not None:
                    return result

            if event.type == pygame.MOUSEWHEEL:
                self._handle_scroll(event)

        return True

    def _handle_keydown(self, event):
        """Tuş basılma olayı."""
        key = event.key
        mods = getattr(event, 'mod', 0)

        # ESC — Lobiden / oyundan çık
        if key == pygame.K_ESCAPE:
            # Kod girişi aktifse önce onu kapat
            if self._join_code_active:
                self._join_code_active = False
                self._join_code_input = ''
                self._join_code_error = ''
                return None
            if self.online_state == OnlineState.PLAYING:
                self.paused = not self.paused
                self._freeze_active_gameplay_input()
                # Rakibe bildir
                if self.paused:
                    self._send_control_message(MsgType.PAUSE_REQUEST, reason='esc_pause')
                else:
                    self._send_control_message(MsgType.RESUME, reason='esc_resume')
                return None
            elif self.online_state == OnlineState.WAITING:
                self._return_to_pvp_lobby_menu()
                return None
            elif self.online_state in (OnlineState.GAME_OVER, OnlineState.DISCONNECTED):
                self.net.leave_lobby()
                return 'menu'
            else:
                self.net.leave_lobby()
                return 'menu'

        # Lobi ekranı
        if self.online_state == OnlineState.LOBBY_MENU:
            # Kod girişi aktifken tuş olayları
            if self._join_code_active:
                if key == pygame.K_RETURN or key == pygame.K_KP_ENTER:
                    self._try_join_by_code()
                elif key == pygame.K_BACKSPACE:
                    if self._join_code_input:
                        self._join_code_input = self._join_code_input[:-1]
                        self._join_code_error = ''
                elif key == pygame.K_v and (mods & pygame.KMOD_CTRL):
                    # Ctrl+V — Yapıştır
                    pasted = self._paste_from_clipboard()
                    if pasted:
                        # Sadece rakam karakterlerini al
                        digits = ''.join(c for c in pasted if c.isdigit())
                        if digits:
                            self._join_code_input = digits[:6]
                            self._join_code_error = ''
                elif key == pygame.K_TAB:
                    self._join_code_active = False
                return None

            if key == pygame.K_1 or key == pygame.K_RETURN or key == pygame.K_KP_ENTER:
                if self._init_networking():
                    self._create_lobby(public=False)
                    self._status_msg = t('creating_lobby', 'Özel lobi oluşturuluyor...')
                    self._status_timer = 2.0
            elif key == pygame.K_2:
                if self._init_networking():
                    self._create_lobby(public=True)
                    self._status_msg = t('creating_lobby', 'Herkese açık lobi oluşturuluyor...')
                    self._status_timer = 2.0
            elif key == pygame.K_3:
                self._request_lobby_list()
            elif key == pygame.K_i:
                self._do_invite_friend()
            elif key == pygame.K_j:
                # J tuşu — Kod ile Katıl alanını aktifle
                self._join_code_active = True
                self._join_code_input = ''
                self._join_code_error = ''
            return None

        # Bekleme → Davet / Kopyala
        if self.online_state == OnlineState.WAITING:
            if key == pygame.K_i:
                self._do_invite_friend()
            elif key == pygame.K_c and self._lobby_code:
                self._copy_lobby_code()
            return None

        # Bekleme → Hazır
        if self.online_state == OnlineState.READY_CHECK:
            if key == pygame.K_RETURN:
                self.my_ready = True
                self._send_ready_signal(reason='keypress_enter')
                self._check_both_ready()
            return None

        # Oyun sonrası → Tekrar / Çık
        if self.online_state == OnlineState.GAME_OVER:
            if key == pygame.K_r:
                # Rematch
                self._request_rematch()
                return None
            if key == pygame.K_ESCAPE or key == pygame.K_q:
                self.net.leave_lobby()
                return 'menu'
            return None

        # Oyun sırasında kontroller
        if (
            self.online_state == OnlineState.PLAYING
            and not self.game_over
            and not self.paused
            and not self.opponent_paused
        ):
            if key == pygame.K_LEFT or key == pygame.K_a:
                self._move_horizontal(-1)
                self.das_direction = -1
                self.das_timer = 0
                self.das_active = False
            elif key == pygame.K_RIGHT or key == pygame.K_d:
                self._move_horizontal(1)
                self.das_direction = 1
                self.das_timer = 0
                self.das_active = False
            elif key == pygame.K_UP or key == pygame.K_w:
                self._rotate_piece(1)
            elif key == pygame.K_z:
                self._rotate_piece(-1)
            elif key == pygame.K_DOWN or key == pygame.K_s:
                # Soft drop başlat
                self.soft_dropping = True
                if self.my_board and self.my_piece:
                    if self.my_board.is_valid_position(self.my_piece, dy=1):
                        self.my_piece.y += 1
                        self.my_board.score += 1
                        self._send_piece_position()
            elif key == pygame.K_SPACE:
                self._hard_drop()
            elif key in (pygame.K_c, pygame.K_v, pygame.K_LSHIFT, pygame.K_RSHIFT):
                # Hold
                self._do_hold()
            elif key == pygame.K_i:
                # Arkadaş davet et (oyun sırasında)
                self._do_invite_friend()

        return None

    def _handle_keyup(self, event):
        key = event.key
        if key in (pygame.K_LEFT, pygame.K_a) and self.das_direction == -1:
            self.das_direction = 0
        elif key in (pygame.K_RIGHT, pygame.K_d) and self.das_direction == 1:
            self.das_direction = 0
        elif key in (pygame.K_DOWN, pygame.K_s):
            self.soft_dropping = False

    def _handle_scroll(self, event):
        """Fare tekerleği — lobi listesi scroll."""
        if self.online_state == OnlineState.LOBBY_MENU and self._get_lobby_entries_for_display():
            self._lobby_list_scroll = max(0, self._lobby_list_scroll - event.y)

    def _handle_mouse_click(self, event):
        """Fare tıklama — tüm ekranlardaki butonlar."""
        pos = normalize_mouse_pos(event.pos) or event.pos

        for btn in self._lobby_buttons:
            if btn['rect'].collidepoint(pos):
                action = btn.get('action', '')
                try:
                    if action == 'create_private':
                        if self._init_networking():
                            self._create_lobby(public=False)
                            self._status_msg = t('creating_lobby', 'Özel lobi oluşturuluyor...')
                            self._status_timer = 2.0
                    elif action == 'create_public':
                        if self._init_networking():
                            self._create_lobby(public=True)
                            self._status_msg = t('creating_lobby', 'Herkese açık lobi oluşturuluyor...')
                            self._status_timer = 2.0
                    elif action == 'find_match':
                        self._request_lobby_list()
                    elif action == 'filter_all_lobbies':
                        self._set_lobby_list_filter('all')
                    elif action == 'filter_public_lobbies':
                        self._set_lobby_list_filter('public')
                    elif action == 'back':
                        return 'menu'
                    elif action == 'invite_friend':
                        self._do_invite_friend()
                    elif action == 'ready':
                        self.my_ready = True
                        self._send_ready_signal(reason='button_ready')
                        self._check_both_ready()
                    elif action == 'rematch':
                        self._request_rematch()
                    elif action == 'exit_menu':
                        self.net.leave_lobby()
                        return 'menu'
                    elif action == 'back_to_pvp_lobby':
                        self._return_to_pvp_lobby_menu()
                    elif action.startswith('join_lobby:'):
                        lobby_id_str = action.split(':', 1)[1]
                        try:
                            lobby_id = int(lobby_id_str)
                            self._join_target_lobby_id = 0
                            self.net.join_lobby(lobby_id)
                        except (ValueError, TypeError):
                            pass
                    elif action.startswith('join_private_lobby:'):
                        lobby_id_str = action.split(':', 1)[1]
                        try:
                            self._open_private_lobby_code_prompt(int(lobby_id_str))
                        except (ValueError, TypeError):
                            self._join_target_lobby_id = 0
                    elif action == 'debug_lobby':
                        self._status_msg = t(
                            'online_pvp_trailer_debug_info',
                            'Bu demo lobi Steam fragmani icin gosterim amaclidir.',
                        )
                        self._status_timer = 2.5
                    elif action.startswith('resolve_lobby_join:'):
                        lobby_id_str = action.split(':', 1)[1]
                        try:
                            self._start_lobby_browser_join(int(lobby_id_str))
                        except (ValueError, TypeError):
                            pass
                    elif action == 'join_by_code':
                        # "Kod ile Katıl" butonuna tıklandı
                        self._join_target_lobby_id = 0
                        self._join_code_active = True
                        self._join_code_input = ''
                        self._join_code_error = ''
                    elif action == 'join_code_submit':
                        self._try_join_by_code()
                    elif action == 'copy_lobby_code':
                        self._copy_lobby_code()
                    elif action == 'copy_lobby_id':
                        self._copy_lobby_id()
                    elif action == 'join_code_field':
                        self._join_code_active = True
                except Exception as e:
                    print(f"[OnlinePvP] Buton aksiyonu hatası ({action}): {e}")
                    import traceback; traceback.print_exc()
                    self._status_msg = t('steam_not_available', 'Steam bağlantısı kurulamadı!')
                    self._status_timer = 3.0
                try:
                    self.sound.play('click')
                except Exception:
                    pass
                break
        return None

    def _rotate_piece(self, direction: int):
        """Parçayı döndür (SRS wall kick dahil)."""
        if not self.my_board or not self.my_piece:
            return
        old_rot = self.my_piece.rotation_state
        self.my_piece.rotate(direction)
        if not self.my_board.is_valid_position(self.my_piece):
            # Basit wall kick denemeleri
            for dx in [1, -1, 2, -2]:
                if self.my_board.is_valid_position(self.my_piece, dx=dx):
                    self.my_piece.x += dx
                    self._send_piece_position()
                    try:
                        self.sound.play('rotate')
                    except Exception:
                        pass
                    return
            # Hiçbiri çalışmadıysa geri al
            self.my_piece.rotate(-direction)
        else:
            self._send_piece_position()
            try:
                self.sound.play('rotate')
            except Exception:
                pass

    def _hard_drop(self):
        """Sert düşüş — parçayı anında en alta indir ve kilitle."""
        if not self.my_board or not self.my_piece:
            return
        drop_distance = 0
        start_y = self.my_piece.y
        while self.my_board.is_valid_position(self.my_piece, dy=1):
            self.my_piece.y += 1
            drop_distance += 1
        self.my_board.score += drop_distance * 2
        my_board_rect = getattr(self, '_my_board_rect', None)
        if self.effects_enabled and drop_distance > 0 and my_board_rect:
            cell_size = max(1, my_board_rect.width // BOARD_WIDTH)
            self._create_drop_trail(
                self.my_piece,
                my_board_rect.x,
                my_board_rect.y,
                cell_size,
                start_y,
                drop_distance,
                trail_type='hard',
            )
        if self.effects_enabled and drop_distance > 0:
            self.trigger_hard_drop_screen_shake()
        self._send_piece_position(force=True)
        try:
            self.sound.play('drop')
        except Exception:
            pass
        self._lock_piece()

    # ============================================================
    #  DAVET & REMATCH
    # ============================================================

    def _do_invite_friend(self):
        """Steam overlay arkadaş davet penceresi aç — kullanıcıya geri bildirim ver.

        Önce C++ bridge üzerinden dener. Başarısız olursa doğrudan
        Steam ctypes API'si üzerinden overlay açar (Windows uyumluluğu).
        """
        if not self._net_initialized:
            ok = self._init_networking()
            if not ok:
                self._status_msg = t('steam_not_available', 'Steam bağlantısı kurulamadı!')
                self._status_timer = 3.0
                return

        if not self.net.available or not self.net.initialized:
            self._status_msg = t('steam_not_available', 'Steam bağlantısı kurulamadı!')
            self._status_timer = 3.0
            return

        # Lobi yoksa önce oluştur
        if not self.net.lobby_id:
            self._create_lobby(public=False)
            self._status_msg = t('creating_lobby_invite', 'Lobi oluşturuluyor...')
            self._status_timer = 2.0
            # Lobi oluşturulduktan sonra davet açılacak — flag koy
            self._invite_after_lobby = True
            return

        # Önce C++ bridge ile dene
        invite_ok = False
        try:
            self.net.invite_friend()
            invite_ok = True
        except Exception:
            pass

        # C++ bridge çalışmadıysa doğrudan ctypes overlay dene
        if not invite_ok:
            lobby_id = self.net.lobby_id
            if lobby_id:
                _activate_invite_dialog(lobby_id)

        self._status_msg = t('invite_sent', 'Steam davet penceresi açıldı')
        self._status_timer = 2.5
        try:
            self.sound.play('click')
        except Exception:
            pass

    def _request_rematch(self):
        """Rakibe rematch isteği gönder ve ready check'e geç."""
        self.my_ready = False
        self.opponent_ready = False
        self._ready_resend_timer = 0.0
        self._game_start_pending_payload = None
        self._game_start_retry_timer = 0.0
        self._reset_match_result_state()
        self.online_state = OnlineState.READY_CHECK
        # Rakibe rematch isteği bildir
        self._send_control_message(MsgType.REMATCH, reason='request_rematch')
        try:
            self.sound.play('click')
        except Exception:
            pass

    # ============================================================
    #  LOBİ KODU İŞLEMLERİ
    # ============================================================

    def _try_join_by_code(self):
        """Girilen 6 haneli lobi kodunu parse edip katılmayı dene.

        Lobi kodu metadata araması ile eşleşen lobiye katılır.
        Bulunamazsa hata mesajı gösterilir.
        """
        code = self._join_code_input.strip()
        if not code:
            self._join_code_error = t('enter_lobby_code', 'Lobi kodu girin')
            return

        if len(code) != 6 or not code.isdigit():
            self._join_code_error = t('enter_six_digit_code', '6 haneli lobi kodu girin')
            return

        if not self._init_networking():
            self._join_code_error = t('steam_not_available', 'Steam bağlantısı kurulamadı!')
            return

        target_lobby_id = int(getattr(self, '_join_target_lobby_id', 0) or 0)
        if target_lobby_id:
            target_snapshot = self._get_lobby_metadata_snapshot(target_lobby_id, prefer_live=True)
            if target_snapshot['metadata_ready']:
                if not target_snapshot['requires_code']:
                    self._join_target_lobby_id = 0
                    self.net.join_lobby(target_lobby_id)
                    self._status_msg = t('joining_lobby', 'Lobiye katılınıyor...')
                    self._status_timer = 2.0
                    self._join_code_active = False
                    return
                if target_snapshot['code'] != code:
                    self._join_code_error = t('invalid_lobby_code', 'Gecersiz lobi kodu')
                    self._status_msg = t('lobby_not_found_by_code', 'Bu kodla lobi bulunamadı')
                    self._status_timer = 3.0
                    return
                self._join_target_lobby_id = 0
                self._remember_private_join_authorization(target_lobby_id, code)
                self.net.join_lobby(target_lobby_id)
                self._status_msg = t('joining_lobby', 'Lobiye katılınıyor...')
                self._status_timer = 2.0
                self._join_code_active = False
                return
            else:
                # Metadata henüz gelmemiş (cross-platform) — kodu yetkilendirme
                # olarak kaydet ve doğrudan katıl. Katıldıktan sonra
                # _validate_joined_lobby_access metadata ile kontrol edecek.
                self._join_target_lobby_id = 0
                self._remember_private_join_authorization(target_lobby_id, code)
                self.net.join_lobby(target_lobby_id)
                self._status_msg = t('joining_lobby', 'Lobiye katılınıyor...')
                self._status_timer = 2.0
                self._join_code_active = False
                return

        # Her zaman 6 haneli kod olarak ara
        self._code_search_retry_count = 0
        self._code_search_retry_timer = 0.0
        self._code_search_retry_code = ''
        self._code_search_retry_use_full_scan = False
        self._begin_code_search(code, fallback_scan=False)
        self._status_msg = t('searching_by_code', 'Lobi kodu aranıyor...')
        self._status_timer = 3.0
        self._join_code_active = False

    def _try_direct_join_by_code(self, code: str):
        """Kod araması sonuçsuz kaldığında, kodu doğrudan lobby ID olarak dene."""
        try:
            lobby_id = int(code)
            if lobby_id > 100000:
                self.net.join_lobby(lobby_id)
                self._status_msg = t('joining_lobby', 'Lobiye katılınıyor...')
                self._status_timer = 2.0
                return
        except (ValueError, TypeError):
            pass
        self._status_msg = t('lobby_not_found_by_code', 'Bu kodla lobi bulunamadı')
        self._status_timer = 3.0

    def _copy_lobby_code(self):
        """Lobi kodunu panoya kopyala."""
        code = self._lobby_code
        if not code:
            return
        ok = self._copy_to_clipboard(code)
        if ok:
            self._status_msg = t('code_copied', 'Lobi kodu kopyalandı!')
        else:
            self._status_msg = f'{t("lobby_code", "Lobi Kodu")}: {code}'
        self._status_timer = 2.5
        try:
            self.sound.play('click')
        except Exception:
            pass

    def _copy_lobby_id(self):
        """Tam lobi ID'sini panoya kopyala."""
        lid = self._lobby_id_str or str(self.net.lobby_id or '')
        if not lid:
            return
        ok = self._copy_to_clipboard(lid)
        if ok:
            self._status_msg = t('lobby_id_copied', 'Lobi ID kopyalandı!')
        else:
            self._status_msg = f'ID: {lid}'
        self._status_timer = 2.5
        try:
            self.sound.play('click')
        except Exception:
            pass

    def _copy_to_clipboard(self, text: str) -> bool:
        """Metni sistem panosuna kopyala — cross-platform.

        Tüm platformlarda metin stdin üzerinden aktarılır;
        komut satırına doğrudan enjeksiyon yapılmaz.
        """
        import subprocess
        try:
            if sys.platform == 'win32':
                # clip.exe — Windows'ta native; stdin'den okur, enjeksiyon riski yok.
                create_no_window = int(getattr(subprocess, 'CREATE_NO_WINDOW', 0) or 0)
                process = subprocess.Popen(
                    ['clip'],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=create_no_window,
                )
                try:
                    # clip.exe BOM'lu UTF-16 girdiyi güvenilir şekilde tanır.
                    # Python 'utf-16' encoding otomatik BOM ekler.
                    process.communicate(text.encode('utf-16'), timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                    return False
                return process.returncode == 0
            elif sys.platform == 'darwin':
                process = subprocess.Popen(['pbcopy'], stdin=subprocess.PIPE)
                try:
                    process.communicate(text.encode('utf-8'), timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                    return False
                return process.returncode == 0
            else:
                for command in (
                    ['xclip', '-selection', 'clipboard'],
                    ['wl-copy'],
                    ['xsel', '--clipboard', '--input'],
                ):
                    try:
                        process = subprocess.Popen(command, stdin=subprocess.PIPE)
                    except FileNotFoundError:
                        continue
                    except OSError:
                        continue
                    try:
                        process.communicate(text.encode('utf-8'), timeout=2)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        continue
                    except Exception:
                        continue
                    if process.returncode == 0:
                        return True
                return False
        except Exception:
            return False

    def _paste_from_clipboard(self) -> str:
        """Sistem panosundan metin oku — cross-platform."""
        try:
            import subprocess
            if sys.platform == 'win32':
                create_no_window = int(getattr(subprocess, 'CREATE_NO_WINDOW', 0) or 0)
                result = subprocess.run(
                    ['powershell', '-command', 'Get-Clipboard'],
                    capture_output=True, text=True, timeout=2,
                    creationflags=create_no_window,
                )
                return result.stdout.strip()
            elif sys.platform == 'darwin':
                result = subprocess.run(
                    ['pbpaste'], capture_output=True, text=True, timeout=2)
                return result.stdout.strip()
            else:
                for command in (
                    ['xclip', '-selection', 'clipboard', '-o'],
                    ['wl-paste', '--no-newline'],
                    ['xsel', '--clipboard', '--output'],
                ):
                    try:
                        result = subprocess.run(
                            command,
                            capture_output=True,
                            text=True,
                            timeout=2,
                        )
                    except FileNotFoundError:
                        continue
                    except subprocess.TimeoutExpired:
                        continue
                    except OSError:
                        continue
                    if result.returncode == 0:
                        return result.stdout.strip()
                return ''
        except Exception:
            return ''

    # ============================================================
    #  ÇİZİM
    # ============================================================

    def draw(self):
        """Ekranı çiz."""
        # Her frame'de buton listesini sıfırla — draw metotları dolduracak
        self._lobby_buttons.clear()

        # Arka plan — retro_style ile tutarlı (resim + gradient fallback)
        _rs.draw_background(self.screen)
        self.draw_ambient_particles()
        # Düşen blok animasyonu — diğer tüm pencerelerle ortak
        self.background_fx.update(self.screen)
        self.background_fx.draw(self.screen)

        if self.online_state == OnlineState.LOBBY_MENU:
            self._draw_lobby_menu()
        elif self.online_state == OnlineState.WAITING:
            self._draw_waiting_screen()
        elif self.online_state == OnlineState.READY_CHECK:
            self._draw_ready_check()
        elif self.online_state == OnlineState.COUNTDOWN:
            self._draw_countdown()
        elif self.online_state == OnlineState.PLAYING:
            self._draw_game()
        elif self.online_state == OnlineState.GAME_OVER:
            self._draw_game()
            self._draw_game_over_overlay()
        elif self.online_state == OnlineState.DISCONNECTED:
            self._draw_disconnected()

        if self.online_state != OnlineState.GAME_OVER:
            self.draw_particles()

        # NOT: pygame.display.flip() burada çağrılmıyor.
        # Ana döngü (main.py) geçiş efektini src üstüne çizdikten sonra
        # flip() yapıyor — local PvP ile aynı davranış.

    # ─── Lobi Menü Çizimi ───

    def _draw_lobby_menu(self):
        """Lobi oluştur/katıl — retro_style butonları ve lobi listesi."""
        w, h = self.window_width, self.window_height
        cx = w // 2
        sc = self._ui_scale()
        s = lambda v, minimum=1: self._sx(v, sc, minimum)

        # Başlık (retro_style.draw_title ile — glow + alt çizgi)
        title_rect = _rs.draw_title(self.screen, t('online_pvp_title', 'ONLINE PvP'), (cx, s(58)))

        # Sol panel: butonlar — modernize edilmiş yerleşim
        btn_w = s(340)
        btn_h = s(52)
        panel_left = max(s(30), cx - s(400))
        btn_x = panel_left
        btn_y_start = title_rect.bottom + s(28)
        gap = s(12)

        # Özel Lobi bölümü başlığı
        section_font = _rs.get_font(s(13, minimum=10), bold=False)
        sec1 = render_text(section_font, t('private_lobby_section', '── Özel Lobi ──'),
                                   True, _rs.text_muted)
        self.screen.blit(sec1, sec1.get_rect(center=(btn_x + btn_w // 2, btn_y_start - s(8))))

        buttons_private = [
            ('create_private', t('create_private_lobby', 'Özel Lobi Oluştur'),
             _rs.primary, '1 / ENTER'),
            ('join_by_code', t('join_by_code', 'Kod ile Katıl'),
             UIColors.NEON_CYAN, 'J'),
            ('invite_friend', t('invite_friend', 'Arkadaş Davet Et'),
             UIColors.NEON_GREEN, 'I'),
        ]

        mouse_pos = get_mouse_pos()
        y_pos = btn_y_start + s(8)
        for action, label, color, shortcut in buttons_private:
            rect = pygame.Rect(btn_x, y_pos, btn_w, btn_h)
            is_hover = rect.collidepoint(mouse_pos)

            _rs.draw_uniform_button(
                self.screen, rect, label,
                sub_text=shortcut,
                color_code=color,
                state='hover' if is_hover else 'normal',
            )
            self._lobby_buttons.append({'rect': rect, 'action': action})
            y_pos += btn_h + gap

        # "Kod ile Katıl" metin giriş alanı (aktifse göster)
        if self._join_code_active:
            self._draw_join_code_input(btn_x, y_pos, btn_w, s, mouse_pos)
            y_pos += s(236)

        # Herkese Açık Lobi bölümü başlığı
        y_pos += s(10)
        sec2 = render_text(section_font, t('public_lobby_section', '── Herkese Açık ──'),
                                   True, _rs.text_muted)
        self.screen.blit(sec2, sec2.get_rect(center=(btn_x + btn_w // 2, y_pos)))
        y_pos += s(18)

        # "Herkese Açık Lobi Oluştur" butonu — sadece public lobi oluşturur
        pub_create_rect = pygame.Rect(btn_x, y_pos, btn_w, btn_h)
        pub_create_hover = pub_create_rect.collidepoint(mouse_pos)
        _rs.draw_uniform_button(
            self.screen, pub_create_rect,
            t('create_public_lobby', 'Herkese Acik Lobi Olustur'),
            sub_text='2',
            color_code=_rs.success,
            state='hover' if pub_create_hover else 'normal',
        )
        self._lobby_buttons.append({'rect': pub_create_rect, 'action': 'create_public'})
        y_pos += btn_h + gap

        # "Maç Bul" butonu — lobi listesini yeniler
        find_rect = pygame.Rect(btn_x, y_pos, btn_w, btn_h)
        find_hover = find_rect.collidepoint(mouse_pos)
        _rs.draw_uniform_button(
            self.screen, find_rect,
            t('find_match', 'Mac Bul'),
            sub_text='3',
            color_code=UIColors.NEON_CYAN,
            state='hover' if find_hover else 'normal',
        )
        self._lobby_buttons.append({'rect': find_rect, 'action': 'find_match'})
        y_pos += btn_h + gap

        # Geri butonu
        y_pos += s(10)
        back_rect = pygame.Rect(btn_x, y_pos, btn_w, s(44))
        back_hover = back_rect.collidepoint(mouse_pos)
        _rs.draw_uniform_button(
            self.screen, back_rect,
            t('back_to_menu', 'Ana Menüye Dön'),
            sub_text='ESC',
            color_code=_rs.secondary,
            state='hover' if back_hover else 'normal',
        )
        self._lobby_buttons.append({'rect': back_rect, 'action': 'back'})

        # Sağ panel: Lobi listesi
        list_x = btn_x + btn_w + s(30)
        list_w = max(s(280), min(s(420), w - list_x - s(30)))
        list_y = btn_y_start
        list_h = h - list_y - s(60)

        list_panel = pygame.Rect(list_x, list_y, list_w, list_h)
        draw_glass_panel(self.screen, list_panel, alpha=165,
                         border_color=(80, 120, 180), glow=True)

        # Lobi listesi başlığı
        lt_font = _rs.get_font(s(20, minimum=14))
        list_title = lt_font.render(
            t('lobby_list_title', 'Mevcut Lobiler'), True, _rs.accent)
        title_rect = list_title.get_rect(center=(list_x + list_w // 2, list_y + s(24)))
        self.screen.blit(list_title, title_rect)

        sub_list_font = _rs.get_font(s(12, minimum=9), bold=False)
        subtitle_text = (
            t('lobby_list_subtitle_public', 'Sadece acik lobiler')
            if self._lobby_list_filter == 'public'
            else t('lobby_list_subtitle_all', 'Ozel ve acik lobiler')
        )
        sub_list_text = sub_list_font.render(
            subtitle_text,
            True, _rs.text_muted)
        subtitle_rect = sub_list_text.get_rect(
            center=(list_x + list_w // 2, title_rect.bottom + s(12)))
        self.screen.blit(sub_list_text, subtitle_rect)

        filter_y = subtitle_rect.bottom + s(10)
        filter_gap = s(10)
        filter_h = s(32)
        filter_x = list_x + s(16)
        filter_total_w = list_w - s(32)
        filter_w = max(s(120), (filter_total_w - filter_gap) // 2)
        all_rect = pygame.Rect(filter_x, filter_y, filter_w, filter_h)
        public_rect = pygame.Rect(
            all_rect.right + filter_gap,
            filter_y,
            filter_total_w - filter_w - filter_gap,
            filter_h,
        )
        all_hover = all_rect.collidepoint(mouse_pos)
        public_hover = public_rect.collidepoint(mouse_pos)
        all_active = self._lobby_list_filter == 'all'
        public_active = self._lobby_list_filter == 'public'
        _rs.draw_uniform_button(
            self.screen, all_rect,
            t('all_lobbies', 'Butun Lobiler'),
            color_code=UIColors.NEON_CYAN if all_active else _rs.secondary,
            state='hover' if all_active or all_hover else 'normal',
        )
        _rs.draw_uniform_button(
            self.screen, public_rect,
            t('public_lobbies', 'Acik Lobiler'),
            color_code=UIColors.NEON_GREEN if public_active else _rs.secondary,
            state='hover' if public_active or public_hover else 'normal',
        )
        self._lobby_buttons.append({'rect': all_rect, 'action': 'filter_all_lobbies'})
        self._lobby_buttons.append({'rect': public_rect, 'action': 'filter_public_lobbies'})

        debug_lobby_mode = self._is_online_pvp_trailer_debug_enabled()
        effective_lobby_list = self._get_lobby_entries_for_display()

        count_font = _rs.get_font(s(12, minimum=9), bold=False)
        count_text = count_font.render(str(len(effective_lobby_list)), True, _rs.text_primary)
        count_pad_x = s(10)
        count_pad_y = s(5)
        count_rect = pygame.Rect(
            list_panel.right - count_text.get_width() - count_pad_x * 2 - s(12),
            list_panel.y + s(12),
            count_text.get_width() + count_pad_x * 2,
            count_text.get_height() + count_pad_y * 2,
        )
        count_bg = pygame.Surface((count_rect.width, count_rect.height), pygame.SRCALPHA)
        pygame.draw.rect(count_bg, (*UIColors.NEON_CYAN[:3], 50), count_bg.get_rect(), border_radius=999)
        pygame.draw.rect(count_bg, (*UIColors.NEON_CYAN[:3], 120), count_bg.get_rect(), 1, border_radius=999)
        self.screen.blit(count_bg, count_rect.topleft)
        self.screen.blit(count_text, count_text.get_rect(center=count_rect.center))

        # Başlık altı çizgi
        header_bottom = max(subtitle_rect.bottom, count_rect.bottom, all_rect.bottom, public_rect.bottom)
        line_y = header_bottom + s(12)
        pygame.draw.line(self.screen, (*_rs.accent[:3], 60),
                         (list_x + s(12), line_y), (list_x + list_w - s(12), line_y), 1)

        content_top = line_y + s(14)

        if self._lobby_list_fetching and not debug_lobby_mode:
            dots = '.' * (int(time.time() * 2) % 4)
            f_txt = _rs.get_font(s(16, minimum=11), bold=False).render(
                t('searching', 'Aranıyor') + dots, True, _rs.text_secondary)
            self.screen.blit(f_txt, f_txt.get_rect(
                center=(list_x + list_w // 2, list_y + list_h // 2)))
        elif not effective_lobby_list:
            e_font = _rs.get_font(s(16, minimum=11), bold=False)
            e1 = render_text(e_font, t('no_lobbies_found', 'Lobi bulunamadı'), True, _rs.text_muted)
            if self._auto_lobby_refresh_requested:
                self.screen.blit(e1, e1.get_rect(center=(list_x + list_w // 2, list_y + list_h // 2)))
            else:
                e2 = _rs.get_font(s(14, minimum=10), bold=False).render(
                    t('press_find_match', '"Maç Bul" ile arayın'), True, _rs.text_muted)
                self.screen.blit(e1, e1.get_rect(center=(list_x + list_w // 2, list_y + list_h // 2 - s(10))))
                self.screen.blit(e2, e2.get_rect(center=(list_x + list_w // 2, list_y + list_h // 2 + s(14))))
        else:
            item_step = s(104)
            item_h = item_step - s(12)
            content_h = max(item_step, list_panel.bottom - content_top - s(22))
            visible = max(1, content_h // item_step)
            max_start = max(0, len(effective_lobby_list) - visible)
            start_idx = min(self._lobby_list_scroll, max_start)
            if start_idx != self._lobby_list_scroll:
                self._lobby_list_scroll = start_idx
            clip = pygame.Rect(list_x + 4, content_top, list_w - 8, content_h)
            self.screen.set_clip(clip)

            for i, lobby in enumerate(effective_lobby_list[start_idx:start_idx + visible]):
                iy = content_top + i * item_step
                ir = pygame.Rect(list_x + s(8), iy, list_w - s(16), item_h)
                hover = ir.collidepoint(mouse_pos)
                raw_requires_code = bool(lobby.get('requires_code', False))
                l_code = str(lobby.get('code', '') or '')
                raw_visibility = str(lobby.get('visibility', 'unknown') or 'unknown').lower()
                visibility, requires_code = _resolve_lobby_display_state(
                    raw_visibility,
                    raw_requires_code,
                    l_code,
                )
                if visibility in ('unknown', 'stale_unknown'):
                    accent_color = UIColors.NEON_ORANGE
                else:
                    accent_color = UIColors.NEON_ORANGE if requires_code else UIColors.NEON_GREEN
                bdr = accent_color if hover or requires_code or visibility in ('unknown', 'stale_unknown') else (*UIColors.NEON_GREEN[:3],)
                draw_glass_panel(self.screen, ir,
                                 alpha=205 if hover else 150, border_color=bdr, glow=hover)

                accent_bar = pygame.Rect(ir.x + s(6), ir.y + s(8), s(5), ir.height - s(16))
                pygame.draw.rect(self.screen, accent_color, accent_bar, border_radius=999)

                if hover:
                    hover_overlay = pygame.Surface((ir.width, ir.height), pygame.SRCALPHA)
                    pygame.draw.rect(hover_overlay, (*accent_color[:3], 20), hover_overlay.get_rect(), border_radius=12)
                    self.screen.blit(hover_overlay, ir.topleft)

                lname = lobby.get('name', f'Lobi #{i + start_idx + 1}')
                members = lobby.get('members', '?')
                mx = lobby.get('max_members', 2)
                lid = lobby.get('id', 0)
                try:
                    member_ratio = min(1.0, max(0.0, float(members) / max(1.0, float(mx))))
                except Exception:
                    member_ratio = 0.0

                # Lobi adı (host adı)
                nf = _rs.get_font(s(17, minimum=12))
                self.screen.blit(nf.render(lname, True, _rs.text_primary),
                                 (ir.x + s(20), ir.y + s(10)))

                badge_font = _rs.get_font(s(11, minimum=9), bold=False)
                badge_icon = None
                if visibility in ('unknown', 'stale_unknown'):
                    badge_text = t('lobby_label', 'Lobi')
                elif requires_code:
                    from emoji_renderer import emoji_surface

                    badge_text = t('private_lobby', 'Ozel Lobi')
                    badge_icon = emoji_surface('🔒', max(10, s(13, minimum=10)))
                else:
                    from emoji_renderer import emoji_surface

                    badge_text = t('open_lobby', 'Acik lobi')
                    badge_icon = emoji_surface('🔓', max(10, s(13, minimum=10)))
                badge_text_surf = badge_font.render(badge_text, True, accent_color)
                badge_gap = s(6) if badge_icon else 0
                badge_content_w = badge_text_surf.get_width() + (badge_icon.get_width() if badge_icon else 0) + badge_gap
                badge_rect = pygame.Rect(
                    ir.right - badge_content_w - s(30),
                    ir.y + s(8),
                    badge_content_w + s(16),
                    badge_text_surf.get_height() + s(8),
                )
                badge_surface = pygame.Surface((badge_rect.width, badge_rect.height), pygame.SRCALPHA)
                pygame.draw.rect(badge_surface, (*accent_color[:3], 40), badge_surface.get_rect(), border_radius=999)
                pygame.draw.rect(badge_surface, (*accent_color[:3], 130), badge_surface.get_rect(), 1, border_radius=999)
                self.screen.blit(badge_surface, badge_rect.topleft)
                if badge_icon:
                    content_left = badge_rect.x + s(8)
                    icon_rect = badge_icon.get_rect()
                    icon_rect.x = content_left
                    icon_rect.centery = badge_rect.centery
                    self.screen.blit(badge_icon, icon_rect)
                    text_rect = badge_text_surf.get_rect(midleft=(icon_rect.right + badge_gap, badge_rect.centery))
                else:
                    text_rect = badge_text_surf.get_rect(center=badge_rect.center)
                self.screen.blit(badge_text_surf, text_rect)

                # Detay satırı: üye sayısı + lobi kodu
                cf = _rs.get_font(s(12, minimum=9), bold=False)
                detail_parts = [f'{members}/{mx} oyuncu']
                if requires_code:
                    detail_parts.append(t('code_required', 'Katilmak icin kod gerekli'))
                elif visibility == 'public':
                    detail_parts.append(t('open_lobby', 'Acik lobi'))
                elif visibility in ('unknown', 'stale_unknown'):
                    detail_parts.append('Erisim ayarlari kontrol edilecek')
                detail_text = '  ·  '.join(detail_parts)
                self.screen.blit(cf.render(detail_text, True, _rs.text_secondary),
                                 (ir.x + s(20), ir.y + s(34)))

                # Zaman bilgisi
                found_t = lobby.get('found_time', 0)
                if found_t:
                    elapsed = int(time.time() - found_t)
                    if elapsed < 60:
                        time_str = t('just_now', 'Az önce')
                    else:
                        time_str = f'{elapsed // 60} dk önce'
                    tf2 = _rs.get_font(s(11, minimum=9), bold=False)
                    self.screen.blit(tf2.render(time_str, True, _rs.text_muted),
                                     (ir.x + s(20), ir.y + s(57)))

                # Katıl butonu — daha belirgin stil
                jw, jh = s(92), s(34)
                jb = pygame.Rect(ir.right - jw - s(12), ir.centery - jh // 2, jw, jh)
                jh_hover = jb.collidepoint(mouse_pos)
                if visibility in ('unknown', 'stale_unknown'):
                    action = f'resolve_lobby_join:{lid}'
                    button_label = t('join', 'Katıl')
                    button_color = UIColors.NEON_CYAN
                elif lobby.get('debug_lobby'):
                    action = 'debug_lobby'
                    button_label = t('demo_lobby', 'Demo')
                    button_color = UIColors.NEON_ORANGE if requires_code else UIColors.NEON_GREEN
                else:
                    action = f'join_private_lobby:{lid}' if requires_code else f'join_lobby:{lid}'
                    button_label = t('enter_code', 'Kod Gir') if requires_code else t('join', 'Katıl')
                    button_color = UIColors.NEON_ORANGE if requires_code else UIColors.NEON_GREEN
                _rs.draw_uniform_button(self.screen, jb,
                                        button_label,
                                        color_code=button_color,
                                        state='hover' if jh_hover else 'normal')
                if requires_code and action:
                    self._lobby_buttons.append({'rect': ir, 'action': action})
                if action:
                    self._lobby_buttons.append({'rect': jb, 'action': action})

                bar_rect = pygame.Rect(ir.x + s(102), ir.y + s(59), max(s(72), jb.x - ir.x - s(132)), s(8))
                pygame.draw.rect(self.screen, (35, 48, 76), bar_rect, border_radius=999)
                fill_rect = pygame.Rect(bar_rect.x, bar_rect.y, max(1, int(bar_rect.width * member_ratio)), bar_rect.height)
                pygame.draw.rect(self.screen, accent_color, fill_rect, border_radius=999)
                occupancy_text = cf.render(f'{members}/{mx}', True, _rs.text_secondary)
                self.screen.blit(occupancy_text, occupancy_text.get_rect(midleft=(bar_rect.right + s(8), bar_rect.centery)))

            self.screen.set_clip(None)

            if len(effective_lobby_list) > visible:
                sc_font = _rs.get_font(s(12, minimum=9), bold=False)
                sc_txt = sc_font.render(
                    f'{start_idx + 1}–{min(start_idx + visible, len(effective_lobby_list))}'
                    f' / {len(effective_lobby_list)}', True, _rs.text_muted)
                self.screen.blit(sc_txt, sc_txt.get_rect(
                    center=(list_x + list_w // 2, list_y + list_h - s(16))))

        # Durum mesajı (hata / bilgi)
        if self._status_msg:
            st_font = _rs.get_font(s(16, minimum=11), bold=False)
            st_surf = st_font.render(self._status_msg, True, UIColors.NEON_MAGENTA)
            self.screen.blit(st_surf, st_surf.get_rect(center=(cx, h - s(52))))

        # Alt bilgi — Steam ID
        info_font = _rs.get_font(s(13, minimum=10), bold=False)
        sid = self.net.my_steam_id or t('connecting', 'Bağlanılıyor...')
        info = info_font.render(f'Steam ID: {sid}', True, _rs.text_muted)
        self.screen.blit(info, info.get_rect(center=(cx, h - s(24))))

    def _draw_join_code_input(self, x, y, btn_w, s, mouse_pos):
        """Kod ile Katıl metin giriş panelini çiz."""
        # Cam panel: giriş alanı + gönder butonu
        panel_h = s(224)
        panel_r = pygame.Rect(x, y, btn_w, panel_h)
        panel_border = UIColors.NEON_RED if self._join_code_error else UIColors.NEON_CYAN
        draw_glass_panel(self.screen, panel_r, alpha=195,
                         border_color=panel_border, glow=True)

        # Başlık
        tf = _rs.get_font(s(18, minimum=12))
        title = render_text(tf, t('join_by_code', 'Kod ile Katıl'), True, UIColors.NEON_CYAN)
        self.screen.blit(title, title.get_rect(
            midleft=(x + s(16), y + s(20))))

        subf = _rs.get_font(s(12, minimum=9), bold=False)
        subtitle = render_text(subf, t('join_code_subtitle', 'Ozel lobiye girmek icin 6 haneli kodu yaz'), True, _rs.text_muted)
        self.screen.blit(subtitle, subtitle.get_rect(midleft=(x + s(16), y + s(41))))

        hint_f = _rs.get_font(s(11, minimum=9), bold=False)
        hint = render_text(hint_f, t('paste_code_hint', 'Yapistir: Ctrl+V  •  Kapat: ESC'), True, _rs.text_muted)
        self.screen.blit(hint, hint.get_rect(midright=(x + btn_w - s(16), y + s(20))))

        # Kod kutuları
        display_text = self._join_code_input[:6]
        slot_gap = s(8)
        slot_count = 6
        slot_w = min(s(44), (btn_w - s(32) - slot_gap * (slot_count - 1)) // slot_count)
        slot_h = s(50)
        total_slots_w = slot_count * slot_w + (slot_count - 1) * slot_gap
        slots_x = x + (btn_w - total_slots_w) // 2
        slots_y = y + s(68)
        slots_rect = pygame.Rect(slots_x, slots_y, total_slots_w, slot_h)

        for idx in range(slot_count):
            slot_x = slots_x + idx * (slot_w + slot_gap)
            slot_rect = pygame.Rect(slot_x, slots_y, slot_w, slot_h)
            is_filled = idx < len(display_text)
            is_active_slot = self._join_code_active and idx == min(len(display_text), slot_count - 1)
            slot_border = UIColors.NEON_RED if self._join_code_error else (UIColors.NEON_CYAN if is_active_slot else (*_rs.glass_border[:3],))
            slot_bg = pygame.Surface((slot_w, slot_h), pygame.SRCALPHA)
            pygame.draw.rect(slot_bg, (18, 22, 46, 230), slot_bg.get_rect(), border_radius=10)
            if is_filled:
                pygame.draw.rect(slot_bg, (*UIColors.NEON_GREEN[:3], 22), slot_bg.get_rect(), border_radius=10)
            self.screen.blit(slot_bg, slot_rect.topleft)
            pygame.draw.rect(self.screen, slot_border, slot_rect, 2, border_radius=10)

            if is_filled:
                char_font = _rs.get_font(s(24, minimum=16))
                char_surf = char_font.render(display_text[idx], True, _rs.text_primary)
                self.screen.blit(char_surf, char_surf.get_rect(center=slot_rect.center))
            else:
                dot_font = _rs.get_font(s(16, minimum=12), bold=False)
                dot_surf = render_text(dot_font, '•', True, _rs.text_muted)
                self.screen.blit(dot_surf, dot_surf.get_rect(center=slot_rect.center))

        if self._join_code_active and int(time.time() * 2.5) % 2 == 0 and len(display_text) < slot_count:
            cursor_slot_x = slots_x + len(display_text) * (slot_w + slot_gap)
            cursor_center_x = cursor_slot_x + slot_w // 2
            pygame.draw.line(self.screen, UIColors.NEON_CYAN,
                             (cursor_center_x, slots_y + s(12)),
                             (cursor_center_x, slots_y + slot_h - s(12)), 2)

        # Tıklanabilir alan olarak kaydet
        self._lobby_buttons.append({'rect': slots_rect, 'action': 'join_code_field'})

        helper_font = _rs.get_font(s(11, minimum=9), bold=False)
        helper_text = render_text(helper_font, t('join_code_helper', 'Her kutuya bir rakam gelecek sekilde 6 haneli kod gir'), True, _rs.text_secondary)
        self.screen.blit(helper_text, helper_text.get_rect(center=(x + btn_w // 2, slots_y + slot_h + s(14))))

        # Hata mesajı
        if self._join_code_error:
            ef = _rs.get_font(s(12, minimum=9), bold=False)
            err = ef.render(self._join_code_error, True, UIColors.NEON_RED)
            self.screen.blit(err, err.get_rect(center=(x + btn_w // 2, slots_y + slot_h + s(34))))

        # Gönder butonu
        sub_btn_w = btn_w - s(32)
        sub_btn_h = s(38)
        sub_y = y + panel_h - sub_btn_h - s(16)
        sub_rect = pygame.Rect(x + s(16), sub_y, sub_btn_w, sub_btn_h)
        sub_hover = sub_rect.collidepoint(mouse_pos)
        _rs.draw_uniform_button(self.screen, sub_rect,
                                t('join_lobby_by_code', 'Kodla Lobiye Katıl'),
                                sub_text='ENTER',
                                color_code=UIColors.NEON_GREEN,
                                state='hover' if sub_hover else 'normal')
        self._lobby_buttons.append({'rect': sub_rect, 'action': 'join_code_submit'})

    # ─── Bekleme Ekranı ───

    def _draw_waiting_screen(self):
        w, h = self.window_width, self.window_height
        cx, cy = w // 2, h // 2
        sc = self._ui_scale()
        s = lambda v, minimum=1: self._sx(v, sc, minimum)
        mouse_pos = get_mouse_pos()

        pw = min(s(520), w - s(80))
        ph = s(440)
        panel = pygame.Rect(cx - pw // 2, cy - ph // 2, pw, ph)
        draw_glass_panel(self.screen, panel, alpha=185,
                         border_color=UIColors.NEON_CYAN, glow=True)

        # Başlık
        tf = _rs.get_fitting_font(
            t('waiting_for_opponent', 'Rakip Bekleniyor...'), s(30), pw - s(60))
        title = render_text(tf, t('waiting_for_opponent', 'Rakip Bekleniyor...'),
                          True, UIColors.NEON_CYAN)
        self.screen.blit(title, title.get_rect(center=(cx, panel.y + s(40))))

        # Animasyonlu noktalar
        dots = '●' * (int(time.time() * 2) % 4) + '○' * (3 - int(time.time() * 2) % 4)
        df = _rs.get_font(s(20, minimum=14))
        dt = df.render(dots, True, _rs.text_secondary)
        self.screen.blit(dt, dt.get_rect(center=(cx, panel.y + s(75))))

        # ─── Lobi Kodu Bölümü (belirgin) ───
        code_section_y = panel.y + s(100)
        if self._lobby_code:
            # "Lobi Kodu" etiketi
            label_f = _rs.get_font(s(14, minimum=10), bold=False)
            label_s = render_text(label_f, t('lobby_code', 'Lobi Kodu'), True, _rs.text_secondary)
            self.screen.blit(label_s, label_s.get_rect(center=(cx, code_section_y)))

            # Büyük kod gösterimi (vurgulu)
            code_f = _rs.get_font(s(40, minimum=24))
            # Kodu okunabilir grupla: "482 917"
            display_code = self._lobby_code
            if len(display_code) == 6:
                display_code = f'{display_code[:3]}  {display_code[3:]}'
            code_surf = code_f.render(display_code, True, UIColors.NEON_GREEN)
            code_rect = code_surf.get_rect(center=(cx, code_section_y + s(35)))
            self.screen.blit(code_surf, code_rect)

            # Paylaşım ipucu
            hint_f = _rs.get_font(s(12, minimum=9), bold=False)
            hint = hint_f.render(
                t('lobby_code_hint', 'Bu kodu arkadaşınla paylaş!'),
                True, UIColors.NEON_MAGENTA)
            self.screen.blit(hint, hint.get_rect(center=(cx, code_section_y + s(62))))

            # Kodu Kopyala butonu (tek, ortalanmış)
            copy_w = s(200)
            copy_h = s(36)
            copy_rect = pygame.Rect(cx - copy_w // 2, code_section_y + s(78),
                                    copy_w, copy_h)
            copy_hover = copy_rect.collidepoint(mouse_pos)
            _rs.draw_uniform_button(self.screen, copy_rect,
                                    t('copy_code', 'Kodu Kopyala'),
                                    sub_text='C',
                                    color_code=UIColors.NEON_CYAN,
                                    state='hover' if copy_hover else 'normal')
            self._lobby_buttons.append({'rect': copy_rect, 'action': 'copy_lobby_code'})

            # Ayırıcı
            sep_y = code_section_y + s(122)
            or_f = _rs.get_font(s(13, minimum=10), bold=False)
            or_s = or_f.render(
                t('or_invite_steam', 'veya Steam\'den davet et'),
                True, _rs.text_muted)
            self.screen.blit(or_s, or_s.get_rect(center=(cx, sep_y)))
            pygame.draw.line(self.screen, (*_rs.text_muted[:3], 40),
                             (panel.x + s(20), sep_y),
                             (cx - or_s.get_width() // 2 - s(10), sep_y), 1)
            pygame.draw.line(self.screen, (*_rs.text_muted[:3], 40),
                             (cx + or_s.get_width() // 2 + s(10), sep_y),
                             (panel.right - s(20), sep_y), 1)

            btn_area_y = sep_y + s(16)
        else:
            btn_area_y = code_section_y + s(10)

        # Steam Davet butonu
        inv_w = s(260)
        inv_rect = pygame.Rect(cx - inv_w // 2, btn_area_y, inv_w, s(44))
        m_hover = inv_rect.collidepoint(mouse_pos)
        _rs.draw_uniform_button(self.screen, inv_rect,
                                t('invite_friend', 'Arkadaş Davet Et'),
                                sub_text='I', color_code=UIColors.NEON_GREEN,
                                state='hover' if m_hover else 'normal')
        self._lobby_buttons.append({'rect': inv_rect, 'action': 'invite_friend'})

        # Geri butonu
        back_rect = pygame.Rect(cx - inv_w // 2, btn_area_y + s(54), inv_w, s(38))
        m_back = back_rect.collidepoint(mouse_pos)
        _rs.draw_uniform_button(self.screen, back_rect,
                                t('back_to_pvp_area', 'PvP Alanına Geri Dön'),
                                sub_text='ESC', color_code=_rs.secondary,
                                state='hover' if m_back else 'normal')
        self._lobby_buttons.append({'rect': back_rect, 'action': 'back_to_pvp_lobby'})

        # Durum mesajı (geri bildirim)
        if self._status_msg:
            st_font = _rs.get_font(s(15, minimum=11), bold=False)
            st_surf = st_font.render(self._status_msg, True, UIColors.NEON_MAGENTA)
            self.screen.blit(st_surf, st_surf.get_rect(center=(cx, panel.bottom + s(18))))

    # ─── Hazırlanma Ekranı ───

    def _get_steam_avatar_surface(self, steam_id: int, size: int) -> pygame.Surface | None:
        """Steam profil fotoğrafını pygame Surface olarak al ve önbelleğe.

        Steam avatar yükleme async olabilir (image_handle == -1 = loading).
        Bu nedenle başarısız sonuçlar kalıcı cache'lenmez — belirli sayıda
        (max 10) yeniden deneme yapılır. Başarılı sonuçlar kalıcı olarak cache'lenir.
        """
        if not hasattr(self, '_avatar_cache'):
            self._avatar_cache: dict[tuple[int, int], pygame.Surface] = {}
        if not hasattr(self, '_avatar_retry_count'):
            self._avatar_retry_count: dict[tuple[int, int], int] = {}
        cache_key = (steam_id, size)
        if cache_key in self._avatar_cache:
            return self._avatar_cache[cache_key]
        # Retry limiti — çok fazla API çağrısı yapılmasını önle
        retries = self._avatar_retry_count.get(cache_key, 0)
        if retries >= 10:
            return None  # Kalıcı olarak bulunamadı
        try:
            from steam_integration import get_avatar_rgba
            rgba = get_avatar_rgba(steam_id, preferred='medium')
            if rgba:
                aw, ah, argba = rgba
                source = pygame.image.frombuffer(bytearray(argba), (aw, ah), 'RGBA').convert_alpha()
                scaled = pygame.transform.smoothscale(source, (size, size))
                # Yuvarlak kırpma
                circle_surf = pygame.Surface((size, size), pygame.SRCALPHA)
                pygame.draw.circle(circle_surf, (255, 255, 255, 255),
                                   (size // 2, size // 2), size // 2)
                scaled.blit(circle_surf, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
                self._avatar_cache[cache_key] = scaled
                return scaled
        except Exception:
            pass
        # Başarısız — cache'leme, retry sayacını artır (sonraki frame tekrar dener)
        self._avatar_retry_count[cache_key] = retries + 1
        return None

    def _draw_ready_check(self):
        w, h = self.window_width, self.window_height
        cx, cy = w // 2, h // 2
        sc = self._ui_scale()
        s = lambda v, minimum=1: self._sx(v, sc, minimum)

        pw = min(s(650), w - s(80))
        ph = s(420)
        panel = pygame.Rect(cx - pw // 2, cy - ph // 2, pw, ph)
        draw_glass_panel(self.screen, panel, alpha=185,
                         border_color=UIColors.NEON_CYAN, glow=True)

        # VS başlık — büyük glow efektli
        vs_font = _rs.get_font(s(56, minimum=32))
        vs = render_text(vs_font, 'VS', True, UIColors.NEON_MAGENTA)
        # Glow
        for offset in (3, 2, 1):
            glow_s = pygame.Surface(vs.get_size(), pygame.SRCALPHA)
            glow_s.fill((*UIColors.NEON_MAGENTA[:3], 20))
            glow_s.blit(vs, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            self.screen.blit(glow_s, glow_s.get_rect(center=(cx + offset, panel.y + s(45) + offset)))
        self.screen.blit(vs, vs.get_rect(center=(cx, panel.y + s(45))))

        # Oyuncu isimleri ve avatarları
        my_name = self.net._get_name(self.net.my_steam_id) if self.net.my_steam_id else 'Sen'
        opp_name = self.net.opponent_name or t('opponent', 'Rakip')

        col_w = pw // 2 - s(20)
        my_cx = panel.x + col_w // 2 + s(10)
        opp_cx = panel.right - col_w // 2 - s(10)

        # Avatar çerçeveleri
        avatar_size = s(64, minimum=40)
        avatar_y = panel.y + s(90)

        # Kendi avatarım
        my_avatar = self._get_steam_avatar_surface(
            self.net.my_steam_id or 0, avatar_size)
        my_accent = UIColors.NEON_CYAN
        my_border_color = UIColors.NEON_GREEN if self.my_ready else my_accent
        # Avatar çerçeve paneli
        av_frame = pygame.Rect(my_cx - avatar_size // 2 - s(4), avatar_y - s(4),
                               avatar_size + s(8), avatar_size + s(8))
        draw_glass_panel(self.screen, av_frame, alpha=160, border_color=my_border_color)
        if my_avatar:
            self.screen.blit(my_avatar, (my_cx - avatar_size // 2, avatar_y))
        else:
            # Placeholder
            pygame.draw.circle(self.screen, (*my_accent[:3], 80),
                               (my_cx, avatar_y + avatar_size // 2), avatar_size // 2)
            pf = _rs.get_font(s(24, minimum=16))
            pt = render_text(pf, '?', True, my_accent)
            self.screen.blit(pt, pt.get_rect(center=(my_cx, avatar_y + avatar_size // 2)))

        # Rakip avatarı
        opp_avatar = self._get_steam_avatar_surface(
            self.net.opponent_steam_id or 0, avatar_size)
        opp_accent = UIColors.NEON_MAGENTA
        opp_border_color = UIColors.NEON_GREEN if self.opponent_ready else opp_accent
        av_frame2 = pygame.Rect(opp_cx - avatar_size // 2 - s(4), avatar_y - s(4),
                                avatar_size + s(8), avatar_size + s(8))
        draw_glass_panel(self.screen, av_frame2, alpha=160, border_color=opp_border_color)
        if opp_avatar:
            self.screen.blit(opp_avatar, (opp_cx - avatar_size // 2, avatar_y))
        else:
            pygame.draw.circle(self.screen, (*opp_accent[:3], 80),
                               (opp_cx, avatar_y + avatar_size // 2), avatar_size // 2)
            pf = _rs.get_font(s(24, minimum=16))
            pt = render_text(pf, '?', True, opp_accent)
            self.screen.blit(pt, pt.get_rect(center=(opp_cx, avatar_y + avatar_size // 2)))

        # İsimler — avatarların altında
        name_y = avatar_y + avatar_size + s(14)
        nf = _rs.get_font(s(20, minimum=14))

        my_color = UIColors.NEON_GREEN if self.my_ready else _rs.text_primary
        opp_color = UIColors.NEON_GREEN if self.opponent_ready else _rs.text_primary

        my_s = nf.render(my_name, True, my_color)
        opp_s = nf.render(opp_name, True, opp_color)
        self.screen.blit(my_s, my_s.get_rect(center=(my_cx, name_y)))
        self.screen.blit(opp_s, opp_s.get_rect(center=(opp_cx, name_y)))

        # Hazır durumu göstergesi — ismin altında badge
        status_y = name_y + s(24)
        status_font = _rs.get_font(s(14, minimum=10), bold=False)
        if self.my_ready:
            ready_badge = pygame.Rect(my_cx - s(50), status_y, s(100), s(24))
            draw_glass_panel(self.screen, ready_badge, alpha=180,
                             border_color=UIColors.NEON_GREEN)
            rt = render_text(status_font, t('campaign_status_ready', 'READY'), True, UIColors.NEON_GREEN)
            self.screen.blit(rt, rt.get_rect(center=ready_badge.center))
        else:
            wt = render_text(status_font, t('not_ready', 'Bekleniyor...'), True, _rs.text_muted)
            self.screen.blit(wt, wt.get_rect(center=(my_cx, status_y + s(12))))

        if self.opponent_ready:
            ready_badge2 = pygame.Rect(opp_cx - s(50), status_y, s(100), s(24))
            draw_glass_panel(self.screen, ready_badge2, alpha=180,
                             border_color=UIColors.NEON_GREEN)
            rt2 = render_text(status_font, t('campaign_status_ready', 'READY'), True, UIColors.NEON_GREEN)
            self.screen.blit(rt2, rt2.get_rect(center=ready_badge2.center))
        else:
            wt2 = render_text(status_font, t('not_ready', 'Bekleniyor...'), True, _rs.text_muted)
            self.screen.blit(wt2, wt2.get_rect(center=(opp_cx, status_y + s(12))))

        # Dikey ayırıcı çizgi
        sep_top = panel.y + s(80)
        sep_bot = status_y + s(30)
        pygame.draw.line(self.screen, (*UIColors.NEON_MAGENTA[:3], 60),
                         (cx, sep_top), (cx, sep_bot), 2)

        # Alt buton — Hazırım
        if not self.my_ready:
            btn_r = pygame.Rect(cx - s(130), panel.y + s(290), s(260), s(50))
            m_h = btn_r.collidepoint(get_mouse_pos())
            _rs.draw_uniform_button(self.screen, btn_r,
                                    t('press_enter_ready', 'Hazırım!'),
                                    sub_text='ENTER', color_code=UIColors.NEON_GREEN,
                                    state='hover' if m_h else 'normal')
            self._lobby_buttons.append({'rect': btn_r, 'action': 'ready'})
        else:
            # "Hazır" onay badge
            wf = _rs.get_font(s(16, minimum=12), bold=False)
            wait_rect = pygame.Rect(cx - s(100), panel.y + s(295), s(200), s(36))
            draw_glass_panel(self.screen, wait_rect, alpha=150,
                             border_color=UIColors.NEON_GREEN)
            wt = render_text(wf, t('waiting_opponent_ready', 'Rakip bekleniyor...'),
                           True, UIColors.NEON_GREEN)
            self.screen.blit(wt, wt.get_rect(center=wait_rect.center))

        # ESC — tıklanabilir geri butonu
        esc_w = s(200)
        esc_h = s(36)
        esc_rect = pygame.Rect(cx - esc_w // 2, panel.bottom - s(48), esc_w, esc_h)
        m_esc = esc_rect.collidepoint(get_mouse_pos())
        _rs.draw_uniform_button(self.screen, esc_rect,
                                t('back_to_menu', 'Ana Menüye Dön'),
                                sub_text='ESC', color_code=_rs.secondary,
                                state='hover' if m_esc else 'normal')
        self._lobby_buttons.append({'rect': esc_rect, 'action': 'exit_menu'})

    # ─── Geri Sayım ───

    def _draw_countdown(self):
        w, h = self.window_width, self.window_height
        cx, cy = w // 2, h // 2
        sc = self._ui_scale()
        s = lambda v, minimum=1: self._sx(v, sc, minimum)

        # Arka plan paneli
        r = s(100)
        bg = pygame.Rect(cx - r, cy - r, r * 2, r * 2)
        draw_glass_panel(self.screen, bg, alpha=150,
                         border_color=UIColors.NEON_CYAN, glow=True)

        if self.countdown_value > 0:
            big_font = _rs.get_font(s(100, minimum=48))
            txt = big_font.render(str(self.countdown_value), True, UIColors.NEON_CYAN)
        else:
            big_font = _rs.get_font(s(72, minimum=36))
            txt = render_text(big_font, 'GO!', True, UIColors.NEON_GREEN)

        # Glow efekti (3 geçiş)
        for offset in (4, 2):
            glow_color = (*UIColors.NEON_CYAN[:3], 25)
            gs = pygame.Surface(txt.get_size(), pygame.SRCALPHA)
            gs.fill(glow_color)
            gs.blit(txt, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            self.screen.blit(gs, gs.get_rect(center=(cx, cy + offset)))

        self.screen.blit(txt, txt.get_rect(center=(cx, cy)))

    # ─── Oyun Çizimi ───

    def _draw_game(self):
        """İki tahtayı + header + skor + VS paneli — pvp_game tarzında çiz."""
        w, h = self.window_width, self.window_height
        sc = self._ui_scale()
        s = lambda v, minimum=1: self._sx(v, sc, minimum)
        shake_x, shake_y = self.get_shake_offset()

        # Layout hesapla
        cell_size = min((h - s(180)) // BOARD_HEIGHT, (w - s(260)) // (BOARD_WIDTH * 2 + 8))
        cell_size = max(s(14), min(cell_size, s(36)))
        self.cell_size = cell_size  # update() sweep animasyonu için sakla
        board_w = BOARD_WIDTH * cell_size
        board_h = BOARD_HEIGHT * cell_size
        mini_cell = max(s(10), cell_size - 4)
        side_panel_w = mini_cell * 5 + s(24)
        gap = s(110)
        header_h = s(56)
        total = board_w * 2 + gap + side_panel_w
        start_x = max(s(10), (w - total) // 2)
        start_x += shake_x

        # Y pozisyonları — header dahil
        header_y = max(s(16), (h - board_h - header_h - s(60)) // 2)
        header_y += shake_y
        board_top = header_y + header_h + s(10)

        # ─ Sol yan panel: Hold + Next ─
        panel_x = start_x
        self._draw_side_panel(panel_x, board_top, cell_size)

        # ─ Sol tahta (ben) ─
        my_x = start_x + side_panel_w + s(10)
        opp_x = my_x + board_w + gap
        self._my_board_rect = pygame.Rect(my_x, board_top, board_w, board_h)
        self._opp_board_rect = pygame.Rect(opp_x, board_top, board_w, board_h)
        self._draw_board(my_x, board_top, cell_size, self.my_board, self.my_piece)

        # Ghost piece
        if self.my_board and self.my_piece and not self.game_over:
            ghost_y = self._get_ghost_y()
            if ghost_y != self.my_piece.y:
                self._draw_ghost_piece(my_x, board_top, cell_size, ghost_y)

        # ─ Sağ tahta (rakip) ─
        self._draw_opponent_board(opp_x, board_top, cell_size)

        # ─ Combo mesajı (DOUBLE/TRIPLE/QUADRIX) ─
        if self.my_combo_message_time > 0 and self.my_combo_message:
            alpha = get_combo_popup_alpha(self.my_combo_message_time)
            msg_cx = my_x + board_w // 2
            msg_cy = board_top + board_h // 3
            msg_font = _rs.get_font(s(28, minimum=18), bold=True)
            shadow = msg_font.render(self.my_combo_message, True, COMBO_POPUP_SHADOW_COLOR)
            if alpha < 255:
                shadow.set_alpha(alpha)
            self.screen.blit(shadow, shadow.get_rect(center=(msg_cx + 2, msg_cy + 2)))
            color = get_combo_popup_color(self.my_combo_message)
            txt = msg_font.render(self.my_combo_message, True, color)
            if alpha < 255:
                txt.set_alpha(alpha)
            self.screen.blit(txt, txt.get_rect(center=(msg_cx, msg_cy)))

        # ─ Header paneller (pvp_game stili) ─
        my_name = self.net._get_name(self.net.my_steam_id) if self.net.my_steam_id else 'Sen'
        opp_name = self.net.opponent_name or t('opponent', 'Rakip')

        my_score = self.my_board.score if self.my_board else 0
        my_lines = self.my_board.lines_cleared if self.my_board else 0

        my_header = pygame.Rect(my_x, header_y, board_w, header_h)
        opp_header = pygame.Rect(opp_x, header_y, board_w, header_h)

        self._draw_player_header(my_header, my_name, UIColors.NEON_CYAN,
                                 my_score, my_lines, 'WASD')
        self._draw_player_header(opp_header, opp_name, UIColors.NEON_MAGENTA,
                                 self.opponent_score, self.opponent_lines, '')

        # ─ Orta VS paneli ─
        vs_x = my_x + board_w + s(8)
        vs_w = gap - s(16)
        vs_rect = pygame.Rect(vs_x, board_top, vs_w, board_h)
        draw_glass_panel(self.screen, vs_rect, alpha=130,
                         border_color=UIColors.NEON_MAGENTA, glow=True)

        vs_font = _rs.get_font(s(38, minimum=20))
        vs_text = render_text(vs_font, 'VS', True, UIColors.NEON_MAGENTA)
        self.screen.blit(vs_text, vs_text.get_rect(center=vs_rect.center))

        # Pending garbage göstergesi (Online garbage açıksa görünür)
        if ONLINE_PVP_GARBAGE_ENABLED and self.pending_garbage > 0:
            gb_h = min(self.pending_garbage * cell_size, board_h)
            gb_rect = pygame.Rect(my_x - s(10), board_top + board_h - gb_h, s(6), gb_h)
            pygame.draw.rect(self.screen, UIColors.NEON_RED, gb_rect, border_radius=3)
            gb_font = _rs.get_font(s(13, minimum=10))
            gb_txt = gb_font.render(str(self.pending_garbage), True, UIColors.NEON_RED)
            self.screen.blit(gb_txt, gb_txt.get_rect(
                center=(my_x - s(10) + s(3), board_top + board_h - gb_h - s(10))))

        # Pause overlay
        if self.paused or self.opponent_paused:
            self._draw_pause_overlay()

    # ── Oyuncu Başlık Paneli (pvp_game.py stili) ────────────────

    def _draw_player_header(self, rect, name, accent_color, score, lines, controls_label):
        """Başlık paneli: cam panel + accent underline + isim/skor."""
        draw_glass_panel(self.screen, rect, alpha=190, border_color=accent_color)
        pygame.draw.rect(self.screen, (*accent_color[:3], 120),
                         rect, 2, border_radius=12)

        # Accent alt çizgi
        underline = pygame.Rect(rect.x + 14, rect.bottom - 5, rect.width - 28, 3)
        pygame.draw.rect(self.screen, accent_color, underline, border_radius=2)

        # İsim
        sc = self._ui_scale()
        nf = _rs.get_fitting_font(name, self._sx(22, sc, 14), rect.width - 120)
        ns = nf.render(name, True, accent_color)
        self.screen.blit(ns, ns.get_rect(midleft=(rect.x + 16, rect.centery - 8)))

        # Skor / satır (sağda)
        sf = _rs.get_font(self._sx(14, sc, 10), bold=False)
        sc_s = sf.render(f'{t("score", "Skor")} {score:,}'.replace(',', '.'),
                         True, _rs.text_primary)
        ln_s = sf.render(f'{t("lines", "Satır")} {lines}', True, _rs.text_primary)
        self.screen.blit(sc_s, sc_s.get_rect(midright=(rect.right - 16, rect.centery - 10)))
        self.screen.blit(ln_s, ln_s.get_rect(midright=(rect.right - 16, rect.centery + 10)))

        # Kontrol etiketi
        if controls_label:
            cf = _rs.get_font(self._sx(12, sc, 9), bold=False)
            cs = cf.render(controls_label, True, _rs.text_muted)
            self.screen.blit(cs, cs.get_rect(bottomleft=(rect.x + 16, rect.bottom - 8)))

    # ── Yardımcı draw metotları ──────────────────────────────────

    def _draw_ghost_piece(self, board_x, board_y, cell_size, ghost_y):
        """Aktif parçanın iniş gölgesini yarı saydam çiz."""
        if not self.my_piece:
            return
        shape = self.my_piece.get_shape()
        ghost_surf = pygame.Surface((cell_size - 2, cell_size - 2), pygame.SRCALPHA)
        ghost_color = (*self.my_piece.color[:3], 60)
        ghost_surf.fill(ghost_color)
        for row_i, row in enumerate(shape):
            for col_i, cell in enumerate(row):
                if cell:
                    gy = ghost_y + row_i
                    gx = self.my_piece.x + col_i
                    if 0 <= gy < BOARD_HEIGHT and 0 <= gx < BOARD_WIDTH:
                        px = board_x + gx * cell_size + 1
                        py = board_y + gy * cell_size + 1
                        self.screen.blit(ghost_surf, (px, py))
                        pygame.draw.rect(self.screen, (*self.my_piece.color[:3], 90),
                                         (px, py, cell_size - 2, cell_size - 2), 1,
                                         border_radius=3)

    def _draw_side_panel(self, panel_x, panel_y, cell_size):
        """Hold ve Next parçalarını gösteren sol yan panel."""
        sc = self._ui_scale()
        s = lambda v, minimum=1: self._sx(v, sc, minimum)
        mini = max(s(10), cell_size - 4)
        pw = mini * 5 + s(24)

        def _draw_panel_label(label_text: str, panel_rect: pygame.Rect) -> int:
            max_width = max(s(18), panel_rect.width - s(14))
            base_size = s(15, minimum=10)
            min_size = s(8, minimum=8)
            text = str(label_text or '').strip() or '-'

            font = _rs.get_fitting_font(text, base_size, max_width, bold=True, min_size=min_size)
            if font.size(text)[0] > max_width:
                compact = text.rstrip(':').strip() or text
                if compact != text and font.size(compact)[0] <= max_width:
                    text = compact
                else:
                    trimmed = compact
                    while trimmed and font.size(trimmed + '...')[0] > max_width:
                        trimmed = trimmed[:-1].rstrip()
                    if trimmed:
                        text = trimmed + '...'
                    elif font.size('...')[0] <= max_width:
                        text = '...'
                    else:
                        text = ''

            label = font.render(text, True, UIColors.NEON_CYAN)
            top_y = panel_rect.top + s(6)
            self.screen.blit(label, label.get_rect(centerx=panel_rect.centerx, top=top_y))
            return top_y + label.get_height()

        # Hold
        hold_h = mini * 5 + s(40)
        hold_rect = pygame.Rect(panel_x, panel_y, pw, hold_h)
        draw_glass_panel(self.screen, hold_rect, alpha=150,
                         border_color=UIColors.NEON_CYAN)
        hold_label_bottom = _draw_panel_label(t('hold', 'Hold'), hold_rect)

        if self.hold_piece:
            self._draw_mini_piece(self.hold_piece, hold_rect.centerx,
                                  hold_label_bottom + s(6), mini)
        elif self.hold_used:
            lock_f = _rs.get_font(s(16, minimum=11))
            lk = render_text(lock_f, 'X', True, _rs.text_muted)
            self.screen.blit(lk, lk.get_rect(center=(hold_rect.centerx,
                                                       hold_label_bottom + s(24))))

        # Next
        next_y = hold_rect.bottom + s(12)
        next_rect = pygame.Rect(panel_x, next_y, pw, hold_h)
        draw_glass_panel(self.screen, next_rect, alpha=150,
                         border_color=UIColors.NEON_CYAN)
        next_label_bottom = _draw_panel_label(t('next', 'Sonraki'), next_rect)
        if self.next_piece:
            self._draw_mini_piece(self.next_piece, next_rect.centerx,
                                  next_label_bottom + s(6), mini)

    def _draw_mini_piece(self, piece, cx, top_y, mini):
        """Bir parçayı küçük boyutta ortalanmış çiz (hold/next için)."""
        shape = piece.get_shape() if hasattr(piece, 'get_shape') else piece.shape
        rows = len(shape)
        cols = len(shape[0]) if rows else 0
        ox = cx - (cols * mini) // 2
        oy = top_y
        piece_texture = getattr(piece, 'texture_surface', None)
        for ri, row in enumerate(shape):
            for ci, cell in enumerate(row):
                if cell:
                    draw_color = piece.color[:3]
                    color_matrix = getattr(piece, 'color_matrix', None)
                    if color_matrix is not None:
                        try:
                            matrix_color = color_matrix[ri][ci]
                            if matrix_color is not None:
                                draw_color = matrix_color[:3]
                        except Exception:
                            pass
                    slice_info = self._make_texture_slice(piece, ci, ri, cols, rows)
                    self.draw_textured_block(
                        ox + ci * mini + 1,
                        oy + ri * mini + 1,
                        mini - 2,
                        draw_color,
                        piece_texture,
                        slice_info,
                    )

    def _draw_pause_overlay(self):
        """Duraklatma ekranı — pvp_game standardında (alpha=185 + cam panel)."""
        w, h = self.window_width, self.window_height
        cx, cy = w // 2, h // 2
        sc = self._ui_scale()
        s = lambda v, minimum=1: self._sx(v, sc, minimum)

        overlay = pygame.Surface((w, h), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 185))
        self.screen.blit(overlay, (0, 0))

        pw = min(s(420), w - s(80))
        ph = s(200)
        panel = pygame.Rect(cx - pw // 2, cy - ph // 2, pw, ph)

        if self.paused:
            msg = t('paused', 'Duraklatıldı')
            sub = t('press_esc_resume', 'Devam etmek için ESC')
            accent = _rs.accent
        else:
            msg = t('opponent_paused', 'Rakip Duraklatıldı')
            sub = t('waiting', 'Bekleniyor...')
            accent = UIColors.NEON_ORANGE

        draw_glass_panel(self.screen, panel, alpha=190,
                         border_color=accent, glow=True)

        tf = _rs.get_fitting_font(msg, s(30), pw - s(40))
        ts = tf.render(msg, True, accent)
        self.screen.blit(ts, ts.get_rect(center=(cx, cy - s(20))))

        sf = _rs.get_font(s(16, minimum=12), bold=False)
        ss = sf.render(sub, True, _rs.text_secondary)
        self.screen.blit(ss, ss.get_rect(center=(cx, cy + s(24))))

    # ── Board çizim ──────────────────────────────────────────────

    def _draw_board(self, x: int, y: int, cell_size: int,
                    board: Board | None, piece: Piece | None):
        """Kendi tahtamızı modern oyun alanı render zinciri ile çiz."""
        if not board:
            return

        board_w = BOARD_WIDTH * cell_size
        board_h = BOARD_HEIGHT * cell_size
        player_accent = UIColors.NEON_CYAN
        board_rect = pygame.Rect(x, y, board_w, board_h)
        skin = self.mode_skin

        bg_rect = pygame.Rect(x - 2, y - 2, board_w + 4, board_h + 4)
        draw_glass_panel(self.screen, bg_rect, alpha=170, border_color=player_accent)
        pygame.draw.rect(self.screen, (6, 6, 16), board_rect)
        self.board_background.draw(self.screen, (x, y, board_w, board_h))
        apply_board_tint(self.screen, board_rect, skin)
        self.screen.blit(self._get_board_accent_overlay(board_w, board_h, player_accent, 18), (x, y))
        draw_board_overlay(self.screen, board_rect, skin)
        self.screen.blit(self._get_board_grid_surface(cell_size), (x, y))

        for row in range(BOARD_HEIGHT):
            for col in range(BOARD_WIDTH):
                if not board.occupancy[row][col]:
                    continue
                color = board.grid[row][col]
                locked_slice = board.texture_grid[row][col] if hasattr(board, 'texture_grid') else None
                texture_surface = None
                texture_slice = None
                if locked_slice and self.block_style_manager:
                    texture_surface = self.block_style_manager.get_texture_surface(locked_slice.piece_name)
                    texture_slice = locked_slice if texture_surface else None
                self.draw_textured_block(
                    x + col * cell_size + 1,
                    y + row * cell_size + 1 + self._get_block_fall_offset(row, col, is_opponent=False),
                    cell_size - 2,
                    color[:3],
                    texture_surface,
                    texture_slice,
                )

        if self.effects_enabled and self.drop_trails:
            self._draw_drop_trails()

        if piece:
            shape = piece.get_shape()
            piece_texture = getattr(piece, 'texture_surface', None)
            piece_height = len(shape)
            piece_width = len(shape[0]) if piece_height else 1
            for row_i, row in enumerate(shape):
                for col_i, cell in enumerate(row):
                    if cell:
                        px = x + (piece.x + col_i) * cell_size
                        py = y + (piece.y + row_i) * cell_size
                        if 0 <= piece.y + row_i < BOARD_HEIGHT:
                            draw_color = piece.color[:3]
                            color_matrix = getattr(piece, 'color_matrix', None)
                            if color_matrix is not None:
                                try:
                                    matrix_color = color_matrix[row_i][col_i]
                                    if matrix_color is not None:
                                        draw_color = matrix_color[:3]
                                except Exception:
                                    pass
                            slice_info = self._make_texture_slice(piece, col_i, row_i, piece_width, piece_height)
                            self.draw_textured_block(
                                px + 1,
                                py + 1,
                                cell_size - 2,
                                draw_color,
                                piece_texture,
                                slice_info,
                            )

        if self.my_line_sweep_rows and self.my_line_sweep_active:
            progress = self.my_line_sweep_progress
            valid_rows = sorted({r for r in self.my_line_sweep_rows if 0 <= r < BOARD_HEIGHT})
            if valid_rows:
                cleared_count = max(1, len(valid_rows))
                if cleared_count >= 4:
                    sw_blocks = 2
                elif cleared_count >= 3:
                    sw_blocks = 3
                elif cleared_count == 2:
                    sw_blocks = 2
                else:
                    sw_blocks = 1
                sweep_width = max(1, int(sw_blocks * cell_size))
                top_row = valid_rows[0]
                bottom_row = valid_rows[-1]
                group_y = y + top_row * cell_size
                group_h = max(cell_size, (bottom_row - top_row + 1) * cell_size)
                phase = (pygame.time.get_ticks() // 80) % 8
                sweep_x = x + int(progress * (board_w + sweep_width)) - sweep_width
                board_group_rect = pygame.Rect(x, group_y, board_w, group_h)
                if self._safe_draw_rainbow_cat_sweep(board_group_rect, sweep_x, sweep_width, phase, is_opponent=False):
                    glow_a = int(70 * (1.0 - progress * 0.4))
                    if glow_a > 0:
                        glow_w = min(sweep_width, int(board_w))
                        glow_x = max(x, sweep_x)
                        if glow_w > 0:
                            for row in valid_rows:
                                row_y = y + row * cell_size
                                glow_surface = self._effect_surface_cache.get_filled_surface((glow_w, cell_size), (255, 255, 255, glow_a))
                                self.screen.blit(glow_surface, (glow_x, row_y))

        if self.my_line_flash_rows and self.my_line_glow_alpha > 0:
            self._draw_line_clear_flash_overlay(x, y, board_w, cell_size, self.my_line_flash_rows, self.my_line_glow_alpha)

        for wave in self.my_wave_effects:
            radius = int(wave.get('radius', 0))
            alpha = max(0, min(255, int(wave.get('alpha', 0))))
            if radius <= 0 or alpha <= 0:
                continue
            wave_surface = self._effect_surface_cache.get_ellipse_surface(
                (radius * 2 + 6, 6),
                (*wave.get('color', (255, 255, 255))[:3], alpha),
            )
            wave_x = int(wave['x'] - radius)
            wave_y = int(wave['y'] - 3)
            self.screen.blit(wave_surface, (wave_x, wave_y))

        pygame.draw.rect(self.screen, player_accent, board_rect, 2, border_radius=14)

    def _draw_opponent_board(self, x: int, y: int, cell_size: int):
        """Ağdan gelen snapshot ile rakip tahtasını modern zincirle çiz."""
        board_w = BOARD_WIDTH * cell_size
        board_h = BOARD_HEIGHT * cell_size
        player_accent = UIColors.NEON_MAGENTA
        board_rect = pygame.Rect(x, y, board_w, board_h)
        skin = self.mode_skin

        if self._pending_opp_particle_rows:
            self._safe_trigger_line_clear_feedback(
                list(self._pending_opp_particle_rows),
                x,
                y,
                cell_size,
                board=None,
                is_opponent=True,
            )
            self._pending_opp_particle_rows = []

        bg_rect = pygame.Rect(x - 2, y - 2, board_w + 4, board_h + 4)
        draw_glass_panel(self.screen, bg_rect, alpha=170, border_color=player_accent)
        pygame.draw.rect(self.screen, (6, 6, 16), board_rect)
        self.board_background.draw(self.screen, (x, y, board_w, board_h))
        apply_board_tint(self.screen, board_rect, skin)
        self.screen.blit(self._get_board_accent_overlay(board_w, board_h, player_accent, 18), (x, y))
        draw_board_overlay(self.screen, board_rect, skin)
        self.screen.blit(self._get_board_grid_surface(cell_size), (x, y))

        if self.opponent_grid_snapshot:
            for row in range(min(BOARD_HEIGHT, len(self.opponent_grid_snapshot))):
                for col in range(min(BOARD_WIDTH, len(self.opponent_grid_snapshot[row]))):
                    cell = self.opponent_grid_snapshot[row][col]
                    if cell is not None:
                        color = tuple(cell) if isinstance(cell, (list, tuple)) else (128, 128, 128)
                        self.draw_textured_block(
                            x + col * cell_size + 1,
                            y + row * cell_size + 1 + self._get_block_fall_offset(row, col, is_opponent=True),
                            cell_size - 2,
                            color[:3],
                        )

        opponent_piece_state = self._get_opponent_piece_draw_state()
        if opponent_piece_state:
            try:
                si = int(opponent_piece_state.get('si', -1))
            except (TypeError, ValueError):
                si = -1
            px = float(opponent_piece_state.get('x', 0.0) or 0.0)
            py = float(opponent_piece_state.get('y', 0.0) or 0.0)
            rot = int(opponent_piece_state.get('r', 0) or 0) % 4
            cache = self._get_cached_opponent_piece_render(si, rot)
            if isinstance(cache, dict):
                temp = cache.get('piece')
                shape = cache.get('shape') or []
                piece_texture = cache.get('texture')
                piece_height = int(cache.get('height', len(shape)) or len(shape))
                piece_width = int(cache.get('width', len(shape[0]) if shape else 1) or 1)
                color_matrix = cache.get('color_matrix')
                for ri, row_data in enumerate(shape):
                    for ci, cell in enumerate(row_data):
                        if cell:
                            draw_row = py + ri
                            draw_col = px + ci
                            if 0 <= draw_row < BOARD_HEIGHT and 0 <= draw_col < BOARD_WIDTH:
                                bx = int(round(x + draw_col * cell_size))
                                by = int(round(y + draw_row * cell_size))
                                draw_color = temp.color[:3] if temp is not None else (255, 255, 255)
                                if color_matrix is not None:
                                    try:
                                        matrix_color = color_matrix[ri][ci]
                                        if matrix_color is not None:
                                            draw_color = matrix_color[:3]
                                    except Exception:
                                        pass
                                slice_info = self._make_texture_slice(temp, ci, ri, piece_width, piece_height) if temp is not None else None
                                self.draw_textured_block(
                                    bx + 1,
                                    by + 1,
                                    cell_size - 2,
                                    draw_color,
                                    piece_texture,
                                    slice_info,
                                )

        if self.opp_line_sweep_rows and self.opp_line_sweep_active:
            progress = self.opp_line_sweep_progress
            valid_rows = sorted({r for r in self.opp_line_sweep_rows if 0 <= r < BOARD_HEIGHT})
            if valid_rows:
                cleared_count = max(1, len(valid_rows))
                if cleared_count >= 4:
                    sw_blocks = 2
                elif cleared_count >= 3:
                    sw_blocks = 3
                elif cleared_count == 2:
                    sw_blocks = 2
                else:
                    sw_blocks = 1
                sweep_width = max(1, int(sw_blocks * cell_size))
                top_row = valid_rows[0]
                bottom_row = valid_rows[-1]
                group_y = y + top_row * cell_size
                group_h = max(cell_size, (bottom_row - top_row + 1) * cell_size)
                phase = (pygame.time.get_ticks() // 80) % 8
                sweep_x = x + int(progress * (board_w + sweep_width)) - sweep_width
                board_group_rect = pygame.Rect(x, group_y, board_w, group_h)
                if self._safe_draw_rainbow_cat_sweep(board_group_rect, sweep_x, sweep_width, phase, is_opponent=True):
                    glow_a = int(70 * (1.0 - progress * 0.4))
                    if glow_a > 0:
                        glow_w = min(sweep_width, int(board_w))
                        glow_x = max(x, sweep_x)
                        if glow_w > 0:
                            for row in valid_rows:
                                row_y = y + row * cell_size
                                glow_surface = self._effect_surface_cache.get_filled_surface((glow_w, cell_size), (255, 255, 255, glow_a))
                                self.screen.blit(glow_surface, (glow_x, row_y))

        if self.opp_line_flash_rows and self.opp_line_glow_alpha > 0:
            self._draw_line_clear_flash_overlay(x, y, board_w, cell_size, self.opp_line_flash_rows, self.opp_line_glow_alpha)

        for wave in self.opp_wave_effects:
            alpha = max(0, min(255, int(wave.get('alpha', 0))))
            if alpha <= 0:
                continue
            radius = int(wave.get('radius', 0))
            if radius <= 0:
                continue
            wave_surface = self._effect_surface_cache.get_ellipse_surface(
                (radius * 2 + 6, 6),
                (*wave.get('color', (255, 255, 255))[:3], alpha),
            )
            wave_x = int(wave.get('x', x + board_w // 2) - radius)
            wave_y = int(wave.get('y', y + board_h // 2) - 3)
            self.screen.blit(wave_surface, (wave_x, wave_y))

        pygame.draw.rect(self.screen, player_accent, board_rect, 2, border_radius=14)

    def _draw_game_over_underlay_effects(self, clip_rect: pygame.Rect) -> None:
        if clip_rect.width <= 0 or clip_rect.height <= 0:
            return

        previous_clip = self.screen.get_clip()
        try:
            self.screen.set_clip(clip_rect)
            if getattr(self, '_my_board_rect', None):
                self._draw_board(
                    self._my_board_rect.x,
                    self._my_board_rect.y,
                    self.cell_size,
                    self.my_board,
                    self.my_piece,
                )
            if getattr(self, '_opp_board_rect', None):
                self._draw_opponent_board(
                    self._opp_board_rect.x,
                    self._opp_board_rect.y,
                    self.cell_size,
                )
            self.draw_particles()
        finally:
            self.screen.set_clip(previous_clip)

    # ─── Game Over Overlay ───

    def _draw_game_over_overlay(self):
        w, h = self.window_width, self.window_height
        cx, cy = w // 2, h // 2
        sc = self._ui_scale()
        s = lambda v, minimum=1: self._sx(v, sc, minimum)

        overlay = pygame.Surface((w, h), pygame.SRCALPHA)
        overlay.fill((1, 4, 14, 212))
        self.screen.blit(overlay, (0, 0))

        if self.winner == 'me':
            result_text = t('you_win', 'KAZANDIN!')
            result_color = UIColors.NEON_GREEN
            icon_text = 'V'
            sub_text = t('victory_sub', 'Tebrikler, rakibini yendin!')
        elif self.winner == 'opponent':
            result_text = t('you_lose', 'KAYBETTIN')
            result_color = UIColors.NEON_RED
            icon_text = 'X'
            sub_text = t('defeat_sub', 'Bir dahaki sefere!')
        else:
            result_text = t('draw', 'BERABERE')
            result_color = UIColors.NEON_ORANGE
            icon_text = '='
            sub_text = t('draw_sub', 'Esit gucte rakipler!')

        my_name, opp_name = self._get_result_player_names()
        result_breakdown = self._build_majority_result_breakdown()
        reason_text = self._build_majority_result_reason_text(result_breakdown)
        lang = get_language()
        is_tr = lang == 'tr'

        my_score = int(getattr(self.my_board, 'score', 0) or 0)
        my_lines = int(getattr(self.my_board, 'lines_cleared', 0) or 0)
        opp_score, opp_lines, _ = self._get_opponent_result_metrics()

        def _safe_steam_id(attr_name: str) -> int:
            try:
                return int(getattr(self.net, attr_name, 0) or 0)
            except Exception:
                return 0

        my_steam_id = _safe_steam_id('my_steam_id')
        opp_steam_id = _safe_steam_id('opponent_steam_id')

        pw = min(s(760), w - s(64))
        btn_w = s(160)
        btn_h = s(48)
        hint_f = _rs.get_font(s(12, minimum=9), bold=False)
        reason_font_px = max(9, s(12, minimum=9))
        reason_wrap_w = max(s(280), pw - s(96))
        reason_font = _rs.get_font(reason_font_px, bold=False)
        reason_lines = _rs.wrap_text(reason_text, reason_font, reason_wrap_w)
        while len(reason_lines) > 4 and reason_font_px > 9:
            reason_font_px -= 1
            reason_font = _rs.get_font(reason_font_px, bold=False)
            reason_lines = _rs.wrap_text(reason_text, reason_font, reason_wrap_w)
        reason_line_gap = max(2, s(2, minimum=2))
        reason_panel_h = max(
            s(62),
            len(reason_lines) * reason_font.get_linesize()
            + max(0, len(reason_lines) - 1) * reason_line_gap
            + s(20),
        )

        card_gap = s(14)
        side_pad = s(28)
        stack_cards = pw < s(630)
        card_h = s(122) if stack_cards else s(158)
        cards_h = card_h * 2 + card_gap if stack_cards else card_h
        criteria_h = s(36)
        header_h = s(142)
        content_bottom = (
            header_h
            + cards_h
            + s(14)
            + criteria_h
            + s(14)
            + reason_panel_h
            + s(18)
            + btn_h
            + s(12)
            + hint_f.get_height()
        )
        ph = max(s(560), content_bottom + s(24))
        panel = pygame.Rect(cx - pw // 2, cy - ph // 2, pw, ph)
        self._draw_game_over_underlay_effects(panel.inflate(-s(12), -s(12)))

        def _draw_alpha_rect(
            rect: pygame.Rect,
            color: tuple[int, int, int],
            alpha: int,
            radius: int = 0,
            width: int = 0,
        ) -> None:
            surf = pygame.Surface(rect.size, pygame.SRCALPHA)
            pygame.draw.rect(surf, (*color[:3], alpha), surf.get_rect(), width, border_radius=radius)
            self.screen.blit(surf, rect.topleft)

        def _draw_alpha_circle(
            center: tuple[int, int],
            radius: int,
            color: tuple[int, int, int],
            alpha: int,
            width: int = 0,
        ) -> None:
            size = radius * 2 + max(2, width * 2)
            surf = pygame.Surface((size, size), pygame.SRCALPHA)
            draw_center = (size // 2, size // 2)
            pygame.draw.circle(surf, (*color[:3], alpha), draw_center, radius, width)
            self.screen.blit(surf, (center[0] - size // 2, center[1] - size // 2))

        halo_rect = panel.inflate(s(28), s(28))
        halo = pygame.Surface(halo_rect.size, pygame.SRCALPHA)
        pygame.draw.rect(halo, (*result_color[:3], 26), halo.get_rect(), border_radius=s(18))
        self.screen.blit(halo, halo_rect.topleft)

        draw_glass_panel(self.screen, panel, alpha=218,
                         border_color=(*result_color[:3], 190), glow=True)
        pygame.draw.rect(self.screen, (*UIColors.NEON_CYAN[:3], 55),
                         panel.inflate(-s(10), -s(10)), 1, border_radius=s(12))

        eyebrow_font = _rs.get_font(s(12, minimum=9), bold=True)
        eyebrow_text = t('online_pvp_title', 'ONLINE PvP')
        eyebrow_s = eyebrow_font.render(eyebrow_text, True, UIColors.NEON_CYAN)
        eyebrow_w = min(panel.width - s(48), eyebrow_s.get_width() + s(34))
        eyebrow_r = pygame.Rect(0, 0, eyebrow_w, s(26))
        eyebrow_r.center = (cx, panel.y + s(28))
        _draw_alpha_rect(eyebrow_r, UIColors.NEON_CYAN, 32, radius=s(13))
        pygame.draw.rect(self.screen, (*UIColors.NEON_CYAN[:3], 150), eyebrow_r, 1, border_radius=s(13))
        self.screen.blit(eyebrow_s, eyebrow_s.get_rect(center=eyebrow_r.center))

        icon_font = _rs.get_font(s(42, minimum=28), bold=True)
        icon_s = icon_font.render(icon_text, True, result_color)
        icon_rect = icon_s.get_rect(center=(cx, panel.y + s(70)))
        for offset, alpha in ((4, 24), (2, 38)):
            glow_icon = icon_font.render(icon_text, True, result_color)
            glow_icon.set_alpha(alpha)
            self.screen.blit(glow_icon, glow_icon.get_rect(center=(icon_rect.centerx + offset, icon_rect.centery + offset)))
        self.screen.blit(icon_s, icon_rect)

        tf = _rs.get_fitting_font(result_text, s(38), pw - s(70), bold=True, min_size=s(20, minimum=16))
        ts = tf.render(result_text, True, result_color)
        for offset, alpha in ((3, 26), (1, 44)):
            glow_title = tf.render(result_text, True, result_color)
            glow_title.set_alpha(alpha)
            self.screen.blit(glow_title, glow_title.get_rect(center=(cx + offset, panel.y + s(105) + offset)))
        self.screen.blit(ts, ts.get_rect(center=(cx, panel.y + s(105))))

        sub_f = _rs.get_fitting_font(sub_text, s(15, minimum=11), pw - s(90), bold=False, min_size=s(10, minimum=8))
        sub_s = sub_f.render(sub_text, True, _rs.text_secondary)
        self.screen.blit(sub_s, sub_s.get_rect(center=(cx, panel.y + s(130))))

        def _format_number(value: int) -> str:
            return f"{int(value):,}".replace(',', '.')

        def _result_status_for(side: str) -> tuple[str, tuple[int, int, int], bool, bool]:
            if self.winner == 'draw':
                return (t('draw', 'Berabere'), UIColors.NEON_ORANGE, False, False)
            is_winner = self.winner == side
            if is_winner:
                return (('Kazanan' if is_tr else 'Winner'), UIColors.NEON_GREEN, True, False)
            return (('Kaybeden' if is_tr else 'Loser'), UIColors.NEON_RED, False, True)

        def _draw_avatar(center: tuple[int, int], steam_id: int, name: str, accent: tuple[int, int, int], size: int, active_color: tuple[int, int, int]) -> None:
            radius = size // 2
            for grow, alpha in ((s(10), 18), (s(5), 32)):
                _draw_alpha_circle(center, radius + grow, active_color, alpha)
            pygame.draw.circle(self.screen, (10, 16, 31), center, radius + s(5))
            pygame.draw.circle(self.screen, active_color, center, radius + s(5), s(2))
            pygame.draw.circle(self.screen, accent, center, radius + s(1), s(1))
            avatar = self._get_steam_avatar_surface(steam_id, size) if steam_id else None
            if avatar:
                self.screen.blit(avatar, avatar.get_rect(center=center))
                return
            _draw_alpha_circle(center, radius, accent, 70)
            initial = (str(name).strip()[:1] or '?').upper()
            initial_font = _rs.get_font(max(14, size // 2), bold=True)
            initial_s = initial_font.render(initial, True, UIColors.TEXT_PRIMARY)
            self.screen.blit(initial_s, initial_s.get_rect(center=center))

        def _draw_player_card(card_rect: pygame.Rect, player: dict[str, object]) -> None:
            side = str(player['side'])
            accent = player['accent']
            status_text, status_color, is_winner, is_loser = _result_status_for(side)
            border_color = status_color if is_winner or is_loser else accent

            draw_glass_panel(self.screen, card_rect, alpha=168,
                             border_color=(*border_color[:3], 175 if is_winner else 105),
                             glow=is_winner)
            tint = pygame.Surface(card_rect.size, pygame.SRCALPHA)
            for y in range(card_rect.height):
                ratio = y / max(1, card_rect.height - 1)
                alpha = int((22 if is_winner else 12) * (1.0 - ratio * 0.55))
                pygame.draw.line(tint, (*accent[:3], alpha), (0, y), (card_rect.width, y))
            pygame.draw.rect(tint, (*status_color[:3], 18 if is_winner else 8), tint.get_rect(), border_radius=s(12))
            self.screen.blit(tint, card_rect.topleft)
            pygame.draw.rect(self.screen, (*border_color[:3], 220 if is_winner else 120),
                             card_rect, s(2) if is_winner else 1, border_radius=s(12))

            badge_font = _rs.get_fitting_font(status_text.upper(), s(12, minimum=9),
                                              card_rect.width - s(34), bold=True, min_size=8)
            badge_s = badge_font.render(status_text.upper(), True, status_color)
            badge_r = pygame.Rect(card_rect.x + s(14), card_rect.y + s(12),
                                  min(card_rect.width - s(28), badge_s.get_width() + s(24)), s(24))
            _draw_alpha_rect(badge_r, status_color, 34, radius=s(12))
            pygame.draw.rect(self.screen, (*status_color[:3], 140), badge_r, 1, border_radius=s(12))
            self.screen.blit(badge_s, badge_s.get_rect(center=badge_r.center))

            avatar_size = min(s(72), max(s(46), card_rect.height - s(52)))
            avatar_center = (
                card_rect.x + s(54),
                card_rect.y + card_rect.height // 2 + s(12 if card_rect.height >= s(145) else 8),
            )
            _draw_avatar(
                avatar_center,
                int(player.get('steam_id', 0) or 0),
                str(player['name']),
                accent,
                avatar_size,
                status_color if is_winner or is_loser else accent,
            )

            text_x = avatar_center[0] + avatar_size // 2 + s(18)
            text_w = max(s(80), card_rect.right - text_x - s(16))
            name_font = _rs.get_fitting_font(str(player['name']), s(20, minimum=13),
                                             text_w, bold=True, min_size=s(10, minimum=8))
            name_s = name_font.render(str(player['name']), True, UIColors.TEXT_PRIMARY if not is_loser else _rs.text_secondary)
            name_y = card_rect.y + s(48 if card_rect.height >= s(145) else 38)
            self.screen.blit(name_s, name_s.get_rect(midleft=(text_x, name_y)))

            line_y = name_y + s(18)
            pygame.draw.line(self.screen, (*accent[:3], 95), (text_x, line_y), (card_rect.right - s(16), line_y), 1)

            score_text = f'{t("score", "Skor")} {_format_number(int(player["score"]))}'
            lines_text = f'{t("lines", "Satır")} {int(player["lines"])}'
            metric_font = _rs.get_fitting_font(score_text, s(13, minimum=10), text_w, bold=False, min_size=8)
            score_s = metric_font.render(score_text, True, _rs.text_primary)
            lines_font = _rs.get_fitting_font(lines_text, s(13, minimum=10), text_w, bold=False, min_size=8)
            lines_s = lines_font.render(lines_text, True, _rs.text_secondary)
            self.screen.blit(score_s, score_s.get_rect(midleft=(text_x, line_y + s(18))))
            self.screen.blit(lines_s, lines_s.get_rect(midleft=(text_x, line_y + s(40))))

        cards_y = panel.y + header_h
        player_cards = [
            {
                'side': 'me',
                'name': my_name,
                'steam_id': my_steam_id,
                'score': my_score,
                'lines': my_lines,
                'accent': UIColors.NEON_CYAN,
            },
            {
                'side': 'opponent',
                'name': opp_name,
                'steam_id': opp_steam_id,
                'score': opp_score,
                'lines': opp_lines,
                'accent': UIColors.NEON_MAGENTA,
            },
        ]
        if stack_cards:
            card_w = panel.width - side_pad * 2
            card_rects = [
                pygame.Rect(panel.x + side_pad, cards_y, card_w, card_h),
                pygame.Rect(panel.x + side_pad, cards_y + card_h + card_gap, card_w, card_h),
            ]
        else:
            card_w = (panel.width - side_pad * 2 - card_gap) // 2
            card_rects = [
                pygame.Rect(panel.x + side_pad, cards_y, card_w, card_h),
                pygame.Rect(panel.x + side_pad + card_w + card_gap, cards_y, card_w, card_h),
            ]
        for card_rect, player in zip(card_rects, player_cards):
            _draw_player_card(card_rect, player)

        def _side_label(side: str) -> str:
            if side == 'me':
                return 'Sen' if is_tr else 'You'
            if side == 'opponent':
                return 'Rakip' if is_tr else 'Opponent'
            if side == 'both':
                return 'İkisi' if is_tr else 'Both'
            if side == 'none':
                return 'Yok' if is_tr else 'None'
            return 'Eşit' if is_tr else 'Tie'

        def _side_color(side: str) -> tuple[int, int, int]:
            if side == 'me':
                return UIColors.NEON_CYAN
            if side == 'opponent':
                return UIColors.NEON_MAGENTA
            if side == 'both':
                return UIColors.NEON_GREEN
            if side == 'none':
                return UIColors.NEON_RED
            return UIColors.NEON_ORANGE

        criteria_y = cards_y + cards_h + s(14)
        criteria = [
            (t('score', 'Skor'), str(result_breakdown.get('score_state', 'draw'))),
            (t('lines', 'Satır'), str(result_breakdown.get('lines_state', 'draw'))),
            (("Alan x2" if is_tr else 'Board x2'), str(result_breakdown.get('board_state', 'draw'))),
        ]
        chip_gap = s(8)
        chip_w = (panel.width - side_pad * 2 - chip_gap * 2) // 3
        chip_font_base = s(12, minimum=9)
        for idx, (label, owner) in enumerate(criteria):
            chip_r = pygame.Rect(panel.x + side_pad + idx * (chip_w + chip_gap), criteria_y, chip_w, criteria_h)
            owner_color = _side_color(owner)
            pygame.draw.rect(self.screen, (12, 18, 32), chip_r, border_radius=s(9))
            pygame.draw.rect(self.screen, (*owner_color[:3], 95), chip_r, 1, border_radius=s(9))
            chip_text = f'{label}: {_side_label(owner)}'
            chip_font = _rs.get_fitting_font(chip_text, chip_font_base, chip_r.width - s(16), bold=True, min_size=8)
            chip_s = chip_font.render(chip_text, True, owner_color)
            self.screen.blit(chip_s, chip_s.get_rect(center=chip_r.center))

        reason_panel_y = criteria_y + criteria_h + s(14)
        reason_panel_r = pygame.Rect(panel.x + s(34), reason_panel_y, panel.width - s(68), reason_panel_h)
        draw_glass_panel(
            self.screen,
            reason_panel_r,
            alpha=132,
            border_color=(*result_color[:3], 120),
        )
        _draw_alpha_rect(reason_panel_r.inflate(-s(8), -s(8)), result_color, 50, radius=s(10), width=1)
        reason_inner_r = reason_panel_r.inflate(-s(16), -s(10))
        reason_total_h = (
            len(reason_lines) * reason_font.get_linesize()
            + max(0, len(reason_lines) - 1) * reason_line_gap
        )
        reason_y = reason_inner_r.centery - reason_total_h // 2
        for line in reason_lines:
            line_s = reason_font.render(line, True, _rs.text_secondary)
            self.screen.blit(line_s, line_s.get_rect(midtop=(reason_inner_r.centerx, reason_y)))
            reason_y += reason_font.get_linesize() + reason_line_gap

        btn_gap = s(20)
        btn_y = reason_panel_r.bottom + s(18)

        rematch_r = pygame.Rect(cx - btn_w - btn_gap // 2, btn_y, btn_w, btn_h)
        exit_r = pygame.Rect(cx + btn_gap // 2, btn_y, btn_w, btn_h)
        mp = get_mouse_pos()

        _rs.draw_uniform_button(self.screen, rematch_r,
                                t('rematch', 'Tekrar Oyna'),
                                sub_text='R', color_code=UIColors.NEON_GREEN,
                                state='hover' if rematch_r.collidepoint(mp) else 'normal')
        _rs.draw_uniform_button(self.screen, exit_r,
                                t('back_to_menu', 'Çıkış'),
                                sub_text='ESC', color_code=_rs.secondary,
                                state='hover' if exit_r.collidepoint(mp) else 'normal')
        self._lobby_buttons.append({'rect': rematch_r, 'action': 'rematch'})
        self._lobby_buttons.append({'rect': exit_r, 'action': 'exit_menu'})

        ht = render_text(hint_f, t('campaign_failed_hint', '[R] Retry | [ESC] Menu'), True, _rs.text_muted)
        self.screen.blit(ht, ht.get_rect(center=(cx, panel.bottom - s(20))))

    # ─── Bağlantı Koptu ───

    def _draw_disconnected(self):
        w, h = self.window_width, self.window_height
        cx, cy = w // 2, h // 2
        sc = self._ui_scale()
        s = lambda v, minimum=1: self._sx(v, sc, minimum)

        pw = min(s(440), w - s(80))
        ph = s(180)
        panel = pygame.Rect(cx - pw // 2, cy - ph // 2, pw, ph)
        draw_glass_panel(self.screen, panel, alpha=200,
                         border_color=UIColors.NEON_RED, glow=True)

        tf = _rs.get_fitting_font(
            t('opponent_disconnected', 'Rakip Bağlantıyı Kesti'), s(24), pw - s(40))
        ts = render_text(tf, t('opponent_disconnected', 'Rakip Bağlantıyı Kesti'),
                       True, UIColors.NEON_RED)
        self.screen.blit(ts, ts.get_rect(center=(cx, cy - s(18))))

        btn_r = pygame.Rect(cx - s(90), cy + s(20), s(180), s(42))
        mp = get_mouse_pos()
        _rs.draw_uniform_button(self.screen, btn_r,
                                t('back_to_menu', 'Ana Menü'),
                                sub_text='ESC', color_code=_rs.secondary,
                                state='hover' if btn_r.collidepoint(mp) else 'normal')
        self._lobby_buttons.append({'rect': btn_r, 'action': 'exit_menu'})

    # ============================================================
    #  ANA DÖNGÜ
    # ============================================================

    def _cleanup(self):
        """Online PvP çıkışında kaynakları temizle ve pump thread'i sürdür."""
        try:
            self.net.shutdown()
        except Exception:
            pass
        # Pump thread'i tekrar başlat — bridge artık RunCallbacks çağırmıyor
        try:
            _resume_steam_pump()
        except Exception:
            pass

    def run(self) -> str:
        """Ana oyun döngüsü. 'menu' döndürürse ana menüye dön."""
        self._init_networking()
        running = True

        try:
            while running:
                try:
                    fps_limit = int(self.settings_manager.get('fps_limit', 0) or 0) \
                        if self.settings_manager else 0
                except Exception:
                    fps_limit = 0

                delta_time = self.clock.tick(resolve_frame_rate_cap(fps_limit))

                result = self.handle_input()
                if result is False:
                    break
                if result == 'menu':
                    self.net.leave_lobby()
                    self._cleanup()
                    return 'menu'

                self.update(delta_time)
                self.draw()
                pygame.display.flip()
        except Exception as e:
            print(f"[OnlinePvP] Kritik hata: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self._cleanup()

        return 'menu'
