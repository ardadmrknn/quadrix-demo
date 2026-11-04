from __future__ import annotations

import pathlib
import sys

import pytest

ROOT_DIR = pathlib.Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import game_modes_advanced as advanced


pytestmark = [pytest.mark.quadrix_feedback, pytest.mark.quadrix_phase6]


def _mode(score: int):
    mode = advanced.SurvivalMode.__new__(advanced.SurvivalMode)
    mode.game_over = False
    mode.paused = False
    mode.show_exit_prompt = False
    mode.survival_time = 0
    mode.last_level_up_time = 0
    mode.virus_level = 1
    mode.board = type("BoardStub", (), {"score": score})()
    mode.last_antivirus_score = 0
    mode.consumed_count = 0
    mode.antivirus_flash = 0
    mode._activated = 0
    mode._activate_antivirus = lambda: setattr(mode, "_activated", mode._activated + 1)
    mode._update_virus_spread = lambda _dt: None
    mode._spawn_virus_if_needed = lambda: None
    mode._check_consumed_blocks = lambda: None
    return mode


def test_antivirus_threshold_is_5000_and_triggers_on_each_boundary(monkeypatch):
    assert advanced.SurvivalMode.ANTIVIRUS_SCORE == 5000
    monkeypatch.setattr(advanced.Game, "update", lambda _self, _dt: None)

    below = _mode(4999)
    below.update(0)
    assert below._activated == 0
    assert below.last_antivirus_score == 0

    at_first = _mode(5000)
    at_first.update(0)
    assert at_first._activated == 1
    assert at_first.last_antivirus_score == 5000

    at_second = _mode(10_000)
    at_second.update(0)
    assert at_second._activated == 1
    assert at_second.last_antivirus_score == 10_000


def test_survival_shake_values_remain_deferred_and_unchanged():
    source = (SRC_DIR / "game_modes_advanced.py").read_text(encoding="utf-8")
    assert "trigger_screen_shake(intensity=25, duration=50 / 60.0)" in source
    assert "trigger_screen_shake(intensity=30, duration=60 / 60.0)" in source
    assert "trigger_screen_shake(intensity=15, duration=30 / 60.0)" in source

