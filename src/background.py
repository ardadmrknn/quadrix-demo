"""Arka plan resmi yöneticisi"""
import pygame
import os
import sys
from collections import OrderedDict
from pathlib import Path

from asset_manager import load_image

# macOS detection
_IS_MACOS = sys.platform == 'darwin'
_BACKGROUND_IMAGE_CACHE: "OrderedDict[tuple[str, bool], pygame.Surface]" = OrderedDict()
_BACKGROUND_IMAGE_CACHE_MAX_ITEMS = 16

def resource_path(relative_path):
    """PyInstaller ile derlenen exe için doğru path'i al"""
    try:
        # PyInstaller temp klasörü
        base_path = Path(sys._MEIPASS)
    except Exception:
        # Normal Python çalıştırma (CWD'ye güvenme)
        base_path = Path(__file__).resolve().parents[1]

    return os.path.normpath(str(base_path / relative_path))


def _resolve_existing_image_path(image_path: str) -> str | None:
    if os.path.isabs(image_path) and os.path.exists(image_path):
        return os.path.normpath(image_path)

    full_path = resource_path(image_path)
    if os.path.exists(full_path):
        return os.path.normpath(full_path)

    return None


def _get_cached_background_image(resolved_path: str) -> pygame.Surface:
    convert_for_display = (not _IS_MACOS) and pygame.display.get_surface() is not None
    cache_key = (resolved_path, bool(convert_for_display))
    cached = _BACKGROUND_IMAGE_CACHE.get(cache_key)
    if cached is not None:
        _BACKGROUND_IMAGE_CACHE.move_to_end(cache_key)
        return cached

    image = load_image(resolved_path, convert_alpha=False)
    if convert_for_display:
        try:
            image = image.convert_alpha() if image.get_alpha() is not None else image.convert()
        except Exception:
            pass

    _BACKGROUND_IMAGE_CACHE[cache_key] = image
    _BACKGROUND_IMAGE_CACHE.move_to_end(cache_key)
    while len(_BACKGROUND_IMAGE_CACHE) > _BACKGROUND_IMAGE_CACHE_MAX_ITEMS:
        _BACKGROUND_IMAGE_CACHE.popitem(last=False)

    return image

class BackgroundManager:
    """Oyun arka planı için resim yöneticisi"""
    
    def __init__(self):
        """Arka plan yöneticisini başlat"""
        self.background_image = None
        self.background_surface = None
        self.transparency = 0.3  # 0.0 (tamamen saydam) - 1.0 (opak)
        self.enabled = True

    @classmethod
    def prewarm_image(cls, image_path):
        resolved_path = _resolve_existing_image_path(image_path)
        if resolved_path is None:
            return False
        _get_cached_background_image(resolved_path)
        return True
        
    def load_image(self, image_path):
        """
        Arka plan resmini yükle
        
        Args:
            image_path: Resim dosyasının yolu (absolute veya relative)
        """
        try:
            resolved_path = _resolve_existing_image_path(image_path)
            if resolved_path is not None:
                self.background_image = _get_cached_background_image(resolved_path)
                print(f"✅ Arka plan resmi yüklendi: {os.path.basename(resolved_path)}")
                return True

            # Do not print per-path 'not found' messages here, the caller will
            # decide whether to print a summary. Avoid spamming the terminal
            # when multiple fallback paths are checked.
            return False
        except Exception as e:
            print(f"⚠️ Arka plan resmi yüklenemedi: {e}")
            return False
    
    def set_transparency(self, value):
        """
        Transparanlık seviyesini ayarla
        
        Args:
            value: 0.0 (tamamen saydam) - 1.0 (tamamen opak)
        """
        self.transparency = max(0.0, min(1.0, value))
        self.background_surface = None  # Yeniden oluşturulacak
    
    def draw(self, screen, board_rect):
        """
        Arka planı çiz (oyun tahtasının arkasına)
        
        Args:
            screen: Pygame ekranı
            board_rect: Oyun tahtasının rect'i (x, y, width, height)
        """
        if not self.enabled or self.background_image is None:
            return
        
        # Arka plan yüzeyini oluştur veya güncelle
        if self.background_surface is None or \
           self.background_surface.get_size() != (board_rect[2], board_rect[3]):
            # Resmi tahta boyutuna ölçeklendir
            # macOS: smoothscale yerine scale daha güvenli
            if _IS_MACOS:
                scaled_image = pygame.transform.scale(
                    self.background_image, 
                    (board_rect[2], board_rect[3])
                )
            else:
                scaled_image = pygame.transform.scale(
                    self.background_image, 
                    (board_rect[2], board_rect[3])
                )

            # macOS: convert bazen crash yapabiliyor
            if not _IS_MACOS:
                try:
                    if pygame.display.get_surface() is not None:
                        scaled_image = scaled_image.convert()
                except Exception:
                    pass
            
            # Yeni surface oluştur
            self.background_surface = pygame.Surface((board_rect[2], board_rect[3]))
            self.background_surface.blit(scaled_image, (0, 0))
            
            # Transparanlığı ayarla
            alpha = int(255 * self.transparency)
            self.background_surface.set_alpha(alpha)
        
        # Arka planı çiz
        screen.blit(self.background_surface, (board_rect[0], board_rect[1]))
    
    def toggle(self):
        """Arka planı aç/kapat"""
        self.enabled = not self.enabled
        return self.enabled
    
    def is_loaded(self):
        """Arka plan resmi yüklü mü?"""
        return self.background_image is not None

    def _ensure_full_screen_cache(self, screen):
        if not self.enabled or self.background_image is None:
            return None

        screen_width, screen_height = screen.get_size()
        current_size = (screen_width, screen_height)

        if not hasattr(self, '_cached_full_screen') or not hasattr(self, '_cached_screen_size') or self._cached_screen_size != current_size:
            scaled = pygame.transform.scale(
                self.background_image,
                (screen_width, screen_height)
            )
            if _IS_MACOS:
                self._cached_full_screen = scaled
            else:
                try:
                    self._cached_full_screen = scaled.convert()
                except Exception:
                    self._cached_full_screen = scaled
            self._cached_screen_size = current_size
            self._cached_full_alpha = None

        alpha = int(255 * max(0.0, min(1.0, float(getattr(self, 'transparency', 1.0)))))
        cached_alpha = getattr(self, '_cached_full_alpha', None)
        if cached_alpha != alpha:
            try:
                self._cached_full_screen.set_alpha(None if alpha >= 255 else alpha)
            except Exception:
                self._cached_full_screen.set_alpha(alpha)
            self._cached_full_alpha = alpha
        return self._cached_full_screen
    
    def draw_full_screen(self, screen):
        """
        Arka planı tam ekrana çiz (oyun alanı dışındaki bölge için)
        CACHE ile optimize edilmiş - her frame scale etmez
        
        Args:
            screen: Pygame ekranı
        """
        if not self.enabled or self.background_image is None:
            return
        
        cached_surface = self._ensure_full_screen_cache(screen)
        if cached_surface is None:
            return

        screen.blit(cached_surface, (0, 0))

    def get_full_screen_surface(self, screen):
        """Cache'lenmiş tam ekran arka plan yüzeyini döndür."""
        return self._ensure_full_screen_cache(screen)

    def draw_full_screen_region(self, screen, region_rect):
        """Çözünürlük cache'ini koruyarak tam ekran arka planın yalnızca istenen bölgesini çiz."""
        if not self.enabled or self.background_image is None:
            return
        rect = pygame.Rect(region_rect)
        if rect.width <= 0 or rect.height <= 0:
            return

        cached_surface = self._ensure_full_screen_cache(screen)
        if cached_surface is None:
            return

        screen.blit(cached_surface, rect.topleft, rect)
