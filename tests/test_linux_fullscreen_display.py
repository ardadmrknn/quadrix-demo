# -*- coding: utf-8 -*-
"""Linux gerçek SDL fullscreen yolu: create_display Linux dalı testleri.

Plan: docs/LINUX_FULLSCREEN_CROSS_PLATFORM_UYGULAMA_PLANI_TR.md §8.1'in 12
vakası. Fake pygame nesneleri gerçek pygame sabitlerinden üretilir (plan
§8.1); platform bayrakları mevcut test konvansiyonuyla zorlanır.

v2'den demo'ya uyarlandı (2026-10-05): vaka 5 demo'nun sinyalsiz
son-çare zincirine göre yeniden yazıldı (DUZ-013 demo'da yok), vaka 11
atlandı (resolve_videoresize_display_params API'si demo'da yok) ve
work-area seam'i demo API'siyle (get_desktop_work_area) yamalandı.

Kapsam:
1.  Linux fullscreen birincil çağrısı pygame.FULLSCREEN içerir.
2.  Birincil çağrı pygame.NOFRAME içermez.
3.  Birincil çağrı (0, 0) boyutu kullanır.
4.  Native pygame.error sonrası borderless fallback çağrılır.
5.  Native + fallback + genel yol birlikte başarısızsa son-çare düz Surface (demo).
6.  SDL_VIDEO_WINDOW_POS/CENTERED çağrı sırasında temizlenir, sonra restore.
7.  Linux windowed çağrısı mevcut RESIZABLE davranışını korur.
8.  Windows monkeypatch'i mevcut NOFRAME borderless davranışını korur.
9.  macOS monkeypatch'i NOFRAME (AppKit yolu) davranışını korur.
10. get_desktop_sizes() native çözünürlük kaynağı olarak korunur.
11. (v2'ye özgü resolve_videoresize_display_params API'si demo'da yok — atlandı.)
12. Seçilen mode, surface size ve flags birbirinden AYRI raporlanır.
Ek: QUADRIX_LINUX_FULLSCREEN_MODE staging override (plan §10).
"""

import os
import sys
import unittest
from unittest.mock import MagicMock

import pytest

import pygame  # gerçek sabitler (plan §8.1: sabit sayı uydurma yok)


# sys.path'e src/ ekle ve platform_utils'u taze import et (A4 kalıbı).
_here = os.path.dirname(__file__)
_src_dir = os.path.abspath(os.path.join(_here, '..', 'src'))
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)
for _key in ('platform_utils', 'src.platform_utils'):
    sys.modules.pop(_key, None)

import platform_utils  # noqa: E402


# Taze import = doğal platform bayrakları; tearDown bunlara döner.
_REAL_PLATFORM_FLAGS = (
    platform_utils.IS_WINDOWS,
    platform_utils.IS_MACOS,
    platform_utils.IS_LINUX,
)


def _force_linux(module):
    module.IS_LINUX = True
    module.IS_MACOS = False
    module.IS_WINDOWS = False


def _force_windows(module):
    module.IS_WINDOWS = True
    module.IS_MACOS = False
    module.IS_LINUX = False


def _force_macos(module):
    module.IS_MACOS = True
    module.IS_WINDOWS = False
    module.IS_LINUX = False


def _restore_platform_flags(module):
    (module.IS_WINDOWS, module.IS_MACOS, module.IS_LINUX) = _REAL_PLATFORM_FLAGS


class _SetModeRecorder:
    """set_mode casusu: çağrıları (boyut, flags, çağrı anı env) kaydeder.

    Dönüş yüzeyi, geçirilen gerçek pygame sabitlerinden üretilir (plan §8.1).
    ``raise_for`` kümesindeki indeksler pygame.error fırlatır.
    """

    def __init__(self, raise_for=frozenset()):
        self.calls = []          # [(size, flags)]
        self.env_at_calls = []   # çağrı anındaki SDL hint görüntüsü
        self._raise_for = set(raise_for)

    def __call__(self, size, flags=0, **kwargs):
        idx = len(self.calls)
        self.calls.append((tuple(size), int(flags)))
        self.env_at_calls.append({
            'centered': os.environ.get('SDL_VIDEO_CENTERED', '__MISSING__'),
            'win_pos': os.environ.get('SDL_VIDEO_WINDOW_POS', '__MISSING__'),
        })
        if idx in self._raise_for:
            raise pygame.error(f'test failure at call {idx}')
        surf = MagicMock()
        surf.get_size.return_value = tuple(size)
        surf.get_width.return_value = int(size[0])
        surf.get_height.return_value = int(size[1])
        surf.get_flags.return_value = int(flags)
        return surf


class _LinuxFullscreenTestBase(unittest.TestCase):
    """Ortam: Linux zorlamalı + kayıtlı set_mode + sabit native çözünürlük."""

    def setUp(self):
        _force_linux(platform_utils)
        self._recorder = _SetModeRecorder()
        self._orig_set_mode = platform_utils.pygame.display.set_mode
        platform_utils.pygame.display.set_mode = self._recorder
        self._orig_native = platform_utils.get_native_resolution
        platform_utils.get_native_resolution = lambda: (1920, 1080)
        self._orig_work_area = platform_utils.get_desktop_work_area
        platform_utils.get_desktop_work_area = lambda: (4096, 4096)
        self._orig_mode = platform_utils._linux_display_selected_mode
        self._orig_req = platform_utils._linux_display_requested
        for _env in ('SDL_VIDEO_CENTERED', 'SDL_VIDEO_WINDOW_POS',
                     'QUADRIX_LINUX_FULLSCREEN_MODE'):
            os.environ.pop(_env, None)

    def tearDown(self):
        platform_utils.pygame.display.set_mode = self._orig_set_mode
        platform_utils.get_native_resolution = self._orig_native
        platform_utils.get_desktop_work_area = self._orig_work_area
        platform_utils._linux_display_selected_mode = self._orig_mode
        platform_utils._linux_display_requested = self._orig_req
        _restore_platform_flags(platform_utils)
        for _env in ('SDL_VIDEO_CENTERED', 'SDL_VIDEO_WINDOW_POS',
                     'QUADRIX_LINUX_FULLSCREEN_MODE'):
            os.environ.pop(_env, None)


# ── 1-3: birincil yol bayrakları ─────────────────────────────────────────────

class TestLinuxFullscreenPrimary(_LinuxFullscreenTestBase):

    def test_primary_call_contains_fullscreen_flag(self):
        """Vaka 1: birincil set_mode pygame.FULLSCREEN içermeli."""
        platform_utils.create_display(1920, 1080, fullscreen=True, borderless=True)
        self.assertEqual(len(self._recorder.calls), 1)
        self.assertTrue(
            self._recorder.calls[0][1] & pygame.FULLSCREEN,
            f"birincil çağrı FULLSCREEN içermeli: flags=0x{self._recorder.calls[0][1]:X}",
        )

    def test_primary_call_has_no_noframe_flag(self):
        """Vaka 2: birincil set_mode NOFRAME içermemeli."""
        platform_utils.create_display(1920, 1080, fullscreen=True, borderless=True)
        self.assertFalse(
            self._recorder.calls[0][1] & pygame.NOFRAME,
            f"birincil çağrı NOFRAME içermemeli: flags=0x{self._recorder.calls[0][1]:X}",
        )

    def test_primary_call_uses_zero_size(self):
        """Vaka 3: birincil set_mode (0, 0) boyutuyla çağrılmalı."""
        platform_utils.create_display(1920, 1080, fullscreen=True, borderless=True)
        self.assertEqual(self._recorder.calls[0][0], (0, 0))

    def test_primary_success_selects_native_mode(self):
        """Vaka 12 (kısmi): native başarıda selected_mode=linux-native."""
        platform_utils.create_display(1920, 1080, fullscreen=True, borderless=True)
        self.assertEqual(platform_utils.get_linux_display_selected_mode(), 'linux-native')

    def test_fullscreen_priority_regardless_of_borderless_param(self):
        """Plan §6.1: borderless=False bile olsa Linux fullscreen native gider."""
        platform_utils.create_display(1920, 1080, fullscreen=True, borderless=False)
        self.assertEqual(len(self._recorder.calls), 1)
        self.assertTrue(self._recorder.calls[0][1] & pygame.FULLSCREEN)
        self.assertEqual(platform_utils.get_linux_display_selected_mode(), 'linux-native')


# ── 4-5: fallback zinciri ────────────────────────────────────────────────────

class TestLinuxFullscreenFallback(_LinuxFullscreenTestBase):

    def test_native_error_triggers_borderless_fallback(self):
        """Vaka 4: native pygame.error → NOFRAME'li borderless fallback."""
        self._recorder._raise_for.add(0)
        surf = platform_utils.create_display(1920, 1080, fullscreen=True, borderless=True)
        self.assertIsNotNone(surf)
        self.assertEqual(len(self._recorder.calls), 2)
        size, flags = self._recorder.calls[1]
        self.assertEqual(size, (1920, 1080))
        self.assertTrue(flags & pygame.NOFRAME, 'fallback NOFRAME içermeli')
        self.assertFalse(flags & pygame.FULLSCREEN, 'fallback FULLSCREEN olmamalı')
        self.assertEqual(
            platform_utils.get_linux_display_selected_mode(),
            'linux-borderless-fallback',
        )

    def test_double_failure_falls_to_plain_surface(self):
        """Vaka 5 (demo uyarlaması): native + fallback + genel yol birlikte
        başarısız → demo'nun mevcut son-çare zinciri: ekran-bağlantısız düz
        pygame.Surface (v2'deki DUZ-013 sinyali demo'da YOKTUR)."""
        self._recorder._raise_for.update({0, 1, 2, 3, 4})
        surf = platform_utils.create_display(1920, 1080, fullscreen=True, borderless=True)
        self.assertIsNotNone(surf)
        self.assertIsInstance(surf, pygame.Surface)
        # Zincir dört çağrıyı da denedi: native (0) → NOFRAME fallback (1) →
        # genel-yol exclusive (2) → genel-yol windowed fallback (3); hepsi
        # pygame.error fırlattı → son-çare düz Surface döner.
        self.assertEqual(len(self._recorder.calls), 4)
        self.assertIsNone(platform_utils.get_linux_display_selected_mode())


# ── 6: env temizliği/restore ─────────────────────────────────────────────────

class TestLinuxFullscreenEnvContract(_LinuxFullscreenTestBase):

    def test_env_cleaned_during_call_and_restored_after(self):
        """Vaka 6: WINDOW_POS/CENTERED çağrı sırasında yok, sonra eski değerde."""
        os.environ['SDL_VIDEO_CENTERED'] = '1'
        os.environ['SDL_VIDEO_WINDOW_POS'] = '999,888'
        try:
            platform_utils.create_display(1920, 1080, fullscreen=True, borderless=True)
            self.assertEqual(len(self._recorder.calls), 1)
            during = self._recorder.env_at_calls[0]
            self.assertEqual(during['centered'], '__MISSING__',
                             'native çağrı sırasında CENTERED bulunmamalı')
            self.assertEqual(during['win_pos'], '__MISSING__',
                             'native çağrı sırasında WINDOW_POS bulunmamalı')
            self.assertEqual(os.environ.get('SDL_VIDEO_CENTERED'), '1',
                             'CENTERED eski değerine dönmeli')
            self.assertEqual(os.environ.get('SDL_VIDEO_WINDOW_POS'), '999,888',
                             'WINDOW_POS eski değerine dönmeli')
        finally:
            os.environ.pop('SDL_VIDEO_CENTERED', None)
            os.environ.pop('SDL_VIDEO_WINDOW_POS', None)

    def test_env_not_recreated_when_was_absent(self):
        """Hint'ler önceden yoksa çağrı sonrası da YOK olmalı (sızıntı yok)."""
        platform_utils.create_display(1920, 1080, fullscreen=True, borderless=True)
        self.assertNotIn('SDL_VIDEO_CENTERED', os.environ)
        self.assertNotIn('SDL_VIDEO_WINDOW_POS', os.environ)


# ── 7: Linux windowed dokunulmazlık ─────────────────────────────────────────

class TestLinuxWindowedUnchanged(_LinuxFullscreenTestBase):

    def test_windowed_keeps_resizable_and_size(self):
        """Vaka 7: windowed çağrı RESIZABLE bayrağını ve boyutu korur."""
        surf = platform_utils.create_display(1280, 720, fullscreen=False, resizable=True)
        self.assertIsNotNone(surf)
        self.assertEqual(len(self._recorder.calls), 1)
        size, flags = self._recorder.calls[0]
        self.assertEqual(size, (1280, 720))
        self.assertTrue(flags & pygame.RESIZABLE, 'windowed RESIZABLE içermeli')
        self.assertFalse(flags & pygame.FULLSCREEN, 'windowed FULLSCREEN olmamalı')
        self.assertEqual(platform_utils.get_linux_display_selected_mode(), 'windowed')


# ── 8-9: Windows/macOS izolasyonu ────────────────────────────────────────────

class TestPlatformIsolation(unittest.TestCase):

    def setUp(self):
        self._recorder = _SetModeRecorder()
        self._orig_set_mode = platform_utils.pygame.display.set_mode
        platform_utils.pygame.display.set_mode = self._recorder
        self._orig_native = platform_utils.get_native_resolution
        platform_utils.get_native_resolution = lambda: (1920, 1080)
        self._orig_phys = platform_utils._get_windows_physical_resolution
        platform_utils._get_windows_physical_resolution = lambda: (1920, 1080)
        self._orig_work_area = platform_utils.get_desktop_work_area
        platform_utils.get_desktop_work_area = lambda: (4096, 4096)
        self._orig_gl_req = platform_utils._GL_WINDOW_REQUEST
        platform_utils._GL_WINDOW_REQUEST = False
        for _env in ('SDL_VIDEO_CENTERED', 'SDL_VIDEO_WINDOW_POS'):
            os.environ.pop(_env, None)

    def tearDown(self):
        platform_utils.pygame.display.set_mode = self._orig_set_mode
        platform_utils.get_native_resolution = self._orig_native
        platform_utils._get_windows_physical_resolution = self._orig_phys
        platform_utils.get_desktop_work_area = self._orig_work_area
        platform_utils._GL_WINDOW_REQUEST = self._orig_gl_req
        _restore_platform_flags(platform_utils)
        for _env in ('SDL_VIDEO_CENTERED', 'SDL_VIDEO_WINDOW_POS'):
            os.environ.pop(_env, None)

    def test_windows_monkeypatch_keeps_noframe_borderless(self):
        """Vaka 8: Windows zorlaması mevcut NOFRAME borderless yolunu korur."""
        _force_windows(platform_utils)
        platform_utils.create_display(1920, 1080, fullscreen=True, borderless=True)
        self.assertEqual(len(self._recorder.calls), 1)
        size, flags = self._recorder.calls[0]
        self.assertEqual(size, (1920, 1080))
        self.assertTrue(flags & pygame.NOFRAME, 'Windows yolu NOFRAME kullanmalı')
        self.assertFalse(flags & pygame.FULLSCREEN, 'Windows borderless FULLSCREEN bayrağı taşımamalı')
        # Windows sözleşmesi: çağrı anında WINDOW_POS='0,0' pinlenir.
        self.assertEqual(self._recorder.env_at_calls[0]['win_pos'], '0,0')

    def test_macos_monkeypatch_keeps_noframe_path(self):
        """Vaka 9: macOS zorlaması AppKit/NOFRAME yolunu korur (FULLSCREEN yok)."""
        _force_macos(platform_utils)
        surf = platform_utils.create_display(1920, 1080, fullscreen=True, borderless=True)
        self.assertIsNotNone(surf)
        self.assertEqual(len(self._recorder.calls), 1)
        size, flags = self._recorder.calls[0]
        self.assertEqual(size, (1920, 1080))
        self.assertTrue(flags & pygame.NOFRAME, 'macOS yolu NOFRAME kullanmalı')
        self.assertFalse(flags & pygame.FULLSCREEN, 'macOS yolunda FULLSCREEN bayrağı olmamalı')


# ── 10: get_native_resolution kaynağı ────────────────────────────────────────

class TestNativeResolutionSource(unittest.TestCase):

    def setUp(self):
        _force_linux(platform_utils)
        self._orig_sizes = pygame.display.get_desktop_sizes
        self._orig_info = pygame.display.Info

    def tearDown(self):
        pygame.display.get_desktop_sizes = self._orig_sizes
        pygame.display.Info = self._orig_info
        _restore_platform_flags(platform_utils)

    def test_desktop_sizes_preferred_over_window_info(self):
        """Vaka 10: get_desktop_sizes, Info()'nun pencere boyutuna önceliklidir."""
        pygame.display.get_desktop_sizes = lambda: [(2560, 1440)]

        class _Info:
            current_w = 1280
            current_h = 720

        pygame.display.Info = lambda: _Info()
        self.assertEqual(platform_utils.get_native_resolution(), (2560, 1440))

    def test_info_fallback_when_desktop_sizes_fail(self):
        """desktop_sizes hata verirse Info() yolu (pencere yokken doğru) korunur."""
        def _boom():
            raise pygame.error('no desktop sizes')

        pygame.display.get_desktop_sizes = _boom

        class _Info:
            current_w = 1920
            current_h = 1080

        pygame.display.Info = lambda: _Info()
        self.assertEqual(platform_utils.get_native_resolution(), (1920, 1080))


# ── 12: telemetri alanları ayrı raporlanır ──────────────────────────────────

def test_telemetry_reports_mode_size_flags_separately(monkeypatch):
    """Vaka 12: mode/surface/window/flags/is_fullscreen AYRI alanlar halinde."""
    _force_linux(platform_utils)
    try:
        monkeypatch.setattr(platform_utils, 'get_native_resolution', lambda: (1920, 1080))
        monkeypatch.setattr(platform_utils, 'get_desktop_work_area', lambda: (4096, 4096))
        monkeypatch.setenv('XDG_SESSION_TYPE', 'x11')

        recorded_calls = []

        def _linux_set_mode(size, flags=0, **k):
            recorded_calls.append((tuple(size), int(flags)))
            # Gerçek SDL sözleşmesi: (0,0)+FULLSCREEN çağrısı native boyutlu
            # Surface döndürür — sahte de öyle davranır (probe kanıtı).
            if tuple(size) == (0, 0) and (int(flags) & pygame.FULLSCREEN):
                return _fake_surface((1920, 1080), flags)
            return _fake_surface(size, flags)

        monkeypatch.setattr(platform_utils.pygame.display, 'set_mode', _linux_set_mode)
        surf = platform_utils.create_display(1920, 1080, fullscreen=True, borderless=True)
        assert recorded_calls and (recorded_calls[0][1] & pygame.FULLSCREEN)
        assert tuple(surf.get_size()) == (1920, 1080)

        # Telemetri okuma API'leri deterministik sahte değerlerle.
        monkeypatch.setattr(pygame.display, 'get_init', lambda: True)
        monkeypatch.setattr(pygame.display, 'get_driver', lambda: 'x11')
        monkeypatch.setattr(pygame.display, 'get_desktop_sizes', lambda: [(1920, 1080)])
        monkeypatch.setattr(pygame.display, 'get_window_size', lambda: (1920, 1080))
        monkeypatch.setattr(pygame.display, 'is_fullscreen', lambda: True)
        monkeypatch.setattr(pygame.display, 'get_surface', lambda: surf)
        monkeypatch.setattr(platform_utils, '_linux_window_position', lambda: (0, 0))

        captured = []
        monkeypatch.setattr(platform_utils, '_gl_diag', lambda msg: captured.append(msg))
        platform_utils.record_platform_display_telemetry(context='startup')

        assert captured, 'telemetry satırı üretilmeli'
        line = captured[0]
        for field in (
            'session=x11',
            'desktop=1920x1080',
            'driver=x11',
            'requested_fullscreen=1',
            'requested_borderless=1',
            'selected_mode=linux-native',
            'surface=1920x1080',
            'window=1920x1080',
            'window_pos=0,0',
            'display_is_fullscreen=1',
        ):
            assert field in line, f'telemetry alanı eksik: {field} | satır: {line}'
        assert 'surface_flags=0x' in line
        # Alanlar ayrı: is_fullscreen TEK başına karar mekanizması değil.
        assert 'selected_mode=linux-native' in line
    finally:
        _restore_platform_flags(platform_utils)


def _fake_surface(size, flags):
    surf = MagicMock()
    surf.get_size.return_value = tuple(size)
    surf.get_width.return_value = int(size[0])
    surf.get_height.return_value = int(size[1])
    surf.get_flags.return_value = int(flags)
    return surf


# ── Ek: staging override (plan §10) ─────────────────────────────────────────

class TestLinuxFullscreenModeOverride(_LinuxFullscreenTestBase):

    def test_borderless_mode_skips_native_attempt(self):
        """QUADRIX_LINUX_FULLSCREEN_MODE=borderless → doğrudan NOFRAME yolu."""
        os.environ['QUADRIX_LINUX_FULLSCREEN_MODE'] = 'borderless'
        platform_utils.create_display(1920, 1080, fullscreen=True, borderless=True)
        self.assertEqual(len(self._recorder.calls), 1)
        size, flags = self._recorder.calls[0]
        self.assertEqual(size, (1920, 1080))
        self.assertTrue(flags & pygame.NOFRAME)
        self.assertFalse(flags & pygame.FULLSCREEN)
        self.assertEqual(
            platform_utils.get_linux_display_selected_mode(),
            'linux-borderless-fallback',
        )

    def test_native_mode_raises_without_fallback(self):
        """QUADRIX_LINUX_FULLSCREEN_MODE=native → fallback YOK, hata görünür."""
        os.environ['QUADRIX_LINUX_FULLSCREEN_MODE'] = 'native'
        self._recorder._raise_for.update({0})
        # Helper hata yükseltir → genel yol (aynı native çağrıyı tekrar dener)
        # devreye girer; ikinci çağrı da başarısız olursa mevcut hata zinciri.
        surf = platform_utils.create_display(1920, 1080, fullscreen=True, borderless=True)
        # Genel yol native'i yeniden denedi ve kayıtçı yalnız 0. çağrıda hata
        # veriyor → ikinci çağrı FULLSCREEN'li genel-yol surface'ı döner.
        self.assertIsNotNone(surf)
        self.assertTrue(self._recorder.calls[1][1] & pygame.FULLSCREEN)

    def test_invalid_override_value_defaults_to_auto(self):
        """Geçersiz değer 'auto' sayılır (native denenir)."""
        os.environ['QUADRIX_LINUX_FULLSCREEN_MODE'] = 'bogus-value'
        platform_utils.create_display(1920, 1080, fullscreen=True, borderless=True)
        self.assertEqual(len(self._recorder.calls), 1)
        self.assertTrue(self._recorder.calls[0][1] & pygame.FULLSCREEN)
        self.assertEqual(platform_utils.get_linux_display_selected_mode(), 'linux-native')


if __name__ == '__main__':
    unittest.main()
