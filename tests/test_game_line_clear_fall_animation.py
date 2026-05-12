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