# -*- coding: utf-8 -*-
"""P1-10: Splash başlık/prompt metin bütçeleri.

Rapor: Quadrix_Tum_Ekranlar_Olcekleme_Denetim_Raporu.md
- Başlık: sabit ``get_font(80)`` yerine genişlik bütçeli font seçimi
  (get_fitting_font; neon yüzeyi glow padding dahil w*0.92 bütçesinde).
- Prompt: alt güvenli bandın (RenderGeometry safe rect; yoksa tam ekran)
  genişlik bütçesine sarma (wrap_text_limited, en fazla 2 satır) +
  kontrollü ASCII '...'; panel alt kenarı safe rect'i aşmaz.

Ölçüm sınırı (dürüst rapor): gerçek 4K/G-Sync görsel doğrulama kılavuz
§7'deki manuel Windows smoke'a aittir — dummy sürücü altında koşulmaz.
Bu dosya bütçe sözleşmelerini (değişmezler), önbellek kimliğini,
baseline (1366x768) piksel düzenini ve kaynak sözleşmesini kilitler.

Kalıp: test_wide_arena_hud_scale_containment (SRC yol hazırlığı + dummy
sürücüler + gerçek modül importu; bare-instance idyomu) ve
test_color_picker_text_input_containment (safe-rect stub + fallback).
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

import splash_screen as splash_screen_module
from splash_screen import SplashScreen

from retro_style import retro_style
from ui_scaling import get_ui_scale_preset, set_ui_scale_preset

if not pygame.font.get_init():
    pygame.font.init()


SIZES = [(640, 360), (800, 480), (1024, 600), (1280, 720),
         (1366, 768), (1920, 1080), (3840, 2160)]

# Uzun lokalizasyon gerilimleri (taşma senaryoları).
LONG_TR = ("Devam etmek için herhangi bir tuşa veya fareye basın — lütfen "
           "bekleyin, oyun başlatılıyor ve dosyalar yükleniyor")
LONG_EN = ("Press any key or click to continue — please wait while the game "
           "is starting and the files are being loaded")

TITLE_TEXT = 'QUADRIX'
TITLE_GLOW_PAD = 4 * 4  # NeonText glow_amount=4 → kenar başına 16px


class _RecordingSurface(pygame.Surface):
    """Blit'leri kaydeden gerçek Surface (piksel-düzeyi sözleşme kanıtı)."""

    def __init__(self, size):
        super().__init__(size)
        self.recorded_blits = []

    def blit(self, source, dest, area=None, special_flags=0):
        if isinstance(dest, pygame.Rect):
            rect = pygame.Rect(dest)
        else:
            rect = pygame.Rect(dest, source.get_size())
        self.recorded_blits.append((source, rect))
        return pygame.Rect(rect)


def _make_splash(size, prompt_text=None):
    """Bare SplashScreen: P1-10 çizim yardımcıları yalnız instance alanı ister."""
    splash = SplashScreen.__new__(SplashScreen)
    splash.screen = _RecordingSurface(size)
    splash._custom_prompt = prompt_text
    # __init__'te tanımlı P1-10 önbellek alanları (bare instance'a kurulur).
    splash._prompt_lines_cache_key = None
    splash._prompt_lines_cache = None
    splash._neon_title_font_key = None
    splash._neon_title_font = None
    return splash


def _text_max_w_for(w):
    """Üretim formülünün aynası: bütçe = bant - ok payı - panel dolgusu."""
    usable_w = max(120, w - 2 * 60)
    return max(40, usable_w - 80)


@pytest.fixture
def no_safe_rect(monkeypatch):
    """Safe rect yok → tam ekran bandı (geriye dönük uyumlu fallback)."""
    monkeypatch.setattr(splash_screen_module, "get_render_safe_rect",
                        lambda screen: None)


@pytest.fixture
def preserve_ui_preset():
    previous = get_ui_scale_preset()
    yield
    set_ui_scale_preset(previous)


# ── Başlık: genişlik bütçesi ─────────────────────────────────────────────────


@pytest.mark.parametrize("w,h", SIZES)
def test_neon_title_surface_fits_width_budget(w, h):
    """Tam neon yüzeyi (glow padding dahil) w*0.92 bütçesine sığar."""
    splash = _make_splash((w, h))
    splash._draw_neon_title(w, h, 255, 1000)

    assert splash.screen.recorded_blits, "başlık blit edilmedi"
    surf, rect = splash.screen.recorded_blits[-1]
    assert surf.get_width() <= int(w * 0.92), (
        f"neon yüzeyi bütçeyi aşıyor: {surf.get_width()} > {int(w * 0.92)} (w={w})")
    assert rect.left >= 0 and rect.right <= w
    assert rect.top >= 0 and rect.bottom <= h


@pytest.mark.parametrize("w,h", [s for s in SIZES if s[0] >= 1280])
def test_title_font_baseline_80_at_reference_sizes(w, h):
    """1280 ve üstünde taban 80 kalır — baseline görünüm birebir (P1-10)."""
    splash = _make_splash((w, h))
    splash._draw_neon_title(w, h, 255, 1000)

    base = retro_style.get_font(80, bold=True)
    assert splash._neon_title_font.size(TITLE_TEXT) == base.size(TITLE_TEXT)
    assert splash._neon_title_font.get_height() == base.get_height()


def test_title_font_shrinks_on_narrow_width():
    """Mekanizma: dar bütçede font küçülür, tam yüzey bütçeye sığar."""
    w, h = 240, 200
    splash = _make_splash((w, h))
    splash._draw_neon_title(w, h, 255, 1000)

    base_h = retro_style.get_font(80, bold=True).get_height()
    assert splash._neon_title_font.get_height() < base_h
    text_w = splash._neon_title_font.size(TITLE_TEXT)[0]
    assert text_w + 2 * TITLE_GLOW_PAD <= int(w * 0.92)


def test_title_font_cache_identity_and_recompute():
    """(w, h) anahtarlı font önbelleği: aynı boyut → aynı Font nesnesi."""
    splash = _make_splash((1366, 768))
    splash._draw_neon_title(1366, 768, 255, 1000)
    font_a = splash._neon_title_font
    splash._draw_neon_title(1366, 768, 255, 2000)
    assert splash._neon_title_font is font_a

    # Boyut değişince anahtar yenilenir (pencere resize). Font NESNESİ
    # retro_style LRU'sundan aynı gelebilir (get_fitting_font ölçümü metin
    # genişliğini aşmıyorsa taban boyutu döndürür) — nesne paylaşımı
    # kare-başı tahsis yasağının İSTENEN sonucudur, anahtar sözleşmesi
    # yenilenmeyi kanıtlar.
    splash._draw_neon_title(800, 480, 255, 3000)
    assert splash._neon_title_font_key == (800, 480)
    assert splash._neon_title_font.size(TITLE_TEXT)[0] + 2 * TITLE_GLOW_PAD <= int(800 * 0.92)


# ── Prompt: bant bütçesi + sarma + önbellek ──────────────────────────────────


@pytest.mark.parametrize("w,h", SIZES)
@pytest.mark.parametrize("prompt", [LONG_TR, LONG_EN])
def test_prompt_wraps_within_band_budget(w, h, prompt, no_safe_rect):
    """Uzun prompt en fazla 2 satıra sarılır; her satır bütçe içinde."""
    splash = _make_splash((w, h), prompt)
    splash._draw_animated_prompt(w, h, 1000, False)

    line_texts, line_surfs = splash._prompt_lines_cache
    assert 1 <= len(line_surfs) <= 2
    text_max_w = _text_max_w_for(w)
    for surf in line_surfs:
        assert surf.get_width() <= text_max_w, (
            f"prompt satırı bütçeyi aşıyor: {surf.get_width()} > {text_max_w} (w={w})")

    # Tüm blit'ler (panel + glow + metin + oklar) ekran içinde kalır.
    for surf, rect in splash.screen.recorded_blits:
        assert rect.left >= 0 and rect.right <= w, f"yatay taşma (w={w}): {rect}"
        assert rect.top >= 0 and rect.bottom <= h, f"dikey taşma (w={w}): {rect}"


def test_prompt_single_line_default_tr_baseline_1366(no_safe_rect):
    """1366x768 + varsayılan TR prompt: tek satır, eski düzenle birebir."""
    w, h = 1366, 768
    splash = _make_splash((w, h))  # özel prompt yok → t('splash_press_any_key')
    splash._draw_animated_prompt(w, h, 1000, False)

    line_texts, line_surfs = splash._prompt_lines_cache
    assert len(line_surfs) == 1
    line_surf = line_surfs[0]
    # Eski formül: metin merkezi (w//2, int(h*0.88)); panel = metin + 80x/36y.
    expected_line = line_surf.get_rect(center=(w // 2, int(h * 0.88)))
    line_blits = [rect for surf, rect in splash.screen.recorded_blits
                  if surf is line_surf]
    assert line_blits == [expected_line]

    panel_rect = [rect for surf, rect in splash.screen.recorded_blits[:1]][0]
    panel_w = line_surf.get_width() + 80
    panel_h = line_surf.get_height() + 36
    assert panel_rect.width == panel_w
    assert panel_rect.height == panel_h
    assert panel_rect.topleft == ((w - panel_w) // 2, expected_line.y - 18)


def test_prompt_custom_prompt_is_used(no_safe_rect):
    """Özel prompt (parametre) önbellek anahtarına ve satırlara yansır."""
    splash = _make_splash((1280, 720), "Özel kısa prompt")
    splash._draw_animated_prompt(1280, 720, 1000, False)
    line_texts, _ = splash._prompt_lines_cache
    assert line_texts == ["Özel kısa prompt"]


def test_prompt_lines_cache_identity(no_safe_rect):
    """Aynı (metin, bütçe) → aynı Satır Surface NESNELERİ (kare-başı yok)."""
    w, h = 800, 480
    splash = _make_splash((w, h), LONG_TR)
    splash._draw_animated_prompt(w, h, 1000, False)
    _, surfs_a = splash._prompt_lines_cache
    splash._draw_animated_prompt(w, h, 2000, False)
    _, surfs_b = splash._prompt_lines_cache
    assert surfs_a is surfs_b  # tuple içindeki liste aynı nesne
    for a, b in zip(surfs_a, surfs_b):
        assert a is b


def test_prompt_lines_cache_recomputes_on_width_change(no_safe_rect):
    """Bütçe değişince (pencere resize) satırlar yeniden çözülür."""
    splash = _make_splash((1024, 600), LONG_TR)
    splash._draw_animated_prompt(1024, 600, 1000, False)
    key_a = splash._prompt_lines_cache_key
    splash._draw_animated_prompt(800, 480, 2000, False)
    assert splash._prompt_lines_cache_key != key_a


def test_prompt_no_emoji_in_lines(no_safe_rect):
    """Sarılan satırlarda emoji/sembol aralığı karakter yok (CLAUDE.md)."""
    splash = _make_splash((800, 480), LONG_TR)
    splash._draw_animated_prompt(800, 480, 1000, False)
    line_texts, _ = splash._prompt_lines_cache
    for line in line_texts:
        assert not any(0x1F000 <= ord(ch) <= 0x1FAFF for ch in line)
        assert not any(0x2700 <= ord(ch) <= 0x27C0 for ch in line)


def test_prompt_bottom_clamped_to_safe_rect(monkeypatch):
    """Safe rect alt kenarı panelin doğal altını kesiyorsa panel yukarı kenetlenir."""
    w, h = 800, 480
    # Safe rect alt kenarı 430; doğal panel altı ~467 (LONG prompt, 2 satır).
    safe = pygame.Rect(0, 0, w, 430)
    monkeypatch.setattr(splash_screen_module, "get_render_safe_rect",
                        lambda screen: safe)
    splash = _make_splash((w, h), LONG_TR)
    splash._draw_animated_prompt(w, h, 1000, False)

    panel_rect = splash.screen.recorded_blits[0][1]
    assert panel_rect.bottom == 430 - 6
    # Satırlar panelin dikey sınırları içinde kalır.
    _, line_surfs = splash._prompt_lines_cache
    for surf, rect in splash.screen.recorded_blits:
        if any(s is surf for s in line_surfs):
            assert rect.top >= panel_rect.top
            assert rect.bottom <= panel_rect.bottom


def test_prompt_horizontal_band_respected(monkeypatch):
    """Safe rect yatay bantları (ör. HDR marjları) panel yerleşimini kısar."""
    w, h = 1280, 720
    safe = pygame.Rect(50, 0, w - 100, h)
    monkeypatch.setattr(splash_screen_module, "get_render_safe_rect",
                        lambda screen: safe)
    splash = _make_splash((w, h), LONG_TR)
    splash._draw_animated_prompt(w, h, 1000, False)

    panel_rect = splash.screen.recorded_blits[0][1]
    assert panel_rect.left >= safe.left
    assert panel_rect.right <= safe.right
    # Satır merkezleri bant merkezine hizalanır.
    center_x = (safe.left + safe.right) // 2
    _, line_surfs = splash._prompt_lines_cache
    for surf, rect in splash.screen.recorded_blits:
        if any(s is surf for s in line_surfs):
            assert abs(rect.centerx - center_x) <= 1


def test_prompt_real_safe_rect_call_stays_in_screen():
    """Gerçek get_render_safe_rect (offscreen Surface) — içerme ekran içinde."""
    w, h = 1280, 720
    splash = _make_splash((w, h), LONG_TR)
    splash._draw_animated_prompt(w, h, 1000, False)

    for surf, rect in splash.screen.recorded_blits:
        assert rect.left >= 0 and rect.right <= w
        assert rect.top >= 0 and rect.bottom <= h


@pytest.mark.parametrize("preset", ["large", "massive"])
@pytest.mark.parametrize("w,h", [(1024, 600), (1366, 768), (1920, 1080)])
def test_prompt_fits_under_ui_scale_presets(w, h, preset, no_safe_rect,
                                            preserve_ui_preset):
    """Büyük font presetlerinde bile satırlar bant bütçesinde kalır."""
    set_ui_scale_preset(preset)
    splash = _make_splash((w, h), LONG_TR)
    splash._draw_animated_prompt(w, h, 1000, False)

    line_texts, line_surfs = splash._prompt_lines_cache
    assert 1 <= len(line_surfs) <= 2
    text_max_w = _text_max_w_for(w)
    for surf in line_surfs:
        assert surf.get_width() <= text_max_w
    for surf, rect in splash.screen.recorded_blits:
        assert rect.left >= 0 and rect.right <= w
        assert rect.top >= 0 and rect.bottom <= h


# ── Kaynak sözleşmeleri (AST-pin idyomu) ─────────────────────────────────────


def _source() -> str:
    return pathlib.Path(splash_screen_module.__file__).read_text(encoding='utf-8')


def test_source_title_uses_fitting_font_not_fixed_80():
    source = _source()
    body = source[source.index("def _draw_neon_title"):source.index("def _hsv_to_rgb")]
    assert "get_fitting_font" in body, "başlık bütçe seçimi kayboldu"
    # Çağrı formunu hedefle: metod docstring'i ``get_font(80)`` geçmiş
    # referansı içerebilir (yanlış pozitif); kod çağrısı yasak.
    assert "retro_style.get_font(80" not in body, "sabit 80 font geri geldi"
    assert "_neon_title_font" in body


def test_source_prompt_uses_wrap_and_safe_rect():
    source = _source()
    body = source[source.index("def _draw_animated_prompt"):
                  source.index("def _draw_corner_decorations")]
    assert "wrap_text_limited" in body, "prompt sarma sözleşmesi kayboldu"
    assert "get_render_safe_rect" in body, "safe-rect bant sözleşmesi kayboldu"
    assert "_prompt_lines_cache" in body, "satır önbelleği kayboldu"
    assert "max_lines=2" in body, "2 satır limiti kayboldu"


def test_source_has_no_emoji():
    """Dosyada emoji/dingbat aralığı karakter yok (CLAUDE.md yasağı)."""
    source = _source()
    assert not re.search(r"[\U0001F000-\U0001FAFF✀-⟀]", source)
