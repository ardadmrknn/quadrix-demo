# -*- coding: utf-8 -*-
"""Koyu blok/parça ve gölge için beyaz dış kontur sözleşmesi.

SORUN (kullanıcı, 2026-11-06): Renk seçicide renk SV karesinin alt/sağ
tarafına (koyulaşan bölge) yaklaştıkça blok rengi koyulaşıyor. Koyu blokta
oyun alanındaki parçanın YARI SAYDAM GÖLGESİ (ghost) neredeyse görünmüyor.
Kullanıcının çözüm kararı: renk koyulaştıkça bloğun/parçanın dış hattına
BEYAZ kontur çizilsin; gölgenin kenarları da beyaz olsun. Açık renklerde
görünüm DEĞİŞMEZ (mevcut neon kenar korunur).

Kılavuz bağı: DUZELTME_KILAVUZU_TR.md §2.5 "renk/outline kontrastı
[ERTELENEN]" (I-39) maddesi bu çalışmayla sanatsal karar olarak kapatılır;
`show_ghost` (I-19/K7) işlevsel sözleşmesi DEĞİŞMEZ — yalnız çizim stili.

Kilitlenen sözleşmeler:
1. `color_brightness` doygun renkleri doğru okur: saf kırmızı "koyu" sayılmaz,
   saf koyu mavi sayılır (Rec.709 luma tek başına yanıltıcıydı).
2. `dark_outline_alpha`: eşik üstü açık renk → 0; eşik altı koyu → 255;
   arası doğrusal geçiş (monoton azalan).
3. `draw_jelly_block` koyu renkte kontur çizer, açık renkte HİÇ çizmez
   (regresyon güvencesi: açık renkli karede piksel değişmez).
4. `draw_jelly_border` (doku üzerine kenar) da aynı konturu alır.
5. Gölge yolu (`draw_dark_block_outline` doğrudan çağrısı) koyu renkte
   beyaz kenar üretir; parça/ghost çizimlerinde kullanılır (game, coop,
   online pvp).
6. KARE BAŞINA TAHSİS YASAĞI: kontur yüzeyi LRU'dan gelir; aynı boyut/genişlik/
   alfa/yarıçap için ikinci çağrı YENİ Surface üretmez.
7. Küçük bloklar (< 4 px) ve görünmez alfa (0) güvenli: çizim yok, çökme yok.
"""
from __future__ import annotations

import os
import pathlib
import sys

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

import pygame

if not pygame.get_init():
    pygame.init()
if not pygame.display.get_init():
    pygame.display.init()
    pygame.display.set_mode((320, 240))

ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / 'src'
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import pytest

from renderers import jelly_renderer as jr


# ── 1) Parlaklık ölçütü ─────────────────────────────────────────────────────

def test_brightness_separates_saturated_from_dark_colors():
    """Doygun kırmızı koyu sayılmaz; koyu mavi sayılır."""
    # Rec.709 luma saf kırmızıda 54'tür — tek başına yanıltıcıydı.
    assert jr.color_luminance((255, 0, 0)) < 60
    assert jr.color_brightness((255, 0, 0)) > jr.OUTLINE_BRIGHTNESS_NONE

    assert jr.color_brightness((0, 0, 40)) < jr.OUTLINE_BRIGHTNESS_FULL
    assert jr.color_brightness((10, 10, 30)) < jr.OUTLINE_BRIGHTNESS_FULL


def test_brightness_monotonic_with_darkening():
    """Renk koyulaştıkça parlaklık artmaz (monotonluk)."""
    samples = [(255, 255, 255), (200, 200, 200), (140, 140, 140),
               (90, 90, 90), (50, 50, 50), (20, 20, 20), (0, 0, 0)]
    values = [jr.color_brightness(c) for c in samples]
    assert values == sorted(values, reverse=True), values


# ── 2) Kontur alfası eşikleri ───────────────────────────────────────────────

def test_outline_alpha_thresholds():
    """Açık renk → 0; koyu renk → tam; arası kısmi ve monoton."""
    assert jr.dark_outline_alpha((255, 255, 255)) == 0
    assert jr.dark_outline_alpha((255, 220, 0)) == 0        # parlak sarı
    assert jr.dark_outline_alpha((0, 0, 0)) == jr.OUTLINE_MAX_ALPHA
    assert jr.dark_outline_alpha((0, 0, 30)) == jr.OUTLINE_MAX_ALPHA

    mid = jr.dark_outline_alpha((70, 70, 70))
    assert 0 < mid < jr.OUTLINE_MAX_ALPHA, mid

    # Koyulaştıkça alfa artar (azalmaz).
    ramp = [(120, 120, 120), (100, 100, 100), (80, 80, 80),
            (60, 60, 60), (40, 40, 40)]
    alphas = [jr.dark_outline_alpha(c) for c in ramp]
    assert alphas == sorted(alphas), alphas


# ── 3-4) Renderer entegrasyonu: koyu çizer, açık çizmez ─────────────────────

def _surface(size=48):
    return pygame.Surface((size, size))


def test_dark_block_gets_white_outline_pixels():
    """Koyu renkli GÖLGE kutusunda dış hat beyaza yaklaşır."""
    surf = _surface()
    surf.fill((0, 0, 0))
    jr.draw_dark_block_outline(surf, 4, 4, 32, (0, 0, 40))
    edge = surf.get_at((4, 4))[:3]
    assert max(edge) > 120, f'kenar beyaz kontur beklenir, gelen {edge}'


def test_blocks_themselves_keep_their_neon_edge():
    """Blok GÖVDESİ kontur almaz — yalnız gölge alır (kullanıcı kararı).

    Regresyon kilidi: ilk uygulamada `draw_jelly_block` de kontur çiziyordu;
    kullanıcı bunu reddetti ("beyaz outline gölge odaklı olmalıydı").
    """
    surf = _surface()
    surf.fill((0, 0, 0))
    orig = jr.draw_dark_block_outline
    calls = []
    jr.draw_dark_block_outline = lambda *a, **k: calls.append(a) or True
    try:
        jr.draw_jelly_block(surf, 4, 4, 32, (0, 0, 40))
        jr.draw_jelly_border(surf, 4, 4, 32, (0, 0, 40))
    finally:
        jr.draw_dark_block_outline = orig
    assert calls == [], f'blok/doku yolu kontur ÇİZMEMELİ, çağrılar: {calls}'


def test_draw_dark_block_outline_returns_false_for_light_color():
    surf = _surface()
    surf.fill((0, 0, 0))
    assert jr.draw_dark_block_outline(surf, 0, 0, 32, (255, 240, 200)) is False
    assert surf.get_at((0, 0))[:3] == (0, 0, 0)


def test_border_path_does_not_add_outline():
    """Doku üzerine çizilen kenar yolu da BLOK gövdesidir → kontur almaz."""
    surf = _surface()
    surf.fill((0, 0, 0))
    calls = []
    orig = jr.draw_dark_block_outline
    jr.draw_dark_block_outline = lambda *a, **k: calls.append(a) or True
    try:
        jr.draw_jelly_border(surf, 4, 4, 32, (0, 0, 40))
    finally:
        jr.draw_dark_block_outline = orig
    assert calls == [], 'doku kenarı blok gövdesidir; gölge konturu çizmemeli'


# ── 5) Gölge: ÖLÇÜM GERÇEK EKRAN RENGİ ÜZERİNDEN ────────────────────────────

def test_composite_over_returns_real_screen_color():
    """Yarı saydam renk zeminle karışınca ekrandaki gerçek renk çıkar."""
    bg = (18, 20, 36)
    # %100 opak → rengin kendisi
    assert jr.composite_over((200, 100, 50), 255, bg) == (200, 100, 50)
    # %0 opak → zemin
    assert jr.composite_over((200, 100, 50), 0, bg) == bg
    mid = jr.composite_over((200, 100, 50), 128, bg)
    assert all(bg[i] <= mid[i] <= (200, 100, 50)[i] for i in range(3))


def test_ghost_of_bright_color_still_gets_outline():
    """KULLANICI BULGUSU: parlak renklerin gölgesi de kontur almalı.

    Ham renk parlaklığı eşiğin ÜSTÜNDE (kontur yok) ama ekranda yarı saydam
    çizildiği için KOYU görünüyor. Ölçüm `overlay_alpha`+`background` ile
    gerçek ekran rengi üzerinden yapılınca kontur çıkmalı.
    """
    bg = (18, 20, 36)
    bright_colors = [(76, 175, 80), (33, 150, 243), (244, 67, 54),
                     (255, 193, 7), (255, 152, 0), (0, 188, 212)]
    for c in bright_colors:
        # Ham renk üzerinden ölçüm: kontur YOK (eski, hatalı davranış)
        assert jr.dark_outline_alpha(c) == 0, f'{c} ham parlaklık eşik üstü olmalı'
        # Ekran rengi üzerinden ölçüm: kontur VAR (doğru davranış)
        screen_color = jr.composite_over(c, 50, bg)
        assert jr.dark_outline_alpha(screen_color) > 0, \
            f'{c} gölgesi ekranda {screen_color} görünüyor; kontur beklenir'

        surf = pygame.Surface((48, 48))
        surf.fill(bg)
        drew = jr.draw_dark_block_outline(
            surf, 4, 4, 32, c, overlay_alpha=50, background=bg)
        assert drew is True, f'{c} gölgesi için kontur çizilmeliydi'


def test_ghost_outline_can_be_softened_by_alpha_scale():
    """Kontur alfa ölçeğiyle yumuşatılabilir (isteğe bağlı ince ayar)."""
    surf = _surface()
    surf.fill((0, 0, 0))
    assert jr.draw_dark_block_outline(surf, 2, 2, 28, (0, 0, 30)) is True
    soft = pygame.Surface((48, 48))
    soft.fill((0, 0, 0))
    assert jr.draw_dark_block_outline(soft, 2, 2, 28, (0, 0, 30), alpha_scale=0.5) is True
    assert soft.get_at((2, 2))[:3] != (0, 0, 0)


# ── 6) Kare başına tahsis yasağı ────────────────────────────────────────────

def test_outline_surface_is_cached_no_per_frame_allocation():
    """Aynı parametreler ikinci çağrıda YENİ Surface üretmemeli."""
    surf = _surface()
    jr._OUTLINE_CACHE.clear()
    jr.draw_dark_block_outline(surf, 0, 0, 24, (0, 0, 30))
    first = jr._outline_surface(24, max(1, round(24 * 0.06)), 255, 0)
    count_after_first = len(jr._OUTLINE_CACHE)
    second = jr._outline_surface(24, max(1, round(24 * 0.06)), 255, 0)
    assert second is first, 'aynı anahtar aynı Surface nesnesini vermeli'
    assert len(jr._OUTLINE_CACHE) == count_after_first, 'önbellek büyümemeli'


def test_outline_cache_is_bounded():
    """Önbellek sınırsız büyümez (LRU tavanı)."""
    jr._OUTLINE_CACHE.clear()
    for size in range(8, 8 + jr._OUTLINE_CACHE_MAX + 20):
        jr._outline_surface(size, 2, 255, 0)
    assert len(jr._OUTLINE_CACHE) <= jr._OUTLINE_CACHE_MAX


# ── 7) Kenar durumlar ───────────────────────────────────────────────────────

def test_small_and_invisible_blocks_are_safe():
    surf = _surface()
    jr.draw_dark_block_outline(surf, 0, 0, 3, (0, 0, 0))       # < 4 px
    jr.draw_dark_block_outline(surf, 0, 0, 24, (0, 0, 0), alpha_scale=0.0)
    assert True  # çökme yok


def test_gameplay_and_overlay_modules_use_the_outline_helper():
    """Oyun içi ghost çizim yolları kontur yardımcısını ve GHOST_ALPHA'yı kullanır."""
    import re
    for name in ('game.py', 'coop_game.py', 'online_pvp_game.py'):
        source = (SRC_DIR / name).read_text(encoding='utf-8')
        assert 'draw_dark_block_outline' in source, f'{name} kontur yardımcısını kullanmalı'
        assert re.search(
            r'from renderers\.jelly_renderer import[\s\S]{0,200}?draw_dark_block_outline',
            source), f'{name} import satırı eksik'
        # Tek kaynak: gölge opaklığı GHOST_ALPHA sabitinden gelmeli, gömülü
        # sayı kalmamalı (canlı renklerin gölgesi gereksiz koyulaşmasın).
        assert 'GHOST_ALPHA' in source, f'{name} GHOST_ALPHA sabitini kullanmalı'


def test_ghost_alpha_keeps_live_colors_alive():
    """KULLANICI BULGUSU: canlı renklerin gölgesi gereksiz koyu OLMAMALI.

    %20 opaklıkta parlak sarı bile kahverengiye düşüyordu (%72 kayıp).
    GHOST_ALPHA bu kaybı makul sınırda tutmalı.
    """
    bg = (18, 20, 36)
    live_colors = [(255, 193, 7), (76, 175, 80), (0, 188, 212),
                   (244, 67, 54), (33, 150, 243)]
    for c in live_colors:
        original = jr.color_brightness(c)
        ghost = jr.color_brightness(jr.composite_over(c, jr.GHOST_ALPHA, bg))
        loss = (original - ghost) / original
        assert loss < 0.60, (
            f'{c}: gölge parlaklığı %{loss*100:.0f} kaybediyor; '
            f'canlı renkler cansız görünür'
        )


def test_ghost_alpha_matches_renderer_constant():
    """Gölge çiziminde kullanılan alfa tek kaynaktan gelir."""
    assert isinstance(jr.GHOST_ALPHA, int)
    assert 80 <= jr.GHOST_ALPHA <= 160, (
        f'GHOST_ALPHA {jr.GHOST_ALPHA} makul aralıkta olmalı (canlı ama görünür)')