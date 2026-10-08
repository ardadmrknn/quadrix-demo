# -*- coding: utf-8 -*-
"""OP-005 kendi görünen ad önbelleği (DALGA C).

Kare başı Steamworks persona çağrısı (draw içinde _get_name) yerine
oturum önbelleği: çözüm BİR kez, presence probu önbelleği düşürür,
my_steam_id yoksa 'Sen' fallback'i, _get_name istisnası id fallback'i
(cache'lenir — tekrar çağrı gitmez).
"""
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


def _make_game(my_steam_id=10):
    game = online_pvp_module.OnlinePvPGame.__new__(online_pvp_module.OnlinePvPGame)
    name_calls = []

    def _get_name(steam_id):
        name_calls.append(steam_id)
        return 'Arda' if steam_id == 10 else f'Peer{steam_id}'

    game.net = types.SimpleNamespace(my_steam_id=my_steam_id, _get_name=_get_name)
    game._cached_my_name = None
    game._name_calls = name_calls
    return game


def test_my_name_resolved_once_across_frames():
    game = _make_game()

    names = [game._resolve_my_display_name() for _ in range(60)]

    assert set(names) == {'Arda'}
    assert len(game._name_calls) == 1, '60 karede persona çağrısı BIR kez'


def test_presence_sync_drops_cache_and_reresolves():
    game = _make_game()
    assert game._resolve_my_display_name() == 'Arda'

    # Presence probu önbelleği düşürür → yeniden çözülür (isim değişimi
    # orada yansır).
    game._cached_my_name = None
    assert game._resolve_my_display_name() == 'Arda'
    assert len(game._name_calls) == 2


def test_missing_steam_id_falls_back_and_no_call():
    game = _make_game(my_steam_id=0)

    assert game._resolve_my_display_name() == 'Sen'
    assert game._name_calls == [], 'steam_id yoksa persona cagirilmamali'


def test_get_name_exception_falls_back_to_id_and_caches():
    game = _make_game()
    calls = []

    def _boom(steam_id):
        calls.append(steam_id)
        raise RuntimeError('bridge yok')

    game.net._get_name = _boom

    assert game._resolve_my_display_name() == '10', 'istisnada id fallback'
    # Fallback çözümü de cache'lenir → ikinci kare çağrı YOK.
    assert game._resolve_my_display_name() == '10'
    assert len(calls) == 1


def _make_presence_game():
    game = online_pvp_module.OnlinePvPGame.__new__(online_pvp_module.OnlinePvPGame)
    game.online_state = online_pvp_module.OnlineState.WAITING
    game._session_established = False
    game._session_ping_timer = 500.0
    game._pending_disconnect_steam_id = 123
    game._disconnect_grace_timer = 2500.0
    game.sound = types.SimpleNamespace(play=Mock())
    game._send_session_ping = Mock(return_value=True)
    game.net = types.SimpleNamespace(
        my_steam_id=10,
        opponent_steam_id=0,
        opponent_name='',
        _opponent_steam_id=0,
        _opponent_name='',
        get_lobby_members=lambda: [10, 42],
        _get_name=lambda steam_id: 'Peer 42' if steam_id == 42 else 'Arda',
    )
    return game


def test_presence_probe_invalidates_my_name_cache():
    game = _make_presence_game()
    game._cached_my_name = 'Arda'

    ok = game._sync_lobby_presence_from_members()

    assert ok is True
    assert game._cached_my_name is None, 'presence probu onbellegi dusurmeli'
