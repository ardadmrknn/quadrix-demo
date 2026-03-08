from __future__ import annotations

import pathlib
import sys
import types


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
    assert lobby['visibility'] == 'public'
    assert lobby['requires_code'] is False


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
    assert lobby['code'] == ''