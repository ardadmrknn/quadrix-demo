"""
Avatar düzenleme ve resim yükleme modülü
Harici resim dosyalarını yükleyip kare şeklinde kırpma
"""
import pygame
import os

from asset_manager import load_image
from storage_layout import build_temp_avatar_path
from ui_theme import UIFonts
from platform_utils import normalize_mouse_pos
from localization import t


# Renkler
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GRAY = (128, 128, 128)
DARK_GRAY = (40, 40, 40)
LIGHT_GRAY = (200, 200, 200)
BLUE = (100, 150, 255)
GREEN = (100, 200, 100)
RED = (200, 100, 100)


class AvatarEditor:
    """Avatar düzenleme ekranı - resim yükleme ve kırpma"""
    
    def __init__(self, screen):
        """Avatar düzenleyiciyi başlat"""
        self.screen = screen
        self.font_title = UIFonts.get(56)
        self.font_normal = UIFonts.get(36)
        self.font_small = UIFonts.get(26)
        
        # Resim dosyası
        self.original_image = None
        self.image_path = None
        self.display_image = None
        
        # Kırpma bölgesi
        self.crop_rect = None
        self.crop_size = 300  # Başlangıç kırpma karesinin boyutu (daha büyük)
        self.min_crop_size = 100  # Minimum kare boyutu
        self.max_crop_size = 500  # Maksimum kare boyutu
        self.crop_x = 0
        self.crop_y = 0
        
        # Zoom ve pan
        self.zoom = 1.0
        self.min_zoom = 0.5
        self.max_zoom = 3.0
        self.pan_x = 0
        self.pan_y = 0
        
        # Mouse kontrolü
        self.dragging = False
        self.resizing = False
        self.drag_start = None
        self.resize_start = None
        self.resize_start_size = 0
        
    def open_file_dialog(self):
        """Dosya seçme dialogunu aç"""
        try:
            from file_dialog import open_file_dialog

            file_path = open_file_dialog(
                title=t('avatar_select_image'),
                filetypes=[
                    (t('avatar_image_files'), '*.png *.jpg *.jpeg *.bmp *.gif'),
                    (t('avatar_all_files'), '*.*')
                ],
            )

            if file_path:
                self.load_image(file_path)
                return True
            return False
        except Exception as e:
            print(f"Dosya seçme hatası: {e}")
            return False
    
    def load_image(self, path):
        """Resmi yükle"""
        try:
            self.original_image = load_image(path, convert_alpha=False)
            self.image_path = path
            
            # Ekrana sığacak şekilde ölçeklendir
            width, height = self.screen.get_size()
            max_size = min(width - 200, height - 300)
            
            img_w, img_h = self.original_image.get_size()
            scale = min(max_size / img_w, max_size / img_h)
            
            new_w = int(img_w * scale)
            new_h = int(img_h * scale)
            
            # SMOOTHSCALE ile kaliteli ölçeklendirme
            self.display_image = pygame.transform.smoothscale(self.original_image, (new_w, new_h))
            
            # Kırpma karesini ortala
            self.crop_x = (new_w - self.crop_size) // 2
            self.crop_y = (new_h - self.crop_size) // 2
            
            # Sınırları ayarla
            self._clamp_crop()
            
            return True
        except Exception as e:
            print(f"Resim yüklenirken hata: {e}")
            return False
    
    def _clamp_crop(self):
        """Kırpma karesini resim sınırları içinde tut"""
        if self.display_image:
            img_w, img_h = self.display_image.get_size()
            self.crop_x = max(0, min(self.crop_x, img_w - self.crop_size))
            self.crop_y = max(0, min(self.crop_y, img_h - self.crop_size))
    
    def handle_event(self, event):
        """Olayları işle"""
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                return 'cancel'
            elif event.key == pygame.K_RETURN:
                if self.display_image:
                    return 'save'
            elif event.key == pygame.K_o or event.key == pygame.K_s:
                # Dosya seç
                self.open_file_dialog()
            
            # Kırpma karesini ok tuşlarıyla hareket ettir
            elif event.key == pygame.K_LEFT:
                self.crop_x -= 5
                self._clamp_crop()
            elif event.key == pygame.K_RIGHT:
                self.crop_x += 5
                self._clamp_crop()
            elif event.key == pygame.K_UP:
                self.crop_y -= 5
                self._clamp_crop()
            elif event.key == pygame.K_DOWN:
                self.crop_y += 5
                self._clamp_crop()
            # + ve - ile boyut değiştir
            elif event.key == pygame.K_PLUS or event.key == pygame.K_EQUALS:
                self.crop_size = min(self.max_crop_size, self.crop_size + 10)
                self._clamp_crop()
            elif event.key == pygame.K_MINUS:
                self.crop_size = max(self.min_crop_size, self.crop_size - 10)
                self._clamp_crop()
            # Gamepad LB/RB (bracket) ile crop size değiştir
            elif event.key == pygame.K_RIGHTBRACKET:
                self.crop_size = min(self.max_crop_size, self.crop_size + 10)
                self._clamp_crop()
            elif event.key == pygame.K_LEFTBRACKET:
                self.crop_size = max(self.min_crop_size, self.crop_size - 10)
                self._clamp_crop()
        
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:  # Sol tık
                pos = normalize_mouse_pos(getattr(event, 'pos', None)) or event.pos
                width, height = self.screen.get_size()
                if self.display_image:
                    img_w, img_h = self.display_image.get_size()
                    img_x = width // 2 - img_w // 2
                    img_y = 150
                    
                    crop_rect = pygame.Rect(
                        img_x + self.crop_x,
                        img_y + self.crop_y,
                        self.crop_size,
                        self.crop_size
                    )
                    
                    # Sağ alt köşe tutamacı kontrolü (resize için)
                    resize_handle_size = 20
                    resize_handle = pygame.Rect(
                        crop_rect.right - resize_handle_size,
                        crop_rect.bottom - resize_handle_size,
                        resize_handle_size,
                        resize_handle_size
                    )
                    
                    if resize_handle.collidepoint(pos):
                        # Resize moduna geç
                        self.resizing = True
                        self.resize_start = pos
                        self.resize_start_size = self.crop_size
                    elif crop_rect.collidepoint(pos):
                        # Sürükleme moduna geç
                        self.dragging = True
                        self.drag_start = (pos[0] - self.crop_x, pos[1] - self.crop_y)
            
            elif event.button == 4:  # Mouse wheel up - zoom in
                self.zoom = min(self.max_zoom, self.zoom + 0.1)
            elif event.button == 5:  # Mouse wheel down - zoom out
                self.zoom = max(self.min_zoom, self.zoom - 0.1)
        
        elif event.type == pygame.MOUSEBUTTONUP:
            if event.button == 1:
                self.dragging = False
                self.resizing = False
                self.drag_start = None
                self.resize_start = None
        
        elif event.type == pygame.MOUSEMOTION:
            pos = normalize_mouse_pos(getattr(event, 'pos', None)) or event.pos
            if self.resizing and self.resize_start:
                # Kare boyutunu değiştir
                width, height = self.screen.get_size()
                if self.display_image:
                    img_w, img_h = self.display_image.get_size()
                    img_x = width // 2 - img_w // 2
                    img_y = 150
                    
                    # Mouse'un başlangıç noktasından ne kadar hareket ettiğini hesapla
                    delta_x = pos[0] - self.resize_start[0]
                    delta_y = pos[1] - self.resize_start[1]
                    
                    # Kare formunu korumak için daha büyük delta'yı kullan
                    delta = max(delta_x, delta_y)
                    
                    # Yeni boyutu hesapla
                    new_size = self.resize_start_size + delta
                    
                    # Sınırları kontrol et
                    new_size = max(self.min_crop_size, min(self.max_crop_size, new_size))
                    
                    # Resim sınırlarını aşmayacak şekilde kontrol et
                    if self.crop_x + new_size <= img_w and self.crop_y + new_size <= img_h:
                        self.crop_size = new_size
                    
                    self._clamp_crop()
                    
            elif self.dragging and self.drag_start:
                # Kareyi hareket ettir
                width, height = self.screen.get_size()
                if self.display_image:
                    img_w, img_h = self.display_image.get_size()
                    img_x = width // 2 - img_w // 2
                    img_y = 150
                    
                    # Yeni pozisyon
                    self.crop_x = pos[0] - self.drag_start[0]
                    self.crop_y = pos[1] - self.drag_start[1] - img_y
                    
                    self._clamp_crop()
        
        return None
    
    def draw(self):
        """Editör ekranını çiz"""
        width, height = self.screen.get_size()
        
        # Koyu gradient arka plan
        for i in range(height):
            color_r = int(10 + (i / height) * 15)
            color_g = int(15 + (i / height) * 20)
            color_b = int(30 + (i / height) * 25)
            pygame.draw.line(self.screen, (color_r, color_g, color_b), (0, i), (width, i))
        
        # Başlık
        title = self.font_title.render(t('avatar_edit_title'), True, WHITE)
        title_rect = title.get_rect(center=(width // 2, 50))
        self.screen.blit(title, title_rect)
        
        if self.display_image:
            # Resmi göster
            img_w, img_h = self.display_image.get_size()
            img_x = width // 2 - img_w // 2
            img_y = 150
            
            # Resim arka plan
            bg_rect = pygame.Rect(img_x - 10, img_y - 10, img_w + 20, img_h + 20)
            pygame.draw.rect(self.screen, (50, 60, 80), bg_rect, border_radius=10)
            pygame.draw.rect(self.screen, (100, 120, 180), bg_rect, 2, border_radius=10)
            
            self.screen.blit(self.display_image, (img_x, img_y))
            
            # Kırpma karesi (mavi çerçeve)
            crop_rect = pygame.Rect(
                img_x + self.crop_x,
                img_y + self.crop_y,
                self.crop_size,
                self.crop_size
            )
            
            # Karanlık overlay (kırpma dışı alan)
            overlay = pygame.Surface((img_w, img_h), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 120))
            
            # Kırpma alanını temizle
            clear_rect = pygame.Rect(self.crop_x, self.crop_y, self.crop_size, self.crop_size)
            pygame.draw.rect(overlay, (0, 0, 0, 0), clear_rect)
            
            self.screen.blit(overlay, (img_x, img_y))
            
            # Kırpma çerçevesi
            pygame.draw.rect(self.screen, BLUE, crop_rect, 3)
            
            # Köşe tutamaçları
            corner_size = 12
            corners = [
                (crop_rect.left, crop_rect.top),
                (crop_rect.right - corner_size, crop_rect.top),
                (crop_rect.left, crop_rect.bottom - corner_size),
                (crop_rect.right - corner_size, crop_rect.bottom - corner_size)
            ]
            
            for corner in corners:
                corner_rect = pygame.Rect(corner[0], corner[1], corner_size, corner_size)
                pygame.draw.rect(self.screen, WHITE, corner_rect)
                pygame.draw.rect(self.screen, BLUE, corner_rect, 2)
            
            # Sağ alt köşe - BÜYÜK RESIZE TUTAMACI
            resize_handle_size = 24
            resize_handle = pygame.Rect(
                crop_rect.right - resize_handle_size,
                crop_rect.bottom - resize_handle_size,
                resize_handle_size,
                resize_handle_size
            )
            
            # Resize tutamacı - daha belirgin
            pygame.draw.rect(self.screen, (255, 200, 0), resize_handle, border_radius=5)
            pygame.draw.rect(self.screen, (255, 255, 100), resize_handle, 3, border_radius=5)
            
            # Resize ikonu — PNG emoji
            from emoji_renderer import emoji_surface
            _resize_ic = emoji_surface('↘', 16) 
            if _resize_ic is None:
                # EMOJI_MAP'te yoksa doğrudan dosyadan yükle
                try:
                    from pathlib import Path
                    _rp = Path(__file__).resolve().parent.parent / 'assets' / 'emoji' / 'resize_arrow.png'
                    if _rp.exists():
                        _resize_ic = pygame.image.load(str(_rp)).convert_alpha()
                        _resize_ic = pygame.transform.smoothscale(_resize_ic, (16, 16))
                except Exception:
                    pass
            if _resize_ic:
                _ir = _resize_ic.get_rect(center=resize_handle.center)
                self.screen.blit(_resize_ic, _ir)
            
            # Boyut göstergesi (karenin üzerinde)
            size_text = f'{self.crop_size}x{self.crop_size} px'
            size_surf = self.font_small.render(size_text, True, (255, 255, 100))
            size_bg_rect = pygame.Rect(crop_rect.centerx - 60, crop_rect.top - 35, 120, 30)
            pygame.draw.rect(self.screen, (40, 50, 70), size_bg_rect, border_radius=8)
            pygame.draw.rect(self.screen, BLUE, size_bg_rect, 2, border_radius=8)
            size_rect = size_surf.get_rect(center=size_bg_rect.center)
            self.screen.blit(size_surf, size_rect)
            
            # Önizleme (sağ üst köşe)
            preview_size = 150  # Biraz daha büyük
            preview_x = width - preview_size - 50
            preview_y = 150
            
            # Kırpılmış alanı al
            cropped = self.get_cropped_image()
            if cropped:
                # SMOOTHSCALE ile kaliteli önizleme
                preview_img = pygame.transform.smoothscale(cropped, (preview_size, preview_size))
                
                # Önizleme arka plan
                preview_bg = pygame.Rect(preview_x - 10, preview_y - 10, preview_size + 20, preview_size + 20)
                pygame.draw.rect(self.screen, (50, 60, 80), preview_bg, border_radius=15)
                pygame.draw.rect(self.screen, GREEN, preview_bg, 3, border_radius=15)
                
                self.screen.blit(preview_img, (preview_x, preview_y))
                
                # Önizleme label
                preview_label = self.font_small.render(t('avatar_preview'), True, WHITE)
                preview_label_rect = preview_label.get_rect(center=(preview_x + preview_size // 2, preview_y - 25))
                self.screen.blit(preview_label, preview_label_rect)
        
        else:
            # Resim yok - dosya seç talimatı
            no_image_text = [
                t('avatar_no_image_selected'),
                '',
                t('avatar_press_s'),
                '"' + t('avatar_key_select') + '"',
                t('avatar_select_file')
            ]
            
            for i, line in enumerate(no_image_text):
                text_surf = self.font_normal.render(line, True, GRAY)
                text_rect = text_surf.get_rect(center=(width // 2, height // 2 - 50 + i * 45))
                self.screen.blit(text_surf, text_rect)
        
        # Alt bar - butonlar
        bottom_bar_y = height - 100
        
        # Gradient alt bar
        for i in range(100):
            alpha = 1 - (i / 100)
            color = (int(20 * alpha), int(25 * alpha), int(40 * alpha))
            pygame.draw.line(self.screen, color, (0, bottom_bar_y + i), (width, bottom_bar_y + i))
        
        pygame.draw.line(self.screen, (70, 100, 180), (0, bottom_bar_y), (width, bottom_bar_y), 2)
        
        # Kontrol butonları
        buttons = [
            ('S', t('avatar_key_select'), (100, 150, 255)),
            ('←/→/↑/↓', t('avatar_key_move'), (150, 100, 200)),
            ('+ / -', t('avatar_key_size'), (255, 200, 100)),
            ('Mouse', t('avatar_key_drag'), (200, 150, 100)),
            ('ENTER', t('avatar_key_save'), (100, 200, 100)),
            ('ESC', t('avatar_key_cancel'), (200, 100, 100))
        ]
        
        total_width = sum(160 for _ in buttons) - 20
        button_x = width // 2 - total_width // 2
        button_y = bottom_bar_y + 10
        
        for key, label, color in buttons:
            key_width = 160 if len(key) > 8 else (100 if len(key) > 5 else 70)
            key_bg = pygame.Rect(button_x, button_y, key_width, 40)
            
            # Buton devre dışıysa gri yap
            if label == 'Kaydet' and not self.display_image:
                color = (100, 100, 100)
            
            pygame.draw.rect(self.screen, color, key_bg, border_radius=8)
            pygame.draw.rect(self.screen, tuple(min(255, c + 40) for c in color), key_bg, 2, border_radius=8)
            
            key_surf = self.font_small.render(key, True, WHITE)
            self.screen.blit(key_surf, key_surf.get_rect(center=key_bg.center))
            
            label_surf = self.font_small.render(label, True, (180, 180, 180))
            label_rect = label_surf.get_rect(midtop=(button_x + key_width // 2, button_y + 45))
            self.screen.blit(label_surf, label_rect)
            
            button_x += 165
    
    def get_cropped_image(self):
        """Kırpılmış resmi al (orijinal kalitede)"""
        if not self.original_image or not self.display_image:
            return None
        
        # Orijinal resmin ölçeği
        orig_w, orig_h = self.original_image.get_size()
        disp_w, disp_h = self.display_image.get_size()
        
        scale = orig_w / disp_w
        
        # Kırpma alanını orijinal resme göre hesapla
        crop_x_orig = int(self.crop_x * scale)
        crop_y_orig = int(self.crop_y * scale)
        crop_size_orig = int(self.crop_size * scale)
        
        # Kırp
        cropped = pygame.Surface((crop_size_orig, crop_size_orig))
        cropped.blit(
            self.original_image,
            (0, 0),
            (crop_x_orig, crop_y_orig, crop_size_orig, crop_size_orig)
        )
        
        # Standart avatar boyutuna ölçekle (128x128) - SMOOTHSCALE ile kaliteli
        final_size = 128
        cropped = pygame.transform.smoothscale(cropped, (final_size, final_size))
        
        return cropped
    
    def save_avatar(self, username, target_path=None):
        """Avatarı kaydet"""
        cropped = self.get_cropped_image()
        if not cropped:
            return None

        filepath = target_path or build_temp_avatar_path(username)
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        
        # Kaydet
        pygame.image.save(cropped, filepath)
        
        return filepath
