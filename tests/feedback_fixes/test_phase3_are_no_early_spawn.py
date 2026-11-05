# -*- coding: utf-8 -*-
"""I-11 / ARE — yeni parça temizleme + düşüş bitmeden doğmaz.

Kullanıcı isteği (2026-11-05): "animasyon bitene kadar temizlenen satırın
üstündeki blok parçaları düşmesin, animasyon bitince düşsün ve düşme işlemi
bitince de yukarıdan yeni parça spawn olsun."

Önceki test yalnızca `inspect.getsource()` içinde `_pending_next_piece`
kelimesini arıyordu; bayrak yazılıyor ama hiç OKUNMUYORDU — parça kilitle aynı
çağrıda doğuyordu ve test bunu kaçırıyordu. Bu sürüm davranışı ölçer.
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

from game import Game  # noqa: E402

pytestmark = [pytest.mark.quadrix_feedback, pytest.mark.quadrix_phase3]


class _Stub:
    """Yalnız spawn/ARE akışını süren oyuncak; gerçek metotları ödünç alır."""

    __test__ = False

    def __init__(self, *, effects_enabled=True, sprint=False, mode='classic'):
        self.effects_enabled = effects_enabled
        self.game_mode = 'sprint' if sprint else mode
        self.spawn_calls = 0
        self._pending_next_piece = False
        self.board = type('B', (), {'level': 1, 'last_cleared_lines': []})()
        self.current_piece = object()
        self.next_piece_queue = [object()]
        self.line_clear_sweep_active = True
        self.falling_block_animations = [{'row': 0, 'col': 0}]

    _is_sprint_mode = Game._is_sprint_mode
    _line_clear_settled = Game._line_clear_settled
    _defer_spawn_for_line_clear = Game._defer_spawn_for_line_clear

    def _spawn_next_piece_from_queue(self):
        self.spawn_calls += 1


def test_spawn_is_deferred_while_sweep_and_fall_are_running():
    stub = _Stub()
    assert stub._defer_spawn_for_line_clear() is True
    assert stub.current_piece is None, (
        'yeni parça animasyon boyunca oyuncunun kontrolüne girmemeli'
    )
    assert stub._pending_next_piece is True


def test_spawn_still_deferred_after_sweep_but_before_fall_finishes():
    stub = _Stub()
    stub.line_clear_sweep_active = False
    assert stub._defer_spawn_for_line_clear() is True, (
        'sweep bitmiş olsa bile üstteki bloklar düşerken parça doğmamalı'
    )


def test_spawn_is_allowed_once_everything_settled():
    stub = _Stub()
    stub.line_clear_sweep_active = False
    stub.falling_block_animations = []
    assert stub._defer_spawn_for_line_clear() is False
    assert stub.current_piece is not None, 'hazır olunca mevcut parça korunmalı'
    assert stub._pending_next_piece is False


def test_sprint_mode_never_defers():
    """Sprint/40L: yarış süresi şişmesin (S-05)."""
    stub = _Stub(sprint=True)
    assert stub._defer_spawn_for_line_clear() is False
    assert stub.current_piece is not None


def test_effects_disabled_never_defers():
    """Efekt kapalıyken animasyon yok; bekleme de olmamalı."""
    stub = _Stub(effects_enabled=False)
    assert stub._defer_spawn_for_line_clear() is False


def test_update_consumes_the_deferred_spawn():
    """`update()` ertelenen parçayı tüketen dalı içermeli (ölü bayrak yasağı)."""
    names = Game.update.__code__.co_names
    assert '_pending_next_piece' in names, (
        'update() ertelenen parçayı tüketmeli; yoksa ARE ölü koddur'
    )
    assert '_spawn_next_piece_from_queue' in names


def test_lock_path_wires_deferral():
    """Kilitleme yolu erteleme kapısını gerçekten çağırmalı."""
    names = Game.lock_and_new_piece.__code__.co_names
    assert '_defer_spawn_for_line_clear' in names