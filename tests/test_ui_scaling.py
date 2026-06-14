from __future__ import annotations

import math

import pytest

import ui_scaling as ui_scaling_module

from ui_scaling import (
    CONTENT_SCALE_PROFILES,
    MODAL_SCALE_PROFILES,
    apply_ui_scale_preset,
    get_content_scale,
    get_effective_content_scale,
    get_effective_modal_scale,
    get_effective_scale,
    get_modal_scale,
    get_projected_effective_scale,
    get_scale,
    get_ui_scale_preset,
    normalize_ui_scale_preset,
    resolve_ui_scale_size,
    scale_px,
    set_ui_scale_preset,
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


def test_resolve_ui_scale_size_keeps_raw_size_without_opt_in():
    assert resolve_ui_scale_size((2560, 1440)) == (2560, 1440)


def test_resolve_ui_scale_size_rejects_effective_mode_for_tuple_input():
    with pytest.raises(TypeError):
        resolve_ui_scale_size((2560, 1440), use_effective_display_size=True)


def test_resolve_ui_scale_size_uses_effective_display_size_when_opted_in(monkeypatch):
    screen = _FakeScreen(2560, 1660)

    monkeypatch.setattr(
        ui_scaling_module,
        "_get_effective_display_size",
        lambda screen_or_size, display_surface=None: (1707, 1107),
    )

    assert resolve_ui_scale_size(screen, use_effective_display_size=True, display_surface=True) == (1707, 1107)


def test_get_effective_scale_uses_effective_display_size_when_opted_in(monkeypatch):
    screen = _FakeScreen(2560, 1660)

    monkeypatch.setattr(
        ui_scaling_module,
        "_get_effective_display_size",
        lambda screen_or_size, display_surface=None: (1707, 1107),
    )

    scale = get_effective_scale(
        screen,
        min_scale=0.65,
        max_scale=1.35,
        reference_size=(1920.0, 1080.0),
        display_surface=True,
    )

    expected = min(1707 / 1920.0, 1107 / 1080.0)
    expected = max(0.65, min(1.35, expected))
    assert math.isclose(scale, expected)


def test_get_projected_effective_scale_projects_logical_scale_back_to_raw_surface(monkeypatch):
    screen = _FakeScreen(2560, 1664)

    monkeypatch.setattr(
        ui_scaling_module,
        "_get_effective_display_size",
        lambda screen_or_size, display_surface=None: (1280, 832),
    )

    scale = get_projected_effective_scale(
        screen,
        min_scale=0.68,
        max_scale=1.20,
        reference_size=(1366.0, 768.0),
        display_surface=True,
    )

    expected_logical = min(1280 / 1366.0, 832 / 768.0)
    expected_logical = max(0.68, min(1.20, expected_logical))
    expected = expected_logical * 2.0
    assert math.isclose(scale, expected)


def test_get_projected_effective_scale_falls_back_to_raw_scale_for_tuple_input():
    scale = get_projected_effective_scale(
        (2560, 1440),
        min_scale=0.68,
        max_scale=1.20,
        reference_size=(1366.0, 768.0),
    )

    expected = min(2560 / 1366.0, 1440 / 768.0)
    expected = max(0.68, min(1.20, expected))
    assert math.isclose(scale, expected)


def test_normalize_ui_scale_preset_falls_back_to_normal():
    assert normalize_ui_scale_preset(None) == "normal"
    assert normalize_ui_scale_preset("unknown") == "normal"
    assert normalize_ui_scale_preset(" LARGE ") == "large"


def test_apply_ui_scale_preset_compact_honors_minimum():
    adjusted = apply_ui_scale_preset(0.74, min_scale=0.72, max_scale=1.24, preset="compact")

    assert math.isclose(adjusted, 0.72)


def test_apply_ui_scale_preset_is_more_visible_near_baseline_for_compact():
    adjusted = apply_ui_scale_preset(1.0, min_scale=0.72, max_scale=1.24, preset="compact")

    assert math.isclose(adjusted, 0.90)


def test_apply_ui_scale_preset_is_more_visible_near_baseline_for_large():
    adjusted = apply_ui_scale_preset(1.0, min_scale=0.72, max_scale=1.24, preset="large")

    assert math.isclose(adjusted, 1.12)


def test_apply_ui_scale_preset_m2_air_like_scale_has_clear_spread():
    compact = apply_ui_scale_preset(0.94, min_scale=0.72, max_scale=1.24, preset="compact")
    large = apply_ui_scale_preset(0.94, min_scale=0.72, max_scale=1.24, preset="large")

    assert math.isclose(compact, 0.84)
    assert math.isclose(large, 1.06)


def test_get_effective_scale_applies_large_preset_after_clamp(monkeypatch):
    screen = _FakeScreen(2560, 1660)
    previous = get_ui_scale_preset()

    monkeypatch.setattr(
        ui_scaling_module,
        "_get_effective_display_size",
        lambda screen_or_size, display_surface=None: (2560, 1440),
    )

    try:
        set_ui_scale_preset("large")
        scale = get_effective_scale(
            screen,
            min_scale=0.72,
            max_scale=1.24,
            reference_size=(1366.0, 768.0),
        )
    finally:
        set_ui_scale_preset(previous)

    assert math.isclose(scale, 1.24 * 1.08)


def test_get_scale_raw_path_ignores_ui_scale_preset():
    previous = get_ui_scale_preset()

    try:
        set_ui_scale_preset("large")
        scale = get_scale((2560, 1440), min_scale=0.72, max_scale=1.24, reference_size=(1366.0, 768.0))
    finally:
        set_ui_scale_preset(previous)

    assert math.isclose(scale, 1.24)


def test_get_modal_scale_accepts_screen_like_objects():
    scale = get_modal_scale(_FakeScreen(2560, 1440), profile="roomy")
    expected = min(2560 / 1920.0, 1440 / 1080.0)
    expected = max(MODAL_SCALE_PROFILES["roomy"][0], min(MODAL_SCALE_PROFILES["roomy"][1], expected))

    assert math.isclose(scale, expected)


def test_effective_profile_wrappers_reuse_existing_profile_clamps(monkeypatch):
    screen = _FakeScreen(2560, 1660)

    monkeypatch.setattr(
        ui_scaling_module,
        "_get_effective_display_size",
        lambda screen_or_size, display_surface=None: (1707, 1107),
    )

    content_scale = get_effective_content_scale(screen, profile="dense", display_surface=True)
    modal_scale = get_effective_modal_scale(screen, profile="roomy", display_surface=True)

    expected_content = min(1707 / 1920.0, 1107 / 1080.0)
    expected_content = max(CONTENT_SCALE_PROFILES["dense"][0], min(CONTENT_SCALE_PROFILES["dense"][1], expected_content))
    expected_modal = min(1707 / 1920.0, 1107 / 1080.0)
    expected_modal = max(MODAL_SCALE_PROFILES["roomy"][0], min(MODAL_SCALE_PROFILES["roomy"][1], expected_modal))

    assert math.isclose(content_scale, expected_content)
    assert math.isclose(modal_scale, expected_modal)


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