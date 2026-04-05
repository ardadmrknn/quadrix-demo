from __future__ import annotations

import importlib
import sys
import types


def _install_stubs(monkeypatch):
    pygame_stub = types.ModuleType('pygame')

    class Rect:
        def __init__(self, x=0, y=0, width=0, height=0):
            self.x = x
            self.y = y
            self.width = width
            self.height = height
            self.left = x
            self.top = y
            self.right = x + width
            self.bottom = y + height
            self.centerx = x + width // 2
            self.centery = y + height // 2
            self.center = (self.centerx, self.centery)
            self.topleft = (x, y)
            self.size = (width, height)

        def collidepoint(self, pos):
            px, py = pos
            return self.x <= px < self.right and self.y <= py < self.bottom

        def inflate(self, dx, dy):
            return Rect(self.x - dx // 2, self.y - dy // 2, self.width + dx, self.height + dy)

        def get_rect(self, **kwargs):
            rect = Rect(self.x, self.y, self.width, self.height)
            for key, value in kwargs.items():
                setattr(rect, key, value)
            return rect

    class Surface:
        def __init__(self, size=(0, 0), *_args, **_kwargs):
            if isinstance(size, tuple):
                self.width, self.height = size
            else:
                self.width, self.height = 0, 0
            self.size = (self.width, self.height)

        def fill(self, *_args, **_kwargs):
            return None

        def blit(self, *_args, **_kwargs):
            return None

        def get_rect(self, **kwargs):
            rect = Rect(0, 0, self.width, self.height)
            for key, value in kwargs.items():
                setattr(rect, key, value)
            return rect

    class RenderedText:
        def __init__(self, text: str, size: int):
            self._text = text
            self._size = max(1, size)

        def get_width(self):
            return max(12, len(self._text) * max(6, self._size // 2))

        def get_height(self):
            return self._size

        def get_rect(self, **kwargs):
            rect = Rect(0, 0, self.get_width(), self.get_height())
            for key, value in kwargs.items():
                setattr(rect, key, value)
            return rect

    class Font:
        def __init__(self, size: int):
            self._size = size

        def render(self, text, *_args, **_kwargs):
            return RenderedText(str(text), self._size)

        def get_height(self):
            return self._size

        def size(self, text):
            rendered = RenderedText(str(text), self._size)
            return rendered.get_width(), rendered.get_height()

    pygame_stub.Rect = Rect
    pygame_stub.Surface = Surface
    pygame_stub.SRCALPHA = 65536
    pygame_stub.KEYDOWN = 768
    pygame_stub.MOUSEBUTTONDOWN = 1025
    pygame_stub.MOUSEBUTTONUP = 1026
    pygame_stub.MOUSEMOTION = 1024
    pygame_stub.MOUSEWHEEL = 1027
    pygame_stub.JOYBUTTONDOWN = 1539
    pygame_stub.JOYAXISMOTION = 1536
    pygame_stub.K_ESCAPE = 27
    pygame_stub.K_RETURN = 13
    pygame_stub.K_KP_ENTER = 271
    pygame_stub.K_LEFT = 276
    pygame_stub.K_RIGHT = 275
    pygame_stub.K_UP = 273
    pygame_stub.K_DOWN = 274
    pygame_stub.K_SPACE = 32
    pygame_stub.K_TAB = 9
    pygame_stub.K_PAGEUP = 280
    pygame_stub.K_PAGEDOWN = 281
    pygame_stub.K_LEFTBRACKET = 91
    pygame_stub.K_RIGHTBRACKET = 93
    pygame_stub.K_DELETE = 127
    pygame_stub.K_BACKSPACE = 8
    pygame_stub.KMOD_SHIFT = 1
    pygame_stub.time = types.SimpleNamespace(get_ticks=lambda: 0)
    pygame_stub.key = types.SimpleNamespace(get_mods=lambda: 0)
    pygame_stub.draw = types.SimpleNamespace(
        rect=lambda *_args, **_kwargs: None,
        line=lambda *_args, **_kwargs: None,
        circle=lambda *_args, **_kwargs: None,
        ellipse=lambda *_args, **_kwargs: None,
        polygon=lambda *_args, **_kwargs: None,
    )
    monkeypatch.setitem(sys.modules, 'pygame', pygame_stub)

    constants_stub = types.ModuleType('constants')
    constants_stub.DEBUG_MODE = False
    monkeypatch.setitem(sys.modules, 'constants', constants_stub)

    retro_style_stub = types.ModuleType('retro_style')
    retro_style_stub.retro_style = types.SimpleNamespace(
        primary=(80, 180, 255),
        draw_background=lambda *_args, **_kwargs: None,
        draw_glass_panel=lambda *_args, **_kwargs: None,
        draw_panel=lambda *_args, **_kwargs: None,
        draw_button=lambda *_args, **_kwargs: None,
        draw_uniform_button=lambda *_args, **_kwargs: None,
        draw_scrollbar=lambda _screen, rect, *_args, **_kwargs: Rect(rect.x, rect.y, rect.width, max(12, rect.height // 4)),
        get_font=lambda size, bold=False: Font(size),
        get_fitting_font=lambda _text, size, _max_width, bold=False, min_size=None: Font(max(min_size or 1, size)),
    )
    monkeypatch.setitem(sys.modules, 'retro_style', retro_style_stub)

    platform_utils_stub = types.ModuleType('platform_utils')
    platform_utils_stub.is_fullscreen_toggle = lambda *args, **kwargs: False
    platform_utils_stub.normalize_mouse_pos = lambda pos=None: pos
    platform_utils_stub.get_mouse_pos = lambda: (0, 0)
    monkeypatch.setitem(sys.modules, 'platform_utils', platform_utils_stub)

    background_effects_stub = types.ModuleType('background_effects')
    background_effects_stub.get_shared_falling_blocks_layer = lambda *args, **kwargs: types.SimpleNamespace(update=lambda *a, **k: None, draw=lambda *a, **k: None)
    monkeypatch.setitem(sys.modules, 'background_effects', background_effects_stub)

    localization_stub = types.ModuleType('localization')
    localization_stub.t = lambda key, *args, **kwargs: key
    localization_stub.get_text = lambda key: key
    localization_stub.get_language = lambda: 'tr'
    localization_stub.set_language = lambda lang: None
    localization_stub.get_language_name = lambda lang: lang
    localization_stub.SUPPORTED_LANGUAGES = ['tr', 'en']
    localization_stub.get_all_languages = lambda: ['tr', 'en']
    monkeypatch.setitem(sys.modules, 'localization', localization_stub)

    ui_lang_stub = types.ModuleType('ui_language_profile')
    ui_lang_stub.apply_language_ui_profile = lambda *args, **kwargs: None
    ui_lang_stub.get_font_for_language = lambda *args, **kwargs: None
    monkeypatch.setitem(sys.modules, 'ui_language_profile', ui_lang_stub)

    menu_stub = types.ModuleType('menu')
    menu_stub.get_control_actions = lambda: {}
    menu_stub.get_mode_music_entries = lambda: []
    menu_stub.get_campaign_phase_entries = lambda: []
    menu_stub.CAMPAIGN_PHASE_WORLDS = []
    menu_stub.BUILT_IN_TRACK_CHOICES = []
    menu_stub.SUPPORTED_MUSIC_EXTENSIONS = ['.ogg', '.mp3', '.wav']
    monkeypatch.setitem(sys.modules, 'menu', menu_stub)

    gamepad_stub = types.ModuleType('gamepad_manager')
    gamepad_stub.get_gamepad_manager = lambda: types.SimpleNamespace(get_button_index_label=lambda idx: f'Btn{idx}')
    gamepad_stub.reload_gamepad_settings = lambda: None
    monkeypatch.setitem(sys.modules, 'gamepad_manager', gamepad_stub)


def _import_module(monkeypatch):
    _install_stubs(monkeypatch)
    sys.modules.pop('settings_screen_tabbed', None)
    return importlib.import_module('settings_screen_tabbed')


class _FakeScreen:
    def __init__(self, width: int, height: int):
        self._size = (width, height)
        self._clip = None

    def get_size(self):
        return self._size

    def get_width(self):
        return self._size[0]

    def get_height(self):
        return self._size[1]

    def blit(self, *_args, **_kwargs):
        return None

    def set_clip(self, rect):
        self._clip = rect


def _make_screen(mod, width: int, height: int, item_count: int = 4):
    screen = mod.TabbedSettingsScreen.__new__(mod.TabbedSettingsScreen)
    screen.screen = _FakeScreen(width, height)
    screen._ui_reference_size = (1366.0, 768.0)
    screen._ui_scale_current = 1.0
    screen._font_scale_signature = None
    screen._base_font_title_size = 36
    screen._base_font_tab_size = 20
    screen._base_font_section_size = 20
    screen._base_font_label_size = 24
    screen._base_font_value_size = 22
    screen._base_font_small_size = 18
    screen._base_font_hint_size = 16
    screen._tab_items = [{'type': 'section', 'label_tr': 'BOLUM', 'label_en': 'SECTION'}] + [
        {'type': 'toggle', 'key': f'item_{idx}', 'label_tr': f'Oge {idx}', 'label_en': f'Item {idx}'}
        for idx in range(item_count)
    ]
    screen._selectable_indices = list(range(1, len(screen._tab_items)))
    screen.selected = 0
    screen.scroll_offset = 0
    screen.option_rects = []
    screen._keybind_slot_rects = []
    screen._help_icon_rects = []
    screen._slider_bar_rects = {}
    screen._slider_action_rects = {}
    screen._tab_rects = []
    screen._settings_sb_thumb_rect = None
    screen._settings_sb_container_rect = None
    screen._settings_sb_drag_active = False
    screen._settings_sb_drag_offset_y = 0
    screen._slider_drag_active = False
    screen._slider_drag_key = ''
    screen._slider_drag_item = None
    screen._slider_drag_bar_rect = None
    screen._campaign_phase_select_active = False
    screen._playlist_edit_active = False
    screen._music_picker_open = False
    screen._waiting_for_key = False
    screen._display_mode_confirm_active = False
    screen._vsync_prompt_active = False
    screen._swallow_next_keydown = False
    screen.current_language = 'tr'
    return screen


def test_settings_ui_scale_preserves_1366_baseline(monkeypatch):
    mod = _import_module(monkeypatch)
    screen = _make_screen(mod, 1366, 768)

    assert abs(screen._ui_scale() - 1.0) < 0.001


def test_settings_panel_and_content_rects_grow_on_large_displays(monkeypatch):
    mod = _import_module(monkeypatch)
    baseline = _make_screen(mod, 1366, 768)
    large = _make_screen(mod, 2560, 1440)

    baseline_panel = baseline._panel_rect()
    large_panel = large._panel_rect()
    baseline_content = baseline._content_rect(baseline_panel)
    large_content = large._content_rect(large_panel)

    assert large._ui_scale() > 1.0
    assert large_panel.width > baseline_panel.width
    assert large_panel.height > baseline_panel.height
    assert large_content.width > baseline_content.width
    assert large_content.height > baseline_content.height


def test_settings_max_scroll_uses_scaled_layout_metrics(monkeypatch):
    mod = _import_module(monkeypatch)
    screen = _make_screen(mod, 2560, 1440, item_count=8)

    panel = screen._panel_rect()
    content = screen._content_rect(panel)
    metrics = screen._layout_metrics()
    expected = max(
        0,
        int(metrics['section_height']) + 8 * int(metrics['row_height']) - content.height,
    )

    assert screen._max_scroll(content) == expected


def test_settings_option_rects_match_mouse_selection_after_scroll(monkeypatch):
    mod = _import_module(monkeypatch)
    screen = _make_screen(mod, 1366, 768, item_count=4)
    screen._draw_section_header = lambda *args, **kwargs: None
    screen._draw_setting_item = lambda *args, **kwargs: None
    screen._draw_help_tooltip = lambda *args, **kwargs: None

    metrics = screen._layout_metrics()
    screen.scroll_offset = int(metrics['row_height'])
    content = screen._content_rect(screen._panel_rect())
    screen._draw_content(content)

    target_rect = screen.option_rects[2]
    event = types.SimpleNamespace(
        type=mod.pygame.MOUSEMOTION,
        pos=(target_rect.x + 5, target_rect.y + 5),
    )

    result = screen.handle_input(event)

    assert result is None
    assert target_rect.width > 0
    assert screen.selected == 2


def test_settings_refresh_fonts_rebuilds_when_language_changes(monkeypatch):
    mod = _import_module(monkeypatch)
    calls = []

    def _tracked_get_font(size, bold=False):
        calls.append((size, bold))
        return types.SimpleNamespace()

    monkeypatch.setattr(mod.retro_style, 'get_font', _tracked_get_font)

    screen = _make_screen(mod, 1366, 768)
    screen.current_language = 'tr'

    screen._refresh_fonts()
    first_call_count = len(calls)

    screen.current_language = 'en'
    screen._refresh_fonts()

    assert first_call_count > 0
    assert len(calls) > first_call_count


def test_settings_slider_left_hit_rect_scales_and_handles_click(monkeypatch):
    mod = _import_module(monkeypatch)
    screen = _make_screen(mod, 2560, 1440, item_count=1)
    screen._tab_items = [
        {
            'type': 'slider',
            'key': 'music_volume',
            'label_tr': 'Muzik',
            'label_en': 'Music',
            'min': 0.0,
            'max': 1.0,
            'step': 0.05,
            'percent': True,
        }
    ]
    screen._selectable_indices = [0]
    screen.selected = 0
    screen.music_volume = 0.5
    screen._music_volume_vis = 0.5
    screen.menu_music_volume = 0.5
    screen._menu_music_volume_vis = 0.5
    screen.sfx_volume = 0.5
    screen._sfx_volume_vis = 0.5
    screen._get_value = lambda _key: 0.5
    screen._draw_help_tooltip = lambda *args, **kwargs: None

    content = screen._content_rect(screen._panel_rect())
    screen._draw_content(content)

    left_rect = screen._slider_action_rects['music_volume']['left_rect']
    assert left_rect.width > 24

    captured = []
    screen._handle_setting_action = lambda key: captured.append(key) or key
    event = types.SimpleNamespace(
        type=mod.pygame.MOUSEBUTTONDOWN,
        button=1,
        pos=(left_rect.x + 1, screen.option_rects[0].y + max(1, screen.option_rects[0].height // 2)),
    )

    result = screen.handle_input(event)

    assert result == mod.pygame.K_LEFT
    assert captured == [mod.pygame.K_LEFT]


def test_settings_scrollbar_arrow_click_uses_scaled_step(monkeypatch):
    mod = _import_module(monkeypatch)
    screen = _make_screen(mod, 2560, 1440, item_count=24)
    screen._draw_section_header = lambda *args, **kwargs: None
    screen._draw_setting_item = lambda *args, **kwargs: None
    screen._draw_help_tooltip = lambda *args, **kwargs: None

    panel = screen._panel_rect()
    content = screen._content_rect(panel)
    step = int(screen._layout_metrics()['scroll_step'])
    screen.scroll_offset = step * 4
    screen._draw_content(content)
    screen._settings_sb_thumb_rect = None

    scrollbar = screen._settings_scrollbar_layout(panel, content)
    up_rect = scrollbar['up_arrow_rect']
    down_rect = scrollbar['down_arrow_rect']
    start_scroll = screen.scroll_offset

    down_event = types.SimpleNamespace(
        type=mod.pygame.MOUSEBUTTONDOWN,
        button=1,
        pos=(down_rect.x + max(1, down_rect.width // 2), down_rect.y + max(1, down_rect.height // 2)),
    )
    down_result = screen.handle_input(down_event)

    assert down_result is None
    assert screen.scroll_offset == min(start_scroll + step, screen._max_scroll(content))

    up_event = types.SimpleNamespace(
        type=mod.pygame.MOUSEBUTTONDOWN,
        button=1,
        pos=(up_rect.x + max(1, up_rect.width // 2), up_rect.y + max(1, up_rect.height // 2)),
    )
    up_result = screen.handle_input(up_event)

    assert up_result is None
    assert screen.scroll_offset == start_scroll