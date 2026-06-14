"""Combo popup text styling helpers shared by gameplay modes."""

from __future__ import annotations

import re


COMBO_POPUP_SHADOW_COLOR = (0, 0, 0)
COMBO_POPUP_DEFAULT_COLOR = (255, 255, 255)
COMBO_POPUP_QUADRIX_COLOR = (255, 215, 0)
COMBO_POPUP_TRIPLE_COLOR = (255, 0, 255)
COMBO_POPUP_DOUBLE_COLOR = (0, 255, 221)
COMBO_POPUP_LOW_COMBO_COLOR = (0, 255, 221)
COMBO_POPUP_MID_COMBO_COLOR = (100, 255, 100)
COMBO_POPUP_HIGH_COMBO_COLOR = (255, 170, 0)
COMBO_POPUP_ULTRA_COMBO_COLOR = (255, 85, 170)
COMBO_POPUP_FADE_FRAMES = 30.0


_COMBO_COUNT_RE = re.compile(r"x\s*(\d+)\s*Combo!?")


def extract_combo_count(message: str) -> int:
    if not message:
        return 0
    match = _COMBO_COUNT_RE.search(message)
    if not match:
        return 0
    try:
        return int(match.group(1))
    except (TypeError, ValueError):
        return 0


def get_combo_popup_color(message: str) -> tuple[int, int, int]:
    combo_count = extract_combo_count(message)
    if 'QUADRIX' in message:
        return COMBO_POPUP_QUADRIX_COLOR
    if combo_count >= 8:
        return COMBO_POPUP_ULTRA_COMBO_COLOR
    if combo_count >= 6:
        return COMBO_POPUP_HIGH_COMBO_COLOR
    if combo_count >= 4:
        return COMBO_POPUP_MID_COMBO_COLOR
    if combo_count >= 2:
        return COMBO_POPUP_LOW_COMBO_COLOR
    if 'TRIPLE' in message:
        return COMBO_POPUP_TRIPLE_COLOR
    if 'DOUBLE' in message:
        return COMBO_POPUP_DOUBLE_COLOR
    return COMBO_POPUP_DEFAULT_COLOR


def get_combo_popup_alpha(timer: float | int) -> int:
    try:
        timer_value = float(timer)
    except (TypeError, ValueError):
        return 0
    if timer_value <= 0:
        return 0
    if timer_value < COMBO_POPUP_FADE_FRAMES:
        return max(0, min(255, int(timer_value * 255 / COMBO_POPUP_FADE_FRAMES)))
    return 255