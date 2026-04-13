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
from pieces import Piece, SHAPES
from constants import (
    BOARD_WIDTH, BOARD_HEIGHT, BLACK, WHITE, CYAN, YELLOW, MAGENTA, GREEN, RED,
    DAS_DELAY, DAS_REPEAT,
)
from sound import SoundManager
from background import BackgroundManager
from background_effects import get_shared_falling_blocks_layer
from mode_skins import apply_board_tint, apply_outer_tint, draw_board_overlay, get_mode_skin
from retro_style import retro_style
from renderers.jelly_renderer import draw_jelly_block, draw_jelly_border
from themes import ThemeManager
from block_styles import BlockStyleManager, TextureSlice, TextureRenderCache
from platform_utils import (
    create_display, normalize_mouse_pos, get_mouse_pos, set_app_icon,
)
from localization import t
from ui_theme import UIColors, UIFonts
from sweep_effects import SweepCatState, draw_rainbow_cat_sweep
from asset_manager import load_image


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
    _SOFT_DROP_SPEED = 50  # ms
    _LINE_CLEAR_SWEEP_BLOCK_FALL_SPEED = 0.144

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

    def _ui_scale(self, mn: float = 0.72, mx: float = 1.20) -> float:
        try:
            s = min(float(self.window_width) / 1366.0, float(self.window_height) / 768.0)
        except Exception:
            s = 1.0
        return max(mn, min(mx, s))

    def _sx(self, value, scale=None, minimum=1) -> int:
        if scale is None:
            scale = self._ui_scale()
        return max(minimum, int(round(float(value) * float(scale))))

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
    ):
        if not pygame.get_init():
            pygame.init()

        self.user_manager = user_manager
        self.settings_manager = settings_manager

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
        self.effects_enabled = effects_enabled
        self._start_music()

        # --- Arka plan ---
        self.background = BackgroundManager()
        self.board_background = BackgroundManager()
        self.background.set_transparency(1.0)
        if self.settings_manager:
            self.board_background.set_transparency(self.settings_manager.get('bg_transparency', 1.0))
        else:
            self.board_background.set_transparency(1.0)
        self._load_backgrounds()

        # --- Tema / blok stili ---
        self.theme_manager = ThemeManager(self.settings_manager)
        self.mode_skin = get_mode_skin('classic')
        self.block_style_manager = BlockStyleManager(self.settings_manager) if self.settings_manager else None
        self._texture_render_cache = TextureRenderCache()

        # --- Kontroller ---
        self.pvp_controls = self._resolve_controls()

        # ==================================================================
        # Board + parça sistemi
        # ==================================================================
        self.board = CoopBoard()

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
        self.paused = False
        self.pause_menu_selected = 0
        self._pause_menu_keys = ['resume', 'settings', 'music', 'music_volume', 'sound_effects', 'sfx_volume', 'main_menu']
        self._pause_option_rects: list[pygame.Rect] = []
        self._pause_volume_rects: dict[str, pygame.Rect] = {}
        self._pause_vol_drag_active = False
        self._pause_vol_drag_option = ''
        self._pause_settings_active = False
        self._pause_settings_screen = None

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

        # --- Visual Effects (Game base ile uyumlu) ---
        self.particles: list = []
        self.ambient_particles: list = []
        self.screen_shake = 0
        self.shake_intensity = 3
        self._screen_shake_initial = 0.0
        self.drop_trails: list = []
        self.line_clear_flash = False
        self._flash_timer = 0.0
        self.line_clear_sweep_active = False
        self.line_clear_sweep_progress = 0.0
        self.line_clear_sweep_rows: list[int] = []
        self.line_clear_pending_rows: list[int] = []
        self.line_clear_pending_colors: dict = {}
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
                self.falling_blocks = get_shared_falling_blocks_layer()
            except Exception:
                self.falling_blocks = None

        # Outer background (tam ekran arka plan)
        self.outer_background = BackgroundManager()
        self._load_outer_background()

        # Ambient particles init
        self._init_ambient_particles()

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
            'pause': pygame.K_p,
        }
        if not self.settings_manager:
            return defaults
        controls = self.settings_manager.get_controls()
        pvp_cfg = controls.get('pvp', {}) if isinstance(controls, dict) else {}
        resolved: dict = {'player1': {}, 'player2': {}}
        for player in ('player1', 'player2'):
            pcfg = pvp_cfg.get(player, {}) if isinstance(pvp_cfg, dict) else {}
            for action in defaults[player]:
                binding = pcfg.get(action)
                resolved[player][action] = self._binding_to_keycode(binding, defaults[player][action])
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
            background_enabled = bool(settings_manager.get('background_enabled', True))
        except Exception:
            background_enabled = True
        try:
            bg_transparency = float(settings_manager.get('bg_transparency', 1.0))
        except Exception:
            bg_transparency = None

        for attr_name in ('background', 'board_background', 'outer_background'):
            background = getattr(self, attr_name, None)
            if background is None:
                continue
            if hasattr(background, 'enabled'):
                try:
                    background.enabled = background_enabled
                except Exception:
                    pass
        if bg_transparency is not None:
            for attr_name in ('background', 'board_background'):
                background = getattr(self, attr_name, None)
                if background is not None and hasattr(background, 'set_transparency'):
                    try:
                        background.set_transparency(bg_transparency)
                    except Exception:
                        pass

        self.falling_blocks = get_shared_falling_blocks_layer('default') if getattr(self, 'effects_enabled', True) else None
        self._layout_key = None

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

        if event.type == pygame.JOYBUTTONDOWN:
            try:
                gp_cfg = self.settings_manager.get_controls().get('gamepad', {})
                if event.button == _gp_btn(gp_cfg.get('menu_back', 1)):
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

    # ==================================================================
    # Parça üretimi (bağımsız bag'ler)
    # ==================================================================

    def _refill_bag(self, player: str) -> None:
        bag: list[int] = list(range(len(SHAPES))) * 2  # 7 tip × 2 kopya
        random.shuffle(bag)
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
        sx, sy = self.board.get_spawn_position(player)
        piece = Piece(x=sx, y=sy, shape_index=idx)
        self._apply_block_style(piece)
        return piece

    def _place_at_spawn(self, piece: Piece, player: str) -> None:
        sx, sy = self.board.get_spawn_position(player)
        piece.x = sx
        piece.y = sy

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
        self._play_game_over_sequence()

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
        if not self.effects_enabled:
            return
        count = 20
        for _ in range(count):
            p = {
                'x': float(random.randint(0, max(1, self.window_width))),
                'y': float(random.randint(0, max(1, self.window_height))),
                'vx': random.uniform(-0.15, 0.15),
                'vy': random.uniform(0.2, 0.6),
                'alpha': random.randint(40, 120),
                'size': random.randint(2, 5),
                'pulse': random.uniform(0, 6.28),
                'pulse_speed': random.uniform(0.03, 0.08),
                'color': random.choice([(80, 200, 255), (160, 80, 255), (80, 255, 160), (255, 200, 80)]),
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
        try:
            return bool(sm.get('particle_effects', False))
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Textured block rendering (Game base ile uyumlu)
    # ------------------------------------------------------------------

    def draw_textured_block(self, x, y, size, color, texture_surface=None, texture_slice: TextureSlice | None = None):
        if color is None:
            color = (128, 128, 128)
        if texture_surface is not None and texture_slice is not None:
            self._draw_texture_cell(x, y, size, color, texture_surface, texture_slice)
            draw_jelly_border(self.screen, x, y, size, color)
            return
        draw_jelly_block(self.screen, x, y, size, color)

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
            found_path = None
            for folder in ["assets/game_ui", "assets/ui"]:
                p = _resource_path(f"{folder}/{asset_name}")
                if os.path.exists(p):
                    found_path = p
                    break
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
        if self.screen_shake > 0:
            shake_x = random.randint(-self.shake_intensity, self.shake_intensity)
            shake_y = random.randint(-self.shake_intensity, self.shake_intensity)
            initial = float(self._screen_shake_initial) if self._screen_shake_initial else 15.0
            decay = max(0.0, min(1.0, float(self.screen_shake) / max(1.0, initial)))
            return (int(shake_x * decay), int(shake_y * decay))
        return (0, 0)

    def trigger_screen_shake(self, duration: int = 8, intensity: int = 3):
        if not self._particle_effects_enabled():
            return
        self.screen_shake = duration
        self.shake_intensity = intensity
        self._screen_shake_initial = float(duration)

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
        for i in range(random.randint(6, 10)):
            angle = (i / 8) * 2 * math.pi + random.uniform(-0.3, 0.3)
            speed = random.uniform(2, 5)
            self.particles.append({
                'x': float(x), 'y': float(y),
                'vx': math.cos(angle) * speed,
                'vy': math.sin(angle) * speed - 1.5,
                'life': random.randint(20, 45),
                'max_life': 45,
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
        for _ in range(max(1, int(count * self.animation_multiplier))):
            self.particles.append({
                'x': float(x), 'y': float(y),
                'vx': random.uniform(-1, 1) * speed,
                'vy': random.uniform(-1, 1) * speed,
                'life': random.randint(30, 60),
                'max_life': 60,
                'color': random.choice(colors),
                'size': random.randint(2, 5),
            })

    def update_particles(self, dt_ms: float = 16.666):
        dt = max(0.0, min(100.0, float(dt_ms)))
        dt_frames = dt / 16.666
        alive = []
        for p in self.particles:
            p['x'] += p['vx'] * dt_frames
            p['y'] += p['vy'] * dt_frames
            p['vy'] += 0.15 * dt_frames  # gravity
            p['life'] -= 1
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
        for p in self.ambient_particles:
            p['x'] += p['vx'] * dt_frames
            p['y'] += p['vy'] * dt_frames
            p['pulse'] += p['pulse_speed'] * dt_frames
            if p['y'] > self.window_height:
                p['y'] = -10
                p['x'] = random.uniform(0, self.window_width)
            if p['x'] < -10:
                p['x'] = self.window_width + 10
            elif p['x'] > self.window_width + 10:
                p['x'] = -10

    def draw_ambient_particles(self):
        if not self._effect_surface_cache:
            return
        for p in self.ambient_particles:
            pulse_alpha = int(p['alpha'] + math.sin(p['pulse']) * 30)
            pulse_alpha = max(30, min(180, pulse_alpha))
            glow_size = p['size'] * 3
            glow_surf = self._effect_surface_cache.get_ellipse_surface(
                (glow_size, glow_size), (*p['color'][:3], pulse_alpha // 3))
            self.screen.blit(glow_surf, (int(p['x']) - glow_size // 2, int(p['y']) - glow_size // 2))
            core_surf = self._effect_surface_cache.get_filled_surface(
                (p['size'], p['size']), (*p['color'][:3], pulse_alpha))
            self.screen.blit(core_surf, (int(p['x']) - p['size'] // 2, int(p['y']) - p['size'] // 2))

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
                t_obj['_surf'].set_alpha(int(t_obj['alpha']))
                alive.append(t_obj)
        self.drop_trails = alive

    def _draw_drop_trails(self):
        for trail in self.drop_trails:
            if trail['alpha'] > 0:
                self.screen.blit(trail['_surf'], (int(trail['x']), int(trail['y'])))

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
        # Flash
        self.line_clear_flash = True
        self._flash_timer = 80.0  # ms

    def _update_line_clear_effects(self, dt_ms: float):
        if self.line_clear_flash:
            self._flash_timer -= dt_ms
            if self._flash_timer <= 0:
                self.line_clear_flash = False
        if self.line_clear_sweep_active:
            cell_size = max(1, int(self.cell_size))
            board_pixel_width = self.board.width * cell_size
            cleared_count = max(1, len(self.line_clear_sweep_rows))
            sweep_width = self._get_line_sweep_length_px(cell_size, cleared_count)
            sweep_travel_px = max(1.0, float(board_pixel_width + sweep_width))
            dt_frames = max(0.0, min(100.0, float(dt_ms))) * 60.0 / 1000.0
            block_px_per_frame = self._LINE_CLEAR_SWEEP_BLOCK_FALL_SPEED * 60.0
            sweep_speed = block_px_per_frame / sweep_travel_px
            self.line_clear_sweep_progress += dt_frames * sweep_speed
            if self.line_clear_sweep_progress >= 1.0:
                self.line_clear_sweep_progress = 1.0
                self.line_clear_sweep_active = False
                self.line_clear_sweep_rows = []
                self.line_clear_pending_rows = []
                self.line_clear_pending_colors = {}

    def _get_line_sweep_length_px(self, cell_size: int, cleared_count: int) -> int:
        return max(cell_size * 3, cell_size * cleared_count * 2)

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
            self.trigger_screen_shake(5, 2)
        self._lock_and_new_piece(player)

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

        # Lock explosion parçacıkları
        if self._particle_effects_enabled():
            cs = self.cell_size
            ox, oy = self.board_offset_x, self.board_offset_y
            for px, py in piece.get_cells():
                if py >= 0:
                    cx = ox + px * cs + cs // 2
                    cy = oy + py * cs + cs // 2
                    self.create_lock_explosion(cx, cy, piece.color, cs)

        # Kilitle (lock_piece_for_player → Board.lock_piece → clear_lines zinciri)
        cleared = self.board.lock_piece_for_player(piece, player)

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
            self.fall_speed = max(100.0, 900.0 - (self.level - 1) * 40.0)

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

            # Line clear visual effects — CoopBoard.clear_lines() satır renklerini kaydetmiştir
            cleared_rows = list(getattr(self.board, 'last_clear_row_colors', {}).keys())
            if cleared_rows:
                self.line_clear_pending_colors = dict(self.board.last_clear_row_colors)
                self.line_clear_pending_rows = list(cleared_rows)
                self._start_line_clear_sweep(cleared_rows)
            # Tetris shake
            if cleared >= 4:
                self.trigger_screen_shake(12, 5)
            elif cleared >= 2:
                self.trigger_screen_shake(6, 2)

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
        else:
            self.p2_hold_used = False

        # Yeni parça spawn
        self._try_spawn_for_player(player)

    def _try_spawn_for_player(self, player: str) -> None:
        next_piece = self.p1_next_piece if player == 'P1' else self.p2_next_piece
        self._place_at_spawn(next_piece, player)
        if self.board.is_valid_position_for_player(next_piece, player):
            if player == 'P1':
                self.p1_current_piece = next_piece
                self.p1_next_piece = self._next_piece('P1')
            else:
                self.p2_current_piece = next_piece
                self.p2_next_piece = self._next_piece('P2')
        else:
            self._freeze_player(player)

    def _freeze_player(self, player: str) -> None:
        if player == 'P1':
            self.p1_frozen = True
            self.p1_current_piece = None
        else:
            self.p2_frozen = True
            self.p2_current_piece = None
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
        """Düşüş tickinde gerçek unfreeze."""
        if player == 'P1':
            self.p1_frozen = False
            self._p1_pending_unfreeze = False
            self.p1_hold_used = False
            next_p = self.p1_next_piece
            self._place_at_spawn(next_p, 'P1')
            if self.board.is_valid_position_for_player(next_p, 'P1'):
                self.p1_current_piece = next_p
                self.p1_next_piece = self._next_piece('P1')
            else:
                self._freeze_player('P1')
        else:
            self.p2_frozen = False
            self._p2_pending_unfreeze = False
            self.p2_hold_used = False
            next_p = self.p2_next_piece
            self._place_at_spawn(next_p, 'P2')
            if self.board.is_valid_position_for_player(next_p, 'P2'):
                self.p2_current_piece = next_p
                self.p2_next_piece = self._next_piece('P2')
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

            if event.type == pygame.VIDEORESIZE:
                req_w = max(event.w, 800)
                req_h = max(event.h, 600)
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
                # Game over'da mouse tıklama — menüye dön
                if self.game_over and event.type == pygame.MOUSEBUTTONDOWN and getattr(event, 'button', None) == 1:
                    return 'menu'
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

                if self.game_over or self.paused:
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
                        self.p1_current_piece.y += 1
                        if not self.board.is_valid_position_for_player(self.p1_current_piece, 'P1'):
                            self.p1_current_piece.y -= 1
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
                        self.p2_current_piece.y += 1
                        if not self.board.is_valid_position_for_player(self.p2_current_piece, 'P2'):
                            self.p2_current_piece.y -= 1
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
    # update
    # ==================================================================

    def update(self, delta_time: float) -> None:
        # Müzik güncelle
        try:
            if self.sound_enabled:
                self.sound.update_music_playlist()
        except Exception:
            pass

        # Efekt güncellemeleri (paused/gameover'da da çalışmalı — animasyon fade'leri)
        if self.effects_enabled:
            self.update_particles(delta_time)
            self.update_ambient_particles(delta_time)
            self.update_drop_trails(delta_time)
            self._update_line_clear_effects(delta_time)
            if self.screen_shake > 0:
                self.screen_shake -= 1

        if self.game_over or self.paused:
            return

        self.elapsed_time += delta_time
        self._emit_event('time_update', {'elapsed': self.elapsed_time / 1000.0})

        # DAS güncelle
        self._update_das(delta_time)
        # Soft drop güncelle
        self._update_soft_drop(delta_time)

        # --- P1 gravity ---
        if not self.p1_frozen and self.p1_current_piece is not None:
            self.p1_fall_time += delta_time
            if self.p1_fall_time >= self.fall_speed:
                self.p1_fall_time = 0
                self.p1_current_piece.y += 1
                if not self.board.is_valid_position_for_player(self.p1_current_piece, 'P1'):
                    self.p1_current_piece.y -= 1
                    self._lock_and_new_piece('P1')
        elif self._p1_pending_unfreeze:
            # Düşüş tick bekleniyor — bir sonraki frame
            self.p1_fall_time += delta_time
            if self.p1_fall_time >= self.fall_speed:
                self.p1_fall_time = 0
                self._do_unfreeze('P1')

        # --- P2 gravity ---
        if not self.p2_frozen and self.p2_current_piece is not None:
            self.p2_fall_time += delta_time
            if self.p2_fall_time >= self.fall_speed:
                self.p2_fall_time = 0
                self.p2_current_piece.y += 1
                if not self.board.is_valid_position_for_player(self.p2_current_piece, 'P2'):
                    self.p2_current_piece.y -= 1
                    self._lock_and_new_piece('P2')
        elif self._p2_pending_unfreeze:
            self.p2_fall_time += delta_time
            if self.p2_fall_time >= self.fall_speed:
                self.p2_fall_time = 0
                self._do_unfreeze('P2')

    # ------------------------------------------------------------------
    # DAS
    # ------------------------------------------------------------------

    def _update_das(self, dt: float) -> None:
        try:
            delay = float(self.settings_manager.get('das_delay', DAS_DELAY)) if self.settings_manager else float(DAS_DELAY)
        except Exception:
            delay = float(DAS_DELAY)
        try:
            repeat = float(self.settings_manager.get('das_repeat', DAS_REPEAT)) if self.settings_manager else float(DAS_REPEAT)
        except Exception:
            repeat = float(DAS_REPEAT)
        delay = max(0.0, delay)
        repeat = max(1.0, repeat)

        for player in ('P1', 'P2'):
            frozen = self.p1_frozen if player == 'P1' else self.p2_frozen
            if frozen:
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
            if not active or frozen or piece is None:
                continue
            if player == 'P1':
                self.p1_soft_drop_timer += dt
                if self.p1_soft_drop_timer >= speed:
                    self.p1_soft_drop_timer = 0
                    piece.y += 1
                    if not self.board.is_valid_position_for_player(piece, 'P1'):
                        piece.y -= 1
                        self._lock_and_new_piece('P1')
                        self.p1_soft_drop_active = False
            else:
                self.p2_soft_drop_timer += dt
                if self.p2_soft_drop_timer >= speed:
                    self.p2_soft_drop_timer = 0
                    piece.y += 1
                    if not self.board.is_valid_position_for_player(piece, 'P2'):
                        piece.y -= 1
                        self._lock_and_new_piece('P2')
                        self.p2_soft_drop_active = False

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

        skin = self.mode_skin or get_mode_skin('classic')
        # Board skin: classic görünüm + modun renk aksentleri
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

        # === Arka plan ===
        if self.outer_background.is_loaded():
            self.outer_background.draw_full_screen(self.screen)
        elif self.background.is_loaded():
            self.background.draw(self.screen, (0, 0, self.window_width, self.window_height))
        else:
            self.screen.fill(skin.outer_bg)
        apply_outer_tint(self.screen, skin)

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

        # Game over
        if self.game_over:
            self._draw_game_over_screen()

    def draw(self) -> None:
        self._render_game()
        pygame.display.flip()

    # ------------------------------------------------------------------
    # Layout hesaplama
    # ------------------------------------------------------------------

    def _calculate_layout(self) -> None:
        key = (int(self.window_width), int(self.window_height))
        if self._layout_key == key:
            return
        self._layout_key = key
        w, h = key

        side_panel = 120  # sol ve sağ paneller için alan
        top_margin = 80
        bottom_margin = 40

        avail_h = max(200, h - top_margin - bottom_margin)
        avail_w = max(200, w - 2 * side_panel - 40)

        cell_by_h = avail_h // self.board.height
        cell_by_w = avail_w // self.board.width
        cs = int(min(40, cell_by_h, cell_by_w))
        cs = max(16, cs)

        bw = self.board.width * cs
        bh = self.board.height * cs

        self.cell_size = cs
        self.board_offset_x = (w - bw) // 2
        self.board_offset_y = top_margin + (avail_h - bh) // 2
        self._side_panel_width = min(side_panel, (w - bw) // 2 - 10)
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
                block_x = ox + x * cs + 1
                block_y = oy + y * cs + 1
                self.draw_textured_block(block_x, block_y, block_size, cell_color, texture_surface, texture_slice)

    def _draw_midline(self, ox, oy, cs, bh) -> None:
        mx = ox + CoopBoard.MIDLINE * cs
        # Neon cyan çizgi + hafif glow
        glow_w = 7
        glow_surf = pygame.Surface((glow_w, bh), pygame.SRCALPHA)
        glow_surf.fill((*retro_style.primary[:3], 18))
        self.screen.blit(glow_surf, (mx - glow_w // 2, oy))
        line_surf = pygame.Surface((2, bh), pygame.SRCALPHA)
        line_surf.fill((*retro_style.primary[:3], 90))
        self.screen.blit(line_surf, (mx - 1, oy))

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
        ghost_y = piece.y
        while self.board.is_valid_position_for_player(piece, player, dy=1):
            piece.y += 1
        if piece.y != ghost_y:
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
                    # Yarı saydam renkli gölge
                    s = pygame.Surface((block_size, block_size))
                    s.set_alpha(50)
                    s.fill(ghost_color)
                    self.screen.blit(s, (block_x, block_y))
                    pygame.draw.rect(self.screen, ghost_color,
                                     (block_x, block_y, block_size, block_size), 2)
        piece.y = ghost_y

    def _draw_hud(self, ox, oy, cs, bw, bh) -> None:
        ui = self._ui_scale()
        cx = self.window_width // 2

        # --- Üst bar: cam panel ile başlık + skor ---
        top_h = self._sx(68, ui, minimum=50)
        top_rect = pygame.Rect(ox - 10, 4, bw + 20, top_h)
        retro_style.draw_glass_panel(self.screen, top_rect, alpha=90,
                                      border_color=(60, 70, 90), glow=False,
                                      top_highlight=False)

        title_font = retro_style.get_font(self._sx(26, ui, minimum=16), bold=True)
        title_surf = title_font.render(t('coop_title', default='QUADRIX CO-OP'), True, retro_style.primary)
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
        preview_cs = max(12, min(20, panel_w // 5))
        ui = self._ui_scale()

        no_preview = getattr(self, '_no_preview', False)
        no_hold = getattr(self, '_no_hold', False)
        left_color = getattr(retro_style, 'primary', (0, 255, 221))
        right_color = getattr(retro_style, 'secondary', getattr(retro_style, 'accent', (255, 180, 80)))
        card_h = preview_cs * 4 + 36
        top_y = oy + 16
        stack_gap = self._sx(16, ui, minimum=10)

        def draw_preview_card(rect: pygame.Rect, piece: Piece | None, label: str, *, accent_color, disabled: bool = False):
            border_c = (100, 50, 60, 90) if disabled else (*accent_color[:3], 90)
            retro_style.draw_glass_panel(self.screen, rect, alpha=90,
                                          border_color=border_c, top_highlight=False)
            content_x = rect.x + 6
            content_y = rect.y + 12

            if disabled:
                label_font = retro_style.get_fitting_font(label, self._sx(14, ui, minimum=10), rect.width - 16, bold=False, min_size=9)
                label_surf = label_font.render(label, True, retro_style.text_muted)
                self.screen.blit(label_surf, label_surf.get_rect(centerx=rect.centerx, top=content_y))
                x_font = retro_style.get_font(self._sx(32, ui, minimum=20), bold=True)
                x_surf = x_font.render('X', True, (200, 50, 50))
                self.screen.blit(x_surf, x_surf.get_rect(center=rect.center))
                return

            if piece is not None:
                self._draw_piece_preview(piece, content_x, content_y, preview_cs, label, panel_width=rect.width - 12)
                return

            label_font = retro_style.get_fitting_font(label, self._sx(14, ui, minimum=10), rect.width - 16, bold=False, min_size=9)
            label_surf = label_font.render(label, True, retro_style.text_muted)
            self.screen.blit(label_surf, label_surf.get_rect(centerx=rect.centerx, top=content_y))
            empty_font = retro_style.get_font(self._sx(16, ui, minimum=11))
            empty_surf = empty_font.render('[ - ]', True, (50, 55, 75))
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
        label_font = retro_style.get_fitting_font(label, self._sx(14, ui, minimum=10), max_width, bold=False, min_size=9)
        label_surf = label_font.render(label, True, retro_style.text_secondary)
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

        # Gradient koyu overlay (üst şeffaf → alt koyu)
        overlay = pygame.Surface(area.size, pygame.SRCALPHA)
        for row in range(area.height):
            alpha = int(80 + 80 * (row / max(1, area.height)))
            pygame.draw.line(overlay, (5, 8, 20, alpha), (0, row), (area.width, row))
        self.screen.blit(overlay, area.topleft)

        # Buz çerçevesi — neon cyan kenarlık
        border_surf = pygame.Surface(area.size, pygame.SRCALPHA)
        pygame.draw.rect(border_surf, (*retro_style.primary[:3], 45), border_surf.get_rect(), 3)
        self.screen.blit(border_surf, area.topleft)

        # Mesaj kutusu
        ui = self._ui_scale()
        msg = t('coop_frozen_waiting', default='Waiting...')
        msg_font = retro_style.get_font(self._sx(18, ui, minimum=12), bold=True)
        msg_surf = msg_font.render(msg, True, retro_style.accent)
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
                sub_text = 'ESC / P'
            elif opt == 'main_menu':
                color_code = retro_style.secondary
                sub_text = 'BACKSPACE'
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
        ui = self._ui_scale()

        # Gradient overlay (kırmızımsı tint — ana tema fail stili)
        overlay = pygame.Surface((w, h), pygame.SRCALPHA)
        for row in range(h):
            ratio = row / max(1, h)
            alpha = int(180 * 0.75 + 40 * ratio)
            overlay.fill((20, 5, 8, min(255, alpha)), (0, row, w, 1))
        self.screen.blit(overlay, (0, 0))

        # Merkez panel
        pw = min(self._sx(440, ui), w - self._sx(80, ui))
        ph = self._sx(280, ui)
        pr = pygame.Rect((w - pw) // 2, (h - ph) // 2, pw, ph)

        # Glow
        glow_rect = pr.inflate(self._sx(20, ui), self._sx(20, ui))
        glow_surf = pygame.Surface(glow_rect.size, pygame.SRCALPHA)
        pygame.draw.rect(glow_surf, (160, 25, 40, 20), glow_surf.get_rect(), border_radius=16)
        self.screen.blit(glow_surf, glow_rect.topleft)

        fail_red = (255, 50, 80)
        retro_style.draw_glass_panel(self.screen, pr, alpha=210,
                                      border_color=(*fail_red, 160), glow=False)

        cx = pr.centerx
        y_cursor = pr.y + self._sx(20, ui)

        # Başlık + glow
        title = t('coop_game_over', default='GAME OVER')
        title_font = retro_style.get_font(self._sx(40, ui, minimum=24), bold=True)
        # Glow katmanları
        for offset in (2, 1):
            glow = title_font.render(title, True, fail_red)
            glow.set_alpha(25)
            for dx, dy in ((offset, 0), (-offset, 0), (0, offset), (0, -offset)):
                self.screen.blit(glow, glow.get_rect(centerx=cx + dx, top=y_cursor + dy))
        title_surf = title_font.render(title, True, fail_red)
        self.screen.blit(title_surf, title_surf.get_rect(centerx=cx, top=y_cursor))
        y_cursor += title_surf.get_height() + self._sx(8, ui)

        if self.p1_frozen and self.p2_frozen:
            sub = t('coop_game_over_both_frozen', default='Both players stuck!')
            sub_font = retro_style.get_font(self._sx(18, ui, minimum=12))
            sub_surf = sub_font.render(sub, True, retro_style.accent)
            self.screen.blit(sub_surf, sub_surf.get_rect(centerx=cx, top=y_cursor))
            y_cursor += sub_surf.get_height() + self._sx(10, ui)
        else:
            y_cursor += self._sx(6, ui)

        # Skor
        score_txt = f"{t('coop_final_score', default='Final Score')}: {self.team_score:,}".replace(',', '.')
        score_font = retro_style.get_font(self._sx(24, ui, minimum=16), bold=True)
        score_surf = score_font.render(score_txt, True, retro_style.text_primary)
        self.screen.blit(score_surf, score_surf.get_rect(centerx=cx, top=y_cursor))
        y_cursor += score_surf.get_height() + self._sx(12, ui)

        # İstatistikler
        info_base = self._sx(16, ui, minimum=11)
        info_max_width = pr.width - self._sx(36, ui, minimum=24)
        minutes = int(self.elapsed_time) // 60000
        seconds = (int(self.elapsed_time) // 1000) % 60
        p1_txt, p2_txt = self._score_contribution_texts()
        info_lines = [
            f"{t('coop_total_lines', default='Total Lines')}: {self.total_lines_cleared}",
            f"{p1_txt}  —  {p2_txt}",
            f"{t('coop_total_time', default='Total Time')}: {minutes}:{seconds:02d}",
        ]
        for line in info_lines:
            info_font = retro_style.get_fitting_font(line, info_base, info_max_width, bold=False, min_size=9)
            surf = info_font.render(line, True, retro_style.text_secondary)
            self.screen.blit(surf, surf.get_rect(centerx=cx, top=y_cursor))
            y_cursor += surf.get_height() + self._sx(4, ui)

        # Alt ipucu
        hint = t('coop_press_continue', default='Press ESC to return')
        hint_font = retro_style.get_font(self._sx(14, ui, minimum=10))
        hint_surf = hint_font.render(hint, True, retro_style.text_muted)
        self.screen.blit(hint_surf, hint_surf.get_rect(centerx=cx, bottom=pr.bottom - self._sx(12, ui)))
