"""D10 (OP-018) ghost drop parite testleri.

`get_ghost_y` (game.py) artık hücre listesini bir kez hesaplayıp drop
adımlarını `Board._is_valid_cells`'e dy ofsetiyle soruyor; eski yol her
adımda `Piece.copy()` + `get_cells()` yeniden üretiyordu (~board_height
kez). Bu dosya üç şeyi kanıtlar:

1) REFERANS PARİTESİ: eski algoritmanın bağımsız kopyası (copy + while
   is_valid_position + y-1) rastgele tahta/parça matrislerinde yeni
   `get_ghost_y` ile birebir aynı sonucu verir — perk'li (tunnel/drill/
   flexible) ve geçersiz-başlangıç senaryoları dahil.
2) ÇIPAL ANKRA: boş tahta ve tek-satır-engel senaryolarında ghost'un
   kapalı-formül değeri (height - 1 - max_dolu_satır_ofseti).
3) ORACLE EŞDEĞERLİĞİ: `is_valid_position(piece, dx, dy)` sarmalayıcısı
   `_is_valid_cells(piece.get_cells(), dx, dy, piece)` ile rastgele
   dx/dy setlerinde aynı cevabı verir (sarmalayıcı ile semantik kaynağı
   arasındaki gelecekteki sürüklenmeyi yakalar).
"""
import os
import pathlib
import random
import sys

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

ROOT_DIR = pathlib.Path(__file__).parent
SRC_DIR = ROOT_DIR / 'src'

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import game as game_module  # noqa: E402
from board import Board  # noqa: E402
from pieces import Piece  # noqa: E402


# ---------------------------------------------------------------------------
# Harness
# ---------------------------------------------------------------------------

def _make_game(board, piece):
    """Bare Game: get_ghost_y yalnız board + current_piece okur."""
    g = game_module.Game.__new__(game_module.Game)
    g.board = board
    g.current_piece = piece
    return g


def _reference_ghost_y(game):
    """Eski (D10 öncesi) algoritmanın bağımsız kopyası.

    Parite referansı: copy() + her adımda is_valid_position + y-1.
    """
    test_piece = game.current_piece.copy()
    while game.board.is_valid_position(test_piece):
        test_piece.y += 1
    return test_piece.y - 1


def _make_board(rng, width=10, height=20, density=0.0):
    board = Board(width, height)
    if density > 0:
        for y in range(height):
            for x in range(width):
                if rng.random() < density:
                    board.grid[y][x] = (200, 30, 30)
                    board.occupancy[y][x] = True
    return board


def _make_piece(shape_index, x, y, rotations=0):
    piece = Piece(x, y, shape_index)
    for _ in range(rotations):
        piece.rotate()
    return piece


def _run_parity(rng, scenarios, perk='none'):
    """Rastgele senaryolarda yeni yol == eski referans."""
    mismatches = []
    for shape_index, x, y, rotations, density in scenarios:
        board = _make_board(rng, density=density)
        piece = _make_piece(shape_index, x, y, rotations)
        if perk == 'tunnel':
            piece.tunnel = True
        elif perk == 'drill':
            piece.drill = True
        elif perk == 'flexible_piece':
            piece.flexible_border = True
        elif perk == 'flexible_board':
            board.flexible_border_active = True
        g = _make_game(board, piece)
        new_value = g.get_ghost_y()
        ref_value = _reference_ghost_y(g)
        if new_value != ref_value:
            mismatches.append(
                (shape_index, x, y, rotations, density, perk,
                 new_value, ref_value)
            )
    return mismatches


def _random_scenarios(rng, count):
    return [
        (
            rng.randrange(7),            # shape_index
            rng.randint(-2, 11),         # x (tahta dışı dahil)
            rng.randint(-2, 18),         # y (negatif spawn dahil)
            rng.randrange(4),            # rotasyon
            rng.uniform(0.0, 0.7),       # tahta doluluk yoğunluğu
        )
        for _ in range(count)
    ]


# ---------------------------------------------------------------------------
# 1) Rastgele matris paritesi
# ---------------------------------------------------------------------------

def test_reference_parity_random_matrix():
    rng = random.Random(20261010)
    scenarios = _random_scenarios(rng, 500)
    mismatches = _run_parity(rng, scenarios, perk='none')
    assert not mismatches, f"parite bozuldu: {mismatches[:5]}"


def test_reference_parity_perk_variants():
    """tunnel/drill/flexible (parça ve board bayrağı) altında da parite."""
    for perk in ('tunnel', 'drill', 'flexible_piece', 'flexible_board'):
        rng = random.Random(20261010)
        scenarios = _random_scenarios(rng, 120)
        mismatches = _run_parity(rng, scenarios, perk=perk)
        assert not mismatches, f"perk={perk} paritesi bozuldu: {mismatches[:5]}"


# ---------------------------------------------------------------------------
# 2) Çıpal ankrar
# ---------------------------------------------------------------------------

def test_empty_board_anchor():
    """Boş tahtada ghost = height - 1 - (şeklin en alt dolu satır ofseti)."""
    board = Board(10, 20)
    for shape_index in range(7):
        for rotations in range(4):
            piece = _make_piece(shape_index, 3, 0, rotations)
            cells = piece.get_cells()
            max_local_y = max(py - piece.y for _, py in cells)
            expected = board.height - 1 - max_local_y
            g = _make_game(board, piece)
            assert g.get_ghost_y() == expected, (
                f"shape={shape_index} rot={rotations} "
                f"ghost={g.get_ghost_y()} expected={expected}"
            )


def test_single_wall_anchor():
    """Tek engel satırında ghost = engel_satırı - 1 - max_dolu_satır_ofseti."""
    board = Board(10, 20)
    # O (2x2, kolonlar 3-4) için satır 10'u kolon 3-4'te doldur.
    board.grid[10][3] = (200, 30, 30)
    board.grid[10][4] = (200, 30, 30)
    board.occupancy[10][3] = True
    board.occupancy[10][4] = True
    piece = Piece(3, 0, 1)  # O
    g = _make_game(board, piece)
    assert g.get_ghost_y() == 8  # 10 - 1 - 1

    # I (bar satır ofseti 1, kolonlar 3-6) için (15, 3) tek engel.
    board2 = Board(10, 20)
    board2.grid[15][3] = (200, 30, 30)
    board2.occupancy[15][3] = True
    piece2 = Piece(3, 0, 0)  # I
    g2 = _make_game(board2, piece2)
    # I bar'ı şeklin satır 1'inde (4x4 kutu): 15 - 1 - 1 = 13
    assert g2.get_ghost_y() == 13


def test_invalid_start_keeps_legacy_return():
    """Mevcut konumu zaten geçersizse eski dönüş (piece.y - 1) korunur."""
    board = Board(10, 20)
    board.grid[5][3] = (200, 30, 30)
    board.occupancy[5][3] = True
    piece = Piece(3, 5, 1)  # O, kendi hücresi dolu → başlangıç geçersiz
    g = _make_game(board, piece)
    assert g.get_ghost_y() == 4  # piece.y - 1 — eski algoritmanın dönüşü
    assert _reference_ghost_y(g) == 4


def test_tunnel_ghost_passes_through_wall():
    """tunnel perk'i ghost'un engelin İÇİNDEN geçmesini korur."""
    board = Board(10, 20)
    for x in range(10):
        board.grid[12][x] = (200, 30, 30)
        board.occupancy[12][x] = True
    piece = Piece(3, 0, 0)  # I
    piece.tunnel = True
    g = _make_game(board, piece)
    # I bar'ı şeklin satır 1'inde: zemin 20 → ghost = 20 - 1 - 1 = 18
    assert g.get_ghost_y() == 18
    # Perk yoksa duvarın üstünde kalır: 12 - 1 - 1 = 10
    piece_plain = Piece(3, 0, 0)
    g2 = _make_game(board, piece_plain)
    assert g2.get_ghost_y() == 10


def test_flexible_border_horizontal_extension():
    """Esnek sınır: x=-1'e taşan parça bayraklıyken düşebilir."""
    board = Board(10, 20)
    piece = Piece(-1, 0, 1)  # O, hücreleri px=-1 ve px=0
    piece.flexible_border = True
    g = _make_game(board, piece)
    assert g.get_ghost_y() == 18
    assert _reference_ghost_y(g) == 18
    # Bayrak yoksa başlangıç geçersiz → eski dönüş piece.y - 1
    piece_plain = Piece(-1, 0, 1)
    g2 = _make_game(board, piece_plain)
    assert g2.get_ghost_y() == -1


# ---------------------------------------------------------------------------
# 3) Oracle eşdeğerliği (sarmalayıcı ↔ _is_valid_cells)
# ---------------------------------------------------------------------------

def test_is_valid_position_wrapper_equivalence():
    rng = random.Random(1810)
    for _ in range(300):
        board = _make_board(rng, density=rng.uniform(0.0, 0.6))
        piece = _make_piece(
            rng.randrange(7), rng.randint(-2, 11), rng.randint(-2, 18),
            rng.randrange(4),
        )
        if rng.random() < 0.2:
            piece.tunnel = True
        if rng.random() < 0.2:
            piece.flexible_border = True
        if rng.random() < 0.2:
            board.flexible_border_active = True
        dx = rng.randint(-3, 3)
        dy = rng.randint(-3, 3)
        via_wrapper = board.is_valid_position(piece, dx, dy)
        via_cells = board._is_valid_cells(piece.get_cells(), dx, dy, piece)
        assert via_wrapper == via_cells, (
            f"sarmalayıcı ≠ _is_valid_cells: dx={dx} dy={dy} "
            f"wrapper={via_wrapper} cells={via_cells}"
        )
