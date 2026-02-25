"""Custom block colors and textures for tetrominoes."""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, Iterable, Optional, Tuple

import pygame

from asset_manager import load_image

BASE_PIECE_NAMES = ['I', 'O', 'T', 'S', 'Z', 'J', 'L']
EXTRA_PIECE_NAMES = ['Plus', 'Y', 'Domino', 'BigSquare']
ALL_PIECE_NAMES: Tuple[str, ...] = tuple(BASE_PIECE_NAMES + EXTRA_PIECE_NAMES)


@dataclass(slots=True)
class TextureSlice:
    """Stores relative coordinates for a textured cell inside a piece."""

    piece_name: str
    rel_x: int
    rel_y: int
    width: int
    height: int
    rotation: int = 0  # clockwise rotation steps (0-3)


class BlockStyleManager:
    """Loads/saves custom block colors and textures."""

    def __init__(self, settings_manager) -> None:
        self.settings_manager = settings_manager
        raw_styles = settings_manager.get('block_styles', {}) or {}
        self.styles: Dict[str, Dict[str, object]] = {}
        self.slice_settings: Dict[str, Dict[str, float]] = {}
        for name, data in raw_styles.items():
            if name not in ALL_PIECE_NAMES or not isinstance(data, dict):
                continue
            entry: Dict[str, object] = {}
            color = data.get('color')
            if isinstance(color, (list, tuple)) and len(color) == 3:
                entry['color'] = tuple(self._clamp_channel(c) for c in color)
            texture = data.get('texture')
            if isinstance(texture, str) and texture.strip():
                entry['texture'] = texture.strip()
            slice_box = data.get('slice')
            if isinstance(slice_box, dict):
                parsed = self._sanitize_slice(slice_box)
                if parsed:
                    self.slice_settings[name] = parsed
            if entry:
                self.styles[name] = entry
        self.texture_cache: Dict[str, Optional[pygame.Surface]] = {}

    # Public API -------------------------------------------------------------
    def iter_piece_names(self) -> Iterable[str]:
        return ALL_PIECE_NAMES

    def get_color(self, piece_name: str, fallback: Tuple[int, int, int]) -> Tuple[int, int, int]:
        entry = self.styles.get(piece_name)
        stored = entry.get('color') if entry else None
        return stored if stored else fallback

    def get_texture_path(self, piece_name: str) -> Optional[str]:
        entry = self.styles.get(piece_name)
        return entry.get('texture') if entry else None

    def get_texture_surface(self, piece_name: str) -> Optional[pygame.Surface]:
        path = self.get_texture_path(piece_name)
        if not path:
            return None
        cached = self.texture_cache.get(path)
        if cached is not None:
            return cached
        if not os.path.exists(path):
            self.texture_cache[path] = None
            return None
        try:
            surface = load_image(path, convert_alpha=True)
            self.texture_cache[path] = surface
            return surface
        except pygame.error as exc:  # pragma: no cover - pygame specific error path
            print(f"[BlockStyle] Texture load failed: {path} ({exc})")
            self.texture_cache[path] = None
            return None

    def get_slice_bounds(self, piece_name: str) -> Dict[str, float]:
        return self.slice_settings.get(piece_name, {'x': 0.0, 'y': 0.0, 'w': 1.0, 'h': 1.0}).copy()

    def set_slice_bounds(self, piece_name: str, bounds: Dict[str, float]) -> None:
        cleaned = self._sanitize_slice(bounds)
        if not cleaned:
            self.slice_settings.pop(piece_name, None)
        else:
            self.slice_settings[piece_name] = cleaned
        self._persist()

    def apply_to_piece(
        self,
        piece,
        fallback_color: Tuple[int, int, int],
        *,
        allow_color_override: bool = True,
    ) -> None:
        if not piece:
            return
        style_key = getattr(piece, 'style_key', None) or piece.name
        if allow_color_override:
            piece.color = self.get_color(style_key, fallback_color)
        else:
            piece.color = fallback_color
        texture_path = self.get_texture_path(style_key)
        piece.texture_path = texture_path
        surface = self.get_texture_surface(style_key) if texture_path else None
        piece.texture_surface_original = surface
        piece.texture_surface = surface

    def set_color(self, piece_name: str, color: Tuple[int, int, int]) -> None:
        color = tuple(self._clamp_channel(c) for c in color)
        entry = self.styles.setdefault(piece_name, {})
        entry['color'] = color
        self._persist()

    def reset_color(self, piece_name: str) -> None:
        entry = self.styles.get(piece_name)
        if entry and 'color' in entry:
            entry.pop('color')
            if not entry:
                self.styles.pop(piece_name, None)
            self._persist()

    def set_texture(self, piece_name: str, path: str) -> None:
        normalized = os.path.abspath(path)
        entry = self.styles.setdefault(piece_name, {})
        entry['texture'] = normalized
        self.texture_cache.pop(normalized, None)
        self.slice_settings.pop(piece_name, None)
        self._persist()

    def clear_texture(self, piece_name: str) -> None:
        entry = self.styles.get(piece_name)
        if entry and 'texture' in entry:
            removed = entry.pop('texture')
            self.texture_cache.pop(removed, None)
            if not entry:
                self.styles.pop(piece_name, None)
            self.slice_settings.pop(piece_name, None)
            self._persist()

    def reset_all(self) -> None:
        self.styles.clear()
        self.texture_cache.clear()
        self.slice_settings.clear()
        self._persist()

    def get_style_snapshot(self) -> Dict[str, Dict[str, Optional[object]]]:
        snapshot: Dict[str, Dict[str, Optional[object]]] = {}
        for name in ALL_PIECE_NAMES:
            entry = self.styles.get(name, {})
            snapshot[name] = {
                'color': entry.get('color'),
                'texture': entry.get('texture'),
                'slice': self.slice_settings.get(name),
            }
        return snapshot

    # Internal helpers ------------------------------------------------------
    def _persist(self) -> None:
        serializable = {}
        for name in set(list(self.styles.keys()) + list(self.slice_settings.keys())):
            entry = self.styles.get(name, {})
            payload: Dict[str, object] = {}
            if 'color' in entry:
                payload['color'] = list(entry['color'])
            if 'texture' in entry:
                payload['texture'] = entry['texture']
            slice_box = self.slice_settings.get(name)
            if slice_box:
                payload['slice'] = slice_box
            if payload:
                serializable[name] = payload
        self.settings_manager.set('block_styles', serializable)

    @staticmethod
    def _clamp_channel(value: object) -> int:
        try:
            return max(0, min(255, int(value)))
        except (TypeError, ValueError):  # pragma: no cover - defensive
            return 0

    @staticmethod
    def _sanitize_slice(data: Dict[str, object]) -> Dict[str, float]:
        try:
            x = float(data.get('x', 0.0))
            y = float(data.get('y', 0.0))
            w = float(data.get('w', 1.0))
            h = float(data.get('h', 1.0))
        except (TypeError, ValueError):
            return {}

        def clamp01(val):
            return max(0.0, min(1.0, val))

        x = clamp01(x)
        y = clamp01(y)
        w = clamp01(w)
        h = clamp01(h)
        w = max(0.01, min(1.0, w))
        h = max(0.01, min(1.0, h))
        if x + w > 1.0:
            x = max(0.0, 1.0 - w)
        if y + h > 1.0:
            y = max(0.0, 1.0 - h)
        return {'x': x, 'y': y, 'w': w, 'h': h}
