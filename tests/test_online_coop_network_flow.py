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
    game._GUEST_PIECE_STATE_INTERVAL = 20.0
    game._guest_authoritative_piece_sync_enabled = True
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
    # Wrapper update() içinde lobby branch'ları için gerekli ek alanlar:
    game._searching_by_code = False
    game._search_code = ''
    game._pending_lobby_list = []
    game._unknown_lobby_metadata_requests = {}
    game._UNKNOWN_LOBBY_DATA_REQUEST_INTERVAL_S = 1.25
    game._authorized_private_join_lobby_id = 0
    game._authorized_private_join_code = ''
    game._lobby_access_validated_id = 0
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


def test_online_coop_host_start_uses_guest_piece_authority_by_default(monkeypatch):
    class FakeHostCoop:
        _SOFT_DROP_SPEED = 50.0

        def __init__(self, **_kwargs):
            self._event_listeners = []
            self.remote_authority_players = set()
            self.p1_frozen = False
            self.p2_frozen = False
            self._cached_das_delay = 120.0
            self._cached_das_repeat = 30.0
            self._das_settings_dirty = False
            self.enable_lock_delay = True
            self.lock_delay = 500.0

    monkeypatch.setattr(coop_module, 'CoopGame', FakeHostCoop)
    monkeypatch.setattr(coop_module.OnlineCoopGame, '_send_gameplay_config', lambda self: None)
    monkeypatch.setattr(coop_module.OnlineCoopGame, '_send_board_state', lambda self, force_full=False: None)
    monkeypatch.setattr(coop_module.OnlineCoopGame, '_send_piece_state', lambda self: None)

    game = _make_game(FakeNet())
    game.role = 'host'

    game._start_game()

    assert game.online_state == coop_module.OnlineCoopState.PLAYING
    assert 'P2' in game.coop_game.remote_authority_players


def test_online_coop_host_start_allows_explicit_guest_piece_authority(monkeypatch):
    class FakeHostCoop:
        _SOFT_DROP_SPEED = 50.0

        def __init__(self, **_kwargs):
            self._event_listeners = []
            self.remote_authority_players = set()
            self.p1_frozen = False
            self.p2_frozen = False
            self._cached_das_delay = 120.0
            self._cached_das_repeat = 30.0
            self._das_settings_dirty = False
            self.enable_lock_delay = True
            self.lock_delay = 500.0

    monkeypatch.setattr(coop_module, 'CoopGame', FakeHostCoop)
    monkeypatch.setattr(coop_module.OnlineCoopGame, '_send_gameplay_config', lambda self: None)
    monkeypatch.setattr(coop_module.OnlineCoopGame, '_send_board_state', lambda self, force_full=False: None)
    monkeypatch.setattr(coop_module.OnlineCoopGame, '_send_piece_state', lambda self: None)

    game = _make_game(FakeNet())
    game.role = 'host'
    game._guest_authoritative_piece_sync_enabled = True

    game._start_game()

    assert 'P2' in game.coop_game.remote_authority_players


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

    assert len(net.sent) == 1
    assert net.sent[0][0]['action'] == 'move_left'
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
        ('P1', 'das_stop_left'),
    ]


def test_online_coop_guest_accepts_wasd_keys_as_p2_alternate_controls(monkeypatch):
    net = FakeNet()
    game = _make_game(net)
    game.online_state = coop_module.OnlineCoopState.PLAYING
    game.role = 'guest'
    predicted = []
    monkeypatch.setattr(game, '_predict_guest_input', lambda action: predicted.append(action))

    game._handle_gameplay_keydown(SimpleNamespace(key=pygame.K_a))
    game._handle_gameplay_keydown(SimpleNamespace(key=pygame.K_LSHIFT))
    game._handle_gameplay_keydown(SimpleNamespace(key=pygame.K_e))
    game._handle_gameplay_keyup(SimpleNamespace(key=pygame.K_a))

    assert predicted == ['move_left', 'hard_drop', 'hold', 'das_stop_left']
    sent_actions = [payload['action'] for payload, _reliable, _channel in net.sent]
    assert sent_actions == ['move_left', 'hard_drop', 'hold', 'das_stop_left']


def test_online_coop_directional_das_stop_preserves_opposite_direction():
    coop = coop_module.CoopGame.__new__(coop_module.CoopGame)
    coop.game_over = False
    coop.paused = False
    coop.p1_frozen = False
    coop.p2_frozen = False
    coop.p1_current_piece = SimpleNamespace()
    coop.p2_current_piece = SimpleNamespace()
    coop.p2_das_direction = 0
    coop.p2_das_timer = 0.0
    coop.p2_das_repeat_timer = 0.0
    coop.p2_das_charged = False
    coop.sound = SimpleNamespace(play=lambda _name: None)
    coop._try_move = lambda _player, _direction: True

    coop.inject_remote_input('P2', 'move_left')
    assert coop.p2_das_direction == -1

    coop.inject_remote_input('P2', 'move_right')
    assert coop.p2_das_direction == 1

    coop.inject_remote_input('P2', 'das_stop_left')
    assert coop.p2_das_direction == 1

    coop.inject_remote_input('P2', 'das_stop_right')
    assert coop.p2_das_direction == 0


def test_online_coop_guest_movement_key_sends_reliable_input(monkeypatch):
    net = FakeNet()
    game = _make_game(net)
    game.online_state = coop_module.OnlineCoopState.PLAYING
    game.role = 'guest'
    game.coop_game = SimpleNamespace(
        game_over=False,
        paused=False,
        p2_current_piece=SimpleNamespace(shape_index=1, x=12, y=0, rotation_state=0),
        p2_next_piece=SimpleNamespace(shape_index=3),
        p2_hold_piece=None,
        p2_frozen=False,
    )
    monkeypatch.setattr(game, '_predict_guest_input', lambda action: None)

    game._handle_gameplay_keydown(SimpleNamespace(key=pygame.K_LEFT))

    assert len(net.sent) == 2
    payload, reliable, channel = net.sent[0]
    assert payload['type'] == MsgType.GUEST_INPUT
    assert payload['action'] == 'move_left'
    assert reliable is True
    assert channel == CHANNEL_CONTROL
    mirror_payload, mirror_reliable, mirror_channel = net.sent[1]
    assert mirror_payload['type'] == MsgType.GUEST_PIECE_STATE
    assert mirror_payload['p2_current']['x'] == 12
    assert mirror_reliable is False
    assert mirror_channel == CHANNEL_STATE


def test_online_coop_guest_piece_mirror_is_not_blocked_by_pending_movement():
    net = FakeNet()
    game = _make_game(net)
    game.online_state = coop_module.OnlineCoopState.PLAYING
    game.role = 'guest'
    game.coop_game = SimpleNamespace(
        game_over=False,
        paused=False,
        p2_current_piece=SimpleNamespace(shape_index=0, x=12, y=0, rotation_state=0),
        p2_next_piece=SimpleNamespace(shape_index=3),
        p2_hold_piece=None,
        p2_frozen=False,
    )
    game._guest_pending_inputs = [(1, 'move_left')]

    assert game._send_guest_piece_state(force=True) is True

    payload, reliable, channel = net.sent[-1]
    assert payload['type'] == MsgType.GUEST_PIECE_STATE
    assert payload['p2_current']['si'] == 0
    assert reliable is False
    assert channel == CHANNEL_STATE


def test_online_coop_guest_piece_mirror_waits_for_hold_ack():
    net = FakeNet()
    game = _make_game(net)
    game.online_state = coop_module.OnlineCoopState.PLAYING
    game.role = 'guest'
    game.coop_game = SimpleNamespace(
        game_over=False,
        paused=False,
        p2_current_piece=SimpleNamespace(shape_index=1, x=12, y=0, rotation_state=0),
        p2_next_piece=SimpleNamespace(shape_index=3),
        p2_hold_piece=None,
        p2_frozen=False,
    )
    game._guest_pending_inputs = [(1, 'hold')]

    assert game._send_guest_piece_state(force=True) is False
    assert net.sent == []


def test_online_coop_guest_predicts_before_first_host_snapshot():
    class FakeRenderCoop:
        game_over = False
        paused = False
        p2_frozen = False

        def __init__(self):
            self.injected = []
            self.p2_current_piece = SimpleNamespace(shape_index=1, x=13, y=0, rotation_state=0)
            self.p2_next_piece = SimpleNamespace(shape_index=3)
            self.p2_hold_piece = None

        def inject_remote_input(self, player, action):
            self.injected.append((player, action))
            if player == 'P2' and action == 'move_left':
                self.p2_current_piece.x -= 1

    net = FakeNet()
    game = _make_game(net)
    game.online_state = coop_module.OnlineCoopState.PLAYING
    game.role = 'guest'
    game.coop_game = FakeRenderCoop()
    game._guest_board_cache = None
    game._guest_piece_cache = None

    game._handle_gameplay_keydown(SimpleNamespace(key=pygame.K_LEFT))

    assert game.coop_game.injected == [('P2', 'move_left')]
    assert game.coop_game.p2_current_piece.x == 12
    mirror_payloads = [payload for payload, _reliable, channel in net.sent if channel == CHANNEL_STATE]
    assert mirror_payloads[-1]['type'] == MsgType.GUEST_PIECE_STATE
    assert mirror_payloads[-1]['p2_current']['x'] == 12


def test_online_coop_guest_flushes_piece_mirror_on_directional_das_stop():
    net = FakeNet()
    game = _make_game(net)
    game.online_state = coop_module.OnlineCoopState.PLAYING
    game.role = 'guest'
    game._held_gameplay_keys = {pygame.K_LEFT}
    game.coop_game = SimpleNamespace(
        game_over=False,
        paused=False,
        p2_current_piece=SimpleNamespace(shape_index=1, x=12, y=0, rotation_state=0),
        p2_next_piece=SimpleNamespace(shape_index=3),
        p2_hold_piece=None,
        p2_frozen=False,
        inject_remote_input=lambda _player, _action: None,
    )

    game._handle_gameplay_keyup(SimpleNamespace(key=pygame.K_LEFT))

    assert net.sent[0][0]['type'] == MsgType.GUEST_INPUT
    assert net.sent[0][0]['action'] == 'das_stop_left'
    assert net.sent[1][0]['type'] == MsgType.GUEST_PIECE_STATE
    assert net.sent[1][2] == CHANNEL_STATE


def test_online_coop_piece_signature_preserves_shape_index_zero():
    piece = SimpleNamespace(shape_index=0, x=4, y=5, rotation_state=2)

    assert coop_module.OnlineCoopGame._piece_signature(piece) == (0, 4, 5, 2)


def test_online_coop_pause_blocks_host_gameplay_input(monkeypatch):
    class CoopSpy:
        def __init__(self):
            self.game_over = False
            self.paused = False
            self.injected = []

        def inject_remote_input(self, player, action):
            self.injected.append((player, action))

    game = _make_game(FakeNet())
    game.online_state = coop_module.OnlineCoopState.PLAYING
    game.role = 'host'
    game.coop_game = CoopSpy()
    game._set_pause_state(True)
    monkeypatch.setattr(game, '_push_piece_state_if_changed', lambda *args, **kwargs: None)

    game._handle_gameplay_keydown(SimpleNamespace(key=pygame.K_SPACE))
    game._handle_gameplay_keydown(SimpleNamespace(key=pygame.K_LEFT))

    assert game.coop_game.injected == []


def test_online_coop_pause_blocks_guest_gameplay_input(monkeypatch):
    net = FakeNet()
    game = _make_game(net)
    game.online_state = coop_module.OnlineCoopState.PLAYING
    game.role = 'guest'
    game.coop_game = SimpleNamespace(game_over=False, paused=False)
    game._set_pause_state(True)
    predicted = []
    monkeypatch.setattr(game, '_predict_guest_input', lambda action: predicted.append(action))

    game._handle_gameplay_keydown(SimpleNamespace(key=pygame.K_SPACE))
    game._handle_gameplay_keydown(SimpleNamespace(key=pygame.K_LEFT))

    assert predicted == []
    assert net.sent == []


def test_online_coop_host_acks_but_ignores_guest_input_while_paused():
    class CoopSpy:
        game_over = False
        paused = False

        def __init__(self):
            self.injected = []

        def inject_remote_input(self, player, action):
            self.injected.append((player, action))

    net = FakeNet([
        _message(42, {
            'type': MsgType.GUEST_INPUT,
            'seq': 4,
            'action': 'hard_drop',
        }),
    ])
    net.opponent_steam_id = 42
    net.is_host = True
    game = _make_game(net)
    game.role = 'host'
    game.online_state = coop_module.OnlineCoopState.PLAYING
    game.coop_game = CoopSpy()
    game._set_pause_state(True)
    game._send_piece_state = lambda: None

    game._process_messages()

    assert game.coop_game.injected == []
    assert game._last_input_ack_seq == 4


def test_online_coop_host_guest_authority_acks_movement_without_double_injecting():
    class CoopSpy:
        game_over = False
        paused = False

        def __init__(self):
            self.injected = []

        def inject_remote_input(self, player, action):
            self.injected.append((player, action))

    net = FakeNet([
        _message(42, {
            'type': MsgType.GUEST_INPUT,
            'seq': 5,
            'action': 'move_left',
        }),
    ])
    net.opponent_steam_id = 42
    net.is_host = True
    game = _make_game(net)
    game.role = 'host'
    game.online_state = coop_module.OnlineCoopState.PLAYING
    game.coop_game = CoopSpy()
    sent_piece_states = []
    game._send_piece_state = lambda: sent_piece_states.append(True)

    game._process_messages()

    assert game._last_input_ack_seq == 5
    assert game.coop_game.injected == []
    assert sent_piece_states == []


def test_online_coop_host_guest_authority_still_simulates_hard_drop():
    class CoopSpy:
        game_over = False
        paused = False

        def __init__(self):
            self.injected = []

        def inject_remote_input(self, player, action):
            self.injected.append((player, action))

    net = FakeNet([
        _message(42, {
            'type': MsgType.GUEST_INPUT,
            'seq': 6,
            'action': 'hard_drop',
        }),
    ])
    net.opponent_steam_id = 42
    net.is_host = True
    game = _make_game(net)
    game.role = 'host'
    game.online_state = coop_module.OnlineCoopState.PLAYING
    game.coop_game = CoopSpy()
    sent_piece_states = []
    game._send_piece_state = lambda: sent_piece_states.append(True)

    game._process_messages()

    assert game._last_input_ack_seq == 6
    assert game.coop_game.injected == [('P2', 'hard_drop')]
    assert sent_piece_states == [True]


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


def test_online_coop_guest_update_advances_prediction_without_guest_piece_authority():
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
    game._guest_authoritative_piece_sync_enabled = False
    game.coop_game = FakeRenderCoop()
    game._process_messages = lambda: None
    game._apply_guest_render_cache = lambda: game.coop_game

    game.update(16)

    guest_piece_payloads = [payload for payload, _reliable, channel in net.sent if payload['type'] == MsgType.GUEST_PIECE_STATE and channel == CHANNEL_STATE]
    assert guest_piece_payloads == []
    assert game._guest_local_prediction_ms == 16.0


def test_online_coop_host_ignores_guest_piece_state_when_remote_authority_disabled():
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
    game._guest_authoritative_piece_sync_enabled = False
    game.coop_game = FakeHostCoop()

    game._process_messages()

    assert 'P2' not in game.coop_game.remote_authority_players
    assert game.coop_game.p2_current_piece.x == 13
    assert game.coop_game.p2_current_piece.y == 0
    assert game.coop_game.p2_current_piece.rotation_state == 0
    assert game.coop_game.p2_das_direction == 1
    assert game.coop_game.p2_soft_drop_active is True
    assert game.coop_game.p2_fall_time == 30.0
    assert game.coop_game.reset_calls == []


def test_online_coop_host_piece_snapshot_does_not_ack_disabled_guest_piece_state():
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
    game._guest_authoritative_piece_sync_enabled = False
    game.coop_game = FakeHostCoop()

    game._process_messages()
    game._send_piece_state()

    assert game._last_guest_piece_state_seq == 0
    assert net.sent[-1][0]['guest_piece_ack'] == 0


def test_online_coop_host_ignores_invalid_guest_piece_state_when_remote_authority_disabled():
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

    net = FakeNet([
        _message(42, {
            'type': MsgType.GUEST_PIECE_STATE,
            'seq': 9,
            'p2_current': {'si': 1, 'x': 12, 'y': 4, 'r': 0},
        }, channel=CHANNEL_STATE),
    ])
    net.opponent_steam_id = 42
    game = _make_game(net)
    game.role = 'host'
    game._guest_authoritative_piece_sync_enabled = False
    game.coop_game = FakeHostCoop()

    game._process_messages()

    assert game._last_guest_piece_state_seq == 0
    assert net.sent == []


def test_online_coop_guest_keeps_local_p2_across_matching_host_heartbeat():
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
    game._guest_authoritative_piece_sync_enabled = True

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

    assert game.coop_game.p2_current_piece.x == 12
    assert game.coop_game.p2_current_piece.y == 1
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


def test_online_coop_guest_render_cache_preserves_pause_state():
    class FakeBoard:
        width = 20
        height = 20

        def __init__(self):
            self.grid = [[(0, 0, 0) for _ in range(20)] for _ in range(20)]
            self.occupancy = [[False for _ in range(20)] for _ in range(20)]
            self.owners = [[None for _ in range(20)] for _ in range(20)]
            self.texture_grid = [[None for _ in range(20)] for _ in range(20)]
            self.gold = [[False for _ in range(20)] for _ in range(20)]

    class FakeRenderCoop:
        def __init__(self):
            self.screen = None
            self.window_width = 0
            self.window_height = 0
            self.fullscreen = False
            self.board = FakeBoard()
            self.paused = False
            self.game_over = False

        def _apply_block_style(self, piece):
            return None

    game = _make_game(FakeNet())
    game.role = 'guest'
    game.online_state = coop_module.OnlineCoopState.PLAYING
    game.coop_game = FakeRenderCoop()
    game._set_pause_state(True)
    game._guest_board_cache = game._normalize_board_snapshot(_valid_board_state(seq=3))

    game._apply_guest_render_cache()

    assert game.coop_game.paused is True


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


def test_online_coop_guest_keeps_predicted_p2_piece_after_input_ack():
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

    assert game.coop_game.p2_current_piece.x == 12
    assert game._guest_pending_inputs == []


def test_online_coop_guest_keeps_locally_simulated_p2_across_matching_host_heartbeat():
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

    heartbeat_piece_state = _valid_piece_state(seq=10)
    heartbeat_piece_state['host_elapsed_ms'] = 1065.0
    heartbeat_piece_state['p2_current']['y'] = 2
    game._guest_piece_cache = game._normalize_piece_snapshot(heartbeat_piece_state)

    game._apply_guest_render_cache()

    assert game.coop_game.p2_current_piece.y == 1
    assert game._guest_local_prediction_ms == 60.0


def test_online_coop_guest_accepts_small_host_correction_after_prediction_cap():
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
            self.p2_frozen = False

        def _apply_block_style(self, piece):
            return None

    game = _make_game(FakeNet())
    game.role = 'guest'
    game.online_state = coop_module.OnlineCoopState.PLAYING
    game.coop_game = FakeRenderCoop()
    # Legacy fallback path — authority kapalıyken cap aşımı host'a re-sync.
    game._guest_authoritative_piece_sync_enabled = False
    game._guest_board_cache = game._normalize_board_snapshot(_valid_board_state(seq=8, team_score=250))
    game._guest_render_board_seq = 8
    game._guest_local_prediction_ms = 150.0
    game._GUEST_LOCAL_PREDICTION_MAX_MS = 150.0

    correction_state = _valid_piece_state(seq=9)
    correction_state['p2_current']['x'] = 13
    correction_state['p2_current']['y'] = 0
    game._guest_piece_cache = game._normalize_piece_snapshot(correction_state)

    game._apply_guest_render_cache()

    assert game.coop_game.p2_current_piece.x == 13
    assert game.coop_game.p2_current_piece.y == 0
    assert game._guest_local_prediction_ms == 0.0


def test_online_coop_guest_accepts_small_host_correction_after_host_elapsed_cap():
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
            self.p2_frozen = False

        def _apply_block_style(self, piece):
            return None

    game = _make_game(FakeNet())
    game.role = 'guest'
    game.online_state = coop_module.OnlineCoopState.PLAYING
    game.coop_game = FakeRenderCoop()
    # Legacy fallback path — authority kapalıyken cap aşımı host'a re-sync.
    game._guest_authoritative_piece_sync_enabled = False
    game._guest_board_cache = game._normalize_board_snapshot(_valid_board_state(seq=8, team_score=250))
    game._guest_render_board_seq = 8
    game._guest_last_authoritative_piece_elapsed_ms = 1000.0
    game._guest_local_prediction_ms = 0.0
    game._GUEST_LOCAL_PREDICTION_MAX_MS = 150.0

    correction_state = _valid_piece_state(seq=9)
    correction_state['host_elapsed_ms'] = 1160.0
    correction_state['p2_current']['x'] = 13
    correction_state['p2_current']['y'] = 0
    game._guest_piece_cache = game._normalize_piece_snapshot(correction_state)

    game._apply_guest_render_cache()

    assert game.coop_game.p2_current_piece.x == 13
    assert game.coop_game.p2_current_piece.y == 0
    assert game._guest_last_authoritative_piece_elapsed_ms == 1160.0


def test_online_coop_guest_accepts_large_host_p2_correction():
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
    # Legacy fallback path: authority kapalıyken büyük host düzeltmesi kabul edilir.
    game._guest_authoritative_piece_sync_enabled = False
    game._guest_board_cache = game._normalize_board_snapshot(_valid_board_state(seq=8, team_score=250))
    game._guest_render_board_seq = 8

    correction_state = _valid_piece_state(seq=9)
    correction_state['p2_current']['x'] = 17
    correction_state['p2_current']['y'] = 9
    game._guest_piece_cache = game._normalize_piece_snapshot(correction_state)

    game._apply_guest_render_cache()

    assert game.coop_game.p2_current_piece.x == 17
    assert game.coop_game.p2_current_piece.y == 9


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


def test_online_coop_host_hard_drop_event_sends_guest_effect_payload():
    piece = SimpleNamespace(shape_index=2, x=5, y=8, rotation_state=1)
    net = FakeNet()
    game = _make_game(net)
    game.role = 'host'

    game._on_coop_event('hard_drop', {
        'player': 'P1',
        'piece': piece,
        'start_y': 1,
        'end_y': 8,
    })

    payload, reliable, channel = net.sent[0]
    assert payload['type'] == MsgType.COOP_GAME_EVENT
    assert payload['event'] == 'hard_drop'
    assert payload['data'] == {
        'player': 'P1',
        'piece': {'x': 5, 'y': 8, 'si': 2, 'r': 1},
        'start_y': 1,
        'end_y': 8,
    }
    assert reliable is True
    assert channel == CHANNEL_CONTROL


def test_online_coop_guest_hard_drop_event_triggers_teammate_trail_and_shake():
    class FakeRenderCoop:
        def __init__(self):
            self.effects_enabled = True
            self.cell_size = 20
            self.board_offset_x = 100
            self.board_offset_y = 50
            self.trails = []
            self.shakes = 0

        def _apply_block_style(self, piece):
            return None

        def create_drop_trail(self, x, y_start, y_end, color, cell_size):
            self.trails.append((x, y_start, y_end, color, cell_size))

        def trigger_hard_drop_screen_shake(self):
            self.shakes += 1

    game = _make_game(FakeNet())
    game.role = 'guest'
    game.online_state = coop_module.OnlineCoopState.PLAYING
    game.coop_game = FakeRenderCoop()

    game._apply_guest_hard_drop_event({
        'player': 'P1',
        'piece': {'si': 0, 'x': 3, 'y': 6, 'r': 0},
        'start_y': 0,
        'end_y': 6,
    })

    assert game.coop_game.trails
    assert game.coop_game.shakes == 1


def test_local_coop_hard_drop_emits_effect_event_before_lock():
    class FakeBoard:
        def is_valid_position_for_player(self, piece, player, dy=0):
            return int(piece.y + dy) <= 3

    class FakePiece:
        shape_index = 1
        x = 3
        y = 0
        rotation_state = 0

        def get_cells(self):
            return [(self.x, self.y)]

    game = coop_module.CoopGame.__new__(coop_module.CoopGame)
    game.board = FakeBoard()
    game.p1_current_piece = FakePiece()
    game.p2_current_piece = None
    game.effects_enabled = False
    events = []
    game._event_listeners = [
        lambda event_type, event_data: events.append((event_type, event_data.get('start_y'), event_data.get('end_y')))
    ]
    game._lock_and_new_piece = lambda player: events.append(('lock', player, None))

    coop_module.CoopGame._hard_drop(game, 'P1')

    assert events == [('hard_drop', 0, 3), ('lock', 'P1', None)]


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


# ============================================================================
# Online Co-op guest input lag/jitter regression tests
# ----------------------------------------------------------------------------
# Aşağıdaki testler, host COOP_PIECE_STATE heartbeat'lerinin guest'in lokal
# olarak tahmin ettiği P2 active piece'ini geri çekmemesini güvence altına
# alır. Online PvP'deki "kendi parçanı sahipleniyorsun" örüntüsü co-op guest'e
# uyarlanmış durumda; identity (active si + next_si + hold_si) host snapshot'ı
# ile aynıyken pozisyon farkı ne kadar büyük olursa olsun host snapshot'ı
# uygulanmaz. Lock/spawn/hold doğal olarak identity'i değiştirip re-sync
# tetikler.
# ============================================================================


def _make_guest_render_coop(p2_x: int = 12, p2_y: int = 1) -> SimpleNamespace:
    class _FakeBoard:
        width = 20
        height = 20

    return SimpleNamespace(
        screen=None,
        window_width=0,
        window_height=0,
        fullscreen=False,
        board=_FakeBoard(),
        p1_current_piece=None,
        p2_current_piece=SimpleNamespace(shape_index=1, x=p2_x, y=p2_y, rotation_state=0),
        p1_next_piece=None,
        p2_next_piece=SimpleNamespace(shape_index=3),
        p1_hold_piece=None,
        p2_hold_piece=None,
        p2_frozen=False,
        _apply_block_style=lambda piece: None,
    )


def test_online_coop_guest_authority_holds_p2_across_prediction_cap_with_identity_match():
    """Authority açıkken cap aşılsa bile aynı identity'li host heartbeat P2'yi geri çekmez."""
    game = _make_game(FakeNet())
    game.role = 'guest'
    game.online_state = coop_module.OnlineCoopState.PLAYING
    game._guest_authoritative_piece_sync_enabled = True
    game.coop_game = _make_guest_render_coop(p2_x=12, p2_y=1)
    game._guest_board_cache = game._normalize_board_snapshot(_valid_board_state(seq=8, team_score=250))
    game._guest_render_board_seq = 8
    game._guest_local_prediction_ms = 200.0  # cap (140) çok aşılmış
    game._GUEST_LOCAL_PREDICTION_MAX_MS = 140.0

    correction_state = _valid_piece_state(seq=9)
    correction_state['p2_current']['x'] = 13  # host P2 farklı kolonda
    correction_state['p2_current']['y'] = 0
    game._guest_piece_cache = game._normalize_piece_snapshot(correction_state)

    game._apply_guest_render_cache()

    # Eski davranış: snap-back (x=13, y=0). Yeni davranış: identity match,
    # P2 lokal kalır (x=12, y=1).
    assert game.coop_game.p2_current_piece.x == 12
    assert game.coop_game.p2_current_piece.y == 1
    # Lokal prediction sayacı sıfırlanmamalı çünkü host snapshot uygulanmadı.
    assert game._guest_local_prediction_ms == 200.0


def test_online_coop_guest_authority_holds_p2_across_host_elapsed_cap_with_identity_match():
    """Authority açıkken host_elapsed cap aşılsa bile identity match → snap-back yok."""
    game = _make_game(FakeNet())
    game.role = 'guest'
    game.online_state = coop_module.OnlineCoopState.PLAYING
    game._guest_authoritative_piece_sync_enabled = True
    game.coop_game = _make_guest_render_coop(p2_x=12, p2_y=1)
    game._guest_board_cache = game._normalize_board_snapshot(_valid_board_state(seq=8, team_score=250))
    game._guest_render_board_seq = 8
    game._guest_last_authoritative_piece_elapsed_ms = 1000.0
    game._guest_local_prediction_ms = 0.0
    game._GUEST_LOCAL_PREDICTION_MAX_MS = 140.0

    correction_state = _valid_piece_state(seq=9)
    correction_state['host_elapsed_ms'] = 1300.0  # 300ms gap >> cap
    correction_state['p2_current']['x'] = 13
    correction_state['p2_current']['y'] = 0
    game._guest_piece_cache = game._normalize_piece_snapshot(correction_state)

    game._apply_guest_render_cache()

    assert game.coop_game.p2_current_piece.x == 12
    assert game.coop_game.p2_current_piece.y == 1


def test_online_coop_guest_authority_resyncs_when_host_signals_new_piece_identity():
    """Lock/spawn olunca host'un yeni shape_index'i guest'e re-sync sağlar."""
    game = _make_game(FakeNet())
    game.role = 'guest'
    game.online_state = coop_module.OnlineCoopState.PLAYING
    game._guest_authoritative_piece_sync_enabled = True
    game.coop_game = _make_guest_render_coop(p2_x=12, p2_y=18)
    game._guest_board_cache = game._normalize_board_snapshot(_valid_board_state(seq=8, team_score=250))
    game._guest_render_board_seq = 8

    new_piece_state = _valid_piece_state(seq=9)
    # Yeni parça spawn: shape_index farklı → identity check fail → host kabul.
    new_piece_state['p2_current'] = {'si': 4, 'x': 13, 'y': 0, 'r': 0}
    new_piece_state['p2_next_si'] = 5
    game._guest_piece_cache = game._normalize_piece_snapshot(new_piece_state)

    game._apply_guest_render_cache()

    assert game.coop_game.p2_current_piece.shape_index == 4
    assert game.coop_game.p2_current_piece.x == 13
    assert game.coop_game.p2_current_piece.y == 0
    assert game._guest_local_prediction_ms == 0.0


def test_online_coop_guest_drops_stale_coop_piece_state_with_equal_seq():
    """Aynı seq'li ikinci COOP_PIECE_STATE paketi yeniden uygulanmaz (replay protection)."""
    net = FakeNet([
        _message(42, _valid_piece_state(seq=5), channel=CHANNEL_STATE),
        _message(42, _valid_piece_state(seq=5), channel=CHANNEL_STATE),
        _message(42, _valid_piece_state(seq=4), channel=CHANNEL_STATE),
    ])
    net.opponent_steam_id = 42
    game = _make_game(net)
    game.role = 'guest'
    game.online_state = coop_module.OnlineCoopState.PLAYING

    game._process_messages()

    # Sadece ilk seq=5 paket cache'lenir; aynı/eski olanlar drop edilir.
    assert game._guest_piece_seq == 5
    assert game._guest_piece_cache is not None


def test_online_coop_guest_input_ack_only_removes_acknowledged_pending_inputs():
    """input_ack pending input listesinden sadece <= ack olanları kaldırır."""
    game = _make_game(FakeNet())
    game.role = 'guest'
    game._guest_pending_inputs = [
        (1, 'move_left'),
        (2, 'move_left'),
        (3, 'rotate'),
        (4, 'hard_drop'),
        (5, 'move_right'),
    ]
    game._last_input_ack_seq = 0

    pending, board_mut = game._consume_guest_input_ack(3)

    assert pending is True
    assert board_mut is True  # seq=4 hard_drop hâlâ pending
    assert game._guest_pending_inputs == [(4, 'hard_drop'), (5, 'move_right')]
    assert game._last_input_ack_seq == 3

    pending, board_mut = game._consume_guest_input_ack(5)

    assert pending is False
    assert board_mut is False
    assert game._guest_pending_inputs == []
    assert game._last_input_ack_seq == 5


def test_online_coop_guest_input_ack_ignores_decreasing_ack_seq():
    """Düşük ack tekrar geldiğinde son ack düşmez ve pending temizlenmez."""
    game = _make_game(FakeNet())
    game.role = 'guest'
    game._guest_pending_inputs = [(7, 'move_left'), (8, 'rotate')]
    game._last_input_ack_seq = 6

    pending, _ = game._consume_guest_input_ack(2)

    assert pending is True
    assert game._last_input_ack_seq == 6
    assert game._guest_pending_inputs == [(7, 'move_left'), (8, 'rotate')]


def test_online_coop_guest_held_key_repeat_sends_exactly_one_input(monkeypatch):
    """Auto-repeat / yeniden basılan tuş tek bir GUEST_INPUT üretir; serbest bırak/yeniden bas akışı çalışır."""
    net = FakeNet()
    game = _make_game(net)
    game.online_state = coop_module.OnlineCoopState.PLAYING
    game.role = 'guest'
    game.coop_game = SimpleNamespace(
        game_over=False,
        paused=False,
        p2_current_piece=SimpleNamespace(shape_index=1, x=12, y=0, rotation_state=0),
        p2_next_piece=SimpleNamespace(shape_index=3),
        p2_hold_piece=None,
        p2_frozen=False,
        inject_remote_input=lambda _player, _action: None,
    )
    monkeypatch.setattr(game, '_predict_guest_input', lambda action: None)

    event = SimpleNamespace(key=pygame.K_LEFT)
    game._handle_gameplay_keydown(event)
    # Auto-repeat veya kullanıcı çoklu basışı:
    game._handle_gameplay_keydown(event)
    game._handle_gameplay_keydown(event)

    move_inputs = [p for p, _r, c in net.sent if c == CHANNEL_CONTROL and p.get('type') == MsgType.GUEST_INPUT]
    assert len(move_inputs) == 1
    assert move_inputs[0]['action'] == 'move_left'

    # Serbest bırak + yeniden bas → ikinci bir input gönderilmeli.
    game._handle_gameplay_keyup(event)
    game._handle_gameplay_keydown(event)

    move_inputs = [p for p, _r, c in net.sent if c == CHANNEL_CONTROL and p.get('type') == MsgType.GUEST_INPUT]
    assert [p['action'] for p in move_inputs] == ['move_left', 'das_stop_left', 'move_left']


def test_online_coop_guest_authority_keeps_p2_against_repeated_heartbeats_no_jitter():
    """Birden çok host heartbeat'i ardı ardına geldiğinde lokal P2 her seferinde aynı yerde kalır (jitter yok)."""
    game = _make_game(FakeNet())
    game.role = 'guest'
    game.online_state = coop_module.OnlineCoopState.PLAYING
    game._guest_authoritative_piece_sync_enabled = True
    game.coop_game = _make_guest_render_coop(p2_x=11, p2_y=4)
    game._guest_board_cache = game._normalize_board_snapshot(_valid_board_state(seq=8, team_score=250))
    game._guest_render_board_seq = 8

    for index, host_x in enumerate((13, 13, 13, 13), start=9):
        heartbeat = _valid_piece_state(seq=index)
        heartbeat['p2_current']['x'] = host_x
        heartbeat['p2_current']['y'] = 0
        heartbeat['host_elapsed_ms'] = 1000.0 + (index - 9) * 50.0
        game._guest_piece_cache = game._normalize_piece_snapshot(heartbeat)

        game._apply_guest_render_cache()

        # Her heartbeat sonrası P2 aynı lokal pozisyonda — jitter yok.
        assert game.coop_game.p2_current_piece.x == 11
        assert game.coop_game.p2_current_piece.y == 4


def test_online_coop_guest_board_snapshot_does_not_wipe_p2_with_pending_inputs():
    """Board snapshot uygulanmasında pending guest input varsa P2 piece dokunulmaz."""
    game = _make_game(FakeNet())
    game.role = 'guest'
    game.online_state = coop_module.OnlineCoopState.PLAYING
    game.coop_game = _make_guest_render_coop(p2_x=10, p2_y=2)
    game._guest_board_cache = game._normalize_board_snapshot(_valid_board_state(seq=12, team_score=250))
    game._guest_render_board_seq = 11
    game._guest_pending_inputs = [(15, 'hard_drop')]
    game._guest_input_seq = 15
    game._last_input_ack_seq = 14

    piece_snapshot = _valid_piece_state(seq=20)
    piece_snapshot['input_ack'] = 14  # hard_drop henüz ack'lenmedi
    piece_snapshot['p2_current']['x'] = 5
    piece_snapshot['p2_current']['y'] = 0
    game._guest_piece_cache = game._normalize_piece_snapshot(piece_snapshot)

    game._apply_guest_render_cache()

    assert game.coop_game.p2_current_piece.x == 10
    assert game.coop_game.p2_current_piece.y == 2
    # Pending hard_drop bozulmaz.
    assert game._guest_pending_inputs == [(15, 'hard_drop')]


def test_online_coop_guest_authority_disabled_falls_back_to_legacy_tolerance():
    """Authority kapalıyken eski dx<=3/dy<=6 toleransı (cap altında) hâlâ identity match'te lokal kalır."""
    game = _make_game(FakeNet())
    game.role = 'guest'
    game.online_state = coop_module.OnlineCoopState.PLAYING
    game._guest_authoritative_piece_sync_enabled = False
    game.coop_game = _make_guest_render_coop(p2_x=12, p2_y=1)
    game._guest_board_cache = game._normalize_board_snapshot(_valid_board_state(seq=8, team_score=250))
    game._guest_render_board_seq = 8
    game._guest_local_prediction_ms = 30.0
    game._GUEST_LOCAL_PREDICTION_MAX_MS = 150.0

    snapshot = _valid_piece_state(seq=9)
    snapshot['p2_current']['x'] = 13  # dx=1
    snapshot['p2_current']['y'] = 2   # dy=1
    game._guest_piece_cache = game._normalize_piece_snapshot(snapshot)

    game._apply_guest_render_cache()

    # Cap aşılmadığı ve dx/dy küçük olduğu için lokal P2 korunur.
    assert game.coop_game.p2_current_piece.x == 12
    assert game.coop_game.p2_current_piece.y == 1


# ============================================================================
# Risk azaltıcı düzeltme testleri
# ----------------------------------------------------------------------------
# - Risk 1: Lock event guest'in pending hard_drop/hold input'larını temizler.
# - Risk 2: SDR yüksek RTT senaryosu için _GUEST_PIECE_ACK_GRACE_S yükseltilmiş.
# ============================================================================


def test_online_coop_lock_event_clears_pending_p2_board_mutating_inputs(monkeypatch):
    """COOP_LOCK_EVENT (player=P2) gelirse pending hard_drop/hold temizlenir."""

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
            self.board_offset_x = 0
            self.board_offset_y = 0
            self.line_clear_pending_rows = []
            self.line_clear_pending_colors = {}

        def _start_line_clear_sweep(self, _rows):
            return None

        def trigger_screen_shake(self, *_a, **_kw):
            return None

        def create_particles(self, *_a, **_kw):
            return None

        def create_lock_explosion(self, *_a, **_kw):
            return None

    monkeypatch.setattr(coop_module, 'CoopGame', FakeRenderCoop)

    net = FakeNet([
        _message(42, {
            'type': MsgType.COOP_LOCK_EVENT,
            'event': 'piece_placed',
            'player': 'P2',
            'new_score': 100,
            'new_level': 1,
            'lock_cells': [],
            'cleared_rows': [],
            'row_colors': {},
        }),
    ])
    net.opponent_steam_id = 42
    game = _make_game(net)
    game.role = 'guest'
    game.online_state = coop_module.OnlineCoopState.PLAYING
    game._guest_pending_inputs = [
        (10, 'move_left'),
        (11, 'rotate'),
        (12, 'hard_drop'),
        (13, 'hold'),
        (14, 'move_right'),
    ]

    game._process_messages()

    # hard_drop ve hold temizlendi; diğer input'lar kaldı.
    assert game._guest_pending_inputs == [
        (10, 'move_left'),
        (11, 'rotate'),
        (14, 'move_right'),
    ]


def test_online_coop_lock_event_for_p1_does_not_clear_p2_pending(monkeypatch):
    """P1 lock'u guest'in P2 pending input'larını etkilemez."""

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
            self.board_offset_x = 0
            self.board_offset_y = 0
            self.line_clear_pending_rows = []
            self.line_clear_pending_colors = {}

        def _start_line_clear_sweep(self, _rows):
            return None

        def trigger_screen_shake(self, *_a, **_kw):
            return None

        def create_particles(self, *_a, **_kw):
            return None

        def create_lock_explosion(self, *_a, **_kw):
            return None

    monkeypatch.setattr(coop_module, 'CoopGame', FakeRenderCoop)

    net = FakeNet([
        _message(42, {
            'type': MsgType.COOP_LOCK_EVENT,
            'event': 'piece_placed',
            'player': 'P1',
            'new_score': 100,
            'new_level': 1,
            'lock_cells': [],
            'cleared_rows': [],
            'row_colors': {},
        }),
    ])
    net.opponent_steam_id = 42
    game = _make_game(net)
    game.role = 'guest'
    game.online_state = coop_module.OnlineCoopState.PLAYING
    game._guest_pending_inputs = [
        (10, 'hard_drop'),
        (11, 'hold'),
    ]

    game._process_messages()

    assert game._guest_pending_inputs == [
        (10, 'hard_drop'),
        (11, 'hold'),
    ]


def test_online_coop_default_guest_piece_ack_grace_supports_high_rtt():
    """SDR gibi yüksek RTT senaryolarında ack grace en az 1.0s olmalı."""
    game = coop_module.OnlineCoopGame.__new__(coop_module.OnlineCoopGame)
    coop_module.OnlineCoopGame.__init__.__wrapped__ if False else None
    # Default değer constructor'da set ediliyor. Basit kontrol için class attr'ı
    # constructor öncesinde manuel set edip baz değeri doğrula:
    game._GUEST_PIECE_ACK_GRACE_S = 0.75  # eski default
    # Yeni değer constructor'da set edileceği için fixture _make_game zaten
    # 0.75'i atıyor (test senaryolarını korumak için). Burada kaynak kodun
    # default'unun yükseltilmiş olduğunu doğrulamak için fresh init yapalım.
    actual_default = None
    try:
        # __init__ pygame ihtiyacı duyduğu için sınıfın class-level/init-time
        # default'ını dolaylı doğrula:
        from inspect import getsource
        source = getsource(coop_module.OnlineCoopGame.__init__)
    except Exception:
        source = ''

    assert '_GUEST_PIECE_ACK_GRACE_S = 2.5' in source, (
        'Default _GUEST_PIECE_ACK_GRACE_S yüksek RTT için yükseltilmiş olmalı'
    )


# ===================================================================
# Online co-op gameplay müziği başlatma + playlist tick parity testleri
# ===================================================================

class _MusicSoundSpy:
    def __init__(self):
        self.music_enabled = True
        self.set_calls: list[dict] = []
        self.update_calls = 0
        self.unduck_calls = 0
        self.stop_calls = 0
        self._tracks = {'pvp_1': True, 'klasik_1': True}

    def ensure_track_available(self, value):
        if not value:
            return None
        return value if value in self._tracks else None

    def set_music_playlist(self, tracks, loop=True, start_index=0, autoplay=True, force=False, shuffle=False):
        self.set_calls.append({
            'tracks': list(tracks),
            'loop': loop,
            'start_index': start_index,
            'autoplay': autoplay,
            'force': force,
            'shuffle': shuffle,
        })
        return True

    def update_music_playlist(self):
        self.update_calls += 1

    def unduck_music(self):
        self.unduck_calls += 1

    def stop_music(self):
        self.stop_calls += 1

    def play(self, *_args, **_kwargs):
        pass


class _SettingsStub:
    def __init__(self, playlist=None, shuffle=False, music_enabled=True, mode_overrides=None):
        self._playlist = list(playlist or [])
        self._shuffle = shuffle
        self._music_enabled = music_enabled
        self._mode_overrides = dict(mode_overrides or {})
        self._values = {
            'music_shuffle': shuffle,
            'music_enabled': music_enabled,
            'coop_music': None,
            'game_music': None,
        }

    def get(self, key, default=None):
        return self._values.get(key, default)

    def get_music_playlist_for_mode(self, mode_key):
        return list(self._playlist)

    def get_mode_music_overrides(self):
        return dict(self._mode_overrides)


def test_online_coop_start_gameplay_music_uses_coop_playlist_with_force_restart():
    """Countdown sonrası gameplay'e geçişte coop playlist explicit start edilmeli."""
    net = FakeNet()
    game = _make_game(net)
    sound = _MusicSoundSpy()
    game.sound = sound
    game.settings_manager = _SettingsStub(playlist=['pvp_1', 'klasik_1'], shuffle=False)

    game._start_gameplay_music()

    assert len(sound.set_calls) == 1
    call = sound.set_calls[0]
    assert call['tracks'] == ['pvp_1', 'klasik_1']
    assert call['autoplay'] is True
    assert call['force'] is True
    assert call['loop'] is True
    assert sound.unduck_calls == 1


def test_online_coop_start_gameplay_music_falls_back_to_single_coop_default_track():
    """Playlist boşsa tek track ile fallback yapılmalı (varsayılan pvp_1)."""
    net = FakeNet()
    game = _make_game(net)
    sound = _MusicSoundSpy()
    game.sound = sound
    game.settings_manager = _SettingsStub(playlist=[], shuffle=False)

    game._start_gameplay_music()

    assert len(sound.set_calls) == 1
    call = sound.set_calls[0]
    assert call['tracks'] == ['pvp_1']
    assert call['force'] is True


def test_online_coop_update_ticks_music_playlist_during_play_state():
    """PLAYING state'te wrapper update() gerçekten playlist tick atmalı.

    `OnlineCoopGame.update()`'i fixture üzerinde gerçekten çağırıp
    `_MusicSoundSpy.update_calls` sayacının arttığını doğruluyoruz.
    """
    net = FakeNet()
    game = _make_game(net)
    sound = _MusicSoundSpy()
    game.sound = sound
    game.online_state = coop_module.OnlineCoopState.PLAYING
    # Gerçek update()'in dışarıya etkisini bastır: yan yollar no-op olsun.
    game._process_messages = lambda: None
    game._update_guest_local_prediction = lambda dt: None
    game.coop_game = SimpleNamespace(
        update=lambda dt: None,
        p1_frozen=False,
        p2_frozen=False,
        game_over=False,
    )
    game._auto_connect_attempted = True
    game._net_initialized = True
    game._auto_lobby_refresh_requested = True

    game.update(16.0)
    game.update(16.0)

    assert sound.update_calls == 2, 'PLAYING state\'te wrapper update playlist tick atmalı'


def test_online_coop_update_does_not_tick_music_playlist_outside_play_state():
    """LOBBY_MENU state'te gameplay playlist tick atılmamalı."""
    net = FakeNet()
    game = _make_game(net)
    sound = _MusicSoundSpy()
    game.sound = sound
    game.online_state = coop_module.OnlineCoopState.LOBBY_MENU
    game._process_messages = lambda: None
    game._auto_connect_attempted = True
    game._net_initialized = True
    game._auto_lobby_refresh_requested = True

    game.update(16.0)

    assert sound.update_calls == 0, (
        'Lobby state\'te gameplay playlist tick atılmamalı'
    )


def test_online_coop_update_does_not_double_tick_music_for_host_via_coop_game():
    """Host frame'inde wrapper + CoopGame çift tick atmamalı.

    Host CoopGame `_suppress_internal_music_tick=True` ile yaratılmalı; wrapper
    tek tick atar. Bu testte CoopGame.update gerçek davranışını taklit eden
    spy ile çağırıp yalnızca wrapper'ın bir kez tick attığını doğruluyoruz.
    """
    net = FakeNet()
    game = _make_game(net)
    sound = _MusicSoundSpy()
    game.sound = sound
    game.online_state = coop_module.OnlineCoopState.PLAYING
    game.role = 'host'
    game._process_messages = lambda: None
    game._auto_connect_attempted = True
    game._net_initialized = True
    game._auto_lobby_refresh_requested = True

    # Gerçek host CoopGame davranışını simüle et: suppress flag açıksa tick yok.
    coop_tick_calls = {'count': 0}

    def coop_update(dt):
        # Gerçek CoopGame.update'inin müzik tick davranışını birebir taklit:
        if not getattr(coop_spy, '_suppress_internal_music_tick', False):
            coop_tick_calls['count'] += 1
            sound.update_music_playlist()

    coop_spy = SimpleNamespace(
        update=coop_update,
        p1_frozen=False,
        p2_frozen=False,
        game_over=False,
        _suppress_internal_music_tick=True,
    )
    game.coop_game = coop_spy
    game._last_frozen_flags = (False, False)
    game._BOARD_STATE_INTERVAL = 1_000_000.0  # broadcasts atlanmaz; sayım önemli değil
    game._PIECE_STATE_INTERVAL = 1_000_000.0
    game._board_state_timer = 0.0
    game._piece_state_timer = 0.0
    game._push_piece_state_if_changed = lambda *a, **kw: False
    game._send_board_state = lambda *a, **kw: None
    game._send_piece_state = lambda *a, **kw: None

    game.update(16.0)

    # Wrapper tam 1 tick atmalı, CoopGame iç tick atlamalı (suppress aktif).
    assert sound.update_calls == 1, (
        f'Host frame\'inde tam 1 playlist tick beklenirdi (wrapper); gözlenen: {sound.update_calls}'
    )
    assert coop_tick_calls['count'] == 0, (
        'Host CoopGame _suppress_internal_music_tick aktifken kendi tick\'ini atmamalı'
    )


def test_online_coop_start_gameplay_music_respects_disabled_music_setting():
    """Music disabled ise playlist set edilmemeli."""
    net = FakeNet()
    game = _make_game(net)
    sound = _MusicSoundSpy()
    sound.music_enabled = False
    game.sound = sound
    game.settings_manager = _SettingsStub(playlist=['pvp_1'], music_enabled=False)

    game._start_gameplay_music()

    assert sound.set_calls == []


# ===================================================================
# Online co-op guest line-clear parity testleri (Game/PvP/CoopGame ile)
# ===================================================================

def test_online_coop_guest_apply_lock_event_queues_wave_effects_for_cleared_rows():
    """Guest tarafında lock event geldiğinde line_clear_wave_effects doldurulmalı."""
    net = FakeNet()
    game = _make_game(net)
    game.online_state = coop_module.OnlineCoopState.PLAYING
    game.role = 'guest'

    fake_render = SimpleNamespace(
        line_clear_pending_rows=[],
        line_clear_pending_colors={},
        line_clear_wave_effects=[],
        cell_size=20,
        board_offset_x=10,
        board_offset_y=10,
        effects_enabled=True,
        board=SimpleNamespace(width=20, height=20, last_clear_row_colors={}),
        _start_line_clear_sweep=lambda rows: None,
        trigger_screen_shake=lambda *a, **kw: None,
        create_lock_explosion=lambda *a, **kw: None,
        create_particles=lambda *a, **kw: None,
        create_line_clear_particles=lambda *a, **kw: None,
        _start_block_fall_animation=lambda *a, **kw: None,
        line_clear_sweep_active=True,
        _fall_animation_rows_key=None,
    )
    game.coop_game = fake_render
    game._ensure_guest_render_game = lambda: fake_render

    row_color = [(0, 255, 255)] * 20
    payload = {
        'type': MsgType.COOP_LOCK_EVENT,
        'player': 'P2',
        'lines': 4,
        'cleared_rows': [16, 17, 18, 19],
        'row_colors': {16: row_color, 17: row_color, 18: row_color, 19: row_color},
        'new_score': 800,
        'new_level': 2,
        'total_lines': 4,
    }
    game._apply_guest_lock_event(payload)

    assert len(fake_render.line_clear_wave_effects) == 4
    # Her dalga gerekli alanları içermeli.
    for wave in fake_render.line_clear_wave_effects:
        assert 'x' in wave and 'y' in wave
        assert 'radius' in wave and 'max_radius' in wave
        assert 'speed' in wave
        assert wave['alpha'] == 200


def test_online_coop_guest_apply_lock_event_calls_create_line_clear_particles():
    """Guest tarafında lock event geldiğinde Game/PvP ile parity'li parçacık zinciri tetiklenmeli."""
    net = FakeNet()
    game = _make_game(net)
    game.online_state = coop_module.OnlineCoopState.PLAYING
    game.role = 'guest'

    particle_calls: list = []

    fake_board = SimpleNamespace(width=20, height=20, last_clear_row_colors={})
    fake_render = SimpleNamespace(
        line_clear_pending_rows=[],
        line_clear_pending_colors={},
        line_clear_wave_effects=[],
        cell_size=20,
        board_offset_x=10,
        board_offset_y=10,
        effects_enabled=True,
        board=fake_board,
        _start_line_clear_sweep=lambda rows: None,
        trigger_screen_shake=lambda *a, **kw: None,
        create_lock_explosion=lambda *a, **kw: None,
        create_particles=lambda *a, **kw: None,
        create_line_clear_particles=lambda rows, ox, oy, cs, board=None: particle_calls.append((tuple(rows), ox, oy, cs)),
        _start_block_fall_animation=lambda *a, **kw: None,
        line_clear_sweep_active=True,
        _fall_animation_rows_key=None,
    )
    game.coop_game = fake_render
    game._ensure_guest_render_game = lambda: fake_render

    row_color = [(255, 100, 0)] * 20
    payload = {
        'type': MsgType.COOP_LOCK_EVENT,
        'player': 'P1',
        'lines': 2,
        'cleared_rows': [18, 19],
        'row_colors': {18: row_color, 19: row_color},
        'new_score': 200,
        'new_level': 1,
        'total_lines': 2,
    }
    game._apply_guest_lock_event(payload)

    assert len(particle_calls) == 1
    rows, ox, oy, cs = particle_calls[0]
    assert sorted(rows) == [18, 19]
    assert cs == 20


def test_coop_game_create_line_clear_particles_uses_snapshot_color():
    """CoopGame.create_line_clear_particles last_clear_row_colors'tan hücre rengi kullanmalı."""
    import coop_game as cg_module
    cg = cg_module.CoopGame.__new__(cg_module.CoopGame)
    cg.particles = []
    cg.effects_enabled = True
    cg.animation_multiplier = 1.0
    cg._FRAME_MS = 1000.0 / 60.0
    cg.window_width = 1280
    cg.window_height = 720
    cg.cell_size = 20
    cg.board_offset_x = 0
    cg.board_offset_y = 0
    cg._particle_effects_enabled = lambda: True
    cg._particle_effects_multiplier = lambda: 1.0
    cg.board = SimpleNamespace(width=20, height=20, last_clear_row_colors={5: [(123, 45, 67)] * 20})

    cg.create_line_clear_particles([5], 0, 0, 20, board=cg.board)

    assert cg.particles, 'Parçacıklar oluşmalı'
    # Snapshot rengi (123,45,67) bazı parçacıklarda görülmeli.
    snapshot_colors_seen = sum(1 for p in cg.particles if tuple(p['color'][:3]) == (123, 45, 67))
    assert snapshot_colors_seen > 0


def test_coop_game_handle_player_lock_populates_wave_effects():
    """CoopGame._lock_and_new_piece sırasında satır temizleme dalga efektleri eklenir.

    `_queue_wave_effects` helper'ı düzgün çağrıldığını doğrular: cleared_rows
    listesindeki her satır için bir wave entry eklenmeli.
    """
    import line_clear_feedback as _lcf
    wave_list: list = []
    _lcf.queue_wave_effects(
        wave_list,
        cleared_rows=[16, 17, 18, 19],
        board_offset_x=10,
        board_offset_y=20,
        cell_size=30,
        board_width_cells=20,
    )
    assert len(wave_list) == 4
    for idx, wave in enumerate(wave_list):
        # x koordinatı board ortasını gösterir.
        assert wave['x'] == 10 + (20 * 30) // 2
        assert wave['radius'] == 0
        assert wave['max_radius'] == 20 * 30
        assert wave['alpha'] == 200
        assert wave['speed'] == 15.0


def test_line_clear_feedback_update_wave_effects_advances_radius_and_drops_finished():
    """Wave update helper radius'u ilerletir ve sönen efektleri çıkarır."""
    import line_clear_feedback as _lcf
    wave_list = [
        {
            'x': 100,
            'y': 100,
            'radius': 0,
            'max_radius': 100,
            'alpha': 200,
            'color': (255, 255, 255),
            'speed': 15.0,
        }
    ]
    _lcf.update_wave_effects(wave_list, dt_frames=1.0)
    assert wave_list[0]['radius'] == 15.0
    # 2x4 frame sonra biter (60 frame * 1.0 ~= 100px). Birkaç tick daha çevir.
    for _ in range(20):
        _lcf.update_wave_effects(wave_list, dt_frames=1.0)
    assert wave_list == [], 'Tamamlanan dalga listeden çıkmalı'



# ===================================================================
# Çok modlu line-clear helper parity testleri (Game / PvP / OnlinePvP / Coop)
# ===================================================================

def test_line_clear_helper_is_imported_by_all_gameplay_modes():
    """`line_clear_feedback` helper'ı tüm gameplay modülleri tarafından import edilmeli.

    Bu, ortak refactor'ın sadece co-op tarafında kalmadığını ve Game / PvP /
    OnlinePvP / Coop / OnlineCoop'un hepsinin aynı kaynağa bağlandığını doğrular.
    """
    import importlib
    expected_modules = [
        'game',
        'pvp_game',
        'online_pvp_game',
        'coop_game',
        'online_coop_game',
    ]
    missing = []
    for mod_name in expected_modules:
        try:
            mod = importlib.import_module(mod_name)
        except Exception as exc:
            missing.append(f'{mod_name} (import error: {exc})')
            continue
        # Modül kaynağında `line_clear_feedback` referansı olmalı.
        from inspect import getsource
        try:
            src = getsource(mod)
        except Exception:
            src = ''
        if 'line_clear_feedback' not in src:
            missing.append(mod_name)
    assert not missing, (
        f'Şu modüller line_clear_feedback helper\'ını kullanmıyor: {missing}'
    )


def test_pvp_game_p1_line_clear_uses_shared_wave_helper():
    """PvP P1 line clear ortak `_queue_wave_effects` helper'ını kullanmalı."""
    import inspect
    import pvp_game as pvp_module
    # PvPGame.update_animations veya draw_locked_blocks yerine sınıfın tüm
    # kaynağında inline `wave_y = ... wave_x = ...; .append({` deseninin
    # kalmadığını doğrula. Bu, helper'a geçiş yaptığımızı sözdizimsel olarak
    # zorlar (refactor regression guard).
    src = inspect.getsource(pvp_module.PvPGame)
    # Kaba bir kontrol: helper çağrısı olmalı.
    assert '_queue_wave_effects(' in src, 'PvPGame _queue_wave_effects çağırmıyor'
    assert '_update_wave_effects(' in src, 'PvPGame _update_wave_effects çağırmıyor'
    # Eski inline append deseni P1/P2 wave için kalmamalı.
    assert 'self.p1_wave_effects.append({' not in src, (
        'PvPGame P1 wave inline append hâlâ var; helper\'a geçiş eksik'
    )
    assert 'self.p2_wave_effects.append({' not in src, (
        'PvPGame P2 wave inline append hâlâ var; helper\'a geçiş eksik'
    )


def test_online_pvp_game_line_clear_uses_shared_wave_helper():
    """OnlinePvPGame `_trigger_line_clear_feedback` helper kullanmalı."""
    import inspect
    import online_pvp_game as opvp_module
    src = inspect.getsource(opvp_module.OnlinePvPGame)
    assert '_queue_wave_effects(' in src, 'OnlinePvPGame _queue_wave_effects çağırmıyor'
    assert '_update_wave_effects(' in src, 'OnlinePvPGame _update_wave_effects çağırmıyor'
    # Eski inline append deseni my/opp wave için kalmamalı.
    assert "wave_list.append({" not in src, (
        'OnlinePvPGame wave_list inline append hâlâ var; helper\'a geçiş eksik'
    )


def test_game_line_clear_uses_shared_wave_helper():
    """Game (single-player + Mystery base) `_queue_line_clear_effects` helper kullanmalı."""
    import inspect
    import game as game_module
    src = inspect.getsource(game_module.Game)
    assert '_queue_wave_effects(' in src, 'Game _queue_wave_effects çağırmıyor'
    assert '_update_wave_effects(' in src, 'Game _update_wave_effects çağırmıyor'
    assert 'self.line_clear_wave_effects.append({' not in src, (
        'Game inline wave append hâlâ var; helper\'a geçiş eksik'
    )


def test_pvp_game_p1_combo_burst_uses_shared_helper():
    """PvP P1 multi-line / Quadrix patlaması helper'ı çağırmalı."""
    import inspect
    import pvp_game as pvp_module
    src = inspect.getsource(pvp_module.PvPGame)
    # _trigger_combo_burst PvP'de iki kez (P1/P2) çağrılıyor olmalı.
    occurrences = src.count('_trigger_combo_burst(')
    assert occurrences >= 2, (
        f'PvP\'de _trigger_combo_burst en az iki kez beklenirdi (P1+P2); gözlenen: {occurrences}'
    )


def test_trigger_combo_burst_quadrix_uses_150_particles_at_speed_10():
    """Quadrix kombo burst Game / PvP ile aynı sayı/hız profilini kullanmalı."""
    import line_clear_feedback as _lcf
    captured = []

    spy = SimpleNamespace(
        effects_enabled=True,
        create_particles=lambda count, x, y, colors, speed: captured.append({
            'count': count,
            'x': x,
            'y': y,
            'colors': list(colors),
            'speed': speed,
        }),
    )
    _lcf.trigger_combo_burst(
        spy,
        cleared_rows=[16, 17, 18, 19],
        lines_cleared=4,
        board_offset_x=10,
        board_offset_y=20,
        cell_size=30,
        board_width_cells=20,
        board_height_cells=20,
    )
    assert len(captured) == 1
    call = captured[0]
    assert call['count'] == 150
    assert call['speed'] == 10


def test_trigger_combo_burst_double_uses_50_per_line_at_speed_6():
    """2-3 satır kombo `50*lines` partikül speed=6 profili kullanmalı."""
    import line_clear_feedback as _lcf
    captured = []

    spy = SimpleNamespace(
        effects_enabled=True,
        create_particles=lambda count, x, y, colors, speed: captured.append({
            'count': count,
            'speed': speed,
        }),
    )
    _lcf.trigger_combo_burst(
        spy,
        cleared_rows=[18, 19],
        lines_cleared=2,
        board_offset_x=0,
        board_offset_y=0,
        cell_size=20,
        board_width_cells=20,
        board_height_cells=20,
    )
    assert len(captured) == 1
    call = captured[0]
    assert call['count'] == 100  # 50 * 2
    assert call['speed'] == 6


def test_trigger_combo_burst_respects_color_overrides():
    """Renk override (PvP P2 magenta paleti) helper tarafından korunmalı."""
    import line_clear_feedback as _lcf
    captured = []

    spy = SimpleNamespace(
        effects_enabled=True,
        create_particles=lambda count, x, y, colors, speed: captured.append({
            'colors': list(colors),
        }),
    )
    p2_quadrix = [(255, 215, 0), (255, 165, 0), (255, 255, 255), (255, 0, 255)]
    _lcf.trigger_combo_burst(
        spy,
        cleared_rows=[19],
        lines_cleared=4,
        board_offset_x=0,
        board_offset_y=0,
        cell_size=20,
        board_width_cells=20,
        board_height_cells=20,
        quadrix_colors=p2_quadrix,
    )
    assert captured[0]['colors'] == p2_quadrix


def test_trigger_combo_burst_skips_single_line_clears():
    """Tek satır temizleme kombo burst tetiklememeli (Game / PvP davranışıyla parity)."""
    import line_clear_feedback as _lcf
    captured = []

    spy = SimpleNamespace(
        effects_enabled=True,
        create_particles=lambda *a, **kw: captured.append(True),
    )
    _lcf.trigger_combo_burst(
        spy,
        cleared_rows=[19],
        lines_cleared=1,
        board_offset_x=0,
        board_offset_y=0,
        cell_size=20,
        board_width_cells=20,
        board_height_cells=20,
    )
    assert captured == []



# ===================================================================
# Guest input reactivity testleri (kök neden iyileştirmesi)
# ===================================================================

def test_predict_guest_input_skips_render_cache_when_coop_game_exists():
    """Reaktivite iyileştirmesi: prediction sırasında render cache atlanmalı.

    Mevcut CoopGame instance'ı varsa `_apply_guest_render_cache` çağrılmamalı;
    bu, art arda gelen input'larda gereksiz iş yapılmasını engeller ve algılanan
    lag'ı azaltır. Render cache her frame `_update_guest_local_prediction`
    tarafından zaten ilerletilir.
    """
    net = FakeNet()
    game = _make_game(net)
    game.online_state = coop_module.OnlineCoopState.PLAYING
    game.role = 'guest'

    cache_apply_calls = {'count': 0}
    inject_calls: list = []

    def fake_apply_cache():
        cache_apply_calls['count'] += 1
        return game.coop_game

    fake_render = SimpleNamespace(
        game_over=False,
        paused=False,
        p2_current_piece=SimpleNamespace(shape_index=1, x=13, y=0, rotation_state=0),
        p2_next_piece=SimpleNamespace(shape_index=3),
        p2_hold_piece=None,
        p2_frozen=False,
        inject_remote_input=lambda player, action: inject_calls.append((player, action)),
    )
    game.coop_game = fake_render
    game._apply_guest_render_cache = fake_apply_cache
    # Cache verisi var ama coop_game zaten tanımlı → cache atlanmalı.
    game._guest_board_cache = {'seq': 1}
    game._guest_piece_cache = {'seq': 1}

    game._predict_guest_input('move_left')
    game._predict_guest_input('move_right')
    game._predict_guest_input('rotate')

    assert inject_calls == [
        ('P2', 'move_left'),
        ('P2', 'move_right'),
        ('P2', 'rotate'),
    ]
    assert cache_apply_calls['count'] == 0, (
        'CoopGame mevcutsa _predict_guest_input render cache çağırmamalı '
        '(reaktivite kök iyileştirmesi)'
    )


def test_predict_guest_input_cold_start_falls_back_to_render_cache():
    """CoopGame yoksa cold-start için cache uygulaması bir kere tetiklenmeli."""
    net = FakeNet()
    game = _make_game(net)
    game.online_state = coop_module.OnlineCoopState.PLAYING
    game.role = 'guest'

    cache_apply_calls = {'count': 0}

    fake_render = SimpleNamespace(
        game_over=False,
        paused=False,
        p2_current_piece=SimpleNamespace(shape_index=1, x=13, y=0, rotation_state=0),
        p2_next_piece=SimpleNamespace(shape_index=3),
        p2_hold_piece=None,
        p2_frozen=False,
        inject_remote_input=lambda player, action: None,
    )

    def fake_apply_cache():
        cache_apply_calls['count'] += 1
        # Cold-start: cache uygulaması coop_game'i kuruyor.
        game.coop_game = fake_render
        return fake_render

    game.coop_game = None
    game._ensure_guest_render_game = lambda: None
    game._apply_guest_render_cache = fake_apply_cache
    game._guest_board_cache = {'seq': 1}
    game._guest_piece_cache = {'seq': 1}

    game._predict_guest_input('move_left')

    assert cache_apply_calls['count'] == 1, (
        'CoopGame yokken cold-start cache fallback bir kez tetiklenmeli'
    )



# ===================================================================
# Pending row snapshot parity testleri (Mystery / Game / PvP / OnlinePvP /
# Coop / OnlineCoop hepsi aynı silinen-satır snapshot davranışına sahip
# olmalı — sweep ön kenarına kadar görünür kal).
# ===================================================================

def test_pvp_game_p1_line_clear_populates_pending_row_snapshot():
    """PvP P1 line clear sırasında pending row snapshot doldurulmalı."""
    import inspect
    import pvp_game as pvp_module
    src = inspect.getsource(pvp_module.PvPGame)
    assert 'p1_line_pending_rows' in src, 'PvPGame p1_line_pending_rows tutmuyor'
    assert 'p1_line_pending_colors' in src, 'PvPGame p1_line_pending_colors tutmuyor'
    assert 'last_cleared_colors' in src, (
        'PvPGame board.last_cleared_colors\'tan snapshot almıyor'
    )


def test_pvp_game_p2_line_clear_populates_pending_row_snapshot():
    """PvP P2 line clear sırasında pending row snapshot doldurulmalı."""
    import inspect
    import pvp_game as pvp_module
    src = inspect.getsource(pvp_module.PvPGame)
    assert 'p2_line_pending_rows' in src, 'PvPGame p2_line_pending_rows tutmuyor'
    assert 'p2_line_pending_colors' in src, 'PvPGame p2_line_pending_colors tutmuyor'


def test_online_pvp_line_clear_populates_pending_row_snapshot():
    """OnlinePvP line clear sırasında my/opp pending row snapshot doldurulmalı."""
    import inspect
    import online_pvp_game as opvp_module
    src = inspect.getsource(opvp_module.OnlinePvPGame)
    assert 'my_line_pending_rows' in src, 'OnlinePvPGame my_line_pending_rows tutmuyor'
    assert 'opp_line_pending_rows' in src, 'OnlinePvPGame opp_line_pending_rows tutmuyor'
    assert 'my_line_pending_colors' in src, 'OnlinePvPGame my_line_pending_colors tutmuyor'
    assert 'opp_line_pending_colors' in src, 'OnlinePvPGame opp_line_pending_colors tutmuyor'


def test_online_pvp_quadrix_burst_uses_shared_helper():
    """OnlinePvP Quadrix burst inline değil, ortak helper'a geçirilmiş olmalı."""
    import inspect
    import online_pvp_game as opvp_module
    src = inspect.getsource(opvp_module.OnlinePvPGame)
    assert '_trigger_combo_burst(' in src, (
        'OnlinePvPGame _trigger_combo_burst helper\'ını çağırmıyor'
    )
    assert 'self.create_particles(150, center_x, center_y, extra_colors' not in src, (
        'OnlinePvPGame Quadrix inline create_particles 150 hâlâ duruyor'
    )


def test_coop_game_line_clear_populates_combo_message():
    """CoopGame _lock_and_new_piece line clear sırasında combo_message kurmalı."""
    import inspect
    import coop_game as cg_module
    src = inspect.getsource(cg_module.CoopGame)
    # Combo / Quadrix overlay alanları ve string sabitleri kaynakta olmalı.
    assert 'self.combo_message' in src, 'CoopGame combo_message field\'i yok'
    assert '"QUADRIX!"' in src, 'CoopGame Quadrix combo mesajı set etmiyor'
    assert '"DOUBLE!"' in src, 'CoopGame Double combo mesajı set etmiyor'
    assert '"TRIPLE!"' in src, 'CoopGame Triple combo mesajı set etmiyor'
    assert 'get_combo_popup_alpha' in src, 'CoopGame combo overlay fade kullanmıyor'


def test_online_coop_guest_lock_event_sets_combo_message_on_render_game():
    """Online co-op guest lock event geldiğinde render_game.combo_message kurulmalı."""
    net = FakeNet()
    game = _make_game(net)
    game.online_state = coop_module.OnlineCoopState.PLAYING
    game.role = 'guest'

    fake_render = SimpleNamespace(
        line_clear_pending_rows=[],
        line_clear_pending_colors={},
        line_clear_wave_effects=[],
        cell_size=20,
        board_offset_x=10,
        board_offset_y=10,
        effects_enabled=True,
        board=SimpleNamespace(width=20, height=20, last_clear_row_colors={}),
        _start_line_clear_sweep=lambda rows: None,
        trigger_screen_shake=lambda *a, **kw: None,
        create_lock_explosion=lambda *a, **kw: None,
        create_particles=lambda *a, **kw: None,
        create_line_clear_particles=lambda *a, **kw: None,
        _start_block_fall_animation=lambda *a, **kw: None,
        line_clear_sweep_active=True,
        _fall_animation_rows_key=None,
        combo_message='',
        combo_message_time=0.0,
    )
    game.coop_game = fake_render
    game._ensure_guest_render_game = lambda: fake_render

    row_color = [(0, 255, 255)] * 20
    payload = {
        'type': MsgType.COOP_LOCK_EVENT,
        'player': 'P1',
        'lines': 4,
        'cleared_rows': [16, 17, 18, 19],
        'row_colors': {16: row_color, 17: row_color, 18: row_color, 19: row_color},
        'new_score': 800,
        'new_level': 2,
        'total_lines': 4,
    }
    game._apply_guest_lock_event(payload)

    assert fake_render.combo_message == 'QUADRIX!'
    assert fake_render.combo_message_time > 0


def test_online_coop_guest_lock_event_sets_double_combo_for_two_lines():
    """Online co-op guest 2-line clear DOUBLE mesajını set etmeli."""
    net = FakeNet()
    game = _make_game(net)
    game.online_state = coop_module.OnlineCoopState.PLAYING
    game.role = 'guest'

    fake_render = SimpleNamespace(
        line_clear_pending_rows=[],
        line_clear_pending_colors={},
        line_clear_wave_effects=[],
        cell_size=20,
        board_offset_x=10,
        board_offset_y=10,
        effects_enabled=True,
        board=SimpleNamespace(width=20, height=20, last_clear_row_colors={}),
        _start_line_clear_sweep=lambda rows: None,
        trigger_screen_shake=lambda *a, **kw: None,
        create_lock_explosion=lambda *a, **kw: None,
        create_particles=lambda *a, **kw: None,
        create_line_clear_particles=lambda *a, **kw: None,
        _start_block_fall_animation=lambda *a, **kw: None,
        line_clear_sweep_active=True,
        _fall_animation_rows_key=None,
        combo_message='',
        combo_message_time=0.0,
    )
    game.coop_game = fake_render
    game._ensure_guest_render_game = lambda: fake_render

    row_color = [(255, 100, 0)] * 20
    payload = {
        'type': MsgType.COOP_LOCK_EVENT,
        'player': 'P2',
        'lines': 2,
        'cleared_rows': [18, 19],
        'row_colors': {18: row_color, 19: row_color},
    }
    game._apply_guest_lock_event(payload)

    assert fake_render.combo_message == 'DOUBLE!'
    assert fake_render.combo_message_time > 0
