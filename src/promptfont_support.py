from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import pygame

from gamepad_manager import GamepadType


_FONT_CACHE: dict[int, pygame.font.Font] = {}
_GLYPH_SURFACE_CACHE: dict[tuple[str, int, tuple[int, int, int]], pygame.Surface] = {}
_FONT_LOAD_FAILED = False


def _get_base_dir() -> Path:
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent


def _get_promptfont_path() -> Path:
    return _get_base_dir() / 'assets' / 'gamepad_icon' / 'promptfont' / 'promptfont.ttf'


def get_promptfont(size: int) -> Optional[pygame.font.Font]:
    global _FONT_LOAD_FAILED

    try:
        font_size = max(1, int(size))
    except Exception:
        font_size = 1

    cached = _FONT_CACHE.get(font_size)
    if cached is not None:
        return cached

    if _FONT_LOAD_FAILED:
        return None

    try:
        if not pygame.font.get_init():
            pygame.font.init()
    except Exception:
        _FONT_LOAD_FAILED = True
        return None

    font_path = _get_promptfont_path()
    if not font_path.exists():
        _FONT_LOAD_FAILED = True
        return None

    try:
        font = pygame.font.Font(str(font_path), font_size)
    except Exception:
        _FONT_LOAD_FAILED = True
        return None

    _FONT_CACHE[font_size] = font
    return font


def clear_promptfont_cache() -> None:
    _FONT_CACHE.clear()
    _GLYPH_SURFACE_CACHE.clear()


def _glyph(codepoint: int) -> str:
    return chr(codepoint)


_GENERIC_BUTTON_GLYPHS = {
    0: _glyph(8615),  # GAMEPAD_A (bottom face button)
    1: _glyph(8614),  # GAMEPAD_B (right face button)
    2: _glyph(8612),  # GAMEPAD_X (left face button)
    3: _glyph(8613),  # GAMEPAD_Y (top face button)
    6: _glyph(8696),  # GAMEPAD_START
    7: _glyph(8634),  # ANALOG_L_CLICK
    8: _glyph(8635),  # ANALOG_R_CLICK
    11: _glyph(8607), # DPAD_UP
    12: _glyph(8609), # DPAD_DOWN
    13: _glyph(8606), # DPAD_LEFT
    14: _glyph(8608), # DPAD_RIGHT
}

_XBOX_BUTTON_GLYPHS = {
    0: _glyph(8659),  # XBOX_A
    1: _glyph(8658),  # XBOX_B
    2: _glyph(8656),  # XBOX_X
    3: _glyph(8657),  # XBOX_Y
    6: _glyph(8699),  # XBOX_MENU
    7: _glyph(8634),  # ANALOG_L_CLICK
    8: _glyph(8635),  # ANALOG_R_CLICK
    9: _glyph(8600),  # XBOX_LEFT_SHOULDER
    10: _glyph(8601), # XBOX_RIGHT_SHOULDER
    11: _glyph(8827), # XBOX_DPAD_UP
    12: _glyph(8829), # XBOX_DPAD_DOWN
    13: _glyph(8826), # XBOX_DPAD_LEFT
    14: _glyph(8828), # XBOX_DPAD_RIGHT
}

_PLAYSTATION_BUTTON_GLYPHS = {
    0: _glyph(8675),  # SONY_A / Cross
    1: _glyph(8674),  # SONY_B / Circle
    2: _glyph(8672),  # SONY_X / Square
    3: _glyph(8673),  # SONY_Y / Triangle
    6: _glyph(8680),  # SONY_OPTIONS
    7: _glyph(8634),  # ANALOG_L_CLICK
    8: _glyph(8635),  # ANALOG_R_CLICK
    9: _glyph(8624),  # SONY_LEFT_SHOULDER
    10: _glyph(8625), # SONY_RIGHT_SHOULDER
    11: _glyph(8607), # DPAD_UP
    12: _glyph(8609), # DPAD_DOWN
    13: _glyph(8606), # DPAD_LEFT
    14: _glyph(8608), # DPAD_RIGHT
}

_NINTENDO_BUTTON_GLYPHS = {
    0: _glyph(8615),  # generic bottom face button (B on Nintendo)
    1: _glyph(8614),  # generic right face button (A on Nintendo)
    2: _glyph(8612),  # generic left face button (Y on Nintendo)
    3: _glyph(8613),  # generic top face button (X on Nintendo)
    6: _glyph(8702),  # NINTENDO_PLUS
    7: _glyph(8634),  # ANALOG_L_CLICK
    8: _glyph(8635),  # ANALOG_R_CLICK
    9: _glyph(8604),  # NINTENDO_LEFT_SHOULDER
    10: _glyph(8605), # NINTENDO_RIGHT_SHOULDER
    11: _glyph(8704), # NINTENDO_DPAD_UP
    12: _glyph(8706), # NINTENDO_DPAD_DOWN
    13: _glyph(8703), # NINTENDO_DPAD_LEFT
    14: _glyph(8705), # NINTENDO_DPAD_RIGHT
}

_XBOX_TRIGGER_GLYPHS = {
    100: _glyph(8598),
    101: _glyph(8599),
}

_PLAYSTATION_TRIGGER_GLYPHS = {
    100: _glyph(8626),
    101: _glyph(8627),
}

_NINTENDO_TRIGGER_GLYPHS = {
    100: _glyph(8602),
    101: _glyph(8603),
}

_UNKNOWN_TRIGGER_GLYPHS = {
    100: _glyph(8598),
    101: _glyph(8599),
}


def get_gamepad_prompt_glyph(btn_index: int, gp_type: str | None = None) -> Optional[str]:
    try:
        button_index = int(btn_index)
    except Exception:
        return None

    if button_index < 0:
        return None

    resolved_type = gp_type or GamepadType.UNKNOWN

    if button_index in (100, 101):
        trigger_maps = {
            GamepadType.XBOX: _XBOX_TRIGGER_GLYPHS,
            GamepadType.PLAYSTATION: _PLAYSTATION_TRIGGER_GLYPHS,
            GamepadType.NINTENDO: _NINTENDO_TRIGGER_GLYPHS,
            GamepadType.UNKNOWN: _UNKNOWN_TRIGGER_GLYPHS,
        }
        mapping = trigger_maps.get(resolved_type, _UNKNOWN_TRIGGER_GLYPHS)
        return mapping.get(button_index)

    button_maps = {
        GamepadType.XBOX: _XBOX_BUTTON_GLYPHS,
        GamepadType.PLAYSTATION: _PLAYSTATION_BUTTON_GLYPHS,
        GamepadType.NINTENDO: _NINTENDO_BUTTON_GLYPHS,
        GamepadType.UNKNOWN: _GENERIC_BUTTON_GLYPHS,
    }
    mapping = button_maps.get(resolved_type, _GENERIC_BUTTON_GLYPHS)
    return mapping.get(button_index)


def render_promptfont_glyph(
    glyph_text: str,
    size: int,
    color,
) -> Optional[pygame.Surface]:
    if not glyph_text:
        return None

    font = get_promptfont(size)
    if font is None:
        return None

    try:
        color_key = tuple(int(channel) for channel in tuple(color)[:3])
    except Exception:
        color_key = (255, 255, 255)

    key = (str(glyph_text), int(size), color_key)
    cached = _GLYPH_SURFACE_CACHE.get(key)
    if cached is not None:
        return cached

    try:
        rendered = font.render(str(glyph_text), True, color_key)
    except Exception:
        return None

    _GLYPH_SURFACE_CACHE[key] = rendered
    return rendered


def fit_promptfont_glyph_surface(
    glyph_text: str,
    max_width: int,
    max_height: int,
    color,
    preferred_size: int,
    minimum_size: int = 10,
) -> Optional[pygame.Surface]:
    try:
        target_w = max(1, int(max_width))
        target_h = max(1, int(max_height))
        start_size = max(1, int(preferred_size))
        min_size = max(1, int(minimum_size))
    except Exception:
        return None

    if min_size > start_size:
        min_size = start_size

    for font_size in range(start_size, min_size - 1, -1):
        surf = render_promptfont_glyph(glyph_text, font_size, color)
        if surf is None:
            continue
        if surf.get_width() <= target_w and surf.get_height() <= target_h:
            return surf

    surf = render_promptfont_glyph(glyph_text, min_size, color)
    if surf is None:
        return None
    if surf.get_width() <= target_w and surf.get_height() <= target_h:
        return surf
    return None