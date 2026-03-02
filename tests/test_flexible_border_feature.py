"""Esnek sınır özelliği için temel pozisyon doğrulama testleri."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from board import Board
from pieces import create_piece_by_name


def _new_piece(name='I', x=0, y=0, flexible=False):
    piece = create_piece_by_name(name)
    piece.x = x
    piece.y = y
    if flexible:
        setattr(piece, 'flexible_border', True)
    return piece


def test_normal_piece_cannot_exit_left_border():
    board = Board(width=10, height=20)
    piece = _new_piece('I', x=-1, y=0, flexible=False)
    assert board.is_valid_position(piece) is False


def test_flexible_piece_can_exit_left_by_one_cell():
    board = Board(width=10, height=20)
    piece = _new_piece('I', x=-1, y=0, flexible=True)
    assert board.is_valid_position(piece) is True


def test_flexible_piece_can_exit_right_by_one_cell():
    board = Board(width=10, height=20)
    piece = _new_piece('I', x=7, y=0, flexible=True)
    assert board.is_valid_position(piece) is True


def test_flexible_piece_cannot_exit_bottom_by_one_cell():
    board = Board(width=10, height=20)
    piece = _new_piece('I', x=0, y=20, flexible=True)
    assert board.is_valid_position(piece) is False


def test_flexible_piece_cannot_exit_by_two_cells():
    board = Board(width=10, height=20)
    piece = _new_piece('I', x=8, y=0, flexible=True)
    assert board.is_valid_position(piece) is False
