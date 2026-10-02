# -*- coding: utf-8 -*-
"""FAZ A1 sözleşme testleri: RenderGeometry + geometri kuşağı + K1-A (S11).

Gorsel_Olcek_Sorunlari_Cozum_Plani.md FAZ A1 madde 7 (kırmızı test ayağı):
  1. K1-A — Windows pencereli DPI bölmesi kalkar: eff = çizim surface'ı.
     S11 senaryosu (%125): oyun alanı tabanı ile overlay projeksiyon tabanı
     aynı uzayda birleşir → get_projected_effective_scale == get_effective_scale.
     (K1-A öncesi bu test KIRMIZI: 0.8x taban vs 1.0x projeksiyon.)
  2. Geometri kuşağı (generation) monotonik artar; backend bildirimleri
     durumu günceller.
  3. RenderGeometry alanları salt-okunur tek snapshot sözleşmesi.

Not: gerçek pygame + SDL dummy driver kullanır. Öncesinde koşan
test_platform_effective_ui_size.py sys.modules'e pygame stub'u enjekte
edebildiğinden bu dosya kendi başında modül kirliliğini temizler.
"""

from __future__ import annotations

import io
import os
import pathlib
import sys
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch


ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / 'src'

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# Modül kirliliği temizliği: stub pygame / önceden import edilmiş modüller
# kaldırılır; gerçek pygame ile taze import edilir (yukarıdaki docstring).
# DİKKAT (K4/A3 kalıbı): pygame KÖKÜNÜ tek başına sökmek aile-yarım-kalma
# mayınıdır — kök sökülür, pygame.* alt modülleri sys.modules'te asılı
# kalır, sonraki `import pygame` "partially initialized module" hatası
# verir VEYA aileyi bozuk bırakır; zincirde bu dosyadan sonra kurulan
# canlı testler pygame.font gibi alt modülleri kaybeder. Pygame AİLESİNİN
# TAMAMI (kök + pygame.*) sökülür: yeniden import sıfırdan, tutarlı koşar.
for _name in ('platform_utils', 'ui_scaling', 'sdl2_overlay', 'gl_compat'):
    sys.modules.pop(_name, None)
    sys.modules.pop('src.' + _name, None)
for _pg_key in [k for k in list(sys.modules) if k == 'pygame' or k.startswith('pygame.')]:
    sys.modules.pop(_pg_key, None)

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

import pygame  # noqa: E402

import platform_utils  # noqa: E402
import ui_scaling  # noqa: E402


def _reset_canvas_state() -> None:
    """Her test temiz INACTIVE durumundan başlasın (toleranslı zorla-alma)."""
    platform_utils._canvas_state = platform_utils.CANVAS_STATE_INACTIVE
    platform_utils._canvas_state_backend = None


class _DisplayTestCase(unittest.TestCase):
    """Ortak dummy-display kurulumu: set_mode(1920x1080) + durum sıfırlama."""

    def setUp(self):
        _reset_canvas_state()
        if pygame.display.get_init():
            pygame.display.quit()
        pygame.display.init()
        pygame.display.set_mode((1920, 1080))
        try:
            pygame.event.clear()
        except Exception:
            pass

    def tearDown(self):
        try:
            platform_utils._teardown_virtual_canvas()
        except Exception:
            pass
        _reset_canvas_state()
        try:
            pygame.event.clear()
        except Exception:
            pass


class TestK1ADpiContract(_DisplayTestCase):
    """S11: %125 DPI senaryosunda iki ölçek katmanı aynı tabanda birleşir."""

    def test_windowed_dpi_scale_does_not_shrink_eff(self):
        """K1-A: eff = çizim surface'ı; DPI bölmüyor (eski: 1536x864)."""
        display_surface = pygame.display.get_surface()
        self.assertEqual(display_surface.get_size(), (1920, 1080))

        with patch.object(platform_utils, 'IS_WINDOWS', True), \
             patch.object(platform_utils, '_get_windows_window_scale_factor', return_value=1.25):
            self.assertEqual(
                platform_utils.get_effective_ui_size(display_surface),
                (1920, 1080),
            )

    def test_layer_parity_projected_equals_effective(self):
        """FAZ A1 madde 7 kırmızı ayağı: S11 ayrışması kapanır.

        Oyun alanı ölçeği get_effective_scale (eff-tabanlı) ile, game-over
        katmanı get_projected_effective_scale (eff × pixel_ratio) ile ölçer.
        K1-A öncesi eff = surface÷1.25 olduğundan ratio=1.25 → 0.8x/1.0x
        ayrışma; K1-A sonrası eff = surface → ratio=1.0 → iki taban eşit.
        """
        display_surface = pygame.display.get_surface()
        ui_scaling._PROJECTED_SCALE_CACHE.clear()

        with patch.object(platform_utils, 'IS_WINDOWS', True), \
             patch.object(platform_utils, '_get_windows_window_scale_factor', return_value=1.25):
            effective = ui_scaling.get_effective_scale(
                display_surface, min_scale=0.53, max_scale=2.37,
            )
            projected = ui_scaling.get_projected_effective_scale(
                display_surface, min_scale=0.53, max_scale=2.37,
            )

        self.assertAlmostEqual(effective, projected, places=6)

    def test_geometry_reports_dpi_without_projecting(self):
        """dpi_scale bilgi alanıdır; sunum ölçeği (scale) 1.0 kalır (plain)."""
        display_surface = pygame.display.get_surface()
        with patch.object(platform_utils, 'IS_WINDOWS', True), \
             patch.object(platform_utils, '_get_windows_window_scale_factor', return_value=1.25):
            geometry = platform_utils.get_render_geometry(display_surface)

        self.assertAlmostEqual(geometry.dpi_scale, 1.25, places=6)
        self.assertAlmostEqual(geometry.scale, 1.0, places=6)
        self.assertEqual(geometry.canvas_size, (1920, 1080))
        self.assertEqual(geometry.window_size, (1920, 1080))
        self.assertEqual(geometry.presentation_rect, (0, 0, 1920, 1080))


class TestGeometryGeneration(_DisplayTestCase):
    """Geometri kuşağı: backend bildirimleri sayaç artırır, durumu günceller."""

    def test_backend_notify_advances_generation_and_state(self):
        gen_before = platform_utils.get_geometry_generation()
        self.assertEqual(platform_utils.get_canvas_state(), platform_utils.CANVAS_STATE_INACTIVE)

        platform_utils._notify_canvas_backend_active('sdl2_overlay')
        self.assertEqual(platform_utils.get_canvas_state(), platform_utils.CANVAS_STATE_ACTIVE)
        self.assertEqual(platform_utils.get_canvas_state_backend(), 'sdl2_overlay')
        gen_active = platform_utils.get_geometry_generation()
        self.assertGreater(gen_active, gen_before)

        platform_utils._notify_canvas_backend_inactive('sdl2_overlay')
        self.assertEqual(platform_utils.get_canvas_state(), platform_utils.CANVAS_STATE_INACTIVE)
        self.assertIsNone(platform_utils.get_canvas_state_backend())
        self.assertGreater(platform_utils.get_geometry_generation(), gen_active)

    def test_illegal_transition_is_forced_and_logged(self):
        """Toleranslı zorla-alma: oyun kilitlenmez, sapma teşhise yazılır."""
        self.assertEqual(platform_utils.get_canvas_state(), platform_utils.CANVAS_STATE_INACTIVE)
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            platform_utils._set_canvas_state(platform_utils.CANVAS_STATE_TEARING_DOWN)
        self.assertEqual(platform_utils.get_canvas_state(), platform_utils.CANVAS_STATE_TEARING_DOWN)
        self.assertIn('Beklenmedik geçiş', buffer.getvalue())

    def test_idempotent_state_call_is_silent(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            platform_utils._set_canvas_state(platform_utils.CANVAS_STATE_INACTIVE)
        self.assertEqual(platform_utils.get_canvas_state(), platform_utils.CANVAS_STATE_INACTIVE)
        self.assertEqual(buffer.getvalue(), '')


class TestCanvasSafeRect(unittest.TestCase):
    """_canvas_safe_rect: %2.5 marj + en az 24px güvenli alan güvencesi."""

    def test_reference_canvas_margin(self):
        # 1920x1080 → marj x=round(48.0)=48, y=round(27.0)=27
        self.assertEqual(
            platform_utils._canvas_safe_rect((1920, 1080)),
            (48, 27, 1824, 1026),
        )

    def test_small_canvas_keeps_24px_minimum(self):
        # 100x100 → marj round(2.5)=2 (çeyrek-yuvarlama bağımsızlığa dikkat:
        # Python banker's rounding round(2.5)=2)
        x0, y0, w, h = platform_utils._canvas_safe_rect((100, 100))
        self.assertGreaterEqual(w, 24)
        self.assertGreaterEqual(h, 24)
        # 40x40 → marj min(1, (40-24)//2=8) = 1 → 38x38 güvenli alan
        self.assertEqual(platform_utils._canvas_safe_rect((40, 40)), (1, 1, 38, 38))
        # 24px ve altı tuvalde marj 0 → güvenli alan tüm tuval
        self.assertEqual(platform_utils._canvas_safe_rect((24, 24)), (0, 0, 24, 24))

    def test_invalid_size_returns_zero(self):
        self.assertEqual(platform_utils._canvas_safe_rect((0, 0)), (0, 0, 0, 0))


class TestRenderGeometry(_DisplayTestCase):
    """RenderGeometry: tek snapshot sözleşmesi (alanlar, immutability, preset)."""

    def _geometry(self):
        return platform_utils.get_render_geometry(pygame.display.get_surface())

    def test_plain_backend_snapshot(self):
        geometry = self._geometry()
        self.assertEqual(geometry.backend, 'plain')
        self.assertEqual(geometry.canvas_size, (1920, 1080))
        self.assertEqual(geometry.window_size, (1920, 1080))
        self.assertEqual(geometry.logical_window_size, (1920, 1080))
        self.assertEqual(geometry.presentation_rect, (0, 0, 1920, 1080))
        self.assertEqual(geometry.offset, (0, 0))
        self.assertAlmostEqual(geometry.scale, 1.0, places=6)
        self.assertEqual(geometry.generation, platform_utils.get_geometry_generation())
        # safe_rect = %2.5 marjlı alan
        self.assertEqual(geometry.safe_rect, platform_utils._canvas_safe_rect((1920, 1080)))

    def test_namedtuple_is_immutable(self):
        geometry = self._geometry()
        with self.assertRaises(AttributeError):
            geometry.backend = 'sdl2_overlay'

    def test_fields_contract(self):
        expected = (
            'canvas_size', 'window_size', 'logical_window_size', 'presentation_rect',
            'safe_rect', 'scale', 'offset', 'backend', 'ui_preset', 'dpi_scale',
            'generation',
        )
        self.assertEqual(platform_utils.RenderGeometry._fields, expected)

    def test_ui_preset_tracks_ui_scaling(self):
        try:
            ui_scaling.set_ui_scale_preset('large')
            self.assertEqual(self._geometry().ui_preset, 'large')
        finally:
            ui_scaling.set_ui_scale_preset('normal')
        self.assertEqual(self._geometry().ui_preset, 'normal')

    def test_offscreen_screen_uses_own_size(self):
        offscreen = pygame.Surface((1280, 720))
        geometry = platform_utils.get_render_geometry(offscreen)
        self.assertEqual(geometry.backend, 'plain')
        self.assertEqual(geometry.canvas_size, (1280, 720))


class TestSoftwareCanvasBackend(_DisplayTestCase):
    """software_canvas rejimi: setup→ACTIVE, geometri alanları, teardown→INACTIVE."""

    def test_software_canvas_active_geometry(self):
        real = pygame.display.get_surface()
        gen_before = platform_utils.get_geometry_generation()

        canvas = platform_utils.setup_virtual_canvas(real, multiplier=2.0)

        self.assertEqual(platform_utils.get_canvas_state(), platform_utils.CANVAS_STATE_ACTIVE)
        self.assertEqual(platform_utils.get_canvas_state_backend(), 'software_canvas')
        self.assertGreater(platform_utils.get_geometry_generation(), gen_before)

        # 1920x1080 @ x2.0 → v_h=1080/2=540 → clamp 720; v_w=round(720*16/9)=1280
        self.assertEqual(canvas.get_size(), (1280, 720))

        geometry = platform_utils.get_render_geometry(None)
        self.assertEqual(geometry.backend, 'software_canvas')
        self.assertEqual(geometry.canvas_size, (1280, 720))
        self.assertEqual(geometry.window_size, (1920, 1080))
        # 16:9 canvas 16:9 pencere: letterbox tam kaplama, offset (0, 0)
        self.assertEqual(geometry.presentation_rect, (0, 0, 1920, 1080))
        self.assertAlmostEqual(geometry.scale, 1.5, places=6)
        self.assertEqual(geometry.logical_window_size, (1280, 720))

    def test_teardown_restores_plain_and_advances_generation(self):
        real = pygame.display.get_surface()
        platform_utils.setup_virtual_canvas(real, multiplier=2.0)
        gen_active = platform_utils.get_geometry_generation()

        platform_utils._teardown_virtual_canvas()

        self.assertEqual(platform_utils.get_canvas_state(), platform_utils.CANVAS_STATE_INACTIVE)
        self.assertIsNone(platform_utils.get_canvas_state_backend())
        self.assertGreater(platform_utils.get_geometry_generation(), gen_active)

        geometry = platform_utils.get_render_geometry(real)
        self.assertEqual(geometry.backend, 'plain')
        self.assertEqual(geometry.canvas_size, (1920, 1080))

    def test_pass_through_marks_fallback(self):
        """canvas==real (1080p normal preset): FALLBACK + kuşak artışı."""
        pygame.display.set_mode((1280, 720))
        real = pygame.display.get_surface()
        gen_before = platform_utils.get_geometry_generation()

        result = platform_utils.setup_virtual_canvas(real, multiplier=1.0)

        self.assertIs(result, real)
        self.assertEqual(platform_utils.get_canvas_state(), platform_utils.CANVAS_STATE_FALLBACK)
        self.assertEqual(platform_utils.get_canvas_state_backend(), 'software_canvas')
        self.assertGreater(platform_utils.get_geometry_generation(), gen_before)
        # FALLBACK: geometri plain'dir (canvas yok, gerçek yüzeye çizim)
        self.assertEqual(platform_utils.get_render_geometry(real).backend, 'plain')


if __name__ == '__main__':
    unittest.main()
