"""SDL2 donanım renderer tabanlı Steam overlay katmanı (Yol 2 — gl_compat alternatifi).

Bu modül, gl_compat.py'deki "manuel ctypes-OpenGL + offscreen CPU surface + her kare
texture-blit" mimarisinin yerine SDL2'nin RESMİ donanım renderer'ını (Windows'ta Direct3D11)
kullanır. Amaç: Steam overlay'in tek/resmi swapchain present'ine temiz şekilde hook olması ve
Windows DWM redirection uyumsuzluğunun (bayat-kare / çift-katman) kökten çözülmesi.

Mimari (pygame-ce 2.5.7, GERÇEK ORTAMDA DOĞRULANMIŞ API):
- `set_mode` ile açılan pencereye Renderer BAĞLANAMAZ ('Surface already associated with window').
  Bu yüzden pencere SAF `pygame._sdl2.video.Window` ile açılır (set_mode YOK).
- `Renderer(window, vsync=...)` — Windows'ta SDL varsayılanı Direct3D11.
- Tek kalıcı `Texture(renderer, (w,h), streaming=True)`; her kare `texture.update(surface)`.
- Sunum: `texture.update → renderer.clear → renderer.blit(texture, None) → renderer.present`.
  NOT: `blit(texture, None)` POZİSYONEL argüman; `dst=` kwarg DESTEKLENMEZ.

Oyun kodu hiç değişmez: `pygame.display.flip/update/get_surface` monkey-patch edilir; oyun yine
offscreen Surface'e çizer (gl_compat ile aynı sözleşme).

Yalnızca Windows + Steam SDK mevcutken etkin. Başarısızlıkta sessizce devre dışı kalır
(çağıran software pencereye düşer). macOS/Linux'ta no-op.
"""

from __future__ import annotations

import os
import platform
import sys

import pygame

# ---------------------------------------------------------------------------
# Modül durumu
# ---------------------------------------------------------------------------
_active = False
_window = None            # pygame._sdl2.video.Window
_renderer = None          # pygame._sdl2.video.Renderer
_texture = None           # pygame._sdl2.video.Texture (kalıcı, streaming)
_game_surface: pygame.Surface | None = None
_width: int = 0
_height: int = 0

_original_flip = pygame.display.flip
_original_update = pygame.display.update
_original_get_surface = pygame.display.get_surface
_original_set_caption = pygame.display.set_caption
_original_get_active = getattr(pygame.display, 'get_active', None)

# Software imleç hook'u: SDL2 renderer penceresinde donanım imleci görünmediği için
# main.py bir imleç yüzeyi + hotspot kaydeder; her present'te offscreen'e çizilir.
_cursor_surface: pygame.Surface | None = None
_cursor_hotspot = (0, 0)
_cursor_enabled = True

# Teşhis günlüğü (gl_compat ile aynı dosyaya yazar: gl_debug.log)
_diag_log_path: str | None = None
_diag_log_resolved = False


def _diag_enabled() -> bool:
    raw = os.environ.get('QUADRIX_GL_DEBUG')
    if raw is None:
        if ('pytest' in sys.modules) or any('pytest' in str(a) for a in sys.argv):
            return False
        return True
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
    line = f"[SDL2 Overlay] {message}"
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


# ---------------------------------------------------------------------------
# Yetenek / koşul kontrolü
# ---------------------------------------------------------------------------

def _sdl2_video_available() -> bool:
    """pygame._sdl2.video import edilebiliyor mu (Renderer/Texture dahil)."""
    try:
        from pygame._sdl2.video import Window, Renderer, Texture  # noqa: F401
        return True
    except Exception as exc:
        _diag_log(f"_sdl2.video import edilemedi: {exc}")
        return False


def _hide_setmode_window_from_taskbar() -> None:
    """Gizli set_mode penceresini görev çubuğu/Alt+Tab'dan KESİN olarak kaldır.

    set_mode((1,1), HIDDEN) penceresi normalde görünmez; ama herhangi bir kod onu
    show() ederse yine de belirebilir. WS_EX_TOOLWINDOW stili uygulayıp
    WS_EX_APPWINDOW'u kaldırarak pencere, show edilse bile görev çubuğunda/Alt+Tab'da
    ASLA görünmez. Yalnızca Windows; hata-toleranslı; başka platformda no-op.
    """
    if platform.system() != 'Windows':
        return
    try:
        info = pygame.display.get_wm_info()
        hwnd = info.get('window') if isinstance(info, dict) else None
        if not hwnd:
            return
        import ctypes
        GWL_EXSTYLE = -20
        WS_EX_TOOLWINDOW = 0x00000080
        WS_EX_APPWINDOW = 0x00040000
        user32 = ctypes.windll.user32
        user32.GetWindowLongW.restype = ctypes.c_long
        user32.GetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int]
        user32.SetWindowLongW.restype = ctypes.c_long
        user32.SetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_long]
        hwnd_p = ctypes.c_void_p(int(hwnd))
        ex = user32.GetWindowLongW(hwnd_p, GWL_EXSTYLE)
        new_ex = (ex | WS_EX_TOOLWINDOW) & ~WS_EX_APPWINDOW
        user32.SetWindowLongW(hwnd_p, GWL_EXSTYLE, new_ex)
        # Görünürlük durumunu kesinleştir: pencereyi gizle (SW_HIDE=0).
        try:
            user32.ShowWindow(hwnd_p, 0)
        except Exception:
            pass
        _diag_log(
            f"set_mode penceresi görev çubuğundan gizlendi (HWND=0x{int(hwnd):X}, "
            f"exStyle 0x{ex:X}→0x{new_ex:X})"
        )
    except Exception as exc:
        _diag_log(f"_hide_setmode_window_from_taskbar hatası: {exc}")


def _should_use_sdl2() -> bool:
    """SDL2 renderer overlay yolu bu platformda kullanılmalı mı?

    Koşullar (hepsi gerekli):
    - Windows (Steam overlay D3D hook gereği).
    - Steam SDK erişilebilir.
    - pygame._sdl2.video mevcut.
    """
    if platform.system() != 'Windows':
        _diag_log(f"_should_use_sdl2=False (platform={platform.system()} != Windows)")
        return False
    try:
        import steam_integration as _si
        if not _si.is_available():
            _diag_log("_should_use_sdl2=False (steam_integration.is_available()=False)")
            return False
    except Exception as exc:
        _diag_log(f"_should_use_sdl2=False (steam_integration hatası: {exc})")
        return False
    ok = _sdl2_video_available()
    _diag_log(f"_should_use_sdl2={ok} (Windows + Steam OK, _sdl2.video={ok})")
    return ok


# ---------------------------------------------------------------------------
# Monkey-patch hedefleri
# ---------------------------------------------------------------------------

def _present():
    """Offscreen surface'i GPU texture'a yükleyip SDL renderer ile sun."""
    if not _active:
        return
    try:
        # Software imleci offscreen'e çiz (donanım imleci SDL2 renderer'da görünmez).
        _draw_software_cursor()
        if _texture is not None and _game_surface is not None:
            _texture.update(_game_surface)
        if _renderer is not None:
            _renderer.clear()
            if _texture is not None:
                _renderer.blit(_texture, None)  # POZİSYONEL — dst= kwarg yok
            _renderer.present()
    except Exception as exc:
        _diag_log(f"_present hatası: {exc}")


def _patched_flip():
    _present()


def _patched_set_caption(title, *args, **kwargs):
    """set_caption'ı görünür _sdl2 Window'a yönlendir (ve orijinali de çağır)."""
    try:
        if _window is not None:
            _window.title = str(title)
    except Exception:
        pass
    try:
        return _original_set_caption(title, *args, **kwargs)
    except Exception:
        return None


def _patched_get_active():
    """SDL2 aktifken pencere odağını görünür _sdl2 Window'dan bildir.

    Gizli set_mode penceresi her zaman 'inaktif' göründüğü için ham get_active
    yanlış (False) döner ve gereksiz focus-recovery tetikler. _sdl2 Window'un
    gerçek odak durumunu döndürürüz.
    """
    if _active and _window is not None:
        try:
            return bool(_window.focused)
        except Exception:
            pass
    if callable(_original_get_active):
        try:
            return _original_get_active()
        except Exception:
            return True
    return True


def _patched_update(rectangle=None):
    _present()


def _patched_get_surface():
    if _active and _game_surface is not None:
        return _game_surface
    return _original_get_surface()


def get_display_surface():
    """Gerçek görünür yüzey yerine offscreen oyun yüzeyini döndür (gl_compat paritesi)."""
    if _active and _game_surface is not None:
        return _game_surface
    try:
        return _original_get_surface()
    except Exception:
        return None


def is_active() -> bool:
    return _active


def is_gl_active() -> bool:
    """gl_compat arayüz paritesi: overlay katmanı aktif mi."""
    return _active


def set_software_cursor(surface, hotspot=(0, 0)) -> None:
    """Software imleç yüzeyini kaydet (SDL2 renderer'da donanım imleci görünmez).

    main.py setup_custom_cursor içinde çağırır; her present'te offscreen'e çizilir.
    surface None ise imleç çizimi devre dışı kalır.
    """
    global _cursor_surface, _cursor_hotspot
    _cursor_surface = surface
    try:
        _cursor_hotspot = (int(hotspot[0]), int(hotspot[1]))
    except Exception:
        _cursor_hotspot = (0, 0)


def set_software_cursor_enabled(enabled: bool) -> None:
    """İmleç çizimini aç/kapat (oyun içinde gizlemek için)."""
    global _cursor_enabled
    _cursor_enabled = bool(enabled)


def _draw_software_cursor() -> None:
    """Kayıtlı imleç yüzeyini offscreen game surface'e çiz (present öncesi)."""
    if not _cursor_enabled or _cursor_surface is None or _game_surface is None:
        return
    try:
        if not pygame.mouse.get_visible():
            return
    except Exception:
        return
    try:
        mx, my = pygame.mouse.get_pos()
        hx, hy = _cursor_hotspot
        _game_surface.blit(_cursor_surface, (int(mx) - hx, int(my) - hy))
    except Exception:
        pass


def get_game_surface() -> pygame.Surface | None:
    return _game_surface


def get_window():
    """Aktif _sdl2 Window nesnesini döndür (yoksa None). Icon/caption köprüsü için."""
    return _window if _active else None


def apply_window_icon(icon_surface) -> bool:
    """Aktif _sdl2 Window'a ikon uygula (set_app_icon köprüsü).

    _sdl2.Window modunda pygame.display.set_icon ve get_wm_info HWND yolu çalışmaz;
    bunun yerine Window.set_icon() kullanılır. Hata-toleranslı.
    """
    if not _active or _window is None or icon_surface is None:
        return False
    try:
        setter = getattr(_window, 'set_icon', None)
        if callable(setter):
            setter(icon_surface)
            return True
    except Exception as exc:
        _diag_log(f"apply_window_icon hatası: {exc}")
    return False


def set_caption(title: str) -> bool:
    """Aktif _sdl2 Window başlığını ayarla (pygame.display.set_caption köprüsü)."""
    if not _active or _window is None:
        return False
    try:
        _window.title = str(title)
        return True
    except Exception:
        return False


def should_skip_display_rebuild(width: int, height: int) -> bool:
    """VIDEORESIZE/rebuild guard'ı: aktif + boyut sabitse rebuild atlanmalı."""
    if not _active or _game_surface is None:
        return False
    if platform.system() != 'Windows':
        return False
    try:
        return int(width) == int(_width) and int(height) == int(_height)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Public API — kurulum
# ---------------------------------------------------------------------------

def prepare_single_context() -> bool:
    """gl_compat.prepare_single_context paritesi — SDL2 yolunda no-op niyet bildirimi.

    SDL2 backend'inde pencere doğrudan setup() içinde _sdl2.Window ile yaratılır; create_display
    öncesi bir bayrağa gerek yoktur. Sadece kullanılabilirliği loglar.
    """
    avail = _should_use_sdl2()
    _diag_log(f"prepare_single_context (sdl2): kullanılabilir={avail}")
    return avail


def setup(display_surface: pygame.Surface | None = None) -> pygame.Surface | None:
    """SDL2 renderer pipeline'ını kur ve oyunun çizeceği offscreen surface'i döndür.

    display_surface: create_display'in döndürdüğü mevcut (software) surface; boyut kaynağı
    olarak kullanılır. Pencere SAF _sdl2.Window ile yeniden açılır (set_mode penceresine
    renderer bağlanamadığı için).

    Başarısızlıkta None döndürür → çağıran mevcut software surface ile devam etmeli.
    """
    global _active, _window, _renderer, _texture, _game_surface, _width, _height

    if not _should_use_sdl2():
        return None

    # Boyut: verilen surface'ten, yoksa native çözünürlükten.
    try:
        if display_surface is not None:
            w, h = display_surface.get_size()
        else:
            raise ValueError('no surface')
    except Exception:
        try:
            import platform_utils as _pu
            w, h = _pu.get_native_resolution()
        except Exception:
            w, h = 1920, 1080
    w, h = int(w), int(h)

    try:
        from pygame._sdl2.video import Window, Renderer, Texture
    except Exception as exc:
        _diag_log(f"setup: _sdl2.video import başarısız: {exc}")
        return None

    # vsync ayarını oku (mevcut SDL_RENDER_VSYNC env'iyle tutarlı)
    try:
        vsync = str(os.environ.get('SDL_RENDER_VSYNC', '1')).strip() not in ('0', 'false', 'off')
    except Exception:
        vsync = True

    caption = 'Quadrix'
    try:
        cap = pygame.display.get_caption()
        if cap and cap[0]:
            caption = cap[0]
    except Exception:
        pass

    try:
        # ÖNEMLİ: pygame.display.quit() ÇAĞIRMA! Bu, convert()/convert_alpha() formatını
        # sıfırlar ve oyun kodunun her yerinde "No convert format has been set" çökmesine
        # yol açar.
        #
        # ÖNEMLİ #2: set_mode penceresini KÜÇÜLTME (1x1 YAPMA)! pygame.mouse / event
        # sistemi ve pygame.display.get_window_size() hâlâ bu set_mode penceresine bağlıdır.
        # 1x1'e küçültülürse get_window_size()=(1,1) döner; normalize_mouse_pos ölçeği
        # 1920/1=1920x olur → mouse koordinatları astronomik büyür, tıklama/etkileşim ölür,
        # ölçekleme bozulur ve bozuk koordinatlar dev bir Surface yaratıp "Out of memory"
        # çökmesine yol açar.
        #
        # DOĞRU YOL: set_mode penceresini TAM BOYUTTA tut ama yalnızca GİZLE (HIDDEN).
        # Böylece get_window_size()=(w,h) korunur (mouse ölçeği 1.0, etkileşim çalışır),
        # convert formatı korunur ve pencere görev çubuğu/Alt+Tab'da görünmez (TOOLWINDOW
        # stili ile pekiştirilir) → asıl görünür pencere ayrı _sdl2.Window olur, TEK pencere.
        try:
            pygame.display.set_mode((w, h), pygame.HIDDEN)
        except Exception:
            # HIDDEN flag yoksa en azından pencereyi gizle (boyutu KÜÇÜLTME).
            try:
                Window.from_display_module().hide()
            except Exception:
                pass

        # KESİN ÇÖZÜM: set_mode penceresini görev çubuğu/Alt+Tab'dan tamamen kaldır
        # (WS_EX_TOOLWINDOW). Böylece herhangi bir kod onu show etse bile ikinci
        # pencere olarak GÖRÜNMEZ.
        _hide_setmode_window_from_taskbar()

        # Pencereyi GİZLİ oluştur ki "pygame window" başlıklı çerçeve anlık parlamasın.
        try:
            win = Window(caption, size=(w, h), hidden=True)
        except TypeError:
            win = Window(caption, size=(w, h))
            try:
                win.hide()
            except Exception:
                pass

        # Başlık + borderless + konum GÖSTERMEDEN ÖNCE ayarla (flash'ı önler).
        try:
            win.title = caption
        except Exception:
            pass
        try:
            win.borderless = True
        except Exception:
            pass
        try:
            win.position = (0, 0)
        except Exception:
            pass

        try:
            renderer = Renderer(win, vsync=vsync)
        except TypeError:
            renderer = Renderer(win)  # vsync kwarg yoksa

        # Hangi SDL render sürücüleri mevcut, logla (D3D11 varsa overlay hook olabilir).
        # Not: _sdl2 seçili sürücüyü doğrudan vermez; mevcut sürücü listesini loglarız.
        try:
            from pygame._sdl2.video import get_drivers as _get_drivers
            _drv_names = [getattr(d, 'name', '?') for d in _get_drivers()]
            _diag_log(f"setup: mevcut SDL render sürücüleri={_drv_names} "
                      f"(SDL_RENDER_DRIVER={os.environ.get('SDL_RENDER_DRIVER')})")
        except Exception as _drv_exc:
            _diag_log(f"setup: render sürücü listesi alınamadı: {_drv_exc}")

        texture = Texture(renderer, (w, h), streaming=True)

        game_surface = pygame.Surface((w, h))
        game_surface.fill((0, 0, 0))

        # Pencereyi şimdi göster (tüm ayarlar tamam; flash yok).
        try:
            win.show()
            win.focus()
        except Exception:
            pass
    except Exception as exc:
        _diag_log(f"setup BAŞARISIZ ({exc}); SDL2 overlay devre dışı, software'e düşülecek")
        # Software fallback: convert formatı korunmuş ama set_mode penceresi HIDDEN'a
        # alınmış olabilir; tam boyutlu GÖRÜNÜR software pencereyi geri kur.
        try:
            pygame.display.set_mode((w, h), pygame.NOFRAME | pygame.DOUBLEBUF)
        except Exception:
            pass
        return None

    _window = win
    _renderer = renderer
    _texture = texture
    _game_surface = game_surface
    _width = w
    _height = h
    _active = True

    # Monkey-patch present yolu (gl_compat ile aynı sözleşme).
    pygame.display.flip = _patched_flip
    pygame.display.update = _patched_update
    pygame.display.get_surface = _patched_get_surface
    # set_caption ve get_active'i de görünür _sdl2 Window'a yönlendir.
    pygame.display.set_caption = _patched_set_caption
    try:
        pygame.display.get_active = _patched_get_active
    except Exception:
        pass

    # İlk temiz kareyi sun (Steam hook'a "pencere canlı" sinyali).
    try:
        _present()
        pygame.event.pump()
    except Exception:
        pass

    _diag_log(f"setup OK — SDL2 renderer overlay AKTİF ({w}x{h}, vsync={vsync})")
    return _game_surface


def gl_overlay_setup(display_surface: pygame.Surface) -> pygame.Surface:
    """gl_compat.gl_overlay_setup paritesi: setup() çağırır, başarısızsa orijinali döndürür."""
    result = setup(display_surface)
    if result is not None:
        return result
    return display_surface


def _reapply_gl(display_surface: pygame.Surface) -> pygame.Surface:
    """gl_compat._reapply_gl paritesi: SDL2 yolunda boyut sabitse offscreen'i koru."""
    if not _active:
        return display_surface
    if _game_surface is not None:
        return _game_surface
    return display_surface


def teardown() -> None:
    """SDL2 renderer kaynaklarını serbest bırak ve monkey-patch'leri geri al."""
    global _active, _window, _renderer, _texture, _game_surface
    pygame.display.flip = _original_flip
    pygame.display.update = _original_update
    pygame.display.get_surface = _original_get_surface
    pygame.display.set_caption = _original_set_caption
    try:
        if callable(_original_get_active):
            pygame.display.get_active = _original_get_active
    except Exception:
        pass
    _active = False
    for obj_name in ('_texture', '_renderer', '_window'):
        obj = globals().get(obj_name)
        try:
            if obj is not None and hasattr(obj, 'destroy'):
                obj.destroy()
        except Exception:
            pass
    _texture = None
    _renderer = None
    _window = None
    _game_surface = None
