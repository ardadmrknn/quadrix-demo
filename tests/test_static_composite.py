# -*- coding: utf-8 -*-
"""PERF FAZ 1 — statik arka plan kompoziti piksel-parite testleri.

Kovuğu: 4K telemetri turunda (rapor §12, build 8c98923) her kare yeniden
blend edilen statik katmanlar karenin yarısını yiyordu:
  - draw_background_fill_ms p50 3.42 ms (fill + yarı-saydam tam ekran blit)
  - draw_outer_tint_ms     p50 1.00 ms (tam ekran SRCALPHA blit)
  - draw_board_base_ms     p50 1.26 ms (tahta dolgusu + bg + tint + overlay)
static_composite.draw_backdrop / blit_board_base bu dizileri girdiler
değişmedikçe bir kez kompozit yüzeyde birleştirir; kare başına tek opak blit
kalır. Blend sırası ve alfa değerleri üretim dizisiyle birebir aynıdır.

Sözleşmeler:
  1. Piksel-parite: kompozit yol, üretimdeki eski çizim dizisiyle byte
     düzeyinde aynı sonuç verir (aynı blend sırası + aynı alfa değerleri).
  2. Yeniden üretim yok: girdiler aynıysa kompozit cache'ten döner (LRU).
  3. Tazelik: set_transparency / load_image sonrası kompozit eski pikselleri
     servis ETMEZ.
  4. Tahta tabanı: dolgu + tahta arka planı + board tint + overlay tek
     kompozitte; grid ayrı blit kalır (kenar çizgileri tahta dışına 1px taşar).

Ortam: SDL dummy + gerçek BackgroundManager (tmp_path PNG) — mock yok.
"""

from __future__ import annotations

import os
import sys
from dataclasses import replace
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pygame
import pytest

import static_composite
from background import BackgroundManager
from mode_skins import (
    apply_board_tint,
    apply_outer_tint,
    draw_board_overlay,
    get_mode_skin,
)


W, H = 96, 64
FILL = (12, 16, 24)
TINT = (5, 8, 16, 60)

BW, BH = 48, 52
BOARD_TOPLEFT = (10, 8)
BOARD_FILL = (4, 4, 12)


def _init_display() -> None:
    pygame.init()
    if pygame.display.get_surface() is None:
        pygame.display.set_mode((W, H))


@pytest.fixture(autouse=True)
def _clean_display_and_caches():
    _init_display()
    static_composite.reset_caches()
    yield


def _pixels(surface: pygame.Surface) -> bytes:
    return pygame.image.tobytes(surface, "RGB")


def _save_test_image(tmp_path, name: str, base, accent) -> str:
    img = pygame.Surface((24, 16))
    img.fill(base)
    pygame.draw.rect(img, accent, (2, 2, 10, 6))
    path = tmp_path / name
    pygame.image.save(img, str(path))
    return str(path)


def _make_manager(tmp_path, transparency: float = 0.4,
                  base=(120, 40, 200), accent=(250, 250, 250)) -> BackgroundManager:
    mgr = BackgroundManager()
    assert mgr.load_image(_save_test_image(tmp_path, "bg.png", base, accent))
    mgr.set_transparency(transparency)
    return mgr


def _legacy_backdrop(screen: pygame.Surface, fill_color, bg: BackgroundManager, outer_tint) -> None:
    """game.py dış arka plan bloğunun (FAZ 1 öncesi üretim dizisi) birebir aynası
    (referans yol)."""
    bg_alpha = 1.0
    if bg.is_loaded():
        try:
            bg_alpha = float(getattr(bg, "transparency", 1.0))
        except Exception:
            bg_alpha = 1.0
        if bg_alpha < 1.0:
            screen.fill(fill_color)
        bg.draw_full_screen(screen)
    else:
        screen.fill(fill_color)
    if outer_tint is not None and len(outer_tint) >= 4 and outer_tint[3] > 0:
        tint_a = int(outer_tint[3] * bg_alpha) if bg_alpha < 1.0 else outer_tint[3]
        if tint_a > 0:
            skin = replace(get_mode_skin("classic"), outer_tint=(*outer_tint[:3], tint_a))
            apply_outer_tint(screen, skin)


@pytest.mark.parametrize(
    "transparency,tint",
    [
        (0.4, TINT),              # üretim durumu: yarı saydam bg + tint (en pahalı yol)
        (0.4, None),              # tint yok
        (1.0, TINT),              # opak bg (fill atlanan yol)
        (1.0, None),              # opak bg, tint yok
        (0.999, (0, 0, 0, 255)),  # sınır: alfa 254 + tam opak tint
    ],
)
def test_backdrop_pixel_parity(tmp_path, transparency, tint):
    bg = _make_manager(tmp_path, transparency=transparency)
    legacy = pygame.Surface((W, H))
    modern = pygame.Surface((W, H))
    # İki yola da aynı "önceki kare kalıntısı" ver: parite ekran geçmişine
    # bağlı olmamalı (kompozit opak blit, legacy fill/blend).
    legacy.fill((255, 0, 255))
    modern.fill((255, 0, 255))

    _legacy_backdrop(legacy, FILL, bg, tint)
    static_composite.draw_backdrop(modern, FILL, bg, tint)

    assert _pixels(legacy) == _pixels(modern)


@pytest.mark.parametrize("tint", [TINT, None])
def test_backdrop_pixel_parity_no_background_loaded(tint):
    bg = BackgroundManager()  # resim yüklenmemiş
    legacy = pygame.Surface((W, H))
    modern = pygame.Surface((W, H))
    legacy.fill((255, 0, 255))
    modern.fill((255, 0, 255))

    _legacy_backdrop(legacy, FILL, bg, tint)
    static_composite.draw_backdrop(modern, FILL, bg, tint)

    assert _pixels(legacy) == _pixels(modern)


def test_backdrop_composite_reused_between_calls(tmp_path):
    bg = _make_manager(tmp_path)
    first = pygame.Surface((W, H))
    second = pygame.Surface((W, H))

    static_composite.draw_backdrop(first, FILL, bg, TINT)
    entries = static_composite.backdrop_cache_size()
    assert entries == 1

    static_composite.draw_backdrop(second, FILL, bg, TINT)
    assert static_composite.backdrop_cache_size() == entries, \
        "aynı girdilerle ikinci çizim yeni kompozit ÜRETMEMELİ (cache hit)"


def test_backdrop_rebuilds_after_transparency_change(tmp_path):
    bg = _make_manager(tmp_path, transparency=0.4)
    legacy = pygame.Surface((W, H))
    modern = pygame.Surface((W, H))

    static_composite.draw_backdrop(modern, FILL, bg, TINT)
    _legacy_backdrop(legacy, FILL, bg, TINT)
    assert _pixels(legacy) == _pixels(modern)

    bg.set_transparency(0.85)
    _legacy_backdrop(legacy, FILL, bg, TINT)
    static_composite.draw_backdrop(modern, FILL, bg, TINT)
    assert _pixels(legacy) == _pixels(modern), \
        "transparanlık değişiminden sonra eski kompozit servis edilmemeli"


def test_background_full_screen_cache_refreshes_after_image_swap(tmp_path):
    """background.py sözleşmesi: aynı boyutta FARKLI resim yüklenince tam ekran
    cache'i bayat KALMAMALI (mevcut kod yalnız boyut anahtarına bakıyor)."""
    bg = BackgroundManager()
    assert bg.load_image(_save_test_image(tmp_path, "bg1.png", (120, 40, 200), (250, 250, 250)))
    bg.set_transparency(0.5)
    first = pygame.Surface((W, H))
    bg.draw_full_screen(first)

    assert bg.load_image(_save_test_image(tmp_path, "bg2.png", (30, 200, 90), (10, 10, 10)))
    second = pygame.Surface((W, H))
    bg.draw_full_screen(second)

    assert _pixels(second) != _pixels(first), \
        "resim değiştikten sonra tam ekran cache'i yeni resmi göstermeli"


def test_background_board_surface_refreshes_after_image_swap(tmp_path):
    """Tahta boyutlu arka plan yüzeyi de resim takasında tazelenmeli."""
    bg = BackgroundManager()
    assert bg.load_image(_save_test_image(tmp_path, "bg1.png", (120, 40, 200), (250, 250, 250)))
    bg.set_transparency(0.5)
    rect = pygame.Rect(0, 0, 40, 60)
    first = pygame.Surface((W, H))
    bg.draw(first, rect)

    assert bg.load_image(_save_test_image(tmp_path, "bg2.png", (30, 200, 90), (10, 10, 10)))
    second = pygame.Surface((W, H))
    bg.draw(second, rect)

    assert _pixels(second) != _pixels(first), \
        "resim değiştikten sonra tahta yüzeyi yeni resmi göstermeli"


def test_backdrop_rebuilds_after_image_swap(tmp_path):
    bg = _make_manager(tmp_path, transparency=0.5,
                       base=(120, 40, 200), accent=(250, 250, 250))
    legacy = pygame.Surface((W, H))
    modern = pygame.Surface((W, H))

    static_composite.draw_backdrop(modern, FILL, bg, TINT)
    _legacy_backdrop(legacy, FILL, bg, TINT)
    assert _pixels(legacy) == _pixels(modern)

    # Aynı boyutta FARKLI içerik: boyut anahtarı değişmediği için yalnız
    # nesil sayacı kompozitin tazelenmesini garantileyebilir.
    assert bg.load_image(_save_test_image(tmp_path, "bg_swap.png", (30, 200, 90), (10, 10, 10)))
    _legacy_backdrop(legacy, FILL, bg, TINT)
    static_composite.draw_backdrop(modern, FILL, bg, TINT)
    assert _pixels(legacy) == _pixels(modern), \
        "resim takasından sonra eski kompozit servis edilmemeli"


# --- Tahta tabanı (blit_board_base) -----------------------------------------


def _board_skin(variant: str):
    """Üretimdeki çeşitli mod skin'lerini temsil eden tahta skin varyantları."""
    base = get_mode_skin("classic")
    if variant == "tintli":
        return replace(base, board_tint=(20, 30, 60, 70))
    if variant == "scan-overlay":
        return replace(base, board_tint=(8, 12, 30, 40), overlay="scan",
                       overlay_colors=((255, 255, 255, 40), (200, 220, 255, 30)),
                       overlay_alpha=90)
    if variant == "speed-overlay":
        return replace(base, overlay="speed",
                       overlay_colors=((255, 120, 40, 60),), overlay_alpha=60)
    return base


def _legacy_board_base(screen, topleft, board_size, fill, bg, skin) -> None:
    """game.py tahta taban bloğunun (FAZ 1 öncesi üretim dizisi) birebir aynası
    (referans yol).

    Grid bilinçli olarak dahil DEĞİL: üretimde ayrı cache'li blit'tir ve
    tahta dışına 1px taşar.
    """
    rect = pygame.Rect(topleft, board_size)
    pygame.draw.rect(screen, fill, rect)
    if bg is not None:
        bg.draw(screen, rect)
    apply_board_tint(screen, rect, skin)
    draw_board_overlay(screen, rect, skin)


@pytest.mark.parametrize(
    "transparency,skin_variant",
    [
        (0.4, "classic-ham"),
        (0.4, "tintli"),
        (0.4, "scan-overlay"),
        (0.4, "speed-overlay"),
        (1.0, "scan-overlay"),
        (None, "tintli"),        # arka plan yok: yalnız dolgu + tint + overlay
        (None, "classic-ham"),
    ],
)
def test_board_base_pixel_parity(tmp_path, transparency, skin_variant):
    bg = None if transparency is None else _make_manager(tmp_path, transparency=transparency)
    skin = _board_skin(skin_variant)
    legacy = pygame.Surface((W, H))
    modern = pygame.Surface((W, H))
    # Her iki yola da aynı "önceki kare kalıntısı" ver (parite geçmişe bağlı olmamalı).
    legacy.fill((0, 255, 255))
    modern.fill((0, 255, 255))

    _legacy_board_base(legacy, BOARD_TOPLEFT, (BW, BH), BOARD_FILL, bg, skin)
    static_composite.blit_board_base(
        modern, BOARD_TOPLEFT, (BW, BH), BOARD_FILL, bg, skin)

    assert _pixels(legacy) == _pixels(modern)


def test_board_base_composite_reused_between_calls(tmp_path):
    bg = _make_manager(tmp_path)
    skin = _board_skin("scan-overlay")

    static_composite.blit_board_base(
        pygame.Surface((W, H)), BOARD_TOPLEFT, (BW, BH), BOARD_FILL, bg, skin)
    entries = static_composite.board_base_cache_size()
    assert entries == 1

    static_composite.blit_board_base(
        pygame.Surface((W, H)), (4, 4), (BW, BH), BOARD_FILL, bg, skin)
    assert static_composite.board_base_cache_size() == entries, \
        "aynı girdilerle ikinci çizim yeni kompozit ÜRETMEMELİ (pozisyon bağımsız)"


def test_board_base_rebuilds_after_skin_change(tmp_path):
    bg = _make_manager(tmp_path, transparency=0.4)
    legacy = pygame.Surface((W, H))
    modern = pygame.Surface((W, H))

    static_composite.blit_board_base(
        modern, BOARD_TOPLEFT, (BW, BH), BOARD_FILL, bg, _board_skin("classic-ham"))
    _legacy_board_base(legacy, BOARD_TOPLEFT, (BW, BH), BOARD_FILL, bg, _board_skin("classic-ham"))
    assert _pixels(legacy) == _pixels(modern)

    _legacy_board_base(legacy, BOARD_TOPLEFT, (BW, BH), BOARD_FILL, bg, _board_skin("tintli"))
    static_composite.blit_board_base(
        modern, BOARD_TOPLEFT, (BW, BH), BOARD_FILL, bg, _board_skin("tintli"))
    assert _pixels(legacy) == _pixels(modern), \
        "skin değişiminden sonra eski kompozit servis edilmemeli"


def test_board_base_rebuilds_after_image_swap(tmp_path):
    bg = _make_manager(tmp_path, transparency=0.5,
                       base=(120, 40, 200), accent=(250, 250, 250))
    legacy = pygame.Surface((W, H))
    modern = pygame.Surface((W, H))

    static_composite.blit_board_base(
        modern, BOARD_TOPLEFT, (BW, BH), BOARD_FILL, bg, _board_skin("tintli"))
    _legacy_board_base(legacy, BOARD_TOPLEFT, (BW, BH), BOARD_FILL, bg, _board_skin("tintli"))
    assert _pixels(legacy) == _pixels(modern)

    assert bg.load_image(_save_test_image(tmp_path, "bg_swap.png", (30, 200, 90), (10, 10, 10)))
    _legacy_board_base(legacy, BOARD_TOPLEFT, (BW, BH), BOARD_FILL, bg, _board_skin("tintli"))
    static_composite.blit_board_base(
        modern, BOARD_TOPLEFT, (BW, BH), BOARD_FILL, bg, _board_skin("tintli"))
    assert _pixels(legacy) == _pixels(modern), \
        "resim takasından sonra eski tahta kompoziti servis edilmemeli"


def test_board_base_does_not_paint_outside_board_rect(tmp_path):
    """Grid ayrı blit olduğu için tahta tabanı kompoziti tahta rect'i DIŞINA
    piksel basmamalı (1px kenar taşması yalnız grid'e aittir)."""
    bg = _make_manager(tmp_path, transparency=0.4)
    screen = pygame.Surface((W, H))
    screen.fill((255, 0, 255))
    x, y = BOARD_TOPLEFT

    static_composite.blit_board_base(
        screen, BOARD_TOPLEFT, (BW, BH), BOARD_FILL, bg, _board_skin("scan-overlay"))

    outside = [
        (x - 1, y), (x, y - 1),                       # sol/üst komşu
        (x + BW, y), (x, y + BH),                     # sağ/alt komşu (grid 1px taşar)
        (x + BW, y + BH), (x - 1, y - 1),             # köşeler
    ]
    for px, py in outside:
        assert screen.get_at((px, py))[:3] == (255, 0, 255), \
            f"({px},{py}) tahta rect dışı piksel bozulmamalı"
