# -*- coding: utf-8 -*-
"""P0-4 + P1-8: renk seçici / metin girişi diyalog içerik bütçesi.

Kılavuz: Quadrix_Tum_Ekranlar_Olcekleme_Denetim_Raporu.md (2026-10-03).
- P0-4: Renk seçici diyaloğu sabit ölçülerle (pad=18, top_bar=52, hue_w=28,
  preview_w=160, right_w=150, btn_w=130, min 520x420) ve metin girişi sabit
  230 yüksekliği / 520 genişliği küçük pencere bütçesini aşıyordu; HSV
  yüzeyi kısmen küçülse de minimumlar içerik bütçesini geçebiliyordu.
- P1-8: Metin girişi uzun lokalizasyon için satır sarma / dikey buton
  istifi içeriyordu mu? — hayır: sabit yükseklik yanındaki prompt tek satır
  taşabiliyordu. Yeni sözleşme: ölç-önce düzen + safe-rect clamp.

Bu dosya KILITLEDİĞİ değişmezler:
1. Diyalog rect daima verilen bounds (ekran veya safe rect) içinde kalır.
2. Input/buton/slider rect'leri daima diyalogun içinde; butonlar ayrık.
3. 1366x768 / ms=1.0'da üretilen ölçüler ESKİ sabit düzenle birebir aynı
   (görünüm koruması — rapor: "mevcut görünüm korunur" taahhüdü).
4. Uzun TR/EN prompt satırları daima diyalog genişlik bütçesine sığar.
5. Kaynak sözleşme: sabit 230/520/420 yolları artık safe-rect clamp
   yolundan geçer.

Ölçüm sınırı (dürüst rapor): gerçek görsel doğrulama (Windows smoke,
canlı font yerleşimi) manuel tura aittir — dummy driver altında koşulmaz.
Kalıp: test_wide_arena_hud_scale_containment (dummy env önce + SRC yolu +
gerçek modül importu).
"""
from __future__ import annotations

import os
import pathlib
import re
import sys
import types

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import pytest

import color_picker as cp
from ui_scaling import scale_px

if not pygame.font.get_init():
    pygame.font.init()


MATRIX = [
    (640, 360),    # P0-4 küçük pencere: eski 420 tabanı ekranı taşırdı
    (800, 480),
    (1024, 600),
    (1280, 720),
    (1366, 768),   # referans: ms=1.0, baseline pin
    (1920, 1080),
    (3840, 2160),  # 4K: modal eğri üst clamp (1.20)
]

LONG_PROMPT_TR = (
    "Çok uzun bir Türkçe prompt metni: lütfen oyuncu adınızı girin, "
    "ENTER ile onaylayın ya da ESC ile vazgeçin, teşekkürler."
)
LONG_PROMPT_EN = (
    "A rather long English prompt line: please enter your player name, "
    "confirm with ENTER or cancel with ESC at any time, thank you."
)


def _screen_rect(w: int, h: int) -> pygame.Rect:
    return pygame.Rect(0, 0, w, h)


def _picker_layout(w, h, has_preview, bounds=None, ms=None):
    if bounds is None:
        bounds = _screen_rect(w, h)
    if ms is None:
        ms = cp._dialog_modal_scale(pygame.Surface((w, h)))
    return cp._compute_picker_layout(w, h, has_preview, ms, bounds)


def _text_input_layout(w, h, prompt=None, bounds=None, ms=None):
    if bounds is None:
        bounds = _screen_rect(w, h)
    if ms is None:
        ms = cp._dialog_modal_scale(pygame.Surface((w, h)))
    # Üretim koduyla AYNI font formülü (minimum dahil) — satır genişliği
    # ölçümü gerçek draw fontuyla anlamlı olsun.
    font_p = cp._get_font(scale_px(18, ms, minimum=11))
    wrap_fn = None
    line_h = 0
    if prompt:
        wrap_fn = lambda max_w, max_lines: cp.wrap_text_limited(
            prompt, font_p, max_w, max_lines=max_lines).lines
        line_h = font_p.get_height()
    lay = cp._compute_text_input_layout(w, h, ms, bounds, wrap_fn, line_h)
    return lay, font_p


# ── P0-4: renk seçici diyalog içerik bütçesi ───────────────────────────────


@pytest.mark.parametrize("w,h", MATRIX)
@pytest.mark.parametrize("has_preview", [False, True])
def test_picker_dialog_and_inner_rects_contained(w, h, has_preview):
    """Diyalog ⊆ ekran; tüm iç rect'ler ⊆ diyalog; butonlar ayrık."""
    lay = _picker_layout(w, h, has_preview)
    screen = _screen_rect(w, h)
    d = lay['d_rect']

    assert screen.contains(d), (
        f"renk seçici diyalogu ekrandan taşıyor: {w}x{h} "
        f"dialog={d} (P0-4)")
    inner = ['sv_rect', 'hue_rect', 'old_r', 'new_r', 'hex_rect',
             'r_sl', 'g_sl', 'b_sl', 'ok_rect', 'cancel_rect']
    if has_preview:
        inner.append('prev_rect')
    for key in inner:
        assert d.contains(lay[key]), (
            f"{key} diyalog dışına taşıyor: {w}x{h} {key}={lay[key]} "
            f"dialog={d} (P0-4)")
    assert not lay['ok_rect'].colliderect(lay['cancel_rect'])
    # Slider'lar butonların üstünde kalmalı (dikey akış).
    assert lay['b_sl'].bottom <= lay['ok_rect'].y
    # HSV yüzeyi okunabilirlik tabanının altına inmez.
    assert lay['sv_rect'].width >= 80
    # Plan aşaması Surface ÜRETMEZ (kare-başı tahsis yasağı).
    for value in lay.values():
        assert not isinstance(value, pygame.Surface)


@pytest.mark.parametrize("w,h", MATRIX)
def test_picker_modal_scale_matches_ui_scaling_curve(w, h):
    """Ölçek gerçek ui_scaling eğrisinden gelir; referans dışı clamplenir."""
    ms = cp._dialog_modal_scale(pygame.Surface((w, h)))
    from ui_scaling import get_effective_modal_scale
    expected = get_effective_modal_scale(
        pygame.Surface((w, h)),
        profile="standard",
        reference_size=(1366.0, 768.0),
    )
    assert ms == pytest.approx(float(expected))
    # 1366x768 referans noktası: görünüm koruma taahhüdü.
    assert cp._dialog_modal_scale(pygame.Surface((1366, 768))) == pytest.approx(1.0)


def test_picker_baseline_1366x768_matches_legacy_metrics():
    """1366x768 / ms=1.0 → eski sabit düzen ölçüleri birebir (regresyon pin).

    Eski değerler: pad=18, top_bar=52, sv=300, hue_w=28, right_w=150,
    preset_h=38, slider 30/gap 10, buton 130x48/gap 16, cmp 84, hex 34,
    dw=550 (önsüz) / 728 (önlü), dh=638.
    """
    bounds = _screen_rect(1366, 768)
    lay = cp._compute_picker_layout(1366, 768, False, 1.0, bounds)
    assert (lay['dw'], lay['dh']) == (550, 638)
    assert lay['shrink'] == 1.0
    assert lay['pad'] == 18
    assert lay['top_bar'] == 52
    assert lay['sv_sz'] == 300
    assert lay['hue_w'] == 28
    assert lay['right_w'] == 150
    assert lay['preset_h'] == 38
    assert (lay['slider_h'], lay['slider_gap']) == (30, 10)
    assert (lay['btn_w'], lay['btn_h'], lay['btn_gap_h']) == (130, 48, 16)
    assert lay['cmp_h'] == 84
    assert lay['rp_w'] == 150
    assert lay['swatch_sz'] == 30
    # Ofset paritesi: hex = iy + cmp + 14, buton satırı = dy + 572.
    assert lay['hex_rect'].y == lay['iy'] + 98
    assert lay['hex_rect'].height == 34
    assert lay['btn_y'] == lay['dy'] + 572
    assert lay['ok_rect'].x == lay['dx'] + 550 - 18 - 130 * 2 - 16
    # Önizlemeli varyant yalnız genişlik ekler.
    lay_p = cp._compute_picker_layout(1366, 768, True, 1.0, bounds)
    assert (lay_p['dw'], lay_p['dh']) == (728, 638)
    assert lay_p['preview_w'] == 160


# ── P0-4/P1-8: metin girişi diyalog içerik bütçesi ─────────────────────────


@pytest.mark.parametrize("w,h", MATRIX)
@pytest.mark.parametrize(
    "prompt_kind",
    ["none", "short", "long_tr", "long_en"],
)
def test_text_input_dialog_contained(w, h, prompt_kind):
    """Diyalog ⊆ ekran; input/buton ⊆ diyalog; prompt satırları bütçede."""
    prompt = {
        "none": None,
        "short": "Oyuncu adı:",
        "long_tr": LONG_PROMPT_TR,
        "long_en": LONG_PROMPT_EN,
    }[prompt_kind]
    lay, font_p = _text_input_layout(w, h, prompt)
    screen = _screen_rect(w, h)
    d = lay['d_rect']

    assert screen.contains(d), (
        f"metin girişi diyalogu ekrandan taşıyor: {w}x{h} dialog={d} (P0-4)")
    for key in ('inp_rect', 'ok_rect', 'cancel_rect'):
        assert d.contains(lay[key]), (
            f"{key} diyalog dışına taşıyor: {w}x{h} {key}={lay[key]} "
            f"dialog={d} (P0-4)")
    assert not lay['ok_rect'].colliderect(lay['cancel_rect'])
    assert lay['inp_rect'].bottom <= lay['ok_rect'].y
    # Uzun lokalizasyon: satır sayısı kontrollü, her satır genişlik
    # bütçesinin içinde (ASCII '...' ile kısaltılmış olabilir).
    assert len(lay['prompt_lines']) <= 2
    budget = lay['dw'] - lay['pad'] * 2
    for line in lay['prompt_lines']:
        assert font_p.size(line)[0] <= budget, (
            f"prompt satırı bütçeyi aşıyor: {w}x{h} kind={prompt_kind} "
            f"line={line[:40]!r} width={font_p.size(line)[0]} budget={budget}")
    # Plan aşaması Surface ÜRETMEZ (kare-başı tahsis yasağı).
    for value in lay.values():
        assert not isinstance(value, pygame.Surface)


def test_text_input_baseline_1366x768_matches_legacy_metrics():
    """1366x768 / ms=1.0 → eski sabit 520x230 ölçüleri birebir (pin).

    Eski değerler: pad=18, inp 44 y-ofset 95, buton 130x44/gap 16,
    başlık y+14, ayırıcı y+48, prompt y+60, OK x-ofset 226.
    """
    bounds = _screen_rect(1366, 768)
    lay, _ = _text_input_layout(1366, 768, None, bounds=bounds, ms=1.0)
    assert (lay['dw'], lay['dh']) == (520, 230)
    assert lay['shrink'] == 1.0
    assert lay['pad'] == 18
    assert lay['inp_rect'].height == 44
    assert lay['inp_rect'].y == lay['dy'] + 95
    assert lay['inp_rect'].width == 520 - 18 * 2
    assert (lay['btn_w'], lay['btn_h'], lay['btn_gap_h']) == (130, 44, 16)
    assert lay['title_y'] == lay['dy'] + 14
    assert lay['sep_y'] == lay['dy'] + 48
    assert lay['prompt_y'] == lay['dy'] + 60
    assert lay['ok_rect'].x == lay['dx'] + 520 - 18 - 130 * 2 - 16
    assert lay['buttons_stacked'] is False
    assert lay['prompt_lines'] == []


def test_text_input_buttons_stack_in_narrow_bounds():
    """P1-8: butonlar yan yana sığmadığında dikey istif (dar safe alan)."""
    narrow = pygame.Rect(0, 0, 200, 600)
    lay, _ = _text_input_layout(200, 600, None, bounds=narrow, ms=0.68)
    assert lay['buttons_stacked'] is True
    assert lay['btn_row_h'] == lay['btn_h'] * 2 + lay['btn_gap_h']
    assert narrow.contains(lay['d_rect'])
    for key in ('inp_rect', 'ok_rect', 'cancel_rect'):
        assert lay['d_rect'].contains(lay[key])
    assert not lay['ok_rect'].colliderect(lay['cancel_rect'])
    assert lay['inp_rect'].bottom <= lay['ok_rect'].y
    # İstifte OK üstte, İptal altta (konsol odak düzeni).
    assert lay['cancel_rect'].y > lay['ok_rect'].y


def test_picker_buttons_fit_narrow_dialog():
    """P1-8: dar diyalogda buton satırı genişliğe uyar (guard yolu)."""
    narrow = pygame.Rect(0, 0, 190, 700)
    lay = cp._compute_picker_layout(190, 700, False, 0.68, narrow)
    assert narrow.contains(lay['d_rect'])
    for key in ('ok_rect', 'cancel_rect', 'sv_rect', 'hue_rect'):
        assert lay['d_rect'].contains(lay[key]), (key, lay[key], lay['d_rect'])
    assert not lay['ok_rect'].colliderect(lay['cancel_rect'])
    assert lay['b_sl'].bottom <= lay['ok_rect'].y


# ── P0-4: safe-rect bağlaması (stub ile deterministik) ─────────────────────


def test_dialog_safe_bounds_uses_render_safe_rect(monkeypatch):
    """get_render_safe_rect geçerli rect döndürürse diyalog ona bağlanır."""
    stub = types.ModuleType("game_over_surfaces")
    safe = pygame.Rect(40, 30, 600, 320)
    stub.get_render_safe_rect = lambda screen: safe
    monkeypatch.setitem(sys.modules, "game_over_surfaces", stub)

    screen = pygame.Surface((800, 480))
    assert cp._dialog_safe_bounds(screen) == safe
    # Safe rect'e bağlanan düzen daima safe alanın içinde kalır.
    lay = cp._compute_picker_layout(800, 480, False, 1.0, safe)
    assert safe.contains(lay['d_rect'])
    ti = cp._compute_text_input_layout(800, 480, 1.0, safe)
    assert safe.contains(ti['d_rect'])


def test_dialog_safe_bounds_falls_back_to_screen(monkeypatch):
    """Geometri yoksa (None) tam-ekran clamp'e geri düşülür."""
    stub = types.ModuleType("game_over_surfaces")
    stub.get_render_safe_rect = lambda screen: None
    monkeypatch.setitem(sys.modules, "game_over_surfaces", stub)

    screen = pygame.Surface((800, 480))
    assert cp._dialog_safe_bounds(screen) == screen.get_rect()


# ── Kaynak sözleşmeleri (eski sabit yolların kalktığını pin'le) ────────────


def _cp_source() -> str:
    return pathlib.Path(cp.__file__).read_text(encoding="utf-8")


def test_source_no_fixed_legacy_dialog_paths():
    """Sabit 520/230/420 diyalog yolları kalktı; clamp yolundan geçer."""
    source = _cp_source()
    assert "dh = 230" not in source, "sabit metin girişi yüksekliği geri geldi"
    assert "dw = min(520, int(sw * 0.8))" not in source
    assert "max(min(content_h, int(sh * 0.90)), 420)" not in source
    assert "max(min(content_w, int(sw * 0.92)), 520)" not in source


def test_source_layout_single_source_and_scaling_contract():
    """Düzen tek kaynaktan + gerçek ölçek/sarma yardımcılarından geçer."""
    source = _cp_source()
    for needle in (
        "_compute_picker_layout",
        "_compute_text_input_layout",
        "get_effective_modal_scale",
        "_DIALOG_MODAL_REFERENCE_SIZE",
        "scale_px",
        "ellipsize_text",
        "wrap_text_limited",
        "get_render_safe_rect",
    ):
        assert needle in source, f"kaynak sözleşme kayboldu: {needle}"
    # Hit-test/çizim aynı rect'leri kullanır: unpack tek kaynaktan.
    assert re.search(r"lay = _compute_picker_layout\(", source)
    assert re.search(r"lay = _compute_text_input_layout\(", source)
