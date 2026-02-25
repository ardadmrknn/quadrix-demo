"""Campaign Özel Blok Sistemi

Farklı mekaniklere sahip özel blok türleri.
Bu bloklar level'larda engel olarak veya bonus olarak kullanılır.
"""
from __future__ import annotations

import pygame
from typing import Dict, Any, List, Optional, Tuple, TYPE_CHECKING
from dataclasses import dataclass, field
from enum import Enum
import math
import random

if TYPE_CHECKING:
    from board import Board


class SpecialBlockType(Enum):
    """Özel blok türleri"""
    NORMAL = "normal"       # Normal blok (özel değil)
    ICE = "ice"             # Buz bloğu - erimesi gerekir
    LOCKED = "locked"       # Kilitli blok - 2 temizleme gerekir
    BOMB = "bomb"           # Bomba - patlar
    TIMER = "timer"         # Zamanlı - süre dolunca büyür
    STAR = "star"           # Yıldız - bonus puan
    RAINBOW = "rainbow"     # Gökkuşağı - joker renk


@dataclass
class SpecialBlockState:
    """Özel blok durumu"""
    block_type: SpecialBlockType = SpecialBlockType.NORMAL
    layers: int = 1          # Kalan katman sayısı (locked için)
    timer: float = 0.0       # Kalan süre (timer için)
    bonus_points: int = 0    # Bonus puan (star için)
    flash_time: float = 0.0  # Animasyon için


class SpecialBlockManager:
    """Özel blokları yöneten sınıf"""
    
    # Blok renkleri
    BLOCK_COLORS = {
        SpecialBlockType.ICE: (150, 220, 255),      # Açık mavi
        SpecialBlockType.LOCKED: (120, 120, 140),   # Gri-metal
        SpecialBlockType.BOMB: (40, 40, 40),        # Siyah
        SpecialBlockType.TIMER: (255, 100, 100),    # Kırmızı
        SpecialBlockType.STAR: (255, 215, 0),       # Altın
        SpecialBlockType.RAINBOW: (255, 255, 255),  # Beyaz (animasyonlu)
    }
    
    # Blok özellikleri
    BLOCK_PROPERTIES = {
        SpecialBlockType.ICE: {
            'layers': 1,
            'clears_on_adjacent': True,  # Komşu satır temizlenince erir
            'blocks_line_clear': True,   # Satır tamamlamayı engeller
        },
        SpecialBlockType.LOCKED: {
            'layers': 2,
            'clears_on_adjacent': False,
            'blocks_line_clear': True,
        },
        SpecialBlockType.BOMB: {
            'explosion_radius': 3,
            'chain_reaction': True,
            'clears_on_line': True,      # Satır temizlenince patlar
        },
        SpecialBlockType.TIMER: {
            'default_timer': 15.0,       # 15 saniye
            'growth_on_expire': True,
            'growth_amount': 2,          # 2 yeni blok ekler
        },
        SpecialBlockType.STAR: {
            'bonus_points': 500,
            'collectible': True,
        },
        SpecialBlockType.RAINBOW: {
            'wild_card': True,
            'color_cycle_speed': 0.5,    # Saniyede renk değişimi
        },
    }
    
    def __init__(self):
        self.special_blocks: Dict[Tuple[int, int], SpecialBlockState] = {}
        self.animation_time = 0.0
        self.pending_explosions: List[Tuple[int, int]] = []
        self.cleared_special_count: Dict[str, int] = {}
    
    def reset(self) -> None:
        """Manager'ı sıfırla"""
        self.special_blocks.clear()
        self.pending_explosions.clear()
        self.cleared_special_count.clear()
        self.animation_time = 0.0
    
    def add_special_block(
        self, 
        x: int, 
        y: int, 
        block_type: SpecialBlockType,
        **kwargs
    ) -> None:
        """Özel blok ekle"""
        props = self.BLOCK_PROPERTIES.get(block_type, {})
        
        state = SpecialBlockState(
            block_type=block_type,
            layers=props.get('layers', 1),
            timer=props.get('default_timer', 0.0),
            bonus_points=props.get('bonus_points', 0),
        )
        
        # Özel parametreler
        if 'timer' in kwargs:
            state.timer = kwargs['timer']
        if 'layers' in kwargs:
            state.layers = kwargs['layers']
        
        self.special_blocks[(x, y)] = state
    
    def get_special_block(self, x: int, y: int) -> Optional[SpecialBlockState]:
        """Koordinattaki özel bloğu al"""
        return self.special_blocks.get((x, y))
    
    def is_special(self, x: int, y: int) -> bool:
        """Koordinatta özel blok var mı?"""
        state = self.special_blocks.get((x, y))
        return state is not None and state.block_type != SpecialBlockType.NORMAL
    
    def get_block_type(self, x: int, y: int) -> SpecialBlockType:
        """Koordinattaki blok türünü al"""
        state = self.special_blocks.get((x, y))
        return state.block_type if state else SpecialBlockType.NORMAL
    
    def update(self, dt: float, board: 'Board') -> Dict[str, Any]:
        """Özel blokları güncelle
        
        Returns:
            Dict with events: explosions, timer_expires, etc.
        """
        self.animation_time += dt
        events = {
            'explosions': [],
            'timer_expires': [],
            'blocks_cleared': [],
            'points_earned': 0,
        }
        
        # Timer blokları güncelle
        expired_timers = []
        for (x, y), state in list(self.special_blocks.items()):
            if state.block_type == SpecialBlockType.TIMER:
                state.timer -= dt
                if state.timer <= 0:
                    expired_timers.append((x, y))
                    events['timer_expires'].append((x, y))
        
        # Süresi dolan timer'ları işle
        for x, y in expired_timers:
            self._handle_timer_expire(x, y, board)
        
        # Bekleyen patlamaları işle
        if self.pending_explosions:
            for x, y in self.pending_explosions[:]:
                explosion_result = self._process_explosion(x, y, board)
                events['explosions'].append(explosion_result)
            self.pending_explosions.clear()
        
        return events
    
    def on_line_cleared(
        self, 
        cleared_rows: List[int], 
        board: 'Board'
    ) -> Dict[str, Any]:
        """Satır temizlendiğinde çağrılır
        
        Returns:
            Dict with: points_earned, special_cleared, explosions_triggered
        """
        result = {
            'points_earned': 0,
            'special_cleared': {},
            'explosions_triggered': [],
            'ice_melted': [],
        }
        
        # Temizlenen satırlardaki özel blokları işle
        for row in cleared_rows:
            for col in range(board.width):
                state = self.special_blocks.get((col, row))
                if not state:
                    continue
                
                block_type = state.block_type
                
                if block_type == SpecialBlockType.BOMB:
                    # Bomba patlaması planla
                    self.pending_explosions.append((col, row))
                    result['explosions_triggered'].append((col, row))
                
                elif block_type == SpecialBlockType.STAR:
                    # Yıldız toplandı
                    result['points_earned'] += state.bonus_points
                    self._increment_cleared_count('star')
                
                elif block_type in (SpecialBlockType.ICE, SpecialBlockType.LOCKED):
                    # Layer azalt
                    state.layers -= 1
                    if state.layers <= 0:
                        self._increment_cleared_count(block_type.value)
                        result['special_cleared'][block_type.value] = \
                            result['special_cleared'].get(block_type.value, 0) + 1
                        del self.special_blocks[(col, row)]
                    else:
                        state.flash_time = 0.3  # Flash animasyonu
        
        # Komşu satırlardaki buz bloklarını erit
        adjacent_rows = set()
        for row in cleared_rows:
            if row > 0:
                adjacent_rows.add(row - 1)
            if row < board.height - 1:
                adjacent_rows.add(row + 1)
        
        for row in adjacent_rows:
            if row in cleared_rows:
                continue
            for col in range(board.width):
                state = self.special_blocks.get((col, row))
                if state and state.block_type == SpecialBlockType.ICE:
                    props = self.BLOCK_PROPERTIES[SpecialBlockType.ICE]
                    if props.get('clears_on_adjacent', False):
                        state.layers -= 1
                        if state.layers <= 0:
                            result['ice_melted'].append((col, row))
                            self._increment_cleared_count('ice')
                            del self.special_blocks[(col, row)]
                        else:
                            state.flash_time = 0.3
        
        return result
    
    def _process_explosion(
        self, 
        x: int, 
        y: int, 
        board: 'Board'
    ) -> Dict[str, Any]:
        """Bomba patlamasını işle"""
        props = self.BLOCK_PROPERTIES[SpecialBlockType.BOMB]
        radius = props.get('explosion_radius', 3)
        half_radius = radius // 2
        
        cleared_cells = []
        chain_explosions = []
        
        for dx in range(-half_radius, half_radius + 1):
            for dy in range(-half_radius, half_radius + 1):
                nx, ny = x + dx, y + dy
                
                if 0 <= nx < board.width and 0 <= ny < board.height:
                    # Hücreyi temizle
                    if board.grid[ny][nx] is not None:
                        cleared_cells.append((nx, ny))
                        board.grid[ny][nx] = None
                    
                    # Zincir reaksiyonu kontrolü
                    state = self.special_blocks.get((nx, ny))
                    if state and state.block_type == SpecialBlockType.BOMB:
                        if (nx, ny) != (x, y) and props.get('chain_reaction', False):
                            chain_explosions.append((nx, ny))
                    
                    # Bu koordinattaki özel bloğu kaldır
                    if (nx, ny) in self.special_blocks:
                        del self.special_blocks[(nx, ny)]
        
        # Zincir patlamalarını planla
        for pos in chain_explosions:
            if pos not in self.pending_explosions:
                self.pending_explosions.append(pos)
        
        self._increment_cleared_count('bomb')
        
        return {
            'position': (x, y),
            'cleared_cells': cleared_cells,
            'chain_count': len(chain_explosions),
        }
    
    def _handle_timer_expire(self, x: int, y: int, board: 'Board') -> None:
        """Timer süresi dolduğunda"""
        props = self.BLOCK_PROPERTIES[SpecialBlockType.TIMER]
        
        if props.get('growth_on_expire', False):
            growth = props.get('growth_amount', 2)
            
            # Altına bloklar ekle
            for i in range(1, growth + 1):
                new_y = y + i
                if new_y < board.height and board.grid[new_y][x] is None:
                    # Yeni timer blok oluştur
                    board.grid[new_y][x] = (255, 100, 100)  # Kırmızı
                    self.add_special_block(
                        x, new_y, 
                        SpecialBlockType.TIMER,
                        timer=props.get('default_timer', 15.0)
                    )
        
        # Orijinal timer'ı kaldır
        if (x, y) in self.special_blocks:
            del self.special_blocks[(x, y)]
    
    def _increment_cleared_count(self, block_type: str) -> None:
        """Temizlenen blok sayısını artır"""
        self.cleared_special_count[block_type] = \
            self.cleared_special_count.get(block_type, 0) + 1
    
    def get_cleared_count(self, block_type: str) -> int:
        """Temizlenen blok sayısını al"""
        return self.cleared_special_count.get(block_type, 0)
    
    def shift_blocks_down(self, cleared_rows: List[int]) -> None:
        """Temizlenen satırların üstündeki blokları aşağı kaydır"""
        new_blocks = {}
        
        for (x, y), state in self.special_blocks.items():
            # Bu satır temizlendiyse atla
            if y in cleared_rows:
                continue
            
            # Kaç satır aşağı kayacak?
            shift = sum(1 for row in cleared_rows if row > y)
            new_y = y + shift
            
            new_blocks[(x, new_y)] = state
        
        self.special_blocks = new_blocks
    
    def draw_special_overlay(
        self, 
        surface: pygame.Surface,
        x: int, 
        y: int, 
        cell_size: int,
        state: SpecialBlockState
    ) -> None:
        """Özel blok overlay'ini çiz"""
        screen_x = x * cell_size
        screen_y = y * cell_size
        
        block_type = state.block_type
        
        if block_type == SpecialBlockType.ICE:
            self._draw_ice_overlay(surface, screen_x, screen_y, cell_size, state)
        elif block_type == SpecialBlockType.LOCKED:
            self._draw_locked_overlay(surface, screen_x, screen_y, cell_size, state)
        elif block_type == SpecialBlockType.BOMB:
            self._draw_bomb_overlay(surface, screen_x, screen_y, cell_size)
        elif block_type == SpecialBlockType.TIMER:
            self._draw_timer_overlay(surface, screen_x, screen_y, cell_size, state)
        elif block_type == SpecialBlockType.STAR:
            self._draw_star_overlay(surface, screen_x, screen_y, cell_size)
        elif block_type == SpecialBlockType.RAINBOW:
            self._draw_rainbow_overlay(surface, screen_x, screen_y, cell_size)
    
    def _draw_ice_overlay(
        self, surface: pygame.Surface, 
        x: int, y: int, size: int, 
        state: SpecialBlockState
    ) -> None:
        """Buz bloğu overlay'i"""
        # Buz rengi overlay
        ice_surface = pygame.Surface((size, size), pygame.SRCALPHA)
        alpha = 180 if state.layers > 0 else 100
        ice_surface.fill((150, 220, 255, alpha))
        surface.blit(ice_surface, (x, y))
        
        # Çapraz çizgiler (kar kristali efekti)
        line_color = (200, 240, 255)
        padding = size // 6
        pygame.draw.line(surface, line_color, 
                        (x + padding, y + padding), 
                        (x + size - padding, y + size - padding), 1)
        pygame.draw.line(surface, line_color, 
                        (x + size - padding, y + padding), 
                        (x + padding, y + size - padding), 1)
        
        # Flash animasyonu
        if state.flash_time > 0:
            flash_alpha = int(255 * (state.flash_time / 0.3))
            flash_surf = pygame.Surface((size, size), pygame.SRCALPHA)
            flash_surf.fill((255, 255, 255, flash_alpha))
            surface.blit(flash_surf, (x, y))
    
    def _draw_locked_overlay(
        self, surface: pygame.Surface, 
        x: int, y: int, size: int,
        state: SpecialBlockState
    ) -> None:
        """Kilitli blok overlay'i"""
        # Metal rengi overlay
        lock_surface = pygame.Surface((size, size), pygame.SRCALPHA)
        lock_surface.fill((100, 100, 120, 200))
        surface.blit(lock_surface, (x, y))
        
        # Zincir çizgileri
        chain_color = (80, 80, 90)
        mid = size // 2
        
        # Yatay zincir
        pygame.draw.line(surface, chain_color, (x, y + mid), (x + size, y + mid), 2)
        # Dikey zincir
        pygame.draw.line(surface, chain_color, (x + mid, y), (x + mid, y + size), 2)
        
        # Layer sayısı
        if state.layers > 1:
            font = pygame.font.Font(None, size // 2)
            text = font.render(str(state.layers), True, (255, 200, 100))
            text_rect = text.get_rect(center=(x + mid, y + mid))
            surface.blit(text, text_rect)
    
    def _draw_bomb_overlay(
        self, surface: pygame.Surface,
        x: int, y: int, size: int
    ) -> None:
        """Bomba bloğu overlay'i"""
        center_x = x + size // 2
        center_y = y + size // 2
        radius = size // 3
        
        # Bomba gövdesi
        pygame.draw.circle(surface, (40, 40, 40), (center_x, center_y), radius)
        pygame.draw.circle(surface, (60, 60, 60), (center_x, center_y), radius, 2)
        
        # Fitil
        fuse_start = (center_x, center_y - radius)
        fuse_end = (center_x + radius // 2, center_y - radius - 5)
        pygame.draw.line(surface, (139, 90, 43), fuse_start, fuse_end, 2)
        
        # Kıvılcım (animasyonlu)
        spark_phase = (self.animation_time * 5) % 1.0
        if spark_phase < 0.5:
            spark_color = (255, 200, 50)
        else:
            spark_color = (255, 100, 50)
        pygame.draw.circle(surface, spark_color, fuse_end, 3)
    
    def _draw_timer_overlay(
        self, surface: pygame.Surface,
        x: int, y: int, size: int,
        state: SpecialBlockState
    ) -> None:
        """Zamanlı blok overlay'i"""
        # Kırmızı overlay
        timer_surface = pygame.Surface((size, size), pygame.SRCALPHA)
        
        # Süreye göre renk (yeşil->sarı->kırmızı)
        remaining_ratio = max(0, min(1, state.timer / 15.0))
        if remaining_ratio > 0.5:
            color = (100, 200, 100, 150)  # Yeşil
        elif remaining_ratio > 0.2:
            color = (255, 200, 50, 180)   # Sarı
        else:
            color = (255, 80, 80, 200)    # Kırmızı
        
        timer_surface.fill(color)
        surface.blit(timer_surface, (x, y))
        
        # Süre göstergesi
        font = pygame.font.Font(None, size // 2)
        time_text = str(int(state.timer))
        text = font.render(time_text, True, (255, 255, 255))
        text_rect = text.get_rect(center=(x + size // 2, y + size // 2))
        surface.blit(text, text_rect)
    
    def _draw_star_overlay(
        self, surface: pygame.Surface,
        x: int, y: int, size: int
    ) -> None:
        """Yıldız bloğu overlay'i"""
        center_x = x + size // 2
        center_y = y + size // 2
        
        # Parıltı efekti (animasyonlu)
        glow_phase = math.sin(self.animation_time * 3) * 0.3 + 0.7
        glow_radius = int(size * 0.6 * glow_phase)
        
        glow_surface = pygame.Surface((size, size), pygame.SRCALPHA)
        pygame.draw.circle(glow_surface, (255, 215, 0, 100), 
                          (size // 2, size // 2), glow_radius)
        surface.blit(glow_surface, (x, y))
        
        # Yıldız şekli (basit)
        star_color = (255, 215, 0)
        points = []
        for i in range(5):
            angle = math.radians(i * 72 - 90)
            outer_x = center_x + int(size * 0.35 * math.cos(angle))
            outer_y = center_y + int(size * 0.35 * math.sin(angle))
            points.append((outer_x, outer_y))
            
            inner_angle = angle + math.radians(36)
            inner_x = center_x + int(size * 0.15 * math.cos(inner_angle))
            inner_y = center_y + int(size * 0.15 * math.sin(inner_angle))
            points.append((inner_x, inner_y))
        
        if len(points) >= 3:
            pygame.draw.polygon(surface, star_color, points)
    
    def _draw_rainbow_overlay(
        self, surface: pygame.Surface,
        x: int, y: int, size: int
    ) -> None:
        """Gökkuşağı bloğu overlay'i (animasyonlu renk)"""
        # Renk döngüsü
        hue = (self.animation_time * 60) % 360
        
        # HSV -> RGB dönüşümü (basit)
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
        
        rainbow_surface = pygame.Surface((size, size), pygame.SRCALPHA)
        rainbow_surface.fill(color)
        surface.blit(rainbow_surface, (x, y))


def create_level_special_blocks(
    level_config: Dict[str, Any],
    board_width: int,
    board_height: int
) -> SpecialBlockManager:
    """Level konfigürasyonuna göre özel bloklar oluştur"""
    manager = SpecialBlockManager()
    
    special_configs = level_config.get('special_blocks', [])
    
    for config in special_configs:
        block_type_str = config.get('type', 'ice')
        count = config.get('count', 0)
        spawn_chance = config.get('spawn_chance', 0.1)
        
        # String'i enum'a çevir
        try:
            block_type = SpecialBlockType(block_type_str)
        except ValueError:
            continue
        
        # Rastgele pozisyonlara yerleştir (alt yarıda)
        available_positions = []
        for y in range(board_height // 2, board_height - 2):
            for x in range(board_width):
                available_positions.append((x, y))
        
        random.shuffle(available_positions)
        
        for i in range(min(count, len(available_positions))):
            x, y = available_positions[i]
            manager.add_special_block(x, y, block_type, **config)
    
    return manager
