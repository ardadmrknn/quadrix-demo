# -*- coding: utf-8 -*-
"""P1-2: Campaign sağ HUD stat satırları ölç-önce plan containment.

Rapor: Quadrix_Tum_Ekranlar_Olcekleme_Denetim_Raporu.md §5 (P1-2) —
campaign_mode.py sağ panel stat satırları ölçüm yapmadan etiketi soldan,
değeri sağdan çiziyordu: uzun lokalize etiket + geniş skor değeri +
büyüyen campaign hud ölçeği kombinasyonunda orta bölgede üst üste biniyordu;
dikey taşmada (stats_rect bittiği yerde opsiyonel combo/tetris satırı
mode_info alanına sızması) hiçbir kontrol yoktu.

Düzeltme sözleşmesi (game.py stats bloğu ve P1-1 Hardcore ile aynı desen):
- her satır Game._fit_hud_stat_row ile ölç-önce planlanır (ölçümler LRU);
- sığmayan toplam önce üniform küçültme ladder'ı (1.0→0.52), EN SON
  opsiyonel satır düşürme (zorunlu 3 satır: skor/satır/seviye korunur);
- taban boyutlarda bile sığmayan satır kontrollü dikey yerleşime düşer,
  ellipsis en son çaredir (ASCII '...' — emoji yasak);
- gerçek blit rect'leri _campaign_hud_stat_rects'e kaydedilir;
- stats gradient artık boyut-anahtarlı cache (kare-başı Surface tahsisi
  yasağı, CLAUDE.md §6).

Bilinçli ürün kararı kiliti: campaign hud ölçeği preset'i yok sayar
(apply_preset=False) — bu davranış DEĞİŞTİRİLMEZ; okunabilirlik tabanı
planlayıcı floor'ları (11/15) + ladder ile korunur.

Ölçüm sınırı (dürüst rapor): gerçek görsel doğrulama kılavuz §11'deki
manuel Windows smoke'a aittir — dummy driver altında koşulmaz. Bu dosya
plan/bütçe değişmezlerini ve kaynak sözleşmesini kilitler.

Kalıp: test_phase7_campaign_hud_ui_scaling (bare CampaignMode instance +
sys.modules retro_style/localization stub'ları; planlayıcı game.py
modül-düzeyi bağlamasıyla GERÇEK fontlarla ölçer) ve
test_wide_arena_hud_scale_containment (plan değişmezleri).

Demo'ya özgü bilinçli fark: opsiyonel tetris sayısı satırının etiketi
t('tetris_label') yerine sabit 'Quadrix' markalaşmasıdır (demo özel
markalaşması; v2'deki t('tetris_label') farkı korunur). Dosyadaki demo
test grubu bu farkı kilitler — v2'den eşitleme yapılırken etiket
kalıbının geri getirilmesi bu dosyayı kırmızıya çevirir.
"""
from __future__ import annotations

import os
import pathlib
import re
import sys
import types
from types import SimpleNamespace

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import pytest

import retro_style as retro_style_module
from campaign import campaign_mode as campaign_mode_module

if not pygame.font.get_init():
    pygame.font.init()

# FAZ A6 modül-kimliği temizliği (test_coop.py / G dosyası düşürme kalıbı):
# yukarıdaki import zinciri campaign/__init__.py'yi çalıştırır ve tüm
# campaign alt modüllerini BU dosyanın pygame nesline bağlar; conftest her
# koleksiyon sınırında pygame ailesini sys.modules'tan düşürür. Burada
# bırakılan eski binding'li campaign girdileri sonraki toplanan dosyada
# modül-kimliği bölünmesi yaratır. Bu dosyanın testleri yukarıdaki doğrudan
# referansla (campaign_mode_module) çalıştığı için aileyi düşürmek etkilemez;
# sonraki dosya kendi pygame'iyle temiz yükler.
for _mod_name in [n for n in list(sys.modules)
                  if n == "campaign" or n.startswith("campaign.")
                  or n == "src.campaign" or n.startswith("src.campaign.")]:
    sys.modules.pop(_mod_name, None)


# ── Campaign ölçekte gerçekçi senaryolar ────────────────────────────────────
# _get_campaign_hud_scale clamp'i: 0.74 (küçük ekran) – 1.12 (büyük ekran);
# referans 1366x768 (CAMPAIGN_HUD_REFERENCE_SIZE) → scale 1.0.
CAMPAIGN_HUD_MIN = 0.74
CAMPAIGN_HUD_MAX = 1.12
CONTENT_W_1366 = 192      # 1366x768'de ölçülen panel içerik genişliği civarı


def _make_mode() -> campaign_mode_module.CampaignMode:
    """Bare CampaignMode: _fit_hud_stat_row yalnız statik yardımcıları kullanır."""
    return campaign_mode_module.CampaignMode.__new__(campaign_mode_module.CampaignMode)


# ── Plan düzeyi: ölç-önce plan değişmezleri (gerçek fontlarla) ──────────────


@pytest.mark.parametrize(
    "content_w,hud",
    [
        (CONTENT_W_1366, 1.0),            # 1366x768 referans
        (CONTENT_W_1366, CAMPAIGN_HUD_MIN),
        (CONTENT_W_1366, CAMPAIGN_HUD_MAX),
        (240, CAMPAIGN_HUD_MAX),          # büyük ekran, geniş panel
        (140, 1.0),                       # dar panel (min panel genişliği civarı)
        (96, CAMPAIGN_HUD_MIN),           # dar + küçük ölçek
        (64, 1.0),                        # aşırı dar (dikey yerleşim bölgesi)
    ],
)
@pytest.mark.parametrize(
    "label,value",
    [
        ("SKOR", "1.234.567"),
        ("SCORE", "12.345.678"),
        ("TEMİZLENEN SATIR", "1234"),
        ("SEVİYE", "99"),
        ("KOMBO ZİNCİRİ", "x12"),
    ],
)
def test_campaign_stat_row_plan_never_overlaps_label_and_value(content_w, hud, label, value):
    """Çekirdek değişmezi: yatay satırda etiket+boşluk+değer daima sığar.

    Eski kod (P1-2 bulgusu) ölçmediği için uzun lokalize etiket soldan,
    geniş değer sağdan çizilip ORTADA üst üste biniyordu. Yeni plan ya
    sığan bir yatay satır üretir (l_w + row_gap + v_w <= avail_w) ya da
    vertical=True olur — ikisi arası (yarı çakışan yatay satır) asla
    üretilmez.
    """
    mode = _make_mode()
    # Campaign pad'i: s(15, minimum=8) → max(8, int(15 * hud))
    pad = max(8, int(15 * hud))
    plan = mode._fit_hud_stat_row(
        label,
        value,
        content_w,
        hud,
        label_base=16,
        value_base=24,
        slot_base=45,
        pad=pad,
        bold_label=False,
    )

    assert plan['avail_w'] >= 24
    if not plan['vertical']:
        total = plan['label_w'] + plan['row_gap'] + plan['value_w']
        assert total <= plan['avail_w'], (
            f"yatay satır taşması: label={plan['label_w']} gap={plan['row_gap']} "
            f"value={plan['value_w']} avail={plan['avail_w']} (hud={hud}, w={content_w})"
        )
    else:
        # Dikey yerleşimde DEĞER daima satır genişliğine sığar. ETİKET taşabilir —
        # bu paylaşılan planlayıcının (game.py) bilinen kenar durumudur; game.py
        # dokunulmaz, tüketicideki draw-zamanı ellipsis guard'ı kapatır (bkz.
        # test_stats_block_draw_uses_plan_vertical_layout).
        assert plan['value_w'] <= plan['avail_w']


def test_campaign_stat_row_baseline_geometry_matches_legacy_sizes():
    """1366x768 referansında (hud=1.0) plan taban boyutları eski kodla birebir.

    Eski draw_stat_row: s(16, minimum=11) etiket / s(24, minimum=15) değer /
    s(45, minimum=28) satır yüksekliği. Planlayıcı aynı tabanlarla (16/24/45,
    floor 11/15/28) ölçer → baseline piksel düzeni korunur, yalnız taşma
    senaryoları düzelir.
    """
    mode = _make_mode()
    plan = mode._fit_hud_stat_row(
        "SKOR", "1.234.567", CONTENT_W_1366, 1.0,
        label_base=16, value_base=24, slot_base=45, pad=15, bold_label=False,
    )

    assert plan['vertical'] is False
    # Font kimlikleri: eski kodun get_font(s(16, min 11)) / get_font(s(24, min 15), bold=True)
    # çağrılarıyla AYNI font_cache girdileri (retro_style singleton).
    assert plan['label_font'] is retro_style_module.retro_style.get_font(16, bold=False)
    assert plan['value_font'] is retro_style_module.retro_style.get_font(24, bold=True)
    # Satır yüksekliği: eski s(45, minimum=28) = 45 (font yüksekliği 45'i aşmadıkça).
    assert plan['row_h'] == max(45, plan['label_h'], plan['value_h'])
    assert plan['row_h'] >= 45


def test_campaign_stat_row_floors_preserve_readability():
    """Küçültme tabanların (etiket 11 / değer 15) altına inmez → okunabilirlik.

    Preset yok sayıldığı için (apply_preset=False) okunabilirlik tabanı bu
    floor'lardır — rapor P1-2'nin 'minimum okunabilirlik testle tanımlanmalı'
    şartı.
    """
    mode = _make_mode()
    plan = mode._fit_hud_stat_row(
        "TEMİZLENEN SATIR", "999.999", 100, CAMPAIGN_HUD_MAX,
        label_base=16, value_base=24, slot_base=45, pad=15, bold_label=False,
    )

    assert plan['label_h'] >= 11
    assert plan['value_h'] >= 15
    assert plan['label_font'] is not None and plan['value_font'] is not None


def test_campaign_stat_row_vertical_fallback_when_floor_fonts_do_not_fit():
    """Taban fontlarda bile sığmayan satır kontrollü dikey yerleşime düşar."""
    mode = _make_mode()
    plan = mode._fit_hud_stat_row(
        "SEVİYE", "999.999", 60, CAMPAIGN_HUD_MAX,
        label_base=16, value_base=24, slot_base=45, pad=15, bold_label=False,
    )

    assert plan['vertical'] is True
    # Dikeyde DEĞER taşmaz (planlayıcı sözleşmesi); etiket taşması bilinen
    # kenar durumdur (draw-zamanı guard ile kapanır).
    assert plan['value_w'] <= plan['avail_w']
    assert plan['row_h'] >= plan['label_h'] + max(2, int(4 * CAMPAIGN_HUD_MAX)) + plan['value_h'] - 1
    # Satır slotu dikeyde her iki bloğu kapsar (row_h >= label_h + value_h).
    assert plan['row_h'] >= plan['label_h'] + plan['value_h']


def test_campaign_stat_row_ellipsis_is_ascii_last_resort():
    """Ellipsis yalnız dikey yerleşimde DEĞER taşarsa uygulanır (ASCII '...')."""
    mode = _make_mode()
    original = "123.456.789"
    plan = mode._fit_hud_stat_row(
        "SKOR", original, 48, CAMPAIGN_HUD_MAX,
        label_base=16, value_base=24, slot_base=45, pad=15, bold_label=False,
    )

    assert plan['value_w'] <= plan['avail_w']
    if plan['value_text'] != original:
        assert plan['value_text'].endswith("...")
        assert len(plan['value_text']) < len(original)
        # ASCII '...' — emoji yok (CLAUDE.md: pygame fontları emoji gliflerini
        # desteklemez).
        assert all(ord(ch) < 128 for ch in plan['value_text'])


def test_campaign_stat_row_plan_is_allocation_free():
    """Plan aşaması Surface ÜRETMEZ; tekrar çağrı aynı font NESNESİNİ verir.

    Kare-başı tahsis yasağı (CLAUDE.md §6): ölçümler LRU'dan, fontlar
    retro_style font_cache'ten; küçültme 0.05 adımlarla kuantalı.
    """
    mode = _make_mode()
    plan_a = mode._fit_hud_stat_row(
        "SKOR", "1.234.567", CONTENT_W_1366, 1.0,
        label_base=16, value_base=24, slot_base=45, pad=15, bold_label=False,
    )
    plan_b = mode._fit_hud_stat_row(
        "SKOR", "1.234.567", CONTENT_W_1366, 1.0,
        label_base=16, value_base=24, slot_base=45, pad=15, bold_label=False,
    )

    for value in plan_a.values():
        assert not isinstance(value, pygame.Surface), "plan aşaması Surface üretmemeli"
    assert plan_a['label_font'] is plan_b['label_font']
    assert plan_a['value_font'] is plan_b['value_font']


# ── Draw düzeyi: gerçek blit rect'leri (phase7 bare-instance idyomu) ─────────


class _FakeFont:
    """retro_style stub fontu — yalnız runtime import eden draw koduna hizmet eder.

    Planlayıcı (game.py._fit_hud_stat_row) game.py modül-düzeyi bağlamasıyla
    GERÇEK retro_style fontlarını kullanır; ölçüm gerçek olur.
    """

    def __init__(self, size: int):
        self._size = max(1, int(size))

    def render(self, text, antialias, color):
        width, height = self.size(text)
        surface = pygame.Surface((width, height), pygame.SRCALPHA)
        rgb = tuple(color[:3]) if isinstance(color, tuple) else (255, 255, 255)
        surface.fill((*rgb, 255))
        return surface

    def size(self, text):
        return max(1, int(len(str(text or '')) * self._size * 0.55)), self.get_height()

    def get_height(self):
        return self._size

    def get_linesize(self):
        return self._size


def _make_fake_font(size: int, bold: bool = False):
    return _FakeFont(size)


def _install_right_hud_test_stubs(monkeypatch) -> None:
    """phase7 kalıbı: runtime import eden retro_style/localization stub'ları."""

    def _get_fitting_font(text, size, max_width, bold=False, min_size=None):
        base_size = max(1, int(size))
        minimum = max(1, int(min_size or 1))
        candidate = base_size
        while candidate > minimum:
            font = _make_fake_font(candidate, bold=bold)
            if font.size(text)[0] <= max_width:
                return font
            candidate -= 1
        return _make_fake_font(minimum, bold=bold)

    retro_style_stub = types.ModuleType('retro_style')
    retro_style_stub.retro_style = SimpleNamespace(
        draw_glass_panel=lambda surface, rect, alpha=90, border_color=(255, 255, 255), glow=False: pygame.draw.rect(surface, border_color, rect, 1),
        get_font=lambda size, bold=False: _make_fake_font(size, bold=bold),
        get_fitting_font=_get_fitting_font,
    )
    localization_stub = types.ModuleType('localization')
    localization_stub.t = lambda key, *args, **kwargs: key
    # Modül-kimliği purge bloğu (bkz. dosya başı) campaign ailesini
    # sys.modules'tan düşürdüğü için üretim kodundaki lazy importlar
    # (ör. _boss_get_type → from .level_data import ...) test sırasında
    # campaign/__init__ zincirini YENİDEN çalıştırır; bu zincirin
    # level_select/coop_level_select modül-düzeyi importu
    # `from localization import t, get_language` ister. Stub bu ikisini
    # de sağlamalı, yoksa lazy import stub'a çarpar (ImportError).
    localization_stub.get_language = lambda: 'tr'

    monkeypatch.setitem(sys.modules, 'retro_style', retro_style_stub)
    monkeypatch.setitem(sys.modules, 'localization', localization_stub)


def _prepare_right_hud_mode(size: tuple[int, int]) -> campaign_mode_module.CampaignMode:
    mode = campaign_mode_module.CampaignMode.__new__(campaign_mode_module.CampaignMode)
    mode.screen = pygame.Surface(size, pygame.SRCALPHA)
    mode.window_width, mode.window_height = size
    mode.current_level_num = 7
    mode.is_boss = False
    mode.is_mini_boss = False
    mode._hide_next_pieces = False
    mode._show_hold_x = False
    mode.held_piece = None
    mode.can_hold = True
    mode.next_piece_queue = []
    mode.board = SimpleNamespace(score=12345, lines_cleared=9, level=7, combo=1, tetrises=0)
    mode._draw_hud_glass_panel = lambda rect: None
    mode._draw_custom_frame = lambda rect, asset_name, padding=0, hole_punch=False: False
    mode.draw_textured_block = lambda *args, **kwargs: None
    mode._make_texture_slice = lambda *args, **kwargs: None
    return mode


def _draw_right_hud(mode) -> None:
    mode._draw_right_hud_panel(430, 70, 300, 620, None, None, (255, 255, 255), (0, 255, 255), (180, 180, 180))


def _assert_rows_contained(recs: dict) -> None:
    """Kaydedilen gerçek blit rect'lerinin panel/bütçe değişmezleri."""
    content_x = recs['content_x']
    content_w = recs['content_w']
    assert recs['rows'], "stat satırı kaydı boş olmamalı"

    for row in recs['rows']:
        for rect in (row['label_rect'], row['value_rect']):
            # Yatay içerik sınırı: panel kenarlarına taşma yok.
            assert rect.left >= content_x - 1, (
                f"etiket/değer panel sol kenarını taşıyor: {rect}"
            )
            assert rect.right <= content_x + content_w + 1, (
                f"etiket/değer panel sağ kenarını taşıyor: {rect} (content_w={content_w})"
            )
        # Satır içi çakışma yok (P1-2 çekirdek bulgusu).
        assert not row['label_rect'].colliderect(row['value_rect']), (
            f"etiket ve değer çakışıyor: {row['label_rect']} vs {row['value_rect']}"
        )

    # Dikey istifleme: ardışık satır rect'leri çakışmaz.
    for prev, nxt in zip(recs['rows'], recs['rows'][1:]):
        for prev_rect in (prev['label_rect'], prev['value_rect']):
            for nxt_rect in (nxt['label_rect'], nxt['value_rect']):
                assert not prev_rect.colliderect(nxt_rect), (
                    f"ardışık stat satırları çakışıyor: {prev_rect} vs {nxt_rect}"
                )

    # Bütçe sözleşmesi: 4 satır çizildiyse dikey bütçeye sığmış olmalı;
    # 3 satıra düştüyse opsiyonel satır (combo/tetris) kontrollü düşürülmüş
    # olmalı (zorunlu 3 satır daima çizilir — game.py sözleşmesi).
    total_h = sum(row['row_h'] for row in recs['rows'])
    if len(recs['rows']) > 3:
        assert total_h <= recs['rows_avail'], (
            f"4 satır bütçeyi aşıyor: total={total_h} avail={recs['rows_avail']}"
        )
    else:
        assert len(recs['rows']) == 3


@pytest.mark.parametrize(
    "size",
    [
        (1280, 720),
        (1366, 768),
        (1920, 1080),
        (2560, 1440),
        (3840, 2160),
    ],
)
def test_right_hud_stat_rows_contained_across_screen_matrix(monkeypatch, size):
    """Ekran matrisi: stat satırları panel genişliğine ve dikey bütçeye sığar."""
    _install_right_hud_test_stubs(monkeypatch)

    mode = _prepare_right_hud_mode(size)
    mode.board.combo = 5  # opsiyonel 4. satır (combo) aktif

    _draw_right_hud(mode)

    recs = mode._campaign_hud_stat_rects
    assert recs is not None
    assert recs['panel'] is mode._hud_panel_rect
    assert recs['stats'] is mode._hud_stats_rect
    assert recs['content_w'] == mode._hud_content_w
    _assert_rows_contained(recs)


def test_right_hud_stat_rows_with_long_localized_strings(monkeypatch):
    """Uzun lokalize etiketler + geniş skor: çakışma/dışa taşma yine imkansız."""
    _install_right_hud_test_stubs(monkeypatch)

    localization_stub = sys.modules['localization']
    translations = {
        'campaign_title': 'CAMPAIGN MODE EXTENDED',
        'score': 'SKOR DEĞERİ TOPLAMI',
        'lines': 'TEMİZLENEN SATIR SAYISI',
        'level': 'SEVİYE NUMARASI',
        'combo': 'KOMBO ZİNCİRİ ÇARPANI',
        'next': 'Next Pieces Preview:',
        'hold': 'Hold Queue Storage (C):',
    }
    localization_stub.t = lambda key, *args, **kwargs: translations.get(key, key)

    mode = _prepare_right_hud_mode((1366, 768))
    mode.board.score = 999_999_999  # geniş değer: '999.999.999'
    mode.board.combo = 12

    _draw_right_hud(mode)

    recs = mode._campaign_hud_stat_rects
    _assert_rows_contained(recs)
    # Uzun etiketler dikey yerleşimi tetikleyebilir — her durumda kayıtlı
    # dikey bayı planla tutarlı olmalı.
    for row in recs['rows']:
        if not row['vertical']:
            assert row['label_rect'].right <= row['value_rect'].left + 1


def test_right_hud_optional_rows_branches(monkeypatch):
    """Combo ve tetris dalları ayrı ayrı çizilir ve kayda geçer."""
    _install_right_hud_test_stubs(monkeypatch)

    mode_combo = _prepare_right_hud_mode((1366, 768))
    mode_combo.board.combo = 5
    mode_combo.board.tetrises = 0
    _draw_right_hud(mode_combo)
    rows_combo = mode_combo._campaign_hud_stat_rects['rows']
    assert [row['label'] for row in rows_combo] == ['score', 'lines', 'level', 'combo']
    _assert_rows_contained(mode_combo._campaign_hud_stat_rects)

    mode_tetris = _prepare_right_hud_mode((1366, 768))
    mode_tetris.board.combo = 1
    mode_tetris.board.tetrises = 2
    _draw_right_hud(mode_tetris)
    rows_tetris = mode_tetris._campaign_hud_stat_rects['rows']
    # Demo dalında tetris satırı t('tetris_label') değil 'Quadrix' etiketidir
    # (bilinçli markalaşma farkı — dosya başındaki nota bkz.).
    assert [row['label'] for row in rows_tetris] == ['score', 'lines', 'level', 'Quadrix']
    _assert_rows_contained(mode_tetris._campaign_hud_stat_rects)


# ── Demo'ya özgü markalaşma: 'Quadrix' tetris satırı (v2 farkı kilitli) ──────
# Bilinçli repo farkı (v2 vs demo): v2'de opsiyonel tetris sayısı satırının
# etiketi t('tetris_label') ile lokalize edilir; demo dalında bu satır sabit
# 'Quadrix' marka etiketiyle ve (100, 255, 100) rengiyle gösterilir. Bu fark
# eşitleme commit'lerinde bilinçli korunur — aşağıdaki testler v2'den yapılacak
# taşımalarda t('tetris_label') kalıbının geri gelmesini engeller.


def test_demo_tetris_row_label_is_quadrix_branding(monkeypatch):
    """tetrises>0 + combo<=1 → opsiyonel 4. satır 'Quadrix' etiketiyle çizilir."""
    _install_right_hud_test_stubs(monkeypatch)

    mode = _prepare_right_hud_mode((1366, 768))
    mode.board.combo = 1
    mode.board.tetrises = 2
    _draw_right_hud(mode)

    rows = mode._campaign_hud_stat_rects['rows']
    assert [row['label'] for row in rows] == ['score', 'lines', 'level', 'Quadrix']


def test_demo_quadrix_label_ignores_localization(monkeypatch):
    """'Quadrix' etiketi t() çeviri katmanına gitmez: lokalize stub
    'tetris_label' anahtarını çevirse bile demo satırı sabit kalır."""
    _install_right_hud_test_stubs(monkeypatch)

    localization_stub = sys.modules['localization']
    localization_stub.t = lambda key, *args, **kwargs: {
        'tetris_label': 'TETRIS SAYISI',
    }.get(key, key)

    mode = _prepare_right_hud_mode((1366, 768))
    mode.board.combo = 1
    mode.board.tetrises = 3
    _draw_right_hud(mode)

    rows = mode._campaign_hud_stat_rects['rows']
    assert rows[-1]['label'] == 'Quadrix'


def test_demo_quadrix_row_drops_when_tetrises_zero(monkeypatch):
    """tetrises=0 + combo<=1 → 'Quadrix' satırı hiç çizilmez (3 zorunlu satır)."""
    _install_right_hud_test_stubs(monkeypatch)

    mode = _prepare_right_hud_mode((1366, 768))
    mode.board.combo = 1
    mode.board.tetrises = 0
    _draw_right_hud(mode)

    rows = mode._campaign_hud_stat_rects['rows']
    assert [row['label'] for row in rows] == ['score', 'lines', 'level']


def test_demo_quadrix_row_yields_to_combo_row(monkeypatch):
    """combo>1 ve tetrises>0 birlikte: elif sözleşmesi — combo satırı kazanır,
    'Quadrix' satırı çizilmez (ikisi aynı anda gösterilmez)."""
    _install_right_hud_test_stubs(monkeypatch)

    mode = _prepare_right_hud_mode((1366, 768))
    mode.board.combo = 5
    mode.board.tetrises = 2
    _draw_right_hud(mode)

    rows = mode._campaign_hud_stat_rects['rows']
    assert [row['label'] for row in rows] == ['score', 'lines', 'level', 'combo']


@pytest.mark.parametrize("size", [(1024, 600), (3840, 2160)])
def test_demo_quadrix_row_contained_extreme_screens(monkeypatch, size):
    """'Quadrix' satırı dar/geniş uç ekranlarda da panel/bütçe değişmezlerini
    korur (marka etiketi containment davranışını değiştirmez)."""
    _install_right_hud_test_stubs(monkeypatch)

    mode = _prepare_right_hud_mode(size)
    mode.board.combo = 1
    mode.board.tetrises = 7
    _draw_right_hud(mode)

    recs = mode._campaign_hud_stat_rects
    _assert_rows_contained(recs)
    assert recs['rows'][-1]['label'] == 'Quadrix'


def test_demo_source_pins_quadrix_stat_row():
    """Kaynak pini: marka satırı tam imzayla (etiket, değer kaynağı, renk)."""
    source = _campaign_source()
    assert re.search(
        r"stat_row_defs\.append\(\('Quadrix', str\(self\.board\.tetrises\), "
        r"\(100, 255, 100\)\)\)",
        source,
    ), "demo 'Quadrix' marka satırı kayboldu"


def test_demo_source_pins_quadrix_divergence_comment():
    """Bilinçli-fark yorumu: eşitlemede kasıtlı olduğunu belgeleyen satır."""
    source = _campaign_source()
    assert "demo ozel markalasma" in source
    assert "v2'deki t('tetris_label') farki korunur" in source


def test_demo_source_forbids_tetris_label_in_stat_defs():
    """v2 kalıbının geri gelmediği negatif pin: stat_row_defs içinde
    t('tetris_label') etiketi demo dalında yasak (bilinçli fark)."""
    source = _campaign_source()
    assert "stat_row_defs.append((t('tetris_label')" not in source


def test_right_hud_baseline_row_height_matches_legacy_slot_geometry(monkeypatch):
    """1366x768 baseline: satır yüksekliği eski s(45, minimum=28) düzeniyle eş.

    Plan tabanları (16/24/45, floor 11/15/28) eski kodun s(...) değerleriyle
    birebir → baseline görünüm korunur (yalnız taşma senaryoları değişir).
    """
    _install_right_hud_test_stubs(monkeypatch)

    mode = _prepare_right_hud_mode((1366, 768))
    mode.board.combo = 1
    mode.board.tetrises = 0

    _draw_right_hud(mode)

    recs = mode._campaign_hud_stat_rects
    assert len(recs['rows']) == 3
    for row in recs['rows']:
        assert row['row_h'] == max(45, row['label_rect'].height, row['value_rect'].height)
        assert row['row_h'] >= 45
        assert row['vertical'] is False


def test_right_hud_stats_background_surface_cached_by_size(monkeypatch):
    """Kare-başı Surface tahsisi yasağı: gradient yalnız boyut değişince üretilir."""
    _install_right_hud_test_stubs(monkeypatch)

    mode = _prepare_right_hud_mode((1366, 768))
    _draw_right_hud(mode)
    first_surface = mode._campaign_stats_bg_surface
    first_key = mode._campaign_stats_bg_key
    assert first_surface is not None
    assert first_key == (first_surface.get_width(), first_surface.get_height())

    # İkinci kare — aynı boyut: Surface NESNESİ yeniden üretilmez.
    _draw_right_hud(mode)
    assert mode._campaign_stats_bg_surface is first_surface
    assert mode._campaign_stats_bg_key == first_key

    # Boyut değişince (büyük ekran) yeniden üretilir ve eski referans kalmaz.
    mode.screen = pygame.Surface((2560, 1440), pygame.SRCALPHA)
    mode.window_width, mode.window_height = 2560, 1440
    _draw_right_hud(mode)
    assert mode._campaign_stats_bg_surface is not first_surface


# ── Kaynak sözleşmeleri (AST-pin idyomu) ────────────────────────────────────
# Repo idyomu (test_wide_arena_hud_scale_containment): inline mantık birim
# çağrılamadığından kaynak sözleşmesiyle sabitlenir.


def _campaign_source() -> str:
    return pathlib.Path(campaign_mode_module.__file__).read_text(encoding='utf-8')


def test_stats_block_uses_measure_first_ladder_with_mandatory_rows():
    source = _campaign_source()
    # Ölç-önce ladder: 5 basamak, üniform küçültme.
    assert re.search(r"for shrink in \(1\.0, 0\.88, 0\.76, 0\.64, 0\.52\):", source)
    # Zorunlu satır sayısı: opsiyonel (combo/tetris) satır EN SON düşürülür.
    assert re.search(r"mandatory_row_count = 3", source)
    assert re.search(r"stat_plans = stat_plans\[:mandatory_row_count\]", source)


def test_stats_block_uses_shared_planner_with_campaign_bases():
    source = _campaign_source()
    start = source.index("for shrink in (1.0, 0.88, 0.76, 0.64, 0.52):")
    ladder = source[start:start + 900]
    assert "self._fit_hud_stat_row(" in ladder
    # Campaign tabanları: eski s(16, min 11)/s(24, min 15)/s(45, min 28) ile eş.
    assert "label_base=max(4, int(round(16 * shrink)))" in ladder
    assert "value_base=max(6, int(round(24 * shrink)))" in ladder
    assert "slot_base=max(12, int(round(45 * shrink)))" in ladder
    # Etiket eski kodda bold DEĞİLDİ — korunur.
    assert "bold_label=False" in ladder
    # Campaign pad'i: s(15, minimum=8).
    assert re.search(r"stat_pad = s\(15, minimum=8\)", source)


def test_stats_block_draw_uses_plan_vertical_layout():
    source = _campaign_source()
    start = source.index("def draw_stat_row(plan, y_pos")
    end = source.index("for (_label, _value, row_color), plan in zip", start)
    draw_fn = source[start:end]
    assert "plan['vertical']" in draw_fn
    assert "topright" in draw_fn
    # Etiket cache'li (render_text), değer ham render (mevcut davranış korunur).
    assert "render_text(label_font, label_text" in draw_fn
    # Eski ölçümsüz desen kalmasın: doğrudan label render yok.
    assert ".render(label" not in draw_fn
    # Dikey modda planlayıcının ellipsis'lemediği ETİKET için draw-zamanı
    # guard (game.py kenar durumu bu panelde kapatılır).
    assert "plan['label_w'] > plan['avail_w']" in draw_fn
    assert "self._ellipsis_text(label_text, label_font, plan['avail_w'])" in draw_fn
    # Dikey değerin satır slotundan taşmaması: slot kenetleme guard'ı —
    # bir sonraki satırın -s(4) yükseltme payı rezerve edilir, etiket tabanı
    # (+2) korunur (row_h >= label_h + value_h daima sağlandığından güvenli).
    assert "y_pos + plan['row_h'] - plan['value_h'] - s(4, minimum=2)" in draw_fn
    assert "value_top = max(value_top, y_pos + plan['label_h'] + 2)" in draw_fn


def test_stat_row_rects_recorded_for_containment():
    source = _campaign_source()
    assert "_campaign_hud_stat_rects" in source
    assert "'rows_bottom_cap'" in source
    assert "'rows_avail'" in source
    assert "'rows': recorded_rows" in source


def test_stats_background_is_size_keyed_cache():
    source = _campaign_source()
    start = source.index("stats_key = (int(stats_rect.width), int(stats_rect.height))")
    end = source.index("stat_y_cur = curr_y", start)
    block = source[start:end]
    assert "_campaign_stats_bg_key" in block
    assert "_campaign_stats_bg_surface" in block
    # Surface tahsisi yalnız cache-miss dalında (kare-başı tahsis yasağı).
    assert block.count("pygame.Surface(") == 1
    assert "if getattr(self, '_campaign_stats_bg_key', None) != stats_key:" in block


def test_campaign_hud_scale_documents_deliberate_preset_bypass():
    """P1-2 şartı: apply_preset=False bilinçli ürün kararı olarak belgelenir."""
    source = _campaign_source()
    start = source.index("def _get_campaign_hud_scale")
    end = source.index("def _scale_campaign_hud_px", start)
    scale_fn = source[start:end]
    assert "apply_preset=False" in scale_fn
    lowered = scale_fn.lower()
    assert "urun karari" in lowered, "bilinçli ürün kararı belgesi eksik"
    # Okunabilirlik tabanı floor'larıyla telafi edildiği belgelenmeli.
    assert "11" in scale_fn and "15" in scale_fn
