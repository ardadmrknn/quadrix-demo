"""Ortak Geri butonu yardımcısı.

Tüm ekranlarda (ayar, atölye, mağaza, kullanıcı seçim, kampanya vb.) sol
üst köşede çizilen "Geri" butonu için tek bir görsel format sağlar.

Tasarım hedefi:
- Görseli ana menüdeki sağ alt "Çık" tuşu ile aynı stilde kart yap:
  glassmorphism panel + neon kenarlık + sola hizalı ikon ve sağındaki etiket.
- ``assets/main_theme/icon_back.png`` ikonunu kullan (24/7 cache).
- Vurgu rengi: açık mavi-yeşil (cyan/teal/mint geçişine yakın).
- Hover ve seçili (klavye odak) durumlarında kenarlık daha kalın çizilir
  ve panelin opaklığı artar.

Bu modül yalnızca çizim ve ikon önbelleği yapar; tıklama davranışı (ESC
semantiği) ve hit-rect kaydı çağıran ekranların sorumluluğunda kalır.

Not: ``pygame``, ``retro_style`` ve ``localization.t`` referansları çağrı
anında ``sys.modules`` üzerinden çözümlenir (lazy lookup). Bu, test
ortamlarında modül stub'larının ``sys.modules`` üzerinden değiştirilmesi
durumunda da bayat referans tutmamayı garantiler.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Callable, Optional, Tuple


def _pg() -> Any:
    """pygame modülünü sys.modules üzerinden lazy çözümle."""
    return sys.modules.get('pygame')


# Açık mavi-yeşil vurgu (mint/aqua tonu). Hover'da daha parlak versiyonu.
ACCENT_COLOR: Tuple[int, int, int] = (120, 230, 200)
ACCENT_HOVER_COLOR: Tuple[int, int, int] = (170, 245, 220)

# İkon dosyası — assets/main_theme klasöründe sabit isim.
_ICON_FILENAME = 'icon_back.png'

# (size,) -> Surface | False (False = yükleme başarısız oldu)
_ICON_CACHE: dict[int, Any] = {}


def _resolve_root_dir() -> Path:
    """PyInstaller (onefile/onedir) ve kaynaktan çalışmaya uyumlu kök dizin."""
    meipass = getattr(sys, '_MEIPASS', None)
    if isinstance(meipass, str) and meipass:
        return Path(meipass)
    return Path(__file__).resolve().parent.parent


def _get_retro_style():
    """``retro_style`` örneğini çağrı anında çözümle (lazy lookup)."""
    mod = sys.modules.get('retro_style')
    if mod is not None and hasattr(mod, 'retro_style'):
        return getattr(mod, 'retro_style')
    try:
        from retro_style import retro_style as _rs  # type: ignore
        return _rs
    except Exception:
        try:
            from .retro_style import retro_style as _rs  # type: ignore
            return _rs
        except Exception:
            return None


def _get_translator() -> Callable[..., str]:
    """``localization.t`` çevirmenini çağrı anında çözümle (lazy lookup)."""
    mod = sys.modules.get('localization')
    if mod is not None and hasattr(mod, 't'):
        return getattr(mod, 't')
    try:
        from localization import t as _t  # type: ignore
        return _t
    except Exception:
        try:
            from .localization import t as _t  # type: ignore
            return _t
        except Exception:
            return lambda key, *a, **kw: kw.get('default', key)


def _load_back_icon(size: int):
    """``icon_back.png`` ikonunu kareleştir, opak alanına trim et ve ölçekle."""
    size = max(8, int(size))
    cached = _ICON_CACHE.get(size)
    if cached is not None:
        return cached if cached is not False else None

    pg = _pg()
    if pg is None or not hasattr(pg, 'image') or not hasattr(pg, 'Surface'):
        _ICON_CACHE[size] = False
        return None

    try:
        path = _resolve_root_dir() / 'assets' / 'main_theme' / _ICON_FILENAME
        if path.exists():
            img = pg.image.load(str(path))
            try:
                img = img.convert_alpha()
            except Exception:
                pass

            try:
                trim_rect = img.get_bounding_rect(min_alpha=1)
                if trim_rect.width > 0 and trim_rect.height > 0:
                    img = img.subsurface(trim_rect).copy()
            except Exception:
                pass

            try:
                iw, ih = img.get_size()
            except Exception:
                _ICON_CACHE[size] = False
                return None

            longest = max(iw, ih)
            if iw != ih:
                try:
                    square = pg.Surface((longest, longest), pg.SRCALPHA)
                    square.blit(img, ((longest - iw) // 2, (longest - ih) // 2))
                    img = square
                except Exception:
                    pass

            try:
                scaled = pg.transform.smoothscale(img, (size, size))
            except Exception:
                scaled = img
            _ICON_CACHE[size] = scaled
            return scaled
    except Exception:
        pass

    _ICON_CACHE[size] = False
    return None


def get_back_label(default: str = 'Geri') -> str:
    """Yerelleştirilmiş 'Geri' etiketini döndür."""
    try:
        return str(_get_translator()('back', default=default))
    except Exception:
        return default


def draw_back_button(
    screen,
    s: Callable[..., int],
    *,
    label: Optional[str] = None,
    hover: bool = False,
    margin_x: int = 20,
    margin_y: int = 20,
    retro_style: Any = None,
):
    """Sol üst Geri butonunu çiz ve hit-rect'ini döndür.

    Görsel format ana menüdeki "Çık" kutusuyla aynı kart düzenidir:
    glass panel + neon kenarlık + sola hizalı ikon ve sağındaki etiket.

    Parametreler
    ------------
    screen :
        Hedef yüzey (genellikle ekran). pygame.Surface ya da test ortamlarında
        uyumlu mock.
    s : Callable
        Çağıran ekranın ölçek lambda'sı. ``s(value, minimum=1)`` ya da
        ``s(value)`` imzasıyla çağrılabilir.
    label : str, optional
        Etiket metni. Verilmezse ``t('back', default='Geri')`` kullanılır.
    hover : bool
        Buton hover/seçili durumunda mı? Kenarlık ve opaklık yoğunluğunu
        belirler.
    margin_x, margin_y : int
        Sol üst köşeye ofset (mantıksal birim — ``s()`` ile ölçeklenir).
    retro_style : opsiyonel
        Çağıran modülün ``retro_style`` referansı. Verilirse helper bu
        referansı kullanır; verilmezse ``sys.modules['retro_style']``
        üzerinden lazy çözümlenir. Test ortamlarında modül purge
        davranışını aşmak için çağıran tarafın kendi import ettiği
        ``retro_style`` referansını geçmesi önerilir.

    Returns
    -------
    pygame.Rect
        Çizilen butonun hit-test rect'i. Çağıran ekran bu rect'i tıklama
        kontrolü için kullanmalıdır.
    """
    label = label if label is not None else get_back_label()

    # Esnek ölçek çağrı imzası: hem `s(v)` hem `s(v, minimum=N)` çalışsın
    def _s(value: int, minimum: int = 1) -> int:
        try:
            return int(s(value, minimum=minimum))
        except TypeError:
            try:
                return int(s(value, minimum))  # type: ignore[arg-type]
            except TypeError:
                return max(minimum, int(s(value)))

    pg = _pg()
    if pg is None or not hasattr(pg, 'Rect'):
        # pygame yüklü değil veya stub eksik — boş bir buton bilgisi yerine
        # çağıranın hit-test edebileceği bir minimal rect döndürmeye
        # çalışsak da pygame.Rect yoksa anlamlı bir şey üretemeyiz.
        # En güvenli davranış: çağıranın istisna görmesi yerine None'a
        # benzer minimal bir nesne dönmek; ama tip uyumu için kayıt yok.
        # Bu yol prod'da çalışmaz; yalnızca aşırı stub'lı testler için.
        class _MinimalRect:
            __slots__ = ('x', 'y', 'width', 'height')
            def __init__(self, x, y, w, h):
                self.x, self.y, self.width, self.height = x, y, w, h
            def collidepoint(self, pos):
                px, py = pos
                return (self.x <= px <= self.x + self.width
                        and self.y <= py <= self.y + self.height)
        return _MinimalRect(_s(margin_x), _s(margin_y), max(80, _s(140)), max(32, _s(42)))

    # Ölçeklenmiş layout sabitleri
    pad_x = _s(14)
    pad_y = _s(8)
    icon_text_gap = _s(10)
    btn_x = _s(margin_x)
    btn_y = _s(margin_y)

    font_size = _s(16, minimum=12)
    if retro_style is None:
        retro_style = _get_retro_style()
    if retro_style is None or not hasattr(retro_style, 'get_font'):
        # Test ortamında retro_style stub'lanmış ya da yüklenememiş —
        # minimum bir buton kutusu yine de yerleştir, ama çizim atla.
        btn_w = max(80, _s(140))
        btn_h = max(32, _s(42))
        return pg.Rect(btn_x, btn_y, btn_w, btn_h)

    font = retro_style.get_font(font_size, bold=True)
    text_surf = font.render(label, True, (236, 244, 255))
    if text_surf is None:
        # Stub font'lar render() → None döndürebilir; bu durumda buton
        # yalnızca rect olarak yerleşir.
        btn_w = max(80, _s(140))
        btn_h = max(32, _s(42))
        return pg.Rect(btn_x, btn_y, btn_w, btn_h)

    # İkon yüksekliği yazıyla uyumlu (çıkış butonundaki ikon/yazı oranı gibi)
    text_h_for_icon = 18
    try:
        text_h_for_icon = text_surf.get_height()
    except Exception:
        pass
    icon_size = max(18, text_h_for_icon + _s(4))
    icon = _load_back_icon(icon_size)

    try:
        text_w = text_surf.get_width()
        text_h = text_surf.get_height()
    except Exception:
        text_w, text_h = 80, 18

    if icon is not None:
        content_w = icon_size + icon_text_gap + text_w
        content_h = max(icon_size, text_h)
    else:
        content_w = text_w
        content_h = text_h

    btn_w = content_w + pad_x * 2
    btn_h = content_h + pad_y * 2

    rect = pg.Rect(btn_x, btn_y, btn_w, btn_h)

    accent = ACCENT_HOVER_COLOR if hover else ACCENT_COLOR

    # Glass panel arka plan (Çık tuşundaki ile aynı zemin tonu)
    try:
        retro_style.draw_glass_panel(
            screen,
            rect,
            alpha=205 if hover else 165,
            border_color=accent,
            glow=False,
            top_highlight=False,
            draw_border=False,
        )
    except Exception:
        # Stub draw_glass_panel sessizce başarısız olabilir; çizimi atla.
        pass

    # Neon kenarlık — Çık kutusuyla aynı kalınlık ve köşe yarıçapı
    try:
        border_alpha = 255 if hover else 170
        border_width = 3 if hover else 2
        pg.draw.rect(
            screen,
            (*accent[:3], border_alpha),
            rect,
            border_width,
            border_radius=14,
        )
    except Exception:
        pass

    # İçeriği yatayda ortala (ikon + boşluk + etiket). Hesaplamalar ham
    # aritmetik ile yapılır (rect.centerx/centery kullanmadan), böylece
    # helper test ortamlarındaki minimal pygame.Rect mock'ları ile de
    # çalışır.
    cy = btn_y + btn_h // 2
    try:
        if icon is not None:
            start_x = btn_x + (btn_w - content_w) // 2
            icon_y = cy - icon_size // 2
            screen.blit(icon, (start_x, icon_y))

            text_x = start_x + icon_size + icon_text_gap
            text_y = cy - text_h // 2
            screen.blit(text_surf, (text_x, text_y))
        else:
            text_x = btn_x + (btn_w - text_w) // 2
            text_y = cy - text_h // 2
            screen.blit(text_surf, (text_x, text_y))
    except Exception:
        pass

    return rect


def clear_icon_cache() -> None:
    """İkon önbelleğini sıfırla (testler ve hot-reload için)."""
    _ICON_CACHE.clear()
