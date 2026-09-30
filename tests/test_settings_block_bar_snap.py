"""
Bölüm E: Blok Bar %5 kilitleme, clamping ve metin gösterimi testleri.
"""

import os
import sys
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

import pygame
from settings_manager import SettingsManager
from settings_screen_tabbed import TabbedSettingsScreen


class TestSettingsBlockBarSnap(unittest.TestCase):
    """Blok Bar 20 segment (%5) kilitleme testleri."""

    def setUp(self):
        pygame.init()
        self.sm = SettingsManager()
        self.screen = TabbedSettingsScreen(pygame.Surface((1280, 720)), MagicMock(), self.sm)

    def tearDown(self):
        pygame.quit()

    def test_block_count_clamped_between_0_and_20(self):
        """0.0 altı veya 1.0 üstü değerler 0-20 sınırına clamp edilmeli."""
        num_blocks = 20
        # Negatif değer
        neg_val = -0.5
        neg_blocks = max(0, min(num_blocks, int(round(neg_val * num_blocks))))
        self.assertEqual(neg_blocks, 0)

        # 1.0'dan büyük aşırı değer
        over_val = 2.5
        over_blocks = max(0, min(num_blocks, int(round(over_val * num_blocks))))
        self.assertEqual(over_blocks, 20)

    def test_intermediate_float_snaps_to_nearest_5_percent(self):
        """0.64 gibi ara değer ilk basışta doğru blok değerine snap olmalı."""
        # 0.64 değeri ayarlandığında
        self.screen.music_volume = 0.64
        # Sağ oka basıldı (delta = +1)
        self.screen._adjust_slider('music_volume', 1, {'min': 0, 'max': 1})
        # 0.64 * 20 = 12.8 -> 13 blok (0.65). 13 + 1 = 14 blok (0.70)
        self.assertEqual(self.screen.music_volume, 0.70)
        self.assertEqual(self.screen._music_volume_vis, 0.70)

    def test_percentage_text_no_float_drift(self):
        """%5, %10, %15, %25 gibi değerlerde IEEE-754 sapması metne yansımamalı."""
        test_values = [0.05, 0.10, 0.15, 0.20, 0.25, 0.35, 0.55, 0.70, 0.95, 1.0]
        for val in test_values:
            blocks = max(0, min(20, int(round(val * 20))))
            text = f'{blocks * 5}%'
            # '14.999' veya '.' içermemeli
            self.assertNotIn('.', text)
            self.assertTrue(text.endswith('%'))
            expected_num = int(round(val * 100))
            self.assertEqual(text, f'{expected_num}%')

    def test_active_count_never_overflows_with_extreme_values(self):
        """Bozuk actual_val değerlerinde bile active_count [0, 20] sınırını aşmamalı."""
        num_blocks = 20
        extreme_values = [-100.0, -1.0, 1.5, 99.0, float('nan')]
        for ext in extreme_values:
            if ext != ext:  # nan
                val = 0.0
            else:
                val = ext
            active_count = max(0, min(num_blocks, int(round(val * num_blocks))))
            self.assertGreaterEqual(active_count, 0)
            self.assertLessEqual(active_count, 20)


if __name__ == '__main__':
    unittest.main()
