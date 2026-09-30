"""Paket D test paketi:
- Ana menü dashboard kartları static panel cache hit / bypass
- Hover ve selected durumunda doğru bypass / ayrı key
- Dil ve tema değişiminde cache invalidation
- Köşe butonlarında mute, gamepad ve hover state ayrımı
- LRU eviction ve kapasite sınırı
- Hitbox ve çizim koordinatlarının korunması
"""
import os
import sys
import pygame
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))
from menu import Menu
from settings_manager import SettingsManager
from themes import ThemeManager
from surface_lru_cache import SurfaceLRUCache
import localization


@pytest.fixture(scope="module", autouse=True)
def init_pygame():
    os.environ["SDL_VIDEODRIVER"] = "dummy"
    pygame.init()
    if not pygame.display.get_init():
        pygame.display.init()
    if not pygame.font.get_init():
        pygame.font.init()
    yield
    pygame.quit()


def _create_test_menu():
    screen = pygame.Surface((1280, 720))
    sm = SettingsManager()
    tm = ThemeManager(sm)
    menu = Menu(screen=screen, settings_manager=sm)
    menu.theme_manager = tm
    return menu


def test_static_dashboard_panel_cache_hit():
    """Statik dashboard kartlarının ilk çizimde cache'lendiğini, ikinci çizimde hit olduğunu test et."""
    menu = _create_test_menu()
    menu.invalidate_menu_surface_caches()

    rect = pygame.Rect(100, 100, 200, 150)
    context = {'daily_title': 'Test Daily', 'daily_lives': 3, 'daily_max_lives': 3}

    # İlk çizim (miss)
    menu._draw_main_dashboard_tile(
        rect,
        title='GÜNLÜK GÖREV',
        selected=False,
        accent_color=(0, 200, 255),
        subtitle='Test',
        hover=False,
        panel_key='daily_challenge',
        panel_context=context,
    )
    assert len(menu._dashboard_tile_surface_cache._cache) == 1
    key = list(menu._dashboard_tile_surface_cache._cache.keys())[0]
    surf1 = menu._dashboard_tile_surface_cache.get(key)
    assert isinstance(surf1, pygame.Surface)

    # İkinci çizim (hit - aynı nesne)
    menu._draw_main_dashboard_tile(
        rect,
        title='GÜNLÜK GÖREV',
        selected=False,
        accent_color=(0, 200, 255),
        subtitle='Test',
        hover=False,
        panel_key='daily_challenge',
        panel_context=context,
    )
    assert len(menu._dashboard_tile_surface_cache._cache) == 1
    assert menu._dashboard_tile_surface_cache.get(key) is surf1


def test_hover_and_selected_bypass_or_distinct_key():
    """Hover veya selected durumunda kartların cache'i bypass ettiğini veya ayrı anahtar kullandığını test et."""
    menu = _create_test_menu()
    menu.invalidate_menu_surface_caches()

    rect = pygame.Rect(100, 100, 200, 150)
    context = {'daily_title': 'Test Daily', 'daily_lives': 3, 'daily_max_lives': 3}

    # Selected=True kartı cache'lenmemeli
    assert not menu._can_cache_dashboard_tile_surface('daily_challenge', selected=True, hover=False)
    # Hover=True kartı cache'lenmemeli
    assert not menu._can_cache_dashboard_tile_surface('daily_challenge', selected=False, hover=True)
    # Statik unhovered kart cache'lenebilir
    assert menu._can_cache_dashboard_tile_surface('daily_challenge', selected=False, hover=False)

    # Panel butonlarında hover=False vs hover=True ayrı cache anahtarları kullanmalı
    panel_rect = pygame.Rect(50, 50, 300, 200)
    menu._panel_button_surface_cache.clear()

    # hover=False
    key_normal = ('test_btn', 100, 40, 'Oyna', (0, 255, 255), False, 'tr', 1.0)
    surf_normal = menu._get_cached_panel_button_surface(key_normal, (110, 50), lambda s: s.fill((10, 10, 10)))

    # hover=True
    key_hover = ('test_btn', 100, 40, 'Oyna', (0, 255, 255), True, 'tr', 1.0)
    surf_hover = menu._get_cached_panel_button_surface(key_hover, (110, 50), lambda s: s.fill((20, 20, 20)))

    assert surf_normal is not surf_hover
    assert len(menu._panel_button_surface_cache._cache) == 2


def test_language_and_theme_invalidation():
    """Dil veya tema değişiminde invalidation tetiklendiğini test et."""
    menu = _create_test_menu()
    rect = pygame.Rect(100, 100, 200, 150)
    context = {'daily_title': 'Test', 'daily_lives': 3}

    # Cache'e veri koy
    menu._draw_main_dashboard_tile(
        rect, title='TEST', selected=False, accent_color=(0, 200, 255),
        hover=False, panel_key='daily_challenge', panel_context=context,
    )
    assert len(menu._dashboard_tile_surface_cache._cache) > 0

    # Invalidation çağrısı
    menu.invalidate_menu_surface_caches()
    assert len(menu._dashboard_tile_surface_cache._cache) == 0
    assert len(menu._corner_button_surface_cache._cache) == 0
    assert len(menu._panel_button_surface_cache._cache) == 0

    # Tema anahtar bileşenini test et
    key_default_theme = menu._get_dashboard_tile_surface_cache_key(
        rect, 'TEST', (0, 200, 255), '', 'daily_challenge', context
    )
    menu.theme_manager.current_theme = 'cyberpunk'
    key_cyberpunk_theme = menu._get_dashboard_tile_surface_cache_key(
        rect, 'TEST', (0, 200, 255), '', 'daily_challenge', context
    )
    assert key_default_theme != key_cyberpunk_theme


def test_corner_buttons_mute_and_gamepad_state():
    """Köşe butonlarında mute ve gamepad seçim durumlarının doğru ayrıştığını test et."""
    menu = _create_test_menu()
    menu._corner_button_surface_cache.clear()

    btn_size = (52, 52)
    accent = (0, 255, 255)

    # Mute kapalı
    surf_unmuted = menu._get_corner_button_surface(
        btn_size, accent, is_active=False, gamepad_selected=False, hover=False, icon_key='mute_False'
    )
    # Mute açık
    surf_muted = menu._get_corner_button_surface(
        btn_size, (255, 50, 50), is_active=True, gamepad_selected=False, hover=False, icon_key='mute_True'
    )
    assert surf_unmuted is not surf_muted

    # Gamepad seçili
    surf_gp_selected = menu._get_corner_button_surface(
        btn_size, accent, is_active=False, gamepad_selected=True, hover=True, icon_key='mute_False'
    )
    assert surf_gp_selected is not surf_unmuted

    # Vektörel dil ikonunun Surface döndürdüğünü doğrula (emoji değil)
    globe_icon = menu._draw_globe_icon(32)
    assert isinstance(globe_icon, pygame.Surface)
    assert globe_icon.get_size() == (32, 32)


def test_lru_cache_capacity_eviction():
    """Cache kapasitesi aşıldığında en eski elemanın (LRU) atıldığını test et."""
    cache = SurfaceLRUCache(max_entries=5)

    surfaces = [pygame.Surface((10, 10)) for _ in range(7)]
    for i in range(5):
        cache.put((f'key_{i}',), surfaces[i])

    assert len(cache._cache) == 5
    assert cache.get(('key_0',)) is surfaces[0]

    # 6. ve 7. elemanları ekle (en eski elemanlar atılmalı)
    cache.put(('key_5',), surfaces[5])
    cache.put(('key_6',), surfaces[6])

    assert len(cache._cache) == 5
    # key_1 atılmış olmalı (key_0 az önce erişildiği için günceldi)
    assert cache.get(('key_1',)) is None
    assert cache.get(('key_5',)) is surfaces[5]
    assert cache.get(('key_6',)) is surfaces[6]


def test_dashboard_tile_and_button_hitbox_preservation():
    """Dashboard kartlarının çizim ve hitbox koordinatlarının değişmediğini test et."""
    menu = _create_test_menu()
    rect = pygame.Rect(120, 200, 280, 180)

    # _draw_main_dashboard_tile dönüş koordinatı
    returned_rect = menu._draw_main_dashboard_tile(
        rect, 'TEST', False, (0, 255, 255), subtitle='Sub', hover=False, panel_key='daily_challenge'
    )
    assert returned_rect == rect

    # Buton rect hesaplamaları (_draw_panel_micro_content)
    menu._draw_panel_micro_content(rect, 'new_gen_tetris', (0, 255, 255), {}, hover=False, target_surface=menu.screen)
    assert menu.new_gen_tetris_play_rect is not None
    assert rect.contains(menu.new_gen_tetris_play_rect)
