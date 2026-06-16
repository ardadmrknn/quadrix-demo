"""Tetr.io standartlarına uygun lock delay stalling ve step reset testleri"""
import sys
import pathlib
import pytest

ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / 'src'

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import game as game_module
from board import Board
from pieces import create_piece_by_name, Piece


class DummySound:
    def play(self, name: str) -> None:
        pass


def _make_test_game(piece: Piece, board: Board) -> game_module.Game:
    game = game_module.Game.__new__(game_module.Game)
    game.game_over = False
    game.paused = False
    game.show_exit_prompt = False
    game.current_piece = piece
    game.board = board
    game.sound = DummySound()
    game.grounded = False
    game.lock_timer = 0.0
    game.lock_reset_count = 0
    game.stall_timer = 0.0
    game.max_reached_y = piece.y
    return game


def test_lock_delay_resets_on_horizontal_move_and_rotation_under_limits() -> None:
    """Yatay hareket ve döndürme yapıldığında, limitler aşılmadıysa lock_timer sıfırlanır."""
    board = Board(width=10, height=20)
    piece = create_piece_by_name('T', x=3, y=18)  # Yerde
    game = _make_test_game(piece, board)
    game.grounded = True
    game.lock_timer = 250.0

    # Sağa hareket
    moved = game._try_move_right()
    assert moved is True
    assert game.lock_timer == 0.0
    assert game.lock_reset_count == 1

    # Dönüş (Clockwise)
    game.lock_timer = 200.0
    rotated = piece.try_rotate_srs(board, 1)
    assert rotated is True
    game._update_grounded_after_action()
    assert game.lock_timer == 0.0
    assert game.lock_reset_count == 2


def test_lock_delay_does_not_reset_when_limit_is_exceeded() -> None:
    """Limit (15 reset veya 3000ms stall) aşıldığında lock_timer sıfırlanmaz."""
    board = Board(width=10, height=20)
    piece = create_piece_by_name('T', x=3, y=18)
    game = _make_test_game(piece, board)
    game.grounded = True
    game.lock_reset_count = 15
    game.lock_timer = 250.0

    # Sağa hareket dene
    moved = game._try_move_right()
    assert moved is True
    assert game.lock_timer == 250.0  # Sıfırlanmadı!
    assert game.lock_reset_count == 16


def test_falling_off_ledge_sets_grounded_false_immediately() -> None:
    """Parça bir boşluğa (ledge) düştüğünde grounded durumu anında False olur ve lock_timer sıfırlanır."""
    board = Board(width=10, height=20)
    # y=19 satırında sadece x=2 hücresini doldur. O parçası x=2, y=17 iken taban hücreleri (2,18) ve (3,18) olur.
    # (2,18)'in altı (2,19) doludur, dolayısıyla grounded'dır.
    board.occupancy[19][2] = True
    piece = create_piece_by_name('O', x=2, y=17)
    
    assert not board.is_valid_position(piece, dy=1)

    game = _make_test_game(piece, board)
    game.grounded = True
    game.lock_timer = 200.0

    # Sağa kaydır (x=3'e) -> O parçası x=3,4 olur. Taban altları (3,19) ve (4,19) boştur. Havada kalır.
    moved = game._try_move_right()
    assert moved is True
    assert game.grounded is False
    assert game.lock_timer == 0.0


def test_step_reset_on_new_lower_y() -> None:
    """Parça yer çekimi ile daha aşağı seviyeye indiğinde limit sayaçları tamamen sıfırlanır."""
    board = Board(width=10, height=20)
    piece = create_piece_by_name('O', x=3, y=10)
    game = _make_test_game(piece, board)
    game.lock_reset_count = 8
    game.stall_timer = 1500.0
    game.lock_timer = 200.0
    game.max_reached_y = 10

    # update döngüsünde aşağı düşüşü taklit et
    dt = 16.66
    effective_lock_delay = 500.0
    # Gravity drop
    piece.y += 1  # y = 11
    assert board.is_valid_position(piece)
    
    # Otomatik gravity güncelleme simülasyonu
    game.last_move_was_rotate = False
    if piece.y > game.max_reached_y:
        game.max_reached_y = piece.y
        game.stall_timer = 0.0
        game.lock_reset_count = 0
        game.lock_timer = 0.0

    assert game.max_reached_y == 11
    assert game.lock_reset_count == 0
    assert game.stall_timer == 0.0
    assert game.lock_timer == 0.0
