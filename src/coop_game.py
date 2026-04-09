"""Co-op Game: Yerel 2 oyunculu kooperatif modu.

PvP akışını temel alarak tek ortak 20×20 board üzerinde çalışır.
P1 (sol 10 sütun, WASD) ve P2 (sağ 10 sütun, yön tuşları) bağımsız
parça akışları alır; satırlar yalnızca 20/20 dolu olduğunda temizlenir.
"""

import pygame
import random
import sys
import os
from pathlib import Path

from coop_board import CoopBoard
from pieces import Piece, SHAPES
from constants import (
    BOARD_WIDTH, BOARD_HEIGHT, BLACK, DAS_DELAY, DAS_REPEAT,
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


def _resource_path(relative_path: str) -> str:
    try:
        base_path = Path(sys._MEIPASS)
    except Exception:
        base_path = Path(__file__).resolve().parents[1]
    return os.path.normpath(str(base_path / relative_path))


# ---------------------------------------------------------------------------
# CoopGame
# ---------------------------------------------------------------------------

class CoopGame:
    """Yerel 2-oyunculu co-op sınıfı."""

    # Hold tuşları (hard_drop ile çakışmamak için ayrı tuşlar)
    _P1_HOLD_KEY = pygame.K_e
    _P2_HOLD_KEY = pygame.K_RSHIFT
    _SOFT_DROP_SPEED = 50  # ms

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
        self.mode_skin = get_mode_skin('pvp')  # co-op varsayılan olarak PvP skin kullanır
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
        self._pause_menu_keys = ['resume', 'music', 'music_volume', 'sound_effects', 'sfx_volume', 'main_menu']
        self._pause_option_rects: list[pygame.Rect] = []
        self._pause_volume_rects: dict[str, pygame.Rect] = {}
        self._pause_vol_drag_active = False
        self._pause_vol_drag_option = ''

        # Skor
        self.team_score = 0
        self.total_lines_cleared = 0
        self.level = 1
        self.p1_contribution_pct = 50
        self.p2_contribution_pct = 50
        self.p1_total_cells = 0
        self.p2_total_cells = 0

        # Freeze
        self.p1_frozen = False
        self.p2_frozen = False
        self._p1_pending_unfreeze = False
        self._p2_pending_unfreeze = False

        # Shared hold
        self.shared_hold_piece: Piece | None = None
        self.p1_hold_used = False
        self.p2_hold_used = False
        self.hold_last_player: str | None = None

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
        try:
            shuffle = False
            if self.settings_manager:
                shuffle = bool(self.settings_manager.get('music_shuffle', False))
            self.sound.set_music_playlist(shuffle=shuffle)
        except Exception:
            pass

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
        while self.board.is_valid_position_for_player(piece, player, dy=1):
            piece.y += 1
        self._lock_and_new_piece(player)

    # ==================================================================
    # Shared hold
    # ==================================================================

    def _use_shared_hold(self, player: str) -> None:
        if player == 'P1' and self.p1_hold_used:
            return
        if player == 'P2' and self.p2_hold_used:
            return

        current = self.p1_current_piece if player == 'P1' else self.p2_current_piece

        if self.shared_hold_piece is None:
            # Hold boş — aktif parçayı koy, bag'den yeni çek
            self.shared_hold_piece = current
            new_piece = self._next_piece(player)
            self._place_at_spawn(new_piece, player)
            if not self.board.is_valid_position_for_player(new_piece, player):
                # Bag parçası bile sığmıyor — freeze
                self._freeze_player(player)
                return
            if player == 'P1':
                self.p1_current_piece = new_piece
            else:
                self.p2_current_piece = new_piece
        else:
            # Hold dolu — swap
            held = self.shared_hold_piece
            self._place_at_spawn(held, player)
            # Rotasyonu sıfırla
            while held.rotation_state != 0:
                held.rotate()
            if not self.board.is_valid_position_for_player(held, player):
                # Swap iptal — hold'daki parça sığmıyor
                return
            self.shared_hold_piece = current
            if player == 'P1':
                self.p1_current_piece = held
            else:
                self.p2_current_piece = held

        if player == 'P1':
            self.p1_hold_used = True
        else:
            self.p2_hold_used = True
        self.hold_last_player = player
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

        # Kilitle — owners'a "P1" / "P2" yazılır
        cleared = self.board.lock_piece_for_player(piece, player)

        # Parça yerleştirildi event'i
        self._emit_event('piece_placed', {'player': player, 'piece': piece})

        if cleared == 0:
            self.sound.play('lock')

        if cleared > 0:
            # Skor delta'sını al (Board kendi hesaplamasını yaptı)
            delta = self.board.score - prev_score
            self.team_score += delta
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
            self.game_over = True
            self.sound.play('gameover')

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

    def _handle_pause_menu_input(self, event):
        def apply_option(opt):
            if opt == 'resume':
                return 'resume'
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
        self.screen.fill(self.mode_skin.outer_bg)

        # Arka plan
        if self.background.is_loaded():
            self.background.draw(self.screen, (0, 0, self.window_width, self.window_height))
        apply_outer_tint(self.screen, self.mode_skin)

        cs = self.cell_size
        bw = self.board.width * cs  # 20 * cs
        bh = self.board.height * cs  # 20 * cs
        ox = self.board_offset_x
        oy = self.board_offset_y

        # Board arka planı
        board_rect = pygame.Rect(ox, oy, bw, bh)
        if self.board_background.is_loaded():
            self.board_background.draw(self.screen, board_rect)
        else:
            pygame.draw.rect(self.screen, (6, 6, 16), board_rect)
        apply_board_tint(self.screen, board_rect, self.mode_skin)
        draw_board_overlay(self.screen, board_rect, self.mode_skin)

        # Grid çizgileri
        self._draw_grid(ox, oy, cs, bw, bh)

        # Kilitli bloklar
        self._draw_locked_blocks(ox, oy, cs)

        # Orta çizgi
        self._draw_midline(ox, oy, cs, bh)

        # Ghost parçalar
        self._draw_ghost('P1', ox, oy, cs)
        self._draw_ghost('P2', ox, oy, cs)

        # Aktif parçalar
        self._draw_piece(self.p1_current_piece, ox, oy, cs)
        self._draw_piece(self.p2_current_piece, ox, oy, cs)

        # HUD
        self._draw_hud(ox, oy, cs, bw, bh)

        # Side paneller (next + hold)
        self._draw_side_panels(ox, oy, cs, bw, bh)

        # Freeze overlay
        if self.p1_frozen:
            self._draw_freeze_overlay('P1', ox, oy, cs, bh)
        if self.p2_frozen:
            self._draw_freeze_overlay('P2', ox, oy, cs, bh)

        # Pause
        if self.paused and not self.game_over:
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
        for y in range(board.height):
            for x in range(board.width):
                if board.occupancy[y][x]:
                    color = board.grid[y][x]
                    rect = pygame.Rect(ox + x * cs, oy + y * cs, cs, cs)
                    ts = board.texture_grid[y][x]
                    if ts and self._texture_render_cache:
                        try:
                            draw_jelly_block(self.screen, rect, color, texture_slice=ts,
                                             render_cache=self._texture_render_cache)
                            continue
                        except Exception:
                            pass
                    pygame.draw.rect(self.screen, color, rect)
                    pygame.draw.rect(self.screen, (0, 0, 0), rect, 1)

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
        for px, py in piece.get_cells():
            if py < 0:
                continue
            rect = pygame.Rect(ox + px * cs, oy + py * cs, cs, cs)
            ts = getattr(piece, 'texture_surface', None)
            if ts and self._texture_render_cache:
                try:
                    draw_jelly_block(self.screen, rect, piece.color, texture_slice=ts,
                                     render_cache=self._texture_render_cache)
                    continue
                except Exception:
                    pass
            pygame.draw.rect(self.screen, piece.color, rect)
            pygame.draw.rect(self.screen, (0, 0, 0), rect, 1)

    def _draw_ghost(self, player: str, ox, oy, cs) -> None:
        piece = self.p1_current_piece if player == 'P1' else self.p2_current_piece
        if piece is None:
            return
        ghost_y = piece.y
        while self.board.is_valid_position_for_player(piece, player, dy=1):
            piece.y += 1
        if piece.y != ghost_y:
            for px, py in piece.get_cells():
                if py < 0:
                    continue
                rect = pygame.Rect(ox + px * cs, oy + py * cs, cs, cs)
                s = pygame.Surface((cs, cs), pygame.SRCALPHA)
                s.fill((*piece.color[:3], 40))
                self.screen.blit(s, rect.topleft)
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
        title_surf = title_font.render("QUADRIX CO-OP", True, retro_style.primary)
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

        contrib_txt = f"P1 %{self.p1_contribution_pct}  —  P2 %{self.p2_contribution_pct}"
        contrib_font = retro_style.get_font(self._sx(14, ui, minimum=10))
        contrib_surf = contrib_font.render(contrib_txt, True, (80, 230, 160))
        self.screen.blit(contrib_surf, contrib_surf.get_rect(centerx=cx, top=info_y + stat_font.get_height() + 2))

    def _draw_side_panels(self, ox, oy, cs, bw, bh) -> None:
        panel_w = self._side_panel_width
        preview_cs = max(12, min(20, panel_w // 5))
        ui = self._ui_scale()

        no_preview = getattr(self, '_no_preview', False)

        if not no_preview:
            # P1 next (sol panel) — glass panel
            p1_panel_x = ox - panel_w - 8
            p1_rect = pygame.Rect(p1_panel_x - 6, oy + 16, panel_w + 12, preview_cs * 4 + 36)
            retro_style.draw_glass_panel(self.screen, p1_rect, alpha=90,
                                          border_color=(60, 70, 90), top_highlight=False)
            self._draw_piece_preview(self.p1_next_piece, p1_panel_x, oy + 28, preview_cs, "P1 NEXT")

            # P2 next (sağ panel) — glass panel
            p2_panel_x = ox + bw + 8
            p2_rect = pygame.Rect(p2_panel_x - 6, oy + 16, panel_w + 12, preview_cs * 4 + 36)
            retro_style.draw_glass_panel(self.screen, p2_rect, alpha=90,
                                          border_color=(60, 70, 90), top_highlight=False)
            self._draw_piece_preview(self.p2_next_piece, p2_panel_x, oy + 28, preview_cs, "P2 NEXT")

        # Shared hold (ortada, board altı) — glass panel
        hold_label = t('coop_shared_hold', default='Shared Hold')
        stat_font = retro_style.get_font(self._sx(14, ui, minimum=10))
        hold_y = oy + bh + self._sx(58, ui, minimum=44)
        hold_w = max(preview_cs * 5 + 20, stat_font.size(hold_label)[0] + 20)
        hold_h = preview_cs * 3 + 36
        hold_rect = pygame.Rect(self.window_width // 2 - hold_w // 2, hold_y - 6, hold_w, hold_h)
        no_hold = getattr(self, '_no_hold', False)
        border_c = (100, 50, 60) if no_hold else (*retro_style.primary[:3], 80)
        retro_style.draw_glass_panel(self.screen, hold_rect, alpha=90,
                                      border_color=border_c, top_highlight=False)

        if no_hold:
            # Hold engelli — kırmızı X
            label_surf = stat_font.render(hold_label, True, retro_style.text_muted)
            self.screen.blit(label_surf, label_surf.get_rect(centerx=self.window_width // 2, top=hold_y))
            x_font = retro_style.get_font(self._sx(36, ui, minimum=20), bold=True)
            x_surf = x_font.render('✕', True, (200, 50, 50))
            self.screen.blit(x_surf, x_surf.get_rect(center=hold_rect.center))
        elif self.shared_hold_piece:
            self._draw_piece_preview(self.shared_hold_piece, self.window_width // 2 - preview_cs * 2, hold_y, preview_cs, hold_label)
        else:
            label_surf = stat_font.render(hold_label, True, retro_style.text_muted)
            self.screen.blit(label_surf, label_surf.get_rect(centerx=self.window_width // 2, top=hold_y))
            empty_font = retro_style.get_font(self._sx(16, ui, minimum=11))
            empty_surf = empty_font.render("[ — ]", True, (50, 55, 75))
            self.screen.blit(empty_surf, empty_surf.get_rect(centerx=self.window_width // 2, top=hold_y + stat_font.get_height() + 4))

    def _draw_piece_preview(self, piece: Piece | None, x, y, cs, label: str) -> None:
        if piece is None:
            return
        ui = self._ui_scale()
        label_font = retro_style.get_font(self._sx(14, ui, minimum=10))
        label_surf = label_font.render(label, True, retro_style.text_secondary)
        self.screen.blit(label_surf, (x, y))
        py = y + label_surf.get_height() + 4
        for row_i, row in enumerate(piece.shape):
            for col_i, cell in enumerate(row):
                if cell:
                    rect = pygame.Rect(x + col_i * cs, py + row_i * cs, cs, cs)
                    pygame.draw.rect(self.screen, piece.color, rect)
                    pygame.draw.rect(self.screen, (0, 0, 0), rect, 1)

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
        start_y = pr.y + top_pad
        for i, opt in enumerate(self.pause_menu_options):
            y = start_y + i * (item_h + gap)
            btn_rect = pygame.Rect(pr.x + self._sx(22, ui), y, pr.width - self._sx(44, ui), item_h)
            self._pause_option_rects.append(btn_rect)
            selected = i == self.pause_menu_selected
            label = self._pause_option_label(opt)
            retro_style.draw_uniform_button(self.screen, btn_rect, label,
                                             color_code=retro_style.accent if selected else retro_style.secondary,
                                             selected=selected)
            if opt in ('music_volume', 'sfx_volume'):
                vol = self.sound.music_volume if opt == 'music_volume' else self.sound.sfx_volume
                bar_rect = pygame.Rect(btn_rect.x + 10, btn_rect.bottom - 8, btn_rect.width - 20, 4)
                pygame.draw.rect(self.screen, (60, 60, 80), bar_rect)
                fill = pygame.Rect(bar_rect.x, bar_rect.y, int(bar_rect.width * vol), bar_rect.height)
                pygame.draw.rect(self.screen, retro_style.accent, fill)
                self._pause_volume_rects[opt] = bar_rect

    def _pause_option_label(self, opt: str) -> str:
        if opt == 'resume':
            return t('coop_resume', default='Resume')
        if opt == 'music':
            state = "ON" if self.sound.music_enabled else "OFF"
            return f"{t('music', default='Music')}: {state}"
        if opt == 'music_volume':
            return f"{t('music_volume', default='Music Vol')}: {int(self.sound.music_volume * 100)}%"
        if opt == 'sound_effects':
            state = "ON" if self.sound.sfx_enabled else "OFF"
            return f"{t('sound_effects', default='SFX')}: {state}"
        if opt == 'sfx_volume':
            return f"{t('sfx_volume', default='SFX Vol')}: {int(self.sound.sfx_volume * 100)}%"
        if opt == 'main_menu':
            return t('coop_main_menu', default='Main Menu')
        return opt

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
        info_font = retro_style.get_font(self._sx(16, ui, minimum=11))
        minutes = int(self.elapsed_time) // 60000
        seconds = (int(self.elapsed_time) // 1000) % 60
        info_lines = [
            f"{t('coop_total_lines', default='Total Lines')}: {self.total_lines_cleared}",
            f"P1 %{self.p1_contribution_pct}  —  P2 %{self.p2_contribution_pct}",
            f"{t('coop_total_time', default='Total Time')}: {minutes}:{seconds:02d}",
        ]
        for line in info_lines:
            surf = info_font.render(line, True, retro_style.text_secondary)
            self.screen.blit(surf, surf.get_rect(centerx=cx, top=y_cursor))
            y_cursor += surf.get_height() + self._sx(4, ui)

        # Alt ipucu
        hint = t('coop_press_continue', default='Press ESC to return')
        hint_font = retro_style.get_font(self._sx(14, ui, minimum=10))
        hint_surf = hint_font.render(hint, True, retro_style.text_muted)
        self.screen.blit(hint_surf, hint_surf.get_rect(centerx=cx, bottom=pr.bottom - self._sx(12, ui)))
