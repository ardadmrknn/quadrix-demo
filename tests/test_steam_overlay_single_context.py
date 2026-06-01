"""Steam overlay tek-context (single-context) düzeltmesi için birim testler.

Kapsanan gereksinimler:
- Gereksinim 1: Windows'ta GL talebi varken create_display ilk set_mode'a OPENGL ekler.
- Gereksinim 5.1/5.2: OPENGL set_mode pygame.error verirse software pencereye düşülür.
- Gereksinim 7: GL talebi yokken (off) OPENGL eklenmez.
"""

import os
import sys
import types
import unittest
from unittest.mock import MagicMock


# ── pygame stub (OPENGL bayrağı dahil) ───────────────────────────────────────
def _make_pygame_stub():
    pg = types.ModuleType("pygame")
    pg.NOFRAME = 32
    pg.DOUBLEBUF = 1
    pg.HWSURFACE = 2
    pg.FULLSCREEN = 4
    pg.RESIZABLE = 16
    pg.OPENGL = 2048
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
        @staticmethod
        def Info():
            return _Info()

        @staticmethod
        def set_mode(size, flags=0):
            surf = MagicMock()
            surf.get_size.return_value = size
            surf.get_flags.return_value = flags
            return surf

    pg.display = _display
    pg.error = type("error", (Exception,), {})

    _font = types.ModuleType("pygame.font")
    _font.Font = MagicMock()
    _font.SysFont = MagicMock()
    _font.get_init = lambda: True
    _font.init = lambda: None
    _font.match_font = lambda name, bold=False, italic=False: None
    _font.get_fonts = lambda: []
    pg.font = _font

    _mixer = types.ModuleType("pygame.mixer")
    _mixer.init = lambda *a, **k: None
    _mixer.pre_init = lambda *a, **k: None
    _mixer.get_init = lambda: (44100, -16, 2)
    _mixer.Sound = MagicMock
    pg.mixer = _mixer

    return pg


_pg_stub = _make_pygame_stub()
if "pygame" not in sys.modules:
    sys.modules["pygame"] = _pg_stub
else:
    _existing_pg = sys.modules["pygame"]
    for _attr in ("FULLSCREEN", "NOFRAME", "DOUBLEBUF", "HWSURFACE", "RESIZABLE",
                  "OPENGL", "VIDEORESIZE", "Surface", "display", "error"):
        if not hasattr(_existing_pg, _attr):
            setattr(_existing_pg, _attr, getattr(_pg_stub, _attr))
    # OPENGL bayrağının testte mevcut olduğundan emin ol.
    if not hasattr(_existing_pg, "OPENGL"):
        _existing_pg.OPENGL = 2048

import pygame  # noqa: E402

# ── modülü temiz import et ───────────────────────────────────────────────────
if "src.platform_utils" in sys.modules:
    del sys.modules["src.platform_utils"]
if "platform_utils" in sys.modules:
    del sys.modules["platform_utils"]

_src_dir = os.path.join(os.path.dirname(__file__), "..", "src")
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

import platform_utils  # noqa: E402


def _force_windows(module):
    module.IS_WINDOWS = True
    module.IS_MACOS = False
    module.IS_LINUX = False


def _force_non_windows(module):
    module.IS_WINDOWS = False
    module.IS_MACOS = False
    module.IS_LINUX = True


class TestSingleContextWindowRequest(unittest.TestCase):
    """create_display Windows borderless yolunda OPENGL bayrağı davranışı."""

    def setUp(self):
        _force_windows(platform_utils)
        platform_utils.set_gl_window_request(False)
        self._captured_flags = []
        self._orig_set_mode = platform_utils.pygame.display.set_mode

        def fake_set_mode(size, flags=0):
            self._captured_flags.append(flags)
            surf = MagicMock()
            surf.get_size.return_value = size
            surf.get_flags.return_value = flags
            return surf

        platform_utils.pygame.display.set_mode = fake_set_mode
        os.environ.pop("SDL_VIDEO_CENTERED", None)
        os.environ.pop("SDL_VIDEO_WINDOW_POS", None)

    def tearDown(self):
        platform_utils.pygame.display.set_mode = self._orig_set_mode
        platform_utils.set_gl_window_request(False)
        _force_non_windows(platform_utils)
        os.environ.pop("SDL_VIDEO_CENTERED", None)
        os.environ.pop("SDL_VIDEO_WINDOW_POS", None)

    def test_opengl_flag_added_when_requested(self):
        """GL talebi açıkken ilk set_mode OPENGL bayrağı içermeli (Gereksinim 1.1)."""
        platform_utils.set_gl_window_request(True)
        platform_utils.create_display(1920, 1080, fullscreen=True, borderless=True)
        self.assertEqual(len(self._captured_flags), 1, "Tek set_mode çağrısı beklenir")
        self.assertTrue(
            self._captured_flags[0] & pygame.OPENGL,
            "GL talebi varken ilk set_mode OPENGL içermeli",
        )

    def test_hwsurface_not_present_with_opengl(self):
        """OPENGL eklenirken HWSURFACE bulunmamalı (Gereksinim 1.3)."""
        platform_utils.set_gl_window_request(True)
        platform_utils.create_display(1920, 1080, fullscreen=True, borderless=True)
        self.assertFalse(
            self._captured_flags[0] & pygame.HWSURFACE,
            "OPENGL ile birlikte HWSURFACE olmamalı",
        )

    def test_opengl_flag_absent_when_not_requested(self):
        """GL talebi yokken OPENGL eklenmemeli (Gereksinim 7.1)."""
        platform_utils.set_gl_window_request(False)
        platform_utils.create_display(1920, 1080, fullscreen=True, borderless=True)
        self.assertEqual(len(self._captured_flags), 1)
        self.assertFalse(
            self._captured_flags[0] & pygame.OPENGL,
            "GL talebi yokken OPENGL eklenmemeli",
        )

    def test_opengl_not_requested_on_non_windows(self):
        """Windows dışı platformda OPENGL talebi yok sayılmalı (Gereksinim 6)."""
        _force_non_windows(platform_utils)
        platform_utils.set_gl_window_request(True)
        platform_utils.create_display(1920, 1080, fullscreen=True, borderless=True)
        for flags in self._captured_flags:
            self.assertFalse(
                flags & pygame.OPENGL,
                "Windows dışında OPENGL eklenmemeli",
            )


class TestSingleContextFallback(unittest.TestCase):
    """OPENGL set_mode başarısız olursa software pencereye güvenli geri dönüş."""

    def setUp(self):
        _force_windows(platform_utils)
        platform_utils.set_gl_window_request(True)
        self._call_flags = []
        self._orig_set_mode = platform_utils.pygame.display.set_mode

        def fake_set_mode(size, flags=0):
            self._call_flags.append(flags)
            # İlk çağrı OPENGL içeriyorsa pygame.error fırlat (GL kurulamadı).
            if flags & pygame.OPENGL:
                raise pygame.error("OpenGL context oluşturulamadı")
            surf = MagicMock()
            surf.get_size.return_value = size
            surf.get_flags.return_value = flags
            return surf

        platform_utils.pygame.display.set_mode = fake_set_mode
        os.environ.pop("SDL_VIDEO_CENTERED", None)
        os.environ.pop("SDL_VIDEO_WINDOW_POS", None)

    def tearDown(self):
        platform_utils.pygame.display.set_mode = self._orig_set_mode
        platform_utils.set_gl_window_request(False)
        _force_non_windows(platform_utils)
        os.environ.pop("SDL_VIDEO_CENTERED", None)
        os.environ.pop("SDL_VIDEO_WINDOW_POS", None)

    def test_falls_back_to_software_on_gl_error(self):
        """OPENGL hatasında software pencere kurulmalı; sonuç None olmamalı (Gereksinim 5.1)."""
        surface = platform_utils.create_display(1920, 1080, fullscreen=True, borderless=True)
        self.assertIsNotNone(surface)
        # İlk çağrı OPENGL (hata), ikinci çağrı OPENGL'siz software olmalı.
        self.assertGreaterEqual(len(self._call_flags), 2)
        self.assertTrue(self._call_flags[0] & pygame.OPENGL)
        self.assertFalse(
            self._call_flags[1] & pygame.OPENGL,
            "Fallback çağrısı OPENGL içermemeli",
        )


if __name__ == "__main__":
    unittest.main()
