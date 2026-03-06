"""Kullanıcı seçim ve yönetim ekranları"""
import pygame
import os
import io
import random
import re
import threading
from datetime import datetime
from constants import *
from avatar_editor import AvatarEditor
from retro_style import retro_style
from background_effects import get_shared_falling_blocks_layer
from ui_theme import UIColors, UIFonts
from asset_manager import load_image
from text_cache import render_text
from avatar_presets import get_avatar_entries, resolve_avatar_value
from pieces import create_piece_by_name
from renderers.jelly_renderer import draw_jelly_block
from platform_utils import normalize_mouse_pos, get_mouse_pos
from localization import t, get_language
from steam_leaderboards import SteamLeaderboardService

_AVATAR_EXTS = ('.png', '.jpg', '.jpeg', '.webp', '.bmp')


def _darken_rgb(color: tuple[int, int, int], factor: float) -> tuple[int, int, int]:
    factor = max(0.0, min(1.0, float(factor)))
    r, g, b = color
    return (int(r * factor), int(g * factor), int(b * factor))


def _circle_crop_surface(src: pygame.Surface | None, diameter: int) -> pygame.Surface:
    """Görüntüyü dairesel keser. En-boy oranını korur (center-crop)."""
    diameter = max(8, int(diameter))
    out = pygame.Surface((diameter, diameter), pygame.SRCALPHA)
    if src is None:
        return out
    src_w, src_h = src.get_size()
    # En-boy oranını koru: kısa kenar diameter olacak şekilde ölçekle
    scale = diameter / min(src_w, src_h) if min(src_w, src_h) > 0 else 1.0
    scaled_w = max(diameter, int(src_w * scale))
    scaled_h = max(diameter, int(src_h * scale))
    img = pygame.transform.smoothscale(src.convert_alpha(), (scaled_w, scaled_h))
    # Ortadan kes
    crop_x = (scaled_w - diameter) // 2
    crop_y = (scaled_h - diameter) // 2
    crop_rect = pygame.Rect(crop_x, crop_y, diameter, diameter)
    cropped = pygame.Surface((diameter, diameter), pygame.SRCALPHA)
    cropped.blit(img, (0, 0), area=crop_rect)
    # Daire maskesi uygula
    mask = pygame.Surface((diameter, diameter), pygame.SRCALPHA)
    pygame.draw.circle(mask, (255, 255, 255, 255), (diameter // 2, diameter // 2), diameter // 2)
    cropped.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    out.blit(cropped, (0, 0))
    return out


def _render_placeholder_avatar(size: int) -> pygame.Surface:
    size = max(16, int(size))
    s = pygame.Surface((size, size), pygame.SRCALPHA)
    bg = (18, 24, 44, 220)
    fg = (235, 240, 250, 220)
    pygame.draw.circle(s, bg, (size // 2, size // 2), size // 2)
    head_r = max(3, int(size * 0.16))
    pygame.draw.circle(s, fg, (size // 2, int(size * 0.42)), head_r)
    body_w = int(size * 0.46)
    body_h = int(size * 0.28)
    body_rect = pygame.Rect(0, 0, body_w, body_h)
    body_rect.center = (size // 2, int(size * 0.68))
    pygame.draw.ellipse(s, fg, body_rect)
    return s


def _load_avatar_image(avatar_value, size: int) -> pygame.Surface | None:
    resolved_value = resolve_avatar_value(avatar_value)
    path_value = resolved_value if isinstance(resolved_value, str) else None
    if not path_value or not path_value.lower().endswith(_AVATAR_EXTS):
        return None
    if not os.path.exists(path_value):
        return None
    try:
        image = load_image(path_value, convert_alpha=True)
        return pygame.transform.smoothscale(image, (size, size))
    except Exception:
        return None

class UserSelectionScreen:
    """Kullanıcı seçim ekranı"""
    
    def __init__(self, screen, user_manager):
        """Kullanıcı seçim ekranını başlat"""
        self.screen = screen
        self.user_manager = user_manager
        self._ui_reference_size = self._get_ui_reference_size()
        self._ui_readable_min_size = (1180, 760)
        self._ui_scale_current = 1.0
        # Tipografi ölçeği (tema tutarlılığı)
        # H1: 56 (retro_style.draw_title içinde), alt başlık: 20-22, bölüm/label: 18
        self._base_font_title_size = 56
        self._base_font_normal_size = 30
        self._base_font_small_size = 20
        self._base_font_label_size = 18
        self.font_title_size = self._base_font_title_size
        self.font_normal_size = self._base_font_normal_size
        self.font_small_size = self._base_font_small_size
        self.font_label_size = self._base_font_label_size
        self._font_scale_signature = None
        self.font_title = retro_style.get_font(self.font_title_size)
        self.font_normal = retro_style.get_font(self.font_normal_size)
        self.font_small = retro_style.get_font(self.font_small_size, bold=False)
        self.font_label = retro_style.get_font(self.font_label_size, bold=False)
        
        self.selected_user = 0
        self.users_list = list(user_manager.get_all_users().keys())
        self.state = 'select'  # select, create_new, edit_existing, avatar_editor
        
        self.new_username = ''
        self.avatar_entries = get_avatar_entries()
        base_presets = [entry.get('value') for entry in self.avatar_entries if entry.get('value')]
        self.avatars = list(base_presets) if base_presets else ['__default__']
        self.selected_avatar = self.avatars[0]
        self.avatar_index = 0
        self.error_message = ''
        self.error_timer = 0
        
        self.avatar_editor = AvatarEditor(screen)
        self.custom_avatar_path = None
        
        self.scroll_offset = 0
        self.visible_limit = 5
        self.card_targets = []
        self.cursor_timer = 0
        self.cursor_visible = True
        self.avatar_cache = {}
        self._piece_preview_cache = {}
        self.last_click_time = 0
        self.last_click_index = None
        
        self._create_button_rect = None
        self._cancel_button_rect = None
        self._custom_avatar_button_rect = None
        self._avatar_left_rect = None
        self._avatar_right_rect = None
        self._profile_edit_button_rect = None
        self._profile_delete_button_rect = None
        self._confirm_yes_rect = None
        self._confirm_no_rect = None
        self._pending_delete_username = None

        # Silme güvenliği: aynı ekranda 2-adım onay (modal yok)
        self._delete_armed_username = None

        # Menüyle aynı shared katman: ekran geçişlerinde animasyon kesilmesin.
        self.background_fx = get_shared_falling_blocks_layer('default')
        self._delete_armed_until_ms = 0

        # Hover/focus
        self._hovered_index = None

        # Form odak yönetimi (TAB ergonomisi)
        # 0: avatar, 1: kullanıcı adı, 2: birincil buton, 3: geri
        self._form_focus = 0
        self._input_rect = None

        # Hafif panel geçiş animasyonu
        self._transition_start_ms = 0
        self._transition_duration_ms = 200
        self._transition_active = False

        # Username validasyon
        self._validation_message = ''
        self._validation_suggestion = ''
        self._username_allowed_re = re.compile(r"^[\w\- ]+$", re.UNICODE)
        self.form_mode = 'create'  # create or edit
        self.edit_target_username = None
        self._avatar_editor_return_state = 'create_new'

        # Avatar arka plan renk seçimi
        self.avatar_colors = [
            (100, 150, 255),  # Mavi
            (255, 100, 100),  # Kırmızı
            (100, 220, 100),  # Yeşil
            (255, 220, 80),   # Sarı
            (255, 100, 220),  # Pembe
            (80, 230, 230),   # Cyan
            (255, 160, 80),   # Turuncu
            (190, 90, 255),   # Mor
        ]
        self.selected_color_index = 0
        self._avatar_color_rects = []

        # Steam avatar (aktif Steam kullanıcısı) cache
        self._steam_current_sid = ''
        self._steam_avatar_url = ''
        self._steam_avatar_bytes: bytes | None = None
        self._steam_avatar_surface_cache: dict[int, pygame.Surface] = {}
        self._steam_avatar_loading = False
        self._steam_avatar_fetch_attempted = False
        self._steam_profile_service = SteamLeaderboardService(
            backend_base_url=os.getenv('LEADERBOARD_BACKEND_URL', ''),
            publisher_key=os.getenv('STEAM_WEB_API_KEY', ''),
            app_id=int(os.getenv('STEAM_APP_ID', '0') or '0'),
            timeout_seconds=3.0,
        )
        self._ensure_steam_avatar_async()

    def _get_ui_reference_size(self) -> tuple[int, int]:
        try:
            info = pygame.display.Info()
            ref_w = int(getattr(info, 'current_w', 0) or 0)
            ref_h = int(getattr(info, 'current_h', 0) or 0)
        except Exception:
            ref_w, ref_h = 0, 0

        if ref_w <= 0 or ref_h <= 0:
            ref_w, ref_h = self.screen.get_size()
        return max(1, ref_w), max(1, ref_h)

    def _ui_scale(self, min_scale: float = 0.62, max_scale: float = 1.0) -> float:
        try:
            w, h = self.screen.get_size()
            w = max(1, int(w))
            h = max(1, int(h))
            ref_w, ref_h = self._ui_reference_size
            ratio = min(float(w) / max(1.0, float(ref_w)), float(h) / max(1.0, float(ref_h)))

            rw, rh = self._ui_readable_min_size
            readable_floor = min(1.0, min(float(w) / max(1.0, float(rw)), float(h) / max(1.0, float(rh))))
            effective_min = max(min_scale, readable_floor)
            return max(effective_min, min(max_scale, ratio))
        except Exception:
            return 1.0

    def _sx(self, value: int | float, minimum: int = 1) -> int:
        return max(minimum, int(round(float(value) * float(self._ui_scale_current))))

    def _apply_responsive_metrics(self) -> None:
        self._ui_scale_current = self._ui_scale(min_scale=0.62, max_scale=1.0)

        title_size = max(28, self._sx(self._base_font_title_size, minimum=28))
        normal_size = max(16, self._sx(self._base_font_normal_size, minimum=16))
        small_size = max(12, self._sx(self._base_font_small_size, minimum=12))
        label_size = max(11, self._sx(self._base_font_label_size, minimum=11))
        signature = (title_size, normal_size, small_size, label_size)
        if signature == self._font_scale_signature:
            return

        self.font_title_size = title_size
        self.font_normal_size = normal_size
        self.font_small_size = small_size
        self.font_label_size = label_size
        self.font_title = retro_style.get_font(self.font_title_size)
        self.font_normal = retro_style.get_font(self.font_normal_size)
        self.font_small = retro_style.get_font(self.font_small_size, bold=False)
        self.font_label = retro_style.get_font(self.font_label_size, bold=False)
        self._font_scale_signature = signature

    def _start_transition(self):
        self._transition_start_ms = pygame.time.get_ticks()
        self._transition_active = True

    def _draw_h1_title(self, text: str, center: tuple[int, int]) -> None:
        """Turkuaz metin yerine beyaz H1 + cyan glow (okunurluk)."""
        s = self._sx
        width, _ = self.screen.get_size()
        max_width = max(0, width - s(120))
        font = retro_style.get_fitting_font(text, self.font_title_size, max_width, bold=True)
        # Glow/underline (cyan) için mevcut draw_title'ı kullan
        retro_style.draw_title(self.screen, text, center)
        # Üstüne sert kontrast: gölge + beyaz metin
        shadow = render_text(font, text, True, (0, 0, 0))
        shadow.set_alpha(180)
        self.screen.blit(shadow, shadow.get_rect(center=(center[0] + s(2), center[1] + s(2))))
        title_surface = render_text(font, text, True, WHITE)
        self.screen.blit(title_surface, title_surface.get_rect(center=center))

    def _get_most_held_piece_name(self, user_data: dict) -> str | None:
        counts = user_data.get('hold_piece_counts')
        if not isinstance(counts, dict) or not counts:
            return None
        try:
            return max(counts.items(), key=lambda kv: int(kv[1] or 0))[0]
        except Exception:
            return None

    def _get_most_held_piece(self, user_data: dict) -> tuple[str, int] | tuple[None, int]:
        counts = user_data.get('hold_piece_counts')
        if not isinstance(counts, dict) or not counts:
            return (None, 0)
        best_name: str | None = None
        best_count = 0
        for k, v in counts.items():
            try:
                iv = int(v or 0)
            except Exception:
                iv = 0
            if best_name is None or iv > best_count:
                best_name = str(k)
                best_count = iv
        return (best_name, best_count)

    def _render_piece_preview(self, piece_name: str | None, size: int) -> pygame.Surface:
        size = max(28, int(size))
        key = (piece_name or '', size)
        cached = self._piece_preview_cache.get(key)
        if cached is not None:
            return cached
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        if not piece_name:
            self._piece_preview_cache[key] = surf
            return surf
        try:
            piece = create_piece_by_name(piece_name, x=0, y=0)
        except Exception:
            self._piece_preview_cache[key] = surf
            return surf
        shape = getattr(piece, 'shape', None)
        color = getattr(piece, 'color', (200, 200, 220))
        if not shape:
            self._piece_preview_cache[key] = surf
            return surf
        rows = len(shape)
        cols = max((len(r) for r in shape), default=0)
        if rows <= 0 or cols <= 0:
            self._piece_preview_cache[key] = surf
            return surf

        pad = 6
        cell = max(4, min((size - pad * 2) // max(cols, 1), (size - pad * 2) // max(rows, 1)))
        occ = [(x, y) for y, row in enumerate(shape) for x, v in enumerate(row) if v]
        if not occ:
            self._piece_preview_cache[key] = surf
            return surf
        min_x = min(x for x, _ in occ)
        max_x = max(x for x, _ in occ)
        min_y = min(y for _, y in occ)
        max_y = max(y for _, y in occ)
        bw = (max_x - min_x + 1) * cell
        bh = (max_y - min_y + 1) * cell
        ox = (size - bw) // 2
        oy = (size - bh) // 2

        # Oyun içindeki varsayılan blok görünümüyle aynı: shared jelly renderer
        base_color = (int(color[0]), int(color[1]), int(color[2]))
        for x, y in occ:
            rx = ox + (x - min_x) * cell
            ry = oy + (y - min_y) * cell
            draw_jelly_block(surf, int(rx), int(ry), int(cell), base_color)

        self._piece_preview_cache[key] = surf
        return surf

    def _draw_most_held_panel(self, rect: pygame.Rect, user_data: dict, username: str | None = None) -> None:
        s = self._sx
        retro_style.draw_panel(self.screen, rect, t('user_most_held_piece_title'), title_color=retro_style.text_primary)
        piece_name, hold_count = self._get_most_held_piece(user_data)

        favorite_card = None
        try:
            if username:
                favorite_card = self.user_manager.get_favorite_card(username)
            else:
                favorite_card = self.user_manager.get_favorite_card()
        except Exception:
            favorite_card = None

        # İçerik alanı (başlığın altı)
        content = pygame.Rect(rect.x + s(24), rect.y + s(52), rect.width - s(48), rect.height - s(72))
        box_size = min(s(200), content.height, max(s(78), int(content.width * 0.34)))
        box_size = max(s(78), int(box_size))
        box_rect = pygame.Rect(content.x, 0, box_size, box_size)
        box_rect.centery = content.centery
        pygame.draw.rect(self.screen, (12, 14, 36), box_rect, border_radius=s(14))
        pygame.draw.rect(self.screen, (*retro_style.primary, 200), box_rect, 2, border_radius=14)

        if not piece_name:
            msg = self.font_small.render(t('user_no_storage_data'), True, (190, 200, 220))
            self.screen.blit(msg, msg.get_rect(midleft=(box_rect.right + s(22), content.centery)))
            return

        preview = self._render_piece_preview(piece_name, box_size - s(16))
        self.screen.blit(preview, preview.get_rect(center=box_rect.center))

        info_x = box_rect.right + s(22)
        info_w = max(10, content.right - info_x)
        name_surface = retro_style.render_fit_text(
            t('user_piece_label', piece=piece_name),
            WHITE,
            info_w,
            self.font_small_size,
            bold=True,
            min_size=14,
        )
        count_surface = retro_style.render_fit_text(
            t('user_held_count_label', count=f"{hold_count:,}".replace(',', '.')),
            (190, 200, 220),
            info_w,
            self.font_small_size,
            bold=False,
            min_size=14,
        )
        total_h = name_surface.get_height() + s(10) + count_surface.get_height()
        top = content.centery - total_h // 2
        self.screen.blit(name_surface, (info_x, top))
        self.screen.blit(count_surface, (info_x, top + name_surface.get_height() + s(10)))

        # Favori kart mini bilgisi (Kullanıcı Değiştir ekranında favori blok bölümünün yanında)
        fav_title = str((favorite_card or {}).get('title', '') or (favorite_card or {}).get('id', '')).strip()
        fav_count = int((favorite_card or {}).get('count', 0) or 0)
        if info_w >= s(210):
            card_w = min(max(s(160), int(info_w * 0.52)), info_w)
            card_h = min(s(86), max(s(64), int(content.height * 0.48)))
            card_x = content.right - card_w
            card_y = content.centery - card_h // 2
            fav_rect = pygame.Rect(card_x, card_y, card_w, card_h)

            fav_bg = pygame.Surface(fav_rect.size, pygame.SRCALPHA)
            pygame.draw.rect(fav_bg, (14, 18, 34, 185), fav_bg.get_rect(), border_radius=s(11))
            pygame.draw.rect(fav_bg, (*retro_style.secondary, 200), pygame.Rect(0, s(5), s(4), fav_rect.height - s(10)), border_radius=s(2))
            pygame.draw.rect(fav_bg, (*retro_style.secondary, 90), fav_bg.get_rect(), 1, border_radius=s(11))
            self.screen.blit(fav_bg, fav_rect.topleft)

            lang = get_language()
            fav_header = 'Favori Kart' if lang == 'tr' else 'Favorite Card'
            hdr_surf = retro_style.render_fit_text(
                fav_header,
                (*retro_style.secondary, 220),
                fav_rect.width - s(16),
                self.font_label_size,
                bold=True,
                min_size=12,
            )
            self.screen.blit(hdr_surf, (fav_rect.x + s(10), fav_rect.y + s(8)))

            if fav_title:
                name_text = f"⭐ {fav_title}"
                name_surf2 = retro_style.render_fit_text(
                    name_text,
                    WHITE,
                    fav_rect.width - s(18),
                    self.font_small_size,
                    bold=True,
                    min_size=12,
                )
                self.screen.blit(name_surf2, (fav_rect.x + s(10), fav_rect.y + s(30)))

                count_text = f"× {fav_count}" if fav_count > 0 else ''
                if count_text:
                    count_surf2 = retro_style.render_fit_text(
                        count_text,
                        (190, 200, 220),
                        fav_rect.width - s(18),
                        self.font_small_size,
                        bold=False,
                        min_size=12,
                    )
                    self.screen.blit(count_surf2, count_surf2.get_rect(bottomright=(fav_rect.right - s(10), fav_rect.bottom - s(8))))
            else:
                empty_text = 'Henüz kart verisi yok' if lang == 'tr' else 'No card data yet'
                empty_surf = retro_style.render_fit_text(
                    empty_text,
                    (175, 188, 214),
                    fav_rect.width - s(18),
                    self.font_small_size,
                    bold=False,
                    min_size=12,
                )
                self.screen.blit(empty_surf, empty_surf.get_rect(midleft=(fav_rect.x + s(10), fav_rect.centery + s(8))))

    def _clear_delete_arm(self):
        self._delete_armed_username = None
        self._delete_armed_until_ms = 0

    def _is_delete_armed(self, username: str | None) -> bool:
        if not username:
            return False
        now = pygame.time.get_ticks()
        return self._delete_armed_username == username and now <= self._delete_armed_until_ms

    def _arm_delete(self, username: str):
        self._delete_armed_username = username
        self._delete_armed_until_ms = pygame.time.get_ticks() + 2000

    def _normalize_username(self, raw: str) -> str:
        # İçeriği bozmayalım: sadece kenar boşluklarını temizle.
        return (raw or '').strip()

    def _suggest_username(self, base: str) -> str:
        """Çakışmada otomatik öneri (örn. ARDA2)."""
        base = self._normalize_username(base)
        if not base:
            return ''
        existing = {u.casefold() for u in self.user_manager.get_all_users().keys()}
        if base.casefold() not in existing:
            return base
        for i in range(2, 1000):
            candidate = f"{base}{i}"
            if candidate.casefold() not in existing and len(candidate) <= 20:
                return candidate
        return ''

    def _validate_username_live(self) -> bool:
        """Anlık validasyon: tek satır net mesaj + (varsa) öneri."""
        self._validation_message = ''
        self._validation_suggestion = ''
        if self.form_mode == 'edit':
            return True
        raw = self.new_username or ''
        if raw != raw.rstrip():
            self._validation_message = t('user_validation_trailing_space')
            return False
        name = self._normalize_username(raw)
        if not name:
            self._validation_message = t('user_validation_empty')
            return False
        if len(name) < 2:
            self._validation_message = t('user_validation_too_short')
            return False
        if len(name) > 20:
            self._validation_message = t('user_validation_too_long')
            return False
        if not self._username_allowed_re.match(name):
            self._validation_message = t('user_validation_invalid_chars')
            return False
        existing = {u.casefold() for u in self.user_manager.get_all_users().keys()}
        if name.casefold() in existing:
            self._validation_message = t('user_validation_exists')
            suggestion = self._suggest_username(name)
            if suggestion and suggestion.casefold() != name.casefold():
                self._validation_suggestion = t('user_validation_suggestion', suggestion=suggestion)
            return False
        return True

    def _total_entries(self):
        return len(self.users_list) + 1  # + Yeni kullanıcı kartı

    def _is_add_index(self, index):
        return index == 0

    def _can_edit_selected(self):
        return self.users_list and not self._is_add_index(self.selected_user)

    def get_selected_username(self):
        if self._can_edit_selected():
            return self.users_list[self.selected_user - 1]
        return None

    def _is_username_editable(self):
        return self.form_mode == 'create'

    def _ensure_visible(self):
        total = self._total_entries()
        if total <= self.visible_limit:
            self.scroll_offset = 0
            return
        if self.selected_user < self.scroll_offset:
            self.scroll_offset = self.selected_user
        elif self.selected_user >= self.scroll_offset + self.visible_limit:
            self.scroll_offset = self.selected_user - self.visible_limit + 1
        max_scroll = max(0, total - self.visible_limit)
        self.scroll_offset = max(0, min(self.scroll_offset, max_scroll))

    def _reset_create_form(self):
        self.new_username = ''
        self.selected_avatar = self.avatars[0] if self.avatars else '__default__'
        self.avatar_index = 0
        self.custom_avatar_path = None
        self.error_message = ''
        self.error_timer = 0
        self._validation_message = ''
        self._validation_suggestion = ''
        self._invalidate_avatar_cache()
        self.form_mode = 'create'
        self.edit_target_username = None
        self._avatar_editor_return_state = 'create_new'
        self._form_focus = 0
        self.selected_color_index = 0

    def _begin_create_flow(self):
        self._reset_create_form()
        self.state = 'create_new'
        self._start_transition()

    def _begin_edit_existing(self, username):
        if username in self.users_list:
            self.selected_user = self.users_list.index(username)
        user_data = self.user_manager.get_user_data(username) or {}
        self.form_mode = 'edit'
        self.edit_target_username = username
        self.new_username = username
        avatar_value = user_data.get('avatar')
        self.custom_avatar_path = None
        if avatar_value in self.avatars:
            self.avatar_index = self.avatars.index(avatar_value)
            self.selected_avatar = avatar_value
        elif isinstance(avatar_value, str) and avatar_value.startswith('preset:') and avatar_value in self.avatars:
            self.avatar_index = self.avatars.index(avatar_value)
            self.selected_avatar = avatar_value
        elif isinstance(avatar_value, str) and os.path.exists(avatar_value):
            self.custom_avatar_path = avatar_value
            self.selected_avatar = self.avatars[self.avatar_index] if self.avatars else '__default__'
        else:
            self.avatar_index = 0
            self.selected_avatar = self.avatars[0] if self.avatars else '__default__'
        self.state = 'edit_existing'
        self.error_message = ''
        self.error_timer = 0
        self._validation_message = ''
        self._validation_suggestion = ''
        self._invalidate_avatar_cache()
        self._avatar_editor_return_state = 'edit_existing'
        self._ensure_visible()
        self._form_focus = 1
        self._start_transition()
        # Kaydedilmiş rengi yükle
        saved_color = user_data.get('avatar_color', (100, 150, 255))
        try:
            self.selected_color_index = self.avatar_colors.index(tuple(saved_color))
        except (ValueError, TypeError):
            self.selected_color_index = 0

    def _launch_avatar_editor(self):
        self._avatar_editor_return_state = self.state if self.state in ('create_new', 'edit_existing') else 'create_new'
        self.state = 'avatar_editor'
        self.avatar_editor.open_file_dialog()
        self._start_transition()

    def _invalidate_avatar_cache(self):
        self.avatar_cache.clear()

    def _ensure_steam_avatar_async(self):
        if self._steam_avatar_bytes is not None or self._steam_avatar_loading:
            return
        if self._steam_avatar_fetch_attempted:
            return
        try:
            import steam_integration as _si
            if not _si.is_available():
                return
            steam_id = str(_si.get_steam_id_str() or '').strip()
        except Exception:
            return
        if not steam_id:
            return

        self._steam_current_sid = steam_id
        if not self._steam_profile_service.is_configured():
            self._steam_avatar_fetch_attempted = True
            return
        self._steam_avatar_loading = True
        self._steam_avatar_fetch_attempted = True

        def _worker():
            try:
                if not self._steam_profile_service.is_configured():
                    return
                summaries = self._steam_profile_service.fetch_player_summaries([steam_id]) or {}
                info = summaries.get(steam_id, {})
                url = str(info.get('avatarmedium') or info.get('avatar') or '').strip()
                if not url:
                    return
                try:
                    import requests as _req
                    resp = _req.get(url, timeout=3)
                    if resp.status_code == 200 and resp.content:
                        self._steam_avatar_url = url
                        self._steam_avatar_bytes = resp.content
                        self._steam_avatar_surface_cache.clear()
                except Exception:
                    pass
            finally:
                self._steam_avatar_loading = False

        threading.Thread(target=_worker, daemon=True).start()

    def _get_steam_avatar_surface(self, size: int) -> pygame.Surface | None:
        self._ensure_steam_avatar_async()
        size = max(16, int(size))

        # 1) HTTP ile indirilen avatar
        if not self._steam_avatar_bytes:
            # 2) Steam SDK avatar fallback
            try:
                import steam_integration as _si
                avatar_rgba = _si.get_avatar_rgba(preferred='medium')
                if avatar_rgba:
                    aw, ah, argba = avatar_rgba
                    source = pygame.image.frombuffer(bytearray(argba), (aw, ah), 'RGBA').convert_alpha()
                    scaled = pygame.transform.smoothscale(source, (size, size))
                    return _circle_crop_surface(scaled, size)
            except Exception:
                pass
            return None

        cached = self._steam_avatar_surface_cache.get(size)
        if cached is not None:
            return cached
        try:
            loaded = pygame.image.load(io.BytesIO(self._steam_avatar_bytes)).convert_alpha()
            scaled = pygame.transform.smoothscale(loaded, (size, size))
            circle = _circle_crop_surface(scaled, size)
            self._steam_avatar_surface_cache[size] = circle
            return circle
        except Exception:
            return None

    def _should_use_steam_avatar_for_user(self, user_data: dict, is_active: bool) -> bool:
        if not self._steam_current_sid:
            return False
        # is_active olmak tek başına Steam avatarı göstermek için yeterli değil;
        # kullanıcının steam_id'si mevcut Steam oturumuyla eşleşmelidir.
        linked_sid = str(user_data.get('steam_id', '') or '').strip()
        return bool(linked_sid and linked_sid == self._steam_current_sid)

    def _get_avatar_surface(self, avatar_value, size):
        cache_key = (avatar_value or '__none__', size)
        cached = self.avatar_cache.get(cache_key)
        if cached:
            return cached
        size = max(16, int(size))
        image = _load_avatar_image(avatar_value, size)
        if image is None:
            image = _render_placeholder_avatar(size)
        surface = _circle_crop_surface(image, size)
        self.avatar_cache[cache_key] = surface
        return surface

    def _format_playtime(self, seconds):
        seconds = int(seconds or 0)
        minutes = seconds // 60
        hours = minutes // 60
        if hours:
            return f'{hours}sa {minutes % 60}dk'
        if minutes:
            return f'{minutes}dk {seconds % 60}sn'
        return f'{seconds}sn'

    def handle_input(self, event):
        """Girdi işle"""
        if self.state == 'select':
            return self._handle_select_input(event)
        elif self.state in ('create_new', 'edit_existing'):
            return self._handle_form_input(event)
        elif self.state == 'avatar_editor':
            return self._handle_avatar_editor_input(event)

    def _handle_select_input(self, event):
        """Kullanıcı seçim girdisi"""
        total_items = self._total_entries()
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_UP:
                self.selected_user = (self.selected_user - 1) % total_items
                self._ensure_visible()
            elif event.key == pygame.K_DOWN:
                self.selected_user = (self.selected_user + 1) % total_items
                self._ensure_visible()
            elif event.key == pygame.K_RETURN:
                if self._is_add_index(self.selected_user):
                    self._begin_create_flow()
                elif self._can_edit_selected():
                    username = self.get_selected_username()
                    self._begin_edit_existing(username)
            elif event.key == pygame.K_SPACE:
                if self._is_add_index(self.selected_user):
                    self._begin_create_flow()
                elif self._can_edit_selected():
                    username = self.get_selected_username()
                    self.user_manager.select_user(username)
                    return 'user_selected'
            elif event.key == pygame.K_n:
                self._begin_create_flow()
            elif event.key in (pygame.K_e, pygame.K_F2):
                if self._can_edit_selected():
                    username = self.get_selected_username()
                    self._begin_edit_existing(username)
            elif getattr(event, 'unicode', '') and event.unicode.lower() == 'e':
                if self._can_edit_selected():
                    username = self.get_selected_username()
                    self._begin_edit_existing(username)
            elif event.key == pygame.K_ESCAPE:
                self._clear_delete_arm()
                return 'back_to_menu'
            elif event.key == pygame.K_DELETE:
                if self._can_edit_selected():
                    username = self.get_selected_username()
                    if self._is_delete_armed(username):
                        self._perform_delete_selected()
                    else:
                        self._arm_delete(username)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mouse_pos = normalize_mouse_pos(getattr(event, 'pos', None)) or event.pos
            for target in self.card_targets:
                if target['rect'].collidepoint(mouse_pos):
                    index = target['index']
                    if target.get('type') == 'select_btn':
                        # index=0 add, so users start at 1? No, draw loop uses enumerate on list.
                        # Wait, list starts with __add__ now.
                        # If index > 0 it is a user.
                        if index > 0:
                            username = self.users_list[index - 1]
                            self.user_manager.select_user(username)
                            return 'user_selected'

                    if target['type'] == 'add':
                        self.selected_user = index
                        self._ensure_visible()
                        self._begin_create_flow()
                        return None
                    
                    double_click = (
                        self.last_click_index == index and
                        pygame.time.get_ticks() - self.last_click_time < 350
                    )
                    self.selected_user = index
                    self._ensure_visible()
                    self._clear_delete_arm()
                    if double_click and not self._is_add_index(index):
                        username = self.users_list[index - 1]
                        self._begin_edit_existing(username)
                        return None
                    self.last_click_index = index
                    self.last_click_time = pygame.time.get_ticks()
                    break
            if self._profile_edit_button_rect and self._profile_edit_button_rect.collidepoint(mouse_pos):
                if self._can_edit_selected():
                    username = self.get_selected_username()
                    self._begin_edit_existing(username)
            elif self._profile_delete_button_rect and self._profile_delete_button_rect.collidepoint(mouse_pos):
                if self._can_edit_selected():
                    username = self.get_selected_username()
                    if self._is_delete_armed(username):
                        self._perform_delete_selected()
                    else:
                        self._arm_delete(username)
        elif event.type == pygame.MOUSEWHEEL:
            self.scroll_offset -= event.y
            max_scroll = max(0, total_items - self.visible_limit)
            self.scroll_offset = max(0, min(self.scroll_offset, max_scroll))
        return None

    def _perform_delete_selected(self):
        username = self.get_selected_username() or self._delete_armed_username
        if not username:
            return
        success, _ = self.user_manager.delete_user(username)
        self._clear_delete_arm()
        if not success:
            return
        self.users_list = list(self.user_manager.get_all_users().keys())
        if self.users_list:
            self.selected_user = min(self.selected_user, len(self.users_list) - 1)
        else:
            self.selected_user = 0
        self._ensure_visible()

    def _handle_form_input(self, event):
        """Yeni kullanıcı oluşturma veya mevcut kullanıcıyı düzenleme girdisi"""
        is_edit_mode = self.form_mode == 'edit'
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.state = 'select'
                self.error_message = ''
                self._validation_message = ''
                self._validation_suggestion = ''
                self._clear_delete_arm()
                if is_edit_mode:
                    self._reset_create_form()
                self._start_transition()
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                # Odak butonlardaysa Enter ile tetikle
                if self._form_focus in (2, 3):
                    if self._form_focus == 3:
                        self.state = 'select'
                        self.error_message = ''
                        self._validation_message = ''
                        self._validation_suggestion = ''
                        if is_edit_mode:
                            self._reset_create_form()
                        self._start_transition()
                        return None
                return self._attempt_update_user() if is_edit_mode else self._attempt_create_user()
            elif event.key == pygame.K_BACKSPACE:
                if self._is_username_editable() and self._form_focus == 1:
                    self.new_username = self.new_username[:-1]
                    self._validate_username_live()
            elif event.key == pygame.K_LEFT:
                if self._form_focus == 0:
                    step = 10 if (getattr(event, 'mod', 0) & pygame.KMOD_SHIFT) else 1
                    self.avatar_index = (self.avatar_index - step) % len(self.avatars)
                    self.selected_avatar = self.avatars[self.avatar_index]
                    self.custom_avatar_path = None
                    self._invalidate_avatar_cache()
            elif event.key == pygame.K_RIGHT:
                if self._form_focus == 0:
                    step = 10 if (getattr(event, 'mod', 0) & pygame.KMOD_SHIFT) else 1
                    self.avatar_index = (self.avatar_index + step) % len(self.avatars)
                    self.selected_avatar = self.avatars[self.avatar_index]
                    self.custom_avatar_path = None
                    self._invalidate_avatar_cache()
            elif event.key == pygame.K_TAB:
                # TAB: avatar ↔ isim ↔ butonlar
                reverse = bool(getattr(event, 'mod', 0) & pygame.KMOD_SHIFT)
                order = [0, 1, 2, 3]
                idx = order.index(self._form_focus) if self._form_focus in order else 0
                idx = (idx - 1) % len(order) if reverse else (idx + 1) % len(order)
                self._form_focus = order[idx]
            elif event.key == pygame.K_r and self._form_focus == 0:
                # Hızlı avatar: rastgele (sadece avatar alanı odaktayken)
                if self.avatars:
                    self.avatar_index = random.randrange(len(self.avatars))
                    self.selected_avatar = self.avatars[self.avatar_index]
                    self.custom_avatar_path = None
                    self._invalidate_avatar_cache()
            else:
                if (
                    self._is_username_editable() and
                    self._form_focus == 1 and
                    event.unicode and
                    event.unicode.isprintable() and
                    len(self.new_username) < 20
                ):
                    self.new_username += event.unicode
                    self._validate_username_live()
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = normalize_mouse_pos(getattr(event, 'pos', None)) or event.pos
            if self._input_rect and self._input_rect.collidepoint(pos):
                self._form_focus = 1
            if self._avatar_left_rect and self._avatar_left_rect.collidepoint(pos):
                self._form_focus = 0
                self.avatar_index = (self.avatar_index - 1) % len(self.avatars)
                self.selected_avatar = self.avatars[self.avatar_index]
                self.custom_avatar_path = None
                self._invalidate_avatar_cache()
            elif self._avatar_right_rect and self._avatar_right_rect.collidepoint(pos):
                self._form_focus = 0
                self.avatar_index = (self.avatar_index + 1) % len(self.avatars)
                self.selected_avatar = self.avatars[self.avatar_index]
                self.custom_avatar_path = None
                self._invalidate_avatar_cache()
            elif self._custom_avatar_button_rect and self._custom_avatar_button_rect.collidepoint(pos):
                self._form_focus = 0
                self._launch_avatar_editor()
            else:
                # Renk paleti dairelerine tıklama
                for i, dot_rect in enumerate(self._avatar_color_rects):
                    if dot_rect.collidepoint(pos):
                        self.selected_color_index = i
                        self._form_focus = 0
                        break
            if self._create_button_rect and self._create_button_rect.collidepoint(pos):
                self._form_focus = 2
                return self._attempt_update_user() if is_edit_mode else self._attempt_create_user()
            elif self._cancel_button_rect and self._cancel_button_rect.collidepoint(pos):
                self._form_focus = 3
                self.state = 'select'
                self.error_message = ''
                self._validation_message = ''
                self._validation_suggestion = ''
                if is_edit_mode:
                    self._reset_create_form()
                self._start_transition()
        return None

    def _attempt_create_user(self):
        """Kullanıcı oluşturmayı dener"""
        # Anlık validasyon mesajını öncele
        if not self._validate_username_live():
            # UI'da tek satır gösterelim; create_user mesajı yerine burayı kullanalım.
            self.error_message = self._validation_message
            self.error_timer = 180
            # Öneri varsa mesajı küçük alanda ayrıca göstereceğiz
            return None

        username = self._normalize_username(self.new_username)
        avatar = self.custom_avatar_path if self.custom_avatar_path else self.selected_avatar
        success, message = self.user_manager.create_user(username, avatar)
        if success:
            # Seçilen arka plan rengini kaydet
            self.user_manager.update_user_profile(
                username, avatar_color=self.avatar_colors[self.selected_color_index])
            self.users_list = list(self.user_manager.get_all_users().keys())
            self.selected_user = len(self.users_list) - 1 if self.users_list else 0
            self.user_manager.select_user(username)
            self.state = 'select'
            self._ensure_visible()
            self._reset_create_form()
            self._start_transition()
            return 'new_user_created'
        else:
            self.error_message = message
            self.error_timer = 180
        return None

    def _attempt_update_user(self):
        if not self.edit_target_username:
            self.state = 'select'
            return None
        avatar = self.custom_avatar_path if self.custom_avatar_path else self.selected_avatar
        success, message = self.user_manager.update_user_profile(
            self.edit_target_username,
            avatar=avatar,
            avatar_color=self.avatar_colors[self.selected_color_index]
        )
        if success:
            self.users_list = list(self.user_manager.get_all_users().keys())
            if self.edit_target_username in self.users_list:
                self.selected_user = self.users_list.index(self.edit_target_username)
            self.user_manager.select_user(self.edit_target_username)
            self.state = 'select'
            self.form_mode = 'create'
            self.edit_target_username = None
            self._ensure_visible()
            self._reset_create_form()
            self._start_transition()
            return 'user_selected'
        else:
            self.error_message = message
            self.error_timer = 180
        return None

    def _handle_avatar_editor_input(self, event):
        """Avatar editör girdisi"""
        result = self.avatar_editor.handle_event(event)
        return_state = self._avatar_editor_return_state or 'create_new'
        if result == 'save':
            target_name = self.new_username or 'temp'
            filepath = self.avatar_editor.save_avatar(target_name)
            if filepath:
                self.custom_avatar_path = filepath
                self.state = return_state
                self._invalidate_avatar_cache()
                self._avatar_editor_return_state = 'create_new'
        elif result == 'cancel':
            self.state = return_state
            self._avatar_editor_return_state = 'create_new'
        return None

    def update(self):
        """Güncelle"""
        if self.error_timer > 0:
            self.error_timer -= 1
            if self.error_timer == 0:
                self.error_message = ''
        self.cursor_timer += 1
        if self.cursor_timer >= 30:
            self.cursor_visible = not self.cursor_visible
            self.cursor_timer = 0
        if self._delete_armed_until_ms and pygame.time.get_ticks() > self._delete_armed_until_ms:
            self._clear_delete_arm()
        total_entries = self._total_entries()
        if total_entries > 0:
            self.selected_user = max(0, min(self.selected_user, total_entries - 1))
        self._ensure_visible()

    def draw(self):
        """Ekranı çiz"""
        self._ensure_steam_avatar_async()
        # Hafif geçiş (fade + küçük slide)
        if self.state == 'avatar_editor':
            self.avatar_editor.draw()
            return

        now = pygame.time.get_ticks()
        if self._transition_active:
            elapsed = now - self._transition_start_ms
            if elapsed >= self._transition_duration_ms:
                self._transition_active = False
            else:
                t = max(0.0, min(1.0, elapsed / max(1, self._transition_duration_ms)))
                alpha = int(255 * t)
                y_off = int((1.0 - t) * 10)
                original = self.screen
                temp = pygame.Surface(original.get_size(), pygame.SRCALPHA)
                self.screen = temp
                if self.state == 'select':
                    self._draw_select_screen()
                elif self.state in ('create_new', 'edit_existing'):
                    self._draw_form_screen()
                self.screen = original
                temp.set_alpha(alpha)
                original.blit(temp, (0, y_off))
                return

        if self.state == 'select':
            self._draw_select_screen()
        elif self.state in ('create_new', 'edit_existing'):
            self._draw_form_screen()

    def _draw_user_card(self, rect, username, user_data, selected, is_active, index):
        s = self._sx
        radius = 14
        border_w = 2
        hovered = (self._hovered_index == index)
        card_surface = pygame.Surface(rect.size, pygame.SRCALPHA)
        card_surface.fill((18, 22, 44, 230) if selected else (12, 14, 30, 210))
        self.screen.blit(card_surface, rect.topleft)

        if selected:
            glow_rect = rect.inflate(s(12), s(12))
            glow = pygame.Surface(glow_rect.size, pygame.SRCALPHA)
            pygame.draw.rect(glow, (*retro_style.primary, 34), glow.get_rect(), border_radius=radius + 4)
            self.screen.blit(glow, glow_rect.topleft)
        elif hovered:
            glow_rect = rect.inflate(s(10), s(10))
            glow = pygame.Surface(glow_rect.size, pygame.SRCALPHA)
            pygame.draw.rect(glow, (*retro_style.primary, 26), glow.get_rect(), border_radius=radius + 4)
            self.screen.blit(glow, glow_rect.topleft)

        border_color = retro_style.primary if (selected or hovered) else (60, 70, 110)
        pygame.draw.rect(self.screen, border_color, rect, border_w, border_radius=radius)

        # Grid hizası: avatar, isim, stats tek çizgide sabit
        avatar_size = s(64)
        avatar_rect = pygame.Rect(rect.x + s(16), rect.y + (rect.height - avatar_size) // 2, avatar_size, avatar_size)
        avatar_color = user_data.get('avatar_color', (100, 150, 255))
        pygame.draw.circle(self.screen, avatar_color, avatar_rect.center, avatar_size // 2)
        pygame.draw.circle(self.screen, (255, 255, 255), avatar_rect.center, avatar_size // 2, s(2))
        avatar_surface = None
        if self._should_use_steam_avatar_for_user(user_data, is_active):
            avatar_surface = self._get_steam_avatar_surface(avatar_size - s(2))
        if avatar_surface is None:
            avatar_surface = self._get_avatar_surface(user_data.get('avatar', '__default__'), avatar_size - s(2))
        self.screen.blit(avatar_surface, avatar_surface.get_rect(center=avatar_rect.center))
        
        name_color = WHITE
        name_x = avatar_rect.right + s(16)
        name_y = rect.y + s(14)
        max_name_w = max(s(40), rect.right - name_x - s(140))
        name_surface = retro_style.render_fit_text(username, name_color, max_name_w, self.font_normal_size)
        self.screen.blit(name_surface, (name_x, name_y))
        
        stats_text = f"{user_data.get('total_games', 0)} oyun  •  {user_data.get('total_score', 0):,} puan".replace(',', '.')
        stats_surface = self.font_small.render(stats_text, True, (190, 200, 230))
        stats_surface.set_alpha(235)
        self.screen.blit(stats_surface, (name_x, rect.y + s(50)))

        # Steam profili bağlıysa küçük rozet göster
        if user_data.get('steam_id'):
            steam_surf = self.font_small.render('• Steam', True, (100, 170, 255))
            steam_surf.set_alpha(210)
            self.screen.blit(steam_surf, (name_x + stats_surface.get_width() + s(10), rect.y + s(50)))
        
        if is_active:
            chip_rect = pygame.Rect(rect.right - s(120), rect.y + s(16), s(100), s(28))
            pygame.draw.rect(self.screen, _darken_rgb(retro_style.success, 0.55), chip_rect, border_radius=14)
            pygame.draw.rect(self.screen, (255, 255, 255, 40), chip_rect, 1, border_radius=14)
            chip_text = self.font_small.render(t('user_active'), True, WHITE)
            self.screen.blit(chip_text, chip_text.get_rect(center=chip_rect.center))
        else:
            # "Geç" (Select) button
            btn_rect = pygame.Rect(rect.right - s(120), rect.bottom - s(44), s(100), s(28))
            # Check hover for visual feedback
            m_pos = get_mouse_pos()
            is_btn_hover = btn_rect.collidepoint(m_pos)
            
            btn_color = retro_style.accent if is_btn_hover else _darken_rgb(retro_style.accent, 0.2)
            pygame.draw.rect(self.screen, btn_color, btn_rect, border_radius=14)
            pygame.draw.rect(self.screen, (255, 255, 255, 40), btn_rect, 1, border_radius=14)
            
            btn_text = self.font_small.render(t('button_switch'), True, (20, 20, 20) if is_btn_hover else WHITE)
            self.screen.blit(btn_text, btn_text.get_rect(center=btn_rect.center))
            
            # Add button target BEFORE the card target so it captures the click first
            self.card_targets.append({'rect': btn_rect, 'index': index, 'type': 'select_btn'})
        
        self.card_targets.append({'rect': rect, 'index': index, 'type': 'user'})

    def _draw_add_card(self, rect, selected, index):
        s = self._sx
        radius = 14
        border_w = 2
        hovered = (self._hovered_index == index)
        card_surface = pygame.Surface(rect.size, pygame.SRCALPHA)
        card_surface.fill((20, 44, 44, 220) if selected else (12, 26, 26, 210))
        self.screen.blit(card_surface, rect.topleft)

        accent = retro_style.accent
        if selected:
            glow_rect = rect.inflate(s(12), s(12))
            glow = pygame.Surface(glow_rect.size, pygame.SRCALPHA)
            pygame.draw.rect(glow, (*accent, 30), glow.get_rect(), border_radius=radius + 4)
            self.screen.blit(glow, glow_rect.topleft)
        elif hovered:
            glow_rect = rect.inflate(s(10), s(10))
            glow = pygame.Surface(glow_rect.size, pygame.SRCALPHA)
            pygame.draw.rect(glow, (*accent, 24), glow.get_rect(), border_radius=radius + 4)
            self.screen.blit(glow, glow_rect.topleft)

        border_color = accent if (selected or hovered) else (60, 130, 120)
        pygame.draw.rect(self.screen, border_color, rect, border_w, border_radius=radius)

        icon_size = s(64)
        icon_rect = pygame.Rect(rect.x + s(16), rect.y + (rect.height - icon_size) // 2, icon_size, icon_size)
        pygame.draw.rect(self.screen, _darken_rgb(retro_style.success, 0.55), icon_rect, border_radius=12)
        pygame.draw.rect(self.screen, (255, 255, 255, 40), icon_rect, 2, border_radius=12)
        # + işaretini pygame.draw.line ile çiz — cross-platform tutarlı merkez
        _cx, _cy = icon_rect.center
        _arm = s(14)
        _lw = max(3, s(4))
        pygame.draw.line(self.screen, WHITE, (_cx - _arm, _cy), (_cx + _arm, _cy), _lw)
        pygame.draw.line(self.screen, WHITE, (_cx, _cy - _arm), (_cx, _cy + _arm), _lw)
        
        title = self.font_normal.render(t('user_create_new'), True, WHITE)
        text_x = icon_rect.right + s(16)
        self.screen.blit(title, (text_x, rect.y + s(18)))
        hint = self.font_small.render(t('user_create_hint'), True, (190, 210, 210))
        hint.set_alpha(235)
        self.screen.blit(hint, (text_x, rect.y + s(52)))
        
        self.card_targets.append({'rect': rect, 'index': index, 'type': 'add'})

    def _draw_profile_panel(self, rect):
        s = self._sx
        retro_style.draw_panel(self.screen, rect, t('user_profile_summary'), title_color=retro_style.text_primary)
        self._profile_edit_button_rect = None
        self._profile_delete_button_rect = None
        if not self.users_list:
            text = self.font_label.render(t('user_no_users'), True, (200, 210, 230))
            self.screen.blit(text, text.get_rect(center=rect.center))
            info = self.font_small.render(t('user_start_hint'), True, (180, 190, 210))
            self.screen.blit(info, info.get_rect(midtop=(rect.centerx, rect.centery + 20)))
            return
        if self._is_add_index(self.selected_user):
            title = self.font_label.render(t('user_new_profile'), True, WHITE)
            self.screen.blit(title, title.get_rect(midtop=(rect.centerx, rect.y + s(80))))
            info = self.font_small.render(t('user_adventure_hint'), True, (190, 200, 220))
            self.screen.blit(info, info.get_rect(midtop=(rect.centerx, rect.y + s(130))))
            return

        username = self.get_selected_username()
        if not username:
            return
        user_data = self.user_manager.get_user_data(username) or {}
        
        header_surface = retro_style.render_fit_text(
            username,
            WHITE,
            rect.width - s(60),
            self.font_title_size
        )
        self.screen.blit(header_surface, (rect.x + s(30), rect.y + s(40)))
        
        badge_rect = pygame.Rect(rect.x + s(30), rect.y + s(110), s(120), s(120))
        badge_center = badge_rect.center
        badge_radius = badge_rect.width // 2
        raw_avatar_color = user_data.get('avatar_color', (100, 150, 255))
        if isinstance(raw_avatar_color, (list, tuple)) and len(raw_avatar_color) >= 3:
            badge_bg_color = tuple(int(max(0, min(255, c))) for c in raw_avatar_color[:3])
        else:
            badge_bg_color = (100, 150, 255)
        # Dış glow halkası — dıştan içe azalan alpha (i=1 en dış, en soluk)
        glow_color = tuple(min(255, c + 40) for c in badge_bg_color)
        for i in range(1, 4):
            glow_alpha = i * 15  # i=1→15, i=2→30, i=3→45 (içe doğru yoğunlaşır)
            gs = badge_radius * 2 + (4 - i) * 8
            glow_surf = pygame.Surface((gs, gs), pygame.SRCALPHA)
            pygame.draw.circle(glow_surf, (*glow_color, glow_alpha),
                               (gs // 2, gs // 2), badge_radius + (4 - i) * 3)
            self.screen.blit(glow_surf, glow_surf.get_rect(center=badge_center))
        pygame.draw.circle(self.screen, badge_bg_color, badge_center, badge_radius)
        pygame.draw.circle(self.screen, tuple(min(255, c + 60) for c in badge_bg_color), badge_center, badge_radius, s(3))
        # Avatar boyutu daire iç çapıyla eşleşmeli (badge_radius * 2)
        avatar_diameter = badge_radius * 2
        is_active_profile = (username == self.user_manager.get_current_user())
        avatar_surface = None
        if self._should_use_steam_avatar_for_user(user_data, is_active_profile):
            avatar_surface = self._get_steam_avatar_surface(avatar_diameter)
        if avatar_surface is None:
            avatar_surface = self._get_avatar_surface(user_data.get('avatar', '__default__'), avatar_diameter)
        # Boyut uyumsuzluğuna karşı güvenlik ölçeği
        if avatar_surface.get_width() != avatar_diameter:
            avatar_surface = pygame.transform.smoothscale(avatar_surface, (avatar_diameter, avatar_diameter))
        self.screen.blit(avatar_surface, avatar_surface.get_rect(center=badge_center))

        button_width = s(220)
        button_height = s(48)
        button_spacing = s(16)
        total_width = button_width * 2 + button_spacing
        button_y = rect.bottom - button_height - s(20)
        start_x = max(rect.x + s(30), rect.right - total_width - s(30))
        delete_rect = pygame.Rect(start_x, button_y, button_width, button_height)
        edit_rect = pygame.Rect(delete_rect.right + button_spacing, button_y, button_width, button_height)
        self._profile_delete_button_rect = delete_rect
        self._profile_edit_button_rect = edit_rect

        def _format_last_played(value) -> str:
            if not value:
                return t('user_never_played')
            if isinstance(value, str):
                v = value.strip()
                if not v:
                    return t('user_never_played')
                # Beklenen format: 2025-12-21 18:09:08
                try:
                    dt = datetime.strptime(v[:19], '%Y-%m-%d %H:%M:%S')
                    return dt.strftime('%d.%m.%Y %H:%M')
                except Exception:
                    return v
            return str(value)

        stats = [
            (t('user_last_played'), _format_last_played(user_data.get('last_played'))),
            (t('total_games'), f"{user_data.get('total_games', 0)}"),
            (t('total_score'), f"{user_data.get('total_score', 0):,}".replace(',', '.')),
            (t('total_lines'), f"{user_data.get('total_lines', 0)}"),
            (t('highest_level'), f"{user_data.get('highest_level', 1)}"),
            (t('favorite_mode'), user_data.get('favorite_mode', t('mode_label_classic'))),
            (t('play_time'), self._format_playtime(user_data.get('total_playtime', 0))),
        ]
        
        info_x = badge_rect.right + s(30)
        info_width = max(s(160), edit_rect.left - info_x - s(20))

        def _draw_stats_column(
            col_x: int,
            col_width: int,
            start_y: int,
            rows: list[tuple[str, str]],
            max_bottom: int,
        ) -> int:
            label_w = max(s(110), int(col_width * 0.56))
            value_w = max(s(80), col_width - label_w - s(12))
            row_y = start_y
            row_gap = s(10)
            value_right = col_x + col_width
            compact_mode = col_width < s(280)
            for label, value in rows:
                label_surface = retro_style.render_fit_text(
                    f"{label}:",
                    (180, 190, 220),
                    max(s(80), (col_width - s(8)) if compact_mode else label_w),
                    self.font_small_size,
                    bold=False,
                    min_size=max(10, s(12)),
                )
                value_surface = retro_style.render_fit_text(
                    value,
                    WHITE,
                    max(s(80), (col_width - s(8)) if compact_mode else value_w),
                    max(self.font_normal_size - 2, 20),
                    min_size=max(11, s(13)),
                )
                label_surface.set_alpha(235)
                row_h = (
                    label_surface.get_height() + value_surface.get_height() + s(4)
                    if compact_mode
                    else max(label_surface.get_height(), value_surface.get_height())
                )
                if row_y + row_h > max_bottom:
                    break
                if compact_mode:
                    self.screen.blit(label_surface, (col_x, row_y))
                    self.screen.blit(value_surface, (col_x, row_y + label_surface.get_height() + s(2)))
                    row_y += label_surface.get_height() + value_surface.get_height() + s(4) + row_gap
                else:
                    self.screen.blit(label_surface, (col_x, row_y))
                    self.screen.blit(value_surface, (value_right - value_surface.get_width(), row_y - s(2)))
                    row_y += max(label_surface.get_height(), value_surface.get_height()) + row_gap
            return row_y

        # Grid'i avatar üst hizasına oturt
        start_y = badge_rect.y + s(4)
        stats_bottom_limit = delete_rect.y - s(18)

        # Yükseklik taşmasını önlemek için (geniş panelde) iki sütun kullan
        use_two_cols = info_width >= s(440) and len(stats) >= 6
        max_column_height = start_y
        if use_two_cols:
            col_gap = s(24)
            col_w = (info_width - col_gap) // 2
            left_rows = stats[0::2]
            right_rows = stats[1::2]
            left_end = _draw_stats_column(info_x, col_w, start_y, left_rows, stats_bottom_limit)
            right_end = _draw_stats_column(info_x + col_w + col_gap, col_w, start_y, right_rows, stats_bottom_limit)
            max_column_height = max(left_end, right_end)
        else:
            max_column_height = _draw_stats_column(info_x, info_width, start_y, stats, stats_bottom_limit)
        
        bio = user_data.get('bio', '').strip()
        text_area_left = rect.x + s(30)
        text_area_right = max(text_area_left + s(100), edit_rect.left - s(20))
        footer_top = max(max_column_height + s(10), badge_rect.bottom + s(10))
        if bio:
            bio_label = self.font_small.render(t('user_bio'), True, (180, 190, 220))
            self.screen.blit(bio_label, (text_area_left, footer_top))
            bio_rect = pygame.Rect(
                text_area_left,
                footer_top + bio_label.get_height() + s(4),
                text_area_right - text_area_left,
                max(s(40), edit_rect.y - footer_top - s(90))
            )
            bio_drawn = retro_style.draw_wrapped_text(
                self.screen,
                bio,
                self.font_small,
                WHITE,
                bio_rect,
                align='left'
            )
            footer_top = bio_drawn.bottom + s(8)
        
        self._draw_action_button(delete_rect, t('user_action_delete_profile'), (210, 80, 80))
        self._draw_action_button(edit_rect, t('user_action_edit_profile'), _darken_rgb(retro_style.success, 0.55))

        # 2-adım silme uyarısı aynı panel içinde
        if self._is_delete_armed(username):
            # Kırmızı pulse (2sn)
            now = pygame.time.get_ticks()
            remaining = max(0, self._delete_armed_until_ms - now)
            # 0..1..0
            phase = (now % 500) / 500.0
            pulse = 1.0 - abs(phase * 2.0 - 1.0)
            alpha = int(60 + 70 * pulse)
            pulse_surf = pygame.Surface(delete_rect.size, pygame.SRCALPHA)
            pygame.draw.rect(pulse_surf, (210, 80, 80, alpha), pulse_surf.get_rect(), border_radius=14)
            self.screen.blit(pulse_surf, delete_rect.topleft)

            warn = self.font_small.render(t('user_confirm_delete'), True, (255, 255, 255))
            warn.set_alpha(235)
            self.screen.blit(warn, warn.get_rect(midbottom=(delete_rect.centerx, delete_rect.y - s(8))))

    def _draw_avatar_picker(self, rect):
        s = self._sx
        retro_style.draw_panel(self.screen, rect, t('user_avatar_select'), title_color=retro_style.text_primary)
        preview_rect = pygame.Rect(rect.centerx - s(90), rect.y + s(80), s(180), s(180))

        # Seçili renkle doldurulan arka plan dairesi
        sel_color = self.avatar_colors[self.selected_color_index]
        pygame.draw.ellipse(self.screen, sel_color, preview_rect)
        glow = pygame.Surface(preview_rect.inflate(s(8), s(8)).size, pygame.SRCALPHA)
        pygame.draw.ellipse(glow, (*sel_color[:3], 50), glow.get_rect())
        self.screen.blit(glow, preview_rect.inflate(s(8), s(8)).topleft)
        pygame.draw.ellipse(self.screen, retro_style.primary, preview_rect.inflate(s(8), s(8)), s(2))

        avatar_value = self.custom_avatar_path if self.custom_avatar_path else self.selected_avatar
        avatar_surface = self._get_avatar_surface(avatar_value, s(162))
        self.screen.blit(avatar_surface, avatar_surface.get_rect(center=preview_rect.center))
        
        # Oklar avatar merkezine simetrik
        arrow_size = s(60)
        gap = s(14)
        self._avatar_left_rect = pygame.Rect(preview_rect.x - gap - arrow_size, preview_rect.centery - arrow_size // 2, arrow_size, arrow_size)
        self._avatar_right_rect = pygame.Rect(preview_rect.right + gap, preview_rect.centery - arrow_size // 2, arrow_size, arrow_size)
        self._draw_icon_button(self._avatar_left_rect, '<')
        self._draw_icon_button(self._avatar_right_rect, '>')
        
        counter = self.font_small.render(f'{self.avatar_index + 1} / {len(self.avatars)}', True, (200, 210, 230))
        counter.set_alpha(235)
        # Sayfa göstergesi tam merkez
        counter_y = preview_rect.bottom + s(10)
        self.screen.blit(counter, counter.get_rect(midtop=(preview_rect.centerx, counter_y)))
        
        self._custom_avatar_button_rect = None
        if self.custom_avatar_path:
            info = self.font_small.render(t('user_custom_image'), True, (120, 255, 180))
            self.screen.blit(info, info.get_rect(midtop=(rect.centerx, preview_rect.bottom + s(35))))

        # Renk paleti — küçük daireler
        dot_r = s(14)
        dot_gap = s(6)
        n_colors = len(self.avatar_colors)
        palette_w = n_colors * (dot_r * 2) + (n_colors - 1) * dot_gap
        palette_x0 = rect.centerx - palette_w // 2
        palette_y = rect.bottom - s(48)
        # Yeterli alan yoksa counter'ın biraz altına koy
        palette_y = max(counter_y + s(30), palette_y)
        self._avatar_color_rects = []
        for i, color in enumerate(self.avatar_colors):
            cx = palette_x0 + i * (dot_r * 2 + dot_gap) + dot_r
            cy = palette_y + dot_r
            dot_rect = pygame.Rect(cx - dot_r, cy - dot_r, dot_r * 2, dot_r * 2)
            self._avatar_color_rects.append(dot_rect)
            pygame.draw.ellipse(self.screen, color, dot_rect)
            if i == self.selected_color_index:
                # Seçili dairenin etrafına parlak çerçeve
                pygame.draw.ellipse(self.screen, (255, 255, 255), dot_rect.inflate(s(4), s(4)), s(2))
            else:
                pygame.draw.ellipse(self.screen, (80, 90, 130), dot_rect, 1)

    def _draw_username_form(self, rect):
        s = self._sx
        is_edit_mode = self.form_mode == 'edit'
        panel_title = t('user_profile_info') if is_edit_mode else t('user_account_info')
        retro_style.draw_panel(self.screen, rect, panel_title, title_color=retro_style.text_primary)
        label = self.font_small.render(t('user_username'), True, (200, 210, 230))
        label.set_alpha(235)
        self.screen.blit(label, (rect.x + s(20), rect.y + s(34)))
        
        input_rect = pygame.Rect(rect.x + s(20), rect.y + s(66), rect.width - s(40), s(64))
        self._input_rect = input_rect
        pygame.draw.rect(self.screen, (12, 14, 36), input_rect, border_radius=12)
        border_color = retro_style.primary if self.new_username else (70, 80, 110)
        if is_edit_mode:
            border_color = (90, 100, 140)
        if self._form_focus == 1 and not is_edit_mode:
            # Odak glow
            glow_rect = input_rect.inflate(s(10), s(10))
            glow = pygame.Surface(glow_rect.size, pygame.SRCALPHA)
            pygame.draw.rect(glow, (*retro_style.primary, 28), glow.get_rect(), border_radius=16)
            self.screen.blit(glow, glow_rect.topleft)
            border_color = retro_style.primary
        pygame.draw.rect(self.screen, border_color, input_rect, s(2), border_radius=12)
        
        display_text = self.new_username if self.new_username else t('user_username_placeholder')
        if self._is_username_editable() and self.new_username and self.cursor_visible:
            display_text += '|'
        if is_edit_mode:
            text_color = (210, 220, 240)
        else:
            text_color = WHITE if self.new_username else (150, 150, 180)
        text_surface = self.font_normal.render(display_text, True, text_color)
        self.screen.blit(text_surface, (input_rect.x + s(16), input_rect.y + s(16)))
        
        # Help/Counter satırı (input altı)
        help_y = input_rect.bottom + s(8)
        if is_edit_mode:
            help_text = self.font_small.render(t('user_name_locked'), True, (180, 190, 210))
            help_text.set_alpha(235)
            self.screen.blit(help_text, (input_rect.x, help_y))
            badge = self.font_small.render(t('user_locked'), True, (210, 220, 240))
            badge.set_alpha(220)
            self.screen.blit(badge, badge.get_rect(topright=(input_rect.right, help_y)))
        else:
            counter_text = self.font_small.render(f'{len(self.new_username)} / 20', True, (180, 190, 210))
            counter_text.set_alpha(235)
            self.screen.blit(counter_text, counter_text.get_rect(topright=(input_rect.right, help_y)))

        # Validasyon alanı (tek satır, butonları itmeden)
        validation_rect = pygame.Rect(rect.x + s(20), help_y + s(26), rect.width - s(40), s(28))
        msg = ''
        if self.error_message:
            msg = self.error_message
        elif self._validation_message:
            msg = self._validation_message
        if msg:
            err = self.font_small.render(msg, True, WHITE)
            err.set_alpha(235)
            # Arka planı çok ağır basmasın
            bg = pygame.Surface(validation_rect.size, pygame.SRCALPHA)
            pygame.draw.rect(bg, (160, 50, 50, 120), bg.get_rect(), border_radius=10)
            self.screen.blit(bg, validation_rect.topleft)
            self.screen.blit(err, err.get_rect(midleft=(validation_rect.x + s(10), validation_rect.centery)))
        elif self._validation_suggestion:
            sug = self.font_small.render(self._validation_suggestion, True, (210, 220, 240))
            sug.set_alpha(220)
            self.screen.blit(sug, sug.get_rect(midleft=(validation_rect.x + s(10), validation_rect.centery)))

        # Butonlar: içerikten sonra, ama altına ankraj yaparak. Küçük ekranda validation ile buton üst üste gelmesin.
        content_bottom = validation_rect.bottom
        bottom_anchor_y = rect.bottom - s(56) - s(54)
        button_y = max(content_bottom + s(12), bottom_anchor_y)
        # Buton, rect sınırından taşmasın
        button_y = min(button_y, rect.bottom - s(56) - s(4))
        self._create_button_rect = pygame.Rect(rect.x + s(20), button_y, s(220), s(56))
        primary_label = t('user_action_save') if is_edit_mode else t('user_action_create')
        self._draw_action_button(self._create_button_rect, primary_label, _darken_rgb(retro_style.success, 0.55))
        self._cancel_button_rect = pygame.Rect(self._create_button_rect.right + s(20), button_y, s(180), s(56))
        self._draw_action_button(self._cancel_button_rect, t('user_action_back_esc'), (200, 80, 80))

        hint_text = t('user_hint_save') if is_edit_mode else t('user_hint_create')
        hint_y = button_y + s(56) + s(6)
        # Hint çizmek için yeterli alan varsa göster
        if hint_y + self.font_small.get_height() <= rect.bottom:
            hint = self.font_small.render(hint_text, True, (190, 200, 215))
            hint.set_alpha(235)
            self.screen.blit(hint, hint.get_rect(midtop=(rect.centerx, hint_y)))

    def _draw_chip_button(self, rect, label, color):
        pygame.draw.rect(self.screen, color, rect, border_radius=16)
        pygame.draw.rect(self.screen, (255, 255, 255, 60), rect, 2, border_radius=16)
        text = retro_style.render_fit_text(label, WHITE, rect.width - 24, self.font_small_size, bold=False)
        self.screen.blit(text, text.get_rect(center=rect.center))

    def _draw_icon_button(self, rect, label):
        pygame.draw.rect(self.screen, (26, 32, 64), rect, border_radius=12)
        pygame.draw.rect(self.screen, retro_style.primary, rect, 2, border_radius=12)
        text = retro_style.render_fit_text(label, WHITE, rect.width - 20, self.font_normal_size)
        self.screen.blit(text, text.get_rect(center=rect.center))

    def _draw_action_button(self, rect, label, color):
        pygame.draw.rect(self.screen, color, rect, border_radius=14)
        pygame.draw.rect(self.screen, (255, 255, 255, 60), rect, 2, border_radius=14)
        text = retro_style.render_fit_text(label, WHITE, rect.width - 24, self.font_small_size, bold=False)
        self.screen.blit(text, text.get_rect(center=rect.center))

    def _draw_select_screen(self):
        """Kullanıcı seçim ekranını çiz - Retro tasarım"""
        self._apply_responsive_metrics()
        s = self._sx
        width, height = self.screen.get_size()
        retro_style.draw_background(self.screen)
        self.background_fx.update(self.screen)
        self.background_fx.draw(self.screen)
        retro_style.draw_title(self.screen, t('user_select_title'), (width // 2, s(70)), emoji=None)
        
        list_width = min(s(520), width - s(120))
        list_height = max(s(320), height - s(190))
        list_rect = pygame.Rect(s(60), s(150), list_width, list_height)
        
        # Dinamik görünür limit: (height - padding) // (card_height + gap)
        # Başlık alanı: draw_panel başlığı y+8 konumuna ~22px font ile çizer → ~y+30.
        # Kartların başladığı y ofseti (s(44)) başlığın altında kalmalıdır.
        card_header_offset = s(44)  # panel başlığının altı + boşluk
        card_bottom_pad = s(24)
        card_height = s(86)
        card_gap = s(14)
        self.visible_limit = max(4, (list_height - card_header_offset - card_bottom_pad) // max(s(84), card_height + card_gap))

        retro_style.draw_panel(self.screen, list_rect, t('user_profiles'), title_color=retro_style.text_primary)
        
        self.card_targets = []
        mouse_pos = get_mouse_pos()
        self._hovered_index = None
        entries = ['__add__'] + self.users_list
        visible_entries = entries[self.scroll_offset:self.scroll_offset + self.visible_limit]
        card_y = list_rect.y + card_header_offset
        for idx, entry in enumerate(visible_entries):
            rect = pygame.Rect(list_rect.x + s(16), card_y, list_rect.width - s(32), card_height)
            global_index = self.scroll_offset + idx
            if rect.collidepoint(mouse_pos):
                self._hovered_index = global_index
            if entry == '__add__':
                self._draw_add_card(rect, global_index == self.selected_user, global_index)
            else:
                data = self.user_manager.get_user_data(entry) or {}
                is_active = (entry == self.user_manager.get_current_user())
                self._draw_user_card(rect, entry, data, global_index == self.selected_user, is_active, global_index)
            card_y += card_height + card_gap
        
        # Scrollbar çiz
        entries = ['__add__'] + self.users_list
        content_height = len(entries) * (card_height + card_gap)
        visible_height = list_rect.height - s(48)
        if len(entries) > self.visible_limit:
            scrollbar_rect = pygame.Rect(
                list_rect.right - s(22),
                list_rect.y + s(24),
                s(22),
                visible_height
            )
            retro_style.draw_scrollbar(
                self.screen,
                scrollbar_rect,
                self.scroll_offset * (card_height + card_gap),
                content_height,
                visible_height
            )
        
        detail_width = max(s(320), width - list_rect.right - s(90))
        detail_height = min(height - s(260), s(380))
        detail_rect = pygame.Rect(list_rect.right + s(30), list_rect.y, detail_width, detail_height)
        stacked_layout = detail_rect.right + s(30) > width
        if stacked_layout:
            detail_rect = pygame.Rect(s(60), list_rect.bottom + s(20), width - s(120), min(s(380), height - list_rect.bottom - s(80)))
        if detail_rect.height < s(240):
            detail_rect.height = s(240)
        if detail_rect.bottom > height - s(40):
            detail_rect.height = max(s(220), height - detail_rect.y - s(60))
        self._draw_profile_panel(detail_rect)

        # Profil özeti altındaki boş alanda göster (mavi işaretlenen yer)
        if self.users_list and not self._is_add_index(self.selected_user):
            username = self.get_selected_username()
            if username:
                user_data = self.user_manager.get_user_data(username) or {}
            top = detail_rect.bottom + s(18)
            bottom = height - s(90)
            available_h = bottom - top
            if available_h >= s(140):
                held_rect = pygame.Rect(detail_rect.x, top, detail_rect.width, min(s(260), available_h))
                self._draw_most_held_panel(held_rect, user_data, username)
        


    def _draw_form_screen(self):
        """Yeni kullanıcı oluşturma veya düzenleme ekranı"""
        self._apply_responsive_metrics()
        s = self._sx
        width, height = self.screen.get_size()
        retro_style.draw_background(self.screen)
        self.background_fx.update(self.screen)
        self.background_fx.draw(self.screen)
        is_edit_mode = self.form_mode == 'edit'
        title = t('user_edit_profile_title') if is_edit_mode else t('user_new_user_title')
        self._draw_h1_title(title, (width // 2, s(70)))
        helper_text = t('user_helper_edit') if is_edit_mode else t('user_helper_create')
        helper_rect = pygame.Rect(s(80), s(100), width - s(160), s(60))
        retro_style.draw_wrapped_text(
            self.screen,
            helper_text,
            self.font_small,
            (200, 210, 240),
            helper_rect,
            align='center'
        )
        
        form_rect = pygame.Rect(s(60), s(150), width - s(120), height - s(260))
        panel_title = t('user_panel_edit') if is_edit_mode else t('user_panel_create')
        retro_style.draw_panel(self.screen, form_rect, panel_title, title_color=retro_style.text_primary)
        
        column_width = (form_rect.width - s(60)) // 2
        avatar_rect = pygame.Rect(form_rect.x + s(30), form_rect.y + s(60), column_width, form_rect.height - s(120))
        info_rect = pygame.Rect(avatar_rect.right + s(30), avatar_rect.y, column_width, avatar_rect.height)
        stacked_layout = info_rect.width < s(320)
        if stacked_layout:
            # info_rect içindeki elemanların üst üste binmemesi için minimum yükseklik:
            # label(34) + input(66+64) + help(8) + validation(26+28) + gap(12) + button(56) + hint(44) = ~292
            MIN_INFO_H = s(300)
            usable_h = form_rect.height - s(120)  # s(60) üst boşluk + s(40) bölümler arası + s(20) alt padding
            avatar_h = max(s(60), usable_h - MIN_INFO_H)
            info_h = max(MIN_INFO_H, usable_h - avatar_h)
            avatar_rect = pygame.Rect(form_rect.x + s(30), form_rect.y + s(60), form_rect.width - s(60), avatar_h)
            info_rect = pygame.Rect(avatar_rect.x, avatar_rect.bottom + s(40), avatar_rect.width, info_h)
        self._draw_avatar_picker(avatar_rect)
        self._draw_username_form(info_rect)
        



class UserManagementScreen:
    """Kullanıcı yönetim ekranı (Ana menüden erişilebilir)"""
    
    def __init__(self, screen, user_manager):
        """Kullanıcı yönetim ekranını başlat"""
        self.screen = screen
        self.user_manager = user_manager
        self.font_title = UIFonts.get(56)
        self.font_normal = UIFonts.get(36)
        self.font_small = UIFonts.get(26)
        
        self.users_list = list(user_manager.get_all_users().keys())
        self.selected_user = 0
        self.state = 'list'  # list, confirm_delete, view_profile, edit_profile
        self.confirm_username = None
        self.message = ''
        self.message_timer = 0
        
        # Profil düzenleme için
        self.edit_field = 0  # 0: avatar, 1: bio, 2: favorite_mode
        self.edit_username = None
        self.temp_avatar_index = 0
        self.temp_bio = ''
        self.temp_favorite_mode = 'Classic'
        management_avatar_entries = get_avatar_entries()
        base_presets = [entry.get('value') for entry in management_avatar_entries if entry.get('value')]
        self.avatars = list(base_presets) if base_presets else ['__default__']
        self.modes = [
            t('mode_label_classic'),
            t('mode_label_sprint'),
            t('mode_label_ultra'),
            t('mode_label_zen'),
            t('mode_tetris_extra'),
            t('mode_label_card_mastery'),
            t('mode_label_wide'),
            t('mode_label_cascade'),
        ]
        self.avatar_colors = [
            (100, 150, 255),  # Mavi
            (255, 100, 100),  # Kırmızı
            (100, 255, 100),  # Yeşil
            (255, 255, 100),  # Sarı
            (255, 100, 255),  # Pembe
            (100, 255, 255),  # Cyan
            (255, 150, 100),  # Turuncu
            (200, 100, 255),  # Mor
        ]
        self.temp_color_index = 0
        
        # Çift tıklama için
        self.last_click_time = 0
        self.last_click_index = None
        self.double_click_delay = 500  # ms
        
        # Scroll için
        self.scroll_offset = 0
        self.max_visible = 5
        
        # Avatar editör
        self.avatar_editor = AvatarEditor(screen)
        self.custom_avatar_path = None
    
    def handle_input(self, event):
        """Girdi işle"""
        if self.state == 'list':
            return self._handle_list_input(event)
        elif self.state == 'confirm_delete':
            return self._handle_confirm_input(event)
        elif self.state == 'view_profile':
            return self._handle_view_profile_input(event)
        elif self.state == 'edit_profile':
            return self._handle_edit_profile_input(event)
        elif self.state == 'avatar_editor':
            return self._handle_avatar_editor_input(event)
    
    def _handle_list_input(self, event):
        """Liste girdisi"""
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                return 'back'
            elif event.key == pygame.K_UP:
                if self.users_list:
                    self.selected_user = (self.selected_user - 1) % len(self.users_list)
            elif event.key == pygame.K_DOWN:
                if self.users_list:
                    self.selected_user = (self.selected_user + 1) % len(self.users_list)
            elif event.key == pygame.K_RETURN or event.key == pygame.K_SPACE:
                # Kullanıcı profilini görüntüle
                if self.users_list:
                    self.edit_username = self.users_list[self.selected_user]
                    self.state = 'view_profile'
            elif event.key == pygame.K_e:
                # Düzenleme moduna geç
                if self.users_list:
                    self.edit_username = self.users_list[self.selected_user]
                    self._init_edit_fields()
                    self.state = 'edit_profile'
            elif event.key == pygame.K_a:
                # Kullanıcıyı aktif yap
                if self.users_list:
                    username = self.users_list[self.selected_user]
                    self.user_manager.select_user(username)
                    self.message = t('user_set_active_message', username=username)
                    self.message_timer = 120
            elif event.key == pygame.K_DELETE or event.key == pygame.K_d:
                # Sil
                if self.users_list:
                    self.confirm_username = self.users_list[self.selected_user]
                    self.state = 'confirm_delete'
        
        # Mouse çift tıklama kontrolü
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            current_time = pygame.time.get_ticks()
            pos = normalize_mouse_pos(getattr(event, 'pos', None)) or event.pos
            
            # Hangi kullanıcıya tıklandığını bul
            width, height = self.screen.get_size()
            card_width = min(900, width - 100)
            card_x = width // 2 - card_width // 2
            list_start_y = 200
            
            visible_users = self.users_list[self.scroll_offset:self.scroll_offset + self.max_visible]
            
            for i, username in enumerate(visible_users):
                card_y = list_start_y + i * 110
                card_rect = pygame.Rect(card_x, card_y, card_width, 100)
                
                if card_rect.collidepoint(pos):
                    clicked_index = self.scroll_offset + i
                    
                    # Çift tıklama kontrolü
                    if (self.last_click_index == clicked_index and 
                        current_time - self.last_click_time < self.double_click_delay):
                        # Çift tıklama tespit edildi - düzenleme moduna geç
                        self.edit_username = username
                        self._init_edit_fields()
                        self.state = 'edit_profile'
                        return None
                    
                    # Tek tıklama - seçimi değiştir
                    self.selected_user = clicked_index
                    
                    # Tıklama bilgilerini kaydet
                    self.last_click_time = current_time
                    self.last_click_index = clicked_index
                    break
        
        return None
    
    def _handle_confirm_input(self, event):
        """Silme onayı girdisi"""
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_y:
                # Sil
                success, msg = self.user_manager.delete_user(self.confirm_username)
                self.users_list = list(self.user_manager.get_all_users().keys())
                self.selected_user = min(self.selected_user, len(self.users_list) - 1) if self.users_list else 0
                self.message = msg
                self.message_timer = 120
                self.state = 'list'
            elif event.key == pygame.K_n or event.key == pygame.K_ESCAPE:
                self.state = 'list'
        
        return None
    
    def _handle_view_profile_input(self, event):
        """Profil görüntüleme girdisi"""
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.state = 'list'
            elif event.key == pygame.K_e:
                # Düzenleme moduna geç
                user_data = self.user_manager.get_user_data(self.edit_username)
                self.temp_bio = user_data.get('bio', '')
                self.temp_favorite_mode = user_data.get('favorite_mode', 'Classic')
                if self.temp_favorite_mode not in self.modes:
                    self.temp_favorite_mode = 'Classic'
                # Avatar index'ini bul
                avatar = user_data.get('avatar', '__default__')
                self.temp_avatar_index = self.avatars.index(avatar) if avatar in self.avatars else 0
                # Color index'ini bul
                color = user_data.get('avatar_color', (100, 150, 255))
                try:
                    self.temp_color_index = self.avatar_colors.index(color)
                except ValueError:
                    self.temp_color_index = 0
                self.edit_field = 0
                self.state = 'edit_profile'
        
        return None
    
    def _init_edit_fields(self):
        """Düzenleme alanlarını başlat"""
        if self.edit_username:
            user_data = self.user_manager.users.get(self.edit_username, {})
            self.temp_bio = user_data.get('bio', '')
            self.temp_favorite_mode = user_data.get('favorite_mode', 'Classic')
            if self.temp_favorite_mode not in self.modes:
                self.temp_favorite_mode = 'Classic'
            # Avatar index'ini bul
            avatar = user_data.get('avatar', '__default__')
            self.temp_avatar_index = self.avatars.index(avatar) if avatar in self.avatars else 0
            # Color index'ini bul
            color = user_data.get('avatar_color', (100, 150, 255))
            try:
                self.temp_color_index = self.avatar_colors.index(color)
            except ValueError:
                self.temp_color_index = 0
            self.edit_field = 0

    def open_edit_for(self, username):
        """Dışarıdan profil düzenleme ekranını aç."""
        self.users_list = list(self.user_manager.get_all_users().keys())
        if not self.users_list:
            self.selected_user = 0
            self.edit_username = None
            self.state = 'list'
            return
        if username in self.users_list:
            self.selected_user = self.users_list.index(username)
        else:
            self.selected_user = 0
            username = self.users_list[0]
        self.edit_username = username
        self.custom_avatar_path = None
        self._init_edit_fields()
        self.state = 'edit_profile'
        self.message = ''
        self.message_timer = 0
    
    def _handle_edit_profile_input(self, event):
        """Profil düzenleme girdisi"""
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.state = 'view_profile'
            elif event.key == pygame.K_TAB or event.key == pygame.K_DOWN:
                self.edit_field = (self.edit_field + 1) % 4  # 4 alan: avatar, color, bio, mode
            elif event.key == pygame.K_UP:
                self.edit_field = (self.edit_field - 1) % 4
            elif event.key == pygame.K_c and self.edit_field == 0:
                # Custom avatar yükle (sadece avatar alanındayken)
                self.state = 'avatar_editor'
                self.avatar_editor.open_file_dialog()
            elif event.key == pygame.K_RETURN:
                # Kaydet
                avatar = self.custom_avatar_path if self.custom_avatar_path else self.avatars[self.temp_avatar_index]
                self.user_manager.update_user_profile(
                    self.edit_username,
                    avatar=avatar,
                    avatar_color=self.avatar_colors[self.temp_color_index],
                    bio=self.temp_bio,
                    favorite_mode=self.temp_favorite_mode
                )
                self.message = t('user_profile_saved')
                self.message_timer = 120
                self.custom_avatar_path = None
                self.state = 'view_profile'
            else:
                # Alan bazlı kontroller
                if self.edit_field == 0:  # Avatar
                    if event.key == pygame.K_LEFT:
                        self.temp_avatar_index = (self.temp_avatar_index - 1) % len(self.avatars)
                    elif event.key == pygame.K_RIGHT:
                        self.temp_avatar_index = (self.temp_avatar_index + 1) % len(self.avatars)
                elif self.edit_field == 1:  # Color
                    if event.key == pygame.K_LEFT:
                        self.temp_color_index = (self.temp_color_index - 1) % len(self.avatar_colors)
                    elif event.key == pygame.K_RIGHT:
                        self.temp_color_index = (self.temp_color_index + 1) % len(self.avatar_colors)
                elif self.edit_field == 2:  # Bio
                    if event.key == pygame.K_BACKSPACE:
                        self.temp_bio = self.temp_bio[:-1]
                    elif event.unicode.isprintable() and len(self.temp_bio) < 50:
                        self.temp_bio += event.unicode
                elif self.edit_field == 3:  # Favorite Mode
                    if event.key == pygame.K_LEFT:
                        idx = self.modes.index(self.temp_favorite_mode) if self.temp_favorite_mode in self.modes else 0
                        self.temp_favorite_mode = self.modes[(idx - 1) % len(self.modes)]
                    elif event.key == pygame.K_RIGHT:
                        idx = self.modes.index(self.temp_favorite_mode) if self.temp_favorite_mode in self.modes else 0
                        self.temp_favorite_mode = self.modes[(idx + 1) % len(self.modes)]
        
        return None
    
    def _handle_avatar_editor_input(self, event):
        """Avatar editör girdisi"""
        result = self.avatar_editor.handle_event(event)
        
        if result == 'save':
            # Kırpılmış avatarı kaydet
            filepath = self.avatar_editor.save_avatar(self.edit_username)
            if filepath:
                self.custom_avatar_path = filepath
                self.state = 'edit_profile'
        
        elif result == 'cancel':
            self.state = 'edit_profile'
        
        return None
    
    def update(self):
        """Güncelle"""
        if self.message_timer > 0:
            self.message_timer -= 1
            if self.message_timer == 0:
                self.message = ''
    
    def draw(self):
        """Ekranı çiz"""
        if self.state == 'list':
            self._draw_list()
        elif self.state == 'confirm_delete':
            self._draw_confirm_delete()
        elif self.state == 'view_profile':
            self._draw_view_profile()
        elif self.state == 'edit_profile':
            self._draw_edit_profile()
        elif self.state == 'avatar_editor':
            self.avatar_editor.draw()
    
    def _draw_list(self):
        """Kullanıcı listesini çiz - Geliştirilmiş tasarım"""
        width, height = self.screen.get_size()
        
        # Koyu gradient arka plan (siyah)
        for i in range(height):
            color_r = int(5 + (i / height) * 5)
            color_g = int(5 + (i / height) * 5)
            color_b = int(10 + (i / height) * 10)
            pygame.draw.line(self.screen, (color_r, color_g, color_b), (0, i), (width, i))
        
        # Üst başlık paneli
        header_height = 120
        header_rect = pygame.Rect(0, 0, width, header_height)
        
        # Header gradient
        for i in range(header_height):
            alpha = i / header_height
            color = (int(20 + alpha * 30), int(30 + alpha * 40), int(60 + alpha * 40))
            pygame.draw.line(self.screen, color, (0, i), (width, i))
        
        # Başlık
        title = self.font_title.render(t('user_management'), True, WHITE)
        title_rect = title.get_rect(center=(width // 2, 45))
        self.screen.blit(title, title_rect)
        
        # Aktif kullanıcı göstergesi
        current = self.user_manager.get_current_user()
        if current:
            current_bg = pygame.Rect(width // 2 - 200, 85, 400, 35)
            pygame.draw.rect(self.screen, (100, 200, 100), current_bg, border_radius=17)
            current_text = f"{t('user_active')}: {current}"
            current_surf = self.font_small.render(current_text, True, WHITE)
            current_rect = current_surf.get_rect(center=current_bg.center)
            self.screen.blit(current_surf, current_rect)
        else:
            current_surf = self.font_small.render(t('user_no_active'), True, (200, 100, 100))
            current_rect = current_surf.get_rect(center=(width // 2, 102))
            self.screen.blit(current_surf, current_rect)
        
        # Kullanıcı kartları bölümü
        cards_start_y = header_height + 30
        card_width = min(700, width - 100)
        card_height = 100
        card_x = width // 2 - card_width // 2
        gap = 15
        
        # Scroll kontrol (maksimum 6 kullanıcı göster)
        max_visible = min(6, len(self.users_list))
        
        for i in range(max_visible):
            if i >= len(self.users_list):
                break
            
            username = self.users_list[i]
            user_data = self.user_manager.get_user_data(username)
            is_current = (username == current)
            is_selected = (i == self.selected_user)
            
            y = cards_start_y + i * (card_height + gap)
            
            # Kart gölgesi
            if is_selected:
                shadow_rect = pygame.Rect(card_x + 4, y + 4, card_width, card_height)
                pygame.draw.rect(self.screen, (0, 0, 0, 100), shadow_rect, border_radius=15)
            
            # Ana kart
            card_rect = pygame.Rect(card_x, y, card_width, card_height)
            
            # Kart rengi - seçili/aktif duruma göre
            if is_selected:
                if is_current:
                    card_color = (60, 120, 60)
                    border_color = (100, 200, 100)
                else:
                    card_color = (60, 80, 140)
                    border_color = (100, 150, 255)
            else:
                if is_current:
                    card_color = (40, 60, 40)
                    border_color = (80, 140, 80)
                else:
                    card_color = (30, 40, 60)
                    border_color = (60, 80, 120)
            
            pygame.draw.rect(self.screen, card_color, card_rect, border_radius=15)
            pygame.draw.rect(self.screen, border_color, card_rect, 3 if is_selected else 2, border_radius=15)
            
            # Avatar bölümü
            avatar = user_data.get('avatar', '__default__')
            avatar_color = user_data.get('avatar_color', (100, 150, 255))
            
            avatar_size = 70
            avatar_bg_x = card_x + 20
            avatar_bg_y = y + (card_height - avatar_size) // 2
            avatar_bg_rect = pygame.Rect(avatar_bg_x, avatar_bg_y, avatar_size, avatar_size)

            # Daire çerçeve + dairesel maske (kare köşeler gizli)
            center = avatar_bg_rect.center
            radius = avatar_size // 2
            pygame.draw.circle(self.screen, avatar_color, center, radius)
            pygame.draw.circle(self.screen, WHITE if is_selected else (200, 200, 200), center, radius, 3 if is_selected else 2)
            avatar_img = _load_avatar_image(avatar, avatar_size - 2)
            if avatar_img is None:
                avatar_img = _render_placeholder_avatar(avatar_size - 2)
            avatar_surf = _circle_crop_surface(avatar_img, avatar_size - 2)
            self.screen.blit(avatar_surf, avatar_surf.get_rect(center=center))
            
            # Kullanıcı bilgileri
            info_x = card_x + 110
            
            # Kullanıcı adı
            name_color = (255, 255, 100) if is_current else WHITE
            name_surf = self.font_normal.render(username, True, name_color)
            name_rect = name_surf.get_rect(midleft=(info_x, y + 28))
            self.screen.blit(name_surf, name_rect)
            
            # Aktif badge
            if is_current:
                badge_x = name_rect.right + 15
                badge_rect = pygame.Rect(badge_x, y + 18, 70, 24)
                pygame.draw.rect(self.screen, (255, 200, 0), badge_rect, border_radius=12)
                badge_text = self.font_small.render(t('user_active').upper(), True, (50, 50, 50))
                self.screen.blit(badge_text, badge_text.get_rect(center=badge_rect.center))
            
            # İstatistikler (ikon yok)
            stats_y = y + 60
            stats_text = t(
                'user_stats_summary',
                games=user_data.get('total_games', 0),
                score=f"{user_data.get('total_score', 0):,}".replace(',', '.'),
                lines=user_data.get('total_lines', 0),
            )
            stats_surf = self.font_small.render(stats_text, True, (200, 200, 200))
            self.screen.blit(stats_surf, (info_x, stats_y + 2))
        
        # Eğer kullanıcı yoksa
        if not self.users_list:
            no_user_text = self.font_normal.render(t('user_not_created'), True, GRAY)
            no_user_rect = no_user_text.get_rect(center=(width // 2, height // 2))
            self.screen.blit(no_user_text, no_user_rect)
        
        # Mesaj gösterimi
        if self.message:
            msg_y = cards_start_y + max_visible * (card_height + gap) + 20
            msg_bg_rect = pygame.Rect(width // 2 - 250, msg_y, 500, 50)
            pygame.draw.rect(self.screen, (50, 200, 100), msg_bg_rect, border_radius=25)
            msg_surf = self.font_normal.render(self.message, True, WHITE)
            msg_rect = msg_surf.get_rect(center=msg_bg_rect.center)
            self.screen.blit(msg_surf, msg_rect)
        
        # Alt bar - talimatlar (modern buton tasarımı)
        bottom_bar_y = height - 80
        inst_bg_rect = pygame.Rect(0, bottom_bar_y, width, 80)
        
        # Gradient alt bar
        for i in range(80):
            alpha = 1 - (i / 80)
            color = (int(20 * alpha), int(25 * alpha), int(40 * alpha))
            pygame.draw.line(self.screen, color, (0, bottom_bar_y + i), (width, bottom_bar_y + i))
        
        pygame.draw.line(self.screen, (70, 100, 180), (0, bottom_bar_y), (width, bottom_bar_y), 2)
        
        # Kontrol butonları
        buttons = [
            ('↑↓', t('select'), (100, 120, 200)),
            ('ENTER', t('profile'), (100, 200, 100)),
            ('A', t('user_set_active'), (200, 150, 100)),
            ('D', t('delete'), (200, 100, 100)),
            ('ESC', t('menu_back'), (120, 120, 120))
        ]
        
        total_width = sum(140 for _ in buttons) - 20
        button_x = width // 2 - total_width // 2
        button_y = bottom_bar_y + 20
        
        for key, label, color in buttons:
            # Key badge
            key_width = 80 if len(key) > 1 else 50
            key_bg = pygame.Rect(button_x, button_y, key_width, 35)
            pygame.draw.rect(self.screen, color, key_bg, border_radius=8)
            pygame.draw.rect(self.screen, tuple(min(255, c + 40) for c in color), key_bg, 2, border_radius=8)
            
            key_surf = self.font_small.render(key, True, WHITE)
            self.screen.blit(key_surf, key_surf.get_rect(center=key_bg.center))
            
            # Label
            label_surf = self.font_small.render(label, True, (180, 180, 180))
            label_rect = label_surf.get_rect(midtop=(button_x + key_width // 2, button_y + 40))
            self.screen.blit(label_surf, label_rect)
            
            button_x += 140
    
    def _draw_confirm_delete(self):
        """Silme onayı çiz - Modern overlay tasarım"""
        width, height = self.screen.get_size()
        
        # Yarı saydam koyu overlay
        overlay = pygame.Surface((width, height), pygame.SRCALPHA).convert_alpha()
        overlay.fill((5, 10, 20, 220))
        self.screen.blit(overlay, (0, 0))
        
        # Onay kutusu - daha büyük ve merkezi
        box_width = 600
        box_height = 280
        box_rect = pygame.Rect(width // 2 - box_width // 2, height // 2 - box_height // 2, box_width, box_height)
        
        # Gölge
        shadow_rect = box_rect.inflate(10, 10)
        pygame.draw.rect(self.screen, (0, 0, 0), shadow_rect, border_radius=20)
        
        # Ana kutu
        pygame.draw.rect(self.screen, (40, 50, 70), box_rect, border_radius=20)
        pygame.draw.rect(self.screen, (255, 100, 100), box_rect, 4, border_radius=20)
        
        # Uyarı ikonu
        warning_rect = pygame.Rect(0, 0, 80, 80)
        warning_rect.center = (width // 2, box_rect.top + 60)
        pygame.draw.circle(self.screen, (255, 200, 100), warning_rect.center, 32)
        pygame.draw.circle(self.screen, (60, 30, 20), warning_rect.center, 32, 4)
        
        # Başlık
        title_surf = self.font_normal.render(t('user_will_delete'), True, (255, 150, 150))
        title_rect = title_surf.get_rect(center=(width // 2, box_rect.top + 120))
        self.screen.blit(title_surf, title_rect)
        
        # Mesajlar
        msg1 = t('user_delete_confirm_line1', username=self.confirm_username)
        msg2 = t('user_delete_confirm_line2')
        
        msg1_surf = self.font_normal.render(msg1, True, WHITE)
        msg2_surf = self.font_normal.render(msg2, True, WHITE)
        
        self.screen.blit(msg1_surf, msg1_surf.get_rect(center=(width // 2, box_rect.top + 160)))
        self.screen.blit(msg2_surf, msg2_surf.get_rect(center=(width // 2, box_rect.top + 190)))
        
        # Uyarı metni
        warning_surf = self.font_small.render(t('user_delete_warning'), True, (255, 200, 100))
        warning_rect = warning_surf.get_rect(center=(width // 2, box_rect.bottom - 70))
        self.screen.blit(warning_surf, warning_rect)
        
        # Butonlar
        button_y = box_rect.bottom - 40
        button_width = 120
        button_height = 35
        gap = 30
        
        # Hayır butonu (sol)
        no_button = pygame.Rect(width // 2 - button_width - gap // 2, button_y - button_height // 2, button_width, button_height)
        pygame.draw.rect(self.screen, (100, 200, 100), no_button, border_radius=10)
        pygame.draw.rect(self.screen, (150, 255, 150), no_button, 2, border_radius=10)
        
        no_text = self.font_normal.render(t('user_no'), True, WHITE)
        self.screen.blit(no_text, no_text.get_rect(center=no_button.center))
        
        # Evet butonu (sağ)
        yes_button = pygame.Rect(width // 2 + gap // 2, button_y - button_height // 2, button_width, button_height)
        pygame.draw.rect(self.screen, (200, 100, 100), yes_button, border_radius=10)
        pygame.draw.rect(self.screen, (255, 150, 150), yes_button, 2, border_radius=10)
        
        yes_text = self.font_normal.render(t('user_yes'), True, WHITE)
        self.screen.blit(yes_text, yes_text.get_rect(center=yes_button.center))
    
    def _draw_view_profile(self):
        """Profil görüntüleme ekranını çiz - Geliştirilmiş tasarım"""
        width, height = self.screen.get_size()
        
        # Koyu gradient arka plan (siyah)
        for i in range(height):
            color_r = int(5 + (i / height) * 5)
            color_g = int(5 + (i / height) * 5)
            color_b = int(10 + (i / height) * 10)
            pygame.draw.line(self.screen, (color_r, color_g, color_b), (0, i), (width, i))
        
        user_data = self.user_manager.get_user_data(self.edit_username)
        if not user_data:
            return
        
        # Ana profil kartı - daha modern tasarım
        card_width = min(900, width - 100)
        card_height = height - 140
        card_x = width // 2 - card_width // 2
        card_y = 70
        
        # Kart gölgesi
        shadow_rect = pygame.Rect(card_x + 5, card_y + 5, card_width, card_height)
        pygame.draw.rect(self.screen, (0, 0, 0, 100), shadow_rect, border_radius=20)
        
        # Ana kart
        card_rect = pygame.Rect(card_x, card_y, card_width, card_height)
        pygame.draw.rect(self.screen, (25, 30, 45), card_rect, border_radius=20)
        pygame.draw.rect(self.screen, (70, 100, 180), card_rect, 3, border_radius=20)
        
        # Üst banner - renkli
        banner_height = 180
        banner_rect = pygame.Rect(card_x, card_y, card_width, banner_height)
        avatar_color = user_data.get('avatar_color', (100, 150, 255))
        
        # Banner gradient
        for i in range(banner_height):
            alpha = i / banner_height
            color = tuple(int(c * (0.3 + alpha * 0.7)) for c in avatar_color)
            pygame.draw.line(self.screen, color, 
                           (card_x, card_y + i), 
                           (card_x + card_width, card_y + i))
        
        # Banner üst köşeleri yuvarla
        pygame.draw.rect(self.screen, (70, 100, 180), banner_rect, 3, border_radius=20)
        
        # Avatar - daha büyük ve merkezi
        avatar = user_data.get('avatar', '__default__')
        avatar_size = 140
        
        # Avatar arka planı - daire çerçeve
        avatar_bg_x = width // 2 - avatar_size // 2 - 10
        avatar_bg_y = card_y + banner_height - avatar_size // 2 - 10
        avatar_bg_size = avatar_size + 20
        avatar_bg_rect = pygame.Rect(avatar_bg_x, avatar_bg_y, avatar_bg_size, avatar_bg_size)
        avatar_center = avatar_bg_rect.center
        avatar_radius = avatar_bg_size // 2
        
        # Outer glow (daire)
        for i in range(3):
            glow_radius = avatar_radius + i * 6
            glow_color = tuple(min(255, c + 40) for c in avatar_color)
            pygame.draw.circle(self.screen, glow_color, avatar_center, glow_radius, 2)

        # Ana avatar arka plan (daire)
        pygame.draw.circle(self.screen, WHITE, avatar_center, avatar_radius)
        pygame.draw.circle(self.screen, avatar_color, avatar_center, avatar_radius, 4)

        avatar_img = _load_avatar_image(avatar, avatar_size + 18)
        if avatar_img is None:
            avatar_img = _render_placeholder_avatar(avatar_size + 18)
        avatar_surf = _circle_crop_surface(avatar_img, avatar_size + 18)
        self.screen.blit(avatar_surf, avatar_surf.get_rect(center=avatar_center))
        
        # İçerik başlangıç y konumu
        content_y = card_y + banner_height + avatar_size // 2 + 30
        
        # Kullanıcı adı - daha büyük ve stilize
        name_surf = self.font_title.render(self.edit_username, True, WHITE)
        name_rect = name_surf.get_rect(center=(width // 2, content_y))
        self.screen.blit(name_surf, name_rect)
        
        # Bio - italik efekti ve quote marks
        bio = user_data.get('bio', '')
        if bio:
            bio_text = f'"{bio}"'
            bio_surf = self.font_normal.render(bio_text, True, (225, 235, 250))
        else:
            bio_text = t('user_no_bio')
            bio_surf = self.font_small.render(bio_text, True, (120, 120, 140))
        bio_rect = bio_surf.get_rect(center=(width // 2, content_y + 50))
        self.screen.blit(bio_surf, bio_rect)
        
        # Favori mod badge
        fav_mode = user_data.get('favorite_mode', t('mode_label_classic'))
        badge_y = content_y + 95
        badge_width = 250
        badge_height = 40
        badge_rect = pygame.Rect(width // 2 - badge_width // 2, badge_y, badge_width, badge_height)
        pygame.draw.rect(self.screen, (255, 100, 100), badge_rect, border_radius=20)
        pygame.draw.rect(self.screen, (255, 150, 150), badge_rect, 2, border_radius=20)
        
        fav_text = self.font_small.render(f'{t("user_favorite")}: {fav_mode}', True, WHITE)
        self.screen.blit(fav_text, fav_text.get_rect(center=badge_rect.center))
        
        # İstatistik kartları - Grid layout
        stats_y = content_y + 155
        
        # Ana istatistikler - 3x2 grid
        main_stats = [
            (t('total_games'), user_data.get('total_games', 0)),
            (t('total_score'), f"{user_data.get('total_score', 0):,}".replace(',', '.')),
            (t('total_lines'), user_data.get('total_lines', 0)),
            (t('highest_combo'), user_data.get('highest_combo', 0)),
            (t('total_tetrises'), user_data.get('total_tetrises', 0)),
            (t('highest_level'), user_data.get('highest_level', 1)),
        ]
        
        stat_card_width = 280
        stat_card_height = 75
        gap = 15
        cols = 3
        
        for i, (label, value) in enumerate(main_stats):
            row = i // cols
            col = i % cols
            
            x = card_x + 30 + col * (stat_card_width + gap)
            y = stats_y + row * (stat_card_height + gap)
            
            # Stat kartı
            stat_rect = pygame.Rect(x, y, stat_card_width, stat_card_height)
            pygame.draw.rect(self.screen, (35, 45, 70), stat_rect, border_radius=12)
            pygame.draw.rect(self.screen, (60, 80, 130), stat_rect, 2, border_radius=12)
            
            # Label ve Value
            label_surf = self.font_small.render(label, True, (150, 160, 180))
            value_surf = self.font_normal.render(str(value), True, WHITE)
            
            label_rect = label_surf.get_rect(topleft=(x + 18, y + 12))
            value_rect = value_surf.get_rect(topleft=(x + 18, y + 38))
            
            self.screen.blit(label_surf, label_rect)
            self.screen.blit(value_surf, value_rect)
        
        # Mod bazlı istatistikler bölümü
        mode_section_y = stats_y + 2 * (stat_card_height + gap) + 30
        
        # Başlık
        mode_title_surf = self.font_normal.render(t('user_mode_stats'), True, (235, 240, 250))
        mode_title_rect = mode_title_surf.get_rect(center=(width // 2, mode_section_y))
        self.screen.blit(mode_title_surf, mode_title_rect)
        
        # Mod istatistikleri
        game_stats = user_data.get('game_stats', {})
        mode_cards_y = mode_section_y + 40
        
        # Oynanan modları topla
        modes_to_show = []
        for mode, stats in game_stats.items():
            if mode == 'pvp':
                if stats.get('games', 0) > 0:
                    modes_to_show.append((mode, stats))
            else:
                if stats.get('games', 0) > 0:
                    modes_to_show.append((mode, stats))
        
        if modes_to_show:
            mode_card_width = 200
            mode_card_height = 60
            max_modes_per_row = 4
            
            for i, (mode, stats) in enumerate(modes_to_show[:8]):  # Max 8 mod
                row = i // max_modes_per_row
                col = i % max_modes_per_row
                
                x = card_x + 30 + col * (mode_card_width + gap)
                y = mode_cards_y + row * (mode_card_height + gap)
                
                # Mod kartı
                mode_rect = pygame.Rect(x, y, mode_card_width, mode_card_height)
                pygame.draw.rect(self.screen, (40, 50, 80), mode_rect, border_radius=10)
                pygame.draw.rect(self.screen, (80, 100, 150), mode_rect, 2, border_radius=10)
                
                # Mod adı
                mode_name = mode.upper()
                mode_name_surf = self.font_small.render(mode_name, True, (200, 220, 255))
                mode_name_rect = mode_name_surf.get_rect(midtop=(x + mode_card_width // 2, y + 8))
                self.screen.blit(mode_name_surf, mode_name_rect)
                
                # Mod stat
                if mode == 'pvp':
                    stat_text = f"{stats.get('wins', 0)}K / {stats.get('losses', 0)}M"
                else:
                    stat_text = t('user_mode_games', games=stats.get('games', 0))
                
                stat_surf = self.font_small.render(stat_text, True, WHITE)
                stat_rect = stat_surf.get_rect(midbottom=(x + mode_card_width // 2, y + mode_card_height - 8))
                self.screen.blit(stat_surf, stat_rect)
        else:
            # Henüz oyun oynamamış
            no_games = self.font_small.render(t('user_no_games'), True, (100, 100, 120))
            no_games_rect = no_games.get_rect(center=(width // 2, mode_cards_y + 30))
            self.screen.blit(no_games, no_games_rect)
        
        # Mesaj gösterimi
        if self.message:
            msg_bg_rect = pygame.Rect(width // 2 - 200, height - 115, 400, 50)
            pygame.draw.rect(self.screen, (50, 200, 100), msg_bg_rect, border_radius=25)
            msg_surf = self.font_normal.render(self.message, True, WHITE)
            msg_rect = msg_surf.get_rect(center=msg_bg_rect.center)
            self.screen.blit(msg_surf, msg_rect)
        
        # Alt bar - talimatlar
        bottom_bar_y = height - 55
        inst_bg_rect = pygame.Rect(0, bottom_bar_y, width, 55)
        pygame.draw.rect(self.screen, (20, 25, 40), inst_bg_rect)
        pygame.draw.line(self.screen, (70, 100, 180), (0, bottom_bar_y), (width, bottom_bar_y), 2)
        
        # Talimat butonları
        buttons = [
            ('E', t('user_action_edit'), (100, 200, 100)),
            ('ESC', t('menu_back'), (200, 100, 100))
        ]
        
        button_x = width // 2 - 150
        for key, label, color in buttons:
            # Key badge
            key_surf = self.font_small.render(key, True, WHITE)
            key_bg = pygame.Rect(button_x, bottom_bar_y + 12, 60, 30)
            pygame.draw.rect(self.screen, color, key_bg, border_radius=5)
            self.screen.blit(key_surf, key_surf.get_rect(center=key_bg.center))
            
            # Label
            label_surf = self.font_small.render(label, True, (200, 200, 200))
            self.screen.blit(label_surf, (button_x + 70, bottom_bar_y + 17))
            
            button_x += 200
    
    def _draw_edit_profile(self):
        """Profil düzenleme ekranını çiz - Geliştirilmiş tasarım"""
        width, height = self.screen.get_size()
        
        # Koyu gradient arka plan (siyah)
        for i in range(height):
            color_r = int(5 + (i / height) * 5)
            color_g = int(5 + (i / height) * 5)
            color_b = int(10 + (i / height) * 10)
            pygame.draw.line(self.screen, (color_r, color_g, color_b), (0, i), (width, i))
        
        # Üst başlık
        header_height = 100
        for i in range(header_height):
            alpha = i / header_height
            color = (int(20 + alpha * 30), int(30 + alpha * 40), int(60 + alpha * 40))
            pygame.draw.line(self.screen, color, (0, i), (width, i))
        
        title = self.font_title.render(f'{self.edit_username} - {t("user_edit_profile")}', True, WHITE)
        title_rect = title.get_rect(center=(width // 2, 50))
        self.screen.blit(title, title_rect)
        
        # Ana kart
        card_width = min(800, width - 100)
        card_x = width // 2 - card_width // 2
        card_y = 130
        
        # Düzenleme alanları
        current_avatar_choice = self.avatars[self.temp_avatar_index] if self.avatars else '__default__'
        fields_data = [
            (0, t('user_field_avatar'), current_avatar_choice, 'avatar'),
            (1, t('user_field_color'), '', 'color'),
            (2, t('user_field_bio'), self.temp_bio if self.temp_bio else t('user_field_empty'), 'text'),
            (3, t('user_field_favorite_mode'), self.temp_favorite_mode, 'text')
        ]
        
        field_height = 90
        field_gap = 20
        
        for idx, (field_id, label, value, field_type) in enumerate(fields_data):
            is_selected = (self.edit_field == field_id)
            y = card_y + idx * (field_height + field_gap)
            
            # Alan kartı
            field_rect = pygame.Rect(card_x, y, card_width, field_height)
            
            # Arka plan rengi
            if is_selected:
                bg_color = (60, 90, 160)
                border_color = (100, 150, 255)
                border_width = 4
            else:
                bg_color = (30, 40, 60)
                border_color = (60, 80, 120)
                border_width = 2
            
            # Gölge (seçili ise)
            if is_selected:
                shadow_rect = field_rect.inflate(6, 6)
                pygame.draw.rect(self.screen, (0, 0, 0, 80), shadow_rect, border_radius=15)
            
            pygame.draw.rect(self.screen, bg_color, field_rect, border_radius=15)
            pygame.draw.rect(self.screen, border_color, field_rect, border_width, border_radius=15)
            
            # Label (sol taraf)
            label_surf = self.font_normal.render(label, True, WHITE if is_selected else (180, 180, 180))
            label_rect = label_surf.get_rect(midleft=(field_rect.x + 30, field_rect.centery))
            self.screen.blit(label_surf, label_rect)
            
            # Value (sağ taraf)
            if field_type == 'avatar':
                avatar_bg_size = 75
                avatar_bg_x = field_rect.right - avatar_bg_size - 80
                avatar_bg_y = field_rect.centery - avatar_bg_size // 2
                avatar_bg_rect = pygame.Rect(avatar_bg_x, avatar_bg_y, avatar_bg_size, avatar_bg_size)
                center = avatar_bg_rect.center
                radius = avatar_bg_size // 2
                pygame.draw.circle(self.screen, self.avatar_colors[self.temp_color_index], center, radius)
                display_value = self.custom_avatar_path if self.custom_avatar_path else value
                avatar_img = _load_avatar_image(display_value, avatar_bg_size - 2)
                if avatar_img is None:
                    avatar_img = _render_placeholder_avatar(avatar_bg_size - 2)
                avatar_surf = _circle_crop_surface(avatar_img, avatar_bg_size - 2)
                self.screen.blit(avatar_surf, avatar_surf.get_rect(center=center))
                pygame.draw.circle(self.screen, WHITE, center, radius, 2)
                
            elif field_type == 'color':
                # Renk önizleme - büyük daire
                color_size = 60
                color_x = field_rect.right - 100
                color_y = field_rect.centery - color_size // 2
                color_rect = pygame.Rect(color_x, color_y, color_size, color_size)
                
                pygame.draw.ellipse(self.screen, self.avatar_colors[self.temp_color_index], color_rect)
                pygame.draw.ellipse(self.screen, WHITE, color_rect, 3)
                
                # Renk adı
                color_names = [
                    t('color_blue'),
                    t('color_red'),
                    t('color_green'),
                    t('color_yellow'),
                    t('color_pink'),
                    t('color_cyan'),
                    t('color_orange'),
                    t('color_purple'),
                ]
                color_name = color_names[self.temp_color_index]
                name_surf = self.font_small.render(color_name, True, WHITE if is_selected else (180, 180, 180))
                name_rect = name_surf.get_rect(midright=(color_x - 15, field_rect.centery))
                self.screen.blit(name_surf, name_rect)
                
            else:  # text
                # Metin değeri
                display_value = value
                if field_id == 2 and is_selected:  # Bio editing
                    display_value = self.temp_bio + '|'  # Cursor
                
                # Metin uzunsa kısalt
                max_chars = 35
                if len(display_value) > max_chars:
                    display_value = display_value[:max_chars] + '...'
                
                value_surf = self.font_normal.render(display_value, True, WHITE if is_selected else (200, 200, 200))
                value_rect = value_surf.get_rect(midright=(field_rect.right - 30, field_rect.centery))
                self.screen.blit(value_surf, value_rect)
            
            # Ok işaretleri (seçili ise ve bio değilse)
            if is_selected and field_id != 2:
                arrow_size = 30
                left_arrow_x = field_rect.right - 250
                right_arrow_x = field_rect.right - 50
                
                # Sol ok
                left_bg = pygame.Rect(left_arrow_x, field_rect.centery - 15, arrow_size, arrow_size)
                pygame.draw.rect(self.screen, (100, 150, 255), left_bg, border_radius=5)
                arrow_left = self.font_normal.render('<', True, WHITE)
                self.screen.blit(arrow_left, arrow_left.get_rect(center=left_bg.center))
                
                # Sağ ok
                right_bg = pygame.Rect(right_arrow_x, field_rect.centery - 15, arrow_size, arrow_size)
                pygame.draw.rect(self.screen, (100, 150, 255), right_bg, border_radius=5)
                arrow_right = self.font_normal.render('>', True, WHITE)
                self.screen.blit(arrow_right, arrow_right.get_rect(center=right_bg.center))
        
        # Yardım metni
        help_y = card_y + 4 * (field_height + field_gap) + 20
        help_texts = []
        
        if self.edit_field == 0:
            help_texts = [
                t('user_help_avatar_switch'),
                t('user_help_avatar_count', count=len(self.avatars)),
                t('user_help_avatar_custom'),
            ]
        elif self.edit_field == 1:
            help_texts = [
                t('user_help_color_switch'),
                t('user_help_color_count', count=8),
            ]
        elif self.edit_field == 2:
            help_texts = [
                t('user_help_bio_input'),
                t('user_help_bio_count', count=len(self.temp_bio), max=50),
            ]
        elif self.edit_field == 3:
            help_texts = [
                t('user_help_mode_switch'),
                t('user_help_mode_count', count=len(self.modes)),
            ]
        
        for i, text in enumerate(help_texts):
            help_surf = self.font_small.render(text, True, (150, 170, 200))
            help_rect = help_surf.get_rect(center=(width // 2, help_y + i * 30))
            self.screen.blit(help_surf, help_rect)
        
        # Alt bar - kontroller
        bottom_bar_y = height - 90
        
        # Gradient alt bar
        for i in range(90):
            alpha = 1 - (i / 90)
            color = (int(20 * alpha), int(25 * alpha), int(40 * alpha))
            pygame.draw.line(self.screen, color, (0, bottom_bar_y + i), (width, bottom_bar_y + i))
        
        pygame.draw.line(self.screen, (70, 100, 180), (0, bottom_bar_y), (width, bottom_bar_y), 2)
        
        # Kontrol butonları
        buttons = [
            (t('keys_tab_up_down'), t('user_control_change_field'), (100, 120, 200)),
            (t('keys_left_right'), t('user_control_change_value'), (150, 100, 200)),
            ('C', t('user_control_custom_avatar'), (150, 100, 255)),
            ('ENTER', t('save'), (100, 200, 100)),
            ('ESC', t('cancel'), (200, 100, 100))
        ]
        
        total_width = sum(150 for _ in buttons) - 20
        button_x = width // 2 - total_width // 2
        button_y = bottom_bar_y + 15
        
        for key, label, color in buttons:
            # Key badge
            key_width = 90 if len(key) > 3 else 60
            key_bg = pygame.Rect(button_x, button_y, key_width, 35)
            pygame.draw.rect(self.screen, color, key_bg, border_radius=8)
            pygame.draw.rect(self.screen, tuple(min(255, c + 40) for c in color), key_bg, 2, border_radius=8)
            
            key_surf = self.font_small.render(key, True, WHITE)
            self.screen.blit(key_surf, key_surf.get_rect(center=key_bg.center))
            
            # Label
            label_surf = self.font_small.render(label, True, (180, 180, 180))
            label_rect = label_surf.get_rect(midtop=(button_x + key_width // 2, button_y + 40))
            self.screen.blit(label_surf, label_rect)
            
            button_x += 150
    




