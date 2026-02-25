"""Preset avatar manifest and helpers."""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence


def _get_project_root() -> Path:
    """PyInstaller uyumlu proje kök dizini."""
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent


PROJECT_ROOT = _get_project_root()
PRIMARY_AVATAR_DIR = PROJECT_ROOT / 'avatars'
SECONDARY_AVATAR_DIR = PROJECT_ROOT / 'src' / 'avatars'
SUPPORTED_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.webp', '.bmp')
MAX_PRESET_COUNT = 30


@dataclass(frozen=True)
class AvatarPreset:
    key: str
    label: str
    path: Path


_PRESET_CACHE: List[AvatarPreset] = []
_PRESET_MAP: Dict[str, AvatarPreset] = {}
_CACHE_READY = False

FALLBACK_EMOJIS = [
    ('classic', 'Klasik', '👤'),
    ('smile', 'Mutlu', '😀'),
    ('cool', 'Havalı', '😎'),
    ('arcade', 'Arcade', '🎮'),
]


def _ensure_primary_dir() -> None:
    PRIMARY_AVATAR_DIR.mkdir(parents=True, exist_ok=True)


def _search_directories() -> List[Path]:
    _ensure_primary_dir()
    directories: List[Path] = []
    for candidate in (PRIMARY_AVATAR_DIR, SECONDARY_AVATAR_DIR):
        if candidate.exists():
            directories.append(candidate)
    if not directories:
        directories.append(PRIMARY_AVATAR_DIR)
    return directories


def _find_avatar_path(index: int, directories: Sequence[Path]) -> Optional[Path]:
    name_candidates = [f'avatar_{index}', f'avatar_{index:02d}', f'preset_{index:02d}']
    for directory in directories:
        for base_name in name_candidates:
            for ext in SUPPORTED_EXTENSIONS:
                candidate = directory / f'{base_name}{ext}'
                if candidate.exists():
                    return candidate.resolve()
    return None


def _load_presets() -> List[AvatarPreset]:
    directories = _search_directories()
    presets: List[AvatarPreset] = []
    for index in range(1, MAX_PRESET_COUNT + 1):
        avatar_path = _find_avatar_path(index, directories)
        if avatar_path:
            key = f'avatar_{index}'
            label = f'Avatar {index:02d}'
            presets.append(AvatarPreset(key, label, avatar_path))
    return presets


def refresh_avatar_cache() -> None:
    global _PRESET_CACHE, _PRESET_MAP, _CACHE_READY
    _PRESET_CACHE = _load_presets()
    _PRESET_MAP = {preset.key: preset for preset in _PRESET_CACHE}
    _CACHE_READY = True


def _ensure_cache() -> None:
    if not _CACHE_READY:
        refresh_avatar_cache()


def get_avatar_entries() -> List[Dict[str, Optional[str]]]:
    """Return metadata for available avatar presets."""
    _ensure_cache()
    if _PRESET_CACHE:
        return [
            {
                'key': preset.key,
                'label': preset.label,
                'value': f'preset:{preset.key}',
                'path': str(preset.path),
            }
            for preset in _PRESET_CACHE
        ]
    _PRESET_MAP.clear()
    fallback: List[Dict[str, Optional[str]]] = []
    for key, label, emoji in FALLBACK_EMOJIS:
        fallback.append({'key': key, 'label': label, 'value': emoji, 'path': None})
    return fallback


def resolve_avatar_value(value: Optional[str]) -> Optional[str]:
    """Translate stored avatar value to an absolute asset path when needed."""
    if not value:
        return None
    if value.startswith('preset:'):
        key = value.split(':', 1)[1]
        _ensure_cache()
        preset = _PRESET_MAP.get(key)
        if preset and preset.path.exists():
            return str(preset.path)
        return None
    return value


def get_avatar_label(value: Optional[str]) -> str:
    """Return the human friendly label for a stored avatar value."""
    if not value:
        return ''
    if value.startswith('preset:'):
        key = value.split(':', 1)[1]
        _ensure_cache()
        preset = _PRESET_MAP.get(key)
        if preset:
            return preset.label
    return ''


__all__ = [
    'AvatarPreset',
    'get_avatar_entries',
    'resolve_avatar_value',
    'get_avatar_label',
    'refresh_avatar_cache',
]
