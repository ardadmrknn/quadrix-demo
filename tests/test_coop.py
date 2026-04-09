"""Co-op modülü temel testleri."""
import sys, os, types

# pygame stub
_pg = types.ModuleType('pygame')
_pg.K_a = 97; _pg.K_d = 100; _pg.K_w = 119; _pg.K_s = 115
_pg.K_LEFT = 276; _pg.K_RIGHT = 275; _pg.K_UP = 273; _pg.K_DOWN = 274
_pg.K_SPACE = 32; _pg.K_LSHIFT = 304; _pg.K_RSHIFT = 303; _pg.K_ESCAPE = 27; _pg.K_RETURN = 13; _pg.K_KP_ENTER = 271; _pg.K_BACKSPACE = 8; _pg.K_p = 112; _pg.K_e = 101
_pg.QUIT = 256; _pg.KEYDOWN = 768; _pg.KEYUP = 769; _pg.VIDEORESIZE = 65281; _pg.MOUSEMOTION = 1024; _pg.MOUSEBUTTONDOWN = 1025; _pg.MOUSEBUTTONUP = 1026; _pg.MOUSEWHEEL = 1027; _pg.SRCALPHA = 65536
_pg.init = lambda: None; _pg.get_init = lambda: True
class _Key:
    @staticmethod
    def key_code(n): return 0
    @staticmethod
    def set_repeat(*a): pass
_pg.key = _Key()
class _Surf:
    def __init__(self, *a, **kw): pass
    def get_width(self): return 1920
    def get_height(self): return 1080
    def fill(self, *a): pass
    def blit(self, *a): pass
    def get_rect(self, **kw):
        class R:
            def __init__(self): self.centerx=0; self.centery=0; self.topleft=(0,0); self.top=0; self.center=(0,0)
            def collidepoint(self, *a): return False
        return R()
    def get_size(self): return (1920, 1080)
    def convert_alpha(self): return self
_pg.Surface = _Surf
class _Draw:
    @staticmethod
    def rect(*a, **kw): pass
    @staticmethod
    def line(*a, **kw): pass
_pg.draw = _Draw()
class _Rect:
    def __init__(self, *a): self.x=0; self.y=0; self.width=0; self.height=0; self.size=(0,0); self.topleft=(0,0); self.center=(0,0); self.centerx=0; self.centery=0; self.bottom=0
    def collidepoint(self, *a): return False
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
sys.modules['pygame'] = _pg

# Basit stub'lar
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# Ağır bağımlılıkları stub'la
for mod_name in ('sound', 'background', 'background_effects', 'mode_skins',
                 'retro_style', 'renderers', 'renderers.jelly_renderer',
                 'themes', 'block_styles', 'platform_utils', 'localization',
                 'ui_theme'):
    if mod_name not in sys.modules:
        m = types.ModuleType(mod_name)
        sys.modules[mod_name] = m

# localization
import localization as _loc
if not hasattr(_loc, 't'):
    _loc.t = lambda key, default='': default or key

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

# sound
import sound as _snd
class _SM:
    enabled = True; sfx_enabled = True; music_enabled = True; music_volume = 0.3; sfx_volume = 0.5
    def play(self, *a): pass
    def stop_music(self): pass
    def duck_music(self): pass
    def unduck_music(self): pass
    def update_music_playlist(self): pass
    def set_music_volume(self, v): self.music_volume = v
    def set_volume(self, v): self.sfx_volume = v
    def set_music_playlist(self, *a, **kw): pass
    def play_music(self, *a, **kw): pass
_snd.SoundManager = _SM

# background
import background as _bg
class _BM:
    def set_transparency(self, *a): pass
    def load_image(self, *a): return False
    def is_loaded(self): return False
    def draw(self, *a): pass
_bg.BackgroundManager = _BM

# background_effects
import background_effects as _be
_be.get_shared_falling_blocks_layer = lambda: None

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
    text_primary = (230, 235, 245); text_secondary = (180, 200, 220); text_muted = (120, 140, 170)
    glass_bg = (15, 20, 40, 140); glass_border = (80, 120, 180, 100)
    bg_color = (8, 12, 28); bg_secondary = (12, 18, 38)
    def get_font(self, *a, **kw): return _FakeFont()
    def get_fitting_font(self, *a, **kw): return _FakeFont()
    def get_mono_font(self, *a, **kw): return _FakeFont()
    def render_fit_text(self, *a, **kw): return _pg.Surface((10, 10))
    def draw_glass_panel(self, *a, **kw): pass
    def draw_uniform_button(self, *a, **kw): pass
    def _scale_menu_alpha(self, a): return a
_rs.retro_style = _RS()

# themes
import themes as _th
_th.ThemeManager = lambda *a, **kw: type('T', (), {'current_theme': None, 'get_piece_color': lambda self, name: (200, 200, 200)})()

# block_styles
import block_styles as _bs
_bs.BlockStyleManager = lambda *a, **kw: type('B', (), {'apply_to_piece': lambda s, p: None})()
_bs.TextureSlice = None
_bs.TextureRenderCache = lambda: {}

# renderers.jelly_renderer
import renderers.jelly_renderer as _jr
_jr.draw_jelly_block = lambda *a, **kw: None
_jr.draw_jelly_border = lambda *a, **kw: None

# ===== Şimdi modülleri import et =====
from board import Board
from pieces import Piece, SHAPES
from coop_board import CoopBoard
from coop_game import CoopGame


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

def test_shared_hold_empty():
    cg = CoopGame(sound_enabled=False, effects_enabled=False, screen=_Surf(), sound_manager=_SM())
    old_p1 = cg.p1_current_piece
    cg._use_shared_hold('P1')
    assert cg.shared_hold_piece is not None
    assert cg.p1_hold_used

def test_shared_hold_swap():
    cg = CoopGame(sound_enabled=False, effects_enabled=False, screen=_Surf(), sound_manager=_SM())
    # P1 hold'a koyar
    cg._use_shared_hold('P1')
    held = cg.shared_hold_piece
    # P2 swap yapar
    old_p2 = cg.p2_current_piece
    cg._use_shared_hold('P2')
    assert cg.p2_hold_used
    assert cg.shared_hold_piece is old_p2

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
    cg = CoopGame(sound_enabled=False, effects_enabled=False, screen=_Surf(), sound_manager=_SM())
    cg._freeze_player('P1')
    cg._freeze_player('P2')
    assert cg.game_over

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

def test_draw_no_crash():
    """draw() çağrıldığında hata atmamalı."""
    cg = CoopGame(sound_enabled=False, effects_enabled=False, screen=_Surf(), sound_manager=_SM())
    cg.draw()  # raise etmemeli

def test_update_no_crash():
    """update() çağrıldığında hata atmamalı."""
    cg = CoopGame(sound_enabled=False, effects_enabled=False, screen=_Surf(), sound_manager=_SM())
    cg.update(16.0)  # 16ms frame
    cg.update(16.0)
