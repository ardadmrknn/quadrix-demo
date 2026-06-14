"""Faz 3 — Boss Seal mekanik (Tip B) testleri.

_boss_seal_apply_lock: dolu hücrelerden birine LOCKED special block uygular.
_boss_seal_update: 45 saniyede bir tetiklenir.
"""
from __future__ import annotations

import pathlib
import sys


ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / 'src'

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from campaign.campaign_mode import CampaignMode
from campaign.special_blocks import SpecialBlockManager, SpecialBlockType


class _FakeBoard:
    """SpecialBlockManager + grid/occupancy ile minimal board."""

    def __init__(self, width=10, height=20):
        self.width = width
        self.height = height
        self.grid = [[None] * width for _ in range(height)]
        self.occupancy = [[False] * width for _ in range(height)]


def _make_seal_mode(level_num=20, seed=42):
    mode = object.__new__(CampaignMode)
    mode.current_level_num = level_num
    last_digit = level_num % 10
    mode.is_mini_boss = (last_digit == 5)
    mode.is_boss = (last_digit == 0 and level_num > 0)
    mode.board = _FakeBoard()
    mode.special_block_manager = SpecialBlockManager()
    mode._piece_seed = seed
    mode._boss_seal_timer = 0.0
    return mode


def test_seal_apply_lock_finds_filled_cell():
    """Dolu hücre olan board'da seal LOCKED special block ekler."""
    mode = _make_seal_mode()
    # (3, 18) ve (5, 18) dolu olarak işaretle
    mode.board.occupancy[18][3] = True
    mode.board.occupancy[18][5] = True
    mode.board.grid[18][3] = (255, 0, 0)
    mode.board.grid[18][5] = (255, 0, 0)

    # Apply seal
    CampaignMode._boss_seal_apply_lock(mode)

    # En az 1 LOCKED block eklenmiş olmalı
    locked_blocks = [
        (x, y) for (x, y), state in mode.special_block_manager.special_blocks.items()
        if state.block_type == SpecialBlockType.LOCKED
    ]
    assert len(locked_blocks) == 1, (
        f"Tek LOCKED block bekleniyor, {len(locked_blocks)} bulundu"
    )
    # Eklenen block dolu hücrelerden birinde olmalı
    assert locked_blocks[0] in [(3, 18), (5, 18)]


def test_seal_apply_lock_skips_empty_board():
    """Boş board'da seal sessizce atlar; exception fırlatmaz."""
    mode = _make_seal_mode()
    # Tüm occupancy False (default)
    initial_blocks = dict(mode.special_block_manager.special_blocks)

    # Apply — exception fırlatmamalı
    CampaignMode._boss_seal_apply_lock(mode)

    assert mode.special_block_manager.special_blocks == initial_blocks, (
        "Boş board'da special_blocks değişmemeli"
    )


def test_seal_apply_lock_avoids_existing_special_blocks():
    """Mevcut özel blokların üstüne ekleme yapılmaz."""
    mode = _make_seal_mode()
    # (4, 18) dolu ama zaten LOCKED
    mode.board.occupancy[18][4] = True
    mode.board.grid[18][4] = (100, 100, 100)
    mode.special_block_manager.add_special_block(4, 18, SpecialBlockType.LOCKED)

    # Hiç başka dolu hücre yok → candidates boş → sessizce atla
    initial_count = len(mode.special_block_manager.special_blocks)
    CampaignMode._boss_seal_apply_lock(mode)
    final_count = len(mode.special_block_manager.special_blocks)

    assert final_count == initial_count, (
        f"Mevcut LOCKED'a yeni eklenmemeli: initial={initial_count} final={final_count}"
    )


def test_seal_update_triggers_at_45_seconds():
    """45 saniyede bir seal tetiklenir."""
    mode = _make_seal_mode()
    # Dolu hücre ekle ki seal apply edebilsin
    mode.board.occupancy[18][2] = True
    mode.board.grid[18][2] = (200, 0, 0)

    initial_count = len(mode.special_block_manager.special_blocks)

    # 44 saniye → henüz tetiklenmemeli
    CampaignMode._boss_seal_update(mode, 44.0)
    assert len(mode.special_block_manager.special_blocks) == initial_count, (
        "44s'de seal henüz tetiklenmemeli"
    )

    # +2 saniye → toplam 46s, tetiklenmeli
    CampaignMode._boss_seal_update(mode, 2.0)
    assert len(mode.special_block_manager.special_blocks) == initial_count + 1, (
        "46s'de seal tetiklenip 1 LOCKED eklemeli"
    )
    # Timer reset edildi
    assert mode._boss_seal_timer == 0.0
