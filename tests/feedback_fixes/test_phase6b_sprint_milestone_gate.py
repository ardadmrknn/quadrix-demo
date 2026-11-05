"""Faz 6b / I-47 + S-19 — Sprint/40L'de milestone kutlaması kapalı.

S-09 Sprint HUD'undan skor satırını kaldırdı. Skoru gizleyip skoru kutlamak
tutarsız olduğu için S-19 ile milestone bloğu bu modlarda tamamen kapatıldı:
havai fişek yok, kutlama sesi yok, `last_milestone_score` güncellenmez.

Kılavuz artık mod kümesini tek kaynakta (`SPRINT_MODE_KEYS`) tutuyor;
HUD kapısı, gravity kapısı ve milestone kapısı aynı kümeyi paylaşır.
"""

import os
import sys

import pytest

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
os.environ.setdefault('SDL_RENDER_VSYNC', '0')

SRC_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

pytestmark = pytest.mark.quadrix_feedback


SPRINT_MODES = ('sprint', '40l', '40_lines', '40-lines')
NON_SPRINT_MODES = ('classic', 'mystery', 'campaign')


def _make_game(tmp_path, mode):
    from settings_manager import SettingsManager
    from game import Game

    path = tmp_path / 'settings.json'
    settings = SettingsManager(filename=str(path))
    return Game(
        sound_enabled=False,
        effects_enabled=False,
        settings_manager=settings,
        game_mode=mode,
    )


def _advance(game, frames=1):
    for _ in range(frames):
        game.update(16)


@pytest.mark.quadrix_phase6b
def test_sprint_mode_keys_single_source():
    """Mod kumesi tek yerde tanimli olmali; kopya listeler geri gelmemeli."""
    import inspect
    from game import Game, SPRINT_MODE_KEYS

    assert SPRINT_MODE_KEYS == frozenset(SPRINT_MODES)

    update_source = inspect.getsource(Game.update)
    assert "'40_lines'" not in update_source, 'milestone blogunda kopya mod listesi var'
    assert 'SPRINT_MODE_KEYS' not in inspect.getsource(Game.update) or '_is_sprint_mode' in update_source


@pytest.mark.quadrix_phase6b
@pytest.mark.parametrize('mode', SPRINT_MODES)
def test_sprint_mode_does_not_start_milestone_celebration(tmp_path, mode):
    game = _make_game(tmp_path, mode)
    try:
        game.board.score = 1000
        _advance(game, frames=2)
        assert game.firework_active is False, f'{mode}: havai fisek baslamamali'
        assert game.last_milestone_score == 0, f'{mode}: milestone isareti guncellenmemeli'
    finally:
        try:
            game.quit()
        except Exception:
            pass


@pytest.mark.quadrix_phase6b
@pytest.mark.parametrize('mode', NON_SPRINT_MODES)
def test_other_modes_still_celebrate_milestones(tmp_path, mode):
    """S-19 yalniz Sprint ailesini kapatir; diger modlar bozulmamali."""
    game = _make_game(tmp_path, mode)
    try:
        game.board.score = 1000
        _advance(game, frames=2)
        assert game.firework_active is True, f'{mode}: milestone kutlamasi devam etmeli'
        assert game.last_milestone_score == 1000
    finally:
        try:
            game.quit()
        except Exception:
            pass


@pytest.mark.quadrix_phase6b
def test_sprint_milestone_gate_is_checked_before_threshold_scan():
    """Kapi erken cikmali: Sprint'te esik taramasi ve ses cagrisi hic calismaz."""
    import inspect
    from game import Game

    source = inspect.getsource(Game.update)
    gate = source.index('if not self._is_sprint_mode():')
    threshold_scan = source.index('MILESTONE_THRESHOLDS = [1000')
    sound_call = source.index("self.sound.play('tetris')")
    assert gate < threshold_scan < sound_call


@pytest.mark.quadrix_phase6b
def test_hud_and_gravity_share_the_same_gate():
    import inspect
    from game import Game

    assert '_is_sprint_mode()' in inspect.getsource(Game._automatic_gravity_paused)
    # Demo'da HUD cizim metodu v2'deki `_draw_right_hud_panel_core` degil
    # `_draw_right_hud_panel_body`; sozlesme ayni, ad farkli.
    assert '_is_sprint_mode()' in inspect.getsource(Game._draw_right_hud_panel_body)