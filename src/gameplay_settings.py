"""
Oynanış Ayarları Menüsü - DAS, hareket hızı, düşme hızı ayarları

Ana menü temasıyla (retro_style) uyumlu tasarım.
"""

import pygame
from constants import *
from retro_style import retro_style
from platform_utils import is_fullscreen_toggle, normalize_mouse_pos
from background_effects import get_shared_falling_blocks_layer
from localization import t
from ui_scaling import (
    get_projected_effective_scale,
    get_virtual_canvas_ui_scale,
    is_virtual_canvas_active,
    scale_px,
)
from ui_text_layout import wrap_text_limited


class GameplaySettingsMenu:
    """Oynanış ayarları ekranı - DAS, hız ayarları"""
    
    def __init__(self, screen, settings_manager):
        """Oynanış menüsünü başlat"""
        self.screen = screen
        self.settings_manager = settings_manager

        # Arka plan efektleri (ayar ekranları ile tutarlı düşen bloklar)
        self.background_fx = get_shared_falling_blocks_layer('default')
        
        # Fontlar (retro_style ile uyumlu) — ortak UI ölçeğine duyarlı (P1-9):
        # taban boyut × ölçek; retro_style.get_font LRU'su aynı boyuta aynı
        # Font nesnesini döndürür (kare-başı tahsis yok).
        self._font_scale = None
        self._font_small_size = 18
        self._refresh_fonts_if_needed()
        
        # Mevcut ayarları yükle
        self.das_delay = settings_manager.get('das_delay', 170)
        self.das_repeat = settings_manager.get('das_repeat', 50)
        self.soft_drop_speed = settings_manager.get('soft_drop_speed', 50)
        
        # Ayar tanımları - dinamik çeviri için key'ler kullanılacak
        self._setting_keys = ['das_delay', 'das_repeat', 'soft_drop_speed']
        self._setting_defaults = {
            'das_delay': {'min': 50, 'max': 300, 'step': 10, 'suffix': 'ms', 'value': self.das_delay},
            'das_repeat': {'min': 10, 'max': 500, 'step': 5, 'suffix': 'ms', 'value': self.das_repeat},
            'soft_drop_speed': {'min': 20, 'max': 100, 'step': 5, 'suffix': 'ms', 'value': self.soft_drop_speed},
        }
        
        self.selected = 0
        self.option_rects = []
        self.desc_rects = []
        self.scroll_offset = 0

    @property
    def settings(self):
        """Dinamik olarak çevirilmiş ayar listesini döndür"""
        result = []
        for key in self._setting_keys:
            defaults = self._setting_defaults[key]
            result.append({
                'key': key,
                'label': t(key),
                'desc': t(f'{key}_desc'),
                'min': defaults['min'],
                'max': defaults['max'],
                'step': defaults['step'],
                'suffix': defaults['suffix'],
                'value': defaults['value'],
            })
        return result

    def _ui_scale(self, min_scale: float = 0.72, max_scale: float = 1.24) -> float:
        """Ortak UI ölçeği (graphics_menu ile aynı profil: 1366x768 referans).

        P1-9: ölçek kaynağı get_projected_effective_scale — komşu ayar
        ekranları hangi profille kullanıyorsa bu ekran da aynı ölçeği alır;
        sanal tuval aktifken tuval ölçeği doğrudan döner.
        """
        _vc = get_virtual_canvas_ui_scale()
        if _vc is not None:
            return _vc
        return get_projected_effective_scale(
            self.screen,
            min_scale=min_scale,
            max_scale=max_scale,
            reference_size=(1366.0, 768.0),
        )

    def _s(self, value, minimum=1, *, scale=None):
        """Değeri ortak UI ölçeğiyle piksele çevir (taban: minimum)."""
        if is_virtual_canvas_active():
            return max(minimum, int(round(float(value))))
        active_scale = self._ui_scale() if scale is None else float(scale)
        return scale_px(value, active_scale, minimum=minimum)

    def _refresh_fonts_if_needed(self):
        """Ortak UI ölçeği değiştiyse (pencere boyutu/preset) fontları tazele.

        retro_style.get_font LRU'su aynı boyuta aynı Font nesnesini verir;
        ölçek değişmedikçe bu çağrı tahsis üretmez.
        """
        scale = self._ui_scale()
        if getattr(self, '_font_scale', None) == scale:
            return
        self._font_scale = scale
        self._font_small_size = self._s(18, minimum=11, scale=scale)
        self.font_title = retro_style.get_font(self._s(48, minimum=30, scale=scale))
        self.font_option = retro_style.get_font(self._s(28, minimum=18, scale=scale))
        self.font_value = retro_style.get_font(self._s(24, minimum=16, scale=scale), bold=False)
        self.font_hint = retro_style.get_font(self._s(20, minimum=13, scale=scale), bold=False)
        self.font_small = retro_style.get_font(self._font_small_size, bold=False)

    def _layout_metrics(self):
        width, height = self.screen.get_size()
        scale = self._ui_scale()
        # P1-9: taban (620/74/82) × ölçek, okunabilirlik tabanlarıyla;
        # genişlik bütçesi ekran kenar payını da ölçekler.
        card_width = min(
            self._s(620, minimum=420, scale=scale),
            width - self._s(120, minimum=60, scale=scale),
        )
        card_height = self._s(74, minimum=56, scale=scale)
        spacing = self._s(82, minimum=62, scale=scale)
        return card_width, card_height, spacing

    def _selected_desc_lines(self, rect):
        """Seçili ayarın açıklamasını kart içi bütçeye sığdır (ölç-önce).

        Sözleşme (P1-9): satır bütçesi = kart iç yüksekliği - başlık bandı
        (tek satır şerit); genişlik bütçesi = kart iç genişliği - pad.
        wrap_text_limited önce sarmaya çalışır, sığmazsa ASCII '...' ile
        kısaltır (emoji yasak - CLAUDE.md).
        """
        if self.selected >= len(self.settings):
            return []
        desc = self.settings[self.selected].get('desc') or ''
        if not desc:
            return []
        pad_x = self._s(20, minimum=14)
        max_w = max(8, rect.width - 2 * pad_x)
        return wrap_text_limited(desc, self.font_small, max_w, max_lines=1).lines

    def _draw_selected_desc(self, rect):
        """Seçili ayarın açıklamasını kart içi alt şerite çiz (P1-9).

        Şerit, draw_setting_row'un dikey ortalanmış başlık bandının ALTINDA
        başlar ve kartın alt kenarını aşmaz. Render retro_style.render_fit_text
        LRU önbelleğinden (kare-başı Surface tahsisi yok); ölçüm
        wrap_text_limited önbelleğinden.
        """
        lines = self._selected_desc_lines(rect)
        text = lines[0] if lines else ''
        if not text:
            return None
        line_h = self.font_small.get_height()
        label_band_h = retro_style.get_font(26, bold=True).get_height()
        label_bottom = rect.y + (rect.height + label_band_h) // 2
        inset = self._s(6, minimum=4)
        # Öncelik: (a) kart alt kenarını aşma, (b) başlık bandının altında
        # başla, (c) kart üst kenarının üstüne çıkma (aşırı küçük kart).
        top = max(rect.y, min(max(label_bottom + 1, rect.bottom - inset - line_h), rect.bottom - line_h))
        desc_rect = pygame.Rect(rect.x + self._s(20, minimum=14), top, max(1, rect.width - 2 * self._s(20, minimum=14)), line_h)
        surf = retro_style.render_fit_text(
            text, (180, 190, 210), None, self._font_small_size, bold=False,
        )
        self.screen.blit(surf, surf.get_rect(midleft=(desc_rect.x, desc_rect.centery)))
        return desc_rect

    def _max_scroll(self, title_rect_bottom: int, height: int) -> int:
        _, _, spacing = self._layout_metrics()
        # P1-9: dikey dolgu/alt kesit sabitleri de ortak ölçekle.
        top_padding = self._s(40, minimum=28)
        bottom_limit = self._s(160, minimum=120)
        visible_h = max(0, (height - bottom_limit) - (title_rect_bottom + top_padding))
        total_h = (len(self.settings) + 1) * spacing
        return max(0, total_h - max(visible_h, 0))

    def _format_value(self, setting, current_value):
        if setting.get('type') == 'toggle':
            return (
                t('on').upper() if current_value else t('off').upper(),
                (100, 255, 100) if current_value else (255, 100, 100),
            )

        suffix = setting.get('suffix', '')
        # Use readable spacing: "170 ms" instead of "170ms"
        unit = f" {suffix}" if suffix else ''
        return (f"< {int(current_value)}{unit} >", (100, 200, 255))
    
    def _get_setting_value(self, setting):
        """Ayar değerini al"""
        key = setting['key']
        if key == 'das_delay':
            return self.das_delay
        elif key == 'das_repeat':
            return self.das_repeat
        elif key == 'soft_drop_speed':
            return self.soft_drop_speed
        return setting.get('value', 0)
    
    def _set_setting_value(self, setting, value):
        """Ayar değerini güncelle"""
        key = setting['key']
        if key == 'das_delay':
            self.das_delay = value
            self._setting_defaults['das_delay']['value'] = value
        elif key == 'das_repeat':
            self.das_repeat = value
            self._setting_defaults['das_repeat']['value'] = value
        elif key == 'soft_drop_speed':
            self.soft_drop_speed = value
            self._setting_defaults['soft_drop_speed']['value'] = value
        
        self.settings_manager.set(key, value)
    
    def _adjust_value(self, delta):
        """Seçili ayarın değerini değiştir"""
        if self.selected >= len(self.settings):
            return
        
        setting = self.settings[self.selected]
        current = self._get_setting_value(setting)
        
        if setting.get('type') == 'toggle':
            # Toggle için değeri tersine çevir
            self._set_setting_value(setting, not current)
        else:
            # Sayısal değer için artır/azalt
            step = setting.get('step', 1)
            min_val = setting.get('min', 0)
            max_val = setting.get('max', 1000)
            
            new_value = current + (step * delta)
            new_value = max(min_val, min(max_val, new_value))
            self._set_setting_value(setting, new_value)

    def _ensure_visible(self):
        """Seçili satırı görünür bölgede tut."""
        _, card_height, spacing = self._layout_metrics()
        height = self.screen.get_height()
        # Başlık (draw_title) ölçeklenmez → sabit yaklaşık alt kenar.
        title_rect_bottom = 70 + 48
        visible_height = max(
            1,
            (height - self._s(160, minimum=120)) - (title_rect_bottom + self._s(40, minimum=28)),
        )

        item_y = self.selected * spacing
        if item_y < self.scroll_offset:
            self.scroll_offset = item_y
        elif item_y + card_height > self.scroll_offset + visible_height:
            self.scroll_offset = item_y + card_height - visible_height

        self.scroll_offset = max(0, min(self.scroll_offset, self._max_scroll(title_rect_bottom, height)))
    
    def handle_input(self, event):
        """Input işle"""
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.settings_manager.save_settings()
                return 'back'
            elif event.key == pygame.K_UP:
                self.selected = (self.selected - 1) % (len(self.settings) + 1)  # +1 for Geri
                self._ensure_visible()
            elif event.key == pygame.K_DOWN:
                self.selected = (self.selected + 1) % (len(self.settings) + 1)
                self._ensure_visible()
            elif event.key == pygame.K_LEFT:
                self._adjust_value(-1)
            elif event.key == pygame.K_RIGHT:
                self._adjust_value(1)
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                if self.selected == len(self.settings):  # Geri butonu
                    self.settings_manager.save_settings()
                    return 'back'
                else:
                    setting = self.settings[self.selected]
                    if setting.get('type') == 'toggle':
                        self._adjust_value(1)  # Toggle
            elif is_fullscreen_toggle(event.key, getattr(event, 'mod', 0)):
                return 'toggle_fullscreen'
        
        elif event.type == pygame.MOUSEWHEEL:
            # Clamp based on current viewport
            self.scroll_offset -= event.y * self._s(30, minimum=18)
            width, height = self.screen.get_size()
            # Approximate title bottom (fixed title position)
            max_scroll = self._max_scroll(70 + 48, height)
            self.scroll_offset = max(0, min(self.scroll_offset, max_scroll))
        
        elif event.type == pygame.MOUSEMOTION:
            mouse_pos = normalize_mouse_pos(getattr(event, 'pos', None)) or event.pos
            for i, rect in enumerate(self.option_rects):
                if rect.collidepoint(mouse_pos):
                    self.selected = i
        
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                mouse_pos = normalize_mouse_pos(getattr(event, 'pos', None)) or event.pos
                for i, rect in enumerate(self.option_rects):
                    if rect.collidepoint(mouse_pos):
                        self.selected = i
                        if i == len(self.settings):  # Geri
                            self.settings_manager.save_settings()
                            return 'back'
                        else:
                            setting = self.settings[i]
                            if setting.get('type') == 'toggle':
                                self._adjust_value(1)
        
        return None
    
    def update(self, dt):
        """UI güncelle (boş - animasyon yok)"""
        pass
    
    def draw(self):
        """Oynanış ayarları menüsünü çiz - Retro tema ile uyumlu"""
        width, height = self.screen.get_size()
        
        # Arka plan (ana menü ile aynı)
        retro_style.draw_background(self.screen)
        self.background_fx.update(self.screen)
        self.background_fx.draw(self.screen)
        
        # Başlık (P1-9: ölü emoji argümanı kaldırıldı — draw_title zaten
        # yok sayıyordu; CLAUDE.md emoji yasağı)
        title_rect = retro_style.draw_title(self.screen, t('gameplay_settings'), (width // 2, 70))
        
        # Ayar kartları
        self.option_rects = []
        self.desc_rects = []
        self._refresh_fonts_if_needed()
        card_width, card_height, spacing = self._layout_metrics()
        start_y = title_rect.bottom + self._s(40, minimum=28) - self.scroll_offset
        
        for i, setting in enumerate(self.settings):
            y_pos = start_y + i * spacing
            
            # Ekran dışındaysa çizme
            if y_pos < title_rect.bottom + self._s(10, minimum=8) or y_pos > height - self._s(160, minimum=120):
                self.option_rects.append(pygame.Rect(0, 0, 0, 0))
                continue
            
            rect = pygame.Rect(width // 2 - card_width // 2, y_pos, card_width, card_height)
            self.option_rects.append(rect)
            
            is_selected = i == self.selected
            
            # Değer ve renk
            current_value = self._get_setting_value(setting)
            value_text, value_color = self._format_value(setting, current_value)
            
            # Strip rengi
            strip_color = (100, 220, 150)  # Yeşil - gameplay teması
            
            # Kart çiz
            retro_style.draw_setting_row(
                self.screen,
                rect,
                setting['label'],
                value_text,
                selected=is_selected,
                label_color=(255, 255, 255) if is_selected else (200, 200, 200),
                value_color=value_color,
                strip_color=strip_color,
                kind='toggle' if setting.get('type') == 'toggle' else 'selector',
            )
            
            # Açıklama (seçili kartta kart içi alt şerit) - dinamik çeviri ile
            # P1-9: kart içi bütçe (wrap + ASCII ellipsis), ölçüm ve render
            # önbellekli; konum başlık bandının altında, kart sınırında.
            if is_selected:
                desc_rect = self._draw_selected_desc(rect)
                if desc_rect is not None:
                    self.desc_rects.append(desc_rect)
        
        # Geri butonu
        geri_y = start_y + len(self.settings) * spacing
        if geri_y >= title_rect.bottom + self._s(10, minimum=8) and geri_y <= height - self._s(160, minimum=120):
            geri_rect = pygame.Rect(width // 2 - card_width // 2, geri_y, card_width, card_height)
            self.option_rects.append(geri_rect)
            
            is_geri_selected = self.selected == len(self.settings)
            retro_style.draw_button(
                self.screen,
                geri_rect,
                '← ' + t('back'),
                selected=is_geri_selected,
                strip_color=(255, 100, 120),  # Kırmızı - geri
            )
        else:
            self.option_rects.append(pygame.Rect(0, 0, 0, 0))
