from __future__ import annotations

import pathlib
import sys
import types

import pygame


ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / 'src'

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import online_pvp_game as online_pvp_module


def _make_game():
    game = online_pvp_module.OnlinePvPGame.__new__(online_pvp_module.OnlinePvPGame)
    game.settings_manager = None
    game._lobby_list = []
    game._lobby_list_filter = 'all'
    game._lobby_buttons = []
    game._status_msg = ''
    game._status_timer = 0.0
    return game


def test_trailer_debug_list_contains_one_private_and_three_public_entries():
    game = _make_game()
    game.settings_manager = types.SimpleNamespace(
        get=lambda key, default=None: True if key == 'online_pvp_trailer_debug' else default
    )

    entries = game._get_lobby_entries_for_display()

    assert len(entries) == 4
    assert sum(1 for lobby in entries if lobby.get('visibility') == 'private') == 1
    assert sum(1 for lobby in entries if lobby.get('visibility') == 'public') == 3
    assert all(lobby.get('debug_lobby') is True for lobby in entries)


def test_trailer_debug_list_respects_public_filter():
    game = _make_game()
    game._lobby_list_filter = 'public'
    game.settings_manager = types.SimpleNamespace(
        get=lambda key, default=None: True if key == 'online_pvp_trailer_debug' else default
    )

    entries = game._get_lobby_entries_for_display()

    assert len(entries) == 3
    assert all(lobby.get('visibility') == 'public' for lobby in entries)


def test_debug_lobby_click_sets_info_message_without_joining():
    game = _make_game()
    game._lobby_buttons = [
        {'rect': pygame.Rect(0, 0, 120, 40), 'action': 'debug_lobby'}
    ]

    result = game._handle_mouse_click(types.SimpleNamespace(pos=(12, 12)))

    assert result is None
    assert 'fragman' in game._status_msg.lower()
    assert game._status_timer == 2.5


def test_request_lobby_list_skips_steam_listing_in_trailer_debug_mode():
    game = _make_game()
    game.settings_manager = types.SimpleNamespace(
        get=lambda key, default=None: True if key == 'online_pvp_trailer_debug' else default
    )
    game._lobby_list_fetching = True
    game._lobby_list_fetch_start_time = 123.0
    game._pending_lobby_list = [{'id': 1}]
    game._deferred_lobby_entries = {1: {'id': 1}}
    game._clear_lobby_metadata_refresh_request = lambda: None
    game._init_networking = lambda: (_ for _ in ()).throw(AssertionError('network should not initialize'))

    assert game._request_lobby_list() is True
    assert game._lobby_list_fetching is False
    assert game._lobby_list_fetch_start_time == 0
    assert game._pending_lobby_list == []
    assert game._deferred_lobby_entries == {}