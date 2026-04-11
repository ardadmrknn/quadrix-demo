from __future__ import annotations

from types import SimpleNamespace

import gamepad_manager as gamepad_manager_module
from gamepad_manager import GamepadManager, GamepadState


class _DummyJoystick:
    def __init__(self, axes: tuple[float, ...]):
        self.axes = axes

    def get_init(self) -> bool:
        return True

    def get_numaxes(self) -> int:
        return len(self.axes)


class _DummySurface:
    def __init__(self, size: tuple[int, int]):
        self._size = size

    def get_size(self) -> tuple[int, int]:
        return self._size


def _make_manager() -> GamepadManager:
    manager = GamepadManager.__new__(GamepadManager)
    manager.MOUSE_SPEED = 20.0
    manager.MOUSE_SENSITIVITY = 1.0
    manager.MOUSE_DEADZONE = 0.12
    manager.MOUSE_ACCEL_EXPONENT = 2.0
    manager.MOUSE_ACTIVATE_THRESHOLD = 0.30
    manager.MOUSE_RELEASE_THRESHOLD = 0.14
    manager.MOUSE_NEUTRAL_TRACK_THRESHOLD = 0.24
    manager.MOUSE_NEUTRAL_FOLLOW_RATE = 0.08
    manager._context = GamepadManager.CONTEXT_MENU
    manager._menu_pointer_active = False
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