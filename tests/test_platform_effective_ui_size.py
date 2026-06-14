"""platform_utils effective UI size helper testleri.

Faz 1 kapsamı:
- display surface için logical window size okunur
- offscreen surface'ler yanlışlıkla display DPI mantığına sokulmaz
- Windows effective UI size, sistem DPI ölçeğine göre normalize edilir
"""

from __future__ import annotations

import pathlib
import sys
import types
import unittest
from unittest.mock import MagicMock, patch


ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / 'src'

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


def _make_pygame_stub():
    pg = types.ModuleType('pygame')
    pg.NOFRAME = 32
    pg.DOUBLEBUF = 1
    pg.HWSURFACE = 2
    pg.FULLSCREEN = 4
    pg.RESIZABLE = 16
    pg.VIDEORESIZE = 256
    pg.KMOD_META = 1024
    pg.KMOD_ALT = 256
    pg.K_F10 = 300
    pg.K_F12 = 301
    pg.K_RETURN = 13
    pg.K_KP_ENTER = 271
    pg.KMOD_CTRL = 64

    class Surface:
        def __init__(self, size=(0, 0), flags=0, depth=0):
            self._size = size

        def get_size(self):
            return self._size

    pg.Surface = Surface

    class _Info:
        current_w = 1920
        current_h = 1080

    class _display:
        _surface = None

        @staticmethod
        def Info():
            return _Info()

        @staticmethod
        def get_surface():
            return _display._surface

        @staticmethod
        def get_window_size():
            if _display._surface is None:
                return (0, 0)
            return _display._surface.get_size()

        @staticmethod
        def set_mode(size, flags=0):
            surf = Surface(size)
            _display._surface = surf
            return surf

    pg.display = _display
    pg.error = Exception
    return pg


_pg_stub = _make_pygame_stub()
sys.modules['pygame'] = _pg_stub

import importlib

if 'platform_utils' in sys.modules:
    del sys.modules['platform_utils']
platform_utils = importlib.import_module('platform_utils')


def _force_windows(module):
    module.IS_WINDOWS = True
    module.IS_MACOS = False
    module.IS_LINUX = False


def _force_macos(module):
    module.IS_WINDOWS = False
    module.IS_MACOS = True
    module.IS_LINUX = False


def _force_linux(module):
    module.IS_WINDOWS = False
    module.IS_MACOS = False
    module.IS_LINUX = True


class TestGetWindowLogicalSize(unittest.TestCase):
    def tearDown(self):
        _force_linux(platform_utils)

    def test_uses_window_size_for_active_display_surface(self):
        _force_macos(platform_utils)
        display_surface = platform_utils.pygame.Surface((2880, 1800))

        with patch.object(platform_utils.pygame.display, 'get_surface', return_value=display_surface, create=True), \
             patch.object(platform_utils.pygame.display, 'get_window_size', return_value=(1440, 900), create=True):
            self.assertEqual(platform_utils.get_window_logical_size(display_surface), (1440, 900))

    def test_offscreen_surface_keeps_own_size(self):
        _force_windows(platform_utils)
        display_surface = platform_utils.pygame.Surface((2560, 1660))
        offscreen_surface = platform_utils.pygame.Surface((900, 600))

        with patch.object(platform_utils.pygame.display, 'get_surface', return_value=display_surface, create=True), \
             patch.object(platform_utils.pygame.display, 'get_window_size', return_value=(1707, 1107), create=True):
            self.assertEqual(platform_utils.get_window_logical_size(offscreen_surface), (900, 600))


class TestWindowsSystemScaleFactor(unittest.TestCase):
    def tearDown(self):
        _force_linux(platform_utils)

    def test_reads_get_dpi_for_system_when_available(self):
        _force_windows(platform_utils)
        fake_ctypes = MagicMock()
        fake_ctypes.windll.user32.GetDpiForSystem.return_value = 144

        with patch.dict('sys.modules', {'ctypes': fake_ctypes}):
            self.assertAlmostEqual(platform_utils._get_windows_system_scale_factor(), 1.5)

    def test_returns_one_on_invalid_dpi(self):
        _force_windows(platform_utils)
        fake_ctypes = MagicMock()
        fake_ctypes.windll.user32.GetDpiForSystem.return_value = 0
        fake_ctypes.windll.gdi32.GetDeviceCaps.return_value = 0
        fake_ctypes.windll.user32.GetDC.return_value = 1
        fake_ctypes.windll.user32.ReleaseDC.return_value = 1

        with patch.dict('sys.modules', {'ctypes': fake_ctypes}):
            self.assertEqual(platform_utils._get_windows_system_scale_factor(), 1.0)


class TestWindowsWindowScaleFactor(unittest.TestCase):
    def tearDown(self):
        _force_linux(platform_utils)

    def test_prefers_window_specific_dpi_when_available(self):
        _force_windows(platform_utils)
        fake_ctypes = MagicMock()
        fake_ctypes.windll.user32.GetDpiForWindow.return_value = 144

        with patch.dict('sys.modules', {'ctypes': fake_ctypes}), \
             patch.object(platform_utils, '_get_windows_active_hwnd', return_value=12345):
            self.assertAlmostEqual(platform_utils._get_windows_window_scale_factor(), 1.5)


class TestGetEffectiveUiSize(unittest.TestCase):
    def tearDown(self):
        _force_linux(platform_utils)

    def test_windows_display_surface_is_normalized_by_scale_factor(self):
        _force_windows(platform_utils)
        display_surface = platform_utils.pygame.Surface((2560, 1660))

        with patch.object(platform_utils.pygame.display, 'get_surface', return_value=display_surface, create=True), \
             patch.object(platform_utils.pygame.display, 'get_window_size', return_value=(2560, 1660), create=True), \
             patch.object(platform_utils, '_get_windows_window_scale_factor', return_value=1.5):
            self.assertEqual(platform_utils.get_effective_ui_size(display_surface), (1707, 1107))

    def test_windows_offscreen_surface_is_not_normalized(self):
        _force_windows(platform_utils)
        display_surface = platform_utils.pygame.Surface((2560, 1660))
        offscreen_surface = platform_utils.pygame.Surface((1200, 800))

        with patch.object(platform_utils.pygame.display, 'get_surface', return_value=display_surface, create=True), \
             patch.object(platform_utils.pygame.display, 'get_window_size', return_value=(2560, 1660), create=True), \
             patch.object(platform_utils, '_get_windows_window_scale_factor', return_value=1.5):
            self.assertEqual(platform_utils.get_effective_ui_size(offscreen_surface), (1200, 800))

    def test_windows_does_not_double_normalize_when_window_size_is_already_logical(self):
        _force_windows(platform_utils)
        display_surface = platform_utils.pygame.Surface((2560, 1660))

        with patch.object(platform_utils.pygame.display, 'get_surface', return_value=display_surface, create=True), \
             patch.object(platform_utils.pygame.display, 'get_window_size', return_value=(1707, 1107), create=True), \
             patch.object(platform_utils, '_get_windows_window_scale_factor', return_value=1.5):
            self.assertEqual(platform_utils.get_effective_ui_size(display_surface), (1707, 1107))

    def test_explicit_display_surface_flag_supports_stale_display_reference(self):
        _force_windows(platform_utils)
        active_display_surface = platform_utils.pygame.Surface((2560, 1660))
        stale_display_surface = platform_utils.pygame.Surface((2560, 1660))

        with patch.object(platform_utils.pygame.display, 'get_surface', return_value=active_display_surface, create=True), \
             patch.object(platform_utils.pygame.display, 'get_window_size', return_value=(1707, 1107), create=True), \
             patch.object(platform_utils, '_get_windows_window_scale_factor', return_value=1.5):
            self.assertEqual(
                platform_utils.get_effective_ui_size(stale_display_surface, display_surface=True),
                (1707, 1107),
            )

    def test_macos_prefers_logical_window_points(self):
        _force_macos(platform_utils)
        display_surface = platform_utils.pygame.Surface((2880, 1800))

        with patch.object(platform_utils.pygame.display, 'get_surface', return_value=display_surface, create=True), \
             patch.object(platform_utils.pygame.display, 'get_window_size', return_value=(1440, 900), create=True):
            self.assertEqual(platform_utils.get_effective_ui_size(display_surface), (1440, 900))


if __name__ == '__main__':
    unittest.main()