from __future__ import annotations

import pathlib
import sys
import types
from unittest.mock import Mock


ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / 'src'

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import online_pvp_game as online_pvp_module


def _make_game() -> online_pvp_module.OnlinePvPGame:
    game = online_pvp_module.OnlinePvPGame.__new__(online_pvp_module.OnlinePvPGame)
    game.net = types.SimpleNamespace(
        send_piece_position=Mock(),
        send_board_state=Mock(),
        get_messages=lambda: [],
        opponent_steam_id=7,
        leave_lobby=Mock(),
    )
    game._net_initialized = True
    game.my_piece = types.SimpleNamespace(shape_index=2, x=3, y=4, rotation_state=0)
    game._my_piece_seq = 0
    game._last_sent_piece_signature = None
    game._pending_piece_position_dirty = False
    game._piece_position_send_timer = 0.0
    game._PIECE_POSITION_INTERVAL_MS = 33.0
    game.opponent_piece_data = None
    game._opponent_piece_visual = None
    game._opponent_piece_render_cache_key = None
    game._opponent_piece_render_cache = None
    game._OPPONENT_PIECE_SMOOTH_MS = 45.0
    return game


def test_online_pvp_piece_position_coalesces_until_interval():
    game = _make_game()

    assert game._send_piece_position() is True
    assert game.net.send_piece_position.call_count == 1

    game.my_piece.x = 4
    game._piece_position_send_timer = 10.0

    assert game._send_piece_position() is False
    assert game.net.send_piece_position.call_count == 1
    assert game._pending_piece_position_dirty is True

    game._piece_position_send_timer = 40.0

    assert game._flush_piece_position() is True
    assert game.net.send_piece_position.call_count == 2
    assert game.net.send_piece_position.call_args.args[:4] == (2, 4, 4, 0)


def test_online_pvp_piece_position_force_bypasses_coalescing_window():
    game = _make_game()

    assert game._send_piece_position() is True
    game.my_piece.rotation_state = 1
    game._piece_position_send_timer = 1.0

    assert game._send_piece_position(force=True) is True
    assert game.net.send_piece_position.call_count == 2
    assert game.net.send_piece_position.call_args.args[:4] == (2, 3, 4, 1)


def test_online_pvp_opponent_piece_visual_smooths_toward_target():
    game = _make_game()

    assert game._set_opponent_piece_state({'si': 1, 'x': 3, 'y': 4, 'r': 0}) is True
    assert game.opponent_piece_data == {'si': 1, 'x': 3, 'y': 4, 'r': 0}
    assert game._opponent_piece_visual['draw_x'] == 3.0
    assert game._opponent_piece_visual['draw_y'] == 4.0

    assert game._set_opponent_piece_state({'si': 1, 'x': 5, 'y': 4, 'r': 0}) is True
    assert game._opponent_piece_visual['draw_x'] == 3.0
    assert game._opponent_piece_visual['target_x'] == 5.0

    game._advance_opponent_piece_visual(22.5)

    assert 3.0 < game._opponent_piece_visual['draw_x'] < 5.0
    assert game._get_opponent_piece_draw_state()['si'] == 1


def test_online_pvp_snapshot_piece_far_correction_snaps_visual_state():
    game = _make_game()

    assert game._set_opponent_piece_state({'si': 4, 'x': 1, 'y': 2, 'r': 0}) is True
    game._advance_opponent_piece_visual(10.0)

    assert game._set_opponent_piece_state({'si': 4, 'x': 7, 'y': 9, 'r': 0}, from_snapshot=True) is True
    assert game._opponent_piece_visual['draw_x'] == 7.0
    assert game._opponent_piece_visual['draw_y'] == 9.0