# -*- coding: utf-8 -*-
"""Tutorial lesson akis helper testleri."""

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

get_next_lesson_id = tutorial_lessons.get_next_lesson_id


class TestTutorialLessonFlow(unittest.TestCase):
    def test_global_flow_crosses_chapter_boundary(self):
        self.assertEqual(get_next_lesson_id('tutorial_complete'), 'surface_gap_fill')

    def test_chapter_scoped_flow_stops_at_chapter_boundary(self):
        self.assertIsNone(get_next_lesson_id('tutorial_complete', chapter_only=True))
        self.assertIsNone(get_next_lesson_id('board_vertical_well', chapter_only=True))
        self.assertEqual(get_next_lesson_id('board_gap_fill', chapter_only=True), 'surface_keep_low')


if __name__ == '__main__':
    unittest.main()