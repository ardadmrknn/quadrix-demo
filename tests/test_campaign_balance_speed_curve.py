"""Faz 2 — Hız eğrisi objective tipine duyarlı.

_calculate_speed survival için hızlandırır, score/tetris için yavaşlatır.
Block limit katsayıları (score 80→60, tetris 10→7) düzeltildi.
"""
from __future__ import annotations

import pathlib
import sys


ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / 'src'

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from campaign.level_data import _calculate_speed, _calculate_block_limit


def test_survival_speed_is_faster_than_default():
    for lv in [10, 30, 60, 90]:
        default = _calculate_speed(lv, 'clear_lines')
        survival = _calculate_speed(lv, 'survival')
        assert survival < default, (
            f"L{lv} survival ({survival}) default ({default})'tan hızlı olmalı"
        )


def test_score_speed_is_slower_than_default():
    for lv in [10, 30, 60, 90]:
        default = _calculate_speed(lv, 'clear_lines')
        score = _calculate_speed(lv, 'score')
        assert score > default, (
            f"L{lv} score ({score}) default ({default})'tan yavaş olmalı"
        )


def test_tetris_speed_is_slower_than_default():
    for lv in [10, 30, 60, 90]:
        default = _calculate_speed(lv, 'clear_lines')
        tetris = _calculate_speed(lv, 'tetris')
        assert tetris > default, (
            f"L{lv} tetris ({tetris}) default ({default})'tan yavaş olmalı"
        )


def test_score_block_limit_uses_60_per_block():
    """Score görevinde block_limit estimated_blocks = target // 60 (eski 80)."""
    # target=3000, level=20 (multiplier=2.5 -> base=125, ama cap+=multiplier var)
    # Önemli: 80'den 60'a düşünce block_limit ARTAR
    target = 3000
    bl = _calculate_block_limit(20, [{'type': 'score', 'target': target}], False)
    # estimated_blocks = 3000 // 60 = 50 (eski 80 ile 37 olurdu); multiplier=2.5
    expected_min = int((target / 60) * 2.5 * 0.9)  # %10 tolerance
    assert bl >= expected_min, f"Score block_limit yetersiz: {bl} < {expected_min}"


def test_tetris_block_limit_uses_7_per_tetris():
    """Tetris görevinde her Quadrix için ~7 blok (eski 10)."""
    target = 3
    bl = _calculate_block_limit(50, [{'type': 'tetris', 'target': target}], False)
    # target * 7 * multiplier(2.2) ≈ 46
    expected_max = int(target * 8 * 2.2)  # eski 10'la 66 olurdu, biz <55 bekliyoruz
    assert bl <= expected_max, f"Tetris block_limit hâlâ çok geniş: {bl} > {expected_max}"


def test_speed_clamp_min_max():
    """speed her durumda 400-1100 ms aralığında."""
    for lv in range(1, 101):
        for obj_type in ['clear_lines', 'survival', 'score', 'tetris', 'combo']:
            sp = _calculate_speed(lv, obj_type)
            assert 400 <= sp <= 1100, f"L{lv} {obj_type}: speed={sp} aralık dışı"
