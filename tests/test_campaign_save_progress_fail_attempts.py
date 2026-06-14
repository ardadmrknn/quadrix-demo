"""Faz 1 — Fail attempts sayma davranışı.

_record_fail_attempt fail edilen denemeleri ayrı 'fail_attempts' alanında
sayar. _save_progress success attempts'i ayrı tutmaya devam eder.
First-clear / improvement flag'leri _last_run_flags'da expose edilir.
"""
from __future__ import annotations

import pathlib
import sys


ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / 'src'

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import pygame

from campaign.campaign_mode import CampaignMode


class _FakeUserManager:
    def __init__(self, initial=None):
        self.progress = initial if isinstance(initial, dict) else {}
        self.save_calls = 0

    def get_campaign_progress(self):
        # Deep-copy semantik: caller değişkliklerini yansıtmamalı
        import copy
        return copy.deepcopy(self.progress)

    def save_campaign_progress(self, progress):
        self.save_calls += 1
        import copy
        self.progress = copy.deepcopy(progress)


class _FakeSettingsManager:
    def __init__(self):
        self.save_calls = 0

    def save(self):
        self.save_calls += 1


def _make_mode_for_progress(level_num=5, initial_progress=None, achievement_manager=None):
    mode = object.__new__(CampaignMode)
    mode.current_level_num = level_num
    mode.user_manager = _FakeUserManager(initial=initial_progress)
    mode.settings_manager = _FakeSettingsManager()
    mode.achievement_manager = achievement_manager
    mode.achievement_notifications = []
    mode.earned_stars = 2
    mode.board = type('Board', (), {'score': 1500})()
    # Faz 3: _save_progress içinde star_conditions iterate ediliyor;
    # minimal stub yeterli.
    mode.star_conditions = {
        1: {'type': '_test', 'value': 1},
        2: {'type': '_test', 'value': 2},
        3: {'type': '_test', 'value': 3},
    }
    mode._is_star_condition_met = lambda cond: False
    return mode


def test_record_fail_attempt_increments_fail_counter():
    """Fail edildiğinde fail_attempts +1 olmalı, attempts (success) etkilenmemeli."""
    mode = _make_mode_for_progress(level_num=5, initial_progress={
        'completed_levels': {
            '5': {'stars': 0, 'best_score': 0, 'completed': False, 'attempts': 0, 'fail_attempts': 2}
        }
    })

    CampaignMode._record_fail_attempt(mode)
    saved = mode.user_manager.progress['completed_levels']['5']
    assert saved['fail_attempts'] == 3
    assert saved['attempts'] == 0  # success attempts değişmedi


def test_record_fail_attempt_creates_entry_for_unseen_level():
    """Daha önce hiç oynanmamış levelda fail → yeni entry, fail_attempts=1."""
    mode = _make_mode_for_progress(level_num=7, initial_progress={'completed_levels': {}})

    CampaignMode._record_fail_attempt(mode)
    saved = mode.user_manager.progress['completed_levels']['7']
    assert saved['fail_attempts'] == 1
    assert saved['attempts'] == 0
    assert saved['completed'] is False
    assert saved['stars'] == 0


def test_save_progress_increments_only_success_attempts():
    """3 fail + 1 success → fail_attempts=3, attempts=1."""
    mode = _make_mode_for_progress(level_num=5, initial_progress={
        'completed_levels': {
            '5': {'stars': 0, 'best_score': 0, 'completed': False, 'attempts': 0, 'fail_attempts': 3}
        }
    })

    CampaignMode._save_progress(mode)
    saved = mode.user_manager.progress['completed_levels']['5']
    assert saved['attempts'] == 1
    assert saved['fail_attempts'] == 3


def test_save_progress_exposes_first_clear_flag():
    """İlk geçişte _last_run_flags['first_clear'] True olmalı."""
    mode = _make_mode_for_progress(level_num=5, initial_progress={'completed_levels': {}})

    CampaignMode._save_progress(mode)
    flags = getattr(mode, '_last_run_flags', None)
    assert flags is not None
    assert flags['first_clear'] is True
    assert flags['previous_stars'] == 0


def test_save_progress_exposes_star_improvement_flag():
    """Daha az yıldız → daha fazla yıldız geçişinde star_improvement True."""
    mode = _make_mode_for_progress(level_num=5, initial_progress={
        'completed_levels': {
            '5': {'stars': 1, 'best_score': 500, 'completed': True, 'attempts': 1, 'fail_attempts': 0}
        }
    })
    mode.earned_stars = 3
    mode.board = type('Board', (), {'score': 600})()

    CampaignMode._save_progress(mode)
    flags = getattr(mode, '_last_run_flags', None)
    assert flags['first_clear'] is False
    assert flags['star_improvement'] is True
    assert flags['previous_stars'] == 1


def test_save_progress_exposes_score_improvement_flag():
    """Skor iyileştirmesi → score_improvement True."""
    mode = _make_mode_for_progress(level_num=5, initial_progress={
        'completed_levels': {
            '5': {'stars': 2, 'best_score': 800, 'completed': True, 'attempts': 1, 'fail_attempts': 0}
        }
    })
    mode.earned_stars = 2
    mode.board = type('Board', (), {'score': 900})()

    CampaignMode._save_progress(mode)
    flags = getattr(mode, '_last_run_flags', None)
    assert flags['first_clear'] is False
    assert flags['star_improvement'] is False
    assert flags['score_improvement'] is True
    assert flags['previous_score'] == 800


def test_save_progress_keeps_max_stars_and_score():
    """Mevcut stars/score daha iyiyse koruma."""
    mode = _make_mode_for_progress(level_num=5, initial_progress={
        'completed_levels': {
            '5': {'stars': 3, 'best_score': 9999, 'completed': True, 'attempts': 5, 'fail_attempts': 1}
        }
    })
    mode.earned_stars = 1
    mode.board = type('Board', (), {'score': 100})()

    CampaignMode._save_progress(mode)
    saved = mode.user_manager.progress['completed_levels']['5']
    assert saved['stars'] == 3  # max korundu
    assert saved['best_score'] == 9999  # max korundu
    assert saved['attempts'] == 6  # +1 success
    assert saved['fail_attempts'] == 1
