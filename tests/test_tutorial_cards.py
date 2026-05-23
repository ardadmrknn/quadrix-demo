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
        self.assertEqual([card['id'] for card in scenario['choices']], ['perk_synergy', 'speed_burst_rare', 'row_shuffle'])
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

    def test_tempo_trap_rewards_gravity_well_over_peak_sculpt(self):
        scenario = get_card_choice_scenario('tempo_trap')
        self.assertIsNotNone(scenario)
        self.assertEqual([card['id'] for card in scenario['choices']], ['speed_burst_rare', 'peak_sculpt', 'gravity_well'])

        best_outcome = evaluate_card_choice(scenario, 'gravity_well')
        weaker_outcome = evaluate_card_choice(scenario, 'peak_sculpt')

        self.assertTrue(best_outcome['success'])
        self.assertEqual(best_outcome['stars'], 3)
        self.assertTrue(weaker_outcome['success'])
        self.assertEqual(weaker_outcome['stars'], 1)

    def test_rare_not_auto_prefers_prevention_over_revive(self):
        scenario = get_card_choice_scenario('rare_not_auto')
        self.assertIsNotNone(scenario)
        self.assertEqual([card['id'] for card in scenario['choices']], ['speed_burst_legendary', 'freeze_drop_rare', 'clear_rows'])

        best_outcome = evaluate_card_choice(scenario, 'freeze_drop_rare')
        acceptable_outcome = evaluate_card_choice(scenario, 'clear_rows')
        weak_outcome = evaluate_card_choice(scenario, 'speed_burst_legendary')

        self.assertTrue(best_outcome['success'])
        self.assertEqual(best_outcome['stars'], 3)
        self.assertTrue(acceptable_outcome['success'])
        self.assertEqual(acceptable_outcome['stars'], 2)
        self.assertFalse(weak_outcome['success'])
        self.assertEqual(weak_outcome['stars'], 0)

    def test_build_direction_now_teaches_targeted_cleanup(self):
        scenario = get_card_choice_scenario('build_direction')
        self.assertIsNotNone(scenario)
        self.assertEqual([card['id'] for card in scenario['choices']], ['peak_sculpt', 'nova_burst', 'row_shuffle'])
        self.assertEqual(scenario['recommended_card_id'], 'peak_sculpt')

        best_outcome = evaluate_card_choice(scenario, 'peak_sculpt')
        overkill_outcome = evaluate_card_choice(scenario, 'nova_burst')

        self.assertTrue(best_outcome['success'])
        self.assertEqual(best_outcome['stars'], 3)
        self.assertFalse(overkill_outcome['success'])
        self.assertEqual(overkill_outcome['stars'], 0)

    def test_card_preview_prefers_real_catalog_fields_over_tutorial_fallbacks(self):
        freeze_drop = tutorial_cards.get_card_preview('freeze_drop_rare')
        self.assertEqual(freeze_drop['value'], 3)
        self.assertEqual(freeze_drop['freeze_duration'], 6)
        self.assertTrue(freeze_drop['single_use'])
        self.assertFalse(freeze_drop.get('persistent', False))
        self.assertIn('3 hak', tutorial_cards.get_tutorial_card_description(freeze_drop))

        nova_burst = tutorial_cards.get_card_preview('nova_burst')
        self.assertEqual(nova_burst['value'], 3)
        self.assertIn('Sonraki 3 kilitte', tutorial_cards.get_tutorial_card_description(nova_burst))

        ghost_echo = tutorial_cards.get_card_preview('ghost_echo')
        self.assertEqual(ghost_echo['value'], 10)
        self.assertTrue(ghost_echo['single_use'])
        self.assertFalse(ghost_echo.get('persistent', False))


class TestTutorialCardProgression(unittest.TestCase):
    def test_card_foundations_unlock_after_prior_chapters_complete(self):
        progress = build_default_tutorial_progress()
        for chapter_id in ('basics', 'board_basics', 'queue_hold', 'recovery'):
            for lesson in list_lessons_for_chapter(chapter_id):
                progress = mark_lesson_completed(progress, lesson['id'], 1)
        card_state = get_chapter_completion(progress, 'card_academy')
        self.assertTrue(card_state['unlocked'])

    def test_card_foundations_lessons_exist_via_legacy_alias(self):
        lesson_ids = [lesson['id'] for lesson in list_lessons_for_chapter('card_academy')]
        self.assertEqual(
            lesson_ids,
            ['cards_rescue_now', 'cards_tempo_trap', 'cards_perk_vs_instant', 'cards_long_term_value'],
        )


if __name__ == '__main__':
    unittest.main()