"""Text render cache for pygame.font.Font.render.

Amaç: UI ekranlarında her frame tekrarlanan font.render çağrılarını azaltmak.
Not: Cache anahtarı font objesinin id'si + metin + antialias + renk tuple'ıdır.
"""

from __future__ import annotations

import sys
from collections import OrderedDict
from typing import Optional

import pygame

# sys.modules üzerinde absolute ve relative import uyumsuzluklarını önlemek için alias oluştur
_current_module = sys.modules.get(__name__)
if _current_module is not None:
    sys.modules.setdefault('text_cache', _current_module)
    sys.modules.setdefault('src.text_cache', _current_module)


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


# System Font Safety Patch (Windows registry DWORD / TypeError guard):
try:
    import pygame.sysfont
    if hasattr(pygame.sysfont, 'initsysfonts_win32'):
        _orig_initsysfonts_win32 = pygame.sysfont.initsysfonts_win32
        def _safe_initsysfonts_win32():
            try:
                return _orig_initsysfonts_win32()
            except Exception:
                return {}
        pygame.sysfont.initsysfonts_win32 = _safe_initsysfonts_win32
except Exception:
    pass


# C-extension type immutability bypass:
# pygame.font.Font'u doğrudan değiştiremeyiz. Bu yüzden subclass türetip
# pygame.font.Font ve pygame.sysfont.Font referanslarını eziyoruz.
if hasattr(pygame, 'font') and hasattr(pygame.font, 'Font'):
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

        def render_shared(self, text, antialias, color, background=None) -> pygame.Surface:
            """Salt-okunur (immutable) blit işlemleri için doğrudan paylaşımlı Surface döndürür."""
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
                return cached

            rendered = super().render(safe_text, antialias, color, background)
            _TEXT_CACHE.set(key, rendered)
            return rendered

def patch_font() -> None:
    """pygame.font.Font ve sysfont.Font'u PatchedFont ile değiştirir."""
    global pygame
    if hasattr(pygame, "font") and hasattr(pygame.font, "Font"):
        if pygame.font.Font is not PatchedFont:
            pygame.font.Font = PatchedFont
        try:
            import pygame.sysfont
            if pygame.sysfont.Font is not PatchedFont:
                pygame.sysfont.Font = PatchedFont
        except Exception:
            pass


patch_font()


def render_text(
    font: pygame.font.Font,
    text: str,
    antialias: bool,
    color,
    background=None,
) -> pygame.Surface:
    """Render text with a small LRU cache (güvenli kopya)."""
    return font.render(text, antialias, color, background)


def render_text_shared(
    font: pygame.font.Font,
    text: str,
    antialias: bool,
    color,
    background=None,
) -> pygame.Surface:
    """Yalnızca mutasyona uğramayacak salt okunur blit işlemleri için paylaşımlı Surface döndürür."""
    if hasattr(font, 'render_shared'):
        return font.render_shared(text, antialias, color, background)

    # Font PatchedFont değilse bile doğrudan LRU önbelleğini yönet
    safe_text = "" if text is None else str(text)
    try:
        color_key = tuple(color)
    except Exception:
        color_key = (255, 255, 255)

    try:
        bg_key = tuple(background) if background is not None else None
    except Exception:
        bg_key = None

    key = (id(font), safe_text, bool(antialias), color_key, bg_key)
    cached = _TEXT_CACHE.get(key)
    if cached is not None:
        return cached

    rendered = font.render(safe_text, antialias, color, background)
    _TEXT_CACHE.set(key, rendered)
    return rendered


def clear_text_cache() -> None:
    _TEXT_CACHE.clear()
