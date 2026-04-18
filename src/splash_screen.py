import os
import sys
import math
import random
import pygame

from asset_manager import load_image
from gamepad_manager import get_gamepad_manager
from promptfont_support import render_inline_action_text_surface
from retro_style import retro_style
from localization import t
from background_effects import get_shared_falling_blocks_layer

# macOS detection
_IS_MACOS = sys.platform == 'darwin'

# Quadrix renkleri - Retro Atari temasına uygun
TETRIS_COLORS = [
    (0, 255, 221),    # Neon Cyan (I)
    (255, 248, 0),    # Yellow (O)
    (255, 132, 75),   # Orange (T)
    (0, 200, 120),    # Green (S)
    (255, 80, 80),    # Red (Z)
    (0, 180, 255),    # Blue (J)
    (255, 150, 50),   # Orange (L)
]


def _get_base_path() -> str:
    """PyInstaller uyumlu temel dizin."""
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return sys._MEIPASS
    return os.path.dirname(__file__)


class Sparkle:
    """Işıltı parçacığı"""
    def __init__(self, screen_w, screen_h):
        self.screen_w = screen_w
        self.screen_h = screen_h
        self.reset()
        
    def reset(self):
        self.x = random.randint(0, self.screen_w)
        self.y = random.randint(0, self.screen_h)
        self.life = random.uniform(0.5, 2.0)
        self.max_life = self.life
        self.size = random.uniform(2, 6)
        self.color = random.choice(TETRIS_COLORS)
        
    def update(self, dt):
        self.life -= dt / 1000.0
        if self.life <= 0:
            self.reset()
            
    def draw(self, surface):
        progress = self.life / self.max_life
        alpha = int(255 * progress * math.sin(progress * math.pi))
        size = self.size * (0.5 + 0.5 * math.sin(progress * math.pi * 2))
        
        if alpha > 0 and size > 0:
            glow_surf = pygame.Surface((int(size * 4), int(size * 4)), pygame.SRCALPHA)
            center = int(size * 2)
            # Dış glow
            pygame.draw.circle(glow_surf, (*self.color, alpha // 3), (center, center), int(size * 2))
            # İç parlak nokta
            pygame.draw.circle(glow_surf, (255, 255, 255, alpha), (center, center), int(size))
            surface.blit(glow_surf, (self.x - center, self.y - center))


class NeonText:
    """Neon efektli metin"""
    @staticmethod
    def render(text, font, base_color, glow_color=None, glow_amount=3):
        if glow_color is None:
            glow_color = base_color
            
        # Ana metin
        text_surf = font.render(text, True, base_color)
        w, h = text_surf.get_size()
        
        # Glow için daha büyük yüzey
        glow_padding = glow_amount * 4
        result = pygame.Surface((w + glow_padding * 2, h + glow_padding * 2), pygame.SRCALPHA)
        
        # Glow katmanları
        for i in range(glow_amount, 0, -1):
            alpha = int(60 / i)
            glow_surf = font.render(text, True, (*glow_color[:3], alpha))
            for dx in range(-i, i + 1):
                for dy in range(-i, i + 1):
                    if dx * dx + dy * dy <= i * i:
                        result.blit(glow_surf, (glow_padding + dx, glow_padding + dy), special_flags=pygame.BLEND_RGBA_ADD)
        
        # Ana metin üstte
        result.blit(text_surf, (glow_padding, glow_padding))
        
        return result


class SplashScreen:
    def __init__(self, screen, settings_manager=None, image_dir=None, prompt_text=None):
        self.screen = screen
        self.settings_manager = settings_manager
        self._custom_prompt = prompt_text
        self.clock = pygame.time.Clock()

        # Windows PrintScreen / focus-loss recovery state
        self._display_was_inactive = False
        self._prtsc_was_down = False
        self._pending_prtsc_recover_ms = -1
        self._last_display_recover_ms = -10_000

        # Ekran boyutları
        self.screen_w, self.screen_h = screen.get_size()
        
        # Arka plan animasyon elemanları - ana menü ile aynı sistemi kullan
        self.background_fx = get_shared_falling_blocks_layer('default')
        self.sparkles = [Sparkle(self.screen_w, self.screen_h) for _ in range(40)]
        
        # Find image in provided image_dir or fallback to src/splashscreen
        if image_dir is None:
            image_dir = os.path.join(_get_base_path(), 'src', 'splashscreen')
            if not os.path.exists(image_dir):
                image_dir = os.path.join(os.path.dirname(__file__), 'splashscreen')
        self.image_path = None
        if os.path.isdir(image_dir):
            for f in sorted(os.listdir(image_dir)):
                if f.lower().endswith('.png'):
                    self.image_path = os.path.join(image_dir, f)
                    break
        # Load image if found
        self.image = None
        if self.image_path and os.path.exists(self.image_path):
            try:
                self.image = load_image(self.image_path, convert_alpha=True)
            except Exception:
                self.image = None

    def _get_continue_button_label(self):
        try:
            gamepad_mgr = get_gamepad_manager()
        except Exception:
            return 'Enter'

        try:
            if getattr(gamepad_mgr, 'enabled', False) and gamepad_mgr.is_connected():
                button_label = gamepad_mgr.get_button_label('menu_confirm')
                if button_label and button_label != '?':
                    return button_label
        except Exception:
            pass

        return 'Enter'

    def _get_prompt_text(self):
        if self._custom_prompt:
            return self._custom_prompt
        return t('splash_press_enter', button=self._get_continue_button_label())

    def _recover_display_after_focus_loss(self, reason: str = '') -> bool:
        """Windows'ta focus/screenshot sonrası splash display'ini yeniden kur."""
        if sys.platform != 'win32':
            return False

        now_ms = pygame.time.get_ticks()
        if now_ms - self._last_display_recover_ms < 900:
            return False
        self._last_display_recover_ms = now_ms

        try:
            width = int(self.screen.get_width()) if self.screen is not None else 0
            height = int(self.screen.get_height()) if self.screen is not None else 0
        except Exception:
            width, height = 0, 0

        width = max(800, width or 0)
        height = max(600, height or 0)

        fullscreen = False
        borderless = False
        try:
            if self.settings_manager is not None:
                fullscreen = bool(self.settings_manager.get('fullscreen', False))
                borderless = bool(self.settings_manager.get('borderless_fullscreen', True))
            else:
                fullscreen = bool(self.screen and (self.screen.get_flags() & pygame.FULLSCREEN))
                borderless = fullscreen
        except Exception:
            fullscreen = False
            borderless = False

        try:
            from platform_utils import create_display, request_window_focus

            self.screen = create_display(
                width,
                height,
                fullscreen=fullscreen,
                resizable=True,
                borderless=(borderless if fullscreen else False),
            )
            self.screen_w, self.screen_h = self.screen.get_size()
            request_window_focus()
            return True
        except Exception:
            return False

    def _update_windows_display_recovery(self, now: int) -> None:
        """Windows için focus regain / PrintScreen sonrası otomatik recovery."""
        if sys.platform != 'win32':
            return

        try:
            is_active = bool(pygame.display.get_active())
        except Exception:
            is_active = True

        focus_event_seen = False
        for evt_name in ('WINDOWFOCUSGAINED', 'WINDOWRESTORED', 'WINDOWEXPOSED'):
            evt_type = getattr(pygame, evt_name, None)
            if evt_type is not None and pygame.event.peek(evt_type):
                focus_event_seen = True
                break

        if not is_active:
            self._display_was_inactive = True
        else:
            if self._display_was_inactive:
                self._display_was_inactive = False
                focus_event_seen = True
            if focus_event_seen:
                self._recover_display_after_focus_loss('focus_regain')

        prtsc_down = False
        k_prtsc = getattr(pygame, 'K_PRINTSCREEN', None)
        if k_prtsc is not None:
            try:
                keys = pygame.key.get_pressed()
                if 0 <= int(k_prtsc) < len(keys):
                    prtsc_down = bool(keys[int(k_prtsc)])
            except Exception:
                prtsc_down = False

        if prtsc_down and not self._prtsc_was_down:
            self._pending_prtsc_recover_ms = now + 220
        self._prtsc_was_down = prtsc_down

        if self._pending_prtsc_recover_ms > 0 and now >= self._pending_prtsc_recover_ms and not self._prtsc_was_down:
            self._pending_prtsc_recover_ms = -1
            self._recover_display_after_focus_loss('printscreen')

    def run(self):
        """Run splashscreen loop, returns True if continue, False for quit"""
        running = True
        alpha = 0
        fade_in = True
        fade_out = False
        duration = 1800  # fade-in duration in ms
        start_time = pygame.time.get_ticks()
        
        # Logo animasyon değişkenleri
        logo_scale = 0.8
        logo_target_scale = 1.0
        
        # Enter text animasyonu
        enter_blink_speed = 400  # ms
        
        exit_start = 0
        exit_duration = 1000  # Uzun animasyon

        while running:
            dt = self.clock.tick(60)  # 60 FPS for smooth animations
            now = pygame.time.get_ticks()

            confirm_pressed = False
            try:
                gamepad_mgr = get_gamepad_manager()
                gamepad_mgr.set_context('menu')
                for gp_event in gamepad_mgr.update(dt):
                    pygame.event.post(gp_event)
                if getattr(gamepad_mgr, 'enabled', False):
                    confirm_pressed = gamepad_mgr.was_action_just_pressed('menu_confirm')
            except Exception:
                confirm_pressed = False
            
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return False
                if event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        fade_out = True
                        exit_start = now
            if confirm_pressed and not fade_out:
                fade_out = True
                exit_start = now

            self._update_windows_display_recovery(now)
                        
            # Update animations
            elapsed = now - start_time
            
            # Düşen blokları güncelle (ana menü ile paylaşılan sistem)
            self.background_fx.update(self.screen)
            
            # Işıltıları güncelle
            for sparkle in self.sparkles:
                sparkle.update(dt)
            
            # Logo scale animasyonu (yumuşak geçiş)
            if logo_scale < logo_target_scale:
                logo_scale += (logo_target_scale - logo_scale) * 0.02
            
            # Fade-in / Fade-out logic
            if fade_out:
                exit_elapsed = now - exit_start
                frac = min(1.0, float(exit_elapsed) / max(1, exit_duration))
                
                # Ease out cubic - son kısımda daha hızlı
                ease_frac = 1 - (1 - frac) ** 3
                
                # Alpha: Smooth düşüş
                alpha = max(0, int(255 * (1 - ease_frac)))
                
                # Logo: Hafif zoom out
                logo_scale = 1.0 + ease_frac * 0.15
                
                # Alpha 5'in altına düşünce hemen geç
                if alpha <= 5:
                    # Event kuyruğunu temizle - menüye geçerken eski input'lar sorun çıkarmasın
                    pygame.event.clear()
                    return True
            elif fade_in:
                # Ease in cubic
                frac = min(1.0, elapsed / max(1, duration))
                ease_frac = frac ** 2
                alpha = min(255, int(255 * ease_frac))
                logo_scale = 0.7 + 0.3 * ease_frac
                if alpha >= 255:
                    fade_in = False
                    logo_scale = 1.0
            else:
                # Steady state (no breathing/pulse)
                alpha = 255
                logo_scale = 1.0  # Logo sabit kalıyor

            # === DRAW ===
            w, h = self.screen.get_size()
            
            # Gradient arka plan
            self._draw_gradient_background(w, h)
            
            # Düşen blokları çiz (arka planda - ana menü ile aynı sistem)
            self.background_fx.draw(self.screen)
            
            # Ana görsel veya fallback (biraz şeffaf ki bloklar görünsün)
            if self.image:
                iw, ih = self.image.get_size()
                # Tam ekrana sığdır (cover)
                base_scale = max(float(w) / iw, float(h) / ih)
                final_scale = base_scale * logo_scale
                size = (int(iw * final_scale), int(ih * final_scale))
                
                try:
                    if _IS_MACOS:
                        img = pygame.transform.scale(self.image, size)
                    else:
                        img = pygame.transform.smoothscale(self.image, size)
                except Exception:
                    img = pygame.transform.scale(self.image, size)
                
                # Tam ortaya yerleştir
                rect = img.get_rect(center=(w // 2, h // 2))
                
                # Alpha uygula (daha şeffaf yap ki arkadaki bloklar görünsün)
                img_alpha = min(alpha, 180)  # Max 180, böylece arkası daha iyi görünür
                img.set_alpha(img_alpha)
                self.screen.blit(img, rect)
            else:
                # Fallback: Neon QUADRIX yazısı
                self._draw_neon_title(w, h, alpha, now)
            
            # Işıltıları çiz (ön planda)
            for sparkle in self.sparkles:
                sparkle.draw(self.screen)
            
            # Alt prompt paneli - animasyonlu
            self._draw_animated_prompt(w, h, now, fade_out)

            pygame.display.flip()

        return True
    
    def _draw_gradient_background(self, w, h):
        """Animasyonlu gradient arka plan"""
        # Koyu mor-mavi gradient
        for y in range(0, h, 4):
            ratio = y / h
            r = int(8 + 15 * ratio)
            g = int(5 + 10 * ratio)
            b = int(25 + 20 * (1 - ratio))
            pygame.draw.line(self.screen, (r, g, b), (0, y), (w, y))
        
        # Grid çizgileri (subtle)
        grid_color = (30, 40, 80, 40)
        grid_surf = pygame.Surface((w, h), pygame.SRCALPHA)
        spacing = 50
        for x in range(0, w, spacing):
            pygame.draw.line(grid_surf, grid_color, (x, 0), (x, h), 1)
        for y in range(0, h, spacing):
            pygame.draw.line(grid_surf, grid_color, (0, y), (w, y), 1)
        self.screen.blit(grid_surf, (0, 0))
    
    def _draw_neon_title(self, w, h, alpha, now):
        """Neon efektli QUADRIX başlığı"""
        title_font = retro_style.get_font(80)
        
        # Rainbow color cycle
        hue = (now / 20) % 360
        color = self._hsv_to_rgb(hue, 0.8, 1.0)
        
        # Glow efekti
        title_surf = NeonText.render('QUADRIX', title_font, (255, 255, 255), color, glow_amount=4)
        title_surf.set_alpha(alpha)
        title_rect = title_surf.get_rect(center=(w // 2, h // 2 - 60))
        self.screen.blit(title_surf, title_rect)
    
    def _hsv_to_rgb(self, h, s, v):
        """HSV to RGB conversion"""
        h = h / 360.0
        if s == 0.0:
            return (int(v * 255), int(v * 255), int(v * 255))
        i = int(h * 6.0)
        f = (h * 6.0) - i
        p = v * (1.0 - s)
        q = v * (1.0 - s * f)
        t = v * (1.0 - s * (1.0 - f))
        i = i % 6
        if i == 0:
            return (int(v * 255), int(t * 255), int(p * 255))
        if i == 1:
            return (int(q * 255), int(v * 255), int(p * 255))
        if i == 2:
            return (int(p * 255), int(v * 255), int(t * 255))
        if i == 3:
            return (int(p * 255), int(q * 255), int(v * 255))
        if i == 4:
            return (int(t * 255), int(p * 255), int(v * 255))
        if i == 5:
            return (int(v * 255), int(p * 255), int(q * 255))
        return (255, 255, 255)
    
    def _draw_animated_prompt(self, w, h, now, fade_out):
        """Animasyonlu 'Enter basın' prompt'u"""
        prompt_font = retro_style.get_font(22, bold=False)
        prompt_text = self._get_prompt_text()
        button_label = self._get_continue_button_label()
        
        # Yanıp sönen efekt
        blink = 0.6 + 0.4 * math.sin(now / 300.0)
        text_alpha = int(255 * blink) if not fade_out else int(255 * (1 - blink))
        
        # Rainbow border animasyonu
        hue = (now / 15) % 360
        border_color = self._hsv_to_rgb(hue, 0.7, 1.0)
        
        text_surf = render_inline_action_text_surface(
            prompt_text,
            button_label,
            'menu_confirm',
            prompt_font,
            (255, 255, 255),
        )
        text_rect = text_surf.get_rect(center=(w // 2, int(h * 0.88)))
        
        # Panel
        panel_w = text_rect.width + 80
        panel_h = text_rect.height + 36
        panel_rect = pygame.Rect((w - panel_w) // 2, text_rect.y - 18, panel_w, panel_h)
        panel_surf = pygame.Surface(panel_rect.size, pygame.SRCALPHA)
        
        # Gradient fill
        for i in range(panel_h):
            ratio = i / panel_h
            alpha_val = int(160 + 40 * ratio)
            pygame.draw.line(panel_surf, (15, 20, 40, alpha_val), (0, i), (panel_w, i))
        
        # Animated border
        pygame.draw.rect(panel_surf, (*border_color, 200), panel_surf.get_rect(), 3, border_radius=18)
        
        # Inner glow
        inner_rect = panel_surf.get_rect().inflate(-8, -8)
        pygame.draw.rect(panel_surf, (*border_color, 50), inner_rect, 2, border_radius=14)
        
        # Dekoratif köşe ışıkları
        corner_size = 8
        corners = [(corner_size, corner_size), (panel_w - corner_size, corner_size),
                   (corner_size, panel_h - corner_size), (panel_w - corner_size, panel_h - corner_size)]
        for cx, cy in corners:
            pygame.draw.circle(panel_surf, (*border_color, 180), (cx, cy), 4)
            pygame.draw.circle(panel_surf, (255, 255, 255, 100), (cx, cy), 2)
        
        self.screen.blit(panel_surf, panel_rect.topleft)
        
        # Text with glow
        text_glow = render_inline_action_text_surface(
            prompt_text,
            button_label,
            'menu_confirm',
            prompt_font,
            border_color,
        )
        text_glow.set_alpha(text_alpha // 2)
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            self.screen.blit(text_glow, (text_rect.x + dx, text_rect.y + dy))
        
        text_surf.set_alpha(text_alpha)
        self.screen.blit(text_surf, text_rect)
        
        # Animated arrows
        arrow_offset = int(10 * math.sin(now / 200.0))
        arrow_alpha = int(180 + 75 * math.sin(now / 250.0))
        
        # Sol ok
        left_arrow = pygame.Surface((20, 20), pygame.SRCALPHA)
        pygame.draw.polygon(left_arrow, (*border_color, arrow_alpha), 
                          [(15, 2), (5, 10), (15, 18)])
        self.screen.blit(left_arrow, (panel_rect.left - 30 - arrow_offset, panel_rect.centery - 10))
        
        # Sağ ok
        right_arrow = pygame.Surface((20, 20), pygame.SRCALPHA)
        pygame.draw.polygon(right_arrow, (*border_color, arrow_alpha), 
                          [(5, 2), (15, 10), (5, 18)])
        self.screen.blit(right_arrow, (panel_rect.right + 10 + arrow_offset, panel_rect.centery - 10))
    
    def _draw_corner_decorations(self, w, h, now, alpha):
        """Köşe dekorasyonları"""
        corner_size = 60
        line_length = 40
        corner_alpha = int(alpha * 0.6)
        
        # Renk döngüsü
        hue = (now / 25) % 360
        color = (*self._hsv_to_rgb(hue, 0.6, 1.0), corner_alpha)
        
        deco_surf = pygame.Surface((w, h), pygame.SRCALPHA)
        
        # Sol üst
        pygame.draw.line(deco_surf, color, (10, 10), (10, 10 + line_length), 3)
        pygame.draw.line(deco_surf, color, (10, 10), (10 + line_length, 10), 3)
        
        # Sağ üst
        pygame.draw.line(deco_surf, color, (w - 10, 10), (w - 10, 10 + line_length), 3)
        pygame.draw.line(deco_surf, color, (w - 10, 10), (w - 10 - line_length, 10), 3)
        
        # Sol alt
        pygame.draw.line(deco_surf, color, (10, h - 10), (10, h - 10 - line_length), 3)
        pygame.draw.line(deco_surf, color, (10, h - 10), (10 + line_length, h - 10), 3)
        
        # Sağ alt
        pygame.draw.line(deco_surf, color, (w - 10, h - 10), (w - 10, h - 10 - line_length), 3)
        pygame.draw.line(deco_surf, color, (w - 10, h - 10), (w - 10 - line_length, h - 10), 3)
        
        self.screen.blit(deco_surf, (0, 0))
