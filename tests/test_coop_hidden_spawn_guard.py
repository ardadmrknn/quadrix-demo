from coop_board import CoopBoard
from pieces import Piece


def test_coop_spawn_rejects_occupied_hidden_buffer_cell():
    board = CoopBoard()
    piece = Piece(x=13, y=-2, shape_index=1)
    board.hidden_occupancy[0][13] = True

    assert board.is_valid_position_for_player(piece, "P2") is False
