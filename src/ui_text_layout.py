"""Ortak metin ölçüm / sarma / kutuya sığdırma kütüphanesi — FAZ A5.

Gorsel_Olcek_Sorunlari_Cozum_Plani.md FAZ A5: her metin çizimi parent içerik
kutusunu, dili ve render kuşağını bilir; taşma sırası sarma -> kontrollü
ellipsis'tir; font sınırsız büyümez ve minimum okunur font eşiği altına
SESSİZCE düşülmez (``min_size_hit`` bayrağı taşmayı bildirir).

Tasarım kararları (süpürme envanterinden):

1. **Tek yönlü bağımlılık:** bu modül yalnız ``text_cache``'e bağlıdır
   (ölçüm LRU'su). ``retro_style`` asla bu modülü import etmez; bu modül
   retro_style'ı yalnız opsiyonel default font fabrikası için ÇAĞRI ANINDA
   (lazy) çözer — import döngüsü bu yönle imkânsızdır.
2. **Parite, testle kilitli:** ``wrap_text`` / ``fit_font_to_width`` /
   ``fit_text_to_box``, retro_style'ın ``wrap_text`` / ``get_fitting_font`` /
   ``fit_wrapped_font`` algoritmalarının modül-seviyesi saf karşılıklarıdır;
   test_text_containment.py eşdeğerliği fixture'lar üzerinden kilitler.
   retro_style içi vekillik sonraki fazlarda bu kilit sayesinde güvenle
   yapılabilir (tek uygulama hedefi).
3. **Kare-başı tahsis yasağı:** bu modül Surface RENDER ETMEZ — ölçüm ve
   satır düzeni döndürür; render text_cache.PatchedFont / retro_style.draw_*
   yolunda kalır. Sonuç cache'leri (sarma/ellipsis) LRU'dur ve değerlerinde
   font referansını tutarak id() geri dönüşümünü keser.
4. **Emoji yok (CLAUDE.md):** varsayılan ellipsis ASCII ``'...'``; sembol
   gerektiren UI için PNG asset sözleşmesi geçerlidir.
5. **Ölçek/dil değişiminde invalidasyon:** ``ui_scaling.set_ui_scale_preset``
   zinciri ``clear_layout_caches`` çağırır; font nesneleri dil/ölçek
   değişiminde yeniden yaratıldığından yeni id'ler taze girdi üretir.
"""

from __future__ import annotations

from typing import Callable, NamedTuple, Optional

import pygame

from text_cache import LRUCache, measure_text, measure_text_width

# Mutlak font tabanı — retro_style.get_fitting_font/fit_wrapped_font paritesi
# (max(8, min_size)). Bu eşiğin altına hiçbir koşulda sessizce inilmez.
MIN_FONT_SIZE = 8
# Varsayılan okunur alt sınır (retro_style.get_fitting_font min_size=10 paritesi).
DEFAULT_MIN_FONT_SIZE = 10
# retro_style draw_wrapped_text/fit_wrapped_font paritesi (piksel cinsinden).
DEFAULT_LINE_SPACING = 6
# ASCII güvenli ellipsis; '…' tek glifi font desteğine göre çağıranın kararıdır.
DEFAULT_ELLIPSIS = '...'

_WRAP_CACHE = LRUCache(max_items=256)
_LIMITED_WRAP_CACHE = LRUCache(max_items=256)
_ELLIPSIZE_CACHE = LRUCache(max_items=512)

_LAYOUT_GENERATION = 0

FontFactory = Callable[..., object]


class WrappedText(NamedTuple):
    """wrap_text_limited sonucu: satırlar (tuple, mutasyona kapalı) + kesinti bayrağı."""

    lines: tuple
    truncated: bool


class FittedFont(NamedTuple):
    """fit_font_to_width sonucu (get_fitting_font paritesi + kanıt bayrakları)."""

    font: object
    requested_size: int
    final_size: int
    text_width: int
    min_size_hit: bool


class TextBlockLayout(NamedTuple):
    """fit_text_to_box sonucu — A6/A7 tüketicilerinin 'text budget' sözleşmesi.

    total_height = len(lines) * line_height + (len(lines)-1) * line_spacing
    (retro_style.fit_wrapped_font formül paritesi). Taşma yalnızca
    ``min_size_hit``/``truncated`` bayraklarıyla BİLDİRİLİR, gizlenmez.
    """

    font: object
    lines: tuple
    line_height: int
    line_spacing: int
    total_height: int
    max_line_width: int
    requested_size: int
    final_size: int
    min_size_hit: bool
    truncated: bool


def layout_generation() -> int:
    """Mevcut layout kuşağı (FAZ A4 deseni: tüketici cache anahtarının İLK bileşeni)."""
    return _LAYOUT_GENERATION


def clear_layout_caches() -> None:
    """Sarma/ellipsis sonuç cache'lerini temizle ve kuşağı artır.

    ui_scaling.set_ui_scale_preset invalidasyon zincirine bağlıdır; ölçüm
    önbelleği text_cache.clear_text_cache tarafından aynı zincirde temizlenir.
    """
    global _LAYOUT_GENERATION
    _WRAP_CACHE.clear()
    _LIMITED_WRAP_CACHE.clear()
    _ELLIPSIZE_CACHE.clear()
    _LAYOUT_GENERATION += 1


def _resolve_font_factory(font_factory: Optional[FontFactory]) -> FontFactory:
    """font_factory None ise retro_style font zincirine vekillik eden fabrika döndür.

    Lazy çözümleme hermetik test purge'lerine dayanıklıdır: çağri anında
    sys.modules'teki güncel retro_style kopyası kullanılır.
    """
    if font_factory is not None:
        return font_factory
    import retro_style as _rs_mod

    _singleton = _rs_mod.retro_style

    def _factory(size, bold=True):
        return _singleton.get_font(int(size), bold=bold)

    return _factory


def _font_height(font) -> int:
    """retro_style paritesi: satır yüksekliği font.get_height()."""
    return font.get_height()


def _break_long_token(token: str, font, max_width: int) -> list:
    """Tek kelime/token genişliğe sığmıyorsa karakter bazında böl.

    Boşluksuz CJK metinlerinde ve aşırı uzun Latin kelimelerde panel taşmasını
    önler (retro_style._break_long_token birebir karşılığı; ölçüm LRU'dan).
    """
    pieces = []
    current = ''
    for ch in token:
        candidate = current + ch
        if not current or measure_text_width(font, candidate) <= max_width:
            current = candidate
        else:
            pieces.append(current)
            current = ch
    if current:
        pieces.append(current)
    return pieces


def wrap_text(text: str, font, max_width: int) -> list:
    """Kelime sarmalı (retro_style.wrap_text birebir paritesi, ölçüm LRU'lu).

    Elle bölünmüş '\\n' satırları korunur; boşluksuz CJK/uzun token'lar
    karakter bazında bölünür. Sonuç cache'lenir (değerde font pinlenir).
    """
    safe_text = "" if text is None else str(text)
    key = (id(font), safe_text, int(max_width))
    cached = _WRAP_CACHE.get(key)
    if cached is not None:
        return list(cached[1])

    lines = []
    if max_width <= 0:
        lines = [safe_text]
    else:
        for paragraph in safe_text.split('\n'):
            words = paragraph.split()
            if not words:
                lines.append('')
                continue
            current = ''
            for word in words:
                test_line = word if not current else f"{current} {word}"
                if measure_text_width(font, test_line) <= max_width:
                    current = test_line
                    continue
                if current:
                    lines.append(current)
                    current = ''
                if measure_text_width(font, word) <= max_width:
                    current = word
                else:
                    # Kelime tek başına bile sığmıyor: karakter bazında böl;
                    # son parça bir sonraki kelimeyle birleşebilsin.
                    pieces = _break_long_token(word, font, max_width)
                    if pieces:
                        lines.extend(pieces[:-1])
                        current = pieces[-1]
            if current:
                lines.append(current)

    _WRAP_CACHE.set(key, (font, tuple(lines)))
    return lines


def ellipsize_text(
    text: str,
    font,
    max_width: int,
    ellipsis: str = DEFAULT_ELLIPSIS,
) -> str:
    """Metni ellipsis ekleyerek max_width'e sığdır (taşma sırasının ikinci adımı).

    İkili arama + komşu düzeltme: gerçek fontlarda kerning, ön-uzunluğun
    katı monotonluğunu bozabildiğinden sınır birkaç adımla sağlamlaştırılır.
    Dejenere bütçede (max_width <= 0) metin dokunulmadan döner; ellipsis'in
    kendisi bile sığmıyorsa yalnız ellipsis döner.
    """
    safe_text = "" if text is None else str(text)
    if max_width is None or max_width <= 0:
        return safe_text
    key = (id(font), safe_text, int(max_width), ellipsis)
    cached = _ELLIPSIZE_CACHE.get(key)
    if cached is not None:
        return cached[1]

    result = safe_text
    if measure_text_width(font, safe_text) > max_width:
        ellipsis_width = measure_text_width(font, ellipsis)
        if ellipsis_width >= max_width:
            result = ellipsis
        else:
            best = 0
            lo, hi = 0, len(safe_text)
            while lo <= hi:
                mid = (lo + hi) // 2
                if measure_text_width(font, safe_text[:mid] + ellipsis) <= max_width:
                    best = mid
                    lo = mid + 1
                else:
                    hi = mid - 1
            # Kerning kaynaklı monotonluk bozulmalarına karşı sınır düzeltme.
            while best < len(safe_text) and measure_text_width(
                font, safe_text[:best + 1] + ellipsis
            ) <= max_width:
                best += 1
            while best > 0 and measure_text_width(
                font, safe_text[:best] + ellipsis
            ) > max_width:
                best -= 1
            prefix = safe_text[:best].rstrip()
            result = (prefix + ellipsis) if prefix else ellipsis

    _ELLIPSIZE_CACHE.set(key, (font, result))
    return result


def wrap_text_limited(
    text: str,
    font,
    max_width: int,
    max_lines: Optional[int] = None,
    ellipsis: str = DEFAULT_ELLIPSIS,
) -> WrappedText:
    """Sarma + satır limiti + kontrollü ellipsis (taşma sırası: wrap -> ellipsis).

    Sözleşme:
    - max_lines None: yalnız genişlik sarması (wrap_text ile aynı satırlar).
    - max_lines verilirse ve sarma daha çok satır üretirse: ilk max_lines-1
      satır tam kalır, son satır kalan metnin ellipsize edilmiş hâlidir
      (``truncated=True``). Kelime sırası korunur — metin kaybolmaz, kesilir.
    - Güvenlik: sığmayan tek parça (aşırı dar bütçe) son çare ellipsis'lenir.
    """
    safe_text = "" if text is None else str(text)
    key = (id(font), safe_text, int(max_width), max_lines, ellipsis)
    cached = _LIMITED_WRAP_CACHE.get(key)
    if cached is not None:
        return WrappedText(lines=cached[1], truncated=cached[2])

    lines = wrap_text(safe_text, font, max_width)
    truncated = False

    if max_lines is not None and max_lines <= 0:
        lines = []
        truncated = bool(safe_text)
    elif max_lines is not None and len(lines) > max_lines:
        kept = lines[:max_lines - 1] if max_lines >= 1 else []
        # Sarma kelime sınırlarından geçtiği için kalan satırları boşlukla
        # birleştirmek kesilen metni (yaklaşık olarak) geri kurar.
        remainder = ' '.join(lines[max_lines - 1:])
        last = ellipsize_text(remainder, font, max_width, ellipsis)
        kept.append(last)
        lines = kept
        truncated = True

    # Güvenlik ağı: bölünemeyen tek parça satırı aşarsa son çare ellipsis.
    if max_width > 0:
        guarded = []
        for line in lines:
            if line and measure_text_width(font, line) > max_width:
                guarded.append(ellipsize_text(line, font, max_width, ellipsis))
            else:
                guarded.append(line)
        lines = guarded

    result = WrappedText(lines=tuple(lines), truncated=truncated)
    _LIMITED_WRAP_CACHE.set(key, (font, result.lines, result.truncated))
    return result


def fit_font_to_width(
    text: str,
    font_factory: Optional[FontFactory] = None,
    base_size: int = 20,
    max_width: Optional[int] = None,
    min_size: int = DEFAULT_MIN_FONT_SIZE,
    bold: bool = True,
) -> FittedFont:
    """Metni tek satırda genişliğe sığdıran fontu küçülterek bul (step -2).

    retro_style.get_fitting_font paritesi: max_width <= 0 ise fit'siz taban
    boyut; küçültme adımı 2; taban max(8, min_size). ``min_size_hit=True``
    tabana inildiğini VE hâlâ taşındığını bildirir (sessiz taşma yok).
    """
    factory = _resolve_font_factory(font_factory)
    safe_text = "" if text is None else str(text)
    eff_min = max(MIN_FONT_SIZE, int(min_size))
    size = int(base_size)
    font = factory(size, bold=bold)

    if not max_width or max_width <= 0:
        width = measure_text_width(font, safe_text)
        return FittedFont(
            font=font, requested_size=int(base_size), final_size=size,
            text_width=width, min_size_hit=False,
        )

    width = measure_text_width(font, safe_text)
    while width > max_width and size > eff_min:
        size -= 2
        font = factory(size, bold=bold)
        width = measure_text_width(font, safe_text)

    return FittedFont(
        font=font, requested_size=int(base_size), final_size=size,
        text_width=width, min_size_hit=width > max_width,
    )


def fit_text_to_box(
    text: str,
    font_factory: Optional[FontFactory] = None,
    box_width: int = 0,
    box_height: int = 0,
    base_size: int = 20,
    min_size: int = DEFAULT_MIN_FONT_SIZE,
    bold: bool = False,
    line_spacing: int = DEFAULT_LINE_SPACING,
    max_lines: Optional[int] = None,
    ellipsis: str = DEFAULT_ELLIPSIS,
) -> TextBlockLayout:
    """Sarılı metni hem genişliğe hem yüksekle sığdır (fit_wrapped_font paritesi + sözleşme).

    Küçültme döngüsü satır adımı -1 (retro_style.fit_wrapped_font paritesi);
    başlangıç max(min_size, base_size) — font base'i AŞMAZ (sınırsız büyüme
    yok). ``TextBlockLayout`` taşma durumunu bayraklarla bildirir:
    ``min_size_hit`` (tabana inildi, hâlâ sığmadı) ve ``truncated``
    (max_lines kesintisi / güvenlik ellipsis'i).
    """
    factory = _resolve_font_factory(font_factory)
    safe_text = "" if text is None else str(text)
    eff_min = max(MIN_FONT_SIZE, int(min_size))
    spacing = max(0, int(line_spacing))
    size = max(eff_min, int(base_size))
    font = factory(size, bold=bold)

    wrapped = wrap_text_limited(
        safe_text, font, box_width, max_lines=max_lines, ellipsis=ellipsis,
    )
    lines = list(wrapped.lines)
    truncated = wrapped.truncated

    def _total_h(fh, line_count):
        return line_count * _font_height(fh) + max(0, line_count - 1) * spacing

    if box_height and box_height > 0:
        while size > eff_min:
            if _total_h(font, len(lines)) <= box_height:
                break
            size -= 1
            font = factory(size, bold=bold)
            wrapped = wrap_text_limited(
                safe_text, font, box_width, max_lines=max_lines, ellipsis=ellipsis,
            )
            lines = list(wrapped.lines)
            truncated = truncated or wrapped.truncated

    line_h = _font_height(font)
    total_h = _total_h(font, len(lines))
    max_line_w = 0
    for line in lines:
        if line:
            max_line_w = max(max_line_w, measure_text_width(font, line))
    # Taşma bayrakları ortogonal: ``truncated`` metnin KESİLDİĞİNİ (max_lines
    # kesintisi / güvenlik ellipsis'i), ``min_size_hit`` tabana inilip yine
    # sığmadığını bildirir. Saf yükseklik taşması total_height alanından okunur.
    overflow = total_h > box_height if (box_height and box_height > 0) else False

    return TextBlockLayout(
        font=font,
        lines=tuple(lines),
        line_height=line_h,
        line_spacing=spacing,
        total_height=total_h,
        max_line_width=max_line_w,
        requested_size=int(base_size),
        final_size=size,
        min_size_hit=overflow and size <= eff_min,
        truncated=truncated,
    )


def clamp_rect_in_parent(rect, parent_rect, padding: int = 0) -> pygame.Rect:
    """Çocuk rect'i parent'ın içerik kutusuna çek (menu.py hero-subtitle modeli).

    Sağ/alt kenar taşması pygame ``right``/``bottom`` atayıcı semantiğiyle
    çözülür: rect GERİ TAŞINIR (boyut korunur — sabit boyutlu render
    surface'ı için doğru hareket; küçültme fit_text_to_box'un işidir).
    pygame.Rect.clamp'ten farkı: yalnız sağ/alt çekilir, sol/üst taşması
    dokunulmaz (menü deseni paritesi). Orijinal rect MUTATE EDİLMEZ.
    """
    out = pygame.Rect(rect)
    parent = pygame.Rect(parent_rect)
    pad = max(0, int(padding))
    if out.right > parent.right - pad:
        out.right = parent.right - pad
    if out.bottom > parent.bottom - pad:
        out.bottom = parent.bottom - pad
    return out
