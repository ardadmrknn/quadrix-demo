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


def _make_game_with_mismatch_sender() -> online_pvp_module.OnlinePvPGame:
    game = online_pvp_module.OnlinePvPGame.__new__(online_pvp_module.OnlinePvPGame)
    game.online_state = online_pvp_module.OnlineState.READY_CHECK
    game.my_ready = False
    game.opponent_ready = False
    game._session_established = False
    game._ready_send_pending = False
    game._check_both_ready = Mock()
    game._send_ready_signal = Mock(return_value=True)
    game.net = types.SimpleNamespace(
        my_steam_id=1,
        opponent_steam_id=7,
        _opponent_steam_id=7,
        get_lobby_members=lambda: [1, 42],
        get_messages=lambda: [
            types.SimpleNamespace(sender=42, data={'type': online_pvp_module.MsgType.READY})
        ],
    )
    return game


def test_ready_message_rebinds_opponent_sender_when_lobby_member_matches():
    game = _make_game_with_mismatch_sender()

    game._process_messages()

    assert game.net._opponent_steam_id == 42
    assert game.opponent_ready is True
    game._check_both_ready.assert_called_once()


def test_ready_message_accepts_lobby_fallback_sender_id_when_sender_is_zero():
    game = _make_game_with_mismatch_sender()
    game.net.get_messages = lambda: [
        types.SimpleNamespace(
            sender=0,
            data={
                'type': online_pvp_module.MsgType.READY,
                'sender_id': 42,
            },
        )
    ]

    game._process_messages()

    assert game.net._opponent_steam_id == 42
    assert game.opponent_ready is True
    game._check_both_ready.assert_called_once()
