"""Campaign Modu UI Bileşenleri ve Efektleri

Oyunun mevcut neon/glassmorphism stiline uygun:
- Power-up bar
- Özel blok overlay'leri
- Level geçiş animasyonları
- Başarı/başarısızlık efektleri
"""
from __future__ import annotations

import pygame
import math
from typing import Dict, Any, List, Optional, Tuple, TYPE_CHECKING

from ui_theme import UIColors, UIFonts, UIStyle
from localization import t

# Oyunun renk paleti (merkezi tema)
NEON_CYAN = UIColors.NEON_CYAN
NEON_MAGENTA = UIColors.NEON_MAGENTA
NEON_ORANGE = UIColors.NEON_ORANGE
NEON_LIME = UIColors.NEON_GREEN
NEON_BLUE = UIColors.NEON_CYAN
GOLD = UIColors.NEON_GOLD
SILVER = UIColors.TEXT_SECONDARY
BRONZE = (205, 127, 50)

# Özel blok renkleri - neon temaya uygun
SPECIAL_BLOCK_COLORS = {
    'ice': (100, 200, 255),       # Buz mavisi
    'locked': (140, 140, 160),    # Metal gri
    'bomb': (255, 80, 80),        # Kırmızı
    'timer': (255, 180, 50),      # Turuncu-sarı
    'star': GOLD,                  # Altın
    'rainbow': NEON_MAGENTA,       # Magenta (animasyonlu)
}


class CampaignUIEffects:
    """Campaign moduna özgü UI efektleri"""
    
    def __init__(self):
        self.animation_time = 0.0
        self._font_cache: Dict[int, pygame.font.Font] = {}
        self._power_bar_cache: Dict[Tuple[int, int], pygame.Surface] = {}
        self._level_overlay_cache: Dict[Tuple[int, int], pygame.Surface] = {}
        self._level_failed_overlay_cache: Dict[Tuple[int, int], pygame.Surface] = {}
        
        # Aktif animasyonlar
        self.level_complete_animation = None
        self.level_failed_animation = None
        self.star_animations: List[Dict] = []
        self.explosion_effects: List[Dict] = []
        self.particle_effects: List[Dict] = []

        # Mouse tıklama için buton rect'leri (her frame draw'da güncellenir)
        self._failed_buttons: Dict[str, pygame.Rect] = {}
        self._complete_buttons: Dict[str, pygame.Rect] = {}
        
    def update(self, dt: float) -> None:
        """Animasyonları güncelle"""
        self.animation_time += dt
        
        # Level complete animasyonu
        if self.level_complete_animation:
            self.level_complete_animation['time'] = min(
                self.level_complete_animation['time'] + dt,
                3.0,
            )
        
        # Level failed animasyonu
        if self.level_failed_animation:
            self.level_failed_animation['time'] = min(
                self.level_failed_animation['time'] + dt,
                2.0,
            )
        
        # Yıldız animasyonları
        for star in self.star_animations[:]:
            star['time'] += dt
            if star['time'] > 1.5:
                self.star_animations.remove(star)
        
        # Patlama efektleri
        for exp in self.explosion_effects[:]:
            exp['time'] += dt
            if exp['time'] > 0.8:
                self.explosion_effects.remove(exp)
        
        # Parçacık efektleri
        for p in self.particle_effects[:]:
            p['time'] += dt
            p['x'] += p['vx'] * dt
            p['y'] += p['vy'] * dt
            p['vy'] += 200 * dt  # Gravity
            if p['time'] > p['lifetime']:
                self.particle_effects.remove(p)
    
    def _get_font(self, size: int) -> pygame.font.Font:
        """Font cache"""
        if size not in self._font_cache:
            self._font_cache[size] = UIFonts.get(size)
        return self._font_cache[size]
    
    # ==========================================
    # POWER-UP BAR
    # ==========================================
    
    def draw_power_up_bar(
        self,
        surface: pygame.Surface,
        power_up_manager,
        x: int,
        y: int,
        width: int,
        lang: str = 'tr'
    ) -> List[Tuple[pygame.Rect, Any]]:
        """Glassmorphism stilinde power-up bar çiz"""
        from .power_ups import PowerUpType, POWER_UPS
        
        clickable = []
        available = power_up_manager.get_available_list()
        
        if not available:
            return clickable
        
        bar_height = 56
        
        # Glassmorphism arka plan
        cache_key = (width, bar_height)
        bar_surf = self._power_bar_cache.get(cache_key)
        if bar_surf is None:
            bar_surf = pygame.Surface((width, bar_height), pygame.SRCALPHA)
            bar_surf.fill(UIColors.GLASS_BG)
            
            # Üst highlight
            for i in range(12):
                alpha = int(30 * (1 - i / 12))
                pygame.draw.line(bar_surf, UIColors.GLASS_HIGHLIGHT[:3] + (alpha,), (0, i), (width, i))
            self._power_bar_cache[cache_key] = bar_surf
        
        surface.blit(bar_surf, (x, y))
        
        # Neon border
        bar_rect = pygame.Rect(x, y, width, bar_height)
        pygame.draw.rect(surface, (*NEON_CYAN, 150), bar_rect, 2, border_radius=UIStyle.BORDER_RADIUS_MEDIUM)
        
        # Power-up ikonları
        icon_size = 44
        padding = 12
        start_x = x + padding
        
        for i, (ptype, count) in enumerate(available):
            config = POWER_UPS.get(ptype)
            if not config:
                continue
            
            icon_x = start_x + i * (icon_size + padding)
            icon_y = y + (bar_height - icon_size) // 2
            icon_rect = pygame.Rect(icon_x, icon_y, icon_size, icon_size)
            
            # Seçili/kullanılabilir durumu
            is_selected = power_up_manager.selected_power_up == ptype
            can_use, _ = power_up_manager.can_use(ptype)
            
            # İkon arka planı
            icon_surf = pygame.Surface((icon_size, icon_size), pygame.SRCALPHA)
            
            if is_selected:
                # Neon glow
                pygame.draw.rect(icon_surf, (*NEON_LIME, 200), icon_surf.get_rect(), border_radius=UIStyle.BORDER_RADIUS_SMALL)
                glow_rect = icon_rect.inflate(8, 8)
                glow_surf = pygame.Surface(glow_rect.size, pygame.SRCALPHA)
                pygame.draw.rect(glow_surf, (*NEON_LIME, 60), glow_surf.get_rect(), border_radius=UIStyle.BORDER_RADIUS_MEDIUM)
                surface.blit(glow_surf, glow_rect.topleft)
            elif can_use:
                pygame.draw.rect(icon_surf, (*UIColors.BUTTON_BG, 220), icon_surf.get_rect(), border_radius=UIStyle.BORDER_RADIUS_SMALL)
            else:
                pygame.draw.rect(icon_surf, (*UIColors.BUTTON_DISABLED, 180), icon_surf.get_rect(), border_radius=UIStyle.BORDER_RADIUS_SMALL)
            
            surface.blit(icon_surf, icon_rect.topleft)
            
            # İkon border
            border_color = NEON_LIME if is_selected else (NEON_CYAN if can_use else UIColors.BUTTON_BORDER)
            pygame.draw.rect(surface, border_color, icon_rect, 2, border_radius=UIStyle.BORDER_RADIUS_SMALL)
            
            # Power-up sembolü (neon efektli)
            symbols = {
                PowerUpType.LINE_BOMB: "B",
                PowerUpType.TIME_FREEZE: "T",
                PowerUpType.SLOW_DOWN: "S",
                PowerUpType.SHUFFLE: "K",
                PowerUpType.CLEAR_COLUMN: "C",
                PowerUpType.SCORE_BOOST: "X",
            }
            symbol = symbols.get(ptype, "?")
            
            font = self._get_font(28)
            text_color = UIColors.TEXT_PRIMARY if can_use else UIColors.TEXT_MUTED
            text = font.render(symbol, True, text_color)
            text_rect = text.get_rect(center=icon_rect.center)
            surface.blit(text, text_rect)
            
            # Sayı badge (sağ alt)
            if count > 1:
                badge_font = self._get_font(16)
                badge = badge_font.render(str(count), True, UIColors.TEXT_PRIMARY)
                badge_x = icon_rect.right - 12
                badge_y = icon_rect.bottom - 12
                pygame.draw.circle(surface, NEON_MAGENTA, (badge_x, badge_y), 10)
                badge_rect = badge.get_rect(center=(badge_x, badge_y))
                surface.blit(badge, badge_rect)
            
            clickable.append((icon_rect, ptype))
        
        return clickable
    
    def draw_active_power_ups(
        self,
        surface: pygame.Surface,
        power_up_manager,
        x: int,
        y: int,
        lang: str = 'tr'
    ) -> None:
        """Aktif power-up'ları göster (süreli olanlar)"""
        from .power_ups import POWER_UPS
        
        if not power_up_manager.active_power_ups:
            return
        
        current_y = y
        
        for active in power_up_manager.active_power_ups:
            config = POWER_UPS.get(active.power_type)
            if not config:
                continue
            
            name = config.name.get(lang, config.name.get('en', ''))
            remaining = active.remaining_time
            max_time = config.duration
            
            # Progress bar
            bar_width = 120
            bar_height = 20
            
            # Arka plan
            bg_rect = pygame.Rect(x, current_y, bar_width, bar_height)
            pygame.draw.rect(surface, UIColors.SLIDER_BG + (200,), bg_rect, border_radius=UIStyle.BORDER_RADIUS_SMALL)
            
            # Progress
            progress = remaining / max_time if max_time > 0 else 0
            fill_width = int(bar_width * progress)
            if fill_width > 0:
                fill_rect = pygame.Rect(x, current_y, fill_width, bar_height)
                
                # Renk gradyanı (yeşil -> sarı -> kırmızı)
                if progress > 0.5:
                    color = NEON_LIME
                elif progress > 0.2:
                    color = NEON_ORANGE
                else:
                    color = UIColors.NEON_RED
                
                pygame.draw.rect(surface, color, fill_rect, border_radius=UIStyle.BORDER_RADIUS_SMALL)
            
            # Border
            pygame.draw.rect(surface, NEON_CYAN, bg_rect, 1, border_radius=UIStyle.BORDER_RADIUS_SMALL)
            
            # İsim ve süre
            font = self._get_font(16)
            text = f"{name[:8]}: {int(remaining)}s"
            text_surf = font.render(text, True, UIColors.TEXT_PRIMARY)
            text_rect = text_surf.get_rect(center=bg_rect.center)
            surface.blit(text_surf, text_rect)
            
            current_y += bar_height + 5
    
    # ==========================================
    # ÖZEL BLOK OVERLAY'LERİ
    # ==========================================
    
    def draw_special_block_overlay(
        self,
        surface: pygame.Surface,
        block_type: str,
        x: int,
        y: int,
        cell_size: int,
        state: Optional[Dict] = None
    ) -> None:
        """Özel blok overlay'ini oyunun stiline uygun çiz"""
        
        if block_type == 'ice':
            self._draw_ice_block(surface, x, y, cell_size, state)
        elif block_type == 'locked':
            self._draw_locked_block(surface, x, y, cell_size, state)
        elif block_type == 'bomb':
            self._draw_bomb_block(surface, x, y, cell_size)
        elif block_type == 'timer':
            self._draw_timer_block(surface, x, y, cell_size, state)
        elif block_type == 'star':
            self._draw_star_block(surface, x, y, cell_size)
        elif block_type == 'rainbow':
            self._draw_rainbow_block(surface, x, y, cell_size)
    
    def _draw_ice_block(self, surface: pygame.Surface, x: int, y: int, size: int, state: Optional[Dict]) -> None:
        """Buz bloğu - neon buz efekti"""
        overlay = pygame.Surface((size, size), pygame.SRCALPHA)
        
        # Buz mavisi overlay
        overlay.fill((100, 200, 255, 160))
        
        # Çapraz kristal çizgiler
        line_color = (200, 240, 255, 200)
        padding = size // 5
        pygame.draw.line(overlay, line_color, (padding, padding), (size - padding, size - padding), 2)
        pygame.draw.line(overlay, line_color, (size - padding, padding), (padding, size - padding), 2)
        
        # Merkez parlama
        pygame.draw.circle(overlay, (255, 255, 255, 80), (size // 2, size // 2), size // 4)
        
        surface.blit(overlay, (x, y))
        
        # Neon border
        pygame.draw.rect(surface, (*SPECIAL_BLOCK_COLORS['ice'], 200), (x, y, size, size), 2)
    
    def _draw_locked_block(self, surface: pygame.Surface, x: int, y: int, size: int, state: Optional[Dict]) -> None:
        """Kilitli blok - metal efekti"""
        overlay = pygame.Surface((size, size), pygame.SRCALPHA)
        
        # Metal gri overlay
        overlay.fill((100, 100, 120, 180))
        
        # Zincir deseni
        chain_color = (70, 70, 85, 220)
        mid = size // 2
        pygame.draw.line(overlay, chain_color, (0, mid), (size, mid), 3)
        pygame.draw.line(overlay, chain_color, (mid, 0), (mid, size), 3)
        
        surface.blit(overlay, (x, y))
        
        # Katman sayısı
        if state and state.get('layers', 1) > 1:
            font = self._get_font(size // 2)
            text = font.render(str(state['layers']), True, NEON_ORANGE)
            text_rect = text.get_rect(center=(x + mid, y + mid))
            surface.blit(text, text_rect)
        
        # Metal border
        pygame.draw.rect(surface, (160, 160, 180), (x, y, size, size), 2)
    
    def _draw_bomb_block(self, surface: pygame.Surface, x: int, y: int, size: int) -> None:
        """Bomba bloğu - neon kırmızı patlama efekti"""
        overlay = pygame.Surface((size, size), pygame.SRCALPHA)
        
        center = size // 2
        radius = size // 3
        
        # Bomba gövdesi
        pygame.draw.circle(overlay, (40, 40, 50, 240), (center, center), radius)
        
        # Neon kırmızı glow
        glow_color = (*SPECIAL_BLOCK_COLORS['bomb'], 100)
        pygame.draw.circle(overlay, glow_color, (center, center), radius + 4)
        
        # Fitil (animasyonlu kıvılcım)
        spark_phase = (self.animation_time * 8) % 1.0
        fitil_end = (center + radius // 2, center - radius)
        pygame.draw.line(overlay, (180, 140, 80, 255), (center, center - radius + 2), fitil_end, 2)
        
        # Kıvılcım
        spark_color = NEON_ORANGE if spark_phase < 0.5 else (255, 100, 50)
        pygame.draw.circle(overlay, (*spark_color, 255), fitil_end, 4)
        
        surface.blit(overlay, (x, y))
    
    def _draw_timer_block(self, surface: pygame.Surface, x: int, y: int, size: int, state: Optional[Dict]) -> None:
        """Zamanlı blok - countdown efekti"""
        overlay = pygame.Surface((size, size), pygame.SRCALPHA)
        
        remaining = state.get('timer', 15.0) if state else 15.0
        ratio = min(1.0, remaining / 15.0)
        
        # Renk (yeşil -> sarı -> kırmızı)
        if ratio > 0.5:
            color = (*NEON_LIME, 160)
        elif ratio > 0.2:
            color = (*NEON_ORANGE, 180)
        else:
            # Yanıp sönen kırmızı
            flash = 0.5 + 0.5 * math.sin(self.animation_time * 10)
            alpha = int(150 + 80 * flash)
            color = (255, 80, 80, alpha)
        
        overlay.fill(color)
        
        surface.blit(overlay, (x, y))
        
        # Süre göstergesi
        font = self._get_font(size // 2)
        text = font.render(str(int(remaining)), True, (255, 255, 255))
        text_rect = text.get_rect(center=(x + size // 2, y + size // 2))
        surface.blit(text, text_rect)
        
        # Border
        pygame.draw.rect(surface, color[:3], (x, y, size, size), 2)
    
    def _draw_star_block(self, surface: pygame.Surface, x: int, y: int, size: int) -> None:
        """Yıldız bloğu - altın parıltı efekti"""
        overlay = pygame.Surface((size, size), pygame.SRCALPHA)
        
        center = size // 2
        
        # Parıltı (animasyonlu)
        glow_phase = 0.7 + 0.3 * math.sin(self.animation_time * 4)
        glow_radius = int(size * 0.4 * glow_phase)
        
        pygame.draw.circle(overlay, (*GOLD, 100), (center, center), glow_radius)
        
        # Yıldız şekli
        points = []
        for i in range(5):
            angle = math.radians(i * 72 - 90)
            outer_x = center + int(size * 0.35 * math.cos(angle))
            outer_y = center + int(size * 0.35 * math.sin(angle))
            points.append((outer_x, outer_y))
            
            inner_angle = angle + math.radians(36)
            inner_x = center + int(size * 0.15 * math.cos(inner_angle))
            inner_y = center + int(size * 0.15 * math.sin(inner_angle))
            points.append((inner_x, inner_y))
        
        if len(points) >= 3:
            pygame.draw.polygon(overlay, (*GOLD, 240), points)
        
        surface.blit(overlay, (x, y))
    
    def _draw_rainbow_block(self, surface: pygame.Surface, x: int, y: int, size: int) -> None:
        """Gökkuşağı bloğu - animasyonlu renk döngüsü"""
        overlay = pygame.Surface((size, size), pygame.SRCALPHA)
        
        # Hue döngüsü
        hue = (self.animation_time * 90) % 360
        
        # HSV -> RGB
        c = 1.0
        x_val = c * (1 - abs((hue / 60) % 2 - 1))
        
        if hue < 60:
            r, g, b = c, x_val, 0
        elif hue < 120:
            r, g, b = x_val, c, 0
        elif hue < 180:
            r, g, b = 0, c, x_val
        elif hue < 240:
            r, g, b = 0, x_val, c
        elif hue < 300:
            r, g, b = x_val, 0, c
        else:
            r, g, b = c, 0, x_val
        
        color = (int(r * 255), int(g * 255), int(b * 255), 200)
        overlay.fill(color)
        
        # Parlama efekti
        glow = pygame.Surface((size, size), pygame.SRCALPHA)
        pygame.draw.circle(glow, (255, 255, 255, 60), (size // 2, size // 2), size // 3)
        overlay.blit(glow, (0, 0))
        
        surface.blit(overlay, (x, y))
        
        # Neon border
        pygame.draw.rect(surface, color[:3], (x, y, size, size), 2)
    
    # ==========================================
    # PATLAMA EFEKTLERİ
    # ==========================================
    
    def trigger_explosion(self, x: int, y: int, cell_size: int) -> None:
        """Bomba patlaması efekti başlat"""
        self.explosion_effects.append({
            'x': x + cell_size // 2,
            'y': y + cell_size // 2,
            'time': 0.0,
            'max_radius': cell_size * 2,
        })
        
        # Parçacıklar ekle
        import random
        for _ in range(20):
            angle = random.uniform(0, math.pi * 2)
            speed = random.uniform(100, 300)
            self.particle_effects.append({
                'x': x + cell_size // 2,
                'y': y + cell_size // 2,
                'vx': math.cos(angle) * speed,
                'vy': math.sin(angle) * speed,
                'time': 0.0,
                'lifetime': random.uniform(0.3, 0.8),
                'color': random.choice([NEON_ORANGE, (255, 100, 50), GOLD]),
                'size': random.randint(3, 8),
            })
    
    def draw_explosions(self, surface: pygame.Surface) -> None:
        """Patlama efektlerini çiz"""
        for exp in self.explosion_effects:
            progress = exp['time'] / 0.8
            radius = int(exp['max_radius'] * progress)
            alpha = int(255 * (1 - progress))
            
            if radius > 0 and alpha > 0:
                glow = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
                pygame.draw.circle(glow, (*NEON_ORANGE, alpha), (radius, radius), radius)
                pygame.draw.circle(glow, (*GOLD, alpha // 2), (radius, radius), radius // 2)
                surface.blit(glow, (exp['x'] - radius, exp['y'] - radius))
    
    def draw_particles(self, surface: pygame.Surface) -> None:
        """Parçacık efektlerini çiz"""
        for p in self.particle_effects:
            progress = p['time'] / p['lifetime']
            alpha = int(255 * (1 - progress))
            size = int(p['size'] * (1 - progress * 0.5))
            
            if size > 0 and alpha > 0:
                pygame.draw.circle(surface, (*p['color'], alpha), (int(p['x']), int(p['y'])), size)
    
    # ==========================================
    # LEVEL TAMAMLANDI / BAŞARISIZ ANİMASYONLARI
    # ==========================================
    
    def start_level_complete(self, stars: int) -> None:
        """Level tamamlandı animasyonunu başlat"""
        self.level_complete_animation = {
            'time': 0.0,
            'stars': stars,
        }
        
        # Yıldız animasyonları
        for i in range(stars):
            self.star_animations.append({
                'index': i,
                'time': 0.0,
                'delay': i * 0.3,
            })
    
    def start_level_failed(self, reason: str = "") -> None:
        """Level başarısız animasyonunu başlat"""
        self.level_failed_animation = {
            'time': 0.0,
            'reason': reason,
        }
    
    def draw_level_complete_overlay(
        self,
        surface: pygame.Surface,
        stars: int,
        score: int,
        level_name: str,
        lang: str = 'tr',
        objectives: Optional[List[Dict[str, Any]]] = None,
        stats: Optional[List[Tuple[str, str]]] = None,
        rewards: Optional[List[Tuple[str, str]]] = None,
        next_level: Optional[Dict[str, Any]] = None,
        star_conditions: Optional[List[Dict[str, Any]]] = None,
        is_last_level: bool = False,
    ) -> None:
        """Level tamamlandı overlay'i - oyunun game over UI stiline uygun"""
        if not self.level_complete_animation:
            return
        
        # retro_style import (oyunun ana stil modülü)
        try:
            from retro_style import retro_style
        except ImportError:
            retro_style = None
        
        screen_w, screen_h = surface.get_size()
        anim_time = self.level_complete_animation['time']
        
        # Fade-in animasyonu (0-0.4 saniye) - game.py stilinde
        fade_duration = 0.4
        if anim_time < fade_duration:
            fade_alpha = int(240 * (anim_time / fade_duration))
        else:
            fade_alpha = 240
        
        # Gradient overlay (game.py stilinde)
        cache_key = (screen_w, screen_h)
        overlay = self._level_overlay_cache.get(cache_key)
        if overlay is None:
            overlay = pygame.Surface((screen_w, screen_h), pygame.SRCALPHA)
            for y in range(screen_h):
                gradient_alpha = int(240 * 0.8 + 40 * (y / screen_h))
                pygame.draw.line(overlay, (5, 8, 18, min(gradient_alpha, 240)), (0, y), (screen_w, y))
            self._level_overlay_cache[cache_key] = overlay

        if fade_alpha < 240:
            overlay_scaled = overlay.copy()
            overlay_scaled.set_alpha(int(255 * (fade_alpha / 240)))
            surface.blit(overlay_scaled, (0, 0))
        else:
            surface.blit(overlay, (0, 0))
        
        # Panel boyutları (game.py stilinde)
        panel_width = min(max(460, screen_w - 320), screen_w - 220)
        panel_width = max(380, panel_width)
        panel_height = min(max(380, screen_h - 160), screen_h - 80)
        panel_height = max(340, panel_height)
        
        panel_x = (screen_w - panel_width) // 2
        panel_y = (screen_h - panel_height) // 2
        
        # Panel slide-in animasyonu
        if anim_time < 0.3:
            panel_y += int(50 * (1 - anim_time / 0.3))
        
        panel_rect = pygame.Rect(panel_x, panel_y, panel_width, panel_height)
        
        # Panel padding
        pad_x = 32
        inner_left = panel_rect.x + pad_x
        inner_right = panel_rect.right - pad_x
        inner_w = inner_right - inner_left
        
        # Glass panel çizimi (retro_style varsa kullan, yoksa fallback)
        use_retro = False
        if retro_style:
            try:
                # Panel glow efekti
                glow_rect = panel_rect.inflate(24, 24)
                glow_surf = pygame.Surface(glow_rect.size, pygame.SRCALPHA)
                pygame.draw.rect(glow_surf, (*NEON_CYAN, 25), glow_surf.get_rect(), border_radius=20)
                surface.blit(glow_surf, glow_rect.topleft)
                
                # Glass panel
                retro_style.draw_glass_panel(surface, panel_rect, alpha=200, border_color=NEON_CYAN)
                use_retro = True
            except (AttributeError, Exception):
                # Cache hatası veya başka hata durumunda fallback
                pass
        
        if not use_retro:
            # Fallback: premium manuel panel
            # Glow efekti
            glow_rect = panel_rect.inflate(24, 24)
            glow_surf = pygame.Surface(glow_rect.size, pygame.SRCALPHA)
            pygame.draw.rect(glow_surf, (*NEON_CYAN, 20), glow_surf.get_rect(), border_radius=18)
            surface.blit(glow_surf, glow_rect.topleft)
            
            # Panel arka plan (glassmorphism benzeri)
            panel_surf = pygame.Surface((panel_width, panel_height), pygame.SRCALPHA)
            panel_surf.fill((10, 15, 35, 220))
            
            # Üst highlight (cam efekti)
            for i in range(20):
                alpha = int(35 * (1 - i / 20))
                pygame.draw.line(panel_surf, (255, 255, 255, alpha), (0, i), (panel_width, i))
            
            surface.blit(panel_surf, panel_rect.topleft)
            
            # Neon border
            pygame.draw.rect(surface, NEON_CYAN, panel_rect, 2, border_radius=14)
        
        # Üst başlık bandı (tema uyumlu)
        header_h = 88
        header_rect = pygame.Rect(panel_rect.x + 8, panel_rect.y + 8, panel_width - 16, header_h)
        header_surf = pygame.Surface(header_rect.size, pygame.SRCALPHA)
        header_surf.fill((12, 18, 40, 230))
        for i in range(12):
            alpha = int(30 * (1 - i / 12))
            pygame.draw.line(header_surf, (255, 255, 255, alpha), (0, i), (header_rect.width, i))
        surface.blit(header_surf, header_rect.topleft)
        pygame.draw.line(surface, (*NEON_CYAN, 140), (header_rect.x + 10, header_rect.bottom - 2), (header_rect.right - 10, header_rect.bottom - 2), 2)

        # BAŞLIK - premium kısa
        title_text = t('campaign_congrats_title')
        title_color = NEON_CYAN

        if retro_style:
            title_font = retro_style.get_font(40, bold=True)
            subtitle_font = retro_style.get_font(21, bold=False)
        else:
            title_font = self._get_font(40)
            subtitle_font = self._get_font(21)

        title = title_font.render(title_text, True, title_color)
        title_rect = title.get_rect(centerx=header_rect.centerx, top=header_rect.y + 6)

        # Glow efekti
        glow_surf = title_font.render(title_text, True, title_color)
        for dx, dy, a in [(-2, 0, 26), (2, 0, 26), (0, -2, 22), (0, 2, 22)]:
            glow_surf.set_alpha(a)
            surface.blit(glow_surf, (title_rect.x + dx, title_rect.y + dy))
        surface.blit(title, title_rect)

        # ============================================
        # YILDIZ SİSTEMİ (game.py stilinde 3 yıldız)
        # ============================================
        star_size = 40
        star_area_y = header_rect.bottom + 8
        star_spacing = 10
        total_stars = 3
        total_star_width = total_stars * star_size + (total_stars - 1) * star_spacing
        star_start_x = header_rect.centerx - total_star_width // 2

        # Alt başlık (level adı) - yıldızların hemen solunda, aynı hizada
        subtitle = subtitle_font.render(level_name, True, (205, 215, 235))
        subtitle_rect = subtitle.get_rect()
        subtitle_rect.midright = (star_start_x - 8, star_area_y + star_size // 2)
        surface.blit(subtitle, subtitle_rect)
        
        # Yıldız reveal animasyonu
        star_reveal_start = 0.5
        star_reveal_speed = 2.0
        
        if anim_time > star_reveal_start:
            shown_progress = min(stars, (anim_time - star_reveal_start) * star_reveal_speed)
        else:
            shown_progress = 0.0
        
        for i in range(total_stars):
            star_x = star_start_x + i * (star_size + star_spacing)
            star_y = star_area_y
            
            # Bu yıldız için doluluk oranı
            if i < int(shown_progress):
                fill_ratio = 1.0
            elif i < shown_progress:
                fill_ratio = shown_progress - int(shown_progress)
            else:
                fill_ratio = 0.0
            
            # Pop animasyonu
            reveal_time = star_reveal_start + (i / max(0.001, star_reveal_speed))
            t_since = max(0.0, anim_time - reveal_time)
            pop = 0.0
            if fill_ratio > 0.0:
                pop = 0.18 * math.exp(-t_since * 6.0) * math.sin(t_since * 18.0)
            scale = max(0.85, 1.0 + pop)
            glow_intensity = min(1.0, 0.35 + 0.55 * fill_ratio + max(0.0, pop) * 1.5)
            
            self._draw_star_premium(surface, star_x, star_y, star_size, 
                                   fill_ratio=fill_ratio, scale=scale, 
                                   glow_intensity=glow_intensity)
        
        # Yıldız sayısı göstergesi
        rating_y = star_area_y + star_size + 6
        if retro_style:
            rating_font = retro_style.get_font(18, bold=True)
        else:
            rating_font = self._get_font(18)
        
        displayed_rating = min(stars, shown_progress)
        rating_text = f"{int(displayed_rating)} / 3"
        rating_color = GOLD if displayed_rating >= 2.5 else (205, 215, 235)
        
        rating_surf = rating_font.render(rating_text, True, rating_color)
        surface.blit(rating_surf, rating_surf.get_rect(centerx=panel_rect.centerx, top=rating_y))

        # Yıldız ilerleme barı
        bar_w = 220
        bar_h = 6
        bar_x = panel_rect.centerx - bar_w // 2
        bar_y = rating_y + 22
        pygame.draw.rect(surface, (35, 45, 70), (bar_x, bar_y, bar_w, bar_h), border_radius=4)
        fill_ratio = max(0.0, min(1.0, shown_progress / 3.0))
        fill_w = int(bar_w * fill_ratio)
        if fill_w > 0:
            pygame.draw.rect(surface, (*GOLD, 200), (bar_x, bar_y, fill_w, bar_h), border_radius=4)
        
        # ============================================
        # SKOR KARTI (game.py stilinde)
        # ============================================
        score_top = bar_y + 16
        score_rect = pygame.Rect(inner_left, score_top, inner_w, 70)
        
        # Skor arka plan
        score_bg = pygame.Surface(score_rect.size, pygame.SRCALPHA)
        score_bg.fill((8, 12, 28, 220))
        surface.blit(score_bg, score_rect.topleft)
        
        # Skor kenar - neon glow
        pygame.draw.rect(surface, (*NEON_CYAN, 180), score_rect, 2, border_radius=10)
        
        # Skor label
        if retro_style:
            score_label_font = retro_style.get_font(16, bold=True)
            score_value_font = retro_style.get_font(32, bold=True)
        else:
            score_label_font = self._get_font(16)
            score_value_font = self._get_font(32)
        
        score_label = score_label_font.render(t('score'), True, (205, 215, 235))
        surface.blit(score_label, (score_rect.x + 16, score_rect.y + 10))
        
        # Animasyonlu skor
        score_anim_start = 0.3
        score_anim_duration = 1.2
        if anim_time > score_anim_start:
            score_progress = min(1.0, (anim_time - score_anim_start) / score_anim_duration)
            eased_progress = 1 - (1 - score_progress) ** 3
            displayed_score = int(score * eased_progress)
        else:
            displayed_score = 0
        
        score_text = f"{displayed_score:,}"
        if lang == 'tr':
            score_text = score_text.replace(',', '.')
        score_value = score_value_font.render(score_text, True, (255, 255, 255))
        score_value_rect = score_value.get_rect()
        score_value_rect.midright = (score_rect.right - 16, score_rect.centery + 4)
        
        # Gölge
        score_shadow = score_value_font.render(score_text, True, (0, 0, 0))
        score_shadow.set_alpha(100)
        shadow_rect = score_value_rect.copy()
        shadow_rect.x += 2
        shadow_rect.y += 2
        surface.blit(score_shadow, shadow_rect)
        surface.blit(score_value, score_value_rect)
        
        # ============================================
        # DETAYLI PANELLER (Hedefler / İstatistik / Ödüller / Yıldız Koşulları / Sonraki Level)
        # ============================================
        footer_h = 40
        content_top = score_rect.bottom + 10
        content_bottom = panel_rect.bottom - footer_h - 14
        content_height = max(160, content_bottom - content_top)

        # İki kolonlu düzen: solda hedefler + istatistik, sağda ödüller + yıldız koşulları + sonraki level
        col_gap = max(16, int(inner_w * 0.035))
        col_left_w = int(inner_w * 0.48)
        col_right_w = inner_w - col_left_w - col_gap
        left_x = inner_left
        right_x = inner_left + col_left_w + col_gap

        row_gap = 12
        left_total = content_height - row_gap
        right_total = content_height - row_gap * 2

        left_top_h = max(150, int(left_total * 0.58))
        left_bottom_h = max(120, left_total - left_top_h)
        if left_top_h + left_bottom_h > left_total:
            left_bottom_h = max(120, left_total - left_top_h)

        right_top_h = max(120, int(right_total * 0.30))
        right_mid_h = max(120, int(right_total * 0.30))
        right_bottom_h = max(130, right_total - right_top_h - right_mid_h)
        if right_top_h + right_mid_h + right_bottom_h > right_total:
            right_bottom_h = max(130, right_total - right_top_h - right_mid_h)

        left_top_rect = pygame.Rect(left_x, content_top, col_left_w, left_top_h)
        left_mid_rect = pygame.Rect(left_x, left_top_rect.bottom + row_gap, col_left_w, left_bottom_h)

        right_top_rect = pygame.Rect(right_x, content_top, col_right_w, right_top_h)
        right_mid_rect = pygame.Rect(right_x, right_top_rect.bottom + row_gap, col_right_w, right_mid_h)
        right_bottom_rect = pygame.Rect(right_x, right_mid_rect.bottom + row_gap, col_right_w, right_bottom_h)

        if retro_style:
            section_title_font = retro_style.get_font(21, bold=True)
            section_line_font = retro_style.get_font(18, bold=False)
            section_small_font = retro_style.get_font(17, bold=False)
        else:
            section_title_font = self._get_font(21)
            section_line_font = self._get_font(18)
            section_small_font = self._get_font(17)

        muted = UIColors.TEXT_PRIMARY
        muted_dim = UIColors.TEXT_SECONDARY
        ok_color = NEON_LIME

        def wrap_text(text: str, font: pygame.font.Font, max_w: int) -> List[str]:
            if not text:
                return []
            words = text.split(' ')
            lines: List[str] = []
            current = ""
            for word in words:
                test = f"{current} {word}".strip()
                if font.size(test)[0] <= max_w:
                    current = test
                else:
                    if current:
                        lines.append(current)
                    current = word
            if current:
                lines.append(current)
            return lines

        def draw_panel(
            rect: pygame.Rect,
            title: str,
            lines: List[Tuple[str, Optional[bool]]],
            accent: Tuple[int, int, int] = NEON_CYAN,
            icon: Optional[str] = None,
            start_delay: float = 0.0
        ) -> None:
            # Panel arka plan (glass)
            if retro_style:
                retro_style.draw_glass_panel(surface, rect, alpha=200, border_color=accent, glow=False)
            else:
                panel_bg = pygame.Surface(rect.size, pygame.SRCALPHA)
                panel_bg.fill(UIColors.GLASS_BG)
                for i in range(10):
                    alpha = int(22 * (1 - i / 10))
                    pygame.draw.line(panel_bg, (255, 255, 255, alpha), (0, i), (rect.width, i))
                surface.blit(panel_bg, rect.topleft)
                pygame.draw.rect(surface, (*accent, 140), rect, 1, border_radius=10)

            pad = 12
            header_h = 32
            header_rect = pygame.Rect(rect.x + 8, rect.y + 6, rect.width - 16, header_h)
            header_surf = pygame.Surface(header_rect.size, pygame.SRCALPHA)
            header_surf.fill((12, 18, 40, 210))
            surface.blit(header_surf, header_rect.topleft)
            pygame.draw.line(surface, (*accent, 150), (header_rect.x + 6, header_rect.bottom - 1), (header_rect.right - 6, header_rect.bottom - 1), 1)

            title_text = title
            title_surf = section_title_font.render(title_text, True, accent)
            surface.blit(title_surf, (rect.x + pad, header_rect.y + 4))

            x = rect.x + pad
            y = header_rect.bottom + 6
            max_y = rect.bottom - pad
            max_w = rect.width - pad * 2

            line_index = 0
            for line_text, is_ok in lines:
                if y >= max_y:
                    break
                color = ok_color if is_ok is True else (muted_dim if is_ok is False else muted)
                font = section_small_font

                wrap_lines = wrap_text(line_text, font, max_w)
                if not wrap_lines:
                    wrap_lines = [""]

                for sub_idx, chunk in enumerate(wrap_lines):
                    if y >= max_y:
                        break
                    line_surf = font.render(chunk, True, color)

                    line_delay = start_delay + 0.05 * line_index
                    if anim_time < line_delay:
                        line_alpha = 0
                    else:
                        line_alpha = int(255 * min(1.0, (anim_time - line_delay) / 0.25))
                    line_surf.set_alpha(line_alpha)
                    surface.blit(line_surf, (x, y))
                    y += line_surf.get_height() + 4
                    line_index += 1

        # Hedefler
        objective_lines: List[Tuple[str, Optional[bool]]] = []
        for obj in objectives or []:
            text = f"{obj.get('text', '')} ({obj.get('progress', '')})"
            objective_lines.append((text, obj.get('completed', False)))
        draw_panel(left_top_rect, t('campaign_objectives_title'), objective_lines, accent=NEON_LIME, icon=None, start_delay=0.3)

        # İstatistik
        stat_lines: List[Tuple[str, Optional[bool]]] = []
        for label, value in stats or []:
            stat_lines.append((f"{label}: {value}", None))
        draw_panel(left_mid_rect, t('campaign_stats_title'), stat_lines, accent=NEON_CYAN, icon=None, start_delay=0.45)

        # Ödüller
        reward_lines: List[Tuple[str, Optional[bool]]] = []
        for label, value in rewards or []:
            reward_lines.append((f"{label}: {value}", None))
        draw_panel(right_top_rect, t('campaign_rewards_title'), reward_lines, accent=GOLD, icon=None, start_delay=0.6)

        # Yıldız koşulları
        star_lines: List[Tuple[str, Optional[bool]]] = []
        for item in star_conditions or []:
            star_num = item.get('star', 0)
            text = item.get('text', '')
            met = item.get('met', False)
            star_lines.append((f"{star_num}. {text}", met))
        draw_panel(right_mid_rect, t('campaign_star_conditions_title'), star_lines, accent=NEON_ORANGE, icon=None, start_delay=0.75)

        # Sonraki level
        next_lines: List[Tuple[str, Optional[bool]]] = []
        if next_level:
            next_title = next_level.get('title')
            if next_title:
                next_lines.append((next_title, None))
            for line in next_level.get('lines', [])[:5]:
                next_lines.append((f"{line}", None))
        else:
            end_text = t('campaign_complete')
            next_lines.append((end_text, None))
        draw_panel(right_bottom_rect, t('campaign_next_level_title'), next_lines, accent=NEON_MAGENTA, icon=None, start_delay=0.9)

        # Footer kontrol şeridi
        footer_rect = pygame.Rect(panel_rect.x + 12, panel_rect.bottom - footer_h - 6, panel_width - 24, footer_h)
        footer_surf = pygame.Surface(footer_rect.size, pygame.SRCALPHA)
        footer_surf.fill((10, 12, 26, 210))
        surface.blit(footer_surf, footer_rect.topleft)
        pygame.draw.line(surface, (*NEON_CYAN, 100), (footer_rect.x + 10, footer_rect.y + 2), (footer_rect.right - 10, footer_rect.y + 2), 1)

        if retro_style:
            footer_font = retro_style.get_font(16, bold=False)
        else:
            footer_font = self._get_font(16)

        # Tekrar Dene butonu (footer'ın sol tarafı)
        if retro_style:
            btn_vpad = 4
            retry_btn_w = min(160, int(footer_rect.width * 0.35))
            retry_btn_rect = pygame.Rect(
                footer_rect.x + 6,
                footer_rect.y + btn_vpad,
                retry_btn_w,
                footer_rect.height - btn_vpad * 2,
            )
            self._complete_buttons = {'retry': retry_btn_rect}
            _mouse_pos = pygame.mouse.get_pos()
            retro_style.draw_uniform_button(
                surface, retry_btn_rect, t('campaign_retry'),
                sub_text='R', color_code=retro_style.primary,
                state='hover' if retry_btn_rect.collidepoint(_mouse_pos) else 'normal',
            )
            # Kontrol metni sağa hizalı
            footer_text = t('campaign_footer_controls')
            footer_surf_text = footer_font.render(footer_text, True, UIColors.TEXT_SECONDARY)
            text_right = footer_rect.right - 8
            text_rect = footer_surf_text.get_rect()
            text_rect.midright = (text_right, footer_rect.centery)
            surface.blit(footer_surf_text, text_rect)
        else:
            self._complete_buttons = {}
            footer_text = t('campaign_footer_controls')
            footer_surf_text = footer_font.render(footer_text, True, UIColors.TEXT_SECONDARY)
            surface.blit(footer_surf_text, footer_surf_text.get_rect(center=footer_rect.center))

        # ============================================
        # Buton çizimi kaldırıldı (alt kısım temiz kalsın)
        # ============================================
    
    def _draw_star_premium(
        self,
        surface: pygame.Surface,
        x: int,
        y: int,
        size: int,
        fill_ratio: float = 1.0,
        color: Tuple = GOLD,
        empty_color: Tuple = (60, 70, 90),
        scale: float = 1.0,
        glow_intensity: float = 0.6
    ) -> None:
        """Premium yıldız çizimi - game.py stiline uygun"""
        fill_ratio = float(max(0.0, min(1.0, fill_ratio)))
        scale = float(max(0.7, min(1.6, scale)))
        glow_intensity = float(max(0.0, min(1.0, glow_intensity)))
        
        # Merkez
        base_cx = x + size * 0.5
        base_cy = y + size * 0.5
        r_outer = (size * 0.5) * scale
        r_inner = (size * 0.25) * scale
        
        pad = max(6, int(size * 0.18))
        surf_w = int(size * scale) + pad * 2
        surf_h = int(size * scale) + pad * 2
        star_surf = pygame.Surface((surf_w, surf_h), pygame.SRCALPHA)
        
        cx = surf_w * 0.5
        cy = surf_h * 0.5
        
        # Yıldız noktaları
        points = []
        for i in range(10):
            angle = i * math.pi / 5 - math.pi / 2
            r = r_outer if i % 2 == 0 else r_inner
            px = cx + r * math.cos(angle)
            py = cy + r * math.sin(angle)
            points.append((int(px), int(py)))
        
        # Boş yıldız tabanı
        pygame.draw.polygon(star_surf, (*empty_color, 255), points)
        edge = tuple(min(255, c + 35) for c in empty_color)
        pygame.draw.polygon(star_surf, (*edge, 220), points, 1)
        
        if fill_ratio > 0.0:
            filled = pygame.Surface((surf_w, surf_h), pygame.SRCALPHA)
            pygame.draw.polygon(filled, (*color, 255), points)
            
            # Kısmi doluluk: soldan sağa clip
            fill_w = int(surf_w * fill_ratio)
            if fill_w > 0:
                star_surf.blit(filled, (0, 0), area=pygame.Rect(0, 0, fill_w, surf_h))
            
            # Glow efekti
            glow_a1 = int(90 * glow_intensity)
            glow_a2 = int(55 * glow_intensity)
            glow_col = (min(255, color[0] + 40), min(255, color[1] + 40), min(255, color[2] + 40))
            if glow_a2 > 0:
                pygame.draw.polygon(star_surf, (*glow_col, glow_a2), points, 6)
            if glow_a1 > 0:
                pygame.draw.polygon(star_surf, (*glow_col, glow_a1), points, 3)
            
            # Parlak kenar
            pygame.draw.polygon(star_surf, (*glow_col, min(255, 180)), points, 1)
        
        # Ekrana ortalı blit
        dest = star_surf.get_rect(center=(int(base_cx), int(base_cy)))
        surface.blit(star_surf, dest)
    
    def draw_level_failed_overlay(
        self,
        surface: pygame.Surface,
        reason: str,
        lang: str = 'tr'
    ) -> None:
        """Level başarısız overlay'i - oyunun game over UI stiline uygun"""
        if not self.level_failed_animation:
            return
        
        # retro_style import
        try:
            from retro_style import retro_style
        except ImportError:
            retro_style = None
        
        screen_w, screen_h = surface.get_size()
        anim_time = self.level_failed_animation['time']
        
        # Kırmızı renk paleti
        FAIL_RED = UIColors.NEON_RED
        FAIL_DARK = UIColors.TEXT_ERROR
        
        # Fade-in animasyonu
        fade_duration = 0.35
        if anim_time < fade_duration:
            fade_alpha = int(230 * (anim_time / fade_duration))
        else:
            fade_alpha = 230
        
        # Gradient overlay (kırmızımsı tint)
        cache_key = (screen_w, screen_h)
        overlay = self._level_failed_overlay_cache.get(cache_key)
        if overlay is None:
            overlay = pygame.Surface((screen_w, screen_h), pygame.SRCALPHA)
            for y in range(screen_h):
                gradient_alpha = int(230 * 0.75 + 35 * (y / screen_h))
                pygame.draw.line(overlay, (20, 5, 8, min(gradient_alpha, 230)), (0, y), (screen_w, y))
            self._level_failed_overlay_cache[cache_key] = overlay

        if fade_alpha < 230:
            overlay_scaled = overlay.copy()
            overlay_scaled.set_alpha(int(255 * (fade_alpha / 230)))
            surface.blit(overlay_scaled, (0, 0))
        else:
            surface.blit(overlay, (0, 0))
        
        # Panel boyutları
        panel_width = min(max(420, screen_w - 160), screen_w - 80)
        panel_width = max(360, panel_width)
        panel_height = min(max(260, screen_h - 200), screen_h - 100)
        panel_height = max(220, panel_height)
        
        panel_x = (screen_w - panel_width) // 2
        panel_y = (screen_h - panel_height) // 2
        
        # Shake efekti (ilk 0.5 saniyede)
        if anim_time < 0.5:
            shake = int(8 * math.sin(anim_time * 45) * (1 - anim_time / 0.5))
            panel_x += shake
        
        panel_rect = pygame.Rect(panel_x, panel_y, panel_width, panel_height)
        
        # Glass panel çizimi (retro_style varsa kullan, yoksa fallback)
        use_retro = False
        if retro_style:
            try:
                # Panel glow efekti (kırmızı)
                glow_rect = panel_rect.inflate(20, 20)
                glow_surf = pygame.Surface(glow_rect.size, pygame.SRCALPHA)
                pygame.draw.rect(glow_surf, (*FAIL_RED, 20), glow_surf.get_rect(), border_radius=18)
                surface.blit(glow_surf, glow_rect.topleft)
                
                # Glass panel (kırmızı border)
                retro_style.draw_glass_panel(surface, panel_rect, alpha=210, border_color=FAIL_RED)
                use_retro = True
            except (AttributeError, Exception):
                pass
        
        if not use_retro:
            # Fallback: premium manuel panel
            glow_rect = panel_rect.inflate(20, 20)
            glow_surf = pygame.Surface(glow_rect.size, pygame.SRCALPHA)
            pygame.draw.rect(glow_surf, (*FAIL_RED, 15), glow_surf.get_rect(), border_radius=16)
            surface.blit(glow_surf, glow_rect.topleft)
            
            panel_surf = pygame.Surface((panel_width, panel_height), pygame.SRCALPHA)
            panel_surf.fill((25, 12, 15, 225))
            
            # Üst highlight
            for i in range(15):
                alpha = int(25 * (1 - i / 15))
                pygame.draw.line(panel_surf, (255, 200, 200, alpha), (0, i), (panel_width, i))
            
            surface.blit(panel_surf, panel_rect.topleft)
            pygame.draw.rect(surface, FAIL_RED, panel_rect, 2, border_radius=14)
        
        # BAŞLIK - glow efektli
        title_text = t('campaign_failed_title')
        
        if retro_style:
            title_font = retro_style.get_font(48, bold=True)
        else:
            title_font = self._get_font(48)
        
        title = title_font.render(title_text, True, FAIL_RED)
        title_rect = title.get_rect(centerx=panel_rect.centerx, top=panel_rect.y + 28)
        
        # Glow efekti
        glow_surf = title_font.render(title_text, True, FAIL_RED)
        for dx, dy, a in [(-2, 0, 30), (2, 0, 30), (0, -2, 25), (0, 2, 25)]:
            glow_surf.set_alpha(a)
            surface.blit(glow_surf, (title_rect.x + dx, title_rect.y + dy))
        surface.blit(title, title_rect)
        
        # Sebep (varsa)
        if reason:
            if retro_style:
                reason_font = retro_style.get_font(20, bold=False)
            else:
                reason_font = self._get_font(20)
            
            reason_surf = reason_font.render(reason, True, (220, 180, 170))
            reason_rect = reason_surf.get_rect(centerx=panel_rect.centerx, top=title_rect.bottom + 16)
            surface.blit(reason_surf, reason_rect)
        
        # Buton ipuçları + tıklanabilir butonlar
        if anim_time > 0.8:
            hint_text = t('campaign_failed_hint')
            
            if retro_style:
                hint_font = retro_style.get_font(15, bold=False)
            else:
                hint_font = self._get_font(15)
            
            # Butonları panel altına yerleştir
            btn_h = 40
            btn_margin = 10
            btn_gap = 8
            btn_w = (panel_rect.width - btn_margin * 2 - btn_gap) // 2
            btn_y = panel_rect.bottom - btn_h - btn_margin

            retry_btn_rect = pygame.Rect(panel_rect.x + btn_margin, btn_y, btn_w, btn_h)
            menu_btn_rect = pygame.Rect(panel_rect.x + btn_margin + btn_w + btn_gap, btn_y, btn_w, btn_h)
            self._failed_buttons = {'retry': retry_btn_rect, 'menu': menu_btn_rect}

            if retro_style:
                _mouse_pos = pygame.mouse.get_pos()
                retro_style.draw_uniform_button(
                    surface, retry_btn_rect, t('campaign_retry'),
                    sub_text='R', color_code=retro_style.success,
                    state='hover' if retry_btn_rect.collidepoint(_mouse_pos) else 'normal',
                )
                retro_style.draw_uniform_button(
                    surface, menu_btn_rect, t('main_menu'),
                    sub_text='ESC', color_code=retro_style.secondary,
                    state='hover' if menu_btn_rect.collidepoint(_mouse_pos) else 'normal',
                )
            
            # Hint metni butonların üstünde
            hint_surf = hint_font.render(hint_text, True, (160, 145, 145))
            hint_rect = hint_surf.get_rect(centerx=panel_rect.centerx, bottom=btn_y - 6)
            
            # Yanıp sönen efekt
            flash = 0.6 + 0.4 * math.sin(anim_time * 3.5)
            hint_surf.set_alpha(int(255 * flash))
            surface.blit(hint_surf, hint_rect)
        else:
            self._failed_buttons = {}
    
    def _draw_star_shape(self, surface: pygame.Surface, cx: int, cy: int, size: int, color: Tuple) -> None:
        """Yıldız şekli çiz"""
        points = []
        for i in range(5):
            angle = math.radians(i * 72 - 90)
            outer_x = cx + int(size * 0.5 * math.cos(angle))
            outer_y = cy + int(size * 0.5 * math.sin(angle))
            points.append((outer_x, outer_y))
            
            inner_angle = angle + math.radians(36)
            inner_x = cx + int(size * 0.2 * math.cos(inner_angle))
            inner_y = cy + int(size * 0.2 * math.sin(inner_angle))
            points.append((inner_x, inner_y))
        
        if len(points) >= 3:
            pygame.draw.polygon(surface, color, points)


# Global instance
campaign_ui_effects = CampaignUIEffects()
