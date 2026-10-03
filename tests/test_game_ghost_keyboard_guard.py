"""Ghost keyboard input korumasının sözleşme testleri (v2'ye özgü).

game.py handle_input, ok tuşu KEYDOWN/KEYUP'larını bağlı bir gamepad'den
"son 150 ms içinde aktif girdi" GELDİYSE yutar (game.py:2312-2323 —
sürücünün/OS'un emüle ettiği mükerrer klavye girdisini önlemek için).
Koruma iki bağımsız saati karşılaştırır: pygame.time.get_ticks() (SDL
uptime) ile GamepadManager._last_gamepad_input_time (poll delta'larından
biriken iç saat).

Görev #59 kök nedeni: iki saat de 0'ken (başlıksız test ortamında time
modülü başlatılmamış → get_ticks() == 0; manager hiç poll edilmemiş →
last_input == 0) "0 - 0 < 150" true döner ve HİÇ girdi gelmemiş bir
gamepad, klavye ok tuşunu "şimdi girdi var" sanarak yutardı. Fiziksel
gamepad bağlı makinede test_game_polish_das_rotate_ghost.py::test_floor_
kick_allows_rotation_for_grounded_i_piece bu yüzden state == 0'da
kalıyordu — kick mantığı sağlamdı. Kaynak düzeltmesi: last_input == 0
("hiç girdi gelmedi") artık yutma koşuluna girmez (game.py:2322).

Bu dosya korumayı sahte manager ile DETERMİNİSTİK kilitler (fiziksel
gamepad bağlı olup olmamasından bağımsız). İki repoda da birebir aynı
dosyadır (2026-10-04: koruma demo'ya v2'den port edildi).

PATCH HEDELBİRLİĞİ NOTU: get_ticks patch'i game_module.pygame.time
üzerinden yapılır (pygame.time DEĞİL). tests/conftest.py her test
dosyası koleksiyonunda pygame ailesini sys.modules'tan düşürür ama
`game` modülünü düşürmez; çok dosyalı koşularda game.py'nin bağlı olduğu
pygame nesnesi, bu dosyanın import ettiği taze pygame'den FARKLI olabilir.
Patch daima oyunun kendi binding'ine (game_module.pygame.*) uygulanmalı —
pygame.event.get için test_game_polish_das_rotate_ghost.py de aynı deseni
kullanır.

Desen referansı: tests/test_game_polish_das_rotate_ghost.py
(_make_rotate_game + monkeypatch'li pygame.event.get).
"""

from __future__ import annotations

import pathlib
import sys
import types

import pytest

ROOT_DIR = pathlib.Path(__file__).parent
SRC_DIR = ROOT_DIR / 'src'

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import pygame  # noqa: E402

import game as game_module  # noqa: E402
import gamepad_manager as gm_module  # noqa: E402
from board import Board  # noqa: E402
from pieces import create_piece_by_name  # noqa: E402


class _FakeGamepadManager:
    """Guard'ın okuduğu iki yüzey: is_connected + get_last_input_time."""

    def __init__(self, last_input_time: int):
        self._last_input_time = last_input_time

    def is_connected(self) -> bool:
        return True

    def get_last_input_time(self) -> int:
        return self._last_input_time


def _keydown(key):
    return types.SimpleNamespace(type=pygame.KEYDOWN, key=key, mod=0)


def _make_guard_game(piece, board):
    """test_game_polish_das_rotate_ghost.py::_make_rotate_game deseni."""
    game = game_module.Game.__new__(game_module.Game)
    game.game_over = False
    game.paused = False
    game.show_exit_prompt = False
    game.alt_control_bindings = {}
    game.control_bindings = {
        'pause': pygame.K_p,
        'rotate': pygame.K_UP,
        'move_left': pygame.K_LEFT,
        'move_right': pygame.K_RIGHT,
        'soft_drop': pygame.K_DOWN,
        'hold': pygame.K_c,
        'hold2': pygame.K_v,
        'hard_drop': pygame.K_SPACE,
    }
    game.current_piece = piece
    game.board = board
    game.sound = types.SimpleNamespace(play=lambda *a, **k: None)
    return game


@pytest.mark.parametrize('last_input_time, now_ms, should_move', [
    # Görev #59: iki saat de 0 — "hiç girdi gelmedi" yutma sebebi DEĞİL.
    (0, 0, True),
    # Süreç başlangıcı penceresi (now < 150) — yine hiç girdi yok.
    (0, 140, True),
    # Aktif kullanım: girdi 50ms önce → mükerrer klavye emülasyonu YUTULUR.
    (950, 1000, False),
    # Bayat girdi: 900ms önce → klavye geçer.
    (100, 1000, True),
])
def test_ghost_keyboard_guard_requires_recent_gamepad_input(
    monkeypatch, last_input_time, now_ms, should_move,
):
    """Koruma yalnız GERÇEKTEN son 150ms'de gamepad girdisi VARSA yutar;
    hiç girdi gelmemiş (last == 0) gamepad klavye ok tuşunu engellemez."""
    board = Board(width=10, height=20)
    piece = create_piece_by_name('I', x=4, y=5)
    game = _make_guard_game(piece, board)

    # handle_input içinden çağrılan get_gamepad_manager modül düzeyinde
    # çözülür → sahte manager gerçek donanımı hiç başlatmaz.
    # Kimlik-bölünmesi (çok-dosyalı koşu): handle_input'in ÇAĞRI-ZAMANI
    # `from gamepad_manager import ...` çözümlemesi sys.modules'ten okur;
    # bu dosyanın gm_module'ü farklı bir nesliğe bölünmüşse yama görünmez
    # olurdu (denetim bulgusu: toplu koşuda sıra bağımlı yanlış-negatif).
    # Bu yüzden gm_module'ü sys.modules'in HER İKİ anahtarına sabitle.
    monkeypatch.setitem(sys.modules, 'gamepad_manager', gm_module)
    monkeypatch.setitem(sys.modules, 'src.gamepad_manager', gm_module)
    monkeypatch.setattr(
        gm_module, 'get_gamepad_manager',
        lambda: _FakeGamepadManager(last_input_time),
    )
    # game_module.pygame.* — oyunun kendi pygame binding'i (bkz. modül
    # docstring'i: conftest koleksiyon sınırında pygame'i yeniden import
    # ettirebilir; bu dosyanın pygame'i farklı bir nesne olabilir).
    monkeypatch.setattr(game_module.pygame.time, 'get_ticks', lambda: now_ms)
    monkeypatch.setattr(
        game_module.pygame.event, 'get',
        lambda: [_keydown(pygame.K_LEFT)],
    )

    game.handle_input()

    if should_move:
        assert piece.x == 3, 'klavye sola hareketi işlenmeli'
    else:
        assert piece.x == 4, 'mükerrer klavye girdisi yutulmalı'
