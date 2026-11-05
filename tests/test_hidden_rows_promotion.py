from board import Board
from pieces import create_piece_by_name


def test_clear_promotes_hidden_cell_into_visible_row():
    board = Board(width=4, height=4)
    piece = create_piece_by_name("O", x=0, y=-1)
    board.lock_piece(piece)
    board.occupancy[0][2] = True
    board.occupancy[0][3] = True

    assert board.clear_lines() == 1
    assert board.occupancy[0][0] is True
    assert board.occupancy[0][1] is True
    assert board.hidden_occupancy[1][0] is False
    assert board.hidden_occupancy[1][1] is False
