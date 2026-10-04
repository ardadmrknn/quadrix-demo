# -*- coding: utf-8 -*-
"""§6.2: Yerel Co-op üst/alt HUD containment — ölçek/taşma regresyonları.

v2 uyarlaması (tests/test_coop_hud_containment.py kardeşi). Quadrix_Tum_
Ekranlar_Olcekleme_Denetim_Raporu.md §6.2: _draw_hud içinde level/lines/time
genişliği ölçülüyordu ve katkı metinleri fitting kullanıyordu; ancak
(a) başlık+skor stack'i üst bara sığmıyordu, (b) toplam stat satırı alt
barın iç bütçesine hiç karşılanmıyordu, (c) katkı surface'ları font.render
ile doğrudan üretiliyordu (kare başına 2 Surface tahsisi), (d) alt bar sıkı
yerleşimlerde (800x480) ekrandan çıkabiliyordu, (e) yan panellerde bölünmüş
tahta sınır koridoru (40px tabanlı daralma) YOKTU — v2'deki clamp bu
uyarlamayla demo'ya geldi.

Bu dosya draw() yollarının GEOMETRİK sözleşmesini kilitler:
- üst/alt bar daima ekran içinde; başlık/skor üst bar içinde ve çakışmaz;
- stat satırı alt barın İÇ bütçesinde (kuantalı font küçültme + gap
  daralma + son çare ASCII '...');
- sıkı yerleşimde alt bar ekrandan çıkmak yerine yukarı kayar;
- yan paneller (next/hold) tahtaya yatayda binmez, daralınca 40px taban
  genişliğini korur (640x480'de 120→112 daralması pin'li);
- kare-başı Surface tahsisi yok: render_fit_text/render_text önbellek
  kimliği iki çizim arasında korunur.

Demo'ya özgü uyarlamalar:
- sanal-tuval monkeypatch fixture'ı yok — demo coop_game modülünde
  is_virtual_canvas_active/get_virtual_canvas_ui_scale bağları hiç yok;
  _ui_scale doğrudan test içinde sabitlenir.
- yan panel kart yükseklikleri v2'den farklıdır (demo'nun preview_cs
  hesabı _ui_scale tabanlıdır; v2 panel_w/120 tabanlı) — p2_hold y pin'i
  231 değil 208'dir. Bu bilinçli demo sapması değil, mevcut demo yan
  panel tasarımıdır; §6.2 taşıması HUD sözleşmesi + sınır koridorudur.

Ölçüm sınırı (dürüst rapor): gerçek render görselliği ve Steam overlay
kılavuz §7'deki manuel Windows smoke'a aittir — dummy driver altında
yalnız geometri sözleşmesi ölçülür. Screen shake geçici ofsetler bu
dosyanın kapsamı dışındadır.

Kalıp: test_online_lobby_containment (dummy sürücüler + __new__ bare
instance + kayıtlı rect assert'leri) + test_menu_mode_music_highscore
(önbellek kimliği + kaynak sözleşme pin'leri).
"""
from __future__ import annotations

import os
import pathlib
import re
import sys

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

import pygame

if not pygame.get_init():
    pygame.init()
if not pygame.display.get_init():
    pygame.display.init()
pygame.display.set_mode((320, 240))
if not pygame.font.get_init():
    pygame.font.init()

ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / 'src'

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import pytest

import coop_game as coop_module
from coop_game import CoopGame
from gameplay_layout import compute_coop_layout

# Gerçek motor ölçekleriyle eşleştirilmiş matris: küçük ekran 0.72'ye
# küçültür, büyük preset (large/massive) 1.2'ye kadar büyütür. Yapay
# (boyut, ölçek) çiftleri üretilmez — üretim dışı kombinasyonlar bar-tahta
# örtüşmesi gibi üretimde oluşmayacak ihlaller üretirdi.
SIZE_SCALES = [
    ((640, 480), (0.72,)),
    ((800, 480), (0.72, 1.0)),
    ((1024, 600), (0.72, 1.0)),
    ((1280, 720), (0.72, 1.0)),
    ((1366, 768), (0.72, 1.0, 1.2)),
    ((1920, 1080), (1.0, 1.2)),
    ((3840, 2160), (1.0, 1.2)),
]

# Stres sahnesi: en uzun gerçekçi metinler (9 haneli skorlar, 999 dk,
# 5 haneli satır) — ambient dilin uzunluk oynaklığı bütçeyle emilir.
STRESS = dict(
    team_score=1234567890,
    level=99,
    total_lines_cleared=99999,
    elapsed_time=(999 * 60 + 59) * 1000,
    p1_score_contribution=987654321,
    p1_score_contribution_pct=53,
    p2_score_contribution=876543210,
    p2_score_contribution_pct=47,
)

# Baseline sahnesi (taban pin'lerinin ölçüldüğü değerler).
BASELINE = dict(
    team_score=1234567,
    level=12,
    total_lines_cleared=345,
    elapsed_time=754_000,
    p1_score_contribution=654321,
    p1_score_contribution_pct=53,
    p2_score_contribution=580651,
    p2_score_contribution_pct=47,
)


def _layout(size):
    return compute_coop_layout(
        active_size=size, effective_size=size, board_width=20, board_height=20)


def _make_game(size, scale, **scene):
    game = CoopGame.__new__(CoopGame)
    game.screen = pygame.Surface(size)
    game.window_width, game.window_height = size
    game._ui_scale = lambda mn=0.72, mx=1.20: scale
    merged = dict(BASELINE)
    merged.update(scene)
    for key, value in merged.items():
        setattr(game, key, value)
    return game


def _draw_hud(game, size):
    m = _layout(size)
    game._draw_hud(m.board_x, m.board_y, m.cell_size, m.board_width, m.board_height)
    return m


# ── Ana matris: barlar ekranda, metinler barlarda ───────────────────────────


@pytest.mark.parametrize('size,scales', SIZE_SCALES)
def test_coop_hud_containment_matrix(size, scales):
    for scale in scales:
        game = _make_game(size, scale, **STRESS)
        _draw_hud(game, size)
        r = game._coop_hud_rects
        screen_rect = pygame.Rect(0, 0, *size)

        assert screen_rect.contains(r['top_rect']), (size, scale, r['top_rect'])
        assert screen_rect.contains(r['bot_rect']), (size, scale, r['bot_rect'])

        # Başlık + skor üst barın içinde ve birbirine binmez.
        assert r['top_rect'].contains(r['title_rect']), (size, scale)
        assert r['top_rect'].contains(r['score_rect']), (size, scale)
        assert not r['title_rect'].colliderect(r['score_rect']), (size, scale)

        # Stat satırı: alt barın İÇ bütçesinde (kayıtlı sözleşme).
        assert r['stat_total_w'] <= r['bot_inner_w'], (
            size, scale, r['stat_total_w'], r['bot_inner_w'])
        for sr in r['stat_rects']:
            assert r['bot_rect'].contains(sr), (size, scale, sr)

        # Katkı satırları alt barın içinde; stat satırıyla çakışmaz.
        for cr in (r['contrib_p1_rect'], r['contrib_p2_rect']):
            assert r['bot_rect'].contains(cr), (size, scale, cr)
            for sr in r['stat_rects']:
                assert not sr.colliderect(cr), (size, scale, sr, cr)

        # Emoji/sembol yasağı (CLAUDE.md): fallback metinleri ASCII '...'
        # üretir; normal glif aralığının dışına çıkmaz.
        texts = [r['title_text'], r['score_text'], r['stat_texts'][1],
                 *r['contrib_texts']]
        for text in texts:
            assert all(ord(ch) < 0x1F000 for ch in text), repr(text)


# ── Taban yerleşim (1366x768 / 0.72): yapısal pin'ler ───────────────────────


def test_coop_hud_baseline_1366x768_structural_pins():
    """Dil-bağımsız yapısal pin'ler: panel dikdörtgenleri, yükseklikler,
    y-kademeleri ve merkezler. Metin genişliğinden türeyen x/w değerleri
    bilinçli olarak pin'lenmez (ambient dil dersleri)."""
    game = _make_game((1366, 768), 0.72)
    _draw_hud(game, (1366, 768))
    r = game._coop_hud_rects

    # Paneller: bw=640, ox=363, oy=84 (compute_coop_layout üretim değeri).
    assert (r['top_rect'].x, r['top_rect'].y, r['top_rect'].w) == (353, 4, 660)
    assert (r['bot_rect'].x, r['bot_rect'].y, r['bot_rect'].w) == (353, 726, 660)
    # Yükseklikler içerik-bütçeli: başlık(26) + skor(19) → 55 (eski kodda
    # bar 50'ydi ve skor satırı 5px taşıyordu); alt bar taban 36.
    assert r['top_rect'].h == 55
    assert r['bot_rect'].h == 36

    # Y-kademeleri: başlık 10'da, skor 10+26+4=40'ta, stat bar.y+4=730,
    # katkı stat_y + stat_h + 2 = 748'de.
    assert r['title_rect'].y == 10
    assert r['score_rect'].y == 40
    assert all(sr.y == 730 and sr.h == 16 for sr in r['stat_rects'])
    assert r['contrib_p1_rect'].y == 748 and r['contrib_p2_rect'].y == 748

    # Merkezler: başlık/skor pencere merkezinde (cx=683), katkılar tahta
    # çeyreklerinde (ox+bw*0.25=523, ox+bw*0.75=843).
    assert r['title_rect'].centerx == 683
    assert r['score_rect'].centerx == 683
    assert r['contrib_p1_rect'].centerx == 523
    assert r['contrib_p2_rect'].centerx == 843


def test_coop_hud_bottom_bar_never_leaves_screen():
    """Sıkı yerleşim (büyük preset): alt bar ekrandan çıkmak yerine yukarı
    kayar — 1366x768 @1.2'de bar 726'dan 710'a çıkar, dibi tam 768'de."""
    game = _make_game((1366, 768), 1.2, **STRESS)
    _draw_hud(game, (1366, 768))
    r = game._coop_hud_rects

    assert r['bot_rect'].bottom <= 768
    assert r['bot_rect'].y == 768 - r['bot_rect'].h, (
        'alt bar ekran dibine yaslanmalıydı (kaydırma guardı)', r['bot_rect'])
    # Kaydırma sonrası içerik yine bar içinde.
    for sr in r['stat_rects']:
        assert r['bot_rect'].contains(sr)
    for cr in (r['contrib_p1_rect'], r['contrib_p2_rect']):
        assert r['bot_rect'].contains(cr)


def test_coop_hud_stat_row_budget_on_narrow_bar():
    """Yapay dar bar (bw=150): stat satırı kuantalı küçülme/ellipsis ile
    iç bütçeye sığar; başlık/skor da üst bar bütçesine sığar."""
    size = (800, 480)
    game = _make_game(size, 0.72, **STRESS)
    game._draw_hud(325, 80, 18, 150, 360)
    r = game._coop_hud_rects
    screen_rect = pygame.Rect(0, 0, *size)

    assert screen_rect.contains(r['top_rect'])
    assert screen_rect.contains(r['bot_rect'])
    assert r['stat_total_w'] <= r['bot_inner_w'], (
        r['stat_total_w'], r['bot_inner_w'])
    assert r['top_rect'].contains(r['title_rect'])
    assert r['top_rect'].contains(r['score_rect'])
    for sr in r['stat_rects']:
        assert r['bot_rect'].contains(sr), sr
    for cr in (r['contrib_p1_rect'], r['contrib_p2_rect']):
        assert r['bot_rect'].contains(cr), cr


def test_coop_hud_no_per_frame_surface_allocation():
    """Kare-başı Surface tahsisi yok: aynı sahnede iki çizim arasında
    başlık/skor/katkı yüzeyleri önbellekten aynı nesne olarak gelir."""
    game = _make_game((1366, 768), 0.72, **STRESS)
    _draw_hud(game, (1366, 768))
    first = game._coop_hud_rects
    _draw_hud(game, (1366, 768))
    second = game._coop_hud_rects

    for key in ('title_surf', 'score_surf', 'p1_surf', 'p2_surf'):
        assert first[key] is second[key], (
            f'{key} ikinci karede yeniden üretilmiş (önbellek ihlali)')


# ── Yan paneller (§6.2: bölünmüş tahtada daralma) ────────────────────────────


def _make_side_game(size, scale):
    game = _make_game(size, scale)
    m = _layout(size)
    game._side_panel_width = m.side_panel_width
    game._no_preview = False
    game._no_hold = False
    game.p1_next_piece = None
    game.p2_next_piece = None
    game.p1_hold_piece = None
    game.p2_hold_piece = None
    game.pvp_controls = {}
    game._is_online_coop = False
    return game, m


@pytest.mark.parametrize('size', [(640, 480), (800, 480), (1366, 768), (3840, 2160)])
def test_coop_side_panels_fit_and_stay_off_board(size):
    game, m = _make_side_game(size, 0.72)
    game._draw_side_panels(m.board_x, m.board_y, m.cell_size, m.board_width, m.board_height)
    r = game._coop_side_panel_rects
    screen_rect = pygame.Rect(0, 0, *size)

    for key in ('p1_next', 'p2_next', 'p1_hold', 'p2_hold'):
        rect = r[key]
        assert rect is not None and rect.width > 0, (key, size)
        assert screen_rect.contains(rect), (key, size, rect)
        if key.startswith('p1'):
            assert rect.right <= m.board_x, (key, size, rect)
        else:
            assert rect.left >= m.board_x + m.board_width, (key, size, rect)

    # Daralma tabanı: panel_w asla 40'ın altına inmez ve panel genişliği
    # +12 çerçeveyle tutarlıdır.
    assert r['panel_w'] >= 40
    for key in ('p1_next', 'p2_next', 'p1_hold', 'p2_hold'):
        assert r[key].width == r['panel_w'] + 12


def test_coop_side_panel_narrows_on_split_board():
    """640x480 bölünmüş tahta: istenen 120px panel 112px'e daralır (tahta
    sınırı 124px), paneller ekranda ve tahtadan uzakta kalır (§6.2).

    Demo uyarlaması: kart yüksekliği v2'den farklıdır (demo preview_cs
    hesabı _ui_scale tabanlı) — p2_hold y pin'i 231 değil 208'dir."""
    game, m = _make_side_game((640, 480), 0.72)
    game._draw_side_panels(m.board_x, m.board_y, m.cell_size, m.board_width, m.board_height)
    r = game._coop_side_panel_rects

    assert r['requested_panel_w'] == 120
    assert r['panel_w'] == 112, r['panel_w']
    assert r['p1_next'].right <= m.board_x
    assert r['p2_hold'].left >= m.board_x + m.board_width
    assert pygame.Rect(0, 0, 640, 480).contains(r['p1_next'])
    assert pygame.Rect(0, 0, 640, 480).contains(r['p2_hold'])
    # Üretim pin'leri: 640x480'de sol next (14, 96) konumunda başlar.
    assert (r['p1_next'].x, r['p1_next'].y) == (14, 96)
    assert (r['p2_hold'].x, r['p2_hold'].y) == (502, 208)


# ── Kaynak sözleşmeleri (sınıf-gövdesi kapsamlı pin'ler) ────────────────────


def _method_source(method_name: str) -> str:
    source = pathlib.Path(coop_module.__file__).read_text(encoding='utf-8')
    start = source.index(f'    def {method_name}(')
    nxt = re.search(r'\n    def ', source[start + 10:])
    end = start + 10 + (nxt.start() if nxt else len(source) - start - 10)
    return source[start:end]


def test_source_hud_budget_and_cache_contract():
    src = _method_source('_draw_hud')
    # Bütçe yardımcıları kullanımda (ölç-önce + ellipsis).
    assert 'ellipsize_text' in src
    assert 'get_fitting_font' in src
    assert 'render_fit_text' in src
    # Kare-başı tahsis yasağı: doğrudan font.render yok (LRU yolları var).
    assert 'stat_font.render(' not in src
    assert 'score_font.render(' not in src
    assert "p1_font.render(" not in src
    # Alt bar ekrandan çıkamaz: yukarı kaydırma guard'ı.
    assert 'min(info_y - 4, self.window_height - bot_h)' in src
    # Test matrisi için rect kaydı.
    assert 'self._coop_hud_rects' in src


def test_source_contribution_rendered_once_per_frame():
    """Katkı bloğu stat döngüsünün DIŞINDA: döngü gövdesinde fitting/render
    çağrısı olmaz (kare başına yeniden render yok)."""
    src = _method_source('_draw_hud')
    loop_start = src.index('for it in items:')
    loop_end = src.index('contrib_y = stat_y + stat_h + 2')
    loop_body = src[loop_start:loop_end]

    assert 'render_fit_text' not in loop_body
    assert 'get_fitting_font' not in loop_body
    assert 'render_text(stat_font, it, True' in loop_body


def test_source_side_panel_rect_recording():
    src = _method_source('_draw_side_panels')
    assert 'self._coop_side_panel_rects' in src
    assert 'max(40, max_allowed_w - 12)' in src
