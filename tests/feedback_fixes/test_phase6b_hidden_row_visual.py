# -*- coding: utf-8 -*-
"""Faz 6b / I-46 — Gizli satırlar GERÇEK blok olarak görünür (TGM/tetr.io buffer).

Kök neden: `Board` iki gizli satırı (`hidden_occupancy`/`hidden_grid`) doğru
yönetiyordu ama görünür alanın üstüne taşan bu hücreler HİÇBİR ZAMAN
çizilmiyordu — oyuncu tehlikeyi ancak lock-out anında görüyordu.

Onaylı tasarım (S-21 v2, kullanıcı kararı):
  * Tahta 20 görünür + 2 gizli = 22 satır yüksekliğinde yerleşir.
  * Gizli satırlar gölge/şerit DEĞİL: aynı doku, aynı renk, aynı boy, tam
    opak normal bloklar — yalnızca arka plan ve ızgara çizilmez (bloklar boş
    arka plan üzerinde "havada" durur).
  * Görünür 20 satırın arka planı/ızgarası BİREBİR eskisi gibi kalır.
  * Hücre boyu toplam 22 satıra bölünür; tahta ekran dışına taşmaz, gerekirse
    hücre küçülür (720p 27, 1080p 43 …).
  * HUD görünür alanın üstüne hizalı kalır.

Kanıt yöntemi: `_BlitSpy` yerine GERÇEK piksel sondası — blit çağrısı saymak
"çağrıldı ama görünmüyor" durumunu kaçırır; bu test bloğun ekranda gerçekten
göründüğünü ve görünür alanın ızgarasının bozulmadığını doğrular.
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
from game import Game  # noqa: E402
from constants import BLACK  # noqa: E402
from gameplay_layout import (  # noqa: E402
    HIDDEN_ROWS,
    compute_single_player_layout,
    total_board_rows,
)

pytestmark = pytest.mark.quadrix_feedback

CELL = 30
OX, OY = 200, 300  # OY = GÖRÜNÜR alanın tepesi; gizli bant bunun üstünde
BOARD_W, BOARD_H = 10, 20
HIDDEN_BAND_TOP = OY - HIDDEN_ROWS * CELL
BLOCK_COLOR = (200, 90, 60)
VISIBLE_BG = (4, 4, 12)


def _blank_grid(rows, cols, fill=BLACK):
    return [[fill for _ in range(cols)] for _ in range(rows)]


def _blank_flags(rows, cols):
    return [[False for _ in range(cols)] for _ in range(rows)]


def _draw(game):
    _original_tint = game_module.apply_board_tint
    _original_overlay = game_module.draw_board_overlay
    game_module.apply_board_tint = lambda *a, **k: None
    game_module.draw_board_overlay = lambda *a, **k: None
    try:
        game._draw_base_scene()
    finally:
        game_module.apply_board_tint = _original_tint
        game_module.draw_board_overlay = _original_overlay


def _make_game(hidden_cells, hidden_rows=HIDDEN_ROWS, show_ghost=True,
               current_piece=None, board_rows=BOARD_H):
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
    game.current_piece = current_piece
    game.outer_background = types.SimpleNamespace(is_loaded=lambda: False)
    game.single_background = types.SimpleNamespace(is_loaded=lambda: False)
    game.background_manager = types.SimpleNamespace()
    game.settings_manager = types.SimpleNamespace(get=lambda k, d=None: show_ghost)
    game.grounded = False
    game.lock_timer = 0
    game.lock_delay = 500
    game.ground_lock_timer = 0
    game.get_shake_offset = lambda: (0, 0)
    game.get_cell_size = lambda: CELL
    game.get_board_offset = lambda: (OX, OY)
    game.board_width = BOARD_W
    game.board_height = board_rows
    # Layout'u instance düzeyinde sabitle: `_get_gameplay_layout_metrics`
    # gerçek ekran boyutundan yeniden hesaplarsa enjekte edilen cell/offset ile
    # bant yüksekliği birbirinden kopar (test ölçtüğü sözleşmeyi kaybeder).
    game._get_gameplay_layout_metrics = lambda: types.SimpleNamespace(
        cell_size=CELL,
        board_y=HIDDEN_BAND_TOP,
        visible_top_y=OY,
        hidden_rows=hidden_rows,
    )

    hidden_occ = _blank_flags(hidden_rows, BOARD_W)
    hidden_grid = _blank_grid(hidden_rows, BOARD_W, fill=BLACK)
    for (row, col) in hidden_cells:
        hidden_occ[row][col] = True
        hidden_grid[row][col] = BLOCK_COLOR

    game.board = types.SimpleNamespace(
        width=BOARD_W,
        height=board_rows,
        hidden_rows=hidden_rows,
        grid=_blank_grid(board_rows, BOARD_W, fill=VISIBLE_BG),
        occupancy=_blank_flags(board_rows, BOARD_W),
        texture_grid=[[None for _ in range(BOARD_W)] for _ in range(board_rows)],
        hidden_occupancy=hidden_occ,
        hidden_grid=hidden_grid,
        hidden_texture_grid=[[None for _ in range(BOARD_W)] for _ in range(hidden_rows)],
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
    game.block_appearance = None
    game._texture_render_cache = types.SimpleNamespace(
        render_slice=lambda *a, **k: None,
        get_rotated_surface=lambda s, r: s,
    )
    game.draw_board_background = lambda *a, **k: None
    game._draw_custom_frame = lambda *a, **k: False
    game._draw_right_hud_panel = lambda *a, **k: None
    game._draw_base_scene_effects = lambda *a, **k: None

    _draw(game)
    return game


def _cell_center(col, row_in_band):
    """Gizli banttaki bir hücrenin merkez pikseli (row_in_band: 0 = en üst)."""
    return (
        OX + col * CELL + 1 + (CELL - 2) // 2,
        HIDDEN_BAND_TOP + row_in_band * CELL + 1 + (CELL - 2) // 2,
    )


def _pixel(game, point):
    return game.screen.get_at(point)[:3]


# --------------------------------------------------------------------------
# (a) Gizli satırda GERÇEK, tam opak blok çizilir
# --------------------------------------------------------------------------

@pytest.mark.quadrix_phase6b
def test_hidden_cell_renders_an_actual_block_not_a_shadow():
    game = _make_game(hidden_cells=[(1, 3)])
    occupied = _pixel(game, _cell_center(3, 1))
    bg = _pixel(game, _cell_center(0, 1))
    assert occupied != bg, 'dolu gizli hücre çizilmeli'
    assert any(abs(o - b) > 40 for o, b in zip(occupied, bg)), (
        f'blok arka plandan ayırt edilebilir olmalı (blok={occupied}, arka plan={bg})'
    )


@pytest.mark.quadrix_phase6b
def test_hidden_block_is_opaque_not_translucent():
    """Eski tasarımın %55 alfa şeridi yerine TAM OPAK blok beklenir."""
    game = _make_game(hidden_cells=[(0, 5)])
    px = _pixel(game, _cell_center(5, 0))
    bg = _pixel(game, _cell_center(0, 0))
    mixed = tuple(int(b + (f - b) * 0.55) for b, f in zip(bg, BLOCK_COLOR))
    assert px != mixed, 'blok %55 alfalı karışım olmamalı — tam opak çizilmeli'
    assert px[0] > max(bg[0], mixed[0]), (
        f'tam opak blokta kanal değeri karışımdan yüksek olmalı ({px} vs {mixed})'
    )


@pytest.mark.quadrix_phase6b
def test_both_hidden_rows_are_independently_rendered():
    game = _make_game(hidden_cells=[(0, 2), (1, 6)])
    assert _pixel(game, _cell_center(2, 0)) != _pixel(game, _cell_center(2, 1)), (
        'iki gizli satır ayrı ayrı çizilmeli (alt satır üst satıra binmemeli)'
    )
    assert _pixel(game, _cell_center(6, 1)) != _pixel(game, _cell_center(6, 0))


@pytest.mark.quadrix_phase6b
def test_empty_hidden_rows_render_nothing():
    game = _make_game(hidden_cells=[])
    reference = _pixel(game, _cell_center(0, 0))
    for col in range(BOARD_W):
        for row in range(HIDDEN_ROWS):
            assert _pixel(game, _cell_center(col, row)) == reference, (
                f'boş gizli hücre ({row},{col}) çizmemeli'
            )


# --------------------------------------------------------------------------
# (b) Görünür 20 satırın arka planı/ızgarası KORUNUR, gizli bantta ızgara YOK
# --------------------------------------------------------------------------

@pytest.mark.quadrix_phase6b
def test_visible_board_grid_is_still_drawn():
    game = _make_game(hidden_cells=[])
    grid_px = game.screen.get_at((OX, OY + CELL))[:3]
    cell_px = game.screen.get_at((OX + CELL // 2, OY + 3 * CELL))[:3]
    assert grid_px != cell_px, 'görünür alanda ızgara korunmalı'


@pytest.mark.quadrix_phase6b
def test_hidden_band_has_no_grid_lines():
    """TGM/tetr.io buffer: bloklar ızgarasız/arka plansız bantta durur."""
    game = _make_game(hidden_cells=[])
    for row in range(HIDDEN_ROWS):
        grid_line_y = HIDDEN_BAND_TOP + row * CELL
        on_line = game.screen.get_at((OX, grid_line_y))[:3]
        inside = game.screen.get_at((OX + CELL * 3 + CELL // 2, grid_line_y + 3))[:3]
        assert on_line == inside, (
            f'gizli bantta ızgara çizilmemeli (satır {row}: {on_line} vs {inside})'
        )


@pytest.mark.quadrix_phase6b
def test_visible_board_background_starts_below_hidden_band():
    """Tahta arka planı görünür alanın tepesinden başlar; bant ayrı kalır."""
    game = _make_game(hidden_cells=[])
    above = _pixel(game, (OX + BOARD_W * CELL // 2, HIDDEN_BAND_TOP + CELL // 2))
    below = _pixel(game, (OX + BOARD_W * CELL // 2, OY + BOARD_H * CELL // 2))
    assert above != below, 'gizli bant ile görünür alan arka planı aynı olmamalı'


# --------------------------------------------------------------------------
# (c) Aktif parça ve ghost, gizli bantta da görünür
# --------------------------------------------------------------------------

class _FakePiece:
    def __init__(self, x, y, shape):
        self.x = x
        self.y = y
        self.shape = shape
        self.color = BLOCK_COLOR
        self.color_matrix = None
        self.texture_surface = None
        self.name = 'T'
        self.piece_type = 'T'

    def get_cells(self):
        for ly, row in enumerate(self.shape):
            for lx, cell in enumerate(row):
                if cell:
                    yield self.x + lx, self.y + ly


@pytest.mark.quadrix_phase6b
def test_active_piece_is_drawn_inside_hidden_band():
    piece = _FakePiece(3, -1, [[1, 1, 1], [0, 1, 0]])
    game = _make_game(hidden_cells=[], current_piece=piece)
    game.game_over = False
    _draw(game)
    occupied = _pixel(game, _cell_center(4, HIDDEN_ROWS - 1))
    background = _pixel(game, _cell_center(0, HIDDEN_ROWS - 1))
    assert occupied != background, 'gizli bantta duran aktif parça normal blok olarak görünmeli'


@pytest.mark.quadrix_phase6b
def test_active_piece_above_hidden_band_is_clipped():
    """Bandın üstüne taşan hücreler çizilmez (ekran dışı çöp olmasın)."""
    piece = _FakePiece(3, -4, [[1]])
    game = _make_game(hidden_cells=[], current_piece=piece)
    game.game_over = False
    before = game.screen.copy()
    _draw(game)
    probe = (OX + 3 * CELL + 1 + (CELL - 2) // 2, HIDDEN_BAND_TOP - CELL + 5)
    assert game.screen.get_at(probe)[:3] == before.get_at(probe)[:3]


@pytest.mark.quadrix_phase6b
@pytest.mark.parametrize('show_ghost', [True, False])
def test_hidden_rows_are_independent_of_show_ghost(show_ghost):
    game = _make_game(hidden_cells=[(1, 2)], show_ghost=show_ghost)
    reference = _pixel(game, _cell_center(0, 1))
    assert _pixel(game, _cell_center(2, 1)) != reference, (
        f'show_ghost={show_ghost}: kilitli gizli blok ayardan bağımsız görünmeli'
    )


# --------------------------------------------------------------------------
# (d) Kare başına tahsis yok / cache sözleşmeleri korunur
# --------------------------------------------------------------------------

@pytest.mark.quadrix_phase6b
def test_repeated_draw_does_not_grow_caches():
    game = _make_game(hidden_cells=[(0, 1), (1, 1), (0, 7)])
    cache_size = len(game._solid_alpha_surface_cache)
    grid_surface = game._board_grid_cache.get('surface')
    for _ in range(3):
        _draw(game)
    assert len(game._solid_alpha_surface_cache) == cache_size, (
        'tekrarlanan çizim yeni Surface üretmemeli'
    )
    assert game._board_grid_cache.get('surface') is grid_surface, (
        'grid cache yeniden üretilmemeli'
    )


@pytest.mark.quadrix_phase6b
def test_board_grid_cache_key_excludes_hidden_rows():
    """Izgara yalnız görünür alanı kapsar; gizli satır eklemek cache'i bozmaz."""
    game = _make_game(hidden_cells=[(0, 0)])
    key = game._board_grid_cache.get('key')
    assert key is not None
    assert key[2] == BOARD_W and key[3] == BOARD_H, (
        f'ızgara boyutu görünür tahtayla sınırlı olmalı, bulunan {key}'
    )


# --------------------------------------------------------------------------
# (e) Yerleşim: 22 satır, taşma yok, HUD görünür alana hizalı
# --------------------------------------------------------------------------

RESOLUTIONS = (
    (640, 360), (1280, 720), (1366, 768), (1920, 1080), (2560, 1440), (3840, 2160),
)


def _layout(width, height, hidden_rows=HIDDEN_ROWS):
    return compute_single_player_layout(
        active_size=(width, height),
        effective_size=(width, height),
        board_width=BOARD_W,
        board_height=BOARD_H,
        info_panel_height=120,
        hidden_rows=hidden_rows,
    )


@pytest.mark.quadrix_phase6b
def test_total_board_rows_includes_hidden_buffer():
    assert total_board_rows(20, 2) == 22
    assert total_board_rows(20, 0) == 20


@pytest.mark.quadrix_phase6b
@pytest.mark.parametrize('width,height', RESOLUTIONS)
def test_layout_places_hidden_band_above_visible_area(width, height):
    m = _layout(width, height)
    assert m.hidden_rows == HIDDEN_ROWS
    expected_shift = HIDDEN_ROWS * m.cell_size
    assert m.visible_top_y - m.board_y == expected_shift, (
        f'{width}x{height}: görünür alan gizli bant kadar aşağıda olmalı'
    )
    assert m.board_y >= 0, f'{width}x{height}: gizli bant ekranın üstünde kalmamalı'


@pytest.mark.quadrix_phase6b
@pytest.mark.parametrize('width,height', RESOLUTIONS)
def test_layout_never_overflows_screen(width, height):
    m = _layout(width, height)
    assert m.visible_top_y + m.board_height <= height, 'görünür tahta ekrandan taşmamalı'
    assert m.panel_y + m.panel_height <= height, 'HUD ekrandan taşmamalı'


@pytest.mark.quadrix_phase6b
@pytest.mark.parametrize('width,height', RESOLUTIONS)
def test_cell_size_matches_total_row_budget(width, height):
    """Hücre boyu 22 satıra bölünür — 20 satırlık eski bütçe kullanılamaz."""
    m = _layout(width, height)
    budget_20 = _layout(width, height, hidden_rows=0).cell_size
    assert m.cell_size <= budget_20, '22 satırlık bütçe hücreyi büyütemez'


@pytest.mark.quadrix_phase6b
def test_cell_shrink_table_is_stable():
    """Belgelenmiş hücre tablosu: 720p 27, 768p 29, 1080p 43, 1440p 52, 2160p 56."""
    expected = {
        (1280, 720): 27,
        (1366, 768): 29,
        (1920, 1080): 43,
        (2560, 1440): 52,
        (3840, 2160): 56,
    }
    for (width, height), cell in expected.items():
        assert _layout(width, height).cell_size == cell, f'{width}x{height} hücre boyu'


@pytest.mark.quadrix_phase6b
@pytest.mark.parametrize('preset', (1.00, 1.75, 2.00))
@pytest.mark.parametrize('width,height', RESOLUTIONS)
def test_geometry_holds_across_ui_presets(width, height, preset):
    active_w = int(round(width * preset))
    active_h = int(round(height * preset))
    m = compute_single_player_layout(
        active_size=(active_w, active_h),
        effective_size=(width, height),
        board_width=BOARD_W,
        board_height=BOARD_H,
        info_panel_height=120,
        hidden_rows=HIDDEN_ROWS,
    )
    assert m.board_y >= 0
    assert m.visible_top_y + m.board_height <= active_h
    assert m.panel_y + m.panel_height <= active_h
    assert m.visible_top_y - m.board_y == HIDDEN_ROWS * m.cell_size


@pytest.mark.quadrix_phase6b
def test_hud_stays_anchored_to_board_top():
    """Kullanıcı kararı "üst hizalı kalsın": panel toplam bloğun tepesine hizalı."""
    for (width, height) in RESOLUTIONS:
        m = _layout(width, height)
        assert m.panel_y - m.board_y >= 0
        assert m.panel_y - m.board_y < m.cell_size * 2, (
            f'{width}x{height}: HUD tahtanın çok altına düşmemeli'
        )


@pytest.mark.quadrix_phase6b
def test_zero_hidden_rows_reproduces_legacy_geometry():
    """Gizli satır yoksa yerleşim eski (20 satır) davranışa döner."""
    legacy = _layout(1920, 1080, hidden_rows=0)
    assert legacy.hidden_rows == 0
    assert legacy.visible_top_y == legacy.board_y