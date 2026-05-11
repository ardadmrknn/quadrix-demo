from __future__ import annotations

from types import SimpleNamespace

from board import Board
import game_modes_extra


def _make_mode(level: int, *, lines_per_level: int = 5):
    return SimpleNamespace(
        board=SimpleNamespace(level=level, level_lines_per_level=lines_per_level),
        settings_manager=SimpleNamespace(get=lambda *_args, **_kwargs: False),
    )


def test_board_level_progression_respects_configured_lines_per_level() -> None:
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


def test_full_build_card_selection_triggers_every_five_lines(monkeypatch) -> None:
    monkeypatch.setattr(game_modes_extra.demo_config, 'IS_DEMO', False)
    monkeypatch.setattr(game_modes_extra.MysteryCardManager, '_build_catalog', lambda self: [{'id': 'demo'}])

    manager = game_modes_extra.MysteryCardManager(_make_mode(1, lines_per_level=5))
    manager.prepare_selection = lambda: [{'id': 'demo'}]

    assert manager.notify_lines_cleared(4) is False

    manager.mode.board.level = 2
    assert manager.notify_lines_cleared(1) is True

    assert manager.notify_lines_cleared(4) is False

    manager.mode.board.level = 3
    assert manager.notify_lines_cleared(1) is True


def test_demo_build_card_selection_triggers_every_ten_lines(monkeypatch) -> None:
    monkeypatch.setattr(game_modes_extra.demo_config, 'IS_DEMO', True)
    monkeypatch.setattr(game_modes_extra.MysteryCardManager, '_build_catalog', lambda self: [{'id': 'demo'}])

    manager = game_modes_extra.MysteryCardManager(_make_mode(1, lines_per_level=10))
    manager.prepare_selection = lambda: [{'id': 'demo'}]

    assert manager.notify_lines_cleared(9) is False

    manager.mode.board.level = 2
    assert manager.notify_lines_cleared(1) is True

    assert manager.notify_lines_cleared(9) is False

    manager.mode.board.level = 3
    assert manager.notify_lines_cleared(1) is True