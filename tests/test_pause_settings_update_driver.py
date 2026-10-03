"""GP-004 (kapsam) — duraklatma-ayarları overlay update() sürücüsü testleri.

İade incelemesinde doğrulanan eksik kapsam: GP-004 düzeltmesi yalnızca
main.py _handle_settings döngüsüne settings_screen.update(delta_ms)
eklemişti; oyun içi duraklatma menüsünden açılan ayarlar ekranı
(game.py _ensure_pause_settings_screen) da tam bir TabbedSettingsScreen
örneğidir ve update() ALMIYORDU — capture sırasında hold-to-clear
ilerlemesi bu yolda hiç çalışmıyordu.

Bu testler Game.update() erken çıkışında (paused) pause-settings
instance'ına update() çağrısının iletildiğini doğrular.
"""

from __future__ import annotations

import os
import sys

import pytest


def _ensure_src_on_path() -> None:
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    src_path = os.path.join(repo_root, 'src')
    if src_path not in sys.path:
        sys.path.insert(0, src_path)


@pytest.fixture(scope='module')
def game_module():
    os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
    os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
    _ensure_src_on_path()

    import pygame
    if not hasattr(pygame, 'K_h'):
        pytest.skip('pygame stub environment')

    import game as game_module
    return game_module


class _FakePauseSettings:
    def __init__(self):
        self.update_calls = []

    def update(self, dt):
        self.update_calls.append(dt)


def _make_paused_game(game_module, pause_settings_active=True, game_over=False):
    game = game_module.Game.__new__(game_module.Game)
    game.game_over = game_over
    game.paused = not game_over
    game.show_exit_prompt = False
    game.game_over_warning_timer = 0
    game._pause_settings_active = pause_settings_active
    fake = _FakePauseSettings()
    ensure_calls = []

    def _fake_ensure():
        ensure_calls.append(1)
        return fake

    game._ensure_pause_settings_screen = _fake_ensure
    return game, fake, ensure_calls


def test_pause_settings_update_called_each_frame(game_module):
    game, fake, ensure_calls = _make_paused_game(game_module)
    game.update(16.0)
    game.update(16.0)
    assert ensure_calls, '_ensure_pause_settings_screen çağrılmalı'
    assert fake.update_calls == [16.0, 16.0], \
        'duraklatma-ayarları ekranı her karede update() almalı (GP-004)'


def test_pause_settings_update_skipped_without_overlay(game_module):
    game, fake, ensure_calls = _make_paused_game(game_module, pause_settings_active=False)
    game.update(16.0)
    assert not ensure_calls, 'overlay kapalıyken ensure çağrılmamalı'
    assert fake.update_calls == []


def test_pause_settings_update_skipped_when_game_over(game_module):
    game, fake, ensure_calls = _make_paused_game(game_module, game_over=True)
    game.update(16.0)
    assert not ensure_calls
    assert fake.update_calls == []
