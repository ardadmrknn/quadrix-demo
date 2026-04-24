from __future__ import annotations

import pygame

try:
    from .menu import Menu
    from .platform_utils import is_fullscreen_toggle
    from .retro_style import retro_style
except Exception:
    from menu import Menu
    from platform_utils import is_fullscreen_toggle
    from retro_style import retro_style


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