from __future__ import annotations

import os
import sys

import pygame


SRC_DIR = os.path.join(os.path.dirname(__file__), '..', 'src')
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from surface_lru_cache import SurfaceLRUCache


def test_surface_lru_cache_reuses_surface_by_key():
    pygame.init()
    try:
        cache = SurfaceLRUCache(max_entries=4)
        key = ('tile', 1)
        surface = pygame.Surface((32, 32), pygame.SRCALPHA)

        cache.put(key, surface)

        assert cache.get(key) is surface
    finally:
        pygame.quit()


def test_surface_lru_cache_evicts_oldest_entry():
    pygame.init()
    try:
        cache = SurfaceLRUCache(max_entries=2)
        first = pygame.Surface((8, 8), pygame.SRCALPHA)
        second = pygame.Surface((8, 8), pygame.SRCALPHA)
        third = pygame.Surface((8, 8), pygame.SRCALPHA)

        cache.put(('first',), first)
        cache.put(('second',), second)
        cache.put(('third',), third)

        assert cache.get(('first',)) is None
        assert cache.get(('second',)) is second
        assert cache.get(('third',)) is third
    finally:
        pygame.quit()