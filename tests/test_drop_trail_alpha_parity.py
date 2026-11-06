from __future__ import annotations

import pygame
import numpy as np

import game as game_module
from pieces import Piece


def _make_game():
    pygame.init()
    game = game_module.Game.__new__(game_module.Game)
    game.effects_enabled = True
    game.drop_trails = []
    game.screen = pygame.Surface((160, 320), pygame.SRCALPHA)
    game.get_cell_size = lambda: 32
    game.get_board_offset = lambda: (0, 0)
    return game


def _render_top_alpha(monkeypatch, numpy_enabled: bool) -> int:
    monkeypatch.setattr(game_module, "_NUMPY_AVAILABLE", numpy_enabled)
    if numpy_enabled:
        class _Surfarray:
            @staticmethod
            def array_alpha(surface):
                w, h = surface.get_size()
                return np.array(
                    [[surface.get_at((x, y)).a for y in range(h)] for x in range(w)],
                    dtype=np.uint8,
                )

        monkeypatch.setattr(game_module.pygame, "surfarray", _Surfarray)
    game = _make_game()
    piece = Piece(x=1, y=0, shape_index=0)
    game._create_drop_trail(piece, start_y=0, distance=6, trail_type="hard")
    trail = game.drop_trails[0]
    return trail["_surf"].get_at((1, 0)).a


def test_hard_drop_trail_alpha_is_platform_parity(monkeypatch):
    numpy_alpha = _render_top_alpha(monkeypatch, True)
    fallback_alpha = _render_top_alpha(monkeypatch, False)

    assert numpy_alpha == 180
    assert fallback_alpha == 180
    assert numpy_alpha == fallback_alpha
