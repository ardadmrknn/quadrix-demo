"""
Steam Pump Pause Ref-count Testleri

pause_pump() / resume_pump() ref-count (sayaca dayalı) davranışını doğrular:
  - Nested pause/resume güvenli çalışmalı
  - resume, count sıfırlanmadan pump'ı açmamalı
  - Count asla negatife düşmemeli
"""
from __future__ import annotations

import sys
import os
import importlib.util
import threading
import unittest
from unittest.mock import patch, MagicMock

# ---------------------------------------------------------------------------
# Gerçek steam_integration modülünü zorla yükle.
# Bazı test dosyaları (ör. test_extras_includes_classic.py) modül seviyesinde
# sys.modules['steam_integration'] yerine boş bir types.ModuleType koyar.
# Bu, alfabetik collection sırasında daha sonra gelen bu dosyanın boş stub
# almasına neden olur. Aşağıdaki kod her durumda gerçek modülü yükler.
# ---------------------------------------------------------------------------
_src_dir = os.path.join(os.path.dirname(__file__), '..', 'src')
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

_real_spec = importlib.util.spec_from_file_location(
    'steam_integration',
    os.path.join(_src_dir, 'steam_integration.py'),
)
_real_mod = importlib.util.module_from_spec(_real_spec)
sys.modules['steam_integration'] = _real_mod   # stub varsa üzerine yaz
_real_spec.loader.exec_module(_real_mod)

import steam_integration  # noqa: E402  — artık gerçek modülü alır


class TestSteamPumpPauseRefcount(unittest.TestCase):
    """pause_pump / resume_pump ref-count mantığını test eder."""

    def _reset_state(self):
        steam_integration._pump_pause_count = 0
        steam_integration._pump_paused = False
        steam_integration._pump_paused_event.clear()
        # DLL ve init_ok'u kapa — lock/wait takılmasın
        steam_integration._dll = None
        steam_integration._init_ok = False

    def setUp(self):
        self._orig_dll = steam_integration._dll
        self._orig_init_ok = steam_integration._init_ok
        self._orig_count = steam_integration._pump_pause_count
        self._orig_paused = steam_integration._pump_paused
        self._reset_state()

    def tearDown(self):
        steam_integration._dll = self._orig_dll
        steam_integration._init_ok = self._orig_init_ok
        steam_integration._pump_pause_count = self._orig_count
        steam_integration._pump_paused = self._orig_paused
        steam_integration._pump_paused_event.clear()

    # ------------------------------------------------------------------

    def test_pause_sets_paused_true(self):
        """pause() sonrası _pump_paused True olmalı."""
        with patch.object(steam_integration._pump_paused_event, 'wait', return_value=True):
            steam_integration.pause_pump()
        self.assertTrue(steam_integration._pump_paused)

    def test_pause_increments_count(self):
        """Her pause() çağrısı count'u 1 artırmalı."""
        with patch.object(steam_integration._pump_paused_event, 'wait', return_value=True):
            steam_integration.pause_pump()
            self.assertEqual(steam_integration._pump_pause_count, 1)
            steam_integration.pause_pump()
            self.assertEqual(steam_integration._pump_pause_count, 2)

    def test_pause_twice_resume_once_still_paused(self):
        """pause×2 → resume×1 → pump hala paused olmalı."""
        with patch.object(steam_integration._pump_paused_event, 'wait', return_value=True):
            steam_integration.pause_pump()
            steam_integration.pause_pump()
        steam_integration.resume_pump()
        self.assertTrue(steam_integration._pump_paused)
        self.assertEqual(steam_integration._pump_pause_count, 1)

    def test_pause_twice_resume_twice_unpaused(self):
        """pause×2 → resume×2 → pump unpaused olmalı."""
        with patch.object(steam_integration._pump_paused_event, 'wait', return_value=True):
            steam_integration.pause_pump()
            steam_integration.pause_pump()
        steam_integration.resume_pump()
        steam_integration.resume_pump()
        self.assertFalse(steam_integration._pump_paused)
        self.assertEqual(steam_integration._pump_pause_count, 0)

    def test_resume_without_pause_no_negative_count(self):
        """resume çağrısı count'u negatif yapmamalı."""
        steam_integration.resume_pump()
        self.assertGreaterEqual(steam_integration._pump_pause_count, 0)

    def test_resume_without_pause_keeps_paused_false(self):
        """Pause edilmemiş durumda resume() _pump_paused'u True yapmamalı."""
        steam_integration.resume_pump()
        self.assertFalse(steam_integration._pump_paused)

    def test_pause_once_resume_once_unpaused(self):
        """Normal tekil pause/resume: unpaused olmalı."""
        with patch.object(steam_integration._pump_paused_event, 'wait', return_value=True):
            steam_integration.pause_pump()
        steam_integration.resume_pump()
        self.assertFalse(steam_integration._pump_paused)
        self.assertEqual(steam_integration._pump_pause_count, 0)

    def test_count_never_goes_below_zero(self):
        """Birden fazla resume bile count'u negatife götürmemeli."""
        steam_integration.resume_pump()
        steam_integration.resume_pump()
        steam_integration.resume_pump()
        self.assertEqual(steam_integration._pump_pause_count, 0)


if __name__ == '__main__':
    unittest.main()
