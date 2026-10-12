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
    mode.settings_manager = None
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
        notify_lines_cleared=lambda _lines: False,
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


def test_slot_key_triggers_sniper_card_via_slot_binding(monkeypatch):
    # Plan §3: kartların sabit tuşu yoktur; tetikleme slota bağlıdır.
    # Sniper kartı bir slota yerleştirilince, o slotun tuşu (varsayılan '1')
    # kartı tetikler ve event tüketilir.
    extra, Game, MysteryMode, _ = _import_mystery_mode()
    mode = _minimal_mode(MysteryMode)
    opened = {'count': 0}

    def _open():
        opened['count'] += 1
        return True

    mode._open_sniper_overlay = _open
    mode.sound_enabled = False
    mode._refresh_slot_charges = lambda: None
    mode._sniper_charges = 2

    sniper_card = {'id': 'sniper_shot', 'value': 2, 'charges': 2}
    mode.card_manager = SimpleNamespace(
        MAX_CARD_SLOTS=6,
        active_slots=[sniper_card, None, None, None, None, None],
        unlocked_slots=3,
        is_slot_unlocked=lambda idx: idx < 3,
        get_slot_card=lambda idx: sniper_card if idx == 0 else None,
    )

    event = SimpleNamespace(type=extra.pygame.KEYDOWN, key=extra.pygame.K_1)
    posted_events = []
    monkeypatch.setattr(extra.pygame.event, 'get', lambda: [event])
    monkeypatch.setattr(extra.pygame.event, 'post', lambda event: posted_events.append(event))
    monkeypatch.setattr(Game, 'handle_input', lambda self: True)
    monkeypatch.setattr(
        'game_modes_extra.get_gamepad_manager',
        lambda: SimpleNamespace(enabled=False),
    )

    assert mode.handle_input() is True
    # Slot 1 tuşu (varsayılan '1') sniper kartını tetikledi ve event tüketildi.
    assert opened['count'] == 1
    assert posted_events == []


def test_legacy_n_key_no_longer_triggers_sniper(monkeypatch):
    # Plan §3: eski N kısayolu kaldırıldı. N tuşu artık sniper açmaz; event
    # base game'e iletilir (post edilir).
    extra, Game, MysteryMode, _ = _import_mystery_mode()
    mode = _minimal_mode(MysteryMode)
    opened = {'count': 0}
    mode._open_sniper_overlay = lambda: opened.__setitem__('count', opened['count'] + 1) or True
    mode.sound_enabled = False
    mode._refresh_slot_charges = lambda: None
    mode.card_manager = SimpleNamespace(
        MAX_CARD_SLOTS=6,
        active_slots=[None] * 6,
        unlocked_slots=3,
        is_slot_unlocked=lambda idx: idx < 3,
        get_slot_card=lambda idx: None,
    )

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
    assert opened['count'] == 0
    assert [e.key for e in posted_events] == [extra.pygame.K_n]


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


def test_time_capsule_does_not_restore_active_card_counters_and_manager_state():
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

    # Artik kart sayaclari ve kart yöneticisi durumlari zaman kapsülü geri yuklemesiyle
    # eski haline donmez, mevcuttaki guncel hallerini korur.
    assert mode.second_held_piece is None
    assert mode.can_hold2 is True
    assert mode._speed_burst_timer == 0.0
    assert mode._speed_burst_speed_mult == 1.0
    assert mode._speed_burst_line_mult == 1.0
    assert mode._mirror_hold_charges == 0
    assert mode._echo_drop_charges == 0
    assert mode._echo_drop_fill_count == 0
    assert mode._freeze_drop_charges == 0
    assert mode._freeze_drop_duration == 0
    assert mode._freeze_drop_active is False
    assert mode._freeze_drop_timer == 0.0
    assert mode.card_manager.force_piece_queue == []
    assert mode.card_manager.progress == 0
    assert mode.card_manager.pending_choices == []
    assert mode.card_manager.active_cards == []
    assert mode.card_manager.used_card_ids == set()


def test_time_capsule_does_not_restore_perk_manager_and_runtime_effect_flags():
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

    # Artik perk yöneticisi ve diger efekt bayraklari zaman kapsülü geri yuklemesiyle
    # eski haline donmez, mevcuttaki guncel hallerini korur.
    assert mode._score_color_override is None
    assert mode._bomb_countdown_timer == 0.0
    assert mode._bomb_countdown_last_int == 0
    assert mode._drill_last_cleanup_y is None
    assert mode._drill_movement_locked is False
    assert mode._rewind_available is False
    assert mode._last_placed_piece is None
    assert mode.perk_manager.active == {}
    assert mode.perk_manager.next_piece_bomb is False
    assert mode.perk_manager.lines_since_chrono == 0
    assert mode.perk_manager.chrono_freeze_timer == 0.0
    assert mode.perk_manager.rewind_uses == 0


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
    mode.card_manager = SimpleNamespace(notify_lines_cleared=lambda _lines: False)
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
    mode.card_manager = SimpleNamespace(reset=lambda: None)
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


def test_reverse_debt_queues_board_delta_effect_when_effects_enabled():
    """Opt-in gate kaldırıldıktan sonra tahtayı değiştiren reverse_debt otomatik animasyon almalı.

    reverse_debt eskiden gate set'te olmadığı için animasyonsuz kalıyordu; koşulsuz
    snapshot ile artık tahta değişimi (silinen alt satırlar) kuyruğa düşmeli.
    """
    _, _, MysteryMode, Board = _import_mystery_mode()
    mode = _minimal_card_effect_mode(MysteryMode, Board, effects_enabled=True)

    # Alt iki satıra (tam dolu OLMAYACAK şekilde) blok koy: clear_lines tetiklenmesin.
    mode.board.grid[5][0] = (255, 80, 80)
    mode.board.occupancy[5][0] = True
    mode.board.grid[4][1] = (80, 160, 255)
    mode.board.occupancy[4][1] = True

    mode._apply_card_effect({'id': 'reverse_debt', 'title': 'Ters Borç', 'value': 1, 'color': (200, 120, 255)})

    assert mode._card_board_effects, 'reverse_debt tahta değişimi animasyon kuyruğuna eklenmeli'
    assert mode._card_board_effects[-1]['id'] == 'reverse_debt'


def test_board_neutral_card_does_not_queue_board_effect_when_effects_enabled():
    """Seçim anında tahtayı değiştirmeyen kart (delta boş) animasyon üretmemeli.

    Koşulsuz snapshot alıyoruz ancak delta boşsa _append_card_board_effect no-op'tur;
    yani armed kartlar (hole_hunter) seçim anında yanlış/çift animasyon üretmez.
    """
    _, _, MysteryMode, Board = _import_mystery_mode()
    mode = _minimal_card_effect_mode(MysteryMode, Board, effects_enabled=True)
    mode._active_effect_visuals = {}

    # hole_hunter seçim anında yalnız hak armalar; board.occupancy değişmez.
    mode._apply_card_effect({'id': 'hole_hunter', 'title': 'Delik Avcısı', 'value': 1, 'color': (140, 230, 200)})

    assert mode._card_board_effects == [], 'tahtayı değiştirmeyen kart animasyon üretmemeli'


def test_reverse_debt_does_not_queue_board_effect_when_effects_disabled():
    """effects_enabled kapalıyken hiçbir tahta animasyonu üretilmemeli (gating korunur)."""
    _, _, MysteryMode, Board = _import_mystery_mode()
    mode = _minimal_card_effect_mode(MysteryMode, Board, effects_enabled=False)

    mode.board.grid[5][0] = (255, 80, 80)
    mode.board.occupancy[5][0] = True

    mode._apply_card_effect({'id': 'reverse_debt', 'title': 'Ters Borç', 'value': 1, 'color': (200, 120, 255)})

    assert mode._card_board_effects == []


# ---------------------------------------------------------------------------
# Satır Karıştırıcı — yerçekimi kaldırıldı sonrası açıklama-davranış sözleşmesi
# (Blok Karıştırıcı yalnızca alt bölge hücrelerini karıştırır: tahta geneli
#  sıkıştırma UYGULAMAZ — dengesiz güçlü bulunduğundan kaldırıldı. "Dolan satır
#  temizlenir" vaadi kalır; testler üretim metodunu gerçek Board üzerinde
#  çalıştırır)
# ---------------------------------------------------------------------------

def _row_shuffle_put_block(board, column, row, color, *, gold=False, owner=None):
    board.occupancy[row][column] = True
    board.grid[row][column] = color
    board.texture_grid[row][column] = None
    board.gold[row][column] = gold
    board.owners[row][column] = owner


def _row_shuffle_board_state(board, start_row, end_row):
    return [
        [
            (
                board.occupancy[row][column],
                board.grid[row][column],
                board.texture_grid[row][column],
                board.gold[row][column],
                board.owners[row][column],
            )
            for column in range(board.width)
        ]
        for row in range(start_row, end_row)
    ]


def test_row_shuffle_runtime_applies_no_gravity_to_board(monkeypatch):
    """Karıştırma yerçekimi uygulamaz: askıda blok askıda kalır, bölge dışı
    tahta bit-bit değişmez; dolan satır yoksa hiçbir yan etki olmaz."""
    extra, _, MysteryMode, Board = _import_mystery_mode()
    mode = _minimal_card_effect_mode(MysteryMode, Board, effects_enabled=False)
    mode.board = Board(width=4, height=6)
    mode.board_width = 4
    # Karıştırmayı no-op yap: hücre multiseti yerinde kalır; geriye kalan
    # olası tek etki yerçekimi + satır temizleme olur — ikisi de görünür
    # olmamalı (eski davranış bu bloğu row 5'e düşürürdü).
    monkeypatch.setattr(extra.random, 'shuffle', lambda seq: None)
    post_calls = []
    mode._post_external_line_clear = (
        lambda cleared, award_energy=False, score_delta=None, source='':
            post_calls.append((cleared, score_delta, source))
    )

    # Alt satır (5) 3/4 dolu — tam değil; (satır 4, kolon 2) altı boş askıda blok.
    for column in range(3):
        _row_shuffle_put_block(mode.board, column, 5, (200, 30, 30))
    _row_shuffle_put_block(mode.board, 2, 4, (30, 200, 30))

    before = _row_shuffle_board_state(mode.board, 0, 6)

    mode._shuffle_bottom_rows(1)

    # Yerçekimi yok: tahta olduğu gibi kaldı, temizlik/rapor yok.
    assert _row_shuffle_board_state(mode.board, 0, 6) == before
    assert post_calls == []
    assert mode.board.score == 0
    assert mode.board.lines_cleared == 0


def test_row_shuffle_runtime_permutes_only_bottom_region_cells():
    """Gerçek karıştırma alt bölge hücre multisetini (renk/gold/owner dahil)
    korur, bölge dışına hiç dokunmaz; dolan satır oluşmaz."""
    from collections import Counter

    _, _, MysteryMode, Board = _import_mystery_mode()
    mode = _minimal_card_effect_mode(MysteryMode, Board, effects_enabled=False)
    mode.board = Board(width=6, height=8)
    mode.board_width = 6
    post_calls = []
    mode._post_external_line_clear = (
        lambda cleared, award_energy=False, score_delta=None, source='':
            post_calls.append((cleared, score_delta, source))
    )

    # Bölge: alt 2 satır (6-7). 5 blok — 6 genişlikte tam satır imkânsız.
    # Distinct renk/gold/owner ile multiset karşılaştırması anlamlı olur.
    region_blocks = [
        (0, 7, (200, 30, 30), False, None),
        (1, 7, (30, 200, 30), False, None),
        (2, 7, (30, 30, 200), True, 'T1'),
        (3, 6, (200, 30, 30), False, None),
        (4, 6, (30, 200, 30), False, 'T2'),
    ]
    for column, row, color, gold, owner in region_blocks:
        _row_shuffle_put_block(mode.board, column, row, color, gold=gold, owner=owner)
    # Bölge DIŞI askıda bloklar — yerçekimi olsaydı bölgeye düşerdi.
    _row_shuffle_put_block(mode.board, 2, 2, (90, 90, 90))
    _row_shuffle_put_block(mode.board, 5, 5, (120, 120, 120))

    outside_before = _row_shuffle_board_state(mode.board, 0, 6)
    region_before = _row_shuffle_board_state(mode.board, 6, 8)

    mode._shuffle_bottom_rows(2)

    # Bölge dışı bit-bit aynı — tahta geneli yerçekimi/sıkıştırma YOK.
    assert _row_shuffle_board_state(mode.board, 0, 6) == outside_before
    # Bölge içi hücre multiseti korundu (permütasyon, dönüşüm değil).
    region_after = _row_shuffle_board_state(mode.board, 6, 8)
    assert Counter(cell for row in region_before for cell in row) == Counter(
        cell for row in region_after for cell in row
    )
    # Kütle: bölge 5 + dış 2 blok — hiçbiri kaybolmadı.
    assert sum(sum(row) for row in mode.board.occupancy) == 7
    # 5 blok 6 genişlikte tam satır dolduramaz → temizlik raporlanmaz.
    assert post_calls == []


def test_row_shuffle_runtime_clears_full_rows_via_card_source(monkeypatch):
    """Bölgede dolu satır temizlenir; puan akışı _post_external_line_clear
    üzerinden source='card' olarak yürür. Blok yalnızca clear_lines'ın
    standart satır-kayması kuralıyla iner — yerçekimiyle değil."""
    extra, _, MysteryMode, Board = _import_mystery_mode()
    mode = _minimal_card_effect_mode(MysteryMode, Board, effects_enabled=False)
    mode.board = Board(width=4, height=6)
    mode.board_width = 4
    monkeypatch.setattr(extra.random, 'shuffle', lambda seq: None)
    post_calls = []
    mode._post_external_line_clear = (
        lambda cleared, award_energy=False, score_delta=None, source='':
            post_calls.append((cleared, score_delta, source))
    )

    # Alt satır (5) komple dolu; bir üstünde (satır 3, kolon 2) altı boş askıda blok.
    for column in range(4):
        _row_shuffle_put_block(mode.board, column, 5, (200, 30, 30))
    _row_shuffle_put_block(mode.board, 2, 3, (30, 200, 30))

    mode._shuffle_bottom_rows(1)

    # Dolu satır temizlendi ve puan akışı kart kaynağıyla raporlandı.
    assert post_calls == [(1, 100, 'card')]
    assert mode.board.score == 100
    assert mode.board.lines_cleared == 1
    # Yerçekimi YOK kanıtı: askıda blok yalnızca altı boşalan satıra kayar
    # (row 3 -> row 4). Eski davranış (yerçekimi) onu önce row 5'e düşürüp
    # orada kalmasını sağlardı.
    assert [sum(row) for row in mode.board.occupancy] == [0, 0, 0, 0, 1, 0]
    assert mode.board.occupancy[4][2] is True
    assert mode.board.grid[4][2] == (30, 200, 30)
    # Kartsal temizlik level/combo ekonomisini oyuncu akışına katmaz.
    assert mode.board.level_lines_cleared == 0


def test_rewind_power_selection_preserves_existing_snapshot():
    """rewind_power tekrar seçilince hak tamamlanır ama anlık görüntü korunur.

    Eski davranış: kart dalı `_last_placed_piece = None` yazıyordu; bu, kartı
    (ör. Atölye/Lunar ile) hak tamamlamak için yeniden alan oyuncunun zaten
    kayıtlı olan son parçasını geri alma yeteneğini kaybetmesine yol açıyordu.
    Anlık görüntü yalnızca satır temizleyen kilitlemede veya kullanımda
    temizlenmelidir (koddaki tek iki yasal sıfırlama noktası).
    """
    extra, _, MysteryMode, Board = _import_mystery_mode()
    mode = _minimal_card_effect_mode(MysteryMode, Board, effects_enabled=False)
    activated = []
    mode.perk_manager = SimpleNamespace(
        get_multiplier=lambda: 1.0,
        notify_lines_cleared=lambda _lines, source='player': None,
        activate=lambda key: activated.append(key),
        rewind_uses=1,
    )
    snapshot = {'piece': object(), 'cells': [(1, 18)], 'color': (255, 0, 0)}
    mode._last_placed_piece = snapshot
    mode._rewind_available = True

    mode._apply_card_effect({'id': 'rewind_power', 'value': 3, 'color': (255, 200, 255)})

    assert activated == ['rewind_power']
    # Kalan hak 1'di; kart değeri 3 → tamamlandı (eksikse tamamlama kuralı).
    assert mode.perk_manager.rewind_uses == 3
    assert mode._rewind_available is True
    # Sözleşme: seçim anlık görüntüyü sıfırlamaz.
    assert mode._last_placed_piece is snapshot


def test_speed_burst_catalog_multipliers_are_single_sourced_from_family():
    """Hız Patlaması çarpan/süre değerleri tek kaynaktan (CARD_UPGRADE_FAMILIES) okunur.

    Katalogdaki eski payload kalıntısı (1.25/1.4/1.6/1.75) family extra'ları
    tarafından zaten eziliyordu; temizlik sonrası normalize katalog değerleri
    family değerleriyle birebir olmalı. Bu test her iki yönlü sürüklenmeyi
    (katalogda çarpan yazma / family değerlerini değiştirip katalogda unutma)
    yakalar.
    """
    extra, _, MysteryMode, Board = _import_mystery_mode()
    mgr = extra.MysteryCardManager.__new__(extra.MysteryCardManager)
    catalog = mgr._build_catalog()
    by_id = {str(c.get('id')): c for c in catalog}

    expected = {
        'speed_burst_rare': ((25, 25), 1.3, 1.3),
        'speed_burst_epic': ((40, 40), 1.5, 1.5),
        'speed_burst_legendary': ((60, 60), 1.75, 2.0),
    }
    for card_id, (value_range, speed_mult, line_mult) in expected.items():
        card = by_id[card_id]
        assert card['value_range'] == value_range, (card_id, card['value_range'])
        assert card['base'] == value_range[0], (card_id, card['base'])
        payload = card.get('payload') or {}
        assert payload.get('speed_multiplier') == speed_mult, (card_id, payload)
        assert payload.get('line_multiplier') == line_mult, (card_id, payload)

    # Family extra payload'ı gerçek etki dalının okuduğu alanla aynı isimde
    # olmalı; aksi halde runtime default'a (1.5) düşer.
    family_spec = {tier['id']: tier for tier in extra.CARD_UPGRADE_FAMILIES['speed_burst']}
    for card_id, (_, speed_mult, line_mult) in expected.items():
        extra_payload = family_spec[card_id]['extra']['payload']
        assert extra_payload['speed_multiplier'] == speed_mult
        assert extra_payload['line_multiplier'] == line_mult


# ---------------------------------------------------------------------------
# Faz 2 denetim düzeltmeleri — regresyon sözleşmeleri (v2 portu)
# ---------------------------------------------------------------------------

def test_row_shuffle_plays_clear_sound_only_when_rows_cleared(monkeypatch):
    """Clear sesi yalnızca gerçekten satır temizlendiyse çalar; boş
    karıştırma sessiz kalır (koşulsuz play_sound('clear') kusuru)."""
    extra, _, MysteryMode, Board = _import_mystery_mode()
    mode = _minimal_card_effect_mode(MysteryMode, Board, effects_enabled=False)
    mode.board = Board(width=4, height=6)
    mode.board_width = 4
    monkeypatch.setattr(extra.random, 'shuffle', lambda seq: None)
    played = []
    mode.sound_enabled = True
    mode.sound = SimpleNamespace(play_sound=played.append)
    post_calls = []
    mode._post_external_line_clear = (
        lambda cleared, award_energy=False, score_delta=None, source='':
            post_calls.append((cleared, score_delta, source))
    )

    # Dolu satır YOK (3/4 hücre): temizlik olmaz → clear sesi çalmamalı.
    for column in range(3):
        _row_shuffle_put_block(mode.board, column, 5, (200, 30, 30))
    mode._shuffle_bottom_rows(1)
    assert post_calls == []
    assert played == []

    # Dolu satır VAR: clear_lines temizler → clear sesi tam bir kez.
    # (Bölge dışı bir blok bırakıyoruz: tahta tamamen boşalırsa perfect
    # clear bonusu skora girer ve delta iddiası 100'den sapar.)
    _row_shuffle_put_block(mode.board, 1, 2, (30, 200, 30))
    _row_shuffle_put_block(mode.board, 3, 5, (200, 30, 30))
    mode._shuffle_bottom_rows(1)
    assert post_calls == [(1, 100, 'card')]
    assert played == ['clear']


def test_sniper_reselection_does_not_reduce_charges():
    """Sniper yeniden seçimi "hakkı tamamla" politikasıyla çalışır:
    kalan hak, seçilen kademeden AZ değilse üzerine yazılmaz."""
    extra, _, MysteryMode, Board = _import_mystery_mode()
    mode = _minimal_card_effect_mode(MysteryMode, Board, effects_enabled=False)
    mode.perk_manager = SimpleNamespace(
        get_multiplier=lambda: 1.0,
        notify_lines_cleared=lambda _lines, source='player': None,
        activate=lambda key: None,
    )

    mode._apply_card_effect({'id': 'sniper_shot', 'value': 6, 'color': (200, 60, 60)})
    assert int(mode._sniper_charges) == 6

    # Düşük kademe yeniden seçimi: hak DÜŞMEMELİ (eski davranış 3'e inerdi).
    mode._apply_card_effect({'id': 'sniper_shot', 'value': 3, 'color': (200, 60, 60)})
    assert int(mode._sniper_charges) == 6

    # Yüksek kademe seçimi: eksik hakkı tamamlamalı.
    mode._apply_card_effect({'id': 'sniper_shot', 'value': 8, 'color': (200, 60, 60)})
    assert int(mode._sniper_charges) == 8


def test_piece_requiring_card_selection_denied_without_current_piece():
    """Mini Bomba / Delici Parça düşen parça yokken seçilemez: deny sesi +
    uyarı; kart harcanmaz, seçim ekranı açık kalır (slot-dolu reddi deseni)."""
    extra, _, MysteryMode, Board = _import_mystery_mode()
    mode = _minimal_card_effect_mode(MysteryMode, Board, effects_enabled=False)
    mode.card_ui = SimpleNamespace(
        is_selection_animating=lambda: False,
        is_flip_animating=lambda: False,
        warning_message='',
        trigger_selection_feedback=lambda _i: None,
        clear_selection_feedback=lambda: None,
    )
    mode._pending_card_choice_index = None
    played = []
    mode.sound = SimpleNamespace(play_sound=played.append)
    mode.sound_enabled = True
    mode.card_manager.pending_choices = [
        {'id': 'mini_bomb', 'title': 'Mini Bomba', 'value': 1, 'color': (255, 110, 80)},
        {'id': 'gravity_well', 'title': 'Yerçekimi Kuyusu', 'value': 1, 'color': (120, 80, 200)},
    ]

    assert getattr(mode, 'current_piece', None) is None

    # mini_bomb (parça gerektirir) → reddedilir, hiçbir şey tüketilmez.
    mode._select_card(0)
    assert mode._pending_card_choice_index is None
    assert mode.card_ui.warning_message
    assert played == ['deny']
    assert mode.card_manager.pending_choices[0]['id'] == 'mini_bomb'

    # Parça gerektirmeyen kart aynı yoldan sorunsuz seçilir.
    mode.card_ui.warning_message = ''
    mode._select_card(1)
    assert mode._pending_card_choice_index == 1
    assert not mode.card_ui.warning_message
    assert played == ['deny']  # ikinci seçimde yeni deny yok


def test_laser_drill_without_current_piece_does_not_trigger_visuals():
    """laser_drill parçasız uygulandığında etki görsel kuyruklanmaz
    (mini_bomb no-piece deseni; seçim katmanı normalde reddeder)."""
    extra, _, MysteryMode, Board = _import_mystery_mode()
    mode = _minimal_card_effect_mode(MysteryMode, Board, effects_enabled=False)
    spawned = []
    mode._spawn_card_particles = lambda _color: spawned.append(_color)

    assert getattr(mode, 'current_piece', None) is None
    mode._apply_card_effect({'id': 'laser_drill', 'value': 1, 'color': (255, 50, 150)})

    assert spawned == []


def test_nova_burst_catalog_is_single_sourced_from_family():
    """Nova Patlaması kademe değerleri tek kaynaktan (CARD_UPGRADE_FAMILIES)
    okunur; katalog ham girdisi family ile birebir olmalı (ölü veri tuzağı)."""
    extra, _, MysteryMode, Board = _import_mystery_mode()
    mgr = extra.MysteryCardManager.__new__(extra.MysteryCardManager)
    catalog = mgr._build_catalog()
    by_id = {str(c.get('id')): c for c in catalog}

    expected = {
        'nova_burst': ((3, 3), 3),
        'nova_burst_epic': ((4, 4), 4),
        'nova_burst_leg': ((5, 5), 5),
    }
    for card_id, (value_range, blast) in expected.items():
        card = by_id[card_id]
        assert card['value_range'] == value_range, (card_id, card['value_range'])
        assert card['base'] == value_range[0], (card_id, card['base'])
        assert int(card.get('blast_size', 0)) == blast, (card_id, card.get('blast_size'))

    family_spec = {tier['id']: tier for tier in extra.CARD_UPGRADE_FAMILIES['nova_burst']}
    for card_id, (_, blast) in expected.items():
        assert family_spec[card_id]['extra']['blast_size'] == blast
