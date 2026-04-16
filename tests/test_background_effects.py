from __future__ import annotations

import pygame

import background_effects as be


def test_falling_blocks_cached_jelly_surface_bakes_alpha():
    pygame.init()

    layer = be.FallingBlocksLayer(block_count=1)
    cell_surface = layer._get_cached_jelly_cell_surface(24, (255, 50, 80), 64)

    assert cell_surface.get_flags() & pygame.SRCALPHA
    assert cell_surface.get_at((12, 12)).a == 64


def test_falling_blocks_fallback_draw_produces_visible_pixels(monkeypatch):
    pygame.init()

    layer = be.FallingBlocksLayer(block_count=1)
    screen = pygame.Surface((160, 120), pygame.SRCALPHA)
    layer.update(screen)

    block = layer.blocks[0]
    block.shape = [(0, 0)]
    block.size = 20
    block.x = 10.0
    block.y = 10.0
    block.alpha = 96

    monkeypatch.setattr(be, '_HAS_JELLY', False)
    monkeypatch.setattr(be, 'draw_jelly_block', None)

    layer.draw(screen)

    assert screen.get_at((20, 20)).a > 0