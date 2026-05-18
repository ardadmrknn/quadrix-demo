from __future__ import annotations

from dataclasses import dataclass
import webbrowser

import pygame

try:
    from . import demo_config
    from .localization import t
    from .retro_style import retro_style
    from .ui_theme import UIColors, UIFonts
    from .ui_scaling import get_projected_effective_scale
except Exception:
    import demo_config
    from localization import t
    from retro_style import retro_style
    from ui_theme import UIColors, UIFonts
    from ui_scaling import get_projected_effective_scale


@dataclass(slots=True)
class _PromptLayout:
    panel_rect: pygame.Rect
    title_rect: pygame.Rect
    body_rect: pygame.Rect
    confirm_rect: pygame.Rect
    cancel_rect: pygame.Rect
    lines: list[str]
    line_height: int


class DemoUpgradePrompt:
    def __init__(self, screen: pygame.Surface):
        self.screen = screen
        self.active = False
        self.title = ""
        self.message = ""
        self.confirm_label = ""
        self.cancel_label = ""
        self.confirm_rect: pygame.Rect | None = None
        self.cancel_rect: pygame.Rect | None = None
        self._last_action: str | None = None

    def is_active(self) -> bool:
        return bool(self.active)

    def show(
        self,
        *,
        message: str,
        confirm_label: str,
        cancel_label: str,
        title: str | None = None,
    ) -> None:
        self.active = True
        self.title = str(title or t('demo_prompt_title', default='Demo Sınırı'))
        self.message = str(message or '')
        self.confirm_label = str(confirm_label or '')
        self.cancel_label = str(cancel_label or '')
        self.confirm_rect = None
        self.cancel_rect = None
        self._last_action = None

    def hide(self) -> None:
        self.active = False
        self.confirm_rect = None
        self.cancel_rect = None

    def consume_last_action(self) -> str | None:
        action = self._last_action
        self._last_action = None
        return action

    def _close_with_action(self, action: str) -> None:
        self._last_action = str(action)
        self.hide()

    def handle_input(self, event: pygame.event.Event) -> bool:
        if not self.active:
            return False

        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_ESCAPE,):
                self._close_with_action('cancel')
                return True
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                self._open_store()
                return True

        if event.type == pygame.MOUSEBUTTONDOWN and getattr(event, 'button', None) == 1:
            pos = getattr(event, 'pos', None)
            if self.confirm_rect and self.confirm_rect.collidepoint(pos):
                self._open_store()
                return True
            if self.cancel_rect and self.cancel_rect.collidepoint(pos):
                self._close_with_action('cancel')
                return True
            self._close_with_action('cancel')
            return True

        return True

    def draw(self) -> None:
        if not self.active:
            return

        width, height = self.screen.get_size()
        scale = get_projected_effective_scale(
            self.screen,
            min_scale=0.72,
            max_scale=1.18,
            reference_size=(1366.0, 768.0),
        )
        s = lambda value, minimum=1: max(minimum, int(round(value * scale)))

        overlay = pygame.Surface((width, height), pygame.SRCALPHA)
        overlay.fill((4, 8, 18, 172))
        self.screen.blit(overlay, (0, 0))

        panel_width = min(width - s(80), s(620))
        title_font = retro_style.get_fitting_font(
            self.title,
            s(28, 16),
            panel_width - s(84),
            bold=True,
            min_size=s(18, 10),
        )
        body_font = UIFonts.get(s(18, 11), bold=False)
        layout = self._build_layout((width, height), scale, title_font, body_font, panel_width=panel_width)

        retro_style.draw_glass_panel(
            self.screen,
            layout.panel_rect,
            alpha=210,
            border_color=UIColors.NEON_CYAN,
            glow=True,
        )

        title_surf = title_font.render(self.title, True, UIColors.TEXT_PRIMARY)
        self.screen.blit(title_surf, layout.title_rect)

        text_y = layout.body_rect.y
        for line in layout.lines:
            line_surf = body_font.render(line, True, UIColors.TEXT_SECONDARY)
            line_rect = line_surf.get_rect(midtop=(layout.body_rect.centerx, text_y))
            self.screen.blit(line_surf, line_rect)
            text_y += layout.line_height

        self.confirm_rect = layout.confirm_rect
        self.cancel_rect = layout.cancel_rect

        confirm_font = retro_style.get_fitting_font(
            self.confirm_label,
            s(16, 10),
            self.confirm_rect.width - s(24),
            bold=True,
            min_size=s(10, 8),
        )
        cancel_font = retro_style.get_fitting_font(
            self.cancel_label,
            s(16, 10),
            self.cancel_rect.width - s(24),
            bold=True,
            min_size=s(10, 8),
        )

        self._draw_button(self.confirm_rect, self.confirm_label, UIColors.NEON_GOLD, confirm_font, dark_text=True)
        self._draw_button(self.cancel_rect, self.cancel_label, UIColors.BUTTON_BORDER, cancel_font, dark_text=False)

    def _build_layout(
        self,
        screen_size: tuple[int, int],
        scale: float,
        title_font,
        body_font,
        *,
        panel_width: int | None = None,
    ) -> _PromptLayout:
        width, height = screen_size
        s = lambda value, minimum=1: max(minimum, int(round(value * scale)))

        resolved_panel_width = int(panel_width or min(width - s(80), s(620)))
        resolved_panel_width = max(s(360), min(resolved_panel_width, width - s(40)))
        wrap_width = max(s(180), resolved_panel_width - s(50))
        lines = self._wrap_text(body_font, self.message, wrap_width)
        line_height = max(s(24), body_font.get_height() + s(6))
        body_height = max(line_height, len(lines) * line_height)

        button_width = max(s(170), (resolved_panel_width - s(68)) // 2)
        button_height = s(46)
        desired_panel_height = (
            s(18)
            + title_font.get_height()
            + s(20)
            + body_height
            + s(22)
            + button_height
            + s(24)
        )
        resolved_panel_height = min(height - s(100), max(s(248), desired_panel_height))
        panel_rect = pygame.Rect(
            (width - resolved_panel_width) // 2,
            (height - resolved_panel_height) // 2,
            resolved_panel_width,
            resolved_panel_height,
        )

        title_width = min(title_font.size(self.title)[0], wrap_width)
        title_rect = pygame.Rect(0, 0, max(1, title_width), title_font.get_height())
        title_rect.midtop = (panel_rect.centerx, panel_rect.y + s(18))

        body_rect = pygame.Rect(
            panel_rect.x + s(25),
            title_rect.bottom + s(20),
            panel_rect.width - s(50),
            body_height,
        )
        button_y = body_rect.bottom + s(22)
        confirm_rect = pygame.Rect(panel_rect.x + s(22), button_y, button_width, button_height)
        cancel_rect = pygame.Rect(panel_rect.right - button_width - s(22), button_y, button_width, button_height)

        return _PromptLayout(
            panel_rect=panel_rect,
            title_rect=title_rect,
            body_rect=body_rect,
            confirm_rect=confirm_rect,
            cancel_rect=cancel_rect,
            lines=lines,
            line_height=line_height,
        )

    def _draw_button(
        self,
        rect: pygame.Rect,
        label: str,
        border_color: tuple[int, int, int],
        font,
        *,
        dark_text: bool,
    ) -> None:
        fill = (*border_color, 210) if dark_text else (*UIColors.BG_MEDIUM, 220)
        pygame.draw.rect(self.screen, fill, rect, border_radius=12)
        pygame.draw.rect(self.screen, border_color, rect, 2, border_radius=12)
        text_color = UIColors.BG_DARK if dark_text else UIColors.TEXT_PRIMARY
        text_surf = font.render(label, True, text_color)
        text_rect = text_surf.get_rect(center=rect.center)
        self.screen.blit(text_surf, text_rect)

    def _open_store(self) -> None:
        try:
            webbrowser.open(demo_config.DEMO_STEAM_STORE_URL, new=2)
        finally:
            self._close_with_action('confirm')

    @staticmethod
    def _wrap_text(font, text: str, max_width: int) -> list[str]:
        lines: list[str] = []
        for paragraph in str(text or '').split('\n'):
            words = paragraph.split()
            if not words:
                lines.append('')
                continue
            current = words[0]
            for word in words[1:]:
                candidate = f'{current} {word}'
                if font.size(candidate)[0] <= max_width:
                    current = candidate
                    continue
                lines.append(current)
                current = word
            lines.append(current)
        return lines


def show_demo_full_lock_prompt(prompt: DemoUpgradePrompt) -> None:
    prompt.show(
        title=t('demo_prompt_title', default='Demo Sınırı'),
        message=t('demo_full_lock_message', default='Bu mod tam sürümde mevcut.'),
        confirm_label=t('demo_open_steam', default="Steam'de Aç"),
        cancel_label=t('demo_close', default='Kapat'),
    )


def show_demo_partial_lock_prompt(prompt: DemoUpgradePrompt) -> None:
    prompt.show(
        title=t('demo_prompt_title', default='Demo Sınırı'),
        message=t(
            'demo_partial_lock_message',
            default='Demo bu bölümün yalnızca ilk aşamalarını içerir. Devamını tam sürümde oyna.',
        ),
        confirm_label=t('demo_open_steam', default="Steam'de Aç"),
        cancel_label=t('demo_close', default='Kapat'),
    )


def show_demo_transition_lock_prompt(prompt: DemoUpgradePrompt) -> None:
    prompt.show(
        title=t('demo_prompt_title', default='Demo Sınırı'),
        message=t('demo_transition_lock_message', default='Çevrimiçi modlar tam sürümde mevcut.'),
        confirm_label=t('demo_open_steam', default="Steam'de Aç"),
        cancel_label=t('demo_back_to_menu', default='Menüye Dön'),
    )


def show_demo_score_cap_prompt(prompt: DemoUpgradePrompt) -> None:
    prompt.show(
        title=t('demo_score_cap_title', default='Demo Tamamlandı'),
        message=t(
            'demo_score_cap_message',
            default='Oynadığınız için teşekkürler, daha fazlası için tam sürümü bekleyin.',
        ),
        confirm_label=t('demo_open_steam', default="Steam'de Aç"),
        cancel_label=t('demo_back_to_menu', default='Menüye Dön'),
    )