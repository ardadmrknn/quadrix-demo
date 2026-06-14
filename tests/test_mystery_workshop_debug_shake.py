import sys
import types

import pygame
import pytest

from screen_shake import (
    HARD_DROP_SCREEN_SHAKE_DURATION_SECONDS,
    HARD_DROP_SCREEN_SHAKE_INTENSITY,
)


_platform_utils = sys.modules.get('platform_utils')
if _platform_utils is not None and not hasattr(_platform_utils, 'get_display_scale_factor'):
    _platform_utils.get_display_scale_factor = lambda: 1.0


def _import_mystery_mode():
    if not hasattr(pygame, 'K_c'):
        pytest.skip('pygame stub environment: MysteryMode import skipped')
    from game_modes_extra import MysteryMode

    return MysteryMode


class _DummySettings:
    def __init__(self, debug_enabled: bool):
        self.debug_enabled = bool(debug_enabled)

    def get(self, key, default=None):
        if key == 'mystery_debug_block_workshop':
            return self.debug_enabled
        return default


def test_workshop_piece_hard_drop_boosts_shake_when_debug_enabled():
    MysteryMode = _import_mystery_mode()
    mode = MysteryMode.__new__(MysteryMode)
    mode.current_piece = types.SimpleNamespace(is_workshop_piece=True)
    mode.settings_manager = _DummySettings(True)

    captured = {}
    mode.trigger_screen_shake = lambda intensity, duration: captured.update(
        {'intensity': intensity, 'duration': duration}
    )

    mode.trigger_hard_drop_screen_shake()

    expected_intensity = max(
        HARD_DROP_SCREEN_SHAKE_INTENSITY + 2,
        int(round(HARD_DROP_SCREEN_SHAKE_INTENSITY * 1.6)),
    )
    expected_duration = max(
        HARD_DROP_SCREEN_SHAKE_DURATION_SECONDS * 1.35,
        HARD_DROP_SCREEN_SHAKE_DURATION_SECONDS + 0.04,
    )

    assert captured['intensity'] == expected_intensity
    assert captured['duration'] == pytest.approx(expected_duration)


def test_non_workshop_piece_uses_default_hard_drop_shake():
    MysteryMode = _import_mystery_mode()
    mode = MysteryMode.__new__(MysteryMode)
    mode.current_piece = types.SimpleNamespace(is_workshop_piece=False)
    mode.settings_manager = _DummySettings(True)

    captured = {}
    mode.trigger_screen_shake = lambda intensity, duration: captured.update(
        {'intensity': intensity, 'duration': duration}
    )

    mode.trigger_hard_drop_screen_shake()

    assert captured['intensity'] == HARD_DROP_SCREEN_SHAKE_INTENSITY
    assert captured['duration'] == pytest.approx(HARD_DROP_SCREEN_SHAKE_DURATION_SECONDS)
