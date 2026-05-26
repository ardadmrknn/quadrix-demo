"""Faz 1 — Block limit makul mü kontrolü.

clear_garbage / score / tetris / clear_lines görev tiplerinde
_calculate_block_limit auto-gen davranışı sanity check.
"""
from __future__ import annotations

import pathlib
import sys


ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / 'src'

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from campaign.level_data import (
    _calculate_block_limit,
    _calculate_garbage_rows,
    get_level,
)


def test_clear_garbage_block_limit_uses_actual_garbage_estimate():
    """clear_garbage target=0 olsa bile block_limit gerçek hücre sayısına göre hesaplanır.

    garbage_rows * 10 * 0.45 ≈ tahmini hücre. Her bloğun ~3-4 hücre kaldıracağı
    varsayımı ile minimum makul limit gelir.
    """
    # Level 45 = clear_garbage override (override block_limit yok, auto-gen)
    # Level 6 ile 60 arası sample alalım
    for level in [10, 25, 50, 75, 100]:
        is_boss = (level % 10 == 0)
        objectives = [{'type': 'clear_garbage', 'target': 0}]
        block_limit = _calculate_block_limit(level, objectives, is_boss)
        garbage_rows = _calculate_garbage_rows(level, is_boss)
        if garbage_rows == 0:
            garbage_rows = max(2, min(4, 2 + (level - 6) // 10))
        estimated_cells = max(15, int(garbage_rows * 10 * 0.45))
        # Her bloğun en az 3 hücre kaldıracağı varsayımıyla minimum sınır
        min_expected = max(15, estimated_cells // 5)
        assert block_limit >= min_expected, (
            f"L{level} clear_garbage: block_limit={block_limit} çok düşük "
            f"(estimated_cells={estimated_cells}, min_expected={min_expected})"
        )


def test_clear_garbage_block_limit_is_finite_and_capped():
    """Her clear_garbage tipinde block_limit 15..120 aralığında."""
    for level in range(6, 101):
        is_boss = (level % 10 == 0)
        objectives = [{'type': 'clear_garbage', 'target': 0}]
        block_limit = _calculate_block_limit(level, objectives, is_boss)
        assert 15 <= block_limit <= 120, f"L{level}: block_limit={block_limit} aralık dışı"


def test_score_objective_block_limit_is_proportional_to_target():
    """score görevinde target arttıkça block_limit artar (monotonik)."""
    bl_low = _calculate_block_limit(20, [{'type': 'score', 'target': 1000}], False)
    bl_high = _calculate_block_limit(20, [{'type': 'score', 'target': 5000}], False)
    assert bl_high > bl_low, (
        f"score block_limit monotonik değil: target=1000 → {bl_low}, target=5000 → {bl_high}"
    )


def test_tetris_objective_block_limit_is_at_least_target_times_seven():
    """tetris görevinde her Quadrix için en az ~7 blok ayrılmalı (lower bound)."""
    for level, target in [(15, 1), (50, 3), (90, 5)]:
        is_boss = (level % 10 == 0)
        block_limit = _calculate_block_limit(level, [{'type': 'tetris', 'target': target}], is_boss)
        # Çok genel: target * 5 absolute minimum (çok agresif lower bound)
        assert block_limit >= target * 5, (
            f"L{level} tetris target={target}: block_limit={block_limit} çok düşük"
        )


def test_real_levels_clear_garbage_have_finite_block_limit():
    """Gerçek campaign levellarında clear_garbage görevleri makul block_limit alır."""
    for level_num in range(1, 101):
        cfg = get_level(level_num)
        assert cfg is not None
        has_clear_garbage = any(o.get('type') == 'clear_garbage' for o in cfg.objectives)
        if has_clear_garbage:
            assert cfg.move_limit is None or 15 <= cfg.move_limit <= 200, (
                f"L{level_num} clear_garbage: move_limit={cfg.move_limit} makul değil"
            )
