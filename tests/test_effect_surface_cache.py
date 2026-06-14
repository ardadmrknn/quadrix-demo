from __future__ import annotations

import os
import sys

import pygame


SRC_DIR = os.path.join(os.path.dirname(__file__), '..', 'src')
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from effect_surface_cache import EffectSurfaceCache


def test_filled_surface_reuses_cached_surface():
    cache = EffectSurfaceCache()

    first = cache.get_filled_surface((64, 12), (255, 255, 255, 96))
    second = cache.get_filled_surface((64, 12), (255, 255, 255, 96))

    assert first is second
    assert first.get_size() == (64, 12)


def test_circle_surface_reuses_cached_surface():
    cache = EffectSurfaceCache()

    first = cache.get_circle_surface(8, (200, 200, 255, 80))
    second = cache.get_circle_surface(8, (200, 200, 255, 80))

    assert first is second
    assert first.get_size() == (16, 16)


def test_ellipse_surface_reuses_cached_surface():
    cache = EffectSurfaceCache()

    first = cache.get_ellipse_surface((42, 6), (255, 240, 180, 128))
    second = cache.get_ellipse_surface((42, 6), (255, 240, 180, 128))

    assert first is second
    assert first.get_size() == (42, 6)


def test_cache_evicts_oldest_entries_when_limit_exceeded():
    cache = EffectSurfaceCache(max_entries=2)

    first = cache.get_circle_surface(4, (255, 0, 0, 255))
    cache.get_circle_surface(5, (0, 255, 0, 255))
    cache.get_circle_surface(6, (0, 0, 255, 255))
    replacement = cache.get_circle_surface(4, (255, 0, 0, 255))

    assert replacement is not first