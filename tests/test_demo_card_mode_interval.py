"""Demo build card selection / level interval davranışı.

> 2026-05-18 mystery progression API migration sonrası: Mystery kart seçimi
> artık `card_xp` tabanlıdır (board.level değil). Bu yüzden eski "her N satırda
> bir kart" testi yerine yeni canon davranışı doğrulanır:
>   - Demo build'de board level-up cadence 10 satır (`level_lines_per_level=10`).
>   - Full build'de 5 satır (`level_lines_per_level=5`).
>   - Card selection trigger bu değerden bağımsızdır; XP overflow ile çalışır.
>     Demo gating gerçek runtime'da `_mystery_level_lines_per_level` üzerinden
>     yalnızca düşüş hızını/level temposunu etkiler.
"""

from __future__ import annotations

from types import SimpleNamespace

from board import Board
import demo_config
import game_modes_extra


def _make_mode(level: int, *, lines_per_level: int = 5):
    return SimpleNamespace(
        board=SimpleNamespace(level=level, level_lines_per_level=lines_per_level),
        settings_manager=SimpleNamespace(get=lambda *_args, **_kwargs: False),
        pending_level_ups=0,
        last_enqueued_level=0,
    )


def test_board_level_progression_respects_configured_lines_per_level() -> None:
    """Board, configured `level_lines_per_level`'a göre level atlar.
    Bu, demo build'de 10 satır = 1 level, full build'de 5 satır = 1 level
    semantiğini yansıtır."""
    board = Board(width=4, height=4)
    board.level_lines_per_level = 10
    board.level_lines_cleared = 9

    board.grid[-1] = [(255, 255, 255)] * board.width
    board.texture_grid[-1] = [None] * board.width
    board.occupancy[-1] = [True] * board.width
    board.gold[-1] = [False] * board.width
    board.owners[-1] = [None] * board.width

    cleared = board.clear_lines()

    assert cleared == 1
    assert board.level_lines_cleared == 10
    assert board.level == 2


def test_demo_config_card_selection_level_interval_per_build() -> None:
    """Demo build ve full build'in card selection level interval'ı farklı.
    Bu değer artık `level_lines_per_level` board konfigürasyonu için
    kullanılır; XP-tabanlı card selection trigger'ını doğrudan etkilemez."""
    # Default IS_DEMO=False -> 5
    interval_full = demo_config.FULL_CARD_SELECTION_LEVEL_INTERVAL
    interval_demo = demo_config.DEMO_CARD_SELECTION_LEVEL_INTERVAL
    assert interval_full == 5
    assert interval_demo == 10
    assert interval_demo == 2 * interval_full, (
        'Demo build full build\'in iki katı kadar yavaş level atlamalı'
    )


def test_xp_progression_independent_of_demo_gating(monkeypatch) -> None:
    """Card XP / card level progression demo build'de de aynı XP eğrisini
    kullanır — `IS_DEMO` flag'i XP miktarını veya threshold'u etkilemez.
    Demo'nun yavaşlığı board.level cadence'inde (level_lines_per_level=10)
    kalır, kart ekonomisi uniform.
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
