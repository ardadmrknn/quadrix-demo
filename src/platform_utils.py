"""Platform-specific utilities for cross-platform compatibility.

This module provides helper functions that abstract OS-specific behaviors.
"""

import os
import platform
import subprocess
import sys
import time

import pygame


# Detect macOS at module load time
IS_MACOS = sys.platform == 'darwin'
IS_WINDOWS = sys.platform == 'win32'
IS_LINUX = sys.platform.startswith('linux')

_REFRESH_RATE_CACHE_HZ = 0
_REFRESH_RATE_CACHE_AT = 0.0
_REFRESH_RATE_CACHE_TTL_S = 1.0
_STARTUP_FOCUS_WARMUP_STATE: dict | None = None

# Steam overlay tek-context (single-context) koordinasyonu.
# gl_compat, ilk create_display() çağrısından önce bu bayrağı True yaparak
# pencerenin baştan OpenGL context'i ile açılmasını ister. Böylece ikinci bir
# set_mode(OPENGL) çağrısına gerek kalmaz ve Steam overlay hook'u doğru
# swapchain'e bağlanır. Yalnızca Windows borderless tam ekran yolunda etkilidir.
_GL_WINDOW_REQUEST = False

# macOS: SDL Fullscreen Spaces ayarı.
# Çerçevesiz tam ekran (NOFRAME borderless) kullanıldığı için bu değer
# doğrudan etkisiz ama 0 olarak bırakılıyor (exclusive fullscreen uyumluluğu).
# Bu env, pygame.init() öncesi set edilmeli.
if IS_MACOS:
    os.environ.setdefault('SDL_VIDEO_MAC_FULLSCREEN_SPACES', '0')
    os.environ.setdefault('SDL_VIDEO_MINIMIZE_ON_FOCUS_LOSS', '0')

# Windows: Focus kaybında (Alt+Tab, PrintScreen vb.) tam ekran penceresinin
# minimize olmasını engelle. Ekran görüntüsü alırken pencere küçülmesin.
if IS_WINDOWS:
    os.environ.setdefault('SDL_VIDEO_MINIMIZE_ON_FOCUS_LOSS', '0')


def safe_blit(dest: pygame.Surface, src: pygame.Surface, pos, special_flags: int = 0) -> None:
    """Platform-safe blit with exception fallback.
    
    Pygame 2.x sürümünde BLEND flag'leri macOS dahil tüm platformlarda
    kararlı çalışmaktadır. Eski Pygame 1.x workaround'u kaldırılmıştır.
    
    Args:
        dest: Hedef surface
        src: Kaynak surface
        pos: Pozisyon (tuple veya Rect)
        special_flags: pygame BLEND flags
    """
    try:
        dest.blit(src, pos, special_flags=special_flags)
    except Exception:
        # Fallback: basit blit (flag'siz)
        try:
            dest.blit(src, pos)
        except Exception:
            pass  # En kötü durumda sessizce devam et




# Windows DPI Awareness - pencere boyutlarının doğru hesaplanması için
def _init_windows_dpi_awareness():
    """Windows 10/11 için DPI awareness ayarla."""
    if not IS_WINDOWS:
        return
    try:
        import ctypes
        # Per-Monitor DPI Awareness v2 (Windows 10 1703+)
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except (AttributeError, OSError):
            # Eski Windows versiyonları için fallback
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except (AttributeError, OSError):
                pass
    except Exception:
        pass  # DPI awareness opsiyonel, hata verirse devam et


def is_primary_modifier(mods: int) -> bool:
    """Check if the primary modifier key is pressed.
    
    On macOS, users expect to use Command (⌘) key for shortcuts like Cmd+N, Cmd+D.
    On Windows/Linux, users expect to use Ctrl key.
    
    Args:
        mods: The modifier key bitmask from pygame.key.get_mods()
        
    Returns:
        True if the appropriate primary modifier is pressed for the current OS.
    """
    if IS_MACOS:
        # On macOS, use Command/Meta key (KMOD_META = KMOD_LGUI | KMOD_RGUI)
        return bool(mods & pygame.KMOD_META)
    else:
        # On Windows/Linux, use Ctrl key
        return bool(mods & pygame.KMOD_CTRL)


def get_modifier_key_name() -> str:
    """Get the display name for the primary modifier key.
    
    Returns:
        'Cmd' on macOS, 'Ctrl' on Windows/Linux.
    """
    return 'Cmd' if IS_MACOS else 'Ctrl'


# Generic (Windows/Linux) tuş etiketlerini macOS klavye terminolojisine çeviren
# tablo. Mac klavyelerinde Enter "return", Backspace "delete" (⌫), Escape "esc"
# olarak yazar; bu yüzden kullanıcıya gösterilen kısayol ipuçları platforma göre
# farklılaşmalı. Anahtarlar BÜYÜK harfle normalize edilerek aranır.
_MACOS_KEY_LABELS = {
    'ENTER': 'return',
    'RETURN': 'return',
    'BACKSPACE': 'delete',
    'DELETE': 'delete',
    'ESC': 'esc',
    'ESCAPE': 'esc',
    'CMD': '⌘',
    'CTRL': '⌃',
    'CONTROL': '⌃',
    'ALT': '⌥',
    'OPTION': '⌥',
    'SHIFT': '⇧',
    'SPACE': 'space',
    'TAB': 'tab',
}


def key_hint_label(label: str) -> str:
    """Return a platform-appropriate display label for a keyboard hint.

    Windows/Linux'ta etiket olduğu gibi döner. macOS'ta yaygın tuşlar Mac
    klavye terminolojisine çevrilir (ENTER→return, BACKSPACE→delete, ESC→esc).
    ``'ENTER / ESC'`` gibi ayraçlı çoklu etiketler de parça parça çevrilir.

    Args:
        label: Gösterilecek ham tuş ipucu (ör. ``'ENTER / ESC'``).

    Returns:
        Platforma uygun etiket.
    """
    if not label:
        return label
    if not IS_MACOS:
        return label

    def _translate_token(token: str) -> str:
        stripped = token.strip()
        if not stripped:
            return token
        mapped = _MACOS_KEY_LABELS.get(stripped.upper())
        if mapped is None:
            return token
        # Orijinal token etrafındaki boşlukları koru (ör. ' / ' ayraçları).
        leading = token[: len(token) - len(token.lstrip())]
        trailing = token[len(token.rstrip()) :]
        return f"{leading}{mapped}{trailing}"

    # '/' ayracını koruyarak her parçayı ayrı çevir.
    if '/' in label:
        return '/'.join(_translate_token(part) for part in label.split('/'))
    return _translate_token(label)



def get_display_flags(resizable: bool = True, fullscreen: bool = False, vsync: bool = True) -> int:
    """Get the appropriate pygame display flags for the current platform.
    
    On macOS, uses minimal flags to avoid crash.
    On Windows, includes HWSURFACE for hardware acceleration.
    
    Args:
        resizable: Whether the window should be resizable.
        fullscreen: Whether to use fullscreen mode.
        vsync: Whether to enable vertical sync (reduces tearing).
        
    Returns:
        Combined pygame display flags.
    """
    # macOS: Minimal flags - crash'i önlemek için
    if IS_MACOS:
        flags = 0
        if fullscreen:
            if hasattr(pygame, 'FULLSCREEN'):
                flags |= pygame.FULLSCREEN
        elif resizable:
            flags |= pygame.RESIZABLE
        return flags
    
    # Windows/Linux için flags
    flags = pygame.DOUBLEBUF
    if IS_WINDOWS:
        flags |= pygame.HWSURFACE
    
    if fullscreen:
        # Native fullscreen - ekranın tam çözünürlüğünü kullan
        flags |= pygame.FULLSCREEN
    elif resizable:
        flags |= pygame.RESIZABLE
    
    return flags


def invalidate_refresh_rate_cache() -> None:
    """Invalidate the cached display refresh rate."""
    global _REFRESH_RATE_CACHE_HZ, _REFRESH_RATE_CACHE_AT
    _REFRESH_RATE_CACHE_HZ = 0
    _REFRESH_RATE_CACHE_AT = 0.0


def _query_max_refresh_rate() -> int:
    """Query the active window refresh rate directly from pygame/SDL."""
    try:
        if hasattr(pygame.display, 'get_current_refresh_rate'):
            refresh_rate = int(pygame.display.get_current_refresh_rate() or 0)
            if refresh_rate > 0:
                return refresh_rate
    except Exception:
        pass

    try:
        if hasattr(pygame.display, 'get_desktop_refresh_rates'):
            refresh_rates = [
                int(rate)
                for rate in (pygame.display.get_desktop_refresh_rates() or [])
                if int(rate or 0) > 0
            ]
            if refresh_rates:
                return max(refresh_rates)
    except Exception:
        pass

    try:
        if hasattr(pygame.display, 'get_num_displays'):
            num = int(pygame.display.get_num_displays() or 0)
            if num > 0 and hasattr(pygame.display, 'get_current_display_mode'):
                refresh_rates = []
                for display_idx in range(num):
                    mode = pygame.display.get_current_display_mode(display_idx)
                    rate = int(getattr(mode, 'refresh_rate', 0) or 0)
                    if rate > 0:
                        refresh_rates.append(rate)
                if refresh_rates:
                    return max(refresh_rates)
    except Exception:
        pass

    return 60


def get_max_refresh_rate(force_refresh: bool = False) -> int:
    """Get the cached maximum refresh rate of the primary display.

    The raw display query is cached briefly because the main loop may ask for
    the auto FPS cap every frame.

    Returns:
        int: The refresh rate in Hz, or 60 as fallback.
    """
    global _REFRESH_RATE_CACHE_HZ, _REFRESH_RATE_CACHE_AT

    now = time.monotonic()
    if (
        not force_refresh
        and _REFRESH_RATE_CACHE_HZ > 0
        and (now - _REFRESH_RATE_CACHE_AT) < _REFRESH_RATE_CACHE_TTL_S
    ):
        return _REFRESH_RATE_CACHE_HZ

    refresh_rate = int(_query_max_refresh_rate() or 60)
    if refresh_rate <= 0:
        refresh_rate = 60

    _REFRESH_RATE_CACHE_HZ = refresh_rate
    _REFRESH_RATE_CACHE_AT = now
    return refresh_rate


def resolve_frame_rate_cap(requested_limit: int | None, fallback: int = 60) -> int:
    """Resolve the effective FPS cap.

    Ayarlarda 0 veya negatif değer "otomatik" anlamına gelir ve mevcut
    ekran yenileme hızına kilitlenir. Geçersiz ekran verisi gelirse fallback
    kullanılır.
    """
    try:
        limit = int(requested_limit or 0)
    except Exception:
        limit = 0

    if limit > 0:
        return max(1, limit)

    try:
        refresh_rate = int(round(float(get_max_refresh_rate())))
    except Exception:
        refresh_rate = 0

    if refresh_rate < 24 or refresh_rate > 1000:
        import sys
        # macOS üzerinde ProMotion ekranların gücünden tam yararlanmak için
        # varsayılan otomatik fallback yenileme hızını (eğer özel bir fallback
        # belirtilmemişse veya varsayılan 60 ise) 90 yapıyoruz.
        if sys.platform == 'darwin' and fallback == 60:
            refresh_rate = 90
        else:
            refresh_rate = int(fallback or 60)

    return max(1, refresh_rate)


def request_window_focus():
    """Request the window to be brought to the front and focused.
    
    On macOS, applications sometimes start in the background.
    This function attempts to ensure the window gets focus.
    """
    if IS_WINDOWS:
        # SDL2 overlay aktifse: asıl görünür pencere ayrı bir _sdl2.Window'dur ve
        # set_mode penceresi TAM BOYUT + HIDDEN tutulur. Burada get_wm_info() set_mode
        # penceresinin HWND'sini döndürür; ona ShowWindow(SW_SHOW) çağırmak GİZLİ
        # pencereyi geri açar → İKİNCİ PENCERE belirir. Bu yüzden overlay aktifken
        # odağı görünür _sdl2.Window'a yönlendir, set_mode penceresine DOKUNMA.
        try:
            _mod = sys.modules.get('sdl2_overlay')
            if _mod is not None:
                _is_active = getattr(_mod, 'is_active', None)
                _get_window = getattr(_mod, 'get_window', None)
                if callable(_is_active) and _is_active() and callable(_get_window):
                    _ovl_win = _get_window()
                    if _ovl_win is not None:
                        try:
                            _ovl_win.focus()
                        except Exception:
                            pass
                        return
        except Exception:
            pass
        try:
            info = pygame.display.get_wm_info() if hasattr(pygame.display, 'get_wm_info') else {}
            hwnd = None
            if isinstance(info, dict):
                hwnd = info.get('window') or info.get('hwnd')
            if hwnd:
                import ctypes
                user32 = ctypes.windll.user32
                user32.ShowWindow(hwnd, 5)  # SW_SHOW
                user32.SetForegroundWindow(hwnd)
                user32.SetActiveWindow(hwnd)
                user32.SetFocus(hwnd)
        except Exception:
            pass
        return

    if IS_MACOS:
        try:
            # Attempt to raise the pygame window to the front
            # This uses the pygame display module's internal methods
            try:
                pygame.event.pump()
            except Exception:
                pass
            pygame.display.get_active()

            # Additional macOS-specific focus request using PyObjC if available
            try:
                import AppKit

                app = AppKit.NSApplication.sharedApplication()
                try:
                    app.finishLaunching()
                except Exception:
                    pass
                try:
                    app.unhide_(None)
                except Exception:
                    pass
                app.activateIgnoringOtherApps_(True)

                running_app = getattr(AppKit, 'NSRunningApplication', None)
                if running_app is not None:
                    try:
                        current_app = running_app.currentApplication()
                        activate_opts = getattr(AppKit, 'NSApplicationActivateIgnoringOtherApps', 1 << 1)
                        if current_app is not None:
                            current_app.activateWithOptions_(activate_opts)
                    except Exception:
                        pass
            except ImportError:
                # PyObjC not installed, this is optional
                pass
        except Exception:
            # Silently ignore any focus-related errors
            pass


def arm_startup_focus_warmup(duration_ms: int = 2500, retry_interval_ms: int = 120) -> bool:
    """Retry focus requests for a short window during macOS packaged startup."""
    global _STARTUP_FOCUS_WARMUP_STATE

    if not IS_MACOS or not getattr(sys, 'frozen', False):
        _STARTUP_FOCUS_WARMUP_STATE = None
        return False

    duration_ms = max(250, int(duration_ms or 0))
    retry_interval_ms = max(40, int(retry_interval_ms or 0))
    now_ms = pygame.time.get_ticks()
    request_window_focus()
    _STARTUP_FOCUS_WARMUP_STATE = {
        'expires_at_ms': now_ms + duration_ms,
        'retry_interval_ms': retry_interval_ms,
        'next_attempt_ms': now_ms + retry_interval_ms,
        'attempts': 1,
    }
    return True


def pump_startup_focus_warmup() -> bool:
    """Issue a best-effort delayed focus request during packaged macOS startup."""
    global _STARTUP_FOCUS_WARMUP_STATE

    state = _STARTUP_FOCUS_WARMUP_STATE
    if not IS_MACOS or state is None:
        return False

    now_ms = pygame.time.get_ticks()
    try:
        is_active = bool(pygame.display.get_active())
    except Exception:
        is_active = False

    if is_active or now_ms >= int(state.get('expires_at_ms', 0)):
        _STARTUP_FOCUS_WARMUP_STATE = None
        return False

    if now_ms < int(state.get('next_attempt_ms', 0)):
        return False

    request_window_focus()
    state['attempts'] = int(state.get('attempts', 0)) + 1
    state['next_attempt_ms'] = now_ms + int(state.get('retry_interval_ms', 120))
    return True


def preload_app_icon(assets_dir: str) -> None:
    """Pencere ikonunu pencere OLUŞTURULMADAN ÖNCE uygula.

    Sorun: `create_display()` ile pencere açıldığında, asıl ikon ancak Steam
    overlay / GL kurulumu bittikten sonra (`set_app_icon`) ayarlanıyordu. Bu
    aradaki ~1-2 saniyede dock/görev çubuğunda SDL'in VARSAYILAN pygame logosu
    görünüyordu.

    Pygame/SDL2, `pygame.display.set_icon()` ilk `set_mode()` çağrısından ÖNCE
    çağrılırsa ikonu pencereye doğuştan uygular. Bu fonksiyon tam da bunu yapar:
    `pygame.init()` sonrası, `create_display()` ÖNCESİ çağrılmalıdır.

    Ek olarak macOS'ta Dock simgesi AppKit ile baştan ayarlanır (pencere
    gerektirmez). Windows HWND seviyesindeki ince ayar pencere oluştuktan sonra
    `set_app_icon()` tarafından tamamlanır.
    """
    import os
    import pygame

    # ── Pygame pencere ikonu (set_mode ÖNCESİ → pencere baştan doğru ikonla açılır) ──
    _icon_candidates = [
        os.path.join(assets_dir, 'quadrix_icon.ico'),
        os.path.join(assets_dir, 'quadrix_icon.png'),
    ]
    for _icon_file in _icon_candidates:
        if os.path.exists(_icon_file):
            try:
                icon_surf = pygame.image.load(_icon_file)
                # convert_alpha için display gerekebilir; set_mode öncesi güvenli olsun
                try:
                    icon_surf = icon_surf.convert_alpha()
                except Exception:
                    pass
                icon_surf = pygame.transform.smoothscale(icon_surf, (32, 32))
                pygame.display.set_icon(icon_surf)
                break
            except Exception:
                continue

    # ── macOS Dock simgesi (pencere gerektirmez; baştan ayarla) ──
    if IS_MACOS:
        icns_path = os.path.join(assets_dir, 'quadrix_icon.icns')
        if not os.path.exists(icns_path):
            _fallback_png = os.path.join(assets_dir, 'quadrix_icon.png')
            icns_path = _fallback_png if os.path.exists(_fallback_png) else icns_path
        try:
            from AppKit import NSApplication, NSImage
            abs_path = os.path.abspath(icns_path)
            image = NSImage.alloc().initWithContentsOfFile_(abs_path)
            if image:
                NSApplication.sharedApplication().setApplicationIconImage_(image)
        except Exception:
            pass


def set_app_icon(assets_dir: str) -> None:
    """Pencere ve görev çubuğu simgesini ayarla.

    - pygame.display.set_icon() ile tüm platformlarda simgeyi günceller.
    - Windows'ta AppUserModelID ile görev çubuğu simgesi ve ismi düzeltilir.
    - macOS'ta AppKit üzerinden Dock simgesini quadrix_icon.icns ile değiştirir.
    """
    import os
    import pygame

    # ── Pygame pencere ikonu (tüm platformlar) — 32x32 standart SDL2 boyutu ──
    # Önce ICO, fallback olarak PNG dene
    _icon_candidates = [
        os.path.join(assets_dir, 'quadrix_icon.ico'),
        os.path.join(assets_dir, 'quadrix_icon.png'),
    ]
    _loaded_icon_surf = None
    for _icon_file in _icon_candidates:
        if os.path.exists(_icon_file):
            try:
                icon_surf = pygame.image.load(_icon_file).convert_alpha()
                icon_surf = pygame.transform.smoothscale(icon_surf, (32, 32))
                _loaded_icon_surf = icon_surf
                # SDL2 renderer (_sdl2.Window) backend aktifse pygame.display.set_icon
                # çalışmaz; ikonu doğrudan Window.set_icon() ile uygula.
                _sdl2_icon_done = False
                try:
                    import sdl2_overlay as _ovl
                    if _ovl.is_active():
                        _sdl2_icon_done = _ovl.apply_window_icon(icon_surf)
                except Exception:
                    _sdl2_icon_done = False
                if not _sdl2_icon_done:
                    pygame.display.set_icon(icon_surf)
                break
            except Exception:
                continue

    # ── Windows: AppUserModelID + ctypes ile görev çubuğu simgesi ──
    if sys.platform == 'win32':
        try:
            import ctypes
            # AppUserModelID ayarla — Windows'un "python.exe" yazmasını engeller
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('Quadrix.Game')
            # .ico dosyasını varsa ctypes ile uygula (daha yüksek kaliteli simge)
            ico_path = os.path.join(assets_dir, 'quadrix_icon.ico')
            if os.path.exists(ico_path):
                abs_ico = os.path.abspath(ico_path)
                # _sdl2.Window modunda get_wm_info boş döner; SDL2 backend aktifse
                # HWND'yi doğrudan Windows API ile aktif pencereden al.
                hwnd = 0
                try:
                    info = pygame.display.get_wm_info() if hasattr(pygame.display, 'get_wm_info') else {}
                    hwnd = info.get('window', 0) if isinstance(info, dict) else 0
                except Exception:
                    hwnd = 0
                if not hwnd:
                    try:
                        hwnd = ctypes.windll.user32.GetActiveWindow() or ctypes.windll.user32.GetForegroundWindow()
                    except Exception:
                        hwnd = 0
                if hwnd:
                    WM_SETICON = 0x0080
                    ICON_SMALL = 0
                    ICON_BIG = 1
                    LR_LOADFROMFILE = 0x00000010
                    LR_DEFAULTSIZE = 0x00000040
                    hicon = ctypes.windll.user32.LoadImageW(
                        0, abs_ico, 1,
                        0, 0,
                        LR_LOADFROMFILE | LR_DEFAULTSIZE
                    )
                    if hicon:
                        ctypes.windll.user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, hicon)
                        ctypes.windll.user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, hicon)
        except Exception:
            pass

    # ── macOS Dock simgesi (AppKit / PyObjC) ──
    if IS_MACOS:
        icns_path = os.path.join(assets_dir, 'quadrix_icon.icns')
        if not os.path.exists(icns_path):
            # Fallback: PNG kullan (kandidatlardan bulunanı al)
            _fallback_png = os.path.join(assets_dir, 'quadrix_icon.png')
            icns_path = _fallback_png if os.path.exists(_fallback_png) else icns_path
        try:
            from AppKit import NSApplication, NSImage
            abs_path = os.path.abspath(icns_path)
            image = NSImage.alloc().initWithContentsOfFile_(abs_path)
            if image:
                NSApplication.sharedApplication().setApplicationIconImage_(image)
        except Exception:
            pass


def init_platform_display():
    """Initialize platform-specific display settings before creating the window.
    
    This should be called after pygame.init() but before pygame.display.set_mode().
    """
    if IS_MACOS:
        try:
            # Ensure the macOS window appears in front
            import os
            os.environ.setdefault('SDL_VIDEO_WINDOW_POS', 'center')
        except Exception:
            pass


def get_display_scale_factor() -> float:
    """Return the ratio of physical pixels to logical points.

    On macOS Retina displays this is typically 2.0.
    On all other platforms (or when HiDPI is disabled) it returns 1.0.
    Safe to call at any time after ``pygame.display.set_mode()``.
    """
    try:
        surface = pygame.display.get_surface()
        if surface is not None and hasattr(pygame.display, 'get_window_size'):
            surf_w, _ = surface.get_size()           # physical pixels
            win_w, _ = pygame.display.get_window_size()  # logical points
            if win_w > 0:
                factor = surf_w / float(win_w)
                if factor >= 0.5:  # sanity check
                    return factor
    except Exception:
        pass
    return 1.0


def _coerce_positive_size(width: int | float, height: int | float) -> tuple[int, int]:
    return max(1, int(width)), max(1, int(height))


def _get_surface_size(screen: pygame.Surface | None) -> tuple[int, int] | None:
    if screen is None or not hasattr(screen, 'get_size'):
        return None
    try:
        width, height = screen.get_size()
        return _coerce_positive_size(width, height)
    except Exception:
        return None


def _resolve_display_surface_context(
    screen: pygame.Surface | None,
    display_surface: bool | None,
) -> tuple[pygame.Surface | None, pygame.Surface | None, bool]:
    try:
        active_display_surface = pygame.display.get_surface()
    except Exception:
        active_display_surface = None

    target_surface = screen if screen is not None else active_display_surface
    if display_surface is None:
        is_display_surface = screen is None
        if screen is not None:
            is_display_surface = (
                active_display_surface is not None and screen is active_display_surface
            )
    else:
        is_display_surface = bool(display_surface)

    return target_surface, active_display_surface, is_display_surface


def get_window_logical_size(
    screen: pygame.Surface | None = None,
    *,
    display_surface: bool | None = None,
) -> tuple[int, int]:
    """Return the window size in logical UI units.

    For the active display surface this prefers SDL/pygame window size when
    available, which reflects logical points on HiDPI platforms. For offscreen
    surfaces it returns the surface size unchanged.
    """
    target_surface, _active_display_surface, is_display_surface = _resolve_display_surface_context(
        screen,
        display_surface,
    )
    target_size = _get_surface_size(target_surface)
    if target_size is None:
        return _coerce_positive_size(*get_native_resolution())

    if is_display_surface and hasattr(pygame.display, 'get_window_size'):
        try:
            win_w, win_h = pygame.display.get_window_size()
            if win_w > 0 and win_h > 0:
                return _coerce_positive_size(win_w, win_h)
        except Exception:
            pass

    return target_size


def _get_windows_active_hwnd() -> int | None:
    if not IS_WINDOWS:
        return None
    try:
        info = pygame.display.get_wm_info() if hasattr(pygame.display, 'get_wm_info') else {}
    except Exception:
        info = {}

    if isinstance(info, dict):
        hwnd = info.get('window') or info.get('hwnd')
        try:
            hwnd = int(hwnd or 0)
        except Exception:
            hwnd = 0
        if hwnd > 0:
            return hwnd
    return None


def _get_windows_system_scale_factor() -> float:
    """Return the best-effort Windows desktop UI scale factor.

    The value is 1.0 on non-Windows platforms or when the DPI query fails.
    """
    if not IS_WINDOWS:
        return 1.0

    try:
        import ctypes

        user32 = getattr(getattr(ctypes, 'windll', None), 'user32', None)
        if user32 is None:
            return 1.0

        get_dpi_for_system = getattr(user32, 'GetDpiForSystem', None)
        if callable(get_dpi_for_system):
            dpi = int(get_dpi_for_system() or 0)
            if dpi > 0:
                factor = dpi / 96.0
                if 0.5 <= factor <= 8.0:
                    return factor

        gdi32 = getattr(getattr(ctypes, 'windll', None), 'gdi32', None)
        get_dc = getattr(user32, 'GetDC', None)
        release_dc = getattr(user32, 'ReleaseDC', None)
        get_device_caps = getattr(gdi32, 'GetDeviceCaps', None)
        if callable(get_dc) and callable(release_dc) and callable(get_device_caps):
            dc = get_dc(0)
            try:
                dpi = int(get_device_caps(dc, 88) or 0)
            finally:
                try:
                    release_dc(0, dc)
                except Exception:
                    pass
            if dpi > 0:
                factor = dpi / 96.0
                if 0.5 <= factor <= 8.0:
                    return factor
    except Exception:
        pass

    return 1.0


def _get_windows_window_scale_factor(hwnd: int | None = None) -> float:
    """Return the best-effort DPI scale factor for the active Windows window."""
    if not IS_WINDOWS:
        return 1.0

    if hwnd is None:
        hwnd = _get_windows_active_hwnd()

    try:
        import ctypes

        user32 = getattr(getattr(ctypes, 'windll', None), 'user32', None)
        shcore = getattr(getattr(ctypes, 'windll', None), 'shcore', None)
        if user32 is not None and hwnd:
            get_dpi_for_window = getattr(user32, 'GetDpiForWindow', None)
            if callable(get_dpi_for_window):
                dpi = int(get_dpi_for_window(hwnd) or 0)
                if dpi > 0:
                    factor = dpi / 96.0
                    if 0.5 <= factor <= 8.0:
                        return factor

            monitor_from_window = getattr(user32, 'MonitorFromWindow', None)
            get_dpi_for_monitor = getattr(shcore, 'GetDpiForMonitor', None)
            if callable(monitor_from_window) and callable(get_dpi_for_monitor):
                monitor = monitor_from_window(hwnd, 2)
                if monitor:
                    dpi_x = ctypes.c_uint()
                    dpi_y = ctypes.c_uint()
                    hr = int(get_dpi_for_monitor(monitor, 0, ctypes.byref(dpi_x), ctypes.byref(dpi_y)) or 0)
                    if hr == 0 and dpi_x.value > 0:
                        factor = dpi_x.value / 96.0
                        if 0.5 <= factor <= 8.0:
                            return factor
    except Exception:
        pass

    return _get_windows_system_scale_factor()


def get_effective_ui_size(
    screen: pygame.Surface | None = None,
    *,
    display_surface: bool | None = None,
) -> tuple[int, int]:
    """Return the size that UI scale calculations should use.

    Render surfaces still use physical surface sizes. This helper only provides
    a more human-facing size baseline for font/panel/layout scaling.
    """
    target_surface, active_display_surface, is_display_surface = _resolve_display_surface_context(
        screen,
        display_surface,
    )
    width, height = get_window_logical_size(
        screen,
        display_surface=display_surface,
    )

    if not is_display_surface:
        return _coerce_positive_size(width, height)

    if IS_WINDOWS:
        active_surf = active_display_surface or target_surface
        is_fs = False
        if active_surf is not None:
            try:
                is_fs = bool(active_surf.get_flags() & (pygame.FULLSCREEN | pygame.NOFRAME))
            except Exception:
                pass
        
        # Tam ekran veya borderless moddayken DPI ölçeğine bölerek çözünürlüğü küçültme
        if not is_fs:
            surface_size = _get_surface_size(active_surf)
            if surface_size is not None:
                surf_w, surf_h = surface_size
                # SDL/Pygame bazı build'lerde get_window_size ile logical boyutu zaten
                # döndürebilir. Bu durumda ikinci kez DPI normalizasyonu yapma.
                if abs(int(surf_w) - int(width)) <= 1 and abs(int(surf_h) - int(height)) <= 1:
                    scale_factor = _get_windows_window_scale_factor()
                    if scale_factor > 1.01:
                        width = int(round(float(width) / float(scale_factor)))
                        height = int(round(float(height) / float(scale_factor)))

    return _coerce_positive_size(width, height)


def _macos_logical_resolution() -> tuple[int, int] | None:
    """macOS'ta NSScreen API ile logical (points) ekran çözünürlüğünü döndür.

    HiDPI aktif olsa bile daima logical boyut döner (ör: 1440×900).
    PyObjC yoksa veya hata olursa None döner.
    """
    if not IS_MACOS:
        return None
    try:
        from AppKit import NSScreen  # type: ignore[import-untyped]
        frame = NSScreen.mainScreen().frame()
        w, h = int(frame.size.width), int(frame.size.height)
        if w > 0 and h > 0:
            return (w, h)
    except Exception:
        pass
    return None


def get_native_resolution():
    """Get the native screen resolution in *logical points*.

    On macOS Retina, always returns the logical (point) resolution
    regardless of HiDPI state (e.g. 1440×900, not 2880×1800).
    On Windows/Linux, returns the desktop pixel resolution.

    Returns:
        Tuple[int, int]: (width, height) of the primary monitor.
    """
    # macOS: prefer NSScreen to avoid SDL physical-vs-logical ambiguity
    if IS_MACOS:
        ns_res = _macos_logical_resolution()
        if ns_res is not None:
            return ns_res

    try:
        info = pygame.display.Info()
        width = info.current_w
        height = info.current_h

        if IS_MACOS and width > 0 and height > 0:
            # Fallback heuristic: SDL HiDPI aktifken fiziksel piksel dönebilir.
            # Tipik Retina scale 2x, bazı ekranlarda ~1.5x–2x arası.
            # 3000'den büyük genişlik neredeyse kesin fiziksel pikseldir.
            if width > 3000:
                width //= 2
                height //= 2

        if width > 0 and height > 0:
            return (width, height)
    except Exception:
        pass
    # Fallback to a common resolution
    return (1920, 1080)


def is_fullscreen_toggle(key: int, mods: int, custom_key: int | None = None) -> bool:
    """Fullscreen/windowed toggle desteği kaldırıldı."""
    return False


def normalize_mouse_pos(pos: tuple[int, int] | list[int] | None, scale: float = 1.0) -> tuple[int, int] | None:
    """Normalize mouse coordinates to match the display surface pixel space and apply UI scale.

    Virtual Canvas farkındalığı:
    - Software virtual canvas aktifken fare koordinatları letterbox offset'ten arındırılır
      ve canvas ölçeğine bölünür.
    - macOS Retina/HiDPI: window_size (points) ile surface_size (pixels) farkı giderilir.
    """
    if pos is None:
        return None
    try:
        x, y = int(pos[0]), int(pos[1])
    except Exception:
        return None

    try:
        # --- Virtual Canvas: letterbox offset + canvas scale ---
        if _software_scale_active and _virtual_blit_rect is not None:
            bx, by, bw, bh = _virtual_blit_rect
            canvas_w, canvas_h = _software_canvas.get_size() if _software_canvas is not None else (bw, bh)
            # Letterbox dışındaki tıklamalar → None (sınır dışı)
            if bw > 0 and bh > 0:
                rx = x - bx
                ry = y - by
                canvas_x = int(rx * canvas_w / bw)
                canvas_y = int(ry * canvas_h / bh)
                # Clamp: canvas sınırlarına sabitle
                canvas_x = max(0, min(canvas_w - 1, canvas_x))
                canvas_y = max(0, min(canvas_h - 1, canvas_y))
                return (canvas_x, canvas_y)
            return (x, y)

        # --- HiDPI / Retina normalizasyonu ---
        surface = pygame.display.get_surface()
        if surface is None:
            final_x, final_y = x, y
        else:
            surf_w, surf_h = surface.get_size()
            if hasattr(pygame.display, 'get_window_size'):
                win_w, win_h = pygame.display.get_window_size()
            else:
                win_w, win_h = (surf_w, surf_h)

            if not win_w or not win_h:
                final_x, final_y = x, y
            elif (surf_w, surf_h) == (win_w, win_h):
                final_x, final_y = x, y
            else:
                scale_x = surf_w / float(win_w)
                scale_y = surf_h / float(win_h)
                final_x, final_y = int(x * scale_x), int(y * scale_y)

        if scale != 1.0:
            final_x = int(final_x / scale)
            final_y = int(final_y / scale)
        return (final_x, final_y)
    except Exception:
        if scale != 1.0:
            x = int(x / scale)
            y = int(y / scale)
        return (x, y)


def get_mouse_pos(scale: float = 1.0) -> tuple[int, int]:
    """Return current mouse position normalized to the display surface and UI scale."""
    try:
        pos = pygame.mouse.get_pos()
    except Exception:
        return (0, 0)
    return normalize_mouse_pos(pos, scale) or (0, 0)


def _get_windows_physical_resolution() -> tuple[int, int]:
    """Windows'ta DPI ölçeğinden bağımsız fiziksel piksel çözünürlüğünü döndür.

    GetSystemMetrics(SM_CXSCREEN/SM_CYSCREEN) Per-Monitor DPI awareness aktifken
    primary monitörün fiziksel piksel boyutunu döndürür.
    Başarısız olursa get_native_resolution() ile devam et.
    """
    try:
        import ctypes
        physical_w = ctypes.windll.user32.GetSystemMetrics(0)  # SM_CXSCREEN
        physical_h = ctypes.windll.user32.GetSystemMetrics(1)  # SM_CYSCREEN
        if physical_w > 0 and physical_h > 0:
            return (physical_w, physical_h)
    except Exception:
        pass
    return get_native_resolution()


def set_gl_window_request(enabled: bool) -> None:
    """Tek-context OpenGL pencere talebini aç/kapat.

    gl_compat, ilk ``create_display()`` çağrısından önce bunu ``True`` yaparak
    pencerenin baştan ``pygame.OPENGL`` bayrağıyla açılmasını ister. Böylece
    ikinci bir ``set_mode`` çağrısı (çift-context) elenir ve Steam overlay
    hook'u doğru swapchain'e bağlanır. Yalnızca Windows borderless tam ekran
    yolunda etkilidir; diğer platform/yollarda yok sayılır.
    """
    global _GL_WINDOW_REQUEST
    _GL_WINDOW_REQUEST = bool(enabled)


def is_gl_window_requested() -> bool:
    """Tek-context OpenGL pencere talebinin aktif olup olmadığını döndür."""
    return _GL_WINDOW_REQUEST


def _gl_diag(message: str) -> None:
    """create_display kararlarını gl_compat teşhis günlüğüne yönlendir (hata yutar)."""
    try:
        import gl_compat as _glc
        _glc._diag_log(f"[platform_utils] {message}")
    except Exception:
        try:
            print(f"[GL Compat] [platform_utils] {message}")
        except Exception:
            pass


def overlay_should_skip_rebuild(width: int, height: int) -> bool:
    """Aktif overlay backend'i (gl_compat veya sdl2_overlay) display rebuild'i atlamalı mı?

    VIDEORESIZE/rebuild işleyicileri bunu çağırarak, overlay katmanı aktif ve boyut sabitse
    yeni bir create_display/set_mode (ve pencere/swapchain yeniden yaratımı) yapmaktan kaçınır.
    Hangi backend aktifse onun should_skip_display_rebuild'ini sorar. Hata-toleranslıdır.
    """
    for _mod_name in ('sdl2_overlay', 'gl_compat'):
        try:
            _mod = sys.modules.get(_mod_name)
            if _mod is None:
                continue
            checker = getattr(_mod, 'should_skip_display_rebuild', None)
            if callable(checker) and checker(width, height):
                return True
        except Exception:
            pass
    return False


def overlay_active_game_surface():
    """Aktif overlay backend'inin offscreen oyun yüzeyini döndür (yoksa None)."""
    for _mod_name in ('sdl2_overlay', 'gl_compat'):
        try:
            _mod = sys.modules.get(_mod_name)
            if _mod is None:
                continue
            getter = getattr(_mod, 'get_game_surface', None)
            is_active = getattr(_mod, 'is_active', None) or getattr(_mod, 'is_gl_active', None)
            if callable(getter) and callable(is_active) and is_active():
                surf = getter()
                if surf is not None:
                    return surf
        except Exception:
            pass
    return None


def create_display(
    width: int,
    height: int,
    fullscreen: bool = False,
    resizable: bool = True,
    borderless: bool = False,
):
    """Create a pygame display locked to always-fullscreen mode."""
    # ── TEK PENCERE GARANTİSİ: Overlay backend aktifse set_mode'a HİÇ DOKUNMA ──
    # SDL2 overlay (veya gl_compat) aktifse asıl görünür pencere ayrı bir
    # _sdl2.Window'dur; ilk set_mode penceresi 1x1 + HIDDEN'a küçültülmüştür.
    # Burada yeniden set_mode çağırmak o gizli pencereyi TAM BOYUTLU + GÖRÜNÜR
    # olarak diriltir → görev çubuğunda/Alt+Tab'da İKİNCİ PENCERE belirir.
    # (Kaynak: splash focus-recovery, VIDEORESIZE, focus regain rebuild'leri.)
    # Çözüm: overlay aktifken create_display, set_mode'u tamamen atlayıp overlay'in
    # offscreen oyun yüzeyini döndürür. Oyun yine bu yüzeye çizer, patched flip
    # onu görünür _sdl2.Window'a sunar. Böylece YALNIZCA TEK pencere kalır.
    try:
        _overlay_surf = overlay_active_game_surface()
        if _overlay_surf is not None:
            _gl_diag(
                "create_display: overlay AKTİF → set_mode ATLANDI, offscreen yüzey "
                f"döndürüldü ({_overlay_surf.get_width()}x{_overlay_surf.get_height()}) "
                "[TEK PENCERE korundu]"
            )
            invalidate_refresh_rate_cache()
            return _overlay_surf
    except Exception:
        pass

    fullscreen = True
    borderless = True
    resizable = False
    
    # macOS için özel handling
    if IS_MACOS:
        try:
            if fullscreen:
                # macOS: Çerçevesiz tam ekran (borderless fullscreen)
                # FULLSCREEN flag'i yerine NOFRAME kullanılır.
                # Böylece SDL Cocoa crash'i (NSWindow setStyleMask) önlenir.
                # Menu bar ve dock pyobjc ile gizlenir.
                try:
                    from AppKit import NSApplication
                    app = NSApplication.sharedApplication()
                    # HideMenuBar(8) | HideDock(2) = 10
                    app.setPresentationOptions_(8 | 2)
                except Exception:
                    pass
                native_w, native_h = get_native_resolution()
                os.environ['SDL_VIDEO_WINDOW_POS'] = '0,0'
                flags = pygame.NOFRAME | pygame.DOUBLEBUF
                surface = pygame.display.set_mode((native_w, native_h), flags)
                invalidate_refresh_rate_cache()
                return surface
            else:
                # Pencere modu - çerçeveli, yeniden boyutlandırılabilir
                # Menu bar ve dock'u geri getir
                try:
                    from AppKit import NSApplication
                    app = NSApplication.sharedApplication()
                    app.setPresentationOptions_(0)  # Normal moda dön
                except Exception:
                    pass
                os.environ['SDL_VIDEO_WINDOW_POS'] = 'center'
                flags = pygame.RESIZABLE
                surface = pygame.display.set_mode((width, height), flags)
                invalidate_refresh_rate_cache()
                return surface
        except pygame.error as e:
            print(f"[UYARI] macOS display hatası: {e}")
            try:
                surface = pygame.display.set_mode((width or 800, height or 600), pygame.RESIZABLE)
                invalidate_refresh_rate_cache()
                return surface
            except pygame.error:
                invalidate_refresh_rate_cache()
                return pygame.Surface((width or 800, height or 600))
    
    # Windows/Linux için standart handling
    if fullscreen and borderless:
        # Windows: ctypes ile DPI-bağımsız fiziksel çözünürlük al
        native_w, native_h = (
            _get_windows_physical_resolution() if IS_WINDOWS else get_native_resolution()
        )
        # SDL_VIDEO_CENTERED=1 NOFRAME penceresinin (0,0)'dan başlamasını engeller.
        # Fullscreen geçişinde centered hint'i geçici olarak devre dışı bırak.
        old_centered = os.environ.pop('SDL_VIDEO_CENTERED', None)
        old_win_pos = os.environ.get('SDL_VIDEO_WINDOW_POS')
        os.environ['SDL_VIDEO_WINDOW_POS'] = '0,0'
        # SDL2/Pygame2'de HWSURFACE gereksiz (SDL2 ignore eder); bu path'ten kaldırıldı.
        flags_bl = pygame.NOFRAME | pygame.DOUBLEBUF
        # Tek-context: gl_compat OpenGL pencere istediyse, pencereyi baştan
        # OPENGL bayrağıyla aç. Böylece ikinci bir set_mode(OPENGL) gerekmez
        # ve Steam overlay hook'u ilk (ve tek) swapchain'e bağlanır.
        # HWSURFACE zaten bu yolda yok; OPENGL ile uyumsuz olduğu için eklenmez.
        gl_requested = bool(_GL_WINDOW_REQUEST and IS_WINDOWS)
        if gl_requested:
            flags_bl |= pygame.OPENGL
        _pending_gl_diag = (
            f"create_display(borderless): _GL_WINDOW_REQUEST={_GL_WINDOW_REQUEST} "
            f"IS_WINDOWS={IS_WINDOWS} → set_mode flags=0x{flags_bl:X} "
            f"(OPENGL={'VAR' if gl_requested else 'YOK'})"
        )
        try:
            try:
                surface = pygame.display.set_mode((native_w, native_h), flags_bl)
            except pygame.error:
                # OpenGL context açılamadıysa (donanım/sürücü) software pencereye
                # güvenli geri dönüş yap. gl_compat sonradan iki-adımlı yolu dener.
                if gl_requested:
                    _pending_gl_diag += ' | OPENGL set_mode BAŞARISIZ → software fallback'
                    flags_bl &= ~pygame.OPENGL
                    surface = pygame.display.set_mode((native_w, native_h), flags_bl)
                else:
                    raise
            # Boyut doğrulama: beklenen boyuta ulaşılamadıysa exclusive fullscreen fallback
            actual_w, actual_h = surface.get_size()
            if abs(actual_w - native_w) > 4 or abs(actual_h - native_h) > 4:
                # Borderless başarısız; exclusive fullscreen'e düş
                excl_flags = pygame.FULLSCREEN | pygame.DOUBLEBUF
                if gl_requested and bool(surface.get_flags() & pygame.OPENGL):
                    # GL context kurulduysa exclusive geçişte de koru.
                    excl_flags |= pygame.OPENGL
                surface = pygame.display.set_mode((0, 0), excl_flags)
                _pending_gl_diag += f' | boyut uyumsuz → exclusive set_mode flags=0x{excl_flags:X}'
            invalidate_refresh_rate_cache()
            try:
                _gl_diag(_pending_gl_diag + f' | SONUÇ flags=0x{surface.get_flags():X}')
            except Exception:
                pass
            return surface
        except pygame.error:
            pass
        finally:
            # Her durumda env'i önceki değerine geri yükle
            if old_centered is not None:
                os.environ['SDL_VIDEO_CENTERED'] = old_centered
            if old_win_pos is not None:
                os.environ['SDL_VIDEO_WINDOW_POS'] = old_win_pos
            elif 'SDL_VIDEO_WINDOW_POS' in os.environ:
                del os.environ['SDL_VIDEO_WINDOW_POS']

    flags = get_display_flags(resizable=(not fullscreen and resizable), fullscreen=fullscreen)

    # Exclusive fullscreen modunda da SDL_VIDEO_CENTERED'ı geçici devre dışı bırak
    old_centered_excl = None
    if fullscreen:
        old_centered_excl = os.environ.pop('SDL_VIDEO_CENTERED', None)
    try:
        if fullscreen:
            surface = pygame.display.set_mode((0, 0), flags)
        else:
            surface = pygame.display.set_mode((width, height), flags)
        invalidate_refresh_rate_cache()
        return surface
    except pygame.error:
        try:
            fallback_flags = pygame.DOUBLEBUF | pygame.RESIZABLE
            surface = pygame.display.set_mode((width or 800, height or 600), fallback_flags)
            invalidate_refresh_rate_cache()
            return surface
        except pygame.error:
            invalidate_refresh_rate_cache()
            return pygame.Surface((width or 800, height or 600))
    finally:
        if fullscreen and old_centered_excl is not None:
            os.environ['SDL_VIDEO_CENTERED'] = old_centered_excl


def _first_nonempty_line(text: str | None) -> str | None:
    if not text:
        return None
    for line in (text or '').splitlines():
        line = (line or '').strip()
        if line:
            return line
    return None


def _run_quick_command(args: list[str], timeout_s: float = 1.2) -> str | None:
    try:
        completed = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
        return _first_nonempty_line(completed.stdout)
    except Exception:
        return None


def get_device_model() -> str:
    """Best-effort cihaz modeli/ürün adı döndür.

    Not: Her platform/kurulumda kesin model bilgisi alınamayabilir.
    """
    try:
        system = platform.system()

        if system == 'Windows':
            # CIM (modern) - hızlı ve çoğu sistemde mevcut
            model = _run_quick_command(
                [
                    'powershell',
                    '-NoProfile',
                    '-NonInteractive',
                    '-ExecutionPolicy',
                    'Bypass',
                    '-Command',
                    '(Get-CimInstance -ClassName Win32_ComputerSystem -ErrorAction Stop).Model',
                ],
                timeout_s=1.5,
            )
            if model:
                return model

            # WMIC (eski) - bazı sistemlerde hâlâ var
            wmic_out = _run_quick_command(['wmic', 'csproduct', 'get', 'name'], timeout_s=1.2)
            if wmic_out and wmic_out.lower() != 'name':
                return wmic_out

        if system == 'Darwin':
            model = _run_quick_command(['sysctl', '-n', 'hw.model'], timeout_s=1.2)
            if model:
                return model

        if system == 'Linux':
            product_name_path = '/sys/devices/virtual/dmi/id/product_name'
            sys_vendor_path = '/sys/devices/virtual/dmi/id/sys_vendor'
            vendor = None
            product = None
            try:
                if os.path.exists(sys_vendor_path):
                    with open(sys_vendor_path, 'r', encoding='utf-8', errors='ignore') as f:
                        vendor = (f.read() or '').strip() or None
                if os.path.exists(product_name_path):
                    with open(product_name_path, 'r', encoding='utf-8', errors='ignore') as f:
                        product = (f.read() or '').strip() or None
            except Exception:
                vendor = None
                product = None
            if vendor or product:
                return ' '.join([p for p in [vendor, product] if p])

        # Fallback: makine mimarisi + node adı
        uname = platform.uname()
        node = (uname.node or '').strip()
        machine = (uname.machine or '').strip()
        pretty = ' '.join([p for p in [node, machine] if p]).strip()
        return pretty or 'Bilinmiyor'
    except Exception:
        return 'Bilinmiyor'


def get_os_software_info_text() -> str:
    """Destek maili için OS + yazılım bilgilerini çok satırlı metin olarak döndür."""
    try:
        uname = platform.uname()
        os_line = ' '.join(
            [
                (uname.system or '').strip(),
                (uname.release or '').strip(),
            ]
        ).strip()
        version_detail = (uname.version or '').strip()
        if version_detail:
            os_line = f"{os_line} ({version_detail})".strip()

        lines: list[str] = []
        if os_line:
            lines.append(f"OS: {os_line}")
        if uname.machine:
            lines.append(f"Architecture: {uname.machine}")
        return '\n'.join(lines) if lines else 'Unknown'
    except Exception:
        return 'Unknown'


def build_support_email_body_template() -> str:
    """SOS menüsünde kullanılacak hazır destek maili gövdesini üret."""
    device_model = get_device_model()
    os_sw = get_os_software_info_text()
    return (
        'Hello,\n\n'
        '(Description / feedback / bug report)\n\n'
        f'Device model: {device_model}\n'
        f'{os_sw}\n'
    )


# ---------------------------------------------------------------------------
# Sanal Ekran (Virtual Canvas) Ölçeklemesi
# ---------------------------------------------------------------------------
# Oyun sabit bir sanal çözünürlüğe (virtual_canvas) çizilir; bu canvas gerçek
# pencere boyutuna letterbox/pillarbox korunarak ölçeklenir.
# Bu sayede tüm UI elemanları otomatik ve tutarlı biçimde büyür/küçülür.
# ---------------------------------------------------------------------------
_software_canvas: pygame.Surface | None = None
_real_display_surface: pygame.Surface | None = None
_software_scale_active: bool = False
_virtual_blit_rect: tuple[int, int, int, int] | None = None  # (x, y, w, h) letterbox dest

try:
    _orig_flip = pygame.display.flip
    _orig_update = pygame.display.update
    _orig_get_surface = pygame.display.get_surface
except Exception:
    _orig_flip = lambda: None
    _orig_update = lambda *args, **kwargs: None
    _orig_get_surface = lambda: None


def _calc_letterbox(canvas_w: int, canvas_h: int, real_w: int, real_h: int) -> tuple[int, int, int, int]:
    """Aspect ratio korunarak canvas'ın gerçek yüzeye sığdırıldığı (x, y, w, h) dikdörtgenini döndür."""
    if real_w <= 0 or real_h <= 0 or canvas_w <= 0 or canvas_h <= 0:
        return (0, 0, real_w, real_h)
    scale_x = real_w / float(canvas_w)
    scale_y = real_h / float(canvas_h)
    scale = min(scale_x, scale_y)
    dst_w = int(canvas_w * scale)
    dst_h = int(canvas_h * scale)
    off_x = (real_w - dst_w) // 2
    off_y = (real_h - dst_h) // 2
    return (off_x, off_y, dst_w, dst_h)


def _blit_canvas_to_display() -> None:
    """Virtual canvas'ı letterbox ile gerçek display'e blit et ve _orig_flip çağır."""
    global _virtual_blit_rect
    if _software_canvas is None or _real_display_surface is None:
        _orig_flip()
        return
    real_w, real_h = _real_display_surface.get_size()
    canvas_w, canvas_h = _software_canvas.get_size()
    bx, by, bw, bh = _calc_letterbox(canvas_w, canvas_h, real_w, real_h)
    _virtual_blit_rect = (bx, by, bw, bh)
    # Siyah bantları doldur (letterbox/pillarbox)
    _real_display_surface.fill((0, 0, 0))
    # Canvas'ı ölçekleyip hedef alana blit et
    try:
        scaled = pygame.transform.scale(_software_canvas, (bw, bh))
        _real_display_surface.blit(scaled, (bx, by))
    except Exception:
        pass
    _orig_flip()


def _software_flip() -> None:
    _blit_canvas_to_display()


def _software_update(*args, **kwargs) -> None:
    _blit_canvas_to_display()


def _software_get_surface() -> pygame.Surface:
    if _software_canvas is not None:
        return _software_canvas
    return _orig_get_surface()


def _calc_virtual_canvas_size(
    real_w: int,
    real_h: int,
    multiplier: float,
) -> tuple[int, int]:
    """UI ölçek çarpanına göre sanal canvas boyutunu hesapla.

    Formül: virtual = actual / multiplier
    Yükseklik 720–1080 arası clamp edilir; genişlik aspect ratio ile hesaplanır.
    """
    if multiplier <= 0:
        multiplier = 1.0
    aspect = real_w / float(real_h) if real_h > 0 else (16.0 / 9.0)
    v_h = int(round(real_h / multiplier))
    # Yükseklik sınırları: minimum 720, maksimum 1080
    v_h = max(720, min(1080, v_h))
    v_w = int(round(v_h * aspect))
    # Genişlik de mantıklı sınır içinde kalsın
    v_w = max(1, v_w)
    return (v_w, v_h)


def setup_virtual_canvas(
    real_surface: pygame.Surface,
    multiplier: float = 1.0,
) -> pygame.Surface:
    """Sanal ekran (virtual canvas) pipeline'ını kur ve oyunun çizeceği küçük surface'i döndür.

    Tüm arka uçlarda (software, gl_compat, sdl2_overlay) çalışır.
    - multiplier = 1.0 → normal preset: canvas = gerçek boyut (pass-through, no-op).
    - multiplier > 1.0 → büyük preset: canvas küçülür → tüm UI otomatik büyür.
    - 4K ekranlarda normal preset bile 1920×1080 canvas'a küçültülür (mevcut davranış korunur).

    Returns:
        Oyunun çizmesi gereken pygame.Surface.
    """
    global _software_canvas, _real_display_surface, _software_scale_active, _virtual_blit_rect

    if real_surface is None or not hasattr(real_surface, 'get_size'):
        return real_surface

    real_w, real_h = real_surface.get_size()

    # Canvas boyutunu hesapla
    canvas_w, canvas_h = _calc_virtual_canvas_size(real_w, real_h, multiplier)

    # Gerçek pencere ile canvas aynıysa pass-through (monkey-patch gerekmez)
    if canvas_w == real_w and canvas_h == real_h:
        # Eğer önceki canvas aktifse temizle
        if _software_scale_active:
            _teardown_virtual_canvas()
        return real_surface

    # Canvas surface oluştur
    try:
        canvas = pygame.Surface((canvas_w, canvas_h))
        canvas = canvas.convert()
    except Exception as exc:
        print(f"[Virtual Canvas] Canvas oluşturulamadı: {exc}")
        return real_surface

    _real_display_surface = real_surface
    _software_canvas = canvas
    _software_scale_active = True
    _virtual_blit_rect = _calc_letterbox(canvas_w, canvas_h, real_w, real_h)

    # Monkey-patch display fonksiyonları
    pygame.display.flip = _software_flip
    pygame.display.update = _software_update
    pygame.display.get_surface = _software_get_surface

    # ui_scaling'e virtual canvas aktif olduğunu bildir
    # → tüm _ui_scale() / _sx() metodları 1.0 döndürerek çift ölçeklemeyi engeller
    try:
        from ui_scaling import set_virtual_canvas_active
        set_virtual_canvas_active(True)
    except Exception:
        pass

    print(
        f"[Virtual Canvas] Aktif: canvas={canvas_w}x{canvas_h} "
        f"→ real={real_w}x{real_h} (x{multiplier:.2f}) "
        f"letterbox=({_virtual_blit_rect[0]},{_virtual_blit_rect[1]},{_virtual_blit_rect[2]},{_virtual_blit_rect[3]})"
    )
    return _software_canvas


def rebuild_virtual_canvas(multiplier: float | None = None) -> pygame.Surface | None:
    """Mevcut virtual canvas'ı yeni multiplier ile yeniden kur.

    Settings ekranında UI preset değiştiğinde bu fonksiyon çağrılır.
    Eğer canvas hiç kurulmamışsa (overlay modları) None döner.

    Args:
        multiplier: Yeni ölçek çarpanı. None verilirse ui_scaling'den alınır.

    Returns:
        Yeni canvas surface veya None (overlay modunda).
    """
    if _real_display_surface is None:
        return None

    if multiplier is None:
        try:
            from ui_scaling import get_ui_scale_multiplier
            multiplier = get_ui_scale_multiplier()
        except Exception:
            multiplier = 1.0

    return setup_virtual_canvas(_real_display_surface, multiplier)


def _teardown_virtual_canvas() -> None:
    """Virtual canvas monkey-patch'lerini geri al."""
    global _software_canvas, _real_display_surface, _software_scale_active, _virtual_blit_rect
    try:
        pygame.display.flip = _orig_flip
        pygame.display.update = _orig_update
        pygame.display.get_surface = _orig_get_surface
    except Exception:
        pass
    _software_canvas = None
    _real_display_surface = None
    _software_scale_active = False
    _virtual_blit_rect = None
    # ui_scaling'i bilgilendir: canvas devre dışı, eski ölçeklemeye dön
    try:
        from ui_scaling import set_virtual_canvas_active
        set_virtual_canvas_active(False)
    except Exception:
        pass


def get_virtual_canvas_info() -> dict:
    """Mevcut virtual canvas bilgilerini döndür.

    Returns:
        dict with keys: active, canvas_w, canvas_h, real_w, real_h,
        offset_x, offset_y, blit_w, blit_h, scale_x, scale_y
    """
    if not _software_scale_active or _software_canvas is None or _virtual_blit_rect is None:
        if _real_display_surface is not None:
            rw, rh = _real_display_surface.get_size()
        else:
            try:
                surf = _orig_get_surface()
                rw, rh = (surf.get_size() if surf else (1920, 1080))
            except Exception:
                rw, rh = 1920, 1080
        return {
            'active': False,
            'canvas_w': rw, 'canvas_h': rh,
            'real_w': rw, 'real_h': rh,
            'offset_x': 0, 'offset_y': 0,
            'blit_w': rw, 'blit_h': rh,
            'scale_x': 1.0, 'scale_y': 1.0,
        }
    cw, ch = _software_canvas.get_size()
    rw, rh = _real_display_surface.get_size()
    bx, by, bw, bh = _virtual_blit_rect
    sx = bw / float(cw) if cw > 0 else 1.0
    sy = bh / float(ch) if ch > 0 else 1.0
    return {
        'active': True,
        'canvas_w': cw, 'canvas_h': ch,
        'real_w': rw, 'real_h': rh,
        'offset_x': bx, 'offset_y': by,
        'blit_w': bw, 'blit_h': bh,
        'scale_x': sx, 'scale_y': sy,
    }


def setup_software_resolution_scaling(real_surface: pygame.Surface) -> pygame.Surface:
    """Geriye dönük uyumluluk: setup_virtual_canvas'a delege eder.

    Bu fonksiyon artık kullanılmamalıdır; setup_virtual_canvas kullanın.
    """
    try:
        from ui_scaling import get_ui_scale_multiplier
        multiplier = get_ui_scale_multiplier()
    except Exception:
        multiplier = 1.0
    return setup_virtual_canvas(real_surface, multiplier)


# ---------------------------------------------------------------------------
# Pygame Event Queue Patching (Virtual Canvas Mouse Koordinat Mutasyonu)
# ---------------------------------------------------------------------------
# MOUSEMOTION, MOUSEBUTTONDOWN, MOUSEBUTTONUP event'lerinin `pos` (ve
# MOUSEMOTION için `rel`) değerleri virtual canvas koordinat sistemine
# otomatik dönüştürülür. Böylece event.pos'u doğrudan kullanan tüm
# kod yerleri de doğru canvas koordinatı alır — normalize_mouse_pos
# çağrısı gerekmez.
# ---------------------------------------------------------------------------
try:
    _orig_event_get = pygame.event.get
except Exception:
    _orig_event_get = lambda *args, **kwargs: []
_event_patch_active = False


def _normalize_event_pos(raw_pos: tuple) -> tuple[int, int]:
    """Ham fare pozisyonunu virtual canvas koordinatına dönüştür."""
    if not _software_scale_active or _virtual_blit_rect is None:
        return raw_pos
    bx, by, bw, bh = _virtual_blit_rect
    canvas_w, canvas_h = (
        _software_canvas.get_size() if _software_canvas is not None
        else (bw, bh)
    )
    if bw <= 0 or bh <= 0:
        return raw_pos
    rx = float(raw_pos[0]) - bx
    ry = float(raw_pos[1]) - by
    cx = int(round(rx * canvas_w / bw))
    cy = int(round(ry * canvas_h / bh))
    cx = max(0, min(canvas_w - 1, cx))
    cy = max(0, min(canvas_h - 1, cy))
    return (cx, cy)


def _normalize_event_rel(raw_rel: tuple) -> tuple[int, int]:
    """Ham fare hareketini (rel) virtual canvas ölçeğine dönüştür."""
    if not _software_scale_active or _virtual_blit_rect is None:
        return raw_rel
    bx, by, bw, bh = _virtual_blit_rect
    canvas_w, canvas_h = (
        _software_canvas.get_size() if _software_canvas is not None
        else (bw, bh)
    )
    if bw <= 0 or bh <= 0:
        return raw_rel
    sx = canvas_w / float(bw)
    sy = canvas_h / float(bh)
    return (int(round(float(raw_rel[0]) * sx)), int(round(float(raw_rel[1]) * sy)))


def _patched_event_get(eventtype=None, pump=True, exclude=None):
    """pygame.event.get wrapper: mouse event koordinatlarını mutate eder."""
    try:
        if eventtype is not None and exclude is not None:
            events = _orig_event_get(eventtype, pump=pump, exclude=exclude)
        elif eventtype is not None:
            events = _orig_event_get(eventtype, pump=pump)
        else:
            events = _orig_event_get()
    except Exception:
        try:
            events = _orig_event_get()
        except Exception:
            return []

    if not _software_scale_active or _virtual_blit_rect is None:
        return events

    patched = []
    for event in events:
        try:
            etype = event.type
            if etype in (
                pygame.MOUSEBUTTONDOWN,
                pygame.MOUSEBUTTONUP,
                pygame.MOUSEMOTION,
            ):
                new_pos = _normalize_event_pos(event.pos)
                attrs = {'pos': new_pos}
                if etype == pygame.MOUSEMOTION:
                    try:
                        new_rel = _normalize_event_rel(event.rel)
                        attrs['rel'] = new_rel
                    except Exception:
                        pass
                # pygame.event.Event ile yeni event oluştur (C-level salt okunur hatalarını önlemek için güvenli kopyalama)
                # dir(event) yerine event.__dict__ kullanımı hem performansı artırır hem de çökmeleri önler.
                event_dict = getattr(event, '__dict__', {})
                new_event = pygame.event.Event(etype, {
                    **{k: v for k, v in event_dict.items() if k not in attrs},
                    **attrs,
                })
                patched.append(new_event)
            else:
                patched.append(event)
        except Exception:
            patched.append(event)
    return patched


def patch_event_queue() -> None:
    """pygame.event.get, mouse.get_pos ve mouse.get_rel'i virtual canvas koordinat
    dönüşümü için monkey-patch et.

    Bu fonksiyon setup_virtual_canvas'tan sonra bir kez çağrılmalıdır.
    Virtual canvas aktif değilken tüm patch'ler pass-through çalışır.

    Monkey-patch'lenen fonksiyonlar:
    - pygame.event.get  → mouse event pos/rel mutasyonu
    - pygame.mouse.get_pos → letterbox offset + canvas scale dönüşümü
    - pygame.mouse.get_rel → canvas scale dönüşümü
    """
    global _event_patch_active
    if _event_patch_active:
        return

    try:
        pygame.event.get = _patched_event_get

        # pygame.mouse.get_pos → virtual canvas koordinatına normalize et
        _orig_mouse_get_pos = pygame.mouse.get_pos

        def _patched_mouse_get_pos():
            try:
                raw = _orig_mouse_get_pos()
                return _normalize_event_pos(raw)
            except Exception:
                return _orig_mouse_get_pos()

        pygame.mouse.get_pos = _patched_mouse_get_pos

        # pygame.mouse.get_rel → canvas ölçeğine normalize et
        _orig_mouse_get_rel = pygame.mouse.get_rel

        def _patched_mouse_get_rel():
            try:
                raw = _orig_mouse_get_rel()
                return _normalize_event_rel(raw)
            except Exception:
                return _orig_mouse_get_rel()

        pygame.mouse.get_rel = _patched_mouse_get_rel

        # Geri alma için referansları sakla
        patch_event_queue._orig_mouse_get_pos = _orig_mouse_get_pos
        patch_event_queue._orig_mouse_get_rel = _orig_mouse_get_rel

        _event_patch_active = True
        print(
            "[Virtual Canvas] Tam mouse patching aktif — "
            "event.get, mouse.get_pos ve mouse.get_rel normalize edilecek"
        )
    except Exception as exc:
        print(f"[Virtual Canvas] Event/mouse patch başarısız: {exc}")


def unpatch_event_queue() -> None:
    """Tüm pygame event/mouse monkey-patch'lerini geri al."""
    global _event_patch_active
    try:
        pygame.event.get = _orig_event_get
    except Exception:
        pass
    try:
        orig_pos = getattr(patch_event_queue, '_orig_mouse_get_pos', None)
        if orig_pos is not None:
            pygame.mouse.get_pos = orig_pos
    except Exception:
        pass
    try:
        orig_rel = getattr(patch_event_queue, '_orig_mouse_get_rel', None)
        if orig_rel is not None:
            pygame.mouse.get_rel = orig_rel
    except Exception:
        pass
    _event_patch_active = False
