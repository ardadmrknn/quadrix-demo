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


def _make_host_ready_game(send_ok: bool) -> online_pvp_module.OnlinePvPGame:
    game = online_pvp_module.OnlinePvPGame.__new__(online_pvp_module.OnlinePvPGame)
    game.my_ready = True
    game.opponent_ready = True
    game.game_seed = 0
    game.piece_sequence = []
    game._GAME_START_RETRY_INTERVAL_MS = 1000.0
    game._game_start_retry_timer = 0.0
    game._game_start_pending_payload = None
    game.net = types.SimpleNamespace(
        is_host=True,
        send_game_start=Mock(return_value=send_ok),
    )
    game._generate_pieces = Mock(side_effect=lambda seed, count: setattr(game, 'piece_sequence', list(range(200))))
    game._start_countdown = Mock()
    return game


def test_check_both_ready_host_send_failure_sets_retry_state():
    game = _make_host_ready_game(send_ok=False)

    game._check_both_ready()

    game.net.send_game_start.assert_called_once()
    assert game._game_start_pending_payload is not None
    assert game._game_start_retry_timer == game._GAME_START_RETRY_INTERVAL_MS
    game._start_countdown.assert_not_called()


def test_check_both_ready_host_retry_success_clears_pending_and_starts_countdown():
    game = _make_host_ready_game(send_ok=False)

    game._check_both_ready()
    game.net.send_game_start.return_value = True
    game._game_start_retry_timer = 0.0

    game._check_both_ready()

    assert game.net.send_game_start.call_count == 2
    assert game._game_start_pending_payload is None
    assert game._game_start_retry_timer == 0.0
    game._start_countdown.assert_called_once()
