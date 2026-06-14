"""
Test: ExtrasScreen._items_base içinde Classic Mode var mı ve MODE_ID_TO_STATS_KEY doğru mu?
"""
import sys
import types
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent))
sys.path.insert(0, str(pathlib.Path(__file__).parent / 'src'))

# pygame stub
pygame_mod = types.ModuleType('pygame')
pygame_mod.QUIT = 256
pygame_mod.KEYDOWN = 768
pygame_mod.K_ESCAPE = 27
pygame_mod.K_RETURN = 13
pygame_mod.K_SPACE = 32
pygame_mod.K_UP = 273
pygame_mod.K_DOWN = 274
pygame_mod.K_LEFT = 276
pygame_mod.K_RIGHT = 275
pygame_mod.K_w = 119
pygame_mod.K_s = 115
pygame_mod.K_a = 97
pygame_mod.K_d = 100
pygame_mod.MOUSEBUTTONDOWN = 1025
pygame_mod.MOUSEMOTION = 1024
pygame_mod.MOUSEWHEEL = 1027
pygame_mod.SRCALPHA = 65536
pygame_mod.BLEND_RGBA_MULT = 0


class _FakeRect:
    def __init__(self, *a, **kw):
        self.width = 0
        self.height = 0

    def collidepoint(self, *a):
        return False


pygame_mod.Rect = _FakeRect


class _FakeFont:
    def render(self, *a, **kw):
        return None

    def size(self, *a):
        return (0, 0)

    def get_height(self):
        return 20


class _FakeSurface:
    def __init__(self, width=1024, height=768):
        self._size = (width, height)

    def fill(self, *a, **kw):
        return None

    def blit(self, *a, **kw):
        return None

    def get_width(self):
        return self._size[0]

    def get_height(self):
        return self._size[1]

    def get_size(self):
        return self._size

    def set_alpha(self, *a, **kw):
        return None

    def subsurface(self, *a, **kw):
        return self

    def convert_alpha(self, *a, **kw):
        return self

    def convert(self, *a, **kw):
        return self


pygame_mod.Surface = _FakeSurface
pygame_mod.font = types.SimpleNamespace(Font=lambda *a, **kw: _FakeFont())
pygame_mod.display = types.SimpleNamespace(
    get_surface=lambda: None,
    get_window_size=lambda: (1024, 768),
    get_size=lambda: (1024, 768),
)
pygame_mod.time = types.SimpleNamespace(get_ticks=lambda: 0)
pygame_mod.image = types.SimpleNamespace(
    load=lambda *a, **kw: _FakeSurface(),
    tostring=lambda *a, **kw: b'',
)
pygame_mod.transform = types.SimpleNamespace(
    smoothscale=lambda *a, **kw: _FakeSurface(),
    scale=lambda *a, **kw: _FakeSurface(),
)
pygame_mod.mixer = types.ModuleType('pygame.mixer')
pygame_mod.mixer.music = types.SimpleNamespace(play=lambda *a, **kw: None, stop=lambda: None)

for m in [
    'pygame',
    'pygame.font',
    'pygame.display',
    'pygame.image',
    'pygame.mixer',
    'pygame.mixer.music',
    'pygame.time',
    'pygame.transform',
]:
    sys.modules[m] = (
        pygame_mod if m == 'pygame' else getattr(pygame_mod, m.split('.')[-1], types.ModuleType(m))
    )

# Stub tüm bağımlılıklar
for name in [
    'retro_style',
    'platform_utils',
    'localization',
    'themes',
    'ui_components',
    'sound',
    'achievements',
    'user_manager',
    'score_manager',
    'constants',
    'block_styles',
    'steam_integration',
    'background_effects',
    'ui_theme',
    'settings_manager',
    'asset_manager',
]:
    sys.modules[name] = types.ModuleType(name)

# localization mock
loc = sys.modules['localization']
loc.t = lambda k, *a, **kw: k
loc.get_language = lambda: 'tr'

# platform_utils mock
pl = sys.modules['platform_utils']
pl.normalize_mouse_pos = lambda p: p
pl.get_mouse_pos = lambda: (0, 0)
pl.is_fullscreen_toggle = lambda *a, **kw: False

# background_effects mock
bg = sys.modules['background_effects']
bg.get_shared_falling_blocks_layer = lambda *a, **kw: types.SimpleNamespace(update=lambda *a, **kw: None, draw=lambda *a, **kw: None)

# ui_components mock
sys.modules['ui_components'].draw_glass_card = lambda *a, **kw: None

# constants mock
const = sys.modules['constants']
const.NEON_BLUE = (50, 100, 255)

# ui_theme mock
uit = sys.modules['ui_theme']
uit.UIColors = type('UIColors', (), {
    'NEON_GOLD': (255, 215, 0),
    'NEON_RED': (255, 50, 50),
    'NEON_GREEN': (50, 255, 50),
    'NEON_MAGENTA': (255, 50, 255),
    'NEON_CYAN': (50, 255, 255),
    'BG_DARK': (10, 10, 20),
})()
uit.UIFonts = type('UIFonts', (), {
    'SIZE_TITLE': 32,
    'SIZE_SUBHEADING': 18,
    'SIZE_SMALL': 12,
    'get': staticmethod(lambda *a, **kw: _FakeFont()),
})()
uit.UIStyle = type('UIStyle', (), {
    'SPACING_LARGE': 24,
    'BORDER_RADIUS_MEDIUM': 12,
})()
uit.lerp_color = lambda a, b, t: a

# retro_style mock (extras_menu: from retro_style import retro_style)
rs_mod = sys.modules['retro_style']
rs_mod.retro_style = types.SimpleNamespace(
    draw_background=lambda *a, **kw: None,
    draw_title=lambda *a, **kw: types.SimpleNamespace(bottom=0),
    get_font=lambda *a, **kw: _FakeFont(),
    get_fitting_font=lambda *a, **kw: _FakeFont(),
    draw_glass_panel=lambda *a, **kw: None,
)
rs_mod.get_font = lambda *a, **kw: _FakeFont()
rs_mod.get_fitting_font = lambda *a, **kw: _FakeFont()
rs_mod.draw_glass_panel = lambda *a, **kw: None

# asset_manager mock
sys.modules['asset_manager'].load_image = lambda *a, **kw: _FakeSurface()

# Extras modülünü import et
import importlib.util
spec = importlib.util.spec_from_file_location('extras_menu', pathlib.Path('src/extras_menu.py'))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
ExtrasScreen = mod.ExtrasScreen


def test_classic_mode_in_items_base():
    """_items_base içinde 'Classic Mode' id'li item var mı?"""
    screen = _FakeSurface()
    user_manager_mock = types.SimpleNamespace(get_mode_highscore=lambda *a, **kw: 0)

    extras = ExtrasScreen(screen, user_manager=user_manager_mock)

    ids = [item['id'] for item in extras._items_base]
    assert 'Classic Mode' in ids, f"'Classic Mode' not in _items_base. Found: {ids}"


def test_coop_campaign_not_in_items_base():
    """Co-op Campaign kartı oyun modları UI listesinde görünmemeli."""
    screen = _FakeSurface()
    user_manager_mock = types.SimpleNamespace(get_mode_highscore=lambda *a, **kw: 0)

    extras = ExtrasScreen(screen, user_manager=user_manager_mock)

    ids = [item['id'] for item in extras._items_base]
    assert 'coop_campaign' not in ids, f"'coop_campaign' unexpectedly in _items_base. Found: {ids}"


def test_mode_id_to_stats_key_classic():
    """MODE_ID_TO_STATS_KEY['Classic Mode'] == 'classic'"""
    assert mod.ExtrasScreen.MODE_ID_TO_STATS_KEY.get('Classic Mode') == 'classic', (
        f"Got: {mod.ExtrasScreen.MODE_ID_TO_STATS_KEY.get('Classic Mode')!r}"
    )


def test_extras_ui_scale_can_grow_above_one_on_large_displays():
    """Faz 2: ortak helper ile extras ekranı 1080p üstünde büyüyebilmeli."""
    screen = _FakeSurface(2560, 1440)
    user_manager_mock = types.SimpleNamespace(get_mode_highscore=lambda *a, **kw: 0)

    extras = ExtrasScreen(screen, user_manager=user_manager_mock)

    assert extras._extras_ui_scale() > 1.0


def test_extras_ui_scale_uses_effective_helper_when_available(monkeypatch):
    screen = _FakeSurface(2560, 1660)
    user_manager_mock = types.SimpleNamespace(get_mode_highscore=lambda *a, **kw: 0)
    captured = {}

    def fake_get_projected_effective_scale(surface, *, min_scale, max_scale, reference_size, display_surface=None):
        captured['surface'] = surface
        captured['min_scale'] = min_scale
        captured['max_scale'] = max_scale
        captured['reference_size'] = reference_size
        captured['display_surface'] = display_surface
        return 0.95

    monkeypatch.setattr(mod, 'get_projected_effective_scale', fake_get_projected_effective_scale)

    extras = ExtrasScreen(screen, user_manager=user_manager_mock)

    assert extras._extras_ui_scale() == 0.95
    assert captured['surface'] is screen
    assert captured['min_scale'] == 0.60
    assert captured['max_scale'] == 1.24
    assert captured['reference_size'] == (1366.0, 768.0)
    assert captured['display_surface'] is None


def test_extras_ui_scale_hits_phase5_relaxed_cap_on_large_displays():
    screen = _FakeSurface(2560, 1440)
    user_manager_mock = types.SimpleNamespace(get_mode_highscore=lambda *a, **kw: 0)

    extras = ExtrasScreen(screen, user_manager=user_manager_mock)

    assert abs(extras._extras_ui_scale() - 1.24) < 0.001


def test_extras_ui_scale_preserves_1366_baseline():
    """Faz 2 uyumluluk: klasik 1366x768 baseline gereksiz yere küçülmemeli."""
    screen = _FakeSurface(1366, 768)
    user_manager_mock = types.SimpleNamespace(get_mode_highscore=lambda *a, **kw: 0)

    extras = ExtrasScreen(screen, user_manager=user_manager_mock)

    assert abs(extras._extras_ui_scale() - 1.0) < 0.001
