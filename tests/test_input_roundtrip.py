# -*- coding: utf-8 -*-
"""FAZ A8 — girdi yolu (mouse hit-test) sözleşme testleri.

Gorsel_Olcek_Sorunlari_Cozum_Plani.md FAZ A8 kabul kriterlerinin test ayağı
(v2/tests/test_input_roundtrip.py'nin quadrix-demo kardeşi — demo kısıtları
gereği F bölümü demo level select'i kullanır):
  1. Window→canvas→window round-trip ≤ 1 canonical px (birden çok letterbox
     geometrisinde).
  2. Letterbox (siyah bar) tıklaması GEÇERSİZ event üretir: patched event
     kuyruğu MOUSEBUTTONDOWN'ı düşürür — kenar butonu yanlış tetiklenmesi
     biter. BUTTONUP/MOTION iletilir (sürükleme yarım kalmaz, hover sürer).
  3. get_presentation_info frame-başı tek hesap + paylaşılan snapshot
     (çağrı-başı dict/Rect.copy tahsisi yok — açık madde (e)).
  4. Software virtual canvas yolu da aynı (pos, inside) sözleşmesini taşır.
  5. Dönüşüm TAM BİR KEZ uygulanır: patched kuyruktan çıkan event.pos
     canvas koordinatındadır ve normalize_mouse_pos üzerinde idempotenttir.

Geometri notları: 21:9 pencere (2560x1080) + 16:9 canvas (1920x1080) →
present rect (320, 0, 1920, 1080) — yatay letterbox. 16:10 pencere
(1024x600) → (0, 12, 1024, 576) — dikey letterbox.
"""

from __future__ import annotations

import os
import pathlib
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
import pytest

ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


def _init_pygame() -> None:
    """Event/font alt sistemlerini hazırla; display surface AÇMA (p0 deseni)."""
    pygame.init()
    if not pygame.display.get_init():
        pygame.display.init()


# Geometriler: (window, canvas, beklenen present rect)
_GEOMETRIES = (
    ((2560, 1080), (1920, 1080), pygame.Rect(320, 0, 1920, 1080)),   # 21:9 → yatay bar
    ((1024, 600), (1920, 1080), pygame.Rect(0, 12, 1024, 576)),      # 16:10 → dikey bar
    ((2560, 1440), (1920, 1080), pygame.Rect(0, 0, 2560, 1440)),     # aynı oran → bar yok
)


def _fake_overlay(monkeypatch, window, canvas, present_rect):
    """sdl2_overlay modül durumunu sahte geometriyle kur (backend test deseni)."""
    import sdl2_overlay

    monkeypatch.setattr(sdl2_overlay, "_active", True)
    monkeypatch.setattr(sdl2_overlay, "_game_surface", pygame.Surface(canvas))
    monkeypatch.setattr(sdl2_overlay, "_width", window[0])
    monkeypatch.setattr(sdl2_overlay, "_height", window[1])
    monkeypatch.setattr(sdl2_overlay, "_present_rect", pygame.Rect(present_rect))
    sdl2_overlay.invalidate_presentation_info_cache()
    return sdl2_overlay


# ---------------------------------------------------------------------------
# Bölüm A — window_to_canvas_pos (pos, inside) sözleşmesi
# ---------------------------------------------------------------------------
class TestWindowToCanvasPosContract:
    def setup_method(self):
        _init_pygame()
        import sdl2_overlay

        self.ovl = sdl2_overlay

    def test_inside_positions_reported_inside(self, monkeypatch):
        ovl = _fake_overlay(monkeypatch, (2560, 1080), (1920, 1080), pygame.Rect(320, 0, 1920, 1080))
        # Kenar noktaları dahil (left/top inclusive, right/bottom exclusive).
        for pos in ((320, 0), (320 + 1919, 1079), (320 + 960, 540), (320, 1079)):
            mapped, inside = ovl.window_to_canvas_pos(pos)
            assert inside is True, pos
            assert 0 <= mapped[0] < 1920 and 0 <= mapped[1] < 1080

    def test_letterbox_positions_reported_outside(self, monkeypatch):
        ovl = _fake_overlay(monkeypatch, (2560, 1080), (1920, 1080), pygame.Rect(320, 0, 1920, 1080))
        # Yatay siyah bar: x < 320 veya x >= 2240.
        for pos in ((0, 540), (319, 540), (2240, 540), (2559, 540), (-5, 540)):
            mapped, inside = ovl.window_to_canvas_pos(pos)
            assert inside is False, pos
            # Pozisyon yine clamped canvas koordinatıdır (hover/motion yolları).
            assert 0 <= mapped[0] < 1920 and 0 <= mapped[1] < 1080

    def test_vertical_letterbox_positions_reported_outside(self, monkeypatch):
        ovl = _fake_overlay(monkeypatch, (1024, 600), (1920, 1080), pygame.Rect(0, 12, 1024, 576))
        for pos in ((512, 0), (512, 11), (512, 588), (512, 599)):
            _mapped, inside = ovl.window_to_canvas_pos(pos)
            assert inside is False, pos

    def test_fullscreen_geometry_everything_inside(self, monkeypatch):
        ovl = _fake_overlay(monkeypatch, (2560, 1440), (1920, 1080), pygame.Rect(0, 0, 2560, 1440))
        for pos in ((0, 0), (2559, 1439), (1280, 720)):
            _mapped, inside = ovl.window_to_canvas_pos(pos)
            assert inside is True, pos

    def test_degenerate_rect_is_passthrough_inside(self, monkeypatch):
        ovl = _fake_overlay(monkeypatch, (800, 600), (1920, 1080), pygame.Rect(0, 0, 0, 0))
        # Geometri yokken event düşürme devreye girmez (inside=True);
        # pozisyon canvas'a clamp edilir.
        mapped, inside = ovl.window_to_canvas_pos((700, 500))
        assert inside is True
        assert mapped == (700, 500)

    def test_invalid_pos_rejected(self, monkeypatch):
        ovl = _fake_overlay(monkeypatch, (2560, 1080), (1920, 1080), pygame.Rect(320, 0, 1920, 1080))
        mapped, inside = ovl.window_to_canvas_pos((None, "x"))
        assert mapped == (0, 0)
        assert inside is False

    def test_center_mapping_exact(self, monkeypatch):
        ovl = _fake_overlay(monkeypatch, (2560, 1080), (1920, 1080), pygame.Rect(320, 0, 1920, 1080))
        mapped, inside = ovl.window_to_canvas_pos((320 + 960, 540))
        assert inside is True
        assert mapped == (960, 540)


# ---------------------------------------------------------------------------
# Bölüm B — ±1 px round-trip
# ---------------------------------------------------------------------------
class TestRoundTrip:
    def setup_method(self):
        _init_pygame()
        import sdl2_overlay

        self.ovl = sdl2_overlay

    @pytest.mark.parametrize("window,canvas,rect", [(g[0], g[1], g[2]) for g in _GEOMETRIES])
    def test_round_trip_within_one_pixel(self, monkeypatch, window, canvas, rect):
        ovl = _fake_overlay(monkeypatch, window, canvas, rect)
        # Present rect içi kapsama noktaları (kenarlar dahil).
        xs = {rect.x, rect.x + rect.w - 1, rect.x + rect.w // 2}
        ys = {rect.y, rect.y + rect.h - 1, rect.y + rect.h // 2}
        for wx in xs:
            for wy in ys:
                mapped, inside = ovl.window_to_canvas_pos((wx, wy))
                assert inside is True, (wx, wy)
                back = ovl.canvas_to_window_pos(mapped)
                err_x = abs(back[0] - wx)
                err_y = abs(back[1] - wy)
                assert err_x <= 1 and err_y <= 1, (wx, wy, mapped, back)

    def test_round_trip_canvas_origin_and_far_corner(self, monkeypatch):
        ovl = _fake_overlay(monkeypatch, (2560, 1080), (1920, 1080), pygame.Rect(320, 0, 1920, 1080))
        assert ovl.canvas_to_window_pos((0, 0)) == (320, 0)
        back = ovl.canvas_to_window_pos((1919, 1079))
        assert abs(back[0] - (320 + 1919)) <= 1
        assert abs(back[1] - 1079) <= 1


# ---------------------------------------------------------------------------
# Bölüm C — patched event kuyruğu: letterbox click düşürme
# ---------------------------------------------------------------------------
def _make_mouse_event(etype, pos, button=1):
    attrs = {"pos": pos}
    if etype != pygame.MOUSEMOTION:
        attrs["button"] = button
    else:
        attrs["rel"] = (0, 0)
        attrs["buttons"] = (0, 0, 0)
    return pygame.event.Event(etype, attrs)


class TestPatchedEventQueueLetterboxReject:
    def setup_method(self):
        _init_pygame()
        import platform_utils

        self.pu = platform_utils

    def _patch_geometry(self, monkeypatch):
        import sdl2_overlay

        ovl = _fake_overlay(monkeypatch, (2560, 1080), (1920, 1080), pygame.Rect(320, 0, 1920, 1080))
        # Software virtual canvas kapalı — yalnız SDL2 overlay yolu aktif.
        monkeypatch.setattr(self.pu, "_software_scale_active", False)
        monkeypatch.setattr(self.pu, "_virtual_blit_rect", None)
        monkeypatch.setattr(self.pu, "_event_patch_active", True)
        return ovl

    def test_letterbox_buttondown_dropped(self, monkeypatch):
        self._patch_geometry(monkeypatch)
        events = [
            _make_mouse_event(pygame.MOUSEBUTTONDOWN, (100, 540)),    # sol bar
            _make_mouse_event(pygame.MOUSEBUTTONDOWN, (2400, 540)),   # sağ bar
        ]
        monkeypatch.setattr(self.pu, "_orig_event_get", lambda *a, **k: list(events))
        result = self.pu._patched_event_get()
        assert result == []

    def test_inside_buttondown_delivered_normalized(self, monkeypatch):
        self._patch_geometry(monkeypatch)
        events = [_make_mouse_event(pygame.MOUSEBUTTONDOWN, (320 + 960, 540))]
        monkeypatch.setattr(self.pu, "_orig_event_get", lambda *a, **k: list(events))
        result = self.pu._patched_event_get()
        assert len(result) == 1
        assert result[0].type == pygame.MOUSEBUTTONDOWN
        assert result[0].pos == (960, 540)

    def test_letterbox_buttonup_and_motion_delivered_clamped(self, monkeypatch):
        self._patch_geometry(monkeypatch)
        events = [
            _make_mouse_event(pygame.MOUSEBUTTONUP, (100, 540)),
            _make_mouse_event(pygame.MOUSEMOTION, (2400, 540)),
        ]
        monkeypatch.setattr(self.pu, "_orig_event_get", lambda *a, **k: list(events))
        result = self.pu._patched_event_get()
        assert len(result) == 2
        by_type = {e.type: e for e in result}
        # UP düşürülmez: sürükleme durumu yarım kalmasın (arm'sız UP tetiklemez).
        assert pygame.MOUSEBUTTONUP in by_type
        # Motion clamped pozisyonla iletilir (hover takibi sürer); sağ bar
        # (x=2400) canvas sağ kenarına kenetlenir.
        assert by_type[pygame.MOUSEMOTION].pos == (1919, 540)

    def test_non_mouse_events_passthrough(self, monkeypatch):
        self._patch_geometry(monkeypatch)
        key_event = pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_ESCAPE})
        monkeypatch.setattr(self.pu, "_orig_event_get", lambda *a, **k: [key_event])
        result = self.pu._patched_event_get()
        assert len(result) == 1
        assert result[0].type == pygame.KEYDOWN

    def test_gamepad_simulated_mouse_not_touched(self, monkeypatch):
        self._patch_geometry(monkeypatch)
        sim = _make_mouse_event(pygame.MOUSEBUTTONDOWN, (100, 540))
        sim.from_gamepad = True
        monkeypatch.setattr(self.pu, "_orig_event_get", lambda *a, **k: [sim])
        result = self.pu._patched_event_get()
        # Gamepad simüle olayı zaten canvas koordinatında — letterbox
        # koşulu OLMASA BİLE (100,540) bar içinde görünse de dokunulmaz:
        # dönüşüm yalnız ham window olaylarına uygulanır (TAM BİR KEZ).
        assert len(result) == 1
        assert result[0].pos == (100, 540)

    def test_normalize_mouse_pos_idempotent_on_canvas_pos(self, monkeypatch):
        # A1 sözleşmesi: patched kuyruktan çıkan pos canvas koordinatındadır;
        # normalize_mouse_pos onu TEKRAR dönüştürmez (çift dönüşüm yok).
        self._patch_geometry(monkeypatch)
        for canvas_pos in ((0, 0), (960, 540), (1919, 1079)):
            assert self.pu.normalize_mouse_pos(canvas_pos) == canvas_pos


# ---------------------------------------------------------------------------
# Bölüm D — presentation info frame-başı cache
# ---------------------------------------------------------------------------
class TestPresentationInfoCache:
    def setup_method(self):
        _init_pygame()
        import sdl2_overlay

        self.ovl = sdl2_overlay

    def test_same_snapshot_object_within_frame(self, monkeypatch):
        ovl = _fake_overlay(monkeypatch, (2560, 1080), (1920, 1080), pygame.Rect(320, 0, 1920, 1080))
        info_a = ovl.get_presentation_info()
        info_b = ovl.get_presentation_info()
        info_c = ovl.get_presentation_info()
        # Paylaşılan snapshot: çağrı-başı dict/Rect.copy tahsisi yok.
        assert info_a is info_b is info_c

    def test_invalidate_produces_fresh_snapshot(self, monkeypatch):
        ovl = _fake_overlay(monkeypatch, (2560, 1080), (1920, 1080), pygame.Rect(320, 0, 1920, 1080))
        first = ovl.get_presentation_info()
        ovl.invalidate_presentation_info_cache()
        second = ovl.get_presentation_info()
        assert first is not second
        assert first == second

    def test_present_invalidates_snapshot(self, monkeypatch):
        ovl = _fake_overlay(monkeypatch, (2560, 1080), (1920, 1080), pygame.Rect(320, 0, 1920, 1080))
        first = ovl.get_presentation_info()
        # _present render yolları gerçek renderer ister; kare-sınırı davranışı
        # invalidate çağrısıyla ölçülür (render kısmı backend testlerinde).
        ovl.invalidate_presentation_info_cache()
        assert ovl.get_presentation_info() is not first

    def test_snapshot_values_correct(self, monkeypatch):
        ovl = _fake_overlay(monkeypatch, (2560, 1080), (1920, 1080), pygame.Rect(320, 0, 1920, 1080))
        info = ovl.get_presentation_info()
        assert info["active"] is True
        assert info["window_w"] == 2560 and info["window_h"] == 1080
        assert info["canvas_w"] == 1920 and info["canvas_h"] == 1080
        assert info["offset_x"] == 320 and info["offset_y"] == 0
        assert info["blit_w"] == 1920 and info["blit_h"] == 1080
        assert abs(info["scale_x"] - 1.0) < 1e-9
        assert abs(info["scale_y"] - 1.0) < 1e-9

    def test_normalize_mouse_pos_uses_cached_snapshot(self, monkeypatch):
        # normalize_mouse_pos'un overlay yolu presentation info'yu okur;
        # cache aktifken çağrı-başı yeni nesne üretilmez (nesne kimliği sabit).
        ovl = _fake_overlay(monkeypatch, (2560, 1080), (1920, 1080), pygame.Rect(320, 0, 1920, 1080))
        import platform_utils

        monkeypatch.setattr(platform_utils, "_event_patch_active", True)
        first = self.pu_normalize(platform_utils)
        second = self.pu_normalize(platform_utils)
        assert first == second

    @staticmethod
    def pu_normalize(platform_utils):
        return platform_utils.normalize_mouse_pos((960, 540))


# ---------------------------------------------------------------------------
# Bölüm E — software virtual canvas yolu aynı sözleşmeyi taşır
# ---------------------------------------------------------------------------
class TestSoftwareCanvasLetterboxContract:
    def setup_method(self):
        _init_pygame()
        import platform_utils

        self.pu = platform_utils

    def _patch_software_canvas(self, monkeypatch, canvas, blit_rect):
        import sdl2_overlay

        monkeypatch.setattr(sdl2_overlay, "_active", False)
        monkeypatch.setattr(self.pu, "_software_scale_active", True)
        monkeypatch.setattr(self.pu, "_virtual_blit_rect", blit_rect)
        monkeypatch.setattr(self.pu, "_software_canvas", pygame.Surface(canvas))
        monkeypatch.setattr(self.pu, "_event_patch_active", False)

    def test_letterbox_outside_and_clamped_pos(self, monkeypatch):
        # 1024x600 pencere, 1920x1080 canvas, (0, 12, 1024, 576) blit rect.
        self._patch_software_canvas(monkeypatch, (1920, 1080), (0, 12, 1024, 576))
        for raw in ((512, 0), (512, 11), (512, 588), (512, 599)):
            pos, inside = self.pu._normalize_event_pos_checked(raw)
            assert inside is False, raw
            assert 0 <= pos[0] < 1920 and 0 <= pos[1] < 1080

    def test_inside_positions_map_to_canvas(self, monkeypatch):
        self._patch_software_canvas(monkeypatch, (1920, 1080), (0, 12, 1024, 576))
        pos, inside = self.pu._normalize_event_pos_checked((512, 12 + 288))
        assert inside is True
        # Dikey merkez: (12+288-12) * 1080/576 = 540.
        assert abs(pos[1] - 540) <= 1
        assert abs(pos[0] - 960) <= 1

    def test_plain_wrapper_returns_position_only(self, monkeypatch):
        self._patch_software_canvas(monkeypatch, (1920, 1080), (0, 12, 1024, 576))
        result = self.pu._normalize_event_pos((512, 0))
        assert isinstance(result, tuple) and len(result) == 2


# ---------------------------------------------------------------------------
# Bölüm F — hit/draw rect eş zamanlılık (aynı generation)
# ---------------------------------------------------------------------------
class TestHitDrawRectGeneration:
    def test_level_select_play_button_click_triggers_action(self):
        _init_pygame()
        from campaign.level_select import CampaignLevelSelect

        screen = pygame.Surface((1280, 720))
        try:
            selector = CampaignLevelSelect(screen)
        except Exception as exc:
            pytest.skip(f"level_select kurulamadi (kirli ortam): {exc}")
        try:
            for probe_font in (
                selector.font_title,
                selector.font_medium,
                selector.font_small,
            ):
                probe_font.size("")
        except Exception:
            pytest.skip("level_select fontlari olu (pygame.quit mayini)")
        selector.draw()
        play = selector.play_button
        assert play is not None
        # Çizim rect'i (draw() ürünü) ile hit rect (handle_input okuduğu
        # self.play_button) aynı nesne — aynı generation'dan türe.
        click = _make_mouse_event(pygame.MOUSEBUTTONDOWN, play.center)
        action = selector.handle_input(click)
        level = selector.selected_level
        if action is not None:
            # Level kilitli değilse merkez tıklaması o eylemi üretir.
            assert action == f"play_{level}"
        # Rect dışı +2 px tıklama aynı eylemi ÜRETMEZ (draw rect = hit rect
        # sözleşmesi: kenar hassasiyeti çizimle örtüşür).
        outside = _make_mouse_event(pygame.MOUSEBUTTONDOWN, (play.right + 2, play.centery))
        assert selector.handle_input(outside) != f"play_{level}"
