"""Tests for the gamepad hot-plug runtime path.

These tests cover the previously missing surfaces:
- `JOYDEVICEADDED` / `JOYDEVICEREMOVED` event handling on the GamepadManager
- Auto-pause when the last gamepad disconnects mid-gameplay
- Steam Overlay (treated like focus-loss) → auto-pause already covered by
  `_is_focus_loss_event`; this test re-asserts that the focus-loss code path
  is not regressed by the hotplug additions.

These do NOT stub out `_check_connections` like
`test_gamepad_mouse_emulation.py` does — they exercise `handle_hotplug_event`
on a real GamepadManager instance with mocked pygame primitives.
"""

from __future__ import annotations

import copy
import pathlib
import sys
import types

import pytest


ROOT_DIR = pathlib.Path(__file__).parent
# Use `os.path.join(..., '..', 'src')` instead of `pathlib.Path / 'src'` so
# that this test file shares the EXACT sys.path string form used by
# `test_focus_manager.py` and `test_mystery_card_xp_progression.py`. If the
# string forms diverge, Python's importlib can load `gamepad_manager` twice
# under the same module name with different file path attributes, causing
# `gpm_module._instance = manager` in one copy to be invisible to game.py's
# `from gamepad_manager import ...` resolved to the other copy.
import os as _os
_SRC_DIR_STR = _os.path.join(_os.path.dirname(__file__), '..', 'src')

if _SRC_DIR_STR not in sys.path:
    sys.path.insert(0, _SRC_DIR_STR)

import gamepad_manager as gpm_module  # noqa: E402
from gamepad_manager import GamepadManager, GamepadState, DEFAULT_GAMEPAD_BINDINGS  # noqa: E402

# If another test module imported gamepad_manager via a different sys.path
# entry (creating a duplicate module object), unify the references so that
# test-side `gpm_module._instance = manager` is visible to the function
# `handle_gamepad_hotplug_event` that game.py imports.
_canonical = sys.modules.get('gamepad_manager')
if _canonical is not None and _canonical is not gpm_module:
    gpm_module = _canonical


def _make_manager():
    """Minimal GamepadManager bypassing __init__ side-effects (settings load,
    initial scan). Mirrors the helper in `test_gamepad_mouse_emulation.py`
    but does NOT stub `_check_connections`.
    """
    manager = GamepadManager.__new__(GamepadManager)
    manager.gamepads = {}
    manager.enabled = True
    manager.rumble_multiplier = 1.0
    manager._context = GamepadManager.CONTEXT_GAME
    manager._menu_pointer_active = False
    manager._suppress_pointer_mode = False
    manager._bindings = copy.deepcopy(DEFAULT_GAMEPAD_BINDINGS)
    manager.DEADZONE = 0.35
    manager.DIGITAL_THRESHOLD = 0.6
    manager.TRIGGER_THRESHOLD = 0.5
    return manager


def _added_event(device_index: int):
    return types.SimpleNamespace(
        type=gpm_module.pygame.JOYDEVICEADDED,
        device_index=device_index,
    )


def _removed_event(instance_id: int):
    return types.SimpleNamespace(
        type=gpm_module.pygame.JOYDEVICEREMOVED,
        instance_id=instance_id,
    )


def _fake_gamepad_state(instance_id: int = 7, name: str = 'Xbox Wireless'):
    """Lightweight GamepadState that satisfies the disconnect path."""
    fake_js = types.SimpleNamespace(
        get_init=lambda: True,
        get_name=lambda: name,
        quit=lambda: None,
    )
    return GamepadState(
        joystick=fake_js,
        controller=None,
        gamepad_type='xbox',
        name=name,
        guid='',
        instance_id=instance_id,
    )


def _sync_singleton_across_module_copies(manager):
    """pytest occasionally loads `gamepad_manager` twice when test files use
    different sys.path string forms for `src/` (e.g. `tests/../src` vs an
    absolute resolved path). When that happens, `gpm_module._instance = manager`
    only affects ONE of the module copies, while game.py's
    `from gamepad_manager import handle_gamepad_hotplug_event` may bind to the
    other copy. Force every loaded `gamepad_manager` module to point at the
    same singleton so the integration test reliably reaches our manager.
    """
    # Trigger the import paths that game.handle_input uses so any lazy module
    # copies are materialised BEFORE we sync. Otherwise the third copy may be
    # created later and miss the singleton update.
    try:
        import importlib
        importlib.import_module('gamepad_manager')
    except Exception:
        pass
    # Also touch the from-import that game.py performs at runtime.
    try:
        from gamepad_manager import handle_gamepad_hotplug_event  # noqa: F401
    except Exception:
        pass

    for _modname, _mod in list(sys.modules.items()):
        if (
            _mod is not None
            and getattr(_mod, '__name__', None) == 'gamepad_manager'
            and hasattr(_mod, '_instance')
        ):
            _mod._instance = manager


def _restore_singleton_across_module_copies(value):
    for _modname, _mod in list(sys.modules.items()):
        if (
            _mod is not None
            and getattr(_mod, '__name__', None) == 'gamepad_manager'
            and hasattr(_mod, '_instance')
        ):
            _mod._instance = value


# ---------------------------------------------------------------------------
# JOYDEVICEADDED
# ---------------------------------------------------------------------------

def test_added_event_registers_new_gamepad(monkeypatch):
    manager = _make_manager()
    register_calls = []

    def fake_register(device_index):
        register_calls.append(device_index)
        manager.gamepads[device_index] = _fake_gamepad_state()
        return True

    monkeypatch.setattr(manager, '_register_gamepad', fake_register)

    result = manager.handle_hotplug_event(_added_event(0))

    assert result == 'connected'
    assert register_calls == [0]
    assert 0 in manager.gamepads


def test_added_event_replaces_stale_slot(monkeypatch):
    """If pygame fires ADDED for an index already in our registry (re-plug
    into same slot), the stale entry must be cleaned up before re-register."""
    manager = _make_manager()
    stale = _fake_gamepad_state(instance_id=10, name='Stale')
    manager.gamepads[0] = stale

    quit_calls = []
    stale.joystick.quit = lambda: quit_calls.append('quit')

    def fake_register(device_index):
        # By the time _register_gamepad runs, the slot must be empty.
        assert device_index not in manager.gamepads, "stale slot not cleared"
        manager.gamepads[device_index] = _fake_gamepad_state(instance_id=11, name='Fresh')
        return True

    monkeypatch.setattr(manager, '_register_gamepad', fake_register)

    result = manager.handle_hotplug_event(_added_event(0))

    assert result == 'connected'
    assert quit_calls == ['quit']
    assert manager.gamepads[0].name == 'Fresh'


def test_added_event_without_device_index_falls_back_to_full_scan(monkeypatch):
    manager = _make_manager()
    scan_calls = []

    def fake_check():
        scan_calls.append(True)
        manager.gamepads[0] = _fake_gamepad_state()

    monkeypatch.setattr(manager, '_check_connections', fake_check)

    event = types.SimpleNamespace(type=gpm_module.pygame.JOYDEVICEADDED)
    result = manager.handle_hotplug_event(event)

    assert scan_calls == [True]
    assert result == 'connected'


# ---------------------------------------------------------------------------
# JOYDEVICEREMOVED
# ---------------------------------------------------------------------------

def test_removed_event_removes_matching_instance_id():
    manager = _make_manager()
    manager.gamepads[0] = _fake_gamepad_state(instance_id=42, name='Xbox A')
    manager.gamepads[1] = _fake_gamepad_state(instance_id=43, name='Xbox B')

    result = manager.handle_hotplug_event(_removed_event(instance_id=42))

    assert result == 'disconnected'
    assert 0 not in manager.gamepads
    assert 1 in manager.gamepads, 'unrelated gamepad must remain'


def test_removed_event_resets_pointer_mode():
    manager = _make_manager()
    manager.gamepads[0] = _fake_gamepad_state(instance_id=42)
    manager._menu_pointer_active = True

    manager.handle_hotplug_event(_removed_event(instance_id=42))

    assert manager._menu_pointer_active is False, (
        'stale pointer-mode state must be cleared on disconnect'
    )


def test_removed_event_unknown_instance_id_is_no_op():
    manager = _make_manager()
    manager.gamepads[0] = _fake_gamepad_state(instance_id=42)

    result = manager.handle_hotplug_event(_removed_event(instance_id=999))

    # Unknown instance: nothing matched; no removal happened.
    assert result is None
    assert 0 in manager.gamepads


def test_unrelated_event_returns_none():
    manager = _make_manager()
    event = types.SimpleNamespace(type=gpm_module.pygame.KEYDOWN, key=0)

    assert manager.handle_hotplug_event(event) is None


# ---------------------------------------------------------------------------
# Module-level helpers (used by Game classes)
# ---------------------------------------------------------------------------

def test_module_level_handle_hotplug_event_uses_singleton(monkeypatch):
    manager = _make_manager()
    monkeypatch.setattr(gpm_module, '_instance', manager)

    register_calls = []
    monkeypatch.setattr(
        manager,
        '_register_gamepad',
        lambda idx: register_calls.append(idx) or True,
    )

    result = gpm_module.handle_gamepad_hotplug_event(_added_event(0))

    assert result == 'connected'
    assert register_calls == [0]


def test_module_level_helper_returns_none_when_no_singleton(monkeypatch):
    monkeypatch.setattr(gpm_module, '_instance', None)
    result = gpm_module.handle_gamepad_hotplug_event(_added_event(0))
    assert result is None
    # Cleanup: ensure that if a real GamepadManager was lazily created earlier
    # in this test session, we do not leave a stale instance behind. The
    # monkeypatch context will restore the original `_instance` when the test
    # exits, so this assert is only for documentation.


def test_is_gamepad_disconnect_event():
    assert gpm_module.is_gamepad_disconnect_event(_removed_event(1)) is True
    assert gpm_module.is_gamepad_disconnect_event(_added_event(1)) is False
    assert (
        gpm_module.is_gamepad_disconnect_event(
            types.SimpleNamespace(type=gpm_module.pygame.KEYDOWN)
        )
        is False
    )


# ---------------------------------------------------------------------------
# Game class auto-pause integration: gamepad disconnect during gameplay
# ---------------------------------------------------------------------------

import game as game_module


def _make_game_instance():
    game = game_module.Game.__new__(game_module.Game)
    game.game_over = False
    game.paused = False
    game.show_exit_prompt = False
    game.level_complete = False
    game.level_failed = False
    game.card_selection_active = False
    game._piece_selection_active = False
    game._card_workshop_active = False
    game._sniper_overlay_active = False
    game.pause_menu_selected = 0
    game.control_bindings = {'pause': game_module.pygame.K_p}
    game.alt_control_bindings = {}
    game._get_fullscreen_toggle_key = lambda: game_module.pygame.K_F12
    game._handle_pause_menu_input = lambda event: None
    game.can_restart = lambda: False
    game.restart = lambda: None
    game.exit_yes_rect = None
    game.exit_no_rect = None
    game.sound = None
    return game


def test_game_pauses_on_gamepad_disconnect_event(monkeypatch):
    """Player pulls the controller cable mid-game → auto-pause must fire."""
    game = _make_game_instance()
    game.pause_menu_selected = 5

    # A real GamepadManager singleton with one gamepad to remove.
    manager = _make_manager()
    manager.gamepads[0] = _fake_gamepad_state(instance_id=42)

    # Sync the singleton across every loaded copy of `gamepad_manager` so the
    # `from gamepad_manager import handle_gamepad_hotplug_event` resolution
    # inside `game.handle_input` lands on this manager regardless of which
    # path string Python used to load the module first.
    original_instance = gpm_module._instance
    _sync_singleton_across_module_copies(manager)
    try:
        event = _removed_event(instance_id=42)
        original_get = game_module.pygame.event.get
        game_module.pygame.event.get = lambda: [event]
        try:
            game.handle_input()
        finally:
            game_module.pygame.event.get = original_get

        assert game.paused is True, (
            f'paused stayed False; manager state after handle_input = '
            f'{list(manager.gamepads.keys())}'
        )
        assert game.pause_menu_selected == 0
    finally:
        _restore_singleton_across_module_copies(original_instance)


def test_game_does_not_pause_on_gamepad_connect_event(monkeypatch):
    """Player plugs in a NEW controller mid-game → state updates, no pause."""
    game = _make_game_instance()
    assert game.paused is False

    manager = _make_manager()
    monkeypatch.setattr(
        manager,
        '_register_gamepad',
        lambda idx: manager.gamepads.setdefault(idx, _fake_gamepad_state()) or True,
    )

    original_instance = gpm_module._instance
    _sync_singleton_across_module_copies(manager)
    try:
        original_get = game_module.pygame.event.get
        game_module.pygame.event.get = lambda: [_added_event(0)]
        try:
            game.handle_input()
        finally:
            game_module.pygame.event.get = original_get

        assert game.paused is False, 'connect must not auto-pause'
    finally:
        _restore_singleton_across_module_copies(original_instance)


def test_game_does_not_double_pause_on_disconnect_when_already_paused(monkeypatch):
    """Already paused: disconnect event must NOT alter state."""
    game = _make_game_instance()
    game.paused = True
    game.pause_menu_selected = 3

    manager = _make_manager()
    manager.gamepads[0] = _fake_gamepad_state(instance_id=42)

    original_instance = gpm_module._instance
    _sync_singleton_across_module_copies(manager)
    try:
        original_get = game_module.pygame.event.get
        game_module.pygame.event.get = lambda: [_removed_event(instance_id=42)]
        try:
            game.handle_input()
        finally:
            game_module.pygame.event.get = original_get

        assert game.paused is True
        # `_pause_for_focus_loss` early-returns when already paused; selection unchanged.
        assert game.pause_menu_selected == 3
    finally:
        _restore_singleton_across_module_copies(original_instance)


def test_game_focus_loss_still_pauses_after_hotplug_addition(monkeypatch):
    """Steam Overlay = WINDOWFOCUSLOST. Verify the new hot-plug branch did not
    swallow the existing focus-loss code path."""
    game = _make_game_instance()
    game.pause_menu_selected = 4

    focus_event = types.SimpleNamespace(
        type=game_module.pygame.ACTIVEEVENT,
        gain=0,
        state=(
            getattr(game_module.pygame, 'APPINPUTFOCUS', 0)
            or getattr(game_module.pygame, 'APPACTIVE', 0)
        ),
    )
    monkeypatch.setattr(game_module.pygame.event, 'get', lambda: [focus_event])

    game.handle_input()

    assert game.paused is True
    assert game.pause_menu_selected == 0
