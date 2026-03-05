"""Platform-specific utilities for cross-platform compatibility.

This module provides helper functions that abstract OS-specific behaviors.
"""

import os
import platform
import subprocess
import sys

import pygame


# Detect macOS at module load time
IS_MACOS = sys.platform == 'darwin'
IS_WINDOWS = sys.platform == 'win32'
IS_LINUX = sys.platform.startswith('linux')

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


def get_max_refresh_rate() -> int:
    """Get the maximum refresh rate of the primary display.
    
    Returns:
        int: The refresh rate in Hz, or 60 as fallback.
    """
    try:
        # SDL2 can provide display mode info
        if hasattr(pygame.display, 'get_num_displays'):
            num = pygame.display.get_num_displays()
            if num > 0 and hasattr(pygame.display, 'get_current_display_mode'):
                mode = pygame.display.get_current_display_mode(0)
                if hasattr(mode, 'refresh_rate') and mode.refresh_rate > 0:
                    return mode.refresh_rate
        return 60
    except Exception:
        return 60


def request_window_focus():
    """Request the window to be brought to the front and focused.
    
    On macOS, applications sometimes start in the background.
    This function attempts to ensure the window gets focus.
    """
    if IS_WINDOWS:
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
            pygame.display.get_active()
            
            # Additional macOS-specific focus request using PyObjC if available
            try:
                from AppKit import NSApplication, NSApp
                app = NSApplication.sharedApplication()
                app.activateIgnoringOtherApps_(True)
            except ImportError:
                # PyObjC not installed, this is optional
                pass
        except Exception:
            # Silently ignore any focus-related errors
            pass


def set_app_icon(assets_dir: str) -> None:
    """Pencere ve görev çubuğu simgesini ayarla.

    - pygame.display.set_icon() ile tüm platformlarda simgeyi günceller.
    - Windows'ta AppUserModelID ile görev çubuğu simgesi ve ismi düzeltilir.
    - macOS'ta AppKit üzerinden Dock simgesini Tetris.icns ile değiştirir.
    """
    import os
    import pygame

    # ── Pygame pencere ikonu (tüm platformlar) — 32x32 standart SDL2 boyutu ──
    # Önce ICO, fallback olarak PNG dene
    _icon_candidates = [
        os.path.join(assets_dir, 'quadrix_icon.ico'),
        os.path.join(assets_dir, 'Tetris_icon.png'),
    ]
    for _icon_file in _icon_candidates:
        if os.path.exists(_icon_file):
            try:
                icon_surf = pygame.image.load(_icon_file).convert_alpha()
                icon_surf = pygame.transform.smoothscale(icon_surf, (32, 32))
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
                hwnd = pygame.display.get_wm_info().get('window', 0)
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
        icns_path = os.path.join(assets_dir, 'Tetris.icns')
        if not os.path.exists(icns_path):
            icns_path = icon_png  # Fallback: PNG kullan
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
    """Return True if a key event should toggle fullscreen.

    - custom_key: Kullanıcının ayarladığı tuş (settings'den gelir)
    - Varsayılan: F10
    - Alternatif: Alt/Option+Enter, macOS'ta Cmd+Enter
    """
    try:
        # Kullanıcının ayarladığı tuş
        if custom_key is not None and key == custom_key:
            return True
        # Varsayılan F10
        if key == pygame.K_F10:
            return True
        # Alt+Enter veya Cmd+Enter (macOS)
        if key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            if mods & pygame.KMOD_ALT:
                return True
            if IS_MACOS and (mods & pygame.KMOD_META):
                return True
        return False
    except Exception:
        return False


def normalize_mouse_pos(pos: tuple[int, int] | list[int] | None) -> tuple[int, int] | None:
    """Normalize mouse coordinates to match the display surface pixel space.

    On macOS (Retina/HiDPI), SDL may report window sizes in "points" while the
    pygame display surface is in physical pixels. This can make mouse movement
    feel offset or scaled incorrectly.

    This helper converts a window-space position (event.pos / pygame.mouse.get_pos)
    into surface-space coordinates.
    """
    if pos is None:
        return None
    try:
        x, y = int(pos[0]), int(pos[1])
    except Exception:
        return None

    try:
        surface = pygame.display.get_surface()
        if surface is None:
            return (x, y)

        surf_w, surf_h = surface.get_size()

        # pygame 2+: window size (logical) can differ from surface size (pixels) on HiDPI.
        if hasattr(pygame.display, 'get_window_size'):
            win_w, win_h = pygame.display.get_window_size()
        else:
            win_w, win_h = (surf_w, surf_h)

        if not win_w or not win_h:
            return (x, y)

        if (surf_w, surf_h) == (win_w, win_h):
            return (x, y)

        scale_x = surf_w / float(win_w)
        scale_y = surf_h / float(win_h)
        return (int(x * scale_x), int(y * scale_y))
    except Exception:
        return (x, y)


def get_mouse_pos() -> tuple[int, int]:
    """Return current mouse position normalized to the display surface."""
    try:
        pos = pygame.mouse.get_pos()
    except Exception:
        return (0, 0)
    return normalize_mouse_pos(pos) or (0, 0)


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


def create_display(
    width: int,
    height: int,
    fullscreen: bool = False,
    resizable: bool = True,
    borderless: bool = False,
):
    """Create a pygame display with platform-appropriate flags."""
    
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
                return surface
        except pygame.error as e:
            print(f"[UYARI] macOS display hatası: {e}")
            try:
                surface = pygame.display.set_mode((width or 800, height or 600), pygame.RESIZABLE)
                return surface
            except pygame.error:
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
        try:
            surface = pygame.display.set_mode((native_w, native_h), flags_bl)
            # Boyut doğrulama: beklenen boyuta ulaşılamadıysa exclusive fullscreen fallback
            actual_w, actual_h = surface.get_size()
            if abs(actual_w - native_w) > 4 or abs(actual_h - native_h) > 4:
                # Borderless başarısız; exclusive fullscreen'e düş
                excl_flags = pygame.FULLSCREEN | pygame.DOUBLEBUF
                surface = pygame.display.set_mode((0, 0), excl_flags)
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
        return surface
    except pygame.error:
        try:
            fallback_flags = pygame.DOUBLEBUF | pygame.RESIZABLE
            surface = pygame.display.set_mode((width or 800, height or 600), fallback_flags)
            return surface
        except pygame.error:
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
