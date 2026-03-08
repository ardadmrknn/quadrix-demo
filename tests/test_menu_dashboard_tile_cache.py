from __future__ import annotations

import os
import sys

import pygame


SRC_DIR = os.path.join(os.path.dirname(__file__), '..', 'src')
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

import menu as menu_module
from menu import Menu
from surface_lru_cache import SurfaceLRUCache


def _make_menu_stub() -> Menu:
    menu = Menu.__new__(Menu)
    menu._menu_panel_content_scale = lambda: 1.0
    return menu


def test_draw_main_dashboard_tile_reuses_cached_static_surface():
    menu = _make_menu_stub()
    menu.screen = pygame.Surface((640, 480), pygame.SRCALPHA)
    menu._dashboard_tile_surface_cache = SurfaceLRUCache(max_entries=8)

    call_count = 0

    def _fake_render(target_surface, rect, title, selected, accent_color, subtitle='', hover=False, panel_key='', panel_context=None):
        nonlocal call_count
        call_count += 1
        target_surface.fill((10, 20, 30, 255), rect)
        return rect

    menu._render_main_dashboard_tile = _fake_render

    rect = pygame.Rect(20, 30, 220, 160)
    panel_context = {'daily_title': 'Bugun', 'daily_lives': 3, 'daily_max_lives': 5}

    menu._draw_main_dashboard_tile(rect, 'Daily', False, (0, 200, 255), panel_key='daily_challenge', panel_context=panel_context)
    menu._draw_main_dashboard_tile(rect, 'Daily', False, (0, 200, 255), panel_key='daily_challenge', panel_context=panel_context)

    assert call_count == 1


def test_draw_main_dashboard_tile_bypasses_cache_for_selected_tile():
    menu = _make_menu_stub()
    menu.screen = pygame.Surface((640, 480), pygame.SRCALPHA)
    menu._dashboard_tile_surface_cache = SurfaceLRUCache(max_entries=8)

    call_count = 0

    def _fake_render(target_surface, rect, title, selected, accent_color, subtitle='', hover=False, panel_key='', panel_context=None):
        nonlocal call_count
        call_count += 1
        return rect

    menu._render_main_dashboard_tile = _fake_render

    rect = pygame.Rect(20, 30, 220, 160)
    panel_context = {'daily_title': 'Bugun', 'daily_lives': 3, 'daily_max_lives': 5}

    menu._draw_main_dashboard_tile(rect, 'Daily', True, (0, 200, 255), panel_key='daily_challenge', panel_context=panel_context)
    menu._draw_main_dashboard_tile(rect, 'Daily', True, (0, 200, 255), panel_key='daily_challenge', panel_context=panel_context)

    assert call_count == 2


def test_can_cache_dashboard_tile_surface_only_for_static_non_hover_tiles():
    menu = _make_menu_stub()

    assert menu._can_cache_dashboard_tile_surface('daily_challenge', selected=False, hover=False) is True
    assert menu._can_cache_dashboard_tile_surface('piece_workshop', selected=False, hover=False) is True
    assert menu._can_cache_dashboard_tile_surface('campaign_mode', selected=False, hover=False) is False
    assert menu._can_cache_dashboard_tile_surface('daily_challenge', selected=True, hover=False) is False
    assert menu._can_cache_dashboard_tile_surface('daily_challenge', selected=False, hover=True) is False


def test_dashboard_tile_cache_key_changes_for_daily_context_updates():
    menu = _make_menu_stub()
    rect = pygame.Rect(0, 0, 220, 160)

    key_a = menu._get_dashboard_tile_surface_cache_key(
        rect,
        'daily',
        (0, 200, 255),
        '',
        'daily_challenge',
        {'daily_title': 'A', 'daily_lives': 3, 'daily_max_lives': 5},
    )
    key_b = menu._get_dashboard_tile_surface_cache_key(
        rect,
        'daily',
        (0, 200, 255),
        '',
        'daily_challenge',
        {'daily_title': 'A', 'daily_lives': 2, 'daily_max_lives': 5},
    )

    assert key_a != key_b


def test_dashboard_tile_cache_key_changes_for_achievement_content_updates():
    menu = _make_menu_stub()
    rect = pygame.Rect(0, 0, 220, 160)

    key_a = menu._get_dashboard_tile_surface_cache_key(
        rect,
        'achievements',
        (255, 220, 0),
        '',
        'achievements',
        {'recent_achievements': ['A'], 'achievement_percent': 10},
    )
    key_b = menu._get_dashboard_tile_surface_cache_key(
        rect,
        'achievements',
        (255, 220, 0),
        '',
        'achievements',
        {'recent_achievements': ['A', 'B'], 'achievement_percent': 10},
    )

    assert key_a != key_b


def test_dashboard_tile_cache_key_changes_with_language(monkeypatch):
    menu = _make_menu_stub()
    rect = pygame.Rect(0, 0, 220, 160)

    monkeypatch.setattr(menu_module, 'get_language', lambda: 'tr')
    key_tr = menu._get_dashboard_tile_surface_cache_key(
        rect,
        'piece workshop',
        (255, 0, 255),
        'subtitle',
        'piece_workshop',
        {},
    )

    monkeypatch.setattr(menu_module, 'get_language', lambda: 'en')
    key_en = menu._get_dashboard_tile_surface_cache_key(
        rect,
        'piece workshop',
        (255, 0, 255),
        'subtitle',
        'piece_workshop',
        {},
    )

    assert key_tr != key_en


def test_dashboard_tile_cache_key_changes_with_menu_transparency(monkeypatch):
    menu = _make_menu_stub()
    rect = pygame.Rect(0, 0, 220, 160)

    monkeypatch.setattr(menu_module.retro_style, '_menu_transparency', 1.0, raising=False)
    key_default = menu._get_dashboard_tile_surface_cache_key(
        rect,
        'achievements',
        (255, 220, 0),
        '',
        'achievements',
        {'recent_achievements': ['A'], 'achievement_percent': 10},
    )

    monkeypatch.setattr(menu_module.retro_style, '_menu_transparency', 0.6, raising=False)
    key_transparent = menu._get_dashboard_tile_surface_cache_key(
        rect,
        'achievements',
        (255, 220, 0),
        '',
        'achievements',
        {'recent_achievements': ['A'], 'achievement_percent': 10},
    )

    assert key_default != key_transparent