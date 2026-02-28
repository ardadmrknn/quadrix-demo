from __future__ import annotations

import importlib
import sys
import types
from dataclasses import dataclass


@dataclass
class DummyRect:
    x: int
    width: int


def _install_settings_module_stubs(monkeypatch):
    pygame_stub = types.ModuleType("pygame")

    class Rect:
        def __init__(self, x=0, y=0, width=0, height=0):
            self.x = x
            self.y = y
            self.width = width
            self.height = height

    pygame_stub.Rect = Rect
    pygame_stub.Surface = type("Surface", (), {})
    monkeypatch.setitem(sys.modules, "pygame", pygame_stub)

    constants_stub = types.ModuleType("constants")
    monkeypatch.setitem(sys.modules, "constants", constants_stub)

    retro_style_stub = types.ModuleType("retro_style")
    retro_style_stub.retro_style = types.SimpleNamespace()
    monkeypatch.setitem(sys.modules, "retro_style", retro_style_stub)

    platform_utils_stub = types.ModuleType("platform_utils")
    platform_utils_stub.is_fullscreen_toggle = lambda *args, **kwargs: False
    platform_utils_stub.normalize_mouse_pos = lambda pos=None: pos
    platform_utils_stub.get_mouse_pos = lambda: (0, 0)
    monkeypatch.setitem(sys.modules, "platform_utils", platform_utils_stub)

    background_effects_stub = types.ModuleType("background_effects")
    background_effects_stub.get_shared_falling_blocks_layer = lambda *args, **kwargs: types.SimpleNamespace(update=lambda *a, **k: None, draw=lambda *a, **k: None)
    monkeypatch.setitem(sys.modules, "background_effects", background_effects_stub)

    localization_stub = types.ModuleType("localization")
    localization_stub.t = lambda key: key
    localization_stub.get_text = lambda key: key
    localization_stub.get_language = lambda: "tr"
    localization_stub.set_language = lambda lang: None
    localization_stub.get_language_name = lambda lang: lang
    localization_stub.SUPPORTED_LANGUAGES = ["tr", "en"]
    localization_stub.get_all_languages = lambda: ["tr", "en"]
    monkeypatch.setitem(sys.modules, "localization", localization_stub)

    ui_lang_stub = types.ModuleType("ui_language_profile")
    ui_lang_stub.apply_language_ui_profile = lambda *args, **kwargs: None
    ui_lang_stub.get_font_for_language = lambda *args, **kwargs: None
    monkeypatch.setitem(sys.modules, "ui_language_profile", ui_lang_stub)

    menu_stub = types.ModuleType("menu")
    menu_stub.get_control_actions = lambda: {}
    menu_stub.get_mode_music_entries = lambda: []
    menu_stub.BUILT_IN_TRACK_CHOICES = []
    menu_stub.SUPPORTED_MUSIC_EXTENSIONS = [".ogg", ".mp3", ".wav"]
    monkeypatch.setitem(sys.modules, "menu", menu_stub)

    gamepad_stub = types.ModuleType("gamepad_manager")
    gamepad_stub.get_gamepad_manager = lambda: types.SimpleNamespace(get_button_index_label=lambda idx: f"Btn{idx}")
    gamepad_stub.reload_gamepad_settings = lambda: None
    monkeypatch.setitem(sys.modules, "gamepad_manager", gamepad_stub)


def _import_module(monkeypatch):
    _install_settings_module_stubs(monkeypatch)
    sys.modules.pop("settings_screen_tabbed", None)
    return importlib.import_module("settings_screen_tabbed")


def _make_screen(mod):
    screen = mod.TabbedSettingsScreen.__new__(mod.TabbedSettingsScreen)
    screen.music_volume = 0.0
    screen.sfx_volume = 0.0
    screen.bg_transparency = 0.0
    screen.menu_transparency = 0.0
    captured = []

    def fake_set_value(key, value):
        captured.append((key, value))

    screen._set_value = fake_set_value
    return screen, captured


def test_set_slider_from_x_percent_snaps_and_returns_music_action(monkeypatch):
    mod = _import_module(monkeypatch)
    screen, captured = _make_screen(mod)

    item = {"type": "slider", "key": "music_volume", "min": 0.0, "max": 1.0, "step": 0.05, "percent": True}
    bar_rect = DummyRect(x=100, width=200)

    result = screen._set_slider_from_x(item, 200, bar_rect)

    assert result == "change_music_volume"
    assert captured[-1] == ("music_volume", 0.5)
    assert screen.music_volume == 0.5


def test_set_slider_from_x_clamps_and_updates_sfx_action(monkeypatch):
    mod = _import_module(monkeypatch)
    screen, captured = _make_screen(mod)

    item = {"type": "slider", "key": "sfx_volume", "min": 0.0, "max": 1.0, "step": 0.05, "percent": True}
    bar_rect = DummyRect(x=100, width=200)

    result = screen._set_slider_from_x(item, -999, bar_rect)

    assert result == "change_sfx_volume"
    assert captured[-1] == ("sfx_volume", 0.0)
    assert screen.sfx_volume == 0.0


def test_set_slider_from_x_integer_slider_snaps_and_returns_none(monkeypatch):
    mod = _import_module(monkeypatch)
    screen, captured = _make_screen(mod)

    item = {"type": "slider", "key": "das_delay", "min": 50, "max": 300, "step": 10}
    bar_rect = DummyRect(x=0, width=100)

    result = screen._set_slider_from_x(item, 25, bar_rect)

    assert result is None
    assert captured[-1] == ("das_delay", 110)


def test_set_slider_from_x_step_zero_uses_raw_percent(monkeypatch):
    mod = _import_module(monkeypatch)
    screen, captured = _make_screen(mod)

    item = {"type": "slider", "key": "bg_transparency", "min": 0.0, "max": 1.0, "step": 0, "percent": True}
    bar_rect = DummyRect(x=0, width=100)

    result = screen._set_slider_from_x(item, 33, bar_rect)

    assert result == "change_bg_transparency"
    assert captured[-1] == ("bg_transparency", 0.33)
    assert screen.bg_transparency == 0.33
