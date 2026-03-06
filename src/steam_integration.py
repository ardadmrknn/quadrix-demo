"""Steam SDK entegrasyonu (ctypes tabanlı, çok platformlu, graceful fallback).

Steamworks SDK flat API'sini ctypes üzerinden kullanır.
  Windows  : steam_api64.dll
  macOS    : libsteam_api.dylib
  Linux    : libsteam_api.so

- SteamAPI_Init() başarısız olursa veya kütüphane bulunamazsa tüm fonksiyonlar
  güvenli biçimde None/False döndürür (oyun çalışmaya devam eder).
- Steam'den bağımsız başlatmalar için is_available() kontrol edilir.
"""

from __future__ import annotations

import atexit
import ctypes
import ctypes.util
import os
import sys
import threading
import time
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# DLL yükleyici
# ---------------------------------------------------------------------------

_dll: ctypes.CDLL | None = None
_dll_loaded = False
_init_ok = False
_init_lock = threading.Lock()

# Interface pointer'ları (init sonrası doldurulur)
_isteam_friends: ctypes.c_void_p | None = None
_isteam_user: ctypes.c_void_p | None = None
_isteam_user_stats: ctypes.c_void_p | None = None
_isteam_utils: ctypes.c_void_p | None = None
_isteam_apps: ctypes.c_void_p | None = None

# Önbellek
_persona_name_cache: str | None = None
_steam_id_cache: int | None = None
_avatar_rgba_cache: dict[tuple[int, str], tuple[int, int, bytes]] = {}

# Leaderboard handle cache: leaderboard_name -> SteamLeaderboard_t (uint64)
_lb_handle_cache: dict[str, int] = {}

# Bekleyen skor gönderimi kuyruğu: (mode, score) listeleri
_pending_scores: list[tuple[str, int]] = []
_score_lock = threading.Lock()

# Callback pump thread
_pump_thread: threading.Thread | None = None
_pump_running = False
_pump_paused = False  # Online PvP bridge aktifken True — Race condition önleme
_pump_pause_count = 0  # Ref-count: nested pause/resume için (0 = resumed)
_pump_paused_event = threading.Event()  # pump döngüsü bu event'i set eder (pause ack)
_pump_lock = threading.Lock()  # RunCallbacks çakmasını önle


def _read_app_id_from_runtime_sources(default: str = '4428040') -> str:
    candidates: list[Path] = []

    env_app_id = str(os.environ.get('STEAM_APP_ID', '') or '').strip()
    if env_app_id:
        return env_app_id

    try:
        candidates.append(Path.cwd() / 'steam_appid.txt')
    except Exception:
        pass

    try:
        exe_path = Path(getattr(sys, 'executable', '') or '')
        if exe_path:
            candidates.append(exe_path.resolve().parent / 'steam_appid.txt')
    except Exception:
        pass

    try:
        if getattr(sys, '_MEIPASS', None):
            candidates.append(Path(sys._MEIPASS) / 'steam_appid.txt')
    except Exception:
        pass

    try:
        project_root = Path(__file__).resolve().parent.parent
        candidates.append(project_root / 'steam_appid.txt')
    except Exception:
        pass

    seen: set[str] = set()
    for candidate in candidates:
        try:
            key = str(candidate.resolve())
        except Exception:
            key = str(candidate)
        if key in seen:
            continue
        seen.add(key)
        try:
            if candidate.exists():
                raw = candidate.read_text(encoding='utf-8').strip()
                if raw:
                    return raw
        except Exception:
            continue

    return default


def _get_platform_lib_name() -> str:
    """Platforma göre Steam kütüphane dosya adını döndür."""
    if sys.platform == 'darwin':
        return 'libsteam_api.dylib'
    elif sys.platform.startswith('linux'):
        return 'libsteam_api.so'
    else:  # Windows
        return 'steam_api64.dll'


def _find_dll() -> str | None:
    """Platforma uygun Steam kütüphanesini bul."""
    lib_name = _get_platform_lib_name()
    candidates: list[str] = []

    # 1. PyInstaller bundle
    if getattr(sys, '_MEIPASS', None):
        candidates.append(str(Path(sys._MEIPASS) / lib_name))

    # 2. Çalışma dizini
    candidates.append(str(Path.cwd() / lib_name))

    # 3. Bu dosyanın bulunduğu klasörün üstü (proje kökü)
    proj_root = Path(__file__).resolve().parent.parent
    candidates.append(str(proj_root / lib_name))

    # 4. Proje içi dll/ alt klasörü (kaynak ağacındaki konum)
    if sys.platform == 'darwin':
        candidates.append(str(proj_root / 'dll' / 'osx' / lib_name))
    elif sys.platform.startswith('linux'):
        candidates.append(str(proj_root / 'dll' / 'linux64' / lib_name))
    else:
        candidates.append(str(proj_root / 'dll' / 'win64' / lib_name))

    # 5. dist/ klasörü
    candidates.append(str(proj_root / 'dist' / lib_name))

    # 5b. macOS .app bundle — Contents/MacOS/ (COLLECT mode)
    if sys.platform == 'darwin' and getattr(sys, 'frozen', False):
        # PyInstaller COLLECT mode: executable is at .app/Contents/MacOS/Quadrix
        _exe_dir = Path(getattr(sys, 'executable', '')).resolve().parent
        candidates.append(str(_exe_dir / lib_name))
        # Also check one level up from _MEIPASS (Frameworks dir in some bundles)
        if getattr(sys, '_MEIPASS', None):
            _meipass = Path(sys._MEIPASS)
            candidates.append(str(_meipass.parent / 'Frameworks' / lib_name))

    # 6. Platform'a özel ek konumlar
    if sys.platform == 'darwin':
        # macOS: Steam uygulama klasörü ve olası framework yolları
        mac_dirs = [
            Path.home() / 'Library/Application Support/Steam',
            Path('/Applications/Steam.app/Contents/MacOS'),
            Path('/usr/local/lib'),
        ]
        for d in mac_dirs:
            candidates.append(str(d / lib_name))
    elif sys.platform.startswith('linux'):
        linux_dirs = [
            Path.home() / '.steam/steam',
            Path.home() / '.local/share/Steam',
            Path('/usr/lib'),
            Path('/usr/lib/x86_64-linux-gnu'),
        ]
        for d in linux_dirs:
            candidates.append(str(d / lib_name))
    else:
        # Windows
        win_dirs = [
            Path(r'C:\Program Files (x86)\Steam'),
            Path(r'C:\Program Files\Steam'),
        ]
        for d in win_dirs:
            candidates.append(str(d / lib_name))

    for c in candidates:
        if os.path.isfile(c):
            return c
    return None


def _setup_dll_functions(dll: ctypes.CDLL) -> None:
    """DLL fonksiyon imzalarını tanımla."""
    # SteamAPI_InitFlat — SDK 1.60+ flat API (tercih edilen)
    # ESteamAPIInitResult döndürür: 0=OK, diğerleri=hata
    try:
        _errmsg_buf_type = ctypes.c_char * 1024
        dll.SteamAPI_InitFlat.restype = ctypes.c_int   # ESteamAPIInitResult
        dll.SteamAPI_InitFlat.argtypes = [ctypes.c_char_p]  # SteamErrMsg* (NULL geçilebilir)
        dll._quadrix_has_init_flat = True
    except AttributeError:
        dll._quadrix_has_init_flat = False

    # SteamAPI_Init — SDK 1.59 ve öncesi (bool döndürür: 1=OK)
    try:
        dll.SteamAPI_Init.restype = ctypes.c_int  # bool ama c_int olarak oku
        dll.SteamAPI_Init.argtypes = []
        dll._quadrix_has_init_legacy = True
    except AttributeError:
        dll._quadrix_has_init_legacy = False

    # SteamAPI_Shutdown()
    try:
        dll.SteamAPI_Shutdown.restype = None
        dll.SteamAPI_Shutdown.argtypes = []
    except AttributeError:
        pass

    # SteamAPI_RunCallbacks()
    try:
        dll.SteamAPI_RunCallbacks.restype = None
        dll.SteamAPI_RunCallbacks.argtypes = []
    except AttributeError:
        pass

    # Interface accessors (flat API)
    try:
        dll.SteamAPI_SteamFriends_v017.restype = ctypes.c_void_p
        dll.SteamAPI_SteamFriends_v017.argtypes = []
    except AttributeError:
        pass

    try:
        dll.SteamAPI_SteamUser_v023.restype = ctypes.c_void_p
        dll.SteamAPI_SteamUser_v023.argtypes = []
    except AttributeError:
        pass

    try:
        dll.SteamAPI_SteamUserStats_v012.restype = ctypes.c_void_p
        dll.SteamAPI_SteamUserStats_v012.argtypes = []
    except AttributeError:
        pass

    # ISteamFriends_GetPersonaName
    try:
        dll.SteamAPI_ISteamFriends_GetPersonaName.restype = ctypes.c_char_p
        dll.SteamAPI_ISteamFriends_GetPersonaName.argtypes = [ctypes.c_void_p]
    except AttributeError:
        pass

    # ISteamFriends_Get*FriendAvatar -> int image_handle (-1 loading, 0 no avatar)
    try:
        dll.SteamAPI_ISteamFriends_GetLargeFriendAvatar.restype = ctypes.c_int
        dll.SteamAPI_ISteamFriends_GetLargeFriendAvatar.argtypes = [ctypes.c_void_p, ctypes.c_uint64]
    except AttributeError:
        pass
    try:
        dll.SteamAPI_ISteamFriends_GetMediumFriendAvatar.restype = ctypes.c_int
        dll.SteamAPI_ISteamFriends_GetMediumFriendAvatar.argtypes = [ctypes.c_void_p, ctypes.c_uint64]
    except AttributeError:
        pass
    try:
        dll.SteamAPI_ISteamFriends_GetSmallFriendAvatar.restype = ctypes.c_int
        dll.SteamAPI_ISteamFriends_GetSmallFriendAvatar.argtypes = [ctypes.c_void_p, ctypes.c_uint64]
    except AttributeError:
        pass

    # ISteamUtils image helpers
    try:
        dll.SteamAPI_ISteamUtils_GetImageSize.restype = ctypes.c_bool
        dll.SteamAPI_ISteamUtils_GetImageSize.argtypes = [
            ctypes.c_void_p,
            ctypes.c_int,
            ctypes.POINTER(ctypes.c_uint32),
            ctypes.POINTER(ctypes.c_uint32),
        ]
    except AttributeError:
        pass
    try:
        dll.SteamAPI_ISteamUtils_GetImageRGBA.restype = ctypes.c_bool
        dll.SteamAPI_ISteamUtils_GetImageRGBA.argtypes = [
            ctypes.c_void_p,
            ctypes.c_int,
            ctypes.POINTER(ctypes.c_uint8),
            ctypes.c_int,
        ]
    except AttributeError:
        pass

    # ISteamUser_GetSteamID returns uint64 in low/high regs; use c_uint64
    try:
        dll.SteamAPI_ISteamUser_GetSteamID.restype = ctypes.c_uint64
        dll.SteamAPI_ISteamUser_GetSteamID.argtypes = [ctypes.c_void_p]
    except AttributeError:
        pass

    # ISteamFriends_ActivateGameOverlay — Steam overlay paneli açma (Windows için kritik)
    try:
        dll.SteamAPI_ISteamFriends_ActivateGameOverlay.restype = None
        dll.SteamAPI_ISteamFriends_ActivateGameOverlay.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
    except AttributeError:
        pass

    # ISteamFriends_ActivateGameOverlayToUser — belirli kullanıcıya overlay açma
    try:
        dll.SteamAPI_ISteamFriends_ActivateGameOverlayToUser.restype = None
        dll.SteamAPI_ISteamFriends_ActivateGameOverlayToUser.argtypes = [
            ctypes.c_void_p, ctypes.c_char_p, ctypes.c_uint64]
    except AttributeError:
        pass

    # ISteamFriends_ActivateGameOverlayInviteDialog — davet penceresi açma
    try:
        dll.SteamAPI_ISteamFriends_ActivateGameOverlayInviteDialog.restype = None
        dll.SteamAPI_ISteamFriends_ActivateGameOverlayInviteDialog.argtypes = [
            ctypes.c_void_p, ctypes.c_uint64]
    except AttributeError:
        pass

    # ISteamUserStats_FindLeaderboard -> SteamAPICall_t (uint64)
    try:
        dll.SteamAPI_ISteamUserStats_FindLeaderboard.restype = ctypes.c_uint64
        dll.SteamAPI_ISteamUserStats_FindLeaderboard.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
    except AttributeError:
        pass

    # ISteamUserStats_UploadLeaderboardScore -> SteamAPICall_t (uint64)
    # eLeaderboardUploadScoreMethod: 0 = KeepBest, 1 = ForceUpdate
    try:
        dll.SteamAPI_ISteamUserStats_UploadLeaderboardScore.restype = ctypes.c_uint64
        dll.SteamAPI_ISteamUserStats_UploadLeaderboardScore.argtypes = [
            ctypes.c_void_p,  # ISteamUserStats*
            ctypes.c_uint64,  # SteamLeaderboard_t
            ctypes.c_int,     # eLeaderboardUploadScoreMethod
            ctypes.c_int32,   # nScore
            ctypes.c_void_p,  # pScoreDetails (NULL)
            ctypes.c_int,     # cScoreDetailsCount (0)
        ]
    except AttributeError:
        pass

    # ISteamUserStats_GetLeaderboardName (handle -> name)
    try:
        dll.SteamAPI_ISteamUserStats_GetLeaderboardName.restype = ctypes.c_char_p
        dll.SteamAPI_ISteamUserStats_GetLeaderboardName.argtypes = [ctypes.c_void_p, ctypes.c_uint64]
    except AttributeError:
        pass

    # ISteamUserStats_DownloadLeaderboardEntries -> SteamAPICall_t
    try:
        dll.SteamAPI_ISteamUserStats_DownloadLeaderboardEntries.restype = ctypes.c_uint64
        dll.SteamAPI_ISteamUserStats_DownloadLeaderboardEntries.argtypes = [
            ctypes.c_void_p,
            ctypes.c_uint64,   # SteamLeaderboard_t
            ctypes.c_int,      # ELeaderboardDataRequest
            ctypes.c_int,      # rangeStart
            ctypes.c_int,      # rangeEnd
        ]
    except AttributeError:
        pass

    # ISteamUser_GetAuthSessionTicket
    try:
        dll.SteamAPI_ISteamUser_GetAuthSessionTicket.restype = ctypes.c_uint32  # HAuthTicket
        dll.SteamAPI_ISteamUser_GetAuthSessionTicket.argtypes = [
            ctypes.c_void_p,   # ISteamUser*
            ctypes.c_void_p,   # pTicket buffer
            ctypes.c_int,      # cbMaxTicket
            ctypes.POINTER(ctypes.c_uint32),  # pcbTicket out
            ctypes.c_void_p,   # pSteamNetworkingIdentity (NULL)
        ]
    except AttributeError:
        pass

    # ISteamUtils interface accessors
    for _utils_ver in ('SteamAPI_SteamUtils_v010', 'SteamAPI_SteamUtils_v009'):
        try:
            fn = getattr(dll, _utils_ver)
            fn.restype = ctypes.c_void_p
            fn.argtypes = []
        except AttributeError:
            pass

    # ISteamUtils_GetAPICallResult — callback sonucunu polling ile almak için
    try:
        dll.SteamAPI_ISteamUtils_GetAPICallResult.restype = ctypes.c_bool
        dll.SteamAPI_ISteamUtils_GetAPICallResult.argtypes = [
            ctypes.c_void_p,              # ISteamUtils*
            ctypes.c_uint64,              # SteamAPICall_t
            ctypes.c_void_p,              # pCallback (out)
            ctypes.c_int,                 # cubCallback
            ctypes.c_int,                 # iCallbackExpected
            ctypes.POINTER(ctypes.c_bool),# pbFailed
        ]
    except AttributeError:
        pass

    # ISteamUtils_IsAPICallCompleted — çağrı tamamlandı mı?
    try:
        dll.SteamAPI_ISteamUtils_IsAPICallCompleted.restype = ctypes.c_bool
        dll.SteamAPI_ISteamUtils_IsAPICallCompleted.argtypes = [
            ctypes.c_void_p,              # ISteamUtils*
            ctypes.c_uint64,              # SteamAPICall_t
            ctypes.POINTER(ctypes.c_bool),# pbFailed
        ]
    except AttributeError:
        pass

    # ISteamUserStats_RequestCurrentStats — UserStats işlemleri için zorunlu
    try:
        dll.SteamAPI_ISteamUserStats_RequestCurrentStats.restype = ctypes.c_bool
        dll.SteamAPI_ISteamUserStats_RequestCurrentStats.argtypes = [ctypes.c_void_p]
    except AttributeError:
        pass

    # ISteamUserStats_SetAchievement — Başarım kilidini aç
    try:
        dll.SteamAPI_ISteamUserStats_SetAchievement.restype = ctypes.c_bool
        dll.SteamAPI_ISteamUserStats_SetAchievement.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
    except AttributeError:
        pass

    # ISteamUserStats_GetAchievement — Başarım durumunu sorgula
    try:
        dll.SteamAPI_ISteamUserStats_GetAchievement.restype = ctypes.c_bool
        dll.SteamAPI_ISteamUserStats_GetAchievement.argtypes = [
            ctypes.c_void_p,               # ISteamUserStats*
            ctypes.c_char_p,               # pchName
            ctypes.POINTER(ctypes.c_bool),  # pbAchieved (out)
        ]
    except AttributeError:
        pass

    # ISteamUserStats_StoreStats — Başarım/stat değişikliklerini Steam'e yaz
    try:
        dll.SteamAPI_ISteamUserStats_StoreStats.restype = ctypes.c_bool
        dll.SteamAPI_ISteamUserStats_StoreStats.argtypes = [ctypes.c_void_p]
    except AttributeError:
        pass

    # ISteamUserStats_ClearAchievement — Başarım kilidini geri al (test/geliştirme)
    try:
        dll.SteamAPI_ISteamUserStats_ClearAchievement.restype = ctypes.c_bool
        dll.SteamAPI_ISteamUserStats_ClearAchievement.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
    except AttributeError:
        pass

    # ISteamUserStats_IndicateAchievementProgress — İlerleme bildirimi göster
    try:
        dll.SteamAPI_ISteamUserStats_IndicateAchievementProgress.restype = ctypes.c_bool
        dll.SteamAPI_ISteamUserStats_IndicateAchievementProgress.argtypes = [
            ctypes.c_void_p,   # ISteamUserStats*
            ctypes.c_char_p,   # pchName
            ctypes.c_uint32,   # nCurProgress
            ctypes.c_uint32,   # nMaxProgress
        ]
    except AttributeError:
        pass

    # ISteamUserStats_SetStat (INT32) — İstatistik değeri yaz
    try:
        dll.SteamAPI_ISteamUserStats_SetStatInt32.restype = ctypes.c_bool
        dll.SteamAPI_ISteamUserStats_SetStatInt32.argtypes = [
            ctypes.c_void_p,   # ISteamUserStats*
            ctypes.c_char_p,   # pchName
            ctypes.c_int32,    # nData
        ]
    except AttributeError:
        pass

    # ISteamUserStats_SetStat (FLOAT) — İstatistik değeri yaz (float)
    try:
        dll.SteamAPI_ISteamUserStats_SetStatFloat.restype = ctypes.c_bool
        dll.SteamAPI_ISteamUserStats_SetStatFloat.argtypes = [
            ctypes.c_void_p,   # ISteamUserStats*
            ctypes.c_char_p,   # pchName
            ctypes.c_float,    # fData
        ]
    except AttributeError:
        pass

    # ISteamUserStats_GetStat (INT32) — İstatistik değeri oku
    try:
        dll.SteamAPI_ISteamUserStats_GetStatInt32.restype = ctypes.c_bool
        dll.SteamAPI_ISteamUserStats_GetStatInt32.argtypes = [
            ctypes.c_void_p,              # ISteamUserStats*
            ctypes.c_char_p,              # pchName
            ctypes.POINTER(ctypes.c_int32),  # pData (out)
        ]
    except AttributeError:
        pass

    # ISteamUserStats_GetStat (FLOAT) — İstatistik değeri oku (float)
    try:
        dll.SteamAPI_ISteamUserStats_GetStatFloat.restype = ctypes.c_bool
        dll.SteamAPI_ISteamUserStats_GetStatFloat.argtypes = [
            ctypes.c_void_p,              # ISteamUserStats*
            ctypes.c_char_p,              # pchName
            ctypes.POINTER(ctypes.c_float),  # pData (out)
        ]
    except AttributeError:
        pass

    # ISteamUserStats_ResetAllStats — Tüm istatistikleri sıfırla (test/geliştirme)
    try:
        dll.SteamAPI_ISteamUserStats_ResetAllStats.restype = ctypes.c_bool
        dll.SteamAPI_ISteamUserStats_ResetAllStats.argtypes = [
            ctypes.c_void_p,   # ISteamUserStats*
            ctypes.c_bool,     # bAchievementsToo
        ]
    except AttributeError:
        pass

    # SteamApps interface accessor (v008 veya v007)
    for _apps_ver in ('SteamAPI_SteamApps_v008', 'SteamAPI_SteamApps_v007'):
        try:
            fn = getattr(dll, _apps_ver)
            fn.restype = ctypes.c_void_p
            fn.argtypes = []
        except AttributeError:
            pass

    # ISteamApps_BIsSubscribed — aktif hesabın AppID lisansı var mı?
    try:
        dll.SteamAPI_ISteamApps_BIsSubscribed.restype = ctypes.c_bool
        dll.SteamAPI_ISteamApps_BIsSubscribed.argtypes = [ctypes.c_void_p]
    except AttributeError:
        pass


def init() -> bool:
    """Steam API'yi başlat. Başarılı olursa True döndürür.

    İkinci çağrıda mevcut durumu döndürür (idempotent).
    """
    global _dll, _dll_loaded, _init_ok, _isteam_friends, _isteam_user, _isteam_user_stats, _isteam_utils
    global _isteam_apps, _pump_thread, _pump_running

    with _init_lock:
        if _dll_loaded:
            return _init_ok

        _dll_loaded = True

        # ── Steam AppID env var — onefile PyInstaller için zorunlu ──────────────
        # SteamAPI_Init, steam_appid.txt dosyasını ya CWD'den ya da SteamAppId
        # env var‧ından okur. Onefile build'larda _MEIPASS geçici klasörüne
        # çıkarılır ama CWD exe'nin bulunduğu yerdir — dosya orada olmayabilir.
        # Env var her zaman çalışır.
        _APP_ID = _read_app_id_from_runtime_sources('4428040')
        # ── Dev mode / Production mode ayırt et ─────────────────────────────────
        # PyInstaller frozen build'da (sys.frozen=True) Steam client AppID'yi
        # zaten sağlar; env override yapmak yanlış AppID enjekte edebilir.
        # Dev modda (script çalıştırma) ya da STEAM_DEV_OVERRIDE=1 olduğunda
        # override yapılır.
        _is_dev_mode = (
            not getattr(sys, 'frozen', False)
            or os.environ.get('STEAM_DEV_OVERRIDE', '0') == '1'
        )
        if _is_dev_mode:
            os.environ.setdefault('SteamAppId', _APP_ID)
            os.environ.setdefault('SteamGameId', _APP_ID)
            # steam_appid.txt'yi exe'nin yanına da yazmaya çalış (Steam offline launch için)
            try:
                import sys as _sys
                _exe_dir = Path(getattr(_sys, 'executable', '') or '').parent
                _appid_dst = _exe_dir / 'steam_appid.txt'
                if not _appid_dst.exists():
                    _appid_dst.write_text(_APP_ID + '\n', encoding='utf-8')
            except Exception:
                pass
            print(f"[Steam] Dev mode: AppID override applied ({_APP_ID})")
        else:
            print("[Steam] Production mode: using AppID from Steam client")
        # ─────────────────────────────────────────────────────────────────────
        # ────────────────────────────────────────────────────────────────────
        dll_path = _find_dll()
        if not dll_path:
            lib_name = _get_platform_lib_name()
            print(f"[Steam] {lib_name} bulunamadı – Steam entegrasyonu devre dışı.")
            return False

        try:
            dll = ctypes.CDLL(dll_path)
        except OSError as e:
            print(f"[Steam] Kütüphane yüklenemedi ({dll_path}): {e}")
            return False

        _setup_dll_functions(dll)

        # SDK 1.60+ → SteamAPI_InitFlat(pOutErrMsg) → ESteamAPIInitResult, 0=OK
        # SDK <1.60  → SteamAPI_Init()            → bool/int,          1=OK
        _init_ok_val = False
        if getattr(dll, '_quadrix_has_init_flat', False):
            try:
                errmsg = ctypes.create_string_buffer(1024)
                result = dll.SteamAPI_InitFlat(errmsg)
                _init_ok_val = (result == 0)   # k_ESteamAPIInitResult_OK == 0
                if not _init_ok_val:
                    msg = errmsg.value.decode('utf-8', errors='replace').strip()
                    print(f"[Steam] SteamAPI_InitFlat başarısız ({result}): {msg or 'Steam çalışıyor mu?'}")
            except Exception as e:
                print(f"[Steam] SteamAPI_InitFlat hatası: {e}")
        elif getattr(dll, '_quadrix_has_init_legacy', False):
            try:
                result = dll.SteamAPI_Init()
                # Eski SDK: bool → 1=True=OK; c_int olarak okuyoruz
                _init_ok_val = bool(result)
                if not _init_ok_val:
                    print("[Steam] SteamAPI_Init() başarısız. Steam çalışıyor mu?")
            except Exception as e:
                print(f"[Steam] SteamAPI_Init hatası: {e}")
        else:
            print("[Steam] Ne SteamAPI_InitFlat ne SteamAPI_Init bulundu – DLL uyumsuz?")

        if not _init_ok_val:
            return False

        _dll = dll
        _init_ok = True
        print(f"[Steam] Runtime AppID: {os.environ.get('SteamAppId', '(from Steam client)')}")

        # Interface pointer'larını al — SDK sürümüne göre doğru accessor'ı dene
        def _try_accessor(*names):
            """Birden fazla versiyon adından ilk çalışanı döndür."""
            for name in names:
                try:
                    fn = getattr(dll, name)
                    fn.restype = ctypes.c_void_p
                    fn.argtypes = []
                    ptr = fn()
                    if ptr:
                        return ptr
                except Exception:
                    pass
            return None

        _isteam_friends = _try_accessor(
            'SteamAPI_SteamFriends_v018',  # SDK 1.62+
            'SteamAPI_SteamFriends_v017',
            'SteamAPI_SteamFriends_v016',
        )
        _isteam_user = _try_accessor(
            'SteamAPI_SteamUser_v023',
            'SteamAPI_SteamUser_v022',
            'SteamAPI_SteamUser_v024',
        )
        _isteam_user_stats = _try_accessor(
            'SteamAPI_SteamUserStats_v013',  # SDK 1.62+
            'SteamAPI_SteamUserStats_v012',
            'SteamAPI_SteamUserStats_v011',
        )
        print(f"[Steam] interface ptrs: friends={_isteam_friends} user={_isteam_user} "
              f"userstats={_isteam_user_stats} utils={_isteam_utils}")
        _isteam_utils = _try_accessor(
            'SteamAPI_SteamUtils_v010',
            'SteamAPI_SteamUtils_v009',
        )
        _isteam_apps = _try_accessor(
            'SteamAPI_SteamApps_v008',
            'SteamAPI_SteamApps_v007',
        )

        # Callback pump thread'i başlat
        _pump_running = True
        _pump_thread = threading.Thread(target=_callback_pump_loop, daemon=True)
        _pump_thread.start()

        # RequestCurrentStats — UserStats API'sini aktive et (leaderboard için gerekli)
        # NOT: Bu fonksiyon bazı SDK versiyonlarında DLL'de olmayabilir, sorun değil
        if _isteam_user_stats:
            try:
                dll.SteamAPI_ISteamUserStats_RequestCurrentStats.restype = ctypes.c_bool
                dll.SteamAPI_ISteamUserStats_RequestCurrentStats.argtypes = [ctypes.c_void_p]
                result = dll.SteamAPI_ISteamUserStats_RequestCurrentStats(_isteam_user_stats)
                # Kısa süre pump yap ki stats gelsin
                for _ in range(10):
                    time.sleep(0.05)
                    try:
                        dll.SteamAPI_RunCallbacks()
                    except Exception:
                        pass
                print(f"[Steam] RequestCurrentStats gönderildi: {result}")
            except AttributeError:
                print("[Steam] RequestCurrentStats bu DLL'de yok, atlanıyor (normal).")
            except Exception as _rcs_e:
                print(f"[Steam] RequestCurrentStats hatası: {_rcs_e}")

        # Tüm leaderboard handle'larını arka planda önceden cache'le
        threading.Thread(target=_precache_all_leaderboard_handles, daemon=True).start()

        print(f"[Steam] Başarıyla başlatıldı. Kullanıcı: {get_persona_name()} ({get_steam_id()})")
        return True


def shutdown() -> None:
    """Steam API'yi kapat."""
    global _pump_running, _init_ok
    _pump_running = False
    if _dll and _init_ok:
        try:
            _dll.SteamAPI_Shutdown()
        except Exception:
            pass
    _init_ok = False


def _atexit_cleanup() -> None:
    """Uygulama çıkışında pump ref-count'u ve paused flag'ini sıfırla, Steam'i kapat."""
    global _pump_pause_count, _pump_paused
    _pump_pause_count = 0
    _pump_paused = False
    shutdown()


atexit.register(_atexit_cleanup)


def is_available() -> bool:
    """Steam SDK başarıyla başlatıldıysa True döndürür."""
    return _init_ok and _dll is not None


# ---------------------------------------------------------------------------
# Steam Achievements API
# ---------------------------------------------------------------------------

def unlock_steam_achievement(api_name: str) -> bool:
    """Steam'de bir başarımın kilidini aç.

    Args:
        api_name: Steamworks konsolunda tanımlı API Name (ör. 'ACH_FIRST_GAME').

    Returns:
        True → başarıyla set edildi ve store edildi.
        False → Steam müsait değil veya hata oluştu.
    """
    if not is_available() or not _isteam_user_stats or not _dll:
        return False
    try:
        name_bytes = api_name.encode('utf-8') if isinstance(api_name, str) else api_name
        ok = _dll.SteamAPI_ISteamUserStats_SetAchievement(_isteam_user_stats, name_bytes)
        if ok:
            _dll.SteamAPI_ISteamUserStats_StoreStats(_isteam_user_stats)
            print(f"[Steam] Achievement unlocked: {api_name}")
        return bool(ok)
    except Exception as e:
        print(f"[Steam] Achievement unlock hatası ({api_name}): {e}")
        return False


def is_steam_achievement_unlocked(api_name: str) -> bool | None:
    """Steam'de başarımın açılmış olup olmadığını sorgula.

    Returns:
        True/False → durum, None → sorgulanamadı.
    """
    if not is_available() or not _isteam_user_stats or not _dll:
        return None
    try:
        name_bytes = api_name.encode('utf-8') if isinstance(api_name, str) else api_name
        achieved = ctypes.c_bool(False)
        ok = _dll.SteamAPI_ISteamUserStats_GetAchievement(
            _isteam_user_stats, name_bytes, ctypes.byref(achieved)
        )
        if ok:
            return bool(achieved.value)
        return None
    except Exception:
        return None


def sync_all_achievements(unlocked_ids: dict[str, str], id_map: dict[str, str]) -> int:
    """Oyundaki tüm açılmış başarımları Steam'e toplu senkronla.

    Args:
        unlocked_ids: {achievement_id: unlock_date} — oyun içi açılmış başarımlar.
        id_map: {achievement_id: steam_api_name} — oyun ID → Steam API Name eşlemesi.

    Returns:
        Yeni senkronlanan başarım sayısı.
    """
    if not is_available() or not _isteam_user_stats or not _dll:
        return 0
    count = 0
    for ach_id, steam_name in id_map.items():
        if ach_id in unlocked_ids:
            # Zaten Steam'de açık mı kontrol et
            already = is_steam_achievement_unlocked(steam_name)
            if already is True:
                continue
            try:
                name_bytes = steam_name.encode('utf-8') if isinstance(steam_name, str) else steam_name
                ok = _dll.SteamAPI_ISteamUserStats_SetAchievement(_isteam_user_stats, name_bytes)
                if ok:
                    count += 1
            except Exception:
                pass
    if count > 0:
        try:
            _dll.SteamAPI_ISteamUserStats_StoreStats(_isteam_user_stats)
            print(f"[Steam] {count} başarım senkronlandı.")
        except Exception:
            pass
    return count


def clear_steam_achievement(api_name: str) -> bool:
    """Steam'de bir başarımın kilidini geri al (test/geliştirme amaçlı).

    Args:
        api_name: Steamworks konsolunda tanımlı API Name (ör. 'ACH_FIRST_GAME').

    Returns:
        True → başarıyla temizlendi ve store edildi.
    """
    if not is_available() or not _isteam_user_stats or not _dll:
        return False
    try:
        name_bytes = api_name.encode('utf-8') if isinstance(api_name, str) else api_name
        ok = _dll.SteamAPI_ISteamUserStats_ClearAchievement(_isteam_user_stats, name_bytes)
        if ok:
            _dll.SteamAPI_ISteamUserStats_StoreStats(_isteam_user_stats)
            print(f"[Steam] Achievement cleared: {api_name}")
        return bool(ok)
    except Exception as e:
        print(f"[Steam] Achievement clear hatası ({api_name}): {e}")
        return False


def indicate_achievement_progress(api_name: str, current: int, target: int) -> bool:
    """Steam Overlay'de başarım ilerleme bildirimi göster.

    Belirli kilometre taşlarında (ör. %50, %75) çağrılarak
    kullanıcıya toast bildirim gösterir.

    Args:
        api_name: Steamworks API Name (ör. 'ACH_LINES_100').
        current: Mevcut ilerleme değeri.
        target: Hedef değer.

    Returns:
        True → bildirim başarıyla gönderildi.
    """
    if not is_available() or not _isteam_user_stats or not _dll:
        return False
    try:
        name_bytes = api_name.encode('utf-8') if isinstance(api_name, str) else api_name
        ok = _dll.SteamAPI_ISteamUserStats_IndicateAchievementProgress(
            _isteam_user_stats, name_bytes,
            ctypes.c_uint32(max(0, current)),
            ctypes.c_uint32(max(1, target)),
        )
        return bool(ok)
    except Exception as e:
        print(f"[Steam] IndicateAchievementProgress hatası ({api_name}): {e}")
        return False


# ---------------------------------------------------------------------------
# Steam Stats API — İstatistik okuma / yazma
# ---------------------------------------------------------------------------

# Oyun → Steamworks stat API Name eşlemesi
STEAM_STAT_MAP: dict[str, tuple[str, str]] = {
    # game_stat_key: (steam_api_name, type)
    'total_games':           ('STAT_TOTAL_GAMES', 'int'),
    'total_lines':           ('STAT_TOTAL_LINES', 'int'),
    'total_tetrises':        ('STAT_TOTAL_TETRISES', 'int'),
    'max_score':             ('STAT_MAX_SCORE', 'int'),
    'max_lines':             ('STAT_MAX_LINES', 'int'),
    'max_level':             ('STAT_MAX_LEVEL', 'int'),
    'max_combo':             ('STAT_MAX_COMBO', 'int'),
    'perfect_clears':        ('STAT_PERFECT_CLEARS', 'int'),
    'pvp_wins':              ('STAT_PVP_WINS', 'int'),
    'campaign_total_stars':  ('STAT_CAMPAIGN_STARS', 'int'),
    'sprint_best_time':      ('STAT_SPRINT_BEST_TIME', 'float'),
    'ultra_max_score':       ('STAT_ULTRA_MAX_SCORE', 'int'),
    'survival_max_time':     ('STAT_SURVIVAL_MAX_TIME', 'float'),
    'cascade_max_chain':     ('STAT_CASCADE_MAX_CHAIN', 'int'),
    'hardcore_max_level':    ('STAT_HARDCORE_MAX_LEVEL', 'int'),
    'wide_max_lines':        ('STAT_WIDE_MAX_LINES', 'int'),
    'daily_max_streak':      ('STAT_DAILY_MAX_STREAK', 'int'),
}


def set_steam_stat_int(api_name: str, value: int) -> bool:
    """Steam'de bir INT istatistiğini güncelle (StoreStats ayrıca çağrılmalı).

    Args:
        api_name: Steamworks konsolunda tanımlı stat API Name.
        value: Yeni değer.
    """
    if not is_available() or not _isteam_user_stats or not _dll:
        return False
    try:
        name_bytes = api_name.encode('utf-8') if isinstance(api_name, str) else api_name
        ok = _dll.SteamAPI_ISteamUserStats_SetStatInt32(
            _isteam_user_stats, name_bytes, ctypes.c_int32(value)
        )
        return bool(ok)
    except Exception as e:
        print(f"[Steam] SetStat INT hatası ({api_name}): {e}")
        return False


def set_steam_stat_float(api_name: str, value: float) -> bool:
    """Steam'de bir FLOAT istatistiğini güncelle (StoreStats ayrıca çağrılmalı).

    Args:
        api_name: Steamworks konsolunda tanımlı stat API Name.
        value: Yeni değer.
    """
    if not is_available() or not _isteam_user_stats or not _dll:
        return False
    try:
        name_bytes = api_name.encode('utf-8') if isinstance(api_name, str) else api_name
        ok = _dll.SteamAPI_ISteamUserStats_SetStatFloat(
            _isteam_user_stats, name_bytes, ctypes.c_float(value)
        )
        return bool(ok)
    except Exception as e:
        print(f"[Steam] SetStat FLOAT hatası ({api_name}): {e}")
        return False


def get_steam_stat_int(api_name: str) -> int | None:
    """Steam'den bir INT istatistiğini oku.

    Returns:
        Değer veya None (okunamadı).
    """
    if not is_available() or not _isteam_user_stats or not _dll:
        return None
    try:
        name_bytes = api_name.encode('utf-8') if isinstance(api_name, str) else api_name
        data = ctypes.c_int32(0)
        ok = _dll.SteamAPI_ISteamUserStats_GetStatInt32(
            _isteam_user_stats, name_bytes, ctypes.byref(data)
        )
        if ok:
            return data.value
        return None
    except Exception:
        return None


def get_steam_stat_float(api_name: str) -> float | None:
    """Steam'den bir FLOAT istatistiğini oku.

    Returns:
        Değer veya None (okunamadı).
    """
    if not is_available() or not _isteam_user_stats or not _dll:
        return None
    try:
        name_bytes = api_name.encode('utf-8') if isinstance(api_name, str) else api_name
        data = ctypes.c_float(0.0)
        ok = _dll.SteamAPI_ISteamUserStats_GetStatFloat(
            _isteam_user_stats, name_bytes, ctypes.byref(data)
        )
        if ok:
            return data.value
        return None
    except Exception:
        return None


def store_steam_stats() -> bool:
    """Bekleyen tüm stat ve başarım değişikliklerini Steam'e yaz.

    SetStat / SetAchievement çağrıları bellekte tutulur;
    bu fonksiyon onları sunucuya gönderir.
    """
    if not is_available() or not _isteam_user_stats or not _dll:
        return False
    try:
        ok = _dll.SteamAPI_ISteamUserStats_StoreStats(_isteam_user_stats)
        return bool(ok)
    except Exception as e:
        print(f"[Steam] StoreStats hatası: {e}")
        return False


def sync_stats_to_steam(stats: dict) -> int:
    """Oyun istatistiklerini Steam'e toplu senkronla.

    Args:
        stats: Oyun içi istatistikler dict'i (AchievementManager.stats).

    Returns:
        Güncellenen stat sayısı.
    """
    if not is_available() or not _isteam_user_stats or not _dll:
        return 0
    count = 0
    for game_key, (steam_name, stat_type) in STEAM_STAT_MAP.items():
        value = stats.get(game_key)
        if value is None:
            continue
        try:
            if stat_type == 'float':
                ok = set_steam_stat_float(steam_name, float(value))
            else:
                ok = set_steam_stat_int(steam_name, int(value))
            if ok:
                count += 1
        except Exception:
            pass
    if count > 0:
        store_steam_stats()
        print(f"[Steam] {count} istatistik senkronlandı.")
    return count


def reset_all_steam_stats(achievements_too: bool = False) -> bool:
    """Tüm istatistikleri (ve isteğe bağlı başarımları) sıfırla.

    DİKKAT: Bu fonksiyon sadece geliştirme/test amacıyla kullanılmalıdır!

    Args:
        achievements_too: True ise başarımlar da sıfırlanır.

    Returns:
        True → başarıyla sıfırlandı.
    """
    if not is_available() or not _isteam_user_stats or not _dll:
        return False
    try:
        ok = _dll.SteamAPI_ISteamUserStats_ResetAllStats(
            _isteam_user_stats, ctypes.c_bool(achievements_too)
        )
        if ok:
            # Sıfırlamadan sonra stats'ı yeniden al
            _dll.SteamAPI_ISteamUserStats_RequestCurrentStats(_isteam_user_stats)
            print(f"[Steam] Tüm istatistikler sıfırlandı (achievements_too={achievements_too})")
        return bool(ok)
    except Exception as e:
        print(f"[Steam] ResetAllStats hatası: {e}")
        return False


def _callback_pump_loop() -> None:
    """Arka planda Steam callback'lerini işle (30ms aralıklı)."""
    while _pump_running:
        if _dll and _init_ok and not _pump_paused:
            with _pump_lock:
                try:
                    _dll.SteamAPI_RunCallbacks()
                except Exception:
                    pass
        else:
            # Pause bekleniyorsa ack ver
            _pump_paused_event.set()
        time.sleep(0.03)


def run_callbacks() -> None:
    """Tek seferlik callback pump (ana thread'den çağrılabilir)."""
    if _dll and _init_ok and not _pump_paused:
        with _pump_lock:
            try:
                _dll.SteamAPI_RunCallbacks()
            except Exception:
                pass


def pause_pump() -> None:
    """Pump thread'ini duraklat — Online PvP bridge RunCallbacks'i devralınca çağrılır.

    Ref-count tabanlı: birden fazla çağrıya karşı güvenli (nested pause/resume).
    Aynı anda iki farklı thread'den SteamAPI_RunCallbacks() çağırmak
    Steam SDK'da race condition/segfault oluşturur. Bridge kendi tick()
    metodu içinde RunCallbacks çağırdığı için pump thread duraklatılmalıdır.
    """
    global _pump_paused, _pump_pause_count
    _pump_pause_count += 1
    _pump_paused_event.clear()
    _pump_paused = True
    # Pump döngüsünün mevcut iterasyonunun bitmesini BEKle (lock ile garanti)
    # Lock al ve bırak — pump döngüsü RunCallbacks'ten çıkana kadar burada bekler
    with _pump_lock:
        pass
    # Ek güvenlik için pump'un pause gördüğünden emin ol (best-effort)
    if not _pump_paused_event.wait(timeout=0.15):
        print(f"[Steam] Pump pause ack timeout (best-effort devam, count={_pump_pause_count})")
    print(f"[Steam] Pump thread duraklatıldı (bridge aktif, count={_pump_pause_count})")


def resume_pump() -> None:
    """Pump thread'ini sürdür — Online PvP bridge kapandığında çağrılır.

    Ref-count tabanlı: yalnızca tüm pause çağrıları karşılandığında pump açılır.
    Count asla negatife düşmez.
    """
    global _pump_paused, _pump_pause_count
    _pump_pause_count -= 1
    if _pump_pause_count <= 0:
        _pump_pause_count = 0  # Negatife düşmeyi önle
        _pump_paused = False
        _pump_paused_event.clear()
    print(f"[Steam] Pump resume çağrıldı (count={_pump_pause_count}, paused={_pump_paused})")


def _precache_all_leaderboard_handles() -> None:
    """Init sonrası tüm leaderboard handle'larını arka planda önceden al."""
    # Pump thread'inin başlaması için biraz bekle
    time.sleep(1.0)
    if not is_available() or not _isteam_user_stats:
        return
    print("[Steam] Leaderboard handle'ları önceden yükleniyor...")
    for mode, lb_name in _MODE_TO_LB.items():
        if lb_name not in _lb_handle_cache:
            _find_leaderboard_handle_by_api(lb_name, timeout=8.0)
    cached = list(_lb_handle_cache.keys())
    print(f"[Steam] {len(cached)} leaderboard handle cache'lendi: {cached}")


# ---------------------------------------------------------------------------
# Kullanıcı bilgisi
# ---------------------------------------------------------------------------

def get_persona_name() -> str | None:
    """Oturum açmış Steam kullanıcısının profil adını döndürür."""
    global _persona_name_cache
    if _persona_name_cache is not None:
        return _persona_name_cache
    if not is_available() or not _isteam_friends:
        return None
    try:
        raw = _dll.SteamAPI_ISteamFriends_GetPersonaName(_isteam_friends)  # type: ignore[union-attr]
        if raw:
            name = raw.decode('utf-8', errors='replace')
            _persona_name_cache = name
            return name
    except Exception as e:
        print(f"[Steam] GetPersonaName hatası: {e}")
    return None


def get_steam_id() -> int | None:
    """Oturum açmış kullanıcının SteamID64'ünü döndürür."""
    global _steam_id_cache
    if _steam_id_cache is not None:
        return _steam_id_cache
    if not is_available() or not _isteam_user:
        return None
    try:
        sid = _dll.SteamAPI_ISteamUser_GetSteamID(_isteam_user)  # type: ignore[union-attr]
        if sid and sid != 0:
            _steam_id_cache = int(sid)
            return _steam_id_cache
    except Exception as e:
        print(f"[Steam] GetSteamID hatası: {e}")
    return None


def get_steam_id_str() -> str:
    """SteamID64'ü string olarak döndürür; bilinmiyorsa boş."""
    sid = get_steam_id()
    return str(sid) if sid else ""


def get_avatar_rgba(
    steam_id: int | None = None,
    preferred: str = 'medium',
) -> tuple[int, int, bytes] | None:
    """Steam avatarını SDK üzerinden RGBA olarak döndür.

    Returns:
        (width, height, rgba_bytes) veya None
    """
    if not is_available() or not _dll or not _isteam_friends or not _isteam_utils:
        return None

    sid = int(steam_id or get_steam_id() or 0)
    if sid <= 0:
        return None

    pref = str(preferred or 'medium').strip().lower()
    if pref not in ('small', 'medium', 'large'):
        pref = 'medium'
    cache_key = (sid, pref)
    cached = _avatar_rgba_cache.get(cache_key)
    if cached is not None:
        return cached

    getter_name = {
        'small': 'SteamAPI_ISteamFriends_GetSmallFriendAvatar',
        'medium': 'SteamAPI_ISteamFriends_GetMediumFriendAvatar',
        'large': 'SteamAPI_ISteamFriends_GetLargeFriendAvatar',
    }[pref]
    get_avatar_fn = getattr(_dll, getter_name, None)
    if not callable(get_avatar_fn):
        return None

    try:
        image_handle = int(get_avatar_fn(_isteam_friends, ctypes.c_uint64(sid)))
    except Exception:
        return None

    # -1: loading, 0: no avatar
    if image_handle <= 0:
        return None

    width = ctypes.c_uint32(0)
    height = ctypes.c_uint32(0)
    try:
        ok_size = _dll.SteamAPI_ISteamUtils_GetImageSize(
            _isteam_utils,
            ctypes.c_int(image_handle),
            ctypes.byref(width),
            ctypes.byref(height),
        )
    except Exception:
        return None
    if not ok_size or width.value <= 0 or height.value <= 0:
        return None

    rgba_len = int(width.value) * int(height.value) * 4
    buf = (ctypes.c_uint8 * rgba_len)()
    try:
        ok_rgba = _dll.SteamAPI_ISteamUtils_GetImageRGBA(
            _isteam_utils,
            ctypes.c_int(image_handle),
            buf,
            ctypes.c_int(rgba_len),
        )
    except Exception:
        return None
    if not ok_rgba:
        return None

    result = (int(width.value), int(height.value), bytes(buf))
    _avatar_rgba_cache[cache_key] = result
    return result


def is_app_owned() -> bool | None:
    """Aktif Steam hesabının bu AppID için geçerli lisansı olup olmadığını kontrol et.

    Returns:
        True  — lisans var (SDK onayı).
        False — lisans yok; k_EResultInvalidParam(8) durumunun root-cause'u.
        None  — Steam SDK mevcut değil veya SteamApps arayüzü alınamadı (bilinmiyor).

    Not: Playtest istek kuyruğuna alınmak ≠ Steam lisansı.
    Lisans için: Partner Portal → AppID → Packages → Developer Comp → hesap ekle.
    """
    if not is_available() or not _isteam_apps or not _dll:
        return None
    try:
        result = _dll.SteamAPI_ISteamApps_BIsSubscribed(_isteam_apps)
        owned = bool(result)
        if not owned:
            print(
                f"[Steam] is_app_owned: FALSE — bu hesapta AppID {_APP_ID_INT} lisansi yok. "
                "Partner Portal -> Packages -> Developer Comp ile lisans ekleyin."
            )
        return owned
    except Exception as e:
        print(f"[Steam] is_app_owned hatasi: {e}")
        return None


# ---------------------------------------------------------------------------
# Auth ticket (arkadaş listesi)
# ---------------------------------------------------------------------------

_auth_ticket_cache: bytes | None = None
_auth_ticket_hex_cache: str | None = None


def get_auth_session_ticket() -> str | None:
    """Steam auth session ticket döndürür (hex encoded).

    Bu ticket backend'e gönderilir; backend ISteamUserAuth_AuthenticateUserTicket ile doğrular.
    """
    global _auth_ticket_cache, _auth_ticket_hex_cache
    if _auth_ticket_hex_cache:
        return _auth_ticket_hex_cache
    if not is_available() or not _isteam_user:
        return None
    try:
        buf_size = 1024
        buf = (ctypes.c_uint8 * buf_size)()
        out_size = ctypes.c_uint32(0)
        handle = _dll.SteamAPI_ISteamUser_GetAuthSessionTicket(  # type: ignore[union-attr]
            _isteam_user,
            buf,
            buf_size,
            ctypes.byref(out_size),
            None,
        )
        if handle and out_size.value > 0:
            ticket_bytes = bytes(buf[:out_size.value])
            _auth_ticket_cache = ticket_bytes
            _auth_ticket_hex_cache = ticket_bytes.hex()
            # Ticket'ın geçerli hale gelmesi için callbacks pump
            for _ in range(5):
                run_callbacks()
                time.sleep(0.05)
            return _auth_ticket_hex_cache
    except Exception as e:
        print(f"[Steam] GetAuthSessionTicket hatası: {e}")
    return None


# ---------------------------------------------------------------------------
# Leaderboard yardımcıları
# ---------------------------------------------------------------------------

# Skor gönderimi için mod adından Steam leaderboard adına map
_MODE_TO_LB: dict[str, str] = {
    "classic": "quadrix_classic",
    "sprint": "quadrix_sprint",
    "ultra": "quadrix_ultra",
    "zen": "quadrix_zen",
    "mystery": "quadrix_mystery",
    "survival": "quadrix_survival",
    "cascade": "quadrix_cascade",
    "wide": "quadrix_wide",
    "hardcore": "quadrix_hardcore",
    "daily": "quadrix_daily",
    "tetris2": "quadrix_tetris2",
}


# NOT: _find_leaderboard_sync kaldırıldı — pump thread ile yarış durumu oluşturuyordu.
# Yerine _find_leaderboard_handle_by_api (GetAPICallResult-polling tabanlı, thread-safe) kullanılır.


# Steam callback ID sabitleri (ISteamUserStats = 1100-base)
_CB_LEADERBOARD_FIND_RESULT   = 1104  # LeaderboardFindResult_t      (k_iSteamUserStatsCallbacks+4)
_CB_LEADERBOARD_SCORE_UPLOADED = 1106  # LeaderboardScoreUploaded_t   (k_iSteamUserStatsCallbacks+6)


class _LeaderboardFindResult(ctypes.Structure):
    """LeaderboardFindResult_t — FindLeaderboard callback sonucu."""
    _fields_ = [
        ("m_hSteamLeaderboard", ctypes.c_uint64),
        ("m_bLeaderboardFound", ctypes.c_uint8),
    ]


class _LeaderboardScoreUploaded(ctypes.Structure):
    """LeaderboardScoreUploaded_t — UploadLeaderboardScore callback sonucu."""
    _fields_ = [
        ("m_bSuccess",          ctypes.c_uint8),
        ("m_hSteamLeaderboard", ctypes.c_uint64),
        ("m_nScore",            ctypes.c_int32),
        ("m_bScoreChanged",     ctypes.c_uint8),
        ("m_nGlobalRankNew",    ctypes.c_int32),
        ("m_nGlobalRankPrevious", ctypes.c_int32),
    ]


def _get_api_call_result(api_call_handle: int, result_struct, callback_id: int,
                         timeout: float = 6.0) -> Any | None:
    """SteamAPI_ISteamUtils_GetAPICallResult ile async call sonucunu polling ile al.

    Bu, C++'daki CCallResult mekanizmasının Python karşılığıdır.
    Returns: dolu result_struct örneği veya None (hata/timeout).
    """
    if not _isteam_utils or not _dll:
        print(f"[Steam] _get_api_call_result: utils={_isteam_utils} dll={_dll is not None}")
        return None
    failed = ctypes.c_bool(False)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        # run_callbacks() burada ÇAĞRILMIYOR — pump thread her 30ms'de hallediyor
        # İki thread'den aynı anda RunCallbacks çağırmak race condition yaratır
        try:
            # Önce tamamlandı mı kontrol et
            try:
                completed = _dll.SteamAPI_ISteamUtils_IsAPICallCompleted(
                    _isteam_utils, ctypes.c_uint64(api_call_handle), ctypes.byref(failed)
                )
                if completed and failed.value:
                    print(f"[Steam] API call {api_call_handle} failed flag set")
                    return None
            except Exception:
                pass  # IsAPICallCompleted olmayabilir, sorun değil

            ok = _dll.SteamAPI_ISteamUtils_GetAPICallResult(
                _isteam_utils,
                ctypes.c_uint64(api_call_handle),
                ctypes.byref(result_struct),
                ctypes.sizeof(result_struct),
                callback_id,
                ctypes.byref(failed),
            )
            if ok:
                if failed.value:
                    print(f"[Steam] API call {api_call_handle} cb={callback_id} failed")
                    return None
                return result_struct
        except Exception as _e:
            print(f"[Steam] GetAPICallResult exception (cb={callback_id}): {_e}")
            return None
        time.sleep(0.05)
    print(f"[Steam] API call {api_call_handle} cb={callback_id} TIMEOUT ({timeout}s)")
    return None


def _find_leaderboard_handle_by_api(lb_name: str, timeout: float = 6.0) -> int | None:
    """FindLeaderboard + GetAPICallResult ile leaderboard handle'ını al."""
    if not is_available() or not _isteam_user_stats:
        return None
    # Cache'de varsa direkt döndür
    if lb_name in _lb_handle_cache:
        return _lb_handle_cache[lb_name]
    try:
        api_call = _dll.SteamAPI_ISteamUserStats_FindLeaderboard(  # type: ignore[union-attr]
            _isteam_user_stats,
            lb_name.encode('utf-8'),
        )
        if not api_call:
            print(f"[Steam] FindLeaderboard çağrısı başarısız: {lb_name}")
            return None

        result = _LeaderboardFindResult()
        found = _get_api_call_result(api_call, result, _CB_LEADERBOARD_FIND_RESULT, timeout=timeout)
        if found and found.m_bLeaderboardFound and found.m_hSteamLeaderboard:
            handle = int(found.m_hSteamLeaderboard)
            _lb_handle_cache[lb_name] = handle
            try:
                print(f"[Steam] Leaderboard found: {lb_name} -> handle={handle}")
            except Exception:
                pass
            return handle
        else:
            try:
                print(f"[Steam] Leaderboard not found: {lb_name}")
            except Exception:
                pass
    except Exception as e:
        try:
            print(f"[Steam] FindLeaderboard error ({lb_name}): {e}")
        except Exception:
            pass
    return None


# Leaderboard isimden Steam numeric ID'ye map (Partner API fallback için)
_LB_NAME_TO_ID: dict[str, int] = {
    "quadrix_classic":  19192037,
    "quadrix_sprint":   19192054,
    "quadrix_ultra":    19192058,
    "quadrix_zen":      19192061,
    "quadrix_mystery":  19198572,
    "quadrix_survival": 19192067,
    "quadrix_cascade":  19192075,
    "quadrix_wide":     19192077,
    "quadrix_hardcore": 19192078,
    "quadrix_daily":    19192081,
    "quadrix_tetris2":  19192083,
}

# NOT: _PARTNER_API_KEY modül import'unda okunur AMA çalışma zamanı
# güncellemelerini yakalamak için _get_partner_api_key() fonksiyonu kullanılır.
_PARTNER_API_KEY_CACHED: str | None = None
_APP_ID_INT = 4428040


def _get_partner_api_key() -> str:
    """Partner API key'i döndürür (env var her seferinde kontrol edilir)."""
    global _PARTNER_API_KEY_CACHED
    val = os.environ.get('STEAM_WEB_API_KEY', '').strip()
    if val:
        _PARTNER_API_KEY_CACHED = val
        return val
    return _PARTNER_API_KEY_CACHED or ''

# In-memory cache for dynamically resolved leaderboard IDs (session-lived)
_lb_id_web_cache: dict[str, int] = {}


def _resolve_lb_id_via_web_api(lb_name: str) -> int | None:
    """Resolve leaderboard numeric ID from Steam Web API (FindLeaderboard/v1/).

    Caches results for the session. Returns None on failure.
    Requires _get_partner_api_key() and _APP_ID_INT to be set.
    """
    if lb_name in _lb_id_web_cache:
        return _lb_id_web_cache[lb_name]
    api_key = _get_partner_api_key()
    if not api_key or not _APP_ID_INT:
        return None
    try:
        import urllib.request
        import urllib.parse
        import json
        params = urllib.parse.urlencode({
            'key': api_key,
            'appid': _APP_ID_INT,
            'name': lb_name,
        })
        url = f'https://partner.steam-api.com/ISteamLeaderboards/FindLeaderboard/v1/?{params}'
        req = urllib.request.Request(url, method='GET')
        with urllib.request.urlopen(req, timeout=6) as resp:
            body = json.loads(resp.read().decode('utf-8', errors='replace'))
            # Steam API yanıt yapısı varyantları:
            #   {"response": {"leaderboard": {"leaderboardid": ...}}}
            #   {"leaderboard": {"leaderboardID": ...}}
            # Her iki yapıyı da destekle
            if not isinstance(body, dict):
                return None

            _ID_KEYS = ('leaderboardid', 'leaderboard_id', 'leaderboardID', 'id')

            def _extract_id(obj: dict) -> int | None:
                for key in _ID_KEYS:
                    val = obj.get(key)
                    if val is not None:
                        try:
                            return int(val)
                        except (TypeError, ValueError):
                            pass
                return None

            lb_id = None

            # Yol 1: body.response.leaderboard (standart Steam API)
            response = body.get('response', {})
            if isinstance(response, dict):
                lb_id = _extract_id(response)
                if lb_id is None:
                    nested = response.get('leaderboard', {})
                    if isinstance(nested, dict):
                        lb_id = _extract_id(nested)

            # Yol 2: body.leaderboard (alternatif format)
            if lb_id is None:
                nested = body.get('leaderboard', {})
                if isinstance(nested, dict):
                    lb_id = _extract_id(nested)

            # Yol 3: doğrudan body seviyesinde
            if lb_id is None:
                lb_id = _extract_id(body)

            if lb_id:
                _lb_id_web_cache[lb_name] = lb_id
                try:
                    print(f"[Steam] Leaderboard ID resolved: {lb_name} -> {lb_id}")
                except Exception:
                    pass
                return lb_id
    except Exception as e:
        try:
            print(f"[Steam] Leaderboard ID resolve failed ({lb_name}): {e}")
        except Exception:
            pass
    return None


def _is_partner_fallback_enabled() -> bool:
    """Partner API write fallback aktif mi kontrol et.

    Aktif olma koşulları (herhangi biri yeterli):
    1. STEAM_PARTNER_WRITE_FALLBACK=1 env var açıkça set edilmişse
    2. STEAM_WEB_API_KEY env var'ında geçerli bir publisher key varsa
       (playtest / dev ortamında key varsa fallback otomatik aktif olur)
    """
    if os.environ.get('STEAM_PARTNER_WRITE_FALLBACK', '0').strip() == '1':
        return True
    # Publisher key mevcutsa otomatik aktifleştir (playtest/dev senaryosu)
    if _get_partner_api_key():
        return True
    return False


def _submit_score_via_partner_api(lb_name: str, score: int, steam_id_str: str) -> bool:
    """SDK başarısız olursa Partner Server API ile skor gönder (fallback).

    Bu yol; oyuncunun Steam lisansı varsa (normal satın alma / playtest key ile)
    her zaman çalışır. Lisans yoksa k_EResultInvalidParam(8) döner.
    """
    # Try dynamic Web API resolution first; fall back to hardcoded map
    lb_id = _resolve_lb_id_via_web_api(lb_name) or _LB_NAME_TO_ID.get(lb_name)
    if not lb_id or not steam_id_str:
        return False
    try:
        import urllib.request
        import urllib.parse
        api_key = _get_partner_api_key()
        params = urllib.parse.urlencode({
            'key': api_key,
            'appid': _APP_ID_INT,
            'leaderboardid': lb_id,
            'steamid': steam_id_str,
            'score': score,
            'scoremethod': 'KeepBest',  # Steam Web API requires string: "KeepBest" or "ForceUpdate"
        }).encode('ascii')
        url = 'https://partner.steam-api.com/ISteamLeaderboards/SetLeaderboardScore/v1/'
        req = urllib.request.Request(url, data=params, method='POST')
        req.add_header('Content-Type', 'application/x-www-form-urlencoded')
        with urllib.request.urlopen(req, timeout=8) as resp:
            import json
            body = json.loads(resp.read().decode('utf-8', errors='replace'))
            result_code = body.get('result', {}).get('result', -1)
            if result_code == 1:
                new_rank = body.get('result', {}).get('global_rank_new', 0)
                print(f"[Steam] Partner API skor OK -> {lb_name}: {score} rank={new_rank}")
                return True
            else:
                # result=8 = k_EResultInvalidParam: bu account bu app'i sahip degil
                # Production oyuncularinda bu olmaz (Steam key/satin alma ile lisansli olurlar)
                hint = ""
                if result_code == 8:
                    hint = " (result=8 = InvalidParam: check scoremethod string, leaderboardid, appid)"
                print(f"[Steam] Partner API skor FAIL -> {lb_name}: result={result_code}{hint} "
                      f"(8=lisans yok / dev hesabi icin: Partner Portal -> Packages -> Developer Comp -> hesabi ekle)")
                return False
    except Exception as e:
        print(f"[Steam] Partner API skor hatasi ({lb_name}): {e}")
        return False


def submit_score(mode: str, score: int) -> bool:
    """Steam leaderboard'una en yüksek skor (KeepBest) olarak yükle.

    Arka planda çalışır. Önce SDK (UploadLeaderboardScore) dener.
    SDK success=0 dönerse Partner Server API'ye fallback yapar.
    Returns True if upload thread was started.
    """
    lb_name = _MODE_TO_LB.get(str(mode or '').lower())
    if not lb_name:
        print(f"[Steam] Tanınmayan mod: {mode!r}")
        return False

    sdk_ok = is_available() and bool(_isteam_user_stats)
    steam_id_str = get_steam_id_str() if sdk_ok else None

    def _worker():
        sdk_success = False

        # --- Yol 1: Client SDK ---
        if sdk_ok and _isteam_user_stats:
            try:
                handle = _lb_handle_cache.get(lb_name) or _find_leaderboard_handle_by_api(lb_name)
                if handle:
                    api_call = _dll.SteamAPI_ISteamUserStats_UploadLeaderboardScore(  # type: ignore[union-attr]
                        _isteam_user_stats,
                        ctypes.c_uint64(handle),
                        1,   # k_ELeaderboardUploadScoreMethodKeepBest (0=None, 1=KeepBest, 2=ForceUpdate)
                        ctypes.c_int32(score),
                        None, 0,
                    )
                    if api_call:
                        up_result = _LeaderboardScoreUploaded()
                        confirmed = _get_api_call_result(
                            api_call, up_result, _CB_LEADERBOARD_SCORE_UPLOADED, timeout=8.0)
                        if confirmed and confirmed.m_bSuccess:
                            sdk_success = True
                            print(f"[Steam] SDK skor OK -> {lb_name}: {score} "
                                  f"rank={confirmed.m_nGlobalRankNew} degisti={bool(confirmed.m_bScoreChanged)}")
                        else:
                            print(f"[Steam] SDK skor FAIL (success=0) -> {lb_name}, Partner API deneniyor...")
                    else:
                        print(f"[Steam] UploadLeaderboardScore cagri basarisiz: {lb_name}")
                else:
                    print(f"[Steam] Handle alinamadi: {lb_name}")
            except Exception as e:
                print(f"[Steam] SDK submit hatasi ({lb_name}): {e}")

        # --- Yol 2: Partner Server API fallback ---
        if not sdk_success and steam_id_str:
            if _is_partner_fallback_enabled():
                partner_ok = _submit_score_via_partner_api(lb_name, score, steam_id_str)
                if not partner_ok:
                    print(
                        f"[Steam] Partner API fallback da basarisiz -> {lb_name}. "
                        f"Leaderboard ID veya publisher key kontrol edin."
                    )
            else:
                print(
                    f"[Steam] SDK yazimi basarisiz (sdk_success=0) -> {lb_name}. "
                    "Partner API fallback icin: STEAM_WEB_API_KEY env var set edin. "
                    "(Playtest kullanicilari icin Partner API gereklidir, "
                    "cunku SDK leaderboard yazimi farkli AppID altinda calismaz.)"
                )
        elif not sdk_success and not steam_id_str:
            print(f"[Steam] Skor gonderilemedi: SDK yok, steam_id yok -> {lb_name}: {score}")

    threading.Thread(target=_worker, daemon=True).start()
    return True


# ---------------------------------------------------------------------------
# Otomatik kullanıcı profil bilgisi
# ---------------------------------------------------------------------------

def get_user_display_name() -> str | None:
    """Steam persona adını döndür (yoksa None)."""
    return get_persona_name()


def get_user_identity() -> dict[str, Any]:
    """Steam profil bilgilerini dict olarak döndür.

    Returns:
        {
            "steam_id": int | None,
            "steam_id_str": str,
            "persona_name": str | None,
            "available": bool,
        }
    """
    return {
        "steam_id": get_steam_id(),
        "steam_id_str": get_steam_id_str(),
        "persona_name": get_persona_name(),
        "available": is_available(),
    }


# ---------------------------------------------------------------------------
# Leaderboard okuma (SDK üzerinden, proxy gerektirmez)
# ---------------------------------------------------------------------------

# ELeaderboardDataRequest enum değerleri
_LB_REQUEST_GLOBAL = 0
_LB_REQUEST_AROUND_USER = 1
_LB_REQUEST_FRIENDS = 2


class _LeaderboardEntry(ctypes.Structure):
    """LeaderboardEntry_t yapısı."""
    _fields_ = [
        ("m_steamIDUser",  ctypes.c_uint64),
        ("m_nGlobalRank",  ctypes.c_int32),
        ("m_nScore",       ctypes.c_int32),
        ("m_cDetails",     ctypes.c_int32),
        ("m_hUGC",         ctypes.c_uint64),
    ]


def _setup_get_entries_function(dll: ctypes.CDLL) -> None:
    """GetDownloadedLeaderboardEntry fonksiyonunu kur."""
    try:
        dll.SteamAPI_ISteamUserStats_GetDownloadedLeaderboardEntry.restype = ctypes.c_bool
        dll.SteamAPI_ISteamUserStats_GetDownloadedLeaderboardEntry.argtypes = [
            ctypes.c_void_p,   # ISteamUserStats*
            ctypes.c_uint64,   # SteamLeaderboardEntries_t
            ctypes.c_int,      # index
            ctypes.POINTER(_LeaderboardEntry),  # pLeaderboardEntry out
            ctypes.c_void_p,   # pDetails (NULL)
            ctypes.c_int,      # cDetailsMax
        ]
    except AttributeError:
        pass

    try:
        dll.SteamAPI_ISteamUserStats_GetLeaderboardEntryCount.restype = ctypes.c_int
        dll.SteamAPI_ISteamUserStats_GetLeaderboardEntryCount.argtypes = [
            ctypes.c_void_p,
            ctypes.c_uint64,
        ]
    except AttributeError:
        pass


class _DownloadLeaderboardEntriesResult(ctypes.Structure):
    """LeaderboardScoresDownloaded_t call result."""
    _fields_ = [
        ("m_hSteamLeaderboard", ctypes.c_uint64),
        ("m_hSteamLeaderboardEntries", ctypes.c_uint64),
        ("m_cEntryCount", ctypes.c_int32),
    ]


def fetch_leaderboard_entries(
    mode: str,
    request_type: int = _LB_REQUEST_GLOBAL,
    limit: int = 5,
    timeout: float = 8.0,
) -> list[dict[str, Any]]:
    """Steam SDK üzerinden leaderboard girişlerini çek.

    Args:
        mode: Oyun modu adı ('mystery', 'classic', vs.)
        request_type: 0=Global, 1=AroundUser, 2=Friends
        limit: Maksimum giriş sayısı
        timeout: Bekleme süresi (saniye)

    Returns:
        [{"rank": int, "score": int, "steam_id": str}, ...]
    """
    if not is_available() or not _isteam_user_stats:
        return []
    lb_name = _MODE_TO_LB.get(str(mode or '').strip().lower())
    if not lb_name:
        return []

    # Gerekli fonksiyonları kur (ilk çağrıda)
    if _dll and not hasattr(_dll, '_entries_setup_done'):
        _setup_get_entries_function(_dll)
        _dll._entries_setup_done = True  # type: ignore[attr-defined]

    result_event = threading.Event()
    result_holder: list[list[dict]] = [[]]

    def _worker():
        try:
            handle = _lb_handle_cache.get(lb_name)
            if not handle:
                handle = _find_leaderboard_handle_by_api(lb_name, timeout=min(5.0, timeout * 0.6))
            if not handle:
                result_event.set()
                return

            safe_limit = max(1, min(int(limit), 100))
            range_start = 1
            range_end = safe_limit
            if int(request_type) == _LB_REQUEST_FRIENDS:
                # Steamworks'te RequestFriends için range parametreleri yok sayılır;
                # -1/-1 kullanmak global liste sızıntısı riskini azaltır.
                range_start = -1
                range_end = -1
            elif int(request_type) == _LB_REQUEST_AROUND_USER:
                half = max(1, safe_limit // 2)
                range_start = -half
                range_end = half
            api_call = _dll.SteamAPI_ISteamUserStats_DownloadLeaderboardEntries(  # type: ignore[union-attr]
                _isteam_user_stats,
                ctypes.c_uint64(handle),
                request_type,
                range_start,
                range_end,
            )
            if not api_call:
                print(f"[Steam] DownloadLeaderboardEntries çağrı başarısız: {lb_name}")
                result_event.set()
                return

            # LeaderboardScoresDownloaded_t callback'ini bekle (k_iSteamUserStatsCallbacks + 5 = 1105)
            _CB_LEADERBOARD_SCORES_DOWNLOADED = 1105
            download_result = _DownloadLeaderboardEntriesResult()
            confirmed = _get_api_call_result(
                api_call, download_result, _CB_LEADERBOARD_SCORES_DOWNLOADED,
                timeout=min(timeout, 8.0))

            if not confirmed:
                print(f"[Steam] DownloadLeaderboardEntries callback timeout: {lb_name}")
                result_event.set()
                return

            entry_count = confirmed.m_cEntryCount
            entries_handle = confirmed.m_hSteamLeaderboardEntries

            if entry_count <= 0 or not entries_handle:
                print(f"[Steam] Leaderboard boş veya handle yok: {lb_name} (count={entry_count})")
                result_event.set()
                return

            # Her girişi oku
            entries: list[dict[str, Any]] = []
            for idx in range(min(entry_count, safe_limit)):
                entry = _LeaderboardEntry()
                try:
                    ok = _dll.SteamAPI_ISteamUserStats_GetDownloadedLeaderboardEntry(  # type: ignore[union-attr]
                        _isteam_user_stats,
                        ctypes.c_uint64(entries_handle),
                        idx,
                        ctypes.byref(entry),
                        None,  # pDetails
                        0,     # cDetailsMax
                    )
                    if ok:
                        entries.append({
                            "rank": int(entry.m_nGlobalRank),
                            "score": int(entry.m_nScore),
                            "steam_id": str(entry.m_steamIDUser),
                        })
                except Exception as e:
                    print(f"[Steam] GetDownloadedLeaderboardEntry[{idx}] hatası: {e}")

            result_holder[0] = entries
            print(f"[Steam] SDK leaderboard OK: {lb_name} -> {len(entries)} giris")

        except Exception as e:
            print(f"[Steam] fetch_leaderboard_entries hatası: {e}")
        finally:
            result_event.set()

    t_worker = threading.Thread(target=_worker, daemon=True)
    t_worker.start()
    result_event.wait(timeout=timeout + 1)
    return result_holder[0]


def fetch_global_scores(mode: str, limit: int = 5) -> list[dict[str, Any]]:
    """Global leaderboard skorlarını Steam SDK üzerinden al."""
    return fetch_leaderboard_entries(mode, request_type=_LB_REQUEST_GLOBAL, limit=limit)


def fetch_friend_scores(mode: str, limit: int = 5) -> list[dict[str, Any]]:
    """Arkadaş leaderboard skorlarını Steam SDK üzerinden al."""
    return fetch_leaderboard_entries(mode, request_type=_LB_REQUEST_FRIENDS, limit=limit)


# ---------------------------------------------------------------------------
# Steam Overlay API — Windows + macOS uyumlu
# ---------------------------------------------------------------------------

def activate_game_overlay(panel: str = 'Friends') -> bool:
    """Steam oyun içi overlay'ı aç.

    Args:
        panel: Açılacak overlay paneli. Geçerli değerler:
            'Friends', 'Community', 'Players', 'Settings',
            'OfficialGameGroup', 'Stats', 'Achievements'

    Returns:
        True → overlay çağrısı başarılı, False → Steam mevcut değil.
    """
    if not is_available() or not _dll or not _isteam_friends:
        return False
    try:
        panel_bytes = panel.encode('utf-8') if isinstance(panel, str) else panel
        _dll.SteamAPI_ISteamFriends_ActivateGameOverlay(_isteam_friends, panel_bytes)
        print(f"[Steam] Overlay açıldı: {panel}")
        return True
    except Exception as e:
        print(f"[Steam] ActivateGameOverlay hatası: {e}")
        return False


def activate_game_overlay_invite_dialog(lobby_id: int) -> bool:
    """Steam davet overlay dialogunu aç (lobby ID ile).

    Bu fonksiyon doğrudan Steam API'nin ISteamFriends arayüzünü
    kullanarak arkadaş davet penceresi açar — C++ bridge gerektirmez.

    Args:
        lobby_id: Davet edilecek lobinin Steam ID'si.

    Returns:
        True → başarılı.
    """
    if not is_available() or not _dll or not _isteam_friends:
        return False
    try:
        _dll.SteamAPI_ISteamFriends_ActivateGameOverlayInviteDialog(
            _isteam_friends, ctypes.c_uint64(lobby_id))
        print(f"[Steam] Davet overlay açıldı: lobby={lobby_id}")
        return True
    except Exception as e:
        print(f"[Steam] ActivateGameOverlayInviteDialog hatası: {e}")
        return False


def activate_game_overlay_to_user(action: str, steam_id: int) -> bool:
    """Belirli bir kullanıcıya yönelik Steam overlay'ı aç.

    Args:
        action: 'steamid', 'chat', 'jointrade', 'stats', 'achievements', 'friendadd', 'friendremove', 'friendrequestaccept', 'friendrequestignore'
        steam_id: Hedef kullanıcının Steam ID'si.

    Returns:
        True → başarılı.
    """
    if not is_available() or not _dll or not _isteam_friends:
        return False
    try:
        action_bytes = action.encode('utf-8') if isinstance(action, str) else action
        _dll.SteamAPI_ISteamFriends_ActivateGameOverlayToUser(
            _isteam_friends, action_bytes, ctypes.c_uint64(steam_id))
        print(f"[Steam] Overlay açıldı: {action} → {steam_id}")
        return True
    except Exception as e:
        print(f"[Steam] ActivateGameOverlayToUser hatası: {e}")
        return False
