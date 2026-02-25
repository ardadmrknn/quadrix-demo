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

Color = Tuple[int, int, int]


def draw_jelly_block(screen: pygame.Surface, x: int, y: int, size: int, color: Color) -> None:
    """Draw a glassy "jelly" block onto the given surface.

    Parameters:
        screen: pygame Surface to draw onto.
        x, y: top-left pixel coordinates.
        size: width/height in pixels.
        color: RGB color tuple, 0-255.
    """
    # Base fill (slightly saturated)
    base_color = tuple(min(255, int(c * 1.05)) for c in color[:3])
    pygame.draw.rect(screen, base_color, (x, y, size, size))

    # Renk parlakligini hesapla - koyu/doygun renkler icin minimum kontrast garantisi
    avg_brightness = sum(base_color[:3]) / 3
    # Koyu renkler icin daha yuksek ekleme, acik renkler icin carpan kullan
    min_highlight_add = max(35, int(80 - avg_brightness * 0.3))  # Koyu renklerde en az 35-80 ekle
    min_shadow_sub = max(25, int(60 - avg_brightness * 0.2))     # Koyu renklerde en az 25-60 cikar

    # Inner shading (soft radial/rect gradient with stroked layers)
    inner_margin = max(1, size // 12)
    gradient_steps = 7
    for i in range(gradient_steps):
        progress = i / gradient_steps
        shade_factor = 1 - (progress * 0.18)
        shade_color = tuple(max(0, int(c * shade_factor)) for c in base_color[:3])
        margin = int(inner_margin * (0.5 + i * 0.3))
        rect_size = size - 2 * margin
        if rect_size > 0:
            pygame.draw.rect(screen, shade_color, (x + margin, y + margin, rect_size, rect_size), 1)

    # Top-left highlight (multi-layer) - minimum kontrast garantili
    highlight_thickness = max(2, size // 8)
    outer_highlight = tuple(min(255, max(int(c * 1.4), c + min_highlight_add)) for c in base_color[:3])
    pygame.draw.line(screen, outer_highlight, (x, y), (x + size - 1, y), highlight_thickness)
    pygame.draw.line(screen, outer_highlight, (x, y), (x, y + size - 1), highlight_thickness)

    mid_highlight = tuple(min(255, max(int(c * 1.65), c + min_highlight_add + 15)) for c in base_color[:3])
    mid_thickness = max(1, highlight_thickness // 2)
    pygame.draw.line(screen, mid_highlight, (x + 1, y + 1), (x + size - 2, y + 1), mid_thickness)
    pygame.draw.line(screen, mid_highlight, (x + 1, y + 1), (x + 1, y + size - 2), mid_thickness)

    inner_highlight = tuple(min(255, max(int(c * 1.9), c + min_highlight_add + 30)) for c in base_color[:3])
    pygame.draw.line(screen, inner_highlight, (x + 2, y + 2), (x + size - 3, y + 2), 1)
    pygame.draw.line(screen, inner_highlight, (x + 2, y + 2), (x + 2, y + size - 3), 1)

    # Bottom-right shadow (multi-layer) - minimum kontrast garantili
    shadow_thickness = max(2, size // 8)
    outer_shadow = tuple(max(0, min(int(c * 0.45), c - min_shadow_sub)) for c in base_color[:3])
    pygame.draw.line(screen, outer_shadow, (x + 1, y + size - 1), (x + size - 1, y + size - 1), shadow_thickness)
    pygame.draw.line(screen, outer_shadow, (x + size - 1, y + 1), (x + size - 1, y + size - 1), shadow_thickness)

    mid_shadow = tuple(max(0, min(int(c * 0.30), c - min_shadow_sub - 10)) for c in base_color[:3])
    mid_thickness = max(1, shadow_thickness // 2)
    pygame.draw.line(screen, mid_shadow, (x + 2, y + size - 2), (x + size - 3, y + size - 2), mid_thickness)
    pygame.draw.line(screen, mid_shadow, (x + size - 2, y + 2), (x + size - 2, y + size - 3), mid_thickness)

    inner_shadow = tuple(max(0, min(int(c * 0.20), c - min_shadow_sub - 20)) for c in base_color[:3])
    pygame.draw.line(screen, inner_shadow, (x + 3, y + size - 3), (x + size - 4, y + size - 3), 1)
    pygame.draw.line(screen, inner_shadow, (x + size - 3, y + 3), (x + size - 3, y + size - 4), 1)

    # Multi-step shine (premium effect) - minimum kontrast garantili
    shine_size = max(4, size // 4)
    shine_offset = max(3, highlight_thickness + 1)

    outer_halo = tuple(min(255, max(int(c * 1.6), c + min_highlight_add + 20)) for c in base_color[:3])
    pygame.draw.rect(screen, outer_halo, (x + shine_offset - 1, y + shine_offset - 1, shine_size + 3, shine_size + 3))

    mid_shine = tuple(min(255, max(int(c * 1.95), c + min_highlight_add + 40)) for c in base_color[:3])
    pygame.draw.rect(screen, mid_shine, (x + shine_offset, y + shine_offset, shine_size + 1, shine_size + 1))

    inner_shine = tuple(min(255, int(c * 2.3 + 60)) for c in base_color[:3])
    pygame.draw.rect(screen, inner_shine, (x + shine_offset + 1, y + shine_offset + 1, max(2, shine_size - 1), max(2, shine_size - 1)))

    core_x = x + shine_offset + max(1, shine_size // 3)
    core_y = y + shine_offset + max(1, shine_size // 3)
    core_size = max(1, shine_size // 2)
    core_shine = tuple(min(255, c + 120) for c in base_color[:3])
    pygame.draw.rect(screen, core_shine, (core_x, core_y, core_size, core_size))

    # Optional fine reflection for larger blocks
    if size > 15:
        reflection_size = max(1, size // 8)
        reflection_x = x + size - shine_offset - reflection_size - 2
        reflection_y = y + size - shine_offset - reflection_size - 2
        reflection_color = tuple(min(255, int(c * 1.3)) for c in base_color[:3])
        pygame.draw.rect(screen, reflection_color, (reflection_x, reflection_y, reflection_size, reflection_size))


def draw_jelly_border(screen: pygame.Surface, x: int, y: int, size: int, color: Color) -> None:
    """Draw a consistent inner/outer border complementing the jelly style.

    Used when a textured cell is blitted instead of the programmatic base.
    """
    border_color = tuple(min(255, int(c * 1.2)) for c in color[:3])
    inner = tuple(max(0, int(c * 0.5)) for c in color[:3])
    pygame.draw.rect(screen, border_color, (x, y, size, size), 2, border_radius=4)
    pygame.draw.rect(screen, inner, (x + 2, y + 2, size - 4, size - 4), 1, border_radius=3)
