from __future__ import annotations

from dataclasses import dataclass

import pygame

try:
    from .asset_manager import load_image  # type: ignore
    from .localization import t  # type: ignore
    from .platform_utils import normalize_mouse_pos  # type: ignore
    from .retro_style import retro_style  # type: ignore
    from .ui_scaling import get_projected_effective_scale  # type: ignore
except Exception:
    from asset_manager import load_image
    from localization import t
    from platform_utils import normalize_mouse_pos
    from retro_style import retro_style
    from ui_scaling import get_projected_effective_scale


@dataclass(frozen=True)
class StoreProduct:
    product_id: str
    title_key: str
    desc_key: str
    category_key: str
    badge_key: str
    status_key: str
    price: int
    accent: tuple[int, int, int]
    icon_path: str | None = None


CATALOG: tuple[StoreProduct, ...] = (
    StoreProduct(
        product_id='luna_tail_pack',
        title_key='store_product_luna_tail_pack_title',
        desc_key='store_product_luna_tail_pack_desc',
        category_key='store_category_tail',
        badge_key='store_badge_demo',
        status_key='store_status_demo',
        price=900,
        accent=(255, 176, 92),
        icon_path='assets/test_icon/luna_leaderboard_icon.png',
    ),
)


class StoreScreen:
    def __init__(self, screen, user_manager=None, settings_manager=None):
        self.screen = screen
        self.user_manager = user_manager
        self.settings_manager = settings_manager
        self.products = list(CATALOG)
        self.selected_index = 0
        self.card_rects: list[pygame.Rect] = []
        self.mouse_pos = (0, 0)
        self.status_message = t(
            'store_preview_notice',
            default='Su an yalnizca 1 demo urun gosteriliyor. Satin alma akisi daha sonra acilacak.',
        )

    def get_product_ids(self) -> list[str]:
        return [product.product_id for product in self.products]

    def get_selected_product(self) -> StoreProduct:
        return self.products[self.selected_index]

    def get_fragment_balance(self) -> int:
        if self.user_manager is None:
            return 0

        getter = getattr(self.user_manager, 'get_user_data', None)
        try:
            profile = getter() if callable(getter) else None
        except Exception:
            profile = None

        if isinstance(profile, dict):
            try:
                return int(profile.get('neural_fragments', 0) or 0)
            except Exception:
                return 0
        return 0

    def handle_input(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
                return 'back'
            if event.key == pygame.K_LEFT:
                self._move_selection(-1, 0)
            elif event.key == pygame.K_RIGHT:
                self._move_selection(1, 0)
            elif event.key == pygame.K_UP:
                self._move_selection(0, -1)
            elif event.key == pygame.K_DOWN:
                self._move_selection(0, 1)
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                self._preview_selected_product()
        elif event.type == pygame.MOUSEMOTION:
            self.mouse_pos = normalize_mouse_pos(getattr(event, 'pos', None)) or event.pos
            self._sync_hover_selection(self.mouse_pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = normalize_mouse_pos(getattr(event, 'pos', None)) or event.pos
            if self._sync_hover_selection(pos):
                self._preview_selected_product()
        elif event.type == pygame.MOUSEWHEEL:
            if event.y > 0:
                self._move_selection(-1, 0)
            elif event.y < 0:
                self._move_selection(1, 0)
        return None

    def draw(self):
        width, height = self.screen.get_size()
        scale = self._ui_scale()
        spacing = self._px(18, scale)
        margin = self._px(34, scale)

        retro_style.draw_background(self.screen)

        title_font = retro_style.get_font(self._px(42, scale), bold=True)
        subtitle_font = retro_style.get_font(self._px(18, scale))
        section_font = retro_style.get_font(self._px(22, scale), bold=True)
        body_font = retro_style.get_font(self._px(18, scale))
        small_font = retro_style.get_font(self._px(15, scale))

        outer_rect = pygame.Rect(margin, margin, width - margin * 2, height - margin * 2)
        header_rect = pygame.Rect(outer_rect.x, outer_rect.y, outer_rect.width, self._px(120, scale))
        footer_rect = pygame.Rect(
            outer_rect.x,
            outer_rect.bottom - self._px(86, scale),
            outer_rect.width,
            self._px(86, scale),
        )
        product_rect = pygame.Rect(
            outer_rect.x,
            header_rect.bottom + spacing,
            outer_rect.width,
            footer_rect.top - header_rect.bottom - spacing * 2,
        )

        self._draw_header(header_rect, title_font, subtitle_font, body_font, small_font, spacing)
        self._draw_product_panel(product_rect, self.get_selected_product(), section_font, body_font, small_font, spacing)
        self._draw_footer(footer_rect, body_font, small_font, spacing)

    def _ui_scale(self) -> float:
        return get_projected_effective_scale(
            self.screen,
            min_scale=0.74,
            max_scale=1.08,
            reference_size=(1920.0, 1080.0),
        )

    def _px(self, value: int, scale: float) -> int:
        return max(1, int(round(value * scale)))

    def _move_selection(self, dx: int, dy: int) -> None:
        if not self.products:
            self.selected_index = 0
            return
        self.selected_index = max(0, min(len(self.products) - 1, self.selected_index + dx + dy))

    def _sync_hover_selection(self, pos) -> bool:
        for index, rect in enumerate(self.card_rects):
            if rect.collidepoint(pos):
                self.selected_index = index
                return True
        return False

    def _preview_selected_product(self) -> None:
        selected = self.get_selected_product()
        self.status_message = t(
            'store_preview_selected',
            default='{name} vitrinde secildi. Harcama ve sahiplik akisi sonraki fazda acilacak.',
            name=t(selected.title_key),
        )

    def _get_current_profile_name(self) -> str:
        if self.user_manager is None:
            return t('store_profile_guest', default='Misafir')
        getter = getattr(self.user_manager, 'get_current_user', None)
        try:
            current_user = getter() if callable(getter) else getattr(self.user_manager, 'current_user', None)
        except Exception:
            current_user = None
        if current_user:
            return str(current_user)
        return t('store_profile_guest', default='Misafir')

    def _draw_header(self, rect, title_font, subtitle_font, body_font, small_font, spacing: int) -> None:
        retro_style.draw_glass_panel(
            self.screen,
            rect,
            alpha=170,
            border_color=(*retro_style.primary, 170),
        )
        inner = rect.inflate(-spacing * 2, -spacing * 2)
        right_w = min(self._px(320, self._ui_scale()), max(self._px(250, self._ui_scale()), inner.width // 3))

        info_rect = pygame.Rect(inner.right - right_w, inner.y, right_w, inner.height)
        text_rect = pygame.Rect(inner.x, inner.y, max(120, info_rect.x - inner.x - spacing), inner.height)

        title_surf = title_font.render(t('store_title', default='Magaza'), True, retro_style.accent)
        self.screen.blit(title_surf, (text_rect.x, text_rect.y - 2))

        subtitle_rect = pygame.Rect(
            text_rect.x,
            text_rect.y + title_surf.get_height() + self._px(4, self._ui_scale()),
            text_rect.width,
            text_rect.height - title_surf.get_height(),
        )
        retro_style.draw_wrapped_text(
            self.screen,
            t('store_subtitle', default='Magaza ilk surumde. Su an tek bir demo urun gosteriliyor.'),
            subtitle_font,
            (220, 230, 245),
            subtitle_rect,
            align='left',
            line_spacing=self._px(4, self._ui_scale()),
        )

        profile_label = t('store_profile_label', default='Profil')
        profile_name = self._get_current_profile_name()
        profile_surf = body_font.render(f'{profile_label}: {profile_name}', True, (245, 248, 255))
        profile_rect = profile_surf.get_rect(topright=(info_rect.right, info_rect.y))
        self.screen.blit(profile_surf, profile_rect)

        wallet_surf = body_font.render(
            t(
                'store_wallet_balance',
                default='{currency}: {amount}',
                currency=t('store_currency_name', default='Neural Fragment'),
                amount=self.get_fragment_balance(),
            ),
            True,
            (255, 234, 166),
        )
        wallet_rect = wallet_surf.get_rect(topright=(info_rect.right, profile_rect.bottom + self._px(8, self._ui_scale())))
        self.screen.blit(wallet_surf, wallet_rect)

        hint_rect = pygame.Rect(info_rect.x, wallet_rect.bottom + self._px(8, self._ui_scale()), info_rect.width, max(10, info_rect.bottom - wallet_rect.bottom))
        retro_style.draw_wrapped_text(
            self.screen,
            t('store_wallet_preview', default='Kart Ustaligi ve Gunluk Gorev odulleri burada birikir.'),
            small_font,
            (176, 190, 215),
            hint_rect,
            align='right',
            line_spacing=self._px(3, self._ui_scale()),
        )

    def _draw_product_panel(self, rect, product, title_font, body_font, small_font, spacing: int) -> None:
        retro_style.draw_glass_panel(
            self.screen,
            rect,
            alpha=155,
            border_color=(*product.accent, 160),
        )
        inner = rect.inflate(-spacing * 2, -spacing * 2)
        self.card_rects = [rect]
        stacked = inner.width < self._px(920, self._ui_scale())

        if stacked:
            preview_rect = pygame.Rect(inner.x, inner.y, inner.width, min(inner.height // 2, self._px(250, self._ui_scale())))
            detail_rect = pygame.Rect(inner.x, preview_rect.bottom + spacing, inner.width, inner.bottom - preview_rect.bottom - spacing)
        else:
            preview_w = min(self._px(430, self._ui_scale()), max(self._px(300, self._ui_scale()), int(inner.width * 0.42)))
            preview_rect = pygame.Rect(inner.x, inner.y, preview_w, inner.height)
            detail_rect = pygame.Rect(preview_rect.right + spacing, inner.y, inner.right - preview_rect.right - spacing, inner.height)

        self._draw_product_preview(product, preview_rect)

        chip_rect = self._draw_chip(detail_rect.x, detail_rect.y, t(product.badge_key), small_font, product.accent, spacing)
        name_y = chip_rect.bottom + self._px(12, self._ui_scale())
        title_surf = title_font.render(t(product.title_key), True, (247, 249, 255))
        self.screen.blit(title_surf, (detail_rect.x, name_y))

        meta_y = name_y + title_surf.get_height() + self._px(12, self._ui_scale())
        meta_lines = (
            (t(product.category_key), (208, 220, 244)),
            (f"{t('store_price_label', default='Fiyat')}: {product.price} {t('store_currency_name', default='Neural Fragment')}", (255, 234, 166)),
            (f"{t('store_status_label', default='Durum')}: {t(product.status_key)}", (172, 245, 196)),
        )
        for text, color in meta_lines:
            row_surf = body_font.render(text, True, color)
            self.screen.blit(row_surf, (detail_rect.x, meta_y))
            meta_y += row_surf.get_height() + self._px(8, self._ui_scale())

        desc_rect = pygame.Rect(
            detail_rect.x,
            meta_y + self._px(6, self._ui_scale()),
            detail_rect.width,
            max(10, detail_rect.bottom - meta_y - self._px(42, self._ui_scale())),
        )
        retro_style.draw_wrapped_text(
            self.screen,
            t(product.desc_key),
            body_font,
            (232, 238, 250),
            desc_rect,
            align='left',
            line_spacing=self._px(5, self._ui_scale()),
        )

    def _draw_footer(self, rect, body_font, small_font, spacing: int) -> None:
        retro_style.draw_glass_panel(
            self.screen,
            rect,
            alpha=150,
            border_color=(78, 98, 132, 150),
        )
        inner = rect.inflate(-spacing * 2, -spacing * 2)
        controls_surf = small_font.render(
            t('store_controls', default='ESC geri  |  ENTER bilgi notu'),
            True,
            (176, 192, 220),
        )
        self.screen.blit(controls_surf, (inner.x, inner.y))

        status_rect = pygame.Rect(inner.x, inner.y + controls_surf.get_height() + self._px(8, self._ui_scale()), inner.width, inner.height)
        retro_style.draw_wrapped_text(
            self.screen,
            self.status_message,
            body_font,
            (240, 246, 255),
            status_rect,
            align='left',
            line_spacing=self._px(4, self._ui_scale()),
        )

    def _draw_chip(self, x: int, y: int, label: str, font, color: tuple[int, int, int], spacing: int) -> pygame.Rect:
        text_surf = font.render(label, True, color)
        pad_x = max(8, spacing // 2)
        pad_y = max(4, spacing // 4)
        rect = pygame.Rect(x, y, text_surf.get_width() + pad_x * 2, text_surf.get_height() + pad_y * 2)
        retro_style.draw_glass_panel(self.screen, rect, alpha=122, border_color=(*color, 145))
        self.screen.blit(text_surf, (rect.x + pad_x, rect.y + pad_y))
        return rect

    def _draw_product_preview(self, product, rect) -> None:
        preview = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(preview, (*product.accent, 20), preview.get_rect(), border_radius=18)
        pygame.draw.rect(preview, (*product.accent, 120), preview.get_rect(), 2, border_radius=18)

        ring_rect = preview.get_rect().inflate(-self._px(34, self._ui_scale()), -self._px(34, self._ui_scale()))
        if ring_rect.width > 12 and ring_rect.height > 12:
            pygame.draw.ellipse(preview, (*product.accent, 36), ring_rect)
            pygame.draw.ellipse(preview, (*product.accent, 105), ring_rect, 2)

        if product.icon_path:
            icon_size = max(42, int(min(rect.width, rect.height) * 0.46))
            try:
                icon = load_image(product.icon_path, convert_alpha=True, size=(icon_size, icon_size))
            except Exception:
                icon = None
            if icon is not None:
                icon_rect = icon.get_rect(center=(rect.width // 2, rect.height // 2))
                preview.blit(icon, icon_rect)

        self.screen.blit(preview, rect.topleft)