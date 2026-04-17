from __future__ import annotations

import pygame

import retro_style as retro_style_module


def _render_background(monkeypatch, *, is_macos: bool) -> bytes:
    style = retro_style_module.RetroStyle()
    style._image_background.enabled = False
    style._image_background.background_image = None
    style._bg_cache.clear()
    style._scan_cache.clear()

    screen = pygame.Surface((320, 180), pygame.SRCALPHA)
    style.draw_background(screen)
    return pygame.image.tobytes(screen, 'RGBA')


def test_draw_background_matches_windows_path_when_platform_flag_is_macos(monkeypatch):
    pygame.init()

    windows_pixels = _render_background(monkeypatch, is_macos=False)
    macos_pixels = _render_background(monkeypatch, is_macos=True)

    assert macos_pixels == windows_pixels
