"""Ekstralar menüsü - Modern Izgara Görünümü"""
import pygame
import math
import os
import sys
from pathlib import Path
from constants import *
from retro_style import retro_style
from background_effects import get_shared_falling_blocks_layer
from platform_utils import is_fullscreen_toggle, normalize_mouse_pos
from ui_theme import UIColors, UIFonts, UIStyle, lerp_color
from ui_components import draw_glass_card
from asset_manager import load_image
from localization import t, get_language


def _get_base_path() -> Path:
    """PyInstaller uyumlu temel dizin."""
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return Path(sys._MEIPASS)
    return Path(__file__).parent.parent

# AI görsel simgelerinin promptları (Nano Banana Pro için)
MODE_IMAGE_PROMPTS = {
    'Classic Mode': {
        'prompt': 'A timeless tetris block arrangement in clean white and light blue gradient, minimalist retro style with subtle grid pattern, classic game aesthetic, soft glow, transparent background, 256x256 icon',
        'filename': 'classic_mode_icon.png',
        'alt_emoji': '🎮'
    },
    'Campaign Mode': {
        'prompt': 'A glowing neon compass over a stylized valley landscape with a winding path and star marker, gold and emerald gradients, futuristic UI frame, soft particle glow, transparent background, 256x256 icon',
        'filename': 'campaign_mode_icon.png',
        'alt_emoji': '🧭'
    },
    'Sprint Mode': {
        'prompt': 'A neon lightning bolt icon in vibrant electric yellow and white, with speed lines and energy particles, cyberpunk style, glowing edges, transparent background, 256x256 icon',
        'filename': 'sprint_mode_icon.png',
        'alt_emoji': '⚡'
    },
    'Ultra Mode': {
        'prompt': 'A glowing stopwatch or timer icon in bright red and orange gradient, with circular motion blur effect, digital numbers, neon cyber style, transparent background, 256x256 icon',
        'filename': 'ultra_mode_icon.png',
        'alt_emoji': '⏱️'
    },
    'Zen Mode': {
        'prompt': 'A peaceful meditation symbol in soft cyan and purple gradients, with subtle glow and floating particles, calming aura effect, minimalist zen design, transparent background, 256x256 icon',
        'filename': 'zen_mode_icon.png',
        'alt_emoji': '🧘'
    },
    'Quadrix Extra': {
        'prompt': 'Colorful tetris blocks arranged in creative formation with rainbow neon glow, futuristic puzzle pieces, vibrant magenta and cyan colors, cyberpunk aesthetic, transparent background, 256x256 icon',
        'filename': 'tetris2_mode_icon.png',
        'alt_emoji': '🧩'
    },
    'Kart Ustalığı': {
        'prompt': 'A sleek playing card or tarot-style icon with neon cyan and magenta glow, futuristic UI framing, minimal but premium, transparent background, 256x256 icon',
        'filename': 'mystery_mode_icon.png',
        'alt_emoji': '🃏'
    },
    'Wide Mode': {
        'prompt': 'Wide horizontal arrows pointing left and right in bright cyan blue, with expansion effect and geometric lines, neon glow, modern minimalist design, transparent background, 256x256 icon',
        'filename': 'wide_mode_icon.png',
        'alt_emoji': '↔️'
    },
    'Survival Mode': {
        'prompt': 'A glowing red heart with pulse lines and health bar effects, dramatic red and orange glow, intense survival theme, cyberpunk medical icon style, transparent background, 256x256 icon',
        'filename': 'survival_mode_icon.png',
        'alt_emoji': '❤️'
    },
    'Cascade Mode': {
        'prompt': 'Flowing water cascade or waterfall effect in bright blue and cyan colors, with particles falling down, fluid motion, neon glowing waves, dynamic design, transparent background, 256x256 icon',
        'filename': 'cascade_mode_icon.png',
        'alt_emoji': '🌊'
    },
    'Hardcore Mode': {
        'prompt': 'A jagged, glitching skull symbol fused with swapped/reversed directional arrows (left pointing right), large question mark silhouette in background, aggressive neon blood-red primary with chaotic violet/cyan glitch effects, clean cyber UI icon, transparent background, 256x256 icon',
        'filename': 'hardcore_mode_icon.png',
        'alt_emoji': '💀'
    }
}


class ExtrasScreen:
    """Ekstralar (Oyun Modları) ekranı - Modern Grid UI with Glassmorphism"""
    
    # Mod ID'lerini game_stats anahtarlarına eşleyen mapping
    MODE_ID_TO_STATS_KEY = {
        'Classic Mode': 'classic',
        'Sprint Mode': 'sprint',
        'Ultra Mode': 'ultra',
        'Zen Mode': 'zen',
        'Quadrix Extra': 'tetris2',
        'Kart Ustalığı': 'mystery',
        'Wide Mode': 'wide',
        'Survival Mode': 'survival',
        'Cascade Mode': 'cascade',
        'Hardcore Mode': 'hardcore',
    }
    
    def __init__(self, screen, user_manager=None):
        """Ekstralar ekranını başlat"""
        self.screen = screen
        self.user_manager = user_manager
        self._base_window_size = self.screen.get_size()
        
        # Modern UI fontları (daha net / daha büyük)
        self._refresh_fonts()
        self._lang_cache = get_language()
        self._layout_signature = (self.screen.get_width(), self.screen.get_height(), self._lang_cache)

        # Kart ikon boyutu (daha büyük)
        self.base_icon_size = 84
        self.icon_size = self.base_icon_size
        
        # Simge yolu (PyInstaller uyumlu)
        self.icons_dir = _get_base_path() / 'assets' / 'ui' / 'mode_icons'
        # Sadece development modunda klasör oluştur
        if not getattr(sys, 'frozen', False):
            self.icons_dir.mkdir(parents=True, exist_ok=True)
        
        # Modlar ve verileri (UI temasına uygun renkler) - dil bağımsız
        self._items_base = [
            {
                'id': 'Campaign Mode',
                'name_key': 'campaign_mode',
                'desc_key': 'campaign_desc',
                'color': (187, 255, 0),  # #E5FF00
                'image_data': MODE_IMAGE_PROMPTS.get('Campaign Mode')
            },
            {
                'id': 'Classic Mode',
                'name_key': 'mode_label_classic',
                'desc_key': 'extras_classic_desc',
                'color': (100, 180, 255),  # Açık mavi — klasik/temiz hiss
                'image_data': MODE_IMAGE_PROMPTS.get('Classic Mode')
            },
            {
                'id': 'Sprint Mode', 
                'name_key': 'mode_label_sprint',
                'desc_key': 'extras_sprint_desc',
                'color': UIColors.NEON_GOLD,
                'image_data': MODE_IMAGE_PROMPTS.get('Sprint Mode')
            },
            {
                'id': 'Ultra Mode', 
                'name_key': 'mode_label_ultra',
                'desc_key': 'extras_ultra_desc',
                'color': UIColors.NEON_RED,
                'image_data': MODE_IMAGE_PROMPTS.get('Ultra Mode')
            },
            {
                'id': 'Zen Mode', 
                'name_key': 'mode_label_zen',
                'desc_key': 'extras_zen_desc',
                'color': UIColors.NEON_GREEN,
                'image_data': MODE_IMAGE_PROMPTS.get('Zen Mode')
            },
            {
                'id': 'Quadrix Extra', 
                'name_key': 'mode_tetris_extra',
                'desc_key': 'extras_tetris2_desc',
                'color': UIColors.NEON_MAGENTA,
                'image_data': MODE_IMAGE_PROMPTS.get('Quadrix Extra')
            },
            {
                'id': 'Kart Ustalığı',
                'name_key': 'mode_card_mastery',
                'desc_key': 'extras_mystery_desc',
                'color': lerp_color(UIColors.NEON_MAGENTA, UIColors.NEON_CYAN, 0.35),
                'image_data': MODE_IMAGE_PROMPTS.get('Kart Ustalığı')
            },
            {
                'id': 'Wide Mode', 
                'name_key': 'mode_label_wide',
                'desc_key': 'extras_wide_desc',
                'color': UIColors.NEON_CYAN,
                'image_data': MODE_IMAGE_PROMPTS.get('Wide Mode')
            },
            {
                'id': 'Survival Mode', 
                'name_key': 'mode_label_survival',
                'desc_key': 'extras_survival_desc',
                # Pembeye kaçan kırmızı (magenta yönüne hafif kaydırılmış)
                'color': lerp_color(UIColors.NEON_RED, UIColors.NEON_MAGENTA, 0.32),
                'hover_color': lerp_color(UIColors.NEON_RED, UIColors.NEON_MAGENTA, 0.55),
                'image_data': MODE_IMAGE_PROMPTS.get('Survival Mode')
            },
            {
                'id': 'Cascade Mode', 
                'name_key': 'mode_label_cascade',
                'desc_key': 'extras_cascade_desc',
                # Koyu mavi: mevcut NEON_BLUE tonunu arka plan laciverte yaklaştır
                'color': lerp_color(NEON_BLUE, UIColors.BG_DARK, 0.55),
                'image_data': MODE_IMAGE_PROMPTS.get('Cascade Mode')
            },
            {
                'id': 'Hardcore Mode', 
                'name_key': 'mode_label_hardcore',
                'desc_key': 'extras_hardcore_desc',
                'color': (180, 30, 30),  # Koyu kırmızı
                'hover_color': (220, 50, 50),
                'image_data': MODE_IMAGE_PROMPTS.get('Hardcore Mode')
            },
        ]
        
        # Simge yükle
        self._load_mode_icons()
        
        self.selected = 0
        self.option_rects = []
        self.scroll_offset = 0
        self.background_fx = get_shared_falling_blocks_layer('default')
        
        # Grid ayarları (UI temasına göre)
        base_w, _ = self._base_window_size
        if base_w > 1200:
            self.base_cols = 4
            self.base_card_size = (285, 240)
        elif base_w > 900:
            self.base_cols = 3
            self.base_card_size = (320, 250)
        else:
            self.base_cols = 2
            self.base_card_size = (360, 270)

        self.cols = self.base_cols
        self.card_size = self.base_card_size
        self.base_spacing = UIStyle.SPACING_LARGE
        self.spacing = self.base_spacing
        
        # Hover animasyon
        self.hover_progress = {}
        for i in range(len(self._items_base)):
            self.hover_progress[i] = 0.0

    def _extras_ui_scale(self, min_scale: float = 0.60, max_scale: float = 1.0) -> float:
        """Tam ekran referansına göre UI ölçeği (yalnızca küçülür)."""
        base_w, base_h = self._base_window_size
        base_w = max(1, int(base_w))
        base_h = max(1, int(base_h))
        w_ratio = self.screen.get_width() / float(base_w)
        h_ratio = self.screen.get_height() / float(base_h)
        return max(min_scale, min(max_scale, min(w_ratio, h_ratio)))

    def _apply_scaled_layout(self) -> None:
        """Mevcut pencereye göre kart, ikon ve boşluk ölçeğini uygula."""
        width = self.screen.get_width()
        ui_scale = self._extras_ui_scale()

        self.icon_size = max(52, int(round(self.base_icon_size * ui_scale)))
        self.spacing = max(10, int(round(self.base_spacing * ui_scale)))
        self.card_size = (
            max(220, int(round(self.base_card_size[0] * ui_scale))),
            max(185, int(round(self.base_card_size[1] * ui_scale))),
        )

        self.cols = self.base_cols
        while self.cols > 1:
            grid_w = self.cols * self.card_size[0] + (self.cols - 1) * self.spacing
            if grid_w <= width - max(20, int(24 * ui_scale)):
                break
            self.cols -= 1

    def _refresh_fonts(self) -> None:
        ui_scale = self._extras_ui_scale()
        def s(value: int, minimum: int) -> int:
            return max(minimum, int(round(value * ui_scale)))

        self.font_title = retro_style.get_font(s(48, 26), bold=True)
        self.font_option = retro_style.get_font(s(34, 16), bold=True)
        self.font_desc = retro_style.get_font(s(22, 11), bold=False)
        self.font_desc_strong = retro_style.get_font(s(22, 11), bold=True)
    
    @property
    def items(self):
        """Yerelleştirilmiş mod listesini döndürür"""
        result = []
        for item in self._items_base:
            localized = dict(item)
            # İsim yerelleştirmesi (bazı modlar için name_key var)
            if 'name_key' in item:
                localized['name'] = t(item['name_key'])
            # Açıklama yerelleştirmesi
            if 'desc_key' in item:
                localized['desc'] = t(item['desc_key'])
            result.append(localized)
        return result
    
    def _load_mode_icons(self):
        """Mod simgelerini yükle veya emoji fallback kullan"""
        for item in self._items_base:
            item['icon_surface'] = None
            if item['image_data']:
                icon_path = self.icons_dir / item['image_data']['filename']
                if icon_path.exists():
                    try:
                        img = load_image(str(icon_path), convert_alpha=False)
                        # Daha büyük ikon
                        item['icon_surface'] = pygame.transform.smoothscale(img, (self.icon_size, self.icon_size))
                    except Exception as e:
                        print(f"⚠️ Simge yüklenemedi: {icon_path} - {e}")
    
    def get_ai_prompts_info(self):
        """AI görsel promptlarını döndür (kullanıcıya gösterim için)"""
        info = []
        info.append("=" * 70)
        info.append("🎨 NANO BANANA PRO İLE MOD SİMGELERİ ÜRETİMİ")
        info.append("=" * 70)
        info.append("")
        info.append("Her mod için aşağıdaki promptları kullanarak simge oluşturun:")
        info.append("")
        
        for item in self.items:
            if item['image_data']:
                info.append(f"📌 {item['name']}:")
                info.append(f"   Dosya: {item['image_data']['filename']}")
                info.append(f"   Prompt: {item['image_data']['prompt']}")
                info.append(f"   Kayıt: {self.icons_dir / item['image_data']['filename']}")
                info.append("")
        
        info.append("=" * 70)
        info.append("💡 Not: Resimleri oluşturduktan sonra yukarıdaki kayıt yollarına yerleştirin.")
        info.append("=" * 70)
        
        return "\n".join(info)
    
    def handle_input(self, event):
        """Ekstralar input işle"""
        if event.type == pygame.KEYDOWN:
            rows = math.ceil(len(self.items) / self.cols)
            
            if event.key in (pygame.K_UP, pygame.K_w):
                if self.selected >= self.cols:
                    self.selected -= self.cols
                self._ensure_visible()
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                if self.selected + self.cols < len(self.items):
                    self.selected += self.cols
                self._ensure_visible()
            elif event.key in (pygame.K_LEFT, pygame.K_a):
                if self.selected % self.cols > 0:
                    self.selected -= 1
                self._ensure_visible()
            elif event.key in (pygame.K_RIGHT, pygame.K_d):
                if self.selected % self.cols < self.cols - 1 and self.selected + 1 < len(self.items):
                    self.selected += 1
                self._ensure_visible()
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                return self.items[self.selected]['id']
            elif event.key == pygame.K_ESCAPE:
                return 'Geri'
            elif is_fullscreen_toggle(event.key, getattr(event, 'mod', 0)):
                return 'toggle_fullscreen'
        
        elif event.type == pygame.MOUSEWHEEL:
            self.scroll_offset -= event.y * 30
            self._clamp_scroll()
        
        elif event.type == pygame.MOUSEMOTION:
            mouse_pos = normalize_mouse_pos(getattr(event, 'pos', None)) or event.pos
            # Mouse herhangi bir kartın üzerinde değilse selected'ı değiştirme
            # Bu sayede mouse karttan çıkınca anında tepki verir
            hovered_any = False
            for i, rect in enumerate(self.option_rects):
                if rect.collidepoint(mouse_pos):
                    self.selected = i
                    hovered_any = True
                    break
        
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                mouse_pos = normalize_mouse_pos(getattr(event, 'pos', None)) or event.pos
                for i, rect in enumerate(self.option_rects):
                    if rect.collidepoint(mouse_pos):
                        return self.items[i]['id']
        
        return None
    
    def _clamp_scroll(self):
        """Scroll sınırlarını kontrol et"""
        width, height = self.screen.get_size()
        ui_scale = self._extras_ui_scale()
        s = lambda v, minimum=1: max(minimum, int(round(v * ui_scale)))
        rows = math.ceil(len(self.items) / self.cols)
        total_height = rows * (self.card_size[1] + self.spacing) + s(100)
        visible_height = height - s(150)
        max_scroll = max(0, total_height - visible_height)
        self.scroll_offset = max(0, min(self.scroll_offset, max_scroll))
    
    def _ensure_visible(self):
        """Seçili öğenin görünür olmasını sağla"""
        width, height = self.screen.get_size()
        ui_scale = self._extras_ui_scale()
        s = lambda v, minimum=1: max(minimum, int(round(v * ui_scale)))
        
        # Grid layout hesabı (draw ile eşleşmeli)
        start_y = s(180)
        row = self.selected // self.cols
        
        item_top = start_y + row * (self.card_size[1] + self.spacing) - self.scroll_offset
        item_bottom = item_top + self.card_size[1]
        
        visible_top = start_y
        visible_bottom = height - s(100)
        
        if item_top < visible_top:
            self.scroll_offset -= (visible_top - item_top) + s(20)
        elif item_bottom > visible_bottom:
            self.scroll_offset += (item_bottom - visible_bottom) + s(20)
            
        self._clamp_scroll()
    
    def draw(self):
        """Ekstralar ekranını çiz - Modern Glassmorphism Grid Layout"""
        width, height = self.screen.get_size()
        current_lang = get_language()
        layout_signature = (width, height, current_lang)
        if self._layout_signature != layout_signature:
            self._layout_signature = layout_signature
            self._lang_cache = current_lang
            self._apply_scaled_layout()
            self._refresh_fonts()
            self._load_mode_icons()
        retro_style.draw_background(self.screen)
        self.background_fx.update(self.screen)
        self.background_fx.draw(self.screen)

        ui_scale = self._extras_ui_scale()
        s = lambda v, minimum=1: max(minimum, int(round(v * ui_scale)))
        
        # Her frame'de mouse pozisyonunu kontrol et (MOUSEMOTION event'i gelmese bile)
        # Bu sayede hover efekti anında tepki verir
        try:
            mouse_pos = pygame.mouse.get_pos()
            mouse_pos = normalize_mouse_pos(mouse_pos) or mouse_pos
            mouse_over_any = False
            for i, rect in enumerate(self.option_rects):
                if rect and rect.width > 0 and rect.collidepoint(mouse_pos):
                    if self.selected != i:
                        self.selected = i
                    mouse_over_any = True
                    break
        except Exception:
            pass
        
        self._apply_scaled_layout()
            
        # Başlık - diğer pencerelerle aynı stil (örn. Başarılar)
        title_rect = retro_style.draw_title(self.screen, t('extras_title'), (width // 2, s(60)), emoji=None)
        
        # Alt başlık
        sub_text = t('extras_subtitle')
        sub_surf = self.font_desc.render(sub_text, True, UIColors.TEXT_SECONDARY)
        sub_rect = sub_surf.get_rect(center=(width // 2, title_rect.bottom + s(25)))
        self.screen.blit(sub_surf, sub_rect)
        
        # Grid başlangıç
        start_y = sub_rect.bottom + s(40)
        self.option_rects = []
        
        # Toplam grid genişliği
        grid_width = self.cols * self.card_size[0] + (self.cols - 1) * self.spacing
        start_x = (width - grid_width) // 2
        
        for idx, item in enumerate(self.items):
            col = idx % self.cols
            row = idx // self.cols
            
            x_pos = start_x + col * (self.card_size[0] + self.spacing)
            y_pos = start_y + row * (self.card_size[1] + self.spacing) - self.scroll_offset
            
            # Görünürlük kontrolü
            if y_pos + self.card_size[1] < start_y - s(50) or y_pos > height:
                self.option_rects.append(pygame.Rect(0, 0, 0, 0))
                continue
                
            card_rect = pygame.Rect(x_pos, y_pos, self.card_size[0], self.card_size[1])
            self.option_rects.append(card_rect)
            
            is_selected = idx == self.selected
            
            # Hover animasyonu güncelle - daha hızlı tepki için lerp faktörü artırıldı
            if idx not in self.hover_progress:
                self.hover_progress[idx] = 0.0
            
            target_hover = 1.0 if is_selected else 0.0
            # Hover'dan çıkış daha hızlı (0.35), giriş biraz daha yumuşak (0.25)
            lerp_speed = 0.35 if target_hover < self.hover_progress[idx] else 0.25
            self.hover_progress[idx] += (target_hover - self.hover_progress[idx]) * lerp_speed
            
            # Modern glassmorphism kart çizimi
            self._draw_modern_mode_card(card_rect, item, is_selected, self.hover_progress[idx])
            
        # Modern scrollbar
        total_grid_h = math.ceil(len(self.items) / self.cols) * (self.card_size[1] + self.spacing)
        visible_h = height - start_y - s(20)
        if total_grid_h > visible_h:
            sb_x = width - s(20)
            sb_w = s(6)
            sb_rect = pygame.Rect(sb_x, start_y, sb_w, visible_h)
            
            # Scrollbar background
            pygame.draw.rect(self.screen, (*UIColors.BG_LIGHT, 100), sb_rect, border_radius=3)
            
            # Scrollbar handle
            handle_height = max(s(30), int(visible_h * visible_h / total_grid_h))
            handle_y = start_y + int(self.scroll_offset * visible_h / total_grid_h)
            handle_rect = pygame.Rect(sb_x, handle_y, sb_w, handle_height)
            pygame.draw.rect(self.screen, UIColors.NEON_CYAN, handle_rect, border_radius=3)

        # Footer intentionally omitted

    
    def _draw_modern_mode_card(self, rect, item, selected, hover_progress):
        """Modern glassmorphism mod kartı çiz"""
        ui_scale = self._extras_ui_scale()
        s = lambda v, minimum=1: max(minimum, int(round(v * ui_scale)))
        # Kartın ana rengi neyse: çerçeve/vurgu + soluk wash da o renk olsun
        mode_color = item.get('color', UIColors.NEON_CYAN)
        hovered = hover_progress > 0.12
        draw_glass_card(
            self.screen,
            rect,
            hovered=hovered,
            selected=selected,
            accent_color=mode_color,
        )

        # Seçili kartta çok hafif mod rengi wash (ana temayı bozmaz)
        if selected and hover_progress > 0:
            wash = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
            pygame.draw.rect(
                wash,
                (*mode_color, int(18 + 14 * hover_progress)),
                wash.get_rect(),
                border_radius=UIStyle.BORDER_RADIUS_MEDIUM,
            )
            half_h = max(1, rect.height // 2)
            self.screen.blit(
                wash,
                rect.topleft,
                area=pygame.Rect(0, 0, rect.width, half_h),
            )
        
        # İçerik çizimi
        # Simge bölgesi
        icon_y = rect.y + s(58)
        
        if item.get('icon_surface'):
            # PNG simge varsa göster
            icon_rect = item['icon_surface'].get_rect(center=(rect.centerx, icon_y))
            
            # Simge glow
            if selected:
                glow_surf = item['icon_surface'].copy()
                glow_surf.fill((*mode_color, int(110 * hover_progress)), special_flags=pygame.BLEND_RGBA_MULT)
                for offset in [(2, 2), (-2, 2), (2, -2), (-2, -2)]:
                    self.screen.blit(glow_surf, (icon_rect.x + offset[0], icon_rect.y + offset[1]))
            
            self.screen.blit(item['icon_surface'], icon_rect)
        else:
            # Fallback (tofu-safe): emoji basma, harf/şekil kullan
            short = ''.join([w[0] for w in (item.get('name', 'M').split()) if w])[:2].upper() or 'M'
            icon_font = retro_style.get_font(s(54, 20), bold=True)
            icon_surf = icon_font.render(short, True, UIColors.TEXT_PRIMARY)
            icon_rect = icon_surf.get_rect(center=(rect.centerx, icon_y))
            
            # İkon arkası daire
            circle_alpha = int(60 + hover_progress * 40)
            pygame.draw.circle(self.screen, (*item.get('color', UIColors.NEON_CYAN), circle_alpha), 
                             icon_rect.center, s(46))
            pygame.draw.circle(self.screen, (*UIColors.GLASS_BORDER[:3], 90), icon_rect.center, s(46), max(1, s(2)))
            
            self.screen.blit(icon_surf, icon_rect)
        
        # Başlık (okunaklılık: label plate + güçlü outline)
        name_color = UIColors.TEXT_PRIMARY
        name_surf = self.font_option.render(item['name'], True, name_color)
        name_shadow = self.font_option.render(item['name'], True, (0, 0, 0))
        name_shadow.set_alpha(180)
        name_rect = name_surf.get_rect(center=(rect.centerx, rect.y + s(148)))

        # Label plate: metni arka plandan ayır
        plate_pad_x = s(16)
        plate_pad_y = s(8)
        plate_w = min(rect.width - s(22), name_rect.width + plate_pad_x * 2)
        plate_h = max(s(28), name_rect.height + plate_pad_y)
        plate = pygame.Rect(0, 0, plate_w, plate_h)
        plate.center = name_rect.center
        plate_surf = pygame.Surface((plate.width, plate.height), pygame.SRCALPHA)
        plate_alpha = int(120 + (40 * hover_progress if selected else 0))
        pygame.draw.rect(plate_surf, (*UIColors.BG_DARK, plate_alpha), plate_surf.get_rect(), border_radius=12)
        pygame.draw.rect(plate_surf, (255, 255, 255, 22), plate_surf.get_rect(), width=1, border_radius=12)
        self.screen.blit(plate_surf, plate.topleft)

        self.screen.blit(name_shadow, name_shadow.get_rect(center=(name_rect.centerx + 1, name_rect.centery + 1)))
        # outline (daha güçlü)
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, -1), (-1, 1), (1, 1)):
            self.screen.blit(name_shadow, name_shadow.get_rect(center=(name_rect.centerx + dx, name_rect.centery + dy)))
        for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2)):
            self.screen.blit(name_shadow, name_shadow.get_rect(center=(name_rect.centerx + dx, name_rect.centery + dy)))
        self.screen.blit(name_surf, name_rect)

        # Açıklama (detaylı + 2 satıra sar)
        desc_color = UIColors.TEXT_SECONDARY if not selected else UIColors.TEXT_PRIMARY
        max_width = rect.width - s(28)
        lines = self._wrap_text(item['desc'], self.font_desc, max_width, max_lines=2)
        base_y = plate.bottom + s(10)
        for li, line in enumerate(lines):
            surf = self.font_desc.render(line, True, desc_color)
            shadow = self.font_desc.render(line, True, (0, 0, 0))
            shadow.set_alpha(170)
            y = base_y + li * s(20)
            r = surf.get_rect(center=(rect.centerx, y))
            self.screen.blit(shadow, shadow.get_rect(center=(r.centerx + 1, r.centery + 1)))
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                self.screen.blit(shadow, shadow.get_rect(center=(r.centerx + dx, r.centery + dy)))
            self.screen.blit(surf, r)
        
        # En yüksek skor gösterimi
        mode_id = item.get('id', '')
        stats_key = self.MODE_ID_TO_STATS_KEY.get(mode_id)
        if stats_key and self.user_manager:
            highscore = self.user_manager.get_mode_highscore(stats_key)
            if highscore > 0:
                # Highscore rozeti - kartın kendi rengini kullan
                hs_text = f"{t('best_score')}: {highscore:,}"
                hs_font = retro_style.get_font(s(24, 11), bold=True)
                hs_surf = hs_font.render(hs_text, True, mode_color)  # Kartın rengi
                hs_shadow = hs_font.render(hs_text, True, (0, 0, 0))
                hs_shadow.set_alpha(200)
                
                # Rozet arka planı - daha belirgin
                badge_pad_x, badge_pad_y = s(18), s(8)
                badge_w = hs_surf.get_width() + badge_pad_x * 2
                badge_h = hs_surf.get_height() + badge_pad_y * 2
                badge_y = rect.y + s(215)
                badge_rect = pygame.Rect(rect.centerx - badge_w // 2, badge_y, badge_w, badge_h)
                
                badge_surf = pygame.Surface((badge_w, badge_h), pygame.SRCALPHA)
                # Arka plan - glassmorphism tarzı
                pygame.draw.rect(badge_surf, (*UIColors.BG_DARK, 200), badge_surf.get_rect(), border_radius=10)
                # Üst highlight
                pygame.draw.rect(badge_surf, (255, 255, 255, 20), badge_surf.get_rect(), width=1, border_radius=10)
                # Kartın rengiyle çerçeve
                pygame.draw.rect(badge_surf, (*mode_color, 140), badge_surf.get_rect(), width=2, border_radius=10)
                self.screen.blit(badge_surf, badge_rect.topleft)
                
                # Skor metni - güçlü outline
                text_rect = hs_surf.get_rect(center=badge_rect.center)
                # Gölge
                self.screen.blit(hs_shadow, hs_shadow.get_rect(center=(text_rect.centerx + 1, text_rect.centery + 1)))
                # Outline
                for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                    self.screen.blit(hs_shadow, hs_shadow.get_rect(center=(text_rect.centerx + dx, text_rect.centery + dy)))
                self.screen.blit(hs_surf, text_rect)
        


    def _wrap_text(self, text: str, font: pygame.font.Font, max_width: int, max_lines: int = 2):
        """Basit kelime sarma: max_lines ile sınırla."""
        words = (text or '').split()
        if not words:
            return ['']

        lines: list[str] = []
        current: list[str] = []

        for word in words:
            test = ' '.join(current + [word])
            if font.size(test)[0] <= max_width or not current:
                current.append(word)
                continue

            lines.append(' '.join(current))
            current = [word]
            if len(lines) >= max_lines:
                break

        if current and len(lines) < max_lines:
            lines.append(' '.join(current))

        # Eğer hala taşma varsa son satırı kısalt
        if len(lines) == max_lines:
            last = lines[-1]
            while last and font.size(last + '…')[0] > max_width:
                last = last.rsplit(' ', 1)[0] if ' ' in last else last[:-1]
            lines[-1] = (last + '…') if last and last != lines[-1] else lines[-1]

        return lines
