"""Kozmetik/cila düzeltmeleri için testler:

A) DAS şarj frame'inde dt çift sayımı düzeltmesi (bulgu #5)
B) Döndürmede floor (dikey) kick (bulgu #6)
C) Piece.copy() perk bayraklarını taşıyor (bulgu #8) -> ghost tutarlılığı

Bu fonksiyonlar Pencere 3 kapsamındadır; lock/spawn/gravity/is_valid_position
yüzeylerine dokunulmaz.
"""
import pathlib
import sys
import types


ROOT_DIR = pathlib.Path(__file__).parent
SRC_DIR = ROOT_DIR / 'src'

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import game as game_module  # noqa: E402
from board import Board  # noqa: E402
from pieces import create_piece_by_name  # noqa: E402


# ---------------------------------------------------------------------------
# A) DAS timing
# ---------------------------------------------------------------------------

def _make_das_game():
    game = game_module.Game.__new__(game_module.Game)
    game.current_piece = object()  # sadece None olmaması yeterli
    game.settings_manager = None   # -> DAS_DELAY/DAS_REPEAT (200/200) defaultları
    game.das_direction = 1
    game.das_timer = 0.0
    game.das_repeat_timer = 0.0
    game.das_charged = False
    moves = []
    game._perform_das_move = lambda direction: (moves.append(direction) or True)
    return game, moves


def test_das_charge_frame_does_not_trigger_premature_repeat():
    """Şarjın tamamlandığı frame'de yalnızca tek (şarj) hareketi olmalı;
    delta_time çift sayılıp ikinci bir otomatik tekrar tetiklenmemeli."""
    game, moves = _make_das_game()

    # Gecikme (200ms) + küçük bir overshoot ile tek frame'de şarj ol.
    game._update_das(210.0)

    # Sadece şarj anındaki tek hareket olmalı. Bug'da repeat_timer = 10 + 210 = 220
    # >= 200 olup erken ikinci hareket tetiklenirdi.
    assert moves == [1]
    # overshoot (10ms) repeat_timer'a aktarıldı, delta_time tekrar eklenmedi.
    assert abs(game.das_repeat_timer - 10.0) < 1e-6


def test_das_first_repeat_lands_after_full_repeat_interval():
    """İlk otomatik tekrar, şarj anından tam repeat_ms sonra tetiklenmeli."""
    game, moves = _make_das_game()

    game._update_das(210.0)   # şarj (overshoot 10ms)
    assert moves == [1]

    # 190ms daha: repeat_timer 10 + 190 = 200 -> ilk tekrar tam burada tetiklenir.
    game._update_das(190.0)
    assert moves == [1, 1]


# ---------------------------------------------------------------------------
# B) Floor (dikey) kick
# ---------------------------------------------------------------------------

def _rotate_keydown(module, key):
    return types.SimpleNamespace(type=module.pygame.KEYDOWN, key=key, mod=0)


def _make_rotate_game(piece, board):
    game = game_module.Game.__new__(game_module.Game)
    game.game_over = False
    game.paused = False
    game.show_exit_prompt = False
    game.alt_control_bindings = {}
    game.control_bindings = {
        'pause': game_module.pygame.K_p,
        'rotate': game_module.pygame.K_UP,
        'move_left': game_module.pygame.K_LEFT,
        'move_right': game_module.pygame.K_RIGHT,
        'soft_drop': game_module.pygame.K_DOWN,
        'hold': game_module.pygame.K_c,
        'hold2': game_module.pygame.K_v,
        'hard_drop': game_module.pygame.K_SPACE,
    }
    game.current_piece = piece
    game.board = board
    game.sound = types.SimpleNamespace(play=lambda *a, **k: None)
    return game


def test_floor_kick_allows_rotation_for_grounded_i_piece(monkeypatch):
    """Zemine yaslı yatay I parçası, yalnız yatay kick'lerle dönemese de
    floor kick ile yukarı itilip döndürülebilmeli."""
    board = Board(width=10, height=20)
    # Yatay I: dolu satır y+1 = 18. Dikeye dönünce satır 20'ye taşar; yatay
    # kick (sadece x) bunu çözemez, floor kick (dy=-1) çözer.
    piece = create_piece_by_name('I', x=3, y=17)
    assert board.is_valid_position(piece)

    game = _make_rotate_game(piece, board)
    monkeypatch.setattr(
        game_module.pygame.event, 'get',
        lambda: [_rotate_keydown(game_module, game_module.pygame.K_UP)],
    )

    game.handle_input()

    # Döndürme başarılı olmalı (dikey duruma geçti) ve floor kick ile yukarı itildi.
    assert game.current_piece.rotation_state == 1
    assert game.current_piece.y == 16
    assert game.current_piece.x == 3
    assert board.is_valid_position(game.current_piece)


def test_rotation_undone_safely_when_no_kick_works(monkeypatch):
    """Hiçbir kick işe yaramazsa parça güvenle eski haline döner."""
    board = Board(width=10, height=20)
    # Tüm board'u doldur: hiçbir kick geçerli pozisyon bulamaz.
    for y in range(board.height):
        for x in range(board.width):
            board.occupancy[y][x] = True

    piece = create_piece_by_name('T', x=3, y=5)
    original_x = piece.x
    original_y = piece.y
    original_state = piece.rotation_state

    game = _make_rotate_game(piece, board)
    monkeypatch.setattr(
        game_module.pygame.event, 'get',
        lambda: [_rotate_keydown(game_module, game_module.pygame.K_UP)],
    )

    game.handle_input()

    # Güvenli geri-alma: konum ve rotation_state korunur.
    assert game.current_piece.x == original_x
    assert game.current_piece.y == original_y
    assert game.current_piece.rotation_state == original_state


# ---------------------------------------------------------------------------
# C) copy() perk bayraklarını taşır -> ghost tutarlılığı
# ---------------------------------------------------------------------------

def test_copy_preserves_perk_flags():
    piece = create_piece_by_name('I', x=3, y=0)
    setattr(piece, 'tunnel', True)
    setattr(piece, 'drill', True)
    setattr(piece, 'flexible_border', True)

    clone = piece.copy()

    assert getattr(clone, 'tunnel', False) is True
    assert getattr(clone, 'drill', False) is True
    assert getattr(clone, 'flexible_border', False) is True


def test_copy_without_perk_flags_does_not_invent_them():
    piece = create_piece_by_name('I', x=3, y=0)
    clone = piece.copy()
    assert not hasattr(clone, 'tunnel')
    assert not hasattr(clone, 'drill')
    assert not hasattr(clone, 'flexible_border')


def test_ghost_matches_tunnel_drop_through_occupancy():
    """Tunnel parçasının ghost'u occupancy'yi yok sayarak gerçek (gravity)
    iniş konumuyla tutarlı olmalı; copy() artık tunnel bayrağını taşıdığı için
    ghost bloğun içinden geçerek tabana iner."""
    board = Board(width=10, height=20)
    # Alt satıra bir engel koy.
    board.occupancy[19][3] = True

    piece = create_piece_by_name('I', x=2, y=0)  # dolu hücreler kol 2..5, satır 1
    setattr(piece, 'tunnel', True)

    game = game_module.Game.__new__(game_module.Game)
    game.current_piece = piece
    game.board = board
    game.falling_block_animations = None

    ghost_y = game.get_ghost_y()

    # Tunnel: occupancy yok sayılır -> piece tabana kadar iner.
    # Dolu satır piece.y+1 olduğundan, en alttaki dolu hücre satır 19'da olur:
    # ghost_y + 1 == 19 -> ghost_y == 18.
    assert ghost_y == 18
