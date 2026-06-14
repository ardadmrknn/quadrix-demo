"""Runtime registry for store-backed block appearance cosmetics.

Block appearances are profile cosmetics, just like line-sweep trails or pets.
The equipped cosmetic value lives in ``equipped_cosmetics['block_skin']`` and
maps to a renderer appearance key understood by ``renderers.jelly_renderer``.
"""
from __future__ import annotations

from dataclasses import dataclass


BLOCK_SKIN_SLOT = 'block_skin'
DEFAULT_BLOCK_SKIN_VALUE = 'block_modern'

MODERN_BLOCK_APPEARANCE = 'modern_sharp'
LEGACY_BLOCK_APPEARANCE = 'legacy_jelly'


@dataclass(frozen=True)
class BlockSkinSpec:
    cosmetic_value: str
    appearance_key: str
    product_id: str
    accent: tuple[int, int, int]
    title_key: str
    desc_key: str
    fallback_title: str
    fallback_desc: str
    price: int
    aliases: tuple[str, ...] = ()


BLOCK_SKINS: tuple[BlockSkinSpec, ...] = (
    BlockSkinSpec(
        cosmetic_value=DEFAULT_BLOCK_SKIN_VALUE,
        appearance_key=MODERN_BLOCK_APPEARANCE,
        product_id='block_skin_modern',
        accent=(116, 214, 255),
        title_key='store_product_block_modern_title',
        desc_key='store_product_block_modern_desc',
        fallback_title='Yeni Blok Gorunumu',
        fallback_desc='Keskin koseli guncel blok gorunumu. Varsayilan stil budur.',
        price=0,
        aliases=(
            'modern',
            'default',
            MODERN_BLOCK_APPEARANCE,
        ),
    ),
    BlockSkinSpec(
        cosmetic_value='block_legacy_jelly',
        appearance_key=LEGACY_BLOCK_APPEARANCE,
        product_id='block_skin_legacy_jelly',
        accent=(255, 168, 108),
        title_key='store_product_block_legacy_title',
        desc_key='store_product_block_legacy_desc',
        fallback_title='Eski Blok Gorunumu',
        fallback_desc='Eski koseli, parlak ve bevel vurgulu klasik blok gorunumunu geri getirir.',
        price=450,
        aliases=(
            'legacy',
            'classic',
            'old',
            LEGACY_BLOCK_APPEARANCE,
        ),
    ),
)


_BY_VALUE: dict[str, BlockSkinSpec] = {spec.cosmetic_value.lower(): spec for spec in BLOCK_SKINS}
_BY_PRODUCT_ID: dict[str, BlockSkinSpec] = {spec.product_id.lower(): spec for spec in BLOCK_SKINS}
_BY_APPEARANCE: dict[str, BlockSkinSpec] = {spec.appearance_key.lower(): spec for spec in BLOCK_SKINS}


def list_block_skins() -> tuple[BlockSkinSpec, ...]:
    return BLOCK_SKINS


def block_skin_aliases() -> dict[str, str]:
    aliases: dict[str, str] = {}
    for spec in BLOCK_SKINS:
        aliases[spec.cosmetic_value.lower()] = spec.cosmetic_value
        aliases[spec.product_id.lower()] = spec.cosmetic_value
        aliases[spec.appearance_key.lower()] = spec.cosmetic_value
        for alias in spec.aliases:
            aliases[str(alias).lower()] = spec.cosmetic_value
    return aliases


def normalize_block_skin(value: str | None) -> str:
    key = str(value or '').strip().lower()
    if not key:
        return DEFAULT_BLOCK_SKIN_VALUE
    return block_skin_aliases().get(key, DEFAULT_BLOCK_SKIN_VALUE)


def get_block_skin(value: str | None) -> BlockSkinSpec:
    normalized = normalize_block_skin(value)
    return _BY_VALUE.get(normalized.lower(), BLOCK_SKINS[0])


def is_default_block_skin(value: str | None) -> bool:
    key = str(value or '').strip().lower()
    if not key:
        return False
    aliases = block_skin_aliases()
    resolved = aliases.get(key)
    return resolved == DEFAULT_BLOCK_SKIN_VALUE


def appearance_for_block_skin(value: str | None) -> str:
    spec = get_block_skin(value)
    return spec.appearance_key


def get_equipped_block_skin(user_manager=None, username=None, profile: dict | None = None) -> str:
    getter = getattr(user_manager, 'get_equipped_cosmetic', None) if user_manager is not None else None
    if callable(getter):
        try:
            value = getter(BLOCK_SKIN_SLOT, username=username)
        except TypeError:
            try:
                value = getter(BLOCK_SKIN_SLOT)
            except Exception:
                value = None
        except Exception:
            value = None
        return normalize_block_skin(value)

    if profile is None and user_manager is not None:
        profile_getter = getattr(user_manager, 'get_user_data', None)
        if callable(profile_getter):
            try:
                profile = profile_getter(username)
            except Exception:
                profile = None

    if isinstance(profile, dict):
        equipped = profile.get('equipped_cosmetics', {})
        if isinstance(equipped, dict):
            return normalize_block_skin(equipped.get(BLOCK_SKIN_SLOT))

    return DEFAULT_BLOCK_SKIN_VALUE


def get_equipped_block_appearance(user_manager=None, username=None, profile: dict | None = None) -> str:
    return appearance_for_block_skin(get_equipped_block_skin(user_manager, username=username, profile=profile))