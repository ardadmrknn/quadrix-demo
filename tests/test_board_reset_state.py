"""Board.reset() tüm board-tarafı state'i eksiksiz sıfırlamalı.

Regresyon: reset() önceden `level_lines_cleared` ve `flexible_border_active`
alanlarını sıfırlamıyordu; tutorial.py reset() sonrası elle
`level_lines_cleared = 0` set ederek bu eksikliği telafi ediyordu.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src'))

from board import Board


def test_reset_clears_level_lines_and_flexible_border():
    board = Board()
    # Board-tarafı state'i kirlet
    board.level_lines_cleared = 7
    board.flexible_border_active = True

    board.reset()

    assert board.level_lines_cleared == 0
    assert board.flexible_border_active is False


def test_reset_clears_baseline_state():
    board = Board()
    board.score = 1234
    board.lines_cleared = 42
    board.level = 5
    board.combo = 3
    board.tetrises = 2
    board.last_cleared_lines = [1, 2, 3]
    board.last_cleared_colors = {1: [(255, 0, 0)]}
    board.back_to_back = True

    board.reset()

    assert board.score == 0
    assert board.lines_cleared == 0
    assert board.level == 1
    assert board.combo == 0
    assert board.tetrises == 0
    assert board.last_cleared_lines == []
    assert board.last_cleared_colors == {}
    assert board.back_to_back is False
