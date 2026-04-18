from __future__ import annotations

import math
import types

import guide_screen
import gameplay_settings as gameplay_settings_module
import graphics_menu
import menu as menu_module
import ui_scaling as ui_scaling_module


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


def _build_menu(size: tuple[int, int]):
    menu = menu_module.Menu.__new__(menu_module.Menu)
    menu.screen = _FakeScreen(*size)
    menu.settings_manager = None
    return menu


def test_graphics_menu_ui_scale_preserves_1366_baseline(monkeypatch):
    monkeypatch.setattr(graphics_menu, 'get_shared_falling_blocks_layer', lambda *args, **kwargs: _DummyFx())
    monkeypatch.setattr(graphics_menu.retro_style, 'get_font', lambda *args, **kwargs: types.SimpleNamespace())

    menu = graphics_menu.GraphicsMenu(_FakeScreen(1366, 768), _DummySettings())

    assert abs(menu._ui_scale() - 1.0) < 0.001


def test_graphics_menu_ui_scale_uses_effective_helper_when_available(monkeypatch):
    monkeypatch.setattr(graphics_menu, 'get_shared_falling_blocks_layer', lambda *args, **kwargs: _DummyFx())
    monkeypatch.setattr(graphics_menu.retro_style, 'get_font', lambda *args, **kwargs: types.SimpleNamespace())
    captured = {}

    def fake_get_projected_effective_scale(screen, *, min_scale, max_scale, reference_size, display_surface=None):
        captured['screen'] = screen
        captured['min_scale'] = min_scale
        captured['max_scale'] = max_scale
        captured['reference_size'] = reference_size
        captured['display_surface'] = display_surface
        return 0.93

    monkeypatch.setattr(graphics_menu, 'get_projected_effective_scale', fake_get_projected_effective_scale)

    menu = graphics_menu.GraphicsMenu(_FakeScreen(2560, 1660), _DummySettings())

    assert math.isclose(menu._ui_scale(), 0.93)
    assert captured['min_scale'] == 0.72
    assert captured['max_scale'] == 1.24
    assert captured['reference_size'] == (1366.0, 768.0)
    assert captured['display_surface'] is None


def test_graphics_menu_ui_scale_hits_phase5_relaxed_cap_on_large_displays(monkeypatch):
    monkeypatch.setattr(graphics_menu, 'get_shared_falling_blocks_layer', lambda *args, **kwargs: _DummyFx())
    monkeypatch.setattr(graphics_menu.retro_style, 'get_font', lambda *args, **kwargs: types.SimpleNamespace())

    menu = graphics_menu.GraphicsMenu(_FakeScreen(2560, 1440), _DummySettings())

    assert math.isclose(menu._ui_scale(), 1.24)


def test_main_menu_ui_scale_preserves_1366_baseline():
    menu = _build_menu((1366, 768))

    assert abs(menu._ui_scale() - 1.0) < 0.001


def test_main_menu_ui_scale_hits_phase5_relaxed_cap_on_large_displays():
    menu = _build_menu((2560, 1440))

    assert math.isclose(menu._ui_scale(), 1.24)


def test_main_menu_manual_ui_scale_preset_only_affects_general_ui():
    menu = _build_menu((2560, 1440))
    previous = ui_scaling_module.get_ui_scale_preset()

    try:
        ui_scaling_module.set_ui_scale_preset('large')
        ui_scale = menu._ui_scale()
        fullscreen_scale = menu._fullscreen_panel_scale()
        content_scale = menu._menu_panel_content_scale()
    finally:
        ui_scaling_module.set_ui_scale_preset(previous)

    assert math.isclose(ui_scale, 1.24 * 1.08)
    assert math.isclose(fullscreen_scale, 1.16)
    assert math.isclose(content_scale, 1.16)


def test_main_menu_scales_use_effective_ui_size_when_available(monkeypatch):
    menu = _build_menu((2560, 1660))
    captured_resolve = []
    captured_projected = []

    def fake_resolve(screen_or_size, *, use_effective_display_size=False, display_surface=None):
        captured_resolve.append((screen_or_size, use_effective_display_size, display_surface))
        return (1200, 700)

    def fake_projected(screen_or_size, *, min_scale, max_scale, reference_size, display_surface=None, apply_preset=True):
        captured_projected.append((screen_or_size, min_scale, max_scale, reference_size, display_surface))
        if reference_size == (1366.0, 768.0):
            return 1.8755490483162518
        return 1.536

    monkeypatch.setattr(menu_module, 'resolve_ui_scale_size', fake_resolve)
    monkeypatch.setattr(menu_module, 'get_projected_effective_scale', fake_projected)

    ui_scale = menu._ui_scale()
    fullscreen_scale = menu._fullscreen_panel_scale()
    content_scale = menu._menu_panel_content_scale()

    assert all(use_effective for _, use_effective, _ in captured_resolve)
    assert math.isclose(ui_scale, max(0.78, min(1.24, min(1200 / 1366.0, 700 / 768.0))))
    assert math.isclose(fullscreen_scale, 1.8755490483162518)
    assert math.isclose(content_scale, 1.536)
    assert len(captured_resolve) == 1
    assert captured_projected == [
        (menu.screen, 0.68, 1.16, (1366.0, 768.0), None),
        (menu.screen, 0.72, 1.16, (1920.0, 1080.0), None),
    ]


def test_credits_reference_size_prefers_effective_ui_size(monkeypatch):
    credits = menu_module.CreditsScreen.__new__(menu_module.CreditsScreen)
    credits.screen = _FakeScreen(2560, 1660)

    def fake_resolve(screen_or_size, *, use_effective_display_size=False, display_surface=None):
        assert screen_or_size is credits.screen
        assert use_effective_display_size is True
        assert display_surface is None
        return (1470, 956)

    monkeypatch.setattr(menu_module, 'resolve_ui_scale_size', fake_resolve)

    assert credits._get_credits_reference_size() == (1470, 956)


def test_credits_ui_scale_uses_projected_effective_scale(monkeypatch):
    credits = menu_module.CreditsScreen.__new__(menu_module.CreditsScreen)
    credits.screen = _FakeScreen(2560, 1660)
    credits._credits_ui_reference_size = (1470, 956)
    captured = {}

    def fake_projected(screen_or_size, *, min_scale, max_scale, reference_size, display_surface=None):
        captured['screen_or_size'] = screen_or_size
        captured['min_scale'] = min_scale
        captured['max_scale'] = max_scale
        captured['reference_size'] = reference_size
        captured['display_surface'] = display_surface
        return 1.92

    monkeypatch.setattr(menu_module, 'get_projected_effective_scale', fake_projected)

    assert math.isclose(credits._credits_ui_scale(), 1.92)
    assert captured['screen_or_size'] is credits.screen
    assert captured['min_scale'] == 0.62
    assert captured['max_scale'] == 1.05
    assert captured['reference_size'] == (1470.0, 956.0)
    assert captured['display_surface'] is None


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


def test_guide_screen_ui_scale_uses_effective_helper_when_available(monkeypatch):
    monkeypatch.setattr(guide_screen, 'get_shared_falling_blocks_layer', lambda *args, **kwargs: _DummyFx())
    captured = {}

    def fake_get_projected_effective_scale(screen, *, min_scale, max_scale, reference_size, display_surface=None):
        captured['screen'] = screen
        captured['min_scale'] = min_scale
        captured['max_scale'] = max_scale
        captured['reference_size'] = reference_size
        captured['display_surface'] = display_surface
        return 0.94

    monkeypatch.setattr(guide_screen, 'get_projected_effective_scale', fake_get_projected_effective_scale)

    guide = guide_screen.GuideScreen(_FakeScreen(2560, 1660))

    assert math.isclose(guide._ui_scale(), 0.94)
    assert captured['min_scale'] == 0.72
    assert captured['max_scale'] == 1.24
    assert captured['reference_size'] == (1366.0, 768.0)
    assert captured['display_surface'] is None


def test_guide_screen_ui_scale_hits_phase5_relaxed_cap_on_large_displays(monkeypatch):
    monkeypatch.setattr(guide_screen, 'get_shared_falling_blocks_layer', lambda *args, **kwargs: _DummyFx())

    guide = guide_screen.GuideScreen(_FakeScreen(2560, 1440))

    assert math.isclose(guide._ui_scale(), 1.24)


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


def test_guide_screen_lb_shortcut_switches_to_previous_tab(monkeypatch):
    monkeypatch.setattr(guide_screen, 'get_shared_falling_blocks_layer', lambda *args, **kwargs: _DummyFx())

    guide = guide_screen.GuideScreen(_FakeScreen(1366, 768))
    guide.selected_tab = 2
    guide.scroll_y = 120
    guide.card_index = 9

    event = types.SimpleNamespace(
        type=guide_screen.pygame.KEYDOWN,
        key=guide_screen.pygame.K_LEFTBRACKET,
        mod=0,
    )

    guide.handle_input(event)

    assert guide.selected_tab == 1
    assert guide.scroll_y == 0
    assert guide.card_index == 0


def test_guide_screen_rb_shortcut_switches_to_next_tab(monkeypatch):
    monkeypatch.setattr(guide_screen, 'get_shared_falling_blocks_layer', lambda *args, **kwargs: _DummyFx())

    guide = guide_screen.GuideScreen(_FakeScreen(1366, 768))
    guide.selected_tab = 2
    guide.scroll_y = 120
    guide.card_index = 9

    event = types.SimpleNamespace(
        type=guide_screen.pygame.KEYDOWN,
        key=guide_screen.pygame.K_RIGHTBRACKET,
        mod=0,
    )

    guide.handle_input(event)

    assert guide.selected_tab == 3
    assert guide.scroll_y == 0
    assert guide.card_index == 0


def test_guide_screen_left_on_cards_switches_to_previous_tab(monkeypatch):
    monkeypatch.setattr(guide_screen, 'get_shared_falling_blocks_layer', lambda *args, **kwargs: _DummyFx())

    guide = guide_screen.GuideScreen(_FakeScreen(1366, 768))
    guide.selected_tab = 2
    guide.scroll_y = 120
    guide.card_index = 9

    event = types.SimpleNamespace(
        type=guide_screen.pygame.KEYDOWN,
        key=guide_screen.pygame.K_LEFT,
        mod=0,
        from_gamepad=True,
    )

    guide.handle_input(event)

    assert guide.selected_tab == 1
    assert guide.scroll_y == 0
    assert guide.card_index == 0


def test_guide_screen_right_on_cards_switches_to_next_tab(monkeypatch):
    monkeypatch.setattr(guide_screen, 'get_shared_falling_blocks_layer', lambda *args, **kwargs: _DummyFx())

    guide = guide_screen.GuideScreen(_FakeScreen(1366, 768))
    guide.selected_tab = 2
    guide.scroll_y = 120
    guide.card_index = 9

    event = types.SimpleNamespace(
        type=guide_screen.pygame.KEYDOWN,
        key=guide_screen.pygame.K_RIGHT,
        mod=0,
        from_gamepad=True,
    )

    guide.handle_input(event)

    assert guide.selected_tab == 3
    assert guide.scroll_y == 0
    assert guide.card_index == 0


def test_graphics_menu_max_scroll_reuses_draw_visible_height(monkeypatch):
    monkeypatch.setattr(graphics_menu, 'get_shared_falling_blocks_layer', lambda *args, **kwargs: _DummyFx())
    monkeypatch.setattr(graphics_menu.retro_style, 'get_font', lambda *args, **kwargs: types.SimpleNamespace())

    menu = graphics_menu.GraphicsMenu(_FakeScreen(1366, 768), _DummySettings())
    metrics = menu._layout_metrics()
    expected = max(0, len(menu.options) * int(metrics['spacing']) - 200)

    assert menu._max_scroll(visible_height=200) == expected
    assert menu._max_scroll() == expected


def test_graphics_menu_keyboard_nav_keeps_selected_row_visible(monkeypatch):
    monkeypatch.setattr(graphics_menu, 'get_shared_falling_blocks_layer', lambda *args, **kwargs: _DummyFx())
    monkeypatch.setattr(graphics_menu.retro_style, 'get_font', lambda *args, **kwargs: types.SimpleNamespace())

    menu = graphics_menu.GraphicsMenu(_FakeScreen(800, 360), _DummySettings())
    menu._last_visible_height = 120
    menu.selected = len(menu.options) - 2

    event = types.SimpleNamespace(type=graphics_menu.pygame.KEYDOWN, key=graphics_menu.pygame.K_DOWN)
    menu.handle_input(event)

    assert menu.selected == len(menu.options) - 1
    assert menu.scroll_offset > 0


def test_gameplay_settings_keyboard_nav_keeps_selected_row_visible(monkeypatch):
    monkeypatch.setattr(gameplay_settings_module, 'get_shared_falling_blocks_layer', lambda *args, **kwargs: _DummyFx())
    monkeypatch.setattr(gameplay_settings_module.retro_style, 'get_font', lambda *args, **kwargs: types.SimpleNamespace())

    menu = gameplay_settings_module.GameplaySettingsMenu(_FakeScreen(800, 260), _DummySettings())
    menu.selected = len(menu.settings) - 1

    event = types.SimpleNamespace(type=gameplay_settings_module.pygame.KEYDOWN, key=gameplay_settings_module.pygame.K_DOWN)
    menu.handle_input(event)

    assert menu.selected == len(menu.settings)
    assert menu.scroll_offset > 0


def test_music_mode_select_keyboard_nav_keeps_selected_row_visible():
    music = menu_module.MusicSettingsScreen.__new__(menu_module.MusicSettingsScreen)
    music.screen = _FakeScreen(500, 320)
    music.modes = [(f'mode-{i}', f'Mode {i}') for i in range(12)]
    music.mode_selected = 7
    music.mode_scroll = 0
    music._title_rect = types.SimpleNamespace(bottom=80)

    event = types.SimpleNamespace(type=menu_module.pygame.KEYDOWN, key=menu_module.pygame.K_DOWN)
    menu_module.MusicSettingsScreen._handle_mode_input(music, event)

    assert music.mode_selected == 8
    assert music.mode_scroll > 0


def test_music_playlist_keyboard_nav_keeps_selected_row_visible():
    music = menu_module.MusicSettingsScreen.__new__(menu_module.MusicSettingsScreen)
    music.screen = _FakeScreen(500, 320)
    music.playlist = [f'track-{i}' for i in range(12)]
    music.playlist_selected = 7
    music.playlist_scroll = 0
    music.playlist_target = 'mode'
    music._title_rect = types.SimpleNamespace(bottom=80)

    event = types.SimpleNamespace(type=menu_module.pygame.KEYDOWN, key=menu_module.pygame.K_DOWN)
    menu_module.MusicSettingsScreen._handle_playlist_input(music, event)

    assert music.playlist_selected == 8
    assert music.playlist_scroll > 0