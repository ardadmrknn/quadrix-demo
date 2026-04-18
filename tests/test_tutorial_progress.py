# -*- coding: utf-8 -*-
"""Tutorial progress helper ve persistence testleri."""

from __future__ import annotations

import importlib
import os
import sys
import tempfile
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
user_manager_module = _ensure_real_module('user_manager')

list_lessons_for_chapter = tutorial_lessons.list_lessons_for_chapter
build_default_tutorial_progress = tutorial_progress.build_default_tutorial_progress
get_chapter_completion = tutorial_progress.get_chapter_completion
mark_chapter_completed = tutorial_progress.mark_chapter_completed
mark_lesson_completed = tutorial_progress.mark_lesson_completed
UserManager = user_manager_module.UserManager


def _make_manager() -> UserManager:
    fd, path = tempfile.mkstemp(suffix='.json', prefix='tutorial_progress_')
    os.close(fd)
    os.unlink(path)
    return UserManager(users_file=path)


class TestTutorialProgressHelpers(unittest.TestCase):
    def test_package_import_works_without_src_path_in_sys_path(self):
        original_sys_path = list(sys.path)
        original_src_module = sys.modules.get('src.tutorial_progress')
        original_top_level_module = sys.modules.get('tutorial_progress')
        try:
            sys.modules.pop('src.tutorial_progress', None)
            sys.modules.pop('tutorial_progress', None)
            sys.path = [ROOT_DIR] + [
                path
                for path in original_sys_path
                if os.path.abspath(path or '.') != os.path.abspath(SRC_DIR)
            ]
            module = importlib.import_module('src.tutorial_progress')
            self.assertTrue(hasattr(module, 'build_default_tutorial_progress'))
        finally:
            sys.path = original_sys_path
            sys.modules.pop('src.tutorial_progress', None)
            sys.modules.pop('tutorial_progress', None)
            if original_src_module is not None:
                sys.modules['src.tutorial_progress'] = original_src_module
            if original_top_level_module is not None:
                sys.modules['tutorial_progress'] = original_top_level_module

    def test_user_manager_package_import_works_without_src_path_in_sys_path(self):
        original_sys_path = list(sys.path)
        original_src_module = sys.modules.get('src.user_manager')
        original_top_level_module = sys.modules.get('user_manager')
        try:
            sys.modules.pop('src.user_manager', None)
            sys.modules.pop('user_manager', None)
            sys.path = [ROOT_DIR] + [
                path
                for path in original_sys_path
                if os.path.abspath(path or '.') != os.path.abspath(SRC_DIR)
            ]
            module = importlib.import_module('src.user_manager')
            self.assertTrue(hasattr(module, 'UserManager'))
        finally:
            sys.path = original_sys_path
            sys.modules.pop('src.user_manager', None)
            sys.modules.pop('user_manager', None)
            if original_src_module is not None:
                sys.modules['src.user_manager'] = original_src_module
            if original_top_level_module is not None:
                sys.modules['user_manager'] = original_top_level_module

    def test_default_progress_contains_quick_start_lessons(self):
        progress = build_default_tutorial_progress()
        quick_start = progress['chapters']['quick_start']
        self.assertTrue(quick_start['unlocked'])
        self.assertEqual(len(quick_start['lessons']), len(list_lessons_for_chapter('quick_start')))

    def test_mark_lesson_completed_accepts_legacy_lesson_id_and_keeps_highest_star_value(self):
        progress = build_default_tutorial_progress()
        progress = mark_lesson_completed(progress, 'move_intro', 1)
        progress = mark_lesson_completed(progress, 'move_intro', 3)
        progress = mark_lesson_completed(progress, 'move_intro', 2)
        lesson = progress['chapters']['quick_start']['lessons']['qs_move_lane']
        self.assertTrue(lesson['completed'])
        self.assertEqual(lesson['stars'], 3)

    def test_marking_all_quick_start_lessons_completes_legacy_basics_alias(self):
        progress = build_default_tutorial_progress()
        for lesson in list_lessons_for_chapter('basics'):
            progress = mark_lesson_completed(progress, lesson['id'], 1)
        basics_state = get_chapter_completion(progress, 'basics')
        self.assertTrue(basics_state['completed'])
        self.assertEqual(basics_state['completed_lessons'], basics_state['total_lessons'])

    def test_mark_chapter_completed_unlocks_next_chapter(self):
        progress = build_default_tutorial_progress()
        progress = mark_chapter_completed(progress, 'basics', stars_per_lesson=1)
        basics_state = get_chapter_completion(progress, 'quick_start')
        board_state = get_chapter_completion(progress, 'board_basics')
        self.assertTrue(basics_state['completed'])
        self.assertTrue(board_state['unlocked'])


class TestUserManagerTutorialProgress(unittest.TestCase):
    def setUp(self):
        self.user_manager = _make_manager()
        ok, message = self.user_manager.create_user('TutorialTester')
        self.assertTrue(ok, message)

    def test_new_user_has_default_tutorial_progress(self):
        progress = self.user_manager.get_tutorial_progress('TutorialTester')
        self.assertIn('quick_start', progress['chapters'])
        self.assertFalse(progress['chapters']['quick_start']['completed'])

    def test_mark_tutorial_lesson_completed_accepts_legacy_lesson_id(self):
        self.user_manager.mark_tutorial_lesson_completed('move_intro', 2, username='TutorialTester')
        progress = self.user_manager.get_tutorial_progress('TutorialTester')
        lesson = progress['chapters']['quick_start']['lessons']['qs_move_lane']
        self.assertTrue(lesson['completed'])
        self.assertEqual(lesson['stars'], 2)

    def test_marking_all_lessons_sets_tutorial_completed(self):
        for lesson in list_lessons_for_chapter('basics'):
            self.user_manager.mark_tutorial_lesson_completed(lesson['id'], 1, username='TutorialTester')
        self.assertTrue(self.user_manager.is_tutorial_completed('TutorialTester'))

    def test_set_tutorial_completed_true_does_not_fabricate_progress(self):
        self.user_manager.set_tutorial_completed(True, username='TutorialTester')
        progress = self.user_manager.get_tutorial_progress('TutorialTester')
        basics_state = get_chapter_completion(progress, 'quick_start')
        board_state = get_chapter_completion(progress, 'surface_control')
        self.assertTrue(self.user_manager.is_tutorial_completed('TutorialTester'))
        self.assertFalse(basics_state['completed'])
        self.assertFalse(board_state['unlocked'])

    def test_set_tutorial_completed_false_resets_progress(self):
        self.user_manager.mark_tutorial_lesson_completed('move_intro', 2, username='TutorialTester')
        self.user_manager.set_tutorial_completed(False, username='TutorialTester')
        progress = self.user_manager.get_tutorial_progress('TutorialTester')
        basics_state = get_chapter_completion(progress, 'quick_start')
        board_state = get_chapter_completion(progress, 'surface_control')
        self.assertFalse(self.user_manager.is_tutorial_completed('TutorialTester'))
        self.assertFalse(basics_state['completed'])
        self.assertFalse(board_state['unlocked'])

    def test_legacy_completed_profile_migrates_to_progress(self):
        fd, path = tempfile.mkstemp(suffix='.json', prefix='tutorial_legacy_')
        os.close(fd)
        try:
            with open(path, 'w', encoding='utf-8') as file_obj:
                file_obj.write(
                    '{'
                    '"users": {'
                    '"LegacyTester": {'
                    '"tutorial_completed": true,'
                    '"game_stats": {},'
                    '"avatar": "default",'
                    '"created_at": "2026-03-10T00:00:00"'
                    '}'
                    '},'
                    '"current_user": "LegacyTester"'
                    '}'
                )
            manager = UserManager(users_file=path)
            progress = manager.get_tutorial_progress('LegacyTester')
            basics_state = get_chapter_completion(progress, 'quick_start')
            self.assertTrue(manager.is_tutorial_completed('LegacyTester'))
            self.assertTrue(basics_state['completed'])
        finally:
            if os.path.exists(path):
                os.unlink(path)


if __name__ == '__main__':
    unittest.main()