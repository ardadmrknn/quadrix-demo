"""Asset loading helpers with lightweight caching.

Amaç: Sık kullanılan görsellerin (pygame.image.load + convert/convert_alpha) tekrar tekrar yapılmasını önlemek.
"""

from __future__ import annotations

import os
import sys
from collections import OrderedDict
from pathlib import Path
from typing import Optional, Tuple, Union

import pygame

# macOS detection
_IS_MACOS = sys.platform == 'darwin'


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


_RAW_IMAGE_CACHE = _LRUCache(max_items=96)
_SCALED_IMAGE_CACHE = _LRUCache(max_items=192)


def _normalize_path(path: Union[str, os.PathLike]) -> str:
    # resolve() bazı senaryolarda (relative / non-existent) exception atabilir; güvenli normalize.
    try:
        p = Path(path)
        if p.exists():
            p = p.resolve()
        return os.path.normpath(str(p))
    except Exception:
        return os.path.normpath(str(path))


def load_image(
    path: Union[str, os.PathLike],
    *,
    convert_alpha: bool = False,
    convert: bool = False,
    size: Optional[Tuple[int, int]] = None,
    smoothscale: bool = True,
) -> pygame.Surface:
    """Görsel yükle (cache'li).

    Args:
        path: Dosya yolu (str veya Path)
        convert_alpha: convert_alpha() uygula
        convert: convert() uygula (convert_alpha ile birlikte kullanılmamalı)
        size: Eğer verilirse (w,h) boyutuna scale et
        smoothscale: True ise pygame.transform.smoothscale kullan
    """

    norm_path = _normalize_path(path)
    raw_key = (norm_path, bool(convert_alpha), bool(convert))

    raw = _RAW_IMAGE_CACHE.get(raw_key)
    if raw is None:
        surf = pygame.image.load(norm_path)

        # convert/convert_alpha ekran init'ine bağlı olabilir; hata olursa ham surface ile devam.
        if convert_alpha:
            try:
                surf = surf.convert_alpha()
            except Exception:
                pass
        elif convert:
            try:
                surf = surf.convert()
            except Exception:
                pass

        _RAW_IMAGE_CACHE.set(raw_key, surf)
        raw = surf

    if size is None:
        return raw

    scaled_key = (raw_key, int(size[0]), int(size[1]), bool(smoothscale))
    scaled = _SCALED_IMAGE_CACHE.get(scaled_key)
    if scaled is not None:
        return scaled

    # macOS: smoothscale bazen crash yapabiliyor
    if _IS_MACOS or not smoothscale:
        scaled = pygame.transform.scale(raw, size)
    else:
        try:
            scaled = pygame.transform.smoothscale(raw, size)
        except Exception:
            scaled = pygame.transform.scale(raw, size)

    _SCALED_IMAGE_CACHE.set(scaled_key, scaled)
    return scaled


def clear_image_cache() -> None:
    """Tüm image cache'lerini temizle."""
    _RAW_IMAGE_CACHE.clear()
    _SCALED_IMAGE_CACHE.clear()
