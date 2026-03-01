"""
Windows'ta pencere ↔ tam ekran geçişi: platform_utils.create_display() düzeltmelerini test eder.

Test kapsamı:
- _get_windows_physical_resolution(): ctypes fallback davranışı
- create_display() Windows borderless: SDL_VIDEO_CENTERED geçici kaldırılıp geri ekleniyor
- create_display() Windows borderless: SDL_VIDEO_WINDOW_POS='0,0' set ediliyor
- create_display() Windows borderless: env çağrı sonrası eski haline dönüyor
- create_display() Windows borderless fallback: boyut tutarsızsa exclusive fullscreen deneniyor
"""

import os
import sys
import types
import unittest
from unittest.mock import MagicMock, patch, call


# ── pygame stub ──────────────────────────────────────────────────────────────
def _make_pygame_stub():
    pg = types.ModuleType("pygame")
    pg.NOFRAME = 32
    pg.DOUBLEBUF = 1
    pg.HWSURFACE = 2
    pg.FULLSCREEN = 4
    pg.RESIZABLE = 16
    pg.VIDEORESIZE = 256
    pg.KMOD_META = 1024
    pg.KMOD_ALT = 256
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
            return surf

    pg.display = _display
    pg.error = Exception

    # Alt modül stub'ları — diğer testlerin pygame.font / pygame.mixer
    # erişiminde AttributeError almaması için eklenir.
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
    _mixer_music = types.ModuleType("pygame.mixer.music")
    _mixer_music.get_busy = lambda: False
    _mixer_music.load = lambda p: None
    _mixer_music.play = lambda *a, **k: None
    _mixer_music.stop = lambda: None
    _mixer_music.set_volume = lambda v: None
    _mixer_music.pause = lambda: None
    _mixer_music.unpause = lambda: None
    _mixer_music.get_pos = lambda: 0
    _mixer.music = _mixer_music
    pg.mixer = _mixer

    return pg


_pg_stub = _make_pygame_stub()
if "pygame" not in sys.modules:
    sys.modules["pygame"] = _pg_stub
else:
    # Başka testlerin bıraktığı stub eksik attribute içerebilir; yoksaları ekle.
    _existing_pg = sys.modules["pygame"]
    for _attr in ("FULLSCREEN", "NOFRAME", "DOUBLEBUF", "HWSURFACE", "RESIZABLE",
                  "VIDEORESIZE", "KMOD_META", "KMOD_ALT", "K_F12", "K_RETURN",
                  "K_KP_ENTER", "KMOD_CTRL", "Surface", "display", "error",
                  "font", "mixer"):
        if not hasattr(_existing_pg, _attr):
            setattr(_existing_pg, _attr, getattr(_pg_stub, _attr))

# Alt modüller de sys.modules'da kayıtlı olmalı
_pg = sys.modules["pygame"]
if "pygame.font" not in sys.modules:
    sys.modules["pygame.font"] = getattr(_pg, "font", _pg_stub.font)
if "pygame.mixer" not in sys.modules:
    sys.modules["pygame.mixer"] = getattr(_pg, "mixer", _pg_stub.mixer)
if "pygame.mixer.music" not in sys.modules:
    _mx = sys.modules.get("pygame.mixer") or getattr(_pg, "mixer", None)
    sys.modules["pygame.mixer.music"] = getattr(_mx, "music", None)
import pygame  # noqa: E402  (pytest discovers after stub is set)


# ── modülü yeniden yükle (stub aktif olsun) ──────────────────────────────────
import importlib
if "src.platform_utils" in sys.modules:
    del sys.modules["src.platform_utils"]
if "platform_utils" in sys.modules:
    del sys.modules["platform_utils"]

# sys.path'e src/ ekle
_src_dir = os.path.join(os.path.dirname(__file__), "src")
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

import platform_utils  # noqa: E402


# ── yardımcı: modülü Windows context'inde zorla ──────────────────────────────
def _force_windows(module):
    module.IS_WINDOWS = True
    module.IS_MACOS = False
    module.IS_LINUX = False


def _force_non_windows(module):
    module.IS_WINDOWS = False
    module.IS_MACOS = False
    module.IS_LINUX = True


# ─────────────────────────────────────────────────────────────────────────────
class TestGetWindowsPhysicalResolution(unittest.TestCase):
    """_get_windows_physical_resolution() birim testleri."""

    def setUp(self):
        _force_windows(platform_utils)

    def tearDown(self):
        _force_non_windows(platform_utils)

    def test_returns_ctypes_values_when_available(self):
        """ctypes GetSystemMetrics başarılıysa (2560, 1440) döndürür."""
        fake_ctypes = MagicMock()
        fake_ctypes.windll.user32.GetSystemMetrics.side_effect = lambda n: 2560 if n == 0 else 1440
        with patch.dict("sys.modules", {"ctypes": fake_ctypes}):
            w, h = platform_utils._get_windows_physical_resolution()
        self.assertEqual((w, h), (2560, 1440))

    def test_falls_back_to_display_info_on_ctypes_error(self):
        """ctypes hata verirse pygame.display.Info() değerlerini kullanır."""
        fake_ctypes = MagicMock()
        fake_ctypes.windll.user32.GetSystemMetrics.side_effect = OSError("access denied")
        with patch.dict("sys.modules", {"ctypes": fake_ctypes}):
            w, h = platform_utils._get_windows_physical_resolution()
        # pygame stub'ımız 1920×1080 döndürüyor
        self.assertEqual((w, h), (1920, 1080))

    def test_falls_back_when_ctypes_returns_zero(self):
        """GetSystemMetrics 0 dönerse pygame.display.Info() kullanılır."""
        fake_ctypes = MagicMock()
        fake_ctypes.windll.user32.GetSystemMetrics.return_value = 0
        with patch.dict("sys.modules", {"ctypes": fake_ctypes}):
            w, h = platform_utils._get_windows_physical_resolution()
        self.assertEqual((w, h), (1920, 1080))


# ─────────────────────────────────────────────────────────────────────────────
class TestCreateDisplayWindowsBorderlessCenteredEnv(unittest.TestCase):
    """Windows borderless fullscreen:
    SDL_VIDEO_CENTERED set_mode çağrısı sırasında yoktur.
    SDL_VIDEO_WINDOW_POS='0,0' set_mode çağrısı sırasında mevcuttur.
    """

    def setUp(self):
        _force_windows(platform_utils)
        # Çağrı anındaki env durumunu kaydetmek için set_mode mock'u
        self._env_at_call = {}

        def fake_set_mode(size, flags=0):
            self._env_at_call["centered"] = os.environ.get("SDL_VIDEO_CENTERED", "__MISSING__")
            self._env_at_call["win_pos"] = os.environ.get("SDL_VIDEO_WINDOW_POS", "__MISSING__")
            surf = MagicMock()
            surf.get_size.return_value = size  # boyut eşleşiyor
            return surf

        platform_utils.pygame.display.set_mode = fake_set_mode

    def tearDown(self):
        _force_non_windows(platform_utils)
        # Orijinal stub'ı geri yükle
        import importlib
        importlib.reload(platform_utils)
        _force_non_windows(platform_utils)

    def test_centered_absent_during_set_mode(self):
        """set_mode çağrısı sırasında SDL_VIDEO_CENTERED env'de bulunmamalı."""
        os.environ["SDL_VIDEO_CENTERED"] = "1"
        try:
            platform_utils.create_display(1920, 1080, fullscreen=True, borderless=True)
            self.assertEqual(
                self._env_at_call.get("centered"), "__MISSING__",
                "set_mode sırasında SDL_VIDEO_CENTERED aktif olmamalı",
            )
        finally:
            os.environ.pop("SDL_VIDEO_CENTERED", None)

    def test_window_pos_is_zero_during_set_mode(self):
        """set_mode çağrısı sırasında SDL_VIDEO_WINDOW_POS='0,0' olmalı."""
        os.environ.pop("SDL_VIDEO_WINDOW_POS", None)
        platform_utils.create_display(1920, 1080, fullscreen=True, borderless=True)
        self.assertEqual(
            self._env_at_call.get("win_pos"), "0,0",
            "set_mode sırasında SDL_VIDEO_WINDOW_POS='0,0' olmalı",
        )


# ─────────────────────────────────────────────────────────────────────────────
class TestCreateDisplayWindowsBorderlessEnvRestore(unittest.TestCase):
    """create_display() sonrası env eski haline dönüyor mu?"""

    def setUp(self):
        _force_windows(platform_utils)

        def fake_set_mode(size, flags=0):
            surf = MagicMock()
            surf.get_size.return_value = size
            return surf

        platform_utils.pygame.display.set_mode = fake_set_mode

    def tearDown(self):
        _force_non_windows(platform_utils)
        import importlib
        importlib.reload(platform_utils)
        _force_non_windows(platform_utils)

    def test_centered_restored_after_call(self):
        """SDL_VIDEO_CENTERED önceki değerine (1) geri yüklenmeli."""
        os.environ["SDL_VIDEO_CENTERED"] = "1"
        try:
            platform_utils.create_display(1920, 1080, fullscreen=True, borderless=True)
            self.assertEqual(
                os.environ.get("SDL_VIDEO_CENTERED"), "1",
                "SDL_VIDEO_CENTERED çağrı sonrası '1' olmalı",
            )
        finally:
            os.environ.pop("SDL_VIDEO_CENTERED", None)

    def test_centered_not_added_if_was_absent(self):
        """SDL_VIDEO_CENTERED önceden yoktu; çağrı sonrası da olmamalı."""
        os.environ.pop("SDL_VIDEO_CENTERED", None)
        try:
            platform_utils.create_display(1920, 1080, fullscreen=True, borderless=True)
            self.assertNotIn(
                "SDL_VIDEO_CENTERED", os.environ,
                "SDL_VIDEO_CENTERED önceden yoktu; çağrı sonrası eklenmemeli",
            )
        finally:
            os.environ.pop("SDL_VIDEO_CENTERED", None)

    def test_window_pos_restored_after_call(self):
        """SDL_VIDEO_WINDOW_POS önceki değerine ('center') geri yüklenmeli."""
        os.environ["SDL_VIDEO_WINDOW_POS"] = "center"
        try:
            platform_utils.create_display(1920, 1080, fullscreen=True, borderless=True)
            self.assertEqual(
                os.environ.get("SDL_VIDEO_WINDOW_POS"), "center",
                "SDL_VIDEO_WINDOW_POS 'center' değerine geri dönmeli",
            )
        finally:
            os.environ.pop("SDL_VIDEO_WINDOW_POS", None)

    def test_window_pos_removed_if_was_absent(self):
        """SDL_VIDEO_WINDOW_POS önceden yoktu; çağrı sonrası temizlenmeli."""
        os.environ.pop("SDL_VIDEO_WINDOW_POS", None)
        try:
            platform_utils.create_display(1920, 1080, fullscreen=True, borderless=True)
            self.assertNotIn(
                "SDL_VIDEO_WINDOW_POS", os.environ,
                "SDL_VIDEO_WINDOW_POS önceden yoktu; çağrı sonrası kalmamalı",
            )
        finally:
            os.environ.pop("SDL_VIDEO_WINDOW_POS", None)


# ─────────────────────────────────────────────────────────────────────────────
class TestCreateDisplayWindowsBorderlessFallback(unittest.TestCase):
    """Borderless set_mode hedef boyuttan küçük Surface döndürürse
    exclusive fullscreen (FULLSCREEN flag) ile ikinci deneme yapılır.
    """

    def setUp(self):
        _force_windows(platform_utils)
        self._call_flags = []

        # Diğer testlerden kalan stub'larda bu sabitler eksik olabilir; güvence al.
        for _attr, _val in (("FULLSCREEN", 4), ("NOFRAME", 32), ("DOUBLEBUF", 1),
                             ("HWSURFACE", 2), ("RESIZABLE", 16), ("error", Exception)):
            if not hasattr(platform_utils.pygame, _attr):
                setattr(platform_utils.pygame, _attr, _val)

        def fake_set_mode(size, flags=0):
            self._call_flags.append(flags)
            surf = MagicMock()
            # İlk çağrıda yanlış boyut dön (fallback'i tetikle)
            if len(self._call_flags) == 1:
                surf.get_size.return_value = (800, 600)  # hedeften çok küçük
            else:
                surf.get_size.return_value = size
            return surf

        platform_utils.pygame.display.set_mode = fake_set_mode

    def tearDown(self):
        _force_non_windows(platform_utils)
        import importlib
        importlib.reload(platform_utils)
        _force_non_windows(platform_utils)

    def test_exclusive_fallback_triggered_on_size_mismatch(self):
        """Boyut uyumsuzluğunda ikinci set_mode FULLSCREEN flag ile çağrılmalı."""
        os.environ.pop("SDL_VIDEO_CENTERED", None)
        os.environ.pop("SDL_VIDEO_WINDOW_POS", None)
        try:
            platform_utils.create_display(1920, 1080, fullscreen=True, borderless=True)
            self.assertEqual(len(self._call_flags), 2, "İki set_mode çağrısı bekleniyor")
            # platform_utils.pygame kullan — test dizisi boyunca tutarlı referans garantisi
            _fullscreen_flag = getattr(platform_utils.pygame, "FULLSCREEN", 4)
            self.assertTrue(
                self._call_flags[1] & _fullscreen_flag,
                "İkinci çağrı FULLSCREEN flag içermeli",
            )
        finally:
            os.environ.pop("SDL_VIDEO_CENTERED", None)
            os.environ.pop("SDL_VIDEO_WINDOW_POS", None)

    def test_no_fallback_when_size_matches(self):
        """Boyut doğruysa tek set_mode çağrısı yeterli."""
        # setUp'ta ilk çağrı küçük döndürüyor; bu testte doğruyu döndüren stub kullan
        call_count = []

        def fake_set_mode_ok(size, flags=0):
            call_count.append(1)
            surf = MagicMock()
            surf.get_size.return_value = size  # tam olarak istenen boyut
            return surf

        platform_utils.pygame.display.set_mode = fake_set_mode_ok
        os.environ.pop("SDL_VIDEO_CENTERED", None)
        os.environ.pop("SDL_VIDEO_WINDOW_POS", None)
        try:
            platform_utils.create_display(1920, 1080, fullscreen=True, borderless=True)
            self.assertEqual(len(call_count), 1, "Boyut eşleşince tek çağrı yetmeli")
        finally:
            os.environ.pop("SDL_VIDEO_CENTERED", None)
            os.environ.pop("SDL_VIDEO_WINDOW_POS", None)


if __name__ == "__main__":
    unittest.main()
