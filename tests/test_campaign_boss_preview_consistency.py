"""Faz 3 — get_boss_type_for_level merkezi fonksiyon doğrulaması.

Single source of truth: hem CampaignMode._boss_get_type hem level_select
bu fonksiyonu kullanır. Test, fonksiyonun doğru çıktı vermesini ve
CampaignMode delegasyonunun aynı sonucu döndürmesini doğrular.
"""
from __future__ import annotations

import pathlib
import sys


ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / 'src'

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from campaign.level_data import get_boss_type_for_level
from campaign.campaign_mode import CampaignMode


def test_get_boss_type_for_level_normal_levels_return_none():
    """Normal levellar (boss/mini-boss değil) None döner."""
    for lv in [1, 2, 3, 4, 6, 7, 8, 9, 11, 12, 13, 14, 16, 17, 18, 19, 99]:
        assert get_boss_type_for_level(lv) is None, f"L{lv} None bekleniyor"


def test_get_boss_type_for_level_boss_rotation():
    """Boss rotation: 10/40/70 rain, 20/50/80 seal, 30/60/90 dark."""
    rain = [10, 40, 70]
    seal = [20, 50, 80]
    dark = [30, 60, 90]
    for lv in rain:
        assert get_boss_type_for_level(lv) == 'rain', f"L{lv} rain bekleniyor"
    for lv in seal:
        assert get_boss_type_for_level(lv) == 'seal', f"L{lv} seal bekleniyor"
    for lv in dark:
        assert get_boss_type_for_level(lv) == 'dark', f"L{lv} dark bekleniyor"


def test_get_boss_type_for_level_final():
    """Level 100 → 'final'."""
    assert get_boss_type_for_level(100) == 'final'


def test_get_boss_type_for_level_mini_boss_rotation():
    """Mini-boss rotation: 5/25/45/65/85 fast, 15/35/55/75/95 missing."""
    fast = [5, 25, 45, 65, 85]
    missing = [15, 35, 55, 75, 95]
    for lv in fast:
        assert get_boss_type_for_level(lv) == 'fast', f"L{lv} fast bekleniyor"
    for lv in missing:
        assert get_boss_type_for_level(lv) == 'missing', f"L{lv} missing bekleniyor"


def test_campaign_mode_delegates_to_get_boss_type_for_level():
    """CampaignMode._boss_get_type ile direkt çağrı aynı sonucu verir."""
    for level_num in range(1, 101):
        mode = object.__new__(CampaignMode)
        mode.current_level_num = level_num
        last_digit = level_num % 10
        mode.is_mini_boss = (last_digit == 5)
        mode.is_boss = (last_digit == 0 and level_num > 0)

        delegated = mode._boss_get_type()
        direct = get_boss_type_for_level(level_num)
        assert delegated == direct, (
            f"L{level_num}: delegasyon ({delegated}) ≠ direkt ({direct})"
        )


def test_get_boss_type_for_level_handles_zero_safely():
    """Level 0 (geçersiz) → None (defansif)."""
    assert get_boss_type_for_level(0) is None
