"""Co-op Kampanya Level Seçim Ekranı

20 level, 2 dünya halinde basitleştirilmiş level seçim arayüzü.
Ana campaign level_select.py'den esinlenilmiştir.
"""
from __future__ import annotations

import math
import pygame
from typing import Dict, Any, Optional

from .coop_level_data import (
    get_coop_level, get_coop_world_levels,
    TOTAL_COOP_LEVELS, COOP_WORLDS, CoopLevelConfig,
)
from platform_utils import get_mouse_pos, normalize_mouse_pos
from ui_theme import UIColors, UIFonts, UIStyle
from localization import t, get_language
from retro_style import retro_style
from ui_scaling import get_projected_effective_scale


# Dünya renk paleti (neon temaya uyumlu)
_WORLD_COLORS = {
    1: (0, 255, 150),    # Neon yeşil — Başlangıç Vadisi
    2: (0, 240, 255),    # Neon cyan — Koordinasyon Kalesi
}

_WORLD_NAMES = {
    1: {'tr': 'Başlangıç Vadisi', 'en': 'Starter Valley'},
    2: {'tr': 'Koordinasyon Kalesi', 'en': 'Coordination Castle'},
}


class CoopLevelSelect:
    """Co-op kampanya level seçim ekranı."""

    def __init__(
        self,
        screen: pygame.Surface,
        settings_manager=None,
        user_manager=None,
    ):
        self.screen = screen
        self.settings_manager = settings_manager
        self.user_manager = user_manager

        self.window_width = screen.get_width()
        self.window_height = screen.get_height()

        self.current_world = 1
        self.hovered_level: Optional[int] = None
        self.animation_time = 0.0

        # İlerleme
        self.progress = self._load_progress()

        # Layout cache
        self._level_rects: Dict[int, pygame.Rect] = {}
        self._back_rect: Optional[pygame.Rect] = None
        self._world_tab_rects: Dict[int, pygame.Rect] = {}

    # ------------------------------------------------------------------
    # Progress
    # ------------------------------------------------------------------

    def _load_progress(self) -> Dict[str, Any]:
        if not self.settings_manager:
            return {'completed_levels': {}, 'highest_level': 0, 'total_stars': 0}
        progress = self.settings_manager.get('coop_campaign_progress', {})
        if not isinstance(progress, dict):
            progress = {}
        return {
            'completed_levels': progress.get('completed_levels', {}),
            'highest_level': progress.get('highest_level', 0),
            'total_stars': progress.get('total_stars', 0),
        }

    def _is_level_unlocked(self, level_num: int) -> bool:
        if level_num == 1:
            return True
        prev = str(level_num - 1)
        completed = self.progress.get('completed_levels', {})
        return prev in completed and completed[prev].get('completed', False)

    def _get_level_stars(self, level_num: int) -> int:
        completed = self.progress.get('completed_levels', {})
        return completed.get(str(level_num), {}).get('stars', 0)

    # ------------------------------------------------------------------
    # Input
    # ------------------------------------------------------------------

    def handle_input(self, event: pygame.event.Event) -> Optional[str]:
        """Event işle. Dönüş: 'back', 'play_N', None."""
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                return 'back'

        if event.type == pygame.VIDEORESIZE:
            self.window_width = self.screen.get_width()
            self.window_height = self.screen.get_height()
            return None

        mx, my = 0, 0
        if event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEMOTION):
            mx, my = normalize_mouse_pos(event.pos) if hasattr(event, 'pos') else get_mouse_pos()

        if event.type == pygame.MOUSEMOTION:
            self.hovered_level = None
            for lv, rect in self._level_rects.items():
                if rect.collidepoint(mx, my):
                    self.hovered_level = lv
                    break

        if event.type == pygame.MOUSEBUTTONDOWN and getattr(event, 'button', None) == 1:
            # Back butonu
            if self._back_rect and self._back_rect.collidepoint(mx, my):
                return 'back'

            # Dünya tabları
            for w, rect in self._world_tab_rects.items():
                if rect.collidepoint(mx, my):
                    self.current_world = w
                    return None

            # Level butonları
            for lv, rect in self._level_rects.items():
                if rect.collidepoint(mx, my) and self._is_level_unlocked(lv):
                    return f'play_{lv}'

        return None

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    def update(self, dt: float) -> None:
        self.animation_time += dt

    # ------------------------------------------------------------------
    # Draw
    # ------------------------------------------------------------------

    def draw(self) -> None:
        w, h = self.window_width, self.window_height
        self.screen.fill(UIColors.BG_DARK)
        scale = self._ui_scale()

        def s(v, minimum=1):
            return max(minimum, int(v * scale))

        # --- Başlık + yıldız (glass panel) ---
        header_h = s(90)
        header_rect = pygame.Rect(s(60), s(10), w - s(120), header_h)
        retro_style.draw_glass_panel(self.screen, header_rect, alpha=165,
                                      border_color=(*retro_style.primary[:3], 100))

        f_title = retro_style.get_font(s(36, minimum=20), bold=True)
        title = t('coop_campaign_title', default='CO-OP KAMPANYA')
        ts = f_title.render(title, True, retro_style.primary)
        self.screen.blit(ts, (w // 2 - ts.get_width() // 2, header_rect.y + s(12)))

        total_stars = self.progress.get('total_stars', 0)
        star_text = f"★ {total_stars}/{TOTAL_COOP_LEVELS * 3}"
        f_star_header = retro_style.get_font(s(20, minimum=14), bold=True)
        ss = f_star_header.render(star_text, True, UIColors.NEON_GOLD)
        self.screen.blit(ss, (w // 2 - ss.get_width() // 2, header_rect.y + s(52)))

        # --- Dünya tabları ---
        tab_y = header_rect.bottom + s(12)
        tab_h = s(36)
        tab_w = s(200)
        tab_gap = s(16)
        total_tab_w = COOP_WORLDS * tab_w + (COOP_WORLDS - 1) * tab_gap
        tab_x0 = w // 2 - total_tab_w // 2
        self._world_tab_rects.clear()

        lang = get_language()
        f_tab = retro_style.get_font(s(18, minimum=12), bold=True)

        for wi in range(1, COOP_WORLDS + 1):
            x = tab_x0 + (wi - 1) * (tab_w + tab_gap)
            rect = pygame.Rect(x, tab_y, tab_w, tab_h)
            self._world_tab_rects[wi] = rect
            color = _WORLD_COLORS.get(wi, retro_style.primary)
            active = wi == self.current_world

            if active:
                # Aktif tab — dolgu + neon border
                retro_style.draw_glass_panel(self.screen, rect, alpha=200,
                                              border_color=color, glow=True)
            else:
                retro_style.draw_glass_panel(self.screen, rect, alpha=100,
                                              border_color=(60, 70, 90))

            wname = _WORLD_NAMES.get(wi, {}).get(lang, _WORLD_NAMES.get(wi, {}).get('en', f'World {wi}'))
            text_color = (10, 12, 28) if active else retro_style.text_secondary
            lbl = f_tab.render(wname, True, text_color)
            self.screen.blit(lbl, (x + tab_w // 2 - lbl.get_width() // 2,
                                   tab_y + tab_h // 2 - lbl.get_height() // 2))

        # --- Level grid ---
        grid_top = tab_y + tab_h + s(16)
        self._draw_level_grid(grid_top, scale, s)

        # --- Back butonu (sol üst) ---
        back_text = f"← {t('coop_main_menu', default='Ana Menü')}"
        f_back = retro_style.get_font(s(18, minimum=12), bold=True)
        bs = f_back.render(back_text, True, retro_style.text_secondary)
        bx, by = s(16), s(16)
        self._back_rect = pygame.Rect(bx, by, bs.get_width() + s(20), bs.get_height() + s(10))
        retro_style.draw_glass_panel(self.screen, self._back_rect, alpha=120,
                                      border_color=(60, 70, 90), top_highlight=False)
        self.screen.blit(bs, (bx + s(10), by + s(5)))

        pygame.display.flip()

    def _draw_level_grid(self, top: int, scale: float, s) -> None:
        """Level butonlarını glass card grid olarak çiz."""
        w, h = self.window_width, self.window_height
        self._level_rects.clear()

        levels = get_coop_world_levels(self.current_world)
        if not levels:
            return

        cols = 5
        btn_w = s(110)
        btn_h = s(88)
        gap_x = s(14)
        gap_y = s(14)
        total_grid_w = cols * btn_w + (cols - 1) * gap_x
        x0 = w // 2 - total_grid_w // 2

        world_color = _WORLD_COLORS.get(self.current_world, retro_style.primary)
        lang = get_language()

        f_num = retro_style.get_font(s(22, minimum=14), bold=True)
        f_name = retro_style.get_font(s(12, minimum=9))
        f_star = retro_style.get_font(s(14, minimum=10))

        for idx, lcfg in enumerate(levels):
            col = idx % cols
            row = idx // cols
            x = x0 + col * (btn_w + gap_x)
            y = top + row * (btn_h + gap_y)
            rect = pygame.Rect(x, y, btn_w, btn_h)
            self._level_rects[lcfg.level] = rect

            unlocked = self._is_level_unlocked(lcfg.level)
            stars = self._get_level_stars(lcfg.level)
            hovered = self.hovered_level == lcfg.level

            # Glass card arka plan
            if not unlocked:
                retro_style.draw_glass_panel(self.screen, rect, alpha=80,
                                              border_color=(40, 45, 60), top_highlight=False)
            elif hovered:
                retro_style.draw_glass_panel(self.screen, rect, alpha=200,
                                              border_color=world_color, glow=True)
            else:
                retro_style.draw_glass_panel(self.screen, rect, alpha=120,
                                              border_color=(*world_color[:3],) + (80,) if len(world_color) == 3 else world_color,
                                              top_highlight=False)

            # Boss badge (neon kırmızı)
            if lcfg.is_boss:
                badge_w, badge_h = s(24), s(16)
                badge_r = pygame.Rect(x + btn_w - badge_w - s(4), y + s(4), badge_w, badge_h)
                pygame.draw.rect(self.screen, UIColors.NEON_RED, badge_r, border_radius=4)
                bs = f_star.render('BOSS', True, (255, 255, 255))
                self.screen.blit(bs, (badge_r.centerx - bs.get_width() // 2,
                                      badge_r.centery - bs.get_height() // 2))

            # Level numarası
            text_color = retro_style.text_primary if unlocked else retro_style.text_muted
            num_surf = f_num.render(str(lcfg.level), True, world_color if (unlocked and hovered) else text_color)
            self.screen.blit(num_surf, (x + btn_w // 2 - num_surf.get_width() // 2,
                                        y + s(10)))

            # Level adı
            name = lcfg.name.get(lang, lcfg.name.get('en', ''))
            if len(name) > 13:
                name = name[:12] + '…'
            name_color = retro_style.text_secondary if unlocked else retro_style.text_muted
            name_surf = f_name.render(name, True, name_color)
            self.screen.blit(name_surf, (x + btn_w // 2 - name_surf.get_width() // 2,
                                          y + s(36)))

            # Yıldızlar veya kilit
            if unlocked:
                star_y = y + btn_h - s(22)
                star_size = s(14, minimum=10)
                star_gap = s(3)
                total_star_w = 3 * star_size + 2 * star_gap
                sx = x + btn_w // 2 - total_star_w // 2
                for si in range(3):
                    color = UIColors.NEON_GOLD if si < stars else (50, 55, 75)
                    self._draw_mini_star(self.screen, sx + si * (star_size + star_gap),
                                         star_y, star_size, color)
            else:
                lock_surf = f_star.render('🔒', True, retro_style.text_muted)
                self.screen.blit(lock_surf, (x + btn_w // 2 - lock_surf.get_width() // 2,
                                              y + btn_h - s(22)))

    @staticmethod
    def _draw_mini_star(surface, x, y, size, color):
        """Küçük 5 köşeli yıldız çiz."""
        cx = x + size * 0.5
        cy = y + size * 0.5
        r_outer = size * 0.5
        r_inner = size * 0.2
        points = []
        for i in range(10):
            angle = i * math.pi / 5 - math.pi / 2
            r = r_outer if i % 2 == 0 else r_inner
            points.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
        if len(points) >= 3:
            pygame.draw.polygon(surface, color, points)
            # Kenar parlaması
            edge = tuple(min(255, c + 40) for c in color[:3])
            pygame.draw.polygon(surface, edge, points, 1)

    def _ui_scale(self) -> float:
        target = getattr(self, 'screen', None)
        if target is None:
            target = (
                getattr(self, 'window_width', 1400),
                getattr(self, 'window_height', 900),
            )
        return get_projected_effective_scale(
            target,
            min_scale=0.72,
            max_scale=1.18,
            reference_size=(1400.0, 900.0),
        )
