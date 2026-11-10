import os
import sys
from pathlib import Path

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
os.environ.setdefault('SDL_RENDER_VSYNC', '0')

ROOT_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / 'src'
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from game import Game  # noqa: E402
from pieces import SHAPE_NAMES, create_piece_by_name  # noqa: E402
from settings_manager import SettingsManager  # noqa: E402


def test_all_standard_pieces_stay_in_hidden_buffer_on_spawn(tmp_path):
    game = Game(
        settings_manager=SettingsManager(filename=str(tmp_path / 'settings.json')),
        sound_enabled=False,
        game_mode='classic',
    )

    for name in SHAPE_NAMES:
        piece = game._create_named_piece(name)
        spawn_y = game._compute_spawn_y(piece)
        game._skip_hidden_rows(piece)

        assert piece.y == spawn_y == (-3 if name == 'I' else -2), name
        assert min(y for _, y in piece.get_cells()) == -2, name
        assert game.board.is_valid_position(piece), name


def test_held_piece_returns_to_hidden_buffer_without_visibility_snap(tmp_path):
    game = Game(
        settings_manager=SettingsManager(filename=str(tmp_path / 'settings.json')),
        sound_enabled=False,
        game_mode='classic',
    )
    piece = create_piece_by_name('T')
    game._position_piece_at_spawn(piece)

    game._skip_hidden_rows(piece)

    assert piece.y == -2
    assert min(y for _, y in piece.get_cells()) == -2
