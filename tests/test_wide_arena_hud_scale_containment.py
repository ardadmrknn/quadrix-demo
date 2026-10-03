# -*- coding: utf-8 -*-
"""DUZ-014: Wide Arena sağ HUD paneli %175/%200 preset içerik bütçesi.

Kılavuz: Quadrix_UI_4K_WideArena_Pencere_Modu_Duzeltme_Kilavuzu.md
(kök nedenler C1-C3):
- C1: HUD preset ölçeği font/padding'i ~2.06x büyütürken panel GENİŞLİĞİ
  preset'ten bağımsız 1x kalır → etiket (sol) ile değer (sağ) aritmetik
  olarak ÇAKIŞIR. Düzeltme: stat satırları ölç-önce (measure-first)
  planlanır; sığmayan satır önce kuantalı oransal küçültme, sonra
  kontrollü dikey yerleşim, en son çare ellipsis.
- C2: eski draw_stat_row genişlik karşılaştırması yapmıyordu → artık
  plan üretim aşamasında ölçüm var (bu dosya ölçüm düzeyinde kanıtlar).
- C3: mini_cell kutu ölçüsüne değil PARÇA matrisine göre bütçelenir →
  kaynak sözleşme testleriyle sabitlenir.

Ölçüm sınırı (dürüst rapor): gerçek 4K görsel doğrulama kılavuz §7'deki
manuel Windows smoke'a aittir — dummy driver altında koşulamaz. Bu dosya
plan sözleşmesini (değişmezler) ve kaynak sözleşmesini kilitler.

Kalıp: test_a9_perf_gate (SRC yol hazırlığı + dummy sürücüler + gerçek
modül importu; Game.__new__ bare-instance idyomu).
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

import game as game_module
from game import Game

if not pygame.font.get_init():
    pygame.font.init()


# ── Kılavuzdan ölçülen gerçek senaryolar ────────────────────────────────────
# %175 preset, 4K (3840x2160): hud_px_scale ~4.13, panel content_w ~192 px.
# %175 preset, 1080p: panel content_w ~192, hud_scale ~1.0 (panel ölçeği
# fontu büyütür, genişlik büyümez → çakışma burada görünür).
HUD_175 = 2.065          # 1.18 (base clamp üst sınırı) × 1.75 (preset)
CONTENT_W_4K = 192       # kılavuzdaki ölçülen Wide Arena panel genişliği
CONTENT_W_1080P = 200


def _make_game() -> Game:
    """Bare Game: _fit_hud_stat_row yalnız statik yardımcıları kullanır."""
    return Game.__new__(Game)


@pytest.mark.parametrize(
    "content_w,hud",
    [
        (CONTENT_W_4K, HUD_175),          # C1: 4K %175 çakışma senaryosu
        (CONTENT_W_1080P, HUD_175),       # 1080p %175
        (CONTENT_W_4K, 2.36),             # %200 preset (1.18 × 2.0)
        (CONTENT_W_4K, 1.0),              # normal
        (CONTENT_W_4K, 0.72),             # compact taban
        (240, HUD_175),
        (160, HUD_175),                   # dar panel
        (96, 1.0),
        (64, 1.0),                        # aşırı dar
    ],
)
@pytest.mark.parametrize(
    "label,value",
    [
        ("SKOR", "1.234.567"),
        ("SCORE", "12.345.678"),
        ("SATIR", "1234"),
        ("SEVİYE", "99"),
    ],
)
def test_stat_row_never_overlaps_label_and_value(content_w, hud, label, value):
    """Çekirdek değişmezi: yatay satırda etiket+boşluk+değer daima sığar.

    Eski kod (C2) ölçmediği için %175'te etiket soldan, değer sağdan
    çizilip ORTADA üst üste biniyordu. Yeni plan ya sığan bir yatay satır
    üretir (l_w + row_gap + v_w <= avail_w) ya da vertical=True olur —
    ikisi arası (yarı çakışan yatay satır) asla üretilmez.
    """
    game = _make_game()
    plan = game._fit_hud_stat_row(label, value, content_w, hud)

    assert plan['avail_w'] >= 24
    if not plan['vertical']:
        total = plan['label_w'] + plan['row_gap'] + plan['value_w']
        assert total <= plan['avail_w'], (
            f"yatay satır taşması: label={plan['label_w']} gap={plan['row_gap']} "
            f"value={plan['value_w']} avail={plan['avail_w']} (hud={hud}, w={content_w})"
        )
    else:
        # Dikey yerleşimde her iki blok da satır genişliğine sığmalı.
        assert plan['label_w'] <= plan['avail_w']
        assert plan['value_w'] <= plan['avail_w']


def test_stat_row_vertical_fallback_when_floor_fonts_do_not_fit():
    """Taban fontlarda bile sığmayan satır kontrollü dikey yerleşime düşer."""
    game = _make_game()
    plan = game._fit_hud_stat_row("SEVİYE", "999.999", 60, 2.065)

    assert plan['vertical'] is True
    assert plan['value_w'] <= plan['avail_w']
    assert plan['label_w'] <= plan['avail_w']
    # Dikey satır yüksekliği iki bloğu kapsar.
    assert plan['row_h'] >= plan['label_h'] + max(2, int(4 * 2.065)) + plan['value_h'] - 1


def test_stat_row_ellipsis_is_last_resort_only():
    """Ellipsis yalnız dikey yerleşimde DEĞER taşarsa uygulanır.

    Değer '...' ile kısaltılmışsa hâlâ avail_w içinde olmalı; kısaltılmamışsa
    da aynı değişmez geçerli.
    """
    game = _make_game()
    original = "123.456.789"
    plan = game._fit_hud_stat_row("SKOR", original, 48, 2.065)

    assert plan['value_w'] <= plan['avail_w']
    if plan['value_text'] != original:
        assert plan['value_text'].endswith("...")
        assert len(plan['value_text']) < len(original)
        # ASCII '...' (emoji yok — CLAUDE.md).
        assert all(ord(ch) < 128 for ch in plan['value_text'])


def test_stat_row_shrink_ladder_respects_font_floors():
    """Oransal küçültme tabanların (11/15) altına inmez → okunabilirlik."""
    game = _make_game()
    plan = game._fit_hud_stat_row("SKOR", "1.234.567", 110, HUD_175)

    # get_height() em-size'tan küçük olamaz; tabanlar alt sınır görevi görür.
    assert plan['label_h'] >= 11
    assert plan['value_h'] >= 15
    assert plan['label_font'] is not None and plan['value_font'] is not None


def test_stat_row_plan_is_cache_friendly_and_allocation_free():
    """Plan aşaması Surface ÜRETMEZ; tekrar çağrı aynı font NESNESİNİ verir.

    Kare-başı tahsis yasağı (CLAUDE.md): ölçümler measure_text_width LRU'dan
    okunur, fontlar retro_style font_cache'ten; küçültme oranları 0.05
    adımlarla kuantalandığından font boyutu seti sınırlı kalır.
    """
    game = _make_game()
    plan_a = game._fit_hud_stat_row("SKOR", "1.234.567", CONTENT_W_4K, HUD_175)
    plan_b = game._fit_hud_stat_row("SKOR", "1.234.567", CONTENT_W_4K, HUD_175)

    for value in plan_a.values():
        assert not isinstance(value, pygame.Surface), "plan aşaması Surface üretmemeli"
    # Aynı girdi → aynı font nesneleri (font_cache kimliği).
    assert plan_a['label_font'] is plan_b['label_font']
    assert plan_a['value_font'] is plan_b['value_font']


def test_stat_row_handles_empty_and_missing_parts():
    """Boş etiket/değer uç durumları planı bozmaz (vertical asla zorlanmaz)."""
    game = _make_game()
    plan = game._fit_hud_stat_row("", "123", CONTENT_W_4K, 1.0)
    assert plan['label_text'] == ''
    assert plan['label_w'] == 0
    assert plan['vertical'] is False

    plan = game._fit_hud_stat_row("SKOR", None, CONTENT_W_4K, 1.0)
    assert plan['value_text'] == ''
    assert plan['value_w'] == 0
    assert plan['vertical'] is False


def test_stat_row_invalid_hud_falls_back_to_unit():
    game = _make_game()
    plan = game._fit_hud_stat_row("SKOR", "123", CONTENT_W_4K, 0)
    assert plan['row_gap'] == max(6, int(12 * 1.0))


# ── Kaynak sözleşmeleri (stats bloğu + mini_cell bütçeleri) ─────────────────
# Repodaki AST-pin idyomu (test_survival_victory_minutes): inline mantık
# birim çağrılamadığından kaynak sözleşmesiyle sabitlenir.


def _game_source() -> str:
    return pathlib.Path(game_module.__file__).read_text(encoding='utf-8')


def test_stats_block_uses_measure_first_ladder_with_mandatory_rows():
    source = _game_source()
    # Ölç-önce ladder: 5 basamak, üniform küçültme.
    assert re.search(r"for shrink in \(1\.0, 0\.88, 0\.76, 0\.64, 0\.52\):", source)
    # Zorunlu satır sayısı: opsiyonel (combo/tetris) satır EN SON düşürülür.
    assert re.search(r"mandatory_row_count = 3", source)
    drop_optional = re.search(
        r"stat_plans = stat_plans\[:mandatory_row_count\]", source)
    assert drop_optional, "opsiyonel satır düşürme sözleşmesi kayboldu"


def test_stats_block_draw_uses_plan_vertical_layout():
    source = _game_source()
    draw_fn = source[source.index("def draw_stat_row"):source.index("for (_label, _value, row_color), plan in zip")]
    assert "plan['vertical']" in draw_fn
    assert "topright" in draw_fn
    # Etiket cache'li (render_text), değer ham render (mevcut davranış korunur).
    assert "render_text(plan['label_font']" in draw_fn


def test_mini_cell_budgets_are_piece_matrix_clamped():
    """C3: mini_cell parça bütçesine (kutu ölçüsüne değil) clamp'lenir."""
    # Kaynak blokları çok satırlı biçimli → whitespace-normalize ederek eşle.
    source = re.sub(r"\s+", " ", _game_source())
    next_match = re.search(
        r"mini_cell = max\( 4, min\( int\(13 \* hud_scale\), "
        r"piece_budget // max\(1, pw\), piece_budget // max\(1, ph\), \), \)",
        source,
    )
    assert next_match, "NEXT mini_cell parça-bütçe clamp'i kayboldu"
    hold_match = re.search(
        r"mini_cell = max\( 5, min\( int\(14 \* hud_scale\), "
        r"\(hold_box_rect\.width - 2 \* piece_inset\) // max\(1, pw\), "
        r"\(hold_box_rect\.height - 2 \* piece_inset\) // max\(1, ph\), \), \)",
        source,
    )
    assert hold_match, "HOLD mini_cell parça-bütçe clamp'i kayboldu"
    assert "piece_budget = box_size - 2 * piece_inset" in source


def test_fit_hud_stat_row_measure_only_no_render_call():
    """Plan fonksiyonu gövdesinde .render( çağrısı olmamalı (ölçüm LRU'dan)."""
    source = _game_source()
    start = source.index("def _fit_hud_stat_row")
    end = source.index("def _font_cache_key", start)
    body = source[start:end]
    assert "measure_text_width" in body
    assert ".render(" not in body
