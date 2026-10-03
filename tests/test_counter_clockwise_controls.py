from __future__ import annotations

import copy
import pathlib
import sys
import types

import pygame

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import game as game_module  # noqa: E402
import game_modes  # noqa: E402
import localization  # noqa: E402
from board import Board  # noqa: E402
from gamepad_manager import ACTION_TO_KEY, DEFAULT_GAMEPAD_BINDINGS, GamepadManager, GamepadState  # noqa: E402
from menu import get_control_actions  # noqa: E402
from pieces import create_piece_by_name  # noqa: E402
from settings_manager import CURRENT_GAMEPAD_LAYOUT_VERSION, DEFAULT_CONTROLS, SettingsManager  # noqa: E402
from settings_screen_tabbed import _build_tab_content  # noqa: E402


class _Settings:
    def __init__(self, controls=None, dcd=17):
        self.controls = controls or copy.deepcopy(DEFAULT_CONTROLS)
        self.dcd = dcd

    def get_controls(self):
        return self.controls

    def get(self, key, default=None):
        if key == 'dcd':
            return self.dcd
        if key == 'controls':
            return self.controls
        return default


class _Sound:
    def __init__(self):
        self.calls = []

    def play(self, name):
        self.calls.append(name)

    def duck_music(self):
        pass

    def unduck_music(self):
        pass


def _keydown(key, **metadata):
    return types.SimpleNamespace(type=pygame.KEYDOWN, key=key, mod=0, **metadata)


def _make_game(controls=None):
    game = game_module.Game.__new__(game_module.Game)
    game.game_over = False
    game.paused = False
    game.show_exit_prompt = False
    game._pause_settings_active = False
    game.settings_manager = _Settings(controls)
    game.control_bindings = game._resolve_single_player_controls()
    game.alt_control_bindings = game._resolve_single_player_secondary_controls(game.control_bindings)
    game.current_piece = create_piece_by_name('T', x=3, y=5)
    game.board = Board(width=10, height=20)
    game.sound = _Sound()
    game.last_move_was_rotate = False
    game.last_rotate_kick_index = -1
    game.dcd_timer = 0.0
    game.lock_reset_count = 0
    game.lock_timer = 0.0
    game._update_grounded_after_action = lambda: None
    return game


def test_settings_merge_adds_ccw_without_overwriting_existing_bindings():
    manager = SettingsManager.__new__(SettingsManager)
    merged = manager._merge_controls({
        'single_player': {'rotate': {'primary': 'x', 'secondary': 'y'}},
        'pvp': {'player1': {'rotate': 'r'}},
        'gamepad': {
            'gamepad_layout_version': CURRENT_GAMEPAD_LAYOUT_VERSION,
            'rotate': {'primary': 7, 'secondary': -1},
        },
    })

    assert merged['single_player']['rotate'] == {'primary': 'x', 'secondary': 'y'}
    assert merged['single_player']['rotate_ccw'] == {'primary': 'z', 'secondary': 'q'}
    assert merged['pvp']['player1']['rotate'] == 'r'
    assert merged['pvp']['player1']['rotate_ccw'] == 'q'
    assert merged['gamepad']['rotate'] == {'primary': 7, 'secondary': -1}
    assert merged['gamepad']['rotate_ccw'] == {'primary': -1, 'secondary': -1}


def test_settings_defaults_and_visible_action_order_include_ccw():
    assert DEFAULT_CONTROLS['single_player']['rotate_ccw'] == {'primary': 'z', 'secondary': 'q'}
    assert DEFAULT_CONTROLS['pvp']['player1']['rotate_ccw'] == 'q'
    assert DEFAULT_CONTROLS['pvp']['player2']['rotate_ccw'] == 'right ctrl'
    assert DEFAULT_CONTROLS['gamepad']['rotate_ccw'] == {'primary': -1, 'secondary': -1}

    actions = [action for action, _label in get_control_actions()['single_player']]
    assert actions == [
        'move_left', 'move_right', 'soft_drop', 'hard_drop', 'rotate',
        'rotate_ccw', 'rotate_180', 'hold', 'pause',
    ]
    assert 'rotate_ccw' in [action for action, _ in get_control_actions()['pvp.player1']]
    assert 'rotate_ccw' in [action for action, _ in get_control_actions()['pvp.player2']]


def test_tabbed_settings_contains_keyboard_and_gamepad_ccw_rows():
    items = _build_tab_content('controls', _Settings())
    rows = {(item.get('section'), item.get('action_key')) for item in items if item.get('type') == 'keybind'}
    assert ('single_player', 'rotate_ccw') in rows
    assert ('pvp.player1', 'rotate_ccw') in rows
    assert ('pvp.player2', 'rotate_ccw') in rows
    assert ('gamepad.ingame', 'rotate_ccw') in rows


def test_all_locales_have_nonempty_ccw_labels():
    for key in ('ctrl_rotate_ccw', 'gp_rotate_ccw', 'guide_action_rotate_ccw'):
        values = localization.TRANSLATIONS[key]
        assert set(values) >= {'tr', 'en', 'de', 'fr', 'es', 'it', 'pt', 'ru', 'ja', 'zh', 'ko'}
        assert all(str(values[lang]).strip() for lang in ('tr', 'en', 'de', 'fr', 'es', 'it', 'pt', 'ru', 'ja', 'zh', 'ko'))


def test_primary_and_secondary_ccw_bindings_rotate_once(monkeypatch):
    for key in (pygame.K_z, pygame.K_q):
        game = _make_game()
        monkeypatch.setattr(game_module.pygame.event, 'get', lambda key=key: [_keydown(key)])
        game.handle_input()
        assert game.current_piece.rotation_state == 3
        assert game.sound.calls == ['rotate']


def test_cleared_secondary_binding_stays_unbound():
    controls = copy.deepcopy(DEFAULT_CONTROLS)
    controls['single_player']['rotate_ccw'] = {'primary': 'f', 'secondary': ''}
    game = _make_game(controls)

    assert game.control_bindings['rotate_ccw'] == pygame.K_f
    assert game.alt_control_bindings['rotate_ccw'] is None


def test_custom_rebind_is_resolved_at_runtime(monkeypatch):
    controls = copy.deepcopy(DEFAULT_CONTROLS)
    controls['single_player']['rotate_ccw'] = {'primary': 'f', 'secondary': 'g'}
    game = _make_game(controls)

    monkeypatch.setattr(game_module.pygame.event, 'get', lambda: [_keydown(pygame.K_g)])
    game.handle_input()

    assert game.current_piece.rotation_state == 3


def test_gamepad_action_metadata_survives_keyboard_rebind(monkeypatch):
    controls = copy.deepcopy(DEFAULT_CONTROLS)
    controls['single_player']['rotate_ccw'] = {'primary': 'f', 'secondary': ''}
    game = _make_game(controls)

    monkeypatch.setattr(
        game_module.pygame.event,
        'get',
        lambda: [_keydown(pygame.K_z, from_gamepad=True, action='rotate_ccw', device_index=0)],
    )
    game.handle_input()

    assert game.current_piece.rotation_state == 3
    assert game.sound.calls == ['rotate']


def test_failed_ccw_has_no_sound_or_rotation_metadata(monkeypatch):
    game = _make_game()
    original = (game.current_piece.x, game.current_piece.y, game.current_piece.rotation_state, copy.deepcopy(game.current_piece.shape))
    game.current_piece.try_rotate_srs = lambda *_args, **_kwargs: False

    monkeypatch.setattr(game_module.pygame.event, 'get', lambda: [_keydown(pygame.K_z)])
    game.handle_input()

    assert (game.current_piece.x, game.current_piece.y, game.current_piece.rotation_state, game.current_piece.shape) == original
    assert game.sound.calls == []
    assert game.last_move_was_rotate is False
    assert game.last_rotate_kick_index == -1


def test_successful_ccw_sets_rotation_metadata(monkeypatch):
    game = _make_game()
    monkeypatch.setattr(game_module.pygame.event, 'get', lambda: [_keydown(pygame.K_z)])

    game.handle_input()

    assert game.last_move_was_rotate is True
    assert game.last_rotate_kick_index == game.current_piece.last_kick_index


def test_paused_game_does_not_apply_ccw(monkeypatch):
    game = _make_game()
    game.paused = True
    game._handle_pause_menu_input = lambda _event: None
    monkeypatch.setattr(game_module.pygame.event, 'get', lambda: [_keydown(pygame.K_z)])

    game.handle_input()

    assert game.current_piece.rotation_state == 0
    assert game.sound.calls == []


def test_gamepad_canonical_binding_and_event_metadata():
    assert DEFAULT_GAMEPAD_BINDINGS['rotate_ccw'] == {'button': None}
    assert ACTION_TO_KEY['rotate_ccw'] == pygame.K_z
    # Demo layout v3 (2026-10-04): restart=Y(3)/level_select=X(2) eklendi —
    # CCW bağlamalarını değiştirmez (rotate_ccw hâlâ atanmamış varsayılan).
    assert CURRENT_GAMEPAD_LAYOUT_VERSION in (2, 3, 5)

    manager = GamepadManager.__new__(GamepadManager)
    event = manager._make_key_event(pygame.K_z, pygame.KEYDOWN, gp_device_index=4, action='rotate_ccw')
    assert event.from_gamepad is True
    assert event.action == 'rotate_ccw'
    assert event.device_index == 4


def test_custom_gamepad_button_emits_single_ccw_keydown_without_cw():
    manager = GamepadManager.__new__(GamepadManager)
    manager._context = GamepadManager.CONTEXT_GAME
    manager._bindings = copy.deepcopy(DEFAULT_GAMEPAD_BINDINGS)
    manager._bindings['rotate_ccw'] = {'button': 4}
    manager._bindings['rotate'] = {'button': 11}
    manager._bindings['rotate_alt'] = {'button': None}
    gamepad = GamepadState(device_index=2, buttons={4: True}, prev_buttons={4: False})

    events = manager._generate_button_events(gamepad)
    down_events = [event for event in events if event.type == pygame.KEYDOWN]

    assert len(down_events) == 1
    assert down_events[0].key == pygame.K_z
    assert down_events[0].action == 'rotate_ccw'
