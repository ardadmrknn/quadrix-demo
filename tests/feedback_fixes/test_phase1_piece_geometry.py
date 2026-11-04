"""Faz 1: bağımsız Guideline SRS ve parça yerleşimi sözleşmeleri."""

import copy

import pytest

from board import Board
from game import Game
from pieces import SRS_KICKS_I, create_piece_by_name


pytestmark = [pytest.mark.quadrix_feedback, pytest.mark.quadrix_phase1]


# TetrisWiki SRS tablosu (pozitif y yukarı) Pygame'in y-aşağı eksenine çevrildi.
# Kaynak: https://tetris.wiki/SRS (erişim: 2026-11-04), I tablosu.
GUIDELINE_I_KICKS_Y_DOWN = {
    (0, 1): [(0, 0), (-2, 0), (1, 0), (-2, 1), (1, -2)],
    (1, 0): [(0, 0), (2, 0), (-1, 0), (2, -1), (-1, 2)],
    (1, 2): [(0, 0), (-1, 0), (2, 0), (-1, -2), (2, 1)],
    (2, 1): [(0, 0), (1, 0), (-2, 0), (1, 2), (-2, -1)],
    (2, 3): [(0, 0), (2, 0), (-1, 0), (2, -1), (-1, 2)],
    (3, 2): [(0, 0), (-2, 0), (1, 0), (-2, 1), (1, -2)],
    (3, 0): [(0, 0), (1, 0), (-2, 0), (1, 2), (-2, -1)],
    (0, 3): [(0, 0), (-1, 0), (2, 0), (-1, -2), (2, 1)],
}


def test_i_piece_90_degree_kicks_match_independent_guideline_fixture():
    assert SRS_KICKS_I == GUIDELINE_I_KICKS_Y_DOWN
    assert all(vectors[0] == (0, 0) for vectors in SRS_KICKS_I.values())
    assert all(len(vectors) == 5 for vectors in SRS_KICKS_I.values())


@pytest.mark.parametrize("name, expected_columns", [
    ("I", {3, 4, 5, 6}),
    ("O", {4, 5}),
    ("T", {3, 4, 5}),
    ("S", {3, 4, 5}),
    ("Z", {3, 4, 5}),
    ("J", {3, 4, 5}),
    ("L", {3, 4, 5}),
])
def test_spawn_columns_use_guideline_centres(name, expected_columns):
    game = Game.__new__(Game)
    game.board_width = 10
    game.board = Board(width=10, height=40)
    piece = create_piece_by_name(name)

    game._position_piece_at_spawn(piece)

    assert {x for x, _ in piece.get_cells()} == expected_columns


def test_hold_orientation_reset_helper_returns_piece_to_spawn_state():
    piece = create_piece_by_name("T")
    piece.rotate(1)
    assert piece.rotation_state == 1

    Game._reset_piece_orientation(piece)

    assert piece.rotation_state == 0
    assert piece.shape == create_piece_by_name("T").shape


def test_empty_board_cw_then_ccw_has_no_i_piece_position_drift():
    board = Board(width=10, height=20)
    piece = create_piece_by_name("I", x=3, y=5)
    original = (piece.x, piece.y, copy.deepcopy(piece.shape))

    assert piece.try_rotate_srs(board, 1)
    assert piece.try_rotate_srs(board, -1)

    assert (piece.x, piece.y, piece.shape) == original


def test_empty_board_180_rotation_uses_reference_zero_test_before_kicks():
    # The first vector is the raw-matrix pivot correction for TETR.IO kick-0.
    from pieces import SRS_KICKS_180_I

    assert SRS_KICKS_180_I
    assert all(len(vectors) == 6 for vectors in SRS_KICKS_180_I.values())
    assert [SRS_KICKS_180_I[key][0] for key in sorted(SRS_KICKS_180_I)] == [
        (0, -1), (1, 0), (0, 1), (-1, 0)
    ]


def test_empty_board_i_180_has_no_extra_kick_drift_on_empty_board():
    board = Board(width=10, height=20)
    piece = create_piece_by_name("I", x=3, y=5)
    original_cells = set(piece.get_cells())

    assert piece.try_rotate_180(board)

    assert set(piece.get_cells()) == original_cells
