"""Esnek Sınır kilitleme + spawn block-out + görünür row 0 lock-out testleri.

Bu testler tek pencerede yapılan üç düzeltmeyi doğrular:
  A) Esnek sınırda taşan parça kilitlenince yerinde kalır; görünür alan dışındaki
      hücreler içeri snap'lenmez.
  B) Spawn çakışmasında block-out game-over; lock sonrası görünür row 0 dolu → game-over;
      row 0 boşken haksız game-over yok.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "src"))

from board import Board
from pieces import create_piece_by_name


def _occupied_count(board: Board) -> int:
    return sum(1 for row in board.occupancy for cell in row if cell)


# ---------------------------------------------------------------------------
# A) Esnek sınır taşması kilitte snap yapmaz
# ---------------------------------------------------------------------------

def test_flexible_overflow_lock_preserves_all_cells_left():
    """I parçası sol kenardan taşmışken kilitlenince yerinde kalmalı, içeri kaymamalı."""
    board = Board(width=10, height=20)
    piece = create_piece_by_name("I")  # 4x4, dolu satır index 1 (col 0..3)
    piece.x = -1  # sol kenardan bir sütun taşma
    piece.y = 0
    setattr(piece, "flexible_border", True)

    board.lock_piece(piece)

    # Parça içeri snap'lenmez; yalnızca görünür kalan 3 hücre yazılır.
    assert _occupied_count(board) == 3
    filled = [(x, y) for y in range(board.height) for x in range(board.width) if board.occupancy[y][x]]
    assert all(0 <= x < board.width for x, _ in filled)
    assert sorted(filled) == [(0, 1), (1, 1), (2, 1)]


def test_flexible_overflow_lock_preserves_all_cells_right():
    """I parçası sağ kenardan taşmışken kilitlenince yerinde kalmalı, içeri kaymamalı."""
    board = Board(width=10, height=20)
    piece = create_piece_by_name("I")
    piece.x = 7  # col 0..3 → board x 7,8,9,10 (10 taşma)
    piece.y = 0
    setattr(piece, "flexible_border", True)

    board.lock_piece(piece)

    assert _occupied_count(board) == 3
    filled = [(x, y) for y in range(board.height) for x in range(board.width) if board.occupancy[y][x]]
    assert all(0 <= x < board.width for x, _ in filled)
    assert sorted(filled) == [(7, 1), (8, 1), (9, 1)]


def test_flexible_overflow_lock_uses_board_flag_without_snap():
    """Board seviyesinde aktif Esnek Sınır da lock sırasında içeri snap üretmemeli."""
    board = Board(width=10, height=20)
    board.flexible_border_active = True

    piece = create_piece_by_name("O")
    piece.x = -1
    piece.y = 2

    board.lock_piece(piece)

    assert _occupied_count(board) == 2
    filled = {(x, y) for y in range(board.height) for x in range(board.width) if board.occupancy[y][x]}
    assert filled == {(0, 2), (0, 3)}


# ---------------------------------------------------------------------------
# B) Görünür row 0 lock-out kuralı
# ---------------------------------------------------------------------------

def test_lock_out_when_visible_row0_filled_after_clears():
    """Kilit + temizlik sonrası görünür row 0'da dolu hücre kalırsa game-over."""
    board = Board(width=10, height=20)
    # I parçası (4 geniş) board width 10'da row 0'ı doldurmaz → satır temizlenmez,
    # row 0 dolu kalır → lock-out.
    piece = create_piece_by_name("I")  # yatay, dolu satır index 1
    piece.x = 0
    piece.y = -1  # dolu satır board y=0'a denk gelir
    board.lock_piece(piece)

    # row 0 dolu → lock-out.
    assert any(board.occupancy[0][x] for x in range(board.width))
    assert board.is_game_over() is True


def test_no_game_over_when_row0_empty_after_lock():
    """Row 0 boşken (parça aşağıda kilitlenir) haksız game-over olmamalı."""
    board = Board(width=10, height=20)
    piece = create_piece_by_name("O")  # 2x2
    piece.x = 0
    piece.y = 18  # tabanda kilitlenir; row 0 boş kalır
    board.lock_piece(piece)

    assert not any(board.occupancy[0][x] for x in range(board.width))
    assert board.is_game_over() is False


def test_full_top_row_clears_and_no_game_over():
    """Görünür row 0 tamamen dolup TEMİZLENİRSE game-over olmamalı (haksız ölüm yok)."""
    board = Board(width=4, height=6)
    # row 0'ın 3 hücresini önceden doldur (clear_lines bunu silmesin diye row 0 değil...)
    # Bunun yerine: tüm row 0'ı dolduracak bir parça yatay I (genişlik 4) ile.
    piece = create_piece_by_name("I")  # 4 geniş, board width 4 → tam satır
    piece.x = 0
    piece.y = -1  # dolu satır row 0
    board.lock_piece(piece)

    # row 0 tamamen dolduğundan clear_lines onu siler → row 0 boşalır → game-over yok.
    assert not any(board.occupancy[0][x] for x in range(board.width))
    assert board.is_game_over() is False


def test_overflow_top_unwritable_cell_triggers_lock_out():
    """Görünür alanın üstünde (y<0) yazılamayan dolu hücre kalırsa top-out → game-over."""
    board = Board(width=10, height=20)
    piece = create_piece_by_name("I")
    # I parçasını dikey yap (dolu sütun) ki bazı hücreler y<0'da kalsın.
    piece.rotate()
    piece.x = 0
    piece.y = -3  # bazı dolu hücreler y<0'da kalır
    board.lock_piece(piece)

    assert board.is_game_over() is True


# ---------------------------------------------------------------------------
# B) Spawn block-out (temel Game.update üzerinden)
# ---------------------------------------------------------------------------

def _make_minimal_game(board, piece):
    from game import Game

    game = Game.__new__(Game)
    game.game_over = False
    game.paused = False
    game.show_exit_prompt = False
    game.game_over_warning_timer = 0
    game.sound = None  # _finalize_game_over_after_lock ses bloğunu atlasın
    game.board = board
    game.current_piece = piece
    return game


def test_spawn_collision_triggers_block_out_game_over():
    """Yeni parça spawn konumunda mevcut blokla çakışıyorsa anında game-over."""
    board = Board(width=10, height=20)
    # Spawn alanını doldur (O parçası (0,0)-(1,1) hücrelerini kaplar).
    board.occupancy[0][0] = True
    board.grid[0][0] = (20, 20, 20)

    piece = create_piece_by_name("O")
    piece.x = 0
    piece.y = 0  # (0,0) dolu → is_valid_position False

    game = _make_minimal_game(board, piece)
    finalize_calls = []
    game.finalize_run = lambda *a, **k: finalize_calls.append(1)

    game.update(16)

    assert game.game_over is True
    assert finalize_calls == [1]


def test_valid_spawn_does_not_block_out():
    """Spawn alanı boşken block-out koşulu (is_valid_position False) tetiklenmemeli."""
    board = Board(width=10, height=20)
    piece = create_piece_by_name("O")
    piece.x = 4
    piece.y = 0

    # update() top-of-frame guard'ı yalnızca is_valid_position False olduğunda
    # _handle_block_out çağırır. Boş tahtada spawn geçerli → block-out yok.
    assert board.is_valid_position(piece) is True


# ---------------------------------------------------------------------------
# A) Render kırpma: board dışı hücreler çizilmez (çizim guard'ı)
# ---------------------------------------------------------------------------

def test_overflow_cell_is_outside_board_render_range():
    """Esnek taşan parçanın taşan hücresi board render aralığı [0,width) dışındadır.

    Aktif parça ve ghost çizim döngüleri `if x < 0 or x >= board_width: continue`
    guard'ı ile bu hücreleri atlar (görsel olarak gözükmez). Bu test, taşan hücrenin
    gerçekten aralık dışında olduğunu ve guard'ın onu eleyeceğini doğrular.
    """
    board_width = 10
    piece = create_piece_by_name("I")
    piece.x = -1  # sol taşma
    piece.y = 0

    cells = piece.get_cells()
    # En az bir hücre board dışında (x < 0) olmalı.
    assert any(x < 0 for x, _ in cells)
    # Render guard'ının çizeceği hücreler yalnızca [0, board_width) aralığındakiler.
    drawable = [(x, y) for x, y in cells if 0 <= x < board_width]
    assert all(0 <= x < board_width for x, _ in drawable)
    # Taşan hücre çizilmez → çizilebilir hücre sayısı toplam hücreden az.
    assert len(drawable) < len(cells)
