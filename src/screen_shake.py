from __future__ import annotations

import random


DEFAULT_SCREEN_SHAKE_DURATION_SECONDS = 15 / 60.0
HARD_DROP_SCREEN_SHAKE_DURATION_SECONDS = 0.14
HARD_DROP_SCREEN_SHAKE_INTENSITY = 3

_DEFAULT_SHAKE_DT_MS = 1000.0 / 60.0
_MAX_SHAKE_STEP_DT_MS = 100.0


def begin_screen_shake(
    state,
    *,
    intensity: int = 10,
    duration: float = DEFAULT_SCREEN_SHAKE_DURATION_SECONDS,
    enabled: bool | None = None,
) -> None:
    """Start or replace the current screen shake.

    Duration is expressed in seconds and internally stored as milliseconds.
    A new trigger always replaces the current shake instead of stacking.
    """
    if enabled is None:
        enabled = bool(getattr(state, 'effects_enabled', True))
    if not enabled:
        return

    try:
        duration_seconds = float(duration)
    except Exception:
        duration_seconds = DEFAULT_SCREEN_SHAKE_DURATION_SECONDS

    try:
        intensity_px = int(round(float(intensity)))
    except Exception:
        intensity_px = 0

    duration_ms = max(0.0, duration_seconds * 1000.0)
    if duration_ms <= 0.0 or intensity_px <= 0:
        state.screen_shake = 0.0
        state.shake_intensity = 0
        state._screen_shake_initial = 0.0
        return

    state._screen_shake_initial = duration_ms
    state.screen_shake = duration_ms
    state.shake_intensity = intensity_px


def step_screen_shake(state, *, dt_ms: float | None = None) -> None:
    """Advance the current screen shake by elapsed milliseconds."""
    remaining = float(getattr(state, 'screen_shake', 0.0) or 0.0)
    if remaining <= 0.0:
        state.screen_shake = 0.0
        return

    try:
        dt = float(dt_ms) if dt_ms is not None else float(getattr(state, '_last_dt_ms', _DEFAULT_SHAKE_DT_MS))
    except Exception:
        dt = _DEFAULT_SHAKE_DT_MS

    dt = max(0.0, min(_MAX_SHAKE_STEP_DT_MS, dt))
    state.screen_shake = max(0.0, remaining - dt)


def sample_screen_shake_offset(state) -> tuple[int, int]:
    """Return the current decayed shake offset."""
    remaining = float(getattr(state, 'screen_shake', 0.0) or 0.0)
    if remaining <= 0.0:
        return (0, 0)

    intensity = int(getattr(state, 'shake_intensity', 0) or 0)
    if intensity <= 0:
        return (0, 0)

    initial = max(1.0, float(getattr(state, '_screen_shake_initial', remaining) or remaining))
    decay = max(0.0, min(1.0, remaining / initial))
    shake_x = random.randint(-intensity, intensity)
    shake_y = random.randint(-intensity, intensity)
    return (int(shake_x * decay), int(shake_y * decay))