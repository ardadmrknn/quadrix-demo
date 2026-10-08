# -*- coding: utf-8 -*-
"""OP-030/031 gamepad çözüm-önbelleği sözleşmeleri (DALGA C; v2 paritesi).

_resolve_menu_button_actions ve _get_overridden_dpad_dirs artık oyun-bağlamı
_resolve_game_button_actions ile AYNI _bindings_rev sözleşmesine bağlı:
rev değişmedikçe kare-başı yeniden inşa YOK. Bu dosya isabet yolunu, rev
invalidasyonunu ve kazanan-öncelik semantiğini kilitler (kapsama dersi:
her yeni önbellek kendi isabet/invalidasyon testini taşır).

Modül importları gövde içinde (koleksiyon-runtime sys.modules kimlik
bölünmesi dersi).
"""
from __future__ import annotations

import os
import pathlib
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


def _make_manager(bindings):
    import gamepad_manager as gm

    manager = gm.GamepadManager.__new__(gm.GamepadManager)
    manager.gamepads = {}
    manager._context = gm.GamepadManager.CONTEXT_MENU
    manager._bindings = bindings
    return manager


def test_menu_button_actions_cache_hit_and_rev_invalidation():
    """OP-030: menü haritası rev değişmedikçe AYNI dict nesnesini döner;
    rev bump (bindings reload) yeniden inşa eder."""
    manager = _make_manager({
        'menu_confirm': {'button': 0},
        'menu_back': {'button': 1},
    })

    first = manager._resolve_menu_button_actions()
    second = manager._resolve_menu_button_actions()
    assert first is second, 'aynı bindings → aynı (önbellek) nesne'
    assert first == {0: 'menu_confirm', 1: 'menu_back'}

    # Rev bump (üretimde 644/748 yolları) → önbellek düşer.
    manager._bindings_rev = getattr(manager, '_bindings_rev', 0) + 1
    manager._bindings = {'menu_confirm': {'button': 2}}
    third = manager._resolve_menu_button_actions()
    assert third is not first, 'rev değişince önbellek düşmeli'
    assert third == {2: 'menu_confirm'}


def test_menu_button_actions_collision_winner_semantics():
    """Aynı butona iki menü aksiyonu düştüğünde MENU_ACTION_PRIORITY
    kazananı döner (eski satır-içi çözümle birebir semantik)."""
    manager = _make_manager({
        # Aynı buton (0): confirm(100) > back(90).
        'menu_confirm': {'button': 0},
        'menu_back': {'button': 0},
    })

    resolved = manager._resolve_menu_button_actions()
    assert resolved == {0: 'menu_confirm'}, 'kazanan öncelikte olmalı'

    # Bağlamsızlık: bağlam GAME'e döndürülse de menü çözümü aynı kalır
    # (bağlamı _generate_button_events seçer — harita bağlam anahtarı
    # taşımaz; OP-030 tasarım gerekçesi).
    import gamepad_manager as gm
    manager._context = gm.GamepadManager.CONTEXT_GAME
    assert manager._resolve_menu_button_actions() is resolved


def test_dpad_overridden_dirs_cache_hit_and_rev_invalidation():
    """OP-031: bastırma kümesi rev değişmedikçe AYNI set nesnesini döner;
    metod pad başına 2+ kez/kare çağrılsa bile taramalar tekrar koşmaz."""
    import gamepad_manager as gm

    manager = _make_manager({
        'slot_1': {'button': 12},  # D-pad Down poll-only → 'down' bastırılır
        'restart': {'button': 11},  # D-pad Up poll-only → 'up' bastırılır
    })
    manager._context = gm.GamepadManager.CONTEXT_GAME

    first = manager._get_overridden_dpad_dirs()
    second = manager._get_overridden_dpad_dirs()
    assert first is second, 'aynı bindings → aynı (önbellek) küme'
    assert first == {'up', 'down'}

    # Rev bump + yeni atama → taramalar yeniden koşar.
    manager._bindings_rev = getattr(manager, '_bindings_rev', 0) + 1
    manager._bindings = {'slot_1': {'button': 12}}
    third = manager._get_overridden_dpad_dirs()
    assert third is not first
    assert third == {'down'}


def test_dpad_literal_tables_are_module_constants():
    """DPAD tabloları modül sabitidir; ayrık kopyalar geri dönerse
    ölü-girdi bug'ı (GP-001 sınıfı) yeniden açılır — sabit kimliğini
    ve içeriğini kilitler."""
    import gamepad_manager as gm

    assert gm.DPAD_BTN_TO_DIR == {11: 'up', 12: 'down', 13: 'left', 14: 'right'}
    assert gm.DPAD_DIR_TO_ACTION == {
        'up': 'rotate',
        'down': 'soft_drop',
        'left': 'move_left',
        'right': 'move_right',
    }
    # Ok-tuşu → aksiyon haritaları bağlama göre seçilir (game/menu).
    import pygame
    assert gm.DPAD_KEY_ACTION_MAP_GAME[pygame.K_UP] == 'rotate'
    assert gm.DPAD_KEY_ACTION_MAP_MENU[pygame.K_UP] == 'menu_up'
    assert set(gm.MENU_BUTTON_ACTIONS_LIST) == {
        'menu_confirm', 'menu_back', 'pause',
        'menu_tab_next', 'menu_tab_prev',
        'editor_secondary', 'editor_delete',
    }
