"""Grafik ayarları menüsü"""
import pygame
from constants import *
from retro_style import retro_style
from platform_utils import is_fullscreen_toggle, normalize_mouse_pos
from background_effects import get_shared_falling_blocks_layer
from localization import t


class GraphicsMenu:
    """Grafik ayarları ekranı"""
    
    def __init__(self, screen, settings_manager):
        """Grafik menüsünü başlat"""
        self.screen = screen
        self.settings_manager = settings_manager
        self.font_hint = retro_style.get_font(20, bold=False)

        # Arka plan efektleri (ayarlar ekranı ile tutarlı düşen bloklar)
        self.background_fx = get_shared_falling_blocks_layer('default')
        
        # Options artık property ile dinamik olarak alınacak
        self._option_keys = [
            'window_mode',
            'resolution',
            'vsync',
            'fps_limit',
            'show_ghost',
            'show_background',
            'bg_transparency',
            'menu_transparency',
            'particle_effects',
            'back'
        ]
        self.selected = 0
        self.option_rects = []
        
        # Mevcut ayarları yükle (varsayılanlar settings_manager ile aynı olmalı)
        self.fullscreen = settings_manager.get('fullscreen', True)
        self.resolution = settings_manager.get('resolution', 'auto')
        self.vsync = settings_manager.get('vsync', True)
        self.fps_limit = settings_manager.get('fps_limit', 0)  # 0 = MAX (sınırsız)
        self.show_ghost = settings_manager.get('show_ghost', True)
        self.background_enabled = settings_manager.get('background_enabled', True)
        self.bg_transparency = settings_manager.get('bg_transparency', 0.3)
        self.menu_transparency = settings_manager.get('menu_transparency', 1.0)
        self.particle_effects = settings_manager.get('particle_effects', False)  # Varsayılan kapalı

        # Track settings as they were when entering this menu. Some settings
        # (like VSYNC/FPS display) don't need a display rebuild, and rebuilding
        # the window on macOS can trigger SDL/Cocoa edge-case crashes.
        self._initial_fullscreen = self.fullscreen
        self._initial_resolution = self.resolution
        
        # Çözünürlük seçenekleri
        self.resolutions = ['auto', '800x600', '1024x768', '1280x720', '1366x768', '1920x1080']

        # FPS limit seçenekleri (0 = MAX/Sınırsız, VSync varsa monitör Hz ile sınırlanır)
        self.fps_limits = [0, 60, 90, 120, 144, 240]
        
        self.scroll_offset = 0

        # VSync changes require restart (SDL hint/env is read on init).
        self._vsync_restart_prompt_active = False
        self._vsync_restart_choice = 0  # 0: restart now, 1: later
        self._vsync_prompt_buttons: list[pygame.Rect] = []
    
    @property
    def options(self):
        """Dil değiştiğinde dinamik olarak çevirilmiş seçenekleri döndür"""
        return [t(key) for key in self._option_keys]
    
    def handle_input(self, event):
        """Grafik menüsü input işle"""
        if self._vsync_restart_prompt_active:
            return self._handle_vsync_prompt_input(event)

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_UP:
                self.selected = (self.selected - 1) % len(self.options)
            elif event.key == pygame.K_DOWN:
                self.selected = (self.selected + 1) % len(self.options)
            elif event.key in (pygame.K_LEFT, pygame.K_RIGHT):
                action = self._change_setting(event.key == pygame.K_RIGHT)
                if action:
                    return action
            elif event.key == pygame.K_RETURN or event.key == pygame.K_SPACE:
                if self.selected == len(self.options) - 1:  # Geri
                    return 'back'
                else:
                    action = self._toggle_setting()
                    if action:
                        return action
            elif event.key == pygame.K_ESCAPE:
                return 'back'
            elif is_fullscreen_toggle(event.key, getattr(event, 'mod', 0)):
                return 'toggle_fullscreen'
        
        elif event.type == pygame.MOUSEWHEEL:
            self.scroll_offset -= event.y * 30
            self.scroll_offset = max(0, min(self.scroll_offset, self._max_scroll()))
        
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
                        if i == len(self.options) - 1:
                            return 'back'
                        else:
                            action = self._toggle_setting()
                            if action:
                                return action
        
        return None

    def _handle_vsync_prompt_input(self, event):
        """VSync restart popup input."""
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_LEFT, pygame.K_UP):
                self._vsync_restart_choice = 0
            elif event.key in (pygame.K_RIGHT, pygame.K_DOWN):
                self._vsync_restart_choice = 1
            elif event.key in (pygame.K_ESCAPE,):
                self._vsync_restart_prompt_active = False
                return None
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                if self._vsync_restart_choice == 0:
                    self._vsync_restart_prompt_active = False
                    return 'restart_now'
                self._vsync_restart_prompt_active = False
                return None

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = normalize_mouse_pos(getattr(event, 'pos', None)) or getattr(event, 'pos', (0, 0))
            if self._vsync_prompt_buttons and len(self._vsync_prompt_buttons) == 2:
                if self._vsync_prompt_buttons[0].collidepoint(pos):
                    self._vsync_restart_prompt_active = False
                    return 'restart_now'
                if self._vsync_prompt_buttons[1].collidepoint(pos):
                    self._vsync_restart_prompt_active = False
                    return None

        return None
    
    def _toggle_setting(self):
        """Seçili ayarı değiştir"""
        if self.selected == 0:  # Pencere Modu
            self.fullscreen = not self.fullscreen
            self.settings_manager.set('fullscreen', self.fullscreen)
            return 'apply_display_mode'  # Display'i yeniden oluştur
        elif self.selected == 2:  # VSync
            self.vsync = not self.vsync
            self.settings_manager.set('vsync', self.vsync)
            # Show restart-required prompt.
            self._vsync_restart_prompt_active = True
            self._vsync_restart_choice = 0
        elif self.selected == 4:  # Gölge Göster
            self.show_ghost = not self.show_ghost
            self.settings_manager.set('show_ghost', self.show_ghost)
        elif self.selected == 5:  # Arka Plan Göster
            self.background_enabled = not self.background_enabled
            self.settings_manager.set('background_enabled', self.background_enabled)
            return 'toggle_background_enabled'
        elif self.selected == 8:  # Parçacık Efektleri
            self.particle_effects = not self.particle_effects
            self.settings_manager.set('particle_effects', self.particle_effects)

        return None

    
    def _change_setting(self, increase=True):
        """Ayarı artır/azalt (ok tuşları ile)"""
        if self.selected == 1:  # Çözünürlük (Pencere Boyutu)
            idx = self.resolutions.index(self.resolution)
            if increase:
                idx = (idx + 1) % len(self.resolutions)
            else:
                idx = (idx - 1) % len(self.resolutions)
            self.resolution = self.resolutions[idx]
            self.settings_manager.set('resolution', self.resolution)
            # Pencere modundaysa display'i güncelle
            if not self.fullscreen:
                return 'apply_display_mode'

        elif self.selected == 3:  # FPS Limiti
            current = self.fps_limit
            if current not in self.fps_limits:
                current = 0
            idx = self.fps_limits.index(current)
            if increase:
                idx = (idx + 1) % len(self.fps_limits)
            else:
                idx = (idx - 1) % len(self.fps_limits)
            self.fps_limit = int(self.fps_limits[idx])
            self.settings_manager.set('fps_limit', self.fps_limit)
        
        elif self.selected == 6:  # Arka Plan Şeffaflığı
            if increase:
                self.bg_transparency = min(1.0, float(self.bg_transparency) + 0.1)
            else:
                self.bg_transparency = max(0.0, float(self.bg_transparency) - 0.1)
            self.settings_manager.set('bg_transparency', round(self.bg_transparency, 1))
            return 'change_bg_transparency'

        elif self.selected == 7:  # Menü Şeffaflığı
            if increase:
                self.menu_transparency = min(1.0, float(self.menu_transparency) + 0.1)
            else:
                self.menu_transparency = max(0.0, float(self.menu_transparency) - 0.1)
            self.settings_manager.set('menu_transparency', round(self.menu_transparency, 1))
            return 'change_menu_transparency'

        return None
    
    def draw(self):
        """Grafik menüsünü çiz - Oynanış stili ile uyumlu"""
        width, height = self.screen.get_size()
        retro_style.draw_background(self.screen)
        self.background_fx.update(self.screen)
        self.background_fx.draw(self.screen)

        title_rect = retro_style.draw_title(self.screen, t('graphics_settings'), (width // 2, 70), emoji='⚙')

        self.option_rects = []
        card_width = min(620, width - 120)
        card_height = 74
        spacing = 82

        max_scroll = self._max_scroll()
        self.scroll_offset = max(0, min(self.scroll_offset, max_scroll))
        start_y = title_rect.bottom + 40 - self.scroll_offset

        for i, option in enumerate(self.options):
            y_pos = start_y + i * spacing
            if y_pos < title_rect.bottom + 10 or y_pos > height - 160:
                self.option_rects.append(pygame.Rect(0, 0, 0, 0))
                continue

            rect = pygame.Rect(width // 2 - card_width // 2, y_pos, card_width, card_height)
            self.option_rects.append(rect)
            
            is_selected = (i == self.selected)
            value = self._get_setting_value(i)
            
            # Ayar tipine göre kind ve strip_color belirle
            if i == len(self.options) - 1:  # Geri
                strip_color = (255, 100, 120)
                kind = 'default'
                retro_style.draw_button(
                    self.screen,
                    rect,
                    '← ' + t('back'),
                    selected=is_selected,
                    strip_color=strip_color,
                )
                continue
            elif i in (2, 4, 5, 8):  # Toggle seçenekler (vsync, show_ghost, show_background, particle)
                kind = 'toggle'
                strip_color = (112, 160, 255)  # mavi
            elif i in (0, 1, 3, 6, 7):  # Selector seçenekler (window_mode, çözünürlük, fps limit, Şeffaflık)
                kind = 'selector'
                strip_color = (100, 220, 150)  # yeşil
            else:
                kind = 'default'
                strip_color = (100, 110, 130)
            
            # Değer rengini belirle - dil bağımsız kontrol
            on_values = (t('on'), t('fullscreen'))
            off_values = (t('off'), t('windowed'))
            if value in on_values:
                value_color = (100, 255, 100)
            elif value in off_values:
                value_color = (255, 100, 100)
            else:
                value_color = (100, 200, 255)
            
            retro_style.draw_setting_row(
                self.screen,
                rect,
                option,
                value,
                selected=is_selected,
                label_color=(255, 255, 255) if is_selected else (200, 200, 200),
                value_color=value_color,
                strip_color=strip_color,
                kind=kind,
            )


        if self._vsync_restart_prompt_active:
            self._draw_vsync_restart_prompt()

    def _draw_vsync_restart_prompt(self):
        width, height = self.screen.get_size()

        overlay = pygame.Surface((width, height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 150))
        self.screen.blit(overlay, (0, 0))

        panel_w = min(680, width - 120)
        panel_h = 220
        panel_rect = pygame.Rect((width - panel_w) // 2, (height - panel_h) // 2, panel_w, panel_h)
        retro_style.draw_panel(self.screen, panel_rect, title=t('vsync_changed'))

        msg_lines = [
            t('vsync_restart_msg1'),
            t('vsync_restart_msg2'),
            t('vsync_restart_msg3')
        ]
        font = retro_style.get_font(22, bold=False)
        y = panel_rect.y + 60
        for line in msg_lines:
            surf = font.render(line, True, (220, 230, 245))
            self.screen.blit(surf, surf.get_rect(center=(panel_rect.centerx, y)))
            y += 28

        btn_h = 56
        btn_gap = 18
        btn_w = (panel_w - 60 - btn_gap) // 2
        btn_y = panel_rect.bottom - btn_h - 24
        btn1 = pygame.Rect(panel_rect.x + 30, btn_y, btn_w, btn_h)
        btn2 = pygame.Rect(btn1.right + btn_gap, btn_y, btn_w, btn_h)
        self._vsync_prompt_buttons = [btn1, btn2]

        retro_style.draw_button(self.screen, btn1, t('restart_now'), selected=self._vsync_restart_choice == 0)
        retro_style.draw_button(self.screen, btn2, t('later'), selected=self._vsync_restart_choice == 1)
    
    def _get_setting_value(self, index):
        """Ayar değerini string olarak döndür"""
        if index == 0:  # Pencere Modu
            return t('fullscreen') if self.fullscreen else t('windowed')
        elif index == 1:  # Pencere Boyutu
            if self.fullscreen:
                return t('not_available_short')  # Tam ekranda geçersiz
            if self.resolution == 'auto':
                return t('automatic')
            return self.resolution
        elif index == 2:  # VSync
            return t('on') if self.vsync else t('off')
        elif index == 3:  # FPS Limiti
            try:
                limit = int(self.fps_limit)
            except Exception:
                limit = 0
            return 'MAX' if limit <= 0 else f'{limit}'
        elif index == 4:  # Gölge Göster
            return t('on') if self.show_ghost else t('off')
        elif index == 5:  # Arka Plan Göster
            return t('on') if self.background_enabled else t('off')
        elif index == 6:  # Arka Plan Şeffaflığı
            return f'{int(self.bg_transparency * 100)}%'
        elif index == 7:  # Menü Şeffaflığı
            return f'{int(self.menu_transparency * 100)}%'
        elif index == 8:  # Parçacık Efektleri
            return t('on') if self.particle_effects else t('off')
        elif index == 9:  # Geri
            return ''
        return ''

    def _max_scroll(self):
        """Listede kaydırılabilecek maksimum mesafe."""
        height = self.screen.get_height()
        visible = height - 280
        total = len(self.options) * 82
        return max(0, total - max(visible, 0))
