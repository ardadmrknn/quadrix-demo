from __future__ import annotations

import copy
from types import SimpleNamespace

import pygame

import gamepad_manager as gamepad_manager_module
from gamepad_manager import GamepadManager, GamepadState, GamepadType, DEFAULT_GAMEPAD_BINDINGS


class _DummyJoystick:
    def __init__(
        self,
        axes: tuple[float, ...],
        *,
        buttons: dict[int, bool] | None = None,
        hats: tuple[tuple[int, int], ...] = (),
        instance_id: int = 0,
    ):
        self.axes = axes
        self.buttons = buttons or {}
        self.hats = hats
        self.instance_id = instance_id

    def get_init(self) -> bool:
        return True

    def get_numaxes(self) -> int:
        return len(self.axes)

    def get_axis(self, index: int) -> float:
        return self.axes[index]

    def get_numbuttons(self) -> int:
        return max(self.buttons.keys(), default=-1) + 1

    def get_button(self, index: int) -> int:
        return 1 if self.buttons.get(index, False) else 0

    def get_numhats(self) -> int:
        return len(self.hats)

    def get_hat(self, index: int) -> tuple[int, int]:
        return self.hats[index]

    def get_instance_id(self) -> int:
        return self.instance_id

    def get_id(self) -> int:
        return self.instance_id


class _DummyController:
    def __init__(
        self,
        *,
        buttons: dict[int, bool] | None = None,
        axes: tuple[float, ...] = (0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
    ):
        self.buttons = buttons or {}
        self.axes = axes

    def get_init(self) -> bool:
        return True

    def get_button(self, index: int) -> bool:
        return bool(self.buttons.get(index, False))

    def get_axis(self, index: int) -> float:
        return self.axes[index]

    def attached(self) -> bool:
        return True


class _DummySurface:
    def __init__(self, size: tuple[int, int]):
        self._size = size

    def get_size(self) -> tuple[int, int]:
        return self._size


def _make_manager() -> GamepadManager:
    manager = GamepadManager.__new__(GamepadManager)
    manager.enabled = True
    manager.gamepads = {}
    manager.rumble_enabled = False
    manager.MOUSE_SPEED = 20.0
    manager.MOUSE_SENSITIVITY = 1.0
    manager.MOUSE_DEADZONE = 0.12
    manager.MOUSE_ACCEL_EXPONENT = 2.0
    manager.MOUSE_ACTIVATE_THRESHOLD = 0.30
    manager.MOUSE_RELEASE_THRESHOLD = 0.14
    manager.MOUSE_NEUTRAL_TRACK_THRESHOLD = 0.24
    manager.MOUSE_NEUTRAL_FOLLOW_RATE = 0.08
    manager.DEADZONE = 0.35
    manager.DIGITAL_THRESHOLD = 0.6
    manager.TRIGGER_THRESHOLD = 0.5
    manager._context = GamepadManager.CONTEXT_MENU
    manager._menu_pointer_active = False
    manager._bindings = copy.deepcopy(DEFAULT_GAMEPAD_BINDINGS)
    manager._check_connections = lambda: None
    return manager


def _patch_display(monkeypatch, *, pos=(640, 360)):
    current = {'pos': pos, 'calls': []}
    gp_pygame = gamepad_manager_module.pygame

    if not hasattr(gp_pygame, 'display'):
        monkeypatch.setattr(gp_pygame, 'display', SimpleNamespace(), raising=False)
    if not hasattr(gp_pygame, 'mouse'):
        monkeypatch.setattr(gp_pygame, 'mouse', SimpleNamespace(), raising=False)
    if not hasattr(gp_pygame, 'event'):
        monkeypatch.setattr(gp_pygame, 'event', SimpleNamespace(), raising=False)

    monkeypatch.setattr(gp_pygame, 'MOUSEMOTION', getattr(gp_pygame, 'MOUSEMOTION', 1024), raising=False)

    monkeypatch.setattr(gp_pygame.display, 'get_surface', lambda: _DummySurface((1280, 720)), raising=False)
    monkeypatch.setattr(gp_pygame.display, 'get_window_size', lambda: (1280, 720), raising=False)
    monkeypatch.setattr(gp_pygame.mouse, 'get_pos', lambda: current['pos'], raising=False)
    monkeypatch.setattr(
        gp_pygame.event,
        'Event',
        lambda event_type, **payload: SimpleNamespace(type=event_type, **payload),
        raising=False,
    )

    def _set_pos(x, y):
        current['pos'] = (x, y)
        current['calls'].append((x, y))

    monkeypatch.setattr(gp_pygame.mouse, 'set_pos', _set_pos, raising=False)
    return current


def test_right_stick_drift_does_not_move_mouse(monkeypatch):
    manager = _make_manager()
    display = _patch_display(monkeypatch)
    monkeypatch.setattr(gamepad_manager_module, '_gmp', lambda: display['pos'])

    gp = GamepadState(joystick=_DummyJoystick((0.0, 0.0, 0.0, 0.28)))
    gp.raw_right_x = 0.0
    gp.raw_right_y = 0.28
    gp.mouse_neutral_x = 0.0
    gp.mouse_neutral_y = 0.22
    gp.mouse_neutral_ready = True

    events = manager._generate_mouse_events(gp, 16.0)

    assert events == []
    assert display['calls'] == []
    assert gp.mouse_control_active is False


def test_initial_right_stick_bias_becomes_neutral_without_cursor_drag(monkeypatch):
    manager = _make_manager()
    display = _patch_display(monkeypatch)
    monkeypatch.setattr(gamepad_manager_module, '_gmp', lambda: display['pos'])

    gp = GamepadState(joystick=_DummyJoystick((0.0, 0.0, 0.55, 0.52)))
    gp.raw_right_x = 0.55
    gp.raw_right_y = 0.52

    manager._update_mouse_neutral(gp)
    events = manager._generate_mouse_events(gp, 16.0)

    assert gp.mouse_neutral_ready is True
    assert display['calls'] == []
    assert events == []
    assert gp.mouse_control_active is False


def test_intentional_right_stick_input_moves_mouse(monkeypatch):
    manager = _make_manager()
    display = _patch_display(monkeypatch)
    monkeypatch.setattr(gamepad_manager_module, '_gmp', lambda: display['pos'])

    gp = GamepadState(joystick=_DummyJoystick((0.0, 0.0, 0.0, -0.9)))
    gp.raw_right_x = 0.0
    gp.raw_right_y = -0.9
    gp.mouse_neutral_x = 0.0
    gp.mouse_neutral_y = 0.0
    gp.mouse_neutral_ready = True

    events = manager._generate_mouse_events(gp, 16.0)

    assert len(events) == 1
    assert events[0].type == gamepad_manager_module.pygame.MOUSEMOTION
    assert events[0].rel[1] < 0
    assert display['calls']
    assert display['calls'][-1][1] < 360
    assert gp.mouse_control_active is True


def test_dpad_button_fallback_generates_left_key_events(monkeypatch):
    manager = _make_manager()
    manager._context = GamepadManager.CONTEXT_GAME

    gp_pygame = gamepad_manager_module.pygame
    if not hasattr(gp_pygame, 'event'):
        monkeypatch.setattr(gp_pygame, 'event', SimpleNamespace(), raising=False)
    monkeypatch.setattr(
        gp_pygame.event,
        'Event',
        lambda event_type, **payload: SimpleNamespace(type=event_type, **payload),
        raising=False,
    )

    gp = GamepadState(joystick=_DummyJoystick((0.0, 0.0), buttons={13: True}))
    manager.gamepads[0] = gp

    events = manager.update(16.0)

    assert any(
        event.type == gp_pygame.KEYDOWN and event.key == gp_pygame.K_LEFT
        for event in events
    )
    assert gp.dpad == (-1, 0)
    assert manager.is_direction_held('left') is True

    gp.joystick.buttons = {13: False}
    events = manager.update(16.0)

    assert any(
        event.type == gp_pygame.KEYUP and event.key == gp_pygame.K_LEFT
        for event in events
    )
    assert gp.dpad == (0, 0)
    assert manager.is_direction_held('left') is False


def test_menu_dpad_hold_repeats_down_navigation(monkeypatch):
    manager = _make_manager()

    gp_pygame = gamepad_manager_module.pygame
    if not hasattr(gp_pygame, 'event'):
        monkeypatch.setattr(gp_pygame, 'event', SimpleNamespace(), raising=False)
    monkeypatch.setattr(
        gp_pygame.event,
        'Event',
        lambda event_type, **payload: SimpleNamespace(type=event_type, **payload),
        raising=False,
    )

    gp = GamepadState(joystick=_DummyJoystick((0.0, 0.0), buttons={12: True}))
    manager.gamepads[0] = gp

    first_events = manager.update(16.0)
    repeat_events = manager.update(manager.STICK_INITIAL_DELAY + 1)

    assert any(
        event.type == gp_pygame.KEYDOWN and event.key == gp_pygame.K_DOWN
        for event in first_events
    )
    assert any(
        event.type == gp_pygame.KEYDOWN and event.key == gp_pygame.K_DOWN
        for event in repeat_events
    )
    assert any(
        event.type == gp_pygame.KEYUP and event.key == gp_pygame.K_DOWN
        for event in repeat_events
    )


def test_menu_left_stick_hold_repeats_down_navigation(monkeypatch):
    manager = _make_manager()

    gp_pygame = gamepad_manager_module.pygame
    if not hasattr(gp_pygame, 'event'):
        monkeypatch.setattr(gp_pygame, 'event', SimpleNamespace(), raising=False)
    monkeypatch.setattr(
        gp_pygame.event,
        'Event',
        lambda event_type, **payload: SimpleNamespace(type=event_type, **payload),
        raising=False,
    )

    gp = GamepadState(joystick=_DummyJoystick((0.0, 1.0)))
    manager.gamepads[0] = gp

    first_events = manager.update(16.0)
    repeat_events = manager.update(manager.STICK_INITIAL_DELAY + 1)

    assert any(
        event.type == gp_pygame.KEYDOWN and event.key == gp_pygame.K_DOWN
        for event in first_events
    )
    assert any(
        event.type == gp_pygame.KEYDOWN and event.key == gp_pygame.K_DOWN
        for event in repeat_events
    )
    assert any(
        event.type == gp_pygame.KEYUP and event.key == gp_pygame.K_DOWN
        for event in repeat_events
    )


def test_game_context_confirm_clicks_are_tagged_from_gamepad(monkeypatch):
    manager = _make_manager()
    manager._context = GamepadManager.CONTEXT_GAME

    gp_pygame = gamepad_manager_module.pygame
    if not hasattr(gp_pygame, 'event'):
        monkeypatch.setattr(gp_pygame, 'event', SimpleNamespace(), raising=False)
    monkeypatch.setattr(
        gp_pygame.event,
        'Event',
        lambda event_type, **payload: SimpleNamespace(type=event_type, **payload),
        raising=False,
    )
    monkeypatch.setattr(gamepad_manager_module, '_gmp', lambda: (320, 240))

    gp = GamepadState(joystick=_DummyJoystick((0.0, 0.0), buttons={0: True}), buttons={0: True})
    gp.prev_buttons = {}

    events = manager._generate_mouse_click_events(gp)

    assert len(events) == 1
    assert events[0].type == gp_pygame.MOUSEBUTTONDOWN
    assert events[0].button == 1
    assert events[0].pos == (320, 240)
    assert events[0].from_gamepad is True


def test_windows_xinput_raw_lb_maps_to_canonical_menu_tab_prev(monkeypatch):
    manager = _make_manager()

    gp_pygame = gamepad_manager_module.pygame
    if not hasattr(gp_pygame, 'event'):
        monkeypatch.setattr(gp_pygame, 'event', SimpleNamespace(), raising=False)
    monkeypatch.setattr(
        gp_pygame.event,
        'Event',
        lambda event_type, **payload: SimpleNamespace(type=event_type, **payload),
        raising=False,
    )

    gp = GamepadState(
        joystick=_DummyJoystick((0.0, 0.0), buttons={4: True}, instance_id=11),
        gamepad_type=GamepadType.XBOX,
        instance_id=11,
    )
    manager.gamepads[0] = gp

    events = manager.update(16.0)

    assert any(
        event.type == gp_pygame.KEYDOWN and event.key == gp_pygame.K_LEFTBRACKET
        for event in events
    )
    assert gp.buttons.get(9) is True


def test_controller_capture_prefers_canonical_button_indices():
    manager = _make_manager()
    gp = GamepadState(
        joystick=_DummyJoystick((0.0, 0.0), buttons={5: True}, instance_id=17),
        controller=_DummyController(buttons={10: True}),
        gamepad_type=GamepadType.XBOX,
        instance_id=17,
    )
    gp.buttons = {10: True}
    gp.prev_buttons = {}
    manager.gamepads[0] = gp

    resolved = manager.resolve_capture_button_index(5, joy_id=0, instance_id=17)

    assert resolved == 10


def test_normalize_gamepad_event_button_maps_windows_raw_rb_with_controller_state(monkeypatch):
    manager = _make_manager()
    gp = GamepadState(
        joystick=_DummyJoystick((0.0, 0.0), buttons={5: True}, instance_id=41),
        controller=_DummyController(buttons={10: True}),
        gamepad_type=GamepadType.XBOX,
        instance_id=41,
    )
    gp.buttons = {}
    gp.prev_buttons = {}
    manager.gamepads[0] = gp
    monkeypatch.setattr(gamepad_manager_module, '_instance', manager)

    event = SimpleNamespace(type=pygame.JOYBUTTONDOWN, button=5, joy=0, instance_id=41)

    resolved = gamepad_manager_module.normalize_gamepad_event_button(event)

    assert resolved == 10


def test_normalize_gamepad_event_button_maps_windows_raw_lb_fallback(monkeypatch):
    manager = _make_manager()
    gp = GamepadState(
        joystick=_DummyJoystick((0.0, 0.0), buttons={4: True}, instance_id=43),
        controller=_DummyController(buttons={}),
        gamepad_type=GamepadType.XBOX,
        instance_id=43,
    )
    gp.buttons = {}
    gp.prev_buttons = {}
    manager.gamepads[0] = gp
    monkeypatch.setattr(gamepad_manager_module, '_instance', manager)

    event = SimpleNamespace(type=pygame.JOYBUTTONDOWN, button=4, joy=0, instance_id=43)

    resolved = gamepad_manager_module.normalize_gamepad_event_button(event)

    assert resolved == 9


def test_controller_capture_prefers_canonical_trigger_indices():
    manager = _make_manager()
    gp = GamepadState(
        joystick=_DummyJoystick((0.0, 0.0), instance_id=23),
        controller=_DummyController(axes=(0.0, 0.0, 0.0, 0.0, 0.0, 0.82)),
        gamepad_type=GamepadType.XBOX,
        instance_id=23,
    )
    gp.left_trigger = 0.0
    gp.right_trigger = 0.82
    manager.gamepads[0] = gp

    resolved = manager.resolve_capture_trigger_index(2, 0.1, joy_id=0, instance_id=23)

    assert resolved == 101


def test_controller_presence_does_not_override_stable_joystick_mouse_axes(monkeypatch):
    manager = _make_manager()
    display = _patch_display(monkeypatch)
    monkeypatch.setattr(gamepad_manager_module, '_gmp', lambda: display['pos'])

    gp = GamepadState(
        joystick=_DummyJoystick((0.0, 0.0, 0.0, 0.0, -1.0, -1.0), instance_id=31),
        controller=_DummyController(axes=(0.0, 0.0, -0.92, -0.96, 0.0, 0.0)),
        gamepad_type=GamepadType.XBOX,
        instance_id=31,
    )
    manager.gamepads[0] = gp

    events = manager.update(16.0)

    assert events == []
    assert display['calls'] == []
    assert gp.raw_right_x == 0.0
    assert gp.raw_right_y == 0.0