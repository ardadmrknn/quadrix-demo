"""Regresyon: büyük skor HUD satırındaki ayırıcı metni kesmemeli.

Geri bildirimdeki 1.000.457.432 skor ekranında ayırıcı çizgi skor metnine
çarpmış görünüyordu. Test gerçek ``Game._draw_right_hud_panel`` çağrısını
headless Surface üzerinde izler; üretim geometrisini kopyalayan yalnız plan
assert'iyle sınırlı değildir.
"""
from __future__ import annotations

import os
import pathlib
import sys
from types import SimpleNamespace

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
import pytest

ROOT_DIR = pathlib.Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import game as game_module
from game import Game
from mode_skins import get_mode_skin

pytestmark = [pytest.mark.quadrix_feedback, pytest.mark.quadrix_phase5]

if not pygame.font.get_init():
    pygame.font.init()


class _TraceSurface(pygame.Surface):
    """Gerçek HUD blit rect'lerini gözlemlemek için Surface alt sınıfı."""

    def __init__(self, size):
        super().__init__(size, pygame.SRCALPHA)
        self.blit_rects: list[pygame.Rect] = []

    def blit(self, source, dest, *args, **kwargs):
        rect = source.get_rect(topleft=dest) if not isinstance(dest, pygame.Rect) else source.get_rect(topleft=dest.topleft)
        self.blit_rects.append(rect.copy())
        return super().blit(source, dest, *args, **kwargs)


def _make_game() -> Game:
    game = Game.__new__(Game)
    game.screen = _TraceSurface((640, 360))
    game.window_width, game.window_height = 640, 360
    game.board = SimpleNamespace(
        score=1_000_457_432,
        lines_cleared=4_832,
        level=967,
        combo=1,
        tetrises=317,
    )
    game.next_piece_queue = []
    game.held_piece = None
    game.can_hold = True
    game._hide_next_pieces = False
    game._show_hold_x = False
    game.control_bindings = {}
    game.perk_manager = None
    game._draw_hud_glass_panel = lambda rect: None
    game._draw_custom_frame = lambda *args, **kwargs: False
    game.draw_textured_block = lambda *args, **kwargs: None
    game._make_texture_slice = lambda *args, **kwargs: None
    return game


def test_large_score_vertical_separator_stays_below_value(monkeypatch):
    """1.000.457.432 dar HUD'da gerçek ayırıcı değer rect'ine girmemeli."""
    game = _make_game()
    separator_lines: list[tuple[tuple[int, int], tuple[int, int]]] = []
    original_line = game_module.pygame.draw.line

    def _record_line(surface, color, start, end, width=1):
        separator_lines.append((tuple(start), tuple(end)))
        return original_line(surface, color, start, end, width)

    monkeypatch.setattr(game_module.pygame.draw, "line", _record_line)
    game._draw_right_hud_panel(
        430,
        70,
        300,
        620,
        get_mode_skin("classic"),
        None,
        (255, 255, 255),
        (0, 255, 255),
        (180, 180, 180),
    )

    stats_rect = game._hud_stats_rect
    stat_blits = [
        rect
        for rect in game.screen.blit_rects
        if rect.top >= stats_rect.top and rect.bottom <= stats_rect.bottom
    ]
    assert len(stat_blits) >= 2, f"gerçek stat blit'leri kaydedilmedi: {stat_blits!r}"
    score_label_rect, score_value_rect = stat_blits[:2]
    assert score_label_rect.top < score_value_rect.top

    stat_lines = [
        start[1]
        for start, end in separator_lines
        if start[1] == end[1] and start[1] >= stats_rect.top
    ]
    assert stat_lines, "stat separator çizgisi gerçek çizimde kaydedilmedi"

    assert stat_lines[0] > score_value_rect.bottom, (
        "HUD ayırıcı çizgisi büyük skor değerinin içine giriyor: "
        f"line_y={stat_lines[0]}, value_rect={score_value_rect}, "
        f"stats_rect={stats_rect}"
    )




