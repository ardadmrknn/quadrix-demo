"""Game-over / level-failed gamepad eslemesi — restart=Y(3) / level_select=X(2).

Sektor-standardi: game-over/level-failed ekranlarinda Y = yeniden dene (retry),
X = level sec (campaign). Bu iki aksiyon POLL-ONLY'dir:
  - ACTION_TO_KEY'de level_select yoktur; restart=K_r vardir AMA sentetik
    emisyon listelerinde (game_actions_list / menu_actions_list) yer almaz →
    oyun ortasinda sentetik KEYDOWN URETMEZLER.
  - Yalnizca game-over/level-failed handler'lari icinde
    was_action_just_pressed('restart' / 'level_select') ile okunurlar.

Bu testler:
1. DEFAULT_GAMEPAD_BINDINGS / settings_manager default'larinin restart=Y(3),
   level_select=X(2) oldugunu,
2. poll API'lerinin (was_action_just_pressed / is_action_pressed) bu butonlar
   icin edge-detect ettigini,
3. restart/level_select'in oyun-ici VE menu sentetik emisyonu URETMEDIGINI,
4. v3→v4 settings migration'inin unmodified kullaniciyi yeni default'a tasidigini
   ve ozellestirmeyi koruydugunu (idempotent),
dogrular.
"""

from __future__ import annotations

import copy
import os
import sys
import types

_SRC_DIR = os.path.join(os.path.dirname(__file__), '..', 'src')
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

import gamepad_manager as gpm_module  # noqa: E402
from gamepad_manager import (  # noqa: E402
    ACTION_TO_KEY,
    DEFAULT_GAMEPAD_BINDINGS,
    GamepadManager,
    GamepadState,
)


def _make_manager(bindings=None, context=GamepadManager.CONTEXT_GAME):
    manager = GamepadManager.__new__(GamepadManager)
    manager.gamepads = {}
    manager.enabled = True
    manager.rumble_multiplier = 1.0
    manager._context = context
    manager._menu_pointer_active = False
    manager._suppress_pointer_mode = False
    manager._bindings = copy.deepcopy(
        DEFAULT_GAMEPAD_BINDINGS if bindings is None else bindings
    )
    manager.DEADZONE = 0.35
    manager.DIGITAL_THRESHOLD = 0.6
    manager.TRIGGER_THRESHOLD = 0.5
    return manager


def _fake_gamepad(buttons=None, prev_buttons=None):
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
    return gp


# ---------------------------------------------------------------------------
# 1. Defaults: restart=Y(3), level_select=X(2)
# ---------------------------------------------------------------------------

def test_default_bindings_restart_is_y_level_select_is_x():
    assert DEFAULT_GAMEPAD_BINDINGS['restart'] == {'button': 3}      # Y / Triangle
    assert DEFAULT_GAMEPAD_BINDINGS['level_select'] == {'button': 2}  # X / Square


def test_settings_defaults_match_gamepad_defaults():
    from settings_manager import DEFAULT_CONTROLS

    gp = DEFAULT_CONTROLS['gamepad']
    assert gp['restart'] == {'primary': 3, 'secondary': -1}
    assert gp['level_select'] == {'primary': 2, 'secondary': -1}


# ---------------------------------------------------------------------------
# 2. poll API edge detection
# ---------------------------------------------------------------------------

def test_restart_poll_edge_detect_on_y():
    manager = _make_manager()
    manager.gamepads[0] = _fake_gamepad(buttons={3: True}, prev_buttons={3: False})
    assert manager.was_action_just_pressed('restart') is True
    assert manager.is_action_pressed('restart') is True


def test_level_select_poll_edge_detect_on_x():
    manager = _make_manager()
    manager.gamepads[0] = _fake_gamepad(buttons={2: True}, prev_buttons={2: False})
    assert manager.was_action_just_pressed('level_select') is True
    assert manager.is_action_pressed('level_select') is True


def test_restart_not_just_pressed_when_held():
    manager = _make_manager()
    manager.gamepads[0] = _fake_gamepad(buttons={3: True}, prev_buttons={3: True})
    assert manager.was_action_just_pressed('restart') is False
    assert manager.is_action_pressed('restart') is True


# ---------------------------------------------------------------------------
# 3. POLL-ONLY: sentetik emisyon URETMEZ (oyun-ici + menu)
# ---------------------------------------------------------------------------

def test_level_select_absent_from_action_to_key():
    # level_select hicbir sentetik tusla eslesmemeli.
    assert 'level_select' not in ACTION_TO_KEY
    # restart geriye-donuk uyumluluk icin K_r'de kalir AMA emit listesinde
    # olmadigi icin sentetik uretmez (asagidaki testler kanit).
    assert ACTION_TO_KEY.get('restart') == gpm_module.pygame.K_r


def test_restart_and_level_select_no_synthetic_in_game():
    """Oyun baglaminda Y(3)/X(2) basinca restart/level_select sentetik KEYDOWN
    URETMEMELI (poll-only). Boylece game-over disinda Y/X serbest kalir."""
    manager = _make_manager(context=GamepadManager.CONTEXT_GAME)
    gp = _fake_gamepad(
        buttons={2: True, 3: True},
        prev_buttons={2: False, 3: False},
    )
    manager.gamepads[0] = gp
    # Poll True donmeli (game-over handler'i bunu okur)
    assert manager.was_action_just_pressed('restart') is True
    assert manager.was_action_just_pressed('level_select') is True
    # Ama sentetik K_r URETILMEMELI
    events = manager._generate_button_events(gp)
    keys = [getattr(e, 'key', None) for e in events]
    assert gpm_module.pygame.K_r not in keys, (
        f'restart/level_select oyun-ici sentetik key uretti: {keys}'
    )


def test_restart_and_level_select_no_synthetic_in_menu():
    """Menu baglaminda da restart/level_select sentetik uretmez."""
    manager = _make_manager(context=GamepadManager.CONTEXT_MENU)
    gp = _fake_gamepad(
        buttons={2: True, 3: True},
        prev_buttons={2: False, 3: False},
    )
    manager.gamepads[0] = gp
    events = manager._generate_button_events(gp)
    keys = [getattr(e, 'key', None) for e in events]
    assert gpm_module.pygame.K_r not in keys


# ---------------------------------------------------------------------------
# 4. _load_settings: restart/level_select settings'ten yuklenir
# ---------------------------------------------------------------------------

def test_load_settings_populates_restart_and_level_select(monkeypatch):
    class _FakeSettings:
        def get_controls(self):
            return {
                'gamepad': {
                    'enabled': True,
                    'rumble': 'high',
                    'restart': {'primary': 3, 'secondary': -1},
                    'level_select': {'primary': 2, 'secondary': -1},
                }
            }

    fake_module = types.SimpleNamespace(SettingsManager=lambda: _FakeSettings())
    monkeypatch.setitem(sys.modules, 'settings_manager', fake_module)

    manager = _make_manager()
    manager._load_settings()

    assert manager._bindings['restart'].get('button') == 3
    assert manager._bindings['level_select'].get('button') == 2


# ---------------------------------------------------------------------------
# 5. v3 → v4 settings migration
# ---------------------------------------------------------------------------

def _v3_default_gamepad_block() -> dict:
    """v2 (game-over eslemesi oncesi; demo zinciri v1-v2-v3 uyarlamasi) gamepad blogunun diske yazilmis hali.
    restart devre disi (-1), level_select yok."""
    from settings_manager import DEFAULT_CONTROLS

    block = copy.deepcopy(DEFAULT_CONTROLS['gamepad'])
    block['restart'] = {'primary': -1, 'secondary': -1}  # v2: devre disi
    block.pop('level_select', None)                       # v2: yoktu
    block['gamepad_layout_version'] = 2
    return block


def test_v2_unmodified_user_migrates_to_v3():
    from settings_manager import CURRENT_GAMEPAD_LAYOUT_VERSION, SettingsManager

    sm = SettingsManager.__new__(SettingsManager)
    gp = sm._merge_controls({'gamepad': _v3_default_gamepad_block()})['gamepad']

    assert gp['restart'] == {'primary': 3, 'secondary': -1}
    assert gp['level_select'] == {'primary': 2, 'secondary': -1}
    assert gp['gamepad_layout_version'] == CURRENT_GAMEPAD_LAYOUT_VERSION


def test_v2_customized_restart_is_preserved():
    """Kullanici v3'te restart'i elle bir butona atadiysa EZME yok."""
    from settings_manager import SettingsManager

    sm = SettingsManager.__new__(SettingsManager)
    block = _v3_default_gamepad_block()
    block['restart'] = {'primary': 5, 'secondary': -1}  # Guide'a ozel atama
    gp = sm._merge_controls({'gamepad': block})['gamepad']
    assert gp['restart']['primary'] == 5  # korundu
    # level_select yine de yeni default'a alinir.
    assert gp['level_select'] == {'primary': 2, 'secondary': -1}


def test_v2_to_v3_migration_is_idempotent():
    from settings_manager import SettingsManager

    sm = SettingsManager.__new__(SettingsManager)
    once = sm._merge_controls({'gamepad': _v3_default_gamepad_block()})
    twice = sm._merge_controls({'gamepad': once['gamepad']})
    assert twice['gamepad'] == once['gamepad']
