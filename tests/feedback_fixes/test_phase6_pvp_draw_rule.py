from __future__ import annotations

import os
import pathlib
import sys

import pygame
import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

ROOT_DIR = pathlib.Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from board import Board
import pvp_game as pvp_game_module
from pvp_game import PvPGame


pytestmark = [pytest.mark.quadrix_feedback, pytest.mark.quadrix_phase6]


def _weighted_example() -> PvPGame:
    pygame.init()
    game = PvPGame.__new__(PvPGame)
    game.player1_name = "Ada"
    game.player2_name = "Bora"
    game.board1 = Board()
    game.board2 = Board()
    game.board1.score = 48_000
    game.board2.score = 35_000
    game.board1.lines_cleared = 42
    game.board2.lines_cleared = 31
    game.p1_eliminated = True
    game.p2_eliminated = False
    return game


def test_weighted_model_constants_and_zero_two_example_are_preserved():
    assert pvp_game_module.LOCAL_PVP_RESULT_SCORE_POINTS == 1
    assert pvp_game_module.LOCAL_PVP_RESULT_LINES_POINTS == 1
    assert pvp_game_module.LOCAL_PVP_RESULT_BOARD_OPEN_POINTS == 2
    assert pvp_game_module.LOCAL_PVP_RESULT_WIN_THRESHOLD == 3

    result = _weighted_example()._build_local_result_breakdown()
    assert result["p1_points"] == 2
    assert result["p2_points"] == 2
    assert result["winner"] == "draw"
    assert result["board_state"] == "p2"


def test_zero_two_example_reason_text_explains_weighted_draw(monkeypatch):
    monkeypatch.setattr(pvp_game_module, "get_language", lambda: "tr")
    text = _weighted_example()._build_local_result_reason_text()
    assert "2-2" in text
    assert "berabere" in text.lower()
    assert "alan ise 2" in text

