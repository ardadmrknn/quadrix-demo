# -*- coding: utf-8 -*-
"""Tutorial senaryo veri/evaluator testleri."""

from __future__ import annotations

import importlib
import os
import sys
import unittest


ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
SRC_DIR = os.path.join(ROOT_DIR, 'src')
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)


def _ensure_real_module(module_name: str):
    existing = sys.modules.get(module_name)
    module_path = getattr(existing, '__file__', '') if existing is not None else ''
    if existing is not None and (not module_path or os.path.abspath(module_path).startswith(os.path.abspath(SRC_DIR)) is False):
        sys.modules.pop(module_name, None)
    return importlib.import_module(module_name)


tutorial_lessons = _ensure_real_module('tutorial_lessons')
tutorial_progress = _ensure_real_module('tutorial_progress')
tutorial_scenarios = _ensure_real_module('tutorial_scenarios')

list_lessons_for_chapter = tutorial_lessons.list_lessons_for_chapter
build_default_tutorial_progress = tutorial_progress.build_default_tutorial_progress
get_chapter_completion = tutorial_progress.get_chapter_completion
mark_lesson_completed = tutorial_progress.mark_lesson_completed
build_occupancy_from_rows = tutorial_scenarios.build_occupancy_from_rows
count_holes = tutorial_scenarios.count_holes
evaluate_scenario = tutorial_scenarios.evaluate_scenario
get_scenario = tutorial_scenarios.get_scenario


class TestTutorialScenarioHelpers(unittest.TestCase):
    def test_build_occupancy_bottom_aligns_rows(self):
        occupancy = build_occupancy_from_rows(["XX..", ".X.."], width=4, height=4)
        self.assertEqual(occupancy[2], [True, True, False, False])
        self.assertEqual(occupancy[3], [False, True, False, False])

    def test_count_holes_detects_internal_gaps(self):
        occupancy = build_occupancy_from_rows(["X.", "..", "X."], width=2, height=3)
        self.assertEqual(count_holes(occupancy), 1)

    def test_gap_fill_scenario_rewards_clean_clear(self):
        scenario = get_scenario('gap_fill_double')
        initial_metrics = {
            'holes': 0,
            'max_height': 2,
            'lines_cleared': 0,
        }
        after_metrics = {
            'holes': 0,
            'max_height': 0,
            'lines_cleared': 2,
        }
        outcome = evaluate_scenario(initial_metrics, after_metrics, scenario['evaluation'])
        self.assertTrue(outcome['success'])
        self.assertEqual(outcome['stars'], 3)

    def test_keep_stack_low_fails_when_height_jumps(self):
        scenario = get_scenario('keep_stack_low')
        initial_metrics = {
            'holes': 0,
            'max_height': 4,
            'lines_cleared': 0,
        }
        after_metrics = {
            'holes': 0,
            'max_height': 6,
            'lines_cleared': 0,
        }
        outcome = evaluate_scenario(initial_metrics, after_metrics, scenario['evaluation'])
        self.assertFalse(outcome['success'])
        self.assertEqual(outcome['feedback_key'], 'stack_too_high')


class TestTutorialScenarioProgression(unittest.TestCase):
    def test_board_basics_chapter_unlocks_after_basics_complete(self):
        progress = build_default_tutorial_progress()
        self.assertFalse(progress['chapters']['board_basics']['unlocked'])
        for lesson in list_lessons_for_chapter('basics'):
            progress = mark_lesson_completed(progress, lesson['id'], 1)
        board_basics = get_chapter_completion(progress, 'board_basics')
        self.assertTrue(board_basics['unlocked'])

    def test_board_scenarios_exist(self):
        lesson_ids = [lesson['id'] for lesson in list_lessons_for_chapter('board_basics')]
        self.assertEqual(
            lesson_ids,
            ['board_gap_fill', 'board_keep_low', 'board_vertical_well'],
        )


if __name__ == '__main__':
    unittest.main()