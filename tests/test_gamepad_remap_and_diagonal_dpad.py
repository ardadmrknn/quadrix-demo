"""
Bölüm G: Gamepad remapping, button collision resolution ve çapraz D-pad testleri.
"""

import os
import sys
import unittest
from unittest.mock import MagicMock

# Proje dizinini ekle
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

import pygame
from gamepad_manager import GamepadManager, GamepadState


class TestGamepadRemapAndDiagonalDpad(unittest.TestCase):
    """Gamepad remap, diagonal D-pad ve collision resolution testleri."""

    def setUp(self):
        pygame.init()
        self.gpm = GamepadManager()
        self.gpm.set_context('game')

    def tearDown(self):
        pygame.quit()

    def _create_mock_gamepad_state(self, hat=(0, 0), buttons=None):
        gp = GamepadState(device_index=0)
        gp.dpad = hat
        gp.prev_dpad = (0, 0)
        gp.connected = True
        gp.is_gamepad = True
        if buttons:
            gp.buttons.update(buttons)
        return gp

    def test_diagonal_hat_up_plus_right_both_processed(self):
        """Hat (1, 1) geldiğinde hem Up hem Right yönleri aynı frame içinde üretilmeli."""
        gp = self._create_mock_gamepad_state(hat=(1, 1))
        # Default bindings: up -> K_UP, right -> K_RIGHT
        events = self.gpm._generate_dpad_events(gp, delta_ms=16.6)
        event_keys = [e.key for e in events if e.type == pygame.KEYDOWN]
        self.assertIn(pygame.K_UP, event_keys, "D-pad Up K_UP üretmeli")
        self.assertIn(pygame.K_RIGHT, event_keys, "D-pad Right K_RIGHT üretmeli")

    def test_dpad_up_remapped_to_hard_drop_with_right(self):
        """D-pad Up Hard Drop'a atandığında: K_SPACE üretilmeli, K_UP bastırılmalı, K_RIGHT kaybolmamalı."""
        # D-pad Up (11) butonunu hard_drop'a bağla
        self.gpm._bindings['hard_drop'] = {'button': 11}
        # rotate'i button 11'den çıkar (veya rotate çakışsa bile hard_drop öncelikli olmalı)
        gp = self._create_mock_gamepad_state(hat=(1, 1), buttons={11: True, 14: True})
        gp.prev_buttons[11] = False
        gp.prev_buttons[14] = False

        # 1. Button eventleri üret: Button 11 -> hard_drop -> K_SPACE
        btn_events = self.gpm._generate_button_events(gp)
        btn_keys = [e.key for e in btn_events if e.type == pygame.KEYDOWN]
        self.assertIn(pygame.K_SPACE, btn_keys, "Button 11 Hard Drop olarak K_SPACE üretmeli")

        # 2. D-pad eventleri üret: Up bastırılmalı, Right (14) K_RIGHT üretmeli
        dpad_events = self.gpm._generate_dpad_events(gp, delta_ms=16.6)
        dpad_keys = [e.key for e in dpad_events if e.type == pygame.KEYDOWN]
        self.assertNotIn(pygame.K_UP, dpad_keys, "Remap edilen D-pad Up doğal K_UP üretmemeli (bastırılmalı)")
        self.assertIn(pygame.K_RIGHT, dpad_keys, "D-pad Right K_RIGHT üretmeye devam etmeli")

    def test_a_button_remapped_to_rotate_overrides_slot_1(self):
        """Kullanıcı A/Cross (0) butonunu Rotate'a atadığında, Rotate Slot 1'e öncelikli olmalı."""
        # A butonu (0) hem rotate hem de slot_1'e atanmış durumda
        self.gpm._bindings['rotate'] = {'button': 0}
        self.gpm._bindings['slot_1'] = {'button': 0}

        gp = self._create_mock_gamepad_state(buttons={0: True})
        gp.prev_buttons[0] = False

        btn_events = self.gpm._generate_button_events(gp)
        event_keys = [e.key for e in btn_events if e.type == pygame.KEYDOWN]
        self.assertIn(pygame.K_UP, event_keys, "A butonu Rotate (K_UP) üretmeli, slot_1 tarafından gasp edilmemeli")

    def test_menu_context_confirm_and_back_preserved(self):
        """Menü bağlamında A/Cross confirm, B/Circle back davranışları korunmalı."""
        self.gpm.set_context('menu')
        self.gpm._bindings['menu_confirm'] = {'button': 0}
        self.gpm._bindings['menu_back'] = {'button': 1}

        # A basıldı
        gp_a = self._create_mock_gamepad_state(buttons={0: True})
        gp_a.prev_buttons[0] = False
        events_a = self.gpm._generate_button_events(gp_a)
        keys_a = [e.key for e in events_a if e.type == pygame.KEYDOWN]
        self.assertIn(pygame.K_RETURN, keys_a, "Menüde A butonu K_RETURN üretmeli")

        # B basıldı
        gp_b = self._create_mock_gamepad_state(buttons={1: True})
        gp_b.prev_buttons[1] = False
        events_b = self.gpm._generate_button_events(gp_b)
        keys_b = [e.key for e in events_b if e.type == pygame.KEYDOWN]
        self.assertIn(pygame.K_ESCAPE, keys_b, "Menüde B butonu K_ESCAPE üretmeli")

    def test_button_collision_resolution_deterministic(self):
        """Aynı butona birden fazla temel/kart aksiyonu atandığında deterministik öncelik geçerli olmalı."""
        # Buton 2'ye hem soft_drop (öncelik 85) hem card_bomb (öncelik 50) atandı
        self.gpm._bindings['soft_drop'] = {'button': 2}
        self.gpm._bindings['card_bomb'] = {'button': 2}

        gp = self._create_mock_gamepad_state(buttons={2: True})
        gp.prev_buttons[2] = False

        btn_events = self.gpm._generate_button_events(gp)
        event_keys = [e.key for e in btn_events if e.type == pygame.KEYDOWN]
        self.assertIn(pygame.K_DOWN, event_keys, "Yüksek öncelikli soft_drop (K_DOWN) seçilmeli")


if __name__ == '__main__':
    unittest.main()
