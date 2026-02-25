"""Quadrix tema sistemi - 5 farklı görsel tema"""
import pygame
from constants import *

class Theme:
    """Tema sınıfı"""
    def __init__(self, name, bg_color, grid_color, text_color, accent_color, pieces_colors, ui_bg, ui_border):
        self.name = name
        self.bg_color = bg_color
        self.grid_color = grid_color
        self.text_color = text_color
        self.accent_color = accent_color
        self.pieces_colors = pieces_colors
        self.ui_bg = ui_bg
        self.ui_border = ui_border

# TEMA TANIMLARI

CLASSIC_THEME = Theme(
    name="Classic",
    bg_color=(10, 10, 15),
    grid_color=(45, 50, 70),
    text_color=WHITE,
    accent_color=(100, 200, 255),
    pieces_colors={
        'I': (0, 255, 255),      # Classic cyan
        'O': (255, 184, 28),     # Classic yellow/gold
        'T': (180, 88, 196),     # Violet
        'S': (0, 200, 80),       # Green
        'Z': (255, 64, 64),      # Red
        'J': (22, 110, 220),     # Blue
        'L': (255, 140, 0),      # Orange
        # Extra pieces (Quadrix 2)
        'Plus': (240, 120, 200), # Soft pink
        'Y': (0, 190, 200),      # Turquoise
        'Domino': (255, 180, 60),# Gold
        'BigSquare': (150, 110, 255)  # Soft purple
    },
    ui_bg=(35, 40, 60),
    ui_border=(80, 100, 140)
)

CYBERPUNK_THEME = Theme(
    name="Cyberpunk",
    # Neon magenta/cyan highlights on a deep indigo-black base
    bg_color=(6, 0, 18),
    grid_color=(34, 12, 54),
    text_color=(235, 245, 255),
    accent_color=(255, 70, 200),
    pieces_colors={
        'I': (0, 255, 240),      # Neon cyan
        'O': (255, 240, 70),     # Acid yellow
        'T': (255, 60, 210),     # Hot magenta
        'S': (0, 255, 150),      # Neon green
        'Z': (255, 70, 130),     # Neon pink-red
        'J': (70, 150, 255),     # Electric blue
        'L': (255, 135, 40),     # Neon orange
        # Extra pieces (Quadrix 2)
        'Plus': (200, 90, 255),  # Neon purple
        'Y': (0, 210, 255),      # Cyan-blue
        'Domino': (255, 170, 0), # Neon amber
        'BigSquare': (150, 80, 255)  # Violet
    },
    ui_bg=(16, 6, 34),
    ui_border=(0, 255, 240)
)

OCEAN_THEME = Theme(
    name="Ocean",
    bg_color=(5, 8, 15),
    grid_color=(20, 40, 70),
    text_color=(200, 240, 255),
    accent_color=(0, 200, 255),
    pieces_colors={
        'I': (0, 170, 220),      # Ocean cyan
        'O': (90, 210, 220),     # Soft cyan
        'T': (10, 120, 200),     # Deep blue
        'S': (30, 200, 160),     # Sea green
        'Z': (220, 110, 230),    # Coral purple
        'J': (10, 95, 170),      # Dark blue
        'L': (95, 170, 220),     # Sky blue
        # Extra pieces (Quadrix 2)
        'Plus': (90, 210, 255),  # Light sea
        'Y': (40, 150, 210),     # Deep sea
        'Domino': (120, 200, 255),# Pale blue
        'BigSquare': (110, 110, 255)  # Coral blue
    },
    ui_bg=(15, 30, 55),
    ui_border=(50, 120, 180)
)


def _make_piece_colors_unique(pieces_colors):
    """Aynı tema içinde parça renklerinin birebir tekrar etmesini engelle.

    Sadece tam eşleşen (r,g,b) tekrarlarını düzeltir; renk paletini minimum değiştirir.
    """
    def clamp(v):
        return max(0, min(255, int(v)))

    used = set()
    out = {}
    for name, col in (pieces_colors or {}).items():
        c = tuple(int(x) for x in col)
        if c not in used:
            out[name] = c
            used.add(c)
            continue

        # Deterministik, küçük kaydırmalarla benzersiz renk üret
        found = None
        for step in range(1, 40):
            cand = (
                clamp(c[0] + step * 7),
                clamp(c[1] + step * 11),
                clamp(c[2] + step * 13),
            )
            if cand not in used:
                found = cand
                break
        out[name] = found if found is not None else c
        used.add(out[name])
    return out

SUNSET_THEME = Theme(
    name="Sunset",
    bg_color=(10, 5, 12),
    grid_color=(60, 30, 70),
    text_color=(255, 230, 200),
    accent_color=(255, 150, 100),
    pieces_colors={
        'I': (255, 90, 150),     # Warm pink
        'O': (255, 190, 60),     # Gold
        'T': (255, 120, 190),    # Rose
        'S': (255, 200, 110),    # Peach
        'Z': (255, 100, 110),    # Deep rose
        'J': (200, 110, 255),    # Lavender
        'L': (255, 150, 90),     # Orange
        # Extra pieces (Quadrix 2)
        'Plus': (255, 140, 180), # Light pink
        'Y': (255, 160, 120),    # Peach
        'Domino': (255, 180, 80), # Gold orange
        'BigSquare': (220, 120, 255)  # Soft purple
    },
    ui_bg=(45, 25, 55),
    ui_border=(120, 70, 130)
)

FOREST_THEME = Theme(
    name="Forest",
    bg_color=(5, 10, 8),
    grid_color=(30, 60, 40),
    text_color=(220, 255, 230),
    accent_color=(100, 255, 150),
    pieces_colors={
        'I': (40, 190, 90),      # Forest green
        'O': (170, 215, 90),     # Light olive
        'T': (70, 150, 100),     # Deep forest
        'S': (140, 240, 100),    # Bright pistachio
        'Z': (90, 140, 70),      # Dark green
        'J': (110, 200, 140),    # Mint
        'L': (190, 220, 110),    # Lemon green
        # Extra pieces (Quadrix 2)
        'Plus': (100, 220, 130), # Light forest
        'Y': (70, 170, 100),     # Deep forest
        'Domino': (160, 230, 110),# Bright pistachio
        'BigSquare': (130, 200, 140)  # Mint
    },
    ui_bg=(25, 45, 35),
    ui_border=(70, 120, 90)
)

GALAXY_THEME = Theme(
    name="Galaxy",
    bg_color=(3, 2, 8),
    grid_color=(30, 20, 50),
    text_color=(230, 220, 255),
    accent_color=(200, 150, 255),
    pieces_colors={
        'I': (150, 100, 255),    # Galaxy violet
        'O': (255, 210, 120),    # Star gold
        'T': (200, 120, 255),    # Nebula
        'S': (100, 190, 255),    # Cosmic blue
        'Z': (255, 120, 200),    # Pink nebula
        'J': (110, 150, 255),    # Deep space
        'L': (255, 150, 110),    # Solar orange
        # Extra pieces (Quadrix 2)
        'Plus': (180, 120, 255), # Light galaxy
        'Y': (120, 110, 220),    # Dark nebula
        'Domino': (255, 180, 130),# Star glow
        'BigSquare': (200, 150, 255)  # Nebula glow
    },
    ui_bg=(20, 15, 40),
    ui_border=(100, 80, 150)
)

LAVA_THEME = Theme(
    name="Lava",
    bg_color=(8, 3, 0),
    grid_color=(50, 20, 10),
    text_color=(255, 220, 180),
    accent_color=(255, 100, 50),
    pieces_colors={
        'I': (255, 90, 20),      # Lava red
        'O': (255, 160, 30),     # Molten orange
        'T': (255, 60, 60),      # Hot red
        'S': (255, 210, 45),     # Flame yellow
        'Z': (200, 50, 20),      # Dark ember
        'J': (255, 120, 90),     # Burnt orange
        'L': (255, 180, 110),    # Warm orange
        # Extra pieces (Quadrix 2)
        'Plus': (255, 110, 90),  # Bright lava
        'Y': (220, 60, 45),      # Deep fire
        'Domino': (255, 160, 85),# Flame orange
        'BigSquare': (255, 140, 110)  # Glowing core
    },
    ui_bg=(35, 15, 10),
    ui_border=(120, 50, 30)
)

ICE_THEME = Theme(
    name="Ice",
    bg_color=(5, 8, 12),
    grid_color=(30, 50, 70),
    text_color=(220, 240, 255),
    accent_color=(150, 220, 255),
    pieces_colors={
        'I': (150, 220, 255),    # Icy cyan
        'O': (215, 240, 255),    # Snow white
        'T': (120, 200, 255),    # Glacier
        'S': (180, 230, 255),    # Pale ice
        'Z': (120, 180, 255),    # Deep ice
        'J': (100, 150, 255),    # Cold blue
        'L': (200, 220, 255),    # Crystal white
        # Extra pieces (Quadrix 2)
        'Plus': (170, 230, 255), # Sparkling ice
        'Y': (130, 190, 255),    # Frozen blue
        'Domino': (190, 235, 255),# Crystal glow
        'BigSquare': (160, 210, 255)  # Icy glow
    },
    ui_bg=(20, 35, 50),
    ui_border=(80, 130, 180)
)

RETRO_ATARI_THEME = Theme(
    name="Retro Atari",
    bg_color=(6, 4, 12),
    grid_color=(18, 12, 30),
    text_color=(0, 255, 221),
    accent_color=(255, 248, 0),
    pieces_colors={
        'I': (0, 255, 221),
        'O': (255, 248, 0),
        'T': (255, 132, 75),
        'S': (0, 200, 120),
        'Z': (255, 80, 80),
        'J': (0, 180, 255),
        'L': (255, 150, 50),
        'Plus': (0, 255, 180),
        'Y': (255, 208, 0),
        'Domino': (255, 120, 0),
        'BigSquare': (255, 60, 180)
    },
    ui_bg=(12, 14, 30),
    ui_border=(0, 255, 221)
)

CUSTOM_THEME_NAME = "Özel Tema"


def _clamp_color_channel(value):
    try:
        return max(0, min(255, int(value)))
    except (TypeError, ValueError):
        return 0


def build_custom_theme(custom_colors=None):
    base_colors = CLASSIC_THEME.pieces_colors.copy()
    if custom_colors:
        for name, color in custom_colors.items():
            if name in base_colors and isinstance(color, (list, tuple)) and len(color) == 3:
                base_colors[name] = tuple(_clamp_color_channel(c) for c in color)
    return Theme(
        name=CUSTOM_THEME_NAME,
        bg_color=(12, 14, 28),
        grid_color=(38, 52, 78),
        text_color=(235, 240, 255),
        accent_color=(255, 180, 120),
        pieces_colors=base_colors,
        ui_bg=(26, 30, 48),
        ui_border=(90, 110, 160)
    )


# Tüm temalar
THEMES = {
    'Classic': CLASSIC_THEME,
    'Cyberpunk': CYBERPUNK_THEME,
    'Sunset': SUNSET_THEME,
    'Forest': FOREST_THEME,
    'Galaxy': GALAXY_THEME,
    'Lava': LAVA_THEME,
    'Ice': ICE_THEME,
    'Retro Atari': RETRO_ATARI_THEME,
    CUSTOM_THEME_NAME: build_custom_theme()
}

# Tema içi parça renklerini tekilleştir (Özel Tema hariç).
for _t in THEMES.values():
    if getattr(_t, 'name', None) != CUSTOM_THEME_NAME:
        _t.pieces_colors = _make_piece_colors_unique(getattr(_t, 'pieces_colors', {}))


class ThemeManager:
    """Tema yöneticisi"""

    def __init__(self, settings_manager=None):
        self.settings_manager = settings_manager
        self.theme_name = 'Retro Atari'
        self._piece_color_cache = {}
        self.custom_theme_colors = {}
        if settings_manager:
            stored = settings_manager.get('custom_theme_colors', {}) or {}
            self.custom_theme_colors = self._sanitize_color_map(stored)
        self.refresh_custom_theme()
        default_theme = 'Classic'
        if settings_manager:
            default_theme = settings_manager.get('theme', default_theme)
        if not self.set_theme(default_theme):
            self.set_theme('Classic')
    
    def set_theme(self, theme_name):
        """Temayı değiştir"""
        if theme_name in THEMES:
            self.current_theme = THEMES[theme_name]
            self.theme_name = theme_name
            self._piece_color_cache = {}
            return True
        return False

    def refresh_custom_theme(self):
        """Custom temayı güncelle ve aktifse uygula."""
        THEMES[CUSTOM_THEME_NAME] = build_custom_theme(self.custom_theme_colors)
        if getattr(self, 'theme_name', None) == CUSTOM_THEME_NAME:
            self.current_theme = THEMES[CUSTOM_THEME_NAME]
        self._piece_color_cache = {}

    def update_custom_theme(self, colors_dict, persist=True):
        """Custom tema renklerini güncelle."""
        self.custom_theme_colors = self._sanitize_color_map(colors_dict)
        if persist and self.settings_manager:
            serializable = {name: list(color) for name, color in self.custom_theme_colors.items()}
            self.settings_manager.set('custom_theme_colors', serializable)
        self.refresh_custom_theme()
    
    def get_piece_color(self, piece_type):
        """Parça rengini al"""
        cached = self._piece_color_cache.get(piece_type)
        if cached is not None:
            return cached
        col = self.current_theme.pieces_colors.get(piece_type, WHITE)
        # Ensure sufficient contrast against the background; if not, slightly boost color
        bg = self.get_bg_color()
        def luminance(c):
            r, g, b = c
            return 0.2126 * r + 0.7152 * g + 0.0722 * b
        lum_bg = luminance(bg)
        lum_col = luminance(col)
        if abs(lum_bg - lum_col) < 40:
            # Boost brightness if too close
            def clamp(v):
                return max(0, min(255, int(v)))
            if lum_col <= lum_bg:
                # Make brighter
                boosted = tuple(clamp(c * 1.35) for c in col)
                self._piece_color_cache[piece_type] = boosted
                return boosted
            else:
                # Make slightly darker for contrast
                darkened = tuple(clamp(c * 0.65) for c in col)
                self._piece_color_cache[piece_type] = darkened
                return darkened
        self._piece_color_cache[piece_type] = col
        return col
    
    def get_bg_color(self):
        """Arka plan rengini al"""
        return self.current_theme.bg_color
    
    def get_grid_color(self):
        """Grid rengini al"""
        return self.current_theme.grid_color
    
    def get_text_color(self):
        """Metin rengini al"""
        return self.current_theme.text_color
    
    def get_accent_color(self):
        """Vurgu rengini al"""
        return self.current_theme.accent_color
    
    def get_ui_bg(self):
        """UI arka plan rengini al"""
        return self.current_theme.ui_bg
    
    def get_ui_border(self):
        """UI çerçeve rengini al"""
        return self.current_theme.ui_border
    
    def get_all_theme_names(self):
        """Tüm tema isimlerini al"""
        return list(THEMES.keys())

    @staticmethod
    def _sanitize_color_map(raw_map):
        sanitized = {}
        for name, color in (raw_map or {}).items():
            if isinstance(color, (list, tuple)) and len(color) == 3:
                sanitized[name] = tuple(_clamp_color_channel(c) for c in color)
        return sanitized
