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

def _gl_flip():
    """Upload game surface to GL texture, then do real GL buffer swap."""
    if _active and _game_surface is not None:
        try:
            _upload_and_draw(_game_surface, _tex_id, _width, _height)
        except Exception:
            pass
    _original_flip()


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

    # Steam SDK'sı yoksa GL'e gerek yok
    try:
        import steam_integration as _si
        if not _si.is_available():
            return display_surface
    except Exception:
        return display_surface

    if not _load_gl():
        return display_surface

    w, h = display_surface.get_size()

    # Re-create display with OPENGL flag
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

        print(f"[GL Compat] OpenGL display created: {w}x{h} flags=0x{new_flags:X}")
    except pygame.error as e:
        print(f"[GL Compat] OpenGL display oluşturulamadı: {e}")
        return display_surface

    # GL setup
    try:
        _setup_ortho(w, h)
        _tex_id = _create_texture(w, h)
        _width = w
        _height = h
        _supports_bgra_upload = None
    except Exception as e:
        print(f"[GL Compat] GL setup hatası: {e}")
        # Eski moda geri dön
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

    print(f"[GL Compat] Steam overlay GL wrapper aktif ({w}x{h})")
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
        caption = pygame.display.get_caption()

        new_flags = (old_flags | pygame.OPENGL | pygame.DOUBLEBUF) & ~pygame.HWSURFACE
        already_gl = bool(old_flags & pygame.OPENGL)
        if not already_gl:
            pygame.display.set_mode((w, h), new_flags)

        if caption and caption[0]:
            pygame.display.set_caption(caption[0])
    except pygame.error as e:
        print(f"[GL Compat] GL reapply display hatası: {e}")
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
        return display_surface


def is_gl_active() -> bool:
    """Return True if the GL overlay wrapper is currently active."""
    return _active


def get_game_surface() -> pygame.Surface | None:
    """Return the offscreen game surface (or None if not active)."""
    return _game_surface
