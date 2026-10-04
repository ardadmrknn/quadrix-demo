"""GP-001 — Gamepad buton çakışma çözümü (collision resolution) testleri.

İade nedeni: v2'de `_generate_button_events` buton→aksiyon eşlemesini
son-yazan-kazanır (last-write-wins) dict ile kuruyor. Kullanıcı D-pad Up
(11) gibi bir butonu hard_drop'a bağlayıp rotate de aynı butona düştüğünde
dict'te rotate kalıyor; D-pad tarafı ise "yön override edildi" diyerek
doğal Up'ı bastırıyor. Sonuç: buton ÖLÜ girdiye dönüşüyor (hiç event yok).

Bu dosya demo'da kanıtlanmış deterministik öncelik çözümünün v2 tarafını
test eder (priorite: hard_drop 100 > rotate 95 > ... > kart aksiyonları 50)
ve D-pad remap bastırma davranışının (Kural 1) kazanan aksiyonla birlikte
çalışmasını güvence altına alır.
"""
import os
import sys
import pathlib
import unittest

ROOT_DIR = pathlib.Path(__file__).parent.parent
SRC_DIR = ROOT_DIR / 'src'
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import pygame  # noqa: E402
from gamepad_manager import GamepadManager, GamepadState  # noqa: E402


class TestGamepadBindingCollisionResolution(unittest.TestCase):
    """Buton çakışması, D-pad remap bastırma ve menü bağlamı testleri."""

    def setUp(self):
        os.environ['SDL_VIDEODRIVER'] = 'dummy'
        os.environ['SDL_AUDIODRIVER'] = 'dummy'
        pygame.init()
        pygame.joystick.init()
        self.gpm = GamepadManager()
        # Otomatik cihaz taramasını kapat: mock state uçmasın
        self.gpm._check_connections = lambda: None
        self.gpm.set_context('game')

    def tearDown(self):
        pygame.quit()

    def _create_mock_gamepad_state(self, hat=(0, 0), buttons=None):
        gp = GamepadState(device_index=0)
        gp.dpad = hat
        gp.prev_dpad = (0, 0)
        if buttons:
            gp.buttons.update(buttons)
            for btn in buttons:
                gp.prev_buttons[btn] = False
        return gp

    def test_dpad_up_hard_drop_and_rotate_same_button_hard_drop_wins(self):
        """GP-001 ana senaryosu: hard_drop=11 + rotate=11 → K_SPACE üretilmeli, K_UP bastırılmalı.

        v2'nin hatalı davranışında son-yazan rotate kazanıyor, D-pad kontrolü onu
        atlıyor ve _generate_dpad_events 'up' override'ı bastırdığı için toplam
        SIFIR event üretiliyordu (ölü girdi).
        """
        self.gpm._bindings['hard_drop'] = {'button': 11}
        self.gpm._bindings['rotate'] = {'button': 11}

        gp = self._create_mock_gamepad_state(hat=(0, 1), buttons={11: True})

        btn_events = self.gpm._generate_button_events(gp)
        btn_down = [e for e in btn_events if e.type == pygame.KEYDOWN]
        self.assertTrue(
            any(e.key == pygame.K_SPACE for e in btn_down),
            "hard_drop (öncelik 100) kazanan olmalı ve K_SPACE KEYDOWN üretmeli",
        )
        self.assertTrue(
            any(getattr(e, 'action', None) == 'hard_drop' for e in btn_down if e.key == pygame.K_SPACE),
            "K_SPACE event'inin action metadata'sı hard_drop olmalı",
        )
        self.assertFalse(
            any(e.key == pygame.K_UP for e in btn_events),
            "Çakışmayı kaybeden rotate için buton event'i üretilmemeli",
        )

        dpad_events = self.gpm._generate_dpad_events(gp, delta_ms=16.6)
        dpad_keys = [e.key for e in dpad_events if e.type == pygame.KEYDOWN]
        self.assertNotIn(
            pygame.K_UP, dpad_keys,
            "Buton 11 hard_drop'a remap edildiği için doğal D-pad Up K_UP üretmemeli (Kural 1)",
        )

    def test_collision_keyup_uses_same_winner(self):
        """Aynı kazanan aksiyon KEYUP tarafında da tutarlı olmalı (basma/bırakma simetrisi)."""
        self.gpm._bindings['hard_drop'] = {'button': 11}
        self.gpm._bindings['rotate'] = {'button': 11}

        gp = self._create_mock_gamepad_state(hat=(0, 0), buttons={})
        gp.buttons[11] = False
        gp.prev_buttons[11] = True

        btn_events = self.gpm._generate_button_events(gp)
        ups = [e for e in btn_events if e.type == pygame.KEYUP]
        self.assertTrue(any(e.key == pygame.K_SPACE for e in ups), "Bırakışta K_SPACE KEYUP üretilmeli")
        self.assertFalse(any(e.key == pygame.K_UP for e in ups), "Kaybeden rotate KEYUP üretmemeli")

    def test_dpad_up_remapped_to_hard_drop_with_right(self):
        """D-pad Up Hard Drop'a atandığında: K_SPACE üretilmeli, K_UP bastırılmalı, K_RIGHT kaybolmamalı."""
        self.gpm._bindings['hard_drop'] = {'button': 11}

        gp = self._create_mock_gamepad_state(hat=(1, 1), buttons={11: True, 14: True})

        btn_events = self.gpm._generate_button_events(gp)
        btn_keys = [e.key for e in btn_events if e.type == pygame.KEYDOWN]
        self.assertIn(pygame.K_SPACE, btn_keys, "Button 11 Hard Drop olarak K_SPACE üretmeli")

        dpad_events = self.gpm._generate_dpad_events(gp, delta_ms=16.6)
        dpad_keys = [e.key for e in dpad_events if e.type == pygame.KEYDOWN]
        self.assertNotIn(pygame.K_UP, dpad_keys, "Remap edilen D-pad Up doğal K_UP üretmemeli")
        self.assertIn(pygame.K_RIGHT, dpad_keys, "D-pad Right K_RIGHT üretmeye devam etmeli")

    def test_diagonal_hat_up_plus_right_both_processed(self):
        """Hat (1, 1) geldiğinde hem Up hem Right yönleri aynı frame içinde üretilmeli."""
        gp = self._create_mock_gamepad_state(hat=(1, 1))
        events = self.gpm._generate_dpad_events(gp, delta_ms=16.6)
        event_keys = [e.key for e in events if e.type == pygame.KEYDOWN]
        self.assertIn(pygame.K_UP, event_keys, "D-pad Up K_UP üretmeli")
        self.assertIn(pygame.K_RIGHT, event_keys, "D-pad Right K_RIGHT üretmeli")

    def test_button_collision_resolution_deterministic(self):
        """Aynı butona birden fazla temel/kart aksiyonu atandığında deterministik öncelik geçerli olmalı."""
        # Buton 2'ye hem soft_drop (öncelik 85) hem card_bomb (öncelik 50) atandı
        self.gpm._bindings['soft_drop'] = {'button': 2}
        self.gpm._bindings['card_bomb'] = {'button': 2}

        gp = self._create_mock_gamepad_state(buttons={2: True})

        btn_events = self.gpm._generate_button_events(gp)
        event_keys = [e.key for e in btn_events if e.type == pygame.KEYDOWN]
        self.assertIn(pygame.K_DOWN, event_keys, "Yüksek öncelikli soft_drop (K_DOWN) seçilmeli")

    def test_a_button_rotate_overrides_lower_priority_action(self):
        """A/Cross (0) hem rotate (95) hem düşük öncelikli bir kart aksiyonuna (50) atanırsa rotate kazanmalı."""
        self.gpm._bindings['rotate'] = {'button': 0}
        self.gpm._bindings['card_bomb'] = {'button': 0}

        gp = self._create_mock_gamepad_state(buttons={0: True})

        btn_events = self.gpm._generate_button_events(gp)
        event_keys = [e.key for e in btn_events if e.type == pygame.KEYDOWN]
        self.assertIn(pygame.K_UP, event_keys, "A butonu Rotate (K_UP) üretmeli, düşük öncelikli aksiyon gasp etmemeli")

    def test_menu_context_confirm_and_back_preserved(self):
        """Menü bağlamında A/Cross confirm, B/Circle back davranışları korunmalı."""
        self.gpm.set_context('menu')
        self.gpm._bindings['menu_confirm'] = {'button': 0}
        self.gpm._bindings['menu_back'] = {'button': 1}

        gp_a = self._create_mock_gamepad_state(buttons={0: True})
        events_a = self.gpm._generate_button_events(gp_a)
        keys_a = [e.key for e in events_a if e.type == pygame.KEYDOWN]
        self.assertIn(pygame.K_RETURN, keys_a, "Menüde A butonu K_RETURN üretmeli")

        gp_b = self._create_mock_gamepad_state(buttons={1: True})
        events_b = self.gpm._generate_button_events(gp_b)
        keys_b = [e.key for e in events_b if e.type == pygame.KEYDOWN]
        self.assertIn(pygame.K_ESCAPE, keys_b, "Menüde B butonu K_ESCAPE üretmeli")


if __name__ == '__main__':
    unittest.main()
