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
# main.py bir imleç yüzeyi + hotspot kaydeder; her present'te GPU katmanı olarak çizilir.
_cursor_surface: pygame.Surface | None = None
_cursor_texture = None        # pygame._sdl2.video.Texture — cursor GPU katmanı
_cursor_size = (0, 0)
_cursor_hotspot = (0, 0)
_cursor_enabled = True
_cursor_dirty = False         # cursor surface değişti → texture yeniden oluşturulmalı

# ---------------------------------------------------------------------------
# Performans telemetrisi (opt-in: QUADRIX_OVERLAY_PERF=1)
# ---------------------------------------------------------------------------
# Varsayılan KAPALI (sıfır ek maliyet). Açıkken her present'in alt-fazları ölçülür:
#   - texture.update (CPU→GPU tam yüzey upload)
#   - clear+blit+present (SDL D3D sunum + vsync)
#   - imleç GPU katmanı (blit + gerekiyorsa texture yeniden oluşturma)
# Her _PERF_WINDOW karede bir ZENGİN özet yazılır: FPS, kare süresi yüzdelikleri
# (p50/p95/p99), min/maks, takılma (spike) kovaları, alt-faz ort/maks, imleç metrikleri.
# Ayrıca ANLIK takılmalar (hitch) eşik aşımında hemen ayrı satır olarak loglanır —
# panel geçişi / imleç gecikmesi gibi tek-seferlik spike'ları yakalamak için kritik.
_perf_enabled_cache: bool | None = None
_perf_total = 0                  # toplam kare (oturum)
_perf_frame_times: list = []     # pencere içi kare süreleri (ms) — yüzdelik için
_perf_t_update = 0.0             # pencere içi toplam texture.update (ms)
_perf_t_present = 0.0            # pencere içi toplam present (ms)
_perf_t_cursor = 0.0             # pencere içi toplam imleç blit (ms)
_perf_update_max = 0.0           # pencere içi maks upload (ms)
_perf_present_max = 0.0          # pencere içi maks present (ms)
_perf_cursor_max = 0.0           # pencere içi maks imleç blit (ms)
_perf_cursor_rebuilds = 0        # pencere içi imleç texture yeniden oluşturma sayısı
_perf_last_frame_ts = 0.0        # son present() zaman damgası (perf_counter)
_perf_window_start_ts = 0.0      # pencere başlangıcı (perf_counter)
_perf_screen = 'startup'         # şu anki ekran/state etiketi (main.py set eder)
_perf_session_start_ts = 0.0     # oturum başlangıcı (ilk present)
_perf_hitch_count = 0            # oturum boyu toplam hitch (anlık takılma) sayısı

# Geçiş (transition) ölçümü — panel/ekran geçiş gecikmesini doğrudan ölçer.
_perf_tr_active = False
_perf_tr_label = ''
_perf_tr_start_ts = 0.0
_perf_tr_frames = 0
_perf_tr_worst = 0.0
_perf_tr_first_frame_ms = 0.0    # geçişin İLK karesi (başlangıç stall'ı burada görünür)

# Eşikler (ms). Spike kovaları ve anlık hitch logu için.
_PERF_WINDOW = 600               # kaç karede bir özet (≈60fps'te 10 sn)
_PERF_HITCH_MS = 70.0            # bu süreyi aşan kare ANLIK loglanır (tek-seferlik stall)
_PERF_SPIKE_BUCKETS = (20.0, 33.0, 50.0, 100.0)  # >20ms(<50fps) >33ms(<30fps) >50ms >100ms


def _perf_enabled() -> bool:
    global _perf_enabled_cache
    if _perf_enabled_cache is None:
        raw = os.environ.get('QUADRIX_OVERLAY_PERF')
        _perf_enabled_cache = str(raw or '').strip().lower() in ('1', 'true', 'on', 'yes')
    return _perf_enabled_cache

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
    """Offscreen surface'i GPU texture'a yükleyip SDL renderer ile sun.

    İmleç oyun yüzeyine PİŞİRİLMEZ; ayrı bir GPU texture katmanı olarak oyun
    texture'ından SONRA blend ile çizilir. Böylece statik panellerde imleç izi
    (ghosting) oluşmaz ve her kare temiz, tek-geçişli sunum yapılır.
    """
    if not _active:
        return
    # Hızlı yol: telemetri kapalıyken hiç ek maliyet yok.
    if not _perf_enabled():
        try:
            if _texture is not None and _game_surface is not None:
                _texture.update(_game_surface)
            if _renderer is not None:
                _renderer.clear()
                if _texture is not None:
                    _renderer.blit(_texture, None)  # POZİSYONEL — dst= kwarg yok
                _blit_cursor_layer()
                _renderer.present()
        except Exception as exc:
            _diag_log(f"_present hatası: {exc}")
        return
    _present_with_perf()


def _present_with_perf():
    """_present'in ölçümlü sürümü (QUADRIX_OVERLAY_PERF=1). Alt-fazları zamanlar,
    yüzdelik/spike/hitch verisi toplar."""
    global _perf_total, _perf_t_update, _perf_t_present, _perf_t_cursor
    global _perf_update_max, _perf_present_max, _perf_cursor_max
    global _perf_last_frame_ts, _perf_window_start_ts, _perf_session_start_ts
    global _perf_hitch_count, _perf_tr_frames, _perf_tr_worst, _perf_tr_first_frame_ms
    import time as _t
    now = _t.perf_counter()
    if _perf_session_start_ts == 0.0:
        _perf_session_start_ts = now

    # present()-arası kare süresi (önceki present'ten bu yana = gerçek kare süresi).
    frame_ms = 0.0
    if _perf_last_frame_ts > 0.0:
        frame_ms = (now - _perf_last_frame_ts) * 1000.0
        _perf_frame_times.append(frame_ms)
        # Anlık takılma (hitch): eşik aşan tek kare HEMEN loglanır (spike yakalama).
        if frame_ms >= _PERF_HITCH_MS:
            _perf_hitch_count += 1
            try:
                _diag_log(
                    f"[HITCH] {frame_ms:.1f}ms tek-kare takılma | ekran={_perf_screen} "
                    f"(upload_max={_perf_update_max:.1f} present_max={_perf_present_max:.1f} "
                    f"imleç_max={_perf_cursor_max:.1f})"
                )
            except Exception:
                pass
        # Geçiş ölçümü aktifse kare istatistiğini biriktir.
        if _perf_tr_active:
            _perf_tr_frames += 1
            if _perf_tr_frames == 1:
                _perf_tr_first_frame_ms = frame_ms
            if frame_ms > _perf_tr_worst:
                _perf_tr_worst = frame_ms
    else:
        _perf_window_start_ts = now
    _perf_last_frame_ts = now

    cur_ms = 0.0
    try:
        t0 = _t.perf_counter()
        if _texture is not None and _game_surface is not None:
            _texture.update(_game_surface)
        t1 = _t.perf_counter()
        if _renderer is not None:
            _renderer.clear()
            if _texture is not None:
                _renderer.blit(_texture, None)
            tc0 = _t.perf_counter()
            _blit_cursor_layer()
            tc1 = _t.perf_counter()
            cur_ms = (tc1 - tc0) * 1000.0
            _renderer.present()
        t2 = _t.perf_counter()
        upd_ms = (t1 - t0) * 1000.0
        # present süresi = (t2 - t1) ama içine imleç blit de girer; onu ayır.
        pres_ms = (t2 - t1) * 1000.0 - cur_ms
        if pres_ms < 0.0:
            pres_ms = 0.0
        _perf_t_update += upd_ms
        _perf_t_present += pres_ms
        _perf_t_cursor += cur_ms
        if upd_ms > _perf_update_max:
            _perf_update_max = upd_ms
        if pres_ms > _perf_present_max:
            _perf_present_max = pres_ms
        if cur_ms > _perf_cursor_max:
            _perf_cursor_max = cur_ms
    except Exception as exc:
        _diag_log(f"_present hatası: {exc}")

    _perf_total += 1
    if len(_perf_frame_times) >= _PERF_WINDOW:
        _perf_flush_window(now)


def _percentile(sorted_vals, pct):
    """Sıralı listede yüzdelik (basit en-yakın indeks)."""
    if not sorted_vals:
        return 0.0
    k = int(round((pct / 100.0) * (len(sorted_vals) - 1)))
    k = max(0, min(len(sorted_vals) - 1, k))
    return sorted_vals[k]


def _perf_flush_window(now: float) -> None:
    """Telemetri penceresini ZENGİN özetle ve log'a yaz, sayaçları sıfırla."""
    global _perf_frame_times, _perf_t_update, _perf_t_present, _perf_t_cursor
    global _perf_update_max, _perf_present_max, _perf_cursor_max
    global _perf_cursor_rebuilds, _perf_window_start_ts
    times = _perf_frame_times
    n = len(times)
    if n == 0:
        return
    wall_s = max(1e-6, now - _perf_window_start_ts)
    fps = n / wall_s
    avg_frame = sum(times) / n
    st = sorted(times)
    p50 = _percentile(st, 50)
    p95 = _percentile(st, 95)
    p99 = _percentile(st, 99)
    fmin = st[0]
    fmax = st[-1]
    # Spike kovaları: kaç kare şu eşikleri aştı.
    b = _PERF_SPIKE_BUCKETS
    c20 = sum(1 for x in times if x > b[0])
    c33 = sum(1 for x in times if x > b[1])
    c50 = sum(1 for x in times if x > b[2])
    c100 = sum(1 for x in times if x > b[3])
    avg_update = _perf_t_update / n
    avg_present = _perf_t_present / n
    avg_cursor = _perf_t_cursor / n
    try:
        cur = 'var' if (_cursor_texture is not None and _cursor_enabled) else 'yok'
        _diag_log(
            f"[PERF] ekran={_perf_screen} kare={_perf_total} pencere={n} FPS={fps:.1f} "
            f"kare(ort/p50/p95/p99/min/maks)="
            f"{avg_frame:.1f}/{p50:.1f}/{p95:.1f}/{p99:.1f}/{fmin:.1f}/{fmax:.1f}ms "
            f"spike(>20/>33/>50/>100ms)={c20}/{c33}/{c50}/{c100} "
            f"upload(ort/maks)={avg_update:.2f}/{_perf_update_max:.2f}ms "
            f"present(ort/maks)={avg_present:.2f}/{_perf_present_max:.2f}ms "
            f"imleç(ort/maks)={avg_cursor:.3f}/{_perf_cursor_max:.3f}ms "
            f"imleç_yenileme={_perf_cursor_rebuilds} imleç_durum={cur} "
            f"hitch_toplam={_perf_hitch_count} boyut={_width}x{_height}"
        )
    except Exception:
        pass
    _perf_frame_times = []
    _perf_t_update = 0.0
    _perf_t_present = 0.0
    _perf_t_cursor = 0.0
    _perf_update_max = 0.0
    _perf_present_max = 0.0
    _perf_cursor_max = 0.0
    _perf_cursor_rebuilds = 0
    _perf_window_start_ts = now


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


def log_marker(label: str) -> None:
    """Runtime olay işaretçisi (ekran/state geçişi vb.) gl_debug.log'a yaz.

    main.py state değişimlerinde çağırır; böylece performans penceresi özetleri
    hangi ekranda/ne yaparken üretildiği anlaşılır olur. Yalnızca overlay aktif
    ve telemetri açıkken (QUADRIX_OVERLAY_PERF=1) yazar — aksi halde no-op (gürültü yok).
    """
    if not _active or not _perf_enabled():
        return
    try:
        _diag_log(f"[OLAY] {label}")
    except Exception:
        pass


def set_perf_screen(screen_label: str) -> None:
    """Şu anki ekran/state etiketini ayarla (PERF satırlarında ekran-bazlı kırılım için).

    Ayrıca pencere içi metrikleri o ana kadar biriktirdiğiyle FLUSH eder ki her
    [PERF] satırı tek bir ekrana ait olsun (ekranlar karışmasın). No-op when off.
    """
    global _perf_screen
    if not _active or not _perf_enabled():
        return
    try:
        prev = _perf_screen
        # Ekran değişiminde mevcut pencereyi kapat (veri ekrana net atfedilsin).
        if _perf_frame_times:
            import time as _t
            _perf_flush_window(_t.perf_counter())
        _perf_screen = str(screen_label or '?')
        _diag_log(f"[OLAY] ekran={prev} → {_perf_screen}")
    except Exception:
        pass


def perf_transition_begin(label: str) -> None:
    """Panel/ekran geçişi BAŞLANGICINI işaretle — geçiş süresi/stall'ı ölçmek için.

    Geçiş bitince perf_transition_end() çağrılır; arada geçen süre, kare sayısı,
    ilk-kare stall'ı ve en kötü kare loglanır. Panel geçiş gecikmesini doğrudan ölçer.
    """
    global _perf_tr_active, _perf_tr_label, _perf_tr_start_ts
    global _perf_tr_frames, _perf_tr_worst, _perf_tr_first_frame_ms
    if not _active or not _perf_enabled():
        return
    try:
        import time as _t
        _perf_tr_active = True
        _perf_tr_label = str(label or '?')
        _perf_tr_start_ts = _t.perf_counter()
        _perf_tr_frames = 0
        _perf_tr_worst = 0.0
        _perf_tr_first_frame_ms = 0.0
    except Exception:
        pass


def perf_transition_end() -> None:
    """Panel/ekran geçişi BİTİŞİNİ işaretle ve geçiş özetini logla."""
    global _perf_tr_active
    if not _active or not _perf_enabled() or not _perf_tr_active:
        return
    try:
        import time as _t
        dur_ms = (_t.perf_counter() - _perf_tr_start_ts) * 1000.0
        avg = dur_ms / max(1, _perf_tr_frames)
        _diag_log(
            f"[GECIS] '{_perf_tr_label}' süre={dur_ms:.0f}ms kare={_perf_tr_frames} "
            f"ort_kare={avg:.1f}ms ilk_kare={_perf_tr_first_frame_ms:.1f}ms "
            f"en_kotu_kare={_perf_tr_worst:.1f}ms"
        )
    except Exception:
        pass
    _perf_tr_active = False


def perf_log_event(label: str) -> None:
    """Genel amaçlı olay işaretçisi (Alt+Tab, overlay aç/kapa, ekran görüntüsü vb.).

    Mevcut bir hitch ile ilişkilendirilebilmesi için zaman damgalı satır yazar.
    """
    if not _active or not _perf_enabled():
        return
    try:
        _diag_log(f"[OLAY] {label} (ekran={_perf_screen})")
    except Exception:
        pass


def is_gl_active() -> bool:
    """gl_compat arayüz paritesi: overlay katmanı aktif mi."""
    return _active


def set_software_cursor(surface, hotspot=(0, 0)) -> None:
    """Software imleç yüzeyini kaydet (SDL2 renderer'da donanım imleci görünmez).

    main.py setup_custom_cursor içinde çağırır; her present'te GPU katmanı olarak
    çizilir. surface None ise imleç çizimi devre dışı kalır. Yüzey değişince
    GPU texture bir sonraki present'te yeniden oluşturulur (dirty bayrağı).
    """
    global _cursor_surface, _cursor_hotspot, _cursor_dirty
    _cursor_surface = surface
    _cursor_dirty = True
    try:
        _cursor_hotspot = (int(hotspot[0]), int(hotspot[1]))
    except Exception:
        _cursor_hotspot = (0, 0)


def set_software_cursor_enabled(enabled: bool) -> None:
    """İmleç çizimini aç/kapat (oyun içinde gizlemek için)."""
    global _cursor_enabled
    _cursor_enabled = bool(enabled)


def _ensure_cursor_texture():
    """İmleç GPU texture'ını (gerekirse) oyun yüzeyinden bir kez oluştur.

    Yüzey değişmediği sürece texture yeniden oluşturulmaz; yalnızca konum değişir.
    """
    global _cursor_texture, _cursor_size, _cursor_dirty, _perf_cursor_rebuilds
    if not _cursor_dirty:
        return
    _cursor_dirty = False
    if _perf_enabled():
        _perf_cursor_rebuilds += 1
    # Eski texture'ı serbest bırak.
    try:
        if _cursor_texture is not None and hasattr(_cursor_texture, 'destroy'):
            _cursor_texture.destroy()
    except Exception:
        pass
    _cursor_texture = None
    if _cursor_surface is None or _renderer is None:
        return
    try:
        from pygame._sdl2.video import Texture
        _cursor_texture = Texture.from_surface(_renderer, _cursor_surface)
        _cursor_size = _cursor_surface.get_size()
        # Alpha blend (cursor PNG'si yarı saydam kenarlara sahip).
        try:
            _cursor_texture.blend_mode = 1  # SDL_BLENDMODE_BLEND
        except Exception:
            pass
    except Exception as exc:
        _diag_log(f"_ensure_cursor_texture hatası: {exc}")
        _cursor_texture = None


def _blit_cursor_layer() -> None:
    """İmleç GPU texture'ını mevcut fare konumunda renderer'a çiz (present içinde).

    Oyun texture'ı zaten basıldıktan SONRA çağrılır; imleç yüzeye pişmez → ghosting yok.
    """
    if not _cursor_enabled or _renderer is None:
        return
    try:
        if not pygame.mouse.get_visible():
            return
    except Exception:
        return
    _ensure_cursor_texture()
    if _cursor_texture is None:
        return
    try:
        mx, my = pygame.mouse.get_pos()
        hx, hy = _cursor_hotspot
        cw, ch = _cursor_size
        dst = pygame.Rect(int(mx) - hx, int(my) - hy, cw, ch)
        _renderer.blit(_cursor_texture, dst)
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
    global _active, _window, _renderer, _texture, _game_surface, _cursor_texture, _cursor_dirty
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
    for obj_name in ('_cursor_texture', '_texture', '_renderer', '_window'):
        obj = globals().get(obj_name)
        try:
            if obj is not None and hasattr(obj, 'destroy'):
                obj.destroy()
        except Exception:
            pass
    _cursor_texture = None
    _cursor_dirty = True
    _texture = None
    _renderer = None
    _window = None
    _game_surface = None
