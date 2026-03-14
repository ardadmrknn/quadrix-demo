from __future__ import annotations

import os
import sys

import pygame


SRC_DIR = os.path.join(os.path.dirname(__file__), '..', 'src')
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from color_picker import _build_sv_surface, _hsv_to_rgb


def _reference_sv_color(x: int, y: int, w: int, h: int, hue: float) -> tuple[int, int, int]:
    saturation = x / max(1, w - 1)
    value = 1.0 - y / max(1, h - 1)
    return _hsv_to_rgb(hue, saturation, value)


def _max_channel_diff(left: tuple[int, int, int], right: tuple[int, int, int]) -> int:
    return max(abs(left[i] - right[i]) for i in range(3))


def test_build_sv_surface_returns_requested_size():
    surface = _build_sv_surface(17, 23, 0.33)
    assert surface.get_size() == (17, 23)


def test_build_sv_surface_top_left_is_white():
    surface = _build_sv_surface(8, 8, 0.5)
    assert surface.get_at((0, 0))[:3] == (255, 255, 255)


def test_build_sv_surface_top_right_matches_pure_hue():
    hue = 0.5
    surface = _build_sv_surface(8, 8, hue)
    assert surface.get_at((7, 0))[:3] == _hsv_to_rgb(hue, 1.0, 1.0)


def test_build_sv_surface_bottom_row_is_black():
    surface = _build_sv_surface(8, 8, 0.2)
    for x in range(8):
        assert surface.get_at((x, 7))[:3] == (0, 0, 0)


def test_build_sv_surface_handles_single_column():
    surface = _build_sv_surface(1, 4, 0.2)
    assert surface.get_at((0, 0))[:3] == (255, 255, 255)
    assert surface.get_at((0, 3))[:3] == (0, 0, 0)


def test_build_sv_surface_handles_single_row():
    hue = 0.8
    surface = _build_sv_surface(4, 1, hue)
    assert surface.get_at((0, 0))[:3] == (255, 255, 255)
    assert surface.get_at((3, 0))[:3] == _hsv_to_rgb(hue, 1.0, 1.0)


def test_build_sv_surface_stays_close_to_reference_hsv_values():
    sample_points = [(0, 0), (3, 1), (7, 4), (11, 9), (15, 15)]
    for hue in (0.0, 0.1, 0.33, 0.5, 0.66, 0.9):
        surface = _build_sv_surface(16, 16, hue)
        for x, y in sample_points:
            expected = _reference_sv_color(x, y, 16, 16, hue)
            actual = surface.get_at((x, y))[:3]
            assert _max_channel_diff(actual, expected) <= 3, (
                f"Hue={hue} nokta=({x},{y}) beklenen={expected} alinan={actual}"
            )


def test_build_sv_surface_uses_real_pygame_surface():
    surface = _build_sv_surface(6, 6, 0.25)
    assert isinstance(surface, pygame.Surface)