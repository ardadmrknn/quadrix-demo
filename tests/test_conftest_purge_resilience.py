# -*- coding: utf-8 -*-
"""conftest purge dayanıklılığı — tembel __getattr__ istisnaları (DALGA C inceleme).

289dbba/24b6f5d'nin _looks_like_test_stub guard'ı birinci döngüyü (stub
sayma) güvenceye aldı. DALGA C kapanış incelemesi (2026-10-08) aynı
gerekenin ikinci döngüde eksik kaldığını buldu: purge'un ikinci
döngüsündeki ``getattr(module_obj, "pygame", None)`` ve
``_purge_foreign_callable_module`` içindeki ``getattr(module_obj,
attr_name, None)`` korumasızdı. ``__getattr__``'ı ImportError fırlatan
bir modül getattr'ın None varsayılanına takılmaz (varsayılan yalnız
AttributeError'u yutar) → purge kilitlenir → teardown zincirindeki
``_purge_leaked_pygame_stubs``/``_reset_ui_scale_preset`` atlanırdı
(commit'in "purge döngüsü kesilmeden devam eder" vaadi ikinci döngü
için eksikti).

Bu dosya guard'lı hâli kilitler: purge istisna fırlatan modülü atlayıp
kesilmeden tamamlanmalı; modül düşürülmez (gerçek modül muamelesi —
ayırt edilemiyorsa güvenli taraf).
"""
from __future__ import annotations

import sys
import types

import pytest

import conftest


class _BrokenModule(types.ModuleType):
    """test_tutorial_cards_catalog_recovery deyimi: tembel __getattr__."""

    def __getattr__(self, name):
        raise ImportError(f"broken stub for {name!r}")


def test_purge_survives_raising_getattr_module(monkeypatch):
    """İkinci döngü (FAZ A8 binding purge) burada kilitleniyordu."""
    broken = _BrokenModule("game_modes_extra")
    monkeypatch.setitem(sys.modules, "game_modes_extra", broken)

    conftest._purge_leaked_test_stubs(skip_pygame=True)

    # Gerçek modül muamelesi: düşürülmez, döngü kesilmeden tamamlanır.
    assert sys.modules.get("game_modes_extra") is broken


def test_foreign_callable_purge_survives_raising_getattr(monkeypatch):
    """_purge_foreign_callable_module aynı deseni taşıyordu."""
    broken = _BrokenModule("background_effects")
    monkeypatch.setitem(sys.modules, "background_effects", broken)

    purged = conftest._purge_foreign_callable_module(
        ("background_effects", "src.background_effects"),
        ("get_shared_falling_blocks_layer", "sync_shared_falling_blocks_appearance"),
    )

    assert purged is False
    assert sys.modules.get("background_effects") is broken


if __name__ == "__main__":
    pytest.main([__file__, "-q"])
