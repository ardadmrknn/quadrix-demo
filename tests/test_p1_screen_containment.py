# -*- coding: utf-8 -*-
"""FAZ A7 — P1 ekran containment sözleşme testleri (S5 kart + S7 level select + S8-S10 menü).

Gorsel_Olcek_Sorunlari_Cozum_Plani.md FAZ A7 kabul kriterlerinin test ayağı:
  1. S5 — MysteryCardUI._get_overlay_scale tek ölçek kaynağına
     (ui_scaling.get_modal_scale, standard profil 0.68-1.20) bağlıdır;
     okunabilirlik katı (readable_floor) küçük canvaslarda ölçeği yukarı
     çeker ama üst sınırı ihlal etmez.
  2. S7 — CampaignLevelSelect: grid + PLAY footer canonical safe rect
     içindedir; PLAY kenar boşluğu 24 canonical px ölçek sözleşmesidir.
  3. S8-S10 — menü: _apply_layout_override_rect coord_space'i gerçekten
     uygular (canvas_pct → oranı koruyan letterbox-fit bölge; 21:9'da
     düzen yatay esnetilmez); leaderboard satır min-height sözleşmesi
     (avatar satıra sığar) ve panel containment.

v2 kardeşinden farklar (demo-doğal): demo leaderboard'ı satır yüzey LRU
cache'i ve footer (self-rank) kullanmaz — bu testler yalnız demo'da var
olan sözleşmeleri kilitler; satır min-height Surface spy ile ölçülür.

Ölçüm (komşu-fark/±%20 bant) A0 compare_ui_captures.py capture altyapısıyla
A9 matrisinde doğrulanır; bu dosya geometri invariant'larını deterministik
olarak kilitler.
"""

from __future__ import annotations

import os
import pathlib
import sys
from collections import Counter
from types import SimpleNamespace

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
import pytest

ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


def _init_pygame() -> None:
    """Font/temel alt sistemleri hazırla; display surface AÇMA (p0 deseni)."""
    pygame.init()
    pygame.font.init()
    if not pygame.display.get_init():
        pygame.display.init()


def _retro_style_alive(instance) -> bool:
    """retro_style instance'ı gerçek ve fontları canlı mı? (p0 katman-3 mayını).

    Tam paket koşumunda önceki dosyalar pygame.quit() çağırabilir; cache'teki
    ölü Font draw yollarını düşürür. Stub/ölü font görülürse test skip edilir
    (tek dosya koşumunda gerçek doğrulama yapılır).
    """
    if not hasattr(instance, "render_multilingual_text"):
        return False
    try:
        probe = instance.get_font(12)
        probe.size("")
    except Exception:
        return False
    return True


# ---------------------------------------------------------------------------
# Bölüm A — S5: MysteryCardUI ölçek sözleşmesi
# ---------------------------------------------------------------------------
class TestMysteryOverlayScaleContract:
    """_get_overlay_scale: modal profil sınırı + readable floor baskınlığı."""

    def setup_method(self):
        _init_pygame()
        from game_modes_extra import MysteryCardUI

        self.ui = MysteryCardUI()

    def test_scale_stays_within_standard_modal_profile_bounds(self):
        for size in ((1366, 768), (1920, 1080), (1024, 600), (2560, 1440), (800, 480)):
            screen = pygame.Surface(size)
            scale = self.ui._get_overlay_scale(screen)
            # standard modal profili: [0.68, 1.20]; floor ≤ 1.0 olduğundan
            # baskınlık üst sınırı ihlal etmez.
            assert 0.68 <= scale <= 1.20, (size, scale)

    def test_readable_floor_dominates_on_small_canvas(self):
        # Okunabilir taban (1180x760) ekrandan büyükse floor modal ölçeği
        # yukarı çeker: sonuç floor'dan küçük olamaz.
        rw, rh = self.ui._overlay_readable_min_size
        for size in ((800, 480), (1024, 600)):
            screen = pygame.Surface(size)
            scale = self.ui._get_overlay_scale(screen)
            floor = min(1.0, min(size[0] / rw, size[1] / rh))
            assert scale >= floor - 1e-9, (size, scale, floor)

    def test_int_arguments_backward_compatible(self):
        # Eski çağrı yüzeyi: (width, height) ints.
        scale_surface = self.ui._get_overlay_scale(pygame.Surface((1366, 768)))
        scale_ints = self.ui._get_overlay_scale(1366, 768)
        assert abs(scale_surface - scale_ints) < 1e-9

    def test_explicit_reference_size_respected(self):
        # set_overlay_reference_size referans boyutu ölçeği büyütür/daraltır:
        # büyük referans → küçük ölçek (referansa oran), ama profil alt sınırı
        # 0.68'in altına inmez.
        self.ui.set_overlay_reference_size(2560, 1440)
        scale = self.ui._get_overlay_scale(pygame.Surface((1366, 768)))
        assert scale >= 0.68
        self.ui.set_overlay_reference_size(800, 600)
        scale_small_ref = self.ui._get_overlay_scale(pygame.Surface((1366, 768)))
        assert scale_small_ref > scale


# ---------------------------------------------------------------------------
# Bölüm B — S7: level select safe alan + PLAY footer sözleşmesi
# ---------------------------------------------------------------------------
class TestLevelSelectSafeArea:
    """CampaignLevelSelect.draw: grid + PLAY canonical safe rect içinde."""

    def _make_level_select(self, size):
        from campaign.level_select import CampaignLevelSelect

        screen = pygame.Surface(size)
        try:
            selector = CampaignLevelSelect(screen)
        except Exception as exc:  # stub/kirli ortam (tam paket mayını)
            pytest.skip(f"level_select kurulamadi (kirli ortam): {exc}")
        # Katman-3 font mayını (p0 docstring'i): önceki testlerden biri
        # pygame.quit() çağırmış olabilir; retro_style font cache'indeki ölü
        # Font'lar draw yolunu düşürür. Kurulumda üretilen gerçek fontlar
        # probe edilir — ölüyse skip (tek dosya koşumunda doğrulama yapılır).
        try:
            for probe_font in (
                selector.font_title,
                selector.font_large,
                selector.font_medium,
                selector.font_small,
                selector.font_tiny,
            ):
                probe_font.size("")
        except Exception:
            pytest.skip("level_select fontlari olu (pygame.quit mayini)")
        return selector

    def test_frame_safe_area_fallback_and_passthrough(self):
        _init_pygame()
        from campaign.level_select import CampaignLevelSelect

        selector = CampaignLevelSelect.__new__(CampaignLevelSelect)
        selector.screen = pygame.Surface((800, 600))
        selector._frame_safe_rect = None
        assert selector._frame_safe_area() == (0, 0, 800, 600)
        selector._frame_safe_rect = pygame.Rect(32, 18, 736, 564)
        assert selector._frame_safe_area() == (32, 18, 736, 564)

    def test_grid_and_play_inside_safe_rect_1280x720(self):
        selector = self._make_level_select((1280, 720))
        selector.draw()
        safe = selector._frame_safe_rect
        assert safe is not None
        assert safe.width <= 1280 and safe.height <= 720
        # PLAY: safe alan içinde, alt/sağ kenar boşluğu 24 canonical px
        # (ölçekle çarpılmış) sözleşmesi.
        play = selector.play_button
        assert safe.contains(play), (safe, play)
        expected_margin = max(1, round(24 * selector._get_ui_scale()))
        assert abs((safe.bottom - play.bottom) - expected_margin) <= 1
        assert abs((safe.right - play.right) - expected_margin) <= 1
        # Grid butonları safe alan içinde.
        assert selector.level_buttons, "grid butonları üretilmedi"
        for entry in selector.level_buttons:
            rect = entry[0] if isinstance(entry, tuple) else entry
            assert safe.contains(rect), (safe, rect)

    def test_grid_and_play_inside_safe_rect_small_window(self):
        # Küçük pencere: min clamp'ler devredeyken de sözleşme geçmeli.
        selector = self._make_level_select((1024, 600))
        selector.draw()
        safe = selector._frame_safe_rect
        assert safe is not None
        play = selector.play_button
        assert safe.contains(play), (safe, play)
        expected_margin = max(1, round(24 * selector._get_ui_scale()))
        assert abs((safe.bottom - play.bottom) - expected_margin) <= 1
        for entry in selector.level_buttons:
            rect = entry[0] if isinstance(entry, tuple) else entry
            assert safe.contains(rect), (safe, rect)


def _module_retro_style():
    import retro_style as retro_style_module

    return getattr(retro_style_module, "retro_style", None)


# ---------------------------------------------------------------------------
# Bölüm C — S8-S10: menü layout override + leaderboard sözleşmeleri
# ---------------------------------------------------------------------------
class TestLayoutOverrideCoordSpace:
    """_apply_layout_override_rect: coord_space uygulanır (screen_pct'ye zorlanmaz)."""

    def _make_menu(self):
        from menu import Menu

        menu = Menu.__new__(Menu)
        menu._layout_override_coord_space = "screen_pct"
        menu._layout_override_reference_canvas = None
        return menu

    def test_fit_aspect_region_letterboxes_16_9_into_ultrawide(self):
        from menu import _fit_aspect_region

        # 16:9 → 2560x1080 (21:9): fazla yatay alan side gutter.
        assert _fit_aspect_region(16 / 9, 2560, 1080) == (320, 0, 1920, 1080)

    def test_fit_aspect_region_letterboxes_16_9_into_tall(self):
        from menu import _fit_aspect_region

        # 16:9 → 1024x600: dikey taşma üst/alt gutter.
        region = _fit_aspect_region(16 / 9, 1024, 600)
        assert region == (0, 12, 1024, 576)

    def test_fit_aspect_region_degenerate(self):
        from menu import _fit_aspect_region

        assert _fit_aspect_region(0.0, 100, 100) == (0, 0, 100, 100)
        assert _fit_aspect_region(-1.0, 100, 100) == (0, 0, 100, 100)

    def test_screen_pct_uses_full_screen(self):
        menu = self._make_menu()
        menu._layout_override_cache = {"tile": {"x_pct": 0.25, "y_pct": 0.1, "w_pct": 0.5, "h_pct": 0.2}}
        menu._layout_override_mtime = None
        menu._layout_override_stat_frame = 0
        menu._layout_override_last_stat_frame = 0
        menu._layout_override_stat_check_interval = 10**9
        menu._layout_override_cache = dict(menu._layout_override_cache)
        menu._load_layout_overrides = lambda: menu._layout_override_cache
        rect = menu._apply_layout_override_rect("tile", pygame.Rect(0, 0, 10, 10), 1280, 720, min_w=10, min_h=10)
        assert (rect.x, rect.y, rect.width, rect.height) == (320, 72, 640, 144)

    def test_canvas_pct_resolves_against_aspect_fit_region(self):
        menu = self._make_menu()
        menu._layout_override_coord_space = "canvas_pct"
        menu._layout_override_reference_canvas = (0, 0, 1920, 1080)
        menu._layout_override_cache = {"tile": {"x_pct": 0.5, "y_pct": 0.0, "w_pct": 0.25, "h_pct": 0.5}}
        menu._load_layout_overrides = lambda: menu._layout_override_cache
        # 21:9 ekranda canvas bölgesi (320, 0, 1920, 1080): x = 320 + 0.5*1920.
        rect = menu._apply_layout_override_rect("tile", pygame.Rect(0, 0, 10, 10), 2560, 1080, min_w=10, min_h=10)
        assert (rect.x, rect.y) == (320 + 960, 0)
        assert rect.width == 480
        assert rect.height == 540

    def test_screen_pct_payload_with_reference_canvas_unchanged_semantics(self):
        # Açık screen_pct beyanı: reference_canvas varsa bile tam ekran oranı.
        menu = self._make_menu()
        menu._layout_override_coord_space = "screen_pct"
        menu._layout_override_reference_canvas = (0, 0, 1920, 1080)
        menu._layout_override_cache = {"tile": {"x_pct": 0.5, "y_pct": 0.0, "w_pct": 0.5, "h_pct": 0.5}}
        menu._load_layout_overrides = lambda: menu._layout_override_cache
        rect = menu._apply_layout_override_rect("tile", pygame.Rect(0, 0, 10, 10), 2560, 1080, min_w=10, min_h=10)
        assert (rect.x, rect.width) == (1280, 1280)


def _make_leaderboard_menu(screen_size=(1280, 720), entries=None, persona_map=None, current_sid=""):
    """_draw_mystery_leaderboard_panel için minimal Menu stub'u (p0 deseni).

    Demo kardeşi: satır yüzey LRU cache'i ve footer yoktur; stub yalnız
    demo'nun çizim yolunun dokunduğu alanları sağlar.
    """
    from menu import Menu

    menu = Menu.__new__(Menu)
    menu.screen = pygame.Surface(screen_size)
    menu._menu_panel_content_scale = lambda: 1.0
    menu._ui_scale = lambda: 1.0
    menu._refresh_mystery_leaderboard_cache = lambda force=False: None
    menu._get_mystery_lb_display_entries = lambda: (entries or [], False, 0)
    menu._mystery_lb_tab = "global"
    menu._mystery_lb_error = None
    menu._mystery_lb_tab_rects = {}
    menu._leaderboard_service = SimpleNamespace(current_steam_id=current_sid)
    menu._steam_player_cache = persona_map or {}
    menu._steam_avatar_surf = {}
    menu._steam_avatar_bytes = {}
    menu._mystery_lb_trailer_row_y = {}
    menu._mystery_lb_trailer_last_tick_ms = 0
    menu._load_main_theme_icon = lambda name, size: None
    return menu


def _default_entries(count=10):
    return [
        {"steam_id": f"76561198000000{i:02d}", "rank": i + 1, "score": 10000 - i * 137}
        for i in range(count)
    ]


class TestMysteryLeaderboardPanelContract:
    """S8-S10: satır min-height, panel containment sözleşmeleri (demo-doğal)."""

    def setup_method(self):
        _init_pygame()
        import menu as menu_module

        if not _retro_style_alive(getattr(menu_module, "retro_style", None)):
            pytest.skip("menu.retro_style stub/olu font (tam paket mayini)")

    def test_row_min_height_fits_avatar_content(self, monkeypatch):
        # panel_scale deterministik: default panel 380x500, verilen rect aynı
        # boyutta → boost 1.0 → panel_scale = 1.0 * max(1.0, 1.24) = 1.24.
        # Demo satır yüzeyi cache'sizdir; boyut sözleşmesi Surface spy ile
        # ölçülür: satır dolgusu (row_w, row_h - s(5)) boyutunda ve tam
        # max_rows kez oluşturulur.
        import menu as menu_module

        entries = _default_entries(10)
        menu = _make_leaderboard_menu(entries=entries)
        created_sizes = []
        original_surface = pygame.Surface

        def surface_spy(size, *args, **kwargs):
            created_sizes.append(tuple(size))
            return original_surface(size, *args, **kwargs)

        monkeypatch.setattr(menu_module.pygame, "Surface", surface_spy)
        menu._draw_mystery_leaderboard_panel(pygame.Rect(900, 200, 380, 500))

        size_counts = Counter(created_sizes)
        candidates = [
            size
            for size, count in size_counts.items()
            if count == len(entries) and size[0] != size[1] and size[0] > 100
        ]
        assert candidates, f"satir dolgu yuzeyi yakalanamadi: {dict(size_counts)}"
        row_w, row_surf_h = candidates[0]
        panel_scale = 1.24
        s = lambda v, minimum=1: max(minimum, round(v * panel_scale))
        row_min_h = max(s(26), 20 + s(13))
        # row_rect yüksekliği = row_h - s(5): içerik sözleşmesi — en az 20 px
        # avatar + dikey padding satır rect'ine sığar.
        assert row_surf_h + s(5) >= row_min_h, (row_surf_h, row_min_h)

    def test_panel_rect_clamped_to_screen(self):
        # Ekranı taşan panel rect'i ekrana kenetlenir (S10).
        entries = _default_entries(10)
        menu = _make_leaderboard_menu(entries=entries)
        screen_w, screen_h = menu.screen.get_size()
        overflowing = pygame.Rect(900, screen_h - 100, 380, 500)
        menu._draw_mystery_leaderboard_panel(overflowing)
        tab_rect = menu._mystery_lb_tab_rects.get("global")
        assert tab_rect is not None
        assert tab_rect.bottom <= screen_h
        assert tab_rect.top >= 0

    def test_tiny_panel_hidden_no_tab_rects(self):
        # Çakışan/aşırı dar panel layout çakışmasını önlemek için gizlenir.
        entries = _default_entries(10)
        menu = _make_leaderboard_menu(entries=entries)
        menu._draw_mystery_leaderboard_panel(pygame.Rect(0, 0, 100, 100))
        assert menu._mystery_lb_tab_rects == {}
