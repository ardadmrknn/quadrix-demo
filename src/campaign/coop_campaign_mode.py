"""Co-op Kampanya Modu

CoopGame üzerinde kampanya görev/yıldız/ilerleme katmanı.
CampaignMode'un tek oyuncu kampanyasına benzer yapıda:
  - Level konfigürasyonu (hız, görevler, yıldız koşulları)
  - Görev takibi (event-driven objectives)
  - Yıldız hesaplama (1-3 yıldız)
  - İlerleme kaydetme / yükleme
"""
from __future__ import annotations

import os
import sys
import pygame
from typing import Dict, Any, Optional, List
from pathlib import Path

# CoopGame'i import et (src root'tan bağımsız çalışabilir)
try:
    from coop_game import CoopGame
except ImportError:
    from src.coop_game import CoopGame

try:
    from localization import t
    from retro_style import retro_style
    from ui_theme import UIFonts, UIColors
except ImportError:
    from src.localization import t
    from src.retro_style import retro_style
    from src.ui_theme import UIFonts, UIColors

from .coop_level_data import get_coop_level, CoopLevelConfig, TOTAL_COOP_LEVELS
from .coop_objectives import create_coop_objective


class CoopCampaignMode(CoopGame):
    """Co-op kampanya modu — CoopGame + görev/yıldız katmanı."""

    def __init__(
        self,
        current_level: int = 1,
        sound_enabled: bool = True,
        effects_enabled: bool = True,
        screen=None,
        fullscreen: bool = True,
        user_manager=None,
        settings_manager=None,
        sound_manager=None,
    ):
        # Level config yükle
        self.current_level_num = current_level
        self.level_config: Optional[CoopLevelConfig] = get_coop_level(current_level)
        if not self.level_config:
            raise ValueError(f"Geçersiz co-op level numarası: {current_level}")
        self._music_mode_key = 'campaign'

        # CoopGame'i başlat
        super().__init__(
            sound_enabled=sound_enabled,
            effects_enabled=effects_enabled,
            screen=screen,
            fullscreen=fullscreen,
            user_manager=user_manager,
            settings_manager=settings_manager,
            sound_manager=sound_manager,
        )

        # Level config'e göre hız ayarla
        self.fall_speed = float(self.level_config.speed)

        # Hold kısıtlaması
        self._no_hold = self.level_config.no_hold

        # Preview kısıtlaması
        self._no_preview = self.level_config.no_preview

        # Görevleri oluştur
        self.objectives: List = []
        for obj_config in self.level_config.objectives:
            obj = create_coop_objective(obj_config)
            self.objectives.append(obj)

        # Yıldız koşulları
        self.star_conditions = self.level_config.stars
        self.earned_stars = 0

        # Level durumu
        self.level_complete = False
        self.level_failed = False
        self.fail_reason = ''

        # İstatistikler (yıldız hesaplama için)
        self.tetris_count = 0
        self.total_combos = 0
        self.max_combo_chain = 0

        # Event listener kaydet
        self._event_listeners.append(self._on_game_event)

    # ------------------------------------------------------------------
    # Event listener
    # ------------------------------------------------------------------

    def _on_game_event(self, event_type: str, event_data: Dict[str, Any]) -> None:
        """CoopGame olaylarını görevlere yönlendir."""
        if self.level_complete or self.level_failed:
            return

        # İstatistik güncelle
        if event_type == 'tetris':
            self.tetris_count += 1
        if event_type == 'lines_cleared':
            lines = event_data.get('lines', 0)
            if lines > 0:
                self.total_combos += 1

        # Görevlere bildir
        for obj in self.objectives:
            try:
                obj.update(self, event_type, event_data)
            except Exception:
                pass

        # Tamamlanma kontrolü
        if all(obj.completed for obj in self.objectives):
            self._handle_level_complete()

    # ------------------------------------------------------------------
    # Hold kısıtlaması
    # ------------------------------------------------------------------

    def _use_shared_hold(self, player: str) -> None:
        if self._no_hold:
            return
        super()._use_shared_hold(player)

    # ------------------------------------------------------------------
    # Oyun döngüsü override
    # ------------------------------------------------------------------

    def update(self, delta_time: float) -> None:
        super().update(delta_time)

        # Game over → level failed
        if self.game_over and not self.level_failed and not self.level_complete:
            self._handle_level_failed(t('coop_game_over', default='Game Over'))

    def handle_input(self):
        """Level tamamlandıysa özel input akışı."""
        if self.level_complete or self.level_failed:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return False
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        return 'menu'
                    if event.key == pygame.K_r:
                        self._restart_level()
                        return True
                    # Herhangi bir tuş → sonraki level veya menü
                    if self.level_complete:
                        return 'next_level'
                    else:
                        return 'menu'
                if event.type == pygame.MOUSEBUTTONDOWN:
                    if self.level_complete:
                        return 'next_level'
                    else:
                        return 'menu'
            return True

        return super().handle_input()

    # ------------------------------------------------------------------
    # Level complete / failed
    # ------------------------------------------------------------------

    def _handle_level_complete(self) -> None:
        if self.level_complete:
            return
        self.level_complete = True
        self.earned_stars = self._calculate_stars()
        self._save_progress()
        if self.sound:
            try:
                self.sound.play('tutorial_complete')
            except Exception:
                self.sound.play('confirm')

    def _handle_level_failed(self, reason: str = '') -> None:
        if self.level_failed:
            return
        self.level_failed = True
        self.fail_reason = reason
        self._activate_game_over()

    def _restart_level(self) -> None:
        """Level'ı tamamen yeniden başlat."""
        self.__init__(
            current_level=self.current_level_num,
            sound_enabled=self.sound_enabled,
            effects_enabled=self.effects_enabled,
            screen=self.screen,
            fullscreen=self.fullscreen,
            user_manager=self.user_manager,
            settings_manager=self.settings_manager,
            sound_manager=self.sound,
        )

    # ------------------------------------------------------------------
    # Yıldız hesaplama
    # ------------------------------------------------------------------

    def _calculate_stars(self) -> int:
        stars = 0
        for star_num in (1, 2, 3):
            condition = self.star_conditions.get(star_num)
            if condition and self._is_star_condition_met(condition):
                stars = star_num
            else:
                break
        return stars

    def _is_star_condition_met(self, condition: Dict[str, Any]) -> bool:
        ctype = condition.get('type')
        value = condition.get('value', 0)

        if ctype == 'complete':
            return all(obj.completed for obj in self.objectives)
        if ctype == 'score':
            return self.team_score >= value
        if ctype == 'tetris':
            return self.tetris_count >= value
        if ctype == 'time_limit':
            return self.level_complete and (self.elapsed_time / 1000.0) <= value
        if ctype == 'combo':
            return self.total_combos >= value
        if ctype == 'balanced':
            total_cells = self.p1_total_cells + self.p2_total_cells
            if total_cells < 20:
                return False
            return min(self.p1_contribution_pct, self.p2_contribution_pct) >= value
        return False

    # ------------------------------------------------------------------
    # İlerleme kaydet
    # ------------------------------------------------------------------

    def _save_progress(self) -> None:
        if not self.settings_manager:
            return

        progress = self.user_manager.get_coop_campaign_progress()
        if not isinstance(progress, dict):
            progress = {}

        completed = progress.get('completed_levels', {})
        if not isinstance(completed, dict):
            completed = {}

        level_key = str(self.current_level_num)
        existing = completed.get(level_key, {})

        best_stars = max(self.earned_stars, existing.get('stars', 0))
        best_score = max(self.team_score, existing.get('best_score', 0))

        completed[level_key] = {
            'stars': best_stars,
            'best_score': best_score,
            'completed': True,
            'attempts': existing.get('attempts', 0) + 1,
        }

        highest = max(self.current_level_num, progress.get('highest_level', 0))
        total_stars = sum(l.get('stars', 0) for l in completed.values())

        progress['completed_levels'] = completed
        progress['highest_level'] = highest
        progress['total_stars'] = total_stars

        self.user_manager.save_coop_campaign_progress(progress)
        self.settings_manager.save()

    @staticmethod
    def load_progress(user_manager) -> dict:
        """İlerleme verisini yükle (level select için)."""
        if not user_manager:
            return {}
        progress = user_manager.get_coop_campaign_progress()
        return progress if isinstance(progress, dict) else {}

    def get_next_level_num(self) -> Optional[int]:
        """Sonraki level numarasını döndür. Son level'daysa None."""
        nxt = self.current_level_num + 1
        return nxt if nxt <= TOTAL_COOP_LEVELS else None

    # ------------------------------------------------------------------
    # Draw override — görev HUD ve complete/fail ekranı
    # ------------------------------------------------------------------

    def draw(self) -> None:
        self._render_game()

        # Görev çubuğu (oyun sırasında)
        if not self.level_complete and not self.level_failed:
            self._draw_objectives_hud()

        # Level tamamlandı ekranı
        if self.level_complete:
            self._draw_level_complete()

        # Level başarısız ekranı (game over yerine)
        if self.level_failed and not self.level_complete:
            self._draw_level_failed()

        pygame.display.flip()

    def _draw_objectives_hud(self) -> None:
        """Board'un üstünde görev ilerleme paneli (glass panel)."""
        ui = self._ui_scale()

        lang = 'tr'
        try:
            from localization import get_language
            lang = get_language()
        except Exception:
            pass

        s = lambda v, minimum=1: max(minimum, int(v * ui))

        # Panel boyutu hesapla
        obj_count = len(self.objectives)
        line_h = s(18)
        panel_h = s(28) + obj_count * (line_h + s(8)) + s(10)
        panel_w = min(s(320), max(s(200), self.board_offset_x - s(20)))
        panel_x = max(s(8), self.board_offset_x - panel_w - s(12))
        panel_y = self.board_offset_y

        panel_rect = pygame.Rect(panel_x, panel_y, panel_w, panel_h)
        retro_style.draw_glass_panel(self.screen, panel_rect, alpha=175,
                                      border_color=(*retro_style.primary[:3], 100))

        # Level başlık bandı
        header_h = s(26)
        header_rect = pygame.Rect(panel_x + 2, panel_y + 2, panel_w - 4, header_h)
        header_surf = pygame.Surface(header_rect.size, pygame.SRCALPHA)
        header_surf.fill((*UIColors.BG_MEDIUM, 190))
        self.screen.blit(header_surf, header_rect.topleft)
        pygame.draw.line(self.screen, (*retro_style.primary[:3], 140),
                         (header_rect.x, header_rect.bottom),
                         (header_rect.right, header_rect.bottom))

        level_name = self.level_config.name.get(lang, self.level_config.name.get('en', ''))
        title_font = retro_style.get_font(s(14, minimum=10), bold=True)
        title_text = f"L{self.current_level_num}: {level_name}"
        title_surf = title_font.render(title_text, True, retro_style.primary)
        self.screen.blit(title_surf, (panel_x + s(8), panel_y + s(5)))

        # Görev satırları
        y = panel_y + header_h + s(8)
        obj_font = retro_style.get_font(s(13, minimum=9))
        prog_font = retro_style.get_font(s(11, minimum=8))

        for obj in self.objectives:
            completed = obj.completed
            # İkon dairesi
            icon_r = s(7, minimum=5)
            icon_cx = panel_x + s(14)
            icon_cy = y + line_h // 2
            if completed:
                pygame.draw.circle(self.screen, (12, 120, 70), (icon_cx, icon_cy), icon_r)
                pygame.draw.circle(self.screen, (40, 255, 155), (icon_cx, icon_cy), icon_r, 1)
                # Tik çizgisi
                check_pts = [
                    (icon_cx - icon_r // 2, icon_cy),
                    (icon_cx - 1, icon_cy + icon_r // 2),
                    (icon_cx + icon_r // 2, icon_cy - icon_r // 3),
                ]
                pygame.draw.lines(self.screen, (220, 255, 230), False, check_pts, max(1, icon_r // 3))
            else:
                pygame.draw.circle(self.screen, UIColors.BG_MEDIUM, (icon_cx, icon_cy), icon_r)
                pygame.draw.circle(self.screen, retro_style.text_muted, (icon_cx, icon_cy), icon_r, 1)

            # Açıklama
            desc_color = (40, 255, 155) if completed else retro_style.text_secondary
            desc = obj.get_description(lang)
            desc_surf = obj_font.render(desc, True, desc_color)
            self.screen.blit(desc_surf, (panel_x + s(26), y))

            # İlerleme barı
            bar_y = y + line_h - s(2)
            bar_w = panel_w - s(34)
            bar_h = s(5, minimum=3)
            bar_rect = pygame.Rect(panel_x + s(26), bar_y, bar_w, bar_h)
            pygame.draw.rect(self.screen, (30, 35, 55), bar_rect, border_radius=s(2))
            ratio = min(1.0, obj.get_progress_ratio()) if hasattr(obj, 'get_progress_ratio') else (1.0 if completed else 0.0)
            if ratio > 0:
                fill_color = (0, 255, 150) if completed else UIColors.NEON_CYAN
                fill_rect = pygame.Rect(bar_rect.x, bar_rect.y, max(1, int(bar_rect.width * ratio)), bar_rect.height)
                pygame.draw.rect(self.screen, fill_color, fill_rect, border_radius=s(2))

            # İlerleme metni
            prog_text = obj.get_progress_text()
            prog_surf = prog_font.render(prog_text, True, retro_style.text_muted)
            self.screen.blit(prog_surf, (panel_x + panel_w - prog_surf.get_width() - s(8), y + 1))

            y += line_h + s(8)

    def _draw_level_complete(self) -> None:
        """Level tamamlandı overlay'i — glassmorphism + neon."""
        w, h = self.window_width, self.window_height
        ui = self._ui_scale()
        s = lambda v, minimum=1: max(minimum, int(v * ui))

        # Gradient overlay (koyu lacivert)
        overlay = pygame.Surface((w, h), pygame.SRCALPHA)
        for row in range(h):
            ratio = row / max(1, h)
            alpha = int(200 * 0.8 + 40 * ratio)
            overlay.fill((5, 8, 18, min(255, alpha)), (0, row, w, 1))
        self.screen.blit(overlay, (0, 0))

        # Panel
        pw = min(s(460), w - s(120))
        ph = s(340)
        pr = pygame.Rect((w - pw) // 2, (h - ph) // 2, pw, ph)

        # Glow
        glow_rect = pr.inflate(s(24), s(24))
        glow_surf = pygame.Surface(glow_rect.size, pygame.SRCALPHA)
        pygame.draw.rect(glow_surf, (*retro_style.primary[:3], 25), glow_surf.get_rect(), border_radius=16)
        self.screen.blit(glow_surf, glow_rect.topleft)

        retro_style.draw_glass_panel(self.screen, pr, alpha=200,
                                      border_color=(*retro_style.primary[:3], 160))
        cx = pr.centerx

        # Başlık bandı
        header_h = s(56)
        header_rect = pygame.Rect(pr.x + 2, pr.y + 2, pr.width - 4, header_h)
        header_surf = pygame.Surface(header_rect.size, pygame.SRCALPHA)
        header_surf.fill((12, 18, 40, 230))
        self.screen.blit(header_surf, header_rect.topleft)
        # Alt çizgi
        pygame.draw.line(self.screen, (*retro_style.primary[:3], 140),
                         (header_rect.x, header_rect.bottom),
                         (header_rect.right, header_rect.bottom))

        # Başlık metin + glow
        title = t('coop_level_complete', default='LEVEL TAMAMLANDI!')
        title_font = retro_style.get_font(s(36, minimum=20), bold=True)
        for offset in (2, 1):
            glow = title_font.render(title, True, retro_style.primary)
            glow.set_alpha(22)
            for dx, dy in ((offset, 0), (-offset, 0), (0, offset), (0, -offset)):
                self.screen.blit(glow, glow.get_rect(centerx=cx + dx, centery=header_rect.centery + dy))
        title_surf = title_font.render(title, True, retro_style.primary)
        self.screen.blit(title_surf, title_surf.get_rect(centerx=cx, centery=header_rect.centery))

        y_cursor = header_rect.bottom + s(16)

        # Yıldızlar (polygon çizimi)
        star_size = s(40, minimum=24)
        star_gap = s(10, minimum=6)
        total_star_w = 3 * star_size + 2 * star_gap
        star_x = cx - total_star_w // 2
        import math
        for si in range(3):
            color = UIColors.NEON_GOLD if si < self.earned_stars else (60, 70, 90)
            self._draw_star(self.screen,
                            star_x + si * (star_size + star_gap),
                            y_cursor, star_size, color)
        y_cursor += star_size + s(16)

        # İstatistik kartı
        stat_h = s(70)
        stat_rect = pygame.Rect(pr.x + s(16), y_cursor, pr.width - s(32), stat_h)
        stat_surf = pygame.Surface(stat_rect.size, pygame.SRCALPHA)
        stat_surf.fill((8, 12, 28, 220))
        self.screen.blit(stat_surf, stat_rect.topleft)
        pygame.draw.rect(self.screen, (*retro_style.primary[:3], 80), stat_rect, 1, border_radius=8)

        label_font = retro_style.get_font(s(14, minimum=10))
        value_font = retro_style.get_font(s(22, minimum=14), bold=True)

        stats = [
            (t('coop_team_score', default='Score'), f"{self.team_score:,}".replace(',', '.')),
            (t('coop_total_lines', default='Lines'), str(self.total_lines_cleared)),
            (t('coop_total_time', default='Time'), self._format_time(self.elapsed_time)),
        ]
        col_w = stat_rect.width // len(stats)
        for i, (label, val) in enumerate(stats):
            col_cx = stat_rect.x + col_w * i + col_w // 2
            lbl_surf = label_font.render(label, True, retro_style.text_muted)
            self.screen.blit(lbl_surf, lbl_surf.get_rect(centerx=col_cx, top=stat_rect.y + s(8)))
            val_surf = value_font.render(val, True, retro_style.text_primary)
            self.screen.blit(val_surf, val_surf.get_rect(centerx=col_cx, top=stat_rect.y + s(28)))

        y_cursor += stat_h + s(16)

        # Katkı barı
        contrib_txt = f"P1 %{self.p1_contribution_pct}  —  P2 %{self.p2_contribution_pct}"
        contrib_font = retro_style.get_font(s(14, minimum=10))
        contrib_surf = contrib_font.render(contrib_txt, True, (0, 255, 150))
        self.screen.blit(contrib_surf, contrib_surf.get_rect(centerx=cx, top=y_cursor))

        # Alt ipucu
        hint = t('coop_press_continue', default='Press any key to continue')
        hint_font = retro_style.get_font(s(15, minimum=10))
        hint_surf = hint_font.render(hint, True, retro_style.text_muted)
        self.screen.blit(hint_surf, hint_surf.get_rect(centerx=cx, bottom=pr.bottom - s(12)))

    def _draw_level_failed(self) -> None:
        """Level başarısız overlay'i — kırmızı neon tema."""
        w, h = self.window_width, self.window_height
        ui = self._ui_scale()
        s = lambda v, minimum=1: max(minimum, int(v * ui))

        fail_red = UIColors.NEON_RED  # (255, 50, 80)

        # Gradient overlay (kırmızımsı tint)
        overlay = pygame.Surface((w, h), pygame.SRCALPHA)
        for row in range(h):
            ratio = row / max(1, h)
            alpha = int(200 * 0.75 + 35 * ratio)
            overlay.fill((20, 5, 8, min(255, alpha)), (0, row, w, 1))
        self.screen.blit(overlay, (0, 0))

        # Panel
        pw = min(s(440), w - s(100))
        obj_count = len(self.objectives)
        ph = s(180) + obj_count * s(28)
        pr = pygame.Rect((w - pw) // 2, (h - ph) // 2, pw, ph)

        # Glow
        glow_rect = pr.inflate(s(20), s(20))
        glow_surf = pygame.Surface(glow_rect.size, pygame.SRCALPHA)
        pygame.draw.rect(glow_surf, (160, 25, 40, 20), glow_surf.get_rect(), border_radius=16)
        self.screen.blit(glow_surf, glow_rect.topleft)

        retro_style.draw_glass_panel(self.screen, pr, alpha=210,
                                      border_color=(*fail_red[:3], 160))

        cx = pr.centerx
        y_cursor = pr.y + s(18)

        # Başlık + glow
        title = t('coop_game_over', default='OYUN BİTTİ')
        title_font = retro_style.get_font(s(40, minimum=24), bold=True)
        for offset in (2, 1):
            glow = title_font.render(title, True, fail_red)
            glow.set_alpha(25)
            for dx, dy in ((offset, 0), (-offset, 0), (0, offset), (0, -offset)):
                self.screen.blit(glow, glow.get_rect(centerx=cx + dx, top=y_cursor + dy))
        title_surf = title_font.render(title, True, fail_red)
        self.screen.blit(title_surf, title_surf.get_rect(centerx=cx, top=y_cursor))
        y_cursor += title_surf.get_height() + s(16)

        # Görev ilerleme
        lang = 'tr'
        try:
            from localization import get_language
            lang = get_language()
        except Exception:
            pass

        obj_font = retro_style.get_font(s(16, minimum=11))
        for obj in self.objectives:
            completed = obj.completed
            icon = '✓' if completed else '✗'
            color = (40, 255, 155) if completed else (255, 100, 120)
            text = f"{icon} {obj.get_description(lang)}  [{obj.get_progress_text()}]"
            surf = obj_font.render(text, True, color)
            self.screen.blit(surf, surf.get_rect(centerx=cx, top=y_cursor))
            y_cursor += s(28)

        # Alt buton ipuçları
        hint_font = retro_style.get_font(s(16, minimum=11))
        hint_r = t('coop_press_r_retry', default='R: Retry')
        hint_esc = t('coop_press_esc_menu', default='ESC: Menu')
        hint = f"{hint_r}  |  {hint_esc}"
        hint_surf = hint_font.render(hint, True, retro_style.text_muted)
        self.screen.blit(hint_surf, hint_surf.get_rect(centerx=cx, bottom=pr.bottom - s(14)))

    @staticmethod
    def _draw_star(surface, x, y, size, color):
        """Premium 5 köşeli yıldız çiz."""
        import math
        cx = x + size * 0.5
        cy = y + size * 0.5
        r_outer = size * 0.5
        r_inner = size * 0.25
        points = []
        for i in range(10):
            angle = i * math.pi / 5 - math.pi / 2
            r = r_outer if i % 2 == 0 else r_inner
            points.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
        if len(points) >= 3:
            # Boş arka plan
            empty_color = (60, 70, 90)
            pygame.draw.polygon(surface, empty_color, points)
            edge = tuple(min(255, c + 35) for c in empty_color)
            pygame.draw.polygon(surface, edge, points, 1)
            # Dolu yıldız
            if color != empty_color:
                pygame.draw.polygon(surface, color, points)
                # Glow kenar
                glow_col = tuple(min(255, c + 40) for c in color[:3])
                pygame.draw.polygon(surface, (*glow_col, 55), points, 3)
                pygame.draw.polygon(surface, (*glow_col, 180), points, 1)

    @staticmethod
    def _format_time(ms: float) -> str:
        secs = int(ms / 1000)
        m, s = divmod(secs, 60)
        return f"{m:02d}:{s:02d}"
