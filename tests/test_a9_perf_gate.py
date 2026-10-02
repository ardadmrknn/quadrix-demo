# -*- coding: utf-8 -*-
"""FAZ A9 — performans kapısı: steady-state draw yollarında kare-başı tahsis.

Gorsel_Olcek_Sorunlari_Cozum_Plani.md FAZ A9 madde 3'ün dummy-altı ayağı
(1080p + 4K sunum yolu):
  1. tracemalloc PEAK bütçesi: ısınmış (warm) draw karesinde Python-seviyesi
     tahsis piki — kare-başı string formatlama / dict-list üretimi / Rect
     spam buradan yakalanır (CLAUDE.md "Kare Başına Bellek Tahsisi Yasağı").
  2. gc Surface sayımı (census): ısınmış kareler boyunca yaşayan
     pygame.Surface sayısı ARTMAZ — kare-başı üretilip referansta tutulan
     (sızıntı) yüzeyler buradan yakalanır.
  3. LRU/cache giriş-dondurma: game_over_surfaces LRU'ları ve font
     cache'leri ısınmış kareler arasında YENİ giriş üretmez — cache'siz
     kalan yüzey yolu her karede yeni Surface üretiyor demektir.

Ölçüm sınırı (dürüst rapor): pygame'in C-taraflı piksel tamponları
tracemalloc'a görünmez; yalnız Python nesne başlıkları görünür. Geçici
(kare içinde üretilip bırakılan) Surface churn'u gc census'la da görünmez.
Bu yüzden yüzey yolları A6/A7 dosyalarındaki LRU kimlik testleriyle
(aynı key → aynı Surface NESNESİ) kilitlenir; bu dosya çöp/sızıntı/cache
üyeleri üzerinden kare-başı tahsis kapısını tutar. Gerçek donanım sunum
ölçümü (texture upload ms, present ms, QUADRIX_OVERLAY_PERF=1) kılavuzdaki
kullanıcı koşusuna aittir — dummy driver altında koşulamaz.

Kalıp: test_p0_screen_containment (retro_style stub mayını guard'ları) +
test_settings_preset_transition (settings kurulumu).
"""

from __future__ import annotations

import gc
import os
import pathlib
import sys
import tracemalloc

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import game_over_surfaces
import pvp_game as pvp_game_module
import coop_game as coop_game_module
from pvp_game import PvPGame
from coop_game import CoopGame
from board import Board
from settings_manager import SettingsManager
import settings_screen_tabbed
import platform_utils
from campaign.level_select import CampaignLevelSelect

import pytest


# ---------------------------------------------------------------------------
# Ortak yardımcılar
# ---------------------------------------------------------------------------
def _init_pygame() -> None:
    """Font/temel alt sistemleri hazırla; display surface AÇMA (p0 kalıbı)."""
    pygame.init()
    pygame.font.init()
    if not pygame.display.get_init():
        pygame.display.init()


def _retro_style_is_real(draw_module) -> bool:
    """Tam paket mayınına karşı koruma (test_p0 kalıbı): draw modülünün
    retro_style binding'i gerçek mi + cache'te ölü Font var mı?"""
    candidate = getattr(draw_module, 'retro_style', None)
    if not hasattr(candidate, 'wrap_text'):
        try:
            import retro_style as _rs_mod
            candidate = getattr(_rs_mod, 'retro_style', None)
        except Exception:
            return False
        if not hasattr(candidate, 'wrap_text'):
            return False
    try:
        for _probe_font in list(getattr(candidate, 'font_cache', {}).values()):
            _probe_font.size('')
            break
    except Exception:
        return False
    return True


def _alive_surface_count() -> int:
    """Yaşayan (referansta tutulan) pygame.Surface sayısı — sızıntı dedektörü."""
    gc.collect()
    return sum(1 for o in gc.get_objects() if type(o) is pygame.Surface)


def _lru_entry_counts() -> dict[str, int]:
    """game_over_surfaces LRU'larının toplam giriş sayısı (cache üyeyi)."""
    return {
        'solid': len(game_over_surfaces._SOLID_CACHE),
        'rounded': len(game_over_surfaces._ROUNDED_CACHE),
        'circle': len(game_over_surfaces._CIRCLE_CACHE),
        'tint': len(game_over_surfaces._TINT_CACHE),
        'custom': len(game_over_surfaces._CUSTOM_CACHE),
    }


def _font_cache_entry_count() -> int:
    """retro_style + UIFonts font cache toplam giriş sayısı (Font üyeyi)."""
    total = 0
    try:
        import retro_style as _rs
        inst = getattr(_rs, 'retro_style', None)
        total += len(getattr(inst, 'font_cache', {}) or {})
        total += len(getattr(_rs, '_cjk_fallback_font_cache', {}) or {})
    except Exception:
        pass
    try:
        from ui_theme import UIFonts
        total += len(UIFonts._cache)
    except Exception:
        pass
    return total


def _measure_steady_frame(draw_fn, warmup: int = 3):
    """Isınmış kareyi ölç: (peak_bytes, retained_bytes, surfaces_before,
    surfaces_after). tracemalloc PEAK'i kare içindeki toplam Python-seviyesi
    tahsisi verir (geçici dâhil); retained = kare sonunda elinde tutulan."""
    for _ in range(warmup):
        draw_fn()
    gc.collect()
    surfaces_before = _alive_surface_count()

    tracemalloc.start()
    tracemalloc.reset_peak()
    before_current, _ = tracemalloc.get_traced_memory()
    draw_fn()
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    gc.collect()
    surfaces_after = _alive_surface_count()
    retained = current - before_current
    return peak, retained, surfaces_before, surfaces_after


def _cleanup_canvas() -> None:
    try:
        platform_utils._teardown_virtual_canvas()
    except Exception:
        pass
    try:
        platform_utils._canvas_state = platform_utils.CANVAS_STATE_INACTIVE
        platform_utils._canvas_state_backend = None
    except Exception:
        pass
    try:
        from ui_scaling import set_ui_scale_preset
        set_ui_scale_preset('normal')
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Ekran kurulumları (p0/p1/settings kalıplarının A9 1080p uyarlaması)
# ---------------------------------------------------------------------------
def _make_pvp_result_game(size: tuple[int, int] = (1920, 1080)) -> PvPGame:
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


def _make_coop_result_game(size: tuple[int, int] = (1920, 1080)) -> CoopGame:
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
    # Fade/skor açılım animasyonu TAMAMLANMIŞ durumda kur (steady-state):
    # start=0 bırakılırsa ilk draw'da şimdiye resetlenir ve 0.35 s'lik
    # fade 12 adımlı kuantumu warmup boyunca ilerler — her yeni kuantum
    # yeni bir LRU girişi üretir (sınırlı animasyon tasarımı, p0'daki
    # "≤13 giriş" iddiası kapsar; kare-başı tahsis DEĞİLDİR). Perf kapısı
    # animasyon-sonrası rejimi ölçer: 10 s önce bitmiş kabul.
    game._game_over_start_time = pygame.time.get_ticks() - 10_000
    game._game_over_peek_active = False
    game.user_manager = None
    game._game_over_restart_rect = None
    game._game_over_exit_rect = None
    return game


# Bütçeler: ısınmış karede Python-seviyesi tahsis piki için üst sınırlar.
# Tek dosya koşumunda ölçülen değerler: pvp 10.9 KiB, coop 5.8 KiB,
# level select 12.1 KiB, 4K flip yolu < 1 KiB — bütçe ~10x ölçüm +
# platform farkı payı; amaç eşik geçmek değil, kare-başı megabayt-sınıfı
# gerilemeyi (string formatlama / dict-list spam / cache'siz yol) yakalamak.
# C-taraflı piksel tamponları tracemalloc'a görünmez — yüzey yolları A6/A7
# LRU kimlik testleriyle kilitlenir (modül docstring'ine bakınız).
_PEAK_BUDGET_BYTES = {
    'pvp_game_over': 128 * 1024,
    'coop_game_over': 128 * 1024,
    'settings_draw': 128 * 1024,
    'level_select_draw': 128 * 1024,
    'software_present_4k': 64 * 1024,
}


# ---------------------------------------------------------------------------
# Bölüm A — P0 game-over yolları (S4)
# ---------------------------------------------------------------------------
class TestPvPGameOverSteadyState:
    def setup_method(self):
        if not _retro_style_is_real(pvp_game_module):
            pytest.skip("retro_style stub kirliliği (tam paket mayını)")

    def test_no_per_frame_growth(self, monkeypatch):
        monkeypatch.setattr(pvp_game_module, "get_mouse_pos", lambda: (-9999, -9999))
        game = _make_pvp_result_game((1920, 1080))

        peak, retained, surf_before, surf_after = _measure_steady_frame(
            game._draw_game_over_screen,
        )
        # 1) Sızıntı yok: yaşayan Surface sayısı artmaz.
        assert surf_after <= surf_before, (
            f"Surface sızıntısı: {surf_before} -> {surf_after}"
        )
        # 2) Kare-başı Python tahsisi bütçe içinde.
        budget = _PEAK_BUDGET_BYTES['pvp_game_over']
        assert peak <= budget, (
            f"pvp game-over kare tahsis piki {peak} bayt > bütçe {budget}"
        )
        # 3) LRU üyeleri donar: ısınmış kareler yeni cache girişi üretmez.
        lru_before = _lru_entry_counts()
        game._draw_game_over_screen()
        game._draw_game_over_screen()
        lru_after = _lru_entry_counts()
        assert lru_after == lru_before, (
            f"kare-başı yeni LRU girişi: {lru_before} -> {lru_after}"
        )
        # 4) Font cache donar: yeni Font üretilmez.
        fonts_before = _font_cache_entry_count()
        game._draw_game_over_screen()
        fonts_after = _font_cache_entry_count()
        assert fonts_after == fonts_before, (
            f"kare-başı yeni Font: {fonts_before} -> {fonts_after}"
        )


class TestCoopGameOverSteadyState:
    def setup_method(self):
        if not _retro_style_is_real(coop_game_module):
            pytest.skip("retro_style stub kirliliği (tam paket mayını)")

    def test_no_per_frame_growth(self, monkeypatch):
        monkeypatch.setattr(coop_game_module, "get_mouse_pos", lambda: (9999, 9999))
        game = _make_coop_result_game((1920, 1080))

        peak, retained, surf_before, surf_after = _measure_steady_frame(
            game._draw_game_over_screen,
        )
        assert surf_after <= surf_before, (
            f"Surface sızıntısı: {surf_before} -> {surf_after}"
        )
        budget = _PEAK_BUDGET_BYTES['coop_game_over']
        assert peak <= budget, (
            f"coop game-over kare tahsis piki {peak} bayt > bütçe {budget}"
        )
        lru_before = _lru_entry_counts()
        game._draw_game_over_screen()
        game._draw_game_over_screen()
        lru_after = _lru_entry_counts()
        assert lru_after == lru_before, (
            f"kare-başı yeni LRU girişi: {lru_before} -> {lru_after}"
        )


# ---------------------------------------------------------------------------
# Bölüm B — settings ekranı (1920×1080 gerçek + 1.25 canvas)
# ---------------------------------------------------------------------------
class TestSettingsDrawSteadyState:
    def test_no_per_frame_growth(self, monkeypatch):
        if not _retro_style_is_real(settings_screen_tabbed):
            pytest.skip("retro_style stub kirliliği (tam paket mayını)")
        _init_pygame()
        pygame.display.set_mode((1920, 1080))
        try:
            platform_utils._teardown_virtual_canvas()
        except Exception:
            pass
        try:
            from ui_scaling import set_ui_scale_preset
            set_ui_scale_preset('large')
        except Exception:
            pass
        try:
            real = pygame.display.get_surface()
            canvas = platform_utils.setup_virtual_canvas(real, 1.25)
        except Exception as exc:
            _cleanup_canvas()
            pytest.skip(f"virtual canvas kurulamadı: {exc}")

        try:
            sm = SettingsManager()
            inst = settings_screen_tabbed.TabbedSettingsScreen(canvas, None, sm)
            calls: list = []
            inst._set_value = lambda key, value: calls.append((key, value))

            peak, retained, surf_before, surf_after = _measure_steady_frame(
                inst.draw,
            )
            assert surf_after <= surf_before, (
                f"Surface sızıntısı: {surf_before} -> {surf_after}"
            )
            budget = _PEAK_BUDGET_BYTES['settings_draw']
            assert peak <= budget, (
                f"settings draw kare tahsis piki {peak} bayt > bütçe {budget}"
            )
            fonts_before = _font_cache_entry_count()
            inst.draw()
            inst.draw()
            fonts_after = _font_cache_entry_count()
            assert fonts_after == fonts_before, (
                f"kare-başı yeni Font: {fonts_before} -> {fonts_after}"
            )
        finally:
            _cleanup_canvas()


# ---------------------------------------------------------------------------
# Bölüm C — level select (S7)
# ---------------------------------------------------------------------------
class TestLevelSelectSteadyState:
    def test_no_per_frame_growth(self):
        _init_pygame()
        screen = pygame.Surface((1920, 1080))
        try:
            selector = CampaignLevelSelect(screen)
        except Exception as exc:
            pytest.skip(f"level_select kurulamadı (kirli ortam): {exc}")
        # Katman-3 font mayını (p1 kalıbı): ölü Font → skip.
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

        peak, retained, surf_before, surf_after = _measure_steady_frame(
            selector.draw,
        )
        assert surf_after <= surf_before, (
            f"Surface sızıntısı: {surf_before} -> {surf_after}"
        )
        budget = _PEAK_BUDGET_BYTES['level_select_draw']
        assert peak <= budget, (
            f"level select kare tahsis piki {peak} bayt > bütçe {budget}"
        )
        fonts_before = _font_cache_entry_count()
        selector.draw()
        selector.draw()
        fonts_after = _font_cache_entry_count()
        assert fonts_after == fonts_before, (
            f"kare-başı yeni Font: {fonts_before} -> {fonts_after}"
        )


# ---------------------------------------------------------------------------
# Bölüm D — 4K software sunum yolu (letterbox blit cache)
# ---------------------------------------------------------------------------
class TestSoftwarePresent4KSteadyState:
    def test_flip_path_no_per_frame_allocation(self):
        _init_pygame()
        pygame.display.set_mode((3840, 2160))
        try:
            platform_utils._teardown_virtual_canvas()
        except Exception:
            pass
        try:
            real = pygame.display.get_surface()
            canvas = platform_utils.setup_virtual_canvas(real, 1.0)
        except Exception as exc:
            _cleanup_canvas()
            pytest.skip(f"4K virtual canvas kurulamadı: {exc}")

        try:
            assert canvas.get_size() == (1920, 1080)

            def _frame():
                canvas.fill((10, 10, 26))
                pygame.display.flip()  # _software_flip → letterbox blit + flip

            peak, retained, surf_before, surf_after = _measure_steady_frame(
                _frame, warmup=4,
            )
            assert surf_after <= surf_before, (
                f"flip yolu Surface sızıntısı: {surf_before} -> {surf_after}"
            )
            budget = _PEAK_BUDGET_BYTES['software_present_4k']
            assert peak <= budget, (
                f"4K flip kare tahsis piki {peak} bayt > bütçe {budget}"
            )
        finally:
            _cleanup_canvas()
