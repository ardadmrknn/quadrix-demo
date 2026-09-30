"""Test suite for Paket B: Platform refresh rate, VRR/G-Sync filtering and dynamic FPS caps."""
import os
import sys
import pytest
import pygame

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))
import platform_utils
from platform_utils import (
    resolve_frame_rate_cap,
    invalidate_refresh_rate_cache,
    create_display,
    _query_max_refresh_rate,
)


@pytest.fixture(autouse=True)
def clean_refresh_rate_cache():
    invalidate_refresh_rate_cache()
    yield
    invalidate_refresh_rate_cache()


def test_vrr_30hz_with_nominal_144hz_resolves_to_144(monkeypatch):
    """When SDL reports 30Hz dynamic cadence on a 144Hz panel, nominal 144Hz must be used."""
    monkeypatch.setattr(platform_utils, '_query_desktop_refresh_rates', lambda: [144])
    monkeypatch.setattr(pygame.display, 'get_current_refresh_rate', lambda: 30)

    rate = _query_max_refresh_rate()
    assert rate == 144

    cap = resolve_frame_rate_cap(0)
    assert cap == 144


def test_vrr_low_rate_without_nominal_falls_back_to_safe_60(monkeypatch):
    """When SDL reports <= 45Hz and no nominal desktop rates exist, fallback to 60Hz."""
    monkeypatch.setattr(platform_utils, '_query_desktop_refresh_rates', lambda: [])
    monkeypatch.setattr(pygame.display, 'get_current_refresh_rate', lambda: 30)

    rate = _query_max_refresh_rate()
    assert rate == 60

    cap = resolve_frame_rate_cap(0)
    assert cap == 60


def test_explicit_fps_limit_is_strictly_preserved(monkeypatch):
    """User-requested limits (e.g. 120, 144, 240) must never be overwritten by display rate."""
    monkeypatch.setattr(platform_utils, 'get_max_refresh_rate', lambda *args, **kwargs: 60)

    assert resolve_frame_rate_cap(120) == 120
    assert resolve_frame_rate_cap(144) == 144
    assert resolve_frame_rate_cap(240) == 240


def test_macos_auto_fallback_uses_90hz_when_rate_invalid(monkeypatch):
    """On macOS, invalid refresh rates in auto mode must fallback to 90Hz for ProMotion."""
    monkeypatch.setattr(platform_utils, 'get_max_refresh_rate', lambda *args, **kwargs: 0)
    monkeypatch.setattr(sys, 'platform', 'darwin')

    cap = resolve_frame_rate_cap(0, fallback=60)
    assert cap == 90

    # Explicit limit must still be preserved on macOS
    assert resolve_frame_rate_cap(60, fallback=60) == 60


def test_window_mode_clamping_and_centering(monkeypatch):
    """Window sizes larger than native desktop must be clamped and centered."""
    monkeypatch.setattr(platform_utils, 'get_native_resolution', lambda: (1366, 768))
    monkeypatch.setattr(platform_utils, 'IS_MACOS', False)
    monkeypatch.setattr(platform_utils, 'overlay_active_game_surface', lambda: None)

    captured_size = None
    captured_flags = None

    def fake_set_mode(size, flags, vsync=0):
        nonlocal captured_size, captured_flags
        captured_size = size
        captured_flags = flags
        surf = pygame.Surface(size)
        return surf

    monkeypatch.setattr(platform_utils.pygame.display, 'set_mode', fake_set_mode)
    monkeypatch.setattr(pygame.display, 'set_mode', fake_set_mode)

    # Request oversized 3840x2160 window on 1366x768 monitor
    surface = create_display(3840, 2160, fullscreen=False, resizable=True)
    assert captured_size is not None
    # Must be clamped down to <= 1366x768 (e.g. 1280x720 preset or clamped min)
    assert captured_size[0] <= 1366
    assert captured_size[1] <= 768


def test_create_display_restores_sdl_video_centered_env(monkeypatch):
    """create_display must restore SDL_VIDEO_CENTERED in finally block."""
    monkeypatch.setattr(platform_utils, 'get_native_resolution', lambda: (1920, 1080))
    monkeypatch.setattr(platform_utils, 'IS_MACOS', False)
    monkeypatch.setattr(platform_utils, 'overlay_active_game_surface', lambda: None)
    fake_surf = lambda size, flags, vsync=0: pygame.Surface(size)
    monkeypatch.setattr(platform_utils.pygame.display, 'set_mode', fake_surf)
    monkeypatch.setattr(pygame.display, 'set_mode', fake_surf)

    # Pre-condition: no env var
    os.environ.pop('SDL_VIDEO_CENTERED', None)
    create_display(1280, 720, fullscreen=False)
    assert 'SDL_VIDEO_CENTERED' not in os.environ

    # Pre-condition: existing env var '0'
    os.environ['SDL_VIDEO_CENTERED'] = '0'
    create_display(1280, 720, fullscreen=False)
    assert os.environ.get('SDL_VIDEO_CENTERED') == '0'
    os.environ.pop('SDL_VIDEO_CENTERED', None)
