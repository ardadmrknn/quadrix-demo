"""
Quadrix Full Edition - Yeniden Kullanılabilir UI Bileşenleri

Tüm ekranlarda kullanılacak ortak UI elementleri:
- Cam panel (Glassmorphism)
- Neon butonlar
- Slider bileşeni
- Toggle switch
- Sayı seçici
- İlerleme çubuğu
"""

import pygame
import math
from collections import OrderedDict
from typing import Tuple, Optional, Callable, List

from ui_theme import UIColors, UIFonts, UIStyle, lerp_color, brighten_color, add_alpha


# ============================================================================
# İÇ CACHE YARDIMCILARI (PERF)
# ============================================================================


class _LRUCache:
    def __init__(self, max_items: int):
        self._max_items = max(1, int(max_items))
        self._data: "OrderedDict[tuple, object]" = OrderedDict()

    def get(self, key: tuple):
        value = self._data.get(key)
        if value is not None:
            self._data.move_to_end(key)
        return value

    def set(self, key: tuple, value):
        self._data[key] = value
        self._data.move_to_end(key)
        while len(self._data) > self._max_items:
            self._data.popitem(last=False)


_TEXT_SURFACE_CACHE = _LRUCache(max_items=512)
_UI_SURFACE_CACHE = _LRUCache(max_items=128)


def _clamp_int(value: int, min_value: int, max_value: int) -> int:
    return max(min_value, min(max_value, int(value)))


def _quantize_int(value: int, step: int) -> int:
    if step <= 1:
        return int(value)
    return int(round(value / step) * step)


def _render_text_cached(
    font: pygame.font.Font,
    text: str,
    antialias: bool,
    color,
) -> pygame.Surface:
    key = (id(font), text, bool(antialias), tuple(color))
    cached = _TEXT_SURFACE_CACHE.get(key)
    if cached is not None:
        return cached
    rendered = font.render(text, antialias, color)
    _TEXT_SURFACE_CACHE.set(key, rendered)
    return rendered


def _get_cached_surface(key: tuple, build_fn) -> pygame.Surface:
    cached = _UI_SURFACE_CACHE.get(key)
    if cached is not None:
        return cached
    surf = build_fn()
    _UI_SURFACE_CACHE.set(key, surf)
    return surf


def _get_menu_transparency_multiplier() -> float:
    try:
        from retro_style import retro_style as _retro_style
        value = float(getattr(_retro_style, '_menu_transparency', 1.0))
    except Exception:
        value = 1.0
    return max(0.0, min(1.0, value))


def _scale_menu_alpha(alpha: int) -> int:
    scaled = int(round(int(alpha) * _get_menu_transparency_multiplier()))
    return _clamp_int(scaled, 0, 255)


# ============================================================================
# CAM PANEL (GLASSMORPHISM)
# ============================================================================

def draw_glass_panel(
    surface: pygame.Surface,
    rect: pygame.Rect,
    alpha: int = 180,
    border_color: Tuple[int, int, int] = None,
    border_width: int = 2,
    border_radius: int = 16,
    glow: bool = True,
    glow_color: Tuple[int, int, int] = None,
) -> None:
    """
    Cam efektli panel çiz (Glassmorphism)
    
    Args:
        surface: Çizilecek yüzey
        rect: Panel boyutları
        alpha: Saydamlık (0-255)
        border_color: Kenar rengi
        border_width: Kenar kalınlığı
        border_radius: Köşe yuvarlaklığı
        glow: Glow efekti ekle
        glow_color: Glow rengi
    """
    if border_color is None:
        border_color = UIColors.GLASS_BORDER[:3]
    
    if glow_color is None:
        glow_color = UIColors.NEON_CYAN

    panel_alpha = _scale_menu_alpha(alpha)
    border_alpha = _scale_menu_alpha(150)
    glow_alpha_outer = _scale_menu_alpha(30)
    glow_alpha_mid = _scale_menu_alpha(20)
    glow_alpha_inner = _scale_menu_alpha(10)
    
    # Glow efekti (panel arkasında)
    if glow:
        glow_key = (
            "glass_panel_glow",
            rect.width,
            rect.height,
            int(border_radius),
            tuple(glow_color[:3]),
            glow_alpha_outer,
            glow_alpha_mid,
            glow_alpha_inner,
        )

        def _build_glow() -> pygame.Surface:
            glow_surf = pygame.Surface((rect.width + 20, rect.height + 20), pygame.SRCALPHA)
            glow_rect = pygame.Rect(10, 10, rect.width, rect.height)
            pygame.draw.rect(glow_surf, (*glow_color[:3], glow_alpha_outer), glow_rect, border_radius=border_radius)
            pygame.draw.rect(glow_surf, (*glow_color[:3], glow_alpha_mid), glow_rect.inflate(6, 6), border_radius=border_radius + 3)
            pygame.draw.rect(glow_surf, (*glow_color[:3], glow_alpha_inner), glow_rect.inflate(12, 12), border_radius=border_radius + 6)
            return glow_surf

        glow_surf = _get_cached_surface(glow_key, _build_glow)
        surface.blit(glow_surf, (rect.x - 10, rect.y - 10), special_flags=pygame.BLEND_ADD)
    
    panel_key = (
        "glass_panel",
        rect.width,
        rect.height,
        panel_alpha,
        tuple(border_color),
        int(border_width),
        int(border_radius),
        border_alpha,
    )

    def _build_panel() -> pygame.Surface:
        panel_surf = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)

        # Arka plan
        pygame.draw.rect(
            panel_surf,
            (*UIColors.BG_MEDIUM, panel_alpha),
            (0, 0, rect.width, rect.height),
            border_radius=border_radius,
        )

        # Üst kenar parlaması
        highlight_rect = pygame.Rect(2, 2, rect.width - 4, rect.height // 3)
        highlight_surf = pygame.Surface((highlight_rect.width, highlight_rect.height), pygame.SRCALPHA)
        for i in range(highlight_rect.height):
            alpha_val = int(30 * (1 - i / highlight_rect.height))
            pygame.draw.line(
                highlight_surf,
                (255, 255, 255, alpha_val),
                (0, i),
                (highlight_rect.width, i),
            )
        panel_surf.blit(highlight_surf, highlight_rect.topleft)

        # Kenar çizgisi
        if border_width > 0:
            pygame.draw.rect(
                panel_surf,
                (*border_color, border_alpha),
                (0, 0, rect.width, rect.height),
                width=border_width,
                border_radius=border_radius,
            )

        return panel_surf

    panel_surf = _get_cached_surface(panel_key, _build_panel)
    surface.blit(panel_surf, rect.topleft)


def draw_glass_card(
    surface: pygame.Surface,
    rect: pygame.Rect,
    hovered: bool = False,
    selected: bool = False,
    accent_color: Tuple[int, int, int] = None,
) -> None:
    """Cam efektli kart çiz"""
    if accent_color is None:
        accent_color = UIColors.NEON_CYAN
    
    alpha = 200 if hovered else 160
    border_color = accent_color if (hovered or selected) else UIColors.GLASS_BORDER[:3]
    
    draw_glass_panel(
        surface, rect,
        alpha=alpha,
        border_color=border_color,
        border_width=2 if selected else 1,
        border_radius=UIStyle.BORDER_RADIUS_MEDIUM,
        glow=hovered or selected,
        glow_color=accent_color,
    )


# ============================================================================
# NEON BUTON
# ============================================================================

class NeonButton:
    """Neon efektli buton bileşeni"""
    
    def __init__(
        self,
        rect: pygame.Rect,
        text: str,
        color: Tuple[int, int, int] = None,
        font_size: int = None,
        icon: str = None,
    ):
        self.rect = rect
        self.text = text
        self.color = color or UIColors.NEON_CYAN
        self.font_size = font_size or UIFonts.SIZE_BODY
        self.icon = icon
        
        self.hovered = False
        self.pressed = False
        self.disabled = False
        
        # Animasyon
        self.hover_anim = 0.0  # 0-1 arası
        self.press_anim = 0.0
    
    def update(self, mouse_pos: Tuple[int, int], mouse_pressed: bool, dt: float) -> bool:
        """Buton durumunu güncelle. Tıklandıysa True döner."""
        was_pressed = self.pressed
        
        self.hovered = self.rect.collidepoint(mouse_pos) and not self.disabled
        self.pressed = self.hovered and mouse_pressed
        
        # Animasyonları güncelle
        target_hover = 1.0 if self.hovered else 0.0
        self.hover_anim += (target_hover - self.hover_anim) * min(1, dt * 10)
        
        target_press = 1.0 if self.pressed else 0.0
        self.press_anim += (target_press - self.press_anim) * min(1, dt * 15)
        
        # Tıklama tespiti (basılıyken bırakıldığında)
        return was_pressed and not self.pressed and self.hovered
    
    def draw(self, surface: pygame.Surface) -> None:
        """Butonu çiz"""
        if self.disabled:
            bg_color = UIColors.BUTTON_DISABLED
            text_color = UIColors.TEXT_MUTED
            border_color = UIColors.TEXT_MUTED
        else:
            # Animasyona göre renk
            bg_color = lerp_color(UIColors.BUTTON_BG, UIColors.BUTTON_HOVER, self.hover_anim)
            text_color = lerp_color(UIColors.TEXT_PRIMARY, self.color, self.hover_anim)
            border_color = lerp_color(UIColors.BUTTON_BORDER, self.color, self.hover_anim)
        
        # Press efekti için ölçek
        scale = 1.0 - (self.press_anim * 0.03)
        scaled_rect = self.rect.copy()
        if scale != 1.0:
            new_w = int(self.rect.width * scale)
            new_h = int(self.rect.height * scale)
            scaled_rect = pygame.Rect(
                self.rect.centerx - new_w // 2,
                self.rect.centery - new_h // 2,
                new_w, new_h
            )
        
        # Glow efekti
        if self.hovered and not self.disabled:
            alpha_main = _clamp_int(int(40 * self.hover_anim), 0, 255)
            alpha_outer = _clamp_int(int(20 * self.hover_anim), 0, 255)

            if alpha_main > 0 or alpha_outer > 0:
                glow_rect = pygame.Rect(8, 8, scaled_rect.width, scaled_rect.height)

                # Hover animasyonu stabilken cache kullan (görsel değişimi minimize eder)
                if self.hover_anim >= 0.98:
                    glow_key = (
                        "neon_button_glow_full",
                        scaled_rect.width,
                        scaled_rect.height,
                        tuple(self.color),
                    )

                    def _build_glow_full() -> pygame.Surface:
                        glow_surf = pygame.Surface((scaled_rect.width + 16, scaled_rect.height + 16), pygame.SRCALPHA)
                        pygame.draw.rect(
                            glow_surf,
                            (*self.color, 40),
                            glow_rect,
                            border_radius=UIStyle.BORDER_RADIUS_MEDIUM,
                        )
                        pygame.draw.rect(
                            glow_surf,
                            (*self.color, 20),
                            glow_rect.inflate(8, 8),
                            border_radius=UIStyle.BORDER_RADIUS_MEDIUM + 4,
                        )
                        return glow_surf

                    glow_surf = _get_cached_surface(glow_key, _build_glow_full)
                else:
                    glow_surf = pygame.Surface((scaled_rect.width + 16, scaled_rect.height + 16), pygame.SRCALPHA)
                    pygame.draw.rect(
                        glow_surf,
                        (*self.color, alpha_main),
                        glow_rect,
                        border_radius=UIStyle.BORDER_RADIUS_MEDIUM,
                    )
                    pygame.draw.rect(
                        glow_surf,
                        (*self.color, alpha_outer),
                        glow_rect.inflate(8, 8),
                        border_radius=UIStyle.BORDER_RADIUS_MEDIUM + 4,
                    )

                surface.blit(glow_surf, (scaled_rect.x - 8, scaled_rect.y - 8), special_flags=pygame.BLEND_ADD)
        
        # Arka plan
        pygame.draw.rect(surface, bg_color, scaled_rect, border_radius=UIStyle.BORDER_RADIUS_MEDIUM)
        
        # Kenar
        pygame.draw.rect(surface, border_color, scaled_rect, 
                        width=2, border_radius=UIStyle.BORDER_RADIUS_MEDIUM)
        
        # Metin
        font = UIFonts.get(self.font_size)
        text_surf = _render_text_cached(font, self.text, True, text_color)
        text_rect = text_surf.get_rect(center=scaled_rect.center)
        
        # İkon varsa sola kaydır
        if self.icon:
            text_rect.x += 12
        
        surface.blit(text_surf, text_rect)


# ============================================================================
# SLIDER BİLEŞENİ
# ============================================================================

class Slider:
    """Mouse ile sürüklenebilir slider"""
    
    def __init__(
        self,
        rect: pygame.Rect,
        min_val: float = 0.0,
        max_val: float = 1.0,
        value: float = 0.5,
        step: float = 0.01,
        color: Tuple[int, int, int] = None,
        show_value: bool = True,
        value_format: str = "{:.0%}",
    ):
        self.rect = rect
        self.min_val = min_val
        self.max_val = max_val
        self.value = max(min_val, min(max_val, value))
        self.step = step
        self.color = color or UIColors.NEON_CYAN
        self.show_value = show_value
        self.value_format = value_format
        
        self.dragging = False
        self.hovered = False
        
        # Tutamak boyutu
        self.handle_radius = rect.height // 2
    
    def update(self, mouse_pos: Tuple[int, int], mouse_pressed: bool, dt: float = 0) -> bool:
        """Slider'ı güncelle. Değer değiştiyse True döner."""
        old_value = self.value
        
        # Track alanı (tutamak hariç)
        track_rect = pygame.Rect(
            self.rect.x + self.handle_radius,
            self.rect.y,
            self.rect.width - self.handle_radius * 2,
            self.rect.height
        )
        
        # Hover tespiti
        self.hovered = self.rect.collidepoint(mouse_pos)
        
        # Sürükleme başlat/bitir
        if mouse_pressed and self.hovered:
            self.dragging = True
        elif not mouse_pressed:
            self.dragging = False
        
        # Sürükleniyorsa değeri güncelle
        if self.dragging:
            # Mouse x pozisyonunu değere çevir
            relative_x = mouse_pos[0] - track_rect.x
            ratio = relative_x / track_rect.width
            ratio = max(0, min(1, ratio))
            
            new_value = self.min_val + ratio * (self.max_val - self.min_val)
            
            # Step'e yuvarla
            if self.step > 0:
                new_value = round(new_value / self.step) * self.step
            
            self.value = max(self.min_val, min(self.max_val, new_value))
        
        return self.value != old_value
    
    def draw(self, surface: pygame.Surface) -> None:
        """Slider'ı çiz"""
        track_height = 6
        track_y = self.rect.centery - track_height // 2
        
        # Track arka planı
        track_rect = pygame.Rect(
            self.rect.x + self.handle_radius,
            track_y,
            self.rect.width - self.handle_radius * 2,
            track_height
        )
        pygame.draw.rect(surface, UIColors.SLIDER_BG, track_rect, border_radius=3)
        
        # Dolu kısım
        fill_ratio = (self.value - self.min_val) / (self.max_val - self.min_val)
        fill_width = int(track_rect.width * fill_ratio)
        if fill_width > 0:
            fill_rect = pygame.Rect(track_rect.x, track_rect.y, fill_width, track_height)
            pygame.draw.rect(surface, self.color, fill_rect, border_radius=3)
        
        # Tutamak pozisyonu
        handle_x = track_rect.x + fill_width
        handle_y = self.rect.centery
        
        # Tutamak glow
        if self.hovered or self.dragging:
            glow_key = ("slider_handle_glow", int(self.handle_radius), tuple(self.color))

            def _build_glow() -> pygame.Surface:
                glow_surf = pygame.Surface((self.handle_radius * 4, self.handle_radius * 4), pygame.SRCALPHA)
                pygame.draw.circle(
                    glow_surf,
                    (*self.color, 60),
                    (self.handle_radius * 2, self.handle_radius * 2),
                    self.handle_radius + 6,
                )
                return glow_surf

            glow_surf = _get_cached_surface(glow_key, _build_glow)
            surface.blit(
                glow_surf,
                (handle_x - self.handle_radius * 2, handle_y - self.handle_radius * 2),
                special_flags=pygame.BLEND_ADD,
            )
        
        # Tutamak
        handle_color = self.color if self.dragging else UIColors.SLIDER_HANDLE
        pygame.draw.circle(surface, handle_color, (handle_x, handle_y), self.handle_radius - 2)
        pygame.draw.circle(surface, UIColors.TEXT_PRIMARY, (handle_x, handle_y), self.handle_radius - 2, width=2)
        
        # Değer gösterimi
        if self.show_value:
            font = UIFonts.small()
            value_text = self.value_format.format(self.value)
            text_surf = _render_text_cached(font, value_text, True, UIColors.TEXT_PRIMARY)
            text_rect = text_surf.get_rect(midleft=(self.rect.right + 10, self.rect.centery))
            surface.blit(text_surf, text_rect)


# ============================================================================
# TOGGLE SWITCH
# ============================================================================

class ToggleSwitch:
    """Açma/kapama anahtarı"""
    
    def __init__(
        self,
        rect: pygame.Rect,
        value: bool = False,
        on_color: Tuple[int, int, int] = None,
        off_color: Tuple[int, int, int] = None,
    ):
        self.rect = rect
        self.value = value
        self.on_color = on_color or UIColors.NEON_GREEN
        self.off_color = off_color or UIColors.SLIDER_BG
        
        self.hovered = False
        self.anim = 1.0 if value else 0.0  # Animasyon değeri
    
    def update(self, mouse_pos: Tuple[int, int], mouse_clicked: bool, dt: float = 0) -> bool:
        """Toggle'ı güncelle. Değer değiştiyse True döner."""
        self.hovered = self.rect.collidepoint(mouse_pos)
        
        # Animasyonu güncelle
        target = 1.0 if self.value else 0.0
        self.anim += (target - self.anim) * min(1, (dt if dt > 0 else 0.016) * 12)
        
        # Tıklama
        if mouse_clicked and self.hovered:
            self.value = not self.value
            return True
        
        return False
    
    def draw(self, surface: pygame.Surface) -> None:
        """Toggle'ı çiz"""
        # Arka plan
        bg_color = lerp_color(self.off_color, self.on_color, self.anim)
        pygame.draw.rect(surface, bg_color, self.rect, border_radius=self.rect.height // 2)
        
        # Kenar
        border_color = brighten_color(bg_color, 1.3) if self.hovered else bg_color
        pygame.draw.rect(surface, border_color, self.rect, 
                        width=2, border_radius=self.rect.height // 2)
        
        # Tutamak
        handle_radius = self.rect.height // 2 - 4
        handle_x = self.rect.x + handle_radius + 4 + int((self.rect.width - handle_radius * 2 - 8) * self.anim)
        handle_y = self.rect.centery
        
        pygame.draw.circle(surface, UIColors.TEXT_PRIMARY, (handle_x, handle_y), handle_radius)


# ============================================================================
# SAYI SEÇİCİ (NUMBER PICKER)
# ============================================================================

class NumberPicker:
    """+/- butonlu sayı seçici"""
    
    def __init__(
        self,
        rect: pygame.Rect,
        min_val: int = 0,
        max_val: int = 100,
        value: int = 50,
        step: int = 1,
        suffix: str = "",
        color: Tuple[int, int, int] = None,
    ):
        self.rect = rect
        self.min_val = min_val
        self.max_val = max_val
        self.value = max(min_val, min(max_val, value))
        self.step = step
        self.suffix = suffix
        self.color = color or UIColors.NEON_CYAN
        
        # Buton alanları
        btn_size = rect.height - 4
        self.minus_rect = pygame.Rect(rect.x + 2, rect.y + 2, btn_size, btn_size)
        self.plus_rect = pygame.Rect(rect.right - btn_size - 2, rect.y + 2, btn_size, btn_size)
        
        self.minus_hovered = False
        self.plus_hovered = False
        self.minus_pressed = False
        self.plus_pressed = False
        
        # Basılı tutma için sayaçlar
        self.hold_timer = 0
        self.repeat_timer = 0
    
    def update(self, mouse_pos: Tuple[int, int], mouse_pressed: bool, dt: float = 0.016) -> bool:
        """Number picker'ı güncelle. Değer değiştiyse True döner."""
        old_value = self.value
        
        self.minus_hovered = self.minus_rect.collidepoint(mouse_pos)
        self.plus_hovered = self.plus_rect.collidepoint(mouse_pos)
        
        # Tıklama tespiti
        if mouse_pressed:
            if self.minus_hovered:
                if not self.minus_pressed:
                    # İlk tıklama
                    self.value = max(self.min_val, self.value - self.step)
                    self.hold_timer = 0
                    self.repeat_timer = 0
                else:
                    # Basılı tutma
                    self.hold_timer += dt
                    if self.hold_timer > 0.5:  # 500ms sonra tekrar et
                        self.repeat_timer += dt
                        if self.repeat_timer > 0.1:  # Her 100ms'de bir
                            self.value = max(self.min_val, self.value - self.step)
                            self.repeat_timer = 0
                self.minus_pressed = True
            elif self.plus_hovered:
                if not self.plus_pressed:
                    self.value = min(self.max_val, self.value + self.step)
                    self.hold_timer = 0
                    self.repeat_timer = 0
                else:
                    self.hold_timer += dt
                    if self.hold_timer > 0.5:
                        self.repeat_timer += dt
                        if self.repeat_timer > 0.1:
                            self.value = min(self.max_val, self.value + self.step)
                            self.repeat_timer = 0
                self.plus_pressed = True
        else:
            self.minus_pressed = False
            self.plus_pressed = False
            self.hold_timer = 0
        
        return self.value != old_value
    
    def draw(self, surface: pygame.Surface) -> None:
        """Number picker'ı çiz"""
        # Ana arka plan
        pygame.draw.rect(surface, UIColors.BUTTON_BG, self.rect, border_radius=UIStyle.BORDER_RADIUS_SMALL)
        pygame.draw.rect(surface, UIColors.BUTTON_BORDER, self.rect, 
                        width=1, border_radius=UIStyle.BORDER_RADIUS_SMALL)
        
        # Eksi butonu
        minus_color = brighten_color(UIColors.BUTTON_BG, 1.3) if self.minus_hovered else UIColors.BUTTON_BG
        if self.minus_pressed:
            minus_color = UIColors.BUTTON_ACTIVE
        pygame.draw.rect(surface, minus_color, self.minus_rect, border_radius=UIStyle.BORDER_RADIUS_SMALL)
        
        # Eksi işareti
        minus_y = self.minus_rect.centery
        pygame.draw.line(surface, UIColors.TEXT_PRIMARY,
                        (self.minus_rect.x + 8, minus_y),
                        (self.minus_rect.right - 8, minus_y), 2)
        
        # Artı butonu
        plus_color = brighten_color(UIColors.BUTTON_BG, 1.3) if self.plus_hovered else UIColors.BUTTON_BG
        if self.plus_pressed:
            plus_color = UIColors.BUTTON_ACTIVE
        pygame.draw.rect(surface, plus_color, self.plus_rect, border_radius=UIStyle.BORDER_RADIUS_SMALL)
        
        # Artı işareti
        plus_cx = self.plus_rect.centerx
        plus_cy = self.plus_rect.centery
        pygame.draw.line(surface, UIColors.TEXT_PRIMARY,
                        (plus_cx - 6, plus_cy), (plus_cx + 6, plus_cy), 2)
        pygame.draw.line(surface, UIColors.TEXT_PRIMARY,
                        (plus_cx, plus_cy - 6), (plus_cx, plus_cy + 6), 2)
        
        # Değer
        font = UIFonts.body()
        value_text = f"{self.value}{self.suffix}"
        text_surf = _render_text_cached(font, value_text, True, UIColors.TEXT_PRIMARY)
        text_rect = text_surf.get_rect(center=self.rect.center)
        surface.blit(text_surf, text_rect)


# ============================================================================
# İLERLEME ÇUBUĞU (PROGRESS BAR)
# ============================================================================

def draw_progress_bar(
    surface: pygame.Surface,
    rect: pygame.Rect,
    value: float,
    max_value: float = 1.0,
    color: Tuple[int, int, int] = None,
    bg_color: Tuple[int, int, int] = None,
    show_text: bool = False,
    text_format: str = "{:.0%}",
    glow: bool = True,
) -> None:
    """
    İlerleme çubuğu çiz
    
    Args:
        value: Mevcut değer
        max_value: Maksimum değer
        color: Dolgu rengi
        bg_color: Arka plan rengi
        show_text: Yüzde göster
        text_format: Metin formatı
        glow: Glow efekti
    """
    if color is None:
        color = UIColors.NEON_CYAN
    if bg_color is None:
        bg_color = UIColors.SLIDER_BG
    
    ratio = min(1.0, max(0.0, value / max_value if max_value > 0 else 0))
    
    # Arka plan
    pygame.draw.rect(surface, bg_color, rect, border_radius=rect.height // 2)
    
    # Dolgu
    if ratio > 0:
        fill_width = max(rect.height, int(rect.width * ratio))
        fill_rect = pygame.Rect(rect.x, rect.y, fill_width, rect.height)
        
        # Glow
        if glow:
            glow_key = ("progress_bar_glow", fill_width, rect.height, tuple(color))

            def _build_glow() -> pygame.Surface:
                glow_surf = pygame.Surface((fill_width + 10, rect.height + 10), pygame.SRCALPHA)
                glow_rect = pygame.Rect(5, 5, fill_width, rect.height)
                pygame.draw.rect(glow_surf, (*color, 60), glow_rect, border_radius=rect.height // 2)
                return glow_surf

            glow_surf = _get_cached_surface(glow_key, _build_glow)
            surface.blit(glow_surf, (rect.x - 5, rect.y - 5), special_flags=pygame.BLEND_ADD)
        
        pygame.draw.rect(surface, color, fill_rect, border_radius=rect.height // 2)
    
    # Kenar
    pygame.draw.rect(surface, brighten_color(bg_color, 1.3), rect, 
                    width=1, border_radius=rect.height // 2)
    
    # Metin
    if show_text:
        font = UIFonts.small()
        text = text_format.format(ratio)
        text_surf = _render_text_cached(font, text, True, UIColors.TEXT_PRIMARY)
        text_rect = text_surf.get_rect(center=rect.center)
        surface.blit(text_surf, text_rect)


# ============================================================================
# SEKME ÇUBUĞU (TAB BAR)
# ============================================================================

class TabBar:
    """Sekme çubuğu bileşeni"""
    
    def __init__(
        self,
        rect: pygame.Rect,
        tabs: List[str],
        selected: int = 0,
        color: Tuple[int, int, int] = None,
    ):
        self.rect = rect
        self.tabs = tabs
        self.selected = selected
        self.color = color or UIColors.NEON_CYAN
        
        self.hovered = -1
        self.tab_rects: List[pygame.Rect] = []
        self._calculate_tab_rects()
    
    def _calculate_tab_rects(self) -> None:
        """Sekme alanlarını hesapla"""
        if not self.tabs:
            return
        
        tab_width = self.rect.width // len(self.tabs)
        self.tab_rects = []
        
        for i in range(len(self.tabs)):
            tab_rect = pygame.Rect(
                self.rect.x + i * tab_width,
                self.rect.y,
                tab_width,
                self.rect.height
            )
            self.tab_rects.append(tab_rect)
    
    def update(self, mouse_pos: Tuple[int, int], mouse_clicked: bool) -> bool:
        """Tab bar'ı güncelle. Seçim değiştiyse True döner."""
        old_selected = self.selected
        self.hovered = -1
        
        for i, tab_rect in enumerate(self.tab_rects):
            if tab_rect.collidepoint(mouse_pos):
                self.hovered = i
                if mouse_clicked:
                    self.selected = i
                break
        
        return self.selected != old_selected
    
    def draw(self, surface: pygame.Surface) -> None:
        """Tab bar'ı çiz"""
        # Arka plan
        pygame.draw.rect(surface, UIColors.BG_MEDIUM, self.rect, border_radius=UIStyle.BORDER_RADIUS_SMALL)
        
        for i, (tab_rect, tab_name) in enumerate(zip(self.tab_rects, self.tabs)):
            is_selected = i == self.selected
            is_hovered = i == self.hovered
            
            # Sekme arka planı
            if is_selected:
                pygame.draw.rect(surface, self.color, tab_rect, border_radius=UIStyle.BORDER_RADIUS_SMALL)
            elif is_hovered:
                pygame.draw.rect(surface, UIColors.TAB_HOVER, tab_rect, border_radius=UIStyle.BORDER_RADIUS_SMALL)
            
            # Metin
            font = UIFonts.body()
            text_color = UIColors.BG_DARK if is_selected else (UIColors.TEXT_PRIMARY if is_hovered else UIColors.TEXT_SECONDARY)
            text_surf = _render_text_cached(font, tab_name, True, text_color)
            text_rect = text_surf.get_rect(center=tab_rect.center)
            surface.blit(text_surf, text_rect)
        
        # Dış kenar
        pygame.draw.rect(surface, UIColors.BUTTON_BORDER, self.rect, 
                        width=1, border_radius=UIStyle.BORDER_RADIUS_SMALL)


# ============================================================================
# YARDIMCI ÇİZİM FONKSİYONLARI
# ============================================================================

def draw_text_with_shadow(
    surface: pygame.Surface,
    text: str,
    pos: Tuple[int, int],
    font: pygame.font.Font,
    color: Tuple[int, int, int] = None,
    shadow_color: Tuple[int, int, int] = None,
    shadow_offset: int = 2,
    center: bool = False,
) -> pygame.Rect:
    """Gölgeli metin çiz"""
    if color is None:
        color = UIColors.TEXT_PRIMARY
    if shadow_color is None:
        shadow_color = (0, 0, 0)
    
    # Gölge
    shadow_surf = _render_text_cached(font, text, True, shadow_color)
    text_surf = _render_text_cached(font, text, True, color)
    
    if center:
        shadow_rect = shadow_surf.get_rect(center=(pos[0] + shadow_offset, pos[1] + shadow_offset))
        text_rect = text_surf.get_rect(center=pos)
    else:
        shadow_rect = shadow_surf.get_rect(topleft=(pos[0] + shadow_offset, pos[1] + shadow_offset))
        text_rect = text_surf.get_rect(topleft=pos)
    
    surface.blit(shadow_surf, shadow_rect)
    surface.blit(text_surf, text_rect)
    
    return text_rect


def draw_neon_text(
    surface: pygame.Surface,
    text: str,
    pos: Tuple[int, int],
    font: pygame.font.Font,
    color: Tuple[int, int, int] = None,
    glow_radius: int = 3,
    center: bool = False,
) -> pygame.Rect:
    """Neon efektli metin çiz"""
    if color is None:
        color = UIColors.NEON_CYAN
    
    text_surf = _render_text_cached(font, text, True, color)
    
    if center:
        text_rect = text_surf.get_rect(center=pos)
    else:
        text_rect = text_surf.get_rect(topleft=pos)
    
    # Glow efekti
    for i in range(glow_radius, 0, -1):
        glow_alpha = int(100 / i)
        glow_surf = _render_text_cached(font, text, True, (*color, glow_alpha))
        for dx in range(-i, i + 1):
            for dy in range(-i, i + 1):
                if dx * dx + dy * dy <= i * i:
                    surface.blit(glow_surf, (text_rect.x + dx, text_rect.y + dy), 
                               special_flags=pygame.BLEND_ADD)
    
    surface.blit(text_surf, text_rect)
    
    return text_rect
