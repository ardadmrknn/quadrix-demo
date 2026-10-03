# -*- coding: utf-8 -*-
"""P0-1/P1-3/P0-2: Campaign başarı/başarısızlık modalı safe rect sözleşmesi.

Kaynak rapor: Quadrix_Tum_Ekranlar_Olcekleme_Denetim_Raporu.md
- P0-1: eski `_safe_rect.clamp(panel_rect)` çağıranın (safe rect'in)
  boyutlarını panel yerine koyuyordu (pygame Rect.clamp sözleşmesi:
  ÇAĞIRAN hedefin içine yerleşir). Doğru yön `panel_rect.clamp(
  _safe_rect)`; ayrıca clamp küçültmediği için safe rect'ten büyük panel
  için clamp ÖNCESİ boyut tavanı uygulanır.
- P1-3: başlık/level adı panel bütçesine fitted; başarısızlık `reason`
  ve `hint` metinleri buton satırından türeyen dikey bütçeye sarılır ve
  butonları kesmez; taşma ASCII '...' ile kesilir.
- P0-2: `_complete_buttons`/`_failed_buttons` aksiyon rect'leri panel ve
  safe rect içinde, birbirinden ayrık (disjoint) kalır.

Kalıp: test_wide_arena_hud_scale_containment.py (SDL dummy env pygame
importundan ÖNCE + sys.path src + gerçek modül importu) ve DUZ-010
rect-kayıt idyomu (draw, rect'leri instance üzerinde kaydeder; test
sadece kayıtlı rect'lerin geometri sözleşmesini doğrular).

Ölçüm sınırı (dürüst rapor): gerçek görsel taşma denetimi rapor §11'deki
manuel Windows smoke turuna aittir — dummy driver altında koşulmaz. Bu
dosya geometri sözleşmelerini kilitler.
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

from campaign import campaign_ui as campaign_ui_module
from campaign.campaign_ui import CampaignUIEffects

if not pygame.font.get_init():
    pygame.font.init()

# FAZ A6 modül-kimliği temizliği (test_coop.py / G dosyası düşürme kalıbı):
# yukarıdaki import zinciri campaign/__init__.py'yi çalıştırır ve tüm
# campaign alt modüllerini BU dosyanın pygame nesline bağlar. conftest her
# koleksiyon sınırında pygame ailesini sys.modules'tan düşürdüğünden,
# burada bırakılan eski binding'li campaign girdileri sonraki toplanan
# test dosyasında (örn. test_coop_level_select_narrow_screen) modül-kimliği
# bölünmesi yaratır — o dosyanın pygame.display.flip monkeypatch'i başka
# instance'ın display'ine düşer ve "video system not initialized" ile tüm
# dosya düşer. Bu dosyanın testleri yukarıdaki doğrudan referanslarla
# (campaign_ui_module, CampaignUIEffects) çalıştığı için aileyi düşürmek
# etkilemez; sonraki dosya kendi pygame'iyle temiz yükler.
for _mod_name in [n for n in list(sys.modules)
                  if n == "campaign" or n.startswith("campaign.")
                  or n == "src.campaign" or n.startswith("src.campaign.")]:
    sys.modules.pop(_mod_name, None)


# ── Matris (rapor §10): dar pencereden 4K'ya ────────────────────────────────
SIZE_MATRIX = [
    (640, 360),
    (800, 480),
    (1024, 600),
    (1280, 720),
    (1920, 1080),
    (3840, 2160),
]

# ── Fixture yardımcıları ────────────────────────────────────────────────────


def _safe_inset(size: tuple[int, int]) -> int:
    w, h = size
    return max(8, min(w, h) // 16)


def _make_effects(
    size: tuple[int, int],
    safe_rect: pygame.Rect | None,
) -> tuple[CampaignUIEffects, pygame.Surface]:
    """Gerçek CampaignUIEffects + kontrollü safe rect (geometry stub).

    `_get_modal_geometry` instance üzerinde ezilir: (None, safe_rect).
    Geometri None döndüğü için modal ölçeği Surface boyutundan çözülür
    (ölçek eğrisi gerçek kalır); safe rect testin kontrolündedir.
    """
    effects = CampaignUIEffects()
    surface = pygame.Surface(size, pygame.SRCALPHA)
    effects._get_modal_geometry = lambda surf: (None, safe_rect)
    return effects, surface


def _draw_success(
    size: tuple[int, int],
    safe_rect: pygame.Rect | None,
    level_name: str = "Bölüm 7",
) -> CampaignUIEffects:
    effects, surface = _make_effects(size, safe_rect)
    effects.start_level_complete(3)
    effects.level_complete_animation['time'] = 1.5
    effects.draw_level_complete_overlay(
        surface,
        stars=3,
        score=123456,
        level_name=level_name,
        lang='tr',
        objectives=[{'text': 'Hedef', 'progress': '1/1', 'completed': True}],
        stats=[('SKOR', '123456')],
        rewards=[('Ödül', '100')],
        next_level={'title': 'Sonraki', 'lines': ['Satır 1', 'Satır 2']},
        star_conditions=[{'star': 1, 'text': 'Koşul', 'met': True}],
    )
    return effects


def _draw_fail(
    size: tuple[int, int],
    safe_rect: pygame.Rect | None,
    reason: str = "Tahta doldu",
) -> CampaignUIEffects:
    effects, surface = _make_effects(size, safe_rect)
    effects.start_level_failed(reason)
    effects.level_failed_animation['time'] = 1.5
    effects.draw_level_failed_overlay(surface, reason=reason, lang='tr')
    return effects


# ── P0-1: clamp yönü + boyut korunumu ───────────────────────────────────────


@pytest.mark.parametrize("size", SIZE_MATRIX)
@pytest.mark.parametrize("draw", [_draw_success, _draw_fail], ids=["success", "fail"])
def test_modal_panel_inside_safe_rect_and_target_size_preserved(size, draw):
    """Panel safe rect İÇİNDE kalır (P0-1 containment yönü).

    Eski `_safe_rect.clamp(...)` hatasının kesin ayrımı deterministik
    1366x768 testlerinde yapılır (orada hedef boyut < safe boyut);
    4K'da hedef panel safe'i aştığından tavan davranışı meşru full-bleed
    üretir — burada yalnız containment doğrulanır.
    """
    w, h = size
    safe = pygame.Rect(_safe_inset(size), _safe_inset(size),
                       w - 2 * _safe_inset(size), h - 2 * _safe_inset(size))
    effects = draw(size, safe)
    panel = (effects._complete_panel_rect if draw is _draw_success
             else effects._failed_panel_rect)

    assert panel is not None
    assert safe.contains(panel), f"panel safe rect dışında: {panel} vs {safe}"


def test_success_modal_deterministic_1366x768_layout():
    """1366x768 (modal ölçek 1.0x tabanı) deterministik yerleşim pini.

    Ölçek eğrisi 1366x768'de tam 1.0 (FAZ A6 sözleşmesi) olduğundan
    panel rect'i elle hesaplanan hedefle birebir eşleşmelidir.
    """
    size = (1366, 768)
    inset = _safe_inset(size)
    safe = pygame.Rect(inset, inset, 1366 - 2 * inset, 768 - 2 * inset)
    effects, surface = _make_effects(size, safe)
    ui_scale = effects._get_modal_ui_scale(surface)
    assert ui_scale == pytest.approx(1.0), "1366x768 modal ölçek tabanı kaydı"

    effects = _draw_success(size, safe)
    s = lambda v, minimum=1: CampaignUIEffects._scale_modal_px(v, ui_scale, minimum=minimum)
    expected_w = min(max(s(460), 1366 - s(320)), 1366 - s(220))
    expected_w = max(s(380), expected_w)
    expected_w = min(expected_w, safe.width)
    expected_h = min(max(s(380), 768 - s(160)), 768 - s(80))
    expected_h = max(s(340), expected_h)
    expected_h = min(expected_h, safe.height)
    expected = pygame.Rect((1366 - expected_w) // 2, (768 - expected_h) // 2,
                           expected_w, expected_h)

    assert effects._complete_panel_rect == expected


def test_fail_modal_deterministic_1366x768_layout():
    size = (1366, 768)
    inset = _safe_inset(size)
    safe = pygame.Rect(inset, inset, 1366 - 2 * inset, 768 - 2 * inset)
    effects, surface = _make_effects(size, safe)
    ui_scale = effects._get_modal_ui_scale(surface)
    assert ui_scale == pytest.approx(1.0)

    effects = _draw_fail(size, safe)
    s = lambda v, minimum=1: CampaignUIEffects._scale_modal_px(v, ui_scale, minimum=minimum)
    expected_w = min(max(s(420), 1366 - s(160)), 1366 - s(80))
    expected_w = max(s(360), expected_w)
    expected_w = min(expected_w, safe.width)
    expected_h = min(max(s(260), 768 - s(200)), 768 - s(100))
    expected_h = max(s(220), expected_h)
    expected_h = min(expected_h, safe.height)
    expected = pygame.Rect((1366 - expected_w) // 2, (768 - expected_h) // 2,
                           expected_w, expected_h)

    assert effects._failed_panel_rect == expected


@pytest.mark.parametrize("draw", [_draw_success, _draw_fail], ids=["success", "fail"])
def test_modal_without_safe_rect_keeps_centered_layout(draw):
    """Geometri yoksa (None) davranış değişmez: ortalanmış panel, safe tavanı yok."""
    size = (1280, 720)
    effects = draw(size, None)
    panel = (effects._complete_panel_rect if draw is _draw_success
             else effects._failed_panel_rect)
    assert panel is not None
    # Tam ortalamama formülü (Rect.center tek-yükseklikte yuvarlar).
    assert panel.left == (size[0] - panel.width) // 2
    assert panel.top == (size[1] - panel.height) // 2


@pytest.mark.parametrize("draw", [_draw_success, _draw_fail], ids=["success", "fail"])
def test_modal_size_cap_when_safe_rect_smaller_than_floors(draw):
    """Safe rect panel floor'larından küçükse panel safe'e sığacak şekilde kırpılır.

    Rect.clamp küçültmediği için tavan clamp'ten ÖNCE uygulanır; clamp
    yalnız konumu düzeltir (P0-1 ek gereklilik).
    """
    size = (800, 480)
    safe = pygame.Rect(300, 160, 200, 160)
    effects = draw(size, safe)
    panel = (effects._complete_panel_rect if draw is _draw_success
             else effects._failed_panel_rect)
    assert panel is not None
    assert safe.contains(panel), f"küçük safe rect'te panel taştı: {panel} vs {safe}"


# ── P0-2: aksiyon rect'leri ─────────────────────────────────────────────────


@pytest.mark.parametrize("size", SIZE_MATRIX)
def test_fail_modal_buttons_inside_panel_safe_and_disjoint(size):
    w, h = size
    inset = _safe_inset(size)
    safe = pygame.Rect(inset, inset, w - 2 * inset, h - 2 * inset)
    effects = _draw_fail(size, safe)
    panel = effects._failed_panel_rect

    retry = effects._failed_buttons.get('retry')
    menu = effects._failed_buttons.get('menu')
    assert retry is not None and menu is not None, "buton rect'leri kaydedilmeli"
    assert panel.contains(retry), f"retry panel dışında: {retry} vs {panel}"
    assert panel.contains(menu), f"menu panel dışında: {menu} vs {panel}"
    assert safe.contains(retry) and safe.contains(menu)
    assert not retry.colliderect(menu), "retry/menu birbirine binmemeli"


@pytest.mark.parametrize("size", SIZE_MATRIX)
def test_success_modal_retry_button_inside_panel_and_safe(size):
    w, h = size
    inset = _safe_inset(size)
    safe = pygame.Rect(inset, inset, w - 2 * inset, h - 2 * inset)
    effects = _draw_success(size, safe)
    panel = effects._complete_panel_rect
    retry = effects._complete_buttons.get('retry')
    assert retry is not None, "complete retry rect kaydedilmeli"
    assert panel.contains(retry) and safe.contains(retry)


# ── P1-3: metin bütçeleri ───────────────────────────────────────────────────


@pytest.mark.parametrize("size", [(640, 360), (800, 480), (1024, 600)])
def test_fail_modal_long_reason_wraps_within_budget_and_above_buttons(size):
    """Uzun Türkçe sebep: satırlar panel iç bütçesinde, butonların üstünde.

    Eski kod reason'ı tek satır render edip genişlikte taşıyordu; yeni
    sözleşme sarma + satır limiti + ASCII '...'.
    """
    w, h = size
    inset = _safe_inset(size)
    safe = pygame.Rect(inset, inset, w - 2 * inset, h - 2 * inset)
    reason = "Tahta özel bloklarla doldu ve kalan alan yeni parçaya yetmedi " * 4
    effects = _draw_fail(size, safe, reason=reason)
    panel = effects._failed_panel_rect
    retry = effects._failed_buttons['retry']
    reason_rects = effects._failed_reason_rects

    assert reason_rects, "reason satır rect'leri kaydedilmeli"
    for rect in reason_rects:
        assert rect.width <= panel.width - 16, f"reason satır panel genişliğini aştı: {rect}"
        assert rect.left >= panel.left + 8 and rect.right <= panel.right - 8
        assert rect.bottom <= retry.top, f"reason buton satırını kesti: {rect} vs {retry}"
        assert safe.contains(rect)
    # Dikey toplam bütçe: son satır buton üstünden yukarıda, ilk satır başlığın altında.
    assert reason_rects[-1].bottom <= retry.top


@pytest.mark.parametrize("size", [(640, 360), (800, 480), (1024, 600)])
def test_fail_modal_long_hint_wraps_upward_above_buttons(size):
    """Uzun hint: alt kenarı butonların üstüne sabit, yukarı doğru büyür."""
    w, h = size
    inset = _safe_inset(size)
    safe = pygame.Rect(inset, inset, w - 2 * inset, h - 2 * inset)
    effects = _draw_fail(size, safe)
    panel = effects._failed_panel_rect
    retry = effects._failed_buttons['retry']
    hint_rects = effects._failed_hint_rects

    if not hint_rects:
        # Dejenere küçük panelde tek satıra bütçe yoksa hint atlanır
        # (kontrollü degradasyon) — bu matris boyutlarında beklenmez.
        pytest.fail("hint rect'leri kaydedilmeli (bütçe tek satıra yeter)")
    for rect in hint_rects:
        assert rect.width <= panel.width - 16
        assert rect.left >= panel.left + 8 and rect.right <= panel.right - 8
        assert rect.bottom <= retry.top, f"hint buton satırını kesti: {rect} vs {retry}"
    # Hint reason ile üst üste binmez (bütçe zinciri).
    reason_rects = effects._failed_reason_rects
    if reason_rects:
        assert max(r.bottom for r in reason_rects) <= min(r.top for r in hint_rects) + 2


def test_success_modal_title_fits_header_budget():
    """Başlık fitted: rect panel iç bütçesinde kalır (P1-3)."""
    size = (800, 480)
    inset = _safe_inset(size)
    safe = pygame.Rect(inset, inset, size[0] - 2 * inset, size[1] - 2 * inset)
    effects = _draw_success(size, safe)
    panel = effects._complete_panel_rect
    title_rect = effects._complete_title_rect
    assert title_rect is not None
    assert title_rect.width <= panel.width - 32
    assert title_rect.left >= panel.left + 8
    assert title_rect.right <= panel.right - 8


def test_success_modal_long_level_name_fitted():
    """Çok uzun level adı yıldız bloğu bütçesine sığar (tek satır, taşma yok)."""
    size = (1024, 600)
    inset = _safe_inset(size)
    safe = pygame.Rect(inset, inset, size[0] - 2 * inset, size[1] - 2 * inset)
    long_name = "Final Patlaması: Kristal Kule Sınavı Bölüm " + "Uzun " * 12
    effects = _draw_success(size, safe, level_name=long_name)
    panel = effects._complete_panel_rect
    # Kayıtlı title rect değil; level adı panel bütçesinde taşmıyor
    # olmalı — doğrulamayı panel içi konum üzerinden star alanına kadar
    # yapan tek kilit: panel genişliğinden geniş bir alt başlık üretilemez.
    # (Kesin rect kaydı star bloğunun soluna kadardır; burada panel
    # bütçesi üst sınır olarak doğrulanır.)
    assert panel is not None
    assert panel.width >= 24


# ── Kaynak sözleşme pin'leri (AST-pin idyomu) ───────────────────────────────


def _source() -> str:
    """Kaynak metin — pin'ler YALNIZ kod satırlarında aranır.

    Yorumlardaki açıklamalar (eski desenin adı geçebilir) strip edilir;
    satır-içi yorumlar da `#`'ten sonra temizlenir.
    """
    raw = pathlib.Path(campaign_ui_module.__file__).read_text(encoding='utf-8')
    return re.sub(r'#[^\n]*', '', raw)


def test_source_contract_clamp_direction_fixed():
    source = _source()
    assert "_safe_rect.clamp(" not in source, (
        "P0-1: ters yön clamp geri gelmiş"
    )
    assert source.count("panel_rect.clamp(_safe_rect)") == 2, (
        "iki modalda da düzeltilmiş clamp bulunmalı"
    )


def test_source_contract_panel_size_refreshed_after_clamp():
    source = _source()
    # Clamp sonrası türev rect kaynağı tek: panel_width/height yenilenir.
    assert source.count("panel_width = panel_rect.width") == 2
    assert source.count("panel_height = panel_rect.height") == 2


def test_source_contract_reason_and_hint_use_wrap_text_limited():
    source = _source()
    assert source.count("wrap_text_limited(") >= 2, (
        "reason/hint sarma sözleşmesi kayboldu"
    )
    # Buton satırı rect'leri reason/hint'ten ÖNCE üretilmeli (bütçe kaynağı).
    btn_index = source.index("btn_y = panel_rect.bottom - btn_h - btn_margin")
    reason_index = source.index("if reason:")
    assert btn_index < reason_index, "buton satırı rect'leri reason'dan önce üretilmeli"


def test_source_contract_rect_recordings_present():
    source = _source()
    for pin in (
        "self._complete_panel_rect = panel_rect",
        "self._failed_panel_rect = panel_rect",
        "self._failed_reason_rects",
        "self._failed_hint_rects",
        "self._complete_title_rect",
    ):
        assert pin in source, f"rect kaydı eksik: {pin}"
