"""Özel oyun modları - Sprint, Ultra, Zen"""
import pygame
import threading

try:
    from .game import Game  # type: ignore
    from .constants import *  # type: ignore
    from .mode_skins import get_mode_skin  # type: ignore
    from .localization import t  # type: ignore
    from .retro_style import retro_style  # type: ignore
except Exception:
    from game import Game
    from constants import *
    from mode_skins import get_mode_skin
    from localization import t
    from retro_style import retro_style


def debug_print(*args, **kwargs):
    """Debug modu açıksa print yap"""
    if DEBUG_MODE:
        print(*args, **kwargs)


class SprintMode(Game):
    """Sprint Mode - 40 satır en hızlı temizleme"""
    
    def get_initial_speed(self):
        """Sprint modda sabit hız"""
        return 900
    
    def get_current_speed(self):
        """Sprint modda hızlanma yok - sabit hız"""
        return 900
    
    def __init__(self, difficulty='Normal', sound_enabled=True, effects_enabled=True, achievement_manager=None, theme_manager=None, screen=None, fullscreen=False, settings_manager=None, user_manager=None, game_mode='sprint', score_manager=None, sound_manager=None):
        """Sprint modunu başlat"""
        super().__init__(
            difficulty,
            sound_enabled,
            effects_enabled,
            achievement_manager,
            theme_manager,
            screen,
            fullscreen,
            settings_manager,
            user_manager,
            game_mode,
            sound_manager=sound_manager,
            score_manager=score_manager,
        )
        self.mode_name = "SPRINT MODE"
        self.target_lines = 40  # Hedef satır sayısı
        self.start_time = pygame.time.get_ticks()
        self.finish_time = None
        self.is_finished = False
        self._total_paused_ms = 0        # Toplam duraklatma süresi (ms)
        self._pause_start_tick = None    # Pause başlangıç anı
        
        # Font cache (her frame yeniden oluşturulmayacak)
        self.sprint_font_large = retro_style.get_font(48, bold=False)
        self.sprint_font_medium = retro_style.get_font(36, bold=False)
        self.sprint_font_small = retro_style.get_font(28, bold=False)
        self.sprint_font_timer = retro_style.get_font(56, bold=False)  # Büyük kronometre fontu
        self.controls_under_stats = True
        self._sprint_counter_base_size = (int(self.window_width), int(self.window_height))
        
        # En iyi süreler (settings'den yükle)
        self.best_times = self._load_best_times()
        
        # NOT: Müzik Game.__init__ içinde ayarlardan seçilen müzikle çalacak

    def _counter_scale_from_base(self, min_scale: float = 0.62, max_scale: float = 1.12) -> float:
        """Sayaç paneli ölçeği: aktif canvas bazlı ortak UI scale wrapper'ı."""
        return self._ui_scale(min_scale=min_scale, max_scale=max_scale)

    def _get_left_gameplay_reserve_width(self) -> int:
        ui_scale = self._ui_scale(min_scale=0.70, max_scale=1.16)
        return self._sx(240, ui_scale) + self._sx(20, ui_scale, minimum=0)
    
    def _load_best_times(self):
        """Settings'den en iyi süreleri yükle"""
        if self.settings_manager:
            times = self.settings_manager.get('sprint_best_times', [])
            if isinstance(times, list):
                return sorted([float(t) for t in times if isinstance(t, (int, float))])[:3]
        return []
    
    def _save_best_time(self, elapsed_seconds):
        """Yeni süreyi kaydet (en iyi 3 tutulur)"""
        if not self.settings_manager:
            return
        times = list(self.best_times)
        times.append(float(elapsed_seconds))
        times = sorted(times)[:3]  # En iyi 3'ü tut
        self.best_times = times
        self.settings_manager.set('sprint_best_times', times)
        self.settings_manager.save()
    
    def update(self, dt):
        """Sprint modunu güncelle"""
        # Pause durumu değişikliğini izle (timer'ı durdurmak/başlatmak için)
        if self.paused and self._pause_start_tick is None:
            self._pause_start_tick = pygame.time.get_ticks()
        elif not self.paused and self._pause_start_tick is not None:
            self._total_paused_ms += pygame.time.get_ticks() - self._pause_start_tick
            self._pause_start_tick = None

        if not self.is_finished:
            super().update(dt)
            
            # Hedef satıra ulaşıldı mı kontrol et
            if self.board.lines_cleared >= self.target_lines and not self.is_finished:
                self.is_finished = True
                self.finish_time = pygame.time.get_ticks()
                self.game_over = True
                elapsed = max(0, self._effective_elapsed_ms()) / 1000
                
                # En iyi süreyi kaydet
                self._save_best_time(elapsed)
                
                self.finalize_run(playtime=int(elapsed))
                
                # Başarılı bitiş sesi
                if self.sound_enabled and self.sound:
                    self.sound.play('level_up')
    
    def _effective_elapsed_ms(self):
        """Pause süresini düşerek net geçen süreyi (ms) döndür."""
        if self.is_finished:
            return self.finish_time - self.start_time - self._total_paused_ms
        paused_now = 0
        if self._pause_start_tick is not None:
            paused_now = pygame.time.get_ticks() - self._pause_start_tick
        return pygame.time.get_ticks() - self.start_time - self._total_paused_ms - paused_now

    def _format_elapsed(self):
        elapsed = max(0, self._effective_elapsed_ms()) / 1000
        minutes = int(elapsed // 60)
        seconds = int(elapsed % 60)
        centiseconds = int((elapsed % 1) * 100)
        return elapsed, minutes, seconds, centiseconds

    def _format_time(self, seconds):
        """Saniyeyi dk:ss.cc formatına çevir"""
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        cents = int((seconds % 1) * 100)
        return f"{minutes}:{secs:02d}.{cents:02d}"

    def draw_mode_info(self, info_x, info_y):
        """Sprint bilgilerini oyun alanının SOL panelinde göster - EN İYİ SÜRELER."""
        board_offset_x, board_offset_y = self.get_board_offset()
        from retro_style import retro_style  # Local import to avoid circular dependency
        ui_scale = self._ui_scale(min_scale=0.70, max_scale=1.16)
        s = lambda v, minimum=1: self._sx(v, ui_scale, minimum)
        
        # Define local colors to avoid NameError if not in constants
        NEON_GOLD = (255, 215, 0)
        NEON_GREEN = (50, 255, 50)

        # === SOL PANEL: EN İYİ SÜRELER (Yeşil Kutu) ===
        # Sağ panel ile simetrik olacak şekilde konumlandır
        panel_width = s(240)
        panel_height = s(200)
        
        # Sol panel offset hesabı:
        # Board'un solu: board_offset_x
        # Panel'in sağı: board_offset_x - 20
        panel_x = board_offset_x - panel_width - s(20)
        
        # Eğer panel ekran dışına taşıyorsa (düşük çözünürlük), biraz içeri al
        if panel_x < s(10):
            panel_x = s(10)
             
        panel_y = board_offset_y
        panel_rect = pygame.Rect(panel_x, panel_y, panel_width, panel_height)
        
        # Retro Glass Panel (Templateden şaşma)
        retro_style.draw_glass_panel(
            self.screen,
            panel_rect,
            alpha=160,
            border_color=(NEON_GREEN if self.is_finished else None), # Bitince yeşil vurgu
            glow=False
        )
        
        # Başlık: EN İYİ SÜRELER
        header_font = retro_style.get_font(s(22, minimum=13), bold=True)
        header_text = header_font.render(t('panel_best_times'), True, NEON_GOLD)
        header_rect = header_text.get_rect(centerx=panel_rect.centerx, top=panel_rect.y + s(15))
        
        # Başlık altı çizgi
        pygame.draw.line(self.screen, (255, 215, 0, 100), 
                         (panel_rect.x + s(20), header_rect.bottom + s(5)),
                         (panel_rect.right - s(20), header_rect.bottom + s(5)), 1)

        self.screen.blit(header_text, header_rect)

        # Liste
        start_y = header_rect.bottom + s(20)
        row_height = s(35)
        
        rank_font = retro_style.get_font(s(24, minimum=13), bold=True)
        time_font = retro_style.get_font(s(24, minimum=13), bold=False)
        
        if self.best_times:
            for idx, time_val in enumerate(self.best_times[:3]):
                rank_colors = [NEON_GOLD, (192, 192, 192), (205, 127, 50)]  # Altın, Gümüş, Bronz
                color = rank_colors[idx] if idx < 3 else (200, 200, 200)
                
                # Sıra no
                rank_surface = rank_font.render(f"{idx + 1}.", True, color)
                # Süre
                time_surface = time_font.render(self._format_time(time_val), True, (240, 240, 255))
                
                y_pos = start_y + idx * row_height
                
                self.screen.blit(rank_surface, (panel_rect.x + s(30), y_pos))
                # Süreyi sağa yasla
                time_rect = time_surface.get_rect(right=panel_rect.right - s(30), top=y_pos)
                self.screen.blit(time_surface, time_rect)
        else:
            no_rec_font = retro_style.get_font(s(18, minimum=11), bold=False)
            no_rec = no_rec_font.render(t('panel_no_records'), True, (150, 150, 150))
            self.screen.blit(no_rec, no_rec.get_rect(center=(panel_rect.centerx, panel_rect.centery + s(10))))

        # 40 Satır Hedefi Bilgisi
        hint_font = retro_style.get_font(s(14, minimum=10), bold=False)
        hint = hint_font.render(t('sprint_target_hint', lines=self.target_lines), True, (100, 200, 255))
        self.screen.blit(hint, hint.get_rect(center=(panel_rect.centerx, panel_rect.bottom - s(20))))

        return 0

    def draw_mode_overlay(self):
        """Sprint modu HUD - Kronometre ve ilerleme."""
        from retro_style import retro_style
        ui_scale = self._counter_scale_from_base()
        s = lambda v, minimum=1: self._sx(v, ui_scale, minimum)
        
        # 1. SOL PANELİ ÇİZ (Explicit call because Game class doesn't call it automatically)
        self.draw_mode_info(0, 0)

        # 2. SAĞ PANEL: KRONOMETRE (Sarı Kutu Yeri)
        # Game.draw metodunda '_hud_mode_info_area' oluşturulmuşsa onu kullan
        target_rect = getattr(self, '_hud_mode_info_area', None)
        
        if target_rect:
            # (x, y, w, h)
            rx, ry, rw, rh = target_rect
            # Çok uzunsa sınırla
            rh = min(rh, s(160))
            timer_rect = pygame.Rect(rx, ry, rw, rh)
        else:
            # Fallback (skor panelinin altı)
            hud_panel = getattr(self, '_hud_panel_rect', None)
            if hud_panel:
                timer_rect = pygame.Rect(hud_panel.x, hud_panel.bottom + s(20), hud_panel.width, s(140))
            else:
                # Total fallback
                offset_x, offset_y = self.get_board_offset()
                timer_rect = pygame.Rect(offset_x + self.board.width*self.get_cell_size() + s(20), offset_y + s(300), s(240), s(140))

        # Glass Panel Çizimi
        retro_style.draw_glass_panel(
            self.screen,
            timer_rect,
            alpha=160,
            border_color=(255, 100, 100), # Kırmızı/Sıcak bir renk
            glow=True
        )

        # Başlık: SÜRE
        header_font = retro_style.get_font(s(20, minimum=12), bold=True)
        header_surf = header_font.render(t('timer_label'), True, (255, 100, 100))
        header_rect = header_surf.get_rect(centerx=timer_rect.centerx, top=timer_rect.y + s(15))
        self.screen.blit(header_surf, header_rect)

        # Süre Değeri (Büyük)
        _, minutes, seconds, centiseconds = self._format_elapsed()
        time_color = (100, 255, 100) if self.is_finished else (255, 255, 255)
        
        timer_font = retro_style.get_mono_font(s(48, minimum=20), bold=True)
        time_str = f'{minutes}:{seconds:02d}.{centiseconds:02d}'
        time_surf = timer_font.render(time_str, True, time_color)
        
        # Titreşmeyi önlemek için: sabit referans genişliği kullan (cache'le)
        if not hasattr(self, '_timer_ref_width'):
            ref_surf = timer_font.render("9:99.99", True, (255, 255, 255))
            self._timer_ref_width = ref_surf.get_width()
        
        # Sabit genişlikli alanın sol kenarını hesapla
        fixed_left = int(timer_rect.centerx - self._timer_ref_width // 2)
        # Mevcut metni bu alanın içinde ortala
        text_offset = (self._timer_ref_width - time_surf.get_width()) // 2
        time_x = fixed_left + text_offset
        time_y = int(timer_rect.centery - time_surf.get_height() // 2 - s(5))
        self.screen.blit(time_surf, (time_x, time_y))
        
        # İlerleme Çubuğu (Progres Bar)
        bar_w = timer_rect.width - s(40)
        bar_h = s(8)
        bar_x = timer_rect.x + s(20)
        bar_y = timer_rect.bottom - s(35)
        
        # Arka plan barı
        pygame.draw.rect(self.screen, (40, 40, 60), (bar_x, bar_y, bar_w, bar_h), border_radius=4)
        
        # Doluluk
        progress = min(1.0, self.board.lines_cleared / self.target_lines)
        if progress > 0:
            fill_w = int(bar_w * progress)
            fill_color = (100, 255, 100) if self.is_finished else (255, 215, 0)
            pygame.draw.rect(self.screen, fill_color, (bar_x, bar_y, fill_w, bar_h), border_radius=4)
            
            # Glow efekti (progres ucu)
            if not self.is_finished:
                 glow_x = bar_x + fill_w
                 pygame.draw.circle(self.screen, (255, 255, 255, 100), (glow_x, bar_y + bar_h//2), s(6))

        # İlerleme Metni
        prog_font = retro_style.get_font(s(14, minimum=10), bold=True)
        prog_text = prog_font.render(f"{self.board.lines_cleared} / {self.target_lines}", True, (180, 180, 180))
        self.screen.blit(prog_text, prog_text.get_rect(centerx=timer_rect.centerx, top=bar_y + s(12)))

    def _draw_game_over_overlay(self, skin, *, alt_theme=None):
        """Sprint bitiş ekranı - ana tema overlay'i ile."""
        if alt_theme is None:
            alt_theme = {
                'title_text': t('sprint_congrats_title'),
                'panel_border_color': (80, 220, 120),
                'panel_glow_color':   (50, 180, 90),
                'panel_fill_tint':    (8, 24, 14),
                'card_fill_tint':     (12, 32, 20),
                'card_border_color':  (60, 160, 100),
                'gradient_tint':      (4, 14, 8),
                'skip_stars': True,
                'state_prefix': 'sprint_',
            }
        super()._draw_game_over_overlay(skin, alt_theme=alt_theme)

    def restart(self):
        """Reset sprint-specific timing/state on restart"""
        super().restart()
        self.start_time = pygame.time.get_ticks()
        self.finish_time = None
        self.is_finished = False
        self._total_paused_ms = 0
        self._pause_start_tick = None
        self._sprint_game_over_active = False
        # En iyi süreleri yeniden yükle
        self.best_times = self._load_best_times()


class UltraMode(Game):
    """Ultra Mode - 2 dakikada en yüksek skor"""
    
    def get_initial_speed(self):
        """Ultra modda sabit hız"""
        return 900
    
    def get_current_speed(self):
        """Ultra modda hızlanma yok - sabit hız"""
        return 900
    
    def __init__(self, difficulty='Normal', sound_enabled=True, effects_enabled=True, achievement_manager=None, theme_manager=None, screen=None, fullscreen=False, settings_manager=None, user_manager=None, game_mode='ultra', score_manager=None, sound_manager=None):
        """Ultra modunu başlat"""
        super().__init__(
            difficulty,
            sound_enabled,
            effects_enabled,
            achievement_manager,
            theme_manager,
            screen,
            fullscreen,
            settings_manager,
            user_manager,
            game_mode,
            sound_manager=sound_manager,
            score_manager=score_manager,
        )
        self.mode_name = "ULTRA MODE"
        self.time_limit = 120  # 2 dakika (saniye)
        self.start_time = pygame.time.get_ticks()
        self.is_finished = False
        
        # Font cache (sadece bitişte kullanılacak)
        self.ultra_font_large = retro_style.get_font(72, bold=False)
        self.ultra_font_medium = retro_style.get_font(56, bold=False)
        self.ultra_panel_font = retro_style.get_font(48, bold=False)
        self.ultra_panel_font_small = retro_style.get_font(36, bold=False)
        self.controls_under_stats = True
        self._ultra_counter_base_size = (int(self.window_width), int(self.window_height))
        
        # NOT: Müzik Game.__init__ içinde ayarlardan seçilen müzikle çalacak

    def _counter_scale_from_base(self, min_scale: float = 0.62, max_scale: float = 1.12) -> float:
        """Sayaç paneli ölçeği: aktif canvas bazlı ortak UI scale wrapper'ı."""
        return self._ui_scale(min_scale=min_scale, max_scale=max_scale)

    def _get_left_gameplay_reserve_width(self) -> int:
        ui_scale = self._ui_scale(min_scale=0.70, max_scale=1.16)
        return self._sx(240, ui_scale) + self._sx(20, ui_scale, minimum=0)
    
    def update(self, dt):
        """Ultra modunu güncelle"""
        if not self.is_finished:
            # Süre kontrolü
            elapsed = (pygame.time.get_ticks() - self.start_time) / 1000
            if elapsed >= self.time_limit:
                self.is_finished = True
                self.finish_time = pygame.time.get_ticks()
                self.game_over = True
                self.finalize_run(playtime=int(elapsed))
                
                # Başarılı bitiş sesi (süre doldu)
                if self.sound_enabled and self.sound:
                    self.sound.play('game_over')
                
                # Skoru kaydet
                self._save_best_score(self.board.score)
            else:
                super().update(dt)

    def _get_time_stats(self):
        elapsed = (pygame.time.get_ticks() - self.start_time) / 1000
        remaining = max(0, self.time_limit - elapsed)
        # Progress: 0 (başlangıç) -> 1 (bitiş)
        progress = min(1.0, elapsed / self.time_limit)
        return elapsed, remaining, progress

    def _save_best_score(self, score):
        """Yeni skoru kaydet (en iyi 3 tutulur)"""
        if not self.settings_manager:
            return
        scores = self.settings_manager.get('ultra_best_scores', [])
        if not isinstance(scores, list):
            scores = []
        scores.append(int(score))
        scores = sorted(scores, reverse=True)[:3]  # En yüksek 3
        self.settings_manager.set('ultra_best_scores', scores)
        self.settings_manager.save()
        self.best_scores = scores

    def draw_mode_info(self, info_x, info_y):
        """Ultra modunun bilgisini oyun alanının SOL panelinde göster - EN YÜKSEK SKORLAR."""
        board_offset_x, board_offset_y = self.get_board_offset()
        from retro_style import retro_style
        ui_scale = self._ui_scale(min_scale=0.70, max_scale=1.16)
        s = lambda v, minimum=1: self._sx(v, ui_scale, minimum)
        
        # Renk tanımları
        NEON_CYAN = (0, 255, 221)
        NEON_PURPLE = (180, 100, 255)
        NEON_GOLD = (255, 215, 0)
        
        # En iyi skorları yükle (eğer yüklenmediyse)
        if not hasattr(self, 'best_scores'):
             sc = self.settings_manager.get('ultra_best_scores', []) if self.settings_manager else []
             self.best_scores = sorted(sc, reverse=True)[:3] if isinstance(sc, list) else []

        # === SOL PANEL: EN İYİ SKORLAR (Ultra Temalı - Mor/Cyan) ===
        panel_width = s(240)
        panel_height = s(200)
        
        panel_x = board_offset_x - panel_width - s(20)
        if panel_x < s(10): panel_x = s(10)
        panel_y = board_offset_y
        
        panel_rect = pygame.Rect(panel_x, panel_y, panel_width, panel_height)
        
        # Retro Glass Panel
        retro_style.draw_glass_panel(
            self.screen,
            panel_rect,
            alpha=160,
            border_color=(NEON_PURPLE if self.is_finished else None),
            glow=False
        )
        
        # Başlık ve Çizgi
        header_font = retro_style.get_font(s(22, minimum=13), bold=True)
        header_text = header_font.render(t('panel_best_scores'), True, NEON_CYAN)
        header_rect = header_text.get_rect(centerx=panel_rect.centerx, top=panel_rect.y + s(15))
        self.screen.blit(header_text, header_rect)
        
        pygame.draw.line(self.screen, (0, 255, 221, 100), 
                         (panel_rect.x + s(20), header_rect.bottom + s(5)),
                         (panel_rect.right - s(20), header_rect.bottom + s(5)), 1)

        # Liste
        start_y = header_rect.bottom + s(20)
        row_height = s(35)
        
        rank_font = retro_style.get_font(s(24, minimum=13), bold=True)
        score_font = retro_style.get_font(s(24, minimum=13), bold=False)
        
        if self.best_scores:
            for idx, score_val in enumerate(self.best_scores[:3]):
                rank_colors = [NEON_GOLD, (192, 192, 192), (205, 127, 50)]
                color = rank_colors[idx] if idx < 3 else (200, 200, 200)
                
                rank_surf = rank_font.render(f"{idx + 1}.", True, color)
                score_surf = score_font.render(f"{score_val:,}".replace(',', '.'), True, (255, 255, 255))
                
                y_pos = start_y + idx * row_height
                self.screen.blit(rank_surf, (panel_rect.x + s(30), y_pos))
                
                s_rect = score_surf.get_rect(right=panel_rect.right - s(30), top=y_pos)
                self.screen.blit(score_surf, s_rect)
        else:
            no_rec_font = retro_style.get_font(s(18, minimum=11), bold=False)
            no_rec = no_rec_font.render(t('panel_no_records'), True, (150, 150, 150))
            self.screen.blit(no_rec, no_rec.get_rect(center=(panel_rect.centerx, panel_rect.centery + s(10))))
        
        # Limit Bilgisi
        hint_font = retro_style.get_font(s(14, minimum=10), bold=False)
        hint = hint_font.render(t('ultra_time_limit_hint'), True, NEON_PURPLE)
        self.screen.blit(hint, hint.get_rect(center=(panel_rect.centerx, panel_rect.bottom - s(20))))

        return 0
    def restart(self):
        """Reset ultra-specific timing/state on restart"""
        super().restart()
        self.start_time = pygame.time.get_ticks()
        self.is_finished = False
        self.finish_time = None
        self._ultra_game_over_active = False

    def draw_mode_overlay(self):
        """Ultra modu HUD - Sağda Geri Sayım Sayacı."""
        from retro_style import retro_style
        ui_scale = self._counter_scale_from_base()
        s = lambda v, minimum=1: self._sx(v, ui_scale, minimum)
        
        # 1. SOL PANEL (Explicit call)
        self.draw_mode_info(0, 0)
        
        # 2. SAĞ PANEL: GERİ SAYIM (Sarı Kutu Yeri)
        target_rect = getattr(self, '_hud_mode_info_area', None)
        if target_rect:
            rx, ry, rw, rh = target_rect
            rh = min(rh, s(160))
            timer_rect = pygame.Rect(rx, ry, rw, rh)
        else:
            hud_panel = getattr(self, '_hud_panel_rect', None)
            if hud_panel:
                timer_rect = pygame.Rect(hud_panel.x, hud_panel.bottom + s(20), hud_panel.width, s(140))
            else:
                 offset_x, offset_y = self.get_board_offset()
                 timer_rect = pygame.Rect(offset_x + self.board.width*self.get_cell_size() + s(20), offset_y + s(300), s(240), s(140))

        # Renkler
        NEON_RED = (255, 50, 80)
        NEON_CYAN = (0, 255, 221)
        NEON_ORANGE = (255, 165, 0)
        
        # Süre Hesapla
        _, remaining, progress = self._get_time_stats()
        is_low_time = remaining <= 30
        
        border_color = NEON_RED if is_low_time else NEON_CYAN
        if self.is_finished: border_color = (150, 150, 150)
        
        # Glass Panel
        retro_style.draw_glass_panel(
            self.screen,
            timer_rect,
            alpha=160,
            border_color=border_color,
            glow=is_low_time
        )
        
        # Başlık ve İkon
        header_font = retro_style.get_font(s(20, minimum=12), bold=True)
        header_color = NEON_RED if is_low_time else NEON_CYAN
        header_text = header_font.render(t('ultra_remaining_label'), True, header_color)
        header_rect = header_text.get_rect(centerx=timer_rect.centerx, top=timer_rect.y + s(15))
        self.screen.blit(header_text, header_rect)
        
        # Kalan Süre (Büyük)
        timer_font = retro_style.get_mono_font(s(48, minimum=20), bold=True)
        minutes = int(remaining // 60)
        seconds = int(remaining % 60)
        time_str = f'{minutes}:{seconds:02d}'
        
        # Yazı rengi son 10 saniye yanıp sönebilir veya kırmızı olabilir
        time_color = (255, 255, 255)
        if remaining <= 10: time_color = NEON_RED
        elif remaining <= 30: time_color = NEON_ORANGE
        
        time_surf = timer_font.render(time_str, True, time_color)
        time_rect = time_surf.get_rect(centerx=timer_rect.centerx, centery=timer_rect.centery - s(5))
        self.screen.blit(time_surf, time_rect)
        
        # Progres Bar (Zaman azaldıkça dolan veya boşalan)
        # Ultra için: Zaman bitiyor, bar DOLUYOR olsun (geçen süre)
        bar_w = timer_rect.width - s(40)
        bar_h = s(8)
        bar_x = timer_rect.x + s(20)
        bar_y = timer_rect.bottom - s(35)
        
        # Arka plan
        pygame.draw.rect(self.screen, (40, 40, 60), (bar_x, bar_y, bar_w, bar_h), border_radius=4)
        
        # Dolu kısım (Zaman geçtikçe artar -> progress 0..1)
        if progress > 0:
            fill_w = int(bar_w * progress)
            fill_color = time_color # Uyumlu renk
            pygame.draw.rect(self.screen, fill_color, (bar_x, bar_y, fill_w, bar_h), border_radius=4)
            
            # Glow
            if not self.is_finished:
                 glow_x = bar_x + fill_w
                 pygame.draw.circle(self.screen, (255, 255, 255, 100), (int(glow_x), int(bar_y + bar_h//2)), s(6))
        
        # Bilgi Yazısı (Skor)
        info_font = retro_style.get_font(s(18, minimum=11), bold=True)
        score_text = info_font.render(f"{t('score')}: {self.board.score}", True, (200, 200, 200))
        self.screen.blit(score_text, score_text.get_rect(centerx=timer_rect.centerx, top=bar_y + s(12)))

    def _draw_game_over_overlay(self, skin, *, alt_theme=None):
        """Ultra bitiş ekranı - ana tema overlay'i ile."""
        if alt_theme is None:
            alt_theme = {
                'title_text': f"{t('pvp_time_up')}!",
                'panel_border_color': (180, 100, 255),
                'panel_glow_color':   (140, 60, 220),
                'panel_fill_tint':    (16, 8, 30),
                'card_fill_tint':     (22, 12, 40),
                'card_border_color':  (120, 70, 180),
                'gradient_tint':      (10, 4, 18),
                'skip_stars': True,
                'state_prefix': 'ultra_',
            }
        super()._draw_game_over_overlay(skin, alt_theme=alt_theme)


class ZenMode(Game):
    """Zen Mode - Süresiz, rahat oyun (game over yok, otomatik temizlik)"""
    
    def __init__(self, difficulty='Kolay', sound_enabled=True, effects_enabled=True, achievement_manager=None, theme_manager=None, screen=None, fullscreen=False, settings_manager=None, user_manager=None, game_mode='zen', score_manager=None, auto_clear_rows=None, sound_manager=None):
        """Zen modunu başlat
        
        Args:
            auto_clear_rows: Otomatik temizlikte silinecek satır sayısı (None = tüm tahta)
        """
        super().__init__(
            difficulty,
            sound_enabled,
            effects_enabled,
            achievement_manager,
            theme_manager,
            screen,
            fullscreen,
            settings_manager,
            user_manager,
            game_mode,
            sound_manager=sound_manager,
            score_manager=score_manager,
        )
        self.mode_name = "ZEN MODE"
        
        # Font cache (her frame yeniden oluşturulmayacak)
        self.zen_font_large = retro_style.get_font(48, bold=False)
        self.zen_font_medium = retro_style.get_font(36, bold=False)
        self.zen_font_small = retro_style.get_font(28, bold=False)
        
        # Zen mode özellikleri
        self.auto_clears = 0  # Otomatik temizlik sayacı
        self.zen_message = ""
        self.zen_message_timer = 0
        self.total_time = 0  # Toplam oynanan süre
        self.relaxation_bonus = 0  # Rahatlatma bonusu
        self.auto_clear_triggered = False
        self.auto_clear_penalty = 0  # Otomatik temizlik cezası (kalıcı)
        self._last_penalty_print = 0  # Debug için
        self._pending_top_out_auto_clear = False
        
        # Otomatik temizlik satır sayısı (kullanıcı seçimi)
        # None = tüm tahta, sayı = o kadar satır temizle
        self.auto_clear_rows = auto_clear_rows
        
        # Zen Mode için daha yavaş hız (her zaman Kolay seviyesinde)
        self.fall_speed = 1000  # 1 saniye (çok yavaş)
        
        # NOT: Müzik Game.__init__ içinde ayarlardan seçilen müzikle çalacak
    
    def lock_and_new_piece(self):
        """Parçayı kilitle - ZEN MODUNDA OYUN ASLA BİTMEZ"""
        # Lock explosion - her hücre için parçacık patlaması
        if self.effects_enabled:
            cell_size = self.get_cell_size()
            offset_x, offset_y = self.get_board_offset()
            piece_cells = self.current_piece.get_cells()
            cm = getattr(self.current_piece, 'color_matrix', None)
            for cell_x, cell_y in piece_cells:
                screen_x = offset_x + cell_x * cell_size + cell_size // 2
                screen_y = offset_y + cell_y * cell_size + cell_size // 2
                cell_color = self.current_piece.color
                if cm is not None:
                    try:
                        lx = cell_x - self.current_piece.x
                        ly = cell_y - self.current_piece.y
                        v = cm[ly][lx]
                        if v is not None:
                            cell_color = v
                    except Exception:
                        pass
                self.create_lock_explosion(x=screen_x, y=screen_y, color=cell_color, cell_size=cell_size)

        # Normal kilitleme işlemi
        lines_cleared = self.board.lock_piece(self.current_piece)

        lock_out_triggered = False
        consume_last_lock_out = getattr(self.board, 'consume_last_lock_out', None)
        if callable(consume_last_lock_out):
            try:
                lock_out_triggered = bool(consume_last_lock_out())
            except Exception:
                lock_out_triggered = False
        if not lock_out_triggered:
            lock_out_triggered = bool(
                getattr(self.board, '_last_lock_out', False)
                or getattr(self.board, '_locked_out', False)
            )
        self._pending_top_out_auto_clear = lock_out_triggered

        # Zen Mode: lock-out flag'ini temizle, oyun asla bitmez
        clear_lock_out = getattr(self.board, 'clear_lock_out', None)
        if callable(clear_lock_out):
            clear_lock_out()

        # Satır temizlenmiyorsa blok kilitlenme sesi çal
        if lines_cleared == 0:
            self.sound.play('lock')
        
        # Satır temizleme animasyonu ve bonuslar
        if lines_cleared > 0:
            self.line_clear_animation = 30
            self.line_clear_flash = True
            
            # Rahatlatma bonusu
            self.relaxation_bonus += lines_cleared * 50
            
            # Temizlenen satırları efekt için kaydet
            cleared_rows = list(self.board.last_cleared_lines) if self.board.last_cleared_lines else []
            self.line_clear_pending_rows = []
            self.line_clear_pending_colors = {}
            if cleared_rows and self.effects_enabled:
                self.line_clear_pending_rows = list(cleared_rows)
                try:
                    pending_colors = {}
                    if hasattr(self.board, 'last_cleared_colors'):
                        for row in cleared_rows:
                            row_colors = self.board.last_cleared_colors.get(row)
                            if row_colors:
                                pending_colors[row] = list(row_colors)
                    self.line_clear_pending_colors = pending_colors
                except Exception:
                    self.line_clear_pending_colors = {}
            
            if self.effects_enabled and cleared_rows:
                cell_size = self.get_cell_size()
                offset_x, offset_y = self.get_board_offset()
                
                # Soldan sağa ışık süpürmesi başlat
                self.line_clear_sweep_rows = cleared_rows
                self.line_clear_sweep_progress = 0.0
                self.line_clear_sweep_active = True
                
                # Parçacık efektleri
                self.create_line_clear_particles(cleared_rows, offset_x, offset_y, cell_size)
                
                # Dalga efekti - her satır için
                for row in cleared_rows:
                    wave_y = offset_y + row * cell_size + cell_size // 2
                    wave_x = offset_x + (self.board_width * cell_size) // 2
                    self.line_clear_wave_effects.append({
                        'x': wave_x,
                        'y': wave_y,
                        'radius': 0,
                        'max_radius': self.board_width * cell_size,
                        'alpha': 200,
                        'color': (255, 255, 255),
                        'speed': 15
                    })
                
                # Blok düşme animasyonu başlat
                self._start_block_fall_animation(cleared_rows)
                
                # Ekran titremesi (1-3 satır için hafif)
                if lines_cleared < 4:
                    self.trigger_screen_shake(intensity=3 + lines_cleared * 2, duration=8 / 60.0)
            
            # Mesaj ve ses
            if lines_cleared == 4:
                self.zen_message = t('zen_message_tetris')
                self.zen_message_timer = 2.0
                self.combo_message = "QUADRIX!"
                self.sound.play('tetris')
                # Gamepad titreşimi - QUADRIX! (güçlü)
                try:
                    from gamepad_manager import get_gamepad_manager
                    get_gamepad_manager().rumble(0.8, 1.0, 400)
                except Exception:
                    pass
                
                # QUADRIX için güçlü ekran titremesi
                self.trigger_screen_shake(intensity=15, duration=20 / 60.0)
                
                # Ekstra parçacıklar
                if self.effects_enabled:
                    active_width, active_height = self._active_ui_size()
                    center_x = active_width // 2
                    center_y = active_height // 2
                    self.create_particles(
                        count=150,
                        x=center_x,
                        y=center_y,
                        colors=[YELLOW, ORANGE, (255, 215, 0), CYAN],
                        speed=10
                    )
                self.combo_message_time = 120
            elif lines_cleared >= 2:
                self.zen_message = t('zen_message_lines', lines=lines_cleared)
                self.zen_message_timer = 1.5
                if lines_cleared == 2:
                    clear_name = "DOUBLE!"
                elif lines_cleared == 3:
                    clear_name = "TRIPLE!"
                else:
                    clear_name = f"{lines_cleared}x CLEAR!"
                combo_count = getattr(self.board, 'combo', 0)
                if combo_count > 1:
                    self.combo_message = f"{clear_name}  x{combo_count} Combo"
                else:
                    self.combo_message = clear_name
                self.sound.play('line')
                # Gamepad titreşimi - çoklu satır (orta)
                try:
                    from gamepad_manager import get_gamepad_manager
                    get_gamepad_manager().rumble(0.4, 0.5, 200)
                except Exception:
                    pass
                # Çoklu satır için renkli parçacıklar
                if self.effects_enabled:
                    active_width, active_height = self._active_ui_size()
                    center_x = active_width // 2
                    center_y = active_height // 2
                    self.create_particles(
                        count=50 * lines_cleared,
                        x=center_x,
                        y=center_y,
                        colors=[CYAN, MAGENTA, GREEN],
                        speed=6
                    )
                self.combo_message_time = 120
            else:
                combo_count = getattr(self.board, 'combo', 0)
                if combo_count > 1:
                    self.combo_message = f"x{combo_count} Combo!"
                    self.combo_message_time = 90
                else:
                    self.combo_message = ""
                    self.combo_message_time = 0
                self.sound.play('line')

            # Başarı kontrolü
            if self.achievement_manager:
                new_achievements = self.achievement_manager.update_stats(
                    score=self.board.score,
                    lines=self.board.lines_cleared,
                    level=self.board.level,
                    tetrises=self.board.tetrises,
                    combo=self.board.combo,
                    game_mode=self.game_mode,
                )
                for ach_id in new_achievements:
                    achievement = self.achievement_manager.get_achievement(ach_id)
                    if achievement:
                        self.achievement_notifications.append({
                            'achievement': achievement,
                            'time': pygame.time.get_ticks(),
                            'alpha': 255,
                        })
                        self.sound.play('tetris')

            # Satırları temizle (efekt bilgisi alındıktan sonra)
            self.board.last_cleared_lines = []
            if hasattr(self.board, 'last_cleared_colors'):
                self.board.last_cleared_colors = {}
        
        # Kuyruktan ilk parçayı al ve kuyruğa yeni parça ekle
        self.current_piece = self.next_piece_queue.pop(0)
        self._skip_hidden_rows(self.current_piece)
        self.next_piece_queue.append(self.spawn_new_piece())
        # Lock-delay state sıfırla
        self.grounded = False
        self.lock_timer = 0
        self.lock_reset_count = 0
        self.can_hold = True
        self.can_hold2 = True
        self.fall_speed = 1000  # Zen Mode her zaman yavaş
        
        # Tema renklerini uygula
        self.apply_theme_to_pieces()
        # ZEN MODE: Yalnızca üst sınır aşıldığında veya spawn alanı bloke olduğunda temizle
        self._ensure_relaxed_space()
    
    def auto_clear_board(self, clear_entire_board=False):
        """Otomatik temizlik - Tahtayı temizle
        
        Kullanıcının seçtiği satır sayısı kadar temizler.
        clear_entire_board=True ise veya auto_clear_rows=None ise tüm tahtayı temizler.
        """
        board_width = self.board.width
        board_height = self.board.height
        
        # Tüm tahtayı temizle mi?
        if clear_entire_board or self.auto_clear_rows is None:
            self.board.grid = [[BLACK for _ in range(board_width)] for _ in range(board_height)]
            self.board.texture_grid = [[None for _ in range(board_width)] for _ in range(board_height)]
            self.board.occupancy = [[False for _ in range(board_width)] for _ in range(board_height)]
            message = t('zen_message_full_clear')
            cleared_desc = "tüm satırlar"
        else:
            # Kullanıcının seçtiği kadar satır temizle (ÜSTTEN - spawn alanı)
            rows_to_clear = min(self.auto_clear_rows, board_height)
            for i in range(rows_to_clear):
                self.board.grid[i] = [BLACK] * board_width
                self.board.texture_grid[i] = [None] * board_width
                self.board.occupancy[i] = [False] * board_width
            message = t('zen_message_rows_cleared', rows=rows_to_clear)
            cleared_desc = f"üst {rows_to_clear} satır"
        
        # Parçayı spawn konumuna geri al
        self._position_piece_at_spawn(self.current_piece)
        self._skip_hidden_rows(self.current_piece)
        
        # Temizlikten sonra parça hala geçersizse (çok az satır temizlendi), tüm tahtayı temizle
        if not clear_entire_board and self.auto_clear_rows is not None:
            if not self.board.is_valid_position(self.current_piece):
                # Recursive çağrı ile tüm tahtayı temizle
                debug_print(f"⚠️ {self.auto_clear_rows} satır yetmedi, tüm tahta temizleniyor...")
                self.board.grid = [[BLACK for _ in range(board_width)] for _ in range(board_height)]
                self.board.texture_grid = [[None for _ in range(board_width)] for _ in range(board_height)]
                self.board.occupancy = [[False for _ in range(board_width)] for _ in range(board_height)]
                self._position_piece_at_spawn(self.current_piece)
                self._skip_hidden_rows(self.current_piece)
                message = t('zen_message_full_clear_fallback')
                cleared_desc = "tüm satırlar (fallback)"
        
        # İstatistikleri güncelle
        self.auto_clears += 1
        
        # Mesaj ve ses
        self.zen_message = message
        self.zen_message_timer = 2.0  # önceki 120 frame ~ 2 saniye
        
        if self.sound_enabled:
            self.sound.play('levelup')
        
        # Parçacık efekti
        if self.effects_enabled:
            active_width, active_height = self._active_ui_size()
            center_x = active_width // 2
            center_y = active_height // 4
            self.create_particles(
                count=50,
                x=center_x,
                y=center_y,
                colors=[CYAN, (100, 200, 255), (150, 230, 255)],
                speed=5
            )
        
        debug_print(f"🧘 Zen Otomatik Temizlik #{self.auto_clears} - {cleared_desc} temizlendi")
        
        # Otomatik temizlik cezası - kalıcı olarak sakla (TEST: 50 puan)
        self.auto_clear_penalty += 50
        debug_print(f"⚠️ Otomatik temizlik cezası: -50 puan (Toplam ceza: -{self.auto_clear_penalty})")
    
    def calculate_zen_score(self):
        """Zen modunda skor = tahtadaki blok sayısı + temizlenen satırlar - cezalar"""
        # Tahtadaki toplam blok sayısını hesapla
        block_count = 0
        for row in self.board.grid:
            for cell in row:
                if cell != BLACK:
                    block_count += 1
        
        # Skor = Blok sayısı * 10 + Temizlenen satırlar * 100 - Otomatik temizlik cezası
        block_score = block_count * 10
        lines_score = self.board.lines_cleared * 100
        zen_score = block_score + lines_score - self.auto_clear_penalty
        
        # Debug - sadece ceza varsa göster
        if self.auto_clear_penalty > 0 and hasattr(self, '_last_penalty_print'):
            if self.auto_clear_penalty != self._last_penalty_print:
                debug_print(f"💰 ZEN SKOR: Bloklar={block_score} + Satırlar={lines_score} - Ceza={self.auto_clear_penalty} = {zen_score}")
                self._last_penalty_print = self.auto_clear_penalty
        
        # Skor hiçbir zaman negatif olamaz
        return max(0, zen_score)
    
    def update(self, dt):
        """Zen modu güncelleme"""
        # Zen skorunu sürekli güncelle (ceza dahil) - parent'tan ÖNCE
        calculated_score = self.calculate_zen_score()
        self.score = calculated_score
        
        # Parent update'i çağır (ama skor değişikliklerini görmezden gel)
        super().update(dt)
        
        # Skoru tekrar ayarla (parent değiştirmiş olabilir)
        self.score = calculated_score
        
        # Toplam süreyi takip et
        self.total_time += dt
        
        # Zen mesaj zamanlayıcısı (dt ms)
        # Daha önce frame bazlıydı; eski hisse yakın kalması için 60 FPS ölçeği.
        if self.zen_message_timer > 0:
            self.zen_message_timer = max(0.0, float(self.zen_message_timer) - (float(dt) / 1000.0))
            if self.zen_message_timer == 0:
                self.zen_message = ""
        
        # Her 30 saniyede bir rahatlatma bonusu
        if int(self.total_time / 1000) % 30 == 0 and self.total_time % 1000 < dt:
            self.relaxation_bonus += 50
            self.zen_message = t('zen_message_relax_bonus', bonus=50)
            self.zen_message_timer = 1.0  # önceki 60 frame ~ 1 saniye
        
        # Auto clear flag'i sıfırla
        if self.auto_clear_triggered:
            self.auto_clear_triggered = False

    def _ensure_relaxed_space(self):
        """Yığın üst sınırı aştığında veya spawn alanı bloke olduğunda alan aç."""
        pending_top_out = bool(getattr(self, '_pending_top_out_auto_clear', False))
        self._pending_top_out_auto_clear = False

        spawn_blocked = False
        current_piece = getattr(self, 'current_piece', None)
        if current_piece is not None:
            try:
                spawn_blocked = not self.board.is_valid_position(current_piece)
            except Exception:
                spawn_blocked = False

        if not (pending_top_out or spawn_blocked):
            return

        self.auto_clear_board(clear_entire_board=False)
        self.auto_clear_triggered = True
    
    def draw_mode_info(self, info_x, info_y):
        """Zen moduna özel bilgiler skor panelinin altında görünür."""
        ui_scale = self._ui_scale(min_scale=0.70, max_scale=1.16)
        s = lambda v, minimum=1: self._sx(v, ui_scale, minimum)
        skin = self.mode_skin or get_mode_skin(self.game_mode)
        panel_rect = pygame.Rect(info_x - s(10), info_y, s(190), s(150))
        surface = pygame.Surface(panel_rect.size, pygame.SRCALPHA)
        surface.fill(skin.panel_bg)
        self.screen.blit(surface, panel_rect.topleft)
        pygame.draw.rect(self.screen, skin.panel_border, panel_rect, 2, border_radius=12)
        minutes = int(self.total_time / 60000)
        seconds = int((self.total_time % 60000) / 1000)
        info_lines = [
            (t('zen_panel_auto_clear'), f'{self.auto_clears}', (255, 255, 150)),
            (t('zen_panel_penalty'), f'-{self.auto_clear_penalty}' if self.auto_clear_penalty else '0', (255, 120, 120)),
            (t('zen_panel_bonus'), f'+{self.relaxation_bonus}', (255, 200, 255)),
            (t('zen_panel_time'), f'{minutes:02d}:{seconds:02d}', (200, 255, 200)),
        ]
        label_font = self.zen_font_small
        if ui_scale != 1.0:
            label_font = retro_style.get_font(s(28, minimum=14), bold=False)
        for idx, (label, value, color) in enumerate(info_lines):
            label_text = label_font.render(label + ':', True, skin.text_color)
            self.screen.blit(label_text, (panel_rect.x + s(14), panel_rect.y + s(10) + idx * s(32)))
            value_text = label_font.render(value, True, color)
            self.screen.blit(value_text, (panel_rect.x + s(14), panel_rect.y + s(28) + idx * s(32)))
        return panel_rect.height + 15

    def draw_mode_overlay(self):
        """Zen moda özel üst başlık, merkez mesajı olmadan."""
        # Kullanıcı isteği üzerine tepedeki ZEN MODE yazısı kaldırıldı.
        pass


class HardcoreMode(Game):
    """Hardcore Mode - Sıradakiler gizli, saklama yok, kontroller ters"""
    
    def __init__(self, difficulty='Normal', sound_enabled=True, effects_enabled=True, 
                 achievement_manager=None, theme_manager=None, screen=None, fullscreen=False, 
                 settings_manager=None, user_manager=None, game_mode='hardcore', score_manager=None, sound_manager=None):
        """Hardcore modunu başlat"""
        super().__init__(
            difficulty,
            sound_enabled,
            effects_enabled,
            achievement_manager,
            theme_manager,
            screen,
            fullscreen,
            settings_manager,
            user_manager,
            game_mode,
            sound_manager=sound_manager,
            score_manager=score_manager,
        )
        self.mode_name = "HARDCORE MODE"
        
        # Hardcore özel ayarlar
        self.hide_next_pieces = True  # Sıradaki parçaları gizle
        self.disable_hold = True  # Saklama devre dışı
        self.inverted_controls = True  # Ters kontroller
        
        # Font cache
        self.hardcore_font_large = retro_style.get_font(48, bold=False)
        self.hardcore_font_medium = retro_style.get_font(36, bold=False)
        self.hardcore_font_small = retro_style.get_font(28, bold=False)
        
        # En yüksek skorlar
        self.best_scores = self._load_best_scores()
    
    def _load_best_scores(self):
        """Settings'den en iyi skorları yükle"""
        if self.settings_manager:
            scores = self.settings_manager.get('hardcore_best_scores', [])
            if isinstance(scores, list):
                return sorted([int(s) for s in scores if isinstance(s, (int, float))], reverse=True)[:3]
        return []

    def _get_left_gameplay_reserve_width(self) -> int:
        ui_scale = self._overlay_ui_scale(min_scale=0.70, max_scale=1.16)
        return self._sx(220, ui_scale) + self._sx(20, ui_scale, minimum=0)
    
    def _save_best_score(self, score):
        """Yeni skoru kaydet (en iyi 3 tutulur)"""
        if not self.settings_manager:
            return
        scores = list(self.best_scores)
        scores.append(int(score))
        scores = sorted(scores, reverse=True)[:3]
        self.best_scores = scores
        self.settings_manager.set('hardcore_best_scores', scores)
        self.settings_manager.save()
    
    def handle_input(self):
        """Ters kontroller ile girdi işleme"""
        if self.game_over or self.paused or self.show_exit_prompt:
            return super().handle_input()
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False

            if self._is_focus_loss_event(event):
                self._pause_for_focus_loss()
                continue
            
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.paused = True
                    self.pause_menu_selected = 0
                    continue
                
                if event.key == pygame.K_p:
                    self.paused = not self.paused
                    if self.paused:
                        self.pause_menu_selected = 0
                    continue
                
                # Saklama devre dışı - C tuşu çalışmaz
                if event.key == pygame.K_c:
                    # Ses efekti ile uyarı ver
                    if self.sound_enabled and self.sound:
                        try:
                            self.sound.play('move')  # Hata sesi yerine move
                        except:
                            pass
                    continue
                
                # TERS KONTROLLER (Ok tuşları)
                if event.key == pygame.K_LEFT or event.key == pygame.K_a:
                    # Sol -> Sağ
                    self._try_move_right()
                    if self.sound_enabled and self.sound:
                        self.sound.play('move')
                elif event.key == pygame.K_RIGHT or event.key == pygame.K_d:
                    # Sağ -> Sol
                    self._try_move_left()
                    if self.sound_enabled and self.sound:
                        self.sound.play('move')
                elif event.key == pygame.K_UP or event.key == pygame.K_w:
                    # Yukarı -> Aşağı (soft drop)
                    if self.current_piece:
                        self.current_piece.y += 1
                        if not self.board.is_valid_position(self.current_piece):
                            self.current_piece.y -= 1
                elif event.key == pygame.K_DOWN or event.key == pygame.K_s:
                    # Aşağı -> Döndür
                    if self.current_piece:
                        self.current_piece.rotate()
                        if not self.board.is_valid_position(self.current_piece):
                            # Wall kick dene
                            for dx in [1, -1, 2, -2]:
                                self.current_piece.x += dx
                                if self.board.is_valid_position(self.current_piece):
                                    break
                                self.current_piece.x -= dx
                            else:
                                # Geri döndür
                                for _ in range(3):
                                    self.current_piece.rotate()
                        if self.sound_enabled and self.sound:
                            self.sound.play('rotate')
                elif event.key == pygame.K_SPACE:
                    # Space hala hard drop
                    if self.current_piece:
                        drop_distance = 0
                        while self.board.is_valid_position(self.current_piece, dy=1):
                            self.current_piece.y += 1
                            drop_distance += 1
                        # Hard Drop Bonus
                        if drop_distance > 0:
                            self.board.score += drop_distance * 2
                        self.lock_and_new_piece()
                        if self.sound_enabled and self.sound:
                            self.sound.play('drop')
                elif event.key == pygame.K_z:
                    # Z hala saat yönünün tersine döndür
                    if self.current_piece:
                        # 3 kez döndür = ters yön
                        for _ in range(3):
                            self.current_piece.rotate()
                        if not self.board.is_valid_position(self.current_piece):
                            self.current_piece.rotate()  # Geri al
                        if self.sound_enabled and self.sound:
                            self.sound.play('rotate')
                elif event.key == pygame.K_x:
                    # X hala saat yönünde döndür
                    if self.current_piece:
                        self.current_piece.rotate()
                        if not self.board.is_valid_position(self.current_piece):
                            # Wall kick dene
                            original_x = self.current_piece.x
                            for dx in [1, -1, 2, -2]:
                                self.current_piece.x = original_x + dx
                                if self.board.is_valid_position(self.current_piece):
                                    break
                            else:
                                self.current_piece.x = original_x
                                for _ in range(3):
                                    self.current_piece.rotate()
                        if self.sound_enabled and self.sound:
                            self.sound.play('rotate')
                elif event.key == pygame.K_r:
                    self.restart()
        
        # Basılı tutulan tuşlar için (sürekli hareket)
        keys = pygame.key.get_pressed()
        
        # DAS (Delayed Auto Shift) için zamanlama
        current_time = pygame.time.get_ticks()
        das_delay = 170  # ms
        das_repeat = 50  # ms
        
        # Sol tuş veya A basılı -> Sağa git (TERS)
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            if not hasattr(self, '_left_press_time') or self._left_press_time is None:
                self._left_press_time = current_time
                self._left_last_move = current_time
            elif current_time - self._left_press_time > das_delay:
                if current_time - self._left_last_move > das_repeat:
                    self._try_move_right()  # TERS: Sağa
                    self._left_last_move = current_time
        else:
            self._left_press_time = None
        
        # Sağ tuş veya D basılı -> Sola git (TERS)
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            if not hasattr(self, '_right_press_time') or self._right_press_time is None:
                self._right_press_time = current_time
                self._right_last_move = current_time
            elif current_time - self._right_press_time > das_delay:
                if current_time - self._right_last_move > das_repeat:
                    self._try_move_left()  # TERS: Sola
                    self._right_last_move = current_time
        else:
            self._right_press_time = None
        
        # Yukarı tuş veya W basılı -> Aşağı git (TERS - soft drop)
        if keys[pygame.K_UP] or keys[pygame.K_w]:
            if not hasattr(self, '_up_press_time') or self._up_press_time is None:
                self._up_press_time = current_time
                self._up_last_move = current_time
            elif current_time - self._up_press_time > 50:  # Daha hızlı soft drop
                if current_time - self._up_last_move > 30:
                    if self.current_piece:
                        self.current_piece.y += 1
                        if not self.board.is_valid_position(self.current_piece):
                            self.current_piece.y -= 1
                    self._up_last_move = current_time
        else:
            self._up_press_time = None
        
        return True
    
    def update(self, dt):
        """Hardcore modu güncelleme"""
        super().update(dt)
    
    def draw_mode_info(self, info_x, info_y):
        """Hardcore mod bilgileri - sol panel"""
        from retro_style import retro_style
        ui_scale = self._overlay_ui_scale(min_scale=0.70, max_scale=1.16)
        s = lambda v, minimum=1: self._sx(v, ui_scale, minimum)
        
        board_offset_x, board_offset_y = self.get_board_offset()
        
        # Panel boyutları
        panel_width = s(220)
        panel_height = s(180)
        panel_x = board_offset_x - panel_width - s(20)
        
        if panel_x < s(10):
            panel_x = s(10)
        
        panel_y = board_offset_y
        panel_rect = pygame.Rect(panel_x, panel_y, panel_width, panel_height)
        
        # Kırmızı temalı panel
        retro_style.draw_glass_panel(
            self.screen,
            panel_rect,
            alpha=160,
            border_color=(255, 50, 50),
            glow=True
        )
        
        # Başlık
        header_font = retro_style.get_font(s(20, minimum=12), bold=True)
        header = header_font.render(t('mode_label_hardcore').upper(), True, (255, 100, 100))
        header_rect = header.get_rect(centerx=panel_rect.centerx, top=panel_rect.y + s(10))
        self.screen.blit(header, header_rect)
        
        # Ayırıcı çizgi
        pygame.draw.line(self.screen, (255, 50, 50, 150),
                        (panel_rect.x + s(15), header_rect.bottom + s(5)),
                        (panel_rect.right - s(15), header_rect.bottom + s(5)), 1)
        
        # Bilgiler
        info_font = retro_style.get_font(s(16, minimum=10), bold=False)
        warnings = [
            (f"{t('hardcore_warning_next')}:", t('hardcore_warning_next_value_hidden'), (255, 200, 100)),
            (f"{t('hardcore_warning_hold')}:", t('hardcore_warning_hold_value_disabled'), (255, 100, 100)),
            (f"{t('hardcore_warning_controls')}:", t('hardcore_warning_controls_value_inverted'), (255, 150, 50)),
        ]
        
        y_offset = header_rect.bottom + s(15)
        for label, value, color in warnings:
            label_surf = info_font.render(label, True, (200, 200, 200))
            value_surf = info_font.render(value, True, color)
            
            self.screen.blit(label_surf, (panel_rect.x + s(15), y_offset))
            value_rect = value_surf.get_rect(right=panel_rect.right - s(15), top=y_offset)
            self.screen.blit(value_surf, value_rect)
            
            y_offset += s(28)
        
        return panel_rect.height + 15
    
    def draw_mode_overlay(self):
        """Hardcore mod overlay - sadece sol panel"""
        # Sol paneli çiz
        self.draw_mode_info(0, 0)
    
    def restart(self):
        """Hardcore modu yeniden başlat"""
        # Mevcut skoru kaydet
        if hasattr(self, 'board') and self.board.score > 0:
            self._save_best_score(self.board.score)
        
        super().restart()
        self._last_score = 0
    
    def finalize_run(self, playtime=None):
        """Oyun bittiğinde skoru kaydet"""
        if hasattr(self, 'board') and self.board.score > 0:
            self._save_best_score(self.board.score)
        super().finalize_run(playtime)
    
    def _draw_right_hud_panel(self, offset_x, offset_y, board_width, board_height, skin, ui_skin, text_color, accent_color, label_color):
        """Hardcore mod için özel sağ panel - sıradaki ve saklanan parçalar YOK"""
        from retro_style import retro_style
        ui_scale = self._overlay_ui_scale(min_scale=0.70, max_scale=1.16)
        s = lambda v, minimum=1: self._sx(v, ui_scale, minimum)
        active_width, active_height = self._active_ui_size()
        # Sağ panel pozisyonu
        info_x = offset_x + board_width + s(25)
        header_y = offset_y + s(10)
        
        # Panel boyutları
        min_panel_width = s(180)
        available_right = int(active_width) - (int(offset_x) + int(board_width) + s(40))
        panel_width = min(s(220), max(min_panel_width, available_right))
        panel_width = max(min_panel_width, min(panel_width, max(min_panel_width, int(active_width) - s(24))))
        info_x = min(info_x, int(active_width) - panel_width - s(12))
        panel_height = min(board_height, int(active_height) - header_y - s(40))
        
        panel_rect = pygame.Rect(info_x, header_y, panel_width, panel_height)
        
        # Ana panel arka planı - kırmızı tema
        self._draw_hud_glass_panel(panel_rect)
        
        # İçerik pozisyonları
        curr_y = header_y + s(20)
        content_x = info_x + s(15)
        content_w = panel_width - s(30)
        
        # Başlık - HARDCORE
        title_text = t('mode_label_hardcore').upper()
        title_max_width = max(s(90, minimum=60), content_w - s(6, minimum=2))
        title_base_size = s(28, minimum=16)
        title_min_size = max(s(12, minimum=8), 8)
        title_color = (255, 50, 50)
        title_surf = self._render_hud_fitted_text(
            title_text,
            title_color,
            title_max_width,
            title_base_size,
            title_min_size,
            bold=True,
            compact_mode_key='hardcore',
        )
        glow_surf = title_surf.copy()
        glow_surf.set_alpha(70)
        for off in range(2, 0, -1):
            self.screen.blit(glow_surf, glow_surf.get_rect(midtop=(info_x + panel_width // 2, curr_y + off)))
        title_rect = title_surf.get_rect(midtop=(info_x + panel_width // 2, curr_y))
        self.screen.blit(title_surf, title_rect)
        
        curr_y = title_rect.bottom + s(13)
        
        # Gizli sıradaki parçalar kutusu
        box_size = s(70)
        box_rect = pygame.Rect(content_x + (content_w - box_size) // 2, curr_y, box_size, box_size)
        pygame.draw.rect(self.screen, (20, 10, 10, 200), box_rect, border_radius=8)
        pygame.draw.rect(self.screen, (255, 50, 50), box_rect, 2, border_radius=8)
        
        # "???" metni
        q_font = retro_style.get_font(s(32, minimum=18), bold=True)
        q_surf = q_font.render("???", True, (255, 100, 100))
        q_rect = q_surf.get_rect(center=box_rect.center)
        self.screen.blit(q_surf, q_rect)
        
        curr_y += box_size + s(20)
        
        # Devre dışı saklama kutusu
        hold_box = pygame.Rect(content_x + (content_w - box_size) // 2, curr_y, box_size, s(50))
        pygame.draw.rect(self.screen, (15, 15, 15, 180), hold_box, border_radius=8)
        pygame.draw.rect(self.screen, (80, 80, 80), hold_box, 1, border_radius=8)
        
        # "X" metni
        x_font = retro_style.get_font(s(28, minimum=16), bold=True)
        x_surf = x_font.render("X", True, (100, 50, 50))
        x_rect = x_surf.get_rect(center=hold_box.center)
        self.screen.blit(x_surf, x_rect)
        
        curr_y += s(70)
        
        # Skor ve istatistikler
        stats_h = s(180)
        stats_rect = pygame.Rect(content_x, curr_y, content_w, stats_h)
        self._hud_stats_rect = stats_rect
        self._hud_panel_rect = panel_rect
        self._hud_content_x = content_x
        self._hud_content_w = content_w
        
        # Stats arka planı
        stats_surf = pygame.Surface(stats_rect.size, pygame.SRCALPHA)
        for i in range(stats_h):
            a = 180 + int(40 * (i / stats_h))
            pygame.draw.line(stats_surf, (25, 15, 15, a), (0, i), (content_w, i))
        self.screen.blit(stats_surf, stats_rect.topleft)
        pygame.draw.rect(self.screen, (100, 40, 40), stats_rect, 1, border_radius=12)
        
        stat_y = curr_y + s(15)
        
        def draw_stat(label, value, y, color=(255, 100, 100)):
            l_surf = retro_style.get_font(s(16, minimum=10)).render(label, True, (180, 150, 150))
            self.screen.blit(l_surf, (content_x + s(15), y))
            v_surf = retro_style.get_font(s(24, minimum=14), bold=True).render(str(value), True, color)
            v_rect = v_surf.get_rect(topright=(content_x + content_w - s(15), y - s(4)))
            self.screen.blit(v_surf, v_rect)
            pygame.draw.line(self.screen, (255, 255, 255, 30), (content_x + s(10), y + s(32)), (content_x + content_w - s(10), y + s(32)))
            return s(45)
        
        stat_y += draw_stat(t('score'), f'{self.board.score:,}'.replace(',', '.'), stat_y)
        stat_y += draw_stat(t('lines'), str(self.board.lines_cleared), stat_y, (200, 180, 180))
        stat_y += draw_stat(t('level'), str(self.board.level), stat_y)
        
        # Mod info alanı
        mode_info_y = stats_rect.bottom + s(15)
        self._hud_mode_info_area = (
            int(content_x),
            int(mode_info_y),
            int(content_w),
            int(max(0, active_height - mode_info_y - s(8))),
        )
