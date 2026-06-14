"""Faz 1 — Validator: tüm 100 level config tutarlılık kontrolü.

_validate_level_config + validate_all_levels davranışını dar testlerle
doğrular. Tüm 100 level temiz olmalı (build-time auto-fix sonrası).
"""
from __future__ import annotations

import pathlib
import sys


ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / 'src'

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from campaign.level_data import (
    LevelConfig,
    _validate_level_config,
    validate_all_levels,
    get_level,
)


def test_validate_all_100_levels_clean():
    """Tüm 100 level validator'dan hata almadan geçmeli."""
    issues = validate_all_levels()
    if issues:
        # Hata varsa detay göster
        report = '\n'.join(f"L{lv}: {errs}" for lv, errs in sorted(issues.items()))
        raise AssertionError(f"Validator failed for {len(issues)} levels:\n{report}")


def test_validate_detects_survival_time_limit_conflict():
    """Survival hedefi time_limit'ten büyük → hata raporu."""
    cfg = LevelConfig(
        level=999,
        world=1,
        name={'tr': 'Test', 'en': 'Test'},
        objectives=[{'type': 'survival', 'target': 100}],
        speed=800,
        time_limit=60,  # 100 + 5 = 105'ten küçük → çakışma
        stars={1: {'type': 'complete'}, 2: {'type': 'complete'}, 3: {'type': 'complete'}},
    )
    errors = _validate_level_config(cfg)
    assert any('survival' in e.lower() and 'time_limit' in e for e in errors), errors


def test_validate_detects_clear_garbage_without_rows():
    """clear_garbage objective var ama pre_placed_rows=0 → hata."""
    cfg = LevelConfig(
        level=998,
        world=1,
        name={'tr': 'Test', 'en': 'Test'},
        objectives=[{'type': 'clear_garbage', 'target': 0}],
        speed=800,
        pre_placed_rows=0,
        garbage_pattern='none',
        stars={1: {'type': 'complete'}, 2: {'type': 'complete'}, 3: {'type': 'complete'}},
    )
    errors = _validate_level_config(cfg)
    assert any('clear_garbage' in e and 'pre_placed_rows' in e for e in errors), errors
    assert any('garbage_pattern' in e for e in errors), errors


def test_validate_detects_low_move_limit():
    """move_limit < 10 → hata."""
    cfg = LevelConfig(
        level=997,
        world=1,
        name={'tr': 'Test', 'en': 'Test'},
        objectives=[{'type': 'clear_lines', 'target': 5}],
        speed=800,
        move_limit=8,
        stars={1: {'type': 'complete'}, 2: {'type': 'complete'}, 3: {'type': 'complete'}},
    )
    errors = _validate_level_config(cfg)
    assert any('move_limit' in e for e in errors), errors


def test_validate_clean_config_returns_empty_list():
    """Tutarlı config → boş hata listesi."""
    cfg = get_level(1)
    assert cfg is not None
    errors = _validate_level_config(cfg)
    assert errors == [], errors


def test_validate_flags_missing_star_keys():
    """Stars dict'inde 1/2/3 anahtarları eksikse hata."""
    cfg = LevelConfig(
        level=996,
        world=1,
        name={'tr': 'Test', 'en': 'Test'},
        objectives=[{'type': 'clear_lines', 'target': 5}],
        speed=800,
        stars={1: {'type': 'complete'}},  # 2 ve 3 eksik
    )
    errors = _validate_level_config(cfg)
    assert any('stars' in e and 'eksik' in e for e in errors), errors
