# -*- coding: utf-8 -*-
"""PieceWorkshopScreen çizim sözleşmesi (demo) — v2 uyarlaması.

v2'nin test_piece_workshop_containment.py twin'i; demo sürümü bilinçli
olarak daha yalın (lunar panel YOK, silme onay modalı YOK) — bu dosya
demo'nun KENDİ sözleşmesini kilitler ve bu dalgada kapatılan hata
ailesinin demo ayağını regresyona bağlar:

1. ÇÖKME (demo HEAD 33243c6'da worktree probe'uyla kanıtlandı):
   massive/double UI preset + dar pencere → dikey kart alanı tükeniyor,
   card_size 1x1'e küçülüyor ve _draw_block_styles_card negatif
   çözünürlüklü Surface üretip draw()'ı her karede çökertiyordu
   (640x480 + double → pygame.error 'Invalid resolution for Surface',
   ölçek 1.68). Artık kart _s(180) altında çizilmiyor; rect sıfırlanır
   (tıklama hedefi kapanır — handle_input falsy-rect kontrolü).
2. GRID/BUTON/PALET TAŞMASI: _s(30) tabanı bütçeleri ezip grid'i,
   KAYDET/SİL butonlarını ve palet sağ kenarını ekran dışına itiyordu
   (v2 ile aynı formüller — demo draw()'ı etkilenen bölgede birebir).
   Artık tabandan sonra SERT genişlik/dikey kapaklar var.
3. PALET SÜTUNU + MODE ETİKETLERİ: palet özel renk butonuna yer ayırıp
   kırpılır; mode paneli parça paneli bütçesine kısıtlı; sığmayan
   satırlar çizilmez ve hit-rect kaydı verilmez (görünmeyen öğe
   tıklanamaz).

Ölçüm sınırı (dürüst rapor): gerçek render görselliği manuel Windows
smoke'una aittir; dummy driver altında koşulmaz. Bilinçli sınırlar:
aşırı presetlerde palet/mode satır kırpması ve kart gizlemesi üretim
tercihi olarak kabul edildi (alternatif: ekran dışı/çöken çizim).

Kalıp: v2 test_avatar_editor_containment demo twin'i + kayıtlı-rect
assert dersi (üretim rect'ine assert, sabite değil).
"""
from __future__ import annotations

import os
import pathlib
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

if not pygame.get_init():
    pygame.init()
if not pygame.display.get_init():
    pygame.display.init()
pygame.display.set_mode((320, 240))
if not pygame.font.get_init():
    pygame.font.init()

ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import pytest

import retro_style as retro_style_module
import piece_workshop as workshop_module
from piece_workshop import PieceWorkshopScreen
from workshop_blocks import WORKSHOP_MODES
from ui_scaling import set_ui_scale_preset, get_ui_scale_preset

# Matris: 8 pencere boyutu x 6 preset = 48 hücre (draw ~2-17 ms).
SIZES = [
    (640, 480), (800, 480), (1024, 600), (1280, 720),
    (1280, 800), (1366, 768), (1600, 900), (1920, 1080),
]
PRESETS = ["compact", "normal", "large", "huge", "massive", "double"]

RECT_ATTRS = (
    "last_grid_rect", "save_button_rect", "delete_button_rect",
    "block_styles_card_rect", "palette_rect", "custom_color_button_rect",
    "last_pieces_panel_rect", "_back_rect",
)


@pytest.fixture(autouse=True)
def _restore_preset():
    previous = get_ui_scale_preset()
    try:
        yield
    finally:
        set_ui_scale_preset(previous)


class _SettingsManagerStub:
    """Ayar yok — parça listesi boş (yeni kullanıcı durumu)."""

    def get(self, key, default=None):
        return default

    def set(self, key, value):
        pass


def _mk_pieces():
    """Üretim gerçekçi parça kayıtları (cells + modes alanları dolu)."""
    shape = [[0, 0], [1, 0], [1, 1]]
    return [
        {
            "id": "p1", "name": "Probe Parça Bir", "shape": shape,
            "cells": [{"pos": p, "color": (0, 255, 255)} for p in shape],
            "modes": ["classic"],
        },
        {
            "id": "p2", "name": "İkinci Probe", "shape": shape,
            "cells": [{"pos": p, "color": (255, 165, 0)} for p in shape],
            "modes": [],
        },
    ]


def _fonts_stubbed() -> bool:
    """Ambient izolasyon: rect ölçüm testleri gerçek font metriği ister.

    Kanıtlanmış mayın (bu dosyanın geliştirilmesi sırasında bulundu):
    text_cache.patch_font() paylaşılan pygame.font.Font attribute'unu
    PatchedFont ile YAMALAR; patch'ten önce retro_style.font_cache'e
    girmiş düz Font nesneleri için isinstance(font, pygame.font.Font)
    kalıcı olarak False döner (sınıf kimliği değişti). Tip tabanlı
    dedektör bu sağlıklı üretim fontlarını yanlışlıkla 'stub' sanıp
    69 testi atlattı. Doğru dedektör İŞLEVSEL sondadır: get_font
    gerçek metrik üretmiyorsa (başka bir test dosyasının retro_style
    monkeypatch'i) ölçüm testleri geçersizdir.
    """
    try:
        probe = retro_style_module.retro_style.get_font(20)
    except Exception:
        return True
    size_fn = getattr(probe, "size", None)
    if not callable(size_fn):
        return True
    try:
        w, h = probe.size("Mj Ölçek Probe")
    except Exception:
        return True
    return not (isinstance(w, int) and isinstance(h, int) and w > 0 and h > 0)


def _skip_if_fonts_stubbed():
    if _fonts_stubbed():
        pytest.skip("retro_style font metriği kullanılamıyor — harness izolasyon sorunu")


def _make(size, scene="default"):
    """Gerçek kurucu (demo: user_manager parametresi yok — lunar yok)."""
    surface = pygame.display.set_mode(size)
    inst = PieceWorkshopScreen(surface, _SettingsManagerStub(), None)
    if scene == "pieces":
        inst.custom_pieces = _mk_pieces()
        inst.selected_piece_idx = 0
    elif scene == "editing":
        inst.custom_pieces = _mk_pieces()
        inst.selected_piece_idx = 0
        inst.editing_piece_id = "p1"
    elif scene == "grid_blocks":
        for x, y in [(2, 2), (3, 2), (2, 3), (3, 3), (4, 3)]:
            inst.grid[y][x] = {"color": (0, 255, 255)}
    elif scene == "message":
        inst.message = "Probe mesajı — uzun deneme metni 12345678"
        inst.message_timer = 5
    inst.draw()
    return inst


def _within(rect, size):
    w, h = size
    return (rect.left >= 0 and rect.top >= 0
            and rect.right <= w and rect.bottom <= h)


def _assert_layout_contract(inst, size):
    """Kayıtlı üretim rect'leriyle (sabit değil) düzen sözleşmesi."""
    for attr in RECT_ATTRS:
        rect = getattr(inst, attr)
        if rect.width == 0 or rect.height == 0:
            continue  # dal alınmadı / bilinçli sıfırlandı (kart)
        assert _within(rect, size), (attr, size, rect)

    grid = inst.last_grid_rect
    save, delete = inst.save_button_rect, inst.delete_button_rect

    # Grid kare ve kayıtla tutarlı.
    assert grid.width == grid.height == inst.last_cell_size * inst.GRID_SIZE
    assert inst.last_cell_size >= 1

    # Butonlar: grid altında, eşit boylu, yan yana, binmez, ekranda.
    assert save.top >= grid.bottom, (size, save, grid)
    assert save.height == delete.height and save.width == delete.width
    assert delete.left >= save.right, (size, save, delete)
    assert save.bottom <= size[1] and delete.bottom <= size[1], (size, save)

    # Palet grid'in sağında ve ekranda; özel renk butonu paletin altında.
    palette = inst.palette_rect
    assert palette.left >= grid.right, (size, palette, grid)
    custom = inst.custom_color_button_rect
    if custom.height > 0:
        assert custom.top >= palette.bottom, (size, custom, palette)
        assert custom.width == palette.width

    # Swatch'lar palet panelinin içinde (kırpma sözleşmesi).
    for rect, _idx in inst.palette_swatch_rects:
        assert rect.bottom <= palette.bottom, (size, rect, palette)
        assert _within(rect, size)

    # Kart: sıfır (bilinçli gizli) VEYA içerik tabanını karşılar.
    card = inst.block_styles_card_rect
    if card.width > 0:
        assert card.width >= 100 and card.height >= 100, (size, card)
        assert _within(card, size)

    # Parça kartları parça panelinin içinde.
    panel = inst.last_pieces_panel_rect
    if panel.height > 0:
        for rect, _pid in inst.piece_item_rects:
            assert panel.contains(rect), (size, rect, panel)
    # Mod etiketleri ekranda.
    for rect in inst.mode_tag_rects:
        assert _within(rect, size), (size, rect)


# ── Çizim containment matrisi ──────────────────────────────────────────────


@pytest.mark.parametrize("preset", PRESETS)
@pytest.mark.parametrize("size", SIZES)
def test_draw_containment_matrix(size, preset):
    _skip_if_fonts_stubbed()
    set_ui_scale_preset(preset)
    inst = _make(size)
    _assert_layout_contract(inst, size)


@pytest.mark.parametrize(
    "size", [(640, 480), (800, 480), (1024, 600), (1280, 720), (1366, 768)])
@pytest.mark.parametrize("preset", ["massive", "double"])
def test_draw_survives_extreme_presets(size, preset):
    """Baş bulgu regresyonu: eski kod bu hücrelerde her karede
    pygame.error('Invalid resolution for Surface') fırlatıyordu
    (demo HEAD 33243c6 worktree probe'uyla kanıtlandı)."""
    _skip_if_fonts_stubbed()
    set_ui_scale_preset(preset)
    inst = _make(size)  # istisna fırlamazsa zaten geçti
    _assert_layout_contract(inst, size)


def test_draw_4k_representative():
    _skip_if_fonts_stubbed()
    for preset in ("normal", "double"):
        set_ui_scale_preset(preset)
        inst = _make((3840, 2160))
        _assert_layout_contract(inst, (3840, 2160))


# ── Sahne derinliği (seçili hücrelerde) ────────────────────────────────────


@pytest.mark.parametrize("size,preset,expected_items", [
    ((1280, 720), "normal", 2),
    # (800,480)+double: liste alanı bir kart yüksekliğinden bile küçük —
    # üretim sözleşmesi kartı çizmez/kayda almaz (bilinçli davranış).
    ((800, 480), "double", 0),
    ((1920, 1080), "huge", 2),
])
def test_pieces_scene_containment(size, preset, expected_items):
    """Seçili parça → mode paneli + parça kartları dalı."""
    _skip_if_fonts_stubbed()
    set_ui_scale_preset(preset)
    inst = _make(size, scene="pieces")
    _assert_layout_contract(inst, size)
    assert 0 < len(inst.mode_tag_rects) <= len(WORKSHOP_MODES)
    assert len(inst.piece_item_rects) == expected_items


def test_mode_tag_clip_extreme():
    """800x480 + double: eski kod etiketleri ekran dışına (456-560)
    yazıyordu; artık satır kırpılır ve kayda girmez."""
    _skip_if_fonts_stubbed()
    set_ui_scale_preset("double")
    inst = _make((800, 480), scene="pieces")
    tags = inst.mode_tag_rects
    assert len(tags) < len(WORKSHOP_MODES), (
        "kırpma devreye girmeli — bu hücrede tüm satırlar sığmıyor")
    panel = inst.last_pieces_panel_rect
    for rect in tags:
        assert panel.contains(rect), (rect, panel)


def test_palette_clip_extreme():
    """800x480 + double: palet doğal boyu buton bütçesini aşar → satır
    kırpılır; özel renk butonu ekranda kalır."""
    _skip_if_fonts_stubbed()
    set_ui_scale_preset("double")
    inst = _make((800, 480))
    assert len(inst.palette_swatch_rects) < 12, (
        "kırpma devreye girmeli — 12 swatch bu hücrede sığmıyor")
    assert inst.custom_color_button_rect.bottom <= 480
    for rect, _idx in inst.palette_swatch_rects:
        assert rect.bottom <= inst.palette_rect.bottom


def test_swatch_full_grid_at_normal():
    _skip_if_fonts_stubbed()
    inst = _make((1920, 1080))
    assert len(inst.palette_swatch_rects) == 12  # kırpma yok


def test_grid_blocks_scene():
    """Blok dolu grid (jelly renderer yolu) düzeni değiştirmez."""
    _skip_if_fonts_stubbed()
    plain = _make((1366, 768))
    blocks = _make((1366, 768), scene="grid_blocks")
    assert blocks.last_grid_rect == plain.last_grid_rect
    assert blocks.last_cell_size == plain.last_cell_size
    _assert_layout_contract(blocks, (1366, 768))


def test_message_timer_decrements():
    _skip_if_fonts_stubbed()
    inst = _make((1366, 768), scene="message")
    assert inst.message_timer == 4  # 5 → draw bir azaltır


def test_scroll_clamped_each_frame():
    """draw() her karede _clamp_pieces_scroll çağırır; devasa scroll
    değeri tek karede sınıra iner."""
    _skip_if_fonts_stubbed()
    inst = _make((1920, 1080), scene="pieces")
    inst.pieces_scroll = 10 ** 6
    inst.draw()
    assert inst.pieces_scroll == inst._max_pieces_scroll()


# ── Kart sözleşmesi (çökme düzeltmesi) ─────────────────────────────────────


def test_card_zeroed_at_extreme():
    """640x480 + double: kart alanı tükenmiştir → rect sıfır (falsy) ve
    tıklama 'block_styles' döndürmez (ölü hit-zone yok)."""
    _skip_if_fonts_stubbed()
    set_ui_scale_preset("double")
    inst = _make((640, 480))
    assert inst.block_styles_card_rect == pygame.Rect(0, 0, 0, 0)
    assert not inst.block_styles_card_rect  # falsy: handle_input guard'ı

    event = pygame.event.Event(
        pygame.MOUSEBUTTONDOWN, button=1, pos=(300, 300))
    assert inst.handle_input(event) != "block_styles"


def test_card_drawn_at_normal():
    _skip_if_fonts_stubbed()
    inst = _make((1920, 1080))
    card = inst.block_styles_card_rect
    assert card.width >= 200 and card.height >= 200, card
    assert _within(card, (1920, 1080))


# ── Ölçek alanı sözleşmesi ────────────────────────────────────────────────


@pytest.mark.parametrize("size", SIZES)
def test_ui_scale_domain_window_mode(size):
    """normal preset: pencere oranlı ölçek [0.68, 1.24] bandında
    (referans 1366x768) — üretim formülünün dili/fontu bağımsız pini."""
    set_ui_scale_preset("normal")
    surface = pygame.display.set_mode(size)
    inst = PieceWorkshopScreen(surface, _SettingsManagerStub(), None)
    w, h = size
    expected = min(w / 1366.0, h / 768.0)
    expected = max(0.68, min(1.24, expected))
    assert inst._ui_scale() == pytest.approx(expected, abs=1e-6)


def test_ui_scale_preset_domain_at_small_window():
    """640x480'de preset alanı (probe ile doğrulanan gerçek değerler):
    compact 0.58 … double 1.68 (additive offset semantiği)."""
    surface = pygame.display.set_mode((640, 480))
    inst = PieceWorkshopScreen(surface, _SettingsManagerStub(), None)
    scales = {}
    for preset in PRESETS:
        set_ui_scale_preset(preset)
        scales[preset] = inst._ui_scale()
    assert scales["compact"] == pytest.approx(0.58, abs=1e-6)
    assert scales["normal"] == pytest.approx(0.68, abs=1e-6)
    assert scales["double"] == pytest.approx(1.68, abs=1e-6)
    values = [scales[p] for p in PRESETS]
    assert values == sorted(values), "preset alanı monotonik olmalı"


# ── Kaynak sözleşmeleri (formül pin'leri) ──────────────────────────────────


def _source() -> str:
    return pathlib.Path(workshop_module.__file__).read_text(encoding="utf-8")


def test_source_cell_caps():
    """Sert genişlik/dikey kapaklar — taban ezerse yeniden uygulanır."""
    src = _source()
    assert "max(1, (width - _s(300)) // self.GRID_SIZE)" in src
    assert "max(1, (height - grid_y - _s(76)) // self.GRID_SIZE)" in src


def test_source_card_crash_guard():
    src = _source()
    assert "if card_size >= _s(180):" in src
    assert "self.block_styles_card_rect = pygame.Rect(0, 0, 0, 0)" in src


def test_source_palette_budget_and_clip():
    src = _source()
    assert "max(_s(80), available_height - _s(86))" in src
    assert "if sy + swatch_size > palette_rect.bottom - _s(4):" in src


def test_source_mode_panel_budget_and_clip():
    src = _source()
    assert "max(1, panel_rect.bottom - header_rect.bottom - _s(18))" in src
    assert "if tag_rect.bottom > mode_panel_rect.bottom - _s(6):" in src


def test_source_no_lunar_panel():
    """Demo sürümü bilinçli olarak lunar'sızdır (v2-only özellik demo
    sınırı); bu dal geri taşınmamalı."""
    src = _source()
    assert "_use_lunar_system" not in src
    assert "lunar_panel_rect" not in src


def test_source_no_direct_font_creation():
    """Tüm fontlar retro_style.get_font önbelleğinden (kare-başı font
    üretimi yasağı — CLAUDE.md)."""
    src = _source()
    assert "pygame.font.Font(" not in src
    assert "retro_style.get_font(" in src
