"""
Test: CampaignLevelSelect._is_level_unlocked debug bypass
"""
import sys, pathlib
import types

sys.path.insert(0, str(pathlib.Path(__file__).parent))
sys.path.insert(0, str(pathlib.Path(__file__).parent / 'src'))

_MISSING = object()
_STUB_MODULE_NAMES = [
    'pygame', 'pygame.font', 'pygame.display', 'pygame.image', 'pygame.mixer',
    'src.ui_components', 'ui_components',
    'src.localization', 'localization',
    'src.themes', 'themes',
    'src.retro_style', 'retro_style',
    'src.campaign.level_data', 'campaign.level_data',
    'src.user_manager', 'user_manager',
    'src.settings_manager', 'settings_manager',
    'src.score_manager', 'score_manager',
    'src.sound', 'sound',
    'src.achievements', 'achievements',
    'src.platform_utils', 'platform_utils',
    'ui_theme', 'background_effects',
]
_ORIGINAL_MODULES = {name: sys.modules.get(name, _MISSING) for name in _STUB_MODULE_NAMES}


def _restore_stubbed_modules():
    for name, original in _ORIGINAL_MODULES.items():
        if original is _MISSING:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = original

# Stub: pygame
pygame_mod = types.ModuleType('pygame')
pygame_mod.QUIT = 0
pygame_mod.KEYDOWN = 1
class FakeFont:
    def render(self, *a, **kw): return None
    def size(self, *a): return (0, 0)
class FakeFontMod:
    def SysFont(self, *a, **kw): return FakeFont()
    def Font(self, *a, **kw): return FakeFont()
pygame_mod.font = FakeFontMod()
pygame_mod.display = types.ModuleType('pygame.display')
pygame_mod.image = types.ModuleType('pygame.image')
pygame_mod.mixer = types.ModuleType('pygame.mixer')
pygame_mod.Color = lambda *a: None
sys.modules['pygame'] = pygame_mod
sys.modules['pygame.font'] = pygame_mod.font
sys.modules['pygame.display'] = pygame_mod.display
sys.modules['pygame.image'] = pygame_mod.image
sys.modules['pygame.mixer'] = pygame_mod.mixer

# Stub: diğer bağımlılıklar
for mod in [
    'src.ui_components', 'ui_components',
    'src.localization', 'localization',
    'src.themes', 'themes',
    'src.retro_style', 'retro_style',
    'src.campaign.level_data', 'campaign.level_data',
    'src.user_manager', 'user_manager',
    'src.settings_manager', 'settings_manager',
    'src.score_manager', 'score_manager',
    'src.sound', 'sound',
    'src.achievements', 'achievements',
    'src.platform_utils', 'platform_utils',
]:
    sys.modules[mod] = types.ModuleType(mod)

for _pu_name in ('platform_utils', 'src.platform_utils'):
    _pu = sys.modules.get(_pu_name)
    if _pu is not None:
        _pu.normalize_mouse_pos = lambda pos=None: pos
        _pu.get_mouse_pos = lambda: (0, 0)
        _pu.is_fullscreen_toggle = lambda *a, **kw: False

sys.modules['retro_style'].retro_style = types.SimpleNamespace(
    get_font=lambda *a, **kw: FakeFont()
)

ui_theme_mod = types.ModuleType('ui_theme')
ui_theme_mod.UIColors = types.SimpleNamespace(
    NEON_CYAN=(0, 255, 255),
    NEON_MAGENTA=(255, 0, 255),
    NEON_ORANGE=(255, 140, 0),
    NEON_GREEN=(0, 255, 0),
    NEON_GOLD=(255, 215, 0),
)
ui_theme_mod.UIFonts = types.SimpleNamespace(get=lambda *a, **kw: FakeFont())
ui_theme_mod.UIStyle = types.SimpleNamespace()
sys.modules['ui_theme'] = ui_theme_mod

bg_mod = types.ModuleType('background_effects')
bg_mod.get_shared_falling_blocks_layer = lambda *a, **kw: None
sys.modules['background_effects'] = bg_mod

loc_mod = sys.modules['localization']
loc_mod.t = lambda key, *a, **kw: key
loc_mod.get_language = lambda: 'en'

import importlib.util

# CampaignLevelSelect'i doğrudan yükle
spec = importlib.util.spec_from_file_location(
    'campaign.level_select',
    pathlib.Path('src/campaign/level_select.py')
)
mod = importlib.util.module_from_spec(spec)

# Stub eksik bağımlılıkları
import unittest.mock as mock
sys.modules['src.campaign.level_data'] = mock.MagicMock()
sys.modules['campaign.level_data'] = mock.MagicMock()

spec.loader.exec_module(mod)
CampaignLevelSelect = mod.CampaignLevelSelect
_restore_stubbed_modules()


def make_instance():
    inst = object.__new__(CampaignLevelSelect)
    inst.progress = {'completed_levels': {}}
    return inst


def apply_campaign_unlock_toggle(inst):
    currently_on = getattr(inst, 'debug_unlock_all', False)
    if currently_on:
        inst.debug_unlock_all = False
        highest = inst.progress.get('highest_level', 0)
        inst.current_world = max(1, (highest - 1) // 20 + 1) if highest > 0 else 1
        inst._update_selection_for_world()
        inst.scroll_offset = 0
        inst.hovered_level = None
    else:
        inst.debug_unlock_all = True


def test_debug_unlock_all_true():
    inst = make_instance()
    inst.debug_unlock_all = True
    assert inst._is_level_unlocked(100) is True


def test_debug_unlock_all_false_locked():
    inst = make_instance()
    inst.debug_unlock_all = False
    assert inst._is_level_unlocked(2) is False


def test_no_flag_level_1_always_open():
    inst = make_instance()
    assert inst._is_level_unlocked(1) is True


def test_toggle_off_sets_debug_unlock_all_false():
    inst = make_instance()
    inst.debug_unlock_all = True
    inst.progress = {
        'highest_level': 25,
        'completed_levels': {'24': {'completed': True}},
        'current_world': 2,
        'total_stars': 0,
    }
    inst.current_world = 5
    inst.scroll_offset = 150
    inst.hovered_level = 25

    apply_campaign_unlock_toggle(inst)

    assert inst.debug_unlock_all is False


def test_toggle_off_restores_world_from_highest_level():
    inst = make_instance()
    inst.debug_unlock_all = True
    inst.progress = {
        'highest_level': 25,
        'completed_levels': {'24': {'completed': True}},
        'current_world': 2,
        'total_stars': 0,
    }
    inst.current_world = 1
    inst.scroll_offset = 150
    inst.hovered_level = 25

    apply_campaign_unlock_toggle(inst)

    assert inst.current_world == 2


def test_toggle_off_with_zero_highest_defaults_world_1():
    inst = make_instance()
    inst.debug_unlock_all = True
    inst.progress = {
        'highest_level': 0,
        'completed_levels': {},
        'current_world': 1,
        'total_stars': 0,
    }
    inst.current_world = 4
    inst.scroll_offset = 150
    inst.hovered_level = 10

    apply_campaign_unlock_toggle(inst)

    assert inst.current_world == 1


def test_toggle_off_resets_scroll_offset_to_zero():
    inst = make_instance()
    inst.debug_unlock_all = True
    inst.progress = {
        'highest_level': 25,
        'completed_levels': {'24': {'completed': True}},
        'current_world': 2,
        'total_stars': 0,
    }
    inst.current_world = 2
    inst.scroll_offset = 150
    inst.hovered_level = 25

    apply_campaign_unlock_toggle(inst)

    assert inst.scroll_offset == 0
    assert inst.hovered_level is None


def test_toggle_on_off_idempotent():
    inst = make_instance()
    inst.debug_unlock_all = False
    inst.progress = {
        'highest_level': 25,
        'completed_levels': {'24': {'completed': True}},
        'current_world': 2,
        'total_stars': 0,
    }
    inst.current_world = 2
    inst.scroll_offset = 100
    inst.hovered_level = 24

    apply_campaign_unlock_toggle(inst)
    assert inst.debug_unlock_all is True

    apply_campaign_unlock_toggle(inst)
    assert inst.debug_unlock_all is False


def test_level_select_ui_scale_stays_raw_surface_scaled_until_campaign_flow_aligns():
    class _FakeScreen:
        def get_size(self):
            return (2560, 1660)

    inst = object.__new__(CampaignLevelSelect)
    inst.screen = _FakeScreen()

    captured = {}
    original = getattr(mod, 'get_scale')

    def fake_get_scale(screen, *, min_scale, max_scale, reference_size):
        captured['screen'] = screen
        captured['min_scale'] = min_scale
        captured['max_scale'] = max_scale
        captured['reference_size'] = reference_size
        return 0.98

    mod.get_scale = fake_get_scale
    try:
        assert inst._get_ui_scale() == 0.98
    finally:
        mod.get_scale = original

    assert captured['screen'] is inst.screen
    assert captured['min_scale'] == 0.72
    assert captured['max_scale'] == 1.18
    assert captured['reference_size'] == (1400.0, 900.0)
