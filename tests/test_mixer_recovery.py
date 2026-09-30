"""
Birim testleri: SoundManager mixer suspend/resume kurtarma (recovery) mekanizması.
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

import pygame
from sound import SoundManager


class TestMixerRecovery(unittest.TestCase):
    """Mixer kurtarma (recovery) dayanıklılık testleri."""

    def setUp(self):
        pygame.init()
        self.sm = SoundManager()
        self.sm.enabled = True

    def tearDown(self):
        pygame.quit()

    def test_mixer_recovery_preserves_volumes(self):
        """Kurtarma sonrasında müzik ve SFX ses seviyeleri eksiksiz korunmalıdır."""
        self.sm.music_volume = 0.75
        self.sm.sfx_volume = 0.85

        with patch.object(self.sm, '_ensure_mixer_ready', return_value=True), \
             patch.object(self.sm, 'create_sounds'), \
             patch.object(self.sm, 'create_music'), \
             patch.object(self.sm, 'set_volume') as mock_set_vol, \
             patch.object(self.sm, 'set_music_volume') as mock_set_mvol:

            res = self.sm.recover_mixer(force=True)

            self.assertTrue(res)
            self.assertEqual(self.sm.music_volume, 0.75)
            self.assertEqual(self.sm.sfx_volume, 0.85)
            mock_set_vol.assert_called_with(0.85)
            mock_set_mvol.assert_called_with(0.75)

    def test_mixer_recovery_preserves_mute_and_duck_state(self):
        """Mute ve duck faktörü kurtarma sonrasında korunmalıdır."""
        self.sm.muted = True
        self.sm._duck_factor = 0.4

        with patch.object(self.sm, '_ensure_mixer_ready', return_value=True), \
             patch.object(self.sm, 'create_sounds'), \
             patch.object(self.sm, 'create_music'), \
             patch.object(self.sm, 'set_volume'), \
             patch.object(self.sm, 'set_music_volume'), \
             patch('pygame.mixer.music.pause') as mock_pause:

            res = self.sm.recover_mixer(force=True)

            self.assertTrue(res)
            self.assertTrue(self.sm.muted)
            self.assertEqual(self.sm._duck_factor, 0.4)
            mock_pause.assert_called_once()

    def test_mixer_recovery_preserves_playlist_state(self):
        """Çalma listesi ve parça indeksi kurtarma sonrasında korunmalıdır."""
        self.sm.music_playlist = ['track_1', 'track_2', 'track_3']
        self.sm.music_playlist_index = 1
        self.sm.current_track_name = 'track_2'

        with patch.object(self.sm, '_ensure_mixer_ready', return_value=True), \
             patch.object(self.sm, 'create_sounds'), \
             patch.object(self.sm, 'create_music'), \
             patch.object(self.sm, 'set_volume'), \
             patch.object(self.sm, 'set_music_volume'), \
             patch.object(self.sm, 'play_music') as mock_play:

            res = self.sm.recover_mixer(force=True)

            self.assertTrue(res)
            self.assertEqual(self.sm.music_playlist, ['track_1', 'track_2', 'track_3'])
            self.assertEqual(self.sm.music_playlist_index, 1)
            mock_play.assert_called_once_with('track_2', loop=True)

    def test_mixer_recovery_failure_does_not_crash_or_lock_game(self):
        """Mixer başlatılamazsa (ses cihazı yoksa) exception fırlatılmamalı ve False dönmelidir."""
        with patch.object(self.sm, '_ensure_mixer_ready', return_value=False):
            res = self.sm.recover_mixer(force=True)

            self.assertFalse(res, "Kurtarma başarısız olduğunda False dönmeli")
            self.assertFalse(self.sm.enabled, "enabled False olmalı")


if __name__ == '__main__':
    unittest.main()
