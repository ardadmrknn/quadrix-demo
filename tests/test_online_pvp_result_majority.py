from __future__ import annotations

import types
from unittest.mock import MagicMock, patch

import online_pvp_game as online_pvp_module
import steam_networking as steam_networking_module


def _make_game(*, my_score: int, my_lines: int, opponent_score: int, opponent_lines: int):
    game = online_pvp_module.OnlinePvPGame.__new__(online_pvp_module.OnlinePvPGame)
    game.online_state = online_pvp_module.OnlineState.PLAYING
    game.game_over = False
    game.winner = ''
    game.my_eliminated = False
    game.opponent_eliminated = False
    game._my_final_board_filled = False
    game._opponent_final_board_filled = False
    game._opponent_final_score = 0
    game._opponent_final_lines = 0
    game._match_result_recorded = False
    game.opponent_score = opponent_score
    game.opponent_lines = opponent_lines
    game.opponent_level = 1
    game.opponent_piece_data = None
    game._pending_disconnect_steam_id = 0
    game._disconnect_grace_timer = 0.0
    game._session_established = True
    game.my_ready = False
    game.opponent_ready = False
    game.sound = types.SimpleNamespace(play=MagicMock())
    game.net = types.SimpleNamespace(
        send_game_over=MagicMock(),
        get_messages=lambda: [],
        opponent_steam_id=42,
        my_steam_id=1,
        opponent_name='Bort',
        _get_name=lambda _steam_id: 'Madelyn',
        get_lobby_members=lambda: [1, 42],
    )
    game.achievement_manager = None
    game._check_both_ready = MagicMock()
    game._send_ready_signal = MagicMock(return_value=True)
    game._freeze_active_gameplay_input = MagicMock()
    game.my_board = types.SimpleNamespace(score=my_score, lines_cleared=my_lines)
    return game


def test_majority_rule_example_gives_win_to_non_filled_opponent():
    game = _make_game(my_score=55000, my_lines=55, opponent_score=56000, opponent_lines=60)

    game._mark_local_eliminated()

    assert game.game_over is True
    assert game.winner == 'opponent'
    game.net.send_game_over.assert_called_once_with(55000, 55, board_filled=True)


def test_majority_rule_allows_filled_player_to_win_with_score_and_lines_lead():
    game = _make_game(my_score=56000, my_lines=60, opponent_score=55000, opponent_lines=55)

    game._mark_local_eliminated()

    assert game.game_over is True
    assert game.winner == 'me'


def test_split_metrics_with_both_filled_is_draw():
    game = _make_game(my_score=56000, my_lines=55, opponent_score=55000, opponent_lines=60)
    game.my_eliminated = True
    game.opponent_eliminated = True
    game._my_final_board_filled = True
    game._opponent_final_board_filled = True
    game._opponent_final_score = 55000
    game._opponent_final_lines = 60

    game._finalize_elimination_result()

    assert game.game_over is True
    assert game.winner == 'draw'


def test_game_over_message_uses_board_filled_in_majority_rule():
    game = _make_game(my_score=55000, my_lines=55, opponent_score=0, opponent_lines=0)
    game.net.get_messages = lambda: [
        types.SimpleNamespace(
            sender=42,
            data={
                'type': steam_networking_module.MsgType.GAME_OVER,
                'score': 56000,
                'lines': 60,
                'board_filled': 1,
            },
        )
    ]

    game._process_messages()

    assert game.game_over is True
    assert game.winner == 'opponent'
    assert game._opponent_final_board_filled is True
    assert game._opponent_final_score == 56000
    assert game._opponent_final_lines == 60


def test_eliminated_without_final_stats_uses_latest_live_metrics():
    game = _make_game(my_score=100, my_lines=10, opponent_score=200, opponent_lines=20)

    game._mark_opponent_eliminated()

    assert game.game_over is True
    assert game.winner == 'opponent'


def test_local_elimination_after_remote_result_still_sends_final_stats():
    game = _make_game(my_score=55000, my_lines=55, opponent_score=56000, opponent_lines=60)

    game._mark_opponent_eliminated(score=56000, lines=60, board_filled=True)
    game.net.send_game_over.reset_mock()

    game._mark_local_eliminated()

    assert game.winner == 'opponent'
    game.net.send_game_over.assert_called_once_with(55000, 55, board_filled=True)


def test_result_reason_mentions_board_fill_and_line_gap_when_higher_score_loses():
    game = _make_game(my_score=55000, my_lines=55, opponent_score=56000, opponent_lines=60)
    game.net.opponent_name = 'Borf'

    game._mark_local_eliminated()
    reason = game._build_majority_result_reason_text()

    assert 'Borf' in reason
    assert 'Madelyn' in reason
    assert 'oyun alan' in reason
    assert 'satır' in reason


def test_result_reason_mentions_open_board_when_filled_player_still_wins():
    game = _make_game(my_score=56000, my_lines=60, opponent_score=55000, opponent_lines=55)
    game.net.opponent_name = 'Borf'

    game._mark_local_eliminated()
    reason = game._build_majority_result_reason_text()

    assert 'Borf' in reason
    assert 'oyun alan' in reason or 'tahta' in reason or 'alan kontrol' in reason
    assert 'puan' in reason or 'skor' in reason
    assert 'satır' in reason


def test_result_reason_uses_english_fallback_for_non_turkish_language():
    game = _make_game(my_score=55000, my_lines=55, opponent_score=56000, opponent_lines=60)
    game.net.opponent_name = 'Borf'

    with patch.object(online_pvp_module, 'get_language', return_value='en'):
        game._mark_local_eliminated()
        reason = game._build_majority_result_reason_text()

    assert 'Borf' in reason
    assert 'Madelyn' in reason
    assert 'higher score' in reason or 'decision score' in reason
    assert 'lines' in reason
    assert 'board' in reason or 'topped out' in reason


def test_send_game_over_payload_includes_board_filled_flag():
    net = steam_networking_module.SteamNetworking.__new__(steam_networking_module.SteamNetworking)
    net.send = MagicMock(return_value=True)

    net.send_game_over(1234, 12, board_filled=False)

    payload = net.send.call_args.args[0]
    assert payload['type'] == steam_networking_module.MsgType.GAME_OVER
    assert payload['score'] == 1234
    assert payload['lines'] == 12
    assert payload['board_filled'] == 0