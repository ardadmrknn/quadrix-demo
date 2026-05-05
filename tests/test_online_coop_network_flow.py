from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pygame

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from steam_networking import MsgType, SteamNetworking  # noqa: E402
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
    game._last_input_ack_seq = 0
    game._held_gameplay_keys = set()
    game._board_state_seq = 0
    game._piece_state_seq = 0
    game._guest_board_seq = -1
    game._guest_piece_seq = -1
    game._guest_board_cache = None
    game._guest_piece_cache = None
    game._guest_score_cache = {}
    game._guest_render_board_seq = -1
    game._guest_render_piece_seq = -1
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
    monkeypatch.setattr(coop_module.OnlineCoopGame, '_send_board_state', lambda self: None)
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


def test_online_coop_ignores_non_game_channel_messages():
    net = FakeNet([
        _message(42, {'type': MsgType.READY}, channel=2),
    ])
    game = _make_game(net)

    game._process_messages()

    assert game.opponent_ready is False


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


def test_online_coop_filters_held_key_repeat_before_sending_guest_input(monkeypatch):
    net = FakeNet()
    game = _make_game(net)
    game.online_state = coop_module.OnlineCoopState.PLAYING
    game.role = 'guest'
    predicted = []
    monkeypatch.setattr(game, '_predict_guest_input', lambda action: predicted.append(action))

    event = SimpleNamespace(key=pygame.K_LEFT)
    game._handle_gameplay_keydown(event)
    game._handle_gameplay_keydown(event)

    assert [sent[0]['action'] for sent in net.sent] == ['move_left']
    assert predicted == ['move_left']


def test_online_coop_host_board_snapshot_uses_occupancy_not_black_grid_color():
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

    sent_grid = net.sent[0][0]['grid']
    assert all(cell == 0 for row in sent_grid for cell in row)


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
