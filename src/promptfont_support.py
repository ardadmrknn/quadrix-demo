from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Optional

import pygame

from gamepad_manager import GamepadType, get_gamepad_manager


_FONT_CACHE: dict[int, pygame.font.Font] = {}
_GLYPH_SURFACE_CACHE: dict[tuple[str, int, tuple[int, int, int]], pygame.Surface] = {}
_FONT_LOAD_FAILED = False
_PROMPTFONT_SYMBOLS: dict[str, str] | None = None
_PROMPTFONT_SYMBOLS_ATTEMPTED = False


def _get_base_dir() -> Path:
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent


def _get_promptfont_path() -> Path:
    return _get_base_dir() / 'assets' / 'gamepad_icon' / 'promptfont' / 'promptfont.ttf'


def _get_promptfont_module_path() -> Path:
    return _get_base_dir() / 'assets' / 'gamepad_icon' / 'promptfont' / 'promptfont.py'


def _load_promptfont_symbols() -> dict[str, str]:
    global _PROMPTFONT_SYMBOLS, _PROMPTFONT_SYMBOLS_ATTEMPTED

    if _PROMPTFONT_SYMBOLS is not None:
        return _PROMPTFONT_SYMBOLS
    if _PROMPTFONT_SYMBOLS_ATTEMPTED:
        return {}

    _PROMPTFONT_SYMBOLS_ATTEMPTED = True
    module_path = _get_promptfont_module_path()
    if not module_path.exists():
        _PROMPTFONT_SYMBOLS = {}
        return _PROMPTFONT_SYMBOLS

    try:
        spec = importlib.util.spec_from_file_location('promptfont_symbols', module_path)
        if spec is None or spec.loader is None:
            raise RuntimeError('promptfont spec unavailable')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    except Exception:
        _PROMPTFONT_SYMBOLS = {}
        return _PROMPTFONT_SYMBOLS

    symbol_names = (
        'GAMEPAD_A', 'GAMEPAD_B', 'GAMEPAD_X', 'GAMEPAD_Y', 'GAMEPAD_START',
        'ANALOG_L_CLICK', 'ANALOG_R_CLICK', 'DPAD_UP', 'DPAD_DOWN', 'DPAD_LEFT', 'DPAD_RIGHT',
        'XBOX_A', 'XBOX_B', 'XBOX_X', 'XBOX_Y', 'XBOX_MENU',
        'XBOX_LEFT_SHOULDER', 'XBOX_RIGHT_SHOULDER', 'XBOX_DPAD_UP', 'XBOX_DPAD_DOWN', 'XBOX_DPAD_LEFT', 'XBOX_DPAD_RIGHT',
        'SONY_A', 'SONY_B', 'SONY_X', 'SONY_Y', 'SONY_OPTIONS',
        'SONY_LEFT_SHOULDER', 'SONY_RIGHT_SHOULDER', 'SONY_LEFT_TRIGGER', 'SONY_RIGHT_TRIGGER',
        'NINTENDO_PLUS', 'NINTENDO_LEFT_SHOULDER', 'NINTENDO_RIGHT_SHOULDER',
        'NINTENDO_DPAD_UP', 'NINTENDO_DPAD_DOWN', 'NINTENDO_DPAD_LEFT', 'NINTENDO_DPAD_RIGHT',
        'NINTENDO_LEFT_TRIGGER', 'NINTENDO_RIGHT_TRIGGER',
        'XBOX_LEFT_TRIGGER', 'XBOX_RIGHT_TRIGGER',
    )
    _PROMPTFONT_SYMBOLS = {
        name: str(getattr(module, name))
        for name in symbol_names
        if hasattr(module, name)
    }
    return _PROMPTFONT_SYMBOLS


def _prompt_symbol(name: str, fallback_codepoint: int) -> str:
    symbols = _load_promptfont_symbols()
    return str(symbols.get(name) or chr(fallback_codepoint))


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


def _button_glyph_maps() -> dict[str, dict[int, str]]:
    return {
        GamepadType.UNKNOWN: {
            0: _prompt_symbol('GAMEPAD_A', 8615),
            1: _prompt_symbol('GAMEPAD_B', 8614),
            2: _prompt_symbol('GAMEPAD_X', 8612),
            3: _prompt_symbol('GAMEPAD_Y', 8613),
            6: _prompt_symbol('GAMEPAD_START', 8696),
            7: _prompt_symbol('ANALOG_L_CLICK', 8634),
            8: _prompt_symbol('ANALOG_R_CLICK', 8635),
            11: _prompt_symbol('DPAD_UP', 8607),
            12: _prompt_symbol('DPAD_DOWN', 8609),
            13: _prompt_symbol('DPAD_LEFT', 8606),
            14: _prompt_symbol('DPAD_RIGHT', 8608),
        },
        GamepadType.XBOX: {
            0: _prompt_symbol('XBOX_A', 8659),
            1: _prompt_symbol('XBOX_B', 8658),
            2: _prompt_symbol('XBOX_X', 8656),
            3: _prompt_symbol('XBOX_Y', 8657),
            6: _prompt_symbol('XBOX_MENU', 8699),
            7: _prompt_symbol('ANALOG_L_CLICK', 8634),
            8: _prompt_symbol('ANALOG_R_CLICK', 8635),
            9: _prompt_symbol('XBOX_LEFT_SHOULDER', 8600),
            10: _prompt_symbol('XBOX_RIGHT_SHOULDER', 8601),
            11: _prompt_symbol('XBOX_DPAD_UP', 8827),
            12: _prompt_symbol('XBOX_DPAD_DOWN', 8829),
            13: _prompt_symbol('XBOX_DPAD_LEFT', 8826),
            14: _prompt_symbol('XBOX_DPAD_RIGHT', 8828),
        },
        GamepadType.PLAYSTATION: {
            0: _prompt_symbol('SONY_A', 8675),
            1: _prompt_symbol('SONY_B', 8674),
            2: _prompt_symbol('SONY_X', 8672),
            3: _prompt_symbol('SONY_Y', 8673),
            6: _prompt_symbol('SONY_OPTIONS', 8680),
            7: _prompt_symbol('ANALOG_L_CLICK', 8634),
            8: _prompt_symbol('ANALOG_R_CLICK', 8635),
            9: _prompt_symbol('SONY_LEFT_SHOULDER', 8624),
            10: _prompt_symbol('SONY_RIGHT_SHOULDER', 8625),
            11: _prompt_symbol('DPAD_UP', 8607),
            12: _prompt_symbol('DPAD_DOWN', 8609),
            13: _prompt_symbol('DPAD_LEFT', 8606),
            14: _prompt_symbol('DPAD_RIGHT', 8608),
        },
        GamepadType.NINTENDO: {
            0: _prompt_symbol('GAMEPAD_A', 8615),
            1: _prompt_symbol('GAMEPAD_B', 8614),
            2: _prompt_symbol('GAMEPAD_X', 8612),
            3: _prompt_symbol('GAMEPAD_Y', 8613),
            6: _prompt_symbol('NINTENDO_PLUS', 8702),
            7: _prompt_symbol('ANALOG_L_CLICK', 8634),
            8: _prompt_symbol('ANALOG_R_CLICK', 8635),
            9: _prompt_symbol('NINTENDO_LEFT_SHOULDER', 8604),
            10: _prompt_symbol('NINTENDO_RIGHT_SHOULDER', 8605),
            11: _prompt_symbol('NINTENDO_DPAD_UP', 8704),
            12: _prompt_symbol('NINTENDO_DPAD_DOWN', 8706),
            13: _prompt_symbol('NINTENDO_DPAD_LEFT', 8703),
            14: _prompt_symbol('NINTENDO_DPAD_RIGHT', 8705),
        },
    }


def _trigger_glyph_maps() -> dict[str, dict[int, str]]:
    return {
        GamepadType.UNKNOWN: {
            100: _prompt_symbol('XBOX_LEFT_TRIGGER', 8598),
            101: _prompt_symbol('XBOX_RIGHT_TRIGGER', 8599),
        },
        GamepadType.XBOX: {
            100: _prompt_symbol('XBOX_LEFT_TRIGGER', 8598),
            101: _prompt_symbol('XBOX_RIGHT_TRIGGER', 8599),
        },
        GamepadType.PLAYSTATION: {
            100: _prompt_symbol('SONY_LEFT_TRIGGER', 8626),
            101: _prompt_symbol('SONY_RIGHT_TRIGGER', 8627),
        },
        GamepadType.NINTENDO: {
            100: _prompt_symbol('NINTENDO_LEFT_TRIGGER', 8602),
            101: _prompt_symbol('NINTENDO_RIGHT_TRIGGER', 8603),
        },
    }


def get_active_gamepad_prompt_type(gpm=None) -> str | None:
    try:
        manager = gpm or get_gamepad_manager()
        gp = manager.get_active_gamepad()
        gp_type = getattr(gp, 'gamepad_type', None)
        return str(gp_type) if gp_type else GamepadType.UNKNOWN
    except Exception:
        return None


def _is_connected_for_prompt(gpm=None) -> bool:
    try:
        manager = gpm or get_gamepad_manager()
        return bool(getattr(manager, 'enabled', False) and manager.is_connected())
    except Exception:
        return False


def get_gamepad_prompt_glyph(btn_index: int, gp_type: str | None = None) -> Optional[str]:
    try:
        button_index = int(btn_index)
    except Exception:
        return None

    if button_index < 0:
        return None

    resolved_type = gp_type or GamepadType.UNKNOWN
    if button_index in (100, 101):
        return _trigger_glyph_maps().get(resolved_type, _trigger_glyph_maps()[GamepadType.UNKNOWN]).get(button_index)
    return _button_glyph_maps().get(resolved_type, _button_glyph_maps()[GamepadType.UNKNOWN]).get(button_index)


def get_button_index_prompt_display(
    btn_index: int,
    fallback_text: str = '',
    *,
    gp_type: str | None = None,
    gpm=None,
    connected_only: bool = True,
) -> dict[str, object | None]:
    text = str(fallback_text or '')
    manager = gpm
    if manager is None:
        try:
            manager = get_gamepad_manager()
        except Exception:
            manager = None

    connected = _is_connected_for_prompt(manager)
    if connected_only and not connected:
        return {'mode': 'text', 'glyph': None, 'text': text}

    resolved_type = gp_type or get_active_gamepad_prompt_type(manager) or GamepadType.UNKNOWN
    try:
        button_index = int(btn_index)
    except Exception:
        return {'mode': 'text', 'glyph': None, 'text': text}

    if manager is not None:
        try:
            label = manager.get_button_index_label(button_index, resolved_type)
            if label and label != '?':
                text = str(label)
        except Exception:
            pass

    glyph = get_gamepad_prompt_glyph(button_index, resolved_type)
    if glyph:
        return {'mode': 'glyph', 'glyph': glyph, 'text': text}
    return {'mode': 'text', 'glyph': None, 'text': text}


def get_action_prompt_display(
    action: str,
    keyboard_label: str,
    *,
    gp_type: str | None = None,
    gpm=None,
) -> dict[str, object | None]:
    text = str(keyboard_label or '')
    manager = gpm
    if manager is None:
        try:
            manager = get_gamepad_manager()
        except Exception:
            manager = None

    if not _is_connected_for_prompt(manager):
        return {'mode': 'text', 'glyph': None, 'text': text}

    resolved_type = gp_type or get_active_gamepad_prompt_type(manager) or GamepadType.UNKNOWN
    if manager is not None:
        try:
            label = manager.get_button_label(action, resolved_type)
            if label and label != '?':
                text = str(label)
        except Exception:
            pass

    button_indices: list[int] = []
    if manager is not None and hasattr(manager, 'get_action_button_indices'):
        try:
            button_indices = list(manager.get_action_button_indices(action))
        except Exception:
            button_indices = []

    if button_indices:
        glyph = get_gamepad_prompt_glyph(button_indices[0], resolved_type)
        if glyph:
            return {'mode': 'glyph', 'glyph': glyph, 'text': text}

    return {'mode': 'text', 'glyph': None, 'text': text}


def render_promptfont_glyph(glyph_text: str, size: int, color) -> Optional[pygame.Surface]:
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


def render_prompt_display_surface(
    display: dict[str, object | None],
    font: pygame.font.Font,
    color,
    *,
    max_width: int | None = None,
    max_height: int | None = None,
) -> Optional[pygame.Surface]:
    if not isinstance(display, dict):
        return None

    if display.get('mode') == 'glyph':
        glyph_text = str(display.get('glyph') or '')
        if glyph_text:
            target_w = max_width if max_width is not None else max(font.get_linesize(), font.size(str(display.get('text') or ''))[0] + 8)
            target_h = max_height if max_height is not None else max(font.get_linesize() + 4, font.get_height() + 2)
            preferred = max(font.get_linesize() + 2, font.get_height() + 2)
            surf = fit_promptfont_glyph_surface(
                glyph_text,
                target_w,
                target_h,
                color,
                preferred_size=preferred,
                minimum_size=max(10, preferred // 2),
            )
            if surf is not None:
                return surf

    text = str(display.get('text') or '')
    try:
        return font.render(text, True, color)
    except Exception:
        return None


def render_action_prompt_surface(
    action: str,
    keyboard_label: str,
    font: pygame.font.Font,
    color,
    *,
    max_width: int | None = None,
    max_height: int | None = None,
    gpm=None,
) -> Optional[pygame.Surface]:
    display = get_action_prompt_display(action, keyboard_label, gpm=gpm)
    return render_prompt_display_surface(display, font, color, max_width=max_width, max_height=max_height)


def render_button_index_prompt_surface(
    btn_index: int,
    fallback_text: str,
    font: pygame.font.Font,
    color,
    *,
    max_width: int | None = None,
    max_height: int | None = None,
    gpm=None,
) -> Optional[pygame.Surface]:
    display = get_button_index_prompt_display(btn_index, fallback_text, gpm=gpm)
    return render_prompt_display_surface(display, font, color, max_width=max_width, max_height=max_height)


def render_inline_action_text_surface(
    text: str,
    label_text: str,
    action: str,
    font: pygame.font.Font,
    color,
    *,
    gpm=None,
) -> pygame.Surface:
    try:
        fallback = font.render(str(text or ''), True, color)
    except Exception:
        fallback = pygame.Surface((1, max(1, font.get_linesize())), pygame.SRCALPHA)

    display = get_action_prompt_display(action, label_text, gpm=gpm)
    if display.get('mode') != 'glyph':
        return fallback

    source_text = str(text or '')
    display_text = str(display.get('text') or '')
    needle = str(label_text or '')
    if not needle or needle not in source_text:
        if display_text and display_text in source_text:
            needle = display_text
        else:
            return fallback

    glyph_surf = render_prompt_display_surface(
        display,
        font,
        color,
        max_width=max(font.size(needle)[0] + max(8, font.get_height() // 2), font.get_linesize()),
        max_height=max(font.get_linesize() + 4, font.get_height() + 2),
    )
    if glyph_surf is None:
        return fallback

    prefix, suffix = source_text.split(needle, 1)
    prefix_surf = font.render(prefix, True, color) if prefix else None
    suffix_surf = font.render(suffix, True, color) if suffix else None

    total_w = glyph_surf.get_width()
    total_h = glyph_surf.get_height()
    if prefix_surf is not None:
        total_w += prefix_surf.get_width()
        total_h = max(total_h, prefix_surf.get_height())
    if suffix_surf is not None:
        total_w += suffix_surf.get_width()
        total_h = max(total_h, suffix_surf.get_height())

    composed = pygame.Surface((max(1, total_w), max(1, total_h)), pygame.SRCALPHA)
    cursor_x = 0
    if prefix_surf is not None:
        composed.blit(prefix_surf, (cursor_x, (total_h - prefix_surf.get_height()) // 2))
        cursor_x += prefix_surf.get_width()
    composed.blit(glyph_surf, (cursor_x, (total_h - glyph_surf.get_height()) // 2))
    cursor_x += glyph_surf.get_width()
    if suffix_surf is not None:
        composed.blit(suffix_surf, (cursor_x, (total_h - suffix_surf.get_height()) // 2))
    return composed