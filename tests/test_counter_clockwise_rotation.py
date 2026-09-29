from __future__ import annotations

import copy
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from board import Board  # noqa: E402
from pieces import Piece, create_piece_by_name  # noqa: E402


def test_t_piece_ccw_open_field_transitions_to_state_three():
    board = Board(width=10, height=20)
    piece = create_piece_by_name('T', x=3, y=4)

    assert piece.try_rotate_srs(board, -1) is True
    assert piece.rotation_state == 3
    assert board.is_valid_position(piece)


def test_four_ccw_rotations_restore_shape_and_state():
    board = Board(width=10, height=20)
    piece = create_piece_by_name('T', x=3, y=4)
    original_shape = copy.deepcopy(piece.shape)

    for _ in range(4):
        assert piece.try_rotate_srs(board, -1) is True

    assert piece.rotation_state == 0
    assert piece.shape == original_shape


def test_cw_then_ccw_round_trip_restores_piece():
    board = Board(width=10, height=20)
    piece = create_piece_by_name('L', x=3, y=4)
    original = (piece.x, piece.y, piece.rotation_state, copy.deepcopy(piece.shape))

    assert piece.try_rotate_srs(board, 1) is True
    assert piece.try_rotate_srs(board, -1) is True

    assert (piece.x, piece.y, piece.rotation_state, piece.shape) == original


def test_normal_piece_ccw_uses_second_zero_to_three_kick():
    board = Board(width=10, height=20)
    piece = create_piece_by_name('T', x=-1, y=4)

    assert piece.try_rotate_srs(board, -1) is True
    assert piece.rotation_state == 3
    assert piece.x == 0
    assert piece.last_kick_index == 1


def test_i_piece_ccw_uses_i_specific_zero_to_three_kick():
    board = Board(width=10, height=20)
    piece = create_piece_by_name('I', x=-3, y=4)

    assert piece.try_rotate_srs(board, -1) is True
    assert piece.rotation_state == 3
    assert piece.x == -1
    assert piece.last_kick_index == 2


def test_failed_ccw_rotation_fully_rolls_back_shape_position_state_and_colors():
    board = Board(width=10, height=20)
    piece = create_piece_by_name('T', x=3, y=5)
    piece.color_matrix = [
        [None, 'a', None],
        ['b', 'c', 'd'],
        [None, None, None],
    ]
    original = (
        piece.x,
        piece.y,
        piece.rotation_state,
        copy.deepcopy(piece.shape),
        copy.deepcopy(piece.color_matrix),
    )

    assert piece.try_rotate_srs(board, -1, check_func=lambda _p: False) is False
    assert (
        piece.x,
        piece.y,
        piece.rotation_state,
        piece.shape,
        piece.color_matrix,
    ) == original


def test_successful_ccw_rotates_color_matrix_with_shape():
    board = Board(width=10, height=20)
    piece = create_piece_by_name('T', x=3, y=5)
    piece.color_matrix = [
        [None, 'a', None],
        ['b', 'c', 'd'],
        [None, None, None],
    ]

    assert piece.try_rotate_srs(board, -1) is True
    assert piece.color_matrix == [
        [None, 'd', None],
        ['a', 'c', None],
        [None, 'b', None],
    ]


def test_workshop_piece_can_rotate_ccw_with_general_nudge_set():
    board = Board(width=10, height=20)
    piece = Piece(x=-1, y=4, shape_index=2)
    piece.is_workshop_piece = True

    assert piece.try_rotate_srs(board, -1) is True
    assert piece.rotation_state == 3
    assert board.is_valid_position(piece)
    assert piece.last_kick_index > 0


def test_o_piece_ccw_is_safe_and_four_turns_restore_state():
    board = Board(width=10, height=20)
    piece = create_piece_by_name('O', x=4, y=4)
    original_shape = copy.deepcopy(piece.shape)

    for _ in range(4):
        assert piece.try_rotate_srs(board, -1) is True

    assert piece.rotation_state == 0
    assert piece.shape == original_shape


def test_ccw_does_not_change_180_rotation_behavior():
    board = Board(width=10, height=20)
    piece = create_piece_by_name('J', x=3, y=4)

    assert piece.try_rotate_180(board) is True
    assert piece.rotation_state == 2
