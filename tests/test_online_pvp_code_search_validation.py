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


def _make_game() -> online_pvp_module.OnlinePvPGame:
    game = online_pvp_module.OnlinePvPGame.__new__(online_pvp_module.OnlinePvPGame)
    game._lobby_list = []
    game._pending_lobby_list = []
    game._lobby_list_fetching = False
    game._lobby_list_scroll = 0
    game._searching_by_code = False
    game._search_code = ''
    game._join_code_input = ''
    game._join_code_active = True
    game._join_code_error = ''
    game._join_target_lobby_id = 0
    game._status_msg = ''
    game._status_timer = 0.0
    game._code_search_retry_count = 0
    game._code_search_retry_timer = 0.0
    game._code_search_retry_code = ''
    game._init_networking = Mock(return_value=True)
    game.net = types.SimpleNamespace(
        join_lobby=Mock(),
        search_lobby_by_code=Mock(),
        get_lobby_data_for=lambda _lobby_id, _key: '',
    )
    return game


def test_try_join_by_code_joins_selected_private_lobby_when_live_code_matches():
    game = _make_game()
    game._join_code_input = '123456'
    game._join_target_lobby_id = 77

    def _get_lobby_data_for(lobby_id, key):
        assert lobby_id == 77
        mapping = {
            'lobby_code': '123456',
            'visibility': 'private',
            'requires_code': '1',
            'metadata_ready': '1',
        }
        return mapping.get(key, '')

    game.net.get_lobby_data_for = _get_lobby_data_for

    game._try_join_by_code()

    game.net.join_lobby.assert_called_once_with(77)
    game.net.search_lobby_by_code.assert_not_called()
    assert game._join_target_lobby_id == 0


def test_try_join_by_code_rejects_wrong_code_for_selected_private_lobby():
    game = _make_game()
    game._join_code_input = '999999'
    game._join_target_lobby_id = 77

    def _get_lobby_data_for(lobby_id, key):
        assert lobby_id == 77
        mapping = {
            'lobby_code': '123456',
            'visibility': 'private',
            'requires_code': '1',
            'metadata_ready': '1',
        }
        return mapping.get(key, '')

    game.net.get_lobby_data_for = _get_lobby_data_for

    game._try_join_by_code()

    game.net.join_lobby.assert_not_called()
    game.net.search_lobby_by_code.assert_not_called()
    assert game._join_code_error
    assert game._join_target_lobby_id == 77


def test_on_lobby_list_complete_does_not_join_ambiguous_code_collision():
    game = _make_game()
    game._searching_by_code = True
    game._search_code = '123456'
    game._pending_lobby_list = [
        {'id': 11, 'code': '123456', 'visibility': 'private', 'requires_code': True, 'metadata_ready': True},
        {'id': 22, 'code': '123456', 'visibility': 'private', 'requires_code': True, 'metadata_ready': True},
    ]

    game._on_lobby_list_complete(online_pvp_module.NetEvent('lobby_list_complete', 0, ''))

    game.net.join_lobby.assert_not_called()
    assert 'birden fazla' in game._status_msg.lower()