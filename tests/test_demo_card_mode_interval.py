"""Demo Mystery progression, ana oyundaki XP ekonomisiyle hizali kalmali."""

from __future__ import annotations

from types import SimpleNamespace

import game_modes_extra


def _make_mode(level: int, *, lines_per_level: int = 5):
    return SimpleNamespace(
        board=SimpleNamespace(level=level, level_lines_per_level=lines_per_level),
        settings_manager=SimpleNamespace(get=lambda *_args, **_kwargs: False),
        pending_level_ups=0,
        last_enqueued_level=0,
    )


def test_xp_progression_independent_of_demo_gating(monkeypatch) -> None:
    """Card XP / card level progression demo build'de de aynı XP eğrisini
    kullanır; demo/full farkı kart ekonomisini etkilemez.
    """
    monkeypatch.setattr(game_modes_extra.MysteryCardManager, '_build_catalog', lambda self: [{'id': 'demo'}])

    # Full build
    monkeypatch.setattr(game_modes_extra.demo_config, 'IS_DEMO', False)
    mgr_full = game_modes_extra.MysteryCardManager(_make_mode(1, lines_per_level=5))
    mgr_full.prepare_selection = lambda: [{'id': 'demo'}]
    assert mgr_full.card_xp_to_next == 4  # BASE_XP_TO_NEXT

    # Demo build: same XP economy
    monkeypatch.setattr(game_modes_extra.demo_config, 'IS_DEMO', True)
    mgr_demo = game_modes_extra.MysteryCardManager(_make_mode(1, lines_per_level=10))
    mgr_demo.prepare_selection = lambda: [{'id': 'demo'}]
    assert mgr_demo.card_xp_to_next == 4  # Same as full

    # Single-line player clear: 1 XP. 4 single-line clears => 1 level up
    # (regardless of demo/full).
    for _ in range(3):
        assert mgr_demo.notify_lines_cleared(1, source='player') is False
    assert mgr_demo.notify_lines_cleared(1, source='player') is True
    assert mgr_demo.card_level == 2
    assert mgr_demo.mode.pending_level_ups == 1
    assert mgr_demo.mode.last_enqueued_level == 2


def test_external_clears_do_not_award_xp_in_demo(monkeypatch) -> None:
    """Anti-farm: demo build'de de external/card kaynaklı clear'lar XP vermez.
    AGENTS.md §7 invariant 2 demo build için de geçerli."""
    monkeypatch.setattr(game_modes_extra.demo_config, 'IS_DEMO', True)
    monkeypatch.setattr(game_modes_extra.MysteryCardManager, '_build_catalog', lambda self: [{'id': 'demo'}])

    mgr = game_modes_extra.MysteryCardManager(_make_mode(1, lines_per_level=10))
    mgr.prepare_selection = lambda: [{'id': 'demo'}]

    for src in ('card', 'ability', 'workshop', 'sweep', 'gravity', 'external'):
        assert mgr.notify_lines_cleared(4, source=src) is False, f'source={src!r} should not award XP'

    assert mgr.card_xp == 0
    assert mgr.card_level == 1
    assert mgr.mode.pending_level_ups == 0
