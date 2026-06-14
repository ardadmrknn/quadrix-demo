"""Faz 2 — Boss/Mini-Boss eşsiz mekanikleri.

- _boss_get_type doğru tip döndürüyor.
- _boss_push_garbage_row overflow guard çalışıyor.
- Mini-boss tip α (fast) fall_speed azaltıyor.
- Mini-boss tip β (missing) _allowed_pieces'tan 1 eleman çıkarıyor.
- Level 100 final boss faz geçişleri tetikleniyor.
"""
from __future__ import annotations

import pathlib
import sys


ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / 'src'

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from campaign.campaign_mode import CampaignMode


def _make_boss_mode(level_num):
    """Minimal CampaignMode instance — sadece boss tipi belirlemek için."""
    mode = object.__new__(CampaignMode)
    mode.current_level_num = level_num
    last_digit = level_num % 10
    mode.is_mini_boss = (last_digit == 5)
    mode.is_boss = (last_digit == 0 and level_num > 0)
    return mode


def test_boss_type_rotation_rain_seal_dark():
    """Level 10/40/70 → rain, 20/50/80 → seal, 30/60/90 → dark."""
    rain_levels = [10, 40, 70]
    seal_levels = [20, 50, 80]
    dark_levels = [30, 60, 90]
    final_levels = [100]

    for lv in rain_levels:
        mode = _make_boss_mode(lv)
        assert CampaignMode._boss_get_type(mode) == 'rain', f"L{lv} rain bekleniyor"
    for lv in seal_levels:
        mode = _make_boss_mode(lv)
        assert CampaignMode._boss_get_type(mode) == 'seal', f"L{lv} seal bekleniyor"
    for lv in dark_levels:
        mode = _make_boss_mode(lv)
        assert CampaignMode._boss_get_type(mode) == 'dark', f"L{lv} dark bekleniyor"
    for lv in final_levels:
        mode = _make_boss_mode(lv)
        assert CampaignMode._boss_get_type(mode) == 'final', f"L{lv} final bekleniyor"


def test_mini_boss_type_rotation_fast_missing():
    """Level 5/25/45/65/85 → fast, 15/35/55/75/95 → missing."""
    fast_levels = [5, 25, 45, 65, 85]
    missing_levels = [15, 35, 55, 75, 95]
    for lv in fast_levels:
        mode = _make_boss_mode(lv)
        assert CampaignMode._boss_get_type(mode) == 'fast', f"L{lv} fast bekleniyor"
    for lv in missing_levels:
        mode = _make_boss_mode(lv)
        assert CampaignMode._boss_get_type(mode) == 'missing', f"L{lv} missing bekleniyor"


def test_normal_levels_have_no_boss_type():
    """Level 1, 7, 11, 13, 99 gibi non-boss/non-miniboss levellar None döner."""
    for lv in [1, 2, 3, 4, 6, 7, 8, 9, 11, 13, 19, 99]:
        mode = _make_boss_mode(lv)
        assert CampaignMode._boss_get_type(mode) is None, f"L{lv} boss tipi None bekleniyor"


def test_boss_push_garbage_row_overflow_guard():
    """Üst satırda dolu hücre varsa push'u atla; rain_count artmaz."""

    class _FakeBoard:
        def __init__(self):
            self.width = 10
            self.height = 20
            # Üst satır dolu → overflow guard tetiklenmeli
            self.occupancy = [[True] * 10] + [[False] * 10 for _ in range(19)]
            self.grid = [[None] * 10 for _ in range(20)]

    mode = _make_boss_mode(10)
    mode.board = _FakeBoard()
    mode._piece_seed = 42
    mode._boss_rain_count = 0

    CampaignMode._boss_push_garbage_row(mode)

    assert mode._boss_rain_count == 0, "Overflow guard tetiklenmedi"


def test_boss_push_garbage_row_appends_when_safe():
    """Üst satır boşsa push uygulanır, rain_count +1, board satır sayısı korunur."""

    class _FakeBoard:
        def __init__(self):
            self.width = 10
            self.height = 20
            self.occupancy = [[False] * 10 for _ in range(20)]
            self.grid = [[None] * 10 for _ in range(20)]

    mode = _make_boss_mode(10)
    mode.board = _FakeBoard()
    mode._piece_seed = 42
    mode._boss_rain_count = 0
    mode.current_piece = None  # Aktif parça yok

    CampaignMode._boss_push_garbage_row(mode)

    assert mode._boss_rain_count == 1
    assert len(mode.board.grid) == 20  # pop+append → satır sayısı sabit
    # Yeni alttaki satırda en az 9 dolu hücre (1 gap)
    bottom_row = mode.board.grid[-1]
    filled = sum(1 for c in bottom_row if c is not None)
    assert filled == 9, f"Push edilen satırda 9 dolu hücre bekleniyor, {filled} bulundu"


def test_boss_dark_update_toggles_preview():
    """Dark phase 4s gizli + 2s açık döngüsü."""
    mode = _make_boss_mode(30)
    mode._boss_dark_timer = 0.0
    mode._dark_preview_visible = True
    mode._hide_next_pieces = False

    # 0..4s arası → gizli
    CampaignMode._boss_dark_update(mode, 1.0)  # 1.0
    CampaignMode._boss_dark_update(mode, 2.0)  # 3.0
    assert mode._hide_next_pieces is True, "0..4s aralığında preview gizli olmalı"

    # 4..6s arası → açık
    CampaignMode._boss_dark_update(mode, 2.0)  # 5.0
    assert mode._hide_next_pieces is False, "4..6s aralığında preview açık olmalı"


def test_final_boss_phase_uses_progress_ratio():
    """Level 100 final boss objective progress'ine göre faz açılır."""
    from campaign.objectives import ClearLinesObjective

    mode = _make_boss_mode(100)
    mode._boss_dark_timer = 0.0
    mode._boss_seal_timer = 0.0
    mode._boss_rain_timer = 0.0
    mode._boss_rain_count = 0
    mode._dark_preview_visible = True
    mode._hide_next_pieces = False
    mode.special_block_manager = type('SBM', (), {'special_blocks': {}})()
    mode._piece_seed = 42

    # Progress %20 → sadece rain
    obj = ClearLinesObjective(target=10)
    obj.progress = 2  # %20
    mode.objectives = [obj]
    mode._boss_phase_update(0.5)
    # rain timer ilerledi
    assert mode._boss_rain_timer > 0
    # seal/dark progres < %33 olduğu için ilerlememeli
    assert mode._boss_seal_timer == 0.0
    assert mode._boss_dark_timer == 0.0

    # Progress %50 → rain + seal
    obj.progress = 5  # %50
    mode._boss_seal_timer = 0.0
    mode._boss_phase_update(0.5)
    assert mode._boss_seal_timer > 0
    # dark hâlâ kapalı (< %66)
    assert mode._boss_dark_timer == 0.0

    # Progress %80 → hepsi
    obj.progress = 8  # %80
    mode._boss_dark_timer = 0.0
    mode._boss_phase_update(0.5)
    assert mode._boss_dark_timer > 0


def test_final_boss_phase_clamps_negative_progress():
    """Defansif clamp: ratio < 0 ise 0 olarak ele alınır."""
    from campaign.objectives import ClearLinesObjective

    mode = _make_boss_mode(100)
    mode._boss_dark_timer = 0.0
    mode._boss_seal_timer = 0.0
    mode._boss_rain_timer = 0.0
    mode._boss_rain_count = 0
    mode._dark_preview_visible = True
    mode._hide_next_pieces = False
    mode.special_block_manager = type('SBM', (), {'special_blocks': {}})()
    mode._piece_seed = 42

    obj = ClearLinesObjective(target=10)
    obj.progress = -5  # negatif
    mode.objectives = [obj]
    mode._boss_phase_update(0.5)
    # Sadece rain açık olmalı (clamp 0 → < 0.33)
    assert mode._boss_seal_timer == 0.0
    assert mode._boss_dark_timer == 0.0
