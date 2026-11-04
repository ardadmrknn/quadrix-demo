import pytest

from board import Board


pytestmark = [pytest.mark.quadrix_feedback, pytest.mark.quadrix_phase2]


@pytest.mark.parametrize("lines, expected", [(0, 400), (1, 800), (2, 1200), (3, 1600)])
def test_full_tspin_points_keep_zero_to_triple_index_contract(lines, expected):
    board = Board(width=10, height=20)
    for offset in range(lines):
        y = board.height - 1 - offset
        for x in range(board.width):
            board.occupancy[y][x] = True
            board.grid[y][x] = (1, 1, 1)
    board.occupancy[0][0] = True
    board.grid[0][0] = (1, 1, 1)
    board.clear_lines(t_spin="full")
    assert board.score == expected * board.level

