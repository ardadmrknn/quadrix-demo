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

    class Surface:
        def __init__(self, size=(0, 0), *_args, **_kwargs):
            self.size = size

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
    monkeypatch.setitem(sys.modules, 'pygame', pygame_stub)

    constants_stub = types.ModuleType('constants')
    constants_stub.DEBUG_MODE = False
    monkeypatch.setitem(sys.modules, 'constants', constants_stub)

    retro_style_stub = types.ModuleType('retro_style')
    retro_style_stub.retro_style = types.SimpleNamespace(
        get_font=lambda *args, **kwargs: None,
        get_fitting_font=lambda *args, **kwargs: None,
    )
    monkeypatch.setitem(sys.modules, 'retro_style', retro_style_stub)

    platform_utils_stub = types.ModuleType('platform_utils')
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
    menu_stub.get_control_actions = lambda: {
        'single_player': [],
        'pvp.player1': [],
        'pvp.player2': [],
    }
    menu_stub.get_mode_music_entries = lambda: []
    menu_stub.get_campaign_phase_entries = lambda: []
    menu_stub.BUILT_IN_TRACK_CHOICES = []
    menu_stub.SUPPORTED_MUSIC_EXTENSIONS = ['.ogg', '.mp3']
    monkeypatch.setitem(sys.modules, 'menu', menu_stub)

    gamepad_stub = types.ModuleType('gamepad_manager')
    gamepad_stub.get_gamepad_manager = lambda: types.SimpleNamespace(get_button_index_label=lambda idx: f'Btn{idx}')
    gamepad_stub.reload_gamepad_settings = lambda: None
    monkeypatch.setitem(sys.modules, 'gamepad_manager', gamepad_stub)

    ui_scaling_stub = types.ModuleType('ui_scaling')
    ui_scaling_stub.UI_SCALE_PRESETS = ['compact', 'normal', 'large']
    ui_scaling_stub.get_effective_scale = lambda *args, **kwargs: 1.0
    ui_scaling_stub.get_projected_effective_scale = lambda *args, **kwargs: 1.0
    ui_scaling_stub.normalize_ui_scale_preset = lambda value: value if value in {'compact', 'normal', 'large'} else 'normal'
    ui_scaling_stub.scale_px = lambda value, scale, minimum=1: max(minimum, int(round(float(value) * float(scale))))
    monkeypatch.setitem(sys.modules, 'ui_scaling', ui_scaling_stub)


def _import_module(monkeypatch):
    _install_stubs(monkeypatch)
    sys.modules.pop('settings_screen_tabbed', None)
    return importlib.import_module('settings_screen_tabbed')


def test_controls_tab_contains_gamepad_rumble_slider(monkeypatch):
    mod = _import_module(monkeypatch)

    items = mod._build_tab_content('controls', sm=types.SimpleNamespace(), show_debug=False)

    rumble_idx = next(i for i, item in enumerate(items) if item.get('key') == 'ctrl_gp_rumble')
    first_gamepad_bind_idx = next(i for i, item in enumerate(items) if item.get('key') == 'ctrl_gp_hard_drop')

    assert items[rumble_idx]['type'] == 'slider'
    assert rumble_idx < first_gamepad_bind_idx


def test_ctrl_gp_rumble_reads_and_persists_control_config(monkeypatch):
    mod = _import_module(monkeypatch)

    class _FakeSettingsManager:
        @staticmethod
        def gamepad_rumble_slider_value(value):
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return max(0, min(3, int(value)))
            return {'off': 0, 'low': 1, 'medium': 2, 'high': 3}.get(str(value), 3)

        @staticmethod
        def gamepad_rumble_level_from_slider(value):
            return {0: 'off', 1: 'low', 2: 'medium', 3: 'high'}.get(int(value), 'high')

    screen = mod.TabbedSettingsScreen.__new__(mod.TabbedSettingsScreen)
    screen.settings_manager = _FakeSettingsManager()
    screen._control_config = {'gamepad': {'rumble': 'medium'}}
    persisted = []
    screen._persist_controls = lambda: persisted.append(screen._control_config['gamepad']['rumble'])

    assert screen._get_value('ctrl_gp_rumble') == 2

    screen._set_value('ctrl_gp_rumble', 1)

    assert screen._control_config['gamepad']['rumble'] == 'low'
    assert persisted == ['low']