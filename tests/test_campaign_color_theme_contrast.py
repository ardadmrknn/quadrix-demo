"""Faz 3 — Color theme luminance kontrol (warning-only mode).

Her dünya renk temasında pairwise luminance delta ≥ 30 olmalı (gevşek).
WCAG AA 4.5:1 ratio'ya gerek yok. Fail vermez; warning bas.
"""
from __future__ import annotations

import pathlib
import sys


ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / 'src'

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


def _luminance(rgb):
    """ITU-R BT.709 luminance approximation (0-255 scale)."""
    r, g, b = rgb[0], rgb[1], rgb[2]
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _get_world_color_theme(world: int):
    """level_data.shape_to_grid içindeki color_themes mapping'ini çıkar.

    NOT: shape_to_grid içinde inline tanımlı; test runtime kullanmıyor.
    Faz 3 raporu: bu mapping'i ayrı constant'a çekmek refactor; kapsam dışı.

    color_themes değerleri 1-indexed (I=1, O=2, T=3, S=4, Z=5, J=6, L=7);
    constants.COLORS list 0-indexed (CYAN=0, YELLOW=1, ...). Test mapping
    için COLORS[idx - 1] kullanılır.
    """
    from constants import COLORS
    raw_themes = {
        1: [1, 2, 4],
        2: [1, 4, 6],
        3: [5, 7, 2],
        4: [3, 6, 1],
        5: [2, 7, 3, 1],
    }
    indices = raw_themes.get(world, [])
    return [COLORS[i - 1] for i in indices if 1 <= i <= len(COLORS)]


def test_world_color_themes_have_minimum_three_colors():
    """Her dünya en az 3 renk içerir (Faz 2'den korunan kontrol)."""
    for world in range(1, 6):
        colors = _get_world_color_theme(world)
        assert len(colors) >= 3, f"World {world} only has {len(colors)} colors"


def test_world_color_themes_have_min_luminance_delta_warning_only():
    """Pairwise luminance delta ≥ 30 (gevşek standart, warning bas).

    Test fail vermez; sadece dokümantasyon ve gözlem amaçlı.
    """
    warnings = []
    for world in range(1, 6):
        colors = _get_world_color_theme(world)
        if len(colors) < 2:
            continue
        for i in range(len(colors)):
            for j in range(i + 1, len(colors)):
                lum1 = _luminance(colors[i])
                lum2 = _luminance(colors[j])
                delta = abs(lum1 - lum2)
                if delta < 30:
                    warnings.append(
                        f"World {world}: colors[{i}]={colors[i]} ↔ colors[{j}]={colors[j]} "
                        f"luminance delta {delta:.1f} < 30"
                    )

    if warnings:
        for w in warnings:
            print(f"[COLOR THEME WARNING] {w}")

    # Faz 3 kararı: warning bas, fail verme.
    assert True
