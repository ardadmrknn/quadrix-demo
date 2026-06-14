# -*- coding: utf-8 -*-
import os, sys, time, ctypes, urllib.request, urllib.parse, json, random
import pytest

APP_ID = 4428040
LB_ID_MYSTERY = 19198572


def test_leaderboard_write():
    """Steam liderlik tablosuna yazma testi (yalnizca Windows + Steam acikken calisir)."""
    publisher_key = os.environ.get("STEAM_WEB_API_KEY", "").strip()
    if not publisher_key:
        pytest.skip("STEAM_WEB_API_KEY tanimli degil; partner API yazma testi atlandi")

    if sys.platform != "win32":
        pytest.skip("Bu test yalnizca Windows'ta calisir")

    dll_path = "dll/win64/steam_api64.dll"
    if not os.path.exists(dll_path):
        pytest.skip(f"DLL bulunamadi: {dll_path}")

    os.environ.setdefault("SteamAppId", "4428040")

    try:
        dll = ctypes.CDLL(dll_path)
    except OSError as e:
        pytest.skip(f"DLL yuklenemedi: {e}")

    dll.SteamAPI_InitFlat.restype = ctypes.c_int; dll.SteamAPI_InitFlat.argtypes = [ctypes.c_char_p]
    dll.SteamAPI_RunCallbacks.restype = None; dll.SteamAPI_RunCallbacks.argtypes = []
    dll.SteamAPI_SteamUserStats_v013.restype = ctypes.c_void_p; dll.SteamAPI_SteamUserStats_v013.argtypes = []
    dll.SteamAPI_SteamUtils_v010.restype = ctypes.c_void_p; dll.SteamAPI_SteamUtils_v010.argtypes = []
    dll.SteamAPI_SteamUser_v023.restype = ctypes.c_void_p; dll.SteamAPI_SteamUser_v023.argtypes = []
    dll.SteamAPI_ISteamUser_GetSteamID.restype = ctypes.c_uint64; dll.SteamAPI_ISteamUser_GetSteamID.argtypes = [ctypes.c_void_p]
    dll.SteamAPI_ISteamUserStats_FindLeaderboard.restype = ctypes.c_uint64
    dll.SteamAPI_ISteamUserStats_FindLeaderboard.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
    dll.SteamAPI_ISteamUtils_GetAPICallResult.restype = ctypes.c_bool
    dll.SteamAPI_ISteamUtils_GetAPICallResult.argtypes = [ctypes.c_void_p, ctypes.c_uint64, ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_bool)]
    dll.SteamAPI_ISteamUserStats_UploadLeaderboardScore.restype = ctypes.c_uint64
    dll.SteamAPI_ISteamUserStats_UploadLeaderboardScore.argtypes = [ctypes.c_void_p, ctypes.c_uint64, ctypes.c_int, ctypes.c_int32, ctypes.c_void_p, ctypes.c_int]
    dll.SteamAPI_Shutdown.restype = None; dll.SteamAPI_Shutdown.argtypes = []

    print("=" * 55)
    errmsg = ctypes.create_string_buffer(1024)
    r = dll.SteamAPI_InitFlat(errmsg)
    print(f"[1] Init={r} (0=OK)")
    if r != 0:
        print("HATA: Steam acik degil")
        pytest.skip("Steam acik degil, test atlaniyor")

    sptr = dll.SteamAPI_SteamUserStats_v013()
    uptr = dll.SteamAPI_SteamUtils_v010()
    steam_id = dll.SteamAPI_ISteamUser_GetSteamID(dll.SteamAPI_SteamUser_v023())
    print(f"[2] stats={sptr}  utils={uptr}  SteamID={steam_id}")
    api_call = dll.SteamAPI_ISteamUserStats_FindLeaderboard(sptr, b"quadrix_mystery")

    class FR(ctypes.Structure):
        _fields_ = [("m_hSteamLeaderboard", ctypes.c_uint64), ("m_bLeaderboardFound", ctypes.c_uint8)]
    fr = FR(); failed = ctypes.c_bool(False)
    for _ in range(200):
        dll.SteamAPI_RunCallbacks()
        if dll.SteamAPI_ISteamUtils_GetAPICallResult(uptr, ctypes.c_uint64(api_call), ctypes.byref(fr), ctypes.sizeof(fr), 1104, ctypes.byref(failed)): break
        time.sleep(0.05)
    lb_handle = int(fr.m_hSteamLeaderboard)
    print(f"[3] FindLB: found={fr.m_bLeaderboardFound} handle={lb_handle}")
    test_score = random.randint(5000, 99999)
    uc = dll.SteamAPI_ISteamUserStats_UploadLeaderboardScore(sptr, ctypes.c_uint64(lb_handle), 1, ctypes.c_int32(test_score), None, 0)
    print(f"[4] Upload score={test_score} api_call={uc}")

    class UR(ctypes.Structure):
        _fields_ = [("m_bSuccess", ctypes.c_uint8), ("m_hSteamLeaderboard", ctypes.c_uint64), ("m_nScore", ctypes.c_int32), ("m_bScoreChanged", ctypes.c_uint8), ("m_nGlobalRankNew", ctypes.c_int32), ("m_nGlobalRankPrevious", ctypes.c_int32)]
    ur = UR(); sdk_ok = False
    for _ in range(300):
        dll.SteamAPI_RunCallbacks()
        if dll.SteamAPI_ISteamUtils_GetAPICallResult(uptr, ctypes.c_uint64(uc), ctypes.byref(ur), ctypes.sizeof(ur), 1106, ctypes.byref(failed)):
            sdk_ok = bool(ur.m_bSuccess)
            print(f"[5] SDK: {'BASARILI rank='+str(ur.m_nGlobalRankNew) if sdk_ok else 'BASARISIZ(lisans yok)'}")
            break
        time.sleep(0.05)
    dll.SteamAPI_Shutdown()

    params = urllib.parse.urlencode({"key": publisher_key, "appid": APP_ID, "leaderboardid": LB_ID_MYSTERY, "steamid": steam_id, "score": test_score, "scoremethod": "KeepBest"}).encode()
    req = urllib.request.Request("https://partner.steam-api.com/ISteamLeaderboards/SetLeaderboardScore/v1/", data=params, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    with urllib.request.urlopen(req, timeout=10) as resp:
        body = json.loads(resp.read())
    rc = body.get("result", {}).get("result", -1)
    rank = body.get("result", {}).get("global_rank_new", 0)
    if rc == 1:
        print(f"[6] Partner API: BASARILI rank={rank}")
        print(">>> COZULDU! Build al + Steam'den oyna.")
    else:
        print(f"[6] Partner API: BASARISIZ result={rc}")
        if rc == 8:
            print(f">>> FIX: partner.steamgames.com -> 4428040 -> Packages -> Developer Comp -> Add {steam_id}")
    print("=" * 55)
    assert rc == 1, f"Partner API basarisiz: result={rc}"
