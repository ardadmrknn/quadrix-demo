from types import SimpleNamespace

import pytest

from board import Board
from game_modes_extra import MysteryMode
from online_coop_game import OnlineCoopGame
from pvp_game import PvPGame


pytestmark = [pytest.mark.quadrix_feedback, pytest.mark.quadrix_phase3]


def _board_with_hidden_cell() -> Board:
    board = Board()
    board.hidden_occupancy[0][4] = True
    board.hidden_grid[0][4] = (11, 22, 33)
    board.hidden_gold[0][4] = True
    board.hidden_owners[0][4] = 'P2'
    return board


def test_time_capsule_round_trip_preserves_hidden_buffer_state():
    mode = MysteryMode.__new__(MysteryMode)
    mode.board = _board_with_hidden_cell()
    snapshot = mode._capture_time_capsule_state()
    mode.board.hidden_occupancy[0][4] = False
    mode.board.hidden_grid[0][4] = (0, 0, 0)
    mode.board.hidden_gold[0][4] = False
    mode.board.hidden_owners[0][4] = None
    mode._restore_time_capsule_state(snapshot)
    assert mode.board.hidden_occupancy[0][4] is True
    assert mode.board.hidden_grid[0][4] == (11, 22, 33)
    assert mode.board.hidden_gold[0][4] is True
    assert mode.board.hidden_owners[0][4] == 'P2'


def test_demobot_board_clone_preserves_hidden_buffer_state():
    clone = PvPGame._clone_board_for_demobot(_board_with_hidden_cell())
    assert clone.hidden_occupancy[0][4] is True
    assert clone.hidden_grid[0][4] == (11, 22, 33)
    assert clone.hidden_gold[0][4] is True
    assert clone.hidden_owners[0][4] == 'P2'


def test_online_coop_semantic_snapshot_round_trip_preserves_hidden_coordinate():
    source = _board_with_hidden_cell()
    host = OnlineCoopGame.__new__(OnlineCoopGame)
    host.coop_game = SimpleNamespace(board=source)
    cells = host._capture_semantic_board_cells()
    payload = {
        'format': 'semantic_delta_v1',
        'cells': [],
        'hidden_cells': host._serialize_semantic_board_cells(
            [((x, -y - 1), payload) for (x, y), payload in cells.items()]
        ),
        'full': True,
    }
    guest = OnlineCoopGame.__new__(OnlineCoopGame)
    guest._last_host_guest_piece_ack_seq = 0
    normalized = guest._normalize_board_snapshot(payload)
    assert normalized is not None
    assert normalized['_semantic_cells'][0][0:2] == (4, -2)
    target = Board()
    guest._apply_semantic_board_cell(target, normalized['_semantic_cells'][0])
    assert target.hidden_occupancy[0][4] is True
    assert target.hidden_gold[0][4] is True
    assert target.hidden_owners[0][4] == 'P2'
