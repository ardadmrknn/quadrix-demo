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
from typing import Dict, Any, Optional, List, Tuple
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
    from game_over_surfaces import get_solid_alpha_surface
    from ui_text_layout import wrap_text_limited, ellipsize_text
    from text_cache import measure_text_width
except ImportError:
    from src.localization import t
    from src.retro_style import retro_style
    from src.ui_theme import UIFonts, UIColors
    from src.game_over_surfaces import get_solid_alpha_surface
    from src.ui_text_layout import wrap_text_limited, ellipsize_text
    from src.text_cache import measure_text_width

from .coop_level_data import get_coop_level, CoopLevelConfig, TOTAL_COOP_LEVELS
from .coop_objectives import create_coop_objective


def _fit_or_ellipsize(text: str, color, max_width: int, base_size: int,
                      bold: bool = True, min_size: int = 10) -> pygame.Surface:
    """render_fit_text + son çare ellipsis (P1-6 taşma sırası: shrink → '...').

    render_fit_text fontu yalnız min_size'e kadar küçültür; tabanda bile
    sığmayan metin yüzeyi bütçeyi aşabilir. Bu yardımcı o durumda
    ellipsize_text ile ASCII '...' kısaltması uygular (emoji/sembol yasağı —
    CLAUDE.md). Her iki adım da retro_style LRU önbelleklerinden geçer.
    """
    surf = retro_style.render_fit_text(
        str(text), color, max_width, base_size, bold=bold, min_size=min_size)
    if surf.get_width() > max_width:
        font = retro_style.get_fitting_font(
            str(text), base_size, max_width, bold=bold, min_size=min_size)
        short = ellipsize_text(str(text), font, max_width)
        surf = retro_style.render_fit_text(
            short, color, max_width, base_size, bold=bold, min_size=min_size)
    return surf


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

        # P1-6/P0-2 (ölçekleme denetim raporu): ölçüm/assert rect kayıtları ve
        # sonuç ekranı yüzey önbelleği (FAZ A6 — kare-başı tahsis yasağı).
        self._coop_objectives_rects: Optional[Dict[str, Any]] = None
        self._level_complete_rects: Optional[Dict[str, Any]] = None
        self._level_failed_rects: Optional[Dict[str, Any]] = None
        self._coop_result_geometry_cache: Optional[Tuple] = None
        self._coop_result_surface_cache: Dict[Tuple, pygame.Surface] = {}

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

    def wants_mouse_visible(self) -> bool:
        """Kampanya tamamlandı/başarısız ekranlarında gamepad 'menu' bağlamına
        dönmeli (A=onay/B=menü reklam edilen davranış) — main.py state→context
        çözümü bu metoda bakar. CoopGame temel sınıfı yalnız paused/game_over'da
        True döner; level_complete'te game_over SET EDİLMEZ → bağlam 'game'
        kalır, B=rotate üretir, ekranda 'B ile dön' reklamı ölü kalırdı
        (v2 paritesi).
        """
        if getattr(self, 'level_failed', False) or getattr(self, 'level_complete', False):
            return True
        return super().wants_mouse_visible()

    def update(self, delta_time: float) -> None:
        super().update(delta_time)

        # Game over → level failed
        if self.game_over and not self.level_failed and not self.level_complete:
            self._handle_level_failed(t('coop_game_over', default='Game Over'))

    def handle_input(self):
        """Level tamamlandıysa özel input akışı."""
        if self.level_complete or self.level_failed:
            # === Gamepad poll-only aksiyonları (v2 paritesi) ===
            # Bu ekranlarda wants_mouse_visible=True → main.py 'menu' bağlamını
            # seçer. Yani A (menu_confirm) sentetik K_RETURN, B (menu_back)
            # sentetik K_ESCAPE üretir; bunlar aşağıdaki klavye döngüsünde
            # işlenir. restart (Y) ve level_select (X) POLL-ONLY'dir — yalnızca
            # burada edge-detection ile okunur. (Denetim bulgusu: blok demo
            # koop'a port edilmemişti — Y, menü bağlamında 'menüye dön' olarak
            # yorumlanıyordu, retry hiç çalışmıyordu.)
            try:
                from gamepad_manager import get_gamepad_manager
                _gpm = get_gamepad_manager()
                if _gpm and getattr(_gpm, 'enabled', False):
                    # X → Bölüm Seç (v2 koop paritesi: menüye dönüş).
                    if _gpm.was_action_just_pressed('level_select'):
                        pygame.event.clear((pygame.KEYDOWN, pygame.KEYUP))
                        return 'menu'
                    # Y → Yeniden Dene (level_complete'te sonraki A'dadır).
                    if _gpm.was_action_just_pressed('restart'):
                        pygame.event.clear((pygame.KEYDOWN, pygame.KEYUP))
                        self._restart_level()
                        return True
            except Exception:
                pass
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return False
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        return 'menu'
                    if event.key == pygame.K_r:
                        self._restart_level()
                        return True
                    # A / ENTER → ileri aksiyon: failed'da yeniden dene (menüye
                    # DÜŞMESİN), complete'te sonraki level. "Herhangi tuş → menü"
                    # fallback'inden ÖNCE gelir (v2 paritesi; R2 inceleme
                    # bulgusu: demo portu bu dalı kaçırıyordu — A ile retry
                    # menüye düşüyordu).
                    if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        if self.level_failed:
                            self._restart_level()
                            return True
                        return 'next_level'
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

    # ------------------------------------------------------------------
    # P1-6/P0-2 (ölçekleme denetim raporu) ortak yardımcıları
    # ------------------------------------------------------------------

    def _coop_result_safe_rect(self) -> pygame.Rect:
        """Sonuç modalları için render güvenli alanı (P0-2).

        campaign_ui._get_modal_geometry deseni: geometri kuşak başına bir kez
        çözülür (get_presentation_info dict/Rect tahsisi kare başına
        tekrarlanmaz). Geometri çözülemezse (dummy driver/test) tam ekran
        fallback — clamp o durumda no-op olur. Testler bu önbelleği doğrudan
        yazarak güvenli alan senaryosu (ör. HDR marjları) simüle eder.
        """
        try:
            from platform_utils import get_geometry_generation
            generation = get_geometry_generation()
        except Exception:
            generation = -1
        cache = getattr(self, '_coop_result_geometry_cache', None)
        if cache is not None and cache[0] == generation:
            return cache[1]

        safe_rect = None
        try:
            from platform_utils import get_render_geometry
            geometry = get_render_geometry(self.screen)
            sx0, sy0, sw, sh = geometry.safe_rect
            if sw > 0 and sh > 0:
                safe_rect = pygame.Rect(sx0, sy0, sw, sh)
        except Exception:
            safe_rect = None
        if safe_rect is None:
            safe_rect = pygame.Rect(0, 0, self.window_width, self.window_height)

        self._coop_result_geometry_cache = (generation, safe_rect)
        return safe_rect

    def _coop_result_overlay(self, variant: str) -> pygame.Surface:
        """Gradient overlay'i (w, h, variant) anahtarlı cache'ten üret (FAZ A6).

        Eski kod her karede Surface((w, h)) tahsis edip h satırlık fill
        döngüsü çalıştırıyordu; sonuç ekranı aktifken bu her kare
        tekrarlanıyordu. Renk/alfa değerleri eski çıktıyla birebir aynı.
        """
        size = (int(self.window_width), int(self.window_height))
        cache = self.__dict__.setdefault('_coop_result_surface_cache', {})
        key = ('overlay', variant, size)
        cached = cache.get(key)
        if cached is not None:
            return cached

        w, h = size
        overlay = pygame.Surface((w, h), pygame.SRCALPHA)
        if variant == 'failed':
            base_rgb, base_alpha, span = (20, 5, 8), int(200 * 0.75), 35
        else:
            base_rgb, base_alpha, span = (5, 8, 18), int(200 * 0.8), 40
        for row in range(h):
            ratio = row / max(1, h)
            alpha = int(base_alpha + span * ratio)
            overlay.fill((*base_rgb, min(255, alpha)), (0, row, w, 1))
        self._coop_result_cache_insert(cache, key, overlay)
        return overlay

    def _coop_result_glow(self, variant: str, size: Tuple[int, int]) -> pygame.Surface:
        """Sonuç paneli glow yüzeyini (variant, size) anahtarlı cache'ten üret.

        FAZ A6: kare-başı SRCALPHA Surface tahsisini önbelleğe indirer.
        """
        cache = self.__dict__.setdefault('_coop_result_surface_cache', {})
        key = ('glow', variant, (int(size[0]), int(size[1])))
        cached = cache.get(key)
        if cached is not None:
            return cached

        glow_surf = pygame.Surface((max(1, int(size[0])), max(1, int(size[1]))), pygame.SRCALPHA)
        if variant == 'failed':
            pygame.draw.rect(glow_surf, (160, 25, 40, 20), glow_surf.get_rect(), border_radius=16)
        else:
            pygame.draw.rect(glow_surf, (*retro_style.primary[:3], 25), glow_surf.get_rect(), border_radius=16)
        self._coop_result_cache_insert(cache, key, glow_surf)
        return glow_surf

    @staticmethod
    def _coop_result_cache_insert(cache: Dict[Tuple, pygame.Surface],
                                  key: Tuple, surface: pygame.Surface) -> None:
        """Sonuç yüzey önbelleğine sınırlı giriş (pencere resize taşmasına karşı).

        Tam-ekran overlay'ler (w*h*4 bayt) pencere boyutu değiştikçe yeni
        anahtar üretir; 8 girişin üzerinde en eski (ilk eklenen) tahliye
        edilir — dict ekleme sırası korunur.
        """
        cache[key] = surface
        while len(cache) > 8:
            oldest = next(iter(cache))
            cache.pop(oldest, None)

    def _draw_objectives_hud(self) -> None:
        """Board'un üstünde görev ilerleme paneli (glass panel).

        P1-6 (ölçekleme denetim raporu): açıklamalar artık ölç-önce
        planlanır — sar (wrap_text_limited) → kontrollü ellipsis; satır
        yüksekliği gerçek satır sayısından, panel yüksekliği içerikten
        türetilir ve dikeyde safe rect'e tavanlanır. Kısa metinlerde çıktı
        eski tek-satır düzeniyle aynıdır. Rect'ler test bütçe sözleşmesi
        için _coop_objectives_rects'e kaydedilir.
        """
        ui = self._ui_scale()

        lang = 'tr'
        try:
            from localization import get_language
            lang = get_language()
        except Exception:
            pass

        s = lambda v, minimum=1: max(minimum, int(v * ui))

        # Fontlar önce çözülür — ölçüm (measure_text_width LRU) ve sarma
        # aynı font nesneleri üzerinden yapılır.
        obj_font = retro_style.get_font(s(13, minimum=9))
        prog_font = retro_style.get_font(s(11, minimum=8))
        desc_line_h = obj_font.get_height() + 1
        bar_h = s(5, minimum=3)
        row_gap = s(8)
        header_h = s(26)

        # Panel genişliği board offset'inden (mevcut davranış korunur).
        panel_w = min(s(320), max(s(200), self.board_offset_x - s(20)))
        panel_x = max(s(8), self.board_offset_x - panel_w - s(12))
        panel_y = self.board_offset_y

        bar_x = panel_x + s(26)
        bar_w = max(s(40), panel_w - s(34))

        # Dikey bütçe: satır limiti ladder'ı (3→2→1 satır) — kısa metinler
        # tek satırda kalır, uzun lokalizasyonlar sarma ile yerleşir.
        safe = self._coop_result_safe_rect()
        avail_h = max(header_h + s(20), safe.bottom - s(2) - panel_y)

        for max_lines in (3, 2, 1):
            rows = []
            for obj in self.objectives:
                prog_text = obj.get_progress_text()
                prog_w = measure_text_width(prog_font, prog_text)
                # İlerleme metni ilk satırın sağında: sarma bütçesi ondan artar.
                desc_w = max(s(60), bar_w - prog_w - s(8))
                wrapped = wrap_text_limited(
                    str(obj.get_description(lang)), obj_font, desc_w, max_lines=max_lines)
                row_h = len(wrapped.lines) * desc_line_h + s(2) + bar_h
                rows.append({
                    'obj': obj, 'lines': wrapped.lines, 'prog_text': prog_text,
                    'prog_w': prog_w, 'row_h': row_h,
                })
            panel_h = header_h + s(8) + sum(r['row_h'] for r in rows) \
                + row_gap * max(0, len(rows) - 1) + s(6)
            if panel_h <= avail_h:
                break
        panel_h = min(panel_h, avail_h)

        panel_rect = pygame.Rect(panel_x, panel_y, panel_w, panel_h)
        retro_style.draw_glass_panel(self.screen, panel_rect, alpha=175,
                                      border_color=(*retro_style.primary[:3], 100))

        # Level başlık bandı
        header_rect = pygame.Rect(panel_x + 2, panel_y + 2, panel_w - 4, header_h)
        # FAZ A6: kare-başı HUD bandı tahsisi solid LRU'ya iner.
        header_surf = get_solid_alpha_surface(header_rect.size, (*UIColors.BG_MEDIUM, 190))
        self.screen.blit(header_surf, header_rect.topleft)
        pygame.draw.line(self.screen, (*retro_style.primary[:3], 140),
                         (header_rect.x, header_rect.bottom),
                         (header_rect.right, header_rect.bottom))

        # P1-6: başlık panel iç genişliğine fitted (render_fit_text LRU) +
        # son çare ASCII ellipsis.
        level_name = self.level_config.name.get(lang, self.level_config.name.get('en', ''))
        title_text = f"L{self.current_level_num}: {level_name}"
        title_surf = _fit_or_ellipsize(
            title_text, tuple(retro_style.primary[:3]), max(24, panel_w - s(16)),
            s(14, minimum=10), bold=True, min_size=s(10, minimum=8))
        title_rect = title_surf.get_rect(topleft=(panel_x + s(8), panel_y + s(5)))
        self.screen.blit(title_surf, title_rect.topleft)

        # Görev satırları
        y = panel_y + header_h + s(8)
        row_records = []

        for row in rows:
            completed = row['obj'].completed
            row_top = y
            n_lines = len(row['lines'])
            desc_rects = []

            # İkon dairesi
            icon_r = s(7, minimum=5)
            icon_cx = panel_x + s(14)
            icon_cy = row_top + desc_line_h // 2
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

            # Açıklama — P1-6: sarılmış satırlar (wrap → kontrollü ellipsis).
            desc_color = (40, 255, 155) if completed else retro_style.text_secondary
            for li, line in enumerate(row['lines']):
                line_surf = obj_font.render(line, True, desc_color)
                line_rect = line_surf.get_rect(topleft=(bar_x, row_top + li * desc_line_h))
                self.screen.blit(line_surf, line_rect.topleft)
                desc_rects.append(line_rect)

            # İlerleme barı
            bar_y = row_top + n_lines * desc_line_h + s(2)
            bar_rect = pygame.Rect(bar_x, bar_y, bar_w, bar_h)
            pygame.draw.rect(self.screen, (30, 35, 55), bar_rect, border_radius=s(2))
            ratio = min(1.0, row['obj'].get_progress_ratio()) if hasattr(row['obj'], 'get_progress_ratio') else (1.0 if completed else 0.0)
            if ratio > 0:
                fill_color = (0, 255, 150) if completed else UIColors.NEON_CYAN
                fill_rect = pygame.Rect(bar_rect.x, bar_rect.y, max(1, int(bar_rect.width * ratio)), bar_rect.height)
                pygame.draw.rect(self.screen, fill_color, fill_rect, border_radius=s(2))

            # İlerleme metni (ilk satırın sağında — sarma bütçesi bunu hesaba kattı)
            prog_surf = prog_font.render(row['prog_text'], True, retro_style.text_muted)
            prog_rect = prog_surf.get_rect(right=panel_x + panel_w - s(8), top=row_top + 1)
            self.screen.blit(prog_surf, prog_rect.topleft)

            row_records.append({
                'row_rect': pygame.Rect(panel_x + s(12), row_top, panel_w - s(24), row['row_h']),
                'desc_rects': desc_rects,
                'bar_rect': bar_rect,
                'prog_rect': prog_rect,
            })

            y += row['row_h'] + row_gap

        self._coop_objectives_rects = {
            'panel': panel_rect,
            'header': header_rect,
            'title': title_rect,
            'rows': row_records,
        }

    def _draw_level_complete(self) -> None:
        """Level tamamlandı overlay'i — glassmorphism + neon.

        P0-2 (ölçekleme denetim raporu): panel önce safe rect boyutlarına
        tavanlanır (Rect.clamp küçültmez), sonra safe rect'İN içine
        clamp'lenir; türev rect'ler clamp SONRASI panel_rect'ten üretilir.
        Başlık render_fit_text (LRU) + tek-surface set_alpha glow modülasyonu
        (kare-başı ikinci font.render kalkar — FAZ A6). Stat kolonları
        ölçülü sığar; katkı/ipucu sarma-fit ile panel içinde kalır. Rect'ler
        _level_complete_rects'e kaydedilir (test bütçe sözleşmesi).
        """
        w, h = self.window_width, self.window_height
        ui = self._ui_scale()
        s = lambda v, minimum=1: max(minimum, int(v * ui))

        # Gradient overlay (koyu lacivert) — FAZ A6: (w,h,variant) cache.
        self.screen.blit(self._coop_result_overlay('complete'), (0, 0))

        # P0-2: güvenli alan + panel boyut tavanı (clamp küçültmediği için
        # tavan clamp'ten ÖNCE uygulanır).
        safe = self._coop_result_safe_rect()
        pw = min(s(460), w - s(120), safe.width)
        inner_w = max(24, pw - s(32))

        # Metinler önce ölçülür (measure-first) — dikey bütçe bunlara bağlı.
        title = t('coop_level_complete', default='LEVEL TAMAMLANDI!')
        title_color = tuple(retro_style.primary[:3])
        title_surf = _fit_or_ellipsize(
            title, title_color, max(24, inner_w - s(16)),
            s(36, minimum=20), bold=True, min_size=s(20, minimum=12))

        contrib_txt = f"P1 %{self.p1_contribution_pct}  —  P2 %{self.p2_contribution_pct}"
        contrib_font = retro_style.get_font(s(14, minimum=10))
        contrib_h = contrib_font.get_height() + s(4)

        hint = t('coop_press_continue', default='Press any key to continue')
        hint_font = retro_style.get_font(s(15, minimum=10))
        hint_wrapped = wrap_text_limited(hint, hint_font, max(24, inner_w - s(8)), max_lines=2)
        hint_line_h = hint_font.get_height() + 2
        hint_h = len(hint_wrapped.lines) * hint_line_h

        # P0-2: dikey bütçe — kuantalı küçültme ladder'ı (FAZ A6 deseni);
        # tabanlar okunabilirliği korur. Hiçbir basamak sığmazsa son basamak
        # + aşağıdaki sıkıştırma + safe-height tavanı geçerli kalır.
        for shrink in (1.0, 0.88, 0.76, 0.64, 0.52):
            header_h = max(s(36), int(56 * ui * shrink))
            star_size = max(s(24), int(40 * ui * shrink))
            star_gap = max(s(6), int(10 * ui * shrink))
            stat_h = max(s(48), int(70 * ui * shrink))
            gap = max(s(6), int(16 * ui * shrink))
            ph = (s(2) + header_h + gap + star_size + gap + stat_h + gap
                  + contrib_h + gap + hint_h + s(12))
            if ph <= safe.height:
                break

        # Başlık bandı fitted başlıktan alçak olmasın (dikey merkez hizası
        # taşmasın) — toplam yeniden toplanır.
        header_h = max(header_h, title_surf.get_height() + s(10))
        # Son çare sıkıştırma: toplam safe height'ı aşarsa hint tek satıra
        # iner (wrap max_lines=1); katkı satırı çizim aşamasında düşürülür.
        total_h = (s(2) + header_h + gap + star_size + gap + stat_h + gap
                   + contrib_h + gap + hint_h + s(12))
        if total_h > safe.height and len(hint_wrapped.lines) > 1:
            hint_wrapped = wrap_text_limited(hint, hint_font, max(24, inner_w - s(8)), max_lines=1)
            hint_h = len(hint_wrapped.lines) * hint_line_h
            total_h = (s(2) + header_h + gap + star_size + gap + stat_h + gap
                       + contrib_h + gap + hint_h + s(12))
        ph = min(max(total_h, s(200)), safe.height)

        pr = pygame.Rect((w - pw) // 2, (h - ph) // 2, pw, ph)
        # P0-2: clamp YÖNÜ — panel safe rect'İN içine gider.
        pr = pr.clamp(safe)
        pw, ph = pr.width, pr.height

        # Glow — FAZ A6: (variant, size) cache.
        glow_rect = pr.inflate(s(24), s(24))
        self.screen.blit(self._coop_result_glow('complete', glow_rect.size), glow_rect.topleft)

        retro_style.draw_glass_panel(self.screen, pr, alpha=200,
                                      border_color=(*retro_style.primary[:3], 160))
        cx = pr.centerx

        # Başlık bandı — FAZ A6: solid LRU (kare-başı tahsis yok).
        header_rect = pygame.Rect(pr.x + 2, pr.y + 2, pr.width - 4, header_h)
        header_surf = get_solid_alpha_surface(header_rect.size, (12, 18, 40, 230))
        self.screen.blit(header_surf, header_rect.topleft)
        # Alt çizgi
        pygame.draw.line(self.screen, (*retro_style.primary[:3], 140),
                         (header_rect.x, header_rect.bottom),
                         (header_rect.right, header_rect.bottom))

        # Başlık metin + glow — tek surface, set_alpha modülasyonlu blit ve
        # tam alfa restore (campaign_ui P1-3 deseni).
        title_rect = title_surf.get_rect(centerx=cx, centery=header_rect.centery)
        for dx, dy, a in [(-s(2, minimum=0), 0, 26), (s(2, minimum=0), 0, 26),
                          (0, -s(2, minimum=0), 22), (0, s(2, minimum=0), 22)]:
            title_surf.set_alpha(a)
            self.screen.blit(title_surf, (title_rect.x + dx, title_rect.y + dy))
        title_surf.set_alpha(255)
        self.screen.blit(title_surf, title_rect.topleft)

        y_cursor = header_rect.bottom + gap

        # Yıldızlar (polygon çizimi)
        total_star_w = 3 * star_size + 2 * star_gap
        star_x = cx - total_star_w // 2
        for si in range(3):
            color = UIColors.NEON_GOLD if si < self.earned_stars else (60, 70, 90)
            self._draw_star(self.screen,
                            star_x + si * (star_size + star_gap),
                            y_cursor, star_size, color)
        y_cursor += star_size + gap

        # İstatistik kartı — FAZ A6: solid LRU.
        stat_rect = pygame.Rect(pr.x + s(16), y_cursor, pr.width - s(32), stat_h)
        stat_surf = get_solid_alpha_surface(stat_rect.size, (8, 12, 28, 220))
        self.screen.blit(stat_surf, stat_rect.topleft)
        pygame.draw.rect(self.screen, (*retro_style.primary[:3], 80), stat_rect, 1, border_radius=8)

        stats = [
            (t('coop_team_score', default='Score'), f"{self.team_score:,}".replace(',', '.')),
            (t('coop_total_lines', default='Lines'), str(self.total_lines_cleared)),
            (t('coop_total_time', default='Time'), self._format_time(self.elapsed_time)),
        ]
        # P1-6: kolonlar ölç-önce — etiket/değer fitted, son çare ellipsis;
        # dikeyde değer font tabanı stat_h'nin kalan bütçesine tavanlanır
        # (kolonlar arası yatay/dikey çakışma matematiksel olarak imkânsız).
        label_color = tuple(retro_style.text_muted[:3])
        value_color = tuple(retro_style.text_primary[:3])
        col_w = stat_rect.width // max(1, len(stats))
        col_records = []
        for i, (label, val) in enumerate(stats):
            col_cx = stat_rect.x + col_w * i + col_w // 2
            col_max_w = max(24, col_w - s(8))
            lbl_surf = _fit_or_ellipsize(
                label, label_color, col_max_w, s(14, minimum=10),
                bold=False, min_size=s(10, minimum=8))
            lbl_rect = lbl_surf.get_rect(centerx=col_cx, top=stat_rect.y + s(6))
            self.screen.blit(lbl_surf, lbl_rect.topleft)
            # Değer font tabanı: stat_h'nin kalan DİKEY bütçesi — font
            # YÜKSEKLİĞİ (size değil) bütçeye inene kadar 2'şer küçülür
            # (kuantalı adım = font_cache dostu).
            value_budget = stat_h - s(6) - lbl_surf.get_height() - s(2) - s(4)
            value_base = min(s(22, minimum=12), max(9, value_budget))
            while value_base > 9 and \
                    retro_style.get_font(value_base, bold=True).get_height() > value_budget:
                value_base -= 2
            val_surf = _fit_or_ellipsize(
                val, value_color, col_max_w, value_base,
                bold=True, min_size=s(12, minimum=9))
            val_rect = val_surf.get_rect(
                centerx=col_cx, top=lbl_rect.bottom + s(2))
            self.screen.blit(val_surf, val_rect.topleft)
            col_records.append({
                'col_rect': pygame.Rect(stat_rect.x + col_w * i, stat_rect.y, col_w, stat_h),
                'label_rect': lbl_rect,
                'value_rect': val_rect,
            })

        y_cursor += stat_h + gap

        # Katkı satırı — fitted; hint alanıyla çakışırsa düşürülür (en düşük
        # öncelikli satır, kademeli küçültmenin son halkası).
        contrib_rect = None
        hint_top = pr.bottom - s(12) - hint_h
        if y_cursor + contrib_h <= hint_top - s(4):
            contrib_surf = _fit_or_ellipsize(
                contrib_txt, (0, 255, 150), max(24, inner_w),
                s(14, minimum=10), bold=False, min_size=s(10, minimum=8))
            contrib_rect = contrib_surf.get_rect(centerx=cx, top=y_cursor)
            self.screen.blit(contrib_surf, contrib_rect.topleft)

        # Alt ipucu — sarılır (maks 2 satır), alta sabitlenip yukarı büyür.
        hint_rects = []
        hint_y = pr.bottom - s(12) - hint_h
        for li, line in enumerate(hint_wrapped.lines):
            line_surf = hint_font.render(line, True, retro_style.text_muted)
            line_rect = line_surf.get_rect(centerx=cx, top=hint_y + li * hint_line_h)
            self.screen.blit(line_surf, line_rect.topleft)
            hint_rects.append(line_rect)

        self._level_complete_rects = {
            'panel': pr,
            'safe': safe,
            'title': title_rect,
            'stats': stat_rect,
            'stat_cols': col_records,
            'contrib': contrib_rect,
            'hint_lines': hint_rects,
        }

    def _draw_level_failed(self) -> None:
        """Level başarısız overlay'i — kırmızı neon tema.

        P0-2 (ölçekleme denetim raporu): panel safe rect tavanı + clamp;
        görev satırları sarılır (wrap → ellipsis) ve panel yüksekliği gerçek
        satır sayısından türetilir. Tamamlandı/başarısız FONT SEMBOLLERİ
        (tik/çarpı karakterleri) kaldırıldı — CLAUDE.md emoji/sembol yasağı:
        işaretler pygame.draw.line ile çizilir
        (_draw_objectives_hud tik idyomu + X için iki çapraz).
        Rect'ler _level_failed_rects'e kaydedilir.
        """
        w, h = self.window_width, self.window_height
        ui = self._ui_scale()
        s = lambda v, minimum=1: max(minimum, int(v * ui))

        fail_red = tuple(UIColors.NEON_RED[:3])  # (255, 50, 80)

        # Gradient overlay (kırmızımsı tint) — FAZ A6: (w,h,variant) cache.
        self.screen.blit(self._coop_result_overlay('failed'), (0, 0))

        # P0-2: güvenli alan + panel boyut tavanı (clamp küçültmez).
        safe = self._coop_result_safe_rect()
        pw = min(s(440), w - s(100), safe.width)
        inner_w = max(24, pw - s(24))

        lang = 'tr'
        try:
            from localization import get_language
            lang = get_language()
        except Exception:
            pass

        obj_font = retro_style.get_font(s(16, minimum=11))
        obj_line_h = obj_font.get_height() + 2
        row_gap = s(8)

        # Başlık (fitted) — yükseklik bütçesi için önce ölçülür.
        title = t('coop_game_over', default='OYUN BİTTİ')
        title_surf = _fit_or_ellipsize(
            title, fail_red, max(24, inner_w - s(8)),
            s(40, minimum=24), bold=True, min_size=s(24, minimum=14))
        title_h = title_surf.get_height()

        # İkon kolonu: tamamlandı/başarısız işaretleri çizgilerle (font glifi değil).
        icon_r = s(8, minimum=5)
        icon_col_w = 2 * icon_r + s(8)
        text_w = max(s(40), inner_w - icon_col_w)

        # Alt ipucu (measure-first): sarılır, alta sabitlenir.
        hint_font = retro_style.get_font(s(16, minimum=11))
        hint_r = t('coop_press_r_retry', default='R: Retry')
        hint_esc = t('coop_press_esc_menu', default='ESC: Menu')
        hint = f"{hint_r}  |  {hint_esc}"
        hint_wrapped = wrap_text_limited(hint, hint_font, max(24, inner_w), max_lines=2)
        hint_line_h = hint_font.get_height() + 2
        hint_h = len(hint_wrapped.lines) * hint_line_h

        # P1-6: satır limiti ladder'ı (3→2→1) — panel yüksekliği gerçek
        # içerikten türetilir; safe height tavanı en son uygulanır.
        for max_lines in (3, 2, 1):
            rows = []
            for obj in self.objectives:
                text = f"{obj.get_description(lang)}  [{obj.get_progress_text()}]"
                wrapped = wrap_text_limited(text, obj_font, text_w, max_lines=max_lines)
                rows.append({'obj': obj, 'lines': wrapped.lines})
            body_h = sum(len(r['lines']) * obj_line_h + row_gap for r in rows)
            if rows:
                body_h -= row_gap
            ph = (s(18) + title_h + s(16) + body_h + s(10) + hint_h + s(14))
            if ph <= safe.height:
                break
        ph = min(max(ph, s(160)), safe.height)

        pr = pygame.Rect((w - pw) // 2, (h - ph) // 2, pw, ph)
        # P0-2: clamp YÖNÜ — panel safe rect'İN içine gider.
        pr = pr.clamp(safe)
        pw, ph = pr.width, pr.height

        # Glow — FAZ A6: (variant, size) cache.
        glow_rect = pr.inflate(s(20), s(20))
        self.screen.blit(self._coop_result_glow('failed', glow_rect.size), glow_rect.topleft)

        retro_style.draw_glass_panel(self.screen, pr, alpha=210,
                                      border_color=(*fail_red, 160))

        cx = pr.centerx
        y_cursor = pr.y + s(18)

        # Başlık + glow — tek surface, set_alpha modülasyonlu blit.
        title_rect = title_surf.get_rect(centerx=cx, top=y_cursor)
        for dx, dy, a in [(-s(2, minimum=0), 0, 26), (s(2, minimum=0), 0, 26),
                          (0, -s(2, minimum=0), 22), (0, s(2, minimum=0), 22)]:
            title_surf.set_alpha(a)
            self.screen.blit(title_surf, (title_rect.x + dx, title_rect.y + dy))
        title_surf.set_alpha(255)
        self.screen.blit(title_surf, title_rect.topleft)
        y_cursor += title_h + s(16)

        # Görev ilerleme — çizgi işaretleri + sarılmış metin.
        hint_top = pr.bottom - s(14) - hint_h
        row_records = []
        for row in rows:
            completed = row['obj'].completed
            color = (40, 255, 155) if completed else (255, 100, 120)
            n_lines = len(row['lines'])
            row_h = n_lines * obj_line_h
            # Kademeli küçültmenin bittiği yerde son çare: kalan satırlar
            # hint alanına binmesin diye çizilmez (kayıt test için sayılır).
            if y_cursor + row_h > hint_top - s(2):
                break

            icon_cx = pr.x + s(12) + icon_col_w // 2
            icon_cy = y_cursor + obj_line_h // 2
            if completed:
                pygame.draw.circle(self.screen, (12, 120, 70), (icon_cx, icon_cy), icon_r)
                pygame.draw.circle(self.screen, (40, 255, 155), (icon_cx, icon_cy), icon_r, 1)
                check_pts = [
                    (icon_cx - icon_r // 2, icon_cy),
                    (icon_cx - 1, icon_cy + icon_r // 2),
                    (icon_cx + icon_r // 2, icon_cy - icon_r // 3),
                ]
                pygame.draw.lines(self.screen, (220, 255, 230), False, check_pts, max(1, icon_r // 3))
            else:
                pygame.draw.circle(self.screen, (40, 10, 18), (icon_cx, icon_cy), icon_r)
                pygame.draw.circle(self.screen, (255, 100, 120), (icon_cx, icon_cy), icon_r, 1)
                # X işareti: iki çapraz çizgi (font sembolü değil).
                d = max(1, icon_r // 2)
                lw = max(1, icon_r // 3)
                pygame.draw.line(self.screen, (255, 100, 120),
                                 (icon_cx - d, icon_cy - d), (icon_cx + d, icon_cy + d), lw)
                pygame.draw.line(self.screen, (255, 100, 120),
                                 (icon_cx - d, icon_cy + d), (icon_cx + d, icon_cy - d), lw)

            line_rects = []
            text_x = pr.x + s(12) + icon_col_w
            for li, line in enumerate(row['lines']):
                line_surf = obj_font.render(line, True, color)
                line_rect = line_surf.get_rect(topleft=(text_x, y_cursor + li * obj_line_h))
                self.screen.blit(line_surf, line_rect.topleft)
                line_rects.append(line_rect)

            row_records.append({
                'row_rect': pygame.Rect(pr.x + s(8), y_cursor, pw - s(16), row_h),
                'icon_rect': pygame.Rect(icon_cx - icon_r, icon_cy - icon_r, 2 * icon_r, 2 * icon_r),
                'lines': line_rects,
                'completed': completed,
            })
            y_cursor += row_h + row_gap

        # Alt ipucu — sarılır, alta sabitlenip yukarı büyür.
        hint_rects = []
        hint_y = pr.bottom - s(14) - hint_h
        for li, line in enumerate(hint_wrapped.lines):
            line_surf = hint_font.render(line, True, retro_style.text_muted)
            line_rect = line_surf.get_rect(centerx=cx, top=hint_y + li * hint_line_h)
            self.screen.blit(line_surf, line_rect.topleft)
            hint_rects.append(line_rect)

        self._level_failed_rects = {
            'panel': pr,
            'safe': safe,
            'title': title_rect,
            'rows': row_records,
            'rows_dropped': max(0, len(rows) - len(row_records)),
            'hint_lines': hint_rects,
        }

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
