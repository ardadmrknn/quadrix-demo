"""Regression: LT/RT (slot_5/slot_6) trigger slotlarinin GERCEK update() dongu
zamanlamasinda edge-detect etmesi.

DOGRULANMIS BUG (fix oncesi):
- `slot_5`/`slot_6` yuvalari yalnizca `was_action_just_pressed()` ile poll edilir
  (sentetik klavye event'i URETMEZLER).
- `prev_left_trigger_pressed` / `prev_right_trigger_pressed`, `update()` SONUNDA
  `_generate_trigger_events()` icinde GUNCEL degere set ediliyordu. Oyun daha
  sonra `was_action_just_pressed('slot_5')` cagirinca now == prev oldugundan
  edge HICBIR ZAMAN algilanmiyordu → Kart Ustaligi'nda LT/RT ile slot tetikleme
  oluydu.
- Butonlar (slot_1..4) `prev_buttons`'u update() BASINDA kaydettigi icin dogru
  calisiyordu; trigger'larda bu simetri eksikti.

Fix: trigger prev durumu da update() basinda (yeni eksenler okunmadan once)
kaydedilir; frame sonundaki overwrite kaldirildi.

Bu test izole `was_action_just_pressed` cagrisi DEGIL, tam `update()` dongusunu
suren ve sonra poll eden gercek oyun akisini taklit eder; bu yuzden zamanlama
bug'ini yakalar.
"""

from __future__ import annotations

import copy
import os
import sys
import types
from types import SimpleNamespace

import pytest

_SRC_DIR = os.path.join(os.path.dirname(__file__), '..', 'src')
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

import gamepad_manager as gamepad_manager_module  # noqa: E402
from gamepad_manager import (  # noqa: E402
    DEFAULT_GAMEPAD_BINDINGS,
    GamepadManager,
    GamepadState,
)


class _DummyJoystick:
    """Eksen degerleri frame'ler arasi degistirilebilen sahte joystick.

    Eksen duzeni (SDL GameController): (LX, LY, RX, RY, LT, RT) → 6 eksen.
    Trigger ham araligi -1 (birak) .. +1 (tam bas).
    """

    def __init__(self, axes):
        self.axes = list(axes)
        self.buttons: dict[int, bool] = {}
        self.hats: tuple = ()

    def get_init(self) -> bool:
        return True

    def get_numaxes(self) -> int:
        return len(self.axes)

    def get_axis(self, index: int) -> float:
        return self.axes[index]

    def get_numbuttons(self) -> int:
        return 0

    def get_button(self, index: int) -> int:
        return 0

    def get_numhats(self) -> int:
        return len(self.hats)

    def get_hat(self, index: int):
        return self.hats[index]


def _make_manager() -> GamepadManager:
    manager = GamepadManager.__new__(GamepadManager)
    manager.enabled = True
    manager.gamepads = {}
    manager.rumble_enabled = False
    manager.rumble_level = 'off'
    manager.rumble_multiplier = 0.0
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
    # Kart Ustaligi oyun-ici baglam: trigger event'leri yalnizca burada uretilir.
    manager._context = GamepadManager.CONTEXT_GAME
    manager._menu_pointer_active = False
    manager._suppress_pointer_mode = False
    manager._bindings = copy.deepcopy(DEFAULT_GAMEPAD_BINDINGS)
    manager._check_connections = lambda: None
    return manager


@pytest.fixture(autouse=True)
def _patch_pygame_event(monkeypatch):
    """update() icindeki sentetik event uretimi pygame.event.Event'e ihtiyac duyar."""
    gp_pygame = gamepad_manager_module.pygame
    if not hasattr(gp_pygame, 'event'):
        monkeypatch.setattr(gp_pygame, 'event', SimpleNamespace(), raising=False)
    monkeypatch.setattr(
        gp_pygame.event,
        'Event',
        lambda event_type, **payload: SimpleNamespace(type=event_type, **payload),
        raising=False,
    )
    if not hasattr(gp_pygame, 'display'):
        monkeypatch.setattr(gp_pygame, 'display', SimpleNamespace(), raising=False)
    monkeypatch.setattr(
        gp_pygame.display, 'get_window_size', lambda: (1280, 720), raising=False
    )
    monkeypatch.setattr(
        gp_pygame.display, 'get_surface', lambda: None, raising=False
    )


_LX, _LY, _RX, _RY = 0.0, 0.0, 0.0, 0.0


def _axes(lt: float, rt: float):
    return (_LX, _LY, _RX, _RY, lt, rt)


def _drive(manager, gp, lt, rt):
    """Bir frame: ham eksenleri ata, update() cagir (gercek oyun dongusu)."""
    gp.joystick.axes = list(_axes(lt, rt))
    manager.update(16.0)


def test_lt_slot5_edge_detected_through_update_loop():
    manager = _make_manager()
    gp = GamepadState(joystick=_DummyJoystick(_axes(-1.0, -1.0)), gamepad_type='xbox')
    manager.gamepads[0] = gp

    _drive(manager, gp, lt=-1.0, rt=-1.0)
    assert manager.was_action_just_pressed('slot_5') is False

    _drive(manager, gp, lt=1.0, rt=-1.0)
    assert manager.was_action_just_pressed('slot_5') is True

    _drive(manager, gp, lt=1.0, rt=-1.0)
    assert manager.was_action_just_pressed('slot_5') is False

    _drive(manager, gp, lt=-1.0, rt=-1.0)
    assert manager.was_action_just_pressed('slot_5') is False

    _drive(manager, gp, lt=1.0, rt=-1.0)
    assert manager.was_action_just_pressed('slot_5') is True


def test_rt_slot6_edge_detected_through_update_loop():
    manager = _make_manager()
    gp = GamepadState(joystick=_DummyJoystick(_axes(-1.0, -1.0)), gamepad_type='xbox')
    manager.gamepads[0] = gp

    _drive(manager, gp, lt=-1.0, rt=-1.0)
    assert manager.was_action_just_pressed('slot_6') is False

    _drive(manager, gp, lt=-1.0, rt=1.0)
    assert manager.was_action_just_pressed('slot_6') is True

    _drive(manager, gp, lt=-1.0, rt=1.0)
    assert manager.was_action_just_pressed('slot_6') is False


def test_is_action_pressed_holds_while_trigger_down():
    manager = _make_manager()
    gp = GamepadState(joystick=_DummyJoystick(_axes(-1.0, -1.0)), gamepad_type='xbox')
    manager.gamepads[0] = gp

    _drive(manager, gp, lt=1.0, rt=-1.0)
    assert manager.is_action_pressed('slot_5') is True
    _drive(manager, gp, lt=1.0, rt=-1.0)
    assert manager.is_action_pressed('slot_5') is True
    _drive(manager, gp, lt=-1.0, rt=-1.0)
    assert manager.is_action_pressed('slot_5') is False
