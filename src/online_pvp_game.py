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
import time
import random
import os
import sys

import pygame

# Proje import'ları
from constants import (
    BOARD_WIDTH, BOARD_HEIGHT, BLACK, COLORS,
    INITIAL_FALL_SPEED, FAST_FALL_SPEED, SPEED_INCREASE_PER_LEVEL,
    DEFAULT_LOCK_DELAY, DAS_DELAY, DAS_REPEAT,
)
from board import Board
from pieces import Piece, SHAPES
from sound import SoundManager
from background import BackgroundManager
from background_effects import get_shared_falling_blocks_layer
from themes import ThemeManager
from retro_style import retro_style as _rs
from renderers.jelly_renderer import draw_jelly_block

# Convenience aliases for retro_style singleton methods
get_font = _rs.get_font
draw_glass_panel = _rs.draw_glass_panel
get_fitting_font = _rs.get_fitting_font
from ui_theme import UIFonts, UIColors, UIStyle
from localization import t
from steam_networking import (
    SteamNetworking, MsgType, NetEvent, NetMessage,
    CHANNEL_GAME, CHANNEL_STATE, CHANNEL_CONTROL,
    generate_lobby_code,
)

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
    from gamepad_manager import GamepadManager
except ImportError:
    GamepadManager = None

try:
    from platform_utils import create_display, set_app_icon, resource_path
    from platform_utils import normalize_mouse_pos, get_mouse_pos, is_fullscreen_toggle
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
    def is_fullscreen_toggle(key, mods, custom_key=None):
        return key == pygame.K_F12


# ─────────────── Online PvP Durumları ───────────────

class OnlineState:
    LOBBY_MENU   = 'lobby_menu'    # Lobi oluştur / katıl ekranı
    WAITING      = 'waiting'       # Lobide rakip bekleniyor
    READY_CHECK  = 'ready_check'   # İki oyuncu da hazır mı?
    COUNTDOWN    = 'countdown'     # 3-2-1 geri sayım
    PLAYING      = 'playing'       # Oyun devam ediyor
    GAME_OVER    = 'game_over'     # Maç bitti
    DISCONNECTED = 'disconnected'  # Bağlantı koptu


# ─────────────── Çöp Satır Tablosu ───────────────

GARBAGE_TABLE = {
    1: 0,   # Tek satır = çöp yok
    2: 1,   # Double = 1 çöp
    3: 2,   # Triple = 2 çöp
    4: 4,   # Quadrix = 4 çöp
}


class OnlinePvPGame:
    """Steam P2P üzerinden Online 1v1 Tetris maçı."""

    # ── Responsive ölçek (pvp_game.py ile aynı pattern) ──

    def _ui_scale(self, min_scale: float = 0.72, max_scale: float = 1.20) -> float:
        """Pencere boyutuna bağlı genel UI ölçeği."""
        try:
            scale = min(float(self.window_width) / 1366.0,
                        float(self.window_height) / 768.0)
        except Exception:
            scale = 1.0
        return max(min_scale, min(max_scale, scale))

    def _sx(self, value, scale=None, minimum=1) -> int:
        """Sabit piksel değerini UI ölçeğine göre dönüştür."""
        if scale is None:
            scale = self._ui_scale()
        return max(minimum, int(round(float(value) * float(scale))))

    def __init__(
        self,
        screen=None,
        fullscreen=False,
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
            self.window_width = screen.get_width()
            self.window_height = screen.get_height()
        else:
            self.window_width = 1400
            self.window_height = 1000
            self.screen = create_display(self.window_width, self.window_height,
                                         fullscreen=False, resizable=True)

        self.fullscreen = fullscreen
        self.clock = pygame.time.Clock()

        # Ses
        self.sound = sound_manager if sound_manager else SoundManager()
        if settings_manager:
            self.sound.music_enabled = settings_manager.get('music_enabled', True)

        # Arka plan
        self.background = BackgroundManager()
        self.background.set_transparency(1.0)
        self.background_fx = get_shared_falling_blocks_layer('default')

        # Tema
        self.theme_manager = ThemeManager(settings_manager)

        # Font'lar (retro_style üzerinden — CJK/HybridFont desteği)
        self.font_large = _rs.get_font(36)
        self.font_medium = _rs.get_font(24)
        self.font_small = _rs.get_font(18)
        self.font_tiny = _rs.get_font(14, bold=False)

        # ─── Steam Networking ───
        self.net = SteamNetworking()
        self._net_initialized = False

        # ─── Gamepad ───
        self.gamepad: GamepadManager | None = None
        if GamepadManager is not None:
            try:
                self.gamepad = GamepadManager()
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

        # Zamanlama
        self.fall_timer = 0
        self.lock_timer = 0
        self.countdown_timer = 0.0
        self.countdown_value = 3
        self.state_snapshot_timer = 0.0
        self.STATE_SNAPSHOT_INTERVAL = 500  # ms — her 500ms'de tahta snapshot'ı gönder

        # Flags
        self.my_ready = False
        self.opponent_ready = False
        self.game_over = False
        self.winner: str = ''  # 'me', 'opponent', 'draw'
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
        self._lobby_list: list[dict] = []  # Public lobiler
        self._lobby_list_scroll = 0
        self._lobby_list_fetching = False
        self._pending_lobby_list: list[dict] = []  # Lobi listesi birikim tampon

        # Durum mesajı (hata/bilgi)
        self._status_msg: str = ''
        self._status_timer: float = 0

        # Lobi oluşturulduktan sonra otomatik davet aç
        self._invite_after_lobby: bool = False

        # ─── Lobi Kodu Sistemi ───
        self._lobby_code: str = ''          # Oluşturulan lobi kodu (6 haneli)
        self._lobby_id_str: str = ''        # Ham lobby ID (tam numara)
        self._join_code_input: str = ''     # "Kod ile Katıl" metin girişi
        self._join_code_active: bool = False  # Metin girişi aktif mi
        self._join_code_error: str = ''     # Giriş hata mesajı
        self._searching_by_code: bool = False  # Kod ile arama yapılıyor mu
        self._search_code: str = ''         # Aranan kod (lobby_list_complete'de eşleşme için)

        # Müzik başlat (lobi ekranına girince)
        self._start_pvp_music()

    # ============================================================
    #  BAŞLATMA
    # ============================================================

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
            self.net.on('lobby_member_disconnected', self._on_member_left)
            # Lobi listesi — C++ per-lobi event gönderiyor, tek JSON değil
            self.net.on('lobby_found', self._on_lobby_found)
            self.net.on('lobby_list_complete', self._on_lobby_list_complete)
            # Steam overlay "Oyuna Katıl" isteği
            self.net.on('join_requested', self._on_join_requested)
            # Hata olayları
            self.net.on('lobby_create_failed', self._on_lobby_error)
            self.net.on('lobby_join_failed', self._on_lobby_error)
            self.net.on('lobby_list_failed', self._on_lobby_list_error)
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
        print(f"[OnlinePvP] Lobi oluşturuldu: {ev.steam_id}")

        # ─── Lobi kodu oluştur ve metadata'ya kaydet ───
        self._lobby_id_str = str(ev.steam_id)
        self._lobby_code = generate_lobby_code(ev.steam_id)
        # Metadata'ya kaydet (kod ile arama desteği için)
        self.net.set_lobby_data('lobby_code', self._lobby_code)
        self.net.set_lobby_data('lobby_code_full', self._lobby_id_str)
        # Host adını metadata'ya kaydet (lobi listesinde gösterilmek üzere)
        host_name = ''
        try:
            host_name = self.net._get_name(self.net.my_steam_id)
        except Exception:
            pass
        if host_name:
            self.net.set_lobby_data('host_name', host_name)
        print(f"[OnlinePvP] Lobi Kodu: {self._lobby_code}  |  Tam ID: {self._lobby_id_str}")

        # Davet bekletilmişse şimdi aç
        if self._invite_after_lobby:
            self._invite_after_lobby = False
            try:
                self.net.invite_friend()
            except Exception:
                pass
            # Windows'ta ek olarak doğrudan ctypes overlay dene
            if sys.platform == 'win32' and ev.steam_id:
                _activate_invite_dialog(ev.steam_id)
            self._status_msg = t('invite_sent', 'Steam davet penceresi açıldı')
            self._status_timer = 2.5

    def _on_lobby_joined(self, ev: NetEvent):
        self.online_state = OnlineState.WAITING
        # Rakip zaten lobideyse bul
        if self.net.opponent_steam_id:
            self.online_state = OnlineState.READY_CHECK

    def _on_member_joined(self, ev: NetEvent):
        if ev.steam_id != self.net.my_steam_id:
            self.online_state = OnlineState.READY_CHECK
            print(f"[OnlinePvP] Rakip katıldı: {self.net.opponent_name}")
            try:
                self.sound.play('click')
            except Exception:
                pass

    def _on_member_left(self, ev: NetEvent):
        if ev.steam_id == self.net.opponent_steam_id:
            if self.online_state == OnlineState.PLAYING:
                self.online_state = OnlineState.DISCONNECTED
                self.game_over = True
                self.winner = 'me'
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

    def _on_lobby_found(self, ev: NetEvent):
        """Tek bir public lobi bulundu — biriktir."""
        # Lobi sahibi bilgisini metadata'dan almayı dene.
        # Not: get_lobby_data, bridge'in lobby_found callback bağlamında
        # bulunan lobinin metadata'sını döndürmelidir. Ancak bridge
        # implementasyonuna bağlı olarak boş string dönebilir — fallback mevcut.
        host_name = ''
        lobby_code = ''
        try:
            host_name = self.net.get_lobby_data('host_name') or ''
        except Exception:
            pass
        try:
            lobby_code = self.net.get_lobby_data('lobby_code') or ''
        except Exception:
            pass

        # ev.data genelde "members" bilgisini taşır — parse kontrolü
        try:
            member_count = int(ev.data) if ev.data and ev.data.isdigit() else 0
        except (ValueError, AttributeError):
            member_count = 0

        self._pending_lobby_list.append({
            'id': ev.steam_id,
            'members': member_count,
            'max_members': 2,
            'name': host_name or f'Lobi #{len(self._pending_lobby_list) + 1}',
            'code': lobby_code,
            'found_time': time.time(),
        })

    def _on_lobby_list_complete(self, ev: NetEvent):
        """Lobi listesi tamamlandı — sonuçları onayla."""
        self._lobby_list_fetching = False
        self._lobby_list = self._pending_lobby_list[:]
        self._pending_lobby_list.clear()
        self._lobby_list_scroll = 0
        count = len(self._lobby_list)
        print(f"[OnlinePvP] {count} lobi bulundu.")

        # Kod ile arama yapılıyorsa otomatik katıl
        if self._searching_by_code:
            self._searching_by_code = False
            if count > 0:
                # İlk eşleşen lobiye katıl
                lobby_id = self._lobby_list[0].get('id', 0)
                if lobby_id:
                    self.net.join_lobby(lobby_id)
                    self._status_msg = t('joining_lobby', 'Lobiye katılınıyor...')
                    self._status_timer = 2.0
                else:
                    self._status_msg = t('lobby_not_found_by_code', 'Bu kodla lobi bulunamadı')
                    self._status_timer = 3.0
            else:
                # Kod ile bulunamadı — tam ID olarak dene
                self._try_direct_join_by_code(self._search_code)
            self._search_code = ''
            return

        if count == 0:
            self._status_msg = t('no_lobbies_found', 'Lobi bulunamadı')
            self._status_timer = 2.5

    def _on_lobby_error(self, ev: NetEvent):
        """Lobi oluşturma/katılma hatası."""
        print(f"[OnlinePvP] Lobi hatası: {ev.type} — {ev.data}")
        self.online_state = OnlineState.LOBBY_MENU
        self._status_msg = t('lobby_error', 'Lobi işlemi başarısız oldu!')
        self._status_timer = 4.0

    def _on_lobby_list_error(self, ev: NetEvent):
        """Lobi listesi alınamadı."""
        self._lobby_list_fetching = False
        self._lobby_list = []
        if self._searching_by_code:
            self._searching_by_code = False
            # Arama başarısız — doğrudan ID ile dene
            self._try_direct_join_by_code(self._search_code)
            self._search_code = ''
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
        self._status_msg = t('joining_lobby', 'Lobiye katılınıyor...')
        self._status_timer = 2.0

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
            if opponent_id and msg.sender != opponent_id:
                print(f"[OnlinePvP] Bilinmeyen gönderici {msg.sender} — mesaj ignore edildi.")
                continue

            if msg_type == MsgType.READY:
                self.opponent_ready = True
                self._check_both_ready()

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

            elif msg_type == MsgType.SCORE_UPDATE:
                self.opponent_score = self._clamp_int(data.get('score', 0), 0, 999999, 'score')
                self.opponent_lines = self._clamp_int(data.get('lines', 0), 0, 999999, 'opponent_lines')
                self.opponent_level = self._clamp_int(data.get('level', 1), 0, 30, 'level')

            elif msg_type == MsgType.GAME_OVER:
                # Rakip öldü — ama biz de ölmüş olabiliriz (race condition)
                if self.game_over and self.winner == 'opponent':
                    # İkimiz de aynı anda öldük — skor karşılaştırması ile karar ver
                    my_score = self.my_board.score if self.my_board else 0
                    opp_score = self._clamp_int(data.get('score', 0), 0, 999999, 'opp_final_score')
                    if my_score > opp_score:
                        self.winner = 'me'
                        print(f"[OnlinePvP] Simultane ölüm — skor karşılaştırması: BEN ({my_score}) > RAKİP ({opp_score})")
                    elif opp_score > my_score:
                        self.winner = 'opponent'
                        print(f"[OnlinePvP] Simultane ölüm — skor karşılaştırması: RAKİP ({opp_score}) > BEN ({my_score})")
                    else:
                        self.winner = 'draw'
                        print(f"[OnlinePvP] Simultane ölüm — BERABERE (her iki skor: {my_score})")
                    self.online_state = OnlineState.GAME_OVER
                elif not self.game_over:
                    # Normal durum — rakip öldü, biz kazandık
                    self.game_over = True
                    self.winner = 'me'
                    self.online_state = OnlineState.GAME_OVER
                    try:
                        self.sound.play('tetris')  # zafer sesi
                    except Exception:
                        pass
                # else: game_over zaten True ve winner zaten 'me' — ignore

            elif msg_type == MsgType.ELIMINATED:
                if not self.game_over:
                    self.game_over = True
                    self.winner = 'me'
                    self.online_state = OnlineState.GAME_OVER

            elif msg_type == MsgType.PAUSE_REQUEST:
                self.opponent_paused = True

            elif msg_type == MsgType.RESUME:
                self.opponent_paused = False

            elif msg_type == MsgType.REMATCH:
                # Rakip rematch istiyor
                self.opponent_ready = False
                self.my_ready = False
                self.game_over = False
                self.winner = ''
                self.online_state = OnlineState.READY_CHECK
                self._status_msg = t('opponent_wants_rematch', 'Rakip tekrar oynamak istiyor!')
                self._status_timer = 3.0

    def _check_both_ready(self):
        """İki oyuncu da hazırsa oyun başlamayı tetikle."""
        if self.my_ready and self.opponent_ready:
            if self.net.is_host:
                # Host başlama sinyali gönderir
                self.game_seed = random.randint(1, 999999)
                self._generate_pieces(self.game_seed, 200)
                self.net.send_game_start(self.game_seed, self.piece_sequence[:200])
                self._start_countdown()

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
        self.my_next_piece = self._get_next_piece()
        self.next_piece = self.my_next_piece  # side panel referansı
        self.hold_piece = None
        self.hold_used = False
        self.hold_shape_index = -1
        self.fall_timer = 0
        self.lock_timer = 0
        self.game_over = False
        self.pending_garbage = 0
        self._garbage_gap = 0
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

    def _get_next_piece(self) -> Piece:
        """Sıradaki parçayı al."""
        if self.piece_index >= len(self.piece_sequence):
            # Daha fazla parça üret (aynı seed)
            self._generate_pieces(self.game_seed + self.piece_index, 100)
        idx = self.piece_sequence[self.piece_index]
        self.piece_index += 1
        piece = Piece(x=3, y=0, shape_index=idx)
        return piece

    # ============================================================
    #  ÇÖP SATIR MEKANİĞİ
    # ============================================================

    def _send_garbage(self, lines_cleared: int):
        """Satır temizlediğimizde rakibe çöp gönder."""
        garbage_lines = GARBAGE_TABLE.get(lines_cleared, 0)
        if garbage_lines > 0:
            gap_col = random.randint(0, BOARD_WIDTH - 1)
            self.net.send_garbage(garbage_lines, gap_col)

    def _receive_garbage(self, lines: int, gap_col: int = -1):
        """Rakipten gelen çöp satırları kuyruğa al — parça kilitlenince uygulanır."""
        if lines <= 0:
            return
        if gap_col < 0:
            gap_col = random.randint(0, BOARD_WIDTH - 1)

        self.pending_garbage += lines
        self._garbage_gap = gap_col  # Son gap sütunu (uygulamada kullanılacak)

    def _apply_pending_garbage(self):
        """Kuyrukta bekleyen çöp satırları tahtaya uygula."""
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
                    # Parça kurtarılamadı — oyun bitti
                    self.game_over = True
                    self.winner = 'opponent'
                    self.online_state = OnlineState.GAME_OVER
                    self.net.send_game_over(
                        self.my_board.score, self.my_board.lines_cleared)
                    try:
                        self.sound.play('gameover')
                    except Exception:
                        pass

    def _update_opponent_display(self, data: dict):
        """Rakip tahta snapshot'ını güncelle."""
        grid = data.get('grid')
        if grid:
            self.opponent_grid_snapshot = grid
        self.opponent_score = data.get('score', self.opponent_score)
        self.opponent_lines = data.get('lines', self.opponent_lines)
        self.opponent_level = data.get('level', self.opponent_level)

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
            self.my_piece = self.my_next_piece
            self.my_next_piece = self._get_next_piece()
            self.next_piece = self.my_next_piece
        else:
            # Swap
            old_hold = self.hold_shape_index
            self.hold_shape_index = current_shape_index
            self.hold_piece = Piece(x=0, y=0, shape_index=current_shape_index)
            self.my_piece = Piece(x=3, y=0, shape_index=old_hold)

        self.hold_used = True
        self.lock_timer = 0
        try:
            self.sound.play('hold')
        except Exception:
            pass

        # Hold sonrası parça geçerli pozisyonda mı kontrol et
        if not self.my_board.is_valid_position(self.my_piece):
            # Yukarı kaydır
            for offset in range(1, 4):
                self.my_piece.y = -offset
                if self.my_board.is_valid_position(self.my_piece):
                    break

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

    def _send_board_snapshot(self):
        """Kendi tahta durumunu rakibe gönder."""
        if not self.my_board:
            return
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

        self.net.send_board_state({
            'grid': compact_grid,
            'score': self.my_board.score,
            'lines': self.my_board.lines_cleared,
            'level': self.my_board.level,
        })

    # ============================================================
    #  OYUN GÜNCELLEMESİ
    # ============================================================

    def update(self, delta_time: int):
        """Her frame çağrılır."""
        # Steam callback'leri işle
        if self._net_initialized:
            self.net.tick()
            self._process_messages()

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
        fall_speed = max(100, INITIAL_FALL_SPEED - (level - 1) * SPEED_INCREASE_PER_LEVEL)

        # Soft drop hızlandırma
        if self.soft_dropping:
            fall_speed = min(fall_speed, FAST_FALL_SPEED)

        self.fall_timer += delta_time

        if self.fall_timer >= fall_speed:
            self.fall_timer = 0
            # Parçayı aşağı düşür
            if self.my_board and self.my_piece:
                if self.my_board.is_valid_position(self.my_piece, dy=1):
                    self.my_piece.y += 1
                    if self.soft_dropping:
                        self.my_board.score += 1
                    self.lock_timer = 0

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
        if self.state_snapshot_timer >= self.STATE_SNAPSHOT_INTERVAL:
            self.state_snapshot_timer = 0
            self._send_board_snapshot()

    def _lock_piece(self):
        """Parçayı kilitle, satır temizle, bekleyen çöpleri uygula, yeni parça al."""
        if not self.my_board or not self.my_piece:
            return

        lines = self.my_board.lock_piece(self.my_piece)

        try:
            self.sound.play('lock')
        except Exception:
            pass

        if lines > 0:
            # Temizlenen satırlar bekleyen çöpü iptal eder
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

        # Kalan bekleyen çöp satırları uygula (satır temizleme iptal edemediği kısım)
        if self.pending_garbage > 0:
            self._apply_pending_garbage()
            if self.game_over:
                return  # Garbage oyunu bitirdi

        # Yeni parça
        self.my_piece = self.my_next_piece
        self.my_next_piece = self._get_next_piece()
        self.next_piece = self.my_next_piece
        self.lock_timer = 0
        self.hold_used = False  # Yeni parçada hold tekrar kullanılabilir

        # Oyun bitti mi?
        if not self.my_board.is_valid_position(self.my_piece):
            self.game_over = True
            self.winner = 'opponent'
            self.online_state = OnlineState.GAME_OVER
            self.net.send_game_over(self.my_board.score, self.my_board.lines_cleared)
            try:
                self.sound.play('gameover')
            except Exception:
                pass

    def _update_das(self, delta_time: int):
        """DAS (Delayed Auto Shift) güncelle."""
        if self.das_direction == 0:
            self.das_timer = 0
            self.das_active = False
            return

        self.das_timer += delta_time
        if not self.das_active:
            if self.das_timer >= DAS_DELAY:
                self.das_active = True
                self.das_timer = 0
                self._move_horizontal(self.das_direction)
        else:
            if self.das_timer >= DAS_REPEAT:
                self.das_timer = 0
                self._move_horizontal(self.das_direction)

    def _move_horizontal(self, dx: int):
        """Parçayı yatay hareket ettir."""
        if self.my_board and self.my_piece:
            if self.my_board.is_valid_position(self.my_piece, dx=dx):
                self.my_piece.x += dx
                self.lock_timer = 0

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
                if self.online_state == OnlineState.PLAYING:
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

            if event.type == pygame.VIDEORESIZE:
                self.window_width = max(800, event.w)
                self.window_height = max(600, event.h)
                self.screen = create_display(self.window_width, self.window_height,
                                             fullscreen=self.fullscreen, resizable=True)
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
                    if ch.isdigit() and len(self._join_code_input) < 20:
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

        # Fullscreen toggle (F12 / Alt+Enter)
        if is_fullscreen_toggle(key, mods):
            return 'toggle_fullscreen'

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
                # Rakibe bildir
                if self.paused:
                    self.net.send({'type': MsgType.PAUSE_REQUEST},
                                 reliable=True, channel=CHANNEL_CONTROL)
                else:
                    self.net.send({'type': MsgType.RESUME},
                                 reliable=True, channel=CHANNEL_CONTROL)
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
                            self._join_code_input = digits[:20]
                            self._join_code_error = ''
                elif key == pygame.K_TAB:
                    self._join_code_active = False
                return None

            if key == pygame.K_1:
                if self._init_networking():
                    self.net.create_lobby()
            elif key == pygame.K_2:
                if self._init_networking():
                    self.net.create_lobby(public=True)
            elif key == pygame.K_3:
                if self._init_networking():
                    self._lobby_list_fetching = True
                    self._pending_lobby_list.clear()
                    self.net.request_lobby_list()
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
            elif key == pygame.K_c:
                self._copy_lobby_code()
            return None

        # Bekleme → Hazır
        if self.online_state == OnlineState.READY_CHECK:
            if key == pygame.K_RETURN:
                self.my_ready = True
                self.net.send_ready()
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
        if self.online_state == OnlineState.PLAYING and not self.game_over and not self.paused:
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
        if self.online_state == OnlineState.LOBBY_MENU and self._lobby_list:
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
                            self.net.create_lobby()
                    elif action == 'create_public':
                        if self._init_networking():
                            self.net.create_lobby(public=True)
                            # Otomatik lobi listesini de yenile (maç bul işlevi)
                            self._lobby_list_fetching = True
                            self._pending_lobby_list.clear()
                            self.net.request_lobby_list()
                    elif action == 'find_match':
                        if self._init_networking():
                            self._lobby_list_fetching = True
                            self._pending_lobby_list.clear()
                            self.net.request_lobby_list()
                    elif action == 'back':
                        return 'menu'
                    elif action == 'invite_friend':
                        self._do_invite_friend()
                    elif action == 'ready':
                        self.my_ready = True
                        self.net.send_ready()
                        self._check_both_ready()
                    elif action == 'rematch':
                        self._request_rematch()
                    elif action == 'exit_menu':
                        self.net.leave_lobby()
                        return 'menu'
                    elif action.startswith('join_lobby:'):
                        lobby_id_str = action.split(':', 1)[1]
                        try:
                            lobby_id = int(lobby_id_str)
                            self.net.join_lobby(lobby_id)
                        except (ValueError, TypeError):
                            pass
                    elif action == 'join_by_code':
                        # "Kod ile Katıl" butonuna tıklandı
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
                    self.lock_timer = 0
                    try:
                        self.sound.play('rotate')
                    except Exception:
                        pass
                    return
            # Hiçbiri çalışmadıysa geri al
            self.my_piece.rotate(-direction)
        else:
            self.lock_timer = 0
            try:
                self.sound.play('rotate')
            except Exception:
                pass

    def _hard_drop(self):
        """Sert düşüş — parçayı anında en alta indir ve kilitle."""
        if not self.my_board or not self.my_piece:
            return
        drop_distance = 0
        while self.my_board.is_valid_position(self.my_piece, dy=1):
            self.my_piece.y += 1
            drop_distance += 1
        self.my_board.score += drop_distance * 2
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
            self.net.create_lobby()
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
        if not invite_ok or sys.platform == 'win32':
            # Windows'ta C++ bridge overlay'ı düzgün açamayabiliyor
            # doğrudan Steam API çağrısı yap
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
        self.game_over = False
        self.winner = ''
        self.online_state = OnlineState.READY_CHECK
        # Rakibe rematch isteği bildir
        self.net.send({'type': MsgType.REMATCH}, reliable=True, channel=CHANNEL_CONTROL)
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

        if not self._init_networking():
            self._join_code_error = t('steam_not_available', 'Steam bağlantısı kurulamadı!')
            return

        # Her zaman 6 haneli kod olarak ara
        self._searching_by_code = True
        self._search_code = code
        self._lobby_list_fetching = True
        self._pending_lobby_list.clear()
        self.net.search_lobby_by_code(code)
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
        if not code and self.net.lobby_id:
            code = str(self.net.lobby_id)
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
        """Metni sistem panosuna kopyala — cross-platform."""
        import subprocess
        try:
            if sys.platform == 'win32':
                process = subprocess.Popen(
                    ['powershell', '-command', f'Set-Clipboard -Value "{text}"'],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
                try:
                    process.wait(timeout=2)
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
                process = subprocess.Popen(
                    ['xclip', '-selection', 'clipboard'],
                    stdin=subprocess.PIPE)
                try:
                    process.communicate(text.encode('utf-8'), timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                    return False
                return process.returncode == 0
        except Exception:
            return False

    def _paste_from_clipboard(self) -> str:
        """Sistem panosundan metin oku — cross-platform."""
        try:
            import subprocess
            if sys.platform == 'win32':
                result = subprocess.run(
                    ['powershell', '-command', 'Get-Clipboard'],
                    capture_output=True, text=True, timeout=2,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
                return result.stdout.strip()
            elif sys.platform == 'darwin':
                result = subprocess.run(
                    ['pbpaste'], capture_output=True, text=True, timeout=2)
                return result.stdout.strip()
            else:
                result = subprocess.run(
                    ['xclip', '-selection', 'clipboard', '-o'],
                    capture_output=True, text=True, timeout=2)
                return result.stdout.strip()
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
        _rs.draw_title(self.screen, t('online_pvp_title', 'ONLINE PvP'), (cx, s(58)))
        sub_font = _rs.get_font(s(16, minimum=11), bold=False)
        sub = sub_font.render(
            t('extras_online_pvp_desc', 'Steam üzerinden 1v1 online Tetris maçı'),
            True, _rs.text_secondary)
        self.screen.blit(sub, sub.get_rect(center=(cx, s(94))))

        # Sol panel: butonlar — modernize edilmiş yerleşim
        btn_w = s(340)
        btn_h = s(52)
        panel_left = max(s(30), cx - s(400))
        btn_x = panel_left
        btn_y_start = s(130)
        gap = s(12)

        # Özel Lobi bölümü başlığı
        section_font = _rs.get_font(s(13, minimum=10), bold=False)
        sec1 = section_font.render(t('private_lobby_section', '── Özel Lobi ──'),
                                   True, _rs.text_muted)
        self.screen.blit(sec1, sec1.get_rect(center=(btn_x + btn_w // 2, btn_y_start - s(8))))

        buttons_private = [
            ('create_private', t('create_private_lobby', 'Özel Lobi Oluştur'),
             _rs.primary, 'ENTER'),
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
            y_pos += s(130)

        # Herkese Açık Lobi bölümü başlığı
        y_pos += s(10)
        sec2 = section_font.render(t('public_lobby_section', '── Herkese Açık ──'),
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
        draw_glass_panel(self.screen, list_panel, alpha=150, border_color=(80, 120, 180))

        # Lobi listesi başlığı
        lt_font = _rs.get_font(s(20, minimum=14))
        list_title = lt_font.render(
            t('lobby_list_title', 'Mevcut Lobiler'), True, _rs.accent)
        self.screen.blit(list_title, list_title.get_rect(
            center=(list_x + list_w // 2, list_y + s(24))))

        # Başlık altı çizgi
        line_y = list_y + s(42)
        pygame.draw.line(self.screen, (*_rs.accent[:3], 60),
                         (list_x + s(12), line_y), (list_x + list_w - s(12), line_y), 1)

        content_top = list_y + s(50)

        if self._lobby_list_fetching:
            dots = '.' * (int(time.time() * 2) % 4)
            f_txt = _rs.get_font(s(16, minimum=11), bold=False).render(
                t('searching', 'Aranıyor') + dots, True, _rs.text_secondary)
            self.screen.blit(f_txt, f_txt.get_rect(
                center=(list_x + list_w // 2, list_y + list_h // 2)))
        elif not self._lobby_list:
            e_font = _rs.get_font(s(16, minimum=11), bold=False)
            e1 = e_font.render(t('no_lobbies_found', 'Lobi bulunamadı'), True, _rs.text_muted)
            e2 = _rs.get_font(s(14, minimum=10), bold=False).render(
                t('press_find_match', '"Maç Bul" ile arayın'), True, _rs.text_muted)
            self.screen.blit(e1, e1.get_rect(center=(list_x + list_w // 2, list_y + list_h // 2 - s(10))))
            self.screen.blit(e2, e2.get_rect(center=(list_x + list_w // 2, list_y + list_h // 2 + s(14))))
        else:
            item_h = s(72)
            visible = max(1, (list_h - s(70)) // item_h)
            start_idx = self._lobby_list_scroll
            clip = pygame.Rect(list_x + 4, content_top, list_w - 8, list_h - s(70))
            self.screen.set_clip(clip)

            for i, lobby in enumerate(self._lobby_list[start_idx:start_idx + visible]):
                iy = content_top + i * item_h
                ir = pygame.Rect(list_x + s(8), iy, list_w - s(16), item_h - s(6))
                hover = ir.collidepoint(mouse_pos)
                bdr = UIColors.NEON_CYAN if hover else (*_rs.glass_border[:3],)
                draw_glass_panel(self.screen, ir,
                                 alpha=190 if hover else 140, border_color=bdr)

                lname = lobby.get('name', f'Lobi #{i + start_idx + 1}')
                members = lobby.get('members', '?')
                mx = lobby.get('max_members', 2)
                lid = lobby.get('id', 0)
                l_code = lobby.get('code', '')

                # Lobi adı (host adı)
                nf = _rs.get_font(s(16, minimum=11))
                self.screen.blit(nf.render(lname, True, _rs.text_primary),
                                 (ir.x + s(12), ir.y + s(7)))

                # Detay satırı: üye sayısı + lobi kodu
                cf = _rs.get_font(s(12, minimum=9), bold=False)
                detail_parts = [f'{members}/{mx} oyuncu']
                if l_code:
                    detail_parts.append(f'Kod: {l_code}')
                detail_text = '  ·  '.join(detail_parts)
                self.screen.blit(cf.render(detail_text, True, _rs.text_secondary),
                                 (ir.x + s(12), ir.y + s(28)))

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
                                     (ir.x + s(12), ir.y + s(43)))

                # Katıl butonu — daha belirgin stil
                jw, jh = s(72), s(32)
                jb = pygame.Rect(ir.right - jw - s(10), ir.centery - jh // 2, jw, jh)
                jh_hover = jb.collidepoint(mouse_pos)
                _rs.draw_uniform_button(self.screen, jb,
                                        t('join', 'Katıl'),
                                        color_code=UIColors.NEON_GREEN,
                                        state='hover' if jh_hover else 'normal')
                self._lobby_buttons.append({'rect': jb, 'action': f'join_lobby:{lid}'})

            self.screen.set_clip(None)

            if len(self._lobby_list) > visible:
                sc_font = _rs.get_font(s(12, minimum=9), bold=False)
                sc_txt = sc_font.render(
                    f'{start_idx + 1}–{min(start_idx + visible, len(self._lobby_list))}'
                    f' / {len(self._lobby_list)}', True, _rs.text_muted)
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
        panel_h = s(120)
        panel_r = pygame.Rect(x, y, btn_w, panel_h)
        draw_glass_panel(self.screen, panel_r, alpha=190,
                         border_color=UIColors.NEON_CYAN, glow=True)

        # Başlık
        tf = _rs.get_font(s(16, minimum=11))
        title = tf.render(t('join_by_code', 'Kod ile Katıl'), True, UIColors.NEON_CYAN)
        self.screen.blit(title, title.get_rect(
            midleft=(x + s(14), y + s(18))))

        # Metin girişi arka planı
        inp_x = x + s(14)
        inp_y = y + s(38)
        inp_w = btn_w - s(28)
        inp_h = s(36)
        inp_rect = pygame.Rect(inp_x, inp_y, inp_w, inp_h)

        # Giriş alanı
        inp_bg = pygame.Surface((inp_w, inp_h), pygame.SRCALPHA)
        pygame.draw.rect(inp_bg, (18, 18, 42, 220), inp_bg.get_rect(), border_radius=8)
        self.screen.blit(inp_bg, (inp_x, inp_y))
        border_color = UIColors.NEON_CYAN if self._join_code_active else _rs.glass_border
        pygame.draw.rect(self.screen, border_color, inp_rect, 2, border_radius=8)

        # Metin
        display_text = self._join_code_input
        if not display_text and self._join_code_active:
            # Placeholder
            pf = _rs.get_font(s(15, minimum=11), bold=False)
            ph_txt = pf.render(
                t('enter_lobby_code', 'Lobi kodu girin'), True, _rs.text_muted)
            self.screen.blit(ph_txt, (inp_x + s(10), inp_y + s(8)))
        else:
            tf2 = _rs.get_font(s(16, minimum=12))
            t_surf = tf2.render(display_text, True, (255, 255, 255))
            self.screen.blit(t_surf, (inp_x + s(10), inp_y + s(8)))

        # İmleç yanıp sönme
        if self._join_code_active and int(time.time() * 2.5) % 2 == 0:
            cursor_x = inp_x + s(10) + _rs.get_font(s(16, minimum=12)).size(display_text)[0]
            pygame.draw.line(self.screen, UIColors.NEON_CYAN,
                             (cursor_x, inp_y + s(6)), (cursor_x, inp_y + inp_h - s(6)), 2)

        # Tıklanabilir alan olarak kaydet
        self._lobby_buttons.append({'rect': inp_rect, 'action': 'join_code_field'})

        # Hata mesajı
        if self._join_code_error:
            ef = _rs.get_font(s(12, minimum=9), bold=False)
            err = ef.render(self._join_code_error, True, UIColors.NEON_RED)
            self.screen.blit(err, (inp_x, inp_y + inp_h + s(4)))

        # Gönder butonu
        sub_btn_w = btn_w - s(28)
        sub_btn_h = s(34)
        sub_y = inp_y + inp_h + s(18)
        sub_rect = pygame.Rect(inp_x, sub_y, sub_btn_w, sub_btn_h)
        sub_hover = sub_rect.collidepoint(mouse_pos)
        _rs.draw_uniform_button(self.screen, sub_rect,
                                t('join', 'Katıl'),
                                sub_text='ENTER',
                                color_code=UIColors.NEON_GREEN,
                                state='hover' if sub_hover else 'normal')
        self._lobby_buttons.append({'rect': sub_rect, 'action': 'join_code_submit'})

        # Paste ipucu
        hint_f = _rs.get_font(s(11, minimum=9), bold=False)
        hint = hint_f.render(t('paste_code_hint', 'Yapıştır: Ctrl+V'), True, _rs.text_muted)
        self.screen.blit(hint, hint.get_rect(
            midright=(x + btn_w - s(14), y + s(18))))

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
        title = tf.render(t('waiting_for_opponent', 'Rakip Bekleniyor...'),
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
            label_s = label_f.render(t('lobby_code', 'Lobi Kodu'), True, _rs.text_secondary)
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
                                t('back_to_menu', 'Ana Menüye Dön'),
                                sub_text='ESC', color_code=_rs.secondary,
                                state='hover' if m_back else 'normal')
        self._lobby_buttons.append({'rect': back_rect, 'action': 'exit_menu'})

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
        vs = vs_font.render('VS', True, UIColors.NEON_MAGENTA)
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
            pt = pf.render('?', True, my_accent)
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
            pt = pf.render('?', True, opp_accent)
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
            rt = status_font.render('HAZIR', True, UIColors.NEON_GREEN)
            self.screen.blit(rt, rt.get_rect(center=ready_badge.center))
        else:
            wt = status_font.render(t('not_ready', 'Bekleniyor...'), True, _rs.text_muted)
            self.screen.blit(wt, wt.get_rect(center=(my_cx, status_y + s(12))))

        if self.opponent_ready:
            ready_badge2 = pygame.Rect(opp_cx - s(50), status_y, s(100), s(24))
            draw_glass_panel(self.screen, ready_badge2, alpha=180,
                             border_color=UIColors.NEON_GREEN)
            rt2 = status_font.render('HAZIR', True, UIColors.NEON_GREEN)
            self.screen.blit(rt2, rt2.get_rect(center=ready_badge2.center))
        else:
            wt2 = status_font.render(t('not_ready', 'Bekleniyor...'), True, _rs.text_muted)
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
            wt = wf.render(t('waiting_opponent_ready', 'Rakip bekleniyor...'),
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
            txt = big_font.render('GO!', True, UIColors.NEON_GREEN)

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

        # Layout hesapla
        cell_size = min((h - s(180)) // BOARD_HEIGHT, (w - s(260)) // (BOARD_WIDTH * 2 + 8))
        cell_size = max(s(14), min(cell_size, s(36)))
        board_w = BOARD_WIDTH * cell_size
        board_h = BOARD_HEIGHT * cell_size
        mini_cell = max(s(10), cell_size - 4)
        side_panel_w = mini_cell * 5 + s(24)
        gap = s(110)
        header_h = s(56)
        total = board_w * 2 + gap + side_panel_w
        start_x = max(s(10), (w - total) // 2)

        # Y pozisyonları — header dahil
        header_y = max(s(16), (h - board_h - header_h - s(60)) // 2)
        board_top = header_y + header_h + s(10)

        # ─ Sol yan panel: Hold + Next ─
        panel_x = start_x
        self._draw_side_panel(panel_x, board_top, cell_size)

        # ─ Sol tahta (ben) ─
        my_x = start_x + side_panel_w + s(10)
        self._draw_board(my_x, board_top, cell_size, self.my_board, self.my_piece)

        # Ghost piece
        if self.my_board and self.my_piece and not self.game_over:
            ghost_y = self._get_ghost_y()
            if ghost_y != self.my_piece.y:
                self._draw_ghost_piece(my_x, board_top, cell_size, ghost_y)

        # ─ Sağ tahta (rakip) ─
        opp_x = my_x + board_w + gap
        self._draw_opponent_board(opp_x, board_top, cell_size)

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
        vs_text = vs_font.render('VS', True, UIColors.NEON_MAGENTA)
        self.screen.blit(vs_text, vs_text.get_rect(center=vs_rect.center))

        # Pending garbage göstergesi (kırmızı bar)
        if self.pending_garbage > 0:
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

        # Hold
        hold_h = mini * 5 + s(40)
        hold_rect = pygame.Rect(panel_x, panel_y, pw, hold_h)
        draw_glass_panel(self.screen, hold_rect, alpha=150,
                         border_color=UIColors.NEON_CYAN)
        hf = _rs.get_font(s(15, minimum=10))
        hl = hf.render(t('hold', 'Hold'), True, UIColors.NEON_CYAN)
        self.screen.blit(hl, hl.get_rect(centerx=hold_rect.centerx, top=hold_rect.top + s(6)))

        if self.hold_piece:
            self._draw_mini_piece(self.hold_piece, hold_rect.centerx,
                                  hold_rect.top + s(30), mini)
        elif self.hold_used:
            lock_f = _rs.get_font(s(16, minimum=11))
            lk = lock_f.render('X', True, _rs.text_muted)
            self.screen.blit(lk, lk.get_rect(center=(hold_rect.centerx,
                                                       hold_rect.top + s(50))))

        # Next
        next_y = hold_rect.bottom + s(12)
        next_rect = pygame.Rect(panel_x, next_y, pw, hold_h)
        draw_glass_panel(self.screen, next_rect, alpha=150,
                         border_color=UIColors.NEON_CYAN)
        nl = hf.render(t('next', 'Sonraki'), True, UIColors.NEON_CYAN)
        self.screen.blit(nl, nl.get_rect(centerx=next_rect.centerx, top=next_rect.top + s(6)))
        if self.next_piece:
            self._draw_mini_piece(self.next_piece, next_rect.centerx,
                                  next_rect.top + s(30), mini)

    def _draw_mini_piece(self, piece, cx, top_y, mini):
        """Bir parçayı küçük boyutta ortalanmış çiz (hold/next için) — jelly stili."""
        shape = piece.get_shape() if hasattr(piece, 'get_shape') else piece.shape
        rows = len(shape)
        cols = len(shape[0]) if rows else 0
        ox = cx - (cols * mini) // 2
        oy = top_y
        for ri, row in enumerate(shape):
            for ci, cell in enumerate(row):
                if cell:
                    draw_jelly_block(self.screen,
                                     ox + ci * mini + 1, oy + ri * mini + 1,
                                     mini - 2, piece.color[:3])

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
        """Kendi tahtamızı çiz — jelly blok stili ile."""
        if not board:
            return

        board_w = BOARD_WIDTH * cell_size
        board_h = BOARD_HEIGHT * cell_size

        # Arka plan
        bg_rect = pygame.Rect(x - 2, y - 2, board_w + 4, board_h + 4)
        draw_glass_panel(self.screen, bg_rect, alpha=170)

        # Grid
        grid_color = (40, 40, 65)
        for row in range(BOARD_HEIGHT):
            for col in range(BOARD_WIDTH):
                cx = x + col * cell_size
                cy = y + row * cell_size
                color = board.grid[row][col]
                if color != BLACK:
                    draw_jelly_block(self.screen, cx + 1, cy + 1,
                                     cell_size - 2, color[:3])
                else:
                    pygame.draw.rect(self.screen, grid_color,
                                     (cx, cy, cell_size, cell_size), 1)

        # Aktif parça
        if piece:
            shape = piece.get_shape()
            for row_i, row in enumerate(shape):
                for col_i, cell in enumerate(row):
                    if cell:
                        px = x + (piece.x + col_i) * cell_size
                        py = y + (piece.y + row_i) * cell_size
                        if 0 <= piece.y + row_i < BOARD_HEIGHT:
                            draw_jelly_block(self.screen, px + 1, py + 1,
                                             cell_size - 2, piece.color[:3])

    def _draw_opponent_board(self, x: int, y: int, cell_size: int):
        """Ağdan gelen snapshot ile rakip tahtasını çiz — jelly blok stili."""
        board_w = BOARD_WIDTH * cell_size
        board_h = BOARD_HEIGHT * cell_size

        bg_rect = pygame.Rect(x - 2, y - 2, board_w + 4, board_h + 4)
        draw_glass_panel(self.screen, bg_rect, alpha=170)

        grid_color = (40, 40, 65)
        if self.opponent_grid_snapshot:
            for row in range(min(BOARD_HEIGHT, len(self.opponent_grid_snapshot))):
                for col in range(min(BOARD_WIDTH, len(self.opponent_grid_snapshot[row]))):
                    cx = x + col * cell_size
                    cy = y + row * cell_size
                    cell = self.opponent_grid_snapshot[row][col]
                    if cell is not None:
                        color = tuple(cell) if isinstance(cell, (list, tuple)) else (128, 128, 128)
                        draw_jelly_block(self.screen, cx + 1, cy + 1,
                                         cell_size - 2, color[:3])
                    else:
                        pygame.draw.rect(self.screen, grid_color,
                                         (cx, cy, cell_size, cell_size), 1)
        else:
            for row in range(BOARD_HEIGHT):
                for col in range(BOARD_WIDTH):
                    cx = x + col * cell_size
                    cy = y + row * cell_size
                    pygame.draw.rect(self.screen, grid_color,
                                     (cx, cy, cell_size, cell_size), 1)

    # ─── Game Over Overlay ───

    def _draw_game_over_overlay(self):
        w, h = self.window_width, self.window_height
        cx, cy = w // 2, h // 2
        sc = self._ui_scale()
        s = lambda v, minimum=1: self._sx(v, sc, minimum)

        # Karartma
        overlay = pygame.Surface((w, h), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 185))
        self.screen.blit(overlay, (0, 0))

        if self.winner == 'me':
            result_text = t('you_win', 'KAZANDIN!')
            result_color = UIColors.NEON_GREEN
            icon_text = '★'
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

        pw = min(s(540), w - s(80))
        ph = s(340)
        panel = pygame.Rect(cx - pw // 2, cy - ph // 2, pw, ph)

        # Ana panel — glow border
        draw_glass_panel(self.screen, panel, alpha=210,
                         border_color=(*result_color[:3], 180), glow=True)

        # İkon
        icon_font = _rs.get_font(s(48, minimum=30))
        icon_s = icon_font.render(icon_text, True, result_color)
        self.screen.blit(icon_s, icon_s.get_rect(center=(cx, panel.y + s(45))))

        # Sonuç başlığı — glow efektli
        tf = _rs.get_fitting_font(result_text, s(40), pw - s(60))
        ts = tf.render(result_text, True, result_color)
        # Glow katmanları
        for glow_offset in (3, 2, 1):
            glow_surf = pygame.Surface(ts.get_size(), pygame.SRCALPHA)
            glow_surf.fill((*result_color[:3], 18))
            glow_surf.blit(ts, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            self.screen.blit(glow_surf, glow_surf.get_rect(center=(cx + glow_offset, panel.y + s(100) + glow_offset)))
        self.screen.blit(ts, ts.get_rect(center=(cx, panel.y + s(100))))

        # Alt açıklama
        sub_f = _rs.get_font(s(15, minimum=11), bold=False)
        sub_s = sub_f.render(sub_text, True, _rs.text_secondary)
        self.screen.blit(sub_s, sub_s.get_rect(center=(cx, panel.y + s(135))))

        # Skor karşılaştırma paneli
        score_panel_y = panel.y + s(158)
        score_panel_h = s(50)
        score_panel_r = pygame.Rect(cx - s(180), score_panel_y, s(360), score_panel_h)
        draw_glass_panel(self.screen, score_panel_r, alpha=140,
                         border_color=_rs.glass_border)

        score_font = _rs.get_font(s(15, minimum=11), bold=False)
        my_name = self.net._get_name(self.net.my_steam_id) if self.net.my_steam_id else 'Sen'
        opp_name = self.net.opponent_name or t('opponent', 'Rakip')
        my_score = self.my_board.score if self.my_board else 0
        my_lines = self.my_board.lines_cleared if self.my_board else 0

        # Sol — benim skorumum
        my_txt = score_font.render(
            f'{my_name}: {my_score:,} · {my_lines} satır'.replace(',', '.'),
            True, UIColors.NEON_CYAN)
        self.screen.blit(my_txt, my_txt.get_rect(
            midleft=(score_panel_r.x + s(12), score_panel_r.centery)))

        # Sağ — rakip skoru
        opp_txt = score_font.render(
            f'{opp_name}: {self.opponent_score:,} · {self.opponent_lines} satır'.replace(',', '.'),
            True, UIColors.NEON_MAGENTA)
        self.screen.blit(opp_txt, opp_txt.get_rect(
            midright=(score_panel_r.right - s(12), score_panel_r.centery)))

        # Butonlar — daha belirgin stiller
        btn_w = s(140)
        btn_h = s(48)
        btn_gap = s(20)
        btn_y = panel.y + s(228)

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

        hint_f = _rs.get_font(s(12, minimum=9), bold=False)
        ht = hint_f.render('[R] Tekrar  ·  [ESC] Çıkış', True, _rs.text_muted)
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
        ts = tf.render(t('opponent_disconnected', 'Rakip Bağlantıyı Kesti'),
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

                delta_time = self.clock.tick(fps_limit if fps_limit > 0 else 60)

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
