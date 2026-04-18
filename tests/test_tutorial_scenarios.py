# -*- coding: utf-8 -*-
"""Tutorial senaryo veri/evaluator testleri."""

from __future__ import annotations

import importlib
import os
import sys
import unittest
from copy import deepcopy


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
pieces_module = _ensure_real_module('pieces')

list_lessons_for_chapter = tutorial_lessons.list_lessons_for_chapter
build_default_tutorial_progress = tutorial_progress.build_default_tutorial_progress
get_chapter_completion = tutorial_progress.get_chapter_completion
mark_lesson_completed = tutorial_progress.mark_lesson_completed
build_occupancy_from_rows = tutorial_scenarios.build_occupancy_from_rows
count_holes = tutorial_scenarios.count_holes
evaluate_scenario = tutorial_scenarios.evaluate_scenario
get_scenario = tutorial_scenarios.get_scenario
capture_board_metrics = tutorial_scenarios.capture_board_metrics
Piece = pieces_module.Piece
SHAPE_NAMES = pieces_module.SHAPE_NAMES


def _apply_piece_sequence_and_measure(board_rows, placements, *, width=10, height=20):
    occupancy = build_occupancy_from_rows(board_rows, width=width, height=height)
    total_lines_cleared = 0

    def is_valid(candidate):
        for cell_x, cell_y in candidate.get_cells():
            if cell_x < 0 or cell_x >= width or cell_y >= height:
                return False
            if cell_y >= 0 and occupancy[cell_y][cell_x]:
                return False
        return True

    for piece_name, rotation, x in placements:
        piece = Piece(x=x, y=-4, shape_index=SHAPE_NAMES.index(piece_name))
        for _ in range(rotation):
            piece.rotate()

        if not is_valid(piece):
            raise AssertionError('Piece cannot spawn for regression test')
        while True:
            falling = Piece(x=piece.x, y=piece.y + 1, shape_index=SHAPE_NAMES.index(piece_name))
            for _ in range(rotation):
                falling.rotate()
            if is_valid(falling):
                piece = falling
            else:
                break

        locked = deepcopy(occupancy)
        for cell_x, cell_y in piece.get_cells():
            if cell_y < 0:
                raise AssertionError('Piece locked above visible board in regression test')
            locked[cell_y][cell_x] = True

        cleared = 0
        remaining_rows = []
        for row in locked:
            if all(row):
                cleared += 1
            else:
                remaining_rows.append(row)
        while len(remaining_rows) < height:
            remaining_rows.insert(0, [False] * width)
        occupancy = remaining_rows
        total_lines_cleared += cleared

    board_like = type('BoardLike', (), {'occupancy': occupancy, 'lines_cleared': total_lines_cleared})()
    return capture_board_metrics(board_like)


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

    def test_recovery_breathing_room_has_a_two_step_solution(self):
        scenario = get_scenario('recovery_breathing_room')
        initial_metrics = capture_board_metrics(
            type('BoardLike', (), {'occupancy': build_occupancy_from_rows(scenario['board_rows']), 'lines_cleared': 0})()
        )
        after_metrics = _apply_piece_sequence_and_measure(scenario['board_rows'], [('L', 3, 4), ('I', 1, 4)])
        outcome = evaluate_scenario(initial_metrics, after_metrics, scenario['evaluation'])

        self.assertTrue(outcome['success'])
        self.assertGreaterEqual(outcome['line_delta'], 3)
        self.assertLessEqual(outcome['height_delta'], -1)

    def test_recovery_hole_vs_height_requires_hole_reduction(self):
        scenario = get_scenario('recovery_hole_vs_height')
        initial_metrics = capture_board_metrics(
            type('BoardLike', (), {'occupancy': build_occupancy_from_rows(scenario['board_rows']), 'lines_cleared': 0})()
        )
        after_metrics = _apply_piece_sequence_and_measure(scenario['board_rows'], [('J', 1, 0), ('T', 1, 3)])
        outcome = evaluate_scenario(initial_metrics, after_metrics, scenario['evaluation'])

        self.assertTrue(outcome['success'])
        self.assertGreaterEqual(outcome['line_delta'], 2)
        self.assertLessEqual(outcome['hole_delta'], -1)

    def test_recovery_reduce_ceiling_has_hold_setup_solution(self):
        scenario = get_scenario('recovery_reduce_ceiling')
        initial_metrics = capture_board_metrics(
            type('BoardLike', (), {'occupancy': build_occupancy_from_rows(scenario['board_rows']), 'lines_cleared': 0})()
        )
        after_metrics = _apply_piece_sequence_and_measure(scenario['board_rows'], [('J', 1, 3), ('I', 1, 0)])
        outcome = evaluate_scenario(initial_metrics, after_metrics, scenario['evaluation'])

        self.assertTrue(scenario['expected_hold_usage'])
        self.assertEqual(scenario['objectives'][0]['metric'], 'hold_used')
        self.assertTrue(outcome['success'])
        self.assertGreaterEqual(outcome['line_delta'], 4)
        self.assertLessEqual(outcome['height_delta'], -2)

    def test_recovery_wrong_side_has_a_clean_solution(self):
        scenario = get_scenario('recovery_wrong_side')
        initial_metrics = capture_board_metrics(
            type('BoardLike', (), {'occupancy': build_occupancy_from_rows(scenario['board_rows']), 'lines_cleared': 0})()
        )
        after_metrics = _apply_piece_sequence_and_measure(scenario['board_rows'], [('J', 1, 3), ('O', 0, 5)])
        outcome = evaluate_scenario(initial_metrics, after_metrics, scenario['evaluation'])

        self.assertTrue(outcome['success'])
        self.assertGreaterEqual(outcome['line_delta'], 2)
        self.assertLessEqual(outcome['hole_delta'], 0)


class TestTutorialScenarioProgression(unittest.TestCase):
    def test_surface_control_chapter_unlocks_after_quick_start_complete(self):
        progress = build_default_tutorial_progress()
        self.assertFalse(progress['chapters']['surface_control']['unlocked'])
        for lesson in list_lessons_for_chapter('basics'):
            progress = mark_lesson_completed(progress, lesson['id'], 1)
        board_basics = get_chapter_completion(progress, 'board_basics')
        self.assertTrue(board_basics['unlocked'])

    def test_board_scenarios_exist(self):
        lesson_ids = [lesson['id'] for lesson in list_lessons_for_chapter('board_basics')]
        self.assertEqual(
            lesson_ids,
            ['surface_gap_fill', 'surface_keep_low', 'surface_avoid_holes', 'surface_protect_well'],
        )


if __name__ == '__main__':
    unittest.main()