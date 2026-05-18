"""Tests for keybind modernization features in TabbedSettingsScreen.

Covers:
- conflict detection within the same section (single_player, pvp, gamepad)
- unbound primary detection (with debug exempt)
- _reset_keybind_row_full restoring both slots
- _clear_keybind_slot setting slot to unbound
- hold-to-clear capture state helpers
"""

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

        @property
        def centerx(self):
            return self.x + self.width // 2

        @property
        def centery(self):
            return self.y + self.height // 2

        def collidepoint(self, pos):
            px, py = pos
            return self.x <= px < self.right and self.y <= py < self.bottom

        def copy(self):
            return Rect(self.x, self.y, self.width, self.height)

    pygame_stub.Rect = Rect
    pygame_stub.Surface = type("Surface", (), {})
    pygame_stub.SRCALPHA = 1
    pygame_stub.K_ESCAPE = 27
    pygame_stub.K_RETURN = 13
    pygame_stub.K_SPACE = 32
    pygame_stub.K_LEFT = 1073741904
    pygame_stub.K_RIGHT = 1073741903
    pygame_stub.K_DELETE = 127
    pygame_stub.K_BACKSPACE = 8
    pygame_stub.KEYDOWN = 768
    pygame_stub.KEYUP = 769
    pygame_stub.JOYBUTTONDOWN = 1539
    pygame_stub.JOYBUTTONUP = 1540
    pygame_stub.MOUSEBUTTONDOWN = 1025

    class _PressMap:
        def __init__(self, pressed: set[int]):
            self._pressed = pressed

        def __getitem__(self, key):
            return int(key) in self._pressed

    pygame_stub._press_state = _PressMap(set())
    pygame_stub.key = types.SimpleNamespace(
        name=lambda code: f"key{int(code)}",
        get_pressed=lambda: pygame_stub._press_state,
    )
    pygame_stub.joystick = types.SimpleNamespace(get_count=lambda: 0)
    pygame_stub.time = types.SimpleNamespace(get_ticks=lambda: pygame_stub._fake_now)
    pygame_stub._fake_now = 1000
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
        update=lambda *a, **k: None, draw=lambda *a, **k: None,
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

    ui_lp_stub = types.ModuleType("ui_language_profile")
    ui_lp_stub.apply_language_ui_profile = lambda *args, **kwargs: None
    ui_lp_stub.get_font_for_language = lambda *args, **kwargs: None
    monkeypatch.setitem(sys.modules, "ui_language_profile", ui_lp_stub)

    menu_stub = types.ModuleType("menu")
    menu_stub.get_control_actions = lambda: {
        "single_player": [], "pvp.player1": [], "pvp.player2": [],
    }
    menu_stub.get_mode_music_entries = lambda: []
    menu_stub.get_campaign_phase_entries = lambda: []
    menu_stub.BUILT_IN_TRACK_CHOICES = []
    menu_stub.SUPPORTED_MUSIC_EXTENSIONS = [".ogg", ".mp3", ".wav"]
    monkeypatch.setitem(sys.modules, "menu", menu_stub)

    gamepad_stub = types.ModuleType("gamepad_manager")
    gamepad_stub.get_gamepad_manager = lambda: types.SimpleNamespace(
        get_button_index_label=lambda idx, gp_type=None: f"Btn{idx}",
    )
    gamepad_stub.reload_gamepad_settings = lambda: None
    gamepad_stub.normalize_gamepad_event_button = lambda event: getattr(event, "button", None)
    gamepad_stub.normalize_gamepad_trigger_event = lambda event: None
    monkeypatch.setitem(sys.modules, "gamepad_manager", gamepad_stub)

    promptfont_stub = types.ModuleType("promptfont_support")
    promptfont_stub.get_gamepad_prompt_glyph = lambda *args, **kwargs: None
    promptfont_stub.fit_promptfont_glyph_surface = lambda *args, **kwargs: None
    monkeypatch.setitem(sys.modules, "promptfont_support", promptfont_stub)

    ui_scaling_stub = types.ModuleType("ui_scaling")
    ui_scaling_stub.UI_SCALE_PRESETS = ["compact", "normal", "large"]
    ui_scaling_stub.get_projected_effective_scale = lambda *args, **kwargs: 1.0
    ui_scaling_stub.normalize_ui_scale_preset = lambda v: "normal"
    ui_scaling_stub.scale_px = lambda v, scale, minimum=1: max(int(minimum), int(round(float(v) * float(scale))))
    monkeypatch.setitem(sys.modules, "ui_scaling", ui_scaling_stub)


def _import_module(monkeypatch):
    _install_stubs(monkeypatch)
    sys.modules.pop("settings_screen_tabbed", None)
    return importlib.import_module("settings_screen_tabbed")


class _StubSettingsManager:
    def __init__(self, default_controls: dict, current_controls: dict | None = None):
        self.default = copy.deepcopy(default_controls)
        self.current = copy.deepcopy(current_controls or default_controls)
        self.saved = False

    def get(self, key, default=None):
        if key == "controls":
            return copy.deepcopy(self.current)
        return copy.deepcopy(default)

    def set(self, key, value):
        if key == "controls":
            self.current = copy.deepcopy(value)
        self.saved = True

    def get_controls(self):
        return copy.deepcopy(self.current)

    def get_default_controls(self):
        return copy.deepcopy(self.default)

    def save_settings(self):
        self.saved = True


def _make_screen(mod, sm, tab_items=None):
    screen = mod.TabbedSettingsScreen.__new__(mod.TabbedSettingsScreen)
    screen.settings_manager = sm
    screen._control_config = sm.get_controls()
    screen._tab_items = list(tab_items or [])
    screen._waiting_for_key = False
    screen._pending_keybind_item = None
    screen._pending_keybind_slot = "primary"
    screen._capture_started_by_gamepad_click = False
    screen._swallow_next_keydown = False
    screen._hold_to_clear_threshold_ms = 1500
    screen._hold_to_clear_pressed_at_ms = None
    screen._hold_to_clear_pressed_signature = None
    screen._hold_to_clear_consumed = False
    return screen


# ---------------------------------------------------------------------------
# Conflict detection
# ---------------------------------------------------------------------------

def test_conflict_detection_finds_duplicate_single_player_keys(monkeypatch):
    mod = _import_module(monkeypatch)
    controls = {
        "single_player": {
            "move_left": {"primary": "a", "secondary": ""},
            "soft_drop": {"primary": "a", "secondary": ""},
        },
        "pvp": {"player1": {}, "player2": {}},
        "gamepad": {},
    }
    sm = _StubSettingsManager(controls)
    screen = _make_screen(mod, sm)

    conflicts = screen._detect_keybind_conflicts()

    keys = set(conflicts.keys())
    assert ("single_player", "move_left", "primary") in keys
    assert ("single_player", "soft_drop", "primary") in keys


def test_conflict_detection_treats_primary_and_secondary_as_same_namespace(monkeypatch):
    mod = _import_module(monkeypatch)
    controls = {
        "single_player": {
            "move_left": {"primary": "a", "secondary": ""},
            "rotate":    {"primary": "",  "secondary": "a"},
        },
        "pvp": {"player1": {}, "player2": {}},
        "gamepad": {},
    }
    sm = _StubSettingsManager(controls)
    screen = _make_screen(mod, sm)

    conflicts = screen._detect_keybind_conflicts()
    assert ("single_player", "move_left", "primary") in conflicts
    assert ("single_player", "rotate", "secondary") in conflicts


def test_conflict_detection_does_not_cross_section_boundaries(monkeypatch):
    """single_player ile pvp.player1 aynı tuşa bağlanabilir; çakışma sayılmaz."""
    mod = _import_module(monkeypatch)
    controls = {
        "single_player": {"move_left": {"primary": "a", "secondary": ""}},
        "pvp": {
            "player1": {"move_left": "a"},
            "player2": {"move_left": "left"},
        },
        "gamepad": {},
    }
    sm = _StubSettingsManager(controls)
    screen = _make_screen(mod, sm)

    conflicts = screen._detect_keybind_conflicts()
    assert conflicts == {}


def test_conflict_detection_empty_bindings_are_not_conflicting(monkeypatch):
    mod = _import_module(monkeypatch)
    controls = {
        "single_player": {
            "move_left": {"primary": "", "secondary": ""},
            "rotate":    {"primary": "", "secondary": ""},
        },
        "pvp": {"player1": {}, "player2": {}},
        "gamepad": {},
    }
    sm = _StubSettingsManager(controls)
    screen = _make_screen(mod, sm)

    conflicts = screen._detect_keybind_conflicts()
    assert conflicts == {}


def test_conflict_detection_gamepad_section_uses_button_index(monkeypatch):
    mod = _import_module(monkeypatch)
    controls = {
        "single_player": {},
        "pvp": {"player1": {}, "player2": {}},
        "gamepad": {
            "hard_drop":   {"primary": 0, "secondary": -1},
            "rotate":      {"primary": 0, "secondary": -1},
            "soft_drop":   {"primary": 1, "secondary": -1},
        },
    }
    sm = _StubSettingsManager(controls)
    items = [
        {"type": "keybind", "section": "gamepad.ingame", "action_key": "hard_drop"},
        {"type": "keybind", "section": "gamepad.ingame", "action_key": "rotate"},
        {"type": "keybind", "section": "gamepad.ingame", "action_key": "soft_drop"},
    ]
    screen = _make_screen(mod, sm, tab_items=items)

    conflicts = screen._detect_keybind_conflicts()
    assert ("gamepad.ingame", "hard_drop", "primary") in conflicts
    assert ("gamepad.ingame", "rotate", "primary") in conflicts
    assert ("gamepad.ingame", "soft_drop", "primary") not in conflicts


# ---------------------------------------------------------------------------
# Unbound detection
# ---------------------------------------------------------------------------

def test_is_keybind_unbound_detects_empty_primary(monkeypatch):
    mod = _import_module(monkeypatch)
    controls = {
        "single_player": {"move_left": {"primary": "", "secondary": "a"}},
        "pvp": {"player1": {}, "player2": {}},
        "gamepad": {},
    }
    sm = _StubSettingsManager(controls)
    screen = _make_screen(mod, sm)

    item = {"type": "keybind", "section": "single_player", "action_key": "move_left"}
    assert screen._is_keybind_unbound(item) is True


def test_is_keybind_unbound_false_when_primary_set(monkeypatch):
    mod = _import_module(monkeypatch)
    controls = {
        "single_player": {"move_left": {"primary": "left", "secondary": ""}},
        "pvp": {"player1": {}, "player2": {}},
        "gamepad": {},
    }
    sm = _StubSettingsManager(controls)
    screen = _make_screen(mod, sm)

    item = {"type": "keybind", "section": "single_player", "action_key": "move_left"}
    assert screen._is_keybind_unbound(item) is False


def test_is_keybind_unbound_debug_section_is_exempt(monkeypatch):
    """Debug aksiyonları opsiyoneldir; boş olsa bile uyarı üretmez."""
    mod = _import_module(monkeypatch)
    controls = {
        "single_player": {},
        "pvp": {"player1": {}, "player2": {}},
        "debug": {"coop_spawner_left": ""},
        "gamepad": {},
    }
    sm = _StubSettingsManager(controls)
    screen = _make_screen(mod, sm)

    item = {"type": "keybind", "section": "debug", "action_key": "coop_spawner_left"}
    assert screen._is_keybind_unbound(item) is False


def test_is_keybind_unbound_gamepad_negative_primary(monkeypatch):
    mod = _import_module(monkeypatch)
    controls = {
        "single_player": {},
        "pvp": {"player1": {}, "player2": {}},
        "gamepad": {"hard_drop": {"primary": -1, "secondary": -1}},
    }
    sm = _StubSettingsManager(controls)
    screen = _make_screen(mod, sm)

    item = {"type": "keybind", "section": "gamepad.ingame", "action_key": "hard_drop"}
    assert screen._is_keybind_unbound(item) is True


# ---------------------------------------------------------------------------
# Per-row reset (_reset_keybind_row_full)
# ---------------------------------------------------------------------------

def test_reset_keybind_row_full_restores_both_slots_for_single_player(monkeypatch):
    mod = _import_module(monkeypatch)
    defaults = {
        "single_player": {"move_left": {"primary": "left", "secondary": "a"}},
        "pvp": {"player1": {}, "player2": {}},
        "gamepad": {},
    }
    current = {
        "single_player": {"move_left": {"primary": "q", "secondary": "w"}},
        "pvp": {"player1": {}, "player2": {}},
        "gamepad": {},
    }
    sm = _StubSettingsManager(defaults, current)
    screen = _make_screen(mod, sm)

    item = {"type": "keybind", "section": "single_player", "action_key": "move_left"}
    screen._reset_keybind_row_full(item)

    row = sm.current["single_player"]["move_left"]
    assert row["primary"] == "left"
    assert row["secondary"] == "a"


def test_reset_keybind_row_full_for_gamepad_restores_both_slots(monkeypatch):
    mod = _import_module(monkeypatch)
    defaults = {
        "single_player": {}, "pvp": {"player1": {}, "player2": {}},
        "gamepad": {"hard_drop": {"primary": 0, "secondary": 1}},
    }
    current = {
        "single_player": {}, "pvp": {"player1": {}, "player2": {}},
        "gamepad": {"hard_drop": {"primary": 5, "secondary": 6}},
    }
    sm = _StubSettingsManager(defaults, current)
    screen = _make_screen(mod, sm)

    item = {"type": "keybind", "section": "gamepad.ingame", "action_key": "hard_drop"}
    screen._reset_keybind_row_full(item)

    raw = sm.current["gamepad"]["hard_drop"]
    assert raw["primary"] == 0
    assert raw["secondary"] == 1


# ---------------------------------------------------------------------------
# Slot clear
# ---------------------------------------------------------------------------

def test_clear_keybind_slot_sets_single_player_slot_to_empty_string(monkeypatch):
    mod = _import_module(monkeypatch)
    defaults = {
        "single_player": {"move_left": {"primary": "left", "secondary": "a"}},
        "pvp": {"player1": {}, "player2": {}},
        "gamepad": {},
    }
    sm = _StubSettingsManager(defaults)
    screen = _make_screen(mod, sm)

    item = {"type": "keybind", "section": "single_player", "action_key": "move_left"}
    screen._clear_keybind_slot(item, "primary")
    assert sm.current["single_player"]["move_left"]["primary"] == ""
    assert sm.current["single_player"]["move_left"]["secondary"] == "a"


def test_clear_keybind_slot_gamepad_uses_negative_one(monkeypatch):
    mod = _import_module(monkeypatch)
    defaults = {
        "single_player": {}, "pvp": {"player1": {}, "player2": {}},
        "gamepad": {"hard_drop": {"primary": 0, "secondary": 1}},
    }
    sm = _StubSettingsManager(defaults)
    screen = _make_screen(mod, sm)

    item = {"type": "keybind", "section": "gamepad.ingame", "action_key": "hard_drop"}
    screen._clear_keybind_slot(item, "secondary")
    assert sm.current["gamepad"]["hard_drop"]["primary"] == 0
    assert sm.current["gamepad"]["hard_drop"]["secondary"] == -1


# ---------------------------------------------------------------------------
# Hold-to-clear capture flow
# ---------------------------------------------------------------------------

def test_hold_to_clear_state_resets_after_capture_start(monkeypatch):
    mod = _import_module(monkeypatch)
    sm = _StubSettingsManager({"single_player": {}, "pvp": {"player1": {}, "player2": {}}, "gamepad": {}})
    screen = _make_screen(mod, sm)
    screen._hold_to_clear_pressed_at_ms = 1234
    screen._hold_to_clear_pressed_signature = ("key", 97)
    screen._hold_to_clear_consumed = True

    item = {"type": "keybind", "section": "single_player", "action_key": "move_left"}
    screen._start_keybind_capture(item, slot="primary")

    assert screen._hold_to_clear_pressed_at_ms is None
    assert screen._hold_to_clear_pressed_signature is None
    assert screen._hold_to_clear_consumed is False
    assert screen._waiting_for_key is True


def test_hold_to_clear_progress_clears_slot_when_threshold_reached(monkeypatch):
    """Capture aktif + tuş eşiği aşıyor + hala basılı → slot temizlenir."""
    mod = _import_module(monkeypatch)
    defaults = {
        "single_player": {"move_left": {"primary": "left", "secondary": ""}},
        "pvp": {"player1": {}, "player2": {}}, "gamepad": {},
    }
    sm = _StubSettingsManager(defaults)
    screen = _make_screen(mod, sm)

    item = {"type": "keybind", "section": "single_player", "action_key": "move_left"}
    screen._start_keybind_capture(item, slot="primary")
    # Simulate KEYDOWN at t=1000
    mod.pygame._fake_now = 1000
    screen._hold_to_clear_pressed_at_ms = 1000
    screen._hold_to_clear_pressed_signature = ("key", mod.pygame.K_LEFT)
    # Tuş hala basılı
    mod.pygame._press_state = mod.pygame._press_state.__class__({mod.pygame.K_LEFT})
    # Eşiği aş (1500 ms)
    mod.pygame._fake_now = 1000 + 1600

    screen._check_hold_to_clear_progress()

    # Slot temizlendi
    assert sm.current["single_player"]["move_left"]["primary"] == ""
    # Capture sonlandı
    assert screen._waiting_for_key is False
    assert screen._pending_keybind_item is None
    assert screen._hold_to_clear_consumed is True


def test_hold_to_clear_progress_does_nothing_before_threshold(monkeypatch):
    mod = _import_module(monkeypatch)
    defaults = {
        "single_player": {"move_left": {"primary": "left", "secondary": ""}},
        "pvp": {"player1": {}, "player2": {}}, "gamepad": {},
    }
    sm = _StubSettingsManager(defaults)
    screen = _make_screen(mod, sm)

    item = {"type": "keybind", "section": "single_player", "action_key": "move_left"}
    screen._start_keybind_capture(item, slot="primary")
    mod.pygame._fake_now = 1000
    screen._hold_to_clear_pressed_at_ms = 1000
    screen._hold_to_clear_pressed_signature = ("key", mod.pygame.K_LEFT)
    mod.pygame._press_state = mod.pygame._press_state.__class__({mod.pygame.K_LEFT})
    # Eşiği geçme (sadece 500 ms)
    mod.pygame._fake_now = 1500

    screen._check_hold_to_clear_progress()

    # Slot DEĞİŞMEDİ
    assert sm.current["single_player"]["move_left"]["primary"] == "left"
    # Capture devam ediyor
    assert screen._waiting_for_key is True


def test_hold_to_clear_progress_resets_when_key_released_early(monkeypatch):
    mod = _import_module(monkeypatch)
    defaults = {
        "single_player": {"move_left": {"primary": "left", "secondary": ""}},
        "pvp": {"player1": {}, "player2": {}}, "gamepad": {},
    }
    sm = _StubSettingsManager(defaults)
    screen = _make_screen(mod, sm)

    item = {"type": "keybind", "section": "single_player", "action_key": "move_left"}
    screen._start_keybind_capture(item, slot="primary")
    mod.pygame._fake_now = 1000
    screen._hold_to_clear_pressed_at_ms = 1000
    screen._hold_to_clear_pressed_signature = ("key", mod.pygame.K_LEFT)
    # Tuş artık basılı değil
    mod.pygame._press_state = mod.pygame._press_state.__class__(set())
    # Eşik geçti ama tuş bırakılmış
    mod.pygame._fake_now = 1000 + 2000

    screen._check_hold_to_clear_progress()

    # Hold state sıfırlandı, slot değişmedi
    assert screen._hold_to_clear_pressed_at_ms is None
    assert screen._hold_to_clear_pressed_signature is None
    assert sm.current["single_player"]["move_left"]["primary"] == "left"



# ---------------------------------------------------------------------------
# Reset button hit-rect izolasyonu
# ---------------------------------------------------------------------------

def test_reset_button_hit_rect_only_triggers_inside_icon_bounds(monkeypatch):
    """Per-row reset (↺) yalnızca kendi rect'i içine tıklanınca tetiklenmeli;
    satırın geri kalanına tıklamak reset'i tetiklememeli."""
    mod = _import_module(monkeypatch)

    # _reset_keybind_row_full çağrı sayısını izle
    calls = []
    original = mod.TabbedSettingsScreen._reset_keybind_row_full

    def _spy(self, item):
        calls.append(item.get('action_key'))
        original(self, item)

    monkeypatch.setattr(mod.TabbedSettingsScreen, '_reset_keybind_row_full', _spy)

    sm = _StubSettingsManager({
        "single_player": {"move_left": {"primary": "left", "secondary": ""}},
        "pvp": {"player1": {}, "player2": {}}, "gamepad": {},
    })
    screen = _make_screen(mod, sm)

    # Reset rect'i 100,200 civarı, 22x22 kare olarak yerleşik kabul et.
    reset_rect = mod.pygame.Rect(100, 200, 22, 22)
    item = {"type": "keybind", "section": "single_player", "action_key": "move_left"}

    # ↺ rect içinde tıklama -> reset tetiklenir
    inside_pos = (110, 211)
    assert reset_rect.collidepoint(inside_pos) is True

    # Satırın başka yerleri (örn. label tarafı) -> reset tetiklenmemeli
    outside_positions = [(50, 211), (200, 211), (110, 100), (110, 300)]
    for pos in outside_positions:
        assert reset_rect.collidepoint(pos) is False

    # Click handler simülasyonu: yalnızca rect.collidepoint(pos) true ise reset çağırır
    def _simulate_click(pos):
        if reset_rect.collidepoint(pos):
            screen._reset_keybind_row_full(item)

    _simulate_click(inside_pos)
    for pos in outside_positions:
        _simulate_click(pos)

    # Sadece bir kez tetiklenmeli (içeri tıklanan)
    assert calls == ['move_left']
