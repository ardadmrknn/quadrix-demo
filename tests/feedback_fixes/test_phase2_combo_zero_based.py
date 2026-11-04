import pytest

from board import Board


pytestmark = [pytest.mark.quadrix_feedback, pytest.mark.quadrix_phase2]


def _single_clear_board() -> Board:
    board = Board(width=10, height=20)
    for x in range(board.width):
        board.occupancy[19][x] = True
        board.grid[19][x] = (1, 1, 1)
    board.occupancy[0][0] = True
    board.grid[0][0] = (1, 1, 1)
    return board


def test_combo_state_starts_at_one_after_first_clear_and_increments_after_next():
    board = _single_clear_board()
    board.clear_lines()
    assert board.combo == 1
    board2 = _single_clear_board()
    board2.combo = board.combo
    board2.clear_lines()
    assert board2.combo == 2

