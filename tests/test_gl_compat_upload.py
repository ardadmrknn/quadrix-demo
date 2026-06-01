from __future__ import annotations

import os
import sys
import types

import pygame


SRC_DIR = os.path.join(os.path.dirname(__file__), '..', 'src')
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

import gl_compat


class DummySurface:
    def __init__(self, *, width=8, bitsize=32, bytesize=4, pitch=32, masks=(0x00FF0000, 0x0000FF00, 0x000000FF, 0)):
        self._width = width
        self._bitsize = bitsize
        self._bytesize = bytesize
        self._pitch = pitch
        self._masks = masks
        self._buffer = bytearray(pitch * 4)

    def get_size(self):
        return (self._width, 4)

    def get_bitsize(self):
        return self._bitsize

    def get_bytesize(self):
        return self._bytesize

    def get_pitch(self):
        return self._pitch

    def get_masks(self):
        return self._masks

    def get_buffer(self):
        return self._buffer


def test_get_upload_source_prefers_direct_buffer_for_compatible_surface(monkeypatch):
    surface = DummySurface()

    def _unexpected_tostring(*args, **kwargs):
        raise AssertionError('fallback tostring yolu kullanilmamali')

    monkeypatch.setattr(pygame.image, 'tostring', _unexpected_tostring)
    monkeypatch.setattr(gl_compat, '_can_use_direct_bgra_upload', lambda: True)

    gl_format, payload, flip_y = gl_compat._get_upload_source(surface)

    assert gl_format == gl_compat.GL_BGRA
    assert payload is surface.get_buffer()
    assert flip_y is False


def test_get_upload_source_falls_back_for_incompatible_surface(monkeypatch):
    surface = DummySurface(bitsize=24, bytesize=3, pitch=24)
    calls: list[tuple[object, str, bool]] = []

    def _fake_tostring(src_surface, fmt, flipped):
        calls.append((src_surface, fmt, flipped))
        return b'rgba-bytes'

    monkeypatch.setattr(pygame.image, 'tostring', _fake_tostring)
    monkeypatch.setattr(gl_compat, '_can_use_direct_bgra_upload', lambda: True)

    gl_format, payload, flip_y = gl_compat._get_upload_source(surface)

    assert gl_format == gl_compat.GL_RGBA
    assert payload == b'rgba-bytes'
    assert flip_y is True
    assert calls == [(surface, 'RGBA', True)]


def test_get_upload_source_falls_back_when_bgra_upload_is_unsupported(monkeypatch):
    surface = DummySurface()
    calls: list[tuple[object, str, bool]] = []

    def _fake_tostring(src_surface, fmt, flipped):
        calls.append((src_surface, fmt, flipped))
        return b'rgba-bytes'

    monkeypatch.setattr(pygame.image, 'tostring', _fake_tostring)
    monkeypatch.setattr(gl_compat, '_can_use_direct_bgra_upload', lambda: False)

    gl_format, payload, flip_y = gl_compat._get_upload_source(surface)

    assert gl_format == gl_compat.GL_RGBA
    assert payload == b'rgba-bytes'
    assert flip_y is True
    assert calls == [(surface, 'RGBA', True)]


def test_patch_create_display_module_refs_updates_preimported_references():
    def original_create_display(width, height, **kwargs):
        return (width, height, kwargs)

    def wrapped_create_display(width, height, **kwargs):
        return ('wrapped', width, height, kwargs)

    fake_platform_utils = types.ModuleType('fake_platform_utils')
    fake_platform_utils.create_display = original_create_display

    consumer_module = types.ModuleType('consumer_module')
    consumer_module.create_display = original_create_display

    unrelated_module = types.ModuleType('unrelated_module')
    unrelated_module.create_display = lambda *args, **kwargs: None

    gl_compat._patch_create_display_module_refs(
        [fake_platform_utils, consumer_module, unrelated_module],
        {original_create_display: wrapped_create_display},
    )

    assert fake_platform_utils.create_display is wrapped_create_display
    assert consumer_module.create_display is wrapped_create_display
    assert unrelated_module.create_display is not wrapped_create_display


# ---------------------------------------------------------------------------
# Tek-context (single-context) koordinasyon testleri
# ---------------------------------------------------------------------------

def test_prepare_single_context_sets_request_when_gl_available(monkeypatch):
    """Windows + Steam + GL mevcutken platform_utils'e GL pencere talebi iletilir."""
    import platform_utils

    monkeypatch.setattr(gl_compat, '_should_use_gl', lambda: True)
    recorded = {}
    monkeypatch.setattr(
        platform_utils,
        'set_gl_window_request',
        lambda enabled: recorded.__setitem__('value', enabled),
    )

    result = gl_compat.prepare_single_context()

    assert result is True
    assert recorded.get('value') is True


def test_prepare_single_context_disables_request_when_unavailable(monkeypatch):
    """GL kullanılamıyorsa talep False yapılır ve fonksiyon False döner."""
    import platform_utils

    monkeypatch.setattr(gl_compat, '_should_use_gl', lambda: False)
    recorded = {}
    monkeypatch.setattr(
        platform_utils,
        'set_gl_window_request',
        lambda enabled: recorded.__setitem__('value', enabled),
    )

    result = gl_compat.prepare_single_context()

    assert result is False
    assert recorded.get('value') is False


def test_should_use_gl_false_on_non_windows(monkeypatch):
    """Windows dışı platformda GL yolu devre dışıdır (Gereksinim 6)."""
    monkeypatch.setattr(gl_compat.platform, 'system', lambda: 'Darwin')
    assert gl_compat._should_use_gl() is False
