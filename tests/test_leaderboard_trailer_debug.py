from __future__ import annotations

import unittest

from leaderboard_trailer_debug import (
    TRAILER_DEBUG_DURATION_MS,
    TRAILER_DEBUG_LUNA_ASSET,
    build_trailer_debug_entries,
    build_trailer_debug_seed_entries,
)


class TestLeaderboardTrailerDebug(unittest.TestCase):
    def test_seed_entries_place_luna_tenth_with_avatar(self):
        entries = build_trailer_debug_seed_entries()

        self.assertEqual(len(entries), 10)
        self.assertEqual(entries[-1]['debug_persona'], 'Luna')
        self.assertEqual(entries[-1]['rank'], 10)
        self.assertEqual(entries[-1]['debug_avatar_asset'], TRAILER_DEBUG_LUNA_ASSET)

    def test_script_finishes_with_luna_in_first_place(self):
        entries, progress, is_running = build_trailer_debug_entries(
            now_ms=TRAILER_DEBUG_DURATION_MS,
            start_ms=0,
        )

        self.assertEqual(progress, 1.0)
        self.assertFalse(is_running)
        self.assertEqual(entries[0]['debug_persona'], 'Luna')
        self.assertEqual(entries[0]['rank'], 1)
        self.assertGreater(entries[0]['score'], entries[1]['score'])

    def test_script_midpoint_already_improves_luna_rank(self):
        entries, progress, is_running = build_trailer_debug_entries(
            now_ms=TRAILER_DEBUG_DURATION_MS // 2,
            start_ms=0,
        )
        luna_entry = next(entry for entry in entries if entry['debug_persona'] == 'Luna')

        self.assertGreater(progress, 0.0)
        self.assertTrue(is_running)
        self.assertLess(luna_entry['rank'], 10)
        self.assertGreater(luna_entry['score'], 64000)


if __name__ == '__main__':
    unittest.main()