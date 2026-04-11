from __future__ import annotations

import os
import sys
import types

import pygame


SRC_DIR = os.path.join(os.path.dirname(__file__), '..', 'src')
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from menu import Menu


def _make_menu_stub() -> Menu:
    menu = Menu.__new__(Menu)
    menu.options = [
        'new_gen_tetris',
        'piece_workshop',
        'extras',
        'coop_mode',
        'tutorial_mode',
        'achievements',
        'pvp_2_players',
        'campaign_mode',
        'store',
        'high_scores',
        'switch_user',
        'settings',
        'guide',
        'credits',
        'exit',
    ]
    menu.selected = 0
    menu._nav_panel_max_idx = 8
    menu._nav_option_keys = {
        'new_gen_tetris',
        'piece_workshop',
        'extras',
        'coop_mode',
        'tutorial_mode',
        'achievements',
        'pvp_2_players',
        'campaign_mode',
        'store',
    }
    menu._nav_geometry_overrides = {}
    menu._pvp_split_selection = 'local'
    menu._nav_source = 'keyboard'
    menu._mouse_in_panel = True
    menu.settings_manager = None
    menu.menu_language_panel_open = False
    menu.sos_open = False
    menu.show_exit_prompt = False
    menu.show_daily_prompt = False
    menu.option_rects = [
        pygame.Rect(0, 0, 200, 200),
        pygame.Rect(220, 0, 120, 140),
        pygame.Rect(360, 0, 120, 140),
        pygame.Rect(500, 0, 100, 200),
        pygame.Rect(620, 0, 80, 140),
        pygame.Rect(710, 0, 100, 140),
        pygame.Rect(10, 220, 180, 110),
        pygame.Rect(230, 220, 100, 110),
        pygame.Rect(370, 220, 100, 110),
        pygame.Rect(0, 0, 0, 0),
        pygame.Rect(0, 0, 0, 0),
        pygame.Rect(0, 0, 0, 0),
        pygame.Rect(0, 0, 0, 0),
        pygame.Rect(0, 0, 0, 0),
        pygame.Rect(0, 0, 0, 0),
    ]
    menu.pvp_local_polygon = [(10, 220), (10, 330), (190, 330)]
    menu.pvp_online_polygon = [(10, 220), (190, 220), (190, 330)]
    menu.campaign_quick_play_rect = None
    menu.new_gen_tetris_play_rect = None
    menu.extras_browse_rect = None
    menu.tutorial_enter_rect = None
    menu.pvp_local_rect = None
    menu.pvp_online_rect = None
    menu.sos_button_rect = None
    menu.showcase_piece_workshop_rect = None
    menu.showcase_block_styles_rect = None
    menu.corner_settings_rect = None
    menu.corner_language_rect = None
    menu.corner_mute_rect = None
    menu.corner_switch_user_rect = None
    menu.corner_credits_rect = None
    menu.corner_achievements_rect = None
    menu.corner_guide_rect = None
    menu._mystery_lb_tab_rects = {}
    menu._handle_menu_language_panel_input = lambda event: None
    menu._is_modal_open = lambda: False
    menu._ensure_visible = lambda: None
    return menu


def _key_event(key: int):
    return types.SimpleNamespace(type=pygame.KEYDOWN, key=key, mod=0)


def test_pvp_right_switches_focus_then_advances_to_campaign():
    menu = _make_menu_stub()
    menu.selected = menu.options.index('pvp_2_players')

    menu.handle_input(_key_event(pygame.K_RIGHT))

    assert menu.options[menu.selected] == 'pvp_2_players'
    assert menu._pvp_split_selection == 'online'

    menu.handle_input(_key_event(pygame.K_RIGHT))

    assert menu.options[menu.selected] == 'campaign_mode'


def test_campaign_left_reenters_pvp_from_online_side():
    menu = _make_menu_stub()
    menu.selected = menu.options.index('campaign_mode')

    menu.handle_input(_key_event(pygame.K_LEFT))

    assert menu.options[menu.selected] == 'pvp_2_players'
    assert menu._pvp_split_selection == 'online'

    menu.handle_input(_key_event(pygame.K_LEFT))

    assert menu.options[menu.selected] == 'pvp_2_players'
    assert menu._pvp_split_selection == 'local'


def test_top_row_up_stays_on_same_tile_without_wrap():
    menu = _make_menu_stub()
    menu.selected = menu.options.index('new_gen_tetris')

    menu.handle_input(_key_event(pygame.K_UP))

    assert menu.options[menu.selected] == 'new_gen_tetris'


def test_coop_down_stays_when_no_geometry_hits_ray():
    menu = _make_menu_stub()
    menu.selected = menu.options.index('coop_mode')

    menu.handle_input(_key_event(pygame.K_DOWN))

    assert menu.options[menu.selected] == 'coop_mode'


def test_extras_down_hits_first_geometry_on_same_vertical_ray():
    menu = _make_menu_stub()
    menu.selected = menu.options.index('extras')

    menu.handle_input(_key_event(pygame.K_DOWN))

    assert menu.options[menu.selected] == 'store'


def test_runtime_added_button_joins_nav_without_hardcoded_index_updates():
    menu = _make_menu_stub()
    menu.options = ['left_mode', 'runtime_mode', 'right_mode']
    menu.option_rects = [
        pygame.Rect(0, 0, 120, 120),
        pygame.Rect(180, 0, 120, 120),
        pygame.Rect(360, 0, 120, 120),
    ]
    menu._nav_option_keys = {'left_mode', 'runtime_mode', 'right_mode'}
    menu._nav_panel_max_idx = 0
    menu.selected = 0
    menu.pvp_local_polygon = None
    menu.pvp_online_polygon = None

    menu.handle_input(_key_event(pygame.K_RIGHT))

    assert menu.options[menu.selected] == 'runtime_mode'


def test_geometry_move_changes_nav_result_automatically():
    menu = _make_menu_stub()
    menu.selected = menu.options.index('extras')
    menu.option_rects[menu.options.index('store')] = pygame.Rect(520, 220, 100, 110)

    menu.handle_input(_key_event(pygame.K_DOWN))

    assert menu.options[menu.selected] == 'extras'


def test_pvp_online_right_uses_parent_tile_center_for_external_nav():
    menu = _make_menu_stub()
    menu.options = ['pvp_2_players', 'campaign_mode']
    menu.option_rects = [
        pygame.Rect(0, 0, 180, 120),
        pygame.Rect(220, 50, 100, 80),
    ]
    menu._nav_option_keys = {'pvp_2_players', 'campaign_mode'}
    menu._nav_panel_max_idx = 0
    menu.selected = 0
    menu._pvp_split_selection = 'online'
    menu.pvp_local_polygon = [(0, 0), (0, 120), (180, 120)]
    menu.pvp_online_polygon = [(0, 0), (180, 0), (180, 120)]

    menu.handle_input(_key_event(pygame.K_RIGHT))

    assert menu.options[menu.selected] == 'campaign_mode'