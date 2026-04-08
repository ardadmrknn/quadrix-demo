from __future__ import annotations

import pathlib
import sys
from unittest.mock import Mock


ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / 'src'

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import steam_networking as steam_networking_module


def test_request_lobby_list_can_force_worldwide_distance_filter():
    net = steam_networking_module.SteamNetworking()
    net._bridge_instance = Mock()

    net.request_lobby_list(worldwide=True)

    net._bridge_instance.add_request_lobby_list_distance_filter.assert_called_once_with(
        steam_networking_module.LobbyDistanceFilter.WORLDWIDE,
    )
    net._bridge_instance.request_lobby_list.assert_called_once_with()


def test_request_lobby_list_still_runs_when_distance_filter_is_unavailable():
    net = steam_networking_module.SteamNetworking()
    bridge = Mock(spec=['request_lobby_list'])
    net._bridge_instance = bridge

    net.request_lobby_list(worldwide=True)

    net._bridge_instance.request_lobby_list.assert_called_once_with()


def test_search_lobby_by_code_uses_worldwide_distance_filter():
    net = steam_networking_module.SteamNetworking()
    net._bridge_instance = Mock()

    net.search_lobby_by_code('123456')

    net._bridge_instance.add_request_lobby_list_distance_filter.assert_called_once_with(
        steam_networking_module.LobbyDistanceFilter.WORLDWIDE,
    )
    net._bridge_instance.add_request_lobby_list_string_filter.assert_called_once_with('lobby_code', '123456')
    net._bridge_instance.request_lobby_list.assert_called_once_with()


def test_search_lobby_by_code_keeps_string_filter_when_distance_filter_is_unavailable():
    net = steam_networking_module.SteamNetworking()
    bridge = Mock(spec=['add_request_lobby_list_string_filter', 'request_lobby_list'])
    net._bridge_instance = bridge

    net.search_lobby_by_code('123456')

    net._bridge_instance.add_request_lobby_list_string_filter.assert_called_once_with('lobby_code', '123456')
    net._bridge_instance.request_lobby_list.assert_called_once_with()


def test_create_lobby_prefers_invisible_type_for_private_code_lobbies():
    net = steam_networking_module.SteamNetworking()
    net._bridge_instance = Mock()

    net.create_lobby(public=False)

    net._bridge_instance.create_lobby_with_type.assert_called_once_with(
        steam_networking_module.LobbyType.INVISIBLE,
        2,
    )
    net._bridge_instance.create_lobby.assert_not_called()


def test_create_lobby_falls_back_to_default_create_when_typed_api_is_missing():
    net = steam_networking_module.SteamNetworking()
    bridge = Mock(spec=['create_lobby'])
    net._bridge_instance = bridge

    net.create_lobby(public=False)

    net._bridge_instance.create_lobby.assert_called_once_with(2)