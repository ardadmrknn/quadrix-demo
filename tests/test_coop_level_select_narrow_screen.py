# -*- coding: utf-8 -*-
"""P0-3/P1-7: Co-op level select dar ekran tab/grid containment.

Rapor: Quadrix_Tum_Ekranlar_Olcekleme_Denetim_Raporu.md
- P0-3: Co-op level select tab/grid toplam genişliği dar ekranlarda ekran
  bütçesine clamp edilmeli (ekran dışı input rect = P0).
- P1-7: kolon sayısı ekran genişliğine göre 5→1 düşer; dünya adı tab iç
  bütçesine fit edilir (font küçültme → ASCII ellipsis); hit rect görsel
  rect ile aynı kaynaktan türetilir.

Kalıp: test_wide_arena_hud_scale_containment (dummy sürücü + gerçek modül
importu). Gerçek CoopLevelSelect instance'ı gerçek fontlarla çizilir;
ölçümler gerçek font metrikleriyle yapılır. draw() sonundaki
pygame.display.flip monkeypatch ile etkisizleştirilir (dummy sürücüde
set_mode açmaya gerek kalmaz).

Ölçüm sınırı (dürüst rapor): dummy driver gerçek görsel sunumu kanıtlamaz;
bu dosya rect/containment/hit-parite sözleşmesini kilitler. Görsel
doğrulama rapor §11'deki manuel Windows smoke'a aittir.
"""
from __future__ import annotations

import os
import pathlib
import re
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import pytest

from ui_scaling import get_ui_scale_preset, set_ui_scale_preset
from ui_text_layout import ellipsize_text
from retro_style import retro_style
from campaign import coop_level_select as coop_level_select_module
from campaign.coop_level_select import CoopLevelSelect, _WORLD_NAMES

if not pygame.font.get_init():
    pygame.font.init()

# FAZ A6 modül-kimliği temizliği (test_coop.py / G dosyası düşürme kalıbı):
# yukarıdaki import zinciri campaign/__init__.py'yi çalıştırır ve tüm
# campaign alt modüllerini BU dosyanın pygame nesline bağlar; conftest her
# koleksiyon sınırında pygame ailesini sys.modules'tan düşürür. Burada
# bırakılan eski binding'li campaign girdileri sonraki toplanan dosyada
# modül-kimliği bölünmesi yaratır. Bu dosyanın testleri yukarıdaki doğrudan
# referanslarla (coop_level_select_module, CoopLevelSelect) çalıştığı için
# aileyi düşürmek etkilemez; sonraki dosya kendi pygame'iyle temiz yükler.
for _mod_name in [n for n in list(sys.modules)
                  if n == "campaign" or n.startswith("campaign.")
                  or n == "src.campaign" or n.startswith("src.campaign.")]:
    sys.modules.pop(_mod_name, None)


SCREEN_MATRIX = [
    (640, 360),
    (800, 480),
    (1024, 600),
    (1280, 720),
    (1920, 1080),
    (3840, 2160),
]
PRESET_MATRIX = ["normal", "large", "massive", "double"]


@pytest.fixture(autouse=True)
def _no_display_flip(monkeypatch):
    """draw() sonundaki flip dummy sürücüde set_mode gerektirmesin."""
    monkeypatch.setattr(pygame.display, "flip", lambda: None)


@pytest.fixture(autouse=True)
def _restore_preset():
    previous = get_ui_scale_preset()
    yield
    set_ui_scale_preset(previous)


def _make_select(size, preset):
    set_ui_scale_preset(preset)
    surface = pygame.Surface(size)
    return CoopLevelSelect(surface), surface


def _s_factory(select):
    scale = select._ui_scale()
    return lambda v, minimum=1: max(minimum, int(v * scale))


# ── P0-3: containment — rect'ler ekran bütçesi içinde ve birbirinden ayrık ──


@pytest.mark.parametrize("preset", PRESET_MATRIX)
@pytest.mark.parametrize("size", SCREEN_MATRIX)
def test_tabs_and_grid_stay_within_screen_budget(size, preset):
    select, _surface = _make_select(size, preset)
    select.draw()

    w, h = size
    s = _s_factory(select)
    margin = s(16)

    # Dünya tabları: üretilmeli, yatay bütçede kalmalı, ekranda kalmalı.
    assert select._world_tab_rects, "dünya tab rect'leri üretilmeli"
    tab_rects = list(select._world_tab_rects.values())
    for rect in tab_rects:
        assert rect.width >= 1 and rect.height >= 1
        assert rect.left >= margin, (
            f"tab sol kenar bütçe dışı: {rect} (margin={margin})"
        )
        assert rect.right <= w - margin, (
            f"tab sağ kenar bütçe dışı: {rect} (w-margin={w - margin})"
        )
        assert 0 <= rect.top and rect.bottom <= h

    # Level kartları: üretilmeli, yatay bütçede ve dikey bütçede kalmalı.
    assert select._level_rects, "level kart rect'leri üretilmeli"
    for rect in select._level_rects.values():
        assert rect.width >= 1 and rect.height >= 1
        assert rect.left >= margin, f"kart sol kenar bütçe dışı: {rect}"
        assert rect.right <= w - margin, f"kart sağ kenar bütçe dışı: {rect}"
        assert rect.top >= 0, f"kart üst kenar ekran dışı: {rect}"
        assert rect.bottom <= h - margin, (
            f"kart alt kenar dikey bütçe dışı: {rect} (h-margin={h - margin})"
        )

    # Rect'ler birbirinden ayrık (çakışan tab/kart yok).
    all_rects = tab_rects + list(select._level_rects.values())
    for i, a in enumerate(all_rects):
        for b in all_rects[i + 1:]:
            assert not a.colliderect(b), f"çakışan rect'ler: {a} vs {b}"


def test_column_count_drops_on_narrow_screens():
    """640x360 + %200 preset: sabit 5 kolon 1041 px ister, bütçe ~586 px →
    kolon sayısı 5'in altına inmelidir (P1-7 kolon merdiveni)."""
    select, _surface = _make_select((640, 360), "double")
    select.draw()
    assert 1 <= select._grid_cols <= 4


def test_baseline_1366x768_normal_keeps_five_column_layout():
    """Taban ölçekte görsel düzen birebir korunur: 5 kolon, s(110)/s(88)."""
    select, _surface = _make_select((1366, 768), "normal")
    select.draw()
    s = _s_factory(select)

    assert select._grid_cols == 5
    assert select._level_rects[1].width == s(110)
    assert select._level_rects[1].height == s(88)


# ── Hit rect == görsel rect (davranışsal parite) ────────────────────────────


@pytest.mark.parametrize("preset", ["normal", "double"])
@pytest.mark.parametrize("size", [(800, 480), (1280, 720)])
def test_hit_rects_match_visual_rects(size, preset):
    """Kayıtlı görsel rect'in merkezi tıklanınca o rect'in eylemi döner —
    hit test çizimle AYNI rect kaynağını kullanıyor demektir."""
    select, _surface = _make_select(size, preset)
    select.draw()

    # Level kartı (level 1 her iki modda da açık).
    level_rect = select._level_rects[1]
    click = pygame.event.Event(
        pygame.MOUSEBUTTONDOWN, pos=level_rect.center, button=1,
    )
    assert select.handle_input(click) == 'play_1'

    # Dünya tabı: v2/demo-tam modda dünya değişir; demo kilit modunda
    # upgrade prompt açılır (her ikisi de tab rect'inin tüketildiğini
    # kanıtlar).
    other_world = 2 if select.current_world == 1 else 1
    tab_rect = select._world_tab_rects[other_world]
    click = pygame.event.Event(
        pygame.MOUSEBUTTONDOWN, pos=tab_rect.center, button=1,
    )
    assert select.handle_input(click) is None
    prompt = getattr(select, '_demo_upgrade_prompt', None)
    assert select.current_world == other_world or (
        prompt is not None and prompt.is_active()
    )

    # Geri butonu.
    assert select._back_rect is not None
    click = pygame.event.Event(
        pygame.MOUSEBUTTONDOWN, pos=select._back_rect.center, button=1,
    )
    assert select.handle_input(click) == 'back'


def test_vertical_navigation_step_follows_column_count():
    """Dikey navigasyon adımı aktif kolon sayısını izler (P1-7).
    640x360 + %200'de kolon sayısı 2'ye düştüğünde K_DOWN seçimi tam bir
    satır (2 kart) kaydırmalı, eski sabit 5'i değil. Navigation yalnızca
    açık levellere taşabildiği için tüm levelleri açık progresle kur."""
    select, _surface = _make_select((640, 360), "double")
    select.progress = {
        'completed_levels': {
            str(i): {'completed': True, 'stars': 3} for i in range(1, 11)
        },
        'highest_level': 10,
        'total_stars': 30,
    }
    select.draw()
    cols = select._grid_cols

    start = select.selected_level
    down = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_DOWN)
    select.handle_input(down)
    moved = select.selected_level - start
    assert moved == cols, (
        f"K_DOWN {cols} kart kaydırmalı, {moved} kaydırdı "
        f"(seçim: {start} → {select.selected_level})"
    )


# ── P1-7: dünya adı fitting zinciri garanti eder (gerçek fontlar) ───────────


@pytest.mark.parametrize("preset", PRESET_MATRIX)
@pytest.mark.parametrize("size", SCREEN_MATRIX)
@pytest.mark.parametrize("lang", ["tr", "en", "de", "ru"])
def test_world_name_fitting_chain_respects_tab_inner_budget(size, preset, lang):
    """Üretim fitting zinciri (get_fitting_font → ellipsize_text) her dünya
    adı için tab iç bütçesini garantiler; kesme işareti ASCII '...'."""
    select, _surface = _make_select(size, preset)
    select.draw()
    s = _s_factory(select)

    for wi, rect in select._world_tab_rects.items():
        inner = max(1, rect.width - 2 * s(8))
        name = _WORLD_NAMES.get(wi, {}).get(lang)
        if not name:
            continue
        font = retro_style.get_fitting_font(
            name, s(18), inner, bold=True, min_size=s(12),
        )
        text = ellipsize_text(name, font, inner)
        assert font.size(text)[0] <= inner, (
            f"dünya adı [{lang}] tab iç bütçesini aşıyor: "
            f"{font.size(text)[0]} > {inner} ({size}, {preset})"
        )
        if text != name:
            assert text.endswith('...'), "kesme işareti ASCII '...' olmalı"


# ── Kaynak sözleşme pin'leri (AST-pin idiomu) ───────────────────────────────


def _source() -> str:
    return pathlib.Path(coop_level_select_module.__file__).read_text(
        encoding='utf-8'
    )


def test_source_pins_tab_width_clamp():
    source = _source()
    assert re.search(
        r"tab_w = min\(s\(200\), max\(1, \(avail_w - total_tab_gap\) // world_count\)\)",
        source,
    ), "tab genişliği ekran payı clamp'i kayboldu"


def test_source_pins_column_ladder_and_vertical_budget():
    source = _source()
    assert re.search(r"for cand_cols in \(5, 4, 3, 2, 1\):", source), (
        "kolon merdiveni (5→1) kayboldu"
    )
    assert re.search(
        r"cand_cols \* btn_w \+ \(cand_cols - 1\) \* gap_x <= avail_w", source,
    ), "kolon seçim bütçe karşılaştırması kayboldu"
    assert re.search(r"avail_h = max\(1, h - s\(16\) - top\)", source), (
        "dikey bütçe sözleşmesi kayboldu"
    )


def test_source_pins_world_name_fitting_chain():
    source = _source()
    assert re.search(
        r"get_fitting_font\(\s*wname, s\(18\), tab_inner_w", source,
    ), "dünya adı font fitting çağrısı kayboldu"
    assert "ellipsize_text(wname, name_font, tab_inner_w)" in source, (
        "dünya adı ellipsis son çaresi kayboldu"
    )


def test_source_pins_navigation_step_follows_columns():
    source = _source()
    assert re.search(
        r"grid_cols = max\(1, int\(getattr\(self, '_grid_cols', 5\)\)\)", source,
    ), "dikey navigasyon adımının kolon takibi kayboldu"
