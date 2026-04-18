"""Grafik ayarları menüsü"""
import pygame
from constants import *
from retro_style import retro_style
from platform_utils import normalize_mouse_pos
from background_effects import get_shared_falling_blocks_layer
from localization import t
from ui_scaling import get_projected_effective_scale, scale_px


class GraphicsMenu:
    """Grafik ayarları ekranı"""

    _PARTICLE_EFFECT_LEVELS = ('off', 'low', 'medium', 'high')
    
    def __init__(self, screen, settings_manager):
        """Grafik menüsünü başlat"""
        self.screen = screen
        self.settings_manager = settings_manager
        self.font_hint = retro_style.get_font(self._s(20, minimum=12), bold=False)

        # Arka plan efektleri (ayarlar ekranı ile tutarlı düşen bloklar)
        self.background_fx = get_shared_falling_blocks_layer('default')
        
        # Options artık property ile dinamik olarak alınacak
        self._option_keys = [
            'vsync',
            'fps_limit',
            'show_ghost',
            'show_background',
            'bg_transparency',
            'effects_opacity',
            'menu_transparency',
            'particle_effects',
            'back'
        ]
        self.selected = 0
        self.option_rects = []
        
        # Mevcut ayarları yükle (varsayılanlar settings_manager ile aynı olmalı)
        self.vsync = settings_manager.get('vsync', True)
        self.fps_limit = settings_manager.get('fps_limit', 0)  # 0 = otomatik ekran yenileme hızı
        self.show_ghost = settings_manager.get('show_ghost', True)
        self.background_enabled = settings_manager.get('background_enabled', True)
        self.bg_transparency = settings_manager.get('bg_transparency', 0.3)
        self.effects_opacity = settings_manager.get('effects_opacity', 1.0)
        self.menu_transparency = settings_manager.get('menu_transparency', 1.0)
        self.particle_effects = self._normalize_particle_effects_value(
            settings_manager.get('particle_effects', 'medium')
        )

        # FPS limit seçenekleri (0 = otomatik ekran yenileme hızı)
        self.fps_limits = [0, 60, 90, 120, 144, 240]
        
        self.scroll_offset = 0
        # Scrollbar drag state
        self._sb_thumb_rect: 'pygame.Rect | None' = None
        self._sb_container_rect: 'pygame.Rect | None' = None
        self._sb_drag_active: bool = False
        self._sb_drag_offset_y: int = 0
        self._last_visible_height: int = 0

        # VSync changes require restart (SDL hint/env is read on init).
        self._vsync_restart_prompt_active = False
        self._vsync_restart_choice = 0  # 0: restart now, 1: later
        self._vsync_prompt_buttons: list[pygame.Rect] = []

    def _ui_scale(self, min_scale: float = 0.72, max_scale: float = 1.24) -> float:
        return get_projected_effective_scale(
            self.screen,
            min_scale=min_scale,
            max_scale=max_scale,
            reference_size=(1366.0, 768.0),
        )

    def _s(self, value: int | float, minimum: int = 1, *, scale: float | None = None) -> int:
        active_scale = self._ui_scale() if scale is None else float(scale)
        return scale_px(value, active_scale, minimum=minimum)

    def _layout_metrics(self) -> dict[str, int | float]:
        width, height = self.screen.get_size()
        scale = self._ui_scale()
        horizontal_margin = self._s(120, minimum=84, scale=scale)
        available_width = max(self._s(260, minimum=220, scale=scale), width - horizontal_margin)
        return {
            'scale': scale,
            'title_y': self._s(70, minimum=50, scale=scale),
            'card_width': min(self._s(620, minimum=420, scale=scale), available_width),
            'card_height': self._s(74, minimum=56, scale=scale),
            'spacing': self._s(82, minimum=62, scale=scale),
            'start_offset': self._s(40, minimum=28, scale=scale),
            'clip_top_gap': self._s(10, minimum=8, scale=scale),
            'clip_bottom_margin': self._s(80, minimum=60, scale=scale),
            'row_cutoff_margin': self._s(160, minimum=120, scale=scale),
            'scroll_step': self._s(30, minimum=18, scale=scale),
            'visible_height_offset': self._s(280, minimum=210, scale=scale),
            'scrollbar_gap': self._s(8, minimum=6, scale=scale),
            'scrollbar_width': self._s(20, minimum=16, scale=scale),
            'scrollbar_bar_width': self._s(10, minimum=8, scale=scale),
            'scrollbar_padding': self._s(2, minimum=2, scale=scale),
            'scrollbar_track_min': self._s(4, minimum=4, scale=scale),
            'scrollbar_thumb_fallback': self._s(30, minimum=20, scale=scale),
            'prompt_width': min(self._s(680, minimum=480, scale=scale), width - self._s(120, minimum=84, scale=scale)),
            'prompt_height': self._s(220, minimum=180, scale=scale),
            'prompt_font_size': self._s(22, minimum=15, scale=scale),
            'prompt_top_padding': self._s(60, minimum=40, scale=scale),
            'prompt_line_gap': self._s(28, minimum=20, scale=scale),
            'prompt_button_height': self._s(56, minimum=44, scale=scale),
            'prompt_button_gap': self._s(18, minimum=12, scale=scale),
            'prompt_side_padding': self._s(30, minimum=18, scale=scale),
            'prompt_bottom_padding': self._s(24, minimum=16, scale=scale),
        }

    def _scrollbar_track_metrics(self) -> tuple[int, int, int]:
        metrics = self._layout_metrics()
        bar_width = int(metrics['scrollbar_bar_width'])
        padding = int(metrics['scrollbar_padding'])
        arrow_zone = max(bar_width, bar_width + padding)
        track_padding = int(metrics['scrollbar_track_min'])
        return arrow_zone, padding, track_padding
    
    @property
    def options(self):
        """Dil değiştiğinde dinamik olarak çevirilmiş seçenekleri döndür"""
        return [t(key) for key in self._option_keys]

    def _ensure_visible(self) -> None:
        """Seçili öğeyi görünür scroll alanında tut."""
        metrics = self._layout_metrics()
        card_height = int(metrics['card_height'])
        spacing = int(metrics['spacing'])
        visible_height = self._last_visible_height or max(1, self.screen.get_height() - int(metrics['visible_height_offset']))

        item_y = self.selected * spacing
        if item_y < self.scroll_offset:
            self.scroll_offset = item_y
        elif item_y + card_height > self.scroll_offset + visible_height:
            self.scroll_offset = item_y + card_height - visible_height

        self.scroll_offset = max(0, min(self.scroll_offset, self._max_scroll(visible_height=visible_height)))
    
    def handle_input(self, event):
        """Grafik menüsü input işle"""
        if self._vsync_restart_prompt_active:
            return self._handle_vsync_prompt_input(event)

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_UP:
                self.selected = (self.selected - 1) % len(self.options)
                self._ensure_visible()
            elif event.key == pygame.K_DOWN:
                self.selected = (self.selected + 1) % len(self.options)
                self._ensure_visible()
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
        
        elif event.type == pygame.MOUSEWHEEL:
            self.scroll_offset -= event.y * int(self._layout_metrics()['scroll_step'])
            self.scroll_offset = max(0, min(self.scroll_offset, self._max_scroll()))
        
        elif event.type == pygame.MOUSEMOTION:
            mouse_pos = normalize_mouse_pos(getattr(event, 'pos', None)) or event.pos
            # Scrollbar drag
            if self._sb_drag_active and self._sb_container_rect:
                _az, _pad, _track_min = self._scrollbar_track_metrics()
                track_y = self._sb_container_rect.top + _az + _pad
                track_h = max(_track_min, self._sb_container_rect.height - _az * 2 - _track_min)
                thumb_h = self._sb_thumb_rect.height if self._sb_thumb_rect else int(self._layout_metrics()['scrollbar_thumb_fallback'])
                max_scroll = self._max_scroll()
                new_thumb_top = mouse_pos[1] - self._sb_drag_offset_y - track_y
                new_thumb_top = max(0, min(new_thumb_top, track_h - thumb_h))
                ratio = new_thumb_top / max(1, track_h - thumb_h)
                self.scroll_offset = int(ratio * max_scroll)
                return None
            for i, rect in enumerate(self.option_rects):
                if rect.collidepoint(mouse_pos):
                    self.selected = i
        
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                mouse_pos = normalize_mouse_pos(getattr(event, 'pos', None)) or event.pos
                # Scrollbar thumb drag başlat
                if self._sb_thumb_rect and self._sb_thumb_rect.collidepoint(mouse_pos):
                    self._sb_drag_active = True
                    self._sb_drag_offset_y = mouse_pos[1] - self._sb_thumb_rect.y
                    return None
                # Scrollbar track alanına tıklama → o pozisyona zıpla
                if self._sb_container_rect and self._sb_container_rect.collidepoint(mouse_pos):
                    _az, _pad, _track_min = self._scrollbar_track_metrics()
                    _ty = self._sb_container_rect.top + _az + _pad
                    _th = max(_track_min, self._sb_container_rect.height - _az * 2 - _track_min)
                    _tmh = self._sb_thumb_rect.height if self._sb_thumb_rect else int(self._layout_metrics()['scrollbar_thumb_fallback'])
                    _max = self._max_scroll()
                    _rel = mouse_pos[1] - _ty - _tmh // 2
                    self.scroll_offset = int(max(0.0, min(1.0, _rel / max(1, _th - _tmh))) * _max)
                    return None
                for i, rect in enumerate(self.option_rects):
                    if rect.collidepoint(mouse_pos):
                        self.selected = i
                        if i == len(self.options) - 1:
                            return 'back'
                        else:
                            action = self._toggle_setting()
                            if action:
                                return action

        elif event.type == pygame.MOUSEBUTTONUP:
            if event.button == 1:
                self._sb_drag_active = False
                self._sb_drag_offset_y = 0

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

    def _normalize_particle_effects_value(self, value):
        helper = getattr(self.settings_manager, 'normalize_particle_effects_value', None)
        if callable(helper):
            try:
                return str(helper(value))
            except Exception:
                pass
        if isinstance(value, bool):
            return 'medium' if value else 'off'
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            mapping = {0: 'off', 1: 'low', 2: 'medium', 3: 'high'}
            return mapping.get(max(0, min(3, int(round(value)))), 'medium')
        mapping = {
            'off': 'off',
            'kapali': 'off',
            'kapalı': 'off',
            'false': 'off',
            '0': 'off',
            'low': 'low',
            'az': 'low',
            '1': 'low',
            'medium': 'medium',
            'orta': 'medium',
            'true': 'medium',
            'on': 'medium',
            'acik': 'medium',
            'açık': 'medium',
            '2': 'medium',
            'high': 'high',
            'cok': 'high',
            'çok': 'high',
            '3': 'high',
        }
        return mapping.get(str(value or '').strip().lower(), 'medium')

    def _cycle_particle_effects(self, increase=True):
        current = self._normalize_particle_effects_value(self.particle_effects)
        levels = self._PARTICLE_EFFECT_LEVELS
        idx = levels.index(current) if current in levels else levels.index('medium')
        if increase:
            idx = min(len(levels) - 1, idx + 1)
        else:
            idx = max(0, idx - 1)
        self.particle_effects = levels[idx]
        self.settings_manager.set('particle_effects', self.particle_effects)

    def _particle_effects_label(self):
        labels = {
            'off': t('off'),
            'low': t('particle_effects_low'),
            'medium': t('particle_effects_medium'),
            'high': t('particle_effects_high'),
        }
        return labels.get(self._normalize_particle_effects_value(self.particle_effects), t('particle_effects_medium'))
    
    def _toggle_setting(self):
        """Seçili ayarı değiştir"""
        if self.selected == 0:  # VSync
            self.vsync = not self.vsync
            self.settings_manager.set('vsync', self.vsync)
            # Show restart-required prompt.
            self._vsync_restart_prompt_active = True
            self._vsync_restart_choice = 0
        elif self.selected == 2:  # Gölge Göster
            self.show_ghost = not self.show_ghost
            self.settings_manager.set('show_ghost', self.show_ghost)
        elif self.selected == 3:  # Arka Plan Göster
            self.background_enabled = not self.background_enabled
            self.settings_manager.set('background_enabled', self.background_enabled)
            return 'toggle_background_enabled'
        elif self.selected == 7:  # Parçacık Efektleri
            self._cycle_particle_effects(True)

        return None

    
    def _change_setting(self, increase=True):
        """Ayarı artır/azalt (ok tuşları ile)"""
        if self.selected == 1:  # FPS Limiti
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
        
        elif self.selected == 4:  # Arka Plan Şeffaflığı
            if increase:
                self.bg_transparency = min(1.0, float(self.bg_transparency) + 0.1)
            else:
                self.bg_transparency = max(0.0, float(self.bg_transparency) - 0.1)
            self.settings_manager.set('bg_transparency', round(self.bg_transparency, 1))
            return 'change_bg_transparency'

        elif self.selected == 5:  # Efekt Şeffaflığı
            if increase:
                self.effects_opacity = min(1.0, float(self.effects_opacity) + 0.1)
            else:
                self.effects_opacity = max(0.0, float(self.effects_opacity) - 0.1)
            self.settings_manager.set('effects_opacity', round(self.effects_opacity, 1))
            return 'change_effects_opacity'

        elif self.selected == 6:  # Menü Şeffaflığı
            if increase:
                self.menu_transparency = min(1.0, float(self.menu_transparency) + 0.1)
            else:
                self.menu_transparency = max(0.0, float(self.menu_transparency) - 0.1)
            self.settings_manager.set('menu_transparency', round(self.menu_transparency, 1))
            return 'change_menu_transparency'

        elif self.selected == 7:  # Parçacık Efektleri
            self._cycle_particle_effects(increase)

        return None
    
    def draw(self):
        """Grafik menüsünü çiz - Oynanış stili ile uyumlu"""
        width, height = self.screen.get_size()
        metrics = self._layout_metrics()
        retro_style.draw_background(self.screen)
        self.background_fx.update(self.screen)
        self.background_fx.draw(self.screen)

        title_rect = retro_style.draw_title(self.screen, t('graphics_settings'), (width // 2, int(metrics['title_y'])), emoji='⚙')

        self.option_rects = []
        card_width = int(metrics['card_width'])
        card_height = int(metrics['card_height'])
        spacing = int(metrics['spacing'])

        clip_top = title_rect.bottom + int(metrics['clip_top_gap'])
        clip_h = max(1, height - clip_top - int(metrics['clip_bottom_margin']))
        max_scroll = self._max_scroll(visible_height=clip_h)
        self.scroll_offset = max(0, min(self.scroll_offset, max_scroll))
        start_y = title_rect.bottom + int(metrics['start_offset']) - self.scroll_offset

        prev_clip = self.screen.get_clip()
        self.screen.set_clip(pygame.Rect(0, clip_top, width, clip_h))

        for i, option in enumerate(self.options):
            y_pos = start_y + i * spacing
            if y_pos < title_rect.bottom + int(metrics['clip_top_gap']) or y_pos > height - int(metrics['row_cutoff_margin']):
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
            elif i in (0, 2, 3):  # Toggle seçenekler
                kind = 'toggle'
                strip_color = (112, 160, 255)  # mavi
            elif i in (1, 4, 5, 6):  # Selector seçenekler (fps limit, şeffaflık, particle)
                kind = 'selector'
                strip_color = (100, 220, 150)  # yeşil
            else:
                kind = 'default'
                strip_color = (100, 110, 130)
            
            # Değer rengini belirle - dil bağımsız kontrol
            on_values = (t('on'),)
            off_values = (t('off'),)
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

        self.screen.set_clip(prev_clip)

        # Scrollbar (sürüklenebilir)
        total_h = len(self.options) * spacing
        visible_h = clip_h
        if total_h > visible_h:
            sb_rect = pygame.Rect(
                width // 2 + card_width // 2 + int(metrics['scrollbar_gap']),
                clip_top,
                int(metrics['scrollbar_width']),
                clip_h,
            )
            self._sb_container_rect = sb_rect
            self._sb_thumb_rect = retro_style.draw_scrollbar(
                self.screen,
                sb_rect,
                self.scroll_offset,
                total_h,
                visible_h,
                bar_width=int(metrics['scrollbar_bar_width']),
            )
        else:
            self._sb_thumb_rect = None
            self._sb_container_rect = None

        if self._vsync_restart_prompt_active:
            self._draw_vsync_restart_prompt()

    def _draw_vsync_restart_prompt(self):
        width, height = self.screen.get_size()
        metrics = self._layout_metrics()

        overlay = pygame.Surface((width, height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 150))
        self.screen.blit(overlay, (0, 0))

        panel_w = int(metrics['prompt_width'])
        panel_h = int(metrics['prompt_height'])
        panel_rect = pygame.Rect((width - panel_w) // 2, (height - panel_h) // 2, panel_w, panel_h)
        retro_style.draw_panel(self.screen, panel_rect, title=t('vsync_changed'))

        msg_lines = [
            t('vsync_restart_msg1'),
            t('vsync_restart_msg2'),
            t('vsync_restart_msg3')
        ]
        font = retro_style.get_font(int(metrics['prompt_font_size']), bold=False)
        y = panel_rect.y + int(metrics['prompt_top_padding'])
        for line in msg_lines:
            surf = font.render(line, True, (220, 230, 245))
            self.screen.blit(surf, surf.get_rect(center=(panel_rect.centerx, y)))
            y += int(metrics['prompt_line_gap'])

        btn_h = int(metrics['prompt_button_height'])
        btn_gap = int(metrics['prompt_button_gap'])
        side_padding = int(metrics['prompt_side_padding'])
        btn_w = (panel_w - side_padding * 2 - btn_gap) // 2
        btn_y = panel_rect.bottom - btn_h - int(metrics['prompt_bottom_padding'])
        btn1 = pygame.Rect(panel_rect.x + side_padding, btn_y, btn_w, btn_h)
        btn2 = pygame.Rect(btn1.right + btn_gap, btn_y, btn_w, btn_h)
        self._vsync_prompt_buttons = [btn1, btn2]

        retro_style.draw_button(self.screen, btn1, t('restart_now'), selected=self._vsync_restart_choice == 0)
        retro_style.draw_button(self.screen, btn2, t('later'), selected=self._vsync_restart_choice == 1)
    
    def _get_setting_value(self, index):
        """Ayar değerini string olarak döndür"""
        if index == 0:  # VSync
            return t('on') if self.vsync else t('off')
        elif index == 1:  # FPS Limiti
            try:
                limit = int(self.fps_limit)
            except Exception:
                limit = 0
            return t('automatic') if limit <= 0 else f'{limit}'
        elif index == 2:  # Gölge Göster
            return t('on') if self.show_ghost else t('off')
        elif index == 3:  # Arka Plan Göster
            return t('on') if self.background_enabled else t('off')
        elif index == 4:  # Arka Plan Şeffaflığı
            return f'{int(self.bg_transparency * 100)}%'
        elif index == 5:  # Efekt Şeffaflığı
            return f'{int(self.effects_opacity * 100)}%'
        elif index == 6:  # Menü Şeffaflığı
            return f'{int(self.menu_transparency * 100)}%'
        elif index == 7:  # Parçacık Efektleri
            return self._particle_effects_label()
        elif index == 8:  # Geri
            return ''
        return ''

    def _max_scroll(self, visible_height: int | None = None):
        """Listede kaydırılabilecek maksimum mesafe."""
        metrics = self._layout_metrics()
        if visible_height is not None:
            visible = max(1, int(visible_height))
            self._last_visible_height = visible
        elif self._last_visible_height > 0:
            visible = self._last_visible_height
        else:
            height = self.screen.get_height()
            visible = max(1, height - int(metrics['visible_height_offset']))
        total = len(self.options) * int(metrics['spacing'])
        return max(0, total - max(visible, 0))
