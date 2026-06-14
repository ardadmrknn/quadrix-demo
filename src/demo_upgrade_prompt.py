from __future__ import annotations

from dataclasses import dataclass
import webbrowser

import pygame

try:
    from . import demo_config
    from .localization import t
    from .platform_utils import get_mouse_pos, normalize_mouse_pos
    from .retro_style import retro_style
    from .ui_theme import UIColors, UIFonts
    from .ui_scaling import get_projected_effective_scale
except Exception:
    import demo_config
    from localization import t
    from platform_utils import get_mouse_pos, normalize_mouse_pos
    from retro_style import retro_style
    from ui_theme import UIColors, UIFonts
    from ui_scaling import get_projected_effective_scale


@dataclass(slots=True)
class _PromptLayout:
    panel_rect: pygame.Rect
    badge_rect: pygame.Rect
    title_rect: pygame.Rect
    body_rect: pygame.Rect
    footer_rect: pygame.Rect
    confirm_rect: pygame.Rect
    cancel_rect: pygame.Rect
    lines: list[str]
    line_height: int
    stack_buttons: bool


class DemoUpgradePrompt:
    def __init__(self, screen: pygame.Surface):
        self.screen = screen
        self.active = False
        self.eyebrow = ""
        self.title = ""
        self.message = ""
        self.confirm_label = ""
        self.cancel_label = ""
        self.accent_color = UIColors.NEON_CYAN
        self.confirm_rect: pygame.Rect | None = None
        self.cancel_rect: pygame.Rect | None = None
        self._last_action: str | None = None
        self._outside_click_closes = False
        self._pressed_action: str | None = None
        self._background_snapshot: pygame.Surface | None = None
        self._confirm_action = 'confirm'
        self._cancel_action = 'cancel'
        self._backdrop_dim: int | None = None

    def is_active(self) -> bool:
        return bool(self.active)

    def show(
        self,
        *,
        message: str,
        confirm_label: str,
        cancel_label: str,
        title: str | None = None,
        eyebrow: str | None = None,
        accent_color: tuple[int, int, int] | None = None,
        outside_click_closes: bool = False,
        confirm_action: str = 'confirm',
        cancel_action: str = 'cancel',
        backdrop_dim: int | None = None,
    ) -> None:
        self.active = True
        self.eyebrow = str(eyebrow or '')
        self.title = str(title or t('demo_prompt_title', default='Demo Sınırı'))
        self.message = str(message or '')
        self.confirm_label = str(confirm_label or '')
        self.cancel_label = str(cancel_label or '')
        self.accent_color = tuple(accent_color or UIColors.NEON_CYAN)
        self.confirm_rect = None
        self.cancel_rect = None
        self._last_action = None
        self._outside_click_closes = bool(outside_click_closes)
        self._pressed_action = None
        self._confirm_action = str(confirm_action or 'confirm')
        self._cancel_action = str(cancel_action or 'cancel')
        # Oyun-içi (ör. demo skor sınırı) bağlamlarda diğer paneller gibi
        # (duraklatma / çıkış onayı) tam-ekran koyu overlay istenir.
        # None bırakılırsa menü/ekstra kilit promptlarının hafif vinyet
        # görünümü korunur.
        if backdrop_dim is None:
            self._backdrop_dim = None
        else:
            self._backdrop_dim = max(0, min(255, int(backdrop_dim)))
        self._capture_background_snapshot()

    def hide(self) -> None:
        self.active = False
        self.confirm_rect = None
        self.cancel_rect = None
        self._pressed_action = None
        self._background_snapshot = None
        self._backdrop_dim = None

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
                self._close_with_action(self._cancel_action)
                return True
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                self._open_store()
                return True

        if event.type == pygame.MOUSEBUTTONDOWN and getattr(event, 'button', None) == 1:
            pos = normalize_mouse_pos(getattr(event, 'pos', None)) or get_mouse_pos()
            if self.confirm_rect and self.confirm_rect.collidepoint(pos):
                self._pressed_action = 'confirm'
                return True
            if self.cancel_rect and self.cancel_rect.collidepoint(pos):
                self._pressed_action = 'cancel'
                return True
            self._pressed_action = None
            if self._outside_click_closes:
                self._close_with_action(self._cancel_action)
            return True

        if event.type == pygame.MOUSEBUTTONUP and getattr(event, 'button', None) == 1:
            pos = normalize_mouse_pos(getattr(event, 'pos', None)) or get_mouse_pos()
            pressed_action = self._pressed_action
            self._pressed_action = None
            if pressed_action == 'confirm' and self.confirm_rect and self.confirm_rect.collidepoint(pos):
                self._open_store()
                return True
            if pressed_action == 'cancel' and self.cancel_rect and self.cancel_rect.collidepoint(pos):
                self._close_with_action(self._cancel_action)
                return True
            return True

        return True

    def draw(self) -> None:
        if not self.active:
            return

        self._blit_background_snapshot()

        width, height = self.screen.get_size()
        scale = get_projected_effective_scale(
            self.screen,
            min_scale=0.72,
            max_scale=1.18,
            reference_size=(1366.0, 768.0),
        )
        s = lambda value, minimum=1: max(minimum, int(round(value * scale)))

        panel_width = min(width - s(56), s(660))
        eyebrow_font = UIFonts.get(s(12, 8), bold=True)
        title_font = retro_style.get_fitting_font(
            self.title,
            s(30, 18),
            panel_width - s(108),
            bold=True,
            min_size=s(20, 12),
        )
        body_font = UIFonts.get(s(18, 11), bold=False)
        layout = self._build_layout(
            (width, height),
            scale,
            title_font,
            body_font,
            panel_width=panel_width,
            eyebrow_font=eyebrow_font,
        )

        self._draw_backdrop(layout, scale)

        retro_style.draw_glass_panel(
            self.screen,
            layout.panel_rect,
            alpha=208,
            border_color=self.accent_color,
            glow=True,
            top_highlight=False,
        )

        self._draw_panel_overlays(layout, scale)

        if self.eyebrow:
            self._draw_badge(layout.badge_rect, self.eyebrow, eyebrow_font, scale)

        title_glow = title_font.render(self.title, True, self.accent_color)
        title_glow.set_alpha(42)
        self.screen.blit(title_glow, title_glow.get_rect(center=(layout.title_rect.centerx, layout.title_rect.centery + s(2))))
        title_surf = title_font.render(self.title, True, UIColors.TEXT_PRIMARY)
        self.screen.blit(title_surf, layout.title_rect)

        text_y = layout.body_rect.y
        for line in layout.lines:
            line_surf = body_font.render(line, True, UIColors.TEXT_SECONDARY)
            line_rect = line_surf.get_rect(topleft=(layout.body_rect.x, text_y))
            self.screen.blit(line_surf, line_rect)
            text_y += layout.line_height

        self.confirm_rect = layout.confirm_rect
        self.cancel_rect = layout.cancel_rect

        cancel_hovered, cancel_pressed = self._get_pointer_state(self.cancel_rect, 'cancel')
        confirm_hovered, confirm_pressed = self._get_pointer_state(self.confirm_rect, 'confirm')

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

        self._draw_button(
            self.cancel_rect,
            self.cancel_label,
            cancel_font,
            primary=False,
            hovered=cancel_hovered,
            pressed=cancel_pressed,
            accent_color=self.accent_color,
            scale=scale,
        )
        self._draw_button(
            self.confirm_rect,
            self.confirm_label,
            confirm_font,
            primary=True,
            hovered=confirm_hovered,
            pressed=confirm_pressed,
            accent_color=self.accent_color,
            scale=scale,
        )

    def _build_layout(
        self,
        screen_size: tuple[int, int],
        scale: float,
        title_font,
        body_font,
        *,
        panel_width: int | None = None,
        eyebrow_font=None,
    ) -> _PromptLayout:
        width, height = screen_size
        s = lambda value, minimum=1: max(minimum, int(round(value * scale)))

        resolved_eyebrow_font = eyebrow_font or body_font
        resolved_panel_width = int(panel_width or min(width - s(56), s(660)))
        resolved_panel_width = max(s(340), min(resolved_panel_width, width - s(28)))

        inner_pad_x = s(28)
        content_width = max(s(200), resolved_panel_width - (inner_pad_x * 2))
        text_width = max(s(180), min(content_width, s(460)))
        lines = self._wrap_text(body_font, self.message, text_width)
        line_height = max(s(24), body_font.get_height() + s(8))

        footer_inner_width = max(s(220), resolved_panel_width - s(44))
        button_gap = s(12)
        button_height = s(48)
        confirm_label_width = body_font.size(self.confirm_label)[0]
        cancel_label_width = body_font.size(self.cancel_label)[0]
        min_button_content = max(confirm_label_width, cancel_label_width) + s(54)
        stacked_buttons = width < s(620) or footer_inner_width < (min_button_content * 2 + button_gap)

        if stacked_buttons:
            button_width = footer_inner_width
            buttons_height = button_height * 2 + button_gap
        else:
            button_width = max(s(156), (footer_inner_width - button_gap) // 2)
            buttons_height = button_height

        badge_height = 0
        if self.eyebrow:
            badge_height = resolved_eyebrow_font.get_height() + s(10)

        top_padding = s(22)
        title_top_gap = s(12) if badge_height else 0
        body_top_gap = s(18)
        footer_gap = s(24)
        footer_padding = s(18)
        panel_bottom_padding = s(18)
        footer_height = (footer_padding * 2) + buttons_height
        body_height = max(line_height, len(lines) * line_height)
        desired_panel_height = (
            top_padding
            + badge_height
            + title_top_gap
            + title_font.get_height()
            + body_top_gap
            + body_height
            + footer_gap
            + footer_height
            + panel_bottom_padding
        )
        max_panel_height = max(s(220), height - s(72))
        resolved_panel_height = min(max_panel_height, max(s(286), desired_panel_height))
        panel_rect = pygame.Rect(
            (width - resolved_panel_width) // 2,
            (height - resolved_panel_height) // 2,
            resolved_panel_width,
            resolved_panel_height,
        )

        badge_rect = pygame.Rect(panel_rect.x + inner_pad_x, panel_rect.y + top_padding, 0, 0)
        if self.eyebrow:
            badge_width = min(content_width, resolved_eyebrow_font.size(self.eyebrow)[0] + s(24))
            badge_rect = pygame.Rect(0, panel_rect.y + top_padding, badge_width, badge_height)
            badge_rect.centerx = panel_rect.centerx

        title_width = min(title_font.size(self.title)[0], content_width)
        title_rect = pygame.Rect(0, 0, max(1, title_width), title_font.get_height())
        title_y = panel_rect.y + top_padding
        if self.eyebrow:
            title_y = badge_rect.bottom + title_top_gap
        title_rect.midtop = (panel_rect.centerx, title_y)

        footer_rect = pygame.Rect(
            panel_rect.x + s(14),
            panel_rect.bottom - panel_bottom_padding - footer_height,
            panel_rect.width - s(28),
            footer_height,
        )

        body_top = title_rect.bottom + body_top_gap
        body_bottom_limit = footer_rect.top - footer_gap
        available_body_height = max(0, body_bottom_limit - body_top)
        visible_lines = self._fit_visible_lines(
            body_font,
            lines,
            text_width,
            line_height,
            available_body_height,
        )
        visible_body_height = len(visible_lines) * line_height

        body_rect = pygame.Rect(
            panel_rect.centerx - (text_width // 2),
            body_top,
            text_width,
            visible_body_height,
        )

        button_y = footer_rect.y + footer_padding
        button_left = footer_rect.x + s(8)
        button_right = footer_rect.right - s(8)

        if stacked_buttons:
            confirm_rect = pygame.Rect(button_left, button_y, button_width, button_height)
            cancel_rect = pygame.Rect(button_left, confirm_rect.bottom + button_gap, button_width, button_height)
        else:
            cancel_rect = pygame.Rect(button_left, button_y, button_width, button_height)
            confirm_rect = pygame.Rect(button_right - button_width, button_y, button_width, button_height)

        return _PromptLayout(
            panel_rect=panel_rect,
            badge_rect=badge_rect,
            title_rect=title_rect,
            body_rect=body_rect,
            footer_rect=footer_rect,
            confirm_rect=confirm_rect,
            cancel_rect=cancel_rect,
            lines=visible_lines,
            line_height=line_height,
            stack_buttons=stacked_buttons,
        )

    def _draw_backdrop(self, layout: _PromptLayout, scale: float) -> None:
        width, height = self.screen.get_size()
        s = lambda value, minimum=1: max(minimum, int(round(value * scale)))

        overlay = pygame.Surface((width, height), pygame.SRCALPHA)
        # Oyun-içi bağlamda (demo skor sınırı) diğer paneller gibi koyu,
        # opak bir overlay; menü/ekstra promptlarında hafif vinyet tonu.
        dim = getattr(self, '_backdrop_dim', None)
        if dim is not None:
            overlay.fill((0, 0, 0, dim))
        else:
            overlay.fill((6, 10, 22, 74))
        self.screen.blit(overlay, (0, 0))

        vignette = pygame.Surface((width, height), pygame.SRCALPHA)
        border_steps = (
            (0, s(24), 12),
            (s(16), s(16), 8),
        )
        for inset, border_width, alpha in border_steps:
            rect = pygame.Rect(inset, inset, width - (inset * 2), height - (inset * 2))
            if rect.width <= 0 or rect.height <= 0:
                continue
            pygame.draw.rect(
                vignette,
                (2, 4, 10, alpha),
                rect,
                width=min(border_width, max(1, rect.width // 2), max(1, rect.height // 2)),
                border_radius=s(30),
            )
        self.screen.blit(vignette, (0, 0))

        halo_rect = layout.panel_rect.inflate(s(60), s(68))
        halo_surf = pygame.Surface(halo_rect.size, pygame.SRCALPHA)
        pygame.draw.rect(halo_surf, (*self.accent_color, 6), halo_surf.get_rect(), border_radius=s(24))
        self.screen.blit(halo_surf, halo_rect.topleft)

    def _draw_panel_overlays(self, layout: _PromptLayout, scale: float) -> None:
        s = lambda value, minimum=1: max(minimum, int(round(value * scale)))

        accent_line = pygame.Surface((layout.panel_rect.width - s(64), s(4)), pygame.SRCALPHA)
        pygame.draw.rect(
            accent_line,
            (*self.accent_color, 150),
            accent_line.get_rect(),
            border_radius=s(4),
        )
        self.screen.blit(accent_line, (layout.panel_rect.x + s(32), layout.panel_rect.y + s(16)))

        footer_surf = pygame.Surface(layout.footer_rect.size, pygame.SRCALPHA)
        pygame.draw.rect(footer_surf, (7, 10, 18, 44), footer_surf.get_rect(), border_radius=s(16))
        pygame.draw.line(
            footer_surf,
            (*self.accent_color, 28),
            (s(16), s(1)),
            (layout.footer_rect.width - s(16), s(1)),
            1,
        )
        self.screen.blit(footer_surf, layout.footer_rect.topleft)

    def _get_pointer_state(self, rect: pygame.Rect, action: str) -> tuple[bool, bool]:
        try:
            mouse_pos = get_mouse_pos()
            hovered = bool(rect.collidepoint(mouse_pos))
            pressed = bool(hovered and self._pressed_action == action)
            return hovered, pressed
        except Exception:
            return False, False

    def _draw_badge(self, rect: pygame.Rect, label: str, font, scale: float) -> None:
        s = lambda value, minimum=1: max(minimum, int(round(value * scale)))

        badge_surf = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(badge_surf, (12, 18, 34, 192), badge_surf.get_rect(), border_radius=s(10))
        pygame.draw.rect(badge_surf, (*self.accent_color, 150), badge_surf.get_rect(), 1, border_radius=s(10))
        self.screen.blit(badge_surf, rect.topleft)

        text_surf = font.render(label, True, self.accent_color)
        text_rect = text_surf.get_rect(center=rect.center)
        self.screen.blit(text_surf, text_rect)

    def _draw_button(
        self,
        rect: pygame.Rect,
        label: str,
        font,
        *,
        primary: bool,
        hovered: bool,
        pressed: bool,
        accent_color: tuple[int, int, int],
        scale: float,
    ) -> None:
        s = lambda value, minimum=1: max(minimum, int(round(value * scale)))
        radius = s(12)
        button_rect = rect.move(0, s(2) if pressed else 0)
        border_color = accent_color if primary else (92, 104, 128)
        button_shadow_rect = rect.move(0, s(3) if not pressed else s(1))

        shadow_surf = pygame.Surface(button_shadow_rect.size, pygame.SRCALPHA)
        shadow_alpha = 40 if primary else 28
        if hovered:
            shadow_alpha += 8
        pygame.draw.rect(shadow_surf, (0, 0, 0, shadow_alpha), shadow_surf.get_rect(), border_radius=radius)
        self.screen.blit(shadow_surf, button_shadow_rect.topleft)

        if hovered or primary:
            glow_rect = button_rect.inflate(s(10), s(8))
            glow_surf = pygame.Surface(glow_rect.size, pygame.SRCALPHA)
            glow_alpha = 32 if primary else 10
            if hovered:
                glow_alpha += 12
            if pressed:
                glow_alpha += 8
            pygame.draw.rect(glow_surf, (*border_color, glow_alpha), glow_surf.get_rect(), border_radius=radius + s(6))
            self.screen.blit(glow_surf, glow_rect.topleft)

        retro_style.draw_glass_panel(
            self.screen,
            button_rect,
            alpha=186 if primary else 142,
            border_color=border_color,
            glow=primary,
            top_highlight=False,
        )

        overlay = pygame.Surface(button_rect.size, pygame.SRCALPHA)
        base_fill = (18, 30, 50, 208) if primary else (10, 14, 24, 138)
        if hovered:
            base_fill = (22, 36, 58, 220) if primary else (14, 20, 32, 154)
        if pressed:
            base_fill = (14, 23, 38, 226) if primary else (8, 11, 20, 166)
        pygame.draw.rect(overlay, base_fill, overlay.get_rect(), border_radius=radius)

        inner_rect = overlay.get_rect().inflate(-s(6), -s(6))
        inner_fill = (*accent_color, 92 if primary else 0)
        if hovered:
            inner_fill = (*accent_color, 112 if primary else 0)
        if pressed:
            inner_fill = (*accent_color, 124 if primary else 0)
        if primary:
            pygame.draw.rect(overlay, inner_fill, inner_rect, border_radius=max(s(8), radius - s(3)))
        else:
            pygame.draw.rect(overlay, (36, 44, 60, 84 if hovered else 62), inner_rect, border_radius=max(s(8), radius - s(3)))

        self.screen.blit(overlay, button_rect.topleft)

        inner_border_rect = button_rect.inflate(-s(6), -s(6))
        inner_border_color = (240, 247, 255) if primary else (156, 168, 192)
        inner_border_alpha = 128 if primary else 64
        if hovered:
            inner_border_alpha += 14
        if pressed:
            inner_border_alpha += 8
        inner_border_surf = pygame.Surface(inner_border_rect.size, pygame.SRCALPHA)
        pygame.draw.rect(
            inner_border_surf,
            (*inner_border_color, inner_border_alpha),
            inner_border_surf.get_rect(),
            1,
            border_radius=max(s(8), radius - s(3)),
        )
        self.screen.blit(inner_border_surf, inner_border_rect.topleft)

        if primary:
            outer_edge = pygame.Surface(button_rect.size, pygame.SRCALPHA)
            pygame.draw.rect(
                outer_edge,
                (255, 255, 255, 28 if hovered else 20),
                outer_edge.get_rect(),
                1,
                border_radius=radius,
            )
            self.screen.blit(outer_edge, button_rect.topleft)

        accent_rect = pygame.Rect(button_rect.x + s(12), button_rect.bottom - s(8), button_rect.width - s(24), s(4 if primary else 3))
        accent_band_color = border_color if primary else (122, 136, 162)
        if hovered and not primary:
            accent_band_color = (146, 160, 186)
        pygame.draw.rect(self.screen, accent_band_color, accent_rect, border_radius=s(3))

        text_color = UIColors.TEXT_PRIMARY if primary or hovered else UIColors.TEXT_SECONDARY
        text_shadow = font.render(label, True, (0, 0, 0))
        text_shadow.set_alpha(120)
        text_shadow_rect = text_shadow.get_rect(center=(button_rect.centerx, button_rect.centery + s(2)))
        self.screen.blit(text_shadow, text_shadow_rect)

        text_surf = font.render(label, True, text_color)
        text_rect = text_surf.get_rect(center=(button_rect.centerx, button_rect.centery - (s(1) if not pressed else s(0))))
        self.screen.blit(text_surf, text_rect)

    def _capture_background_snapshot(self) -> None:
        try:
            self._background_snapshot = self.screen.copy()
        except Exception:
            self._background_snapshot = None

    def _blit_background_snapshot(self) -> None:
        snapshot = self._background_snapshot
        if snapshot is None:
            return

        try:
            target_size = self.screen.get_size()
            source_size = snapshot.get_size()
        except Exception:
            return

        draw_snapshot = snapshot
        if source_size != target_size:
            try:
                draw_snapshot = pygame.transform.smoothscale(snapshot, target_size)
            except Exception:
                try:
                    draw_snapshot = pygame.transform.scale(snapshot, target_size)
                except Exception:
                    draw_snapshot = snapshot

        try:
            self.screen.blit(draw_snapshot, (0, 0))
        except Exception:
            pass

    def _open_store(self) -> None:
        try:
            webbrowser.open(demo_config.DEMO_STEAM_STORE_URL, new=2)
        finally:
            self._close_with_action(self._confirm_action)

    @staticmethod
    def _wrap_text(font, text: str, max_width: int) -> list[str]:
        lines: list[str] = []
        for paragraph in str(text or '').split('\n'):
            if not paragraph:
                lines.append('')
                continue
            lines.extend(DemoUpgradePrompt._wrap_paragraph(font, paragraph, max_width))
        return lines

    @staticmethod
    def _wrap_paragraph(font, paragraph: str, max_width: int) -> list[str]:
        if not paragraph:
            return ['']

        wrapped_lines: list[str] = []
        current = ''
        pending_space = False

        for token in paragraph.split():
            token_chunks = DemoUpgradePrompt._split_token_to_fit(font, token, max_width)
            for index, chunk in enumerate(token_chunks):
                prefix = ' ' if pending_space and current and index == 0 else ''
                candidate = f'{current}{prefix}{chunk}' if current else chunk
                if current and font.size(candidate)[0] <= max_width:
                    current = candidate
                else:
                    if current:
                        wrapped_lines.append(current)
                    current = chunk
                pending_space = index == len(token_chunks) - 1

        if current:
            wrapped_lines.append(current)

        if wrapped_lines:
            return wrapped_lines

        return DemoUpgradePrompt._split_token_to_fit(font, paragraph, max_width)

    @staticmethod
    def _split_token_to_fit(font, token: str, max_width: int) -> list[str]:
        token = str(token or '')
        if not token:
            return ['']
        if font.size(token)[0] <= max_width:
            return [token]

        chunks: list[str] = []
        current = ''
        for character in token:
            candidate = f'{current}{character}'
            if current and font.size(candidate)[0] > max_width:
                chunks.append(current)
                current = character
                continue
            current = candidate

        if current:
            chunks.append(current)
        return chunks or [token]

    @staticmethod
    def _fit_visible_lines(font, lines: list[str], max_width: int, line_height: int, max_height: int) -> list[str]:
        if not lines:
            return []

        line_capacity = max(0, max_height // max(1, line_height))
        if line_capacity <= 0:
            return []
        if len(lines) <= line_capacity:
            return list(lines)

        visible_lines = list(lines[:line_capacity])
        visible_lines[-1] = DemoUpgradePrompt._ellipsize_to_width(font, visible_lines[-1], max_width)
        return visible_lines

    @staticmethod
    def _ellipsize_to_width(font, text: str, max_width: int) -> str:
        suffix = '...'
        base = str(text or '').rstrip()
        if font.size(base + suffix)[0] <= max_width:
            return base + suffix
        while base and font.size(base + suffix)[0] > max_width:
            base = base[:-1].rstrip()
        if base:
            return base + suffix
        if font.size(suffix)[0] <= max_width:
            return suffix
        fitted = DemoUpgradePrompt._split_token_to_fit(font, suffix, max_width)
        return fitted[0] if fitted else ''


def show_demo_full_lock_prompt(prompt: DemoUpgradePrompt) -> None:
    prompt.show(
        eyebrow=t('locked_badge', default='Kilitli'),
        title=t('demo_prompt_title', default='Demo Sınırı'),
        message=t('demo_full_lock_message', default='Bu mod tam sürümde mevcut.'),
        confirm_label=t('demo_open_steam', default="Steam'de Aç"),
        cancel_label=t('demo_close', default='Kapat'),
        accent_color=UIColors.NEON_GOLD,
    )


def show_demo_store_lock_prompt(prompt: DemoUpgradePrompt) -> None:
    prompt.show(
        eyebrow=t('locked_badge', default='Kilitli'),
        title=t('demo_prompt_title', default='Demo Sınırı'),
        message=t(
            'demo_store_lock_message',
            default='Magaza vitrini ve satin alma akisi tam surumde acilir.',
        ),
        confirm_label=t('demo_open_steam', default="Steam'de Aç"),
        cancel_label=t('demo_back_to_menu', default='Menuye Don'),
        accent_color=UIColors.NEON_GOLD,
        cancel_action='menu_back',
    )


def show_demo_partial_lock_prompt(prompt: DemoUpgradePrompt) -> None:
    prompt.show(
        eyebrow=t('locked_badge', default='Kilitli'),
        title=t('demo_prompt_title', default='Demo Sınırı'),
        message=t(
            'demo_partial_lock_message',
            default='Demo bu bölümün yalnızca ilk aşamalarını içerir. Devamını tam sürümde oyna.',
        ),
        confirm_label=t('demo_open_steam', default="Steam'de Aç"),
        cancel_label=t('demo_close', default='Kapat'),
        accent_color=UIColors.NEON_CYAN,
    )


def show_demo_transition_lock_prompt(prompt: DemoUpgradePrompt) -> None:
    prompt.show(
        eyebrow=t('locked_badge', default='Kilitli'),
        title=t('demo_prompt_title', default='Demo Sınırı'),
        message=t('demo_transition_lock_message', default='Çevrimiçi modlar tam sürümde mevcut.'),
        confirm_label=t('demo_open_steam', default="Steam'de Aç"),
        cancel_label=t('demo_back_to_menu', default='Menüye Dön'),
        accent_color=UIColors.NEON_CYAN,
        cancel_action='menu_back',
    )


def show_demo_score_cap_prompt(prompt: DemoUpgradePrompt) -> None:
    prompt.show(
        eyebrow=t('demo_prompt_title', default='Demo Sınırı'),
        title=t('demo_score_cap_title', default='Demo Tamamlandı'),
        message=t(
            'demo_score_cap_message',
            default='Oynadığınız için teşekkürler, daha fazlası için tam sürümü bekleyin.',
        ),
        confirm_label=t('demo_open_steam', default="Steam'de Aç"),
        cancel_label=t('demo_back_to_menu', default='Menüye Dön'),
        accent_color=UIColors.NEON_GOLD,
        # Oyun-içi panel: duraklatma/çıkış onayı gibi tam-ekran koyu overlay.
        backdrop_dim=185,
    )
