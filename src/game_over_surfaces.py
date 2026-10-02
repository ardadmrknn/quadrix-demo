# -*- coding: utf-8 -*-
"""FAZ A6 — game-over (P0) ekranlarının ortak yüzey önbellek kütüphanesi.

PvPGame / CoopGame / OnlinePvPGame Game sınıfından bağımsız sınıflar
olduğundan game.py'nin instance LRU helper'larını miras alamazlar; bu modül
aynı sözleşmeyi (ana döngüde kare-başı Surface tahsisi yasak, kapasite
sınırlı LRU, kuantize edilmiş key'ler) üç bağımsız sınıf için tek kaynak
olarak sunar — A5'in ui_text_layout.py ortak kütüphane kalıbının sürümü.

Kullanım notları:
- Boyut/renk değişiminde eski girdiler kapasite sınırından doğal olarak düşer;
  resolution geçişleri ek temizlik gerektirmez.
- get_render_safe_rect kuşak (geometry generation) bazlı önbellekle A1
  RenderGeometry.safe_rect döndürür; kare içi çağrılar tek hesaba iner.
"""

from __future__ import annotations

import pygame

try:
    from platform_utils import get_geometry_generation, get_render_geometry
except Exception:  # pragma: no cover - platform_utils her zaman mevcut olmalı
    get_geometry_generation = None
    get_render_geometry = None


_SURFACE_CACHE_MAX = 128
_SOLID_CACHE: dict[tuple, pygame.Surface] = {}
_SOLID_ORDER: list[tuple] = []
_ROUNDED_CACHE: dict[tuple, pygame.Surface] = {}
_ROUNDED_ORDER: list[tuple] = []
_CIRCLE_CACHE: dict[tuple, pygame.Surface] = {}
_CIRCLE_ORDER: list[tuple] = []
_TINT_CACHE: dict[tuple, pygame.Surface] = {}
_TINT_ORDER: list[tuple] = []
_CUSTOM_CACHE: dict[tuple, pygame.Surface] = {}
_CUSTOM_ORDER: list[tuple] = []

# Kuşak+boyut bazlı safe rect önbelleği (generation, screen size, safe_rect|None).
_SAFE_RECT_CACHE: tuple[int, tuple[int, int], pygame.Rect | None] | None = None


def _cache_surface(
    cache: dict[tuple, pygame.Surface],
    order: list[tuple],
    key: tuple,
    build,
) -> pygame.Surface:
    """Kapasite sınırlı LRU (FIFO tahliye) — game.py _solid_alpha_surface_cache kalıbı."""
    surface = cache.get(key)
    if surface is None:
        surface = build()
        cache[key] = surface
        order.append(key)
        while len(order) > _SURFACE_CACHE_MAX:
            cache.pop(order.pop(0), None)
    return surface


def get_solid_alpha_surface(size, rgba) -> pygame.Surface:
    """Doldurulmuş SRCALPHA yüzey: (w, h, r, g, b, a) key'li LRU."""
    key = (int(size[0]), int(size[1]), int(rgba[0]), int(rgba[1]), int(rgba[2]), int(rgba[3]))

    def _build() -> pygame.Surface:
        surface = pygame.Surface((key[0], key[1]), pygame.SRCALPHA)
        surface.fill(key[2:6])
        return surface

    return _cache_surface(_SOLID_CACHE, _SOLID_ORDER, key, _build)


def get_rounded_rect_surface(size, rgba, border_radius: int = 0, width: int = 0) -> pygame.Surface:
    """Dikdörtgen (opsiyonel yuvarlak köşe / çerçeve) yüzeyi: kare-başı tahsis yerine LRU."""
    key = (
        int(size[0]), int(size[1]),
        int(rgba[0]), int(rgba[1]), int(rgba[2]), int(rgba[3]),
        int(border_radius), max(0, int(width)),
    )

    def _build() -> pygame.Surface:
        surface = pygame.Surface((key[0], key[1]), pygame.SRCALPHA)
        pygame.draw.rect(
            surface, key[2:6], surface.get_rect(), key[7], border_radius=key[6],
        )
        return surface

    return _cache_surface(_ROUNDED_CACHE, _ROUNDED_ORDER, key, _build)


def get_circle_surface(radius: int, rgba, width: int = 0) -> pygame.Surface:
    """Daire (opsiyonel çerçeve) yüzeyi: (size, radius, rgba, width) key'li LRU."""
    radius = max(1, int(radius))
    width = max(0, int(width))
    size = radius * 2 + max(2, width * 2)
    key = (size, radius, int(rgba[0]), int(rgba[1]), int(rgba[2]), int(rgba[3]), width)

    def _build() -> pygame.Surface:
        surface = pygame.Surface((size, size), pygame.SRCALPHA)
        pygame.draw.circle(surface, key[2:6], (size // 2, size // 2), radius, width)
        return surface

    return _cache_surface(_CIRCLE_CACHE, _CIRCLE_ORDER, key, _build)


def get_card_tint_surface(size, accent, status_color, is_winner: bool, border_radius: int) -> pygame.Surface:
    """Oyuncu kartı dikey degrade tint'i — draw path'teki satır satır çizimden LRU'ya."""
    key = (
        int(size[0]), int(size[1]),
        int(accent[0]), int(accent[1]), int(accent[2]),
        int(status_color[0]), int(status_color[1]), int(status_color[2]),
        bool(is_winner), int(border_radius),
    )

    def _build() -> pygame.Surface:
        w, h = key[0], key[1]
        surface = pygame.Surface((w, h), pygame.SRCALPHA)
        base_alpha = 22 if key[8] else 12
        for y in range(h):
            ratio = y / max(1, h - 1)
            alpha = int(base_alpha * (1.0 - ratio * 0.55))
            pygame.draw.line(surface, (*key[2:5], alpha), (0, y), (w, y))
        pygame.draw.rect(
            surface, (*key[5:8], 18 if key[8] else 8), surface.get_rect(), border_radius=key[9],
        )
        return surface

    return _cache_surface(_TINT_CACHE, _TINT_ORDER, key, _build)


def get_custom_surface(key: tuple, build) -> pygame.Surface:
    """Çağırıcının kendi ürettiği karma yüzeyler için genel LRU girişi.

    key tüm girdileri (boyut + kuantize edilmiş dinamik parametreler)
    içermelidir; build yalnızca key ilk kez görüldüğünde çağrılır. Coop
    game-over'ın dikey degrade karartması (fade kuantumlu) ve panel tint'i
    bu giriş üzerinden kare-başı satır fill'lerinden kurtulur.
    """
    return _cache_surface(_CUSTOM_CACHE, _CUSTOM_ORDER, key, build)


def get_render_safe_rect(screen):
    """A1 RenderGeometry.safe_rect'i kuşak+boyut bazlı önbellekten pygame.Rect olarak döndür.

    Geometri yoksa / hesap başarısızsa None döner — çağıranlar tam-ekran
    clamp'e geri düşer (geriye dönük uyumlu).

    FAZ A6 düzeltmesi: cache anahtarı yalnızca geometry generation değil
    (generation, screen boyutu) ikilisidir. get_render_geometry(offscreen
    Surface) çağrının kendi boyutunu kullanır; generation yalnızca canvas
    state/backend geçişlerinde ilerler. Farklı boyutlu Surface'ler aynı
    kuşakta safe rect isterse (test zincirleri, çok-ekran draw'ları) tek
    boyutlu cache çapraz kirlilik üretiyordu — 1280x720 hesabı 4K çağrıya
    servis edilip panelleri ekran dışına taşıyordu.
    """
    global _SAFE_RECT_CACHE
    if get_geometry_generation is None or get_render_geometry is None:
        return None
    try:
        generation = get_geometry_generation()
        size = tuple(screen.get_size())
    except Exception:
        return None
    cached = _SAFE_RECT_CACHE
    if cached is not None and cached[0] == generation and cached[1] == size:
        return cached[2]
    safe_rect = None
    try:
        geometry = get_render_geometry(screen)
        sx0, sy0, sw, sh = geometry.safe_rect
        if sw > 0 and sh > 0:
            safe_rect = pygame.Rect(sx0, sy0, sw, sh)
    except Exception:
        safe_rect = None
    _SAFE_RECT_CACHE = (generation, size, safe_rect)
    return safe_rect


__all__ = [
    'get_card_tint_surface',
    'get_circle_surface',
    'get_custom_surface',
    'get_render_safe_rect',
    'get_rounded_rect_surface',
    'get_solid_alpha_surface',
]
