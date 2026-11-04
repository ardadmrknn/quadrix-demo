from __future__ import annotations

import json
import pathlib
import sys

import pytest

ROOT_DIR = pathlib.Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from menu import Menu


pytestmark = [pytest.mark.quadrix_feedback, pytest.mark.quadrix_phase6]


class _Users:
    def __init__(self, path):
        self.path = str(path)

    def get_user_data(self):
        return {}

    def get_achievements_file(self):
        return self.path


def _panel_data(tmp_path, payload):
    path = tmp_path / "achievements.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    menu = Menu.__new__(Menu)
    menu.user_manager = _Users(path)
    menu._achievements_panel_cache = {
        "path": None,
        "mtime": None,
        "recent": [],
        "percent": 0,
    }
    return Menu._get_recent_achievements_panel_data(menu, "tr")


def test_badge_is_off_when_all_unlocked_rewards_are_claimed(tmp_path):
    recent, percent, has_unclaimed = _panel_data(
        tmp_path,
        {"unlocked": {"first_game": "2026-01-01 00:00"}, "claimed_rewards": ["first_game"]},
    )
    assert has_unclaimed is False


def test_badge_is_on_for_an_unclaimed_unlock(tmp_path):
    recent, percent, has_unclaimed = _panel_data(
        tmp_path,
        {"unlocked": {"first_game": "2026-01-01 00:00"}, "claimed_rewards": []},
    )
    assert has_unclaimed is True
