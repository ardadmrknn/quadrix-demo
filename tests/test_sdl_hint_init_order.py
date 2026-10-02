# -*- coding: utf-8 -*-
"""FAZ A2: SDL hint init sırası, texture format sorgusu, blit cache + erişimci bildirimi.

Gorsel_Olcek_Sorunlari_Cozum_Plani.md FAZ A2 kabul kriterlerinin testleri:
1. SDL_RENDER_SCALE_QUALITY hint'i Renderer/Texture oluşturulmasından ÖNCE
   kurulur — init sırası test tarafından SAHTE Window/Renderer/Texture
   sınıflarıyla saptanır (setup zincirine enjekte edilip çağrı sırası
   kaydedilir; plan: "mock sırasıyla saptanır").
2. _set_scale_quality_hint: SDL_SetHint sözleşmesi + ctypes yokluğunda env
   fallback'i (setdefault — mevcut değeri EZMEZ).
3. Texture pixel formatı runtime sorgusu setup log kaydına girer (ölçümdür,
   eşik değildir — A9 performans kapısı baseline'a göre eşik koyar).
4. platform_utils._blit_canvas_to_display: letterbox geometrisi değişmedikçe
   subsurface + fill rect'leri YENİDEN KULLANILIR (kare-başı nesne tahsisi
   kırmızı çizgisi — identity kanıtı); geometri değişince taze üretilir.
5. teardown sonrası get_canvas_size() inactive erişimi BİR KEZ diag kanalıyla
   bildirilir (sessiz kanonik dönüş kalmaz; tekrarı gürültü üretmez).

Canlı testtir (gerçek pygame, SDL_VIDEODRIVER=dummy; stub pytest ortamında
atlanır). Disk yazımı olmamalı: _diag_log monkeypatch'la yakalanır.
Önc-var kırmızı yok: bu dosya FAZ A2 ile birlikte eklendi.
"""

from __future__ import annotations

import ctypes
import os
import sys
import types

import pytest

# Modül seviyesinde (koleksiyon anı = temiz süreç durumu) gerçek pygame'i
# bağla (A4 kalıbı; süit ortasında taze import WinError 206 verebiliyor).
import pygame


def _ensure_src_on_path() -> None:
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    src_path = os.path.join(repo_root, 'src')
    if src_path in sys.path:
        sys.path.remove(src_path)
    sys.path.insert(0, src_path)


@pytest.fixture(scope='module')
def live_env():
    """Gerçek modülleri yükle; pygame'i dummy sürücüyle hazırla (A4 kalıbı)."""
    os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
    os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
    _ensure_src_on_path()

    _module_keys = [
        'sdl2_overlay', 'gl_compat', 'platform_utils', 'ui_scaling',
        'constants', 'retro_style', 'localization',
    ]
    _module_lookup_keys = [
        key
        for mod in _module_keys
        for key in (mod, f'src.{mod}')
    ]
    # Pygame ailesi anlık görüntüsü: teardown'da kök + tüm alt modüller tek
    # transaction'da geri konur (K4'de kanıtlanan aile-yarım-kalma mayınına
    # karşı; conftest koleksiyon-sınırı aile purge'üyle aynı gerekçe).
    _pygame_family_leaked = {
        key: mod for key, mod in list(sys.modules.items())
        if key == 'pygame' or key.startswith('pygame.')
    }
    _pygame_leaked = sys.modules.get('pygame')
    if _pygame_leaked is not pygame:
        sys.modules['pygame'] = pygame

    _original_modules = {key: sys.modules.get(key) for key in _module_lookup_keys}
    for key in _module_lookup_keys:
        sys.modules.pop(key, None)

    if not hasattr(pygame, 'K_h'):
        pytest.skip('pygame stub environment')

    pygame.init()
    if not pygame.display.get_init():
        pygame.display.init()

    import sdl2_overlay
    import platform_utils

    assert sys.modules['sdl2_overlay'] is sdl2_overlay
    assert sys.modules['platform_utils'] is platform_utils

    yield types.SimpleNamespace(
        pygame=pygame, sdl2_overlay=sdl2_overlay, platform_utils=platform_utils,
    )

    try:
        sdl2_overlay.teardown()
    except Exception:
        pass
    try:
        platform_utils._teardown_virtual_canvas()
    except Exception:
        pass
    try:
        platform_utils.unpatch_event_queue()
    except Exception:
        pass
    for _key, _original in _original_modules.items():
        if _original is not None:
            sys.modules[_key] = _original
        else:
            sys.modules.pop(_key, None)
    # Aile-tutarlı geri koyma: önce kök + alt modüllerin hepsini sök, sonra
    # kurulum anındaki anlık görüntüyü aynen geri koy.
    for _key in [
        k for k in list(sys.modules)
        if k == 'pygame' or k.startswith('pygame.')
    ]:
        sys.modules.pop(_key, None)
    for _key, _mod in _pygame_family_leaked.items():
        sys.modules[_key] = _mod


# ---------------------------------------------------------------------------
# 1) Hint fonksiyonu sözleşmesi (SDL_SetHint + env fallback)
# ---------------------------------------------------------------------------

def test_scale_quality_hint_calls_sdl_sethint(live_env, monkeypatch):
    """Başarı yolu: SDL_SetHint'e doğru anahtar/değer gider, True döner."""
    sdl2 = live_env.sdl2_overlay
    calls = []

    class _FakeDll:
        def SDL_SetHint(self, name, value):
            calls.append((name, value))

    monkeypatch.setattr(ctypes.cdll, 'LoadLibrary', lambda name: _FakeDll())
    assert sdl2._set_scale_quality_hint() is True
    assert calls == [(b'SDL_RENDER_SCALE_QUALITY', b'0')], (
        f"SDL_SetHint birebir bu çağrıyı yapmalı: {calls}"
    )


def test_scale_quality_hint_env_fallback_setdefault(live_env, monkeypatch):
    """ctypes/DLL yokluğunda env fallback'i KURULUR ama mevcut değeri EZMEZ."""
    sdl2 = live_env.sdl2_overlay

    def _raising_load(name):
        raise RuntimeError('sahte DLL yokluğu')

    monkeypatch.setattr(ctypes.cdll, 'LoadLibrary', _raising_load)
    monkeypatch.delenv('SDL_HINT_RENDER_SCALE_QUALITY', raising=False)
    monkeypatch.delenv('SDL_RENDER_SCALE_QUALITY', raising=False)

    assert sdl2._set_scale_quality_hint() is False
    assert os.environ.get('SDL_HINT_RENDER_SCALE_QUALITY') == '0'

    # setdefault semantiği: mevcut değer korunur.
    monkeypatch.setenv('SDL_HINT_RENDER_SCALE_QUALITY', '2')
    sdl2._set_scale_quality_hint()
    assert os.environ['SDL_HINT_RENDER_SCALE_QUALITY'] == '2', (
        "fallback mevcut env değerini ezmemeli (setdefault sözleşmesi)"
    )


# ---------------------------------------------------------------------------
# 2) İnit sırası: hint Renderer/Texture'dan ÖNCE (mock sırasıyla saptanır)
# ---------------------------------------------------------------------------

def test_hint_precedes_renderer_and_texture(live_env, monkeypatch):
    """setup() zincirinde SDL hint çağrısı Renderer ve Texture kurulumundan
    ÖNCE gelir; texture format sorgusu da log kaydına girer.

    Sahte Window/Renderer/Texture sınıfları sys.modules['pygame._sdl2.video']
    üzerinden enjekte edilir (setup gövdesi `from pygame._sdl2.video import
    ...` yapar → sahteler zincire girer). _build_background_texture ve
    _set_scale_quality_hint da kayıt toplayan monkeypatch'larla sarılır.
    """
    sdl2 = live_env.sdl2_overlay
    order = []
    diag = []

    class _FakeWindow:
        def __init__(self, *args, **kwargs):
            self.size = tuple(kwargs.get('size', (0, 0)))
            order.append('window')

        @classmethod
        def from_display_module(cls):
            return cls()

        def hide(self):
            pass

        def show(self):
            pass

        def focus(self):
            pass

        def destroy(self):
            pass

    class _FakeRenderer:
        def __init__(self, win, vsync=None):
            order.append('renderer')

        def present(self):
            pass

        def blit(self, *args, **kwargs):
            pass

        def destroy(self):
            pass

    class _FakeTexture:
        def __init__(self, renderer, size, streaming=False):
            self._size = tuple(size)
            order.append('texture')

        def query(self):
            # ARGB8888'imsi sabit — log formatının yalnızca görünür olması
            # için; gerçek değer SDL sürücüsüne aittir.
            return (0x16362004, 1, self._size[0], self._size[1])

        def update(self, *args, **kwargs):
            pass

        def destroy(self):
            pass

    fake_video = types.ModuleType('pygame._sdl2.video')
    fake_video.Window = _FakeWindow
    fake_video.Renderer = _FakeRenderer
    fake_video.Texture = _FakeTexture
    fake_video.get_drivers = lambda: []
    monkeypatch.setitem(sys.modules, 'pygame._sdl2.video', fake_video)

    monkeypatch.setattr(sdl2, '_should_use_sdl2', lambda: True)
    monkeypatch.setattr(sdl2, '_hide_setmode_window_from_taskbar', lambda: None)
    monkeypatch.setattr(
        sdl2, '_set_scale_quality_hint',
        lambda: order.append('hint') or True,
    )
    monkeypatch.setattr(
        sdl2, '_build_background_texture',
        lambda renderer, w, h: _FakeTexture(renderer, (w, h)),
    )
    monkeypatch.setattr(sdl2, '_present', lambda *a, **k: None)
    monkeypatch.setattr(sdl2, '_diag_log', lambda msg: diag.append(msg))

    real_surface = live_env.pygame.display.set_mode((1280, 720))
    try:
        game_surface = sdl2.setup(real_surface)
        assert game_surface is not None, "sahte zincirde setup başarılı olmalı"

        # SIRA SÖZLEŞMESİ (FAZ A2 madde 1): hint Renderer'dan VE Texture'dan
        # önce. SDL bu hint'i kurulum anında okur — sonrası etkisizdir.
        assert 'hint' in order and 'renderer' in order and 'texture' in order, (
            f"zincirde window/renderer/texture/hint görünmeli: {order}"
        )
        assert order.index('hint') < order.index('renderer'), (
            f"hint Renderer'dan ÖNCE kurulmalı: {order}"
        )
        assert order.index('hint') < order.index('texture'), (
            f"hint Texture'dan ÖNCE kurulmalı: {order}"
        )
        assert order[0] == 'window', (
            f"zincir ilk adımı sahte Window kurulumu olmalı: {order}"
        )

        # FAZ A2 madde 2: texture format sorgusu log kaydında.
        fmt_logs = [m for m in diag if 'texture format=' in m]
        assert len(fmt_logs) == 1, f"tek format satırı bekleniyordu: {fmt_logs}"
        assert '0x' in fmt_logs[0] and 'access=' in fmt_logs[0]
        assert 'game_surface bytes=' in fmt_logs[0]
        assert 'srcalpha=' in fmt_logs[0]
    finally:
        try:
            sdl2.teardown()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# 3) Blit letterbox cache (kare-başı tahsis kırmızı çizgisi)
# ---------------------------------------------------------------------------

def test_blit_letterbox_cache_reuses_objects(live_env):
    """Geometri değişmedikçe subsurface + fill rect'leri yeniden kullanılır;
    canvas/boyut değişince taze üretilir. Identity kanıtı."""
    pu = live_env.platform_utils
    pygame = live_env.pygame

    real = pygame.display.set_mode((2560, 1440))
    # GERÇEK kurulum akışı: 2560x1440 display @ preset 100 → canvas 1920x1080
    # (kılavuzun 4K tuval sözleşmesi) → letterbox blit dalı + flip/get_surface
    # patch'leri kurulur (üretimde _blit_canvas_to_display ancak bu patch'ler
    # üzerinden çağrılır; pass-through dalı cache testini işletemez).
    pu.setup_virtual_canvas(real, 1.0)
    assert pu._software_scale_active, (
        "gerçek ölçekleme dalı kurulmalı — pass-through'da blit cache yolu yok"
    )
    canvas = pygame.Surface((960, 540), pygame.SRCALPHA)
    pu._software_canvas = canvas
    try:
        # 16:9 canvas @16:9 display → bant yok (fill'ler None cache'lenir).
        pu._blit_canvas_to_display()
        snapshot = pu._blit_letterbox_cache
        assert snapshot[0] is not None, "cache anahtarı kurulmalı"
        assert snapshot[2] is None and snapshot[5] is None, (
            "bant yokken fill rect'leri None olarak cache'lenmeli (0-genişlik "
            "Rect tahsis etme)"
        )
        sub_first = snapshot[1]

        # İkinci kare: AYNI nesneler (kare-başı tahsis yok).
        pu._blit_canvas_to_display()
        assert pu._blit_letterbox_cache is snapshot, (
            "geometri değişmedi — cache tuple'ı yeniden üretilmemeli"
        )
        assert pu._blit_letterbox_cache[1] is sub_first, (
            "subsurface nesnesi yeniden kullanılmalı"
        )

        # 4:3 canvas @16:9 display → yan bantlar var; yeni anahtar + dolu
        # fill rect'leri (taze nesneler).
        canvas_43 = pygame.Surface((960, 720), pygame.SRCALPHA)
        pu._software_canvas = canvas_43
        pu._blit_canvas_to_display()
        assert pu._blit_letterbox_cache is not snapshot, (
            "canvas boyutu değişti — cache yenilenmeli"
        )
        assert pu._blit_letterbox_cache[2] is not None, (
            "yan bant varken sol fill rect'i dolu olmalı"
        )
        assert pu._blit_letterbox_cache[1] is not sub_first

        # Display değişimi (resize) de cache'i yeniler.
        real2 = pygame.display.set_mode((1600, 900))
        pu._real_display_surface = real2
        pu._blit_canvas_to_display()
        stale = pu._blit_letterbox_cache
        assert stale is not None and stale[0][1] != snapshot[0][1]

        # Teardown (patch'ler bizim → TAM YOL) cache'i sıfırlar: parent yüzey
        # söküldü, subsurface/rect'ler bayattı. FAZ A4'ün "sökülecek bir şey
        # yok" erken çıkışı yalnızca patch'siz-boş durumda tetiklenir.
        pu._teardown_virtual_canvas()
        assert pu._blit_letterbox_cache[0] is None, (
            "teardown letterbox cache'ini sıfırlamalı (parent yüzey bayat)"
        )
    finally:
        pu._software_canvas = None
        pu._real_display_surface = None
        pu._software_scale_active = False
        pu._virtual_blit_rect = None
        try:
            pu._teardown_virtual_canvas()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# 4) get_canvas_size: inactive erişim BİR KEZ bildirilir (madde 4)
# ---------------------------------------------------------------------------

def test_get_canvas_size_inactive_logs_once(live_env, monkeypatch):
    sdl2 = live_env.sdl2_overlay
    logs = []
    monkeypatch.setattr(sdl2, '_diag_log', lambda msg: logs.append(msg))
    # İzolasyon: bayrak taze modül durumu.
    sdl2._canvas_size_inactive_logged = False
    sdl2._game_surface = None
    sdl2._active = False
    try:
        # Kanonik sözleşme korunur (DUZ-011/013: erişimci asla patlamaz).
        assert sdl2.get_canvas_size() == (1920, 1080)
        inactive = [m for m in logs if 'INACTIVE' in m]
        assert len(inactive) == 1, (
            f"inactive erişim BİR KEZ bildirilmeli: {inactive}"
        )

        # Tekrarları gürültü üretmez.
        sdl2.get_canvas_size()
        sdl2.get_canvas_size()
        assert len([m for m in logs if 'INACTIVE' in m]) == 1

        # _game_surface doluyken bildirim yok (aktif kaynaktan okur).
        sdl2._game_surface = live_env.pygame.Surface((1536, 864))
        assert sdl2.get_canvas_size() == (1536, 864)
        assert len([m for m in logs if 'INACTIVE' in m]) == 1
    finally:
        sdl2._game_surface = None
        sdl2._canvas_size_inactive_logged = False
