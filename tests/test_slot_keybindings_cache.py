# -*- coding: utf-8 -*-
"""Slot keybinding çözümü imza-cache sözleşmesi (OP-027).

_resolve_slot_keybindings config imzası değişmedikçe çözüm listesini
cache'ten döndürür (key_code dizisi tekrar koşmaz); ayar değişince imza
değişir ve yeni çözüm üretilir. Kurulum: __new__ bare-instance + stub.
"""
from __future__ import annotations

import os
import pathlib
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from game_modes_extra import MysteryMode


class _StubCardManager:
    MAX_CARD_SLOTS = 6


class _StubSettingsManager:
    def __init__(self, card_slots):
        self._card_slots = card_slots

    def get_controls(self):
        return {"card_slots": self._card_slots}


def _make_ui(card_slots):
    ui = MysteryMode.__new__(MysteryMode)
    ui.settings_manager = _StubSettingsManager(card_slots)
    ui.card_manager = _StubCardManager()
    return ui


def test_slot_keybindings_cache_hit_returns_same_object():
    ui = _make_ui({"slot_1": {"primary": "1", "secondary": "KP1"}})

    pygame.init()
    try:
        first = ui._resolve_slot_keybindings()
        assert isinstance(first, list) and len(first) == 6

        # Isabet: aynı ayar imzası -> cache'ten AYNI liste nesnesi.
        second = ui._resolve_slot_keybindings()
        assert second is first
        cache = getattr(ui, "_slot_keybindings_cache", None)
        assert cache is not None and cache[1] is first
    finally:
        pygame.quit()


def test_slot_keybindings_settings_change_invalidates_cache():
    slots = {"slot_1": {"primary": "1"}}
    ui = _make_ui(slots)

    pygame.init()
    try:
        first = ui._resolve_slot_keybindings()

        # Ayar degisimi: imza degisir -> yeni cozum listesi uretilir.
        slots["slot_2"] = {"primary": "q"}
        second = ui._resolve_slot_keybindings()
        assert second is not first
        # Yeni baglama cozumlenmis olmali (bos kume degil).
        assert second[1]
        # Cagiranlar sadece okur: set icerikleri baglamalarin keycode'lari.
        assert isinstance(second[0], set)
    finally:
        pygame.quit()
