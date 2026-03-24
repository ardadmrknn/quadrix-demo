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


def _make_game(send_ready_ok: bool) -> online_pvp_module.OnlinePvPGame:
    game = online_pvp_module.OnlinePvPGame.__new__(online_pvp_module.OnlinePvPGame)
    game._net_initialized = True
    game._session_established = False
    game._ready_send_pending = False
    game.net = types.SimpleNamespace(
        opponent_steam_id=0,
        send_ready=Mock(return_value=send_ready_ok),
        send=Mock(return_value=True),
    )
    return game


def _make_game_with_opponent(send_ready_ok: bool, ping_ok: bool) -> online_pvp_module.OnlinePvPGame:
    game = online_pvp_module.OnlinePvPGame.__new__(online_pvp_module.OnlinePvPGame)
    game._net_initialized = True
    game._session_established = False
    game._ready_send_pending = False
    game.net = types.SimpleNamespace(
        opponent_steam_id=123,
        send_ready=Mock(return_value=send_ready_ok),
        send=Mock(return_value=ping_ok),
    )
    return game


def test_ready_signal_uses_lobby_fallback_when_opponent_id_unknown():
    game = _make_game(send_ready_ok=True)

    ok = game._send_ready_signal(reason='unit_test')

    assert ok is True
    game.net.send_ready.assert_called_once()
    assert game._ready_send_pending is False


def test_ready_signal_fallback_keeps_pending_on_send_failure():
    game = _make_game(send_ready_ok=False)

    ok = game._send_ready_signal(reason='unit_test')

    assert ok is False
    game.net.send_ready.assert_called_once()
    assert game._ready_send_pending is True


def test_ready_signal_with_opponent_and_no_session_still_sends_ready():
    game = _make_game_with_opponent(send_ready_ok=True, ping_ok=False)

    ok = game._send_ready_signal(reason='unit_test')

    assert ok is True
    game.net.send.assert_called_once()  # session_ping denemesi
    game.net.send_ready.assert_called_once()
    assert game._ready_send_pending is False


def test_ready_signal_with_opponent_and_no_session_pending_on_double_failure():
    game = _make_game_with_opponent(send_ready_ok=False, ping_ok=False)

    ok = game._send_ready_signal(reason='unit_test')

    assert ok is False
    game.net.send.assert_called_once()
    game.net.send_ready.assert_called_once()
    assert game._ready_send_pending is True
