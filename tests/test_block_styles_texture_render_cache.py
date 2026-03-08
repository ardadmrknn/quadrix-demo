from __future__ import annotations

import os
import sys

import pygame


SRC_DIR = os.path.join(os.path.dirname(__file__), '..', 'src')
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from block_styles import TextureRenderCache, TextureSlice


def test_render_slice_caches_scaled_cell(monkeypatch):
    cache = TextureRenderCache()
    source = pygame.Surface((32, 32), pygame.SRCALPHA)
    slice_info = TextureSlice('T', rel_x=0, rel_y=0, width=1, height=1, rotation=0)
    calls: list[tuple[tuple[int, int], tuple[int, int]]] = []

    def fake_smoothscale(surface, size):
        calls.append((surface.get_size(), size))
        return pygame.Surface(size, pygame.SRCALPHA)

    monkeypatch.setattr(pygame.transform, 'smoothscale', fake_smoothscale)

    first = cache.render_slice(source, slice_info, 24, {'x': 0.0, 'y': 0.0, 'w': 1.0, 'h': 1.0})
    second = cache.render_slice(source, slice_info, 24, {'x': 0.0, 'y': 0.0, 'w': 1.0, 'h': 1.0})

    assert first is second
    assert calls == [((32, 32), (24, 24))]


def test_render_slice_invalidates_cache_when_bounds_change(monkeypatch):
    cache = TextureRenderCache()
    source = pygame.Surface((32, 32), pygame.SRCALPHA)
    slice_info = TextureSlice('T', rel_x=0, rel_y=0, width=1, height=1, rotation=0)
    calls: list[tuple[tuple[int, int], tuple[int, int]]] = []

    def fake_smoothscale(surface, size):
        calls.append((surface.get_size(), size))
        return pygame.Surface(size, pygame.SRCALPHA)

    monkeypatch.setattr(pygame.transform, 'smoothscale', fake_smoothscale)

    cache.render_slice(source, slice_info, 24, {'x': 0.0, 'y': 0.0, 'w': 1.0, 'h': 1.0})
    cache.render_slice(source, slice_info, 24, {'x': 0.25, 'y': 0.0, 'w': 0.75, 'h': 1.0})

    assert len(calls) == 2


def test_render_slice_handles_zero_width_height_defensively(monkeypatch):
    cache = TextureRenderCache()
    source = pygame.Surface((32, 32), pygame.SRCALPHA)
    slice_info = TextureSlice('T', rel_x=0, rel_y=0, width=0, height=0, rotation=0)

    def fake_smoothscale(surface, size):
        return pygame.Surface(size, pygame.SRCALPHA)

    monkeypatch.setattr(pygame.transform, 'smoothscale', fake_smoothscale)

    scaled = cache.render_slice(source, slice_info, 24, {'x': 0.0, 'y': 0.0, 'w': 1.0, 'h': 1.0})

    assert scaled is not None
    assert scaled.get_size() == (24, 24)