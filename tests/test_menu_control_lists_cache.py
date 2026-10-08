# -*- coding: utf-8 -*-
"""get_control_tabs/get_control_actions dil-epoch cache sözleşmesi (OP-028).

Iki uretici de (dil) anahtarli modul cache'i kullaniyor; bu dosya isabet
yolunu ve dil degisimi invalidasyonunu kilitler. Donen yapilarin
cagiranlarca yalniz okundugu (mutasyon yok) dogrulanmisti.
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

import menu


def test_control_lists_cache_hit_returns_same_object():
    first_tabs = menu.get_control_tabs()
    assert len(first_tabs) >= 4

    # Isabet: ayni dil -> cache'ten AYNI liste nesnesi.
    second_tabs = menu.get_control_tabs()
    assert second_tabs is first_tabs
    assert menu._CONTROL_TABS_CACHE

    first_actions = menu.get_control_actions()
    second_actions = menu.get_control_actions()
    assert second_actions is first_actions
    assert menu._CONTROL_ACTIONS_CACHE

    # Anahtar turleri: (key, label) ciftleri; dict bolum anahtarlari.
    assert all(isinstance(entry, tuple) and len(entry) == 2 for entry in first_tabs)
    assert 'single_player' in first_actions and 'pvp.player1' in first_actions


def test_control_lists_language_switch_invalidates_cache():
    from localization import get_language, set_language

    original_lang = str(get_language() or 'en')
    try:
        set_language('en')
        tabs_en = menu.get_control_tabs()

        set_language('tr')
        tabs_tr = menu.get_control_tabs()
        # Dil degisimi yeni epoch anahtari uretmeli: yeni liste nesnesi.
        assert tabs_tr is not tabs_en
        # Sekme anahtarlari (yerellestirmeden bagimsiz kimlikler) korunur.
        assert [key for key, _ in tabs_en] == [key for key, _ in tabs_tr]

        set_language('en')
        actions_en = menu.get_control_actions()
        # Ayni dil -> isabet: ayni dict nesnesi.
        assert menu.get_control_actions() is actions_en

        set_language('tr')
        actions_tr = menu.get_control_actions()
        assert actions_tr is not actions_en
    finally:
        set_language(original_lang)
        menu._CONTROL_TABS_CACHE.clear()
        menu._CONTROL_ACTIONS_CACHE.clear()
