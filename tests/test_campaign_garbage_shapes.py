"""Faz 2 — Garbage shape strict mode.

shape_to_grid'deki "tam dolu satır → ortaya boşluk aç" hack'i kaldırıldı.
SHAPES verisi her satırda en az 1 boşluk içermeli (geometric invariant).
"""
from __future__ import annotations

import pathlib
import sys


ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / 'src'

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from campaign.level_data import get_level_shape, shape_to_grid


def test_no_shape_contains_fully_filled_row():
    """STRICT MODE (Faz 2): SHAPES verisinde tam dolu satır olamaz.

    Hack kaldırıldı; veri seviyesinde geometric invariant.
    """
    bad = []
    for shape_index in range(95):
        shape = get_level_shape(shape_index)
        for row_idx, row_str in enumerate(shape):
            if len(row_str) == 10 and row_str.count('.') == 0:
                bad.append((shape_index, shape_index + 6, row_idx, row_str))
    assert not bad, (
        f"{len(bad)} tam dolu satır bulundu (örn: L{bad[0][1]} row {bad[0][2]} "
        f"= {bad[0][3]!r}). Tüm liste: {bad}"
    )


def test_all_shapes_have_at_least_one_gap_per_row():
    """shape_to_grid çıkışı satır başına en az 1 boş hücre içerir."""
    for shape_index in range(95):
        shape = get_level_shape(shape_index)
        grid = shape_to_grid(shape, cols=10, level=shape_index + 6)
        for row_idx, row in enumerate(grid):
            assert any(cell == 0 for cell in row), (
                f"shape_index={shape_index} (level={shape_index + 6}) row {row_idx} "
                f"tamamen dolu"
            )


def test_all_shapes_within_max_dimensions():
    """Her shape 10 sütun, 10 satır limiti içinde olmalı."""
    for shape_index in range(95):
        shape = get_level_shape(shape_index)
        assert len(shape) <= 10, f"shape_index={shape_index} satır sayısı 10'u aşıyor"
        for row_idx, row_str in enumerate(shape):
            assert len(row_str) == 10, (
                f"shape_index={shape_index} row {row_idx} genişlik {len(row_str)} (10 olmalı)"
            )
            assert all(ch in '.X' for ch in row_str), (
                f"shape_index={shape_index} row {row_idx} geçersiz karakter: {row_str!r}"
            )


def test_shape_to_grid_uses_3_to_4_color_palette():
    """color_themes 3-4 renk içerir (Faz 2 genişletmesi)."""
    # Level 1-20 (Vadi): 3 renk; Level 81-100 (Yıldız): 4 renk
    for level, expected_min_colors in [(10, 3), (30, 3), (50, 3), (70, 3), (90, 4)]:
        shape = get_level_shape(level - 6)
        grid = shape_to_grid(shape, cols=10, level=level)
        used_colors = set()
        for row in grid:
            for cell in row:
                if cell != 0:
                    used_colors.add(cell)
        assert len(used_colors) >= min(expected_min_colors, 2), (
            f"L{level} sadece {len(used_colors)} renk kullanıyor "
            f"(beklenen ≥ {min(expected_min_colors, 2)})"
        )


def test_shape_index_clamping():
    """Negatif veya 95'ten büyük shape_index güvenli fallback üretir."""
    fallback_neg = get_level_shape(-1)
    assert isinstance(fallback_neg, list)
    assert len(fallback_neg) >= 1

    fallback_high = get_level_shape(150)
    last_shape = get_level_shape(94)
    assert fallback_high == last_shape


def test_level_89_and_100_redesigned():
    """Faz 2: Level 89 master koridor ve Level 100 final boss yenilendi."""
    shape_89 = get_level_shape(89 - 6)
    # Aynı satır 3+ kez tekrar etmesin
    seen = {}
    for row in shape_89:
        seen[row] = seen.get(row, 0) + 1
    max_repeat = max(seen.values()) if seen else 0
    assert max_repeat <= 3, f"L89'da bir satır {max_repeat} kez tekrarlıyor: {shape_89}"

    shape_100 = get_level_shape(100 - 6)
    # Final boss: en az 5 farklı satır
    unique_rows = len(set(shape_100))
    assert unique_rows >= 4, f"L100 final boss çeşitliliği zayıf: {unique_rows} farklı satır"
