from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace


SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import gamepad_manager as gamepad_manager_module
from gamepad_manager import GamepadManager, _SteamInputJoystick


def _manager() -> GamepadManager:
    manager = GamepadManager.__new__(GamepadManager)
    manager.gamepads = {}
    return manager


def _snapshot(handle: int = 123) -> dict:
    return {
        "handle": handle,
        "input_type": 3,
        "buttons": {
            "a": True,
            "b": False,
            "left_trigger": True,
            "right_trigger": False,
        },
        "axes": {
            "left_stick": (0.5, -0.75),
            "right_stick": (-0.25, 0.25),
        },
    }


def test_steam_input_joystick_exposes_canonical_state():
    joystick = _SteamInputJoystick(_snapshot(), -123)

    assert joystick.get_name() == "Steam Input Xbox Controller"
    assert joystick.get_button(0) == 1
    assert joystick.get_button(1) == 0
    assert joystick.get_axis(0) == 0.5
    assert joystick.get_axis(1) == 0.75
    assert joystick.get_axis(2) == -0.25
    assert joystick.get_axis(3) == -0.25
    assert joystick.get_axis(4) == 1.0
    assert joystick.get_axis(5) == -1.0


def test_manager_adds_steam_action_fallback_when_sdl_is_empty(monkeypatch):
    manager = _manager()
    monkeypatch.setattr(gamepad_manager_module.pygame.joystick, "get_count", lambda: 0)
    monkeypatch.setitem(sys.modules, "steam_integration", SimpleNamespace(
        get_steam_input_snapshots=lambda: [_snapshot()],
    ))

    manager._sync_steam_input_gamepads()

    assert len(manager.gamepads) == 1
    state = next(iter(manager.gamepads.values()))
    assert isinstance(state.joystick, _SteamInputJoystick)
    assert state.controller is state.joystick
    assert state.gamepad_type == "xbox"
    # Boş SDL listesinde köprü canlıysa birincil mod açılır.
    assert manager._steam_input_primary is True


def test_manager_keeps_steam_primary_when_sdl_device_exists(monkeypatch):
    """SI açıkken Steam'in XInput kancası SDL'e çevrilmiş akış sunar: köprü
    canlıysa Steam action verisi birincil kalır, SDL kaynağına düşülmez."""
    manager = _manager()
    key = -1000123
    joystick = _SteamInputJoystick(_snapshot(), key)
    manager.gamepads[key] = SimpleNamespace(joystick=joystick, name=joystick.get_name())
    monkeypatch.setattr(gamepad_manager_module.pygame.joystick, "get_count", lambda: 1)
    monkeypatch.setitem(sys.modules, "steam_integration", SimpleNamespace(
        get_steam_input_snapshots=lambda: [_snapshot()],
    ))

    manager._sync_steam_input_gamepads()

    assert manager._steam_input_primary is True
    assert set(manager.gamepads) == {key}
    assert joystick.get_init() is True


def test_bridge_live_purges_sdl_gamepads(monkeypatch):
    """Birincil moda geçişte kayıtlı SDL pad'leri kapatılır (kancalı akış +
    çift girdi önlenir) ve bekleyen capture kenarları GP-006 ile atılır."""
    manager = _manager()
    manager._capture_edges = [(0, "down"), (-1000123, "down")]
    quit_calls = []
    manager.gamepads[0] = SimpleNamespace(
        joystick=SimpleNamespace(quit=lambda: quit_calls.append(0)),
        name="Xbox 360 Controller",
    )
    monkeypatch.setattr(gamepad_manager_module.pygame.joystick, "get_count", lambda: 1)
    monkeypatch.setitem(sys.modules, "steam_integration", SimpleNamespace(
        get_steam_input_snapshots=lambda: [_snapshot()],
    ))

    manager._sync_steam_input_gamepads()

    assert quit_calls == [0]
    assert set(manager.gamepads) == {-1000123}
    assert isinstance(manager.gamepads[-1000123].joystick, _SteamInputJoystick)
    # SDL cihazına ait kenar atıldı, Steam cihazınınki korundu.
    assert manager._capture_edges == [(-1000123, "down")]


def test_scan_gamepads_skipped_while_steam_primary(monkeypatch):
    """Birincil modda SDL taraması hiç açılmaz (get_count bile çağrılmaz)."""
    manager = _manager()
    manager._steam_input_primary = True
    manager.gamepads = {}

    def _boom():
        raise AssertionError("get_count çağrılmamalıydı")

    monkeypatch.setattr(
        gamepad_manager_module.pygame.joystick, "get_count", _boom
    )

    manager._scan_gamepads()  # exception yok = erken dönüş


def test_register_gamepad_skipped_while_steam_primary(monkeypatch):
    """Hotplug event'i doğrudan _register_gamepad'e düşebilir; birincil
    modda SDL cihazı açılmaz ve False döner."""
    manager = _manager()
    manager._steam_input_primary = True
    manager.gamepads = {}

    def _boom(_index):
        raise AssertionError("Joystick açılmamalıydı")

    monkeypatch.setattr(gamepad_manager_module.pygame.joystick, "Joystick", _boom)

    assert manager._register_gamepad(0) is False


def test_bridge_loss_rescans_sdl_devices(monkeypatch):
    """Köprü ortada kapandıysa (SI kapatıldı/Steam çıktı) fiziksel cihaz SDL
    için hiç kopmadığından hotplug eventi gelmez: elle yeniden tarama."""
    manager = _manager()
    manager._steam_input_primary = True
    key = -1000123
    joystick = _SteamInputJoystick(_snapshot(), key)
    manager.gamepads[key] = SimpleNamespace(joystick=joystick, name=joystick.get_name())
    monkeypatch.setattr(gamepad_manager_module.pygame.joystick, "get_count", lambda: 1)
    monkeypatch.setitem(sys.modules, "steam_integration", SimpleNamespace(
        get_steam_input_snapshots=lambda: [],
    ))
    scan_calls = []
    monkeypatch.setattr(
        manager, "_scan_gamepads", lambda: scan_calls.append(True)
    )

    manager._sync_steam_input_gamepads()

    assert manager._steam_input_primary is False
    assert manager.gamepads == {}
    assert joystick.get_init() is False
    assert scan_calls == [True]


def test_no_scan_when_bridge_never_live(monkeypatch):
    """Köprü hiç canlı olmamışsa (SI kapalı) eski davranış: SDL taraması
    elle tetiklenmez, periyodik polling halleder."""
    manager = _manager()
    monkeypatch.setattr(gamepad_manager_module.pygame.joystick, "get_count", lambda: 1)
    monkeypatch.setitem(sys.modules, "steam_integration", SimpleNamespace(
        get_steam_input_snapshots=lambda: [],
    ))
    scan_calls = []
    monkeypatch.setattr(
        manager, "_scan_gamepads", lambda: scan_calls.append(True)
    )

    manager._sync_steam_input_gamepads()

    assert manager._steam_input_primary is False
    assert scan_calls == []


def test_steam_input_device_families_keep_their_native_labels():
    expected = {
        1: ("Steam Input Steam Controller", "xbox"),
        2: ("Steam Input Xbox Controller", "xbox"),
        3: ("Steam Input Xbox Controller", "xbox"),
        4: ("Steam Input Xbox Controller", "xbox"),
        5: ("Steam Input PlayStation Controller", "playstation"),
        8: ("Steam Input Nintendo Controller", "nintendo"),
        9: ("Steam Input Nintendo Controller", "nintendo"),
        10: ("Steam Input Nintendo Controller", "nintendo"),
        12: ("Steam Input PlayStation Controller", "playstation"),
        13: ("Steam Input PlayStation Controller", "playstation"),
        14: ("Steam Input Steam Deck Controller", "xbox"),
    }
    manager = _manager()

    for input_type, (name, family) in expected.items():
        snapshot = _snapshot(handle=1000 + input_type)
        snapshot["input_type"] = input_type
        joystick = _SteamInputJoystick(snapshot, -input_type)
        assert joystick.get_name() == name
        assert manager._detect_type(joystick) == family


def test_full_64_bit_steam_handles_do_not_collide(monkeypatch):
    manager = _manager()
    monkeypatch.setattr(gamepad_manager_module.pygame.joystick, "get_count", lambda: 0)
    first = _snapshot(handle=1)
    second = _snapshot(handle=1 + (1 << 31))
    monkeypatch.setitem(
        sys.modules,
        "steam_integration",
        SimpleNamespace(get_steam_input_snapshots=lambda: [first, second]),
    )

    manager._sync_steam_input_gamepads()

    assert set(manager.gamepads) == {-1000001, -1000000 - (1 + (1 << 31))}


def test_steam_adapter_forwards_rumble_to_native_handle(monkeypatch):
    calls = []
    monkeypatch.setitem(
        sys.modules,
        "steam_integration",
        SimpleNamespace(
            trigger_steam_input_vibration=lambda handle, low, high: calls.append(
                (handle, low, high)
            ) or True
        ),
    )
    joystick = _SteamInputJoystick(_snapshot(handle=456), -456)

    assert joystick.rumble(0.25, 0.75, 100) is True
    joystick.stop_rumble()

    assert calls == [(456, 0.25, 0.75), (456, 0.0, 0.0)]


def test_steam_adapter_stops_rumble_after_requested_duration(monkeypatch):
    import time

    calls = []
    monkeypatch.setitem(
        sys.modules,
        "steam_integration",
        SimpleNamespace(
            trigger_steam_input_vibration=lambda handle, low, high: calls.append(
                (handle, low, high)
            ) or True
        ),
    )
    joystick = _SteamInputJoystick(_snapshot(handle=789), -789)

    assert joystick.rumble(0.3, 0.6, 20) is True
    time.sleep(0.08)

    assert calls == [(789, 0.3, 0.6), (789, 0.0, 0.0)]


def test_new_rumble_replaces_old_stop_timer(monkeypatch):
    import time

    calls = []
    monkeypatch.setitem(
        sys.modules,
        "steam_integration",
        SimpleNamespace(
            trigger_steam_input_vibration=lambda handle, low, high: calls.append(
                (handle, low, high)
            ) or True
        ),
    )
    joystick = _SteamInputJoystick(_snapshot(handle=900), -900)

    assert joystick.rumble(0.2, 0.3, 20) is True
    assert joystick.rumble(0.7, 0.8, 80) is True
    time.sleep(0.04)
    assert calls == [(900, 0.2, 0.3), (900, 0.7, 0.8)]
    time.sleep(0.08)
    assert calls[-1] == (900, 0.0, 0.0)
    assert calls.count((900, 0.0, 0.0)) == 1


def test_sdl_controller_family_detection_covers_major_devices():
    manager = _manager()
    expected = {
        "Xbox Series X Controller": "xbox",
        "Generic XInput Controller": "xbox",
        "DualSense Wireless Controller": "playstation",
        "DUALSHOCK 4 Wireless Controller": "playstation",
        "Nintendo Switch Pro Controller": "nintendo",
        "Joy-Con (L/R)": "nintendo",
        "Steam Deck Controller": "xbox",
    }

    for name, family in expected.items():
        joystick = SimpleNamespace(get_name=lambda value=name: value)
        assert manager._detect_type(joystick) == family
