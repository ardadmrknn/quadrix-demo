# -*- coding: utf-8 -*-
"""P1-9: Oynanış Ayarları ekranının ortak UI ölçeği + kart içi açıklama bütçesi.

Denetim raporu (Quadrix_Tum_Ekranlar_Olcekleme_Denetim_Raporu.md) P1-9:
- _layout_metrics sabit piksellerle (620/74/82) çalışıyordu → artık ortak UI
  ölçeğiyle (graphics_menu profili: get_projected_effective_scale,
  1366x768 referans, 0.72-1.24 clamp) taban × ölçek + okunabilirlik tabanları.
- Kart açıklaması genişlik bütçesi olmadan render ediliyordu → artık kart içi
  alt şeritte wrap_text_limited ile sınırlı; sığmayan tek satır ASCII '...'
  ile kısalır (emoji yasak - CLAUDE.md). Desc render'ı retro_style
  render_fit_text LRU'sundan (kare-başı Surface tahsisi yok).
- Başlık çağrısındaki ölü emoji argümanı kaldırıldı (draw_title zaten yok
  sayıyordu).

Kalıp: test_phase3_ui_scaling (SDL dummy + gerçek modül importu) ve
test_wide_arena_hud_scale_containment (matris + kaynak sözleşme pin'leri).
Ekran nesnesi olarak gerçek pygame.Surface (blit/get_size doğal); dummy
display sürücüsünde set_mode gerekmez (karekimliği testleri hariç).
"""
from __future__ import annotations

import os
import pathlib
import sys
import types

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import pygame

import pytest

import ui_scaling
import gameplay_settings as gameplay_settings_module
from ui_scaling import set_ui_scale_preset

if not pygame.font.get_init():
    pygame.font.init()


# ── Matris: rapor §9 test senaryoları (pencere modları × UI preset'leri) ────
SIZES = [(800, 480), (1024, 600), (1280, 720), (1366, 768), (1920, 1080), (3840, 2160)]
PRESETS = ["compact", "normal", "large", "huge", "massive", "double"]

EMOJI_RANGES = (
    (0x1F000, 0x1FAFF),   # emoji blokları
    (0x2600, 0x27BF),     # dingbats / misc symbols
    (0xFE0F, 0xFE0F),     # variation selector
)


class _DummyFx:
    """get_shared_falling_blocks_layer stub'u (test_phase3 idyomu)."""

    def update(self, screen):
        pass

    def draw(self, screen):
        pass


class _DummySettings:
    def get(self, key, default=None):
        return default

    def set(self, key, value):
        pass

    def save_settings(self):
        pass


def _make_screen(width: int, height: int) -> pygame.Surface:
    """Gerçek Surface 'ekran' (blit/get_size/get_height doğal destekli)."""
    return pygame.Surface((width, height), pygame.SRCALPHA)


def _make_menu(width: int, height: int, monkeypatch) -> gameplay_settings_module.GameplaySettingsMenu:
    monkeypatch.setattr(
        gameplay_settings_module,
        'get_shared_falling_blocks_layer',
        lambda *args, **kwargs: _DummyFx(),
    )
    return gameplay_settings_module.GameplaySettingsMenu(_make_screen(width, height), _DummySettings())


def _has_no_emoji(text: str) -> bool:
    return not any(lo <= ord(ch) <= hi for ch in text for lo, hi in EMOJI_RANGES)


def _source() -> str:
    path = pathlib.Path(gameplay_settings_module.__file__)
    return path.read_text(encoding='utf-8')


# ── Ölçek bağlama (komşu ekranla aynı profil) ────────────────────────────────

def test_ui_scale_binds_graphics_menu_profile(monkeypatch):
    """Ölçek kaynağı: graphics_menu ile aynı get_projected_effective_scale profili."""
    menu = _make_menu(1920, 1080, monkeypatch)
    expected = ui_scaling.get_projected_effective_scale(
        menu.screen, min_scale=0.72, max_scale=1.24, reference_size=(1366.0, 768.0),
    )
    assert menu._ui_scale() == pytest.approx(expected)


def test_baseline_1366_768_metrics_are_pixel_identical(monkeypatch):
    """1366x768 + normal preset → taban değerler birebir (görünüm değişmez)."""
    set_ui_scale_preset('normal')
    try:
        menu = _make_menu(1366, 768, monkeypatch)
        card_w, card_h, spacing = menu._layout_metrics()
        assert (card_w, card_h, spacing) == (620, 74, 82)
        assert menu._font_small_size == 18
    finally:
        set_ui_scale_preset('normal')


@pytest.mark.parametrize("preset", PRESETS)
@pytest.mark.parametrize("size", SIZES, ids=[f"{w}x{h}" for w, h in SIZES])
def test_metrics_respect_floors_and_screen_budget(size, preset, monkeypatch):
    """Her boyut/preset bileşiminde tabanlar ve ekran bütçesi korunur."""
    width, height = size
    set_ui_scale_preset(preset)
    try:
        menu = _make_menu(width, height, monkeypatch)
        card_w, card_h, spacing = menu._layout_metrics()

        # Okunabilirlik tabanları (graphics_menu ile aynı değerler).
        assert card_w >= 420
        assert card_h >= 56
        assert spacing >= 62
        # Kart genişliği ekranı aşamaz; kenar payı asgari 60px kalır.
        assert card_w <= width - 60
        assert card_w < width
        # Satır aralığı kart yüksekliğini kapsar (desc şeridi için alan).
        assert spacing >= card_h
        # Desc font tabanı.
        assert menu._font_small_size >= 11
    finally:
        set_ui_scale_preset('normal')


@pytest.mark.parametrize("size", [(1366, 768), (1920, 1080), (3840, 2160)])
def test_metrics_grow_with_ui_scale_preset(size, monkeypatch):
    """Preset büyüdükçe metrikler küçülmez (monoton; tabanlar eşitleyebilir)."""
    width, height = size
    heights, spacings, fonts = [], [], []
    try:
        for preset in PRESETS:
            set_ui_scale_preset(preset)
            menu = _make_menu(width, height, monkeypatch)
            card_w, card_h, spacing = menu._layout_metrics()
            heights.append(card_h)
            spacings.append(spacing)
            fonts.append(menu._font_small_size)
    finally:
        set_ui_scale_preset('normal')

    assert heights == sorted(heights), f"card_h preset ile küçüldü: {heights}"
    assert spacings == sorted(spacings), f"spacing preset ile küçüldü: {spacings}"
    assert fonts == sorted(fonts), f"desc font preset ile küçüldü: {fonts}"


def test_fonts_refresh_when_scale_changes(monkeypatch):
    """Pencere boyutu/preset değişince fontlar ölçeğe göre tazelenir."""
    menu = _make_menu(1366, 768, monkeypatch)
    small_before = menu._font_small_size

    menu.screen = _make_screen(3840, 2160)
    menu._refresh_fonts_if_needed()
    assert menu._font_small_size > small_before

    # Ölçek değişmedikçe ikinci çağrı fontları değiştirmez (LRU kimliği).
    font_obj = menu.font_small
    menu._refresh_fonts_if_needed()
    assert menu.font_small is font_obj


# ── Kart içi açıklama bütçesi (P1-9 çekirdek sözleşme) ──────────────────────

@pytest.mark.parametrize("preset", PRESETS)
@pytest.mark.parametrize("size", SIZES, ids=[f"{w}x{h}" for w, h in SIZES])
def test_selected_desc_fits_card_inner_width(size, preset, monkeypatch):
    """Seçili ayarın açıklaması tek satırda kart iç genişliğine sığar."""
    width, height = size
    set_ui_scale_preset(preset)
    try:
        menu = _make_menu(width, height, monkeypatch)
        card_w, card_h, _ = menu._layout_metrics()
        rect = pygame.Rect(width // 2 - card_w // 2, 200, card_w, card_h)

        for selected in range(len(menu.settings)):
            menu.selected = selected
            lines = menu._selected_desc_lines(rect)
            assert 0 < len(lines) <= 1, "desc satır bütçesi 1'den fazlaya çıktı"
            pad_x = menu._s(20, minimum=14)
            line_w = menu.font_small.size(lines[0])[0]
            assert line_w <= max(8, rect.width - 2 * pad_x), (
                f"desc kart iç genişliğini aştı: {line_w}px > {rect.width - 2 * pad_x}px "
                f"(size={size}, preset={preset})"
            )
            assert _has_no_emoji(lines[0]), "desc satırında emoji-range karakter var"
    finally:
        set_ui_scale_preset('normal')


@pytest.mark.parametrize(
    "size",
    [(800, 480), (1366, 768), (1920, 1080), (3840, 2160)],
    ids=["800x480", "1366x768", "1920x1080", "3840x2160"],
)
def test_drawn_desc_rect_stays_inside_card(size, monkeypatch):
    """Çizilen desc şeridi kartın içinde kalır; başlık METNİYLE çakışmaz.

    Bant-aritmetiği font metrik dolgusu yüzünden yanıltıcıdır (label bandı
    35px ama glif mürekkebi ~26px): rect'ler 1-4px örtüşse bile mürekkep
    düzeyinde çakışma olmamalı. Sözleşme piksel maskesiyle kanıtlanır —
    draw_setting_row'un başlığı kendi konumunda, desc kendi şeridinde
    render edilip maskeler karşılaştırılır (ink çakışması = None).
    """
    width, height = size
    menu = _make_menu(width, height, monkeypatch)
    card_w, card_h, _ = menu._layout_metrics()
    rect = pygame.Rect(width // 2 - card_w // 2, 200, card_w, card_h)
    menu.selected = 0

    desc_rect = menu._draw_selected_desc(rect)
    assert desc_rect is not None

    line_h = menu.font_small.get_height()
    pad_x = menu._s(20, minimum=14)
    assert desc_rect.height == line_h
    assert desc_rect.left >= rect.x + pad_x
    assert desc_rect.right <= rect.right - pad_x
    assert desc_rect.top >= rect.y
    assert desc_rect.bottom <= rect.bottom

    # Mürekkep düzeyi: başlık glifleri ile desc glifleri üst üste binmez.
    # draw_setting_row başlığı 26 taban fontla dikey ortalanır (en kötü durum:
    # küçülmemiş, en yüksek font) — x=14 ofseti aynı fonksiyonun sabitidir.
    label_font = gameplay_settings_module.retro_style.get_font(26, bold=True)
    label_surf = label_font.render(menu.settings[0]['label'], True, (255, 255, 255))
    label_canvas = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    label_canvas.blit(
        label_surf, (14, (rect.height - label_surf.get_height()) // 2),
    )

    desc_line = menu._selected_desc_lines(rect)[0]
    desc_surf = menu.font_small.render(desc_line, True, (180, 190, 210))
    desc_canvas = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    desc_canvas.blit(
        desc_surf, (desc_rect.x - rect.x, desc_rect.y - rect.y),
    )

    label_mask = pygame.mask.from_surface(label_canvas)
    desc_mask = pygame.mask.from_surface(desc_canvas)
    overlap = label_mask.overlap(desc_mask, (0, 0))
    assert overlap is None, (
        f"desc mürekkebi başlık glifleriyle çakıştı (size={size}, konum={overlap})"
    )


def test_draw_selected_desc_renders_lru_cached_surface(monkeypatch):
    """Desc render'ı render_fit_text LRU'sundan: aynı metin → aynı Surface."""
    menu = _make_menu(1366, 768, monkeypatch)
    card_w, card_h, _ = menu._layout_metrics()
    rect = pygame.Rect(0, 200, card_w, card_h)
    menu.selected = 0

    lines = menu._selected_desc_lines(rect)
    surf_a = gameplay_settings_module.retro_style.render_fit_text(
        lines[0], (180, 190, 210), None, menu._font_small_size, bold=False,
    )
    surf_b = gameplay_settings_module.retro_style.render_fit_text(
        lines[0], (180, 190, 210), None, menu._font_small_size, bold=False,
    )
    assert surf_a is surf_b


def test_selected_desc_empty_when_back_row_selected(monkeypatch):
    """'Geri' satırı seçiliyken desc üretilmez (None/boş)."""
    menu = _make_menu(1366, 768, monkeypatch)
    menu.selected = len(menu.settings)
    card_w, card_h, _ = menu._layout_metrics()
    rect = pygame.Rect(0, 200, card_w, card_h)

    assert menu._selected_desc_lines(rect) == []
    assert menu._draw_selected_desc(rect) is None


# ── Kaydırma ölçeği ──────────────────────────────────────────────────────────

def test_mousewheel_step_scales(monkeypatch):
    """Tekerlek adımı ortak ölçekle (taban 30 → minimum 18)."""
    width, height = 800, 480
    menu = _make_menu(width, height, monkeypatch)
    expected_step = menu._s(30, minimum=18)

    event = types.SimpleNamespace(
        type=gameplay_settings_module.pygame.MOUSEWHEEL, y=-1,
    )
    menu.handle_input(event)

    assert menu.scroll_offset == expected_step


# ── Kaynak sözleşmeleri (AST-pin idyomu) ─────────────────────────────────────

def test_source_has_no_emoji_and_no_emoji_argument():
    """CLAUDE.md emoji yasağı: dosyada emoji-range karakter / emoji= argümanı yok."""
    source = _source()
    for i, line in enumerate(source.splitlines(), start=1):
        assert _has_no_emoji(line), f"emoji-range karakter (satır {i}): {ascii(line)[:80]}"
    assert "emoji=" not in source, "başlık çağrısında ölü emoji argümanı hâlâ duruyor"


def test_source_pins_scale_and_wrap_contracts():
    """Ölçek profili, wrap/fit ve LRU render sözleşmeleri kaynağa sabitlenir."""
    source = _source()
    # Ortak ölçek profili (graphics_menu ile aynı sabitler).
    assert "get_projected_effective_scale" in source
    assert "reference_size=(1366.0, 768.0)" in source
    # Desc: wrap + ellipsis yardımcısı ve LRU render.
    assert "wrap_text_limited(" in source
    assert "render_fit_text(" in source
    assert "self.font_small.render(" not in source, "kare-başı ham font render'ı geri geldi"
    # Kaydırma adımı ölçekli.
    assert "self._s(30, minimum=18)" in source
