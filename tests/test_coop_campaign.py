"""Co-op Kampanya sistemi testleri.

Level verisi, objective'ler, progress yönetimi, campaign mode davranışları.
"""
import sys, os, types

# pygame stub (test_coop.py ile aynı pattern)
_pg = types.ModuleType('pygame')
_pg.K_a = 97; _pg.K_d = 100; _pg.K_w = 119; _pg.K_s = 115
_pg.K_LEFT = 276; _pg.K_RIGHT = 275; _pg.K_UP = 273; _pg.K_DOWN = 274
_pg.K_SPACE = 32; _pg.K_LSHIFT = 304; _pg.K_RSHIFT = 303; _pg.K_ESCAPE = 27
_pg.K_RETURN = 13; _pg.K_KP_ENTER = 271; _pg.K_BACKSPACE = 8; _pg.K_p = 112
_pg.K_e = 101; _pg.K_r = 114
_pg.QUIT = 256; _pg.KEYDOWN = 768; _pg.KEYUP = 769; _pg.VIDEORESIZE = 65281
_pg.MOUSEMOTION = 1024; _pg.MOUSEBUTTONDOWN = 1025; _pg.MOUSEBUTTONUP = 1026
_pg.MOUSEWHEEL = 1027; _pg.SRCALPHA = 65536
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
    @staticmethod
    def circle(*a, **kw): pass
    @staticmethod
    def polygon(*a, **kw): pass
    @staticmethod
    def lines(*a, **kw): pass
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
        self.w=self.width; self.h=self.height
        self.size=(self.width,self.height)
        self.topleft=(self.x,self.y)
        self.top=self.y; self.left=self.x
        self.right=self.x + self.width
        self.bottom=self.y + self.height
        self.center=(self.x + self.width // 2, self.y + self.height // 2)
        self.centerx=self.center[0]; self.centery=self.center[1]
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
    def get_pos(): return (0, 0)
_pg.mouse = _Mouse()
class _Time:
    @staticmethod
    def get_ticks(): return 0
_pg.time = _Time()

_pg.event = types.ModuleType('pygame.event')
_pg.event.get = lambda: []

sys.modules['pygame'] = _pg
sys.modules['pygame.event'] = _pg.event

# src path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# Stub heavy dependencies
for mod_name in ('sound', 'background', 'background_effects', 'mode_skins',
                 'retro_style', 'renderers', 'renderers.jelly_renderer',
                 'themes', 'block_styles', 'platform_utils', 'localization',
                 'ui_theme', 'sweep_effects', 'asset_manager'):
    if mod_name not in sys.modules:
        m = types.ModuleType(mod_name)
        sys.modules[mod_name] = m

# localization stub
import localization as _loc
if not hasattr(_loc, 't'):
    _loc.t = lambda key, default='', **kw: default or key
if not hasattr(_loc, 'get_language'):
    _loc.get_language = lambda: 'en'

# ui_theme stub
import ui_theme as _ut
class _FakeFont:
    def render(self, *a, **kw): return _Surf()
    def size(self, t): return (len(t)*8, 16)
    def get_height(self): return 16
    def get_linesize(self): return 18
class _UIFonts:
    @staticmethod
    def get(sz): return _FakeFont()
class _UIColors:
    BG_DARK = (10, 10, 20)
    BG_MEDIUM = (20, 25, 45)
    NEON_CYAN = (0, 240, 255)
    NEON_GOLD = (255, 210, 0)
    NEON_RED = (255, 50, 80)
class _UIStyle:
    pass
_ut.UIFonts = _UIFonts
_ut.UIColors = _UIColors
_ut.UIStyle = _UIStyle

# platform_utils stub
import platform_utils as _pu
_pu.create_display = lambda *a, **kw: _Surf()
_pu.normalize_mouse_pos = lambda pos: pos
_pu.get_mouse_pos = lambda: (0, 0)
_pu.set_app_icon = lambda: None

# sound stub
import sound as _snd
class _SM:
    enabled = True; sfx_enabled = True; music_enabled = True; music_volume = 0.3; sfx_volume = 0.5
    def __init__(self): self.game_over_sequence_calls = 0
    def play(self, *a): pass
    def stop_music(self): pass
    def duck_music(self): pass
    def unduck_music(self): pass
    def update_music_playlist(self): pass
    def set_music_volume(self, v): self.music_volume = v
    def set_volume(self, v): self.sfx_volume = v
    def set_music_playlist(self, *a, **kw): pass
    def play_music(self, *a, **kw): pass
    current_track_name = 'main_1'
    def play_game_over_sequence(self): self.game_over_sequence_calls += 1
_snd.SoundManager = _SM

# background / background_effects / mode_skins / retro_style / themes / block_styles stubs
import background as _bg
class _BM:
    def set_transparency(self, *a): pass
    def load_image(self, *a): return False
    def is_loaded(self): return False
    def draw(self, *a): pass
    def draw_full_screen(self, *a): pass
_bg.BackgroundManager = _BM

import background_effects as _be
_ORIGINAL_SHARED_FALLING_LAYER_GETTER = getattr(_be, 'get_shared_falling_blocks_layer', None)
_be.get_shared_falling_blocks_layer = lambda: None

import mode_skins as _ms
class _Skin:
    outer_bg = (0,0,0); grid_color = (50,50,80)
_ms.apply_board_tint = lambda *a: None
_ms.apply_outer_tint = lambda *a: None
_ms.draw_board_overlay = lambda *a: None
_ms.get_mode_skin = lambda *a: _Skin()
_ms.get_localized_skin_title = lambda *a: ''
_ms.get_localized_skin_subtitle = lambda *a: ''

import retro_style as _rs
class _RS:
    primary = (0, 255, 221); accent = (255, 165, 0); secondary = (255, 0, 255)
    success = (60, 200, 120)
    text_primary = (230, 235, 245); text_secondary = (180, 200, 220); text_muted = (120, 140, 170)
    glass_bg = (15, 20, 40, 140); glass_border = (80, 120, 180, 100)
    bg_color = (8, 12, 28); bg_secondary = (12, 18, 38)
    def get_font(self, *a, **kw): return _FakeFont()
    def get_fitting_font(self, *a, **kw): return _FakeFont()
    def get_mono_font(self, *a, **kw): return _FakeFont()
    def render_fit_text(self, *a, **kw): return _pg.Surface((10, 10))
    def draw_glass_panel(self, *a, **kw): pass
    def draw_uniform_button(self, *a, **kw): pass
    def draw_volume_bar(self, *a, **kw): pass
    def _scale_menu_alpha(self, a): return a
_rs.retro_style = _RS()

import themes as _th
_th.ThemeManager = lambda *a, **kw: type('T', (), {'current_theme': None, 'get_piece_color': lambda self, name: (200, 200, 200)})()

import block_styles as _bs
_bs.BlockStyleManager = lambda *a, **kw: type('B', (), {
    'apply_to_piece': lambda s, p, *a2, **kw2: None,
    'get_texture_surface': lambda s, name: None,
    'get_slice_bounds': lambda s, name: {'x': 0.0, 'y': 0.0, 'w': 1.0, 'h': 1.0},
})()
_bs.TextureSlice = None
_bs.TextureRenderCache = lambda: {}

import renderers.jelly_renderer as _jr
_jr.draw_jelly_block = lambda *a, **kw: None
_jr.draw_jelly_border = lambda *a, **kw: None

# sweep_effects stub
import sweep_effects as _se
if not hasattr(_se, 'SweepCatState'):
    class _SCS: pass
    _se.SweepCatState = _SCS
if not hasattr(_se, 'draw_rainbow_cat_sweep'):
    _se.draw_rainbow_cat_sweep = lambda *a, **kw: None

# asset_manager stub
import asset_manager as _am
if not hasattr(_am, 'load_image'):
    _am.load_image = lambda *a, **kw: _Surf()

# ====== Pre-register campaign package to bypass heavy __init__.py ======
# campaign/__init__.py imports CampaignMode → game.py → many heavy deps.
# We register campaign as an empty package, then import submodules directly.
import importlib
_campaign_pkg = types.ModuleType('campaign')
_campaign_pkg.__path__ = [os.path.join(os.path.dirname(__file__), '..', 'src', 'campaign')]
_campaign_pkg.__package__ = 'campaign'
sys.modules['campaign'] = _campaign_pkg

# ====== Imports (submodules via relative imports work because package is registered) ======
from campaign.coop_level_data import (
    get_coop_level, get_coop_world_levels,
    TOTAL_COOP_LEVELS, COOP_WORLDS, CoopLevelConfig,
)
# coop_objectives needs campaign.objectives — import objectives first
from campaign import objectives as _objectives_mod
from campaign.coop_objectives import (
    create_coop_objective,
    SharedHoldObjective,
    BalancedContributionObjective,
    FreezeRecoveryObjective,
    CoopComboObjective,
)

if _ORIGINAL_SHARED_FALLING_LAYER_GETTER is None:
    try:
        delattr(_be, 'get_shared_falling_blocks_layer')
    except AttributeError:
        pass
else:
    _be.get_shared_falling_blocks_layer = _ORIGINAL_SHARED_FALLING_LAYER_GETTER


# =====================================================================
# Level Data testleri
# =====================================================================

def test_total_levels_count():
    """20 co-op level tanımlı olmalı."""
    assert TOTAL_COOP_LEVELS == 20

def test_worlds_count():
    assert COOP_WORLDS == 2

def test_all_levels_load():
    """Her level numarası geçerli bir config döndürmeli."""
    for i in range(1, TOTAL_COOP_LEVELS + 1):
        cfg = get_coop_level(i)
        assert cfg is not None, f"Level {i} yüklenemedi"
        assert isinstance(cfg, CoopLevelConfig)
        assert cfg.level == i

def test_invalid_level_returns_none():
    assert get_coop_level(0) is None
    assert get_coop_level(99) is None

def test_world_levels():
    w1 = get_coop_world_levels(1)
    w2 = get_coop_world_levels(2)
    assert len(w1) == 10
    assert len(w2) == 10
    assert all(c.world == 1 for c in w1)
    assert all(c.world == 2 for c in w2)

def test_level_has_name():
    for i in range(1, TOTAL_COOP_LEVELS + 1):
        cfg = get_coop_level(i)
        assert 'tr' in cfg.name or 'en' in cfg.name

def test_speed_progression():
    """Genel olarak speed düşmeli (hızlanmalı)."""
    speeds = [get_coop_level(i).speed for i in range(1, TOTAL_COOP_LEVELS + 1)]
    assert speeds[0] >= speeds[-1]

def test_boss_levels():
    """Level 10 ve 20 boss olmalı."""
    assert get_coop_level(10).is_boss
    assert get_coop_level(20).is_boss

def test_no_hold_levels():
    """Level 5 ve 15 no_hold olmalı."""
    assert get_coop_level(5).no_hold
    assert get_coop_level(15).no_hold

def test_all_levels_have_star_conditions():
    for i in range(1, TOTAL_COOP_LEVELS + 1):
        cfg = get_coop_level(i)
        assert 1 in cfg.stars, f"Level {i} 1. yıldız koşulu eksik"

def test_objectives_not_empty():
    for i in range(1, TOTAL_COOP_LEVELS + 1):
        cfg = get_coop_level(i)
        assert len(cfg.objectives) > 0, f"Level {i} görev listesi boş"


# =====================================================================
# Objective testleri
# =====================================================================

def test_create_clear_lines_objective():
    obj = create_coop_objective({'type': 'clear_lines', 'target': 10})
    assert obj is not None
    assert not obj.completed
    assert obj.target == 10

def test_create_score_objective():
    obj = create_coop_objective({'type': 'score', 'target': 1000})
    assert obj.target == 1000

def test_create_tetris_objective():
    obj = create_coop_objective({'type': 'tetris', 'target': 2})
    assert obj.target == 2

def test_create_shared_hold_objective():
    obj = create_coop_objective({'type': 'shared_hold', 'target': 3})
    assert isinstance(obj, SharedHoldObjective)
    assert obj.target == 3

def test_create_balanced_objective():
    obj = create_coop_objective({'type': 'balanced', 'target': 100, 'min_pct': 35})
    assert isinstance(obj, BalancedContributionObjective)
    assert obj.min_pct == 35

def test_create_freeze_recovery_objective():
    obj = create_coop_objective({'type': 'freeze_recovery', 'target': 2})
    assert isinstance(obj, FreezeRecoveryObjective)
    assert obj.target == 2

def test_create_combo_objective():
    obj = create_coop_objective({'type': 'combo', 'target': 4})
    assert isinstance(obj, CoopComboObjective)
    assert obj.target == 4


def test_shared_hold_objective_tracking():
    obj = SharedHoldObjective(target=2)
    assert not obj.completed
    obj.update(None, 'hold_used', {'player': 'P1'})
    assert obj.progress == 1
    assert not obj.completed
    obj.update(None, 'hold_used', {'player': 'P2'})
    assert obj.progress == 2
    assert obj.completed

def test_shared_hold_ignores_other_events():
    obj = SharedHoldObjective(target=2)
    obj.update(None, 'lines_cleared', {'lines': 1})
    assert obj.progress == 0

def test_combo_objective_tracking():
    obj = CoopComboObjective(target=3)
    obj.update(None, 'lines_cleared', {})
    assert obj.progress == 1
    obj.update(None, 'lines_cleared', {})
    assert obj.progress == 2
    obj.update(None, 'lines_cleared', {})
    assert obj.progress == 3
    assert obj.completed


def test_combo_objective_resets_on_no_clear():
    """Satır temizlemeden parça yerleştirilince combo sıfırlanmalı."""
    obj = CoopComboObjective(target=3)
    # İlk parça + temizleme → combo 1
    obj.update(None, 'piece_placed', {})
    obj.update(None, 'lines_cleared', {})
    assert obj._consecutive == 1
    # İkinci parça + temizleme → combo 2
    obj.update(None, 'piece_placed', {})
    obj.update(None, 'lines_cleared', {})
    assert obj._consecutive == 2
    assert obj.progress == 2
    # Üçüncü parça: temizleme YOK → combo devam eder (piece_placed henüz kontrol etmez)
    obj.update(None, 'piece_placed', {})
    assert obj._consecutive == 2  # henüz reset yok
    # Dördüncü parça: önceki piece_placed temizleme gelmediği için combo sıfırlanır
    obj.update(None, 'piece_placed', {})
    assert obj._consecutive == 0
    # En iyi combo 2 olarak kalmalı
    assert obj.progress == 2


def test_balanced_contribution_needs_minimum_cells():
    """Yeterli veri olmadan balanced objective tamamlanmamalı."""
    obj = BalancedContributionObjective(min_pct=30)
    game = types.SimpleNamespace(
        p1_total_cells=5, p2_total_cells=5,
        p1_contribution_pct=50, p2_contribution_pct=50,
        total_lines_cleared=10,
    )
    obj.update(game, 'lines_cleared', {})
    assert not obj.completed  # total_cells < 20

def test_balanced_contribution_completes():
    obj = BalancedContributionObjective(min_pct=30)
    game = types.SimpleNamespace(
        p1_total_cells=15, p2_total_cells=15,
        p1_contribution_pct=50, p2_contribution_pct=50,
        total_lines_cleared=10,
    )
    obj.update(game, 'lines_cleared', {})
    assert obj.completed

def test_balanced_contribution_fails_with_imbalance():
    obj = BalancedContributionObjective(min_pct=40)
    game = types.SimpleNamespace(
        p1_total_cells=18, p2_total_cells=12,
        p1_contribution_pct=60, p2_contribution_pct=40,
        total_lines_cleared=10,
    )
    obj.update(game, 'lines_cleared', {})
    assert obj.completed  # 40 >= 40 boundary case

    obj2 = BalancedContributionObjective(min_pct=45)
    obj2.update(game, 'lines_cleared', {})
    assert not obj2.completed  # 40 < 45

def test_freeze_recovery_objective():
    obj = FreezeRecoveryObjective(target=1)
    # Simülasyon: freeze oldu
    obj.update(None, 'player_frozen', {'player': 'P1'})
    # Simülasyon: unfreeze oldu (lines_cleared ile)
    game = types.SimpleNamespace(p1_frozen=False, p2_frozen=False,
                                  _p1_pending_unfreeze=False, _p2_pending_unfreeze=False)
    obj.update(game, 'lines_cleared', {})
    assert obj.completed


def test_factory_all_level_objectives_valid():
    """Tüm level'lardaki görevler oluşturulabilmeli."""
    for i in range(1, TOTAL_COOP_LEVELS + 1):
        cfg = get_coop_level(i)
        for obj_config in cfg.objectives:
            obj = create_coop_objective(obj_config)
            assert obj is not None, f"Level {i} görev oluşturulamadı: {obj_config}"


# =====================================================================
# CoopCampaignMode testleri (lightweight — init ve progress)
# =====================================================================

class _FakeSettingsManager:
    """Test için minimal settings manager."""
    def __init__(self):
        self._store = {}
    def get(self, key, default=None):
        return self._store.get(key, default)
    def set(self, key, value):
        self._store[key] = value
    def save(self):
        pass


class _FakeUserManager:
    """Test için minimal co-op progress taşıyıcısı."""

    def __init__(self):
        self._coop_campaign_progress = {}

    def get_coop_campaign_progress(self, username=None):
        return self._coop_campaign_progress

    def save_coop_campaign_progress(self, progress, username=None):
        self._coop_campaign_progress = dict(progress or {})


def test_campaign_mode_import():
    """CoopCampaignMode import edilebilmeli."""
    from campaign.coop_campaign_mode import CoopCampaignMode
    assert CoopCampaignMode is not None


def test_campaign_mode_star_conditions():
    """Yıldız koşul kontrol metodu doğru çalışmalı."""
    from campaign.coop_campaign_mode import CoopCampaignMode
    # CoopCampaignMode'u __new__ ile oluştur (CoopGame init'ini atla)
    mode = object.__new__(CoopCampaignMode)
    mode.objectives = []
    mode.team_score = 1500
    mode.tetris_count = 2
    mode.total_combos = 5
    mode.elapsed_time = 60000  # 60 saniye
    mode.level_complete = True
    mode.p1_total_cells = 50
    mode.p2_total_cells = 50
    mode.p1_contribution_pct = 50
    mode.p2_contribution_pct = 50

    # Tüm görevler tamamlanmış mockla
    class _MockObj:
        completed = True
    mode.objectives = [_MockObj()]

    assert mode._is_star_condition_met({'type': 'complete'})
    assert mode._is_star_condition_met({'type': 'score', 'value': 1000})
    assert not mode._is_star_condition_met({'type': 'score', 'value': 2000})
    assert mode._is_star_condition_met({'type': 'tetris', 'value': 1})
    assert not mode._is_star_condition_met({'type': 'tetris', 'value': 5})
    assert mode._is_star_condition_met({'type': 'time_limit', 'value': 90})
    assert not mode._is_star_condition_met({'type': 'time_limit', 'value': 30})
    assert mode._is_star_condition_met({'type': 'combo', 'value': 3})
    assert mode._is_star_condition_met({'type': 'balanced', 'value': 40})


def test_campaign_mode_calculate_stars():
    """Yıldız hesaplaması — sequential kontrol."""
    from campaign.coop_campaign_mode import CoopCampaignMode
    mode = object.__new__(CoopCampaignMode)
    mode.objectives = []
    mode.team_score = 2000
    mode.tetris_count = 0
    mode.total_combos = 0
    mode.elapsed_time = 80000
    mode.level_complete = True
    mode.p1_total_cells = 50
    mode.p2_total_cells = 50
    mode.p1_contribution_pct = 50
    mode.p2_contribution_pct = 50

    class _MockObj:
        completed = True
    mode.objectives = [_MockObj()]

    # Star 1: complete (OK), Star 2: score >= 1500 (OK), Star 3: time <= 60 (FAIL)
    mode.star_conditions = {
        1: {'type': 'complete'},
        2: {'type': 'score', 'value': 1500},
        3: {'type': 'time_limit', 'value': 60},
    }
    assert mode._calculate_stars() == 2


def test_save_and_load_progress():
    """Progress kaydetme ve yükleme."""
    from campaign.coop_campaign_mode import CoopCampaignMode
    sm = _FakeSettingsManager()
    um = _FakeUserManager()

    mode = object.__new__(CoopCampaignMode)
    mode.settings_manager = sm
    mode.user_manager = um
    mode.current_level_num = 1
    mode.earned_stars = 2
    mode.team_score = 1500

    mode._save_progress()

    progress = CoopCampaignMode.load_progress(um)
    assert '1' in progress.get('completed_levels', {})
    assert progress['completed_levels']['1']['stars'] == 2
    assert progress['completed_levels']['1']['best_score'] == 1500
    assert progress['highest_level'] == 1
    assert progress['total_stars'] == 2


def test_save_progress_best_score_preserved():
    """Daha düşük skorlu yeni tamamlama eski best_score'u korumalı."""
    from campaign.coop_campaign_mode import CoopCampaignMode
    sm = _FakeSettingsManager()
    um = _FakeUserManager()

    # İlk tamamlama — yüksek skor
    mode1 = object.__new__(CoopCampaignMode)
    mode1.settings_manager = sm
    mode1.user_manager = um
    mode1.current_level_num = 1
    mode1.earned_stars = 3
    mode1.team_score = 3000
    mode1._save_progress()

    # İkinci tamamlama — düşük skor
    mode2 = object.__new__(CoopCampaignMode)
    mode2.settings_manager = sm
    mode2.user_manager = um
    mode2.current_level_num = 1
    mode2.earned_stars = 1
    mode2.team_score = 500
    mode2._save_progress()

    progress = CoopCampaignMode.load_progress(um)
    lvl = progress['completed_levels']['1']
    assert lvl['best_score'] == 3000  # Eski yüksek skor korunmalı
    assert lvl['stars'] == 3  # Eski yüksek yıldız korunmalı
    assert lvl['attempts'] == 2


def test_get_next_level():
    from campaign.coop_campaign_mode import CoopCampaignMode
    mode = object.__new__(CoopCampaignMode)
    mode.current_level_num = 5
    assert mode.get_next_level_num() == 6

    mode.current_level_num = TOTAL_COOP_LEVELS
    assert mode.get_next_level_num() is None


def test_format_time():
    from campaign.coop_campaign_mode import CoopCampaignMode
    assert CoopCampaignMode._format_time(0) == '00:00'
    assert CoopCampaignMode._format_time(61000) == '01:01'
    assert CoopCampaignMode._format_time(600000) == '10:00'


def test_campaign_fail_uses_shared_game_over_activation_path():
    from campaign.coop_campaign_mode import CoopCampaignMode

    mode = object.__new__(CoopCampaignMode)
    mode.level_failed = False
    mode.fail_reason = ''
    mode.game_over = False
    mode.sound = _SM()

    mode._handle_level_failed('timeout')

    assert mode.level_failed is True
    assert mode.fail_reason == 'timeout'
    assert mode.game_over is True
    assert mode.sound.game_over_sequence_calls == 1


# =====================================================================
# CoopLevelSelect testleri
# =====================================================================

def test_level_select_import():
    from campaign.coop_level_select import CoopLevelSelect
    assert CoopLevelSelect is not None

def test_level_select_unlocking():
    from campaign.coop_level_select import CoopLevelSelect
    sm = _FakeSettingsManager()
    sel = CoopLevelSelect(screen=_Surf(), settings_manager=sm)
    # Level 1 her zaman açık
    assert sel._is_level_unlocked(1)
    # Level 2 kilitli
    assert not sel._is_level_unlocked(2)

def test_level_select_unlocking_with_progress():
    from campaign.coop_level_select import CoopLevelSelect
    sm = _FakeSettingsManager()
    um = _FakeUserManager()
    um.save_coop_campaign_progress({
        'completed_levels': {'1': {'completed': True, 'stars': 1}},
        'highest_level': 1,
    })
    sel = CoopLevelSelect(screen=_Surf(), settings_manager=sm, user_manager=um)
    assert sel._is_level_unlocked(1)
    assert sel._is_level_unlocked(2)
    assert not sel._is_level_unlocked(3)

def test_level_select_stars():
    from campaign.coop_level_select import CoopLevelSelect
    sm = _FakeSettingsManager()
    um = _FakeUserManager()
    um.save_coop_campaign_progress({
        'completed_levels': {'2': {'completed': True, 'stars': 3}},
    })
    sel = CoopLevelSelect(screen=_Surf(), settings_manager=sm, user_manager=um)
    assert sel._get_level_stars(2) == 3
    assert sel._get_level_stars(1) == 0  # tamamlanmamış


def test_level_select_ui_scale_uses_projected_effective_scale(monkeypatch):
    from campaign import coop_level_select as coop_level_select_module
    from campaign.coop_level_select import CoopLevelSelect

    sel = CoopLevelSelect(screen=_Surf(), settings_manager=_FakeSettingsManager())
    captured = {}

    def fake_get_projected_scale(target, *, min_scale, max_scale, reference_size, display_surface=None):
        captured['target'] = target
        captured['min_scale'] = min_scale
        captured['max_scale'] = max_scale
        captured['reference_size'] = reference_size
        captured['display_surface'] = display_surface
        return 1.05

    monkeypatch.setattr(coop_level_select_module, 'get_projected_effective_scale', fake_get_projected_scale)

    assert sel._ui_scale() == 1.05
    assert captured['target'] is sel.screen
    assert captured['min_scale'] == 0.72
    assert captured['max_scale'] == 1.18
    assert captured['reference_size'] == (1400.0, 900.0)
    assert captured['display_surface'] is None
