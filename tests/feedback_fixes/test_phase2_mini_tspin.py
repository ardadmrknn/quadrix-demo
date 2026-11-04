import pytest

from board import Board


pytestmark = [pytest.mark.quadrix_feedback, pytest.mark.quadrix_phase2]


def _board_with_full_rows(count: int) -> Board:
    board = Board(width=10, height=20)
    for offset in range(count):
        y = board.height - 1 - offset
        for x in range(board.width):
            board.occupancy[y][x] = True
            board.grid[y][x] = (1, 1, 1)
    board.occupancy[0][0] = True
    board.grid[0][0] = (1, 1, 1)
    return board


@pytest.mark.parametrize("lines, expected", [(0, 100), (1, 200), (2, 400)])
def test_mini_tspin_guideline_points(lines, expected):
    board = _board_with_full_rows(lines)
    board.clear_lines(t_spin="mini")
    assert board.score == expected * board.level

