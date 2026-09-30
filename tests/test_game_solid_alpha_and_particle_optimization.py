"""Test suite for Paket A game optimizations in quadrix-demo:
- Solid alpha surface LRU cache hit and reuse
- Line clear burst particle throttling (stutter prevention)
- HUD action prompt surface caching
- Color tuple sanitization and edge-case safety
- Signature compatibility for multiplayer / test callers
"""
import os
import sys
import pygame
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))
from game import Game
from settings_manager import SettingsManager


@pytest.fixture(scope="module", autouse=True)
def init_pygame():
    pygame.init()
    if not pygame.display.get_init():
        pygame.display.init()
    if not pygame.font.get_init():
        pygame.font.init()
    yield
    pygame.quit()


def _create_test_game():
    screen = pygame.Surface((800, 600))
    sm = SettingsManager()
    return Game(screen=screen, settings_manager=sm)


def test_solid_alpha_surface_cache_hits():
    game = _create_test_game()
    
    surf1 = game._get_solid_alpha_surface((32, 32), (255, 0, 0, 100))
    surf2 = game._get_solid_alpha_surface((32, 32), (255, 0, 0, 100))
    surf3 = game._get_solid_alpha_surface((32, 32), (0, 255, 0, 100))
    
    # Same size and color must return the exact same Surface object from cache
    assert surf1 is surf2
    # Different color must return a distinct surface
    assert surf1 is not surf3
    assert surf1.get_size() == (32, 32)


def test_solid_alpha_surface_color_sanitization():
    game = _create_test_game()
    
    # RGBA tuple with 4 elements
    surf_rgba = game._get_solid_alpha_surface((24, 24), (200, 100, 50, 120))
    assert surf_rgba is not None
    assert surf_rgba.get_size() == (24, 24)

    # 3-element RGB tuple
    surf_rgb = game._get_solid_alpha_surface((24, 24), (100, 150, 200))
    assert surf_rgb is not None

    # Oversized tuple should be safely clamped/handled without TypeError
    surf_oversized = game._get_solid_alpha_surface((24, 24), (100, 150, 200, 255, 50))
    assert surf_oversized is not None

    # RGB and alpha channels are all clamped to Pygame's valid range.
    surf_clamped = game._get_solid_alpha_surface((2, 2), (256, -1, 300, 400))
    assert surf_clamped.get_at((0, 0)) == (255, 0, 255, 255)


def test_create_line_clear_particles_is_throttled_and_flexible():
    game = _create_test_game()
    
    initial_particle_count = len(game.particles)
    # Trigger line clear particle generation with extra kwargs (like board=...)
    game.create_line_clear_particles([10, 11], board_offset_x=100, board_offset_y=100, cell_size=30, board=getattr(game, 'board', None))
    
    # Must remain zero / throttled to avoid frame spikes during sweep animation
    assert len(game.particles) == initial_particle_count


def test_hud_action_prompt_cache_hits():
    game = _create_test_game()
    font = pygame.font.SysFont(None, 20)
    
    p1 = game._cached_action_prompt_surface('hold', 'C', font, (255, 255, 255))
    p2 = game._cached_action_prompt_surface('hold', 'C', font, (255, 255, 255))
    
    assert p1 is not None
    assert p1 is p2


def test_hud_action_prompt_cache_tracks_prompt_state(monkeypatch):
    game = _create_test_game()
    font = pygame.font.SysFont(None, 20)
    state = {'connected': False}

    monkeypatch.setattr(
        'game.get_action_prompt_display',
        lambda action, label: {
            'mode': 'glyph' if state['connected'] else 'text',
            'glyph': 'A' if state['connected'] else None,
            'text': 'A' if state['connected'] else label,
        },
    )

    first = game._cached_action_prompt_surface('menu_confirm', 'ENTER', font, (255, 255, 255))
    state['connected'] = True
    second = game._cached_action_prompt_surface('menu_confirm', 'ENTER', font, (255, 255, 255))

    assert first is not second


def test_inline_action_prompt_cache_tracks_prompt_state(monkeypatch):
    game = _create_test_game()
    font = pygame.font.SysFont(None, 20)
    state = {'connected': False}

    monkeypatch.setattr(
        'game.get_action_prompt_display',
        lambda action, label: {
            'mode': 'glyph' if state['connected'] else 'text',
            'glyph': 'A' if state['connected'] else None,
            'text': 'A' if state['connected'] else label,
        },
    )

    first = game._cached_inline_action_text_surface('Hold C', 'C', 'hold', font, (255, 255, 255))
    state['connected'] = True
    second = game._cached_inline_action_text_surface('Hold C', 'C', 'hold', font, (255, 255, 255))

    assert first is not second


def test_pause_menu_reuses_cached_dim_overlay(monkeypatch):
    game = _create_test_game()
    game.pause_menu_options = ['Devam Et']
    game.pause_menu_selected = 0
    game._overlay_ui_scale = lambda: 1.0
    game.screen = pygame.Surface((800, 600))
    monkeypatch.setattr('game.get_mouse_pos', lambda: (0, 0))

    for _ in range(3):
        game._draw_pause_menu()

    key = (800, 600, (0, 0, 0, 185))
    assert list(game._solid_alpha_surface_cache).count(key) == 1


def test_sync_runtime_settings_clears_prompt_cache():
    game = _create_test_game()
    font = pygame.font.SysFont(None, 20)
    
    game._cached_action_prompt_surface('hold', 'C', font, (255, 255, 255))
    assert len(game._hud_prompt_surface_cache) > 0
    
    # Settings changed / rebind synchronized
    game._sync_runtime_settings_from_manager()
    assert len(game._hud_prompt_surface_cache) == 0
