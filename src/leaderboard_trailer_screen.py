from __future__ import annotations

import pygame

try:
    from .menu import Menu
    from .platform_utils import is_fullscreen_toggle, normalize_mouse_pos, get_mouse_pos
    from .retro_style import retro_style
    from .localization import t
    from .back_button import draw_back_button as _draw_shared_back_button
except Exception:
    from menu import Menu
    from platform_utils import is_fullscreen_toggle, normalize_mouse_pos, get_mouse_pos
    from retro_style import retro_style
    from localization import t
    from back_button import draw_back_button as _draw_shared_back_button


def get_leaderboard_trailer_panel_rect(surface_size: tuple[int, int]) -> pygame.Rect:
    width = max(1, int(surface_size[0]))
    height = max(1, int(surface_size[1]))
    panel_w = min(width - 48, max(560, int(width * 0.70)))
    panel_h = min(height - 110, max(460, int(height * 0.76)))
    panel_x = (width - panel_w) // 2
    panel_y = max(88, (height - panel_h) // 2 + int(height * 0.035))
    return pygame.Rect(panel_x, panel_y, panel_w, panel_h)


class LeaderboardTrailerScreen:
    def __init__(self, screen, settings_manager=None, user_manager=None):
        self.screen = screen
        self.settings_manager = settings_manager
        self.user_manager = user_manager
        self.preview_menu = Menu(screen, user_manager=user_manager, settings_manager=settings_manager)
        self.preview_menu.enable_mystery_lb_trailer_preview()
        # Mouse Geri butonu — sol üst, overlay panel ortada olduğu için
        # çakışmaz. ESC ve replay kısayolları aynen korunur.
        self._back_rect: pygame.Rect | None = None
        self._back_hover: bool = False

    def restart_animation(self) -> None:
        self.preview_menu.enable_mystery_lb_trailer_preview()

    def handle_input(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                return 'back'
            if event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_l, pygame.K_r):
                self.preview_menu._start_mystery_lb_trailer_debug()
                return None
            if is_fullscreen_toggle(event.key, getattr(event, 'mod', 0)):
                return 'toggle_fullscreen'
        elif event.type == pygame.MOUSEMOTION:
            pos = normalize_mouse_pos(getattr(event, 'pos', None)) or event.pos
            self._back_hover = bool(
                self._back_rect is not None and self._back_rect.collidepoint(pos)
            )
        elif event.type == pygame.MOUSEBUTTONDOWN and getattr(event, 'button', None) == 1:
            pos = normalize_mouse_pos(getattr(event, 'pos', None)) or event.pos
            # Replay kısayollarını ezme: yalnızca back rect'e tıklama 'back'
            # döner; overlay panel veya başka alana tıklama hiçbir aksiyon
            # tetiklemez (mevcut davranışla aynı).
            if self._back_rect is not None and self._back_rect.collidepoint(pos):
                return 'back'
        return None

    def draw(self):
        self.preview_menu.screen = self.screen
        self.preview_menu.draw()

        width, height = self.screen.get_size()
        overlay = pygame.Surface((width, height), pygame.SRCALPHA)
        overlay.fill((5, 8, 18, 128))
        self.screen.blit(overlay, (0, 0))

        title_font = retro_style.get_font(max(24, int(height * 0.028)), bold=True)
        hint_font = retro_style.get_font(max(14, int(height * 0.015)))
        title = title_font.render('LEADERBOARD TRAILER PREVIEW', True, (236, 241, 255))
        hint = hint_font.render('ENTER / SPACE / L / R: yeniden oynat    ESC: geri', True, (184, 198, 228))
        self.screen.blit(title, title.get_rect(center=(width // 2, max(42, int(height * 0.055)))))
        self.screen.blit(hint, hint.get_rect(center=(width // 2, max(76, int(height * 0.092)))))

        panel_rect = get_leaderboard_trailer_panel_rect(self.screen.get_size())
        self.preview_menu._draw_mystery_leaderboard_panel(panel_rect)

        # Mouse Geri butonu (sol üst, overlay panelin tamamen dışında).
        self._draw_back_button(width, height)

    def _draw_back_button(self, width: int, height: int) -> None:
        """Sol üst Geri affordance — ESC ile aynı semantik ('back').

        Overlay panel ekran ortasında konumlandığı için sol üst köşe
        boşta kalır; bu chip oraya yerleşir. Görsel format ana menüdeki
        sağ alt 'Çık' tuşu ile aynıdır (ortak helper)."""
        scale = max(0.7, min(1.4, width / 1366.0))
        s = lambda v, minimum=1: max(minimum, int(round(v * scale)))

        try:
            live_pos = get_mouse_pos()
        except Exception:
            live_pos = (-1, -1)
        prev_rect = self._back_rect
        hover = bool(prev_rect is not None and prev_rect.collidepoint(live_pos))

        rect = _draw_shared_back_button(self.screen, s, hover=hover, retro_style=retro_style)
        self._back_rect = rect
        self._back_hover = bool(rect.collidepoint(live_pos))