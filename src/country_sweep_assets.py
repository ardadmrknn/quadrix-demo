"""Runtime registry for country-themed line-sweep assets.

The store catalogue and the gameplay sweep both share this single source
of truth so adding a new country only requires:

1. dropping ``flag.png`` + ``provenance.txt`` under
   ``assets/ui/line_sweep_countries/<theme_id>/`` (see
   ``tools/generate_country_sweep_assets.py``);
2. adding a ``CountryThemeSpec`` entry below.

Why a registry instead of per-country procedural draws?
    Procedural flags scale badly: each new country needs handcrafted
    polygon code and the result still feels homemade against the rest of
    the store. Asset-backed flags read as official, opaque, premium
    rectangles regardless of how many countries we add later.

Save compatibility:
    Cosmetic ``value`` strings in user profiles are stable. The four
    legacy values ``luna_usa``, ``luna_turkiye``, ``luna_russia``,
    ``luna_japan`` are preserved verbatim. New countries follow the same
    ``luna_<theme_id>`` shape.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import pygame


def _resource_path(relative_path: str) -> str:
    """Locate vendored assets when running from source or a frozen bundle.

    Mirrors ``sweep_effects._resource_path`` so we keep the same lookup
    behaviour for both modules without importing private helpers.
    """
    import sys

    base_path = getattr(
        sys,
        '_MEIPASS',
        os.path.abspath(os.path.join(os.path.dirname(__file__), '..')),
    )
    return os.path.join(base_path, relative_path)


# ---------------------------------------------------------------------------
# Spec
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CountryThemeSpec:
    """One row of the country-theme catalogue.

    Attributes
    ----------
    theme_id:
        Stable id used everywhere (registry key, alias, asset folder).
    cosmetic_value:
        Persisted value written into ``equipped_cosmetics['line_sweep_skin']``.
        Always ``f'luna_{theme_id}'`` for backward compatibility with
        existing user profiles.
    product_id:
        Store catalog id; same shape as the cosmetic value but with the
        ``sweep`` infix users have come to recognise.
    accent:
        UI accent colour for the store card border + CTA halo. Picked from
        the flag itself but tempered so it doesn't over-saturate the panel.
    title_key, desc_key:
        Localization keys used by the store screen.
    fallback_title, fallback_desc:
        Inline copy used when the localization table can't resolve the key
        (defensive default for tests and offline flows).
    aliases:
        Lower-case alias strings normalised to ``theme_id`` by
        ``normalize_line_sweep_theme``. Includes the legacy values that
        existing user profiles already reference.
    """

    theme_id: str
    cosmetic_value: str
    product_id: str
    accent: tuple[int, int, int]
    title_key: str
    desc_key: str
    fallback_title: str
    fallback_desc: str
    aliases: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# Catalogue
# ---------------------------------------------------------------------------


# Order in this tuple is the order users see in the store. Existing four
# stay first so an existing user's selection index does not shuffle.
COUNTRY_THEMES: tuple[CountryThemeSpec, ...] = (
    CountryThemeSpec(
        theme_id='usa',
        cosmetic_value='luna_usa',
        product_id='luna_sweep_usa',
        accent=(92, 158, 255),
        title_key='store_product_luna_sweep_usa_title',
        desc_key='store_product_luna_sweep_usa_desc',
        fallback_title='Luna-Cat ABD İzi',
        fallback_desc='Resmi yıldız ve şerit görünümünü temiz çizgilerle taşıyan koleksiyon izi.',
        aliases=('abd', 'us', 'united_states', 'united-states'),
    ),
    CountryThemeSpec(
        theme_id='turkiye',
        cosmetic_value='luna_turkiye',
        product_id='luna_sweep_turkiye',
        accent=(235, 86, 92),
        title_key='store_product_luna_sweep_turkiye_title',
        desc_key='store_product_luna_sweep_turkiye_desc',
        fallback_title='Luna-Cat Türkiye İzi',
        fallback_desc='Kırmızı bayrağı ve ay yıldız vurgusunu temiz çizgilerle taşıyan zarif koleksiyon izi.',
        aliases=('turkey', 'tr'),
    ),
    CountryThemeSpec(
        theme_id='russia',
        cosmetic_value='luna_russia',
        product_id='luna_sweep_russia',
        accent=(112, 156, 255),
        title_key='store_product_luna_sweep_russia_title',
        desc_key='store_product_luna_sweep_russia_desc',
        fallback_title='Luna-Cat Rusya İzi',
        fallback_desc='Beyaz, mavi ve kırmızı bantları temiz çizgilerle dengeleyen sakin bir koleksiyon izi.',
        aliases=('rusya', 'ru'),
    ),
    CountryThemeSpec(
        theme_id='japan',
        cosmetic_value='luna_japan',
        product_id='luna_sweep_japan',
        accent=(244, 119, 122),
        title_key='store_product_luna_sweep_japan_title',
        desc_key='store_product_luna_sweep_japan_desc',
        fallback_title='Luna-Cat Japonya İzi',
        fallback_desc='Beyaz zemini ve canlı kırmızı güneş diskini temiz çizgilerle taşıyan minimal iz.',
        aliases=('japonya', 'jp'),
    ),
    # ------------------------------------------------------------------
    # First wave of new additions
    # ------------------------------------------------------------------
    CountryThemeSpec(
        theme_id='china',
        cosmetic_value='luna_china',
        product_id='luna_sweep_china',
        accent=(238, 28, 37),
        title_key='store_product_luna_sweep_china_title',
        desc_key='store_product_luna_sweep_china_desc',
        fallback_title='Luna-Cat Çin İzi',
        fallback_desc='Derin kırmızı zemini ve altın yıldız düzenini temiz çizgilerle taşıyan koleksiyon izi.',
        aliases=('cn',),
    ),
    CountryThemeSpec(
        theme_id='germany',
        cosmetic_value='luna_germany',
        product_id='luna_sweep_germany',
        accent=(255, 196, 78),
        title_key='store_product_luna_sweep_germany_title',
        desc_key='store_product_luna_sweep_germany_desc',
        fallback_title='Luna-Cat Almanya İzi',
        fallback_desc='Siyah, kırmızı ve altın yatay bantları temiz çizgilerle taşıyan iz.',
        aliases=('almanya',),
    ),
    CountryThemeSpec(
        theme_id='france',
        cosmetic_value='luna_france',
        product_id='luna_sweep_france',
        accent=(98, 142, 235),
        title_key='store_product_luna_sweep_france_title',
        desc_key='store_product_luna_sweep_france_desc',
        fallback_title='Luna-Cat Fransa İzi',
        fallback_desc='Mavi, beyaz, kırmızı dikey bantları temiz çizgilerle taşıyan sakin koleksiyon izi.',
        aliases=('fransa',),
    ),
    CountryThemeSpec(
        theme_id='spain',
        cosmetic_value='luna_spain',
        product_id='luna_sweep_spain',
        accent=(255, 196, 78),
        title_key='store_product_luna_sweep_spain_title',
        desc_key='store_product_luna_sweep_spain_desc',
        fallback_title='Luna-Cat İspanya İzi',
        fallback_desc='Kırmızı ve altın bantları temiz çizgilerle taşıyan sıcak koleksiyon izi.',
        aliases=('ispanya',),
    ),
    CountryThemeSpec(
        theme_id='italy',
        cosmetic_value='luna_italy',
        product_id='luna_sweep_italy',
        accent=(116, 196, 134),
        title_key='store_product_luna_sweep_italy_title',
        desc_key='store_product_luna_sweep_italy_desc',
        fallback_title='Luna-Cat İtalya İzi',
        fallback_desc='Yeşil, beyaz ve kırmızı dikey bantları temiz çizgilerle taşıyan koleksiyon izi.',
        aliases=('italya', 'italya̱'),
    ),
    CountryThemeSpec(
        theme_id='brazil',
        cosmetic_value='luna_brazil',
        product_id='luna_sweep_brazil',
        accent=(98, 196, 132),
        title_key='store_product_luna_sweep_brazil_title',
        desc_key='store_product_luna_sweep_brazil_desc',
        fallback_title='Luna-Cat Brezilya İzi',
        fallback_desc='Yeşil zemini ve sarı eşkenar dörtgeni temiz çizgilerle taşıyan canlı koleksiyon izi.',
        aliases=('brezilya', 'br'),
    ),
    CountryThemeSpec(
        theme_id='south_korea',
        cosmetic_value='luna_south_korea',
        product_id='luna_sweep_south_korea',
        accent=(96, 144, 232),
        title_key='store_product_luna_sweep_south_korea_title',
        desc_key='store_product_luna_sweep_south_korea_desc',
        fallback_title='Luna-Cat Güney Kore İzi',
        fallback_desc='Beyaz zemini ve taeguk dairesini temiz çizgilerle taşıyan denge dolu iz.',
        aliases=('guney_kore', 'kore', 'korea'),
    ),
    CountryThemeSpec(
        theme_id='united_kingdom',
        cosmetic_value='luna_united_kingdom',
        product_id='luna_sweep_united_kingdom',
        accent=(120, 156, 235),
        title_key='store_product_luna_sweep_united_kingdom_title',
        desc_key='store_product_luna_sweep_united_kingdom_desc',
        fallback_title='Luna-Cat Birleşik Krallık İzi',
        fallback_desc='Union Flag\'in kırmızı, beyaz, mavi geometrisini temiz çizgilerle taşıyan iz.',
        aliases=('uk', 'birlesik_krallik', 'britain'),
    ),
    # ------------------------------------------------------------------
    # Second wave: most-visited store countries that still lacked a flag
    # (Singapore, Hong Kong, Viet Nam, Canada).
    # ------------------------------------------------------------------
    CountryThemeSpec(
        theme_id='singapore',
        cosmetic_value='luna_singapore',
        product_id='luna_sweep_singapore',
        accent=(235, 86, 92),
        title_key='store_product_luna_sweep_singapore_title',
        desc_key='store_product_luna_sweep_singapore_desc',
        fallback_title='Luna-Cat Singapur İzi',
        fallback_desc='Kırmızı-beyaz bandı, hilal ve beş yıldız vurgusunu temiz çizgilerle taşıyan koleksiyon izi.',
        aliases=('singapur', 'sg'),
    ),
    CountryThemeSpec(
        theme_id='hong_kong',
        cosmetic_value='luna_hong_kong',
        product_id='luna_sweep_hong_kong',
        accent=(238, 64, 72),
        title_key='store_product_luna_sweep_hong_kong_title',
        desc_key='store_product_luna_sweep_hong_kong_desc',
        fallback_title='Luna-Cat Hong Kong İzi',
        fallback_desc='Kırmızı zemini ve beyaz bauhinia çiçeğini temiz çizgilerle taşıyan koleksiyon izi.',
        aliases=('hongkong', 'hk'),
    ),
    CountryThemeSpec(
        theme_id='vietnam',
        cosmetic_value='luna_vietnam',
        product_id='luna_sweep_vietnam',
        accent=(238, 64, 72),
        title_key='store_product_luna_sweep_vietnam_title',
        desc_key='store_product_luna_sweep_vietnam_desc',
        fallback_title='Luna-Cat Vietnam İzi',
        fallback_desc='Kırmızı zemini ve altın yıldızı temiz çizgilerle taşıyan canlı koleksiyon izi.',
        aliases=('viet_nam', 'vietnam', 'vn'),
    ),
    CountryThemeSpec(
        theme_id='canada',
        cosmetic_value='luna_canada',
        product_id='luna_sweep_canada',
        accent=(238, 64, 72),
        title_key='store_product_luna_sweep_canada_title',
        desc_key='store_product_luna_sweep_canada_desc',
        fallback_title='Luna-Cat Kanada İzi',
        fallback_desc='Kırmızı-beyaz bandı ve akçaağaç yaprağı vurgusunu temiz çizgilerle taşıyan koleksiyon izi.',
        aliases=('kanada', 'ca'),
    ),
)


# Convenience map: theme_id -> spec.
_BY_THEME_ID: dict[str, CountryThemeSpec] = {spec.theme_id: spec for spec in COUNTRY_THEMES}


def list_country_themes() -> tuple[CountryThemeSpec, ...]:
    """Public ordered tuple of every catalogued country theme."""
    return COUNTRY_THEMES


def get_country_theme(theme_id: str) -> CountryThemeSpec | None:
    """Return the spec for ``theme_id`` (case-insensitive) or ``None``."""
    if not theme_id:
        return None
    return _BY_THEME_ID.get(str(theme_id).strip().lower())


# ---------------------------------------------------------------------------
# Alias map for normalisation
# ---------------------------------------------------------------------------


def country_theme_aliases() -> dict[str, str]:
    """Return alias -> theme_id mapping including theme ids themselves and
    their ``luna_*`` / ``luna_sweep_*`` historical forms.

    The returned dict is rebuilt each call but only on import-time of the
    sweep effects module, which is cheap relative to other init work and
    keeps tests free to mutate ``COUNTRY_THEMES`` if they ever need to.
    """
    aliases: dict[str, str] = {}
    for spec in COUNTRY_THEMES:
        aliases[spec.theme_id] = spec.theme_id
        # Historical persisted values used by existing user profiles.
        aliases[spec.cosmetic_value] = spec.theme_id            # luna_usa, luna_turkiye, ...
        aliases[spec.product_id] = spec.theme_id                # luna_sweep_usa, ...
        for alias in spec.aliases:
            aliases[alias.lower()] = spec.theme_id
    return aliases


# ---------------------------------------------------------------------------
# Surface cache
# ---------------------------------------------------------------------------


# (theme_id, kind, target_w, target_h) -> Surface
_surface_cache: dict[tuple[str, str, int, int], pygame.Surface] = {}
# (theme_id, kind) -> raw loaded Surface (None if asset is missing on disk).
_raw_cache: dict[tuple[str, str], pygame.Surface | None] = {}


def _asset_dir(theme_id: str) -> str:
    return _resource_path(os.path.join('assets', 'ui', 'line_sweep_countries', theme_id))


def _load_raw(theme_id: str, kind: str) -> pygame.Surface | None:
    """Load ``flag.png`` once and cache the surface.

    ``kind`` is ``'flag'``. Missing files are cached as ``None`` so we
    don't try to ``load`` again per frame.

    Format policy
    -------------
    * ``flag``: kept in **plain RGB** (no SRCALPHA). Flags are opaque on
      disk and we want them to fully cover the line-sweep band when
      blitted. Promoting them to SRCALPHA forces us into a numpy-backed
      alpha clamp later, which breaks on frozen macOS builds where
      ``numpy``/``pygame.surfarray`` are excluded from the bundle (the
      fallback ``pygame.Surface(size).blit(srcalpha_src)`` ends up with
      ``alpha=0`` in pixel storage on macOS, which then makes the band
      fully transparent after the border-radius mask multiply).
    """
    key = (theme_id, kind)
    if key in _raw_cache:
        return _raw_cache[key]

    path = os.path.join(_asset_dir(theme_id), f'{kind}.png')
    surface: pygame.Surface | None = None
    if os.path.exists(path):
        try:
            loaded = pygame.image.load(path)
            # Plain RGB copy. ``loaded`` already has no per-pixel alpha for
            # the bundled flag PNGs (they are saved as ``8-bit/color RGB``);
            # copying into a fresh RGB surface decouples us from the
            # display's pixel format and makes the result deterministic
            # across source runs and frozen macOS .app/Steam launches.
            rgb = pygame.Surface(loaded.get_size())
            rgb.blit(loaded, (0, 0))
            surface = rgb
        except Exception:
            surface = None
    _raw_cache[key] = surface
    return surface


def get_flag_aspect_ratio(theme_id: str) -> float | None:
    """Return the flag asset's natural width/height ratio, or ``None``.

    Used by the line-sweep so it can tile a *single*, un-stretched flag
    (sized to the band height with a proportional width) instead of
    distorting one copy across the whole band.
    """
    raw = _load_raw(theme_id, 'flag')
    if raw is None:
        return None
    width, height = raw.get_size()
    if height <= 0:
        return None
    return width / float(height)


def get_flag_surface(theme_id: str, target_w: int, target_h: int) -> pygame.Surface | None:
    """Return a scaled flag surface, cached by target size.

    The flag PNG is opaque (RGB on disk) and we keep it that way through
    the whole pipeline:

    * No SRCALPHA promotion → no numpy/surfarray dependency for an alpha
      clamp. This matters because the macOS PyInstaller spec excludes
      both ``numpy`` and ``pygame.surfarray`` to keep the bundle small,
      and the historical SRCALPHA-with-numpy-clamp path silently turned
      flags fully transparent on macOS frozen builds (band → mask
      multiply ended up multiplying by ``alpha=0``).
    * Blitting a plain RGB source onto a SRCALPHA band produces fully
      opaque pixels in the band — exactly what the line-sweep wants —
      so we don't need any post-processing here.
    """
    target_w = max(1, int(target_w))
    target_h = max(1, int(target_h))
    cache_key = (theme_id, 'flag', target_w, target_h)
    cached = _surface_cache.get(cache_key)
    if cached is not None:
        return cached

    raw = _load_raw(theme_id, 'flag')
    if raw is None:
        return None

    # ``smoothscale`` preserves the source's pixel format, but on
    # pygame-ce it can leave garbage in the unused alpha byte of a
    # 32-bit RGB surface (we observed 253-254 in macOS smoothscale
    # output). Converting the result to an explicit 24-bit display
    # format strips that byte cleanly and guarantees the SDL blitter
    # treats every pixel as fully opaque when blitted onto a SRCALPHA
    # band — without ever touching ``pygame.surfarray`` (which is
    # excluded from the macOS bundle).
    scaled = pygame.transform.smoothscale(raw, (target_w, target_h))
    try:
        scaled = scaled.convert(24)
    except pygame.error:
        # No display surface available (e.g. unit tests with SDL_VIDEODRIVER=dummy
        # mid-init). Falling back to the unconverted scaled RGB surface still
        # blits as fully opaque on every blitter we ship — alpha-byte garbage
        # only matters when surfarray inspects raw pixel storage, which we no
        # longer do.
        pass
    scaled.set_alpha(None)  # belt-and-suspenders: no per-surface alpha modulation
    _surface_cache[cache_key] = scaled
    return scaled


def clear_runtime_cache() -> None:
    """Drop every cached surface — used by tests that monkey-patch assets."""
    _surface_cache.clear()
    _raw_cache.clear()
