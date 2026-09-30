"""
Birim testleri: Smart Store Opener akışı, Steam Overlay önceliği ve fallback stratejisi.
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

import steam_integration
import demo_config
from demo_upgrade_prompt import DemoUpgradePrompt
import pygame


class TestDemoStoreOpener(unittest.TestCase):
    """Smart Store Opener hiyerarşisi ve fallback testleri."""

    def test_overlay_store_preferred_when_steam_and_overlay_available(self):
        """Steam ve overlay aktif olduğunda öncelikle ActivateGameOverlayToStore kullanılmalıdır."""
        with patch.object(steam_integration, 'is_available', return_value=True), \
             patch.object(steam_integration, 'is_overlay_enabled', return_value=True), \
             patch.object(steam_integration, 'activate_game_overlay_to_store', return_value=True) as mock_overlay:

            success, method = steam_integration.open_store_page(app_id="4414520")

            self.assertTrue(success)
            self.assertEqual(method, 'overlay_store')
            mock_overlay.assert_called_once_with(4414520)

    def test_protocol_fallback_when_overlay_disabled(self):
        """Overlay kapalıysa veya kullanılamazsa steam://store/<id> protokolü denenmelidir."""
        with patch.object(steam_integration, 'is_available', return_value=True), \
             patch.object(steam_integration, 'is_overlay_enabled', return_value=False), \
             patch('webbrowser.open', return_value=True) as mock_webbrowser:

            success, method = steam_integration.open_store_page(app_id="4414520")

            self.assertTrue(success)
            self.assertEqual(method, 'protocol')
            mock_webbrowser.assert_called_once_with("steam://store/4414520", new=2)

    def test_browser_fallback_when_protocol_fails(self):
        """Protokol açılışı başarısız olduğunda standart HTTPS tarayıcı URL'si açılmalıdır."""
        with patch.object(steam_integration, 'is_available', return_value=False), \
             patch('webbrowser.open', side_effect=[False, True]) as mock_webbrowser:

            success, method = steam_integration.open_store_page(app_id="4414520", url="https://store.steampowered.com/app/4414520/")

            self.assertTrue(success)
            self.assertEqual(method, 'browser')
            self.assertEqual(mock_webbrowser.call_count, 2)
            mock_webbrowser.assert_called_with("https://store.steampowered.com/app/4414520/", new=2)

    def test_upgrade_prompt_action_calls_store_and_closes_with_confirm(self):
        """DemoUpgradePrompt._open_store() open_store_page'i çağırıp prompt'u confirm ile kapatmalıdır."""
        pygame.init()
        try:
            screen = pygame.Surface((800, 600))
            prompt = DemoUpgradePrompt(screen)
            prompt.active = True

            with patch('steam_integration.open_store_page', return_value=(True, 'overlay_store')) as mock_open:
                prompt._open_store()

                mock_open.assert_called_once()
                self.assertFalse(prompt.active, "Prompt kapanmış olmalı")
                self.assertEqual(prompt.consume_last_action(), 'confirm', "Son aksiyon 'confirm' olmalı")
        finally:
            pygame.quit()


if __name__ == '__main__':
    unittest.main()
