from __future__ import annotations

import os
import sys
from types import SimpleNamespace


ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
SRC_DIR = os.path.join(ROOT_DIR, 'src')
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)


from screen_shake import (  # noqa: E402
    HARD_DROP_SCREEN_SHAKE_DURATION_SECONDS,
    HARD_DROP_SCREEN_SHAKE_INTENSITY,
    begin_screen_shake,
    sample_screen_shake_offset,
    step_screen_shake,
)


def _state():
    return SimpleNamespace(
        effects_enabled=True,
        screen_shake=0.0,
        shake_intensity=0,
        _screen_shake_initial=0.0,
    )


def test_begin_screen_shake_uses_seconds():
    state = _state()

    begin_screen_shake(state, intensity=7, duration=0.2)

    assert round(state.screen_shake, 3) == 200.0
    assert round(state._screen_shake_initial, 3) == 200.0
    assert state.shake_intensity == 7


def test_begin_screen_shake_restarts_existing_state():
    state = _state()

    begin_screen_shake(state, intensity=9, duration=0.5)
    step_screen_shake(state, dt_ms=120.0)
    begin_screen_shake(
        state,
        intensity=HARD_DROP_SCREEN_SHAKE_INTENSITY,
        duration=HARD_DROP_SCREEN_SHAKE_DURATION_SECONDS,
    )

    expected_ms = HARD_DROP_SCREEN_SHAKE_DURATION_SECONDS * 1000.0
    assert round(state.screen_shake, 3) == round(expected_ms, 3)
    assert round(state._screen_shake_initial, 3) == round(expected_ms, 3)
    assert state.shake_intensity == HARD_DROP_SCREEN_SHAKE_INTENSITY


def test_step_screen_shake_uses_elapsed_milliseconds():
    state = _state()

    begin_screen_shake(state, intensity=4, duration=0.25)
    step_screen_shake(state, dt_ms=40.0)

    assert round(state.screen_shake, 3) == 210.0


def test_sample_screen_shake_offset_returns_zero_when_inactive():
    assert sample_screen_shake_offset(_state()) == (0, 0)