from __future__ import annotations

import os
import pathlib
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame


ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from board import Board
import pvp_game as pvp_game_module
from pvp_game import PvPGame


def _make_result_game(
    winner: int | str,
    *,
    p1_eliminated: bool = False,
    p2_eliminated: bool = False,
    size: tuple[int, int] = (1280, 720),
) -> PvPGame:
    pygame.init()
    pygame.font.init()

    game = PvPGame.__new__(PvPGame)
    game.screen = pygame.Surface(size)
    game.window_width, game.window_height = size
    game.player1_name = "Ada"
    game.player2_name = "Bora"
    game.board1 = Board()
    game.board2 = Board()
    game.board1.score = 48000
    game.board2.score = 35000
    game.board1.lines_cleared = 42
    game.board2.lines_cleared = 31
    game.winner = winner
    game.match_end_reason = "elimination"
    game.p1_eliminated = p1_eliminated
    game.p2_eliminated = p2_eliminated
    game._game_over_restart_rect = None
    game._game_over_menu_rect = None
    return game


def test_local_pvp_result_overlay_uses_online_style_controls(monkeypatch):
    monkeypatch.setattr(pvp_game_module, "get_mouse_pos", lambda: (-9999, -9999))
    game = _make_result_game(1, p2_eliminated=True)

    game._draw_game_over_screen()

    assert game._game_over_restart_rect is not None
    assert game._game_over_menu_rect is not None
    assert game._game_over_restart_rect.colliderect(game.screen.get_rect())
    assert game._game_over_menu_rect.colliderect(game.screen.get_rect())
    assert getattr(game, "_game_over_peek_rect", None) is None
    assert game.screen.get_at(game._game_over_restart_rect.center)[:3] != (0, 0, 0)


def test_local_pvp_result_breakdown_marks_loser_board_as_open_winner():
    game = _make_result_game(2, p1_eliminated=True)

    result = game._build_local_result_breakdown()

    assert result["winner"] == "p2"
    assert result["board_state"] == "p2"
    assert result["score_state"] == "p1"


def test_local_pvp_result_overlay_draws_draw_state(monkeypatch):
    monkeypatch.setattr(pvp_game_module, "get_mouse_pos", lambda: (-9999, -9999))
    game = _make_result_game("draw", p1_eliminated=True, p2_eliminated=True)
    game.board2.score = game.board1.score
    game.board2.lines_cleared = game.board1.lines_cleared

    game._draw_game_over_screen()

    assert game._game_over_restart_rect is not None
    assert game._game_over_menu_rect is not None


def test_local_pvp_result_overlay_fits_compact_viewport(monkeypatch):
    monkeypatch.setattr(pvp_game_module, "get_mouse_pos", lambda: (-9999, -9999))
    game = _make_result_game(1, p2_eliminated=True, size=(800, 600))

    game._draw_game_over_screen()

    assert game._game_over_restart_rect is not None
    assert game._game_over_menu_rect is not None
    assert game.screen.get_rect().contains(game._game_over_restart_rect)
    assert game.screen.get_rect().contains(game._game_over_menu_rect)
