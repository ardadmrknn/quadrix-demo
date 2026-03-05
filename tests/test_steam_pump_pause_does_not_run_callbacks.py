"""
Steam Pump Pause → RunCallbacks Engelleme Testi

pump thread paused durumdayken SteamAPI_RunCallbacks'in çağrılmadığını doğrular.
"""
from __future__ import annotations

import sys
import os
import importlib.util
import time
import unittest
from unittest.mock import patch, MagicMock

# ---------------------------------------------------------------------------
# Gerçek steam_integration modülünü zorla yükle (stub baskısına karşı).
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

import steam_integration  # noqa: E402


class TestSteamPumpCallbacksNotCalledWhenPaused(unittest.TestCase):
    """Pump thread paused iken SteamAPI_RunCallbacks çağrılmamalı."""

    def setUp(self):
        self._orig_dll = steam_integration._dll
        self._orig_init_ok = steam_integration._init_ok
        self._orig_pump_running = steam_integration._pump_running
        self._orig_paused = steam_integration._pump_paused
        self._orig_count = steam_integration._pump_pause_count

    def tearDown(self):
        steam_integration._dll = self._orig_dll
        steam_integration._init_ok = self._orig_init_ok
        steam_integration._pump_running = self._orig_pump_running
        steam_integration._pump_paused = self._orig_paused
        steam_integration._pump_pause_count = self._orig_count
        steam_integration._pump_paused_event.clear()

    def test_callbacks_not_called_when_paused(self):
        """pump thread'i simüle et; paused iken RunCallbacks mock'u çağrılmamalı."""
        mock_dll = MagicMock()
        steam_integration._dll = mock_dll
        steam_integration._init_ok = True
        steam_integration._pump_paused = True
        steam_integration._pump_running = True

        iteration_count = [0]

        def fake_sleep(_t):
            iteration_count[0] += 1
            if iteration_count[0] >= 3:
                steam_integration._pump_running = False
            # Gerçek sleep yok — test hızlı çalışsın

        with patch('time.sleep', fake_sleep):
            steam_integration._callback_pump_loop()

        mock_dll.SteamAPI_RunCallbacks.assert_not_called()

    def test_callbacks_called_when_not_paused(self):
        """pump thread paused değilken RunCallbacks çağrılmalı."""
        mock_dll = MagicMock()
        steam_integration._dll = mock_dll
        steam_integration._init_ok = True
        steam_integration._pump_paused = False
        steam_integration._pump_running = True

        iteration_count = [0]

        def fake_sleep(_t):
            iteration_count[0] += 1
            if iteration_count[0] >= 2:
                steam_integration._pump_running = False

        with patch('time.sleep', fake_sleep):
            steam_integration._callback_pump_loop()

        self.assertTrue(mock_dll.SteamAPI_RunCallbacks.call_count >= 1)

    def test_paused_event_set_when_paused_in_loop(self):
        """Pump döngüsü paused iken _pump_paused_event'i set etmeli (ack sinyali)."""
        mock_dll = MagicMock()
        steam_integration._dll = mock_dll
        steam_integration._init_ok = True
        steam_integration._pump_paused = True
        steam_integration._pump_running = True
        steam_integration._pump_paused_event.clear()

        iteration_count = [0]

        def fake_sleep(_t):
            iteration_count[0] += 1
            if iteration_count[0] >= 1:
                steam_integration._pump_running = False

        with patch('time.sleep', fake_sleep):
            steam_integration._callback_pump_loop()

        # Paused branch'inde event set edilmiş olmalı
        self.assertTrue(steam_integration._pump_paused_event.is_set())


if __name__ == '__main__':
    unittest.main()
