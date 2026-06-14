from __future__ import annotations

import os

import pygame

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')


def _reset_retro_style_cache() -> None:
    from retro_style import retro_style

    retro_style.font_cache.clear()
    retro_style._render_cache.clear()
    retro_style._render_cache_order.clear()


class _DummyUserManager:
    def __init__(self):
        self.profile = {
            'neural_fragments': 700,
            'owned_cosmetics': [],
            'equipped_cosmetics': {},
        }

    def get_current_user(self):
        return 'Arda'

    def get_user_data(self, username=None):
        return self.profile


def _find_product(screen, product_id: str):
    return next(product for product in screen.products if product.product_id == product_id)


def test_store_blocks_category_lists_default_and_legacy_products():
    pygame.init()
    try:
        _reset_retro_style_cache()
        from store_screen import StoreScreen

        screen = StoreScreen(pygame.Surface((1280, 720), pygame.SRCALPHA), user_manager=_DummyUserManager())

        category_keys = [category.get('key') for category in screen.categories]
        assert 'blocks' in category_keys

        block_ids = {screen.products[index].product_id for index in screen._compute_visible_indices('blocks')}
        assert 'block_skin_modern' in block_ids
        assert 'block_skin_legacy_jelly' in block_ids

        modern = _find_product(screen, 'block_skin_modern')
        legacy = _find_product(screen, 'block_skin_legacy_jelly')
        assert screen._resolve_ownership_state(modern) == 'demo'
        assert screen._resolve_ownership_state(legacy) == 'unowned'

        trace_ids = {screen.products[index].product_id for index in screen._compute_visible_indices('traces')}
        assert 'block_skin_modern' not in trace_ids
        assert 'block_skin_legacy_jelly' not in trace_ids
    finally:
        pygame.quit()


def test_store_can_purchase_and_equip_legacy_block_skin():
    pygame.init()
    try:
        _reset_retro_style_cache()
        from background_effects import get_shared_falling_blocks_layer
        from block_skin_assets import LEGACY_BLOCK_APPEARANCE
        from store_screen import StoreScreen

        manager = _DummyUserManager()
        screen = StoreScreen(pygame.Surface((1280, 720), pygame.SRCALPHA), user_manager=manager)

        legacy_index = next(index for index, product in enumerate(screen.products) if product.product_id == 'block_skin_legacy_jelly')
        screen.selected_index = legacy_index
        screen.handle_input(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN))
        assert screen.is_confirm_open

        screen.handle_input(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN))
        assert not screen.is_confirm_open
        assert manager.profile['neural_fragments'] == 250
        assert 'block_legacy_jelly' in manager.profile['owned_cosmetics']
        assert manager.profile['equipped_cosmetics']['block_skin'] == 'block_legacy_jelly'
        assert get_shared_falling_blocks_layer('default').block_appearance == LEGACY_BLOCK_APPEARANCE
    finally:
        pygame.quit()


def test_store_default_block_skin_re_equips_without_ownership():
    pygame.init()
    try:
        _reset_retro_style_cache()
        from background_effects import get_shared_falling_blocks_layer
        from block_skin_assets import DEFAULT_BLOCK_SKIN_VALUE
        from block_skin_assets import MODERN_BLOCK_APPEARANCE
        from store_screen import StoreScreen

        manager = _DummyUserManager()
        manager.profile['owned_cosmetics'] = ['block_legacy_jelly']
        manager.profile['equipped_cosmetics'] = {'block_skin': 'block_legacy_jelly'}
        screen = StoreScreen(pygame.Surface((1280, 720), pygame.SRCALPHA), user_manager=manager)

        modern_index = next(index for index, product in enumerate(screen.products) if product.product_id == 'block_skin_modern')
        screen.selected_index = modern_index
        before_balance = manager.profile['neural_fragments']
        screen.handle_input(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN))

        assert manager.profile['neural_fragments'] == before_balance
        assert manager.profile['equipped_cosmetics']['block_skin'] == DEFAULT_BLOCK_SKIN_VALUE
        assert get_shared_falling_blocks_layer('default').block_appearance == MODERN_BLOCK_APPEARANCE
    finally:
        pygame.quit()


def test_store_background_fx_syncs_with_equipped_block_skin_on_open():
    pygame.init()
    try:
        _reset_retro_style_cache()
        from block_skin_assets import LEGACY_BLOCK_APPEARANCE
        from store_screen import StoreScreen

        manager = _DummyUserManager()
        manager.profile['equipped_cosmetics'] = {'block_skin': 'block_legacy_jelly'}
        screen = StoreScreen(pygame.Surface((1280, 720), pygame.SRCALPHA), user_manager=manager)

        assert screen.background_fx is not None
        assert screen.background_fx.block_appearance == LEGACY_BLOCK_APPEARANCE
    finally:
        pygame.quit()