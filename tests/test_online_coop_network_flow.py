from __future__ import annotations

import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pygame

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from steam_networking import CHANNEL_CONTROL, CHANNEL_STATE, MsgType, SteamNetworking  # noqa: E402
import online_coop_game as coop_module  # noqa: E402


class FakeNet:
    def __init__(self, messages=None):
        self._messages = list(messages or [])
        self.my_steam_id = 1
        self._opponent_steam_id = 0
        self._opponent_name = ''
        self.is_host = False
        self.lobby_id = 123
        self.available = True
        self.initialized = True
        self.sent = []
        self.joined = []
        self.left = False
        self.created = []
        self.invited = False

    @property
    def opponent_steam_id(self):
        return self._opponent_steam_id

    @opponent_steam_id.setter
    def opponent_steam_id(self, value):
        self._opponent_steam_id = int(value or 0)

    @property
    def opponent_name(self):
        return self._opponent_name

    def get_messages(self):
        messages = self._messages
        self._messages = []
        return messages

    def get_lobby_members(self):
        return [1, 42]

    def send(self, data, reliable=True, channel=0):
        self.sent.append((data, reliable, channel))
        return True

    def send_ready(self):
        return self.send({'type': MsgType.READY}, reliable=True)

    def join_lobby(self, lobby_id):
        self.joined.append(int(lobby_id))

    def create_lobby(self, public=False):
        self.created.append(bool(public))

    def invite_friend(self):
        self.invited = True

    def leave_lobby(self):
        self.left = True

    def get_lobby_owner(self):
        return 0

    def get_lobby_data_for(self, lobby_id, key):
        return ''

    def request_lobby_data(self, lobby_id):
        return True


def _message(sender: int, data: dict, channel: int = 0):
    return SimpleNamespace(sender=sender, data=data, channel=channel)


def _valid_board_state(seq: int = 1, team_score: int = 0):
    grid = [[0 for _ in range(20)] for _ in range(20)]
    owners = [['' for _ in range(20)] for _ in range(20)]
    return {
        'type': MsgType.COOP_BOARD_STATE,
        'seq': seq,
        'grid': grid,
        'owners': owners,
        'team_score': team_score,
        'total_lines': 0,
        'level': 1,
        'fall_speed': 900.0,
        'p1_frozen': False,
        'p2_frozen': False,
    }


def _valid_piece_state(seq: int = 1):
    return {
        'type': MsgType.COOP_PIECE_STATE,
        'seq': seq,
        'p1_current': {'si': 0, 'x': 3, 'y': 0, 'r': 0},
        'p2_current': {'si': 1, 'x': 13, 'y': 0, 'r': 0},
        'p1_next_si': 2,
        'p2_next_si': 3,
        'p1_hold_si': -1,
        'p2_hold_si': -1,
        'p1_ghost_y': 10,
        'p2_ghost_y': 12,
        'input_ack': 7,
    }


def _make_game(net: FakeNet):
    game = coop_module.OnlineCoopGame.__new__(coop_module.OnlineCoopGame)
    game.net = net
    game.online_state = coop_module.OnlineCoopState.READY_CHECK
    game.role = 'guest'
    game.my_ready = False
    game.opponent_ready = False
    game._session_established = False
    game._ready_send_pending = False
    game._pending_disconnect_steam_id = 0
    game._disconnect_grace_timer = 0.0
    game._last_guest_input_seq = 0
    game._last_guest_piece_state_seq = 0
    game._last_host_guest_piece_ack_seq = 0
    game._last_input_ack_seq = 0
    game._guest_input_seq = 0
    game._guest_piece_state_out_seq = 0
    game._guest_piece_unacked_since = 0.0
    game._guest_pending_inputs = []
    game._held_gameplay_keys = set()
    game._board_state_seq = 0
    game._piece_state_seq = 0
    game._guest_board_seq = -1
    game._guest_piece_seq = -1
    game._guest_piece_state_timer = 0.0
    game._GUEST_PIECE_STATE_INTERVAL = 33.0
    game._last_sent_board_cells = None
    game._last_guest_sent_piece_signature = None
    game._last_piece_state_signature = None
    game._authoritative_gameplay_config = {}
    game._guest_board_cache = None
    game._guest_piece_cache = None
    game._guest_score_cache = {}
    game._guest_render_board_seq = -1
    game._guest_render_piece_seq = -1
    game._guest_last_authoritative_piece_elapsed_ms = 0.0
    game._guest_local_prediction_ms = 0.0
    game._GUEST_LOCAL_PREDICTION_MAX_MS = 150.0
    game._GUEST_PIECE_ACK_GRACE_S = 0.75
    game._game_start_pending_payload = None
    game._game_start_retry_timer = 0.0
    game._game_seed = 0
    game.selected_submode = 'endless'
    game.countdown_value = 3
    game.countdown_timer = 0
    game.game_over = False
    game.paused = False
    game.coop_game = None
    game.sound = SimpleNamespace(play=lambda _name: None)
    game._status_msg = ''
    game._status_timer = 0.0
    game._lobby_list = []
    game._lobby_list_filter = 'all'
    game._lobby_list_scroll = 0
    game._lobby_list_fetching = False
    game._lobby_list_fetch_start_time = 0.0
    game._auto_lobby_refresh_requested = False
    game._auto_lobby_refresh_timer = 0.0
    game._auto_lobby_refresh_interval = 0.0
    game._code_search_retry_timer = 0.0
    game._code_search_retry_code = ''
    game._code_search_retry_use_full_scan = False
    game._deferred_lobby_entries = {}
    game._deferred_lobby_refresh_timer = 0.0
    game._pending_access_revalidation_lobby_id = 0
    game._pending_revalidation_start_time = 0.0
    game._pending_reval_last_check_time = 0.0
    game._lobby_presence_probe_timer = 0.0
    game._LOBBY_PRESENCE_PROBE_INTERVAL_MS = 1000.0
    game._pause_cooldown_timer = 0.0
    game._session_ping_timer = 0.0
    game._SESSION_PING_INTERVAL_MS = 1000.0
    game._session_ping_backoff_ms = 0.0
    game._ready_resend_timer = 0.0
    game._READY_RESEND_INTERVAL_MS = 1000.0
    game._invite_after_lobby = False
    game._join_code_suppress_textinput = ''
    game.user_manager = None
    game.settings_manager = None
    game.screen = SimpleNamespace(get_width=lambda: 1280, get_height=lambda: 720)
    game.window_width = 1280
    game.window_height = 720
    game.fullscreen = False
    return game


def test_online_coop_process_messages_uses_get_messages_and_binds_lobby_sender():
    net = FakeNet([
        _message(42, {'type': MsgType.READY}),
    ])
    game = _make_game(net)

    game._process_messages()

    assert net.opponent_steam_id == 42
    assert game.opponent_ready is True


def test_online_coop_rejects_unknown_sender_when_opponent_is_known():
    class CoopSpy:
        game_over = False
        paused = False

        def __init__(self):
            self.injected = []

        def inject_remote_input(self, player, action):
            self.injected.append((player, action))

    net = FakeNet([
        _message(99, {'type': MsgType.GUEST_INPUT, 'seq': 1, 'action': 'move_left'}),
    ])
    net.opponent_steam_id = 42
    net.is_host = True
    game = _make_game(net)
    game.role = 'host'
    game.coop_game = CoopSpy()

    game._process_messages()

    assert game.coop_game.injected == []


def test_online_coop_uses_dedicated_coop_start_message():
    net = FakeNet()
    net.is_host = True
    game = _make_game(net)
    game.role = 'host'
    game._net_initialized = True
    game.my_ready = True
    game.opponent_ready = True
    game._GAME_START_RETRY_INTERVAL_MS = 1000.0

    game._check_both_ready()

    assert net.sent
    assert net.sent[0][0]['type'] == MsgType.COOP_GAME_START
    assert net.sent[0][0]['config']['das_delay'] >= 0.0
    assert net.sent[0][2] == CHANNEL_CONTROL
    assert game.online_state == coop_module.OnlineCoopState.COUNTDOWN


def test_online_coop_host_start_forwards_match_seed_to_coop_game(monkeypatch):
    captured = {}

    class FakeHostCoop:
        def __init__(self, **kwargs):
            captured['piece_rng_seed'] = kwargs.get('piece_rng_seed')
            self._event_listeners = []
            self.p1_frozen = False
            self.p2_frozen = False

    monkeypatch.setattr(coop_module, 'CoopGame', FakeHostCoop)
    monkeypatch.setattr(coop_module.OnlineCoopGame, '_send_board_state', lambda self, force_full=False: None)
    monkeypatch.setattr(coop_module.OnlineCoopGame, '_send_piece_state', lambda self: None)

    game = _make_game(FakeNet())
    game.role = 'host'
    game._game_seed = 13579

    game._start_game()

    assert captured['piece_rng_seed'] == 13579
    assert game.online_state == coop_module.OnlineCoopState.PLAYING


def test_online_coop_guest_ignores_out_of_order_board_snapshots():
    net = FakeNet([
        _message(42, _valid_board_state(seq=5, team_score=100)),
        _message(42, _valid_board_state(seq=4, team_score=10)),
    ])
    net.opponent_steam_id = 42
    game = _make_game(net)
    game.role = 'guest'

    game._process_messages()

    assert game._guest_board_seq == 5
    assert game._guest_board_cache['team_score'] == 100


def test_online_coop_guest_rejects_malformed_board_snapshot():
    net = FakeNet([
        _message(42, {'type': MsgType.COOP_BOARD_STATE, 'seq': 1, 'grid': [[0]], 'team_score': 100}),
    ])
    net.opponent_steam_id = 42
    game = _make_game(net)
    game.role = 'guest'

    game._process_messages()

    assert game._guest_board_seq == -1
    assert game._guest_board_cache is None


def test_online_coop_ignores_messages_on_unexpected_channel():
    net = FakeNet([
        _message(42, {'type': MsgType.READY}, channel=CHANNEL_STATE),
    ])
    game = _make_game(net)

    game._process_messages()

    assert game.opponent_ready is False


def test_online_coop_accepts_state_channel_board_snapshots():
    net = FakeNet([
        _message(42, _valid_board_state(seq=5, team_score=100), channel=CHANNEL_STATE),
    ])
    net.opponent_steam_id = 42
    game = _make_game(net)
    game.role = 'guest'

    game._process_messages()

    assert game._guest_board_seq == 5
    assert game._guest_board_cache['team_score'] == 100


def test_online_coop_join_code_digit_is_not_duplicated_by_keydown_and_textinput(monkeypatch):
    game = _make_game(FakeNet())
    game.online_state = coop_module.OnlineCoopState.LOBBY_MENU
    game._join_code_active = True
    game._join_code_input = ''

    events = [
        SimpleNamespace(type=pygame.KEYDOWN, key=pygame.K_5, unicode='5'),
        SimpleNamespace(type=pygame.TEXTINPUT, text='5'),
    ]
    monkeypatch.setattr(coop_module.pygame.event, 'get', lambda: events)

    assert game.handle_input() is True
    assert game._join_code_input == '5'


def test_online_coop_join_code_keydown_digit_works_without_textinput(monkeypatch):
    game = _make_game(FakeNet())
    game.online_state = coop_module.OnlineCoopState.LOBBY_MENU
    game._join_code_active = True
    game._join_code_input = ''

    events = [
        SimpleNamespace(type=pygame.KEYDOWN, key=pygame.K_5, unicode='5'),
    ]
    monkeypatch.setattr(coop_module.pygame.event, 'get', lambda: events)

    assert game.handle_input() is True
    assert game._join_code_input == '5'


def test_online_coop_filters_held_key_repeat_before_relaying_guest_movement(monkeypatch):
    net = FakeNet()
    game = _make_game(net)
    game.online_state = coop_module.OnlineCoopState.PLAYING
    game.role = 'guest'
    predicted = []
    monkeypatch.setattr(game, '_predict_guest_input', lambda action: predicted.append(action))

    event = SimpleNamespace(key=pygame.K_LEFT)
    game._handle_gameplay_keydown(event)
    game._handle_gameplay_keydown(event)

    assert net.sent == []
    assert predicted == ['move_left']


def test_online_coop_host_accepts_arrow_keys_as_p1_alternate_controls(monkeypatch):
    class CoopSpy:
        def __init__(self):
            self.injected = []

        def inject_remote_input(self, player, action):
            self.injected.append((player, action))

    game = _make_game(FakeNet())
    game.online_state = coop_module.OnlineCoopState.PLAYING
    game.role = 'host'
    game.coop_game = CoopSpy()
    monkeypatch.setattr(game, '_push_piece_state_if_changed', lambda *args, **kwargs: None)

    game._handle_gameplay_keydown(SimpleNamespace(key=pygame.K_LEFT))
    game._handle_gameplay_keydown(SimpleNamespace(key=pygame.K_SPACE))
    game._handle_gameplay_keydown(SimpleNamespace(key=pygame.K_RSHIFT))
    game._handle_gameplay_keyup(SimpleNamespace(key=pygame.K_LEFT))

    assert game.coop_game.injected == [
        ('P1', 'move_left'),
        ('P1', 'hard_drop'),
        ('P1', 'hold'),
        ('P1', 'das_stop'),
    ]


def test_online_coop_guest_accepts_wasd_keys_as_p2_alternate_controls(monkeypatch):
    net = FakeNet()
    game = _make_game(net)
    game.online_state = coop_module.OnlineCoopState.PLAYING
    game.role = 'guest'
    predicted = []
    monkeypatch.setattr(game, '_predict_guest_input', lambda action: predicted.append(action))
    monkeypatch.setattr(game, '_send_guest_piece_state', lambda force=False: True)

    game._handle_gameplay_keydown(SimpleNamespace(key=pygame.K_a))
    game._handle_gameplay_keydown(SimpleNamespace(key=pygame.K_LSHIFT))
    game._handle_gameplay_keydown(SimpleNamespace(key=pygame.K_e))
    game._handle_gameplay_keyup(SimpleNamespace(key=pygame.K_a))

    assert predicted == ['move_left', 'hard_drop', 'hold', 'das_stop']
    sent_actions = [payload['action'] for payload, _reliable, _channel in net.sent]
    assert sent_actions == ['hard_drop', 'hold']


def test_online_coop_host_board_snapshot_emits_empty_semantic_full_snapshot_for_empty_board():
    class FakeBoard:
        width = 20
        height = 20
        grid = [[(0, 0, 0) for _ in range(20)] for _ in range(20)]
        occupancy = [[False for _ in range(20)] for _ in range(20)]
        owners = [[None for _ in range(20)] for _ in range(20)]

    net = FakeNet()
    game = _make_game(net)
    game.role = 'host'
    game.coop_game = SimpleNamespace(
        board=FakeBoard(),
        team_score=0,
        total_lines_cleared=0,
        level=1,
        fall_speed=900.0,
        p1_frozen=False,
        p2_frozen=False,
    )

    game._send_board_state()

    payload, reliable, channel = net.sent[0]
    assert payload['format'] == 'semantic_delta_v1'
    assert payload['full'] is True
    assert payload['cells'] == []
    assert reliable is False
    assert channel == CHANNEL_STATE


def test_online_coop_host_board_snapshot_serializes_semantic_locked_cells():
    texture_slice = coop_module.TextureSlice('T', rel_x=1, rel_y=2, width=4, height=4, rotation=3)

    class FakeBoard:
        width = 20
        height = 20
        grid = [[(0, 0, 0) for _ in range(20)] for _ in range(20)]
        occupancy = [[False for _ in range(20)] for _ in range(20)]
        owners = [[None for _ in range(20)] for _ in range(20)]
        texture_grid = [[None for _ in range(20)] for _ in range(20)]
        gold = [[False for _ in range(20)] for _ in range(20)]

    board = FakeBoard()
    board.occupancy[19][3] = True
    board.grid[19][3] = (10, 20, 30)
    board.owners[19][3] = 'P2'
    board.texture_grid[19][3] = texture_slice
    board.gold[19][3] = True

    net = FakeNet()
    game = _make_game(net)
    game.role = 'host'
    game.coop_game = SimpleNamespace(
        board=board,
        team_score=0,
        total_lines_cleared=0,
        level=1,
        fall_speed=900.0,
        p1_frozen=False,
        p2_frozen=False,
    )

    game._send_board_state()

    assert net.sent[0][0]['cells'] == [[3, 19, 'T', 'P2', 1, 2, 4, 4, 3, 1, 10, 20, 30]]


def test_online_coop_host_board_snapshot_carries_latest_guest_ack():
    class FakeBoard:
        width = 20
        height = 20
        grid = [[(0, 0, 0) for _ in range(20)] for _ in range(20)]
        occupancy = [[False for _ in range(20)] for _ in range(20)]
        owners = [[None for _ in range(20)] for _ in range(20)]

    net = FakeNet()
    game = _make_game(net)
    game.role = 'host'
    game._last_input_ack_seq = 12
    game.coop_game = SimpleNamespace(
        board=FakeBoard(),
        team_score=0,
        total_lines_cleared=0,
        level=1,
        fall_speed=900.0,
        p1_frozen=False,
        p2_frozen=False,
    )

    game._send_board_state()

    assert net.sent[0][0]['input_ack'] == 12
    assert net.sent[0][2] == CHANNEL_STATE


def test_online_coop_host_board_heartbeat_forces_full_snapshot_after_delta_send():
    class FakeBoard:
        width = 20
        height = 20
        grid = [[(0, 0, 0) for _ in range(20)] for _ in range(20)]
        occupancy = [[False for _ in range(20)] for _ in range(20)]
        owners = [[None for _ in range(20)] for _ in range(20)]
        texture_grid = [[None for _ in range(20)] for _ in range(20)]
        gold = [[False for _ in range(20)] for _ in range(20)]

        def is_valid_position_for_player(self, piece, player, dy=0):
            return False

    class FakePiece:
        def __init__(self, shape_index, x, y, rotation_state=0):
            self.shape_index = shape_index
            self.x = x
            self.y = y
            self.rotation_state = rotation_state

    class FakeHostCoop:
        def __init__(self):
            self.board = FakeBoard()
            self.p1_current_piece = FakePiece(0, 3, 0)
            self.p2_current_piece = FakePiece(1, 13, 0)
            self.p1_next_piece = FakePiece(2, 0, 0)
            self.p2_next_piece = FakePiece(3, 0, 0)
            self.p1_hold_piece = None
            self.p2_hold_piece = None
            self.p1_frozen = False
            self.p2_frozen = False
            self.team_score = 0
            self.total_lines_cleared = 0
            self.level = 1
            self.fall_speed = 900.0
            self.game_over = False
            self.elapsed_time = 0.0

        def update(self, _dt):
            self.elapsed_time += float(_dt)

    net = FakeNet()
    net.tick = lambda: None
    game = _make_game(net)
    game.role = 'host'
    game.online_state = coop_module.OnlineCoopState.PLAYING
    game._net_initialized = True
    game._auto_connect_attempted = True
    game._auto_connect_retry_timer = 0.0
    game._last_frozen_flags = (False, False)
    game._BOARD_STATE_INTERVAL = 250.0
    game._PIECE_STATE_INTERVAL = 1000.0
    game._board_state_timer = 240.0
    game._piece_state_timer = 0.0
    game._pause_cooldown_timer = 0.0
    game.coop_game = FakeHostCoop()
    game._last_sent_board_cells = {(0, 0): ('I', 'P1', 0, 0, 4, 4, 0, False, 10, 20, 30)}
    game._last_piece_state_signature = game._current_piece_state_signature()

    game.update(16)

    board_payloads = [payload for payload, _reliable, channel in net.sent if channel == CHANNEL_STATE and payload['type'] == MsgType.COOP_BOARD_STATE]
    assert board_payloads
    assert board_payloads[-1]['full'] is True


def test_online_coop_host_update_pushes_piece_state_on_live_change():
    class FakeBoard:
        def is_valid_position_for_player(self, piece, player, dy=0):
            return False

    class FakePiece:
        def __init__(self, shape_index, x, y, rotation_state=0):
            self.shape_index = shape_index
            self.x = x
            self.y = y
            self.rotation_state = rotation_state

    class FakeHostCoop:
        def __init__(self):
            self.board = FakeBoard()
            self.p1_current_piece = FakePiece(0, 3, 0)
            self.p2_current_piece = FakePiece(1, 13, 0)
            self.p1_next_piece = FakePiece(2, 0, 0)
            self.p2_next_piece = FakePiece(3, 0, 0)
            self.p1_hold_piece = None
            self.p2_hold_piece = None
            self.p1_frozen = False
            self.p2_frozen = False
            self.team_score = 0
            self.total_lines_cleared = 0
            self.level = 1
            self.fall_speed = 900.0
            self.game_over = False

        def update(self, _dt):
            self.p2_current_piece.y += 1

    net = FakeNet()
    net.tick = lambda: None
    game = _make_game(net)
    game.role = 'host'
    game.online_state = coop_module.OnlineCoopState.PLAYING
    game._net_initialized = True
    game._auto_connect_attempted = True
    game._auto_connect_retry_timer = 0.0
    game._last_frozen_flags = (False, False)
    game._BOARD_STATE_INTERVAL = 250.0
    game._PIECE_STATE_INTERVAL = 100.0
    game._board_state_timer = 0.0
    game._piece_state_timer = 0.0
    game._pause_cooldown_timer = 0.0
    game.coop_game = FakeHostCoop()
    game._last_piece_state_signature = game._current_piece_state_signature()

    game.update(16)

    sent_types = [payload['type'] for payload, _reliable, _channel in net.sent]
    assert sent_types == [MsgType.COOP_PIECE_STATE]
    assert net.sent[0][0]['p2_current']['y'] == 1


def test_online_coop_guest_update_sends_guest_piece_state_after_local_prediction():
    class FakeRenderCoop:
        def __init__(self):
            self.effects_enabled = False
            self.game_over = False
            self.paused = False
            self.p1_frozen = False
            self._p1_pending_unfreeze = False
            self.p1_das_direction = 1
            self.p1_soft_drop_active = True
            self.p2_frozen = False
            self.p2_current_piece = SimpleNamespace(shape_index=1, x=13, y=0, rotation_state=0)
            self.p2_next_piece = SimpleNamespace(shape_index=3)
            self.p2_hold_piece = None

        def update(self, _dt):
            self.p2_current_piece.y += 1

        def _lock_and_new_piece(self, _player):
            raise AssertionError('guest preview should patch lock path')

        def _do_unfreeze(self, _player):
            raise AssertionError('guest preview should patch unfreeze path')

    net = FakeNet()
    net.tick = lambda: None
    game = _make_game(net)
    game.role = 'guest'
    game.online_state = coop_module.OnlineCoopState.PLAYING
    game._net_initialized = True
    game._auto_connect_attempted = True
    game._auto_connect_retry_timer = 0.0
    game.coop_game = FakeRenderCoop()
    game._process_messages = lambda: None
    game._apply_guest_render_cache = lambda: game.coop_game

    game.update(16)

    guest_piece_payloads = [payload for payload, _reliable, channel in net.sent if payload['type'] == MsgType.GUEST_PIECE_STATE and channel == CHANNEL_STATE]
    assert guest_piece_payloads
    assert guest_piece_payloads[-1]['p2_current']['y'] == 1


def test_online_coop_host_applies_guest_piece_state_as_remote_authority():
    class FakeBoard:
        def is_valid_position_for_player(self, piece, player, dy=0):
            return player == 'P2' and dy == 0 and piece.x == 12 and piece.y == 4 and piece.rotation_state == 1

    class FakePiece:
        def __init__(self, shape_index, x, y, rotation_state=0):
            self.shape_index = shape_index
            self.x = x
            self.y = y
            self.rotation_state = rotation_state

    class FakeHostCoop:
        def __init__(self):
            self.board = FakeBoard()
            self.remote_authority_players = set()
            self.p2_current_piece = FakePiece(1, 13, 0, 0)
            self.p2_frozen = False
            self.p2_das_direction = 1
            self.p2_das_charged = True
            self.p2_das_timer = 12.0
            self.p2_das_repeat_timer = 9.0
            self.p2_soft_drop_active = True
            self.p2_soft_drop_timer = 7.0
            self.p2_fall_time = 30.0
            self.reset_calls = []

        def _apply_block_style(self, piece):
            piece.styled = True

        def _reset_player_lock_state(self, player):
            self.reset_calls.append(player)

    net = FakeNet([
        _message(42, {
            'type': MsgType.GUEST_PIECE_STATE,
            'seq': 3,
            'p2_current': {'si': 1, 'x': 12, 'y': 4, 'r': 1},
            'p2_frozen': False,
        }, channel=CHANNEL_STATE),
    ])
    net.opponent_steam_id = 42
    game = _make_game(net)
    game.role = 'host'
    game.coop_game = FakeHostCoop()

    game._process_messages()

    assert 'P2' in game.coop_game.remote_authority_players
    assert game.coop_game.p2_current_piece.x == 12
    assert game.coop_game.p2_current_piece.y == 4
    assert game.coop_game.p2_current_piece.rotation_state == 1
    assert game.coop_game.p2_das_direction == 0
    assert game.coop_game.p2_soft_drop_active is False
    assert game.coop_game.p2_fall_time == 0.0
    assert game.coop_game.reset_calls == ['P2']


def test_online_coop_host_piece_snapshot_acknowledges_latest_guest_piece_state():
    class FakeBoard:
        def is_valid_position_for_player(self, piece, player, dy=0):
            return dy == 0

    class FakePiece:
        def __init__(self, shape_index, x, y, rotation_state=0):
            self.shape_index = shape_index
            self.x = x
            self.y = y
            self.rotation_state = rotation_state

    class FakeHostCoop:
        def __init__(self):
            self.board = FakeBoard()
            self.remote_authority_players = set()
            self.p1_current_piece = FakePiece(0, 3, 0)
            self.p2_current_piece = FakePiece(1, 13, 0)
            self.p1_next_piece = FakePiece(2, 0, 0)
            self.p2_next_piece = FakePiece(3, 0, 0)
            self.p1_hold_piece = None
            self.p2_hold_piece = None
            self.p1_frozen = False
            self.p2_frozen = False
            self.team_score = 0
            self.total_lines_cleared = 0
            self.level = 1
            self.fall_speed = 900.0
            self.elapsed_time = 0.0

        def _apply_block_style(self, piece):
            return None

        def _reset_player_lock_state(self, player):
            return None

    net = FakeNet([
        _message(42, {
            'type': MsgType.GUEST_PIECE_STATE,
            'seq': 6,
            'p2_current': {'si': 1, 'x': 12, 'y': 2, 'r': 0},
        }, channel=CHANNEL_STATE),
    ])
    net.opponent_steam_id = 42
    game = _make_game(net)
    game.role = 'host'
    game.coop_game = FakeHostCoop()

    game._process_messages()
    game._send_piece_state()

    assert game._last_guest_piece_state_seq == 6
    assert net.sent[-1][0]['guest_piece_ack'] == 6


def test_online_coop_guest_keeps_unacked_local_p2_until_host_guest_piece_ack_catches_up():
    class FakeBoard:
        width = 20
        height = 20

    class FakeRenderCoop:
        def __init__(self):
            self.screen = None
            self.window_width = 0
            self.window_height = 0
            self.fullscreen = False
            self.board = FakeBoard()
            self.p1_current_piece = None
            self.p2_current_piece = SimpleNamespace(shape_index=1, x=12, y=1, rotation_state=0)
            self.p1_next_piece = None
            self.p2_next_piece = SimpleNamespace(shape_index=3)
            self.p1_hold_piece = None
            self.p2_hold_piece = None

        def _apply_block_style(self, piece):
            return None

    game = _make_game(FakeNet())
    game.role = 'guest'
    game.online_state = coop_module.OnlineCoopState.PLAYING
    game.coop_game = FakeRenderCoop()
    game._guest_board_cache = game._normalize_board_snapshot(_valid_board_state(seq=8, team_score=250))
    game._guest_render_board_seq = 8
    game._guest_piece_state_out_seq = 5
    game._last_host_guest_piece_ack_seq = 3
    game._guest_piece_unacked_since = time.time()

    stale_piece_state = _valid_piece_state(seq=9)
    stale_piece_state['guest_piece_ack'] = 4
    stale_piece_state['p2_current']['x'] = 13
    stale_piece_state['p2_current']['y'] = 0
    game._guest_piece_cache = game._normalize_piece_snapshot(stale_piece_state)

    game._apply_guest_render_cache()

    assert game.coop_game.p2_current_piece.x == 12
    assert game.coop_game.p2_current_piece.y == 1
    assert game._last_host_guest_piece_ack_seq == 4

    fresh_piece_state = _valid_piece_state(seq=10)
    fresh_piece_state['guest_piece_ack'] = 5
    fresh_piece_state['p2_current']['x'] = 11
    fresh_piece_state['p2_current']['y'] = 2
    game._guest_piece_cache = game._normalize_piece_snapshot(fresh_piece_state)

    game._apply_guest_render_cache()

    assert game.coop_game.p2_current_piece.x == 11
    assert game.coop_game.p2_current_piece.y == 2
    assert game._guest_piece_unacked_since == 0.0


def test_online_coop_guest_update_advances_local_p2_prediction():
    class FakeRenderCoop:
        def __init__(self):
            self.effects_enabled = False
            self.game_over = False
            self.paused = False
            self.p1_frozen = False
            self._p1_pending_unfreeze = False
            self.p1_das_direction = 1
            self.p1_soft_drop_active = True
            self.p2_frozen = False
            self.p2_current_piece = SimpleNamespace(shape_index=1, x=13, y=0, rotation_state=0)
            self.p2_next_piece = SimpleNamespace(shape_index=3)
            self.p2_hold_piece = None
            self.update_calls = 0

        def update(self, _dt):
            self.update_calls += 1
            assert self.p1_frozen is True
            self.p2_current_piece.y += 1

        def _lock_and_new_piece(self, _player):
            raise AssertionError('guest preview should patch lock path')

        def _do_unfreeze(self, _player):
            raise AssertionError('guest preview should patch unfreeze path')

    net = FakeNet()
    net.tick = lambda: None
    game = _make_game(net)
    game.role = 'guest'
    game.online_state = coop_module.OnlineCoopState.PLAYING
    game._net_initialized = True
    game._auto_connect_attempted = True
    game._auto_connect_retry_timer = 0.0
    render_game = FakeRenderCoop()
    game.coop_game = render_game
    game._process_messages = lambda: None
    game._apply_guest_render_cache = lambda: render_game

    game.update(16)

    assert render_game.update_calls == 1
    assert render_game.p2_current_piece.y == 1
    assert game._guest_local_prediction_ms == 16.0
    assert render_game.p1_frozen is False


def test_online_coop_guest_hydrates_local_coop_renderer(monkeypatch):
    captured = {}

    class FakeBoard:
        width = 20
        height = 20

    class FakeRenderCoop:
        def __init__(self, **kwargs):
            captured['piece_rng_seed'] = kwargs.get('piece_rng_seed')
            self.screen = kwargs.get('screen')
            self.window_width = self.screen.get_width()
            self.window_height = self.screen.get_height()
            self.fullscreen = kwargs.get('fullscreen')
            self.board = FakeBoard()
            self.applied_styles = []
            self.rendered = False
            self.curtain = False
            self.p1_frozen = False
            self.p2_frozen = False
            self.game_over = False
            self.paused = False

        def _apply_block_style(self, piece):
            self.applied_styles.append(piece.shape_index)

        def _render_game(self):
            self.rendered = True

        def _draw_opening_curtain(self):
            self.curtain = True

    monkeypatch.setattr(coop_module, 'CoopGame', FakeRenderCoop)

    game = _make_game(FakeNet())
    game.role = 'guest'
    game.online_state = coop_module.OnlineCoopState.PLAYING
    game._game_seed = 4242
    game._guest_board_cache = game._normalize_board_snapshot(_valid_board_state(seq=8, team_score=250))
    game._guest_piece_cache = game._normalize_piece_snapshot(_valid_piece_state(seq=9))

    render_game = game._apply_guest_render_cache()

    assert captured['piece_rng_seed'] == 4242
    assert isinstance(render_game, FakeRenderCoop)
    assert render_game.team_score == 250
    assert render_game.p1_current_piece.shape_index == 0
    assert render_game.p2_current_piece.shape_index == 1
    assert render_game.p1_next_piece.shape_index == 2
    assert render_game.p2_next_piece.shape_index == 3


def test_online_coop_guest_render_effects_advance_screen_shake():
    game = _make_game(FakeNet())
    game.role = 'guest'
    game.coop_game = SimpleNamespace(
        effects_enabled=True,
        update_particles=lambda _dt: None,
        update_ambient_particles=lambda _dt: None,
        update_drop_trails=lambda _dt: None,
        _update_line_clear_effects=lambda _dt: None,
        screen_shake=120.0,
        _screen_shake_initial=120.0,
        shake_intensity=3,
    )

    game._update_guest_render_effects(16.0)

    assert game.coop_game.screen_shake == 104.0


def test_online_coop_guest_keeps_predicted_p2_piece_until_ack_catches_up():
    class FakeBoard:
        width = 20
        height = 20

    class FakeRenderCoop:
        def __init__(self):
            self.screen = None
            self.window_width = 0
            self.window_height = 0
            self.fullscreen = False
            self.board = FakeBoard()
            self.p1_current_piece = None
            self.p2_current_piece = SimpleNamespace(shape_index=1, x=12, y=0, rotation_state=0)
            self.p1_next_piece = None
            self.p2_next_piece = SimpleNamespace(shape_index=3)
            self.p1_hold_piece = None
            self.p2_hold_piece = None

        def _apply_block_style(self, piece):
            return None

    game = _make_game(FakeNet())
    game.role = 'guest'
    game.online_state = coop_module.OnlineCoopState.PLAYING
    game.coop_game = FakeRenderCoop()
    game._guest_board_cache = game._normalize_board_snapshot(_valid_board_state(seq=8, team_score=250))
    game._guest_render_board_seq = 8
    game._guest_pending_inputs = [(8, 'move_left')]
    game._guest_input_seq = 8
    stale_piece_state = _valid_piece_state(seq=9)
    stale_piece_state['input_ack'] = 7
    stale_piece_state['p2_current']['x'] = 13
    game._guest_piece_cache = game._normalize_piece_snapshot(stale_piece_state)

    game._apply_guest_render_cache()

    assert game.coop_game.p1_current_piece.x == 3
    assert game.coop_game.p2_current_piece.x == 12
    assert game._guest_pending_inputs == [(8, 'move_left')]

    fresh_piece_state = _valid_piece_state(seq=10)
    fresh_piece_state['input_ack'] = 8
    fresh_piece_state['p2_current']['x'] = 11
    game._guest_piece_cache = game._normalize_piece_snapshot(fresh_piece_state)

    game._apply_guest_render_cache()

    assert game.coop_game.p2_current_piece.x == 11
    assert game._guest_pending_inputs == []


def test_online_coop_guest_keeps_locally_simulated_p2_until_host_piece_time_catches_up():
    class FakeBoard:
        width = 20
        height = 20

    class FakeRenderCoop:
        def __init__(self):
            self.screen = None
            self.window_width = 0
            self.window_height = 0
            self.fullscreen = False
            self.board = FakeBoard()
            self.p1_current_piece = None
            self.p2_current_piece = SimpleNamespace(shape_index=1, x=13, y=1, rotation_state=0)
            self.p1_next_piece = None
            self.p2_next_piece = SimpleNamespace(shape_index=3)
            self.p1_hold_piece = None
            self.p2_hold_piece = None
            self.p2_frozen = False

        def _apply_block_style(self, piece):
            return None

    game = _make_game(FakeNet())
    game.role = 'guest'
    game.online_state = coop_module.OnlineCoopState.PLAYING
    game.coop_game = FakeRenderCoop()
    game._guest_board_cache = game._normalize_board_snapshot(_valid_board_state(seq=8, team_score=250))
    game._guest_render_board_seq = 8
    game._guest_last_authoritative_piece_elapsed_ms = 1000.0
    game._guest_local_prediction_ms = 60.0

    stale_piece_state = _valid_piece_state(seq=9)
    stale_piece_state['host_elapsed_ms'] = 1040.0
    stale_piece_state['p2_current']['y'] = 0
    game._guest_piece_cache = game._normalize_piece_snapshot(stale_piece_state)

    game._apply_guest_render_cache()

    assert game.coop_game.p2_current_piece.y == 1
    assert game._guest_local_prediction_ms == 60.0

    fresh_piece_state = _valid_piece_state(seq=10)
    fresh_piece_state['host_elapsed_ms'] = 1065.0
    fresh_piece_state['p2_current']['y'] = 2
    game._guest_piece_cache = game._normalize_piece_snapshot(fresh_piece_state)

    game._apply_guest_render_cache()

    assert game.coop_game.p2_current_piece.y == 2
    assert game._guest_local_prediction_ms == 0.0
    assert game._guest_last_authoritative_piece_elapsed_ms == 1065.0


def test_online_coop_guest_applies_host_authoritative_das_timing():
    class FakeBoard:
        width = 20
        height = 20

    class FakeRenderCoop:
        def __init__(self):
            self.screen = None
            self.window_width = 0
            self.window_height = 0
            self.fullscreen = False
            self.board = FakeBoard()
            self.p1_current_piece = None
            self.p2_current_piece = None
            self.p1_next_piece = None
            self.p2_next_piece = None
            self.p1_hold_piece = None
            self.p2_hold_piece = None
            self.p1_frozen = False
            self.p2_frozen = False
            self._cached_das_delay = 999.0
            self._cached_das_repeat = 999.0
            self._das_settings_dirty = True

        def _apply_block_style(self, piece):
            return None

    game = _make_game(FakeNet())
    game.role = 'guest'
    game.online_state = coop_module.OnlineCoopState.PLAYING
    game.coop_game = FakeRenderCoop()
    board_state = _valid_board_state(seq=3)
    board_state['das_delay'] = 145.0
    board_state['das_repeat'] = 32.0
    piece_state = _valid_piece_state(seq=4)
    piece_state['das_delay'] = 145.0
    piece_state['das_repeat'] = 32.0
    game._guest_board_cache = game._normalize_board_snapshot(board_state)
    game._guest_piece_cache = game._normalize_piece_snapshot(piece_state)

    game._apply_guest_render_cache()

    assert game.coop_game._cached_das_delay == 145.0
    assert game.coop_game._cached_das_repeat == 32.0
    assert game.coop_game._das_settings_dirty is False


def test_online_coop_line_clear_event_triggers_guest_render_sweep(monkeypatch):
    class FakeBoard:
        width = 20
        height = 20

    class FakeRenderCoop:
        def __init__(self, **kwargs):
            self.screen = kwargs.get('screen')
            self.window_width = self.screen.get_width()
            self.window_height = self.screen.get_height()
            self.fullscreen = kwargs.get('fullscreen')
            self.board = FakeBoard()
            self.started_sweep = []

        def _start_line_clear_sweep(self, rows):
            self.started_sweep = list(rows)

    monkeypatch.setattr(coop_module, 'CoopGame', FakeRenderCoop)
    row = [[20, 30, 40] for _ in range(20)]
    net = FakeNet([
        _message(42, {
            'type': MsgType.COOP_LOCK_EVENT,
            'new_score': 500,
            'new_level': 2,
            'total_lines': 1,
            'cleared_rows': [19],
            'row_colors': {'19': row},
        }),
    ])
    net.opponent_steam_id = 42
    game = _make_game(net)
    game.role = 'guest'
    game.online_state = coop_module.OnlineCoopState.PLAYING

    game._process_messages()

    assert game.online_state == coop_module.OnlineCoopState.PLAYING
    assert game.coop_game.started_sweep == [19]
    assert game.coop_game.line_clear_pending_rows == [19]
    assert game._guest_score_cache['team_score'] == 500


def test_online_coop_piece_placed_event_triggers_guest_lock_feedback(monkeypatch):
    class FakeBoard:
        width = 20
        height = 20

    class FakeRenderCoop:
        def __init__(self, **kwargs):
            self.screen = kwargs.get('screen')
            self.window_width = self.screen.get_width()
            self.window_height = self.screen.get_height()
            self.fullscreen = kwargs.get('fullscreen')
            self.board = FakeBoard()
            self.cell_size = 24
            self.board_offset_x = 10
            self.board_offset_y = 20
            self.explosions = []

        def create_lock_explosion(self, x, y, color, cell_size=25):
            self.explosions.append((x, y, color, cell_size))

    monkeypatch.setattr(coop_module, 'CoopGame', FakeRenderCoop)
    net = FakeNet([
        _message(42, {
            'type': MsgType.COOP_LOCK_EVENT,
            'event': 'piece_placed',
            'new_score': 100,
            'new_level': 1,
            'lock_cells': [[3, 19, 10, 20, 30]],
            'cleared_rows': [],
            'row_colors': {},
        }),
    ])
    net.opponent_steam_id = 42
    game = _make_game(net)
    game.role = 'guest'
    game.online_state = coop_module.OnlineCoopState.PLAYING

    game._process_messages()

    assert game.coop_game.explosions == [(94, 488, (10, 20, 30), 24)]
    assert game._guest_score_cache['team_score'] == 100


def test_online_coop_guest_hard_drop_prediction_triggers_drop_trail_and_shake(monkeypatch):
    class FakeBoard:
        def is_valid_position_for_player(self, piece, player, dy=0):
            return int(piece.y + dy) <= 4

    class FakePiece:
        shape_index = 1
        x = 10
        y = 0
        rotation_state = 0
        color = (80, 120, 200)

        def get_cells(self):
            return [(self.x, self.y)]

    class FakeRenderCoop:
        def __init__(self):
            self.effects_enabled = True
            self.board = FakeBoard()
            self.p2_current_piece = FakePiece()
            self.cell_size = 20
            self.board_offset_x = 100
            self.board_offset_y = 50
            self.trails = []
            self.shakes = 0

        def create_drop_trail(self, x, y_start, y_end, color, cell_size):
            self.trails.append((x, y_start, y_end, color, cell_size))

        def trigger_hard_drop_screen_shake(self):
            self.shakes += 1

        def _reset_player_lock_state(self, player):
            return None

        def _effective_lock_delay_for_player(self, player, piece):
            return 500.0

    game = _make_game(FakeNet())
    game.role = 'guest'
    game.online_state = coop_module.OnlineCoopState.PLAYING
    game._guest_board_cache = game._normalize_board_snapshot(_valid_board_state(seq=2))
    game._guest_piece_cache = game._normalize_piece_snapshot(_valid_piece_state(seq=3))
    render_game = FakeRenderCoop()
    game._apply_guest_render_cache = lambda: render_game

    game._predict_guest_input('hard_drop')

    assert render_game.p2_current_piece.y == 4
    assert render_game.trails == [(300, 50, 130, (80, 120, 200), 20)]
    assert render_game.shakes == 1


def test_online_coop_guest_starts_block_fall_animation_after_final_board_state():
    class FakeBoard:
        width = 20
        height = 20

    class FakeRenderCoop:
        def __init__(self):
            self.screen = None
            self.window_width = 0
            self.window_height = 0
            self.fullscreen = False
            self.board = FakeBoard()
            self.line_clear_pending_rows = [19]
            self.line_clear_sweep_active = True
            self._fall_animation_rows_key = None
            self.started_fall = []

        def _start_block_fall_animation(self, rows):
            self.started_fall = list(rows)
            self._fall_animation_rows_key = tuple(sorted(rows))

    game = _make_game(FakeNet())
    game.role = 'guest'
    game.online_state = coop_module.OnlineCoopState.PLAYING
    game.coop_game = FakeRenderCoop()
    board_state = _valid_board_state(seq=2, team_score=500)
    board_state['grid'][18][0] = [10, 20, 30]
    board_state['owners'][18][0] = 'P1'
    game._guest_board_cache = game._normalize_board_snapshot(board_state)

    game._apply_guest_render_cache()

    assert game.coop_game.started_fall == [19]


def test_online_coop_ignores_legacy_pvp_game_start_message():
    net = FakeNet([
        _message(42, {'type': MsgType.GAME_START, 'seed': 123}),
    ])
    net.opponent_steam_id = 42
    game = _make_game(net)

    game._process_messages()

    assert game.online_state == coop_module.OnlineCoopState.READY_CHECK
    assert game._game_seed == 0


def test_steam_networking_send_coop_start_uses_coop_message_type():
    net = SteamNetworking.__new__(SteamNetworking)
    sent = []

    def fake_send(data, reliable=True, channel=0):
        sent.append((data, reliable, channel))
        return True

    net.send = fake_send

    assert net.send_coop_start(123, sub_mode='endless') is True
    assert sent[0][0]['type'] == MsgType.COOP_GAME_START
    assert sent[0][0]['seed'] == 123
    assert sent[0][0]['sub_mode'] == 'endless'
    assert sent[0][1] is True
    assert sent[0][2] == CHANNEL_CONTROL


def test_online_coop_invite_existing_lobby_does_not_recreate_lobby():
    net = FakeNet()
    game = _make_game(net)
    game._net_initialized = True

    game._execute_button_action('invite_friend')

    assert net.invited is True
    assert net.created == []
    assert game._invite_after_lobby is False


def test_online_coop_invite_without_lobby_creates_private_lobby_and_defers_invite():
    net = FakeNet()
    net.lobby_id = 0
    game = _make_game(net)
    game._net_initialized = True

    game._execute_button_action('invite_friend')

    assert net.created == [False]
    assert net.invited is False
    assert game._invite_after_lobby is True


def test_online_coop_lobby_filter_is_display_only_and_preserves_private_entries():
    game = _make_game(FakeNet())
    game._lobby_list = [
        {'id': 1, 'visibility': 'public'},
        {'id': 2, 'visibility': 'private'},
        {'id': 3, 'visibility': 'unknown'},
    ]

    assert [entry['id'] for entry in game._get_lobby_entries_for_display()] == [1, 2, 3]

    game._set_lobby_list_filter('public', refresh=False)

    assert [entry['id'] for entry in game._get_lobby_entries_for_display()] == [1, 3]
    assert [entry['id'] for entry in game._lobby_list] == [1, 2, 3]
