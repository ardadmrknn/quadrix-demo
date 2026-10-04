"""Regression coverage for Kart Ustaligi (Mystery) slot gamepad bindings — B1.

DOGRULANMIS BUG (fix oncesi):
- `settings_manager.DEFAULT_CONTROLS['gamepad']` `slot_1..slot_6` icin buton
  atamasi iceriyordu, AMA `gamepad_manager.DEFAULT_GAMEPAD_BINDINGS` icinde
  `slot_1..6` YOKTU ve `_load_settings`'teki `button_actions` listesinde de
  yer almiyordu. `if action not in self._bindings: continue` guard'i yuzunden
  slot_N hicbir zaman `_bindings`'e girmiyordu →
  `was_action_just_pressed('slot_N')` / `is_action_pressed('slot_N')` DAIMA
  False donuyordu → Kart Ustaligi'nda gamepad ile slot/kart tetiklemesi
  tamamen oludu.

Bu testler:
1. DEFAULT_GAMEPAD_BINDINGS slot/card aksiyonlarinin var oldugunu,
2. settings_manager defaultlari ile gamepad_manager defaultlarinin
   slot layout'unda celismedigini,
3. _load_settings'in slot binding'lerini settings'ten yukledigini,
4. poll API'lerinin (was_action_just_pressed / is_action_pressed) buton ve
   trigger slot'lari icin edge-detect ettigini
dogrular.
"""

from __future__ import annotations

import copy
import os
import sys
import types

import pytest

_SRC_DIR = os.path.join(os.path.dirname(__file__), '..', 'src')
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

import gamepad_manager as gpm_module  # noqa: E402
from gamepad_manager import (  # noqa: E402
    DEFAULT_GAMEPAD_BINDINGS,
    GamepadManager,
    GamepadState,
)

SLOT_ACTIONS = ('slot_1', 'slot_2', 'slot_3', 'slot_4', 'slot_5', 'slot_6')


def _make_manager(bindings=None):
    """GamepadManager'i __init__ yan etkileri (settings load + scan) olmadan kur."""
    manager = GamepadManager.__new__(GamepadManager)
    manager.gamepads = {}
    manager.enabled = True
    manager.rumble_multiplier = 1.0
    manager._context = GamepadManager.CONTEXT_GAME
    manager._menu_pointer_active = False
    manager._suppress_pointer_mode = False
    manager._bindings = copy.deepcopy(
        DEFAULT_GAMEPAD_BINDINGS if bindings is None else bindings
    )
    manager.DEADZONE = 0.35
    manager.DIGITAL_THRESHOLD = 0.6
    manager.TRIGGER_THRESHOLD = 0.5
    return manager


def _fake_gamepad(buttons=None, prev_buttons=None,
                  left_trigger=0.0, right_trigger=0.0,
                  prev_left_trigger_pressed=False,
                  prev_right_trigger_pressed=False):
    fake_js = types.SimpleNamespace(
        get_init=lambda: True,
        get_name=lambda: 'Xbox Wireless',
    )
    gp = GamepadState(
        joystick=fake_js,
        controller=None,
        gamepad_type='xbox',
        name='Xbox Wireless',
        guid='',
        instance_id=1,
    )
    gp.buttons = dict(buttons or {})
    gp.prev_buttons = dict(prev_buttons or {})
    gp.left_trigger = left_trigger
    gp.right_trigger = right_trigger
    gp.prev_left_trigger_pressed = prev_left_trigger_pressed
    gp.prev_right_trigger_pressed = prev_right_trigger_pressed
    return gp


# ---------------------------------------------------------------------------
# 1. Defaults present (fix oncesi bu test fail ederdi)
# ---------------------------------------------------------------------------

def test_slot_actions_present_in_default_bindings():
    for action in SLOT_ACTIONS:
        assert action in DEFAULT_GAMEPAD_BINDINGS, (
            f'{action} DEFAULT_GAMEPAD_BINDINGS icinde yok → slot gamepad ile '
            f'tetiklenemez (B1)'
        )


def test_card_actions_present_in_default_bindings():
    for action in (
        'card_rewind', 'card_sniper', 'card_time_capsule_save',
        'card_time_capsule_restore', 'card_freeze', 'card_phase_shift',
        'card_ghost', 'card_hammer', 'card_bomb',
    ):
        assert action in DEFAULT_GAMEPAD_BINDINGS


def test_default_slot_layout_matches_settings_manager_defaults():
    """gamepad_manager defaultlari, settings dosyasi yokken kullanildigi icin
    settings_manager 'gamepad' blogu ile ayni slot layout'unu temsil etmeli."""
    from settings_manager import DEFAULT_CONTROLS

    gp_defaults = DEFAULT_CONTROLS['gamepad']
    # settings primary (pseudo-index) -> gamepad_manager binding beklentisi.
    # Trigger pseudo-index: 100 = left, 101 = right.
    # YENI LAYOUT: slot_1..4 = A/X/B/Y, slot_5/6 = LT/RT.
    expected_primary = {
        'slot_1': 0,
        'slot_2': 2,
        'slot_3': 1,
        'slot_4': 3,
        'slot_5': 100,
        'slot_6': 101,
    }
    expected_binding = {
        'slot_1': {'button': 0},
        'slot_2': {'button': 2},
        'slot_3': {'button': 1},
        'slot_4': {'button': 3},
        'slot_5': {'trigger': 'left'},
        'slot_6': {'trigger': 'right'},
    }
    for action, primary in expected_primary.items():
        assert gp_defaults[action]['primary'] == primary
        assert DEFAULT_GAMEPAD_BINDINGS[action] == expected_binding[action]


# ---------------------------------------------------------------------------
# 2. poll API edge detection — buton slot'lari
# ---------------------------------------------------------------------------

def test_was_action_just_pressed_for_button_slot():
    manager = _make_manager()
    # slot_1 default = button 0 (A)
    manager.gamepads[0] = _fake_gamepad(
        buttons={0: True}, prev_buttons={0: False}
    )
    assert manager.was_action_just_pressed('slot_1') is True
    assert manager.is_action_pressed('slot_1') is True


def test_button_slot_not_just_pressed_when_held():
    manager = _make_manager()
    manager.gamepads[0] = _fake_gamepad(
        buttons={0: True}, prev_buttons={0: True}
    )
    # Hala basili ama yeni basilmadi → edge yok
    assert manager.was_action_just_pressed('slot_1') is False
    # Ama is_action_pressed True kalmali (poll)
    assert manager.is_action_pressed('slot_1') is True


def test_was_action_just_pressed_for_trigger_slot():
    manager = _make_manager()
    # slot_5 default = trigger left (pseudo 100)
    manager.gamepads[0] = _fake_gamepad(
        left_trigger=0.9, prev_left_trigger_pressed=False
    )
    assert manager.was_action_just_pressed('slot_5') is True
    assert manager.is_action_pressed('slot_5') is True

    # slot_6 = trigger right
    manager.gamepads[0] = _fake_gamepad(
        right_trigger=0.9, prev_right_trigger_pressed=False
    )
    assert manager.was_action_just_pressed('slot_6') is True


def test_all_six_slots_resolve_to_distinct_inputs():
    manager = _make_manager()
    seen = set()
    for action in SLOT_ACTIONS:
        indices = manager.get_action_button_indices(action)
        assert indices, f'{action} icin buton/trigger index cozulmedi'
        key = tuple(indices)
        assert key not in seen, f'{action} baska bir slot ile ayni input ({key})'
        seen.add(key)


# ---------------------------------------------------------------------------
# 3. _load_settings slot binding'leri settings'ten yukler
# ---------------------------------------------------------------------------

def test_load_settings_populates_slot_bindings(monkeypatch):
    """Fix oncesi: button_actions listesinde slot_N olmadigi icin settings'teki
    slot atamasi `_bindings`'e hic islenmiyordu. Burada slot_1'i farkli bir
    butona remap edip yuklendigini kanitliyoruz."""

    class _FakeSettings:
        def get_controls(self):
            return {
                'gamepad': {
                    'enabled': True,
                    'rumble': 'high',
                    'slot_1': {'primary': 0, 'secondary': -1},   # A butonuna remap
                    'slot_6': {'primary': 101, 'secondary': -1},  # RT trigger'a remap
                }
            }

    fake_module = types.SimpleNamespace(SettingsManager=lambda: _FakeSettings())
    monkeypatch.setitem(sys.modules, 'settings_manager', fake_module)

    manager = _make_manager()
    manager._load_settings()

    # slot_1 artik A butonu (0)
    assert manager._bindings['slot_1'].get('button') == 0
    # slot_6 artik RT trigger
    assert manager._bindings['slot_6'].get('trigger') == 'right'
    # Dokunulmayan slotlar default'ta kalmali (yeni layout: slot_2 = X = 2)
    assert manager._bindings['slot_2'].get('button') == 2


# ---------------------------------------------------------------------------
# 4. Slot aksiyonlari sentetik klavye event'i URETMEZ (poll-only invariant)
# ---------------------------------------------------------------------------

def test_slot_actions_do_not_emit_synthetic_key_events():
    """slot_N poll-only olmali; ACTION_TO_KEY'de bulunmamali ve buton/trigger
    event uretiminde yer almamali (aksi halde hold/discard ile cift event)."""
    from gamepad_manager import ACTION_TO_KEY

    for action in SLOT_ACTIONS:
        assert action not in ACTION_TO_KEY, (
            f'{action} ACTION_TO_KEY icinde olmamali → poll-only kalmali'
        )

    manager = _make_manager()
    # YENI LAYOUT cift-tetik kaniti: slot butonlari A(0)/X(2)/B(1)/Y(3) ve
    # slot trigger'lari LT/RT basili. Bu butonlar oyun baglaminda HICBIR
    # sentetik KEYDOWN uretmemeli (slot'lar poll-only). Yalnizca hold (LB=9)
    # ve hard_drop (RB=10) sentetik uretmeli.
    gp = _fake_gamepad(
        buttons={0: True, 1: True, 2: True, 3: True},
        prev_buttons={0: False, 1: False, 2: False, 3: False},
        left_trigger=0.9, prev_left_trigger_pressed=False,
        right_trigger=0.9, prev_right_trigger_pressed=False,
    )
    manager.gamepads[0] = gp
    btn_events = manager._generate_button_events(gp)
    keys = [getattr(e, 'key', None) for e in btn_events]
    # Slot poll API'leri True donmeli (trigger event uretimi prev-state'i
    # mutasyona ugrattigi icin poll'u event uretiminden ONCE dogrula)
    assert manager.was_action_just_pressed('slot_1') is True  # A
    assert manager.was_action_just_pressed('slot_2') is True  # X
    assert manager.was_action_just_pressed('slot_3') is True  # B
    assert manager.was_action_just_pressed('slot_4') is True  # Y
    assert manager.was_action_just_pressed('slot_5') is True  # LT
    assert manager.was_action_just_pressed('slot_6') is True  # RT
    # Trigger event uretimi de slot'lar icin sentetik key URETMEMELI
    trig_events = manager._generate_trigger_events(gp)
    keys += [getattr(e, 'key', None) for e in trig_events]
    # A/X/B/Y ve LT/RT slot girisleri → sentetik key URETILMEMELI
    assert keys == [], (
        f'Slot butonlari sentetik key uretti (cift-tetik): {keys}'
    )


def test_hold_and_hard_drop_still_emit_on_lb_rb():
    """LB → hold (K_c), RB → hard_drop (K_SPACE) sentetikleri korunmali."""
    manager = _make_manager()
    gp = _fake_gamepad(
        buttons={9: True, 10: True},
        prev_buttons={9: False, 10: False},
    )
    manager.gamepads[0] = gp
    btn_events = manager._generate_button_events(gp)
    keys = [getattr(e, 'key', None) for e in btn_events]
    assert gpm_module.pygame.K_c in keys       # hold (LB=9)
    assert gpm_module.pygame.K_SPACE in keys   # hard_drop (RB=10)


def test_dpad_up_rotates_and_down_soft_drops_in_game():
    """rotate binding bosa cekildi ama D-pad ^ = K_UP (donme) ve
    D-pad v = K_DOWN (soft drop) hardcoded emisyonla oyun-icinde calismali."""
    manager = _make_manager()
    manager._context = GamepadManager.CONTEXT_GAME

    # D-pad ^ (SDL hat: yukari = +1)
    gp_up = _fake_gamepad()
    gp_up.dpad = (0, 1)
    gp_up.prev_dpad = (0, 0)
    manager.gamepads[0] = gp_up
    up_events = manager._generate_dpad_events(gp_up, 16.0)
    up_keys = [(getattr(e, 'key', None), e.type) for e in up_events]
    assert (gpm_module.pygame.K_UP, gpm_module.pygame.KEYDOWN) in up_keys

    # D-pad v (asagi = -1)
    gp_down = _fake_gamepad()
    gp_down.dpad = (0, -1)
    gp_down.prev_dpad = (0, 0)
    manager.gamepads[1] = gp_down
    down_events = manager._generate_dpad_events(gp_down, 16.0)
    down_keys = [(getattr(e, 'key', None), e.type) for e in down_events]
    assert (gpm_module.pygame.K_DOWN, gpm_module.pygame.KEYDOWN) in down_keys
