import pathlib
import sys
from types import SimpleNamespace

import pygame


ROOT_DIR = pathlib.Path(__file__).parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src import splash_screen as splash_screen_module


def test_recover_display_after_focus_loss_rebuilds_sparkle_bounds(monkeypatch):
    splash = splash_screen_module.SplashScreen.__new__(splash_screen_module.SplashScreen)
    splash.screen = pygame.Surface((800, 600), pygame.SRCALPHA)
    splash.settings_manager = SimpleNamespace(get=lambda key, default=None: {'fullscreen': False, 'borderless_fullscreen': True}.get(key, default))
    splash._last_display_recover_ms = -10000
    splash.sparkles = [splash_screen_module.Sparkle(800, 600) for _ in range(3)]
    splash.screen_w = 800
    splash.screen_h = 600

    monkeypatch.setattr(splash_screen_module.sys, 'platform', 'win32')
    monkeypatch.setattr(splash_screen_module.pygame.time, 'get_ticks', lambda: 5000)

    import platform_utils as platform_utils_module

    monkeypatch.setattr(
        platform_utils_module,
        'create_display',
        lambda width, height, fullscreen=False, resizable=True, borderless=False: pygame.Surface((width, height), pygame.SRCALPHA),
    )
    monkeypatch.setattr(platform_utils_module, 'request_window_focus', lambda: None)

    assert splash._recover_display_after_focus_loss('focus_regain') is True
    assert splash.screen.get_size() == (800, 600)
    assert splash.screen_w == 800
    assert splash.screen_h == 600
    assert len(splash.sparkles) == 3
    assert all(sp.screen_w == 800 and sp.screen_h == 600 for sp in splash.sparkles)


def test_recover_display_after_focus_loss_adopts_new_surface_size(monkeypatch):
    splash = splash_screen_module.SplashScreen.__new__(splash_screen_module.SplashScreen)
    splash.screen = pygame.Surface((800, 600), pygame.SRCALPHA)
    splash.settings_manager = SimpleNamespace(get=lambda key, default=None: {'fullscreen': False, 'borderless_fullscreen': True}.get(key, default))
    splash._last_display_recover_ms = -10000
    splash.sparkles = [splash_screen_module.Sparkle(800, 600)]
    splash.screen_w = 800
    splash.screen_h = 600

    monkeypatch.setattr(splash_screen_module.sys, 'platform', 'win32')
    monkeypatch.setattr(splash_screen_module.pygame.time, 'get_ticks', lambda: 5000)

    import platform_utils as platform_utils_module

    monkeypatch.setattr(
        platform_utils_module,
        'create_display',
        lambda width, height, fullscreen=False, resizable=True, borderless=False: pygame.Surface((1600, 900), pygame.SRCALPHA),
    )
    monkeypatch.setattr(platform_utils_module, 'request_window_focus', lambda: None)

    assert splash._recover_display_after_focus_loss('focus_regain') is True
    assert splash.screen.get_size() == (1600, 900)
    assert splash.screen_w == 1600
    assert splash.screen_h == 900
    assert all(sp.screen_w == 1600 and sp.screen_h == 900 for sp in splash.sparkles)