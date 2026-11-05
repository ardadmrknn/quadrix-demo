# -*- coding: utf-8 -*-
"""I-11 / S-05 — ARE sırasında rotate/hold/drop tamponlanır.

Önceki test yalnızca kaynak metninde `_pending_rotate` vb. isimleri arıyordu;
isimler yalnızca `__init__`'de başlatıldığı için tampon ÖLÜ KODDU ve test
yeşil kalıyordu. Bu sürüm davranışı ölçer:

  * ARE penceresinde rotate olayı tampona girer (kaybolmaz)
  * Taş doğmadan tampon uygulanmaz
  * Taş doğunca tampon bir kez uygulanır ve tüketilir
  * Tampon taşmaz (sınırlı uzunluk)
"""

import os
import sys
from pathlib import Path

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
os.environ.setdefault('SDL_RENDER_VSYNC', '0')

import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / 'src'
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import pygame  # noqa: E402
from game import Game  # noqa: E402
from settings_manager import SettingsManager  # noqa: E402

pytestmark = [pytest.mark.quadrix_feedback, pytest.mark.quadrix_phase3]


@pytest.fixture()
def game(tmp_path):
    settings = SettingsManager(filename=str(tmp_path / 'settings.json'))
    g = Game(settings_manager=settings, sound_enabled=False)
    g.game_mode = 'classic'
    g.effects_enabled = True
    g.game_over = False
    g.paused = False
    return g


def _rotate_event(game):
    keys = game.control_bindings.get('rotate')
    key = keys[0] if isinstance(keys, (list, tuple)) else keys
    return pygame.event.Event(pygame.KEYDOWN, key=key)


def test_are_window_buffers_rotate_instead_of_dropping_it(game):
    game.current_piece = None
    game._pending_rotate = []
    game._buffer_are_input(_rotate_event(game), game.control_bindings)
    assert len(game._pending_rotate) == 1, (
        'ARE penceresinde basılan rotate kaybolmamalı (S-05)'
    )


def test_buffer_is_not_applied_before_piece_spawns(game):
    game.current_piece = None
    game._pending_rotate = [_rotate_event(game)]
    assert game._take_buffered_are_input() == []
    assert len(game._pending_rotate) == 1, 'taş yokken tampon tüketilmemeli'


def test_buffer_applies_once_when_piece_spawns(game):
    piece = game.next_piece_queue.pop(0)
    game.current_piece = piece
    game._reset_piece_state()
    before = piece.rotation_state
    game._pending_rotate = [_rotate_event(game)]
    pygame.event.clear()
    game.handle_input()
    assert game.current_piece is not None
    assert game.current_piece.rotation_state == (before + 1) % 4
    assert game._pending_rotate == [], 'tampon tek kullanımlık olmalı'


def test_buffer_is_bounded(game):
    game.current_piece = None
    game._pending_rotate = []
    event = _rotate_event(game)
    for _ in range(Game._ARE_INPUT_BUFFER_LIMIT + 12):
        game._buffer_are_input(event, game.control_bindings)
    assert len(game._pending_rotate) == Game._ARE_INPUT_BUFFER_LIMIT, (
        'taşkın girdi tamponu sınırsız büyümemeli'
    )


def test_hold_and_drop_are_buffered_too(game):
    game.current_piece = None
    game._pending_hold = []
    game._pending_drop = []
    hold_keys = game.control_bindings.get('hold')
    drop_keys = game.control_bindings.get('hard_drop')
    hold_key = hold_keys[0] if isinstance(hold_keys, (list, tuple)) else hold_keys
    drop_key = drop_keys[0] if isinstance(drop_keys, (list, tuple)) else drop_keys
    game._buffer_are_input(
        pygame.event.Event(pygame.KEYDOWN, key=hold_key), game.control_bindings
    )
    game._buffer_are_input(
        pygame.event.Event(pygame.KEYDOWN, key=drop_key), game.control_bindings
    )
    assert len(game._pending_hold) == 1
    assert len(game._pending_drop) == 1