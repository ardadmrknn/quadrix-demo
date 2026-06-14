from __future__ import annotations

from types import SimpleNamespace

import pygame
import pytest


def _import_mystery_mode():
    if not hasattr(pygame, 'K_h'):
        pytest.skip('pygame stub environment: MysteryMode import skipped')
    import game_modes_extra as extra
    from board import Board

    return extra, extra.Game, extra.MysteryMode, Board


class _FakeKeys:
    def __init__(self, pressed: set[int]) -> None:
        self.pressed = set(pressed)

    def __getitem__(self, key: int) -> bool:
        return int(key) in self.pressed

    def __len__(self) -> int:
        return 65536


def _minimal_mode(MysteryMode):
    mode = MysteryMode.__new__(MysteryMode)
    mode.card_selection_active = False
    mode._piece_selection_active = False
    mode._card_workshop_active = False
    mode._sniper_overlay_active = False
    mode._drill_movement_locked = False
    mode.current_piece = SimpleNamespace(drill=False, is_bomb=False)
    mode.game_over = False
    mode.paused = False
    mode.control_bindings = {
        'move_left': pygame.K_LEFT,
        'move_right': pygame.K_RIGHT,
        'soft_drop': pygame.K_DOWN,
        'rotate': pygame.K_UP,
        'hard_drop': pygame.K_SPACE,
        'hold': pygame.K_c,
        'hold2': pygame.K_v,
    }
    mode.alt_control_bindings = {}
    mode._try_open_debug_workshop_from_key = lambda _event: False
    mode._do_rewind = lambda: False
    mode._open_sniper_overlay = lambda: False
    mode._save_time_capsule = lambda: False
    mode._restore_time_capsule = lambda: False
    return mode


def _minimal_card_effect_mode(MysteryMode, Board, *, effects_enabled: bool):
    mode = MysteryMode.__new__(MysteryMode)
    mode.board = Board(width=4, height=6)
    mode.sound_enabled = False
    mode.effects_enabled = effects_enabled
    mode.card_selection_active = False
    mode.game_over = False
    mode.paused = False
    mode.energy = 0
    mode.energy_max = 100
    mode.pending_level_ups = 0
    mode.board_width = mode.board.width
    mode.line_clear_sweep_active = False
    mode.line_clear_sweep_rows = []
    mode.line_clear_sweep_progress = 0.0
    mode.line_clear_pending_rows = []
    mode.line_clear_pending_colors = {}
    mode.line_clear_wave_effects = []
    mode.line_clear_animation = 0
    mode.line_clear_flash = False
    mode.falling_block_animations = []
    mode._card_board_effects = []
    mode._open_card_selection = lambda: None
    mode._apply_line_bonus_reward = lambda _lines: None
    mode._apply_score_multiplier_to_delta = lambda _delta: 0
    mode._apply_line_clear_multiplier_to_delta = lambda _cleared, _delta: 0
    mode._set_localized_card_message = lambda *_args, **_kwargs: ''
    mode.perk_manager = SimpleNamespace(
        get_multiplier=lambda: 1.0,
        notify_lines_cleared=lambda _lines, source='player': None,
    )
    mode.card_manager = SimpleNamespace(
        progress=0,
        threshold=5,
        pending_choices=[],
        notify_lines_cleared=lambda _lines, **_kwargs: False,
        used_card_ids=set(),
    )
    mode.get_cell_size = lambda: 10
    mode.get_board_offset = lambda: (0, 0)
    mode.create_line_clear_particles = lambda *_args, **_kwargs: None
    mode._start_block_fall_animation = lambda _rows: None
    mode.trigger_screen_shake = lambda **_kwargs: None
    return mode


def test_freeze_drop_event_filter_allows_only_lateral_and_hard_drop(monkeypatch):
    extra, Game, MysteryMode, _ = _import_mystery_mode()
    mode = _minimal_mode(MysteryMode)
    mode._freeze_drop_active = True

    rotate_event = SimpleNamespace(type=extra.pygame.KEYDOWN, key=extra.pygame.K_UP)
    hard_drop_event = SimpleNamespace(type=extra.pygame.KEYDOWN, key=extra.pygame.K_SPACE)
    posted_events = []

    monkeypatch.setattr(extra.pygame.event, 'get', lambda: [rotate_event, hard_drop_event])
    monkeypatch.setattr(extra.pygame.event, 'post', lambda event: posted_events.append(event))
    monkeypatch.setattr(Game, 'handle_input', lambda self: True)
    monkeypatch.setattr(
        'game_modes_extra.get_gamepad_manager',
        lambda: SimpleNamespace(enabled=False),
    )

    assert mode.handle_input() is True
    assert [event.key for event in posted_events] == [extra.pygame.K_SPACE]


def test_sniper_hotkey_consumes_event_when_overlay_opens(monkeypatch):
    extra, Game, MysteryMode, _ = _import_mystery_mode()
    mode = _minimal_mode(MysteryMode)
    mode._open_sniper_overlay = lambda: True
    event = SimpleNamespace(type=extra.pygame.KEYDOWN, key=extra.pygame.K_n)
    posted_events = []

    monkeypatch.setattr(extra.pygame.event, 'get', lambda: [event])
    monkeypatch.setattr(extra.pygame.event, 'post', lambda event: posted_events.append(event))
    monkeypatch.setattr(Game, 'handle_input', lambda self: True)
    monkeypatch.setattr(
        'game_modes_extra.get_gamepad_manager',
        lambda: SimpleNamespace(enabled=False),
    )

    assert mode.handle_input() is True
    assert posted_events == []


def test_freeze_drop_blocks_card_hotkeys_from_key_state(monkeypatch):
    extra, Game, MysteryMode, _ = _import_mystery_mode()
    mode = _minimal_mode(MysteryMode)
    mode._freeze_drop_active = True
    mode._freeze_drop_timer = 5.0
    mode.card_message_timer = 0.0
    mode.card_ui = SimpleNamespace(update=lambda *_args, **_kwargs: None)
    mode.board = SimpleNamespace(level=1)
    mode._last_ability_keys = {
        'z': False,
        'x': False,
        'g': False,
        'h': False,
        'm': False,
        'c': False,
        'rotate': False,
        'lshift': False,
        'v': False,
        'b': False,
        'f': False,
    }
    mode.energy = 100
    mode.hammer_charges_remaining = 3
    mode.time_warp_timer = 0.0
    mode.gravity_freeze_timer = 0.0
    mode.get_current_speed = lambda: 900
    mode._update_effect_timers = lambda _dt: None
    mode._sync_active_cards = lambda: None
    mode._set_localized_card_message = lambda *_args, **_kwargs: ''
    mode.sound_enabled = False
    mode.effects_enabled = False

    hammer_calls = []
    mode._hammer_current_piece_to_unit = lambda: hammer_calls.append('hammer') or True

    gamepad = SimpleNamespace(
        is_connected=lambda: False,
        is_action_pressed=lambda _action: False,
        is_direction_held=lambda _direction: False,
    )
    monkeypatch.setattr(Game, 'update', lambda self, dt: None)
    monkeypatch.setattr(extra.pygame.key, 'get_pressed', lambda: _FakeKeys({extra.pygame.K_h}))
    monkeypatch.setattr('game_modes_extra.get_gamepad_manager', lambda: gamepad)

    mode.update(16)

    assert hammer_calls == []
    assert mode.hammer_charges_remaining == 3


def test_time_capsule_captures_active_card_counters_and_manager_state():
    _, _, MysteryMode, Board = _import_mystery_mode()
    mode = MysteryMode.__new__(MysteryMode)
    mode.board = Board()
    mode.current_piece = 'CURRENT'
    mode.next_piece_queue = ['NEXT']
    mode.held_piece = 'HOLD'
    mode.second_held_piece = 'SECOND_HOLD'
    mode.can_hold = False
    mode.can_hold2 = False
    mode._speed_burst_timer = 12.5
    mode._speed_burst_speed_mult = 1.6
    mode._speed_burst_line_mult = 1.75
    mode._mirror_hold_charges = 1
    mode._echo_drop_charges = 2
    mode._echo_drop_fill_count = 3
    mode._freeze_drop_charges = 2
    mode._freeze_drop_duration = 15
    mode._freeze_drop_active = True
    mode._freeze_drop_timer = 4.0
    mode.card_manager = SimpleNamespace(
        force_piece_queue=['I', 'T'],
        progress=4,
        threshold=5,
        pending_choices=[{'id': 'clear_rows'}],
        active_cards=[{'id': 'freeze_drop'}],
        used_card_ids={'freeze_drop'},
    )

    data = mode._capture_time_capsule_state()

    mode.second_held_piece = None
    mode.can_hold2 = True
    mode._speed_burst_timer = 0.0
    mode._speed_burst_speed_mult = 1.0
    mode._speed_burst_line_mult = 1.0
    mode._mirror_hold_charges = 0
    mode._echo_drop_charges = 0
    mode._echo_drop_fill_count = 0
    mode._freeze_drop_charges = 0
    mode._freeze_drop_duration = 0
    mode._freeze_drop_active = False
    mode._freeze_drop_timer = 0.0
    mode.card_manager.force_piece_queue = []
    mode.card_manager.progress = 0
    mode.card_manager.pending_choices = []
    mode.card_manager.active_cards = []
    mode.card_manager.used_card_ids = set()

    mode._restore_time_capsule_state(data)

    assert mode.second_held_piece == 'SECOND_HOLD'
    assert mode.can_hold2 is False
    assert mode._speed_burst_timer == 12.5
    assert mode._speed_burst_speed_mult == 1.6
    assert mode._speed_burst_line_mult == 1.75
    assert mode._mirror_hold_charges == 1
    assert mode._echo_drop_charges == 2
    assert mode._echo_drop_fill_count == 3
    assert mode._freeze_drop_charges == 2
    assert mode._freeze_drop_duration == 15
    assert mode._freeze_drop_active is True
    assert mode._freeze_drop_timer == 4.0
    assert mode.card_manager.force_piece_queue == ['I', 'T']
    assert mode.card_manager.progress == 4
    assert mode.card_manager.pending_choices == [{'id': 'clear_rows'}]
    assert mode.card_manager.active_cards == [{'id': 'freeze_drop'}]
    assert mode.card_manager.used_card_ids == {'freeze_drop'}


def test_time_capsule_restores_perk_manager_and_runtime_effect_flags():
    _, _, MysteryMode, Board = _import_mystery_mode()
    mode = MysteryMode.__new__(MysteryMode)
    mode.board = Board()
    mode.current_piece = None
    mode.next_piece_queue = []
    mode.held_piece = None
    mode.can_hold = True
    mode._score_color_override = (255, 210, 75)
    mode._bomb_countdown_timer = 2.4
    mode._bomb_countdown_last_int = 3
    mode._drill_last_cleanup_y = 12
    mode._drill_movement_locked = True
    mode._rewind_available = True
    mode._last_placed_piece = {'cells': [(1, 18)]}
    mode.card_manager = SimpleNamespace(force_piece_queue=[], progress=0, threshold=5, pending_choices=[], active_cards=[], used_card_ids=set())
    mode.perk_manager = SimpleNamespace(
        active={'synergy_core': True, 'perk_flexible_border': True},
        next_piece_bomb=True,
        lines_since_chrono=8,
        chrono_freeze_timer=1.5,
        rewind_uses=2,
    )

    data = mode._capture_time_capsule_state()

    mode._score_color_override = None
    mode._bomb_countdown_timer = 0.0
    mode._bomb_countdown_last_int = 0
    mode._drill_last_cleanup_y = None
    mode._drill_movement_locked = False
    mode._rewind_available = False
    mode._last_placed_piece = None
    mode.perk_manager.active = {}
    mode.perk_manager.next_piece_bomb = False
    mode.perk_manager.lines_since_chrono = 0
    mode.perk_manager.chrono_freeze_timer = 0.0
    mode.perk_manager.rewind_uses = 0

    mode._restore_time_capsule_state(data)

    assert mode._score_color_override == (255, 210, 75)
    assert mode._bomb_countdown_timer == 2.4
    assert mode._bomb_countdown_last_int == 3
    assert mode._drill_last_cleanup_y == 12
    assert mode._drill_movement_locked is True
    assert mode._rewind_available is True
    assert mode._last_placed_piece == {'cells': [(1, 18)]}
    assert mode.perk_manager.active == {'synergy_core': True, 'perk_flexible_border': True}
    assert mode.perk_manager.next_piece_bomb is True
    assert mode.perk_manager.lines_since_chrono == 8
    assert mode.perk_manager.chrono_freeze_timer == 1.5
    assert mode.perk_manager.rewind_uses == 2


def test_phase_shift_mapping_matches_card_text_only_mirrors_lj_and_zs():
    _, _, MysteryMode, _ = _import_mystery_mode()
    mode = MysteryMode.__new__(MysteryMode)

    assert mode._get_smart_phase_shift_target_name('L') == 'J'
    assert mode._get_smart_phase_shift_target_name('J') == 'L'
    assert mode._get_smart_phase_shift_target_name('Z') == 'S'
    assert mode._get_smart_phase_shift_target_name('S') == 'Z'
    assert mode._get_smart_phase_shift_target_name('I') == 'I'
    assert mode._get_smart_phase_shift_target_name('O') == 'O'
    assert mode._get_smart_phase_shift_target_name('T') == 'T'


def test_hammer_does_not_consume_again_after_piece_is_already_1x1():
    _, _, MysteryMode, _ = _import_mystery_mode()
    mode = MysteryMode.__new__(MysteryMode)
    piece = SimpleNamespace(
        shape=[[1]],
        x=4,
        y=10,
        color=(255, 255, 255),
        get_cells=lambda: [(4, 10)],
    )
    mode.current_piece = piece

    assert mode._hammer_current_piece_to_unit() is False
    assert getattr(piece, 'hammered', False) is True


def test_mirror_hold_prepares_mirrored_piece_and_consumes_charge():
    _, _, MysteryMode, _ = _import_mystery_mode()
    from pieces import create_piece_by_name

    mode = MysteryMode.__new__(MysteryMode)
    mode._mirror_hold_charges = 1
    mode._set_localized_card_message = lambda *_args, **_kwargs: ''

    original = create_piece_by_name('L', x=0, y=0)
    mirrored = mode._prepare_piece_for_hold(original, slot='primary')

    assert mirrored is not original
    assert mirrored.shape == create_piece_by_name('J', x=0, y=0).shape
    assert mode._mirror_hold_charges == 0


def test_echo_drop_fills_gap_below_locked_piece_and_consumes_charge():
    _, _, MysteryMode, Board = _import_mystery_mode()
    mode = _minimal_card_effect_mode(MysteryMode, Board, effects_enabled=False)
    mode._echo_drop_charges = 1
    mode._echo_drop_fill_count = 2
    mode._active_effect_visuals = {'echo_drop': {'color': (120, 220, 255)}}
    mode._sync_active_cards = lambda: None
    mode._post_external_line_clear = lambda *_args, **_kwargs: None

    piece = SimpleNamespace(
        x=0,
        y=0,
        color=(90, 180, 255),
        shape=[[1, 1]],
    )

    placed = mode._apply_echo_drop_on_lock(piece, [(1, 1), (2, 1)], [])

    assert placed == 2
    assert mode._echo_drop_charges == 0
    assert mode.board.occupancy[2][1] is True
    assert mode.board.occupancy[2][2] is True


def test_echo_drop_keeps_charge_until_it_can_fill_a_gap():
    _, _, MysteryMode, Board = _import_mystery_mode()
    mode = _minimal_card_effect_mode(MysteryMode, Board, effects_enabled=False)
    mode._echo_drop_charges = 1
    mode._echo_drop_fill_count = 2
    mode._active_effect_visuals = {'echo_drop': {'color': (120, 220, 255)}}
    mode._sync_active_cards = lambda: None
    mode._post_external_line_clear = lambda *_args, **_kwargs: None

    mode.board.occupancy[2][1] = True
    mode.board.grid[2][1] = (255, 255, 255)
    mode.board.occupancy[2][2] = True
    mode.board.grid[2][2] = (255, 255, 255)

    piece = SimpleNamespace(
        x=0,
        y=0,
        color=(90, 180, 255),
        shape=[[1, 1]],
    )

    placed = mode._apply_echo_drop_on_lock(piece, [(1, 1), (2, 1)], [])

    assert placed == 0
    assert mode._echo_drop_charges == 1


def test_gambler_bad_roll_fills_empty_board_to_half_without_touching_top_rows(monkeypatch):
    extra, _, MysteryMode, Board = _import_mystery_mode()
    mode = MysteryMode.__new__(MysteryMode)
    mode.board = Board()
    mode.sound_enabled = False
    mode.effects_enabled = False
    mode.card_manager = SimpleNamespace(used_card_ids=set())
    mode._set_localized_card_message = lambda *_args, **_kwargs: ''

    monkeypatch.setattr(extra.random, 'random', lambda: 0.75)

    mode._apply_card_effect({'id': 'gambler_dice', 'value': 1, 'color': (255, 80, 80)})

    occupied = sum(1 for row in mode.board.occupancy for cell in row if cell)
    top_occupied = sum(1 for row in mode.board.occupancy[:5] for cell in row if cell)

    assert occupied == (mode.board.width * mode.board.height) // 2
    assert top_occupied == 0
    assert not any(all(row) for row in mode.board.occupancy)


def test_block_magnet_keeps_empty_cells_canonical_black_after_shift():
    extra, _, MysteryMode, Board = _import_mystery_mode()
    mode = MysteryMode.__new__(MysteryMode)
    mode.board = Board()
    mode.sound_enabled = False
    marker_texture = object()

    mode.board.grid[19][3] = (255, 80, 80)
    mode.board.occupancy[19][3] = True
    mode.board.texture_grid[19][3] = marker_texture
    mode.board.gold[19][3] = True
    mode.board.owners[19][3] = 'L'
    mode.board.grid[19][7] = (80, 160, 255)
    mode.board.occupancy[19][7] = True

    mode._apply_block_magnet()

    assert mode.board.grid[19][0] == (255, 80, 80)
    assert mode.board.texture_grid[19][0] is marker_texture
    assert mode.board.gold[19][0] is True
    assert mode.board.owners[19][0] == 'L'
    assert mode.board.grid[19][1] == (80, 160, 255)
    assert mode.board.occupancy[19][0] is True
    assert mode.board.occupancy[19][1] is True
    for x in range(2, mode.board.width):
        assert mode.board.grid[19][x] == extra.BLACK
        assert mode.board.occupancy[19][x] is False
        assert mode.board.texture_grid[19][x] is None
        assert mode.board.gold[19][x] is False
        assert mode.board.owners[19][x] is None


def test_block_magnet_queues_board_delta_effect_for_shifted_cells():
    _, _, MysteryMode, Board = _import_mystery_mode()
    mode = _minimal_card_effect_mode(MysteryMode, Board, effects_enabled=True)

    mode.board.grid[5][2] = (255, 80, 80)
    mode.board.occupancy[5][2] = True
    mode.board.grid[5][3] = (80, 160, 255)
    mode.board.occupancy[5][3] = True

    mode._apply_card_effect({'id': 'block_magnet', 'value': 1, 'color': (255, 140, 100)})

    effect = mode._card_board_effects[-1]
    assert {(move['from_x'], move['from_y'], move['to_x'], move['to_y']) for move in effect['moves']} == {
        (2, 5, 0, 5),
        (3, 5, 1, 5),
    }
    assert effect['removed'] == []
    assert effect['added'] == []


def test_color_cleanse_clears_target_color_to_canonical_black(monkeypatch):
    extra, _, MysteryMode, Board = _import_mystery_mode()
    mode = MysteryMode.__new__(MysteryMode)
    mode.board = Board()
    mode.sound_enabled = False
    mode._set_localized_card_message = lambda *_args, **_kwargs: ''
    marker_texture = object()
    red = (255, 0, 0)
    blue = (0, 0, 255)

    mode.board.grid[18][2] = red
    mode.board.occupancy[18][2] = True
    mode.board.texture_grid[18][2] = marker_texture
    mode.board.gold[18][2] = True
    mode.board.owners[18][2] = 'Z'
    mode.board.grid[19][3] = blue
    mode.board.occupancy[19][3] = True

    monkeypatch.setattr(extra.random, 'choice', lambda _values: red)

    mode._apply_color_cleanse()

    assert mode.board.grid[18][2] == extra.BLACK
    assert mode.board.occupancy[18][2] is False
    assert mode.board.texture_grid[18][2] is None
    assert mode.board.gold[18][2] is False
    assert mode.board.owners[18][2] is None
    assert any(
        mode.board.occupancy[y][x] and mode.board.grid[y][x] == blue
        for y in range(mode.board.height)
        for x in range(mode.board.width)
    )


def test_color_cleanse_queues_board_delta_effect_for_removed_color(monkeypatch):
    extra, _, MysteryMode, Board = _import_mystery_mode()
    mode = _minimal_card_effect_mode(MysteryMode, Board, effects_enabled=True)
    mode._set_localized_card_message = lambda *_args, **_kwargs: ''
    red = (255, 0, 0)
    blue = (0, 0, 255)

    mode.board.grid[2][1] = red
    mode.board.occupancy[2][1] = True
    mode.board.grid[5][3] = blue
    mode.board.occupancy[5][3] = True

    monkeypatch.setattr(extra.random, 'choice', lambda _values: red)

    mode._apply_card_effect({'id': 'color_cleanse', 'value': 1, 'color': (100, 255, 200)})

    effect = mode._card_board_effects[-1]
    assert (1, 2, red) in {(cell['x'], cell['y'], tuple(cell['color'])) for cell in effect['removed']}


def test_clear_drill_cells_queues_board_delta_effect_for_removed_cells():
    _, _, MysteryMode, Board = _import_mystery_mode()
    mode = MysteryMode.__new__(MysteryMode)
    mode.board = Board(width=4, height=6)
    mode.sound_enabled = False
    mode.effects_enabled = True
    mode._card_board_effects = []
    mode._drill_movement_locked = False
    mode._trace_ghost_bug_clear = lambda **_kwargs: None

    mode.board.grid[4][2] = (255, 90, 90)
    mode.board.occupancy[4][2] = True

    cleared = mode._clear_drill_cells([(2, 4)], SimpleNamespace(name='I'), clear_kind='drill')

    assert cleared == 1
    effect = mode._card_board_effects[-1]
    assert effect['id'] == 'laser_drill'
    assert effect['removed'] == [{'x': 2, 'y': 4, 'color': (255, 70, 70)}]


def test_clear_rows_card_does_not_count_sweep_only_rows_as_cleared_lines():
    _, _, MysteryMode, Board = _import_mystery_mode()
    mode = _minimal_card_effect_mode(MysteryMode, Board, effects_enabled=False)

    for x, y in ((0, 1), (1, 2), (2, 3)):
        mode.board.occupancy[y][x] = True
        mode.board.grid[y][x] = (255, 255, 255)

    mode._apply_card_effect({'id': 'clear_rows', 'value': 1, 'color': (1, 2, 3)})

    assert mode.board.lines_cleared == 0
    assert mode.board.level_lines_cleared == 0
    assert mode.board.score == 150
    assert mode.board.combo == 0


def test_clear_rows_card_starts_gravity_fall_animation_for_sweep_only_collapse():
    _, _, MysteryMode, Board = _import_mystery_mode()
    mode = _minimal_card_effect_mode(MysteryMode, Board, effects_enabled=True)

    for x, y in ((0, 1), (1, 2), (2, 3)):
        mode.board.occupancy[y][x] = True
        mode.board.grid[y][x] = (255, 255, 255)

    mode._apply_card_effect({'id': 'clear_rows', 'value': 1, 'color': (1, 2, 3)})

    assert mode.line_clear_sweep_active is False
    assert mode.line_clear_animation == 0
    assert [
        (anim['row'], anim['col'], anim['current_offset'], anim['started'])
        for anim in mode.falling_block_animations
    ] == [
        (5, 0, -40.0, True),
        (5, 1, -30.0, True),
        (5, 2, -20.0, True),
    ]


def test_clear_rows_card_animates_direct_downward_shift_without_extra_gravity():
    _, _, MysteryMode, Board = _import_mystery_mode()
    mode = _minimal_card_effect_mode(MysteryMode, Board, effects_enabled=True)

    for y in (2, 3, 4):
        mode.board.occupancy[y][0] = True
        mode.board.grid[y][0] = (255, 255, 255)

    mode._apply_card_effect({'id': 'clear_rows', 'value': 1, 'color': (1, 2, 3)})

    assert [
        (anim['row'], anim['col'], anim['current_offset'], anim['started'])
        for anim in mode.falling_block_animations
    ] == [
        (3, 0, -10.0, True),
        (4, 0, -10.0, True),
        (5, 0, -10.0, True),
    ]


def test_clear_rows_card_queues_line_clear_effects_for_resulting_full_rows():
    _, _, MysteryMode, Board = _import_mystery_mode()
    mode = _minimal_card_effect_mode(MysteryMode, Board, effects_enabled=True)

    for x, y in ((0, 1), (1, 1), (2, 2), (3, 2), (0, 3), (2, 3), (1, 4)):
        mode.board.occupancy[y][x] = True
        mode.board.grid[y][x] = (255, 255, 255)

    mode._apply_card_effect({'id': 'clear_rows', 'value': 1, 'color': (1, 2, 3)})

    assert mode.board.lines_cleared == 1
    assert mode.line_clear_sweep_active is True
    assert mode.line_clear_pending_rows == [5]
    assert mode.line_clear_animation == 30
    assert mode.line_clear_flash is True
    assert mode.board.last_cleared_lines == []


def test_snapshotless_external_clear_does_not_arm_blank_line_clear_animation():
    _, _, MysteryMode, Board = _import_mystery_mode()
    mode = _minimal_card_effect_mode(MysteryMode, Board, effects_enabled=True)

    mode.board.grid[1][0] = (255, 255, 255)
    mode.board.occupancy[1][0] = True

    prev_score = mode.board.score
    mode._clear_rows(1, count_as_lines=True)
    delta = mode.board.score - prev_score
    mode._post_external_line_clear(1, award_energy=False, score_delta=delta, source='ability')

    assert mode.line_clear_animation == 0
    assert mode.line_clear_flash is False
    assert mode.line_clear_sweep_active is False
    assert mode.line_clear_pending_rows == []


def test_card_secondary_lines_are_not_recounted_as_player_lines(monkeypatch):
    extra, Game, MysteryMode, Board = _import_mystery_mode()
    mode = MysteryMode.__new__(MysteryMode)
    mode.board = Board()
    mode.current_piece = SimpleNamespace(
        name='I',
        drill=False,
        is_bomb=False,
        get_cells=lambda: [(4, 5)],
    )
    mode._armed_nova_clusters = 1
    mode._rewind_available = False
    mode.energy = None
    mode.sound_enabled = False
    mode.effects_enabled = False
    mode.line_bonus_remaining = 0
    mode.line_bonus_amount = 0
    mode._score_multiplier_timer = 0.0
    mode._score_multiplier_value = 1.0
    mode._line_clear_multiplier_remaining = 0
    mode._line_clear_multiplier_value = 1.0
    mode._speed_burst_timer = 0.0
    mode._speed_burst_line_mult = 1.0
    mode._active_effect_visuals = {}
    mode._sync_active_cards = lambda: None
    mode.create_power_particles = lambda *_args, **_kwargs: None
    mode._apply_combo_aura_on_lock = lambda gained, _previous_combo: None

    for x in range(mode.board.width):
        mode.board.grid[19][x] = (120, 200, 255)
        mode.board.occupancy[19][x] = True
    mode.board.grid[5][4] = (255, 80, 80)
    mode.board.occupancy[5][4] = True

    card_progress_calls = []
    perk_calls = []
    alchemist_calls = []
    mode.card_manager = SimpleNamespace(
        notify_lines_cleared=lambda lines, **kwargs: card_progress_calls.append((lines, kwargs.get('source', 'player'))) or False,
        pending_choices=[],
    )
    mode.perk_manager = SimpleNamespace(
        get_multiplier=lambda: 1.0,
        maybe_trigger_alchemist=lambda _piece, lines: alchemist_calls.append(lines),
        notify_lines_cleared=lambda lines, source='player': perk_calls.append((lines, source)),
        on_piece_locked=lambda _piece, _cells: None,
    )

    def fake_lock_and_spawn(self):
        self.board.lines_cleared += 1
        self.current_piece = SimpleNamespace(drill=False, is_bomb=False)

    monkeypatch.setattr(Game, 'lock_and_new_piece', fake_lock_and_spawn)

    mode.lock_and_new_piece()

    assert card_progress_calls == [(1, 'card'), (1, 'player')]
    assert perk_calls == [(1, 'card'), (1, 'player')]
    assert alchemist_calls == []
    assert mode.board.lines_cleared == 2


def test_alchemist_quadrix_triggers_once_on_player_lock(monkeypatch):
    extra, Game, MysteryMode, _ = _import_mystery_mode()
    mode = MysteryMode.__new__(MysteryMode)
    converted = []
    mode.board = SimpleNamespace(
        score=0,
        lines_cleared=0,
        combo=0,
        convert_to_gold=lambda count: converted.append(count),
    )
    mode.current_piece = SimpleNamespace(
        name='I',
        drill=False,
        is_bomb=False,
        get_cells=lambda: [(4, 18)],
    )
    mode._armed_nova_clusters = 0
    mode._rewind_available = False
    mode.energy = None
    mode.sound_enabled = False
    mode.effects_enabled = False
    mode.line_bonus_remaining = 0
    mode.line_bonus_amount = 0
    mode._score_multiplier_timer = 0.0
    mode._score_multiplier_value = 1.0
    mode._line_clear_multiplier_remaining = 0
    mode._line_clear_multiplier_value = 1.0
    mode._speed_burst_timer = 0.0
    mode._speed_burst_line_mult = 1.0
    mode._active_effect_visuals = {}
    mode._sync_active_cards = lambda: None
    mode._apply_combo_aura_on_lock = lambda gained, _previous_combo: None
    mode.card_manager = SimpleNamespace(notify_lines_cleared=lambda _lines, **_kwargs: False)
    mode.perk_manager = extra.PerkManager(mode)
    mode.perk_manager.activate('perk_alchemist')

    def fake_quadrix_lock(self):
        self.board.lines_cleared += 4
        self.current_piece = SimpleNamespace(drill=False, is_bomb=False)

    monkeypatch.setattr(Game, 'lock_and_new_piece', fake_quadrix_lock)

    mode.lock_and_new_piece()

    assert converted == [5]


def test_rewind_clears_last_piece_cells_to_canonical_empty_state():
    extra, _, MysteryMode, Board = _import_mystery_mode()
    mode = MysteryMode.__new__(MysteryMode)
    mode.board = Board()
    mode.board.grid[18][4] = (255, 0, 0)
    mode.board.occupancy[18][4] = True
    mode.board.texture_grid[18][4] = object()
    mode.board.gold[18][4] = True
    mode.board.owners[18][4] = 'T'
    mode.current_piece = None
    mode.next_piece_queue = []
    mode._last_placed_piece = {
        'piece': SimpleNamespace(shape=[[1]], x=4, y=18, color=(255, 0, 0), get_cells=lambda: [(4, 18)]),
        'cells': [(4, 18)],
        'color': (255, 0, 0),
    }
    mode.perk_manager = SimpleNamespace(
        rewind_uses=1,
        is_active=lambda key: key == 'rewind_power',
        deactivate=lambda _key: None,
    )
    mode._set_localized_card_message = lambda *_args, **_kwargs: ''
    mode._position_piece_at_spawn = lambda _piece: None
    mode._skip_hidden_rows = lambda _piece: None
    mode.apply_theme_to_pieces = lambda: None
    mode._sync_active_cards = lambda: None
    mode.sound_enabled = False

    assert mode._do_rewind() is True
    assert mode.board.grid[18][4] == extra.BLACK
    assert mode.board.occupancy[18][4] is False
    assert mode.board.texture_grid[18][4] is None
    assert mode.board.gold[18][4] is False
    assert mode.board.owners[18][4] is None


def test_sniper_card_grants_charge_without_opening_overlay():
    _, _, MysteryMode, _ = _import_mystery_mode()
    mode = MysteryMode.__new__(MysteryMode)
    mode.card_manager = SimpleNamespace(used_card_ids=set(), active_cards=[], catalog=[])
    mode._active_effect_visuals = {}
    mode.sound_enabled = False
    mode.effects_enabled = False
    mode._set_localized_card_message = lambda *_args, **_kwargs: ''
    mode._sync_active_cards = lambda: None
    overlay_calls = []
    mode._open_sniper_overlay = lambda: overlay_calls.append('open') or True

    mode._apply_card_effect({'id': 'sniper_shot', 'title': 'Keskin Nişancı', 'value': 3, 'color': (255, 80, 80)})

    # Charge verilmiş olmalı...
    assert mode._sniper_charges == 3
    # ...ama overlay otomatik açılmamalı (sadece N / card_sniper ile açılır).
    assert mode._sniper_overlay_active is False
    assert mode._sniper_hover_pos is None
    assert overlay_calls == []


def test_sniper_overlay_opens_only_via_explicit_hotkey():
    _, _, MysteryMode, _ = _import_mystery_mode()
    mode = MysteryMode.__new__(MysteryMode)
    mode.card_manager = SimpleNamespace(used_card_ids=set(), active_cards=[], catalog=[])
    mode._active_effect_visuals = {}
    mode.sound_enabled = False
    mode.effects_enabled = False
    mode._set_localized_card_message = lambda *_args, **_kwargs: ''
    mode._sync_active_cards = lambda: None
    mode.board = SimpleNamespace(width=10, height=20)

    mode._apply_card_effect({'id': 'sniper_shot', 'title': 'Keskin Nişancı', 'value': 2, 'color': (255, 80, 80)})
    assert mode._sniper_overlay_active is False

    opened = MysteryMode._open_sniper_overlay(mode)
    assert opened is True
    assert mode._sniper_overlay_active is True
    # Gamepad cursor tahtanın ortasından başlamalı
    assert mode._sniper_cursor_x == 5
    assert mode._sniper_cursor_y == 10
    assert mode._sniper_cursor_active is True


def test_laser_drill_cleans_hard_drop_path_before_lock():
    extra, _, MysteryMode, Board = _import_mystery_mode()
    mode = MysteryMode.__new__(MysteryMode)
    mode.board = Board()
    mode.sound_enabled = False
    mode._drill_movement_locked = False
    mode._drill_last_cleanup_y = 5
    piece = SimpleNamespace(x=4, y=15, drill=True)
    piece.get_cells = lambda: [(piece.x, piece.y)]
    for y in (10, 15):
        mode.board.grid[y][4] = (255, 80, 80)
        mode.board.occupancy[y][4] = True
        mode.board.texture_grid[y][4] = object()
        mode.board.gold[y][4] = True
        mode.board.owners[y][4] = 'I'

    mode._cleanup_drill_path_to_lock(piece)

    for y in (10, 15):
        assert mode.board.grid[y][4] == extra.BLACK
        assert mode.board.occupancy[y][4] is False
        assert mode.board.texture_grid[y][4] is None
        assert mode.board.gold[y][4] is False
        assert mode.board.owners[y][4] is None
    assert mode.board.score == 40
    assert mode._drill_movement_locked is True
    assert mode._drill_last_cleanup_y == 15


def test_restart_resets_mystery_runtime_effect_state(monkeypatch):
    _, Game, MysteryMode, _ = _import_mystery_mode()
    mode = MysteryMode.__new__(MysteryMode)
    mode.board = SimpleNamespace(level=4, flexible_border_active=True)
    mode.card_manager = SimpleNamespace(reset=lambda: None, sync_level_progress=lambda: None)
    mode.card_selection_reroll_limit = 5
    mode._sync_active_cards = lambda: None
    mode._score_multiplier_timer = 9.0
    mode._score_multiplier_value = 3.0
    mode._line_clear_multiplier_remaining = 4
    mode._line_clear_multiplier_value = 2.0
    mode._score_color_override = (255, 210, 75)
    mode._speed_burst_timer = 12.0
    mode._speed_burst_speed_mult = 1.6
    mode._speed_burst_line_mult = 1.75
    mode._armed_nova_clusters = 3
    mode._bomb_countdown_timer = 2.0
    mode._bomb_countdown_last_int = 2
    mode._drill_last_cleanup_y = 10
    mode.energy = 80
    mode.time_warp_timer = 1.5
    mode._timewarp_old_speed = 1200

    monkeypatch.setattr(Game, 'restart', lambda self: None)

    mode.restart()

    assert mode._score_multiplier_timer == 0.0
    assert mode._score_multiplier_value == 1.0
    assert mode._line_clear_multiplier_remaining == 0
    assert mode._line_clear_multiplier_value == 1.0
    assert mode._score_color_override is None
    assert mode._speed_burst_timer == 0.0
    assert mode._speed_burst_speed_mult == 1.0
    assert mode._speed_burst_line_mult == 1.0
    assert mode._armed_nova_clusters == 0
    assert mode._bomb_countdown_timer == 0.0
    assert mode._bomb_countdown_last_int == 0
    assert mode._drill_last_cleanup_y is None
    assert mode.energy == 0
    assert mode.time_warp_timer == 0.0
    assert not hasattr(mode, '_timewarp_old_speed')


def test_effect_timers_accept_seconds_dt_without_slowing_real_time():
    _, _, MysteryMode, _ = _import_mystery_mode()
    mode = MysteryMode.__new__(MysteryMode)
    mode._score_multiplier_timer = 0.0
    mode.speed_effect_timer = 0.0
    mode.combo_aura_timer = 0.0
    mode.time_warp_timer = 0.0
    mode.gravity_freeze_timer = 0.0
    mode._speed_burst_timer = 1.0
    mode._speed_burst_speed_mult = 1.4
    mode._speed_burst_line_mult = 1.5
    mode._freeze_drop_active = False
    mode._active_effect_visuals = {}
    mode._sync_active_cards = lambda: None

    mode._update_effect_timers(0.25)

    assert mode._speed_burst_timer == 0.75



def test_card_reveal_sfx_fires_once_at_flip_midpoint_not_at_flip_start():
    """Reveal SFX kart yüzü açılırken (flip_progress >= 0.5) çalmalı; flip
    delay sona erer ermez (progress 0) çalmamalı. Aynı kart için yalnızca bir
    kez tetiklenmeli."""
    if not hasattr(pygame, 'K_h'):
        pytest.skip('pygame stub environment: UICard import skipped')
    import game_modes_extra as extra

    calls = []

    rect = pygame.Rect(0, 0, 100, 140)
    card = {'id': 'sniper_shot', 'rarity': 'common', 'tag': 'Common', 'description': '...'}
    fonts = {
        'card_title': SimpleNamespace(),
        'card_body': SimpleNamespace(),
        'card_tag': SimpleNamespace(),
        'card_value': SimpleNamespace(),
    }
    widget = extra.UICard.__new__(extra.UICard)
    widget.card = card
    widget.base_rect = rect
    widget.index = 0
    widget.fonts = fonts
    widget.icon_getter = lambda *_args, **_kwargs: None
    widget._reveal_sfx_callback = lambda: calls.append('sfx')
    widget.rect = rect.copy()
    widget.hover = False
    widget.scale = 1.0
    widget.target_scale = 1.0
    widget.pulse = 0.0
    widget.flip_duration = 0.40
    widget.flip_delay = 0.0  # delay test'in dışında
    widget.flip_timer = 0.0
    widget.flip_progress = 0.0
    widget.is_revealed = False
    widget.reveal_burst_done = False
    widget._flip_sfx_played = False
    widget.entry_progress = 1.0
    widget.entry_duration = 0.35
    widget.entry_done = True
    widget.entry_offset_y = 0
    widget.rarity_particles = []
    widget._continuous_particle_timer = 0.0
    widget._continuous_particle_interval = 0.5
    widget._flame_seeds = []
    widget._shake_intensity = 0.0
    widget._shake_timer = 0.0
    widget._shake_offset = (0.0, 0.0)

    # 1. tick: çok küçük dt -> flip henüz yarıya gelmedi.
    widget.update(0.05, None)  # 0.05 / 0.40 = 0.125 raw; eased ~0.234
    assert calls == [], 'SFX flip ortasından önce çalmamalı'
    assert widget._flip_sfx_played is False

    # 2. tick: yarıya geç -> SFX bir kez çalmalı.
    widget.update(0.15, None)  # toplam 0.20s -> raw 0.5 -> eased ~0.823
    assert calls == ['sfx']
    assert widget._flip_sfx_played is True

    # 3. tick: kart tamamen açılmış olsa bile ikinci kez çalmamalı.
    widget.update(0.40, None)
    assert calls == ['sfx'], 'Aynı kart için reveal SFX sadece bir kez tetiklenmeli'
