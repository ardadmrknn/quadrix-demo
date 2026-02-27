"""Campaign Level Seçim Ekranı

Premium World Map tarzı level seçim arayüzü.
5 Dünya, her dünyada 20 level gösterir.
Oyunun neon/glassmorphism UI stiline tam uyumlu.
"""
from __future__ import annotations

import pygame
import math
from typing import Dict, Any, List, Optional, Tuple, TYPE_CHECKING

from .level_data import get_level, get_levels, get_total_levels, get_world_info, LevelConfig
from background_effects import get_shared_falling_blocks_layer
from ui_theme import UIColors, UIFonts, UIStyle
from retro_style import retro_style as _retro_style
from localization import t, get_language

# Neon renk paleti (merkezi tema)
NEON_CYAN = UIColors.NEON_CYAN
NEON_MAGENTA = UIColors.NEON_MAGENTA
NEON_ORANGE = UIColors.NEON_ORANGE
NEON_LIME = UIColors.NEON_GREEN
NEON_BLUE = UIColors.NEON_CYAN
GOLD = UIColors.NEON_GOLD


class CampaignLevelSelect:
    """Premium Level Seçim Ekranı"""
    
    def __init__(
        self,
        screen: pygame.Surface,
        settings_manager = None,
        user_manager = None,
    ):
        self.screen = screen
        self.settings_manager = settings_manager
        self.user_manager = user_manager
        
        # Ekran boyutları
        self.window_width = screen.get_width()
        self.window_height = screen.get_height()
        
        # Seçim durumu
        self.current_world = 1
        self.selected_level = 1
        self.hovered_level: Optional[int] = None
        self.debug_unlock_all = False
        
        # Scroll
        self.scroll_offset = 0
        self.max_scroll = 0
        
        # Animasyon
        self.animation_time = 0.0
        
        # Dünya geçiş animasyonu
        self.world_transition_active = False
        self.world_transition_progress = 0.0
        self.world_transition_duration = 0.4  # saniye
        self.previous_world = 1
        self.target_world = 1
        
        # İlerleme bilgisi
        self.progress = self._load_progress()
        
        # Renkler - merkezi tema palette
        self.COLORS = {
            'bg': UIColors.BG_DARK,
            'panel': UIColors.BG_MEDIUM,
            'panel_dark': UIColors.BG_LIGHT,
            'gold': GOLD,
            'green': UIColors.NEON_GREEN,
            'cyan': UIColors.NEON_CYAN,
            'purple': UIColors.NEON_MAGENTA,
            'orange': UIColors.NEON_ORANGE,
            'red': UIColors.NEON_RED,
            'gray': UIColors.TEXT_MUTED,
            'dark_gray': UIColors.BUTTON_BG,
            'white': UIColors.TEXT_PRIMARY,
            'text': UIColors.TEXT_SECONDARY,
            'text_dim': UIColors.TEXT_MUTED,
        }
        
        # Dünya renkleri - neon versiyonları
        self.WORLD_COLORS = {
            1: NEON_LIME,         # Başlangıç Vadisi
            2: NEON_CYAN,         # Buz Diyarı
            3: NEON_ORANGE,       # Lav Mağarası
            4: NEON_MAGENTA,      # Fırtına Kalesi
            5: GOLD,              # Yıldız Kulesi
        }
        
        # retro_style import (varsa)
        self._init_style()
        
        # Fontlar
        self._init_fonts()

        # Dil değişimi takibi (hızlı yenileme için)
        self._lang_cache = get_language()
        
        # Arka plan görselini yükle
        self._load_background()

        # Arka plan efekti (akan tetromino blokları)
        self.background_fx = get_shared_falling_blocks_layer('default')
        self.effects_enabled = True
        self.background_enabled = True
        if self.settings_manager:
            self.effects_enabled = self.settings_manager.get('effects_enabled', True)
            self.background_enabled = self.settings_manager.get('background_enabled', True)
        
        # UI Elemanları
        self.level_buttons: List[Tuple[pygame.Rect, int]] = []
        self.world_tabs: List[Tuple[pygame.Rect, int]] = []
        self.back_button: Optional[pygame.Rect] = None
        self.play_button: Optional[pygame.Rect] = None
        self.header_bottom = 0
        self.tabs_bottom = 0
        
        # Performance: overlay cache
        self._overlay_cache: Optional[pygame.Surface] = None
        
        # Kilit ikonu yükle
        self._load_lock_icon()
        
        # Yıldız ikonu yükle
        self._load_star_icon()
        
        # Level buton çerçevelerini yükle
        self._load_level_frames()

        # Legacy stil: varsayılan olarak PNG çerçeveleri AÇIK (yeni görünüm)
        try:
            self.use_legacy_level_frames = bool(
                self.settings_manager.get('campaign_legacy_style', False)
            ) if self.settings_manager else False
        except Exception:
            self.use_legacy_level_frames = False
    
    def _load_background(self) -> None:
        """Uzay arka planını yükle"""
        import os
        
        self.background_image = None
        self.background_scaled = None
        
        # Olası arka plan yolları
        possible_paths = [
            os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'backgrounds', 'outer_background.jpg'),
            os.path.join(os.path.dirname(os.path.dirname(__file__)), 'backgrounds', 'outer_background.jpg'),
            'backgrounds/outer_background.jpg',
            '../backgrounds/outer_background.jpg',
        ]
        
        for path in possible_paths:
            try:
                if os.path.exists(path):
                    self.background_image = pygame.image.load(path).convert()
                    break
            except Exception:
                continue
        
        if self.background_image:
            # Ekran boyutuna ölçekle
            self.background_scaled = pygame.transform.scale(
                self.background_image, 
                (self.window_width, self.window_height)
            )
    
    def _init_style(self) -> None:
        """retro_style'ı yükle (varsa)"""
        try:
            from retro_style import retro_style
            self.retro_style = retro_style
        except (ImportError, AttributeError):
            self.retro_style = None
    
    def _init_fonts(self) -> None:
        """Fontları başlat"""
        # max_scale=1.0 ile cap'lendi; 1080p ve üstünde puntoların gereğinden büyümesi önlenir
        scale = max(0.72, min(1.0, self.window_width / 1400, self.window_height / 900))
        self.font_title = _retro_style.get_font(int(48 * scale), bold=True)
        self.font_large = _retro_style.get_font(int(36 * scale), bold=True)
        self.font_medium = _retro_style.get_font(int(28 * scale), bold=False)
        self.font_small = _retro_style.get_font(int(22 * scale), bold=False)
        self.font_tiny = _retro_style.get_font(int(18 * scale), bold=False)

    def _get_ui_scale(self, min_scale: float = 0.72, max_scale: float = 1.26) -> float:
        """Pencere boyutuna göre ortak UI ölçek katsayısı"""
        width = self.screen.get_width()
        height = self.screen.get_height()
        return max(min_scale, min(max_scale, min(width / 1366.0, height / 768.0)))
    
    def _load_progress(self) -> Dict[str, Any]:
        """Campaign ilerlemesini yükle"""
        if not self.settings_manager:
            return {'completed_levels': {}, 'highest_level': 0, 'total_stars': 0}
        
        progress = self.settings_manager.get('campaign_progress', {})
        if not isinstance(progress, dict):
            progress = {}
        
        return {
            'completed_levels': progress.get('completed_levels', {}),
            'highest_level': progress.get('highest_level', 0),
            'total_stars': progress.get('total_stars', 0),
            'current_world': progress.get('current_world', 1),
        }
    
    def _is_level_unlocked(self, level_num: int) -> bool:
        """Level açık mı kontrol et"""
        if getattr(self, 'debug_unlock_all', False):
            return True
        if level_num == 1:
            return True
        prev_level = str(level_num - 1)
        completed = self.progress.get('completed_levels', {})
        return prev_level in completed and completed[prev_level].get('completed', False)
    
    def _get_level_stars(self, level_num: int) -> int:
        """Level için kazanılan yıldız sayısı"""
        completed = self.progress.get('completed_levels', {})
        level_data = completed.get(str(level_num), {})
        return level_data.get('stars', 0)
    
    def update(self, dt: float = 0.016) -> None:
        """Animasyonları güncelle"""
        self.animation_time += dt
        
        # Dünya geçiş animasyonu
        if self.world_transition_active:
            self.world_transition_progress += dt / self.world_transition_duration
            if self.world_transition_progress >= 1.0:
                self.world_transition_progress = 1.0
                self.world_transition_active = False
                self.previous_world = self.target_world
    
    def handle_input(self, event: pygame.event) -> Optional[str]:
        """Kullanıcı girdilerini işle"""
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                return 'back'
            
            # Ok tuşları ile navigasyon
            if event.key == pygame.K_LEFT:
                self._move_selection(-1)
            elif event.key == pygame.K_RIGHT:
                self._move_selection(1)
            elif event.key == pygame.K_UP:
                self._move_selection(-5)  # Üst satır
            elif event.key == pygame.K_DOWN:
                self._move_selection(5)   # Alt satır
            
            # Dünya değiştirme (animasyon sırasında engelle)
            elif event.key == pygame.K_1 and not self.world_transition_active:
                if self.current_world != 1:
                    self._start_world_transition(1)
            elif event.key == pygame.K_2 and not self.world_transition_active:
                if self.current_world != 2:
                    self._start_world_transition(2)
            elif event.key == pygame.K_3 and not self.world_transition_active:
                if self.current_world != 3:
                    self._start_world_transition(3)
            elif event.key == pygame.K_4 and not self.world_transition_active:
                if self.current_world != 4:
                    self._start_world_transition(4)
            elif event.key == pygame.K_5 and not self.world_transition_active:
                if self.current_world != 5:
                    self._start_world_transition(5)
            
            # Enter ile level başlat
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                if self._is_level_unlocked(self.selected_level):
                    return f'play_{self.selected_level}'
        
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = event.pos
            
            # Oyna butonu
            if self.play_button and self.play_button.collidepoint(pos):
                if self._is_level_unlocked(self.selected_level):
                    return f'play_{self.selected_level}'
            
            # Dünya tabları (animasyon sırasında değişiklik yapma)
            if not self.world_transition_active:
                for rect, world_num in self.world_tabs:
                    if rect.collidepoint(pos):
                        if world_num != self.current_world:
                            self._start_world_transition(world_num)
                        return None
            
            # Level butonları
            for rect, level_num in self.level_buttons:
                if rect.collidepoint(pos):
                    if self._is_level_unlocked(level_num):
                        if self.selected_level == level_num:
                            return f'play_{level_num}'
                        self.selected_level = level_num
                    else:
                        # Kilitli level - sadece seç
                        self.selected_level = level_num
        
        elif event.type == pygame.MOUSEMOTION:
            pos = event.pos
            self.hovered_level = None
            for rect, level_num in self.level_buttons:
                if rect.collidepoint(pos):
                    self.hovered_level = level_num
                    break
        
        elif event.type == pygame.MOUSEWHEEL:
            self.scroll_offset -= event.y * 30
            self.scroll_offset = max(0, min(self.scroll_offset, self.max_scroll))
        
        return None
    
    def _move_selection(self, delta: int) -> None:
        """Seçimi hareket ettir"""
        world_start = (self.current_world - 1) * 20 + 1
        world_end = self.current_world * 20
        
        new_level = self.selected_level + delta
        
        # Dünya sınırları içinde kal
        if new_level < world_start:
            new_level = world_start
        elif new_level > world_end:
            new_level = world_end
        
        self.selected_level = new_level
        # Klavye navigasyonunda hover state'i temizle; panel hemen seçili level'ı göstersin
        self.hovered_level = None
    
    def _update_selection_for_world(self) -> None:
        """Dünya değiştiğinde seçimi güncelle"""
        world_start = (self.current_world - 1) * 20 + 1
        
        # Bu dünyanın en yüksek açık level'ını bul
        highest = self.progress.get('highest_level', 0)
        
        if highest >= world_start:
            self.selected_level = min(highest + 1, self.current_world * 20)
        else:
            self.selected_level = world_start
        
        # Açık değilse ilk level'ı seç
        if not self._is_level_unlocked(self.selected_level):
            self.selected_level = world_start
    
    def _start_world_transition(self, target_world: int) -> None:
        """Dünya geçiş animasyonunu başlat"""
        if target_world == self.current_world:
            return
        
        self.previous_world = self.current_world
        self.target_world = target_world
        self.current_world = target_world  # Hemen değiştir (animasyon görsel)
        self.world_transition_active = True
        self.world_transition_progress = 0.0
        self._update_selection_for_world()
        # Dünya geçişinde hover state'i temizle
        self.hovered_level = None
    
    def draw(self) -> None:
        """Ekranı çiz"""
        width = self.screen.get_width()
        height = self.screen.get_height()

        if width != self.window_width or height != self.window_height:
            self.window_width = width
            self.window_height = height
            self._init_fonts()
            self._overlay_cache = None

        if self._lang_cache != get_language():
            self._lang_cache = get_language()
            self._init_fonts()
            self._overlay_cache = None
        
        # Premium arka plan
        self._draw_background()
        
        # Header
        self._draw_header()
        
        # Dünya tabları
        self._draw_world_tabs()
        
        # Level grid
        self._draw_level_grid()
        
        # Seçili level bilgisi
        self._draw_level_info()
        
        # Alt butonlar
        self._draw_bottom_buttons()
        
        # Dünya geçiş animasyonu overlay (fade efekti)
        if self.world_transition_active:
            self._draw_world_transition_overlay()
    
    def _draw_background(self) -> None:
        """Ana menü ile uyumlu arka plan"""
        width, height = self.screen.get_size()
        if self.retro_style:
            self.retro_style.draw_background(self.screen)
        else:
            # Arka plan görselini çiz
            if self.background_scaled:
                # Ekran boyutu değiştiyse yeniden ölçekle
                if self.background_scaled.get_size() != (width, height):
                    self.background_scaled = pygame.transform.scale(
                        self.background_image, (width, height)
                    )
                self.screen.blit(self.background_scaled, (0, 0))
            else:
                # Fallback: gradient arka plan
                for y in range(height):
                    progress = y / height
                    r = int(10 + 8 * progress)
                    g = int(14 + 10 * progress)
                    b = int(24 + 18 * progress)
                    pygame.draw.line(self.screen, (r, g, b), (0, y), (width, y))

        # Akan tetromino arka plan efekti (menü ile aynı)
        if self.background_fx and self.effects_enabled and self.background_enabled:
            self.background_fx.update(self.screen)
            self.background_fx.draw(self.screen)
    
    def _draw_header(self) -> None:
        """Premium başlık"""
        width = self.screen.get_width()
        ui_scale = self._get_ui_scale()
        s = lambda v, minimum=1: max(minimum, int(round(v * ui_scale)))
        world_color = self.WORLD_COLORS[self.current_world]

        # Başlık - ana UI teması (retro_style)
        title_text = t('campaign_title')
        title_rect = None
        title_center_y = s(56)
        if self.retro_style:
            max_width = max(0, width - s(120))
            font = self.retro_style.get_fitting_font(title_text, s(56), max_width, bold=True)
            shadow = font.render(title_text, True, (0, 0, 0))
            shadow.set_alpha(160)
            shadow_rect = shadow.get_rect(center=(width // 2 + s(2), title_center_y + s(2)))
            self.screen.blit(shadow, shadow_rect)
            title_surface = font.render(title_text, True, UIColors.TEXT_PRIMARY)
            title_rect = title_surface.get_rect(center=(width // 2, title_center_y))
            self.screen.blit(title_surface, title_rect)
        else:
            title = self.font_title.render(title_text, True, world_color)
            title_rect = title.get_rect(centerx=width // 2, y=s(18))
            glow = self.font_title.render(title_text, True, world_color)
            for dx, dy, a in [(-s(2), 0, 25), (s(2), 0, 25), (0, -s(2), 20), (0, s(2), 20)]:
                glow.set_alpha(a)
                self.screen.blit(glow, (title_rect.x + dx, title_rect.y + dy))
            self.screen.blit(title, title_rect)

        # İlerleme bilgisi - ana UI temasına uygun panel
        total_stars = self.progress.get('total_stars', 0)
        highest = self.progress.get('highest_level', 0)

        bar_width = min(s(560), width - s(120))
        bar_height = s(56)
        bar_x = (width - bar_width) // 2
        base_y = title_rect.bottom + s(14) if title_rect else s(72)
        bar_y = base_y
        bar_rect = pygame.Rect(bar_x, bar_y, bar_width, bar_height)

        if self.retro_style:
            self.retro_style.draw_glass_panel(
                self.screen,
                bar_rect,
                alpha=165,
                border_color=UIColors.NEON_CYAN,
                glow=False,
            )
        else:
            bar_surf = pygame.Surface((bar_width, bar_height), pygame.SRCALPHA)
            bar_surf.fill(UIColors.GLASS_BG)
            for i in range(8):
                alpha = int(30 * (1 - i / 8))
                pygame.draw.line(bar_surf, UIColors.GLASS_HIGHLIGHT[:3] + (alpha,), (0, i), (bar_width, i))
            self.screen.blit(bar_surf, bar_rect.topleft)
            pygame.draw.rect(self.screen, UIColors.BUTTON_BORDER, bar_rect, 2, border_radius=UIStyle.BORDER_RADIUS_SMALL)

        # İlerleme text (üstte, bar ile çakışmasın)
        progress_text = t(
            'campaign_progress',
            current=highest,
            total=100,
            stars=total_stars,
            level_label=t('level'),
            stars_label=t('stars')
        )
        progress_surf = self.font_small.render(progress_text, True, UIColors.TEXT_PRIMARY)
        progress_rect = progress_surf.get_rect(centerx=bar_rect.centerx, y=bar_rect.y + s(10))
        self.screen.blit(progress_surf, progress_rect)

        # Progress bar içi (modern)
        progress_ratio = max(0.0, min(1.0, highest / 100))
        track_rect = pygame.Rect(bar_x + s(12), bar_y + bar_height - s(18), bar_width - s(24), s(10))
        track_surf = pygame.Surface(track_rect.size, pygame.SRCALPHA)
        pygame.draw.rect(track_surf, (*UIColors.SLIDER_BG, 200), track_surf.get_rect(), border_radius=6)
        pygame.draw.rect(track_surf, (255, 255, 255, 28), track_surf.get_rect(), 1, border_radius=6)
        for i in range(4):
            alpha = int(24 * (1 - i / 4))
            pygame.draw.line(track_surf, (255, 255, 255, alpha), (0, i), (track_rect.width, i))
        self.screen.blit(track_surf, track_rect.topleft)

        fill_width = int(track_rect.width * progress_ratio)
        if fill_width > 0:
            fill_rect = pygame.Rect(track_rect.x, track_rect.y, fill_width, track_rect.height)
            start_c = UIColors.NEON_CYAN
            end_c = UIColors.NEON_GOLD
            for i in range(fill_width):
                grad_t = i / max(1, fill_width - 1)
                r = int(start_c[0] + (end_c[0] - start_c[0]) * grad_t)
                g = int(start_c[1] + (end_c[1] - start_c[1]) * grad_t)
                b = int(start_c[2] + (end_c[2] - start_c[2]) * grad_t)
                pygame.draw.line(self.screen, (r, g, b),
                                 (fill_rect.x + i, fill_rect.y),
                                 (fill_rect.x + i, fill_rect.y + fill_rect.height))
            # Glow
            pygame.draw.rect(self.screen, (*UIColors.NEON_CYAN, 60), fill_rect.inflate(6, 4), border_radius=7)

        self.header_bottom = bar_rect.bottom
    
    def _draw_world_tabs(self) -> None:
        """Premium dünya sekmeleri"""
        width = self.screen.get_width()
        ui_scale = self._get_ui_scale()
        s = lambda v, minimum=1: max(minimum, int(round(v * ui_scale)))
        self.world_tabs = []

        tab_y = max(self.header_bottom + s(14), s(115))
        tab_width = min(s(132), (width - s(120)) // 5)
        tab_height = s(46)
        gap = s(10)
        total_width = tab_width * 5 + gap * 4
        start_x = (width - total_width) // 2

        for i in range(1, 6):
            x = start_x + (i - 1) * (tab_width + gap)
            rect = pygame.Rect(x, tab_y, tab_width, tab_height)
            self.world_tabs.append((rect, i))

            is_selected = (i == self.current_world)
            world_color = self.WORLD_COLORS[i]
            world_name = t(f'campaign_world_short_{i}')

            # Arka plan (modern glass) - tam dolgu
            fill_color = world_color if is_selected else UIColors.TAB_INACTIVE
            fill_alpha = 255 if is_selected else 220
            pygame.draw.rect(
                self.screen,
                (*fill_color, fill_alpha),
                rect,
                border_radius=UIStyle.BORDER_RADIUS_MEDIUM,
            )
            base_surf = pygame.Surface(rect.size, pygame.SRCALPHA)
            pygame.draw.rect(base_surf, (255, 255, 255, 28), base_surf.get_rect(), 1, border_radius=UIStyle.BORDER_RADIUS_MEDIUM)
            for j in range(6):
                alpha = int(22 * (1 - j / 6))
                pygame.draw.line(base_surf, (255, 255, 255, alpha), (0, j), (rect.width, j))
            self.screen.blit(base_surf, rect.topleft)

            # Kenar
            border_color = world_color if is_selected else UIColors.BUTTON_BORDER
            pygame.draw.rect(self.screen, border_color, rect, 2, border_radius=UIStyle.BORDER_RADIUS_MEDIUM)

            # Alt şerit (dünya rengi)
            strip_rect = pygame.Rect(rect.x + 10, rect.bottom - 6, rect.width - 20, 3)
            strip_rect = pygame.Rect(rect.x + s(10), rect.bottom - s(6), rect.width - s(20), s(3))
            pygame.draw.rect(self.screen, world_color, strip_rect, border_radius=2)

            # Dünya numarası ve ismi
            text_color = UIColors.BG_DARK if is_selected else UIColors.TEXT_SECONDARY
            tab_text = t('campaign_world_tab_format', index=i, name=world_name)
            text = self.font_small.render(tab_text, True, text_color)
            text_rect = text.get_rect(center=rect.center)
            self.screen.blit(text, text_rect)

        self.tabs_bottom = tab_y + tab_height
    
    def _draw_level_grid(self) -> None:
        """Premium level butonları grid"""
        width = self.screen.get_width()
        height = self.screen.get_height()
        ui_scale = self._get_ui_scale()
        s = lambda v, minimum=1: max(minimum, int(round(v * ui_scale)))
        
        self.level_buttons = []
        
        # Grid ayarları
        cols = 5
        rows = 4
        gap = s(20)
        button_size_by_width = min(s(104), (width - s(160)) // cols)

        # Alt bilgi panelinin üst kenarıyla güvenli boşluk kuralı
        # (_draw_level_info ile aynı panel geometrisi kullanılıyor)
        info_scale = self._get_ui_scale(min_scale=0.68, max_scale=1.18)
        info_panel_height = min(int(round(250 * info_scale)), height - s(70))
        info_panel_height = max(s(155), info_panel_height)
        info_panel_top = height - info_panel_height - s(10)
        frame_bottom_overflow = max(8, s(10))  # frame_rect inflate(20) nedeniyle görsel taşma
        desired_gap_to_info = max(6, s(8))
        max_grid_bottom = info_panel_top - desired_gap_to_info - frame_bottom_overflow

        top_anchor = max(self.tabs_bottom + s(14), s(175))
        available_grid_height = max(0, max_grid_bottom - top_anchor)
        button_size_by_height = max(s(52), (available_grid_height - (rows - 1) * gap) // rows)

        button_size = min(button_size_by_width, button_size_by_height)
        
        grid_width = cols * button_size + (cols - 1) * gap
        grid_height = rows * button_size + (rows - 1) * gap
        
        start_x = (width - grid_width) // 2
        # 4. satır tabanını alt panel üst kenarına 1-2px boşlukla hizala
        start_y = max(top_anchor, max_grid_bottom - grid_height)
        
        # Bu dünyanın level'ları
        world_start = (self.current_world - 1) * 20 + 1
        world_color = self.WORLD_COLORS[self.current_world]
        
        for row in range(rows):
            for col in range(cols):
                level_num = world_start + row * cols + col
                
                if level_num > self.current_world * 20:
                    continue
                
                x = start_x + col * (button_size + gap)
                y = start_y + row * (button_size + gap)
                rect = pygame.Rect(x, y, button_size, button_size)
                self.level_buttons.append((rect, level_num))
                
                # Level durumu
                is_unlocked = self._is_level_unlocked(level_num)
                is_selected = (level_num == self.selected_level)
                is_hovered = (level_num == self.hovered_level)
                stars = self._get_level_stars(level_num)
                level_config = get_level(level_num)
                is_boss = level_config.is_boss if level_config else False
                
                # Premium buton çizimi
                self._draw_level_button(
                    rect, level_num, is_unlocked, is_selected, is_hovered, 
                    stars, is_boss, world_color
                )
    
    def _get_scaled_frame(self, frame_type: str, size: Tuple[int, int], world: Optional[int] = None) -> Optional[pygame.Surface]:
        """Çerçeveyi boyutuna göre ölçekle (cache kullanarak)"""
        if getattr(self, "use_legacy_level_frames", False):
            return None
        frame_surface = None
        if world and getattr(self, "level_frames_by_world", None):
            frame_surface = self.level_frames_by_world.get(world, {}).get(frame_type)
        if frame_surface is None:
            frame_surface = self.level_frames.get(frame_type)
        if frame_surface is None:
            return None

        cache_key = (world, frame_type, size)
        if cache_key not in self.level_frames_scaled:
            self.level_frames_scaled[cache_key] = pygame.transform.smoothscale(
                frame_surface, size
            )
        return self.level_frames_scaled[cache_key]
    
    def _draw_level_button(
        self, 
        rect: pygame.Rect, 
        level_num: int,
        is_unlocked: bool, 
        is_selected: bool, 
        is_hovered: bool, 
        stars: int, 
        is_boss: bool,
        world_color: Tuple[int, int, int]
    ) -> None:
        """Premium level butonu çiz - PNG çerçeve kullanarak"""

        base_rect = rect
        # Hangi çerçeveyi kullanacağız?
        if is_selected:
            frame_type = 'selected'
            text_color = (0, 0, 0)
        elif is_hovered and is_unlocked:
            frame_type = 'hover'
            text_color = self.COLORS['white']
        elif is_unlocked:
            frame_type = 'normal'
            text_color = self.COLORS['white']
        else:
            frame_type = 'locked'
            text_color = self.COLORS['dark_gray']

        # PNG çerçeveyi çiz - biraz şişir ki tam kaplasın
        inflate_amount = 20  # Her yönde 20 piksel şişir
        frame_rect = rect.inflate(inflate_amount, inflate_amount)
        frame_size = (frame_rect.width, frame_rect.height)
        scaled_frame = self._get_scaled_frame(frame_type, frame_size, self.current_world)

        if scaled_frame:
            self.screen.blit(scaled_frame, frame_rect.topleft)
            base_rect = frame_rect
        elif self.retro_style:
            alpha = 200 if is_selected else (175 if is_unlocked else 140)
            border_color = world_color if is_selected else UIColors.BUTTON_BORDER
            if is_hovered and is_unlocked and not is_selected:
                border_color = UIColors.NEON_CYAN

            self.retro_style.draw_glass_panel(
                self.screen,
                rect,
                alpha=alpha,
                border_color=border_color,
                glow=is_selected,
            )

            if not is_unlocked:
                lock_overlay = pygame.Surface(rect.size, pygame.SRCALPHA)
                lock_overlay.fill((*UIColors.BUTTON_DISABLED, 140))
                self.screen.blit(lock_overlay, rect.topleft)

            text_color = UIColors.TEXT_PRIMARY if is_unlocked else UIColors.TEXT_MUTED
        else:
            # Fallback: eski yöntem
            if is_selected:
                glow_rect = rect.inflate(10, 10)
                glow_surf = pygame.Surface(glow_rect.size, pygame.SRCALPHA)
                pygame.draw.rect(glow_surf, (*world_color, 60), glow_surf.get_rect(), border_radius=UIStyle.BORDER_RADIUS_LARGE)
                self.screen.blit(glow_surf, glow_rect.topleft)

                btn_surf = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
                for row in range(rect.height):
                    alpha = int(200 - 40 * (row / rect.height))
                    pygame.draw.line(btn_surf, (*world_color, alpha), (0, row), (rect.width, row))
                self.screen.blit(btn_surf, rect.topleft)
                pygame.draw.rect(self.screen, self.COLORS['gold'], rect, 3, border_radius=UIStyle.BORDER_RADIUS_MEDIUM)

            elif is_hovered and is_unlocked:
                btn_surf = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
                btn_surf.fill((*UIColors.BUTTON_HOVER, 220))
                self.screen.blit(btn_surf, rect.topleft)

            elif is_unlocked:
                btn_surf = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
                btn_surf.fill((*UIColors.BUTTON_BG, 220))
                self.screen.blit(btn_surf, rect.topleft)
                pygame.draw.rect(self.screen, (*world_color, 120), rect, 1, border_radius=UIStyle.BORDER_RADIUS_MEDIUM)

            else:
                btn_surf = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
                btn_surf.fill((*UIColors.BUTTON_DISABLED, 200))
                self.screen.blit(btn_surf, rect.topleft)
                pygame.draw.rect(self.screen, UIColors.BUTTON_BORDER, rect, 1, border_radius=UIStyle.BORDER_RADIUS_MEDIUM)
        
        # Boss level özel glow KALDIRILDI - artık normal level gibi görünecek
        # if is_boss and is_unlocked:
        #     pulse = 0.6 + 0.4 * math.sin(self.animation_time * 4)
        #     glow_alpha = int(50 * pulse)
        #     glow_rect = frame_rect.inflate(6, 6)
        #     pygame.draw.rect(self.screen, (*NEON_MAGENTA, glow_alpha), glow_rect, 2, border_radius=12)
        
        # Level numarası - frame_rect merkezine göre
        # Artık boss leveller de normal numara gösteriyor (B harfi yerine 10, 20, 30 vb.)
        level_text = str((level_num - 1) % 20 + 1)  # Dünya içi numara (1-20)

        num_font_size = max(16, int(base_rect.height * 0.42))
        level_font = UIFonts.get(num_font_size, bold=True)
        text = level_font.render(level_text, True, text_color)
        text_offset_y = max(0, int(base_rect.height * 0.10)) if (is_unlocked or stars > 0) else 0
        text_rect = text.get_rect(center=(base_rect.centerx, base_rect.centery - text_offset_y))
        self.screen.blit(text, text_rect)
        
        # Yıldızlar (açık level için) - base_rect kullan
        if is_unlocked or stars > 0:
            self._draw_mini_stars(base_rect, stars, world_color)
        
        # Kilit ikonu (kilitli ise) - base_rect kullan
        if not is_unlocked and stars == 0:
            self._draw_lock_icon(base_rect)
    
    def _draw_mini_stars(self, rect: pygame.Rect, stars: int, world_color: Tuple) -> None:
        """Küçük yıldız gösterimi"""
        star_size = max(8, int(rect.width * 0.14))
        star_gap = max(3, int(star_size * 0.4))
        star_y = rect.bottom - max(8, int(rect.height * 0.16))
        total_width = 3 * star_size + 2 * star_gap
        start_x = rect.centerx - total_width // 2
        
        for i in range(3):
            star_x = start_x + i * (star_size + star_gap)
            
            if i < stars:
                # Dolu yıldız
                color = self.COLORS['gold']
                self._draw_star(star_x + star_size // 2, star_y + star_size // 2, star_size, color)
            else:
                # Boş yıldız
                color = self.COLORS['dark_gray']
                self._draw_star(star_x + star_size // 2, star_y + star_size // 2, star_size, color, filled=False)
    
    def _draw_star(self, cx: int, cy: int, size: int, color: Tuple, filled: bool = True) -> None:
        """Küçük yıldız çiz"""
        points = []
        for i in range(10):
            angle = i * math.pi / 5 - math.pi / 2
            r = size * 0.5 if i % 2 == 0 else size * 0.25
            px = cx + r * math.cos(angle)
            py = cy + r * math.sin(angle)
            points.append((int(px), int(py)))
        
        if filled:
            pygame.draw.polygon(self.screen, color, points)
        else:
            pygame.draw.polygon(self.screen, color, points, 1)
    
    def _load_level_frames(self) -> None:
        """Level buton çerçevelerini yükle"""
        import os
        
        self.level_frames = {
            'normal': None,
            'selected': None,
            'locked': None,
            'hover': None,
            'info_panel': None,
        }
        self.level_frames_by_world = {i: {'normal': None, 'selected': None, 'locked': None, 'hover': None} for i in range(1, 6)}
        self.level_frames_scaled = {}
        
        frame_files = {
            'normal': 'level_frame_normal.png',
            'selected': 'level_frame_selected.png',
            'locked': 'level_frame_locked.png',
            'hover': 'level_frame_hover.png',
            'info_panel': 'info_panel_frame.png',
        }
        
        base_paths = [
            os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'assets', 'ui'),
            os.path.join(os.path.dirname(os.path.dirname(__file__)), 'assets', 'ui'),
            'assets/ui',
            '../assets/ui',
        ]

        campaign_base_paths = [
            os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'assets', 'campaign_level'),
            os.path.join(os.path.dirname(os.path.dirname(__file__)), 'assets', 'campaign_level'),
            'assets/campaign_level',
            '../assets/campaign_level',
        ]

        world_frame_candidates = {
            'normal': ['d{w}_normal.png', 'd{w}_nomal.png', 'd{w}_norma.png'],
            'selected': ['d{w}_selected.png'],
            'locked': ['d{w}_locked.png'],
            'hover': ['d{w}_hover.png'],
        }

        for world in range(1, 6):
            for frame_type, patterns in world_frame_candidates.items():
                for base_path in campaign_base_paths:
                    for pattern in patterns:
                        filename = pattern.format(w=world)
                        try:
                            path = os.path.join(base_path, filename)
                            if os.path.exists(path):
                                self.level_frames_by_world[world][frame_type] = pygame.image.load(path).convert_alpha()
                                break
                        except Exception:
                            continue
                    if self.level_frames_by_world[world][frame_type] is not None:
                        break
        
        for frame_type, filename in frame_files.items():
            for base_path in base_paths:
                try:
                    path = os.path.join(base_path, filename)
                    if os.path.exists(path):
                        self.level_frames[frame_type] = pygame.image.load(path).convert_alpha()
                        break
                except Exception as e:
                    continue
    
    def _load_lock_icon(self) -> None:
        """Kilit ikonunu yükle"""
        import os
        
        self.lock_icon = None
        self.lock_icon_scaled = None
        
        # Olası kilit ikonu yolları
        possible_paths = [
            os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'assets', 'ui', 'icon_lock.png'),
            os.path.join(os.path.dirname(os.path.dirname(__file__)), 'assets', 'ui', 'icon_lock.png'),
            'assets/ui/icon_lock.png',
            '../assets/ui/icon_lock.png',
        ]
        
        for path in possible_paths:
            try:
                if os.path.exists(path):
                    self.lock_icon = pygame.image.load(path).convert_alpha()
                    # Level butonuna sığacak şekilde ölçekle (buton boyutunun %65'i)
                    icon_size = 42  # Varsayılan boyut
                    self.lock_icon_scaled = pygame.transform.smoothscale(self.lock_icon, (icon_size, icon_size))
                    break
            except Exception as e:
                print(f"[LOCK ICON] Yükleme hatası: {e}")
                continue
    
    def _load_star_icon(self) -> None:
        """Yıldız ikonunu yükle"""
        import os
        
        self.star_icon_small = None
        self.star_icon_medium = None
        
        # Olası yıldız ikonu yolları
        possible_paths = [
            os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'assets', 'ui', 'yildiz.png'),
            os.path.join(os.path.dirname(os.path.dirname(__file__)), 'assets', 'ui', 'yildiz.png'),
            'assets/ui/yildiz.png',
            '../assets/ui/yildiz.png',
        ]
        
        for path in possible_paths:
            try:
                if os.path.exists(path):
                    star_img = pygame.image.load(path).convert_alpha()
                    # 2 farklı boyut
                    self.star_icon_small = pygame.transform.smoothscale(star_img, (14, 14))
                    self.star_icon_medium = pygame.transform.smoothscale(star_img, (18, 18))
                    print(f"[STAR ICON] Yıldız ikonu yüklendi: {path}")
                    break
            except Exception as e:
                print(f"[STAR ICON] Yükleme hatası: {e}")
                continue

    def _draw_lock_icon(self, rect: pygame.Rect) -> None:
        """Premium kilit ikonu - PNG veya fallback"""
        cx = rect.centerx
        cy = rect.centery
        
        # PNG ikonu varsa kullan
        if self.lock_icon_scaled:
            # İkonu buton boyutuna göre ölçekle
            target_size = int(min(rect.width, rect.height) * 0.85)
            if target_size != self.lock_icon_scaled.get_width():
                self.lock_icon_scaled = pygame.transform.smoothscale(self.lock_icon, (target_size, target_size))
            
            icon_rect = self.lock_icon_scaled.get_rect(center=(cx, cy))
            self.screen.blit(self.lock_icon_scaled, icon_rect)
        else:
            # Fallback: eski çizim yöntemi
            body_width = 18
            body_height = 14
            body_rect = pygame.Rect(cx - body_width // 2, cy - 2, body_width, body_height)
            pygame.draw.rect(self.screen, self.COLORS['gray'], body_rect, border_radius=UIStyle.BORDER_RADIUS_SMALL)
            
            arc_rect = pygame.Rect(cx - 8, cy - 12, 16, 14)
            pygame.draw.arc(self.screen, self.COLORS['gray'], arc_rect, 0, math.pi, 3)
    
    def _draw_level_info(self) -> None:
        """Premium level bilgi paneli - Yıldız koşulları ile"""
        width = self.screen.get_width()
        height = self.screen.get_height()
        # Panel ve iç kutular pencereye göre ölçeklenir
        info_scale = self._get_ui_scale(min_scale=0.68, max_scale=1.18)
        s = lambda v, minimum=1: max(minimum, int(round(v * info_scale)))
        world_color = self.WORLD_COLORS[self.current_world]
        
        # Panel - iki kartlı düzen için optimize
        panel_width = min(s(760), width - s(40))
        panel_height = min(s(250), height - s(70))
        panel_height = max(s(155), panel_height)
        panel_x = (width - panel_width) // 2
        panel_y = height - panel_height - s(10)
        
        panel_rect = pygame.Rect(panel_x, panel_y, panel_width, panel_height)
        
        # Ana menü ile uyumlu glass panel
        if self.retro_style:
            self.retro_style.draw_glass_panel(
                self.screen,
                panel_rect,
                alpha=200,
                border_color=world_color,
                glow=True,
            )
        else:
            # Fallback: eski glassmorphism panel
            panel_surf = pygame.Surface((panel_width, panel_height), pygame.SRCALPHA)
            panel_surf.fill(UIColors.GLASS_BG)
            
            # Üst highlight
            for i in range(15):
                alpha = int(30 * (1 - i / 15))
                pygame.draw.line(panel_surf, UIColors.GLASS_HIGHLIGHT[:3] + (alpha,), (0, i), (panel_width, i))
            
            self.screen.blit(panel_surf, panel_rect.topleft)
            
            # Glow border
            glow_rect = panel_rect.inflate(8, 8)
            pygame.draw.rect(self.screen, (*world_color, 25), glow_rect, border_radius=UIStyle.BORDER_RADIUS_LARGE)
            pygame.draw.rect(self.screen, (*world_color, 180), panel_rect, 2, border_radius=UIStyle.BORDER_RADIUS_MEDIUM)
        
        # Level bilgisi - hover edilen level varsa onu göster, yoksa seçili level
        display_level = self.hovered_level if self.hovered_level else self.selected_level
        level_config = get_level(display_level)
        if not level_config:
            return
        
        is_unlocked = self._is_level_unlocked(display_level)
        stars = self._get_level_stars(display_level)
        
        # Level ismi - glow efektli
        lang = get_language()
        level_name = level_config.name.get(lang, level_config.name.get('en', f"{t('level')} {display_level}"))
        name_text = f"{t('level')} {display_level}: {level_name}"
        name_surf = self.font_medium.render(name_text, True, world_color)
        
        # Glow
        glow_surf = self.font_medium.render(name_text, True, world_color)
        for dx, dy, a in [(-1, 0, 40), (1, 0, 40)]:
            glow_surf.set_alpha(a)
            self.screen.blit(glow_surf, (panel_x + 18 + dx, panel_y + 14 + dy))
        self.screen.blit(name_surf, (panel_x + s(18), panel_y + s(12)))

        # === İKİLİ KART DÜZENİ ===
        inner_pad = s(18)
        header_height = s(34)
        badge_height = s(26)
        cards_top = panel_y + header_height + s(12)
        cards_height = panel_height - header_height - badge_height - s(24)
        card_gap = s(18)
        cards_width = panel_width - inner_pad * 2
        card_width = (cards_width - card_gap) // 2

        left_card = pygame.Rect(panel_x + inner_pad, cards_top, card_width, cards_height)
        right_card = pygame.Rect(left_card.right + card_gap, cards_top, card_width, cards_height)

        def draw_info_card(rect: pygame.Rect, border_color: Tuple[int, int, int]) -> None:
            if self.retro_style:
                self.retro_style.draw_glass_panel(
                    self.screen,
                    rect,
                    alpha=175,
                    border_color=border_color,
                    glow=False,
                )
            else:
                card_surf = pygame.Surface(rect.size, pygame.SRCALPHA)
                card_surf.fill(UIColors.GLASS_BG)
                for i in range(8):
                    alpha = int(24 * (1 - i / 8))
                    pygame.draw.line(card_surf, UIColors.GLASS_HIGHLIGHT[:3] + (alpha,), (0, i), (rect.width, i))
                self.screen.blit(card_surf, rect.topleft)
                pygame.draw.rect(self.screen, (*border_color, 120), rect, 1, border_radius=UIStyle.BORDER_RADIUS_MEDIUM)

        draw_info_card(left_card, world_color)
        draw_info_card(right_card, world_color)

        # === SOL KART: GÖREVLER ===
        left_x = left_card.x + s(12)
        obj_title = self.font_small.render(t('campaign_objectives_title'), True, self.COLORS['gray'])
        self.screen.blit(obj_title, (left_x, left_card.y + s(10)))

        if level_config.objectives:
            obj_y = left_card.y + s(34)
            for obj in level_config.objectives[:3]:
                obj_type = obj.get('type', 'clear_lines')
                target = obj.get('target', 0)

                formatted_target = f"{target:,}"
                if lang == 'tr':
                    formatted_target = formatted_target.replace(',', '.')

                obj_names = {
                    'clear_lines': t('campaign_obj_clear_lines', target=formatted_target),
                    'clear_garbage': t('campaign_obj_clear_garbage'),
                    'score': t('campaign_obj_score', target=formatted_target),
                    'tetris': t('campaign_obj_tetris', target=formatted_target),
                    'combo': t('campaign_obj_combo', target=formatted_target),
                    'survival': t('campaign_obj_survival', target=formatted_target),
                    'time': t('campaign_obj_time', target=formatted_target),
                    'time_challenge': t('campaign_obj_time', target=formatted_target),
                    'special_block': t('campaign_obj_special_block', target=formatted_target),
                    'perfect_clear': t('campaign_obj_perfect_clear', target=formatted_target),
                    'move_efficiency': t('campaign_obj_move_efficiency', target=formatted_target),
                }
                obj_text = obj_names.get(obj_type, f"{obj_type}: {formatted_target}")

                pygame.draw.circle(self.screen, world_color, (left_x + s(8), obj_y + s(8)), max(2, s(4)))
                surf = self.font_small.render(obj_text, True, self.COLORS['text'])
                self.screen.blit(surf, (left_x + s(20), obj_y))
                obj_y += s(22)

        # === SAĞ KART: YILDIZ KOŞULLARI ===
        right_x = right_card.x + s(12)
        star_title = self.font_small.render(t('campaign_star_conditions_title'), True, self.COLORS['gray'])
        self.screen.blit(star_title, (right_x, right_card.y + s(10)))

        star_conditions = level_config.stars
        star_y = right_card.y + s(34)
        
        star_colors = {
            1: UIColors.TEXT_SECONDARY,  # Gümüş
            2: UIColors.NEON_ORANGE,     # Bronz/Turuncu
            3: UIColors.NEON_GOLD,       # Altın
        }
        
        for star_num in [1, 2, 3]:
            condition = star_conditions.get(star_num, {})
            cond_type = condition.get('type', 'complete')
            cond_value = condition.get('value', 0)
            
            # Yıldız sembolü
            star_color = star_colors.get(star_num, self.COLORS['gold'])
            earned = stars >= star_num
            display_color = star_color if earned else (80, 80, 80)
            
            # X pozisyonu
            x_pos = right_x
            
            # Yıldız PNG'lerini çiz (eğer yüklüyse)
            if self.star_icon_small:
                # star_num kadar yıldız çiz
                for i in range(star_num):
                    # Renkleri karartmak için (earned değilse)
                    if not earned:
                        darkened = self.star_icon_small.copy()
                        darkened.fill((80, 80, 80, 255), special_flags=pygame.BLEND_RGBA_MULT)
                        self.screen.blit(darkened, (x_pos + i * s(16), star_y))
                    else:
                        self.screen.blit(self.star_icon_small, (x_pos + i * s(16), star_y))
                x_pos += star_num * s(16) + s(5)
            else:
                # Fallback: * sembolleri
                star_text = "*" * star_num
                star_surf = self.font_small.render(star_text, True, display_color)
                self.screen.blit(star_surf, (x_pos, star_y))
                x_pos += star_surf.get_width() + s(5)
            
            # Koşul açıklaması
            formatted_value = f"{cond_value:,}"
            if lang == 'tr':
                formatted_value = formatted_value.replace(',', '.')

            if cond_type == 'complete':
                cond_text = t('campaign_cond_complete')
            elif cond_type == 'score':
                cond_text = t('campaign_cond_score', value=formatted_value)
            elif cond_type == 'combo':
                cond_text = t('campaign_cond_combo', value=formatted_value)
            elif cond_type == 'multi_clear':
                if cond_value == 2:
                    cond_text = t('campaign_cond_multi_clear_2')
                elif cond_value == 3:
                    cond_text = t('campaign_cond_multi_clear_3')
                else:
                    cond_text = t('campaign_cond_multi_clear_n', value=formatted_value)
            elif cond_type == 'tetris':
                cond_text = t('campaign_cond_tetris', value=formatted_value)
            elif cond_type == 'combo_chain':
                cond_text = t('campaign_cond_combo_chain', value=formatted_value)
            elif cond_type == 'time_limit':
                cond_text = t('campaign_cond_time_limit', value=formatted_value)
            elif cond_type == 'extra_lines':
                cond_text = t('campaign_cond_extra_lines', value=formatted_value)
            elif cond_type == 'efficiency':
                cond_text = t('campaign_cond_efficiency', value=formatted_value)
            elif cond_type == 'time':
                cond_text = t('campaign_cond_time', value=formatted_value)
            else:
                desc = condition.get('description', {})
                cond_text = desc.get(lang, desc.get('en', str(cond_type)))
            
            # Koşul metni
            cond_surf = self.font_small.render(f": {cond_text}", True, display_color)
            self.screen.blit(cond_surf, (x_pos, star_y))
            
            # Tik işareti (kazanılmışsa)
            if earned:
                tick_surf = self.font_small.render(" OK", True, self.COLORS['green'])
                self.screen.blit(tick_surf, (x_pos + cond_surf.get_width() + s(5), star_y))
            
            star_y += s(22)

        # === ALT BÖLÜM: DURUM BADGE ===
        status_y = panel_y + panel_height - badge_height - s(10)
        
        if not is_unlocked:
            status_text = t('campaign_status_locked')
            status_color = self.COLORS['red']
            badge_color = UIColors.BG_MEDIUM
        elif stars == 3:
            status_text = t('campaign_status_perfect')
            status_color = self.COLORS['gold']
            badge_color = UIColors.BG_LIGHT
        elif stars > 0:
            status_text = t('campaign_status_stars', stars=stars)
            status_color = self.COLORS['green']
            badge_color = UIColors.BG_MEDIUM
        else:
            status_text = t('campaign_status_ready')
            status_color = self.COLORS['cyan']
            badge_color = UIColors.BG_MEDIUM
        
        # Badge arka plan
        status_surf = self.font_small.render(status_text, True, status_color)
        badge_width = status_surf.get_width() + s(20)
        badge_rect = pygame.Rect(panel_x + panel_width - badge_width - s(18), status_y, badge_width, badge_height)
        
        badge_surf = pygame.Surface((badge_width, badge_height), pygame.SRCALPHA)
        badge_surf.fill((*badge_color, 200))
        self.screen.blit(badge_surf, badge_rect.topleft)
        pygame.draw.rect(self.screen, (*status_color, 150), badge_rect, 1, border_radius=UIStyle.BORDER_RADIUS_SMALL)

        self.screen.blit(status_surf, (badge_rect.x + s(10), badge_rect.y + max(1, s(3))))
    
    def _draw_bottom_buttons(self) -> None:
        """Premium alt butonlar"""
        width = self.screen.get_width()
        height = self.screen.get_height()
        ui_scale = self._get_ui_scale()
        s = lambda v, minimum=1: max(minimum, int(round(v * ui_scale)))
        world_color = self.WORLD_COLORS[self.current_world]
        
        play_height = s(44)
        play_width = s(176)
        play_y = height - play_height - s(14)

        self.back_button = None
        
        # Oyna butonu
        play_x = width - play_width - s(25)
        self.play_button = pygame.Rect(play_x, play_y, play_width, play_height)
        
        is_unlocked = self._is_level_unlocked(self.selected_level)
        
        if is_unlocked:
            if self.retro_style:
                self.retro_style.draw_glass_panel(
                    self.screen,
                    self.play_button,
                    alpha=215,
                    border_color=world_color,
                    glow=True,
                )
            else:
                btn_surf = pygame.Surface((play_width, play_height), pygame.SRCALPHA)
                for row in range(play_height):
                    alpha = int(210 - 40 * (row / play_height))
                    pygame.draw.line(btn_surf, (*world_color, alpha), (0, row), (play_width, row))
                self.screen.blit(btn_surf, self.play_button.topleft)
                glow_rect = self.play_button.inflate(10, 10)
                pygame.draw.rect(self.screen, (*world_color, 35), glow_rect, border_radius=UIStyle.BORDER_RADIUS_MEDIUM)
                pygame.draw.rect(self.screen, (*world_color, 200), self.play_button, 2, border_radius=UIStyle.BORDER_RADIUS_MEDIUM)

            play_color = UIColors.TEXT_PRIMARY
        else:
            if self.retro_style:
                self.retro_style.draw_glass_panel(
                    self.screen,
                    self.play_button,
                    alpha=160,
                    border_color=UIColors.BUTTON_BORDER,
                    glow=False,
                )
            else:
                btn_surf = pygame.Surface((play_width, play_height), pygame.SRCALPHA)
                btn_surf.fill((*UIColors.BUTTON_DISABLED, 190))
                self.screen.blit(btn_surf, self.play_button.topleft)
                pygame.draw.rect(self.screen, (*UIColors.BUTTON_BORDER, 140), self.play_button, 2, border_radius=UIStyle.BORDER_RADIUS_MEDIUM)
            play_color = UIColors.TEXT_MUTED
        
        play_text = self.font_large.render(t('campaign_play'), True, play_color)
        play_rect = play_text.get_rect(center=self.play_button.center)
        self.screen.blit(play_text, play_rect)
    
    def _draw_world_transition_overlay(self) -> None:
        """Dünya geçişi sırasında fade overlay çiz (optimized)"""
        width, height = self.screen.get_size()
        
        # Cache overlay surface (performance optimization)
        if self._overlay_cache is None or self._overlay_cache.get_size() != (width, height):
            self._overlay_cache = pygame.Surface((width, height), pygame.SRCALPHA)
        
        # Fade in/out animasyonu (0.0 -> 1.0 -> 0.0)
        # İlk yarıda fade in (karartma), ikinci yarıda fade out (açma)
        progress = self.world_transition_progress
        
        if progress <= 0.5:
            # Fade in (0.0 -> 0.5 arası, karartma)
            alpha = int((progress / 0.5) * 180)
        else:
            # Fade out (0.5 -> 1.0 arası, açma)
            alpha = int(((1.0 - progress) / 0.5) * 180)
        
        if alpha > 0:
            # Sadece alpha'yı değiştir (yeniden fill yerine)
            self._overlay_cache.fill((0, 0, 0, 0))  # Temizle
            self._overlay_cache.set_alpha(alpha)
            pygame.draw.rect(self._overlay_cache, (0, 0, 0, 255), (0, 0, width, height))
            self.screen.blit(self._overlay_cache, (0, 0))


