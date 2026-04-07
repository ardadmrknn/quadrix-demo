"""Steam shutdown, izlenen worker thread'leri beklemeli.

Ana menüye dönüşte tetiklenen leaderboard worker'ı gibi Steam API kullanan
arka plan işleri bitmeden SteamAPI_Shutdown çağrılırsa macOS'ta crash/hang
riski oluşur. Bu test shutdown sıralamasını kilitler.
"""
from __future__ import annotations

import importlib.util
import os
import sys
import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch


_src_dir = os.path.join(os.path.dirname(__file__), '..', 'src')
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

_real_spec = importlib.util.spec_from_file_location(
    'steam_integration',
    os.path.join(_src_dir, 'steam_integration.py'),
)
_real_mod = importlib.util.module_from_spec(_real_spec)
sys.modules['steam_integration'] = _real_mod
_real_spec.loader.exec_module(_real_mod)

import steam_integration  # noqa: E402


class TestSteamShutdownWaitsWorkers(unittest.TestCase):
    def setUp(self):
        self._orig_dll = steam_integration._dll
        self._orig_dll_loaded = steam_integration._dll_loaded
        self._orig_init_ok = steam_integration._init_ok
        self._orig_exit_requested = steam_integration._exit_requested
        self._orig_shutdown_requested = steam_integration._shutdown_requested
        self._orig_pump_thread = steam_integration._pump_thread
        self._orig_pump_running = steam_integration._pump_running
        self._orig_pump_paused = steam_integration._pump_paused
        self._orig_pump_pause_count = steam_integration._pump_pause_count
        self._orig_precache_thread = steam_integration._precache_thread
        self._orig_worker_threads = set(steam_integration._worker_threads)
        self._orig_isteam_friends = steam_integration._isteam_friends
        self._orig_isteam_user = steam_integration._isteam_user
        self._orig_isteam_user_stats = steam_integration._isteam_user_stats
        self._orig_isteam_utils = steam_integration._isteam_utils
        self._orig_isteam_apps = steam_integration._isteam_apps

        steam_integration._exit_requested = False
        steam_integration._shutdown_requested = False
        steam_integration._pump_thread = None
        steam_integration._pump_running = False
        steam_integration._pump_paused = False
        steam_integration._pump_pause_count = 0
        steam_integration._precache_thread = None
        steam_integration._worker_threads.clear()

    def tearDown(self):
        steam_integration._dll = self._orig_dll
        steam_integration._dll_loaded = self._orig_dll_loaded
        steam_integration._init_ok = self._orig_init_ok
        steam_integration._exit_requested = self._orig_exit_requested
        steam_integration._shutdown_requested = self._orig_shutdown_requested
        steam_integration._pump_thread = self._orig_pump_thread
        steam_integration._pump_running = self._orig_pump_running
        steam_integration._pump_paused = self._orig_pump_paused
        steam_integration._pump_pause_count = self._orig_pump_pause_count
        steam_integration._precache_thread = self._orig_precache_thread
        steam_integration._worker_threads.clear()
        steam_integration._worker_threads.update(self._orig_worker_threads)
        steam_integration._isteam_friends = self._orig_isteam_friends
        steam_integration._isteam_user = self._orig_isteam_user
        steam_integration._isteam_user_stats = self._orig_isteam_user_stats
        steam_integration._isteam_utils = self._orig_isteam_utils
        steam_integration._isteam_apps = self._orig_isteam_apps

    def test_request_shutdown_stops_new_workers_only_on_macos(self):
        steam_integration._dll = SimpleNamespace()
        steam_integration._dll_loaded = True
        steam_integration._init_ok = True

        with patch.object(steam_integration.sys, 'platform', 'darwin'):
            steam_integration.request_shutdown()

            self.assertTrue(steam_integration.should_cancel_background_work())
            self.assertTrue(steam_integration.is_available())
            started = steam_integration._start_tracked_worker(lambda: None, name='blocked-worker')
            self.assertIsNone(started)

    def test_request_shutdown_is_noop_off_macos(self):
        release_event = threading.Event()

        def worker() -> None:
            release_event.wait(timeout=0.2)

        with patch.object(steam_integration.sys, 'platform', 'linux'):
            steam_integration.request_shutdown()
            self.assertFalse(steam_integration.should_cancel_background_work())
            started = steam_integration._start_tracked_worker(worker, name='non-macos-worker')

        self.assertIsNotNone(started)
        self.assertIn(started, steam_integration._worker_threads)

        release_event.set()
        started.join(timeout=0.5)

    def test_macos_shutdown_skips_api_shutdown_if_worker_is_still_alive(self):
        release_event = threading.Event()
        order: list[str] = []

        def worker() -> None:
            release_event.wait(timeout=1.2)

        started = steam_integration._start_tracked_worker(worker, name='macos-stuck-worker')
        self.assertIsNotNone(started, 'Test worker baslatilamadi')

        def fake_shutdown() -> None:
            order.append('api_shutdown')

        steam_integration._dll = SimpleNamespace(SteamAPI_Shutdown=fake_shutdown)
        steam_integration._dll_loaded = True
        steam_integration._init_ok = True

        with patch.object(steam_integration.sys, 'platform', 'darwin'):
            steam_integration.shutdown()

        self.assertNotIn('api_shutdown', order, 'macOS yolunda yaşayan worker varken SteamAPI_Shutdown çağrıldı')

        release_event.set()
        started.join(timeout=0.5)

    def test_shutdown_waits_for_tracked_worker_before_api_shutdown(self):
        order: list[str] = []
        worker_finished = threading.Event()

        def worker() -> None:
            order.append('worker_start')
            deadline = time.monotonic() + 1.0
            while not steam_integration._shutdown_requested and time.monotonic() < deadline:
                time.sleep(0.01)
            order.append('worker_exit')
            worker_finished.set()

        started = steam_integration._start_tracked_worker(worker, name='test-shutdown-worker')
        self.assertIsNotNone(started, 'Test worker baslatilamadi')

        def fake_shutdown() -> None:
            order.append('api_shutdown')

        steam_integration._dll = SimpleNamespace(SteamAPI_Shutdown=fake_shutdown)
        steam_integration._dll_loaded = True
        steam_integration._init_ok = True

        steam_integration.shutdown()

        self.assertTrue(worker_finished.is_set(), 'Worker shutdown öncesi tamamlanmadi')
        self.assertIn('api_shutdown', order, 'SteamAPI_Shutdown çağrilmadi')
        self.assertLess(
            order.index('worker_exit'),
            order.index('api_shutdown'),
            f'Yanlis sira: {order}',
        )
        self.assertFalse(steam_integration._worker_threads, 'Worker kaydi temizlenmedi')


if __name__ == '__main__':
    unittest.main()