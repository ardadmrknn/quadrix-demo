"""Co-op modülü temel testleri."""
import sys, os, types

# pygame stub
_pg = types.ModuleType('pygame')
_pg.K_a = 97; _pg.K_d = 100; _pg.K_w = 119; _pg.K_s = 115
_pg.K_b = 98; _pg.K_c = 99; _pg.K_e = 101; _pg.K_g = 103; _pg.K_h = 104
_pg.K_m = 109; _pg.K_n = 110; _pg.K_p = 112; _pg.K_q = 113; _pg.K_r = 114
_pg.K_t = 116; _pg.K_u = 117; _pg.K_v = 118
_pg.K_LEFT = 276; _pg.K_RIGHT = 275; _pg.K_UP = 273; _pg.K_DOWN = 274
_pg.K_LEFTBRACKET = 91; _pg.K_RIGHTBRACKET = 93
_pg.K_SPACE = 32; _pg.K_LSHIFT = 304; _pg.K_RSHIFT = 303; _pg.K_ESCAPE = 27; _pg.K_RETURN = 13; _pg.K_KP_ENTER = 271; _pg.K_BACKSPACE = 8
_pg.QUIT = 256; _pg.KEYDOWN = 768; _pg.KEYUP = 769; _pg.VIDEORESIZE = 65281; _pg.MOUSEMOTION = 1024; _pg.MOUSEBUTTONDOWN = 1025; _pg.MOUSEBUTTONUP = 1026; _pg.MOUSEWHEEL = 1027; _pg.SRCALPHA = 65536
_pg.init = lambda: None; _pg.get_init = lambda: True
class _Key:
    @staticmethod
    def key_code(n): return 0
    @staticmethod
    def name(k):
        key_names = {
            32: 'space',
            97: 'a',
            100: 'd',
            101: 'e',
            112: 'p',
            222: 'right shift',
            276: 'left',
            275: 'right',
            273: 'up',
            274: 'down',
            303: 'right shift',
            304: 'left shift',
        }
        return key_names.get(k, str(k))
    @staticmethod
    def set_repeat(*a): pass
_pg.key = _Key()
class _Surf:
    def __init__(self, *a, **kw): pass
    def get_width(self): return 1920
    def get_height(self): return 1080
    def fill(self, *a): pass
    def blit(self, *a): pass
    def set_alpha(self, *a): pass
    def get_rect(self, **kw):
        class R:
            def __init__(self): self.centerx=0; self.centery=0; self.topleft=(0,0); self.top=0; self.center=(0,0)
            def collidepoint(self, *a): return False
        return R()
    def get_size(self): return (1920, 1080)
    def convert_alpha(self): return self


class _SizedSurf(_Surf):
    def __init__(self, width=1920, height=1080):
        self._size = (width, height)

    def get_width(self): return self._size[0]
    def get_height(self): return self._size[1]
    def get_size(self): return self._size
_pg.Surface = _Surf
class _Draw:
    @staticmethod
    def rect(*a, **kw): pass
    @staticmethod
    def line(*a, **kw): pass
    @staticmethod
    def circle(*a, **kw): pass
_pg.draw = _Draw()
class _Rect:
    def __init__(self, *a):
        if len(a) == 4:
            self.x, self.y, self.width, self.height = a
        elif len(a) == 2 and isinstance(a[0], tuple) and isinstance(a[1], tuple):
            self.x, self.y = a[0]
            self.width, self.height = a[1]
        else:
            self.x=0; self.y=0; self.width=0; self.height=0
        self.w = self.width
        self.h = self.height
        self.size=(self.width,self.height)
        self.topleft=(self.x,self.y)
        self.top=self.y
        self.left=self.x
        self.right=self.x + self.width
        self.bottom=self.y + self.height
        self.center=(self.x + self.width // 2, self.y + self.height // 2)
        self.centerx=self.center[0]
        self.centery=self.center[1]
    def collidepoint(self, *a): return False
    def inflate(self, dx, dy):
        return _Rect(self.x - dx // 2, self.y - dy // 2, self.width + dx, self.height + dy)
_pg.Rect = _Rect
class _Display:
    @staticmethod
    def get_surface(): return _Surf()
    @staticmethod
    def flip(): pass
_pg.display = _Display()
class _Mouse:
    @staticmethod
    def set_visible(*a): pass
    @staticmethod
    def get_pos(): return (0,0)
_pg.mouse = _Mouse()
class _Time:
    @staticmethod
    def get_ticks(): return 0
_pg.time = _Time()
_pg.event = types.SimpleNamespace(get=lambda: [])

_STUB_MODULES = (
    'pygame',
    'sound',
    'background',
    'background_effects',
    'mode_skins',
    'retro_style',
    'renderers',
    'renderers.jelly_renderer',
    'themes',
    'block_styles',
    'gamepad_manager',
    'promptfont_support',
    'platform_utils',
    'localization',
    'ui_theme',
    'sweep_effects',
    'asset_manager',
)
_ORIGINAL_MODULES = {name: sys.modules.get(name) for name in _STUB_MODULES}
sys.modules['pygame'] = _pg

# Basit stub'lar
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# Ağır bağımlılıkları stub'la
for mod_name in _STUB_MODULES[1:]:
    sys.modules[mod_name] = types.ModuleType(mod_name)

for mod_name in ('board', 'pieces', 'coop_board', 'coop_game'):
    sys.modules.pop(mod_name, None)

# localization
import localization as _loc
if not hasattr(_loc, 't'):
    def _t(key, default='', **kwargs):
        text = default or key
        if kwargs:
            try:
                text = text.format(**kwargs)
            except Exception:
                pass
        return text
    _loc.t = _t

# ui_theme
import ui_theme as _ut
class _FakeFont:
    def render(self, *a, **kw): return _Surf()
    def size(self, t): return (len(t)*8, 16)
    def get_height(self): return 16
    def get_linesize(self): return 18
class _UIFonts:
    @staticmethod
    def get(sz): return _FakeFont()
class _UIColors: pass
_ut.UIFonts = _UIFonts
_ut.UIColors = _UIColors

# platform_utils
import platform_utils as _pu
_pu.create_display = lambda *a, **kw: _Surf()
_pu.normalize_mouse_pos = lambda pos: pos
_pu.get_mouse_pos = lambda: (0,0)
_pu.set_app_icon = lambda: None
_pu.IS_WINDOWS = False

# gamepad_manager
import gamepad_manager as _gm
_gm.is_gamepad_connected = lambda: False
_gm.normalize_gamepad_event_button = lambda event: None
_gm.get_gamepad_manager = lambda: types.SimpleNamespace(rumble=lambda *a, **kw: None)

# promptfont_support
import promptfont_support as _pfs
_pfs.render_action_prompt_surface = lambda *a, **kw: None
_pfs.render_button_index_prompt_surface = lambda *a, **kw: None

# sound
import sound as _snd
class _SM:
    enabled = True; sfx_enabled = True; music_enabled = True; music_volume = 0.3; sfx_volume = 0.5
    def __init__(self): self.game_over_sequence_calls = 0; self.stop_music_calls = 0; self.play_calls = []
    def play(self, *a): self.play_calls.append(a)
    def stop_music(self): self.stop_music_calls += 1
    def duck_music(self): pass
    def unduck_music(self): pass
    def update_music_playlist(self): pass
    def set_music_volume(self, v): self.music_volume = v
    def set_volume(self, v): self.sfx_volume = v
    def set_music_playlist(self, *a, **kw): pass
    def play_music(self, *a, **kw): pass
    def play_game_over_sequence(self): self.game_over_sequence_calls += 1
_snd.SoundManager = _SM

class _FakeSettings:
    def __init__(self, controls=None, values=None):
        self._controls = controls or {}
        self._values = values or {}

    def get(self, key, default=None):
        return self._values.get(key, default)

    def get_controls(self):
        return self._controls

# background
import background as _bg
class _BM:
    def set_transparency(self, *a): pass
    def load_image(self, *a): return False
    def is_loaded(self): return False
    def draw(self, *a): pass
    def draw_full_screen(self, *a): pass
_bg.BackgroundManager = _BM

# background_effects
import background_effects as _be
_be.get_shared_falling_blocks_layer = lambda *args, **kwargs: None

# mode_skins
import mode_skins as _ms
class _Skin:
    outer_bg = (0,0,0); grid_color = (50,50,80)
_ms.apply_board_tint = lambda *a: None
_ms.apply_outer_tint = lambda *a: None
_ms.draw_board_overlay = lambda *a: None
_ms.get_mode_skin = lambda *a: _Skin()

# retro_style
import retro_style as _rs
class _RS:
    primary = (0, 255, 221); accent = (255, 165, 0); secondary = (255, 0, 255)
    success = (60, 200, 120)
    text_primary = (230, 235, 245); text_secondary = (180, 200, 220); text_muted = (120, 140, 170)
    glass_bg = (15, 20, 40, 140); glass_border = (80, 120, 180, 100)
    bg_color = (8, 12, 28); bg_secondary = (12, 18, 38)
    _menu_transparency = 1.0
    _bg_transparency = 0.3
    def get_font(self, *a, **kw): return _FakeFont()
    def get_fitting_font(self, *a, **kw): return _FakeFont()
    def get_mono_font(self, *a, **kw): return _FakeFont()
    def render_fit_text(self, *a, **kw): return _pg.Surface((10, 10))
    def draw_glass_panel(self, *a, **kw): pass
    def draw_uniform_button(self, *a, **kw): pass
    def draw_volume_bar(self, *a, **kw): pass
    def _scale_menu_alpha(self, a): return a
    def set_menu_transparency(self, value): self._menu_transparency = float(value)
    def set_background_transparency(self, value): self._bg_transparency = float(value)
_rs.retro_style = _RS()

# themes
import themes as _th
_th.ThemeManager = lambda *a, **kw: type('T', (), {'current_theme': None, 'get_piece_color': lambda self, name: (200, 200, 200)})()

# block_styles
import block_styles as _bs
_bs.BlockStyleManager = lambda *a, **kw: type('B', (), {
    'apply_to_piece': lambda s, p, *a2, **kw2: None,
    'get_texture_surface': lambda s, name: None,
    'get_slice_bounds': lambda s, name: {'x': 0.0, 'y': 0.0, 'w': 1.0, 'h': 1.0},
})()
_bs.TextureSlice = None
_bs.TextureRenderCache = lambda: {}

# renderers.jelly_renderer
import renderers.jelly_renderer as _jr
_jr.draw_jelly_block = lambda *a, **kw: None
_jr.draw_jelly_border = lambda *a, **kw: None

# sweep_effects
import sweep_effects as _se
if not hasattr(_se, 'SweepCatState'):
    class _SCS:
        pass
    _se.SweepCatState = _SCS
if not hasattr(_se, 'draw_rainbow_cat_sweep'):
    _se.draw_rainbow_cat_sweep = lambda *a, **kw: None

# asset_manager
import asset_manager as _am
if not hasattr(_am, 'load_image'):
    _am.load_image = lambda *a, **kw: _Surf()

# ===== Şimdi modülleri import et =====
from board import Board
from pieces import Piece, SHAPES
from coop_board import CoopBoard
import coop_game as coop_game_module
from coop_game import CoopGame

for mod_name, original in _ORIGINAL_MODULES.items():
    if original is None:
        sys.modules.pop(mod_name, None)
    else:
        sys.modules[mod_name] = original


# =====================================================================
# CoopBoard testleri
# =====================================================================

def test_coop_board_dimensions():
    b = CoopBoard()
    assert b.width == 20
    assert b.height == 20

def test_spawn_positions():
    b = CoopBoard()
    assert b.get_spawn_position('P1') == (3, 0)
    assert b.get_spawn_position('P2') == (13, 0)

def test_player_column_enforcement():
    b = CoopBoard()
    p = Piece(x=3, y=0, shape_index=0)
    assert b.is_valid_position_for_player(p, 'P1')
    assert not b.is_valid_position_for_player(p, 'P2')
    p2 = Piece(x=13, y=0, shape_index=0)
    assert b.is_valid_position_for_player(p2, 'P2')
    assert not b.is_valid_position_for_player(p2, 'P1')

def test_lock_piece_writes_owner():
    b = CoopBoard()
    p = Piece(x=3, y=18, shape_index=0)
    b.lock_piece_for_player(p, 'P1')
    for px, py in p.get_cells():
        if 0 <= py < 20:
            assert b.owners[py][px] == 'P1'

def test_full_line_clear():
    b = CoopBoard()
    y = 19
    for x in range(20):
        b.grid[y][x] = (255, 0, 0)
        b.occupancy[y][x] = True
        b.owners[y][x] = 'P1' if x < 10 else 'P2'
    cleared = b.clear_lines()
    assert cleared >= 1
    assert b.last_clear_p1_cells > 0
    assert b.last_clear_p2_cells > 0
    assert y in b.last_clear_row_colors
    assert len(b.last_clear_row_colors[y]) == 20
    assert b.last_clear_row_colors[y][0] == (255, 0, 0)


# =====================================================================
# CoopGame testleri
# =====================================================================

def test_coop_game_init():
    cg = CoopGame(sound_enabled=False, effects_enabled=False, screen=_Surf(), sound_manager=_SM())
    assert cg.board.width == 20
    assert cg.p1_current_piece is not None
    assert cg.p2_current_piece is not None
    assert not cg.game_over
    assert cg.team_score == 0

def test_player_hold_empty_stores_only_that_players_piece():
    cg = CoopGame(sound_enabled=False, effects_enabled=False, screen=_Surf(), sound_manager=_SM())
    old_p1 = cg.p1_current_piece
    old_next = cg.p1_next_piece
    cg._use_shared_hold('P1')
    assert cg.p1_hold_piece is old_p1
    assert cg.p2_hold_piece is None
    assert cg.p1_current_piece is old_next
    assert cg.p1_next_piece is not old_next
    assert cg.p1_hold_used

def test_player_hold_empty_does_not_replace_other_players_filled_hold():
    cg = CoopGame(sound_enabled=False, effects_enabled=False, screen=_Surf(), sound_manager=_SM())
    # P1 hold'a koyar
    cg._use_shared_hold('P1')
    p1_held = cg.p1_hold_piece

    # P2 hold'u ilk kez doldurur; P1 tarafı değişmez
    old_p2 = cg.p2_current_piece
    cg._use_shared_hold('P2')
    assert cg.p2_hold_used
    assert cg.p1_hold_piece is p1_held
    assert cg.p2_hold_piece is old_p2

def test_player_hold_swap_uses_players_own_hold_piece():
    cg = CoopGame(sound_enabled=False, effects_enabled=False, screen=_Surf(), sound_manager=_SM())
    cg._use_shared_hold('P1')
    stored_piece = cg.p1_hold_piece
    replacement_piece = cg.p1_current_piece
    next_after_hold = cg.p1_next_piece

    cg.p1_hold_used = False
    cg._use_shared_hold('P1')

    assert cg.p1_current_piece is stored_piece
    assert cg.p1_hold_piece is replacement_piece
    assert cg.p2_hold_piece is None
    assert cg.p1_next_piece is next_after_hold

def test_player_hold_swap_after_lock_returns_stored_piece():
    cg = CoopGame(sound_enabled=False, effects_enabled=False, screen=_Surf(), sound_manager=_SM())

    stored_piece = cg.p1_current_piece
    cg._use_shared_hold('P1')

    cg.p1_current_piece.y = 10
    cg._lock_and_new_piece('P1')
    spawned_after_lock = cg.p1_current_piece

    assert cg.p1_hold_used is False

    cg._use_shared_hold('P1')

    assert cg.p1_current_piece is stored_piece
    assert cg.p1_hold_piece is spawned_after_lock

def test_resolve_controls_uses_per_player_hold_bindings_from_settings():
    settings = _FakeSettings({
        'pvp': {
            'player1': {'hold': 111},
            'player2': {'hold': 222},
        },
        'single_player': {'pause': 333},
    })

    cg = CoopGame(
        sound_enabled=False,
        effects_enabled=False,
        screen=_Surf(),
        settings_manager=settings,
        sound_manager=_SM(),
    )

    assert cg.pvp_controls['player1']['hold'] == 111
    assert cg.pvp_controls['player2']['hold'] == 222
    assert cg.pvp_controls['pause'] == 333

def test_handle_input_triggers_hold_with_custom_per_player_bindings():
    settings = _FakeSettings({
        'pvp': {
            'player1': {'hold': 111},
            'player2': {'hold': 222},
        }
    })
    cg = CoopGame(
        sound_enabled=False,
        effects_enabled=False,
        screen=_Surf(),
        settings_manager=settings,
        sound_manager=_SM(),
    )

    original_event_get = _pg.event.get
    _pg.event.get = lambda: [
        types.SimpleNamespace(type=_pg.KEYDOWN, key=111),
        types.SimpleNamespace(type=_pg.KEYDOWN, key=222),
    ]
    try:
        result = cg.handle_input()
    finally:
        _pg.event.get = original_event_get

    assert result is True
    assert cg.p1_hold_used is True
    assert cg.p2_hold_used is True
    assert cg.p1_hold_piece is not None
    assert cg.p2_hold_piece is not None

def test_freeze_on_spawn_fail():
    cg = CoopGame(sound_enabled=False, effects_enabled=False, screen=_Surf(), sound_manager=_SM())
    # P1 bölgesini dolduralım
    for y in range(4):
        for x in range(10):
            cg.board.occupancy[y][x] = True
            cg.board.grid[y][x] = (255,0,0)
    cg._freeze_player('P1')
    assert cg.p1_frozen
    assert cg.p1_current_piece is None

def test_double_freeze_game_over():
    sound = _SM()
    cg = CoopGame(sound_enabled=False, effects_enabled=False, screen=_Surf(), sound_manager=sound)
    cg._freeze_player('P1')
    cg._freeze_player('P2')
    assert cg.game_over
    assert sound.game_over_sequence_calls == 1

def test_lock_out_freeze_does_not_commit_top_out_piece_to_board():
    cg = CoopGame(sound_enabled=False, effects_enabled=True, screen=_Surf(), sound_manager=_SM())
    events = []
    explosions = []
    cg._event_listeners.append(lambda event_type, event_data: events.append((event_type, event_data)))
    cg._particle_effects_enabled = lambda: True
    cg.create_lock_explosion = lambda *args, **kwargs: explosions.append((args, kwargs))
    piece = Piece(x=17, y=-1, shape_index=5)
    cg.p2_current_piece = piece

    cg._lock_and_new_piece('P2')

    assert cg.p2_frozen
    assert cg.p2_current_piece is None
    assert cg.board.score == 0
    assert all(not cg.board.occupancy[0][x] for x in range(17, 20))
    assert explosions == []
    assert not any(event_type == 'piece_placed' for event_type, _event_data in events)
    assert any(
        event_type == 'player_frozen' and event_data.get('player') == 'P2'
        for event_type, event_data in events
    )

def test_unfrozen_player_has_extended_lock_delay_in_top_four_rows():
    cg = CoopGame(sound_enabled=False, effects_enabled=False, screen=_Surf(), sound_manager=_SM())
    cg.lock_delay = 500
    cg.p1_current_piece = None
    cg.p1_next_piece = Piece(x=0, y=0, shape_index=1)
    cg.p1_frozen = True
    cg._p1_pending_unfreeze = True

    for x in (3, 4):
        cg.board.occupancy[1][x] = True
        cg.board.grid[1][x] = (255, 0, 0)
        cg.board.owners[1][x] = 'P2'

    cg._do_unfreeze('P1')

    assert not cg.p1_frozen
    assert cg.p1_current_piece is not None
    assert cg.p1_current_piece.y == -1
    assert cg._effective_lock_delay_for_player('P1', cg.p1_current_piece) == 2500.0

    cg._update_lock_delay(2499.0)

    assert not cg.p1_frozen
    assert cg.p1_current_piece is not None

    cg._update_lock_delay(1.0)

    assert cg.p1_frozen

def test_unfreeze_lock_delay_persists_while_top_four_rows_stay_dangerous():
    cg = CoopGame(sound_enabled=False, effects_enabled=False, screen=_Surf(), sound_manager=_SM())
    cg.lock_delay = 500
    first_piece = Piece(x=3, y=2, shape_index=1)
    cg.p1_current_piece = first_piece
    cg.p1_next_piece = Piece(x=0, y=0, shape_index=1)
    cg._set_unfreeze_lock_delay_active('P1', True)

    for x in (3, 4):
        cg.board.occupancy[4][x] = True
        cg.board.grid[4][x] = (255, 0, 0)
        cg.board.owners[4][x] = 'P2'

    cg._update_lock_delay(2499.0)

    assert cg.p1_current_piece is first_piece

    cg._update_lock_delay(1.0)

    assert not cg.p1_frozen
    assert cg.p1_current_piece is not first_piece
    assert cg._unfreeze_lock_delay_active('P1')
    assert cg._effective_lock_delay_for_player('P1', cg.p1_current_piece) == 2500.0

    for y in range(4):
        for x in range(10):
            cg.board.occupancy[y][x] = False
            cg.board.grid[y][x] = (0, 0, 0)
            cg.board.owners[y][x] = None
    cg.p1_current_piece.y = 5
    cg._update_lock_delay(0.0)

    assert not cg._unfreeze_lock_delay_active('P1')

def test_unfreeze_lock_delay_rearms_after_each_freeze_cycle():
    cg = CoopGame(sound_enabled=False, effects_enabled=False, screen=_Surf(), sound_manager=_SM())
    cg.lock_delay = 500
    cg.p1_current_piece = None

    for _cycle in range(2):
        for y in range(4):
            for x in range(10, 20):
                cg.board.occupancy[y][x] = False
                cg.board.grid[y][x] = (0, 0, 0)
                cg.board.owners[y][x] = None
        for x in (13, 14):
            cg.board.occupancy[1][x] = True
            cg.board.grid[1][x] = (255, 0, 0)
            cg.board.owners[1][x] = 'P1'

        cg.p2_current_piece = None
        cg.p2_next_piece = Piece(x=0, y=0, shape_index=1)
        cg.p2_frozen = False
        cg._freeze_player('P2')
        cg._p2_pending_unfreeze = True

        cg._do_unfreeze('P2')

        assert not cg.p2_frozen
        assert cg.p2_current_piece is not None
        assert cg._effective_lock_delay_for_player('P2', cg.p2_current_piece) == 2500.0

        cg._update_lock_delay(2499.0)

        assert not cg.p2_frozen

        cg._update_lock_delay(1.0)

        assert cg.p2_frozen

def test_level_progression():
    cg = CoopGame(sound_enabled=False, effects_enabled=False, screen=_Surf(), sound_manager=_SM())
    cg.total_lines_cleared = 10
    cg.level = (cg.total_lines_cleared // 5) + 1
    assert cg.level == 3

def test_contribution_tracking():
    cg = CoopGame(sound_enabled=False, effects_enabled=False, screen=_Surf(), sound_manager=_SM())
    cg.p1_total_cells = 30
    cg.p2_total_cells = 70
    total = cg.p1_total_cells + cg.p2_total_cells
    cg.p1_contribution_pct = round(100 * cg.p1_total_cells / total)
    cg.p2_contribution_pct = 100 - cg.p1_contribution_pct
    assert cg.p1_contribution_pct == 30
    assert cg.p2_contribution_pct == 70

def test_try_move():
    cg = CoopGame(sound_enabled=False, effects_enabled=False, screen=_Surf(), sound_manager=_SM())
    old_x = cg.p1_current_piece.x
    result = cg._try_move('P1', 1)
    if result:
        assert cg.p1_current_piece.x == old_x + 1

def test_hard_drop():
    cg = CoopGame(sound_enabled=False, effects_enabled=False, screen=_Surf(), sound_manager=_SM())
    cg._hard_drop('P1')
    # Hard drop sonrası yeni parça spawn olmalı veya freeze
    # (spawn olabilir ya da piece None olabilir freeze durumunda)
    assert cg.p1_current_piece is not None or cg.p1_frozen

def test_lock_and_new_piece_caches_clear_row_snapshot():
    cg = CoopGame(sound_enabled=False, effects_enabled=True, screen=_Surf(), sound_manager=_SM())
    row = 19
    prefill_color = (255, 0, 0)

    for x in list(range(0, 8)) + list(range(10, 20)):
        cg.board.grid[row][x] = prefill_color
        cg.board.occupancy[row][x] = True
        cg.board.owners[row][x] = 'P1' if x < 10 else 'P2'

    piece = Piece(x=8, y=18, shape_index=1)
    cg._apply_block_style(piece)
    cg.p1_current_piece = piece

    cg._lock_and_new_piece('P1')

    assert row in cg.line_clear_pending_rows
    assert row in cg.line_clear_pending_colors
    row_colors = cg.line_clear_pending_colors[row]
    assert len(row_colors) == 20
    assert row_colors[8] == piece.color
    assert row_colors[9] == piece.color

def test_lock_and_new_piece_tracks_score_contribution_for_scoring_player():
    cg = CoopGame(sound_enabled=False, effects_enabled=False, screen=_Surf(), sound_manager=_SM())
    row = 19

    for x in list(range(0, 8)) + list(range(10, 20)):
        cg.board.grid[row][x] = (255, 0, 0)
        cg.board.occupancy[row][x] = True
        cg.board.owners[row][x] = 'P1' if x < 10 else 'P2'

    piece = Piece(x=8, y=18, shape_index=1)
    cg._apply_block_style(piece)
    cg.p1_current_piece = piece

    cg._lock_and_new_piece('P1')

    assert cg.team_score > 0
    assert cg.p1_score_contribution == cg.team_score
    assert cg.p2_score_contribution == 0
    assert cg.p1_score_contribution_pct == 100
    assert cg.p2_score_contribution_pct == 0

def test_coop_ambient_particles_use_neutral_star_palette_like_other_modes():
    settings = _FakeSettings(values={'particle_effects': 'medium'})
    cg = CoopGame(
        sound_enabled=False,
        effects_enabled=True,
        screen=_Surf(),
        settings_manager=settings,
        sound_manager=_SM(),
    )

    assert cg.ambient_particles
    assert {tuple(p['color']) for p in cg.ambient_particles} == {(200, 200, 255)}

def test_coop_sync_runtime_settings_updates_retro_style_transparency_state():
    settings = _FakeSettings(values={
        'bg_transparency': 0.4,
        'menu_transparency': 0.6,
    })

    cg = CoopGame(
        sound_enabled=False,
        effects_enabled=False,
        screen=_Surf(),
        settings_manager=settings,
        sound_manager=_SM(),
    )

    assert _rs.retro_style._bg_transparency == 0.4
    assert _rs.retro_style._menu_transparency == 0.6

def test_coop_uses_dedicated_dense_background_layer(monkeypatch):
    captured_calls = []

    class _Layer:
        def __init__(self):
            self.opacity = None

        def set_opacity_multiplier(self, value):
            self.opacity = float(value)

    layer = _Layer()

    def _fake_get_shared_layer(name='default', **kwargs):
        captured_calls.append((name, kwargs))
        return layer

    monkeypatch.setattr(coop_game_module, 'get_shared_falling_blocks_layer', _fake_get_shared_layer)

    settings = _FakeSettings(values={'effects_opacity': 0.6})
    cg = CoopGame(
        sound_enabled=False,
        effects_enabled=True,
        screen=_Surf(),
        settings_manager=settings,
        sound_manager=_SM(),
    )

    assert cg.falling_blocks is layer
    assert captured_calls
    assert all(name == 'coop' for name, _kwargs in captured_calls)
    assert all(kwargs.get('block_count') == CoopGame._BACKGROUND_LAYER_BLOCK_COUNT for _name, kwargs in captured_calls)
    assert layer.opacity == 0.6

def test_draw_pending_line_clear_rows_uses_snapshot_colors():
    cg = CoopGame(sound_enabled=False, effects_enabled=True, screen=_Surf(), sound_manager=_SM())
    snapshot_color = (12, 34, 56)
    cg.line_clear_sweep_active = True
    cg.line_clear_sweep_progress = 0.0
    cg.line_clear_sweep_rows = [0]
    cg.line_clear_pending_rows = [0]
    cg.line_clear_pending_colors = {0: [snapshot_color for _ in range(cg.board.width)]}

    draw_calls = []
    cg.draw_textured_block = lambda x, y, size, color, texture_surface=None, texture_slice=None: draw_calls.append(color)

    cg._draw_pending_line_clear_rows(0, 0, 10, cg.board.width * 10)

    assert len(draw_calls) == cg.board.width
    assert all(color == snapshot_color for color in draw_calls)

def test_coop_line_sweep_timing_uses_balanced_board_width_reference():
    cg = CoopGame(sound_enabled=False, effects_enabled=True, screen=_Surf(), sound_manager=_SM())
    cg.cell_size = 40
    cg.line_clear_sweep_active = True
    cg.line_clear_sweep_progress = 0.0
    cg.line_clear_sweep_rows = [19]
    sweep_width = cg._get_line_sweep_length_px(cg.cell_size, len(cg.line_clear_sweep_rows))

    cg._update_line_clear_effects(100.0)

    reference_travel = cg._LINE_CLEAR_SWEEP_REFERENCE_BOARD_WIDTH * cg.cell_size + sweep_width
    full_coop_travel = cg.board.width * cg.cell_size + sweep_width
    too_fast_single_board_travel = 10 * cg.cell_size + sweep_width
    expected_progress = 0.1 * (
        cg._LINE_CLEAR_SWEEP_BLOCK_FALL_SPEED * 3600.0 / reference_travel
    )
    old_full_width_progress = 0.1 * (
        cg._LINE_CLEAR_SWEEP_BLOCK_FALL_SPEED * 3600.0 / full_coop_travel
    )
    too_fast_single_board_progress = 0.1 * (
        cg._LINE_CLEAR_SWEEP_BLOCK_FALL_SPEED * 3600.0 / too_fast_single_board_travel
    )

    assert abs(cg.line_clear_sweep_progress - expected_progress) < 0.0001
    assert old_full_width_progress < cg.line_clear_sweep_progress < too_fast_single_board_progress

def test_coop_block_fall_animation_uses_per_row_clear_distance():
    cg = CoopGame(sound_enabled=False, effects_enabled=True, screen=_Surf(), sound_manager=_SM())
    cg.cell_size = 20

    for y, x in ((6, 0), (7, 1), (11, 2)):
        cg.board.occupancy[y][x] = True
        cg.board.grid[y][x] = (10 + y, 20 + x, 30)
        cg.board.owners[y][x] = 'P1'

    cg._start_block_fall_animation([5, 10])

    assert cg._get_block_fall_offset(6, 0) == -40.0
    assert cg._get_block_fall_offset(7, 1) == -20.0
    assert cg._get_block_fall_offset(11, 2) == 0.0

    cg.line_clear_sweep_active = False
    cg._update_falling_block_animations(1000.0)

    assert cg.falling_block_animations == []

def test_draw_locked_blocks_applies_falling_block_animation_offset():
    cg = CoopGame(sound_enabled=False, effects_enabled=True, screen=_Surf(), sound_manager=_SM())
    cg.board.occupancy[6][0] = True
    cg.board.grid[6][0] = (12, 34, 56)
    cg.falling_block_animations = [{
        'row': 6,
        'col': 0,
        'current_offset': -20.0,
        'target_offset': 0.0,
        'sweep_trigger': 0.0,
        'started': True,
    }]
    draw_calls = []
    cg.draw_textured_block = lambda x, y, size, color, texture_surface=None, texture_slice=None: draw_calls.append((x, y, color))

    cg._draw_locked_blocks(0, 0, 10)

    assert draw_calls == [(1, 41, (12, 34, 56))]

def test_side_panels_draw_player_specific_hold_on_both_sides_below_next_panels():
    cg = CoopGame(sound_enabled=False, effects_enabled=False, screen=_Surf(), sound_manager=_SM())
    cg.p1_hold_piece = Piece(x=0, y=0, shape_index=0)
    cg.p2_hold_piece = Piece(x=0, y=0, shape_index=1)
    cg._apply_block_style(cg.p1_hold_piece)
    cg._apply_block_style(cg.p2_hold_piece)
    cg._calculate_layout()

    preview_calls = []
    cg._draw_piece_preview = lambda piece, x, y, cs, label, panel_width=None: preview_calls.append((label, x, y, panel_width, piece))

    cg._draw_side_panels(cg.board_offset_x, cg.board_offset_y, cg.cell_size, cg.board.width * cg.cell_size, cg.board.height * cg.cell_size)

    by_label = {label: (x, y, panel_width, piece) for label, x, y, panel_width, piece in preview_calls}
    p1_next_label = 'P1 NEXT'
    p2_next_label = 'P2 NEXT'
    assert p1_next_label in by_label
    assert p2_next_label in by_label
    p1_hold_label = 'P1 Hold (E)'
    p2_hold_label = 'P2 Hold (RShift)'
    assert p1_hold_label in by_label
    assert p2_hold_label in by_label
    assert by_label[p1_hold_label][0] == by_label[p1_next_label][0]
    assert by_label[p2_hold_label][0] == by_label[p2_next_label][0]
    assert by_label[p1_hold_label][1] > by_label[p1_next_label][1]
    assert by_label[p2_hold_label][1] > by_label[p2_next_label][1]
    assert by_label[p1_hold_label][2] == by_label[p1_next_label][2]
    assert by_label[p2_hold_label][2] == by_label[p2_next_label][2]
    assert by_label[p1_hold_label][3] is cg.p1_hold_piece
    assert by_label[p2_hold_label][3] is cg.p2_hold_piece

def test_side_panels_hold_labels_follow_custom_bindings():
    settings = _FakeSettings({
        'pvp': {
            'player1': {'hold': 111},
            'player2': {'hold': 222},
        }
    })
    cg = CoopGame(
        sound_enabled=False,
        effects_enabled=False,
        screen=_Surf(),
        settings_manager=settings,
        sound_manager=_SM(),
    )
    cg.p1_hold_piece = Piece(x=0, y=0, shape_index=0)
    cg.p2_hold_piece = Piece(x=0, y=0, shape_index=1)
    cg._apply_block_style(cg.p1_hold_piece)
    cg._apply_block_style(cg.p2_hold_piece)
    cg._calculate_layout()

    original_name = _pg.key.name
    _pg.key.name = staticmethod(lambda k: {111: 'o', 222: 'right shift'}.get(k, original_name(k)))
    preview_calls = []
    cg._draw_piece_preview = lambda piece, x, y, cs, label, panel_width=None: preview_calls.append((label, piece))
    try:
        cg._draw_side_panels(cg.board_offset_x, cg.board_offset_y, cg.cell_size, cg.board.width * cg.cell_size, cg.board.height * cg.cell_size)
    finally:
        _pg.key.name = original_name

    labels = {label: piece for label, piece in preview_calls}
    assert 'P1 Hold (O)' in labels
    assert 'P2 Hold (RShift)' in labels
    assert labels['P1 Hold (O)'] is cg.p1_hold_piece
    assert labels['P2 Hold (RShift)'] is cg.p2_hold_piece


def test_coop_layout_can_grow_beyond_legacy_large_display_caps():
    cg = CoopGame(sound_enabled=False, effects_enabled=False, screen=_SizedSurf(2560, 1440), sound_manager=_SM())
    cg.window_width = 1366
    cg.window_height = 768
    cg._layout_key = None

    cg._calculate_layout()

    assert cg.cell_size > 40
    assert cg._side_panel_width > 120
    assert cg.board_offset_x > 0
    assert cg.board_offset_x + (cg.board.width * cg.cell_size) < 2560


def test_coop_layout_projects_effective_retina_metrics_into_raw_surface():
    cg = CoopGame(sound_enabled=False, effects_enabled=False, screen=_SizedSurf(2940, 1912), sound_manager=_SM())
    cg.window_width = 1470
    cg.window_height = 956
    cg._layout_key = None

    original_resolve = coop_game_module.resolve_ui_scale_size
    coop_game_module.resolve_ui_scale_size = lambda screen_or_size, *, use_effective_display_size=False, display_surface=None: (1470, 956)
    try:
        cg._calculate_layout()
    finally:
        coop_game_module.resolve_ui_scale_size = original_resolve

    assert cg.cell_size >= 80
    assert cg._side_panel_width >= 200
    assert cg.board_offset_x + (cg.board.width * cg.cell_size) < 2940

def test_score_contribution_texts_match_bottom_hud_and_game_over_summary():
    cg = CoopGame(sound_enabled=False, effects_enabled=False, screen=_Surf(), sound_manager=_SM())
    cg.p1_score_contribution = 460
    cg.p2_score_contribution = 680
    cg.p1_score_contribution_pct = 40
    cg.p2_score_contribution_pct = 60

    p1_txt, p2_txt = cg._score_contribution_texts()

    assert p1_txt == 'P1 460 (%40)'
    assert p2_txt == 'P2 680 (%60)'

def test_hold_label_does_not_include_legacy_c_hint_text():
    cg = CoopGame(sound_enabled=False, effects_enabled=False, screen=_Surf(), sound_manager=_SM())

    assert cg._hold_label('P1') == 'P1 Hold (E)'
    assert '(C)' not in cg._hold_label('P1')

def test_game_over_summary_renders_same_score_contribution_text_as_hud():
    cg = CoopGame(sound_enabled=False, effects_enabled=False, screen=_Surf(), sound_manager=_SM())
    cg.game_over = True
    cg.team_score = 1140
    cg.total_lines_cleared = 6
    cg.elapsed_time = 134000
    cg.p1_score_contribution = 460
    cg.p2_score_contribution = 680
    cg.p1_score_contribution_pct = 40
    cg.p2_score_contribution_pct = 60

    rendered_texts = []

    class _RecordingFont(_FakeFont):
        def render(self, text, *a, **kw):
            rendered_texts.append(text)
            return _Surf()

    original_get_font = _rs.retro_style.get_font
    original_get_fitting_font = _rs.retro_style.get_fitting_font
    _rs.retro_style.get_font = lambda *a, **kw: _RecordingFont()
    _rs.retro_style.get_fitting_font = lambda *a, **kw: _RecordingFont()
    try:
        cg._draw_game_over_screen()
    finally:
        _rs.retro_style.get_font = original_get_font
        _rs.retro_style.get_fitting_font = original_get_fitting_font

    assert 'P1 460 (%40)' in rendered_texts
    assert 'P2 680 (%60)' in rendered_texts

def test_draw_no_crash():
    """draw() çağrıldığında hata atmamalı."""
    cg = CoopGame(sound_enabled=False, effects_enabled=False, screen=_Surf(), sound_manager=_SM())
    cg.draw()  # raise etmemeli

def test_update_no_crash():
    """update() çağrıldığında hata atmamalı."""
    cg = CoopGame(sound_enabled=False, effects_enabled=False, screen=_Surf(), sound_manager=_SM())
    cg.update(16.0)  # 16ms frame
    cg.update(16.0)

def test_wants_mouse_visible_for_pause_and_game_over():
    cg = CoopGame(sound_enabled=False, effects_enabled=False, screen=_Surf(), sound_manager=_SM())

    assert cg.wants_mouse_visible() is False

    cg.paused = True
    assert cg.wants_mouse_visible() is True

    cg.paused = False
    cg.game_over = True
    assert cg.wants_mouse_visible() is True


def test_game_over_ignores_gamepad_mouse_click():
    cg = CoopGame(sound_enabled=False, effects_enabled=False, screen=_Surf(), sound_manager=_SM())
    cg.game_over = True
    cg._game_over_peek_active = False
    cg._game_over_peek_rect = None

    class _HitRect:
        def collidepoint(self, pos):
            return True

    restart_calls = []
    cg._game_over_restart_rect = _HitRect()
    cg._game_over_exit_rect = _HitRect()
    cg.restart = lambda: restart_calls.append(True)

    original_get = _pg.event.get
    _pg.event.get = lambda: [types.SimpleNamespace(type=_pg.MOUSEBUTTONDOWN, button=1, pos=(10, 10), from_gamepad=True)]
    try:
        cg.handle_input()
    finally:
        _pg.event.get = original_get

    assert restart_calls == []


def test_coop_spawn_halt_blocks_respawn_until_toggled_off():
    settings = _FakeSettings(
        controls={'debug': {'coop_spawner_left': _pg.K_h}},
        values={'coop_debug_halt_blocks': True},
    )
    cg = CoopGame(
        sound_enabled=False,
        effects_enabled=False,
        screen=_Surf(),
        settings_manager=settings,
        sound_manager=_SM(),
    )

    cg._p1_spawn_halted = True
    expected_piece = cg.p1_next_piece

    cg._hard_drop('P1')

    assert cg.p1_current_piece is None

    cg._toggle_player_spawner_halt('P1')

    assert cg.p1_current_piece is expected_piece
    assert cg._p1_spawn_halted is False
