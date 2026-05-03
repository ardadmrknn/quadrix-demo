from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace


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
        self.sent = []
        self.joined = []
        self.left = False

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

    def leave_lobby(self):
        self.left = True

    def get_lobby_owner(self):
        return 0

    def get_lobby_data_for(self, lobby_id, key):
        return ''

    def request_lobby_data(self, lobby_id):
        return True


def _message(sender: int, data: dict):
    return SimpleNamespace(sender=sender, data=data)


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
    game._guest_board_seq = -1
    game._guest_piece_seq = -1
    game._guest_board_cache = None
    game._guest_piece_cache = None
    game._guest_score_cache = {}
    game._game_start_pending_payload = None
    game._game_start_retry_timer = 0.0
    game._game_seed = 0
    game.selected_submode = 'endless'
    game.countdown_value = 3
    game.countdown_timer = 0
    game.game_over = False
    game.paused = False
    game.coop_game = None
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


def test_online_coop_guest_ignores_out_of_order_board_snapshots():
    net = FakeNet([
        _message(42, {'type': MsgType.COOP_BOARD_STATE, 'seq': 5, 'team_score': 100}),
        _message(42, {'type': MsgType.COOP_BOARD_STATE, 'seq': 4, 'team_score': 10}),
    ])
    net.opponent_steam_id = 42
    game = _make_game(net)
    game.role = 'guest'

    game._process_messages()

    assert game._guest_board_seq == 5
    assert game._guest_board_cache['team_score'] == 100


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
