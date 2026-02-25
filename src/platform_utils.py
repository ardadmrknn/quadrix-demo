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
    """Platform-safe blit - macOS'ta BLEND flags'ler crash yapabiliyor.
    
    Args:
        dest: Hedef surface
        src: Kaynak surface
        pos: Pozisyon (tuple veya Rect)
        special_flags: pygame BLEND flags (macOS'ta yok sayılır)
    """
    try:
        if IS_MACOS and special_flags != 0:
            # macOS'ta BLEND flags'ler sorunlu olabilir
            # Basit blit kullan
            dest.blit(src, pos)
        else:
            dest.blit(src, pos, special_flags=special_flags)
    except Exception:
        # Fallback: basit blit
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


def get_native_resolution():
    """Get the native screen resolution from the operating system.

    Returns:
        Tuple[int, int]: (width, height) of the primary monitor.
    """
    try:
        # pygame.display.Info() works before set_mode on most platforms
        info = pygame.display.Info()
        width = info.current_w
        height = info.current_h
        
        # macOS Retina: SDL bazen "points" (logical) döndürür, bazen "pixels" (physical)
        # HIDPI disabled olduğunda logical resolution alırız
        if IS_MACOS:
            # Eğer çözünürlük çok büyükse (physical pixels) logical'a çevir
            # Tipik Retina: 2880x1800 -> 1440x900, 3024x1964 -> 1512x982
            # Gerçek ekran boyutuna göre mantıklı bir değer döndür
            pass  # HIDPI disabled olduğu için zaten logical alıyoruz
        
        # Sanity check: if the values are unreasonable, fall back
        if width > 0 and height > 0:
            return (width, height)
    except Exception:
        pass
    # Fallback to a common resolution
    return (1920, 1080)


def is_fullscreen_toggle(key: int, mods: int, custom_key: int | None = None) -> bool:
    """Return True if a key event should toggle fullscreen.

    - custom_key: Kullanıcının ayarladığı tuş (settings'den gelir)
    - Varsayılan: F12
    - Alternatif: Alt/Option+Enter, macOS'ta Cmd+Enter
    """
    try:
        # Kullanıcının ayarladığı tuş
        if custom_key is not None and key == custom_key:
            return True
        # Varsayılan F12
        if key == pygame.K_F12:
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
        native_w, native_h = get_native_resolution()
        flags = pygame.NOFRAME | pygame.DOUBLEBUF
        if IS_WINDOWS:
            flags |= pygame.HWSURFACE
        try:
            surface = pygame.display.set_mode((native_w, native_h), flags)
            return surface
        except pygame.error:
            pass

    flags = get_display_flags(resizable=(not fullscreen and resizable), fullscreen=fullscreen)
    
    try:
        if fullscreen:
            surface = pygame.display.set_mode((0, 0), flags)
        else:
            surface = pygame.display.set_mode((width, height), flags)
        return surface
    except pygame.error:
        try:
            fallback_flags = pygame.DOUBLEBUF | pygame.RESIZABLE
            if IS_WINDOWS:
                fallback_flags |= pygame.HWSURFACE
            surface = pygame.display.set_mode((width or 800, height or 600), fallback_flags)
            return surface
        except pygame.error:
            return pygame.Surface((width or 800, height or 600))


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
