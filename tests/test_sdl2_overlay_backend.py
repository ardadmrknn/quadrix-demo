"""SDL2 overlay backend (Yol 2) için birim testler.

Kapsanan:
- sdl2_overlay modülünün gl_compat ile arayüz paritesi (gerekli public fonksiyonlar var).
- _should_use_sdl2 platform/steam koşulları.
- should_skip_display_rebuild / get_game_surface davranışı (aktif değilken).
- _present hata-toleransı (aktif değilken no-op).
"""

import os
import sys

import pygame  # noqa: F401  (gerçek pygame; sdl2_overlay import için gerekli)


SRC_DIR = os.path.join(os.path.dirname(__file__), '..', 'src')
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

import sdl2_overlay


def test_sdl2_overlay_has_gl_compat_parity_interface():
    """sdl2_overlay, main.py'nin beklediği public arayüzü sağlamalı."""
    for name in (
        'prepare_single_context',
        'gl_overlay_setup',
        'setup',
        'is_active',
        'is_gl_active',
        'get_display_surface',
        'get_game_surface',
        'should_skip_display_rebuild',
        'register_gpu_overlay_drawer',
        'unregister_gpu_overlay_drawer',
        'probe_sdl2_texture_properties',
        'get_cursor_mode',
        '_reapply_gl',
        '_diag_log',
        'teardown',
    ):
        assert hasattr(sdl2_overlay, name), f"sdl2_overlay.{name} eksik"


def test_should_use_sdl2_false_on_non_windows(monkeypatch):
    monkeypatch.setattr(sdl2_overlay.platform, 'system', lambda: 'Darwin')
    assert sdl2_overlay._should_use_sdl2() is False


def test_is_active_false_initially(monkeypatch):
    monkeypatch.setattr(sdl2_overlay, '_active', False)
    assert sdl2_overlay.is_active() is False
    assert sdl2_overlay.is_gl_active() is False


def test_should_skip_display_rebuild_false_when_inactive(monkeypatch):
    monkeypatch.setattr(sdl2_overlay, '_active', False)
    monkeypatch.setattr(sdl2_overlay, '_game_surface', None)
    assert sdl2_overlay.should_skip_display_rebuild(1920, 1080) is False


def test_should_skip_display_rebuild_true_when_active_same_size(monkeypatch):
    monkeypatch.setattr(sdl2_overlay.platform, 'system', lambda: 'Windows')
    monkeypatch.setattr(sdl2_overlay, '_active', True)
    monkeypatch.setattr(sdl2_overlay, '_game_surface', pygame.Surface((1920, 1080)))
    monkeypatch.setattr(sdl2_overlay, '_width', 1920)
    monkeypatch.setattr(sdl2_overlay, '_height', 1080)
    assert sdl2_overlay.should_skip_display_rebuild(1920, 1080) is True
    assert sdl2_overlay.should_skip_display_rebuild(1280, 720) is False


def test_present_noop_when_inactive(monkeypatch):
    """Aktif değilken _present() sessizce hiçbir şey yapmamalı (exception fırlatmamalı)."""
    monkeypatch.setattr(sdl2_overlay, '_active', False)
    sdl2_overlay._present()  # exception yok


def test_gpu_overlay_drawer_registration(monkeypatch):
    monkeypatch.setattr(sdl2_overlay, '_gpu_overlay_drawers', [])

    def callback(renderer):
        return None

    assert sdl2_overlay.register_gpu_overlay_drawer(callback) is True
    assert sdl2_overlay.register_gpu_overlay_drawer(callback) is False
    assert sdl2_overlay.unregister_gpu_overlay_drawer(callback) is True
    assert sdl2_overlay.unregister_gpu_overlay_drawer(callback) is False


def test_cursor_none_clears_cached_active_texture(monkeypatch):
    marker = object()
    monkeypatch.setattr(sdl2_overlay, '_cursor_texture', marker)
    monkeypatch.setattr(sdl2_overlay, '_cursor_size', (32, 32))

    sdl2_overlay.set_software_cursor(None)

    assert sdl2_overlay._cursor_texture is None
    assert sdl2_overlay._cursor_size == (0, 0)


def test_gl_overlay_setup_returns_original_when_unavailable(monkeypatch):
    """SDL2 kullanılamıyorsa gl_overlay_setup orijinal surface'i döndürmeli."""
    monkeypatch.setattr(sdl2_overlay, '_should_use_sdl2', lambda: False)
    surf = pygame.Surface((640, 480))
    result = sdl2_overlay.gl_overlay_setup(surf)
    assert result is surf


def test_prepare_single_context_returns_availability(monkeypatch):
    monkeypatch.setattr(sdl2_overlay, '_should_use_sdl2', lambda: False)
    assert sdl2_overlay.prepare_single_context() is False
    monkeypatch.setattr(sdl2_overlay, '_should_use_sdl2', lambda: True)
    assert sdl2_overlay.prepare_single_context() is True
