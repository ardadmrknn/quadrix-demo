from __future__ import annotations

from collections import OrderedDict
import os
import sys

import pygame

SRC_DIR = os.path.join(os.path.dirname(__file__), '..', 'src')
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from surface_lru_cache import SurfaceLRUCache


def test_surface_lru_cache_uses_ordered_dict():
    """Implementasyonun O(1) OrderedDict kullandığı statik olarak doğrulanmalıdır."""
    cache = SurfaceLRUCache(max_entries=4)
    assert isinstance(cache._cache, OrderedDict), "SurfaceLRUCache._cache OrderedDict tipinde olmalı"


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


def test_surface_lru_cache_reordering_on_get_prevents_eviction():
    """get() çağrısı yapılan anahtar en sona taşınmalı ve bir sonraki taşmada atılmamalıdır."""
    pygame.init()
    try:
        cache = SurfaceLRUCache(max_entries=2)
        s1 = pygame.Surface((8, 8))
        s2 = pygame.Surface((8, 8))
        s3 = pygame.Surface((8, 8))

        cache.put(('k1',), s1)
        cache.put(('k2',), s2)

        # k1'e eriş: k1 en sona taşınmalı, en eski k2 olmalı
        assert cache.get(('k1',)) is s1

        # k3 ekle: k2 atılmalı, k1 ve k3 kalmalı
        cache.put(('k3',), s3)

        assert cache.get(('k2',)) is None, "k2 en eski olduğu için atılmış olmalı"
        assert cache.get(('k1',)) is s1, "k1 get ile yenilendiği için korunmuş olmalı"
        assert cache.get(('k3',)) is s3
    finally:
        pygame.quit()


def test_surface_lru_cache_replacement_updates_lru_order():
    """Mevcut anahtara yeni değer yazılması (replacement) anahtarı en sona taşımalıdır."""
    pygame.init()
    try:
        cache = SurfaceLRUCache(max_entries=2)
        s1 = pygame.Surface((8, 8))
        s2 = pygame.Surface((8, 8))
        s1_new = pygame.Surface((8, 8))
        s3 = pygame.Surface((8, 8))

        cache.put(('k1',), s1)
        cache.put(('k2',), s2)

        # k1'i güncelle: k1 en sona geçer, k2 en eski olur
        cache.put(('k1',), s1_new)

        # k3 ekle: k2 atılmalı
        cache.put(('k3',), s3)

        assert cache.get(('k2',)) is None
        assert cache.get(('k1',)) is s1_new
        assert cache.get(('k3',)) is s3
    finally:
        pygame.quit()


def test_surface_lru_cache_clear():
    """clear() tüm önbelleği boşaltmalıdır."""
    cache = SurfaceLRUCache(max_entries=5)
    cache.put(('a',), pygame.Surface((4, 4)))
    cache.put(('b',), pygame.Surface((4, 4)))
    assert len(cache._cache) == 2

    cache.clear()
    assert len(cache._cache) == 0
    assert cache.get(('a',)) is None