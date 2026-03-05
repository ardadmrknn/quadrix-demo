"""
Phase 5: Clipboard Subprocess Timeout Temizligi

Windows, macOS ve Linux kollarinda TimeoutExpired sonrasi:
 - process.kill() veya process.terminate() cagrildigini
 - False donduruldugunu
 - Basarili durumda True donduruldugunu
dogrular.
"""
from __future__ import annotations

import importlib
import subprocess
import sys
import os
import types
import unittest
from unittest.mock import MagicMock, patch

# --- sys.path duzeltmesi ---
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'src')
for _p in (ROOT, SRC):
    if _p not in sys.path:
        sys.path.insert(0, _p)

_STUB_MODULES = [
    'pygame', 'board', 'pieces', 'sound', 'background',
    'background_effects', 'themes', 'retro_style', 'ui_theme',
    'localization', 'platform_utils', 'gamepad_manager',
    'achievements', 'score_manager', 'user_manager', 'steam_integration',
]


def _make_stubs() -> dict:
    stubs: dict = {}
    for name in _STUB_MODULES:
        stubs[name] = MagicMock()

    stubs['board'].Board = MagicMock()
    stubs['pieces'].Piece = MagicMock()
    stubs['pieces'].SHAPES = []
    stubs['sound'].SoundManager = MagicMock()
    stubs['background'].BackgroundManager = MagicMock()
    stubs['background_effects'].get_shared_falling_blocks_layer = MagicMock()
    stubs['themes'].ThemeManager = MagicMock()
    stubs['retro_style'].retro_style = MagicMock()
    stubs['retro_style'].retro_style.get_font = MagicMock()
    stubs['retro_style'].retro_style.draw_glass_panel = MagicMock()
    stubs['retro_style'].retro_style.get_fitting_font = MagicMock()
    stubs['ui_theme'].UIFonts = MagicMock()
    stubs['ui_theme'].UIColors = MagicMock()
    stubs['ui_theme'].UIStyle = MagicMock()
    stubs['localization'].t = lambda key, default='': default
    stubs['steam_integration'].pause_pump = MagicMock()
    stubs['steam_integration'].resume_pump = MagicMock()

    _old = sys.modules.pop('constants', None)
    try:
        import constants as _rc
        stubs['constants'] = _rc
    except ImportError:
        _c = types.ModuleType('constants')
        _c.BOARD_WIDTH = 10
        _c.BOARD_HEIGHT = 20
        _c.BLACK = (0, 0, 0)
        _c.COLORS = {}
        _c.INITIAL_FALL_SPEED = 500
        _c.FAST_FALL_SPEED = 50
        _c.SPEED_INCREASE_PER_LEVEL = 30
        _c.DEFAULT_LOCK_DELAY = 500
        _c.DAS_DELAY = 170
        _c.DAS_REPEAT = 50
        stubs['constants'] = _c
    finally:
        if _old is not None:
            sys.modules['constants'] = _old
        else:
            sys.modules.pop('constants', None)

    return stubs


def _get_game_class():
    stubs = _make_stubs()
    for name, stub in stubs.items():
        sys.modules[name] = stub
    sys.modules.pop('online_pvp_game', None)
    mod = importlib.import_module('online_pvp_game')
    return mod.OnlinePvPGame


def _make_bare_instance():
    cls = _get_game_class()
    return object.__new__(cls)


class TestWindowsClipboardTimeoutKillsProcess(unittest.TestCase):

    def test_windows_clipboard_timeout_kills_process(self):
        obj = _make_bare_instance()
        mock_process = MagicMock()
        mock_process.wait.side_effect = subprocess.TimeoutExpired(cmd='powershell', timeout=2)
        mock_process.returncode = 0
        with patch('sys.platform', 'win32'), patch('subprocess.Popen', return_value=mock_process):
            result = obj._copy_to_clipboard("test_text")
        called = mock_process.kill.called or mock_process.terminate.called
        self.assertTrue(called, "TimeoutExpired sonrasi process.kill/terminate cagrilmadi")
        self.assertFalse(result, "TimeoutExpired sonrasi False donmeli")

    def test_windows_clipboard_success_returns_true(self):
        obj = _make_bare_instance()
        mock_process = MagicMock()
        mock_process.wait.return_value = None
        mock_process.wait.side_effect = None
        mock_process.returncode = 0
        with patch('sys.platform', 'win32'), patch('subprocess.Popen', return_value=mock_process):
            result = obj._copy_to_clipboard("hello world")
        self.assertTrue(result, "Basarili Windows kopyalamada True donmeli")


class TestMacOSClipboardTimeoutKillsProcess(unittest.TestCase):

    def test_macos_clipboard_timeout_kills_process(self):
        obj = _make_bare_instance()
        mock_process = MagicMock()
        mock_process.communicate.side_effect = subprocess.TimeoutExpired(cmd='pbcopy', timeout=2)
        mock_process.returncode = 0
        with patch('sys.platform', 'darwin'), patch('subprocess.Popen', return_value=mock_process):
            result = obj._copy_to_clipboard("test_text")
        called = mock_process.kill.called or mock_process.terminate.called
        self.assertTrue(called, "macOS TimeoutExpired sonrasi process.kill/terminate cagrilmadi")
        self.assertFalse(result, "macOS TimeoutExpired sonrasi False donmeli")

    def test_macos_clipboard_success_returns_true(self):
        obj = _make_bare_instance()
        mock_process = MagicMock()
        mock_process.communicate.return_value = (b'', b'')
        mock_process.communicate.side_effect = None
        mock_process.returncode = 0
        with patch('sys.platform', 'darwin'), patch('subprocess.Popen', return_value=mock_process):
            result = obj._copy_to_clipboard("hello")
        self.assertTrue(result, "Basarili macOS kopyalamada True donmeli")


class TestLinuxClipboardTimeoutKillsProcess(unittest.TestCase):

    def test_linux_clipboard_timeout_kills_process(self):
        obj = _make_bare_instance()
        mock_process = MagicMock()
        mock_process.communicate.side_effect = subprocess.TimeoutExpired(cmd='xclip', timeout=2)
        mock_process.returncode = 0
        with patch('sys.platform', 'linux'), patch('subprocess.Popen', return_value=mock_process):
            result = obj._copy_to_clipboard("test_text")
        called = mock_process.kill.called or mock_process.terminate.called
        self.assertTrue(called, "Linux TimeoutExpired sonrasi process.kill/terminate cagrilmadi")
        self.assertFalse(result, "Linux TimeoutExpired sonrasi False donmeli")


class TestClampIntStaticMethod(unittest.TestCase):

    def test_clamp_int_callable_without_instance(self):
        cls = _get_game_class()
        self.assertEqual(cls._clamp_int(150, 0, 100, 'test'), 100)
        self.assertEqual(cls._clamp_int(-5, 0, 100, 'test'), 0)
        self.assertEqual(cls._clamp_int(50, 0, 100, 'test'), 50)
        self.assertEqual(cls._clamp_int('abc', 0, 100, 'test'), 0)

    def test_clamp_int_via_instance(self):
        obj = _make_bare_instance()
        self.assertEqual(obj._clamp_int(200, 0, 100), 100)


if __name__ == '__main__':
    unittest.main()
