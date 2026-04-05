from __future__ import annotations

import math

import pytest

from ui_scaling import (
    CONTENT_SCALE_PROFILES,
    MODAL_SCALE_PROFILES,
    get_content_scale,
    get_modal_scale,
    get_scale,
    scale_px,
)


class _FakeScreen:
    def __init__(self, width: int, height: int):
        self._size = (width, height)

    def get_size(self) -> tuple[int, int]:
        return self._size


class _RectLike:
    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height


def test_get_content_scale_is_one_at_1080p_reference():
    scale = get_content_scale((1920, 1080))
    assert math.isclose(scale, 1.0)


def test_get_content_scale_uses_standard_cap_on_large_displays():
    scale = get_content_scale((3840, 2160))
    assert math.isclose(scale, CONTENT_SCALE_PROFILES["standard"][1])


def test_get_content_scale_dense_profile_is_more_conservative():
    standard_scale = get_content_scale((3840, 2160), profile="standard")
    dense_scale = get_content_scale((3840, 2160), profile="dense")

    assert dense_scale < standard_scale
    assert math.isclose(dense_scale, CONTENT_SCALE_PROFILES["dense"][1])


def test_get_content_scale_accepts_custom_reference_size():
    scale = get_content_scale((1400, 900), reference_size=(1400.0, 900.0))
    assert math.isclose(scale, 1.0)


def test_get_modal_scale_accepts_screen_like_objects():
    scale = get_modal_scale(_FakeScreen(2560, 1440), profile="roomy")
    expected = min(2560 / 1920.0, 1440 / 1080.0)
    expected = max(MODAL_SCALE_PROFILES["roomy"][0], min(MODAL_SCALE_PROFILES["roomy"][1], expected))

    assert math.isclose(scale, expected)


def test_get_content_scale_accepts_rect_like_objects():
    scale = get_content_scale(_RectLike(2560, 1440), profile="dense_content")
    expected = min(2560 / 1920.0, 1440 / 1080.0)
    expected = max(CONTENT_SCALE_PROFILES["dense_content"][0], min(CONTENT_SCALE_PROFILES["dense_content"][1], expected))

    assert math.isclose(scale, expected)


def test_get_scale_rejects_invalid_reference_size():
    with pytest.raises(ValueError):
        get_scale((1920, 1080), min_scale=0.72, max_scale=1.16, reference_size=(0.0, 1080.0))


def test_get_scale_rejects_inverted_clamp_range():
    with pytest.raises(ValueError):
        get_scale((1920, 1080), min_scale=1.16, max_scale=0.72)


def test_get_content_scale_rejects_unknown_profile():
    with pytest.raises(ValueError):
        get_content_scale((1920, 1080), profile="unknown")


def test_scale_px_rounds_and_honors_minimum():
    assert scale_px(10, 1.16) == 12
    assert scale_px(0.4, 1.0, minimum=3) == 3