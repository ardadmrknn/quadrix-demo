"""Steam Input entegrasyon katmanı testleri (demo deposu, P0-1 v2 paritesi).

v2'deki test_steam_input_integration.py'nin demo deposuna taşıması: sahte
DLL üzerinden ISteamInput flat API bağlamalarını, snapshot okumayı,
manifest retry davranışını ve titreşim keleme (clamping) sözleşmesini
doğrular. Gerçek Steam istemcisi gerektirmeden (fake DLL) çalışır.
"""

from __future__ import annotations

import ctypes
import importlib
import sys
from pathlib import Path


SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


class _FakeSteamInputDLL:
    def __init__(self, controller_count: int = 0):
        self.controller_count = controller_count
        self.run_frame_calls = 0
        self.activated: list[tuple[int, int]] = []
        self.vibrations: list[tuple[int, int, int]] = []

    def SteamAPI_ISteamInput_RunFrame(self, interface, reserved):
        self.run_frame_calls += 1

    def SteamAPI_ISteamInput_GetConnectedControllers(self, interface, handles):
        for index in range(self.controller_count):
            handles[index] = 1000 + index
        return self.controller_count

    def SteamAPI_ISteamInput_ActivateActionSet(self, interface, handle, action_set):
        self.activated.append((int(handle.value), int(action_set.value)))

    def SteamAPI_ISteamInput_GetDigitalActionData(self, interface, handle, action_handle):
        steam = sys.modules["steam_integration"]
        data = steam._InputDigitalActionData()
        data.bActive = True
        data.bState = int(action_handle.value) in (1, 15)
        return data

    def SteamAPI_ISteamInput_GetAnalogActionData(self, interface, handle, action_handle):
        steam = sys.modules["steam_integration"]
        data = steam._InputAnalogActionData()
        data.bActive = True
        data.x = 0.5 if int(action_handle.value) == 101 else -0.25
        data.y = -0.75 if int(action_handle.value) == 101 else 0.25
        return data

    def SteamAPI_ISteamInput_GetInputTypeForHandle(self, interface, handle):
        return 3

    def SteamAPI_ISteamInput_TriggerVibration(self, interface, handle, low, high):
        self.vibrations.append((int(handle.value), int(low.value), int(high.value)))


class _DelayedManifestDLL:
    def __init__(self):
        self.manifest_set_calls = 0
        self.mapping_ready = False

    def SteamAPI_ISteamInput_SetInputActionManifestFilePath(self, interface, path):
        self.manifest_set_calls += 1
        return True

    def SteamAPI_ISteamInput_GetActionSetHandle(self, interface, name):
        return 1 if self.mapping_ready else 0

    def SteamAPI_ISteamInput_GetDigitalActionHandle(self, interface, name):
        return 1 if self.mapping_ready else 0

    def SteamAPI_ISteamInput_GetAnalogActionHandle(self, interface, name):
        return 1 if self.mapping_ready else 0


def _fresh_module():
    sys.modules.pop("steam_integration", None)
    return importlib.import_module("steam_integration")


def test_steam_input_controller_count_returns_zero_when_unavailable(monkeypatch):
    steam = _fresh_module()
    monkeypatch.setattr(steam, "_init_ok", False)
    monkeypatch.setattr(steam, "_dll", None)
    monkeypatch.setattr(steam, "_isteam_input", None)
    monkeypatch.setattr(steam, "_steam_input_initialized", False)

    assert steam.is_steam_input_available() is False
    assert steam.get_steam_input_controller_count() == 0


def test_steam_input_controller_count_polls_initialized_interface(monkeypatch):
    steam = _fresh_module()
    fake_dll = _FakeSteamInputDLL(controller_count=2)
    fake_interface = ctypes.c_void_p(1234)

    monkeypatch.setattr(steam, "_init_ok", True)
    monkeypatch.setattr(steam, "_shutdown_requested", False)
    monkeypatch.setattr(steam, "_dll", fake_dll)
    monkeypatch.setattr(steam, "_isteam_input", fake_interface)
    monkeypatch.setattr(steam, "_steam_input_initialized", True)

    assert steam.is_steam_input_available() is True
    assert steam.get_steam_input_controller_count() == 2
    assert fake_dll.run_frame_calls == 1


def test_setup_dll_functions_declares_steam_input_flat_api():
    steam = _fresh_module()

    class _Function:
        restype = None
        argtypes = None

        def __call__(self, *args):
            return 0

    class _DLL:
        def __getattr__(self, name):
            fn = _Function()
            setattr(self, name, fn)
            return fn

    dll = _DLL()
    steam._setup_dll_functions(dll)

    assert dll.SteamAPI_SteamInput_v006.restype is ctypes.c_void_p
    assert dll.SteamAPI_ISteamInput_Init.restype is ctypes.c_bool
    assert dll.SteamAPI_ISteamInput_Init.argtypes == [ctypes.c_void_p, ctypes.c_bool]
    assert dll.SteamAPI_ISteamInput_GetConnectedControllers.restype is ctypes.c_int
    assert dll.SteamAPI_ISteamInput_GetDigitalActionData.restype is steam._InputDigitalActionData
    assert dll.SteamAPI_ISteamInput_GetAnalogActionData.restype is steam._InputAnalogActionData
    assert dll.SteamAPI_ISteamInput_TriggerVibration.restype is None
    assert dll.SteamAPI_ISteamInput_TriggerVibration.argtypes == [
        ctypes.c_void_p, ctypes.c_uint64, ctypes.c_ushort, ctypes.c_ushort,
    ]


def test_steam_input_action_snapshot_reads_buttons_and_sticks(monkeypatch):
    steam = _fresh_module()
    fake_dll = _FakeSteamInputDLL(controller_count=1)

    monkeypatch.setattr(steam, "_init_ok", True)
    monkeypatch.setattr(steam, "_shutdown_requested", False)
    monkeypatch.setattr(steam, "_dll", fake_dll)
    monkeypatch.setattr(steam, "_isteam_input", ctypes.c_void_p(1234))
    monkeypatch.setattr(steam, "_steam_input_initialized", True)
    monkeypatch.setattr(steam, "_steam_input_manifest_ready", True)
    monkeypatch.setattr(steam, "_steam_input_action_set_handle", 99)
    monkeypatch.setattr(
        steam,
        "_steam_input_digital_handles",
        {name: index + 1 for index, name in enumerate(steam._STEAM_INPUT_DIGITAL_ACTIONS)},
    )
    monkeypatch.setattr(steam, "_steam_input_analog_handles", {"left_stick": 101, "right_stick": 102})

    snapshots = steam.get_steam_input_snapshots()

    assert len(snapshots) == 1
    assert snapshots[0]["handle"] == 1000
    assert snapshots[0]["input_type"] == 3
    assert snapshots[0]["buttons"]["a"] is True
    assert snapshots[0]["buttons"]["left_trigger"] is True
    assert snapshots[0]["buttons"]["b"] is False
    assert snapshots[0]["axes"]["left_stick"] == (0.5, -0.75)
    assert snapshots[0]["axes"]["right_stick"] == (-0.25, 0.25)
    assert fake_dll.activated == [(1000, 99)]


def test_manifest_is_not_reset_while_waiting_for_action_handles(monkeypatch, tmp_path):
    steam = _fresh_module()
    fake_dll = _DelayedManifestDLL()
    manifest = tmp_path / "quadrix_actions.vdf"
    manifest.write_text('"Action Manifest" {}', encoding="utf-8")

    monkeypatch.setattr(steam, "_isteam_input", ctypes.c_void_p(1234))
    monkeypatch.setattr(steam, "_steam_input_initialized", True)
    monkeypatch.setattr(steam, "_steam_input_manifest_configured", False)
    monkeypatch.setattr(steam, "_steam_input_manifest_ready", False)
    monkeypatch.setattr(steam, "_steam_input_manifest_retry_at", 0.0)
    monkeypatch.setattr(steam, "_find_steam_input_manifest", lambda: manifest)

    assert steam._configure_steam_input_manifest(fake_dll) is False
    assert fake_dll.manifest_set_calls == 1
    assert steam._steam_input_manifest_configured is True

    fake_dll.mapping_ready = True
    monkeypatch.setattr(steam, "_steam_input_manifest_retry_at", 0.0)

    assert steam._configure_steam_input_manifest(fake_dll) is True
    assert fake_dll.manifest_set_calls == 1
    assert steam._steam_input_manifest_ready is True


def test_steam_input_vibration_clamps_and_forwards_motor_values(monkeypatch):
    steam = _fresh_module()
    fake_dll = _FakeSteamInputDLL(controller_count=1)

    monkeypatch.setattr(steam, "_init_ok", True)
    monkeypatch.setattr(steam, "_shutdown_requested", False)
    monkeypatch.setattr(steam, "_dll", fake_dll)
    monkeypatch.setattr(steam, "_isteam_input", ctypes.c_void_p(1234))
    monkeypatch.setattr(steam, "_steam_input_initialized", True)

    assert steam.trigger_steam_input_vibration(1000, -0.5, 1.5) is True
    assert fake_dll.vibrations == [(1000, 0, 65535)]
