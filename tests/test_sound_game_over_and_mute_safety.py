"""
Bölüm F: Ses ve Game Over güvenliği testleri.
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

import pygame
from sound import SoundManager


class TestSoundGameOverAndMuteSafety(unittest.TestCase):
    """Game Over dizisi ve Mute güvenliği testleri."""

    def setUp(self):
        pygame.init()
        self.sm = SoundManager()
        self.sm.enabled = True
        self.sm.music_enabled = True
        self.sm.sfx_enabled = True

    def tearDown(self):
        pygame.quit()

    def test_play_game_over_perceptual_volume_applied(self):
        """play_game_over_sequence() ses seviyesini perceptual curve üzerinden uygulamalı."""
        self.sm.sfx_volume = 0.5
        mock_sound = MagicMock()
        self.sm.sounds['gameover'] = mock_sound

        self.sm.play_game_over_sequence()

        expected_vol = self.sm._perceptual_volume(0.5)
        mock_sound.set_volume.assert_called_with(expected_vol)
        mock_sound.play.assert_called_once()

    def test_game_over_sound_not_played_when_muted(self):
        """muted=True iken Game Over sesi çalınmamalı."""
        self.sm.muted = True
        mock_sound = MagicMock()
        self.sm.sounds['gameover'] = mock_sound

        self.sm.play_game_over_sequence()

        mock_sound.play.assert_not_called()

    def test_game_over_sound_not_played_when_sfx_disabled(self):
        """sfx_enabled=False iken Game Over sesi çalınmamalı."""
        self.sm.sfx_enabled = False
        mock_sound = MagicMock()
        self.sm.sounds['gameover'] = mock_sound

        self.sm.play_game_over_sequence()

        mock_sound.play.assert_not_called()

    def test_stop_music_clears_resume_track_preventing_accidental_restart_on_unmute(self):
        """stop_music() çağrısından sonra mute açılsa bile müzik beklenmedik biçimde yeniden başlamamalı."""
        # 1. Müzik çalıyordu
        self.sm.current_track_name = 'battle_1'
        self.sm.set_muted(True)
        self.assertEqual(self.sm._resume_track_name, 'battle_1')

        # 2. Oyun bitti, stop_music çağrıldı
        self.sm.stop_music()
        self.assertIsNone(self.sm.current_track_name)
        self.assertIsNone(self.sm._resume_track_name, "stop_music() resume track bilgisini sıfırlamalı")

        # 3. Oyuncu veya sistem sesi açtı (unmute)
        with patch.object(self.sm, 'play_music') as mock_play:
            self.sm.set_muted(False)
            mock_play.assert_not_called()

    def test_safe_behavior_without_audio_hardware(self):
        """Ses donanımı yokken (enabled=False) metotlar güvenli şekilde tamamlanmalı."""
        self.sm.enabled = False
        # Hiçbir exception fırlatmamalı
        self.sm.set_muted(True)
        self.sm.play_game_over_sequence()
        self.sm.stop_music()
        self.sm.set_volume(0.5)
        self.sm.set_music_volume(0.5)


if __name__ == '__main__':
    unittest.main()
