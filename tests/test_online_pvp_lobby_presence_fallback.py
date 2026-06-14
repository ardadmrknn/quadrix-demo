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


def _make_game(state: str) -> online_pvp_module.OnlinePvPGame:
    game = online_pvp_module.OnlinePvPGame.__new__(online_pvp_module.OnlinePvPGame)
    game.online_state = state
    game._session_established = False
    game._session_ping_timer = 500.0
    game._pending_disconnect_steam_id = 123
    game._disconnect_grace_timer = 2500.0
    game.sound = types.SimpleNamespace(play=Mock())
    game._send_session_ping = Mock(return_value=True)
    game.net = types.SimpleNamespace(
        my_steam_id=10,
        opponent_steam_id=0,
        opponent_name='',
        _opponent_steam_id=0,
        _opponent_name='',
        get_lobby_members=lambda: [10, 42],
        _get_name=lambda steam_id: 'Peer 42' if steam_id == 42 else str(steam_id),
    )
    return game


def test_sync_lobby_presence_promotes_waiting_state_without_member_join_event():
    game = _make_game(online_pvp_module.OnlineState.WAITING)

    ok = game._sync_lobby_presence_from_members()

    assert ok is True
    assert game.online_state == online_pvp_module.OnlineState.READY_CHECK
    assert game.net._opponent_steam_id == 42
    assert game.net._opponent_name == 'Peer 42'
    assert game._pending_disconnect_steam_id == 0
    assert game._disconnect_grace_timer == 0.0
    game._send_session_ping.assert_called_once()
    game.sound.play.assert_called_once_with('click')


def test_sync_lobby_presence_noops_when_no_other_member_exists():
    game = _make_game(online_pvp_module.OnlineState.WAITING)
    game.net.get_lobby_members = lambda: [10]

    ok = game._sync_lobby_presence_from_members()

    assert ok is False
    assert game.online_state == online_pvp_module.OnlineState.WAITING
    game._send_session_ping.assert_not_called()
    game.sound.play.assert_not_called()
