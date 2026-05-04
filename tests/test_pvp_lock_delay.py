from __future__ import annotations

import pathlib
import sys


ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / 'src'

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from board import Board
from constants import DEFAULT_LOCK_DELAY
from online_pvp_game import OnlinePvPGame
from pieces import Piece
from pvp_game import PvPGame


class _SilentSound:
    def play(self, _name):
        pass


def _make_lock_delay_game() -> PvPGame:
    game = PvPGame.__new__(PvPGame)
    game.board1 = Board()
    game.board2 = Board()
    game.sound = _SilentSound()
    game.current_piece1 = None
    game.current_piece2 = None
    game.lock_delay = DEFAULT_LOCK_DELAY
    game.enable_lock_delay = True
    game.p1_grounded = False
    game.p2_grounded = False
    game.p1_lock_timer = 0.0
    game.p2_lock_timer = 0.0
    return game


def _grounded_o_piece() -> Piece:
    return Piece(x=4, y=18, shape_index=1)


def test_local_pvp_player1_waits_for_lock_delay_before_locking():
    game = _make_lock_delay_game()
    calls: list[int] = []
    game.current_piece1 = _grounded_o_piece()
    game.lock_and_new_piece = lambda player: calls.append(player)

    game._update_lock_delay_for_player(1, DEFAULT_LOCK_DELAY - 1)

    assert calls == []
    assert game.p1_grounded is True
    assert game.p1_lock_timer == DEFAULT_LOCK_DELAY - 1

    game._update_lock_delay_for_player(1, 1)

    assert calls == [1]


def test_local_pvp_player2_uses_same_lock_delay_path():
    game = _make_lock_delay_game()
    calls: list[int] = []
    game.current_piece2 = _grounded_o_piece()
    game.lock_and_new_piece = lambda player: calls.append(player)

    game._update_lock_delay_for_player(2, DEFAULT_LOCK_DELAY)

    assert calls == [2]
    assert game.p2_grounded is True


def test_local_pvp_lock_delay_resets_when_piece_can_fall_again():
    game = _make_lock_delay_game()
    calls: list[int] = []
    game.current_piece1 = Piece(x=4, y=17, shape_index=1)
    game.p1_grounded = True
    game.p1_lock_timer = DEFAULT_LOCK_DELAY - 1
    game.lock_and_new_piece = lambda player: calls.append(player)

    game._update_lock_delay_for_player(1, 16)

    assert calls == []
    assert game.p1_grounded is False
    assert game.p1_lock_timer == 0.0


def test_local_pvp_soft_drop_touching_ground_does_not_lock_immediately():
    game = _make_lock_delay_game()
    calls: list[int] = []
    game.current_piece1 = _grounded_o_piece()
    game.lock_and_new_piece = lambda player: calls.append(player)

    assert game._try_soft_drop_step_p1() is True

    assert calls == []
    assert game.p1_grounded is True

    game._update_lock_delay_for_player(1, DEFAULT_LOCK_DELAY)

    assert calls == [1]


def test_local_pvp_horizontal_move_does_not_extend_lock_delay_forever():
    game = _make_lock_delay_game()
    calls: list[int] = []
    game.current_piece1 = _grounded_o_piece()
    game.p1_grounded = True
    game.p1_lock_timer = DEFAULT_LOCK_DELAY - 1
    game.lock_and_new_piece = lambda player: calls.append(player)

    assert game._try_move_right_p1() is True
    assert game.p1_lock_timer == DEFAULT_LOCK_DELAY - 1

    game._update_lock_delay_for_player(1, 1)

    assert calls == [1]


def test_local_pvp_player2_horizontal_move_does_not_reset_lock_timer():
    game = _make_lock_delay_game()
    calls: list[int] = []
    game.current_piece2 = _grounded_o_piece()
    game.p2_grounded = True
    game.p2_lock_timer = DEFAULT_LOCK_DELAY - 1
    game.lock_and_new_piece = lambda player: calls.append(player)

    assert game._try_move_left_p2() is True
    assert game.p2_lock_timer == DEFAULT_LOCK_DELAY - 1

    game._update_lock_delay_for_player(2, 1)

    assert calls == [2]


def test_local_pvp_rotate_does_not_reset_grounded_lock_timer():
    game = _make_lock_delay_game()
    calls: list[int] = []
    game.current_piece1 = _grounded_o_piece()
    game.p1_grounded = True
    game.p1_lock_timer = DEFAULT_LOCK_DELAY - 1
    game.lock_and_new_piece = lambda player: calls.append(player)

    assert game._try_rotate_p1() is True
    assert game.p1_lock_timer == DEFAULT_LOCK_DELAY - 1

    game._update_lock_delay_for_player(1, 1)

    assert calls == [1]


def test_online_pvp_horizontal_move_does_not_reset_grounded_lock_timer():
    game = OnlinePvPGame.__new__(OnlinePvPGame)
    game.my_board = Board()
    game.my_piece = _grounded_o_piece()
    game.lock_timer = DEFAULT_LOCK_DELAY - 1
    game._send_piece_position = lambda: None

    game._move_horizontal(1)

    assert game.lock_timer == DEFAULT_LOCK_DELAY - 1


def test_online_pvp_rotate_does_not_reset_grounded_lock_timer():
    game = OnlinePvPGame.__new__(OnlinePvPGame)
    game.my_board = Board()
    game.my_piece = _grounded_o_piece()
    game.lock_timer = DEFAULT_LOCK_DELAY - 1
    game.sound = _SilentSound()
    game._send_piece_position = lambda: None

    game._rotate_piece(1)

    assert game.lock_timer == DEFAULT_LOCK_DELAY - 1
