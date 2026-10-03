# -*- coding: utf-8 -*-
"""P1-12a: ModeMusicScreen + HighScoreScreen ölçek/containment sözleşmesi.

Quadrix_Tum_Ekranlar_Olcekleme_Denetim_Raporu (P1-12a) düzeltmeleri:
- ModeMusicScreen draw()/_overlay_layout/_draw_track_picker panelleri
  ölçekli taban + safe-rect bütçesine bağlandı (eski sabit 700/500
  tabanları küçük pencerelerde ekrana taşıyordu); kare-başı SRCALPHA
  yüzey tahsisleri (gölge/panel/chip/satır/zemin/dim) boyut-anahtarlı
  önbelleğe taşındı (FAZ A6 deseni); picker parça adları satır bütçesine
  ASCII '...' ile sığar.
- HighScoreScreen kart/header yüzeyleri önbelleğe alındı; mod adı fitted;
  sıra/skor/tarih kolon çakışma guard'ı eklendi (yalnız taşma anında
  devreye girer — baseline genişliğinde konumlar birebir); içerik alanı
  safe rect bütçesine bağlandı.
- Gamepad göstergesi fallback'inde font emoji glifi kaldırıldı (CLAUDE.md:
  pygame fontları renkli emojiyi bozar; PNG asset yolu korunur).

Değişmez kapsamı (dürüst sınır): HighScore kart ızgarası kaydırılabilir
sanal listedir — alt kenardan kısmen taşan görünen kart BLIT düzeyinde
set_clip ile kırpılır (mevcut tasarım). Bu dosya yatay bütçe (içerik
alanı/kart genişliği), kolon ayrıklığı ve kaynak sözleşmesini kilitler.
Gerçek 4K/G-Sync görsel doğrulama kılavuz §7'deki manuel Windows
smoke'a aittir — dummy driver altında koşulmaz.

Kalıp: test_highscore_screen_data_source (gerçek menu importu) +
test_coop_level_select_narrow_screen (çok boyutlu gerçek draw) +
test_gameplay_settings_ui_scale (preset save/restore).
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

import menu as menu_module
from menu import HighScoreScreen, ModeMusicScreen
from ui_scaling import set_ui_scale_preset, get_ui_scale_preset

if not pygame.font.get_init():
    pygame.font.init()
if not pygame.display.get_init():
    pygame.display.init()


SIZES = [(640, 360), (800, 480), (1024, 600), (1280, 720), (1366, 768), (1920, 1080), (3840, 2160)]
PRESETS = ["normal", "large", "massive"]


class _SettingsManagerStub:
    """ModeMusicScreen için ayar yöneticisi stub'u."""

    def __init__(self):
        self._overrides = {}

    def get_mode_music_overrides(self):
        return dict(self._overrides)

    def set_mode_music_override(self, mode_key, value):
        self._overrides[mode_key] = value


class _UserManagerStub:
    """HighScoreScreen için yerel skor kaynağı stub'u."""

    def __init__(self, scores):
        self._scores = scores

    def get_mode_highscores(self, mode_key, limit=3):
        return list(self._scores.get(mode_key, []))[:limit]


def _make_screen_surface(w: int, h: int) -> pygame.Surface:
    return pygame.display.set_mode((w, h))


def _make_mode_music(w: int, h: int) -> ModeMusicScreen:
    surface = _make_screen_surface(w, h)
    return ModeMusicScreen(surface, _SettingsManagerStub())


def _make_highscore(w: int, h: int, scores=None) -> HighScoreScreen:
    surface = _make_screen_surface(w, h)
    return HighScoreScreen(
        surface, score_manager=None,
        user_manager=_UserManagerStub(scores or {}), steam_mode_scores={})


LONG_SCORES = {
    'classic': [
        {'score': 12345678, 'date': '2026-10-03'},
        {'score': 9876543, 'date': '2026-09-28'},
        {'score': 55555, 'date': '2026-08-14'},
    ],
    'mystery': [
        {'score': 197502, 'date': '2026-10-01'},
        {'score': 122239, 'date': '2026-09-30'},
    ],
}


@pytest.fixture(autouse=True)
def _restore_preset():
    previous = get_ui_scale_preset()
    try:
        yield
    finally:
        set_ui_scale_preset(previous)


# ── ModeMusicScreen: panel containment matrisi ──────────────────────────────


@pytest.mark.parametrize("w,h", SIZES)
@pytest.mark.parametrize("preset", PRESETS)
def test_mode_music_panel_fits_screen_matrix(w, h, preset):
    """Ana panel daima ekran (safe-rect fallback) içinde kalır.

    Eski sabit 700/500 tabanları 640x360'ta ekrana taşıyordu; yeni formül
    0.88*width terimi korunan genişlikte bağlayıcı kalır (baseline nötr).
    """
    set_ui_scale_preset(preset)
    screen = _make_mode_music(w, h)
    screen.draw()

    panel = screen._mode_music_panel_rects['panel']
    screen_rect = pygame.Rect(0, 0, w, h)
    assert screen_rect.contains(panel), (
        f"mod müziği paneli ekrana taşıyor: {panel} vs {screen_rect} "
        f"({w}x{h}, preset={preset})"
    )


@pytest.mark.parametrize("w,h", SIZES)
def test_mode_music_overlay_panel_fits_screen(w, h):
    """Overlay (modal) düzeni de ekrana sığar; rect kayıtları bu kareye ait.

    rows kaydının BOŞ olmaması ayrıca güvence altına alınır — kayıt,
    satır döngüsünden SONRA alınmalıdır (döngü öncesi alınırsa ilk
    çizimde bir önceki karenin boş listesi kaydedilirdi).
    """
    screen = _make_mode_music(w, h)
    screen.draw_overlay()

    rects = screen._mode_music_overlay_rects
    panel, list_rect = rects['panel'], rects['list']
    screen_rect = pygame.Rect(0, 0, w, h)
    assert screen_rect.contains(panel)
    assert panel.contains(list_rect)
    assert any(r.height > 0 for r in rects['rows']), (
        "overlay satır kayıtları boş (kayıt döngü öncesi alınmış olabilir)"
    )
    # Görünür satırlar liste alanının yatay bütçesinde (kaydırma dikeydir).
    for row in rects['rows']:
        if row.height > 0:
            assert row.right <= list_rect.right + 1
            assert row.width == list_rect.width


@pytest.mark.parametrize("w,h", [(640, 360), (800, 480), (1024, 600)])
def test_track_picker_label_fits_row_budget(w, h):
    """Uzun parça adı satır bütçesine ASCII '...' ile sığar (P1-12a)."""
    screen = _make_mode_music(w, h)
    long_label = 'Cok Uzun Bir Parca Adi Deneme Dosyasi 2026 Bolum 12 Final'
    # Deterministik sahne: seçenek listesi testin kendi verisiyle kurulur.
    # Tam paket koşularında önceki dosyalar ambient dili değiştirebiliyor ve
    # ambient müzik durumu parça listesini doldurabiliyordu; uzun etiket
    # görünür kayan pencerenin dışına düşüp items[-1] bambaşka (lokalize)
    # bir parça adı oluyordu. Tek seçenekli listede kayıtlı satır daima
    # uzun etiketin kendisidir.
    screen.track_options = [{'label': long_label, 'value': 'file:test_long.ogg'}]
    screen.picker_open = True
    screen.picker_mode_key = 'classic'
    screen.picker_selected = 0
    screen._draw_track_picker()

    items = screen._track_picker_rects['items']
    assert items, "picker öğe kaydı boş"
    row, label_fit = items[-1]
    # Kaynak kodun ölçüm fontu: seçili satır → bold=True.
    font = menu_module.retro_style.get_font(22, bold=True)
    label_w = font.size(label_fit)[0]
    pad = int(screen._s(14, minimum=1))
    budget = max(16, row.width - pad * 2)
    assert label_w <= budget, (
        f"picker etiketi satır bütçesini aşıyor: {label_w} > {budget} "
        f"({w}x{h}, label={label_fit!r})"
    )
    assert all(ord(ch) < 128 or ord(ch) > 0x2700 for ch in label_fit), \
        "ellipsis ASCII '...' olmalı (emoji/sembol yasak)"


def test_mode_music_surface_cache_bounded_and_stable():
    """Kare-başı SRCALPHA tahsisi yok: aynı boyutta önbellek nesne kimliği
    korunur; tek instance üzerinde değişen pencere boyutları FIFO
    kapasite sınırını (24) gerçekten exercise eder."""
    screen = _make_mode_music(1366, 768)
    screen.draw()
    snapshot_a = dict(screen._mm_surface_cache)
    screen.draw()
    snapshot_b = dict(screen._mm_surface_cache)
    assert set(snapshot_a) == set(snapshot_b)
    assert snapshot_a, "ilk çizimden sonra önbellek boş olamaz"
    for key in snapshot_a:
        assert snapshot_a[key] is snapshot_b[key], (
            f"aynı boyutta yüzey yeniden üretilmiş: {key}"
        )

    # Aynı instance, farklı boyutlar → farklı anahtarlar birikir; sınır
    # aşımında en eski tahliye edilir.
    for w, h in SIZES:
        screen.screen = _make_screen_surface(w, h)
        screen.draw()
    assert 0 < len(screen._mm_surface_cache) <= 24, (
        "yüzey önbelleği kapasite sınırını aştı"
    )


# ── HighScoreScreen: kart bütçe matrisi ─────────────────────────────────────


@pytest.mark.parametrize("w,h", SIZES)
@pytest.mark.parametrize("preset", PRESETS)
def test_highscore_cards_within_budget_matrix(w, h, preset):
    """İçerik alanı ekrana sığar; kartlar YATAY bütçe içinde; kolonlar
    (sıra↔skor↔tarih, mod adı) çakışmaz.

    Dikey taşma bilinçli olarak kapsam dışıdır: ızgara kaydırılabilir
    sanal liste, kırpma set_clip ile (mevcut tasarım).
    """
    set_ui_scale_preset(preset)
    screen = _make_highscore(w, h, scores=LONG_SCORES)
    screen.draw()

    rects = screen._highscore_rects
    bounds, cards = rects['bounds'], rects['cards']
    assert bounds.width <= w and bounds.height <= h
    # İçerik alanı güvenli bütçe içinde.
    assert rects['content_x'] >= bounds.left
    assert rects['content_x'] + rects['content_w'] <= bounds.right
    assert rects['content_w'] >= 120, (
        f"içerik alanı okunamaz kadar dar: {rects['content_w']} ({w}x{h})"
    )
    # Kartlar yatay bütçede (dikeyde clip; üstten negatif olamaz).
    for card in cards:
        assert card.left >= bounds.left and card.right <= bounds.right, (
            f"kart yatay bütçe dışında: {card} vs {bounds} "
            f"({w}x{h}, preset={preset})"
        )
        assert card.top >= bounds.top

    # Kolon çakışmaz: sıra ↔ skor ↔ tarih rect'leri ayrık.
    for rows in rects['card_rows']:
        for row in rows[1:]:
            rank_rect, score_rect = row['rank'], row['score']
            assert not rank_rect.colliderect(score_rect), (
                f"sıra/skor kolonları çakıştı: {rank_rect} vs {score_rect} "
                f"({w}x{h}, preset={preset})"
            )
            date_rect = row['date']
            if date_rect is not None:
                assert not score_rect.colliderect(date_rect)
        # İsim rect'i yatayda bütçe içinde (ilk kayıt).
        name_rect = rows[0]['name']
        assert name_rect.left >= bounds.left and name_rect.right <= bounds.right, (
            f"mod adı yatay bütçe dışında: {name_rect} ({w}x{h})"
        )


def test_highscore_narrow_card_rank_score_no_overlap():
    """Dar kartta sıra/skor çakışma guard'ı: fitted skor sıranın sağına
    yerleşir, üst üste binme OLMAZ (eski kodda guard yoktu)."""
    surface = _make_screen_surface(640, 360)
    screen = HighScoreScreen.__new__(HighScoreScreen)
    screen.screen = surface
    screen.user_manager = None
    screen.steam_mode_scores = {}
    screen._highscore_rects = {'card_rows': []}

    scores = [
        {'score': 123456789, 'date': '2026-10-03'},
        {'score': 98765432, 'date': '2026-09-28'},
        {'score': 55555555, 'date': '2026-08-14'},
    ]
    narrow = pygame.Rect(0, 0, 120, 130)
    screen._draw_mode_card(narrow, 'Kart Ustalığı', (255, 150, 255), scores)

    rows = screen._highscore_rects['card_rows'][0]
    for row in rows[1:]:
        assert not row['rank'].colliderect(row['score']), (
            f"dar kartta sıra/skor çakışması: {row['rank']} vs {row['score']}"
        )
        assert row['score'].right <= narrow.right
    # Fitted mod adı kart genişliğine sığar.
    assert rows[0]['name'].right <= narrow.right


def test_highscore_surface_cache_identity():
    """Kart/header yüzeyleri önbellekli — aynı boyut+renkte kimlik korunur."""
    screen = _make_highscore(1366, 768, scores=LONG_SCORES)
    screen.draw()
    snap_a = dict(screen._hs_surface_cache)
    screen.draw()
    snap_b = dict(screen._hs_surface_cache)
    assert snap_a and set(snap_a) == set(snap_b)
    for key in snap_a:
        assert snap_a[key] is snap_b[key]
    assert len(snap_b) <= 32, "kart yüzey önbelleği kapasiteyi aştı"


# ── Baseline (1366x768 / normal) geometri pin'leri ──────────────────────────


def test_baseline_1366_768_geometry_pins():
    """1366x768 + normal preset: eski yerleşim birebir korunur."""
    set_ui_scale_preset('normal')
    mm = _make_mode_music(1366, 768)
    mm.draw()
    panel = mm._mode_music_panel_rects['panel']
    assert (panel.x, panel.y, panel.width, panel.height) == (83, 46, 1200, 675)

    hs = _make_highscore(1366, 768, scores=LONG_SCORES)
    hs.draw()
    rects = hs._highscore_rects
    assert rects['content_x'] == 83
    assert rects['content_w'] == 1200
    first_card = rects['cards'][0]
    assert (first_card.width, first_card.height) == (386, 200)
    # Baseline'ta skor hâlâ ortalanmış çizilir (guard nötr).
    rows = rects['card_rows'][0]
    score_rect = rows[1]['score']
    assert abs(score_rect.centerx - first_card.centerx) <= 2


# ── Kaynak sözleşmeleri ──────────────────────────────────────────────────────


def _menu_source() -> str:
    return pathlib.Path(menu_module.__file__).read_text(encoding='utf-8')


def _class_source(class_name: str) -> str:
    """Bir sınıfın gövdesini kaynak dosyadan yalıt (scoped pin).

    menu.py'de birden çok ekran aynı kalıbı kullanır (ör. ControlSettingsScreen
    700/500 tabanlarını hâlâ taşır — P1-12a kapsamı dışında, başka maddeye
    aittir). Pin'ler sınıf gövdesine sokulmadan yanlış ekranı kilitler.
    """
    source = _menu_source()
    start = source.index(f"class {class_name}:")
    nxt = re.search(r"\nclass ", source[start + 10:])
    end = start + 10 + (nxt.start() if nxt else len(source) - start - 10)
    return source[start:end]


def test_source_no_emoji_fallback_in_gamepad_indicator():
    """Gamepad fallback'inde font emoji glifi YOK (PNG yolu korunur)."""
    source = _menu_source()
    assert "f'🎮" not in source and 'f"🎮' not in source, (
        "gamepad fallback'inde emoji glifi kalmış (CLAUDE.md yasağı)"
    )
    # PNG asset yolu aynen duruyor.
    assert re.search(r"emoji_surface\('\\U0001f3ae', 18\)|emoji_surface\('🎮', 18\)", source)


def test_source_mode_music_panel_budget_formula():
    """Panel bütçe formülü: ölçekli taban + 0.88*width + safe-rect clamp."""
    source = re.sub(r"\s+", " ", _class_source('ModeMusicScreen'))
    assert "max(_s(340), int(width * 0.88))" in source
    assert "max(_s(260), int(height * 0.88))" in source
    assert "panel.clamp(bounds)" in source
    # Eski sabit tabanlar ModeMusicScreen'de kalktı (diğer ekranlar
    # kapsam dışıdır — ayrı maddelerin konusu).
    assert "max(700, int(width * 0.88))" not in source
    assert "max(500, int(height * 0.88))" not in source


def test_source_mode_music_cache_and_picker_ellipsis():
    source = _menu_source()
    assert "_mm_cached_surface" in source
    assert "_mm_make_fill" in source
    assert "ellipsize_text(label, text_font" in source
    # Kare-başı dim tahsisi kalktı (iki yerde de önbellek kullanılıyor).
    assert re.search(r"dim = self\._mm_cached_surface\(\s*'dim'", source)


def test_source_highscore_fitted_name_and_column_guard():
    source = re.sub(r"\s+", " ", _class_source('HighScoreScreen'))
    assert "render_fit_text( mode_name, mode_color" in source
    assert "render_fit_text( score_text, score_color" in source
    assert "_hs_cached_surface" in source
    assert "rank_right + _s(6) > score_left" in source
