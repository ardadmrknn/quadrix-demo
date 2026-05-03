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

import pygame

# Proje import'ları
from background import BackgroundManager
from background_effects import get_shared_falling_blocks_layer
from themes import ThemeManager
from mode_skins import get_mode_skin
from block_styles import BlockStyleManager
from retro_style import retro_style as _rs
from ui_theme import UIColors
from localization import t, get_language
from sound import SoundManager
from ui_scaling import get_projected_effective_scale
from steam_networking import (
    SteamNetworking, MsgType, NetEvent, NetMessage,
    CHANNEL_GAME,
    generate_lobby_code,
)
from coop_game import CoopGame
from pieces import SHAPES as _SHAPES
from constants import COLORS as _PIECE_COLORS

# Steam pump thread kontrolü
try:
    from steam_integration import pause_pump as _pause_steam_pump
    from steam_integration import resume_pump as _resume_steam_pump
except ImportError:
    def _pause_steam_pump(): pass
    def _resume_steam_pump(): pass

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
            self.paused = True
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
        self._last_input_ack_seq = 0  # Host: en son işlenen guest input seq
        self._guest_input_seq = 0
        self._last_guest_input_seq = 0
        self._board_state_seq = 0
        self._piece_state_seq = 0
        self._guest_board_seq = -1
        self._guest_piece_seq = -1
        self._last_frozen_flags: tuple[bool, bool] | None = None

        # Host state broadcast timers (ms)
        self._board_state_timer = 0.0
        self._piece_state_timer = 0.0
        self._BOARD_STATE_INTERVAL = 100.0   # ~10 Hz
        self._PIECE_STATE_INTERVAL = 50.0    # ~20 Hz

        # Guest: received state cache
        self._guest_board_cache = None   # dict from host
        self._guest_piece_cache = None   # dict from host
        self._guest_score_cache = {}     # score/lines/level

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
            self.paused = False
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
            self.paused = True
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

        if self._lobby_list_filter == 'public':
            self._lobby_list = [
                lobby for lobby in self._lobby_list
                if str(lobby.get('visibility', 'unknown') or 'unknown').lower()
                in ('public', 'unknown', 'stale_unknown')
            ]

        self._refresh_unknown_lobby_entries()
        if self._lobby_list_filter == 'public':
            self._lobby_list = [
                lobby for lobby in self._lobby_list
                if str(lobby.get('visibility', 'unknown') or 'unknown').lower()
                in ('public', 'unknown', 'stale_unknown')
            ]

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
        ok = self.net.send({'type': 'session_ping'}, reliable=True, channel=CHANNEL_GAME)
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

            if event.type == pygame.KEYDOWN:
                # Join code text input
                if self._join_code_active and self.online_state == OnlineCoopState.LOBBY_MENU:
                    if event.key == pygame.K_BACKSPACE:
                        self._join_code_input = self._join_code_input[:-1]
                        continue
                    elif event.key == pygame.K_RETURN:
                        self._try_join_by_code()
                        continue
                    elif event.key == pygame.K_ESCAPE:
                        self._join_code_active = False
                        continue
                    elif event.unicode and event.unicode.isdigit() and len(self._join_code_input) < 6:
                        self._join_code_input += event.unicode
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

            elif event.type == pygame.KEYUP:
                if self.online_state == OnlineCoopState.PLAYING:
                    self._handle_gameplay_keyup(event)

            if event.type == pygame.VIDEORESIZE:
                self.window_width = event.w
                self.window_height = event.h
                if self.coop_game:
                    self.coop_game.screen = self.screen
                    self.coop_game.window_width = event.w
                    self.coop_game.window_height = event.h

            # Mouse click
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self._handle_mouse_click(event.pos)

        return True

    # ── Gameplay input (PLAYING state) ──

    # Host plays as P1 (WASD defaults from CoopGame controls)
    # Guest plays as P2 but from their own keyboard → sends to host
    _HOST_KEYS = {
        pygame.K_a: 'move_left',
        pygame.K_d: 'move_right',
        pygame.K_s: 'soft_drop_start',
        pygame.K_w: 'rotate',
        pygame.K_LSHIFT: 'hard_drop',
        pygame.K_e: 'hold',
    }
    _HOST_KEYUP = {
        pygame.K_a: 'das_stop',
        pygame.K_d: 'das_stop',
        pygame.K_s: 'soft_drop_stop',
    }
    # Guest uses the same keys as P2 local (arrow keys)
    _GUEST_KEYS = {
        pygame.K_LEFT: 'move_left',
        pygame.K_RIGHT: 'move_right',
        pygame.K_DOWN: 'soft_drop_start',
        pygame.K_UP: 'rotate',
        pygame.K_SPACE: 'hard_drop',
        pygame.K_RSHIFT: 'hold',
    }
    _GUEST_KEYUP = {
        pygame.K_LEFT: 'das_stop',
        pygame.K_RIGHT: 'das_stop',
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

        if self.role == 'host':
            action = self._HOST_KEYS.get(event.key)
            if action and self.coop_game:
                self.coop_game.inject_remote_input('P1', action)
        elif self.role == 'guest':
            action = self._GUEST_KEYS.get(event.key)
            if action:
                self._send_guest_input(action)

    def _handle_gameplay_keyup(self, event):
        """PLAYING state'te tuş bırakma."""
        if self.role == 'host':
            action = self._HOST_KEYUP.get(event.key)
            if action and self.coop_game:
                self.coop_game.inject_remote_input('P1', action)
        elif self.role == 'guest':
            action = self._GUEST_KEYUP.get(event.key)
            if action:
                self._send_guest_input(action)

    def _toggle_pause_safe(self):
        """Host'ta güvenli pause toggle — cooldown ile race condition önlenir."""
        if self._pause_cooldown_timer > 0:
            return
        self.paused = not self.paused
        self._freeze_active_gameplay_input()
        ev_name = 'pause' if self.paused else 'resume'
        self._send_game_event(ev_name)
        self._pause_cooldown_timer = self._PAUSE_COOLDOWN_MS

    def _freeze_active_gameplay_input(self):
        """Pause/disconnect geçişlerinde held movement state'lerini temizle."""
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

    def _handle_mouse_click(self, pos):
        """Lobi ekranlarında mouse tıklama."""
        for btn in self._lobby_buttons:
            r = btn.get('rect')
            action = btn.get('action')
            if r and action and r.collidepoint(pos):
                self._execute_button_action(action)
                break

    def _execute_button_action(self, action: str):
        if action == 'create_private':
            self._create_lobby(public=False)
        elif action == 'create_public':
            self._create_lobby(public=True)
        elif action == 'invite_friend':
            self._invite_after_lobby = True
            self._create_lobby(public=False)
        elif action == 'toggle_join_code':
            self._join_code_active = not self._join_code_active
            self._join_code_error = ''
        elif action == 'submit_join_code':
            self._try_join_by_code()
        elif action == 'refresh_list':
            self._request_lobby_list()
        elif action.startswith('join_lobby:'):
            lobby_id_str = action.split(':', 1)[1]
            try:
                self._start_lobby_browser_join(int(lobby_id_str))
            except Exception:
                self._status_msg = t('lobby_error', 'Lobi işlemi başarısız oldu!')
                self._status_timer = 3.0
        elif action == 'ready':
            self.my_ready = not self.my_ready
            if self.my_ready:
                self._send_ready_signal(reason='button_ready')
                self._check_both_ready()
        elif action == 'back_to_lobby':
            self._return_to_coop_lobby_menu()
            self._my_rematch = False
            self._opponent_rematch = False
        elif action == 'rematch':
            self._my_rematch = True
            self.net.send({'type': MsgType.REMATCH}, reliable=True, channel=CHANNEL_GAME)
            self._check_both_rematch()

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

            # Broadcast state to guest (paused'da da gönder — guest board'u görsün)
            self._board_state_timer += float(delta_time)
            self._piece_state_timer += float(delta_time)

            if self._board_state_timer >= self._BOARD_STATE_INTERVAL:
                self._board_state_timer = 0.0
                self._send_board_state()

            if self._piece_state_timer >= self._PIECE_STATE_INTERVAL:
                self._piece_state_timer = 0.0
                self._send_piece_state()

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

    def _process_messages(self):
        """Ağdan gelen mesajları işle."""
        for msg in self.net.get_messages():
            try:
                data = msg.data
                if not isinstance(data, dict):
                    continue
                msg_type = data.get('type', '')

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
                        self.paused = False
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

                # Co-op host: guest input processing
                elif msg_type == MsgType.GUEST_INPUT:
                    if self.role == 'host' and self.coop_game:
                        action = data.get('action', '')
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
                            self.coop_game.inject_remote_input('P2', action)
                            self._last_input_ack_seq = max(self._last_input_ack_seq, seq)
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
                        self._guest_board_seq = seq
                        self._guest_board_cache = data
                        self._guest_score_cache.update({
                            'team_score': data.get('team_score', 0),
                            'total_lines': data.get('total_lines', 0),
                            'level': data.get('level', 1),
                        })

                elif msg_type == MsgType.COOP_PIECE_STATE:
                    if self.role == 'guest':
                        try:
                            seq = int(data.get('seq', 0) or 0)
                        except (TypeError, ValueError):
                            seq = 0
                        if seq < self._guest_piece_seq:
                            continue
                        self._guest_piece_seq = seq
                        self._guest_piece_cache = data

                elif msg_type == MsgType.COOP_LOCK_EVENT:
                    if self.role == 'guest':
                        # Update score/lines from lock
                        self._guest_score_cache['team_score'] = data.get('new_score', 0)
                        self._guest_score_cache['level'] = data.get('new_level', 1)
                        if data.get('total_lines', 0):
                            self._guest_score_cache['total_lines'] = data['total_lines']

                elif msg_type == MsgType.COOP_GAME_EVENT:
                    event_name = data.get('event', '')
                    if event_name == 'game_over':
                        self.game_over = True
                        self.online_state = OnlineCoopState.GAME_OVER
                        self._guest_score_cache.update(data.get('data', {}))
                    elif event_name == 'pause':
                        self.paused = True
                        self._freeze_active_gameplay_input()
                    elif event_name == 'resume':
                        self.paused = False
                        self._freeze_active_gameplay_input()
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
        send_coop_start = getattr(self.net, 'send_coop_start', None)
        if callable(send_coop_start):
            return bool(send_coop_start(seed, sub_mode=sub_mode))
        return bool(self.net.send({
            'type': MsgType.COOP_GAME_START,
            'seed': seed,
            'sub_mode': sub_mode,
            'timestamp': time.time(),
        }, reliable=True, channel=CHANNEL_GAME))

    def _start_countdown(self):
        """3-2-1 geri sayım başlat."""
        self.online_state = OnlineCoopState.COUNTDOWN
        self.countdown_value = 3
        self.countdown_timer = 0
        try:
            self.sound.stop_music()
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
            )
            # Event listener: lock/clear/game_over gibi olayları guest'e yayınla
            self.coop_game._event_listeners.append(self._on_coop_event)
            self._last_frozen_flags = (
                bool(self.coop_game.p1_frozen),
                bool(self.coop_game.p2_frozen),
            )
            # NOT: Otoriter host modelinde deterministik RNG gerekmez.
            # Guest simülasyon yapmıyor, tüm state host'tan gelir.
        else:
            # Guest: state cache'leri temizle
            self._guest_board_cache = None
            self._guest_piece_cache = None
            self._guest_score_cache = {}
            self._guest_board_seq = -1
            self._guest_piece_seq = -1

        # Broadcast timer'larını sıfırla
        self._board_state_timer = 0.0
        self._piece_state_timer = 0.0
        self._last_input_ack_seq = 0
        self._last_guest_input_seq = 0
        self._board_state_seq = 0
        self._piece_state_seq = 0
        if self.role == 'host':
            self._send_board_state()
            self._send_piece_state()

    def _on_coop_event(self, event_type: str, event_data: dict):
        """CoopGame event listener — host lock/clear/freeze olaylarını guest'e iletir."""
        if self.role != 'host':
            return
        if event_type == 'lines_cleared':
            self._send_lock_event(event_data)
            self._send_board_state()
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

    def _send_board_state(self):
        """Host → Guest: board grid + game state (unreliable)."""
        if not self.coop_game:
            return
        b = self.coop_game.board
        self._board_state_seq += 1
        # Compact grid: list of lists of [r,g,b] for non-empty, 0 for empty
        grid = []
        owners = []
        for row_idx in range(b.height):
            grow = []
            orow = []
            for col_idx in range(b.width):
                cell = b.grid[row_idx][col_idx]
                if cell and cell != (0, 0, 0):
                    grow.append(list(cell))
                else:
                    grow.append(0)
                owner = b.owners[row_idx][col_idx] if hasattr(b, 'owners') else None
                orow.append(owner or '')
            grid.append(grow)
            owners.append(orow)

        data = {
            'type': MsgType.COOP_BOARD_STATE,
            'seq': self._board_state_seq,
            'grid': grid,
            'owners': owners,
            'team_score': self.coop_game.team_score,
            'total_lines': self.coop_game.total_lines_cleared,
            'level': self.coop_game.level,
            'fall_speed': self.coop_game.fall_speed,
            'p1_frozen': self.coop_game.p1_frozen,
            'p2_frozen': self.coop_game.p2_frozen,
        }
        self.net.send(data, reliable=False, channel=CHANNEL_GAME)

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
        }
        self.net.send(data, reliable=False, channel=CHANNEL_GAME)

    def _send_lock_event(self, event_data: dict):
        """Host → Guest: parça kilit / satır temizleme olayı (reliable)."""
        data = {
            'type': MsgType.COOP_LOCK_EVENT,
            'player': event_data.get('player', ''),
            'new_score': self.coop_game.team_score if self.coop_game else 0,
            'new_level': self.coop_game.level if self.coop_game else 1,
            'lines': event_data.get('lines', 0),
            'total_lines': event_data.get('total_lines', 0),
            'p1_frozen': self.coop_game.p1_frozen if self.coop_game else False,
            'p2_frozen': self.coop_game.p2_frozen if self.coop_game else False,
        }
        self.net.send(data, reliable=True, channel=CHANNEL_GAME)

    def _send_game_event(self, event_name: str, event_data: dict = None):
        """Host → Guest: genel oyun olayı (reliable)."""
        data = {
            'type': MsgType.COOP_GAME_EVENT,
            'event': event_name,
            'data': event_data or {},
        }
        self.net.send(data, reliable=True, channel=CHANNEL_GAME)

    # ============================================================
    #  GUEST INPUT SENDING
    # ============================================================

    def _send_guest_input(self, action: str):
        """Guest → Host: input aksiyonu gönder (reliable)."""
        self._guest_input_seq = getattr(self, '_guest_input_seq', 0) + 1
        data = {
            'type': MsgType.GUEST_INPUT,
            'action': action,
            'seq': self._guest_input_seq,
            'ts': time.time(),
        }
        self.net.send(data, reliable=True, channel=CHANNEL_GAME)

    def draw(self):
        """Ekranı çiz."""
        self._lobby_buttons.clear()
        self._skip_flip = False

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

        if not self._skip_flip:
            pygame.display.flip()

    # ============================================================
    #  DRAW: Online Shell Ekranları (PvP'den adapte)
    # ============================================================

    def _draw_lobby_menu(self):
        """Co-op lobi menüsü."""
        w, h = self.window_width, self.window_height
        cx = w // 2
        sc = self._ui_scale()
        s = lambda v, minimum=1: self._sx(v, sc, minimum)

        # Başlık
        title_rect = _rs.draw_title(self.screen, t('online_coop_title', 'ONLINE CO-OP'), (cx, s(58)))

        # Sol panel: butonlar
        btn_w = s(340)
        btn_h = s(52)
        panel_left = max(s(30), cx - s(400))
        btn_x = panel_left
        btn_y = title_rect.bottom + s(28)
        gap = s(12)

        # Özel Lobi bölümü
        section_font = _rs.get_font(s(13, minimum=10), bold=False)
        sec1 = section_font.render(t('private_coop_section', '── Özel Co-op ──'),
                                   True, _rs.text_muted)
        self.screen.blit(sec1, sec1.get_rect(center=(btn_x + btn_w // 2, btn_y)))
        btn_y += s(24)

        buttons = [
            (t('create_private_coop', 'Özel Endless Lobi'), 'create_private'),
            (t('join_by_code', 'Kod ile Katıl'), 'toggle_join_code'),
            (t('invite_friend_coop', 'Arkadaş Davet Et'), 'invite_friend'),
        ]

        mouse_pos = pygame.mouse.get_pos()
        for label, action in buttons:
            btn_rect = pygame.Rect(btn_x, btn_y, btn_w, btn_h)
            hover = btn_rect.collidepoint(mouse_pos)
            _rs.draw_uniform_button(
                self.screen, btn_rect, label,
                color_code=_rs.accent if hover else _rs.secondary,
                state='hover' if hover else 'normal',
            )
            self._lobby_buttons.append({'rect': btn_rect, 'action': action})
            btn_y += btn_h + gap

        if self._join_code_active:
            input_rect = pygame.Rect(btn_x, btn_y + s(2), btn_w, s(54))
            draw_glass_panel(self.screen, input_rect, alpha=140, border_color=(80, 230, 160))
            code_font = _rs.get_font(s(22, minimum=15), bold=True)
            display_code = self._join_code_input or '------'
            if len(display_code) == 6 and display_code.isdigit():
                display_code = f'{display_code[:3]} {display_code[3:]}'
            code_surf = code_font.render(display_code, True, UIColors.TEXT_PRIMARY)
            self.screen.blit(code_surf, code_surf.get_rect(center=input_rect.center))
            self._lobby_buttons.append({'rect': input_rect, 'action': 'submit_join_code'})
            btn_y += input_rect.height + s(6)

            hint_font = _rs.get_font(s(12, minimum=10), bold=False)
            hint_text = self._join_code_error or t('enter_six_digit_code', '6 haneli lobi kodu girin')
            hint_color = UIColors.NEON_RED if self._join_code_error else _rs.text_muted
            hint = hint_font.render(hint_text, True, hint_color)
            self.screen.blit(hint, hint.get_rect(center=(btn_x + btn_w // 2, btn_y + s(8))))
            btn_y += s(22)

        # Herkese Açık bölümü
        btn_y += s(12)
        sec2 = section_font.render(t('public_coop_section', '── Herkese Açık ──'),
                                   True, _rs.text_muted)
        self.screen.blit(sec2, sec2.get_rect(center=(btn_x + btn_w // 2, btn_y)))
        btn_y += s(24)

        public_buttons = [
            (t('create_public_coop', 'Açık Endless Lobi'), 'create_public'),
            (t('find_coop_lobby', 'Co-op Lobi Bul'), 'refresh_list'),
        ]
        for label, action in public_buttons:
            btn_rect = pygame.Rect(btn_x, btn_y, btn_w, btn_h)
            hover = btn_rect.collidepoint(mouse_pos)
            _rs.draw_uniform_button(
                self.screen, btn_rect, label,
                color_code=_rs.accent if hover else _rs.secondary,
                state='hover' if hover else 'normal',
            )
            self._lobby_buttons.append({'rect': btn_rect, 'action': action})
            btn_y += btn_h + gap

        # Sağ panel: lobi listesi
        list_left = cx + s(20)
        list_top = title_rect.bottom + s(28)
        list_w = min(s(400), w - list_left - s(30))
        list_h = h - list_top - s(100)
        list_rect = pygame.Rect(list_left, list_top, list_w, list_h)
        draw_glass_panel(self.screen, list_rect, alpha=160,
                        border_color=(80, 230, 160), glow=False)

        list_title_font = _rs.get_font(s(16, minimum=12), bold=True)
        list_title = list_title_font.render(
            t('coop_lobby_list_title', 'Mevcut Co-op Lobileri'),
            True, UIColors.TEXT_PRIMARY)
        self.screen.blit(list_title, list_title.get_rect(
            midtop=(list_left + list_w // 2, list_top + s(12))))

        if self._lobby_list_fetching:
            loading_font = _rs.get_font(s(14, minimum=11), bold=False)
            loading = loading_font.render(
                t('lobby_list_loading', 'Yükleniyor...'),
                True, _rs.text_muted)
            self.screen.blit(loading, loading.get_rect(
                center=(list_left + list_w // 2, list_top + list_h // 2)))
        elif not self._lobby_list:
            empty_font = _rs.get_font(s(14, minimum=11), bold=False)
            empty = empty_font.render(
                t('no_coop_lobbies', 'Henüz aktif co-op lobisi yok'),
                True, _rs.text_muted)
            self.screen.blit(empty, empty.get_rect(
                center=(list_left + list_w // 2, list_top + list_h // 2)))
        else:
            item_h = s(60)
            item_y = list_top + s(40)
            item_font = _rs.get_font(s(14, minimum=11))
            sub_font_sm = _rs.get_font(s(12, minimum=10), bold=False)
            for lobby in self._lobby_list[:max(1, (list_h - s(50)) // item_h)]:
                host_name = str(lobby.get('host_name') or lobby.get('name') or '?')
                sub_mode = str(lobby.get('sub_mode', 'endless'))
                visibility = str(lobby.get('visibility', 'unknown') or 'unknown')
                item_rect = pygame.Rect(list_left + s(8), item_y, list_w - s(16), item_h - s(4))
                border = (80, 230, 160) if visibility == 'public' else (130, 170, 240)
                draw_glass_panel(self.screen, item_rect, alpha=120, border_color=border)
                name_surf = item_font.render(f"{host_name}", True, UIColors.TEXT_PRIMARY)
                self.screen.blit(name_surf, (item_rect.x + s(10), item_rect.y + s(8)))
                info = sub_font_sm.render(f"{sub_mode.capitalize()} | {visibility}", True, _rs.text_muted)
                self.screen.blit(info, (item_rect.x + s(10), item_rect.y + s(30)))
                lobby_id = lobby.get('lobby_id') or lobby.get('id')
                if lobby_id:
                    self._lobby_buttons.append({
                        'rect': item_rect,
                        'action': f'join_lobby:{lobby_id}'
                    })
                item_y += item_h

        # Durum mesajı
        if self._status_msg:
            status_font = _rs.get_font(s(14, minimum=11), bold=False)
            status = status_font.render(self._status_msg, True, UIColors.TEXT_SECONDARY)
            self.screen.blit(status, status.get_rect(center=(cx, h - s(40))))

    def _draw_waiting_screen(self):
        """Takım arkadaşı bekleme ekranı."""
        w, h = self.window_width, self.window_height
        cx, cy = w // 2, h // 2
        sc = self._ui_scale()
        s = lambda v, minimum=1: self._sx(v, sc, minimum)

        pw = min(s(520), w - s(80))
        ph = s(440)
        panel = pygame.Rect(cx - pw // 2, cy - ph // 2, pw, ph)
        draw_glass_panel(self.screen, panel, alpha=185,
                        border_color=(80, 230, 160), glow=True)

        # Başlık
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

        # Mod badge
        mode_font = _rs.get_font(s(14, minimum=11), bold=True)
        mode_text = f"Mod: {self.selected_submode.capitalize()}"
        mode_surf = mode_font.render(mode_text, True, UIColors.TEXT_PRIMARY)
        self.screen.blit(mode_surf, mode_surf.get_rect(center=(cx, panel.y + s(105))))

        # Lobi kodu
        if self._lobby_code:
            code_label_font = _rs.get_font(s(14, minimum=11), bold=False)
            code_label = code_label_font.render(
                t('lobby_code_label', 'Lobi Kodu'), True, _rs.text_muted)
            self.screen.blit(code_label, code_label.get_rect(center=(cx, panel.y + s(150))))

            code_font = _rs.get_font(s(42, minimum=24), bold=True)
            formatted = self._lobby_code[:3] + ' ' + self._lobby_code[3:] if len(self._lobby_code) >= 6 else self._lobby_code
            code_surf = code_font.render(formatted, True, UIColors.TEXT_PRIMARY)
            self.screen.blit(code_surf, code_surf.get_rect(center=(cx, panel.y + s(190))))

            hint_font = _rs.get_font(s(12, minimum=10), bold=False)
            hint = hint_font.render(
                t('share_code_hint', 'Bu kodu arkadaşınla paylaş'),
                True, _rs.text_muted)
            self.screen.blit(hint, hint.get_rect(center=(cx, panel.y + s(225))))

        # Geri butonu
        back_rect = pygame.Rect(cx - s(110), panel.bottom - s(70), s(220), s(44))
        mouse_pos = pygame.mouse.get_pos()
        _rs.draw_uniform_button(
            self.screen, back_rect,
            t('back_to_coop_lobby', 'Co-op Lobiye Dön'),
            sub_text='ESC',
            color_code=_rs.secondary,
            state='hover' if back_rect.collidepoint(mouse_pos) else 'normal',
        )
        self._lobby_buttons.append({'rect': back_rect, 'action': 'back_to_lobby'})

    def _draw_ready_check(self):
        """Ready-check ekranı: iki oyuncu kartı + CO-OP başlık."""
        w, h = self.window_width, self.window_height
        cx, cy = w // 2, h // 2
        sc = self._ui_scale()
        s = lambda v, minimum=1: self._sx(v, sc, minimum)

        pw = min(s(650), w - s(80))
        ph = s(420)
        panel = pygame.Rect(cx - pw // 2, cy - ph // 2, pw, ph)
        draw_glass_panel(self.screen, panel, alpha=185,
                        border_color=(80, 230, 160), glow=True)

        # CO-OP başlık
        vs_font = _rs.get_font(s(48, minimum=28))
        vs = vs_font.render('CO-OP', True, (80, 230, 160))
        self.screen.blit(vs, vs.get_rect(center=(cx, panel.y + s(50))))

        # Oyuncu kartları
        card_w = s(180)
        card_h = s(160)
        card_gap = s(60)
        my_card = pygame.Rect(cx - card_gap // 2 - card_w, cy - card_h // 2 + s(20), card_w, card_h)
        opp_card = pygame.Rect(cx + card_gap // 2, cy - card_h // 2 + s(20), card_w, card_h)

        for card_rect, is_me in [(my_card, True), (opp_card, False)]:
            ready = self.my_ready if is_me else self.opponent_ready
            border_color = (80, 230, 160) if ready else (100, 100, 120)
            draw_glass_panel(self.screen, card_rect, alpha=150, border_color=border_color)

            name = t('you', 'Sen') if is_me else (getattr(self.net, 'opponent_name', '') or t('teammate', 'Takım Arkadaşı'))
            name_font = _rs.get_font(s(16, minimum=12), bold=True)
            name_surf = name_font.render(name, True, UIColors.TEXT_PRIMARY)
            self.screen.blit(name_surf, name_surf.get_rect(center=(card_rect.centerx, card_rect.y + s(40))))

            status_font = _rs.get_font(s(14, minimum=11), bold=True)
            if ready:
                status = status_font.render(t('ready_status', 'HAZIR'), True, (80, 230, 160))
            else:
                status = status_font.render(t('not_ready_status', 'Bekleniyor'), True, _rs.text_muted)
            self.screen.blit(status, status.get_rect(center=(card_rect.centerx, card_rect.bottom - s(40))))

        # Hazır butonu
        ready_rect = pygame.Rect(cx - s(100), panel.bottom - s(80), s(200), s(48))
        mouse_pos = pygame.mouse.get_pos()
        ready_label = t('ready_button', 'Hazırım!') if not self.my_ready else t('cancel_ready', 'İptal')
        _rs.draw_uniform_button(
            self.screen, ready_rect, ready_label,
            color_code=_rs.accent if not self.my_ready else _rs.secondary,
            state='hover' if ready_rect.collidepoint(mouse_pos) else 'normal',
        )
        self._lobby_buttons.append({'rect': ready_rect, 'action': 'ready'})

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
            pygame.display.flip()
            self._skip_flip = True
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
        for row_idx in range(min(board_h, len(grid))):
            row = grid[row_idx]
            for col_idx in range(min(board_w, len(row))):
                cell = row[col_idx]
                px = board_x + col_idx * cell_size
                py = board_y + row_idx * cell_size
                if cell and cell != 0:
                    color = tuple(cell) if isinstance(cell, list) else (128, 128, 128)
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
