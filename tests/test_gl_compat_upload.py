from __future__ import annotations

import os
import sys
import types

import pygame


SRC_DIR = os.path.join(os.path.dirname(__file__), '..', 'src')
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

import gl_compat


class DummySurface:
    def __init__(self, *, width=8, bitsize=32, bytesize=4, pitch=32, masks=(0x00FF0000, 0x0000FF00, 0x000000FF, 0)):
        self._width = width
        self._bitsize = bitsize
        self._bytesize = bytesize
        self._pitch = pitch
        self._masks = masks
        self._buffer = bytearray(pitch * 4)

    def get_size(self):
        return (self._width, 4)

    def get_bitsize(self):
        return self._bitsize

    def get_bytesize(self):
        return self._bytesize

    def get_pitch(self):
        return self._pitch

    def get_masks(self):
        return self._masks

    def get_buffer(self):
        return self._buffer


def test_get_upload_source_prefers_direct_buffer_for_compatible_surface(monkeypatch):
    surface = DummySurface()

    def _unexpected_tostring(*args, **kwargs):
        raise AssertionError('fallback tostring yolu kullanilmamali')

    monkeypatch.setattr(pygame.image, 'tostring', _unexpected_tostring)
    monkeypatch.setattr(gl_compat, '_can_use_direct_bgra_upload', lambda: True)

    gl_format, payload, flip_y = gl_compat._get_upload_source(surface)

    assert gl_format == gl_compat.GL_BGRA
    assert payload is surface.get_buffer()
    assert flip_y is False


def test_get_upload_source_falls_back_for_incompatible_surface(monkeypatch):
    surface = DummySurface(bitsize=24, bytesize=3, pitch=24)
    calls: list[tuple[object, str, bool]] = []

    def _fake_tostring(src_surface, fmt, flipped):
        calls.append((src_surface, fmt, flipped))
        return b'rgba-bytes'

    monkeypatch.setattr(pygame.image, 'tostring', _fake_tostring)
    monkeypatch.setattr(gl_compat, '_can_use_direct_bgra_upload', lambda: True)

    gl_format, payload, flip_y = gl_compat._get_upload_source(surface)

    assert gl_format == gl_compat.GL_RGBA
    assert payload == b'rgba-bytes'
    assert flip_y is True
    assert calls == [(surface, 'RGBA', True)]


def test_get_upload_source_falls_back_when_bgra_upload_is_unsupported(monkeypatch):
    surface = DummySurface()
    calls: list[tuple[object, str, bool]] = []

    def _fake_tostring(src_surface, fmt, flipped):
        calls.append((src_surface, fmt, flipped))
        return b'rgba-bytes'

    monkeypatch.setattr(pygame.image, 'tostring', _fake_tostring)
    monkeypatch.setattr(gl_compat, '_can_use_direct_bgra_upload', lambda: False)

    gl_format, payload, flip_y = gl_compat._get_upload_source(surface)

    assert gl_format == gl_compat.GL_RGBA
    assert payload == b'rgba-bytes'
    assert flip_y is True
    assert calls == [(surface, 'RGBA', True)]


def test_patch_create_display_module_refs_updates_preimported_references():
    def original_create_display(width, height, **kwargs):
        return (width, height, kwargs)

    def wrapped_create_display(width, height, **kwargs):
        return ('wrapped', width, height, kwargs)

    fake_platform_utils = types.ModuleType('fake_platform_utils')
    fake_platform_utils.create_display = original_create_display

    consumer_module = types.ModuleType('consumer_module')
    consumer_module.create_display = original_create_display

    unrelated_module = types.ModuleType('unrelated_module')
    unrelated_module.create_display = lambda *args, **kwargs: None

    gl_compat._patch_create_display_module_refs(
        [fake_platform_utils, consumer_module, unrelated_module],
        {original_create_display: wrapped_create_display},
    )

    assert fake_platform_utils.create_display is wrapped_create_display
    assert consumer_module.create_display is wrapped_create_display
    assert unrelated_module.create_display is not wrapped_create_display


# ---------------------------------------------------------------------------
# Tek-context (single-context) koordinasyon testleri
# ---------------------------------------------------------------------------

def test_prepare_single_context_sets_request_when_gl_available(monkeypatch):
    """Windows + Steam + GL mevcutken platform_utils'e GL pencere talebi iletilir."""
    import platform_utils

    monkeypatch.setattr(gl_compat, '_should_use_gl', lambda: True)
    recorded = {}
    monkeypatch.setattr(
        platform_utils,
        'set_gl_window_request',
        lambda enabled: recorded.__setitem__('value', enabled),
    )

    result = gl_compat.prepare_single_context()

    assert result is True
    assert recorded.get('value') is True


def test_prepare_single_context_disables_request_when_unavailable(monkeypatch):
    """GL kullanılamıyorsa talep False yapılır ve fonksiyon False döner."""
    import platform_utils

    monkeypatch.setattr(gl_compat, '_should_use_gl', lambda: False)
    recorded = {}
    monkeypatch.setattr(
        platform_utils,
        'set_gl_window_request',
        lambda enabled: recorded.__setitem__('value', enabled),
    )

    result = gl_compat.prepare_single_context()

    assert result is False
    assert recorded.get('value') is False


def test_should_use_gl_false_on_non_windows(monkeypatch):
    """Windows dışı platformda GL yolu devre dışıdır (Gereksinim 6)."""
    monkeypatch.setattr(gl_compat.platform, 'system', lambda: 'Darwin')
    assert gl_compat._should_use_gl() is False


# ---------------------------------------------------------------------------
# Strict-return: tek-context'te GL kurulamazsa ham GL surface DÖNDÜRÜLMEMELİ
# (kalıcı siyah ekranı önler). Pencere software moduna demote edilmeli.
# ---------------------------------------------------------------------------

class _FakeGLSurface:
    """OPENGL bayrağına sahip, çizilemeyen ham display surface taklidi."""

    def __init__(self, size=(1920, 1080)):
        self._size = size

    def get_size(self):
        return self._size

    def get_flags(self):
        return pygame.OPENGL


class _FakeSoftwareSurface:
    """set_mode sonrası dönen çizilebilir software surface taklidi."""

    def __init__(self, size=(1920, 1080), flags=0):
        self._size = size
        self._flags = flags

    def get_size(self):
        return self._size

    def get_flags(self):
        return self._flags


def _install_gl_overlay_stubs(monkeypatch, *, steam_available, load_gl_ok):
    """gl_overlay_setup için ortak Windows + Steam + GL stub'ları kur."""
    import platform_utils

    monkeypatch.setattr(gl_compat.platform, 'system', lambda: 'Windows')

    fake_steam = types.ModuleType('steam_integration')
    fake_steam.is_available = lambda: steam_available
    monkeypatch.setitem(sys.modules, 'steam_integration', fake_steam)

    monkeypatch.setattr(gl_compat, '_load_gl', lambda: load_gl_ok)

    set_mode_calls = []

    def fake_set_mode(size, flags=0):
        set_mode_calls.append((size, flags))
        return _FakeSoftwareSurface(size, flags)

    monkeypatch.setattr(gl_compat.pygame.display, 'set_mode', fake_set_mode)
    monkeypatch.setattr(gl_compat.pygame.display, 'get_caption', lambda: ('Quadrix', 'Quadrix'))
    monkeypatch.setattr(gl_compat.pygame.display, 'set_caption', lambda *a, **k: None)

    # set_gl_window_request çağrısının gerçek modülde patlamamasını sağla.
    monkeypatch.setattr(platform_utils, 'set_gl_window_request', lambda enabled: None)

    return set_mode_calls


def test_single_context_demotes_to_software_when_gl_load_fails(monkeypatch):
    """Tek-context'te _load_gl başarısızsa sonuç ham GL surface OLMAMALI."""
    # _active state'ini sızdırmamak için sıfırla.
    monkeypatch.setattr(gl_compat, '_active', False)

    set_mode_calls = _install_gl_overlay_stubs(
        monkeypatch, steam_available=True, load_gl_ok=False
    )

    raw_gl_surface = _FakeGLSurface()
    result = gl_compat.gl_overlay_setup(raw_gl_surface)

    # Sonuç ham GL surface olmamalı (kalıcı siyah ekranı önler).
    assert result is not raw_gl_surface
    assert not (result.get_flags() & pygame.OPENGL), "Sonuç software surface olmalı"
    # Software penceresine geri dönüş için set_mode çağrılmış olmalı.
    assert set_mode_calls, "Software'e demote için set_mode çağrılmalı"
    assert not (set_mode_calls[-1][1] & pygame.OPENGL)


def test_single_context_demotes_to_software_when_steam_unavailable(monkeypatch):
    """Pencere GL açıldı ama Steam yoksa ham GL surface bırakılmamalı."""
    monkeypatch.setattr(gl_compat, '_active', False)

    set_mode_calls = _install_gl_overlay_stubs(
        monkeypatch, steam_available=False, load_gl_ok=True
    )

    raw_gl_surface = _FakeGLSurface()
    result = gl_compat.gl_overlay_setup(raw_gl_surface)

    assert result is not raw_gl_surface
    assert not (result.get_flags() & pygame.OPENGL)
    assert set_mode_calls, "Steam yokken software'e demote için set_mode çağrılmalı"


# ---------------------------------------------------------------------------
# Başarı yolu: tek-context GL tam çalışınca oyun OFFSCREEN surface almalı
# (ham GL DEĞİL), monkey-patch'ler kurulmalı ve ilk kare pompalanmalı.
# ---------------------------------------------------------------------------

def test_single_context_success_returns_offscreen_and_pumps_first_frame(monkeypatch):
    """GL kurulumu başarılıysa: offscreen surface döner, flip patch'lenir, ilk kare basılır."""
    # State sızıntısını önle.
    monkeypatch.setattr(gl_compat, '_active', False)
    monkeypatch.setattr(gl_compat, '_game_surface', None)

    monkeypatch.setattr(gl_compat.platform, 'system', lambda: 'Windows')

    fake_steam = types.ModuleType('steam_integration')
    fake_steam.is_available = lambda: True
    monkeypatch.setitem(sys.modules, 'steam_integration', fake_steam)

    monkeypatch.setattr(gl_compat, '_load_gl', lambda: True)

    # GL setup'ı gerçek opengl32 çağrısı yapmadan başarılı kıl.
    monkeypatch.setattr(gl_compat, '_setup_ortho', lambda w, h: None)
    monkeypatch.setattr(gl_compat, '_create_texture', lambda w, h: 42)

    # set_mode çağrılırsa yakala (tek-context'te çağrılMAMALI).
    set_mode_calls = []

    def fake_set_mode(size, flags=0):
        set_mode_calls.append((size, flags))
        return _FakeSoftwareSurface(size, flags)

    monkeypatch.setattr(gl_compat.pygame.display, 'set_mode', fake_set_mode)
    monkeypatch.setattr(gl_compat.pygame.display, 'get_caption', lambda: ('Quadrix', 'Quadrix'))
    monkeypatch.setattr(gl_compat.pygame.display, 'set_caption', lambda *a, **k: None)
    monkeypatch.setattr(gl_compat, '_patch_create_display', lambda: None)

    # İlk kare pompalamayı gözlemle: _upload_and_draw + _original_flip + event.pump
    pump_events = {'upload': 0, 'flip': 0, 'pump': 0}
    monkeypatch.setattr(gl_compat, '_upload_and_draw', lambda *a, **k: pump_events.__setitem__('upload', pump_events['upload'] + 1))
    monkeypatch.setattr(gl_compat, '_original_flip', lambda *a, **k: pump_events.__setitem__('flip', pump_events['flip'] + 1))
    monkeypatch.setattr(gl_compat.pygame.event, 'pump', lambda: pump_events.__setitem__('pump', pump_events['pump'] + 1))

    raw_gl_surface = _FakeGLSurface((1920, 1080))
    try:
        result = gl_compat.gl_overlay_setup(raw_gl_surface)

        # Oyun ham GL surface DEĞİL, gerçek pygame offscreen surface almalı.
        assert isinstance(result, pygame.Surface)
        assert result.get_size() == (1920, 1080)
        assert not (result.get_flags() & pygame.OPENGL), "Offscreen surface OPENGL olmamalı"

        # Tek-context: ikinci set_mode YAPILMAMALI.
        assert set_mode_calls == [], "Tek-context'te ikinci set_mode çağrılmamalı"

        # GL wrapper aktive edilmeli ve flip/get_surface patch'lenmeli.
        assert gl_compat.is_gl_active() is True
        assert pygame.display.get_surface is gl_compat._gl_get_surface
        assert pygame.display.flip is gl_compat._gl_flip

        # İlk kare pompalanmış olmalı (Adım 2): upload + flip + pump en az 1 kez.
        assert pump_events['upload'] >= 1
        assert pump_events['flip'] >= 1
        assert pump_events['pump'] >= 1
    finally:
        # Monkey-patch'leri ve global state'i temizle ki diğer testler etkilenmesin.
        pygame.display.flip = gl_compat._original_flip
        pygame.display.update = gl_compat._original_update
        pygame.display.get_surface = gl_compat._original_get_surface
        gl_compat._active = False
        gl_compat._game_surface = None


# ---------------------------------------------------------------------------
# GPU senkronizasyon (glFlush/glFinish) ve VIDEORESIZE GL-aware guard testleri.
# DWM/OBS/PrintScreen'in taze kareyi görmesi + ikinci set_mode'un önlenmesi.
# ---------------------------------------------------------------------------

class _FakeGL:
    """ctypes opengl32 taklidi: glFlush/glFinish çağrılarını sayar."""

    def __init__(self):
        self.flush_count = 0
        self.finish_count = 0

    def glFlush(self):
        self.flush_count += 1

    def glFinish(self):
        self.finish_count += 1


def test_resolve_gpu_sync_mode_default_is_off(monkeypatch):
    """Varsayılan (auto) GPU sync modu 'off' olmalı (PERFORMANS: glFinish/DwmFlush FPS düşürür)."""
    monkeypatch.setattr(gl_compat, '_gpu_sync_mode', None)
    monkeypatch.delenv('QUADRIX_STEAM_OVERLAY_GL_SYNC', raising=False)
    assert gl_compat._resolve_gpu_sync_mode() == 'off'


def test_resolve_gpu_sync_mode_env_off(monkeypatch):
    monkeypatch.setattr(gl_compat, '_gpu_sync_mode', None)
    monkeypatch.setenv('QUADRIX_STEAM_OVERLAY_GL_SYNC', 'off')
    assert gl_compat._resolve_gpu_sync_mode() == 'off'


def test_resolve_gpu_sync_mode_env_flush(monkeypatch):
    monkeypatch.setattr(gl_compat, '_gpu_sync_mode', None)
    monkeypatch.setenv('QUADRIX_STEAM_OVERLAY_GL_SYNC', 'flush')
    assert gl_compat._resolve_gpu_sync_mode() == 'flush'


def test_resolve_gpu_sync_mode_env_finish(monkeypatch):
    monkeypatch.setattr(gl_compat, '_gpu_sync_mode', None)
    monkeypatch.setenv('QUADRIX_STEAM_OVERLAY_GL_SYNC', 'finish')
    assert gl_compat._resolve_gpu_sync_mode() == 'finish'


def test_resolve_gpu_sync_mode_env_dwm(monkeypatch):
    monkeypatch.setattr(gl_compat, '_gpu_sync_mode', None)
    monkeypatch.setenv('QUADRIX_STEAM_OVERLAY_GL_SYNC', 'dwm')
    assert gl_compat._resolve_gpu_sync_mode() == 'dwm'


def test_gl_flip_finish_mode_flushes_before_and_finishes_after_swap(monkeypatch):
    """finish modunda: swap öncesi glFlush, swap sonrası glFinish çağrılmalı."""
    fake_gl = _FakeGL()
    order = []

    monkeypatch.setattr(gl_compat, '_active', True)
    monkeypatch.setattr(gl_compat, '_game_surface', pygame.Surface((4, 4)))
    monkeypatch.setattr(gl_compat, '_gl', fake_gl)
    monkeypatch.setattr(gl_compat, '_gpu_sync_mode', 'finish')
    monkeypatch.setattr(gl_compat, '_upload_and_draw', lambda *a, **k: order.append('upload'))

    def _fake_flush(mode):
        order.append(f'sync:{mode}')
        if mode == 'flush':
            fake_gl.flush_count += 1
        elif mode == 'finish':
            fake_gl.finish_count += 1

    monkeypatch.setattr(gl_compat, '_gpu_sync', _fake_flush)
    monkeypatch.setattr(gl_compat, '_original_flip', lambda *a, **k: order.append('swap'))

    gl_compat._gl_flip()

    # Sıralama: upload -> flush -> swap -> finish
    assert order == ['upload', 'sync:flush', 'swap', 'sync:finish']
    assert fake_gl.flush_count == 1
    assert fake_gl.finish_count == 1


def test_gl_flip_dwm_mode_calls_dwmflush_after_swap_and_finish(monkeypatch):
    """dwm modunda sıra: upload -> glFlush -> SwapBuffers -> glFinish -> DwmFlush."""
    fake_gl = _FakeGL()
    order = []

    monkeypatch.setattr(gl_compat, '_active', True)
    monkeypatch.setattr(gl_compat, '_game_surface', pygame.Surface((4, 4)))
    monkeypatch.setattr(gl_compat, '_gl', fake_gl)
    monkeypatch.setattr(gl_compat, '_gpu_sync_mode', 'dwm')
    monkeypatch.setattr(gl_compat, '_upload_and_draw', lambda *a, **k: order.append('upload'))
    monkeypatch.setattr(gl_compat, '_gpu_sync', lambda mode: order.append(f'sync:{mode}'))
    monkeypatch.setattr(gl_compat, '_original_flip', lambda *a, **k: order.append('swap'))

    dwm_calls = []
    monkeypatch.setattr(gl_compat, '_dwm_flush', lambda: dwm_calls.append('dwmflush') or order.append('dwmflush'))

    gl_compat._gl_flip()

    assert order == ['upload', 'sync:flush', 'swap', 'sync:finish', 'dwmflush']
    assert dwm_calls == ['dwmflush'], "DwmFlush tam olarak bir kez çağrılmalı"
    # DwmFlush, swap ve finish'ten SONRA gelmeli (capture doğruluğu).
    assert order.index('dwmflush') > order.index('swap')
    assert order.index('dwmflush') > order.index('sync:finish')


def test_gl_flip_finish_mode_does_not_call_dwmflush(monkeypatch):
    """finish modunda DwmFlush çağrılMAMALI (yalnızca dwm modunda)."""
    monkeypatch.setattr(gl_compat, '_active', True)
    monkeypatch.setattr(gl_compat, '_game_surface', pygame.Surface((4, 4)))
    monkeypatch.setattr(gl_compat, '_gpu_sync_mode', 'finish')
    monkeypatch.setattr(gl_compat, '_upload_and_draw', lambda *a, **k: None)
    monkeypatch.setattr(gl_compat, '_gpu_sync', lambda mode: None)
    monkeypatch.setattr(gl_compat, '_original_flip', lambda *a, **k: None)

    dwm_calls = []
    monkeypatch.setattr(gl_compat, '_dwm_flush', lambda: dwm_calls.append('dwmflush'))

    gl_compat._gl_flip()

    assert dwm_calls == [], "finish modunda DwmFlush çağrılmamalı"


def test_dwm_flush_safe_when_dll_unavailable(monkeypatch):
    """dwmapi yüklenemezse _dwm_flush sessizce geçmeli (exception fırlatmamalı)."""
    monkeypatch.setattr(gl_compat, '_dwm', None)
    monkeypatch.setattr(gl_compat, '_dwm_load_failed', False)
    monkeypatch.setattr(gl_compat, '_load_dwm', lambda: False)
    # Exception fırlatmamalı.
    gl_compat._dwm_flush()


def test_gl_flip_off_mode_skips_gpu_sync(monkeypatch):
    """off modunda hiç glFlush/glFinish çağrılmamalı; yine de swap yapılmalı."""
    order = []
    monkeypatch.setattr(gl_compat, '_active', True)
    monkeypatch.setattr(gl_compat, '_game_surface', pygame.Surface((4, 4)))
    monkeypatch.setattr(gl_compat, '_gpu_sync_mode', 'off')
    monkeypatch.setattr(gl_compat, '_upload_and_draw', lambda *a, **k: order.append('upload'))
    monkeypatch.setattr(gl_compat, '_gpu_sync', lambda mode: order.append(f'sync:{mode}'))
    monkeypatch.setattr(gl_compat, '_original_flip', lambda *a, **k: order.append('swap'))

    gl_compat._gl_flip()

    assert order == ['upload', 'swap']
    assert not any(o.startswith('sync:') for o in order)


def test_should_skip_display_rebuild_true_when_gl_active_same_size(monkeypatch):
    """GL aktif + Windows + boyut sabit → rebuild atlanmalı (True)."""
    monkeypatch.setattr(gl_compat.platform, 'system', lambda: 'Windows')
    monkeypatch.setattr(gl_compat, '_active', True)
    monkeypatch.setattr(gl_compat, '_game_surface', pygame.Surface((1920, 1080)))
    monkeypatch.setattr(gl_compat, '_width', 1920)
    monkeypatch.setattr(gl_compat, '_height', 1080)
    assert gl_compat.should_skip_display_rebuild(1920, 1080) is True


def test_should_skip_display_rebuild_false_on_size_change(monkeypatch):
    """Boyut değişirse rebuild atlanMAMALI (False)."""
    monkeypatch.setattr(gl_compat.platform, 'system', lambda: 'Windows')
    monkeypatch.setattr(gl_compat, '_active', True)
    monkeypatch.setattr(gl_compat, '_game_surface', pygame.Surface((1920, 1080)))
    monkeypatch.setattr(gl_compat, '_width', 1920)
    monkeypatch.setattr(gl_compat, '_height', 1080)
    assert gl_compat.should_skip_display_rebuild(1280, 720) is False


def test_should_skip_display_rebuild_false_when_gl_inactive(monkeypatch):
    """GL aktif değilse rebuild atlanMAMALI (False)."""
    monkeypatch.setattr(gl_compat.platform, 'system', lambda: 'Windows')
    monkeypatch.setattr(gl_compat, '_active', False)
    monkeypatch.setattr(gl_compat, '_game_surface', None)
    assert gl_compat.should_skip_display_rebuild(1920, 1080) is False
