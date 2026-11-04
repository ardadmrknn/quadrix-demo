import copy

import pytest

from board import Board


pytestmark = [pytest.mark.quadrix_feedback, pytest.mark.quadrix_phase2]


def _fixture() -> Board:
    board = Board(width=10, height=20)
    for y in (18, 19):
        for x in range(10):
            board.occupancy[y][x] = True
            board.grid[y][x] = (1, 1, 1)
    board.occupancy[10][2] = True
    board.grid[10][2] = (2, 2, 2)
    board.level = 3
    board.combo = 1
    board.back_to_back = True
    return board


def test_same_board_scoring_is_deterministic():
    first = _fixture()
    second = _fixture()
    first.clear_lines(t_spin="full")
    second.clear_lines(t_spin="full")
    assert (first.score, first.combo, first.back_to_back, first.lines_cleared) == (
        second.score, second.combo, second.back_to_back, second.lines_cleared
    )

