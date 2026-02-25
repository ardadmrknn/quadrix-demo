"""Campaign Power-up/Booster Sistemi

Oyuncuların level'larda kullanabileceği güçlendiriciler.
Her level başında sınırlı sayıda power-up kullanılabilir.
"""
from __future__ import annotations

import pygame
from typing import Dict, Any, List, Optional, Tuple, Callable, TYPE_CHECKING
from dataclasses import dataclass, field
from enum import Enum
import math

if TYPE_CHECKING:
    from board import Board
    from campaign.campaign_mode import CampaignMode


class PowerUpType(Enum):
    """Power-up türleri"""
    LINE_BOMB = "line_bomb"           # Alt satırı patlatır
    TIME_FREEZE = "time_freeze"       # Zamanı dondurur
    SLOW_DOWN = "slow_down"           # Blok düşüşünü yavaşlatır
    SHUFFLE = "shuffle"               # Tahtadaki blokları karıştırır
    CLEAR_COLUMN = "clear_column"     # Bir sütunu temizler
    SCORE_BOOST = "score_boost"       # 2x skor çarpanı
    # Gelecekte eklenecek:
    # PREVIEW_PLUS = "preview_plus"   # Ekstra önizleme
    # WILD_PIECE = "wild_piece"       # Sonraki parça istediğin şekil


@dataclass
class PowerUpConfig:
    """Power-up konfigürasyonu"""
    power_type: PowerUpType
    name: Dict[str, str]
    description: Dict[str, str]
    duration: float = 0.0        # Geçerlilik süresi (0 = anlık)
    cost: int = 100              # XP maliyeti
    cooldown: float = 0.0        # Tekrar kullanım bekleme süresi
    max_per_level: int = 1       # Level başına max kullanım


# Power-up tanımları
POWER_UPS: Dict[PowerUpType, PowerUpConfig] = {
    PowerUpType.LINE_BOMB: PowerUpConfig(
        power_type=PowerUpType.LINE_BOMB,
        name={"tr": "Satir Bombasi", "en": "Line Bomb"},
        description={
            "tr": "En alt dolu satiri patlatir",
            "en": "Destroys the bottom filled row"
        },
        cost=50,
        max_per_level=2,
    ),
    PowerUpType.TIME_FREEZE: PowerUpConfig(
        power_type=PowerUpType.TIME_FREEZE,
        name={"tr": "Zaman Dondurma", "en": "Time Freeze"},
        description={
            "tr": "5 saniye zaman sayaci durur",
            "en": "Timer stops for 5 seconds"
        },
        duration=5.0,
        cost=75,
        max_per_level=1,
    ),
    PowerUpType.SLOW_DOWN: PowerUpConfig(
        power_type=PowerUpType.SLOW_DOWN,
        name={"tr": "Yavaslatma", "en": "Slow Down"},
        description={
            "tr": "10 saniye bloklar yavas duser",
            "en": "Blocks fall slower for 10 seconds"
        },
        duration=10.0,
        cost=60,
        max_per_level=2,
    ),
    PowerUpType.SHUFFLE: PowerUpConfig(
        power_type=PowerUpType.SHUFFLE,
        name={"tr": "Karistirma", "en": "Shuffle"},
        description={
            "tr": "Tahtadaki bloklari yeniden duzenler",
            "en": "Rearranges blocks on the board"
        },
        cost=100,
        max_per_level=1,
    ),
    PowerUpType.CLEAR_COLUMN: PowerUpConfig(
        power_type=PowerUpType.CLEAR_COLUMN,
        name={"tr": "Sutun Temizle", "en": "Clear Column"},
        description={
            "tr": "Secilen sutunu tamamen temizler",
            "en": "Clears the selected column completely"
        },
        cost=80,
        max_per_level=1,
    ),
    PowerUpType.SCORE_BOOST: PowerUpConfig(
        power_type=PowerUpType.SCORE_BOOST,
        name={"tr": "Skor Artisi", "en": "Score Boost"},
        description={
            "tr": "15 saniye 2x skor kazanirsin",
            "en": "Earn 2x score for 15 seconds"
        },
        duration=15.0,
        cost=70,
        max_per_level=2,
    ),
}


@dataclass
class ActivePowerUp:
    """Aktif power-up durumu"""
    power_type: PowerUpType
    remaining_time: float
    effect_multiplier: float = 1.0


class PowerUpManager:
    """Power-up yönetici sınıfı"""
    
    def __init__(self):
        self.available_power_ups: Dict[PowerUpType, int] = {}  # Kalan kullanım hakkı
        self.active_power_ups: List[ActivePowerUp] = []        # Aktif güçlendiriciler
        self.cooldowns: Dict[PowerUpType, float] = {}          # Cooldown süreleri
        self.used_count: Dict[PowerUpType, int] = {}           # Kullanım sayısı
        
        # UI state
        self.selected_power_up: Optional[PowerUpType] = None
        self.awaiting_target: bool = False  # Hedef seçimi bekleniyor mu?
        
        # Efektler
        self.time_frozen = False
        self.slow_down_active = False
        self.score_multiplier = 1.0
        
    def reset(self) -> None:
        """Yeni level için sıfırla"""
        self.available_power_ups.clear()
        self.active_power_ups.clear()
        self.cooldowns.clear()
        self.used_count.clear()
        self.selected_power_up = None
        self.awaiting_target = False
        self.time_frozen = False
        self.slow_down_active = False
        self.score_multiplier = 1.0
    
    def set_available_power_ups(self, power_ups: List[PowerUpType]) -> None:
        """Level için kullanılabilir power-up'ları ayarla"""
        for ptype in power_ups:
            config = POWER_UPS.get(ptype)
            if config:
                self.available_power_ups[ptype] = config.max_per_level
    
    def grant_power_up(self, power_type: PowerUpType, count: int = 1) -> None:
        """Power-up ekle"""
        current = self.available_power_ups.get(power_type, 0)
        self.available_power_ups[power_type] = current + count
    
    def can_use(self, power_type: PowerUpType) -> Tuple[bool, str]:
        """Power-up kullanılabilir mi?"""
        # Stok kontrolü
        if self.available_power_ups.get(power_type, 0) <= 0:
            return False, "Kalan hak yok"
        
        # Cooldown kontrolü
        if self.cooldowns.get(power_type, 0) > 0:
            return False, "Bekleme suresi"
        
        # Zaten aktif mi?
        for active in self.active_power_ups:
            if active.power_type == power_type:
                return False, "Zaten aktif"
        
        return True, ""
    
    def use_power_up(
        self, 
        power_type: PowerUpType, 
        game: 'CampaignMode',
        target: Optional[Any] = None
    ) -> bool:
        """Power-up kullan"""
        can_use, reason = self.can_use(power_type)
        if not can_use:
            return False
        
        config = POWER_UPS.get(power_type)
        if not config:
            return False
        
        # Stoktan düş
        self.available_power_ups[power_type] -= 1
        self.used_count[power_type] = self.used_count.get(power_type, 0) + 1
        
        # Efekti uygula
        success = self._apply_effect(power_type, game, target)
        
        if success and config.duration > 0:
            # Süreli power-up
            self.active_power_ups.append(ActivePowerUp(
                power_type=power_type,
                remaining_time=config.duration,
            ))
        
        # Cooldown başlat
        if config.cooldown > 0:
            self.cooldowns[power_type] = config.cooldown
        
        return success
    
    def _apply_effect(
        self, 
        power_type: PowerUpType, 
        game: 'CampaignMode',
        target: Optional[Any] = None
    ) -> bool:
        """Power-up efektini uygula"""
        board = game.board
        
        if power_type == PowerUpType.LINE_BOMB:
            return self._effect_line_bomb(board)
        
        elif power_type == PowerUpType.TIME_FREEZE:
            self.time_frozen = True
            return True
        
        elif power_type == PowerUpType.SLOW_DOWN:
            self.slow_down_active = True
            return True
        
        elif power_type == PowerUpType.SHUFFLE:
            return self._effect_shuffle(board)
        
        elif power_type == PowerUpType.CLEAR_COLUMN:
            if isinstance(target, int) and 0 <= target < board.width:
                return self._effect_clear_column(board, target)
            return False
        
        elif power_type == PowerUpType.SCORE_BOOST:
            self.score_multiplier = 2.0
            return True
        
        return False
    
    def _effect_line_bomb(self, board: 'Board') -> bool:
        """En alt dolu satırı patlat"""
        # En alt dolu satırı bul
        for y in range(board.height - 1, -1, -1):
            if any(board.grid[y][x] is not None for x in range(board.width)):
                # Bu satırı temizle
                for x in range(board.width):
                    board.grid[y][x] = None
                
                # Üstteki satırları aşağı kaydır
                for row in range(y, 0, -1):
                    board.grid[row] = board.grid[row - 1][:]
                board.grid[0] = [None] * board.width
                
                board.lines_cleared += 1
                return True
        
        return False
    
    def _effect_shuffle(self, board: 'Board') -> bool:
        """Tahtadaki blokları yeniden düzenle (boşlukları doldur)"""
        import random
        
        # Tüm blokları topla
        all_blocks = []
        for y in range(board.height):
            for x in range(board.width):
                if board.grid[y][x] is not None:
                    all_blocks.append(board.grid[y][x])
                    board.grid[y][x] = None
        
        if not all_blocks:
            return False
        
        # Blokları alttan başlayarak sıkıştır
        random.shuffle(all_blocks)
        
        block_index = 0
        for y in range(board.height - 1, -1, -1):
            for x in range(board.width):
                if block_index < len(all_blocks):
                    board.grid[y][x] = all_blocks[block_index]
                    block_index += 1
        
        return True
    
    def _effect_clear_column(self, board: 'Board', column: int) -> bool:
        """Belirtilen sütunu temizle"""
        cleared_any = False
        
        for y in range(board.height):
            if board.grid[y][column] is not None:
                board.grid[y][column] = None
                cleared_any = True
        
        if cleared_any:
            # Gravity uygula - her satırı aşağı kaydır
            # Her sütun için ayrı ayrı
            pass  # Board'un kendi gravity'si halleder
        
        return cleared_any
    
    def update(self, dt: float) -> Dict[str, Any]:
        """Aktif power-up'ları güncelle"""
        events = {
            'expired': [],
            'time_frozen': self.time_frozen,
            'slow_down': self.slow_down_active,
            'score_multiplier': self.score_multiplier,
        }
        
        # Cooldown güncelle
        for ptype in list(self.cooldowns.keys()):
            self.cooldowns[ptype] -= dt
            if self.cooldowns[ptype] <= 0:
                del self.cooldowns[ptype]
        
        # Aktif power-up'ları güncelle
        expired = []
        for active in self.active_power_ups:
            active.remaining_time -= dt
            if active.remaining_time <= 0:
                expired.append(active)
        
        # Süresi dolmuşları kaldır ve efektleri iptal et
        for exp in expired:
            self.active_power_ups.remove(exp)
            events['expired'].append(exp.power_type)
            
            # Efekt iptal
            if exp.power_type == PowerUpType.TIME_FREEZE:
                self.time_frozen = False
            elif exp.power_type == PowerUpType.SLOW_DOWN:
                self.slow_down_active = False
            elif exp.power_type == PowerUpType.SCORE_BOOST:
                self.score_multiplier = 1.0
        
        return events
    
    def get_speed_modifier(self) -> float:
        """Hız çarpanını döndür (slow down için)"""
        if self.slow_down_active:
            return 0.5  # Yarı hız
        return 1.0
    
    def get_score_modifier(self) -> float:
        """Skor çarpanını döndür"""
        return self.score_multiplier
    
    def is_time_frozen(self) -> bool:
        """Zaman donmuş mu?"""
        return self.time_frozen
    
    def get_available_list(self) -> List[Tuple[PowerUpType, int]]:
        """Kullanılabilir power-up listesi"""
        result = []
        for ptype, count in self.available_power_ups.items():
            if count > 0:
                result.append((ptype, count))
        return result
    
    def draw_power_up_bar(
        self, 
        surface: pygame.Surface, 
        x: int, 
        y: int, 
        width: int,
        lang: str = 'tr'
    ) -> List[Tuple[pygame.Rect, PowerUpType]]:
        """Power-up barını çiz ve tıklanabilir alanları döndür"""
        clickable_areas = []
        
        available = self.get_available_list()
        if not available:
            return clickable_areas
        
        # Arka plan
        bar_height = 50
        bar_rect = pygame.Rect(x, y, width, bar_height)
        pygame.draw.rect(surface, (30, 35, 50), bar_rect, border_radius=8)
        pygame.draw.rect(surface, (60, 70, 90), bar_rect, 2, border_radius=8)
        
        # Power-up ikonları
        icon_size = 40
        padding = 10
        start_x = x + padding
        
        for i, (ptype, count) in enumerate(available):
            config = POWER_UPS.get(ptype)
            if not config:
                continue
            
            icon_x = start_x + i * (icon_size + padding)
            icon_y = y + (bar_height - icon_size) // 2
            icon_rect = pygame.Rect(icon_x, icon_y, icon_size, icon_size)
            
            # Seçili mi?
            is_selected = (self.selected_power_up == ptype)
            
            # Kullanılabilir mi?
            can_use, _ = self.can_use(ptype)
            
            # İkon arka planı
            if is_selected:
                bg_color = (100, 200, 100)
            elif can_use:
                bg_color = (50, 60, 80)
            else:
                bg_color = (40, 40, 50)
            
            pygame.draw.rect(surface, bg_color, icon_rect, border_radius=6)
            
            # İkon sembolü (basit)
            symbols = {
                PowerUpType.LINE_BOMB: "B",
                PowerUpType.TIME_FREEZE: "T",
                PowerUpType.SLOW_DOWN: "S",
                PowerUpType.SHUFFLE: "K",
                PowerUpType.CLEAR_COLUMN: "C",
                PowerUpType.SCORE_BOOST: "X",
            }
            symbol = symbols.get(ptype, "?")
            
            font = pygame.font.Font(None, 28)
            text = font.render(symbol, True, (255, 255, 255))
            text_rect = text.get_rect(center=icon_rect.center)
            surface.blit(text, text_rect)
            
            # Sayı badge
            if count > 1:
                badge_font = pygame.font.Font(None, 18)
                badge = badge_font.render(str(count), True, (255, 255, 255))
                badge_rect = badge.get_rect(bottomright=(icon_rect.right - 2, icon_rect.bottom - 2))
                pygame.draw.circle(surface, (200, 50, 50), badge_rect.center, 8)
                surface.blit(badge, badge_rect)
            
            clickable_areas.append((icon_rect, ptype))
        
        return clickable_areas
    
    def draw_active_effects(
        self, 
        surface: pygame.Surface,
        x: int,
        y: int,
        lang: str = 'tr'
    ) -> None:
        """Aktif efektleri göster"""
        if not self.active_power_ups:
            return
        
        font = pygame.font.Font(None, 20)
        current_y = y
        
        for active in self.active_power_ups:
            config = POWER_UPS.get(active.power_type)
            if not config:
                continue
            
            name = config.name.get(lang, config.name.get('en', ''))
            remaining = int(active.remaining_time)
            
            text = f"{name}: {remaining}s"
            surf = font.render(text, True, (100, 255, 100))
            surface.blit(surf, (x, current_y))
            current_y += 20


def get_power_up_config(power_type: PowerUpType) -> Optional[PowerUpConfig]:
    """Power-up konfigürasyonunu al"""
    return POWER_UPS.get(power_type)


def get_all_power_ups() -> List[PowerUpConfig]:
    """Tüm power-up'ları döndür"""
    return list(POWER_UPS.values())
