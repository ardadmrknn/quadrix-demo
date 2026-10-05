# -*- coding: utf-8 -*-
"""Linux sistem telemetri toplayıcısı (yerel log; optimizasyon kararları için).

Kullanıcı talebi (2026-10-04): ELF içinde Linux bazında optimizasyon yapmaya
yarayacak her türlü sistem bilgisini (OS, CPU, bellek, GPU, oturum/sürücü,
runtime) toplayan telemetri — veriler YEREL bir log dosyasında tutulur.

İlkeler:
- Salt-okunur ve best-effort: her koleksiyon adımı hata yutar; oyun asla
  bu modül yüzünden düşmez. Yalnız startup'ta BİR KEZ yazılır (per-frame
  tahsis/IO yasağına uygun; oyun döngüsünde maliyeti yoktur).
- Yerellik: log yalnız ``data_paths.get_local_data_dir()`` altına yazılır
  (Auto-Cloud yalnız ``cloud/`` alt dizinini eşzamanlar — bu dosya ASLA
  Steam Cloud'a çıkmaz, kullanıcı makinesinden dışarı gitmez).
- Gizli bilgi güvenliği: env anahtarları BEYAZ LİSTE + QUADRIX_ önekiyle
  filtreli; Steam token'ları, leaderboard client credential'ları ve
  benzeri hassas değerler hiç toplanmaz; son blok yine de hassas env
  değerlerine karşı redaction taramasından geçer.
- Platform disiplini: Linux dışında no-op'tur (Windows/macOS davranışı ve
  log çıktısı değişmez).

Log formatı: okunabilir ``key = value`` satırları, oturum başlıklarıyla
ayrılmış bloklar; dosya 512 KB'ı aşarsa tek kopyaya (``.old``) döndürülür.
Soldier konteynerinde hem konteyner kimliği (``distro_*``) hem host dağıtımı
(``host_distro_*``, ``/run/host/etc/os-release``) kaydedilir.
"""

from __future__ import annotations

import os
import platform
import sys
import time

# Modül-global platform bayrağı — platform_utils deseniyle call-time okunur
# (testler monkeypatch edebilir).
IS_LINUX = sys.platform.startswith('linux')

LOG_FILENAME = 'linux_system_telemetry.log'
_MAX_LOG_BYTES = 512 * 1024
_ROTATED_SUFFIX = '.old'
_MAX_ENV_VALUE_LEN = 160

# Env güvenlik listesi: yalnız bu anahtarlar doğrudan loglanır (değerleriyle).
# Steam/leaderboard credential anahtarları KASITLI olarak listede DEĞİLDİR.
_ENV_WHITELIST = (
    'XDG_SESSION_TYPE',
    'XDG_CURRENT_DESKTOP',
    'XDG_SESSION_DESKTOP',
    'DESKTOP_SESSION',
    'DISPLAY',
    'WAYLAND_DISPLAY',
    'XDG_RUNTIME_DIR',
    'LANG',
    'LC_ALL',
    'SDL_VIDEODRIVER',
    'SDL_AUDIODRIVER',
    'SDL_RENDER_VSYNC',
    'QUADRIX_LINUX_FULLSCREEN_MODE',
)
# QUADRIX_* önekli anahtarlar da toplanır — ama yalnız hassas işaret
# taşımayanlar (gelecekte token benzeri QUADRIX_* eklenirse otomatik elenir).
_QUADRIX_ENV_PREFIX = 'QUADRIX_'
# Steam istemci ortamının VARLIĞI loglanır; değerleri ASLA yazılmaz.
_STEAM_PRESENCE_KEYS = ('SteamAppId', 'SteamClientLaunch', 'SteamPath', 'STEAM_PATH')
# Hassas anahtar işaretleri (alt-dizi eşleşmesi, küçük harf).
_SENSITIVE_KEY_MARKERS = (
    'token', 'secret', 'password', 'passwd', 'credential', 'apikey',
    'api_key', 'private',
)
# Steam Runtime (pressure-vessel/Soldier) konteynerinde /etc/os-release
# Steam Runtime kimliğiyle değiştirilir; host dağıtımının gerçek kimliği
# /run/host altına bağlanmış os-release dosyasındadır.
_HOST_OS_RELEASE_PATH = '/run/host/etc/os-release'

# Süreç başına bir kez yaz (startup zincirinde tek çağrı; force ile yeniden).
_SESSION_WRITTEN = False
_LAST_LOG_PATH: str | None = None


# ── küçük yardımcılar ────────────────────────────────────────────────────────

def _is_sensitive_key(key: str) -> bool:
    k = (key or '').lower()
    return any(marker in k for marker in _SENSITIVE_KEY_MARKERS)


def _read_kv_file(path: str) -> dict[str, str]:
    """``KEY=VALUE`` satırlı dosyayı oku (hata yutar)."""
    out: dict[str, str] = {}
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                k, _, v = line.partition('=')
                out[k.strip()] = v.strip().strip('"')
    except Exception:
        pass
    return out


def _read_os_release_key(key: str) -> str | None:
    try:
        data = _read_kv_file('/etc/os-release')
        val = data.get(key)
        return val if val else None
    except Exception:
        return None


# ── koleksiyon bölümleri (her biri hata yutar) ──────────────────────────────

def _collect_os() -> list[str]:
    lines = [
        f"os = {platform.system()}",
        f"kernel_release = {platform.release()}",
        f"machine = {platform.machine()}",
        f"python_implementation = {platform.python_implementation()}",
    ]
    try:
        u = os.uname()
        lines.append(f"kernel_version = {u.version}")
        lines.append(f"hostname = {u.nodename}")
    except Exception:
        pass
    for key in ('PRETTY_NAME', 'NAME', 'VERSION_ID', 'ID', 'BUILD_ID'):
        val = _read_os_release_key(key)
        if val:
            lines.append(f"distro_{key.lower()} = {val}")
    # Host dağıtımı: konteyner içinde /etc/os-release Steam Runtime kimliğidir;
    # host gerçeği /run/host/etc/os-release'tan host_distro_* olarak okunur.
    # Konteyner dışında dosya yoktur → host_distro_* yazılmaz (o durumda
    # distro_* zaten host'un kendisidir).
    host_data = _read_kv_file(_HOST_OS_RELEASE_PATH)
    if host_data:
        for key in ('PRETTY_NAME', 'NAME', 'VERSION_ID', 'ID', 'BUILD_ID'):
            val = host_data.get(key)
            if val:
                lines.append(f"host_distro_{key.lower()} = {val}")
    return lines


def _parse_proc_cpuinfo() -> dict[str, str]:
    """İlk çekirdek bloğunun anahtar değerleri + toplam işlemci sayısı."""
    first: dict[str, str] = {}
    processor_count = 0
    try:
        with open('/proc/cpuinfo', 'r', encoding='utf-8', errors='replace') as fh:
            in_first_block = True
            for line in fh:
                line = line.strip()
                if not line:
                    in_first_block = False
                    continue
                if ':' not in line:
                    continue
                k, _, v = line.partition(':')
                k = k.strip().lower()
                v = v.strip()
                if k == 'processor':
                    processor_count += 1
                if in_first_block and k not in first and v:
                    first[k] = v
    except Exception:
        pass
    first['processor_count'] = str(processor_count)
    return first


def _collect_cpu() -> list[str]:
    lines: list[str] = []
    try:
        lines.append(f"cpu_count = {os.cpu_count()}")
    except Exception:
        pass
    info = _parse_proc_cpuinfo()
    key_map = {
        'model name': 'cpu_model',
        'processor_count': 'cpu_processor_count',
        'cpu mhz': 'cpu_mhz_current',
        'cache size': 'cpu_cache_size',
        'address sizes': 'cpu_address_sizes',
        'flags': 'cpu_flags',
        'vendor_id': 'cpu_vendor',
    }
    for src, dst in key_map.items():
        val = info.get(src)
        if val:
            lines.append(f"{dst} = {val}")
    # cpufreq politikaları (performans/enerji — optimizasyon kararına girdi).
    try:
        base = '/sys/devices/system/cpu'
        for entry in ('scaling_governor', 'cpuinfo_max_freq', 'cpuinfo_min_freq'):
            path = os.path.join(base, 'cpu0', 'cpufreq', entry)
            try:
                with open(path, 'r', encoding='utf-8', errors='replace') as fh:
                    val = fh.read().strip()
                if val:
                    lines.append(f"cpu0_{entry} = {val}")
            except Exception:
                pass
    except Exception:
        pass
    return lines


def _collect_memory() -> list[str]:
    keys = (
        'MemTotal', 'MemFree', 'MemAvailable', 'Buffers', 'Cached',
        'SwapTotal', 'SwapFree', 'HugePages_Total', 'Hugepagesize',
    )
    lines: list[str] = []
    try:
        with open('/proc/meminfo', 'r', encoding='utf-8', errors='replace') as fh:
            for line in fh:
                if ':' not in line:
                    continue
                k, _, rest = line.partition(':')
                k = k.strip()
                if k in keys:
                    lines.append(f"mem_{k} = {rest.strip()}")
    except Exception:
        pass
    return lines


def _collect_gpu() -> list[str]:
    lines: list[str] = []
    # DRM kartları: PCI vendor:device kimlikleri (driver teşhisi için yeterli).
    try:
        base = '/sys/class/drm'
        for name in sorted(os.listdir(base)):
            if not (name.startswith('card') or name.startswith('renderD')):
                continue
            uevent = _read_kv_file(os.path.join(base, name, 'device', 'uevent'))
            pci_id = uevent.get('PCI_ID')
            if pci_id:
                lines.append(f"drm_{name}_pci = {pci_id}")
            driver = uevent.get('DRIVER')
            if driver:
                lines.append(f"drm_{name}_driver = {driver}")
    except Exception:
        pass
    # /dev/dri düğümleri (donanım erişim olanağı).
    try:
        dri = sorted(os.listdir('/dev/dri'))
        if dri:
            lines.append(f"dri_nodes = {','.join(dri)}")
    except Exception:
        pass
    # lspci (kuruluysa; kısa zaman aşımı — yoksa sessiz atlanır).
    try:
        import subprocess
        completed = subprocess.run(
            ['lspci', '-nn'],
            capture_output=True,
            text=True,
            timeout=2.0,
            check=False,
        )
        for line in (completed.stdout or '').splitlines():
            low = line.lower()
            if 'vga' in low or '3d controller' in low or 'display controller' in low:
                lines.append(f"lspci_gpu = {line.strip()}")
    except Exception:
        pass
    return lines


def _collect_display() -> list[str]:
    """pygame/SDL display gerçekleri — display kurulmuşsa anlamlıdır."""
    lines: list[str] = []
    try:
        import pygame
        if pygame.display.get_init():
            try:
                lines.append(f"sdl_video_driver = {pygame.display.get_driver()}")
            except Exception:
                pass
            try:
                lines.append(f"desktop_sizes = {list(pygame.display.get_desktop_sizes())}")
            except Exception:
                pass
            if hasattr(pygame.display, 'get_num_displays'):
                try:
                    lines.append(f"num_displays = {pygame.display.get_num_displays()}")
                except Exception:
                    pass
            if hasattr(pygame.display, 'is_fullscreen'):
                try:
                    lines.append(f"display_is_fullscreen = {int(bool(pygame.display.is_fullscreen()))}")
                except Exception:
                    pass
            if hasattr(pygame.display, 'get_window_size'):
                try:
                    lines.append(f"window_size = {tuple(pygame.display.get_window_size())}")
                except Exception:
                    pass
            try:
                surf = pygame.display.get_surface()
                if surf is not None:
                    lines.append(f"surface_size = {tuple(surf.get_size())}")
                    lines.append(f"surface_flags = 0x{int(surf.get_flags()):X}")
            except Exception:
                pass
            if hasattr(pygame.display, 'get_current_refresh_rate'):
                try:
                    lines.append(f"current_refresh_rate = {pygame.display.get_current_refresh_rate()}")
                except Exception:
                    pass
            if hasattr(pygame.display, 'get_desktop_refresh_rates'):
                try:
                    lines.append(f"desktop_refresh_rates = {list(pygame.display.get_desktop_refresh_rates())}")
                except Exception:
                    pass
            try:
                lines.append(f"sdl_version = {pygame.get_sdl_version()}")
            except Exception:
                pass
            try:
                lines.append(f"pygame_version = {pygame.version.ver}")
            except Exception:
                pass
            # Seçilen Linux fullscreen modu (platform_utils durum sinyali).
            try:
                pu = sys.modules.get('platform_utils') or sys.modules.get('src.platform_utils')
                if pu is None:
                    try:
                        import platform_utils as pu  # type: ignore[no-redef]
                    except Exception:
                        pu = None
                getter = getattr(pu, 'get_linux_display_selected_mode', None) if pu else None
                if callable(getter):
                    mode = getter()
                    if mode:
                        lines.append(f"fullscreen_selected_mode = {mode}")
            except Exception:
                pass
    except Exception:
        pass
    return lines


def _collect_runtime() -> list[str]:
    lines = [
        f"python = {sys.version.split()[0]}",
        f"python_executable = {sys.executable}",
        f"frozen = {int(bool(getattr(sys, 'frozen', False)))}",
    ]
    if hasattr(sys, '_MEIPASS'):
        lines.append("pyinstaller_onefile = 1")
    try:
        import version  # type: ignore[import-not-found]
        lines.append(f"game_version = {version.VERSION}")
        lines.append(f"game_build = {version.BUILD_NUMBER}")
        lines.append(f"version_source = {version.VERSION_SOURCE}")
    except Exception:
        pass
    return lines


def _collect_env() -> list[str]:
    lines: list[str] = []
    for key in _ENV_WHITELIST:
        val = os.environ.get(key)
        if val is not None:
            lines.append(f"env_{key} = {val[:_MAX_ENV_VALUE_LEN]}")
    for key in sorted(os.environ.keys()):
        if key in _ENV_WHITELIST or not key.startswith(_QUADRIX_ENV_PREFIX):
            continue
        if _is_sensitive_key(key):
            continue
        val = os.environ.get(key, '')
        lines.append(f"env_{key} = {val[:_MAX_ENV_VALUE_LEN]}")
    # Steam istemci ortamı: yalnız VARLIK (değer değil — gizli bilgi güvenliği).
    for key in _STEAM_PRESENCE_KEYS:
        if key in os.environ:
            lines.append(f"env_present_{key} = 1")
    return lines


def _collect_storage(data_dir: str) -> list[str]:
    lines: list[str] = []
    try:
        st = os.statvfs(data_dir)
        total_mb = (st.f_blocks * st.f_frsize) // (1024 * 1024)
        free_mb = (st.f_bavail * st.f_frsize) // (1024 * 1024)
        lines.append(f"data_fs_total_mb = {total_mb}")
        lines.append(f"data_fs_free_mb = {free_mb}")
    except Exception:
        pass
    return lines


# ── güvenlik: son blok redaction taraması ───────────────────────────────────

def _redact_sensitive_values(text: str) -> str:
    """Toplanmayan hassas env değerleri metne sızmışsa maskeli geri dön.

    Savunma derinliği: beyaz liste zaten credential anahtarlarını toplamaz;
    bu tarama, aynı değerin başka bir alan üzerinden (ör. hostname) sızma
    ihtimaline karşı son bariyerdir.
    """
    try:
        for key, val in list(os.environ.items()):
            if not val or len(val) < 8:
                continue
            upper = key.upper()
            if (
                _is_sensitive_key(key)
                or upper.startswith(('LEADERBOARD_', 'STEAM_'))
                or key in _STEAM_PRESENCE_KEYS
            ) and val in text:
                text = text.replace(val, '<REDACTED>')
    except Exception:
        pass
    return text


# ── yazma tarafı ─────────────────────────────────────────────────────────────

def _resolve_data_dir() -> str | None:
    """Yerel veri dizini (cloud DEĞİL). Testler bu fonksiyonu patch'ler."""
    try:
        from data_paths import get_local_data_dir
        return get_local_data_dir()
    except Exception:
        try:
            from src.data_paths import get_local_data_dir  # type: ignore[no-redef]
            return get_local_data_dir()
        except Exception:
            return None


def _rotate_if_needed(log_path: str) -> None:
    try:
        if os.path.exists(log_path) and os.path.getsize(log_path) > _MAX_LOG_BYTES:
            rotated = log_path + _ROTATED_SUFFIX
            try:
                os.remove(rotated)
            except OSError:
                pass
            os.replace(log_path, rotated)
    except Exception:
        pass


def _safe_section(title: str, collector) -> tuple[str, list[str]]:
    """Tek bölüm çökerse boş döner — best-effort sözleşmesi blok seviyesinde."""
    try:
        return (title, collector() or [])
    except Exception:
        return (title, [])


def _build_block(data_dir: str | None) -> str:
    ts = time.strftime('%Y-%m-%dT%H:%M:%S', time.gmtime()) + 'Z'
    sections: list[tuple[str, list[str]]] = [
        _safe_section('OS', _collect_os),
        _safe_section('CPU', _collect_cpu),
        _safe_section('MEMORY', _collect_memory),
        _safe_section('GPU', _collect_gpu),
        _safe_section('DISPLAY', _collect_display),
        _safe_section('RUNTIME', _collect_runtime),
        _safe_section('ENV', _collect_env),
        _safe_section('STORAGE', lambda: _collect_storage(data_dir) if data_dir else []),
    ]
    out = [f"===== QUADRIX LINUX SYSTEM TELEMETRY {ts} ====="]
    for title, lines in sections:
        if not lines:
            continue
        out.append(f"--- {title} ---")
        out.extend(lines)
    out.append('')
    return _redact_sensitive_values('\n'.join(out)) + '\n'


def _diag_pointer(log_path: str) -> None:
    """gl_debug.log'a tek satır işaret koy (best-effort; ayrı kanal bozulsa da oyun etkilenmez)."""
    try:
        pu = sys.modules.get('platform_utils') or sys.modules.get('src.platform_utils')
        if pu is None:
            try:
                import platform_utils as pu  # type: ignore[no-redef]
            except Exception:
                return
        diag = getattr(pu, '_gl_diag', None)
        if callable(diag):
            diag(f"linux_system_telemetry: yerel sistem logu yazıldı ({log_path})")
    except Exception:
        pass


def collect_and_log_startup(force: bool = False) -> str | None:
    """Startup Linux sistem telemetrisini topla ve YEREL log dosyasına yaz.

    Non-Linux platformlarda no-op'tur (dönüş None). Yalnız ``local/`` veri
    dizinine yazar — Auto-Cloud ``cloud/`` alt dizinini eşzamanlar, bu dosya
    asla buluta çıkmaz. Süreç başına bir kez yazılır; ``force=True`` ile
    yeniden yazılabilir. Hata yutar; yazılamadıysa None döner.

    Returns:
        Yazılan log dosyasının tam yolu ya da None (yazılmadı).
    """
    global _SESSION_WRITTEN, _LAST_LOG_PATH
    if not IS_LINUX:
        return None
    if _SESSION_WRITTEN and not force:
        return _LAST_LOG_PATH
    data_dir = _resolve_data_dir()
    if not data_dir:
        return None
    log_path = os.path.join(data_dir, LOG_FILENAME)
    try:
        _rotate_if_needed(log_path)
        block = _build_block(data_dir)
        with open(log_path, 'a', encoding='utf-8') as fh:
            fh.write(block)
        _SESSION_WRITTEN = True
        _LAST_LOG_PATH = log_path
        _diag_pointer(log_path)
        return log_path
    except Exception:
        return None
