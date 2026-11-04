import pytest
from board import Board
from pieces import create_piece_by_name

pytestmark = [pytest.mark.quadrix_feedback, pytest.mark.quadrix_phase3]

def test_partial_hidden_lock_is_not_game_over():
    board = Board(width=10, height=20)
    piece = create_piece_by_name("O", x=3, y=-1)
    board.lock_piece(piece)
    assert board.is_game_over() is False

def test_fully_hidden_lock_is_game_over():
    board = Board(width=10, height=20)
    piece = create_piece_by_name("O", x=3, y=-3)
    board.lock_piece(piece)
    assert board.is_game_over() is True

