from __future__ import annotations

import pathlib
import sys
import types
from unittest.mock import Mock


ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / 'src'

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import online_pvp_game as online_pvp_module


def _make_online_game() -> online_pvp_module.OnlinePvPGame:
    game = online_pvp_module.OnlinePvPGame.__new__(online_pvp_module.OnlinePvPGame)
    game.online_state = online_pvp_module.OnlineState.PLAYING
    game.game_over = False
    game.paused = False
    game.opponent_paused = False
    game._join_code_active = False
    game._join_code_input = ''
    game._join_code_error = ''
    game._join_target_lobby_id = 0
    game.soft_dropping = False
    game.das_direction = 0
    game.das_timer = 0
    game.das_active = False
    game.net = types.SimpleNamespace(
        send=Mock(),
        get_messages=lambda: [],
        opponent_steam_id=7,
        leave_lobby=Mock(),
    )
    game._move_horizontal = Mock()
    game._rotate_piece = Mock()
    game._hard_drop = Mock()
    game._do_hold = Mock()
    game._do_invite_friend = Mock()
    game._try_join_by_code = Mock()
    game._return_to_pvp_lobby_menu = Mock()
    game._request_rematch = Mock()
    game._check_both_ready = Mock()
    game.my_board = Mock()
    game.my_piece = Mock()
    return game


def _keydown_event(key: int):
    return types.SimpleNamespace(key=key, mod=0)


def _focus_loss_event():
    return types.SimpleNamespace(
        type=online_pvp_module.pygame.ACTIVEEVENT,
        gain=0,
        state=getattr(online_pvp_module.pygame, 'APPINPUTFOCUS', 0) or getattr(online_pvp_module.pygame, 'APPACTIVE', 0),
    )


def test_online_pvp_opponent_pause_blocks_local_gameplay_input():
    game = _make_online_game()
    game.opponent_paused = True

    game._handle_keydown(_keydown_event(online_pvp_module.pygame.K_LEFT))
    game._handle_keydown(_keydown_event(online_pvp_module.pygame.K_SPACE))

    game._move_horizontal.assert_not_called()
    game._hard_drop.assert_not_called()
    assert game.das_direction == 0
    assert game.soft_dropping is False


def test_online_pvp_local_pause_clears_active_movement_and_notifies_peer():
    game = _make_online_game()
    game.soft_dropping = True
    game.das_direction = -1
    game.das_timer = 87
    game.das_active = True

    game._handle_keydown(_keydown_event(online_pvp_module.pygame.K_ESCAPE))

    assert game.paused is True
    assert game.soft_dropping is False
    assert game.das_direction == 0
    assert game.das_timer == 0
    assert game.das_active is False
    game.net.send.assert_called_once_with(
        {'type': online_pvp_module.MsgType.PAUSE_REQUEST},
        reliable=True,
        channel=online_pvp_module.CHANNEL_CONTROL,
    )


def test_online_pvp_remote_pause_message_freezes_local_active_input():
    game = _make_online_game()
    game.soft_dropping = True
    game.das_direction = 1
    game.das_timer = 42
    game.das_active = True
    game.net.get_messages = lambda: [
        types.SimpleNamespace(
            sender=7,
            data={'type': online_pvp_module.MsgType.PAUSE_REQUEST},
        )
    ]

    game._process_messages()

    assert game.opponent_paused is True
    assert game.soft_dropping is False
    assert game.das_direction == 0
    assert game.das_timer == 0
    assert game.das_active is False


def test_online_pvp_focus_loss_pauses_and_notifies_peer(monkeypatch):
    game = _make_online_game()
    game.gamepad = None
    game.soft_dropping = True
    game.das_direction = -1
    game.das_timer = 12
    game.das_active = True

    monkeypatch.setattr(online_pvp_module.pygame.event, 'get', lambda: [_focus_loss_event()])

    result = game.handle_input()

    assert result is True
    assert game.paused is True
    assert game.soft_dropping is False
    assert game.das_direction == 0
    assert game.das_timer == 0
    assert game.das_active is False
    game.net.send.assert_called_once_with(
        {'type': online_pvp_module.MsgType.PAUSE_REQUEST},
        reliable=True,
        channel=online_pvp_module.CHANNEL_CONTROL,
    )