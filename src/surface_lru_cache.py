import pygame


class SurfaceLRUCache:
    """Small LRU cache for reusable rendered surfaces."""

    def __init__(self, max_entries: int = 64):
        self.max_entries = max(1, int(max_entries))
        self._cache: dict[tuple, pygame.Surface] = {}
        self._order: list[tuple] = []

    def clear(self) -> None:
        self._cache.clear()
        self._order.clear()

    def get(self, key: tuple) -> pygame.Surface | None:
        surface = self._cache.get(key)
        if surface is None:
            return None
        try:
            self._order.remove(key)
        except ValueError:
            pass
        self._order.append(key)
        return surface

    def put(self, key: tuple, surface: pygame.Surface) -> pygame.Surface:
        if key in self._cache:
            self._cache[key] = surface
            try:
                self._order.remove(key)
            except ValueError:
                pass
            self._order.append(key)
            return surface

        self._cache[key] = surface
        self._order.append(key)
        while len(self._order) > self.max_entries:
            oldest = self._order.pop(0)
            self._cache.pop(oldest, None)
        return surface