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
from steam_networking import generate_lobby_code


def _make_game() -> online_pvp_module.OnlinePvPGame:
    game = online_pvp_module.OnlinePvPGame.__new__(online_pvp_module.OnlinePvPGame)
    game._lobby_list = []
    game._pending_lobby_list = []
    game._deferred_lobby_entries = {}
    game._lobby_list_fetching = False
    game._lobby_list_scroll = 0
    game._lobby_list_filter = 'all'
    game._searching_by_code = False
    game._search_code = ''
    game._join_code_input = ''
    game._join_code_active = True
    game._join_code_error = ''
    game._join_target_lobby_id = 0
    game._authorized_private_join_lobby_id = 0
    game._authorized_private_join_code = ''
    game._invite_authorized_lobby_id = 0
    game._status_msg = ''
    game._status_timer = 0.0
    game._code_search_retry_count = 0
    game._code_search_retry_timer = 0.0
    game._code_search_retry_code = ''
    game._code_search_retry_use_full_scan = False
    game._auto_lobby_refresh_interval = 0.0
    game._init_networking = Mock(return_value=True)
    game.net = types.SimpleNamespace(
        join_lobby=Mock(),
        request_lobby_list=Mock(),
        search_lobby_by_code=Mock(),
        add_lobby_search_filter=Mock(),
        get_lobby_data_for=lambda _lobby_id, _key: '',
    )
    return game


def test_request_lobby_list_uses_worldwide_scope():
    game = _make_game()
    game._lobby_list_filter = 'all'
    game._auto_lobby_refresh_interval = 10000.0

    assert game._request_lobby_list() is True

    game.net.request_lobby_list.assert_called_once_with(worldwide=True)


def test_try_join_by_code_uses_exact_code_search_first():
    game = _make_game()
    game._join_code_input = '123456'

    game._try_join_by_code()

    game.net.search_lobby_by_code.assert_called_once_with('123456')
    game.net.request_lobby_list.assert_not_called()
    assert game._searching_by_code is True
    assert game._search_code == '123456'


def test_code_search_retry_switches_to_worldwide_scan_for_last_attempt():
    game = _make_game()
    game._search_code = '123456'
    game._code_search_retry_count = 1

    game._code_search_fail_or_retry()

    assert game._code_search_retry_count == 2
    assert game._code_search_retry_use_full_scan is True


def test_begin_code_search_can_use_worldwide_fallback_scan():
    game = _make_game()

    game._begin_code_search('123456', fallback_scan=True)

    game.net.request_lobby_list.assert_called_once_with(worldwide=True)
    game.net.search_lobby_by_code.assert_not_called()


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
    assert game._authorized_private_join_lobby_id == 77
    assert game._authorized_private_join_code == '123456'


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


def test_try_join_by_code_accepts_generated_code_when_private_metadata_code_is_missing():
    game = _make_game()
    game._join_target_lobby_id = 77
    game._join_code_input = generate_lobby_code(77)

    def _get_lobby_data_for(lobby_id, key):
        assert lobby_id == 77
        mapping = {
            'visibility': 'private',
            'requires_code': '1',
            'metadata_ready': '0',
        }
        return mapping.get(key, '')

    game.net.get_lobby_data_for = _get_lobby_data_for

    game._try_join_by_code()

    game.net.join_lobby.assert_called_once_with(77)
    game.net.search_lobby_by_code.assert_not_called()
    assert game._join_target_lobby_id == 0
    assert game._authorized_private_join_lobby_id == 77
    assert game._authorized_private_join_code == generate_lobby_code(77)


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


def test_on_lobby_list_complete_matches_generated_private_code_without_metadata_code():
    game = _make_game()
    game._searching_by_code = True
    game._search_code = generate_lobby_code(77)
    game._pending_lobby_list = [
        {'id': 77, 'code': '', 'visibility': 'private', 'requires_code': True, 'metadata_ready': False},
    ]

    def _get_lobby_data_for(lobby_id, key):
        assert lobby_id == 77
        mapping = {
            'visibility': 'private',
            'requires_code': '1',
            'metadata_ready': '0',
        }
        return mapping.get(key, '')

    game.net.get_lobby_data_for = _get_lobby_data_for

    game._on_lobby_list_complete(online_pvp_module.NetEvent('lobby_list_complete', 0, ''))

    game.net.join_lobby.assert_called_once_with(77)
    assert game._authorized_private_join_lobby_id == 77
    assert game._authorized_private_join_code == generate_lobby_code(77)


def test_on_lobby_list_complete_can_match_private_code_from_deferred_lobby_entries():
    game = _make_game()
    game._searching_by_code = True
    game._search_code = '123456'
    game._deferred_lobby_entries = {
        77: {
            'id': 77,
            'name': 'Bekleyen özel lobi',
            'code': '',
            'visibility': 'unknown',
            'requires_code': False,
            'metadata_ready': False,
        }
    }

    def _get_lobby_data_for(lobby_id, key):
        assert lobby_id == 77
        mapping = {
            'visibility': 'private',
            'requires_code': '1',
            'metadata_ready': '1',
            'lobby_code': '123456',
        }
        return mapping.get(key, '')

    game.net.get_lobby_data_for = _get_lobby_data_for

    game._on_lobby_list_complete(online_pvp_module.NetEvent('lobby_list_complete', 0, ''))

    game.net.join_lobby.assert_called_once_with(77)
    assert game._authorized_private_join_lobby_id == 77
    assert game._authorized_private_join_code == '123456'