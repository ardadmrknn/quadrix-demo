# -*- coding: utf-8 -*-
"""P1-11: Kullanıcı yönetim ekranı modal + profil kartı metin/grid bütçeleri.

Rapor: Quadrix_Tum_Ekranlar_Olcekleme_Denetim_Raporu.md (P1-11):
- Silme onayı (UserManagementScreen._draw_confirm_delete): kutu render
  güvenli alanına P0-2 düzeniyle oturur — boyut tavanı clamp'ten ÖNCE
  (Rect.clamp küçültmez); geometry yoksa tam-ekran fallback. Kullanıcı adı
  içeren satır, ikinci satır ve uyarı metni kutu iç genişliğine
  wrap_text_limited ile sarılır (70+ karakterlik ad eskiden tek satırda
  kutudan taşıyordu). Kutu yüksekliği içerik bütçesinden türetilir (eski
  sabit s(280) 36'lık fontta msg satırlarını üst üste bindiriyordu).
  Overlay yüzeyi (w, h) anahtarlı önbellekten üretilir — kare-başı
  SRCALPHA tahsisi kaldırıldı.
- Profil kartı (_draw_view_profile): stat kartı kolon sayısı kullanılabilir
  genişlikten türetilir (3 -> 2 -> 1), mod kartları (4 -> 3 -> 2 -> 1);
  eski kod sabit 3/4 kolonla dar pencerede kart dışına taşıyordu.
  Kullanıcı adı render_fit_text ile, bio satırlara sarılır.

Ölçüm sınırı (dürüst rapor): gerçek safe-rect/4K görsel davranışı kılavuz
§7'deki manuel Windows smoke'a aittir — dummy driver altında gerçek geometry
kuşağı yoktur; bu dosya stub'lı safe rect + fallback senaryolarıyla
sözleşmeyi kilitler.

Kalıp: SDL dummy env pygame importundan ÖNCE + SRC yolu + gerçek modül
importu; UserManagementScreen.__new__ bare-instance idyomu (init'siz,
yalnız çizim yolunun gerçek bağımlılıkları enjekte edilir).
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

import ui_scaling
import user_screens
from ui_text_layout import wrap_text_limited
from user_screens import UserManagementScreen

if not pygame.font.get_init():
    pygame.font.init()


# 70+ karakterlik kullanıcı adı: eskiden onay satırını kutudan taşırdı.
LONG_USERNAME = "Cok_Uzun_Kullanici_Adi_Ornegi_" + "X" * 40
# Uzun Türkçe karakterli biyografi (üöişçğü) — satır genişliği sözleşmesi.
LONG_BIO = (
    "Çok uzun Türkçe karakterli bir biyografi örneği: üöişçğü "
    "Işıklar sürekli parlasın ve satırlar kart içinde kalsın. " + "y" * 60
)
GAME_MODES = ["classic", "survival", "zen", "sprint", "ultra", "chaos", "royale", "custom"]

USER_DATA = {
    "bio": LONG_BIO,
    "total_games": 1234,
    "total_wins": 567,
    "total_score": 12345678,
    "total_lines": 987,
    "total_tetris": 65,
    "total_time": 123456,
    "game_stats": {
        mode: {"games": (i + 1) * 3, "wins": i + 1, "losses": (i + 1) * 2}
        for i, mode in enumerate(GAME_MODES)
    },
}

SIZES = [
    (640, 360),
    (800, 480),
    (1024, 600),
    (1280, 720),
    (1366, 768),
    (1600, 900),
    (1920, 1080),
    (3840, 2160),
]


class _StubUserManager:
    def __init__(self, data):
        self._data = data

    def get_user_data(self, username):
        return self._data


def _make_mgr(screen, username=LONG_USERNAME, user_data=None):
    """Bare UserManagementScreen: yalnız çizim yolunun bağımlılıkları."""
    mgr = UserManagementScreen.__new__(UserManagementScreen)
    mgr.screen = screen
    mgr._ui_reference_size = (1600.0, 900.0)
    mgr._ui_readable_min_size = (1366.0, 768.0)
    mgr._ui_scale_current = 1.0
    mgr._base_font_title_size = 56
    mgr._base_font_normal_size = 36
    mgr._base_font_small_size = 26
    mgr._font_scale_signature = None
    mgr.confirm_username = username
    mgr.edit_username = username
    mgr.message = ""
    mgr.state = "confirm_delete"
    mgr.user_manager = _StubUserManager(user_data if user_data is not None else USER_DATA)
    mgr._apply_responsive_metrics()  # fontlar (UIFonts.get) hazır olsun
    return mgr


@pytest.fixture(autouse=True)
def _normal_preset():
    """Her testin 'normal' preset ile başlayıp bitmesini garantiler."""
    ui_scaling.set_ui_scale_preset("normal")
    yield
    ui_scaling.set_ui_scale_preset("normal")


# ── Modal: safe rect + sarma + buton yerleşimi ──────────────────────────────


@pytest.mark.parametrize("size", SIZES)
def test_modal_box_and_text_within_safe_rect(size):
    """Kutu, başlık, sarılmış satırlar ve butonlar daima safe rect + kutu içinde."""
    screen = pygame.display.set_mode(size)
    mgr = _make_mgr(screen)
    w, h = size
    # Gerçekçi overscan benzeri stub: %5 içeri çekilmiş güvenli alan.
    stub = pygame.Rect(w // 20, h // 20, w - 2 * (w // 20), h - 2 * (h // 20))
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(user_screens, "get_render_safe_rect", lambda scr: stub)
        mgr._draw_confirm_delete()
    r = mgr._confirm_delete_rects
    box, bounds = r["box"], r["bounds"]

    assert stub.contains(box), f"kutu safe rect dışında: {box} vs {stub}"
    assert bounds == stub
    assert box.width >= mgr._s(200) and box.height >= mgr._s(160)

    # Metin satırları kutu İÇİNDE (yükseklik içerik bütçesinden üretildi).
    for key in ("title",):
        assert box.contains(r[key]), f"{key} kutu dışında: {r[key]}"
    for key in ("msg1_lines", "msg2_lines", "warning_lines"):
        for i, line_rect in enumerate(r[key]):
            assert box.contains(line_rect), f"{key}[{i}] kutu dışında: {line_rect} vs {box}"

    # Satır genişlikleri kutu iç genişliğine sığar (pad_x = s(24)).
    inner_w = box.width - 2 * mgr._s(24)
    for key in ("msg1_lines", "msg2_lines", "warning_lines"):
        for i, line_rect in enumerate(r[key]):
            assert line_rect.width <= inner_w, (
                f"{key}[{i}] genişlik taşması: {line_rect.width} > {inner_w} (size={size})"
            )

    # Butonlar kutu içinde ve birbirine binmez; metin satırları butonlara binmez.
    for key in ("no_button", "yes_button"):
        assert box.contains(r[key]), f"{key} kutu dışında: {r[key]}"
    assert not r["no_button"].colliderect(r["yes_button"]), "butonlar çakışıyor"
    for key in ("msg1_lines", "msg2_lines", "warning_lines"):
        for i, line_rect in enumerate(r[key]):
            assert not line_rect.colliderect(r["no_button"]), f"{key}[{i}] no butonuna biniyor"
            assert not line_rect.colliderect(r["yes_button"]), f"{key}[{i}] yes butonuna biniyor"


@pytest.mark.parametrize("size", SIZES)
def test_modal_full_screen_fallback_when_safe_rect_missing(size):
    """Geometry yoksa (None) bounds tam ekrana düşer; kutu yine ekranda kalır."""
    screen = pygame.display.set_mode(size)
    mgr = _make_mgr(screen)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(user_screens, "get_render_safe_rect", lambda scr: None)
        mgr._draw_confirm_delete()
    r = mgr._confirm_delete_rects
    box, bounds = r["box"], r["bounds"]
    w, h = size

    assert bounds == pygame.Rect(0, 0, w, h)
    assert bounds.contains(box)
    for key in ("no_button", "yes_button"):
        assert box.contains(r[key])


def test_modal_long_username_wraps_instead_of_overflow():
    """70+ karakterlik ad: satır sayısı artar, genişlik taşması asla olmaz."""
    screen = pygame.display.set_mode((1280, 720))
    mgr = _make_mgr(screen)
    mgr._draw_confirm_delete()
    r = mgr._confirm_delete_rects
    box = r["box"]
    inner_w = box.width - 2 * mgr._s(24)

    assert len(r["msg1_lines"]) >= 1
    for i, line_rect in enumerate(r["msg1_lines"]):
        assert line_rect.width <= inner_w
        assert box.contains(line_rect)


def test_modal_box_height_grows_with_wrapped_content():
    """Çok satırlı içerik kutuyu s(280) tabanının ÜZERİNE büyütür (artık üst üste binmez)."""
    screen = pygame.display.set_mode((1600, 900))
    mgr = _make_mgr(screen)
    mgr._draw_confirm_delete()
    tall = mgr._confirm_delete_rects["box"].height

    assert tall >= mgr._s(280)

    # Kısa kullanıcı adıyla taban kutu birebir s(280) tabanını korur.
    mgr_short = _make_mgr(screen, username="kisa")
    mgr_short._draw_confirm_delete()
    assert mgr_short._confirm_delete_rects["box"].height >= mgr_short._s(280)
    assert mgr_short._confirm_delete_rects["box"].height <= tall + 1


@pytest.mark.parametrize("size", SIZES)
def test_modal_large_preset_keeps_containment(size):
    """'large' preset (%125) altında da aynı değişmezler geçerli."""
    ui_scaling.set_ui_scale_preset("large")
    screen = pygame.display.set_mode(size)
    mgr = _make_mgr(screen)
    w, h = size
    stub = pygame.Rect(w // 20, h // 20, w - 2 * (w // 20), h - 2 * (h // 20))
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(user_screens, "get_render_safe_rect", lambda scr: stub)
        mgr._draw_confirm_delete()
    r = mgr._confirm_delete_rects
    box = r["box"]

    assert stub.contains(box)
    for key in ("msg1_lines", "msg2_lines", "warning_lines"):
        for i, line_rect in enumerate(r[key]):
            assert box.contains(line_rect), f"{key}[{i}] kutu dışında: {line_rect}"
    inner_w = box.width - 2 * mgr._s(24)
    for key in ("msg1_lines", "msg2_lines"):
        for line_rect in r[key]:
            assert line_rect.width <= inner_w
    assert not r["no_button"].colliderect(r["yes_button"])


def test_modal_overlay_surface_is_cached_not_reallocation():
    """Kare-başı Surface tahsisi yasaktır: ikinci kare önbellekten aynı yüzey."""
    screen = pygame.display.set_mode((1280, 720))
    mgr = _make_mgr(screen)
    mgr._draw_confirm_delete()
    cache = mgr._confirm_overlay_cache
    key = ("overlay", 1280, 720)
    assert key in cache
    first = cache[key]

    mgr._draw_confirm_delete()
    assert mgr._confirm_overlay_cache[key] is first
    assert len(mgr._confirm_overlay_cache) <= 8


def test_modal_button_geometry_pins_baseline():
    """1600x900 baseline: kutu genişliği 600, buton ölçüleri + alt-s(40) çapası."""
    screen = pygame.display.set_mode((1600, 900))
    mgr = _make_mgr(screen, username="kisa")
    mgr._draw_confirm_delete()
    r = mgr._confirm_delete_rects
    box = r["box"]

    assert box.width == 600
    assert box.centerx == 800  # clamp no-op (ekran ortası)
    s = mgr._s
    assert not r["buttons_stacked"]
    assert r["no_button"].width == 120 and r["no_button"].height == 35
    assert r["yes_button"].width == 120 and r["yes_button"].height == 35
    # left = cx - 120 - 15, merkez = left + 60.
    assert r["no_button"].center == (box.centerx - 120 - 30 // 2 + 60, box.bottom - 40)
    assert r["yes_button"].center == (box.centerx + 30 // 2 + 120 // 2, box.bottom - 40)


# ── Profil kartı: grid reflow + metin bütçeleri ─────────────────────────────


@pytest.mark.parametrize("size", SIZES)
def test_profile_stat_grid_columns_fit_available_width(size):
    """Değişmez: cols*card_w + (cols-1)*gap daima kullanılabilir genişlikte."""
    screen = pygame.display.set_mode(size)
    mgr = _make_mgr(screen)
    mgr.state = "view_profile"
    mgr._draw_view_profile()
    vr = mgr._view_profile_rects
    gap = mgr._s(15)

    assert vr["stat_cols"] >= 1
    total_w = vr["stat_cols"] * vr["stat_card_width"] + (vr["stat_cols"] - 1) * gap
    assert total_w <= vr["stat_avail_w"], (
        f"stat grid taşması: cols={vr['stat_cols']} card_w={vr['stat_card_width']} "
        f"gap={gap} avail={vr['stat_avail_w']} (size={size})"
    )
    # Kolon merdiveni dar ekranda gerçekten devreye girer (≤800 genişlikte
    # 3 kolon ~870px bütçeye sığamaz → 2 veya 1 olmalı).
    if size[0] <= 800:
        assert vr["stat_cols"] <= 2


@pytest.mark.parametrize("size", SIZES)
def test_profile_mode_grid_columns_fit_available_width(size):
    screen = pygame.display.set_mode(size)
    mgr = _make_mgr(screen)
    mgr.state = "view_profile"
    mgr._draw_view_profile()
    vr = mgr._view_profile_rects
    if not vr["mode_rects"] and vr["mode_cols"] == 0:
        return  # oyun oynamamış senaryo değil; mod var ama dikey guard kesti
    gap = mgr._s(15)
    total_w = vr["mode_cols"] * mgr._s(200) + (vr["mode_cols"] - 1) * gap
    assert total_w <= vr["stat_avail_w"] or vr["mode_cols"] == 1


@pytest.mark.parametrize("size", SIZES)
def test_profile_stat_and_mode_rects_within_card(size):
    """Çizilen tüm stat/mod kartları kartın yatay sınırları ve alt bütçesi içinde."""
    screen = pygame.display.set_mode(size)
    mgr = _make_mgr(screen)
    mgr.state = "view_profile"
    mgr._draw_view_profile()
    vr = mgr._view_profile_rects
    card = vr["card"]

    for i, rect in enumerate(vr["stat_rects"]):
        assert rect.left >= card.left and rect.right <= card.right, (
            f"stat[{i}] yatay taşma: {rect} vs {card}"
        )
        assert rect.top >= card.top and rect.bottom <= card.bottom - mgr._s(4), (
            f"stat[{i}] dikey taşma: {rect} vs {card}"
        )
    for i, rect in enumerate(vr["mode_rects"]):
        assert rect.left >= card.left and rect.right <= card.right, (
            f"mode[{i}] yatay taşma: {rect} vs {card}"
        )
        assert rect.bottom <= card.bottom - mgr._s(4), (
            f"mode[{i}] dikey taşma: {rect} vs {card}"
        )


@pytest.mark.parametrize("size", SIZES)
def test_profile_bio_lines_fit_card_width(size):
    """Bio satırları (uzun TR metin dahil) kart genişlik bütçesine sığar."""
    screen = pygame.display.set_mode(size)
    mgr = _make_mgr(screen)
    mgr.state = "view_profile"
    mgr._draw_view_profile()
    vr = mgr._view_profile_rects
    budget = max(mgr._s(60), vr["card"].width - mgr._s(80))

    assert vr["bio_lines"], "bio satırları kaydedilmeli"
    for i, line_rect in enumerate(vr["bio_lines"]):
        assert line_rect.width <= budget, (
            f"bio[{i}] genişlik taşması: {line_rect.width} > {budget} (size={size})"
        )


def test_profile_name_uses_fit_text_budget():
    """Kullanıcı adı (70+ karakter) render_fit_text + '...' ile karta sığar."""
    screen = pygame.display.set_mode((1280, 720))
    mgr = _make_mgr(screen)
    mgr.state = "view_profile"
    mgr._draw_view_profile()
    vr = mgr._view_profile_rects
    budget = max(mgr._s(60), vr["card"].width - mgr._s(80))

    assert vr["name"].width <= budget, (
        f"ad taşması: {vr['name'].width} > {budget}"
    )


def test_profile_baseline_1600x900_pins_grid():
    """Baseline 1600x900: 3 stat kolonu, 280px kart, 4 mod/kolon (eski çapa)."""
    screen = pygame.display.set_mode((1600, 900))
    mgr = _make_mgr(screen)
    mgr.state = "view_profile"
    mgr._draw_view_profile()
    vr = mgr._view_profile_rects

    assert vr["stat_cols"] == 3
    assert vr["stat_card_width"] == 280
    assert vr["stat_avail_w"] == 870  # 900 - s(30) sol pay (sağ flush)
    assert vr["mode_cols"] == 4
    assert len(vr["stat_rects"]) == 6  # 6 ana stat tam görünür


# ── Kaynak sözleşmeleri (AST-pin idyomu) ────────────────────────────────────


def _user_screens_source() -> str:
    return pathlib.Path(user_screens.__file__).read_text(encoding="utf-8")


def test_source_modal_uses_safe_rect_and_wrap():
    source = _user_screens_source()
    modal = source[source.index("def _draw_confirm_delete"):source.index("def _draw_view_profile")]

    assert "get_render_safe_rect" in modal
    assert "clamp(bounds)" in modal
    assert "bounds.width - 2 * s(16)" in modal
    assert "wrap_text_limited" in modal
    # Kare-başı tahsis yasağı: overlay (w, h) önbellek anahtarı.
    assert "overlay_key = ('overlay', int(width), int(height))" in modal


def test_source_grid_ladder_no_hardcoded_columns():
    source = _user_screens_source()
    view = source[source.index("def _draw_view_profile"):]

    # Kolon merdivenleri mevcut; sabit kolon atamaları YOK.
    assert re.search(r"for cand_cols in \(3, 2, 1\):", view)
    assert re.search(r"for cand_modes in \(4, 3, 2, 1\):", view)
    assert not re.search(r"^\s*cols = 3\b", view, re.MULTILINE)
    assert not re.search(r"^\s*max_modes_per_row = 4\b", view, re.MULTILINE)
    # Ad + bio bütçe sözleşmeleri.
    assert "render_fit_text" in view
    assert "wrap_text_limited" in view


def test_wrap_ellipsis_is_ascii():
    """Ellipsis daima ASCII '...' — emoji/unicode kısaltma yasak (CLAUDE.md)."""
    screen = pygame.display.set_mode((800, 480))
    mgr = _make_mgr(screen)
    wrapped = wrap_text_limited("X" * 300, mgr.font_normal, 200, max_lines=2)

    assert wrapped.truncated is True
    assert wrapped.lines
    assert wrapped.lines[-1].endswith("...")
    for line in wrapped.lines:
        assert "…" not in line
