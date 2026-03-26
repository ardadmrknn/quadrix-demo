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


def test_member_disconnected_in_playing_starts_grace_instead_of_immediate_drop():
    game = online_pvp_module.OnlinePvPGame.__new__(online_pvp_module.OnlinePvPGame)
    game.online_state = online_pvp_module.OnlineState.PLAYING
    game._DISCONNECT_GRACE_MS = 5000.0
    game._pending_disconnect_steam_id = 0
    game._disconnect_grace_timer = 0.0
    game._session_established = True
    game._session_ping_timer = 999.0
    game._status_msg = ''
    game._status_timer = 0.0
    game.net = types.SimpleNamespace(opponent_steam_id=42)
    game._send_session_ping = Mock(return_value=True)

    event = types.SimpleNamespace(steam_id=42, data='')
    game._on_member_disconnected(event)

    assert game.online_state == online_pvp_module.OnlineState.PLAYING
    assert game._pending_disconnect_steam_id == 42
    assert game._disconnect_grace_timer == 5000.0
    assert game._session_established is False
    game._send_session_ping.assert_called_once()


def test_incoming_opponent_message_clears_disconnect_grace():
    game = online_pvp_module.OnlinePvPGame.__new__(online_pvp_module.OnlinePvPGame)
    game.online_state = online_pvp_module.OnlineState.PLAYING
    game._session_established = True
    game.my_ready = False
    game.opponent_ready = False
    game._pending_disconnect_steam_id = 42
    game._disconnect_grace_timer = 5000.0
    game._send_ready_signal = Mock(return_value=True)
    game._check_both_ready = Mock()
    game.net = types.SimpleNamespace(
        my_steam_id=1,
        opponent_steam_id=42,
        _opponent_steam_id=42,
        get_lobby_members=lambda: [1, 42],
        get_messages=lambda: [
            types.SimpleNamespace(sender=42, data={'type': 'session_ping'})
        ],
    )

    game._process_messages()

    assert game._pending_disconnect_steam_id == 0
    assert game._disconnect_grace_timer == 0.0


def test_member_left_in_playing_starts_grace_instead_of_immediate_drop():
    game = online_pvp_module.OnlinePvPGame.__new__(online_pvp_module.OnlinePvPGame)
    game.online_state = online_pvp_module.OnlineState.PLAYING
    game._DISCONNECT_GRACE_MS = 5000.0
    game._pending_disconnect_steam_id = 0
    game._disconnect_grace_timer = 0.0
    game._session_established = True
    game._session_ping_timer = 999.0
    game._status_msg = ''
    game._status_timer = 0.0
    game.game_over = False
    game.winner = ''
    game.opponent_piece_data = {'x': 1}
    game._opponent_piece_seq = 10
    game.net = types.SimpleNamespace(opponent_steam_id=42)
    game._send_session_ping = Mock(return_value=True)

    event = types.SimpleNamespace(steam_id=42, data='')
    game._on_member_left(event)

    assert game.online_state == online_pvp_module.OnlineState.PLAYING
    assert game.game_over is False
    assert game.winner == ''
    assert game._pending_disconnect_steam_id == 42
    assert game._disconnect_grace_timer == 5000.0
    assert game._session_established is False
    game._send_session_ping.assert_called_once()


def test_member_left_uses_event_sender_when_opponent_already_cleared():
    game = online_pvp_module.OnlinePvPGame.__new__(online_pvp_module.OnlinePvPGame)
    game.online_state = online_pvp_module.OnlineState.PLAYING
    game._DISCONNECT_GRACE_MS = 5000.0
    game._pending_disconnect_steam_id = 0
    game._disconnect_grace_timer = 0.0
    game._session_established = True
    game._session_ping_timer = 999.0
    game._status_msg = ''
    game._status_timer = 0.0
    game.game_over = False
    game.winner = ''
    game.opponent_piece_data = {'x': 1}
    game._opponent_piece_seq = 10
    game.net = types.SimpleNamespace(opponent_steam_id=0, my_steam_id=1)
    game._send_session_ping = Mock(return_value=True)

    event = types.SimpleNamespace(steam_id=42, data='2')
    game._on_member_left(event)

    assert game.online_state == online_pvp_module.OnlineState.PLAYING
    assert game._pending_disconnect_steam_id == 42
    assert game._disconnect_grace_timer == 5000.0
    game._send_session_ping.assert_called_once()


def test_member_disconnected_uses_event_sender_when_opponent_already_cleared():
    game = online_pvp_module.OnlinePvPGame.__new__(online_pvp_module.OnlinePvPGame)
    game.online_state = online_pvp_module.OnlineState.PLAYING
    game._DISCONNECT_GRACE_MS = 5000.0
    game._pending_disconnect_steam_id = 0
    game._disconnect_grace_timer = 0.0
    game._session_established = True
    game._session_ping_timer = 999.0
    game._status_msg = ''
    game._status_timer = 0.0
    game.net = types.SimpleNamespace(opponent_steam_id=0, my_steam_id=1)
    game._send_session_ping = Mock(return_value=True)

    event = types.SimpleNamespace(steam_id=42, data='18')
    game._on_member_disconnected(event)

    assert game.online_state == online_pvp_module.OnlineState.PLAYING
    assert game._pending_disconnect_steam_id == 42
    assert game._disconnect_grace_timer == 5000.0
    game._send_session_ping.assert_called_once()
