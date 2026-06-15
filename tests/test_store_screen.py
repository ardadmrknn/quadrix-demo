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
            'neural_fragments': 345,
            'owned_cosmetics': [],
            'equipped_cosmetics': {},
        }

    def get_current_user(self):
        return 'Arda'

    def get_user_data(self, username=None):
        return self.profile


def test_store_screen_navigation_and_back_action():
    pygame.init()
    try:
        _reset_retro_style_cache()
        from store_screen import StoreScreen

        screen = StoreScreen(pygame.Surface((1280, 720), pygame.SRCALPHA), user_manager=_DummyUserManager())

        product_ids = screen.get_product_ids()
        assert 'luna_sweep_rainbow' in product_ids
        assert 'block_skin_modern' in product_ids
        assert 'block_skin_legacy_jelly' in product_ids
        assert len(product_ids) == len(set(product_ids))

        assert screen.get_selected_product().product_id == product_ids[0]
        assert screen.get_fragment_balance() == 345

        screen.draw()

        screen.handle_input(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RIGHT))
        assert screen.get_selected_product().product_id == product_ids[1]

        action = screen.handle_input(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
        assert action == 'back'
    finally:
        pygame.quit()


def test_store_screen_purchase_and_equip_flow():
    pygame.init()
    try:
        _reset_retro_style_cache()
        from store_screen import StoreScreen

        manager = _DummyUserManager()
        manager.profile['neural_fragments'] = 700
        screen = StoreScreen(pygame.Surface((1280, 720), pygame.SRCALPHA), user_manager=manager)

        screen.draw()
        legacy_idx = next(i for i, p in enumerate(screen.products) if p.product_id == 'block_skin_legacy_jelly')
        screen.selected_index = legacy_idx
        screen.draw()

        # ENTER on an affordable, unowned product opens confirmation
        screen.handle_input(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN))
        assert screen.is_confirm_open
        assert manager.profile['neural_fragments'] == 700
        assert 'block_legacy_jelly' not in manager.profile['owned_cosmetics']

        # Confirm
        screen.handle_input(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN))
        assert not screen.is_confirm_open
        assert manager.profile['neural_fragments'] == 250
        assert 'block_legacy_jelly' in manager.profile['owned_cosmetics']
        assert manager.profile['equipped_cosmetics']['block_skin'] == 'block_legacy_jelly'

        # Equipping an already owned one
        screen.selected_index = 0
        screen.handle_input(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN))
        assert not screen.is_confirm_open
        assert manager.profile['equipped_cosmetics']['line_sweep_skin'] == 'luna_rainbow'
    finally:
        pygame.quit()


def test_store_confirm_modal_cancel_keeps_wallet_intact():
    pygame.init()
    try:
        _reset_retro_style_cache()
        from store_screen import StoreScreen

        manager = _DummyUserManager()
        manager.profile['neural_fragments'] = 700
        screen = StoreScreen(pygame.Surface((1280, 720), pygame.SRCALPHA), user_manager=manager)

        screen.draw()
        legacy_idx = next(i for i, p in enumerate(screen.products) if p.product_id == 'block_skin_legacy_jelly')
        screen.selected_index = legacy_idx
        screen.draw()
        screen.handle_input(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN))
        assert screen.is_confirm_open

        action = screen.handle_input(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
        assert action is None
        assert not screen.is_confirm_open
        assert manager.profile['neural_fragments'] == 700
        assert 'block_legacy_jelly' not in manager.profile['owned_cosmetics']
    finally:
        pygame.quit()


def test_store_confirm_modal_buy_button_completes_purchase():
    pygame.init()
    try:
        _reset_retro_style_cache()
        from store_screen import StoreScreen

        manager = _DummyUserManager()
        manager.profile['neural_fragments'] = 700
        screen = StoreScreen(pygame.Surface((1280, 720), pygame.SRCALPHA), user_manager=manager)

        legacy_idx = next(i for i, p in enumerate(screen.products) if p.product_id == 'block_skin_legacy_jelly')
        _select_and_render(screen, legacy_idx)
        _click(screen, screen._cta_rect.center)
        assert screen.is_confirm_open
        screen.draw()
        assert screen._confirm_yes_rect is not None and screen._confirm_no_rect is not None

        _click(screen, screen._confirm_yes_rect.center)
        assert not screen.is_confirm_open
        assert manager.profile['neural_fragments'] == 250
        assert 'block_legacy_jelly' in manager.profile['owned_cosmetics']
        assert manager.profile['equipped_cosmetics']['block_skin'] == 'block_legacy_jelly'
    finally:
        pygame.quit()


def test_store_hover_does_not_change_selection():
    pygame.init()
    try:
        _reset_retro_style_cache()
        from store_screen import StoreScreen

        screen = StoreScreen(pygame.Surface((1280, 720), pygame.SRCALPHA), user_manager=_DummyUserManager())
        screen.draw()
        start_index = screen.selected_index

        target_idx = next(
            (i for i, r in enumerate(screen.card_rects)
             if i != start_index and r.width > 0 and r.height > 0),
            None,
        )
        assert target_idx is not None
        screen.handle_input(pygame.event.Event(
            pygame.MOUSEMOTION, pos=screen.card_rects[target_idx].center, rel=(1, 1), buttons=(0, 0, 0),
        ))
        assert screen.selected_index == start_index

        _click(screen, screen.card_rects[target_idx].center)
        assert screen.selected_index == target_idx
    finally:
        pygame.quit()


def _click(screen, pos: tuple[int, int]) -> None:
    screen.handle_input(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=pos))


def _select_and_render(screen, index: int) -> None:
    screen.draw()
    screen.selected_index = index
    screen.draw()


def test_store_card_click_only_selects_and_does_not_purchase():
    pygame.init()
    try:
        _reset_retro_style_cache()
        from store_screen import StoreScreen

        manager = _DummyUserManager()
        manager.profile['neural_fragments'] = 700
        screen = StoreScreen(pygame.Surface((1280, 720), pygame.SRCALPHA), user_manager=manager)

        screen.draw()
        target_idx = next(i for i, p in enumerate(screen.products) if p.product_id == 'block_skin_legacy_jelly')
        target_rect = screen.card_rects[target_idx]
        assert target_rect.width > 0 and target_rect.height > 0
        _click(screen, target_rect.center)
        screen.draw()
        assert screen.selected_index == target_idx

        _click(screen, target_rect.center)
        assert manager.profile['neural_fragments'] == 700
        assert 'block_legacy_jelly' not in manager.profile.get('owned_cosmetics', [])
    finally:
        pygame.quit()


def test_store_cta_click_buys_when_affordable():
    pygame.init()
    try:
        _reset_retro_style_cache()
        from store_screen import StoreScreen

        manager = _DummyUserManager()
        manager.profile['neural_fragments'] = 700
        screen = StoreScreen(pygame.Surface((1280, 720), pygame.SRCALPHA), user_manager=manager)

        legacy_idx = next(i for i, p in enumerate(screen.products) if p.product_id == 'block_skin_legacy_jelly')
        _select_and_render(screen, legacy_idx)
        assert screen._cta_rect is not None
        _click(screen, screen._cta_rect.center)
        assert screen.is_confirm_open
        assert manager.profile['neural_fragments'] == 700

        screen.draw()
        assert screen._confirm_yes_rect is not None
        _click(screen, screen._confirm_yes_rect.center)

        assert not screen.is_confirm_open
        assert manager.profile['neural_fragments'] == 250
        assert 'block_legacy_jelly' in manager.profile['owned_cosmetics']
        assert manager.profile['equipped_cosmetics']['block_skin'] == 'block_legacy_jelly'
    finally:
        pygame.quit()


def test_store_cta_click_equips_when_owned_but_not_equipped():
    pygame.init()
    try:
        _reset_retro_style_cache()
        from store_screen import StoreScreen

        manager = _DummyUserManager()
        manager.profile['owned_cosmetics'] = ['block_legacy_jelly']
        manager.profile['equipped_cosmetics'] = {'block_skin': 'block_skin_modern'}
        manager.profile['neural_fragments'] = 100
        screen = StoreScreen(pygame.Surface((1280, 720), pygame.SRCALPHA), user_manager=manager)

        legacy_idx = next(i for i, p in enumerate(screen.products) if p.product_id == 'block_skin_legacy_jelly')
        _select_and_render(screen, legacy_idx)
        assert screen._cta_rect is not None
        _click(screen, screen._cta_rect.center)

        assert manager.profile['equipped_cosmetics']['block_skin'] == 'block_legacy_jelly'
        assert manager.profile['neural_fragments'] == 100
    finally:
        pygame.quit()


def test_store_cta_click_when_locked_explains_to_user():
    pygame.init()
    try:
        _reset_retro_style_cache()
        from store_screen import StoreScreen

        manager = _DummyUserManager()
        manager.profile['neural_fragments'] = 50
        screen = StoreScreen(pygame.Surface((1280, 720), pygame.SRCALPHA), user_manager=manager)

        legacy_idx = next(i for i, p in enumerate(screen.products) if p.product_id == 'block_skin_legacy_jelly')
        _select_and_render(screen, legacy_idx)
        assert screen._cta_rect is not None
        before_balance = manager.profile['neural_fragments']
        before_owned = list(manager.profile['owned_cosmetics'])
        _click(screen, screen._cta_rect.center)

        assert manager.profile['neural_fragments'] == before_balance
        assert manager.profile['owned_cosmetics'] == before_owned
        product = screen.products[legacy_idx]
        assert screen._product_title(product) in screen.status_message
    finally:
        pygame.quit()


def test_store_locked_message_formats_without_raw_placeholders_in_english():
    pygame.init()
    previous_lang = 'tr'
    try:
        _reset_retro_style_cache()
        import localization
        from store_screen import StoreScreen

        previous_lang = localization.get_language()
        localization.set_language('en')

        manager = _DummyUserManager()
        manager.profile['neural_fragments'] = 50
        screen = StoreScreen(pygame.Surface((1280, 720), pygame.SRCALPHA), user_manager=manager)

        legacy_idx = next(i for i, p in enumerate(screen.products) if p.product_id == 'block_skin_legacy_jelly')
        _select_and_render(screen, legacy_idx)
        assert screen._cta_rect is not None
        _click(screen, screen._cta_rect.center)

        product = screen.products[legacy_idx]
        assert screen._product_title(product) in screen.status_message
        assert '450 Lunar' in screen.status_message
        assert '50 Lunar' in screen.status_message
        assert '{' not in screen.status_message and '}' not in screen.status_message
    finally:
        try:
            import localization
            localization.set_language(previous_lang)
        except Exception:
            pass
        pygame.quit()


def test_store_cta_click_when_equipped_says_already_in_use():
    pygame.init()
    try:
        _reset_retro_style_cache()
        from store_screen import StoreScreen

        manager = _DummyUserManager()
        manager.profile['owned_cosmetics'] = ['block_legacy_jelly']
        manager.profile['equipped_cosmetics'] = {'block_skin': 'block_legacy_jelly'}
        screen = StoreScreen(pygame.Surface((1280, 720), pygame.SRCALPHA), user_manager=manager)

        legacy_idx = next(i for i, p in enumerate(screen.products) if p.product_id == 'block_skin_legacy_jelly')
        _select_and_render(screen, legacy_idx)
        assert screen._cta_rect is not None
        _click(screen, screen._cta_rect.center)

        assert manager.profile['equipped_cosmetics']['block_skin'] == 'block_legacy_jelly'
        product = screen.products[legacy_idx]
        assert screen._product_title(product) in screen.status_message
        assert 'kullan' in screen.status_message.lower() or 'equip' in screen.status_message.lower()
    finally:
        pygame.quit()


def test_store_renders_at_narrow_resolution_keeps_status_visible():
    pygame.init()
    try:
        _reset_retro_style_cache()
        from store_screen import StoreScreen

        manager_narrow = _DummyUserManager()
        manager_narrow.profile['neural_fragments'] = 50
        narrow = StoreScreen(pygame.Surface((800, 600), pygame.SRCALPHA), user_manager=manager_narrow)
        narrow.draw()
        assert narrow._footer_two_row is True

        legacy_idx = next(i for i, p in enumerate(narrow.products) if p.product_id == 'block_skin_legacy_jelly')
        _select_and_render(narrow, legacy_idx)
        assert narrow._cta_rect is not None
        _click(narrow, narrow._cta_rect.center)
        narrow.draw()
        product = narrow.products[legacy_idx]
        assert narrow._product_title(product) in narrow.status_message
        assert narrow._footer_two_row is True

        wide = StoreScreen(pygame.Surface((1280, 720), pygame.SRCALPHA), user_manager=_DummyUserManager())
        wide.draw()
        assert wide._footer_two_row is False
    finally:
        pygame.quit()


def test_store_footer_breakpoint_uses_raw_pixels_not_scaled():
    pygame.init()
    try:
        _reset_retro_style_cache()
        from store_screen import StoreScreen

        narrow = StoreScreen(pygame.Surface((800, 600), pygame.SRCALPHA), user_manager=_DummyUserManager())
        narrow.draw()
        wide = StoreScreen(pygame.Surface((1024, 768), pygame.SRCALPHA), user_manager=_DummyUserManager())
        wide.draw()
        edge_below = StoreScreen(pygame.Surface((899, 720), pygame.SRCALPHA), user_manager=_DummyUserManager())
        edge_below.draw()
        edge_above = StoreScreen(pygame.Surface((900, 720), pygame.SRCALPHA), user_manager=_DummyUserManager())
        edge_above.draw()

        assert narrow._footer_two_row is True
        assert wide._footer_two_row is False
        assert edge_below._footer_two_row is True
        assert edge_above._footer_two_row is False
    finally:
        pygame.quit()


def test_store_back_button_click_returns_back_action():
    pygame.init()
    try:
        _reset_retro_style_cache()
        from store_screen import StoreScreen

        manager = _DummyUserManager()
        manager.profile['neural_fragments'] = 700
        manager.profile['owned_cosmetics'] = list(manager.profile.get('owned_cosmetics') or [])
        screen = StoreScreen(pygame.Surface((1280, 720), pygame.SRCALPHA), user_manager=manager)
        screen.draw()
        assert screen._back_rect is not None
        before_balance = manager.profile['neural_fragments']
        before_owned = list(manager.profile.get('owned_cosmetics') or [])
        before_equipped = dict(manager.profile.get('equipped_cosmetics') or {})

        action = screen.handle_input(pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, button=1, pos=screen._back_rect.center,
        ))

        assert action == 'back'
        assert manager.profile['neural_fragments'] == before_balance
        assert list(manager.profile.get('owned_cosmetics') or []) == before_owned
        assert dict(manager.profile.get('equipped_cosmetics') or {}) == before_equipped
    finally:
        pygame.quit()


def test_store_back_button_does_not_overlap_cta_or_cards():
    pygame.init()
    try:
        _reset_retro_style_cache()
        from store_screen import StoreScreen

        manager = _DummyUserManager()
        manager.profile['neural_fragments'] = 700
        screen = StoreScreen(pygame.Surface((1280, 720), pygame.SRCALPHA), user_manager=manager)
        screen.draw()

        assert screen._back_rect is not None
        assert screen._cta_rect is not None
        assert not screen._back_rect.colliderect(screen._cta_rect)
        for card_rect in screen.card_rects:
            if card_rect.width > 0 and card_rect.height > 0:
                assert not screen._back_rect.colliderect(card_rect)
    finally:
        pygame.quit()


def test_store_back_button_visible_at_narrow_resolution():
    pygame.init()
    try:
        _reset_retro_style_cache()
        from store_screen import StoreScreen

        screen = StoreScreen(pygame.Surface((800, 600), pygame.SRCALPHA), user_manager=_DummyUserManager())
        screen.draw()
        assert screen._back_rect is not None
        assert screen._back_rect.width > 0 and screen._back_rect.height > 0
        assert screen._back_rect.x >= 0
        assert screen._back_rect.y >= 0
        assert screen._back_rect.right < 800 // 2
    finally:
        pygame.quit()


def test_store_tab_arrows_do_not_overlap_back_cta_or_cards():
    pygame.init()
    try:
        _reset_retro_style_cache()
        from store_screen import StoreScreen

        manager = _DummyUserManager()
        manager.profile['neural_fragments'] = 700
        screen = StoreScreen(pygame.Surface((1280, 720), pygame.SRCALPHA), user_manager=manager)
        screen.draw()

        assert screen._tab_prev_arrow_rect is not None
        assert screen._tab_next_arrow_rect is not None
        assert screen._back_rect is not None
        assert screen._cta_rect is not None

        for arrow in (screen._tab_prev_arrow_rect, screen._tab_next_arrow_rect):
            assert not arrow.colliderect(screen._back_rect)
            assert not arrow.colliderect(screen._cta_rect)
            for card_rect in screen.card_rects:
                if card_rect.width > 0 and card_rect.height > 0:
                    assert not arrow.colliderect(card_rect)
        assert not screen._tab_prev_arrow_rect.colliderect(screen._tab_next_arrow_rect)
        for tab_rect in screen._tab_rects:
            assert not screen._tab_prev_arrow_rect.colliderect(tab_rect)
            assert not screen._tab_next_arrow_rect.colliderect(tab_rect)
    finally:
        pygame.quit()


def test_store_tab_arrow_click_pages_category_without_purchasing():
    pygame.init()
    try:
        _reset_retro_style_cache()
        from store_screen import StoreScreen

        manager = _DummyUserManager()
        manager.profile['neural_fragments'] = 700
        screen = StoreScreen(pygame.Surface((1280, 720), pygame.SRCALPHA), user_manager=manager)
        screen.draw()

        before_balance = manager.profile['neural_fragments']
        before_owned = list(manager.profile.get('owned_cosmetics') or [])
        before_equipped = dict(manager.profile.get('equipped_cosmetics') or {})

        assert screen.active_category == 0
        action = screen.handle_input(pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, button=1, pos=screen._tab_next_arrow_rect.center,
        ))
        assert action is None
        assert screen.active_category == 1
        screen.draw()

        screen.handle_input(pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, button=1, pos=screen._tab_prev_arrow_rect.center,
        ))
        assert screen.active_category == 0

        assert manager.profile['neural_fragments'] == before_balance
        assert list(manager.profile.get('owned_cosmetics') or []) == before_owned
        assert dict(manager.profile.get('equipped_cosmetics') or {}) == before_equipped
    finally:
        pygame.quit()