# -*- coding: utf-8 -*-
"""Faz 6b / I-46 — Gizli satır gölge şeridi ve S-21 yerleşim rezervasyonu.

Kök neden: `Board` iki gizli satırı (`hidden_occupancy`/`hidden_grid`) doğru
yönetiyordu ama görünür alanın üstüne taşan bu hücreler HİÇBİR ZAMAN
çizilmiyordu — oyuncu tehlikeyi ancak lock-out anında görüyordu.

Düzeltme iki parçalı:
  1. `gameplay_layout.compute_single_player_layout` tahta + yan HUD'u
     `hidden_strip_height + hidden_strip_gap` kadar aşağı kaydırır (S-21).
  2. `Game._draw_hidden_row_strip` tahtanın hemen üstündeki bu bantta, dolu
     sütunlar için %55 alfalı ince şerit çizer.

Kabul sözleşmesi (kılavuz F6b.1): (a) dolu gizli hücre varken şerit pikseli
görünür, (b) gizli satır boşken hiçbir şey çizilmez, (c) `show_ghost=False`
iken de görünür, (d) iki kez çizim `Surface` sayısını artırmaz (LRU cache +
kuantize alfa), (e) 640×360 / 1280×720 / 1920×1080 × UI preset 100/175/200'de
şerit bandı tahtanın üstünde, HUD tahtayla hizalı ve hiçbir şey taşmıyor.

Kanıt yöntemi: `_BlitSpy` yerine GERÇEK piksel sondası — blit çağrısı saymak
"çağrıldı ama görünmüyor" durumunu kaçırır; bu test şeridin ekranda gerçekten
göründüğünü doğrular.
"""

from __future__ import annotations

import os
import pathlib
import sys
import types

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
os.environ.setdefault('SDL_RENDER_VSYNC', '0')

import pygame
import pytest

ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent.parent
SRC_DIR = ROOT_DIR / 'src'
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import game as game_module  # noqa: E402
from game import Game, HIDDEN_STRIP_ALPHA  # noqa: E402
from constants import BLACK  # noqa: E402
from gameplay_layout import (  # noqa: E402
    HIDDEN_STRIP_CELL_RATIO,
    compute_single_player_layout,
)

pytestmark = pytest.mark.quadrix_feedback

CELL = 30
OX, OY = 200, 160
BOARD_W, BOARD_H = 10, 20
HIDDEN_ROWS = 2
STRIP_H, STRIP_GAP = 15, 10
STRIP_COLOR = (200, 90, 60)


def _blank_grid(rows, cols, fill=BLACK):
    return [[fill for _ in range(cols)] for _ in range(rows)]


def _blank_flags(rows, cols):
    return [[False for _ in range(cols)] for _ in range(rows)]


def _make_game(hidden_cells, hidden_rows=HIDDEN_ROWS, strip_h=STRIP_H,
               strip_gap=STRIP_GAP, show_ghost=True):
    """`Game.__new__` + çizim yolu enjeksiyonu (duz010 / OP-014 deseni).

    `_draw_base_scene` gerçekten koşar; tahta arka planı/tint/overlay no-op'lanır
    çünkü `.convert_alpha()` display formatı ister ve bu test blit SAYISINI ve
    GEOMETRİYİ doğrular, piksel tint'ini değil.
    """
    pygame.init()
    if not pygame.display.get_init():
        pygame.display.init()

    game = Game.__new__(Game)
    game.screen = pygame.Surface((900, 800))
    game.game_mode = 'classic'
    game.mode_skin = None
    game.effects_enabled = False
    game.game_over = True
    game.current_piece = None
    game.outer_background = types.SimpleNamespace(is_loaded=lambda: False)
    game.single_background = types.SimpleNamespace(is_loaded=lambda: False)
    game.background_manager = types.SimpleNamespace()
    game.settings_manager = types.SimpleNamespace(get=lambda k, d=None: show_ghost)
    game.get_shake_offset = lambda: (0, 0)
    game.get_cell_size = lambda: CELL
    game.get_board_offset = lambda: (OX, OY)
    game.board_width = BOARD_W
    game.board_height = BOARD_H
    # Layout'u instance düzeyinde sabitle: `_get_gameplay_layout_metrics`
    # gerçek ekran boyutundan yeniden hesaplarsa enjekte edilen cell/offset ile
    # şerit yüksekliği birbirinden kopar (test ölçtüğü sözleşmeyi kaybeder).
    game._get_gameplay_layout_metrics = lambda: types.SimpleNamespace(
        hidden_strip_height=strip_h,
        hidden_strip_gap=strip_gap,
        cell_size=CELL,
    )

    hidden_occ = _blank_flags(hidden_rows, BOARD_W)
    hidden_grid = _blank_grid(hidden_rows, BOARD_W)
    for (row, col) in hidden_cells:
        hidden_occ[row][col] = True
        hidden_grid[row][col] = STRIP_COLOR

    game.board = types.SimpleNamespace(
        width=BOARD_W,
        height=BOARD_H,
        grid=_blank_grid(BOARD_H, BOARD_W),
        occupancy=_blank_flags(BOARD_H, BOARD_W),
        texture_grid=[[None for _ in range(BOARD_W)] for _ in range(BOARD_H)],
        hidden_occupancy=hidden_occ,
        hidden_grid=hidden_grid,
        last_cleared_lines=[],
        flexible_border_active=False,
    )
    game._board_grid_cache = {'key': None, 'surface': None}
    game._solid_alpha_surface_cache = {}
    game._solid_alpha_surface_cache_order = []
    game._solid_alpha_surface_cache_max = 64
    game.line_clear_flash = False
    game.falling_block_animations = []
    game.drop_trails = []
    game.line_clear_wave_effects = []
    game.line_clear_sweep_rows = []
    game.line_clear_sweep_active = False
    game.line_clear_pending_rows = []
    game.block_style_manager = None
    game.draw_board_background = lambda *a, **k: None
    game._draw_custom_frame = lambda *a, **k: False
    game._draw_right_hud_panel = lambda *a, **k: None
    game._draw_base_scene_effects = lambda *a, **k: None

    _original_tint = game_module.apply_board_tint
    _original_overlay = game_module.draw_board_overlay
    game_module.apply_board_tint = lambda *a, **k: None
    game_module.draw_board_overlay = lambda *a, **k: None
    try:
        game._draw_base_scene()
    finally:
        game_module.apply_board_tint = _original_tint
        game_module.draw_board_overlay = _original_overlay
    return game


def _strip_pixel(game, col, strip_y=OY - STRIP_GAP - STRIP_H):
    """Şerit hücresinin merkez pikseli."""
    return game.screen.get_at((OX + col * CELL + 1 + (CELL - 2) // 2, strip_y + STRIP_H // 2))[:3]


# --------------------------------------------------------------------------
# (a) / (b) Dolu gizli hücre çizer, boş gizli satır hiçbir şey çizmez
# --------------------------------------------------------------------------

@pytest.mark.quadrix_phase6b
def test_occupied_hidden_cell_renders_visible_strip():
    game = _make_game(hidden_cells=[(1, 3)])
    reference = _strip_pixel(game, col=0)  # boş sütun: arka plan
    occupied = _strip_pixel(game, col=3)
    assert occupied != reference, 'dolu gizli sütun şerit çizmeli (piksel arka plandan farklı)'


@pytest.mark.quadrix_phase6b
def test_strip_pixel_is_between_block_color_and_background():
    """%55 alfa: sonuç ne saf blok rengi ne saf arka plan olmalı (gerçekten yarı saydam)."""
    game = _make_game(hidden_cells=[(1, 3)])
    background = _strip_pixel(game, col=0)
    occupied = _strip_pixel(game, col=3)
    for channel, (bg, fg) in enumerate(zip(background, STRIP_COLOR)):
        low, high = min(bg, fg), max(bg, fg)
        assert low - 2 <= occupied[channel] <= high + 2, (
            f'kanal {channel}: şerit pikseli blok ({fg}) ile arka plan ({bg}) arasında olmalı, '
            f'bulunan {occupied[channel]}'
        )
    assert occupied != tuple(STRIP_COLOR), 'alfa uygulanmamış — saf blok rengi görünüyor'


@pytest.mark.quadrix_phase6b
def test_empty_hidden_rows_render_nothing():
    game = _make_game(hidden_cells=[])
    background = _strip_pixel(game, col=0)
    for col in range(BOARD_W):
        assert _strip_pixel(game, col) == background, f'boş gizli satır sütun {col} çizmemeli'


@pytest.mark.quadrix_phase6b
def test_strip_alpha_is_the_approved_55_percent():
    game = _make_game(hidden_cells=[])
    surface = game._get_solid_alpha_surface(
        (CELL - 2, STRIP_H), (*STRIP_COLOR, HIDDEN_STRIP_ALPHA)
    )
    assert surface.get_at((0, 0))[3] == HIDDEN_STRIP_ALPHA
    assert 138 <= HIDDEN_STRIP_ALPHA <= 141, 'onaylı %55 alfa (0.55*255≈140)'


@pytest.mark.quadrix_phase6b
def test_lower_hidden_row_color_wins_is_documented_and_rendered():
    """Alt gizli satır görünür tahtaya daha yakın; iki satır tek bantta birleşir."""
    game = _make_game(hidden_cells=[])
    game.board.hidden_occupancy[1][4] = True
    game.board.hidden_grid[1][4] = (10, 200, 30)
    game.board.hidden_occupancy[0][4] = True
    game.board.hidden_grid[0][4] = (250, 250, 0)
    game._draw_hidden_row_strip(OX, OY, CELL)
    colors = [key[2] for key in game._solid_alpha_surface_cache]
    assert (10, 200, 30, HIDDEN_STRIP_ALPHA) in colors, 'alt satırın rengi kullanılmalı'
    assert (250, 250, 0, HIDDEN_STRIP_ALPHA) not in colors, 'üst satır rengi baskın olmamalı'


# --------------------------------------------------------------------------
# (c) show_ghost ayarından bağımsız
# --------------------------------------------------------------------------

@pytest.mark.quadrix_phase6b
@pytest.mark.parametrize('show_ghost', [True, False])
def test_strip_is_independent_of_show_ghost(show_ghost):
    game = _make_game(hidden_cells=[(1, 2)], show_ghost=show_ghost)
    reference = _strip_pixel(game, col=0)
    assert _strip_pixel(game, col=2) != reference, (
        f'show_ghost={show_ghost}: şerit ayardan bağımsız görünmeli'
    )


# --------------------------------------------------------------------------
# (d) Kare başına tahsis yok — iki çizim Surface sayısını artırmaz
# --------------------------------------------------------------------------

@pytest.mark.quadrix_phase6b
def test_second_draw_does_not_allocate_new_surfaces():
    game = _make_game(hidden_cells=[(0, 1), (1, 1), (0, 7)])
    first = len(game._solid_alpha_surface_cache)
    assert first == 1, 'üç sütun da aynı rengi kullanıyor → tek cache girdisi'
    game._draw_hidden_row_strip(OX, OY, CELL)
    game._draw_hidden_row_strip(OX, OY, CELL)
    assert len(game._solid_alpha_surface_cache) == first, (
        'tekrarlanan çizim yeni Surface üretmemeli (LRU cache + kuantize alfa)'
    )


@pytest.mark.quadrix_phase6b
def test_strip_alpha_is_quantized_not_float():
    """Kuantize alfa cache anahtarını sabitler; float alfa her karede yeni key üretirdi."""
    assert isinstance(HIDDEN_STRIP_ALPHA, int)
    game = _make_game(hidden_cells=[(0, 0)])
    assert game._solid_alpha_surface_cache, 'şerit çizildiyse cache dolu olmalı'
    for key in game._solid_alpha_surface_cache:
        assert isinstance(key[2][3], int), 'alfa int olmalı'


@pytest.mark.quadrix_phase6b
def test_board_grid_cache_still_reused_across_frames():
    """Şerit eklenirken mevcut grid cache sözleşmesi bozulmamalı."""
    game = _make_game(hidden_cells=[(0, 0)])
    cached = game._board_grid_cache.get('surface')
    assert cached is not None
    _original_tint = game_module.apply_board_tint
    _original_overlay = game_module.draw_board_overlay
    game_module.apply_board_tint = lambda *a, **k: None
    game_module.draw_board_overlay = lambda *a, **k: None
    try:
        game._draw_base_scene()
    finally:
        game_module.apply_board_tint = _original_tint
        game_module.draw_board_overlay = _original_overlay
    assert game._board_grid_cache.get('surface') is cached, 'grid cache yeniden üretilmemeli'


# --------------------------------------------------------------------------
# (e) Yerleşim: şerit bandı tahtanın üstünde, HUD hizalı, hiçbir şey taşmıyor
# --------------------------------------------------------------------------

UI_PRESETS = (1.00, 1.75, 2.00)
RESOLUTIONS = ((640, 360), (1280, 720), (1920, 1080))


def _layout(width, height):
    return compute_single_player_layout(
        active_size=(width, height),
        effective_size=(width, height),
        board_width=BOARD_W,
        board_height=BOARD_H,
        info_panel_height=120,
    )


@pytest.mark.quadrix_phase6b
@pytest.mark.parametrize('width,height', RESOLUTIONS)
def test_layout_reserves_strip_headroom_above_board(width, height):
    m = _layout(width, height)
    assert m.hidden_strip_height > 0
    assert m.hidden_strip_gap > 0
    strip_top = m.board_y - m.hidden_strip_gap - m.hidden_strip_height
    assert strip_top >= 0, f'{width}x{height}: şerit ekranın üstünde kalmalı (top={strip_top})'


@pytest.mark.quadrix_phase6b
@pytest.mark.parametrize('width,height', RESOLUTIONS)
def test_layout_shift_does_not_overflow_bottom(width, height):
    m = _layout(width, height)
    assert m.board_y + m.board_height <= height, 'tahta ekrandan taşmamalı'
    assert m.panel_y + m.panel_height <= height, 'HUD ekrandan taşmamalı'


@pytest.mark.quadrix_phase6b
@pytest.mark.parametrize('width,height', RESOLUTIONS)
def test_hud_stays_aligned_with_board_after_shift(width, height):
    """S-21: tahta + HUD tek grup kayar; panel_y - board_y sabit kalır."""
    m = _layout(width, height)
    assert m.panel_y - m.board_y >= 0
    assert m.panel_y - m.board_y < m.cell_size * 2, 'HUD tahtanın çok altına düşmemeli'


@pytest.mark.quadrix_phase6b
@pytest.mark.parametrize('preset', UI_PRESETS)
def test_strip_geometry_holds_across_ui_presets(preset):
    for (width, height) in RESOLUTIONS:
        active_w = int(round(width * preset))
        active_h = int(round(height * preset))
        m = compute_single_player_layout(
            active_size=(active_w, active_h),
            effective_size=(width, height),
            board_width=BOARD_W,
            board_height=BOARD_H,
            info_panel_height=120,
        )
        strip_top = m.board_y - m.hidden_strip_gap - m.hidden_strip_height
        assert strip_top >= 0, f'preset={preset} {width}x{height}: şerit üstten taşıyor'
        assert m.board_y + m.board_height <= active_h
        assert m.panel_y + m.panel_height <= active_h
        assert m.hidden_strip_height == max(
            1, int(round(m.cell_size * HIDDEN_STRIP_CELL_RATIO))
        )


@pytest.mark.quadrix_phase6b
def test_strip_band_sits_entirely_above_board_body():
    """Şerit bandı + boşluk tahtanın üstünde biter; tahta gövdesine binmez."""
    for (width, height) in RESOLUTIONS:
        m = _layout(width, height)
        assert m.board_y - m.hidden_strip_gap - m.hidden_strip_height < m.board_y
        assert m.hidden_strip_gap > 0, 'bant tahta çerçevesine yapışmamalı'