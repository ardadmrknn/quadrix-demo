"""Faz 2 — 3. yıldız tip çeşitliliği + yeni handler doğrulama.

- Her dünyada (1-5) override tablosunda en az 4 farklı 3. yıldız tipi var.
- Aynı tip art arda 3'ten fazla level tekrar etmesin.
- Yeni tipler (no_hold_run, pristine, garbage_speed, tetris_only, min_score)
  _is_star_condition_met ile doğru sonuç verir.
"""
from __future__ import annotations

import pathlib
import sys


ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / 'src'

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from campaign.campaign_mode import CampaignMode
from campaign.level_data import get_level


def _world_levels(world: int):
    start = (world - 1) * 20 + 1
    return list(range(start, start + 20))


def _third_star_type(level_num: int) -> str:
    cfg = get_level(level_num)
    if not cfg or 3 not in cfg.stars:
        return ''
    return cfg.stars[3].get('type', '')


def test_each_world_has_at_least_4_distinct_third_star_types():
    """Her dünyada 3. yıldız tipinde en az 4 farklı çeşit (campaign monotonisini kır)."""
    for world in range(1, 6):
        types_in_world = set()
        for lv in _world_levels(world):
            t = _third_star_type(lv)
            if t:
                types_in_world.add(t)
        assert len(types_in_world) >= 4, (
            f"World {world}: sadece {len(types_in_world)} farklı 3. yıldız tipi: {types_in_world}"
        )


def test_no_third_star_type_repeats_more_than_3_consecutive():
    """Aynı 3. yıldız tipi art arda 3'ten fazla level tekrar etmesin."""
    prev_type = None
    streak = 0
    bad = []
    for lv in range(1, 101):
        t = _third_star_type(lv)
        if t == prev_type and t:
            streak += 1
            if streak > 3:
                bad.append((lv, t, streak))
        else:
            streak = 1
            prev_type = t
    assert not bad, f"Art arda tekrarlayan 3. yıldız tipi: {bad}"


# === Yeni tip handler testleri ===

def _make_mode_for_star(level_complete=True, **stats):
    mode = object.__new__(CampaignMode)
    mode.level_complete = level_complete
    mode.elapsed_time = stats.get('elapsed_time', 30.0)
    mode.moves_count = stats.get('moves_count', 0)
    mode._hold_use_count = stats.get('hold_count', 0)
    mode._hard_drop_count = stats.get('hard_drop_count', 0)
    mode._single_lines_count = stats.get('singles', 0)
    mode.double_count = stats.get('doubles', 0)
    mode.triple_count = stats.get('triples', 0)
    mode.tetris_count = stats.get('tetris', 0)
    mode.total_combos = stats.get('combos', 0)
    mode.max_combo_chain = stats.get('chain', 0)
    mode.board = type('B', (), {'score': stats.get('score', 0), 'lines_cleared': 0})()
    mode.objectives = stats.get('objectives', [])
    return mode


def test_no_hold_run_passes_when_hold_count_zero():
    mode = _make_mode_for_star(hold_count=0)
    assert CampaignMode._is_star_condition_met(mode, {'type': 'no_hold_run'}) is True


def test_no_hold_run_fails_when_hold_used():
    mode = _make_mode_for_star(hold_count=1)
    assert CampaignMode._is_star_condition_met(mode, {'type': 'no_hold_run'}) is False


def test_pristine_passes_when_no_hard_drop():
    mode = _make_mode_for_star(hard_drop_count=0)
    assert CampaignMode._is_star_condition_met(mode, {'type': 'pristine'}) is True


def test_pristine_fails_when_hard_drop_used():
    mode = _make_mode_for_star(hard_drop_count=1)
    assert CampaignMode._is_star_condition_met(mode, {'type': 'pristine'}) is False


def test_tetris_only_passes_when_only_tetrises():
    mode = _make_mode_for_star(tetris=2, singles=0, doubles=0, triples=0)
    assert CampaignMode._is_star_condition_met(mode, {'type': 'tetris_only'}) is True


def test_tetris_only_fails_when_singles_present():
    mode = _make_mode_for_star(tetris=2, singles=1)
    assert CampaignMode._is_star_condition_met(mode, {'type': 'tetris_only'}) is False


def test_tetris_only_fails_when_doubles_present():
    mode = _make_mode_for_star(tetris=2, doubles=1)
    assert CampaignMode._is_star_condition_met(mode, {'type': 'tetris_only'}) is False


def test_tetris_only_fails_when_no_tetrises():
    mode = _make_mode_for_star(tetris=0)
    assert CampaignMode._is_star_condition_met(mode, {'type': 'tetris_only'}) is False


def test_min_score_passes_at_threshold():
    mode = _make_mode_for_star(score=10000)
    assert CampaignMode._is_star_condition_met(mode, {'type': 'min_score', 'value': 10000}) is True


def test_min_score_fails_below_threshold():
    mode = _make_mode_for_star(score=9999)
    assert CampaignMode._is_star_condition_met(mode, {'type': 'min_score', 'value': 10000}) is False


def test_garbage_speed_requires_completed_clear_garbage():
    """clear_garbage objective tamamlanmamışsa garbage_speed sağlanamaz."""
    from campaign.objectives import ClearGarbageObjective
    obj = ClearGarbageObjective(target=10)
    obj.completed = False
    mode = _make_mode_for_star(elapsed_time=30.0, objectives=[obj])
    assert CampaignMode._is_star_condition_met(mode, {'type': 'garbage_speed', 'value': 60}) is False


def test_garbage_speed_passes_when_completed_within_time():
    from campaign.objectives import ClearGarbageObjective
    obj = ClearGarbageObjective(target=10)
    obj.completed = True
    mode = _make_mode_for_star(elapsed_time=30.0, objectives=[obj])
    assert CampaignMode._is_star_condition_met(mode, {'type': 'garbage_speed', 'value': 60}) is True


def test_garbage_speed_fails_when_too_slow():
    from campaign.objectives import ClearGarbageObjective
    obj = ClearGarbageObjective(target=10)
    obj.completed = True
    mode = _make_mode_for_star(elapsed_time=120.0, objectives=[obj])
    assert CampaignMode._is_star_condition_met(mode, {'type': 'garbage_speed', 'value': 60}) is False
