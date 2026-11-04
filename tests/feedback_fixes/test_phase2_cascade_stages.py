import pytest

from board import Board


pytestmark = [pytest.mark.quadrix_feedback, pytest.mark.quadrix_phase2]


def test_clear_lines_returns_total_and_processes_combo_once_for_a_clear_event():
    board = Board(width=10, height=20)
    for x in range(10):
        board.occupancy[19][x] = True
        board.grid[19][x] = (1, 1, 1)
    board.occupancy[0][0] = True
    board.grid[0][0] = (1, 1, 1)
    assert board.clear_lines() == 1
    assert board.lines_cleared == 1
    assert board.combo == 1


def test_cascade_waves_score_as_separate_combo_events(monkeypatch):
    """Each detected cascade wave is one scoring/combo event."""
    board = Board(width=4, height=6)
    board.occupancy[0][0] = True  # keep the fixture out of perfect-clear scoring
    board.grid[0][0] = (1, 1, 1)
    scan = {"index": 0}

    def scripted_cell_filled(x, y):
        result = y == board.height - 1 and scan["index"] < 2
        if y == board.height - 1 and x == board.width - 1:
            scan["index"] += 1
        return result

    monkeypatch.setattr(board, "_cell_filled", scripted_cell_filled)

    assert board.clear_lines() == 2
    assert board.lines_cleared == 2
    assert board.combo == 2
    # 100 for wave 1 + (100 + 50 combo bonus) for wave 2.
    assert board.score == 250

