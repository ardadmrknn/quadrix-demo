"""Modern/Smooth esintili paylaşılmış UI araçları.

Glassmorphism, yumuşak gradientler ve neon vurgular içeren
premium UI tasarımı.
"""
from __future__ import annotations

import os
import unicodedata
import pygame
from localization import t
import math
from background import BackgroundManager
from constants import NEON_CYAN, NEON_MAGENTA, NEON_ORANGE, NEON_LIME, NEON_BLUE


def _is_cjk_char(ch: str) -> bool:
    """Karakterin CJK (Çince/Japonca/Korece) olup olmadığını kontrol et."""
    cp = ord(ch)
    # CJK Unified Ideographs
    if 0x4E00 <= cp <= 0x9FFF:
        return True
    # CJK Unified Extension A/B
    if 0x3400 <= cp <= 0x4DBF or 0x20000 <= cp <= 0x2A6DF:
        return True
    # Hiragana
    if 0x3040 <= cp <= 0x309F:
        return True
    # Katakana
    if 0x30A0 <= cp <= 0x30FF:
        return True
    # Katakana Phonetic Extensions
    if 0x31F0 <= cp <= 0x31FF:
        return True
    # CJK Symbols and Punctuation
    if 0x3000 <= cp <= 0x303F:
        return True
    # Hangul Syllables
    if 0xAC00 <= cp <= 0xD7AF:
        return True
    # Hangul Jamo
    if 0x1100 <= cp <= 0x11FF:
        return True
    # Hangul Compatibility Jamo
    if 0x3130 <= cp <= 0x318F:
        return True
    # CJK Compatibility
    if 0x3300 <= cp <= 0x33FF:
        return True
    # Fullwidth Forms
    if 0xFF00 <= cp <= 0xFFEF:
        return True
    # Half-width Katakana
    if 0xFF65 <= cp <= 0xFF9F:
        return True
    return False


def _segment_text(text: str) -> list[tuple[bool, str]]:
    """Metni CJK ve latin segmentlerine böl.

    Returns:
        [(is_cjk, segment_text), ...]
    """
    if not text:
        return []
    segments: list[tuple[bool, str]] = []
    current_is_cjk = _is_cjk_char(text[0])
    current_chars: list[str] = [text[0]]
    for ch in text[1:]:
        ch_cjk = _is_cjk_char(ch)
        if ch_cjk == current_is_cjk:
            current_chars.append(ch)
        else:
            segments.append((current_is_cjk, ''.join(current_chars)))
            current_is_cjk = ch_cjk
            current_chars = [ch]
    segments.append((current_is_cjk, ''.join(current_chars)))
    return segments


class HybridFont:
    """CJK dilleri aktifken latin ve CJK karakterlerini ayrı fontlarla render eden proxy.

    pygame.font.Font arayüzünü taklit eder; render() çağrıldığında metni
    CJK/latin segmentlerine böler, her segmenti uygun fontla render eder ve
    birleştirilmiş bir Surface döndürür.
    """

    def __init__(self, latin_font: pygame.font.Font, cjk_font: pygame.font.Font) -> None:
        self._latin = latin_font
        self._cjk = cjk_font
        self._render_cache: dict[tuple, pygame.Surface] = {}

    # ---- pygame.font.Font uyumlu API ----

    def render(self, text: str, antialias: bool, color, background=None) -> pygame.Surface:
        """Metni segmentlere böl; latin kısmını latin fontuyla, CJK kısmını CJK fontuyla render et."""
        if not text:
            return self._latin.render('', antialias, color, background)

        key = (text, antialias, tuple(color[:3]) if color else color, background)
        cached = self._render_cache.get(key)
        if cached is not None:
            return cached

        segments = _segment_text(text)
        # Tek segment ise doğrudan kaynak fontla render et (performans)
        if len(segments) == 1:
            is_cjk, seg = segments[0]
            font = self._cjk if is_cjk else self._latin
            result = font.render(seg, antialias, color, background)
            self._render_cache[key] = result
            self._trim_cache()
            return result

        # Birden fazla segment: her birini ayrı render et ve birleştir
        rendered_parts: list[pygame.Surface] = []
        total_width = 0
        max_height = 0
        for is_cjk, seg in segments:
            font = self._cjk if is_cjk else self._latin
            part = font.render(seg, antialias, color)
            rendered_parts.append(part)
            total_width += part.get_width()
            max_height = max(max_height, part.get_height())

        combined = pygame.Surface((total_width, max_height), pygame.SRCALPHA)
        if background:
            combined.fill(background)
        x = 0
        for part in rendered_parts:
            # Dikey hizalama: alt kenara hizala (baseline alignment)
            y = max_height - part.get_height()
            combined.blit(part, (x, y))
            x += part.get_width()

        self._render_cache[key] = combined
        self._trim_cache()
        return combined

    def size(self, text: str) -> tuple[int, int]:
        """Metnin render boyutunu hesapla."""
        if not text:
            return self._latin.size('')
        segments = _segment_text(text)
        total_w = 0
        max_h = 0
        for is_cjk, seg in segments:
            font = self._cjk if is_cjk else self._latin
            w, h = font.size(seg)
            total_w += w
            max_h = max(max_h, h)
        return (total_w, max_h)

    def get_height(self) -> int:
        return max(self._latin.get_height(), self._cjk.get_height())

    def get_linesize(self) -> int:
        return max(self._latin.get_linesize(), self._cjk.get_linesize())

    def get_ascent(self) -> int:
        return max(self._latin.get_ascent(), self._cjk.get_ascent())

    def get_descent(self) -> int:
        return max(self._latin.get_descent(), self._cjk.get_descent())

    def set_bold(self, value: bool) -> None:
        self._latin.set_bold(value)
        # CJK fontlarda bold genellikle bozuk görünür; yine de set et
        try:
            self._cjk.set_bold(value)
        except Exception:
            pass

    def get_bold(self) -> bool:
        return self._latin.get_bold()

    def set_italic(self, value: bool) -> None:
        self._latin.set_italic(value)

    def get_italic(self) -> bool:
        return self._latin.get_italic()

    def set_underline(self, value: bool) -> None:
        self._latin.set_underline(value)

    def metrics(self, text: str):
        """Karakter bazlı metrikleri döndür."""
        result = []
        for ch in text:
            font = self._cjk if _is_cjk_char(ch) else self._latin
            m = font.metrics(ch)
            result.extend(m)
        return result

    def get_rect(self, text: str, **kwargs):
        w, h = self.size(text)
        rect = pygame.Rect(0, 0, w, h)
        for k, v in kwargs.items():
            setattr(rect, k, v)
        return rect

    def _trim_cache(self) -> None:
        if len(self._render_cache) > 256:
            # En eski girişlerin yarısını sil
            keys = list(self._render_cache.keys())
            for k in keys[:128]:
                self._render_cache.pop(k, None)


class RetroStyle:
    """Modern/Glassmorphism stilleri merkezden yöneten yardımcı."""

    def __init__(self) -> None:
        # Koyu arka plan (derin lacivert)
        self.bg_color = (8, 12, 28)
        self.bg_secondary = (12, 18, 38)
        self.grid_color = (30, 40, 65)
        self.scanline_color = (0, 0, 0, 12)  # Daha hafif scanline
        
        # Neon accent renkler
        self.primary = NEON_CYAN       # Ana vurgu (cyan)
        self.secondary = NEON_MAGENTA  # İkincil (magenta)
        self.accent = NEON_ORANGE      # Aksan (turuncu)
        self.success = NEON_LIME       # Başarı rengi

        # Text colors (some screens reference these directly)
        self.text_primary = (230, 235, 245)
        self.text_secondary = (180, 200, 220)
        self.text_muted = (120, 140, 170)
        
        # Cam panel renkleri (glassmorphism)
        self.glass_bg = (15, 20, 40, 140)
        self.glass_border = (80, 120, 180, 100)
        self.glass_highlight = (255, 255, 255, 25)
        
        # Panel arka plan
        self.panel_bg = (12, 16, 32, 180)

        # Menü/UI şeffaflığı (buton/panel/row gibi yüzeylerin alfa çarpanı)
        # 0.0 (tamamen saydam) - 1.0 (opak)
        self._menu_transparency = 1.0
        
        # Font cache
        self.font_cache: dict[tuple[int, bool], pygame.font.Font] = {}
        self._font_path: str | None = None
        self._default_font_path: str | None = None  # Latin fallback (CJK hibrit için)
        self._font_scale: float = 1.0
        self._force_no_bold: bool = False

        # Çoklu-script font cache: aktif dilden bağımsız olarak metinde geçen
        # Latin-dışı karakterler (CJK, Hangul, Hiragana/Katakana) için lazy
        # yüklenen font'lar. _get_script_font() her karakter için doğru fontu seçer.
        self._script_font_paths: dict[str, str] = {
            'cjk_kr': os.path.join('font', 'paperlogy', 'Paperlogy-4Regular.ttf'),
            'cjk_jp': os.path.join('font', 'ki-cho-jis_0310', 'KikaiChokokuJIS-Md.otf'),
            'cjk_zh': os.path.join('font', 'cinecaption Regular', 'ChildFunSans-CHS.ttf'),
        }
        self._script_font_cache: dict[tuple[str, int, bool], pygame.font.Font] = {}

        # Render cache (font.render pahalı; özellikle menülerde aynı metinler tekrar tekrar çiziliyor)
        self._render_cache: dict[tuple, pygame.Surface] = {}
        self._render_cache_order: list[tuple] = []
        self._render_cache_max = 512
        
        # Background cache
        self._bg_cache: dict[tuple[int, int], pygame.Surface] = {}
        self._scan_cache: dict[tuple[int, int], pygame.Surface] = {}

        # Global image background (menus/screens): prefer outer_background.* like gameplay.
        self._image_background = BackgroundManager()
        self._bg_transparency = 0.3
        try:
            self._image_background.set_transparency(self._bg_transparency)
        except Exception:
            pass
        self._image_background_attempted = False

        # Glass panel caches (avoid per-frame Surface allocations)
        self._glass_panel_cache: dict[tuple, pygame.Surface] = {}
        self._glass_panel_cache_order: list[tuple] = []
        self._glass_panel_cache_max = 128
        self._glass_glow_cache: dict[tuple, pygame.Surface] = {}
        self._glass_glow_cache_order: list[tuple] = []
        self._glass_glow_cache_max = 128

        # Animasyon zamanı
        self._time = 0

    def _scale_menu_alpha(self, alpha: int) -> int:
        try:
            a = int(alpha)
        except Exception:
            a = 0
        a = max(0, min(255, a))

        try:
            m = float(getattr(self, '_menu_transparency', 1.0))
        except Exception:
            m = 1.0
        m = max(0.0, min(1.0, m))
        return int(a * m)

    def set_menu_transparency(self, value: float) -> None:
        """Menü/UI yüzeylerinin şeffaflığını ayarla.

        Not: Bu ayar arka plan görselini etkilemez; yalnızca RetroStyle ile
        çizilen panel/buton/satır gibi UI yüzeylerinin alfa değerlerini çarpar.
        """
        try:
            v = float(value)
        except Exception:
            return
        v = max(0.0, min(1.0, v))
        self._menu_transparency = v

        # Cache'ler alpha'ya bağlı: temizle ki değişiklik hemen yansısın.
        try:
            self._glass_panel_cache.clear()
            self._glass_panel_cache_order.clear()
        except Exception:
            pass
        try:
            self._glass_glow_cache.clear()
            self._glass_glow_cache_order.clear()
        except Exception:
            pass

    def set_background_transparency(self, value: float) -> None:
        """Menü/ekran arka planı transparanlığını ayarla.

        Amaç: Ana sayfa vb. ekranlardaki arka plan, oyun alanlarının kullandığı
        bg_transparency ile aynı davransın .
        """
        try:
            v = float(value)
        except Exception:
            return
        v = max(0.0, min(1.0, v))
        self._bg_transparency = v
        try:
            self._image_background.set_transparency(v)
        except Exception:
            pass

        # Glass panel caches (avoid per-frame Surface allocations)
        self._glass_panel_cache: dict[tuple, pygame.Surface] = {}
        self._glass_panel_cache_order: list[tuple] = []
        self._glass_panel_cache_max = 128
        self._glass_glow_cache: dict[tuple, pygame.Surface] = {}
        self._glass_glow_cache_order: list[tuple] = []
        self._glass_glow_cache_max = 128
        
        # Animasyon zamanı
        self._time = 0

    def update_time(self, dt_ms: float) -> None:
        """Animasyon zamanını güncelle"""
        self._time += dt_ms / 1000.0

    def _blit_with_subtractive_fallback(
        self,
        target: pygame.Surface,
        overlay: pygame.Surface,
        pos: tuple[int, int] = (0, 0),
    ) -> None:
        """Subtractive blit mümkünse onu kullan, değilse normal alpha blit'e düş."""
        blend_sub = getattr(pygame, 'BLEND_RGBA_SUB', None)
        if blend_sub is not None:
            try:
                target.blit(overlay, pos, special_flags=blend_sub)
                return
            except Exception:
                pass
        target.blit(overlay, pos)

    def _get_latin_font(self, scaled_size: int, effective_bold: bool) -> pygame.font.Font:
        """Varsayılan latin fontunu döndür (CJK hibrit sistem için)."""
        key = (scaled_size, effective_bold, '__latin__')
        if key not in self.font_cache:
            font_obj = None
            # Önceden kaydedilmiş varsayılan font path varsa kullan
            if self._default_font_path:
                try:
                    font_obj = pygame.font.Font(self._default_font_path, scaled_size)
                    if effective_bold:
                        font_obj.set_bold(True)
                except Exception:
                    font_obj = None
            if font_obj is None:
                candidates = [
                    "Segoe UI",
                    "Arial",
                    "Helvetica",
                    "DejaVu Sans",
                    "Consolas",
                ]
                for name in candidates:
                    path = pygame.font.match_font(name)
                    if path:
                        font_obj = pygame.font.Font(path, scaled_size)
                        break
                if font_obj is None:
                    font_obj = pygame.font.SysFont(None, scaled_size, bold=effective_bold)
            self.font_cache[key] = font_obj
        return self.font_cache[key]

    def get_font(self, size: int, bold: bool = True) -> pygame.font.Font:
        if not pygame.font.get_init():
            pygame.font.init()
        scaled_size = self._apply_font_scale(size)
        effective_bold = False if self._force_no_bold else bool(bold)
        key = (scaled_size, effective_bold, self._font_path, self._default_font_path)
        if key not in self.font_cache:
            font_obj = None
            if self._font_path:
                try:
                    cjk_font = pygame.font.Font(self._font_path, scaled_size)
                    if effective_bold:
                        cjk_font.set_bold(True)
                    # CJK font path aktif → HybridFont oluştur
                    latin_font = self._get_latin_font(scaled_size, effective_bold)
                    font_obj = HybridFont(latin_font, cjk_font)
                except Exception:
                    font_obj = None
            if font_obj is None:
                font_obj = self._get_latin_font(scaled_size, effective_bold)
            self.font_cache[key] = font_obj
        # Cached font objects may become invalid if pygame.font was quit and
        # re-initialized during the test run. Validate cached font and
        # recreate if necessary.
        font_obj = self.font_cache.get(key)
        if font_obj is not None:
            try:
                # size('') is a cheap check that will raise if font module is dead
                font_obj.size('')
                return font_obj
            except Exception:
                try:
                    del self.font_cache[key]
                except Exception:
                    pass
                # fallthrough: recreate below

        # Recreate font object if cache was invalidated
        font_obj = None
        if self._font_path:
            try:
                cjk_font = pygame.font.Font(self._font_path, scaled_size)
                if effective_bold:
                    cjk_font.set_bold(True)
                latin_font = self._get_latin_font(scaled_size, effective_bold)
                font_obj = HybridFont(latin_font, cjk_font)
            except Exception:
                font_obj = None
        if font_obj is None:
            font_obj = self._get_latin_font(scaled_size, effective_bold)
        self.font_cache[key] = font_obj
        return font_obj

    def get_mono_font(self, size: int, bold: bool = True) -> pygame.font.Font:
        """Sayısal sayaçlar vb. için eş aralıklı (monospaced) font döndür."""
        if not pygame.font.get_init():
            pygame.font.init()
        # Use a distinguishable key for mono fonts
        scaled_size = self._apply_font_scale(size)
        key = (scaled_size, bold, 'mono')
        if key not in self.font_cache:
            candidates = [
                "Consolas",
                "Courier New",
                "Liberation Mono",
                "Menlo",
                "Monaco",
                "Lucida Console",
            ]
            font_obj = None
            for name in candidates:
                path = pygame.font.match_font(name)
                if path:
                    font_obj = pygame.font.Font(path, scaled_size)
                    break
            if font_obj is None:
                # System fallback
                font_obj = pygame.font.SysFont("monospace", scaled_size, bold=bold)
            self.font_cache[key] = font_obj
        return self.font_cache[key]

    def _apply_font_scale(self, size: int) -> int:
        try:
            scale = float(self._font_scale)
        except (TypeError, ValueError):
            scale = 1.0
        scale = max(0.5, min(2.0, scale))
        try:
            scaled = int(round(int(size) * scale))
        except (TypeError, ValueError):
            scaled = int(round(22 * scale))
        return max(6, scaled)

    def set_font_profile(
        self,
        font_path: str | None = None,
        default_font_path: str | None = None,
        size_scale: float = 1.0,
        force_no_bold: bool = False,
    ) -> None:
        """Dil bazlı font profilini uygula."""
        self._font_path = font_path
        self._default_font_path = default_font_path
        try:
            self._font_scale = float(size_scale)
        except (TypeError, ValueError):
            self._font_scale = 1.0
        self._force_no_bold = bool(force_no_bold)
        try:
            self.font_cache.clear()
        except Exception:
            pass
        try:
            self._render_cache.clear()
            self._render_cache_order.clear()
        except Exception:
            pass

    def get_fitting_font(
        self,
        text: str,
        base_size: int,
        max_width: int | None,
        bold: bool = True,
        min_size: int = 10,
    ) -> pygame.font.Font:
        """Shrink font size until text fits the provided width."""
        if not max_width or max_width <= 0:
            return self.get_font(base_size, bold=bold)
        size = base_size
        font = self.get_font(size, bold=bold)
        text_width = font.size(text)[0]
        min_size = max(8, min_size)
        while text_width > max_width and size > min_size:
            size -= 2
            font = self.get_font(size, bold=bold)
            text_width = font.size(text)[0]
        return font

    def render_fit_text(
        self,
        text: str,
        color: tuple[int, int, int],
        max_width: int | None,
        base_size: int,
        bold: bool = True,
        min_size: int = 10,
    ) -> pygame.Surface:
        font = self.get_fitting_font(text, base_size, max_width, bold=bold, min_size=min_size)

        # Cache key: font identity + text + color. max_width/base_size/bold etkisi font'a yansıyor.
        key = (id(font), text, color)
        cached = self._render_cache.get(key)
        if cached is not None:
            return cached

        surf = font.render(text, True, color)
        self._render_cache[key] = surf
        self._render_cache_order.append(key)
        if len(self._render_cache_order) > self._render_cache_max:
            old = self._render_cache_order.pop(0)
            self._render_cache.pop(old, None)
        return surf

    # ========================================================================
    # Çoklu-script font/render desteği — aktif dil ne olursa olsun, metinde
    # geçen Hangul/Hiragana/Katakana/CJK Unified karakterleri uygun fontla
    # render eder. Steam leaderboard isim listeleri gibi kullanıcı tarafından
    # üretilen, dil-bağımsız yazılarda "kutucuk" sorununu çözer.
    # ========================================================================

    def _classify_char_script(self, ch: str) -> str:
        """Karakter için uygun script anahtarını döndür.

        Dönüş değerleri:
          'latin' → mevcut Latin/temel fontla render edilebilir
          'cjk_kr' / 'cjk_jp' / 'cjk_zh' → ilgili CJK alt-script
        """
        if not ch:
            return 'latin'
        cp = ord(ch)
        # Hangul (Korece)
        if (0xAC00 <= cp <= 0xD7AF) or (0x1100 <= cp <= 0x11FF) or (0x3130 <= cp <= 0x318F):
            return 'cjk_kr'
        # Hiragana / Katakana / Katakana Phonetic Ext / Half-width Katakana (Japonca)
        if (0x3040 <= cp <= 0x309F) or (0x30A0 <= cp <= 0x30FF) or (0x31F0 <= cp <= 0x31FF) or (0xFF65 <= cp <= 0xFF9F):
            return 'cjk_jp'
        # CJK Unified Ideographs ve Extension A/B (Çince/Japonca ortak Kanji)
        if (0x4E00 <= cp <= 0x9FFF) or (0x3400 <= cp <= 0x4DBF) or (0x20000 <= cp <= 0x2A6DF):
            return 'cjk_zh'
        # CJK Symbols/Punctuation, Compatibility, Fullwidth Forms — varsayılan olarak Çince fontuyla
        if (0x3000 <= cp <= 0x303F) or (0x3300 <= cp <= 0x33FF) or (0xFF00 <= cp <= 0xFFEF):
            return 'cjk_zh'
        return 'latin'

    def _get_script_font(self, script: str, size: int, bold: bool = False) -> pygame.font.Font | None:
        """Belirli bir CJK alt-script için lazy yüklenmiş font'u döndür.

        Yükleme başarısız olursa None döner ve karakter Latin fontuna düşer
        (eski "kutucuk" davranışı; daha iyi bir alternatif yok).
        """
        if script == 'latin':
            return None
        rel_path = self._script_font_paths.get(script)
        if not rel_path:
            return None
        scaled_size = self._apply_font_scale(size)
        effective_bold = False if self._force_no_bold else bool(bold)
        cache_key = (script, scaled_size, effective_bold)
        cached = self._script_font_cache.get(cache_key)
        if cached is not None:
            try:
                cached.size('A')
                return cached
            except Exception:
                self._script_font_cache.pop(cache_key, None)

        try:
            if not pygame.font.get_init():
                pygame.font.init()
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            full_path = os.path.join(project_root, rel_path)
            if not os.path.exists(full_path):
                return None
            font = pygame.font.Font(full_path, scaled_size)
            if effective_bold:
                try:
                    font.set_bold(True)
                except Exception:
                    pass
            self._script_font_cache[cache_key] = font
            return font
        except Exception:
            return None

    def _segment_text_by_script(self, text: str) -> list[tuple[str, str]]:
        """Metni script segmentlerine böl. [(script, segment_text), ...]"""
        if not text:
            return []
        segments: list[tuple[str, str]] = []
        current_script = self._classify_char_script(text[0])
        current_chars: list[str] = [text[0]]
        for ch in text[1:]:
            ch_script = self._classify_char_script(ch)
            if ch_script == current_script:
                current_chars.append(ch)
            else:
                segments.append((current_script, ''.join(current_chars)))
                current_script = ch_script
                current_chars = [ch]
        segments.append((current_script, ''.join(current_chars)))
        return segments

    def _measure_multilingual_text(
        self,
        text: str,
        latin_font: pygame.font.Font,
        base_size: int,
        bold: bool,
    ) -> int:
        """Metnin script-aware genişliğini hesapla (max_width fitting için)."""
        total = 0
        for script, seg in self._segment_text_by_script(text):
            if script == 'latin':
                font = latin_font
            else:
                font = self._get_script_font(script, base_size, bold=bold) or latin_font
            try:
                total += font.size(seg)[0]
            except Exception:
                total += latin_font.size(seg)[0]
        return total

    def render_multilingual_text(
        self,
        text: str,
        color: tuple[int, int, int],
        max_width: int | None,
        base_size: int,
        bold: bool = False,
        min_size: int = 10,
    ) -> pygame.Surface:
        """Aktif dilden bağımsız çoklu-script (Latin + CJK) metin render'ı.

        Latin karakterler için mevcut tema fontu, CJK karakterler için (Hangul,
        Hiragana, Katakana, CJK Unified Ideographs) projedeki ilgili font
        kullanılır. Steam leaderboard isim listesi gibi kullanıcı üretimli
        metinler dil seçimi Türkçe iken bile doğru render edilir.
        """
        text = str(text or '')
        if not text:
            return self.get_font(base_size, bold=bold).render('', True, color)

        # Önce font boyutunu sığdırmaya çalış
        size = base_size
        latin_font = self.get_font(size, bold=bold)
        if max_width and max_width > 0:
            min_size = max(8, min_size)
            while size > min_size and self._measure_multilingual_text(text, latin_font, size, bold) > max_width:
                size -= 1
                latin_font = self.get_font(size, bold=bold)

        # Karakter bazında segmentle ve birleştirilmiş bir surface oluştur
        rendered_parts: list[pygame.Surface] = []
        total_width = 0
        max_height = 0
        for script, seg in self._segment_text_by_script(text):
            if script == 'latin':
                font = latin_font
            else:
                font = self._get_script_font(script, size, bold=bold) or latin_font
            try:
                part = font.render(seg, True, color)
            except Exception:
                part = latin_font.render(seg, True, color)
            rendered_parts.append(part)
            total_width += part.get_width()
            max_height = max(max_height, part.get_height())

        if not rendered_parts:
            return latin_font.render('', True, color)

        combined = pygame.Surface((max(1, total_width), max(1, max_height)), pygame.SRCALPHA)
        x = 0
        for part in rendered_parts:
            # Baseline alignment: parçaları alt kenara hizala
            y = max_height - part.get_height()
            combined.blit(part, (x, y))
            x += part.get_width()
        return combined

    def _lru_get(self, cache: dict[tuple, pygame.Surface], order: list[tuple], key: tuple) -> pygame.Surface | None:
        value = cache.get(key)
        if value is None:
            return None
        try:
            order.remove(key)
        except ValueError:
            pass
        order.append(key)
        return value

    def _lru_put(
        self,
        cache: dict[tuple, pygame.Surface],
        order: list[tuple],
        key: tuple,
        value: pygame.Surface,
        max_items: int,
    ) -> None:
        cache[key] = value
        order.append(key)
        while len(order) > max_items:
            oldest = order.pop(0)
            cache.pop(oldest, None)

    def wrap_text(self, text: str, font: pygame.font.Font, max_width: int) -> list[str]:
        if max_width <= 0:
            return [text]
        lines: list[str] = []
        for paragraph in text.split('\n'):
            words = paragraph.split()
            if not words:
                lines.append('')
                continue
            current = words[0]
            for word in words[1:]:
                test_line = f"{current} {word}"
                if font.size(test_line)[0] <= max_width:
                    current = test_line
                else:
                    lines.append(current)
                    current = word
            lines.append(current)
        return lines

    def draw_wrapped_text(
        self,
        screen: pygame.Surface,
        text: str,
        font: pygame.font.Font,
        color: tuple[int, int, int],
        rect: pygame.Rect,
        align: str = 'center',
        line_spacing: int = 6,
    ) -> pygame.Rect:
        lines = self.wrap_text(text, font, rect.width)
        y = rect.y
        for line in lines:
            line_surface = font.render(line, True, color)
            if align == 'left':
                line_rect = line_surface.get_rect(topleft=(rect.x, y))
            elif align == 'right':
                line_rect = line_surface.get_rect(topright=(rect.right, y))
            else:
                line_rect = line_surface.get_rect(midtop=(rect.centerx, y))
            screen.blit(line_surface, line_rect)
            y += line_surface.get_height() + line_spacing
        return pygame.Rect(rect.x, rect.y, rect.width, y - rect.y)

    # ------------------------------------------------------------------
    # Ortak çizim yardımcıları - MODERN TASARIM
    # ------------------------------------------------------------------
    def draw_background(self, screen: pygame.Surface) -> None:
        """Modern arka plan.

        Varsayılan: backgrounds/outer_background.* görselini tam ekrana çiz.
        (Oyun modlarıyla aynı temel arka plan.)
        Görsel bulunamazsa eski gradient fallback kullan.
        """
        if not self._image_background_attempted:
            self._image_background_attempted = True
            # Prefer png, fallback to jpg, then legacy background.*
            for rel in (
                'backgrounds/outer_background.png',
                'backgrounds/outer_background.jpg',
                'backgrounds/background.png',
                'backgrounds/background.jpg',
            ):
                try:
                    if self._image_background.load_image(rel):
                        break
                except Exception:
                    continue

        if self._image_background.is_loaded():
            # If the background image is drawn with per-surface alpha (< 255),
            # we must clear the screen first; otherwise previous frame pixels
            # remain and get blended, which makes unrelated layers (e.g. falling
            # blocks) look like they change with bg_transparency.
            try:
                if float(getattr(self, '_bg_transparency', 1.0)) < 1.0:
                    screen.fill(self.bg_color)
            except Exception:
                pass
            self._image_background.draw_full_screen(screen)
            return

        size = screen.get_size()
        surface = self._bg_cache.get(size)
        if surface is None:
            width, height = size
            surface = pygame.Surface(size)
            
            # Gradient arka plan (üstten alta - koyu → daha koyu)
            for y in range(height):
                ratio = y / max(height - 1, 1)
                r = int(self.bg_color[0] * (1 - ratio * 0.3) + self.bg_secondary[0] * ratio * 0.3)
                g = int(self.bg_color[1] * (1 - ratio * 0.3) + self.bg_secondary[1] * ratio * 0.3)
                b = int(self.bg_color[2] * (1 - ratio * 0.5) + self.bg_secondary[2] * ratio * 0.5 + 10)
                pygame.draw.line(surface, (r, g, b), (0, y), (width, y))

            # Hafif grid overlay (daha modern görünüm)
            grid_alpha = 18
            step = 40
            try:
                grid_surface = pygame.Surface(size, pygame.SRCALPHA)
                for x in range(0, width, step):
                    pygame.draw.line(grid_surface, (*self.grid_color, grid_alpha), (x, 0), (x, height))
                for y in range(0, height, step):
                    pygame.draw.line(grid_surface, (*self.grid_color, grid_alpha), (0, y), (width, y))
                surface.blit(grid_surface, (0, 0))
            except Exception:
                for x in range(0, width, step):
                    pygame.draw.line(surface, self.grid_color, (x, 0), (x, height))
                for y in range(0, height, step):
                    pygame.draw.line(surface, self.grid_color, (0, y), (width, y))

            # Merkez glow efekti (neon ambient)
            try:
                # Not: Az sayıda halka çizmek büyük çözünürlüklerde "daire çerçeve" gibi banding yapıyordu.
                # Daha fazla adım + daha düşük alfa ile yumuşatıyoruz.
                glow = pygame.Surface((width, height), pygame.SRCALPHA)
                cx, cy = width // 2, int(height * 0.4)
                # Use screen diagonal so the outermost circle boundary is outside the screen.
                # This prevents a visible "big circle" edge on large resolutions.
                max_radius = int(math.hypot(width, height))
                steps = 22
                for i in range(steps):
                    ring_progress = i / max(steps - 1, 1)
                    radius = int(max_radius * (1.0 - ring_progress * 0.95))
                    # Quadratic falloff for smoother center
                    alpha = int(18 * ((1.0 - ring_progress) ** 2))
                    if alpha <= 0 or radius <= 0:
                        continue
                    color = (self.primary[0], self.primary[1], self.primary[2], alpha)
                    pygame.draw.circle(glow, color, (cx, cy), radius)
                surface.blit(glow, (0, 0))
            except Exception:
                pass

            # Köşe vignette (karartma)
            try:
                vignette = pygame.Surface(size, pygame.SRCALPHA)
                for i in range(60):
                    alpha = int(50 * (i / 60))
                    rect = pygame.Rect(i, i, width - i * 2, height - i * 2)
                    if rect.width > 0 and rect.height > 0:
                        pygame.draw.rect(vignette, (0, 0, 0, alpha), rect, 1, border_radius=30)
                self._blit_with_subtractive_fallback(surface, vignette)
            except Exception:
                pass

            self._bg_cache[size] = surface
        screen.blit(surface, (0, 0))
        self._blit_scanlines(screen)

    def _blit_scanlines(self, screen: pygame.Surface) -> None:
        """Hafif CRT scanline efekti (çok hafif)"""
        size = screen.get_size()
        overlay = self._scan_cache.get(size)
        if overlay is None:
            overlay = pygame.Surface(size, pygame.SRCALPHA)
            width, height = size
            for y in range(0, height, 3):
                pygame.draw.rect(overlay, self.scanline_color, (0, y, width, 1))
            self._scan_cache[size] = overlay
        self._blit_with_subtractive_fallback(screen, overlay)

    def draw_glass_panel(
        self, 
        screen: pygame.Surface, 
        rect: pygame.Rect, 
        alpha: int = 140,
        border_color: tuple | None = None,
        glow: bool = False,
        blur_effect: bool = True,
        top_highlight: bool = True,
        draw_border: bool = True,
    ) -> None:
        """Glassmorphism panel çiz.

        `top_highlight` parametresi API uyumluluğu için korunur.
        Popup panellerinde üst parlama bandı artık çizilmez.
        """
        alpha = self._scale_menu_alpha(alpha)

        # Glow efekti (opsiyonel)
        if glow:
            glow_rect = rect.inflate(16, 16)
            glow_color = border_color[:3] if border_color else self.primary
            glow_key = (glow_rect.size, glow_color)
            glow_surf = self._lru_get(self._glass_glow_cache, self._glass_glow_cache_order, glow_key)
            if glow_surf is None:
                glow_surf = pygame.Surface(glow_rect.size, pygame.SRCALPHA)
                pygame.draw.rect(glow_surf, (*glow_color, self._scale_menu_alpha(30)), glow_surf.get_rect(), border_radius=16)
                self._lru_put(self._glass_glow_cache, self._glass_glow_cache_order, glow_key, glow_surf, self._glass_glow_cache_max)
            screen.blit(glow_surf, glow_rect.topleft)
        
        # Ana panel (yarı saydam)
        base_rgb = (self.glass_bg[0], self.glass_bg[1], self.glass_bg[2])
        panel_key = (rect.size, base_rgb, alpha)
        panel = self._lru_get(self._glass_panel_cache, self._glass_panel_cache_order, panel_key)
        if panel is None:
            panel = pygame.Surface(rect.size, pygame.SRCALPHA)
            panel.fill((*base_rgb, alpha))

            self._lru_put(self._glass_panel_cache, self._glass_panel_cache_order, panel_key, panel, self._glass_panel_cache_max)

        screen.blit(panel, rect.topleft)
        
        # Kenar çizgisi
        if draw_border:
            border = border_color if border_color else (*self.glass_border[:3], self._scale_menu_alpha(80))
            pygame.draw.rect(screen, border, rect, 2, border_radius=12)

    def draw_title(self, screen: pygame.Surface, text: str, center: tuple[int, int], emoji: str | None = None) -> pygame.Rect:
        """Modern başlık - glow efektli

        Not: Emoji glyph'leri bazı sistem fontlarında kare/kutucuk olarak görünebildiği için
        UI başlıklarında emoji render edilmez (emoji paramı bilinçli olarak yok sayılır).
        """
        width, _ = screen.get_size()
        max_width = max(0, width - 120)
        # H1: 56px hedefi (dar ekranlarda fit edilecek şekilde)
        font = self.get_fitting_font(text, 56, max_width, bold=True)
        
        # Glow efekti (hafif blur simülasyonu)
        glow_color = (*self.primary, 60)
        # Tek tip glow şiddeti (tüm ekranlarda aynı hissiyat)
        for offset in range(3, 0, -1):
            glow_surf = font.render(text, True, glow_color[:3])
            glow_surf.set_alpha(self._scale_menu_alpha(18 * offset))
            glow_rect = glow_surf.get_rect(center=(center[0], center[1] + offset))
            screen.blit(glow_surf, glow_rect)
        
        # Ana metin
        title_surface = font.render(text, True, self.primary)
        title_rect = title_surface.get_rect(center=center)
        screen.blit(title_surface, title_rect)
        
        # Alt çizgi (gradient)
        line_width = min(title_rect.width + 60, width - 100)
        line_y = title_rect.bottom + 8
        line_surf = pygame.Surface((line_width, 3), pygame.SRCALPHA)
        for x in range(line_width):
            # Ortadan kenarlara gradient
            dist_from_center = abs(x - line_width // 2) / (line_width // 2)
            alpha = int(150 * (1 - dist_from_center))
            pygame.draw.line(line_surf, (*self.primary, alpha), (x, 0), (x, 3))
        screen.blit(line_surf, (center[0] - line_width // 2, line_y))
        
        return title_rect

    def draw_panel(
        self,
        screen: pygame.Surface,
        rect: pygame.Rect,
        title: str | None = None,
        border: bool = True,
        shadow: bool = True,
        title_color: tuple[int, int, int] | None = None,
    ) -> None:
        """Glass panel çiz - modern tasarım"""
        # Gölge
        if shadow:
            shadow_surf = pygame.Surface((rect.width + 8, rect.height + 8), pygame.SRCALPHA)
            pygame.draw.rect(shadow_surf, (0, 0, 0, 40), shadow_surf.get_rect(), border_radius=14)
            screen.blit(shadow_surf, (rect.x + 4, rect.y + 4))
        
        # Glass panel
        self.draw_glass_panel(screen, rect, alpha=160, border_color=self.primary if border else None)
        
        # Başlık
        if title:
            title_font = self.get_fitting_font(title, 22, rect.width - 40)
            color = title_color if title_color is not None else self.accent
            title_surf = title_font.render(title, True, color)
            screen.blit(title_surf, (rect.x + 16, rect.y + 8))

    def draw_button(
        self,
        screen: pygame.Surface,
        rect: pygame.Rect,
        text: str,
        selected: bool = False,
        strip_color: tuple | None = None,
        strip_width: int = 5,
    ) -> None:
        """Modern buton - glassmorphism efektli"""
        # Glow (selected)
        if selected:
            glow_rect = rect.inflate(12, 12)
            glow_surf = pygame.Surface(glow_rect.size, pygame.SRCALPHA)
            glow_color = strip_color or self.primary
            pygame.draw.rect(glow_surf, (*glow_color[:3], self._scale_menu_alpha(40)), glow_surf.get_rect(), border_radius=14)
            screen.blit(glow_surf, glow_rect.topleft)
        
        # Buton arka planı
        alpha = self._scale_menu_alpha(200 if selected else 160)
        fill_color = (28, 35, 55) if selected else (18, 24, 40)
        
        btn_surf = pygame.Surface(rect.size, pygame.SRCALPHA)
        btn_surf.fill((*fill_color, alpha))
        
        # Üst kenar highlight
        for y in range(min(20, rect.height // 3)):
            h_alpha = int(30 * (1 - y / 20)) if selected else int(15 * (1 - y / 20))
            pygame.draw.line(btn_surf, (255, 255, 255, self._scale_menu_alpha(h_alpha)), (0, y), (rect.width, y))
        
        screen.blit(btn_surf, rect.topleft)
        
        # Kenar
        border_color = self.primary if selected else (60, 75, 100)
        pygame.draw.rect(screen, border_color, rect, 2, border_radius=10)
        
        # Sol strip
        strip_col = strip_color or (self.primary if selected else (100, 110, 130))
        lw = strip_width * (2 if selected else 1)
        strip_rect = pygame.Rect(rect.x + 2, rect.y + 4, lw, rect.height - 8)
        pygame.draw.rect(screen, strip_col, strip_rect, border_radius=3)
        
        # Metin
        max_width = rect.width - lw - 30
        text_color = (255, 255, 255) if selected else (200, 210, 225)
        text_surf = self.render_fit_text(
            text,
            text_color,
            max_width,
            26 if selected else 24,
            bold=True,
        )
        text_rect = text_surf.get_rect(midleft=(rect.x + lw + 20, rect.centery))
        screen.blit(text_surf, text_rect)

    def draw_footer(self, screen: pygame.Surface, lines: list[str]) -> None:
        """Footer panel"""
        width, height = screen.get_size()
        panel_height = 20 * len(lines) + 24
        panel_rect = pygame.Rect(40, height - panel_height - 20, width - 80, panel_height)
        
        self.draw_glass_panel(screen, panel_rect, alpha=120, border_color=(60, 80, 120))
        
        for i, line in enumerate(lines):
            font = self.get_fitting_font(line, 18, panel_rect.width - 40, bold=False)
            text_surf = font.render(line, True, (180, 195, 220))
            text_rect = text_surf.get_rect(center=(width // 2, panel_rect.y + 14 + i * 20))
            screen.blit(text_surf, text_rect)

    def draw_list_item(
        self,
        screen: pygame.Surface,
        rect: pygame.Rect,
        title: str,
        subtitle: str | None = None,
        selected: bool = False,
    ) -> None:
        """Liste öğesi çiz"""
        self.draw_glass_panel(screen, rect, alpha=180 if selected else 140, 
                             border_color=self.primary if selected else None,
                             glow=selected)
        
        # Başlık
        title_font = self.get_fitting_font(title, 26, rect.width - 32, bold=True)
        title_color = self.primary if selected else (230, 235, 245)
        title_surf = title_font.render(title, True, title_color)
        screen.blit(title_surf, (rect.x + 16, rect.y + 12))
        
        # Alt başlık
        if subtitle:
            sub_font = self.get_fitting_font(subtitle, 18, rect.width - 32, bold=False)
            sub_surf = sub_font.render(subtitle, True, (150, 165, 190))
            screen.blit(sub_surf, (rect.x + 16, rect.y + rect.height - 30))

    def draw_value_text(self, screen: pygame.Surface, pos: tuple[int, int], text: str, highlight: bool = False) -> None:
        font = self.get_font(22)
        color = self.primary if highlight else (180, 200, 220)
        surface = font.render(text, True, color)
        screen.blit(surface, surface.get_rect(midright=pos))

    def draw_option_card(self, screen: pygame.Surface, rect: pygame.Rect, label: str, value: str | None = None, selected: bool = False, label_color: tuple[int, int, int] | None = None, value_color: tuple[int, int, int] | None = None) -> None:
        """Ayar kartı çiz"""
        self.draw_glass_panel(screen, rect, alpha=180 if selected else 150,
                             border_color=self.primary if selected else None,
                             glow=selected)
        
        # Label
        label_font = self.get_fitting_font(label, 26, rect.width - 180, bold=True)
        label_c = label_color or (230, 235, 245)
        label_surf = label_font.render(label, True, label_c)
        screen.blit(label_surf, (rect.x + 20, rect.y + (rect.height - label_surf.get_height()) // 2))
        
        # Value
        if value:
            val_font = self.get_fitting_font(value, 22, rect.width - 200, bold=True)
            val_c = value_color or (180, 200, 230)
            val_surf = val_font.render(value, True, val_c)
            val_rect = val_surf.get_rect(midright=(rect.right - 20, rect.centery))
            screen.blit(val_surf, val_rect)

    def _is_toggle_on(self, text: str | None) -> bool | None:
        """Yerelleştirilmiş ON/OFF metnini algıla."""
        if text is None:
            return None
        raw = str(text).strip()
        if not raw:
            return None
        raw_cf = raw.casefold()
        on_cf = t('on').casefold()
        off_cf = t('off').casefold()
        on_tokens = {on_cf, 'on', 'açık', 'acik', 'true', '1', 'yes'}
        off_tokens = {off_cf, 'off', 'kapalı', 'kapali', 'false', '0', 'no'}
        if raw_cf in on_tokens:
            return True
        if raw_cf in off_tokens:
            return False
        return None

    def draw_setting_row(
        self,
        screen: pygame.Surface,
        rect: pygame.Rect,
        label: str,
        value: str | None = None,
        selected: bool = False,
        label_color: tuple[int, int, int] | None = None,
        value_color: tuple[int, int, int] | None = None,
        strip_color: tuple[int, int, int] | None = None,
        kind: str = 'default',
    ) -> None:
        """Ayar satırı - modern tasarım"""
        # Arka plan
        alpha = self._scale_menu_alpha(190 if selected else 150)
        fill_color = (25, 32, 52) if selected else (18, 24, 40)
        
        row_surf = pygame.Surface(rect.size, pygame.SRCALPHA)
        row_surf.fill((*fill_color, alpha))
        
        # Üst highlight
        for y in range(min(15, rect.height // 4)):
            h_alpha = int(20 * (1 - y / 15))
            pygame.draw.line(row_surf, (255, 255, 255, self._scale_menu_alpha(h_alpha)), (0, y), (rect.width, y))
        
        screen.blit(row_surf, rect.topleft)
        
        # Kenar (selected ise glow)
        if selected:
            pygame.draw.rect(screen, (*self.primary, self._scale_menu_alpha(180)), rect, 2, border_radius=10)
        else:
            pygame.draw.rect(screen, (50, 60, 85), rect, 1, border_radius=10)
        
        # Label
        label_c = label_color or (230, 235, 245)
        label_font = self.get_fitting_font(label, 26, rect.width - 200, bold=True)
        label_surf = label_font.render(label, True, label_c)
        screen.blit(label_surf, (rect.x + 14, rect.y + (rect.height - label_surf.get_height()) // 2))
        
        # Value (kind'a göre)
        if kind == 'toggle':
            is_on = self._is_toggle_on(value)
            if is_on is None:
                is_on = False
            badge_text = t('on') if is_on else t('off')
            badge_color = (60, 180, 100) if is_on else (180, 70, 70)
            
            badge_font = self.get_fitting_font(badge_text, 16, 120, bold=True)
            badge_surf = badge_font.render(badge_text, True, (255, 255, 255))
            badge_w = badge_surf.get_width() + 20
            badge_h = badge_surf.get_height() + 10
            badge_rect = pygame.Rect(rect.right - badge_w - 16, rect.centery - badge_h // 2, badge_w, badge_h)
            
            pygame.draw.rect(screen, badge_color, badge_rect, border_radius=badge_h // 2)
            screen.blit(badge_surf, badge_surf.get_rect(center=badge_rect.center))
            
        elif kind == 'selector':
            val = value or ''
            # Oklar
            arrow_font = self.get_font(20, bold=True)
            arrow_color = self.primary if selected else (120, 140, 170)
            
            val_font = self.get_fitting_font(val, 22, 200, bold=True)
            val_surf = val_font.render(val, True, value_color or (230, 240, 255))
            
            total_w = val_surf.get_width() + 50
            cx = rect.right - 20 - total_w // 2
            
            left_arrow = arrow_font.render('<', True, arrow_color)
            right_arrow = arrow_font.render('>', True, arrow_color)
            
            screen.blit(left_arrow, left_arrow.get_rect(center=(cx - val_surf.get_width() // 2 - 18, rect.centery)))
            screen.blit(val_surf, val_surf.get_rect(center=(cx, rect.centery)))
            screen.blit(right_arrow, right_arrow.get_rect(center=(cx + val_surf.get_width() // 2 + 18, rect.centery)))
            
        elif kind == 'submenu':
            arrow_font = self.get_font(22, bold=True)
            arrow = arrow_font.render('>', True, self.primary if selected else (150, 160, 180))
            screen.blit(arrow, arrow.get_rect(center=(rect.right - 30, rect.centery)))
        else:
            if value:
                val_font = self.get_fitting_font(value, 22, rect.width - 200, bold=True)
                val_surf = val_font.render(value, True, value_color or (200, 215, 240))
                screen.blit(val_surf, val_surf.get_rect(midright=(rect.right - 20, rect.centery)))

    def draw_uniform_button(
        self,
        screen: pygame.Surface,
        rect: pygame.Rect,
        text: str,
        sub_text: str | pygame.Surface | None = None,
        state: str = 'normal',
        color_code: str | tuple[int, int, int] = 'general',
        selected: bool = False,
        checked: bool = False,
        preview_color: tuple[int, int, int] | None = None,
        align: str = 'left',
    ) -> None:
        """Unified list button"""
        # Strip color
        if isinstance(color_code, tuple):
            strip_color = color_code
        else:
            mapping = {
                'general': NEON_CYAN,
                'music': (190, 80, 255),
                'gameplay': NEON_ORANGE,
                'graphics': NEON_BLUE,
            }
            strip_color = mapping.get(color_code, (100, 110, 130))
        
        is_hover = state == 'hover' or selected
        
        # Arka plan
        alpha = self._scale_menu_alpha(200 if is_hover else 160)
        fill = (30, 38, 58) if is_hover else (20, 26, 42)
        
        btn_surf = pygame.Surface(rect.size, pygame.SRCALPHA)
        btn_surf.fill((*fill, alpha))
        screen.blit(btn_surf, rect.topleft)
        
        # Kenar
        if is_hover:
            pygame.draw.rect(screen, (*strip_color, self._scale_menu_alpha(180)), rect, 2, border_radius=10)
        else:
            pygame.draw.rect(screen, (50, 60, 85), rect, 1, border_radius=10)
        
        padding = 14
        title_x = rect.x + padding
        
        # Preview color
        if preview_color:
            pv_size = 32
            pv_rect = pygame.Rect(title_x, rect.centery - pv_size // 2, pv_size, pv_size)
            pygame.draw.rect(screen, preview_color, pv_rect, border_radius=6)
            pygame.draw.rect(screen, (40, 50, 70), pv_rect, 2, border_radius=6)
            title_x = pv_rect.right + padding
        
        # Başlık ve alt metin font boyutlarını buton yüksekliğine göre sınırla.
        # Fontlar HiDPI/ölçek faktöründen bağımsız sabit px üretir; buton
        # yüksekliği ise UI ölçeğiyle küçülebilir (özellikle macOS Retina'da
        # effective scale daha düşük). Sabit 24/16 px kullanılırsa alt metin
        # "total_h > rect.height" kontrolüne takılıp tamamen düşüyordu. Yüksekliğe
        # oranlı boyut seçerek başlık + alt metnin her platformda sığmasını
        # garanti ediyoruz.
        title_size = max(12, min(24, int(rect.height * 0.42)))
        sub_size = max(9, min(16, int(rect.height * 0.26)))

        # Başlık
        title_font = self.get_fitting_font(text, title_size, rect.width - 100, bold=True)
        title_surf = title_font.render(text, True, (245, 248, 255))
        title_pos = (title_x, rect.y + padding)
        
        # Alt metin veya toggle
        sub_surf = None
        sub_pos = None
        if sub_text:
            if isinstance(sub_text, pygame.Surface):
                sub_surf = sub_text
            else:
                is_on = self._is_toggle_on(sub_text)
                if is_on is not None:
                    badge_text = t('on') if is_on else t('off')
                    badge_color = (60, 180, 100) if is_on else (180, 70, 70)
                    
                    badge_font = self.get_font(14, bold=True)
                    badge_surf = badge_font.render(badge_text, True, (255, 255, 255))
                    badge_rect = pygame.Rect(rect.right - badge_surf.get_width() - 30, 
                                            rect.centery - 12, badge_surf.get_width() + 16, 24)
                    pygame.draw.rect(screen, badge_color, badge_rect, border_radius=12)
                    screen.blit(badge_surf, badge_surf.get_rect(center=badge_rect.center))
                else:
                    sub_font = self.get_fitting_font(sub_text, sub_size, rect.width - 100, bold=False)
                    sub_surf = sub_font.render(sub_text, True, (160, 175, 200))

        # Place text. When sub_text exists (non-toggle), stack + vertically center to avoid overlap
        if sub_surf is not None:
            gap = 4
            total_h = title_surf.get_height() + gap + sub_surf.get_height()
            # Buton kısa kalırsa alt metni hemen düşürmek yerine önce başlık ve
            # alt metni sığacak şekilde küçültmeyi dene. Sabit font px'i ile
            # ölçekli buton yüksekliği uyuşmadığında (özellikle macOS Retina'da
            # effective scale düşükken) alt metin tamamen kaybolmasın.
            if total_h + 6 > rect.height and isinstance(sub_text, str):
                shrink_guard = 0
                while total_h + 6 > rect.height and shrink_guard < 12:
                    shrink_guard += 1
                    progressed = False
                    # Önce alt metni küçült (asıl taşan genelde odur).
                    if sub_size > 9:
                        sub_size = max(9, sub_size - 1)
                        sub_font = self.get_fitting_font(sub_text, sub_size, rect.width - 100, bold=False)
                        sub_surf = sub_font.render(sub_text, True, (160, 175, 200))
                        progressed = True
                    # Hâlâ sığmıyorsa başlığı da küçült.
                    if total_h + 6 > rect.height and title_size > 12:
                        title_size = max(12, title_size - 1)
                        title_font = self.get_fitting_font(text, title_size, rect.width - 100, bold=True)
                        title_surf = title_font.render(text, True, (245, 248, 255))
                        progressed = True
                    total_h = title_surf.get_height() + gap + sub_surf.get_height()
                    if not progressed:
                        break
            # If the button is still extremely short, drop the sub label rather than overlapping
            if total_h + 6 > rect.height:
                if align == 'center':
                    title_pos = (rect.x + (rect.width - title_surf.get_width()) // 2, rect.y + (rect.height - title_surf.get_height()) // 2)
                else:
                    title_pos = (title_x, rect.y + (rect.height - title_surf.get_height()) // 2)
                sub_surf = None
            else:
                start_y = rect.y + (rect.height - total_h) // 2
                if align == 'center':
                    title_pos = (rect.x + (rect.width - title_surf.get_width()) // 2, start_y)
                    sub_pos = (rect.x + (rect.width - sub_surf.get_width()) // 2, start_y + title_surf.get_height() + gap)
                else:
                    title_pos = (title_x, start_y)
                    sub_pos = (title_x, start_y + title_surf.get_height() + gap)
        else:
            if align == 'center':
                title_pos = (rect.x + (rect.width - title_surf.get_width()) // 2, rect.y + (rect.height - title_surf.get_height()) // 2)
            else:
                title_pos = (title_x, rect.y + (rect.height - title_surf.get_height()) // 2)

        screen.blit(title_surf, title_pos)
        if sub_surf is not None and sub_pos is not None:
            screen.blit(sub_surf, sub_pos)
        
        # Checked
        if checked:
            check_rect = pygame.Rect(rect.right - 24, rect.centery - 7, 14, 14)
            pygame.draw.rect(screen, (60, 180, 100), check_rect, border_radius=4)
            pygame.draw.rect(screen, (30, 40, 60), check_rect, 2, border_radius=4)

    def draw_chip(self, screen: pygame.Surface, rect: pygame.Rect, text: str, active: bool = False) -> None:
        """Chip/tag çiz"""
        fill = (50, 100, 75) if active else (30, 38, 58)
        border = self.primary if active else (70, 85, 115)
        
        chip_surf = pygame.Surface(rect.size, pygame.SRCALPHA)
        chip_surf.fill((*fill, 200))
        screen.blit(chip_surf, rect.topleft)
        pygame.draw.rect(screen, border, rect, 2, border_radius=rect.height // 2)
        
        font = self.get_fitting_font(text, 14, rect.width - 12, bold=True)
        label = font.render(text, True, (235, 245, 255))
        screen.blit(label, label.get_rect(center=rect.center))

    def draw_scrollbar(
        self,
        screen: pygame.Surface,
        container_rect: pygame.Rect,
        scroll_offset: int,
        content_height: int,
        visible_height: int | None = None,
        bar_width: int = 10,
        color: tuple[int, int, int] | None = None,
        show_always: bool = False,
    ) -> pygame.Rect | None:
        """Premium scrollbar — gradient thumb, ok işaretleri, parlak glow."""
        visible = visible_height if visible_height else container_rect.height

        if content_height <= visible and not show_always:
            return None

        thumb_color = color or self.primary
        r = bar_width // 2

        # ── Track ──────────────────────────────────────────────────────
        arrow_zone = max(10, bar_width + 2)          # ok için ayrılan yükseklik
        # Track'i container içinde yatay-ortala; tıklama alanı tüm genişliği kaplar
        track_x = container_rect.x + (container_rect.width - bar_width) // 2
        track_y = container_rect.top + arrow_zone + 2
        track_height = max(4, container_rect.height - arrow_zone * 2 - 4)
        track_rect = pygame.Rect(track_x, track_y, bar_width, track_height)

        # Track arka plan — pill şekli
        track_surf = pygame.Surface((bar_width, track_height), pygame.SRCALPHA)
        pygame.draw.rect(track_surf, (20, 28, 48, 180), track_surf.get_rect(), border_radius=r)
        pygame.draw.rect(track_surf, (60, 80, 120, 120), track_surf.get_rect(), 1, border_radius=r)
        # İç soluk çizgi (derinlik hissi)
        inner_line_surf = pygame.Surface((2, track_height - 4), pygame.SRCALPHA)
        inner_line_surf.fill((255, 255, 255, 14))
        track_surf.blit(inner_line_surf, (2, 2))
        screen.blit(track_surf, (track_x, track_y))

        # ── Thumb ──────────────────────────────────────────────────────
        thumb_ratio = visible / max(content_height, 1)
        thumb_height = max(bar_width * 2 + 4, int(track_height * thumb_ratio))

        max_scroll = max(0, content_height - visible)
        scroll_ratio = scroll_offset / max(max_scroll, 1) if max_scroll > 0 else 0
        thumb_y = track_y + int((track_height - thumb_height) * scroll_ratio)

        thumb_rect = pygame.Rect(track_x, thumb_y, bar_width, thumb_height)

        # Dış parlama (glow)
        glow_w = bar_width + 8
        glow_h = thumb_height + 8
        glow_surf = pygame.Surface((glow_w, glow_h), pygame.SRCALPHA)
        gc = thumb_color
        for i, alpha in enumerate([20, 35, 50]):
            inset = i
            gr = pygame.Rect(inset, inset, glow_w - inset * 2, glow_h - inset * 2)
            pygame.draw.rect(glow_surf, (*gc, alpha), gr, border_radius=r + 4 - inset)
        screen.blit(glow_surf, (thumb_rect.x - 4, thumb_rect.y - 4))

        # Thumb gövdesi — gradient (üstten alta: açık → koyu)
        thumb_surf = pygame.Surface((bar_width, thumb_height), pygame.SRCALPHA)
        for iy in range(thumb_height):
            t_ratio = iy / max(thumb_height - 1, 1)
            bright = int(thumb_color[0] + (min(255, thumb_color[0] + 60) - thumb_color[0]) * (1 - t_ratio))
            gr_c = (
                min(255, int(thumb_color[0] * (1.25 - 0.45 * t_ratio))),
                min(255, int(thumb_color[1] * (1.20 - 0.40 * t_ratio))),
                min(255, int(thumb_color[2] * (1.15 - 0.35 * t_ratio))),
            )
            pygame.draw.line(thumb_surf, (*gr_c, 230), (0, iy), (bar_width, iy))
        pygame.draw.rect(thumb_surf, (0, 0, 0, 0), thumb_surf.get_rect(), border_radius=r)  # köşe mask
        # Yeniden pill çiz — gradient clip için
        mask = pygame.Surface((bar_width, thumb_height), pygame.SRCALPHA)
        pygame.draw.rect(mask, (255, 255, 255, 255), mask.get_rect(), border_radius=r)
        thumb_surf.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
        screen.blit(thumb_surf, thumb_rect.topleft)

        # Thumb üst kenarda parlak vurgu çizgisi
        hl_surf = pygame.Surface((max(1, bar_width - 4), 2), pygame.SRCALPHA)
        hl_surf.fill((255, 255, 255, 80))
        screen.blit(hl_surf, (thumb_rect.x + 2, thumb_rect.y + 2))

        # Thumb border
        pygame.draw.rect(screen, (*thumb_color, 200), thumb_rect, 1, border_radius=r)

        # ── Ok işaretleri ──────────────────────────────────────────────
        arrow_color = (*thumb_color, 180)
        arrow_dim  = (*thumb_color, 80)
        cx = track_x + bar_width // 2

        # Yukarı ok ▲
        up_cy = container_rect.top + arrow_zone // 2
        aw = max(4, bar_width - 2)
        ah = max(3, aw // 2)
        at_up = max_scroll > 0 and scroll_offset > 0
        _ac = arrow_color if at_up else arrow_dim
        pygame.draw.polygon(screen, _ac, [
            (cx, up_cy - ah // 2),
            (cx - aw // 2, up_cy + ah // 2),
            (cx + aw // 2, up_cy + ah // 2),
        ])

        # Aşağı ok ▼
        down_cy = container_rect.bottom - arrow_zone // 2
        at_down = max_scroll > 0 and scroll_offset < max_scroll
        _ac2 = arrow_color if at_down else arrow_dim
        pygame.draw.polygon(screen, _ac2, [
            (cx, down_cy + ah // 2),
            (cx - aw // 2, down_cy - ah // 2),
            (cx + aw // 2, down_cy - ah // 2),
        ])

        return thumb_rect

    def _render_text_with_outline(self, font: pygame.font.Font, text: str, color: tuple[int, int, int], outline_color: tuple[int, int, int] = (0, 0, 0), outline_width: int = 1) -> pygame.Surface:
        """Outline'lı metin render et"""
        base = font.render(text, True, color)
        if outline_width <= 0:
            return base
        w, h = base.get_size()
        surf = pygame.Surface((w + outline_width * 2, h + outline_width * 2), pygame.SRCALPHA)
        outline_surf = font.render(text, True, outline_color)
        for dx in range(-outline_width, outline_width + 1):
            for dy in range(-outline_width, outline_width + 1):
                if dx == 0 and dy == 0:
                    continue
                surf.blit(outline_surf, (dx + outline_width, dy + outline_width))
        surf.blit(base, (outline_width, outline_width))
        return surf

    def apply_game_overlay(self, screen: pygame.Surface) -> None:
        """Oyun içi overlay"""
        self._blit_scanlines(screen)

    def draw_volume_bar(
        self,
        screen: pygame.Surface,
        x: int,
        y: int,
        width: int,
        height: int,
        value: float,
        color: tuple,
        pct: int,
        is_selected: bool,
        ui_scale: float = 1.0,
    ) -> None:
        """Premium neon ses seviyesi çubuğu (pause menüsü için)."""
        r = height // 2
        cy = y + height // 2

        # Track – pill, iç gölge
        track_surf = pygame.Surface((width, height), pygame.SRCALPHA)
        pygame.draw.rect(track_surf, (16, 22, 42, 215), track_surf.get_rect(), border_radius=r)
        pygame.draw.rect(track_surf, (60, 80, 120, 130), track_surf.get_rect(), 1, border_radius=r)
        hl_t = pygame.Surface((max(1, width - 6), 2), pygame.SRCALPHA)
        hl_t.fill((255, 255, 255, 14))
        track_surf.blit(hl_t, (3, 3))
        screen.blit(track_surf, (x, y))

        # Seçiliyse track glow
        if is_selected:
            glow_s = pygame.Surface((width + 16, height + 16), pygame.SRCALPHA)
            for gi, ga in enumerate([12, 28, 50]):
                gr = pygame.Rect(gi * 2, gi * 2, width + 16 - gi * 4, height + 16 - gi * 4)
                pygame.draw.rect(glow_s, (*color, ga), gr, border_radius=r + 8 - gi * 2)
            screen.blit(glow_s, (x - 8, y - 8))

        # Dolgu – neon pill + üst vurgu + glow katman
        fill_w = int(width * max(0.0, min(1.0, value)))
        if fill_w > 2:
            fill_surf = pygame.Surface((fill_w, height), pygame.SRCALPHA)
            pygame.draw.rect(fill_surf, (*color, 230), fill_surf.get_rect(), border_radius=r)
            hl_f = pygame.Surface((max(1, fill_w - 6), max(1, height // 3)), pygame.SRCALPHA)
            hl_f.fill((255, 255, 255, 70))
            fill_surf.blit(hl_f, (3, 2))
            gc = tuple(min(255, c + 55) for c in color)
            pygame.draw.rect(fill_surf, (*gc, 40), fill_surf.get_rect(), border_radius=r)
            screen.blit(fill_surf, (x, y))

        # Knob
        knob_x = x + fill_w
        knob_r = r + 2
        if is_selected:
            glow_k = pygame.Surface((knob_r * 2 + 10, knob_r * 2 + 10), pygame.SRCALPHA)
            for gi, ga in enumerate([20, 40, 65]):
                gkr = knob_r + 5 - gi * 2
                pygame.draw.circle(glow_k, (*color, ga), (knob_r + 5, knob_r + 5), max(1, gkr))
            screen.blit(glow_k, (knob_x - knob_r - 5, cy - knob_r - 5))
        pygame.draw.circle(screen, color, (knob_x, cy), knob_r, 2)
        inner_c = (255, 255, 255) if is_selected else (200, 212, 230)
        pygame.draw.circle(screen, inner_c, (knob_x, cy), knob_r - 2)
        pygame.draw.circle(screen, (255, 255, 255), (knob_x - 2, cy - max(1, knob_r // 3)), max(1, knob_r // 4))

        # Yüzde metni
        font_size = max(9, int(round(15 * ui_scale)))
        pct_surf = self.get_font(font_size, bold=True).render(f'{pct}%', True, (255, 255, 255))
        screen.blit(pct_surf, pct_surf.get_rect(center=(x + width // 2, cy)))


retro_style = RetroStyle()
