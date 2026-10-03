"""
Quadrix – Premium Renk Seçici (Color Picker)

Oyun içi gerçek jelly blok renderer kullanan, neon glassmorphism temalı,
performans için cache kullanan premium renk seçici.

Kullanım:
    from color_picker import pygame_color_picker
    chosen = pygame_color_picker(screen, initial_color=(255,0,0), piece_name="T")
"""
from __future__ import annotations

import colorsys
import math
import sys
import time
from typing import Dict, List, Optional, Tuple

import pygame

from platform_utils import get_mouse_pos, resolve_frame_rate_cap
from localization import t
from ui_scaling import scale_px
from ui_text_layout import ellipsize_text, wrap_text_limited

# ── Tetromino şekilleri ──────────────────────────────────────────────
_PIECE_SHAPES: Dict[str, List[List[int]]] = {
    "I": [[0, 0, 0, 0], [1, 1, 1, 1], [0, 0, 0, 0], [0, 0, 0, 0]],
    "O": [[1, 1], [1, 1]],
    "T": [[0, 1, 0], [1, 1, 1], [0, 0, 0]],
    "S": [[0, 1, 1], [1, 1, 0], [0, 0, 0]],
    "Z": [[1, 1, 0], [0, 1, 1], [0, 0, 0]],
    "J": [[1, 0, 0], [1, 1, 1], [0, 0, 0]],
    "L": [[0, 0, 1], [1, 1, 1], [0, 0, 0]],
    "Plus": [[0, 1, 0], [1, 1, 1], [0, 1, 0]],
    "Y": [[1, 0, 1], [1, 1, 1], [0, 1, 0]],
    "Domino": [[1, 1], [0, 0]],
    "BigSquare": [[1, 1, 1], [1, 1, 1], [1, 1, 1]],
}

# ── Preset renk paleti ──────────────────────────────────────────────
_PRESET_COLORS: List[Tuple[int, int, int]] = [
    (0, 240, 255),    # Neon Cyan
    (255, 0, 200),    # Neon Magenta
    (0, 255, 150),    # Neon Green
    (255, 215, 0),    # Gold
    (255, 80, 80),    # Coral Red
    (80, 130, 255),   # Royal Blue
    (255, 150, 0),    # Orange
    (180, 80, 255),   # Purple
    (255, 255, 255),  # White
    (40, 40, 60),     # Dark
]

# ═════════════════════════════════════════════════════════════════════
#  YARDIMCILAR
# ═════════════════════════════════════════════════════════════════════

def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))

def _rgb_to_hsv(r: int, g: int, b: int) -> Tuple[float, float, float]:
    return colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)

def _hsv_to_rgb(h: float, s: float, v: float) -> Tuple[int, int, int]:
    r, g, b = colorsys.hsv_to_rgb(_clamp(h), _clamp(s), _clamp(v))
    return (int(round(r * 255)), int(round(g * 255)), int(round(b * 255)))

def _hex_from_rgb(r: int, g: int, b: int) -> str:
    return f"#{r:02X}{g:02X}{b:02X}"


def _to_rgb_tuple(values: List[int]) -> Tuple[int, int, int]:
    return (int(values[0]), int(values[1]), int(values[2]))

def _rgb_from_hex(s: str) -> Optional[Tuple[int, int, int]]:
    s = s.strip().lstrip("#")
    if len(s) == 6:
        try:
            return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))
        except ValueError:
            pass
    return None

def _get_font(size: int, bold: bool = False):
    try:
        from ui_theme import UIFonts
        return UIFonts.get(size, bold)
    except Exception:
        f = pygame.font.Font(None, size)
        if bold:
            f.set_bold(True)
        return f


# ═════════════════════════════════════════════════════════════════════
#  DİYALOG ÖLÇEK / CONTAINMENT YARDIMCILARI — P0-4/P1-8
#  (Quadrix Tüm Ekranlar Ölçekleme Denetim Raporu, 2026-10-03)
#
#  Renk seçici ve metin giriş diyalogları daha önce sabit taban ölçüler
#  (min 520x420 / sabit 230 yükseklik, 130x44 buton, 18 pad) kullanıyordu;
#  küçük pencerede (ör. 640x360) sabit minimumlar diyalogu EKRANDAN
#  taşıyordu. Yeni sözleşme:
#  - Tüm ölçüler ui_scaling effective modal eğrisiyle ölçeklenir
#    (campaign modallarıyla aynı 1366x768 referansı → 1366x768'de ölçek
#    1.0, mevcut görünüm birebir korunur; preset duyarlı).
#  - Diyalog rect'i safe rect'e (yoksa ekran) clamp'li üretilir.
#  - İçerik sığmıyorsa floor'lar korunarak quantalı küçültme merdiveni
#    uygulanır (font/ölçü cache disiplini: sınırlı boyut seti).
#  - Rect'ler çizimden ÖNCE tek kaynaktan üretilir; event/hit-test aynı
#    Rect'leri kullanır.
# ═════════════════════════════════════════════════════════════════════

# Campaign modallarıyla aynı referans (campaign_ui._MODAL_SCALE_REFERENCE_SIZE
# paritesi): 1366x768'de modal ölçek 1.0 → diyalog görünümü korunur.
_DIALOG_MODAL_REFERENCE_SIZE = (1366.0, 768.0)

# Küçültme merdiveni — quantalı adımlar (üretilen ölçü seti sınırlı kalır).
_DIALOG_SHRINK_LADDER = (1.0, 0.88, 0.76, 0.64, 0.52)


def _dialog_modal_scale(screen: pygame.Surface) -> float:
    """Diyalog ölçeği — ui_scaling effective modal eğrisi (preset duyarlı)."""
    try:
        from ui_scaling import get_effective_modal_scale
        return float(get_effective_modal_scale(
            screen,
            profile="standard",
            reference_size=_DIALOG_MODAL_REFERENCE_SIZE,
        ))
    except Exception:
        return 1.0


def _dialog_safe_bounds(screen: pygame.Surface) -> pygame.Rect:
    """P0-4: diyalog güvenli alanı — A1 safe rect varsa o, yoksa tam ekran."""
    try:
        from game_over_surfaces import get_render_safe_rect
        safe = get_render_safe_rect(screen)
        if safe is not None and safe.width > 0 and safe.height > 0:
            return pygame.Rect(safe)
    except Exception:
        pass
    return screen.get_rect()


def _compute_picker_layout(
    sw: int,
    sh: int,
    has_preview: bool,
    ms: float,
    bounds: pygame.Rect,
) -> Dict[str, object]:
    """Renk seçici diyalog düzeni — ölç-önce, tek rect kaynağı (P0-4/P1-8).

    Bileşen ölçüleri modal ölçeğiyle (ms) ölçeklenir; güvenli alana
    sığmayan içerik floor'lar korunarak küçültme merdiveniyle daraltılır.
    Dönen diyalog rect'i daima ``bounds`` içinde kalır — sabit 520x420
    taban minimumları küçük pencerede diyalogu ekrandan taşıyordu.
    1366x768 / ms=1.0'da ürettiği ölçüler eski sabit düzenle birebir
    aynıdır (regresyon testi bu noktayı pin'ler).
    """
    def _spx(value: float, minimum: int = 1) -> int:
        return scale_px(value, ms, minimum=minimum)

    margin = _spx(24, minimum=8)
    avail_w = max(160, bounds.width - margin * 2)
    avail_h = max(160, bounds.height - margin * 2)

    for shrink in _DIALOG_SHRINK_LADDER:
        pad = max(6, _spx(18 * shrink))
        top_bar = max(24, _spx(52 * shrink))
        hue_w = max(12, _spx(28 * shrink))
        preview_w = max(60, _spx(160 * shrink)) if has_preview else 0
        right_w = max(70, _spx(150 * shrink))
        preset_h = max(22, _spx(38 * shrink))
        slider_h = max(16, _spx(30 * shrink))
        slider_gap = max(4, _spx(10 * shrink))
        sliders_h = slider_h * 3 + slider_gap * 2
        btn_h = max(26, _spx(48 * shrink))
        btn_w = max(56, _spx(130 * shrink))
        btn_gap_h = max(6, _spx(16 * shrink))
        cmp_h = max(40, _spx(84 * shrink))
        hex_gap = max(6, _spx(14 * shrink))
        hex_h = max(24, _spx(34 * shrink))

        sv_sz = min(_spx(300), int(sw * 0.30), int(sh * 0.42))
        sv_sz = max(80, int(sv_sz * shrink))

        content_w = (preview_w + sv_sz + hue_w + right_w +
                     pad * (5 if has_preview else 4))
        dw = min(content_w, avail_w)
        # P1-8: buton satırı daima diyalog genişliğine sığar (dar alan guard'ı).
        if btn_w * 2 + btn_gap_h + pad * 2 > dw:
            btn_w = max(40, (dw - pad * 2 - btn_gap_h) // 2)
        content_h = (top_bar + pad + sv_sz + pad +
                     preset_h + pad + sliders_h + pad + btn_h + pad)
        if content_w <= avail_w and content_h <= avail_h:
            break

    dh = min(content_h, avail_h)
    dx = bounds.left + (bounds.width - dw) // 2
    dy = bounds.top + (bounds.height - dh) // 2
    d_rect = pygame.Rect(dx, dy, dw, dh)

    ix = dx + pad
    iy = dy + top_bar + pad

    if has_preview:
        prev_rect: Optional[pygame.Rect] = pygame.Rect(ix, iy, preview_w, sv_sz)
        pk_x = ix + preview_w + pad
    else:
        prev_rect = None
        pk_x = ix

    sv_rect = pygame.Rect(pk_x, iy, sv_sz, sv_sz)
    hue_x = pk_x + sv_sz + pad
    hue_rect = pygame.Rect(hue_x, iy, hue_w, sv_sz)

    rp_x = hue_x + hue_w + pad
    # Sağ kolon kalan diyalog genişliğine iner; dejenere dar ekranda 24 px
    # taban (normal genişlikte kalan ≡ right_w → görünüm birebir korunur).
    rp_remaining = dx + dw - pad - rp_x
    rp_w = rp_remaining if rp_remaining >= 24 else 24

    old_r = pygame.Rect(rp_x, iy, rp_w, cmp_h // 2)
    new_r = pygame.Rect(rp_x, iy + cmp_h // 2, rp_w, cmp_h // 2)
    hex_rect = pygame.Rect(rp_x, iy + cmp_h + hex_gap, rp_w, hex_h)
    rgb_y = hex_rect.bottom + max(6, _spx(12 * shrink))

    preset_y = iy + sv_sz + pad
    preset_x = pk_x
    preset_total_w = sv_sz + pad + hue_w
    n_presets = len(_PRESET_COLORS)
    swatch_gap = max(2, _spx(5))
    swatch_sz = min(
        _spx(30 * shrink, minimum=10),
        (preset_total_w - (n_presets - 1) * swatch_gap) // n_presets,
    )
    swatch_sz = max(8, swatch_sz)
    preset_row_w = n_presets * swatch_sz + (n_presets - 1) * swatch_gap
    preset_ox = preset_x + (preset_total_w - preset_row_w) // 2

    preset_rects: List[pygame.Rect] = []
    for i in range(n_presets):
        preset_rects.append(pygame.Rect(
            preset_ox + i * (swatch_sz + swatch_gap),
            preset_y + 4, swatch_sz, swatch_sz))

    sl_y = preset_y + preset_h + pad
    sl_w = preset_total_w
    r_sl = pygame.Rect(pk_x, sl_y, sl_w, slider_h)
    g_sl = pygame.Rect(pk_x, sl_y + slider_h + slider_gap, sl_w, slider_h)
    b_sl = pygame.Rect(pk_x, sl_y + (slider_h + slider_gap) * 2, sl_w, slider_h)

    btn_y = dy + dh - btn_h - pad
    ok_rect = pygame.Rect(dx + dw - pad - btn_w * 2 - btn_gap_h, btn_y, btn_w, btn_h)
    cancel_rect = pygame.Rect(dx + dw - pad - btn_w, btn_y, btn_w, btn_h)

    return {
        'ms': float(ms), 'shrink': float(shrink),
        'dw': dw, 'dh': dh, 'dx': dx, 'dy': dy, 'd_rect': d_rect,
        'pad': pad, 'top_bar': top_bar,
        'sv_sz': sv_sz, 'hue_w': hue_w, 'preview_w': preview_w,
        'right_w': right_w, 'preset_h': preset_h,
        'slider_h': slider_h, 'slider_gap': slider_gap, 'sliders_h': sliders_h,
        'btn_h': btn_h, 'btn_w': btn_w, 'btn_gap_h': btn_gap_h,
        'btn_y': btn_y, 'ok_rect': ok_rect, 'cancel_rect': cancel_rect,
        'hint_y': btn_y + btn_h + 4,
        'ix': ix, 'iy': iy, 'pk_x': pk_x, 'hue_x': hue_x,
        'prev_rect': prev_rect, 'sv_rect': sv_rect, 'hue_rect': hue_rect,
        'rp_x': rp_x, 'rp_w': rp_w, 'cmp_h': cmp_h,
        'old_r': old_r, 'new_r': new_r,
        'hex_rect': hex_rect, 'rgb_y': rgb_y,
        'preset_y': preset_y, 'preset_x': preset_x,
        'preset_total_w': preset_total_w, 'swatch_sz': swatch_sz,
        'swatch_gap': swatch_gap, 'preset_row_w': preset_row_w,
        'preset_ox': preset_ox, 'preset_rects': preset_rects,
        'sl_y': sl_y, 'sl_w': sl_w,
        'r_sl': r_sl, 'g_sl': g_sl, 'b_sl': b_sl,
    }


def _compute_text_input_layout(
    sw: int,
    sh: int,
    ms: float,
    bounds: pygame.Rect,
    prompt_wrap_fn=None,
    prompt_line_h: int = 0,
) -> Dict[str, object]:
    """Metin giriş diyalog düzeni — ölç-önce, tek rect kaynağı (P0-4/P1-8).

    Sabit 230 yükseklik / 520 genişlik yerine: genişlik modal ölçekli
    tabandan güvenli alana clamp'lenir; yükseklik başlık + sarılan prompt
    + input + buton satırı içerik bütçesinden üretilir. Uzun prompt
    ``prompt_wrap_fn(max_w, max_lines) -> list[str]`` ile en fazla 2 satıra
    sarılır; dikey bütçe yetmezse küçültme merdiveni prompt satırlarını
    kontrollü düşürür. Butonlar yan yana sığmadığında sağ altta dikey
    stack'e geçer (P1-8: "dar alanda düğmeleri alt alta").
    """
    def _spx(value: float, minimum: int = 1) -> int:
        return scale_px(value, ms, minimum=minimum)

    margin = _spx(24, minimum=8)
    avail_w = max(140, bounds.width - margin * 2)
    avail_h = max(120, bounds.height - margin * 2)

    prompt_lines: List[str] = []
    for shrink in _DIALOG_SHRINK_LADDER:
        pad = max(6, _spx(18 * shrink))
        title_gap = max(8, _spx(14 * shrink))
        sep_gap = max(24, _spx(48 * shrink))
        prompt_gap = max(30, _spx(60 * shrink))
        inp_h = max(24, _spx(44 * shrink))
        inp_gap = max(10, _spx(29 * shrink))
        btn_h = max(24, _spx(44 * shrink))
        btn_w = max(64, _spx(130 * shrink))
        btn_gap_h = max(6, _spx(16 * shrink))
        prompt_line_gap = max(2, _spx(4 * shrink))

        dw = min(max(_spx(520), btn_w * 2 + btn_gap_h + pad * 2), avail_w)
        # P1-8: butonlar yan yana sığmıyorsa sağ altta dikey stack.
        buttons_stacked = (btn_w * 2 + btn_gap_h + pad * 2) > dw
        if buttons_stacked:
            btn_row_h = btn_h * 2 + btn_gap_h
            btn_w = max(40, min(btn_w, dw - pad * 2))
        else:
            btn_row_h = btn_h

        # Prompt satır bütçesi: merdiven ilerledikçe kontrollü düşür.
        max_prompt_lines = 2 if shrink >= 0.76 else (1 if shrink >= 0.52 else 0)
        prompt_lines = (
            list(prompt_wrap_fn(dw - pad * 2, max_prompt_lines))
            if (prompt_wrap_fn is not None and max_prompt_lines > 0) else []
        )
        prompt_h = (
            len(prompt_lines) * (int(prompt_line_h) + prompt_line_gap)
            - prompt_line_gap
        ) if prompt_lines else 0

        inp_y_off = max(
            _spx(95 * shrink),
            prompt_gap + prompt_h + max(6, _spx(12 * shrink)),
        )
        content_h = inp_y_off + inp_h + inp_gap + btn_row_h + pad
        if content_h <= avail_h:
            break

    dh = min(content_h, avail_h)
    dx = bounds.left + (bounds.width - dw) // 2
    dy = bounds.top + (bounds.height - dh) // 2
    d_rect = pygame.Rect(dx, dy, dw, dh)

    inp_rect = pygame.Rect(dx + pad, dy + inp_y_off, dw - pad * 2, inp_h)
    btn_y = dy + dh - btn_row_h - pad
    if buttons_stacked:
        ok_rect = pygame.Rect(dx + dw - pad - btn_w, btn_y, btn_w, btn_h)
        cancel_rect = pygame.Rect(
            dx + dw - pad - btn_w, btn_y + btn_h + btn_gap_h, btn_w, btn_h)
    else:
        ok_rect = pygame.Rect(dx + dw - pad - btn_w * 2 - btn_gap_h, btn_y, btn_w, btn_h)
        cancel_rect = pygame.Rect(dx + dw - pad - btn_w, btn_y, btn_w, btn_h)

    return {
        'ms': float(ms), 'shrink': float(shrink),
        'dw': dw, 'dh': dh, 'dx': dx, 'dy': dy, 'd_rect': d_rect,
        'pad': pad, 'inp_rect': inp_rect,
        'ok_rect': ok_rect, 'cancel_rect': cancel_rect,
        'buttons_stacked': buttons_stacked, 'btn_row_h': btn_row_h,
        'title_y': dy + title_gap, 'sep_y': dy + sep_gap,
        'prompt_y': dy + prompt_gap, 'prompt_line_gap': prompt_line_gap,
        'prompt_lines': prompt_lines,
        'btn_w': btn_w, 'btn_h': btn_h, 'btn_gap_h': btn_gap_h,
    }


# ═════════════════════════════════════════════════════════════════════
#  GERÇEK JELLY BLOK RENDERER
# ═════════════════════════════════════════════════════════════════════

def _real_jelly_block(surf: pygame.Surface, x: int, y: int,
                      size: int, color: Tuple[int, int, int]):
    """Oyun içindeki gerçek jelly renderer'ı kullan."""
    try:
        from renderers.jelly_renderer import draw_jelly_block
        draw_jelly_block(surf, x, y, size, color)
    except Exception:
        # Fallback: basit blok
        pygame.draw.rect(surf, color, (x, y, size, size))
        hl = tuple(min(255, c + 60) for c in color[:3])
        pygame.draw.rect(surf, hl, (x + 1, y + 1, size // 3, size // 3))


def _draw_piece_real(surf: pygame.Surface, cx: int, cy: int,
                     name: str, color: Tuple[int, int, int],
                     max_sz: int, pulse: float = 0.0):
    """Parça önizleme — gerçek jelly blok renderer ile."""
    shape = _PIECE_SHAPES.get(name)
    if not shape:
        _real_jelly_block(surf, cx - 16, cy - 16, 32, color)
        return
    rows = len(shape)
    cols = max(len(r) for r in shape)
    cell = min(max_sz // max(rows, cols), 40)
    cell = int(cell * (1.0 + pulse * 0.04))
    gap = 1
    tw, th = cols * cell, rows * cell
    ox, oy = cx - tw // 2, cy - th // 2
    for r in range(rows):
        for c in range(len(shape[r])):
            if shape[r][c]:
                _real_jelly_block(surf, ox + c * cell + gap,
                                  oy + r * cell + gap,
                                  cell - gap * 2, color)


# ═════════════════════════════════════════════════════════════════════
#  CACHE SİSTEMİ — performans için tüm ağır yüzeyler önceden oluşturulur
# ═════════════════════════════════════════════════════════════════════

def _build_sv_surface(w: int, h: int, hue: float) -> pygame.Surface:
    """SV gradyan — 2 şerit + ölçekleme + BLEND_RGB_MULT ile hızlı.

    Eski yöntem: w×h adet set_at() (~90.000 çağrı 300×300 için).
    Yeni yöntem:
      1. Yatay doygunluk şeridi (w×1): beyaz → saf hue rengi   → w piksel
      2. Dikey parlaklık şeridi  (1×h): beyaz(üst) → siyah(alt) → h piksel
      Toplam: w+h set_at() çağrısı + 2 transform.scale + 1 blit.
        Görsel olarak HSV yüzeyiyle eşdeğer davranır; integer yuvarlama nedeniyle
        bazı piksellerde 1-3 seviyelik fark oluşabilir, ancak gerçek kullanımda
        ayırt edilemez.
    """
    hue_rgb = _hsv_to_rgb(hue, 1.0, 1.0)

    # Yatay doygunluk şeridi: beyaz (sol) → saf hue rengi (sağ)
    sat_strip = pygame.Surface((w, 1))
    for x in range(w):
        s = x / max(1, w - 1)
        r = int(round(255 * (1.0 - s) + hue_rgb[0] * s))
        g = int(round(255 * (1.0 - s) + hue_rgb[1] * s))
        b = int(round(255 * (1.0 - s) + hue_rgb[2] * s))
        sat_strip.set_at((x, 0), (r, g, b))

    # Tam boyuta ölçekle: her satır aynı yatay gradyanı tekrarlar
    surf = pygame.transform.scale(sat_strip, (w, h))

    # Dikey parlaklık şeridi: tam beyaz (üst) → tam siyah (alt)
    val_strip = pygame.Surface((1, h))
    for y in range(h):
        brightness = int(round(255 * (1.0 - y / max(1, h - 1))))
        val_strip.set_at((0, y), (brightness, brightness, brightness))

    val_overlay = pygame.transform.scale(val_strip, (w, h))

    # BLEND_RGB_MULT: her pikseli v katsayısıyla karartır → altta siyah
    surf.blit(val_overlay, (0, 0), special_flags=pygame.BLEND_RGB_MULT)

    return surf


def _build_hue_bar(w: int, h: int) -> pygame.Surface:
    surf = pygame.Surface((w, h))
    for y in range(h):
        hh = y / max(1, h - 1)
        r, g, b = _hsv_to_rgb(hh, 1.0, 1.0)
        pygame.draw.line(surf, (r, g, b), (0, y), (w - 1, y))
    return surf


def _build_slider_fill(w: int, h: int, color: Tuple[int, int, int]) -> pygame.Surface:
    """Slider gradient dolgusu — cached."""
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    top_c = tuple(min(255, c + 50) for c in color[:3])
    bot_c = tuple(max(0, c - 30) for c in color[:3])
    for y in range(h):
        blend_ratio = y / max(1, h - 1)
        lc = tuple(int(top_c[i] + (bot_c[i] - top_c[i]) * blend_ratio) for i in range(3))
        pygame.draw.line(surf, (*lc, 210), (0, y), (w - 1, y))
    return surf


def _build_button_surf(w: int, h: int, color: Tuple[int, int, int],
                       hover: bool) -> pygame.Surface:
    """Buton gradient yüzeyi — cached."""
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    bc = color[:3]
    top = tuple(min(255, c + 40) for c in bc)
    bot = tuple(max(0, c - 25) for c in bc)
    alpha = 240 if hover else 190
    for y in range(h):
        blend_ratio = y / max(1, h - 1)
        lc = tuple(int(top[i] + (bot[i] - top[i]) * blend_ratio) for i in range(3))
        pygame.draw.line(surf, (*lc, alpha), (0, y), (w - 1, y))
    # Round mask
    mask = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.rect(mask, (255, 255, 255, 255), (0, 0, w, h), border_radius=12)
    out = pygame.Surface((w, h), pygame.SRCALPHA)
    out.blit(surf, (0, 0))
    out.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    return out


def _build_overlay(sw: int, sh: int) -> pygame.Surface:
    """Karartma overlay — bir kez oluştur."""
    ov = pygame.Surface((sw, sh), pygame.SRCALPHA)
    ov.fill((0, 0, 0, 190))
    return ov


def _build_glass_panel(w: int, h: int, bg, border, radius: int) -> pygame.Surface:
    """Glass panel yüzeyi — cached."""
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.rect(surf, bg, (0, 0, w, h), border_radius=radius)
    # Üst gradient
    for y in range(min(h, 50)):
        a = int(25 * (1.0 - y / 50.0))
        pygame.draw.line(surf, (255, 255, 255, a), (0, y), (w, y))
    # Kenar
    pygame.draw.rect(surf, border, (0, 0, w, h), width=2, border_radius=radius)
    # Üst parlama
    if w > radius * 2:
        hl = pygame.Surface((w - radius * 2, 1), pygame.SRCALPHA)
        hl.fill((255, 255, 255, 45))
        surf.blit(hl, (radius, 1))
    return surf


def _build_separator(w: int) -> pygame.Surface:
    """Neon ayırıcı çizgi — cached."""
    surf = pygame.Surface((w, 2), pygame.SRCALPHA)
    hw = w / 2
    for x in range(w):
        falloff = 1.0 - abs(x - hw) / max(1, hw)
        surf.set_at((x, 0), (0, 240, 255, int(55 * falloff)))
        surf.set_at((x, 1), (0, 240, 255, int(20 * falloff)))
    return surf


# ═════════════════════════════════════════════════════════════════════
#  ÇİZİM PRİMİTİFLERİ (hafif)
# ═════════════════════════════════════════════════════════════════════

def _draw_premium_button(surf, rect, text, font, base_color,
                         hover=False, btn_cache=None):
    """Buton çiz — cached yüzey kullan."""
    if btn_cache:
        surf.blit(btn_cache, rect.topleft)
    else:
        pygame.draw.rect(surf, (*base_color[:3], 190), rect, border_radius=12)

    if hover:
        pygame.draw.rect(surf, (255, 255, 255, 200), rect, width=2, border_radius=12)
    else:
        dark = tuple(max(0, c - 40) for c in base_color[:3])
        pygame.draw.rect(surf, (*dark, 160), rect, width=1, border_radius=12)

    # Highlight üst çizgi
    hl = pygame.Surface((rect.w - 8, 1), pygame.SRCALPHA)
    hl.fill((255, 255, 255, 55 if hover else 30))
    surf.blit(hl, (rect.x + 4, rect.y + 3))

    # Metin
    t_surf = font.render(text, True, (255, 255, 255))
    tx = rect.centerx - t_surf.get_width() // 2
    ty = rect.centery - t_surf.get_height() // 2
    # Gölge
    sh = font.render(text, True, (0, 0, 0))
    surf.blit(sh, (tx + 1, ty + 1))
    surf.blit(t_surf, (tx, ty))


# ═════════════════════════════════════════════════════════════════════
#  ANA RENK SEÇİCİ
# ═════════════════════════════════════════════════════════════════════

def pygame_color_picker(
    screen: pygame.Surface,
    initial_color: Tuple[int, int, int] = (255, 0, 0),
    title: str = "",
    piece_name: str = "",
    settings_manager = None,
) -> Optional[Tuple[int, int, int]]:
    """Quadrix premium renk seçici."""
    from localization import t

    if not title:
        try:
            title = t("color_picker_title")
        except Exception:
            title = "Renk Seçici"

    clock = pygame.time.Clock()
    sw, sh = screen.get_size()
    t0 = time.time()

    # ── Layout (P0-4/P1-8: ölçek + safe-rect bağlı, ölç-önce) ──────────
    # Düzen tek kaynaktan (_compute_picker_layout) üretilir; aşağıdaki
    # unpack satırları döngü/event kodunun aynı değişken adlarını kullanmasını
    # korur (minimal blast radius).
    has_preview = bool(piece_name and piece_name in _PIECE_SHAPES)
    ms = _dialog_modal_scale(screen)
    bounds = _dialog_safe_bounds(screen)
    lay = _compute_picker_layout(sw, sh, has_preview, ms, bounds)

    pad = lay['pad']; top_bar = lay['top_bar']
    dw = lay['dw']; dh = lay['dh']; dx = lay['dx']; dy = lay['dy']
    d_rect = lay['d_rect']
    sv_sz = lay['sv_sz']; hue_w = lay['hue_w']; preview_w = lay['preview_w']
    right_w = lay['right_w']; preset_h = lay['preset_h']
    slider_h = lay['slider_h']; slider_gap = lay['slider_gap']
    sliders_h = lay['sliders_h']
    btn_h = lay['btn_h']; btn_w = lay['btn_w']; btn_gap_h = lay['btn_gap_h']
    btn_y = lay['btn_y']; hint_y = lay['hint_y']
    ok_rect = lay['ok_rect']; cancel_rect = lay['cancel_rect']
    ix = lay['ix']; iy = lay['iy']; pk_x = lay['pk_x']; hue_x = lay['hue_x']
    prev_rect = lay['prev_rect']; sv_rect = lay['sv_rect']; hue_rect = lay['hue_rect']
    rp_x = lay['rp_x']; rp_w = lay['rp_w']; cmp_h = lay['cmp_h']
    old_r = lay['old_r']; new_r = lay['new_r']
    hex_rect = lay['hex_rect']; rgb_y = lay['rgb_y']
    preset_y = lay['preset_y']; preset_x = lay['preset_x']
    preset_total_w = lay['preset_total_w']; swatch_sz = lay['swatch_sz']
    swatch_gap = lay['swatch_gap']; preset_row_w = lay['preset_row_w']
    preset_ox = lay['preset_ox']; preset_rects = lay['preset_rects']
    sl_y = lay['sl_y']; sl_w = lay['sl_w']
    r_sl = lay['r_sl']; g_sl = lay['g_sl']; b_sl = lay['b_sl']
    n_presets = len(_PRESET_COLORS)
    _sp = lambda value, minimum=1: scale_px(value, ms, minimum=minimum)

    # ── State ───────────────────────────────────────────────────────
    h, s, v = _rgb_to_hsv(*initial_color)
    cur = list(initial_color)
    orig: Tuple[int, int, int] = (initial_color[0], initial_color[1], initial_color[2])

    sv_cache: Optional[pygame.Surface] = None
    sv_hue: float = -1.0
    hue_surf = _build_hue_bar(hue_w, sv_sz)

    drag = ""
    hex_text = _hex_from_rgb(*cur)
    hex_edit = False
    hex_cur = len(hex_text)

    # Gamepad state: RGB kanal seçimi ve preset index
    _gp_state: dict = {'ch': 0, 'preset': 0}

    running = True
    result: Optional[Tuple[int, int, int]] = None

    # ── Cached Surfaces (bir kez oluştur) ───────────────────────────
    overlay_surf = _build_overlay(sw, sh)
    dialog_panel = _build_glass_panel(dw, dh,
                                      bg=(10, 10, 28, 235),
                                      border=(50, 70, 150, 200),
                                      radius=18)
    if has_preview and prev_rect:
        preview_panel = _build_glass_panel(preview_w, sv_sz,
                                           bg=(12, 12, 35, 215),
                                           border=(40, 55, 110, 160),
                                           radius=14)
        sep_surf = _build_separator(preview_w - 24)
    else:
        preview_panel = None
        sep_surf = None

    # Slider fill cache'leri
    sl_colors = [(255, 70, 70), (70, 255, 100), (70, 120, 255)]
    sl_fills = [_build_slider_fill(sl_w, slider_h, c) for c in sl_colors]

    # Buton cache'leri
    ok_btn_n = _build_button_surf(btn_w, btn_h, (0, 180, 100), False)
    ok_btn_h = _build_button_surf(btn_w, btn_h, (0, 180, 100), True)
    cancel_btn_n = _build_button_surf(btn_w, btn_h, (180, 40, 50), False)
    cancel_btn_h = _build_button_surf(btn_w, btn_h, (180, 40, 50), True)

    # Neon glow (dialog dış) — 3 katman, cached
    glow_layers: List[pygame.Surface] = []
    for i in range(3):
        gw = dw + 16 + i * 8
        gh = dh + 16 + i * 8
        g = pygame.Surface((gw, gh), pygame.SRCALPHA)
        a = max(4, 22 - i * 8)
        pygame.draw.rect(g, (0, 240, 255, a), (0, 0, gw, gh), border_radius=22 + i * 2)
        glow_layers.append(g)

    bg_snap = screen.copy()

    # Sync helpers
    def _sync_hsv():
        nonlocal cur, hex_text
        rgb = _hsv_to_rgb(h, s, v)
        cur[:] = list(rgb)
        hex_text = _hex_from_rgb(*rgb)
        hex_cur_fix()

    def _sync_rgb():
        nonlocal h, s, v, hex_text
        h, s, v = _rgb_to_hsv(*cur)
        hex_text = _hex_from_rgb(*cur)
        hex_cur_fix()

    def hex_cur_fix():
        nonlocal hex_cur
        hex_cur = min(hex_cur, len(hex_text))

    def _sval(rect, mx):
        return _clamp((mx - rect.x) / max(1, rect.w))

    # Font'lar — bir kez oluştur (P1-8: modal ölçeğiyle boyutlandır;
    # tabanlar okunabilirlik için korunur, boyut seti sınırlı kalır → cache)
    font_title = _get_font(_sp(28, minimum=12), bold=True)
    font_piece_name = _get_font(_sp(20, minimum=10), bold=True)
    font_badge = _get_font(_sp(14, minimum=9), bold=True)
    font_hex = _get_font(_sp(18, minimum=10), bold=True)
    font_vals = _get_font(_sp(16, minimum=10))
    font_preset_label = _get_font(_sp(13, minimum=9), bold=True)
    font_slider = _get_font(_sp(15, minimum=9), bold=True)
    font_btn = _get_font(_sp(20, minimum=11), bold=True)
    font_hint = _get_font(_sp(13, minimum=9))
    font_label = _get_font(_sp(14, minimum=9), bold=True)

    # P1-8: statik metinler döngü dışında bir kez üretilir (kare-başı
    # render yasağı); başlık diyalog genişliğine ASCII '...' ile sığar.
    title_fit = ellipsize_text(title, font_title, dw - pad * 2)
    title_surf = font_title.render(title_fit, True, (0, 240, 255))
    try:
        cl = t("color_picker_cancel")
    except Exception:
        cl = "İptal"
    try:
        from promptfont_support import resolve_nav_hint_label as _nav_hint
        _confirm_lbl = _nav_hint('ENTER', 'menu_confirm')
        _cancel_lbl = _nav_hint('ESC', 'menu_back')
    except Exception:
        _confirm_lbl, _cancel_lbl = 'ENTER', 'ESC'
    hint_text = f"{_cancel_lbl}: {t('cancel', 'Cancel')}  ·  {_confirm_lbl}: {t('confirm', 'Confirm')}"
    hint_fit = ellipsize_text(hint_text, font_hint, dw - pad * 2)
    hint_surf_c = font_hint.render(hint_fit, True, (65, 65, 95))
    preset_label_surf = font_preset_label.render(
        t('color_picker_preset_label', 'PRESET'), True, (90, 90, 120))

    # ── Ana Döngü ───────────────────────────────────────────────────
    # Gamepad: bu bloklayıcı döngü ana döngünün pump'ını atlar; gamepad'i
    # burada canlı tut. Pointer modunu bastır ki A=ENTER (onay) garantilensin.
    _gpm = None
    _gp_prev_suppress = False
    try:
        from gamepad_manager import get_gamepad_manager as _get_gpm
        _gpm = _get_gpm()
        _gp_prev_suppress = bool(getattr(_gpm, '_suppress_pointer_mode', False))
        _gpm.set_suppress_pointer_mode(True)
    except Exception:
        _gpm = None

    fps_limit = 0
    try:
        fps_limit = int(settings_manager.get('fps_limit', 0) or 0) if settings_manager else 0
    except Exception:
        fps_limit = 0
    frame_cap = resolve_frame_rate_cap(fps_limit)
    is_darwin_busy = (sys.platform == 'darwin' and hasattr(clock, 'tick_busy_loop'))

    while running:
        try:
            from gamepad_manager import pump_gamepad_into_event_queue as _gp_pump
            _gp_pump(16.0, 'menu')
        except Exception:
            pass
        mp = get_mouse_pos()
        h_ok = ok_rect.collidepoint(mp)
        h_cancel = cancel_rect.collidepoint(mp)
        now = time.time() - t0

        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False
                result = None
                break

            elif ev.type == pygame.KEYDOWN:
                if hex_edit:
                    if ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        p = _rgb_from_hex(hex_text)
                        if p:
                            cur[:] = list(p)
                            _sync_rgb()
                        hex_edit = False
                    elif ev.key == pygame.K_ESCAPE:
                        hex_edit = False
                        hex_text = _hex_from_rgb(*cur)
                    elif ev.key == pygame.K_BACKSPACE:
                        if hex_cur > 0:
                            hex_text = hex_text[:hex_cur - 1] + hex_text[hex_cur:]
                            hex_cur -= 1
                    elif ev.key == pygame.K_DELETE:
                        if hex_cur < len(hex_text):
                            hex_text = hex_text[:hex_cur] + hex_text[hex_cur + 1:]
                    elif ev.key == pygame.K_LEFT:
                        hex_cur = max(0, hex_cur - 1)
                    elif ev.key == pygame.K_RIGHT:
                        hex_cur = min(len(hex_text), hex_cur + 1)
                    elif ev.key == pygame.K_HOME:
                        hex_cur = 0
                    elif ev.key == pygame.K_END:
                        hex_cur = len(hex_text)
                    elif ev.unicode and ev.unicode in "0123456789abcdefABCDEF#":
                        if len(hex_text) < 7:
                            hex_text = hex_text[:hex_cur] + ev.unicode + hex_text[hex_cur:]
                            hex_cur += 1
                else:
                    if ev.key == pygame.K_ESCAPE:
                        running = False
                        result = None
                    elif ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        running = False
                        result = _to_rgb_tuple(cur)
                    # Gamepad RGB stepper: LB/RB (bracket) ile kanal seç,
                    # UP/DOWN ile değer değiştir
                    elif ev.key == pygame.K_UP:
                        # Aktif RGB kanalını +5 artır
                        ch_idx = getattr(self_state, '_gp_rgb_channel', 0) if 'self_state' in dir() else _gp_state.get('ch', 0)
                        cur[_gp_state.get('ch', 0)] = min(255, cur[_gp_state.get('ch', 0)] + 5)
                        _sync_rgb()
                    elif ev.key == pygame.K_DOWN:
                        cur[_gp_state.get('ch', 0)] = max(0, cur[_gp_state.get('ch', 0)] - 5)
                        _sync_rgb()
                    elif ev.key == pygame.K_LEFTBRACKET:
                        # Önceki RGB kanalı
                        _gp_state['ch'] = (_gp_state.get('ch', 0) - 1) % 3
                    elif ev.key == pygame.K_RIGHTBRACKET:
                        # Sonraki RGB kanalı
                        _gp_state['ch'] = (_gp_state.get('ch', 0) + 1) % 3
                    elif ev.key == pygame.K_LEFT:
                        # Preset swatchlar arası gezinme
                        _gp_state['preset'] = max(0, _gp_state.get('preset', 0) - 1)
                    elif ev.key == pygame.K_RIGHT:
                        _gp_state['preset'] = min(n_presets - 1, _gp_state.get('preset', 0) + 1)
                    elif ev.key == pygame.K_SPACE:
                        # Space ile aktif preset'i seç
                        pidx = _gp_state.get('preset', 0)
                        if 0 <= pidx < n_presets:
                            cur[:] = list(_PRESET_COLORS[pidx])
                            _sync_rgb()

            elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                mx, my = ev.pos
                if sv_rect.collidepoint(mx, my):
                    drag = "sv"
                    s = _clamp((mx - sv_rect.x) / max(1, sv_rect.w))
                    v = 1.0 - _clamp((my - sv_rect.y) / max(1, sv_rect.h))
                    _sync_hsv()
                elif hue_rect.collidepoint(mx, my):
                    drag = "hue"
                    h = _clamp((my - hue_rect.y) / max(1, hue_rect.h))
                    _sync_hsv()
                elif r_sl.collidepoint(mx, my):
                    drag = "r"
                    cur[0] = int(_sval(r_sl, mx) * 255)
                    _sync_rgb()
                elif g_sl.collidepoint(mx, my):
                    drag = "g"
                    cur[1] = int(_sval(g_sl, mx) * 255)
                    _sync_rgb()
                elif b_sl.collidepoint(mx, my):
                    drag = "b"
                    cur[2] = int(_sval(b_sl, mx) * 255)
                    _sync_rgb()
                elif ok_rect.collidepoint(mx, my):
                    running = False
                    result = _to_rgb_tuple(cur)
                elif cancel_rect.collidepoint(mx, my):
                    running = False
                    result = None
                elif hex_rect.collidepoint(mx, my):
                    hex_edit = True
                    hex_cur = len(hex_text)
                else:
                    for i, pr in enumerate(preset_rects):
                        if pr.collidepoint(mx, my):
                            cur[:] = list(_PRESET_COLORS[i])
                            _sync_rgb()
                            break
                    else:
                        if hex_edit:
                            p = _rgb_from_hex(hex_text)
                            if p:
                                cur[:] = list(p)
                                _sync_rgb()
                            hex_edit = False

            elif ev.type == pygame.MOUSEBUTTONUP:
                drag = ""

            elif ev.type == pygame.MOUSEMOTION:
                mx, my = ev.pos
                if drag == "sv":
                    s = _clamp((mx - sv_rect.x) / max(1, sv_rect.w))
                    v = 1.0 - _clamp((my - sv_rect.y) / max(1, sv_rect.h))
                    _sync_hsv()
                elif drag == "hue":
                    h = _clamp((my - hue_rect.y) / max(1, hue_rect.h))
                    _sync_hsv()
                elif drag == "r":
                    cur[0] = int(_sval(r_sl, mx) * 255)
                    _sync_rgb()
                elif drag == "g":
                    cur[1] = int(_sval(g_sl, mx) * 255)
                    _sync_rgb()
                elif drag == "b":
                    cur[2] = int(_sval(b_sl, mx) * 255)
                    _sync_rgb()

        # ═════════════════════════════════════════════════════════════
        #  ÇİZİM
        # ═════════════════════════════════════════════════════════════
        screen.blit(bg_snap, (0, 0))
        screen.blit(overlay_surf, (0, 0))

        # ── Neon glow (cached) ──
        for i, gl in enumerate(glow_layers):
            screen.blit(gl, (dx - 8 - i * 4, dy - 8 - i * 4))

        # ── Dialog panel (cached) ──
        screen.blit(dialog_panel, (dx, dy))

        # ── Başlık (P1-8: döngü dışında üretildi, ellipsis'li) ──
        screen.blit(title_surf, (dx + pad, dy + _sp(12, minimum=4)))
        pygame.draw.line(screen, (0, 240, 255, 50),
                         (dx + pad, dy + top_bar - 4),
                         (dx + dw - pad, dy + top_bar - 4), 1)

        # ── SOL: Blok Önizleme (gerçek jelly renderer) ─────────────
        if has_preview and prev_rect and preview_panel:
            screen.blit(preview_panel, prev_rect.topleft)

            # Parça adı
            ns = font_piece_name.render(piece_name, True, (0, 240, 255))
            screen.blit(ns, (prev_rect.centerx - ns.get_width() // 2,
                             prev_rect.y + 10))

            # ── YENİ bölümü ──
            new_y = prev_rect.y + 36
            badge_s = font_badge.render(t('color_picker_new_badge', 'YENI'), True, (0, 255, 150))
            bx = prev_rect.centerx - badge_s.get_width() // 2
            bp = pygame.Surface((badge_s.get_width() + 12, badge_s.get_height() + 6), pygame.SRCALPHA)
            pygame.draw.rect(bp, (0, 255, 150, 40), bp.get_rect(), border_radius=4)
            screen.blit(bp, (bx - 6, new_y))
            screen.blit(badge_s, (bx, new_y + 3))

            # Parça — gerçek jelly blok
            piece_cy = prev_rect.y + prev_rect.h * 2 // 5 + 5
            pulse = math.sin(now * 2.0) * 0.4
            _draw_piece_real(screen, prev_rect.centerx, piece_cy,
                             piece_name, _to_rgb_tuple(cur), preview_w - 30, pulse)

            # Ayırıcı (cached)
            sep_y_pos = prev_rect.y + prev_rect.h * 3 // 5
            if sep_surf:
                screen.blit(sep_surf, (prev_rect.x + 12, sep_y_pos))

            # ── ESKİ bölümü ──
            old_tag = font_badge.render(t('color_picker_old_badge', 'ESKI'), True, (140, 140, 165))
            screen.blit(old_tag,
                        (prev_rect.centerx - old_tag.get_width() // 2,
                         sep_y_pos + 8))

            old_cy = sep_y_pos + 14 + (prev_rect.bottom - sep_y_pos - 14) // 2
            _draw_piece_real(screen, prev_rect.centerx, old_cy,
                             piece_name, orig, preview_w - 44)

        # ── SV Picker ──────────────────────────────────────────────
        if sv_cache is None or abs(sv_hue - h) > 0.002:
            sv_cache = _build_sv_surface(sv_sz, sv_sz, h)
            sv_hue = h
        screen.blit(sv_cache, sv_rect.topleft)
        pygame.draw.rect(screen, (50, 70, 140), sv_rect, width=2, border_radius=2)

        # SV imleci
        cx = sv_rect.x + int(s * sv_rect.w)
        cy = sv_rect.y + int((1.0 - v) * sv_rect.h)
        # Neon glow
        gs2 = pygame.Surface((24, 24), pygame.SRCALPHA)
        pygame.draw.circle(gs2, (*cur[:3], 50), (12, 12), 12)
        screen.blit(gs2, (cx - 12, cy - 12))
        pygame.draw.circle(screen, (255, 255, 255), (cx, cy), 9, 2)
        pygame.draw.circle(screen, tuple(cur[:3]), (cx, cy), 6)
        pygame.draw.circle(screen, (255, 255, 255), (cx, cy), 3, 1)

        # ── Hue Çubuğu ─────────────────────────────────────────────
        screen.blit(hue_surf, hue_rect.topleft)
        pygame.draw.rect(screen, (50, 70, 140), hue_rect, width=2, border_radius=4)

        hy = hue_rect.y + int(h * hue_rect.h)
        hc = _hsv_to_rgb(h, 1.0, 1.0)
        # Üçgen oklar
        for side, xp in [(-1, hue_rect.x), (1, hue_rect.right)]:
            tip = xp + side * 7
            b1 = (xp + side * 1, hy - 5)
            b2 = (xp + side * 1, hy + 5)
            pygame.draw.polygon(screen, (255, 255, 255), [(tip, hy), b1, b2])
        pygame.draw.rect(screen, hc, (hue_rect.x, hy - 1, hue_w, 3))
        pygame.draw.rect(screen, (255, 255, 255), (hue_rect.x - 1, hy - 2, hue_w + 2, 5), 1, border_radius=2)

        # ── Sağ Panel: Renk Karşılaştırma ──────────────────────────
        pygame.draw.rect(screen, orig, old_r, border_radius=6)
        pygame.draw.rect(screen, tuple(cur), new_r, border_radius=6)
        cmp_border = pygame.Rect(rp_x, iy, rp_w, cmp_h)
        pygame.draw.rect(screen, (50, 70, 140), cmp_border, width=2, border_radius=6)

        # Neon accent
        pygame.draw.rect(screen, (0, 255, 150), (new_r.x, new_r.y, 3, new_r.h), border_radius=1)

        # Etiketler (okunabilir boyutta)
        for txt, r, col in [
            (t('color_picker_old_badge', 'ESKI'), old_r, (220, 220, 235)),
            (t('color_picker_new_badge', 'YENI'), new_r, (0, 255, 150)),
        ]:
            ls = font_label.render(txt, True, col)
            bg_s = pygame.Surface((ls.get_width() + 12, ls.get_height() + 6), pygame.SRCALPHA)
            bg_s.fill((0, 0, 0, 150))
            screen.blit(bg_s, (r.x + 4, r.y + 3))
            screen.blit(ls, (r.x + 10, r.y + 6))

        # ── HEX Input ──
        hx_bg = (35, 35, 65, 230) if hex_edit else (25, 25, 55, 210)
        hx_s = pygame.Surface((hex_rect.w, hex_rect.h), pygame.SRCALPHA)
        pygame.draw.rect(hx_s, hx_bg, hx_s.get_rect(), border_radius=8)
        screen.blit(hx_s, hex_rect.topleft)
        hx_b = (0, 240, 255) if hex_edit else (50, 65, 120)
        pygame.draw.rect(screen, hx_b, hex_rect, width=2 if hex_edit else 1, border_radius=8)
        hx_txt = font_hex.render(hex_text, True, (255, 255, 255))
        screen.blit(hx_txt, (hex_rect.x + 10, hex_rect.y + 7))
        if hex_edit and int(now * 2.5) % 2 == 0:
            pw = font_hex.size(hex_text[:hex_cur])[0]
            ccx = hex_rect.x + 10 + pw
            pygame.draw.line(screen, (0, 240, 255),
                             (ccx, hex_rect.y + 6), (ccx, hex_rect.bottom - 6), 2)

        # ── RGB / HSV Değerleri ─────────────────────────────────────
        vals = [
            (f"R: {cur[0]}", (255, 110, 110)),
            (f"G: {cur[1]}", (110, 255, 130)),
            (f"B: {cur[2]}", (110, 160, 255)),
            (f"H: {int(h * 360)}°", (200, 200, 220)),
            (f"S: {int(s * 100)}%", (200, 200, 220)),
            (f"V: {int(v * 100)}%", (200, 200, 220)),
        ]
        vy = rgb_y
        for txt, col in vals:
            if vy + 18 > d_rect.bottom - 60:
                break
            screen.blit(font_vals.render(txt, True, col), (rp_x + 6, vy))
            vy += 21

        # ── Preset Renk Paleti (P1-8: etiket döngü dışında üretildi) ──
        screen.blit(preset_label_surf,
                    (preset_x, preset_y - max(2, _sp(4, minimum=2))))

        for i, pr in enumerate(preset_rects):
            pc = _PRESET_COLORS[i]
            is_hover = pr.collidepoint(mp)
            is_sel = (list(pc) == cur)
            pygame.draw.rect(screen, pc, pr, border_radius=5)
            if is_sel:
                pygame.draw.rect(screen, (0, 240, 255),
                                 pr.inflate(6, 6), width=2, border_radius=7)
            elif is_hover:
                pygame.draw.rect(screen, (255, 255, 255),
                                 pr.inflate(4, 4), width=2, border_radius=6)
            else:
                dark = tuple(max(0, c - 50) for c in pc)
                pygame.draw.rect(screen, dark, pr, width=1, border_radius=5)

        # ── RGB Slider'lar (cached fill) ────────────────────────────
        sl_labels = ["R", "G", "B"]
        sl_rects = [r_sl, g_sl, b_sl]
        for i in range(3):
            rect = sl_rects[i]
            val = cur[i]
            ratio = val / 255.0
            col = sl_colors[i]

            # Koyu track
            pygame.draw.rect(screen, (20, 20, 42), rect, border_radius=8)

            # Fill (cached gradient, clip ile)
            fw = max(0, int(rect.w * ratio))
            if fw > 2:
                clip = sl_fills[i].subsurface(pygame.Rect(0, 0, fw, slider_h))
                screen.blit(clip, rect.topleft)

            pygame.draw.rect(screen, (*col, 80), rect, width=1, border_radius=8)

            # Handle
            hx = rect.x + int(rect.w * ratio)
            handle_r = 8
            pygame.draw.circle(screen, (255, 255, 255), (hx, rect.centery), handle_r)
            pygame.draw.circle(screen, col, (hx, rect.centery), handle_r - 2)
            pygame.draw.circle(screen, (255, 255, 255), (hx, rect.centery), handle_r - 4, 1)

            # Label (shadow + text)
            lbl = f"{sl_labels[i]}: {val}"
            sh = font_slider.render(lbl, True, (0, 0, 0))
            screen.blit(sh, (rect.x + 9, rect.y + 6))
            screen.blit(font_slider.render(lbl, True, (240, 240, 250)),
                        (rect.x + 8, rect.y + 5))

        # ── Butonlar (cached) ───────────────────────────────────────
        _draw_premium_button(screen, ok_rect, t('confirm', 'Confirm'), font_btn,
                             (0, 180, 100), h_ok,
                             btn_cache=ok_btn_h if h_ok else ok_btn_n)
        _draw_premium_button(screen, cancel_rect, cl, font_btn,
                             (180, 40, 50), h_cancel,
                             btn_cache=cancel_btn_h if h_cancel else cancel_btn_n)

        # ── Kısayol ipucu (P1-8: döngü dışında üretildi, ellipsis'li) ──
        screen.blit(hint_surf_c, (dx + pad, hint_y))

        pygame.display.flip()
        if is_darwin_busy:
            clock.tick_busy_loop(frame_cap)
        else:
            clock.tick(frame_cap)

    # Pointer-mode bastırmasını eski haline getir
    try:
        if _gpm is not None:
            _gpm.set_suppress_pointer_mode(_gp_prev_suppress)
    except Exception:
        pass

    pygame.event.clear()
    return result


# ═════════════════════════════════════════════════════════════════════
#  METİN GİRİŞİ
# ═════════════════════════════════════════════════════════════════════

def pygame_text_input(
    screen: pygame.Surface,
    title: str = "",
    prompt: str = "",
    initial_text: str = "",
    max_length: int = 40,
    settings_manager = None,
) -> Optional[str]:
    """Quadrix premium metin girişi — gamepad uyumlu.

    Gamepad ile: D-pad L/R ile input/OK/Cancel arası focus geçişi.
    Confirm (A/Enter) aktif focus'u uygular. Back (B/ESC) iptal eder.
    Input focus'tayken D-pad L/R cursor hareket ettirir.
    """
    clock = pygame.time.Clock()
    sw, sh = screen.get_size()
    t0 = time.time()

    # ── Layout (P0-4/P1-8: ölçek + safe-rect bağlı, ölç-önce) ──────────
    # Sabit 520x230 (ve sabit 95/44/130/16 ofsetleri) küçük pencerelerde
    # ekran/safe-rect bütçesini aşabiliyordu; artık modal ölçeği ile
    # boyutlanır, safe-rect'e clamp'lenir, sığmazsa kuantalı küçültme +
    # dar diyaloglarda dikey buton istifine düşer.
    ms = _dialog_modal_scale(screen)
    bounds = _dialog_safe_bounds(screen)
    _sp = lambda value, minimum=1: scale_px(value, ms, minimum=minimum)

    font_t = _get_font(_sp(26, minimum=14), bold=True)
    font_p = _get_font(_sp(18, minimum=11))
    font_i = _get_font(_sp(20, minimum=12))
    font_b = _get_font(_sp(20, minimum=12), bold=True)

    # Uzun prompt wrap edilir; satır bütçesi küçültme merdiveniyle
    # 2 → 1 → 0 düşer (diyalog yükseklik bütçesi korunarak).
    _prompt_wrap = None
    _prompt_line_h = 0
    if prompt:
        _prompt_wrap = lambda max_w, max_lines: wrap_text_limited(
            prompt, font_p, max_w, max_lines=max_lines).lines
        _prompt_line_h = font_p.get_height()

    lay = _compute_text_input_layout(sw, sh, ms, bounds,
                                     _prompt_wrap, _prompt_line_h)
    dw = lay['dw']; dh = lay['dh']; dx = lay['dx']; dy = lay['dy']
    d_rect = lay['d_rect']
    pad = lay['pad']
    inp_rect = lay['inp_rect']
    ok_rect = lay['ok_rect']; cancel_rect = lay['cancel_rect']
    btn_w = lay['btn_w']; btn_h = lay['btn_h']; btn_gap_h = lay['btn_gap_h']
    title_y = lay['title_y']; sep_y = lay['sep_y']; prompt_y = lay['prompt_y']
    prompt_line_gap = lay['prompt_line_gap']
    prompt_lines = lay['prompt_lines']

    text = initial_text
    cursor = len(text)
    running = True
    result: Optional[str] = None

    # Gamepad focus: 0=input, 1=OK, 2=Cancel
    gp_focus = 0

    bg_snap = screen.copy()
    overlay = _build_overlay(sw, sh)
    panel = _build_glass_panel(dw, dh,
                               bg=(10, 10, 28, 235),
                               border=(50, 70, 150, 200),
                               radius=18)
    ok_n = _build_button_surf(btn_w, btn_h, (0, 180, 100), False)
    ok_h = _build_button_surf(btn_w, btn_h, (0, 180, 100), True)
    cn_n = _build_button_surf(btn_w, btn_h, (180, 40, 50), False)
    cn_h = _build_button_surf(btn_w, btn_h, (180, 40, 50), True)

    # P1-8: statik metinler döngü dışında bir kez üretilir (kare-başı
    # render yasağı); başlık diyalog genişliğine ASCII '...' ile sığar.
    title_fit = ellipsize_text(title, font_t, dw - pad * 2)
    title_surf = font_t.render(title_fit, True, (0, 240, 255))
    _pl_h = font_p.get_height()
    prompt_positions = [
        (dx + pad, prompt_y + i * (_pl_h + prompt_line_gap))
        for i in range(len(prompt_lines))
    ]
    prompt_surfs = [font_p.render(line, True, (190, 190, 215))
                    for line in prompt_lines]

    # Gamepad: bloklayıcı döngü → pointer modunu bastır + her frame pump et.
    _gpm = None
    _gp_prev_suppress = False
    try:
        from gamepad_manager import get_gamepad_manager as _get_gpm
        _gpm = _get_gpm()
        _gp_prev_suppress = bool(getattr(_gpm, '_suppress_pointer_mode', False))
        _gpm.set_suppress_pointer_mode(True)
    except Exception:
        _gpm = None

    fps_limit = 0
    try:
        fps_limit = int(settings_manager.get('fps_limit', 0) or 0) if settings_manager else 0
    except Exception:
        fps_limit = 0
    frame_cap = resolve_frame_rate_cap(fps_limit)
    is_darwin_busy = (sys.platform == 'darwin' and hasattr(clock, 'tick_busy_loop'))

    while running:
        try:
            from gamepad_manager import pump_gamepad_into_event_queue as _gp_pump
            _gp_pump(16.0, 'menu')
        except Exception:
            pass
        mp = get_mouse_pos()
        ho = ok_rect.collidepoint(mp) or gp_focus == 1
        hc = cancel_rect.collidepoint(mp) or gp_focus == 2
        now = time.time() - t0

        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False
                result = None
            elif ev.type == pygame.KEYDOWN:
                if ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    if gp_focus == 2:
                        running = False
                        result = None
                    else:
                        running = False
                        result = text.strip() if text.strip() else None
                elif ev.key == pygame.K_ESCAPE:
                    running = False
                    result = None
                elif ev.key == pygame.K_TAB:
                    # Tab ile focus geçişi
                    gp_focus = (gp_focus + 1) % 3
                elif ev.key == pygame.K_DOWN:
                    # Input'tan butonlara geç
                    if gp_focus == 0:
                        gp_focus = 1
                elif ev.key == pygame.K_UP:
                    # Butonlardan input'a geç
                    if gp_focus in (1, 2):
                        gp_focus = 0
                elif ev.key == pygame.K_LEFT:
                    if gp_focus == 0:
                        cursor = max(0, cursor - 1)
                    elif gp_focus == 2:
                        gp_focus = 1
                elif ev.key == pygame.K_RIGHT:
                    if gp_focus == 0:
                        cursor = min(len(text), cursor + 1)
                    elif gp_focus == 1:
                        gp_focus = 2
                elif ev.key == pygame.K_BACKSPACE:
                    if gp_focus == 0 and cursor > 0:
                        text = text[:cursor - 1] + text[cursor:]
                        cursor -= 1
                elif ev.key == pygame.K_DELETE:
                    if gp_focus == 0 and cursor < len(text):
                        text = text[:cursor] + text[cursor + 1:]
                elif ev.key == pygame.K_HOME:
                    cursor = 0
                elif ev.key == pygame.K_END:
                    cursor = len(text)
                elif ev.unicode and len(text) < max_length and gp_focus == 0:
                    ch = ev.unicode
                    if ch.isprintable():
                        text = text[:cursor] + ch + text[cursor:]
                        cursor += 1
            elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                if ok_rect.collidepoint(ev.pos):
                    running = False
                    result = text.strip() if text.strip() else None
                elif cancel_rect.collidepoint(ev.pos):
                    running = False
                    result = None
                elif inp_rect.collidepoint(ev.pos):
                    gp_focus = 0

        screen.blit(bg_snap, (0, 0))
        screen.blit(overlay, (0, 0))
        screen.blit(panel, (dx, dy))

        # P1-8: statik başlık/prompt yüzeyleri döngü dışında üretildi.
        screen.blit(title_surf, (dx + pad, title_y))
        pygame.draw.line(screen, (0, 240, 255, 50),
                         (dx + pad, sep_y), (dx + dw - pad, sep_y), 1)

        for _pline_surf, _pline_pos in zip(prompt_surfs, prompt_positions):
            screen.blit(_pline_surf, _pline_pos)

        # Input
        ip = pygame.Surface((inp_rect.w, inp_rect.h), pygame.SRCALPHA)
        pygame.draw.rect(ip, (25, 25, 50, 230), ip.get_rect(), border_radius=10)
        screen.blit(ip, inp_rect.topleft)
        pygame.draw.rect(screen, (0, 240, 255), inp_rect, width=2, border_radius=10)
        screen.blit(font_i.render(text, True, (255, 255, 255)),
                    (inp_rect.x + 14, inp_rect.y + 10))

        if int(now * 2.5) % 2 == 0:
            pw = font_i.size(text[:cursor])[0]
            ccx = inp_rect.x + 14 + pw
            pygame.draw.line(screen, (0, 240, 255),
                             (ccx, inp_rect.y + 8), (ccx, inp_rect.bottom - 8), 2)

        try:
            from localization import t as _t
            cl = _t("color_picker_cancel")
        except Exception:
            cl = "İptal"

        _draw_premium_button(screen, ok_rect, "OK", font_b,
                             (0, 180, 100), ho, btn_cache=ok_h if ho else ok_n)
        _draw_premium_button(screen, cancel_rect, cl, font_b,
                             (180, 40, 50), hc, btn_cache=cn_h if hc else cn_n)

        pygame.display.flip()
        if is_darwin_busy:
            clock.tick_busy_loop(frame_cap)
        else:
            clock.tick(frame_cap)

    # Pointer-mode bastırmasını eski haline getir
    try:
        if _gpm is not None:
            _gpm.set_suppress_pointer_mode(_gp_prev_suppress)
    except Exception:
        pass

    pygame.event.clear()
    return result
