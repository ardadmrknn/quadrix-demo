from __future__ import annotations

import importlib
import sys
import types
from types import SimpleNamespace
from unittest.mock import Mock


def _install_settings_module_stubs(monkeypatch):
    pygame_stub = types.ModuleType('pygame')

    class Rect:
        def __init__(self, x=0, y=0, width=0, height=0):
            self.x = x
            self.y = y
            self.width = width
            self.height = height

    pygame_stub.Rect = Rect
    pygame_stub.Surface = type('Surface', (), {})
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
    pygame_stub.SRCALPHA = 65536
    pygame_stub.time = types.SimpleNamespace(get_ticks=lambda: 0)
    pygame_stub.key = types.SimpleNamespace(get_mods=lambda: 0)
    monkeypatch.setitem(sys.modules, 'pygame', pygame_stub)

    constants_stub = types.ModuleType('constants')
    constants_stub.DEBUG_MODE = False
    monkeypatch.setitem(sys.modules, 'constants', constants_stub)

    retro_style_stub = types.ModuleType('retro_style')
    retro_style_stub.retro_style = types.SimpleNamespace(
        draw_background=lambda *args, **kwargs: None,
        get_font=lambda *args, **kwargs: types.SimpleNamespace(render=lambda *a, **k: None),
    )
    monkeypatch.setitem(sys.modules, 'retro_style', retro_style_stub)

    platform_utils_stub = types.ModuleType('platform_utils')
    platform_utils_stub.is_fullscreen_toggle = lambda *args, **kwargs: False
    platform_utils_stub.normalize_mouse_pos = lambda pos=None: pos
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
    menu_stub.BUILT_IN_TRACK_CHOICES = []
    menu_stub.SUPPORTED_MUSIC_EXTENSIONS = ['.ogg', '.mp3', '.wav']
    monkeypatch.setitem(sys.modules, 'menu', menu_stub)

    gamepad_stub = types.ModuleType('gamepad_manager')
    gamepad_stub.get_gamepad_manager = lambda: types.SimpleNamespace(get_button_index_label=lambda idx: f'Btn{idx}')
    gamepad_stub.reload_gamepad_settings = lambda: None
    monkeypatch.setitem(sys.modules, 'gamepad_manager', gamepad_stub)


def _import_module(monkeypatch):
    _install_settings_module_stubs(monkeypatch)
    sys.modules.pop('settings_screen_tabbed', None)
    return importlib.import_module('settings_screen_tabbed')


def _make_screen_for_playlist_editor(mod, initial_playlist=None):
    if initial_playlist is None:
        initial_playlist = []

    screen = mod.TabbedSettingsScreen.__new__(mod.TabbedSettingsScreen)
    screen.settings_manager = Mock()
    screen.settings_manager.get_mode_music_playlist.return_value = list(initial_playlist)
    screen.settings_manager.set_mode_music_playlist = Mock()

    screen._music_picker_open = False
    screen._music_picker_mode_key = None

    screen._playlist_edit_active = False
    screen._playlist_edit_mode_key = None
    screen._playlist_edit_items = []
    screen._playlist_edit_selected = 0
    screen._playlist_edit_scroll = 0
    screen._playlist_edit_picker_open = False
    screen._playlist_edit_picker_selected = 0
    screen._playlist_edit_picker_scroll = 0
    screen._playlist_edit_item_rects = []
    screen._playlist_edit_picker_rects = []

    screen._track_options = [
        {'label': 'Track 1', 'value': 'track1'},
        {'label': 'Track 2', 'value': 'track2'},
    ]
    screen._picker_max_scroll = lambda visible_h, item_h, gap: 0
    screen._playlist_picker_max_scroll = lambda visible_h, item_h, gap: 0

    return screen


def test_open_mode_playlist_editor_sets_expected_state(monkeypatch):
    mod = _import_module(monkeypatch)
    screen = _make_screen_for_playlist_editor(mod, ['track1', 'track2'])
    screen._music_picker_open = True
    screen._music_picker_mode_key = 'sprint'

    screen.open_mode_playlist_editor('classic')

    assert screen._playlist_edit_active is True
    assert screen._playlist_edit_mode_key == 'classic'
    assert screen._playlist_edit_items == ['track1', 'track2']
    assert screen._music_picker_open is False
    assert screen._music_picker_mode_key is None


def test_close_mode_playlist_editor_deactivates_overlay(monkeypatch):
    mod = _import_module(monkeypatch)
    screen = _make_screen_for_playlist_editor(mod, ['track1'])
    screen.open_mode_playlist_editor('classic')

    screen._close_mode_playlist_editor()

    assert screen._playlist_edit_active is False


def test_playlist_editor_esc_closes_and_returns_none(monkeypatch):
    mod = _import_module(monkeypatch)
    screen = _make_screen_for_playlist_editor(mod, ['track1'])
    screen.open_mode_playlist_editor('classic')

    event = SimpleNamespace(type=mod.pygame.KEYDOWN, key=mod.pygame.K_ESCAPE)
    result = screen._handle_mode_playlist_edit_input(event)

    assert result is None
    assert screen._playlist_edit_active is False


def test_playlist_editor_delete_removes_selected_and_saves(monkeypatch):
    mod = _import_module(monkeypatch)
    screen = _make_screen_for_playlist_editor(mod, ['track1', 'track2'])
    screen.open_mode_playlist_editor('classic')
    screen._playlist_edit_selected = 1

    event = SimpleNamespace(type=mod.pygame.KEYDOWN, key=mod.pygame.K_DELETE)
    result = screen._handle_mode_playlist_edit_input(event)

    assert screen._playlist_edit_items == ['track2']
    screen.settings_manager.set_mode_music_playlist.assert_called_once_with('classic', ['track2'])
    assert result == 'mode_playlist_changed'


def test_playlist_editor_return_on_add_row_opens_picker(monkeypatch):
    mod = _import_module(monkeypatch)
    screen = _make_screen_for_playlist_editor(mod, ['track1'])
    screen.open_mode_playlist_editor('classic')
    screen._playlist_edit_selected = 0

    event = SimpleNamespace(type=mod.pygame.KEYDOWN, key=mod.pygame.K_RETURN)
    result = screen._handle_mode_playlist_edit_input(event)

    assert result is None
    assert screen._playlist_edit_picker_open is True


def test_handle_input_playlist_edit_guard_calls_only_playlist_handler(monkeypatch):
    mod = _import_module(monkeypatch)
    screen = mod.TabbedSettingsScreen.__new__(mod.TabbedSettingsScreen)

    screen._swallow_next_keydown = False
    screen._playlist_edit_active = True
    screen._music_picker_open = True
    screen._waiting_for_key = True
    screen._display_mode_confirm_active = True
    screen._vsync_prompt_active = True

    screen._handle_mode_playlist_edit_input = Mock(return_value='playlist_handler_called')
    screen._handle_music_picker_input = Mock()
    screen._handle_display_mode_confirm = Mock(return_value='display_handler_called')
    screen._handle_vsync_prompt = Mock(return_value='vsync_handler_called')

    event = SimpleNamespace(type=999, key=111)
    result = screen.handle_input(event)

    assert result == 'playlist_handler_called'
    screen._handle_mode_playlist_edit_input.assert_called_once_with(event)
    screen._handle_music_picker_input.assert_not_called()
    screen._handle_display_mode_confirm.assert_not_called()
    screen._handle_vsync_prompt.assert_not_called()


def test_draw_calls_playlist_edit_overlay_when_active(monkeypatch):
    mod = _import_module(monkeypatch)
    mod.retro_style.draw_background = Mock()

    screen = mod.TabbedSettingsScreen.__new__(mod.TabbedSettingsScreen)
    screen.screen = SimpleNamespace(get_size=lambda: (1280, 720))
    screen._anim_last_tick = 0
    screen.music_volume = 0.3
    screen.sfx_volume = 0.4
    screen.menu_music_volume = 0.5
    screen._music_volume_vis = 0.3
    screen._sfx_volume_vis = 0.4
    screen._menu_music_volume_vis = 0.5
    screen.background_fx = SimpleNamespace(update=Mock(), draw=Mock())

    sentinel = object()
    screen._panel_rect = Mock(return_value=sentinel)
    screen._draw_panel = Mock()
    screen._draw_title = Mock()
    screen._tab_bar_rect = Mock(return_value=sentinel)
    screen._draw_tab_bar = Mock()
    screen._content_rect = Mock(return_value=sentinel)
    screen._draw_content = Mock()
    screen._draw_vsync_prompt = Mock()
    screen._draw_display_mode_confirm_panel = Mock()
    screen._draw_music_picker = Mock()
    screen._draw_mode_playlist_edit_overlay = Mock()

    screen._vsync_prompt_active = False
    screen._display_mode_confirm_active = False
    screen._music_picker_open = False
    screen._playlist_edit_active = True

    screen.draw()

    screen._draw_mode_playlist_edit_overlay.assert_called_once_with()
    screen._draw_music_picker.assert_not_called()


def test_backspace_deletes_item(monkeypatch):
    mod = _import_module(monkeypatch)
    screen = _make_screen_for_playlist_editor(mod, ['track1', 'track2'])
    screen.open_mode_playlist_editor('classic')
    screen._playlist_edit_selected = 1

    event = SimpleNamespace(type=mod.pygame.KEYDOWN, key=mod.pygame.K_BACKSPACE)
    result = screen._handle_mode_playlist_edit_input(event)

    assert screen._playlist_edit_items == ['track2']
    screen.settings_manager.set_mode_music_playlist.assert_called_once_with('classic', ['track2'])
    assert result == 'mode_playlist_changed'
