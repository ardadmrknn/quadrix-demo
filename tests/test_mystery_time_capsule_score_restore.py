import types
import sys

import pygame
import pytest

_platform_utils = sys.modules.get('platform_utils')
if _platform_utils is not None and not hasattr(_platform_utils, 'get_display_scale_factor'):
    _platform_utils.get_display_scale_factor = lambda: 1.0


def _import_game_modes_extra():
    if not hasattr(pygame, 'K_c'):
        pytest.skip("pygame stub environment: MysteryMode import skipped")
    from game_modes_extra import Game, MysteryMode
    return Game, MysteryMode


class _DummyBoard:
    def __init__(self):
        self.grid = [[(0, 0, 0)]]
        self.occupancy = [[False]]
        self.texture_grid = [[None]]
        self.gold = [[False]]
        self.owners = [[None]]
        self.score = 0
        self.lines_cleared = 0
        self.level_lines_cleared = 0
        self.level = 1
        self.combo = 0


def test_restore_time_capsule_only_restores_board_blocks():
    _, MysteryMode = _import_game_modes_extra()
    mode = MysteryMode.__new__(MysteryMode)
    mode.board = _DummyBoard()
    mode.board.score = 7777
    mode.time_capsule_available = True
    mode.time_capsule_saved = True
    mode.time_capsule_data = {
        'board_grid': [[(1, 1, 1)]],
        'board_occupancy': [[True]],
        'board_texture_grid': [[None]],
        'board_gold': [[False]],
        'board_owners': [[None]],
    }
    mode.current_piece = None
    mode.next_piece_queue = []
    mode.held_piece = "HOLD_A"
    mode.can_hold = False
    mode._active_effect_visuals = {'time_capsule': {'id': 'time_capsule'}}
    mode.sound_enabled = False

    mode._rebuild_active_effect_visuals = lambda: None
    mode._sync_active_cards = lambda: None
    mode.apply_theme_to_pieces = lambda: None

    ok = mode._restore_time_capsule()

    assert ok is True
    assert mode.board.score == 7777
    assert mode.held_piece == "HOLD_A"
    assert mode.can_hold is False
    assert mode.time_capsule_available is False
    assert mode.time_capsule_saved is False


def test_handle_input_r_consumes_event_without_reposting(monkeypatch):
    Game, MysteryMode = _import_game_modes_extra()
    mode = MysteryMode.__new__(MysteryMode)
    mode.card_selection_active = False
    mode._piece_selection_active = False
    mode._card_workshop_active = False
    mode._sniper_overlay_active = False
    mode._drill_movement_locked = False
    mode.current_piece = None
    mode.game_over = False
    mode.paused = False
    mode.control_bindings = {'rotate': pygame.K_UP}

    toggle_calls = []
    mode._toggle_time_capsule = lambda: (toggle_calls.append(1) or True)
    mode._do_rewind = lambda: False
    mode._open_sniper_overlay = lambda: False

    event = types.SimpleNamespace(type=pygame.KEYDOWN, key=pygame.K_r)
    posted_events = []

    monkeypatch.setattr(Game, 'handle_input', lambda self: True)
    monkeypatch.setattr(pygame.event, 'get', lambda: [event])
    monkeypatch.setattr(pygame.event, 'post', lambda e: posted_events.append(e))

    result = mode.handle_input()

    assert result is True
    assert toggle_calls == [1]
    assert posted_events == []
