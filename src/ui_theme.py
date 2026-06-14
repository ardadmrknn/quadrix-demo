"""
Quadrix Full Edition - Merkezi UI Tema Sistemi

Tüm pencerelerde tutarlı görsel kimlik için renk paleti,
font boyutları, kenar yuvarlaklıkları ve stil sabitleri.
"""

import pygame
from retro_style import HybridFont

# ============================================================================
# ANA RENK PALETİ
# ============================================================================

class UIColors:
    """Tüm UI bileşenlerinde kullanılacak renk sabitleri"""
    
    # Ana arka plan renkleri
    BG_DARK = (10, 10, 26)           # Koyu lacivert - ana arka plan
    BG_MEDIUM = (18, 18, 40)         # Orta koyu - panel arka planı
    BG_LIGHT = (30, 30, 55)          # Açık koyu - hover/seçili durumlar
    BG_OVERLAY = (5, 5, 15, 200)     # Yarı saydam overlay
    
    # Cam efekti (Glassmorphism)
    GLASS_BG = (20, 20, 45, 180)     # Cam panel arka planı
    GLASS_BORDER = (80, 80, 120, 150) # Cam panel kenarı
    GLASS_HIGHLIGHT = (255, 255, 255, 30)  # Üst kenar parlama
    
    # Neon vurgu renkleri
    NEON_CYAN = (0, 240, 255)        # Ana vurgu
    NEON_MAGENTA = (255, 0, 200)     # İkincil vurgu
    NEON_GREEN = (0, 255, 150)       # Başarı/onay
    NEON_ORANGE = (255, 150, 0)      # Uyarı
    NEON_RED = (255, 50, 80)         # Hata/tehlike
    NEON_GOLD = (255, 215, 0)        # Özel/premium
    
    # Metin renkleri
    TEXT_PRIMARY = (255, 255, 255)   # Ana metin
    TEXT_SECONDARY = (180, 180, 200) # İkincil metin
    TEXT_MUTED = (120, 120, 140)     # Soluk metin
    TEXT_ACCENT = NEON_CYAN          # Vurgulu metin
    TEXT_SUCCESS = NEON_GREEN        # Başarı mesajı
    TEXT_ERROR = NEON_RED            # Hata mesajı
    
    # Buton renkleri
    BUTTON_BG = (40, 40, 70)         # Buton arka planı
    BUTTON_HOVER = (60, 60, 100)     # Hover durumu
    BUTTON_ACTIVE = (80, 80, 130)    # Tıklama durumu
    BUTTON_DISABLED = (30, 30, 50)   # Devre dışı
    BUTTON_BORDER = (100, 100, 150)  # Buton kenarı
    
    # Slider renkleri
    SLIDER_BG = (30, 30, 50)         # Slider yolu
    SLIDER_FILL = NEON_CYAN          # Dolu kısım
    SLIDER_HANDLE = (255, 255, 255)  # Tutamak
    
    # Sekme/Tab renkleri
    TAB_INACTIVE = (40, 40, 60)      # Pasif sekme
    TAB_ACTIVE = NEON_CYAN           # Aktif sekme
    TAB_HOVER = (60, 60, 90)         # Hover
    
    # Kart nadirlikleri
    RARITY_COMMON = (180, 180, 180)  # Yaygın / Sıradan
    RARITY_UNCOMMON = (100, 220, 140) # Sıradışı
    RARITY_RARE = (80, 180, 255)     # Nadir / Ender
    RARITY_EPIC = (180, 80, 255)     # Epik
    RARITY_LEGENDARY = (255, 180, 0) # Efsanevi


# ============================================================================
# FONT SİSTEMİ
# ============================================================================

class UIFonts:
    """Font boyutları ve stilleri"""
    
    # Font boyutları (temel çözünürlük için)
    SIZE_TITLE = 48          # Büyük başlıklar
    SIZE_HEADING = 36        # Alt başlıklar
    SIZE_SUBHEADING = 28     # Küçük başlıklar
    SIZE_BODY = 22           # Normal metin
    SIZE_SMALL = 18          # Küçük metin
    SIZE_TINY = 14           # Çok küçük metin
    
    # Cache'lenmiş fontlar
    _cache = {}
    _font_path = None
    _default_font_path = None  # Latin fallback (CJK hibrit için)
    _size_scale = 1.0
    _force_no_bold = False

    @classmethod
    def _apply_size_scale(cls, size: int) -> int:
        try:
            scale = float(cls._size_scale)
        except (TypeError, ValueError):
            scale = 1.0
        scale = max(0.5, min(2.0, scale))
        try:
            scaled = int(round(int(size) * scale))
        except (TypeError, ValueError):
            scaled = int(round(22 * scale))
        return max(6, scaled)

    @classmethod
    def set_font_profile(
        cls,
        font_path: str | None = None,
        default_font_path: str | None = None,
        size_scale: float = 1.0,
        force_no_bold: bool = False,
    ) -> None:
        """Font profilini ayarla (dil bazlı override)."""
        cls._font_path = font_path
        cls._default_font_path = default_font_path
        try:
            cls._size_scale = float(size_scale)
        except (TypeError, ValueError):
            cls._size_scale = 1.0
        cls._force_no_bold = bool(force_no_bold)
        cls.clear_cache()
    
    @classmethod
    def _get_system_font(cls, scaled_size: int, effective_bold: bool) -> pygame.font.Font:
        """Güvenli system font fallback — pygame default font (freesansbold.ttf) olmadan da çalışır."""
        if not pygame.font.get_init():
            pygame.font.init()
        for name in ('Segoe UI', 'Arial', 'Helvetica', 'DejaVu Sans'):
            path = pygame.font.match_font(name)
            if path:
                try:
                    font_obj = pygame.font.Font(path, scaled_size)
                    if effective_bold:
                        font_obj.set_bold(True)
                    return font_obj
                except Exception:
                    continue
        # Son çare: SysFont (freesansbold.ttf gerektirmez)
        try:
            return pygame.font.SysFont(None, scaled_size, bold=effective_bold)
        except Exception:
            return pygame.font.SysFont('monospace', scaled_size, bold=effective_bold)

    @classmethod
    def _get_latin_font(cls, scaled_size: int, effective_bold: bool) -> pygame.font.Font:
        """Varsayılan latin fontunu döndür (CJK hibrit sistem için)."""
        key = (scaled_size, effective_bold, '__latin__')
        if key not in cls._cache:
            font_obj = None
            if cls._default_font_path:
                try:
                    font_obj = pygame.font.Font(cls._default_font_path, scaled_size)
                    if effective_bold:
                        font_obj.set_bold(True)
                except Exception:
                    font_obj = None
            if font_obj is None:
                # Font(None) yerine güvenli system font fallback kullan
                font_obj = cls._get_system_font(scaled_size, effective_bold)
            cls._cache[key] = font_obj
        return cls._cache[key]

    @classmethod
    def get(cls, size: int, bold: bool = False) -> pygame.font.Font:
        """Font al (cache'li)"""
        scaled_size = cls._apply_size_scale(size)
        effective_bold = False if cls._force_no_bold else bool(bold)
        key = (scaled_size, effective_bold, cls._font_path, cls._default_font_path)
        if key not in cls._cache:
            try:
                if cls._font_path:
                    cjk_font = pygame.font.Font(cls._font_path, scaled_size)
                    if effective_bold:
                        cjk_font.set_bold(True)
                    latin_font = cls._get_latin_font(scaled_size, effective_bold)
                    cls._cache[key] = HybridFont(latin_font, cjk_font)
                else:
                    cls._cache[key] = cls._get_latin_font(scaled_size, effective_bold)
            except Exception:
                # Son çare: güvenli fallback (Font(None) kullanma — paketli build'da eksik olabilir)
                cls._cache[key] = cls._get_system_font(scaled_size, effective_bold)
        return cls._cache[key]
    
    @classmethod
    def title(cls) -> pygame.font.Font:
        return cls.get(cls.SIZE_TITLE, bold=True)
    
    @classmethod
    def heading(cls) -> pygame.font.Font:
        return cls.get(cls.SIZE_HEADING, bold=True)
    
    @classmethod
    def subheading(cls) -> pygame.font.Font:
        return cls.get(cls.SIZE_SUBHEADING)
    
    @classmethod
    def body(cls) -> pygame.font.Font:
        return cls.get(cls.SIZE_BODY)
    
    @classmethod
    def small(cls) -> pygame.font.Font:
        return cls.get(cls.SIZE_SMALL)
    
    @classmethod
    def tiny(cls) -> pygame.font.Font:
        return cls.get(cls.SIZE_TINY)
    
    @classmethod
    def clear_cache(cls):
        """Font cache'ini temizle"""
        cls._cache.clear()


# ============================================================================
# STİL SABİTLERİ
# ============================================================================

class UIStyle:
    """Genel stil sabitleri"""
    
    # Kenar yuvarlaklıkları
    BORDER_RADIUS_SMALL = 8
    BORDER_RADIUS_MEDIUM = 12
    BORDER_RADIUS_LARGE = 16
    BORDER_RADIUS_XLARGE = 24
    
    # Kenar kalınlıkları
    BORDER_WIDTH_THIN = 1
    BORDER_WIDTH_NORMAL = 2
    BORDER_WIDTH_THICK = 3
    
    # Padding değerleri
    PADDING_TINY = 4
    PADDING_SMALL = 8
    PADDING_MEDIUM = 12
    PADDING_LARGE = 16
    PADDING_XLARGE = 24
    
    # Spacing (boşluk) değerleri
    SPACING_TINY = 4
    SPACING_SMALL = 8
    SPACING_MEDIUM = 16
    SPACING_LARGE = 24
    SPACING_XLARGE = 32
    
    # Animasyon süreleri (ms)
    ANIM_FAST = 100
    ANIM_NORMAL = 200
    ANIM_SLOW = 400
    
    # Hover/tıklama ölçekleri
    HOVER_SCALE = 1.02
    CLICK_SCALE = 0.98
    
    # Glow (parıltı) özellikleri
    GLOW_RADIUS = 4
    GLOW_INTENSITY = 0.5
    
    # Panel boyutları
    PANEL_MIN_WIDTH = 300
    PANEL_MAX_WIDTH = 800
    
    # Buton boyutları
    BUTTON_HEIGHT = 44
    BUTTON_MIN_WIDTH = 120


# ============================================================================
# YARDIMCI FONKSİYONLAR
# ============================================================================

def lerp_color(color1: tuple, color2: tuple, t: float) -> tuple:
    """İki renk arasında lineer interpolasyon"""
    t = max(0, min(1, t))
    if len(color1) == 3:
        return (
            int(color1[0] + (color2[0] - color1[0]) * t),
            int(color1[1] + (color2[1] - color1[1]) * t),
            int(color1[2] + (color2[2] - color1[2]) * t),
        )
    else:
        return (
            int(color1[0] + (color2[0] - color1[0]) * t),
            int(color1[1] + (color2[1] - color1[1]) * t),
            int(color1[2] + (color2[2] - color1[2]) * t),
            int(color1[3] + (color2[3] - color1[3]) * t),
        )


def brighten_color(color: tuple, factor: float = 1.2) -> tuple:
    """Rengi parlat"""
    if len(color) == 3:
        return (
            min(255, int(color[0] * factor)),
            min(255, int(color[1] * factor)),
            min(255, int(color[2] * factor)),
        )
    else:
        return (
            min(255, int(color[0] * factor)),
            min(255, int(color[1] * factor)),
            min(255, int(color[2] * factor)),
            color[3],
        )


def darken_color(color: tuple, factor: float = 0.7) -> tuple:
    """Rengi koyulaştır"""
    if len(color) == 3:
        return (
            int(color[0] * factor),
            int(color[1] * factor),
            int(color[2] * factor),
        )
    else:
        return (
            int(color[0] * factor),
            int(color[1] * factor),
            int(color[2] * factor),
            color[3],
        )


def add_alpha(color: tuple, alpha: int) -> tuple:
    """Renge alpha ekle"""
    if len(color) == 3:
        return (*color, alpha)
    else:
        return (*color[:3], alpha)


def get_neon_glow_color(base_color: tuple, intensity: float = 0.5) -> tuple:
    """Neon glow efekti için renk hesapla"""
    return add_alpha(brighten_color(base_color, 1.3), int(255 * intensity))


# ============================================================================
# TEMA PRESET'LERİ
# ============================================================================

class ThemePresets:
    """Hazır tema kombinasyonları"""
    
    CYBERPUNK = {
        'primary': UIColors.NEON_CYAN,
        'secondary': UIColors.NEON_MAGENTA,
        'background': UIColors.BG_DARK,
        'surface': UIColors.GLASS_BG,
    }
    
    OCEAN = {
        'primary': (0, 180, 220),
        'secondary': (0, 100, 180),
        'background': (5, 15, 30),
        'surface': (15, 35, 60, 180),
    }
    
    SUNSET = {
        'primary': (255, 120, 80),
        'secondary': (255, 60, 120),
        'background': (20, 10, 15),
        'surface': (40, 20, 30, 180),
    }
    
    FOREST = {
        'primary': (80, 220, 100),
        'secondary': (40, 160, 80),
        'background': (10, 20, 15),
        'surface': (25, 45, 30, 180),
    }
