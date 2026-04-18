"""Mode-specific board skins and helper utilities for matching retro themes."""
from __future__ import annotations

from dataclasses import dataclass
import math
import random
from typing import Dict, Tuple
from constants import NEON_CYAN, NEON_MAGENTA, NEON_ORANGE, NEON_LIME, NEON_BLUE, RED
from localization import t

import pygame

Color = Tuple[int, int, int]
ColorA = Tuple[int, int, int, int]


def _tint(color: Color, alpha: int) -> ColorA:
    return (color[0], color[1], color[2], alpha)


# Oyun Modları kartlarıyla aynı ana vurgu renkleri
MODE_ACCENTS: Dict[str, Color] = {
    "sprint": (255, 215, 0),          # NEON_GOLD
    "ultra": RED,                     # NEON_RED
    "zen": (0, 255, 150),             # NEON_GREEN
    "tetris2": NEON_MAGENTA,
    "wide": NEON_CYAN,
    "survival": (255, 34, 118),       # RED->MAGENTA lerp(0.32)
    "cascade": (56, 78, 129),         # NEON_BLUE->BG_DARK lerp(0.55)
}


@dataclass(frozen=True)
class ModeSkin:
    """Declarative skin definition for a gameplay mode."""

    key: str
    title: str
    subtitle: str | None
    outer_bg: Color
    outer_tint: ColorA
    board_tint: ColorA
    grid_color: Color
    text_color: Color
    accent: Color
    panel_bg: ColorA
    panel_border: Color
    board_border: Color
    overlay: str
    overlay_colors: Tuple[ColorA, ...] = ((255, 255, 255, 35),)
    overlay_alpha: int = 60
    badge_icon: str | None = None


def _skin(
    key: str,
    *,
    title: str,
    subtitle: str | None,
    outer_bg: Color,
    outer_tint: ColorA,
    board_tint: ColorA,
    grid_color: Color,
    text_color: Color,
    accent: Color,
    panel_bg: ColorA,
    panel_border: Color,
    board_border: Color,
    overlay: str,
    overlay_colors: Tuple[ColorA, ...] = ((255, 255, 255, 35),),
    overlay_alpha: int = 60,
    badge_icon: str | None = None,
) -> ModeSkin:
    return ModeSkin(
        key,
        title,
        subtitle,
        outer_bg,
        outer_tint,
        board_tint,
        grid_color,
        text_color,
        accent,
        panel_bg,
        panel_border,
        board_border,
        overlay,
        overlay_colors,
        overlay_alpha,
        badge_icon,
    )


_SKINS: Dict[str, ModeSkin] = {
    "classic": _skin(
        "classic",
        title=t('skin_classic_title'),
        subtitle=t('skin_classic_subtitle'),
        outer_bg=(4, 6, 16),
        outer_tint=(12, 8, 26, 80),
        board_tint=(12, 20, 60, 90),
        grid_color=(42, 78, 128),
        text_color=(218, 232, 255),
        accent=NEON_CYAN,
        panel_bg=(8, 10, 26, 230),
        panel_border=NEON_CYAN,
        board_border=NEON_CYAN,
        overlay="none",
        overlay_alpha=0,
    ),
    "tutorial": _skin(
        "tutorial",
        title=t('skin_tutorial_title'),
        subtitle=t('skin_tutorial_subtitle'),
        outer_bg=(4, 6, 16),
        outer_tint=(12, 8, 26, 80),
        board_tint=(12, 20, 60, 90),
        grid_color=(42, 78, 128),
        text_color=(218, 232, 255),
        accent=NEON_CYAN,
        panel_bg=(8, 10, 26, 230),
        panel_border=NEON_CYAN,
        board_border=NEON_CYAN,
        overlay="none",
        overlay_alpha=0,
    ),
    "sprint": _skin(
        "sprint",
        title=t('skin_sprint_title'),
        subtitle=t('skin_sprint_subtitle'),
        outer_bg=(8, 6, 20),
        outer_tint=_tint(MODE_ACCENTS["sprint"], 45),
        board_tint=_tint(MODE_ACCENTS["sprint"], 55),
        grid_color=(120, 110, 70),
        text_color=(245, 226, 210),
        accent=MODE_ACCENTS["sprint"],
        panel_bg=(30, 12, 6, 230),
        panel_border=MODE_ACCENTS["sprint"],
        board_border=MODE_ACCENTS["sprint"],
        overlay="none",
        overlay_alpha=0,
    ),
    "ultra": _skin(
        "ultra",
        title=t('skin_ultra_title'),
        subtitle=t('skin_ultra_subtitle'),
        outer_bg=(6, 6, 18),
        outer_tint=_tint(MODE_ACCENTS["ultra"], 45),
        board_tint=_tint(MODE_ACCENTS["ultra"], 55),
        grid_color=(120, 90, 120),
        text_color=(225, 230, 255),
        accent=MODE_ACCENTS["ultra"],
        panel_bg=(12, 16, 40, 230),
        panel_border=MODE_ACCENTS["ultra"],
        board_border=MODE_ACCENTS["ultra"],
        overlay="none",
        overlay_alpha=0,
    ),
    "zen": _skin(
        "zen",
        title=t('skin_zen_title'),
        subtitle=t('skin_zen_subtitle'),
        outer_bg=(2, 8, 12),
        outer_tint=_tint(MODE_ACCENTS["zen"], 40),
        board_tint=_tint(MODE_ACCENTS["zen"], 52),
        grid_color=(70, 120, 105),
        text_color=(220, 245, 242),
        accent=MODE_ACCENTS["zen"],
        panel_bg=(6, 30, 28, 230),
        panel_border=MODE_ACCENTS["zen"],
        board_border=MODE_ACCENTS["zen"],
        overlay="none",
        overlay_alpha=0,
    ),
    "tetris2": _skin(
        "tetris2",
        title=t('skin_tetris2_title'),
        subtitle=t('skin_tetris2_subtitle'),
        outer_bg=(8, 4, 12),
        outer_tint=(60, 10, 80, 60),
        board_tint=(50, 10, 70, 80),
        grid_color=(200, 150, 255),
        text_color=(240, 225, 255),
        accent=MODE_ACCENTS["tetris2"],
        panel_bg=(28, 12, 34, 230),
        panel_border=MODE_ACCENTS["tetris2"],
        board_border=MODE_ACCENTS["tetris2"],
        overlay="none",
        overlay_alpha=0,
    ),
    "mystery": _skin(
        "mystery",
        title=t('skin_mystery_title'),
        subtitle=t('skin_mystery_subtitle'),
        outer_bg=(6, 4, 10),
        outer_tint=(80, 20, 80, 70),
        board_tint=(30, 6, 40, 90),
        grid_color=(220, 160, 255),
        text_color=(240, 220, 255),
        accent=NEON_MAGENTA,
        panel_bg=(24, 10, 30, 230),
        panel_border=NEON_MAGENTA,
        board_border=NEON_MAGENTA,
        overlay="none",
        overlay_alpha=0,
    ),
    "wide": _skin(
        "wide",
        title=t('skin_wide_title'),
        subtitle=t('skin_wide_subtitle'),
        outer_bg=(4, 6, 10),
        outer_tint=(10, 40, 80, 70),
        board_tint=(12, 24, 50, 70),
        grid_color=(120, 200, 255),
        text_color=(215, 230, 250),
        accent=MODE_ACCENTS["wide"],
        panel_bg=(14, 22, 40, 230),
        panel_border=MODE_ACCENTS["wide"],
        board_border=MODE_ACCENTS["wide"],
        overlay="none",
        overlay_alpha=0,
    ),
    "survival": _skin(
        "survival",
        title=t('skin_survival_title'),
        subtitle=t('skin_survival_subtitle'),
        outer_bg=(8, 4, 6),
        outer_tint=(80, 20, 20, 80),
        board_tint=(50, 8, 8, 90),
        grid_color=(255, 120, 120),
        text_color=(255, 230, 220),
        accent=MODE_ACCENTS["survival"],
        panel_bg=(40, 10, 12, 230),
        panel_border=MODE_ACCENTS["survival"],
        board_border=MODE_ACCENTS["survival"],
        overlay="none",
        overlay_alpha=0,
    ),
    "cascade": _skin(
        "cascade",
        title=t('skin_cascade_title'),
        subtitle=t('skin_cascade_subtitle'),
        outer_bg=(4, 8, 14),
        outer_tint=(10, 30, 80, 70),
        board_tint=(8, 24, 60, 80),
        grid_color=(120, 200, 255),
        text_color=(220, 235, 255),
        accent=MODE_ACCENTS["cascade"],
        panel_bg=(12, 20, 50, 230),
        panel_border=MODE_ACCENTS["cascade"],
        board_border=MODE_ACCENTS["cascade"],
        overlay="none",
        overlay_alpha=0,
    ),
    "daily": _skin(
        "daily",
        title=t('skin_daily_title'),
        subtitle=t('skin_daily_subtitle'),
        outer_bg=(6, 6, 14),
        outer_tint=(40, 30, 80, 70),
        board_tint=(30, 24, 60, 80),
        grid_color=(220, 190, 120),
        text_color=(235, 225, 210),
        accent=NEON_ORANGE,
        panel_bg=(30, 20, 40, 230),
        panel_border=NEON_ORANGE,
        board_border=NEON_ORANGE,
        overlay="none",
        overlay_alpha=0,
    ),
    "pvp": _skin(
        "pvp",
        title=t('skin_pvp_title'),
        subtitle=t('skin_pvp_subtitle'),
        outer_bg=(6, 4, 14),
        outer_tint=(34, 26, 60, 42),
        board_tint=(24, 24, 46, 62),
        grid_color=(152, 138, 212),
        text_color=(230, 220, 255),
        accent=NEON_MAGENTA,
        panel_bg=(24, 18, 40, 230),
        panel_border=NEON_MAGENTA,
        board_border=NEON_MAGENTA,
        overlay="versus",
        overlay_colors=((196, 150, 205, 72), (132, 176, 220, 66)),
        overlay_alpha=82,
    ),
    "hardcore": _skin(
        "hardcore",
        title="HARDCORE",
        subtitle="Gercek zorluk",
        outer_bg=(10, 4, 4),
        outer_tint=(80, 20, 20, 80),
        board_tint=(60, 10, 10, 90),
        grid_color=(180, 80, 80),
        text_color=(255, 220, 220),
        accent=(255, 50, 50),
        panel_bg=(40, 10, 10, 230),
        panel_border=(255, 50, 50),
        board_border=(255, 50, 50),
        overlay="none",
        overlay_alpha=0,
    ),
}

_ALIASES = {
    "classic": "classic",
    "retro": "classic",
    "single": "classic",
    "tutorial": "tutorial",
    "sprint mode": "sprint",
    "ultra mode": "ultra",
    "zen mode": "zen",
    "mystery mode": "mystery",
    "kart ustalığı": "mystery",
    "card mastery": "mystery",
    "tetris 2": "tetris2",
    "tetris extra": "tetris2",
    "wide mode": "wide",
    "survival mode": "survival",
    "cascade mode": "cascade",
    "daily challenge": "daily",
    "hardcore mode": "hardcore",
}


def get_mode_skin(mode: str | None) -> ModeSkin:
    """Return the visual skin for a mode (defaults to classic)."""
    if not mode:
        return _SKINS["classic"]
    key = mode.lower().strip()
    key = _ALIASES.get(key, key)
    return _SKINS.get(key, _SKINS["classic"])


def get_localized_skin_title(skin: ModeSkin) -> str:
    """Skin başlığını yerelleştirilmiş olarak döndürür."""
    key = f"skin_{skin.key}_title"
    translated = t(key)
    return translated if translated != key else skin.title


def get_localized_skin_subtitle(skin: ModeSkin) -> str:
    """Skin alt başlığını yerelleştirilmiş olarak döndürür."""
    if not skin.subtitle:
        return ""
    key = f"skin_{skin.key}_subtitle"
    translated = t(key)
    return translated if translated != key else skin.subtitle


def apply_outer_tint(screen: pygame.Surface, skin: ModeSkin, rect: pygame.Rect | tuple[int, int, int, int] | None = None) -> None:
    """Overlay a subtle color tint on top of whatever background is active."""
    if skin.outer_tint[-1] <= 0:
        return
    # Cache to avoid per-frame surface allocation.
    global _OUTER_TINT_CACHE
    try:
        _OUTER_TINT_CACHE
    except NameError:
        _OUTER_TINT_CACHE = {}
    key = (screen.get_size(), tuple(skin.outer_tint))
    overlay = _OUTER_TINT_CACHE.get(key)
    if overlay is None:
        overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        overlay.fill(skin.outer_tint)
        _OUTER_TINT_CACHE[key] = overlay
    if rect is None:
        screen.blit(overlay, (0, 0))
        return

    area = pygame.Rect(rect)
    if area.width <= 0 or area.height <= 0:
        return
    screen.blit(overlay, area.topleft, area)


def apply_board_tint(screen: pygame.Surface, rect: pygame.Rect, skin: ModeSkin) -> None:
    if skin.board_tint[-1] <= 0:
        return
    # Cache to avoid per-frame surface allocation.
    global _BOARD_TINT_CACHE
    try:
        _BOARD_TINT_CACHE
    except NameError:
        _BOARD_TINT_CACHE = {}
    key = (rect.size, tuple(skin.board_tint))
    overlay = _BOARD_TINT_CACHE.get(key)
    if overlay is None:
        overlay = pygame.Surface(rect.size, pygame.SRCALPHA).convert_alpha()
        overlay.fill(skin.board_tint)
        _BOARD_TINT_CACHE[key] = overlay
    # Default blit respects per-pixel alpha on most platforms; avoid PREMULTIPLIED which
    # behaves inconsistently on some macOS SDL builds and can cause visual artifacts.
    screen.blit(overlay, rect.topleft)


def draw_board_overlay(screen: pygame.Surface, rect: pygame.Rect, skin: ModeSkin) -> None:
    """Draw the decorative overlay for the board area based on the skin."""
    if skin.overlay == "none" or skin.overlay_alpha <= 0:
        return
    # Cache to avoid per-frame surface allocation + pattern rerender.
    global _BOARD_OVERLAY_CACHE
    try:
        _BOARD_OVERLAY_CACHE
    except NameError:
        _BOARD_OVERLAY_CACHE = {}
    key = (rect.size, str(skin.overlay), tuple(tuple(c) for c in skin.overlay_colors), int(skin.overlay_alpha))
    overlay = _BOARD_OVERLAY_CACHE.get(key)
    if overlay is None:
        overlay = pygame.Surface(rect.size, pygame.SRCALPHA).convert_alpha()
        renderer = _PATTERN_RENDERERS.get(skin.overlay, _render_scan)
        renderer(overlay, skin.overlay_colors)
        overlay.set_alpha(skin.overlay_alpha)
        _BOARD_OVERLAY_CACHE[key] = overlay
    # Use a normal blit for safe alpha blending; BLEND_PREMULTIPLIED can yield incorrect
    # results if the surface isn't premultiplied, which happens on some macOS systems.
    screen.blit(overlay, rect.topleft)


# ---------------------------------------------------------------------------
# Pattern renderers
# ---------------------------------------------------------------------------

def _render_scan(surface: pygame.Surface, colors: Tuple[ColorA, ...]) -> None:
    width, height = surface.get_size()
    for y in range(0, height, 6):
        color = colors[y // 6 % len(colors)]
        pygame.draw.rect(surface, color, (0, y, width, 2))


def _render_minimal(surface: pygame.Surface, colors: Tuple[ColorA, ...]) -> None:
    width, height = surface.get_size()
    border_color = colors[0]
    pygame.draw.rect(surface, border_color, (6, 6, width - 12, height - 12), 2, border_radius=12)
    accent = colors[min(1, len(colors) - 1)]
    for fraction in (0.33, 0.66):
        y = int(height * fraction)
        pygame.draw.line(surface, accent, (18, y), (width - 18, y), 1)
    for x in (24, width - 24):
        pygame.draw.line(surface, accent, (x, 18), (x, height - 18), 1)


def _render_speed(surface: pygame.Surface, colors: Tuple[ColorA, ...]) -> None:
    width, height = surface.get_size()
    step = 24
    for i in range(-height, width, step):
        color = colors[(i // step) % len(colors)]
        pygame.draw.line(surface, color, (i, 0), (i + height, height), 4)


def _render_pulse(surface: pygame.Surface, colors: Tuple[ColorA, ...]) -> None:
    width, height = surface.get_size()
    center = (width // 2, height // 2)
    max_radius = int(math.hypot(width, height))
    for idx, radius in enumerate(range(20, max_radius, 40)):
        color = colors[idx % len(colors)]
        pygame.draw.circle(surface, color, center, radius, 3)


def _render_waves(surface: pygame.Surface, colors: Tuple[ColorA, ...]) -> None:
    width, height = surface.get_size()
    for idx, color in enumerate(colors):
        points = []
        amplitude = 12 + idx * 6
        frequency = 0.02 + idx * 0.01
        offset_y = (idx + 1) * (height // (len(colors) + 1))
        for x in range(width):
            y = int(offset_y + math.sin(x * frequency) * amplitude)
            points.append((x, y))
        if len(points) > 1:
            pygame.draw.aalines(surface, color, False, points)


def _render_tiles(surface: pygame.Surface, colors: Tuple[ColorA, ...]) -> None:
    width, height = surface.get_size()
    tile = 40
    color_count = len(colors)
    for y in range(0, height, tile):
        for x in range(0, width, tile):
            color = colors[((x // tile) + (y // tile)) % color_count]
            pygame.draw.rect(surface, color, (x, y, tile - 6, tile - 6), 2, border_radius=6)


def _render_glitch(surface: pygame.Surface, colors: Tuple[ColorA, ...]) -> None:
    width, height = surface.get_size()
    random.seed(42)
    for _ in range(60):
        w = random.randint(20, 80)
        h = random.randint(4, 20)
        x = random.randint(0, max(0, width - w))
        y = random.randint(0, max(0, height - h))
        color = random.choice(colors)
        pygame.draw.rect(surface, color, (x, y, w, h))


def _render_h_stripes(surface: pygame.Surface, colors: Tuple[ColorA, ...]) -> None:
    width, height = surface.get_size()
    stripe = max(12, height // 20)
    for i in range(0, height, stripe):
        color = colors[(i // stripe) % len(colors)]
        pygame.draw.rect(surface, color, (0, i, width, stripe // 2))


def _render_warning(surface: pygame.Surface, colors: Tuple[ColorA, ...]) -> None:
    width, height = surface.get_size()
    stripe_height = 28
    for y in range(0, height + stripe_height, stripe_height):
        color = colors[(y // stripe_height) % len(colors)]
        points = [
            (0, y),
            (width, y - stripe_height // 2),
            (width, y),
            (0, y + stripe_height // 2),
        ]
        pygame.draw.polygon(surface, color, points)


def _render_constellation(surface: pygame.Surface, colors: Tuple[ColorA, ...]) -> None:
    width, height = surface.get_size()
    random.seed(7)
    stars = []
    for _ in range(25):
        x = random.randint(0, width)
        y = random.randint(0, height)
        stars.append((x, y))
        color = random.choice(colors)
        pygame.draw.circle(surface, color, (x, y), 2)
    for i in range(0, len(stars), 2):
        color = colors[i % len(colors)]
        pygame.draw.line(surface, color, stars[i], stars[(i + 1) % len(stars)], 1)


def _render_versus(surface: pygame.Surface, colors: Tuple[ColorA, ...]) -> None:
    width, height = surface.get_size()
    center = width // 2
    pygame.draw.rect(surface, colors[0], (center - 4, 0, 8, height))
    for idx, color in enumerate(colors):
        pygame.draw.circle(surface, color, (center, height // 2), 90 - idx * 20, 3)


_PATTERN_RENDERERS = {
    "scan": _render_scan,
    "minimal": _render_minimal,
    "speed": _render_speed,
    "pulse": _render_pulse,
    "waves": _render_waves,
    "tiles": _render_tiles,
    "glitch": _render_glitch,
    "h_stripes": _render_h_stripes,
    "warning": _render_warning,
    "constellation": _render_constellation,
    "versus": _render_versus,
}
