"""Platform-specific utilities for cross-platform compatibility.

This module provides helper functions that abstract OS-specific behaviors.
"""

import os
import platform
import subprocess
import sys
import time
from typing import NamedTuple

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


_REFRESH_RATE_CACHE_HZ = 0
_REFRESH_RATE_CACHE_AT = 0.0
_REFRESH_RATE_CACHE_TTL_S = 1.0
_VRR_FEEDBACK_LOW_REFRESH_HZ = 45


def invalidate_refresh_rate_cache() -> None:
    """Invalidate the cached display refresh rate."""
    global _REFRESH_RATE_CACHE_HZ, _REFRESH_RATE_CACHE_AT
    _REFRESH_RATE_CACHE_HZ = 0
    _REFRESH_RATE_CACHE_AT = 0.0


def _query_desktop_refresh_rates() -> list[int]:
    """Return nominal desktop/mode refresh rates reported by pygame/SDL."""
    refresh_rates: list[int] = []
    try:
        if hasattr(pygame.display, 'get_desktop_refresh_rates'):
            for rate in (pygame.display.get_desktop_refresh_rates() or []):
                try:
                    parsed = int(rate or 0)
                except Exception:
                    parsed = 0
                if parsed > 0:
                    refresh_rates.append(parsed)
    except Exception:
        pass

    try:
        if hasattr(pygame.display, 'get_num_displays'):
            num = int(pygame.display.get_num_displays() or 0)
            if num > 0 and hasattr(pygame.display, 'get_current_display_mode'):
                for display_idx in range(num):
                    mode = pygame.display.get_current_display_mode(display_idx)
                    rate = int(getattr(mode, 'refresh_rate', 0) or 0)
                    if rate > 0:
                        refresh_rates.append(rate)
    except Exception:
        pass

    return refresh_rates


def _query_max_refresh_rate() -> int:
    """Query a stable refresh rate for automatic FPS caps.

    On VRR/G-Sync systems SDL may briefly report the current dynamic cadence
    (commonly 30 Hz) through get_current_refresh_rate(). Treat very low current
    values as feedback samples and prefer nominal desktop/mode rates instead.
    """
    desktop_rates = _query_desktop_refresh_rates()
    nominal_rate = max(desktop_rates) if desktop_rates else 0

    try:
        if hasattr(pygame.display, 'get_current_refresh_rate'):
            refresh_rate = int(pygame.display.get_current_refresh_rate() or 0)
            if refresh_rate > 0:
                if (
                    refresh_rate <= _VRR_FEEDBACK_LOW_REFRESH_HZ
                    and nominal_rate > refresh_rate
                ):
                    return nominal_rate
                if refresh_rate <= _VRR_FEEDBACK_LOW_REFRESH_HZ:
                    return 60
                return refresh_rate
    except Exception:
        pass

    if nominal_rate > 0:
        return nominal_rate

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
                import AppKit  # type: ignore

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
            from AppKit import NSApplication, NSImage  # type: ignore
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
            from AppKit import NSApplication, NSImage  # type: ignore
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
        # RN-002: sessiz yutma, native sızıntı rejimini teşhis edilemez
        # kıldı. FAZ 1 sonrası buraya hiç düşülmemeli; düşüyorsa bildir.
        # gl_debug.log'a tek yazma kanalı sdl2_overlay._diag_log'dur
        # (sdl2_overlay.py:319); main.py stdout'u log dosyasına
        # yönlendirmez — çıplak print oraya ulaşmaz (BLN-001).
        active_display_surface = None
        try:
            from sdl2_overlay import _diag_log  # döngüsel import yok: fonksiyon içi
        except Exception:
            try:
                from src.sdl2_overlay import _diag_log
            except Exception:
                _diag_log = None
        if _diag_log is not None:
            try:
                _diag_log(
                    "RN-002/1-E: display surface çözümü başarısız — eff native "
                    "fallback'e düşebilir (FAZ 1 sonrası beklenen: hiç tetiklenmemeli)"
                )
            except Exception:
                pass

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


def _sdl2_overlay_canvas_size() -> tuple[int, int] | None:
    """SDL2 overlay aktifse sabit tuval boyutunu döndür; değilse None.

    Döngüsel import yasağı (plan Risk 2): sdl2_overlay modül seviyesinde import
    EDİLMEZ; sys.modules üzerinden yoklanır — get_projected_effective_scale'in
    platform_utils yoklamasıyla (ui_scaling) aynı yerleşik desen
    (çift anahtarlı: iki import yolu da kapsanır).
    """
    ovl = sys.modules.get('sdl2_overlay') or sys.modules.get('src.sdl2_overlay')
    if ovl is None:
        return None
    try:
        if not ovl.is_active():
            return None
        size = ovl.get_canvas_size()
    except Exception:
        return None
    if size and int(size[0]) > 0 and int(size[1]) > 0:
        return (int(size[0]), int(size[1]))
    return None


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
    # SDL2 overlay aktifken koordinat uzayı zaten sabit 1920x1080 tuvaldir
    # (EKS-001 / RN-002; v2'deki software-canvas early-return'unun SDL2
    # kardeşi olan bu dal demoda yalnızca SDL2 rejiminde çalışır).
    sdl2_size = _sdl2_overlay_canvas_size()
    if sdl2_size is not None:
        return sdl2_size

    # FAZ A1 / madde (d): virtual canvas aktifken canvas boyutu = UI'in
    # koordinat uzayı (v2 paritesi — demo'da bu early-return eksikti).
    if _software_scale_active and _software_canvas is not None:
        return _software_canvas.get_size()

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
    # FAZ A1 / madde (d): virtual canvas aktifken canvas boyutu = UI koordinat
    # uzayı (v2 paritesi — demo'da bu early-return eksikti). Canvas üstünde
    # eff = canvas boyutu; SDL2 rejimi zaten yukarıda yakalandı.
    if _software_scale_active and _software_canvas is not None:
        return _software_canvas.get_size()

    # SDL2 overlay aktifken koordinat uzayı zaten sabit tuvaldir; eff = tuval
    # (EKS-001 / RN-002; v2'deki software-canvas early-return'unun SDL2
    # kardeşi olan bu dal demoda yalnızca SDL2 rejiminde çalışır). Bu
    # early-return, Windows DPI dalını (aşağıda) SDL2 rejiminde güvenle
    # atlatır (RN-006 / K13): eff = tuval boyutudur; %150 ölçekleme
    # D3D11 sunum katmanının işidir, logical ölçeğin değil.
    sdl2_size = _sdl2_overlay_canvas_size()
    if sdl2_size is not None:
        return sdl2_size

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
        # FAZ A1 / K1-A (S11): Windows pencereli DPI bölmesi kaldırıldı.
        # eff = çizim hedefi surface'unun koordinat uzayı boyutu (tuval
        # sözleşmesi; kılavuz D.4.1: "DPI canvas/koordinat uzayı boyutunu
        # değiştirmez"). Eski bölme, oyun alanını (_ui_scale, eff-tabanlı)
        # game-over katmanından (get_projected_effective_scale = eff × DPI)
        # tam DPI ölçeği kadar ayırıyordu (S11: %125'te 0.8x/1.0x ayrışma).
        # Canvas rejimleri yukarıdaki early-return'lara takıldığı için bu
        # bloğa hiç ulaşamaz; burası yalnız düz pygame pencere rejimidir ve
        # orada eff = gerçek çizim yüzeyinin boyutudur, projeksiyon çarpanı
        # 1.0'dır (dpi_scale yalnız bilgi alanı olarak raporlanır).
        surface_size = _get_surface_size(active_display_surface or target_surface)
        if surface_size is not None:
            width, height = surface_size

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


def get_desktop_work_area() -> tuple[int, int]:
    """Görev çubuğu ve dock alanları hariç kullanılabilir masaüstü çalışma alanını döndürür.

    Windows: SystemParametersInfoW(SPI_GETWORKAREA)
    macOS: NSScreen.mainScreen().visibleFrame()
    Fallback: get_native_resolution()
    """
    native_w, native_h = get_native_resolution()
    work_w, work_h = native_w, native_h

    if IS_WINDOWS:
        try:
            import ctypes
            from ctypes import wintypes
            rect = wintypes.RECT()
            # SPI_GETWORKAREA = 0x0030 (48)
            if ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0):
                w = int(rect.right - rect.left)
                h = int(rect.bottom - rect.top)
                if w > 0 and h > 0:
                    work_w, work_h = w, h
        except Exception:
            pass

    elif IS_MACOS:
        try:
            from AppKit import NSScreen  # type: ignore[import-untyped]
            vframe = NSScreen.mainScreen().visibleFrame()
            w, h = int(vframe.size.width), int(vframe.size.height)
            if w > 0 and h > 0:
                work_w, work_h = w, h
        except Exception:
            pass

    final_w = min(native_w, work_w) if native_w > 0 else work_w
    final_h = min(native_h, work_h) if native_h > 0 else work_h
    return (final_w, final_h)


def clamp_window_size_to_work_area(width: int, height: int) -> tuple[int, int]:
    """Pencere boyutunu masaüstü çalışma alanına en-boy oranını koruyarak clamp eder."""
    try:
        w = int(width)
        h = int(height)
    except Exception:
        return (1280, 720)

    if w <= 0 or h <= 0:
        return (1280, 720)

    max_w, max_h = get_desktop_work_area()
    if max_w <= 0 or max_h <= 0:
        max_w, max_h = (1920, 1080)

    if w <= max_w and h <= max_h:
        return (w, h)

    # Orantılı clamp: Kullanıcının istediği en-boy oranını koru
    scale = min(max_w / float(w), max_h / float(h))
    clamped_w = max(640, int(round(w * scale)))
    clamped_h = max(360, int(round(h * scale)))

    if clamped_w > max_w:
        clamped_w = max_w
        clamped_h = max(360, int(round(clamped_w * (float(h) / float(w)))))
    if clamped_h > max_h:
        clamped_h = max_h
        clamped_w = max(640, int(round(clamped_h * (float(w) / float(h)))))

    return (clamped_w, clamped_h)


def is_fullscreen_toggle(key: int, mods: int, custom_key: int | None = None) -> bool:
    """Fullscreen/windowed toggle desteği kaldırıldı."""
    return False


def is_alt_f4_event(event) -> bool:
    """Return whether an event represents the Windows/Linux Alt+F4 shortcut."""
    if getattr(event, 'type', None) != getattr(pygame, 'KEYDOWN', None):
        return False
    if getattr(event, 'key', None) != getattr(pygame, 'K_F4', None):
        return False
    event_mods = getattr(event, 'mod', None)
    if not isinstance(event_mods, int):
        try:
            event_mods = pygame.key.get_mods()
        except Exception:
            event_mods = 0
    return bool(event_mods & getattr(pygame, 'KMOD_ALT', 0))


def normalize_window_close_event(event):
    """Convert Alt+F4 into QUIT for borderless SDL windows."""
    if is_alt_f4_event(event):
        return pygame.event.Event(pygame.QUIT)
    return event



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
        try:
            import sdl2_overlay as _sdl2_ovl
            if _sdl2_ovl.is_active():
                if _event_patch_active:
                    info = _sdl2_ovl.get_presentation_info()
                    canvas_w = max(1, int(info.get('canvas_w', 1920)))
                    canvas_h = max(1, int(info.get('canvas_h', 1080)))
                    cx = max(0, min(canvas_w - 1, x))
                    cy = max(0, min(canvas_h - 1, y))
                    if scale != 1.0:
                        cx = int(cx / scale)
                        cy = int(cy / scale)
                    return (cx, cy)
                # FAZ A8: (pos, inside) sözleşmesi — pozisyon her zaman
                # clamped canvas koordinatıdır; inside bilgisi burada
                # kullanılmaz (yalnız event yolu DOWN düşürmede iş görür).
                (cx, cy), _inside = _sdl2_ovl.window_to_canvas_pos((x, y))
                if scale != 1.0:
                    cx = int(cx / scale)
                    cy = int(cy / scale)
                return (cx, cy)
        except Exception:
            pass

        # --- Virtual Canvas: letterbox offset + canvas scale ---
        if _software_scale_active and _virtual_blit_rect is not None:
            if _event_patch_active and _software_canvas is not None:
                canvas_w, canvas_h = _software_canvas.get_size()
                if canvas_w > 0 and canvas_h > 0:
                    canvas_x = max(0, min(canvas_w - 1, x))
                    canvas_y = max(0, min(canvas_h - 1, y))
                    if scale != 1.0:
                        canvas_x = int(canvas_x / scale)
                        canvas_y = int(canvas_y / scale)
                    return (canvas_x, canvas_y)

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
        orig_get_pos = getattr(patch_event_queue, '_orig_mouse_get_pos', None)
        pos = orig_get_pos() if orig_get_pos is not None else pygame.mouse.get_pos()
    except Exception:
        return (0, 0)

    try:
        import sdl2_overlay as _sdl2_ovl
        if _sdl2_ovl.is_active():
            # FAZ A8: (pos, inside) sözleşmesi — pozisyon clamped'tır.
            (x, y), _inside = _sdl2_ovl.window_to_canvas_pos(pos)
            if scale != 1.0:
                x = int(x / scale)
                y = int(y / scale)
            return (x, y)
    except Exception:
        pass

    if _software_scale_active and _virtual_blit_rect is not None:
        try:
            x, y = _normalize_event_pos(pos)
            if scale != 1.0:
                x = int(x / scale)
                y = int(y / scale)
            return (x, y)
        except Exception:
            pass
    return normalize_mouse_pos(pos, scale) or (0, 0)


def get_raw_mouse_pos() -> tuple[int, int]:
    """Fiziksel pencere koordinatlarında ham fare pozisyonunu döndür."""
    try:
        orig_get_pos = getattr(patch_event_queue, '_orig_mouse_get_pos', None)
        if orig_get_pos is not None:
            return orig_get_pos()
        return pygame.mouse.get_pos()
    except Exception:
        return (0, 0)


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
    if _software_scale_active and _software_canvas is not None:
        try:
            canvas_w, canvas_h = _software_canvas.get_size()
            if int(width) == int(canvas_w) and int(height) == int(canvas_h):
                return True
        except Exception:
            pass

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


def parse_window_resolution(
    value,
    default: tuple[int, int] = (1280, 720),
) -> tuple[int, int]:
    """Ayar kaydındaki 'WxH' çözünürlük değerini güvenle (w, h)'ye çöz (FAZ A3).

    Ayar dosyasındaki değer elle düzenlenmiş, bozulmuş ya da eski biçimli
    olabilir; handler bu yüzden ham int parse YAPMAZ. Geçersiz/eksik
    değerlerde default döner. Boyutlar alt pencere tabanına oturtulur
    (w >= 320, h >= 200) — bunlar layout pikselleri değil, minimum pencere
    ölçüsü güvencesidir. Ekranı aşan üst değer create_display'in work-area
    clamp'ına emanettir; burada üst sınır uygulanmaz. (v2 paritesi)
    """
    try:
        if isinstance(value, str):
            parts = value.lower().split('x')
            if len(parts) != 2:
                return default
            w = int(parts[0].strip())
            h = int(parts[1].strip())
        elif isinstance(value, (tuple, list)) and len(value) == 2:
            w = int(value[0])
            h = int(value[1])
        else:
            return default
    except Exception:
        return default
    try:
        w = int(w)
        h = int(h)
    except Exception:
        return default
    # Alt pencere tabanı: layout piksel sabiti değil, kullanılabilir minimum
    # pencere güvencesi (deforme '50x30' gibi değerler 320x200'e oturur).
    w = max(320, w)
    h = max(200, h)
    return (w, h)


def is_steam_deck() -> bool:
    """Steam Deck ortamında mı çalışıyoruz? (FAZ A3 tespit/telemetri)

    Valve'ın önerdiği tespit kuralı: Steam Deck üzerinde STEAMDECK=1
    ortam değişkeni tanımlıdır. LCD/OLED donanım sürümleri bu değerden
    ayrışmaz; tespitin amacı cihaz sınıfıdır (1280x800 taban + kontrolcü
    odaklı gezinme). Testlerde monkeypatch ile üstüne yazılabilir.
    """
    try:
        return str(os.environ.get('STEAMDECK', '')).strip() == '1'
    except Exception:
        return False


def record_platform_display_telemetry(context: str = 'startup') -> None:
    """Platform/ekran gerçeklerini teşhis günlüğüne kaydet (FAZ A3, plan m4).

    Tek satırda birleştirir: Windows Per-Monitor V2 başlangıç sırası
    (SDL_WINDOWS_DPI_AWARENESS env değeri + logical/gerçek pencere
    çifti), macOS Retina logical/backing ayrımı (mantıksal pencere
    boyutu ile sunum yüzeyi boyutu oranı) ve Steam Deck bayrağı.
    Kanal _gl_diag -> gl_compat._diag_log'tur: stdout + kalıcı
    gl_debug.log (pytest altında dosyaya yazmaz, yalnızca print eder).
    Salt-okunur ve hata yutucudur — davranış değiştirmez. (v2 paritesi)
    """
    lw: int | None = None
    try:
        parts = [f"DISPLAY TELEMETRY [{context}]"]
        try:
            parts.append(f"platform={platform.system()} sys.platform={sys.platform}")
        except Exception:
            pass
        if IS_WINDOWS:
            try:
                parts.append(
                    "dpi_awareness_env="
                    + str(os.environ.get('SDL_WINDOWS_DPI_AWARENESS', '<unset>'))
                )
            except Exception:
                pass
        if is_steam_deck():
            parts.append("steam_deck=1")
        # Mantıksal pencere boyutu (SDL points; canvas aktifse canvas sözleşmesi)
        try:
            lw, lh = get_window_logical_size()
            parts.append(f"window_logical={lw}x{lh}")
        except Exception:
            pass
        # Sunum/backing gerçekleri (canvas aktifse gerçek pencere; değilse
        # mevcut sunum yüzeyi — Retina'da yüzey > mantıksal ise backing 2x)
        try:
            info = get_virtual_canvas_info()
            canvas_desc = (
                f"canvas_active={int(bool(info.get('active')))} "
                f"canvas={info.get('canvas_w')}x{info.get('canvas_h')} "
                f"real={info.get('real_w')}x{info.get('real_h')}"
            )
            if IS_MACOS and lw is not None:
                try:
                    rw = int(info.get('real_w') or 0)
                    if rw > 0 and lw > 0:
                        canvas_desc += f" backing_ratio={rw / float(lw):.2f}"
                except Exception:
                    pass
            parts.append(canvas_desc)
        except Exception:
            pass
        try:
            geo = get_render_geometry()
            parts.append(
                f"backend={geo.backend} preset={geo.ui_preset or '<yok>'} "
                f"dpi_scale={geo.dpi_scale:.2f} generation={geo.generation}"
            )
        except Exception:
            pass
        _gl_diag(' | '.join(parts))
    except Exception:
        pass


def create_display(
    width: int,
    height: int,
    fullscreen: bool = False,
    resizable: bool = True,
    borderless: bool = False,
):
    """Create a pygame display honoring the requested fullscreen/windowed mode."""
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

    # Software virtual canvas bir overlay backend'i değildir. Gerçek display yeniden
    # kurulacaksa önce monkey-patch'leri sök; aksi halde yeni set_mode sonrası flip()
    # eski/stale display surface'e blit etmeye devam edebilir. (v2 paritesi, FAZ A3)
    try:
        if _software_scale_active:
            _teardown_virtual_canvas()
    except Exception:
        pass

    fullscreen = bool(fullscreen)
    borderless = bool(borderless) if fullscreen else False
    resizable = bool(resizable) if not fullscreen else False

    if not fullscreen:
        # Ekran boyutundan büyük pencerelerin taşmasını engellemek için çözünürlüğü clamp et (en-boy oranını koru)
        width, height = clamp_window_size_to_work_area(width, height)
    
    # macOS için özel handling
    if IS_MACOS:
        old_win_pos_mac = os.environ.get('SDL_VIDEO_WINDOW_POS')
        try:
            if fullscreen:
                # macOS: Çerçevesiz tam ekran (borderless fullscreen)
                # FULLSCREEN flag'i yerine NOFRAME kullanılır.
                # Böylece SDL Cocoa crash'i (NSWindow setStyleMask) önlenir.
                # Menu bar ve dock pyobjc ile gizlenir.
                try:
                    from AppKit import NSApplication  # type: ignore
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
                # Pencere modu - çerçeveli (resizable bayrağına duyarlı)
                # Menu bar ve dock'u geri getir
                try:
                    from AppKit import NSApplication  # type: ignore
                    app = NSApplication.sharedApplication()
                    app.setPresentationOptions_(0)  # Normal moda dön
                except Exception:
                    pass
                os.environ['SDL_VIDEO_WINDOW_POS'] = 'center'
                flags = pygame.RESIZABLE if resizable else 0
                surface = pygame.display.set_mode((width, height), flags)
                invalidate_refresh_rate_cache()
                return surface
        except pygame.error as e:
            print(f"[UYARI] macOS display hatası: {e}")
            try:
                surface = pygame.display.set_mode((width or 800, height or 600), pygame.RESIZABLE if resizable else 0)
                invalidate_refresh_rate_cache()
                return surface
            except pygame.error:
                invalidate_refresh_rate_cache()
                return pygame.Surface((width or 800, height or 600))
        finally:
            if old_win_pos_mac is not None:
                os.environ['SDL_VIDEO_WINDOW_POS'] = old_win_pos_mac
            elif 'SDL_VIDEO_WINDOW_POS' in os.environ:
                del os.environ['SDL_VIDEO_WINDOW_POS']
    
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

    # Exclusive fullscreen modunda SDL_VIDEO_CENTERED'ı geçici devre dışı bırak;
    # pencere modunda ise pencereyi ekranın ortasında aç.
    old_centered_excl = None
    old_win_pos_excl = None
    if fullscreen:
        old_centered_excl = os.environ.pop('SDL_VIDEO_CENTERED', None)
    else:
        old_centered_excl = os.environ.get('SDL_VIDEO_CENTERED')
        old_win_pos_excl = os.environ.get('SDL_VIDEO_WINDOW_POS')
        os.environ['SDL_VIDEO_CENTERED'] = '1'
        os.environ['SDL_VIDEO_WINDOW_POS'] = 'center'
    try:
        if fullscreen:
            surface = pygame.display.set_mode((0, 0), flags)
        else:
            surface = pygame.display.set_mode((width, height), flags)
        invalidate_refresh_rate_cache()
        return surface
    except pygame.error:
        try:
            fallback_flags = pygame.DOUBLEBUF | (pygame.RESIZABLE if resizable else 0)
            surface = pygame.display.set_mode((width or 800, height or 600), fallback_flags)
            invalidate_refresh_rate_cache()
            return surface
        except pygame.error:
            invalidate_refresh_rate_cache()
            return pygame.Surface((width or 800, height or 600))
    finally:
        if fullscreen:
            if old_centered_excl is not None:
                os.environ['SDL_VIDEO_CENTERED'] = old_centered_excl
        else:
            if old_centered_excl is not None:
                os.environ['SDL_VIDEO_CENTERED'] = old_centered_excl
            elif 'SDL_VIDEO_CENTERED' in os.environ:
                del os.environ['SDL_VIDEO_CENTERED']
            if old_win_pos_excl is not None:
                os.environ['SDL_VIDEO_WINDOW_POS'] = old_win_pos_excl
            elif 'SDL_VIDEO_WINDOW_POS' in os.environ:
                del os.environ['SDL_VIDEO_WINDOW_POS']


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


# FAZ A2 madde 3: letterbox blit geometrisi değişmedikçe subsurface + fill
# rect'leri YENİDEN KULLANILIR. Kare-başı nesne tahsisi (subsurface wrapper +
# 4 Rect + ölçeklenmiş ara Surface) GC baskısı yaratır; 240 FPS'te fark
# yaratır (kare-başı tahsis kırmızı çizgisi). Anahtar: (parent yüzey id,
# pencere boyutu, letterbox rect). Ayrıca tam-ekran siyah fill yerine yalnız
# dolu bantlar doldurulur (4K'da tüm-ekran fill maliyeti).
_blit_letterbox_cache: tuple = (None, None, None, None, None, None)


def _blit_canvas_to_display() -> None:
    """Virtual canvas'ı letterbox ile gerçek display'e blit et ve _orig_flip çağır."""
    global _virtual_blit_rect, _blit_letterbox_cache
    if _software_canvas is None or _real_display_surface is None:
        _orig_flip()
        return
    real_w, real_h = _real_display_surface.get_size()
    canvas_w, canvas_h = _software_canvas.get_size()
    bx, by, bw, bh = _calc_letterbox(canvas_w, canvas_h, real_w, real_h)
    _virtual_blit_rect = (bx, by, bw, bh)

    # bw/bh sıfır veya negatifse scale başarısız olur: siyah fill yapmadan _orig_flip çağır
    if bw <= 0 or bh <= 0:
        _orig_flip()
        return

    # FAZ A2 madde 3: geometri değişmedikçe cache'ten al; değiştiyse (pencere
    # resize / canvas swap) bir kez yeniden oluştur. Dolu olmayan bantlar
    # None olarak cache'lenir (0 genişlikli Rect tahsis etme).
    cache_key = (id(_real_display_surface), real_w, real_h, bx, by, bw, bh)
    if _blit_letterbox_cache[0] != cache_key:
        try:
            sub = _real_display_surface.subsurface(pygame.Rect(bx, by, bw, bh))
        except Exception:
            sub = None
        fills = (
            pygame.Rect(0, 0, bx, real_h) if bx > 0 else None,
            pygame.Rect(bx + bw, 0, real_w - (bx + bw), real_h) if bx > 0 else None,
            pygame.Rect(0, 0, real_w, by) if by > 0 else None,
            pygame.Rect(0, by + bh, real_w, real_h - (by + bh)) if by > 0 else None,
        )
        _blit_letterbox_cache = (cache_key, sub, *fills)
    _, _sub, _fill_left, _fill_right, _fill_top, _fill_bottom = _blit_letterbox_cache

    # Siyah bantları doldur (Tüm ekranı doldurmak yerine sadece boş yan bantları doldur - 4K ekranlarda yüksek performans sağlar)
    if _fill_left is not None:
        _real_display_surface.fill((0, 0, 0), _fill_left)
        _real_display_surface.fill((0, 0, 0), _fill_right)
    if _fill_top is not None:
        _real_display_surface.fill((0, 0, 0), _fill_top)
        _real_display_surface.fill((0, 0, 0), _fill_bottom)

    # Canvas'ı doğrudan display subsurface'ine ölçekle (Geçici Surface tahsisini ve kopyalamayı önler)
    try:
        if _sub is None:
            raise ValueError('letterbox subsurface yok')
        pygame.transform.scale(_software_canvas, (bw, bh), _sub)
    except Exception as _blit_exc:
        try:
            scaled = pygame.transform.scale(_software_canvas, (bw, bh))
            _real_display_surface.blit(scaled, (bx, by))
        except Exception as _blit_exc2:
            print(f"[Virtual Canvas] Blit hatası ({bw}x{bh}): {_blit_exc2}")
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


# ---------------------------------------------------------------------------
# FAZ A1: Canvas durum makinesi + geometri kuşağı (generation)
# ---------------------------------------------------------------------------
# Gorsel_Olcek_Sorunlari_Cozum_Plani.md FAZ A1: her render backend'inin
# (software canvas / SDL2 overlay / GL overlay / düz pygame) yaşam döngüsü tek
# duruma ve tek sayaca bağlanır. Ekranlar layout snapshot'larını kuşak
# numarasıyla damgalar; kuşak değiştiğinde bayat snapshot'ı geçersiz sayıp
# yeniden kurar (S2/S3'ün kökü: 100→125→100 rect döngüsü + bayat cache).
# ---------------------------------------------------------------------------
CANVAS_STATE_INACTIVE = 'inactive'
CANVAS_STATE_PREPARING = 'preparing'
CANVAS_STATE_ACTIVE = 'active'
CANVAS_STATE_TEARING_DOWN = 'tearing_down'
CANVAS_STATE_FALLBACK = 'fallback'

# Yasal geçişler. SDL2/GL overlay kurulumları INACTIVE→ACTIVE ile girer;
# software canvas setup→teardown zinciri PREPARING/ACTIVE üzerinden döner;
# FALLBACK pass-through (canvas==real / kurulum başarısız) durumudur.
_CANVAS_STATE_TRANSITIONS = {
    CANVAS_STATE_INACTIVE: frozenset({
        CANVAS_STATE_PREPARING, CANVAS_STATE_ACTIVE, CANVAS_STATE_FALLBACK,
    }),
    CANVAS_STATE_PREPARING: frozenset({
        CANVAS_STATE_ACTIVE, CANVAS_STATE_FALLBACK,
    }),
    CANVAS_STATE_ACTIVE: frozenset({
        CANVAS_STATE_PREPARING, CANVAS_STATE_TEARING_DOWN,
    }),
    CANVAS_STATE_TEARING_DOWN: frozenset({
        CANVAS_STATE_INACTIVE, CANVAS_STATE_PREPARING,
    }),
    CANVAS_STATE_FALLBACK: frozenset({
        CANVAS_STATE_PREPARING, CANVAS_STATE_ACTIVE, CANVAS_STATE_TEARING_DOWN,
        CANVAS_STATE_INACTIVE,
    }),
}

_canvas_state: str = CANVAS_STATE_INACTIVE
_canvas_state_backend: str | None = None
_geometry_generation: int = 0


def get_canvas_state() -> str:
    """Aktif render backend'inin canvas yaşam döngüsü durumu (FAZ A1)."""
    return _canvas_state


def get_canvas_state_backend() -> str | None:
    """Durumu taşıyan backend adı ('software_canvas' | 'sdl2_overlay' | 'gl_compat' | None)."""
    return _canvas_state_backend


def _set_canvas_state(new_state: str, backend: str | None = None) -> None:
    """Canvas durumunu güncelle; yasadışı geçişte toleranslı zorla-alma + teşhis.

    Oyun döngüsü bir durum kirliliği yüzünden kilitlenmemeli: sapma yalnızca
    stdout teşhisine yazılır ve geçiş uygulanır. Aynı duruma ve aynı backend'e
    geçiş idempotent no-op'tur (log da üretmez).
    """
    global _canvas_state, _canvas_state_backend
    if new_state == _canvas_state and (backend is None or backend == _canvas_state_backend):
        return
    allowed = _CANVAS_STATE_TRANSITIONS.get(_canvas_state, frozenset())
    if new_state not in allowed:
        try:
            print(
                f"[CanvasState] Beklenmedik geçiş: {_canvas_state} -> {new_state} "
                f"(backend={backend or _canvas_state_backend})"
            )
        except Exception:
            pass
    _canvas_state = new_state
    if new_state == CANVAS_STATE_INACTIVE:
        # INACTIVE = taşıyıcı backend yok; alan her geçişte sıfırlanır
        # (backend=None "dokunma" yerine sıfırlama semantiği taşır).
        _canvas_state_backend = None
    elif backend is not None:
        _canvas_state_backend = backend


def bump_geometry_generation() -> int:
    """Geometri kuşağını artır; yeni değeri döndür (FAZ A1).

    Canvas kurulumu/ardownı ve backend geçişleri çağırır. Ekranlar snapshot
    aldıkları kuşağı bu sayıyla damgalar; farklı kuşağa rastlayan tüketici
    snapshot'ı yeniden kurar (S2/S3 verici ucu; A4 cache generation'ın kaynağı).
    """
    global _geometry_generation
    _geometry_generation += 1
    return _geometry_generation


def get_geometry_generation() -> int:
    """Mevcut geometri kuşağı sayacı (0 = henüz geçiş yaşanmadı)."""
    return _geometry_generation


def _notify_canvas_backend_active(backend: str) -> None:
    """Overlay backend kurulduğunda çağırır; ACTIVE + kuşak artışı (FAZ A1).

    sdl2_overlay / gl_compat platform_utils'ü import EDEMEZ (döngüsel import
    yasağı, plan Risk 2); bu fonksiyonu sys.modules yoklamasıyla bulup
    çağırırlar (çift anahtarlı: iki import yolu da kapsanır).
    """
    _set_canvas_state(CANVAS_STATE_ACTIVE, backend)
    bump_geometry_generation()


def _notify_canvas_backend_inactive(backend: str) -> None:
    """Overlay backend kapatıldığında çağırır; TEARING_DOWN→INACTIVE + kuşak."""
    _set_canvas_state(CANVAS_STATE_TEARING_DOWN, backend)
    bump_geometry_generation()
    _set_canvas_state(CANVAS_STATE_INACTIVE, None)


def _gl_overlay_active() -> bool:
    """gl_compat overlay aktif mi? (K2 / BLN-006: gl yolu erişimcisi).

    K2 ile gl_compat'e is_active() eklendi; eski sürümlerle (veya erişimci
    tanımsızken) `_active` modül değişkeni üzerinden son çare yoklaması yapılır.
    """
    gl = sys.modules.get('gl_compat') or sys.modules.get('src.gl_compat')
    if gl is None:
        return False
    try:
        is_active = getattr(gl, 'is_active', None)
        if callable(is_active):
            return bool(is_active())
        return bool(getattr(gl, '_active', False))
    except Exception:
        return False


class RenderGeometry(NamedTuple):
    """Geçerli render geometrisinin salt-okunur snapshot'ı (FAZ A1).

    Layout kurulum/snapshot anında alınır (kare içi değil): A6/A7 ekranları ve
    A8 mouse normalizasyonu aynı kaynaktan okur — iki katmanın farklı ölçek
    tabanından kaynaklanan ayrışmayı (S11) tek sözleşmeye indirger.
    """

    canvas_size: tuple[int, int]                       # çizim koordinat uzayı (eff sözleşmesi)
    window_size: tuple[int, int]                       # hedef pencere/sunum yüzeyi
    logical_window_size: tuple[int, int]               # SDL logical points (gwls)
    presentation_rect: tuple[int, int, int, int]       # canvas→pencere blit (x, y, w, h)
    safe_rect: tuple[int, int, int, int]               # canvas uzayında güvenli alan
    scale: float                                       # sunum ölçeği (blit_w / canvas_w)
    offset: tuple[int, int]                            # sunum offset'i (letterbox)
    backend: str                                       # 'software_canvas' | 'sdl2_overlay' | 'gl_compat' | 'plain'
    ui_preset: str                                     # ui_scaling preset adı ('' → çözülemedi)
    dpi_scale: float                                   # Windows pencere DPI ölçeği (değilse 1.0)
    generation: int                                    # geometri kuşağı


def _canvas_safe_rect(canvas_size: tuple[int, int]) -> tuple[int, int, int, int]:
    """Canvas uzayında kenar marjlı güvenli alanı (x, y, w, h) döndür (A1/A6).

    Marj oran %2.5'tir (1080p tuvalde ~27px, 2160p'de ~54px) ve güvenli alanın
    en az 24px kalması güvenceye alınır: marj, (boyut - 24) / 2 ile sınırlıdır.
    Amaç: aşırı taramalı TV'ler ve letterbox hizasındaki kırpılmalara karşı
    P0 içerik (metin/buton) kenara yapışmasın (S4/S7 tüketimi A6/A7'de).
    """
    cw, ch = canvas_size
    if cw <= 0 or ch <= 0:
        return (0, 0, 0, 0)
    margin_x = int(round(cw * 0.025))
    margin_y = int(round(ch * 0.025))
    margin_x = max(0, min(margin_x, (cw - 24) // 2)) if cw > 24 else 0
    margin_y = max(0, min(margin_y, (ch - 24) // 2)) if ch > 24 else 0
    return (margin_x, margin_y, cw - 2 * margin_x, ch - 2 * margin_y)


def get_render_geometry(screen: pygame.Surface | None = None) -> RenderGeometry:
    """Aktif render geometrisinin tek-snapshot tanımını döndür (FAZ A1).

    Tüm katmanlar (oyun alanı, overlay'ler, menüler) bu tek kaynaktan okur;
    iki farklı ölçek tabanı (S11) bu sözleşmeyle tek kaynağa iner. Kare içi
    değil, layout kurulum anında çağrılır. Varsayılan yol 'plain'dir; canvas
    rejimleri yalnızca kendi durum bayrakları açıksa seçilir (yoklamalar
    istisna toleranslıdır: overlay modülü yoksa dal sessizce atlanır).
    """
    # 1) Backend tespiti + canvas/pencere/sunum değerleri
    sdl2 = sys.modules.get('sdl2_overlay') or sys.modules.get('src.sdl2_overlay')
    sdl2_info = None
    if sdl2 is not None:
        try:
            if sdl2.is_active():
                sdl2_info = sdl2.get_presentation_info()
        except Exception:
            sdl2_info = None

    if sdl2_info:
        backend = 'sdl2_overlay'
        canvas_size = (int(sdl2_info.get('canvas_w', 0) or 0), int(sdl2_info.get('canvas_h', 0) or 0))
        window_size = (int(sdl2_info.get('window_w', 0) or 0), int(sdl2_info.get('window_h', 0) or 0))
        presentation_rect = (
            int(sdl2_info.get('offset_x', 0) or 0),
            int(sdl2_info.get('offset_y', 0) or 0),
            int(sdl2_info.get('blit_w', 0) or 0),
            int(sdl2_info.get('blit_h', 0) or 0),
        )
    elif _software_scale_active and _software_canvas is not None:
        backend = 'software_canvas'
        canvas_size = _software_canvas.get_size()
        if _virtual_blit_rect is not None:
            presentation_rect = _virtual_blit_rect
        else:
            presentation_rect = _calc_letterbox(
                canvas_size[0], canvas_size[1],
                *(_real_display_surface.get_size() if _real_display_surface is not None else canvas_size),
            )
        if _real_display_surface is not None:
            window_size = _real_display_surface.get_size()
        else:
            window_size = canvas_size
    elif _gl_overlay_active():
        backend = 'gl_compat'
        gl = sys.modules.get('gl_compat') or sys.modules.get('src.gl_compat')
        gl_surface = None
        try:
            gl_surface = gl.get_display_surface() if gl is not None else None
        except Exception:
            gl_surface = None
        if gl_surface is not None:
            canvas_size = gl_surface.get_size()
        elif screen is not None:
            canvas_size = screen.get_size()
        else:
            canvas_size = _coerce_positive_size(*get_native_resolution())
        window_size = canvas_size
        presentation_rect = (0, 0, canvas_size[0], canvas_size[1])
    else:
        backend = 'plain'
        target_surface, _active_display_surface, _is_display = _resolve_display_surface_context(
            screen, None,
        )
        target_size = _get_surface_size(target_surface)
        if target_size is None:
            target_size = _coerce_positive_size(*get_native_resolution())
        canvas_size = target_size
        window_size = target_size
        presentation_rect = (0, 0, target_size[0], target_size[1])

    # 2) Türetilmiş alanlar
    logical_window_size = get_window_logical_size(screen)
    cw, ch = canvas_size
    px, py, pw, ph = presentation_rect
    if pw > 0 and cw > 0:
        scale = pw / float(cw)
    elif ph > 0 and ch > 0:
        scale = ph / float(ch)
    else:
        scale = 1.0
    offset = (px, py)

    # 3) Preset / DPI / kuşak (istisna toleranslı yoklamalar)
    ui_preset = ''
    try:
        from ui_scaling import get_ui_scale_preset
        ui_preset = get_ui_scale_preset() or ''
    except Exception:
        try:
            from src.ui_scaling import get_ui_scale_preset
            ui_preset = get_ui_scale_preset() or ''
        except Exception:
            ui_preset = ''
    dpi_scale = 1.0
    if IS_WINDOWS:
        try:
            dpi_scale = _get_windows_window_scale_factor() or 1.0
        except Exception:
            dpi_scale = 1.0

    return RenderGeometry(
        canvas_size=canvas_size,
        window_size=window_size,
        logical_window_size=logical_window_size,
        presentation_rect=presentation_rect,
        safe_rect=_canvas_safe_rect(canvas_size),
        scale=scale,
        offset=offset,
        backend=backend,
        ui_preset=ui_preset,
        dpi_scale=dpi_scale,
        generation=_geometry_generation,
    )


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

    # SDL2 overlay aktifken virtual canvas kurma: SDL renderer GPU'da zaten
    # letterbox/ölçekleme yapıyor. platform_utils'in CPU-taraflı
    # pygame.transform.scale'i üstüne eklemek çift maliyet yaratır (CPU scale +
    # GPU upload). Overlay aktifken pass-through yap; ui_scaling'e "canvas yok"
    # bildir (çift ölçekleme olmasın). (v2 paritesi — inceleme B1: FAZ 1
    # early-return'leri olmadan bu dal sessizce atlanabiliyordu; şimdi eff
    # tuvale sabitlendiği için SDL2 + software birleşik rejimi koordinat
    # uzayı çelişkisi üretirdi.)
    try:
        import sdl2_overlay as _sdl2_ovl
        if _sdl2_ovl.is_active():
            try:
                from ui_scaling import set_virtual_canvas_active
                # KILAVUZ FAZ 2 (plan Faz 1.2'den gerekçeli sapma): SDL2 yolunda
                # bayrak bilinçli olarak False kalır. eff boyutu FAZ 1 ile tuvale
                # sabitlendi; identity _s dallarının açılması 1080p Steam
                # baseline'ını (~1.22-1.24 ölçek) ham koordinata düşürürdü.
                # Software canvas (tuval boyutu preset taşıyıcısı) bayrağı
                # True tutmaya devam eder — mevcut sözleşme korunur.
                set_virtual_canvas_active(False)
            except Exception:
                pass
            # Eğer önceki bir virtual canvas kuruluysa temizle
            if _software_scale_active:
                _teardown_virtual_canvas()
            # FAZ A3 (v2 paritesi): SDL2 yolunda da event/mouse yamaları ayakta
            # kalsın — _normalize_event_pos overlay aktifken window_to_canvas_pos
            # üzerinden normalize eder; yamalar sökülüp geri gelmezse SDL2
            # oturumunda fare koordinatları ham pencere uzayında akar.
            # patch_event_queue idempotent + desync-toleranslıdır.
            try:
                patch_event_queue()
            except Exception:
                pass
            return real_surface
    except Exception:
        pass

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
        # FAZ A1: geometri "canvas yok, gerçek yüzeye çizim" olarak değişti
        # (1080p normal preset'in standart durumu). Kuşak bump'ı, bayat
        # snapshot'ları damgalamak için bilinçli olarak burada da atılır.
        _set_canvas_state(CANVAS_STATE_FALLBACK, 'software_canvas')
        bump_geometry_generation()
        # FAZ A3 (v2 paritesi): preset 125 -> 100 gibi geçişler teardown ile
        # yamaları söktüğünde pass-through dalı onları GERİ GETİRMEZSE
        # oturumun kalanında (100 -> 125 geri dönüşü dahil) mouse
        # koordinatları normalize edilmeden akardı. Yamaları burada da
        # yeniden kur: canvas yokken kimlik dönüşüm (pass-through) uygularlar.
        try:
            patch_event_queue()
        except Exception:
            pass
        return real_surface

    # FAZ A4 (v2 paritesi): PREPARING pass-through dalının SONRASına
    # taşındı. Önceki yerinde pass-through, PREPARING iken
    # _teardown_virtual_canvas çağırıyordu (preparing→tearing_down
    # yasadışı geçiş; A1'in toleranslı zorla-alması yutuyordu ama
    # [CanvasState] teşhisini kirletiyordu).
    _set_canvas_state(CANVAS_STATE_PREPARING, 'software_canvas')

    # Canvas surface oluştur
    try:
        canvas = pygame.Surface((canvas_w, canvas_h))
        canvas = canvas.convert()
    except Exception as exc:
        print(f"[Virtual Canvas] Canvas oluşturulamadı: {exc}")
        _set_canvas_state(CANVAS_STATE_FALLBACK, 'software_canvas')
        bump_geometry_generation()
        # FAZ A3 (v2 paritesi): hata FALLBACK'inde de yamalar ayakta kalsın
        # (pass-through).
        try:
            patch_event_queue()
        except Exception:
            pass
        return real_surface

    _real_display_surface = real_surface
    _software_canvas = canvas
    _software_scale_active = True
    _virtual_blit_rect = _calc_letterbox(canvas_w, canvas_h, real_w, real_h)

    # Monkey-patch display fonksiyonları
    # _orig_flip'i burada yeniden al: sdl2_overlay veya gl_compat setup sırasında
    # pygame.display.flip'i zaten patch'lemiş olabilir. Bu noktada aldığımızda
    # Steam overlay → virtual canvas blit zinciri doğru sırayla çalışır.
    # (v2 paritesi, FAZ A3: demo doğrudan atama yapıyordu; orig kaydı
    # yokluğunda ikinci kurulum flip zincirini kendi patch'ine sarardı.)
    global _orig_flip, _orig_update, _orig_get_surface
    try:
        current_flip = pygame.display.flip
        current_update = pygame.display.update
        current_get_surface = pygame.display.get_surface
        # Kendi patch'lerimizi tekrar sarmamak için kontrol et
        if current_flip not in (_software_flip,):
            _orig_flip = current_flip
        if current_update not in (_software_update,):
            _orig_update = current_update
        if current_get_surface not in (_software_get_surface,):
            _orig_get_surface = current_get_surface
    except Exception:
        pass

    pygame.display.flip = _software_flip
    pygame.display.update = _software_update
    pygame.display.get_surface = _software_get_surface

    # FAZ A1: kurulum tamamlandı — canvas yayında; kuşak sayacı arttı.
    # Tüketici ekranlar (A6/A7) bu kuşakla snapshot damgalar.
    _set_canvas_state(CANVAS_STATE_ACTIVE, 'software_canvas')
    bump_geometry_generation()

    # ui_scaling'e virtual canvas aktif olduğunu bildir
    # → tüm _ui_scale() / _sx() metodları 1.0 döndürerek çift ölçeklemeyi engeller
    try:
        from ui_scaling import set_virtual_canvas_active
        set_virtual_canvas_active(True)
    except Exception:
        pass

    # FAZ A3 (v2 paritesi, ömür gediği): kurulum çağrıları startup'a mahsus
    # olmamalı. Preset değişimi teardown ile yamaları söktüğünde, YENİ kurulum
    # onları geri getirmeli — aksi halde 125 -> 100 -> 125 döngüsü sonrası
    # mouse/event normalizasyonu oturum boyunca kapalı kalır. Buradaki
    # çağrı idempotent: yamalar zaten kuruluysa no-op'tur.
    try:
        patch_event_queue()
    except Exception:
        pass

    print(
        f"[Virtual Canvas] Aktif: canvas={canvas_w}x{canvas_h} "
        f"→ real={real_w}x{real_h} (x{multiplier:.2f}) "
        f"letterbox=({_virtual_blit_rect[0]},{_virtual_blit_rect[1]},{_virtual_blit_rect[2]},{_virtual_blit_rect[3]})"
    )

    # Rebuild/setup sonrasında logical canvas boyutunu event kuyruğuna koy.
    # Bu, VIDEORESIZE işleyen ekranlarda layout/font yenilemeyi tetikler; global
    # tüm text/font cache'leri için tam yeniden kurulum garantisi değildir.
    # (v2 paritesi, FAZ A3.)
    try:
        event = pygame.event.Event(
            pygame.VIDEORESIZE,
            {'size': (canvas_w, canvas_h), 'w': canvas_w, 'h': canvas_h}
        )
        pygame.event.post(event)
    except Exception:
        pass

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
    real_surface = _real_display_surface
    if real_surface is None:
        # FAZ A4 (v2 paritesi, S2): tuval söküldükten sonra yeni bir
        # büyütme isteği gelirse _real_display_surface None'dır; güncel
        # display surface'ını kullan. Aksi halde ikinci kurulum isteği
        # HİÇ tuval kuramazdı. Canvas aktifken bu dala düşülmez
        # (_real_display_surface doludur); None olduğu iki durumda da
        # get_surface gerçek display'i döndürür.
        try:
            real_surface = pygame.display.get_surface()
        except Exception:
            real_surface = None
    if real_surface is None or not hasattr(real_surface, 'get_size'):
        return None

    if multiplier is None:
        try:
            from ui_scaling import get_ui_scale_multiplier
            multiplier = get_ui_scale_multiplier()
        except Exception:
            multiplier = 1.0

    return setup_virtual_canvas(real_surface, multiplier)


def _teardown_virtual_canvas() -> None:
    """Virtual canvas monkey-patch'lerini geri al."""
    global _software_canvas, _real_display_surface, _software_scale_active, _virtual_blit_rect, _blit_letterbox_cache

    # FAZ A4 (v2 paritesi): sökülecek bir şey yoksa sessiz erken çık —
    # INACTIVE'tan TEARING_DOWN'a geçiş yasadışıdır ve toleranslı
    # zorla-alma bunu yutarken [CanvasState] teşhisini kirletirdi.
    # Patch'ler bizimse tam yol işletilir.
    try:
        _nothing_to_teardown = (
            _canvas_state == CANVAS_STATE_INACTIVE
            and not _software_scale_active
            and _software_canvas is None
            and _real_display_surface is None
            and pygame.display.get_surface is not _software_get_surface
        )
    except Exception:
        _nothing_to_teardown = False
    if _nothing_to_teardown:
        return

    # FAZ A1: söküm başladı; sonda INACTIVE'a döner + kuşak artar (geometri
    # "canvas yok" olarak değişti — bayat snapshot'lar damgalanır).
    _set_canvas_state(CANVAS_STATE_TEARING_DOWN, 'software_canvas')

    # Gerçek ekranın boyutlarını al (v2 paritesi): son VIDEORESIZE bildirimi
    # için söküm gerçek yüzeyi None'lamadan ÖNCE yakalanır.
    real_w, real_h = 1728, 1080
    if _real_display_surface is not None:
        try:
            real_w, real_h = _real_display_surface.get_size()
        except Exception:
            pass

    try:
        # Yalnızca kendi patch'lerimizi geri al (v2 paritesi): mevcut
        # flip/update/get_surface _software_* değilse başka bir katman
        # (ör. sdl2_overlay'ın _patched_flip'i) patch koymuştur — dokunma.
        # B1'in canvas→overlay geçişindeki _teardown_virtual_canvas çağrısı
        # bu korumayı gerekli kılar.
        if pygame.display.flip is _software_flip:
            pygame.display.flip = _orig_flip
        if pygame.display.update is _software_update:
            pygame.display.update = _orig_update
        if pygame.display.get_surface is _software_get_surface:
            pygame.display.get_surface = _orig_get_surface
    except Exception:
        pass
    _software_canvas = None
    _real_display_surface = None
    _software_scale_active = False
    _virtual_blit_rect = None
    # FAZ A2 madde 3 (v2 paritesi): letterbox blit cache'i parent yüzeye
    # bağlı — yüzey söküldü, cache'teki subsurface/rect'ler bayattı; sıfırla.
    _blit_letterbox_cache = (None, None, None, None, None, None)
    # FAZ A1: söküm tamamlandı — durum ve kuşak (INACTIVE'a yasal geçiş;
    # idempotent erken dönüş yok, çift bump yalnız sayacı büyütür, zararsız).
    _set_canvas_state(CANVAS_STATE_INACTIVE, None)
    bump_geometry_generation()
    # ui_scaling'i bilgilendir: canvas devre dışı, eski ölçeklemeye dön
    try:
        from ui_scaling import set_virtual_canvas_active
        set_virtual_canvas_active(False)
    except Exception:
        pass

    # Event kuyruğu monkey-patch'lerini de geri al (v2 paritesi, FAZ A3)
    try:
        unpatch_event_queue()
    except Exception:
        pass

    # Event kuyruğuna gerçek ekran boyutu ile VIDEORESIZE gönder (v2 paritesi)
    try:
        event = pygame.event.Event(
            pygame.VIDEORESIZE,
            {'size': (real_w, real_h), 'w': real_w, 'h': real_h}
        )
        pygame.event.post(event)
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
# FAZ A3 (v2 paritesi): kurulum kaydı — hangi slota hangi patched callable
# kuruldu ve sökülürken hangi orig referansına döneceği (slot → (holder,
# attr, patched, orig)). patch_event_queue kısmen başarısız olursa flag ile
# kurulu yamalar ayrışır (desync); ikinci kurulum kendi yamasını "orig"
# olarak yakalayıp ÇİFTE normalizasyon üretir (self-capture). Bu kayıt
# desync'i tespit eder ve yamaları kayıtlı orig'lere GERİ ALARAK telafi
# eder; unpatch yalnızca hâlâ bizim olan slota dokunur — slotu devralan
# yabancı katman (sdl2_overlay'in get_window_size yaması gibi) ezilmez.
# Not: legacy `patch_event_queue._orig_*` fonksiyon öznitelikleri ayrıca
# korunur (get_mouse_pos / get_raw_mouse_pos bunları ham pozisyon için
# okur — canlı üretim sözleşmesi).
_event_patch_installed: dict = {}


def _normalize_event_pos_checked(raw_pos: tuple) -> tuple[tuple[int, int], bool]:
    """Ham fare pozisyonunu canvas koordinatına çevir — (pos, inside) çifti.

    FAZ A8 event provenance: letterbox (siyah bar) üzerindeki pozisyonlar
    inside=False döner; _patched_event_get MOUSEBUTTONDOWN'ı düşürür (kenar
    butonu yanlış tetiklenmesi biter). SDL2 overlay ve software virtual
    canvas yollarının İKİSİNDE de aynı sözleşme geçerlidir. Pozisyon her
    durumda clamped canvas koordinatıdır (motion/hover yolları bozulmaz).
    """
    try:
        import sdl2_overlay as _sdl2_ovl
        if _sdl2_ovl.is_active():
            return _sdl2_ovl.window_to_canvas_pos(raw_pos)
    except Exception:
        pass
    if not _software_scale_active or _virtual_blit_rect is None:
        try:
            return (int(raw_pos[0]), int(raw_pos[1])), True
        except Exception:
            return (0, 0), False
    bx, by, bw, bh = _virtual_blit_rect
    canvas_w, canvas_h = (
        _software_canvas.get_size() if _software_canvas is not None
        else (bw, bh)
    )
    if bw <= 0 or bh <= 0:
        return (int(raw_pos[0]), int(raw_pos[1])), True
    try:
        rx = float(raw_pos[0]) - bx
        ry = float(raw_pos[1]) - by
    except Exception:
        return (0, 0), False
    inside = (bx <= raw_pos[0] < bx + bw) and (by <= raw_pos[1] < by + bh)
    cx = int(round(rx * canvas_w / bw))
    cy = int(round(ry * canvas_h / bh))
    cx = max(0, min(canvas_w - 1, cx))
    cy = max(0, min(canvas_h - 1, cy))
    return (cx, cy), inside


def _normalize_event_pos(raw_pos: tuple) -> tuple[int, int]:
    """Ham fare pozisyonunu virtual canvas koordinatına dönüştür (yalnız pozisyon)."""
    pos, _inside = _normalize_event_pos_checked(raw_pos)
    return pos


def _normalize_event_rel(raw_rel: tuple) -> tuple[int, int]:
    """Ham fare hareketini (rel) virtual canvas ölçeğine dönüştür."""
    try:
        import sdl2_overlay as _sdl2_ovl
        if _sdl2_ovl.is_active():
            return _sdl2_ovl.window_to_canvas_rel(raw_rel)
    except Exception:
        pass
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


def denormalize_mouse_pos(canvas_pos: tuple) -> tuple[int, int]:
    """Canvas koordinatını fiziksel pencere koordinatına geri dönüştür."""
    try:
        import sdl2_overlay as _sdl2_ovl
        if _sdl2_ovl.is_active():
            return _sdl2_ovl.canvas_to_window_pos(canvas_pos)
    except Exception:
        pass
    if not _software_scale_active or _virtual_blit_rect is None or _software_canvas is None:
        return canvas_pos
    bx, by, bw, bh = _virtual_blit_rect
    canvas_w, canvas_h = _software_canvas.get_size()
    if canvas_w <= 0 or canvas_h <= 0 or bw <= 0 or bh <= 0:
        return canvas_pos
    cx, cy = canvas_pos[0], canvas_pos[1]
    rx = float(cx) * bw / canvas_w
    ry = float(cy) * bh / canvas_h
    return (int(round(rx + bx)), int(round(ry + by)))


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

    _sdl2_mouse_active = False
    try:
        import sdl2_overlay as _sdl2_ovl
        _sdl2_mouse_active = bool(_sdl2_ovl.is_active())
    except Exception:
        _sdl2_mouse_active = False

    events = [normalize_window_close_event(e) for e in events]
    if not _sdl2_mouse_active and (not _software_scale_active or _virtual_blit_rect is None):
        return events

    patched = []
    for event in events:
        try:
            event = normalize_window_close_event(event)
            etype = event.type
            if etype in (
                pygame.MOUSEBUTTONDOWN,
                pygame.MOUSEBUTTONUP,
                pygame.MOUSEMOTION,
            ):
                if getattr(event, 'from_gamepad', False):
                    patched.append(event)
                    continue
                new_pos, pos_inside = _normalize_event_pos_checked(event.pos)
                # FAZ A8: letterbox (siyah bar) tıklaması GEÇERSİZ event üretir —
                # MOUSEBUTTONDOWN düşürülür (kenar butonu yanlış tetiklenmesi
                # biter). BUTTONUP/MOTION iletilir: sürükleme durumu yarım
                # kalmaz (DOWN'sız gelen UP herhangi bir arm durumunu
                # tetiklemez), hover takibi clamped pozisyonla sürer.
                if etype == pygame.MOUSEBUTTONDOWN and not pos_inside:
                    continue
                attrs = {'pos': new_pos}
                if etype == pygame.MOUSEMOTION:
                    try:
                        new_rel = _normalize_event_rel(event.rel)
                        attrs['rel'] = new_rel
                    except Exception:
                        pass
                # pygame.event.Event ile yeni event oluştur (C-level salt okunur hatalarını önlemek için güvenli kopyalama)
                # dir(event) yerine event.__dict__ kullanımı hem performansı artırır hem de çökmeleri önler.
                event_dict = event.dict if hasattr(event, 'dict') else getattr(event, '__dict__', {})
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

    FAZ A3 (v2 paritesi): idempotent ve desync-toleranslıdır. Flag kapalıyken
    slotlarda eski yamalarımız duruyorsa (önceki kısmi başarısızlık, ya da
    flag düşürülmüş ama söküm tam yapılmamış durum) bunlar önce kayıtlı
    orig'lere geri alınır, ardından taze kurulum yapılır — ikinci kurulum
    kendi yamasını "orig" olarak yakalayıp çifte normalizasyon üretemez
    (self-capture) ve flag/kurulum ayrışması kalıcılaşamaz. Slotu yabancı
    bir katman devralmışsa (örn. sdl2_overlay'in get_window_size yaması)
    o katmanın üzerine güvenle sarılır; unpatch kimlik guard'ıyla söker.
    """
    if IS_MACOS:
        return

    global _event_patch_active, _orig_event_get
    if _event_patch_active:
        return

    if not hasattr(pygame, 'event') or not hasattr(pygame, 'mouse'):
        return

    # FAZ A3 (v2 paritesi): kısmi kurulum telafisi — kayıtlı slotlarda hâlâ
    # bizim yamamız varsa kayıtlı orig'e geri al. Temiz sökülmüş (slot zaten
    # orig'te) veya yabancı katmana devredilmiş slota dokunma; ikisi de
    # aşağıdaki taze kurulumda güvenle sarılır.
    if _event_patch_installed:
        for _slot_key, _entry in list(_event_patch_installed.items()):
            _holder, _attr, _patched, _orig = _entry
            try:
                if _orig is not None and getattr(_holder, _attr, None) is _patched:
                    setattr(_holder, _attr, _orig)
            except Exception:
                pass
            try:
                del _event_patch_installed[_slot_key]
            except KeyError:
                pass
        try:
            del _slot_key, _entry, _holder, _attr, _patched, _orig
        except NameError:
            pass

    # FAZ A3 (v2 paritesi): bu çağrıda kurulan slotlar — exception durumunda
    # geri alınır; kısmi başarısızlık flag'i kapalı bırakır, desync oluşmaz.
    _installed_this_call: list = []

    def _record(slot_key, holder, attr, patched, orig):
        _event_patch_installed[slot_key] = (holder, attr, patched, orig)
        _installed_this_call.append(slot_key)

    try:
        if pygame.event.get is not _patched_event_get:
            _orig_event_get = pygame.event.get
        pygame.event.get = _patched_event_get
        _record('event_get', pygame.event, 'get', _patched_event_get, _orig_event_get)

        # pygame.mouse.get_pos → virtual canvas koordinatına normalize et
        _orig_mouse_get_pos = pygame.mouse.get_pos

        def _patched_mouse_get_pos():
            try:
                raw = _orig_mouse_get_pos()
                return _normalize_event_pos(raw)
            except Exception:
                return _orig_mouse_get_pos()

        pygame.mouse.get_pos = _patched_mouse_get_pos
        _record('mouse_get_pos', pygame.mouse, 'get_pos', _patched_mouse_get_pos, _orig_mouse_get_pos)

        # pygame.mouse.get_rel → canvas ölçeğine normalize et
        _orig_mouse_get_rel = pygame.mouse.get_rel

        def _patched_mouse_get_rel():
            try:
                raw = _orig_mouse_get_rel()
                return _normalize_event_rel(raw)
            except Exception:
                return _orig_mouse_get_rel()

        pygame.mouse.get_rel = _patched_mouse_get_rel
        _record('mouse_get_rel', pygame.mouse, 'get_rel', _patched_mouse_get_rel, _orig_mouse_get_rel)

        # pygame.mouse.set_pos → canvas koordinatını fiziksel pencere koordinatına geri dönüştür
        _orig_mouse_set_pos = pygame.mouse.set_pos

        def _patched_mouse_set_pos(*args, **kwargs):
            try:
                if len(args) == 2:
                    px, py = denormalize_mouse_pos((args[0], args[1]))
                    return _orig_mouse_set_pos(px, py)
                if len(args) == 1 and isinstance(args[0], (tuple, list)):
                    px, py = denormalize_mouse_pos(args[0])
                    return _orig_mouse_set_pos((px, py))
                return _orig_mouse_set_pos(*args, **kwargs)
            except Exception:
                return _orig_mouse_set_pos(*args, **kwargs)

        pygame.mouse.set_pos = _patched_mouse_set_pos
        _record('mouse_set_pos', pygame.mouse, 'set_pos', _patched_mouse_set_pos, _orig_mouse_set_pos)

        _orig_display_get_window_size = getattr(pygame.display, 'get_window_size', None)
        if _orig_display_get_window_size is not None:
            def _patched_display_get_window_size():
                # get_window_logical_size() BURADAN ÇAĞRILMAZ: o fonksiyon
                # pygame.display.get_window_size'ı — yani bu patch'in kendisini —
                # çağırır; argümansız gwls çağrısı KARŞILIKLI RECURSION üretir
                # (v2 kanıtı K1/K11: 0.44-0.48 ms/çağrı vergisi). Eskiden
                # buradaki sdl2_overlay sorgusu get_presentation_info() dict'iyle
                # çağrı başına tahsis üretiyordu; yoklayıcı
                # (_sdl2_overlay_canvas_size) hem daha ucuz hem v2 ile birebir
                # parite. Boyutu doğrudan çöz:
                try:
                    if _software_scale_active and _software_canvas is not None:
                        return _software_canvas.get_size()
                    sdl2_size = _sdl2_overlay_canvas_size()
                    if sdl2_size is not None:
                        return sdl2_size
                    return _orig_display_get_window_size()
                except Exception:
                    return _orig_display_get_window_size()
            pygame.display.get_window_size = _patched_display_get_window_size
            _record('display_get_window_size', pygame.display, 'get_window_size',
                    _patched_display_get_window_size, _orig_display_get_window_size)

        # Geri alma için referansları sakla
        patch_event_queue._orig_mouse_get_pos = _orig_mouse_get_pos
        patch_event_queue._orig_mouse_get_rel = _orig_mouse_get_rel
        patch_event_queue._orig_mouse_set_pos = _orig_mouse_set_pos
        patch_event_queue._orig_display_get_window_size = _orig_display_get_window_size

        _event_patch_active = True
        print(
            "[Virtual Canvas] Tam mouse patching aktif — "
            "event.get, mouse.get_pos, mouse.get_rel, mouse.set_pos ve display.get_window_size normalize edilecek"
        )
    except Exception as exc:
        # FAZ A3 (v2 paritesi): kısmi başarısızlık — bu çağrıda kurulan
        # slotları kayıtlı orig'lere geri al, kurulum kaydından düşür;
        # flag kapalı kalır.
        for _slot_key in _installed_this_call:
            try:
                _holder, _attr, _patched, _orig = _event_patch_installed[_slot_key]
                if _orig is not None and getattr(_holder, _attr, None) is _patched:
                    setattr(_holder, _attr, _orig)
            except Exception:
                pass
            try:
                del _event_patch_installed[_slot_key]
            except KeyError:
                pass
        print(f"[Virtual Canvas] Event/mouse patch başarısız: {exc}")


def unpatch_event_queue() -> None:
    """Tüm pygame event/mouse monkey-patch'lerini geri al.

    FAZ A3 (v2 paritesi): yalnızca hâlâ bizim yamamızı taşıyan slotlar geri
    alınır (kimlik guard'ı) — slotu yabancı bir katman devraldıysa üzerine
    yazılmaz; o katman sökülürken bizi geri koyar. Kurulum kaydı ve
    legacy _orig_* öznitelikleri temizlenir (get_mouse_pos / raw okuma
    yolu pygame.mouse.get_pos'a döner — sökümden sonra bu zaten ham
    fonksiyondur). Kayıt boşsa ikinci çağrı tam no-op'tur.
    """
    global _event_patch_active
    if not _event_patch_installed and not _event_patch_active:
        # FAZ A3 (v2 paritesi): hızlı yol — kurulum yok (çift unpatch no-op).
        return
    for _slot_key, _entry in list(_event_patch_installed.items()):
        _holder, _attr, _patched, _orig = _entry
        try:
            if _orig is not None and getattr(_holder, _attr, None) is _patched:
                setattr(_holder, _attr, _orig)
        except Exception:
            pass
        try:
            del _event_patch_installed[_slot_key]
        except KeyError:
            pass
    try:
        del patch_event_queue._orig_mouse_get_pos
    except AttributeError:
        pass
    try:
        del patch_event_queue._orig_mouse_get_rel
    except AttributeError:
        pass
    try:
        del patch_event_queue._orig_mouse_set_pos
    except AttributeError:
        pass
    try:
        del patch_event_queue._orig_display_get_window_size
    except AttributeError:
        pass
    _event_patch_active = False


class FocusThrottlePolicy:
    """Merkezi odak kaybı ve düşük güç tüketimi politikası.

    Pencere arka plandayken veya simge durumundayken CPU/GPU kullanımını
    azaltmak için FPS tavanını düşürür; ancak ana döngüyü bloklamaz (time.sleep yok).
    Event kuyruğu, Steam callback'leri ve online networking kesilmeden akar.
    Odak geri kazanıldığında delta_ms sıçramasını sınırlar.
    """

    def __init__(
        self,
        inactive_fps: int = 15,
        debounce_ms: int = 150,
        max_resume_delta_ms: float = 50.0,
    ) -> None:
        self.inactive_fps = max(5, int(inactive_fps))
        self.debounce_ms = max(50, int(debounce_ms))
        self.max_resume_delta_ms = float(max_resume_delta_ms)
        self._is_active = True
        self._inactive_since_ms = 0
        self._was_throttled = False

    def update_active_state(self, is_active: bool, now_ms: int | None = None) -> None:
        """Ekranın aktif/odak durumunu güncelle."""
        if now_ms is None:
            now_ms = pygame.time.get_ticks() if pygame.get_init() else 0

        if is_active:
            self._is_active = True
            self._inactive_since_ms = 0
        else:
            if self._is_active:
                self._is_active = False
                self._inactive_since_ms = now_ms

    def is_throttled(self, state: str = 'menu', now_ms: int | None = None) -> bool:
        """Kısa süreli (transient) odak geçişleri debounce edilerek throttle kararı verilir."""
        if self._is_active:
            return False

        if now_ms is None:
            now_ms = pygame.time.get_ticks() if pygame.get_init() else 0

        if (now_ms - self._inactive_since_ms) < self.debounce_ms:
            return False

        return True

    def resolve_frame_cap(
        self,
        target_fps: int,
        state: str = 'menu',
        now_ms: int | None = None,
    ) -> int:
        """Odak dışındaysa düşük güç FPS tavanı, aktifse hedef FPS döndürür."""
        if self.is_throttled(state=state, now_ms=now_ms):
            self._was_throttled = True
            return self.inactive_fps
        return target_fps

    def filter_delta_ms(self, delta_ms: float) -> float:
        """Odak geri kazanıldığında ilk karede oluşabilecek aşırı delta_ms sıçramasını sınırlar."""
        if self._was_throttled:
            self._was_throttled = False
            return min(float(delta_ms), self.max_resume_delta_ms)
        return float(delta_ms)


_GLOBAL_FOCUS_THROTTLE_POLICY: FocusThrottlePolicy | None = None


def get_focus_throttle_policy() -> FocusThrottlePolicy:
    global _GLOBAL_FOCUS_THROTTLE_POLICY
    if _GLOBAL_FOCUS_THROTTLE_POLICY is None:
        _GLOBAL_FOCUS_THROTTLE_POLICY = FocusThrottlePolicy()
    return _GLOBAL_FOCUS_THROTTLE_POLICY
