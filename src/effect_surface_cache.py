import pygame


class EffectSurfaceCache:
    """Small LRU cache for frequently re-created alpha helper surfaces."""

    def __init__(self, max_entries: int = 384):
        self.max_entries = max(1, int(max_entries))
        self._cache: dict[tuple, pygame.Surface] = {}
        self._order: list[tuple] = []

    @staticmethod
    def _normalize_color(color) -> tuple[int, int, int, int]:
        if not isinstance(color, (tuple, list)):
            return (255, 255, 255, 255)
        if len(color) >= 4:
            return (
                max(0, min(255, int(color[0]))),
                max(0, min(255, int(color[1]))),
                max(0, min(255, int(color[2]))),
                max(0, min(255, int(color[3]))),
            )
        if len(color) >= 3:
            return (
                max(0, min(255, int(color[0]))),
                max(0, min(255, int(color[1]))),
                max(0, min(255, int(color[2]))),
                255,
            )
        return (255, 255, 255, 255)

    def clear(self) -> None:
        self._cache.clear()
        self._order.clear()

    def _get(self, key: tuple) -> pygame.Surface | None:
        surface = self._cache.get(key)
        if surface is None:
            return None
        try:
            self._order.remove(key)
        except ValueError:
            pass
        self._order.append(key)
        return surface

    def _put(self, key: tuple, surface: pygame.Surface) -> pygame.Surface:
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

    def get_filled_surface(self, size, color) -> pygame.Surface:
        width, height = size
        width = max(1, int(width))
        height = max(1, int(height))
        rgba = self._normalize_color(color)
        key = ('fill', width, height, rgba)
        cached = self._get(key)
        if cached is not None:
            return cached

        surface = pygame.Surface((width, height), pygame.SRCALPHA)
        surface.fill(rgba)
        return self._put(key, surface)

    def get_circle_surface(self, radius: int, color) -> pygame.Surface:
        radius = max(1, int(radius))
        rgba = self._normalize_color(color)
        key = ('circle', radius, rgba)
        cached = self._get(key)
        if cached is not None:
            return cached

        diameter = radius * 2
        surface = pygame.Surface((diameter, diameter), pygame.SRCALPHA)
        pygame.draw.circle(surface, rgba, (radius, radius), radius)
        return self._put(key, surface)

    def get_ellipse_surface(self, size, color) -> pygame.Surface:
        width, height = size
        width = max(1, int(width))
        height = max(1, int(height))
        rgba = self._normalize_color(color)
        key = ('ellipse', width, height, rgba)
        cached = self._get(key)
        if cached is not None:
            return cached

        surface = pygame.Surface((width, height), pygame.SRCALPHA)
        pygame.draw.ellipse(surface, rgba, surface.get_rect())
        return self._put(key, surface)