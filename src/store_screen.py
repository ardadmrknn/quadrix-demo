from __future__ import annotations

from dataclasses import dataclass
import importlib
import sys

import pygame

try:
    from .block_skin_assets import (  # type: ignore
        BLOCK_SKIN_SLOT as _BLOCK_SKIN_SLOT,
        DEFAULT_BLOCK_SKIN_VALUE as _DEFAULT_BLOCK_SKIN_VALUE,
        appearance_for_block_skin as _appearance_for_block_skin,
        is_default_block_skin as _is_default_block_skin,
        list_block_skins as _list_block_skins,
    )
    from .localization import t  # type: ignore
    from .platform_utils import normalize_mouse_pos, get_mouse_pos  # type: ignore
    from .renderers.jelly_renderer import draw_jelly_block  # type: ignore
    from .retro_style import retro_style  # type: ignore
    from .ui_scaling import get_projected_effective_scale  # type: ignore
    from .back_button import draw_back_button as _draw_shared_back_button  # type: ignore
except Exception:
    from block_skin_assets import (
        BLOCK_SKIN_SLOT as _BLOCK_SKIN_SLOT,
        DEFAULT_BLOCK_SKIN_VALUE as _DEFAULT_BLOCK_SKIN_VALUE,
        appearance_for_block_skin as _appearance_for_block_skin,
        is_default_block_skin as _is_default_block_skin,
        list_block_skins as _list_block_skins,
    )
    from localization import t
    from platform_utils import normalize_mouse_pos, get_mouse_pos
    from renderers.jelly_renderer import draw_jelly_block
    from retro_style import retro_style
    from ui_scaling import get_projected_effective_scale
    from back_button import draw_back_button as _draw_shared_back_button

try:
    try:
        from .sweep_effects import SweepCatState, draw_line_sweep_band  # type: ignore
    except Exception:
        from sweep_effects import SweepCatState, draw_line_sweep_band  # type: ignore
except Exception:
    try:
        from .sweep_effects import SweepCatState  # type: ignore
    except Exception:
        from sweep_effects import SweepCatState  # type: ignore

    def draw_line_sweep_band(*args, **kwargs):
        return None

try:
    try:
        from .country_sweep_assets import (  # type: ignore
            list_country_themes as _list_country_themes,
        )
    except Exception:
        from country_sweep_assets import (  # type: ignore
            list_country_themes as _list_country_themes,
        )
except Exception:
    def _list_country_themes():
        return []


try:
    try:
        from .pet_assets import (  # type: ignore
            DEFAULT_PET_VALUE as _DEFAULT_PET_VALUE,
            PET_SLOT as _PET_SLOT,
            list_pets as _list_pets,
        )
    except Exception:
        from pet_assets import (  # type: ignore
            DEFAULT_PET_VALUE as _DEFAULT_PET_VALUE,
            PET_SLOT as _PET_SLOT,
            list_pets as _list_pets,
        )
except Exception:
    _DEFAULT_PET_VALUE = 'luna_cat'
    _PET_SLOT = 'line_sweep_pet'

    def _list_pets():
        return []


def _background_effects_module():
    """Resolve the live background_effects module.

    Test isolation sometimes reloads ``background_effects`` while keeping this
    module cached. Looking it up lazily keeps StoreScreen bound to the current
    shared-layer singleton instead of a stale module instance.
    """
    cached = sys.modules.get('background_effects')
    if cached is not None:
        return cached
    cached = sys.modules.get('src.background_effects')
    if cached is not None:
        return cached
    try:
        return importlib.import_module('background_effects')
    except Exception:
        if __package__:
            return importlib.import_module('.background_effects', __package__)
        raise


def _get_shared_falling_blocks_layer(name: str = 'default', **kwargs):
    return _background_effects_module().get_shared_falling_blocks_layer(name, **kwargs)


def _sync_shared_falling_blocks_appearance(*args, **kwargs):
    return _background_effects_module().sync_shared_falling_blocks_appearance(*args, **kwargs)

# Mystery (Kart Ustalığı) kart mağaza meta verisi — tek kaynak
# (game_modes_extra.CARD_UPGRADE_FAMILIES / CARD_SINGLE_TIER_LOCKED). Mağaza
# kart ürünleri buradan türetilir. Heavily stubbed test ortamlarında modül
# yoksa kart kategorileri sessizce boş kalır (kozmetik mağaza bozulmaz).
try:
    try:
        from .game_modes_extra import (  # type: ignore
            get_store_card_families as _get_store_card_families,
            get_card_family_max_tier as _get_card_family_max_tier,
            get_card_upgrade_price as _get_card_upgrade_price,
            get_card_tier_rarity as _get_card_tier_rarity,
            get_card_title as _get_card_title,
            get_card_description as _get_card_description,
        )
    except Exception:
        from game_modes_extra import (  # type: ignore
            get_store_card_families as _get_store_card_families,
            get_card_family_max_tier as _get_card_family_max_tier,
            get_card_upgrade_price as _get_card_upgrade_price,
            get_card_tier_rarity as _get_card_tier_rarity,
            get_card_title as _get_card_title,
            get_card_description as _get_card_description,
        )
except Exception:  # pragma: no cover - stubbed test envs without pygame Game
    _get_store_card_families = None  # type: ignore
    _get_card_family_max_tier = None  # type: ignore
    _get_card_upgrade_price = None  # type: ignore
    _get_card_tier_rarity = None  # type: ignore
    _get_card_title = None  # type: ignore
    _get_card_description = None  # type: ignore

# Gamepad button-glyph helpers for the tab-bar controller hints. These are
# optional: in heavily stubbed test environments the modules may be absent,
# so we degrade to a plain keyboard hint rather than failing the store import.
try:
    try:
        from .promptfont_support import render_button_index_prompt_surface as _render_button_glyph  # type: ignore
        from .gamepad_manager import is_gamepad_connected as _is_gamepad_connected  # type: ignore
    except Exception:
        from promptfont_support import render_button_index_prompt_surface as _render_button_glyph  # type: ignore
        from gamepad_manager import is_gamepad_connected as _is_gamepad_connected  # type: ignore
except Exception:  # pragma: no cover - exercised only in stubbed test envs
    _render_button_glyph = None  # type: ignore

    def _is_gamepad_connected() -> bool:  # type: ignore
        return False


@dataclass(frozen=True)
class StoreProduct:
    product_id: str
    title_key: str | None
    desc_key: str | None
    category_key: str | None
    badge_key: str | None
    status_key: str | None
    price: int
    accent: tuple[int, int, int]
    preview_theme: str = 'rainbow'
    cosmetic_payload: dict[str, str] | None = None
    fallback_title: str = ''
    fallback_desc: str = ''
    fallback_category: str = ''
    fallback_badge: str = ''
    fallback_status: str = ''
    # ``True`` for traces added after the original launch line-up. Drives the
    # data-driven "Yeni" badge and the "New" category page. This is observed
    # from the registry (any non-legacy country), never a hand-curated flag,
    # so newly registered countries surface automatically without a second
    # edit drifting out of sync.
    is_new: bool = False
    # ``True`` for pet companions (Evcil Hayvanlar). Drives the Pets category
    # page and tells the preview to render the pet sprite instead of the cat.
    is_pet: bool = False
    # ``True`` for block appearance cosmetics shown under the "Bloklar" tab.
    is_block_skin: bool = False
    # Mystery kart ürünleri için payload. None ise bu ürün kozmetik bir üründür.
    # Şekil: {'type': 'card'|'card_upgrade', 'value': '<aile_id>'}.
    # ``card_family`` aile id'sini ayrıca taşır (filtre/ownership için kestirme).
    card_payload: dict[str, str] | None = None
    card_family: str | None = None
    # Kart ürününün K1 ikon dosya yolu (önizleme için). Kozmetiklerde None.
    card_icon: str | None = None


CATALOG_LINE_SWEEP_PRICE = 350

# Product ids that shipped in the original store line-up. Everything else in
# the country registry is treated as a "new arrival" for badge + category
# purposes. Kept as a frozenset so membership checks are O(1) and the legacy
# anchor list can't be mutated accidentally.
_LEGACY_PRODUCT_IDS = frozenset(
    {
        'luna_sweep_rainbow',
        'luna_sweep_usa',
        'luna_sweep_turkiye',
        'luna_sweep_russia',
        'luna_sweep_japan',
    }
)


def _build_catalog() -> tuple['StoreProduct', ...]:
    """Compose the visible store catalogue.

    The first product is the included rainbow trace, followed by every
    country theme registered in :mod:`country_sweep_assets`. Pulling the
    countries from the registry keeps adding a new flag to a single edit
    in the registry instead of two parallel lists drifting out of sync.
    Existing user profiles continue to round-trip because the registry's
    ``cosmetic_value`` and ``product_id`` strings are stable historical
    identifiers (`luna_usa`, `luna_sweep_usa`, ...).
    """
    catalog: list[StoreProduct] = [
        StoreProduct(
            product_id='luna_sweep_rainbow',
            title_key='store_product_luna_sweep_rainbow_title',
            desc_key='store_product_luna_sweep_rainbow_desc',
            category_key='store_category_line_sweep',
            badge_key='store_badge_featured',
            status_key='store_default_label',
            price=250,
            accent=(255, 182, 96),
            preview_theme='rainbow',
            cosmetic_payload={'type': 'line_sweep_skin', 'value': 'luna_rainbow'},
            fallback_title='Luna-Cat Gökkuşağı İzi',
            fallback_desc='Profilinle birlikte gelen imza Luna-Cat izi. Parlak renk geçişleriyle ilk andan itibaren kullanıma hazırdır.',
            fallback_category='Satır Temizleme İzi',
            fallback_badge='Varsayılan',
            fallback_status='Varsayılan',
        )
    ]
    for spec in _list_country_themes():
        is_new = spec.product_id not in _LEGACY_PRODUCT_IDS
        catalog.append(
            StoreProduct(
                product_id=spec.product_id,
                title_key=spec.title_key,
                desc_key=spec.desc_key,
                category_key='store_category_line_sweep',
                badge_key='store_badge_new' if is_new else 'store_badge_curated',
                status_key='store_status_available',
                price=CATALOG_LINE_SWEEP_PRICE,
                accent=spec.accent,
                preview_theme=spec.theme_id,
                cosmetic_payload={'type': 'line_sweep_skin', 'value': spec.cosmetic_value},
                fallback_title=spec.fallback_title,
                fallback_desc=spec.fallback_desc,
                fallback_category='Satır Temizleme İzi',
                fallback_badge='Yeni' if is_new else 'Koleksiyon',
                fallback_status='Alınabilir',
                is_new=is_new,
            )
        )
    # Pet companions (Evcil Hayvanlar). These swap the walking Luna-Cat for an
    # animated pet during the line-sweep, using the dedicated ``line_sweep_pet``
    # cosmetic slot. The default Luna-Cat (price 0) anchors the page as the
    # baseline companion, mirroring how the rainbow trace anchors the traces.
    for pet in _list_pets():
        is_default = pet.cosmetic_value == _DEFAULT_PET_VALUE
        catalog.append(
            StoreProduct(
                product_id=pet.product_id,
                title_key=pet.title_key,
                desc_key=pet.desc_key,
                category_key='store_category_pets',
                badge_key='store_default_label' if is_default else 'store_badge_new',
                status_key='store_default_label' if is_default else 'store_status_available',
                price=pet.price,
                accent=pet.accent,
                preview_theme='rainbow',
                cosmetic_payload={'type': _PET_SLOT, 'value': pet.cosmetic_value},
                fallback_title=pet.fallback_title,
                fallback_desc=pet.fallback_desc,
                fallback_category='Evcil Hayvanlar',
                fallback_badge='Varsayılan' if is_default else 'Yeni',
                fallback_status='Varsayılan' if is_default else 'Alınabilir',
                is_new=not is_default,
                is_pet=True,
            )
        )
    for block_skin in _list_block_skins():
        is_default = _is_default_block_skin(block_skin.cosmetic_value)
        catalog.append(
            StoreProduct(
                product_id=block_skin.product_id,
                title_key=block_skin.title_key,
                desc_key=block_skin.desc_key,
                category_key='store_category_blocks',
                badge_key='store_default_label' if is_default else 'store_badge_curated',
                status_key='store_default_label' if is_default else 'store_status_available',
                price=block_skin.price,
                accent=block_skin.accent,
                preview_theme='rainbow',
                cosmetic_payload={'type': _BLOCK_SKIN_SLOT, 'value': block_skin.cosmetic_value},
                fallback_title=block_skin.fallback_title,
                fallback_desc=block_skin.fallback_desc,
                fallback_category='Bloklar',
                fallback_badge='Varsayilan' if is_default else 'Klasik',
                fallback_status='Varsayilan' if is_default else 'Alinabilir',
                is_block_skin=True,
            )
        )
    catalog.extend(_build_card_products())
    return tuple(catalog)


# Enderlik -> vurgu rengi (kart ürün kartları için).
_CARD_RARITY_ACCENTS: dict[str, tuple[int, int, int]] = {
    'common': (170, 190, 210),
    'uncommon': (120, 220, 150),
    'rare': (90, 170, 255),
    'epic': (200, 120, 255),
    'legendary': (255, 200, 80),
}


def _build_card_products() -> list['StoreProduct']:
    """Mystery kart ürünlerini tek-kaynak meta veriden türet.

    Her geliştirilebilir/kilitli aile için TEK bir ürün üretilir. Ürünün
    "satın alma mı geliştirme mi" olduğu sahipliğe göre çalışma anında
    belirlenir (kategori filtresi + CTA). Bu yüzden product_id sabittir ve
    save-compat invariantını bozmaz (ürün listesi yeniden sıralanmaz).
    """
    if _get_store_card_families is None:
        return []
    products: list[StoreProduct] = []
    try:
        families = _get_store_card_families()
    except Exception:
        return []
    for fam in families:
        family_id = str(fam.get('family_id') or '')
        if not family_id:
            continue
        base_rarity = str(fam.get('base_rarity') or 'common')
        accent = _CARD_RARITY_ACCENTS.get(base_rarity, (170, 190, 210))
        purchase_price = int(fam.get('purchase_price') or 0)
        icon_path = fam.get('icon_image')
        products.append(
            StoreProduct(
                product_id=f'card_{family_id}',
                title_key=None,            # Kart başlığı _group_id'den çözülür (resolve runtime).
                desc_key=None,
                category_key='store_category_cards',
                badge_key=None,
                status_key=None,
                price=purchase_price,
                accent=accent,
                preview_theme='rainbow',
                cosmetic_payload=None,
                card_payload={'type': 'card', 'value': family_id},
                card_family=family_id,
                card_icon=icon_path,
                fallback_title=family_id,
                fallback_desc='',
                fallback_category='Kartlar',
                fallback_badge='Kart',
                fallback_status='Alınabilir',
            )
        )
    return products


CATALOG: tuple[StoreProduct, ...] = _build_catalog()


# Store category pages. Each entry is an honest VIEW over the unchanged
# ``self.products`` list — categories never reorder or hide the canonical
# catalogue, they only filter which products a page shows. The first/default
# page is the full catalogue so the spotlight + keyboard navigation behave
# exactly like the historical single-page store (and the behavioural tests
# that anchor on it). ``loc_key`` reuses existing localization keys wherever
# possible to avoid duplicate strings.
STORE_CATEGORY_DEFS: tuple[dict[str, str], ...] = (
    {'key': 'featured', 'loc_key': 'store_featured_title', 'fallback': 'Öne Çıkanlar'},
    {'key': 'traces', 'loc_key': 'store_category_traces', 'fallback': 'İzler'},
    {'key': 'pets', 'loc_key': 'store_category_pets', 'fallback': 'Evcil Hayvanlar'},
    {'key': 'blocks', 'loc_key': 'store_category_blocks', 'fallback': 'Bloklar'},
    {'key': 'cards', 'loc_key': 'store_category_cards', 'fallback': 'Kartlar'},
    {'key': 'card_upgrades', 'loc_key': 'store_category_card_upgrades', 'fallback': 'Kartları Geliştir'},
    {'key': 'owned', 'loc_key': 'store_my_collection', 'fallback': 'Koleksiyonum'},
)

# Duration of the cross-page fade/slide and the sliding-underline glide, in
# milliseconds. Kept short so paging feels snappy, not floaty — in line with
# the game's restrained neon-on-dark motion language.
_TAB_TRANSITION_MS = 180


class StoreScreen:
    def __init__(self, screen, user_manager=None, settings_manager=None):
        self.screen = screen
        self.user_manager = user_manager
        self.settings_manager = settings_manager
        self.products = list(CATALOG)
        self.selected_index = 0
        # Category page state. The store is a single catalogue rendered through
        # category "pages": each page filters the *visible* products without
        # touching ``self.products`` (save-compat invariant). ``active_category``
        # indexes ``STORE_CATEGORY_DEFS``; ``featured`` (page 0) shows the full
        # ordered catalogue so the historical navigation behaviour is preserved.
        self.categories = list(STORE_CATEGORY_DEFS)
        self.active_category = 0
        # Visible -> absolute product index map for the active page, rebuilt
        # every frame in draw(). Lets the grid render a filtered subset while
        # selection/CTA keep operating on absolute ``self.products`` indices.
        self._visible_indices: list[int] = list(range(len(self.products)))
        # Tab hit-zones (rebuilt each frame) for mouse clicks on the tab bar.
        self._tab_rects: list[pygame.Rect] = []
        # Prev/next page arrow affordances at the ends of the tab bar. Rebuilt
        # every frame in draw(); checked in the mouse handler AFTER the back
        # button but BEFORE tabs/CTA/cards so an arrow click only pages and
        # never triggers a purchase/equip.
        self._tab_prev_arrow_rect: pygame.Rect | None = None
        self._tab_next_arrow_rect: pygame.Rect | None = None
        # Sliding-underline animation state. We store the underline's current
        # x/width in *logical screen* coordinates and lerp them toward the
        # active tab's target every frame (time-driven via pygame.time). No
        # per-frame surface allocation beyond the tiny underline strip.
        self._tab_underline_x: float | None = None
        self._tab_underline_w: float | None = None
        # Short cross-page fade. ``_tab_switch_ms`` is the tick timestamp of the
        # last category change; the body content fades/slides in over
        # ``_TAB_TRANSITION_MS`` after it. Pure scalar bookkeeping.
        self._tab_switch_ms: int = 0
        self.card_rects: list[pygame.Rect] = []
        self.mouse_pos = (0, 0)
        self.grid_scroll = 0
        self.max_grid_scroll = 0
        self._last_columns = 1
        self._last_card_height = 0
        self._last_row_step = 0
        self._last_grid_viewport = pygame.Rect(0, 0, 0, 0)
        self._draw_scale = 1.0
        self._sweep_cat_state = SweepCatState()
        self.background_fx = _get_shared_falling_blocks_layer('default')
        # Hero CTA hit-zone - rebuilt every frame; enables click on the action button.
        self._cta_rect: pygame.Rect | None = None
        # Back affordance for mouse users. ESC/BACKSPACE keep working;
        # this rect is rebuilt every frame in draw() so layout follows the
        # current window size. Hit-zone is checked before any card or CTA
        # collision so it never bypasses the existing buy/equip flow.
        self._back_rect: pygame.Rect | None = None
        self._back_hover: bool = False
        # Footer layout decision recorded each frame so tests and other helpers
        # can observe it without re-deriving the breakpoint.
        self._footer_two_row: bool = False
        # Purchase-confirmation modal. ``None`` when closed; otherwise the
        # absolute product index awaiting confirmation. Buying a trace/pet now
        # routes through this dialog (ENTER/CTA open it; it shows name + price
        # and a Confirm/Cancel choice) so a click or keypress can never spend
        # currency without an explicit, informed confirmation step.
        self._confirm_index: int | None = None
        # Modal button hit-zones, rebuilt every frame the modal is drawn.
        self._confirm_yes_rect: pygame.Rect | None = None
        self._confirm_no_rect: pygame.Rect | None = None
        self.status_message = t(
            'store_preview_notice',
            default="Mağaza açık. Kozmetikleri Lunar ile satın alıp hemen kullanabilirsin.",
        )
        if self.background_fx is not None:
            try:
                _sync_shared_falling_blocks_appearance(self.user_manager, username=self._get_current_username())
            except Exception:
                pass

    def get_product_ids(self) -> list[str]:
        return [product.product_id for product in self.products]

    def get_selected_product(self) -> StoreProduct:
        return self.products[self.selected_index]

    def get_active_category_key(self) -> str:
        """Key of the currently active category page (see STORE_CATEGORY_DEFS)."""
        if not self.categories:
            return 'featured'
        index = max(0, min(self.active_category, len(self.categories) - 1))
        return str(self.categories[index].get('key', 'featured'))

    def _category_label(self, category: dict) -> str:
        """Localized label for a category tab, falling back to its inline text."""
        loc_key = category.get('loc_key')
        fallback = category.get('fallback', '')
        if loc_key:
            return t(loc_key, default=fallback)
        return fallback

    def _product_matches_category(self, index: int, category_key: str) -> bool:
        """Decide whether product ``index`` belongs on the given category page.

        This is a pure view filter — it never mutates ``self.products`` or the
        product ordering, so save-compat and the catalogue invariants hold.
        """
        try:
            product = self.products[index]
        except IndexError:
            return False

        is_card = self._is_card_product(product)
        is_block_skin = self._is_block_skin_product(product)

        if category_key == 'featured':
            # Öne çıkanlar yalnızca kozmetikleri gösterir; kartların kendi
            # sekmeleri (cards / card_upgrades) vardır. Açılış sayfası kart
            # kalabalığına dönüşmesin (UX).
            return not is_card
        if category_key == 'traces':
            # All line-sweep traces (rainbow + country flags), i.e. the
            # non-pet cosmetics that ride along the cleared rows. Kart değil.
            return (not is_card) and (not bool(getattr(product, 'is_pet', False))) and (not is_block_skin)
        if category_key == 'pets':
            return (not is_card) and bool(getattr(product, 'is_pet', False))
        if category_key == 'blocks':
            return (not is_card) and is_block_skin
        if category_key == 'cards':
            # Satın alınabilir, henüz sahip OLUNMAYAN kartlar.
            if not is_card:
                return False
            return not self._card_is_owned(product)
        if category_key == 'card_upgrades':
            # Sahip OLUNAN ve bir üst kademesi olan kartlar.
            if not is_card:
                return False
            if not self._card_is_owned(product):
                return False
            return self._card_current_tier(product) < self._card_max_tier(product)
        if category_key == 'owned':
            # Yalnızca kozmetik koleksiyonu: bought, equipped, veya bundled
            # rainbow default. Kartlar burada GÖSTERİLMEZ (kendi sekmeleri var).
            if is_card:
                return False
            return self._resolve_ownership_state(product) in ('owned', 'equipped', 'demo')
        return True

    def _compute_visible_indices(self, category_key: str | None = None) -> list[int]:
        """Absolute product indices visible on the active (or given) page."""
        key = category_key or self.get_active_category_key()
        return [i for i in range(len(self.products)) if self._product_matches_category(i, key)]

    # ── Kart ürünü yardımcıları ───────────────────────────────────

    def _is_card_product(self, product) -> bool:
        """Ürün bir Mystery kart ürünü mü (kozmetik değil)?"""
        return bool(getattr(product, 'card_payload', None)) and bool(getattr(product, 'card_family', None))

    def _is_block_skin_product(self, product) -> bool:
        payload = getattr(product, 'cosmetic_payload', None) or {}
        return str(payload.get('type') or '') == _BLOCK_SKIN_SLOT or bool(getattr(product, 'is_block_skin', False))

    def _card_family_of(self, product) -> str:
        return str(getattr(product, 'card_family', '') or '')

    def _card_is_owned(self, product) -> bool:
        """Oyuncu bu kart ailesine sahip mi? (common-start: ücretsiz açık)."""
        family = self._card_family_of(product)
        if not family:
            return False
        um = self.user_manager
        owns = getattr(um, 'owns_card', None) if um is not None else None
        if not callable(owns):
            return False
        username = self._get_current_username()
        try:
            return bool(owns(family, username=username))
        except TypeError:
            try:
                return bool(owns(family))
            except Exception:
                return False
        except Exception:
            return False

    def _card_current_tier(self, product) -> int:
        family = self._card_family_of(product)
        if not family:
            return 0
        um = self.user_manager
        getter = getattr(um, 'get_card_tier', None) if um is not None else None
        if not callable(getter):
            return 0
        username = self._get_current_username()
        try:
            return int(getter(family, username=username) or 0)
        except TypeError:
            try:
                return int(getter(family) or 0)
            except Exception:
                return 0
        except Exception:
            return 0

    def _card_max_tier(self, product) -> int:
        family = self._card_family_of(product)
        if not family or _get_card_family_max_tier is None:
            return 1
        try:
            return int(_get_card_family_max_tier(family) or 1)
        except Exception:
            return 1

    def _card_current_rarity(self, product) -> str:
        """Kartın O ANKİ kademesinin enderliği.

        Sahip değilse base (K1) enderlik; sahipse mevcut tier'ın enderliği.
        Renk eşleşmesine DEĞİL, gerçek tier→rarity verisine dayanır.
        """
        family = self._card_family_of(product)
        if not family or _get_card_tier_rarity is None:
            return ''
        tier = self._card_current_tier(product)
        if tier <= 0:
            tier = 1  # sahip değilse K1 enderliğini göster
        return str(_get_card_tier_rarity(family, tier) or '')

    def _card_next_rarity(self, product) -> str:
        """Geliştirilince ulaşılacak (tier+1) enderlik. Tavandaysa ''."""
        family = self._card_family_of(product)
        if not family or _get_card_tier_rarity is None:
            return ''
        tier = self._card_current_tier(product)
        if tier <= 0:
            tier = 1
        if tier >= self._card_max_tier(product):
            return ''
        return str(_get_card_tier_rarity(family, tier + 1) or '')

    def _card_effective_price(self, product) -> int:
        """Bu ürünün şu anki Lunar fiyatı.

        - Sahip değilse: satın alma (K1) fiyatı (product.price).
        - Sahipse ve geliştirilebilirse: bir üst kademe fiyatı.
        - Sahipse ve tavandaysa: 0 (işlem yok).
        """
        if not self._is_card_product(product):
            return int(getattr(product, 'price', 0) or 0)
        if not self._card_is_owned(product):
            return int(getattr(product, 'price', 0) or 0)
        current_tier = self._card_current_tier(product)
        if current_tier >= self._card_max_tier(product):
            return 0
        family = self._card_family_of(product)
        if _get_card_upgrade_price is None:
            return 0
        try:
            return int(_get_card_upgrade_price(family, current_tier) or 0)
        except Exception:
            return 0

    def _card_is_upgrade_action(self, product) -> bool:
        """Bu kart için işlem 'geliştirme' mi (sahip + tavan altı)?"""
        if not self._is_card_product(product):
            return False
        if not self._card_is_owned(product):
            return False
        return self._card_current_tier(product) < self._card_max_tier(product)

    def _card_title(self, product) -> str:
        """Kart başlığını _group_id üzerinden yerelleştir."""
        family = self._card_family_of(product)
        if family and _get_card_title is not None:
            try:
                title = _get_card_title({'id': family, '_group_id': family}, fallback=getattr(product, 'fallback_title', family))
                if title:
                    return str(title)
            except Exception:
                pass
        return str(getattr(product, 'fallback_title', '') or family)

    def _card_desc(self, product) -> str:
        """Kart açıklamasını _group_id üzerinden yerelleştir."""
        family = self._card_family_of(product)
        if family and _get_card_description is not None:
            try:
                desc = _get_card_description({'id': family, '_group_id': family}, fallback=getattr(product, 'fallback_desc', ''))
                if desc:
                    return str(desc)
            except Exception:
                pass
        return str(getattr(product, 'fallback_desc', '') or '')

    def _set_active_category(self, index: int) -> None:
        """Switch the active category page, keeping a sensible selection.

        If the currently selected product is not present on the new page we
        snap the selection to the first visible product so the spotlight always
        shows something coherent for the page the player is looking at.
        """
        if not self.categories:
            return
        new_index = index % len(self.categories)
        if new_index == self.active_category:
            return
        self.active_category = new_index
        self.grid_scroll = 0
        # Stamp the switch so draw() can run the short fade/slide transition.
        try:
            self._tab_switch_ms = pygame.time.get_ticks()
        except Exception:
            self._tab_switch_ms = 0
        visible = self._compute_visible_indices()
        self._visible_indices = visible
        if visible and self.selected_index not in visible:
            self.selected_index = visible[0]

    def _switch_category(self, delta: int) -> None:
        if not self.categories:
            return
        self._set_active_category(self.active_category + delta)

    def get_fragment_balance(self) -> int:
        if self.user_manager is None:
            return 0

        balance_getter = getattr(self.user_manager, 'get_fragments', None)
        try:
            if callable(balance_getter):
                return max(0, int(balance_getter() or 0))
        except Exception:
            pass

        profile = self._get_user_profile()
        if isinstance(profile, dict):
            try:
                return int(profile.get('neural_fragments', 0) or 0)
            except Exception:
                return 0
        return 0

    def handle_input(self, event):
        # Purchase-confirmation modal is fully modal: while open it captures all
        # input so nothing behind it can be navigated, paged, or clicked.
        if self.is_confirm_open:
            return self._handle_confirm_input(event)
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
                return 'back'
            # Category page switching. Bound to Tab / [ ] / PageUp-Down so it
            # never collides with the arrow keys (which stay product
            # selection). Gamepad LB/RB map to K_LEFTBRACKET / K_RIGHTBRACKET
            # (see gamepad_manager), so controllers page through categories too.
            if event.key == pygame.K_TAB:
                mods = pygame.key.get_mods()
                self._switch_category(-1 if mods & pygame.KMOD_SHIFT else 1)
                return None
            if event.key in (pygame.K_RIGHTBRACKET, pygame.K_PAGEDOWN):
                self._switch_category(1)
                return None
            if event.key in (pygame.K_LEFTBRACKET, pygame.K_PAGEUP):
                self._switch_category(-1)
                return None
            if event.key == pygame.K_LEFT:
                self._move_selection(-1, 0)
            elif event.key == pygame.K_RIGHT:
                self._move_selection(1, 0)
            elif event.key == pygame.K_UP:
                self._move_selection(0, -1)
            elif event.key == pygame.K_DOWN:
                self._move_selection(0, 1)
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                self._activate_selected_product()
        elif event.type == pygame.MOUSEMOTION:
            self.mouse_pos = normalize_mouse_pos(getattr(event, 'pos', None)) or event.pos
            # Back affordance hover. Keep this update lightweight — no rect
            # rebuild here; draw() owns the layout and rebuilds the rect.
            self._back_hover = bool(
                self._back_rect is not None and self._back_rect.collidepoint(self.mouse_pos)
            )
            # NOTE: hover no longer changes the selection. The spotlight/hero
            # only follows an explicit click (or keyboard navigation), so
            # sweeping the mouse over the rail never reassigns the selected
            # product. Cards still render a light hover cue via ``mouse_pos``.
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = normalize_mouse_pos(getattr(event, 'pos', None)) or event.pos
            # Back affordance must win over CTA/cards so a back-click can
            # never accidentally land on a hero card or trigger a purchase.
            if self._back_rect is not None and self._back_rect.collidepoint(pos):
                return 'back'
            # Page arrows (‹ ›) are checked right after back and before tabs.
            # They only page the category view — never buy/equip.
            if self._tab_prev_arrow_rect is not None and self._tab_prev_arrow_rect.collidepoint(pos):
                self._switch_category(-1)
                return None
            if self._tab_next_arrow_rect is not None and self._tab_next_arrow_rect.collidepoint(pos):
                self._switch_category(1)
                return None
            # Category tabs are checked before CTA/cards. Clicking a tab only
            # switches the page; it never buys/equips.
            for tab_index, tab_rect in enumerate(self._tab_rects):
                if tab_rect.collidepoint(pos):
                    self._set_active_category(tab_index)
                    return None
            # CTA button is the only mouse path that triggers buy/equip/feedback.
            # The hit-zone is always live (even when the button is visually disabled)
            # so that locked/equipped clicks produce the same explanation the
            # keyboard ENTER path does — mouse and keyboard now agree.
            if self._cta_rect is not None and self._cta_rect.collidepoint(pos):
                self._activate_selected_product()
                return None
            # Card clicks select only. Activation is intentional, via CTA or ENTER,
            # so a second click on the spotlight cannot accidentally spend currency.
            clicked_index = self._card_index_at(pos)
            if clicked_index is not None and clicked_index != self.selected_index:
                self.selected_index = clicked_index
                self._ensure_selected_card_visible()
        elif event.type == pygame.MOUSEWHEEL:
            if self.max_grid_scroll > 0:
                self._scroll_grid(-event.y)
            elif event.y > 0:
                self._move_selection(0, -1)
            elif event.y < 0:
                self._move_selection(0, 1)
        return None

    def draw(self):
        width, height = self.screen.get_size()
        self._draw_scale = self._ui_scale()
        _s = self._s

        retro_style.draw_background(self.screen)
        self.background_fx.update(self.screen)
        self.background_fx.draw(self.screen)
        title_rect = retro_style.draw_title(
            self.screen,
            t('store_title', default='Mağaza'),
            (width // 2, _s(70)),
        )

        # Mouse-friendly back affordance in the top-left. ESC/BACKSPACE keep
        # working; this never overlaps the centered title or the hero/rail
        # area below it.
        self._draw_back_button()

        # Outer content column. Widened so the store fills more of the window
        # left-to-right; a slim gutter keeps it off the screen edges. The
        # logical cap stops it from sprawling on ultra-wide monitors.
        outer_width = min(_s(1600), max(0, width - _s(48)))
        outer_x = (width - outer_width) // 2

        # Resolve the active category page every frame. Ownership-driven pages
        # (e.g. "Koleksiyonum") can change between frames as the player buys
        # things, so we recompute here rather than caching. Snap the selection
        # back onto the page if it drifted off (e.g. a product left the owned
        # page) so the spotlight always reflects the page being viewed.
        self._visible_indices = self._compute_visible_indices()
        if self._visible_indices and self.selected_index not in self._visible_indices:
            self.selected_index = self._visible_indices[0]
            self.grid_scroll = 0

        # Footer breakpoint flag is preserved for layout-aware tests even
        # though no visual footer panel/text is rendered. Tests check this
        # flag to confirm the screen still adapts to narrow widths.
        narrow_footer = width < 900
        self._footer_two_row = narrow_footer

        # Category tab bar sits between the title and the body. It is the
        # primary page-navigation affordance and stays visible on every page.
        # The bar is a tall glass "rail" segmented control (icon + label per
        # tab), so it needs more vertical room than a flat pill strip.
        tab_bar_height = _s(78 if not narrow_footer else 62)
        tab_bar_rect = pygame.Rect(
            outer_x,
            title_rect.bottom + _s(22),
            outer_width,
            tab_bar_height,
        )
        self._draw_category_tabs(tab_bar_rect, narrow=narrow_footer)

        # Body fills the area between the tab bar and the screen bottom margin.
        bottom_margin = _s(28)
        body_top = tab_bar_rect.bottom + _s(20)
        body_height = max(_s(320), height - body_top - bottom_margin)

        # Hero band consumes ~46% of the body height; collection rail takes
        # the rest. Compact mode keeps the hero comfortable on shorter
        # screens but lets the rail breathe.
        compact = body_height < _s(520)
        hero_ratio = 0.50 if compact else 0.46
        hero_height = max(_s(220), min(_s(330), int(body_height * hero_ratio)))
        gap = _s(20)

        hero_rect = pygame.Rect(outer_x, body_top, outer_width, hero_height)
        rail_rect = pygame.Rect(
            outer_x,
            hero_rect.bottom + gap,
            outer_width,
            max(_s(180), height - hero_rect.bottom - gap - bottom_margin),
        )

        title_font = retro_style.get_font(_s(26), bold=True)
        body_font = retro_style.get_font(_s(16))
        small_font = retro_style.get_font(_s(13))
        price_font = retro_style.get_font(_s(28), bold=True)

        if self._visible_indices:
            self._draw_hero(hero_rect, title_font, body_font, small_font, price_font)
            self._draw_collection_rail(rail_rect, title_font, body_font, small_font, price_font)
        else:
            # Defensive empty-state: keep the CTA/card hit-zones cleared so a
            # stray click can't trigger a purchase on a page with nothing to
            # show. In practice the owned page always contains the bundled
            # rainbow trace, so this is a safety net rather than a common path.
            self._cta_rect = None
            self.card_rects = []
            self._draw_empty_category(hero_rect.union(rail_rect), title_font, body_font)

        # Cross-page transition: a short fade veil over the body right after a
        # category switch. Drawn AFTER the body (so hit-zones stay at their
        # final positions — no mis-click during the glide) and only allocates a
        # surface during the brief transition window, never in steady state.
        self._draw_page_transition_veil(hero_rect.union(rail_rect))

        # Purchase-confirmation modal is drawn last so it sits above everything
        # (including the transition veil) and owns the topmost hit-zones.
        if self.is_confirm_open:
            self._draw_purchase_confirm()

    def _draw_page_transition_veil(self, body_rect: pygame.Rect) -> None:
        """Fade veil over the body for ``_TAB_TRANSITION_MS`` after a switch.

        Combined with the sliding tab underline this reads as a polished page
        transition. Time-driven via ``pygame.time.get_ticks()``; the veil's
        alpha decays to zero so the effect self-terminates without any per-frame
        steady-state cost.
        """
        if not self._tab_switch_ms:
            return
        try:
            now = pygame.time.get_ticks()
        except Exception:
            self._tab_switch_ms = 0
            return
        elapsed = now - self._tab_switch_ms
        if elapsed < 0 or elapsed >= _TAB_TRANSITION_MS:
            # Transition finished — clear the stamp so we stop allocating.
            self._tab_switch_ms = 0
            return
        progress = elapsed / float(_TAB_TRANSITION_MS)
        # Ease-out: veil starts fairly opaque and fades quickly.
        veil_alpha = int(max(0, min(140, 140 * (1.0 - progress))))
        if veil_alpha <= 0 or body_rect.width <= 0 or body_rect.height <= 0:
            return
        veil = pygame.Surface(body_rect.size, pygame.SRCALPHA)
        pygame.draw.rect(veil, (6, 10, 22, veil_alpha), veil.get_rect(), border_radius=self._s(16))
        self.screen.blit(veil, body_rect.topleft)

    def _draw_purchase_confirm(self) -> None:
        """Centered purchase-confirmation dialog over a dimmed full-screen veil.

        Shows the product name, its price, and the player's balance, with
        Confirm/Cancel buttons. Rebuilds ``_confirm_yes_rect`` / ``_confirm_no_rect``
        every frame so the click hit-zones track the current layout.
        """
        if self._confirm_index is None:
            return
        try:
            product = self.products[self._confirm_index]
        except IndexError:
            self._close_purchase_confirm()
            return

        width, height = self.screen.get_size()
        _s = self._s

        # 1) Full-screen dim veil so the dialog reads as modal.
        veil = pygame.Surface((width, height), pygame.SRCALPHA)
        veil.fill((4, 8, 18, 188))
        self.screen.blit(veil, (0, 0))

        # 2) Dialog panel, centered.
        panel_w = min(_s(520), max(_s(320), width - _s(80)))
        panel_h = min(_s(300), max(_s(220), height - _s(120)))
        panel_rect = pygame.Rect(0, 0, panel_w, panel_h)
        panel_rect.center = (width // 2, height // 2)
        retro_style.draw_glass_panel(
            self.screen,
            panel_rect,
            alpha=238,
            border_color=product.accent,
            glow=True,
        )
        pygame.draw.rect(self.screen, (*product.accent, 210), panel_rect, 2, border_radius=_s(16))

        inner = panel_rect.inflate(-_s(34), -_s(28))

        # 3) Heading.
        heading_font = retro_style.get_font(_s(22), bold=True)
        heading = t('store_confirm_title', default='Satın almak istiyor musun?')
        heading_surf = heading_font.render(heading, True, (244, 248, 255))
        self.screen.blit(heading_surf, (inner.centerx - heading_surf.get_width() // 2, inner.y))

        # 4) Product name (accent), centered under the heading.
        name_font = retro_style.get_font(_s(18), bold=True)
        name = self._product_title(product)
        name_max = inner.width
        if name_font.size(name)[0] > name_max:
            name = self._ellipsize(name_font, name, name_max)
        name_surf = name_font.render(name, True, product.accent)
        name_y = inner.y + heading_surf.get_height() + _s(16)
        self.screen.blit(name_surf, (inner.centerx - name_surf.get_width() // 2, name_y))

        # 5) Price line with the fragment glyph, and the running balance below.
        # Kart ürünleri için satın alma/geliştirme bedelini kullan.
        effective_price = self._card_effective_price(product) if self._is_card_product(product) else product.price
        price_font = retro_style.get_font(_s(30), bold=True)
        price_text = self._price_short_label(effective_price)
        price_surf = price_font.render(price_text, True, (255, 232, 158))
        glyph_size = max(_s(22), min(_s(30), price_surf.get_height()))
        gap = _s(10)
        block_w = glyph_size + gap + price_surf.get_width()
        price_y = name_y + name_surf.get_height() + _s(18)
        glyph_cx = inner.centerx - block_w // 2 + glyph_size // 2
        glyph_cy = price_y + price_surf.get_height() // 2
        self._draw_fragment_glyph((glyph_cx, glyph_cy), glyph_size, (255, 214, 130))
        self.screen.blit(price_surf, (glyph_cx + glyph_size // 2 + gap, price_y))

        balance = self.get_fragment_balance()
        bal_font = retro_style.get_font(_s(13))
        after = max(0, balance - effective_price)
        bal_text = self._trf(
            'store_confirm_balance',
            'Bakiye: {balance} LN  →  {after} LN',
            balance=balance,
            after=after,
        )
        bal_surf = bal_font.render(bal_text, True, (176, 192, 220))
        bal_y = price_y + price_surf.get_height() + _s(10)
        self.screen.blit(bal_surf, (inner.centerx - bal_surf.get_width() // 2, bal_y))

        # 6) Confirm / Cancel buttons along the bottom.
        btn_h = _s(48)
        btn_gap = _s(16)
        btn_w = (inner.width - btn_gap) // 2
        btn_y = inner.bottom - btn_h
        no_rect = pygame.Rect(inner.x, btn_y, btn_w, btn_h)
        yes_rect = pygame.Rect(inner.right - btn_w, btn_y, btn_w, btn_h)
        self._confirm_no_rect = no_rect
        self._confirm_yes_rect = yes_rect

        btn_font = retro_style.get_font(_s(16), bold=True)
        # Cancel (neutral)
        no_hover = no_rect.collidepoint(self.mouse_pos)
        no_surf = pygame.Surface(no_rect.size, pygame.SRCALPHA)
        pygame.draw.rect(no_surf, (40, 52, 78, 230 if no_hover else 190), no_surf.get_rect(), border_radius=_s(12))
        pygame.draw.rect(no_surf, (150, 168, 200, 220 if no_hover else 150), no_surf.get_rect(), 1, border_radius=_s(12))
        self.screen.blit(no_surf, no_rect.topleft)
        no_label = btn_font.render(t('store_confirm_cancel', default='Vazgeç'), True, (224, 232, 246))
        self.screen.blit(no_label, (no_rect.centerx - no_label.get_width() // 2, no_rect.centery - no_label.get_height() // 2))

        # Confirm (accent)
        yes_hover = yes_rect.collidepoint(self.mouse_pos)
        accent = product.accent
        yes_surf = pygame.Surface(yes_rect.size, pygame.SRCALPHA)
        pygame.draw.rect(yes_surf, (*accent, 255 if yes_hover else 224), yes_surf.get_rect(), border_radius=_s(12))
        self.screen.blit(yes_surf, yes_rect.topleft)
        if yes_hover:
            pygame.draw.rect(self.screen, (255, 255, 255, 60), yes_rect, 2, border_radius=_s(12))
        yes_label = btn_font.render(t('store_confirm_buy', default='Satın Al'), True, (14, 22, 38))
        self.screen.blit(yes_label, (yes_rect.centerx - yes_label.get_width() // 2, yes_rect.centery - yes_label.get_height() // 2))

    def _draw_back_button(self) -> None:
        """Top-left mouse back affordance.

        Click semantics: returns ``'back'`` from ``handle_input`` — exactly
        the same outcome as ESC/BACKSPACE. Visual format matches the main
        menu's bottom-right exit tile (shared helper)."""
        # Refresh hover from the live (normalized) cursor every frame so a
        # missed MOUSEMOTION (alt-tab, focus loss, hidden mouse) does not
        # leave the hover state stale. Falls back to the cached event pos
        # if the normalized helper raises in headless/test contexts.
        try:
            live_pos = get_mouse_pos()
        except Exception:
            live_pos = self.mouse_pos
        prev_rect = self._back_rect
        hover = bool(prev_rect is not None and prev_rect.collidepoint(live_pos))

        rect = _draw_shared_back_button(
            self.screen,
            self._s,
            label=f"{t('main_menu', default='Ana Menü')}",
            hover=hover,
            retro_style=retro_style,
        )
        self._back_rect = rect
        self._back_hover = bool(rect.collidepoint(live_pos))

    # Per-category neon accents. Each store page owns a hue so the rail reads
    # as a colour-coded segmented control instead of six identical pills. The
    # active tab, its icon, count badge and the sliding underline all adopt the
    # page's own hue, which makes "where am I" obvious at a glance.
    _CATEGORY_ACCENTS: dict[str, tuple[int, int, int]] = {
        'featured': (255, 178, 64),     # warm amber — the spotlight page
        'traces': (0, 235, 214),        # cyan — line-sweep trails
        'pets': (255, 96, 196),         # pink — companions
        'blocks': (116, 214, 255),      # ice blue — block appearances
        'cards': (122, 224, 120),       # lime — buyable cards
        'card_upgrades': (124, 168, 255),  # blue — upgrades
        'owned': (255, 212, 92),        # gold — your collection
    }

    def _category_accent(self, key: str) -> tuple[int, int, int]:
        """Resolve a category's neon hue, defaulting to the theme primary."""
        return self._CATEGORY_ACCENTS.get(str(key), tuple(retro_style.primary))

    def _draw_category_tabs(self, bar_rect: pygame.Rect, *, narrow: bool = False) -> None:
        """Render the category tab bar and record per-tab hit-zones.

        The bar is a single glass "rail" segmented control. Each segment stacks
        a small neon vector icon over its label and carries a corner count
        badge; the active segment lights up in its own category hue with a soft
        glow and a sliding underline. The rail is flanked by ‹ / › page arrows
        and (when there's room) a keyboard / gamepad navigation hint, so paging
        stays discoverable instead of a guessable keypress.
        """
        self._tab_rects = []
        self._tab_prev_arrow_rect = None
        self._tab_next_arrow_rect = None
        if not self.categories:
            return

        count = len(self.categories)
        gap = self._s(8)
        rail_pad = self._s(8)
        radius = self._s(16)

        # Square page-arrow buttons flank the rail, vertically centred. Reserve
        # their footprint up front so the rail never grows under them.
        arrow_size = self._s(40 if not narrow else 34)
        arrow_margin = self._s(14)
        reserved = (arrow_size + arrow_margin) * 2
        # The rail stretches to (almost) the full content column width, leaving
        # only the arrow footprint on each side. The logical cap keeps the
        # segments from becoming absurdly wide on ultra-wide displays.
        usable_width = min(max(self._s(280), bar_rect.width - reserved), self._s(1500))

        # Segment width honours a readable floor; with six tabs the cluster can
        # exceed ``usable_width`` on narrow windows, so we derive the ACTUAL
        # rail width from the resolved segment width and let the arrows track
        # the rail edges (never overlapping the end segments).
        seg_floor = self._s(120 if not narrow else 88)
        inner_budget = usable_width - rail_pad * 2
        seg_width = max(seg_floor, (inner_budget - gap * (count - 1)) // count)
        cluster_width = seg_width * count + gap * (count - 1)
        rail_width = cluster_width + rail_pad * 2
        rail_x = bar_rect.x + max(arrow_size + arrow_margin, (bar_rect.width - rail_width) // 2)
        rail_rect = pygame.Rect(rail_x, bar_rect.y, rail_width, bar_rect.height)

        # ── Glass rail shell ─────────────────────────────────────────
        # One container that visually binds the tabs together. Darker than the
        # body so the lit active segment pops, with a faint top sheen + neon rim.
        shell = pygame.Surface(rail_rect.size, pygame.SRCALPHA)
        shell_box = shell.get_rect()
        pygame.draw.rect(shell, (9, 14, 30, 184), shell_box, border_radius=radius)
        sheen_h = max(self._s(2), rail_rect.height // 2)
        sheen = pygame.Surface((rail_rect.width, sheen_h), pygame.SRCALPHA)
        pygame.draw.rect(sheen, (255, 255, 255, 12), sheen.get_rect(), border_radius=radius)
        shell.blit(sheen, (0, 0))
        pygame.draw.rect(shell, (66, 98, 158, 95), shell_box, 1, border_radius=radius)
        self.screen.blit(shell, rail_rect.topleft)

        # Arrow hit-zones (recorded for the mouse handler; click → page only).
        arrow_cy = bar_rect.y + bar_rect.height // 2
        prev_rect = pygame.Rect(
            rail_x - arrow_margin - arrow_size, arrow_cy - arrow_size // 2, arrow_size, arrow_size
        )
        next_rect = pygame.Rect(
            rail_x + rail_width + arrow_margin, arrow_cy - arrow_size // 2, arrow_size, arrow_size
        )
        self._draw_tab_arrow(prev_rect, left=True)
        self._draw_tab_arrow(next_rect, left=False)
        self._tab_prev_arrow_rect = prev_rect
        self._tab_next_arrow_rect = next_rect

        label_size = self._s(16 if not narrow else 13)
        badge_font = retro_style.get_font(self._s(11), bold=True)

        active_target_x = None
        active_target_w = None
        active_accent = self._category_accent(self.get_active_category_key())

        seg_x0 = rail_x + rail_pad
        for index, category in enumerate(self.categories):
            tx = seg_x0 + index * (seg_width + gap)
            tab_rect = pygame.Rect(tx, bar_rect.y + rail_pad, seg_width, bar_rect.height - rail_pad * 2)
            self._tab_rects.append(tab_rect)

            key = str(category.get('key', ''))
            accent = self._category_accent(key)
            active = index == self.active_category
            hovered = tab_rect.collidepoint(self.mouse_pos)
            seg_radius = self._s(11)

            # Active segment: soft outer glow + accent-washed fill + bright rim.
            if active:
                self._draw_soft_glow(tab_rect, accent, alpha=46, padding=self._s(5))
            seg = pygame.Surface(tab_rect.size, pygame.SRCALPHA)
            seg_box = seg.get_rect()
            if active:
                pygame.draw.rect(seg, (20, 30, 52, 235), seg_box, border_radius=seg_radius)
                wash = pygame.Surface(tab_rect.size, pygame.SRCALPHA)
                pygame.draw.rect(wash, (*accent, 52), wash.get_rect(), border_radius=seg_radius)
                seg.blit(wash, (0, 0))
            elif hovered:
                pygame.draw.rect(seg, (18, 27, 47, 170), seg_box, border_radius=seg_radius)
            else:
                pygame.draw.rect(seg, (13, 20, 38, 90), seg_box, border_radius=seg_radius)
            rim_alpha = 235 if active else (150 if hovered else 0)
            if rim_alpha:
                pygame.draw.rect(seg, (*accent, rim_alpha), seg_box, 2 if active else 1, border_radius=seg_radius)
            self.screen.blit(seg, tab_rect.topleft)

            # Icon hue: bright on the active tab, lifted on hover, dim otherwise.
            if active:
                icon_color = tuple(min(255, c + 26) for c in accent)
            elif hovered:
                icon_color = accent
            else:
                icon_color = tuple(int(c * 0.55 + 70) for c in accent)
            label_color = (250, 252, 255) if active else (204, 218, 240) if hovered else (150, 166, 196)

            # Vertical stack: icon on top, label beneath. The label uses the
            # fit-renderer so long names (e.g. "Kartları Geliştir") shrink to
            # the segment instead of overflowing the rail.
            icon_size = self._s(30 if not narrow else 22)
            label_max = tab_rect.width - self._s(14)
            label_surf = retro_style.render_fit_text(
                self._category_label(category), label_color, label_max, label_size, bold=True, min_size=self._s(10)
            )
            stack_h = icon_size + self._s(4) + label_surf.get_height()
            stack_top = tab_rect.y + max(self._s(2), (tab_rect.height - stack_h) // 2)
            icon_center = (tab_rect.centerx, stack_top + icon_size // 2)
            self._draw_tab_icon(icon_center, icon_size, key, icon_color)
            label_y = stack_top + icon_size + self._s(4)
            self.screen.blit(label_surf, (tab_rect.centerx - label_surf.get_width() // 2, label_y))

            # Corner count badge — how many items live on this page, so the tab
            # doubles as a quick inventory read. Computed from the same honest
            # view filter the grid uses.
            page_count = len(self._compute_visible_indices(key))
            badge_surf = badge_font.render(str(page_count), True, (10, 16, 30) if active else (216, 226, 246))
            badge_d = max(self._s(15), badge_surf.get_height() + self._s(5))
            badge_w = max(badge_d, badge_surf.get_width() + self._s(8))
            badge_rect = pygame.Rect(0, 0, badge_w, badge_d)
            badge_rect.topright = (tab_rect.right - self._s(5), tab_rect.y + self._s(4))
            badge_bg = pygame.Surface(badge_rect.size, pygame.SRCALPHA)
            badge_fill = (*accent, 240) if active else (26, 38, 62, 210)
            pygame.draw.rect(badge_bg, badge_fill, badge_bg.get_rect(), border_radius=badge_d // 2)
            if not active:
                pygame.draw.rect(badge_bg, (*accent, 140), badge_bg.get_rect(), 1, border_radius=badge_d // 2)
            self.screen.blit(badge_bg, badge_rect.topleft)
            self.screen.blit(
                badge_surf,
                (badge_rect.centerx - badge_surf.get_width() // 2, badge_rect.centery - badge_surf.get_height() // 2),
            )

            if active:
                active_target_x = tab_rect.x + self._s(14)
                active_target_w = tab_rect.width - self._s(28)

        # Sliding accent underline. Instead of snapping a static bar under the
        # active tab, we glide the underline toward the active tab's target
        # every frame, tinted with the active page's own hue.
        self._draw_sliding_underline(rail_rect, active_target_x, active_target_w, active_accent)

        # Navigation hints near the arrows. Hidden on narrow windows where the
        # horizontal budget is tight; arrows alone remain the affordance there.
        if not narrow:
            self._draw_tab_nav_hints(prev_rect, next_rect)

    def _draw_tab_icon(
        self, center: tuple[int, int], size: int, key: str, color: tuple[int, int, int]
    ) -> None:
        """Draw a small neon vector glyph for a category tab (pure primitives).

        Each glyph is rendered onto a transparent square so it stays crisp and
        consistently centred regardless of the segment size; no image assets.
        """
        size = max(self._s(12), int(size))
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        c = tuple(color)
        cx = cy = size // 2
        r = size // 2 - self._s(1)
        lw = max(2, self._s(2))

        if key == 'featured':
            # Spotlight star.
            self._draw_star(surf, (cx, cy), r, c)
        elif key == 'traces':
            # Shooting "sweep": a bright head with a shrinking, fading trail —
            # mirrors the line-sweep cosmetics this page sells.
            head = (int(size * 0.66), int(size * 0.34))
            hr = max(2, size // 5)
            for i in range(3, 0, -1):
                t = i / 3.0
                tx = int(head[0] - t * size * 0.5)
                ty = int(head[1] + t * size * 0.5)
                tr = max(1, int(hr * (1.0 - t * 0.55)))
                pygame.draw.circle(surf, (*c, max(60, int(255 * (1.0 - t * 0.5)))), (tx, ty), tr)
            pygame.draw.circle(surf, c, head, hr)
        elif key == 'pets':
            # Paw: main pad + three toe beans.
            pad_r = max(3, size // 4)
            pygame.draw.circle(surf, c, (cx, int(size * 0.64)), pad_r)
            toe_r = max(2, size // 7)
            for ox in (0.30, 0.5, 0.70):
                ty = int(size * (0.32 if abs(ox - 0.5) < 0.01 else 0.42))
                pygame.draw.circle(surf, c, (int(size * ox), ty), toe_r)
        elif key == 'blocks':
            # Four stacked cells = block cosmetic category.
            cell = max(3, size // 4)
            gap = max(1, size // 12)
            total = cell * 2 + gap
            start_x = cx - total // 2
            start_y = cy - total // 2
            for dx in (0, 1):
                for dy in (0, 1):
                    rect = pygame.Rect(
                        start_x + dx * (cell + gap),
                        start_y + dy * (cell + gap),
                        cell,
                        cell,
                    )
                    pygame.draw.rect(surf, c, rect, max(1, lw - 1))
        elif key == 'cards':
            # A single playing card with an inner header line.
            cw, ch = int(size * 0.52), int(size * 0.66)
            card = pygame.Rect(0, 0, cw, ch)
            card.center = (cx, cy)
            pygame.draw.rect(surf, c, card, lw, border_radius=self._s(2))
            ly = card.y + ch // 3
            pygame.draw.line(surf, c, (card.x + lw + 1, ly), (card.right - lw - 1, ly), max(1, lw - 1))
        elif key == 'card_upgrades':
            # Double up-chevron = level up / upgrade.
            reach = max(3, size // 4)
            for yc in (int(size * 0.44), int(size * 0.64)):
                pygame.draw.line(surf, c, (cx - reach, yc + reach), (cx, yc), lw)
                pygame.draw.line(surf, c, (cx + reach, yc + reach), (cx, yc), lw)
        elif key == 'owned':
            # Collection checkmark.
            pygame.draw.lines(
                surf, c, False,
                [(int(size * 0.24), int(size * 0.52)),
                 (int(size * 0.43), int(size * 0.70)),
                 (int(size * 0.78), int(size * 0.30))],
                lw + 1,
            )
        else:
            # Generic dot fallback for any future category key.
            pygame.draw.circle(surf, c, (cx, cy), max(2, r // 2), lw)

        self.screen.blit(surf, (center[0] - size // 2, center[1] - size // 2))

    def _draw_tab_arrow(self, rect: pygame.Rect, *, left: bool) -> None:
        """Draw a single ‹ / › page-arrow button. Pure primitives, no asset."""
        hovered = rect.collidepoint(self.mouse_pos)
        accent = retro_style.accent if hovered else retro_style.primary
        bg = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(bg, (14, 21, 40, 200 if hovered else 150), bg.get_rect(), border_radius=self._s(12))
        pygame.draw.rect(bg, (*accent, 220 if hovered else 130), bg.get_rect(), 2 if hovered else 1, border_radius=self._s(12))
        self.screen.blit(bg, rect.topleft)

        # Chevron drawn from two line segments so it scales crisply.
        cx, cy = rect.centerx, rect.centery
        reach = max(self._s(5), rect.width // 5)
        tip_x = cx - reach if left else cx + reach
        base_x = cx + reach if left else cx - reach
        color = (250, 252, 255) if hovered else (196, 210, 236)
        width = max(2, self._s(3))
        pygame.draw.line(self.screen, color, (base_x, cy - reach), (tip_x, cy), width)
        pygame.draw.line(self.screen, color, (base_x, cy + reach), (tip_x, cy), width)

    def _draw_sliding_underline(
        self,
        bar_rect: pygame.Rect,
        target_x: float | None,
        target_w: float | None,
        accent: tuple[int, int, int] | None = None,
    ) -> None:
        """Glide the active-tab underline toward its target (time-driven lerp)."""
        if target_x is None or target_w is None:
            return
        if accent is None:
            accent = tuple(retro_style.accent)
        # Initialise on first draw so the underline doesn't slide in from 0.
        if self._tab_underline_x is None or self._tab_underline_w is None:
            self._tab_underline_x = float(target_x)
            self._tab_underline_w = float(target_w)
        else:
            # Critically-damped-ish ease: move a fixed fraction toward target
            # each frame. Frame-rate independence isn't critical for a sub-
            # 200 ms cosmetic glide, and this avoids storing a per-frame dt.
            ease = 0.32
            self._tab_underline_x += (float(target_x) - self._tab_underline_x) * ease
            self._tab_underline_w += (float(target_w) - self._tab_underline_w) * ease
            # Snap once we're within a pixel so we don't jitter forever.
            if abs(float(target_x) - self._tab_underline_x) < 1.0:
                self._tab_underline_x = float(target_x)
            if abs(float(target_w) - self._tab_underline_w) < 1.0:
                self._tab_underline_w = float(target_w)

        ux = int(round(self._tab_underline_x))
        uw = max(self._s(8), int(round(self._tab_underline_w)))
        underline = pygame.Surface((uw, self._s(3)), pygame.SRCALPHA)
        pygame.draw.rect(underline, (*accent, 230), underline.get_rect(), border_radius=self._s(2))
        self.screen.blit(underline, (ux, bar_rect.bottom - self._s(7)))

    def _draw_tab_nav_hints(self, prev_rect: pygame.Rect, next_rect: pygame.Rect) -> None:
        """Show LB/RB gamepad glyphs beside the page arrows — only when a
        controller is connected.

        The arrows themselves are the visual paging affordance, so we no longer
        draw a keyboard ``[`` / ``]`` rosette (it only added clutter for
        mouse/keyboard players). When a gamepad IS connected the LB/RB glyphs
        are genuinely useful, so those stay.
        """
        connected = False
        try:
            connected = bool(_is_gamepad_connected())
        except Exception:
            connected = False
        if not connected or _render_button_glyph is None:
            return

        hint_font = retro_style.get_font(self._s(13), bold=True)
        hint_color = (150, 168, 198)
        try:
            # LB = button 9, RB = button 10 (see gamepad_manager).
            left_surf = _render_button_glyph(9, 'LB', hint_font, hint_color)
            right_surf = _render_button_glyph(10, 'RB', hint_font, hint_color)
        except Exception:
            return
        if left_surf is None or right_surf is None:
            return

        # Place left hint to the LEFT of the prev arrow, right hint to the
        # RIGHT of the next arrow, vertically centred on the arrows.
        gap = self._s(8)
        lx = prev_rect.x - gap - left_surf.get_width()
        if lx >= 0:
            ly = prev_rect.centery - left_surf.get_height() // 2
            self.screen.blit(left_surf, (lx, ly))
        rx = next_rect.right + gap
        if rx + right_surf.get_width() <= self.screen.get_width():
            ry = next_rect.centery - right_surf.get_height() // 2
            self.screen.blit(right_surf, (rx, ry))

    def _draw_empty_category(self, rect: pygame.Rect, title_font, body_font) -> None:
        """Gentle empty-state panel when the active page has no products."""
        retro_style.draw_glass_panel(
            self.screen,
            rect,
            alpha=160,
            border_color=retro_style.primary,
            glow=False,
        )
        # Decorative fragment glyph above the copy so the empty state feels
        # intentional rather than broken. Reuses the same faceted-diamond the
        # wallet pill uses, in a muted accent so it doesn't shout.
        glyph_size = max(self._s(34), min(self._s(56), rect.height // 6))
        glyph_cy = rect.centery - self._s(44)
        self._draw_fragment_glyph((rect.centerx, glyph_cy), glyph_size, (120, 150, 196))
        # Soft halo ring around the glyph for a bit of depth.
        ring_r = glyph_size
        ring = pygame.Surface((ring_r * 2, ring_r * 2), pygame.SRCALPHA)
        pygame.draw.circle(ring, (*retro_style.primary, 30), (ring_r, ring_r), ring_r, max(2, self._s(2)))
        self.screen.blit(ring, (rect.centerx - ring_r, glyph_cy - ring_r))

        title_text = t('store_empty_category', default='Bu sayfada henüz ürün yok.')
        title_surf = title_font.render(title_text, True, (228, 236, 250))
        self.screen.blit(
            title_surf,
            title_surf.get_rect(center=(rect.centerx, rect.centery + self._s(8))),
        )
        hint_text = t('store_empty_category_hint', default='Diğer sekmelere göz at.')
        hint_surf = body_font.render(hint_text, True, (170, 188, 218))
        self.screen.blit(
            hint_surf,
            hint_surf.get_rect(center=(rect.centerx, rect.centery + self._s(40))),
        )

    def _ui_scale(self) -> float:
        return get_projected_effective_scale(
            self.screen,
            min_scale=0.68,
            max_scale=1.08,
            reference_size=(1920.0, 1080.0),
        )

    def _s(self, value: int | float, minimum: int = 1) -> int:
        return max(minimum, int(round(float(value) * self._draw_scale)))

    def _get_user_profile(self):
        if self.user_manager is None:
            return None

        getter = getattr(self.user_manager, 'get_user_data', None)
        if not callable(getter):
            return None

        try:
            return getter()
        except TypeError:
            try:
                return getter(self._get_current_profile_name())
            except Exception:
                return None
        except Exception:
            return None

    def _move_selection(self, dx: int, dy: int) -> None:
        # Navigation operates within the active category page. ``_visible_indices``
        # maps grid positions -> absolute product indices, so we move in
        # *visible-position* space and translate back to the absolute index the
        # rest of the screen (CTA, ownership) expects.
        visible = self._visible_indices or list(range(len(self.products)))
        if not visible:
            self.selected_index = 0
            return

        columns = max(1, self._last_columns or self._get_column_count(self.screen.get_width()))
        try:
            pos = visible.index(self.selected_index)
        except ValueError:
            pos = 0

        next_pos = pos
        if dx < 0:
            next_pos = max(0, pos - 1)
        elif dx > 0:
            next_pos = min(len(visible) - 1, pos + 1)
        elif dy < 0:
            next_pos = max(0, pos - columns)
        elif dy > 0:
            next_pos = min(len(visible) - 1, pos + columns)

        next_index = visible[next_pos]
        if next_index != self.selected_index:
            self.selected_index = next_index
            self._ensure_selected_card_visible()

    def _scroll_grid(self, rows: int) -> None:
        if self.max_grid_scroll <= 0:
            return
        step = max(self._last_row_step, self._s(120))
        self.grid_scroll = max(0, min(self.max_grid_scroll, self.grid_scroll + rows * step))

    def _ensure_selected_card_visible(self) -> None:
        if not self.products or self._last_card_height <= 0 or self._last_grid_viewport.height <= 0:
            return
        visible = self._visible_indices or list(range(len(self.products)))
        try:
            pos = visible.index(self.selected_index)
        except ValueError:
            return
        columns = max(1, self._last_columns)
        row = pos // columns
        top = row * self._last_row_step
        bottom = top + self._last_card_height
        viewport_top = self.grid_scroll
        viewport_bottom = self.grid_scroll + self._last_grid_viewport.height
        if top < viewport_top:
            self.grid_scroll = top
        elif bottom > viewport_bottom:
            self.grid_scroll = bottom - self._last_grid_viewport.height
        self.grid_scroll = max(0, min(self.max_grid_scroll, self.grid_scroll))

    def _sync_hover_selection(self, pos) -> bool:
        for index, rect in enumerate(self.card_rects):
            if rect.collidepoint(pos):
                if self.selected_index != index:
                    self.selected_index = index
                    self._ensure_selected_card_visible()
                return True
        return False

    def _card_index_at(self, pos) -> int | None:
        for index, rect in enumerate(self.card_rects):
            if rect.collidepoint(pos):
                return index
        return None

    def _activate_selected_product(self) -> None:
        selected = self.get_selected_product()
        state = self._resolve_ownership_state(selected)
        name = self._product_title(selected)

        # === Kart ürünleri ===
        if self._is_card_product(selected):
            if state == 'maxed':
                self.status_message = self._trf(
                    'store_card_maxed', '{name} zaten en yüksek kademede.', name=name
                )
                return
            # unowned (satın al) veya upgrade (geliştir) → bakiye kontrolü + modal.
            price = self._card_effective_price(selected)
            if self.get_fragment_balance() < price:
                self.status_message = self._trf(
                    'store_not_enough_fragments',
                    "{name} için yeterli Lunar yok.",
                    name=name,
                    price=price,
                    balance=self.get_fragment_balance(),
                )
                return
            self._open_purchase_confirm()
            return

        if state == 'equipped':
            self.status_message = self._trf('store_already_equipped', '{name} zaten kullanımda.', name=name)
            return
        if state == 'demo':
            if self._equip_product(selected, allow_demo=True):
                self.status_message = self._trf('store_demo_equipped', '{name} varsayılan iz olarak seçildi.', name=name)
            else:
                self.status_message = self._trf('store_action_failed', '{name} şu anda etkinleştirilemedi.', name=name)
            return
        if state == 'owned':
            if self._equip_product(selected):
                self.status_message = self._trf('store_equip_success', '{name} takıldı. Oyun içi sweep güncellendi.', name=name)
            else:
                self.status_message = self._trf('store_action_failed', '{name} şu anda etkinleştirilemedi.', name=name)
            return
        if self.get_fragment_balance() < selected.price:
            self.status_message = self._trf(
                'store_not_enough_fragments',
                "{name} için yeterli Lunar yok.",
                name=name,
                price=selected.price,
                balance=self.get_fragment_balance(),
            )
            return
        # Affordable, unowned → open the purchase-confirmation modal instead of
        # buying immediately. The dialog shows the name + price and only the
        # explicit "confirm" path spends currency.
        self._open_purchase_confirm()

    def _open_purchase_confirm(self) -> None:
        """Arm the purchase-confirmation modal for the current selection."""
        self._confirm_index = self.selected_index

    def _close_purchase_confirm(self) -> None:
        self._confirm_index = None
        self._confirm_yes_rect = None
        self._confirm_no_rect = None

    @property
    def is_confirm_open(self) -> bool:
        return self._confirm_index is not None

    def _handle_confirm_input(self, event):
        """Modal input: confirm/cancel only; never falls through to the store.

        Returns ``None`` always (the modal never exits the store; ESC just
        closes the dialog). Keyboard: ENTER confirms, ESC/BACKSPACE cancel.
        Mouse: click the Yes/No buttons; a click outside both cancels.
        """
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self._confirm_purchase()
            elif event.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
                self._close_purchase_confirm()
        elif event.type == pygame.MOUSEMOTION:
            self.mouse_pos = normalize_mouse_pos(getattr(event, 'pos', None)) or event.pos
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = normalize_mouse_pos(getattr(event, 'pos', None)) or event.pos
            if self._confirm_yes_rect is not None and self._confirm_yes_rect.collidepoint(pos):
                self._confirm_purchase()
            elif self._confirm_no_rect is not None and self._confirm_no_rect.collidepoint(pos):
                self._close_purchase_confirm()
            else:
                # Click on the dimmed backdrop cancels — standard modal affordance.
                self._close_purchase_confirm()
        return None

    def _confirm_purchase(self) -> None:
        """Execute the purchase the modal is asking the player to confirm.

        Re-validates ownership and balance at confirm time so a stale dialog
        (e.g. balance changed underneath it) can never overspend.
        """
        if self._confirm_index is None:
            return
        try:
            product = self.products[self._confirm_index]
        except IndexError:
            self._close_purchase_confirm()
            return
        name = self._product_title(product)
        state = self._resolve_ownership_state(product)

        # === Kart ürünleri (satın al / geliştir) ===
        if self._is_card_product(product):
            if state == 'maxed':
                # Açılışla onay arasında tavana ulaşılmış — sadece kapat.
                self._close_purchase_confirm()
                return
            is_upgrade = (state == 'upgrade')
            price = self._card_effective_price(product)
            if self.get_fragment_balance() < price:
                self.status_message = self._trf(
                    'store_not_enough_fragments',
                    "{name} için yeterli Lunar yok.",
                    name=name,
                    price=price,
                    balance=self.get_fragment_balance(),
                )
                self._close_purchase_confirm()
                return
            if self._purchase_or_upgrade_card_product(product, is_upgrade=is_upgrade):
                if is_upgrade:
                    self.status_message = self._trf(
                        'store_card_upgrade_success', '{name} geliştirildi.', name=name
                    )
                else:
                    self.status_message = self._trf(
                        'store_card_purchase_success', '{name} havuza eklendi.', name=name
                    )
            else:
                self.status_message = self._trf('store_action_failed', '{name} şu anda etkinleştirilemedi.', name=name)
            self._close_purchase_confirm()
            return

        if state in ('owned', 'equipped', 'demo'):
            # Already obtained between opening and confirming — just close.
            self._close_purchase_confirm()
            return
        if self.get_fragment_balance() < product.price:
            self.status_message = self._trf(
                'store_not_enough_fragments',
                "{name} için yeterli Lunar yok.",
                name=name,
                price=product.price,
                balance=self.get_fragment_balance(),
            )
            self._close_purchase_confirm()
            return
        if self._purchase_and_equip_product(product):
            self.status_message = self._trf(
                'store_purchase_success', '{name} satın alındı ve takıldı.', name=name
            )
        else:
            self.status_message = self._trf('store_action_failed', '{name} şu anda etkinleştirilemedi.', name=name)
        self._close_purchase_confirm()

    def _get_current_username(self):
        if self.user_manager is None:
            return None
        getter = getattr(self.user_manager, 'get_current_user', None)
        try:
            current_user = getter() if callable(getter) else getattr(self.user_manager, 'current_user', None)
        except Exception:
            current_user = None
        return current_user

    def _get_current_profile_name(self) -> str:
        current_user = self._get_current_username()
        if current_user:
            return str(current_user)
        return t('store_profile_guest', default='Misafir')

    def _trf(self, key: str, default: str, **values) -> str:
        template = str(t(key, default=default) or default)
        try:
            return template.format(**values)
        except Exception:
            return template

    def _product_payload(self, product: StoreProduct) -> tuple[str, str]:
        payload = product.cosmetic_payload or {}
        return str(payload.get('type') or ''), str(payload.get('value') or '')

    def _save_profile_state(self) -> None:
        if self.user_manager is None:
            return
        username = self._get_current_username()
        touch = getattr(self.user_manager, '_touch_profile', None)
        if callable(touch) and username:
            try:
                touch(username)
            except Exception:
                pass
        saver = getattr(self.user_manager, 'save_users', None)
        if callable(saver):
            try:
                saver()
            except Exception:
                pass

    def _equip_product(self, product: StoreProduct, *, allow_demo: bool = False) -> bool:
        slot, value = self._product_payload(product)
        if not slot or not value:
            return False

        equip = getattr(self.user_manager, 'equip_cosmetic', None)
        username = self._get_current_username()
        if callable(equip):
            try:
                return bool(equip(slot, value, username=username))
            except TypeError:
                try:
                    return bool(equip(slot, value))
                except Exception:
                    pass
            except Exception:
                pass

        profile = self._get_user_profile()
        if not isinstance(profile, dict):
            return False
        owned = profile.get('owned_cosmetics')
        if not isinstance(owned, list):
            owned = []
            profile['owned_cosmetics'] = owned
        if not allow_demo and value not in {str(entry) for entry in owned}:
            return False
        equipped_map = profile.get('equipped_cosmetics')
        if not isinstance(equipped_map, dict):
            equipped_map = {}
            profile['equipped_cosmetics'] = equipped_map
        equipped_map[slot] = value
        self._save_profile_state()
        if slot == _BLOCK_SKIN_SLOT and self.background_fx is not None:
            try:
                self.background_fx.sync_block_appearance(profile=profile)
            except Exception:
                pass
        return True

    def _purchase_and_equip_product(self, product: StoreProduct) -> bool:
        slot, value = self._product_payload(product)
        if not slot or not value:
            return False

        purchase = getattr(self.user_manager, 'purchase_and_equip_cosmetic', None)
        username = self._get_current_username()
        if callable(purchase):
            try:
                return bool(purchase(slot, value, product.price, username=username))
            except TypeError:
                try:
                    return bool(purchase(slot, value, product.price))
                except Exception:
                    pass
            except Exception:
                pass

        profile = self._get_user_profile()
        if not isinstance(profile, dict):
            return False

        current_balance = int(profile.get('neural_fragments', 0) or 0)
        if current_balance < product.price:
            return False

        owned = profile.get('owned_cosmetics')
        if not isinstance(owned, list):
            owned = []
            profile['owned_cosmetics'] = owned
        if value not in {str(entry) for entry in owned}:
            owned.append(value)
            profile['neural_fragments'] = current_balance - product.price

        equipped_map = profile.get('equipped_cosmetics')
        if not isinstance(equipped_map, dict):
            equipped_map = {}
            profile['equipped_cosmetics'] = equipped_map
        equipped_map[slot] = value
        self._save_profile_state()
        if slot == _BLOCK_SKIN_SLOT and self.background_fx is not None:
            try:
                self.background_fx.sync_block_appearance(profile=profile)
            except Exception:
                pass
        return True

    def _purchase_or_upgrade_card_product(self, product: StoreProduct, *, is_upgrade: bool) -> bool:
        """Kart ürününü satın al veya geliştir (user_manager üzerinden, atomik).

        Kartlarda 'equip' kavramı yoktur; satın alma sadece kartı Mystery seçim
        havuzunda aktif yapar, geliştirme ise kademeyi artırır.
        """
        family = self._card_family_of(product)
        if not family:
            return False
        um = self.user_manager
        if um is None:
            return False
        username = self._get_current_username()

        if is_upgrade:
            upgrade = getattr(um, 'upgrade_card', None)
            if not callable(upgrade):
                return False
            price = self._card_effective_price(product)
            max_tier = self._card_max_tier(product)
            try:
                return bool(upgrade(family, price, max_tier, username=username))
            except TypeError:
                try:
                    return bool(upgrade(family, price, max_tier))
                except Exception:
                    return False
            except Exception:
                return False

        purchase = getattr(um, 'purchase_card', None)
        if not callable(purchase):
            return False
        price = int(getattr(product, 'price', 0) or 0)
        try:
            return bool(purchase(family, price, username=username))
        except TypeError:
            try:
                return bool(purchase(family, price))
            except Exception:
                return False
        except Exception:
            return False

    def _draw_hero(self, rect, title_font, body_font, small_font, price_font) -> None:
        """Full-width featured/hero band: big preview + product story + wallet + CTA."""
        selected = self.get_selected_product()
        # Single-layer glass panel with the product's accent border. The old
        # bright halo behind the panel has been removed so the shop reads as
        # a single layered surface, in line with the game's neon-on-dark theme.
        retro_style.draw_glass_panel(
            self.screen,
            rect,
            alpha=180,
            border_color=selected.accent,
            glow=False,
        )
        # Generous corner padding so columns never touch the rounded border.
        inner = rect.inflate(-self._s(28), -self._s(24))

        # Three columns: preview | product copy | action stack (wallet + CTA + ownership)
        action_width = max(self._s(248), min(self._s(300), int(inner.width * 0.24)))
        preview_width = max(self._s(280), min(self._s(420), int(inner.width * 0.36)))
        gap = self._s(22)
        copy_width = max(self._s(220), inner.width - preview_width - action_width - gap * 2)

        preview_rect = pygame.Rect(inner.x, inner.y, preview_width, inner.height)
        copy_rect = pygame.Rect(preview_rect.right + gap, inner.y, copy_width, inner.height)
        action_rect = pygame.Rect(copy_rect.right + gap, inner.y, action_width, inner.height)

        self._draw_product_preview(selected, preview_rect, hero=True)
        self._draw_hero_copy(selected, copy_rect, title_font, body_font, small_font)
        self._draw_hero_action_stack(selected, action_rect, body_font, small_font, price_font)

    def _draw_hero_copy(
        self,
        product: StoreProduct,
        rect: pygame.Rect,
        title_font,
        body_font,
        small_font,
    ) -> None:
        """Center column: 'selected' tag, badge chip, product name, story copy."""
        # Honest tag: this anchors 'this is the spotlight ürünüsünüz', not a
        # marketing claim. The catalog has no curated featured field today, so
        # avoid implying every selection is editorially featured.
        tag_label = t('store_selected_label', default='Seçili ürün').upper()
        tag_font = retro_style.get_font(self._s(11), bold=True)
        tag_surf = tag_font.render(tag_label, True, (12, 18, 32))
        pad_x = self._s(10)
        pad_y = self._s(4)
        tag_rect = pygame.Rect(rect.x, rect.y, tag_surf.get_width() + pad_x * 2, tag_surf.get_height() + pad_y * 2)
        tag_bg = pygame.Surface(tag_rect.size, pygame.SRCALPHA)
        pygame.draw.rect(tag_bg, (*product.accent, 230), tag_bg.get_rect(), border_radius=tag_rect.height // 2)
        self.screen.blit(tag_bg, tag_rect.topleft)
        self.screen.blit(tag_surf, (tag_rect.x + pad_x, tag_rect.y + pad_y))

        # Badge chip (curated/featured/etc.) — comes from product metadata, so it
        # remains data-driven.
        badge_label = self._product_badge(product)
        badge_rect = self._draw_chip(
            tag_rect.right + self._s(8),
            tag_rect.y + (tag_rect.height - small_font.get_height() - self._s(8)) // 2,
            badge_label,
            small_font,
            product.accent,
            fill_alpha=132,
        )

        category_y = max(tag_rect.bottom, badge_rect.bottom) + self._s(8)
        category_surf = small_font.render(self._product_category(product), True, (174, 192, 222))
        self.screen.blit(category_surf, (rect.x, category_y))

        title_y = category_y + category_surf.get_height() + self._s(6)
        # Reserve up to two lines for the title; bigger font than the rail.
        title_font_big = retro_style.get_font(self._s(30), bold=True)
        title_rect = pygame.Rect(rect.x, title_y, rect.width, title_font_big.get_height() * 2 + self._s(4))
        end_y = self._draw_text_block(
            self._product_title(product),
            title_font_big,
            (250, 252, 255),
            title_rect,
            max_lines=2,
            line_spacing=self._s(2),
        )

        # Product story / pitch — feels like a curated product page.
        desc_top = end_y + self._s(8)
        desc_rect = pygame.Rect(rect.x, desc_top, rect.width, max(self._s(40), rect.bottom - desc_top - self._s(4)))
        self._draw_text_block(
            self._product_desc(product),
            body_font,
            (210, 222, 246),
            desc_rect,
            max_lines=4,
            line_spacing=self._s(4),
        )

    def _draw_hero_action_stack(
        self,
        product: StoreProduct,
        rect: pygame.Rect,
        body_font,
        small_font,
        price_font,
    ) -> None:
        """Right column: wallet pill, price/ownership block, primary CTA button.

        The old inner 'checkout plate' panel-on-panel has been removed so the
        action column reads as part of the hero panel rather than a nested
        surface. Vertical separators do the visual grouping instead.
        """
        # Subtle vertical accent line on the left edge — just enough to hint
        # at a column boundary without stacking another translucent panel.
        sep = pygame.Surface((self._s(2), rect.height), pygame.SRCALPHA)
        pygame.draw.rect(sep, (*product.accent, 70), sep.get_rect(), border_radius=self._s(1))
        self.screen.blit(sep, (rect.x - self._s(10), rect.y))

        inner = rect

        # 1) Wallet pill (premium, gold-accented)
        wallet_height = max(self._s(56), min(self._s(70), int(inner.height * 0.26)))
        wallet_rect = pygame.Rect(inner.x, inner.y, inner.width, wallet_height)
        self._draw_wallet_pill(wallet_rect, small_font)

        # 2) Price + ownership pair
        info_top = wallet_rect.bottom + self._s(14)
        cta_height = max(self._s(54), min(self._s(64), int(inner.height * 0.22)))
        cta_top = inner.bottom - cta_height
        info_rect = pygame.Rect(inner.x, info_top, inner.width, max(self._s(40), cta_top - info_top - self._s(12)))
        self._draw_hero_price_block(product, info_rect, price_font, small_font, body_font)

        # 3) Primary CTA button (records hit-zone for mouse clicks)
        cta_rect = pygame.Rect(inner.x, cta_top, inner.width, cta_height)
        self._draw_cta_button(cta_rect, product, body_font, small_font)

    def _draw_wallet_pill(self, rect: pygame.Rect, small_font) -> None:
        """Gold-accented wallet chip so currency feels meaningful, not incidental."""
        balance = self.get_fragment_balance()
        gold = (255, 214, 130)
        warm = (255, 188, 92)

        # Gradient fill
        surf = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(surf, (24, 18, 14, 220), surf.get_rect(), border_radius=self._s(14))
        for y in range(rect.height):
            mix = y / max(1, rect.height - 1)
            color = (
                int(warm[0] * (1.0 - mix) * 0.30 + 24),
                int(warm[1] * (1.0 - mix) * 0.20 + 18),
                int(warm[2] * (1.0 - mix) * 0.10 + 14),
                70,
            )
            pygame.draw.line(surf, color, (0, y), (rect.width, y))
        pygame.draw.rect(surf, (*gold, 175), surf.get_rect(), 1, border_radius=self._s(14))
        self.screen.blit(surf, rect.topleft)

        # Lunar coin on the left — sized to nearly fill the pill height so the
        # currency reads clearly instead of looking like a tiny incidental icon.
        glyph_size = max(self._s(44), min(self._s(60), rect.height - self._s(8)))
        glyph_cx = rect.x + self._s(12) + glyph_size // 2
        glyph_cy = rect.centery
        self._draw_fragment_glyph((glyph_cx, glyph_cy), glyph_size, gold)

        # Label
        label_font = retro_style.get_font(self._s(11), bold=True)
        label_surf = label_font.render(
            t('store_currency_name', default='Lunar').upper(),
            True,
            (255, 226, 168),
        )
        # Amount — biggest text in the wallet pill
        amount_font = retro_style.get_font(self._s(26), bold=True)
        amount_surf = amount_font.render(f'{int(max(0, balance))}', True, (255, 244, 210))

        text_x = glyph_cx + glyph_size // 2 + self._s(12)
        label_y = rect.y + (rect.height - label_surf.get_height() - amount_surf.get_height() - self._s(2)) // 2
        self.screen.blit(label_surf, (text_x, label_y))
        self.screen.blit(amount_surf, (text_x, label_y + label_surf.get_height() + self._s(2)))

    def _get_lunar_coin(self, size: int) -> "pygame.Surface | None":
        """Return the Lunar coin sprite scaled to ``size`` px, or ``None``.

        The artwork (``assets/ui/lunar_coin.png``) is the canonical currency
        icon. We load it lazily through the shared cache and memoise per-size
        scaled copies on the instance so the draw path allocates nothing on the
        steady state. Any failure (missing file, headless test surface) returns
        ``None`` so the caller falls back to the procedural diamond glyph.
        """
        size = max(1, int(size))
        cache = getattr(self, '_coin_scaled_cache', None)
        if cache is None:
            cache = {}
            self._coin_scaled_cache = cache
        cached = cache.get(size)
        if cached is not None:
            return cached
        if getattr(self, '_coin_load_failed', False):
            return None
        try:
            from .asset_manager import load_image as _load_image  # type: ignore
        except Exception:
            try:
                from asset_manager import load_image as _load_image  # type: ignore
            except Exception:
                self._coin_load_failed = True
                return None
        try:
            surf = _load_image(
                'assets/ui/lunar_coin.png',
                convert_alpha=True,
                size=(size, size),
            )
        except Exception:
            self._coin_load_failed = True
            return None
        cache[size] = surf
        return surf

    def _get_card_icon(self, path: str, size: int) -> "pygame.Surface | None":
        """Kart ikonunu ``size`` px ölçeğinde döndür, yoksa ``None``.

        ``_get_lunar_coin`` desenini izler: lazy-load + (path, size) bazında
        memoize. Yükleme başarısızsa None döner (çağıran fallback çizer).
        """
        if not path:
            return None
        size = max(1, int(size))
        cache = getattr(self, '_card_icon_cache', None)
        if cache is None:
            cache = {}
            self._card_icon_cache = cache
        key = (path, size)
        cached = cache.get(key)
        if cached is not None:
            return cached
        failed = getattr(self, '_card_icon_load_failed', None)
        if failed is None:
            failed = set()
            self._card_icon_load_failed = failed
        if path in failed:
            return None
        try:
            from .asset_manager import load_image as _load_image  # type: ignore
        except Exception:
            try:
                from asset_manager import load_image as _load_image  # type: ignore
            except Exception:
                failed.add(path)
                return None
        try:
            surf = _load_image(path, convert_alpha=True, size=(size, size))
        except Exception:
            failed.add(path)
            return None
        cache[key] = surf
        return surf

    def _draw_fragment_glyph(self, center: tuple[int, int], size: int, color: tuple[int, int, int]) -> None:
        """Currency icon: the Lunar coin sprite, with a diamond glyph fallback.

        ``color`` is retained for the procedural fallback (and for the muted
        empty-state tint); the coin artwork is drawn as-is when available.
        """
        cx, cy = center
        coin = self._get_lunar_coin(size)
        if coin is not None:
            self.screen.blit(coin, (cx - size // 2, cy - size // 2))
            return
        # Fallback: tiny faceted-diamond icon. Pure pygame primitives — no asset.
        half = size // 2
        outer = [
            (cx, cy - half),
            (cx + half, cy),
            (cx, cy + half),
            (cx - half, cy),
        ]
        pygame.draw.polygon(self.screen, color, outer)
        # Inner highlight facet
        inner = [
            (cx, cy - half + max(2, size // 6)),
            (cx + half - max(2, size // 5), cy),
            (cx, cy + half - max(2, size // 6)),
            (cx - half + max(2, size // 5), cy),
        ]
        highlight = (min(255, color[0] + 30), min(255, color[1] + 30), min(255, color[2] + 30))
        pygame.draw.polygon(self.screen, highlight, inner)
        # Outline
        pygame.draw.polygon(self.screen, (90, 60, 18), outer, 1)

    def _draw_hero_price_block(
        self,
        product: StoreProduct,
        rect: pygame.Rect,
        price_font,
        small_font,
        body_font,
    ) -> None:
        """Price label + ownership status, stacked above the CTA."""
        state = self._resolve_ownership_state(product)
        is_card = self._is_card_product(product)
        price_label_font = retro_style.get_font(self._s(11), bold=True)

        price_label_surf = price_label_font.render(
            t('store_price_label', default='Fiyat').upper(),
            True,
            (170, 188, 220),
        )
        self.screen.blit(price_label_surf, (rect.x, rect.y))

        # Kart ürünleri için fiyat: satın alma veya geliştirme bedeli.
        # Maks. kademede fiyat yoktur (—).
        if is_card:
            if state == 'maxed':
                price_value_text = '—'
            else:
                price_value_text = self._price_short_label(self._card_effective_price(product))
            display_price = self._card_effective_price(product)
        else:
            price_value_text = self._price_short_label(product.price)
            display_price = product.price

        # Strike-through original price if owned/equipped — implies value already captured.
        if state in ('owned', 'equipped', 'maxed'):
            price_color = (158, 174, 204)
        elif state == 'demo':
            price_color = (200, 214, 240)
        elif self.get_fragment_balance() < display_price:
            price_color = (255, 184, 184)
        else:
            price_color = (255, 232, 158)

        price_surf = price_font.render(price_value_text, True, price_color)
        price_y = rect.y + price_label_surf.get_height() + self._s(2)
        self.screen.blit(price_surf, (rect.x, price_y))

        if state in ('owned', 'equipped'):
            line_y = price_y + price_surf.get_height() // 2
            pygame.draw.line(
                self.screen,
                (255, 232, 158, 200),
                (rect.x + self._s(2), line_y),
                (rect.x + price_surf.get_width() - self._s(2), line_y),
                2,
            )

        # Ownership status row
        status_y = price_y + price_surf.get_height() + self._s(8)
        ownership_color = self._ownership_color(product)
        dot_radius = max(3, self._s(4))
        pygame.draw.circle(self.screen, ownership_color, (rect.x + dot_radius, status_y + small_font.get_height() // 2), dot_radius)
        ownership_surf = small_font.render(self._ownership_label(product), True, ownership_color)
        self.screen.blit(ownership_surf, (rect.x + dot_radius * 2 + self._s(8), status_y))

    def _draw_cta_button(
        self,
        rect: pygame.Rect,
        product: StoreProduct,
        body_font,
        small_font,
    ) -> None:
        """Primary call-to-action — color and label reflect ownership state."""
        state = self._resolve_ownership_state(product)
        balance = self.get_fragment_balance()

        # === Kart ürünleri: satın al / geliştir / maks. ===
        if self._is_card_product(product):
            self._draw_card_cta_button(rect, product, state, balance, body_font, small_font)
            return

        affordable = balance >= product.price

        if state == 'equipped':
            label = t('store_owned_equipped', default='Takılı')
            base = (96, 188, 132)
            enabled = False
        elif state == 'owned':
            label = t('store_action_equip', default='Tak')
            base = (112, 196, 255)
            enabled = True
        elif state == 'demo':
            label = t('store_action_set_default', default='Varsayılan yap')
            base = (255, 214, 122)
            enabled = True
        elif not affordable:
            label = t('store_action_locked', default='Yetersiz Parça')
            base = (180, 96, 110)
            enabled = False
        else:
            label = t('store_action_buy', default='Satın al')
            base = (255, 188, 92)
            enabled = True

        hovered = enabled and rect.collidepoint(self.mouse_pos)

        # A small accent halo when hovered telegraphs interactivity. Kept
        # tight (small padding) so it doesn't read as a second floating panel.
        if enabled and hovered:
            self._draw_soft_glow(rect, base, alpha=70, padding=self._s(4))

        surf = pygame.Surface(rect.size, pygame.SRCALPHA)
        # Vertical gradient — top brighter, bottom darker.
        top = base
        bottom = tuple(max(0, int(c * 0.55)) for c in base)
        for y in range(rect.height):
            mix = y / max(1, rect.height - 1)
            color = (
                int(top[0] * (1.0 - mix) + bottom[0] * mix),
                int(top[1] * (1.0 - mix) + bottom[1] * mix),
                int(top[2] * (1.0 - mix) + bottom[2] * mix),
                235 if enabled else 165,
            )
            pygame.draw.line(surf, color, (0, y), (rect.width, y))
        # Top sheen
        for y in range(min(self._s(8), rect.height // 3)):
            alpha = int(70 * (1 - y / max(1, self._s(8))))
            pygame.draw.line(surf, (255, 255, 255, alpha), (0, y), (rect.width, y))
        # Mask to rounded rect
        mask = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(mask, (255, 255, 255, 255), mask.get_rect(), border_radius=self._s(14))
        surf.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
        self.screen.blit(surf, rect.topleft)

        # Border
        border_color = base if enabled else (90, 100, 124)
        pygame.draw.rect(self.screen, border_color, rect, 2, border_radius=self._s(14))

        # Label
        label_font = retro_style.get_font(self._s(20), bold=True)
        label_surf = label_font.render(label, True, (16, 24, 40) if enabled else (220, 226, 240))

        # If buying, append the price inline so the CTA also functions as a confirmation amount.
        sub_label = None
        if state == 'unowned' and affordable:
            sub_font = retro_style.get_font(self._s(12), bold=True)
            sub_label = sub_font.render(self._price_short_label(product.price), True, (24, 32, 50))
        elif state == 'unowned' and not affordable:
            sub_font = retro_style.get_font(self._s(12), bold=True)
            shortfall = product.price - balance
            symbol = t('store_price_fragments_label', default='Lunar')
            sub_label = sub_font.render(f'-{shortfall} {symbol}', True, (255, 226, 232))

        if sub_label is not None:
            total_height = label_surf.get_height() + sub_label.get_height()
            top_y = rect.centery - total_height // 2
            self.screen.blit(label_surf, label_surf.get_rect(midtop=(rect.centerx, top_y)))
            self.screen.blit(sub_label, sub_label.get_rect(midtop=(rect.centerx, top_y + label_surf.get_height())))
        else:
            self.screen.blit(label_surf, label_surf.get_rect(center=rect.center))

        # Track hit-zone unconditionally. Mouse and keyboard now use the same
        # entry point: clicking the CTA in equipped/locked states still routes
        # through `_activate_selected_product`, which produces the correct
        # explanatory status message ("already equipped", "not enough fragments").
        # The button's visual `enabled` flag only controls colour and glow, not
        # interactivity.
        self._cta_rect = rect.copy()

    def _draw_card_cta_button(self, rect, product, state, balance, body_font, small_font) -> None:
        """Kart ürünü CTA'sı: Satın al / Geliştir / Maks. kademe.

        Görsel `enabled` yalnızca renk/parıltıyı etkiler; hit-zone her zaman
        kayıtlıdır (mouse ve klavye aynı `_activate_selected_product` yoluna
        gider; maxed/yetersiz durumda açıklayıcı mesaj üretilir).
        """
        price = self._card_effective_price(product)
        affordable = balance >= price
        sub_label_surf = None

        if state == 'maxed':
            label = t('store_card_action_maxed', default='Maks. Kademe')
            base = (96, 188, 132)
            enabled = False
        elif state == 'upgrade':
            if affordable:
                # Hedef enderliği etikete ekle: "Geliştir → Rare".
                nxt = self._card_next_rarity(product)
                if nxt:
                    nxt_label = t(f'store_rarity_{nxt}', default=nxt.title())
                    label = t('store_card_action_upgrade_to', default='Geliştir → {rarity}').format(rarity=nxt_label)
                else:
                    label = t('store_card_action_upgrade', default='Geliştir')
                base = (200, 140, 255)
                enabled = True
                sub_font = retro_style.get_font(self._s(12), bold=True)
                sub_label_surf = sub_font.render(self._price_short_label(price), True, (24, 32, 50))
            else:
                label = t('store_action_locked', default='Yetersiz Parça')
                base = (180, 96, 110)
                enabled = False
                sub_font = retro_style.get_font(self._s(12), bold=True)
                shortfall = price - balance
                symbol = t('store_price_fragments_label', default='Lunar')
                sub_label_surf = sub_font.render(f'-{shortfall} {symbol}', True, (255, 226, 232))
        else:  # unowned
            if affordable:
                label = t('store_card_action_buy', default='Satın al')
                base = (255, 188, 92)
                enabled = True
                sub_font = retro_style.get_font(self._s(12), bold=True)
                sub_label_surf = sub_font.render(self._price_short_label(price), True, (24, 32, 50))
            else:
                label = t('store_action_locked', default='Yetersiz Parça')
                base = (180, 96, 110)
                enabled = False
                sub_font = retro_style.get_font(self._s(12), bold=True)
                shortfall = price - balance
                symbol = t('store_price_fragments_label', default='Lunar')
                sub_label_surf = sub_font.render(f'-{shortfall} {symbol}', True, (255, 226, 232))

        hovered = enabled and rect.collidepoint(self.mouse_pos)
        if enabled and hovered:
            self._draw_soft_glow(rect, base, alpha=70, padding=self._s(4))

        surf = pygame.Surface(rect.size, pygame.SRCALPHA)
        top = base
        bottom = tuple(max(0, int(c * 0.55)) for c in base)
        for y in range(rect.height):
            mix = y / max(1, rect.height - 1)
            color = (
                int(top[0] * (1.0 - mix) + bottom[0] * mix),
                int(top[1] * (1.0 - mix) + bottom[1] * mix),
                int(top[2] * (1.0 - mix) + bottom[2] * mix),
                235 if enabled else 165,
            )
            pygame.draw.line(surf, color, (0, y), (rect.width, y))
        for y in range(min(self._s(8), rect.height // 3)):
            alpha = int(70 * (1 - y / max(1, self._s(8))))
            pygame.draw.line(surf, (255, 255, 255, alpha), (0, y), (rect.width, y))
        mask = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(mask, (255, 255, 255, 255), mask.get_rect(), border_radius=self._s(14))
        surf.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
        self.screen.blit(surf, rect.topleft)

        border_color = base if enabled else (90, 100, 124)
        pygame.draw.rect(self.screen, border_color, rect, 2, border_radius=self._s(14))

        label_font = retro_style.get_font(self._s(20), bold=True)
        label_surf = label_font.render(label, True, (16, 24, 40) if enabled else (220, 226, 240))

        if sub_label_surf is not None:
            total_height = label_surf.get_height() + sub_label_surf.get_height()
            top_y = rect.centery - total_height // 2
            self.screen.blit(label_surf, label_surf.get_rect(midtop=(rect.centerx, top_y)))
            self.screen.blit(sub_label_surf, sub_label_surf.get_rect(midtop=(rect.centerx, top_y + label_surf.get_height())))
        else:
            self.screen.blit(label_surf, label_surf.get_rect(center=rect.center))

        self._cta_rect = rect.copy()

    def _draw_collection_rail(self, rect, title_font, body_font, small_font, price_font) -> None:
        """Lower rail: section header + card collection. Hero is the spotlight; this is the shelf."""
        retro_style.draw_glass_panel(
            self.screen,
            rect,
            alpha=170,
            border_color=retro_style.primary,
            glow=False,
        )
        # Generous corner padding around the rail content.
        inner = rect.inflate(-self._s(24), -self._s(20))

        header_height = self._s(52)
        header_rect = pygame.Rect(inner.x, inner.y, inner.width, header_height)
        self._draw_rail_header(header_rect, title_font, small_font)

        grid_rect = pygame.Rect(
            inner.x,
            header_rect.bottom + self._s(10),
            inner.width,
            inner.bottom - header_rect.bottom - self._s(10),
        )
        self._last_grid_viewport = grid_rect.copy()

        columns = self._get_column_count(grid_rect.width)
        card_gap = self._s(14)
        # Floor card width to a sane minimum so we never collapse below
        # something readable; the column count already guarantees fit, so
        # this just clamps very narrow viewports.
        card_width = max(self._s(170), (grid_rect.width - card_gap * (columns - 1)) // columns)
        # Rail cards are intentionally shorter than the old grid — hero owns the spotlight.
        card_height = self._get_rail_card_height(card_width, grid_rect.height)

        # Only the products on the active category page are laid out. Grid
        # positions are dense over the *visible* set; the absolute product
        # index is preserved so selection/CTA/ownership all keep working on
        # ``self.products``. ``card_rects`` stays parallel to ``self.products``
        # — hidden products get an empty rect so collision/hover logic simply
        # never matches them.
        visible = self._visible_indices or list(range(len(self.products)))
        visible_count = len(visible)
        row_count = max(1, (visible_count + columns - 1) // columns)

        self._last_columns = columns
        self._last_card_height = card_height
        self._last_row_step = card_height + card_gap

        content_height = row_count * card_height + (row_count - 1) * card_gap
        self.max_grid_scroll = max(0, content_height - grid_rect.height)
        self.grid_scroll = max(0, min(self.max_grid_scroll, self.grid_scroll))
        self.card_rects = [pygame.Rect(0, 0, 0, 0) for _ in self.products]

        previous_clip = self.screen.get_clip()
        self.screen.set_clip(grid_rect)
        try:
            for grid_pos, index in enumerate(visible):
                product = self.products[index]
                row = grid_pos // columns
                col = grid_pos % columns
                card_rect = pygame.Rect(
                    grid_rect.x + col * (card_width + card_gap),
                    grid_rect.y + row * (card_height + card_gap) - self.grid_scroll,
                    card_width,
                    card_height,
                )
                self.card_rects[index] = card_rect
                if card_rect.bottom < grid_rect.y - card_height or card_rect.top > grid_rect.bottom + card_height:
                    continue
                hovered = card_rect.collidepoint(self.mouse_pos)
                self._draw_product_card(
                    card_rect,
                    product,
                    selected=index == self.selected_index,
                    hovered=hovered,
                    title_font=title_font,
                    body_font=body_font,
                    small_font=small_font,
                    price_font=price_font,
                )
        finally:
            self.screen.set_clip(previous_clip)

        if self.max_grid_scroll > 0:
            self._draw_scrollbar(rect, grid_rect)

    def _draw_rail_header(self, rect: pygame.Rect, title_font, small_font) -> None:
        """Section header for the collection rail."""
        # Accent bar on the left so the header reads like a curated section title.
        accent_w = self._s(4)
        bar_rect = pygame.Rect(rect.x, rect.y + self._s(4), accent_w, rect.height - self._s(8))
        bar_surf = pygame.Surface(bar_rect.size, pygame.SRCALPHA)
        pygame.draw.rect(bar_surf, (*retro_style.accent, 220), bar_surf.get_rect(), border_radius=accent_w // 2)
        self.screen.blit(bar_surf, bar_rect.topleft)

        title_x = bar_rect.right + self._s(12)
        # Section title tracks the active category so the rail header and the
        # tab bar always agree on which page is open.
        category = self.categories[self.active_category] if self.categories else None
        if category is not None:
            title_text = self._category_label(category)
        else:
            title_text = t('store_collection_title', default='Luna-Cat İz Koleksiyonu')
        title_surf = title_font.render(title_text, True, (244, 248, 255))
        self.screen.blit(title_surf, (title_x, rect.y + self._s(2)))

        sub_text = t('store_collection_subtitle', default='Satır temizleme kozmetikleri')
        sub_surf = small_font.render(sub_text, True, (170, 188, 218))
        self.screen.blit(sub_surf, (title_x, rect.y + title_surf.get_height() + self._s(2)))

        # Right-aligned chips: count + position indicator, scoped to the
        # active page (visible set) rather than the whole catalogue.
        visible = self._visible_indices or list(range(len(self.products)))
        visible_count = len(visible)
        try:
            visible_pos = visible.index(self.selected_index) + 1
        except ValueError:
            visible_pos = min(1, visible_count)
        right_y = rect.y + (rect.height - small_font.get_height() - self._s(8)) // 2
        position_label = f'{visible_pos}/{max(1, visible_count)}'
        pos_x = self._draw_chip_right(
            rect.right,
            right_y,
            position_label,
            small_font,
            (240, 244, 255),
            fill_alpha=132,
        )
        self._draw_chip_right(
            pos_x - self._s(8),
            right_y,
            self._trf('store_count_label', '{count} ürün', count=visible_count),
            small_font,
            (200, 216, 244),
            fill_alpha=120,
        )

    def _get_rail_card_height(self, card_width: int, available_height: int) -> int:
        """Rail cards are compact: preview-led with a slim info strip below."""
        target = int(card_width * 0.78)
        target = max(self._s(170), min(self._s(220), target))
        # Don't exceed the rail viewport — keep at least a single row visible cleanly.
        return min(target, max(self._s(150), available_height - self._s(4)))

    def _draw_product_card(
        self,
        rect: pygame.Rect,
        product: StoreProduct,
        *,
        selected: bool,
        hovered: bool,
        title_font,
        body_font,
        small_font,
        price_font,
    ) -> None:
        """Compact rail card: preview-led, just enough text to scan and pick.

        The hero now carries description and CTA, so the card focuses on visual
        recognition and a clear price/ownership read.
        """
        accent = product.accent

        # Card border colour reflects selection — selected uses the product
        # accent at full strength, others are dimmed so the spotlight is
        # unambiguous. The old bright halos and white outline that floated
        # above the panel have been removed for a cleaner shop feel.
        border_color = accent if selected else (
            tuple(max(80, min(220, int(value * 0.55 + 36))) for value in accent)
        )
        retro_style.draw_glass_panel(
            self.screen,
            rect,
            alpha=200 if selected else 178 if hovered else 154,
            border_color=border_color,
            glow=False,
        )
        # Selected card gets a slightly thicker accent border to read as the
        # active item without resorting to a separate overlay rectangle.
        if selected:
            pygame.draw.rect(self.screen, accent, rect, 2, border_radius=self._s(12))
        # Comfortable inner padding so the preview never crowds the corners.
        inner = rect.inflate(-self._s(14), -self._s(14))

        # Preview occupies roughly the upper two-thirds — most recognisable surface.
        preview_height = max(self._s(80), int(inner.height * 0.62))
        preview_rect = pygame.Rect(inner.x, inner.y, inner.width, preview_height)
        self._draw_product_preview(product, preview_rect, hero=False)

        # Status pill on the preview tells "Owned/Equipped/Default/Available" at a glance.
        state = self._resolve_ownership_state(product)
        status_label = self._ownership_label(product)
        status_color = self._ownership_color(product)
        self._draw_status_corner_pill(
            preview_rect.right - self._s(6),
            preview_rect.y + self._s(6),
            status_label,
            small_font,
            status_color,
            state,
        )

        # "Yeni" badge at the top-LEFT for newly added traces (top-right is
        # taken by the status pill). Data-driven (``product.is_new``) and
        # accent-tinted so it draws the eye without faking urgency.
        if getattr(product, 'is_new', False):
            self._draw_new_badge(
                preview_rect.x + self._s(6),
                preview_rect.y + self._s(6),
                small_font,
            )

        # Title strip — single line, ellipsised if needed.
        title_y = preview_rect.bottom + self._s(8)
        card_title_font = retro_style.get_font(self._s(15), bold=True)
        title_rect = pygame.Rect(inner.x, title_y, inner.width, card_title_font.get_height())
        self._draw_text_block(
            self._product_title(product),
            card_title_font,
            (244, 248, 255),
            title_rect,
            max_lines=1,
            line_spacing=0,
        )

        # Bottom strip: price (with Lunar chip) on the left.
        is_card = self._is_card_product(product)
        if is_card:
            effective_price = self._card_effective_price(product)
            price_label = self._price_short_label(effective_price)
        else:
            price_label = self._price_short_label(product.price)
        price_text_font = retro_style.get_font(self._s(15), bold=True)
        if is_card:
            if state == 'maxed':
                # Sahip + tavan: onay işareti + maks. ipucu.
                price_label = '\u2713 ' + t('store_card_status_maxed', default='Maks. kademe')
                price_color = status_color
            elif state == 'upgrade':
                # Sahip ama geliştirilebilir: geliştirme bedelini göster.
                price_color = (210, 170, 255)
            else:  # unowned
                price_color = (255, 232, 158)
        elif state in ('owned', 'equipped'):
            # Shorten price to a check-mark style cue when already in inventory.
            price_label = '\u2713 ' + (
                t('store_owned_label', default='Sahip olundu')
                if state == 'owned'
                else t('store_owned_equipped', default='Takılı')
            )
            price_color = status_color
        elif state == 'demo':
            price_color = (255, 224, 162)
        else:
            price_color = (255, 232, 158)

        price_y = inner.bottom - price_text_font.get_height() - self._s(2)
        price_max_width = inner.width
        price_text = price_label if price_text_font.size(price_label)[0] <= price_max_width else self._ellipsize(price_text_font, price_label, price_max_width)
        price_surf = price_text_font.render(price_text, True, price_color)
        self.screen.blit(price_surf, (inner.x, price_y))

    def _draw_status_corner_pill(
        self,
        right_x: int,
        y: int,
        label: str,
        font,
        color: tuple[int, int, int],
        state: str,
    ) -> None:
        """Top-right ownership pill on a card preview. Colour cues the state."""
        text_surf = font.render(label, True, (12, 18, 32) if state in ('equipped', 'demo') else (240, 246, 255))
        pad_x = self._s(8)
        pad_y = self._s(3)
        rect = pygame.Rect(0, 0, text_surf.get_width() + pad_x * 2, text_surf.get_height() + pad_y * 2)
        rect.topright = (right_x, y)

        if state in ('equipped', 'demo'):
            fill = (*color, 235)
        else:
            fill = (10, 16, 32, 210)

        chip = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(chip, fill, chip.get_rect(), border_radius=rect.height // 2)
        pygame.draw.rect(chip, (*color, 200), chip.get_rect(), 1, border_radius=rect.height // 2)
        self.screen.blit(chip, rect.topleft)
        self.screen.blit(text_surf, (rect.x + pad_x, rect.y + pad_y))

    def _draw_new_badge(self, x: int, y: int, font) -> None:
        """Top-left 'Yeni' badge for newly added traces.

        Accent-filled pill with a small leading dot so it reads as a positive
        'new arrival' marker — eye-catching but not a fake-urgency device. Uses
        the shared ``store_badge_new`` localization key.
        """
        accent = retro_style.accent
        label = t('store_badge_new', default='Yeni')
        text_surf = font.render(label, True, (16, 22, 36))
        pad_x = self._s(8)
        pad_y = self._s(3)
        dot_r = max(2, self._s(3))
        dot_gap = self._s(5)
        width = dot_r * 2 + dot_gap + text_surf.get_width() + pad_x * 2
        height = text_surf.get_height() + pad_y * 2
        rect = pygame.Rect(x, y, width, height)

        chip = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(chip, (*accent, 240), chip.get_rect(), border_radius=height // 2)
        pygame.draw.rect(chip, (255, 255, 255, 90), chip.get_rect(), 1, border_radius=height // 2)
        self.screen.blit(chip, rect.topleft)

        dot_cx = rect.x + pad_x + dot_r
        dot_cy = rect.centery
        pygame.draw.circle(self.screen, (28, 36, 52), (dot_cx, dot_cy), dot_r)
        self.screen.blit(text_surf, (dot_cx + dot_r + dot_gap, rect.y + pad_y))

    def _draw_footer(self, rect, body_font, small_font, *, two_row: bool = False) -> None:
        """Deprecated. The shop UI no longer renders a footer panel.

        Kept as a no-op so older callers and tests that reference the
        function name don't crash. The status_message is still updated via
        :meth:`_activate_selected_product` and tests assert on it directly.
        """
        return None

    def _draw_chip(
        self,
        x: int,
        y: int,
        label: str,
        font,
        color: tuple[int, int, int],
        *,
        fill_alpha: int = 122,
    ) -> pygame.Rect:
        text_surf = font.render(label, True, color)
        pad_x = max(8, self._s(8))
        pad_y = max(4, self._s(4))
        rect = pygame.Rect(x, y, text_surf.get_width() + pad_x * 2, text_surf.get_height() + pad_y * 2)
        chip_surf = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(chip_surf, (12, 20, 38, fill_alpha), chip_surf.get_rect(), border_radius=self._s(9))
        pygame.draw.rect(chip_surf, (*color, 150), chip_surf.get_rect(), 1, border_radius=self._s(9))
        self.screen.blit(chip_surf, rect.topleft)
        self.screen.blit(text_surf, (rect.x + pad_x, rect.y + pad_y))
        return rect

    def _draw_chip_right(
        self,
        right_x: int,
        y: int,
        label: str,
        font,
        color: tuple[int, int, int],
        *,
        fill_alpha: int = 122,
    ) -> int:
        text_surf = font.render(label, True, color)
        pad_x = max(8, self._s(8))
        width = text_surf.get_width() + pad_x * 2
        rect = self._draw_chip(right_x - width, y, label, font, color, fill_alpha=fill_alpha)
        return rect.x

    def _draw_product_preview(self, product: StoreProduct, rect: pygame.Rect, *, hero: bool) -> None:
        # Kart ürünleri kendi önizlemesini kullanır (Luna-Cat/iz değil; kart ikonu).
        if self._is_card_product(product):
            self._draw_card_product_preview(product, rect, hero=hero)
            return
        if self._is_block_skin_product(product):
            self._draw_block_product_preview(product, rect, hero=hero)
            return
        preview = pygame.Surface(rect.size, pygame.SRCALPHA)
        radius = self._s(14 if hero else 12)
        # Deep arcade-cabinet base — matches the game's neon-on-dark theme.
        pygame.draw.rect(preview, (6, 10, 22, 230), preview.get_rect(), border_radius=radius)
        self._draw_preview_backdrop(preview, product, hero)

        # Board sits centred with comfortable margins. Hero gets more breathing
        # room than the rail cards so the trail and Luna-Cat read clearly.
        board_margin_x = self._s(20 if hero else 14)
        board_margin_y = self._s(20 if hero else 14)
        board_height = max(self._s(64), int(rect.height * (0.52 if hero else 0.46)))
        board_rect = pygame.Rect(
            board_margin_x,
            board_margin_y + max(0, (rect.height - board_height - board_margin_y * 2) // 2),
            max(self._s(140), rect.width - board_margin_x * 2),
            board_height,
        )
        self._draw_preview_board(preview, board_rect, product.accent)

        phase = ((pygame.time.get_ticks() // 120) + self._product_phase_seed(product)) % 8
        cat_target_h = int(board_rect.height * (0.92 if hero else 0.82))
        # Pet products preview their own animated sprite in place of the cat;
        # everything else keeps the walking Luna-Cat.
        pet_value = None
        if getattr(product, 'is_pet', False):
            payload = product.cosmetic_payload or {}
            pet_value = str(payload.get('value') or '')
        cat_surface = self._sweep_cat_state.get_companion_surface(
            board_rect.width, cat_target_h, phase, pet_value
        )
        cat_x = board_rect.x + int(board_rect.width * (0.62 if hero else 0.58))
        trail_left = board_rect.x + self._s(8)

        if cat_surface is not None:
            cat_x = min(board_rect.right - cat_surface.get_width() - self._s(8), cat_x)
            cat_y = board_rect.centery - cat_surface.get_height() // 2
            head_attach_x = cat_x + max(1, int(cat_surface.get_width() * 0.86))
        else:
            cat_y = board_rect.y
            head_attach_x = board_rect.centerx

        trail_height = max(self._s(24), int(board_rect.height * (0.52 if hero else 0.50)))
        trail_rect = pygame.Rect(
            trail_left,
            board_rect.centery - trail_height // 2,
            max(self._s(44), head_attach_x - trail_left),
            trail_height,
        )
        self._draw_preview_trail(preview, trail_rect, product)

        if cat_surface is not None:
            shadow_rect = cat_surface.get_rect(topleft=(cat_x, cat_y + self._s(3)))
            shadow = pygame.Surface(shadow_rect.size, pygame.SRCALPHA)
            pygame.draw.ellipse(shadow, (0, 0, 0, 72), shadow.get_rect().inflate(-self._s(16), -self._s(8)))
            preview.blit(shadow, shadow_rect.topleft)
            preview.blit(cat_surface, (cat_x, cat_y))

        # Crisp accent border with an inner highlight for the neon-bezel feel.
        pygame.draw.rect(preview, (*product.accent, 150), preview.get_rect(), 2, border_radius=radius)
        pygame.draw.rect(preview, (255, 255, 255, 22), preview.get_rect().inflate(-2, -2), 1, border_radius=max(1, radius - 1))
        self.screen.blit(preview, rect.topleft)

    def _draw_card_product_preview(self, product: StoreProduct, rect: pygame.Rect, *, hero: bool) -> None:
        """Kart ürünü önizlemesi: enderlik renkli zemin + kartın kendi ikonu.

        Kozmetiklerdeki Luna-Cat / satır-izi çizimi KULLANILMAZ. İkon yoksa
        kart adının baş harfiyle bir rozet fallback'i çizilir.
        """
        # Accent rengi kartın O ANKİ kademesinin enderliğinden gelir; geliştirilmiş
        # kart mevcut kademe renginde görünür. product.accent (frozen) DEĞİŞMEZ —
        # yalnızca çizimde yerel `accent` kullanılır.
        rarity = self._card_current_rarity(product)
        accent = _CARD_RARITY_ACCENTS.get(rarity, product.accent)
        preview = pygame.Surface(rect.size, pygame.SRCALPHA)
        radius = self._s(14 if hero else 12)

        # 1) Koyu taban + enderlik renginden dikey degrade.
        pygame.draw.rect(preview, (6, 10, 22, 235), preview.get_rect(), border_radius=radius)
        width, height = rect.size
        top_color = tuple(min(255, int(c * 0.40 + 24)) for c in accent)
        bottom_color = (4, 8, 18)
        grad = pygame.Surface((width, height), pygame.SRCALPHA)
        for y in range(height):
            mix = y / max(1, height - 1)
            color = (
                int(top_color[0] * (1.0 - mix) + bottom_color[0] * mix),
                int(top_color[1] * (1.0 - mix) + bottom_color[1] * mix),
                int(top_color[2] * (1.0 - mix) + bottom_color[2] * mix),
                180,
            )
            pygame.draw.line(grad, color, (0, y), (width, y))
        # Degradeyi yuvarlatılmış köşelere maskele.
        mask = pygame.Surface((width, height), pygame.SRCALPHA)
        pygame.draw.rect(mask, (255, 255, 255, 255), mask.get_rect(), border_radius=radius)
        grad.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
        preview.blit(grad, (0, 0))

        # 2) Hafif bir merkez ışıması (ikon arkasında derinlik hissi).
        glow_size = int(min(width, height) * (0.72 if hero else 0.66))
        if glow_size > 0:
            glow = pygame.Surface((glow_size, glow_size), pygame.SRCALPHA)
            pygame.draw.ellipse(glow, (*accent, 60), glow.get_rect())
            preview.blit(glow, (width // 2 - glow_size // 2, height // 2 - glow_size // 2))

        # 3) Kartın ikonu, merkeze hizalı.
        icon_size = int(min(width, height) * (0.56 if hero else 0.50))
        icon_size = max(self._s(28), icon_size)
        icon_surf = self._get_card_icon(getattr(product, 'card_icon', None), icon_size)
        if icon_surf is not None:
            ix = width // 2 - icon_surf.get_width() // 2
            iy = height // 2 - icon_surf.get_height() // 2
            # Yumuşak gölge.
            shadow = pygame.Surface(icon_surf.get_size(), pygame.SRCALPHA)
            shadow.blit(icon_surf, (0, 0))
            shadow.fill((0, 0, 0, 90), special_flags=pygame.BLEND_RGBA_MULT)
            preview.blit(shadow, (ix + self._s(2), iy + self._s(3)))
            preview.blit(icon_surf, (ix, iy))
        else:
            # Fallback: enderlik renginde daire + kart adının baş harfi.
            badge_r = max(self._s(18), icon_size // 2)
            cx, cy = width // 2, height // 2
            pygame.draw.circle(preview, (*accent, 220), (cx, cy), badge_r)
            pygame.draw.circle(preview, (255, 255, 255, 40), (cx, cy), badge_r, 2)
            title = self._product_title(product) or '?'
            letter = title.strip()[:1].upper() if title.strip() else '?'
            letter_font = retro_style.get_font(max(self._s(20), badge_r), bold=True)
            letter_surf = letter_font.render(letter, True, (16, 24, 40))
            preview.blit(letter_surf, letter_surf.get_rect(center=(cx, cy)))

        # 4) Enderlik etiketi (üst-sol küçük şerit). Geliştirme durumunda
        # "Mevcut → Hedef" geçişini göster.
        state = self._resolve_ownership_state(product)
        cur_rarity = self._card_current_rarity(product)
        cur_label = t(f'store_rarity_{cur_rarity}', default=cur_rarity.title()) if cur_rarity else ''
        if state == 'upgrade' and self._card_next_rarity(product):
            nxt_rarity = self._card_next_rarity(product)
            nxt_label = t(f'store_rarity_{nxt_rarity}', default=nxt_rarity.title())
            rarity_label = f'{cur_label} → {nxt_label}'
        else:
            rarity_label = cur_label
        if rarity_label:
            chip_font = retro_style.get_font(self._s(11), bold=True)
            chip_surf = chip_font.render(rarity_label, True, (12, 18, 32))
            pad_x = self._s(8)
            pad_y = self._s(3)
            chip_rect = pygame.Rect(self._s(8), self._s(8),
                                    chip_surf.get_width() + pad_x * 2,
                                    chip_surf.get_height() + pad_y * 2)
            chip_bg = pygame.Surface(chip_rect.size, pygame.SRCALPHA)
            pygame.draw.rect(chip_bg, (*accent, 230), chip_bg.get_rect(), border_radius=chip_rect.height // 2)
            preview.blit(chip_bg, chip_rect.topleft)
            preview.blit(chip_surf, (chip_rect.x + pad_x, chip_rect.y + pad_y))

        # 5) Accent border + inner highlight (kozmetik önizlemeyle aynı stil).
        pygame.draw.rect(preview, (*accent, 150), preview.get_rect(), 2, border_radius=radius)
        pygame.draw.rect(preview, (255, 255, 255, 22), preview.get_rect().inflate(-2, -2), 1, border_radius=max(1, radius - 1))
        self.screen.blit(preview, rect.topleft)

    def _draw_block_product_preview(self, product: StoreProduct, rect: pygame.Rect, *, hero: bool) -> None:
        preview = pygame.Surface(rect.size, pygame.SRCALPHA)
        radius = self._s(14 if hero else 12)
        pygame.draw.rect(preview, (6, 10, 22, 235), preview.get_rect(), border_radius=radius)
        self._draw_preview_backdrop(preview, product, hero)

        board_margin_x = self._s(18 if hero else 12)
        board_margin_y = self._s(18 if hero else 12)
        board_height = max(self._s(88), int(rect.height * (0.66 if hero else 0.58)))
        board_rect = pygame.Rect(
            board_margin_x,
            board_margin_y + max(0, (rect.height - board_height - board_margin_y * 2) // 2),
            max(self._s(140), rect.width - board_margin_x * 2),
            board_height,
        )
        self._draw_preview_board(preview, board_rect, product.accent)

        payload = product.cosmetic_payload or {}
        appearance = _appearance_for_block_skin(payload.get('value'))
        cell = max(self._s(16), min(board_rect.width // 6, board_rect.height // 4))
        step = cell + self._s(2)
        block_size = max(self._s(12), cell - self._s(2))

        samples = (
            (
                [(0, 1), (1, 1), (2, 1), (1, 0)],
                (140, 104, 255),
                board_rect.x + self._s(12),
                board_rect.y + self._s(12),
            ),
            (
                [(0, 0), (1, 0), (1, 1), (2, 1)],
                (90, 220, 255),
                board_rect.x + board_rect.width // 2 - step,
                board_rect.y + board_rect.height // 2 - step,
            ),
            (
                [(0, 0), (0, 1), (1, 1), (2, 1)],
                (255, 174, 88),
                board_rect.right - self._s(12) - step * 3,
                board_rect.y + self._s(18),
            ),
        )
        for cells, color, start_x, start_y in samples:
            for rel_x, rel_y in cells:
                draw_jelly_block(
                    preview,
                    start_x + rel_x * step,
                    start_y + rel_y * step,
                    block_size,
                    color,
                    appearance=appearance,
                )

        chip_font = retro_style.get_font(self._s(11), bold=True)
        subtitle = t('store_block_preview_chip', default='Blok Onizleme')
        chip_surf = chip_font.render(subtitle, True, (12, 18, 32))
        pad_x = self._s(8)
        pad_y = self._s(3)
        chip_rect = pygame.Rect(
            self._s(8),
            self._s(8),
            chip_surf.get_width() + pad_x * 2,
            chip_surf.get_height() + pad_y * 2,
        )
        chip_bg = pygame.Surface(chip_rect.size, pygame.SRCALPHA)
        pygame.draw.rect(chip_bg, (*product.accent, 230), chip_bg.get_rect(), border_radius=chip_rect.height // 2)
        preview.blit(chip_bg, chip_rect.topleft)
        preview.blit(chip_surf, (chip_rect.x + pad_x, chip_rect.y + pad_y))

        pygame.draw.rect(preview, (*product.accent, 150), preview.get_rect(), 2, border_radius=radius)
        pygame.draw.rect(preview, (255, 255, 255, 22), preview.get_rect().inflate(-2, -2), 1, border_radius=max(1, radius - 1))
        self.screen.blit(preview, rect.topleft)

    def _draw_preview_backdrop(self, surface: pygame.Surface, product: StoreProduct, hero: bool) -> None:
        width, height = surface.get_size()
        bg = pygame.Surface((width, height), pygame.SRCALPHA)
        # Dimmer top so the accent never overpowers the on-board content.
        top_color = tuple(min(255, int(component * 0.35 + 30)) for component in product.accent)
        bottom_color = (4, 8, 18)
        for y in range(height):
            mix = y / max(1, height - 1)
            color = (
                int(top_color[0] * (1.0 - mix) + bottom_color[0] * mix),
                int(top_color[1] * (1.0 - mix) + bottom_color[1] * mix),
                int(top_color[2] * (1.0 - mix) + bottom_color[2] * mix),
                170,
            )
            pygame.draw.line(bg, color, (0, y), (width, y))
        surface.blit(bg, (0, 0))

        # Horizon line — simple but instantly reads as 'arcade screen'.
        horizon_y = int(height * 0.62)
        pygame.draw.line(surface, (*product.accent, 90), (0, horizon_y), (width, horizon_y), 1)

        # A few softly drifting orbs add depth without competing with the trail.
        orbs = (
            (0.20, 0.22, 0.10),
            (0.46, 0.16, 0.08),
            (0.66, 0.26, 0.10),
        )
        for px, py, ratio in orbs:
            orb_rect = pygame.Rect(0, 0, int(width * ratio * (1.25 if hero else 1.0)), int(width * ratio))
            orb_rect.center = (int(width * px), int(height * py))
            pygame.draw.ellipse(surface, (*product.accent, 32), orb_rect)

        # Subtle scanlines tie the preview into the game's CRT-style retro look.
        scan_step = max(2, self._s(3))
        for y in range(0, height, scan_step):
            pygame.draw.line(surface, (0, 0, 0, 28), (0, y), (width, y), 1)

    def _draw_preview_board(self, surface: pygame.Surface, rect: pygame.Rect, accent: tuple[int, int, int]) -> None:
        board = pygame.Surface(rect.size, pygame.SRCALPHA)
        # Slightly translucent inset surface so grid + trail stand out.
        pygame.draw.rect(board, (10, 16, 32, 200), board.get_rect(), border_radius=self._s(10))

        # Tetromino-grid hint — 10 columns × 4 rows, like a slim play-field.
        columns = 10
        rows = 4
        for index in range(1, columns):
            x = int(index * rect.width / columns)
            pygame.draw.line(board, (255, 255, 255, 18), (x, self._s(6)), (x, rect.height - self._s(6)), 1)
        for index in range(1, rows):
            y = int(index * rect.height / rows)
            pygame.draw.line(board, (255, 255, 255, 18), (self._s(6), y), (rect.width - self._s(6), y), 1)

        # Inner accent bezel — keeps the board feeling like a small play-field.
        pygame.draw.rect(board, (*accent, 110), board.get_rect(), 2, border_radius=self._s(10))
        pygame.draw.rect(board, (255, 255, 255, 28), board.get_rect().inflate(-2, -2), 1, border_radius=max(1, self._s(9)))
        surface.blit(board, rect.topleft)

    def _draw_preview_trail(self, surface: pygame.Surface, rect: pygame.Rect, product: StoreProduct) -> None:
        # Soft accent halo behind the trail — kept very subtle so it doesn't
        # mimic the panel-on-panel "bright plate" we deliberately removed.
        glow_rect = rect.inflate(self._s(14), self._s(8))
        glow = pygame.Surface(glow_rect.size, pygame.SRCALPHA)
        pygame.draw.rect(glow, (*product.accent, 30), glow.get_rect(), border_radius=self._s(14))
        surface.blit(glow, glow_rect.topleft)

        # Pass the same phase the cat preview uses so the flag overlays
        # (twinkling stars, drifting highlights, rotating sun rays) animate
        # in sync with the cat — both are time-driven via pygame.time.
        phase = ((pygame.time.get_ticks() // 120) + self._product_phase_seed(product)) % 8
        draw_line_sweep_band(
            surface,
            rect,
            theme=product.preview_theme,
            stripe_highlight_enabled=False,
            border_radius=self._s(8),
            border_color=product.accent,
            border_alpha=90,
            phase=phase,
        )

    def _preview_palette(self, product: StoreProduct) -> list[tuple[int, int, int]]:
        theme = product.preview_theme
        if theme == 'rainbow':
            return [
                (255, 88, 112),
                (255, 162, 92),
                (255, 228, 110),
                (112, 222, 150),
                (98, 178, 255),
                (146, 112, 255),
            ]
        if theme == 'usa':
            return [
                (226, 68, 74),
                (244, 244, 244),
                (226, 68, 74),
                (244, 244, 244),
                (226, 68, 74),
            ]
        if theme == 'turkiye':
            return [(217, 42, 54)] * 5
        if theme == 'russia':
            return [
                (245, 245, 245),
                (76, 118, 223),
                (220, 66, 72),
            ]
        if theme == 'japan':
            return [(248, 248, 248)] * 4
        return [product.accent] * 4

    def _draw_star(self, surface: pygame.Surface, center: tuple[int, int], radius: int, color: tuple[int, int, int]) -> None:
        cx, cy = center
        points = []
        outer = max(2, radius)
        inner = max(1, int(radius * 0.45))
        for index in range(10):
            angle = -90 + index * 36
            current_radius = outer if index % 2 == 0 else inner
            vector = pygame.math.Vector2(current_radius, 0).rotate(angle)
            points.append((cx + vector.x, cy + vector.y))
        if len(points) >= 3:
            pygame.draw.polygon(surface, color, points)

    def _draw_scrollbar(self, outer_rect: pygame.Rect, inner_rect: pygame.Rect) -> None:
        track_width = self._s(10)
        track_rect = pygame.Rect(
            outer_rect.right - track_width - self._s(8),
            inner_rect.y,
            track_width,
            inner_rect.height,
        )
        track_surf = pygame.Surface(track_rect.size, pygame.SRCALPHA)
        pygame.draw.rect(track_surf, (14, 20, 35, 160), track_surf.get_rect(), border_radius=track_width // 2)
        self.screen.blit(track_surf, track_rect.topleft)

        thumb_height = max(self._s(42), int(track_rect.height * (inner_rect.height / max(inner_rect.height, inner_rect.height + self.max_grid_scroll))))
        thumb_y = track_rect.y
        if self.max_grid_scroll > 0:
            thumb_y += int((track_rect.height - thumb_height) * (self.grid_scroll / self.max_grid_scroll))
        thumb_rect = pygame.Rect(track_rect.x, thumb_y, track_rect.width, thumb_height)
        thumb_surf = pygame.Surface(thumb_rect.size, pygame.SRCALPHA)
        pygame.draw.rect(thumb_surf, (126, 168, 238, 180), thumb_surf.get_rect(), border_radius=track_width // 2)
        self.screen.blit(thumb_surf, thumb_rect.topleft)

    def _draw_soft_glow(self, rect: pygame.Rect, color: tuple[int, int, int], *, alpha: int, padding: int) -> None:
        glow_rect = rect.inflate(padding * 2, padding * 2)
        glow = pygame.Surface(glow_rect.size, pygame.SRCALPHA)
        pygame.draw.rect(glow, (*color, alpha), glow.get_rect(), border_radius=self._s(18))
        self.screen.blit(glow, glow_rect.topleft)

    def _product_title(self, product: StoreProduct) -> str:
        if self._is_card_product(product):
            return self._card_title(product)
        return self._translate(product.title_key, product.fallback_title)

    def _product_desc(self, product: StoreProduct) -> str:
        if self._is_card_product(product):
            return self._card_desc(product)
        return self._translate(product.desc_key, product.fallback_desc)

    def _product_category(self, product: StoreProduct) -> str:
        if self._is_card_product(product):
            # Sahipliğe göre "Kartlar" / "Kartları Geliştir".
            if self._card_is_upgrade_action(product):
                return t('store_category_card_upgrades', default='Kartları Geliştir')
            return t('store_category_cards', default='Kartlar')
        return self._translate(product.category_key, product.fallback_category)

    def _product_badge(self, product: StoreProduct) -> str:
        if self._is_card_product(product):
            # Enderlik etiketini rozet olarak göster.
            return self._card_rarity_label(product)
        return self._translate(product.badge_key, product.fallback_badge)

    def _product_status(self, product: StoreProduct) -> str:
        if self._is_card_product(product):
            state = self._resolve_ownership_state(product)
            if state == 'maxed':
                return t('store_card_status_maxed', default='Maks. kademe')
            if state == 'upgrade':
                return t('store_card_status_owned', default='Sahip — geliştirilebilir')
            return t('store_status_available', default='Alınabilir')
        return self._translate(product.status_key, product.fallback_status)

    def _card_rarity_label(self, product: StoreProduct) -> str:
        """Kartın O ANKİ kademesinin enderlik etiketi (yerelleştirilmiş).

        Renk eşleşmesine GÜVENMEZ; gerçek tier→rarity verisini kullanır, böylece
        geliştirme sonrası (örn. Uncommon → Rare) doğru enderliği yansıtır.
        """
        rarity = self._card_current_rarity(product)
        if not rarity:
            return ''
        return t(f'store_rarity_{rarity}', default=rarity.title())

    def _translate(self, key: str | None, fallback: str) -> str:
        if key:
            return t(key, default=fallback)
        return fallback

    def _price_short_label(self, price: int) -> str:
        symbol = t('store_price_fragments_label', default='Lunar')
        return f'{int(max(0, price))} {symbol}'

    def _ownership_label(self, product: StoreProduct) -> str:
        state = self._resolve_ownership_state(product)
        if self._is_card_product(product):
            if state == 'maxed':
                return t('store_card_owned_maxed', default='Sahip — maks. kademe')
            if state == 'upgrade':
                return t('store_card_owned_label', default='Sahip — geliştirilebilir')
            return t('store_unowned_label', default='Sahip olunmadı')
        if state == 'equipped':
            return t('store_owned_equipped', default='Takılı')
        if state == 'owned':
            return t('store_owned_label', default='Sahip olundu')
        if state == 'demo':
            return t('store_default_label', default='Varsayılan')
        return t('store_unowned_label', default='Sahip olunmadı')

    def _ownership_color(self, product: StoreProduct) -> tuple[int, int, int]:
        state = self._resolve_ownership_state(product)
        if self._is_card_product(product):
            if state == 'maxed':
                return (144, 255, 186)
            if state == 'upgrade':
                return (210, 170, 255)
            return (174, 192, 220)
        if state == 'equipped':
            return (144, 255, 186)
        if state == 'owned':
            return (184, 232, 255)
        if state == 'demo':
            return (255, 214, 122)
        return (174, 192, 220)

    def _resolve_ownership_state(self, product: StoreProduct) -> str:
        # Kart ürünleri için sahiplik kozmetikten AYRI hesaplanır. Kartlarda
        # 'equipped' kavramı yoktur; durumlar: unowned / upgrade / maxed.
        if self._is_card_product(product):
            if not self._card_is_owned(product):
                return 'unowned'
            if self._card_current_tier(product) < self._card_max_tier(product):
                return 'upgrade'
            return 'maxed'

        profile = self._get_user_profile()
        slot, value = self._product_payload(product)

        if isinstance(profile, dict) and value:
            equipped_map = profile.get('equipped_cosmetics', {})
            if isinstance(equipped_map, dict):
                equipped_value = equipped_map.get(slot)
                if equipped_value == value:
                    return 'equipped'
            owned = profile.get('owned_cosmetics', [])
            if isinstance(owned, list) and value in {str(entry) for entry in owned}:
                return 'owned'

        if value == 'luna_rainbow' or value == _DEFAULT_PET_VALUE or _is_default_block_skin(value):
            return 'demo'
        return 'unowned'

    def _get_column_count(self, available_width: int) -> int:
        """Pick a column count that guarantees every card fits within the rail.

        We size against a comfortable target card width plus the rail gap. The
        previous static breakpoints could trip into 5 columns on windows that
        couldn't actually accommodate the rightmost card, leaving it clipped
        by the rail border.
        """
        target_card_w = self._s(190)
        gap = self._s(14)
        catalog = max(1, len(self.products))
        if available_width <= 0:
            return 1
        fit = max(1, (available_width + gap) // (target_card_w + gap))
        return min(catalog, max(1, int(fit)), 6)

    def _get_card_height(self, card_width: int) -> int:
        # Kept for backward compatibility with any external callers; rail uses
        # `_get_rail_card_height` which is viewport-aware.
        return max(self._s(220), min(self._s(300), int(card_width * 0.72)))

    def _draw_text_block(
        self,
        text: str,
        font,
        color: tuple[int, int, int],
        rect: pygame.Rect,
        *,
        max_lines: int,
        line_spacing: int,
    ) -> int:
        lines = self._wrap_text(font, text, rect.width, max_lines=max_lines)
        y = rect.y
        for line in lines:
            line_surf = font.render(line, True, color)
            self.screen.blit(line_surf, (rect.x, y))
            y += line_surf.get_height() + line_spacing
        return y

    def _wrap_text(self, font, text: str, max_width: int, *, max_lines: int) -> list[str]:
        words = str(text or '').split()
        if not words:
            return []

        lines: list[str] = []
        current = ''
        index = 0
        truncated = False
        while index < len(words):
            word = words[index]
            candidate = word if not current else current + ' ' + word
            if font.size(candidate)[0] <= max_width:
                current = candidate
                index += 1
                continue

            if current:
                lines.append(current)
                current = ''
            else:
                current = self._split_token_to_fit(font, word, max_width)
                index += 1
                lines.append(current)
                current = ''

            if len(lines) >= max_lines:
                truncated = index < len(words)
                break

        if not truncated and current:
            lines.append(current)

        if len(lines) > max_lines:
            lines = lines[:max_lines]
            truncated = True

        if truncated and lines:
            lines[-1] = self._ellipsize(font, lines[-1], max_width)
        return lines

    def _split_token_to_fit(self, font, token: str, max_width: int) -> str:
        chunk = ''
        for char in token:
            candidate = chunk + char
            if chunk and font.size(candidate)[0] > max_width:
                break
            chunk = candidate
        return chunk or token[:1]

    def _ellipsize(self, font, text: str, max_width: int) -> str:
        suffix = '...'
        base = str(text or '').rstrip()
        while base and font.size(base + suffix)[0] > max_width:
            base = base[:-1].rstrip()
        if not base:
            return suffix if font.size(suffix)[0] <= max_width else ''
        return base + suffix

    def _product_phase_seed(self, product: StoreProduct) -> int:
        return sum(ord(ch) for ch in product.product_id) % 8
