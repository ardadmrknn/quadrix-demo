# -*- coding: utf-8 -*-
"""OP-036: _draw_ghost_piece kare-başı Surface tahsisini EffectSurfaceCache'e taşır.

Eski davranış: her _draw_ghost_piece çağrısında (her karede) yeni
``pygame.Surface((cell-2, cell-2), SRCALPHA)`` + fill üretiliyordu — CLAUDE.md
"kare başına bellek tahsisi yasağı"nın ihlali. Yeni davranış: dolgu yüzeyi
``self._effect_surface_cache.get_filled_surface`` LRU'sundan gelir; ilk
çağrı doldurur, tekrar eden kareler tahsissiz blit eder.

Bu dosya sözleşmeyi kilitler:
- ilk çağrı tam 1 Surface üretir (cache dolumu);
- aynı boyut/renkle ikinci çağrı YENİ Surface ÜRETMEZ, blit sayısı aynı
  kalır ve kaynak yüzey kimliği (identity) ilk kareyle aynıdır;
- dönen yüzeyin pikseli eski fill ile birebir (RGB + alpha=60);
- sınır dışı ghost hücreleri blitlenmez ama yüzey yine cache'ten gelir.

Kalıp: test_online_pvp_launch_guard draw idyomu (dummy sürücüler +
``__new__`` bare instance). Surface.blit read-only olduğundan ekran stub'la
ve ``pygame.draw.rect`` monkeypatch'le izole edilir.
"""
from __future__ import annotations

import os
import pathlib
import sys

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

import pygame

if not pygame.get_init():
    pygame.init()
if not pygame.display.get_init():
    pygame.display.init()
    pygame.display.set_mode((320, 240))
if not pygame.font.get_init():
    pygame.font.init()

ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / 'src'
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import pytest

import online_pvp_game as pvp
from effect_surface_cache import EffectSurfaceCache


class _PieceStub:
    """my_piece yeteri: shape/color/x — _draw_ghost_piece yalnız bunları okur."""

    color = (255, 120, 40)
    x = 3

    def get_shape(self):
        # 3 dolu hücre: (0,0), (0,1), (1,1) — gx=3,4 / gy=ghost_y,ghost_y+1.
        return [[1, 1], [0, 1]]


class _ScreenStub:
    def __init__(self):
        self.blit_calls = []

    def blit(self, source, dest, *args, **kwargs):
        self.blit_calls.append((source, tuple(dest)))


def _make_game(screen):
    game = pvp.OnlinePvPGame.__new__(pvp.OnlinePvPGame)
    game.my_piece = _PieceStub()
    game.screen = screen
    game._effect_surface_cache = EffectSurfaceCache()
    return game


def _wrap_surface_ctor(monkeypatch):
    """pygame.Surface yapıcısını sayan sarmalayıcı kur; sayaç listesi döner."""
    real_surface = pygame.Surface
    calls = []

    def counting_surface(*args, **kwargs):
        calls.append(1)
        return real_surface(*args, **kwargs)

    monkeypatch.setattr(pygame, 'Surface', counting_surface)
    return calls


def _stub_draw_rect(monkeypatch):
    """pygame.draw.rect'i Surface beklemeyen stub'la değiştir."""
    monkeypatch.setattr(
        pygame.draw, 'rect',
        lambda surface, color, rect, width=0, *a, **k: pygame.Rect(rect),
    )


def test_first_call_fills_cache_exactly_once(monkeypatch):
    calls = _wrap_surface_ctor(monkeypatch)
    _stub_draw_rect(monkeypatch)
    game = _make_game(_ScreenStub())
    game._draw_ghost_piece(40, 40, 24, ghost_y=15)
    # Cache dolumu: 1 üretim (dolgu yüzeyi). Ek üretim olmamalı.
    assert len(calls) == 1, f'ilk çağrı yalnız cache dolumu üretmeli, {len(calls)} üretti'


def test_second_call_allocates_no_new_surface(monkeypatch):
    calls = _wrap_surface_ctor(monkeypatch)
    _stub_draw_rect(monkeypatch)
    screen = _ScreenStub()
    game = _make_game(screen)

    game._draw_ghost_piece(40, 40, 24, ghost_y=15)
    assert len(calls) == 1
    assert len(screen.blit_calls) == 3, 'shape\'teki 3 dolu hücre blitlenmeli'
    first_sources = [src for src, _ in screen.blit_calls]

    game._draw_ghost_piece(40, 40, 24, ghost_y=15)
    assert len(calls) == 1, (
        f'tekrar eden kare yeni Surface tahsis etmemeli: {len(calls) - 1} yeni üretim'
    )
    assert len(screen.blit_calls) == 6, 'blit sayısı her karede aynı olmalı'
    # Kaynak yüzey cache'ten gelen AYNI obje (kopya değil).
    for src, _ in screen.blit_calls[3:]:
        assert src is first_sources[0], 'ikinci kare cache yüzeyini paylaşmalı'


def test_cached_surface_matches_legacy_fill_pixel():
    screen = pygame.Surface((480, 640), pygame.SRCALPHA)
    game = _make_game(screen)
    game._draw_ghost_piece(40, 40, 24, ghost_y=15)

    filled = next(iter(game._effect_surface_cache._cache.values()))
    # Eski davranışın birebir karşılığı: (*color[:3], 60) dolgusu.
    assert filled.get_size() == (24 - 2, 24 - 2)
    assert tuple(filled.get_at((1, 1))) == (255, 120, 40, 60)


def test_out_of_bounds_cells_do_not_blit_but_cache_still_serves(monkeypatch):
    calls = _wrap_surface_ctor(monkeypatch)
    _stub_draw_rect(monkeypatch)
    screen = _ScreenStub()
    game = _make_game(screen)
    # ghost_y tahta dışında: hiçbir hücre blitlenmez, yüzey yine cache'ten kurulur.
    game._draw_ghost_piece(40, 40, 24, ghost_y=pvp.BOARD_HEIGHT + 5)
    assert screen.blit_calls == []
    keys = list(game._effect_surface_cache._cache.keys())
    assert any(k[0] == 'fill' for k in keys), 'dolgu yüzeyi cache\'e yazılmalı'
    assert len(calls) == 1
