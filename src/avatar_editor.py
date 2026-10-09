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


# ---------------------------------------------------------------------------
# Yüzey önbellekleri (OP-020 / DALGA D6):
# Editör açıkken her kare ~height adet draw.line (4K'ta 2160) + alt bar
# ~100 satır + kırpma overlay Surface'i + 2 smoothscale + resize ikonu
# DISK yükleme üretiliyordu (ölçüm: 18.0 ms/kare, SDL dummy — draw.line
# yalnız %65). Renk formülleri sabit olduğundan arka plan/alt bar
# (width, boyut) saf fonksiyonudur → modül LRU'su kalıcı yüzey üretir,
# her kare tek blit. Kırpma-bağımlı overlay/önizleme örnek-düzeyi LRU'dur
# (sürükleme karesi kendi anahtarıyla miss — bugünkü maliyetiyle üretir;
# boşta kalan kareler hit). İkon bir kez yüklenir (kare-döngüsünde I/O
# yasağı). Geometri anahtarları çözünürlük değişimini kapsar; içerik hiç
# bir kancaya bağlı olmadığından invalidasyon gerekmez (görüntü değişimi
# load_image'te örnek cache'leri temizlenerek kapanır).
_BG_GRADIENT_CACHE: dict = {}
_BG_GRADIENT_CACHE_ORDER: list = []
_BG_GRADIENT_CACHE_MAX = 4

_BOTTOM_BAR_GRADIENT_CACHE: dict = {}
_BOTTOM_BAR_GRADIENT_CACHE_ORDER: list = []
_BOTTOM_BAR_GRADIENT_CACHE_MAX = 4

_RESIZE_ICON_CACHE: dict = {}


def _lru_get(cache: dict, order: list, key: tuple):
    value = cache.get(key)
    if value is not None:
        order.remove(key)
        order.append(key)
    return value


def _lru_set(cache: dict, order: list, key: tuple, value, max_items: int) -> None:
    if key in cache:
        order.remove(key)
    cache[key] = value
    order.append(key)
    while len(order) > max_items:
        old_key = order.pop(0)
        cache.pop(old_key, None)


def _get_bg_gradient_surface(width: int, height: int) -> pygame.Surface:
    """Tam-ekran dikey gradyan arka planı — LRU 4 (OP-020 / D6).

    İçerik (width, height)'in saf fonksiyonu (renk formülleri sabit);
    üretimde bir kez çizilir, kare başına tek blit kalır.
    """
    key = (int(width), int(height))
    cached = _lru_get(_BG_GRADIENT_CACHE, _BG_GRADIENT_CACHE_ORDER, key)
    if cached is not None:
        return cached
    surface = pygame.Surface(key)
    for i in range(key[1]):
        color_r = int(10 + (i / key[1]) * 15)
        color_g = int(15 + (i / key[1]) * 20)
        color_b = int(30 + (i / key[1]) * 25)
        pygame.draw.line(surface, (color_r, color_g, color_b), (0, i), (key[0], i))
    _lru_set(_BG_GRADIENT_CACHE, _BG_GRADIENT_CACHE_ORDER, key, surface,
             _BG_GRADIENT_CACHE_MAX)
    return surface


def _get_bottom_bar_gradient_surface(width: int, denom: float) -> pygame.Surface:
    """Alt bar gradyanı — LRU 4 (OP-020 / D6).

    Satır sayısı int(denom), alfa eğrisi i/denom — MEVCUT formüllerin
    birebir kopyası (kesirli ölçekte payda farkı piksel değiştirir; anahtar
    tam float paydayı taşır).
    """
    bar_px = int(denom)
    key = (int(width), float(denom))
    cached = _lru_get(_BOTTOM_BAR_GRADIENT_CACHE, _BOTTOM_BAR_GRADIENT_CACHE_ORDER, key)
    if cached is not None:
        return cached
    surface = pygame.Surface((int(width), bar_px))
    for i in range(bar_px):
        alpha = 1 - (i / denom)
        color = (int(20 * alpha), int(25 * alpha), int(40 * alpha))
        pygame.draw.line(surface, color, (0, i), (int(width), i))
    _lru_set(_BOTTOM_BAR_GRADIENT_CACHE, _BOTTOM_BAR_GRADIENT_CACHE_ORDER, key,
             surface, _BOTTOM_BAR_GRADIENT_CACHE_MAX)
    return surface


def _get_resize_icon() -> pygame.Surface | None:
    """Resize oku ikonu — süreç başına bir kez (OP-020 / D6).

    Eski yol emoji_surface None dönerse fallback HER KARE dosyadan
    yüklüyordu (image.load + pathlib.resolve + stat oyun döngüsünde).
    """
    # None da önbelleklenir: 'in' denetimi miss'ten ayırt eder (None iken
    # dosya denemesi kare-döngüsünde tekrar etmez).
    if 'resize_arrow_16' in _RESIZE_ICON_CACHE:
        return _RESIZE_ICON_CACHE['resize_arrow_16']
    icon = None
    try:
        from emoji_renderer import emoji_surface
        icon = emoji_surface('↘', 16)
    except Exception:
        icon = None
    if icon is None:
        try:
            from pathlib import Path
            _rp = Path(__file__).resolve().parent.parent / 'assets' / 'emoji' / 'resize_arrow.png'
            if _rp.exists():
                icon = pygame.image.load(str(_rp)).convert_alpha()
                icon = pygame.transform.smoothscale(icon, (16, 16))
        except Exception:
            icon = None
    _RESIZE_ICON_CACHE['resize_arrow_16'] = icon
    return icon


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

            # Görüntü değişti — kırpma-bağımlı örnek cache'leri düşür (OP-020 / D6)
            self._clear_image_layout_caches()

            return True
        except Exception as e:
            print(f"Resim yüklenirken hata: {e}")
            return False
    
    def _clamp_crop(self):
        """Kırpma karesini resim sınırları içinde tut"""
        if self.display_image:
            img_w, img_h = self.display_image.get_size()
            # Kare BOYUTU da görüntüye sığdırılır (v2 uyarlaması): varsayılan
            # 300px'lik kare alçak pencerelerde (yükseklik < 600 → görüntü kısa
            # kenarı 300'ün altında ölçeklenir) her yüklemede görüntüden büyük
            # başlıyordu ve get_cropped_image kaynak-dışı bölge blit'leyip
            # avatarı bozuyordu; +/- tuşları da kareyi görüntünün dışına
            # büyütebiliyordu. min_crop_size tabanı korunur (aşırı ince
            # görüntülerde kare yine görüntüden büyük kalabilir — bilinen sınır).
            self.crop_size = max(self.min_crop_size, min(self.crop_size, min(img_w, img_h)))
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
        # Çizim sözleşmesi kaydı (containment regresyon testleri): rect'ler
        # zaten hesaplanmış nesneler — kare başına yalnızca küçük bir dict
        # tutulur, yeni Surface/font tahsisi yok (v2 _draw_layout deseni,
        # v2 uyarlaması).
        layout = self._draw_layout = {}
        layout['has_image'] = self.display_image is not None
        
        # Koyu gradient arka plan — (width, height) saf fonksiyonu; kalıcı
        # yüzeye bir kez üretilir, her kare tek blit (OP-020 / D6).
        self.screen.blit(_get_bg_gradient_surface(width, height), (0, 0))
        
        # Başlık
        title = self.font_title.render(t('avatar_edit_title'), True, WHITE)
        title_rect = title.get_rect(center=(width // 2, 50))
        layout['title'] = title_rect
        self.screen.blit(title, title_rect)
        
        if self.display_image:
            # Resmi göster
            img_w, img_h = self.display_image.get_size()
            img_x = width // 2 - img_w // 2
            img_y = 150
            
            # Resim arka plan
            bg_rect = pygame.Rect(img_x - 10, img_y - 10, img_w + 20, img_h + 20)
            layout['image_bg'] = bg_rect
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
            
            layout['crop'] = crop_rect

            # Karanlık overlay (kırpma dışı alan) — kırpma geometrisi
            # anahtarlı LRU; sürükleme karesi miss, boşta kalan hit (OP-020 / D6).
            overlay = self._get_crop_overlay_surface()

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
            
            layout['resize_handle'] = resize_handle

            # Resize tutamacı - daha belirgin
            pygame.draw.rect(self.screen, (255, 200, 0), resize_handle, border_radius=5)
            pygame.draw.rect(self.screen, (255, 255, 100), resize_handle, 3, border_radius=5)
            
            # Resize ikonu — süreç başına bir kez yüklenir (OP-020 / D6).
            _resize_ic = _get_resize_icon()
            if _resize_ic:
                _ir = _resize_ic.get_rect(center=resize_handle.center)
                self.screen.blit(_resize_ic, _ir)
            
            # Boyut göstergesi (karenin üzerinde)
            size_text = f'{self.crop_size}x{self.crop_size} px'
            size_surf = self.font_small.render(size_text, True, (255, 255, 100))
            size_bg_rect = pygame.Rect(crop_rect.centerx - 60, crop_rect.top - 35, 120, 30)
            layout['size_badge'] = size_bg_rect
            pygame.draw.rect(self.screen, (40, 50, 70), size_bg_rect, border_radius=8)
            pygame.draw.rect(self.screen, BLUE, size_bg_rect, 2, border_radius=8)
            size_rect = size_surf.get_rect(center=size_bg_rect.center)
            self.screen.blit(size_surf, size_rect)
            
            # Önizleme (sağ üst köşe)
            preview_size = 150  # Biraz daha büyük
            preview_x = width - preview_size - 50
            preview_y = 150
            # (v2 uyarlaması) dar/uzun pencerede önizleme görüntü PANELİNE
            # binmesin: panelin sağ kenarından sonraya sıkıştırılır; ekran
            # sınırı önceliklidir (aşırı uzun pencerelerde bindirme bilinen
            # sınırdır).
            preview_x = max(preview_x, min(bg_rect.right + 12,
                                           width - preview_size - 10))
            
            # Kırpılmış alanı al — kırpma + önizleme boyutu anahtarlı LRU;
            # sürükleme karesi miss, boşta kalan hit (OP-020 / D6).
            preview_img = self._get_preview_surface(preview_size)
            if preview_img:

                # Önizleme arka plan
                preview_bg = pygame.Rect(preview_x - 10, preview_y - 10, preview_size + 20, preview_size + 20)
                layout['preview_bg'] = preview_bg
                pygame.draw.rect(self.screen, (50, 60, 80), preview_bg, border_radius=15)
                pygame.draw.rect(self.screen, GREEN, preview_bg, 3, border_radius=15)
                
                self.screen.blit(preview_img, (preview_x, preview_y))
                
                # Önizleme label
                preview_label = self.font_small.render(t('avatar_preview'), True, WHITE)
                preview_label_rect = preview_label.get_rect(center=(preview_x + preview_size // 2, preview_y - 25))
                layout['preview_label'] = preview_label_rect
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
        layout['bottom_bar_y'] = bottom_bar_y
        
        # Gradient alt bar — (width, boyut) saf fonksiyonu; tek blit (OP-020 / D6).
        self.screen.blit(_get_bottom_bar_gradient_surface(width, 100), (0, bottom_bar_y))

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
        
        # Gerçek satır genişliğiyle ortala (v2 uyarlaması): eski kod tüm
        # slotları 160px varsayıp 940px'lik toplamla ortalamıştı — 640/800
        # genişlikte buton barı iki uçtan da ekrana taşıyordu (başlangıç
        # x'i -150'ye, son butonun sağı 745'e düşüyordu). Adım da sabit
        # 165 yerine gerçek key_width + 5'tir (v2'nin scale=1 formülü).
        key_widths = [160 if len(k) > 8 else (100 if len(k) > 5 else 70) for k, _l, _c in buttons]
        total_width = sum(key_widths) + 5 * (len(buttons) - 1)
        button_x = width // 2 - total_width // 2
        button_y = bottom_bar_y + 10
        
        button_rects = []
        button_label_rects = []
        for key, label, color in buttons:
            key_width = 160 if len(key) > 8 else (100 if len(key) > 5 else 70)
            key_bg = pygame.Rect(button_x, button_y, key_width, 40)
            button_rects.append(key_bg)
            
            # Buton devre dışıysa gri yap
            if label == 'Kaydet' and not self.display_image:
                color = (100, 100, 100)
            
            pygame.draw.rect(self.screen, color, key_bg, border_radius=8)
            pygame.draw.rect(self.screen, tuple(min(255, c + 40) for c in color), key_bg, 2, border_radius=8)
            
            key_surf = self.font_small.render(key, True, WHITE)
            self.screen.blit(key_surf, key_surf.get_rect(center=key_bg.center))
            
            label_surf = self.font_small.render(label, True, (180, 180, 180))
            label_rect = label_surf.get_rect(midtop=(button_x + key_width // 2, button_y + 45))
            button_label_rects.append(label_rect)
            self.screen.blit(label_surf, label_rect)
            
            button_x += key_width + 5

        layout['buttons'] = button_rects
        layout['button_labels'] = button_label_rects

    def _clear_image_layout_caches(self) -> None:
        """Görüntü değişince kırpma-bağımlı yüzey cache'lerini düşür (OP-020 / D6)."""
        self._crop_overlay_cache = {}
        self._crop_overlay_cache_order = []
        self._preview_cache = {}
        self._preview_cache_order = []

    def _get_crop_overlay_surface(self) -> pygame.Surface:
        """Kırpma-dışı karartma yüzeyi — örnek LRU 8 (OP-020 / D6).

        İçerik (display boyutu, crop_x, crop_y, crop_size)'un saf
        fonksiyonu: SRCALPHA fill(0,0,0,120) + kırpma alanının (0,0,0,0)
        ile temizlenmesi (mevcut deyim birebir). Sürükleme karesi yeni
        anahtarla miss olur ve bugünkü maliyetiyle üretir; boşta kalan
        kareler tek blit'e iner.
        """
        img_w, img_h = self.display_image.get_size()
        key = (img_w, img_h, int(self.crop_x), int(self.crop_y), int(self.crop_size))
        cache = getattr(self, '_crop_overlay_cache', None)
        if cache is None:
            cache = self._crop_overlay_cache = {}
            self._crop_overlay_cache_order = []
        cached = _lru_get(cache, self._crop_overlay_cache_order, key)
        if cached is not None:
            return cached
        overlay = pygame.Surface((img_w, img_h), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 120))
        # Kırpma alanını temizle
        clear_rect = pygame.Rect(self.crop_x, self.crop_y, self.crop_size, self.crop_size)
        pygame.draw.rect(overlay, (0, 0, 0, 0), clear_rect)
        _lru_set(cache, self._crop_overlay_cache_order, key, overlay, 8)
        return overlay

    def _get_preview_surface(self, preview_size: int):
        """Önizleme yüzeyi — örnek LRU 8 (OP-020 / D6).

        get_cropped_image (kırp + 128'e smoothscale) + preview boyutuna
        smoothscale zinciri; kırpma geometrisi ve önizleme boyutunun saf
        fonksiyonu. get_cropped_image yalnız miss yolunda koşar —
        save_avatar kendi çağrısında her zaman taze üretir.
        """
        img_w, img_h = self.display_image.get_size()
        key = (img_w, img_h, int(self.crop_x), int(self.crop_y),
               int(self.crop_size), int(preview_size))
        cache = getattr(self, '_preview_cache', None)
        if cache is None:
            cache = self._preview_cache = {}
            self._preview_cache_order = []
        cached = _lru_get(cache, self._preview_cache_order, key)
        if cached is not None:
            return cached
        cropped = self.get_cropped_image()
        if not cropped:
            return None
        # SMOOTHSCALE ile kaliteli önizleme
        preview_img = pygame.transform.smoothscale(cropped, (int(preview_size), int(preview_size)))
        _lru_set(cache, self._preview_cache_order, key, preview_img, 8)
        return preview_img

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
