from __future__ import annotations

import unittest

from leaderboard_trailer_screen import get_leaderboard_trailer_panel_rect


class TestLeaderboardTrailerScreen(unittest.TestCase):
    def test_panel_rect_is_centered_and_large(self):
        rect = get_leaderboard_trailer_panel_rect((1920, 1080))

        self.assertGreaterEqual(rect.width, int(1920 * 0.69))
        self.assertGreaterEqual(rect.height, int(1080 * 0.70))
        self.assertEqual(rect.centerx, 1920 // 2)
        self.assertGreater(rect.y, 0)

    def test_panel_rect_stays_inside_small_surface(self):
        rect = get_leaderboard_trailer_panel_rect((1280, 720))

        self.assertGreaterEqual(rect.x, 0)
        self.assertGreaterEqual(rect.y, 0)
        self.assertLessEqual(rect.right, 1280)
        self.assertLessEqual(rect.bottom, 720)


if __name__ == '__main__':
    unittest.main()