# -*- coding: utf-8 -*-
"""FAZ A9 — matris property kapısı (çözünürlük × preset × backend geometri sözleşmeleri).

Gorsel_Olcek_Sorunlari_Cozum_Plani.md FAZ A9 madde 1'in matris ayağı:
  1. Presentation rect aspect'ini koruyor (letterbox/pillarbox; esnetme yok)
     ve pencere içinde ortalanmış.
  2. Canonical tuval sözleşmesi: tuval yüksekliği [720, 1080] bandında
     (4K/1440p'de 1080); 3840×2160 yalnız presentation rect'i büyütür.
  3. Safe rect tuvalin içinde.
  4. Preset → çarpan haritası dokümante değerlerle (0.94/1.0/1.25/1.5/1.75/2.0).
  5. Backend parity: sdl2_overlay._compute_present_rect ile
     platform_utils._calc_letterbox aynı (window, canvas) girdisinde
     ≤1 px anlaşır (software/SDL2 sunum matematiği tek kaynak).
  6. Girdi matrisi (A8 sözleşmesinin matris uyarlaması): round-trip ≤1 px
     + letterbox (siyah bar) DOWN reddi 21:9 ve 16:10 pencerelerde.

Ölçüm tabanlı semptom eşikleri (S4-S10) compare_ui_captures.py ile capture
matrisinde (tools/capture_ui_matrix.py) doğrulanır; bu dosya geometri
invariant'larını deterministik olarak kilitler.

Not: gerçek pygame + SDL dummy driver kullanır (test_render_geometry_contract
kalıbı): modül seviyesinde pygame ailesi + ölçekleme modülleri sökülüp
taze import edilir.
"""

from __future__ import annotations

import os
import pathlib
import sys
import unittest

ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / 'src'

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# Modül kirliliği temizliği (test_render_geometry_contract.py kalıbı):
# pygame AİLESİNİN TAMAMI (kök + pygame.*) sökülür; pygame kökünü tek başına
# sökmek aile-yarım-kalma mayınıdır ("partially initialized module").
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
import sdl2_overlay  # noqa: E402


# D.5 A9 çözünürlük matrisi (Retina@2x donanım senaryosu hariç; Steam Deck
# mantıksal 1280×800 pencere olarak temsil edilir).
_MATRIX_RESOLUTIONS = (
    (1280, 720),
    (1280, 800),    # Steam Deck mantıksal boyut (16:10)
    (1366, 768),
    (1600, 900),
    (1920, 1080),
    (2560, 1440),
    (2560, 1600),   # 16:10
    (3440, 1440),   # 21:9 ultrawide
    (3840, 2160),   # 4K
)

# D.7: preset çarpanları dokümante değerlerle birebir.
_EXPECTED_PRESET_MULTIPLIERS = {
    'compact': 0.94,
    'normal': 1.0,
    'large': 1.25,
    'huge': 1.5,
    'massive': 1.75,
    'double': 2.0,
}


def _reset_canvas_state() -> None:
    platform_utils._canvas_state = platform_utils.CANVAS_STATE_INACTIVE
    platform_utils._canvas_state_backend = None


class _DisplayTestCase(unittest.TestCase):
    """Ortak dummy-display kurulumu: her test kendi pencere boyutunu kurar."""

    def setUp(self):
        # Önce dürüst durumdan sök (ACTIVE→TEARING_DOWN→INACTIVE), sonra
        # bayrağı sıfırla: state'i önce INACTIVE'a zorlamak teardown'un
        # INACTIVE→TEARING_DOWN (yasadışı, toleranslı) geçişi basmasına
        # ve [CanvasState] teşhisinin kirlenmesine yol açar.
        try:
            platform_utils._teardown_virtual_canvas()
        except Exception:
            pass
        _reset_canvas_state()
        if pygame.display.get_init():
            pygame.display.quit()
        pygame.display.init()
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
            ui_scaling.set_ui_scale_preset('normal')
        except Exception:
            pass
        try:
            pygame.event.clear()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Bölüm A — presentation rect: aspect korunumu, ortalanma, sığma
# ---------------------------------------------------------------------------
class TestPresentationRectMatrix(_DisplayTestCase):

    def _geometry_for(self, window, multiplier):
        # Subtest-arası söküm: uygulamanın rebuild transaction'ı da (FAZ A3)
        # her yeni kurulumda eski canvas'ı söker. Sökmeden set_mode +
        # get_surface çağrılırsa, önceki subtest'in _software_get_surface
        # patch'i hâlâ kurulu olurdu ve STALE canvas döndürürdü (test
        # harness hatası — ürün yolu _real_display_surface referansını
        # kullanır, patch'li get_surface'i asla yeni pencere kurmaz).
        try:
            platform_utils._teardown_virtual_canvas()
        except Exception:
            pass
        _reset_canvas_state()
        pygame.display.set_mode(window)
        real = pygame.display.get_surface()
        canvas = platform_utils.setup_virtual_canvas(real, multiplier)
        geometry = platform_utils.get_render_geometry(None)
        return canvas, geometry

    def test_present_rect_fits_window_and_is_centered(self):
        for window in _MATRIX_RESOLUTIONS:
            for multiplier in (1.25, 2.0):
                with self.subTest(window=window, multiplier=multiplier):
                    canvas, geometry = self._geometry_for(window, multiplier)
                    win_w, win_h = window
                    pr = geometry.presentation_rect
                    px, py, pw, ph = pr
                    # Sığma: present rect pencere içinde.
                    self.assertGreaterEqual(px, 0, pr)
                    self.assertGreaterEqual(py, 0, pr)
                    self.assertLessEqual(px + pw, win_w, pr)
                    self.assertLessEqual(py + ph, win_h, pr)
                    # Ortalanma: kenar boşlukları simetrik (±1 px yuvarlama).
                    self.assertLessEqual(abs(px - (win_w - pw - px)), 1, pr)
                    self.assertLessEqual(abs(py - (win_h - ph - py)), 1, pr)

    def test_present_rect_aspect_matches_canvas(self):
        """Sunum aspect'i tuval aspect'ini korur — metin yatay ESNETİLMEZ."""
        for window in _MATRIX_RESOLUTIONS:
            for multiplier in (1.25, 2.0):
                with self.subTest(window=window, multiplier=multiplier):
                    canvas, geometry = self._geometry_for(window, multiplier)
                    cw, ch = geometry.canvas_size
                    _, _, pw, ph = geometry.presentation_rect
                    canvas_aspect = cw / float(ch)
                    present_aspect = pw / float(ph)
                    # ≤%0.5 sapma (yuvarlama + min-fit)
                    self.assertLessEqual(
                        abs(present_aspect - canvas_aspect) / canvas_aspect,
                        0.005,
                        (geometry.presentation_rect, geometry.canvas_size),
                    )

    def test_canvas_height_stays_in_canonical_band(self):
        """Tuval yüksekliği [720, 1080]: 4K/1440p'de canonical 1080."""
        for window in _MATRIX_RESOLUTIONS:
            for multiplier in (0.94, 1.0, 1.25, 1.5, 1.75, 2.0):
                with self.subTest(window=window, multiplier=multiplier):
                    canvas, geometry = self._geometry_for(window, multiplier)
                    cw, ch = geometry.canvas_size
                    self.assertGreaterEqual(ch, 720, geometry.canvas_size)
                    self.assertLessEqual(ch, 1080, geometry.canvas_size)
                    # Tuval aspect'i pencere aspect'ini izler (software yolu):
                    # esneme yok, genişlik yükseklikten türer.
                    win_w, win_h = window
                    self.assertLessEqual(
                        abs((cw / float(ch)) - (win_w / float(win_h))),
                        0.02,
                        geometry.canvas_size,
                    )

    def test_safe_rect_inside_canvas(self):
        for window in _MATRIX_RESOLUTIONS:
            with self.subTest(window=window):
                canvas, geometry = self._geometry_for(window, 1.25)
                cw, ch = geometry.canvas_size
                sx, sy, sw, sh = geometry.safe_rect
                self.assertGreaterEqual(sx, 0)
                self.assertGreaterEqual(sy, 0)
                self.assertLessEqual(sx + sw, cw)
                self.assertLessEqual(sy + sh, ch)


# ---------------------------------------------------------------------------
# Bölüm B — 4K canonical invariant (D.6: 3840×2160 yalnız sunumu büyütür)
# ---------------------------------------------------------------------------
class Test4KCanonicalInvariant(_DisplayTestCase):

    def test_4k_window_produces_canonical_canvas_and_full_present(self):
        pygame.display.set_mode((3840, 2160))
        real = pygame.display.get_surface()
        canvas = platform_utils.setup_virtual_canvas(real, 1.0)

        self.assertEqual(canvas.get_size(), (1920, 1080))
        geometry = platform_utils.get_render_geometry(None)
        self.assertEqual(geometry.canvas_size, (1920, 1080))
        # Tam kaplama: letterbox bar yok (aynı aspect).
        self.assertEqual(geometry.presentation_rect, (0, 0, 3840, 2160))
        self.assertAlmostEqual(geometry.scale, 2.0, places=6)
        self.assertEqual(geometry.window_size, (3840, 2160))

    def test_4k_with_double_preset_keeps_canvas_canonical(self):
        """Preset sunumu değil yalnız tuval ölçüsünü değiştirir; 4K'da
        double preset bile canonical 1080 yükseklik bant sınırında kalır."""
        pygame.display.set_mode((3840, 2160))
        real = pygame.display.get_surface()
        canvas = platform_utils.setup_virtual_canvas(real, 2.0)

        _, ch = canvas.get_size()
        self.assertEqual(ch, 1080)
        geometry = platform_utils.get_render_geometry(None)
        self.assertEqual(geometry.presentation_rect, (0, 0, 3840, 2160))


# ---------------------------------------------------------------------------
# Bölüm C — backend parity: iki sunum matematiği tek anlaşır
# ---------------------------------------------------------------------------
class TestBackendParityPresentRect(_DisplayTestCase):

    def test_overlay_and_software_letterbox_agree(self):
        """Aynı (window, canvas) için SDL2 overlay ve software blit rect'i
        ≤1 px farkla aynı bölgeyi üretir (D.6 backend parity)."""
        for window in _MATRIX_RESOLUTIONS:
            for canvas_size in ((1920, 1080), (1280, 720), (1536, 864)):
                with self.subTest(window=window, canvas=canvas_size):
                    overlay_rect = sdl2_overlay._compute_present_rect(
                        window[0], window[1], canvas_size[0], canvas_size[1],
                    )
                    sw = platform_utils._calc_letterbox(
                        canvas_size[0], canvas_size[1], window[0], window[1],
                    )
                    sw_rect = pygame.Rect(sw)
                    self.assertLessEqual(
                        abs(overlay_rect.x - sw_rect.x), 1,
                        (overlay_rect, sw),
                    )
                    self.assertLessEqual(
                        abs(overlay_rect.y - sw_rect.y), 1,
                        (overlay_rect, sw),
                    )
                    self.assertLessEqual(
                        abs(overlay_rect.w - sw_rect.w), 1,
                        (overlay_rect, sw),
                    )
                    self.assertLessEqual(
                        abs(overlay_rect.h - sw_rect.h), 1,
                        (overlay_rect, sw),
                    )

    def test_overlay_presentation_info_matches_software_geometry(self):
        """Sahte overlay (A8 deseni) ile software geometri aynı girdide
        aynı ofset/ölçek anlaşır (pos, inside) matrisi boyunca."""
        for window in _MATRIX_RESOLUTIONS:
            canvas_size = (1920, 1080)
            with self.subTest(window=window):
                pygame.display.set_mode(window)
                present = sdl2_overlay._compute_present_rect(
                    window[0], window[1], canvas_size[0], canvas_size[1],
                )
                # Sahte overlay durumu (test_input_roundtrip._fake_overlay
                # kalıbı; monkeypatch yerine doğrudan modül durumu).
                old_state = (
                    sdl2_overlay._active, sdl2_overlay._game_surface,
                    sdl2_overlay._width, sdl2_overlay._height,
                    sdl2_overlay._present_rect,
                )
                try:
                    sdl2_overlay._active = True
                    sdl2_overlay._game_surface = pygame.Surface(canvas_size)
                    sdl2_overlay._width = window[0]
                    sdl2_overlay._height = window[1]
                    sdl2_overlay._present_rect = pygame.Rect(present)
                    sdl2_overlay.invalidate_presentation_info_cache()
                    info = sdl2_overlay.get_presentation_info()
                finally:
                    (
                        sdl2_overlay._active, sdl2_overlay._game_surface,
                        sdl2_overlay._width, sdl2_overlay._height,
                        sdl2_overlay._present_rect,
                    ) = old_state
                    sdl2_overlay.invalidate_presentation_info_cache()

                self.assertTrue(info['active'])
                self.assertEqual((info['window_w'], info['window_h']), window)
                self.assertEqual(
                    (info['canvas_w'], info['canvas_h']), canvas_size,
                )
                self.assertEqual(
                    (info['offset_x'], info['offset_y']),
                    (present.x, present.y),
                )
                self.assertEqual((info['blit_w'], info['blit_h']), (present.w, present.h))


# ---------------------------------------------------------------------------
# Bölüm D — girdi matrisi: round-trip + black-bar reject (A8 sözleşmesi)
# ---------------------------------------------------------------------------
class TestInputMatrix(_DisplayTestCase):

    def _push_overlay_state(self, window, canvas):
        """Sahte overlay durumu kur (A8 _fake_overlay kalıbı); önceki durumu
        döndürür — test sonunda _pop_overlay_state ile geri konur."""
        present = sdl2_overlay._compute_present_rect(
            window[0], window[1], canvas[0], canvas[1],
        )
        saved = (
            sdl2_overlay._active, sdl2_overlay._game_surface,
            sdl2_overlay._width, sdl2_overlay._height,
            sdl2_overlay._present_rect,
        )
        sdl2_overlay._active = True
        sdl2_overlay._game_surface = pygame.Surface(canvas)
        sdl2_overlay._width = window[0]
        sdl2_overlay._height = window[1]
        sdl2_overlay._present_rect = pygame.Rect(present)
        sdl2_overlay.invalidate_presentation_info_cache()
        return saved

    def _pop_overlay_state(self, saved):
        sdl2_overlay._active, sdl2_overlay._game_surface, \
            sdl2_overlay._width, sdl2_overlay._height, sdl2_overlay._present_rect = saved
        sdl2_overlay.invalidate_presentation_info_cache()

    def test_round_trip_corners_within_one_pixel(self):
        for window in _MATRIX_RESOLUTIONS:
            canvas = (1920, 1080)
            with self.subTest(window=window):
                saved = self._push_overlay_state(window, canvas)
                try:
                    xs = (0, canvas[0] - 1, canvas[0] // 2)
                    ys = (0, canvas[1] - 1, canvas[1] // 2)
                    for cx in xs:
                        for cy in ys:
                            wx, wy = sdl2_overlay.canvas_to_window_pos((cx, cy))
                            mapped, inside = sdl2_overlay.window_to_canvas_pos((wx, wy))
                            self.assertTrue(inside, (cx, cy, mapped))
                            self.assertLessEqual(abs(mapped[0] - cx), 1)
                            self.assertLessEqual(abs(mapped[1] - cy), 1)
                finally:
                    self._pop_overlay_state(saved)

    def test_letterbox_down_rejected_in_ultrawide_and_16_10(self):
        """21:9 ve 16:10 pencerede bar alanı tıklaması inside=False;
        normalize Checked (software yolu) aynı sözleşmeyi verir."""
        for window, expected_bar in (
            ((3440, 1440), 'pillarbox'),   # yatay bar (sol/sağ)
            ((1280, 800), 'letterbox'),     # dikey bar (üst/alt)
        ):
            with self.subTest(window=window, bar=expected_bar):
                present = sdl2_overlay._compute_present_rect(
                    window[0], window[1], 1920, 1080,
                )
                saved = self._push_overlay_state(window, (1920, 1080))
                try:
                    if expected_bar == 'pillarbox':
                        bar_positions = ((0, 720), (present.x - 1, 720),
                                         (present.right, 720), (window[0] - 1, 720))
                    else:
                        bar_positions = ((640, 0), (640, present.y - 1),
                                         (640, present.bottom), (640, window[1] - 1))
                    for pos in bar_positions:
                        mapped, inside = sdl2_overlay.window_to_canvas_pos(pos)
                        self.assertFalse(inside, pos)
                        # Pozisyon yine clamped canvas koordinatıdır.
                        self.assertGreaterEqual(mapped[0], 0)
                        self.assertLessEqual(mapped[0], 1919)
                        self.assertGreaterEqual(mapped[1], 0)
                        self.assertLessEqual(mapped[1], 1079)
                finally:
                    self._pop_overlay_state(saved)


# ---------------------------------------------------------------------------
# Bölüm E — preset haritası (D.7 dokümante değerler)
# ---------------------------------------------------------------------------
class TestPresetMatrix(unittest.TestCase):

    def test_preset_multiplier_map_matches_documentation(self):
        for preset, expected in _EXPECTED_PRESET_MULTIPLIERS.items():
            with self.subTest(preset=preset):
                ui_scaling.set_ui_scale_preset(preset)
                try:
                    self.assertAlmostEqual(
                        ui_scaling.get_ui_scale_multiplier(), expected, places=6,
                    )
                finally:
                    ui_scaling.set_ui_scale_preset('normal')

    def test_canvas_aspect_invariant_across_presets(self):
        """Tüm preset'lerde tuval aspect'i pencere aspect'ini izler;
        preset yeni aspect üretmez (sunum letterbox'ı her zaman geçerli).

        Iterasyon-arası söküm rebuild_virtual_canvas transaction'ının
        (FAZ A3) gerçek çağrı dizisini izler: teardown → yeni kurulum.
        """
        pygame.display.init()
        pygame.display.set_mode((2560, 1080))  # 21:9
        try:
            for preset in _EXPECTED_PRESET_MULTIPLIERS:
                with self.subTest(preset=preset):
                    ui_scaling.set_ui_scale_preset(preset)
                    # Pass-through iterasyonlarında (FALLBACK) sökülecek patch
                    # yoktur; yalnız gerçek canvas aktifken teardown çağır —
                    # aksi halde FALLBACK→TEARING_DOWN teşhisi basılır.
                    if getattr(platform_utils, '_software_scale_active', False):
                        try:
                            platform_utils._teardown_virtual_canvas()
                        except Exception:
                            pass
                    _reset_canvas_state()
                    real = pygame.display.get_surface()
                    canvas = platform_utils.setup_virtual_canvas(
                        real, ui_scaling.get_ui_scale_multiplier(),
                    )
                    cw, ch = canvas.get_size()
                    self.assertLessEqual(
                        abs((cw / float(ch)) - (2560 / 1080.0)), 0.02,
                        (preset, canvas.get_size()),
                    )
        finally:
            try:
                platform_utils._teardown_virtual_canvas()
            except Exception:
                pass
            ui_scaling.set_ui_scale_preset('normal')
            _reset_canvas_state()


if __name__ == '__main__':
    unittest.main()
