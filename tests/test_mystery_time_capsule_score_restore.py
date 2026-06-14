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


def test_restore_time_capsule_restores_board_and_gameplay_state():
    _, MysteryMode = _import_game_modes_extra()
    mode = MysteryMode.__new__(MysteryMode)
    mode.board = _DummyBoard()
    mode.board.score = 7777
    mode.board.lines_cleared = 88
    mode.board.level_lines_cleared = 7
    mode.board.level = 5
    mode.board.combo = 3
    mode.time_capsule_available = True
    mode.time_capsule_saved = True
    mode.time_capsule_data = {
        'board_grid': [[(1, 1, 1)]],
        'board_occupancy': [[True]],
        'board_texture_grid': [[None]],
        'board_gold': [[False]],
        'board_owners': [[None]],
        'board_score': 1234,
        'board_lines_cleared': 12,
        'board_level_lines_cleared': 2,
        'board_level': 3,
        'board_combo': 1,
        'current_piece': 'CURRENT_SAVED',
        'next_piece_queue': ['NEXT_A', 'NEXT_B'],
        'held_piece': 'HOLD_SAVED',
        'can_hold': True,
        'energy': 42,
    }
    mode.current_piece = None
    mode.next_piece_queue = []
    mode.held_piece = "HOLD_A"
    mode.can_hold = False
    mode.energy = 5
    mode._active_effect_visuals = {'time_capsule': {'id': 'time_capsule'}}
    mode.sound_enabled = False

    mode._rebuild_active_effect_visuals = lambda: None
    mode._sync_active_cards = lambda: None
    mode.apply_theme_to_pieces = lambda: None

    ok = mode._restore_time_capsule()

    assert ok is True
    # Skor zaman kapsulu geri yuklemesinden ETKILENMEZ: kaydedilen ana donmez,
    # mevcut skor korunur.
    assert mode.board.score == 7777
    assert mode.board.lines_cleared == 12
    assert mode.board.level_lines_cleared == 2
    assert mode.board.level == 3
    assert mode.board.combo == 1
    assert mode.current_piece == 'CURRENT_SAVED'
    assert mode.next_piece_queue == ['NEXT_A', 'NEXT_B']
    assert mode.held_piece == "HOLD_SAVED"
    assert mode.can_hold is True
    assert mode.energy == 42
    assert mode.time_capsule_available is False
    assert mode.time_capsule_saved is False


def test_speed_burst_expiry_resets_state_and_clears_visual():
    _, MysteryMode = _import_game_modes_extra()
    mode = MysteryMode.__new__(MysteryMode)
    mode._score_multiplier_timer = 0.0
    mode._score_multiplier_value = 1.0
    mode.speed_effect_timer = 0.0
    mode.speed_effect_multiplier = 1.0
    mode.combo_aura_timer = 0.0
    mode.combo_aura_bonus = 0
    mode.time_warp_timer = 0.0
    mode.gravity_freeze_timer = 0.0
    mode._speed_burst_timer = 0.05
    mode._speed_burst_speed_mult = 1.4
    mode._speed_burst_line_mult = 1.5
    mode._active_effect_visuals = {
        'speed_burst': {
            'title': 'Hız Patlaması',
            'color': (255, 180, 50),
            'icon': '⚡',
            'tag': 'Epic',
            'rarity': 'epic',
            'style': {},
            'icon_image': None,
            'value': 30,
            'payload': {'speed_multiplier': 1.4, 'line_multiplier': 1.5},
        }
    }
    mode.card_manager = types.SimpleNamespace(active_cards=[], catalog=[], force_piece_queue=[])
    mode.line_bonus_remaining = 0
    mode.line_bonus_amount = 0
    mode._line_clear_multiplier_remaining = 0
    mode._line_clear_multiplier_value = 1.0
    mode._armed_nova_clusters = 0
    mode.tunnel_charges_remaining = 0
    mode.current_piece = None
    mode.hammer_charges_remaining = 0
    mode.bomb_master_charges = 0
    mode._hold_destroyer_charges = 0
    mode._freeze_drop_charges = 0
    mode._freeze_drop_active = False
    mode._sniper_charges = 0
    mode.time_capsule_available = False
    mode.time_capsule_saved = False
    mode.phase_shift_uses_remaining = 0
    mode.perk_manager = types.SimpleNamespace(
        is_active=lambda _key: False,
        get_multiplier=lambda: 1.0,
        rewind_uses=0,
    )
    mode.get_current_speed = lambda: 900
    mode.fall_speed = 600

    mode._update_effect_timers(100)

    assert mode._speed_burst_timer == 0
    assert mode._speed_burst_speed_mult == 1.0
    assert mode._speed_burst_line_mult == 1.0
    assert mode.fall_speed == 900
    assert isinstance(mode._active_effect_visuals, dict)
    assert 'speed_burst' not in mode._active_effect_visuals
    assert mode.card_manager.active_cards == []


def test_handle_input_t_saves_time_capsule_and_consumes_event_without_reposting(monkeypatch):
    Game, MysteryMode = _import_game_modes_extra()
    import game_modes_extra as game_modes_module

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

    save_calls = []
    restore_calls = []
    mode._save_time_capsule = lambda: (save_calls.append(1) or True)
    mode._restore_time_capsule = lambda: (restore_calls.append(1) or True)
    mode._do_rewind = lambda: False
    mode._open_sniper_overlay = lambda: False

    event = types.SimpleNamespace(type=game_modes_module.pygame.KEYDOWN, key=game_modes_module.pygame.K_t)
    posted_events = []

    monkeypatch.setattr(Game, 'handle_input', lambda self: True)
    monkeypatch.setattr('game_modes_extra.get_gamepad_manager', lambda: types.SimpleNamespace(enabled=False))
    monkeypatch.setattr(game_modes_module.pygame.event, 'get', lambda: [event])
    monkeypatch.setattr(game_modes_module.pygame.event, 'post', lambda e: posted_events.append(e))

    result = mode.handle_input()

    assert result is True
    assert save_calls == [1]
    assert restore_calls == []
    assert posted_events == []


def test_handle_input_r_restores_time_capsule_and_consumes_event_without_reposting(monkeypatch):
    Game, MysteryMode = _import_game_modes_extra()
    import game_modes_extra as game_modes_module

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

    save_calls = []
    restore_calls = []
    mode._save_time_capsule = lambda: (save_calls.append(1) or True)
    mode._restore_time_capsule = lambda: (restore_calls.append(1) or True)
    mode._do_rewind = lambda: False
    mode._open_sniper_overlay = lambda: False

    event = types.SimpleNamespace(type=game_modes_module.pygame.KEYDOWN, key=game_modes_module.pygame.K_r)
    posted_events = []

    monkeypatch.setattr(Game, 'handle_input', lambda self: True)
    monkeypatch.setattr('game_modes_extra.get_gamepad_manager', lambda: types.SimpleNamespace(enabled=False))
    monkeypatch.setattr(game_modes_module.pygame.event, 'get', lambda: [event])
    monkeypatch.setattr(game_modes_module.pygame.event, 'post', lambda e: posted_events.append(e))

    result = mode.handle_input()

    assert result is True
    assert save_calls == []
    assert restore_calls == [1]
    assert posted_events == []
