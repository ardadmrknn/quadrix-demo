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
from steam_networking import NetEvent


def _make_game():
    game = online_pvp_module.OnlinePvPGame.__new__(online_pvp_module.OnlinePvPGame)
    game._pending_lobby_list = []
    return game


def test_lobby_found_does_not_fallback_to_current_lobby_metadata():
    """Metadata tamamen boşsa lobi hazır değil olarak işaretlenmeli."""
    game = _make_game()
    game.net = types.SimpleNamespace(
        get_lobby_data_for=lambda lobby_id, key: '',
        get_lobby_data=lambda key: 'private',
    )

    event = NetEvent(
        'lobby_found',
        steam_id=42,
        data='{"host_name":"mac-host","members":1,"max_members":2}',
    )

    game._on_lobby_found(event)

    assert len(game._pending_lobby_list) == 1
    lobby = game._pending_lobby_list[0]
    assert lobby['visibility'] == 'unknown'
    assert lobby['requires_code'] is False
    assert lobby['metadata_ready'] is False


def test_lobby_found_uses_per_lobby_metadata_for_private_visibility():
    game = _make_game()

    def _get_lobby_data_for(_lobby_id, key):
        mapping = {
            'visibility': 'private',
            'requires_code': '1',
            'host_name': 'mac-host',
            'lobby_code': '123456',
        }
        return mapping.get(key, '')

    game.net = types.SimpleNamespace(
        get_lobby_data_for=_get_lobby_data_for,
        get_lobby_data=lambda key: '',
    )

    event = NetEvent(
        'lobby_found',
        steam_id=43,
        data='{"members":1,"max_members":2}',
    )

    game._on_lobby_found(event)

    assert len(game._pending_lobby_list) == 1
    lobby = game._pending_lobby_list[0]
    assert lobby['visibility'] == 'private'
    assert lobby['requires_code'] is True
    assert lobby['code'] == '123456'
    assert lobby['metadata_ready'] is True


def test_lobby_found_infers_public_when_requires_code_is_false():
    game = _make_game()
    game.net = types.SimpleNamespace(
        get_lobby_data_for=lambda lobby_id, key: '',
        get_lobby_data=lambda key: '',
    )

    event = NetEvent(
        'lobby_found',
        steam_id=44,
        data='{"host_name":"mac-host","requires_code":false,"members":1,"max_members":2}',
    )

    game._on_lobby_found(event)

    assert len(game._pending_lobby_list) == 1
    lobby = game._pending_lobby_list[0]
    assert lobby['visibility'] == 'public'
    assert lobby['requires_code'] is False
    assert lobby['metadata_ready'] is True


def test_lobby_found_keeps_public_visibility_when_requires_code_missing():
    game = _make_game()

    def _get_lobby_data_for(_lobby_id, key):
        mapping = {
            'visibility': 'public',
            'requires_code': '',
            'host_name': 'mac-host',
            'lobby_code': '',
        }
        return mapping.get(key, '')

    game.net = types.SimpleNamespace(
        get_lobby_data_for=_get_lobby_data_for,
        get_lobby_data=lambda key: '',
    )

    event = NetEvent(
        'lobby_found',
        steam_id=45,
        data='{"members":1,"max_members":2}',
    )

    game._on_lobby_found(event)

    assert len(game._pending_lobby_list) == 1
    lobby = game._pending_lobby_list[0]
    assert lobby['visibility'] == 'public'
    assert lobby['requires_code'] is False
    assert lobby['metadata_ready'] is True


def test_lobby_found_uses_explicit_visibility_even_when_metadata_ready_is_false():
    game = _make_game()
    game.net = types.SimpleNamespace(
        get_lobby_data_for=lambda lobby_id, key: '',
        get_lobby_data=lambda key: '',
    )

    event = NetEvent(
        'lobby_found',
        steam_id=46,
        data='{"host_name":"mac-host","visibility":"private","requires_code":true,"metadata_ready":false,"members":1,"max_members":2}',
    )

    game._on_lobby_found(event)

    assert len(game._pending_lobby_list) == 1
    lobby = game._pending_lobby_list[0]
    assert lobby['visibility'] == 'private'
    assert lobby['requires_code'] is True
    assert lobby['metadata_ready'] is True


def test_lobby_data_updated_refreshes_cached_lobby_entry():
    game = _make_game()
    game._lobby_list = [{
        'id': 99,
        'name': 'Unknown host',
        'code': '',
        'visibility': 'unknown',
        'requires_code': False,
        'metadata_ready': False,
    }]
    game._code_search_retry_count = 0
    game._code_search_retry_timer = 0.0
    game._code_search_retry_code = ''
    game._code_search_retry_use_full_scan = False
    game._join_target_lobby_id = 0
    game._status_msg = ''
    game._status_timer = 0.0
    game.net = types.SimpleNamespace(
        get_lobby_data_for=lambda _lobby_id, key: {
            'host_name': 'Public host',
            'visibility': 'public',
            'requires_code': '0',
            'metadata_ready': '1',
            'lobby_code': '',
        }.get(key, ''),
        get_lobby_data=lambda key: '',
        join_lobby=Mock(),
    )

    game._on_lobby_data_updated(NetEvent('lobby_data_updated', 99, '99'))

    lobby = game._lobby_list[0]
    assert lobby['name'] == 'Public host'
    assert lobby['visibility'] == 'public'
    assert lobby['requires_code'] is False
    assert lobby['metadata_ready'] is True
    game.net.join_lobby.assert_not_called()


def test_lobby_data_updated_can_complete_pending_code_join():
    game = _make_game()
    game._lobby_list = [{
        'id': 77,
        'name': 'Pending host',
        'code': '',
        'visibility': 'unknown',
        'requires_code': False,
        'metadata_ready': False,
    }]
    game._code_search_retry_count = 1
    game._code_search_retry_timer = 1500.0
    game._code_search_retry_code = '123456'
    game._code_search_retry_use_full_scan = True
    game._join_target_lobby_id = 0
    game._status_msg = ''
    game._status_timer = 0.0
    game.net = types.SimpleNamespace(
        get_lobby_data_for=lambda _lobby_id, key: {
            'host_name': 'Private host',
            'visibility': 'private',
            'requires_code': '1',
            'metadata_ready': '1',
            'lobby_code': '123456',
        }.get(key, ''),
        get_lobby_data=lambda key: '',
        join_lobby=Mock(),
    )

    game._on_lobby_data_updated(NetEvent('lobby_data_updated', 77, '77'))

    game.net.join_lobby.assert_called_once_with(77)
    assert game._code_search_retry_code == ''
    assert game._code_search_retry_timer == 0.0
    assert game._code_search_retry_use_full_scan is False