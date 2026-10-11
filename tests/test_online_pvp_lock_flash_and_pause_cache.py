# -*- coding: utf-8 -*-
"""OP-007/OP-008 (online_pvp kalan iki nokta): kilit-parlama glow + pause dim LRU.

- kilit-parlama (üçüncü OP-007 ikizi): parça grounded + lock_timer oranına
  göre hücre başına her kare ``pygame.Surface((cell_size-2,)*2, SRCALPHA)`` +
  ``fill((255,255,255,alpha))`` üretiliyordu. Yeni davranış
  ``_get_grounded_glow_surface`` — ``EffectSurfaceCache.get_filled_surface``
  (ghost/sweep deseni; pvp_game/coop_game 609/4221 muadili).
- pause dim (online_pvp OP-008 ayağı): ``_draw_pause_overlay`` her çağrıda
  tam-ekran SRCALPHA + fill (4K'ta ~8 MB/kare) üretiyordu. Yeni davranış
  ``_get_pause_dim_surface`` (pvp_game standardı, alpha=185).

Sözleşmeler:
- her iki helper: aynı (boyut, RGBA) → AYNI yüzey objesi (LRU isabeti) ve
  piksel içeriği eski ``Surface + fill`` üretimiyle birebir (get_at örneklemi);
- ``_draw_board`` kilit-parlama yolu: ilk çağrı yalnız cache dolumu üretir,
  ikinci çağrı SIFIR yeni Surface üretir ve blitlenen glow objesi aynıdır;
- ``_draw_pause_overlay``: karartma yüzeyi cache'ten gelir (blit kaynağı,
  helper'ın döndürdüğü objeyle kimlikçe aynı).

Kalıp: test_online_pvp_ghost_surface_cache draw idyomu (dummy sürücüler +
``__new__`` bare instance + blit kaydeden ekran stub'ı).
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

ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / 'src'
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import pytest

import online_pvp_game as pvp
from effect_surface_cache import EffectSurfaceCache


class _ScreenStub:
    """get_size + blit kaydı (demo ayağı window_width/height ayrıca kurulur)."""

    def __init__(self, size=(320, 240)):
        self._size = size
        self.blit_calls = []

    def get_size(self):
        return self._size

    def blit(self, source, dest, *args, **kwargs):
        self.blit_calls.append((source, tuple(dest)))


class _PieceStub:
    """my_piece yeteri: shape/color/x/y — kilit-parlama yolu bunları okur."""

    color = (255, 120, 40)
    x = 3
    y = 5
    texture_surface = None

    def get_shape(self):
        return [[1]]


class _BoardStub:
    """Boş tahta + grounded parça (is_valid_position dy=1 → False)."""

    def __init__(self):
        self.occupancy = [[0] * pvp.BOARD_WIDTH for _ in range(pvp.BOARD_HEIGHT)]
        self.grid = [[None] * pvp.BOARD_WIDTH for _ in range(pvp.BOARD_HEIGHT)]

    def is_valid_position(self, piece, dy=1):
        return False


class _BackgroundStub:
    def draw(self, screen, rect):
        return None


class _RsStub:
    """_draw_pause_overlay panel yolu için minimal _rs yüzeyi."""

    accent = (255, 190, 60)
    text_secondary = (170, 170, 180)
    text_primary = (235, 235, 240)

    def get_font(self, size, bold=True):
        return pygame.font.Font(None, max(10, int(size)))

    def get_fitting_font(self, text, size, max_w):
        return pygame.font.Font(None, max(10, int(size)))


def _make_game(screen, piece=None):
    game = pvp.OnlinePvPGame.__new__(pvp.OnlinePvPGame)
    game.screen = screen
    game.window_width, game.window_height = screen.get_size()
    game._effect_surface_cache = EffectSurfaceCache()
    game.mode_skin = None
    game.board_background = _BackgroundStub()
    game.block_style_manager = None
    game.effects_enabled = False
    game.drop_trails = []
    game.lock_timer = 250.0
    game.lock_delay = 500
    # Satır-süpürme/flash/wave kolları kapalı — kilit-parlama yolunu izole tut.
    game.my_line_sweep_rows = []
    game.my_line_sweep_active = False
    game.my_line_sweep_progress = 0.0
    game.my_line_flash_rows = []
    game.my_line_glow_alpha = 0.0
    game.my_wave_effects = []
    if piece is not None:
        game.my_piece = piece
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


def _stub_board_module_funcs(monkeypatch):
    """_draw_board'un modül-düzeyi çizim yardımcılarını no-op'la."""
    monkeypatch.setattr(pvp, 'draw_glass_panel', lambda *a, **k: None)
    monkeypatch.setattr(pvp, 'draw_board_overlay', lambda *a, **k: None)
    monkeypatch.setattr(pvp, 'apply_board_tint', lambda *a, **k: None)
    monkeypatch.setattr(
        pygame.draw, 'rect',
        lambda surface, color, rect, width=0, *a, **k: pygame.Rect(rect),
    )


def _stub_board_instance_helpers(game, accent_dummy, grid_dummy):
    """_draw_board'un instance yardımcılarını ve texture çağrılarını stub'la."""
    game._get_board_accent_overlay = lambda *a, **k: accent_dummy
    game._get_board_grid_surface = lambda *a, **k: grid_dummy
    game._get_block_fall_offset = lambda row, col, is_opponent=False: 0
    game.draw_textured_block = lambda *a, **k: None
    game._make_texture_slice = lambda *a, **k: None


def test_grounded_glow_helper_identity_and_pixel_parity():
    game = _make_game(_ScreenStub())
    s1 = game._get_grounded_glow_surface(22, 120)
    s2 = game._get_grounded_glow_surface(22, 120)
    assert s1 is s2, 'aynı (boyut, alfa) LRU işareti aynı objeyi döndürmeli'

    legacy = pygame.Surface((22, 22), pygame.SRCALPHA)
    legacy.fill((255, 255, 255, 120))
    assert s1.get_size() == legacy.get_size()
    for nokta in ((0, 0), (11, 11), (21, 21)):
        assert s1.get_at(nokta) == legacy.get_at(nokta), (
            f'piksel paritesi bozuldu: {nokta}'
        )


def test_pause_dim_helper_identity_and_pixel_parity():
    game = _make_game(_ScreenStub())
    s1 = game._get_pause_dim_surface((100, 50))
    s2 = game._get_pause_dim_surface((100, 50))
    assert s1 is s2, 'aynı boyut LRU işareti aynı objeyi döndürmeli'

    legacy = pygame.Surface((100, 50), pygame.SRCALPHA)
    legacy.fill((0, 0, 0, 185))
    assert s1.get_size() == legacy.get_size()
    for nokta in ((0, 0), (50, 25), (99, 49)):
        assert s1.get_at(nokta) == legacy.get_at(nokta), (
            f'piksel paritesi bozuldu: {nokta}'
        )


def test_lock_flash_first_draw_fills_cache_once_then_zero(monkeypatch):
    _stub_board_module_funcs(monkeypatch)
    screen = _ScreenStub()
    game = _make_game(screen, piece=_PieceStub())
    # Dummy'ler sayaç kurulmadan ÖNCE yaratılır — yalnız kilit-parlama
    # cache dolumu sayılmalı.
    accent_dummy = pygame.Surface((4, 4))
    grid_dummy = pygame.Surface((4, 4))
    _stub_board_instance_helpers(game, accent_dummy, grid_dummy)
    calls = _wrap_surface_ctor(monkeypatch)

    game._draw_board(10, 10, 24, _BoardStub(), game.my_piece)
    # İlk çizim: yalnızca glow cache dolumu üretir (accent/grid dummy'leri
    # sayaç kurulmadan ÖNCE yaratıldı; texture/blok çizimi stub'lı).
    assert len(calls) == 1, f'ilk çağrı yalnız cache dolumu üretmeli, {len(calls)} üretti'
    glow_first = screen.blit_calls[-1][0]

    n_blit_before = len(screen.blit_calls)
    game._draw_board(10, 10, 24, _BoardStub(), game.my_piece)
    # İkinci çizim: sıfır yeni üretim; glow aynı objeyi paylaşır.
    assert len(calls) == 1, f'ikinci çağrı yeni Surface üretmemeli, {len(calls) - 1} üretti'
    glow_second = screen.blit_calls[-1][0]
    assert glow_first is glow_second, 'kilit-parlama glow yüzeyi kareler arası paylaşılmalı'


def test_pause_overlay_blits_cached_dim_surface(monkeypatch):
    monkeypatch.setattr(pvp, 'draw_glass_panel', lambda *a, **k: None)
    monkeypatch.setattr(pvp, 't', lambda key, default=None, *a, **k: default)
    monkeypatch.setattr(pvp, '_rs', _RsStub())

    screen = _ScreenStub()
    game = _make_game(screen)
    game.paused = True
    game._ui_scale = lambda: 1.0
    game._sx = lambda v, sc=1.0, minimum=1: max(minimum, int(v))

    expected = game._get_pause_dim_surface(screen.get_size())
    game._draw_pause_overlay()

    assert screen.blit_calls, 'pause overlay en az karartmayı blitlemeli'
    assert screen.blit_calls[0][0] is expected, (
        'karartma yüzeyi efekt cache\'inden gelmeli (ham Surface değil)'
    )
    assert screen.blit_calls[0][1] == (0, 0)
