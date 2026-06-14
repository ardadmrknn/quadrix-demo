"""Quadrix Online Co-op — Steam P2P üzerinden 2 oyunculu kooperatif Tetris

Bu modül, yerel Co-op (coop_game.py) mantığını temel alarak
Steam Networking üzerinden online co-op oynanmasını sağlar.

Mimari: Otoriter Host
  - Host: Tam CoopGame simülasyonu çalıştırır
  - Guest: Input gönderir, host'tan gelen state'i render eder

Akış:
  1. Lobi ekranı: oluştur / katıl / arkadaş davet et
  2. İki oyuncu hazır olunca host oyunu başlatır
  3. Oyun sırasında:
     - Host: Tam CoopGame simülasyonu + P2 input injection
     - Guest: Input gönderme + board/piece state alma + render
  4. İkisi de freeze → game over
"""
from __future__ import annotations

import time
import random
import json
import sys

import pygame

# Proje import'ları
from background import BackgroundManager
from background_effects import get_shared_falling_blocks_layer
from themes import ThemeManager
from mode_skins import get_mode_skin
from block_styles import BlockStyleManager, TextureSlice
from retro_style import retro_style as _rs
from ui_theme import UIColors
from localization import t, get_language
from sound import SoundManager
from ui_scaling import get_projected_effective_scale
from steam_networking import (
    SteamNetworking, MsgType, NetEvent, NetMessage,
    CHANNEL_GAME,
    CHANNEL_STATE,
    CHANNEL_CONTROL,
    generate_lobby_code,
)
from coop_game import CoopGame
from screen_shake import step_screen_shake
from pieces import Piece, SHAPES as _SHAPES
from line_clear_feedback import (
    queue_wave_effects as _queue_wave_effects,
    update_wave_effects as _update_wave_effects,
    trigger_combo_burst as _trigger_combo_burst,
)
from constants import (
    COLORS as _PIECE_COLORS,
    BLACK as _BOARD_EMPTY_COLOR,
    DEFAULT_LOCK_DELAY,
    DAS_DELAY,
    DAS_REPEAT,
)

# Steam pump thread kontrolü
try:
    from steam_integration import pause_pump as _pause_steam_pump
    from steam_integration import resume_pump as _resume_steam_pump
except ImportError:
    def _pause_steam_pump(): pass
    def _resume_steam_pump(): pass

try:
    from steam_integration import activate_game_overlay_invite_dialog as _activate_invite_dialog
except ImportError:
    def _activate_invite_dialog(lobby_id=0): return False

try:
    from platform_utils import normalize_mouse_pos, get_mouse_pos
except ImportError:
    def normalize_mouse_pos(pos):
        return pos

    def get_mouse_pos():
        return pygame.mouse.get_pos()

# Convenience aliases
get_font = _rs.get_font
draw_glass_panel = _rs.draw_glass_panel
get_fitting_font = _rs.get_fitting_font


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


# ─────────────── Online Co-op Durumları ───────────────

class OnlineCoopState:
    LOBBY_MENU   = 'lobby_menu'
    WAITING      = 'waiting'
    READY_CHECK  = 'ready_check'
    COUNTDOWN    = 'countdown'
    PLAYING      = 'playing'
    GAME_OVER    = 'game_over'
    DISCONNECTED = 'disconnected'


class OnlineCoopGame:
    """Steam P2P üzerinden Online 2 Oyunculu Co-op Tetris."""

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
        if self.online_state != OnlineCoopState.PLAYING:
            return False
        if self.game_over or self.paused:
            return False
        if self.role == 'host':
            self._set_pause_state(True)
            self._freeze_active_gameplay_input()
            self._send_game_event('pause')
        elif self.role == 'guest':
            self._send_guest_input('pause_request')
        return True

    # ── Responsive ölçek ──

    def _ui_scale(self, min_scale: float = 0.72, max_scale: float = 1.20) -> float:
        try:
            scale = get_projected_effective_scale(
                self.screen,
                min_scale=min_scale,
                max_scale=max_scale,
                reference_size=(1366.0, 768.0),
            )
        except Exception:
            scale = 1.0
        return max(min_scale, min(max_scale, scale))

    def _sx(self, value, scale=None, minimum=1) -> int:
        if scale is None:
            scale = self._ui_scale()
        return max(minimum, int(round(float(value) * float(scale))))

    def _get_lobby_entries_for_display(self) -> list[dict]:
        """Aktif filtreye göre gösterilecek lobi kartlarını döndür."""
        entries = list(getattr(self, '_lobby_list', []) or [])
        if getattr(self, '_lobby_list_filter', 'all') == 'public':
            entries = [
                lobby for lobby in entries
                if str(lobby.get('visibility', 'unknown') or 'unknown').lower()
                in ('public', 'unknown', 'stale_unknown')
            ]
        return entries

    def __init__(
        self,
        screen=None,
        fullscreen=True,
        user_manager=None,
        settings_manager=None,
        sound_manager=None,
    ):
        if not pygame.get_init():
            pygame.init()

        self.user_manager = user_manager
        self.settings_manager = settings_manager

        # Ekran
        if screen is not None:
            self.screen = screen
            self.window_width = self.screen.get_width()
            self.window_height = self.screen.get_height()
        else:
            self.screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN | pygame.RESIZABLE)
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
        self.background.set_transparency(1.0)
        self.background_fx = get_shared_falling_blocks_layer('default')

        # Tema
        self.theme_manager = ThemeManager(settings_manager)
        if self.settings_manager:
            active_theme = self.settings_manager.get('theme', self.settings_manager.get('active_theme', 'Classic'))
            self.theme_manager.set_theme(active_theme)
        self.mode_skin = get_mode_skin('coop')
        self.block_style_manager = BlockStyleManager(self.settings_manager) if self.settings_manager else None

        # Steam Networking
        self.net = SteamNetworking()
        self._net_initialized = False
        self._auto_connect_attempted = False
        self._auto_connect_retry_timer = 0.0

        # ─── Online durumu ───
        self.online_state = OnlineCoopState.LOBBY_MENU
        self.role: str = ''  # 'host' | 'guest'

        # Lobi
        self._lobby_list: list[dict] = []
        self._lobby_list_filter: str = 'all'
        self._lobby_list_scroll = 0
        self._lobby_list_fetching = False
        self._lobby_list_fetch_start_time: float = 0.0
        self._auto_lobby_refresh_requested = False
        self._auto_lobby_refresh_timer = 0.0
        self._auto_lobby_refresh_interval = 10000.0
        self._pending_lobby_list: list[dict] = []
        self._deferred_lobby_entries: dict[int, dict] = {}
        self._deferred_lobby_refresh_timer = 0.0
        self._DEFERRED_LOBBY_REFRESH_INTERVAL_MS = 500.0
        self._unknown_lobby_metadata_requests: dict[int, float] = {}
        self._UNKNOWN_LOBBY_DATA_REQUEST_INTERVAL_S = 1.25
        self._lobby_presence_probe_timer = 0.0
        self._LOBBY_PRESENCE_PROBE_INTERVAL_MS = 350.0

        # Lobi kod sistemi
        self._lobby_code: str = ''
        self._lobby_id_str: str = ''
        self._join_code_input: str = ''
        self._join_code_active: bool = False
        self._join_code_error: str = ''
        self._join_code_suppress_textinput: str = ''
        self._join_target_lobby_id: int = 0
        self._pending_browser_join_lobby_id: int = 0
        self._searching_by_code: bool = False
        self._search_code: str = ''
        self._code_search_retry_count: int = 0
        self._code_search_retry_timer: float = 0.0
        self._code_search_retry_code: str = ''
        self._code_search_retry_use_full_scan: bool = False
        self._authorized_private_join_lobby_id: int = 0
        self._authorized_private_join_code: str = ''
        self._invite_authorized_lobby_id: int = 0
        self._pending_access_revalidation_lobby_id: int = 0
        self._pending_revalidation_start_time: float = 0.0
        self._pending_reval_last_check_time: float = 0.0
        self._lobby_access_validated_id: int = 0
        self._invite_after_lobby: bool = False
        self._creating_public_lobby: bool = False

        # Ready
        self.my_ready = False
        self.opponent_ready = False
        self._ready_resend_timer = 0.0
        self._READY_RESEND_INTERVAL_MS = 1000.0
        self._session_ping_timer = 0.0
        self._SESSION_PING_INTERVAL_MS = 2000.0
        self._SESSION_PING_BACKOFF_BASE_MS = 500.0
        self._SESSION_PING_BACKOFF_MAX_MS = 4000.0
        self._session_ping_backoff_ms = 0.0
        self._session_established = False
        self._ready_send_pending = False
        self._game_start_pending_payload: dict | None = None
        self._game_start_retry_timer = 0.0
        self._GAME_START_RETRY_INTERVAL_MS = 1000.0

        # Countdown
        self.countdown_timer = 0.0
        self.countdown_value = 3

        # Durum mesajı
        self._status_msg: str = ''
        self._status_timer: float = 0

        # Sub-mode (V1'de sabit endless)
        self.selected_submode: str = 'endless'

        # Pause toggle cooldown (race önleme, ms)
        self._pause_cooldown_timer = 0.0
        self._PAUSE_COOLDOWN_MS = 500.0

        # Disconnect
        self._pending_disconnect_steam_id = 0
        self._disconnect_grace_timer = 0.0
        self._DISCONNECT_GRACE_MS = 5000.0

        # Rematch
        self._my_rematch = False
        self._opponent_rematch = False

        # Game state (host runs CoopGame; guest receives state)
        self.coop_game = None  # CoopGame instance (host only)
        self.game_over = False
        self.paused = False
        self._game_seed = 0
        self._last_input_ack_seq = 0  # Host: en son işlenen guest input seq, Guest: son otoriter ack
        self._guest_input_seq = 0
        self._last_guest_input_seq = 0
        self._last_guest_piece_state_seq = 0
        self._last_host_guest_piece_ack_seq = 0
        self._guest_pending_inputs: list[tuple[int, str]] = []
        self._board_state_seq = 0
        self._piece_state_seq = 0
        self._guest_piece_state_out_seq = 0
        self._guest_piece_unacked_since = 0.0
        self._guest_board_seq = -1
        self._guest_piece_seq = -1
        self._last_sent_board_cells = None
        self._last_piece_state_signature = None
        self._last_guest_sent_piece_signature = None
        self._last_frozen_flags: tuple[bool, bool] | None = None
        self._authoritative_gameplay_config: dict = {}

        # Host state broadcast timers (ms)
        self._board_state_timer = 0.0
        self._piece_state_timer = 0.0
        self._guest_piece_state_timer = 0.0
        self._BOARD_STATE_INTERVAL = 200.0   # full-board heartbeat; asil sync event-driven
        # Online PvP'nin `PIECE_POSITION` 33ms cadansıyla parity için heartbeat'i
        # 50ms'den 33ms'e indirdik. Push asıl olarak event-driven (signature
        # equality early-return) çalışıyor; bu sadece tavanı düşürerek guest'in
        # lokal mirror'ı host otoritesiyle daha sık çakışmasını sağlar.
        self._PIECE_STATE_INTERVAL = 33.0
        # Guest mirror heartbeat 20ms idi; signature-equality erken-çıkışla
        # gerçek değişim yoksa paket yine üretilmiyor. Tavanı 16ms (~60fps) seviyesine
        # indirerek hızlı DAS / rotation akışlarında host'un guest aktif
        # parçasından haberdar olma latency'sini bir frame daha kısaltıyoruz.
        self._GUEST_PIECE_STATE_INTERVAL = 16.0

        # Guest: received state cache
        self._guest_board_cache = None   # dict from host
        self._guest_piece_cache = None   # dict from host
        self._guest_score_cache = {}     # score/lines/level
        self._guest_render_board_seq = -1
        self._guest_render_piece_seq = -1
        self._guest_last_authoritative_piece_elapsed_ms = 0.0
        self._guest_local_prediction_ms = 0.0
        self._GUEST_LOCAL_PREDICTION_MAX_MS = 140.0
        # SDR relay üzerinden 200-400ms RTT'de mirror ack 0.75s'lik grace'i
        # aşabiliyor; identity-based koruma (`_should_keep_locally_simulated_p2`)
        # zaten yedekleniyor olsa da ack-bazlı yol da yüksek latency'de açık
        # kalsın diye 2.5s'e yükseltildi. Worst-case identity match yolu hâlâ
        # geçersiz state'i bloklayabilir, bu yüzden zararsız.
        self._GUEST_PIECE_ACK_GRACE_S = 2.5
        self._guest_authoritative_piece_sync_enabled = True
        self._held_gameplay_keys: set[int] = set()

        # Placeholder font'lar
        self.font_large = _rs.get_font(36)
        self.font_medium = _rs.get_font(24)
        self.font_small = _rs.get_font(18)

        # Lobby butonları
        self._lobby_buttons: list[dict] = []

    # ============================================================
    #  NETWORKING
    # ============================================================

    def _init_networking(self) -> bool:
        """Steam networking'i başlat."""
        if self._net_initialized:
            return True

        if not self.net.available:
            self._status_msg = t('steam_bridge_not_available',
                                 'Steam ağ köprüsü yüklenemedi.')
            self._status_timer = 4.0
            return False

        try:
            _pause_steam_pump()
        except Exception as e:
            print(f"[OnlineCoop] Pump pause hatası: {e}")

        ok = self.net.init()
        if ok:
            self._net_initialized = True
            self.net.on('lobby_created', self._on_lobby_created)
            self.net.on('lobby_joined', self._on_lobby_joined)
            self.net.on('lobby_member_joined', self._on_member_joined)
            self.net.on('lobby_member_left', self._on_member_left)
            self.net.on('lobby_member_disconnected', self._on_member_disconnected)
            self.net.on('lobby_found', self._on_lobby_found)
            self.net.on('lobby_data_updated', self._on_lobby_data_updated)
            self.net.on('lobby_list_complete', self._on_lobby_list_complete)
            self.net.on('join_requested', self._on_join_requested)
            self.net.on('lobby_create_failed', self._on_lobby_error)
            self.net.on('lobby_join_failed', self._on_lobby_error)
            self.net.on('lobby_list_failed', self._on_lobby_list_error)
            self.net.on('session_accepted', self._on_session_accepted)
            self.net.on('session_rejected', self._on_session_rejected)
        else:
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
        self.online_state = OnlineCoopState.WAITING
        self.role = 'host'
        self._lobby_presence_probe_timer = 0.0
        self._lobby_access_validated_id = int(ev.steam_id or 0)
        self._pending_access_revalidation_lobby_id = 0
        self._pending_revalidation_start_time = 0.0
        self._session_established = False
        self._ready_send_pending = False
        print(f"[OnlineCoop] Lobi oluşturuldu: {ev.steam_id}")

        self._lobby_id_str = str(ev.steam_id)
        if self._creating_public_lobby:
            self._lobby_code = ''
        else:
            self._lobby_code = generate_lobby_code(ev.steam_id)

        # Eski C++ bridge uyumluluğu: C++ OnLobbyCreated metadata_ready=1
        # yazmış olabilir. Hassas alanları yazmadan önce metadata_ready=0'a çek.
        try:
            self.net.set_lobby_data('metadata_ready', '0')
        except Exception:
            pass

        # Co-op metadata set
        # Not: '1'/'0' formatı C++ bridge (build_lobby_found_payload) ve
        # PvP koduyla tutarlılık için kullanılır. C++ requires_code=='1'
        # kontrolü yapar; 'true'/'false' kullanılmamalı.
        try:
            self.net.set_lobby_data('game', 'quadrix')
            self.net.set_lobby_data('mode', 'coop')
            self.net.set_lobby_data('sub_mode', self.selected_submode)
            visibility = 'public' if self._creating_public_lobby else 'private'
            self.net.set_lobby_data('visibility', visibility)
            if self._lobby_code:
                self.net.set_lobby_data('lobby_code', self._lobby_code)
                self.net.set_lobby_data('lobby_code_full', self._lobby_id_str)
            self.net.set_lobby_data('requires_code', '1' if self._lobby_code else '0')
            host_name = ''
            if self.user_manager:
                host_name = getattr(self.user_manager, 'display_name', '') or ''
            self.net.set_lobby_data('host_name', host_name or 'Host')
            self.net.set_lobby_data('metadata_ready', '1')
        except Exception as e:
            print(f"[OnlineCoop] Metadata set hatası: {e}")

        if self._invite_after_lobby:
            self._invite_after_lobby = False
            try:
                self.net.invite_friend()
            except Exception:
                pass
            self._status_msg = t('invite_sent', 'Steam davet penceresi açıldı')
            self._status_timer = 2.5

    def _on_lobby_joined(self, ev: NetEvent):
        if self.role != 'host':
            self.role = 'guest'
        self.online_state = OnlineCoopState.WAITING
        self._lobby_presence_probe_timer = 0.0
        self._join_target_lobby_id = 0
        self._lobby_access_validated_id = 0
        self._pending_access_revalidation_lobby_id = 0
        self._pending_revalidation_start_time = 0.0
        self._pending_reval_last_check_time = 0.0
        self._session_established = False
        self._ready_send_pending = False
        self.my_ready = False
        self.opponent_ready = False
        print(f"[OnlineCoop] Lobiye katıldı: {ev.steam_id}")

        if ev.data:
            try:
                parsed = json.loads(ev.data)
                if isinstance(parsed, dict):
                    joined_lobby_id = int(getattr(self.net, 'lobby_id', 0) or 0)
                    if joined_lobby_id:
                        self._refresh_cached_lobby_metadata(
                            joined_lobby_id, parsed, prefer_live=True)
            except (json.JSONDecodeError, ValueError, TypeError):
                pass

        joined_lobby_id = int(getattr(self.net, 'lobby_id', 0) or 0)
        if joined_lobby_id:
            try:
                self.net.request_lobby_data(joined_lobby_id)
            except Exception:
                pass

        if not self._validate_joined_lobby_access():
            return

        if getattr(self.net, 'opponent_steam_id', 0):
            self._promote_to_ready_check(self.net.opponent_steam_id, self.net.opponent_name)

    def _on_member_joined(self, ev: NetEvent):
        if ev.steam_id == getattr(self.net, 'my_steam_id', 0):
            return
        if self.online_state in (OnlineCoopState.WAITING, OnlineCoopState.READY_CHECK):
            self._promote_to_ready_check(ev.steam_id, ev.data or self.net.opponent_name, play_sound=True)
        elif self.online_state == OnlineCoopState.PLAYING and self._disconnect_grace_timer > 0:
            # Reconnect sırasında grace period'u iptal et
            if ev.steam_id:
                try:
                    self.net._opponent_steam_id = ev.steam_id
                except Exception:
                    pass
            self._pending_disconnect_steam_id = 0
            self._disconnect_grace_timer = 0.0
            self._set_pause_state(False)
            if self.role == 'host':
                self._send_game_event('resume')
        print(f"[OnlineCoop] Üye katıldı: {ev.steam_id}")

    def _on_member_left(self, ev: NetEvent):
        self._handle_opponent_gone('left', ev.steam_id)

    def _on_member_disconnected(self, ev: NetEvent):
        self._handle_opponent_gone('disconnected', ev.steam_id)

    def _handle_opponent_gone(self, reason: str, steam_id: int = 0):
        my_id = int(getattr(self.net, 'my_steam_id', 0) or 0)
        opponent_id = int(getattr(self.net, 'opponent_steam_id', 0) or 0)
        target_id = int(steam_id or opponent_id or getattr(self, '_pending_disconnect_steam_id', 0) or 0)
        if not target_id or target_id == my_id:
            return

        if self.online_state == OnlineCoopState.PLAYING:
            # Grace period: oyun sırasında 5 sn bekle
            self._pending_disconnect_steam_id = target_id
            self._disconnect_grace_timer = self._DISCONNECT_GRACE_MS
            self._session_established = False
            self._session_ping_timer = 0.0
            self._send_session_ping()
            self._set_pause_state(True)
        elif self.online_state in (OnlineCoopState.READY_CHECK, OnlineCoopState.COUNTDOWN):
            self.online_state = OnlineCoopState.WAITING
            self.my_ready = False
            self.opponent_ready = False
            self._ready_resend_timer = 0.0
            self._game_start_pending_payload = None
            self._game_start_retry_timer = 0.0
        elif self.online_state == OnlineCoopState.GAME_OVER:
            pass  # Game over'da disconnect önemsiz
        else:
            self.online_state = OnlineCoopState.LOBBY_MENU
        print(f"[OnlineCoop] Takım arkadaşı ayrıldı: {reason}")

    def _on_lobby_found(self, ev: NetEvent):
        """Tek bir co-op lobi bulundu; metadata gecikmelerine dayanıklı ekle."""
        payload = {}
        if ev.data:
            try:
                parsed = json.loads(ev.data)
                if isinstance(parsed, dict):
                    payload = parsed
            except Exception:
                payload = {}

        mode = str(payload.get('mode', '') or '').strip().lower()
        if mode and mode != 'coop':
            return
        if not mode and ev.steam_id:
            try:
                live_mode = str(self.net.get_lobby_data_for(ev.steam_id, 'mode') or '').strip().lower()
            except Exception:
                live_mode = ''
            if live_mode and live_mode != 'coop':
                return

        snapshot = self._get_lobby_metadata_snapshot(ev.steam_id, payload)
        if snapshot['visibility'] == 'unknown':
            live_snapshot = self._get_lobby_metadata_snapshot(
                ev.steam_id, payload, prefer_live=True)
            if live_snapshot['visibility'] != 'unknown':
                snapshot = live_snapshot
            else:
                self._request_lobby_metadata_refresh(ev.steam_id)

        member_count = 0
        try:
            if isinstance(payload.get('members'), int):
                member_count = int(payload.get('members', 0))
            elif ev.data and str(ev.data).isdigit():
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
            'lobby_id': ev.steam_id,
            'members': member_count,
            'max_members': max_members,
            'name': snapshot['name'] or payload.get('host_name') or f'Co-op Lobi #{len(self._pending_lobby_list) + 1}',
            'host_name': snapshot['name'] or payload.get('host_name') or 'Host',
            'mode': 'coop',
            'sub_mode': str(payload.get('sub_mode', self.selected_submode) or self.selected_submode),
            'code': snapshot['code'],
            'lobby_code': snapshot['code'],
            'visibility': snapshot['visibility'],
            'requires_code': snapshot['requires_code'],
            'metadata_ready': snapshot['metadata_ready'],
            'found_time': time.time(),
        }
        prev_found_time = 0.0
        for prev in getattr(self, '_lobby_list', []):
            if int(prev.get('id', 0) or 0) == int(ev.steam_id or 0):
                prev_found_time = float(prev.get('found_time', 0) or 0)
                break
        if prev_found_time and entry['visibility'] == 'unknown':
            entry['found_time'] = prev_found_time
        if entry['visibility'] == 'unknown':
            self._remember_deferred_lobby_entry(entry)
        self._upsert_lobby_entry('_pending_lobby_list', entry)

    def _on_lobby_data_updated(self, ev: NetEvent):
        current_lobby_id = int(getattr(self.net, 'lobby_id', 0) or 0)
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
            pending_revalidation = int(
                getattr(self, '_pending_access_revalidation_lobby_id', 0) or 0)
            if pending_revalidation == current_lobby_id:
                if snapshot.get('metadata_ready'):
                    self._pending_access_revalidation_lobby_id = 0
                    self._pending_revalidation_start_time = 0.0
                self._validate_joined_lobby_access()

    def _on_lobby_list_complete(self, ev: NetEvent):
        self._lobby_list_fetching = False
        self._lobby_list_fetch_start_time = 0.0

        new_entries = self._pending_lobby_list[:]
        self._pending_lobby_list.clear()

        old_map: dict[int, dict] = {}
        for old_lobby in self._lobby_list:
            old_id = int(old_lobby.get('id', 0) or old_lobby.get('lobby_id', 0) or 0)
            if old_id:
                old_map[old_id] = old_lobby

        new_map: dict[int, dict] = {}
        for new_lobby in new_entries:
            new_id = int(new_lobby.get('id', 0) or new_lobby.get('lobby_id', 0) or 0)
            if new_id:
                new_map[new_id] = new_lobby

        merged: list[dict] = []
        for old_lobby in self._lobby_list:
            old_id = int(old_lobby.get('id', 0) or old_lobby.get('lobby_id', 0) or 0)
            if old_id not in new_map:
                continue
            fresh = new_map[old_id]
            old_lobby['members'] = fresh.get('members', old_lobby.get('members', '?'))
            old_lobby['max_members'] = fresh.get('max_members', old_lobby.get('max_members', 2))
            old_lobby['name'] = fresh.get('name') or old_lobby.get('name', '')
            old_lobby['host_name'] = fresh.get('host_name') or old_lobby.get('host_name', old_lobby.get('name', ''))
            old_lobby['sub_mode'] = fresh.get('sub_mode', old_lobby.get('sub_mode', self.selected_submode))
            old_vis = str(old_lobby.get('visibility', 'unknown') or 'unknown').lower()
            new_vis = str(fresh.get('visibility', 'unknown') or 'unknown').lower()
            if new_vis not in ('unknown', 'stale_unknown') or old_vis in ('unknown', 'stale_unknown'):
                old_lobby['visibility'] = fresh.get('visibility', old_lobby.get('visibility'))
                old_lobby['requires_code'] = fresh.get('requires_code', old_lobby.get('requires_code'))
                old_lobby['code'] = fresh.get('code', old_lobby.get('code', ''))
                old_lobby['lobby_code'] = fresh.get('lobby_code', fresh.get('code', old_lobby.get('lobby_code', '')))
                old_lobby['metadata_ready'] = fresh.get('metadata_ready', old_lobby.get('metadata_ready'))
            merged.append(old_lobby)

        for new_id, new_lobby in new_map.items():
            if new_id not in old_map:
                merged.append(new_lobby)

        self._lobby_list = merged

        # Kod ile arama yapılıyorsa eşleştir
        if self._searching_by_code:
            pending_code = self._search_code
            self._searching_by_code = False
            self._code_search_retry_use_full_scan = False
            matched_lobby_id, pending_metadata, ambiguous_match = self._find_lobby_match_by_code(pending_code)
            if matched_lobby_id:
                self._code_search_retry_count = 0
                self._join_target_lobby_id = 0
                self._remember_private_join_authorization(matched_lobby_id, pending_code)
                self.net.join_lobby(matched_lobby_id)
                self._status_msg = t('joining_lobby', 'Lobiye katılınıyor...')
                self._status_timer = 2.0
            elif ambiguous_match:
                self._code_search_retry_count = 0
                self._code_search_retry_timer = 0.0
                self._code_search_retry_code = ''
                self._join_code_error = t('lobby_code_ambiguous', 'Bu kod birden fazla lobiyle eslesiyor')
            elif not self._lobby_list or pending_metadata:
                self._code_search_fail_or_retry()
            else:
                self._code_search_retry_count = 0
                self._code_search_retry_timer = 0.0
                self._code_search_retry_code = ''
                self._join_code_error = t('code_not_found', 'Lobi bulunamadı')
            self._search_code = ''
            return

        self._refresh_unknown_lobby_entries()
        display_entries = self._get_lobby_entries_for_display()
        self._lobby_list_scroll = min(
            max(0, getattr(self, '_lobby_list_scroll', 0)),
            max(0, len(display_entries) - 1),
        )

    def _on_join_requested(self, ev: NetEvent):
        lobby_id = getattr(ev, 'steam_id', 0) or 0
        if lobby_id:
            self._invite_authorized_lobby_id = int(lobby_id)
            self.net.join_lobby(lobby_id)
            self._status_msg = t('joining_lobby', 'Lobiye katılınıyor...')
            self._status_timer = 2.0

    def _on_lobby_error(self, ev: NetEvent):
        self.online_state = OnlineCoopState.LOBBY_MENU
        self._lobby_list_fetching = False
        self._lobby_list_fetch_start_time = 0.0
        self._status_msg = t('lobby_create_failed', 'Lobi oluşturulamadı!')
        self._status_timer = 3.0

    def _on_lobby_list_error(self, ev: NetEvent):
        self._lobby_list_fetching = False
        self._lobby_list_fetch_start_time = 0.0
        if self._searching_by_code:
            self._searching_by_code = False
            self._code_search_fail_or_retry()
            return
        self._status_msg = t('lobby_list_error', 'Lobi listesi alınamadı')
        self._status_timer = 3.0

    def _on_session_accepted(self, ev: NetEvent):
        self._session_established = True
        self._session_ping_backoff_ms = 0.0
        self._session_ping_timer = 0.0
        print(f"[OnlineCoop] P2P session kabul edildi: {ev.steam_id}")
        if self.online_state == OnlineCoopState.READY_CHECK and self.my_ready and not self.opponent_ready:
            self._send_ready_signal(reason='session_accepted')

    def _on_session_rejected(self, ev: NetEvent):
        self._session_established = False
        print(f"[OnlineCoop] P2P session REDDEDİLDİ: {ev.steam_id} sebep={ev.data}")
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

    # ── Lobby metadata / session hardening helpers ─────────────────────

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
            for lobby in collection:
                existing_id = int(lobby.get('id', 0) or lobby.get('lobby_id', 0) or 0)
                if existing_id != lobby_id:
                    continue
                lobby['id'] = lobby_id
                lobby['lobby_id'] = lobby_id
                lobby['name'] = snapshot.get('name') or lobby.get('name') or lobby.get('host_name') or 'Host'
                lobby['host_name'] = lobby['name']
                lobby['code'] = snapshot.get('code', lobby.get('code', ''))
                lobby['lobby_code'] = lobby['code']
                lobby['visibility'] = snapshot.get('visibility', lobby.get('visibility', 'unknown'))
                lobby['requires_code'] = bool(snapshot.get('requires_code', lobby.get('requires_code', False)))
                lobby['metadata_ready'] = bool(snapshot.get('metadata_ready', lobby.get('metadata_ready', False)))
                updated = True
        return updated

    def _upsert_lobby_entry(self, collection_name: str, entry: dict):
        collection = getattr(self, collection_name, None)
        if not isinstance(collection, list):
            return
        lobby_id = int(entry.get('id', 0) or entry.get('lobby_id', 0) or 0)
        if not lobby_id:
            return
        entry['id'] = lobby_id
        entry['lobby_id'] = lobby_id
        for index, lobby in enumerate(collection):
            existing_id = int(lobby.get('id', 0) or lobby.get('lobby_id', 0) or 0)
            if existing_id == lobby_id:
                collection[index] = entry
                return
        collection.append(entry)

    def _remember_deferred_lobby_entry(self, entry: dict):
        lobby_id = int(entry.get('id', 0) or entry.get('lobby_id', 0) or 0)
        if lobby_id:
            self._deferred_lobby_entries[lobby_id] = entry

    def _iter_known_lobby_entries(self) -> list[dict]:
        seen_ids: set[int] = set()
        entries: list[dict] = []
        for collection in (
            getattr(self, '_lobby_list', []),
            list(getattr(self, '_deferred_lobby_entries', {}).values()),
            getattr(self, '_pending_lobby_list', []),
        ):
            for lobby in collection:
                lobby_id = int(lobby.get('id', 0) or lobby.get('lobby_id', 0) or 0)
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
            sanitized_payload = {}
            for key, value in deferred_entry.items():
                if key in ('requires_code', 'metadata_ready'):
                    if isinstance(value, str):
                        sanitized_payload[key] = value
                elif key == 'visibility' and value == 'unknown':
                    continue
                else:
                    sanitized_payload[key] = value
            effective_snapshot = self._get_lobby_metadata_snapshot(
                normalized_lobby_id,
                sanitized_payload or None,
                prefer_live=True,
            )
        if effective_snapshot.get('visibility') == 'unknown':
            return False

        promoted_entry = dict(deferred_entry)
        promoted_entry['name'] = effective_snapshot.get('name') or deferred_entry.get('name') or 'Host'
        promoted_entry['host_name'] = promoted_entry['name']
        promoted_entry['code'] = effective_snapshot.get('code', deferred_entry.get('code', ''))
        promoted_entry['lobby_code'] = promoted_entry['code']
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
        now = time.time()
        last_request = float(self._unknown_lobby_metadata_requests.get(normalized_lobby_id, 0.0) or 0.0)
        min_interval = max(0.1, float(self._UNKNOWN_LOBBY_DATA_REQUEST_INTERVAL_S))
        if last_request > 0.0 and (now - last_request) < min_interval:
            return False
        request_fn = getattr(self.net, 'request_lobby_data', None)
        if not callable(request_fn):
            return False
        try:
            requested = bool(request_fn(normalized_lobby_id))
        except Exception:
            return False
        if requested:
            self._unknown_lobby_metadata_requests[normalized_lobby_id] = now
        return requested

    def _clear_lobby_metadata_refresh_request(self, lobby_id: int | None = None):
        normalized_lobby_id = int(lobby_id or 0)
        if normalized_lobby_id:
            self._unknown_lobby_metadata_requests.pop(normalized_lobby_id, None)
            return
        self._unknown_lobby_metadata_requests.clear()

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
        self._join_code_suppress_textinput = ''
        self._status_msg = t('enter_lobby_code', 'Lobi kodu girin')
        self._status_timer = 2.5

    def _start_lobby_browser_join(self, lobby_id: int, snapshot: dict | None = None) -> bool:
        normalized_lobby_id = int(lobby_id or 0)
        if not normalized_lobby_id:
            return False
        effective_snapshot = snapshot or self._get_lobby_metadata_snapshot(
            normalized_lobby_id, prefer_live=True)
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
        effective_snapshot = snapshot or self._get_lobby_metadata_snapshot(
            normalized_lobby_id, prefer_live=True)
        return self._start_lobby_browser_join(normalized_lobby_id, effective_snapshot)

    def _reject_private_lobby_join(self):
        rejected_lobby_id = int(getattr(self.net, 'lobby_id', 0) or 0)
        self._return_to_coop_lobby_menu()
        if rejected_lobby_id:
            self._join_target_lobby_id = rejected_lobby_id
            self._join_code_active = True
        self._join_code_input = ''
        self._join_code_error = ''
        self._status_msg = t(
            'private_lobby_code_required',
            'Bu özel lobi için geçerli kod veya davet gerekli',
        )
        self._status_timer = 3.0

    def _validate_joined_lobby_access(self) -> bool:
        current_lobby_id = int(getattr(self.net, 'lobby_id', 0) or 0)
        if not current_lobby_id:
            return True
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
            if self._invite_authorized_lobby_id == current_lobby_id:
                self._clear_private_join_authorization(current_lobby_id)
                self._lobby_access_validated_id = current_lobby_id
                return True
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
        pending_code = str(
            getattr(self, '_code_search_retry_code', '')
            or (getattr(self, '_search_code', '') if getattr(self, '_searching_by_code', False) else '')
        ).strip()
        if not pending_code:
            return False
        effective_snapshot = snapshot or self._get_lobby_metadata_snapshot(lobby_id, prefer_live=True)
        if not effective_snapshot.get('metadata_ready'):
            return False
        if str(effective_snapshot.get('code', '') or '').strip() != pending_code:
            return False
        self._code_search_retry_count = 0
        self._code_search_retry_timer = 0.0
        self._code_search_retry_code = ''
        self._code_search_retry_use_full_scan = False
        self._searching_by_code = False
        self._search_code = ''
        self._join_target_lobby_id = 0
        self._remember_private_join_authorization(lobby_id, pending_code)
        self.net.join_lobby(lobby_id)
        self._status_msg = t('joining_lobby', 'Lobiye katılınıyor...')
        self._status_timer = 2.0
        return True

    def _promote_to_ready_check(self, opponent_id: int = 0, opponent_name: str = '', play_sound: bool = False):
        normalized_opponent_id = int(opponent_id or getattr(self.net, 'opponent_steam_id', 0) or 0)
        state_changed = self.online_state != OnlineCoopState.READY_CHECK
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
        self.online_state = OnlineCoopState.READY_CHECK
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
        if self.online_state not in (OnlineCoopState.WAITING, OnlineCoopState.READY_CHECK):
            return False
        try:
            members = list(self.net.get_lobby_members() or [])
        except Exception:
            return False
        my_id = int(getattr(self.net, 'my_steam_id', 0) or 0)
        opponent_ids = [
            int(member_id)
            for member_id in members
            if int(member_id or 0) and int(member_id or 0) != my_id
        ]
        if not opponent_ids:
            return False
        opponent_id = opponent_ids[0]
        opponent_name = getattr(self.net, 'opponent_name', '')
        if not opponent_name:
            try:
                opponent_name = self.net._get_name(opponent_id)
            except Exception:
                opponent_name = ''
        self._promote_to_ready_check(
            opponent_id,
            opponent_name,
            play_sound=self.online_state == OnlineCoopState.WAITING,
        )
        return True

    def _find_lobby_match_by_code(self, code: str) -> tuple[int, bool, bool]:
        normalized_code = (code or '').strip()
        if not normalized_code:
            return 0, False, False
        target_lobby_id = int(getattr(self, '_join_target_lobby_id', 0) or 0)
        matched_ids: list[int] = []
        pending_metadata = False
        for lobby in self._iter_known_lobby_entries():
            lobby_id = int(lobby.get('id', 0) or lobby.get('lobby_id', 0) or 0)
            if not lobby_id:
                continue
            if target_lobby_id and lobby_id != target_lobby_id:
                continue
            raw_mode = str(lobby.get('mode', '') or '').strip().lower()
            if not raw_mode:
                try:
                    raw_mode = str(self.net.get_lobby_data_for(lobby_id, 'mode') or '').strip().lower()
                except Exception:
                    raw_mode = ''
            if raw_mode and raw_mode != 'coop':
                continue
            snapshot = self._get_lobby_metadata_snapshot(
                lobby_id,
                {
                    'host_name': lobby.get('name') or lobby.get('host_name', ''),
                    'lobby_code': lobby.get('code') or lobby.get('lobby_code', ''),
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
            snapshot_code = str(snapshot.get('code', '') or '').strip()
            if snapshot_code and snapshot_code == normalized_code:
                if lobby_id not in matched_ids:
                    matched_ids.append(lobby_id)
                continue
            try:
                if generate_lobby_code(lobby_id) == normalized_code:
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

    def _refresh_unknown_lobby_entries(self):
        if not getattr(self, '_net_initialized', False):
            return
        for lobby in self._lobby_list:
            visibility = str(lobby.get('visibility', '') or '').lower()
            if visibility not in ('unknown', 'stale_unknown'):
                continue
            lobby_id = int(lobby.get('id', 0) or lobby.get('lobby_id', 0) or 0)
            if not lobby_id:
                continue
            self._request_lobby_metadata_refresh(lobby_id)
            snapshot = self._get_lobby_metadata_snapshot(lobby_id, prefer_live=True)
            if snapshot.get('visibility') not in (None, '', 'unknown'):
                lobby['name'] = snapshot.get('name') or lobby.get('name', '')
                lobby['host_name'] = lobby['name']
                lobby['code'] = snapshot.get('code', lobby.get('code', ''))
                lobby['lobby_code'] = lobby['code']
                lobby['visibility'] = snapshot.get('visibility', 'unknown')
                lobby['requires_code'] = bool(snapshot.get('requires_code', False))
                lobby['metadata_ready'] = bool(snapshot.get('metadata_ready', False))
                self._deferred_lobby_entries.pop(lobby_id, None)
                self._clear_lobby_metadata_refresh_request(lobby_id)
                self._complete_pending_browser_join(lobby_id, snapshot)
                continue

            try:
                raw_code = self.net.get_lobby_data_for(lobby_id, 'lobby_code')
                raw_code_full = self.net.get_lobby_data_for(lobby_id, 'lobby_code_full')
                raw_game = self.net.get_lobby_data_for(lobby_id, 'game')
                raw_mode = self.net.get_lobby_data_for(lobby_id, 'mode')
            except Exception:
                raw_code = ''
                raw_code_full = ''
                raw_game = ''
                raw_mode = ''

            if raw_mode and str(raw_mode).lower() != 'coop':
                continue
            if raw_code or raw_code_full:
                lobby['visibility'] = 'private'
                lobby['requires_code'] = True
                lobby['code'] = raw_code or _resolve_private_lobby_code(lobby_id, True, '')
                lobby['lobby_code'] = lobby['code']
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
            elif raw_game == 'quadrix':
                try:
                    raw_meta_ready = self.net.get_lobby_data_for(lobby_id, 'metadata_ready')
                    raw_vis = self.net.get_lobby_data_for(lobby_id, 'visibility')
                    raw_req = self.net.get_lobby_data_for(lobby_id, 'requires_code')
                except Exception:
                    raw_meta_ready = ''
                    raw_vis = ''
                    raw_req = ''
                if raw_meta_ready == '1':
                    if raw_vis == 'private' or raw_req == '1':
                        lobby['visibility'] = 'private'
                        lobby['requires_code'] = True
                        lobby['code'] = _resolve_private_lobby_code(lobby_id, True, '')
                    elif raw_vis == 'public' or raw_req == '0':
                        lobby['visibility'] = 'public'
                        lobby['requires_code'] = False
                        lobby['code'] = ''
                    else:
                        continue
                    lobby['lobby_code'] = lobby['code']
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

    def _send_session_ping(self) -> bool:
        if not self._net_initialized:
            return False
        ok = self.net.send({'type': 'session_ping'}, reliable=True, channel=CHANNEL_CONTROL)
        if ok:
            self._session_ping_backoff_ms = 0.0
        return bool(ok)

    def _send_ready_signal(self, reason: str = '') -> bool:
        if not self._net_initialized:
            return False
        has_opponent_id = bool(getattr(self.net, 'opponent_steam_id', 0))
        if not has_opponent_id:
            self._ready_send_pending = True
            ok = bool(self.net.send_ready())
            if ok:
                self._ready_send_pending = False
            return ok
        if not self._session_established:
            self._ready_send_pending = True
            self._send_session_ping()
            ready_ok = bool(self.net.send_ready())
            if ready_ok:
                self._ready_send_pending = False
            return ready_ok
        ok = bool(self.net.send_ready())
        if ok:
            self._ready_send_pending = False
        return ok

    def _return_to_coop_lobby_menu(self):
        try:
            self.net.leave_lobby()
        except Exception:
            pass
        self.online_state = OnlineCoopState.LOBBY_MENU
        self.role = ''
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
        self.game_over = False
        self.paused = False
        self.coop_game = None
        self._guest_board_cache = None
        self._guest_piece_cache = None
        self._guest_score_cache = {}
        self._guest_pending_inputs = []
        self._guest_input_seq = 0
        self._last_input_ack_seq = 0
        self._last_guest_input_seq = 0
        self._guest_board_seq = -1
        self._guest_piece_seq = -1
        self._last_host_guest_piece_ack_seq = 0
        self._guest_piece_unacked_since = 0.0
        self._guest_render_board_seq = -1
        self._guest_render_piece_seq = -1
        self._guest_last_authoritative_piece_elapsed_ms = 0.0
        self._guest_local_prediction_ms = 0.0
        self._lobby_code = ''
        self._lobby_id_str = ''
        self._join_code_active = False
        self._join_code_input = ''
        self._join_code_error = ''
        self._join_code_suppress_textinput = ''
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
        self._pending_reval_last_check_time = 0.0
        self._lobby_access_validated_id = 0
        self._lobby_list_fetching = False
        self._lobby_list_fetch_start_time = 0.0
        self._auto_lobby_refresh_requested = False
        self._auto_lobby_refresh_timer = 0.0
        self._pending_lobby_list.clear()
        self._deferred_lobby_entries.clear()
        self._clear_lobby_metadata_refresh_request()

    # ============================================================
    #  LOBİ AKSIYONLARI
    # ============================================================

    def _create_lobby(self, public: bool = False):
        self._creating_public_lobby = bool(public)
        self.net.create_lobby(public=public)

    def _request_lobby_list(self) -> bool:
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
        try:
            add_filter = getattr(self.net, 'add_lobby_search_filter', None)
            if callable(add_filter):
                add_filter('game', 'quadrix')
                add_filter('mode', 'coop')
            self.net.request_lobby_list(worldwide=True)
        except Exception:
            self._lobby_list_fetching = False
            self._lobby_list_fetch_start_time = 0.0
            return False
        return True

    def _set_lobby_list_filter(self, lobby_filter: str, refresh: bool = True) -> bool:
        """Lobi listesi filtresini güncelle; ham listeyi silmeden ekranda filtrele."""
        normalized = 'public' if str(lobby_filter).lower() == 'public' else 'all'
        changed = normalized != getattr(self, '_lobby_list_filter', 'all')
        self._lobby_list_filter = normalized
        if changed:
            self._lobby_list_scroll = 0
        if refresh:
            return self._request_lobby_list()
        return changed

    def _do_invite_friend(self):
        """Steam overlay davetini aç; lobi yoksa önce özel lobi oluştur."""
        if not self._net_initialized and not self._init_networking():
            self._status_msg = t('steam_not_available', 'Steam bağlantısı kurulamadı!')
            self._status_timer = 3.0
            return

        if (
            getattr(self.net, 'available', True) is False
            or getattr(self.net, 'initialized', True) is False
        ):
            self._status_msg = t('steam_not_available', 'Steam bağlantısı kurulamadı!')
            self._status_timer = 3.0
            return

        if not getattr(self.net, 'lobby_id', 0):
            self._invite_after_lobby = True
            self._create_lobby(public=False)
            self._status_msg = t('creating_lobby_invite', 'Lobi oluşturuluyor...')
            self._status_timer = 2.0
            return

        invite_ok = False
        try:
            invite_fn = getattr(self.net, 'invite_friend', None)
            if callable(invite_fn):
                invite_fn()
                invite_ok = True
        except Exception:
            invite_ok = False

        if not invite_ok:
            try:
                invite_ok = bool(_activate_invite_dialog(getattr(self.net, 'lobby_id', 0)))
            except Exception:
                invite_ok = False

        self._status_msg = (
            t('invite_sent', 'Steam davet penceresi açıldı')
            if invite_ok
            else t('invite_open_failed', 'Steam davet penceresi açılamadı')
        )
        self._status_timer = 2.5
        try:
            self.sound.play('click')
        except Exception:
            pass

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
            self.net.request_lobby_list(worldwide=True)
            return
        self.net.search_lobby_by_code(normalized_code)

    def _code_search_fail_or_retry(self):
        if self._code_search_retry_count < 2 and self._search_code:
            self._code_search_retry_count += 1
            self._code_search_retry_timer = 1200.0
            self._code_search_retry_code = self._search_code
            self._code_search_retry_use_full_scan = True
            self._status_msg = t('searching_by_code', 'Lobi kodu aranıyor...')
            self._status_timer = 3.0
        else:
            self._code_search_retry_count = 0
            self._code_search_retry_timer = 0.0
            self._code_search_retry_code = ''
            self._code_search_retry_use_full_scan = False
            self._search_code = ''
            self._join_code_error = t('code_not_found', 'Lobi bulunamadı')
            self._status_msg = t('lobby_not_found_by_code', 'Bu kodla lobi bulunamadı')
            self._status_timer = 3.0

    def _copy_lobby_code(self):
        code = str(getattr(self, '_lobby_code', '') or '').strip()
        if not code:
            self._status_msg = t('no_lobby_code_to_copy', 'Bu lobide paylaşım kodu yok')
            self._status_timer = 2.0
            return
        ok = self._copy_to_clipboard(code)
        self._status_msg = (
            t('code_copied', 'Lobi kodu kopyalandı!')
            if ok
            else f'{t("lobby_code_label", "Lobi Kodu")}: {code}'
        )
        self._status_timer = 2.5
        try:
            self.sound.play('click')
        except Exception:
            pass

    def _copy_lobby_id(self):
        lobby_id = str(
            getattr(self, '_lobby_id_str', '')
            or getattr(self.net, 'lobby_id', '')
            or ''
        ).strip()
        if not lobby_id:
            return
        ok = self._copy_to_clipboard(lobby_id)
        self._status_msg = (
            t('lobby_id_copied', 'Lobi ID kopyalandı!')
            if ok
            else f'ID: {lobby_id}'
        )
        self._status_timer = 2.5
        try:
            self.sound.play('click')
        except Exception:
            pass

    def _copy_to_clipboard(self, text: str) -> bool:
        """Metni sistem panosuna güvenli şekilde kopyala."""
        import subprocess
        try:
            if sys.platform == 'win32':
                create_no_window = int(getattr(subprocess, 'CREATE_NO_WINDOW', 0) or 0)
                process = subprocess.Popen(
                    ['clip'],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=create_no_window,
                )
                try:
                    process.communicate(str(text).encode('utf-16'), timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                    return False
                return process.returncode == 0
            if sys.platform == 'darwin':
                process = subprocess.Popen(
                    ['pbcopy'],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                try:
                    process.communicate(str(text).encode('utf-8'), timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                    return False
                return process.returncode == 0

            for command in (
                ['xclip', '-selection', 'clipboard'],
                ['wl-copy'],
                ['xsel', '--clipboard', '--input'],
            ):
                try:
                    process = subprocess.Popen(
                        command,
                        stdin=subprocess.PIPE,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                except (FileNotFoundError, OSError):
                    continue
                try:
                    process.communicate(str(text).encode('utf-8'), timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                    continue
                except Exception:
                    continue
                if process.returncode == 0:
                    return True
        except Exception:
            return False
        return False

    def _paste_from_clipboard(self) -> str:
        """Sistem panosundan kısa metin oku."""
        import subprocess
        try:
            if sys.platform == 'win32':
                create_no_window = int(getattr(subprocess, 'CREATE_NO_WINDOW', 0) or 0)
                result = subprocess.run(
                    ['powershell', '-command', 'Get-Clipboard'],
                    capture_output=True,
                    text=True,
                    timeout=2,
                    creationflags=create_no_window,
                )
                return result.stdout.strip()
            if sys.platform == 'darwin':
                result = subprocess.run(
                    ['pbpaste'],
                    capture_output=True,
                    text=True,
                    timeout=2,
                )
                return result.stdout.strip()
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
                except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
                    continue
                if result.returncode == 0:
                    return result.stdout.strip()
        except Exception:
            return ''
        return ''

    # ============================================================
    #  ANA DÖNGÜ: handle_input / update / draw
    # ============================================================

    def handle_input(self):
        """Pygame event'lerini işle. False=çık, 'menu'=menüye dön."""
        for event in pygame.event.get():
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

            if event.type == pygame.KEYDOWN:
                # Join code text input
                if self._join_code_active and self.online_state == OnlineCoopState.LOBBY_MENU:
                    if event.key == pygame.K_BACKSPACE:
                        self._join_code_input = self._join_code_input[:-1]
                        self._join_code_error = ''
                        continue
                    elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        self._try_join_by_code()
                        continue
                    elif event.key == pygame.K_ESCAPE:
                        self._join_code_active = False
                        self._join_code_input = ''
                        self._join_code_error = ''
                        self._join_code_suppress_textinput = ''
                        continue
                    elif event.key == pygame.K_v and (getattr(event, 'mod', 0) & pygame.KMOD_CTRL):
                        pasted = self._paste_from_clipboard()
                        if pasted:
                            digits = ''.join(ch for ch in pasted if ch.isdigit())
                            if digits:
                                self._join_code_input = digits[:6]
                                self._join_code_error = ''
                        continue
                    elif event.unicode and event.unicode.isdigit():
                        digit = event.unicode
                        if len(self._join_code_input) < 6:
                            self._join_code_input += digit
                            self._join_code_error = ''
                            # SDL/Steam builds often emit KEYDOWN unicode and
                            # TEXTINPUT for one physical key. Keep KEYDOWN as a
                            # fallback, then suppress the matching text event.
                            self._join_code_suppress_textinput = digit
                        continue

                # Gameplay input during PLAYING state
                if self.online_state == OnlineCoopState.PLAYING:
                    self._handle_gameplay_keydown(event)
                    continue

                if event.key == pygame.K_ESCAPE:
                    if self.online_state == OnlineCoopState.LOBBY_MENU:
                        return 'menu'
                    elif self.online_state in (
                        OnlineCoopState.WAITING,
                        OnlineCoopState.READY_CHECK,
                    ):
                        self._return_to_coop_lobby_menu()
                    elif self.online_state == OnlineCoopState.DISCONNECTED:
                        self._return_to_coop_lobby_menu()
                    elif self.online_state == OnlineCoopState.GAME_OVER:
                        self._return_to_coop_lobby_menu()

                if self.online_state == OnlineCoopState.LOBBY_MENU:
                    if event.key in (pygame.K_1, pygame.K_RETURN, pygame.K_KP_ENTER):
                        if self._init_networking():
                            self._create_lobby(public=False)
                            self._status_msg = t('creating_lobby', 'Özel lobi oluşturuluyor...')
                            self._status_timer = 2.0
                    elif event.key == pygame.K_2:
                        if self._init_networking():
                            self._create_lobby(public=True)
                            self._status_msg = t('creating_lobby', 'Herkese açık lobi oluşturuluyor...')
                            self._status_timer = 2.0
                    elif event.key == pygame.K_3:
                        self._request_lobby_list()
                    elif event.key == pygame.K_j:
                        self._join_target_lobby_id = 0
                        self._join_code_active = True
                        self._join_code_input = ''
                        self._join_code_error = ''
                        self._join_code_suppress_textinput = ''
                    elif event.key == pygame.K_i:
                        self._do_invite_friend()
                elif self.online_state == OnlineCoopState.WAITING:
                    if event.key == pygame.K_i:
                        self._do_invite_friend()
                    elif event.key == pygame.K_c and self._lobby_code:
                        self._copy_lobby_code()
                elif self.online_state == OnlineCoopState.READY_CHECK:
                    if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        if not self.my_ready:
                            self.my_ready = True
                            self._send_ready_signal(reason='keypress_enter')
                            self._check_both_ready()

            elif event.type == pygame.KEYUP:
                if self.online_state == OnlineCoopState.PLAYING:
                    self._handle_gameplay_keyup(event)

            if event.type == pygame.TEXTINPUT and self._join_code_active:
                for ch in event.text:
                    if ch.isdigit() and len(self._join_code_input) < 6:
                        if ch == getattr(self, '_join_code_suppress_textinput', ''):
                            self._join_code_suppress_textinput = ''
                            continue
                        self._join_code_input += ch
                        self._join_code_error = ''

            if event.type == pygame.VIDEORESIZE:
                self.window_width = event.w
                self.window_height = event.h
                if self.coop_game:
                    self.coop_game.screen = self.screen
                    self.coop_game.window_width = event.w
                    self.coop_game.window_height = event.h

            # Mouse click
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                result = self._handle_mouse_click(event.pos)
                if result is not None:
                    return result

            if event.type == pygame.MOUSEWHEEL:
                self._handle_scroll(event)

        return True

    # ── Gameplay input (PLAYING state) ──

    # Online players each have their own keyboard, so both roles accept the
    # usual WASD scheme and the arrow-key scheme.
    _HOST_KEYS = {
        pygame.K_a: 'move_left',
        pygame.K_LEFT: 'move_left',
        pygame.K_d: 'move_right',
        pygame.K_RIGHT: 'move_right',
        pygame.K_s: 'soft_drop_start',
        pygame.K_DOWN: 'soft_drop_start',
        pygame.K_w: 'rotate',
        pygame.K_UP: 'rotate',
        pygame.K_LSHIFT: 'hard_drop',
        pygame.K_SPACE: 'hard_drop',
        pygame.K_e: 'hold',
        pygame.K_RSHIFT: 'hold',
    }
    _HOST_KEYUP = {
        pygame.K_a: 'das_stop_left',
        pygame.K_LEFT: 'das_stop_left',
        pygame.K_d: 'das_stop_right',
        pygame.K_RIGHT: 'das_stop_right',
        pygame.K_s: 'soft_drop_stop',
        pygame.K_DOWN: 'soft_drop_stop',
    }
    _GUEST_KEYS = {
        pygame.K_a: 'move_left',
        pygame.K_LEFT: 'move_left',
        pygame.K_d: 'move_right',
        pygame.K_RIGHT: 'move_right',
        pygame.K_s: 'soft_drop_start',
        pygame.K_DOWN: 'soft_drop_start',
        pygame.K_w: 'rotate',
        pygame.K_UP: 'rotate',
        pygame.K_LSHIFT: 'hard_drop',
        pygame.K_SPACE: 'hard_drop',
        pygame.K_e: 'hold',
        pygame.K_RSHIFT: 'hold',
    }
    _GUEST_KEYUP = {
        pygame.K_a: 'das_stop_left',
        pygame.K_LEFT: 'das_stop_left',
        pygame.K_d: 'das_stop_right',
        pygame.K_RIGHT: 'das_stop_right',
        pygame.K_s: 'soft_drop_stop',
        pygame.K_DOWN: 'soft_drop_stop',
    }

    def _handle_gameplay_keydown(self, event):
        """PLAYING state'te tuş basımı."""
        if event.key == pygame.K_ESCAPE:
            # Pause isteği
            if self.role == 'host' and self.coop_game:
                self._toggle_pause_safe()
            elif self.role == 'guest':
                self._send_guest_input('pause_request')
            return

        if self._gameplay_input_blocked():
            return

        if self.role == 'host':
            action = self._HOST_KEYS.get(event.key)
            if action and self.coop_game:
                held_keys = getattr(self, '_held_gameplay_keys', None)
                if not isinstance(held_keys, set):
                    held_keys = set()
                    self._held_gameplay_keys = held_keys
                if event.key in held_keys:
                    return
                held_keys.add(event.key)
                self.coop_game.inject_remote_input('P1', action)
                self._push_piece_state_if_changed()
        elif self.role == 'guest':
            action = self._GUEST_KEYS.get(event.key)
            if action:
                held_keys = getattr(self, '_held_gameplay_keys', None)
                if not isinstance(held_keys, set):
                    held_keys = set()
                    self._held_gameplay_keys = held_keys
                if event.key in held_keys:
                    return
                held_keys.add(event.key)
                self._predict_guest_input(action)
                if self._guest_action_requires_host_control(action):
                    self._send_guest_input(action)
                    self._flush_guest_piece_mirror_for_action(action)

    def _handle_gameplay_keyup(self, event):
        """PLAYING state'te tuş bırakma."""
        if self.role == 'host':
            try:
                self._held_gameplay_keys.discard(event.key)
            except Exception:
                pass
            if self._gameplay_input_blocked():
                return
            action = self._HOST_KEYUP.get(event.key)
            if action and self.coop_game:
                self.coop_game.inject_remote_input('P1', action)
                self._push_piece_state_if_changed()
        elif self.role == 'guest':
            try:
                self._held_gameplay_keys.discard(event.key)
            except Exception:
                pass
            if self._gameplay_input_blocked():
                return
            action = self._GUEST_KEYUP.get(event.key)
            if action:
                self._predict_guest_input(action)
                if self._guest_action_requires_host_control(action):
                    self._send_guest_input(action)
                    self._flush_guest_piece_mirror_for_action(action)

    def _set_pause_state(self, paused: bool) -> None:
        self.paused = bool(paused)
        coop_game = getattr(self, 'coop_game', None)
        if coop_game is not None and hasattr(coop_game, 'paused'):
            try:
                coop_game.paused = bool(paused)
            except Exception:
                pass

    def _gameplay_input_blocked(self) -> bool:
        if self.online_state != OnlineCoopState.PLAYING:
            return False
        if bool(getattr(self, 'game_over', False)) or bool(getattr(self, 'paused', False)):
            return True
        coop_game = getattr(self, 'coop_game', None)
        if coop_game is None:
            return False
        return bool(getattr(coop_game, 'game_over', False) or getattr(coop_game, 'paused', False))

    def _toggle_pause_safe(self):
        """Host'ta güvenli pause toggle — cooldown ile race condition önlenir."""
        if self._pause_cooldown_timer > 0:
            return
        self._set_pause_state(not self.paused)
        self._freeze_active_gameplay_input()
        ev_name = 'pause' if self.paused else 'resume'
        self._send_game_event(ev_name)
        self._pause_cooldown_timer = self._PAUSE_COOLDOWN_MS

    def _freeze_active_gameplay_input(self):
        """Pause/disconnect geçişlerinde held movement state'lerini temizle."""
        try:
            self._held_gameplay_keys.clear()
        except Exception:
            pass
        coop_game = getattr(self, 'coop_game', None)
        if not coop_game:
            return
        for player_key in ('p1', 'p2'):
            for attr, value in (
                (f'{player_key}_soft_drop_active', False),
                (f'{player_key}_das_direction', 0),
                (f'{player_key}_das_timer', 0),
                (f'{player_key}_das_repeat_timer', 0),
                (f'{player_key}_das_charged', False),
            ):
                if hasattr(coop_game, attr):
                    try:
                        setattr(coop_game, attr, value)
                    except Exception:
                        pass

    def _handle_scroll(self, event):
        """Fare tekerleği — lobi listesi scroll."""
        if self.online_state != OnlineCoopState.LOBBY_MENU:
            return
        entries = self._get_lobby_entries_for_display()
        if entries:
            self._lobby_list_scroll = max(0, self._lobby_list_scroll - int(getattr(event, 'y', 0) or 0))

    def _handle_mouse_click(self, pos):
        """Lobi ekranlarında mouse tıklama."""
        pos = normalize_mouse_pos(pos) or pos
        for btn in self._lobby_buttons:
            r = btn.get('rect')
            action = btn.get('action')
            if r and action and r.collidepoint(pos):
                return self._execute_button_action(action)
        return None

    def _execute_button_action(self, action: str):
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
        elif action == 'invite_friend':
            self._do_invite_friend()
        elif action in ('toggle_join_code', 'join_by_code'):
            self._join_target_lobby_id = 0
            self._join_code_active = True
            self._join_code_input = ''
            self._join_code_error = ''
            self._join_code_suppress_textinput = ''
        elif action == 'join_code_field':
            self._join_code_active = True
        elif action in ('submit_join_code', 'join_code_submit'):
            self._try_join_by_code()
        elif action in ('refresh_list', 'find_match'):
            self._request_lobby_list()
        elif action == 'filter_all_lobbies':
            self._set_lobby_list_filter('all')
        elif action == 'filter_public_lobbies':
            self._set_lobby_list_filter('public')
        elif action == 'copy_lobby_code':
            self._copy_lobby_code()
        elif action == 'copy_lobby_id':
            self._copy_lobby_id()
        elif action == 'back':
            return 'menu'
        elif action.startswith('join_lobby:'):
            lobby_id_str = action.split(':', 1)[1]
            try:
                self._start_lobby_browser_join(int(lobby_id_str))
            except Exception:
                self._status_msg = t('lobby_error', 'Lobi işlemi başarısız oldu!')
                self._status_timer = 3.0
        elif action.startswith('join_private_lobby:'):
            lobby_id_str = action.split(':', 1)[1]
            try:
                self._open_private_lobby_code_prompt(int(lobby_id_str))
            except (ValueError, TypeError):
                self._join_target_lobby_id = 0
        elif action.startswith('resolve_lobby_join:'):
            lobby_id_str = action.split(':', 1)[1]
            try:
                self._start_lobby_browser_join(int(lobby_id_str))
            except (ValueError, TypeError):
                pass
        elif action == 'ready':
            if not self.my_ready:
                self.my_ready = True
                self._send_ready_signal(reason='button_ready')
                self._check_both_ready()
        elif action == 'back_to_lobby':
            self._return_to_coop_lobby_menu()
            self._my_rematch = False
            self._opponent_rematch = False
        elif action == 'rematch':
            self._my_rematch = True
            self.net.send({'type': MsgType.REMATCH}, reliable=True, channel=CHANNEL_CONTROL)
            self._check_both_rematch()
        return None

    def _try_join_by_code(self):
        """Lobi kodunu kullanarak lobiye katılmayı dene."""
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

            self._join_target_lobby_id = 0
            self._remember_private_join_authorization(target_lobby_id, code)
            self.net.join_lobby(target_lobby_id)
            self._status_msg = t('joining_lobby', 'Lobiye katılınıyor...')
            self._status_timer = 2.0
            self._join_code_active = False
            return

        self._code_search_retry_count = 0
        self._code_search_retry_timer = 0.0
        self._code_search_retry_code = ''
        self._code_search_retry_use_full_scan = False
        self._begin_code_search(code, fallback_scan=False)
        self._join_code_error = ''
        self._status_msg = t('searching_by_code', 'Kod ile aranıyor...')
        self._status_timer = 3.0
        self._join_code_active = False

    def update(self, delta_time: int):
        """Her frame çağrılır."""
        # Auto-connect networking
        if not self._net_initialized:
            if self._auto_connect_retry_timer > 0:
                self._auto_connect_retry_timer = max(0.0, self._auto_connect_retry_timer - float(delta_time))
            if not self._auto_connect_attempted or self._auto_connect_retry_timer <= 0:
                self._auto_connect_attempted = True
                if not self._init_networking():
                    self._auto_connect_retry_timer = 2000.0

        # Network tick
        if self._net_initialized:
            try:
                self.net.tick()
                self._process_messages()
            except Exception:
                pass

        # Playlist tick — wrapper SAHİP. Host CoopGame.update() de aynı
        # `self.sound` üzerinde tick edebileceğinden çift tick riskini
        # ortadan kaldırmak için wrapper tek otoriter tick yolu olur ve host
        # CoopGame'in iç tick'i `_suppress_internal_music_tick` ile
        # bastırılır (bkz. CoopGame.update). Guest tarafında zaten
        # `sound_enabled=False` olduğu için CoopGame'in iç tick'i çalışmıyor;
        # wrapper tick'i playlist ilerlemesinin tek garantisi.
        try:
            if self.online_state == OnlineCoopState.PLAYING and getattr(self, 'sound', None):
                update_playlist = getattr(self.sound, 'update_music_playlist', None)
                if callable(update_playlist):
                    update_playlist()
        except Exception:
            pass

        # Auto-refresh lobby list
        if (
            self.online_state == OnlineCoopState.LOBBY_MENU
            and self._net_initialized
        ):
            if not self._auto_lobby_refresh_requested:
                if self._request_lobby_list():
                    self._auto_lobby_refresh_requested = True
                    self._auto_lobby_refresh_timer = self._auto_lobby_refresh_interval
            else:
                self._auto_lobby_refresh_timer = max(0.0, self._auto_lobby_refresh_timer - float(delta_time))
                if (
                    self._auto_lobby_refresh_timer <= 0.0
                    and not self._lobby_list_fetching
                    and not self._searching_by_code
                ):
                    self._request_lobby_list()

        if (
            self._lobby_list_fetching
            and self._lobby_list_fetch_start_time > 0
            and (time.time() - self._lobby_list_fetch_start_time) > 8.0
        ):
            print("[OnlineCoop] Lobi listesi fetch timeout (8s) — sıfırlanıyor")
            self._lobby_list_fetching = False
            if self._searching_by_code:
                self._searching_by_code = False
                self._code_search_fail_or_retry()
            elif not self._lobby_list:
                self._lobby_list = self._pending_lobby_list[:]
                self._pending_lobby_list.clear()
            self._lobby_list_fetch_start_time = 0.0

        if (
            self.online_state == OnlineCoopState.LOBBY_MENU
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

        has_unknown_lobbies = any(
            str(lobby.get('visibility', '') or '').lower() in ('unknown', 'stale_unknown')
            for lobby in getattr(self, '_lobby_list', [])
        ) or bool(getattr(self, '_deferred_lobby_entries', {}))
        if self.online_state == OnlineCoopState.LOBBY_MENU and self._net_initialized and has_unknown_lobbies:
            self._deferred_lobby_refresh_timer = max(
                0.0,
                self._deferred_lobby_refresh_timer - float(delta_time),
            )
            if self._deferred_lobby_refresh_timer <= 0.0:
                self._refresh_deferred_lobby_entries()
                self._refresh_unknown_lobby_entries()
                now = time.time()
                stale_ids: set[int] = set()
                for lobby in getattr(self, '_lobby_list', []):
                    visibility = str(lobby.get('visibility', '') or '').lower()
                    if visibility not in ('unknown', 'stale_unknown'):
                        continue
                    found_time = float(lobby.get('found_time', 0) or 0)
                    if not found_time:
                        continue
                    elapsed = now - found_time
                    lobby_id = int(lobby.get('id', 0) or lobby.get('lobby_id', 0) or 0)
                    if elapsed > 120.0:
                        stale_ids.add(lobby_id)
                    elif visibility == 'unknown' and elapsed > 2.0:
                        lobby['visibility'] = 'stale_unknown'
                if stale_ids:
                    self._lobby_list = [
                        lobby for lobby in self._lobby_list
                        if int(lobby.get('id', 0) or lobby.get('lobby_id', 0) or 0) not in stale_ids
                    ]
                    for stale_id in stale_ids:
                        self._deferred_lobby_entries.pop(stale_id, None)
                        self._clear_lobby_metadata_refresh_request(stale_id)
                self._deferred_lobby_refresh_timer = self._DEFERRED_LOBBY_REFRESH_INTERVAL_MS

        pending_revalidation = int(getattr(self, '_pending_access_revalidation_lobby_id', 0) or 0)
        if (
            pending_revalidation
            and self._net_initialized
            and self.online_state == OnlineCoopState.WAITING
        ):
            revalidation_start = float(getattr(self, '_pending_revalidation_start_time', 0) or 0)
            revalidation_elapsed = time.time() - revalidation_start if revalidation_start else 0.0
            last_check = float(getattr(self, '_pending_reval_last_check_time', 0) or 0)
            if revalidation_elapsed > 3.0 and (time.time() - last_check) >= 1.0:
                self._pending_reval_last_check_time = time.time()
                try:
                    self.net.request_lobby_data(pending_revalidation)
                except Exception:
                    pass
                snapshot = self._get_lobby_metadata_snapshot(
                    pending_revalidation,
                    prefer_live=True,
                )
                if snapshot.get('visibility') not in (None, '', 'unknown'):
                    self._pending_access_revalidation_lobby_id = 0
                    self._pending_revalidation_start_time = 0.0
                    self._validate_joined_lobby_access()
                elif revalidation_elapsed > 5.0:
                    has_code_auth = (
                        self._authorized_private_join_lobby_id == pending_revalidation
                        and bool(self._authorized_private_join_code)
                    )
                    self._pending_access_revalidation_lobby_id = 0
                    self._pending_revalidation_start_time = 0.0
                    if has_code_auth:
                        self._clear_private_join_authorization(pending_revalidation)
                        self._lobby_access_validated_id = pending_revalidation
                    else:
                        self._reject_private_lobby_join()

        if self._net_initialized and self.online_state in (OnlineCoopState.WAITING, OnlineCoopState.READY_CHECK):
            self._lobby_presence_probe_timer = max(
                0.0,
                self._lobby_presence_probe_timer - float(delta_time),
            )
            if self._lobby_presence_probe_timer <= 0.0:
                self._sync_lobby_presence_from_members()
                self._lobby_presence_probe_timer = self._LOBBY_PRESENCE_PROBE_INTERVAL_MS

        # Status message timer
        if self._status_timer > 0:
            self._status_timer = max(0.0, self._status_timer - float(delta_time) / 1000.0)
            if self._status_timer <= 0:
                self._status_msg = ''

        # Pause cooldown timer
        if self._pause_cooldown_timer > 0:
            self._pause_cooldown_timer = max(0.0, self._pause_cooldown_timer - float(delta_time))

        # Countdown
        if self.online_state == OnlineCoopState.COUNTDOWN:
            self.countdown_timer += float(delta_time)
            if self.countdown_timer >= 1000:
                self.countdown_timer -= 1000
                self.countdown_value -= 1
                if self.countdown_value < 0:
                    self._start_game()

        # Host game loop
        if self.online_state == OnlineCoopState.PLAYING and self.role == 'host' and self.coop_game:
            before_frozen = (bool(self.coop_game.p1_frozen), bool(self.coop_game.p2_frozen))
            if not self.paused:
                self.coop_game.update(float(delta_time))
            after_frozen = (bool(self.coop_game.p1_frozen), bool(self.coop_game.p2_frozen))
            if self._last_frozen_flags is None:
                self._last_frozen_flags = before_frozen
            if after_frozen != self._last_frozen_flags:
                for index, player in enumerate(('P1', 'P2')):
                    if after_frozen[index] != self._last_frozen_flags[index]:
                        event_name = 'player_frozen' if after_frozen[index] else 'player_unfrozen'
                        self._send_game_event(event_name, {'player': player})
                self._send_board_state()
                self._send_piece_state()
                self._last_frozen_flags = after_frozen

            if not self.paused and self._push_piece_state_if_changed():
                self._piece_state_timer = 0.0

            # Broadcast state to guest (paused'da da gönder — guest board'u görsün)
            self._board_state_timer += float(delta_time)
            self._piece_state_timer += float(delta_time)

            if self._board_state_timer >= self._BOARD_STATE_INTERVAL:
                self._board_state_timer = 0.0
                # Unreliable delta paketleri kaybolursa guest board kalici desync olmamali.
                # Timer heartbeat'i her zaman full snapshot gondererek taban durumu yeniler.
                self._send_board_state(force_full=True)

            if self._piece_state_timer >= self._PIECE_STATE_INTERVAL:
                self._piece_state_timer = 0.0
                self._push_piece_state_if_changed(force=True)

            # Check game over
            if self.coop_game.game_over and not self.game_over:
                self.game_over = True
                self.online_state = OnlineCoopState.GAME_OVER
                self._send_game_event('game_over', {
                    'team_score': self.coop_game.team_score,
                    'total_lines': self.coop_game.total_lines_cleared,
                })

        # Disconnect grace timer
        if self._disconnect_grace_timer > 0:
            self._disconnect_grace_timer -= float(delta_time)
            if self._disconnect_grace_timer <= 0:
                self._disconnect_grace_timer = 0.0
                pending_id = int(getattr(self, '_pending_disconnect_steam_id', 0) or 0)
                try:
                    members = set(self.net.get_lobby_members() or [])
                except Exception:
                    members = set()
                if pending_id and pending_id in members:
                    self._pending_disconnect_steam_id = 0
                    if not getattr(self.net, 'opponent_steam_id', 0):
                        try:
                            self.net._opponent_steam_id = pending_id
                        except Exception:
                            pass
                elif self.online_state == OnlineCoopState.PLAYING:
                    self.online_state = OnlineCoopState.DISCONNECTED
                    self._pending_disconnect_steam_id = 0

        if (
            self.online_state == OnlineCoopState.READY_CHECK
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
            self.online_state == OnlineCoopState.READY_CHECK
            and self._net_initialized
            and self.my_ready
            and self._ready_send_pending
            and self.net.opponent_steam_id
            and self._session_established
        ):
            self._send_ready_signal(reason='pending_flush')

        if (
            self.online_state == OnlineCoopState.READY_CHECK
            and self.my_ready
            and not self.opponent_ready
            and self._net_initialized
        ):
            self._ready_resend_timer -= float(delta_time)
            if self._ready_resend_timer <= 0:
                self._send_ready_signal(reason='ready_resend')
                self._ready_resend_timer = self._READY_RESEND_INTERVAL_MS

        if (
            self.online_state == OnlineCoopState.READY_CHECK
            and self._net_initialized
            and self.net.is_host
            and self.my_ready
            and self.opponent_ready
            and bool(getattr(self, '_game_start_pending_payload', None))
        ):
            self._game_start_retry_timer = float(self._game_start_retry_timer) - float(delta_time)
            if self._game_start_retry_timer <= 0:
                start_ok = self._send_coop_start_payload(self._game_start_pending_payload)
                if start_ok:
                    self._game_start_pending_payload = None
                    self._game_start_retry_timer = 0.0
                    self._start_countdown()
                else:
                    self._game_start_retry_timer = self._GAME_START_RETRY_INTERVAL_MS

        if (
            self.online_state == OnlineCoopState.PLAYING
            and self.role == 'guest'
            and self.coop_game
        ):
            self._update_guest_local_prediction(float(delta_time))
            if bool(getattr(self, '_guest_authoritative_piece_sync_enabled', False)):
                self._guest_piece_state_timer += float(delta_time)
                if self._guest_piece_state_timer >= self._GUEST_PIECE_STATE_INTERVAL:
                    self._send_guest_piece_state(force=True)

    @staticmethod
    def _clamp_int(value, minimum: int, maximum: int, default: int = 0) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            parsed = int(default)
        return max(int(minimum), min(int(maximum), parsed))

    @staticmethod
    def _coerce_rgb_cell(cell) -> tuple[tuple[int, int, int], bool] | None:
        if cell in (0, None, False, ''):
            return (0, 0, 0), False
        if not isinstance(cell, (list, tuple)) or len(cell) < 3:
            return None
        rgb = []
        for channel in cell[:3]:
            try:
                value = int(channel)
            except (TypeError, ValueError):
                return None
            rgb.append(max(0, min(255, value)))
        color = (rgb[0], rgb[1], rgb[2])
        return color, color != (0, 0, 0)

    def _normalize_board_snapshot(self, data: dict) -> dict | None:
        if data.get('format') == 'semantic_delta_v1':
            raw_cells = data.get('cells')
            if not isinstance(raw_cells, list):
                return None

            normalized_cells = []
            for entry in raw_cells:
                if not isinstance(entry, (list, tuple)) or len(entry) != 13:
                    return None
                x = self._clamp_int(entry[0], 0, 19)
                y = self._clamp_int(entry[1], 0, 19)
                piece_name = str(entry[2] or '')
                owner = entry[3] if entry[3] in ('P1', 'P2') else None
                rel_x = self._clamp_int(entry[4], 0, 3)
                rel_y = self._clamp_int(entry[5], 0, 3)
                width = self._clamp_int(entry[6], 1, 4, 1)
                height = self._clamp_int(entry[7], 1, 4, 1)
                rotation = self._clamp_int(entry[8], 0, 3, 0)
                gold = bool(entry[9])
                fallback_color = (
                    self._clamp_int(entry[10], 0, 255, 0),
                    self._clamp_int(entry[11], 0, 255, 0),
                    self._clamp_int(entry[12], 0, 255, 0),
                )
                normalized_cells.append((
                    x, y, piece_name, owner,
                    rel_x, rel_y, width, height, rotation,
                    gold, fallback_color,
                ))

            removed_positions = []
            raw_removed = data.get('removed', [])
            if raw_removed is not None:
                if not isinstance(raw_removed, list):
                    return None
                for entry in raw_removed:
                    if not isinstance(entry, (list, tuple)) or len(entry) != 2:
                        return None
                    removed_positions.append((
                        self._clamp_int(entry[0], 0, 19),
                        self._clamp_int(entry[1], 0, 19),
                    ))

            normalized = dict(data)
            normalized['_semantic_board'] = True
            normalized['_semantic_cells'] = normalized_cells
            normalized['_removed_cells'] = removed_positions
            normalized['_board_full'] = bool(data.get('full', False))
            normalized['team_score'] = self._clamp_int(data.get('team_score', 0), 0, 999999999)
            normalized['total_lines'] = self._clamp_int(data.get('total_lines', 0), 0, 999999)
            normalized['level'] = self._clamp_int(data.get('level', 1), 1, 999)
            try:
                normalized['fall_speed'] = max(1.0, min(5000.0, float(data.get('fall_speed', 900.0))))
            except (TypeError, ValueError):
                normalized['fall_speed'] = 900.0
            normalized['p1_frozen'] = bool(data.get('p1_frozen', False))
            normalized['p2_frozen'] = bool(data.get('p2_frozen', False))
            normalized['guest_piece_ack'] = self._clamp_int(
                data.get('guest_piece_ack', self._last_host_guest_piece_ack_seq),
                0,
                999999999,
                self._last_host_guest_piece_ack_seq,
            )
            normalized.update(self._normalize_authoritative_gameplay_config(data))
            return normalized

        grid = data.get('grid')
        if not isinstance(grid, list) or len(grid) != 20:
            return None

        normalized_grid: list[list[tuple[int, int, int]]] = []
        occupancy: list[list[bool]] = []
        for row in grid:
            if not isinstance(row, list) or len(row) != 20:
                return None
            normalized_row: list[tuple[int, int, int]] = []
            occupancy_row: list[bool] = []
            for cell in row:
                coerced = self._coerce_rgb_cell(cell)
                if coerced is None:
                    return None
                color, filled = coerced
                normalized_row.append(color)
                occupancy_row.append(filled)
            normalized_grid.append(normalized_row)
            occupancy.append(occupancy_row)

        raw_owners = data.get('owners')
        owners: list[list[str | None]] = []
        if isinstance(raw_owners, list) and len(raw_owners) == 20:
            for owner_row in raw_owners:
                if not isinstance(owner_row, list) or len(owner_row) != 20:
                    return None
                normalized_owner_row = []
                for owner in owner_row:
                    normalized_owner_row.append(owner if owner in ('P1', 'P2') else None)
                owners.append(normalized_owner_row)
        else:
            owners = [[None for _ in range(20)] for _ in range(20)]

        normalized = dict(data)
        normalized['grid'] = normalized_grid
        normalized['owners'] = owners
        normalized['_occupancy'] = occupancy
        normalized['team_score'] = self._clamp_int(data.get('team_score', 0), 0, 999999999)
        normalized['total_lines'] = self._clamp_int(data.get('total_lines', 0), 0, 999999)
        normalized['level'] = self._clamp_int(data.get('level', 1), 1, 999)
        try:
            normalized['fall_speed'] = max(1.0, min(5000.0, float(data.get('fall_speed', 900.0))))
        except (TypeError, ValueError):
            normalized['fall_speed'] = 900.0
        normalized['p1_frozen'] = bool(data.get('p1_frozen', False))
        normalized['p2_frozen'] = bool(data.get('p2_frozen', False))
        normalized['guest_piece_ack'] = self._clamp_int(
            data.get('guest_piece_ack', self._last_host_guest_piece_ack_seq),
            0,
            999999999,
            self._last_host_guest_piece_ack_seq,
        )
        normalized.update(self._normalize_authoritative_gameplay_config(data))
        return normalized

    def _normalize_piece_snapshot(self, data: dict) -> dict:
        def _piece_dict(raw_piece):
            if not isinstance(raw_piece, dict):
                return None
            si = self._clamp_int(raw_piece.get('si', -1), -1, len(_SHAPES) - 1, -1)
            if si < 0:
                return None
            return {
                'si': si,
                'x': self._clamp_int(raw_piece.get('x', 0), -6, 25),
                'y': self._clamp_int(raw_piece.get('y', 0), -8, 25),
                'r': self._clamp_int(raw_piece.get('r', 0), 0, 3),
            }

        normalized = dict(data)
        normalized['p1_current'] = _piece_dict(data.get('p1_current'))
        normalized['p2_current'] = _piece_dict(data.get('p2_current'))
        for key in ('p1_next_si', 'p2_next_si', 'p1_hold_si', 'p2_hold_si'):
            normalized[key] = self._clamp_int(data.get(key, -1), -1, len(_SHAPES) - 1, -1)
        normalized['p1_ghost_y'] = self._clamp_int(data.get('p1_ghost_y', -1), -8, 25, -1)
        normalized['p2_ghost_y'] = self._clamp_int(data.get('p2_ghost_y', -1), -8, 25, -1)
        normalized['input_ack'] = self._clamp_int(data.get('input_ack', 0), 0, 999999999)
        normalized['guest_piece_ack'] = self._clamp_int(
            data.get('guest_piece_ack', self._last_host_guest_piece_ack_seq),
            0,
            999999999,
            self._last_host_guest_piece_ack_seq,
        )
        try:
            normalized['host_elapsed_ms'] = max(0.0, min(999999999.0, float(data.get('host_elapsed_ms', 0.0))))
        except (TypeError, ValueError):
            normalized['host_elapsed_ms'] = 0.0
        normalized.update(self._normalize_authoritative_gameplay_config(data))
        return normalized

    def _consume_guest_input_ack(self, ack_seq: int) -> tuple[bool, bool]:
        normalized_ack = self._clamp_int(
            ack_seq,
            0,
            999999999,
            getattr(self, '_last_input_ack_seq', 0),
        )
        if normalized_ack > self._last_input_ack_seq:
            self._last_input_ack_seq = normalized_ack

        pending_inputs = getattr(self, '_guest_pending_inputs', None)
        if not isinstance(pending_inputs, list) or not pending_inputs:
            return False, False

        remaining_inputs: list[tuple[int, str]] = []
        pending_board_mutation = False
        for seq, action in pending_inputs:
            if int(seq or 0) <= normalized_ack:
                continue
            normalized_action = str(action or '')
            remaining_inputs.append((int(seq or 0), normalized_action))
            if normalized_action == 'hard_drop':
                pending_board_mutation = True

        self._guest_pending_inputs = remaining_inputs[-64:]
        return bool(self._guest_pending_inputs), pending_board_mutation

    def _consume_guest_piece_ack(self, ack_seq: int) -> int:
        normalized_ack = self._clamp_int(
            ack_seq,
            0,
            999999999,
            getattr(self, '_last_host_guest_piece_ack_seq', 0),
        )
        previous_ack = int(getattr(self, '_last_host_guest_piece_ack_seq', 0) or 0)
        if normalized_ack > previous_ack:
            self._last_host_guest_piece_ack_seq = normalized_ack
            if normalized_ack >= int(getattr(self, '_guest_piece_state_out_seq', 0) or 0):
                self._guest_piece_unacked_since = 0.0
            else:
                self._guest_piece_unacked_since = time.time()
        elif normalized_ack >= int(getattr(self, '_guest_piece_state_out_seq', 0) or 0):
            self._guest_piece_unacked_since = 0.0
        return int(getattr(self, '_last_host_guest_piece_ack_seq', 0) or 0)

    def _ensure_guest_render_game(self):
        if self.role != 'guest':
            return None
        if self.coop_game is not None:
            self.coop_game.screen = self.screen
            self.coop_game.window_width = self.window_width
            self.coop_game.window_height = self.window_height
            self.coop_game.fullscreen = self.fullscreen
            if self._authoritative_gameplay_config:
                self._apply_authoritative_guest_timing(self.coop_game, self._authoritative_gameplay_config)
            return self.coop_game
        try:
            self.coop_game = CoopGame(
                sound_enabled=False,
                effects_enabled=True,
                screen=self.screen,
                fullscreen=self.fullscreen,
                user_manager=self.user_manager,
                settings_manager=self.settings_manager,
                sound_manager=self.sound,
                piece_rng_seed=(int(self._game_seed) if int(self._game_seed or 0) > 0 else None),
            )
            self.coop_game._event_listeners = []
            if self._authoritative_gameplay_config:
                self._apply_authoritative_guest_timing(self.coop_game, self._authoritative_gameplay_config)
        except Exception as exc:
            print(f"[OnlineCoop] Guest render init hatası: {exc}")
            self.coop_game = None
        return self.coop_game

    def _piece_from_snapshot(self, piece_data: dict | None):
        if not isinstance(piece_data, dict):
            return None
        si = self._clamp_int(piece_data.get('si', -1), -1, len(_SHAPES) - 1, -1)
        if si < 0:
            return None
        piece = Piece(
            x=self._clamp_int(piece_data.get('x', 0), -6, 25),
            y=self._clamp_int(piece_data.get('y', 0), -8, 25),
            shape_index=si,
        )
        rotation = self._clamp_int(piece_data.get('r', 0), 0, 3)
        if rotation:
            piece.rotate(rotation)
        return piece

    def _piece_from_shape_index(self, shape_index: int):
        si = self._clamp_int(shape_index, -1, len(_SHAPES) - 1, -1)
        if si < 0:
            return None
        return Piece(x=0, y=0, shape_index=si)

    def _apply_block_style_to_guest_piece(self, piece):
        if piece is None or self.coop_game is None:
            return piece
        try:
            self.coop_game._apply_block_style(piece)
        except Exception:
            pass
        return piece

    @staticmethod
    def _piece_shape_index(piece) -> int:
        if piece is None:
            return -1
        try:
            return int(getattr(piece, 'shape_index', -1))
        except (TypeError, ValueError):
            return -1

    def _guest_p2_state_signature(self, render_game) -> tuple | None:
        if render_game is None:
            return None
        return (
            self._piece_signature(getattr(render_game, 'p2_current_piece', None)),
            self._piece_shape_index(getattr(render_game, 'p2_next_piece', None)),
            self._piece_shape_index(getattr(render_game, 'p2_hold_piece', None)),
            bool(getattr(render_game, 'p2_frozen', False)),
        )

    @staticmethod
    def _guest_action_requires_host_control(action: str) -> bool:
        return str(action or '') in {
            'move_left',
            'move_right',
            'soft_drop_start',
            'soft_drop_stop',
            'rotate',
            'hard_drop',
            'hold',
            'das_stop',
            'das_stop_left',
            'das_stop_right',
            'pause_request',
        }

    @staticmethod
    def _guest_action_requires_host_simulation(action: str) -> bool:
        return str(action or '') in {
            'hard_drop',
            'hold',
            'pause_request',
        }

    @staticmethod
    def _guest_action_blocks_piece_mirror(action: str) -> bool:
        return str(action or '') in {
            'hard_drop',
            'hold',
            'pause_request',
        }

    @staticmethod
    def _guest_action_flushes_piece_mirror(action: str) -> bool:
        return str(action or '') in {
            'move_left',
            'move_right',
            'rotate',
            'soft_drop_start',
            'soft_drop_stop',
            'das_stop',
            'das_stop_left',
            'das_stop_right',
        }

    def _flush_guest_piece_mirror_for_action(self, action: str) -> bool:
        if not bool(getattr(self, '_guest_authoritative_piece_sync_enabled', False)):
            return False
        if not self._guest_action_flushes_piece_mirror(action):
            return False
        return self._send_guest_piece_state(force=True)

    def _guest_control_sync_pending(self) -> bool:
        pending_inputs = getattr(self, '_guest_pending_inputs', None)
        if not isinstance(pending_inputs, list):
            return False
        for _seq, action in pending_inputs:
            if self._guest_action_blocks_piece_mirror(str(action or '')):
                return True
        return False

    def _guest_piece_dict(self, piece) -> dict | None:
        if piece is None:
            return None
        shape_index = self._piece_shape_index(piece)
        return {
            'x': int(getattr(piece, 'x', 0) or 0),
            'y': int(getattr(piece, 'y', 0) or 0),
            'si': shape_index,
            'r': int(getattr(piece, 'rotation_state', 0) or 0),
        }

    def _send_guest_piece_state(self, force: bool = False, reliable: bool = False) -> bool:
        if not bool(getattr(self, '_guest_authoritative_piece_sync_enabled', False)):
            return False
        if self.role != 'guest' or self.online_state != OnlineCoopState.PLAYING:
            return False
        if bool(getattr(self, 'game_over', False)) or bool(getattr(self, 'paused', False)):
            return False
        render_game = self.coop_game
        if render_game is None or self._guest_control_sync_pending():
            return False
        if bool(getattr(render_game, 'game_over', False)) or bool(getattr(render_game, 'paused', False)):
            return False

        signature = self._guest_p2_state_signature(render_game)
        if not force and signature == getattr(self, '_last_guest_sent_piece_signature', None):
            return False

        self._guest_piece_state_out_seq = int(getattr(self, '_guest_piece_state_out_seq', 0) or 0) + 1
        self._last_guest_sent_piece_signature = signature
        self._guest_piece_state_timer = 0.0
        if float(getattr(self, '_guest_piece_unacked_since', 0.0) or 0.0) <= 0.0:
            self._guest_piece_unacked_since = time.time()
        return bool(self.net.send({
            'type': MsgType.GUEST_PIECE_STATE,
            'seq': self._guest_piece_state_out_seq,
            'p2_current': self._guest_piece_dict(getattr(render_game, 'p2_current_piece', None)),
            'p2_frozen': bool(getattr(render_game, 'p2_frozen', False)),
        }, reliable=bool(reliable), channel=CHANNEL_STATE))

    def _apply_guest_authoritative_piece_state(self, data: dict) -> None:
        if not bool(getattr(self, '_guest_authoritative_piece_sync_enabled', False)):
            return
        if self.role != 'host' or self.coop_game is None or not isinstance(data, dict):
            return

        try:
            seq = int(data.get('seq', 0) or 0)
        except (TypeError, ValueError):
            seq = 0
        if seq <= int(getattr(self, '_last_guest_piece_state_seq', 0) or 0):
            return

        if self._gameplay_input_blocked():
            self._reject_guest_authoritative_piece_state(seq)
            return

        incoming_piece = self._piece_from_snapshot(data.get('p2_current'))
        if incoming_piece is None:
            self._reject_guest_authoritative_piece_state(seq)
            return

        current_piece = getattr(self.coop_game, 'p2_current_piece', None)
        if current_piece is not None and self._piece_shape_index(current_piece) != self._piece_shape_index(incoming_piece):
            self._reject_guest_authoritative_piece_state(seq)
            return

        board = getattr(self.coop_game, 'board', None)
        if board is not None and hasattr(board, 'is_valid_position_for_player'):
            try:
                if not board.is_valid_position_for_player(incoming_piece, 'P2'):
                    self._reject_guest_authoritative_piece_state(seq)
                    return
            except Exception:
                self._reject_guest_authoritative_piece_state(seq)
                return

        remote_players = getattr(self.coop_game, 'remote_authority_players', None)
        if not isinstance(remote_players, set):
            remote_players = set(remote_players or []) if remote_players is not None else set()
            self.coop_game.remote_authority_players = remote_players
        remote_players.add('P2')

        moved = self._piece_signature(current_piece) != self._piece_signature(incoming_piece)
        try:
            self.coop_game._apply_block_style(incoming_piece)
        except Exception:
            pass
        self.coop_game.p2_current_piece = incoming_piece
        self.coop_game.p2_das_direction = 0
        self.coop_game.p2_das_charged = False
        self.coop_game.p2_das_timer = 0.0
        self.coop_game.p2_das_repeat_timer = 0.0
        self.coop_game.p2_soft_drop_active = False
        self.coop_game.p2_soft_drop_timer = 0.0
        self.coop_game.p2_fall_time = 0.0
        if moved:
            try:
                self.coop_game._reset_player_lock_state('P2')
            except Exception:
                pass
        self._last_guest_piece_state_seq = seq

    def _reject_guest_authoritative_piece_state(self, seq: int) -> None:
        """Mark a guest snapshot as processed and immediately resend host truth."""
        if seq > int(getattr(self, '_last_guest_piece_state_seq', 0) or 0):
            self._last_guest_piece_state_seq = int(seq)
        try:
            self._send_piece_state()
        except Exception:
            pass

    def _should_keep_locally_simulated_p2(self, render_game, piece_data: dict) -> bool:
        if render_game is None or not isinstance(piece_data, dict):
            return False

        incoming_piece = piece_data.get('p2_current')
        if not isinstance(incoming_piece, dict):
            return False

        local_signature = self._guest_p2_state_signature(render_game)
        local_piece_signature = local_signature[0] if local_signature else None
        if local_piece_signature is None:
            return False

        # Identity check: aynı active shape + same next + same hold demek,
        # host'un hâlâ aynı parçayı bekliyor olduğu anlamına gelir. Lock veya
        # hold-swap olduğunda shape index değişir ve fallback (False) host'u
        # otoriter kılarak doğal re-sync sağlar.
        if int(incoming_piece.get('si', -1)) != int(local_piece_signature[0]):
            return False
        if self._piece_shape_index(getattr(render_game, 'p2_next_piece', None)) != int(piece_data.get('p2_next_si', -1)):
            return False
        if self._piece_shape_index(getattr(render_game, 'p2_hold_piece', None)) != int(piece_data.get('p2_hold_si', -1)):
            return False

        # PvP-style local active-piece ownership: guest authoritative piece sync
        # açıkken P2'yi guest sahipleniyor — host CoopGame'i P2 için gravity/DAS
        # uygulamaz, sadece guest'in GUEST_PIECE_STATE mirror'ını yansıtır. Bu
        # nedenle aynı kimliğe sahip COOP_PIECE_STATE heartbeat'leri lokal P2
        # tahminini geri çekmemeli (jitter kaynağı). Lock/spawn/hold ile gerçek
        # kimlik değişimi yukarıdaki erken return'lerle host'a re-sync sağlar.
        if bool(getattr(self, '_guest_authoritative_piece_sync_enabled', False)):
            return True

        # Legacy non-authoritative fallback (authority kapalıyken eski davranış).
        # Prediction cap aşıldığında veya host elapsed cap'i aştığında host
        # snapshot'ını kabul eder; aksi halde dx<=3/dy<=6 toleransı uygulanır.
        dx = abs(int(incoming_piece.get('x', 0)) - int(local_piece_signature[1]))
        dy = abs(int(incoming_piece.get('y', 0)) - int(local_piece_signature[2]))
        prediction_ms = max(0.0, float(getattr(self, '_guest_local_prediction_ms', 0.0) or 0.0))
        prediction_cap = max(1.0, float(getattr(self, '_GUEST_LOCAL_PREDICTION_MAX_MS', 150.0) or 150.0))
        try:
            host_elapsed_ms = max(0.0, float(piece_data.get('host_elapsed_ms', 0.0) or 0.0))
        except (TypeError, ValueError):
            host_elapsed_ms = 0.0
        last_authoritative_ms = max(
            0.0,
            float(getattr(self, '_guest_last_authoritative_piece_elapsed_ms', 0.0) or 0.0),
        )
        if prediction_ms >= prediction_cap and (dx > 0 or dy > 0):
            return False
        if (
            last_authoritative_ms > 0.0
            and host_elapsed_ms > last_authoritative_ms
            and (host_elapsed_ms - last_authoritative_ms) >= prediction_cap
            and (dx > 0 or dy > 0)
        ):
            return False
        return dx <= 3 and dy <= 6

    def _should_keep_unacked_guest_p2(self, render_game, piece_data: dict) -> bool:
        if not bool(getattr(self, '_guest_authoritative_piece_sync_enabled', False)):
            return False
        if render_game is None or not isinstance(piece_data, dict):
            return False
        self._consume_guest_piece_ack(piece_data.get('guest_piece_ack', 0))
        last_sent_seq = int(getattr(self, '_guest_piece_state_out_seq', 0) or 0)
        last_ack_seq = int(getattr(self, '_last_host_guest_piece_ack_seq', 0) or 0)
        if last_sent_seq <= 0 or last_ack_seq >= last_sent_seq:
            return False

        unacked_since = float(getattr(self, '_guest_piece_unacked_since', 0.0) or 0.0)
        if unacked_since <= 0.0:
            self._guest_piece_unacked_since = time.time()
            unacked_since = self._guest_piece_unacked_since
        grace_s = max(0.05, float(getattr(self, '_GUEST_PIECE_ACK_GRACE_S', 0.75) or 0.75))
        if time.time() - unacked_since > grace_s:
            return False

        incoming_piece = piece_data.get('p2_current')
        if not isinstance(incoming_piece, dict):
            return False
        local_signature = self._guest_p2_state_signature(render_game)
        local_piece_signature = local_signature[0] if local_signature else None
        if local_piece_signature is None:
            return False
        if int(incoming_piece.get('si', -1)) != int(local_piece_signature[0]):
            return False
        if self._piece_shape_index(getattr(render_game, 'p2_next_piece', None)) != int(piece_data.get('p2_next_si', -1)):
            return False
        if self._piece_shape_index(getattr(render_game, 'p2_hold_piece', None)) != int(piece_data.get('p2_hold_si', -1)):
            return False
        return True

    def _update_guest_local_prediction(self, delta_time: float):
        render_game = self._apply_guest_render_cache()
        if render_game is None:
            self._update_guest_render_effects(delta_time)
            return
        if self.game_over or self.paused or getattr(render_game, 'game_over', False) or getattr(render_game, 'paused', False):
            self._update_guest_render_effects(delta_time)
            return

        before_signature = self._guest_p2_state_signature(render_game)
        original_lock_and_new_piece = getattr(render_game, '_lock_and_new_piece', None)
        original_do_unfreeze = getattr(render_game, '_do_unfreeze', None)
        original_p1_frozen = bool(getattr(render_game, 'p1_frozen', False))
        original_p1_pending_unfreeze = bool(getattr(render_game, '_p1_pending_unfreeze', False))
        original_p1_das_direction = int(getattr(render_game, 'p1_das_direction', 0) or 0)
        original_p1_soft_drop_active = bool(getattr(render_game, 'p1_soft_drop_active', False))

        def _preview_lock_and_new_piece(player: str):
            if player == 'P2':
                return None
            if callable(original_lock_and_new_piece):
                return original_lock_and_new_piece(player)
            return None

        def _preview_do_unfreeze(player: str):
            if player == 'P2':
                return None
            if callable(original_do_unfreeze):
                return original_do_unfreeze(player)
            return None

        try:
            render_game.p1_frozen = True
            render_game._p1_pending_unfreeze = False
            render_game.p1_das_direction = 0
            render_game.p1_soft_drop_active = False
            render_game._lock_and_new_piece = _preview_lock_and_new_piece
            render_game._do_unfreeze = _preview_do_unfreeze
            render_game.update(delta_time)
        except Exception:
            self._update_guest_render_effects(delta_time)
            return
        finally:
            render_game.p1_frozen = original_p1_frozen
            render_game._p1_pending_unfreeze = original_p1_pending_unfreeze
            render_game.p1_das_direction = original_p1_das_direction
            render_game.p1_soft_drop_active = original_p1_soft_drop_active
            if callable(original_lock_and_new_piece):
                render_game._lock_and_new_piece = original_lock_and_new_piece
            if callable(original_do_unfreeze):
                render_game._do_unfreeze = original_do_unfreeze

        after_signature = self._guest_p2_state_signature(render_game)
        if after_signature != before_signature:
            prediction_cap = max(1.0, float(getattr(self, '_GUEST_LOCAL_PREDICTION_MAX_MS', 150.0) or 150.0))
            self._guest_local_prediction_ms = min(
                prediction_cap,
                max(0.0, float(getattr(self, '_guest_local_prediction_ms', 0.0) or 0.0)) + float(delta_time),
            )
            self._send_guest_piece_state(force=True)

    def _apply_guest_render_cache(self):
        render_game = self._ensure_guest_render_game()
        board_data = self._guest_board_cache
        if render_game is None or not isinstance(board_data, dict):
            return None

        board_seq = int(board_data.get('seq', -1) or -1)
        board_ack = self._clamp_int(
            board_data.get('input_ack', self._last_input_ack_seq),
            0,
            999999999,
            self._last_input_ack_seq,
        )
        _pending_inputs, pending_board_mutation = self._consume_guest_input_ack(board_ack)
        self._consume_guest_piece_ack(
            board_data.get('guest_piece_ack', self._last_host_guest_piece_ack_seq)
        )
        if board_seq != getattr(self, '_guest_render_board_seq', -1) and not pending_board_mutation:
            board = render_game.board
            if board_data.get('_semantic_board'):
                if bool(board_data.get('_board_full', False)):
                    board.grid = [[_BOARD_EMPTY_COLOR for _ in range(board.width)] for _ in range(board.height)]
                    board.occupancy = [[False for _ in range(board.width)] for _ in range(board.height)]
                    board.owners = [[None for _ in range(board.width)] for _ in range(board.height)]
                    board.texture_grid = [[None for _ in range(board.width)] for _ in range(board.height)]
                    board.gold = [[False for _ in range(board.width)] for _ in range(board.height)]

                for x, y in board_data.get('_removed_cells', []):
                    board.grid[y][x] = _BOARD_EMPTY_COLOR
                    board.occupancy[y][x] = False
                    board.owners[y][x] = None
                    board.texture_grid[y][x] = None
                    board.gold[y][x] = False

                for (
                    x,
                    y,
                    piece_name,
                    owner,
                    rel_x,
                    rel_y,
                    width,
                    height,
                    rotation,
                    is_gold,
                    fallback_color,
                ) in board_data.get('_semantic_cells', []):
                    board.grid[y][x] = self._local_locked_block_color(render_game, piece_name, fallback_color)
                    board.occupancy[y][x] = True
                    board.owners[y][x] = owner if owner in ('P1', 'P2') else None
                    board.gold[y][x] = bool(is_gold)
                    board.texture_grid[y][x] = (
                        TextureSlice(piece_name, rel_x=rel_x, rel_y=rel_y, width=width, height=height, rotation=rotation)
                        if piece_name else None
                    )
            else:
                grid = board_data.get('grid')
                occupancy = board_data.get('_occupancy')
                owners = board_data.get('owners')
                if not (
                    isinstance(grid, list)
                    and isinstance(occupancy, list)
                    and isinstance(owners, list)
                ):
                    return None
                board.grid = [[tuple(cell) for cell in row] for row in grid]
                board.occupancy = [[bool(cell) for cell in row] for row in occupancy]
                board.owners = [[owner if owner in ('P1', 'P2') else None for owner in row] for row in owners]
                board.texture_grid = [[None for _ in range(board.width)] for _ in range(board.height)]
                board.gold = [[False for _ in range(board.width)] for _ in range(board.height)]
            board.score = int(board_data.get('team_score', 0) or 0)
            board.lines_cleared = int(board_data.get('total_lines', 0) or 0)
            board.level = int(board_data.get('level', 1) or 1)
            render_game.team_score = int(board_data.get('team_score', 0) or 0)
            render_game.total_lines_cleared = int(board_data.get('total_lines', 0) or 0)
            render_game.level = int(board_data.get('level', 1) or 1)
            render_game.fall_speed = float(board_data.get('fall_speed', 900.0) or 900.0)
            render_game.p1_frozen = bool(board_data.get('p1_frozen', False))
            render_game.p2_frozen = bool(board_data.get('p2_frozen', False))
            render_game.game_over = bool(getattr(self, 'game_over', False))
            render_game.paused = bool(getattr(self, 'paused', False))
            self._apply_authoritative_guest_timing(render_game, board_data)
            self._guest_render_board_seq = board_seq
            try:
                pending_rows = list(getattr(render_game, 'line_clear_pending_rows', []) or [])
                if (
                    pending_rows
                    and getattr(render_game, 'line_clear_sweep_active', False)
                    and hasattr(render_game, '_start_block_fall_animation')
                ):
                    rows_key = tuple(sorted(int(row) for row in pending_rows))
                    if getattr(render_game, '_fall_animation_rows_key', None) != rows_key:
                        render_game._start_block_fall_animation(pending_rows)
            except Exception:
                pass

        piece_data = self._guest_piece_cache
        if isinstance(piece_data, dict):
            piece_seq = int(piece_data.get('seq', -1) or -1)
            if piece_seq != getattr(self, '_guest_render_piece_seq', -1):
                self._apply_authoritative_guest_timing(render_game, piece_data)
                piece_ack = self._clamp_int(
                    piece_data.get('input_ack', self._last_input_ack_seq),
                    0,
                    999999999,
                    self._last_input_ack_seq,
                )
                pending_guest_inputs, _ = self._consume_guest_input_ack(piece_ack)
                keep_local_p2 = False
                if not pending_guest_inputs:
                    keep_local_p2 = (
                        self._should_keep_unacked_guest_p2(render_game, piece_data)
                        or self._should_keep_locally_simulated_p2(render_game, piece_data)
                    )
                piece_elapsed_ms = max(0.0, float(piece_data.get('host_elapsed_ms', 0.0) or 0.0))
                render_game.p1_current_piece = self._apply_block_style_to_guest_piece(
                    self._piece_from_snapshot(piece_data.get('p1_current')))
                render_game.p1_next_piece = self._apply_block_style_to_guest_piece(
                    self._piece_from_shape_index(piece_data.get('p1_next_si', -1)))
                render_game.p1_hold_piece = self._apply_block_style_to_guest_piece(
                    self._piece_from_shape_index(piece_data.get('p1_hold_si', -1)))
                if not pending_guest_inputs and not keep_local_p2:
                    render_game.p2_current_piece = self._apply_block_style_to_guest_piece(
                        self._piece_from_snapshot(piece_data.get('p2_current')))
                    render_game.p2_next_piece = self._apply_block_style_to_guest_piece(
                        self._piece_from_shape_index(piece_data.get('p2_next_si', -1)))
                    render_game.p2_hold_piece = self._apply_block_style_to_guest_piece(
                        self._piece_from_shape_index(piece_data.get('p2_hold_si', -1)))
                    self._guest_last_authoritative_piece_elapsed_ms = piece_elapsed_ms
                    self._guest_local_prediction_ms = 0.0
                self._guest_render_piece_seq = piece_seq
        return render_game

    def _update_guest_render_effects(self, delta_time: float):
        render_game = self.coop_game
        if not render_game:
            return
        try:
            if getattr(render_game, 'effects_enabled', False):
                render_game.update_particles(delta_time)
                render_game.update_ambient_particles(delta_time)
                render_game.update_drop_trails(delta_time)
                render_game._update_line_clear_effects(delta_time)
                step_screen_shake(render_game, dt_ms=delta_time)
        except Exception:
            pass

    def _apply_guest_lock_event(self, data: dict):
        # Risk-1 azaltıcı: Host bu lock event'i guest'in P2'si için yayınlıyorsa
        # guest'in pending input listesindeki ilgili hard_drop/hold artık host
        # tarafında uygulanmış demektir. Listede tutmak hem `pending_board_mutation`
        # üzerinden bir sonraki board snapshot'ın uygulanmasını gereksiz yere
        # bloke eder, hem de re-sync gecikmesi yaratır. Bu nedenle host onayı
        # geldiği anda pending P2 board-mutating input'ları proaktif temizliyoruz.
        if str(data.get('player', '')) == 'P2':
            pending_inputs = getattr(self, '_guest_pending_inputs', None)
            if isinstance(pending_inputs, list) and pending_inputs:
                self._guest_pending_inputs = [
                    (seq, action)
                    for seq, action in pending_inputs
                    if str(action or '') not in ('hard_drop', 'hold')
                ]

        self._guest_score_cache['team_score'] = self._clamp_int(
            data.get('new_score', 0), 0, 999999999)
        self._guest_score_cache['level'] = self._clamp_int(
            data.get('new_level', 1), 1, 999)
        if data.get('total_lines', 0):
            self._guest_score_cache['total_lines'] = self._clamp_int(
                data.get('total_lines', 0), 0, 999999)

        rows = data.get('cleared_rows', [])
        colors = data.get('row_colors', {})
        if not isinstance(rows, list) or not isinstance(colors, dict):
            return
        normalized_rows = []
        normalized_colors: dict[int, list[tuple[int, int, int]]] = {}
        for row in rows[:20]:
            row_index = self._clamp_int(row, 0, 19)
            raw_colors = colors.get(str(row_index), colors.get(row_index, []))
            if not isinstance(raw_colors, list) or len(raw_colors) != 20:
                continue
            color_row = []
            valid = True
            for cell in raw_colors:
                coerced = self._coerce_rgb_cell(cell)
                if coerced is None:
                    valid = False
                    break
                color_row.append(coerced[0])
            if valid:
                normalized_rows.append(row_index)
                normalized_colors[row_index] = color_row
        render_game = self._ensure_guest_render_game()
        if not render_game:
            return
        self._apply_guest_lock_feedback(data, render_game)
        if not normalized_rows:
            return
        render_game.line_clear_pending_rows = normalized_rows
        render_game.line_clear_pending_colors = normalized_colors
        try:
            render_game._start_line_clear_sweep(normalized_rows)
        except Exception:
            pass
        # Game / PvP / OnlinePvP / Coop ile parity: dalga + Quadrix burst
        try:
            cs = int(getattr(render_game, 'cell_size', 0) or 0)
            ox = int(getattr(render_game, 'board_offset_x', 0) or 0)
            oy = int(getattr(render_game, 'board_offset_y', 0) or 0)
            board_width_cells = int(getattr(getattr(render_game, 'board', None), 'width', 20) or 20)
            board_height_cells = int(getattr(getattr(render_game, 'board', None), 'height', 20) or 20)
            wave_list = getattr(render_game, 'line_clear_wave_effects', None)
            if isinstance(wave_list, list) and cs > 0:
                _queue_wave_effects(
                    wave_list,
                    normalized_rows,
                    ox,
                    oy,
                    cs,
                    board_width_cells,
                )
        except Exception:
            pass
        try:
            lines_count = self._clamp_int(data.get('lines', len(normalized_rows)), 0, 20)
            if lines_count >= 4:
                render_game.trigger_screen_shake(intensity=7, duration=20 / 60.0)
            elif lines_count >= 2:
                render_game.trigger_screen_shake(intensity=3, duration=10 / 60.0)
        except Exception:
            pass
        # Hücre-bazlı line-clear parçacık zinciri (Game / PvP parity)
        try:
            if hasattr(render_game, 'create_line_clear_particles'):
                render_game.create_line_clear_particles(
                    normalized_rows,
                    int(getattr(render_game, 'board_offset_x', 0) or 0),
                    int(getattr(render_game, 'board_offset_y', 0) or 0),
                    int(getattr(render_game, 'cell_size', 0) or 0),
                    board=getattr(render_game, 'board', None),
                )
        except Exception:
            pass
        # Combo / Quadrix merkezli patlama
        try:
            cs = int(getattr(render_game, 'cell_size', 0) or 0)
            ox = int(getattr(render_game, 'board_offset_x', 0) or 0)
            oy = int(getattr(render_game, 'board_offset_y', 0) or 0)
            board_width_cells = int(getattr(getattr(render_game, 'board', None), 'width', 20) or 20)
            board_height_cells = int(getattr(getattr(render_game, 'board', None), 'height', 20) or 20)
            _trigger_combo_burst(
                render_game,
                normalized_rows,
                int(self._clamp_int(data.get('lines', len(normalized_rows)), 0, 20)),
                ox,
                oy,
                cs,
                board_width_cells,
                board_height_cells,
            )
        except Exception:
            pass

        # Combo / Quadrix mesaj overlay'ı (Game / PvP / OnlinePvP / Coop ile parity)
        try:
            lines_count = self._clamp_int(data.get('lines', len(normalized_rows)), 0, 20)
            if lines_count == 4:
                render_game.combo_message = "QUADRIX!"
                render_game.combo_message_time = 120.0
            elif lines_count >= 2:
                if lines_count == 2:
                    render_game.combo_message = "DOUBLE!"
                elif lines_count == 3:
                    render_game.combo_message = "TRIPLE!"
                else:
                    render_game.combo_message = f"{lines_count}x CLEAR!"
                render_game.combo_message_time = 120.0
        except Exception:
            pass

    def _apply_guest_hard_drop_event(self, data: dict) -> None:
        if self.role != 'guest' or not isinstance(data, dict):
            return
        player = data.get('player', '')
        if player not in ('P1', 'P2'):
            return

        pending_inputs = getattr(self, '_guest_pending_inputs', None)
        if player == 'P2' and isinstance(pending_inputs, list):
            if any(str(action or '') == 'hard_drop' for _seq, action in pending_inputs):
                return

        render_game = self._ensure_guest_render_game()
        if render_game is None:
            return
        piece = self._piece_from_snapshot(data.get('piece'))
        if piece is None:
            return
        try:
            piece.y = self._clamp_int(
                data.get('end_y', getattr(piece, 'y', 0)),
                -8,
                25,
                getattr(piece, 'y', 0),
            )
        except Exception:
            pass
        piece = self._apply_block_style_to_guest_piece(piece)
        start_y = self._clamp_int(
            data.get('start_y', getattr(piece, 'y', 0)),
            -8,
            25,
            getattr(piece, 'y', 0),
        )
        self._trigger_guest_hard_drop_preview_effect(render_game, piece, start_y)

    def _process_messages(self):
        """Ağdan gelen mesajları işle."""
        for msg in self.net.get_messages():
            try:
                channel = getattr(msg, 'channel', CHANNEL_GAME)
                data = msg.data
                if not isinstance(data, dict):
                    continue
                msg_type = data.get('type', '')
                if not self._is_supported_message_channel(msg_type, channel):
                    continue

                opponent_id = int(getattr(self.net, 'opponent_steam_id', 0) or 0)
                my_id = int(getattr(self.net, 'my_steam_id', 0) or 0)
                sender = int(getattr(msg, 'sender', 0) or 0)

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
                        except Exception:
                            pass

                if opponent_id and sender and sender != opponent_id:
                    rebound = False
                    if self.online_state in (
                        OnlineCoopState.WAITING,
                        OnlineCoopState.READY_CHECK,
                        OnlineCoopState.COUNTDOWN,
                    ):
                        try:
                            members = set(self.net.get_lobby_members() or [])
                        except Exception:
                            members = set()
                        if sender in members and sender != my_id:
                            try:
                                self.net._opponent_steam_id = sender
                                opponent_id = sender
                                rebound = True
                            except Exception:
                                rebound = False
                    if not rebound:
                        print(f"[OnlineCoop] Bilinmeyen gönderici {sender} — mesaj ignore edildi.")
                        continue

                pending_disconnect_id = int(getattr(self, '_pending_disconnect_steam_id', 0) or 0)
                if sender and (sender == opponent_id or (pending_disconnect_id and sender == pending_disconnect_id)):
                    was_waiting_disconnect = self._disconnect_grace_timer > 0
                    self._pending_disconnect_steam_id = 0
                    self._disconnect_grace_timer = 0.0
                    if was_waiting_disconnect and self.paused:
                        self._set_pause_state(False)
                        if self.role == 'host':
                            self._send_game_event('resume')

                if (not bool(getattr(self, '_session_established', False))) and opponent_id and sender == opponent_id:
                    self._session_established = True
                    if self.online_state == OnlineCoopState.READY_CHECK and self.my_ready and not self.opponent_ready:
                        self._send_ready_signal(reason='message_session_established')

                if msg_type == MsgType.READY:
                    self.opponent_ready = True
                    self._check_both_ready()

                elif msg_type == 'session_ping':
                    if self.online_state == OnlineCoopState.READY_CHECK and self.my_ready and not self.opponent_ready:
                        self._send_ready_signal(reason='peer_session_ping')

                elif msg_type == MsgType.COOP_GAME_START:
                    self._on_game_start(data)

                elif msg_type == MsgType.COOP_GAME_CONFIG:
                    if self.role == 'guest':
                        normalized_config = self._normalize_authoritative_gameplay_config(data.get('config'))
                        self._authoritative_gameplay_config = dict(normalized_config)
                        if self.coop_game is not None:
                            self._apply_authoritative_guest_timing(self.coop_game, normalized_config)

                elif msg_type == MsgType.GUEST_PIECE_STATE:
                    self._apply_guest_authoritative_piece_state(data)

                # Co-op host: guest input processing
                elif msg_type == MsgType.GUEST_INPUT:
                    if self.role == 'host' and self.coop_game:
                        action = data.get('action', '')
                        if action not in (
                            'move_left',
                            'move_right',
                            'soft_drop_start',
                            'soft_drop_stop',
                            'rotate',
                            'hard_drop',
                            'hold',
                            'das_stop',
                            'das_stop_left',
                            'das_stop_right',
                            'pause_request',
                        ):
                            continue
                        try:
                            seq = int(data.get('seq', 0) or 0)
                        except (TypeError, ValueError):
                            seq = 0
                        if seq <= self._last_guest_input_seq:
                            continue
                        self._last_guest_input_seq = seq
                        if action == 'pause_request':
                            # Guest pause isteği → cooldown ile güvenli toggle
                            self._toggle_pause_safe()
                        elif action:
                            self._last_input_ack_seq = max(self._last_input_ack_seq, seq)
                            if self._gameplay_input_blocked():
                                self._send_piece_state()
                                continue
                            guest_piece_authority = bool(
                                getattr(self, '_guest_authoritative_piece_sync_enabled', False)
                            )
                            should_simulate_action = (
                                (not guest_piece_authority)
                                or self._guest_action_requires_host_simulation(action)
                            )
                            if should_simulate_action and self._guest_action_requires_host_control(action):
                                self.coop_game.inject_remote_input('P2', action)
                                self._send_piece_state()

                # Co-op guest: receive host state
                elif msg_type == MsgType.COOP_BOARD_STATE:
                    if self.role == 'guest':
                        try:
                            seq = int(data.get('seq', 0) or 0)
                        except (TypeError, ValueError):
                            seq = 0
                        if seq < self._guest_board_seq:
                            continue
                        normalized = self._normalize_board_snapshot(data)
                        if normalized is None:
                            print("[OnlineCoop] Geçersiz coop board snapshot — ignore.")
                            continue
                        self._guest_board_seq = seq
                        self._guest_board_cache = normalized
                        self._guest_score_cache.update({
                            'team_score': normalized.get('team_score', 0),
                            'total_lines': normalized.get('total_lines', 0),
                            'level': normalized.get('level', 1),
                        })

                elif msg_type == MsgType.COOP_PIECE_STATE:
                    if self.role == 'guest':
                        try:
                            seq = int(data.get('seq', 0) or 0)
                        except (TypeError, ValueError):
                            seq = 0
                        if seq <= self._guest_piece_seq:
                            continue
                        self._guest_piece_seq = seq
                        self._guest_piece_cache = self._normalize_piece_snapshot(data)

                elif msg_type == MsgType.COOP_LOCK_EVENT:
                    if self.role == 'guest':
                        self._apply_guest_lock_event(data)

                elif msg_type == MsgType.COOP_GAME_EVENT:
                    event_name = data.get('event', '')
                    if event_name == 'game_over':
                        self.game_over = True
                        self.online_state = OnlineCoopState.GAME_OVER
                        self._guest_score_cache.update(data.get('data', {}))
                    elif event_name == 'pause':
                        self._set_pause_state(True)
                        self._freeze_active_gameplay_input()
                    elif event_name == 'resume':
                        self._set_pause_state(False)
                        self._freeze_active_gameplay_input()
                    elif event_name == 'hard_drop':
                        self._apply_guest_hard_drop_event(data.get('data', {}) or {})
                    elif event_name == 'hold_used':
                        try:
                            self.sound.play('hold')
                        except Exception:
                            pass
                    elif event_name in ('player_frozen', 'player_unfrozen'):
                        event_data = data.get('data', {}) or {}
                        if isinstance(event_data, dict):
                            player = event_data.get('player')
                            if self._guest_board_cache and player in ('P1', 'P2'):
                                key = 'p1_frozen' if player == 'P1' else 'p2_frozen'
                                self._guest_board_cache[key] = event_name == 'player_frozen'

                elif msg_type == MsgType.REMATCH:
                    self._opponent_rematch = True
                    self._check_both_rematch()

            except Exception as e:
                print(f"[OnlineCoop] Mesaj işleme hatası: {e}")

    def _check_both_ready(self):
        """İki oyuncu da hazırsa countdown başlat."""
        if self.online_state != OnlineCoopState.READY_CHECK:
            return
        if self.my_ready and self.opponent_ready:
            if self.net.is_host:
                if not self._game_start_pending_payload:
                    self._game_seed = random.randint(1, 999999)
                    self._game_start_pending_payload = {
                        'seed': self._game_seed,
                        'sub_mode': self.selected_submode,
                    }
                    self._game_start_retry_timer = 0.0
                if self._game_start_retry_timer <= 0:
                    start_ok = self._send_coop_start_payload(self._game_start_pending_payload)
                    if start_ok:
                        self._game_start_pending_payload = None
                        self._game_start_retry_timer = 0.0
                        self._start_countdown()
                    else:
                        self._game_start_retry_timer = self._GAME_START_RETRY_INTERVAL_MS

    def _check_both_rematch(self):
        """İki oyuncu da rematch istediyse yeniden countdown başlat."""
        if self.online_state != OnlineCoopState.GAME_OVER:
            return
        if self._my_rematch and self._opponent_rematch:
            self._my_rematch = False
            self._opponent_rematch = False
            self.game_over = False
            self.coop_game = None
            self._guest_board_cache = None
            self._guest_piece_cache = None
            self._guest_score_cache = {}
            self._guest_render_board_seq = -1
            self._guest_render_piece_seq = -1
            if self.net.is_host:
                self._game_seed = random.randint(1, 999999)
                self._game_start_pending_payload = {
                    'seed': self._game_seed,
                    'sub_mode': self.selected_submode,
                }
                if self._send_coop_start_payload(self._game_start_pending_payload):
                    self._game_start_pending_payload = None
                    self._start_countdown()
                else:
                    self._game_start_retry_timer = self._GAME_START_RETRY_INTERVAL_MS

    def _send_coop_start_payload(self, payload: dict | None) -> bool:
        if not payload:
            return False
        seed = int(payload.get('seed', 0) or 0)
        sub_mode = str(payload.get('sub_mode', self.selected_submode) or self.selected_submode)
        config = self._build_authoritative_gameplay_config()
        self._authoritative_gameplay_config = dict(config)
        send_coop_start = getattr(self.net, 'send_coop_start', None)
        if callable(send_coop_start):
            return bool(send_coop_start(seed, sub_mode=sub_mode, config=config))
        return bool(self.net.send({
            'type': MsgType.COOP_GAME_START,
            'seed': seed,
            'sub_mode': sub_mode,
            'timestamp': time.time(),
            'config': config,
        }, reliable=True, channel=CHANNEL_CONTROL))

    def _start_countdown(self):
        """3-2-1 geri sayım başlat."""
        self.online_state = OnlineCoopState.COUNTDOWN
        self.countdown_value = 3
        self.countdown_timer = 0
        try:
            self.sound.stop_music()
        except Exception:
            pass

    def _start_gameplay_music(self):
        """Gameplay co-op müziğini başlat (host ve guest için).

        Countdown sırasında `stop_music()` çağrıldı. Gameplay'e geçişte
        coop playlist'ini açıkça yeniden kuruyoruz; CoopGame.__init__'in
        `_start_music()` çağrısı yardımcı olsa da guest tarafında
        `_ensure_guest_render_game()` her zaman __init__'i çağırmadığı için
        wrapper düzeyinde explicit restart playlist ownership'i netleştirir.
        """
        sound = getattr(self, 'sound', None)
        if sound is None or not getattr(sound, 'music_enabled', True):
            return
        try:
            if hasattr(sound, 'unduck_music'):
                sound.unduck_music()
        except Exception:
            pass

        ensure_track_available = getattr(sound, 'ensure_track_available', None)
        playlist_values: list = []
        if self.settings_manager:
            try:
                playlist_values = list(
                    self.settings_manager.get_music_playlist_for_mode('coop') or []
                )
            except Exception:
                playlist_values = []

        track_keys: list[str] = []
        if playlist_values and callable(ensure_track_available):
            for value in playlist_values:
                try:
                    track_key = ensure_track_available(value)
                except Exception:
                    track_key = None
                if track_key:
                    track_keys.append(track_key)

        if track_keys:
            try:
                do_shuffle = bool(self.settings_manager.get('music_shuffle', False)) if self.settings_manager else False
            except Exception:
                do_shuffle = False
            try:
                start_index = 0 if do_shuffle else random.randrange(len(track_keys))
            except Exception:
                start_index = 0
            try:
                sound.set_music_playlist(
                    track_keys,
                    loop=True,
                    start_index=start_index,
                    autoplay=True,
                    force=True,
                    shuffle=do_shuffle,
                )
                return
            except Exception:
                pass

        # Fallback: tek parça
        preferred = None
        if self.settings_manager:
            try:
                overrides = self.settings_manager.get_mode_music_overrides() if hasattr(
                    self.settings_manager, 'get_mode_music_overrides'
                ) else {}
                preferred = overrides.get('coop') if isinstance(overrides, dict) else None
            except Exception:
                preferred = None
            if not preferred:
                try:
                    preferred = self.settings_manager.get('coop_music')
                except Exception:
                    preferred = None
            if not preferred:
                try:
                    preferred = self.settings_manager.get('game_music')
                except Exception:
                    preferred = None
        track_key = ensure_track_available(preferred or 'pvp_1') if callable(ensure_track_available) else (preferred or 'pvp_1')
        if track_key:
            try:
                sound.set_music_playlist([track_key], loop=True, autoplay=True, force=True)
            except Exception:
                pass

    def _on_game_start(self, data: dict):
        """Guest tarafında game_start mesajını işle."""
        if self.online_state not in (
            OnlineCoopState.READY_CHECK,
            OnlineCoopState.COUNTDOWN,
            OnlineCoopState.GAME_OVER,
        ):
            return
        self._game_seed = data.get('seed', 0)
        self.selected_submode = str(data.get('sub_mode', self.selected_submode) or self.selected_submode)
        self._authoritative_gameplay_config = self._normalize_authoritative_gameplay_config(data.get('config'))
        self._game_start_pending_payload = None
        self._game_start_retry_timer = 0.0
        self.online_state = OnlineCoopState.COUNTDOWN
        self.countdown_value = 3
        self.countdown_timer = 0

    # ============================================================
    #  GAME LIFECYCLE
    # ============================================================

    def _start_game(self):
        """Countdown bittikten sonra oyunu başlat."""
        self.online_state = OnlineCoopState.PLAYING
        self.game_over = False
        self.paused = False
        try:
            self._held_gameplay_keys.clear()
        except Exception:
            self._held_gameplay_keys = set()

        if self.role == 'host':
            # Host: tam CoopGame simülasyonu oluştur
            self.coop_game = CoopGame(
                sound_enabled=True,
                effects_enabled=True,
                screen=self.screen,
                fullscreen=self.fullscreen,
                user_manager=self.user_manager,
                settings_manager=self.settings_manager,
                sound_manager=self.sound,
                piece_rng_seed=(int(self._game_seed) if int(self._game_seed or 0) > 0 else None),
            )
            # Çift playlist tick riskini önlemek için CoopGame'in iç
            # `update_music_playlist()` çağrısını bastır. Online wrapper
            # her frame zaten kendi tick'ini atıyor.
            try:
                self.coop_game._suppress_internal_music_tick = True
            except Exception:
                pass
            # Event listener: lock/clear/game_over gibi olayları guest'e yayınla
            self.coop_game._event_listeners.append(self._on_coop_event)
            remote_players = getattr(self.coop_game, 'remote_authority_players', None)
            if not isinstance(remote_players, set):
                remote_players = set(remote_players or []) if remote_players is not None else set()
                self.coop_game.remote_authority_players = remote_players
            # Default online co-op is host-authoritative. Only the experimental
            # guest-authoritative mirror may disable host-side P2 active updates.
            if bool(getattr(self, '_guest_authoritative_piece_sync_enabled', False)):
                remote_players.add('P2')
            else:
                remote_players.discard('P2')
            self._last_frozen_flags = (
                bool(self.coop_game.p1_frozen),
                bool(self.coop_game.p2_frozen),
            )
            self._authoritative_gameplay_config = self._build_authoritative_gameplay_config()
            # Host otoriter kalır; seed sadece bag sırasını maç bazında sabitler.
        else:
            # Guest: state cache'leri temizle
            self._guest_board_cache = None
            self._guest_piece_cache = None
            self._guest_score_cache = {}
            self._guest_pending_inputs = []
            self._guest_input_seq = 0
            self._guest_piece_state_out_seq = 0
            self._guest_board_seq = -1
            self._guest_piece_seq = -1
            self._last_guest_piece_state_seq = 0
            self._last_host_guest_piece_ack_seq = 0
            self._guest_piece_unacked_since = 0.0
            self._last_sent_board_cells = None
            self._last_guest_sent_piece_signature = None
            self._last_piece_state_signature = None
            self._guest_render_board_seq = -1
            self._guest_render_piece_seq = -1
            self._guest_last_authoritative_piece_elapsed_ms = 0.0
            self._guest_local_prediction_ms = 0.0
            self._guest_piece_state_timer = 0.0
            self._ensure_guest_render_game()

        # Broadcast timer'larını sıfırla
        self._board_state_timer = 0.0
        self._piece_state_timer = 0.0
        self._last_input_ack_seq = 0
        self._guest_pending_inputs = []
        self._last_guest_input_seq = 0
        self._last_guest_piece_state_seq = 0
        self._last_host_guest_piece_ack_seq = 0
        self._guest_piece_unacked_since = 0.0
        self._board_state_seq = 0
        self._piece_state_seq = 0
        self._guest_piece_state_out_seq = 0
        self._guest_piece_state_timer = 0.0
        self._last_sent_board_cells = None
        self._last_guest_sent_piece_signature = None
        self._last_piece_state_signature = None
        self._guest_last_authoritative_piece_elapsed_ms = 0.0
        self._guest_local_prediction_ms = 0.0
        if self.role == 'host':
            self._send_gameplay_config()
            self._send_board_state(force_full=True)
            self._send_piece_state()

        # Countdown sırasında müzik durdurulmuştu — gameplay'e geçişte coop
        # playlist'ini explicit restart et. Host CoopGame.__init__'i içinde
        # `_start_music()` çağırsa da güvenli tarafta wrapper düzeyinde de
        # yeniden başlatıyoruz; guest tarafında CoopGame'in `sound_enabled`'ı
        # kapalı olduğu için bu çağrı gameplay müziğinin tek garantisidir.
        self._start_gameplay_music()

    def _on_coop_event(self, event_type: str, event_data: dict):
        """CoopGame event listener — host lock/clear/freeze olaylarını guest'e iletir."""
        if self.role != 'host':
            return
        if event_type == 'lines_cleared':
            self._send_lock_event(event_data, event_name='lines_cleared')
            self._send_board_state()
            self._send_piece_state()
        elif event_type == 'piece_placed':
            self._send_lock_event(event_data, event_name='piece_placed')
            self._send_board_state()
            self._send_piece_state()
        elif event_type == 'hard_drop':
            self._send_hard_drop_event(event_data)
            self._send_piece_state()
        elif event_type == 'hold_used':
            self._send_game_event('hold_used', event_data)
            self._send_piece_state()
        elif event_type == 'player_frozen':
            self._send_game_event('player_frozen', event_data)
            self._send_board_state()
            self._send_piece_state()

    # ============================================================
    #  HOST STATE BROADCASTING
    # ============================================================

    def _get_ghost_y(self, player: str) -> int:
        """Belirli oyuncunun ghost (düşme hedefi) Y pozisyonunu hesapla."""
        if not self.coop_game:
            return 0
        piece = self.coop_game.p1_current_piece if player == 'P1' else self.coop_game.p2_current_piece
        if not piece:
            return 0
        board = self.coop_game.board
        orig_y = piece.y
        while board.is_valid_position_for_player(piece, player, dy=1):
            piece.y += 1
        ghost = piece.y
        piece.y = orig_y
        return ghost

    @staticmethod
    def _piece_signature(piece) -> tuple[int, int, int, int] | None:
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

    def _current_piece_state_signature(self):
        if not self.coop_game:
            return None

        def _shape_index(piece) -> int:
            if not piece:
                return -1
            try:
                return int(getattr(piece, 'shape_index', -1))
            except (TypeError, ValueError):
                return -1

        return (
            self._piece_signature(getattr(self.coop_game, 'p1_current_piece', None)),
            self._piece_signature(getattr(self.coop_game, 'p2_current_piece', None)),
            _shape_index(getattr(self.coop_game, 'p1_next_piece', None)),
            _shape_index(getattr(self.coop_game, 'p2_next_piece', None)),
            _shape_index(getattr(self.coop_game, 'p1_hold_piece', None)),
            _shape_index(getattr(self.coop_game, 'p2_hold_piece', None)),
            int(self._get_ghost_y('P1')),
            int(self._get_ghost_y('P2')),
            int(getattr(self, '_last_input_ack_seq', 0) or 0),
            bool(getattr(self.coop_game, 'p1_frozen', False)),
            bool(getattr(self.coop_game, 'p2_frozen', False)),
        )

    def _push_piece_state_if_changed(self, force: bool = False) -> bool:
        signature = self._current_piece_state_signature()
        if not force and signature == getattr(self, '_last_piece_state_signature', None):
            return False
        self._send_piece_state()
        return True

    def _build_authoritative_gameplay_config(self) -> dict:
        settings_manager = getattr(self, 'settings_manager', None)
        try:
            das_delay = float(settings_manager.get('das_delay', DAS_DELAY)) if settings_manager else float(DAS_DELAY)
        except Exception:
            das_delay = float(DAS_DELAY)
        try:
            das_repeat = float(settings_manager.get('das_repeat', DAS_REPEAT)) if settings_manager else float(DAS_REPEAT)
        except Exception:
            das_repeat = float(DAS_REPEAT)

        config = {
            'das_delay': max(0.0, das_delay),
            'das_repeat': max(1.0, das_repeat),
            'enable_lock_delay': True,
            'lock_delay': float(DEFAULT_LOCK_DELAY),
            'soft_drop_speed': float(getattr(CoopGame, '_SOFT_DROP_SPEED', 50.0) or 50.0),
        }

        if self.coop_game is not None:
            das_delay = float(getattr(self.coop_game, '_cached_das_delay', das_delay) or das_delay)
            das_repeat = float(getattr(self.coop_game, '_cached_das_repeat', das_repeat) or das_repeat)
            if bool(getattr(self.coop_game, '_das_settings_dirty', False)):
                coop_settings = getattr(self.coop_game, 'settings_manager', None) or settings_manager
                if coop_settings is not None:
                    try:
                        das_delay = float(coop_settings.get('das_delay', das_delay))
                    except Exception:
                        pass
                    try:
                        das_repeat = float(coop_settings.get('das_repeat', das_repeat))
                    except Exception:
                        pass
            config['enable_lock_delay'] = bool(getattr(self.coop_game, 'enable_lock_delay', True))
            config['lock_delay'] = max(
                0.0,
                float(getattr(self.coop_game, 'lock_delay', DEFAULT_LOCK_DELAY) or DEFAULT_LOCK_DELAY),
            )
            config['soft_drop_speed'] = max(
                1.0,
                float(getattr(self.coop_game, '_SOFT_DROP_SPEED', config['soft_drop_speed']) or config['soft_drop_speed']),
            )

        config['das_delay'] = max(0.0, das_delay)
        config['das_repeat'] = max(1.0, das_repeat)

        return config

    def _get_authoritative_das_config(self) -> tuple[float, float]:
        config = self._build_authoritative_gameplay_config()
        return float(config.get('das_delay', 0.0) or 0.0), float(config.get('das_repeat', 1.0) or 1.0)

    @staticmethod
    def _normalize_authoritative_gameplay_config(config: dict | None) -> dict:
        raw = config if isinstance(config, dict) else {}

        def _clamp_float(key: str, default: float, minimum: float, maximum: float) -> float:
            try:
                value = float(raw.get(key, default))
            except (TypeError, ValueError):
                value = float(default)
            return max(minimum, min(maximum, value))

        return {
            'das_delay': _clamp_float('das_delay', float(DAS_DELAY), 0.0, 5000.0),
            'das_repeat': _clamp_float('das_repeat', float(DAS_REPEAT), 1.0, 5000.0),
            'lock_delay': _clamp_float('lock_delay', float(DEFAULT_LOCK_DELAY), 0.0, 10000.0),
            'soft_drop_speed': _clamp_float('soft_drop_speed', float(getattr(CoopGame, '_SOFT_DROP_SPEED', 50.0) or 50.0), 1.0, 5000.0),
            'enable_lock_delay': bool(raw.get('enable_lock_delay', True)),
        }

    @staticmethod
    def _apply_authoritative_guest_timing(render_game, timing_data: dict) -> None:
        if render_game is None or not isinstance(timing_data, dict):
            return

        normalized = OnlineCoopGame._normalize_authoritative_gameplay_config(timing_data)
        try:
            render_game._cached_das_delay = float(normalized['das_delay'])
            render_game._cached_das_repeat = float(normalized['das_repeat'])
            render_game._das_settings_dirty = False
            render_game.enable_lock_delay = bool(normalized['enable_lock_delay'])
            render_game.lock_delay = float(normalized['lock_delay'])
            render_game._SOFT_DROP_SPEED = float(normalized['soft_drop_speed'])
        except Exception:
            pass

    def _capture_semantic_board_cells(self) -> dict[tuple[int, int], tuple]:
        if not self.coop_game:
            return {}
        board = self.coop_game.board
        texture_grid = getattr(board, 'texture_grid', None)
        gold_grid = getattr(board, 'gold', None)
        captured: dict[tuple[int, int], tuple] = {}
        for y in range(getattr(board, 'height', 0)):
            for x in range(getattr(board, 'width', 0)):
                if not board.occupancy[y][x]:
                    continue
                locked_slice = None
                if isinstance(texture_grid, list) and y < len(texture_grid) and x < len(texture_grid[y]):
                    locked_slice = texture_grid[y][x]
                piece_name = ''
                rel_x = 0
                rel_y = 0
                width = 1
                height = 1
                rotation = 0
                if isinstance(locked_slice, TextureSlice):
                    piece_name = str(getattr(locked_slice, 'piece_name', '') or '')
                    rel_x = int(getattr(locked_slice, 'rel_x', 0) or 0)
                    rel_y = int(getattr(locked_slice, 'rel_y', 0) or 0)
                    width = max(1, int(getattr(locked_slice, 'width', 1) or 1))
                    height = max(1, int(getattr(locked_slice, 'height', 1) or 1))
                    rotation = int(getattr(locked_slice, 'rotation', 0) or 0) % 4
                color = board.grid[y][x]
                if isinstance(color, (list, tuple)) and len(color) >= 3:
                    r = max(0, min(255, int(color[0])))
                    g = max(0, min(255, int(color[1])))
                    b = max(0, min(255, int(color[2])))
                else:
                    r, g, b = _BOARD_EMPTY_COLOR
                owner = board.owners[y][x] if hasattr(board, 'owners') else None
                captured[(x, y)] = (
                    piece_name,
                    owner or '',
                    rel_x,
                    rel_y,
                    width,
                    height,
                    rotation,
                    bool(
                        isinstance(gold_grid, list)
                        and y < len(gold_grid)
                        and x < len(gold_grid[y])
                        and gold_grid[y][x]
                    ),
                    r,
                    g,
                    b,
                )
        return captured

    @staticmethod
    def _serialize_semantic_board_cells(items) -> list[list]:
        serialized = []
        for (x, y), payload in sorted(items, key=lambda item: (item[0][1], item[0][0])):
            piece_name, owner, rel_x, rel_y, width, height, rotation, is_gold, r, g, b = payload
            serialized.append([
                int(x),
                int(y),
                str(piece_name or ''),
                str(owner or ''),
                int(rel_x),
                int(rel_y),
                int(width),
                int(height),
                int(rotation),
                1 if is_gold else 0,
                int(r),
                int(g),
                int(b),
            ])
        return serialized

    @staticmethod
    def _serialize_removed_cells(positions) -> list[list[int]]:
        return [[int(x), int(y)] for x, y in sorted(positions, key=lambda item: (item[1], item[0]))]

    @staticmethod
    def _local_locked_block_color(render_game, piece_name: str, fallback_color: tuple[int, int, int]) -> tuple[int, int, int]:
        color = fallback_color
        try:
            if piece_name and getattr(render_game, 'theme_manager', None) is not None:
                color = tuple(render_game.theme_manager.get_piece_color(piece_name)[:3])
        except Exception:
            color = fallback_color
        try:
            block_style_manager = getattr(render_game, 'block_style_manager', None)
            if piece_name and block_style_manager is not None:
                styled = block_style_manager.get_color(piece_name, color)
                color = (int(styled[0]), int(styled[1]), int(styled[2]))
        except Exception:
            color = fallback_color
        return color

    def _send_gameplay_config(self):
        config = self._build_authoritative_gameplay_config()
        self._authoritative_gameplay_config = dict(config)
        self.net.send({
            'type': MsgType.COOP_GAME_CONFIG,
            'config': config,
        }, reliable=True, channel=CHANNEL_CONTROL)

    @staticmethod
    def _expected_channel_for_message(msg_type: str) -> int:
        if msg_type in {
            MsgType.GUEST_PIECE_STATE,
            MsgType.COOP_BOARD_STATE,
            MsgType.COOP_PIECE_STATE,
            MsgType.BOARD_STATE,
            MsgType.PIECE_POSITION,
            MsgType.SCORE_UPDATE,
        }:
            return CHANNEL_STATE
        if msg_type in {
            MsgType.READY,
            MsgType.GAME_START,
            MsgType.GAME_OVER,
            MsgType.REMATCH,
            MsgType.GARBAGE_ATTACK,
            MsgType.GUEST_INPUT,
            MsgType.COOP_GAME_START,
            MsgType.COOP_GAME_CONFIG,
            MsgType.COOP_LOCK_EVENT,
            MsgType.COOP_GAME_EVENT,
            'session_ping',
        }:
            return CHANNEL_CONTROL
        return CHANNEL_GAME

    @classmethod
    def _is_supported_message_channel(cls, msg_type: str, channel: int) -> bool:
        expected = cls._expected_channel_for_message(msg_type)
        return channel in (CHANNEL_GAME, expected)

    def _send_board_state(self, force_full: bool = False):
        """Host → Guest: semantic board delta/full snapshot (unreliable)."""
        if not self.coop_game:
            return
        current_cells = self._capture_semantic_board_cells()
        previous_cells = self._last_sent_board_cells if isinstance(self._last_sent_board_cells, dict) else None
        full_snapshot = bool(force_full or previous_cells is None)
        if full_snapshot:
            changed_items = list(current_cells.items())
            removed_positions = []
        else:
            changed_items = [
                (position, payload)
                for position, payload in current_cells.items()
                if previous_cells.get(position) != payload
            ]
            removed_positions = [position for position in previous_cells if position not in current_cells]

        gameplay_config = self._build_authoritative_gameplay_config()
        self._board_state_seq += 1

        data = {
            'type': MsgType.COOP_BOARD_STATE,
            'seq': self._board_state_seq,
            'format': 'semantic_delta_v1',
            'full': full_snapshot,
            'cells': self._serialize_semantic_board_cells(changed_items),
            'team_score': self.coop_game.team_score,
            'total_lines': self.coop_game.total_lines_cleared,
            'level': self.coop_game.level,
            'fall_speed': self.coop_game.fall_speed,
            'p1_frozen': self.coop_game.p1_frozen,
            'p2_frozen': self.coop_game.p2_frozen,
            'input_ack': self._last_input_ack_seq,
            'guest_piece_ack': self._last_guest_piece_state_seq,
            **gameplay_config,
        }
        if removed_positions:
            data['removed'] = self._serialize_removed_cells(removed_positions)

        self._last_sent_board_cells = current_cells
        self.net.send(data, reliable=False, channel=CHANNEL_STATE)

    def _send_piece_state(self):
        """Host → Guest: aktif parça pozisyonları (unreliable)."""
        if not self.coop_game:
            return
        self._piece_state_seq += 1

        def _piece_dict(piece):
            if not piece:
                return None
            return {
                'x': piece.x, 'y': piece.y,
                'si': piece.shape_index,
                'r': piece.rotation_state,
            }

        def _shape_index(piece):
            return piece.shape_index if piece else -1

        gameplay_config = self._build_authoritative_gameplay_config()

        data = {
            'type': MsgType.COOP_PIECE_STATE,
            'seq': self._piece_state_seq,
            'p1_current': _piece_dict(self.coop_game.p1_current_piece),
            'p2_current': _piece_dict(self.coop_game.p2_current_piece),
            'p1_next_si': _shape_index(self.coop_game.p1_next_piece),
            'p2_next_si': _shape_index(self.coop_game.p2_next_piece),
            'p1_hold_si': _shape_index(self.coop_game.p1_hold_piece),
            'p2_hold_si': _shape_index(self.coop_game.p2_hold_piece),
            'p1_ghost_y': self._get_ghost_y('P1'),
            'p2_ghost_y': self._get_ghost_y('P2'),
            'input_ack': self._last_input_ack_seq,
            'guest_piece_ack': self._last_guest_piece_state_seq,
            'host_elapsed_ms': max(0.0, float(getattr(self.coop_game, 'elapsed_time', 0.0) or 0.0)),
            **gameplay_config,
        }
        self._last_piece_state_signature = self._current_piece_state_signature()
        self.net.send(data, reliable=False, channel=CHANNEL_STATE)

    def _send_lock_event(self, event_data: dict, event_name: str = 'lines_cleared'):
        """Host → Guest: parça kilit / satır temizleme olayı (reliable)."""
        event_data = event_data or {}
        cleared_row_colors = {}
        cleared_rows = []
        if self.coop_game:
            try:
                raw_colors = getattr(self.coop_game.board, 'last_clear_row_colors', {}) or {}
                for row_index, row_colors in raw_colors.items():
                    normalized_row = int(row_index)
                    cleared_rows.append(normalized_row)
                    cleared_row_colors[str(normalized_row)] = [
                        list(color[:3]) if isinstance(color, (list, tuple)) else [0, 0, 0]
                        for color in row_colors[:20]
                    ]
            except Exception:
                cleared_row_colors = {}
                cleared_rows = []
        data = {
            'type': MsgType.COOP_LOCK_EVENT,
            'event': event_name,
            'player': event_data.get('player', ''),
            'lock_cells': self._serialize_piece_lock_cells(event_data.get('piece')),
            'new_score': self.coop_game.team_score if self.coop_game else 0,
            'new_level': self.coop_game.level if self.coop_game else 1,
            'lines': event_data.get('lines', 0),
            'total_lines': event_data.get('total_lines', 0),
            'p1_frozen': self.coop_game.p1_frozen if self.coop_game else False,
            'p2_frozen': self.coop_game.p2_frozen if self.coop_game else False,
            'cleared_rows': sorted(cleared_rows),
            'row_colors': cleared_row_colors,
        }
        self.net.send(data, reliable=True, channel=CHANNEL_CONTROL)

    def _send_hard_drop_event(self, event_data: dict) -> None:
        """Host → Guest: hard drop trail/shake effect payload."""
        event_data = event_data or {}
        piece = event_data.get('piece')
        try:
            start_y = int(event_data.get('start_y', getattr(piece, 'y', 0) or 0) or 0)
        except (TypeError, ValueError):
            start_y = int(getattr(piece, 'y', 0) or 0)
        try:
            end_y = int(event_data.get('end_y', getattr(piece, 'y', start_y) or start_y) or start_y)
        except (TypeError, ValueError):
            end_y = int(getattr(piece, 'y', start_y) or start_y)
        self._send_game_event('hard_drop', {
            'player': event_data.get('player', ''),
            'piece': self._guest_piece_dict(piece),
            'start_y': start_y,
            'end_y': end_y,
        })

    def _send_game_event(self, event_name: str, event_data: dict = None):
        """Host → Guest: genel oyun olayı (reliable)."""
        data = {
            'type': MsgType.COOP_GAME_EVENT,
            'event': event_name,
            'data': event_data or {},
        }
        self.net.send(data, reliable=True, channel=CHANNEL_CONTROL)

    # ============================================================
    #  GUEST INPUT SENDING
    # ============================================================

    def _trigger_guest_hard_drop_preview_effect(self, render_game, piece, start_y: int) -> None:
        if render_game is None or piece is None:
            return
        if not bool(getattr(render_game, 'effects_enabled', False)):
            return
        distance = int(getattr(piece, 'y', start_y) or start_y) - int(start_y or 0)
        if distance <= 0:
            return
        try:
            cs = int(getattr(render_game, 'cell_size', 0) or 0)
            if cs <= 0:
                return
            ox = int(getattr(render_game, 'board_offset_x', 0) or 0)
            oy = int(getattr(render_game, 'board_offset_y', 0) or 0)
            for px, py_abs in piece.get_cells():
                row_offset = int(py_abs) - int(getattr(piece, 'y', 0) or 0)
                trail_x = ox + int(px) * cs
                trail_y_start = oy + (int(start_y) + row_offset) * cs
                trail_y_end = oy + int(py_abs) * cs
                if trail_y_end > trail_y_start:
                    render_game.create_drop_trail(
                        trail_x,
                        trail_y_start,
                        trail_y_end,
                        getattr(piece, 'color', (128, 128, 128)),
                        cs,
                    )
            render_game.trigger_hard_drop_screen_shake()
        except Exception:
            pass

    @staticmethod
    def _serialize_piece_lock_cells(piece) -> list[list[int]]:
        if piece is None or not hasattr(piece, 'get_cells'):
            return []
        color_matrix = getattr(piece, 'color_matrix', None)
        fallback_color = tuple(getattr(piece, 'color', (128, 128, 128))[:3])
        cells: list[list[int]] = []
        try:
            for px, py in piece.get_cells():
                if not (0 <= int(px) < 20 and 0 <= int(py) < 20):
                    continue
                color = fallback_color
                if isinstance(color_matrix, list):
                    rel_y = int(py) - int(getattr(piece, 'y', 0) or 0)
                    rel_x = int(px) - int(getattr(piece, 'x', 0) or 0)
                    try:
                        matrix_color = color_matrix[rel_y][rel_x]
                        if matrix_color is not None:
                            color = tuple(matrix_color[:3])
                    except Exception:
                        color = fallback_color
                cells.append([
                    int(px),
                    int(py),
                    max(0, min(255, int(color[0]))),
                    max(0, min(255, int(color[1]))),
                    max(0, min(255, int(color[2]))),
                ])
        except Exception:
            return []
        return cells

    def _apply_guest_lock_feedback(self, data: dict, render_game) -> None:
        if render_game is None or not isinstance(data, dict):
            return
        raw_cells = data.get('lock_cells', [])
        if not isinstance(raw_cells, list) or not raw_cells:
            return
        try:
            cs = int(getattr(render_game, 'cell_size', 0) or 0)
            if cs <= 0:
                return
            ox = int(getattr(render_game, 'board_offset_x', 0) or 0)
            oy = int(getattr(render_game, 'board_offset_y', 0) or 0)
            for entry in raw_cells[:16]:
                if not isinstance(entry, (list, tuple)) or len(entry) < 5:
                    continue
                x = self._clamp_int(entry[0], 0, 19)
                y = self._clamp_int(entry[1], 0, 19)
                color = (
                    self._clamp_int(entry[2], 0, 255),
                    self._clamp_int(entry[3], 0, 255),
                    self._clamp_int(entry[4], 0, 255),
                )
                render_game.create_lock_explosion(
                    ox + x * cs + cs // 2,
                    oy + y * cs + cs // 2,
                    color,
                    cs,
                )
        except Exception:
            pass

    def _predict_guest_input(self, action: str):
        """Guest'te kendi parçasını anında oynat; host snapshot'ı otoriter kalır.

        Reaktivite kök iyileştirmesi: input sırasında render cache'i (host
        board snapshot uygulaması) tetiklemiyoruz. Render cache her frame
        `_update_guest_local_prediction` üzerinden zaten ilerletiliyor; input
        anında ek bir cache uygulaması yapmak art arda gelen input'larda
        gereksiz iş yaratıyor ve özellikle yeni board snapshot bekleyen
        durumlarda input ile snapshot uygulaması yarışıp algılanan lag'a
        sebep olabiliyor. Inject doğrudan mevcut CoopGame state'i üzerinden
        çalışsın — kimlik eşleşmesi `_apply_guest_render_cache` tarafında
        zaten korunuyor.
        """
        if self.role != 'guest' or self.online_state != OnlineCoopState.PLAYING:
            return
        if self.game_over or self.paused or action == 'pause_request':
            return
        # CoopGame'i mevcut hâliyle al — cache uygulamasını atla.
        render_game = self.coop_game if self.coop_game is not None else self._ensure_guest_render_game()
        # Eğer hiç render game yoksa ve cache verisi varsa, ilk uygulama
        # için cache'i bir kez tetikleyebiliriz (cold-start korumacı).
        if render_game is None and self._guest_board_cache and self._guest_piece_cache:
            render_game = self._apply_guest_render_cache()
        if not render_game:
            return
        try:
            if action == 'hard_drop':
                piece = getattr(render_game, 'p2_current_piece', None)
                board = getattr(render_game, 'board', None)
                if piece is not None and board is not None and hasattr(board, 'is_valid_position_for_player'):
                    start_y = int(getattr(piece, 'y', 0) or 0)
                    while board.is_valid_position_for_player(piece, 'P2', dy=1):
                        piece.y += 1
                    self._trigger_guest_hard_drop_preview_effect(render_game, piece, start_y)
                    try:
                        render_game._reset_player_lock_state('P2')
                    except Exception:
                        pass
                    try:
                        render_game.p2_soft_drop_active = False
                        render_game.p2_das_direction = 0
                        render_game.p2_fall_time = 0.0
                        render_game.p2_grounded = True
                        render_game.p2_lock_timer = max(
                            float(getattr(render_game, 'p2_lock_timer', 0.0) or 0.0),
                            float(render_game._effective_lock_delay_for_player('P2', piece)),
                        )
                    except Exception:
                        pass
                else:
                    render_game.inject_remote_input('P2', action)
            else:
                render_game.inject_remote_input('P2', action)
        except Exception:
            pass

    def _send_guest_input(self, action: str):
        """Guest → Host: input aksiyonu gönder (reliable)."""
        if action != 'pause_request' and (
            self.online_state != OnlineCoopState.PLAYING
            or bool(getattr(self, 'game_over', False))
            or bool(getattr(self, 'paused', False))
        ):
            return False
        self._guest_input_seq = getattr(self, '_guest_input_seq', 0) + 1
        if action != 'pause_request' and self._guest_action_requires_host_control(action):
            pending_inputs = getattr(self, '_guest_pending_inputs', None)
            if not isinstance(pending_inputs, list):
                pending_inputs = []
            pending_inputs.append((self._guest_input_seq, str(action or '')))
            self._guest_pending_inputs = pending_inputs[-64:]
        data = {
            'type': MsgType.GUEST_INPUT,
            'action': action,
            'seq': self._guest_input_seq,
            'ts': time.time(),
        }
        return self.net.send(data, reliable=True, channel=CHANNEL_CONTROL)

    def draw(self):
        """Ekranı çiz."""
        self._lobby_buttons.clear()

        # Arka plan (PLAYING host'ta CoopGame kendi arka planını çizer)
        if not (self.online_state == OnlineCoopState.PLAYING and self.role == 'host' and self.coop_game):
            _rs.draw_background(self.screen)
            self.background_fx.update(self.screen)
            self.background_fx.draw(self.screen)

        if self.online_state == OnlineCoopState.LOBBY_MENU:
            self._draw_lobby_menu()
        elif self.online_state == OnlineCoopState.WAITING:
            self._draw_waiting_screen()
        elif self.online_state == OnlineCoopState.READY_CHECK:
            self._draw_ready_check()
        elif self.online_state == OnlineCoopState.COUNTDOWN:
            self._draw_countdown()
        elif self.online_state == OnlineCoopState.PLAYING:
            self._draw_playing_placeholder()
        elif self.online_state == OnlineCoopState.GAME_OVER:
            self._draw_game_over()
        elif self.online_state == OnlineCoopState.DISCONNECTED:
            self._draw_disconnected()

        # NOT: pygame.display.flip() burada çağrılmıyor.
        # Ana döngü, Online PvP ile aynı sırada geçiş perdesini çizip flip yapıyor.

    # ============================================================
    #  DRAW: Online Shell Ekranları (PvP'den adapte)
    # ============================================================

    def _draw_lobby_menu(self):
        """Online PvP lobby ekranıyla aynı görsel dilde Co-op ana menüsü."""
        w, h = self.window_width, self.window_height
        cx = w // 2
        sc = self._ui_scale()
        s = lambda v, minimum=1: self._sx(v, sc, minimum)

        title_rect = _rs.draw_title(self.screen, t('online_coop_title', 'ONLINE CO-OP'), (cx, s(58)))

        btn_w = s(340)
        btn_h = s(52)
        panel_left = max(s(30), cx - s(400))
        btn_x = panel_left
        btn_y_start = title_rect.bottom + s(28)
        gap = s(12)

        section_font = _rs.get_font(s(13, minimum=10), bold=False)
        private_section = section_font.render(
            t('private_lobby_section', '── Özel Lobi ──'),
            True,
            _rs.text_muted,
        )
        self.screen.blit(
            private_section,
            private_section.get_rect(center=(btn_x + btn_w // 2, btn_y_start - s(8))),
        )

        buttons_private = [
            ('create_private', t('create_private_coop', 'Özel Co-op Lobisi'), _rs.primary, '1 / ENTER'),
            ('join_by_code', t('join_by_code', 'Kod ile Katıl'), UIColors.NEON_CYAN, 'J'),
            ('invite_friend', t('invite_friend_coop', 'Arkadaş Davet Et'), UIColors.NEON_GREEN, 'I'),
        ]

        mouse_pos = get_mouse_pos()
        y_pos = btn_y_start + s(8)
        for action, label, color, shortcut in buttons_private:
            rect = pygame.Rect(btn_x, y_pos, btn_w, btn_h)
            hover = rect.collidepoint(mouse_pos)
            _rs.draw_uniform_button(
                self.screen,
                rect,
                label,
                sub_text=shortcut,
                color_code=color,
                state='hover' if hover else 'normal',
            )
            self._lobby_buttons.append({'rect': rect, 'action': action})
            y_pos += btn_h + gap

        if self._join_code_active:
            self._draw_join_code_input(btn_x, y_pos, btn_w, s, mouse_pos)
            y_pos += s(236)

        y_pos += s(10)
        public_section = section_font.render(
            t('public_lobby_section', '── Herkese Açık ──'),
            True,
            _rs.text_muted,
        )
        self.screen.blit(public_section, public_section.get_rect(center=(btn_x + btn_w // 2, y_pos)))
        y_pos += s(18)

        pub_create_rect = pygame.Rect(btn_x, y_pos, btn_w, btn_h)
        pub_create_hover = pub_create_rect.collidepoint(mouse_pos)
        _rs.draw_uniform_button(
            self.screen,
            pub_create_rect,
            t('create_public_coop', 'Herkese Açık Lobi'),
            sub_text='2',
            color_code=_rs.success,
            state='hover' if pub_create_hover else 'normal',
        )
        self._lobby_buttons.append({'rect': pub_create_rect, 'action': 'create_public'})
        y_pos += btn_h + gap

        find_rect = pygame.Rect(btn_x, y_pos, btn_w, btn_h)
        find_hover = find_rect.collidepoint(mouse_pos)
        _rs.draw_uniform_button(
            self.screen,
            find_rect,
            t('find_match', 'Maç Bul'),
            sub_text='3',
            color_code=UIColors.NEON_CYAN,
            state='hover' if find_hover else 'normal',
        )
        self._lobby_buttons.append({'rect': find_rect, 'action': 'find_match'})
        y_pos += btn_h + gap

        y_pos += s(10)
        back_rect = pygame.Rect(btn_x, y_pos, btn_w, s(44))
        _rs.draw_uniform_button(
            self.screen,
            back_rect,
            t('back_to_menu', 'Ana Menüye Dön'),
            sub_text='ESC',
            color_code=_rs.secondary,
            state='hover' if back_rect.collidepoint(mouse_pos) else 'normal',
        )
        self._lobby_buttons.append({'rect': back_rect, 'action': 'back'})

        list_x = btn_x + btn_w + s(30)
        list_w = max(s(280), min(s(420), w - list_x - s(30)))
        list_y = btn_y_start
        list_h = h - list_y - s(60)
        list_panel = pygame.Rect(list_x, list_y, list_w, list_h)
        draw_glass_panel(
            self.screen,
            list_panel,
            alpha=165,
            border_color=(80, 120, 180),
            glow=True,
        )

        title_font = _rs.get_font(s(20, minimum=14))
        list_title = title_font.render(
            t('coop_lobby_list_title', 'Mevcut Co-op Lobileri'),
            True,
            _rs.accent,
        )
        list_title_rect = list_title.get_rect(center=(list_x + list_w // 2, list_y + s(24)))
        self.screen.blit(list_title, list_title_rect)

        sub_font = _rs.get_font(s(12, minimum=9), bold=False)
        subtitle_text = (
            t('lobby_list_subtitle_public', 'Sadece açık lobiler')
            if self._lobby_list_filter == 'public'
            else t('lobby_list_subtitle_all', 'Özel ve açık lobiler')
        )
        subtitle = sub_font.render(subtitle_text, True, _rs.text_muted)
        subtitle_rect = subtitle.get_rect(
            center=(list_x + list_w // 2, list_title_rect.bottom + s(12)),
        )
        self.screen.blit(subtitle, subtitle_rect)

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
        all_active = self._lobby_list_filter == 'all'
        public_active = self._lobby_list_filter == 'public'
        _rs.draw_uniform_button(
            self.screen,
            all_rect,
            t('all_lobbies', 'Bütün Lobiler'),
            color_code=UIColors.NEON_CYAN if all_active else _rs.secondary,
            state='hover' if all_active or all_rect.collidepoint(mouse_pos) else 'normal',
        )
        _rs.draw_uniform_button(
            self.screen,
            public_rect,
            t('public_lobbies', 'Açık Lobiler'),
            color_code=UIColors.NEON_GREEN if public_active else _rs.secondary,
            state='hover' if public_active or public_rect.collidepoint(mouse_pos) else 'normal',
        )
        self._lobby_buttons.append({'rect': all_rect, 'action': 'filter_all_lobbies'})
        self._lobby_buttons.append({'rect': public_rect, 'action': 'filter_public_lobbies'})

        entries = self._get_lobby_entries_for_display()
        count_font = _rs.get_font(s(12, minimum=9), bold=False)
        count_text = count_font.render(str(len(entries)), True, _rs.text_primary)
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

        header_bottom = max(subtitle_rect.bottom, count_rect.bottom, all_rect.bottom, public_rect.bottom)
        line_y = header_bottom + s(12)
        pygame.draw.line(
            self.screen,
            (*_rs.accent[:3], 60),
            (list_x + s(12), line_y),
            (list_x + list_w - s(12), line_y),
            1,
        )
        content_top = line_y + s(14)

        if self._lobby_list_fetching and not entries:
            dots = '.' * (int(time.time() * 2) % 4)
            fetching = _rs.get_font(s(16, minimum=11), bold=False).render(
                t('searching', 'Aranıyor') + dots,
                True,
                _rs.text_secondary,
            )
            self.screen.blit(fetching, fetching.get_rect(center=(list_x + list_w // 2, list_y + list_h // 2)))
        elif not entries:
            empty_font = _rs.get_font(s(16, minimum=11), bold=False)
            empty_title = empty_font.render(
                t('no_coop_lobbies', 'Henüz aktif co-op lobisi yok'),
                True,
                _rs.text_muted,
            )
            if self._auto_lobby_refresh_requested:
                self.screen.blit(empty_title, empty_title.get_rect(center=(list_x + list_w // 2, list_y + list_h // 2)))
            else:
                empty_hint = _rs.get_font(s(14, minimum=10), bold=False).render(
                    t('press_find_match', '"Maç Bul" ile arayın'),
                    True,
                    _rs.text_muted,
                )
                self.screen.blit(empty_title, empty_title.get_rect(center=(list_x + list_w // 2, list_y + list_h // 2 - s(10))))
                self.screen.blit(empty_hint, empty_hint.get_rect(center=(list_x + list_w // 2, list_y + list_h // 2 + s(14))))
        else:
            item_step = s(104)
            item_h = item_step - s(12)
            content_h = max(item_step, list_panel.bottom - content_top - s(22))
            visible = max(1, content_h // item_step)
            max_start = max(0, len(entries) - visible)
            start_idx = min(self._lobby_list_scroll, max_start)
            if start_idx != self._lobby_list_scroll:
                self._lobby_list_scroll = start_idx

            clip = pygame.Rect(list_x + 4, content_top, list_w - 8, content_h)
            self.screen.set_clip(clip)

            for i, lobby in enumerate(entries[start_idx:start_idx + visible]):
                iy = content_top + i * item_step
                item_rect = pygame.Rect(list_x + s(8), iy, list_w - s(16), item_h)
                hover = item_rect.collidepoint(mouse_pos)
                raw_requires_code = bool(lobby.get('requires_code', False))
                lobby_code = str((lobby.get('code') or lobby.get('lobby_code') or '')).strip()
                raw_visibility = str(lobby.get('visibility', 'unknown') or 'unknown').lower()
                visibility, requires_code = _resolve_lobby_display_state(
                    raw_visibility,
                    raw_requires_code,
                    lobby_code,
                )
                if visibility in ('unknown', 'stale_unknown'):
                    accent_color = UIColors.NEON_ORANGE
                else:
                    accent_color = UIColors.NEON_ORANGE if requires_code else UIColors.NEON_GREEN

                draw_glass_panel(
                    self.screen,
                    item_rect,
                    alpha=205 if hover else 150,
                    border_color=accent_color,
                    glow=hover,
                )
                accent_bar = pygame.Rect(item_rect.x + s(6), item_rect.y + s(8), s(5), item_rect.height - s(16))
                pygame.draw.rect(self.screen, accent_color, accent_bar, border_radius=999)

                if hover:
                    hover_overlay = pygame.Surface((item_rect.width, item_rect.height), pygame.SRCALPHA)
                    pygame.draw.rect(hover_overlay, (*accent_color[:3], 20), hover_overlay.get_rect(), border_radius=12)
                    self.screen.blit(hover_overlay, item_rect.topleft)

                lobby_name = str(
                    lobby.get('host_name')
                    or lobby.get('name')
                    or f"Co-op Lobi #{i + start_idx + 1}"
                )
                members = lobby.get('members', '?')
                max_members = lobby.get('max_members', 2)
                lobby_id = lobby.get('id') or lobby.get('lobby_id') or 0
                try:
                    member_ratio = min(1.0, max(0.0, float(members) / max(1.0, float(max_members))))
                except Exception:
                    member_ratio = 0.0

                name_font = _rs.get_font(s(17, minimum=12))
                self.screen.blit(
                    name_font.render(lobby_name, True, _rs.text_primary),
                    (item_rect.x + s(20), item_rect.y + s(10)),
                )

                badge_font = _rs.get_font(s(11, minimum=9), bold=False)
                badge_icon = None
                if visibility in ('unknown', 'stale_unknown'):
                    badge_text = t('lobby_label', 'Lobi')
                elif requires_code:
                    from emoji_renderer import emoji_surface

                    badge_text = t('private_lobby', 'Özel Lobi')
                    badge_icon = emoji_surface('🔒', max(10, s(13, minimum=10)))
                else:
                    from emoji_renderer import emoji_surface

                    badge_text = t('open_lobby', 'Açık lobi')
                    badge_icon = emoji_surface('🔓', max(10, s(13, minimum=10)))

                badge_text_surf = badge_font.render(badge_text, True, accent_color)
                badge_gap = s(6) if badge_icon else 0
                badge_content_w = (
                    badge_text_surf.get_width()
                    + (badge_icon.get_width() if badge_icon else 0)
                    + badge_gap
                )
                badge_rect = pygame.Rect(
                    item_rect.right - badge_content_w - s(30),
                    item_rect.y + s(8),
                    badge_content_w + s(16),
                    badge_text_surf.get_height() + s(8),
                )
                badge_surface = pygame.Surface((badge_rect.width, badge_rect.height), pygame.SRCALPHA)
                pygame.draw.rect(badge_surface, (*accent_color[:3], 40), badge_surface.get_rect(), border_radius=999)
                pygame.draw.rect(badge_surface, (*accent_color[:3], 130), badge_surface.get_rect(), 1, border_radius=999)
                self.screen.blit(badge_surface, badge_rect.topleft)
                if badge_icon:
                    icon_rect = badge_icon.get_rect()
                    icon_rect.x = badge_rect.x + s(8)
                    icon_rect.centery = badge_rect.centery
                    self.screen.blit(badge_icon, icon_rect)
                    text_rect = badge_text_surf.get_rect(midleft=(icon_rect.right + badge_gap, badge_rect.centery))
                else:
                    text_rect = badge_text_surf.get_rect(center=badge_rect.center)
                self.screen.blit(badge_text_surf, text_rect)

                detail_font = _rs.get_font(s(12, minimum=9), bold=False)
                detail_parts = [f"{members}/{max_members} {t('players_count_suffix', 'oyuncu')}"]
                if requires_code:
                    detail_parts.append(t('code_required', 'Katılmak için kod gerekli'))
                elif visibility == 'public':
                    detail_parts.append(t('open_lobby', 'Açık lobi'))
                elif visibility in ('unknown', 'stale_unknown'):
                    detail_parts.append(t('lobby_syncing', 'Lobi bilgisi kontrol ediliyor'))
                detail_text = '  ·  '.join(detail_parts)
                self.screen.blit(
                    detail_font.render(detail_text, True, _rs.text_secondary),
                    (item_rect.x + s(20), item_rect.y + s(34)),
                )

                found_time = lobby.get('found_time', 0)
                if found_time:
                    elapsed = int(time.time() - found_time)
                    time_text = t('just_now', 'Az önce') if elapsed < 60 else f'{elapsed // 60} dk önce'
                    time_font = _rs.get_font(s(11, minimum=9), bold=False)
                    self.screen.blit(
                        time_font.render(time_text, True, _rs.text_muted),
                        (item_rect.x + s(20), item_rect.y + s(57)),
                    )

                join_w, join_h = s(92), s(34)
                join_rect = pygame.Rect(item_rect.right - join_w - s(12), item_rect.centery - join_h // 2, join_w, join_h)
                join_hover = join_rect.collidepoint(mouse_pos)
                action = ''
                if visibility in ('unknown', 'stale_unknown'):
                    action = f'resolve_lobby_join:{lobby_id}'
                    button_label = t('join', 'Katıl')
                    button_color = UIColors.NEON_CYAN
                else:
                    action = f'join_private_lobby:{lobby_id}' if requires_code else f'join_lobby:{lobby_id}'
                    button_label = t('enter_code', 'Kod Gir') if requires_code else t('join', 'Katıl')
                    button_color = UIColors.NEON_ORANGE if requires_code else UIColors.NEON_GREEN

                _rs.draw_uniform_button(
                    self.screen,
                    join_rect,
                    button_label,
                    color_code=button_color,
                    state='hover' if join_hover else 'normal',
                )
                if requires_code and action:
                    self._lobby_buttons.append({'rect': item_rect, 'action': action})
                if action:
                    self._lobby_buttons.append({'rect': join_rect, 'action': action})

                bar_rect = pygame.Rect(
                    item_rect.x + s(102),
                    item_rect.y + s(59),
                    max(s(72), join_rect.x - item_rect.x - s(132)),
                    s(8),
                )
                pygame.draw.rect(self.screen, (35, 48, 76), bar_rect, border_radius=999)
                fill_rect = pygame.Rect(
                    bar_rect.x,
                    bar_rect.y,
                    max(1, int(bar_rect.width * member_ratio)),
                    bar_rect.height,
                )
                pygame.draw.rect(self.screen, accent_color, fill_rect, border_radius=999)
                occupancy = detail_font.render(f'{members}/{max_members}', True, _rs.text_secondary)
                self.screen.blit(occupancy, occupancy.get_rect(midleft=(bar_rect.right + s(8), bar_rect.centery)))

            self.screen.set_clip(None)

            if len(entries) > visible:
                scroll_font = _rs.get_font(s(12, minimum=9), bold=False)
                scroll_text = scroll_font.render(
                    f'{start_idx + 1}–{min(start_idx + visible, len(entries))} / {len(entries)}',
                    True,
                    _rs.text_muted,
                )
                self.screen.blit(
                    scroll_text,
                    scroll_text.get_rect(center=(list_x + list_w // 2, list_y + list_h - s(16))),
                )

        if self._status_msg:
            status_font = _rs.get_font(s(16, minimum=11), bold=False)
            status = status_font.render(self._status_msg, True, UIColors.NEON_MAGENTA)
            self.screen.blit(status, status.get_rect(center=(cx, h - s(52))))

        info_font = _rs.get_font(s(13, minimum=10), bold=False)
        sid = getattr(self.net, 'my_steam_id', 0) or t('connecting', 'Bağlanılıyor...')
        info = info_font.render(f'Steam ID: {sid}', True, _rs.text_muted)
        self.screen.blit(info, info.get_rect(center=(cx, h - s(24))))

    def _draw_join_code_input(self, x, y, btn_w, s, mouse_pos):
        """Kod ile katıl panelini Online PvP ile aynı slotlu formda çiz."""
        panel_h = s(224)
        panel_rect = pygame.Rect(x, y, btn_w, panel_h)
        panel_border = UIColors.NEON_RED if self._join_code_error else UIColors.NEON_CYAN
        draw_glass_panel(self.screen, panel_rect, alpha=195, border_color=panel_border, glow=True)

        title_font = _rs.get_font(s(18, minimum=12))
        title = title_font.render(t('join_by_code', 'Kod ile Katıl'), True, UIColors.NEON_CYAN)
        self.screen.blit(title, title.get_rect(midleft=(x + s(16), y + s(20))))

        subtitle_font = _rs.get_font(s(12, minimum=9), bold=False)
        subtitle = subtitle_font.render(
            t('join_code_subtitle', 'Özel lobiye girmek için 6 haneli kodu yaz'),
            True,
            _rs.text_muted,
        )
        self.screen.blit(subtitle, subtitle.get_rect(midleft=(x + s(16), y + s(41))))

        hint_font = _rs.get_font(s(11, minimum=9), bold=False)
        hint = hint_font.render(
            t('paste_code_hint', 'Yapıştır: Ctrl+V  •  Kapat: ESC'),
            True,
            _rs.text_muted,
        )
        self.screen.blit(hint, hint.get_rect(midright=(x + btn_w - s(16), y + s(20))))

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
            slot_border = UIColors.NEON_RED if self._join_code_error else (
                UIColors.NEON_CYAN if is_active_slot else (*_rs.glass_border[:3],)
            )
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
                dot_surf = dot_font.render('•', True, _rs.text_muted)
                self.screen.blit(dot_surf, dot_surf.get_rect(center=slot_rect.center))

        if self._join_code_active and int(time.time() * 2.5) % 2 == 0 and len(display_text) < slot_count:
            cursor_slot_x = slots_x + len(display_text) * (slot_w + slot_gap)
            cursor_center_x = cursor_slot_x + slot_w // 2
            pygame.draw.line(
                self.screen,
                UIColors.NEON_CYAN,
                (cursor_center_x, slots_y + s(12)),
                (cursor_center_x, slots_y + slot_h - s(12)),
                2,
            )

        self._lobby_buttons.append({'rect': slots_rect, 'action': 'join_code_field'})

        helper_font = _rs.get_font(s(11, minimum=9), bold=False)
        helper_text = helper_font.render(
            t('join_code_helper', 'Her kutuya bir rakam gelecek şekilde 6 haneli kod gir'),
            True,
            _rs.text_secondary,
        )
        self.screen.blit(helper_text, helper_text.get_rect(center=(x + btn_w // 2, slots_y + slot_h + s(14))))

        if self._join_code_error:
            error_font = _rs.get_font(s(12, minimum=9), bold=False)
            error = error_font.render(self._join_code_error, True, UIColors.NEON_RED)
            self.screen.blit(error, error.get_rect(center=(x + btn_w // 2, slots_y + slot_h + s(34))))

        submit_w = btn_w - s(32)
        submit_h = s(38)
        submit_y = y + panel_h - submit_h - s(16)
        submit_rect = pygame.Rect(x + s(16), submit_y, submit_w, submit_h)
        _rs.draw_uniform_button(
            self.screen,
            submit_rect,
            t('join_lobby_by_code', 'Kodla Lobiye Katıl'),
            sub_text='ENTER',
            color_code=UIColors.NEON_GREEN,
            state='hover' if submit_rect.collidepoint(mouse_pos) else 'normal',
        )
        self._lobby_buttons.append({'rect': submit_rect, 'action': 'join_code_submit'})
        return panel_h

    def _draw_waiting_screen(self):
        """Takım arkadaşı bekleme ekranı."""
        w, h = self.window_width, self.window_height
        cx, cy = w // 2, h // 2
        sc = self._ui_scale()
        s = lambda v, minimum=1: self._sx(v, sc, minimum)
        mouse_pos = get_mouse_pos()

        pw = min(s(640), w - s(80))
        ph = min(s(510), h - s(100))
        panel = pygame.Rect(cx - pw // 2, cy - ph // 2, pw, ph)
        draw_glass_panel(self.screen, panel, alpha=185,
                        border_color=(80, 230, 160), glow=True)

        tf = get_fitting_font(
            t('waiting_for_teammate', 'Takım Arkadaşı Bekleniyor...'),
            s(30), pw - s(60))
        title = tf.render(
            t('waiting_for_teammate', 'Takım Arkadaşı Bekleniyor...'),
            True, (80, 230, 160))
        self.screen.blit(title, title.get_rect(center=(cx, panel.y + s(40))))

        # Animasyonlu noktalar
        dots = '●' * (int(time.time() * 2) % 4) + '○' * (3 - int(time.time() * 2) % 4)
        df = _rs.get_font(s(20, minimum=14))
        dots_surf = df.render(dots, True, (80, 230, 160))
        self.screen.blit(dots_surf, dots_surf.get_rect(center=(cx, panel.y + s(72))))

        mode_font = _rs.get_font(s(14, minimum=11), bold=True)
        lobby_type = t('public_lobby_badge', 'AÇIK') if not self._lobby_code else t('private_lobby_badge', 'KOD')
        mode_text = lobby_type
        mode_surf = mode_font.render(mode_text, True, UIColors.TEXT_PRIMARY)
        self.screen.blit(mode_surf, mode_surf.get_rect(center=(cx, panel.y + s(105))))

        card = pygame.Rect(panel.x + s(34), panel.y + s(130), panel.width - s(68), s(170))
        draw_glass_panel(self.screen, card, alpha=130, border_color=(80, 230, 160), glow=False)

        if self._lobby_code:
            code_label_font = _rs.get_font(s(14, minimum=11), bold=False)
            code_label = code_label_font.render(
                t('lobby_code_label', 'Lobi Kodu'), True, _rs.text_muted)
            self.screen.blit(code_label, code_label.get_rect(center=(cx, card.y + s(28))))

            code_font = _rs.get_font(s(42, minimum=24), bold=True)
            formatted = self._lobby_code[:3] + ' ' + self._lobby_code[3:] if len(self._lobby_code) >= 6 else self._lobby_code
            code_surf = code_font.render(formatted, True, UIColors.TEXT_PRIMARY)
            self.screen.blit(code_surf, code_surf.get_rect(center=(cx, card.y + s(72))))

            hint_font = _rs.get_font(s(12, minimum=10), bold=False)
            hint = hint_font.render(
                t('share_code_hint', 'Bu kodu arkadaşınla paylaş'),
                True, _rs.text_muted)
            self.screen.blit(hint, hint.get_rect(center=(cx, card.y + s(112))))
        else:
            public_font = _rs.get_font(s(18, minimum=13), bold=True)
            public = public_font.render(t('public_lobby_waiting', 'Herkese açık lobi aktif'), True, (90, 150, 230))
            self.screen.blit(public, public.get_rect(center=(cx, card.y + s(58))))
            hint = _rs.get_font(s(12, minimum=10), bold=False).render(
                t('public_lobby_waiting_hint', 'Arkadaşın liste üzerinden doğrudan katılabilir'),
                True,
                _rs.text_muted,
            )
            self.screen.blit(hint, hint.get_rect(center=(cx, card.y + s(96))))

        button_y = card.bottom + s(20)
        btn_w = min(s(170), (panel.width - s(88)) // 3)
        btn_h = s(44)
        buttons = []
        if self._lobby_code:
            buttons.append((t('copy_lobby_code', 'Kodu Kopyala'), 'copy_lobby_code', 'C', (80, 230, 160)))
        buttons.append((t('invite_friend_coop', 'Davet Et'), 'invite_friend', 'I', UIColors.NEON_CYAN))
        buttons.append((t('copy_lobby_id', 'ID Kopyala'), 'copy_lobby_id', '', _rs.secondary))
        total_w = len(buttons) * btn_w + max(0, len(buttons) - 1) * s(10)
        start_x = cx - total_w // 2
        for idx, (label, action, shortcut, color) in enumerate(buttons):
            rect = pygame.Rect(start_x + idx * (btn_w + s(10)), button_y, btn_w, btn_h)
            _rs.draw_uniform_button(
                self.screen,
                rect,
                label,
                sub_text=shortcut,
                color_code=color,
                state='hover' if rect.collidepoint(mouse_pos) else 'normal',
            )
            self._lobby_buttons.append({'rect': rect, 'action': action})

        back_rect = pygame.Rect(cx - s(110), panel.bottom - s(70), s(220), s(44))
        _rs.draw_uniform_button(
            self.screen, back_rect,
            t('back_to_coop_lobby', 'Co-op Lobiye Dön'),
            sub_text='ESC',
            color_code=_rs.secondary,
            state='hover' if back_rect.collidepoint(mouse_pos) else 'normal',
        )
        self._lobby_buttons.append({'rect': back_rect, 'action': 'back_to_lobby'})

        if self._status_msg:
            status_font = _rs.get_font(s(13, minimum=10), bold=False)
            status = status_font.render(self._status_msg, True, UIColors.TEXT_SECONDARY)
            self.screen.blit(status, status.get_rect(center=(cx, panel.bottom - s(18))))

    def _get_steam_avatar_surface(self, steam_id: int, size: int) -> pygame.Surface | None:
        """Steam profil fotoğrafını pygame Surface olarak al ve önbelleğe."""
        if not hasattr(self, '_avatar_cache'):
            self._avatar_cache: dict[tuple[int, int], pygame.Surface] = {}
        if not hasattr(self, '_avatar_retry_count'):
            self._avatar_retry_count: dict[tuple[int, int], int] = {}

        cache_key = (steam_id, size)
        if cache_key in self._avatar_cache:
            return self._avatar_cache[cache_key]

        retries = self._avatar_retry_count.get(cache_key, 0)
        if retries >= 10:
            return None

        try:
            from steam_integration import get_avatar_rgba

            rgba = get_avatar_rgba(steam_id, preferred='medium')
            if rgba:
                aw, ah, argba = rgba
                source = pygame.image.frombuffer(bytearray(argba), (aw, ah), 'RGBA').convert_alpha()
                scaled = pygame.transform.smoothscale(source, (size, size))
                circle = pygame.Surface((size, size), pygame.SRCALPHA)
                pygame.draw.circle(circle, (255, 255, 255, 255), (size // 2, size // 2), size // 2)
                scaled.blit(circle, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
                self._avatar_cache[cache_key] = scaled
                return scaled
        except Exception:
            pass

        self._avatar_retry_count[cache_key] = retries + 1
        return None

    def _draw_ready_check(self):
        """Online PvP hazır ekranıyla aynı avatar/badge düzeninde onay ekranı."""
        w, h = self.window_width, self.window_height
        cx, cy = w // 2, h // 2
        sc = self._ui_scale()
        s = lambda v, minimum=1: self._sx(v, sc, minimum)

        pw = min(s(650), w - s(80))
        ph = s(420)
        panel = pygame.Rect(cx - pw // 2, cy - ph // 2, pw, ph)
        draw_glass_panel(self.screen, panel, alpha=185,
                         border_color=UIColors.NEON_CYAN, glow=True)

        vs_font = _rs.get_font(s(56, minimum=32))
        vs = vs_font.render('CO-OP', True, UIColors.NEON_MAGENTA)
        for offset in (3, 2, 1):
            glow_surf = pygame.Surface(vs.get_size(), pygame.SRCALPHA)
            glow_surf.fill((*UIColors.NEON_MAGENTA[:3], 20))
            glow_surf.blit(vs, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            self.screen.blit(
                glow_surf,
                glow_surf.get_rect(center=(cx + offset, panel.y + s(45) + offset)),
            )
        self.screen.blit(vs, vs.get_rect(center=(cx, panel.y + s(45))))

        my_name = t('you', 'Sen')
        my_steam_id = 0
        try:
            my_steam_id = int(getattr(self.net, 'my_steam_id', 0) or 0)
            name_reader = getattr(self.net, '_get_name', None)
            if my_steam_id and callable(name_reader):
                my_name = name_reader(my_steam_id) or my_name
        except Exception:
            my_steam_id = 0

        opponent_id = int(getattr(self.net, 'opponent_steam_id', 0) or 0)
        opponent_name = (
            getattr(self.net, 'opponent_name', '')
            or t('teammate', 'Takım Arkadaşı')
        )

        col_w = pw // 2 - s(20)
        my_cx = panel.x + col_w // 2 + s(10)
        opp_cx = panel.right - col_w // 2 - s(10)

        avatar_size = s(64, minimum=40)
        avatar_y = panel.y + s(90)

        my_avatar = self._get_steam_avatar_surface(my_steam_id, avatar_size)
        my_accent = UIColors.NEON_CYAN
        my_border = UIColors.NEON_GREEN if self.my_ready else my_accent
        my_frame = pygame.Rect(
            my_cx - avatar_size // 2 - s(4),
            avatar_y - s(4),
            avatar_size + s(8),
            avatar_size + s(8),
        )
        draw_glass_panel(self.screen, my_frame, alpha=160, border_color=my_border)
        if my_avatar:
            self.screen.blit(my_avatar, (my_cx - avatar_size // 2, avatar_y))
        else:
            pygame.draw.circle(
                self.screen,
                (*my_accent[:3], 80),
                (my_cx, avatar_y + avatar_size // 2),
                avatar_size // 2,
            )
            placeholder_font = _rs.get_font(s(24, minimum=16))
            placeholder = placeholder_font.render('?', True, my_accent)
            self.screen.blit(placeholder, placeholder.get_rect(center=(my_cx, avatar_y + avatar_size // 2)))

        opp_avatar = self._get_steam_avatar_surface(opponent_id, avatar_size)
        opp_accent = UIColors.NEON_MAGENTA
        opp_border = UIColors.NEON_GREEN if self.opponent_ready else opp_accent
        opp_frame = pygame.Rect(
            opp_cx - avatar_size // 2 - s(4),
            avatar_y - s(4),
            avatar_size + s(8),
            avatar_size + s(8),
        )
        draw_glass_panel(self.screen, opp_frame, alpha=160, border_color=opp_border)
        if opp_avatar:
            self.screen.blit(opp_avatar, (opp_cx - avatar_size // 2, avatar_y))
        else:
            pygame.draw.circle(
                self.screen,
                (*opp_accent[:3], 80),
                (opp_cx, avatar_y + avatar_size // 2),
                avatar_size // 2,
            )
            placeholder_font = _rs.get_font(s(24, minimum=16))
            placeholder = placeholder_font.render('?', True, opp_accent)
            self.screen.blit(placeholder, placeholder.get_rect(center=(opp_cx, avatar_y + avatar_size // 2)))

        name_y = avatar_y + avatar_size + s(14)
        name_font = _rs.get_font(s(20, minimum=14))
        my_color = UIColors.NEON_GREEN if self.my_ready else _rs.text_primary
        opp_color = UIColors.NEON_GREEN if self.opponent_ready else _rs.text_primary
        my_name_surface = name_font.render(my_name, True, my_color)
        opp_name_surface = name_font.render(opponent_name, True, opp_color)
        self.screen.blit(my_name_surface, my_name_surface.get_rect(center=(my_cx, name_y)))
        self.screen.blit(opp_name_surface, opp_name_surface.get_rect(center=(opp_cx, name_y)))

        role_font = _rs.get_font(s(12, minimum=9), bold=False)
        my_role = t('host_role', 'Host') if self.role == 'host' else t('guest_role', 'Guest')
        opp_role = t('guest_role', 'Guest') if self.role == 'host' else t('host_role', 'Host')
        my_role_surface = role_font.render(my_role, True, _rs.text_muted)
        opp_role_surface = role_font.render(opp_role, True, _rs.text_muted)
        self.screen.blit(my_role_surface, my_role_surface.get_rect(center=(my_cx, name_y + s(22))))
        self.screen.blit(opp_role_surface, opp_role_surface.get_rect(center=(opp_cx, name_y + s(22))))

        status_y = name_y + s(42)
        status_font = _rs.get_font(s(14, minimum=10), bold=False)
        if self.my_ready:
            ready_badge = pygame.Rect(my_cx - s(50), status_y, s(100), s(24))
            draw_glass_panel(self.screen, ready_badge, alpha=180, border_color=UIColors.NEON_GREEN)
            ready_text = status_font.render(t('campaign_status_ready', 'READY'), True, UIColors.NEON_GREEN)
            self.screen.blit(ready_text, ready_text.get_rect(center=ready_badge.center))
        else:
            waiting_text = status_font.render(t('not_ready', 'Bekleniyor...'), True, _rs.text_muted)
            self.screen.blit(waiting_text, waiting_text.get_rect(center=(my_cx, status_y + s(12))))

        if self.opponent_ready:
            ready_badge = pygame.Rect(opp_cx - s(50), status_y, s(100), s(24))
            draw_glass_panel(self.screen, ready_badge, alpha=180, border_color=UIColors.NEON_GREEN)
            ready_text = status_font.render(t('campaign_status_ready', 'READY'), True, UIColors.NEON_GREEN)
            self.screen.blit(ready_text, ready_text.get_rect(center=ready_badge.center))
        else:
            waiting_text = status_font.render(t('not_ready', 'Bekleniyor...'), True, _rs.text_muted)
            self.screen.blit(waiting_text, waiting_text.get_rect(center=(opp_cx, status_y + s(12))))

        pygame.draw.line(
            self.screen,
            (*UIColors.NEON_MAGENTA[:3], 60),
            (cx, panel.y + s(80)),
            (cx, status_y + s(30)),
            2,
        )

        if not self.my_ready:
            ready_rect = pygame.Rect(cx - s(130), panel.y + s(290), s(260), s(50))
            ready_hover = ready_rect.collidepoint(get_mouse_pos())
            _rs.draw_uniform_button(
                self.screen,
                ready_rect,
                t('press_enter_ready', 'Hazırım!'),
                sub_text='ENTER',
                color_code=UIColors.NEON_GREEN,
                state='hover' if ready_hover else 'normal',
            )
            self._lobby_buttons.append({'rect': ready_rect, 'action': 'ready'})
        else:
            waiting_rect = pygame.Rect(cx - s(112), panel.y + s(295), s(224), s(36))
            draw_glass_panel(self.screen, waiting_rect, alpha=150, border_color=UIColors.NEON_GREEN)
            wait_font = _rs.get_font(s(16, minimum=12), bold=False)
            wait_text = wait_font.render(
                t('waiting_for_teammate', 'Takım arkadaşı bekleniyor...'),
                True,
                UIColors.NEON_GREEN,
            )
            self.screen.blit(wait_text, wait_text.get_rect(center=waiting_rect.center))

        back_w = s(220)
        back_h = s(36)
        back_rect = pygame.Rect(cx - back_w // 2, panel.bottom - s(48), back_w, back_h)
        back_hover = back_rect.collidepoint(get_mouse_pos())
        _rs.draw_uniform_button(
            self.screen,
            back_rect,
            t('back_to_coop_lobby', 'Co-op Lobiye Dön'),
            sub_text='ESC',
            color_code=_rs.secondary,
            state='hover' if back_hover else 'normal',
        )
        self._lobby_buttons.append({'rect': back_rect, 'action': 'back_to_lobby'})

    def _draw_countdown(self):
        """3-2-1 geri sayım."""
        w, h = self.window_width, self.window_height
        cx, cy = w // 2, h // 2
        sc = self._ui_scale()
        s = lambda v, minimum=1: self._sx(v, sc, minimum)

        r = s(100)
        bg = pygame.Rect(cx - r, cy - r, r * 2, r * 2)
        draw_glass_panel(self.screen, bg, alpha=150,
                        border_color=(80, 230, 160), glow=True)

        if self.countdown_value > 0:
            big_font = _rs.get_font(s(100, minimum=48))
            txt = big_font.render(str(self.countdown_value), True, (80, 230, 160))
        else:
            big_font = _rs.get_font(s(72, minimum=36))
            txt = big_font.render('GO!', True, UIColors.NEON_GREEN)

        self.screen.blit(txt, txt.get_rect(center=(cx, cy)))

    def _draw_playing_placeholder(self):
        """Oyun render: host=CoopGame render, guest=state cache'den render."""
        if self.role == 'host' and self.coop_game:
            # Host: CoopGame'in render fonksiyonunu doğrudan çağır (flip yapmaz)
            # draw() yerine _render_game() kullanıyoruz çünkü:
            # - draw() kendi pygame.display.flip() çağırır
            # - draw() → _render_game() paused ise CoopGame'in kendi pause menüsünü çizer
            #   (Resume/Settings/Main Menu gibi online'da çalışmayan butonlar)
            self.coop_game._render_game()
            self.coop_game._draw_opening_curtain()
            # Online pause overlay (CoopGame'in pause menüsü yerine basit overlay)
            if self.paused:
                self._draw_online_pause_overlay()
            return
        elif self.role == 'guest':
            self._draw_guest_view()
            # Guest pause overlay
            if self.paused:
                self._draw_online_pause_overlay()
            return

        # Fallback placeholder
        w, h = self.window_width, self.window_height
        cx, cy = w // 2, h // 2
        sc = self._ui_scale()
        s = lambda v, minimum=1: self._sx(v, sc, minimum)

        panel = pygame.Rect(cx - s(200), cy - s(60), s(400), s(120))
        draw_glass_panel(self.screen, panel, alpha=180,
                        border_color=(80, 230, 160))

        font = _rs.get_font(s(24, minimum=16), bold=True)
        role_text = f"Online Co-op — {self.role.upper()}"
        surf = font.render(role_text, True, (80, 230, 160))
        self.screen.blit(surf, surf.get_rect(center=(cx, cy - s(10))))

    def _draw_guest_view(self):
        """Guest tarafında host'tan gelen state cache ile görsel render."""
        w, h = self.window_width, self.window_height
        cx, cy = w // 2, h // 2
        sc = self._ui_scale()
        s = lambda v, minimum=1: self._sx(v, sc, minimum)

        board_data = self._guest_board_cache
        piece_data = self._guest_piece_cache

        if not board_data:
            # Henüz state gelmedi
            font = _rs.get_font(s(18, minimum=12))
            text = font.render(t('waiting_for_host', 'Host verisi bekleniyor...'), True, _rs.text_muted)
            self.screen.blit(text, text.get_rect(center=(cx, cy)))
            return

        render_game = self._apply_guest_render_cache()
        if render_game is not None:
            render_game._render_game()
            render_game._draw_opening_curtain()
            return

        # Board boyutları
        board_w = 20
        board_h = 20
        cell_size = min(s(24), (h - s(120)) // board_h, (w - s(200)) // board_w)
        board_pixel_w = board_w * cell_size
        board_pixel_h = board_h * cell_size
        board_x = cx - board_pixel_w // 2
        board_y = cy - board_pixel_h // 2 + s(20)

        # Board arka planı
        board_rect = pygame.Rect(board_x - 2, board_y - 2, board_pixel_w + 4, board_pixel_h + 4)
        draw_glass_panel(self.screen, board_rect, alpha=160, border_color=(60, 60, 70))

        # Grid çizimi
        grid = board_data.get('grid', [])
        occupancy = board_data.get('_occupancy', [])
        for row_idx in range(min(board_h, len(grid))):
            row = grid[row_idx]
            for col_idx in range(min(board_w, len(row))):
                cell = row[col_idx]
                px = board_x + col_idx * cell_size
                py = board_y + row_idx * cell_size
                filled = (
                    isinstance(occupancy, list)
                    and row_idx < len(occupancy)
                    and isinstance(occupancy[row_idx], list)
                    and col_idx < len(occupancy[row_idx])
                    and bool(occupancy[row_idx][col_idx])
                )
                if filled:
                    color = tuple(cell) if isinstance(cell, (list, tuple)) else (128, 128, 128)
                    pygame.draw.rect(self.screen, color,
                                   (px + 1, py + 1, cell_size - 2, cell_size - 2))
                else:
                    pygame.draw.rect(self.screen, (20, 20, 30),
                                   (px, py, cell_size, cell_size), 1)

        # Orta duvar çizgisi (column 10)
        mid_x = board_x + 10 * cell_size
        pygame.draw.line(self.screen, (80, 80, 100),
                        (mid_x, board_y), (mid_x, board_y + board_pixel_h), 2)

        # Aktif parçalar
        if piece_data:
            for pkey in ('p1_current', 'p2_current'):
                pd = piece_data.get(pkey)
                if pd:
                    self._draw_guest_piece(pd, board_x, board_y, cell_size)

            # Ghost parçalar
            for pkey, ghost_key in [('p1_current', 'p1_ghost_y'), ('p2_current', 'p2_ghost_y')]:
                pd = piece_data.get(pkey)
                gy = piece_data.get(ghost_key, -1)
                if pd and gy >= 0:
                    ghost_pd = dict(pd)
                    ghost_pd['y'] = gy
                    self._draw_guest_piece(ghost_pd, board_x, board_y, cell_size, alpha=60)

        # HUD: skor / seviye / satır
        score = board_data.get('team_score', 0)
        level = board_data.get('level', 1)
        lines = board_data.get('total_lines', 0)
        p1_frozen = board_data.get('p1_frozen', False)
        p2_frozen = board_data.get('p2_frozen', False)

        hud_font = _rs.get_font(s(14, minimum=11), bold=True)
        hud_y = board_y - s(35)
        score_text = hud_font.render(f"Score: {score}  Level: {level}  Lines: {lines}", True, UIColors.TEXT_PRIMARY)
        self.screen.blit(score_text, score_text.get_rect(center=(cx, hud_y)))

        if p1_frozen or p2_frozen:
            freeze_font = _rs.get_font(s(12, minimum=10))
            freeze_parts = []
            if p1_frozen:
                freeze_parts.append('P1 FROZEN')
            if p2_frozen:
                freeze_parts.append('P2 FROZEN')
            freeze_text = freeze_font.render(' | '.join(freeze_parts), True, UIColors.NEON_RED)
            self.screen.blit(freeze_text, freeze_text.get_rect(center=(cx, hud_y + s(18))))

    def _draw_guest_piece(self, piece_data: dict, board_x: int, board_y: int,
                         cell_size: int, alpha: int = 255):
        """Guest view: parça çiz (piece_data = {x, y, si, r})."""
        si = piece_data.get('si', 0)
        if si < 0 or si >= len(_SHAPES):
            return
        x = piece_data.get('x', 0)
        y = piece_data.get('y', 0)
        r = piece_data.get('r', 0)

        shape = _SHAPES[si]
        # Rotation uygula (basit: rotation_state kadar 90° döndür)
        rotated = shape
        for _ in range(r % 4):
            rotated = list(zip(*rotated[::-1]))

        # Renk — constants.py'dan gerçek renk paleti
        color = _PIECE_COLORS[si % len(_PIECE_COLORS)]

        for ry, row in enumerate(rotated):
            for rx, cell in enumerate(row):
                if cell:
                    px = board_x + (x + rx) * cell_size
                    py = board_y + (y + ry) * cell_size
                    if alpha < 255:
                        s = pygame.Surface((cell_size - 2, cell_size - 2), pygame.SRCALPHA)
                        s.fill((*color, alpha))
                        self.screen.blit(s, (px + 1, py + 1))
                    else:
                        pygame.draw.rect(self.screen, color,
                                       (px + 1, py + 1, cell_size - 2, cell_size - 2))

    def _draw_game_over(self):
        """Game over ekranı: skor + rematch butonu."""
        w, h = self.window_width, self.window_height
        cx, cy = w // 2, h // 2
        sc = self._ui_scale()
        s = lambda v, minimum=1: self._sx(v, sc, minimum)

        overlay = pygame.Surface((w, h), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 185))
        self.screen.blit(overlay, (0, 0))

        pw = min(s(480), w - s(80))
        ph = s(320)
        panel = pygame.Rect(cx - pw // 2, cy - ph // 2, pw, ph)
        draw_glass_panel(self.screen, panel, alpha=200,
                        border_color=UIColors.NEON_RED, glow=True)

        # Başlık
        font = _rs.get_font(s(36, minimum=24), bold=True)
        text = font.render(t('game_over', 'OYUN BİTTİ'), True, UIColors.NEON_RED)
        self.screen.blit(text, text.get_rect(center=(cx, panel.y + s(40))))

        # Skor bilgisi
        score = 0
        lines = 0
        if self.role == 'host' and self.coop_game:
            score = self.coop_game.team_score
            lines = self.coop_game.total_lines_cleared
        elif self.role == 'guest':
            score = self._guest_score_cache.get('team_score', 0)
            lines = self._guest_score_cache.get('total_lines', 0)

        score_font = _rs.get_font(s(20, minimum=14), bold=True)
        score_text = score_font.render(f"Score: {score}  Lines: {lines}", True, UIColors.TEXT_PRIMARY)
        self.screen.blit(score_text, score_text.get_rect(center=(cx, panel.y + s(90))))

        # Rematch durumu
        status_font = _rs.get_font(s(14, minimum=11))
        if self._my_rematch and not self._opponent_rematch:
            status = status_font.render(
                t('waiting_rematch', 'Takım arkadaşı bekleniyor...'),
                True, _rs.text_muted)
            self.screen.blit(status, status.get_rect(center=(cx, panel.y + s(130))))
        elif self._opponent_rematch and not self._my_rematch:
            status = status_font.render(
                t('opponent_wants_rematch', 'Takım arkadaşı tekrar oynamak istiyor!'),
                True, (80, 230, 160))
            self.screen.blit(status, status.get_rect(center=(cx, panel.y + s(130))))

        # Butonlar
        mouse_pos = pygame.mouse.get_pos()
        btn_y = panel.y + s(160)

        rematch_rect = pygame.Rect(cx - s(100), btn_y, s(200), s(44))
        rematch_label = t('rematch', 'Tekrar Oyna') if not self._my_rematch else t('rematch_waiting', 'Bekleniyor...')
        _rs.draw_uniform_button(
            self.screen, rematch_rect, rematch_label,
            color_code=_rs.accent if not self._my_rematch else _rs.secondary,
            state='hover' if rematch_rect.collidepoint(mouse_pos) and not self._my_rematch else 'normal',
        )
        if not self._my_rematch:
            self._lobby_buttons.append({'rect': rematch_rect, 'action': 'rematch'})

        menu_rect = pygame.Rect(cx - s(90), btn_y + s(56), s(180), s(42))
        _rs.draw_uniform_button(
            self.screen, menu_rect,
            t('back_to_menu', 'Ana Menü'),
            sub_text='ESC', color_code=_rs.secondary,
            state='hover' if menu_rect.collidepoint(mouse_pos) else 'normal')
        self._lobby_buttons.append({'rect': menu_rect, 'action': 'back_to_lobby'})

    def _draw_disconnected(self):
        """Bağlantı koptu ekranı."""
        w, h = self.window_width, self.window_height
        cx, cy = w // 2, h // 2
        sc = self._ui_scale()
        s = lambda v, minimum=1: self._sx(v, sc, minimum)

        pw = min(s(440), w - s(80))
        ph = s(180)
        panel = pygame.Rect(cx - pw // 2, cy - ph // 2, pw, ph)
        draw_glass_panel(self.screen, panel, alpha=200,
                        border_color=UIColors.NEON_RED, glow=True)

        tf = get_fitting_font(
            t('teammate_disconnected', 'Takım Arkadaşı Bağlantıyı Kesti'),
            s(24), pw - s(40))
        ts = tf.render(
            t('teammate_disconnected', 'Takım Arkadaşı Bağlantıyı Kesti'),
            True, UIColors.NEON_RED)
        self.screen.blit(ts, ts.get_rect(center=(cx, cy - s(18))))

        btn_r = pygame.Rect(cx - s(90), cy + s(20), s(180), s(42))
        mp = pygame.mouse.get_pos()
        _rs.draw_uniform_button(
            self.screen, btn_r,
            t('back_to_menu', 'Ana Menü'),
            sub_text='ESC', color_code=_rs.secondary,
            state='hover' if btn_r.collidepoint(mp) else 'normal')
        self._lobby_buttons.append({'rect': btn_r, 'action': 'back_to_lobby'})

    def _draw_online_pause_overlay(self):
        """Online co-op pause overlay — CoopGame'in kendi pause menüsü yerine basit görsel."""
        w, h = self.window_width, self.window_height
        overlay = pygame.Surface((w, h), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        self.screen.blit(overlay, (0, 0))

        sc = self._ui_scale()
        s = lambda v, minimum=1: self._sx(v, sc, minimum)

        pw = s(320)
        ph = s(120)
        panel = pygame.Rect(w // 2 - pw // 2, h // 2 - ph // 2, pw, ph)
        draw_glass_panel(self.screen, panel, alpha=180,
                        border_color=(80, 230, 160), glow=True)

        font = _rs.get_font(s(36, minimum=22), bold=True)
        text = font.render(t('paused', 'PAUSED'), True, (80, 230, 160))
        self.screen.blit(text, text.get_rect(center=(w // 2, h // 2 - s(12))))

        sub_font = _rs.get_font(s(14, minimum=10))
        sub = sub_font.render('ESC', True, _rs.text_muted)
        self.screen.blit(sub, sub.get_rect(center=(w // 2, h // 2 + s(22))))

    # ============================================================
    #  CLEANUP
    # ============================================================

    def _cleanup(self):
        """Online Co-op çıkışında kaynakları temizle ve pump thread'i sürdür."""
        try:
            self.net.shutdown()
        except Exception:
            pass
        try:
            _resume_steam_pump()
        except Exception:
            pass
