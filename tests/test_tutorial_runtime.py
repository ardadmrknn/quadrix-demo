# -*- coding: utf-8 -*-
"""Tutorial runtime regresyon testleri."""

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
TutorialMode = tutorial_module.TutorialMode


class TestTutorialRuntime(unittest.TestCase):
    def _build_das_tutorial(self, *, step=1, active_lesson=None):
        pygame = tutorial_module.pygame
        tutorial = TutorialMode.__new__(TutorialMode)
        tutorial.game_over = False
        tutorial.show_exit_prompt = False
        tutorial.hub_active = False
        tutorial.lesson_result_active = False
        tutorial.lesson_result = None
        tutorial.waiting_for_enter = False
        tutorial.in_transition = False
        tutorial.user_manager = None
        tutorial.active_lesson = active_lesson
        tutorial.active_lesson_id = 'das_test_lesson'
        tutorial.card_ui = None
        tutorial.step = step
        tutorial.step_target = 3
        tutorial.step_move_left_count = 0
        tutorial.step_move_right_count = 0
        tutorial.step_rotate_count = 0
        tutorial.soft_drop_counter = 0
        tutorial.lesson_runtime_state = {}
        tutorial.step_idle_timer = 0.0
        tutorial.stuck_hint_message = ''
        tutorial.base_fall_speed = 2000
        tutorial.fall_speed = 2000
        tutorial.soft_drop_active = False
        tutorial.das_direction = 0
        tutorial.das_timer = 0
        tutorial.das_repeat_timer = 0
        tutorial.das_charged = False
        tutorial.sub_message = ''
        tutorial.control_bindings = {
            'move_left': pygame.K_LEFT,
            'move_right': pygame.K_RIGHT,
            'soft_drop': pygame.K_DOWN,
            'hard_drop': pygame.K_SPACE,
            'rotate': pygame.K_UP,
            'hold': pygame.K_c,
            'hold2': pygame.K_v,
            'pause': pygame.K_p,
        }
        tutorial.alt_control_bindings = {
            'move_left': pygame.K_a,
            'move_right': pygame.K_d,
            'soft_drop': pygame.K_s,
            'hard_drop': None,
            'rotate': pygame.K_w,
            'hold': None,
            'hold2': None,
            'pause': None,
        }
        tutorial.settings_manager = types.SimpleNamespace(
            get=lambda key, default=None: {
                'das_delay': 100,
                'das_repeat': 1000,
            }.get(key, default)
        )
        tutorial.current_piece = types.SimpleNamespace(x=4, y=0)
        tutorial.board = types.SimpleNamespace(
            lines_cleared=0,
            is_valid_position=lambda piece, dx=0, dy=0: 0 <= piece.x + dx < 10,
        )
        plays = []
        tutorial.sound = types.SimpleNamespace(play=lambda name: plays.append(name))
        tutorial._create_mini_success_effect = lambda *_args, **_kwargs: None
        tutorial._complete_step = lambda next_step: setattr(tutorial, 'completed_step', next_step)
        return tutorial, plays

    def test_tutorial_move_key_starts_das_and_repeat_updates_progress(self):
        pygame = tutorial_module.pygame
        tutorial, plays = self._build_das_tutorial(step=1)

        with mock.patch.object(
            tutorial_module.pygame.event,
            'get',
            return_value=[pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RIGHT)],
        ):
            self.assertTrue(TutorialMode.handle_input(tutorial))

        self.assertEqual(tutorial.current_piece.x, 5)
        self.assertEqual(tutorial.das_direction, 1)
        self.assertEqual(tutorial.step_move_right_count, 1)

        TutorialMode._update_das(tutorial, 100)

        self.assertEqual(tutorial.current_piece.x, 6)
        self.assertEqual(tutorial.step_move_right_count, 2)
        self.assertEqual(tutorial.lesson_runtime_state['move_right_count'], 2)
        self.assertGreaterEqual(plays.count('move'), 2)

    def test_tutorial_scenario_das_repeat_updates_runtime_counts(self):
        tutorial, _plays = self._build_das_tutorial(step=8, active_lesson={'kind': 'scenario'})
        tutorial.das_direction = -1

        TutorialMode._update_das(tutorial, 100)

        self.assertEqual(tutorial.current_piece.x, 3)
        self.assertEqual(tutorial.step_move_left_count, 1)
        self.assertEqual(tutorial.lesson_runtime_state['move_left_count'], 1)

    def test_tutorial_move_keyup_stops_das(self):
        pygame = tutorial_module.pygame
        tutorial, _plays = self._build_das_tutorial(step=5)
        tutorial.das_direction = 1
        tutorial.das_timer = 42

        with mock.patch.object(
            tutorial_module.pygame.event,
            'get',
            return_value=[pygame.event.Event(pygame.KEYUP, key=pygame.K_RIGHT)],
        ), mock.patch.object(tutorial_module.pygame.key, 'get_pressed', return_value=()):
            self.assertTrue(TutorialMode.handle_input(tutorial))

        self.assertEqual(tutorial.das_direction, 0)
        self.assertEqual(tutorial.das_timer, 0)

    def test_continue_after_completion_starts_next_chapter_lesson_in_full_flow(self):
        tutorial = TutorialMode.__new__(TutorialMode)
        tutorial.next_lesson_id = None
        tutorial.active_lesson_id = 'tutorial_complete'
        tutorial.active_lesson = {'chapter': 'quick_start'}
        tutorial.lesson_lookup = {}
        tutorial.lesson_flow_scope = 'full'
        tutorial.hub_return_enabled = True
        started = {}

        tutorial._start_lesson = lambda lesson_id: started.setdefault('lesson_id', lesson_id)
        tutorial._open_tutorial_hub = lambda **kwargs: started.setdefault('hub', kwargs)

        result = TutorialMode._continue_after_completion(tutorial)

        self.assertTrue(result)
        self.assertEqual(started.get('lesson_id'), 'surface_gap_fill')
        self.assertNotIn('hub', started)

    def test_line_clear_setup_removes_extra_right_support_block(self):
        tutorial = TutorialMode.__new__(TutorialMode)
        tutorial.board = types.SimpleNamespace(
            width=10,
            height=20,
            grid=[[None for _ in range(10)] for _ in range(20)],
            occupancy=[[False for _ in range(10)] for _ in range(20)],
        )
        tutorial._clear_tutorial_board = lambda: None
        tutorial._create_named_piece = lambda name: types.SimpleNamespace(name=name, x=0, y=0)
        tutorial._compute_spawn_y = lambda piece: 0
        tutorial._skip_hidden_rows = lambda piece: None
        tutorial.spawn_new_piece = lambda: types.SimpleNamespace(name='I')
        tutorial.apply_theme_to_pieces = lambda: None

        TutorialMode._setup_line_clear_scenario(tutorial)

        above = tutorial.board.height - 2
        self.assertFalse(tutorial.board.occupancy[above][8])
        self.assertTrue(tutorial.board.occupancy[above][9])
        self.assertEqual(len(tutorial.next_piece_queue), 1)

    def test_continue_after_completion_keeps_chapter_scope_at_boundary(self):
        tutorial = TutorialMode.__new__(TutorialMode)
        tutorial.next_lesson_id = None
        tutorial.active_lesson_id = 'tutorial_complete'
        tutorial.active_lesson = {'chapter': 'quick_start'}
        tutorial.lesson_lookup = {}
        tutorial.lesson_flow_scope = 'chapter'
        tutorial.hub_return_enabled = True
        started = {}

        tutorial._start_lesson = lambda lesson_id: started.setdefault('lesson_id', lesson_id)
        tutorial._open_tutorial_hub = lambda preferred_chapter_id=None, preferred_lesson_id=None: started.setdefault(
            'hub',
            (preferred_chapter_id, preferred_lesson_id),
        )

        result = TutorialMode._continue_after_completion(tutorial)

        self.assertTrue(result)
        self.assertEqual(started.get('hub'), ('quick_start', 'tutorial_complete'))
        self.assertNotIn('lesson_id', started)

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
