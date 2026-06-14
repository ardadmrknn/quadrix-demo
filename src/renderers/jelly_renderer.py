"""Shared jelly/glass block renderer for neon look.

This helper provides a single consistent visual for 'jelly' blocks used in game
and PvP modes. It intentionally draws highlight/shadow layers and a soft
inner shine. It does not handle texture-backed rendering; textured blocks are
intentionally drawn by the renderer which can preserve the slicing logic in
`game.py` while still drawing a complementing border.
"""
from __future__ import annotations

import pygame
from typing import Tuple
from collections import OrderedDict

try:
    from ..block_skin_assets import (  # type: ignore
        LEGACY_BLOCK_APPEARANCE,
        MODERN_BLOCK_APPEARANCE,
        appearance_for_block_skin,
    )
except Exception:
    from block_skin_assets import (  # type: ignore
        LEGACY_BLOCK_APPEARANCE,
        MODERN_BLOCK_APPEARANCE,
        appearance_for_block_skin,
    )

Color = Tuple[int, int, int]

# LRU cache for pre-rendered jelly block surfaces.
# Key: (size, color_r, color_g, color_b)  Value: pygame.Surface
_JELLY_BLOCK_CACHE: OrderedDict[tuple, pygame.Surface] = OrderedDict()
_JELLY_BLOCK_CACHE_MAX = 128


def _render_jelly_block_surface(size: int, color: Color) -> pygame.Surface:
    """Render a jelly block onto a new surface (internal, used by cache)."""
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    _draw_jelly_block_onto(surf, 0, 0, size, color)
    return surf


def _normalize_appearance(appearance: str | None) -> str:
    resolved = appearance_for_block_skin(appearance)
    if resolved == LEGACY_BLOCK_APPEARANCE:
        return LEGACY_BLOCK_APPEARANCE
    return MODERN_BLOCK_APPEARANCE


def _render_block_surface(size: int, color: Color, appearance: str | None) -> pygame.Surface:
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    _draw_jelly_block_onto(surf, 0, 0, size, color, appearance=appearance)
    return surf


def draw_jelly_block(
    screen: pygame.Surface,
    x: int,
    y: int,
    size: int,
    color: Color,
    *,
    appearance: str | None = None,
) -> None:
    """Draw a glassy "jelly" block onto the given surface (cached).

    Parameters:
        screen: pygame Surface to draw onto.
        x, y: top-left pixel coordinates.
        size: width/height in pixels.
        color: RGB color tuple, 0-255.
    """
    appearance_key = _normalize_appearance(appearance)
    key = (appearance_key, size, color[0], color[1], color[2])
    cached = _JELLY_BLOCK_CACHE.get(key)
    if cached is not None:
        _JELLY_BLOCK_CACHE.move_to_end(key)
        screen.blit(cached, (x, y))
        return
    surf = _render_block_surface(size, color, appearance_key)
    _JELLY_BLOCK_CACHE[key] = surf
    _JELLY_BLOCK_CACHE.move_to_end(key)
    while len(_JELLY_BLOCK_CACHE) > _JELLY_BLOCK_CACHE_MAX:
        _JELLY_BLOCK_CACHE.popitem(last=False)
    screen.blit(surf, (x, y))


def _clamp_color(r: float, g: float, b: float) -> Color:
    return (
        max(0, min(255, int(r))),
        max(0, min(255, int(g))),
        max(0, min(255, int(b))),
    )


def _draw_jelly_block_onto(
    screen: pygame.Surface,
    x: int,
    y: int,
    size: int,
    color: Color,
    *,
    appearance: str | None = None,
) -> None:
    appearance_key = _normalize_appearance(appearance)
    if appearance_key == LEGACY_BLOCK_APPEARANCE:
        _draw_legacy_jelly_block_onto(screen, x, y, size, color)
        return
    _draw_modern_jelly_block_onto(screen, x, y, size, color)


def _draw_modern_jelly_block_onto(screen: pygame.Surface, x: int, y: int, size: int, color: Color) -> None:
    """Draw the actual jelly block layers (no caching).

    Produces a sharp-cornered "lit tech glass" block: a low-contrast vertical
    depth gradient body, a thin top sheen, a measured bottom inner shadow and a
    crisp neon edge in the block's own brightened tone. No rounded corners.
    Everything scales with ``size`` and stays deterministic so the LRU cache
    remains valid.
    """
    base_color = _clamp_color(color[0] * 1.04, color[1] * 1.04, color[2] * 1.04)

    # Cok kucuk bloklarda (next/hold onizleme, parcacik vb.) katmanlar bozulur;
    # basit dolu kare guvenli fallback'tir.
    if size < 6:
        pygame.draw.rect(screen, base_color, (x, y, size, size))
        return

    # Koyu/doygun renkler icin minimum kontrast garantisi (orijinal davranis korunur).
    avg_brightness = sum(base_color) / 3
    min_highlight_add = max(28, int(70 - avg_brightness * 0.3))

    # --- Govde: dusuk kontrastli dikey derinlik gradyani (ust hafif aydinlik -> alt hafif koyu) ---
    top_color = _clamp_color(
        max(base_color[0] * 1.10, base_color[0] + min_highlight_add * 0.35),
        max(base_color[1] * 1.10, base_color[1] + min_highlight_add * 0.35),
        max(base_color[2] * 1.10, base_color[2] + min_highlight_add * 0.35),
    )
    bottom_color = _clamp_color(base_color[0] * 0.80, base_color[1] * 0.80, base_color[2] * 0.80)

    # Keskin kareli govde (yuvarlatma maskesi YOK).
    block = pygame.Surface((size, size), pygame.SRCALPHA)
    span = max(1, size - 1)
    for row in range(size):
        t = row / span
        line_color = (
            int(top_color[0] + (bottom_color[0] - top_color[0]) * t),
            int(top_color[1] + (bottom_color[1] - top_color[1]) * t),
            int(top_color[2] + (bottom_color[2] - top_color[2]) * t),
            255,
        )
        pygame.draw.line(block, line_color, (0, row), (size, row))

    # --- Ust sheen: ince, dusuk alpha'li cam parlama ipucu (seker bandi degil) ---
    sheen_h = max(1, int(size * 0.20))
    if sheen_h >= 1:
        sheen = pygame.Surface((size, sheen_h), pygame.SRCALPHA)
        sheen_alpha = 55
        sheen_span = max(1, sheen_h - 1)
        for row in range(sheen_h):
            gt = row / sheen_span
            a = int(sheen_alpha * (1.0 - gt) ** 1.6)
            if a <= 0:
                continue
            pygame.draw.line(sheen, (255, 255, 255, a), (0, row), (size, row))
        block.blit(sheen, (0, 0))

    # --- Alt ic golge: derinlik icin olculu, keskin kareli koyulasma ---
    shade_h = max(1, int(size * 0.32))
    if shade_h >= 1:
        shade = pygame.Surface((size, shade_h), pygame.SRCALPHA)
        shade_span = max(1, shade_h - 1)
        for i in range(shade_h):
            row = shade_h - 1 - i
            st = i / shade_span
            a = int(60 * (1.0 - st) ** 1.6)
            if a <= 0:
                continue
            pygame.draw.line(shade, (0, 0, 0, a), (0, row), (size, row))
        block.blit(shade, (0, size - shade_h))

    # --- Net neon kenar: keskin koseli, blok renginin parlatilmis tonu (ana tech vurgu) ---
    neon = _clamp_color(base_color[0] * 1.5 + 30, base_color[1] * 1.5 + 30, base_color[2] * 1.5 + 30)
    edge_w = max(1, round(size * 0.05))
    pygame.draw.rect(block, neon, (0, 0, size, size), width=edge_w)
    # Ust kenarda ekstra ince parlak rim (cam agzi) - keskin koseli.
    if size >= 10:
        rim = _clamp_color(neon[0] + 40, neon[1] + 40, neon[2] + 40)
        inset = max(1, edge_w)
        pygame.draw.line(block, rim, (edge_w, inset), (size - edge_w - 1, inset), 1)

    screen.blit(block, (x, y))


def _draw_legacy_jelly_block_onto(screen: pygame.Surface, x: int, y: int, size: int, color: Color) -> None:
    """Pre-2026 square glossy block variant used by the legacy store cosmetic."""
    base_color = _clamp_color(color[0] * 1.05, color[1] * 1.05, color[2] * 1.05)

    if size < 6:
        pygame.draw.rect(screen, base_color, (x, y, size, size))
        return

    avg_brightness = sum(base_color) / 3
    min_highlight_add = max(35, int(80 - avg_brightness * 0.3))
    min_shadow_sub = max(25, int(60 - avg_brightness * 0.2))

    pygame.draw.rect(screen, base_color, (x, y, size, size))

    inner_margin = max(1, size // 12)
    gradient_steps = 7
    for index in range(gradient_steps):
        progress = index / gradient_steps
        shade_factor = 1 - (progress * 0.18)
        shade_color = tuple(max(0, int(channel * shade_factor)) for channel in base_color[:3])
        margin = int(inner_margin * (0.5 + index * 0.3))
        rect_size = size - 2 * margin
        if rect_size > 0:
            pygame.draw.rect(screen, shade_color, (x + margin, y + margin, rect_size, rect_size), 1)

    highlight_thickness = max(2, size // 8)
    outer_highlight = tuple(min(255, max(int(channel * 1.4), channel + min_highlight_add)) for channel in base_color[:3])
    pygame.draw.line(screen, outer_highlight, (x, y), (x + size - 1, y), highlight_thickness)
    pygame.draw.line(screen, outer_highlight, (x, y), (x, y + size - 1), highlight_thickness)

    mid_highlight = tuple(min(255, max(int(channel * 1.65), channel + min_highlight_add + 15)) for channel in base_color[:3])
    mid_thickness = max(1, highlight_thickness // 2)
    pygame.draw.line(screen, mid_highlight, (x + 1, y + 1), (x + size - 2, y + 1), mid_thickness)
    pygame.draw.line(screen, mid_highlight, (x + 1, y + 1), (x + 1, y + size - 2), mid_thickness)

    inner_highlight = tuple(min(255, max(int(channel * 1.9), channel + min_highlight_add + 30)) for channel in base_color[:3])
    pygame.draw.line(screen, inner_highlight, (x + 2, y + 2), (x + size - 3, y + 2), 1)
    pygame.draw.line(screen, inner_highlight, (x + 2, y + 2), (x + 2, y + size - 3), 1)

    shadow_thickness = max(2, size // 8)
    outer_shadow = tuple(max(0, min(int(channel * 0.45), channel - min_shadow_sub)) for channel in base_color[:3])
    pygame.draw.line(screen, outer_shadow, (x + 1, y + size - 1), (x + size - 1, y + size - 1), shadow_thickness)
    pygame.draw.line(screen, outer_shadow, (x + size - 1, y + 1), (x + size - 1, y + size - 1), shadow_thickness)

    mid_shadow = tuple(max(0, min(int(channel * 0.30), channel - min_shadow_sub - 10)) for channel in base_color[:3])
    mid_shadow_thickness = max(1, shadow_thickness // 2)
    pygame.draw.line(screen, mid_shadow, (x + 2, y + size - 2), (x + size - 3, y + size - 2), mid_shadow_thickness)
    pygame.draw.line(screen, mid_shadow, (x + size - 2, y + 2), (x + size - 2, y + size - 3), mid_shadow_thickness)

    inner_shadow = tuple(max(0, min(int(channel * 0.20), channel - min_shadow_sub - 20)) for channel in base_color[:3])
    pygame.draw.line(screen, inner_shadow, (x + 3, y + size - 3), (x + size - 4, y + size - 3), 1)
    pygame.draw.line(screen, inner_shadow, (x + size - 3, y + 3), (x + size - 3, y + size - 4), 1)

    shine_size = max(4, size // 4)
    shine_offset = max(3, highlight_thickness + 1)
    outer_halo = tuple(min(255, max(int(channel * 1.6), channel + min_highlight_add + 20)) for channel in base_color[:3])
    pygame.draw.rect(screen, outer_halo, (x + shine_offset - 1, y + shine_offset - 1, shine_size + 3, shine_size + 3))

    mid_shine = tuple(min(255, max(int(channel * 1.95), channel + min_highlight_add + 40)) for channel in base_color[:3])
    pygame.draw.rect(screen, mid_shine, (x + shine_offset, y + shine_offset, shine_size + 1, shine_size + 1))

    inner_shine = tuple(min(255, int(channel * 2.3 + 60)) for channel in base_color[:3])
    pygame.draw.rect(screen, inner_shine, (x + shine_offset + 1, y + shine_offset + 1, max(2, shine_size - 1), max(2, shine_size - 1)))

    core_x = x + shine_offset + max(1, shine_size // 3)
    core_y = y + shine_offset + max(1, shine_size // 3)
    core_size = max(1, shine_size // 2)
    core_shine = tuple(min(255, channel + 120) for channel in base_color[:3])
    pygame.draw.rect(screen, core_shine, (core_x, core_y, core_size, core_size))

    if size > 15:
        reflection_size = max(1, size // 8)
        reflection_x = x + size - shine_offset - reflection_size - 2
        reflection_y = y + size - shine_offset - reflection_size - 2
        reflection_color = tuple(min(255, int(channel * 1.3)) for channel in base_color[:3])
        pygame.draw.rect(screen, reflection_color, (reflection_x, reflection_y, reflection_size, reflection_size))


def draw_jelly_border(
    screen: pygame.Surface,
    x: int,
    y: int,
    size: int,
    color: Color,
    *,
    appearance: str | None = None,
) -> None:
    """Draw a consistent inner/outer border complementing the jelly style.

    Used when a textured cell is blitted instead of the programmatic base.
    The interior is intentionally left untouched so the texture stays visible;
    only the sharp-cornered neon-tinted frame is drawn so textured and
    programmatic blocks share the same crisp silhouette.
    """
    appearance_key = _normalize_appearance(appearance)
    if appearance_key == LEGACY_BLOCK_APPEARANCE:
        _draw_legacy_jelly_border(screen, x, y, size, color)
        return

    _draw_modern_jelly_border(screen, x, y, size, color)


def _draw_modern_jelly_border(screen: pygame.Surface, x: int, y: int, size: int, color: Color) -> None:
    if size < 6:
        pygame.draw.rect(screen, _clamp_color(color[0] * 1.2, color[1] * 1.2, color[2] * 1.2),
                         (x, y, size, size), 1)
        return

    # Neon tonunda parlak, keskin koseli dis cerceve (texture'i bozmadan kenari vurgular).
    border_color = _clamp_color(color[0] * 1.45 + 25, color[1] * 1.45 + 25, color[2] * 1.45 + 25)
    inner = _clamp_color(color[0] * 0.5, color[1] * 0.5, color[2] * 0.5)
    edge_w = max(2, size // 16)
    pygame.draw.rect(screen, border_color, (x, y, size, size), edge_w)
    pygame.draw.rect(screen, inner, (x + edge_w, y + edge_w, size - 2 * edge_w, size - 2 * edge_w), 1)


def _draw_legacy_jelly_border(screen: pygame.Surface, x: int, y: int, size: int, color: Color) -> None:
    border_color = tuple(min(255, int(channel * 1.2)) for channel in color[:3])
    inner = tuple(max(0, int(channel * 0.5)) for channel in color[:3])
    pygame.draw.rect(screen, border_color, (x, y, size, size), 2, border_radius=4)
    pygame.draw.rect(screen, inner, (x + 2, y + 2, size - 4, size - 4), 1, border_radius=3)
