import types

import pytest

from board import Board
from game_modes_advanced import CascadeMode


pytestmark = [pytest.mark.quadrix_feedback, pytest.mark.quadrix_phase2]


def test_cascade_bulk_row_removal_preserves_original_row_ownership():
    mode = CascadeMode.__new__(CascadeMode)
    mode.board_width = 6
    mode.board_height = 6
    mode.board = Board(width=6, height=6)
    for y in range(6):
        owner = str(y)
        for x in range(6):
            mode.board.occupancy[y][x] = True
            mode.board.owners[y][x] = owner
    mode.apply_cascade_gravity([2, 4])
    assert [row[0] for row in mode.board.owners] == [None, None, "0", "1", "3", "5"]

