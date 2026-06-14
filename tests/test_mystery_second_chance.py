from __future__ import annotations

from types import SimpleNamespace

import game_modes_extra as extra_modes_module


class _GhostEchoBoard:
    width = 10
    height = 20

    def __init__(self) -> None:
        self._locked_out = True
        self._last_lock_out = True
        self.cleared_rows = 0
        self.grid = [[(255, 255, 255) for _ in range(self.width)] for _ in range(self.height)]
        self.texture_grid = [[object() for _ in range(self.width)] for _ in range(self.height)]
        self.occupancy = [[True for _ in range(self.width)] for _ in range(self.height)]
        self.gold = [[True for _ in range(self.width)] for _ in range(self.height)]
        self.owners = [["piece" for _ in range(self.width)] for _ in range(self.height)]

    def clear_top_rows(self, n: int) -> None:
        self.cleared_rows = int(n)
        for y in range(int(n)):
            for x in range(self.width):
                self.grid[y][x] = extra_modes_module.BLACK
                self.texture_grid[y][x] = None
                self.occupancy[y][x] = False
                self.gold[y][x] = False
                self.owners[y][x] = None

    def clear_lock_out(self) -> None:
        self._locked_out = False
        self._last_lock_out = False

    def is_game_over(self) -> bool:
        return self._locked_out


def _build_armed_mode() -> extra_modes_module.MysteryMode:
    mode = extra_modes_module.MysteryMode.__new__(extra_modes_module.MysteryMode)
    mode.board = _GhostEchoBoard()
    mode.card_manager = SimpleNamespace(
        active_cards=[
            {"id": "ghost_echo", "value": 6},
            {"id": "score", "value": 100},
        ],
    )
    mode._active_effect_visuals = {"ghost_echo": {"id": "ghost_echo", "value": 6}}
    mode.card_message = ""
    mode.card_message_timer = 0.0
    mode._sync_active_cards = lambda: None
    return mode


def test_second_chance_consumes_card_and_clears_lock_out() -> None:
    mode = _build_armed_mode()

    assert mode._try_prevent_game_over_after_lock() is True

    assert mode.board.cleared_rows == 10
    assert mode.board.is_game_over() is False
    assert mode.board.occupancy[0] == [False] * mode.board.width
    assert mode._active_effect_visuals == {}
    assert [card["id"] for card in mode.card_manager.active_cards] == ["score"]


def test_second_chance_hook_lets_game_continue_after_top_out_lock() -> None:
    mode = _build_armed_mode()
    calls = []

    mode.effects_enabled = False
    mode.current_piece = SimpleNamespace(
        get_cells=lambda: [],
        color=(255, 255, 255),
        x=0,
        y=0,
    )
    next_piece = SimpleNamespace(x=0, y=0)
    spawned_piece = SimpleNamespace(x=0, y=0)
    mode.next_piece_queue = [next_piece]
    mode.spawn_new_piece = lambda: spawned_piece
    mode._skip_hidden_rows = lambda piece: calls.append(("skip", piece))
    mode.apply_theme_to_pieces = lambda: calls.append("theme")
    mode.get_current_speed = lambda: 700
    mode.sound = SimpleNamespace(
        play=lambda name: calls.append(("sound", name)),
        play_game_over_sequence=lambda: calls.append("game_over_sound"),
    )
    mode.finalize_run = lambda playtime=None: calls.append("finalize")
    mode.game_over = False
    mode.board.lock_piece = lambda piece: 0
    mode.board.last_cleared_lines = []

    extra_modes_module.Game.lock_and_new_piece(mode)

    assert mode.game_over is False
    assert "game_over_sound" not in calls
    assert "finalize" not in calls
    assert mode.current_piece is next_piece
    assert mode.next_piece_queue == [spawned_piece]
    assert mode.fall_speed == 700
