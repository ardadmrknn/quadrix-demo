"""Runtime registry for store "Evcil Hayvanlar" (Pets) sweep companions.

A pet replaces the walking Luna-Cat that escorts the line-sweep effect.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import pygame


def _resource_path(relative_path: str) -> str:
    """Locate vendored assets from source or a frozen bundle."""
    import sys

    base_path = getattr(
        sys,
        '_MEIPASS',
        os.path.abspath(os.path.join(os.path.dirname(__file__), '..')),
    )
    return os.path.join(base_path, relative_path)


@dataclass(frozen=True)
class PetSpec:
    """One row of the pet catalogue.

    Attributes
    ----------
    pet_id:
        Stable id used everywhere.
    cosmetic_value:
        Persisted value written into user profiles.
    product_id:
        Store catalogue id.
    accent:
        UI accent colour.
    title_key, desc_key:
        Localization keys.
    fallback_title, fallback_desc:
        Inline copy fallback.
    frame_count:
        Number of frame images.
    price:
        Store price.
    aliases:
        Lookup aliases.
    """

    pet_id: str
    cosmetic_value: str
    product_id: str
    accent: tuple[int, int, int]
    title_key: str
    desc_key: str
    fallback_title: str
    fallback_desc: str
    frame_count: int = 0
    price: int = 0
    size_multiplier: float = 1.0
    head_anchor_x: float = 0.86
    aliases: tuple[str, ...] = ()


# In demo, we make scuba_cat the default pet.
DEFAULT_PET_VALUE = 'pet_scuba_cat'

PET_SLOT = 'line_sweep_pet'


PETS: tuple[PetSpec, ...] = (
    PetSpec(
        pet_id='luna_cat',
        cosmetic_value='luna_cat',
        product_id='pet_luna_cat',
        accent=(255, 182, 96),
        title_key='store_product_pet_luna_cat_title',
        desc_key='store_product_pet_luna_cat_desc',
        fallback_title='Luna-Cat',
        fallback_desc='Satır temizleme izini takip eden klasik Luna-Cat dostun. Profilinle birlikte gelir.',
        frame_count=0,
        price=1800,
        aliases=('cat', 'lunacat'),
    ),
    PetSpec(
        pet_id='sheep',
        cosmetic_value='pet_sheep',
        product_id='pet_sheep',
        accent=(120, 170, 235),
        title_key='store_product_pet_sheep_title',
        desc_key='store_product_pet_sheep_desc',
        fallback_title='Sevimli Kuzu',
        fallback_desc='Satır temizlerken zıplayarak izini takip eden mavi yeleli minik kuzu. Luna-Cat\'in yerine geçer.',
        frame_count=10,
        price=4200,
        size_multiplier=1.30,
        head_anchor_x=0.70,
        aliases=('kuzu', 'lamb', 'koyun'),
    ),
    PetSpec(
        pet_id='scuba_cat',
        cosmetic_value=DEFAULT_PET_VALUE,
        product_id='pet_scuba_cat',
        accent=(50, 150, 250),
        title_key='store_product_pet_scuba_cat_title',
        desc_key='store_product_pet_scuba_cat_desc',
        fallback_title='Scuba Cat',
        fallback_desc='Dalış takımlarıyla satırları temizleyen efsanevi dalgıç kedi. Luna-Cat\'in yerine geçer.',
        frame_count=34,
        price=0,
        size_multiplier=1.50,
        head_anchor_x=0.45,
        aliases=('scuba', 'scubacat', 'dalgic', 'dalisci', 'default'),
    ),
)


_BY_PET_ID: dict[str, PetSpec] = {spec.pet_id.lower(): spec for spec in PETS}
_BY_VALUE: dict[str, PetSpec] = {spec.cosmetic_value.lower(): spec for spec in PETS}


def list_pets() -> tuple[PetSpec, ...]:
    """Ordered tuple of pet specs for catalogue assembly."""
    return PETS


def get_pet(value_or_id: str | None) -> PetSpec | None:
    """Return the spec matching a cosmetic value, pet id or alias (or ``None``)."""
    key = str(value_or_id or '').strip().lower()
    if not key:
        return None
    spec = _BY_VALUE.get(key) or _BY_PET_ID.get(key)
    if spec is not None:
        return spec
    normalized = pet_aliases().get(key)
    if normalized:
        return _BY_VALUE.get(normalized)
    return None


def pet_aliases() -> dict[str, str]:
    """alias -> cosmetic_value mapping (ids, values and explicit aliases)."""
    aliases: dict[str, str] = {}
    for spec in PETS:
        aliases[spec.cosmetic_value.lower()] = spec.cosmetic_value
        aliases[spec.pet_id.lower()] = spec.cosmetic_value
        aliases[spec.product_id.lower()] = spec.cosmetic_value
        for alias in spec.aliases:
            aliases[alias.lower()] = spec.cosmetic_value
    return aliases


def normalize_pet(value: str | None) -> str:
    """Normalise a persisted/arbitrary value to a known cosmetic value."""
    key = str(value or '').strip().lower()
    return pet_aliases().get(key, DEFAULT_PET_VALUE)


def is_default_pet(value: str | None) -> bool:
    """True if ``value`` resolves to the built-in Luna-Cat companion."""
    # Built-in Luna-Cat has no animation frames, so it must be processed procedurally.
    key = str(value or '').strip().lower()
    return key in ('luna_cat', 'cat', 'lunacat')


_frames_cache: dict[str, list[pygame.Surface] | None] = {}


def load_pet_frames(value: str | None) -> list[pygame.Surface] | None:
    """Return the registered animation frames for a pet, or ``None``."""
    normalized = normalize_pet(value)
    if normalized in _frames_cache:
        return _frames_cache[normalized]

    spec = _BY_VALUE.get(normalized)
    if spec is None or spec.frame_count <= 0:
        _frames_cache[normalized] = None
        return None

    frames: list[pygame.Surface] = []
    asset_dir = _resource_path(os.path.join('assets', 'ui', 'pets', spec.pet_id))
    for index in range(spec.frame_count):
        path = os.path.join(asset_dir, f'frame_{index:02d}.png')
        if not os.path.exists(path):
            continue
        try:
            surface = pygame.image.load(path).convert_alpha()
        except Exception:
            continue
        if surface.get_width() > 0 and surface.get_height() > 0:
            frames.append(surface)

    result = frames if frames else None
    _frames_cache[normalized] = result
    return result


def clear_runtime_cache() -> None:
    """Drop cached surfaces (used by tests that swap the display surface)."""
    _frames_cache.clear()
