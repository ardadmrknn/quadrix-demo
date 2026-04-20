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


def test_new_gen_tetris_flavor_resolves_localized_asset_path(monkeypatch):
    menu = _make_menu_stub()
    flavor = menu._get_dashboard_tile_flavor_map()['new_gen_tetris']

    monkeypatch.setattr(menu_module, 'get_language', lambda: 'tr')
    assert menu._resolve_dashboard_tile_flavor_path(flavor).endswith('kart_panel_effect.png')

    monkeypatch.setattr(menu_module, 'get_language', lambda: 'en')
    assert menu._resolve_dashboard_tile_flavor_path(flavor).endswith('kart_panel_effect_english.png')

    monkeypatch.setattr(menu_module, 'get_language', lambda: 'de')
    assert menu._resolve_dashboard_tile_flavor_path(flavor).endswith('kart_effect_panel_almanca.png')


def test_draw_dashboard_tile_flavor_uses_language_specific_scaled_image(monkeypatch):
    menu = _make_menu_stub()
    menu.screen = pygame.Surface((420, 280), pygame.SRCALPHA)
    menu._tile_flavor_scaled_cache = {}
    menu._apply_layout_override_rect = lambda override_key, rect, *args, **kwargs: rect

    tr_surface = pygame.Surface((120, 120), pygame.SRCALPHA)
    tr_surface.fill((255, 0, 0, 255))
    en_surface = pygame.Surface((120, 120), pygame.SRCALPHA)
    en_surface.fill((0, 0, 255, 255))

    loaded_paths = []

    def _fake_load_image(path, convert_alpha=True):
        loaded_paths.append(path)
        if path.endswith('kart_panel_effect.png'):
            return tr_surface
        if path.endswith('kart_panel_effect_english.png'):
            return en_surface
        return tr_surface

    monkeypatch.setattr(menu_module, 'load_image', _fake_load_image)

    rect = pygame.Rect(40, 30, 280, 180)

    monkeypatch.setattr(menu_module, 'get_language', lambda: 'tr')
    tr_target = pygame.Surface(menu.screen.get_size(), pygame.SRCALPHA)
    menu._draw_dashboard_tile_flavor(rect, 'new_gen_tetris', (255, 0, 255), False, target_surface=tr_target)

    monkeypatch.setattr(menu_module, 'get_language', lambda: 'en')
    en_target = pygame.Surface(menu.screen.get_size(), pygame.SRCALPHA)
    menu._draw_dashboard_tile_flavor(rect, 'new_gen_tetris', (255, 0, 255), False, target_surface=en_target)

    tr_color = tr_target.get_at(rect.center)[:3]
    en_color = en_target.get_at(rect.center)[:3]

    assert tr_color[0] > 200 and tr_color[1] < 10 and tr_color[2] < 10
    assert en_color[2] > 200 and en_color[0] < 10 and en_color[1] < 10
    assert any(path.endswith('kart_panel_effect.png') for path in loaded_paths)
    assert any(path.endswith('kart_panel_effect_english.png') for path in loaded_paths)


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


def test_problem_panels_disable_glass_top_highlight(monkeypatch):
    menu = _make_menu_stub()
    menu.screen = pygame.Surface((640, 480), pygame.SRCALPHA)
    menu._draw_dashboard_tile_flavor = lambda *args, **kwargs: None
    menu._draw_panel_micro_content = lambda *args, **kwargs: None

    class _StubFont:
        def size(self, text):
            return (max(1, len(text)) * 10, 20)

        def get_linesize(self):
            return 20

        def render(self, text, antialias, color):
            return pygame.Surface((max(1, len(text)) * 10, 20), pygame.SRCALPHA)

    calls = []

    def _fake_draw_glass_panel(*args, **kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(menu_module.retro_style, 'draw_glass_panel', _fake_draw_glass_panel)
    monkeypatch.setattr(menu_module.retro_style, 'draw_wrapped_text', lambda *args, **kwargs: pygame.Rect(0, 0, 0, 0))
    monkeypatch.setattr(menu_module.retro_style, 'get_font', lambda *args, **kwargs: _StubFont())
    monkeypatch.setattr(menu_module.retro_style, 'wrap_text', lambda text, font, width: [text])

    rect = pygame.Rect(20, 30, 220, 160)

    menu._render_main_dashboard_tile(menu.screen, rect, 'Başarımlar', False, (255, 220, 0), panel_key='achievements')
    menu._render_main_dashboard_tile(menu.screen, rect, 'Kart Ustalığı', False, (255, 0, 255), panel_key='new_gen_tetris')

    assert calls[0]['top_highlight'] is False
    assert calls[1]['top_highlight'] is True