"""OpenGL compatibility layer for Steam overlay support on Windows.

Steam overlay hooks into D3D/OpenGL rendering contexts. Pygame's default
software renderer (SDL2 + GDI) is invisible to Steam's hook. This module
creates an OpenGL context and transparently blits the game's pygame Surface
onto an OpenGL texture each frame.

Usage (in main.py, after create_display):
    from gl_compat import gl_overlay_setup
    screen = gl_overlay_setup(screen)  # returns offscreen surface

The module monkey-patches:
- ``pygame.display.flip`` / ``pygame.display.update``  → upload texture then swap
- ``pygame.display.get_surface`` → return offscreen game surface (not GL surface)

Use ``get_display_surface()`` to access the real visible GL display surface when
you need to inspect or forward the window after toggles/rebuilds.

Non-Windows platforms or environments without OpenGL silently fall back to
the standard pygame path (no-op wrapper).
"""

from __future__ import annotations

import ctypes
import os
import platform
import sys

import pygame

# ---------------------------------------------------------------------------
# Teşhis (diagnostic) günlüğü
# ---------------------------------------------------------------------------
# Build'de (PyInstaller, console=False) print() çıktısı hiçbir yere gitmez.
# Steam overlay / çift-pencere / PrintScreen sorununu gerçek ortamda teşhis
# edebilmek için kararları kalıcı bir dosyaya yazıyoruz:
#   Windows: %APPDATA%\<AppName>\local\gl_debug.log  (data_paths varsa)
#            yoksa %LOCALAPPDATA%\Quadrix\gl_debug.log
# Kapatmak için QUADRIX_GL_DEBUG=0. Açıkça açmak için QUADRIX_GL_DEBUG=1.
# Varsayılan: AÇIK (sorun çözülene kadar). Hata-toleranslıdır; asla exception sızdırmaz.
_diag_log_path: str | None = None
_diag_log_resolved = False
_diag_set_mode_count = 0  # Tek-context teşhisi: kaç kez set_mode benzeri çağrı oldu


def _diag_enabled() -> bool:
    # Birim testler (pytest) gerçek build teşhis logunu kirletmesin: pytest
    # altında dosyaya YAZMA. Açıkça QUADRIX_GL_DEBUG=1 verilirse yine de yazar.
    raw = os.environ.get('QUADRIX_GL_DEBUG')
    if raw is None:
        if ('pytest' in sys.modules) or any('pytest' in str(a) for a in sys.argv):
            return False
        return True  # varsayılan açık (teşhis dönemi)
    return str(raw).strip().lower() not in ('0', 'false', 'off', 'no', 'disable', 'disabled')


def _diag_resolve_path() -> str | None:
    global _diag_log_path, _diag_log_resolved
    if _diag_log_resolved:
        return _diag_log_path
    _diag_log_resolved = True
    try:
        log_dir = None
        try:
            import data_paths as _dp
            log_dir = _dp.get_local_data_dir()
        except Exception:
            try:
                from . import data_paths as _dp  # type: ignore
                log_dir = _dp.get_local_data_dir()
            except Exception:
                log_dir = None
        if not log_dir:
            base = os.getenv('LOCALAPPDATA') or os.getenv('APPDATA') or os.path.expanduser('~')
            log_dir = os.path.join(base, 'Quadrix')
        os.makedirs(log_dir, exist_ok=True)
        _diag_log_path = os.path.join(log_dir, 'gl_debug.log')
    except Exception:
        _diag_log_path = None
    return _diag_log_path


def _diag_log(message: str) -> None:
    """Teşhis satırını hem stdout'a (varsa) hem kalıcı log dosyasına yaz. Hata yutar."""
    line = f"[GL Compat] {message}"
    try:
        print(line)
    except Exception:
        pass
    if not _diag_enabled():
        return
    try:
        path = _diag_resolve_path()
        if not path:
            return
        import time as _time
        ts = _time.strftime('%Y-%m-%d %H:%M:%S')
        with open(path, 'a', encoding='utf-8', errors='ignore') as fh:
            fh.write(f"{ts} {line}\n")
    except Exception:
        pass


def _diag_log_env_snapshot() -> None:
    """İlk kurulumda ortam/teşhis bağlamını logla (platform, Steam, GL durumu)."""
    try:
        import time as _time
        sep = '=' * 60
        _diag_log(sep)
        _diag_log(f"GL DEBUG OTURUM BAŞLANGICI {_time.strftime('%Y-%m-%d %H:%M:%S')}")
        _diag_log(f"platform.system={platform.system()} sys.platform={sys.platform}")
        _diag_log(f"frozen={getattr(sys, 'frozen', False)} executable={getattr(sys, 'executable', '?')}")
        try:
            import steam_integration as _si
            _diag_log(f"steam_integration.is_available()={_si.is_available()}")
        except Exception as exc:
            _diag_log(f"steam_integration import/durum hatası: {exc}")
        _diag_log(f"QUADRIX_STEAM_OVERLAY_GL={os.environ.get('QUADRIX_STEAM_OVERLAY_GL')}")
        _diag_log(f"QUADRIX_STEAM_OVERLAY_GL_SYNC={os.environ.get('QUADRIX_STEAM_OVERLAY_GL_SYNC')}")
        _diag_log(sep)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Module state
# ---------------------------------------------------------------------------
_active = False
_game_surface: pygame.Surface | None = None
_tex_id: int = 0
_width: int = 0
_height: int = 0
_original_flip = pygame.display.flip
_original_update = pygame.display.update
_original_get_surface = pygame.display.get_surface
_original_create_display = None  # set during first gl_overlay_setup
_create_display_wrappers: dict[object, object] = {}
_supports_bgra_upload: bool | None = None

# GPU senkronizasyon modu (DWM/OBS/Steam capture'ın taze kareyi görmesi için).
# - 'dwm'   : glFlush (swap öncesi) + SwapBuffers + glFinish + DwmFlush (swap sonrası).
#             En doğru yakalama; DWM kompozisyonu beklenir, PrintScreen/Snipping/Window
#             capture her zaman güncel kareyi alır. Kare DWM vsync'ine kilitlenir (~ekran Hz).
# - 'finish': glFlush (swap öncesi) + glFinish (swap sonrası). GPU eşitlenir ama DWM
#             kompozisyonu beklenmez; bazı yakalama yollarında bayat kare kalabilir.
# - 'flush' : yalnızca glFlush. Ucuz; komutları GPU'ya iteler.
# - 'off'   : senkronizasyon yok (eski davranış).
# Varsayılan 'auto' → PERFORMANS için 'off' (glFinish/DwmFlush FPS düşürür). Kullanıcı
# PrintScreen/capture tazeliği isterse 'dwm'/'finish'/'flush' ile açabilir.
_gpu_sync_mode: str | None = None

# GL constants (from OpenGL spec, avoids PyOpenGL dep)
GL_TEXTURE_2D = 0x0DE1
GL_RGBA = 0x1908
GL_UNSIGNED_BYTE = 0x1401
GL_TEXTURE_MIN_FILTER = 0x2801
GL_TEXTURE_MAG_FILTER = 0x2800
GL_LINEAR = 0x2601
GL_BGRA = 0x80E1
GL_COLOR_BUFFER_BIT = 0x00004000
GL_VERSION = 0x1F02
GL_EXTENSIONS = 0x1F03
GL_QUADS = 0x0007
GL_PROJECTION = 0x1701
GL_MODELVIEW = 0x1700
GL_BLEND = 0x0BE2

# ---------------------------------------------------------------------------
# Lazy-loaded GL function pointers (ctypes from opengl32.dll)
# ---------------------------------------------------------------------------
_gl = None  # ctypes.windll.opengl32
_dwm = None  # ctypes.windll.dwmapi (Windows Vista+)
_dwm_load_failed = False


def _load_gl():
    """Load opengl32.dll and set up function signatures."""
    global _gl
    if _gl is not None:
        return True
    try:
        _gl = ctypes.windll.opengl32
        return True
    except Exception:
        return False


def _load_dwm():
    """Load dwmapi.dll for DwmFlush() (DWM composition sync). Windows Vista+.

    DwmFlush, DWM bir sonraki kompozisyonu tamamlayana kadar bloklar. OpenGL
    pencerede SwapBuffers yalnızca monitör vblank'ine senkronize olur; DWM'nin
    kompozisyon döngüsüne değil. PrintScreen/Snipping Tool/Window-capture DWM'nin
    kompoze ettiği yüzeyden okuduğu için, SwapBuffers'tan sonra DwmFlush çağrılması
    sunulan karenin yakalama yüzeyine yansımasını sağlar (bayat-kare düzeltmesi).
    """
    global _dwm, _dwm_load_failed
    if _dwm is not None:
        return True
    if _dwm_load_failed:
        return False
    try:
        _dwm = ctypes.windll.dwmapi
        return True
    except Exception:
        _dwm_load_failed = True
        return False


def _dwm_flush() -> None:
    """DWM kompozisyonunu bekle (safe fallback). DwmFlush() HRESULT döndürür."""
    if not _load_dwm():
        return
    try:
        _dwm.DwmFlush()
    except Exception:
        pass


def _gl_call(name, restype=None, argtypes=None, *args):
    """Call an OpenGL function via ctypes."""
    fn = getattr(_gl, name)
    if restype is not None:
        fn.restype = restype
    if argtypes is not None:
        fn.argtypes = argtypes
    return fn(*args)


# ---------------------------------------------------------------------------
# Core GL helpers (minimal subset, no PyOpenGL needed)
# ---------------------------------------------------------------------------

def _setup_ortho(w: int, h: int):
    """Set up 2D orthographic projection matching pixel coords."""
    # glMatrixMode(GL_PROJECTION)
    _gl.glMatrixMode(GL_PROJECTION)
    _gl.glLoadIdentity()

    # gluOrtho2D equivalent via glOrtho
    _gl.glOrtho.argtypes = [
        ctypes.c_double, ctypes.c_double,
        ctypes.c_double, ctypes.c_double,
        ctypes.c_double, ctypes.c_double,
    ]
    _gl.glOrtho(0.0, float(w), float(h), 0.0, -1.0, 1.0)

    _gl.glMatrixMode(GL_MODELVIEW)
    _gl.glLoadIdentity()


def _create_texture(w: int, h: int) -> int:
    """Create and configure an RGBA texture, return its GL id."""
    tex = ctypes.c_uint(0)
    _gl.glGenTextures(1, ctypes.byref(tex))
    _gl.glBindTexture(GL_TEXTURE_2D, tex.value)

    _gl.glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
    _gl.glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)

    # Allocate empty texture
    _gl.glTexImage2D.argtypes = [
        ctypes.c_uint, ctypes.c_int, ctypes.c_int,
        ctypes.c_int, ctypes.c_int, ctypes.c_int,
        ctypes.c_uint, ctypes.c_uint, ctypes.c_void_p,
    ]
    _gl.glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, w, h, 0, GL_RGBA, GL_UNSIGNED_BYTE, None)

    return tex.value


def _can_use_direct_bgra_upload() -> bool:
    """Return True if the active GL context can accept BGRA uploads."""
    global _supports_bgra_upload

    if _supports_bgra_upload is not None:
        return _supports_bgra_upload

    try:
        _gl.glGetString.restype = ctypes.c_char_p
        _gl.glGetString.argtypes = [ctypes.c_uint]

        version_raw = _gl.glGetString(GL_VERSION) or b''
        extensions_raw = _gl.glGetString(GL_EXTENSIONS) or b''

        version_text = version_raw.decode('ascii', errors='ignore').strip()
        extensions_text = extensions_raw.decode('ascii', errors='ignore')
        version_token = version_text.split(' ', 1)[0]
        version_parts = version_token.split('.')
        major = int(version_parts[0] or '0') if version_parts else 0
        minor = int(version_parts[1] or '0') if len(version_parts) > 1 else 0

        _supports_bgra_upload = (major, minor) >= (1, 2) or 'GL_EXT_bgra' in extensions_text
    except Exception:
        _supports_bgra_upload = False

    return _supports_bgra_upload


def _get_upload_source(surface: pygame.Surface) -> tuple[int, object, bool]:
    """Return the most efficient upload payload for the current surface.

    Returns:
        (gl_format, payload, flip_y)

    payload is either a live BufferProxy for direct BGRA upload or a bytes
    object from pygame.image.tostring fallback.
    """
    try:
        width, _height = surface.get_size()
        bitsize = int(surface.get_bitsize())
        bytesize = int(surface.get_bytesize())
        pitch = int(surface.get_pitch())
        masks = tuple(int(m) for m in surface.get_masks())
        alpha_mask = masks[3] if len(masks) >= 4 else 0

        if (
            sys.byteorder == 'little'
            and bitsize == 32
            and bytesize == 4
            and pitch == width * bytesize
            and masks[:3] == (0x00FF0000, 0x0000FF00, 0x000000FF)
            and alpha_mask in (0x00000000, 0xFF000000)
            and hasattr(surface, 'get_buffer')
            and _can_use_direct_bgra_upload()
        ):
            return (GL_BGRA, surface.get_buffer(), False)
    except Exception:
        pass

    return (GL_RGBA, pygame.image.tostring(surface, 'RGBA', True), True)


def _get_upload_pointer(payload: object) -> ctypes.c_void_p:
    """Convert an upload payload to a C pointer without changing ownership."""
    if isinstance(payload, (bytes, bytearray)):
        return ctypes.cast(ctypes.c_char_p(payload), ctypes.c_void_p)

    # BufferProxy/memoryview path: borrow the writable buffer directly.
    return ctypes.c_void_p(ctypes.addressof(ctypes.c_char.from_buffer(payload)))


def _draw_fullscreen_quad(w: int, h: int, *, flip_y: bool) -> None:
    """Draw the uploaded texture over the entire framebuffer."""
    _gl.glBegin(GL_QUADS)

    _gl.glTexCoord2f.argtypes = [ctypes.c_float, ctypes.c_float]
    _gl.glVertex2f.argtypes = [ctypes.c_float, ctypes.c_float]

    if flip_y:
        top_v = 1.0
        bottom_v = 0.0
    else:
        top_v = 0.0
        bottom_v = 1.0

    _gl.glTexCoord2f(0.0, top_v)
    _gl.glVertex2f(0.0, 0.0)

    _gl.glTexCoord2f(1.0, top_v)
    _gl.glVertex2f(float(w), 0.0)

    _gl.glTexCoord2f(1.0, bottom_v)
    _gl.glVertex2f(float(w), float(h))

    _gl.glTexCoord2f(0.0, bottom_v)
    _gl.glVertex2f(0.0, float(h))

    _gl.glEnd()


def _upload_and_draw(surface: pygame.Surface, tex: int, w: int, h: int):
    """Upload a pygame Surface to the GL texture and draw a fullscreen quad."""
    gl_format, payload, flip_y = _get_upload_source(surface)
    pixel_pointer = _get_upload_pointer(payload)

    _gl.glBindTexture(GL_TEXTURE_2D, tex)
    _gl.glTexSubImage2D.argtypes = [
        ctypes.c_uint, ctypes.c_int,
        ctypes.c_int, ctypes.c_int,
        ctypes.c_int, ctypes.c_int,
        ctypes.c_uint, ctypes.c_uint, ctypes.c_void_p,
    ]
    _gl.glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, w, h, gl_format, GL_UNSIGNED_BYTE, pixel_pointer)

    # Clear & draw fullscreen textured quad
    _gl.glClear(GL_COLOR_BUFFER_BIT)
    _gl.glEnable(GL_TEXTURE_2D)
    _draw_fullscreen_quad(w, h, flip_y=flip_y)


# ---------------------------------------------------------------------------
# Monkey-patched flip / update
# ---------------------------------------------------------------------------

def _resolve_gpu_sync_mode() -> str:
    """Aktif GPU senkronizasyon modunu döndür: 'dwm' | 'finish' | 'flush' | 'off'.

    Öncelik: QUADRIX_STEAM_OVERLAY_GL_SYNC ortam değişkeni > varsayılan ('auto').
    'auto' → 'off' (PERFORMANS: glFinish/DwmFlush her karede CPU'yu bloklayıp FPS'i
    düşürdüğü için varsayılan KAPALI). PrintScreen/capture tazeliği için kullanıcı
    açıkça 'dwm' (en doğru, en yavaş), 'finish' veya 'flush' (en ucuz) seçebilir.
    Sonuç bir kez hesaplanıp önbelleğe alınır.
    """
    global _gpu_sync_mode
    if _gpu_sync_mode is not None:
        return _gpu_sync_mode

    raw = os.environ.get('QUADRIX_STEAM_OVERLAY_GL_SYNC')
    mode = str(raw or 'auto').strip().lower()

    if mode in ('off', '0', 'false', 'none', 'disable', 'disabled'):
        resolved = 'off'
    elif mode in ('flush',):
        resolved = 'flush'
    elif mode in ('finish',):
        resolved = 'finish'
    elif mode in ('dwm', 'dwmflush', '1', 'true', 'on', 'enable', 'enabled'):
        resolved = 'dwm'
    else:  # 'auto' veya tanınmayan → performans için senkronizasyon KAPALI
        resolved = 'off'

    _gpu_sync_mode = resolved
    return resolved


def _gpu_sync(mode: str) -> None:
    """Sürücü komut kuyruğunu senkronize et (ctypes, PyOpenGL bağımlılığı yok).

    'flush'  → glFlush(): komutları GPU'ya iteler, bloklamaz.
    'finish' → glFinish(): GPU kareyi bitirene kadar CPU'yu bloklar.
    Başarısızlıkta sessizce geçilir (safe fallback).
    """
    if _gl is None:
        return
    try:
        if mode == 'flush':
            _gl.glFlush()
        elif mode == 'finish':
            _gl.glFinish()
    except Exception:
        pass


def _gl_flip():
    """Upload game surface to GL texture, then do real GL buffer swap.

    DWM/OBS/Steam ekran yakalamasının her zaman TAZE kareyi görmesi için sürücü
    komut kuyruğu VE (gerekirse) DWM kompozisyonu senkronize edilir.

    Windows'ta OpenGL pencerede SwapBuffers yalnızca monitör vblank'ine senkronize
    olur; DWM'nin kompozisyon döngüsüne DEĞİL. PrintScreen/Snipping Tool/Window
    capture DWM'nin kompoze ettiği yüzeyden okur. Bu yüzden glFinish (GPU eşitleme)
    tek başına yetmez; 'dwm' modunda SwapBuffers'tan sonra DwmFlush ile DWM
    kompozisyonu da beklenir → yakalama hep güncel kareyi alır (bayat-kare fix).

    Sıralama: glFlush (swap ÖNCESİ, komutları GPU'ya iter) → SwapBuffers (takas) →
    glFinish (swap SONRASI, GPU'yu eşitler) → DwmFlush (DWM kompozisyonunu bekler).
    """
    sync_mode = 'off'
    if _active and _game_surface is not None:
        try:
            _upload_and_draw(_game_surface, _tex_id, _width, _height)
        except Exception:
            pass
        sync_mode = _resolve_gpu_sync_mode()

    # 1) Swap ÖNCESİ: komutları GPU'ya iter (flush/finish/dwm hepsi iter).
    if sync_mode in ('flush', 'finish', 'dwm'):
        _gpu_sync('flush')

    # 2) Gerçek pencere buffer takası (SwapBuffers).
    _original_flip()

    # 3) Swap SONRASI: GPU'yu donanımla eşitle ('finish' ve 'dwm').
    if sync_mode in ('finish', 'dwm'):
        _gpu_sync('finish')

    # 4) DWM kompozisyonunu bekle ('dwm'): sunulan kare PrintScreen/capture'ın
    #    okuduğu DWM yüzeyine yansır. Bayat-kare sorununun asıl düzeltmesi.
    if sync_mode == 'dwm':
        _dwm_flush()


def _gl_update(
    rectangle: pygame.Rect | list | None = None,
):
    """Same as flip for GL mode — partial update not meaningful in GL."""
    _gl_flip()


def _gl_get_surface():
    """Return the offscreen game surface instead of the GL display surface."""
    if _active and _game_surface is not None:
        return _game_surface
    return _original_get_surface()


def get_display_surface():
    """Return the real visible display surface, bypassing the GL offscreen wrapper."""
    try:
        return _original_get_surface()
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _should_use_gl() -> bool:
    """Return True if the GL overlay path should be used on this platform.

    Conditions (all required):
    - Running on Windows (Steam overlay D3D/OpenGL hook requirement).
    - Steam SDK is available (no point hooking overlay without Steam).
    - opengl32.dll loads successfully.
    """
    if platform.system() != 'Windows':
        _diag_log(f"_should_use_gl=False (platform={platform.system()} != Windows)")
        return False

    try:
        import steam_integration as _si
        if not _si.is_available():
            _diag_log("_should_use_gl=False (steam_integration.is_available()=False)")
            return False
    except Exception as exc:
        _diag_log(f"_should_use_gl=False (steam_integration import/durum hatası: {exc})")
        return False

    ok = _load_gl()
    _diag_log(f"_should_use_gl={ok} (Windows + Steam OK, opengl32 yüklendi={ok})")
    return ok


def _iter_platform_utils_modules():
    """Yield every imported module whose name ends with 'platform_utils'.

    Frozen (PyInstaller) build'lerde modül hem ``platform_utils`` hem de
    ``src.platform_utils`` olarak yüklenebilir. GL bayrağının, create_display'in
    okuduğu örnekle aynı modülde set edilmesi için tüm örnekleri tarıyoruz.
    """
    seen = set()
    for module in list(sys.modules.values()):
        if module is None:
            continue
        name = str(getattr(module, '__name__', '') or '')
        if name.endswith('platform_utils') and id(module) not in seen:
            seen.add(id(module))
            yield module


def _set_gl_window_request_everywhere(enabled: bool) -> bool:
    """Set the single-context request flag on all platform_utils instances.

    Returns True if at least one module accepted the request.
    """
    applied = False
    for module in _iter_platform_utils_modules():
        setter = getattr(module, 'set_gl_window_request', None)
        if callable(setter):
            try:
                setter(enabled)
                applied = True
            except Exception:
                pass

    if not applied:
        # Modül henüz sys.modules'da değilse doğrudan import et.
        try:
            import platform_utils as _pu
        except Exception:
            try:
                from . import platform_utils as _pu  # type: ignore
            except Exception:
                return False
        setter = getattr(_pu, 'set_gl_window_request', None)
        if callable(setter):
            try:
                setter(enabled)
                applied = True
            except Exception:
                applied = False

    return applied


def prepare_single_context() -> bool:
    """Ask platform_utils to open the window with OpenGL from the first set_mode.

    Call this *before* the first ``create_display()`` so the window is created
    in a single shot with the ``pygame.OPENGL`` flag (single-context). This
    eliminates the second ``set_mode`` that previously re-created the swapchain
    and could leave Steam's overlay hook on a dead context.

    Returns:
        True if the single-context request was registered (Windows + Steam +
        GL available), False otherwise. On False the caller should proceed with
        the standard software path; ``gl_overlay_setup`` will then fall back to
        the legacy two-step path if it still decides GL is needed.
    """
    _diag_log_env_snapshot()

    if not _should_use_gl():
        _set_gl_window_request_everywhere(False)
        _diag_log("prepare_single_context: _should_use_gl()=False → GL talebi YOK "
                  "(software pencere; gl_overlay_setup da no-op olacak)")
        return False

    if _set_gl_window_request_everywhere(True):
        _diag_log("prepare_single_context: GL talebi KAYDEDİLDİ → pencere baştan OPENGL açılmalı")
        return True

    _diag_log("prepare_single_context: GL talebi KAYDEDİLEMEDİ (platform_utils bulunamadı) "
              "→ RİSK: gl_overlay_setup iki-adımlı fallback'e düşebilir (çift pencere)")
    return False


def gl_overlay_setup(display_surface: pygame.Surface) -> pygame.Surface:
    """Activate the GL overlay wrapper if on Windows and GL available.

    Call this right after ``create_display()``.  It re-creates the display
    with ``pygame.OPENGL`` flag, sets up the GL texture pipeline, and
    returns an offscreen Surface that the rest of the game should render to.

    If anything fails (non-Windows, no GL, etc.) the original surface is
    returned unchanged and no monkey-patching happens.

    Args:
        display_surface: The surface returned by ``create_display()``.

    Returns:
        A pygame.Surface the game should use as its ``screen``.
    """
    global _active, _game_surface, _tex_id, _width, _height, _supports_bgra_upload

    # Only needed on Windows (Steam overlay issue)
    if platform.system() != 'Windows':
        return display_surface

    w, h = display_surface.get_size()

    # Tek-context yolu: pencere zaten OPENGL bayrağıyla açılmışsa ikinci bir
    # set_mode YAPMA (Gereksinim 1.2). Yalnızca GL texture pipeline'ını kur.
    try:
        existing_flags = display_surface.get_flags()
    except Exception:
        existing_flags = 0
    single_context = bool(existing_flags & pygame.OPENGL)

    _diag_log(f"gl_overlay_setup: giriş surface {w}x{h} flags=0x{existing_flags:X} "
              f"single_context(OPENGL zaten var mı)={single_context}")

    # KRİTİK: Tek-context'te create_display ham bir OpenGL surface döndürür.
    # Bu surface'e CPU ile (blit/draw) çizilemez. Eğer GL pipeline kurulumu
    # herhangi bir aşamada başarısız olursa, oyuna ham GL surface vermek KALICI
    # SİYAH EKRAN demektir. Bu yüzden tek-context'te başarısızlık halinde pencereyi
    # mutlaka çizilebilir bir software penceresine geri almalıyız (strict return).
    def _demote_to_software(reason: str) -> pygame.Surface:
        """GL kurulamazsa pencereyi software moduna alıp çizilebilir surface döndür."""
        _diag_log(f"DEMOTE → software: Tek-context GL kurulamadı ({reason}); "
                  f"güvenli geri dönüş yapılıyor")
        try:
            from platform_utils import set_gl_window_request
            set_gl_window_request(False)
        except Exception:
            pass
        # Pencere zaten GL ise software (NOFRAME) moduna geri al.
        try:
            sw_flags = (pygame.NOFRAME | pygame.DOUBLEBUF)
            sw_surface = pygame.display.set_mode((w, h), sw_flags)
            try:
                caption = pygame.display.get_caption()
                if caption and caption[0]:
                    pygame.display.set_caption(caption[0])
            except Exception:
                pass
            return sw_surface
        except Exception as exc:
            _diag_log(f"Software'e geri dönüş de başarısız: {exc}")
            # En kötü durumda en azından çizilebilir bir surface bırak.
            try:
                return pygame.display.get_surface() or display_surface
            except Exception:
                return display_surface

    # Steam SDK'sı yoksa GL'e gerek yok.
    steam_ok = False
    try:
        import steam_integration as _si
        steam_ok = bool(_si.is_available())
    except Exception:
        steam_ok = False

    if not steam_ok:
        if single_context:
            # Pencere GL açıldı ama Steam yok: ham GL surface ile bırakma.
            return _demote_to_software('Steam SDK erişilemiyor')
        return display_surface

    if not _load_gl():
        if single_context:
            return _demote_to_software('opengl32.dll yüklenemedi')
        return display_surface

    if single_context:
        old_flags = existing_flags
        _diag_log(f"YOL=TEK-CONTEXT: pencere zaten OPENGL ({w}x{h} flags=0x{existing_flags:X}); "
                  f"ikinci set_mode ATLANIYOR (doğru davranış)")
    else:
        # Geri dönüş (fallback): pencere software açıldı; eski iki-adımlı yol ile
        # OPENGL'e yeniden geç. En kötü senaryo bugünkü davranıştır (Gereksinim 5.2).
        _diag_log(f"YOL=İKİ-ADIMLI FALLBACK: pencere software açılmış (flags=0x{existing_flags:X}); "
                  f"ŞİMDİ ikinci set_mode(OPENGL) yapılacak → ÇİFT PENCERE KAYNAĞI! "
                  f"(prepare_single_context çalışmamış demektir)")
        try:
            # Mevcut display flag'lerini al
            old_flags = display_surface.get_flags()
            caption = pygame.display.get_caption()

            # OPENGL | DOUBLEBUF ekle, HWSURFACE kaldır (GL ile uyumsuz)
            new_flags = (old_flags | pygame.OPENGL | pygame.DOUBLEBUF) & ~pygame.HWSURFACE
            # Borderless NOFRAME durumunda da OPENGL ekle
            gl_display = pygame.display.set_mode((w, h), new_flags)

            # Caption'ı geri yükle
            if caption and caption[0]:
                pygame.display.set_caption(caption[0])

            _diag_log(f"İki-adımlı fallback: ikinci set_mode(OPENGL) yapıldı "
                      f"{w}x{h} flags=0x{new_flags:X}")
        except pygame.error as e:
            _diag_log(f"OpenGL display oluşturulamadı: {e}")
            return display_surface

    # GL setup
    try:
        _setup_ortho(w, h)
        _tex_id = _create_texture(w, h)
        _width = w
        _height = h
        _supports_bgra_upload = None
    except Exception as e:
        _diag_log(f"GL setup hatası: {e}")
        if single_context:
            # Tek-context: ham GL surface ile bırakma → software'e geri dön.
            return _demote_to_software(f'GL pipeline kurulamadı: {e}')
        # İki-adımlı yolda eski software moduna geri dön.
        try:
            pygame.display.set_mode((w, h), old_flags)
        except Exception:
            pass
        return display_surface

    # Offscreen game surface oluştur
    _game_surface = pygame.Surface((w, h))
    _game_surface.fill((0, 0, 0))

    # Monkey-patch flip/update/get_surface
    pygame.display.flip = _gl_flip
    pygame.display.update = _gl_update
    pygame.display.get_surface = _gl_get_surface
    _active = True

    # Patch platform_utils.create_display so that dynamic imports that access
    # the module attribute can still reapply GL when they rebuild the display.
    _patch_create_display()

    # Adım 2 (Pump & Flip): Pencere açılır açılmaz, ağır asset yüklemeleri
    # başlamadan ÖNCE temiz bir kare sun ve OS event kuyruğunu işlet. Bu, Steam'in
    # Present/SwapBuffers hook'una "pencere canlı ve render alıyor" sinyalini verir
    # ve uzun yükleme sırasında hook'un zaman aşımına/siyah kareye düşmesini önler.
    try:
        _gl_flip()
        pygame.event.pump()
    except Exception as exc:
        _diag_log(f"İlk kare pompalama atlandı: {exc}")

    if single_context:
        _diag_log(f"SONUÇ: GL wrapper AKTİF — tek-context ({w}x{h}) [İSTENEN DURUM]")
    else:
        _diag_log(f"SONUÇ: GL wrapper AKTİF — iki-adımlı fallback ({w}x{h}) "
                  f"[SORUNLU: çift set_mode yapıldı]")
    return _game_surface


def gl_overlay_resize(new_w: int, new_h: int) -> pygame.Surface | None:
    """Handle window resize — recreate texture and offscreen surface.

    Returns the new game surface, or None if GL wrapper is not active.
    """
    global _game_surface, _tex_id, _width, _height, _supports_bgra_upload

    if not _active:
        return None

    try:
        # Eski texture'ı sil
        if _tex_id:
            tex = ctypes.c_uint(_tex_id)
            _gl.glDeleteTextures(1, ctypes.byref(tex))

        _setup_ortho(new_w, new_h)
        _tex_id = _create_texture(new_w, new_h)
        _width = new_w
        _height = new_h
        _supports_bgra_upload = None
        _game_surface = pygame.Surface((new_w, new_h))
        _game_surface.fill((0, 0, 0))
        print(f"[GL Compat] Resize: {new_w}x{new_h}")
        return _game_surface
    except Exception as e:
        print(f"[GL Compat] Resize hatası: {e}")
        return _game_surface


def _get_gl_create_display_wrapper(original_create_display):
    """Wrap a create_display callable so rebuilt windows reapply GL overlay."""
    wrapper = _create_display_wrappers.get(original_create_display)
    if wrapper is not None:
        return wrapper

    def _gl_create_display(width, height, **kwargs):
        # Gereksinim 11.1: Tek-context aktif ve görünür pencere boyutu mevcut GL
        # yüzeyiyle aynıysa, alttaki create_display'i (ve onun set_mode'unu) HİÇ
        # çağırma. Steam hook'u ve GL context'i korunur; sadece offscreen yüzeyi
        # döndür. Bu kod tabanında pencere her zaman masaüstü çözünürlüğünde
        # sabit olduğundan rebuild'ler boyutu değiştirmez.
        if _active and _game_surface is not None and platform.system() == 'Windows':
            actual = get_display_surface()
            try:
                cur_w, cur_h = actual.get_size() if actual is not None else (0, 0)
                is_gl = bool(actual.get_flags() & pygame.OPENGL) if actual is not None else False
            except Exception:
                cur_w, cur_h, is_gl = 0, 0, False
            if is_gl and cur_w == _width and cur_h == _height:
                print(f"[GL Compat] Rebuild atlandı (tek-context, boyut sabit "
                      f"{_width}x{_height}); set_mode çağrılmadı")
                return _game_surface

        surface = original_create_display(width, height, **kwargs)
        return _reapply_gl(surface)

    _create_display_wrappers[original_create_display] = _gl_create_display
    return _gl_create_display


def _patch_create_display_module_refs(modules, original_to_wrapper: dict[object, object]) -> None:
    """Replace already-imported create_display globals that point to originals."""
    if not original_to_wrapper:
        return

    original_refs = set(original_to_wrapper.keys())
    for module in modules:
        module_dict = getattr(module, '__dict__', None)
        if not isinstance(module_dict, dict):
            continue
        current = module_dict.get('create_display')
        if current in original_refs:
            module_dict['create_display'] = original_to_wrapper[current]


def _patch_create_display():
    """Monkey-patch platform_utils.create_display to auto-apply GL wrapper.

    After first gl_overlay_setup, every subsequent create_display call
    (resize, fullscreen toggle, etc.) automatically re-creates the GL
    context and returns the offscreen game surface.
    """
    global _original_create_display

    try:
        modules = [module for module in list(sys.modules.values()) if module is not None]
        original_to_wrapper: dict[object, object] = {}

        for module in modules:
            module_name = str(getattr(module, '__name__', '') or '')
            if not module_name.endswith('platform_utils'):
                continue

            current = getattr(module, 'create_display', None)
            if not callable(current):
                continue
            if current in _create_display_wrappers.values():
                continue

            if _original_create_display is None:
                _original_create_display = current

            wrapper = _get_gl_create_display_wrapper(current)
            setattr(module, 'create_display', wrapper)
            original_to_wrapper[current] = wrapper

        if not original_to_wrapper:
            import platform_utils as _pu

            current = getattr(_pu, 'create_display', None)
            if callable(current):
                if _original_create_display is None:
                    _original_create_display = current
                wrapper = _get_gl_create_display_wrapper(current)
                _pu.create_display = wrapper
                original_to_wrapper[current] = wrapper
                modules = [module for module in list(sys.modules.values()) if module is not None]

        _patch_create_display_module_refs(modules, original_to_wrapper)
        print("[GL Compat] platform_utils.create_display patched")
    except Exception as e:
        print(f"[GL Compat] create_display patch hatası: {e}")


def _reapply_gl(display_surface: pygame.Surface) -> pygame.Surface:
    """Re-apply GL overlay on an existing display surface.

    Called internally after create_display or toggle_fullscreen to
    re-create the GL context on the new window.
    """
    global _game_surface, _tex_id, _width, _height, _supports_bgra_upload

    if not _active:
        return display_surface

    if platform.system() != 'Windows':
        return display_surface

    if display_surface is _game_surface:
        actual_surface = get_display_surface()
        if actual_surface is not None:
            display_surface = actual_surface

    w, h = display_surface.get_size()

    try:
        old_flags = display_surface.get_flags()
    except Exception:
        old_flags = 0
    already_gl = bool(old_flags & pygame.OPENGL)

    # Gereksinim 11.1/11.3: Tek-context aktif, pencere zaten OPENGL ve boyut
    # değişmiyorsa hiçbir şey yapma. Yeni set_mode YAPMA, texture'ı ve offscreen
    # yüzeyi yeniden OLUŞTURMA — Steam hook'u ve mevcut GL durumu korunur.
    if already_gl and w == _width and h == _height and _game_surface is not None:
        print(f"[GL Compat] GL reapply atlandı (tek-context, boyut sabit {w}x{h})")
        return _game_surface

    try:
        caption = pygame.display.get_caption()

        new_flags = (old_flags | pygame.OPENGL | pygame.DOUBLEBUF) & ~pygame.HWSURFACE
        # Yalnızca pencere henüz GL değilse ikinci set_mode'a izin ver (fallback yolu).
        if not already_gl:
            pygame.display.set_mode((w, h), new_flags)

        if caption and caption[0]:
            pygame.display.set_caption(caption[0])
    except pygame.error as e:
        print(f"[GL Compat] GL reapply display hatası: {e}")
        # Pencere GL ise ham surface'i oyuna verme; çizilebilir offscreen'i koru.
        if _game_surface is not None:
            return _game_surface
        return display_surface

    try:
        # Eski texture'ı sil
        if _tex_id:
            try:
                tex = ctypes.c_uint(_tex_id)
                _gl.glDeleteTextures(1, ctypes.byref(tex))
            except Exception:
                pass

        _setup_ortho(w, h)
        _tex_id = _create_texture(w, h)
        _width = w
        _height = h
        _supports_bgra_upload = None
        _game_surface = pygame.Surface((w, h))
        _game_surface.fill((0, 0, 0))
        print(f"[GL Compat] GL reapplied: {w}x{h}")
        return _game_surface
    except Exception as e:
        print(f"[GL Compat] GL reapply hatası: {e}")
        # Texture yeniden kurulamadı; pencere GL ise ham surface'i verme.
        if _game_surface is not None:
            return _game_surface
        return display_surface


def is_gl_active() -> bool:
    """Return True if the GL overlay wrapper is currently active."""
    return _active


def get_game_surface() -> pygame.Surface | None:
    """Return the offscreen game surface (or None if not active)."""
    return _game_surface


def should_skip_display_rebuild(width: int, height: int) -> bool:
    """VIDEORESIZE/rebuild handler'ları için GL-aware erken guard.

    Tek-context GL aktifken ve istenen boyut mevcut GL yüzeyiyle aynıysa True döner.
    True ise çağıran, ``create_display``/``set_mode`` ÇAĞIRMAMALI (Steam hook ve GL
    context korunur); bunun yerine ``get_game_surface()`` ile offscreen yüzeye devam
    etmelidir. Bu kod tabanında pencere her zaman masaüstü çözünürlüğünde sabit
    olduğundan rebuild'ler boyutu değiştirmez.
    """
    if not _active or _game_surface is None:
        return False
    if platform.system() != 'Windows':
        return False
    try:
        return int(width) == int(_width) and int(height) == int(_height)
    except Exception:
        return False
