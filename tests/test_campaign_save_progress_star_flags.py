"""Faz 3 — Save format star_flags (1+3 senaryosu için bireysel flag'ler).

Karma yıldız modelinde her slot bağımsız değerlendirilir. Save'e bireysel
flag'ler yazılır; eski save'lerde alan yoksa cumulatif fallback yapılır.
"""
from __future__ import annotations

import pathlib
import sys


ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / 'src'

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from campaign.campaign_mode import CampaignMode


class _FakeUserManager:
    def __init__(self, initial=None):
        import copy
        self.progress = copy.deepcopy(initial) if isinstance(initial, dict) else {}

    def get_campaign_progress(self):
        import copy
        return copy.deepcopy(self.progress)

    def save_campaign_progress(self, progress):
        import copy
        self.progress = copy.deepcopy(progress)


class _FakeSettingsManager:
    def save(self):
        pass


def _make_mode_with_conditions(level_num=5, condition_results=None, score=1500):
    """condition_results: {1: bool, 2: bool, 3: bool}"""
    mode = object.__new__(CampaignMode)
    mode.current_level_num = level_num
    mode.user_manager = _FakeUserManager()
    mode.settings_manager = _FakeSettingsManager()
    mode.achievement_manager = None
    mode.achievement_notifications = []
    mode.earned_stars = sum(1 for v in (condition_results or {}).values() if v)
    mode.board = type('B', (), {'score': score})()

    cr = condition_results or {1: False, 2: False, 3: False}
    mode.star_conditions = {
        1: {'type': '_test_1', 'value': 0},
        2: {'type': '_test_2', 'value': 0},
        3: {'type': '_test_3', 'value': 0},
    }
    # Stub _is_star_condition_met
    mode._is_star_condition_met = lambda cond: cr.get(int(cond.get('type', '_test_0').split('_')[-1] or 0), False)
    return mode


def test_save_writes_star_flags_for_first_clear():
    """İlk geçişte star_flags doğru kaydedilir."""
    mode = _make_mode_with_conditions(level_num=5, condition_results={1: True, 2: False, 3: True})
    CampaignMode._save_progress(mode)
    saved = mode.user_manager.progress['completed_levels']['5']
    assert 'star_flags' in saved
    assert saved['star_flags']['1'] is True
    assert saved['star_flags']['2'] is False
    assert saved['star_flags']['3'] is True


def test_save_star_flags_preserves_previous_run_flags():
    """OR semantik: önceki run'da kazandığı flag'ler korunur, yenileri eklenir."""
    initial = {
        'completed_levels': {
            '5': {
                'stars': 2, 'best_score': 800, 'completed': True,
                'attempts': 1, 'fail_attempts': 0,
                'star_flags': {'1': True, '2': True, '3': False},
            }
        }
    }
    mode = _make_mode_with_conditions(
        level_num=5,
        condition_results={1: True, 2: False, 3: True},
        score=900,
    )
    mode.user_manager = _FakeUserManager(initial=initial)

    CampaignMode._save_progress(mode)
    saved = mode.user_manager.progress['completed_levels']['5']
    # 1: önceki + bu run = True; 2: önceki True kalır; 3: bu run True
    assert saved['star_flags']['1'] is True
    assert saved['star_flags']['2'] is True, "Önceki run'da kazanılan 2. yıldız korunmalı"
    assert saved['star_flags']['3'] is True


def test_save_star_flags_zero_when_first_star_not_met():
    """1. yıldız sağlanmadıysa hiçbir flag set edilmez (karma model)."""
    mode = _make_mode_with_conditions(
        level_num=5,
        condition_results={1: False, 2: True, 3: True},
    )
    CampaignMode._save_progress(mode)
    saved = mode.user_manager.progress['completed_levels']['5']
    # 1 sağlanmadıysa hiçbiri set edilmez
    assert saved['star_flags']['1'] is False
    assert saved['star_flags']['2'] is False
    assert saved['star_flags']['3'] is False
