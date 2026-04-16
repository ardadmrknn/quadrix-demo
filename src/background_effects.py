"""Reusable animated background layers."""
from __future__ import annotations

import random
import sys
from dataclasses import dataclass

import pygame

# macOS detection - SRCALPHA surface'ler bazen crash yapabiliyor
_IS_MACOS = sys.platform == 'darwin'

# Jelly renderer'ı import et
try:
    from renderers.jelly_renderer import draw_jelly_block
    _HAS_JELLY = True
except ImportError:
    _HAS_JELLY = False
    draw_jelly_block = None


_TETROMINO_SHAPES = [
    [(0, 0), (1, 0), (2, 0), (3, 0)],  # I
    [(0, 0), (1, 0), (0, 1), (1, 1)],  # O
    [(0, 0), (1, 0), (2, 0), (1, 1)],  # T
    [(0, 0), (0, 1), (0, 2), (1, 2)],  # J
    [(1, 0), (1, 1), (1, 2), (0, 2)],  # L
    [(0, 1), (1, 1), (1, 0), (2, 0)],  # S
    [(0, 0), (1, 0), (1, 1), (2, 1)],  # Z
]

# Oyundaki gerçek tetromino renkleri (constants.py'den)
_TETROMINO_COLORS = [
    (0, 255, 221),    # CYAN - I
    (255, 200, 40),   # YELLOW - O
    (190, 80, 255),   # PURPLE - T
    (80, 255, 100),   # GREEN - S
    (255, 50, 80),    # RED - Z
    (112, 160, 255),  # BLUE - J
    (255, 165, 0),    # ORANGE - L
]


@dataclass
class FallingBlock:
    shape: list[tuple[int, int]]
    size: int
    x: float
    y: float
    speed: float
    color: tuple[int, int, int]
    alpha: int
    cols: int
    rows: int


class FallingBlocksLayer:
    """Animates translucent tetrominoes drifting downward behind menus."""

    def __init__(
        self,
        block_count: int = 14,
        layer_alpha: int = 180,
        shape_pool: list[list[tuple[int, int]]] | None = None,
        color_pool: list[tuple[int, int, int]] | None = None,
    ) -> None:
        self.block_count = block_count
        self.layer_alpha = layer_alpha
        self._shape_pool = shape_pool or _TETROMINO_SHAPES
        self._color_pool = color_pool or _TETROMINO_COLORS
        self.blocks: list[FallingBlock] = []
        self._last_frame_time = pygame.time.get_ticks()
        self._last_screen_size: tuple[int, int] | None = None
        self._jelly_cell_cache: dict[tuple[int, tuple[int, int, int], int], pygame.Surface] = {}
        self._opacity_multiplier: float = 1.0

    def set_opacity_multiplier(self, value: float) -> None:
        """Tüm düşen blokların alfa değerini orantılı olarak ayarla (0.0–1.0)."""
        self._opacity_multiplier = max(0.0, min(1.0, float(value)))

    # Public API -------------------------------------------------------------
    def update(self, screen: pygame.Surface) -> None:
        width, height = screen.get_size()
        if not self.blocks:
            self._populate(width, height)
            return

        if self._last_screen_size != (width, height):
            self._handle_resize(width, height)
            self._last_screen_size = (width, height)
            self._last_frame_time = pygame.time.get_ticks()

        now = pygame.time.get_ticks()
        delta = (now - self._last_frame_time) / 1000.0 if self._last_frame_time else 0.016
        self._last_frame_time = now
        delta = max(0.001, min(delta, 0.05))

        for block in self.blocks:
            block.y += block.speed * delta
            if block.y - block.rows * block.size > height + 60:
                self._reset_block(block, width, height)

    def draw(self, screen: pygame.Surface) -> None:
        if not self.blocks:
            return
        width, height = screen.get_size()
        om = getattr(self, '_opacity_multiplier', 1.0)
        
        # Jelly renderer varsa kullan - oyundaki blokların aynısı
        if _HAS_JELLY and draw_jelly_block is not None:
            for block in self.blocks:
                effective_alpha = max(0, min(255, int(block.alpha * om)))
                if effective_alpha <= 0:
                    continue
                for cell_x, cell_y in block.shape:
                    bx = int(block.x + cell_x * block.size)
                    by = int(block.y + cell_y * block.size)
                    cell_size = block.size - 1
                    if cell_size > 2:
                        cell_surf = self._get_cached_jelly_cell_surface(cell_size, block.color, effective_alpha)
                        screen.blit(cell_surf, (bx, by))
            return
        
        # Fallback: basit çizim
        for block in self.blocks:
            effective_alpha = max(0, min(255, int(block.alpha * om)))
            if effective_alpha <= 0:
                continue
            for cell_x, cell_y in block.shape:
                rect = pygame.Rect(
                    int(block.x + cell_x * block.size),
                    int(block.y + cell_y * block.size),
                    block.size - 1,
                    block.size - 1,
                )
                fb_surf = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
                pygame.draw.rect(fb_surf, (*block.color, effective_alpha), fb_surf.get_rect(), border_radius=3)
                pygame.draw.rect(fb_surf, (255, 255, 255, effective_alpha), fb_surf.get_rect(), 1, border_radius=3)
                screen.blit(fb_surf, rect.topleft)

    def _get_cached_jelly_cell_surface(
        self,
        cell_size: int,
        color: tuple[int, int, int],
        alpha: int,
    ) -> pygame.Surface:
        key = (cell_size, color, alpha)
        cached = self._jelly_cell_cache.get(key)
        if cached is not None:
            return cached

        cell_surf = pygame.Surface((cell_size, cell_size), pygame.SRCALPHA)
        draw_jelly_block(cell_surf, 0, 0, cell_size, color)
        # macOS'ta SRCALPHA surface üzerinde set_alpha() (per-surface alpha) ile
        # per-pixel alpha birleşimi Metal/OpenGL backend'inde tutarsız sonuç verir.
        # Alpha'yı doğrudan piksel kanallarına BLEND_RGBA_MULT ile bake ederek
        # tüm platformlarda aynı görünümü garanti ederiz.
        if alpha < 255:
            _alpha_mask = pygame.Surface((cell_size, cell_size), pygame.SRCALPHA)
            _alpha_mask.fill((255, 255, 255, alpha))
            cell_surf.blit(_alpha_mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        self._jelly_cell_cache[key] = cell_surf
        return cell_surf

    # Internal helpers -------------------------------------------------------
    def _populate(self, width: int, height: int) -> None:
        self.blocks = [self._create_block(width, height, random_start=True) for _ in range(self.block_count)]
        self._last_screen_size = (width, height)
        self._last_frame_time = pygame.time.get_ticks()

    def _create_block(self, width: int, height: int, *, random_start: bool) -> FallingBlock:
        shape = random.choice(self._shape_pool)
        block_size = random.randint(18, 28)
        cols = max(x for x, _ in shape) + 1
        rows = max(y for _, y in shape) + 1
        max_x = max(0, width - cols * block_size)
        start_x = random.randint(0, max_x) if max_x > 0 else 0
        if random_start:
            # İlk karede boşluk oluşmaması için bazı blokları ekran içinde başlat
            lower_bound = -rows * block_size
            upper_bound = int(height * 0.65)
            start_y = random.randint(lower_bound, upper_bound)
        else:
            start_y = -rows * block_size
        return FallingBlock(
            shape=shape,
            size=block_size,
            x=float(start_x),
            y=float(start_y),
            speed=random.uniform(40, 90),
            color=random.choice(self._color_pool),
            alpha=random.randint(50, 110),
            cols=cols,
            rows=rows,
        )

    def _reset_block(self, block: FallingBlock, width: int, height: int) -> None:
        new_block = self._create_block(width, height, random_start=False)
        block.shape = new_block.shape
        block.size = new_block.size
        block.x = new_block.x
        block.y = new_block.y
        block.speed = new_block.speed
        block.color = new_block.color
        block.alpha = new_block.alpha
        block.cols = new_block.cols
        block.rows = new_block.rows

    def _handle_resize(self, width: int, height: int) -> None:
        """Preserve animation continuity when the render surface changes size."""
        for block in self.blocks:
            max_x = max(0, width - block.cols * block.size)
            if max_x <= 0:
                block.x = 0.0
            else:
                # Keep x within new bounds without re-rolling shapes/colors.
                block.x = float(int(block.x) % (max_x + 1))


_SHARED_FALLING_LAYERS: dict[str, FallingBlocksLayer] = {}


def get_shared_falling_blocks_layer(name: str = 'default', **kwargs) -> FallingBlocksLayer:
    """Return a shared FallingBlocksLayer instance.

    Use different `name` values to maintain separate shared streams (e.g. 'default', 'domino').
    """
    layer = _SHARED_FALLING_LAYERS.get(name)
    if layer is None:
        layer = FallingBlocksLayer(**kwargs)
        _SHARED_FALLING_LAYERS[name] = layer
    return layer


# ============================================================================
# EKRAN GEÇİŞ EFEKTLERİ
# ============================================================================

class ScreenTransition:
    """Ekranlar arası güzel geçiş efektleri."""
    
    # Geçiş tipleri
    FADE = 'fade'           # Karartıp açma
    SLIDE_LEFT = 'slide_left'
    SLIDE_RIGHT = 'slide_right'
    SLIDE_UP = 'slide_up'
    SLIDE_DOWN = 'slide_down'
    ZOOM_IN = 'zoom_in'
    ZOOM_OUT = 'zoom_out'
    WIPE = 'wipe'           # Perdeler gibi kapanıp açılma
    CIRCLE = 'circle'       # Daireden açılma
    
    def __init__(self, duration_ms: int = 300, transition_type: str = 'fade'):
        """
        Args:
            duration_ms: Geçiş süresi (milisaniye)
            transition_type: Geçiş tipi (fade, slide_*, zoom_*, wipe, circle)
        """
        self.duration = duration_ms
        self.transition_type = transition_type
        self.active = False
        self.phase = 'out'  # 'out' = eski ekran kapanıyor, 'in' = yeni ekran açılıyor
        self.start_time = 0
        self.progress = 0.0  # 0.0 - 1.0
        self._old_screen_capture = None
        self._callback = None
        
    def start(self, screen: pygame.Surface, callback=None):
        """Geçişi başlat.
        
        Args:
            screen: Mevcut ekran (capture için)
            callback: Yarı noktada çağrılacak fonksiyon (ekran değişimi), None ise tek fazlı geçiş
        """
        self.active = True
        self.start_time = pygame.time.get_ticks()
        self.progress = 0.0
        self._callback = callback
        
        # Slide geçişlerinde her zaman eski ekranı yakala (gri ekran yerine)
        is_slide = self.transition_type.startswith('slide_')
        
        # Callback varsa iki fazlı (out-in), yoksa tek fazlı (sadece in) geçiş
        if callback is not None:
            self.phase = 'out'
            # Mevcut ekranı yakala
            self._old_screen_capture = screen.copy()
        elif is_slide:
            # Slide için callback olmasa da eski ekranı yakala
            self.phase = 'in'
            self._old_screen_capture = screen.copy()
        else:
            # Diğer efektler için tek fazlı geçiş
            self.phase = 'in'
            self._old_screen_capture = None
        
    def update(self) -> bool:
        """Geçişi güncelle.
        
        Returns:
            True: Geçiş devam ediyor
            False: Geçiş bitti
        """
        if not self.active:
            return False
        
        elapsed = pygame.time.get_ticks() - self.start_time
        
        # Callback varsa iki fazlı, yoksa tek fazlı
        if self._callback is not None or self.phase == 'out':
            half_duration = self.duration / 2
            
            if self.phase == 'out':
                # İlk yarı: eski ekran kapanıyor
                self.progress = min(1.0, elapsed / half_duration)
                if elapsed >= half_duration:
                    self.phase = 'in'
                    self.start_time = pygame.time.get_ticks()
                    self.progress = 0.0
                    # Callback'i çağır (yeni ekrana geçiş)
                    if self._callback:
                        self._callback()
                        self._callback = None
            else:
                # İkinci yarı: yeni ekran açılıyor
                self.progress = min(1.0, elapsed / half_duration)
                if elapsed >= half_duration:
                    self.active = False
                    self._old_screen_capture = None
                    return False
        else:
            # Tek fazlı geçiş (sadece in)
            self.progress = min(1.0, elapsed / self.duration)
            if elapsed >= self.duration:
                self.active = False
                return False
                
        return True
    
    def draw(self, screen: pygame.Surface):
        """Geçiş efektini çiz."""
        if not self.active:
            return
            
        width, height = screen.get_size()
        
        if self.transition_type == self.FADE:
            self._draw_fade(screen, width, height)
        elif self.transition_type == self.WIPE:
            self._draw_wipe(screen, width, height)
        elif self.transition_type == self.CIRCLE:
            self._draw_circle(screen, width, height)
        elif self.transition_type.startswith('slide_'):
            self._draw_slide(screen, width, height)
        elif self.transition_type.startswith('zoom_'):
            self._draw_zoom(screen, width, height)
        else:
            self._draw_fade(screen, width, height)
    
    def _ease_out_quad(self, t: float) -> float:
        """Yumuşak yavaşlama easing fonksiyonu."""
        return 1 - (1 - t) * (1 - t)
    
    def _ease_in_out_quad(self, t: float) -> float:
        """Giriş-çıkış yumuşak easing."""
        if t < 0.5:
            return 2 * t * t
        return 1 - pow(-2 * t + 2, 2) / 2
    
    def _draw_fade(self, screen: pygame.Surface, width: int, height: int):
        """Fade (karartma) efekti."""
        if self.phase == 'out':
            # Eski ekran kararıyor
            alpha = int(255 * self._ease_out_quad(self.progress))
        else:
            # Yeni ekran açılıyor
            alpha = int(255 * (1 - self._ease_out_quad(self.progress)))
        
        overlay = pygame.Surface((width, height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, alpha))
        screen.blit(overlay, (0, 0))
    
    def _draw_wipe(self, screen: pygame.Surface, width: int, height: int):
        """Perde efekti - ortadan dışa/içe."""
        progress = self._ease_in_out_quad(self.progress)
        
        if self.phase == 'out':
            # Perdeler kapanıyor (ortaya doğru)
            cover_width = int((width / 2) * progress)
        else:
            # Perdeler açılıyor (dışa doğru)
            cover_width = int((width / 2) * (1 - progress))
        
        # Sol ve sağ perde
        if cover_width > 0:
            left_rect = pygame.Rect(0, 0, cover_width, height)
            right_rect = pygame.Rect(width - cover_width, 0, cover_width, height)

            left_overlay = pygame.Surface(left_rect.size, pygame.SRCALPHA)
            right_overlay = pygame.Surface(right_rect.size, pygame.SRCALPHA)
            left_overlay.fill((15, 20, 30, 236))
            right_overlay.fill((15, 20, 30, 236))

            edge_steps = min(8, cover_width)
            for step in range(edge_steps):
                ratio = step / max(1, edge_steps - 1)
                alpha = int(54 * (1.0 - ratio))
                left_x = max(0, cover_width - edge_steps + step)
                right_x = min(cover_width - 1, step)
                pygame.draw.line(left_overlay, (48, 62, 82, alpha), (left_x, 0), (left_x, height))
                pygame.draw.line(right_overlay, (48, 62, 82, alpha), (right_x, 0), (right_x, height))

            screen.blit(left_overlay, left_rect.topleft)
            screen.blit(right_overlay, right_rect.topleft)
    
    def _draw_circle(self, screen: pygame.Surface, width: int, height: int):
        """Daire efekti - ortadan açılıp kapanan."""
        progress = self._ease_in_out_quad(self.progress)
        center = (width // 2, height // 2)
        max_radius = int((width ** 2 + height ** 2) ** 0.5 / 2) + 50
        
        if self.phase == 'out':
            # Daire küçülüyor (ekran kapanıyor)
            radius = int(max_radius * (1 - progress))
        else:
            # Daire büyüyor (ekran açılıyor)
            radius = int(max_radius * progress)
        
        # Maskeleme için surface oluştur
        mask = pygame.Surface((width, height), pygame.SRCALPHA)
        mask.fill((0, 0, 0, 255))
        
        if radius > 0:
            # Daire içini şeffaf yap
            pygame.draw.circle(mask, (0, 0, 0, 0), center, radius)
        
        screen.blit(mask, (0, 0))
    
    def _draw_slide(self, screen: pygame.Surface, width: int, height: int):
        """Kaydırma efekti - eski ekran kayarak çıkıyor, yeni ekran kayarak giriyor."""
        progress = self._ease_out_quad(self.progress)
        
        direction = self.transition_type.split('_')[1]
        
        if self.phase == 'out' and self._old_screen_capture:
            # İki fazlı mod (out fazı): Eski ekran kayıyor
            if direction == 'left':
                offset_x = int(-width * progress)
                offset_y = 0
            elif direction == 'right':
                offset_x = int(width * progress)
                offset_y = 0
            elif direction == 'up':
                offset_x = 0
                offset_y = int(-height * progress)
            else:  # down
                offset_x = 0
                offset_y = int(height * progress)
            
            screen.blit(self._old_screen_capture, (offset_x, offset_y))
        elif self._old_screen_capture:
            # Tek fazlı veya in fazı: Eski ve yeni ekran birlikte kayıyor
            # Eski ekran çıkıyor, yeni ekran giriyor (yan yana)

            if direction == 'left':
                # Eski ekran sola kayarak çıkıyor
                old_offset_x = int(-width * progress)
                old_offset_y = 0
                # Yeni ekran sağdan giriyor
                new_offset_x = int(width * (1 - progress))
                new_offset_y = 0
            elif direction == 'right':
                # Eski ekran sağa kayarak çıkıyor
                old_offset_x = int(width * progress)
                old_offset_y = 0
                # Yeni ekran soldan giriyor
                new_offset_x = int(-width * (1 - progress))
                new_offset_y = 0
            elif direction == 'up':
                # Eski ekran yukarı kayarak çıkıyor
                old_offset_x = 0
                old_offset_y = int(-height * progress)
                # Yeni ekran aşağıdan giriyor
                new_offset_x = 0
                new_offset_y = int(height * (1 - progress))
            else:  # down
                # Eski ekran aşağı kayarak çıkıyor
                old_offset_x = 0
                old_offset_y = int(height * progress)
                # Yeni ekran yukarıdan giriyor
                new_offset_x = 0
                new_offset_y = int(-height * (1 - progress))

            # Performans: her frame tam ekran screen.copy() yerine mevcut yeni ekranı
            # yerinde kaydır, sonra eski ekranı üzerine uygun offset ile çiz.
            if new_offset_x != 0 or new_offset_y != 0:
                screen.scroll(new_offset_x, new_offset_y)
            screen.blit(self._old_screen_capture, (old_offset_x, old_offset_y))
        else:
            # Eski ekran capture yok - sadece fade efekti uygula
            inv_progress = 1 - progress
            alpha = int(180 * inv_progress)
            if alpha > 0:
                overlay = pygame.Surface((width, height), pygame.SRCALPHA)
                overlay.fill((10, 15, 25, alpha))
                screen.blit(overlay, (0, 0))
    
    def _draw_zoom(self, screen: pygame.Surface, width: int, height: int):
        """Zoom efekti - ekranı büyütüp/küçültüp karartma."""
        progress = self._ease_in_out_quad(self.progress)
        
        # Karartma alpha değeri
        if self.phase == 'out':
            alpha = int(255 * progress)
        else:
            alpha = int(255 * (1 - progress))
        
        # Overlay çiz
        overlay = pygame.Surface((width, height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, alpha))
        screen.blit(overlay, (0, 0))
    
    def is_active(self) -> bool:
        """Geçiş aktif mi?"""
        return self.active
    
    def is_midpoint(self) -> bool:
        """Geçişin tam ortasında mıyız? (ekran değişimi için)"""
        return self.active and self.phase == 'in' and self.progress < 0.1


# Global geçiş instance'ı
_screen_transition: ScreenTransition | None = None


def get_screen_transition(duration_ms: int = 250, transition_type: str = 'fade') -> ScreenTransition:
    """Global ekran geçişi instance'ını al veya oluştur."""
    global _screen_transition
    if _screen_transition is None:
        _screen_transition = ScreenTransition(duration_ms, transition_type)
    return _screen_transition


def start_screen_transition(screen: pygame.Surface, callback=None, 
                            duration_ms: int = 250, transition_type: str = 'fade'):
    """Ekran geçişini başlat.
    
    Args:
        screen: Mevcut ekran surface'i
        callback: Geçiş ortasında çağrılacak fonksiyon (state değişimi için)
        duration_ms: Toplam geçiş süresi (ms)
        transition_type: 'fade', 'wipe', 'circle', 'slide_left', 'slide_right', 
                        'slide_up', 'slide_down', 'zoom_in', 'zoom_out'
    """
    global _screen_transition
    _screen_transition = ScreenTransition(duration_ms, transition_type)
    _screen_transition.start(screen, callback)


def update_screen_transition() -> bool:
    """Ekran geçişini güncelle.
    
    Returns:
        True: Geçiş devam ediyor
        False: Geçiş bitti veya aktif değil
    """
    global _screen_transition
    if _screen_transition is None:
        return False
    return _screen_transition.update()


def draw_screen_transition(screen: pygame.Surface):
    """Ekran geçişini çiz."""
    global _screen_transition
    if _screen_transition is not None and _screen_transition.is_active():
        _screen_transition.draw(screen)


def is_screen_transition_active() -> bool:
    """Ekran geçişi aktif mi?"""
    global _screen_transition
    return _screen_transition is not None and _screen_transition.is_active()
