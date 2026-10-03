# -*- coding: utf-8 -*-
"""DUZ: pencere modu SDL2 overlay intent transaction sözleşme testleri (demo).

Kılavuz: Quadrix_UI_4K_WideArena_Pencere_Modu_Duzeltme_Kilavuzu.md
(kök nedenler C4-C6) — v2 tests/test_display_window_transaction.py
uyarlaması. Bilinçli demo farkları (kör kopya YASAK):
- Demo platform_utils work-area API'si FARKLI: get_desktop_work_area()
  (w, h) döndürür (v2'deki Rect tabanlı get_work_area DEĞİL) →
  _centered_window_position merkezlemesi (0,0) kökenlidir.
- Demo clamp'i oransal (clamp_window_size_to_work_area); v2'nin sabit
  (1600,900)/(1280,720) merdiveni YOK → aşırı boyut testi tam değer
  değil SINIR + merkez sözleşmesiyle doğrulanır.
- Demo create_display'te _set_mode_with_vsync YOK (düz set_mode) →
  kaynak sözleşmesi IS_MACOS dalına göre sabitlenir.

Düzeltme sözleşmeleri (bu dosya kanıtlar):
1. sdl2_overlay.apply_window_intent: boyut+borderless+resizable+konum
   TOPLUCA karşılaştırılır (no-op kararı), uygulama sırası kenar→resizable→
   boyut→konum, hata anında rollback, GERÇEK boyut geri okunur ve
   _width/_height + present rect ona göre tazelenir; boyut değiştiyse arka
   plan dokusu yeniden kurulur; tek geçişte geometri kuşağı + tazeleme hızı
   önbelleği düşürülür.
2. platform_utils.create_display: overlay (sdl2) aktifken intent,
   work-area clamp'inden SONRA uygulanır → 4K'da ekranı aşan istek clamp
   edilir; set_mode yine ASLA çağrılmaz (tek pencere garantisi).
3. gl_compat aktifken create_display yalnız GERÇEK no-op'ta yüzey döndürür;
   değişiklik istekleri set_mode yoluna düşer (wrapper + _reapply_gl
   iki-adımlı yol), gl_compat wrapper'ı erken dönmek için boyut VE stil
   intent'inin eşleşmesini ister.
4. main.py açılışı gl_overlay_setup'a intent'i geçirir.

Ölçüm sınırı (dürüst rapor): dummy sürücünün pencere yöneticisi yoktur —
borderless/resizable flag'lerinin GERÇEK görsel etkisi ve Steam overlay
davranışı burada KANITLANAMAZ; testler çağrı sözleşmesini (fake Window ile
yazım sırası, rollback, geri okuma) kilitler. Gerçek Windows/Steam smoke
kılavuz §7'deki kullanıcı turudur.

Kalıp: test_sdl2_overlay_backend (modül global'leri monkeypatch + gerçek
modül importu). ÖNEMLİ: platform_utils/sdl2_overlay/gl_compat importları
modül-seviyesinde DEĞİL, her testin BAŞINDA (live_display_family fixture'ı)
yapılır. Gerekçe (v2'de probe koşusuyla kanıtlandı, demo conftest'i aynı
izolasyon makinelerini kullanır): conftest'in koleksiyon-sınırı purgeleri
ve sonraki dosyaların stub-yeniden import zinciri, koleksiyon ile runtime
arasında sys.modules kopyalarını dosya-seviyesi importlardan AYRI
nesnelere bölebiliyor. Runtime importu tek tutarlı pygame nesline bağlı
taze bir modül ailesi kurar ve teardown orijinal manzarayı geri koyar.
"""
from __future__ import annotations

import importlib
import os
import pathlib
import platform
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

if not pygame.display.get_init():
    pygame.display.init()


# Runtime'da taze kurulacak display modül ailesi (kısa + src.* takma adları).
_DISPLAY_FAMILY_KEYS = (
    "platform_utils",
    "src.platform_utils",
    "sdl2_overlay",
    "src.sdl2_overlay",
    "gl_compat",
    "src.gl_compat",
)


@pytest.fixture(autouse=True)
def live_display_family(monkeypatch):
    """Test anında TUTARLI tek modül ailesi kur (kimlik-bölünmesini kapat).

    Tam koleksiyon sonrası sys.modules'teki platform_utils/sdl2_overlay/
    gl_compat/pygame kopyaları, bu dosyanın koleksiyon-zamanı importlarından
    AYRI nesneler olabiliyor (conftest _purge_leaked_test_stubs koleksiyon
    sınırları + stub-yeniden import zinciri). Bu fixture:
    1. pygame'i dosya-seviyesi nesine eşitler (C-düzeyi SDL durumu zaten
       süreç-geneldir; yalnız Python nesnesi tutarlılaştırılır),
    2. üç display modülünü bu pygame nesline bağlı TAZE import eder,
    3. sys.modules'e (kısa + src.* anahtarları) VE bu dosyanın global
       adlarına bağlar — böylece create_display/_centered_window_position
       gibi sys.modules yoklamalı kod, testin monkeypatch'lediği NESNEYİ
       görür.
    monkeypatch teardown'u orijinal sys.modules manzarasını geri koyar;
    taze importun açtığı yan-anahtarları conftest'in autouse teardown'u düşürür.
    """
    for key in _DISPLAY_FAMILY_KEYS:
        monkeypatch.delitem(sys.modules, key, raising=False)
    monkeypatch.setitem(sys.modules, "pygame", pygame)

    pu_mod = importlib.import_module("platform_utils")
    ovl_mod = importlib.import_module("sdl2_overlay")
    glc_mod = importlib.import_module("gl_compat")
    for key, mod in (
        ("platform_utils", pu_mod),
        ("src.platform_utils", pu_mod),
        ("sdl2_overlay", ovl_mod),
        ("src.sdl2_overlay", ovl_mod),
        ("gl_compat", glc_mod),
        ("src.gl_compat", glc_mod),
    ):
        monkeypatch.setitem(sys.modules, key, mod)

    test_mod = sys.modules[__name__]
    monkeypatch.setattr(test_mod, "platform_utils", pu_mod, raising=False)
    monkeypatch.setattr(test_mod, "sdl2_overlay", ovl_mod, raising=False)
    monkeypatch.setattr(test_mod, "gl_compat", glc_mod, raising=False)
    yield


class _FakeWindow:
    """SDL2 Window arayüzünü taklit eden kayıt-tutan sahte pencere.

    `readback_size` ayarlanırsa size GETTER'i yazılandan farklı değer döner
    (SDL'in min/max ya da work-area kısıtlarını simüle eder — geri okuma
    sözleşmesi için).
    """

    def __init__(self, size=(1920, 1080), position=(0, 0), borderless=True, resizable=False):
        self._size = tuple(int(v) for v in size)
        self._position = tuple(int(v) for v in position)
        self._borderless = bool(borderless)
        self._resizable = bool(resizable)
        self.readback_size = None
        self.fail_on = None
        self.size_write_calls = []
        self.position_write_calls = []
        self.borderless_write_calls = []
        self.resizable_write_calls = []

    @property
    def size(self):
        return self.readback_size or self._size

    @size.setter
    def size(self, value):
        if self.fail_on == 'size':
            raise RuntimeError('fake set_mode size failure')
        self.size_write_calls.append(tuple(int(v) for v in value))
        self._size = tuple(int(v) for v in value)

    @property
    def position(self):
        return self._position

    @position.setter
    def position(self, value):
        if self.fail_on == 'position':
            raise RuntimeError('fake position failure')
        self.position_write_calls.append(tuple(int(v) for v in value))
        self._position = tuple(int(v) for v in value)

    @property
    def borderless(self):
        return self._borderless

    @borderless.setter
    def borderless(self, value):
        if self.fail_on == 'borderless':
            raise RuntimeError('fake borderless failure')
        self.borderless_write_calls.append(bool(value))
        self._borderless = bool(value)

    @property
    def resizable(self):
        return self._resizable

    @resizable.setter
    def resizable(self, value):
        if self.fail_on == 'resizable':
            raise RuntimeError('fake resizable failure')
        self.resizable_write_calls.append(bool(value))
        self._resizable = bool(value)


class _FakeDisplay:
    """get_flags/get_size arayüzlü sahte display yüzeyi (gl_compat için)."""

    def __init__(self, flags, size):
        self._flags = int(flags)
        self._size = tuple(int(v) for v in size)

    def get_flags(self):
        return self._flags

    def get_size(self):
        return self._size


def _install_overlay(monkeypatch, window, renderer=None, background_texture=None,
                     game_surface=None, width=1920, height=1080):
    """sdl2_overlay modülünü sahte kurulum durumuyla donat."""
    monkeypatch.setattr(sdl2_overlay, '_active', True)
    monkeypatch.setattr(sdl2_overlay, '_window', window)
    monkeypatch.setattr(
        sdl2_overlay, '_game_surface',
        game_surface if game_surface is not None else pygame.Surface((1920, 1080), pygame.SRCALPHA),
    )
    monkeypatch.setattr(sdl2_overlay, '_width', width)
    monkeypatch.setattr(sdl2_overlay, '_height', height)
    monkeypatch.setattr(sdl2_overlay, '_renderer', renderer)
    monkeypatch.setattr(sdl2_overlay, '_background_texture', background_texture)


# ── apply_window_intent birim sözleşmeleri ──────────────────────────────────


def test_apply_window_intent_false_when_inactive(monkeypatch):
    window = _FakeWindow()
    _install_overlay(monkeypatch, window)
    monkeypatch.setattr(sdl2_overlay, '_active', False)

    assert sdl2_overlay.apply_window_intent(1280, 720) is False
    assert window.size_write_calls == []


def test_apply_window_intent_noop_when_state_matches(monkeypatch):
    """Aynı boyut+stil+konum → no-op (False) ve hiçbir yazım yapılmaz."""
    window = _FakeWindow(size=(1920, 1080), position=(0, 0), borderless=True, resizable=False)
    _install_overlay(monkeypatch, window)

    assert sdl2_overlay.apply_window_intent(1920, 1080, fullscreen=True) is False
    assert window.size_write_calls == []
    assert window.borderless_write_calls == []
    assert window.position_write_calls == []


def test_apply_window_intent_windowed_from_fullscreen(monkeypatch):
    """C4/C5: windowed intent görünür pencereye TAM uygulanır.

    Uygulama sırası sözleşmesi: kenar → resizable → boyut → konum.
    """
    window = _FakeWindow(size=(1920, 1080), position=(0, 0), borderless=True, resizable=False)
    _install_overlay(monkeypatch, window)

    result = sdl2_overlay.apply_window_intent(
        1280, 720,
        fullscreen=False, borderless=False, resizable=True, position=(320, 160),
    )
    assert result is True
    assert window.borderless_write_calls == [False]
    assert window.resizable_write_calls == [True]
    assert window.size_write_calls == [(1280, 720)]
    assert window.position_write_calls == [(320, 160)]
    # Gerçek boyut geri okunur → modül durumu pencereyle senkron.
    assert sdl2_overlay._width == 1280 and sdl2_overlay._height == 720


def test_apply_window_intent_fullscreen_from_windowed(monkeypatch):
    """Tam ekran intent: borderless + native boyut + (0,0)."""
    window = _FakeWindow(size=(1280, 720), position=(320, 160), borderless=False, resizable=True)
    _install_overlay(monkeypatch, window, width=1280, height=720)

    result = sdl2_overlay.apply_window_intent(1920, 1080, fullscreen=True)
    assert result is True
    assert window.borderless_write_calls == [True]
    assert window.resizable_write_calls == [False]
    assert window.size_write_calls == [(1920, 1080)]
    assert window.position_write_calls == [(0, 0)]
    assert sdl2_overlay._width == 1920 and sdl2_overlay._height == 1080


def test_apply_window_intent_same_size_mode_change_still_writes_style(monkeypatch):
    """C6: boyut AYNI ama mod değişimi → stil/konum yine uygulanır."""
    window = _FakeWindow(size=(1280, 720), position=(320, 160), borderless=False, resizable=True)
    _install_overlay(monkeypatch, window, width=1280, height=720)

    result = sdl2_overlay.apply_window_intent(1280, 720, fullscreen=True)
    assert result is True
    # Boyut yeniden yazılmaz (aynı), stil ve konum uygulanır.
    assert window.size_write_calls == []
    assert window.borderless_write_calls == [True]
    assert window.position_write_calls == [(0, 0)]


def test_apply_window_intent_reads_back_actual_size(monkeypatch):
    """SDL kısıtı simülasyonu: gerçek boyut istenenden farklı olabilir."""
    window = _FakeWindow(size=(1280, 720), borderless=False, resizable=True)
    window.readback_size = (1200, 700)
    _install_overlay(monkeypatch, window, width=1280, height=720)

    result = sdl2_overlay.apply_window_intent(1280, 720, fullscreen=False, resizable=True, position=(0, 0))
    assert result is True
    assert sdl2_overlay._width == 1200 and sdl2_overlay._height == 700


def test_apply_window_intent_rebuilds_background_texture_only_on_size_change(monkeypatch):
    """Arka plan dokusu YALNIZ boyut gerçekten değişince yeniden kurulur."""
    rebuilds = []

    def fake_build(renderer, w, h):
        rebuilds.append((int(w), int(h)))
        return None

    window = _FakeWindow(size=(1920, 1080), borderless=False, resizable=True)
    fake_renderer = object()
    _install_overlay(monkeypatch, window, renderer=fake_renderer, width=1920, height=1080)
    monkeypatch.setattr(sdl2_overlay, '_build_background_texture', fake_build)

    # Boyut değişmedi (yalnız mod değişimi) → doku yeniden kurulmaz.
    sdl2_overlay.apply_window_intent(1920, 1080, fullscreen=False, borderless=False, resizable=True, position=(0, 0))
    assert rebuilds == []

    # Boyut değişti → doku YENİ gerçek boyutla kurulur.
    sdl2_overlay.apply_window_intent(1600, 900, fullscreen=True)
    assert rebuilds == [(1600, 900)]


def test_apply_window_intent_rolls_back_on_error(monkeypatch):
    """Pencere güncellemesi hata verirse önceki durum geri yüklenir (rollback)."""
    window = _FakeWindow(size=(1920, 1080), position=(0, 0), borderless=True, resizable=False)
    _install_overlay(monkeypatch, window)
    window.fail_on = 'size'

    result = sdl2_overlay.apply_window_intent(1280, 720, fullscreen=False, borderless=False, resizable=True, position=(320, 160))
    assert result is False
    # borderless False yazıldı, hata sonrası rollback True'ya döndürdü.
    assert window.borderless_write_calls == [False, True]
    assert window.resizable_write_calls == [True, False]
    # size yazımı patladı; pencere boyutu değişmedi.
    assert window._size == (1920, 1080)
    # Modül durumu da eski boyutta kaldı.
    assert sdl2_overlay._width == 1920 and sdl2_overlay._height == 1080


def test_apply_window_intent_invalid_size_returns_false(monkeypatch):
    window = _FakeWindow()
    _install_overlay(monkeypatch, window)

    assert sdl2_overlay.apply_window_intent(None, 'x') is False
    assert window.size_write_calls == []


def test_centered_window_position_uses_work_area(monkeypatch):
    """Demo uyarlaması: get_desktop_work_area() (w, h) → (0,0) kökenli merkezleme."""
    monkeypatch.setattr(platform_utils, 'get_desktop_work_area', lambda: (1772, 928))
    pos = sdl2_overlay._centered_window_position(1280, 660)
    assert pos == ((1772 - 1280) // 2, (928 - 660) // 2)


def test_centered_window_position_falls_back_to_desktop_sizes(monkeypatch):
    monkeypatch.setattr(platform_utils, 'get_desktop_work_area', lambda: (0, 0))
    monkeypatch.setattr(pygame.display, 'get_desktop_sizes', lambda: [(1920, 1080)])
    pos = sdl2_overlay._centered_window_position(1280, 720)
    assert pos == ((1920 - 1280) // 2, (1080 - 720) // 2)


def test_centered_window_position_none_without_any_measure(monkeypatch):
    monkeypatch.setattr(platform_utils, 'get_desktop_work_area', lambda: (0, 0))
    monkeypatch.setattr(pygame.display, 'get_desktop_sizes', lambda: [])
    assert sdl2_overlay._centered_window_position(1280, 720) is None


def test_get_actual_window_size(monkeypatch):
    window = _FakeWindow(size=(1234, 567))
    _install_overlay(monkeypatch, window)
    assert sdl2_overlay.get_actual_window_size() == (1234, 567)

    monkeypatch.setattr(sdl2_overlay, '_active', False)
    assert sdl2_overlay.get_actual_window_size() == (0, 0)


# ── create_display ↔ overlay intent bütünleşmesi ────────────────────────────


def _pin_display_geometry(monkeypatch, set_mode_spy):
    """Clamp kaynaklarını deterministik yap; set_mode'u casusa bağla.

    Demo uyarlaması: work-area kaynağı get_desktop_work_area() (w, h)'dir
    (v2'deki Rect tabanlı get_work_area DEĞİL).
    """
    monkeypatch.setattr(platform_utils, 'get_native_resolution', lambda: (1920, 1080))
    monkeypatch.setattr(platform_utils, 'get_desktop_work_area', lambda: (1920, 1040))
    monkeypatch.setattr(
        pygame.display, 'set_mode',
        lambda *a, **k: set_mode_spy.append((a, k)) or pygame.Surface((640, 480)),
    )


def test_create_display_applies_windowed_intent_to_visible_window(monkeypatch):
    """C4: overlay aktifken set_mode ATLANIR, intent clamp'li boyutla uygulanır.

    Boyut 1920x1080 native / 1920x1040 work-area altında → clamp yok;
    konum work-area ortalaması ((1920-1280)//2, (1040-720)//2) = (320, 160).
    """
    window = _FakeWindow(size=(1920, 1080), position=(0, 0), borderless=True, resizable=False)
    _install_overlay(monkeypatch, window)
    set_mode_spy = []
    _pin_display_geometry(monkeypatch, set_mode_spy)

    surf = platform_utils.create_display(1280, 720, fullscreen=False, resizable=True)

    assert set_mode_spy == []  # TEK PENCERE: set_mode çağrılmadı
    assert surf is sdl2_overlay._game_surface
    assert window.borderless_write_calls == [False]
    assert window.resizable_write_calls == [True]
    assert window.size_write_calls == [(1280, 720)]
    assert window.position_write_calls == [(320, 160)]
    assert sdl2_overlay._width == 1280 and sdl2_overlay._height == 720


def test_create_display_clamps_oversized_windowed_intent(monkeypatch):
    """4K senaryosu (demo): native'i AŞAN istek ORANSAL clamp'ten geçer.

    Demo clamp'i v2'nin sabit (1600,900) merdiveni yerine
    clamp_window_size_to_work_area ile oransaldır → tam değer yerine
    SINIR sözleşmesi doğrulanır: yazılan boyut work-area'yı AŞMAZ ve konum
    work-area ortalamasıdır.
    """
    window = _FakeWindow(size=(1920, 1080), position=(0, 0), borderless=True, resizable=False)
    _install_overlay(monkeypatch, window)
    set_mode_spy = []
    _pin_display_geometry(monkeypatch, set_mode_spy)

    platform_utils.create_display(2560, 1440, fullscreen=False, resizable=True)

    assert set_mode_spy == []
    assert len(window.size_write_calls) == 1
    clamped_w, clamped_h = window.size_write_calls[0]
    assert clamped_w <= 1920 and clamped_h <= 1040, (
        f"clamp edilen boyut work-area'yı aşıyor: {(clamped_w, clamped_h)}"
    )
    assert clamped_w > 1280, "aşırı istek oransal clamp ile anlamlı küçülme görmeli"
    expected_pos = ((1920 - clamped_w) // 2, (1040 - clamped_h) // 2)
    assert window.position_write_calls == [expected_pos]


def test_create_display_fullscreen_intent_keeps_single_window(monkeypatch):
    """Tam ekran intent: set_mode atlanır, pencere borderless+(0,0)+native."""
    window = _FakeWindow(size=(1280, 720), position=(320, 160), borderless=False, resizable=True)
    _install_overlay(monkeypatch, window, width=1280, height=720)
    set_mode_spy = []
    _pin_display_geometry(monkeypatch, set_mode_spy)

    surf = platform_utils.create_display(1920, 1080, fullscreen=True, resizable=False, borderless=True)

    assert set_mode_spy == []
    assert surf is sdl2_overlay._game_surface
    assert window.borderless_write_calls == [True]
    assert window.size_write_calls == [(1920, 1080)]
    assert window.position_write_calls == [(0, 0)]


def test_create_display_glcompat_noop_returns_surface_without_set_mode(monkeypatch):
    """gl_compat aktif + gerçek no-op → set_mode atlanır, GL context korunur."""
    monkeypatch.setattr(gl_compat, '_active', True)
    fake_surface = pygame.Surface((640, 480), pygame.SRCALPHA)
    monkeypatch.setattr(gl_compat, '_game_surface', fake_surface)
    pygame.display.set_mode((640, 480), pygame.RESIZABLE)
    set_mode_spy = []
    _pin_display_geometry(monkeypatch, set_mode_spy)

    surf = platform_utils.create_display(640, 480, fullscreen=False, resizable=True)

    assert set_mode_spy == []
    assert surf is fake_surface


def test_create_display_glcompat_change_request_runs_set_mode(monkeypatch):
    """gl_compat aktif + değişiklik isteği → set_mode YOLU ÇALIŞIR (yutulmaz)."""
    monkeypatch.setattr(gl_compat, '_active', True)
    fake_surface = pygame.Surface((640, 480), pygame.SRCALPHA)
    monkeypatch.setattr(gl_compat, '_game_surface', fake_surface)
    pygame.display.set_mode((640, 480), pygame.RESIZABLE)
    set_mode_spy = []
    _pin_display_geometry(monkeypatch, set_mode_spy)

    surf = platform_utils.create_display(800, 600, fullscreen=False, resizable=True)

    assert len(set_mode_spy) == 1  # değişiklik set_mode'a düştü
    assert tuple(set_mode_spy[0][0][0]) == (800, 600)
    assert surf is not fake_surface  # gerçek (stub) display yüzeyi döndü


# ── gl_compat wrapper (C6) ──────────────────────────────────────────────────


def test_intent_matches_current_window_matrix(monkeypatch):
    """Stil intent eşleşme matrisi: pencere/tam ekran × flag kombinasyonları."""
    cases = [
        # (display_flags, kwargs, beklenen)
        (pygame.RESIZABLE, dict(fullscreen=False, resizable=True), True),
        (pygame.RESIZABLE, dict(fullscreen=False, resizable=False), False),
        (0, dict(fullscreen=False, resizable=False), True),
        (0, dict(fullscreen=False, resizable=True), False),
        (pygame.RESIZABLE, dict(fullscreen=True, borderless=True), False),
        (pygame.NOFRAME, dict(fullscreen=True, borderless=True), True),
        (pygame.NOFRAME, dict(fullscreen=True, borderless=False), False),
        (pygame.FULLSCREEN, dict(fullscreen=True, borderless=False), True),
        (pygame.FULLSCREEN | pygame.RESIZABLE, dict(fullscreen=True, borderless=False), False),
        (pygame.NOFRAME | pygame.RESIZABLE, dict(fullscreen=True, borderless=True), False),
        # Varsayılan kwargs (create_display imza varsayılanları): windowed + resizable.
        (pygame.RESIZABLE, dict(), True),
        (0, dict(), False),
    ]
    for flags, kwargs, expected in cases:
        monkeypatch.setattr(
            gl_compat, 'get_display_surface',
            lambda f=flags: _FakeDisplay(f, (1920, 1080)),
        )
        assert gl_compat._intent_matches_current_window(kwargs) is expected, (
            f"flags=0x{flags:X} kwargs={kwargs} beklenen={expected}"
        )


def test_intent_matches_current_window_none_display(monkeypatch):
    monkeypatch.setattr(gl_compat, 'get_display_surface', lambda: None)
    assert gl_compat._intent_matches_current_window(dict(fullscreen=False, resizable=True)) is False


@pytest.mark.skipif(platform.system() != 'Windows', reason="wrapper koşulu Windows'a özgü")
def test_gl_create_display_wrapper_skips_on_true_noop(monkeypatch):
    """Boyut + stil intent eşleşiyorsa orijinal create_display çağrılmaz."""
    monkeypatch.setattr(gl_compat, '_active', True)
    fake_surface = pygame.Surface((1920, 1080), pygame.SRCALPHA)
    monkeypatch.setattr(gl_compat, '_game_surface', fake_surface)
    monkeypatch.setattr(gl_compat, '_width', 1920)
    monkeypatch.setattr(gl_compat, '_height', 1080)
    monkeypatch.setattr(
        gl_compat, 'get_display_surface',
        lambda: _FakeDisplay(pygame.OPENGL | pygame.RESIZABLE, (1920, 1080)),
    )

    def _original_must_not_run(*a, **k):
        raise AssertionError('no-op istekte orijinal create_display çağrılmamalı')

    wrapper = gl_compat._get_gl_create_display_wrapper(_original_must_not_run)
    assert wrapper(1920, 1080, fullscreen=False, resizable=True) is fake_surface


@pytest.mark.skipif(platform.system() != 'Windows', reason="wrapper koşulu Windows'a özgü")
def test_gl_create_display_wrapper_falls_through_on_size_change(monkeypatch):
    """İstenen boyut farklıysa erken dönüş YAPILMAZ (eski C6 davranışı)."""
    monkeypatch.setattr(gl_compat, '_active', True)
    fake_surface = pygame.Surface((1920, 1080), pygame.SRCALPHA)
    monkeypatch.setattr(gl_compat, '_game_surface', fake_surface)
    monkeypatch.setattr(gl_compat, '_width', 1920)
    monkeypatch.setattr(gl_compat, '_height', 1080)
    monkeypatch.setattr(
        gl_compat, 'get_display_surface',
        lambda: _FakeDisplay(pygame.OPENGL | pygame.RESIZABLE, (1920, 1080)),
    )
    reapply_calls = []
    monkeypatch.setattr(
        gl_compat, '_reapply_gl',
        lambda surf: reapply_calls.append(surf) or surf,
    )

    stub_result = pygame.Surface((1280, 720), pygame.SRCALPHA)

    def _original(*a, **k):
        original_calls.append((a, k))
        return stub_result

    original_calls = []
    wrapper = gl_compat._get_gl_create_display_wrapper(_original)

    result = wrapper(1280, 720, fullscreen=False, resizable=True)
    assert original_calls == [((1280, 720), dict(fullscreen=False, resizable=True))]
    assert reapply_calls == [stub_result]
    assert result is stub_result


@pytest.mark.skipif(platform.system() != 'Windows', reason="wrapper koşulu Windows'a özgü")
def test_gl_create_display_wrapper_falls_through_on_intent_mismatch(monkeypatch):
    """Boyut AYNI ama stil intent farklı → erken dönüş YAPILMAZ (C6)."""
    monkeypatch.setattr(gl_compat, '_active', True)
    fake_surface = pygame.Surface((1920, 1080), pygame.SRCALPHA)
    monkeypatch.setattr(gl_compat, '_game_surface', fake_surface)
    monkeypatch.setattr(gl_compat, '_width', 1920)
    monkeypatch.setattr(gl_compat, '_height', 1080)
    monkeypatch.setattr(
        gl_compat, 'get_display_surface',
        lambda: _FakeDisplay(pygame.OPENGL | pygame.RESIZABLE, (1920, 1080)),
    )
    monkeypatch.setattr(gl_compat, '_reapply_gl', lambda surf: surf)

    original_calls = []

    def _original(*a, **k):
        original_calls.append((a, k))
        return fake_surface

    wrapper = gl_compat._get_gl_create_display_wrapper(_original)
    result = wrapper(1920, 1080, fullscreen=True, borderless=True)
    assert original_calls == [((1920, 1080), dict(fullscreen=True, borderless=True))]
    assert result is fake_surface


# ── Kaynak sözleşmeleri (intent zinciri sırası) ─────────────────────────────


def _platform_utils_source() -> str:
    return pathlib.Path(platform_utils.__file__).read_text(encoding='utf-8')


def _main_source() -> str:
    return (pathlib.Path(__file__).resolve().parent.parent / 'src' / 'main.py').read_text(encoding='utf-8')


def test_create_display_intent_applied_after_work_area_clamp():
    """Sıra sözleşmesi: intent, normalizasyon + work-area clamp'inden SONRA.

    Demo uyarlaması: create_display'te _set_mode_with_vsync YOKTUR —
    sabitleme noktası macOS dalıdır (overlay dalı ondan önce döner).
    """
    source = _platform_utils_source()
    cd_start = source.index('def create_display(')
    cd_end = source.index('\ndef ', cd_start + 10)
    body = source[cd_start:cd_end]
    assert 'clamp_window_size_to_work_area(width, height)' in body
    assert 'apply_window_intent' in body
    assert body.index('clamp_window_size_to_work_area(width, height)') < body.index('apply_window_intent')
    # Overlay dalı macOS/set_mode yolundan ÖNCE döner (erken dönüş).
    assert body.index('apply_window_intent') < body.index('if IS_MACOS:')


def test_setup_window_creation_is_intent_aware():
    """setup() pencere yaratımı intent alır (açılış BUG B düzeltmesi)."""
    source = pathlib.Path(sdl2_overlay.__file__).read_text(encoding='utf-8')
    setup_start = source.index('def setup(')
    setup_end = source.index('\ndef ', setup_start + 10)
    body = source[setup_start:setup_end]
    assert 'want_borderless = True if _fs else False' in body
    assert 'win.borderless = want_borderless' in body
    assert 'win.resizable' in body
    assert '_centered_window_position' in body


def test_gl_overlay_setup_passes_intent_to_setup():
    """gl_overlay_setup intent kwargs'larını setup()'a aktarır."""
    source = pathlib.Path(sdl2_overlay.__file__).read_text(encoding='utf-8')
    gls_start = source.index('def gl_overlay_setup(')
    gls_end = source.index('\ndef ', gls_start + 10)
    body = source[gls_start:gls_end]
    assert 'fullscreen=fullscreen' in body
    assert 'resizable=resizable' in body


def test_main_startup_passes_intent_to_gl_overlay_setup():
    """main.py açılışı overlay kurulumuna intent'i geçirir (C4/C5 zinciri)."""
    source = re.sub(r"\s+", " ", _main_source())
    assert re.search(
        r"_ovl\.gl_overlay_setup\( screen, fullscreen=startup_fullscreen, "
        r"borderless=startup_borderless, resizable=\(not startup_fullscreen\), \)",
        source,
    ), "main.py startup intent aktarımı kayboldu"
