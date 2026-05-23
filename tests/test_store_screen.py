from __future__ import annotations

import os

import pygame


os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')


class _DummyUserManager:
    def get_current_user(self):
        return 'Arda'

    def get_user_data(self, username=None):
        return {'neural_fragments': 345}


def test_store_screen_navigation_and_back_action():
    pygame.init()
    try:
        from store_screen import StoreScreen

        screen = StoreScreen(pygame.Surface((1280, 720), pygame.SRCALPHA), user_manager=_DummyUserManager())

        assert screen.get_product_ids() == ['luna_tail_pack']
        assert screen.get_selected_product().product_id == 'luna_tail_pack'
        assert screen.get_fragment_balance() == 345

        screen.handle_input(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RIGHT))
        assert screen.get_selected_product().product_id == 'luna_tail_pack'

        screen.handle_input(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_DOWN))
        assert screen.get_selected_product().product_id == 'luna_tail_pack'

        screen.handle_input(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN))
        assert 'Luna-Cat' in screen.status_message

        screen.draw()

        action = screen.handle_input(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
        assert action == 'back'
    finally:
        pygame.quit()