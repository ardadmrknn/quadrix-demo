# -*- coding: utf-8 -*-
"""Çözünürlük x DPI x preset ölçek matrisi (kılavuz Bölüm 9 kabul kriterleri).

FAZ 6 test paketi — 4K_Sanal_Tuval_Uygulama_Kilavuzu.md Bölüm 8/FAZ 6.

Teknik: Ek B simülasyonu — SDL2-overlay patch taklidi + monkeypatch ile
zorlanan eff rejimleri. Surface çizimi yok; saf ölçek matematiği.

Ortam notu: bu dosya gerçek pygame de stub pygame de altında koşabilmelidir
(pytest süreç-içi modül durumu dosya sırasına bağlıdır — kılavuz 4.5/FAZ 6).
Bu yüzden pygame API'leri getattr fallback'leriyle kullanılır ve pygame.init
koşulludur. Zamanlama (ms) assert'i YAPILMAZ — flaky; kararlılık ve değer
eşitliği assert edilir.
"""
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import math
import sys
import types
import pathlib

import pytest

import pygame

ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
if str(ROOT_DIR / "src") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "src"))  # mevcut demo test konvansiyonu
import platform_utils
from ui_scaling import (
    apply_ui_scale_preset,
    get_scale,
    get_ui_scale_multiplier,
    get_ui_scale_preset,
    set_ui_scale_preset,
)
from gameplay_layout import get_display_pixel_ratio

# pygame.init yalnızca gerçek pygame'te anlamlıdır; stub'ta no-op/atlanır.
try:
    pygame.init()
    pygame.display.init()
except Exception:
    pass

CANVAS = (1920, 1080)
GAMEPLAY_UI_REFERENCE_SIZE = (1366.0, 768.0)


def _sdl2_sim(monkeypatch, canvas=CANVAS, dpi_scale=1.0):
    """SDL2 overlay kurulum-sonrası display sözleşmesini taklit et (Ek B).

    v1.1.1 (eleştirmen turu): 1-B yoklayıcısı ``sdl2_overlay`` modülünü
    sys.modules'ta arar — sahte modül KAYDEDİLMEDİKÇE yoklayıcı None döner,
    1-C early-return'leri hiç sınamaz ve testler yanlış nedenle geçer;
    ``_get_windows_window_scale_factor`` sabitlenmedikçe sonuç test makinesinin
    DPI'sına göre değişir. Bu yüzden (a) sahte modül kaydı, (b) DPI sabitleme.
    """
    game_surface = pygame.Surface(canvas, getattr(pygame, "SRCALPHA", 0))
    fake_overlay = types.SimpleNamespace(
        is_active=lambda: True,
        get_canvas_size=lambda: tuple(canvas),
    )
    monkeypatch.setitem(sys.modules, "sdl2_overlay", fake_overlay)
    monkeypatch.setattr(pygame.display, "get_surface", lambda: game_surface, raising=False)
    monkeypatch.setattr(pygame.display, "get_window_size", lambda: game_surface.get_size(), raising=False)
    monkeypatch.setattr(
        platform_utils, "_get_windows_window_scale_factor", lambda hwnd=None: dpi_scale
    )
    return game_surface


def _game_ui_scale_copy(eff, min_scale=0.72, max_scale=1.24):
    """game.py _ui_scale birebir kopyası (FAZ 4 sonrası: boost'suz).

    FAZ 4-A boost'u kaldırıldığından eff=3840 girdisi clamp üst sınırına
    oturur ve 1080p değeriyle eşit çıkar (9.1: 4K SDL2 = 1080p değerleri).
    """
    return apply_ui_scale_preset(
        get_scale(
            eff,
            min_scale=min_scale,
            max_scale=max_scale,
            reference_size=GAMEPLAY_UI_REFERENCE_SIZE,
        ),
        min_scale=min_scale,
        max_scale=max_scale,
    )


@pytest.mark.parametrize("dpi_scale", [1.0, 1.5])
def test_sdl2_eff_is_canvas(dpi_scale, monkeypatch):
    """FAZ 1 kabul: SDL2 aktifken eff == (1920, 1080), 300/300 çağrıda.

    En az bir varyant dpi_scale=1.5 ile koşar (K13): early-return'ün DPI
    bölme dalını yendiğini kanıtlar — %100'de geçen test bunu sınamaz.
    """
    surface = _sdl2_sim(monkeypatch, canvas=CANVAS, dpi_scale=dpi_scale)
    for _ in range(300):
        assert tuple(platform_utils.get_effective_ui_size(surface)) == CANVAS


def test_sdl2_eff_beats_dpi_division(monkeypatch):
    """FAZ 1-C kabul (v1.1.1): dpi_scale=1.5 zorlamasında eff == canvas.

    DPI bölme dalı erişilmez — Test 4 S3'ün karşıtı: 1-D sonrası
    fırtınasız SDL2 rejiminde bölme deterministik ateşlenirdi (1280,720);
    1-C early-return bölmeden ÖNCE geldiği için bu zincir kesilir.
    """
    surface = _sdl2_sim(monkeypatch, canvas=CANVAS, dpi_scale=1.5)
    assert tuple(platform_utils.get_effective_ui_size(surface)) == CANVAS


def test_gwls_no_recursion_tax(monkeypatch):
    """FAZ 1-C/1-D kabul: çifte patch altında 300 çağrının TÜMÜ (1920, 1080)
    döner; RecursionError yükselmez.

    Çifte patch topolojisi üretim sırasını izler: önce SDL2-sim display
    patch'leri (_sdl2_sim), sonra patch_event_queue. Eski koddaki
    _patched_display_get_window_size gövdesi get_presentation_info() dict'iyle
    çağrı başına tahsis üretirdi; yeni gövde yoklayıcıyı kullanır ve
    get_window_logical_size'i ASLA çağırmaz (v2 K1/K11 karşılıklı recursion
    lotaryası buradan doğardı).
    """
    _sdl2_sim(monkeypatch, canvas=CANVAS, dpi_scale=1.0)

    # patch_event_queue sessiz no-op'lara karşı ön koşulları garanti et
    monkeypatch.setattr(platform_utils, "IS_MACOS", False)
    if platform_utils._event_patch_active:
        platform_utils.unpatch_event_queue()
    if not hasattr(pygame, "event") or not hasattr(pygame.event, "get"):
        monkeypatch.setattr(
            pygame, "event",
            types.SimpleNamespace(get=lambda *a, **k: [], post=lambda e: None),
            raising=False,
        )
    if not hasattr(pygame, "mouse") or not hasattr(pygame.mouse, "get_pos"):
        monkeypatch.setattr(
            pygame, "mouse",
            types.SimpleNamespace(
                get_pos=lambda: (0, 0),
                get_rel=lambda: (0, 0),
                set_pos=lambda *a, **k: None,
            ),
            raising=False,
        )

    platform_utils.patch_event_queue()
    try:
        for _ in range(300):
            assert tuple(platform_utils.get_window_logical_size()) == CANVAS
            # Patch'li get_window_size 1-D gövdesini doğrudan sınar:
            assert tuple(pygame.display.get_window_size()) == CANVAS
    finally:
        platform_utils.unpatch_event_queue()


@pytest.mark.parametrize("preset", ["normal", "large", "double"])
def test_4k_equals_1080p_scales(preset):
    """FAZ 4 kabul: eff=3840 zorlanınca game _ui_scale 1.24 x preset'i AŞMAZ.

    Boost (RN-003) kalktığından 4K girdisi clamp üst sınırına oturur ve
    1080p değeriyle eşit çıkar — 9.1: 1080p 1.240 / 4K 1.240 (2.480 YASAK).
    """
    previous = get_ui_scale_preset()
    try:
        set_ui_scale_preset(preset)
        max_allowed = 1.24 * get_ui_scale_multiplier() + 1e-9
        for eff in [(1920, 1080), (3840, 2160), (2560, 1440)]:
            assert _game_ui_scale_copy(eff) <= max_allowed
        assert math.isclose(
            _game_ui_scale_copy((1920, 1080)),
            _game_ui_scale_copy((3840, 2160)),
        )
    finally:
        set_ui_scale_preset(previous)


def test_pixel_ratio_uses_raw_projection():
    """FAZ 4-B kabul: canvas 1920 / eff 3840 zorlamasında oran 0.5'te kalır.

    get_display_pixel_ratio (gameplay_layout.py:36-51) [0.5, 4.0] güvenlik
    aralığını zaten uygular; tüketicilerdeki max(1.0, ...) clamp'i (RN-004)
    kaldırıldı — ham projeksiyon değeri korunur.
    """
    assert get_display_pixel_ratio((1920, 1080), (3840, 2160)) == 0.5
    assert get_display_pixel_ratio((1920, 1080), (1920, 1080)) == 1.0


def test_right_hud_panel_width_defined():
    """DUZ-001 kabul: _draw_right_hud_panel panel_width'i panel_rect'ten türeir.

    Eski koddaki NameError (panel_width yerel tanımı yoktu) sadece panel
    çizim yolunda patlardı; bu test türetimin varlığını kaynak düzeyinde
    sabitler — gerçek çizim doğrulaması manuel matriste (9.2) kalır.
    """
    game_path = ROOT_DIR / "src" / "game.py"
    text = game_path.read_text(encoding="utf-8")
    assert "panel_width = panel_rect.width" in text, (
        "DUZ-001: game.py _draw_right_hud_panel panel_width türetimi eksik"
    )
