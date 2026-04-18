# -*- coding: utf-8 -*-
"""Tutorial scenario runtime regression tests for V2 lesson flow."""

from __future__ import annotations

import importlib
import os
import sys
import types
import unittest
from unittest import mock


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


tutorial_module = _ensure_real_module('tutorial')
tutorial_scenarios = _ensure_real_module('tutorial_scenarios')
pieces_module = _ensure_real_module('pieces')

TutorialMode = tutorial_module.TutorialMode
create_piece_by_name = pieces_module.create_piece_by_name
get_scenario = tutorial_scenarios.get_scenario


class TestTutorialScenarioFlowV2(unittest.TestCase):
    def test_build_piece_queue_preserves_full_defined_sequence(self):
        tutorial = TutorialMode.__new__(TutorialMode)
        tutorial._create_named_piece = lambda name: name
        tutorial.spawn_new_piece = lambda: 'RANDOM'

        queue = TutorialMode._build_piece_queue(tutorial, ['I', 'L', 'J', 'O'])

        self.assertEqual(queue, ['I', 'L', 'J', 'O'])

    def test_scenario_hold_consumes_queue_and_disables_reuse(self):
        tutorial = TutorialMode.__new__(TutorialMode)
        tutorial._scenario_allow_hold = True
        tutorial.can_hold = True
        tutorial.in_transition = False
        tutorial.current_piece = create_piece_by_name('T')
        tutorial.held_piece = None
        tutorial.next_piece_queue = [create_piece_by_name('I'), create_piece_by_name('O')]
        tutorial.lesson_runtime_state = {}
        tutorial._register_step_activity = lambda: None
        tutorial._sync_lesson_runtime_state = lambda: None
        tutorial._skip_hidden_rows = lambda piece: piece
        tutorial._position_piece_at_spawn = lambda piece: piece
        tutorial.spawn_new_piece = lambda: create_piece_by_name('S')
        tutorial.apply_theme_to_pieces = lambda: None
        tutorial.sound = types.SimpleNamespace(play=lambda *_args, **_kwargs: None)

        used = TutorialMode._use_scenario_hold(tutorial)

        self.assertTrue(used)
        self.assertEqual(tutorial.held_piece.name, 'T')
        self.assertEqual(tutorial.current_piece.name, 'I')
        self.assertEqual([piece.name for piece in tutorial.next_piece_queue], ['O', 'S'])
        self.assertFalse(tutorial.can_hold)
        self.assertTrue(tutorial.lesson_runtime_state['hold_used'])

        used_again = TutorialMode._use_scenario_hold(tutorial)

        self.assertFalse(used_again)
        self.assertEqual(tutorial.held_piece.name, 'T')
        self.assertEqual(tutorial.current_piece.name, 'I')

    def test_multi_lock_scenarios_are_explicitly_marked(self):
        self.assertEqual(get_scenario('two_step_combo')['max_piece_locks'], 2)
        self.assertEqual(get_scenario('exam_board_combined')['max_piece_locks'], 2)
        self.assertEqual(get_scenario('exam_plan_combined')['max_piece_locks'], 2)

    def test_exam_plan_combined_requires_hold_usage(self):
        scenario = get_scenario('exam_plan_combined')

        self.assertTrue(scenario['expected_hold_usage'])
        self.assertEqual(scenario['objectives'][0]['metric'], 'hold_used')

    def test_lock_and_new_piece_waits_for_multi_lock_budget(self):
        tutorial = TutorialMode.__new__(TutorialMode)
        tutorial.step = 12
        tutorial.board = types.SimpleNamespace(lines_cleared=0)
        tutorial.in_transition = False
        tutorial.lesson_result_active = False
        tutorial.hub_progress_snapshot = {}
        tutorial.active_lesson_id = 'plan_two_step_setup'
        tutorial.lesson_runtime_state = {
            'scenario_lock_count': 0,
            'scenario_max_piece_locks': 2,
        }
        tutorial._is_scenario_lesson_active = lambda: True
        tutorial._evaluate_active_scenario = lambda: {'success': False, 'stars': 0}
        tutorial._sync_lesson_runtime_state = lambda: None
        tutorial._show_lesson_result = mock.Mock()

        with mock.patch.object(tutorial_module.Game, 'lock_and_new_piece', lambda self: None):
            TutorialMode.lock_and_new_piece(tutorial)
            self.assertEqual(tutorial.lesson_runtime_state['scenario_lock_count'], 1)
            tutorial._show_lesson_result.assert_not_called()

            TutorialMode.lock_and_new_piece(tutorial)
            self.assertEqual(tutorial.lesson_runtime_state['scenario_lock_count'], 2)
            tutorial._show_lesson_result.assert_called_once()


if __name__ == '__main__':
    unittest.main()