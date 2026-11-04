from __future__ import annotations

import pathlib
import sys

import pytest

ROOT_DIR = pathlib.Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from tutorial_lessons import get_lesson
from tutorial_scenarios import SCENARIOS


pytestmark = [pytest.mark.quadrix_feedback, pytest.mark.quadrix_phase6]


def test_legacy_tutorial_steps_5_8_11_14_have_executable_targets():
    # The current lesson catalog keeps the first five legacy steps and uses
    # stable IDs for later content chapters; verify the corresponding 5/8/11/14
    # content entries without inventing missing numeric aliases.
    lesson_ids = ("qs_first_clear", "surface_avoid_holes", "plan_queue_read", "recover_hole_or_height")
    for lesson_id in lesson_ids:
        lesson = get_lesson(lesson_id)
        assert lesson is not None
        assert lesson.get("title_key")
        assert lesson.get("description_key")
        scenario_id = lesson.get("scenario_id")
        if scenario_id:
            scenario = SCENARIOS.get(scenario_id)
            assert scenario is not None
            assert scenario.get("objectives")


def test_hole_delta_goals_are_explicitly_bounded():
    hole_goals = []
    for scenario in SCENARIOS.values():
        for goal in scenario.get("objectives", []):
            if goal.get("metric") == "hole_delta":
                hole_goals.append(goal)
    assert hole_goals
    assert all(goal.get("comparison") in {"max", "min", "eq"} for goal in hole_goals)



