"""Arka plan resmi yöneticisi"""
import pygame
import os
import sys
from pathlib import Path

from asset_manager import load_image

# macOS detection
_IS_MACOS = sys.platform == 'darwin'

def resource_path(relative_path):
    """PyInstaller ile derlenen exe için doğru path'i al"""
    try:
        # PyInstaller temp klasörü
        base_path = Path(sys._MEIPASS)
    except Exception:
        # Normal Python çalıştırma (CWD'ye güvenme)
        base_path = Path(__file__).resolve().parents[1]

    return os.path.normpath(str(base_path / relative_path))

class BackgroundManager:
    """Oyun arka planı için resim yöneticisi"""
    
    def __init__(self):
        """Arka plan yöneticisini başlat"""
        self.background_image = None
        self.background_surface = None
        self.transparency = 0.3  # 0.0 (tamamen saydam) - 1.0 (opak)
        self.enabled = True
        
    def load_image(self, image_path):
        """
        Arka plan resmini yükle
        
        Args:
            image_path: Resim dosyasının yolu (absolute veya relative)
        """
        try:
            # Önce absolute path olarak dene (custom background için)
            if os.path.isabs(image_path) and os.path.exists(image_path):
                img = load_image(image_path, convert_alpha=False)
                # macOS: convert/convert_alpha bazen crash yapabiliyor
                if not _IS_MACOS:
                    try:
                        if pygame.display.get_surface() is not None:
                            img = img.convert_alpha() if img.get_alpha() is not None else img.convert()
                    except Exception:
                        pass
                self.background_image = img
                print(f"✅ Özel arka plan resmi yüklendi: {os.path.basename(image_path)}")
                return True
            
            # Değilse PyInstaller için doğru path'i al (relative path)
            full_path = resource_path(image_path)
            if os.path.exists(full_path):
                img = load_image(full_path, convert_alpha=False)
                # macOS: convert/convert_alpha bazen crash yapabiliyor
                if not _IS_MACOS:
                    try:
                        if pygame.display.get_surface() is not None:
                            img = img.convert_alpha() if img.get_alpha() is not None else img.convert()
                    except Exception:
                        pass
                self.background_image = img
                print(f"✅ Arka plan resmi yüklendi: {image_path}")
                return True
            else:
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
    
    def draw_full_screen(self, screen):
        """
        Arka planı tam ekrana çiz (oyun alanı dışındaki bölge için)
        CACHE ile optimize edilmiş - her frame scale etmez
        
        Args:
            screen: Pygame ekranı
        """
        if not self.enabled or self.background_image is None:
            return
        
        # Ekran boyutunu al
        screen_width, screen_height = screen.get_size()
        current_size = (screen_width, screen_height)
        
        # Cache kontrolü - sadece boyut değiştiğinde yeniden scale et
        if not hasattr(self, '_cached_full_screen') or not hasattr(self, '_cached_screen_size') or self._cached_screen_size != current_size:
            # Resmi ekran boyutuna ölçeklendir ve cache'le
            scaled = pygame.transform.scale(
                self.background_image,
                (screen_width, screen_height)
            )
            # macOS: convert bazen crash yapabiliyor
            if _IS_MACOS:
                self._cached_full_screen = scaled
            else:
                try:
                    self._cached_full_screen = scaled.convert()
                except Exception:
                    self._cached_full_screen = scaled
            self._cached_screen_size = current_size
            self._cached_full_alpha = None

        # Transparanlığı uygula (menüler + oyun dış alanı aynı davranmalı)
        alpha = int(255 * max(0.0, min(1.0, float(getattr(self, 'transparency', 1.0)))))
        cached_alpha = getattr(self, '_cached_full_alpha', None)
        if cached_alpha != alpha:
            try:
                # alpha=255 -> per-surface alpha kapat (daha hızlı)
                self._cached_full_screen.set_alpha(None if alpha >= 255 else alpha)
            except Exception:
                self._cached_full_screen.set_alpha(alpha)
            self._cached_full_alpha = alpha

        # Cache'lenmiş resmi çiz (her frame aynı)
        screen.blit(self._cached_full_screen, (0, 0))
