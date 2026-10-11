# -*- coding: utf-8 -*-
"""Statik katman kompoziti — PERF FAZ 1.

fill + tam ekran arka plan (yarı-saydam) + outer tint, üretimde her kare
yeniden blend ediliyordu (4K telemetri turu: kare p50 11.3 ms'in ~4.4 ms'i).
Bu modül aynı blend dizisini girdiler değişmedikçe BİR KEZ kompozit yüzeyde
birleştirir; kare başına tek opak blit kalır. Blend sırası ve alfa değerleri
eski yol ile birebir aynıdır — görsel sonuç piksel-birebir
(bkz. tests/test_static_composite.py).

Kare-başı tahsis yasağına uygunluk: kompozit yüzeyler yalnızca cache miss
anında üretilir; kare yolunda Surface tahsisi yoktur.
"""

from __future__ import annotations

from collections import OrderedDict

import pygame

from mode_skins import apply_board_tint, draw_board_overlay

_BACKDROP_CACHE: "OrderedDict[tuple, pygame.Surface]" = OrderedDict()
_BACKDROP_CACHE_MAX = 4
_BOARD_BASE_CACHE: "OrderedDict[tuple, pygame.Surface]" = OrderedDict()
_BOARD_BASE_CACHE_MAX = 4


def reset_caches() -> None:
    """Test/çözünürlük geçişi kancası: kompozit önbelleklerini boşalt."""
    _BACKDROP_CACHE.clear()
    _BOARD_BASE_CACHE.clear()


def backdrop_cache_size() -> int:
    return len(_BACKDROP_CACHE)


def board_base_cache_size() -> int:
    return len(_BOARD_BASE_CACHE)


def _convert_like_display(surface: pygame.Surface) -> pygame.Surface:
    """Display varsa yüzeyi display formatına çevir (hızlı opak blit).

    Display yoksa (headless) yüzey aynen döndürülür — background.py'deki
    guard'lı convert deseniyle aynı.
    """
    try:
        if pygame.display.get_surface() is not None:
            return surface.convert()
    except Exception:
        pass
    return surface


def _tint_overlay(size, tint_rgba) -> pygame.Surface:
    overlay = pygame.Surface(size, pygame.SRCALPHA)
    overlay.fill(tint_rgba)
    return overlay


def draw_backdrop(screen: pygame.Surface, fill_color, background_manager, outer_tint=None) -> None:
    """Tam ekran statik arka planı tek kompozit blit ile bas.

    Üretim dizisiyle birebir: (gerekirse) fill + outer_background.draw_full_screen
    + apply_outer_tint. Arka plan yüklenmemişse yalnız fill (+ varsa tint).
    outer_tint, üretimdeki gibi HAM skin tint'idir; alfa ölçeklemesi
    (bg_alpha ile) burada üretim mantığıyla birebir yapılır.
    """
    bg = background_manager
    loaded = bg is not None and bg.is_loaded() and bool(getattr(bg, "enabled", True))
    bg_alpha = 1.0
    if loaded:
        try:
            bg_alpha = float(getattr(bg, "transparency", 1.0))
        except Exception:
            bg_alpha = 1.0
    alpha_int = int(255 * max(0.0, min(1.0, bg_alpha)))

    tint = tuple(outer_tint) if outer_tint is not None else None
    if tint is not None and len(tint) >= 4 and tint[3] > 0:
        # FAZ 1 öncesi üretim mantığı: yarı saydam bg'de tint alfası
        # bg alfasıyla ölçeklenir; opak bg'de ham değer kullanılır.
        tint_a = int(tint[3] * bg_alpha) if bg_alpha < 1.0 else tint[3]
        tint = (*tint[:3], tint_a) if tint_a > 0 else None
    else:
        tint = None

    key = (screen.get_size(), tuple(fill_color), tint,
           id(bg) if loaded else None, alpha_int,
           getattr(bg, "_generation", 0) if loaded else 0)
    composite = _BACKDROP_CACHE.get(key)
    if composite is None:
        composite = pygame.Surface(screen.get_size())
        if not loaded or alpha_int < 255:
            # Üretim: yarı saydam bg önce temiz fill ister; yüklü olmayan
            # yolda fill tek başına çizilir. Opak bg'de (t=1.0) fill atlanır.
            composite.fill(fill_color)
        if loaded:
            # draw_full_screen ile aynı yüzey/blit; yalnızca hedef kompozit.
            composite.blit(bg.get_full_screen_surface(screen), (0, 0))
        if tint is not None:
            composite.blit(_tint_overlay(screen.get_size(), tint), (0, 0))
        composite = _convert_like_display(composite)
        _BACKDROP_CACHE[key] = composite
        while len(_BACKDROP_CACHE) > _BACKDROP_CACHE_MAX:
            _BACKDROP_CACHE.popitem(last=False)
    else:
        _BACKDROP_CACHE.move_to_end(key)

    screen.blit(composite, (0, 0))


def _bg_fingerprint(mgr) -> tuple | None:
    """Tahta arka planını içeriksel olarak tanımlayan anahtar parçası.

    Yüklü+etkin yönetici için (id, nesil, alfa) döndürür; yüklü değilse veya
    etkin değilse None (çizilen şey yok — sabit). Nesil sayacı (background.py)
    resim takası VE transparanlık değişiminde artar; enabled toggle'ı
    nesil artırmadığından parmak izinin None/val geçişi bunu kapsar.
    """
    if mgr is None or not mgr.is_loaded() or not bool(getattr(mgr, "enabled", True)):
        return None
    try:
        alpha = int(255 * max(0.0, min(1.0, float(getattr(mgr, "transparency", 1.0)))))
    except Exception:
        alpha = 255
    return (id(mgr), getattr(mgr, "_generation", 0), alpha)


def _board_skin_fingerprint(skin) -> tuple:
    """Tahta tabanı piksellerini belirleyen skin alanları (mode_skins.py anahtarlarıyla aynı)."""
    try:
        colors = tuple(tuple(c) for c in skin.overlay_colors)
    except Exception:
        colors = None
    return (tuple(skin.board_tint), str(skin.overlay), colors, int(skin.overlay_alpha))


def blit_board_base(screen: pygame.Surface, topleft, board_size, fill_color,
                    background_manager, board_skin) -> None:
    """Tahta tabanını (dolgu + tahta arka planı + board tint + overlay) tek
    kompozit blit ile bas.

    Üretim dizisiyle birebir (FAZ 1 öncesi tahta taban bloğu): rect dolgusu,
    draw_board_background'ın taban seçimi (background_manager.draw), apply_board_tint,
    draw_board_overlay. GRID bilinçli olarak hariçtir: üretimde ayrı cache'li
    blit'tir ve kenar çizgileri tahta dışına 1px taşar. Kompozit pozisyondan
    bağımsızdır (shake sadece topleft'i değiştirir, içeriği değil).
    """
    size = (int(board_size[0]), int(board_size[1]))
    bg = background_manager
    key = (size, tuple(fill_color), _bg_fingerprint(bg),
           _board_skin_fingerprint(board_skin))
    composite = _BOARD_BASE_CACHE.get(key)
    if composite is None:
        composite = pygame.Surface(size)
        pygame.draw.rect(composite, fill_color, composite.get_rect())
        if bg is not None and bg.is_loaded() and bool(getattr(bg, "enabled", True)):
            # draw_board_background taban yolu: draw() içsel boyut cache'i +
            # transparanlık alfasıyla (0,0)'a ölçekli blit.
            bg.draw(composite, (0, 0, size[0], size[1]))
        rect0 = pygame.Rect(0, 0, size[0], size[1])
        apply_board_tint(composite, rect0, board_skin)
        draw_board_overlay(composite, rect0, board_skin)
        composite = _convert_like_display(composite)
        _BOARD_BASE_CACHE[key] = composite
        while len(_BOARD_BASE_CACHE) > _BOARD_BASE_CACHE_MAX:
            _BOARD_BASE_CACHE.popitem(last=False)
    else:
        _BOARD_BASE_CACHE.move_to_end(key)

    screen.blit(composite, topleft)
