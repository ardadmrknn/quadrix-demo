from __future__ import annotations

import types

import guide_screen
import graphics_menu


class _FakeScreen:
    def __init__(self, width: int, height: int):
        self._size = (width, height)

    def get_size(self) -> tuple[int, int]:
        return self._size

    def set_size(self, width: int, height: int) -> None:
        self._size = (width, height)

    def get_width(self) -> int:
        return self._size[0]

    def get_height(self) -> int:
        return self._size[1]


class _DummyFx:
    def update(self, *args, **kwargs):
        return None

    def draw(self, *args, **kwargs):
        return None


class _DummySettings:
    def __init__(self):
        self.values: dict[str, object] = {}

    def get(self, key: str, default=None):
        return self.values.get(key, default)

    def set(self, key: str, value):
        self.values[key] = value


def test_graphics_menu_ui_scale_preserves_1366_baseline(monkeypatch):
    monkeypatch.setattr(graphics_menu, 'get_shared_falling_blocks_layer', lambda *args, **kwargs: _DummyFx())
    monkeypatch.setattr(graphics_menu.retro_style, 'get_font', lambda *args, **kwargs: types.SimpleNamespace())

    menu = graphics_menu.GraphicsMenu(_FakeScreen(1366, 768), _DummySettings())

    assert abs(menu._ui_scale() - 1.0) < 0.001


def test_graphics_menu_layout_metrics_grow_on_large_displays(monkeypatch):
    monkeypatch.setattr(graphics_menu, 'get_shared_falling_blocks_layer', lambda *args, **kwargs: _DummyFx())
    monkeypatch.setattr(graphics_menu.retro_style, 'get_font', lambda *args, **kwargs: types.SimpleNamespace())

    menu = graphics_menu.GraphicsMenu(_FakeScreen(2560, 1440), _DummySettings())
    metrics = menu._layout_metrics()

    assert metrics['card_height'] > 74
    assert metrics['scroll_step'] > 30


def test_guide_screen_ui_scale_preserves_1366_baseline(monkeypatch):
    monkeypatch.setattr(guide_screen, 'get_shared_falling_blocks_layer', lambda *args, **kwargs: _DummyFx())

    guide = guide_screen.GuideScreen(_FakeScreen(1366, 768))

    assert abs(guide._ui_scale() - 1.0) < 0.001


def test_guide_screen_buttons_and_scroll_step_grow_on_large_displays(monkeypatch):
    monkeypatch.setattr(guide_screen, 'get_shared_falling_blocks_layer', lambda *args, **kwargs: _DummyFx())

    guide = guide_screen.GuideScreen(_FakeScreen(2560, 1440))
    tutorial_rect, back_rect = guide._get_bottom_button_rects()

    assert tutorial_rect.height > 50
    assert back_rect.height > 50
    assert guide._scroll_step() > 40


def test_guide_screen_content_cache_signature_changes_on_height_only_resize(monkeypatch):
    monkeypatch.setattr(guide_screen, 'get_shared_falling_blocks_layer', lambda *args, **kwargs: _DummyFx())

    screen = _FakeScreen(1366, 768)
    guide = guide_screen.GuideScreen(screen)

    signature_before = guide._content_cache_signature(820)
    screen.set_size(1366, 620)
    signature_after = guide._content_cache_signature(820)

    assert signature_before != signature_after


def test_guide_screen_content_cache_signature_tracks_language(monkeypatch):
    monkeypatch.setattr(guide_screen, 'get_shared_falling_blocks_layer', lambda *args, **kwargs: _DummyFx())
    current_language = ['tr']
    monkeypatch.setattr(guide_screen, 'get_language', lambda: current_language[0])

    guide = guide_screen.GuideScreen(_FakeScreen(1366, 768))

    signature_tr = guide._content_cache_signature(820)
    current_language[0] = 'en'
    signature_en = guide._content_cache_signature(820)

    assert signature_tr != signature_en


def test_graphics_menu_max_scroll_reuses_draw_visible_height(monkeypatch):
    monkeypatch.setattr(graphics_menu, 'get_shared_falling_blocks_layer', lambda *args, **kwargs: _DummyFx())
    monkeypatch.setattr(graphics_menu.retro_style, 'get_font', lambda *args, **kwargs: types.SimpleNamespace())

    menu = graphics_menu.GraphicsMenu(_FakeScreen(1366, 768), _DummySettings())
    metrics = menu._layout_metrics()
    expected = max(0, len(menu.options) * int(metrics['spacing']) - 200)

    assert menu._max_scroll(visible_height=200) == expected
    assert menu._max_scroll() == expected