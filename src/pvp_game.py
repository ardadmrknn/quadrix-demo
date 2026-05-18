"""PvP (2 Oyunculu) Mod"""
import pygame
import random
import math
import sys
import os
from pathlib import Path
from board import Board
from pieces import Piece, create_piece_by_index, SHAPES, get_piece_spawn_y, skip_hidden_rows
from constants import *
from sound import SoundManager
from background import BackgroundManager
from background_effects import get_shared_falling_blocks_layer
from mode_skins import apply_board_tint, apply_outer_tint, get_mode_skin
from retro_style import retro_style
from renderers.jelly_renderer import draw_jelly_block, draw_jelly_border
from themes import ThemeManager
from block_styles import BlockStyleManager, TextureSlice, TextureRenderCache
from platform_utils import create_display, get_display_flags, normalize_mouse_pos, get_mouse_pos, set_app_icon, resolve_frame_rate_cap
from localization import t, get_language
from gamepad_manager import is_gamepad_connected
from ui_scaling import get_projected_effective_scale
from ui_theme import UIColors, UIFonts
from effect_surface_cache import EffectSurfaceCache
from sweep_effects import SweepCatState, draw_rainbow_cat_sweep
from line_clear_feedback import (
    queue_wave_effects as _queue_wave_effects,
    update_wave_effects as _update_wave_effects,
    trigger_combo_burst as _trigger_combo_burst,
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
from combo_popup_style import (
    COMBO_POPUP_SHADOW_COLOR,
    get_combo_popup_alpha,
    get_combo_popup_color,
)
from screen_shake import (
    DEFAULT_SCREEN_SHAKE_DURATION_SECONDS,
    HARD_DROP_SCREEN_SHAKE_DURATION_SECONDS,
    HARD_DROP_SCREEN_SHAKE_INTENSITY,
    begin_screen_shake,
    sample_screen_shake_offset,
    step_screen_shake,
)

# Demobot'u yavaşlatmak için bu değeri artır, hızlandırmak için azalt.
DEMOBOT_ACTION_DELAY_MULTIPLIER = 2.5
LOCAL_PVP_RESULT_SCORE_POINTS = 1
LOCAL_PVP_RESULT_LINES_POINTS = 1
LOCAL_PVP_RESULT_BOARD_OPEN_POINTS = 2
LOCAL_PVP_RESULT_WIN_THRESHOLD = 3

try:
    from gamepad_manager import normalize_gamepad_event_button
except ImportError:
    def normalize_gamepad_event_button(event):
        button = getattr(event, 'button', None)
        if isinstance(button, (int, float)) and not isinstance(button, bool):
            return int(button)
        return None

def resource_path(relative_path):
    """PyInstaller ile derlenen exe için doğru path'i al"""
    try:
        base_path = Path(sys._MEIPASS)
    except Exception:
        base_path = Path(__file__).resolve().parents[1]
    return os.path.normpath(str(base_path / relative_path))


def _gp_btn(raw) -> int:
    if isinstance(raw, int):
        return raw
    if isinstance(raw, dict):
        value = raw.get('primary', -1)
        return int(value) if isinstance(value, (int, float)) else -1
    return -1


class PvPGame:
    """2 oyunculu PvP oyun sınıfı"""

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
        if getattr(self, 'paused', False):
            return False
        if getattr(self, 'game_over', False) or getattr(self, 'show_exit_prompt', False):
            return False
        if getattr(self, 'name_input_active', False):
            return False

        self.paused = True
        self.pause_menu_selected = 0
        if hasattr(self, 'sound') and self.sound:
            try:
                self.sound.duck_music()
            except Exception:
                pass
        return True

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

    def _sx(self, value: int | float, scale: float | None = None, minimum: int = 1) -> int:
        """Sabit piksel değerini UI ölçeğine göre dönüştür."""
        if scale is None:
            scale = self._ui_scale()
        return max(minimum, int(round(float(value) * float(scale))))

    @property
    def pause_menu_options(self):
        """Dil değiştiğinde dinamik güncellenen pause menü seçenekleri"""
        return list(self._pause_menu_keys)

    def wants_mouse_visible(self) -> bool:
        # Normal gameplay: gizli; pause / oyun sonu / isim ekranı gibi UI'de görünür.
        if getattr(self, 'show_exit_prompt', False):
            return True
        if getattr(self, 'paused', False):
            return True
        if getattr(self, 'game_over', False):
            return True
        if getattr(self, 'name_input_active', False):
            return True
        return False

    def _particle_effects_enabled(self) -> bool:
        if not getattr(self, 'effects_enabled', True):
            return False
        sm = getattr(self, 'settings_manager', None)
        if sm is None:
            return False
        helper = getattr(sm, 'particle_effects_enabled', None)
        if callable(helper):
            try:
                return bool(helper())
            except Exception:
                pass
        try:
            value = sm.get('particle_effects', False)
        except Exception:
            return False
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
            return 0.0
        helper = getattr(sm, 'get_particle_effects_multiplier', None)
        if callable(helper):
            try:
                return max(0.0, float(helper()))
            except Exception:
                pass
        try:
            value = sm.get('particle_effects', False)
        except Exception:
            return 0.0
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
    
    def __init__(
        self,
        sound_enabled=True,
        effects_enabled=True,
        screen=None,
        fullscreen=True,
        user_manager=None,
        settings_manager=None,
        sound_manager=None,
    ):
        """PvP oyunu başlat"""
        if not pygame.get_init():
            pygame.init()
        
        # User manager ve Settings manager
        self.user_manager = user_manager
        self.settings_manager = settings_manager
        self.pvp_controls = self._resolve_pvp_controls()
        
        # Eğer ekran verilmişse onu kullan, yoksa yeni oluştur
        if screen is not None:
            self.screen = screen
            self.window_width = screen.get_width()
            self.window_height = screen.get_height()
            self.fullscreen = True
        else:
            self.screen = create_display(0, 0, fullscreen=True, resizable=False, borderless=True)
            self.window_width = self.screen.get_width()
            self.window_height = self.screen.get_height()
            self.fullscreen = True
        
        try:
            pygame.display.set_caption('Quadrix')
        except Exception:
            pass
        try:
            import os
            _pvp_assets = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'assets')
            set_app_icon(_pvp_assets)
        except Exception:
            pass
        
        # Ses yöneticisi (menüden enjekte edilebilir)
        self.sound = sound_manager if sound_manager is not None else SoundManager()
        self.sound.enabled = True  # Müzik için her zaman açık
        self.sound.sfx_enabled = sound_enabled  # Ses efektleri ayarı
        if self.settings_manager:
            self.sound.music_enabled = self.settings_manager.get('music_enabled', True)
            self.sound.sfx_enabled = self.settings_manager.get('sound_enabled', sound_enabled)
            self.sound.set_music_volume(self.settings_manager.get('music_volume', 0.3))
            self.sound.set_volume(self.settings_manager.get('sfx_volume', 0.5))
        if hasattr(self.sound, 'unduck_music'):
            self.sound.unduck_music()
        self.current_music_track = None
        self.effects_enabled = effects_enabled
        self._start_pvp_music()
        
        # Arka plan yöneticileri
        self.background = BackgroundManager()  # Ana arka plan
        self.board_background = BackgroundManager()  # Quadrix alanları için ayrı arka plan
        
        # Ana arka planı tam opak yap (1.0 = %100 opak, transparanlık yok)
        self.background.set_transparency(1.0)
        
        # Board background'a ayarlardaki transparanlığı uygula
        if self.settings_manager:
            bg_transparency = self.settings_manager.get('bg_transparency', 0.3)
            self.board_background.set_transparency(bg_transparency)
        else:
            self.board_background.set_transparency(0.3)
        
        self.load_background_image()
        self.load_board_background()
        
        # Tema sistemi (tek oyunculu ile aynı)
        self.theme_manager = ThemeManager(self.settings_manager)
        self.mode_skin = get_mode_skin('pvp')

        # Blok stili / texture sistemi (tek oyunculu ile aynı temel)
        self.block_style_manager = BlockStyleManager(self.settings_manager) if self.settings_manager else None
        self._texture_render_cache = TextureRenderCache()
        
        # İki oyuncu
        self.board1 = Board()  # Oyuncu 1 (Sol - WASD)
        self.board2 = Board()  # Oyuncu 2 (Sağ - Ok tuşları)
        
        # Senkronize parçalar (her iki oyuncu aynı parçaları alır)
        self.piece_sequence = []
        self.current_piece_index = 0
        self.generate_pieces(100)  # 100 parça önceden oluştur
        
        # Oyuncu 1 parçaları
        self.current_piece1 = self.get_next_piece()
        skip_hidden_rows(self.current_piece1, self.board1)
        self.next_piece1 = self.get_next_piece()
        
        # Oyuncu 2 parçaları (aynı sıra)
        self.current_piece_index = 0  # Sıfırla
        self.current_piece2 = self.get_next_piece()
        skip_hidden_rows(self.current_piece2, self.board2)
        self.next_piece2 = self.get_next_piece()

        # Hold parçaları
        self.hold_piece1 = None
        self.hold_piece2 = None
        self.can_hold1 = True
        self.can_hold2 = True
        
        # Tema renklerini parçalara uygula
        self.apply_theme_to_pieces()
        
        # Oyun durumu
        self.game_over = False
        self.winner = None  # 1, 2, veya 'draw'
        self.paused = False

        # ESC ile çıkış onayı (tek oyunculu ile aynı davranış)
        self.show_exit_prompt = False
        self.exit_yes_rect: pygame.Rect | None = None
        self.exit_no_rect: pygame.Rect | None = None

        # PvP maç modu: 'timed' (süreli) veya 'endless' (süresiz)
        self.match_mode = 'timed'  # Varsayılan: süreli
        self.custom_duration_minutes = 2  # Kullanıcının seçtiği süre (dakika)
        self.match_duration_ms = self.custom_duration_minutes * 60 * 1000
        self.match_elapsed_ms = 0
        self.match_active = False
        self.match_end_reason: str | None = None  # 'time' | 'elimination' | None
        self._last_timer_seconds: int | None = None

        # Eleme durumu: spawn edemeyen (veya top-out olan) oyuncu elenir
        self.p1_eliminated = False
        self.p2_eliminated = False

        # Duraklama menüsü (tek oyunculu ile aynı)
        self.pause_menu_selected = 0
        self._pause_menu_keys = ['resume', 'settings', 'music', 'music_volume', 'sound_effects', 'sfx_volume', 'main_menu']
        self._pause_option_rects: list[pygame.Rect] = []
        self._pause_volume_rects: dict[str, pygame.Rect] = {}
        self._pause_vol_drag_active: bool = False
        self._pause_vol_drag_option: str = ''
        self._pause_settings_active = False
        self._pause_settings_screen = None
        
        # Game over ekranı buton rect'leri (mouse desteği için)
        self._game_over_restart_rect: pygame.Rect | None = None
        self._game_over_menu_rect: pygame.Rect | None = None
        
        # Oyuncu isimleri
        self.player1_name = ""
        self.player2_name = ""
        self.name_input_active = True  # İsim girişi ekranı
        self.current_input = 1  # Hangi oyuncunun ismini giriyoruz (1 veya 2, 3=mod seçimi, 4=süre ayarı)
        
        # Zamanlama - Her oyuncu için ayrı hız
        self.fall_time1 = 0
        self.fall_time2 = 0
        self.fall_speed1 = 900  # Oyuncu 1 sabit hız
        self.fall_speed2 = 900  # Oyuncu 2 sabit hız
        self.lock_delay = DEFAULT_LOCK_DELAY
        self.enable_lock_delay = True
        self.p1_grounded = False
        self.p2_grounded = False
        self.p1_lock_timer = 0.0
        self.p2_lock_timer = 0.0
        self.speed_increase_per_milestone = 0  # Hızlanma yok
        self.min_fall_speed = 900  # Sabit hız
        
        # Fontlar
        self.font_large = UIFonts.get(72)
        self.font_vs = UIFonts.get(120)  # VS için çok büyük font
        self.font_medium = UIFonts.get(36)
        self.font_small = UIFonts.get(24)
        
        # Partiküller
        self.particles = []

        # Satır temizleme efekt sistemi (ana oyundaki gibi gelişmiş)
        self.p1_line_flash_rows = []
        self.p2_line_flash_rows = []
        self.p1_line_flash_timer = 0  # Frame bazlı timer
        self.p2_line_flash_timer = 0
        self.p1_line_glow_alpha = 0
        self.p2_line_glow_alpha = 0
        self.p1_wave_effects = []  # Dalga efektleri
        self.p2_wave_effects = []
        self.p1_line_sweep_rows = []
        self.p1_line_sweep_progress = 0.0
        self.p1_line_sweep_active = False
        self.p2_line_sweep_rows = []
        self.p2_line_sweep_progress = 0.0
        self.p2_line_sweep_active = False
        # Pending row snapshot: clear_lines() satırları anında siler; sweep
        # ön kenarına kadar görünür kalmaları için renk snapshot'ı tutuluyor
        # (Mystery / Game / Coop ile parity).
        self.p1_line_pending_rows: list[int] = []
        self.p1_line_pending_colors: dict[int, list[tuple[int, int, int]]] = {}
        self.p2_line_pending_rows: list[int] = []
        self.p2_line_pending_colors: dict[int, list[tuple[int, int, int]]] = {}
        self.p1_falling_block_animations = []
        self.p2_falling_block_animations = []
        self.p1_drop_trails = []
        self.p2_drop_trails = []
        self.block_fall_speed = 0.12
        
        # Combo mesaj sistemi (DOUBLE/TRIPLE/QUADRIX gösterimi)
        self.p1_combo_message = ""
        self.p1_combo_message_time = 0
        self.p2_combo_message = ""
        self.p2_combo_message_time = 0
        
        # Arka plan parçacıkları (ambient effect)
        self.ambient_particles = []
        self.create_ambient_particles()

        # İsim giriş ekranı için arka plan tetris blokları efekti
        self.name_background_fx = get_shared_falling_blocks_layer('default') if self.effects_enabled else None
        
        # Screen shake efekti
        self.screen_shake = 0.0
        self.shake_intensity = 0
        self._screen_shake_initial = 0.0
        
        # Havai fişek sistemi (her 1000 puan) - Her oyuncu için ayrı
        self.p1_last_milestone = 0
        self.p2_last_milestone = 0
        self.p1_firework_active = False
        self.p2_firework_active = False
        self.p1_firework_time = 0
        self.p2_firework_time = 0
        
        # DAS (Delayed Auto Shift) - Her oyuncu için ayrı
        # Oyuncu 1
        self.p1_das_direction = 0  # -1: sol, 0: yok, 1: sağ
        self.p1_das_timer = 0
        self.p1_das_repeat_timer = 0
        self.p1_das_charged = False
        # Oyuncu 2
        self.p2_das_direction = 0
        self.p2_das_timer = 0
        self.p2_das_repeat_timer = 0
        self.p2_das_charged = False
        
        # Soft drop (hızlı düşüş) - Her oyuncu için ayrı
        self.p1_soft_drop_active = False
        self.p1_soft_drop_timer = 0
        self.p2_soft_drop_active = False
        self.p2_soft_drop_timer = 0
        self.soft_drop_speed = 50  # Soft drop hızı (ms)

        # Debug-only local PvP demobot state
        self._demobot_plan = None
        self._demobot_piece_ref = None
        self._demobot_action_timer = 0.0
        self._demobot_active_last_frame = False
        
        # Oyun alanı pozisyonları (parçacıklar için)
        self.cell_size = 50
        self._base_center_panel_width = 92
        self.center_panel_width = 92
        self._base_header_height = 64
        self.header_height = 64
        self._base_header_top = 28
        self.header_top = 28
        self.board_top = 120
        self._base_board_gap = 24
        self.board_gap = 24
        self._base_preview_panel_width = 108
        self.preview_panel_width = 108
        self._base_preview_panel_gap = 8
        self.preview_panel_gap = 8
        self._base_center_panel_gap = 12
        self.center_panel_gap = 12
        self.p1_preview_x = 0
        self.p2_preview_x = 0
        self.center_panel_x = 0
        self._layout_key = None
        self._board_grid_cache = {'key': None, 'surface': None}

        # Kilitli blokları cache'le (her frame tüm grid'i çizme maliyetini azalt)
        self._locked_board_cache = {
            1: {'key': None, 'surface': None, 'dirty': True},
            2: {'key': None, 'surface': None, 'dirty': True},
        }

        # Ambient particle sprite cache (surface allocation azalt)
        self._ambient_sprite_cache = {}
        self._effect_surface_cache = EffectSurfaceCache()
        self._sweep_cat_state = SweepCatState()

        # PvP draw cache (surface allocation azalt)
        self._board_accent_overlay_cache = {}
        self.calculate_board_positions()
        
        self._vs_panel_surface = None
        self._vs_panel_dirty = True
    
    def apply_theme_to_pieces(self):
        """Tema + blok stili görünümünü mevcut parçalara uygula (ana oyun temeli)."""
        for piece in (
            self.current_piece1,
            self.next_piece1,
            self.hold_piece1,
            self.current_piece2,
            self.next_piece2,
            self.hold_piece2,
        ):
            self._apply_block_style(piece)

    def _apply_block_style(self, piece):
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
            # Texture sistemi yoksa garantiye al
            piece.texture_path = None
            piece.texture_surface = None
            piece.texture_surface_original = None
    
    def _find_closest_theme_color(self, color):
        """Bir rengi en yakın tema rengine eşleştir"""
        if not self.theme_manager:
            return color
        
        # Tüm parça renklerini al
        theme_colors = {
            self.theme_manager.get_piece_color('I'),
            self.theme_manager.get_piece_color('O'),
            self.theme_manager.get_piece_color('T'),
            self.theme_manager.get_piece_color('S'),
            self.theme_manager.get_piece_color('Z'),
            self.theme_manager.get_piece_color('J'),
            self.theme_manager.get_piece_color('L')
        }
        
        # En yakın rengi bul
        min_distance = float('inf')
        closest_color = color
        for theme_color in theme_colors:
            distance = sum((a - b) ** 2 for a, b in zip(color[:3], theme_color[:3]))
            if distance < min_distance:
                min_distance = distance
                closest_color = theme_color
        
        return closest_color

    def _mark_locked_board_dirty(self, player: int) -> None:
        cache = self._locked_board_cache.get(player)
        if cache is not None:
            cache['dirty'] = True

    def _start_block_fall_animation(self, player: int, board: Board, cleared_rows: list[int]) -> None:
        if not cleared_rows:
            return
        animations = []
        lines_count = len(cleared_rows)
        cell_size = self.cell_size
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
        if player == 1:
            self.p1_falling_block_animations = animations
        else:
            self.p2_falling_block_animations = animations

    def _get_block_fall_offset(self, player: int, row: int, col: int) -> float:
        animations = self.p1_falling_block_animations if player == 1 else self.p2_falling_block_animations
        for anim in animations:
            if anim['row'] == row and anim['col'] == col:
                return anim['current_offset']
        return 0

    def _get_ambient_sprite(self, radius: int, alpha: int, glow: bool) -> pygame.Surface:
        """Create/reuse small cached circle sprites for ambient particles."""
        radius = max(1, int(radius))
        alpha = int(max(0, min(255, int(alpha))))
        alpha_bucket = int(alpha // 16) * 16
        key = (radius, alpha_bucket, 1 if glow else 0)
        cached = self._ambient_sprite_cache.get(key)
        if cached is not None:
            return cached

        size = radius * (4 if glow else 2)
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        center = (size // 2, size // 2)
        color = (200, 200, 255, alpha_bucket)
        pygame.draw.circle(surf, color, center, radius * (2 if glow else 1))
        self._ambient_sprite_cache[key] = surf
        return surf

    def _resolve_pvp_controls(self):
        defaults = {
            'player1': {
                'move_left': pygame.K_a,
                'move_right': pygame.K_d,
                'soft_drop': pygame.K_s,
                'hard_drop': pygame.K_LSHIFT,
                'rotate': pygame.K_w,
                'hold': pygame.K_LCTRL,
            },
            'player2': {
                'move_left': pygame.K_LEFT,
                'move_right': pygame.K_RIGHT,
                'soft_drop': pygame.K_DOWN,
                'hard_drop': pygame.K_SPACE,
                'rotate': pygame.K_UP,
                'hold': pygame.K_RCTRL,
            },
            'pause': pygame.K_p,
        }
        if not self.settings_manager:
            return defaults
        controls = self.settings_manager.get_controls()
        pvp_config = controls.get('pvp', {}) if isinstance(controls, dict) else {}
        resolved = {
            'player1': {},
            'player2': {},
        }
        for player in ('player1', 'player2'):
            player_cfg = pvp_config.get(player, {}) if isinstance(pvp_config, dict) else {}
            resolved[player] = {
                action: self._binding_to_keycode(player_cfg.get(action), defaults[player][action])
                for action in defaults[player]
            }
        single_cfg = controls.get('single_player', {}) if isinstance(controls, dict) else {}
        resolved['pause'] = self._binding_to_keycode(single_cfg.get('pause'), defaults['pause'])
        return resolved

    @staticmethod
    def _binding_to_keycode(binding, fallback):
        if isinstance(binding, int):
            return binding
        if isinstance(binding, str):
            try:
                return pygame.key.key_code(binding)
            except ValueError:
                return fallback
        return fallback

    def _ensure_pause_settings_screen(self):
        pause_settings = getattr(self, '_pause_settings_screen', None)
        if pause_settings is not None:
            pause_settings.screen = self.screen
            return pause_settings

        try:
            try:
                from settings_screen_tabbed import TabbedSettingsScreen
            except Exception:
                from .settings_screen_tabbed import TabbedSettingsScreen  # type: ignore
            pause_settings = TabbedSettingsScreen(
                self.screen,
                getattr(self, 'theme_manager', None),
                getattr(self, 'settings_manager', None),
                getattr(self, 'sound', None),
            )
        except Exception:
            return None

        self._pause_settings_screen = pause_settings
        return pause_settings

    def _sync_runtime_settings_from_manager(self):
        settings_manager = getattr(self, 'settings_manager', None)
        if settings_manager is None:
            return

        sound = getattr(self, 'sound', None)
        if sound is not None:
            try:
                sound.music_enabled = bool(settings_manager.get('music_enabled', getattr(sound, 'music_enabled', True)))
            except Exception:
                pass
            try:
                sound.sfx_enabled = bool(settings_manager.get('sound_enabled', getattr(sound, 'sfx_enabled', True)))
            except Exception:
                pass
            try:
                sound.set_music_volume(float(settings_manager.get('music_volume', getattr(sound, 'music_volume', 0.3))))
            except Exception:
                pass
            try:
                sound.set_volume(float(settings_manager.get('sfx_volume', getattr(sound, 'sfx_volume', 0.5))))
            except Exception:
                pass
            if hasattr(sound, 'set_muted'):
                try:
                    sound.set_muted(bool(settings_manager.get('mute_all', False)))
                except Exception:
                    pass
            try:
                if sound.music_enabled:
                    if not pygame.mixer.music.get_busy():
                        self._start_pvp_music()
                else:
                    sound.stop_music()
            except Exception:
                pass

        self.sound_enabled = bool(getattr(sound, 'sfx_enabled', getattr(self, 'sound_enabled', True)))
        try:
            self.effects_enabled = bool(settings_manager.get('effects_enabled', getattr(self, 'effects_enabled', True)))
        except Exception:
            pass

        try:
            self.pvp_controls = self._resolve_pvp_controls()
        except Exception:
            pass

        theme_manager = getattr(self, 'theme_manager', None)
        if theme_manager is not None:
            try:
                theme_manager.set_theme(settings_manager.get('theme', settings_manager.get('active_theme', 'Classic')))
            except Exception:
                pass

        try:
            self.apply_theme_to_pieces()
        except Exception:
            pass

        try:
            bg_transparency = float(settings_manager.get('bg_transparency', 0.3))
        except Exception:
            bg_transparency = 0.3
        try:
            menu_transparency = float(settings_manager.get('menu_transparency', 1.0))
        except Exception:
            menu_transparency = None

        if bg_transparency is not None:
            try:
                retro_style.set_background_transparency(bg_transparency)
            except Exception:
                pass
        if menu_transparency is not None:
            try:
                retro_style.set_menu_transparency(menu_transparency)
            except Exception:
                pass

        for attr_name in ('background', 'board_background', 'outer_background'):
            background = getattr(self, attr_name, None)
            if background is None:
                continue
            if hasattr(background, 'enabled'):
                try:
                    background.enabled = True
                except Exception:
                    pass
        if bg_transparency is not None:
            try:
                self.update_transparency(bg_transparency)
            except Exception:
                pass

        self.name_background_fx = get_shared_falling_blocks_layer('default') if getattr(self, 'effects_enabled', True) else None
        if self.name_background_fx is not None:
            try:
                eff_opacity = float(settings_manager.get('effects_opacity', 1.0))
                self.name_background_fx.set_opacity_multiplier(eff_opacity)
                self.effects_opacity = eff_opacity
            except Exception:
                pass
        self._layout_key = None
        self._vs_panel_dirty = True
        try:
            self.calculate_board_positions()
        except Exception:
            pass

        pause_settings = getattr(self, '_pause_settings_screen', None)
        if pause_settings is not None:
            pause_settings.screen = self.screen

    def _open_pause_settings(self):
        pause_settings = self._ensure_pause_settings_screen()
        if pause_settings is None:
            return
        pause_settings.screen = self.screen
        try:
            pause_settings.sync_from_settings_manager()
        except Exception:
            pass
        self._pause_settings_active = True

    def _close_pause_settings(self):
        self._pause_settings_active = False
        self._sync_runtime_settings_from_manager()

    def _handle_pause_settings_input(self, event):
        if not getattr(self, '_pause_settings_active', False):
            return None

        event_button = normalize_gamepad_event_button(event)
        if event_button is not None:
            try:
                gp_cfg = self.settings_manager.get_controls().get('gamepad', {})
                if event_button == _gp_btn(gp_cfg.get('menu_back', 1)):
                    self._close_pause_settings()
                    return None
            except Exception:
                pass

        pause_settings = self._ensure_pause_settings_screen()
        if pause_settings is None:
            self._pause_settings_active = False
            return None

        pause_settings.screen = self.screen
        action = pause_settings.handle_input(event)
        if action == 'back':
            self._close_pause_settings()
            return None
        if action in ('quit_game', 'restart_now'):
            self._close_pause_settings()
            return None
        if action:
            self._sync_runtime_settings_from_manager()
        return None

    @staticmethod
    def _key_label(key_code):
        try:
            return pygame.key.name(key_code).upper()
        except ValueError:
            return str(key_code)

    @staticmethod
    def _normalize_preview_label(key: str, fallback: str) -> str:
        try:
            raw = t(key, fallback)
        except Exception:
            raw = fallback
        normalized = str(raw).strip().replace('\n', ' ')
        return normalized.upper() if normalized else fallback.upper()

    def _hold_preview_label(self, player: int) -> str:
        controls_key = 'player1' if player == 1 else 'player2'
        hold_key = self.pvp_controls.get(controls_key, {}).get('hold')
        key_label = self._key_label(hold_key) if hold_key is not None else '?'
        compact_label = (
            str(key_label)
            .replace('LEFT ', 'L')
            .replace('RIGHT ', 'R')
            .replace('CONTROL', 'CTRL')
            .replace('RETURN', 'ENTER')
            .replace('KP_ENTER', 'ENTER')
        )
        return t('pvp_hold_preview_label', default='Saklanan:{binding}', binding=compact_label)

    def _reset_piece_to_spawn(self, piece, board):
        if piece is None:
            return None

        spawned = piece.copy() if hasattr(piece, 'copy') else piece
        try:
            rotation_state = int(getattr(spawned, 'rotation_state', 0) or 0) % 4
        except Exception:
            rotation_state = 0
        if rotation_state:
            for _ in range((4 - rotation_state) % 4):
                spawned.rotate()
        spawned.x = BOARD_WIDTH // 2 - len(spawned.shape[0]) // 2
        spawned.y = get_piece_spawn_y(spawned)
        skip_hidden_rows(spawned, board)
        self._apply_block_style(spawned)
        return spawned

    def _eliminate_player(self, player: int) -> None:
        self._reset_lock_delay_state(player)
        if player == 1:
            self.p1_eliminated = True
        else:
            self.p2_eliminated = True
        self.match_end_reason = 'elimination'
        self.determine_winner()

    def _try_hold_piece(self, player: int) -> bool:
        if self.game_over or self.paused:
            return False

        if player == 1:
            board = self.board1
            current_piece = self.current_piece1
            next_piece = self.next_piece1
            hold_piece = self.hold_piece1
            can_hold = self.can_hold1
        else:
            board = self.board2
            current_piece = self.current_piece2
            next_piece = self.next_piece2
            hold_piece = self.hold_piece2
            can_hold = self.can_hold2

        if current_piece is None or not can_hold:
            return False

        stored_hold = self._reset_piece_to_spawn(current_piece, board)
        if hold_piece is None:
            new_current = next_piece
            new_next = self.get_next_piece()
        else:
            new_current = hold_piece
            new_next = next_piece

        new_current = self._reset_piece_to_spawn(new_current, board)
        if new_next is not None:
            self._apply_block_style(new_next)

        if new_current is None or not board.is_valid_position(new_current):
            self._eliminate_player(player)
            return False

        if player == 1:
            self.hold_piece1 = stored_hold
            self.current_piece1 = new_current
            self.next_piece1 = new_next
            self.can_hold1 = False
        else:
            self.hold_piece2 = stored_hold
            self.current_piece2 = new_current
            self.next_piece2 = new_next
            self.can_hold2 = False

        self._reset_lock_delay_state(player)
        self._vs_panel_dirty = True
        try:
            self.sound.play('swap')
        except Exception:
            self.sound.play('move')
        return True

    def _is_local_pvp_demobot_debug_enabled(self) -> bool:
        try:
            return bool(self.settings_manager and self.settings_manager.get('local_pvp_demobot_debug', False))
        except Exception:
            return False

    @staticmethod
    def _is_demobot_name(name) -> bool:
        return str(name or '').strip().lower() == 'demobot'

    def _is_player1_demobot_active(self) -> bool:
        return (
            self._is_local_pvp_demobot_debug_enabled()
            and self._is_demobot_name(getattr(self, 'player1_name', ''))
            and not getattr(self, 'name_input_active', False)
            and not getattr(self, 'paused', False)
            and not getattr(self, 'game_over', False)
        )

    def _clear_demobot_state(self) -> None:
        self._demobot_plan = None
        self._demobot_piece_ref = None
        self._demobot_action_timer = 0.0

    def _cancel_p1_manual_input_state(self) -> None:
        self.p1_das_direction = 0
        self.p1_das_timer = 0
        self.p1_das_repeat_timer = 0
        self.p1_das_charged = False
        self.p1_soft_drop_active = False
        self.p1_soft_drop_timer = 0

    @staticmethod
    def _column_heights_for_board(board: Board) -> list[int]:
        heights: list[int] = []
        for x in range(board.width):
            height = 0
            for y in range(board.height):
                if board.occupancy[y][x]:
                    height = board.height - y
                    break
            heights.append(height)
        return heights

    def _demobot_stack_pressure(self, board: Board) -> int:
        heights = self._column_heights_for_board(board)
        return max(0, (max(heights) if heights else 0) - 10)

    def _demobot_next_action_delay(self, action: str) -> float:
        ranges = {
            'think': (170.0, 250.0),
            'move': (58.0, 98.0),
            'rotate': (72.0, 118.0),
            'hold': (110.0, 170.0),
            'soft_drop': (34.0, 58.0),
            'hard_drop': (90.0, 145.0),
        }
        minimums = {
            'think': 90.0,
            'move': 32.0,
            'rotate': 42.0,
            'hold': 74.0,
            'soft_drop': 22.0,
            'hard_drop': 52.0,
        }
        low, high = ranges.get(action, (60.0, 100.0))
        delay_multiplier = max(0.25, float(DEMOBOT_ACTION_DELAY_MULTIPLIER))
        low *= delay_multiplier
        high *= delay_multiplier
        reduction = min(85.0, self._demobot_stack_pressure(self.board1) * 9.0)
        return max(minimums.get(action, 30.0) * delay_multiplier, random.uniform(low, high) - reduction)

    @staticmethod
    def _clone_board_for_demobot(board: Board) -> Board:
        sim_board = Board(width=board.width, height=board.height)
        sim_board.grid = [row[:] for row in board.grid]
        sim_board.texture_grid = [row[:] for row in board.texture_grid]
        sim_board.owners = [row[:] for row in board.owners]
        sim_board.occupancy = [row[:] for row in board.occupancy]
        sim_board.gold = [row[:] for row in board.gold]
        sim_board.score = int(getattr(board, 'score', 0) or 0)
        sim_board.lines_cleared = int(getattr(board, 'lines_cleared', 0) or 0)
        sim_board.level_lines_cleared = int(getattr(board, 'level_lines_cleared', 0) or 0)
        sim_board.level = int(getattr(board, 'level', 1) or 1)
        sim_board.combo = int(getattr(board, 'combo', 0) or 0)
        sim_board.tetrises = int(getattr(board, 'tetrises', 0) or 0)
        sim_board.last_cleared_lines = list(getattr(board, 'last_cleared_lines', []))
        sim_board.last_cleared_colors = dict(getattr(board, 'last_cleared_colors', {}))
        sim_board.flexible_border_active = bool(getattr(board, 'flexible_border_active', False))
        sim_board.back_to_back = bool(getattr(board, 'back_to_back', False))
        return sim_board

    @staticmethod
    def _measure_drop_distance(board: Board, piece) -> int:
        test_piece = piece.copy() if hasattr(piece, 'copy') else piece
        distance = 0
        while board.is_valid_position(test_piece, dy=1):
            test_piece.y += 1
            distance += 1
        return distance

    def _score_demobot_board(self, board: Board, lines_cleared: int) -> float:
        heights = self._column_heights_for_board(board)
        aggregate_height = float(sum(heights))
        max_height = float(max(heights) if heights else 0)
        bumpiness = float(sum(abs(a - b) for a, b in zip(heights, heights[1:])))

        holes = 0
        for x in range(board.width):
            filled_seen = False
            for y in range(board.height):
                if board.occupancy[y][x]:
                    filled_seen = True
                elif filled_seen:
                    holes += 1

        row_fill_score = 0.0
        height_scale = max(1, board.height - 1)
        for y, row in enumerate(board.occupancy):
            filled = sum(1 for cell in row if cell)
            if filled:
                depth_weight = 1.0 + (float(y) / float(height_scale)) * 0.35
                row_fill_score += float(filled * filled) * depth_weight

        danger = max(0.0, max_height - (board.height * 0.55))
        return (
            float(lines_cleared) * 1500.0
            + row_fill_score * 2.6
            - aggregate_height * 18.0
            - float(holes) * 230.0
            - bumpiness * 14.0
            - max_height * 32.0
            - (danger * danger) * 18.0
        )

    def _evaluate_demobot_piece_option(self, piece) -> dict | None:
        if piece is None:
            return None

        board = self.board1
        best_plan = None
        working_piece = piece.copy() if hasattr(piece, 'copy') else piece
        seen_shapes: set[tuple[tuple[int, ...], ...]] = set()

        for _ in range(4):
            shape_signature = tuple(tuple(int(cell) for cell in row) for row in working_piece.shape)
            if shape_signature not in seen_shapes:
                seen_shapes.add(shape_signature)
                for target_x in range(-2, board.width + 2):
                    candidate = working_piece.copy() if hasattr(working_piece, 'copy') else working_piece
                    candidate.x = target_x
                    if not board.is_valid_position(candidate):
                        continue

                    drop_distance = self._measure_drop_distance(board, candidate)
                    landing_piece = candidate.copy() if hasattr(candidate, 'copy') else candidate
                    landing_piece.y += drop_distance

                    sim_board = self._clone_board_for_demobot(board)
                    lines_cleared = sim_board.lock_piece(landing_piece)
                    score = self._score_demobot_board(sim_board, lines_cleared)
                    if sim_board.is_game_over():
                        score -= 100000.0

                    plan = {
                        'target_x': int(candidate.x),
                        'target_rotation': int(getattr(candidate, 'rotation_state', 0) or 0) % 4,
                        'score': float(score),
                        'lines_cleared': int(lines_cleared),
                        'soft_drop_steps_remaining': min(3, max(0, (int(drop_distance) - 8) // 4)),
                        'use_hold': False,
                    }
                    if best_plan is None or float(plan['score']) > float(best_plan['score']):
                        best_plan = plan

            working_piece.rotate()

        return best_plan

    def _build_demobot_plan(self) -> dict | None:
        best_plan = self._evaluate_demobot_piece_option(self.current_piece1)

        if self.can_hold1:
            hold_candidate = self.hold_piece1 if self.hold_piece1 is not None else self.next_piece1
            if hold_candidate is not None:
                spawned_hold = self._reset_piece_to_spawn(hold_candidate, self.board1)
                hold_plan = self._evaluate_demobot_piece_option(spawned_hold)
                if hold_plan is not None:
                    hold_plan = dict(hold_plan)
                    hold_plan['use_hold'] = True
                    hold_margin = 80.0 if self.hold_piece1 is not None else 160.0
                    if (
                        best_plan is None
                        or int(hold_plan['lines_cleared']) > int(best_plan.get('lines_cleared', 0))
                        or float(hold_plan['score']) > float(best_plan.get('score', 0.0)) + hold_margin
                    ):
                        best_plan = hold_plan

        return best_plan

    def _try_rotate_p1(self) -> bool:
        if self.current_piece1 is None or self.board1.is_game_over():
            return False

        original_x = self.current_piece1.x
        self.current_piece1.rotate()
        if not self.board1.is_valid_position(self.current_piece1):
            for dx in [1, -1, 2, -2]:
                self.current_piece1.x = original_x + dx
                if self.board1.is_valid_position(self.current_piece1):
                    break
            else:
                self.current_piece1.x = original_x
                for _ in range(3):
                    self.current_piece1.rotate()
                return False

        self.sound.play('rotate')
        return True

    def _try_soft_drop_step_p1(self) -> bool:
        if self.current_piece1 is None or self.board1.is_game_over():
            return False

        self.current_piece1.y += 1
        if not self.board1.is_valid_position(self.current_piece1):
            self.current_piece1.y -= 1
            self._mark_player_grounded(1)
            return True
        self._reset_lock_delay_state(1)
        return True

    def _hard_drop_p1(self) -> bool:
        if self.current_piece1 is None or self.board1.is_game_over():
            return False

        start_y = self.current_piece1.y
        drop_distance = 0
        while self.board1.is_valid_position(self.current_piece1, dy=1):
            self.current_piece1.y += 1
            drop_distance += 1

        if self.effects_enabled and drop_distance > 0:
            self._create_drop_trail(
                1,
                self.current_piece1,
                self.p1_offset_x,
                self.p1_offset_y,
                self.cell_size,
                start_y,
                drop_distance,
                trail_type='hard',
            )

        if self.effects_enabled and drop_distance > 0:
            self.trigger_hard_drop_screen_shake()

        self.lock_and_new_piece(1)

        try:
            from gamepad_manager import get_gamepad_manager
            get_gamepad_manager().rumble(0.3, 0.6, 120)
        except Exception:
            pass
        return True

    def _update_demobot(self, delta_time) -> None:
        if not self._is_player1_demobot_active():
            if self._demobot_active_last_frame:
                self._clear_demobot_state()
            self._demobot_active_last_frame = False
            return

        self._demobot_active_last_frame = True
        self._cancel_p1_manual_input_state()

        if self.current_piece1 is None or self.board1.is_game_over():
            return

        if self._demobot_piece_ref is not self.current_piece1:
            self._demobot_piece_ref = self.current_piece1
            self._demobot_plan = None
            self._demobot_action_timer = self._demobot_next_action_delay('think')
        else:
            self._demobot_action_timer = max(0.0, float(self._demobot_action_timer or 0.0) - float(delta_time or 0.0))

        if self._demobot_action_timer > 0:
            return

        if self._demobot_plan is None:
            self._demobot_plan = self._build_demobot_plan()
            if self._demobot_plan is None:
                self._demobot_action_timer = self._demobot_next_action_delay('move')
                return

        if self._demobot_plan.get('use_hold'):
            if self.can_hold1 and self._try_hold_piece(1):
                self._demobot_piece_ref = self.current_piece1
                self._demobot_plan = None
                self._demobot_action_timer = self._demobot_next_action_delay('hold')
                return
            self._demobot_plan = None
            self._demobot_action_timer = self._demobot_next_action_delay('move')
            return

        current_piece = self.current_piece1
        if current_piece is None:
            self._demobot_plan = None
            return

        current_rotation = int(getattr(current_piece, 'rotation_state', 0) or 0) % 4
        target_rotation = int(self._demobot_plan.get('target_rotation', current_rotation) or 0) % 4
        if current_rotation != target_rotation:
            if self._try_rotate_p1():
                self._demobot_action_timer = self._demobot_next_action_delay('rotate')
            else:
                self._demobot_plan = None
                self._demobot_action_timer = self._demobot_next_action_delay('move')
            return

        target_x = int(self._demobot_plan.get('target_x', current_piece.x))
        if current_piece.x < target_x:
            moved = self._try_move_right_p1()
            if moved:
                self.sound.play('move')
            else:
                self._demobot_plan = None
            self._demobot_action_timer = self._demobot_next_action_delay('move')
            return

        if current_piece.x > target_x:
            moved = self._try_move_left_p1()
            if moved:
                self.sound.play('move')
            else:
                self._demobot_plan = None
            self._demobot_action_timer = self._demobot_next_action_delay('move')
            return

        drop_distance = self._measure_drop_distance(self.board1, current_piece)
        soft_drop_steps_remaining = int(self._demobot_plan.get('soft_drop_steps_remaining', 0) or 0)
        if drop_distance > 0 and soft_drop_steps_remaining > 0:
            current_ref = self.current_piece1
            self._demobot_plan['soft_drop_steps_remaining'] = soft_drop_steps_remaining - 1
            self._try_soft_drop_step_p1()
            if self.current_piece1 is not current_ref:
                self._demobot_piece_ref = self.current_piece1
                self._demobot_plan = None
                self._demobot_action_timer = self._demobot_next_action_delay('think')
            else:
                self._demobot_action_timer = self._demobot_next_action_delay('soft_drop')
            return

        self._hard_drop_p1()
        self._demobot_piece_ref = self.current_piece1
        self._demobot_plan = None
        self._demobot_action_timer = self._demobot_next_action_delay('hard_drop')

    def _start_pvp_music(self):
        """Start the arena music respecting user preferences."""
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
                if do_shuffle:
                    start_index = 0
                else:
                    start_index = random.randrange(len(track_keys))
                self.sound.set_music_playlist(track_keys, loop=True, start_index=start_index, autoplay=True, force=True, shuffle=do_shuffle)
                self.current_music_track = track_keys[start_index]
                return

        preferred = None
        if self.settings_manager:
            overrides = self.settings_manager.get_mode_music_overrides()
            preferred = overrides.get('pvp')
            if not preferred:
                preferred = self.settings_manager.get('pvp_music')
            if not preferred:
                preferred = self.settings_manager.get('game_music')
        track_key = self.sound.ensure_track_available(preferred or 'pvp_1')
        if track_key:
            self.sound.set_music_playlist([track_key], loop=True, autoplay=True, force=True)
            self.current_music_track = track_key

    def _get_vs_panel_surface(self, panel_width=None, panel_height=None):
        """Return (and rebuild if needed) the cached VS panel surface."""
        target_width = int(panel_width if panel_width else min(self._sx(160), max(self._sx(96), self.window_width // 6)))
        target_height = int(panel_height if panel_height else self._sx(220))
        needs_rebuild = (
            self._vs_panel_surface is None
            or self._vs_panel_surface.get_width() != target_width
            or self._vs_panel_surface.get_height() != target_height
            or self._vs_panel_dirty
        )
        if needs_rebuild:
            surface = pygame.Surface((target_width, target_height), pygame.SRCALPHA)
            self._render_vs_panel(surface)
            self._vs_panel_surface = surface
            self._vs_panel_dirty = False
        return self._vs_panel_surface

    def _render_vs_panel(self, surface: pygame.Surface) -> None:
        """Draw the shared center HUD panel in online PvP visual style."""
        rect = surface.get_rect()
        surface.fill((0, 0, 0, 0))

        sc = self._ui_scale()
        s = lambda v, minimum=1: self._sx(v, sc, minimum)

        base_border = (96, 108, 128)
        soft_cyan = (108, 146, 160)
        soft_magenta = (152, 126, 162)
        vs_color = (210, 204, 224)

        retro_style.draw_glass_panel(
            surface,
            rect,
            alpha=108,
            border_color=base_border,
            glow=False,
        )
        pygame.draw.rect(surface, (*base_border, 160), rect, 1, border_radius=14)

        inner_rect = rect.inflate(-s(10), -s(12))
        inner_surface = pygame.Surface(inner_rect.size, pygame.SRCALPHA)
        h = max(1, inner_rect.height - 1)
        for y in range(inner_rect.height):
            ratio = y / h
            r = int(15 + 10 * ratio)
            g = int(20 + 8 * ratio)
            b = int(34 + 6 * ratio)
            a = int(190 + 8 * ratio)
            pygame.draw.line(inner_surface, (r, g, b, a), (0, y), (inner_rect.width, y))
        surface.blit(inner_surface, inner_rect.topleft)
        pygame.draw.rect(surface, (62, 74, 94), inner_rect, 1, border_radius=12)

        accent_h = max(s(2), 1)
        accent_w = max(s(18), 12)
        left_accent = pygame.Rect(inner_rect.x + s(10), inner_rect.y + s(10), accent_w, accent_h)
        right_accent = pygame.Rect(inner_rect.right - s(10) - accent_w, inner_rect.y + s(10), accent_w, accent_h)
        pygame.draw.rect(surface, soft_cyan, left_accent, border_radius=2)
        pygame.draw.rect(surface, soft_magenta, right_accent, border_radius=2)

        midline = pygame.Rect(rect.centerx - max(1, s(1, minimum=1)), inner_rect.y + s(18), max(2, s(2, minimum=1)), inner_rect.height - s(36))
        pygame.draw.rect(surface, (88, 82, 104, 104), midline, border_radius=2)

        ring_radius = max(s(16), min(inner_rect.width, inner_rect.height) // 4)
        pygame.draw.circle(surface, (120, 126, 158, 38), (rect.centerx, rect.centery + s(4, minimum=0)), ring_radius, 1)
        pygame.draw.circle(surface, (98, 108, 138, 28), (rect.centerx, rect.centery + s(4, minimum=0)), max(1, ring_radius - s(8)), 1)

        info_font = retro_style.get_font(s(14, minimum=10), bold=False)

        if self.match_mode == 'timed':
            remaining_ms = max(0, int(self.match_duration_ms) - int(getattr(self, 'match_elapsed_ms', 0) or 0))
            total_seconds = remaining_ms // 1000
            mm = total_seconds // 60
            ss = total_seconds % 60
            timer_label = f"{mm}:{ss:02d}"
        else:
            elapsed_ms = int(getattr(self, 'match_elapsed_ms', 0) or 0)
            total_seconds = elapsed_ms // 1000
            mm = total_seconds // 60
            ss = total_seconds % 60
            timer_label = f"{mm}:{ss:02d} ∞"
        timer = info_font.render(timer_label, True, (222, 226, 236))
        timer_pill_w = min(inner_rect.width - s(20), max(s(78), timer.get_width() + s(20)))
        timer_pill = pygame.Rect(0, 0, timer_pill_w, s(26))
        timer_pill.centerx = rect.centerx
        timer_pill.top = inner_rect.y + s(12)
        pygame.draw.rect(surface, (24, 30, 44), timer_pill, border_radius=s(13))
        pygame.draw.rect(surface, (74, 84, 104), timer_pill, 1, border_radius=s(13))
        timer_rect = timer.get_rect(center=timer_pill.center)
        surface.blit(timer, timer_rect)

        vs_font = retro_style.get_font(s(40, minimum=22), bold=True)
        vs_text = vs_font.render('VS', True, vs_color)
        vs_shadow = vs_font.render('VS', True, (34, 38, 52))
        vs_center = (rect.centerx, rect.centery + s(4, minimum=0))
        surface.blit(vs_shadow, vs_shadow.get_rect(center=(vs_center[0], vs_center[1] + 2)))
        surface.blit(vs_text, vs_text.get_rect(center=vs_center))
    
    def calculate_board_positions(self):
        """Oyun tahtalarının ekran pozisyonlarını hesapla"""
        active_surface = getattr(self, 'screen', None)
        if active_surface is not None:
            width = int(active_surface.get_width())
            height = int(active_surface.get_height())
        else:
            width = int(getattr(self, 'window_width', 0) or 0)
            height = int(getattr(self, 'window_height', 0) or 0)

        key = (width, height)
        if self._layout_key == key:
            return

        self._layout_key = key
        self.window_width = width
        self.window_height = height

        sc = self._ui_scale()
        s = lambda v, minimum=1: self._sx(v, sc, minimum)

        outer_margin = s(12)
        header_height = s(int(getattr(self, '_base_header_height', 64) or 64))
        preview_panel_width = s(int(getattr(self, '_base_preview_panel_width', 108) or 108))
        preview_panel_gap = s(int(getattr(self, '_base_preview_panel_gap', 8) or 8))
        center_panel_width = s(int(getattr(self, '_base_center_panel_width', 92) or 92))
        center_panel_gap = s(int(getattr(self, '_base_center_panel_gap', 12) or 12))

        available_h = max(s(240), height - s(16) - s(28) - header_height - s(12))
        cell_by_h = available_h // BOARD_HEIGHT

        fixed_width = (
            outer_margin * 2
            + preview_panel_width * 2
            + preview_panel_gap * 2
            + center_panel_width
            + center_panel_gap * 2
        )
        available_w = max(s(280), width - fixed_width)
        cell_by_w = available_w // (2 * BOARD_WIDTH)

        cell_size = int(min(s(36), cell_by_h, cell_by_w))
        cell_size = int(max(s(14), cell_size))

        board_width = BOARD_WIDTH * cell_size
        board_height = BOARD_HEIGHT * cell_size

        total_w = (
            preview_panel_width * 2
            + preview_panel_gap * 2
            + center_panel_width
            + center_panel_gap * 2
            + board_width * 2
        )
        start_x = (width - total_w) // 2
        start_x = int(max(outer_margin, start_x))

        header_top = max(s(16), (height - board_height - header_height - s(44)) // 2)
        board_top = header_top + header_height + s(10)

        self.cell_size = cell_size
        self.preview_panel_width = preview_panel_width
        self.preview_panel_gap = preview_panel_gap
        self.center_panel_width = center_panel_width
        self.center_panel_gap = center_panel_gap
        self.header_height = header_height
        self.header_top = header_top
        self.board_top = board_top
        self.board_gap = center_panel_gap

        self.p1_preview_x = start_x
        self.p1_offset_x = start_x + preview_panel_width + preview_panel_gap
        self.center_panel_x = self.p1_offset_x + board_width + center_panel_gap
        self.p2_offset_x = self.center_panel_x + center_panel_width + center_panel_gap
        self.p2_preview_x = self.p2_offset_x + board_width + preview_panel_gap
        self.p1_offset_y = board_top
        self.p2_offset_y = board_top

        # Grid cache invalidate
        self._board_grid_cache['key'] = None
        self._board_grid_cache['surface'] = None

        # Locked board caches invalidate (layout/cell değişti)
        self._mark_locked_board_dirty(1)
        self._mark_locked_board_dirty(2)

    def _get_board_grid_surface(self, cell_size: int):
        """Return cached semi-transparent grid surface sized to the board."""
        skin = self.mode_skin
        key = (int(cell_size), tuple(getattr(skin, 'grid_color', (50, 50, 80))), BOARD_WIDTH, BOARD_HEIGHT)
        cached = self._board_grid_cache
        if cached.get('key') == key and cached.get('surface') is not None:
            return cached['surface']

        board_width = BOARD_WIDTH * cell_size
        board_height = BOARD_HEIGHT * cell_size
        surface = pygame.Surface((board_width, board_height), pygame.SRCALPHA)
        grid_color = getattr(skin, 'grid_color', (50, 50, 80))

        # Daha minimalist görünüm: grid çizgilerini alpha ile yumuşat.
        grid_alpha = 70
        line_color = (*grid_color[:3], grid_alpha)

        for x in range(BOARD_WIDTH + 1):
            pygame.draw.line(surface, line_color, (x * cell_size, 0), (x * cell_size, board_height))
        for y in range(BOARD_HEIGHT + 1):
            pygame.draw.line(surface, line_color, (0, y * cell_size), (board_width, y * cell_size))

        cached['key'] = key
        cached['surface'] = surface
        return surface

    def _draw_combo_messages(self, offset_x1, offset_x2, start_y, board_width, board_height):
        """Combo mesajlarını (DOUBLE/TRIPLE/QUADRIX) her oyuncunun tahtası üzerinde çiz."""
        for msg, timer, ox in [
            (self.p1_combo_message, self.p1_combo_message_time, offset_x1),
            (self.p2_combo_message, self.p2_combo_message_time, offset_x2),
        ]:
            if timer <= 0 or not msg:
                continue
            alpha = get_combo_popup_alpha(timer)
            center_x = ox + board_width // 2
            center_y = start_y + board_height // 3
            font = self.font_large
            # Gölge
            shadow_surf = font.render(msg, True, COMBO_POPUP_SHADOW_COLOR)
            if alpha < 255:
                shadow_surf.set_alpha(alpha)
            sr = shadow_surf.get_rect(center=(center_x + 2, center_y + 2))
            self.screen.blit(shadow_surf, sr)
            # Ana metin
            color = get_combo_popup_color(msg)
            text_surf = font.render(msg, True, color)
            if alpha < 255:
                text_surf.set_alpha(alpha)
            tr = text_surf.get_rect(center=(center_x, center_y))
            self.screen.blit(text_surf, tr)

    def _draw_player_header(self, rect: pygame.Rect, name: str, accent_color, score: int, lines: int, controls_label: str):
        skin = self.mode_skin
        sc = self._ui_scale()
        s = lambda v, minimum=1: self._sx(v, sc, minimum)

        retro_style.draw_glass_panel(self.screen, rect, alpha=190, border_color=accent_color)
        pygame.draw.rect(self.screen, (*accent_color[:3], 120), rect, 2, border_radius=12)

        underline = pygame.Rect(rect.x + s(14), rect.bottom - s(5), rect.width - s(28), s(3))
        pygame.draw.rect(self.screen, accent_color, underline, border_radius=2)

        title_font = retro_style.get_fitting_font(name, s(22, minimum=14), rect.width - s(120))
        title = title_font.render(name, True, accent_color)
        title_rect = title.get_rect(midleft=(rect.x + s(16), rect.centery - s(8, minimum=0)))
        self.screen.blit(title, title_rect)

        info_color = skin.text_color
        info_font = retro_style.get_font(s(14, minimum=10), bold=False)
        score_s = info_font.render(f'{t("pvp_score")} {score:,}'.replace(',', '.'), True, info_color)
        lines_s = info_font.render(f'{t("pvp_lines")} {lines}', True, info_color)
        self.screen.blit(score_s, score_s.get_rect(midright=(rect.right - s(16), rect.centery - s(10, minimum=0))))
        self.screen.blit(lines_s, lines_s.get_rect(midright=(rect.right - s(16), rect.centery + s(10, minimum=0))))

        ctrl_color = tuple(int(c * 0.75) for c in skin.text_color[:3])
        ctrl_font = retro_style.get_font(s(12, minimum=9), bold=False)
        ctrl = ctrl_font.render(controls_label, True, ctrl_color)
        self.screen.blit(ctrl, ctrl.get_rect(bottomleft=(rect.x + s(16), rect.bottom - s(8))))

    def _draw_preview_piece(self, piece, preview_rect: pygame.Rect):
        if piece is None:
            return

        shape = piece.get_shape() if hasattr(piece, 'get_shape') else getattr(piece, 'shape', None)
        if not shape:
            return

        rows = len(shape)
        cols = max((len(row) for row in shape), default=0)
        if rows <= 0 or cols <= 0:
            return

        padding = max(4, min(preview_rect.width, preview_rect.height) // 10)
        available_w = max(1, preview_rect.width - padding * 2)
        available_h = max(1, preview_rect.height - padding * 2)
        max_cell = max(6, getattr(self, 'cell_size', 20) - 4)
        cell = max(6, min(available_w // cols, available_h // rows, max_cell))
        origin_x = preview_rect.x + (preview_rect.width - cols * cell) // 2
        origin_y = preview_rect.y + (preview_rect.height - rows * cell) // 2

        texture_surface = getattr(piece, 'texture_surface', None)
        rotation = getattr(piece, 'rotation_state', 0)
        color_matrix = getattr(piece, 'color_matrix', None)

        for row_i, row in enumerate(shape):
            for col_i, value in enumerate(row):
                if not value:
                    continue
                draw_color = piece.color[:3] if isinstance(piece.color, (list, tuple)) else piece.color
                if color_matrix is not None:
                    try:
                        matrix_color = color_matrix[row_i][col_i]
                        if matrix_color is not None:
                            draw_color = matrix_color[:3]
                    except Exception:
                        pass
                slice_info = None
                if texture_surface is not None:
                    slice_info = TextureSlice(
                        piece.name,
                        rel_x=col_i,
                        rel_y=row_i,
                        width=cols,
                        height=rows,
                        rotation=rotation,
                    )
                self.draw_textured_block(
                    origin_x + col_i * cell + 1,
                    origin_y + row_i * cell + 1,
                    max(4, cell - 2),
                    draw_color,
                    texture_surface,
                    slice_info,
                )

    def _draw_preview_panel(self, rect: pygame.Rect, accent_color, preview_piece, panel_title: str):
        sc = self._ui_scale()
        s = lambda v, minimum=1: self._sx(v, sc, minimum)

        soft_border = tuple(min(255, int(channel * 0.58 + neutral * 0.42)) for channel, neutral in zip(accent_color[:3], (56, 62, 84)))

        retro_style.draw_glass_panel(self.screen, rect, alpha=122, border_color=soft_border, glow=False)
        pygame.draw.rect(self.screen, (*soft_border, 146), rect, 1, border_radius=12)

        title_text = str(panel_title).strip().upper()
        if not title_text:
            title_text = t('next', 'Sonraki').upper()
        title_max_width = max(s(24), rect.width - s(16))
        title_font = retro_style.get_fitting_font(
            title_text,
            s(15, minimum=10),
            title_max_width,
            bold=True,
            min_size=s(8, minimum=8),
        )
        if title_font.size(title_text)[0] > title_max_width:
            trimmed = title_text.rstrip(':').strip() or title_text
            while trimmed and title_font.size(trimmed + '...')[0] > title_max_width:
                trimmed = trimmed[:-1].rstrip()
            if trimmed:
                title_text = trimmed + '...'
            elif title_font.size('...')[0] <= title_max_width:
                title_text = '...'
            else:
                title_text = ''
        title = title_font.render(title_text, True, soft_border)
        self.screen.blit(title, title.get_rect(centerx=rect.centerx, top=rect.y + s(10)))

        preview_height = min(rect.height - s(42), s(164))
        preview_height = max(s(96), preview_height)
        preview_rect = pygame.Rect(
            rect.x + s(12),
            rect.y + max(s(30), (rect.height - preview_height) // 2),
            rect.width - s(24),
            preview_height,
        )
        inner_surface = self._effect_surface_cache.get_filled_surface(
            (preview_rect.width, preview_rect.height),
            (14, 18, 30, 182),
        )
        self.screen.blit(inner_surface, preview_rect.topleft)
        pygame.draw.rect(self.screen, (*soft_border, 84), preview_rect, 1, border_radius=s(10))

        if preview_piece is not None:
            self._draw_preview_piece(preview_piece, preview_rect)
        else:
            empty_font = retro_style.get_font(s(22, minimum=14), bold=True)
            empty = empty_font.render('—', True, retro_style.text_muted)
            self.screen.blit(empty, empty.get_rect(center=preview_rect.center))
    
    def load_background_image(self):
        """Arka plan resmini yükle"""
        # Önce custom background'ı kontrol et
        custom_bg = self.settings_manager.get('bg_pvp_main', None)
        if custom_bg and os.path.exists(custom_bg):
            if self.background.load_image(custom_bg):
                print(f"✨ Özel PvP ana arka plan yüklendi: {os.path.basename(custom_bg)}")
                return
        
        # Yoksa olası resim yolları - PyInstaller için resource_path kullan
        # Varsayılan: outer_backgrounds/outer_background (PvP ana arka plan)
        possible_paths = [
            resource_path('backgrounds/outer_backgrounds.png'),
            resource_path('backgrounds/outer_background.png'),
            resource_path('backgrounds/outer_background.jpg'),
            resource_path('backgrounds/background.png'),
            resource_path('backgrounds/background.jpg'),
            resource_path('backgrounds/anime_bg.png'),
            resource_path('backgrounds/waifu.png'),
        ]
        
        for path in possible_paths:
            if self.background.load_image(path):
                print(f"✨ PvP Arka plan yüklendi: {os.path.basename(path)}")
                break
        else:
            print("ℹ️ PvP için arka plan resmi bulunamadı. backgrounds/ klasörüne resim ekleyin!")
    
    def load_board_background(self):
        """Quadrix oyun alanları için ayrı arka plan resmini yükle"""
        # Önce custom background'ı kontrol et
        custom_bg = self.settings_manager.get('bg_pvp_board', None)
        if custom_bg and os.path.exists(custom_bg):
            if self.board_background.load_image(custom_bg):
                print(f"✨ Özel PvP oyun alanı arka planı yüklendi: {os.path.basename(custom_bg)}")
                return
        
        # Yoksa olası resim yolları - Quadrix alanları için ayrı arka plan
        # Varsayılan: game_background (oyun alanı)
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
                print(f"✨ Quadrix alanlari icin arka plan yuklendi: {os.path.basename(path)}")
                break
        else:
            print("ℹ️ Quadrix alanlari icin ayri arka plan bulunamadi (opsiyonel)")
    
    def update_transparency(self, value):
        """Transparanlık ayarını güncelle.

        Amaç: menülerdeki ve oyun alanlarındaki transparanlık aynı davransın.
        """
        if self.board_background:
            self.board_background.set_transparency(value)
            print(f"🎨 PvP board background transparanlığı güncellendi: %{int(value * 100)}")
        if getattr(self, 'background', None) is not None:
            try:
                self.background.set_transparency(value)
            except Exception:
                pass
    
    def generate_pieces(self, count: int) -> None:
        """Torba (bag) sistemiyle önceden belirlenmiş parça sırası oluştur.

        Pool'daki her parça tipinden ``_bag_copies`` (3) kadar kopya bir torbaya
        atılıp karıştırılır.  İstenen ``count`` kadar parça üretilene kadar
        torbalar oluşturulmaya devam eder.  Üst üste aynı parça sınırı korunur.
        """
        if not hasattr(self, '_max_consecutive_same_piece'):
            self._max_consecutive_same_piece = 3
        if not hasattr(self, '_last_piece_index'):
            self._last_piece_index = None
        if not hasattr(self, '_last_piece_streak'):
            self._last_piece_streak = 0

        limit = int(getattr(self, '_max_consecutive_same_piece', 3) or 3)
        total = len(SHAPES)
        bag_copies = 3  # Her parça tipinden kaç kopya

        generated = 0
        while generated < count:
            # Yeni torba oluştur: her indeksten bag_copies kadar kopya
            bag: list[int] = list(range(total)) * bag_copies
            random.shuffle(bag)

            for piece_index in bag:
                # Üst üste aynı parça sınırını kontrol et
                if (
                    self._last_piece_index is not None
                    and piece_index == self._last_piece_index
                    and int(getattr(self, '_last_piece_streak', 0) or 0) >= limit
                    and total > 1
                ):
                    # Bu parçayı atla - torbadaki sonrakine geç
                    continue

                if piece_index == self._last_piece_index:
                    self._last_piece_streak = int(getattr(self, '_last_piece_streak', 0) or 0) + 1
                else:
                    self._last_piece_index = piece_index
                    self._last_piece_streak = 1

                self.piece_sequence.append(piece_index)
                generated += 1
                if generated >= count:
                    break
    
    def get_next_piece(self):
        """Sıradaki parçayı al (her iki oyuncu için aynı)"""
        if self.current_piece_index >= len(self.piece_sequence):
            self.generate_pieces(50)
        
        piece_index = self.piece_sequence[self.current_piece_index]
        self.current_piece_index += 1
        piece = Piece(x=3, y=0, shape_index=piece_index)
        piece.y = get_piece_spawn_y(piece)

        # Tema + blok stili uygula
        self._apply_block_style(piece)
        
        return piece
    
    def handle_input(self):
        """Kullanıcı girdilerini işle"""
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
            
            if event.type == pygame.VIDEORESIZE:
                req_w = max(event.w, 800)
                req_h = max(event.h, 600)
                self.screen = create_display(req_w, req_h, fullscreen=True, resizable=False, borderless=True)
                # Daima surface'tan gerçek piksel boyutunu al
                self.window_width = self.screen.get_width()
                self.window_height = self.screen.get_height()
                self._vs_panel_dirty = True
                self.calculate_board_positions()
                continue

            # Çıkış onayı açıksa tüm input'u burada yakala
            if getattr(self, 'show_exit_prompt', False) and not getattr(self, 'name_input_active', False):
                if event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_ESCAPE, pygame.K_n):
                        self.show_exit_prompt = False
                        continue
                    if event.key in (pygame.K_RETURN, pygame.K_y):
                        return 'menu'
                    continue

                if event.type == pygame.MOUSEBUTTONDOWN and getattr(event, 'button', None) == 1:
                    pos = normalize_mouse_pos(getattr(event, 'pos', None)) or get_mouse_pos()
                    if self.exit_yes_rect and self.exit_yes_rect.collidepoint(pos):
                        try:
                            self.sound.play('click')
                        except Exception:
                            pass
                        return 'menu'
                    if self.exit_no_rect and self.exit_no_rect.collidepoint(pos):
                        try:
                            self.sound.play('move')
                        except Exception:
                            pass
                        self.show_exit_prompt = False
                    continue

                # Diğer event'leri yut
                continue

            if self.paused and not self.game_over and getattr(self, '_pause_settings_active', False):
                pause_settings_action = self._handle_pause_settings_input(event)
                if pause_settings_action is not None:
                    return pause_settings_action
                continue

            # Duraklatılmışsa mouse kontrollerini işle (tek oyunculu ile aynı)
            if self.paused and not self.game_over and event.type in (pygame.MOUSEMOTION, pygame.MOUSEWHEEL, pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
                pause_action = self._handle_pause_menu_input(event)
                if pause_action == 'resume':
                    self.paused = False
                    if hasattr(self, 'sound') and self.sound:
                        self.sound.unduck_music()
                elif pause_action == 'main_menu':
                    return 'menu'
                continue
            
            # İsim girişi/mod seçimi ekranında fare desteği
            if self.name_input_active and event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                pos = normalize_mouse_pos(getattr(event, 'pos', None)) or event.pos
                mouse_action = self._handle_setup_mouse_click(pos)
                if mouse_action:
                    continue
            
            if event.type == pygame.KEYDOWN:
                controls1 = self.pvp_controls['player1']
                controls2 = self.pvp_controls['player2']
                demobot_active = self._is_player1_demobot_active()
                # İsim girişi ekranındayken
                if self.name_input_active:
                    if event.key == pygame.K_ESCAPE:
                        return 'menu'  # Ana menüye dön
                    
                    if self.current_input == 1:
                        if event.key == pygame.K_RETURN and len(self.player1_name) > 0:
                            self.current_input = 2
                            self._vs_panel_dirty = True
                        elif event.key == pygame.K_BACKSPACE:
                            self.player1_name = self.player1_name[:-1]
                            self._vs_panel_dirty = True
                        elif len(self.player1_name) < 12 and event.unicode.isprintable():
                            self.player1_name += event.unicode
                            self._vs_panel_dirty = True
                    
                    elif self.current_input == 2:
                        if event.key == pygame.K_RETURN and len(self.player2_name) > 0:
                            self.current_input = 3  # Mod seçimine geç
                            self._vs_panel_dirty = True
                        elif event.key == pygame.K_BACKSPACE:
                            self.player2_name = self.player2_name[:-1]
                            self._vs_panel_dirty = True
                        elif len(self.player2_name) < 12 and event.unicode.isprintable():
                            self.player2_name += event.unicode
                            self._vs_panel_dirty = True
                    
                    elif self.current_input == 3:
                        # Mod seçimi: Sol/Sağ ok ile değiştir
                        if event.key in (pygame.K_LEFT, pygame.K_RIGHT):
                            self.match_mode = 'endless' if self.match_mode == 'timed' else 'timed'
                            self._vs_panel_dirty = True
                        elif event.key == pygame.K_RETURN:
                            if self.match_mode == 'timed':
                                self.current_input = 4  # Süre ayarına geç
                            else:
                                # Süresiz mod - direkt oyuna başla
                                self.name_input_active = False
                                self._vs_panel_dirty = True
                                self.match_active = False
                                self.match_elapsed_ms = 0
                                self.match_end_reason = None
                                self._last_timer_seconds = None
                        elif event.key == pygame.K_BACKSPACE:
                            self.current_input = 2  # Geri dön
                            self._vs_panel_dirty = True
                    
                    elif self.current_input == 4:
                        # Süre ayarı: Sol/Sağ ok ile değiştir (1-10 dakika)
                        if event.key == pygame.K_LEFT:
                            self.custom_duration_minutes = max(1, self.custom_duration_minutes - 1)
                            self.match_duration_ms = self.custom_duration_minutes * 60 * 1000
                            self._vs_panel_dirty = True
                        elif event.key == pygame.K_RIGHT:
                            self.custom_duration_minutes = min(10, self.custom_duration_minutes + 1)
                            self.match_duration_ms = self.custom_duration_minutes * 60 * 1000
                            self._vs_panel_dirty = True
                        elif event.key == pygame.K_RETURN:
                            # Oyuna başla
                            self.name_input_active = False
                            self._vs_panel_dirty = True
                            self.match_active = False
                            self.match_elapsed_ms = 0
                            self.match_end_reason = None
                            self._last_timer_seconds = None
                        elif event.key == pygame.K_BACKSPACE:
                            self.current_input = 3  # Mod seçimine geri dön
                            self._vs_panel_dirty = True
                    continue
                
                # P - Duraklat
                if event.key == self.pvp_controls['pause']:
                    self.paused = not self.paused
                    if self.paused:
                        self.pause_menu_selected = 0
                        if hasattr(self, 'sound') and self.sound:
                            self.sound.duck_music()
                    else:
                        if hasattr(self, 'sound') and self.sound:
                            self.sound.unduck_music()
                    continue

                # Duraklatılmışsa menü kontrollerini işle
                if self.paused:
                    pause_action = self._handle_pause_menu_input(event)
                    if pause_action == 'resume':
                        self.paused = False
                        if hasattr(self, 'sound') and self.sound:
                            self.sound.unduck_music()
                    elif pause_action == 'main_menu':
                        return 'menu'
                    continue

                # Game over iken ESC - ana menüye dön
                if self.game_over and event.key == pygame.K_ESCAPE:
                    return 'menu'

                # Oyun sırasında ESC - pause menüsünü aç
                if event.key == pygame.K_ESCAPE:
                    self.paused = True
                    self.pause_menu_selected = 0
                    if hasattr(self, 'sound') and self.sound:
                        self.sound.duck_music()
                    continue
                
                if self.game_over:
                    if event.key == pygame.K_r:
                        self.restart(preserve_session=True)
                    continue
                
                if self.paused:
                    continue
                
                # OYUNCU 1 KONTROLLER (WASD + Shift/Ctrl)
                if not self.board1.is_game_over() and not demobot_active:
                    # A - Sol (DAS ile)
                    if event.key == controls1['move_left']:
                        moved = self._try_move_left_p1()
                        if moved:
                            self.sound.play('move')
                        self.p1_das_direction = -1
                        self.p1_das_timer = 0
                        self.p1_das_repeat_timer = 0
                        self.p1_das_charged = False
                    
                    # D - Sağ (DAS ile)
                    elif event.key == controls1['move_right']:
                        moved = self._try_move_right_p1()
                        if moved:
                            self.sound.play('move')
                        self.p1_das_direction = 1
                        self.p1_das_timer = 0
                        self.p1_das_repeat_timer = 0
                        self.p1_das_charged = False
                    
                    # S - Aşağı (soft drop) - tuşa basılınca hızlı düş
                    elif event.key == controls1['soft_drop']:
                        self.p1_soft_drop_active = True
                        self.p1_soft_drop_timer = 0
                        # İlk hareketi hemen yap
                        self._try_soft_drop_step_p1()
                    
                    # W - Döndür
                    elif event.key == controls1['rotate']:
                        self._try_rotate_p1()
                    
                    # Shift - Hard drop
                    elif event.key == controls1['hard_drop']:
                        self._hard_drop_p1()

                    # Hold
                    elif event.key == controls1['hold']:
                        self._try_hold_piece(1)
                
                # OYUNCU 2 KONTROLLER (Ok tuşları + Space)
                if not self.board2.is_game_over():
                    # Sol ok (DAS ile)
                    if event.key == controls2['move_left']:
                        moved = self._try_move_left_p2()
                        if moved:
                            self.sound.play('move')
                        self.p2_das_direction = -1
                        self.p2_das_timer = 0
                        self.p2_das_repeat_timer = 0
                        self.p2_das_charged = False
                    
                    # Sağ ok (DAS ile)
                    elif event.key == controls2['move_right']:
                        moved = self._try_move_right_p2()
                        if moved:
                            self.sound.play('move')
                        self.p2_das_direction = 1
                        self.p2_das_timer = 0
                        self.p2_das_repeat_timer = 0
                        self.p2_das_charged = False
                    
                    # Aşağı ok - tuşa basılınca hızlı düş
                    elif event.key == controls2['soft_drop']:
                        self.p2_soft_drop_active = True
                        self.p2_soft_drop_timer = 0
                        # İlk hareketi hemen yap
                        self.current_piece2.y += 1
                        if not self.board2.is_valid_position(self.current_piece2):
                            self.current_piece2.y -= 1
                            self._mark_player_grounded(2)
                        else:
                            self._reset_lock_delay_state(2)
                    
                    # Yukarı ok - Döndür
                    elif event.key == controls2['rotate']:
                        original_x = self.current_piece2.x
                        rotated = True
                        self.current_piece2.rotate()
                        if not self.board2.is_valid_position(self.current_piece2):
                            for dx in [1, -1, 2, -2]:
                                self.current_piece2.x = original_x + dx
                                if self.board2.is_valid_position(self.current_piece2):
                                    break
                            else:
                                self.current_piece2.x = original_x
                                for _ in range(3):
                                    self.current_piece2.rotate()
                                rotated = False
                        if rotated:
                            self.sound.play('rotate')
                    
                    # Space - Hard drop
                    elif event.key == controls2['hard_drop']:
                        start_y = self.current_piece2.y
                        drop_distance = 0
                        
                        while self.board2.is_valid_position(self.current_piece2, dy=1):
                            self.current_piece2.y += 1
                            drop_distance += 1

                        if self.effects_enabled and drop_distance > 0:
                            self._create_drop_trail(
                                2,
                                self.current_piece2,
                                self.p2_offset_x,
                                self.p2_offset_y,
                                self.cell_size,
                                start_y,
                                drop_distance,
                                trail_type='hard',
                            )
                        
                        # Hard drop ekran sarsıntısı
                        if self.effects_enabled and drop_distance > 0:
                            self.trigger_hard_drop_screen_shake()

                        self.lock_and_new_piece(2)

                        try:
                            from gamepad_manager import get_gamepad_manager
                            get_gamepad_manager().rumble(0.3, 0.6, 120)
                        except Exception:
                            pass

                    # Hold
                    elif event.key == controls2['hold']:
                        self._try_hold_piece(2)
            
            # Game over ekranında mouse tıklama kontrolü
            if self.game_over and event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if getattr(event, 'from_gamepad', False) and getattr(event, 'gamepad_context', 'game') == 'game':
                    continue
                pos = normalize_mouse_pos(getattr(event, 'pos', None)) or event.pos
                if self._game_over_restart_rect and self._game_over_restart_rect.collidepoint(pos):
                    self.sound.play('click')
                    self.restart(preserve_session=True)
                elif self._game_over_menu_rect and self._game_over_menu_rect.collidepoint(pos):
                    self.sound.play('click')
                    return 'menu'
            
            # Tuş bırakıldığında DAS'ı ve soft drop'u durdur
            if event.type == pygame.KEYUP:
                controls1 = self.pvp_controls['player1']
                controls2 = self.pvp_controls['player2']
                demobot_active = self._is_player1_demobot_active()
                # Oyuncu 1
                if not demobot_active and event.key == controls1['move_left']:
                    if self.p1_das_direction == -1:
                        pressed = pygame.key.get_pressed()
                        other_key = controls1['move_right']
                        if other_key < len(pressed) and pressed[other_key]:
                            moved = self._try_move_right_p1()
                            if moved:
                                self.sound.play('move')
                            self.p1_das_direction = 1
                            self.p1_das_timer = 0
                            self.p1_das_repeat_timer = 0
                            self.p1_das_charged = False
                        else:
                            self.p1_das_direction = 0
                            self.p1_das_charged = False
                elif not demobot_active and event.key == controls1['move_right']:
                    if self.p1_das_direction == 1:
                        pressed = pygame.key.get_pressed()
                        other_key = controls1['move_left']
                        if other_key < len(pressed) and pressed[other_key]:
                            moved = self._try_move_left_p1()
                            if moved:
                                self.sound.play('move')
                            self.p1_das_direction = -1
                            self.p1_das_timer = 0
                            self.p1_das_repeat_timer = 0
                            self.p1_das_charged = False
                        else:
                            self.p1_das_direction = 0
                            self.p1_das_charged = False
                elif not demobot_active and event.key == controls1['soft_drop']:
                    self.p1_soft_drop_active = False
                # Oyuncu 2
                elif event.key == controls2['move_left']:
                    if self.p2_das_direction == -1:
                        pressed = pygame.key.get_pressed()
                        other_key = controls2['move_right']
                        if other_key < len(pressed) and pressed[other_key]:
                            moved = self._try_move_right_p2()
                            if moved:
                                self.sound.play('move')
                            self.p2_das_direction = 1
                            self.p2_das_timer = 0
                            self.p2_das_repeat_timer = 0
                            self.p2_das_charged = False
                        else:
                            self.p2_das_direction = 0
                            self.p2_das_charged = False
                elif event.key == controls2['move_right']:
                    if self.p2_das_direction == 1:
                        pressed = pygame.key.get_pressed()
                        other_key = controls2['move_left']
                        if other_key < len(pressed) and pressed[other_key]:
                            moved = self._try_move_left_p2()
                            if moved:
                                self.sound.play('move')
                            self.p2_das_direction = -1
                            self.p2_das_timer = 0
                            self.p2_das_repeat_timer = 0
                            self.p2_das_charged = False
                        else:
                            self.p2_das_direction = 0
                            self.p2_das_charged = False
                elif event.key == controls2['soft_drop']:
                    self.p2_soft_drop_active = False
        
        return True

    def _handle_pause_menu_input(self, event):
        """Duraklama menüsü girdilerini işle (tek oyunculu ile aynı davranış)."""

        def apply_option(option: str):
            if option == 'resume':
                return 'resume'
            if option == 'settings':
                self._open_pause_settings()
                return None
            if option == 'music':
                self.sound.music_enabled = not self.sound.music_enabled
                if self.settings_manager:
                    self.settings_manager.set('music_enabled', self.sound.music_enabled)
                if self.sound.music_enabled:
                    # Müzik tekrar açıldıysa PvP playlist'ini başlat (shuffle/playlist korunur)
                    self._start_pvp_music()
                else:
                    self.sound.stop_music()
                return None
            if option == 'sound_effects':
                self.sound.sfx_enabled = not self.sound.sfx_enabled
                if self.settings_manager:
                    self.settings_manager.set('sound_enabled', self.sound.sfx_enabled)
                return None
            if option == 'main_menu':
                return 'main_menu'
            return None

        def adjust_volume(option: str, delta: float | None = None, absolute: float | None = None):
            if option == 'music_volume':
                if absolute is None:
                    target = self.sound.music_volume + (delta or 0.0)
                else:
                    target = absolute
                new_vol = max(0.0, min(1.0, float(target)))
                self.sound.set_music_volume(new_vol)
                if self.settings_manager:
                    self.settings_manager.set('music_volume', new_vol)
            elif option == 'sfx_volume':
                if absolute is None:
                    target = self.sound.sfx_volume + (delta or 0.0)
                else:
                    target = absolute
                new_vol = max(0.0, min(1.0, float(target)))
                self.sound.set_volume(new_vol)
                if self.settings_manager:
                    self.settings_manager.set('sfx_volume', new_vol)

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_UP:
                self.pause_menu_selected = (self.pause_menu_selected - 1) % len(self.pause_menu_options)
                self.sound.play('move')
                return None
            if event.key == pygame.K_DOWN:
                self.pause_menu_selected = (self.pause_menu_selected + 1) % len(self.pause_menu_options)
                self.sound.play('move')
                return None
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                option = self.pause_menu_options[self.pause_menu_selected]
                return apply_option(option)
            if event.key in (pygame.K_LEFT, pygame.K_RIGHT):
                option = self.pause_menu_options[self.pause_menu_selected]
                delta = 0.1 if event.key == pygame.K_RIGHT else -0.1
                adjust_volume(option, delta=delta)
                return None
            if event.key == pygame.K_BACKSPACE:
                return 'main_menu'
            if event.key == pygame.K_ESCAPE:
                return 'resume'
            # P tuşu pause toggle, menüde "Devam Et" gibi davransın
            if event.key == self.pvp_controls.get('pause'):
                return 'resume'
            return None

        if event.type == pygame.MOUSEWHEEL:
            option = self.pause_menu_options[self.pause_menu_selected]
            if option in ('music_volume', 'sfx_volume'):
                delta = 0.05 if event.y > 0 else -0.05
                adjust_volume(option, delta=delta)
            else:
                step = -1 if event.y > 0 else 1
                self.pause_menu_selected = (self.pause_menu_selected + step) % len(self.pause_menu_options)
                self.sound.play('move')
            return None

        if event.type == pygame.MOUSEMOTION:
            pos = normalize_mouse_pos(getattr(event, 'pos', None)) or get_mouse_pos()
            if self._pause_vol_drag_active and self._pause_vol_drag_option:
                bar_rect = (getattr(self, '_pause_volume_rects', {}) or {}).get(self._pause_vol_drag_option)
                if bar_rect and bar_rect.width > 0:
                    ratio = (pos[0] - bar_rect.x) / bar_rect.width
                    adjust_volume(self._pause_vol_drag_option, absolute=max(0.0, min(1.0, ratio)))
                return None
            for idx, rect in enumerate(getattr(self, '_pause_option_rects', []) or []):
                if rect and rect.collidepoint(pos):
                    if idx != self.pause_menu_selected:
                        self.pause_menu_selected = idx
                    break
            return None

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = normalize_mouse_pos(getattr(event, 'pos', None)) or get_mouse_pos()
            for idx, rect in enumerate(getattr(self, '_pause_option_rects', []) or []):
                if rect and rect.collidepoint(pos):
                    self.pause_menu_selected = idx
                    option = self.pause_menu_options[idx]
                    if option in ('music_volume', 'sfx_volume'):
                        bar_rect = (getattr(self, '_pause_volume_rects', {}) or {}).get(option)
                        if bar_rect and bar_rect.width > 0:
                            ratio = (pos[0] - bar_rect.x) / bar_rect.width
                            adjust_volume(option, absolute=max(0.0, min(1.0, ratio)))
                            self._pause_vol_drag_active = True
                            self._pause_vol_drag_option = option
                        return None
                    return apply_option(option)
            return None

        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self._pause_vol_drag_active = False
            self._pause_vol_drag_option = ''
            return None

        return None

    def _draw_pause_menu(self):
        """Tek oyuncudaki duraklama menüsü panelini PvP'de çiz."""
        width, height = self.window_width, self.window_height
        ui_scale = self._ui_scale()

        overlay = pygame.Surface((width, height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 185))
        self.screen.blit(overlay, (0, 0))

        panel_width = min(self._sx(520, ui_scale), width - self._sx(100, ui_scale))
        option_count = len(self.pause_menu_options)
        item_h = self._sx(56, ui_scale)
        gap = self._sx(10, ui_scale)
        top_pad = self._sx(78, ui_scale)
        bottom_pad = self._sx(64, ui_scale)
        panel_height = top_pad + option_count * item_h + (option_count - 1) * gap + bottom_pad
        panel_rect = pygame.Rect((width - panel_width) // 2, (height - panel_height) // 2, panel_width, panel_height)

        retro_style.draw_glass_panel(self.screen, panel_rect, alpha=180, border_color=(*retro_style.accent, 140), glow=True)

        title_font = retro_style.get_font(self._sx(30, ui_scale, minimum=16), bold=True)
        title_surf = title_font.render(t('paused'), True, retro_style.accent)
        self.screen.blit(title_surf, title_surf.get_rect(centerx=panel_rect.centerx, top=panel_rect.y + self._sx(18, ui_scale)))

        self._pause_option_rects = []
        self._pause_volume_rects = {}
        _pause_mouse_pos = get_mouse_pos()

        start_y = panel_rect.y + top_pad
        for i, option in enumerate(self.pause_menu_options):
            y = start_y + i * (item_h + gap)
            button_rect = pygame.Rect(panel_rect.x + self._sx(22, ui_scale), y, panel_rect.width - self._sx(44, ui_scale), item_h)
            self._pause_option_rects.append(button_rect)

            is_selected = i == self.pause_menu_selected
            label = t(option)
            sub_text = None
            color_code = retro_style.primary

            if option == 'resume':
                color_code = retro_style.success
            elif option == 'main_menu':
                color_code = retro_style.secondary
            elif option == 'music':
                color_code = retro_style.primary
                sub_text = t('on') if self.sound.music_enabled else t('off')
            elif option == 'sound_effects':
                color_code = retro_style.primary
                sub_text = t('on') if self.sound.sfx_enabled else t('off')
            elif option == 'music_volume':
                color_code = retro_style.accent
                sub_text = f"{int(self.sound.music_volume * 100)}%  < >"
            elif option == 'sfx_volume':
                color_code = retro_style.accent
                sub_text = f"{int(self.sound.sfx_volume * 100)}%  < >"

            _pv_hover = button_rect.collidepoint(_pause_mouse_pos)
            retro_style.draw_uniform_button(
                self.screen,
                button_rect,
                label,
                sub_text=sub_text,
                color_code=color_code,
                selected=is_selected,
                state='hover' if _pv_hover else 'normal',
            )

            if option == 'music_volume':
                bar_rect = pygame.Rect(
                    button_rect.right - self._sx(150, ui_scale),
                    button_rect.y + self._sx(18, ui_scale),
                    self._sx(90, ui_scale),
                    self._sx(18, ui_scale),
                )
                self._pause_volume_rects[option] = bar_rect
                retro_style.draw_volume_bar(
                    self.screen, bar_rect.x, bar_rect.y, bar_rect.width, bar_rect.height,
                    self.sound.music_volume, (0, 210, 255), int(self.sound.music_volume * 100),
                    is_selected, ui_scale,
                )
            elif option == 'sfx_volume':
                bar_rect = pygame.Rect(
                    button_rect.right - self._sx(150, ui_scale),
                    button_rect.y + self._sx(18, ui_scale),
                    self._sx(90, ui_scale),
                    self._sx(18, ui_scale),
                )
                self._pause_volume_rects[option] = bar_rect
                retro_style.draw_volume_bar(
                    self.screen, bar_rect.x, bar_rect.y, bar_rect.width, bar_rect.height,
                    self.sound.sfx_volume, (255, 185, 0), int(self.sound.sfx_volume * 100),
                    is_selected, ui_scale,
                )

    def _get_local_result_player_names(self) -> tuple[str, str]:
        p1 = str(self.player1_name or t('pvp_player1', 'Oyuncu 1')).strip()
        p2 = str(self.player2_name or t('pvp_player2', 'Oyuncu 2')).strip()
        return p1 or t('pvp_player1', 'Oyuncu 1'), p2 or t('pvp_player2', 'Oyuncu 2')

    @staticmethod
    def _format_pvp_result_number(value: int) -> str:
        return f"{int(value):,}".replace(',', '.')

    @staticmethod
    def _local_result_side_label(side: str, is_tr: bool) -> str:
        if side == 'p1':
            return 'P1'
        if side == 'p2':
            return 'P2'
        if side == 'both':
            return 'İkisi' if is_tr else 'Both'
        if side == 'none':
            return 'Yok' if is_tr else 'None'
        return 'Eşit' if is_tr else 'Tie'

    def _build_local_result_breakdown(self) -> dict[str, object]:
        p1_name, p2_name = self._get_local_result_player_names()
        score1 = int(getattr(self.board1, 'score', 0) or 0)
        score2 = int(getattr(self.board2, 'score', 0) or 0)
        lines1 = int(getattr(self.board1, 'lines_cleared', 0) or 0)
        lines2 = int(getattr(self.board2, 'lines_cleared', 0) or 0)

        if score1 > score2:
            score_state = 'p1'
            p1_score_point = LOCAL_PVP_RESULT_SCORE_POINTS
            p2_score_point = 0
        elif score2 > score1:
            score_state = 'p2'
            p1_score_point = 0
            p2_score_point = LOCAL_PVP_RESULT_SCORE_POINTS
        else:
            score_state = 'draw'
            p1_score_point = 0
            p2_score_point = 0

        if lines1 > lines2:
            lines_state = 'p1'
            p1_lines_point = LOCAL_PVP_RESULT_LINES_POINTS
            p2_lines_point = 0
        elif lines2 > lines1:
            lines_state = 'p2'
            p1_lines_point = 0
            p2_lines_point = LOCAL_PVP_RESULT_LINES_POINTS
        else:
            lines_state = 'draw'
            p1_lines_point = 0
            p2_lines_point = 0

        p1_eliminated = bool(getattr(self, 'p1_eliminated', False))
        p2_eliminated = bool(getattr(self, 'p2_eliminated', False))
        if p1_eliminated and p2_eliminated:
            board_state = 'none'
            p1_board_point = 0
            p2_board_point = 0
        elif p1_eliminated:
            board_state = 'p2'
            p1_board_point = 0
            p2_board_point = LOCAL_PVP_RESULT_BOARD_OPEN_POINTS
        elif p2_eliminated:
            board_state = 'p1'
            p1_board_point = LOCAL_PVP_RESULT_BOARD_OPEN_POINTS
            p2_board_point = 0
        else:
            board_state = 'both'
            p1_board_point = LOCAL_PVP_RESULT_BOARD_OPEN_POINTS
            p2_board_point = LOCAL_PVP_RESULT_BOARD_OPEN_POINTS

        p1_points = p1_score_point + p1_lines_point + p1_board_point
        p2_points = p2_score_point + p2_lines_point + p2_board_point

        if p1_points >= LOCAL_PVP_RESULT_WIN_THRESHOLD and p2_points < LOCAL_PVP_RESULT_WIN_THRESHOLD:
            winner_side = 'p1'
        elif p2_points >= LOCAL_PVP_RESULT_WIN_THRESHOLD and p1_points < LOCAL_PVP_RESULT_WIN_THRESHOLD:
            winner_side = 'p2'
        else:
            winner_side = 'draw'

        return {
            'winner': winner_side,
            'p1_name': p1_name,
            'p2_name': p2_name,
            'p1_score': score1,
            'p2_score': score2,
            'p1_lines': lines1,
            'p2_lines': lines2,
            'score_state': score_state,
            'lines_state': lines_state,
            'board_state': board_state,
            'p1_eliminated': p1_eliminated,
            'p2_eliminated': p2_eliminated,
            'p1_score_point': p1_score_point,
            'p2_score_point': p2_score_point,
            'p1_lines_point': p1_lines_point,
            'p2_lines_point': p2_lines_point,
            'p1_board_point': p1_board_point,
            'p2_board_point': p2_board_point,
            'p1_points': p1_points,
            'p2_points': p2_points,
        }

    def _build_local_result_reason_text(self, result: dict[str, object] | None = None) -> str:
        if result is None:
            result = self._build_local_result_breakdown()

        lang = get_language()
        is_tr = lang == 'tr'
        p1_name = str(result.get('p1_name', t('pvp_player1', 'Oyuncu 1')))
        p2_name = str(result.get('p2_name', t('pvp_player2', 'Oyuncu 2')))
        winner_side = str(result.get('winner', 'draw'))
        score_state = str(result.get('score_state', 'draw'))
        lines_state = str(result.get('lines_state', 'draw'))
        board_state = str(result.get('board_state', 'none'))
        p1_points = int(result.get('p1_points', 0) or 0)
        p2_points = int(result.get('p2_points', 0) or 0)
        rule_text = (
            'Skor ve satır 1, alan ise 2 puan sayıldı.'
            if is_tr else
            'Score and lines counted as 1 point each, while board control counted as 2.'
        )

        def join_parts(parts: list[str]) -> str:
            clean_parts = [str(part).strip() for part in parts if str(part).strip()]
            if not clean_parts:
                return ''
            if len(clean_parts) == 1:
                return clean_parts[0]
            if len(clean_parts) == 2:
                return f"{clean_parts[0]} ve {clean_parts[1]}" if is_tr else f"{clean_parts[0]} and {clean_parts[1]}"
            head = ', '.join(clean_parts[:-1])
            tail = clean_parts[-1]
            return f"{head} ve {tail}" if is_tr else f"{head}, and {tail}"

        def side_name(side: str) -> str:
            return p1_name if side == 'p1' else p2_name

        def unique_advantage(side: str) -> str:
            parts: list[str] = []
            if score_state == side:
                parts.append('skorda öne geçti' if is_tr else 'finished with the higher score')
            if lines_state == side:
                parts.append('daha çok satır temizledi' if is_tr else 'cleared more lines')
            if board_state == side:
                parts.append('oyun alanını açık tuttu' if is_tr else 'kept the board open')
            joined = join_parts(parts)
            if not joined:
                return ''
            return f"{side_name(side)} {joined}"

        shared_parts: list[str] = []
        if score_state == 'draw':
            shared_parts.append('skor başlığı eşit kaldı' if is_tr else 'the score stayed tied')
        if lines_state == 'draw':
            shared_parts.append('satır temizliği dengede kaldı' if is_tr else 'line clears stayed even')
        if board_state == 'both':
            shared_parts.append('iki oyuncu da oyun alanını açık tuttu' if is_tr else 'both boards stayed open')
        elif board_state == 'none':
            shared_parts.append('iki oyuncu da oyun alanını doldurdu' if is_tr else 'both boards topped out')

        detail_segments = [
            unique_advantage('p1'),
            unique_advantage('p2'),
        ]
        shared_text = join_parts(shared_parts)
        if shared_text:
            detail_segments.append(shared_text.capitalize())
        detail_text = '. '.join(segment for segment in detail_segments if segment)
        if detail_text:
            detail_text = f" {detail_text}."

        if not is_tr:
            if winner_side == 'draw':
                return (
                    f"The weighted result points finished {p1_points}-{p2_points}, so the match ended in a draw."
                    f" {rule_text}{detail_text}"
                ).strip()

            winner_name = side_name(winner_side)
            winner_points = p1_points if winner_side == 'p1' else p2_points
            loser_points = p2_points if winner_side == 'p1' else p1_points
            return (
                f"{winner_name} won the weighted result check {winner_points}-{loser_points}."
                f" {rule_text}{detail_text}"
            ).strip()

        if winner_side == 'draw':
            return (
                f"Ağırlıklı sonuç puanı {p1_points}-{p2_points} bitti ve maç berabere kaldı."
                f" {rule_text}{detail_text}"
            ).strip()

        winner_name = side_name(winner_side)
        winner_points = p1_points if winner_side == 'p1' else p2_points
        loser_points = p2_points if winner_side == 'p1' else p1_points
        return (
            f"{winner_name}, ağırlıklı sonuç puanlamasını {winner_points}-{loser_points} kazandı."
            f" {rule_text}{detail_text}"
        ).strip()

    def _draw_game_over_underlay_effects(self, clip_rect: pygame.Rect) -> None:
        if clip_rect.width <= 0 or clip_rect.height <= 0:
            return

        shake_x, shake_y = self.get_shake_offset()
        board_y = int(self.p1_offset_y + shake_y)
        p1_x = int(self.p1_offset_x + shake_x)
        p2_x = int(self.p2_offset_x + shake_x)
        previous_clip = self.screen.get_clip()
        try:
            self.screen.set_clip(clip_rect)
            self.draw_board(self.board1, self.current_piece1, p1_x, board_y, self.cell_size)
            self.draw_board(self.board2, self.current_piece2, p2_x, board_y, self.cell_size)
            if self.effects_enabled:
                self.draw_particles()
        finally:
            self.screen.set_clip(previous_clip)

    def _draw_game_over_screen(self):
        """Oyun sonu ekranı - online PvP sonuç panelinin local PvP varyantı."""
        width, height = self.window_width, self.window_height
        cx, cy = width // 2, height // 2
        ui_scale = self._ui_scale(min_scale=0.62, max_scale=1.16)
        s = lambda v, minimum=1: self._sx(v, ui_scale, minimum)

        self._game_over_peek_rect = None
        self._game_over_peek_active = False

        overlay = pygame.Surface((width, height), pygame.SRCALPHA)
        overlay.fill((1, 4, 14, 212))
        self.screen.blit(overlay, (0, 0))

        result_breakdown = self._build_local_result_breakdown()
        reason_text = self._build_local_result_reason_text(result_breakdown)
        lang = get_language()
        is_tr = lang == 'tr'

        p1_name = str(result_breakdown['p1_name'])
        p2_name = str(result_breakdown['p2_name'])
        score1 = int(result_breakdown['p1_score'])
        score2 = int(result_breakdown['p2_score'])
        lines1 = int(result_breakdown['p1_lines'])
        lines2 = int(result_breakdown['p2_lines'])
        winner_side = str(result_breakdown['winner'])

        if winner_side == 'draw':
            result_text = t('draw', 'BERABERE')
            result_color = UIColors.NEON_ORANGE
            icon_text = '='
            sub_text = t('draw_sub', 'Eşit güçte rakipler!')
        else:
            winner_name = p1_name if winner_side == 'p1' else p2_name
            result_text = f"{winner_name} {t('pvp_wins', 'KAZANDI!')}".strip()
            result_color = UIColors.NEON_GREEN
            icon_text = 'V'
            sub_text = t('victory_sub', 'Tebrikler, rakibini yendin!')

        panel_width = min(s(760), width - s(64))
        button_width = s(160)
        button_height = s(48)
        hint_font = retro_style.get_font(s(12, minimum=9), bold=False)
        reason_font_px = max(9, s(12, minimum=9))
        reason_wrap_w = max(s(280), panel_width - s(96))
        reason_font = retro_style.get_font(reason_font_px, bold=False)
        reason_lines = retro_style.wrap_text(reason_text, reason_font, reason_wrap_w)
        while len(reason_lines) > 4 and reason_font_px > 9:
            reason_font_px -= 1
            reason_font = retro_style.get_font(reason_font_px, bold=False)
            reason_lines = retro_style.wrap_text(reason_text, reason_font, reason_wrap_w)
        reason_line_gap = max(2, s(2, minimum=2))
        reason_panel_h = max(
            s(62),
            len(reason_lines) * reason_font.get_linesize()
            + max(0, len(reason_lines) - 1) * reason_line_gap
            + s(20),
        )

        card_gap = s(14)
        side_pad = s(28)
        stack_cards = panel_width < s(630)
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
            + button_height
            + s(12)
            + hint_font.get_height()
        )
        panel_height = max(s(560), content_bottom + s(24))
        panel_rect = pygame.Rect(cx - panel_width // 2, cy - panel_height // 2, panel_width, panel_height)
        self._draw_game_over_underlay_effects(panel_rect.inflate(-s(12), -s(12)))

        def _draw_alpha_rect(
            rect: pygame.Rect,
            color: tuple[int, int, int],
            alpha: int,
            radius: int = 0,
            width_arg: int = 0,
        ) -> None:
            surf = pygame.Surface(rect.size, pygame.SRCALPHA)
            pygame.draw.rect(surf, (*color[:3], alpha), surf.get_rect(), width_arg, border_radius=radius)
            self.screen.blit(surf, rect.topleft)

        def _draw_alpha_circle(
            center: tuple[int, int],
            radius: int,
            color: tuple[int, int, int],
            alpha: int,
            width_arg: int = 0,
        ) -> None:
            size = radius * 2 + max(2, width_arg * 2)
            surf = pygame.Surface((size, size), pygame.SRCALPHA)
            draw_center = (size // 2, size // 2)
            pygame.draw.circle(surf, (*color[:3], alpha), draw_center, radius, width_arg)
            self.screen.blit(surf, (center[0] - size // 2, center[1] - size // 2))

        halo_rect = panel_rect.inflate(s(28), s(28))
        halo = pygame.Surface(halo_rect.size, pygame.SRCALPHA)
        pygame.draw.rect(halo, (*result_color[:3], 26), halo.get_rect(), border_radius=s(18))
        self.screen.blit(halo, halo_rect.topleft)

        retro_style.draw_glass_panel(
            self.screen,
            panel_rect,
            alpha=218,
            border_color=(*result_color[:3], 190),
            glow=True,
        )
        pygame.draw.rect(
            self.screen,
            (*UIColors.NEON_CYAN[:3], 55),
            panel_rect.inflate(-s(10), -s(10)),
            1,
            border_radius=s(12),
        )

        eyebrow_font = retro_style.get_font(s(12, minimum=9), bold=True)
        eyebrow_text = t('menu_dashboard_pvp_local_label', 'Local PvP')
        eyebrow_surf = eyebrow_font.render(eyebrow_text, True, UIColors.NEON_CYAN)
        eyebrow_w = min(panel_rect.width - s(48), eyebrow_surf.get_width() + s(34))
        eyebrow_rect = pygame.Rect(0, 0, eyebrow_w, s(26))
        eyebrow_rect.center = (cx, panel_rect.y + s(28))
        _draw_alpha_rect(eyebrow_rect, UIColors.NEON_CYAN, 32, radius=s(13))
        pygame.draw.rect(self.screen, (*UIColors.NEON_CYAN[:3], 150), eyebrow_rect, 1, border_radius=s(13))
        self.screen.blit(eyebrow_surf, eyebrow_surf.get_rect(center=eyebrow_rect.center))

        icon_font = retro_style.get_font(s(42, minimum=28), bold=True)
        icon_surf = icon_font.render(icon_text, True, result_color)
        icon_rect = icon_surf.get_rect(center=(cx, panel_rect.y + s(70)))
        for offset, alpha in ((4, 24), (2, 38)):
            glow_icon = icon_font.render(icon_text, True, result_color)
            glow_icon.set_alpha(alpha)
            self.screen.blit(glow_icon, glow_icon.get_rect(center=(icon_rect.centerx + offset, icon_rect.centery + offset)))
        self.screen.blit(icon_surf, icon_rect)

        title_font = retro_style.get_fitting_font(result_text, s(38), panel_width - s(70), bold=True, min_size=s(20, minimum=16))
        title_surf = title_font.render(result_text, True, result_color)
        for offset, alpha in ((3, 26), (1, 44)):
            glow_title = title_font.render(result_text, True, result_color)
            glow_title.set_alpha(alpha)
            self.screen.blit(glow_title, glow_title.get_rect(center=(cx + offset, panel_rect.y + s(105) + offset)))
        self.screen.blit(title_surf, title_surf.get_rect(center=(cx, panel_rect.y + s(105))))

        sub_font = retro_style.get_fitting_font(sub_text, s(15, minimum=11), panel_width - s(90), bold=False, min_size=s(10, minimum=8))
        sub_surf = sub_font.render(sub_text, True, retro_style.text_secondary)
        self.screen.blit(sub_surf, sub_surf.get_rect(center=(cx, panel_rect.y + s(130))))

        def _status_for(side: str) -> tuple[str, tuple[int, int, int], bool, bool]:
            if winner_side == 'draw':
                return (t('draw', 'Berabere'), UIColors.NEON_ORANGE, False, False)
            is_winner = winner_side == side
            if is_winner:
                return (('Kazanan' if is_tr else 'Winner'), UIColors.NEON_GREEN, True, False)
            return (('Kaybeden' if is_tr else 'Loser'), UIColors.NEON_RED, False, True)

        def _draw_avatar(center: tuple[int, int], name: str, accent: tuple[int, int, int], size: int, active_color: tuple[int, int, int]) -> None:
            radius = size // 2
            for grow, alpha in ((s(10), 18), (s(5), 32)):
                _draw_alpha_circle(center, radius + grow, active_color, alpha)
            pygame.draw.circle(self.screen, (10, 16, 31), center, radius + s(5))
            pygame.draw.circle(self.screen, active_color, center, radius + s(5), s(2))
            pygame.draw.circle(self.screen, accent, center, radius + s(1), s(1))
            _draw_alpha_circle(center, radius, accent, 70)
            initial = (str(name).strip()[:1] or '?').upper()
            initial_font = retro_style.get_font(max(14, size // 2), bold=True)
            initial_surf = initial_font.render(initial, True, UIColors.TEXT_PRIMARY)
            self.screen.blit(initial_surf, initial_surf.get_rect(center=center))

        def _draw_player_card(card_rect: pygame.Rect, player: dict[str, object]) -> None:
            side = str(player['side'])
            accent = player['accent']
            status_text, status_color, is_winner, is_loser = _status_for(side)
            border_color = status_color if is_winner or is_loser else accent

            retro_style.draw_glass_panel(
                self.screen,
                card_rect,
                alpha=168,
                border_color=(*border_color[:3], 175 if is_winner else 105),
                glow=is_winner,
            )
            tint = pygame.Surface(card_rect.size, pygame.SRCALPHA)
            for y in range(card_rect.height):
                ratio = y / max(1, card_rect.height - 1)
                alpha = int((22 if is_winner else 12) * (1.0 - ratio * 0.55))
                pygame.draw.line(tint, (*accent[:3], alpha), (0, y), (card_rect.width, y))
            pygame.draw.rect(tint, (*status_color[:3], 18 if is_winner else 8), tint.get_rect(), border_radius=s(12))
            self.screen.blit(tint, card_rect.topleft)
            pygame.draw.rect(
                self.screen,
                (*border_color[:3], 220 if is_winner else 120),
                card_rect,
                s(2) if is_winner else 1,
                border_radius=s(12),
            )

            badge_font = retro_style.get_fitting_font(status_text.upper(), s(12, minimum=9), card_rect.width - s(34), bold=True, min_size=8)
            badge_surf = badge_font.render(status_text.upper(), True, status_color)
            badge_rect = pygame.Rect(
                card_rect.x + s(14),
                card_rect.y + s(12),
                min(card_rect.width - s(28), badge_surf.get_width() + s(24)),
                s(24),
            )
            _draw_alpha_rect(badge_rect, status_color, 34, radius=s(12))
            pygame.draw.rect(self.screen, (*status_color[:3], 140), badge_rect, 1, border_radius=s(12))
            self.screen.blit(badge_surf, badge_surf.get_rect(center=badge_rect.center))

            avatar_size = min(s(72), max(s(46), card_rect.height - s(52)))
            avatar_center = (
                card_rect.x + s(54),
                card_rect.y + card_rect.height // 2 + s(12 if card_rect.height >= s(145) else 8),
            )
            _draw_avatar(
                avatar_center,
                str(player['name']),
                accent,
                avatar_size,
                status_color if is_winner or is_loser else accent,
            )

            text_x = avatar_center[0] + avatar_size // 2 + s(18)
            text_w = max(s(80), card_rect.right - text_x - s(16))
            name_font = retro_style.get_fitting_font(str(player['name']), s(20, minimum=13), text_w, bold=True, min_size=s(10, minimum=8))
            name_color = UIColors.TEXT_PRIMARY if not is_loser else retro_style.text_secondary
            name_surf = name_font.render(str(player['name']), True, name_color)
            name_y = card_rect.y + s(48 if card_rect.height >= s(145) else 38)
            self.screen.blit(name_surf, name_surf.get_rect(midleft=(text_x, name_y)))

            line_y = name_y + s(18)
            pygame.draw.line(self.screen, (*accent[:3], 95), (text_x, line_y), (card_rect.right - s(16), line_y), 1)

            score_text = f'{t("score", "Skor")} {self._format_pvp_result_number(int(player["score"]))}'
            lines_text = f'{t("lines", "Satır")} {int(player["lines"])}'
            score_font = retro_style.get_fitting_font(score_text, s(13, minimum=10), text_w, bold=False, min_size=8)
            score_surf = score_font.render(score_text, True, retro_style.text_primary)
            lines_font = retro_style.get_fitting_font(lines_text, s(13, minimum=10), text_w, bold=False, min_size=8)
            lines_surf = lines_font.render(lines_text, True, retro_style.text_secondary)
            self.screen.blit(score_surf, score_surf.get_rect(midleft=(text_x, line_y + s(18))))
            self.screen.blit(lines_surf, lines_surf.get_rect(midleft=(text_x, line_y + s(40))))

        cards_y = panel_rect.y + header_h
        player_cards = [
            {
                'side': 'p1',
                'name': p1_name,
                'score': score1,
                'lines': lines1,
                'accent': UIColors.NEON_CYAN,
            },
            {
                'side': 'p2',
                'name': p2_name,
                'score': score2,
                'lines': lines2,
                'accent': UIColors.NEON_MAGENTA,
            },
        ]
        if stack_cards:
            card_width = panel_rect.width - side_pad * 2
            card_rects = [
                pygame.Rect(panel_rect.x + side_pad, cards_y, card_width, card_h),
                pygame.Rect(panel_rect.x + side_pad, cards_y + card_h + card_gap, card_width, card_h),
            ]
        else:
            card_width = (panel_rect.width - side_pad * 2 - card_gap) // 2
            card_rects = [
                pygame.Rect(panel_rect.x + side_pad, cards_y, card_width, card_h),
                pygame.Rect(panel_rect.x + side_pad + card_width + card_gap, cards_y, card_width, card_h),
            ]
        for card_rect, player in zip(card_rects, player_cards):
            _draw_player_card(card_rect, player)

        def _side_color(side: str) -> tuple[int, int, int]:
            if side == 'p1':
                return UIColors.NEON_CYAN
            if side == 'p2':
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
        chip_width = (panel_rect.width - side_pad * 2 - chip_gap * 2) // 3
        chip_font_base = s(12, minimum=9)
        for idx, (label, owner) in enumerate(criteria):
            chip_rect = pygame.Rect(panel_rect.x + side_pad + idx * (chip_width + chip_gap), criteria_y, chip_width, criteria_h)
            owner_color = _side_color(owner)
            pygame.draw.rect(self.screen, (12, 18, 32), chip_rect, border_radius=s(9))
            pygame.draw.rect(self.screen, (*owner_color[:3], 95), chip_rect, 1, border_radius=s(9))
            chip_text = f'{label}: {self._local_result_side_label(owner, is_tr)}'
            chip_font = retro_style.get_fitting_font(chip_text, chip_font_base, chip_rect.width - s(16), bold=True, min_size=8)
            chip_surf = chip_font.render(chip_text, True, owner_color)
            self.screen.blit(chip_surf, chip_surf.get_rect(center=chip_rect.center))

        reason_panel_y = criteria_y + criteria_h + s(14)
        reason_panel_rect = pygame.Rect(panel_rect.x + s(34), reason_panel_y, panel_rect.width - s(68), reason_panel_h)
        retro_style.draw_glass_panel(
            self.screen,
            reason_panel_rect,
            alpha=132,
            border_color=(*result_color[:3], 120),
        )
        _draw_alpha_rect(reason_panel_rect.inflate(-s(8), -s(8)), result_color, 50, radius=s(10), width_arg=1)
        reason_inner = reason_panel_rect.inflate(-s(16), -s(10))
        reason_total_h = (
            len(reason_lines) * reason_font.get_linesize()
            + max(0, len(reason_lines) - 1) * reason_line_gap
        )
        reason_y = reason_inner.centery - reason_total_h // 2
        for line in reason_lines:
            line_surf = reason_font.render(line, True, retro_style.text_secondary)
            self.screen.blit(line_surf, line_surf.get_rect(midtop=(reason_inner.centerx, reason_y)))
            reason_y += reason_font.get_linesize() + reason_line_gap

        button_gap = s(20)
        button_y = reason_panel_rect.bottom + s(18)
        mouse_pos = get_mouse_pos() or (-9999, -9999)

        restart_rect = pygame.Rect(cx - button_width - button_gap // 2, button_y, button_width, button_height)
        menu_rect = pygame.Rect(cx + button_gap // 2, button_y, button_width, button_height)

        retro_style.draw_uniform_button(
            self.screen,
            restart_rect,
            t('rematch', 'Tekrar Oyna'),
            sub_text='R',
            color_code=UIColors.NEON_GREEN,
            state='hover' if restart_rect.collidepoint(mouse_pos) else 'normal',
        )
        retro_style.draw_uniform_button(
            self.screen,
            menu_rect,
            t('back_to_menu', 'Çıkış'),
            sub_text='ESC',
            color_code=retro_style.secondary,
            state='hover' if menu_rect.collidepoint(mouse_pos) else 'normal',
        )
        self._game_over_restart_rect = restart_rect
        self._game_over_menu_rect = menu_rect

        hint_surf = hint_font.render(t('campaign_failed_hint', '[R] Retry | [ESC] Menu'), True, retro_style.text_muted)
        self.screen.blit(hint_surf, hint_surf.get_rect(center=(cx, panel_rect.bottom - s(20))))

    def _reset_lock_delay_state(self, player: int) -> None:
        if player == 1:
            self.p1_grounded = False
            self.p1_lock_timer = 0.0
        else:
            self.p2_grounded = False
            self.p2_lock_timer = 0.0

    def _mark_player_grounded(self, player: int) -> None:
        if player == 1:
            if not getattr(self, 'p1_grounded', False):
                self.p1_grounded = True
                self.p1_lock_timer = 0.0
        else:
            if not getattr(self, 'p2_grounded', False):
                self.p2_grounded = True
                self.p2_lock_timer = 0.0

    def _player_piece_touching_ground(self, player: int) -> bool:
        if player == 1:
            board = self.board1
            piece = self.current_piece1
        else:
            board = self.board2
            piece = self.current_piece2
        if piece is None or board.is_game_over():
            return False
        return not board.is_valid_position(piece, dy=1)

    def _update_lock_delay_for_player(self, player: int, delta_time: float) -> bool:
        if player == 1:
            board = self.board1
            piece = self.current_piece1
        else:
            board = self.board2
            piece = self.current_piece2
        if piece is None or board.is_game_over():
            self._reset_lock_delay_state(player)
            return False

        if not self._player_piece_touching_ground(player):
            self._reset_lock_delay_state(player)
            return False

        if not getattr(self, 'enable_lock_delay', True):
            self.lock_and_new_piece(player)
            return True

        self._mark_player_grounded(player)
        lock_delay = max(0.0, float(getattr(self, 'lock_delay', DEFAULT_LOCK_DELAY)))
        if player == 1:
            self.p1_lock_timer += max(0.0, float(delta_time or 0.0))
            if self.p1_lock_timer >= lock_delay:
                self.lock_and_new_piece(1)
                return True
        else:
            self.p2_lock_timer += max(0.0, float(delta_time or 0.0))
            if self.p2_lock_timer >= lock_delay:
                self.lock_and_new_piece(2)
                return True
        return False

    def _update_lock_delay(self, delta_time: float) -> None:
        self._update_lock_delay_for_player(1, delta_time)
        self._update_lock_delay_for_player(2, delta_time)

    def _try_move_left_p1(self):
        """Oyuncu 1 sola hareket"""
        if self.current_piece1 is None:
            return False
        self.current_piece1.x -= 1
        if not self.board1.is_valid_position(self.current_piece1):
            self.current_piece1.x += 1
            return False
        return True
    
    def _try_move_right_p1(self):
        """Oyuncu 1 sağa hareket"""
        if self.current_piece1 is None:
            return False
        self.current_piece1.x += 1
        if not self.board1.is_valid_position(self.current_piece1):
            self.current_piece1.x -= 1
            return False
        return True
    
    def _try_move_left_p2(self):
        """Oyuncu 2 sola hareket"""
        if self.current_piece2 is None:
            return False
        self.current_piece2.x -= 1
        if not self.board2.is_valid_position(self.current_piece2):
            self.current_piece2.x += 1
            return False
        return True
    
    def _try_move_right_p2(self):
        """Oyuncu 2 sağa hareket"""
        if self.current_piece2 is None:
            return False
        self.current_piece2.x += 1
        if not self.board2.is_valid_position(self.current_piece2):
            self.current_piece2.x -= 1
            return False
        return True
    
    def _update_das(self, delta_time):
        """Her iki oyuncu için DAS güncelle"""
        try:
            delay_ms = float(self.settings_manager.get('das_delay', DAS_DELAY)) if self.settings_manager else float(DAS_DELAY)
        except Exception:
            delay_ms = float(DAS_DELAY)
        try:
            repeat_ms = float(self.settings_manager.get('das_repeat', DAS_REPEAT)) if self.settings_manager else float(DAS_REPEAT)
        except Exception:
            repeat_ms = float(DAS_REPEAT)
        delay_ms = max(0.0, delay_ms)
        repeat_ms = max(1.0, repeat_ms)
        
        # Oyuncu 1 DAS
        if self.p1_das_direction != 0 and self.current_piece1 and not self.board1.is_game_over():
            self.p1_das_timer += delta_time
            if not self.p1_das_charged:
                if self.p1_das_timer >= delay_ms:
                    overshoot = max(0.0, self.p1_das_timer - delay_ms)
                    self.p1_das_charged = True
                    self.p1_das_repeat_timer = overshoot
                    if self.p1_das_direction == -1:
                        if self._try_move_left_p1():
                            self.sound.play('move')
                    elif self.p1_das_direction == 1:
                        if self._try_move_right_p1():
                            self.sound.play('move')
            else:
                self.p1_das_repeat_timer += delta_time
                while self.p1_das_repeat_timer >= repeat_ms:
                    self.p1_das_repeat_timer -= repeat_ms
                    if self.p1_das_direction == -1:
                        if self._try_move_left_p1():
                            self.sound.play('move')
                        else:
                            self.p1_das_repeat_timer = 0
                            break
                    elif self.p1_das_direction == 1:
                        if self._try_move_right_p1():
                            self.sound.play('move')
                        else:
                            self.p1_das_repeat_timer = 0
                            break
        
        # Oyuncu 2 DAS
        if self.p2_das_direction != 0 and self.current_piece2 and not self.board2.is_game_over():
            self.p2_das_timer += delta_time
            if not self.p2_das_charged:
                if self.p2_das_timer >= delay_ms:
                    overshoot = max(0.0, self.p2_das_timer - delay_ms)
                    self.p2_das_charged = True
                    self.p2_das_repeat_timer = overshoot
                    if self.p2_das_direction == -1:
                        if self._try_move_left_p2():
                            self.sound.play('move')
                    elif self.p2_das_direction == 1:
                        if self._try_move_right_p2():
                            self.sound.play('move')
            else:
                self.p2_das_repeat_timer += delta_time
                while self.p2_das_repeat_timer >= repeat_ms:
                    self.p2_das_repeat_timer -= repeat_ms
                    if self.p2_das_direction == -1:
                        if self._try_move_left_p2():
                            self.sound.play('move')
                        else:
                            self.p2_das_repeat_timer = 0
                            break
                    elif self.p2_das_direction == 1:
                        if self._try_move_right_p2():
                            self.sound.play('move')
                        else:
                            self.p2_das_repeat_timer = 0
                            break
    
    def _update_soft_drop(self, delta_time):
        """Her iki oyuncu için soft drop (hızlı düşüş) güncelle"""
        # Oyuncu 1 soft drop
        if self.p1_soft_drop_active and self.current_piece1 and not self.board1.is_game_over():
            self.p1_soft_drop_timer += delta_time
            if self.p1_soft_drop_timer >= self.soft_drop_speed:
                self.p1_soft_drop_timer = 0
                self.current_piece1.y += 1
                if not self.board1.is_valid_position(self.current_piece1):
                    self.current_piece1.y -= 1
                    self._mark_player_grounded(1)
                else:
                    self._reset_lock_delay_state(1)
        
        # Oyuncu 2 soft drop
        if self.p2_soft_drop_active and self.current_piece2 and not self.board2.is_game_over():
            self.p2_soft_drop_timer += delta_time
            if self.p2_soft_drop_timer >= self.soft_drop_speed:
                self.p2_soft_drop_timer = 0
                self.current_piece2.y += 1
                if not self.board2.is_valid_position(self.current_piece2):
                    self.current_piece2.y -= 1
                    self._mark_player_grounded(2)
                else:
                    self._reset_lock_delay_state(2)

    def lock_and_new_piece(self, player):
        """Parçayı kilitle ve yeni parça oluştur"""
        if player == 1:
            if self.effects_enabled:
                color_matrix = getattr(self.current_piece1, 'color_matrix', None)
                for row_i, row in enumerate(self.current_piece1.shape):
                    for col_i, cell in enumerate(row):
                        if not cell:
                            continue
                        board_col = self.current_piece1.x + col_i
                        board_row = self.current_piece1.y + row_i
                        if not (0 <= board_col < BOARD_WIDTH and 0 <= board_row < BOARD_HEIGHT):
                            continue
                        cell_color = self.current_piece1.color
                        if color_matrix is not None:
                            try:
                                matrix_color = color_matrix[row_i][col_i]
                                if matrix_color is not None:
                                    cell_color = matrix_color
                            except Exception:
                                pass
                        screen_x = self.p1_offset_x + board_col * self.cell_size + self.cell_size // 2
                        screen_y = self.p1_offset_y + board_row * self.cell_size + self.cell_size // 2
                        self.create_lock_explosion(screen_x, screen_y, cell_color, cell_size=self.cell_size)
            
            lines = self.board1.lock_piece(self.current_piece1)
            self._mark_locked_board_dirty(1)

            # Lock-out kontrolü (Tetris Guideline)
            if self.board1.is_game_over():
                self._eliminate_player(1)
                return

            # Satır temizlenmiyorsa blok kilitlenme sesi çal
            if lines == 0:
                self.sound.play('lock')
            
            if lines > 0:
                # Gelişmiş satır temizleme efektleri (ana oyundaki gibi)
                if self.board1.last_cleared_lines and self.effects_enabled:
                    cleared_rows = list(self.board1.last_cleared_lines)
                    self.p1_line_flash_rows = cleared_rows
                    self.p1_line_flash_timer = 20  # Ana oyunla aynı
                    self.p1_line_glow_alpha = 255
                    self.p1_line_sweep_rows = cleared_rows
                    self.p1_line_sweep_progress = 0.0
                    self.p1_line_sweep_active = True
                    # Pending row snapshot — sweep ön kenarına kadar silinen
                    # blokları görünür tut (Mystery / Game / Coop ile parity).
                    self.p1_line_pending_rows = list(cleared_rows)
                    try:
                        snap = getattr(self.board1, 'last_cleared_colors', {}) or {}
                        self.p1_line_pending_colors = {
                            int(r): list(snap[r]) for r in cleared_rows if r in snap
                        }
                    except Exception:
                        self.p1_line_pending_colors = {}
                    
                    # Parçacık efektleri (ana oyundaki gelişmiş versiyon)
                    self.create_line_clear_particles(
                        cleared_rows, 
                        self.p1_offset_x, 
                        self.p1_offset_y, 
                        self.cell_size,
                        board=self.board1
                    )
                    
                    # Dalga efektleri - her satır için (ana oyunla aynı parametreler)
                    _queue_wave_effects(
                        self.p1_wave_effects,
                        cleared_rows,
                        self.p1_offset_x,
                        self.p1_offset_y,
                        self.cell_size,
                        BOARD_WIDTH,
                    )

                    # Ekran titremesi (ana oyunla aynı)
                    if lines < 4:
                        self.trigger_screen_shake(intensity=3 + lines * 2, duration=8 / 60.0)
                    self._start_block_fall_animation(1, self.board1, cleared_rows)
                
                self.sound.play('line' if lines < 4 else 'tetris')
                
                # Combo mesajı (DOUBLE/TRIPLE/QUADRIX)
                if lines == 4:
                    self.p1_combo_message = "QUADRIX!"
                    self.p1_combo_message_time = 120
                elif lines >= 2:
                    if lines == 2:
                        self.p1_combo_message = "DOUBLE!"
                    elif lines == 3:
                        self.p1_combo_message = "TRIPLE!"
                    else:
                        self.p1_combo_message = f"{lines}x CLEAR!"
                    combo_count = getattr(self.board1, 'combo', 0)
                    if combo_count > 1:
                        self.p1_combo_message += f"  x{combo_count} Combo"
                    self.p1_combo_message_time = 120
                else:
                    combo_count = getattr(self.board1, 'combo', 0)
                    if combo_count > 1:
                        self.p1_combo_message = f"x{combo_count} Combo!"
                        self.p1_combo_message_time = 90

                # Gamepad titreşimi - satır temizleme
                try:
                    from gamepad_manager import get_gamepad_manager
                    if lines >= 4:
                        get_gamepad_manager().rumble(0.8, 1.0, 400)
                    elif lines >= 2:
                        get_gamepad_manager().rumble(0.4, 0.5, 200)
                except Exception:
                    pass

                # Multi-line / Quadrix parçacık merkez patlaması — ortak helper
                # ile (Game / OnlinePvP / Coop ile parity)
                _trigger_combo_burst(
                    self,
                    cleared_rows or [],
                    int(lines),
                    self.p1_offset_x,
                    self.p1_offset_y,
                    self.cell_size,
                    BOARD_WIDTH,
                    BOARD_HEIGHT,
                    multi_line_colors=[CYAN, (100, 200, 255), (150, 220, 255)],
                    quadrix_colors=[YELLOW, ORANGE, (255, 215, 0), CYAN],
                )
                if lines == 4 and self.effects_enabled:
                    self.trigger_screen_shake(intensity=15, duration=20 / 60.0)
            
            self.current_piece1 = self.next_piece1
            skip_hidden_rows(self.current_piece1, self.board1)
            self.next_piece1 = self.get_next_piece()
            self.can_hold1 = True
            self._reset_lock_delay_state(1)
        
        else:  # player == 2
            if self.effects_enabled:
                color_matrix = getattr(self.current_piece2, 'color_matrix', None)
                for row_i, row in enumerate(self.current_piece2.shape):
                    for col_i, cell in enumerate(row):
                        if not cell:
                            continue
                        board_col = self.current_piece2.x + col_i
                        board_row = self.current_piece2.y + row_i
                        if not (0 <= board_col < BOARD_WIDTH and 0 <= board_row < BOARD_HEIGHT):
                            continue
                        cell_color = self.current_piece2.color
                        if color_matrix is not None:
                            try:
                                matrix_color = color_matrix[row_i][col_i]
                                if matrix_color is not None:
                                    cell_color = matrix_color
                            except Exception:
                                pass
                        screen_x = self.p2_offset_x + board_col * self.cell_size + self.cell_size // 2
                        screen_y = self.p2_offset_y + board_row * self.cell_size + self.cell_size // 2
                        self.create_lock_explosion(screen_x, screen_y, cell_color, cell_size=self.cell_size)
            
            lines = self.board2.lock_piece(self.current_piece2)
            self._mark_locked_board_dirty(2)

            # Lock-out kontrolü (Tetris Guideline)
            if self.board2.is_game_over():
                self._eliminate_player(2)
                return

            # Satır temizlenmiyorsa blok kilitlenme sesi çal
            if lines == 0:
                self.sound.play('lock')
            
            if lines > 0:
                # Gelişmiş satır temizleme efektleri (ana oyundaki gibi)
                if self.board2.last_cleared_lines and self.effects_enabled:
                    cleared_rows = list(self.board2.last_cleared_lines)
                    self.p2_line_flash_rows = cleared_rows
                    self.p2_line_flash_timer = 20  # Ana oyunla aynı
                    self.p2_line_glow_alpha = 255
                    self.p2_line_sweep_rows = cleared_rows
                    self.p2_line_sweep_progress = 0.0
                    self.p2_line_sweep_active = True
                    # Pending row snapshot (Mystery / Game / Coop ile parity)
                    self.p2_line_pending_rows = list(cleared_rows)
                    try:
                        snap = getattr(self.board2, 'last_cleared_colors', {}) or {}
                        self.p2_line_pending_colors = {
                            int(r): list(snap[r]) for r in cleared_rows if r in snap
                        }
                    except Exception:
                        self.p2_line_pending_colors = {}
                    
                    # Parçacık efektleri (ana oyundaki gelişmiş versiyon)
                    self.create_line_clear_particles(
                        cleared_rows, 
                        self.p2_offset_x, 
                        self.p2_offset_y, 
                        self.cell_size,
                        board=self.board2
                    )
                    
                    # Dalga efektleri - her satır için (ana oyunla aynı parametreler)
                    _queue_wave_effects(
                        self.p2_wave_effects,
                        cleared_rows,
                        self.p2_offset_x,
                        self.p2_offset_y,
                        self.cell_size,
                        BOARD_WIDTH,
                    )

                    # Ekran titremesi (ana oyunla aynı)
                    if lines < 4:
                        self.trigger_screen_shake(intensity=3 + lines * 2, duration=8 / 60.0)
                    self._start_block_fall_animation(2, self.board2, cleared_rows)
                
                self.sound.play('line' if lines < 4 else 'tetris')
                
                # Combo mesajı (DOUBLE/TRIPLE/QUADRIX)
                if lines == 4:
                    self.p2_combo_message = "QUADRIX!"
                    self.p2_combo_message_time = 120
                elif lines >= 2:
                    if lines == 2:
                        self.p2_combo_message = "DOUBLE!"
                    elif lines == 3:
                        self.p2_combo_message = "TRIPLE!"
                    else:
                        self.p2_combo_message = f"{lines}x CLEAR!"
                    combo_count = getattr(self.board2, 'combo', 0)
                    if combo_count > 1:
                        self.p2_combo_message += f"  x{combo_count} Combo"
                    self.p2_combo_message_time = 120
                else:
                    combo_count = getattr(self.board2, 'combo', 0)
                    if combo_count > 1:
                        self.p2_combo_message = f"x{combo_count} Combo!"
                        self.p2_combo_message_time = 90

                # Gamepad titreşimi - satır temizleme
                try:
                    from gamepad_manager import get_gamepad_manager
                    if lines >= 4:
                        get_gamepad_manager().rumble(0.8, 1.0, 400)
                    elif lines >= 2:
                        get_gamepad_manager().rumble(0.4, 0.5, 200)
                except Exception:
                    pass

                # Multi-line / Quadrix parçacık merkez patlaması — ortak helper
                # ile (Game / OnlinePvP / Coop ile parity, P2 magenta paletini
                # koruyarak)
                _trigger_combo_burst(
                    self,
                    cleared_rows or [],
                    int(lines),
                    self.p2_offset_x,
                    self.p2_offset_y,
                    self.cell_size,
                    BOARD_WIDTH,
                    BOARD_HEIGHT,
                    multi_line_colors=[MAGENTA, (200, 100, 255), (220, 150, 255)],
                    quadrix_colors=[YELLOW, ORANGE, (255, 215, 0), MAGENTA],
                )
                if lines == 4 and self.effects_enabled:
                    self.trigger_screen_shake(intensity=15, duration=20 / 60.0)
            
            self.current_piece2 = self.next_piece2
            skip_hidden_rows(self.current_piece2, self.board2)
            self.next_piece2 = self.get_next_piece()
            self.can_hold2 = True
            self._reset_lock_delay_state(2)
    
    def determine_winner(self):
        """Kazananı ağırlıklı sonuç puanlamasıyla belirle."""
        result = self._build_local_result_breakdown()
        winner_side = str(result.get('winner', 'draw'))
        if winner_side == 'p1':
            self.winner = 1
        elif winner_side == 'p2':
            self.winner = 2
        else:
            self.winner = 'draw'

        print(
            "[LocalPvP] Agirlikli sonuc puanlama "
            f"p1(score={result['p1_score']}, lines={result['p1_lines']}, board={result['p1_board_point']}) "
            f"p2(score={result['p2_score']}, lines={result['p2_lines']}, board={result['p2_board_point']}) "
            f"=> totals {result['p1_points']}-{result['p2_points']} winner={winner_side}"
        )
        
        self.game_over = True
        # Gamepad titreşimi - game over
        try:
            from gamepad_manager import get_gamepad_manager
            get_gamepad_manager().rumble(1.0, 1.0, 600)
        except Exception:
            pass
        self.sound.play('gameover')
        
        # Kullanıcı istatistiklerini güncelle
        if self.user_manager:
            # PvP oyun sayısını artır ve kazanan/kaybedeni kaydet
            if self.winner == 1:
                self.user_manager.update_pvp_stats(win=True)
                print(f"💾 PvP istatistikleri güncellendi: KAZANDI")
            elif self.winner == 2:
                self.user_manager.update_pvp_stats(win=False)
                print(f"💾 PvP istatistikleri güncellendi: KAYBETTİ")
            else:
                # Beraberlik - oyun sayısını artır ama kazanan/kaybeden yok
                self.user_manager.update_pvp_stats(win=False)
                print(f"💾 PvP istatistikleri güncellendi: BERABERE")
    
    def create_particles(self, count, x=None, y=None, colors=None, speed=5):
        """Partiküller oluştur - optimize edilmiş"""
        if not self._particle_effects_enabled():
            return
        
        # Varsayılan konum
        if x is None:
            x = random.randint(0, self.window_width)
        if y is None:
            y = random.randint(0, self.window_height // 2)
        
        # Varsayılan renkler
        if colors is None:
            colors = [CYAN, YELLOW, MAGENTA, GREEN, RED]
        
        for _ in range(max(1, int(count * self._particle_effects_multiplier()))):
            particle = {
                'x': float(x),
                'y': float(y),
                'vx': speed * (random.random() * 2 - 1),
                'vy': speed * (random.random() * 2 - 1),
                'life': random.randint(20, 40),  # Daha kısa ömür
                'max_life': 40,
                'color': random.choice(colors),
                'size': random.randint(2, 4)  # Daha küçük
            }
            self.particles.append(particle)
    
    def create_line_clear_particles(self, cleared_rows, board_offset_x, board_offset_y, cell_size, board=None):
        """Satır temizlendiğinde SÜPER parçacıklar oluştur - ANA OYUN İLE AYNI (GELİŞTİRİLMİŞ VERSİYON)"""
        if not self._particle_effects_enabled():
            return
        
        # Parlak renkler paleti
        sparkle_colors = [
            (255, 255, 255),  # Beyaz
            (255, 255, 200),  # Sıcak beyaz
            (255, 215, 0),    # Altın
            (0, 255, 255),    # Cyan
            (255, 100, 255),  # Pembe
        ]
        
        for row in cleared_rows:
            # Satırdaki tüm hücrelerden parçacıklar saçıl
            for col in range(BOARD_WIDTH):
                # Hücrenin ekran pozisyonu
                cell_x = board_offset_x + col * cell_size + cell_size // 2
                cell_y = board_offset_y + row * cell_size + cell_size // 2
                
                # Hücre rengi - last_cleared_colors'dan al (satır silinmeden kaydedilmiş)
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
                
                # === ANA PATLAMA PARÇACIKLARı ===
                # Her hücreden 6-10 ana parçacık
                for _ in range(max(1, int(random.randint(6, 10) * self._particle_effects_multiplier()))):
                    speed = random.uniform(4, 12)
                    
                    # Yatay hareket daha baskın (satır boyunca saçılım)
                    vx = speed * random.uniform(-1.5, 1.5)
                    vy = speed * random.uniform(-1, 0.5) - 2  # Yukarı doğru
                    
                    particle = {
                        'x': float(cell_x + random.randint(-3, 3)),
                        'y': float(cell_y + random.randint(-3, 3)),
                        'vx': vx,
                        'vy': vy,
                        'life': random.randint(40, 80),
                        'max_life': 80,
                        'color': cell_color,
                        'size': random.randint(3, 7),
                        'glow': True
                    }
                    self.particles.append(particle)
                
                # === KIVILCIM PARÇACIKLARı ===
                # Her 2 hücreden 1 kıvılcım
                if col % 2 == 0:
                    for _ in range(max(1, int(random.randint(2, 4) * self._particle_effects_multiplier()))):
                        spark_color = random.choice(sparkle_colors)
                        spark_speed = random.uniform(8, 15)
                        
                        particle = {
                            'x': float(cell_x),
                            'y': float(cell_y),
                            'vx': spark_speed * random.uniform(-1, 1),
                            'vy': -spark_speed * random.uniform(0.3, 1) - 5,  # Güçlü yukarı
                            'life': random.randint(20, 40),
                            'max_life': 40,
                            'color': spark_color,
                            'size': random.randint(2, 4),
                            'glow': True,
                            'spark': True  # Kıvılcım işareti
                        }
                        self.particles.append(particle)
            
            # === SATIR ORTASINDAN YILDIZ EFEKTİ ===
            center_x = board_offset_x + (BOARD_WIDTH * cell_size) // 2
            center_y = board_offset_y + row * cell_size + cell_size // 2
            
            # Merkezi patlama - yıldız şeklinde
            star_count = max(4, int(16 * self._particle_effects_multiplier()))
            for i in range(star_count):
                angle = (i / star_count) * 2 * math.pi
                star_speed = random.uniform(6, 14)
                
                particle = {
                    'x': float(center_x),
                    'y': float(center_y),
                    'vx': math.cos(angle) * star_speed,
                    'vy': math.sin(angle) * star_speed - 2,
                    'life': random.randint(30, 60),
                    'max_life': 60,
                    'color': random.choice(sparkle_colors),
                    'size': random.randint(4, 8),
                    'glow': True
                }
                self.particles.append(particle)
    
    def update_particles(self, dt_ms: float | None = None):
        """Partikülleri güncelle (dt tabanlı - game.py ile aynı akıcılık)"""
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
            particle['vy'] += 0.5 * dt_frames  # Yerçekimi (dt tabanlı)
            particle['vx'] *= 0.98 ** dt_frames  # Hava sürtünmesi (dt tabanlı)
            particle['life'] = float(particle.get('life', 0)) - dt_frames
            if particle['life'] > 0:
                alive.append(particle)
        self.particles = alive

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

    def _get_drop_trail_store(self, player: int):
        return self.p1_drop_trails if player == 1 else self.p2_drop_trails

    def _create_drop_trail(self, player: int, piece: Piece | None, board_x: int, board_y: int,
                           cell_size: int, start_y: int, distance: int,
                           trail_type: str = 'hard'):
        """Oyuncu bazlı sert düşüş izi oluştur."""
        if not self.effects_enabled or not piece or distance <= 0:
            return

        trail_store = self._get_drop_trail_store(player)
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
                trail_store.append({
                    'x': block_x + (cell_size - trail_width) // 2,
                    'y': block_y,
                    'width': trail_width,
                    'height': trail_height,
                    'color': bright_color,
                    'alpha': alpha,
                    'fade_speed': fade_speed,
                })

    def _update_drop_trails(self, dt_frames: float):
        """Oyuncu bazlı trail efektlerini güncelle."""
        for trail_store_name in ('p1_drop_trails', 'p2_drop_trails'):
            trail_store = getattr(self, trail_store_name, [])
            for trail in trail_store:
                trail['alpha'] -= trail['fade_speed'] * dt_frames
            setattr(self, trail_store_name, [trail for trail in trail_store if trail['alpha'] > 0])

    def _draw_drop_trails(self, player: int):
        """İlgili oyuncunun drop trail efektlerini çiz."""
        for trail in self._get_drop_trail_store(player):
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
    
    def create_ambient_particles(self):
        """Arka plan için ambient parçacıklar oluştur"""
        if not self._particle_effects_enabled():
            return
        for _ in range(max(10, int(random.randint(50, 100) * self._particle_effects_multiplier()))):
            particle = {
                'x': random.uniform(0, self.window_width),
                'y': random.uniform(0, self.window_height),
                'vx': random.uniform(-0.5, 0.5),
                'vy': random.uniform(0.2, 0.8),
                'size': random.randint(1, 3),
                'alpha': random.randint(50, 150),
                'pulse': random.uniform(0, 6.28),
                'pulse_speed': random.uniform(0.02, 0.05)
            }
            self.ambient_particles.append(particle)
    
    def update_ambient_particles(self, dt_ms: float | None = None):
        """Ambient parçacıkları güncelle (dt tabanlı)"""
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
        """Ambient parçacıkları çiz"""
        eo = getattr(self, 'effects_opacity', 1.0)
        if eo <= 0:
            return
        for particle in self.ambient_particles:
            pulse_alpha = int(particle['alpha'] + math.sin(particle['pulse']) * 30)
            pulse_alpha = max(30, min(180, pulse_alpha))
            pulse_alpha = int(pulse_alpha * eo)
            
            color = (200, 200, 255)
            pos = (int(particle['x']), int(particle['y']))
            size = particle['size']
            
            if size > 1:
                glow_surface = self._get_ambient_sprite(size, pulse_alpha // 3, glow=True)
                self.screen.blit(glow_surface, (pos[0] - glow_surface.get_width() // 2, pos[1] - glow_surface.get_height() // 2))
            
            particle_surface = self._get_ambient_sprite(size, pulse_alpha, glow=False)
            self.screen.blit(particle_surface, (pos[0] - particle_surface.get_width() // 2, pos[1] - particle_surface.get_height() // 2))
    
    def trigger_hard_drop_screen_shake(self):
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
    
    def get_shake_offset(self):
        """Ekran titremesi için offset hesapla"""
        return sample_screen_shake_offset(self)
    
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
        """Ana oyun temeli: texture varsa dilimle + jelly border, yoksa jelly."""
        target = dst or self.screen
        if texture_surface is not None and texture_slice is not None:
            self._draw_texture_cell(x, y, size, texture_surface, texture_slice, target)
            draw_jelly_border(target, x, y, size, color)
            return
        draw_jelly_block(target, x, y, size, color)
    
    def draw_particles(self):
        """Partikülleri çiz - İYİLEŞTİRİLMİŞ GLOW EFEKTİ"""
        for particle in self.particles:
            # Alpha değeri (sönme efekti)
            alpha_ratio = particle['life'] / particle['max_life']
            alpha = int(255 * alpha_ratio)
            
            # Boyut (küçülme efekti)
            size = max(1, int(particle['size'] * alpha_ratio))
            
            color = particle['color']
            pos = (int(particle['x']), int(particle['y']))
            
            # Glow efekti varsa
            if particle.get('glow', False) and size > 2:
                # Dış halo
                halo_size = size + 4
                halo_color = tuple(min(255, int(c * 0.6)) for c in color[:3])
                halo_surface = self._effect_surface_cache.get_circle_surface(halo_size, (*halo_color, int(alpha * 0.3)))
                self.screen.blit(halo_surface, (pos[0] - halo_size, pos[1] - halo_size))
                
                # Orta halo
                mid_size = size + 2
                mid_color = tuple(min(255, int(c * 0.8)) for c in color[:3])
                mid_surface = self._effect_surface_cache.get_circle_surface(mid_size, (*mid_color, int(alpha * 0.5)))
                self.screen.blit(mid_surface, (pos[0] - mid_size, pos[1] - mid_size))
            
            # Ana parçacık
            pygame.draw.circle(self.screen, color, pos, size)
            
            # Parlama efekti (iç kısım) - daha parlak
            if size > 2:
                inner_size = max(1, size - 1)
                inner_color = tuple(min(255, c + 80) for c in color[:3])
                pygame.draw.circle(self.screen, inner_color, pos, inner_size)
                
                # Merkez ışık noktası
                if size > 3:
                    core_color = tuple(min(255, c + 120) for c in color[:3])
                    pygame.draw.circle(self.screen, core_color, pos, 1)
    
    def create_firework(self, x, y, player=None):
        """Havai fişek efekti oluştur - optimize edilmiş"""
        if not self._particle_effects_enabled():
            return
        
        # Oyuncuya özel renkler
        if player == 1:
            colors = [(0, 255, 255), (0, 200, 255), (100, 255, 255), (255, 255, 255)]  # Cyan tonları
        elif player == 2:
            colors = [(255, 0, 255), (255, 100, 255), (200, 0, 255), (255, 255, 255)]  # Magenta tonları
        else:
            colors = [(255, 215, 0), (255, 165, 0), (255, 50, 50), (50, 255, 50)]  # Karışık
        
        main_color = random.choice(colors)
        
        # Dairesel patlama - optimize edilmiş
        particle_count = random.randint(12, 18)  # 22-32'den düşürüldü
        for i in range(particle_count):
            angle = (i / particle_count) * 2 * 3.14159
            speed = random.uniform(2, 5)  # Daha yavaş
            
            particle = {
                'x': float(x),
                'y': float(y),
                'vx': speed * (random.random() * 0.5 + 0.75) * (1 if random.random() > 0.5 else -1),
                'vy': speed * (random.random() * 0.5 + 0.75) * (1 if random.random() > 0.5 else -1) - 2,
                'life': random.randint(35, 55),  # Daha kısa ömür
                'max_life': 55,
                'color': main_color if random.random() > 0.3 else random.choice(colors),
                'size': random.randint(3, 6),  # Daha küçük
                'type': 'firework'
            }
            self.particles.append(particle)
    
    def create_player_fireworks(self, player):
        """Belirli bir oyuncu için havai fişek gösterisi"""
        if not self._particle_effects_enabled():
            return
        
        # Oyuncunun oyun alanı etrafında havai fişekler
        if player == 1:
            base_x = self.p1_offset_x + (BOARD_WIDTH * self.cell_size) // 2
        else:
            base_x = self.p2_offset_x + (BOARD_WIDTH * self.cell_size) // 2
        
        firework_count = random.randint(1, 2)
        for _ in range(firework_count):
            x = base_x + random.randint(-100, 100)
            y = random.randint(self.window_height // 4, 2 * self.window_height // 3)
            self.create_firework(x, y, player)

    def _update_visual_effect_layers(self, delta_time: float) -> None:
        """Gameplay durduğunda da akan transient efektleri ilerlet."""
        self._last_dt_ms = delta_time

        self.update_particles(dt_ms=delta_time)
        self.update_ambient_particles(dt_ms=delta_time)
        self.update_screen_shake(dt_ms=delta_time)

        dt_frames = delta_time / 16.67 if delta_time > 0 else 1.0
        dt_seconds = max(0.0, float(delta_time or 0.0)) / 1000.0

        if self.p1_drop_trails or self.p2_drop_trails:
            self._update_drop_trails(dt_frames)

        if self.p1_line_flash_timer > 0:
            self.p1_line_flash_timer = max(0, self.p1_line_flash_timer - dt_frames)
            ratio = max(0.0, min(1.0, self.p1_line_flash_timer / 20.0))
            self.p1_line_glow_alpha = int(255 * ratio)
            if self.p1_line_flash_timer <= 0:
                self.p1_line_flash_rows = []
                self.p1_line_glow_alpha = 0

        if self.p2_line_flash_timer > 0:
            self.p2_line_flash_timer = max(0, self.p2_line_flash_timer - dt_frames)
            ratio = max(0.0, min(1.0, self.p2_line_flash_timer / 20.0))
            self.p2_line_glow_alpha = int(255 * ratio)
            if self.p2_line_flash_timer <= 0:
                self.p2_line_flash_rows = []
                self.p2_line_glow_alpha = 0

        if self.p1_combo_message_time > 0:
            self.p1_combo_message_time = max(0, self.p1_combo_message_time - dt_frames)
            if self.p1_combo_message_time <= 0:
                self.p1_combo_message = ""
        if self.p2_combo_message_time > 0:
            self.p2_combo_message_time = max(0, self.p2_combo_message_time - dt_frames)
            if self.p2_combo_message_time <= 0:
                self.p2_combo_message = ""

        if self.p1_line_sweep_active:
            board_pixel_width = self.board1.width * self.cell_size
            sweep_width = max(1, int(self.cell_size * 1.5))
            sweep_travel_px = max(1.0, float(board_pixel_width + sweep_width))
            p1_level = max(1, int(getattr(self.board1, 'level', 1)))
            sweep_speed = _compute_line_sweep_progress_speed(self.block_fall_speed, sweep_travel_px, p1_level)
            self.p1_line_sweep_progress += dt_seconds * sweep_speed
            if self.p1_line_sweep_progress >= 1.0:
                self.p1_line_sweep_progress = 1.0
                self.p1_line_sweep_active = False
                self.p1_line_sweep_rows = []
                self.p1_line_pending_rows = []
                self.p1_line_pending_colors = {}

        if self.p2_line_sweep_active:
            board_pixel_width = self.board2.width * self.cell_size
            sweep_width = max(1, int(self.cell_size * 1.5))
            sweep_travel_px = max(1.0, float(board_pixel_width + sweep_width))
            p2_level = max(1, int(getattr(self.board2, 'level', 1)))
            sweep_speed = _compute_line_sweep_progress_speed(self.block_fall_speed, sweep_travel_px, p2_level)
            self.p2_line_sweep_progress += dt_seconds * sweep_speed
            if self.p2_line_sweep_progress >= 1.0:
                self.p2_line_sweep_progress = 1.0
                self.p2_line_sweep_active = False
                self.p2_line_sweep_rows = []
                self.p2_line_pending_rows = []
                self.p2_line_pending_colors = {}

        # Wave efektleri ortak helper ile (Game / OnlinePvP / Coop ile parity)
        try:
            _update_wave_effects(self.p1_wave_effects, dt_frames)
            _update_wave_effects(self.p2_wave_effects, dt_frames)
        except Exception:
            pass

        if self.p1_falling_block_animations:
            fall_speed = self.block_fall_speed * dt_frames * 60
            for anim in self.p1_falling_block_animations:
                if not anim.get('started', False) and self.p1_line_sweep_progress >= anim.get('sweep_trigger', 0):
                    anim['started'] = True
                if anim.get('started', False):
                    anim['current_offset'] += fall_speed
                    if anim['current_offset'] >= 0:
                        anim['current_offset'] = 0
            self.p1_falling_block_animations = [
                anim for anim in self.p1_falling_block_animations
                if not (anim['current_offset'] >= 0 and anim.get('started', False))
            ]

        if self.p2_falling_block_animations:
            fall_speed = self.block_fall_speed * dt_frames * 60
            for anim in self.p2_falling_block_animations:
                if not anim.get('started', False) and self.p2_line_sweep_progress >= anim.get('sweep_trigger', 0):
                    anim['started'] = True
                if anim.get('started', False):
                    anim['current_offset'] += fall_speed
                    if anim['current_offset'] >= 0:
                        anim['current_offset'] = 0
            self.p2_falling_block_animations = [
                anim for anim in self.p2_falling_block_animations
                if not (anim['current_offset'] >= 0 and anim.get('started', False))
            ]
    
    def update(self, delta_time):
        """Oyun durumunu güncelle"""
        try:
            if self.sound_enabled:
                self.sound.update_music_playlist()
        except Exception:
            pass
        if self.name_input_active or self.paused or getattr(self, 'show_exit_prompt', False):
            return

        if self.game_over:
            self._update_visual_effect_layers(delta_time)
            return

        # Start the match timer the first frame after name entry.
        if not self.match_active:
            self.match_active = True
            self.match_elapsed_ms = 0
            self.match_end_reason = None
            self._last_timer_seconds = None

        # Update match timer; only check time limit in timed mode
        self.match_elapsed_ms += int(delta_time)
        
        if self.match_mode == 'timed':
            remaining_ms = int(self.match_duration_ms) - int(self.match_elapsed_ms)
            remaining_ms = max(0, remaining_ms)
            remaining_seconds = remaining_ms // 1000
            if self._last_timer_seconds != remaining_seconds:
                self._last_timer_seconds = remaining_seconds
                self._vs_panel_dirty = True
            if remaining_ms <= 0 and not self.game_over:
                self.match_end_reason = 'time'
                self.determine_winner()
                return
        else:
            # Süresiz mod - sadece elapsed time'ı göster
            elapsed_seconds = self.match_elapsed_ms // 1000
            if self._last_timer_seconds != elapsed_seconds:
                self._last_timer_seconds = elapsed_seconds
                self._vs_panel_dirty = True

        self._update_demobot(delta_time)
        
        # DAS (Delayed Auto Shift) güncelle - basılı tutarak yatay hareket
        self._update_das(delta_time)
        
        # Soft drop güncelle - basılı tutarak hızlı düşüş
        self._update_soft_drop(delta_time)
        
        self._update_visual_effect_layers(delta_time)
        
        # Oyuncu 1 milestone kontrolü
        p1_milestone = (self.board1.score // 1000) * 1000
        if p1_milestone > self.p1_last_milestone and p1_milestone > 0:
            self.p1_last_milestone = p1_milestone
            self.create_player_fireworks(1)
            self.p1_firework_active = True
            self.p1_firework_time = 120
            self.sound.play('tetris')
            self.trigger_screen_shake(intensity=12, duration=15 / 60.0)  # Screen shake
            # Oyuncu 1 hızını artır
            old_speed = self.fall_speed1
            self.fall_speed1 = max(self.min_fall_speed, self.fall_speed1 - self.speed_increase_per_milestone)
            print(f"🎆 Oyuncu 1: {p1_milestone} PUAN! Hız: {old_speed}ms -> {self.fall_speed1}ms 🚀")
        
        # Oyuncu 2 milestone kontrolü
        p2_milestone = (self.board2.score // 1000) * 1000
        if p2_milestone > self.p2_last_milestone and p2_milestone > 0:
            self.p2_last_milestone = p2_milestone
            self.create_player_fireworks(2)
            self.p2_firework_active = True
            self.p2_firework_time = 120
            self.sound.play('tetris')
            self.trigger_screen_shake(intensity=12, duration=15 / 60.0)  # Screen shake
            # Oyuncu 2 hızını artır
            old_speed = self.fall_speed2
            self.fall_speed2 = max(self.min_fall_speed, self.fall_speed2 - self.speed_increase_per_milestone)
            print(f"🎆 Oyuncu 2: {p2_milestone} PUAN! Hız: {old_speed}ms -> {self.fall_speed2}ms 🚀")
        
        # Havai fişek sürelerini güncelle
        if self.p1_firework_active:
            self.p1_firework_time -= 1
            if self.p1_firework_time <= 0:
                self.p1_firework_active = False
        
        if self.p2_firework_active:
            self.p2_firework_time -= 1
            if self.p2_firework_time <= 0:
                self.p2_firework_active = False
        
        # Oyuncu 1 otomatik düşüş (kendi hızıyla)
        if self.current_piece1 is not None and not self.board1.is_game_over():
            self.fall_time1 += delta_time
            if self.fall_time1 >= self.fall_speed1:
                self.fall_time1 = 0
                self.current_piece1.y += 1

                if not self.board1.is_valid_position(self.current_piece1):
                    self.current_piece1.y -= 1
                    self._mark_player_grounded(1)
                else:
                    self._reset_lock_delay_state(1)
        else:
            self._reset_lock_delay_state(1)

        # Oyuncu 2 otomatik düşüş (kendi hızıyla)
        if self.current_piece2 is not None and not self.board2.is_game_over():
            self.fall_time2 += delta_time
            if self.fall_time2 >= self.fall_speed2:
                self.fall_time2 = 0
                self.current_piece2.y += 1

                if not self.board2.is_valid_position(self.current_piece2):
                    self.current_piece2.y -= 1
                    self._mark_player_grounded(2)
                else:
                    self._reset_lock_delay_state(2)
        else:
            self._reset_lock_delay_state(2)

        self._update_lock_delay(delta_time)

    def draw_board(self, board, current_piece, offset_x, offset_y, cell_size):
        """Bir oyun tahtasını çiz"""
        board_width = BOARD_WIDTH * cell_size
        board_height = BOARD_HEIGHT * cell_size
        skin = self.mode_skin
        player_accent = UIColors.NEON_CYAN if board is self.board1 else UIColors.NEON_MAGENTA
        
        # Arka plan - Quadrix alanı için özel arka plan varsa onu kullan
        board_rect = pygame.Rect(offset_x, offset_y, board_width, board_height)
        bg_rect = pygame.Rect(offset_x - 2, offset_y - 2, board_width + 4, board_height + 4)
        retro_style.draw_glass_panel(self.screen, bg_rect, alpha=170, border_color=player_accent)
        
        if self.board_background.is_loaded():
            # Özel tetris alan arka planı çiz
            self.board_background.draw(self.screen, board_rect)
        else:
            # Varsayılan siyah arka plan
            pygame.draw.rect(self.screen, (6, 6, 16), board_rect)
        apply_board_tint(self.screen, board_rect, skin)

        # Oyuncuya göre çok hafif tint + border (alanları daha net ayırır) - cache'li
        accent_key = (int(board_width), int(board_height), player_accent)
        accent_overlay = self._board_accent_overlay_cache.get(accent_key)
        if accent_overlay is None:
            accent_overlay = pygame.Surface(board_rect.size, pygame.SRCALPHA).convert_alpha()
            accent_overlay.fill((*player_accent[:3], 18))
            self._board_accent_overlay_cache[accent_key] = accent_overlay
        self.screen.blit(accent_overlay, board_rect.topleft)

        pygame.draw.rect(self.screen, player_accent, board_rect, 2, border_radius=14)

        # Cache'li, alpha'lı grid (daha sade)
        grid_surface = self._get_board_grid_surface(cell_size)
        self.screen.blit(grid_surface, (offset_x, offset_y))

        # Kilitli bloklar - cache'li surface (performans)
        player_idx = 1 if board is self.board1 else 2
        cache_entry = self._locked_board_cache[player_idx]
        cache_key = (int(cell_size), int(board_width), int(board_height))
        animating_fall = bool(self.p1_falling_block_animations) if player_idx == 1 else bool(self.p2_falling_block_animations)
        if cache_entry.get('surface') is None or cache_entry.get('key') != cache_key or cache_entry.get('dirty') or animating_fall:
            locked_surface = pygame.Surface((board_width, board_height), pygame.SRCALPHA).convert_alpha()
            locked_surface.fill((0, 0, 0, 0))
            block_size = cell_size - 2
            for y in range(BOARD_HEIGHT):
                row = board.grid[y]
                for x in range(BOARD_WIDTH):
                    c = row[x]
                    if c != BLACK:
                        slice_info = None
                        tex = None
                        try:
                            slice_info = board.texture_grid[y][x]
                        except Exception:
                            slice_info = None
                        if slice_info is not None and self.block_style_manager:
                            tex = self.block_style_manager.get_texture_surface(slice_info.piece_name)
                        block_x = x * cell_size + 1
                        block_y = y * cell_size + 1
                        block_y += self._get_block_fall_offset(player_idx, y, x)
                        self.draw_textured_block(block_x, block_y, block_size, c, tex, slice_info, dst=locked_surface)
            cache_entry['surface'] = locked_surface
            cache_entry['key'] = cache_key
            cache_entry['dirty'] = animating_fall

        self.screen.blit(cache_entry['surface'], (offset_x, offset_y))

        if self.effects_enabled:
            self._draw_drop_trails(player_idx)
        
        # Mevcut parça - 3D DOKULU
        if not board.is_game_over():
            tex = getattr(current_piece, 'texture_surface', None)
            piece_w = len(current_piece.shape[0]) if current_piece.shape else 1
            piece_h = len(current_piece.shape) if current_piece.shape else 1
            for ly, prow in enumerate(current_piece.shape):
                for lx, val in enumerate(prow):
                    if not val:
                        continue
                    x = current_piece.x + lx
                    y = current_piece.y + ly
                    if y < 0:
                        continue
                    block_x = offset_x + x * cell_size + 1
                    block_y = offset_y + y * cell_size + 1
                    block_size = cell_size - 2
                    slice_info = None
                    if tex is not None:
                        slice_info = TextureSlice(
                            current_piece.name,
                            rel_x=lx,
                            rel_y=ly,
                            width=piece_w or 1,
                            height=piece_h or 1,
                            rotation=getattr(current_piece, 'rotation_state', 0),
                        )
                    draw_color = current_piece.color
                    color_matrix = getattr(current_piece, 'color_matrix', None)
                    if color_matrix is not None:
                        try:
                            cell_color = color_matrix[ly][lx]
                            if cell_color is not None:
                                draw_color = cell_color
                        except Exception:
                            pass
                    self.draw_textured_block(block_x, block_y, block_size, draw_color, tex, slice_info)

        # ===== SATIR TEMİZLEME EFEKTLERİ (ANA OYUNLA BİREBİR AYNI) =====
        flash_rows = self.p1_line_flash_rows if board is self.board1 else self.p2_line_flash_rows
        glow_alpha = self.p1_line_glow_alpha if board is self.board1 else self.p2_line_glow_alpha
        sweep_rows = self.p1_line_sweep_rows if board is self.board1 else self.p2_line_sweep_rows
        sweep_progress = self.p1_line_sweep_progress if board is self.board1 else self.p2_line_sweep_progress
        sweep_active = self.p1_line_sweep_active if board is self.board1 else self.p2_line_sweep_active
        pending_rows = self.p1_line_pending_rows if board is self.board1 else self.p2_line_pending_rows
        pending_colors = self.p1_line_pending_colors if board is self.board1 else self.p2_line_pending_colors

        # Pending row snapshot — sweep ön kenarına kadar silinen blokları çiz
        # (Mystery / Game / Coop ile parity).
        if (
            self.effects_enabled
            and sweep_active
            and pending_rows
            and pending_colors
        ):
            cleared_count_p = max(1, len(pending_rows))
            if cleared_count_p >= 4:
                sw_blocks_p = 2
            elif cleared_count_p >= 3:
                sw_blocks_p = 3
            elif cleared_count_p == 2:
                sw_blocks_p = 2
            else:
                sw_blocks_p = 1
            sweep_width_p = max(1, int(sw_blocks_p * cell_size))
            sweep_x_p = offset_x + int(sweep_progress * (board_width + sweep_width_p)) - sweep_width_p
            sweep_front_x_p = sweep_x_p + sweep_width_p
            block_size_p = cell_size - 2
            for row in pending_rows:
                if not (0 <= row < BOARD_HEIGHT):
                    continue
                row_colors = pending_colors.get(int(row))
                if not row_colors:
                    continue
                max_cols = min(BOARD_WIDTH, len(row_colors))
                for x in range(max_cols):
                    color = row_colors[x]
                    if color is None or tuple(color[:3]) == (0, 0, 0):
                        continue
                    cell_center_x = offset_x + x * cell_size + cell_size // 2
                    # Sweep ön kenarı bu hücreye ulaştıysa snapshot çizilmez.
                    if cell_center_x <= sweep_front_x_p:
                        continue
                    block_x = offset_x + x * cell_size + 1
                    block_y = offset_y + row * cell_size + 1
                    self.draw_textured_block(block_x, block_y, block_size_p, color, None, None)

        if self.effects_enabled and sweep_rows and sweep_active:
            valid_rows = sorted({r for r in sweep_rows if 0 <= r < BOARD_HEIGHT})
            if valid_rows:
                cleared_count = max(1, len(valid_rows))
                # Sweep genişliği (base game ile aynı mantık)
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
                group_y = offset_y + top_row * cell_size
                group_h = max(cell_size, (bottom_row - top_row + 1) * cell_size)
                phase = (pygame.time.get_ticks() // 80) % 8

                sweep_x = offset_x + int(sweep_progress * (board_width + sweep_width)) - sweep_width
                board_group_rect = pygame.Rect(offset_x, group_y, board_width, group_h)
                draw_rainbow_cat_sweep(self.screen, self._sweep_cat_state, board_group_rect, sweep_x, sweep_width, phase, BOARD_WIDTH)

                # Hafif beyaz vurgu
                glow_a = int(70 * (1.0 - sweep_progress * 0.4))
                if glow_a > 0:
                    glow_w = min(sweep_width, int(board_width))
                    glow_x = max(offset_x, sweep_x)
                    if glow_w > 0:
                        for row in valid_rows:
                            row_y = offset_y + row * cell_size
                            glow_surface = self._effect_surface_cache.get_filled_surface((glow_w, cell_size), (255, 255, 255, glow_a))
                            self.screen.blit(glow_surface, (glow_x, row_y))
        
        # Flash overlay - temizlenen satırlar için beyaz parlama
        if self.effects_enabled and flash_rows and glow_alpha > 0:
            # Cache: her frame yeni surface yaratmak yerine yeniden kullan
            flash_cache = getattr(self, '_line_clear_flash_cache', None)
            if flash_cache is None:
                flash_cache = {}
                self._line_clear_flash_cache = flash_cache
            glow_cache = getattr(self, '_line_clear_glow_cache', None)
            if glow_cache is None:
                glow_cache = {}
                self._line_clear_glow_cache = glow_cache

            for row in flash_rows:
                if 0 <= row < BOARD_HEIGHT:
                    # Satır için parlayan overlay
                    flash_rect = pygame.Rect(
                        offset_x, 
                        offset_y + row * cell_size, 
                        board_width, 
                        cell_size
                    )
                    
                    # Ana beyaz parlama (ana oyunla aynı)
                    flash_alpha = min(255, glow_alpha)
                    flash_key = (int(board_width), int(cell_size))
                    flash_surface = flash_cache.get(flash_key)
                    if flash_surface is None or flash_surface.get_size() != (int(board_width), int(cell_size)):
                        flash_surface = pygame.Surface((int(board_width), int(cell_size)), pygame.SRCALPHA)
                        flash_surface.fill((255, 255, 255, 255))
                        flash_cache[flash_key] = flash_surface
                    flash_surface.set_alpha(int(flash_alpha))
                    self.screen.blit(flash_surface, flash_rect.topleft)
                    
                    # Kenarlarda ışık efekti (gradient benzeri) - ana oyunla aynı
                    if glow_alpha > 100:
                        glow_height = cell_size // 2
                        # Üst/alt glow gradient'lerini cache'le
                        glow_surf_alpha = int(flash_alpha * 0.5)
                        if glow_height > 0 and glow_surf_alpha > 0:
                            top_key = (int(board_width), int(glow_height), 'top')
                            top_glow = glow_cache.get(top_key)
                            if top_glow is None or top_glow.get_size() != (int(board_width), int(glow_height)):
                                top_glow = pygame.Surface((int(board_width), int(glow_height)), pygame.SRCALPHA)
                                for i in range(int(glow_height)):
                                    a = int(255 * (1.0 - (i / max(1, glow_height - 1))))
                                    pygame.draw.line(top_glow, (255, 255, 200, a), (0, i), (int(board_width), i))
                                glow_cache[top_key] = top_glow
                            top_glow.set_alpha(glow_surf_alpha)
                            self.screen.blit(top_glow, (offset_x, offset_y + row * cell_size - glow_height))

                            bottom_key = (int(board_width), int(glow_height), 'bottom')
                            bottom_glow = glow_cache.get(bottom_key)
                            if bottom_glow is None or bottom_glow.get_size() != (int(board_width), int(glow_height)):
                                bottom_glow = pygame.Surface((int(board_width), int(glow_height)), pygame.SRCALPHA)
                                for i in range(int(glow_height)):
                                    a = int(255 * (i / max(1, glow_height - 1)))
                                    pygame.draw.line(bottom_glow, (255, 255, 200, a), (0, i), (int(board_width), i))
                                glow_cache[bottom_key] = bottom_glow
                            bottom_glow.set_alpha(glow_surf_alpha)
                            self.screen.blit(bottom_glow, (offset_x, offset_y + (row + 1) * cell_size))
        
        # Dalga efektleri çiz (ana oyunla aynı - yatay elips)
        wave_effects = self.p1_wave_effects if board is self.board1 else self.p2_wave_effects
        if self.effects_enabled:
            for wave in wave_effects:
                if wave['alpha'] > 0:
                    # Yatay dalga çizgisi (ana oyunla aynı)
                    wave_color = (*wave['color'], wave['alpha'])
                    wave_surface = self._effect_surface_cache.get_ellipse_surface((int(wave['radius'] * 2), 6), wave_color)
                    wave_x = wave['x'] - wave['radius']
                    wave_y = wave['y'] - 3
                    self.screen.blit(wave_surface, (int(wave_x), int(wave_y)))
    
    def draw(self):
        """Ekranı çiz"""
        # Pencere boyutu değiştiyse layout'u yenile
        self.calculate_board_positions()

        # Screen shake offset hesapla
        shake_x, shake_y = self.get_shake_offset()
        
        # Ekranı temizle
        self.screen.fill(self.mode_skin.outer_bg)
        
        # Ambient particles'ı en arkada çiz
        self.draw_ambient_particles()
        
        # İsim girişi ekranı
        if self.name_input_active:
            self.draw_name_input()
            return
        
        cell_size = self.cell_size
        board_width = BOARD_WIDTH * cell_size
        board_height = BOARD_HEIGHT * cell_size
        preview_panel_width = int(self.preview_panel_width)
        vs_panel_width = int(self.center_panel_width)

        preview_x1 = int(self.p1_preview_x + shake_x)
        offset_x1 = int(self.p1_offset_x + shake_x)
        center_panel_x = int(self.center_panel_x + shake_x)
        offset_x2 = int(self.p2_offset_x + shake_x)
        preview_x2 = int(self.p2_preview_x + shake_x)
        start_y = int(self.p1_offset_y + shake_y)
        preview_gap = max(self._sx(12), cell_size // 2)
        preview_panel_height = max(self._sx(118), (board_height - preview_gap) // 2)
        preview_panel_height = min(preview_panel_height, max(self._sx(136), cell_size * 4 + self._sx(26)))
        top_preview_y = start_y
        bottom_preview_y = start_y + board_height - preview_panel_height
        vs_panel_height = min(board_height, max(self._sx(176), cell_size * 6 + self._sx(24)))
        vs_panel_y = start_y + max(0, (board_height - vs_panel_height) // 2)
        
        # Arka planları çiz - Ana arka plan (tüm ekran)
        # Menü ile tutarlı görünüm için retro_style.bg_color kullan
        _fill_color = getattr(retro_style, 'bg_color', (8, 12, 28))
        bg_alpha = 1.0
        if self.background.is_loaded():
            try:
                bg_alpha = float(getattr(self.background, 'transparency', 1.0))
            except Exception:
                bg_alpha = 1.0
            if bg_alpha < 1.0:
                self.screen.fill(_fill_color)
            self.background.draw(self.screen, (0, 0, self.window_width, self.window_height))
        else:
            self.screen.fill(_fill_color)

        # Ana menü benzeri arka plan tetris blokları kayma/düşme efekti (PvP gameplay)
        if self.effects_enabled and self.name_background_fx:
            self.name_background_fx.update(self.screen)
            self.name_background_fx.draw(self.screen)

        # Outer tint: bg_transparency ile orantılı (menüde tint yok → tutarlılık)
        _ot = tuple(self.mode_skin.outer_tint)
        if len(_ot) >= 4 and _ot[3] > 0:
            _tint_a = int(_ot[3] * bg_alpha) if bg_alpha < 1.0 else _ot[3]
            if _tint_a > 0:
                try:
                    from dataclasses import replace as _dc_replace
                    apply_outer_tint(self.screen, _dc_replace(self.mode_skin, outer_tint=(*_ot[:3], _tint_a)))
                except Exception:
                    apply_outer_tint(self.screen, self.mode_skin)
        
        # Oyuncu başlık panelleri (minimal)
        header_y = int(self.header_top + shake_y)
        header_h = int(self.header_height)
        p1_header = pygame.Rect(offset_x1, header_y, board_width, header_h)
        p2_header = pygame.Rect(offset_x2, header_y, board_width, header_h)

        p1_name = (self.player1_name if self.player1_name else t('player_1')).upper()
        p2_name = (self.player2_name if self.player2_name else t('player_2')).upper()

        self._draw_player_header(p1_header, p1_name, UIColors.NEON_CYAN, int(self.board1.score), int(self.board1.lines_cleared), 'WASD')
        self._draw_player_header(p2_header, p2_name, UIColors.NEON_MAGENTA, int(self.board2.score), int(self.board2.lines_cleared), t('arrows').upper())

        next_label = self._normalize_preview_label('next', 'Sonraki')
        p1_hold_label = self._hold_preview_label(1)
        p2_hold_label = self._hold_preview_label(2)

        p1_next_rect = pygame.Rect(preview_x1, top_preview_y, preview_panel_width, preview_panel_height)
        p1_hold_rect = pygame.Rect(preview_x1, bottom_preview_y, preview_panel_width, preview_panel_height)
        p2_next_rect = pygame.Rect(preview_x2, top_preview_y, preview_panel_width, preview_panel_height)
        p2_hold_rect = pygame.Rect(preview_x2, bottom_preview_y, preview_panel_width, preview_panel_height)

        self._draw_preview_panel(p1_next_rect, UIColors.NEON_CYAN, self.next_piece1, next_label)
        self._draw_preview_panel(p1_hold_rect, UIColors.NEON_CYAN, self.hold_piece1, p1_hold_label)
        self._draw_preview_panel(p2_next_rect, UIColors.NEON_MAGENTA, self.next_piece2, next_label)
        self._draw_preview_panel(p2_hold_rect, UIColors.NEON_MAGENTA, self.hold_piece2, p2_hold_label)

        # OYUNCU 1 (Sol)
        self.draw_board(self.board1, self.current_piece1, offset_x1, start_y, cell_size)
        
        # OYUNCU 2 (Sağ)
        self.draw_board(self.board2, self.current_piece2, offset_x2, start_y, cell_size)
        
        # Combo mesajları (DOUBLE/TRIPLE/QUADRIX - her oyuncunun tahtası üzerinde)
        self._draw_combo_messages(offset_x1, offset_x2, start_y, board_width, board_height)
        
        # ORTADAKİ VS PANELİ
        vs_surface = self._get_vs_panel_surface(vs_panel_width, vs_panel_height)
        vs_rect = pygame.Rect(center_panel_x, vs_panel_y, vs_panel_width, vs_panel_height)
        self.screen.blit(vs_surface, vs_rect)
        
        # Pause
        if self.paused and not self.game_over:
            if getattr(self, '_pause_settings_active', False):
                pause_settings = self._ensure_pause_settings_screen()
                if pause_settings is not None:
                    pause_settings.screen = self.screen
                    pause_settings.draw()
                else:
                    self._draw_pause_menu()
            else:
                self._draw_pause_menu()
        
        # Game Over / Kazanan - Duraklama menüsüyle aynı tema
        if self.game_over:
            self._draw_game_over_screen()
        
        # Oyuncu 1 milestone mesajı
        if self.p1_firework_active and self.p1_firework_time > 0:
            pulse = abs((self.p1_firework_time % 20) - 10) / 10.0
            color_intensity = int(155 + 100 * pulse)
            
            msg = f"{self.p1_last_milestone:,} 🎆".replace(',', '.')
            msg_surf = self.font_large.render(msg, True, (0, color_intensity, 255))
            
            # Oyuncu 1'in alanı üzerinde
            x_pos = self.p1_offset_x + (BOARD_WIDTH * self.cell_size) // 2
            msg_rect = msg_surf.get_rect(center=(x_pos, 200))
            
            # Gölge
            shadow = self.font_large.render(msg, True, BLACK)
            shadow_rect = shadow.get_rect(center=(x_pos + 3, 203))
            self.screen.blit(shadow, shadow_rect)
            self.screen.blit(msg_surf, msg_rect)
        
        # Oyuncu 2 milestone mesajı
        if self.p2_firework_active and self.p2_firework_time > 0:
            pulse = abs((self.p2_firework_time % 20) - 10) / 10.0
            color_intensity = int(155 + 100 * pulse)
            
            msg = f"{self.p2_last_milestone:,} 🎆".replace(',', '.')
            msg_surf = self.font_large.render(msg, True, (255, 0, color_intensity))
            
            # Oyuncu 2'nin alanı üzerinde
            x_pos = self.p2_offset_x + (BOARD_WIDTH * self.cell_size) // 2
            msg_rect = msg_surf.get_rect(center=(x_pos, 200))
            
            # Gölge
            shadow = self.font_large.render(msg, True, BLACK)
            shadow_rect = shadow.get_rect(center=(x_pos + 3, 203))
            self.screen.blit(shadow, shadow_rect)
            self.screen.blit(msg_surf, msg_rect)
        
        # Partikülleri çiz (oyun sonu panelindeyken panel alt katmanında yeniden çiziliyor)
        if self.effects_enabled and not self.game_over:
            self.draw_particles()
        
        if getattr(self, 'show_exit_prompt', False):
            self._draw_exit_prompt_overlay()


    def _draw_exit_prompt_overlay(self):
        width, height = self.screen.get_size()
        ui_scale = self._ui_scale(min_scale=0.68, max_scale=1.16)

        def _fit_font_size(text: str, base_size: int, min_size: int, max_width: int, bold: bool = False) -> pygame.font.Font:
            size = max(min_size, int(base_size))
            while size > min_size:
                f = retro_style.get_font(size, bold=bold)
                if f.size(text)[0] <= max_width:
                    return f
                size -= 1
            return retro_style.get_font(min_size, bold=bold)

        # Dim overlay
        overlay = pygame.Surface((width, height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 185))
        self.screen.blit(overlay, (0, 0))

        panel_width = min(self._sx(520, ui_scale), width - self._sx(100, ui_scale))
        panel_height = self._sx(240, ui_scale)
        panel_rect = pygame.Rect((width - panel_width) // 2, (height - panel_height) // 2, panel_width, panel_height)

        retro_style.draw_glass_panel(
            self.screen,
            panel_rect,
            alpha=180,
            border_color=(*retro_style.accent, 140),
            glow=True,
        )

        title_font = _fit_font_size(
            t('quit_confirm_title'),
            self._sx(30, ui_scale, minimum=16),
            self._sx(15, ui_scale, minimum=11),
            panel_rect.width - self._sx(30, ui_scale),
            bold=True,
        )
        title_surf = title_font.render(t('quit_confirm_title'), True, retro_style.accent)
        self.screen.blit(title_surf, title_surf.get_rect(centerx=panel_rect.centerx, top=panel_rect.y + self._sx(18, ui_scale)))

        body_font = retro_style.get_font(self._sx(18, ui_scale, minimum=12), bold=False)
        body_color = (210, 225, 245)
        body_rect = pygame.Rect(
            panel_rect.x + self._sx(26, ui_scale),
            panel_rect.y + self._sx(64, ui_scale),
            panel_rect.width - self._sx(52, ui_scale),
            self._sx(70, ui_scale),
        )
        retro_style.draw_wrapped_text(
            self.screen,
            t('quit_confirm_message'),
            body_font,
            body_color,
            body_rect,
            align='center',
            line_spacing=self._sx(6, ui_scale),
        )

        button_width = min(self._sx(200, ui_scale), (panel_rect.width - self._sx(26, ui_scale) * 2 - self._sx(16, ui_scale)) // 2)
        button_height = self._sx(54, ui_scale)
        spacing = self._sx(16, ui_scale)
        total_width = button_width * 2 + spacing
        start_x = panel_rect.centerx - total_width // 2
        button_y = panel_rect.bottom - button_height - self._sx(48, ui_scale)

        yes_rect = pygame.Rect(start_x, button_y, button_width, button_height)
        no_rect = pygame.Rect(start_x + button_width + spacing, button_y, button_width, button_height)

        retro_style.draw_uniform_button(
            self.screen,
            yes_rect,
            t('quit_confirm_yes_label'),
            color_code=retro_style.success,
            selected=False,
        )
        retro_style.draw_uniform_button(
            self.screen,
            no_rect,
            t('quit_confirm_no_label'),
            color_code=retro_style.secondary,
            selected=False,
        )

        self.exit_yes_rect = yes_rect
        self.exit_no_rect = no_rect

        hint_font = _fit_font_size(
            t('quit_confirm_select_hint'),
            self._sx(16, ui_scale, minimum=10),
            self._sx(10, ui_scale, minimum=8),
            panel_rect.width - self._sx(24, ui_scale),
            bold=False,
        )
        hint = hint_font.render(t('quit_confirm_select_hint'), True, (150, 165, 190))
        self.screen.blit(hint, hint.get_rect(centerx=panel_rect.centerx, bottom=panel_rect.bottom - self._sx(14, ui_scale)))
        

    
    def restart(self, preserve_session: bool = False):
        """Oyunu yeniden başlat.

        preserve_session=True ise oyuncu isimlerini/kurulum ekranını korur ve
        doğrudan yeni maça başlar.
        """
        from board import Board
        
        # Board'ları tamamen yeniden oluştur (temiz grid ile)
        self.board1 = Board(width=BOARD_WIDTH, height=BOARD_HEIGHT)
        self.board2 = Board(width=BOARD_WIDTH, height=BOARD_HEIGHT)
        
        # Board cache'lerini temizle
        self._locked_board_cache = {
            1: {'key': None, 'surface': None, 'dirty': True},
            2: {'key': None, 'surface': None, 'dirty': True},
        }
        
        # Yeni parça sırası
        self.piece_sequence = []
        self.current_piece_index = 0
        self.generate_pieces(100)
        
        # Oyuncu 1 parçaları
        self.current_piece1 = self.get_next_piece()
        skip_hidden_rows(self.current_piece1, self.board1)
        self.next_piece1 = self.get_next_piece()
        
        # Oyuncu 2 parçaları (aynı sıra)
        self.current_piece_index = 0
        self.current_piece2 = self.get_next_piece()
        skip_hidden_rows(self.current_piece2, self.board2)
        self.next_piece2 = self.get_next_piece()

        # Hold durumunu sıfırla
        self.hold_piece1 = None
        self.hold_piece2 = None
        self.can_hold1 = True
        self.can_hold2 = True
        
        # Tema renklerini parçalara uygula
        self.apply_theme_to_pieces()
        
        # Oyun durumu sıfırla
        self.game_over = False
        self.winner = None
        self.paused = False
        if hasattr(self, 'sound') and self.sound:
            self.sound.unduck_music()
        self._game_over_peek_active = False
        self._game_over_peek_rect = None
        
        # Maç durumu sıfırla
        self.match_active = False
        self.match_elapsed_ms = 0
        self.match_end_reason = None
        self._last_timer_seconds = None
        
        # Eleme durumu sıfırla
        self.p1_eliminated = False
        self.p2_eliminated = False
        
        # Zamanlama sıfırla
        self.fall_time1 = 0
        self.fall_time2 = 0
        self.fall_speed1 = 900
        self.fall_speed2 = 900
        self.lock_delay = DEFAULT_LOCK_DELAY
        self.enable_lock_delay = True
        self.p1_grounded = False
        self.p2_grounded = False
        self.p1_lock_timer = 0.0
        self.p2_lock_timer = 0.0
        
        # Milestone ve havai fişek sıfırla
        self.p1_last_milestone = 0
        self.p2_last_milestone = 0
        self.p1_firework_active = False
        self.p2_firework_active = False
        self.p1_firework_time = 0
        self.p2_firework_time = 0
        
        # DAS sıfırla
        self.p1_das_direction = 0
        self.p1_das_timer = 0
        self.p1_das_repeat_timer = 0
        self.p1_das_charged = False
        self.p2_das_direction = 0
        self.p2_das_timer = 0
        self.p2_das_repeat_timer = 0
        self.p2_das_charged = False
        
        # Soft drop sıfırla
        self.p1_soft_drop_active = False
        self.p1_soft_drop_timer = 0
        self.p2_soft_drop_active = False
        self.p2_soft_drop_timer = 0

        self._clear_demobot_state()
        self._demobot_active_last_frame = False
        
        # Satır temizleme efektlerini sıfırla
        self.p1_line_flash_rows = []
        self.p2_line_flash_rows = []
        self.p1_line_flash_timer = 0
        self.p2_line_flash_timer = 0
        self.p1_line_glow_alpha = 0
        self.p2_line_glow_alpha = 0
        self.p1_wave_effects = []
        self.p2_wave_effects = []
        self.p1_line_sweep_rows = []
        self.p2_line_sweep_rows = []
        self.p1_line_sweep_progress = 0.0
        self.p2_line_sweep_progress = 0.0
        self.p1_line_sweep_active = False
        self.p2_line_sweep_active = False
        self.p1_line_pending_rows = []
        self.p2_line_pending_rows = []
        self.p1_line_pending_colors = {}
        self.p2_line_pending_colors = {}
        self.p1_falling_block_animations = []
        self.p2_falling_block_animations = []
        self.p1_drop_trails = []
        self.p2_drop_trails = []
        
        # Combo mesajlarını sıfırla
        self.p1_combo_message = ""
        self.p1_combo_message_time = 0
        self.p2_combo_message = ""
        self.p2_combo_message_time = 0
        
        # Partiküller ve ambient efektler sıfırla
        self.particles = []
        self.ambient_particles = []
        self.create_ambient_particles()
        
        # Screen shake sıfırla
        self.screen_shake = 0.0
        self.shake_intensity = 0
        self._screen_shake_initial = 0.0
        
        if preserve_session and (self.player1_name and self.player2_name):
            # Aynı oturumla devam et: isim/ayar ekranını tekrar sorma.
            self.name_input_active = False
            self.current_input = 3
        else:
            # İsim giriş ekranına geri dön
            self.name_input_active = True
            self.current_input = 1
            self.player1_name = ''
            self.player2_name = ''
        
        # VS panel'i yenile
        self._vs_panel_dirty = True
        
        print("🔄 PvP oyunu tamamen sıfırlandı!")
    
    def draw_name_input(self):
        """Retro stile uygun PvP isim giriş ekranı."""
        width, height = self.window_width, self.window_height
        ui_scale = self._ui_scale(min_scale=0.72, max_scale=1.14)
        s = lambda v, minimum=1: self._sx(v, ui_scale, minimum)
        retro_style.draw_background(self.screen)

        # Ana menü benzeri arka plan tetris blokları kayma/düşme efekti
        if self.effects_enabled and self.name_background_fx:
            self.name_background_fx.update(self.screen)
            self.name_background_fx.draw(self.screen)

        # Adım 3 ve 4 için farklı başlık
        if self.current_input >= 3:
            title_text = t('pvp_title_settings')
        else:
            title_text = t('pvp_title_names')
        title_rect = retro_style.draw_title(self.screen, title_text, (width // 2, s(110)))
        
        # Adıma göre focus color
        if self.current_input == 1:
            focus_color = UIColors.NEON_CYAN
        elif self.current_input == 2:
            focus_color = UIColors.NEON_MAGENTA
        elif self.current_input == 3:
            focus_color = UIColors.NEON_ORANGE
        else:
            focus_color = UIColors.NEON_GOLD

        panel_w = min(s(900), width - s(160))
        panel_h = s(420) if self.current_input >= 3 else s(372)
        panel_rect = pygame.Rect(width // 2 - panel_w // 2, title_rect.bottom + s(28), panel_w, panel_h)

        # Ana UI temasına uygun glass panel
        retro_style.draw_glass_panel(self.screen, panel_rect, alpha=195, border_color=focus_color)
        pygame.draw.rect(self.screen, (*focus_color, 120), panel_rect, 2, border_radius=16)

        if self.current_input <= 2:
            # İsim giriş alanları
            inner_pad_x = s(40)
            inner_pad_top = s(18)
            label_h = s(26)
            label_to_field_gap = s(8)
            block_gap = s(18)
            field_height = s(120)

            label1_y = panel_rect.y + inner_pad_top
            field1_y = label1_y + label_h + label_to_field_gap
            label2_y = field1_y + field_height + block_gap
            field2_y = label2_y + label_h + label_to_field_gap

            field1 = pygame.Rect(panel_rect.x + inner_pad_x, field1_y, panel_rect.width - inner_pad_x * 2, field_height)
            field2 = pygame.Rect(panel_rect.x + inner_pad_x, field2_y, panel_rect.width - inner_pad_x * 2, field_height)
            # Tıklama tespiti için sakla
            self._name_field1_rect = field1.copy()
            self._name_field2_rect = field2.copy()

            self._draw_name_field(
                field1,
                t('pvp_player1_wasd'),
                self.player1_name,
                UIColors.NEON_CYAN,
                self.current_input == 1,
                ['W', 'A', 'S', 'D'],
                label1_y,
            )
            self._draw_name_field(
                field2,
                t('pvp_player2_arrows'),
                self.player2_name,
                UIColors.NEON_MAGENTA,
                self.current_input == 2,
                ['UP', 'DN', 'LT', 'RT'],
                label2_y,
            )

            progress_font = retro_style.get_font(s(20, minimum=12), bold=False)
            progress_text = progress_font.render(f'{t("pvp_step")} {self.current_input}/4', True, focus_color)
            self.screen.blit(progress_text, progress_text.get_rect(center=(width // 2, panel_rect.bottom + s(28))))
            
            # Progress bar (adım noktaları)
            dot_y = panel_rect.bottom + s(48)
            dot_radius = s(6)
            dot_spacing = s(24)
            total_dots = 4
            dots_start_x = width // 2 - (total_dots * dot_spacing) // 2 + dot_spacing // 2
            for dot_i in range(total_dots):
                dot_x = dots_start_x + dot_i * dot_spacing
                if dot_i + 1 <= self.current_input:
                    # Tamamlanmış adım - dolu
                    pygame.draw.circle(self.screen, focus_color, (dot_x, dot_y), dot_radius)
                else:
                    # Bekleyen adım - boş
                    pygame.draw.circle(self.screen, (60, 70, 90), (dot_x, dot_y), dot_radius)
                    pygame.draw.circle(self.screen, (80, 90, 110), (dot_x, dot_y), dot_radius, 1)

        else:
            # Mod seçimi ve süre ayarı
            self._draw_mode_selection(panel_rect)
    
    def _draw_name_field(self, rect, label, value, accent_color, is_active, keys, label_top: int | None = None):
        ui_scale = self._ui_scale(min_scale=0.72, max_scale=1.14)
        s = lambda v, minimum=1: self._sx(v, ui_scale, minimum)
        # Oyuncu numarası etiketi (alan üstünde)
        label_font = retro_style.get_font(s(22, minimum=12), bold=True)
        label_color = accent_color if is_active else (140, 150, 170)
        label_y = (rect.y - s(30)) if label_top is None else int(label_top)
        self.screen.blit(label_font.render(label, True, label_color), (rect.x + s(6), label_y))

        field_surface = pygame.Surface(rect.size, pygame.SRCALPHA)

        # Aktif alan için neon glow efekti
        if is_active:
            # Dıştaki parlak glow (büyük, soluk)
            glow_rect = field_surface.get_rect().inflate(s(8), s(8))
            glow_surf = pygame.Surface((glow_rect.width, glow_rect.height), pygame.SRCALPHA)
            glow_color = (*accent_color[:3], 35)
            pygame.draw.rect(glow_surf, glow_color, glow_surf.get_rect(), border_radius=22)
            field_surface.blit(glow_surf, (-s(4), -s(4)))

            # Gradient arka plan (üstten alta koyu -> hafif aydınlık)
            for i in range(rect.height):
                ratio = i / max(1, rect.height - 1)
                r = int(15 + 20 * ratio)
                g = int(18 + 22 * ratio)
                b = int(30 + 30 * ratio)
                a = 230
                pygame.draw.line(field_surface, (r, g, b, a), (0, i), (rect.width, i))
        else:
            # İnaktif alan: düz koyu arka plan
            fill = (*UIColors.BG_MEDIUM[:3], 200) if hasattr(UIColors, 'BG_MEDIUM') else (22, 26, 40, 200)
            field_surface.fill(fill)

        # Border - aktif alan daha parlak
        border_color = accent_color if is_active else (60, 70, 90)
        border_width = 3 if is_active else 1
        pygame.draw.rect(field_surface, border_color, field_surface.get_rect(), border_width, border_radius=18)

        # İç highlight çizgisi (üst kenar)
        if is_active:
            highlight_color = (*accent_color[:3], 50)
            pygame.draw.line(field_surface, highlight_color, (s(12), 1), (rect.width - s(12), 1))

        # İsim metni
        display = value if value else t('pvp_enter_name')
        text_color = UIColors.TEXT_PRIMARY if value else (100, 110, 130)

        if is_active:
            # Yanıp sönen cursor
            import time
            cursor_visible = int(time.time() * 2) % 2 == 0
            if cursor_visible:
                display += '|'
            text_color = (255, 255, 255)

        name_font = retro_style.get_font(s(36, minimum=16), bold=True)
        clipped = display[:18]
        name_surface = name_font.render(clipped, True, text_color)
        name_rect = name_surface.get_rect(midleft=(s(22), int(field_surface.get_height() * 0.42)))
        field_surface.blit(name_surface, name_rect)

        # Alt bilgi metni
        hint_font = retro_style.get_font(s(16, minimum=10), bold=False)
        if is_active:
            hint_text = t('pvp_max_chars')
            hint_color = (*accent_color[:3],)
        else:
            hint_text = t('pvp_enter_confirm')
            hint_color = (100, 110, 130)
        hint_surface = hint_font.render(hint_text, True, hint_color)
        field_surface.blit(hint_surface, (s(22), field_surface.get_height() - s(26)))

        # Tuş göstergeleri
        key_color = accent_color if is_active else (80, 90, 110)
        self._draw_keycaps(field_surface, keys, key_color, is_active)

        self.screen.blit(field_surface, rect.topleft)

    def _draw_keycaps(self, surface, keys, color, is_active=False):
        if not keys:
            return
        ui_scale = self._ui_scale(min_scale=0.72, max_scale=1.14)
        s = lambda v, minimum=1: self._sx(v, ui_scale, minimum)
        cap_font = retro_style.get_font(s(16, minimum=10), bold=True)
        cap_size = s(32)
        spacing = s(8)
        total_width = len(keys) * cap_size + (len(keys) - 1) * spacing
        start_x = surface.get_width() - total_width - s(20)
        y = surface.get_height() - cap_size - s(14)
        for idx, key in enumerate(keys):
            cap_rect = pygame.Rect(start_x + idx * (cap_size + spacing), y, cap_size, cap_size)
            # Arka plan
            bg_color = (15, 18, 30) if is_active else (8, 10, 24)
            pygame.draw.rect(surface, bg_color, cap_rect, border_radius=8)
            # Border
            pygame.draw.rect(surface, color, cap_rect, 2, border_radius=8)
            # İç parlama
            if is_active:
                inner = cap_rect.inflate(-6, -6)
                pygame.draw.rect(surface, (*color[:3], 20), inner, border_radius=5)
            # Tuş etiketi
            label = cap_font.render(key, True, color)
            surface.blit(label, label.get_rect(center=cap_rect.center))

    def _draw_mode_selection(self, panel_rect):
        """Mod seçimi ve süre ayarı ekranını çiz."""
        width = self.window_width
        ui_scale = self._ui_scale(min_scale=0.72, max_scale=1.14)
        s = lambda v, minimum=1: self._sx(v, ui_scale, minimum)
        
        # Panel başlığı
        title_label_rect = pygame.Rect(panel_rect.x + s(18), panel_rect.y + s(14), panel_rect.width - s(36), s(26))
        title_label = retro_style.render_fit_text(t('pvp_match_settings'), UIColors.NEON_GOLD, title_label_rect.width, s(20, minimum=12), bold=True)
        self.screen.blit(title_label, title_label.get_rect(midleft=(title_label_rect.left, title_label_rect.centery)))
        
        inner_pad_x = s(36)
        inner_pad_top = s(56)
        
        # Mod seçimi
        mode_y = panel_rect.y + inner_pad_top
        mode_label_font = retro_style.get_font(s(24, minimum=12), bold=True)
        mode_value_font = retro_style.get_font(s(32, minimum=14))
        
        mode_label = mode_label_font.render(t('pvp_match_mode'), True, UIColors.TEXT_PRIMARY)
        self.screen.blit(mode_label, (panel_rect.x + inner_pad_x, mode_y))
        
        # Mod butonları - kullanıcı değiştir ekranı stili
        btn_width = s(150)
        btn_height = s(50)
        btn_gap = s(30)
        total_btn_width = btn_width * 2 + btn_gap
        btn_start_x = panel_rect.centerx - total_btn_width // 2
        btn_y = mode_y + s(40)
        
        # Süreli mod butonu
        timed_rect = pygame.Rect(btn_start_x, btn_y, btn_width, btn_height)
        self._timed_btn_rect = timed_rect  # Fare için sakla
        timed_active = self.match_mode == 'timed'
        # Aktif: cyan arka plan + beyaz yazi, Pasif: koyu arka plan + gri yazi
        timed_bg = UIColors.NEON_CYAN if timed_active else (45, 55, 70)
        timed_text_color = (15, 25, 35) if timed_active else UIColors.TEXT_SECONDARY
        pygame.draw.rect(self.screen, timed_bg, timed_rect, border_radius=s(14))
        pygame.draw.rect(self.screen, (255, 255, 255, 100) if timed_active else (80, 90, 110), timed_rect, 2, border_radius=s(14))
        timed_text = mode_value_font.render(t('pvp_timed'), True, timed_text_color)
        self.screen.blit(timed_text, timed_text.get_rect(center=timed_rect.center))
        
        # Süresiz mod butonu
        endless_rect = pygame.Rect(btn_start_x + btn_width + btn_gap, btn_y, btn_width, btn_height)
        self._endless_btn_rect = endless_rect  # Fare için sakla
        endless_active = self.match_mode == 'endless'
        # Aktif: koyu mor arka plan + beyaz yazi, Pasif: koyu arka plan + gri yazi
        endless_bg = (100, 60, 130) if endless_active else (45, 55, 70)
        endless_text_color = (255, 255, 255) if endless_active else UIColors.TEXT_SECONDARY
        pygame.draw.rect(self.screen, endless_bg, endless_rect, border_radius=s(14))
        pygame.draw.rect(self.screen, (255, 255, 255, 100) if endless_active else (80, 90, 110), endless_rect, 2, border_radius=s(14))
        endless_text = mode_value_font.render(t('pvp_endless'), True, endless_text_color)
        self.screen.blit(endless_text, endless_text.get_rect(center=endless_rect.center))
        
        # Mod açıklaması
        desc_font = retro_style.get_font(s(18, minimum=10), bold=False)
        if self.match_mode == 'timed':
            desc_text = t('pvp_timed_desc')
        else:
            desc_text = t('pvp_endless_desc')
        desc = desc_font.render(desc_text, True, UIColors.TEXT_SECONDARY)
        self.screen.blit(desc, desc.get_rect(center=(panel_rect.centerx, btn_y + btn_height + s(25))))
        
        # Başla butonu (süresiz modda)
        start_btn_y = btn_y + btn_height + s(60)
        start_btn_rect = pygame.Rect(panel_rect.centerx - s(100), start_btn_y, s(200), s(50))
        self._start_btn_rect = start_btn_rect
        
        if self.match_mode == 'endless':
            # Süresiz modda direkt başla butonu göster
            start_bg = (55, 140, 90)  # Yesil arka plan
            pygame.draw.rect(self.screen, start_bg, start_btn_rect, border_radius=s(14))
            pygame.draw.rect(self.screen, (255, 255, 255, 100), start_btn_rect, 2, border_radius=s(14))
            start_text = mode_value_font.render(t('pvp_start'), True, (255, 255, 255))
            self.screen.blit(start_text, start_text.get_rect(center=start_btn_rect.center))
        
        # Süre ayarı (sadece süreli modda göster)
        if self.match_mode == 'timed':
            duration_y = btn_y + btn_height + s(60)
            duration_label = mode_label_font.render(t('pvp_match_duration'), True, UIColors.TEXT_PRIMARY)
            self.screen.blit(duration_label, (panel_rect.x + inner_pad_x, duration_y))
            
            # Süre seçici
            slider_y = duration_y + s(45)
            
            # Sol ok butonu - kullanici ekrani stili
            arrow_size = s(50)
            left_arrow_rect = pygame.Rect(panel_rect.centerx - s(150), slider_y, arrow_size, arrow_size)
            self._left_arrow_rect = left_arrow_rect  # Fare için sakla
            left_hover = self.current_input == 4
            left_bg = (70, 85, 110) if left_hover else (45, 55, 70)
            pygame.draw.rect(self.screen, left_bg, left_arrow_rect, border_radius=s(10))
            pygame.draw.rect(self.screen, (255, 255, 255, 100) if left_hover else (80, 90, 110), left_arrow_rect, 2, border_radius=s(10))
            # Ok çizimi (Unicode yerine polygon)
            arrow_color = (255, 255, 255) if left_hover else UIColors.TEXT_SECONDARY
            cx, cy = left_arrow_rect.center
            arrow_points = [(cx + s(8), cy - s(12)), (cx - s(8), cy), (cx + s(8), cy + s(12))]
            pygame.draw.polygon(self.screen, arrow_color, arrow_points)
            
            # Süre değeri
            duration_value = retro_style.get_font(s(48, minimum=18), bold=True)
            duration_text = duration_value.render(f'{self.custom_duration_minutes} {t("pvp_minutes")}', True, UIColors.NEON_GOLD)
            self.screen.blit(duration_text, duration_text.get_rect(center=(panel_rect.centerx, slider_y + arrow_size // 2)))
            
            # Sağ ok butonu - kullanici ekrani stili
            right_arrow_rect = pygame.Rect(panel_rect.centerx + s(100), slider_y, arrow_size, arrow_size)
            self._right_arrow_rect = right_arrow_rect  # Fare için sakla
            right_hover = self.current_input == 4
            right_bg = (70, 85, 110) if right_hover else (45, 55, 70)
            pygame.draw.rect(self.screen, right_bg, right_arrow_rect, border_radius=s(10))
            pygame.draw.rect(self.screen, (255, 255, 255, 100) if right_hover else (80, 90, 110), right_arrow_rect, 2, border_radius=s(10))
            # Ok çizimi (Unicode yerine polygon)
            cx, cy = right_arrow_rect.center
            arrow_points = [(cx - s(8), cy - s(12)), (cx + s(8), cy), (cx - s(8), cy + s(12))]
            pygame.draw.polygon(self.screen, arrow_color, arrow_points)
            
            # Süre aralığı bilgisi
            range_text = desc_font.render(t('pvp_duration_range'), True, UIColors.TEXT_SECONDARY)
            self.screen.blit(range_text, range_text.get_rect(center=(panel_rect.centerx, slider_y + arrow_size + s(20))))
            
            # Başla butonu - kullanici ekrani stili
            start_btn_y = slider_y + arrow_size + s(50)
            start_btn_rect = pygame.Rect(panel_rect.centerx - s(100), start_btn_y, s(200), s(50))
            self._start_btn_rect = start_btn_rect
            start_bg = (55, 140, 90)  # Yesil arka plan
            pygame.draw.rect(self.screen, start_bg, start_btn_rect, border_radius=s(14))
            pygame.draw.rect(self.screen, (255, 255, 255, 100), start_btn_rect, 2, border_radius=s(14))
            start_text = mode_value_font.render(t('pvp_start'), True, (255, 255, 255))
            self.screen.blit(start_text, start_text.get_rect(center=start_btn_rect.center))
        
        # İlerleme ve footer
        progress_font = retro_style.get_font(s(20, minimum=12), bold=False)
        current_step = 4 if (self.current_input == 4 or (self.current_input == 3 and self.match_mode == 'endless')) else 3
        max_step = 3 if self.match_mode == 'endless' else 4
        focus_color = UIColors.NEON_GOLD if self.current_input == 4 else UIColors.NEON_ORANGE
        progress_text = progress_font.render(f'{t("pvp_step")} {min(self.current_input, max_step)}/{max_step}', True, focus_color)
        self.screen.blit(progress_text, progress_text.get_rect(center=(width // 2, panel_rect.bottom + s(34))))
        

    
    def _handle_setup_mouse_click(self, pos):
        """Mod seçimi ekranında fare tıklamalarını işle."""
        if self.current_input <= 2:
            # İsim alanlarına tıklama ile odak değiştir
            if hasattr(self, '_name_field1_rect') and self._name_field1_rect.collidepoint(pos):
                if self.current_input != 1:
                    self.current_input = 1
                    self._vs_panel_dirty = True
                    self.sound.play('move')
                return True
            if hasattr(self, '_name_field2_rect') and self._name_field2_rect.collidepoint(pos):
                if self.current_input != 2:
                    self.current_input = 2
                    self._vs_panel_dirty = True
                    self.sound.play('move')
                return True
            return False

        if self.current_input >= 3:
            # Süreli mod butonu
            if hasattr(self, '_timed_btn_rect') and self._timed_btn_rect.collidepoint(pos):
                self.match_mode = 'timed'
                self.current_input = 4  # Süre ayarına geç
                self._vs_panel_dirty = True
                self.sound.play('move')
                return True
            
            # Süresiz mod butonu
            if hasattr(self, '_endless_btn_rect') and self._endless_btn_rect.collidepoint(pos):
                self.match_mode = 'endless'
                self._vs_panel_dirty = True
                self.sound.play('move')
                return True
            
            # Sol ok butonu (süre azalt)
            if hasattr(self, '_left_arrow_rect') and self._left_arrow_rect.collidepoint(pos):
                if self.match_mode == 'timed':
                    self.custom_duration_minutes = max(1, self.custom_duration_minutes - 1)
                    self.match_duration_ms = self.custom_duration_minutes * 60 * 1000
                    self._vs_panel_dirty = True
                    self.sound.play('move')
                    return True
            
            # Sağ ok butonu (süre artır)
            if hasattr(self, '_right_arrow_rect') and self._right_arrow_rect.collidepoint(pos):
                if self.match_mode == 'timed':
                    self.custom_duration_minutes = min(10, self.custom_duration_minutes + 1)
                    self.match_duration_ms = self.custom_duration_minutes * 60 * 1000
                    self._vs_panel_dirty = True
                    self.sound.play('move')
                    return True
            
            # Başla butonu
            if hasattr(self, '_start_btn_rect') and self._start_btn_rect.collidepoint(pos):
                self.name_input_active = False
                self._vs_panel_dirty = True
                self.match_active = False
                self.match_elapsed_ms = 0
                self.match_end_reason = None
                self._last_timer_seconds = None
                self.sound.play('rotate')
                return True
        
        return False

    def run(self):
        """Ana oyun döngüsü"""
        running = True
        
        while running:
            try:
                fps_limit = int(self.settings_manager.get('fps_limit', 0) or 0) if self.settings_manager else 0
            except Exception:
                fps_limit = 0
            delta_time = self.clock.tick(resolve_frame_rate_cap(fps_limit))
            
            running = self.handle_input()
            self.update(delta_time)
            self.draw()
        
        pygame.quit()
