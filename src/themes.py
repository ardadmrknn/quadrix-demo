"""Quadrix tema sistemi."""
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
        'I': (0, 255, 255),
        'O': (255, 184, 28),
        'T': (180, 88, 196),
        'S': (0, 200, 80),
        'Z': (255, 64, 64),
        'J': (22, 110, 220),
        'L': (255, 140, 0),
        'Plus': (240, 120, 200),
        'Y': (0, 190, 200),
        'Domino': (255, 180, 60),
        'BigSquare': (150, 110, 255),
    },
    ui_bg=(35, 40, 60),
    ui_border=(80, 100, 140),
)

THEMES = {
    CLASSIC_THEME.name: CLASSIC_THEME,
}


class ThemeManager:
    """Tema yöneticisi"""

    def __init__(self, settings_manager=None):
        self.settings_manager = settings_manager
        self.current_theme = CLASSIC_THEME
        self.theme_name = CLASSIC_THEME.name
        self._piece_color_cache = {}
    
    def set_theme(self, theme_name):
        """Temayı Classic üzerinde sabit tut."""
        self.current_theme = CLASSIC_THEME
        self.theme_name = CLASSIC_THEME.name
        self._piece_color_cache = {}
        return theme_name in THEMES
    
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
    
