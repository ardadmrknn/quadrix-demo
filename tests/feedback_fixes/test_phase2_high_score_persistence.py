"""I-45: yüksek skorların kayıpsız ve tekrar denemeli kalıcılığı."""

from __future__ import annotations

import importlib
import json
import sys
import threading
import types
from pathlib import Path

import pytest

pytestmark = [pytest.mark.quadrix_feedback, pytest.mark.quadrix_phase2]
HIGH_SCORE = 1_000_457_432


@pytest.mark.parametrize("score", [999_999_999, 1_000_000_000, HIGH_SCORE, 2_147_483_647, 2_147_483_648, 9_007_199_254_740_993])
def test_high_score_round_trips_exactly_through_json(tmp_path, monkeypatch, score):
    monkeypatch.setenv("QUADRIX_DATA_DIR", str(tmp_path / "data"))
    from score_manager import ScoreManager

    path = tmp_path / "highscores.json"
    manager = ScoreManager(str(path))
    assert manager.add_score(score, 4_832, 967, tetrises=317) == 1
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["highscores"][0]["score"] == score
    assert isinstance(payload["highscores"][0]["score"], int)
    reloaded = ScoreManager(str(path))
    assert reloaded.highscores[0]["score"] == score
    assert reloaded.stats["total_score"] == score


def _fail_first_atomic_write(monkeypatch):
    module = importlib.import_module("score_manager")
    real_write = module.atomic_write_json
    calls = []

    def flaky_write(*args, **kwargs):
        calls.append(args[0])
        if len(calls) == 1:
            raise OSError("temporary locked file")
        return real_write(*args, **kwargs)

    monkeypatch.setattr(module, "atomic_write_json", flaky_write)
    return module, calls


def test_atomic_write_failure_stays_pending_until_forced_retry(tmp_path, monkeypatch):
    module, calls = _fail_first_atomic_write(monkeypatch)
    path = tmp_path / "scores.json"
    manager = module.ScoreManager(str(path))
    assert manager.add_score(HIGH_SCORE, 4_832, 967) == 1
    assert manager._dirty is True
    assert not path.exists()
    assert manager.highscores[0]["score"] == HIGH_SCORE
    assert manager.stats["total_games"] == 1

    assert manager.flush_if_due() is False
    assert len(calls) == 1
    assert manager.flush_if_due(force=True) is True
    assert manager._dirty is False
    assert len(calls) == 2
    assert module.ScoreManager(str(path)).highscores[0]["score"] == HIGH_SCORE
    assert manager.flush_if_due(force=True) is False
    assert len(calls) == 2


def test_repeated_write_failures_use_monotonic_backoff(tmp_path, monkeypatch):
    module = importlib.import_module("score_manager")
    now = [100.0]
    calls = []
    monkeypatch.setattr(module.time, "monotonic", lambda: now[0])

    def failing_write(*args, **kwargs):
        calls.append(args[0])
        raise OSError("still locked")

    monkeypatch.setattr(module, "atomic_write_json", failing_write)
    manager = module.ScoreManager(str(tmp_path / "scores.json"))
    manager.add_score(HIGH_SCORE, 4_832, 967)
    now[0] = 101.99
    assert manager.flush_if_due() is False
    assert len(calls) == 1
    now[0] = 102.0
    assert manager.flush_if_due() is False
    assert len(calls) == 2
    assert manager._dirty is True
    now[0] = 103.99
    assert manager.flush_if_due() is False
    assert len(calls) == 2


def test_finalize_retry_does_not_crash_or_duplicate_run_counters(tmp_path, monkeypatch):
    from game import Game

    module, calls = _fail_first_atomic_write(monkeypatch)
    # Steam worker is external to the local persistence contract.
    monkeypatch.setattr(threading, "Thread", lambda **kwargs: types.SimpleNamespace(start=lambda: None))
    manager = module.ScoreManager(str(tmp_path / "scores.json"))
    user_calls = {"update": 0, "flush": 0}

    def update_user_stats(**kwargs):
        user_calls["update"] += 1

    def flush_users_if_due(force=False):
        user_calls["flush"] += int(force)

    game = Game.__new__(Game)
    game._score_recorded = False
    game._suppress_progression_tracking = False
    game.game_time = 0
    game.game_mode = "classic"
    game.score_manager = manager
    game.user_manager = types.SimpleNamespace(update_user_stats=update_user_stats, flush_users_if_due=flush_users_if_due)
    game.achievement_manager = None
    game.board = types.SimpleNamespace(score=HIGH_SCORE, lines_cleared=4_832, level=967, tetrises=317, combo=0)
    Game.finalize_run(game)
    assert game._score_recorded is True
    assert manager._dirty is True
    assert manager.stats["total_games"] == 1
    assert user_calls["update"] == 1

    Game.finalize_run(game)
    Game.finalize_run(game)
    assert len(calls) == 2
    assert manager._dirty is False
    assert manager.stats["total_games"] == 1
    assert len(manager.highscores) == 1
    assert user_calls["update"] == 1
    assert user_calls["flush"] == 2


def test_main_flushes_pending_scores_on_frame_restart_and_shutdown():
    source = (Path(__file__).resolve().parents[2] / "src" / "main.py").read_text(encoding="utf-8")
    restart = source[source.index("    def _restart_application"):source.index("    def _restart_application") + 2200]
    assert "score_manager.flush_if_due(force=True)" in restart
    assert "score_manager.flush_if_due()" in source
    assert source.count("score_manager.flush_if_due(force=True)") >= 2
