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


class GameplaySettingsMenu:
    """Oynanış ayarları ekranı - DAS, hız ayarları"""
    
    def __init__(self, screen, settings_manager):
        """Oynanış menüsünü başlat"""
        self.screen = screen
        self.settings_manager = settings_manager

        # Arka plan efektleri (ayar ekranları ile tutarlı düşen bloklar)
        self.background_fx = get_shared_falling_blocks_layer('default')
        
        # Fontlar (retro_style ile uyumlu)
        self.font_title = retro_style.get_font(48)
        self.font_option = retro_style.get_font(28)
        self.font_value = retro_style.get_font(24, bold=False)
        self.font_hint = retro_style.get_font(20, bold=False)
        self.font_small = retro_style.get_font(18, bold=False)
        
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

    def _layout_metrics(self):
        width, height = self.screen.get_size()
        card_width = min(620, width - 120)
        card_height = 74
        spacing = 82
        return card_width, card_height, spacing

    def _max_scroll(self, title_rect_bottom: int, height: int) -> int:
        _, _, spacing = self._layout_metrics()
        top_padding = 40
        bottom_limit = 160
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
        title_rect_bottom = 70 + 48
        visible_height = max(1, (height - 160) - (title_rect_bottom + 40))

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
            self.scroll_offset -= event.y * 30
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
        
        # Başlık
        title_rect = retro_style.draw_title(self.screen, t('gameplay_settings'), (width // 2, 70), emoji='🎮')
        
        # Ayar kartları
        self.option_rects = []
        card_width, card_height, spacing = self._layout_metrics()
        start_y = title_rect.bottom + 40 - self.scroll_offset
        
        for i, setting in enumerate(self.settings):
            y_pos = start_y + i * spacing
            
            # Ekran dışındaysa çizme
            if y_pos < title_rect.bottom + 10 or y_pos > height - 160:
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
            
            # Açıklama (alt satır) - dinamik çeviri ile
            if is_selected:
                desc_surf = self.font_small.render(setting['desc'], True, (180, 190, 210))
                desc_rect = desc_surf.get_rect(midleft=(rect.x + 20, rect.bottom + 12))
                self.screen.blit(desc_surf, desc_rect)
        
        # Geri butonu
        geri_y = start_y + len(self.settings) * spacing
        if geri_y >= title_rect.bottom + 10 and geri_y <= height - 160:
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
