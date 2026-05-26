"""Faz 3 — Level 100 final boss progress_ratio fallback testleri.

Final boss 3-fazlı geçişler ana objective'in get_progress_ratio() üzerinden
hesaplanır. survival/clear_garbage/normal hepsinde defansif çalışmalı.
objectives=[] ise ratio=0, sadece rain aktif.
"""
from __future__ import annotations

import pathlib
import sys


ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / 'src'

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from campaign.campaign_mode import CampaignMode
from campaign.special_blocks import SpecialBlockManager
from campaign.objectives import (
    ClearLinesObjective,
    TimeObjective,
    ClearGarbageObjective,
)


def _make_final_boss_mode():
    mode = object.__new__(CampaignMode)
    mode.current_level_num = 100
    mode.is_boss = True
    mode.is_mini_boss = False
    mode._boss_dark_timer = 0.0
    mode._boss_seal_timer = 0.0
    mode._boss_rain_timer = 0.0
    mode._boss_rain_count = 0
    mode._dark_preview_visible = True
    mode._hide_next_pieces = False
    mode.special_block_manager = SpecialBlockManager()
    mode._piece_seed = 42
    return mode


def test_final_boss_phase_with_survival_objective_uses_safe_fallback():
    """Survival objective için elapsed/target ratio'su faz geçişlerini sürer."""
    mode = _make_final_boss_mode()

    # Survival 100s hedefli; 50 saniye geçti → ratio=0.5
    obj = TimeObjective(target_seconds=100, objective_type='survive')
    obj.progress = 50  # 50 / 100 = 0.5
    mode.objectives = [obj]

    mode._boss_phase_update(0.5)

    # ratio=0.5 ≥ 0.33 → seal aktif
    assert mode._boss_seal_timer > 0, "Survival 50%'de seal aktif olmalı"
    # 0.5 < 0.66 → dark kapalı
    assert mode._boss_dark_timer == 0.0, "Survival 50%'de dark kapalı olmalı"


def test_final_boss_phase_with_garbage_objective_uses_safe_fallback():
    """ClearGarbageObjective için progress/target ratio."""
    mode = _make_final_boss_mode()

    # 10 hücreden 7'si temizlendi → ratio=0.7
    obj = ClearGarbageObjective(target=10)
    obj.set_initial_garbage(10)
    obj.progress = 7  # 7 / 10 = 0.7
    mode.objectives = [obj]

    mode._boss_phase_update(0.5)

    # 0.7 ≥ 0.33 ve ≥ 0.66 → seal + dark aktif
    assert mode._boss_seal_timer > 0, "Garbage 70%'de seal aktif olmalı"
    assert mode._boss_dark_timer > 0, "Garbage 70%'de dark aktif olmalı"


def test_final_boss_phase_with_zero_objectives_safe():
    """objectives=[] ise ratio=0 fallback (sadece rain aktif)."""
    mode = _make_final_boss_mode()
    mode.objectives = []

    # Exception fırlatmamalı
    mode._boss_phase_update(0.5)

    assert mode._boss_rain_timer > 0, "objectives=[] ile rain timer ilerlemiş olmalı"
    assert mode._boss_seal_timer == 0.0
    assert mode._boss_dark_timer == 0.0


def test_final_boss_phase_with_objective_progress_ratio_clamps_above_one():
    """Progress ratio > 1.0 ise clamp = 1.0, hepsi aktif."""
    mode = _make_final_boss_mode()

    obj = ClearLinesObjective(target=5)
    obj.progress = 100  # 100/5 = 20.0 → clamp 1.0
    mode.objectives = [obj]

    mode._boss_phase_update(0.5)

    # ratio=1.0 ≥ 0.66 → hepsi aktif
    assert mode._boss_rain_timer > 0
    assert mode._boss_seal_timer > 0
    assert mode._boss_dark_timer > 0
