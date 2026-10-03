# -*- coding: utf-8 -*-
"""P1-6 + P0-2 (co-op tarafı): Co-op kampanya görev HUD + sonuç containment.

Rapor: Quadrix_Tum_Ekranlar_Olcekleme_Denetim_Raporu.md
- P1-6 (co-op): _draw_objectives_hud açıklamaları progress bar bütçesine
  sarılır (wrap → kontrollü ellipsis); satır yükseklikleri gerçek satır
  sayısından, panel yüksekliği içerikten türetilir ve dikeyde safe rect'e
  tavanlanır; ilerleme metni ilk satırın sağında sarma bütçesine dahildir
  (desc/prog çakışması matematiksel olarak engellenir).
- P0-2 (co-op): _draw_level_complete/_draw_level_failed paneli önce safe
  rect boyutlarına TAVANLANIR sonra safe rect'İN içine clamp'lenir
  (Rect.clamp küçültmez — tavan clamp'ten önce, türevler clamp'ten sonra);
  başlık/stat kolonları/katkı/hint panel içinde kalır; dikey bütçe kuantalı
  küçültme ladder'ıyla çözülür.
- ✓/✗ FONT SEMBOLLERİ kaldırıldı (CLAUDE.md emoji/sembol yasağı): işaretler
  pygame.draw.line/circle ile çizilir; kaynak dosyasında dingbat glifi
  kalmaz (kaynak sözleşmesi testi bunu kilitler).

Dürüst rapor notu: sonuç ekranlarında tıklanabilir BUTON yoktur — akış
klavye/gamepad + tam-ekran tık ile ilerler (handle_input'ta MOUSEBUTTONDOWN
serbest geçiş). Bu yüzden 'action rect' testi yerine panel/metin/hint rect
containment'ı kilitlenir; mouse buton hit-paritesi bu ekranda mevcut değil.

Kalıp: test_coop_level_select_narrow_screen (dummy sürücü + gerçek modül
importu + gerçek fontlar; _ui_scale instance override; safe rect kuşak
önbelleği doğrudan yazılarak HDR marj senaryosu simüle edilir).
Görsel doğrulama rapor §11'deki manuel Windows smoke'a aittir.
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

from campaign import coop_campaign_mode as coop_campaign_module
from campaign.coop_campaign_mode import CoopCampaignMode

if not pygame.font.get_init():
    pygame.font.init()

# FAZ A6 modül-kimliği temizliği (test_coop.py'nin coop_game düşürme kalıbı):
# Yukarıdaki import zinciri campaign/__init__.py'yi GERÇEK haliyle
# çalıştırır; __init__ line 46 coop_level_select dahil tüm alt modülleri BU
# dosyanın pygame instance'ına bağlar. conftest her koleksiyon sınırında
# pygame ailesini sys.modules'tan düşürdüğü için sonraki toplanan test
# dosyası (örn. test_coop_level_select_narrow_screen) kendi pygame
# instance'ıyla TAZE yükleme bekler; burada bırakılan eski binding'li
# campaign girdileri modül-kimliği bölünmesi yaratır — o dosyanın
# pygame.display.flip monkeypatch'i başka instance'ın display'ine düşer,
# coop_level_select.draw() gerçek flip'i çağırır ve "video system not
# initialized" ile tüm dosya düşer. Bu dosyanın testleri yukarıdaki doğrudan
# referanslarla (coop_campaign_module, CoopCampaignMode) çalıştığı için
# aileyi sys.modules'tan düşürmek onları etkilemez; sonraki dosya kendi
# pygame'iyle temiz yükler.
for _mod_name in [n for n in list(sys.modules)
                  if n == "campaign" or n.startswith("campaign.")
                  or n == "src.campaign" or n.startswith("src.campaign.")]:
    sys.modules.pop(_mod_name, None)


# ── Ölçüm matrisi ──────────────────────────────────────────────────────────
# 4K satırında HDR marjı simüle edilir (safe rect inset); küçük boyutlarda
# tam ekran (gerçek dünyada HDR inset yalnız 4K+ panelde oluşur).
SCREEN_MATRIX = [
    (640, 360),
    (800, 480),
    (1024, 600),
    (1366, 768),
    (1920, 1080),
    (3840, 2160),
]
# 0.72–1.20 CoopGame._ui_scale clamp aralığı; 2.065 = denetim raporundaki
# %175 preset gerilim senaryosu (HUD yolu) — yardımcılar clamp dışında da
# containment sağlamalı.
UI_MATRIX = (0.72, 1.0, 1.2, 2.065)

LONG_TR = ("Her iki oyuncu da en az %40 katkı sağlamalı ve dengeli bir "
           "oynuşla toplam hedefe ulaşmalı")
LONG_EN = ("Both players must contribute at least 40 percent and reach "
           "the shared target with balanced play")
SHORT_TR = "40 satır temizle"
LONG_LEVEL_NAME_TR = "Bölüm Adı Çok Uzun Olabilir Denetim Raporu Gerilim Senaryosu"


class FakeObjective:
    """Bare-instance draw yolu için Objective API'si (desc/progress/completed)."""

    def __init__(self, desc: str, progress: int = 3, target: int = 12,
                 completed: bool = False):
        self._desc = desc
        self.progress = progress
        self.target = target
        self.completed = completed

    def get_description(self, lang: str | None = None) -> str:
        return self._desc

    def get_progress_text(self) -> str:
        return f"{self.progress}/{self.target}"

    def get_progress_ratio(self) -> float:
        return min(1.0, self.progress / max(1, self.target))


def _force_safe_rect(mode, rect: pygame.Rect) -> None:
    """_coop_result_safe_rect kuşak önbelleğini doğrudan yaz (HDR senaryosu).

    Anahtar = gerçek geometry generation: platform_utils güvenilir değilse
    -1 sabitiyle yazılır; iki durumda da ilk draw çağrısı bu rect'i okur.
    """
    try:
        from platform_utils import get_geometry_generation
        gen = get_geometry_generation()
    except Exception:
        gen = -1
    mode._coop_result_geometry_cache = (gen, rect)


def _safe_rect_for(size):
    """4K için HDR-marj simülasyonu, diğerleri tam ekran."""
    w, h = size
    if w >= 3840:
        inset_x, inset_y = max(1, w // 40), max(1, h // 40)
        return pygame.Rect(inset_x, inset_y, w - 2 * inset_x, h - 2 * inset_y)
    return pygame.Rect(0, 0, w, h)


def _make_mode(size, ui, objectives, board_frac=(0.34, 0.12)):
    """Bare CoopCampaignMode: draw yardımcıları yalnız statik veri ister."""
    mode = CoopCampaignMode.__new__(CoopCampaignMode)
    w, h = size
    mode.screen = pygame.Surface((w, h))
    mode.window_width, mode.window_height = w, h
    mode.board_offset_x = int(w * board_frac[0])
    mode.board_offset_y = int(h * board_frac[1])
    mode.current_level_num = 7
    mode.level_config = type("LC", (), {
        "name": {"tr": LONG_LEVEL_NAME_TR, "en": "Level Name Can Be Long"}})()
    mode.objectives = list(objectives)
    mode._ui_scale = lambda: ui  # instance override (preset yolu bypass)
    mode._coop_result_geometry_cache = None
    mode.__dict__.setdefault("_coop_result_surface_cache", {})
    _force_safe_rect(mode, _safe_rect_for(size))
    return mode


def _make_complete_mode(size, ui, objectives):
    mode = _make_mode(size, ui, objectives)
    mode.level_complete = True
    mode.earned_stars = 2
    mode.team_score = 1234567
    mode.total_lines_cleared = 42
    mode.elapsed_time = 153000.0
    mode.p1_contribution_pct = 55
    mode.p2_contribution_pct = 45
    return mode


def _make_failed_mode(size, ui, objectives):
    mode = _make_mode(size, ui, objectives)
    mode.level_failed = True
    mode.fail_reason = "game_over"
    return mode


def _long_objectives():
    return [
        FakeObjective(LONG_TR, 5, 12, completed=True),
        FakeObjective(LONG_EN, 12, 12, completed=True),
        FakeObjective(SHORT_TR, 0, 40),
    ]


# ── P1-6: Görev HUD — sarma + içerikten panel + çakışma yasağı ────────────

@pytest.mark.parametrize("size", SCREEN_MATRIX)
@pytest.mark.parametrize("ui", UI_MATRIX)
def test_objectives_hud_all_rects_inside_panel_and_no_overlap(size, ui):
    """desc satırları, bar ve ilerleme metni panel içinde; desc/prog çakışmaz."""
    mode = _make_mode(size, ui, _long_objectives())
    mode._draw_objectives_hud()
    rec = mode._coop_objectives_rects
    assert rec is not None, "rect kayıtları üretilmedi"

    panel, screen_rect = rec["panel"], pygame.Rect(0, 0, *size)
    assert screen_rect.contains(panel)
    assert panel.bottom <= _safe_rect_for(size).bottom + 2

    assert rec["title"].right <= panel.right - 2
    assert panel.contains(rec["title"])

    prev_row = None
    for row in rec["rows"]:
        assert panel.contains(row["bar_rect"])
        assert panel.contains(row["prog_rect"])
        assert panel.contains(row["row_rect"])
        for drect in row["desc_rects"]:
            assert panel.contains(drect), (
                f"sarılmış desc panel dışına taşıyor: {drect} / panel {panel} "
                f"(size={size}, ui={ui})")
            # İlerleme metniyle yatay çakışma yasak (ilk satır sağında durur).
            assert not drect.colliderect(row["prog_rect"]), (
                f"desc/prog çakışması: {drect} vs {row['prog_rect']} "
                f"(size={size}, ui={ui})")
        if prev_row is not None:
            assert not prev_row.colliderect(row["row_rect"])
        prev_row = row["row_rect"]


@pytest.mark.parametrize("size", [(640, 360), (1366, 768), (3840, 2160)])
def test_objectives_hud_panel_height_follows_wrapped_content(size):
    """Uzun açıklamalar sarılır; panel kısa metne göre büyür (içerikten türetim)."""
    ui = 1.0
    short_mode = _make_mode(size, ui, [FakeObjective(SHORT_TR, 1, 40)])
    short_mode._draw_objectives_hud()

    long_mode = _make_mode(size, ui, _long_objectives())
    long_mode._draw_objectives_hud()

    short_panel = short_mode._coop_objectives_rects["panel"]
    long_panel = long_mode._coop_objectives_rects["panel"]
    assert long_panel.height >= short_panel.height
    # Uzun metin gerçekte SARILDI (tek satıra sıkıştırılmadı) veya
    # kontrollü ellipsis'e düştü — ikisi de containment'ı korur.
    long_rows = long_mode._coop_objectives_rects["rows"]
    assert len(long_rows) == 3
    total_lines = sum(len(r["desc_rects"]) for r in long_rows)
    assert total_lines >= 3, "her objective en az bir satır üretmeli"


@pytest.mark.parametrize("size", [(640, 360), (1024, 600)])
def test_objectives_hud_title_fits_long_level_name(size):
    """Seviye başlığı (uzun ad) fitted — panel sağ kenarını aşamaz."""
    mode = _make_mode(size, 1.2, [FakeObjective(SHORT_TR)])
    mode._draw_objectives_hud()
    title_rect = mode._coop_objectives_rects["title"]
    panel = mode._coop_objectives_rects["panel"]
    assert title_rect.right <= panel.right - 2, (
        f"başlık panel taşması: {title_rect} / {panel}")


# ── P0-2: Level Complete — safe rect clamp + ölçülü stat kolonları ─────────

@pytest.mark.parametrize("size", SCREEN_MATRIX)
@pytest.mark.parametrize("ui", UI_MATRIX)
def test_level_complete_panel_and_sections_inside_safe_rect(size, ui):
    """Panel safe rect'in İÇİNDE; başlık/stat/hint panelin içinde; çakışma yok."""
    mode = _make_complete_mode(size, ui, _long_objectives())
    mode._draw_level_complete()
    rec = mode._level_complete_rects
    assert rec is not None

    safe, panel = rec["safe"], rec["panel"]
    # P0-2 çekirdek değişmezi: safe.contains(panel) — eski kod ph=s(340)
    # sabitiyle %175'te ekranı taşıyordu.
    assert safe.contains(panel), (
        f"panel safe rect dışında: {panel} / safe {safe} (size={size}, ui={ui})")

    assert panel.contains(rec["title"])
    assert panel.contains(rec["stats"])

    cols = rec["stat_cols"]
    assert len(cols) == 3
    for i, col in enumerate(cols):
        # Etiket/değer kendi kolonu içinde (fitted + son çare ellipsis).
        assert col["col_rect"].contains(col["label_rect"]), (
            f"stat etiketi kolon dışına taşıyor (i={i}, size={size}, ui={ui})")
        assert col["col_rect"].contains(col["value_rect"]), (
            f"stat değeri kolon dışına taşıyor (i={i}, size={size}, ui={ui})")
        if i > 0:
            assert not cols[i - 1]["col_rect"].colliderect(col["col_rect"])

    # Katkı satırı çizildiyse panel içinde ve hint ile çakışmamalı;
    # sıkışık bütçede bilinçli olarak DÜŞÜRÜLEBİLİR (None).
    contrib = rec["contrib"]
    if contrib is not None:
        assert panel.contains(contrib)
        for hline in rec["hint_lines"]:
            assert not contrib.colliderect(hline)

    for hline in rec["hint_lines"]:
        assert panel.contains(hline), (
            f"hint satırı panel dışında: {hline} / {panel} (size={size}, ui={ui})")
        # Stat kartı ile çakışma yasağı (dikey bütçe sözleşmesi).
        assert not rec["stats"].colliderect(hline), (
            f"stat/hint çakışması (size={size}, ui={ui})")


@pytest.mark.parametrize("size", [(640, 360), (1366, 768), (1920, 1080)])
def test_level_complete_extreme_ui_175_percent_stress(size):
    """Denetim raporunun %175 gerilim senaryosu (hud 2.065) — containment."""
    mode = _make_complete_mode(size, 2.065, _long_objectives())
    mode._draw_level_complete()
    rec = mode._level_complete_rects
    assert rec["safe"].contains(rec["panel"])
    assert rec["panel"].contains(rec["title"])
    assert rec["panel"].contains(rec["stats"])


# ── P0-2: Level Failed — clamp + sarılmış görevler + çizgi işaretleri ──────

@pytest.mark.parametrize("size", SCREEN_MATRIX)
@pytest.mark.parametrize("ui", UI_MATRIX)
def test_level_failed_panel_rows_and_hint_inside_safe_rect(size, ui):
    mode = _make_failed_mode(size, ui, _long_objectives())
    mode._draw_level_failed()
    rec = mode._level_failed_rects
    assert rec is not None

    safe, panel = rec["safe"], rec["panel"]
    assert safe.contains(panel), (
        f"panel safe rect dışında: {panel} / safe {safe} (size={size}, ui={ui})")
    assert panel.contains(rec["title"])

    prev_row = None
    for row in rec["rows"]:
        assert panel.contains(row["row_rect"]), (
            f"görev satırı panel dışında: {row['row_rect']} / {panel}")
        assert panel.contains(row["icon_rect"])
        for line_rect in row["lines"]:
            assert panel.contains(line_rect)
        for hline in rec["hint_lines"]:
            assert not row["row_rect"].colliderect(hline), (
                f"görev/hint çakışması (size={size}, ui={ui})")
        if prev_row is not None:
            assert not prev_row.colliderect(row["row_rect"])
        prev_row = row["row_rect"]

    for hline in rec["hint_lines"]:
        assert panel.contains(hline)

    # Normal ölçeklerde (CoopGame clamp'i 0.72–1.20) hiçbir görev satırı
    # DÜŞMEMELİ; drop yalnız clamp dışı gerilim senaryosunda son çaredir.
    if ui <= 1.2:
        assert rec["rows_dropped"] == 0, (
            f"görev satırı düştü: {rec['rows_dropped']} (size={size}, ui={ui})")
    else:
        assert rec["rows_dropped"] >= 0
        assert len(rec["rows"]) >= 1, "en az bir görev satırı kalmalı"


@pytest.mark.parametrize("size", [(640, 360), (1920, 1080)])
def test_level_failed_marks_are_drawn_not_font_glyphs(size):
    """İkonlar draw çağrılarıyla üretilir; kayıtlar ikon rect'i taşır."""
    mode = _make_failed_mode(size, 1.0, _long_objectives())
    mode._draw_level_failed()
    rec = mode._level_failed_rects
    assert len(rec["rows"]) == 3
    for row in rec["rows"]:
        assert "icon_rect" in row
        assert isinstance(row["completed"], bool)
        assert row["icon_rect"].width >= 2  # çizgi işareti kutusu mevcut


# ── Kare-başı tahsis yasağı (FAZ A6) ───────────────────────────────────────

def test_result_overlays_and_glow_are_cached_across_frames():
    """Overlay/glow yüzeyleri iki karede AYNI nesne (kare-başı tahsis yok)."""
    mode = _make_complete_mode((1366, 768), 1.0, _long_objectives())
    mode._draw_level_complete()
    cache_after_first = dict(mode._coop_result_surface_cache)
    mode._draw_level_complete()
    cache_after_second = mode._coop_result_surface_cache

    overlay_keys = [k for k in cache_after_second if k[0] == "overlay"]
    glow_keys = [k for k in cache_after_second if k[0] == "glow"]
    assert overlay_keys, "overlay önbellek anahtarı üretilemedi"
    assert glow_keys, "glow önbellek anahtarı üretilemedi"
    for k in overlay_keys + glow_keys:
        assert cache_after_second[k] is cache_after_first[k], (
            f"kare-başı yüzey tahsisi: {k} her karede yeniden üretiliyor")


# ── Kaynak sözleşmeleri (AST-pin idyomu) ────────────────────────────────────

def _source() -> str:
    return pathlib.Path(coop_campaign_module.__file__).read_text(encoding="utf-8")


def test_source_no_dingbat_font_glyph_symbols():
    """✓/✗ (dingbat aralığı) kaynakta bulunamaz — CLAUDE.md sembol yasağı."""
    source = _source()
    for cp in range(0x2700, 0x27C0):
        assert chr(cp) not in source, f"dingbat glifi kaynakta: U+{cp:04X}"


def test_source_panel_clamp_pattern():
    """P0-2 desen kilidi: tavan (safe.width/height) → clamp(safe) → türetim."""
    source = _source()
    assert source.count("pr = pr.clamp(safe)") == 2, (
        "her iki sonuç panelinde clamp(safe) deseni bulunmalı")
    assert re.search(r"pw = min\(s\(460\), w - s\(120\), safe\.width\)", source)
    assert re.search(r"pw = min\(s\(440\), w - s\(100\), safe\.width\)", source)


def test_source_shrink_and_wrap_ladders_present():
    source = _source()
    # FAZ A6 kuantalı küçültme ladder'ı (complete ekranı dikey bütçesi).
    assert "for shrink in (1.0, 0.88, 0.76, 0.64, 0.52):" in source
    # Satır limiti ladder'ı (HUD ve failed ekranı sarma bütçesi).
    assert source.count("for max_lines in (3, 2, 1):") == 2
    # Sarma + son çare ellipsis yolu.
    assert source.count("wrap_text_limited(") >= 4
    assert "_fit_or_ellipsize(" in source


def test_source_per_frame_overlay_loop_removed():
    """Eski h-satırlık gradient döngüsü DRAW gövdelerinden kalktı.

    Döngü _coop_result_overlay CACHE ÜRETİCİSİNDE kalabilir — orada yalnız
    (w,h) başına bir kez çalışır, kare başına değil (FAZ A6 sözleşmesi:
    kare-başı tahsis yok; size-başı üretim + LRU serbest).
    """
    source = _source()
    assert "self._coop_result_overlay(" in source
    for fn_name in ("def _draw_level_complete", "def _draw_level_failed"):
        start = source.index(fn_name)
        end = source.index("\n    def ", start + 10)
        body = source[start:end]
        assert "for row in range(h):" not in body, (
            f"{fn_name} gövdesinde kare-başı gradient döngüsü hâlâ var")
        assert "pygame.Surface((w, h), pygame.SRCALPHA)" not in body
    # Tek-surface glow modülasyonu (set_alpha restore ile).
    assert source.count("title_surf.set_alpha(255)") == 2


def test_source_rect_records_exposed():
    source = _source()
    for attr in ("_coop_objectives_rects", "_level_complete_rects",
                 "_level_failed_rects"):
        assert attr in source, f"rect kaydı eksik: {attr}"


def test_source_failed_screen_draws_marks_with_lines():
    """failed ekranı ikonları pygame.draw.line/circle ile üretir."""
    source = _source()
    fn = source[source.index("def _draw_level_failed"):source.index("def _draw_star")]
    assert "pygame.draw.circle(" in fn
    assert "pygame.draw.line(" in fn
    assert "pygame.draw.lines(" in fn  # tik (check) işareti
