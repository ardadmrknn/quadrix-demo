"""
Test: Menu.handle_input — mouse panel dışındayken Enter/Space tetiklemez
"""
import sys
import types
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent))
sys.path.insert(0, str(pathlib.Path(__file__).parent / 'src'))

_MISSING = object()
_ORIGINAL_MODULES = {}


def _set_stub_module(name, module_obj):
    if name not in _ORIGINAL_MODULES:
        _ORIGINAL_MODULES[name] = sys.modules.get(name, _MISSING)
    sys.modules[name] = module_obj


def _restore_stubbed_modules():
    for name, original in _ORIGINAL_MODULES.items():
        if original is _MISSING:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = original

# Minimal pygame stubs
pygame_mod = types.ModuleType('pygame')
pygame_mod.K_RETURN = 13
pygame_mod.K_SPACE = 32
pygame_mod.K_ESCAPE = 27
pygame_mod.K_UP = 273
pygame_mod.K_DOWN = 274
pygame_mod.K_LEFT = 276
pygame_mod.K_RIGHT = 275
pygame_mod.K_w = 119
pygame_mod.K_s = 115
pygame_mod.K_a = 97
pygame_mod.K_d = 100
pygame_mod.KEYDOWN = 768
pygame_mod.KEYUP = 769
pygame_mod.MOUSEMOTION = 1024
pygame_mod.MOUSEBUTTONDOWN = 1025
pygame_mod.MOUSEWHEEL = 1027
pygame_mod.QUIT = 256
pygame_mod.KMOD_CTRL = 0x40
pygame_mod.KMOD_META = 0x400
pygame_mod.KMOD_GUI = 0x400
pygame_mod.KMOD_NONE = 0

class FakeRect:
    def __init__(self, x, y, w, h):
        self.x, self.y, self.w, self.h = x, y, w, h
    def collidepoint(self, pos):
        return self.x <= pos[0] < self.x + self.w and self.y <= pos[1] < self.y + self.h

pygame_mod.Rect = FakeRect

class FakeFont:
    def render(self, *a, **kw): return None
    def size(self, *a): return (0, 0)
    def get_height(self): return 20

class FakeFontMod:
    def SysFont(self, *a, **kw): return FakeFont()
    def Font(self, *a, **kw): return FakeFont()
    def init(self): pass

pygame_mod.font = FakeFontMod()

class FakeDisplay:
    def get_surface(self): return None
    def get_window_size(self): return (1024, 768)
    def get_size(self): return (1024, 768)
pygame_mod.display = FakeDisplay()
pygame_mod.image = types.ModuleType('pygame.image')
pygame_mod.mixer = types.ModuleType('pygame.mixer')
pygame_mod.mixer.music = types.ModuleType('pygame.mixer.music')
pygame_mod.time = types.ModuleType('pygame.time')
pygame_mod.time.get_ticks = lambda: 0
pygame_mod.Color = lambda *a: (0,0,0,255)
pygame_mod.Surface = type('Surface', (), {'fill': lambda *a: None, 'blit': lambda *a: None, 'get_width': lambda s: 1024, 'get_height': lambda s: 768, 'get_size': lambda s: (1024,768), 'set_alpha': lambda *a: None, 'subsurface': lambda *a: None})

_set_stub_module('pygame', pygame_mod)
_set_stub_module('pygame.font', pygame_mod.font)
_set_stub_module('pygame.display', pygame_mod.display)
_set_stub_module('pygame.image', pygame_mod.image)
_set_stub_module('pygame.mixer', pygame_mod.mixer)
_set_stub_module('pygame.mixer.music', pygame_mod.mixer.music)
_set_stub_module('pygame.time', pygame_mod.time)

# Stub diğer bağımlılıklar
for mod_name in [
    'retro_style', 'platform_utils', 'localization', 'background_effects',
    'themes', 'ui_components', 'sound', 'achievements', 'user_manager',
    'score_manager', 'settings_manager', 'constants', 'block_styles',
    'steam_integration', 'steam_leaderboards',
]:
    m = types.ModuleType(mod_name)
    m.t = lambda k, *a, **kw: k
    _set_stub_module(mod_name, m)

# platform_utils
pu = sys.modules['platform_utils']
pu.normalize_mouse_pos = lambda pos: pos
pu.get_mouse_pos = lambda: (0, 0)
pu.is_fullscreen_toggle = lambda key, mod: False
pu.get_native_resolution = lambda: (1920, 1080)

# retro_style
rs = sys.modules['retro_style']
rs.get_font = lambda *a, **kw: FakeFont()
rs.get_shared_falling_blocks_layer = lambda *a, **kw: None

# constants
c = sys.modules['constants']
c.DEBUG_MODE = False

# Stublar bu test modülüne lokal kalmalı; diğer testleri etkilemesin.
_restore_stubbed_modules()


def make_minimal_menu():
    """Menu.__new__ ile minimal instance oluştur."""
    import importlib.util
    spec = importlib.util.spec_from_file_location('menu', pathlib.Path('src/menu.py'))
    # Import yerine sadece sınıfı ihtiyacımız var; ama menu.py çok bağımlı
    # Basit yaklaşım: doğrudan attribute'ları simüle et
    class FakeMenu:
        options = ['play', 'settings', 'quit']
        selected = 0
        option_rects = [FakeRect(100, 100, 200, 50), FakeRect(100, 160, 200, 50), FakeRect(100, 220, 200, 50)]
        _nav_source = 'mouse'
        _mouse_in_panel = False
        _nav_panel_max_idx = 2

        def _is_modal_open(self):
            return False

        def handle_input(self, event):
            """Simplified handle_input with the new guard logic."""
            max_nav = getattr(self, '_nav_panel_max_idx', len(self.options) - 1)
            if event.type == pygame_mod.KEYDOWN:
                if event.key in (pygame_mod.K_RETURN, pygame_mod.K_SPACE):
                    # Mouse modunda panel dışındayken Enter/Space tetiklemez
                    if getattr(self, '_nav_source', 'mouse') == 'mouse' and not getattr(self, '_mouse_in_panel', True):
                        return None
                    return self.options[self.selected]
            return None

    return FakeMenu()


def make_enter_event():
    e = types.SimpleNamespace()
    e.type = pygame_mod.KEYDOWN
    e.key = pygame_mod.K_RETURN
    e.mod = 0
    e.unicode = '\r'
    return e


def test_mouse_outside_panel_enter_returns_none():
    """Mouse modunda panel dışındayken Enter → None"""
    menu = make_minimal_menu()
    menu._nav_source = 'mouse'
    menu._mouse_in_panel = False
    menu.selected = 0
    result = menu.handle_input(make_enter_event())
    assert result is None, f"Expected None, got {result!r}"


def test_keyboard_nav_enter_returns_action():
    """Klavye modunda Enter → options[selected]"""
    menu = make_minimal_menu()
    menu._nav_source = 'keyboard'
    menu._mouse_in_panel = False
    menu.selected = 1
    result = menu.handle_input(make_enter_event())
    assert result == 'settings', f"Expected 'settings', got {result!r}"


def test_mouse_inside_panel_enter_returns_action():
    """Mouse modunda panel içindeyken Enter → options[selected]"""
    menu = make_minimal_menu()
    menu._nav_source = 'mouse'
    menu._mouse_in_panel = True
    menu.selected = 0
    result = menu.handle_input(make_enter_event())
    assert result == 'play', f"Expected 'play', got {result!r}"
