from collections import OrderedDict
import pygame


class SurfaceLRUCache:
    """O(1) LRU cache for reusable rendered surfaces."""

    def __init__(self, max_entries: int = 64):
        self.max_entries = max(1, int(max_entries))
        self._cache: OrderedDict[tuple, pygame.Surface] = OrderedDict()

    @property
    def _order(self) -> list[tuple]:
        return list(self._cache.keys())

    @_order.setter
    def _order(self, value: list[tuple]) -> None:
        pass

    def clear(self) -> None:
        self._cache.clear()

    def get(self, key: tuple) -> pygame.Surface | None:
        surface = self._cache.get(key)
        if surface is None:
            return None
        self._cache.move_to_end(key)
        return surface

    def put(self, key: tuple, surface: pygame.Surface) -> pygame.Surface:
        self._cache[key] = surface
        self._cache.move_to_end(key)
        while len(self._cache) > self.max_entries:
            self._cache.popitem(last=False)
        return surface