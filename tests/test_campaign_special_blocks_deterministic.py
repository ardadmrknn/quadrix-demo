"""Faz 1 — Special blocks deterministik yerleşim.

_init_special_blocks artık random.shuffle (global state) yerine
random.Random(seed) instance kullanıyor. Aynı seed → aynı (x,y) listesi.
quick_restart aynı seed kullandığı için layout aynı kalır.
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
from campaign.level_data import get_level


class _FakeBoard:
    def __init__(self, width=10, height=20):
        self.width = width
        self.height = height


def _make_mode_for_special_blocks(level_num: int, piece_seed: int):
    mode = object.__new__(CampaignMode)
    mode.current_level_num = level_num
    mode.level_config = get_level(level_num)
    mode._piece_seed = piece_seed
    mode.special_block_manager = SpecialBlockManager()
    mode.board = _FakeBoard()
    return mode


def _capture_layout(mode):
    """SpecialBlockManager.special_blocks dict'inden (x,y,type) listesi çıkar."""
    sbm = mode.special_block_manager
    items = []
    for (x, y), state in sbm.special_blocks.items():
        items.append((x, y, state.block_type.value))
    return sorted(items)


def test_same_seed_produces_identical_layout():
    """Aynı seed iki kez init edilince aynı pozisyon listesi gelir."""
    # Level 21+ özel blok içerir. Level 25 mini-boss + ice blokları
    seed = 12345
    mode_a = _make_mode_for_special_blocks(level_num=25, piece_seed=seed)
    CampaignMode._init_special_blocks(mode_a)
    layout_a = _capture_layout(mode_a)

    mode_b = _make_mode_for_special_blocks(level_num=25, piece_seed=seed)
    CampaignMode._init_special_blocks(mode_b)
    layout_b = _capture_layout(mode_b)

    assert layout_a == layout_b, f"Aynı seed farklı layout üretti:\n  a={layout_a}\n  b={layout_b}"
    assert len(layout_a) > 0, "Level 25 özel blok içermeli"


def test_different_seed_produces_different_layout():
    """Farklı seed → en azından bir farklı pozisyon."""
    mode_a = _make_mode_for_special_blocks(level_num=45, piece_seed=11111)
    CampaignMode._init_special_blocks(mode_a)
    layout_a = _capture_layout(mode_a)

    mode_b = _make_mode_for_special_blocks(level_num=45, piece_seed=99999)
    CampaignMode._init_special_blocks(mode_b)
    layout_b = _capture_layout(mode_b)

    # Layout boş değilse fark olmalı
    if layout_a and layout_b:
        assert layout_a != layout_b, (
            f"Farklı seed aynı layout üretti (random.Random instance kullanılmıyor olabilir)"
        )


def test_init_does_not_pollute_global_random_state():
    """_init_special_blocks global random state'i etkilemez."""
    import random as _global_rng

    _global_rng.seed(777)
    expected_value = _global_rng.random()
    _global_rng.seed(777)  # tekrar başa al

    mode = _make_mode_for_special_blocks(level_num=55, piece_seed=42)
    CampaignMode._init_special_blocks(mode)

    # Global random state init_special_blocks tarafından kullanılmadıysa
    # aynı seed sonrası ilk random() değeri aynı kalır
    actual_value = _global_rng.random()
    assert actual_value == expected_value, (
        "_init_special_blocks global random state'i kirletti"
    )
