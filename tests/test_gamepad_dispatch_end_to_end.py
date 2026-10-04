# -*- coding: utf-8 -*-
"""Coop/PvP gamepad dispatch UÇTAN UCA davranışsal testleri (demo).

v2 tests/test_gamepad_dispatch_end_to_end.py uyarlaması — R2 inceleme
bulgusu: dispatch düzeltmeleri yalnız birim+sözleşme testliydi; bu dosya
handle_input'a gerçek (sahte) event verip hold/drop/move GERÇEKLEŞTİĞİNİ
kanıtlar. Demo farkları: coop KEYUP gövdeleri basit yön sıfırlama
(DAS-controller yok); pvp de davranışsal kapsanır (v2 pvp lobi tabanlı
olduğundan v2 dosyasında pvp testi bilinçli YOKTUR).
"""
from __future__ import annotations

import os
import pathlib
import sys
import types

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import pytest

if not pygame.display.get_init():
    pygame.display.init()
if not pygame.font.get_init():
    pygame.font.init()


def _make_coop_harness():
    import coop_game as cg

    game = cg.CoopGame.__new__(cg.CoopGame)
    game.pvp_controls = {
        'player1': {'move_left': pygame.K_a, 'move_right': pygame.K_d,
                    'soft_drop': pygame.K_s, 'rotate': pygame.K_w,
                    'rotate_ccw': pygame.K_q, 'hard_drop': pygame.K_LSHIFT,
                    'hold': pygame.K_e},
        'player2': {'move_left': pygame.K_LEFT, 'move_right': pygame.K_RIGHT,
                    'soft_drop': pygame.K_DOWN, 'rotate': pygame.K_UP,
                    'rotate_ccw': pygame.K_RCTRL, 'hard_drop': pygame.K_SPACE,
                    'hold': pygame.K_RSHIFT},
        'pause': pygame.K_p,
        'debug': {},
    }
    game.paused = False
    game.game_over = False
    game.p1_frozen = False
    game.p2_frozen = False
    game.p1_current_piece = object()
    game.p2_current_piece = object()
    game.p1_gamepad_idx = None
    game.p2_gamepad_idx = None
    game.p1_gamepad_instance_id = None
    game.p2_gamepad_instance_id = None
    game.settings_manager = None
    game.sound = types.SimpleNamespace(
        play=lambda *a, **k: None,
        duck_music=lambda: None,
        unduck_music=lambda: None,
    )
    calls = []
    game._try_move = lambda who, d: calls.append(('move', who, d)) or True
    game._hard_drop = lambda who: calls.append(('hard_drop', who))
    game._use_shared_hold = lambda who: calls.append(('hold', who))
    game._try_rotate = lambda who, direction=1: calls.append(('rotate', who, direction))
    game._step_piece_down = lambda who: calls.append(('soft_step', who))
    game.p1_das_direction = 0
    game.p2_das_direction = 0
    game.p1_das_charged = False
    game.p2_das_charged = False
    game.p1_soft_drop_active = False
    game.p2_soft_drop_active = False
    return game, calls


def _make_pvp_harness():
    import pvp_game as pg

    game = pg.PvPGame.__new__(pg.PvPGame)
    game.pvp_controls = {
        'player1': {'move_left': pygame.K_a, 'move_right': pygame.K_d,
                    'soft_drop': pygame.K_s, 'rotate': pygame.K_w,
                    'rotate_ccw': pygame.K_q, 'hard_drop': pygame.K_LSHIFT,
                    'hold': pygame.K_LCTRL},
        'player2': {'move_left': pygame.K_LEFT, 'move_right': pygame.K_RIGHT,
                    'soft_drop': pygame.K_DOWN, 'rotate': pygame.K_UP,
                    'rotate_ccw': pygame.K_RCTRL, 'hard_drop': pygame.K_SPACE,
                    'hold': pygame.K_RCTRL},
        'pause': pygame.K_p,
    }
    game.paused = False
    game.game_over = False
    game.name_input_active = False
    game.p1_gamepad_idx = None
    game.p2_gamepad_idx = None
    game.p1_gamepad_instance_id = None
    game.p2_gamepad_instance_id = None
    game.settings_manager = None
    game.board1 = types.SimpleNamespace(is_game_over=lambda: False)
    game.board2 = types.SimpleNamespace(is_game_over=lambda: False)
    game.current_piece2 = types.SimpleNamespace(x=4, y=5)
    game.effects_enabled = False
    game._is_player1_demobot_active = lambda: False

    calls = []
    game._try_move_left_p1 = lambda: calls.append(('move', 'P1', -1)) or True
    game._try_move_right_p1 = lambda: calls.append(('move', 'P1', 1)) or True
    game._try_move_left_p2 = lambda: calls.append(('move', 'P2', -1)) or True
    game._try_move_right_p2 = lambda: calls.append(('move', 'P2', 1)) or True
    game._hard_drop_p1 = lambda: calls.append(('hard_drop', 'P1'))
    game._try_hard_drop_p2 = None  # pvp P2 hard drop gövdesi satır içi
    game._try_rotate_p1 = lambda direction=1: calls.append(('rotate', 'P1', direction))
    game._try_rotate_p2 = lambda direction=1: calls.append(('rotate', 'P2', direction))
    game._try_hold_piece = lambda player: calls.append(('hold', player))
    game._try_soft_drop_step_p1 = lambda: calls.append(('soft_step', 'P1'))
    game.p1_das_direction = 0
    game.p2_das_direction = 0
    game.p1_soft_drop_active = False
    game.p2_soft_drop_active = False
    game.demobot_active = False
    game.sound = types.SimpleNamespace(play=lambda *a, **k: None, duck_music=lambda: None, unduck_music=lambda: None)
    return game, calls


def _gp_event(key, action, player, device=3, etype=pygame.KEYDOWN):
    return types.SimpleNamespace(
        type=etype, key=key, mod=0, from_gamepad=True, action=action,
        device_index=device, gamepad_player=player,
    )


def _kbd_event(key, etype=pygame.KEYDOWN):
    return types.SimpleNamespace(type=etype, key=key, mod=0, unicode='', from_gamepad=False)


def _feed(mod, monkeypatch, events):
    monkeypatch.setattr(mod.pygame.event, 'get', lambda: list(events))


# ── Coop: F3'nin çekirdek senaryoları ────────────────────────────────────────

def test_gamepad_hold_p1_end_to_end(monkeypatch):
    """Gamepad hold (K_c sentetik + action='hold') P1'e — eski davranışta
    K_c, c1 hold K_e ile eşleşmezdi → gamepad hold HİÇ çalışmıyordu."""
    import coop_game as cg
    game, calls = _make_coop_harness()
    _feed(cg, monkeypatch, [_gp_event(pygame.K_c, 'hold', 1)])
    game.handle_input()
    assert ('hold', 'P1') in calls


def test_gamepad_hold_p2_end_to_end(monkeypatch):
    import coop_game as cg
    game, calls = _make_coop_harness()
    _feed(cg, monkeypatch, [_gp_event(pygame.K_c, 'hold', 2)])
    game.handle_input()
    assert ('hold', 'P2') in calls


def test_gamepad_hold_legacy_default_p2(monkeypatch):
    import coop_game as cg
    game, calls = _make_coop_harness()
    _feed(cg, monkeypatch, [_gp_event(pygame.K_c, 'hold', None, device=7)])
    game.handle_input()
    assert ('hold', 'P2') in calls


def test_gamepad_hold_ccw_metadata_p2(monkeypatch):
    """Gamepad rotate_ccw (K_z sentetik + action) P2'ye — eski davranışta
    K_z hiçbir varsayılan rotate_ccw tuşuyla (K_q/K_RCTRL) eşleşmezdi."""
    import coop_game as cg
    game, calls = _make_coop_harness()
    _feed(cg, monkeypatch, [_gp_event(pygame.K_z, 'rotate_ccw', 2)])
    game.handle_input()
    assert ('rotate', 'P2', -1) in calls


def test_keyboard_hold_p1_end_to_end(monkeypatch):
    import coop_game as cg
    game, calls = _make_coop_harness()
    _feed(cg, monkeypatch, [_kbd_event(pygame.K_e)])
    game.handle_input()
    assert ('hold', 'P1') in calls


def test_gamepad_hard_drop_p2_end_to_end(monkeypatch):
    import coop_game as cg
    game, calls = _make_coop_harness()
    _feed(cg, monkeypatch, [_gp_event(pygame.K_SPACE, 'hard_drop', 2)])
    game.handle_input()
    assert ('hard_drop', 'P2') in calls


def test_keyboard_remap_does_not_drop_gamepad_move(monkeypatch):
    """Klavye remap'i gamepad'i düşürmez (F3 çekirdeği)."""
    import coop_game as cg
    game, calls = _make_coop_harness()
    game.pvp_controls['player1']['move_left'] = pygame.K_a
    _feed(cg, monkeypatch, [_gp_event(pygame.K_LEFT, 'move_left', 1)])
    game.handle_input()
    assert ('move', 'P1', -1) in calls


def test_gamepad_keyup_soft_drop_clears(monkeypatch):
    """Gamepad soft_drop KEYUP (metadata) soft-drop kilidini temizler."""
    import coop_game as cg
    game, _ = _make_coop_harness()
    game.p2_soft_drop_active = True
    _feed(cg, monkeypatch, [_gp_event(pygame.K_DOWN, 'soft_drop', 2, etype=pygame.KEYUP)])
    game.handle_input()
    assert game.p2_soft_drop_active is False


# ── PvP: F3'ün pvp yarısı ────────────────────────────────────────────────────

def test_pvp_gamepad_hold_p1_end_to_end(monkeypatch):
    """Gamepad hold P1'e (metadata) — eski davranışta K_c, pvp hold
    K_LCTRL/K_RCTRL ile eşleşmezdi → HİÇ çalışmıyordu."""
    import pvp_game as pg
    game, calls = _make_pvp_harness()
    _feed(pg, monkeypatch, [_gp_event(pygame.K_c, 'hold', 1)])
    game.handle_input()
    assert ('hold', 1) in calls


def test_pvp_gamepad_hold_p2_end_to_end(monkeypatch):
    import pvp_game as pg
    game, calls = _make_pvp_harness()
    _feed(pg, monkeypatch, [_gp_event(pygame.K_c, 'hold', 2)])
    game.handle_input()
    assert ('hold', 2) in calls


def test_pvp_gamepad_move_p1_end_to_end(monkeypatch):
    import pvp_game as pg
    game, calls = _make_pvp_harness()
    _feed(pg, monkeypatch, [_gp_event(pygame.K_LEFT, 'move_left', 1)])
    game.handle_input()
    assert ('move', 'P1', -1) in calls


def test_pvp_gamepad_rotate_ccw_p1(monkeypatch):
    """Gamepad rotate_ccw (K_z) P1'e — eski davranışta eşleşmezdi."""
    import pvp_game as pg
    game, calls = _make_pvp_harness()
    _feed(pg, monkeypatch, [_gp_event(pygame.K_z, 'rotate_ccw', 1)])
    game.handle_input()
    assert ('rotate', 'P1', -1) in calls


def test_pvp_keyboard_remap_does_not_drop_gamepad_move(monkeypatch):
    import pvp_game as pg
    game, calls = _make_pvp_harness()
    game.pvp_controls['player1']['move_left'] = pygame.K_a
    _feed(pg, monkeypatch, [_gp_event(pygame.K_LEFT, 'move_left', 1)])
    game.handle_input()
    assert ('move', 'P1', -1) in calls
