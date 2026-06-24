"""Text render cache for pygame.font.Font.render.

Amaç: UI ekranlarında her frame tekrarlanan font.render çağrılarını azaltmak.
Not: Cache anahtarı font objesinin id'si + metin + antialias + renk tuple'ıdır.
"""

from __future__ import annotations

from collections import OrderedDict
from typing import Optional

import pygame


class _LRUCache:
    def __init__(self, max_items: int):
        self._max_items = max(1, int(max_items))
        self._data: "OrderedDict[tuple, pygame.Surface]" = OrderedDict()

    def get(self, key: tuple) -> Optional[pygame.Surface]:
        value = self._data.get(key)
        if value is not None:
            self._data.move_to_end(key)
        return value

    def set(self, key: tuple, value: pygame.Surface) -> None:
        self._data[key] = value
        self._data.move_to_end(key)
        while len(self._data) > self._max_items:
            self._data.popitem(last=False)

    def clear(self) -> None:
        self._data.clear()


_TEXT_CACHE = _LRUCache(max_items=1024)


# C-extension type immutability bypass:
# pygame.font.Font'u doğrudan değiştiremeyiz. Bu yüzden subclass türetip
# pygame.font.Font ve pygame.sysfont.Font referanslarını eziyoruz.
class PatchedFont(pygame.font.Font):
    def render(self, text, antialias, color, background=None):
        safe_text = "" if text is None else str(text)
        try:
            color_key = tuple(color)
        except Exception:
            color_key = (255, 255, 255)

        try:
            bg_key = tuple(background) if background is not None else None
        except Exception:
            bg_key = None

        key = (id(self), safe_text, bool(antialias), color_key, bg_key)
        cached = _TEXT_CACHE.get(key)
        if cached is not None:
            return cached.copy()

        rendered = super().render(safe_text, antialias, color, background)
        _TEXT_CACHE.set(key, rendered)
        return rendered.copy()


# Sınıf referanslarını güncelle
pygame.font.Font = PatchedFont
try:
    import pygame.sysfont
    pygame.sysfont.Font = PatchedFont
except Exception:
    pass


def render_text(
    font: pygame.font.Font,
    text: str,
    antialias: bool,
    color,
) -> pygame.Surface:
    """Render text with a small LRU cache."""
    return font.render(text, antialias, color)


def clear_text_cache() -> None:
    _TEXT_CACHE.clear()
