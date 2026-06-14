import importlib
import sys
import types


def test_ui_components_glass_panel_scales_with_menu_transparency(monkeypatch):
    draw_calls = []

    class FakeSurface:
        def __init__(self, size, *_args, **_kwargs):
            self.size = size

        def blit(self, *_args, **_kwargs):
            return None

    class FakeRect:
        def __init__(self, x, y, width, height):
            self.x = x
            self.y = y
            self.width = width
            self.height = height

        def inflate(self, dx, dy):
            return FakeRect(self.x - dx // 2, self.y - dy // 2, self.width + dx, self.height + dy)

        @property
        def topleft(self):
            return (self.x, self.y)

    fake_pygame = types.ModuleType('pygame')
    fake_pygame.SRCALPHA = 1
    fake_pygame.BLEND_ADD = 1
    fake_pygame.Surface = FakeSurface
    fake_pygame.Rect = FakeRect
    fake_pygame.font = types.SimpleNamespace(Font=object)
    fake_pygame.draw = types.SimpleNamespace(
        rect=lambda _surface, color, *_args, **_kwargs: draw_calls.append(tuple(color)),
        line=lambda *_args, **_kwargs: None,
    )

    fake_ui_theme = types.ModuleType('ui_theme')
    fake_ui_theme.UIColors = types.SimpleNamespace(
        GLASS_BORDER=(80, 80, 120, 150),
        NEON_CYAN=(0, 255, 255),
        BG_MEDIUM=(20, 20, 45),
    )
    fake_ui_theme.UIFonts = types.SimpleNamespace()
    fake_ui_theme.UIStyle = types.SimpleNamespace(BORDER_RADIUS_MEDIUM=16)
    fake_ui_theme.lerp_color = lambda *args, **kwargs: None
    fake_ui_theme.brighten_color = lambda *args, **kwargs: None
    fake_ui_theme.add_alpha = lambda *args, **kwargs: None

    fake_retro_style = types.ModuleType('retro_style')
    fake_retro_style.retro_style = types.SimpleNamespace(_menu_transparency=0.5)

    monkeypatch.setitem(sys.modules, 'pygame', fake_pygame)
    monkeypatch.setitem(sys.modules, 'ui_theme', fake_ui_theme)
    monkeypatch.setitem(sys.modules, 'retro_style', fake_retro_style)
    monkeypatch.delitem(sys.modules, 'ui_components', raising=False)

    ui_components = importlib.import_module('ui_components')

    ui_components.draw_glass_panel(
        FakeSurface((200, 120)),
        FakeRect(10, 10, 80, 40),
        alpha=180,
        border_color=(10, 20, 30),
        glow=False,
    )

    assert (20, 20, 45, 90) in draw_calls
    assert (10, 20, 30, 75) in draw_calls