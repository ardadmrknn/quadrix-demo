from __future__ import annotations

import pathlib
import sys
import types


ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / 'src'

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from board import Board
from pieces import Piece, get_piece_spawn_y
from pvp_game import PvPGame


def _make_game(debug_enabled: bool = True) -> PvPGame:
    game = PvPGame.__new__(PvPGame)
    game.settings_manager = types.SimpleNamespace(
        get=lambda key, default=None: debug_enabled if key == 'local_pvp_demobot_debug' else default
    )
    game.player1_name = 'demobot'
    game.name_input_active = False
    game.paused = False
    game.game_over = False
    game.board1 = Board()
    game.current_piece1 = None
    game.next_piece1 = None
    game.hold_piece1 = None
    game.can_hold1 = True
    game._apply_block_style = lambda piece: piece
    return game


def _fill_bottom_gap(board: Board, start: int, width: int) -> None:
    for x in range(board.width):
        if start <= x < (start + width):
            continue
        board.occupancy[board.height - 1][x] = True
        board.grid[board.height - 1][x] = (40, 40, 40)


def test_demobot_activation_requires_hidden_toggle_and_name():
    game = _make_game(debug_enabled=True)

    assert game._is_player1_demobot_active() is True

    game.player1_name = 'arda'
    assert game._is_player1_demobot_active() is False

    game.player1_name = 'demobot'
    game.settings_manager = types.SimpleNamespace(get=lambda key, default=None: False if key == 'local_pvp_demobot_debug' else default)
    assert game._is_player1_demobot_active() is False


def test_demobot_prefers_immediate_line_clear_with_i_piece():
    game = _make_game(debug_enabled=True)
    _fill_bottom_gap(game.board1, start=3, width=4)

    piece = Piece(x=3, y=get_piece_spawn_y(Piece(shape_index=0)), shape_index=0)
    piece.y = get_piece_spawn_y(piece)
    game.current_piece1 = piece
    game.can_hold1 = False

    plan = game._build_demobot_plan()

    assert plan is not None
    assert plan['use_hold'] is False
    assert plan['lines_cleared'] >= 1
    assert plan['target_x'] == 3


def test_demobot_uses_hold_when_held_piece_clears_line_better():
    game = _make_game(debug_enabled=True)
    _fill_bottom_gap(game.board1, start=3, width=4)

    game.current_piece1 = Piece(shape_index=1)
    game.current_piece1.y = get_piece_spawn_y(game.current_piece1)
    game.hold_piece1 = Piece(shape_index=0)
    game.hold_piece1.y = get_piece_spawn_y(game.hold_piece1)
    game.next_piece1 = Piece(shape_index=2)
    game.next_piece1.y = get_piece_spawn_y(game.next_piece1)
    game.can_hold1 = True

    plan = game._build_demobot_plan()

    assert plan is not None
    assert plan['use_hold'] is True
    assert plan['lines_cleared'] >= 1
    assert plan['target_x'] == 3