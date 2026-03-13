# -*- coding: utf-8 -*-
"""Tutorial runtime regresyon testleri."""

from __future__ import annotations

import importlib
import os
import sys
import types
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


tutorial_module = _ensure_real_module('tutorial')
TutorialMode = tutorial_module.TutorialMode


class TestTutorialRuntime(unittest.TestCase):
    def test_lesson_result_keeps_screen_shake_progressing(self):
        tutorial = TutorialMode.__new__(TutorialMode)
        tutorial.in_transition = False
        tutorial.hub_active = False
        tutorial.lesson_result_active = True
        tutorial.line_clear_animation = 0
        tutorial.line_clear_flash = False
        tutorial.line_clear_sweep_active = False
        tutorial.line_clear_sweep_progress = 0.0
        tutorial.line_clear_sweep_rows = []
        tutorial.line_clear_wave_effects = []
        tutorial.falling_block_animations = []
        tutorial.block_fall_speed = 0
        tutorial.combo_message_time = 0
        tutorial.drop_trails = []
        tutorial.screen_shake = 20.0
        tutorial._screen_shake_initial = 20.0
        tutorial.shake_intensity = 15
        tutorial.board = types.SimpleNamespace(last_cleared_lines=[])
        tutorial.card_ui = None
        tutorial._pending_card_choice_index = None
        tutorial._update_success_effects = lambda _dt: None
        tutorial.update_particles = lambda dt_ms=None: None
        tutorial.update_ambient_particles = lambda dt_ms=None: None
        tutorial._update_drop_trails = lambda _dt_frames: None
        tutorial._is_card_choice_lesson_active = lambda: False

        TutorialMode.update(tutorial, 16.666)

        self.assertLess(tutorial.screen_shake, 20.0)

    def test_wants_mouse_visible_for_hub(self):
        tutorial = TutorialMode.__new__(TutorialMode)
        tutorial.hub_active = True
        tutorial.show_exit_prompt = False
        tutorial.paused = False
        tutorial.game_over = False
        tutorial.lesson_result_active = False
        tutorial.active_lesson = None

        self.assertTrue(TutorialMode.wants_mouse_visible(tutorial))

    def test_wants_mouse_visible_for_card_choice(self):
        tutorial = TutorialMode.__new__(TutorialMode)
        tutorial.hub_active = False
        tutorial.show_exit_prompt = False
        tutorial.paused = False
        tutorial.game_over = False
        tutorial.lesson_result_active = False
        tutorial.active_lesson = {'kind': 'card_choice'}

        self.assertTrue(TutorialMode.wants_mouse_visible(tutorial))

    def test_wants_mouse_hidden_during_normal_tutorial_gameplay(self):
        tutorial = TutorialMode.__new__(TutorialMode)
        tutorial.hub_active = False
        tutorial.show_exit_prompt = False
        tutorial.paused = False
        tutorial.game_over = False
        tutorial.lesson_result_active = False
        tutorial.active_lesson = {'kind': 'scenario'}

        self.assertFalse(TutorialMode.wants_mouse_visible(tutorial))


if __name__ == '__main__':
    unittest.main()