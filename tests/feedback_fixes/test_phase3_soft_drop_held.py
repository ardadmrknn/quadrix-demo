# -*- coding: utf-8 -*-
"""Soft drop basılı-tutma regresyonu — ScancodeWrapper keycode sözleşmesi.

KÖK NEDEN (2026-11-05): `pygame.key.get_pressed()` bir `ScancodeWrapper`
döndürür; 512 elemanlıdır ama `__getitem__` verilen değeri keycode kabul edip
`SDL_GetScancodeFromKey` ile scancode'a çevirir. Kod bu nesneyi
`key < len(pressed)` uzunluk kapısıyla okuyordu; ok tuşları
(`K_DOWN = 1073741905`) 512'nin üstünde olduğu için kapı daima `False`
dönüyordu. Sonuç: aşağı tuşuna basıldığı anda KEYDOWN yolu mevcut parçaya SDF
uyguluyor, ama basılı tutuldukça yoklama ölü olduğu için SONRAKİ parçalar
normal hızda iniyordu.

Bu testler davranışı ölçer; kaynak metninde isim aramaz:
  * `is_key_held` ok tuşu keycode'unu doğru okur (uzunluk kapısı YOK)
  * Aşağı tuşu basılıyken parça değişse de fall_speed soft hedefte kalır
  * Soft drop satır başına 1 puan verir; normal gravity puan vermez
  * Tuş basılıyken doğan parça ilk karesinde normal hıza sıçramaz
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

import game as game_module  # noqa: E402
from game import Game  # noqa: E402
from platform_utils import is_key_held  # noqa: E402
from settings_manager import SettingsManager  # noqa: E402

pytestmark = [pytest.mark.quadrix_feedback, pytest.mark.quadrix_phase3]

FRAME_MS = 1000.0 / 60.0
# Gerçek ScancodeWrapper uzunluğu (SDL_NUM_SCANCODES).
_SCANCODE_WRAPPER_LEN = 512


class FakeScancodeWrapper:
    """`pygame.key.get_pressed()` sözleşmesini birebir taklit eder.

    Uzunluk 512'dir ama indeks KEYCODE'dur. Önceki sondalar `__len__`'i
    `max(active)+1` yaptığı için `key < len(pressed)` kapısını yanlışlıkla
    geçiriyor ve kusuru maskeliyordu; bu fake o maskeyi kaldırır.
    """

    def __init__(self, active=()):
        self._active = {int(k) for k in active}

    def __len__(self):
        return _SCANCODE_WRAPPER_LEN

    def __getitem__(self, code):
        try:
            code = int(code)
        except (TypeError, ValueError):
            return False
        if code < 0:
            return False
        return code in self._active

    def __iter__(self):
        raise TypeError('Iterating over key states is not supported')


@pytest.fixture()
def game(tmp_path, monkeypatch):
    settings = SettingsManager(filename=str(tmp_path / 'settings.json'))
    # Demo'da `sdf` ayarı yok; aralık doğrudan `soft_drop_speed`tir.
    settings.settings['soft_drop_speed'] = 50
    g = Game(settings_manager=settings, sound_enabled=False)
    g.game_mode = 'classic'
    g.effects_enabled = False
    g.game_over = False
    g.paused = False
    _install_keys(monkeypatch, [])
    return g


def _install_keys(monkeypatch, active):
    monkeypatch.setattr(
        game_module.pygame.key,
        'get_pressed',
        lambda: FakeScancodeWrapper(active),
        raising=True,
    )


def _soft_key(game):
    bindings = getattr(game, 'control_bindings', None) or {}
    return int(bindings.get('soft_drop', pygame.K_DOWN))


def test_arrow_keycodes_are_above_wrapper_length():
    """Kusurun ön koşulu: ok tuşu keycode'u 512'den büyük, indeksleme yine çalışır."""
    assert pygame.K_DOWN > _SCANCODE_WRAPPER_LEN, (
        'K_DOWN 512 altına düştüyse uzunluk kapısı yeniden "doğru" görünür; '
        'bu testin varsayımı geçersiz olur'
    )
    state = FakeScancodeWrapper([pygame.K_DOWN])
    assert len(state) == _SCANCODE_WRAPPER_LEN
    assert is_key_held(pygame.K_DOWN, state) is True
    assert is_key_held(pygame.K_UP, state) is False
    assert is_key_held('not-a-key', state) is False
    assert is_key_held(-1, state) is False


def test_held_soft_drop_survives_piece_changes(game, monkeypatch):
    """Basılı tutuldukça SONRAKİ parçalar da soft hızda inmeli."""
    soft_key = _soft_key(game)
    soft_target = game.get_soft_drop_speed()
    normal = float(game.get_current_speed())
    assert 0.0 < soft_target < normal, 'SDF ön koşulu: soft aralık normalden küçük olmalı'

    _install_keys(monkeypatch, [soft_key])

    piece = game.current_piece
    speeds_per_piece = []
    current = []
    for _ in range(400):
        game.update(FRAME_MS)
        if game.current_piece is not piece:
            speeds_per_piece.append(current)
            current = []
            piece = game.current_piece
            if len(speeds_per_piece) >= 4:
                break
        if piece is not None:
            current.append(float(game.fall_speed))

    assert len(speeds_per_piece) >= 4, 'ölçüm için en az 4 parça gerekli'
    for index, speeds in enumerate(speeds_per_piece[:4]):
        assert speeds, f'parça #{index} için hiç kare ölçülmedi'
        off_target = [s for s in speeds if abs(s - soft_target) > 0.5]
        assert not off_target, (
            f'parça #{index} basılı tutulurken normal hıza döndü: {sorted(set(off_target))} '
            f'(soft hedef {soft_target})'
        )


def test_new_piece_does_not_blip_to_normal_speed_while_held(game, monkeypatch):
    """Tuş basılıyken doğan parçanın ilk karesi normal hız olmamalı."""
    soft_key = _soft_key(game)
    soft_target = game.get_soft_drop_speed()
    normal = float(game.get_current_speed())

    _install_keys(monkeypatch, [soft_key])
    previous_piece = game.current_piece
    first_speed_after_spawn = None
    for _ in range(400):
        game.update(FRAME_MS)
        if game.current_piece is not previous_piece:
            first_speed_after_spawn = float(game.fall_speed)
            break
        previous_piece = game.current_piece

    assert first_speed_after_spawn is not None, 'parça değişimi gözlenmedi'
    assert abs(first_speed_after_spawn - soft_target) <= 0.5, (
        f'doğan parça {first_speed_after_spawn} ms ile başladı; '
        f'soft hedef {soft_target}, normal {normal}'
    )


def test_soft_drop_awards_one_point_per_row(game, monkeypatch):
    """Soft drop ile inen parça satır başına 1 puan kazandırır."""
    soft_key = _soft_key(game)

    # Taze tahtada parça gizli bantta başlar; önce normal hızda görünür alana indir.
    _install_keys(monkeypatch, [])
    for _ in range(45):
        game.update(FRAME_MS)

    piece = game.current_piece
    assert piece is not None
    start_y = piece.y
    start_score = game.board.score

    _install_keys(monkeypatch, [soft_key])
    moved = 0
    for _ in range(300):
        game.update(FRAME_MS)
        if game.current_piece is not piece:
            break
        moved = piece.y - start_y

    gained = game.board.score - start_score
    assert moved > 0, 'soft drop parçayı hiç indirmedi'
    assert gained == moved, f'{moved} satır için {gained} puan verildi (beklenen {moved})'


def test_ordinary_gravity_awards_no_soft_drop_points(game, monkeypatch):
    """Tuş basılı değilken inen parça puan kazandırmamalı."""
    _install_keys(monkeypatch, [])
    start_score = game.board.score
    for _ in range(90):
        game.update(FRAME_MS)
    assert game.board.score == start_score


def test_release_restores_normal_speed(game, monkeypatch):
    """Tuş bırakılınca normal düşüş hızına dönülmeli."""
    soft_key = _soft_key(game)
    soft_target = game.get_soft_drop_speed()
    normal = float(game.get_current_speed())

    _install_keys(monkeypatch, [soft_key])
    game.update(FRAME_MS)
    assert abs(float(game.fall_speed) - soft_target) <= 0.5

    _install_keys(monkeypatch, [])
    game.update(FRAME_MS)
    assert abs(float(game.fall_speed) - normal) <= 0.5