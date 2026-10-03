# -*- coding: utf-8 -*-
"""P1-1: Hardcore sağ HUD stat satırları ölç-önce plan sözleşmesi.

Kılavuz: Quadrix_Tum_Ekranlar_Olcekleme_Denetim_Raporu.md (P1-1).
Eski yerel draw_stat (game_modes.py HardcoreMode._draw_right_hud_panel)
ölçüm yapmadan etiketi soldan, değeri sağdan çiziyordu; uzun Türkçe/İngilizce
etiket + büyük skor + yüksek preset kombinasyonunda orta bölgede üst üste
biniyordu. Düzeltme: satırlar ortak Game._fit_hud_stat_row planlayıcısıyla
planlanır (game.py stats bloğu ile aynı ölçüm/floor kuralları), dikey bütçe
için üniform küçültme basamağı uygulanır, gerçek blit rect'leri
`_hardcore_hud_rects` altında kayda geçer.

Hardcore panelinde tüm satırlar (skor/satır/seviye) ZORUNLUDUR —
düşürülecek opsiyonel satır yoktur (game.py'deki combo/tetris muadili).

Ölçüm sınırı (dürüst rapor): gerçek 4K görsel doğrulama rapor §11'deki
manuel Windows smoke'a aittir — dummy driver altında koşulmaz. Bu dosya
plan sözleşmesini (değişmezler) ve kaynak sözleşmesini kilitler.

Kalıp: test_wide_arena_hud_scale_containment.py (SRC yol hazırlığı +
dummy sürücüler + gerçek modül importu; bare-instance idyomu).
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

from game_modes import HardcoreMode
from types import SimpleNamespace

if not pygame.font.get_init():
    pygame.font.init()


# ── Hardcore panel ölçüleri (kaynak: _draw_right_hud_panel) ─────────────────
# Panel ~s(180)-s(220) genişlik, content_w = panel_width - s(30); stat satırı
# pad'i s(15). Plan düzeyi bu gerçek bütçelerle sınanır.
HARDCORE_PLAN_KW = {"bold_label": False}  # Hardcore etiketi bold DEĞİLDİR


def _retro_style_stub_leaked() -> bool:
    """Bilinen harness izolasyon kirliliği: önceki test dosyaları game.py
    global `retro_style`'ını veya sys.modules['retro_style']'ı _FakeFont
    tabanlı stub'la değiştirebiliyor (denetim raporu §10 — çift modül
    kimliği; altyapı düzeltmesi ayrı iştir). Bu dosya ürün kodunu değil,
    kendi test dayanıklılığını korur: sızıntı varsa font/draw testleri
    gerekçeli skip edilir; temiz koşumda tam koşar.

    İki erişim yolu ayrı denetlenir: planlayıcı game.py global'ini,
    _draw_right_hud_panel içindeki yerel import sys.modules'u okur.
    """
    import game as game_module

    candidates = []
    game_rs = getattr(game_module, 'retro_style', None)
    if game_rs is not None:
        candidates.append(game_rs)
    rs_module = sys.modules.get('retro_style')
    if rs_module is not None:
        candidates.append(getattr(rs_module, 'retro_style', rs_module))
    if not candidates:
        return True
    for rs in candidates:
        try:
            probe = rs.get_font(16)
        except Exception:
            return True
        if not isinstance(probe, pygame.font.Font):
            return True
    return False


def _skip_if_stub_leaked():
    if _retro_style_stub_leaked():
        pytest.skip("retro_style stub sızıntısı — bilinen harness izolasyon sorunu (rapor §10)")


def _make_mode() -> HardcoreMode:
    """Bare HardcoreMode: _fit_hud_stat_row yalnız statik yardımcıları kullanır."""
    return HardcoreMode.__new__(HardcoreMode)


@pytest.mark.parametrize(
    "content_w,hud",
    [
        (240, 1.0),
        (240, 1.16),          # Hardcore overlay üst clamp'i (0.70-1.16)
        (160, 1.0),
        (133, 0.70),          # 640x360 gerçek content_w ölçümü
        (96, 1.16),
        (64, 1.0),
        (192, 2.065),         # rapor senaryosu: %175 preset ölçek kombinasyonu
        (192, 2.36),          # %200
        (160, 2.065),
        (64, 2.065),
    ],
)
@pytest.mark.parametrize(
    "label,value",
    [
        ("SKOR", "9.999.999"),
        ("SCORE", "12.345.678"),
        ("SATIR", "1234"),
        ("SEVİYE", "99"),
    ],
)
def test_stat_row_never_overlaps_label_and_value(content_w, hud, label, value):
    """Çekirdek değişmezi: yatay satırda etiket+boşluk+değer daima sığar.

    Eski draw_stat ölçmediği için uzun etiket soldan, büyük değer sağdan
    çizilip ORTADA üst üste biniyordu. Yeni plan ya sığan bir yatay satır
    üretir (l_w + row_gap + v_w <= avail_w) ya da vertical=True olur —
    ikisi arası (yarı çakışan yatay satır) asla üretilmez.
    """
    mode = _make_mode()
    _skip_if_stub_leaked()
    plan = mode._fit_hud_stat_row(label, value, content_w, hud, **HARDCORE_PLAN_KW)

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


@pytest.mark.parametrize(
    "content_w,hud",
    [
        (160, 1.0),
        (133, 0.70),
        (96, 1.16),
        (64, 1.0),
        (64, 2.065),
    ],
)
@pytest.mark.parametrize(
    "label,value",
    [
        ("ANTİVİRÜS SÜRESİ", "9.999.999"),
        ("VİRÜS SEVİYESİ", "12345"),
        ("TÜKETİLEN BLOKLAR", "1234"),
        ("CONSUMED BLOCKS", "12.345.678"),
    ],
)
def test_stat_row_long_labels_shared_planner_contract(content_w, hud, label, value):
    """Uzun etiketler: paylaşılan planlayıcı sözleşmesi (game.py ile aynı).

    Yatay modda satır toplamı daima sığar; dikey modda DEĞER daima sığar.
    NOT: paylaşılan planlayıcı dikey modda etiketi ellipsis'lemez — aşırı dar
    bütçede etiket genişliği avail_w'yi aşabilir (game.py'nin bilinen kenar
    durumu; game.py bu görevde dokunulmaz). Hardcore draw yolu bunu
    draw-zamanı _ellipsis_text guard'ı ile kapatır (aşağıdaki draw testleri).
    """
    mode = _make_mode()
    _skip_if_stub_leaked()
    plan = mode._fit_hud_stat_row(label, value, content_w, hud, **HARDCORE_PLAN_KW)

    if not plan['vertical']:
        total = plan['label_w'] + plan['row_gap'] + plan['value_w']
        assert total <= plan['avail_w']
    else:
        assert plan['value_w'] <= plan['avail_w']


def test_stat_row_vertical_fallback_when_floor_fonts_do_not_fit():
    """Taban fontlarda bile sığmayan satır kontrollü dikey yerleşime düşer."""
    mode = _make_mode()
    _skip_if_stub_leaked()
    plan = mode._fit_hud_stat_row("SEVİYE", "999.999", 60, 1.16, **HARDCORE_PLAN_KW)

    assert plan['vertical'] is True
    assert plan['value_w'] <= plan['avail_w']
    assert plan['label_w'] <= plan['avail_w']


def test_stat_row_ellipsis_is_last_resort_only():
    """Ellipsis yalnız dikey yerleşimde DEĞER taşarsa uygulanır; ASCII kalır."""
    mode = _make_mode()
    _skip_if_stub_leaked()
    original = "123.456.789"
    plan = mode._fit_hud_stat_row("SKOR", original, 48, 1.16, **HARDCORE_PLAN_KW)

    assert plan['value_w'] <= plan['avail_w']
    if plan['value_text'] != original:
        assert plan['value_text'].endswith("...")
        assert len(plan['value_text']) < len(original)
        # ASCII '...' (emoji yok — CLAUDE.md).
        assert all(ord(ch) < 128 for ch in plan['value_text'])


def test_stat_row_plan_is_cache_friendly_and_allocation_free():
    """Plan aşaması Surface ÜRETMEZ; tekrar çağrı aynı font NESNESİNİ verir.

    Kare-başı tahsis yasağı (CLAUDE.md): ölçümler measure_text_width LRU'dan
    okunur, fontlar retro_style font_cache'ten; küçültme oranları 0.05
    adımlarla kuantalandığından font boyutu seti sınırlı kalır.
    """
    mode = _make_mode()
    _skip_if_stub_leaked()
    plan_a = mode._fit_hud_stat_row("SKOR", "9.999.999", 133, 1.0, **HARDCORE_PLAN_KW)
    plan_b = mode._fit_hud_stat_row("SKOR", "9.999.999", 133, 1.0, **HARDCORE_PLAN_KW)

    for value in plan_a.values():
        assert not isinstance(value, pygame.Surface), "plan aşaması Surface üretmemeli"
    assert plan_a['label_font'] is plan_b['label_font']
    assert plan_a['value_font'] is plan_b['value_font']


def test_stat_row_hardcore_label_font_is_not_bold():
    """Hardcore etiketi mevcut görünümde bold DEĞİLDİR (parite koruması)."""
    mode = _make_mode()
    _skip_if_stub_leaked()
    plan = mode._fit_hud_stat_row("SKOR", "123", 240, 1.0, **HARDCORE_PLAN_KW)
    # retro_style.get_font bold=False → get_bold() False döner.
    assert not plan['label_font'].get_bold()


# ── Draw düzeyi: gerçek blit rect kaydı ─────────────────────────────────────


def _make_draw_mode(size: tuple[int, int], *, score: int = 9999999, lines: int = 123, level: int = 99) -> HardcoreMode:
    mode = HardcoreMode.__new__(HardcoreMode)
    mode.screen = pygame.Surface(size)
    mode.board = SimpleNamespace(score=score, lines_cleared=lines, level=level)
    return mode


@pytest.mark.parametrize(
    "size",
    [
        (640, 360),
        (800, 480),
        (1024, 600),
        (1280, 720),
        (1366, 768),   # referans: görünüm paritesi
        (1920, 1080),
        (3840, 2160),
    ],
)
def test_hardcore_hud_records_rects_and_rows_never_overlap(size):
    """Draw sonrası _hardcore_hud_rects: satırlar çakışmaz, panel ekranda kalır."""
    _skip_if_stub_leaked()
    mode = _make_draw_mode(size)
    mode._draw_right_hud_panel(0, 10, 300, size[1] - 40, None, None, (255, 255, 255), (255, 50, 50), (180, 150, 150))

    rec = getattr(mode, '_hardcore_hud_rects', None)
    assert rec is not None, "_hardcore_hud_rects kaydı yok (P1-1 sözleşmesi)"
    for key in ('panel', 'stats', 'content_x', 'content_w', 'rows_bottom_cap', 'rows_avail', 'rows'):
        assert key in rec, f"kayıt anahtarı eksik: {key}"

    screen_w, screen_h = size
    assert 0 < rec['panel'].width and rec['panel'].right <= screen_w
    assert rec['panel'].bottom <= screen_h

    assert len(rec['rows']) == 3, "Hardcore'ta 3 zorunlu satır (skor/satır/seviye) çizilmeli"
    for row in rec['rows']:
        assert not row['label_rect'].colliderect(row['value_rect']), (
            f"etiket-değer çakışması: {row['label']} label={row['label_rect']} "
            f"value={row['value_rect']} (size={size})"
        )
        # Satır blokları stats içerik sınırları içinde (etiket draw guard'ı
        # ile taşmaz — paylaşılan planlayıcı kenar durumuna karşı).
        assert row['label_rect'].left >= rec['stats'].left
        assert row['label_rect'].right <= rec['stats'].right + 1
        assert row['value_rect'].right <= rec['stats'].right + 1

    # Dikey bütçe: ladder sığdıysa (toplam row_h <= rows_avail) tüm satır
    # blokları cap içinde kalmalı. Hardcore'ta tüm satırlar zorunlu olduğundan
    # degenerate bütçede satır düşürme yoktur — çakışmazlık her koşulda geçerli.
    total_h = sum(row['row_h'] for row in rec['rows'])
    if total_h <= rec['rows_avail']:
        for row in rec['rows']:
            assert row['value_rect'].bottom <= rec['rows_bottom_cap'] + 1, (
                f"satır cap aşımı: {row['label_rect']} / {row['value_rect']} "
                f"cap={rec['rows_bottom_cap']}"
            )


def test_hardcore_hud_high_preset_stays_plan_safe():
    """%175/%200 preset: overlay ölçeği 0.70-1.16 clamp'lense de ölç-önce
    plan tüm preset kombinasyonlarında çakışma üretmez (rapor P1-1 senaryosu)."""
    from ui_scaling import get_ui_scale_preset, set_ui_scale_preset

    _skip_if_stub_leaked()
    previous = get_ui_scale_preset()
    try:
        for preset in ("large", "massive", "double"):
            set_ui_scale_preset(preset)
            for size in ((1920, 1080), (3840, 2160)):
                mode = _make_draw_mode(size)
                mode._draw_right_hud_panel(0, 10, 300, size[1] - 40, None, None, (255, 255, 255), (255, 50, 50), (180, 150, 150))
                rec = mode._hardcore_hud_rects
                for row in rec['rows']:
                    assert not row['label_rect'].colliderect(row['value_rect']), (
                        f"{preset} preset çakışması: {row['label']} "
                        f"label={row['label_rect']} value={row['value_rect']}"
                    )
    finally:
        set_ui_scale_preset(previous)


def test_hardcore_hud_long_labels_draw_guard(monkeypatch):
    """Uzun lokalizasyon etiketleri draw yolunda: çakışma ve taşma yok.

    Paylaşılan planlayıcı dikey modda etiketi kısaltmaz; Hardcore draw yolu
    draw-zamanı _ellipsis_text guard'ı ile etiketi içerik genişliğine sığdırır.
    Bu test guard'ı uzun etiket + dar panel kombinasyonunda kanıtlar.
    """
    import game_modes as game_modes_module

    _skip_if_stub_leaked()
    long_labels = {
        'score': "ANTİVİRÜS SÜRESİ KALDIRIÇI",
        'lines': "TÜKETİLEN BLOKLAR",
        'level': "VİRÜS SEVİYESİ GÖSTERGESİ",
    }
    monkeypatch.setattr(game_modes_module, 't', lambda key, *a, **k: long_labels.get(key, key))

    for size in ((640, 360), (800, 480)):
        mode = _make_draw_mode(size)
        mode._draw_right_hud_panel(0, 10, 300, size[1] - 40, None, None, (255, 255, 255), (255, 50, 50), (180, 150, 150))
        rec = mode._hardcore_hud_rects
        for row in rec['rows']:
            assert not row['label_rect'].colliderect(row['value_rect']), (
                f"uzun etiket çakışması: label={row['label_rect']} value={row['value_rect']}"
            )
            assert row['label_rect'].right <= rec['stats'].right + 1, (
                f"etiket taşması: {row['label_rect']} stats={rec['stats']}"
            )
            assert row['value_rect'].right <= rec['stats'].right + 1


# ── Kaynak sözleşmeleri (AST-pin idyomu) ────────────────────────────────────


def _game_modes_source() -> str:
    import game_modes as game_modes_module
    return pathlib.Path(game_modes_module.__file__).read_text(encoding='utf-8')


def _hardcore_panel_body(source: str) -> str:
    start = source.index("def _draw_right_hud_panel")
    # Metodun bitişi: bir sonraki aynı-indent def
    next_def = re.search(r"\n    def ", source[start + 10:])
    end = start + 10 + next_def.start() if next_def else len(source)
    return source[start:end]


def test_hardcore_draw_stat_uses_shared_planner():
    source = _game_modes_source()
    body = _hardcore_panel_body(source)
    assert "self._fit_hud_stat_row(" in body, "Hardcore draw_stat ortak planlayıcıyı kullanmıyor"
    # game.py ile aynı shrink ladder (üniform küçültme basamakları).
    assert re.search(r"for shrink in \(1\.0, 0\.88, 0\.76, 0\.64, 0\.52\):", body)
    # Etiket bold değil (mevcut Hardcore görünümü korunur).
    assert "bold_label=False" in body
    # Rect kaydı (containment testleri için).
    assert "_hardcore_hud_rects" in body


def test_hardcore_planning_section_is_measure_only():
    """Plan üretim bölümünde .render( çağrısı olmamalı (ölçüm LRU'dan)."""
    source = _game_modes_source()
    body = _hardcore_panel_body(source)
    start = body.index("stat_y = curr_y + s(15)")
    end = body.index("def draw_stat", start)
    planning = body[start:end]
    assert "self._fit_hud_stat_row(" in planning
    assert ".render(" not in planning


def test_hardcore_old_unmeasured_draw_stat_pattern_removed():
    """Eski ölçümsüz desen (sabit font + karşılıklı çizim) kayboldu."""
    source = _game_modes_source()
    body = _hardcore_panel_body(source)
    assert "retro_style.get_font(s(16, minimum=10)).render" not in body
    assert "retro_style.get_font(s(24, minimum=14), bold=True).render" not in body
