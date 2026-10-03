"""Gamepad oyuncu yönlendirme (player routing) testleri — quadrix-demo varyantı.

Gamepad_Iade_Nedeni_Cozum_Proje_Referansi.md 13 — bu depo için KAPSAM
NOTU: yerel PvP/Coop modları demo'da BULUNUR ve kilitli DEĞİL
(demo_config.py yalnız online modları kilitler), ancak:

- Atama lobisi (current_input == 0 / gamepad_assignments sözlüğü) ve
  device_index bazlı P1/P2 filtresi (is_p1_gp / is_p2_gp) v2'ye ÖZGÜDÜR —
  bu depoda p1_gamepad_idx / gamepad_assignments / is_p1_gp eşleşmeleri
  SIFIRDIR (grep kanıtı). İki cihazın sentetik tuşları event.key'e göre
  aynı oyuncu kollarına düşer; cihaz kimliği ayrıştırılmaz.
- plans/2026-04-18-yerel-pvp-coop-cift-gamepad-destegi-plan.md (Faz 1/2/3:
  local_mode / player_slots / gamepad_player) bu depoya uygulanmamıştır
  (Status: Draft). Plan uygulandığında v2'deki
  tests/test_gamepad_player_routing.py'nin routing bölümü buraya
  taşınmalıdır.
- v2 rumble imzası `device_index=` parametresi KABUL EDER; demo imzası
  (gamepad_manager.py:2736) yalnız (low, high, duration_ms) alır ve her
  zaman AKTİF cihada titretir — cihaz hedefleme demo'da YOK.

Bu dosya iki depoda ORTAK manager katmanını kapsar:
- _make_key_event device_index + action metadata taşır (ayrıştırmanın
  altyapısı; v2'deki filtre bu metadata'yı tüketir).
- _find_gamepad_for_event: joy_id doğrudan çözümü + bilinmeyen kimlikte
  aktif cihaza fallback.
- rumble: çoklu cihaz durumunda yalnız AKTİF (ilk init'li) cihaz titrer.

Desen referansı: tests/test_gamepad_hotplug.py (_make_manager + fake
gamepad), v2 tests/test_gamepad_player_routing.py (tam routing seti).
"""

from __future__ import annotations

import copy
import os
import sys
import types

import pytest

_SRC_DIR_STR = os.path.join(os.path.dirname(__file__), '..', 'src')
if _SRC_DIR_STR not in sys.path:
    sys.path.insert(0, _SRC_DIR_STR)

import pygame  # noqa: E402

from gamepad_manager import (  # noqa: E402
    DEFAULT_GAMEPAD_BINDINGS,
    GamepadManager,
    GamepadState,
)


@pytest.fixture(scope='module', autouse=True)
def _pygame_init():
    pygame.init()
    yield


def _fake_joystick(rumble_log=None):
    js = types.SimpleNamespace(
        get_init=lambda: True,
        get_name=lambda: 'Pad',
        quit=lambda: None,
    )
    if rumble_log is not None:
        js.rumble = lambda low, high, dur: rumble_log.append((low, high, dur))
    return js


def _make_manager():
    """Minimal GamepadManager (test_gamepad_hotplug.py deseni)."""
    manager = GamepadManager.__new__(GamepadManager)
    manager.gamepads = {}
    manager.enabled = True
    manager.rumble_multiplier = 1.0
    manager.rumble_enabled = True
    manager._context = GamepadManager.CONTEXT_GAME
    manager._menu_pointer_active = False
    manager._suppress_pointer_mode = False
    manager._bindings = copy.deepcopy(DEFAULT_GAMEPAD_BINDINGS)
    manager.DEADZONE = 0.35
    manager.DIGITAL_THRESHOLD = 0.6
    manager.TRIGGER_THRESHOLD = 0.5
    return manager


# ---------------------------------------------------------------------------
# Sentetik event üretimi — cihaz kimliği metadata'sı
# ---------------------------------------------------------------------------

def test_make_key_event_carries_device_index_and_action():
    """_make_key_event cihaz kimliğini taşır: v2'deki P1/P2 ayrıştırması
    tamamen bu metadata'ya dayanır (DUZ-007 sözleşmesi); demo'da üretici
    katman aynı, tüketen filtre henüz yok."""
    manager = _make_manager()

    event = manager._make_key_event(
        pygame.K_LEFT, pygame.KEYDOWN, gp_device_index=4, action='move_left',
    )

    assert event.type == pygame.KEYDOWN
    assert event.key == pygame.K_LEFT
    assert event.from_gamepad is True
    assert event.device_index == 4
    assert event.action == 'move_left'
    assert event.mod == 0


def test_find_gamepad_for_event_resolves_joy_id_and_falls_back_to_active():
    manager = _make_manager()
    pad_a = GamepadState(device_index=0, instance_id=111, joystick=_fake_joystick())
    pad_b = GamepadState(device_index=1, instance_id=222, joystick=_fake_joystick())
    manager.gamepads[0] = pad_a
    manager.gamepads[1] = pad_b
    try:
        # joy_id doğrudan sözlük anahtarıyla çözülür.
        assert manager._find_gamepad_for_event(joy_id=1) is pad_b
        # instance_id cihazlar arasında taranarak bulunur.
        assert manager._find_gamepad_for_event(instance_id=222) is pad_b
        # Bilinmeyen kimlik → aktif (ilk init'li) cihaza fallback.
        assert manager._find_gamepad_for_event(joy_id=9) is pad_a
    finally:
        manager.gamepads.clear()


# ---------------------------------------------------------------------------
# Rumble — demo sözleşmesi: hedefleme yok, aktif cihaz titrer
# ---------------------------------------------------------------------------

def test_rumble_uses_active_gamepad_when_multiple_connected():
    """Demo rumble imzası device_index KABUL ETMEZ (gamepad_manager.py:2736):
    iki cihaz bağlıyken titreşim yalnız AKTİF (ilk init'li) cihaza gider.
    v2'de cihaz hedefleme (PvP galibiyet titreşimi) device_index= ile
    yapılır — o imza bu depoya planin PvP/coop fazıyla gelir."""
    manager = _make_manager()
    rumble_a = []
    rumble_b = []
    pad_a = GamepadState(device_index=0, joystick=_fake_joystick(rumble_a))
    pad_b = GamepadState(device_index=1, joystick=_fake_joystick(rumble_b))
    manager.gamepads[0] = pad_a
    manager.gamepads[1] = pad_b
    try:
        assert manager.get_active_gamepad() is pad_a

        manager.rumble(0.3, 0.6, 120)

        assert rumble_a == [(0.3, 0.6, 120)]
        assert rumble_b == [], 'aktif olmayan cihaz titrememeli'
    finally:
        manager.gamepads.clear()
