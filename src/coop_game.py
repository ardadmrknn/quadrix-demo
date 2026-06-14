"""Co-op Game: Yerel 2 oyunculu kooperatif modu.

PvP akışını temel alarak tek ortak 20×20 board üzerinde çalışır.
P1 (sol 10 sütun, WASD) ve P2 (sağ 10 sütun, yön tuşları) bağımsız
parça akışları alır; satırlar yalnızca 20/20 dolu olduğunda temizlenir.
"""
from __future__ import annotations

import pygame
import random
import math
import sys
import os
from pathlib import Path

from coop_board import CoopBoard
from pieces import Piece, SHAPES, skip_hidden_rows
from constants import (
    BOARD_WIDTH, BOARD_HEIGHT, BLACK, WHITE, CYAN, YELLOW, MAGENTA, GREEN, RED,
    DAS_DELAY, DAS_REPEAT, DEFAULT_LOCK_DELAY,
    LEVEL_SPEED_MIN_MS,
    get_level_fall_speed_ms,
)
from sound import SoundManager
from background import BackgroundManager
from background_effects import get_shared_falling_blocks_layer
from mode_skins import apply_board_tint, apply_outer_tint, draw_board_overlay, get_mode_skin
from retro_style import retro_style
from renderers.jelly_renderer import draw_jelly_block, draw_jelly_border
from themes import ThemeManager
from block_styles import BlockStyleManager, TextureSlice, TextureRenderCache
from block_skin_assets import get_equipped_block_appearance
from platform_utils import (
    create_display, normalize_mouse_pos, get_mouse_pos, set_app_icon,
)
from localization import t
from gamepad_manager import is_gamepad_connected
from promptfont_support import render_action_prompt_surface, render_button_index_prompt_surface
from ui_theme import UIColors, UIFonts
from sweep_effects import SweepCatState, draw_rainbow_cat_sweep
from line_clear_feedback import (
    queue_wave_effects as _queue_wave_effects,
    update_wave_effects as _update_wave_effects,
    trigger_combo_burst as _trigger_combo_burst,
)
from combo_popup_style import (
    COMBO_POPUP_SHADOW_COLOR,
    get_combo_popup_alpha,
    get_combo_popup_color,
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
from asset_manager import load_image
from text_cache import render_text
from gameplay_layout import (
    GAMEPLAY_OCCUPANCY_REFERENCE_SIZE,
    compute_coop_layout,
    get_display_pixel_ratio,
)
from ui_scaling import apply_ui_scale_preset, get_scale, resolve_ui_scale_size

try:
    from gamepad_manager import normalize_gamepad_event_button
except ImportError:
    def normalize_gamepad_event_button(event):
        button = getattr(event, 'button', None)
        if isinstance(button, (int, float)) and not isinstance(button, bool):
            return int(button)
        return None

from screen_shake import (
    DEFAULT_SCREEN_SHAKE_DURATION_SECONDS,
    HARD_DROP_SCREEN_SHAKE_DURATION_SECONDS,
    HARD_DROP_SCREEN_SHAKE_INTENSITY,
    begin_screen_shake,
    sample_screen_shake_offset,
    step_screen_shake,
)


def _resource_path(relative_path: str) -> str:
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


# ---------------------------------------------------------------------------
# CoopGame
# ---------------------------------------------------------------------------

class CoopGame:
    """Yerel 2-oyunculu co-op sınıfı."""

    # Hold tuşları (hard_drop ile çakışmamak için ayrı tuşlar)
    _P1_HOLD_KEY = pygame.K_e
    _P2_HOLD_KEY = pygame.K_RSHIFT
    _AMBIENT_PARTICLE_COLOR = (200, 200, 255)
    _SOFT_DROP_SPEED = 50  # ms
    _LINE_CLEAR_SWEEP_BLOCK_FALL_SPEED = 0.144
    _LINE_CLEAR_SWEEP_REFERENCE_BOARD_WIDTH = BOARD_WIDTH + BOARD_WIDTH // 2
    _OPENING_CURTAIN_DURATION_MS = 350
    _FRAME_MS = 1000.0 / 60.0
    _BACKGROUND_LAYER_NAME = 'coop'
    _BACKGROUND_LAYER_BLOCK_COUNT = 19
    _UNFREEZE_DANGER_ROW_COUNT = 4
    _UNFREEZE_DANGER_LOCK_DELAY_MS = 2500.0

    # ------------------------------------------------------------------
    # Statik yardımcılar (PvP ile ortak)
    # ------------------------------------------------------------------

    @staticmethod
    def _is_focus_loss_event(event) -> bool:
        etype = getattr(event, 'type', None)
        if etype is None:
            return False
        focus_types = (
            getattr(pygame, 'WINDOWFOCUSLOST', None),
            getattr(pygame, 'WINDOWMINIMIZED', None),
            getattr(pygame, 'WINDOWHIDDEN', None),
            getattr(pygame, 'APP_WILLENTERBACKGROUND', None),
            getattr(pygame, 'APP_DIDENTERBACKGROUND', None),
        )
        if any(ft is not None and etype == ft for ft in focus_types):
            return True
        we = getattr(pygame, 'WINDOWEVENT', None)
        if we is not None and etype == we:
            sub = getattr(event, 'event', None)
            if any(ft is not None and sub == ft for ft in focus_types[:3]):
                return True
        ae = getattr(pygame, 'ACTIVEEVENT', None)
        if ae is not None and etype == ae:
            gain = getattr(event, 'gain', 1)
            state = getattr(event, 'state', 0)
            mask = 0
            for a in ('APPINPUTFOCUS', 'APPACTIVE'):
                v = getattr(pygame, a, 0)
                if isinstance(v, int):
                    mask |= v
            return gain == 0 and (state == 0 or mask == 0 or bool(state & mask))
        return False

    # ------------------------------------------------------------------
    # UI ölçek yardımcıları
    # ------------------------------------------------------------------

    def _active_ui_size(self) -> tuple[int, int]:
        screen = getattr(self, 'screen', None)
        if screen is not None and hasattr(screen, 'get_size'):
            try:
                width, height = screen.get_size()
                return max(1, int(width)), max(1, int(height))
            except Exception:
                pass
        return (
            max(1, int(getattr(self, 'window_width', GAMEPLAY_OCCUPANCY_REFERENCE_SIZE[0]))),
            max(1, int(getattr(self, 'window_height', GAMEPLAY_OCCUPANCY_REFERENCE_SIZE[1]))),
        )

    def _effective_ui_size(self) -> tuple[int, int]:
        screen = getattr(self, 'screen', None)
        if screen is not None and hasattr(screen, 'get_size'):
            display_surface = None
            try:
                active_display_surface = pygame.display.get_surface()
                if active_display_surface is not None and screen is active_display_surface:
                    display_surface = True
            except Exception:
                pass

            try:
                width, height = resolve_ui_scale_size(
                    screen,
                    use_effective_display_size=True,
                    display_surface=display_surface,
                )
                return max(1, int(width)), max(1, int(height))
            except Exception:
                pass

        return self._active_ui_size()

    def _display_pixel_ratio(self) -> float:
        return get_display_pixel_ratio(self._active_ui_size(), self._effective_ui_size())

    def _ui_scale(self, mn: float = 0.72, mx: float = 1.20) -> float:
        logical_scale = apply_ui_scale_preset(
            get_scale(
                self._effective_ui_size(),
                min_scale=mn,
                max_scale=mx,
                reference_size=GAMEPLAY_OCCUPANCY_REFERENCE_SIZE,
            ),
            min_scale=mn,
            max_scale=mx,
        )
        return float(logical_scale) * float(self._display_pixel_ratio())

    def _sx(self, value, scale=None, minimum=1) -> int:
        if scale is None:
            scale = self._ui_scale()
        return max(minimum, int(round(float(value) * float(scale))))

    @staticmethod
    def _ease_in_out_quad(t: float) -> float:
        if t < 0.5:
            return 2 * t * t
        return 1 - pow(-2 * t + 2, 2) / 2

    @staticmethod
    def _ease_out_cubic(t: float) -> float:
        return 1 - pow(1 - t, 3)

    # ------------------------------------------------------------------
    # __init__
    # ------------------------------------------------------------------

    def __init__(
        self,
        sound_enabled=True,
        effects_enabled=True,
        screen=None,
        fullscreen=True,
        user_manager=None,
        settings_manager=None,
        sound_manager=None,
        piece_rng_seed: int | None = None,
    ):
        if not pygame.get_init():
            pygame.init()

        self.user_manager = user_manager
        self.settings_manager = settings_manager
        try:
            self._piece_rng_seed = int(piece_rng_seed) if piece_rng_seed is not None else None
        except Exception:
            self._piece_rng_seed = None
        if self._piece_rng_seed is None:
            self._p1_piece_rng = random.Random()
            self._p2_piece_rng = random.Random()
        else:
            base_seed = int(self._piece_rng_seed)
            # Oyuncu bag'lerini birbirinden ayır ama aynı match seed'ine bağla.
            self._p1_piece_rng = random.Random(base_seed ^ 0xA5A5A5A5)
            self._p2_piece_rng = random.Random((base_seed + 0x9E3779B9) & 0xFFFFFFFF)

        # --- Ekran ---
        if screen is not None:
            self.screen = screen
        else:
            self.screen = create_display(0, 0, fullscreen=True, resizable=False, borderless=True)
        self.window_width = self.screen.get_width()
        self.window_height = self.screen.get_height()
        self.fullscreen = fullscreen

        # --- Ses ---
        self.sound = sound_manager if sound_manager is not None else SoundManager()
        self.sound.enabled = True
        self.sound.sfx_enabled = sound_enabled
        self.sound_enabled = sound_enabled
        if self.settings_manager:
            self.sound.music_enabled = self.settings_manager.get('music_enabled', True)
            self.sound.sfx_enabled = self.settings_manager.get('sound_enabled', sound_enabled)
            self.sound.set_music_volume(self.settings_manager.get('music_volume', 0.3))
            self.sound.set_volume(self.settings_manager.get('sfx_volume', 0.5))
        if hasattr(self.sound, 'unduck_music'):
            self.sound.unduck_music()
        self._music_mode_key = getattr(self, '_music_mode_key', 'coop')
        self.current_music_track = None
        # Online co-op host'unda wrapper kendi `update_music_playlist()` tick'ini
        # atar; aynı frame'de CoopGame'in iç tick'i çift tick yaratmasın diye
        # bu flag default False; OnlineCoopGame bunu host yaratırken True yapar.
        self._suppress_internal_music_tick = False
        self.effects_enabled = effects_enabled
        self._start_music()

        # --- Arka plan ---
        self.background = BackgroundManager()
        self.board_background = BackgroundManager()
        self.background.set_transparency(0.7)
        if self.settings_manager:
            self.board_background.set_transparency(self.settings_manager.get('bg_transparency', 0.7))
        else:
            self.board_background.set_transparency(0.7)
        self._load_backgrounds()

        # --- Tema / blok stili ---
        self.theme_manager = ThemeManager(self.settings_manager)
        self.mode_skin = get_mode_skin('classic')
        self.block_style_manager = BlockStyleManager(self.settings_manager) if self.settings_manager else None
        self.block_appearance = get_equipped_block_appearance(self.user_manager)
        self._texture_render_cache = TextureRenderCache()

        # --- Kontroller ---
        self.pvp_controls = self._resolve_controls()
        self._coop_spawner_debug_enabled = False
        self._p1_spawn_halted = False
        self._p2_spawn_halted = False

        # ==================================================================
        # Board + parça sistemi
        # ==================================================================
        self.board = CoopBoard()
        self.remote_authority_players: set[str] = set()

        # Bağımsız parça bag'leri
        self._p1_bag: list[int] = []
        self._p2_bag: list[int] = []

        # İlk parçalar
        self.p1_current_piece = self._next_piece('P1')
        self.p1_next_piece = self._next_piece('P1')
        self.p2_current_piece = self._next_piece('P2')
        self.p2_next_piece = self._next_piece('P2')
        self._place_at_spawn(self.p1_current_piece, 'P1')
        self._place_at_spawn(self.p2_current_piece, 'P2')

        # Tema uygula
        for p in (self.p1_current_piece, self.p1_next_piece, self.p2_current_piece, self.p2_next_piece):
            self._apply_block_style(p)

        # ==================================================================
        # Oyun durumu
        # ==================================================================
        self.game_over = False
        self._game_over_snapshot = None
        self._game_over_start_time = 0
        self._game_over_restart_rect = None
        self._game_over_exit_rect = None
        self._game_over_peek_active = False
        self._game_over_peek_rect = None
        self._peek_icon_cache = None
        self._peek_icon_cache_key = None
        self.paused = False
        self.pause_menu_selected = 0
        self._pause_menu_keys = ['resume', 'settings', 'music', 'music_volume', 'sound_effects', 'sfx_volume', 'main_menu']
        self._pause_option_rects: list[pygame.Rect] = []
        self._pause_volume_rects: dict[str, pygame.Rect] = {}
        self._pause_vol_drag_active = False
        self._pause_vol_drag_option = ''
        self._pause_settings_active = False
        self._pause_settings_screen = None
        self._opening_curtain_active = True
        self._opening_curtain_duration_ms = self._OPENING_CURTAIN_DURATION_MS
        self._opening_curtain_start_ms = 0  # deferred — set on first draw frame
        self._opening_curtain_deferred = True

        # Skor
        self.team_score = 0
        self.total_lines_cleared = 0
        self.level = 1
        self.p1_contribution_pct = 50
        self.p2_contribution_pct = 50
        self.p1_total_cells = 0
        self.p2_total_cells = 0
        self.p1_score_contribution = 0
        self.p2_score_contribution = 0
        self.p1_score_contribution_pct = 0
        self.p2_score_contribution_pct = 0

        # Freeze
        self.p1_frozen = False
        self.p2_frozen = False
        self._p1_pending_unfreeze = False
        self._p2_pending_unfreeze = False
        self._p1_unfreeze_lock_delay_active = False
        self._p2_unfreeze_lock_delay_active = False

        # Oyuncu bazlı hold
        self.p1_hold_piece: Piece | None = None
        self.p2_hold_piece: Piece | None = None
        self.p1_hold_used = False
        self.p2_hold_used = False

        # Zamanlama
        self.p1_fall_time = 0.0
        self.p2_fall_time = 0.0
        self.fall_speed = 900.0  # ortak global hız (ms)
        self.elapsed_time = 0.0

        # DAS
        self.p1_das_direction = 0
        self.p1_das_timer = 0.0
        self.p1_das_repeat_timer = 0.0
        self.p1_das_charged = False
        self.p2_das_direction = 0
        self.p2_das_timer = 0.0
        self.p2_das_repeat_timer = 0.0
        self.p2_das_charged = False

        # Soft drop
        self.p1_soft_drop_active = False
        self.p1_soft_drop_timer = 0.0
        self.p2_soft_drop_active = False
        self.p2_soft_drop_timer = 0.0

        # Lock delay (Kart Ustalığı / ana oyun davranışı)
        self.enable_lock_delay = True
        self.lock_delay = DEFAULT_LOCK_DELAY
        self.p1_grounded = False
        self.p2_grounded = False
        self.p1_lock_timer = 0.0
        self.p2_lock_timer = 0.0

        # Event callback'leri (kampanya modu gibi alt sınıflar için)
        self._event_listeners: list = []

        # Fontlar
        self.font_large = UIFonts.get(48)
        self.font_medium = UIFonts.get(30)
        self.font_small = UIFonts.get(22)
        self.font_hud = UIFonts.get(18)

        # Layout cache
        self._layout_key = None
        self.cell_size = 30
        self.board_offset_x = 0
        self.board_offset_y = 0
        self._side_panel_width = 120
        self._board_grid_cache: dict = {'key': None, 'surface': None}

        # --- Per-frame surface caches (perf) ---
        self._midline_cache: dict = {'key': None, 'glow': None, 'line': None}
        self._ghost_surf_cache: dict = {'key': None, 'surface': None}
        self._freeze_overlay_cache: dict = {'P1': {'key': None, 'surface': None}, 'P2': {'key': None, 'surface': None}}
        self._board_skin_cache: dict = {'skin_id': None, 'board_skin': None}
        self._outer_bg_composite_cache: dict = {'key': None, 'surface': None}
        self._frame_path_cache: dict = {}
        self._cached_das_delay: float = float(DAS_DELAY)
        self._cached_das_repeat: float = float(DAS_REPEAT)
        self._das_settings_dirty: bool = True

        # --- Visual Effects (Game base ile uyumlu) ---
        self.particles: list = []
        self.ambient_particles: list = []
        self.screen_shake = 0.0
        self.shake_intensity = 3
        self._screen_shake_initial = 0.0
        self.drop_trails: list = []
        self.line_clear_flash = False
        self._flash_timer = 0.0
        # Combo / Quadrix mesaj overlay'i (Game / PvP ile parity için)
        self.combo_message: str = ""
        self.combo_message_time: float = 0.0
        self.line_clear_sweep_active = False
        self.line_clear_sweep_progress = 0.0
        self.line_clear_sweep_rows: list[int] = []
        self.line_clear_pending_rows: list[int] = []
        self.line_clear_pending_colors: dict = {}
        self.falling_block_animations: list[dict] = []
        self._fall_animation_rows_key: tuple[int, ...] | None = None
        self.line_clear_wave_effects: list = []
        self._sweep_cat_state = SweepCatState()
        self._effect_surface_cache = None
        try:
            from effect_surface_cache import EffectSurfaceCache as _ESC
            self._effect_surface_cache = _ESC()
        except Exception:
            pass
        self.animation_multiplier = 1.0

        # Falling blocks background layer
        self.falling_blocks = None
        if self.effects_enabled:
            try:
                if self._BACKGROUND_LAYER_NAME == 'default':
                    self.falling_blocks = get_shared_falling_blocks_layer(self._BACKGROUND_LAYER_NAME)
                else:
                    self.falling_blocks = get_shared_falling_blocks_layer(
                        self._BACKGROUND_LAYER_NAME,
                        block_count=self._BACKGROUND_LAYER_BLOCK_COUNT,
                    )
            except Exception:
                self.falling_blocks = None

        # Outer background (tam ekran arka plan)
        self.outer_background = BackgroundManager()
        if self.settings_manager:
            self.outer_background.set_transparency(self.settings_manager.get('bg_transparency', 0.7))
        else:
            self.outer_background.set_transparency(0.7)
        self._load_outer_background()

        # Ambient particles init
        self._init_ambient_particles()
        self._sync_runtime_settings_from_manager()
        self._prewarm_startup_render_caches()

    # ==================================================================
    # Kontrol çözümleme
    # ==================================================================

    def _resolve_controls(self) -> dict:
        defaults = {
            'player1': {
                'move_left': pygame.K_a,
                'move_right': pygame.K_d,
                'soft_drop': pygame.K_s,
                'hard_drop': pygame.K_LSHIFT,
                'rotate': pygame.K_w,
                'hold': self._P1_HOLD_KEY,
            },
            'player2': {
                'move_left': pygame.K_LEFT,
                'move_right': pygame.K_RIGHT,
                'soft_drop': pygame.K_DOWN,
                'hard_drop': pygame.K_SPACE,
                'rotate': pygame.K_UP,
                'hold': self._P2_HOLD_KEY,
            },
            'debug': {
                'coop_spawner_left': None,
                'coop_spawner_right': None,
            },
            'pause': pygame.K_p,
        }
        if not self.settings_manager:
            return defaults
        controls = self.settings_manager.get_controls()
        pvp_cfg = controls.get('pvp', {}) if isinstance(controls, dict) else {}
        debug_cfg = controls.get('debug', {}) if isinstance(controls, dict) else {}
        resolved: dict = {'player1': {}, 'player2': {}, 'debug': {}}
        for player in ('player1', 'player2'):
            pcfg = pvp_cfg.get(player, {}) if isinstance(pvp_cfg, dict) else {}
            for action in defaults[player]:
                binding = pcfg.get(action)
                resolved[player][action] = self._binding_to_keycode(binding, defaults[player][action])
        for action in defaults['debug']:
            binding = debug_cfg.get(action) if isinstance(debug_cfg, dict) else None
            resolved['debug'][action] = self._binding_to_keycode(binding, defaults['debug'][action])
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

    def _sync_coop_spawner_debug_settings(self) -> None:
        enabled = False
        settings_manager = getattr(self, 'settings_manager', None)
        if settings_manager is not None:
            try:
                enabled = bool(settings_manager.get('coop_debug_halt_blocks', False))
            except Exception:
                enabled = False

        self._coop_spawner_debug_enabled = enabled
        if enabled:
            return

        resume_p1 = self._p1_spawn_halted
        resume_p2 = self._p2_spawn_halted
        self._p1_spawn_halted = False
        self._p2_spawn_halted = False

        if resume_p1:
            self._resume_player_spawner_if_waiting('P1')
        if resume_p2:
            self._resume_player_spawner_if_waiting('P2')

    def _player_spawner_halted(self, player: str) -> bool:
        if not getattr(self, '_coop_spawner_debug_enabled', False):
            return False
        return self._p1_spawn_halted if player == 'P1' else self._p2_spawn_halted

    def _resume_player_spawner_if_waiting(self, player: str) -> None:
        if getattr(self, 'game_over', False):
            return
        if player == 'P1':
            if self.p1_frozen or self._p1_pending_unfreeze or self.p1_current_piece is not None:
                return
        else:
            if self.p2_frozen or self._p2_pending_unfreeze or self.p2_current_piece is not None:
                return
        self._try_spawn_for_player(player, force=True)

    def _toggle_player_spawner_halt(self, player: str) -> None:
        if not getattr(self, '_coop_spawner_debug_enabled', False):
            return

        if player == 'P1':
            self._p1_spawn_halted = not self._p1_spawn_halted
            halted = self._p1_spawn_halted
        else:
            self._p2_spawn_halted = not self._p2_spawn_halted
            halted = self._p2_spawn_halted

        if not halted:
            self._resume_player_spawner_if_waiting(player)

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
                        self._start_music()
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
            self.pvp_controls = self._resolve_controls()
        except Exception:
            pass
        self._sync_coop_spawner_debug_settings()

        theme_manager = getattr(self, 'theme_manager', None)
        if theme_manager is not None:
            try:
                theme_manager.set_theme(settings_manager.get('theme', settings_manager.get('active_theme', 'Classic')))
            except Exception:
                pass

        for attr_name in ('p1_current_piece', 'p1_next_piece', 'p2_current_piece', 'p2_next_piece', 'p1_hold_piece', 'p2_hold_piece'):
            piece = getattr(self, attr_name, None)
            if piece is None:
                continue
            try:
                self._apply_block_style(piece)
            except Exception:
                pass

        try:
            bg_transparency = float(settings_manager.get('bg_transparency', 0.7))
        except Exception:
            bg_transparency = None
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
            for attr_name in ('background', 'board_background', 'outer_background'):
                background = getattr(self, attr_name, None)
                if background is not None and hasattr(background, 'set_transparency'):
                    try:
                        background.set_transparency(bg_transparency)
                    except Exception:
                        pass

        self.falling_blocks = None
        if getattr(self, 'effects_enabled', True):
            try:
                if self._BACKGROUND_LAYER_NAME == 'default':
                    self.falling_blocks = get_shared_falling_blocks_layer(self._BACKGROUND_LAYER_NAME)
                else:
                    self.falling_blocks = get_shared_falling_blocks_layer(
                        self._BACKGROUND_LAYER_NAME,
                        block_count=self._BACKGROUND_LAYER_BLOCK_COUNT,
                    )
            except Exception:
                self.falling_blocks = None
        if self.falling_blocks is not None:
            try:
                eff_opacity = float(settings_manager.get('effects_opacity', 1.0))
                self.falling_blocks.set_opacity_multiplier(eff_opacity)
                self.effects_opacity = eff_opacity
            except Exception:
                pass
        self._layout_key = None
        self._das_settings_dirty = True
        self._board_skin_cache = {'skin_id': None, 'board_skin': None}
        self._outer_bg_composite_cache = {'key': None, 'surface': None}

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
    def _key_label(key_code) -> str:
        key_name = ''
        try:
            name_getter = getattr(pygame.key, 'name', None)
            if callable(name_getter):
                key_name = name_getter(int(key_code)) or ''
        except Exception:
            key_name = ''

        if not key_name:
            fallback_names = {
                getattr(pygame, 'K_RSHIFT', None): 'RShift',
                getattr(pygame, 'K_LSHIFT', None): 'LShift',
                getattr(pygame, 'K_SPACE', None): 'Space',
                getattr(pygame, 'K_RETURN', None): 'Enter',
                getattr(pygame, 'K_KP_ENTER', None): 'Enter',
                getattr(pygame, 'K_LEFT', None): 'Left',
                getattr(pygame, 'K_RIGHT', None): 'Right',
                getattr(pygame, 'K_UP', None): 'Up',
                getattr(pygame, 'K_DOWN', None): 'Down',
            }
            key_name = fallback_names.get(key_code, str(key_code))

        compact_names = {
            'right shift': 'RShift',
            'left shift': 'LShift',
            'right ctrl': 'RCtrl',
            'left ctrl': 'LCtrl',
            'kp enter': 'Enter',
            'return': 'Enter',
            'backspace': 'Bksp',
        }
        normalized = compact_names.get(str(key_name).strip().lower(), str(key_name).strip())
        if len(normalized) <= 2:
            return normalized.upper()
        if normalized.islower():
            return normalized.title()
        return normalized

    @staticmethod
    def _fmt_score(value: int) -> str:
        return f"{int(value):,}".replace(',', '.')

    def _score_contribution_text(self, player: str, score_value: int, percent_value: int) -> str:
        return t(
            'coop_score_contribution',
            default='{player} {score} (%{percent})',
            player=player,
            score=self._fmt_score(score_value),
            percent=percent_value,
        )

    def _score_contribution_texts(self) -> tuple[str, str]:
        return (
            self._score_contribution_text('P1', self.p1_score_contribution, self.p1_score_contribution_pct),
            self._score_contribution_text('P2', self.p2_score_contribution, self.p2_score_contribution_pct),
        )

    def _next_label(self, player: str) -> str:
        return t('coop_next_panel_label', default='{player} NEXT', player=player)

    def _hold_label(self, player: str) -> str:
        controls_key = 'player1' if player == 'P1' else 'player2'
        hold_key = self.pvp_controls.get(controls_key, {}).get('hold')
        key_label = self._key_label(hold_key)
        return t('coop_hold_panel_label', default='{player} Hold ({binding})', player=player, binding=key_label)

    def _render_panel_label_surface(
        self,
        label: str,
        color,
        max_width: int,
        *,
        base_size: int,
        min_size: int = 8,
        bold: bool = False,
    ) -> pygame.Surface:
        safe_max_width = max(8, int(max_width))
        text = str(label or '').strip() or '-'
        base_px = max(int(base_size), int(min_size))
        min_px = max(6, int(min_size))
        font = retro_style.get_fitting_font(text, base_px, safe_max_width, bold=bold, min_size=min_px)

        candidate = text
        if font.size(candidate)[0] > safe_max_width:
            compact = candidate.rstrip(':').strip() or candidate
            if compact != candidate and font.size(compact)[0] <= safe_max_width:
                candidate = compact
            else:
                if ' (' in compact:
                    without_binding = compact.split(' (', 1)[0].strip()
                    if without_binding and font.size(without_binding)[0] <= safe_max_width:
                        candidate = without_binding
                    else:
                        candidate = compact
                else:
                    candidate = compact

                if font.size(candidate)[0] > safe_max_width:
                    trimmed = candidate
                    while trimmed and font.size(trimmed + '...')[0] > safe_max_width:
                        trimmed = trimmed[:-1].rstrip()
                    if trimmed:
                        candidate = trimmed + '...'
                    elif font.size('...')[0] <= safe_max_width:
                        candidate = '...'
                    else:
                        candidate = ''

        return font.render(candidate, True, color)

    # ==================================================================
    # Parça üretimi (bağımsız bag'ler)
    # ==================================================================

    def _refill_bag(self, player: str) -> None:
        bag: list[int] = list(range(len(SHAPES))) * 2  # 7 tip × 2 kopya
        bag_rng = self._p1_piece_rng if player == 'P1' else self._p2_piece_rng
        bag_rng.shuffle(bag)
        if player == 'P1':
            self._p1_bag.extend(bag)
        else:
            self._p2_bag.extend(bag)

    def _next_piece(self, player: str) -> Piece:
        bag = self._p1_bag if player == 'P1' else self._p2_bag
        if not bag:
            self._refill_bag(player)
            bag = self._p1_bag if player == 'P1' else self._p2_bag
        idx = bag.pop(0)
        piece = Piece(x=0, y=0, shape_index=idx)
        self._place_at_spawn(piece, player)
        self._apply_block_style(piece)
        return piece

    def _place_at_spawn(self, piece: Piece, player: str) -> None:
        sx, sy = self.board.get_spawn_position(player, piece)
        piece.x = sx
        piece.y = sy
        # Instantly drop through hidden spawn rows for immediate visibility
        while piece.y < 0 and self.board.is_valid_position_for_player(piece, player, dy=1):
            piece.y += 1

    def _apply_block_style(self, piece: Piece) -> None:
        if not piece:
            return
        base_color = self.theme_manager.get_piece_color(piece.name) if self.theme_manager else piece.color
        if self.block_style_manager:
            self.block_style_manager.apply_to_piece(piece, base_color)
        else:
            piece.color = base_color
            piece.texture_path = None

    # ==================================================================
    # Müzik / arka plan
    # ==================================================================

    def _start_music(self):
        if not getattr(self.sound, 'music_enabled', True):
            return
        ensure_track_available = getattr(self.sound, 'ensure_track_available', None)
        playlist_values = []
        mode_key = getattr(self, '_music_mode_key', 'coop')
        if self.settings_manager:
            try:
                playlist_values = self.settings_manager.get_music_playlist_for_mode(mode_key)
            except Exception:
                playlist_values = []
        if playlist_values:
            track_keys = []
            for value in playlist_values:
                track_key = ensure_track_available(value) if callable(ensure_track_available) else value
                if track_key:
                    track_keys.append(track_key)
            if track_keys:
                do_shuffle = bool(self.settings_manager.get('music_shuffle', False)) if self.settings_manager else False
                start_index = 0 if do_shuffle else random.randrange(len(track_keys))
                self.sound.set_music_playlist(
                    track_keys,
                    loop=True,
                    start_index=start_index,
                    autoplay=True,
                    force=True,
                    shuffle=do_shuffle,
                )
                self.current_music_track = track_keys[start_index]
                return

        preferred = None
        if self.settings_manager:
            overrides = {}
            get_mode_music_overrides = getattr(self.settings_manager, 'get_mode_music_overrides', None)
            if callable(get_mode_music_overrides):
                try:
                    overrides = get_mode_music_overrides() or {}
                except Exception:
                    overrides = {}
            preferred = overrides.get(mode_key) if isinstance(overrides, dict) else None
            legacy_key = f'{mode_key}_music'
            if not preferred:
                preferred = self.settings_manager.get(legacy_key)
            if not preferred:
                preferred = self.settings_manager.get('game_music')

        fallback_track = 'pvp_1' if mode_key == 'coop' else 'klasik_1'
        raw_track = preferred or fallback_track
        track_key = ensure_track_available(raw_track) if callable(ensure_track_available) else raw_track
        if track_key:
            self.sound.set_music_playlist([track_key], loop=True, autoplay=True, force=True)
            self.current_music_track = track_key

    @staticmethod
    def _format_elapsed_time(ms_value: int) -> str:
        total_seconds = max(0, int(ms_value) // 1000)
        minutes, seconds = divmod(total_seconds, 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f'{hours:02d}:{minutes:02d}:{seconds:02d}'
        return f'{minutes:02d}:{seconds:02d}'

    def _wrap_overlay_text(self, font, text: str, max_width: int) -> list[str]:
        raw_lines = [segment.strip() for segment in str(text or '').splitlines() if segment.strip()]
        if not raw_lines:
            return ['']

        wrapped: list[str] = []
        for raw_line in raw_lines:
            words = raw_line.split()
            if not words:
                wrapped.append('')
                continue
            current = words[0]
            for word in words[1:]:
                candidate = f'{current} {word}'
                try:
                    candidate_width = font.size(candidate)[0]
                except Exception:
                    candidate_width = len(candidate) * 8
                if candidate_width <= max_width:
                    current = candidate
                else:
                    wrapped.append(current)
                    current = word
            wrapped.append(current)
        return wrapped

    def _get_cached_peek_icon(self, icon_size: int):
        cache_key = max(1, int(icon_size))
        if getattr(self, '_peek_icon_cache_key', None) == cache_key:
            return self._peek_icon_cache

        try:
            peek_icon = load_image(_resource_path('assets/kart_secim_sagust.png'))
            smoothscale = getattr(getattr(pygame, 'transform', None), 'smoothscale', None)
            if callable(smoothscale):
                peek_icon = smoothscale(peek_icon, (cache_key, cache_key))
            self._peek_icon_cache = peek_icon
            self._peek_icon_cache_key = cache_key
            return peek_icon
        except Exception:
            self._peek_icon_cache = None
            self._peek_icon_cache_key = cache_key
            return None

    def _draw_game_over_peek_button(
        self,
        rect: pygame.Rect,
        *,
        hovered: bool,
        fallback_label: str,
        border_color: tuple[int, int, int] | None = None,
    ) -> None:
        resolved_border_color = border_color or ((116, 190, 255) if hovered else (110, 134, 188))
        pygame.draw.circle(self.screen, (255, 255, 255), rect.center, min(rect.width, rect.height) // 2)
        pygame.draw.circle(self.screen, resolved_border_color, rect.center, min(rect.width, rect.height) // 2, 2)

        icon_size = max(12, int(min(rect.width, rect.height) * 0.65))
        peek_icon_surf = self._get_cached_peek_icon(icon_size)
        if peek_icon_surf is not None:
            self.screen.blit(peek_icon_surf, peek_icon_surf.get_rect(center=rect.center))
            return

        fallback_font = retro_style.get_font(max(10, int(icon_size * 0.5)), bold=True)
        fallback_color = border_color or ((116, 190, 255) if hovered else (160, 182, 220))
        eye_surf = fallback_font.render(fallback_label, True, fallback_color)
        self.screen.blit(eye_surf, eye_surf.get_rect(center=rect.center))

    def _capture_game_over_snapshot(self) -> dict[str, object]:
        p1_score = int(getattr(self, 'p1_score_contribution', 0) or 0)
        p2_score = int(getattr(self, 'p2_score_contribution', 0) or 0)
        p1_pct = int(getattr(self, 'p1_score_contribution_pct', 0) or 0)
        p2_pct = int(getattr(self, 'p2_score_contribution_pct', 0) or 0)
        p1_frozen = bool(getattr(self, 'p1_frozen', False))
        p2_frozen = bool(getattr(self, 'p2_frozen', False))
        return {
            'team_score': int(getattr(self, 'team_score', 0) or 0),
            'total_lines': int(getattr(self, 'total_lines_cleared', 0) or 0),
            'level': int(getattr(self, 'level', 1) or 1),
            'elapsed_ms': int(getattr(self, 'elapsed_time', 0) or 0),
            'p1_score': p1_score,
            'p2_score': p2_score,
            'p1_pct': p1_pct,
            'p2_pct': p2_pct,
            'p1_text': self._score_contribution_text('P1', p1_score, p1_pct),
            'p2_text': self._score_contribution_text('P2', p2_score, p2_pct),
            'p1_frozen': p1_frozen,
            'p2_frozen': p2_frozen,
            'both_frozen': p1_frozen and p2_frozen,
        }

    def _ensure_game_over_snapshot(self) -> dict[str, object]:
        snapshot = getattr(self, '_game_over_snapshot', None)
        if not isinstance(snapshot, dict):
            snapshot = self._capture_game_over_snapshot()
            self._game_over_snapshot = snapshot
        if not getattr(self, '_game_over_start_time', 0):
            try:
                self._game_over_start_time = int(pygame.time.get_ticks())
            except Exception:
                self._game_over_start_time = 0
        return snapshot

    def _game_over_status_text(self, snapshot: dict[str, object]) -> str:
        if snapshot.get('both_frozen'):
            return t('coop_game_over_both_frozen', default='Both players stuck!')
        if snapshot.get('p1_frozen'):
            return t('coop_game_over_p1_frozen', default='P1 alanı kapandı')
        if snapshot.get('p2_frozen'):
            return t('coop_game_over_p2_frozen', default='P2 alanı kapandı')
        return t('coop_game_over_status_default', default='Takım koşusu sonlandı')

    def _game_over_reason_text(self, snapshot: dict[str, object]) -> str:
        if snapshot.get('both_frozen'):
            return t(
                'coop_game_over_reason_double_freeze',
                default='İki oyuncunun spawn alanı aynı anda kapandı. Ortak koşu burada sona erdi.',
            )
        if snapshot.get('p1_frozen'):
            return t(
                'coop_game_over_reason_p1_frozen',
                default='P1 spawn alanı kilitlendi ve takım bu turu geri çevirecek boşluğu açamadı.',
            )
        if snapshot.get('p2_frozen'):
            return t(
                'coop_game_over_reason_p2_frozen',
                default='P2 spawn alanı kilitlendi ve takım bu turu kurtaracak alanı açamadı.',
            )
        return t(
            'coop_game_over_reason_default',
            default='Ortak board ilerleyemediği için takım koşusu güvenli şekilde kapatıldı.',
        )

    def _play_game_over_sequence(self) -> None:
        if not getattr(self, 'sound', None):
            return

        play_game_over_sequence = getattr(self.sound, 'play_game_over_sequence', None)
        if callable(play_game_over_sequence):
            try:
                play_game_over_sequence()
                return
            except Exception:
                pass

        try:
            self.sound.stop_music()
        except Exception:
            pass

        try:
            self.sound.play('gameover')
        except Exception:
            pass

    def _activate_game_over(self) -> None:
        if self.game_over:
            return
        self.game_over = True
        self._game_over_snapshot = self._capture_game_over_snapshot()
        try:
            self._game_over_start_time = int(pygame.time.get_ticks())
        except Exception:
            self._game_over_start_time = 0
        self._game_over_restart_rect = None
        self._game_over_exit_rect = None
        self._game_over_peek_active = False
        self._game_over_peek_rect = None
        try:
            from gamepad_manager import get_gamepad_manager
            get_gamepad_manager().rumble(1.0, 1.0, 600)
        except Exception:
            pass
        self._play_game_over_sequence()

    def restart(self) -> None:
        screen = self.screen
        sound_manager = self.sound
        self.__init__(
            sound_enabled=self.sound_enabled,
            effects_enabled=self.effects_enabled,
            screen=screen,
            fullscreen=self.fullscreen,
            user_manager=self.user_manager,
            settings_manager=self.settings_manager,
            sound_manager=sound_manager,
            piece_rng_seed=self._piece_rng_seed,
        )

    def _load_backgrounds(self):
        for name in ('backgrounds/main_background.png', 'backgrounds/main_background.jpg',
                      'backgrounds/game_background.png', 'backgrounds/game_background.jpg'):
            path = _resource_path(name)
            if self.background.load_image(path):
                break
        for name in ('backgrounds/game_background.png', 'backgrounds/game_background.jpg',
                      'backgrounds/board_background.png', 'backgrounds/board_bg.png'):
            path = _resource_path(name)
            if self.board_background.load_image(path):
                break

    def _load_outer_background(self):
        for name in ('backgrounds/outer_background.png', 'backgrounds/outer_background.jpg',
                      'backgrounds/background.png', 'backgrounds/background.jpg'):
            path = _resource_path(name)
            if self.outer_background.load_image(path):
                break

    def _init_ambient_particles(self):
        """Arka plan ambient parçacıklarını oluştur."""
        if not self._particle_effects_enabled():
            return
        self.ambient_particles.clear()
        active_width, active_height = self._active_ui_size()
        base_count = random.randint(50, 100)
        count = int(base_count * getattr(self, 'animation_multiplier', 1.0) * self._particle_effects_multiplier())
        for _ in range(count):
            p = {
                'x': random.uniform(0, active_width),
                'y': random.uniform(0, active_height),
                'vx': random.uniform(-0.5, 0.5),
                'vy': random.uniform(0.2, 0.8),
                'alpha': random.randint(50, 150),
                'size': random.randint(1, 3),
                'pulse': random.uniform(0, 6.28),
                'pulse_speed': random.uniform(0.02, 0.05),
                'color': self._AMBIENT_PARTICLE_COLOR,
            }
            self.ambient_particles.append(p)

    # ------------------------------------------------------------------
    # Particle effects toggle
    # ------------------------------------------------------------------

    def _particle_effects_enabled(self) -> bool:
        if not self.effects_enabled:
            return False
        sm = self.settings_manager
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
        sm = self.settings_manager
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

    # ------------------------------------------------------------------
    # Textured block rendering (Game base ile uyumlu)
    # ------------------------------------------------------------------

    def draw_textured_block(self, x, y, size, color, texture_surface=None, texture_slice: TextureSlice | None = None):
        if color is None:
            color = (128, 128, 128)
        if texture_surface is not None and texture_slice is not None:
            self._draw_texture_cell(x, y, size, color, texture_surface, texture_slice)
            draw_jelly_border(self.screen, x, y, size, color, appearance=self.block_appearance)
            return
        draw_jelly_block(self.screen, x, y, size, color, appearance=self.block_appearance)

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

    def _render_texture_slice(self, surface, slice_info: TextureSlice, size: int):
        bounds = {'x': 0.0, 'y': 0.0, 'w': 1.0, 'h': 1.0}
        if self.block_style_manager:
            bounds = self.block_style_manager.get_slice_bounds(slice_info.piece_name)
        return self._texture_render_cache.render_slice(surface, slice_info, size, bounds)

    def _draw_texture_cell(self, x, y, size, color, surface, slice_info: TextureSlice) -> None:
        scaled = self._render_texture_slice(surface, slice_info, size)
        if scaled is None:
            return
        self.screen.blit(scaled, (x, y))
        self._draw_texture_border(x, y, size, color, textured=True)

    def _draw_texture_border(self, x, y, size, color, textured=False) -> None:
        if textured:
            border_color = (255, 255, 255)
            inner = (220, 220, 220)
        else:
            border_color = tuple(min(255, int(c * 1.2)) for c in color[:3])
            inner = tuple(max(0, int(c * 0.5)) for c in color[:3])
        pygame.draw.rect(self.screen, border_color, (x, y, size, size), 2, border_radius=4)
        pygame.draw.rect(self.screen, inner, (x + 2, y + 2, size - 4, size - 4), 1, border_radius=3)

    def _draw_custom_frame(self, rect: pygame.Rect, asset_name: str, padding: int = 0, hole_punch: bool = False) -> bool:
        try:
            # Cache the file path lookup
            found_path = self._frame_path_cache.get(asset_name)
            if found_path is None:
                for folder in ["assets/game_ui", "assets/ui"]:
                    p = _resource_path(f"{folder}/{asset_name}")
                    if os.path.exists(p):
                        found_path = p
                        break
                self._frame_path_cache[asset_name] = found_path or ''
            if not found_path:
                return False
            target_w = int(rect.width + (padding * 2))
            target_h = int(rect.height + (padding * 2))
            img = load_image(found_path, size=(target_w, target_h), convert_alpha=True)
            draw_x = rect.centerx - (target_w // 2)
            draw_y = rect.centery - (target_h // 2)
            if hole_punch and padding > 0:
                self.screen.blit(img, (draw_x, draw_y), (0, 0, target_w, padding))
                self.screen.blit(img, (draw_x, draw_y + target_h - padding), (0, target_h - padding, target_w, padding))
                self.screen.blit(img, (draw_x, draw_y + padding), (0, padding, padding, rect.height))
                self.screen.blit(img, (draw_x + target_w - padding, draw_y + padding), (target_w - padding, padding, padding, rect.height))
            else:
                self.screen.blit(img, (draw_x, draw_y))
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Screen shake
    # ------------------------------------------------------------------

    def get_shake_offset(self):
        return sample_screen_shake_offset(self)

    def _screen_shake_enabled(self) -> bool:
        """Screen shake genel efekt anahtarına bağlıdır, particle toggle'a değil."""
        return bool(self.effects_enabled)

    def trigger_hard_drop_screen_shake(self) -> None:
        self.trigger_screen_shake(
            intensity=HARD_DROP_SCREEN_SHAKE_INTENSITY,
            duration=HARD_DROP_SCREEN_SHAKE_DURATION_SECONDS,
        )

    def trigger_screen_shake(self, intensity: int = 10, duration: float = DEFAULT_SCREEN_SHAKE_DURATION_SECONDS) -> None:
        begin_screen_shake(
            self,
            intensity=intensity,
            duration=duration,
            enabled=self._screen_shake_enabled(),
        )

    # ------------------------------------------------------------------
    # Particles
    # ------------------------------------------------------------------

    def create_lock_explosion(self, x, y, color, cell_size=25):
        if not self._particle_effects_enabled():
            return
        base_color = color[:3]
        bright = tuple(min(255, int(c * 1.3)) for c in base_color)
        dim = tuple(max(0, int(c * 0.7)) for c in base_color)
        white_t = tuple(min(255, c + 80) for c in base_color)
        palette = [base_color, bright, dim, white_t, (255, 255, 255)]
        particle_count = max(1, int(random.randint(6, 10) * self._particle_effects_multiplier()))
        for i in range(particle_count):
            angle = (i / max(1, particle_count)) * 2 * math.pi + random.uniform(-0.3, 0.3)
            speed = random.uniform(2, 5)
            life_ms = random.randint(20, 45) * self._FRAME_MS
            self.particles.append({
                'x': float(x), 'y': float(y),
                'vx': math.cos(angle) * speed,
                'vy': math.sin(angle) * speed - 1.5,
                'life': life_ms,
                'max_life': life_ms,
                'color': random.choice(palette),
                'size': random.randint(2, 5),
            })

    def create_particles(self, count, x=None, y=None, colors=None, speed=5):
        if not self._particle_effects_enabled():
            return
        if x is None:
            x = random.randint(0, max(1, self.window_width))
        if y is None:
            y = random.randint(0, max(1, self.window_height // 2))
        if colors is None:
            colors = [CYAN, YELLOW, MAGENTA, GREEN, RED]
        for _ in range(max(1, int(count * self.animation_multiplier * self._particle_effects_multiplier()))):
            life_ms = random.randint(30, 60) * self._FRAME_MS
            self.particles.append({
                'x': float(x), 'y': float(y),
                'vx': random.uniform(-1, 1) * speed,
                'vy': random.uniform(-1, 1) * speed,
                'life': life_ms,
                'max_life': life_ms,
                'color': random.choice(colors),
                'size': random.randint(2, 5),
            })

    def create_line_clear_particles(self, cleared_rows, board_offset_x, board_offset_y, cell_size, board=None):
        """Satır temizlendiğinde Game / PvP ile parity'li parçacık zinciri.

        Hücre rengi `last_cleared_colors` (CoopBoard `last_clear_row_colors`)
        snapshot'ından alınır; sweep henüz oynamadan önceki parça renklerini
        kullanır. Mod-spesifik bookkeeping (skor / katkı) bu fonksiyona girmez.
        """
        if not self._particle_effects_enabled():
            return
        target_board = board if board is not None else self.board
        sparkle_colors = [
            (255, 255, 255),
            (255, 255, 200),
            (255, 215, 0),
            (0, 255, 255),
            (255, 100, 255),
        ]
        cs = max(1, int(cell_size))
        board_width_cells = max(1, int(getattr(target_board, 'width', BOARD_WIDTH)))
        cleared_colors_map = getattr(target_board, 'last_clear_row_colors', None) or getattr(target_board, 'last_cleared_colors', None) or {}

        # Per-cell saçılım
        for row in cleared_rows:
            try:
                row_index = int(row)
            except (TypeError, ValueError):
                continue
            row_colors = cleared_colors_map.get(row_index) if isinstance(cleared_colors_map, dict) else None
            for col in range(board_width_cells):
                cell_x = int(board_offset_x) + col * cs + cs // 2
                cell_y = int(board_offset_y) + row_index * cs + cs // 2
                cell_color = None
                try:
                    if row_colors and col < len(row_colors):
                        candidate = row_colors[col]
                        if candidate and tuple(candidate[:3]) != (0, 0, 0):
                            cell_color = tuple(candidate[:3])
                except Exception:
                    cell_color = None
                if cell_color is None:
                    cell_color = random.choice(sparkle_colors)

                main_count = max(1, int(random.randint(6, 10) * self._particle_effects_multiplier()))
                for _ in range(main_count):
                    speed = random.uniform(4, 12)
                    vx = speed * random.uniform(-1.5, 1.5)
                    vy = speed * random.uniform(-1, 0.5) - 2
                    life_ms = random.randint(40, 80) * self._FRAME_MS
                    self.particles.append({
                        'x': float(cell_x + random.randint(-3, 3)),
                        'y': float(cell_y + random.randint(-3, 3)),
                        'vx': vx,
                        'vy': vy,
                        'life': life_ms,
                        'max_life': life_ms,
                        'color': cell_color,
                        'size': random.randint(3, 6),
                    })

                # Kıvılcım (küçük, parlak)
                spark_count = max(1, int(random.randint(2, 4) * self._particle_effects_multiplier()))
                for _ in range(spark_count):
                    life_ms = random.randint(20, 40) * self._FRAME_MS
                    self.particles.append({
                        'x': float(cell_x + random.randint(-5, 5)),
                        'y': float(cell_y + random.randint(-5, 5)),
                        'vx': random.uniform(-3, 3),
                        'vy': random.uniform(-4, -1),
                        'life': life_ms,
                        'max_life': life_ms,
                        'color': random.choice(sparkle_colors),
                        'size': random.randint(2, 3),
                    })

    def update_particles(self, dt_ms: float = 16.666):
        dt = max(0.0, min(100.0, float(dt_ms)))
        dt_frames = dt / 16.666
        alive = []
        for p in self.particles:
            p['x'] += p['vx'] * dt_frames
            p['y'] += p['vy'] * dt_frames
            p['vy'] += 0.15 * dt_frames  # gravity
            p['life'] -= dt
            if p['life'] > 0:
                alive.append(p)
        self.particles = alive

    def draw_particles(self):
        if not self._effect_surface_cache:
            return
        cs = self.cell_size
        ox, oy = self.board_offset_x, self.board_offset_y
        bw = self.board.width * cs
        bh = self.board.height * cs
        for p in self.particles:
            if p['life'] <= 0:
                continue
            ratio = p['life'] / max(1, p['max_life'])
            alpha = int(255 * ratio)
            size = max(1, int(p['size'] * (0.3 + 0.7 * ratio)))
            px, py = int(p['x']), int(p['y'])
            # Board sınırları dışında çizme
            if px < ox - 20 or px > ox + bw + 20 or py < oy - 20 or py > oy + bh + 20:
                continue
            # Glow halo
            glow_size = size * 3
            glow_surf = self._effect_surface_cache.get_ellipse_surface(
                (glow_size, glow_size), (*p['color'][:3], max(10, alpha // 4)))
            self.screen.blit(glow_surf, (px - glow_size // 2, py - glow_size // 2))
            # Core
            core_surf = self._effect_surface_cache.get_filled_surface(
                (size, size), (*p['color'][:3], alpha))
            self.screen.blit(core_surf, (px - size // 2, py - size // 2))

    def update_ambient_particles(self, dt_ms: float = 16.666):
        dt = max(0.0, min(100.0, float(dt_ms)))
        dt_frames = dt / 16.666
        active_width, active_height = self._active_ui_size()
        for p in self.ambient_particles:
            p['x'] += p['vx'] * dt_frames
            p['y'] += p['vy'] * dt_frames
            p['pulse'] += p['pulse_speed'] * dt_frames
            if p['y'] > active_height:
                p['y'] = -10
                p['x'] = random.uniform(0, active_width)
            if p['x'] < -10:
                p['x'] = active_width + 10
            elif p['x'] > active_width + 10:
                p['x'] = -10

    def draw_ambient_particles(self):
        if not self._effect_surface_cache:
            return
        eo = getattr(self, 'effects_opacity', 1.0)
        if eo <= 0:
            return
        for p in self.ambient_particles:
            pulse_alpha = int(p['alpha'] + math.sin(p['pulse']) * 30)
            pulse_alpha = max(30, min(180, pulse_alpha))
            pulse_alpha = int(pulse_alpha * eo)
            color = tuple(p.get('color', self._AMBIENT_PARTICLE_COLOR))[:3]
            pos = (int(p['x']), int(p['y']))
            size = max(1, int(p['size']))
            if size > 1:
                glow_surf = self._effect_surface_cache.get_circle_surface(size * 2, (*color, pulse_alpha // 3))
                self.screen.blit(glow_surf, (pos[0] - size * 2, pos[1] - size * 2))
            particle_surf = self._effect_surface_cache.get_circle_surface(size, (*color, pulse_alpha))
            self.screen.blit(particle_surf, (pos[0] - size, pos[1] - size))

    # ------------------------------------------------------------------
    # Drop trails
    # ------------------------------------------------------------------

    def create_drop_trail(self, x_px: int, y_start: int, y_end: int, color, cell_size: int):
        if not self._particle_effects_enabled():
            return
        trail_h = max(1, y_end - y_start)
        surf = pygame.Surface((cell_size, trail_h), pygame.SRCALPHA)
        segments = max(1, trail_h // 4)
        seg_h = trail_h / segments
        for i in range(segments):
            seg_alpha = int(120 * (1 - i / segments))
            y_pos = int(i * seg_h)
            surf.fill((*color[:3], seg_alpha), (0, y_pos, cell_size, int(seg_h) + 1))
        self.drop_trails.append({
            'x': float(x_px), 'y': float(y_start),
            'alpha': 120.0, '_init_alpha': 120.0,
            '_surf': surf, '_color': color[:3],
            '_base_alpha': None,
        })

    def update_drop_trails(self, dt_ms: float = 16.666):
        dt = max(0.0, min(100.0, float(dt_ms)))
        fade_speed = 250.0  # alpha/saniye
        alive = []
        for t_obj in self.drop_trails:
            t_obj['alpha'] -= fade_speed * dt / 1000.0
            if t_obj['alpha'] > 0:
                alive.append(t_obj)
        self.drop_trails = alive

    def _draw_drop_trails(self):
        for trail in self.drop_trails:
            if trail['alpha'] <= 0:
                continue
            surf = trail['_surf']
            # macOS Metal/OpenGL: SRCALPHA surface üzerinde set_alpha() hatalı
            # sonuç verir. Surface'i sıfırlayıp orantılı alpha ile yeniden doldur.
            w, h = surf.get_size()
            segments = max(1, h // 4)
            seg_h = h / segments
            surf.fill((0, 0, 0, 0))
            color = trail['_color']
            scale = trail['alpha'] / trail['_init_alpha']
            for i in range(segments):
                seg_alpha = int(120 * scale * (1 - i / segments))
                if seg_alpha <= 0:
                    continue
                y_pos = int(i * seg_h)
                surf.fill((*color, seg_alpha), (0, y_pos, w, int(seg_h) + 1))
            self.screen.blit(surf, (int(trail['x']), int(trail['y'])))

    # ------------------------------------------------------------------
    # Line clear effects
    # ------------------------------------------------------------------

    def _start_line_clear_sweep(self, cleared_rows: list[int]):
        """Satır temizleme sweep efektini başlat.

        Renk verisi calling code tarafından self.line_clear_pending_colors'a
        önceden yazılır (clear_lines ÖNCE kaydeder, sonra satırları siler).
        """
        if not cleared_rows or not self.effects_enabled:
            return
        self.line_clear_sweep_active = True
        self.line_clear_sweep_progress = 0.0
        self.line_clear_sweep_rows = list(cleared_rows)
        self._fall_animation_rows_key = None
        # Flash
        self.line_clear_flash = True
        self._flash_timer = 80.0  # ms

    def _update_line_clear_effects(self, dt_ms: float):
        if self.line_clear_flash:
            self._flash_timer -= dt_ms
            if self._flash_timer <= 0:
                self.line_clear_flash = False
        # Combo / Quadrix mesaj timer'ı (frame-bazlı, Game / PvP ile aynı eğri)
        if self.combo_message_time > 0:
            dt_frames = max(0.0, min(100.0, float(dt_ms))) / self._FRAME_MS
            self.combo_message_time = max(0.0, self.combo_message_time - dt_frames)
            if self.combo_message_time <= 0:
                self.combo_message = ""
        if self.line_clear_sweep_active:
            cell_size = max(1, int(self.cell_size))
            cleared_count = max(1, len(self.line_clear_sweep_rows))
            sweep_width = self._get_line_sweep_length_px(cell_size, cleared_count)
            sweep_travel_px = self._get_line_sweep_timing_travel_px(cell_size, sweep_width)
            dt_seconds = max(0.0, min(100.0, float(dt_ms))) / 1000.0
            level = max(1, int(getattr(self, 'level', 1)))
            sweep_speed = _compute_line_sweep_progress_speed(self._LINE_CLEAR_SWEEP_BLOCK_FALL_SPEED, sweep_travel_px, level)
            self.line_clear_sweep_progress += dt_seconds * sweep_speed
            if self.line_clear_sweep_progress >= 1.0:
                self.line_clear_sweep_progress = 1.0
                self.line_clear_sweep_active = False
                self.line_clear_sweep_rows = []
                self.line_clear_pending_rows = []
                self.line_clear_pending_colors = {}
        # Dalga efekti (Game / PvP ile parity için ortak helper)
        dt_frames = max(0.0, min(100.0, float(dt_ms))) / self._FRAME_MS
        try:
            _update_wave_effects(self.line_clear_wave_effects, dt_frames)
        except Exception:
            pass
        self._update_falling_block_animations(dt_ms)

    def _get_line_sweep_length_px(self, cell_size: int, cleared_count: int) -> int:
        return max(cell_size * 3, cell_size * cleared_count * 2)

    def _get_line_sweep_timing_travel_px(self, cell_size: int, sweep_width: int) -> float:
        board_width = max(1, int(getattr(self.board, 'width', self._LINE_CLEAR_SWEEP_REFERENCE_BOARD_WIDTH)))
        timing_cells = min(board_width, max(1, int(self._LINE_CLEAR_SWEEP_REFERENCE_BOARD_WIDTH)))
        return max(1.0, float(timing_cells * max(1, int(cell_size)) + max(1, int(sweep_width))))

    def _get_line_sweep_draw_travel_px(self, cell_size: int, sweep_width: int) -> float:
        board_width = max(1, int(getattr(self.board, 'width', 20)))
        return max(1.0, float(board_width * max(1, int(cell_size)) + max(1, int(sweep_width))))

    def _row_drop_distances_after_clear(self, cleared_rows: list[int]) -> dict[int, int]:
        valid_rows = sorted({
            int(row)
            for row in cleared_rows
            if 0 <= int(row) < self.board.height
        })
        if not valid_rows:
            return {}
        cleared_set = set(valid_rows)
        distances: dict[int, int] = {}
        for old_y in range(self.board.height):
            if old_y in cleared_set:
                continue
            drop_rows = sum(1 for cleared_y in valid_rows if cleared_y > old_y)
            if drop_rows <= 0:
                continue
            new_y = old_y + drop_rows
            if 0 <= new_y < self.board.height:
                distances[new_y] = drop_rows
        return distances

    def _start_block_fall_animation(self, cleared_rows: list[int]) -> None:
        rows_key = tuple(sorted({
            int(row)
            for row in cleared_rows
            if 0 <= int(row) < self.board.height
        }))
        self._fall_animation_rows_key = rows_key
        self.falling_block_animations = []
        if not rows_key or not self.effects_enabled:
            return

        cell_size = max(1, int(self.cell_size))
        cleared_count = max(1, len(rows_key))
        sweep_width = self._get_line_sweep_length_px(cell_size, cleared_count)
        sweep_travel_px = self._get_line_sweep_draw_travel_px(cell_size, sweep_width)
        row_drop_distances = self._row_drop_distances_after_clear(list(rows_key))

        for y in range(self.board.height):
            drop_rows = row_drop_distances.get(y, 0)
            if drop_rows <= 0:
                continue
            for x in range(self.board.width):
                if not self.board.occupancy[y][x]:
                    continue
                column_center_px = (x + 0.5) * cell_size
                sweep_trigger = max(0.0, min(1.0, column_center_px / sweep_travel_px))
                self.falling_block_animations.append({
                    'row': y,
                    'col': x,
                    'current_offset': float(-drop_rows * cell_size),
                    'target_offset': 0.0,
                    'sweep_trigger': sweep_trigger,
                    'started': False,
                })

    def _update_falling_block_animations(self, dt_ms: float) -> None:
        if not self.falling_block_animations:
            return
        dt_frames = max(0.0, min(100.0, float(dt_ms))) / self._FRAME_MS
        fall_speed = self._LINE_CLEAR_SWEEP_BLOCK_FALL_SPEED * dt_frames * 60.0
        sweep_progress = self.line_clear_sweep_progress if self.line_clear_sweep_active else 1.0

        for anim in self.falling_block_animations:
            if not anim.get('started', False) and sweep_progress >= anim.get('sweep_trigger', 0.0):
                anim['started'] = True
            if anim.get('started', False):
                anim['current_offset'] = min(0.0, float(anim.get('current_offset', 0.0)) + fall_speed)

        self.falling_block_animations = [
            anim for anim in self.falling_block_animations
            if not (anim.get('started', False) and float(anim.get('current_offset', 0.0)) >= 0.0)
        ]

    def _get_block_fall_offset(self, row: int, col: int) -> float:
        for anim in self.falling_block_animations:
            if anim.get('row') == row and anim.get('col') == col:
                return float(anim.get('current_offset', 0.0))
        return 0.0

    def _get_ghost_visual_offset(self, piece, drop_y: int) -> float:
        """Satır temizleme animasyonu sırasında ghost piece'ın altındaki düşen
        blokların offset'ine göre ghost'u yukarı kaydır.
        Sıfır veya negatif (yukarı kayma) bir piksel değeri döner.
        """
        anims = getattr(self, 'falling_block_animations', None)
        if not anims or piece is None:
            return 0.0
        anim_lookup = {}
        for anim in anims:
            try:
                anim_lookup[(int(anim['row']), int(anim['col']))] = float(
                    anim.get('current_offset', 0.0)
                )
            except Exception:
                continue
        if not anim_lookup:
            return 0.0
        min_offset = 0.0
        board_h = self.board.height
        board_w = self.board.width
        for local_y, row in enumerate(piece.shape):
            for local_x, cell in enumerate(row):
                if not cell:
                    continue
                x = piece.x + local_x
                y = drop_y + local_y
                if x < 0 or x >= board_w:
                    continue
                for ay in range(y + 1, board_h):
                    if self.board.occupancy[ay][x]:
                        offset = anim_lookup.get((ay, x), 0.0)
                        if offset < min_offset:
                            min_offset = offset
                        break
        return min_offset

    def _capture_board_state_for_failed_lock(self) -> dict:
        board = self.board
        return {
            'grid': [row[:] for row in board.grid],
            'texture_grid': [row[:] for row in board.texture_grid],
            'occupancy': [row[:] for row in board.occupancy],
            'gold': [row[:] for row in board.gold],
            'owners': [row[:] for row in board.owners],
            'score': board.score,
            'lines_cleared': board.lines_cleared,
            'level_lines_cleared': getattr(board, 'level_lines_cleared', 0),
            'level': board.level,
            'combo': board.combo,
            'tetrises': board.tetrises,
            'back_to_back': board.back_to_back,
            'last_cleared_lines': list(board.last_cleared_lines),
            'last_cleared_colors': dict(board.last_cleared_colors),
            'last_clear_p1_cells': getattr(board, 'last_clear_p1_cells', 0),
            'last_clear_p2_cells': getattr(board, 'last_clear_p2_cells', 0),
            'last_clear_row_colors': dict(getattr(board, 'last_clear_row_colors', {})),
            '_locked_out': getattr(board, '_locked_out', False),
            '_last_lock_out': getattr(board, '_last_lock_out', False),
        }

    def _restore_board_state_after_failed_lock(self, snapshot: dict) -> None:
        board = self.board
        board.grid = [row[:] for row in snapshot['grid']]
        board.texture_grid = [row[:] for row in snapshot['texture_grid']]
        board.occupancy = [row[:] for row in snapshot['occupancy']]
        board.gold = [row[:] for row in snapshot['gold']]
        board.owners = [row[:] for row in snapshot['owners']]
        board.score = snapshot['score']
        board.lines_cleared = snapshot['lines_cleared']
        board.level_lines_cleared = snapshot['level_lines_cleared']
        board.level = snapshot['level']
        board.combo = snapshot['combo']
        board.tetrises = snapshot['tetrises']
        board.back_to_back = snapshot['back_to_back']
        board.last_cleared_lines = list(snapshot['last_cleared_lines'])
        board.last_cleared_colors = dict(snapshot['last_cleared_colors'])
        board.last_clear_p1_cells = snapshot['last_clear_p1_cells']
        board.last_clear_p2_cells = snapshot['last_clear_p2_cells']
        board.last_clear_row_colors = dict(snapshot['last_clear_row_colors'])
        board._locked_out = snapshot['_locked_out']
        board._last_lock_out = snapshot['_last_lock_out']

    def _draw_pending_line_clear_rows(self, ox: int, oy: int, cs: int, bw: int) -> None:
        """Sweep öncesi temizlenen satırların snapshot'unu çiz.

        Board clear_lines() satırları anında sildiği için, sweep ilerlerken
        görünür kalması gereken bloklar pending snapshot'tan çizilir.
        """
        if (
            not self.effects_enabled
            or not self.line_clear_sweep_active
            or not self.line_clear_pending_rows
            or not self.line_clear_pending_colors
        ):
            return

        cleared_count = max(1, len(self.line_clear_sweep_rows or self.line_clear_pending_rows))
        sweep_width = self._get_line_sweep_length_px(cs, cleared_count)
        sweep_x = ox + int(self.line_clear_sweep_progress * (bw + sweep_width)) - sweep_width
        sweep_front_x = sweep_x + sweep_width
        block_size = cs - 2

        for row in self.line_clear_pending_rows:
            if not (0 <= row < self.board.height):
                continue
            row_colors = self.line_clear_pending_colors.get(row)
            if not row_colors:
                continue
            max_cols = min(self.board.width, len(row_colors))
            for x in range(max_cols):
                color = row_colors[x]
                if color == BLACK:
                    continue
                cell_center_x = ox + x * cs + cs // 2
                # Işığın ön kenarı hücreye ulaştığında snapshot artık görünmez.
                if cell_center_x <= sweep_front_x:
                    continue
                block_x = ox + x * cs + 1
                block_y = oy + row * cs + 1
                self.draw_textured_block(block_x, block_y, block_size, color, None, None)

    def _draw_line_clear_waves(self) -> None:
        """Line clear sırasında temizlenen satırlar boyunca yatay dalga çiz.

        Game / PvP / OnlinePvP ile parity için aynı yatay-elips formu kullanır.
        """
        if not self.effects_enabled or not self.line_clear_wave_effects:
            return
        cache = getattr(self, '_effect_surface_cache', None)
        for wave in self.line_clear_wave_effects:
            try:
                alpha = int(wave.get('alpha', 0) or 0)
                if alpha <= 0:
                    continue
                radius = float(wave.get('radius', 0) or 0)
                if radius <= 0:
                    continue
                color = tuple(int(c) for c in wave.get('color', (255, 255, 255))[:3])
                wave_color = (*color, alpha)
                width_px = max(1, int(radius * 2))
                if cache is not None and hasattr(cache, 'get_ellipse_surface'):
                    surface = cache.get_ellipse_surface((width_px, 6), wave_color)
                else:
                    surface = pygame.Surface((width_px, 6), pygame.SRCALPHA)
                    pygame.draw.ellipse(surface, wave_color, surface.get_rect())
                wave_x = int(wave.get('x', 0) or 0) - width_px // 2
                wave_y = int(wave.get('y', 0) or 0) - 3
                self.screen.blit(surface, (wave_x, wave_y))
            except Exception:
                continue

    def _draw_combo_message_overlay(self, board_offset_x: int, board_offset_y: int,
                                    cell_size: int, board_width_px: int,
                                    board_height_px: int) -> None:
        """Combo / Quadrix mesaj overlay'ı (Game / PvP / OnlinePvP ile parity).

        Co-op paylaşılan board'un üst üçte birinde gösterilir; renk ve fade
        eğrisi `combo_popup_style` ortak helper'ları üzerinden alınır.
        """
        if not self.combo_message or self.combo_message_time <= 0:
            return
        try:
            alpha = get_combo_popup_alpha(self.combo_message_time)
            font = getattr(self, 'font_large', None) or _rs.get_font(max(28, int(cell_size * 1.4)), bold=True)
            msg = str(self.combo_message)
            shadow = font.render(msg, True, COMBO_POPUP_SHADOW_COLOR)
            if alpha < 255:
                shadow.set_alpha(alpha)
            cx = int(board_offset_x) + int(board_width_px) // 2
            cy = int(board_offset_y) + int(board_height_px) // 3
            self.screen.blit(shadow, shadow.get_rect(center=(cx + 2, cy + 2)))
            color = get_combo_popup_color(msg)
            text_surf = font.render(msg, True, color)
            if alpha < 255:
                text_surf.set_alpha(alpha)
            self.screen.blit(text_surf, text_surf.get_rect(center=(cx, cy)))
        except Exception:
            pass

    # ==================================================================
    # Event sistemi (kampanya entegrasyonu)
    # ==================================================================

    def _emit_event(self, event_type: str, event_data: dict) -> None:
        """Alt sınıflar veya dinleyiciler için oyun olayı yayınla."""
        for listener in self._event_listeners:
            try:
                listener(event_type, event_data)
            except Exception:
                pass

    # ==================================================================
    # Hareket yardımcıları
    # ==================================================================

    def _try_move(self, player: str, dx: int) -> bool:
        piece = self.p1_current_piece if player == 'P1' else self.p2_current_piece
        if piece is None:
            return False
        piece.x += dx
        if not self.board.is_valid_position_for_player(piece, player):
            piece.x -= dx
            return False
        return True

    def _try_rotate(self, player: str) -> bool:
        piece = self.p1_current_piece if player == 'P1' else self.p2_current_piece
        if piece is None:
            return False
        original_x = piece.x
        piece.rotate()
        if self.board.is_valid_position_for_player(piece, player):
            return True
        # Wall kick dene
        for dx in [1, -1, 2, -2]:
            piece.x = original_x + dx
            if self.board.is_valid_position_for_player(piece, player):
                return True
        # Başarısız — geri al
        piece.x = original_x
        for _ in range(3):
            piece.rotate()
        return False

    def _hard_drop(self, player: str) -> None:
        piece = self.p1_current_piece if player == 'P1' else self.p2_current_piece
        if piece is None:
            return
        start_y = piece.y
        while self.board.is_valid_position_for_player(piece, player, dy=1):
            piece.y += 1
        # Drop trail efekti
        if piece.y > start_y and self.effects_enabled:
            cs = self.cell_size
            ox, oy = self.board_offset_x, self.board_offset_y
            for px, py_abs in piece.get_cells():
                row_offset = py_abs - piece.y  # local row within piece
                trail_x = ox + px * cs
                trail_y_start = oy + (start_y + row_offset) * cs
                trail_y_end = oy + py_abs * cs
                if trail_y_end > trail_y_start:
                    self.create_drop_trail(trail_x, trail_y_start, trail_y_end, piece.color, cs)
            self.trigger_hard_drop_screen_shake()
        self._emit_event('hard_drop', {
            'player': player,
            'piece': piece,
            'start_y': start_y,
            'end_y': piece.y,
        })
        self._lock_and_new_piece(player)
        try:
            from gamepad_manager import get_gamepad_manager
            get_gamepad_manager().rumble(0.3, 0.6, 120)
        except Exception:
            pass

    def _reset_player_lock_state(self, player: str) -> None:
        if player == 'P1':
            self.p1_grounded = False
            self.p1_lock_timer = 0.0
        else:
            self.p2_grounded = False
            self.p2_lock_timer = 0.0

    def _set_unfreeze_lock_delay_active(self, player: str, active: bool) -> None:
        if player == 'P1':
            self._p1_unfreeze_lock_delay_active = bool(active)
        else:
            self._p2_unfreeze_lock_delay_active = bool(active)

    def _unfreeze_lock_delay_active(self, player: str) -> bool:
        return (
            bool(getattr(self, '_p1_unfreeze_lock_delay_active', False))
            if player == 'P1'
            else bool(getattr(self, '_p2_unfreeze_lock_delay_active', False))
        )

    def _piece_in_unfreeze_danger_rows(self, piece: Piece | None) -> bool:
        if piece is None:
            return False
        danger_limit = max(0, int(self._UNFREEZE_DANGER_ROW_COUNT)) - 1
        return any(py <= danger_limit for _px, py in piece.get_cells())

    def _player_has_unfreeze_danger_stack(self, player: str) -> bool:
        cols = self.board._player_columns(player)
        danger_row_count = min(self.board.height, max(0, int(self._UNFREEZE_DANGER_ROW_COUNT)))
        for y in range(danger_row_count):
            for x in cols:
                if self.board.occupancy[y][x]:
                    return True
        return False

    def _refresh_unfreeze_lock_delay_state(self, player: str, piece: Piece | None) -> None:
        if not self._unfreeze_lock_delay_active(player):
            return
        if self._piece_in_unfreeze_danger_rows(piece):
            return
        if self._player_has_unfreeze_danger_stack(player):
            return
        self._set_unfreeze_lock_delay_active(player, False)

    def _effective_lock_delay_for_player(self, player: str, piece: Piece | None) -> float:
        lock_delay = max(0.0, float(getattr(self, 'lock_delay', DEFAULT_LOCK_DELAY)))
        if (
            self._unfreeze_lock_delay_active(player)
            and self._piece_in_unfreeze_danger_rows(piece)
        ):
            return max(lock_delay, float(self._UNFREEZE_DANGER_LOCK_DELAY_MS))
        return lock_delay

    def _mark_player_grounded(self, player: str) -> None:
        if player == 'P1':
            if not self.p1_grounded:
                self.p1_grounded = True
                self.p1_lock_timer = 0.0
        else:
            if not self.p2_grounded:
                self.p2_grounded = True
                self.p2_lock_timer = 0.0

    def _player_touching_ground(self, player: str) -> bool:
        piece = self.p1_current_piece if player == 'P1' else self.p2_current_piece
        if piece is None:
            return False
        return not self.board.is_valid_position_for_player(piece, player, dy=1)

    def _player_uses_remote_active_authority(self, player: str) -> bool:
        try:
            return str(player) in set(getattr(self, 'remote_authority_players', set()) or set())
        except Exception:
            return False

    def _step_piece_down(self, player: str) -> bool:
        piece = self.p1_current_piece if player == 'P1' else self.p2_current_piece
        if piece is None:
            return False

        piece.y += 1
        if not self.board.is_valid_position_for_player(piece, player):
            piece.y -= 1
            if getattr(self, 'enable_lock_delay', True):
                self._mark_player_grounded(player)
            else:
                self._lock_and_new_piece(player)
            return False

        self._reset_player_lock_state(player)
        return True

    def _update_lock_delay(self, dt: float) -> set[str]:
        locked_players: set[str] = set()
        if not getattr(self, 'enable_lock_delay', True):
            return locked_players

        for player in ('P1', 'P2'):
            frozen = self.p1_frozen if player == 'P1' else self.p2_frozen
            piece = self.p1_current_piece if player == 'P1' else self.p2_current_piece
            if frozen or piece is None:
                self._reset_player_lock_state(player)
                continue

            self._refresh_unfreeze_lock_delay_state(player, piece)
            lock_delay = self._effective_lock_delay_for_player(player, piece)
            if self._player_touching_ground(player):
                self._mark_player_grounded(player)
                if player == 'P1':
                    self.p1_lock_timer += dt
                    if self.p1_lock_timer >= lock_delay:
                        locked_players.add('P1')
                else:
                    self.p2_lock_timer += dt
                    if self.p2_lock_timer >= lock_delay:
                        locked_players.add('P2')
            else:
                self._reset_player_lock_state(player)

        for player in locked_players:
            self._lock_and_new_piece(player)

        return locked_players

    # ==================================================================
    # Hold
    # ==================================================================

    def _use_shared_hold(self, player: str) -> None:
        if player == 'P1' and self.p1_hold_used:
            return
        if player == 'P2' and self.p2_hold_used:
            return

        current = self.p1_current_piece if player == 'P1' else self.p2_current_piece
        held_piece = self.p1_hold_piece if player == 'P1' else self.p2_hold_piece
        if current is None:
            return

        if held_piece is None:
            # Hold boş — aktif parçayı sakla, mevcut next parçasını oyuna al
            if player == 'P1':
                self.p1_hold_piece = current
                new_piece = self.p1_next_piece
            else:
                self.p2_hold_piece = current
                new_piece = self.p2_next_piece
            self._place_at_spawn(new_piece, player)
            if not self.board.is_valid_position_for_player(new_piece, player):
                # Next parçası bile sığmıyor — freeze
                if player == 'P1':
                    self.p1_hold_piece = None
                else:
                    self.p2_hold_piece = None
                self._freeze_player(player)
                return
            if player == 'P1':
                self.p1_current_piece = new_piece
                self.p1_next_piece = self._next_piece('P1')
            else:
                self.p2_current_piece = new_piece
                self.p2_next_piece = self._next_piece('P2')
        else:
            # Hold dolu — swap
            held = held_piece
            self._place_at_spawn(held, player)
            # Rotasyonu sıfırla
            while held.rotation_state != 0:
                held.rotate()
            if not self.board.is_valid_position_for_player(held, player):
                # Swap iptal — hold'daki parça sığmıyor
                return
            if player == 'P1':
                self.p1_hold_piece = current
                self.p1_current_piece = held
            else:
                self.p2_hold_piece = current
                self.p2_current_piece = held

        if player == 'P1':
            self.p1_hold_used = True
        else:
            self.p2_hold_used = True
        self._reset_player_lock_state(player)
        self.sound.play('hold')
        self._emit_event('hold_used', {'player': player})

    # ==================================================================
    # Lock & spawn
    # ==================================================================

    def _lock_and_new_piece(self, player: str) -> None:
        piece = self.p1_current_piece if player == 'P1' else self.p2_current_piece
        if piece is None:
            return

        prev_score = self.board.score
        board_snapshot = self._capture_board_state_for_failed_lock()

        # Kilitle (lock_piece_for_player → Board.lock_piece → clear_lines zinciri)
        cleared = self.board.lock_piece_for_player(piece, player)
        player_locked_out = self.board.consume_last_lock_out()

        if player_locked_out:
            self._restore_board_state_after_failed_lock(board_snapshot)
            if player == 'P1':
                self.p1_hold_used = False
                self.p1_current_piece = None
            else:
                self.p2_hold_used = False
                self.p2_current_piece = None
            self._reset_player_lock_state(player)
            self._freeze_player(player)
            return

        # Lock explosion parçacıkları
        if self._particle_effects_enabled():
            cs = self.cell_size
            ox, oy = self.board_offset_x, self.board_offset_y
            for px, py in piece.get_cells():
                if py >= 0:
                    cx = ox + px * cs + cs // 2
                    cy = oy + py * cs + cs // 2
                    self.create_lock_explosion(cx, cy, piece.color, cs)

        # Parça yerleştirildi event'i
        self._emit_event('piece_placed', {'player': player, 'piece': piece})

        if cleared == 0:
            self.sound.play('lock')

        if cleared > 0:
            # Skor delta'sını al (Board kendi hesaplamasını yaptı)
            delta = self.board.score - prev_score
            self.team_score += delta
            if player == 'P1':
                self.p1_score_contribution += delta
            else:
                self.p2_score_contribution += delta
            total_score_contribution = self.p1_score_contribution + self.p2_score_contribution
            if total_score_contribution > 0:
                self.p1_score_contribution_pct = round(100 * self.p1_score_contribution / total_score_contribution)
                self.p2_score_contribution_pct = 100 - self.p1_score_contribution_pct
            self.total_lines_cleared += cleared

            # Seviye & hız
            self.level = (self.total_lines_cleared // 5) + 1
            self.fall_speed = float(
                get_level_fall_speed_ms(
                    self.level,
                    initial_speed=900,
                    min_speed=LEVEL_SPEED_MIN_MS,
                )
            )

            # Katkı güncelle
            p1c = self.board.last_clear_p1_cells
            p2c = self.board.last_clear_p2_cells
            self.p1_total_cells += p1c
            self.p2_total_cells += p2c
            total = self.p1_total_cells + self.p2_total_cells
            if total > 0:
                self.p1_contribution_pct = round(100 * self.p1_total_cells / total)
                self.p2_contribution_pct = 100 - self.p1_contribution_pct

            # Ses
            self.sound.play('line' if cleared < 4 else 'tetris')

            # Combo / Quadrix mesajı (Game / PvP / OnlinePvP ile parity için
            # `DOUBLE!` / `TRIPLE!` / `QUADRIX!` overlay'ı co-op'ta da gösterilir).
            if cleared == 4:
                self.combo_message = "QUADRIX!"
                self.combo_message_time = 120
            elif cleared >= 2:
                if cleared == 2:
                    self.combo_message = "DOUBLE!"
                elif cleared == 3:
                    self.combo_message = "TRIPLE!"
                else:
                    self.combo_message = f"{cleared}x CLEAR!"
                combo_count = int(getattr(self.board, 'combo', 0) or 0)
                if combo_count > 1:
                    self.combo_message = f"{self.combo_message}  x{combo_count} Combo"
                self.combo_message_time = 120
            else:
                combo_count = int(getattr(self.board, 'combo', 0) or 0)
                if combo_count > 1:
                    self.combo_message = f"x{combo_count} Combo!"
                    self.combo_message_time = 90

            # Line clear visual effects — CoopBoard.clear_lines() satır renklerini kaydetmiştir
            cleared_rows = list(getattr(self.board, 'last_clear_row_colors', {}).keys())
            if cleared_rows:
                self.line_clear_pending_colors = dict(self.board.last_clear_row_colors)
                self.line_clear_pending_rows = list(cleared_rows)
                self._start_line_clear_sweep(cleared_rows)
                self._start_block_fall_animation(cleared_rows)
                # Game / PvP ile parity için: dalga + parçacık + Quadrix burst
                if self.effects_enabled:
                    cs = max(1, int(self.cell_size))
                    ox = int(self.board_offset_x)
                    oy = int(self.board_offset_y)
                    board_width_cells = max(1, int(self.board.width))
                    board_height_cells = max(1, int(self.board.height))
                    try:
                        _queue_wave_effects(
                            self.line_clear_wave_effects,
                            cleared_rows,
                            ox,
                            oy,
                            cs,
                            board_width_cells,
                        )
                    except Exception:
                        pass
                    try:
                        self.create_line_clear_particles(
                            cleared_rows,
                            ox,
                            oy,
                            cs,
                            board=self.board,
                        )
                    except Exception:
                        pass
                    try:
                        _trigger_combo_burst(
                            self,
                            cleared_rows,
                            int(cleared),
                            ox,
                            oy,
                            cs,
                            board_width_cells,
                            board_height_cells,
                        )
                    except Exception:
                        pass
            # Tetris shake
            if cleared >= 4:
                self.trigger_screen_shake(intensity=7, duration=20 / 60.0)
            elif cleared >= 2:
                self.trigger_screen_shake(intensity=3, duration=10 / 60.0)

            # Gamepad titreşimi - line clear
            try:
                from gamepad_manager import get_gamepad_manager
                if cleared >= 4:
                    get_gamepad_manager().rumble(0.8, 1.0, 400)
                elif cleared >= 2:
                    get_gamepad_manager().rumble(0.4, 0.5, 200)
            except Exception:
                pass

            # Event yayınla
            self._emit_event('lines_cleared', {
                'lines': cleared,
                'total_lines': self.total_lines_cleared,
                'player': player,
                'p1_cells': p1c,
                'p2_cells': p2c,
            })
            self._emit_event('score_update', {'score': self.team_score})
            if cleared >= 4:
                self._emit_event('tetris', {'player': player})

            # Unfreeze kontrolü
            self._try_unfreeze_players()

        # Hold hakkını sıfırla
        if player == 'P1':
            self.p1_hold_used = False
            self.p1_current_piece = None
        else:
            self.p2_hold_used = False
            self.p2_current_piece = None

        self._reset_player_lock_state(player)

        # Yeni parça spawn
        self._try_spawn_for_player(player)

    def _try_spawn_for_player(self, player: str, force: bool = False) -> None:
        if not force and self._player_spawner_halted(player):
            return

        next_piece = self.p1_next_piece if player == 'P1' else self.p2_next_piece
        self._place_at_spawn(next_piece, player)
        if self.board.is_valid_position_for_player(next_piece, player):
            if player == 'P1':
                self.p1_current_piece = next_piece
                self.p1_next_piece = self._next_piece('P1')
            else:
                self.p2_current_piece = next_piece
                self.p2_next_piece = self._next_piece('P2')
            self._reset_player_lock_state(player)
        else:
            self._freeze_player(player)

    def _freeze_player(self, player: str) -> None:
        try:
            remote_players = getattr(self, 'remote_authority_players', None)
            if isinstance(remote_players, set):
                remote_players.discard(player)
        except Exception:
            pass
        if player == 'P1':
            self.p1_frozen = True
            self.p1_current_piece = None
        else:
            self.p2_frozen = True
            self.p2_current_piece = None
        self._set_unfreeze_lock_delay_active(player, False)
        self._reset_player_lock_state(player)
        self._emit_event('player_frozen', {'player': player})
        self._check_double_freeze()

    def _check_double_freeze(self) -> None:
        if self.p1_frozen and self.p2_frozen:
            self._activate_game_over()

    def _try_unfreeze_players(self) -> None:
        """Satır temizliği sonrası çağrılır. Hemen unfreeze etmez, pending flag set eder."""
        if self.p1_frozen:
            test = Piece(x=0, y=0, shape_index=self.p1_next_piece.shape_index)
            self._place_at_spawn(test, 'P1')
            if self.board.is_valid_position_for_player(test, 'P1'):
                self._p1_pending_unfreeze = True
        if self.p2_frozen:
            test = Piece(x=0, y=0, shape_index=self.p2_next_piece.shape_index)
            self._place_at_spawn(test, 'P2')
            if self.board.is_valid_position_for_player(test, 'P2'):
                self._p2_pending_unfreeze = True

    def _do_unfreeze(self, player: str) -> None:
        """Resume a frozen player once their spawn area is open again."""
        try:
            remote_players = getattr(self, 'remote_authority_players', None)
            if isinstance(remote_players, set):
                remote_players.discard(player)
        except Exception:
            pass
        if player == 'P1':
            self.p1_frozen = False
            self._p1_pending_unfreeze = False
            self.p1_hold_used = False
            if self._player_spawner_halted('P1'):
                self.p1_current_piece = None
                self._reset_player_lock_state('P1')
                return
            next_p = self.p1_next_piece
            self._place_at_spawn(next_p, 'P1')
            if self.board.is_valid_position_for_player(next_p, 'P1'):
                self.p1_current_piece = next_p
                self.p1_next_piece = self._next_piece('P1')
                self._reset_player_lock_state('P1')
                self._set_unfreeze_lock_delay_active('P1', True)
            else:
                self._freeze_player('P1')
        else:
            self.p2_frozen = False
            self._p2_pending_unfreeze = False
            self.p2_hold_used = False
            if self._player_spawner_halted('P2'):
                self.p2_current_piece = None
                self._reset_player_lock_state('P2')
                return
            next_p = self.p2_next_piece
            self._place_at_spawn(next_p, 'P2')
            if self.board.is_valid_position_for_player(next_p, 'P2'):
                self.p2_current_piece = next_p
                self.p2_next_piece = self._next_piece('P2')
                self._reset_player_lock_state('P2')
                self._set_unfreeze_lock_delay_active('P2', True)
            else:
                self._freeze_player('P2')

    # ==================================================================
    # handle_input
    # ==================================================================

    def handle_input(self):
        """Kullanıcı girdilerini işle. True=devam, False/'menu'=çık."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False

            if self._is_focus_loss_event(event):
                if not self.paused and not self.game_over:
                    self.paused = True
                    self.pause_menu_selected = 0
                    try:
                        self.sound.duck_music()
                    except Exception:
                        pass
                continue

            # Gamepad hot-plug: bağlantı kopması durumunda otomatik pause.
            try:
                from gamepad_manager import handle_gamepad_hotplug_event as _gp_hotplug
                hotplug_result = _gp_hotplug(event)
            except Exception:
                hotplug_result = None
            if hotplug_result is not None:
                if hotplug_result == 'disconnected' and not self.paused and not self.game_over:
                    self.paused = True
                    self.pause_menu_selected = 0
                    try:
                        self.sound.duck_music()
                    except Exception:
                        pass
                continue

            if event.type == pygame.VIDEORESIZE:
                req_w = max(event.w, 800)
                req_h = max(event.h, 600)
                # Overlay backend (gl_compat/sdl2) aktif ve boyut sabitse create_display ÇAĞIRMA.
                _gl_skip = False
                try:
                    import platform_utils as _pu
                    _gl_skip = _pu.overlay_should_skip_rebuild(req_w, req_h)
                    if _gl_skip:
                        _gs = _pu.overlay_active_game_surface()
                        if _gs is not None:
                            self.screen = _gs
                except Exception:
                    _gl_skip = False
                if not _gl_skip:
                    self.screen = create_display(req_w, req_h, fullscreen=True, resizable=False, borderless=True)
                self.window_width = self.screen.get_width()
                self.window_height = self.screen.get_height()
                self._layout_key = None
                continue

            if self.paused and not self.game_over and getattr(self, '_pause_settings_active', False):
                pause_settings_action = self._handle_pause_settings_input(event)
                if pause_settings_action is not None:
                    return pause_settings_action
                continue

            # -- Pause menü input --
            if self.paused and not self.game_over:
                if event.type in (pygame.MOUSEMOTION, pygame.MOUSEWHEEL, pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
                    action = self._handle_pause_menu_input(event)
                    if action == 'resume':
                        self.paused = False
                        self.sound.unduck_music()
                    elif action == 'main_menu':
                        return 'menu'
                    continue
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE or event.key == self.pvp_controls.get('pause'):
                        self.paused = False
                        self.sound.unduck_music()
                        continue
                    action = self._handle_pause_menu_input(event)
                    if action == 'resume':
                        self.paused = False
                        self.sound.unduck_music()
                    elif action == 'main_menu':
                        return 'menu'
                    continue

            if event.type != pygame.KEYDOWN and event.type != pygame.KEYUP:
                # Game over butonları
                if self.game_over and event.type == pygame.MOUSEBUTTONDOWN and getattr(event, 'button', None) == 1:
                    if getattr(event, 'from_gamepad', False) and getattr(event, 'gamepad_context', 'game') == 'game':
                        continue
                    pos = normalize_mouse_pos(getattr(event, 'pos', None)) or get_mouse_pos()
                    peek_rect = getattr(self, '_game_over_peek_rect', None)
                    if peek_rect is not None and peek_rect.collidepoint(pos):
                        self._game_over_peek_active = not getattr(self, '_game_over_peek_active', False)
                        continue
                    if getattr(self, '_game_over_peek_active', False):
                        continue
                    restart_rect = getattr(self, '_game_over_restart_rect', None)
                    exit_rect = getattr(self, '_game_over_exit_rect', None)
                    if restart_rect is not None and restart_rect.collidepoint(pos):
                        self.restart()
                        continue
                    if exit_rect is not None and exit_rect.collidepoint(pos):
                        return 'menu'
                    continue
                continue

            # -- KEYDOWN --
            if event.type == pygame.KEYDOWN:
                # Pause toggle
                if event.key == self.pvp_controls.get('pause') or event.key == pygame.K_ESCAPE:
                    if self.game_over:
                        return 'menu'
                    self.paused = True
                    self.pause_menu_selected = 0
                    self.sound.duck_music()
                    continue

                if self.game_over:
                    if event.key == pygame.K_r:
                        self.restart()
                        continue
                    continue

                if self.paused:
                    continue

                debug_controls = self.pvp_controls.get('debug', {})
                if event.key == debug_controls.get('coop_spawner_left'):
                    self._toggle_player_spawner_halt('P1')
                    continue
                if event.key == debug_controls.get('coop_spawner_right'):
                    self._toggle_player_spawner_halt('P2')
                    continue

                c1 = self.pvp_controls['player1']
                c2 = self.pvp_controls['player2']

                # --- P1 input ---
                if not self.p1_frozen and self.p1_current_piece is not None:
                    if event.key == c1['move_left']:
                        if self._try_move('P1', -1):
                            self.sound.play('move')
                        self.p1_das_direction = -1
                        self.p1_das_timer = 0
                        self.p1_das_repeat_timer = 0
                        self.p1_das_charged = False
                    elif event.key == c1['move_right']:
                        if self._try_move('P1', 1):
                            self.sound.play('move')
                        self.p1_das_direction = 1
                        self.p1_das_timer = 0
                        self.p1_das_repeat_timer = 0
                        self.p1_das_charged = False
                    elif event.key == c1['soft_drop']:
                        self.p1_soft_drop_active = True
                        self.p1_soft_drop_timer = 0
                        self._step_piece_down('P1')
                    elif event.key == c1['rotate']:
                        self._try_rotate('P1')
                        self.sound.play('rotate')
                    elif event.key == c1['hard_drop']:
                        self._hard_drop('P1')
                        self.sound.play('drop')
                    elif event.key == c1['hold']:
                        self._use_shared_hold('P1')

                # --- P2 input ---
                if not self.p2_frozen and self.p2_current_piece is not None:
                    if event.key == c2['move_left']:
                        if self._try_move('P2', -1):
                            self.sound.play('move')
                        self.p2_das_direction = -1
                        self.p2_das_timer = 0
                        self.p2_das_repeat_timer = 0
                        self.p2_das_charged = False
                    elif event.key == c2['move_right']:
                        if self._try_move('P2', 1):
                            self.sound.play('move')
                        self.p2_das_direction = 1
                        self.p2_das_timer = 0
                        self.p2_das_repeat_timer = 0
                        self.p2_das_charged = False
                    elif event.key == c2['soft_drop']:
                        self.p2_soft_drop_active = True
                        self.p2_soft_drop_timer = 0
                        self._step_piece_down('P2')
                    elif event.key == c2['rotate']:
                        self._try_rotate('P2')
                        self.sound.play('rotate')
                    elif event.key == c2['hard_drop']:
                        self._hard_drop('P2')
                        self.sound.play('drop')
                    elif event.key == c2['hold']:
                        self._use_shared_hold('P2')

            # -- KEYUP --
            elif event.type == pygame.KEYUP:
                c1 = self.pvp_controls['player1']
                c2 = self.pvp_controls['player2']
                if event.key == c1['move_left']:
                    if self.p1_das_direction == -1:
                        self.p1_das_direction = 0
                        self.p1_das_charged = False
                elif event.key == c1['move_right']:
                    if self.p1_das_direction == 1:
                        self.p1_das_direction = 0
                        self.p1_das_charged = False
                elif event.key == c1['soft_drop']:
                    self.p1_soft_drop_active = False
                elif event.key == c2['move_left']:
                    if self.p2_das_direction == -1:
                        self.p2_das_direction = 0
                        self.p2_das_charged = False
                elif event.key == c2['move_right']:
                    if self.p2_das_direction == 1:
                        self.p2_das_direction = 0
                        self.p2_das_charged = False
                elif event.key == c2['soft_drop']:
                    self.p2_soft_drop_active = False

        return True

    # ==================================================================
    # inject_remote_input — Online Co-op: Host injects guest actions
    # ==================================================================

    def inject_remote_input(self, player: str, action: str):
        """Online Co-op için uzaktan gelen input aksiyonunu uygula.

        Args:
            player: 'P1' veya 'P2'
            action: 'move_left', 'move_right', 'soft_drop', 'hard_drop',
                    'rotate', 'hold', 'soft_drop_start', 'soft_drop_stop',
                    'das_start_left', 'das_start_right', 'das_stop',
                    'das_stop_left', 'das_stop_right'
        """
        if self.game_over or self.paused:
            return

        frozen = self.p1_frozen if player == 'P1' else self.p2_frozen
        piece = self.p1_current_piece if player == 'P1' else self.p2_current_piece
        if frozen or piece is None:
            return

        if action == 'move_left':
            if self._try_move(player, -1):
                self.sound.play('move')
            if player == 'P1':
                self.p1_das_direction = -1
                self.p1_das_timer = 0
                self.p1_das_repeat_timer = 0
                self.p1_das_charged = False
            else:
                self.p2_das_direction = -1
                self.p2_das_timer = 0
                self.p2_das_repeat_timer = 0
                self.p2_das_charged = False

        elif action == 'move_right':
            if self._try_move(player, 1):
                self.sound.play('move')
            if player == 'P1':
                self.p1_das_direction = 1
                self.p1_das_timer = 0
                self.p1_das_repeat_timer = 0
                self.p1_das_charged = False
            else:
                self.p2_das_direction = 1
                self.p2_das_timer = 0
                self.p2_das_repeat_timer = 0
                self.p2_das_charged = False

        elif action == 'soft_drop_start':
            if player == 'P1':
                self.p1_soft_drop_active = True
                self.p1_soft_drop_timer = 0
            else:
                self.p2_soft_drop_active = True
                self.p2_soft_drop_timer = 0
            self._step_piece_down(player)

        elif action == 'soft_drop_stop':
            if player == 'P1':
                self.p1_soft_drop_active = False
            else:
                self.p2_soft_drop_active = False

        elif action == 'rotate':
            self._try_rotate(player)
            self.sound.play('rotate')

        elif action == 'hard_drop':
            self._hard_drop(player)
            self.sound.play('drop')

        elif action == 'hold':
            self._use_shared_hold(player)

        elif action in ('das_stop', 'das_stop_left', 'das_stop_right'):
            if player == 'P1':
                if (
                    action == 'das_stop'
                    or (action == 'das_stop_left' and self.p1_das_direction == -1)
                    or (action == 'das_stop_right' and self.p1_das_direction == 1)
                ):
                    self.p1_das_direction = 0
                    self.p1_das_charged = False
            else:
                if (
                    action == 'das_stop'
                    or (action == 'das_stop_left' and self.p2_das_direction == -1)
                    or (action == 'das_stop_right' and self.p2_das_direction == 1)
                ):
                    self.p2_das_direction = 0
                    self.p2_das_charged = False

    # ==================================================================
    # update
    # ==================================================================

    def update(self, delta_time: float) -> None:
        # Müzik güncelle
        try:
            if self.sound_enabled and not getattr(self, '_suppress_internal_music_tick', False):
                self.sound.update_music_playlist()
        except Exception:
            pass

        # Efekt güncellemeleri (paused/gameover'da da çalışmalı — animasyon fade'leri)
        if self.effects_enabled:
            self.update_particles(delta_time)
            self.update_ambient_particles(delta_time)
            self.update_drop_trails(delta_time)
            self._update_line_clear_effects(delta_time)
            step_screen_shake(self, dt_ms=delta_time)

        if self.game_over or self.paused:
            return

        self.elapsed_time += delta_time
        self._emit_event('time_update', {'elapsed': self.elapsed_time / 1000.0})

        # DAS güncelle
        self._update_das(delta_time)
        # Soft drop güncelle
        self._update_soft_drop(delta_time)
        locked_players = self._update_lock_delay(delta_time)

        # Satır temizleme animasyonu oynarken otomatik gravity duraklatılır
        # (shared board → tek animasyon state). Soft/hard drop ayrı yollardan
        # işlendiği için oyuncular yine de parça indirebilir.
        line_clear_anim_active = bool(
            getattr(self, 'line_clear_sweep_active', False)
        ) or bool(getattr(self, 'falling_block_animations', None))

        # --- P1 gravity ---
        if 'P1' not in locked_players and not self.p1_frozen and self.p1_current_piece is not None:
            if line_clear_anim_active:
                self.p1_fall_time = 0
            else:
                self.p1_fall_time += delta_time
                if self.p1_fall_time >= self.fall_speed:
                    self.p1_fall_time = 0
                    self._step_piece_down('P1')
        elif self._p1_pending_unfreeze:
            self.p1_fall_time += delta_time
            if self.p1_fall_time >= self.fall_speed:
                self.p1_fall_time = 0
                self._do_unfreeze('P1')

        # --- P2 gravity ---
        if (
            'P2' not in locked_players
            and not self.p2_frozen
            and self.p2_current_piece is not None
            and not self._player_uses_remote_active_authority('P2')
        ):
            if line_clear_anim_active:
                self.p2_fall_time = 0
            else:
                self.p2_fall_time += delta_time
                if self.p2_fall_time >= self.fall_speed:
                    self.p2_fall_time = 0
                    self._step_piece_down('P2')
        elif self._p2_pending_unfreeze:
            self.p2_fall_time += delta_time
            if self.p2_fall_time >= self.fall_speed:
                self.p2_fall_time = 0
                self._do_unfreeze('P2')
        elif self._player_uses_remote_active_authority('P2'):
            self.p2_fall_time = 0

    # ------------------------------------------------------------------
    # DAS
    # ------------------------------------------------------------------

    def _update_das(self, dt: float) -> None:
        if self._das_settings_dirty:
            try:
                self._cached_das_delay = float(self.settings_manager.get('das_delay', DAS_DELAY)) if self.settings_manager else float(DAS_DELAY)
            except Exception:
                self._cached_das_delay = float(DAS_DELAY)
            try:
                self._cached_das_repeat = float(self.settings_manager.get('das_repeat', DAS_REPEAT)) if self.settings_manager else float(DAS_REPEAT)
            except Exception:
                self._cached_das_repeat = float(DAS_REPEAT)
            self._cached_das_delay = max(0.0, self._cached_das_delay)
            self._cached_das_repeat = max(1.0, self._cached_das_repeat)
            self._das_settings_dirty = False
        delay = self._cached_das_delay
        repeat = self._cached_das_repeat

        for player in ('P1', 'P2'):
            frozen = self.p1_frozen if player == 'P1' else self.p2_frozen
            if frozen:
                continue
            if self._player_uses_remote_active_authority(player):
                if player == 'P1':
                    self.p1_das_direction = 0
                    self.p1_das_timer = 0
                    self.p1_das_repeat_timer = 0
                    self.p1_das_charged = False
                else:
                    self.p2_das_direction = 0
                    self.p2_das_timer = 0
                    self.p2_das_repeat_timer = 0
                    self.p2_das_charged = False
                continue
            das_dir = self.p1_das_direction if player == 'P1' else self.p2_das_direction
            piece = self.p1_current_piece if player == 'P1' else self.p2_current_piece
            if das_dir == 0 or piece is None:
                continue

            if player == 'P1':
                self.p1_das_timer += dt
                if not self.p1_das_charged:
                    if self.p1_das_timer >= delay:
                        self.p1_das_charged = True
                        self.p1_das_repeat_timer = max(0.0, self.p1_das_timer - delay)
                        if self._try_move('P1', das_dir):
                            self.sound.play('move')
                else:
                    self.p1_das_repeat_timer += dt
                    while self.p1_das_repeat_timer >= repeat:
                        self.p1_das_repeat_timer -= repeat
                        if not self._try_move('P1', das_dir):
                            self.p1_das_repeat_timer = 0
                            break
                        self.sound.play('move')
            else:
                self.p2_das_timer += dt
                if not self.p2_das_charged:
                    if self.p2_das_timer >= delay:
                        self.p2_das_charged = True
                        self.p2_das_repeat_timer = max(0.0, self.p2_das_timer - delay)
                        if self._try_move('P2', das_dir):
                            self.sound.play('move')
                else:
                    self.p2_das_repeat_timer += dt
                    while self.p2_das_repeat_timer >= repeat:
                        self.p2_das_repeat_timer -= repeat
                        if not self._try_move('P2', das_dir):
                            self.p2_das_repeat_timer = 0
                            break
                        self.sound.play('move')

    def _update_soft_drop(self, dt: float) -> None:
        speed = self._SOFT_DROP_SPEED
        for player in ('P1', 'P2'):
            frozen = self.p1_frozen if player == 'P1' else self.p2_frozen
            active = self.p1_soft_drop_active if player == 'P1' else self.p2_soft_drop_active
            piece = self.p1_current_piece if player == 'P1' else self.p2_current_piece
            if self._player_uses_remote_active_authority(player):
                if player == 'P1':
                    self.p1_soft_drop_active = False
                    self.p1_soft_drop_timer = 0
                else:
                    self.p2_soft_drop_active = False
                    self.p2_soft_drop_timer = 0
                continue
            if not active or frozen or piece is None:
                continue
            if player == 'P1':
                self.p1_soft_drop_timer += dt
                if self.p1_soft_drop_timer >= speed:
                    self.p1_soft_drop_timer = 0
                    self._step_piece_down('P1')
            else:
                self.p2_soft_drop_timer += dt
                if self.p2_soft_drop_timer >= speed:
                    self.p2_soft_drop_timer = 0
                    self._step_piece_down('P2')

    # ==================================================================
    # Pause menü (PvP ile aynı yapı)
    # ==================================================================

    @property
    def pause_menu_options(self):
        return list(self._pause_menu_keys)

    def wants_mouse_visible(self) -> bool:
        """Gameplay sırasında mouse görünür mü?

        Co-op normal oynanışta imleci gizler; pause ve oyun sonu gibi
        overlay ekranlarında tekrar görünür olmalıdır.
        """
        if getattr(self, 'paused', False):
            return True
        if getattr(self, 'game_over', False):
            return True
        return False

    def _handle_pause_menu_input(self, event):
        def apply_option(opt):
            if opt == 'resume':
                return 'resume'
            if opt == 'settings':
                self._open_pause_settings()
                return None
            if opt == 'music':
                self.sound.music_enabled = not self.sound.music_enabled
                if self.settings_manager:
                    self.settings_manager.set('music_enabled', self.sound.music_enabled)
                if self.sound.music_enabled:
                    self._start_music()
                else:
                    self.sound.stop_music()
                return None
            if opt == 'sound_effects':
                self.sound.sfx_enabled = not self.sound.sfx_enabled
                if self.settings_manager:
                    self.settings_manager.set('sound_enabled', self.sound.sfx_enabled)
                return None
            if opt == 'main_menu':
                return 'main_menu'
            return None

        def adjust_vol(opt, delta=None, absolute=None):
            if opt == 'music_volume':
                target = (self.sound.music_volume + (delta or 0.0)) if absolute is None else absolute
                nv = max(0.0, min(1.0, float(target)))
                self.sound.set_music_volume(nv)
                if self.settings_manager:
                    self.settings_manager.set('music_volume', nv)
            elif opt == 'sfx_volume':
                target = (self.sound.sfx_volume + (delta or 0.0)) if absolute is None else absolute
                nv = max(0.0, min(1.0, float(target)))
                self.sound.set_volume(nv)
                if self.settings_manager:
                    self.settings_manager.set('sfx_volume', nv)

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
                return apply_option(self.pause_menu_options[self.pause_menu_selected])
            if event.key in (pygame.K_LEFT, pygame.K_RIGHT):
                opt = self.pause_menu_options[self.pause_menu_selected]
                d = 0.1 if event.key == pygame.K_RIGHT else -0.1
                adjust_vol(opt, delta=d)
                return None
            if event.key == pygame.K_BACKSPACE:
                return 'main_menu'
            if event.key == pygame.K_ESCAPE:
                return 'resume'
            return None

        if event.type == pygame.MOUSEWHEEL:
            opt = self.pause_menu_options[self.pause_menu_selected]
            if opt in ('music_volume', 'sfx_volume'):
                adjust_vol(opt, delta=0.05 if event.y > 0 else -0.05)
            else:
                step = -1 if event.y > 0 else 1
                self.pause_menu_selected = (self.pause_menu_selected + step) % len(self.pause_menu_options)
                self.sound.play('move')
            return None

        if event.type == pygame.MOUSEMOTION:
            pos = normalize_mouse_pos(getattr(event, 'pos', None)) or get_mouse_pos()
            if self._pause_vol_drag_active and self._pause_vol_drag_option:
                bar = (self._pause_volume_rects or {}).get(self._pause_vol_drag_option)
                if bar and bar.width > 0:
                    adjust_vol(self._pause_vol_drag_option, absolute=max(0.0, min(1.0, (pos[0] - bar.x) / bar.width)))
                return None
            for idx, rect in enumerate(self._pause_option_rects or []):
                if rect and rect.collidepoint(pos):
                    self.pause_menu_selected = idx
                    break
            return None

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = normalize_mouse_pos(getattr(event, 'pos', None)) or get_mouse_pos()
            for idx, rect in enumerate(self._pause_option_rects or []):
                if rect and rect.collidepoint(pos):
                    self.pause_menu_selected = idx
                    opt = self.pause_menu_options[idx]
                    if opt in ('music_volume', 'sfx_volume'):
                        bar = (self._pause_volume_rects or {}).get(opt)
                        if bar and bar.width > 0:
                            adjust_vol(opt, absolute=max(0.0, min(1.0, (pos[0] - bar.x) / bar.width)))
                            self._pause_vol_drag_active = True
                            self._pause_vol_drag_option = opt
                        return None
                    return apply_option(opt)
            return None

        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self._pause_vol_drag_active = False
            self._pause_vol_drag_option = ''
            return None

        return None

    # ==================================================================
    # draw
    # ==================================================================

    def _render_game(self) -> None:
        """Oyun sahnesini çiz (flip çağırmaz — alt sınıflar overlay ekleyebilir)."""
        self._calculate_layout()
        curtain_cover_width = self._get_opening_curtain_cover_width()
        visible_outer_rect = None
        if curtain_cover_width > 0:
            visible_width = max(0, self.window_width - (curtain_cover_width * 2))
            if visible_width > 0:
                visible_outer_rect = pygame.Rect(curtain_cover_width, 0, visible_width, self.window_height)

        skin = self.mode_skin or get_mode_skin('classic')
        # Board skin: classic görünüm + modun renk aksentleri (cached)
        skin_id = id(skin)
        bsc = self._board_skin_cache
        if bsc.get('skin_id') != skin_id:
            try:
                from dataclasses import replace as _replace
                classic = get_mode_skin('classic')
                board_skin = _replace(
                    classic,
                    accent=getattr(skin, 'accent', getattr(classic, 'accent', (0, 210, 255))),
                    panel_border=getattr(skin, 'accent', getattr(classic, 'panel_border', (0, 210, 255))),
                    board_border=getattr(skin, 'accent', getattr(classic, 'board_border', (0, 210, 255))),
                    board_tint=getattr(skin, 'board_tint', getattr(classic, 'board_tint', None)),
                    grid_color=getattr(skin, 'grid_color', getattr(classic, 'grid_color', (50, 50, 80))),
                    overlay='none',
                    overlay_alpha=0,
                )
            except Exception:
                board_skin = skin
            bsc['skin_id'] = skin_id
            bsc['board_skin'] = board_skin
        board_skin = bsc['board_skin']

        # === Arka plan ===
        # Menü ile tutarlı görünüm için retro_style.bg_color kullan
        _fill_color = getattr(retro_style, 'bg_color', getattr(skin, 'outer_bg', (0, 0, 0)))
        bg_alpha = 1.0
        if self.outer_background.is_loaded():
            try:
                bg_alpha = float(getattr(self.outer_background, 'transparency', 1.0))
            except Exception:
                bg_alpha = 1.0
            if bg_alpha < 1.0:
                self.screen.fill(_fill_color)
            if visible_outer_rect is not None:
                self.outer_background.draw_full_screen_region(self.screen, visible_outer_rect)
            else:
                self.outer_background.draw_full_screen(self.screen)
        elif self.background.is_loaded():
            # Yarı-saydam arka plan blend artefaktını önlemek için base fill
            try:
                bg_alpha = float(getattr(self.background, 'transparency', 1.0))
            except Exception:
                bg_alpha = 1.0
            if bg_alpha < 1.0:
                self.screen.fill(_fill_color)
            self.background.draw(self.screen, (0, 0, self.window_width, self.window_height))
        else:
            self.screen.fill(_fill_color)

        # Outer tint: bg_transparency ile orantılı
        _ot = tuple(getattr(skin, 'outer_tint', (0, 0, 0, 0)))
        if len(_ot) >= 4 and _ot[3] > 0:
            _tint_a = int(_ot[3] * bg_alpha) if bg_alpha < 1.0 else _ot[3]
            if _tint_a > 0:
                try:
                    from dataclasses import replace as _dc_replace
                    apply_outer_tint(self.screen, _dc_replace(skin, outer_tint=(*_ot[:3], _tint_a)), visible_outer_rect)
                except Exception:
                    apply_outer_tint(self.screen, skin, visible_outer_rect)

        # Falling blocks layer
        if self.effects_enabled and self.falling_blocks:
            self.falling_blocks.update(self.screen)
            self.falling_blocks.draw(self.screen)

        # Ambient particles (arka plan üstünde, board altında)
        if self.effects_enabled:
            self.draw_ambient_particles()

        # Screen shake offset
        shake_x, shake_y = self.get_shake_offset()

        cs = self.cell_size
        bw = self.board.width * cs
        bh = self.board.height * cs
        ox = self.board_offset_x + shake_x
        oy = self.board_offset_y + shake_y

        # === Board arka planı ===
        board_rect = pygame.Rect(ox, oy, bw, bh)
        if self.board_background.is_loaded():
            self.board_background.draw(self.screen, board_rect)
        else:
            pygame.draw.rect(self.screen, (4, 4, 12), board_rect)
        apply_board_tint(self.screen, board_rect, board_skin)
        draw_board_overlay(self.screen, board_rect, board_skin)

        # Grid çizgileri
        self._draw_grid(ox, oy, cs, bw, bh)

        # Kilitli bloklar
        self._draw_locked_blocks(ox, oy, cs)

        # Sweep tamamlanana kadar temizlenen satırların snapshot'unu koru.
        self._draw_pending_line_clear_rows(ox, oy, cs, bw)

        # Line clear sweep efekti
        if (self.effects_enabled and self.line_clear_sweep_active
                and self.line_clear_pending_rows and self.line_clear_pending_colors):
            cleared_count = max(1, len(self.line_clear_sweep_rows))
            sweep_width = self._get_line_sweep_length_px(cs, cleared_count)
            valid_rows = sorted({r for r in self.line_clear_sweep_rows if 0 <= r < self.board.height})
            if valid_rows:
                top_row = valid_rows[0]
                bottom_row = valid_rows[-1]
                group_y = oy + top_row * cs
                group_h = max(cs, (bottom_row - top_row + 1) * cs)
                phase = (pygame.time.get_ticks() // 80) % 8
                sweep_x = ox + int(self.line_clear_sweep_progress * (bw + sweep_width)) - sweep_width
                board_group_rect = pygame.Rect(ox, group_y, bw, group_h)
                draw_rainbow_cat_sweep(self.screen, self._sweep_cat_state, board_group_rect,
                                       sweep_x, sweep_width, phase, self.board.width,
                                       stripe_highlight_enabled=False)

        # Drop trails
        if self.effects_enabled and self.drop_trails:
            self._draw_drop_trails()

        # Orta çizgi
        self._draw_midline(ox, oy, cs, bh)

        # Ghost parçalar
        self._draw_ghost('P1', ox, oy, cs)
        self._draw_ghost('P2', ox, oy, cs)

        # Aktif parçalar
        self._draw_piece(self.p1_current_piece, ox, oy, cs)
        self._draw_piece(self.p2_current_piece, ox, oy, cs)

        # Board frame (PNG)
        if not self._draw_custom_frame(board_rect, "board_frame.png", padding=88, hole_punch=True):
            border_color = getattr(board_skin, 'board_border', (0, 210, 255))
            pygame.draw.rect(self.screen, border_color, board_rect, 3)

        # HUD
        self._draw_hud(ox, oy, cs, bw, bh)

        # Side paneller (next + hold)
        self._draw_side_panels(ox, oy, cs, bw, bh)

        # Particles
        if self.effects_enabled and self.particles:
            self.draw_particles()

        # Line clear dalga efekti (Game / PvP ile parity)
        if self.effects_enabled and self.line_clear_wave_effects:
            self._draw_line_clear_waves()

        # Combo / Quadrix mesaj overlay'ı (Game / PvP / OnlinePvP ile parity)
        if self.combo_message and self.combo_message_time > 0:
            self._draw_combo_message_overlay(ox, oy, cs, bw, bh)

        # Freeze overlay
        if self.p1_frozen:
            self._draw_freeze_overlay('P1', ox, oy, cs, bh)
        if self.p2_frozen:
            self._draw_freeze_overlay('P2', ox, oy, cs, bh)

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

        # Game over (kampanya overlay'i varsa atla — alt sınıf kendi overlay'ini çizer)
        if self.game_over and not getattr(self, 'level_failed', False) and not getattr(self, 'level_complete', False):
            self._draw_game_over_screen()

    def _draw_opening_curtain(self) -> None:
        cover_width = self._get_opening_curtain_cover_width()
        if cover_width <= 0:
            return

        wh = self.window_height
        left_rect = pygame.Rect(0, 0, cover_width, wh)
        right_rect = pygame.Rect(self.window_width - cover_width, 0, cover_width, wh)
        curtain_color = (15, 20, 30)
        pygame.draw.rect(self.screen, curtain_color, left_rect)
        pygame.draw.rect(self.screen, curtain_color, right_rect)

        edge_width = min(6, cover_width)
        if edge_width > 0:
            left_edge_x = cover_width - 1
            right_edge_x = self.window_width - cover_width
            edge_colors = [
                (92, 118, 152),
                (66, 84, 108),
                (46, 58, 77),
            ]
            for offset, color in enumerate(edge_colors):
                if offset >= edge_width:
                    break
                lx = left_edge_x - offset
                rx = right_edge_x + offset
                pygame.draw.line(self.screen, color, (lx, 0), (lx, wh))
                pygame.draw.line(self.screen, color, (rx, 0), (rx, wh))

            accent_inset = min(edge_width - 1, max(1, edge_width // 2))
            if accent_inset > 0:
                inner_left_x = max(0, left_edge_x - accent_inset)
                inner_right_x = min(self.window_width - 1, right_edge_x + accent_inset)
                pygame.draw.line(self.screen, (24, 30, 42), (inner_left_x, 0), (inner_left_x, wh))
                pygame.draw.line(self.screen, (24, 30, 42), (inner_right_x, 0), (inner_right_x, wh))

    def _get_opening_curtain_cover_width(self) -> int:
        if not getattr(self, '_opening_curtain_active', False):
            return 0

        if getattr(self, '_opening_curtain_deferred', False):
            self._opening_curtain_start_ms = int(pygame.time.get_ticks())
            self._opening_curtain_deferred = False

        duration_ms = max(1, int(getattr(self, '_opening_curtain_duration_ms', self._OPENING_CURTAIN_DURATION_MS) or self._OPENING_CURTAIN_DURATION_MS))
        start_ms = int(getattr(self, '_opening_curtain_start_ms', 0) or 0)
        try:
            now_ms = int(pygame.time.get_ticks())
        except Exception:
            now_ms = start_ms + duration_ms

        elapsed_ms = max(0, now_ms - start_ms)
        progress = min(1.0, elapsed_ms / max(1, duration_ms))
        if progress >= 1.0:
            self._opening_curtain_active = False
            return 0

        eased = self._ease_out_cubic(progress)
        cover_width = int(round((self.window_width / 2) * (1.0 - eased)))
        if cover_width <= 0:
            self._opening_curtain_active = False
            return 0
        return cover_width

    def _get_outer_background_composite(self, skin) -> pygame.Surface | None:
        outer_bg = getattr(self, 'outer_background', None)
        if outer_bg is None or not outer_bg.is_loaded():
            return None

        cache = getattr(self, '_outer_bg_composite_cache', None)
        if not isinstance(cache, dict):
            cache = {'key': None, 'surface': None}
            self._outer_bg_composite_cache = cache

        cache_key = (
            int(self.window_width),
            int(self.window_height),
            tuple(getattr(skin, 'outer_bg', (0, 0, 0))),
            tuple(getattr(skin, 'outer_tint', (0, 0, 0, 0))),
            round(float(getattr(outer_bg, 'transparency', 1.0) or 0.0), 3),
            id(getattr(outer_bg, 'background_image', None)),
        )
        if cache.get('key') == cache_key and cache.get('surface') is not None:
            return cache['surface']

        composed = pygame.Surface((self.window_width, self.window_height))
        # Menü ile tutarlı görünüm için retro_style.bg_color kullan
        _fill_color = getattr(retro_style, 'bg_color', getattr(skin, 'outer_bg', (0, 0, 0)))
        composed.fill(_fill_color)

        bg_surface = outer_bg.get_full_screen_surface(self.screen)
        if bg_surface is not None:
            composed.blit(bg_surface, (0, 0))

        # Outer tint: bg_transparency ile orantılı (menüde tint yok → tutarlılık)
        try:
            _bg_a = float(getattr(outer_bg, 'transparency', 1.0))
        except Exception:
            _bg_a = 1.0
        outer_tint = tuple(getattr(skin, 'outer_tint', (0, 0, 0, 0)))
        if len(outer_tint) >= 4 and int(outer_tint[3]) > 0:
            _tint_a = int(outer_tint[3] * _bg_a) if _bg_a < 1.0 else int(outer_tint[3])
            if _tint_a > 0:
                tint_surface = pygame.Surface((self.window_width, self.window_height), pygame.SRCALPHA)
                tint_surface.fill((*outer_tint[:3], _tint_a))
                composed.blit(tint_surface, (0, 0))

        # Display formatına çevrilebildiğinde cache blit maliyeti düşer;
        # desteklemeyen backend'lerde sessizce ham surface'te kal.
        try:
            if pygame.display.get_surface() is not None:
                composed = composed.convert()
        except Exception:
            pass

        cache['key'] = cache_key
        cache['surface'] = composed
        return composed

    def _prewarm_startup_render_caches(self) -> None:
        try:
            self._calculate_layout()
            if self.outer_background.is_loaded():
                self.outer_background.get_full_screen_surface(self.screen)

            cs = self.cell_size
            bw = self.board.width * cs
            bh = self.board.height * cs
            ox = self.board_offset_x
            oy = self.board_offset_y
            board_rect = pygame.Rect(ox, oy, bw, bh)

            warm_surface = pygame.Surface((self.window_width, self.window_height), pygame.SRCALPHA)
            original_screen = self.screen
            self.screen = warm_surface
            try:
                self._draw_custom_frame(board_rect, "board_frame.png", padding=88, hole_punch=True)
                self._draw_hud(ox, oy, cs, bw, bh)
                self._draw_side_panels(ox, oy, cs, bw, bh)
            finally:
                self.screen = original_screen
        except Exception:
            pass

    def draw(self) -> None:
        self._render_game()
        self._draw_opening_curtain()
        pygame.display.flip()

    # ------------------------------------------------------------------
    # Layout hesaplama
    # ------------------------------------------------------------------

    def _calculate_layout(self) -> None:
        active_size = self._active_ui_size()
        effective_size = self._effective_ui_size()
        key = (
            int(active_size[0]),
            int(active_size[1]),
            int(effective_size[0]),
            int(effective_size[1]),
            int(getattr(self.board, 'width', 20)),
            int(getattr(self.board, 'height', 20)),
        )
        if self._layout_key == key:
            return
        self._layout_key = key
        self.window_width, self.window_height = active_size

        metrics = compute_coop_layout(
            active_size=active_size,
            effective_size=effective_size,
            board_width=getattr(self.board, 'width', 20),
            board_height=getattr(self.board, 'height', 20),
        )
        self._coop_layout_metrics = metrics

        self.cell_size = metrics.cell_size
        self.board_offset_x = metrics.board_x
        self.board_offset_y = metrics.board_y
        self._side_panel_width = metrics.side_panel_width
        self._board_grid_cache['key'] = None

    # ------------------------------------------------------------------
    # Draw yardımcıları
    # ------------------------------------------------------------------

    def _draw_grid(self, ox, oy, cs, bw, bh) -> None:
        skin = self.mode_skin
        gc = getattr(skin, 'grid_color', (50, 50, 80))
        key = (cs, tuple(gc), self.board.width, self.board.height)
        cached = self._board_grid_cache
        if cached.get('key') != key or cached.get('surface') is None:
            surf = pygame.Surface((bw, bh), pygame.SRCALPHA)
            lc = (*gc[:3], 50)
            for x in range(self.board.width + 1):
                pygame.draw.line(surf, lc, (x * cs, 0), (x * cs, bh))
            for y in range(self.board.height + 1):
                pygame.draw.line(surf, lc, (0, y * cs), (bw, y * cs))
            cached['key'] = key
            cached['surface'] = surf
        self.screen.blit(cached['surface'], (ox, oy))

    def _draw_locked_blocks(self, ox, oy, cs) -> None:
        board = self.board
        block_size = cs - 2
        for y in range(board.height):
            flash = (y in self.line_clear_sweep_rows) and self.line_clear_flash
            for x in range(board.width):
                if not board.occupancy[y][x]:
                    continue
                cell_color = WHITE if flash else board.grid[y][x]
                locked_slice = board.texture_grid[y][x]
                texture_surface = None
                texture_slice = None
                if not flash and locked_slice and self.block_style_manager:
                    texture_surface = self.block_style_manager.get_texture_surface(locked_slice.piece_name)
                    texture_slice = locked_slice if texture_surface else None
                fall_offset = self._get_block_fall_offset(y, x)
                block_x = ox + x * cs + 1
                block_y = oy + y * cs + int(round(fall_offset)) + 1
                self.draw_textured_block(block_x, block_y, block_size, cell_color, texture_surface, texture_slice)

    def _draw_midline(self, ox, oy, cs, bh) -> None:
        mx = ox + CoopBoard.MIDLINE * cs
        # Neon cyan çizgi + hafif glow (cached)
        glow_w = 7
        primary = retro_style.primary[:3]
        cache_key = (glow_w, bh, primary)
        cached = self._midline_cache
        if cached.get('key') != cache_key:
            glow_surf = pygame.Surface((glow_w, bh), pygame.SRCALPHA)
            glow_surf.fill((*primary, 18))
            line_surf = pygame.Surface((2, bh), pygame.SRCALPHA)
            line_surf.fill((*primary, 90))
            cached['key'] = cache_key
            cached['glow'] = glow_surf
            cached['line'] = line_surf
        self.screen.blit(cached['glow'], (mx - glow_w // 2, oy))
        self.screen.blit(cached['line'], (mx - 1, oy))

    def _draw_piece(self, piece: Piece | None, ox, oy, cs) -> None:
        if piece is None:
            return
        current_texture = getattr(piece, 'texture_surface', None)
        piece_shape = piece.shape
        piece_width = len(piece_shape[0]) if piece_shape else 1
        piece_height = len(piece_shape) if piece_shape else 1
        block_size = cs - 2
        for local_y, row in enumerate(piece.shape):
            for local_x, cell in enumerate(row):
                if not cell:
                    continue
                x = piece.x + local_x
                y = piece.y + local_y
                if y < 0:
                    continue
                block_x = ox + x * cs + 1
                block_y = oy + y * cs + 1
                draw_color = piece.color
                cm = getattr(piece, 'color_matrix', None)
                if cm is not None:
                    try:
                        v = cm[local_y][local_x]
                        if v is not None:
                            draw_color = v
                    except Exception:
                        pass
                slice_info = self._make_texture_slice(piece, local_x, local_y, piece_width, piece_height)
                self.draw_textured_block(block_x, block_y, block_size, draw_color, current_texture, slice_info)

    def _draw_ghost(self, player: str, ox, oy, cs) -> None:
        piece = self.p1_current_piece if player == 'P1' else self.p2_current_piece
        if piece is None:
            return
        if not self.effects_enabled:
            return
        # Offset-based ghost y calculation (piece.y is NOT mutated)
        ghost_y = piece.y
        offset = 0
        while self.board.is_valid_position_for_player(piece, player, dy=offset + 1):
            offset += 1
        if offset == 0:
            return
        drop_y = ghost_y + offset
        ghost_visual_offset = self._get_ghost_visual_offset(piece, drop_y)
        current_texture = getattr(piece, 'texture_surface', None)
        piece_shape = piece.shape
        piece_width = len(piece_shape[0]) if piece_shape else 1
        piece_height = len(piece_shape) if piece_shape else 1
        block_size = cs - 2
        # Reusable ghost surface for non-textured blocks
        gcache = self._ghost_surf_cache
        if gcache.get('key') != block_size:
            s = pygame.Surface((block_size, block_size))
            s.set_alpha(50)
            gcache['key'] = block_size
            gcache['surface'] = s
        ghost_base_surf = gcache['surface']
        for local_y, row in enumerate(piece.shape):
            for local_x, cell in enumerate(row):
                if not cell:
                    continue
                x = piece.x + local_x
                y = drop_y + local_y
                if y < 0:
                    continue
                block_x = ox + x * cs + 1
                block_y = oy + y * cs + 1 + int(ghost_visual_offset)
                ghost_color = piece.color
                cm = getattr(piece, 'color_matrix', None)
                if cm is not None:
                    try:
                        v = cm[local_y][local_x]
                        if v is not None:
                            ghost_color = v
                    except Exception:
                        pass
                ghost_slice = None
                if current_texture:
                    ghost_slice = self._make_texture_slice(piece, local_x, local_y, piece_width, piece_height)
                if current_texture and ghost_slice:
                    ghost_img = self._render_texture_slice(current_texture, ghost_slice, block_size)
                    if ghost_img:
                        ghost_img.set_alpha(80)
                        self.screen.blit(ghost_img, (block_x, block_y))
                        self._draw_texture_border(block_x, block_y, block_size, ghost_color, textured=True)
                        continue
                # Yarı saydam renkli gölge (reuse cached surface)
                ghost_base_surf.fill(ghost_color)
                self.screen.blit(ghost_base_surf, (block_x, block_y))
                pygame.draw.rect(self.screen, ghost_color,
                                 (block_x, block_y, block_size, block_size), 2)

    def _draw_hud(self, ox, oy, cs, bw, bh) -> None:
        ui = self._ui_scale()
        cx = self.window_width // 2

        # --- Üst bar: cam panel ile başlık + skor ---
        top_h = self._sx(68, ui, minimum=50)
        top_rect = pygame.Rect(ox - 10, 4, bw + 20, top_h)
        retro_style.draw_glass_panel(self.screen, top_rect, alpha=90,
                                      border_color=(60, 70, 90), glow=False,
                                      top_highlight=False)

        # Title (cached — doesn't change during gameplay)
        title_size = self._sx(26, ui, minimum=16)
        hud_cache = getattr(self, '_hud_title_cache', None)
        if hud_cache is None or hud_cache.get('size') != title_size:
            title_font = retro_style.get_font(title_size, bold=True)
            title_surf = title_font.render(t('coop_title', default='QUADRIX CO-OP'), True, retro_style.primary)
            self._hud_title_cache = {'size': title_size, 'surf': title_surf}
        title_surf = self._hud_title_cache['surf']
        self.screen.blit(title_surf, title_surf.get_rect(centerx=cx, top=10))

        score_font = retro_style.get_font(self._sx(20, ui, minimum=14), bold=True)
        score_txt = f"{t('coop_team_score', default='Team Score')}: {self.team_score:,}".replace(',', '.')
        score_surf = score_font.render(score_txt, True, retro_style.text_primary)
        self.screen.blit(score_surf, score_surf.get_rect(centerx=cx, top=10 + title_surf.get_height() + 4))

        # --- Alt bar: seviye, satırlar, süre, katkı ---
        info_y = oy + bh + 6
        bot_h = self._sx(48, ui, minimum=36)
        bot_rect = pygame.Rect(ox - 10, info_y - 4, bw + 20, bot_h)
        retro_style.draw_glass_panel(self.screen, bot_rect, alpha=90,
                                      border_color=(60, 70, 90), glow=False,
                                      top_highlight=False)

        stat_font = retro_style.get_font(self._sx(16, ui, minimum=11))
        level_txt = f"Lv.{self.level}"
        lines_txt = f"{self.total_lines_cleared} {t('coop_lines', default='Lines')}"
        minutes = int(self.elapsed_time) // 60000
        seconds = (int(self.elapsed_time) // 1000) % 60
        time_txt = f"{minutes}:{seconds:02d}"

        items = [level_txt, lines_txt, time_txt]
        gap = self._sx(30, ui, minimum=16)
        total_w = sum(stat_font.size(it)[0] for it in items) + gap * (len(items) - 1)
        start_x = cx - total_w // 2
        for it in items:
            surf = stat_font.render(it, True, retro_style.text_secondary)
            self.screen.blit(surf, (start_x, info_y))
            start_x += surf.get_width() + gap

        contrib_y = info_y + stat_font.get_height() + 2
        contrib_w = max(120, bw // 2 - self._sx(20, ui, minimum=12))
        p1_txt, p2_txt = self._score_contribution_texts()
        contrib_base = self._sx(14, ui, minimum=10)
        p1_font = retro_style.get_fitting_font(p1_txt, contrib_base, contrib_w, bold=False, min_size=9)
        p2_font = retro_style.get_fitting_font(p2_txt, contrib_base, contrib_w, bold=False, min_size=9)
        p1_surf = p1_font.render(p1_txt, True, (90, 235, 170))
        p2_surf = p2_font.render(p2_txt, True, (120, 210, 255))
        self.screen.blit(p1_surf, p1_surf.get_rect(centerx=ox + bw * 0.25, top=contrib_y))
        self.screen.blit(p2_surf, p2_surf.get_rect(centerx=ox + bw * 0.75, top=contrib_y))

    def _draw_side_panels(self, ox, oy, cs, bw, bh) -> None:
        panel_w = self._side_panel_width
        preview_cs = max(12, min(max(12, panel_w // 4), self._sx(22, self._ui_scale(), minimum=12)))
        ui = self._ui_scale()

        no_preview = getattr(self, '_no_preview', False)
        no_hold = getattr(self, '_no_hold', False)
        left_color = getattr(retro_style, 'primary', (0, 255, 221))
        right_color = getattr(retro_style, 'secondary', getattr(retro_style, 'accent', (255, 180, 80)))
        card_h = preview_cs * 4 + self._sx(36, ui, minimum=36)
        top_y = oy + 16
        stack_gap = self._sx(16, ui, minimum=10)

        def draw_preview_card(rect: pygame.Rect, piece: Piece | None, label: str, *, accent_color, disabled: bool = False):
            border_c = (100, 50, 60, 90) if disabled else (*accent_color[:3], 90)
            retro_style.draw_glass_panel(self.screen, rect, alpha=90,
                                          border_color=border_c, top_highlight=False)
            content_x = rect.x + 6
            content_y = rect.y + 12

            if disabled:
                label_surf = self._render_panel_label_surface(
                    label,
                    retro_style.text_muted,
                    rect.width - 16,
                    base_size=self._sx(14, ui, minimum=10),
                    min_size=8,
                    bold=False,
                )
                self.screen.blit(label_surf, label_surf.get_rect(centerx=rect.centerx, top=content_y))
                x_font = retro_style.get_font(self._sx(32, ui, minimum=20), bold=True)
                x_surf = render_text(x_font, 'X', True, (200, 50, 50))
                self.screen.blit(x_surf, x_surf.get_rect(center=rect.center))
                return

            if piece is not None:
                self._draw_piece_preview(piece, content_x, content_y, preview_cs, label, panel_width=rect.width - 12)
                return

            label_surf = self._render_panel_label_surface(
                label,
                retro_style.text_muted,
                rect.width - 16,
                base_size=self._sx(14, ui, minimum=10),
                min_size=8,
                bold=False,
            )
            self.screen.blit(label_surf, label_surf.get_rect(centerx=rect.centerx, top=content_y))
            empty_font = retro_style.get_font(self._sx(16, ui, minimum=11))
            empty_surf = render_text(empty_font, '[ - ]', True, (50, 55, 75))
            self.screen.blit(empty_surf, empty_surf.get_rect(centerx=rect.centerx, centery=rect.centery + self._sx(8, ui, minimum=4)))

        def draw_stack_connector(top_rect: pygame.Rect | None, bottom_rect: pygame.Rect, color):
            if top_rect is None:
                return
            line_x = getattr(top_rect, 'centerx', top_rect.x + top_rect.width // 2)
            top_bottom = getattr(top_rect, 'bottom', top_rect.y + top_rect.height)
            bottom_top = getattr(bottom_rect, 'top', bottom_rect.y)
            line_y1 = top_bottom + 3
            line_y2 = bottom_top - 3
            if line_y2 <= line_y1:
                return
            pygame.draw.line(self.screen, (*color[:3], 95), (line_x, line_y1), (line_x, line_y2), 2)
            pygame.draw.line(self.screen, (*color[:3], 80), (line_x - 4, line_y2 - 6), (line_x, line_y2), 2)
            pygame.draw.line(self.screen, (*color[:3], 80), (line_x + 4, line_y2 - 6), (line_x, line_y2), 2)

        p1_panel_x = ox - panel_w - 8
        p2_panel_x = ox + bw + 8
        p1_next_rect = None
        p2_next_rect = None
        if not no_preview:
            # P1 next (sol panel) — glass panel
            p1_next_rect = pygame.Rect(p1_panel_x - 6, top_y, panel_w + 12, card_h)
            draw_preview_card(p1_next_rect, self.p1_next_piece, self._next_label('P1'), accent_color=left_color)

            # P2 next (sağ panel) — glass panel
            p2_next_rect = pygame.Rect(p2_panel_x - 6, top_y, panel_w + 12, card_h)
            draw_preview_card(p2_next_rect, self.p2_next_piece, self._next_label('P2'), accent_color=right_color)

        hold_top = (p1_next_rect.bottom + stack_gap) if p1_next_rect is not None else top_y
        p1_hold_rect = pygame.Rect(p1_panel_x - 6, hold_top, panel_w + 12, card_h)
        p2_hold_rect = pygame.Rect(p2_panel_x - 6, hold_top, panel_w + 12, card_h)
        draw_preview_card(p1_hold_rect, self.p1_hold_piece, self._hold_label('P1'), accent_color=left_color, disabled=no_hold)
        draw_preview_card(p2_hold_rect, self.p2_hold_piece, self._hold_label('P2'), accent_color=right_color, disabled=no_hold)
        draw_stack_connector(p1_next_rect, p1_hold_rect, left_color)
        draw_stack_connector(p2_next_rect, p2_hold_rect, right_color)

    def _draw_piece_preview(self, piece: Piece | None, x, y, cs, label: str, panel_width: int | None = None) -> None:
        ui = self._ui_scale()
        max_width = None if panel_width is None else max(40, panel_width - 6)
        label_limit = max_width if max_width is not None else 4096
        label_surf = self._render_panel_label_surface(
            label,
            retro_style.text_secondary,
            label_limit,
            base_size=self._sx(14, ui, minimum=10),
            min_size=8,
            bold=False,
        )
        label_x = x if panel_width is None else x + max(0, (panel_width - label_surf.get_width()) // 2)
        self.screen.blit(label_surf, (label_x, y))
        if piece is None:
            return
        py = y + label_surf.get_height() + 4
        block_size = cs - 2
        current_texture = getattr(piece, 'texture_surface', None)
        piece_width = len(piece.shape[0]) if piece.shape else 1
        piece_height = len(piece.shape) if piece.shape else 1
        active_cells = [(col_i, row_i) for row_i, row in enumerate(piece.shape) for col_i, cell in enumerate(row) if cell]
        min_col = min((col_i for col_i, _ in active_cells), default=0)
        max_col = max((col_i for col_i, _ in active_cells), default=piece_width - 1)
        preview_offset_x = 0
        if panel_width is not None:
            preview_width = max(1, (max_col - min_col + 1) * cs)
            preview_offset_x = max(0, (panel_width - preview_width) // 2) - min_col * cs
        for row_i, row in enumerate(piece.shape):
            for col_i, cell in enumerate(row):
                if cell:
                    bx = x + preview_offset_x + col_i * cs + 1
                    by = py + row_i * cs + 1
                    draw_color = piece.color
                    cm = getattr(piece, 'color_matrix', None)
                    if cm is not None:
                        try:
                            v = cm[row_i][col_i]
                            if v is not None:
                                draw_color = v
                        except Exception:
                            pass
                    slice_info = self._make_texture_slice(piece, col_i, row_i, piece_width, piece_height)
                    self.draw_textured_block(bx, by, block_size, draw_color, current_texture, slice_info)

    def _draw_freeze_overlay(self, player: str, ox, oy, cs, bh) -> None:
        if player == 'P1':
            area = pygame.Rect(ox, oy, CoopBoard.MIDLINE * cs, bh)
        else:
            area = pygame.Rect(ox + CoopBoard.MIDLINE * cs, oy, CoopBoard.MIDLINE * cs, bh)

        # Gradient koyu overlay (cached)
        cache_key = (area.width, area.height)
        fcache = self._freeze_overlay_cache[player]
        if fcache.get('key') != cache_key:
            overlay = pygame.Surface(area.size, pygame.SRCALPHA)
            for row in range(area.height):
                alpha = int(80 + 80 * (row / max(1, area.height)))
                pygame.draw.line(overlay, (5, 8, 20, alpha), (0, row), (area.width, row))
            # Buz çerçevesi — neon cyan kenarlık
            pygame.draw.rect(overlay, (*retro_style.primary[:3], 45), overlay.get_rect(), 3)
            fcache['key'] = cache_key
            fcache['surface'] = overlay
        self.screen.blit(fcache['surface'], area.topleft)

        # Mesaj kutusu
        ui = self._ui_scale()
        msg = t('coop_frozen_waiting', default='Waiting...')
        msg_font = retro_style.get_font(self._sx(18, ui, minimum=12), bold=True)
        msg_surf = render_text(msg_font, msg, True, retro_style.accent)
        box_w = msg_surf.get_width() + self._sx(28, ui)
        box_h = msg_surf.get_height() + self._sx(14, ui)
        box_rect = pygame.Rect(0, 0, box_w, box_h)
        box_rect.center = area.center
        retro_style.draw_glass_panel(self.screen, box_rect, alpha=160,
                                      border_color=(*retro_style.accent[:3], 120), glow=True)
        self.screen.blit(msg_surf, msg_surf.get_rect(center=box_rect.center))

    def _draw_pause_menu(self) -> None:
        w, h = self.window_width, self.window_height
        ui = self._ui_scale()

        overlay = pygame.Surface((w, h), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 185))
        self.screen.blit(overlay, (0, 0))

        # Lokalize seçenek etiketleri (Game base ile aynı yapı)
        option_labels = {
            'resume': t('resume', default='Resume'),
            'settings': t('settings', default='Settings'),
            'music': t('music', default='Music'),
            'music_volume': t('music_volume', default='Music Volume'),
            'sound_effects': t('sound_effects', default='Sound Effects'),
            'sfx_volume': t('sfx_volume', default='SFX Volume'),
            'main_menu': t('main_menu', default='Main Menu'),
        }

        pw = min(self._sx(520, ui), w - self._sx(100, ui))
        count = len(self.pause_menu_options)
        item_h = self._sx(56, ui)
        gap = self._sx(10, ui)
        top_pad = self._sx(78, ui)
        bot_pad = self._sx(64, ui)
        ph = top_pad + count * item_h + (count - 1) * gap + bot_pad
        pr = pygame.Rect((w - pw) // 2, (h - ph) // 2, pw, ph)

        retro_style.draw_glass_panel(self.screen, pr, alpha=180,
                                      border_color=(*retro_style.accent, 140), glow=True)

        tf = retro_style.get_font(self._sx(30, ui, minimum=16), bold=True)
        ts = tf.render(t('paused', default='PAUSED'), True, retro_style.accent)
        self.screen.blit(ts, ts.get_rect(centerx=pr.centerx, top=pr.y + self._sx(18, ui)))

        self._pause_option_rects = []
        self._pause_volume_rects = {}
        _pause_mouse_pos = get_mouse_pos()

        start_y = pr.y + top_pad
        for i, opt in enumerate(self.pause_menu_options):
            y = start_y + i * (item_h + gap)
            btn_rect = pygame.Rect(pr.x + self._sx(22, ui), y, pr.width - self._sx(44, ui), item_h)
            self._pause_option_rects.append(btn_rect)

            selected = i == self.pause_menu_selected
            label = option_labels.get(opt, opt)
            sub_text = None
            color_code = retro_style.primary

            if opt == 'resume':
                color_code = retro_style.success if hasattr(retro_style, 'success') else (60, 200, 120)
            elif opt == 'main_menu':
                color_code = retro_style.secondary
            elif opt == 'music':
                color_code = retro_style.primary
                sub_text = t('on', default='ON') if self.sound.music_enabled else t('off', default='OFF')
            elif opt == 'sound_effects':
                color_code = retro_style.primary
                sub_text = t('on', default='ON') if self.sound.sfx_enabled else t('off', default='OFF')
            elif opt == 'music_volume':
                color_code = retro_style.accent
                sub_text = f"{int(self.sound.music_volume * 100)}%  < >"
            elif opt == 'sfx_volume':
                color_code = retro_style.accent
                sub_text = f"{int(self.sound.sfx_volume * 100)}%  < >"

            _pm_hover = btn_rect.collidepoint(_pause_mouse_pos)
            retro_style.draw_uniform_button(
                self.screen, btn_rect, label,
                sub_text=sub_text,
                color_code=color_code,
                selected=selected,
                state='hover' if _pm_hover else 'normal',
            )

            # Volume bars
            if opt == 'music_volume':
                bar_rect = pygame.Rect(
                    btn_rect.right - self._sx(150, ui),
                    btn_rect.y + self._sx(18, ui),
                    self._sx(90, ui),
                    self._sx(18, ui),
                )
                self._pause_volume_rects[opt] = bar_rect
                retro_style.draw_volume_bar(self.screen, bar_rect.x, bar_rect.y, bar_rect.width, bar_rect.height,
                                             self.sound.music_volume, (0, 210, 255), int(self.sound.music_volume * 100), selected, ui)
            elif opt == 'sfx_volume':
                bar_rect = pygame.Rect(
                    btn_rect.right - self._sx(150, ui),
                    btn_rect.y + self._sx(18, ui),
                    self._sx(90, ui),
                    self._sx(18, ui),
                )
                self._pause_volume_rects[opt] = bar_rect
                retro_style.draw_volume_bar(self.screen, bar_rect.x, bar_rect.y, bar_rect.width, bar_rect.height,
                                             self.sound.sfx_volume, (255, 185, 0), int(self.sound.sfx_volume * 100), selected, ui)

    def _draw_game_over_screen(self) -> None:
        w, h = self.window_width, self.window_height
        ui = self._ui_scale(0.70, 1.16)
        s = lambda value, minimum=1: self._sx(value, ui, minimum)
        snapshot = self._ensure_game_over_snapshot()
        try:
            now_ms = int(pygame.time.get_ticks())
        except Exception:
            now_ms = int(getattr(self, '_game_over_start_time', 0) or 0)
        start_ms = int(getattr(self, '_game_over_start_time', 0) or now_ms)
        elapsed_sec = max(0.0, (now_ms - start_ms) / 1000.0)
        fade_progress = min(1.0, elapsed_sec / 0.35)
        score_progress = min(1.0, max(0.0, (elapsed_sec - 0.12) / 1.15))
        displayed_score = int(int(snapshot.get('team_score', 0) or 0) * (1 - (1 - score_progress) ** 3))
        self._game_over_restart_rect = None
        self._game_over_exit_rect = None
        self._game_over_peek_rect = None

        if getattr(self, '_game_over_peek_active', False):
            peek_btn_size = s(48)
            peek_rect = pygame.Rect(w - peek_btn_size - s(20), h - peek_btn_size - s(20), peek_btn_size, peek_btn_size)
            self._game_over_peek_rect = peek_rect
            self._draw_game_over_peek_button(
                peek_rect,
                hovered=False,
                fallback_label='X',
                border_color=(100, 200, 255),
            )
            return

        overlay = pygame.Surface((w, h), pygame.SRCALPHA)
        for row in range(h):
            ratio = row / max(1, h - 1)
            alpha = int((155 + 70 * ratio) * fade_progress)
            red = int(18 + 18 * (1.0 - ratio))
            green = int(7 + 10 * ratio)
            blue = int(14 + 24 * ratio)
            overlay.fill((red, green, blue, min(240, alpha)), (0, row, w, 1))
        self.screen.blit(overlay, (0, 0))

        panel_w = min(max(s(780), w - s(340)), w - s(72))
        panel_h = min(max(s(560), h - s(120)), h - s(52))
        panel_rect = pygame.Rect((w - panel_w) // 2, (h - panel_h) // 2, panel_w, panel_h)
        glow_rect = panel_rect.inflate(s(26), s(26))
        glow_surf = pygame.Surface(glow_rect.size, pygame.SRCALPHA)
        pygame.draw.rect(glow_surf, (165, 32, 58, 34), glow_surf.get_rect(), border_radius=22)
        self.screen.blit(glow_surf, glow_rect.topleft)

        retro_style.draw_glass_panel(
            self.screen,
            panel_rect,
            alpha=216,
            border_color=(230, 92, 122),
            glow=False,
            top_highlight=False,
        )
        panel_tint = pygame.Surface(panel_rect.size, pygame.SRCALPHA)
        panel_tint.fill((28, 8, 16, 208))
        highlight_h = min(panel_rect.height // 3, s(44))
        for row in range(highlight_h):
            hi_alpha = int(24 * (1 - row / max(1, highlight_h)))
            pygame.draw.line(panel_tint, (255, 255, 255, hi_alpha), (0, row), (panel_rect.width, row))
        self.screen.blit(panel_tint, panel_rect.topleft)
        pygame.draw.rect(self.screen, (240, 92, 122), panel_rect, 2, border_radius=18)

        mouse_pos = get_mouse_pos()
        peek_btn_size = s(36)
        peek_rect = pygame.Rect(panel_rect.right - peek_btn_size - s(16), panel_rect.y + s(16), peek_btn_size, peek_btn_size)
        self._game_over_peek_rect = peek_rect
        peek_hovered = mouse_pos is not None and peek_rect.collidepoint(mouse_pos)
        self._draw_game_over_peek_button(peek_rect, hovered=peek_hovered, fallback_label='O')

        inner_left = panel_rect.x + s(28)
        inner_right = panel_rect.right - s(28)
        inner_width = inner_right - inner_left

        title_color = (255, 78, 112)
        subtitle_color = (196, 212, 236)
        status_color = (255, 188, 88)
        p1_color = (88, 226, 182)
        p2_color = (114, 210, 255)

        def draw_metric_card(rect: pygame.Rect, label: str, value: str, accent: tuple[int, int, int], note: str | None = None):
            card_bg = (
                min(52, 10 + accent[0] // 10),
                min(58, 12 + accent[1] // 10),
                min(72, 20 + accent[2] // 10),
            )
            card_border = (
                min(230, 42 + accent[0] // 2),
                min(230, 48 + accent[1] // 2),
                min(240, 54 + accent[2] // 2),
            )
            card_fill = pygame.Surface(rect.size, pygame.SRCALPHA)
            card_fill.fill((*card_bg, 220))
            self.screen.blit(card_fill, rect.topleft)
            pygame.draw.rect(self.screen, card_border, rect, 1, border_radius=12)
            pygame.draw.rect(self.screen, accent, (rect.x + s(8), rect.y + s(8), s(5), rect.height - s(16)), border_radius=2)

            label_font = retro_style.get_fitting_font(label, s(15), rect.width - s(34), bold=True, min_size=9)
            label_surf = label_font.render(label, True, (205, 220, 240))
            self.screen.blit(label_surf, (rect.x + s(20), rect.y + s(10)))

            value_font = retro_style.get_fitting_font(value, s(28), rect.width - s(34), bold=True, min_size=12)
            value_surf = value_font.render(value, True, accent)
            value_y = rect.y + s(10) + label_font.get_height() + s(4)
            self.screen.blit(value_surf, (rect.x + s(20), value_y))

            if note:
                note_font = retro_style.get_fitting_font(note, s(13), rect.width - s(34), bold=False, min_size=9)
                note_surf = note_font.render(note, True, (175, 194, 220))
                note_y = rect.bottom - s(10) - note_font.get_height()
                self.screen.blit(note_surf, (rect.x + s(20), note_y))

        tag_text = t('coop_title', default='QUADRIX CO-OP')
        tag_font = retro_style.get_font(s(14), bold=True)
        tag_w = min(inner_width, tag_font.size(tag_text)[0] + s(24))
        tag_rect = pygame.Rect(inner_left, panel_rect.y + s(22), tag_w, s(28))
        pygame.draw.rect(self.screen, (34, 56, 84), tag_rect, border_radius=tag_rect.height // 2)
        pygame.draw.rect(self.screen, (96, 188, 255), tag_rect, 1, border_radius=tag_rect.height // 2)
        tag_surf = render_text(tag_font, tag_text, True, (170, 220, 255))
        tag_x = tag_rect.x + (tag_rect.width - tag_font.size(tag_text)[0]) // 2
        tag_y = tag_rect.y + (tag_rect.height - tag_font.get_height()) // 2
        self.screen.blit(tag_surf, (tag_x, tag_y))

        title_text = t('coop_game_over', default='GAME OVER')
        title_font = retro_style.get_font(s(46), bold=True)
        title_w, title_h = title_font.size(title_text)
        title_x = panel_rect.centerx - title_w // 2
        title_y = tag_rect.bottom + s(14)
        for dx, dy, alpha in [(-2, 0, 32), (2, 0, 32), (0, -2, 28), (0, 2, 28), (-2, -2, 18), (2, 2, 18)]:
            glow = title_font.render(title_text, True, title_color)
            glow.set_alpha(alpha)
            self.screen.blit(glow, (title_x + dx, title_y + dy))
        title_surf = render_text(title_font, title_text, True, title_color)
        self.screen.blit(title_surf, (title_x, title_y))

        subtitle_text = t(
            'coop_game_over_subtitle',
            default='Takım koşusu kapandı. Son durum özeti aşağıda.',
        )
        subtitle_font = retro_style.get_font(s(18), bold=False)
        subtitle_w, subtitle_h = subtitle_font.size(subtitle_text)
        subtitle_x = panel_rect.centerx - subtitle_w // 2
        subtitle_y = title_y + title_h + s(8)
        subtitle_surf = render_text(subtitle_font, subtitle_text, True, subtitle_color)
        self.screen.blit(subtitle_surf, (subtitle_x, subtitle_y))

        score_rect = pygame.Rect(inner_left, subtitle_y + subtitle_h + s(18), inner_width, s(86))
        score_fill = pygame.Surface(score_rect.size, pygame.SRCALPHA)
        score_fill.fill((42, 12, 24, 228))
        self.screen.blit(score_fill, score_rect.topleft)
        pygame.draw.rect(self.screen, (112, 180, 255), score_rect, 2, border_radius=14)

        score_label_font = retro_style.get_font(s(16), bold=True)
        score_label_text = t('coop_team_score', default='Team Score')
        score_label_surf = render_text(score_label_font, score_label_text, True, (204, 220, 244))
        self.screen.blit(score_label_surf, (score_rect.x + s(18), score_rect.y + s(14)))

        score_value_text = self._fmt_score(displayed_score)
        score_value_font = retro_style.get_font(s(38), bold=True)
        score_value_w, score_value_h = score_value_font.size(score_value_text)
        score_value_x = score_rect.right - s(18) - score_value_w
        score_value_y = score_rect.y + s(10)
        score_shadow = score_value_font.render(score_value_text, True, (0, 0, 0))
        score_shadow.set_alpha(110)
        self.screen.blit(score_shadow, (score_value_x + 2, score_value_y + 2))
        score_value_surf = score_value_font.render(score_value_text, True, WHITE)
        self.screen.blit(score_value_surf, (score_value_x, score_value_y))

        status_text = self._game_over_status_text(snapshot)
        status_font = retro_style.get_fitting_font(status_text, s(15), score_rect.width - s(36), bold=True, min_size=10)
        status_w, status_h = status_font.size(status_text)
        status_x = score_rect.x + (score_rect.width - status_w) // 2
        status_y = score_rect.bottom - s(14) - status_h
        status_surf = status_font.render(status_text, True, status_color)
        self.screen.blit(status_surf, (status_x, status_y))

        reason_text = self._game_over_reason_text(snapshot)
        reason_title_font = retro_style.get_font(s(18), bold=True)
        reason_body_font = retro_style.get_font(s(16), bold=False)
        reason_lines = self._wrap_overlay_text(reason_body_font, reason_text, inner_width - s(40))
        reason_body_h = len(reason_lines) * reason_body_font.get_linesize()
        reason_gap = s(4)
        reason_rect_h = max(s(94), s(22) + reason_title_font.get_height() + reason_gap + reason_body_h + s(20))
        reason_rect = pygame.Rect(inner_left, score_rect.bottom + s(14), inner_width, reason_rect_h)
        reason_fill = pygame.Surface(reason_rect.size, pygame.SRCALPHA)
        reason_fill.fill((32, 14, 22, 205))
        self.screen.blit(reason_fill, reason_rect.topleft)
        pygame.draw.rect(self.screen, (192, 86, 118), reason_rect, 1, border_radius=14)

        reason_title = status_text
        reason_title_surf = reason_title_font.render(reason_title, True, title_color)
        reason_title_y = reason_rect.y + s(14)
        self.screen.blit(reason_title_surf, (reason_rect.x + s(18), reason_title_y))
        body_y = reason_title_y + reason_title_font.get_height() + reason_gap
        for line in reason_lines:
            line_surf = reason_body_font.render(line, True, subtitle_color)
            self.screen.blit(line_surf, (reason_rect.x + s(18), body_y))
            body_y += reason_body_font.get_linesize()

        stat_gap = s(14)
        stat_w = (inner_width - 2 * stat_gap) // 3
        stat_h = s(78)
        stat_top = reason_rect.bottom + s(14)
        draw_metric_card(
            pygame.Rect(inner_left, stat_top, stat_w, stat_h),
            t('coop_total_lines', default='Total Lines'),
            str(int(snapshot.get('total_lines', 0) or 0)),
            (78, 224, 255),
        )
        draw_metric_card(
            pygame.Rect(inner_left + stat_w + stat_gap, stat_top, stat_w, stat_h),
            t('coop_level', default='Level'),
            str(int(snapshot.get('level', 1) or 1)),
            (255, 186, 82),
        )
        draw_metric_card(
            pygame.Rect(inner_left + (stat_w + stat_gap) * 2, stat_top, stat_w, stat_h),
            t('coop_total_time', default='Total Time'),
            self._format_elapsed_time(int(snapshot.get('elapsed_ms', 0) or 0)),
            (114, 245, 176),
        )

        contrib_top = stat_top + stat_h + s(14)
        contrib_w = (inner_width - stat_gap) // 2
        contrib_h = s(92)
        draw_metric_card(
            pygame.Rect(inner_left, contrib_top, contrib_w, contrib_h),
            'P1',
            f"%{int(snapshot.get('p1_pct', 0) or 0)}",
            p1_color,
            str(snapshot.get('p1_text', '')),
        )
        draw_metric_card(
            pygame.Rect(inner_left + contrib_w + stat_gap, contrib_top, contrib_w, contrib_h),
            'P2',
            f"%{int(snapshot.get('p2_pct', 0) or 0)}",
            p2_color,
            str(snapshot.get('p2_text', '')),
        )

        footer_surfaces = []
        current_user = None
        if getattr(self, 'user_manager', None):
            get_current_user = getattr(self.user_manager, 'get_current_user', None)
            if callable(get_current_user):
                try:
                    current_user = get_current_user()
                except Exception:
                    current_user = None
        footer_font = retro_style.get_font(s(14), bold=False)
        if current_user:
            profile_text = t('saved_profile', default='Saved profile: {}').format(current_user)
            footer_surfaces.append((footer_font.render(profile_text, True, (178, 198, 224)), footer_font.size(profile_text)[0]))
        hint_text = t('coop_game_over_hint', default='R ile yeniden başlat, ESC ile menüye dön.')
        footer_surfaces.append((render_text(footer_font, hint_text, True, (164, 182, 208)), footer_font.size(hint_text)[0]))

        button_gap = s(16)
        button_w = min((inner_width - button_gap) // 2, s(248))
        button_h = s(48)
        restart_rect = pygame.Rect(panel_rect.centerx - button_gap // 2 - button_w, panel_rect.bottom - s(72), button_w, button_h)
        button_rect = pygame.Rect(panel_rect.centerx + button_gap // 2, panel_rect.bottom - s(72), button_w, button_h)
        footer_y = restart_rect.y - s(12)
        line_h = footer_font.get_linesize()
        total_footer_h = len(footer_surfaces) * line_h
        current_y = footer_y - total_footer_h
        for surf, width in footer_surfaces:
            surf_x = panel_rect.centerx - width // 2
            self.screen.blit(surf, (surf_x, current_y))
            current_y += line_h

        restart_sub = render_action_prompt_surface(
            'restart',
            'R',
            retro_style.get_font(self._sx(16, ui, minimum=10), bold=False),
            (160, 175, 200),
            max_width=self._sx(40, ui, minimum=24),
            max_height=self._sx(18, ui, minimum=12),
        )
        retro_style.draw_uniform_button(
            self.screen,
            restart_rect,
            t('campaign_retry', default='Yeniden Başlat'),
            sub_text=(restart_sub or 'R'),
            color_code=(72, 216, 158),
            state='hover' if restart_rect.collidepoint(mouse_pos) else 'normal',
        )
        menu_sub = render_action_prompt_surface(
            'menu_back',
            'ESC',
            retro_style.get_font(self._sx(16, ui, minimum=10), bold=False),
            (160, 175, 200),
            max_width=self._sx(46, ui, minimum=24),
            max_height=self._sx(18, ui, minimum=12),
        )
        retro_style.draw_uniform_button(
            self.screen,
            button_rect,
            t('back_to_menu', default='Back to Menu'),
            sub_text=(menu_sub or 'ESC'),
            color_code=(220, 86, 112),
            state='hover' if button_rect.collidepoint(mouse_pos) else 'normal',
        )
        self._game_over_restart_rect = restart_rect
        self._game_over_exit_rect = button_rect
