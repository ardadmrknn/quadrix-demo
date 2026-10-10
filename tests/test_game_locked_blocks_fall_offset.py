# -*- coding: utf-8 -*-
"""OP-014 (D3) — kilitli blok çizim yolunda düşme offset'i dict erişimi.

Kapsam kovuğu dersi (C2/C3): `_draw_base_scene` içindeki kilitli-blok döngüsü
hiçbir mevcut testle sürülmüyordu (`test_game_line_clear_fall_animation.py`
yalnız `_start_block_fall_animation` veri üretimini test eder; skin testleri
`draw_textured_block`'u doğrudan çağırır). Bu smoke test gerçek draw yolunu
sürer: `Game.__new__` + metrik enjeksiyonu (duz010/p0 deseni, set_mode yok)
ile `_draw_base_scene` çağrılır ve `draw_textured_block`'a iletilen koordinatlar
doğrulanır.

Sözleşme (değişiklik öncesiyle birebir — `_get_block_fall_offset` semantiği):
  1. Animasyonlu hücre: block_y = offset_y + row*cell + 1 + current_offset.
  2. Animasyonsuz dolu hücre: offset 0.
  3. Yinelenen (row, col) animasyonlarında İLK eşleşme kazanır (lineer tarama
     semantiği — dict kurulumu da ilk değeri korur).
  4. Boş animasyon listesi: çizim yolunda hata yok, tüm offsetler 0.
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

import game as game_module
from game import Game

CELL = 30
OX, OY = 100, 60
BOARD_W, BOARD_H = 10, 20
BLOCK_COLOR = (90, 90, 120)


def _make_game(occupancy_cells, animations):
    """Game.__new__ + draw-yolu enjeksiyonu; screen offscreen Surface.

    apply_board_tint / draw_board_overlay no-op'lanır: ikisi de
    `.convert_alpha()` çağırır (display formatı ister — set_mode'suz koşumda
    hata). Bu test koordinat sözleşmesini doğrular, tint/overlay piksellerini
    değil; blit yolu zaten duz010/p0 desenlerinde kapsanıyor.
    """
    pygame.init()
    if not pygame.display.get_init():
        pygame.display.init()
    game = Game.__new__(Game)
    game.screen = pygame.Surface((640, 720))
    game.game_mode = 'classic'
    game.mode_skin = None
    game.effects_enabled = False
    game.game_over = True  # parça/ghost yolları kapalı; kilitli bloklar bağımsız
    game.current_piece = None
    game.outer_background = types.SimpleNamespace(is_loaded=lambda: False)
    game.get_shake_offset = lambda: (0, 0)
    game.get_cell_size = lambda: CELL
    game.get_board_offset = lambda: (OX, OY)
    game.board_width = BOARD_W
    game.board_height = BOARD_H
    occupancy = [[False] * BOARD_W for _ in range(BOARD_H)]
    grid = [[None] * BOARD_W for _ in range(BOARD_H)]
    for (row, col) in occupancy_cells:
        occupancy[row][col] = True
        grid[row][col] = BLOCK_COLOR
    game.board = types.SimpleNamespace(
        width=BOARD_W,
        height=BOARD_H,
        grid=grid,
        occupancy=occupancy,
        texture_grid=[[None] * BOARD_W for _ in range(BOARD_H)],
        last_cleared_lines=[],
        flexible_border_active=False,
    )
    game._board_grid_cache = {}
    game.line_clear_flash = False
    game.falling_block_animations = animations
    game.block_style_manager = None
    game.draw_board_background = lambda *a, **k: None
    game._draw_custom_frame = lambda *a, **k: False
    game._draw_right_hud_panel = lambda *a, **k: None
    game._draw_base_scene_effects = lambda *a, **k: None

    draw_calls = []
    game.draw_textured_block = (
        lambda x, y, size, color, texture_surface=None, texture_slice=None:
            draw_calls.append((x, y, size, color))
    )
    # convert_alpha display formatı ister; bu testte tint/overlay pikselleri
    # kapsam dışı — no-op stub (test_block_skin_rendering restore deseni).
    _original_tint = game_module.apply_board_tint
    _original_overlay = game_module.draw_board_overlay
    game_module.apply_board_tint = lambda *a, **k: None
    game_module.draw_board_overlay = lambda *a, **k: None
    try:
        game._draw_base_scene()
    finally:
        game_module.apply_board_tint = _original_tint
        game_module.draw_board_overlay = _original_overlay
    return game, draw_calls


def _anim(row, col, offset):
    return {
        'row': row,
        'col': col,
        'current_offset': float(offset),
        'target_offset': 0.0,
        'sweep_trigger': 1.0,
        'started': False,
    }


def test_animated_and_plain_cells_apply_expected_offsets():
    cells = [(5, 2), (5, 3), (6, 0)]
    anims = [_anim(5, 2, -37.5), _anim(6, 0, -15.0)]
    game, draw_calls = _make_game(cells, anims)

    assert len(draw_calls) == len(cells), "her dolu hücre tam bir blok çizmeli"
    positions = {(x, y) for (x, y, _s, _c) in draw_calls}
    expected = {
        (OX + 2 * CELL + 1, OY + 5 * CELL + 1 - 37.5),
        (OX + 3 * CELL + 1, OY + 5 * CELL + 1),
        (OX + 0 * CELL + 1, OY + 6 * CELL + 1 - 15.0),
    }
    assert positions == expected, f"offset konumları sapmış: {positions ^ expected}"
    # Metot denkliği: dokunulmamış _get_block_fall_offset ile birebir.
    for (row, col) in cells:
        expected_y = OY + row * CELL + 1 + game._get_block_fall_offset(row, col)
        drawn = [y for (x, y) in positions if x == OX + col * CELL + 1]
        assert drawn == [expected_y], (row, col)


def test_duplicate_animation_keeps_first_match_semantics():
    # Lineer tarama İLK eşleşmeyi döndürür; dict kurulumu da ilk değeri korumalı.
    cells = [(7, 4)]
    anims = [_anim(7, 4, -25.0), _anim(7, 4, -99.0)]
    game, draw_calls = _make_game(cells, anims)

    assert len(draw_calls) == 1
    _x, y, _s, _c = draw_calls[0]
    first_match = game._get_block_fall_offset(7, 4)
    assert first_match == -25.0
    assert y == OY + 7 * CELL + 1 - 25.0


def test_empty_animation_list_draws_without_error_and_zero_offset():
    cells = [(10, 1), (11, 9)]
    game, draw_calls = _make_game(cells, [])

    assert len(draw_calls) == len(cells)
    for _x, y, _s, _c in draw_calls:
        row = int((y - 1 - OY) // CELL)
        assert y == OY + row * CELL + 1, "boş animasyon listesinde offset 0 olmalı"
