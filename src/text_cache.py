"""Text render cache for pygame.font.Font.render.

Amaç: UI ekranlarında her frame tekrarlanan font.render çağrılarını azaltmak.
Not: Cache anahtarı font objesinin id'si + metin + antialias + renk tuple'ıdır.
"""

from __future__ import annotations

import sys
from collections import OrderedDict
from typing import Optional

import pygame

# sys.modules üzerinde absolute ve relative import uyumsuzluklarını önlemek için alias oluştur
_current_module = sys.modules.get(__name__)
if _current_module is not None:
    sys.modules.setdefault('text_cache', _current_module)
    sys.modules.setdefault('src.text_cache', _current_module)


class _LRUCache:
    def __init__(self, max_items: int):
        self._max_items = max(1, int(max_items))
        self._data: "OrderedDict[tuple, pygame.Surface]" = OrderedDict()

    def get(self, key: tuple) -> Optional[pygame.Surface]:
        value = self._data.get(key)
        if value is not None:
            self._data.move_to_end(key)
        return value

    def set(self, key: tuple, value: pygame.Surface) -> None:
        self._data[key] = value
        self._data.move_to_end(key)
        while len(self._data) > self._max_items:
            self._data.popitem(last=False)

    def clear(self) -> None:
        self._data.clear()


_TEXT_CACHE = _LRUCache(max_items=1024)

# FAZ A5: metin ÖLÇÜM (font.size) önbelleği — render önbelleğinden ayrık.
# Süpürme bulgusu: font.size sonuçları kod tabanında hiçbir yerde
# önbelleklenmiyordu; sarma/fit döngüleri her adımda pygame C çağrısı
# tekrarlıyordu. Anahtar (id(font), text); değer (font, w, h) — font
# referansını değerde tutmak id() geri dönüşüm tuzağını (GC sonrası yeni
# nesnenin aynı adresi alması) keser: girdi yaşadığı sürece id benzersizdir.
_MEASURE_CACHE = _LRUCache(max_items=1024)

# FAZ A5 (ui_text_layout) için ortak LRU ilkelinin kamusal adı.
LRUCache = _LRUCache


# System Font Safety Patch (Windows registry DWORD / TypeError guard):
try:
    import pygame.sysfont
    if hasattr(pygame.sysfont, 'initsysfonts_win32'):
        _orig_initsysfonts_win32 = pygame.sysfont.initsysfonts_win32
        def _safe_initsysfonts_win32():
            try:
                return _orig_initsysfonts_win32()
            except Exception:
                return {}
        pygame.sysfont.initsysfonts_win32 = _safe_initsysfonts_win32
except Exception:
    pass


# C-extension type immutability bypass:
# pygame.font.Font'u doğrudan değiştiremeyiz. Bu yüzden subclass türetip
# pygame.font.Font ve pygame.sysfont.Font referanslarını eziyoruz.
_font_subclassing_ok = False
if hasattr(pygame, 'font') and hasattr(pygame.font, 'Font'):
    try:
        class PatchedFont(pygame.font.Font):
            def render(self, text, antialias, color, background=None):
                safe_text = "" if text is None else str(text)
                try:
                    color_key = tuple(color)
                except Exception:
                    color_key = (255, 255, 255)

                try:
                    bg_key = tuple(background) if background is not None else None
                except Exception:
                    bg_key = None

                key = (id(self), safe_text, bool(antialias), color_key, bg_key)
                cached = _TEXT_CACHE.get(key)
                if cached is not None:
                    return cached.copy()

                rendered = super().render(safe_text, antialias, color, background)
                _TEXT_CACHE.set(key, rendered)
                return rendered.copy()

            def render_shared(self, text, antialias, color, background=None) -> pygame.Surface:
                """Salt-okunur (immutable) blit işlemleri için doğrudan paylaşımlı Surface döndürür."""
                safe_text = "" if text is None else str(text)
                try:
                    color_key = tuple(color)
                except Exception:
                    color_key = (255, 255, 255)

                try:
                    bg_key = tuple(background) if background is not None else None
                except Exception:
                    bg_key = None

                key = (id(self), safe_text, bool(antialias), color_key, bg_key)
                cached = _TEXT_CACHE.get(key)
                if cached is not None:
                    return cached

                rendered = super().render(safe_text, antialias, color, background)
                _TEXT_CACHE.set(key, rendered)
                return rendered

        _font_subclassing_ok = True
    except TypeError:
        # Font VAR ama kalıtılamıyor olabilir: bazı test dosyaları pygame'i
        # ``Font=lambda *a, **kw: ...`` kalıbıyla stub'lar (test_extras_*).
        # Lambda tabanını kalıtmak metasınıf çözümünde TypeError fırlatır ve
        # modül importu — pytest KOLEKSİYONU — kırılırdı. Font referansı
        # ezilmez; aşağıdaki sade fallback sınıfı kullanılır. Üretimde
        # gerçek pygame.font.Font bir sınıftır: bu dal asla çalışmaz,
        # davranış birebir korunur.
        _font_subclassing_ok = False

if not _font_subclassing_ok:
    # v2 deseninin demo uyarlaması: kalıtılamaz/eksik Font ortamında
    # (stub pygame'li testler) sade PatchedFont. render_text_shared,
    # hasattr(font, 'render_shared') ile yokluğu zaten tolere eder.
    class PatchedFont:
        def __init__(self, *args, **kwargs):
            pass
        def render(self, text, antialias, color, background=None):
            try:
                return pygame.Surface((0, 0))
            except TypeError:
                try:
                    return pygame.Surface()
                except Exception:
                    class DummySurface:
                        def get_size(self):
                            return (0, 0)
                        def get_rect(self, **kwargs):
                            class DummyRect:
                                def __init__(self):
                                    self.x = self.y = self.width = self.height = 0
                                    self.top = self.bottom = self.left = self.right = 0
                                    self.center = self.centerx = self.centery = (0, 0)
                                def copy(self):
                                    return self
                            return DummyRect()
                    return DummySurface()

def patch_font() -> None:
    """pygame.font.Font ve sysfont.Font'u PatchedFont ile değiştirir."""
    global pygame
    if not _font_subclassing_ok:
        # Kalıtılamaz Font ortamında (stub pygame'li testler) PatchedFont
        # sade fallback sınıfıdır; stub'ın kendi fake Font'unu ezmek yerine
        # bilinçli no-op. Üretimde bayrak her zaman True'dur.
        return
    if hasattr(pygame, "font") and hasattr(pygame.font, "Font"):
        if pygame.font.Font is not PatchedFont:
            pygame.font.Font = PatchedFont
        try:
            import pygame.sysfont
            if pygame.sysfont.Font is not PatchedFont:
                pygame.sysfont.Font = PatchedFont
        except Exception:
            pass


patch_font()


def render_text(
    font: pygame.font.Font,
    text: str,
    antialias: bool,
    color,
    background=None,
) -> pygame.Surface:
    """Render text with a small LRU cache (güvenli kopya)."""
    return font.render(text, antialias, color, background)


def render_text_shared(
    font: pygame.font.Font,
    text: str,
    antialias: bool,
    color,
    background=None,
) -> pygame.Surface:
    """Yalnızca mutasyona uğramayacak salt okunur blit işlemleri için paylaşımlı Surface döndürür."""
    if hasattr(font, 'render_shared'):
        return font.render_shared(text, antialias, color, background)

    # Font PatchedFont değilse bile doğrudan LRU önbelleğini yönet
    safe_text = "" if text is None else str(text)
    try:
        color_key = tuple(color)
    except Exception:
        color_key = (255, 255, 255)

    try:
        bg_key = tuple(background) if background is not None else None
    except Exception:
        bg_key = None

    key = (id(font), safe_text, bool(antialias), color_key, bg_key)
    cached = _TEXT_CACHE.get(key)
    if cached is not None:
        return cached

    rendered = font.render(safe_text, antialias, color, background)
    _TEXT_CACHE.set(key, rendered)
    return rendered


def measure_text(
    font: pygame.font.Font,
    text: str,
) -> tuple[int, int]:
    """font.size(text) sonucunu LRU önbellekli döndür: (genişlik, yükseklik).

    Sık ölçüm döngüleri (fit küçültme adımları, satır sarma denemeleri)
    pygame C çağrısını her adımda tekrarlamak yerine buradan okur. Font
    ölçümü deterministik olduğu için önbellek davranışsal fark yaratmaz;
    yalnızca maliyeti düşürür.
    """
    safe_text = "" if text is None else str(text)
    key = (id(font), safe_text)
    cached = _MEASURE_CACHE.get(key)
    if cached is not None:
        return cached[1], cached[2]
    width, height = font.size(safe_text)
    _MEASURE_CACHE.set(key, (font, width, height))
    return width, height


def measure_text_width(font: pygame.font.Font, text: str) -> int:
    """measure_text'in yalnız genişlik bileşeni (sarma/fit döngülerinin ihtiyacı)."""
    return measure_text(font, text)[0]


def clear_text_cache() -> None:
    _TEXT_CACHE.clear()
    _MEASURE_CACHE.clear()
