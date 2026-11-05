from coop_game import CoopGame
from pieces import Piece


def test_failed_hidden_lock_rollback_restores_hidden_buffer():
    cg = CoopGame(sound_enabled=False, effects_enabled=False)
    cg.p2_current_piece = Piece(x=13, y=-3, shape_index=1)

    cg._lock_and_new_piece("P2")

    assert all(not cell for row in cg.board.hidden_occupancy for cell in row)
