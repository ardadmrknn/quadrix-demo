import pathlib
import sys
import types


ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / 'src'

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import game as game_module


def _build_game_for_fall_animation():
    game = game_module.Game.__new__(game_module.Game)
    game.board = types.SimpleNamespace(
        width=4,
        height=7,
        occupancy=[[False for _ in range(4)] for _ in range(7)],
    )
    game.line_clear_sweep_active = True
    game.line_clear_sweep_progress = 0.0
    game.falling_block_animations = []
    game.get_cell_size = lambda: 10
    return game


def test_start_block_fall_animation_waits_for_sweep_and_only_animates_shifted_cells():
    game = _build_game_for_fall_animation()

    # clear row 4 -> only rows above it should have moved down into their new spots.
    game.board.occupancy[4][0] = True
    game.board.occupancy[5][1] = True

    game._start_block_fall_animation([4])

    assert game.falling_block_animations == [
        {
            'row': 4,
            'col': 0,
            'current_offset': -10.0,
            'target_offset': 0,
            'sweep_trigger': 1.0,
            'started': False,
        }
    ]


def test_ghost_visual_offset_tracks_falling_locked_blocks():
    game = _build_game_for_fall_animation()
    game.current_piece = types.SimpleNamespace(
        y=1,
        get_cells=lambda: [(0, 1), (1, 1)],
    )
    game.falling_block_animations = [
        {'row': 5, 'col': 0, 'current_offset': -10.0},
        {'row': 5, 'col': 1, 'current_offset': -4.0},
        {'row': 6, 'col': 2, 'current_offset': -20.0},
    ]
    game.board.occupancy[5][0] = True
    game.board.occupancy[5][1] = True
    game.board.occupancy[6][2] = True

    assert game._get_ghost_visual_offset(4) == -10.0


def test_ghost_visual_offset_ignores_columns_without_supporting_blocks():
    game = _build_game_for_fall_animation()
    game.current_piece = types.SimpleNamespace(
        y=0,
        get_cells=lambda: [(3, 0)],
    )
    game.falling_block_animations = [
        {'row': 5, 'col': 0, 'current_offset': -12.0},
    ]
    game.board.occupancy[5][0] = True

    assert game._get_ghost_visual_offset(3) == 0.0
