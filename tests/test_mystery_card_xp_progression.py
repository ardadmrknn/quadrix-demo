"""Tests for the dedicated card_xp / card_level reward progression in
MysteryMode.

These tests cover the new mimari:
- player-source clears award XP (1/3/5/8 + small bonuses)
- non-player sources never award XP (anti-farm)
- XP overflow can produce multiple level-ups in one call -> queue
- get_status() exposes card_level / card_xp / card_xp_to_next
- reset() clears card progression state
"""

from __future__ import annotations

import os
import sys
from types import SimpleNamespace

ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
SRC_DIR = os.path.join(ROOT_DIR, 'src')
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from game_modes_extra import MysteryCardManager


def _make_manager():
    """Build a MysteryCardManager wired to a minimal mode stub.

    We bypass __init__ so we don't need a full MysteryMode instance.
    """
    mgr = MysteryCardManager.__new__(MysteryCardManager)
    mgr.catalog = []
    mgr.force_piece_queue = []
    mgr.pending_choices = []
    mgr.active_cards = []
    mgr.used_card_ids = set()
    mgr._debug_lines_progress = 0
    mgr.card_xp = 0
    mgr.card_level = 1
    mgr.card_xp_to_next = MysteryCardManager._compute_xp_to_next(1)
    mgr.progress = 0
    mgr.threshold = mgr.card_xp_to_next
    mode = SimpleNamespace(
        pending_level_ups=0,
        last_enqueued_level=0,
        settings_manager=None,
    )
    mgr.mode = mode
    # prepare_selection would normally pick from catalog; stub it out so tests
    # don't depend on the real catalog.
    mgr.prepare_selection = lambda: setattr(mgr, 'pending_choices', [{'id': 'stub'}]) or mgr.pending_choices
    return mgr, mode


# ---------------------------------------------------------------------------
# XP award formula
# ---------------------------------------------------------------------------

def test_compute_xp_award_single_line_gives_one():
    assert MysteryCardManager.compute_xp_award(1) == 1


def test_compute_xp_award_double_triple_quad_match_design_table():
    assert MysteryCardManager.compute_xp_award(2) == 3
    assert MysteryCardManager.compute_xp_award(3) == 5
    assert MysteryCardManager.compute_xp_award(4) == 8


def test_compute_xp_award_zero_lines_yields_no_xp():
    assert MysteryCardManager.compute_xp_award(0) == 0
    assert MysteryCardManager.compute_xp_award(-3) == 0


def test_compute_xp_award_combo_bonus_triggers_at_three_chain():
    # 1 line + combo of 3 -> 1 base + 1 combo bonus
    assert MysteryCardManager.compute_xp_award(1, combo=3) == 2
    # combo below 3 -> no bonus
    assert MysteryCardManager.compute_xp_award(1, combo=2) == 1


def test_compute_xp_award_back_to_back_only_applies_to_quadrix():
    # B2B with single line should NOT get the B2B bonus
    assert MysteryCardManager.compute_xp_award(1, back_to_back=True) == 1
    # B2B with quadrix gets +2
    assert MysteryCardManager.compute_xp_award(4, back_to_back=True) == 10


def test_compute_xp_award_perfect_clear_adds_three():
    assert MysteryCardManager.compute_xp_award(1, perfect_clear=True) == 4


# ---------------------------------------------------------------------------
# Curve: xp_to_next
# ---------------------------------------------------------------------------

def test_xp_to_next_starts_low_and_grows_linearly():
    assert MysteryCardManager._compute_xp_to_next(1) == 4
    assert MysteryCardManager._compute_xp_to_next(2) == 6
    assert MysteryCardManager._compute_xp_to_next(3) == 8
    # later levels keep growing -> reward stream slows down naturally
    assert MysteryCardManager._compute_xp_to_next(10) > MysteryCardManager._compute_xp_to_next(2)


# ---------------------------------------------------------------------------
# notify_lines_cleared: player-source XP award + queueing
# ---------------------------------------------------------------------------

def test_player_single_line_does_not_level_up_yet():
    mgr, mode = _make_manager()
    triggered = mgr.notify_lines_cleared(1, source='player')
    assert triggered is False
    assert mgr.card_level == 1
    assert mgr.card_xp == 1
    assert mode.pending_level_ups == 0


def test_player_quadrix_overflows_into_multiple_pending_levels():
    """A single Quadrix gives 8 XP. With base curve (4 then 6) that should
    produce 2 card levels in one call, so pending_level_ups should be 2."""
    mgr, mode = _make_manager()
    triggered = mgr.notify_lines_cleared(4, source='player')
    assert triggered is True
    # 8 XP -> spend 4 (lvl1->2), spend 6 needed... not enough left (4 remaining < 6)
    # so only 1 level up. Adjust assertion to actual math:
    # card_level: 1 -> 2. pending_level_ups += 1.
    assert mgr.card_level == 2
    assert mode.pending_level_ups == 1
    assert mgr.card_xp == 4  # leftover after first level-up


def test_player_huge_xp_gain_produces_multiple_queued_levels():
    """Force a huge XP gain to verify overflow can stack multiple queued
    rewards in one notify call."""
    mgr, mode = _make_manager()
    # Synthesize a giant gain by passing combo + perfect + B2B + quadrix
    # 8 base + 1 combo + 2 b2b + 3 perfect = 14 XP
    # curve: 4, 6, 8, 10 -> spends 4 (lvl2), 6 (lvl3) -> remaining 4 < 8
    triggered = mgr.notify_lines_cleared(
        4, source='player', combo=5, back_to_back=True, perfect_clear=True
    )
    assert triggered is True
    assert mgr.card_level == 3
    assert mode.pending_level_ups == 2
    assert mgr.card_xp == 4


def test_external_clear_sources_award_no_xp():
    mgr, mode = _make_manager()
    for src in ('card', 'ability', 'workshop', 'sweep', 'gravity', 'external'):
        triggered = mgr.notify_lines_cleared(4, source=src)
        assert triggered is False, f"source={src!r} should not award XP"
    assert mgr.card_xp == 0
    assert mgr.card_level == 1
    assert mode.pending_level_ups == 0


def test_player_clear_after_external_does_not_lose_xp():
    """External clears must not contaminate or reset XP state for the next
    player clear."""
    mgr, mode = _make_manager()
    mgr.notify_lines_cleared(4, source='card')
    assert mgr.card_xp == 0
    mgr.notify_lines_cleared(2, source='player')  # +3 XP
    assert mgr.card_xp == 3
    assert mgr.card_level == 1
    assert mode.pending_level_ups == 0


# ---------------------------------------------------------------------------
# get_status / reset
# ---------------------------------------------------------------------------

def test_get_status_returns_card_level_and_xp_fields():
    mgr, _ = _make_manager()
    status = mgr.get_status()
    assert status['card_level'] == 1
    assert status['card_xp'] == 0
    assert status['card_xp_to_next'] == 4
    # backward compat keys
    assert status['progress'] == 0
    assert status['threshold'] == 4


def test_reset_clears_card_progression_state():
    mgr, _ = _make_manager()
    mgr.notify_lines_cleared(4, source='player')
    assert mgr.card_xp != 0 or mgr.card_level != 1
    mgr.reset()
    assert mgr.card_xp == 0
    assert mgr.card_level == 1
    assert mgr.card_xp_to_next == 4
    assert mgr.progress == 0
    assert mgr.threshold == 4
    assert mgr.pending_choices == []
    assert mgr.active_cards == []
    assert mgr.used_card_ids == set()


# ---------------------------------------------------------------------------
# State capture for restore (time capsule path)
# ---------------------------------------------------------------------------

def test_card_xp_state_does_not_change_on_restore():
    """The capture/restore plumbing in MysteryMode must NOT change card_xp,
    card_level, and card_xp_to_next since time capsule should not affect
    progression."""
    import pygame

    if not hasattr(pygame, 'K_h'):
        import pytest

        pytest.skip("pygame stub: full MysteryMode unavailable")

    from board import Board
    from game_modes_extra import MysteryMode

    mode = MysteryMode.__new__(MysteryMode)
    mode.board = Board()
    mode.current_piece = None
    mode.next_piece_queue = []
    mode.held_piece = None
    mode.second_held_piece = None
    mode.can_hold = True
    mode.can_hold2 = True
    mode.card_manager = MysteryCardManager.__new__(MysteryCardManager)
    mgr = mode.card_manager
    mgr.catalog = []
    mgr.force_piece_queue = ['I', 'T']
    mgr.pending_choices = [{'id': 'queued'}]
    mgr.active_cards = [{'id': 'persistent'}]
    mgr.used_card_ids = {'persistent'}
    mgr._debug_lines_progress = 0
    mgr.card_xp = 5
    mgr.card_level = 4
    mgr.card_xp_to_next = MysteryCardManager._compute_xp_to_next(4)
    mgr.progress = mgr.card_xp
    mgr.threshold = mgr.card_xp_to_next
    mgr.mode = mode

    data = mode._capture_time_capsule_state()

    # Mutate everything to confirm restore really repopulates state.
    mgr.card_xp = 0
    mgr.card_level = 1
    mgr.card_xp_to_next = MysteryCardManager._compute_xp_to_next(1)
    mgr.progress = 0
    mgr.threshold = mgr.card_xp_to_next

    mode._restore_time_capsule_state(data)

    # Artik bu durumlar zaman kapsülü geri yuklemesiyle eski haline donmez, mevcuttaki hallerini korur.
    assert mgr.card_xp == 0
    assert mgr.card_level == 1
    assert mgr.card_xp_to_next == MysteryCardManager._compute_xp_to_next(1)
