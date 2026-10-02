# -*- coding: utf-8 -*-
"""FAZ A6 — P0 ekran containment sözleşme testleri (S4 game-over + S6 gameplay).

Gorsel_Olcek_Sorunlari_Cozum_Plani.md FAZ A6 kabul kriterlerinin test ayağı:
  1. S6 — compute_single_player_layout canvas_safe_rect alır: board + yan
     panel + sol grup ortak parent safe rect içinde kalır (None → eski
     davranış, geriye dönük uyumlu).
  2. game_over_surfaces LRU sözleşmeleri: kare-başı tahsis yasak → aynı key
     aynı Surface; kapasite sınırlı; kuantize key'ler.
  3. S4 — P0 game-over draw yolları (PvP + Coop gerçek draw): eylem rect'leri
     canonical safe rect içinde VE birbirleriyle disjoint (çakışmıyor).
     Online PvP draw zinciri pvp_game ile birebir aynı desen olduğundan
     buradaki PvP draw testi deseni temsil eder (ayrıca
     test_online_pvp_result_majority/threshold paketleri sözdizimi +
     yaşam döngüsünü kapsar).

Ölçüm (merkez_sapma_px ≤ 40/60) A0 compare_ui_captures.py capture
altyapısıyla A9 matrisinde doğrulanır; bu dosya geometri invariant'larını
deterministik olarak kilitler.
"""

from __future__ import annotations

import os
import pathlib
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from gameplay_layout import compute_single_player_layout
import game_over_surfaces
from game_over_surfaces import (
    get_card_tint_surface,
    get_circle_surface,
    get_custom_surface,
    get_render_safe_rect,
    get_rounded_rect_surface,
    get_solid_alpha_surface,
)
import pvp_game as pvp_game_module
import coop_game as coop_game_module
from pvp_game import PvPGame
from coop_game import CoopGame
from board import Board


# ---------------------------------------------------------------------------
# Ortak kurulum
# ---------------------------------------------------------------------------
def _init_pygame() -> None:
    """Font/temel alt sistemleri hazırla; display surface AÇMA.

    Tam paket koşumunda (alfabetik zincir) önceki dosyaların bıraktığı
    display/window durumunu kirletmemek için set_mode çağrılmaz —
    get_render_geometry offscreen Surface'lerde kendi boyutunu kullanır.
    """
    pygame.init()
    pygame.font.init()
    if not pygame.display.get_init():
        pygame.display.init()


def _retro_style_is_real(draw_module) -> bool:
    """Tam paket mayınına karşı koruma: draw modülünün retro_style'i gerçek mi?

    Mayının üç katmanı vardır:
      1. retro_style modülü stub'lanmış (test_coop ailesi) — draw yolu
         AttributeError alır.
      2. Daha sinsi: retro_style MODÜLÜ temizdir ama draw modülü
         (pvp_game/coop_game) stub ortamında import edildiği için module-level
         ``from retro_style import retro_style`` binding'i _RS stub'ına
         bağlıdır — modülü inceleyen bir guard bunu görmez.
      3. Font mayını: uzun zincirlerde pygame ailesi defalarca yeniden
         import edilir (conftest purgeleri) veya bir test pygame.quit()
         çağırır; retro_style instance'ının font_cache'indeki Font
         objelerinin SDL_ttf referansı ölür — init geri gelse bile
         "Invalid font (font module quit since font created)" fırlar.
         Cache'teki herhangi bir font probe edilir; ölüyse test skip
         edilir (tek dosya koşumunda gerçek doğrulama yapılır).
    Bu yüzden doğrudan draw modülünün local ``retro_style`` attribute'una
    bakarız: draw çağrısı tam olarak bu nesneyi kullanır. Stub/ölü font
    görülürse test skip edilir (tek dosya koşumunda gerçek doğrulama yapılır).
    """
    candidate = getattr(draw_module, 'retro_style', None)
    if not hasattr(candidate, 'wrap_text'):
        # retro_style attribute'u hiç yoksa (draw modülü farklı isimle import
        # etmiş olabilir) modülün kendisine düş.
        try:
            import retro_style as _rs_mod
            candidate = getattr(_rs_mod, 'retro_style', None)
        except Exception:
            return False
        if not hasattr(candidate, 'wrap_text'):
            return False
    # Katman 3: cache'te ölü Font var mı? (quit / pygame re-import sonrası)
    try:
        for _probe_font in list(getattr(candidate, 'font_cache', {}).values()):
            _probe_font.size('')
            break  # tek bir ölü font bile tüm draw'u düşürür; ilkini yeter
    except Exception:
        return False
    return True


def _clear_surface_caches() -> None:
    """Testler arası LRU durumunu sıfırla (kapasite testleri deterministik kalsın)."""
    for cache, order in (
        (game_over_surfaces._SOLID_CACHE, game_over_surfaces._SOLID_ORDER),
        (game_over_surfaces._ROUNDED_CACHE, game_over_surfaces._ROUNDED_ORDER),
        (game_over_surfaces._CIRCLE_CACHE, game_over_surfaces._CIRCLE_ORDER),
        (game_over_surfaces._TINT_CACHE, game_over_surfaces._TINT_ORDER),
        (game_over_surfaces._CUSTOM_CACHE, game_over_surfaces._CUSTOM_ORDER),
    ):
        cache.clear()
        order.clear()
    game_over_surfaces._SAFE_RECT_CACHE = None


# ---------------------------------------------------------------------------
# Bölüm A — S6: gameplay layout canonical safe rect
# ---------------------------------------------------------------------------
class TestSinglePlayerLayoutSafeRect:
    """compute_single_player_layout: board/panel aynı parent safe rect'i paylaşır."""

    def test_symmetric_safe_rect_bounds_board_and_panel(self):
        metrics = compute_single_player_layout(
            active_size=(1920, 1080),
            effective_size=(1920, 1080),
            board_width=10,
            board_height=20,
            info_panel_height=120,
            canvas_safe_rect=(96, 54, 1728, 972),
        )
        # safe marjı x=96, y=54 (scale 1): sol/üst kenarlar safe alandan içeride.
        assert metrics.board_x >= 96
        assert metrics.board_y >= 54
        assert metrics.panel_x >= 96
        # Sağ kenar: outer_margin=96 tabanıyla panel sağ kenarı safe sağdan taşmaz
        # (yuvarlama toleransı ±2 px).
        assert metrics.panel_x + metrics.panel_width <= 1920 - 96 + 2
        # Alt kenar: board yüksekliği kullanılabilir alandan türer, taşmaz.
        assert metrics.board_y + metrics.board_height <= 1080

    def test_asymmetric_safe_rect_shifts_board_right(self):
        # safe alan sol üstten değil yalnızca sağdan kesiyor: x marjı = 1920-1600 = 320.
        metrics = compute_single_player_layout(
            active_size=(1920, 1080),
            effective_size=(1920, 1080),
            board_width=10,
            board_height=20,
            canvas_safe_rect=(0, 0, 1600, 1080),
        )
        assert metrics.board_x >= 320
        assert metrics.panel_x >= 320
        assert metrics.board_y >= 8

    def test_none_keeps_legacy_margin_behavior(self):
        metrics = compute_single_player_layout(
            active_size=(1920, 1080),
            effective_size=(1920, 1080),
            board_width=10,
            board_height=20,
        )
        # Safe yok: eski davranış — outer_margin tabanı (≥12) geçerli.
        assert metrics.board_x >= 12
        assert metrics.panel_x >= 12
        assert metrics.board_y >= 8
        assert metrics.panel_gap >= 1

    def test_left_group_reserve_stays_inside_safe_rect(self):
        # Sol kart grubu (campaign/mode reserve) da aynı safe parent'tan türer.
        metrics = compute_single_player_layout(
            active_size=(1920, 1080),
            effective_size=(1920, 1080),
            board_width=10,
            board_height=20,
            left_group_reserve_px=340,
            canvas_safe_rect=(96, 54, 1728, 972),
        )
        group_left = metrics.board_x - int(340 * 1.0)
        assert group_left >= 96 - 2
        assert metrics.board_x >= 96


# ---------------------------------------------------------------------------
# Bölüm B — game_over_surfaces LRU + safe rect sözleşmeleri
# ---------------------------------------------------------------------------
class TestGameOverSurfacesContract:
    """Kare-başı tahsis yasağı: aynı key aynı Surface; kapasite sınırlı LRU."""

    def setup_method(self):
        _init_pygame()
        _clear_surface_caches()

    def test_solid_surface_is_cached_and_colored(self):
        first = get_solid_alpha_surface((10, 6), (1, 4, 14, 212))
        second = get_solid_alpha_surface((10, 6), (1, 4, 14, 212))
        assert first is second
        assert first.get_at((5, 3)) == (1, 4, 14, 212)

    def test_solid_surface_key_quantizes_inputs(self):
        first = get_solid_alpha_surface((10, 6), (1, 4, 14, 212))
        other_alpha = get_solid_alpha_surface((10, 6), (1, 4, 14, 211))
        other_size = get_solid_alpha_surface((11, 6), (1, 4, 14, 212))
        assert first is not other_alpha
        assert first is not other_size

    def test_rounded_rect_filled_vs_outline(self):
        filled = get_rounded_rect_surface((20, 20), (255, 0, 0, 200), 6, 0)
        outline = get_rounded_rect_surface((20, 20), (255, 0, 0, 200), 6, 1)
        assert filled is not outline
        assert filled.get_at((10, 10))[3] == 200
        # Çerçeve genişliği 1: merkez çerçevenin içinde kalır (alpha 0).
        assert outline.get_at((10, 10))[3] == 0

    def test_circle_surface_center_filled_corner_empty(self):
        circle = get_circle_surface(8, (0, 255, 0, 90), 0)
        assert circle.get_at((8, 8))[3] == 90
        assert circle.get_at((0, 0))[3] == 0

    def test_card_tint_gradient_direction_and_winner_weight(self):
        winner = get_card_tint_surface((40, 40), (88, 226, 182), (255, 78, 112), True, 12)
        loser = get_card_tint_surface((40, 40), (88, 226, 182), (255, 78, 112), False, 12)
        assert winner is not loser
        # Status dolgusu (radius 12) merkezi kaplar: kazayan kartta taban alfası
        # 8, kazanan kartta 18'dir.
        assert winner.get_at((20, 20))[3] == 18
        assert loser.get_at((20, 20))[3] == 8
        # Degrade satırları radius dışı köşe kolonunda görünür: üst satır
        # alfası > alt satır alfası; kazanan tabanı (22) kaybedenden (12) yüksek.
        assert winner.get_at((0, 1))[3] > winner.get_at((0, 38))[3]
        assert winner.get_at((0, 1))[3] > loser.get_at((0, 1))[3]

    def test_custom_surface_identity_for_quantized_fade(self):
        def _build(fade_q):
            def _inner() -> pygame.Surface:
                surface = pygame.Surface((8, 8), pygame.SRCALPHA)
                surface.fill((18, 7, 14, int(240 * fade_q)))
                return surface
            return _inner

        first = get_custom_surface(("overlay", 8, 8, 0.5), _build(0.5))
        again = get_custom_surface(("overlay", 8, 8, 0.5), _build(0.5))
        other = get_custom_surface(("overlay", 8, 8, 0.75), _build(0.75))
        assert first is again
        assert first is not other

    def test_capacity_evicts_oldest_entries(self):
        for i in range(200):
            get_solid_alpha_surface((i + 1, 4), (1, 4, 14, 212))
        assert len(game_over_surfaces._SOLID_CACHE) <= game_over_surfaces._SURFACE_CACHE_MAX
        # İlk girdiler tahliye edildi.
        assert (1, 4, 1, 4, 14, 212) not in game_over_surfaces._SOLID_CACHE

    def test_render_safe_rect_offscreen_and_cached(self):
        offscreen = pygame.Surface((1920, 1080))
        safe = get_render_safe_rect(offscreen)
        assert safe == pygame.Rect(48, 27, 1824, 1026)
        assert get_render_safe_rect(offscreen) is safe

    def test_render_safe_rect_generation_cache(self):
        import platform_utils

        offscreen = pygame.Surface((1920, 1080))
        first = get_render_safe_rect(offscreen)
        # Geometri kuşağı ilerleyince önbellek yeniden hesaplar; testin
        # bıraktığı küresel canvas durumu geri alınır (sonraki dosyaların
        # platform_utils görünümünü kirletmemesi için).
        try:
            platform_utils._set_canvas_state(platform_utils.CANVAS_STATE_ACTIVE)
            second = get_render_safe_rect(offscreen)
        finally:
            platform_utils._set_canvas_state(platform_utils.CANVAS_STATE_INACTIVE)
        assert second is not None
        assert second == first  # plain geometri: alan aynı, nesne taze


# ---------------------------------------------------------------------------
# Bölüm C — S4: PvP game-over gerçek draw containment
# ---------------------------------------------------------------------------
def _make_pvp_result_game(size: tuple[int, int] = (1280, 720)) -> PvPGame:
    _init_pygame()
    game = PvPGame.__new__(PvPGame)
    game.screen = pygame.Surface(size)
    game.window_width, game.window_height = size
    game.player1_name = "Ada"
    game.player2_name = "Bora"
    game.board1 = Board()
    game.board2 = Board()
    game.board1.score = 48000
    game.board2.score = 35000
    game.board1.lines_cleared = 42
    game.board2.lines_cleared = 31
    game.winner = 1
    game.match_end_reason = "elimination"
    game.p1_eliminated = False
    game.p2_eliminated = True
    game._game_over_restart_rect = None
    game._game_over_menu_rect = None
    return game


class TestPvPGameOverContainment:
    """P0 PvP game-over: eylem rect'leri safe rect içinde ve disjoint.

    Tam paket zincirinde retro_style stub'lanmışsa (bilinen aile mayını)
    draw yolu çalışamaz; test skip edilir — tek dosya koşumunda gerçek
    doğrulama yapılır.
    """

    def setup_method(self):
        _init_pygame()
        _clear_surface_caches()

    def test_action_rects_inside_real_offscreen_safe_rect(self, monkeypatch):
        if not _retro_style_is_real(pvp_game_module):
            import pytest
            pytest.skip("retro_style stub kirliliği (tam paket mayını)")
        monkeypatch.setattr(pvp_game_module, "get_mouse_pos", lambda: (-9999, -9999))
        game = _make_pvp_result_game((1280, 720))

        game._draw_game_over_screen()

        safe = get_render_safe_rect(game.screen)
        assert safe is not None
        assert safe.contains(game._game_over_restart_rect)
        assert safe.contains(game._game_over_menu_rect)
        assert not game._game_over_restart_rect.colliderect(game._game_over_menu_rect)

    def test_action_rects_survive_asymmetric_safe_rect(self, monkeypatch):
        if not _retro_style_is_real(pvp_game_module):
            import pytest
            pytest.skip("retro_style stub kirliliği (tam paket mayını)")
        # Maksimum kenar kesmesi: safe alan 680x500 → panel + butonlar içeride.
        monkeypatch.setattr(pvp_game_module, "get_mouse_pos", lambda: (-9999, -9999))
        monkeypatch.setattr(
            pvp_game_module, "get_render_safe_rect",
            lambda screen: pygame.Rect(60, 50, 680, 500),
        )
        game = _make_pvp_result_game((800, 600))

        game._draw_game_over_screen()

        forced = pygame.Rect(60, 50, 680, 500)
        assert forced.contains(game._game_over_restart_rect)
        assert forced.contains(game._game_over_menu_rect)

    def test_overlay_surface_comes_from_lru(self, monkeypatch):
        if not _retro_style_is_real(pvp_game_module):
            import pytest
            pytest.skip("retro_style stub kirliliği (tam paket mayını)")
        # Kare-başı overlay tahsisi kalktı: aynı boyut iki draw → aynı Surface.
        monkeypatch.setattr(pvp_game_module, "get_mouse_pos", lambda: (-9999, -9999))
        game = _make_pvp_result_game((1280, 720))
        game._draw_game_over_screen()
        first_overlay = game_over_surfaces._SOLID_CACHE.get((1280, 720, 1, 4, 14, 212))
        game._draw_game_over_screen()
        second_overlay = game_over_surfaces._SOLID_CACHE.get((1280, 720, 1, 4, 14, 212))
        assert first_overlay is not None
        assert first_overlay is second_overlay


# ---------------------------------------------------------------------------
# Bölüm D — S4: Coop game-over gerçek draw containment
# ---------------------------------------------------------------------------
def _make_coop_result_game(size: tuple[int, int] = (1280, 720)) -> CoopGame:
    _init_pygame()
    game = CoopGame.__new__(CoopGame)
    game.screen = pygame.Surface(size)
    game.window_width, game.window_height = size
    game._game_over_snapshot = {
        "team_score": 1234,
        "total_lines": 40,
        "level": 3,
        "elapsed_ms": 65000,
        "p1_pct": 55,
        "p2_pct": 45,
        "p1_text": "P1 not",
        "p2_text": "P2 not",
    }
    game._game_over_start_time = 0
    game._game_over_peek_active = False
    game.user_manager = None
    game._game_over_restart_rect = None
    game._game_over_exit_rect = None
    return game


class TestCoopGameOverContainment:
    """P0 Coop game-over: restart/exit rect'leri safe rect içinde ve disjoint.

    PvP bölümündekiyle aynı retro_style stub koruması: tam paket
    zincirinde draw yolu çalışamazsa skip edilir.
    """

    def setup_method(self):
        _init_pygame()
        _clear_surface_caches()

    def test_action_rects_inside_real_offscreen_safe_rect(self, monkeypatch):
        if not _retro_style_is_real(coop_game_module):
            import pytest
            pytest.skip("retro_style stub kirliliği (tam paket mayını)")
        monkeypatch.setattr(coop_game_module, "get_mouse_pos", lambda: (9999, 9999))
        game = _make_coop_result_game((1280, 720))

        game._draw_game_over_screen()

        safe = get_render_safe_rect(game.screen)
        assert safe is not None
        assert safe.contains(game._game_over_restart_rect)
        assert safe.contains(game._game_over_exit_rect)
        assert not game._game_over_restart_rect.colliderect(game._game_over_exit_rect)

    def test_action_rects_survive_compact_viewport(self, monkeypatch):
        if not _retro_style_is_real(coop_game_module):
            import pytest
            pytest.skip("retro_style stub kirliliği (tam paket mayını)")
        monkeypatch.setattr(coop_game_module, "get_mouse_pos", lambda: (9999, 9999))
        game = _make_coop_result_game((800, 600))

        game._draw_game_over_screen()

        safe = get_render_safe_rect(game.screen)
        assert safe is not None
        assert safe.contains(game._game_over_restart_rect)
        assert safe.contains(game._game_over_exit_rect)

    def test_overlay_gradient_uses_quantized_custom_cache(self, monkeypatch):
        if not _retro_style_is_real(coop_game_module):
            import pytest
            pytest.skip("retro_style stub kirliliği (tam paket mayını)")
        # Dikey degrade karartması artık LRU'dan: fade kuantumları sınırlı yüzey.
        monkeypatch.setattr(coop_game_module, "get_mouse_pos", lambda: (9999, 9999))
        game = _make_coop_result_game((1280, 720))
        game._draw_game_over_screen()
        overlay_keys = [
            key for key in game_over_surfaces._CUSTOM_CACHE
            if key and key[0] == "coop_go_overlay"
        ]
        assert overlay_keys, "coop overlay LRU girdisi üretilmeli"
        # Fade 0.35 s'lik açılma + 12 adım kuantum → girdi sayısı sınırlı.
        assert len(overlay_keys) <= 13
