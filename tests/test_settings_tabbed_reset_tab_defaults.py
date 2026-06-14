from __future__ import annotations

import copy
import importlib
import sys
import types


def _install_stubs(monkeypatch):
    pygame_stub = types.ModuleType("pygame")

    class Rect:
        def __init__(self, x=0, y=0, width=0, height=0):
            self.x = int(x)
            self.y = int(y)
            self.width = int(width)
            self.height = int(height)

        @property
        def right(self):
            return self.x + self.width

        @property
        def bottom(self):
            return self.y + self.height

        def collidepoint(self, pos):
            px, py = pos
            return self.x <= px < self.right and self.y <= py < self.bottom

    pygame_stub.Rect = Rect
    pygame_stub.Surface = type("Surface", (), {})
    pygame_stub.SRCALPHA = 1
    monkeypatch.setitem(sys.modules, "pygame", pygame_stub)

    constants_stub = types.ModuleType("constants")
    monkeypatch.setitem(sys.modules, "constants", constants_stub)

    retro_style_stub = types.ModuleType("retro_style")
    retro_style_stub.retro_style = types.SimpleNamespace(
        primary=(80, 160, 255),
        get_font=lambda *args, **kwargs: types.SimpleNamespace(render=lambda *a, **k: None),
        get_fitting_font=lambda *args, **kwargs: types.SimpleNamespace(render=lambda *a, **k: None),
        draw_uniform_button=lambda *args, **kwargs: None,
    )
    monkeypatch.setitem(sys.modules, "retro_style", retro_style_stub)

    platform_utils_stub = types.ModuleType("platform_utils")
    platform_utils_stub.normalize_mouse_pos = lambda pos=None: pos
    platform_utils_stub.get_mouse_pos = lambda: (0, 0)
    monkeypatch.setitem(sys.modules, "platform_utils", platform_utils_stub)

    background_effects_stub = types.ModuleType("background_effects")
    background_effects_stub.get_shared_falling_blocks_layer = lambda *args, **kwargs: types.SimpleNamespace(
        update=lambda *a, **k: None,
        draw=lambda *a, **k: None,
    )
    monkeypatch.setitem(sys.modules, "background_effects", background_effects_stub)

    localization_stub = types.ModuleType("localization")
    localization_stub.t = lambda key, **kwargs: key
    localization_stub.get_text = lambda key, **kwargs: key
    localization_stub.get_language = lambda: "tr"
    localization_stub.set_language = lambda lang: None
    localization_stub.get_language_name = lambda lang: str(lang)
    localization_stub.SUPPORTED_LANGUAGES = ["tr", "en"]
    localization_stub.get_all_languages = lambda: ["tr", "en"]
    monkeypatch.setitem(sys.modules, "localization", localization_stub)

    ui_language_profile_stub = types.ModuleType("ui_language_profile")
    ui_language_profile_stub.apply_language_ui_profile = lambda *args, **kwargs: None
    ui_language_profile_stub.get_font_for_language = lambda *args, **kwargs: None
    monkeypatch.setitem(sys.modules, "ui_language_profile", ui_language_profile_stub)

    menu_stub = types.ModuleType("menu")
    menu_stub.get_control_actions = lambda: {
        "single_player": [],
        "pvp.player1": [],
        "pvp.player2": [],
    }
    menu_stub.get_mode_music_entries = lambda: []
    menu_stub.get_campaign_phase_entries = lambda: []
    menu_stub.BUILT_IN_TRACK_CHOICES = []
    menu_stub.SUPPORTED_MUSIC_EXTENSIONS = [".ogg", ".mp3", ".wav"]
    monkeypatch.setitem(sys.modules, "menu", menu_stub)

    gamepad_stub = types.ModuleType("gamepad_manager")
    gamepad_stub.get_gamepad_manager = lambda: types.SimpleNamespace(get_button_index_label=lambda idx, gp_type=None: f"Btn{idx}")
    gamepad_stub.reload_gamepad_settings = lambda: None
    monkeypatch.setitem(sys.modules, "gamepad_manager", gamepad_stub)

    promptfont_stub = types.ModuleType("promptfont_support")
    promptfont_stub.get_gamepad_prompt_glyph = lambda *args, **kwargs: None
    promptfont_stub.fit_promptfont_glyph_surface = lambda *args, **kwargs: None
    monkeypatch.setitem(sys.modules, "promptfont_support", promptfont_stub)

    ui_scaling_stub = types.ModuleType("ui_scaling")
    ui_scaling_stub.UI_SCALE_PRESETS = ["compact", "normal", "large"]
    ui_scaling_stub.get_projected_effective_scale = lambda *args, **kwargs: 1.0
    ui_scaling_stub.normalize_ui_scale_preset = lambda value: str(value or "").strip().lower() if str(value or "").strip().lower() in {"compact", "normal", "large"} else "normal"
    ui_scaling_stub.scale_px = lambda value, scale, minimum=1: max(int(minimum), int(round(float(value) * float(scale))))
    monkeypatch.setitem(sys.modules, "ui_scaling", ui_scaling_stub)


def _import_module(monkeypatch):
    _install_stubs(monkeypatch)
    sys.modules.pop("settings_screen_tabbed", None)
    return importlib.import_module("settings_screen_tabbed")


class _FakeSettingsManager:
    def __init__(self):
        self.default_settings = {
            "das_delay": 170,
            "das_repeat": 50,
            "soft_drop_speed": 50,
            "vsync": True,
            "fps_limit": 0,
            "ui_scale_preset": "normal",
            "show_ghost": True,
            "bg_transparency": 0.3,
            "effects_opacity": 1.0,
            "menu_transparency": 1.0,
            "particle_effects": "medium",
            "music_enabled": True,
            "music_volume": 0.3,
            "menu_music_volume": 0.3,
            "sound_enabled": True,
            "sfx_volume": 0.5,
            "mute_all": False,
            "music_shuffle": False,
            "menu_music": "main_1",
            "game_music": "klasik_1",
            "menu_music_playlist": ["main_1"],
            "game_music_playlist": ["klasik_1"],
            "campaign_music_playlist": ["klasik_1"],
            "mode_music_overrides": {},
            "mode_music_playlists": {"classic": ["file:klasik_1.mp3"]},
            "controls": {
                "single_player": {
                    "move_left": {"primary": "left", "secondary": "a"},
                    "move_right": {"primary": "right", "secondary": "d"},
                },
                "pvp": {
                    "player1": {"move_left": "a"},
                    "player2": {"move_left": "left"},
                },
                "debug": {
                    "coop_spawner_left": "",
                    "coop_spawner_right": "",
                },
                "gamepad": {
                    "enabled": True,
                    "rumble": "high",
                    "hard_drop": {"primary": 0, "secondary": -1},
                },
            },
        }
        self.settings = copy.deepcopy(self.default_settings)
        self.saved = False

    def get(self, key, default=None):
        if key in self.settings:
            return copy.deepcopy(self.settings[key])
        return copy.deepcopy(default)

    def set(self, key, value):
        self.settings[key] = copy.deepcopy(value)

    def update(self, **kwargs):
        for key, value in kwargs.items():
            self.settings[key] = copy.deepcopy(value)

    def save_settings(self):
        self.saved = True

    def get_controls(self):
        return copy.deepcopy(self.settings.get("controls", {}))

    def get_default_controls(self):
        return copy.deepcopy(self.default_settings.get("controls", {}))

    def get_mode_music_overrides(self):
        return copy.deepcopy(self.settings.get("mode_music_overrides", {}))


def _make_screen(mod, sm, tab_index):
    screen = mod.TabbedSettingsScreen.__new__(mod.TabbedSettingsScreen)
    screen.settings_manager = sm
    screen.current_tab = tab_index
    screen.vsync = bool(sm.get("vsync", True))
    screen._control_config = sm.get_controls()
    screen._mode_music_overrides = sm.get_mode_music_overrides()
    return screen


def test_reset_game_tab_restores_default_values(monkeypatch):
    mod = _import_module(monkeypatch)
    sm = _FakeSettingsManager()
    sm.settings["das_delay"] = 290
    sm.settings["das_repeat"] = 110
    sm.settings["soft_drop_speed"] = 95

    screen = _make_screen(mod, sm, tab_index=0)
    action = screen._reset_current_tab_to_defaults()

    assert action == "reset_tab_defaults:game"
    assert sm.settings["das_delay"] == 170
    assert sm.settings["das_repeat"] == 50
    assert sm.settings["soft_drop_speed"] == 50


def test_reset_controls_tab_restores_defaults_and_reloads_gamepad(monkeypatch):
    mod = _import_module(monkeypatch)
    sm = _FakeSettingsManager()
    sm.settings["controls"]["single_player"]["move_left"]["primary"] = "q"
    reloaded = []
    monkeypatch.setattr(mod, "reload_gamepad_settings", lambda: reloaded.append(True))

    screen = _make_screen(mod, sm, tab_index=3)
    action = screen._reset_current_tab_to_defaults()

    assert action == "reset_tab_defaults:controls"
    assert sm.settings["controls"]["single_player"]["move_left"]["primary"] == "left"
    assert reloaded == [True]


def test_tab_reset_button_rect_hidden_on_non_reset_tab(monkeypatch):
    mod = _import_module(monkeypatch)
    sm = _FakeSettingsManager()
    screen = _make_screen(mod, sm, tab_index=4)
    screen._s = lambda value, minimum=1: int(value)
    screen._layout_metrics = lambda: {
        "panel": mod.pygame.Rect(100, 80, 900, 620),
        "title_pad_x": 20,
    }

    rect = screen._tab_reset_button_rect()

    assert rect is None


def test_tab_reset_button_rect_visible_on_display_tab(monkeypatch):
    mod = _import_module(monkeypatch)
    sm = _FakeSettingsManager()
    screen = _make_screen(mod, sm, tab_index=1)
    screen._s = lambda value, minimum=1: int(value)
    screen._layout_metrics = lambda: {
        "panel": mod.pygame.Rect(100, 80, 900, 620),
        "title_pad_x": 20,
    }

    rect = screen._tab_reset_button_rect()

    assert rect is not None
    assert rect.width > 0
    assert rect.height > 0


def test_debug_keybind_capture_updates_controls(monkeypatch):
    mod = _import_module(monkeypatch)
    sm = _FakeSettingsManager()
    screen = _make_screen(mod, sm, tab_index=5)
    mod.pygame.key = types.SimpleNamespace(name=lambda key_code: "h")
    screen._pending_keybind_item = {"section": "debug", "action_key": "coop_spawner_left"}
    screen._pending_keybind_slot = "primary"

    screen._apply_captured_key(104)

    assert screen._control_config["debug"]["coop_spawner_left"] == "h"
    assert sm.settings["controls"]["debug"]["coop_spawner_left"] == "h"
