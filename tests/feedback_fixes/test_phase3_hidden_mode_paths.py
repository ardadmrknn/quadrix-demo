from types import SimpleNamespace

import pytest

from board import Board
from game_modes import ZenMode
from game_modes_advanced import CascadeMode
from pieces import create_piece_by_name


pytestmark = [pytest.mark.quadrix_feedback, pytest.mark.quadrix_phase3]


def _zen_mode(board: Board, *, auto_clear_rows=None):
    mode = ZenMode.__new__(ZenMode)
    mode.board = board
    mode.auto_clear_rows = auto_clear_rows
    mode.auto_clears = 0
    mode.auto_clear_penalty = 0
    mode.current_piece = SimpleNamespace(x=0, y=0)
    mode.effects_enabled = False
    mode.sound_enabled = False
    mode._position_piece_at_spawn = lambda piece: None
    mode._skip_hidden_rows = lambda piece: None
    mode.create_particles = lambda **kwargs: None
    return mode


def test_zen_auto_clear_clears_physical_hidden_buffer():
    board = Board()
    board.hidden_occupancy[0][4] = True
    board.hidden_grid[0][4] = (11, 22, 33)
    board.hidden_gold[0][4] = True
    board.hidden_owners[0][4] = 'P2'

    ZenMode.auto_clear_board(_zen_mode(board))

    assert all(not cell for row in board.hidden_occupancy for cell in row)
    assert all(cell == (5, 5, 20) for row in board.hidden_grid for cell in row)
    assert all(not cell for row in board.hidden_gold for cell in row)
    assert all(cell is None for row in board.hidden_owners for cell in row)


def _cascade_mode(board: Board, piece):
    mode = CascadeMode.__new__(CascadeMode)
    mode.board = board
    mode.board_width = board.width
    mode.board_height = board.height
    mode.current_piece = piece
    mode.next_piece_queue = [create_piece_by_name('O')]
    mode.effects_enabled = False
    mode.sound = SimpleNamespace(
        play=lambda *_args, **_kwargs: None,
        play_game_over_sequence=lambda: None,
    )
    mode.finalize_run = lambda: None
    mode.game_over = False
    mode.cascade_bonus = 0
    mode.last_cascade_level = 0
    mode.cascade_message_time = 0
    mode.grounded = False
    mode.lock_timer = 0
    mode.lock_reset_count = 0
    mode.can_hold = True
    mode.can_hold2 = True
    mode._skip_hidden_rows = lambda _piece: None
    mode.spawn_new_piece = lambda: create_piece_by_name('I')
    mode.apply_theme_to_pieces = lambda: None
    mode.get_current_speed = lambda: 1000
    return mode


def test_cascade_partial_hidden_lock_survives_and_keeps_hidden_cells():
    board = Board(width=10, height=20)
    piece = create_piece_by_name('I')
    piece.rotate()
    piece.x = 0
    piece.y = -2

    mode = _cascade_mode(board, piece)
    CascadeMode.lock_and_new_piece(mode)

    assert mode.game_over is False
    assert board.hidden_occupancy[0][2] is True
    assert board.hidden_occupancy[1][2] is True
    assert board.occupancy[0][2] is True
    assert board.occupancy[1][2] is True


def test_cascade_row_zero_partial_fill_is_not_lock_out():
    board = Board(width=10, height=20)
    piece = create_piece_by_name('I')
    piece.x = 0
    piece.y = -1

    mode = _cascade_mode(board, piece)
    CascadeMode.lock_and_new_piece(mode)

    assert mode.game_over is False
    assert any(board.occupancy[0])


def test_cascade_fully_hidden_lock_is_lock_out():
    board = Board(width=10, height=20)
    piece = create_piece_by_name('O')
    piece.x = 0
    piece.y = -3

    mode = _cascade_mode(board, piece)
    CascadeMode.lock_and_new_piece(mode)

    assert mode.game_over is True


def test_cascade_gravity_promotes_hidden_rows_with_visible_clear():
    board = Board(width=4, height=4)
    board.hidden_occupancy[1][0] = True
    board.hidden_grid[1][0] = (12, 34, 56)
    board.hidden_owners[1][0] = 'hidden'
    mode = CascadeMode.__new__(CascadeMode)
    mode.board = board
    mode.board_width = 4
    mode.board_height = 4

    CascadeMode.apply_cascade_gravity(mode, [3])

    assert all(not cell for row in board.hidden_occupancy for cell in row)
    assert board.occupancy[0][0] is True
    assert board.grid[0][0] == (12, 34, 56)
    assert board.owners[0][0] == 'hidden'
