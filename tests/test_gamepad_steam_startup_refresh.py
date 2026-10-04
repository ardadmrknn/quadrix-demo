"""Steam Input sanal gamepad'inin gecikmeli başlangıç taraması testleri."""

import pathlib
import sys

ROOT_DIR = pathlib.Path(__file__).parent.parent
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import gamepad_manager as gamepad_module  # noqa: E402


class _FakeControllerModule:
    def __init__(self):
        self.initialized = True
        self.quit_calls = 0
        self.init_calls = 0

    def get_init(self):
        return self.initialized

    def quit(self):
        self.quit_calls += 1
        self.initialized = False

    def init(self):
        self.init_calls += 1
        self.initialized = True


def _bare_manager():
    manager = object.__new__(gamepad_module.GamepadManager)
    manager.gamepads = {}
    manager._internal_time = 0.0
    manager._startup_refresh_attempts = 0
    manager._startup_refresh_schedule_ms = (250.0, 1000.0, 2500.0, 5000.0)
    return manager


def test_startup_refresh_waits_until_first_deadline(monkeypatch):
    manager = _bare_manager()
    calls = {"quit": 0, "init": 0}

    monkeypatch.setattr(gamepad_module.pygame.event, "pump", lambda: None)
    monkeypatch.setattr(gamepad_module.pygame.joystick, "get_count", lambda: 0)
    monkeypatch.setattr(
        gamepad_module.pygame.joystick,
        "quit",
        lambda: calls.__setitem__("quit", calls["quit"] + 1),
    )
    monkeypatch.setattr(
        gamepad_module.pygame.joystick,
        "init",
        lambda: calls.__setitem__("init", calls["init"] + 1),
    )

    manager._internal_time = 249.0
    manager._refresh_empty_startup_scan()

    assert manager._startup_refresh_attempts == 0
    assert calls == {"quit": 0, "init": 0}


def test_startup_refresh_reinitializes_empty_sdl_once(monkeypatch):
    manager = _bare_manager()
    manager._internal_time = 250.0
    calls = {"quit": 0, "init": 0}
    controller = _FakeControllerModule()

    monkeypatch.setattr(gamepad_module, "_sdl2_controller", controller)
    monkeypatch.setattr(gamepad_module.pygame.event, "pump", lambda: None)
    monkeypatch.setattr(gamepad_module.pygame.joystick, "get_count", lambda: 0)
    monkeypatch.setattr(
        gamepad_module.pygame.joystick,
        "quit",
        lambda: calls.__setitem__("quit", calls["quit"] + 1),
    )
    monkeypatch.setattr(
        gamepad_module.pygame.joystick,
        "init",
        lambda: calls.__setitem__("init", calls["init"] + 1),
    )

    manager._refresh_empty_startup_scan()

    assert manager._startup_refresh_attempts == 1
    assert calls == {"quit": 1, "init": 1}
    assert controller.quit_calls == 1
    assert controller.init_calls == 1


def test_startup_refresh_does_not_reset_when_device_is_visible(monkeypatch):
    manager = _bare_manager()
    manager._internal_time = 250.0
    calls = {"quit": 0, "init": 0}

    monkeypatch.setattr(gamepad_module.pygame.event, "pump", lambda: None)
    monkeypatch.setattr(gamepad_module.pygame.joystick, "get_count", lambda: 1)
    monkeypatch.setattr(
        gamepad_module.pygame.joystick,
        "quit",
        lambda: calls.__setitem__("quit", calls["quit"] + 1),
    )
    monkeypatch.setattr(
        gamepad_module.pygame.joystick,
        "init",
        lambda: calls.__setitem__("init", calls["init"] + 1),
    )

    manager._refresh_empty_startup_scan()

    assert manager._startup_refresh_attempts == 1
    assert calls == {"quit": 0, "init": 0}


def test_startup_refresh_skips_when_manager_already_has_gamepad(monkeypatch):
    manager = _bare_manager()
    manager._internal_time = 5000.0
    manager.gamepads[0] = object()
    calls = {"count": 0}

    monkeypatch.setattr(
        gamepad_module.pygame.joystick,
        "get_count",
        lambda: calls.__setitem__("count", calls["count"] + 1),
    )

    manager._refresh_empty_startup_scan()

    assert manager._startup_refresh_attempts == 0
    assert calls["count"] == 0
