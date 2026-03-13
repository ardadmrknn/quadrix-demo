# -*- coding: utf-8 -*-
"""Tutorial kart dersi helper testleri."""

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


tutorial_cards = _ensure_real_module('tutorial_cards')
tutorial_lessons = _ensure_real_module('tutorial_lessons')
tutorial_progress = _ensure_real_module('tutorial_progress')

evaluate_card_choice = tutorial_cards.evaluate_card_choice
get_card_choice_scenario = tutorial_cards.get_card_choice_scenario
list_lessons_for_chapter = tutorial_lessons.list_lessons_for_chapter
build_default_tutorial_progress = tutorial_progress.build_default_tutorial_progress
get_chapter_completion = tutorial_progress.get_chapter_completion
mark_lesson_completed = tutorial_progress.mark_lesson_completed


class TestTutorialCardHelpers(unittest.TestCase):
    def test_card_choice_scenario_hydrates_real_choices(self):
        scenario = get_card_choice_scenario('rescue_pick')
        self.assertIsNotNone(scenario)
        self.assertEqual(scenario['scenario_id'], 'rescue_pick')
        self.assertEqual([card['id'] for card in scenario['choices']], ['clear_rows', 'peak_sculpt', 'speed_burst_legendary'])

    def test_synergy_scenario_uses_current_cards_only(self):
        scenario = get_card_choice_scenario('synergy_pick')
        self.assertIsNotNone(scenario)
        self.assertEqual([card['id'] for card in scenario['choices']], ['perk_synergy', 'line_bonus', 'row_shuffle'])
        self.assertNotIn('score', [card['id'] for card in scenario['choices']])

    def test_recommended_choice_gets_three_stars(self):
        scenario = get_card_choice_scenario('rescue_pick')
        outcome = evaluate_card_choice(scenario, 'clear_rows')
        self.assertTrue(outcome['success'])
        self.assertEqual(outcome['stars'], 3)

    def test_acceptable_choice_still_passes(self):
        scenario = get_card_choice_scenario('rescue_pick')
        outcome = evaluate_card_choice(scenario, 'peak_sculpt')
        self.assertTrue(outcome['success'])
        self.assertEqual(outcome['stars'], 2)

    def test_wrong_choice_fails(self):
        scenario = get_card_choice_scenario('long_term_pick')
        outcome = evaluate_card_choice(scenario, 'row_shuffle')
        self.assertFalse(outcome['success'])
        self.assertEqual(outcome['stars'], 0)


class TestTutorialCardProgression(unittest.TestCase):
    def test_card_academy_unlocks_after_board_basics_complete(self):
        progress = build_default_tutorial_progress()
        for lesson in list_lessons_for_chapter('basics'):
            progress = mark_lesson_completed(progress, lesson['id'], 1)
        for lesson in list_lessons_for_chapter('board_basics'):
            progress = mark_lesson_completed(progress, lesson['id'], 1)
        card_state = get_chapter_completion(progress, 'card_academy')
        self.assertTrue(card_state['unlocked'])

    def test_card_academy_lessons_exist(self):
        lesson_ids = [lesson['id'] for lesson in list_lessons_for_chapter('card_academy')]
        self.assertEqual(
            lesson_ids,
            ['card_rescue_pick', 'card_long_term_pick', 'card_synergy_pick'],
        )


if __name__ == '__main__':
    unittest.main()