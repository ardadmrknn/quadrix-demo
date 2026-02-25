"""Leaderboard konfigürasyonunu ve yazma yetkisini tanılar.

Kullanım:
  $env:STEAM_APP_ID="4428040"
  $env:STEAM_WEB_API_KEY="PUBLISHER_KEY"
  py tools/steam_diag_leaderboard.py
"""
from __future__ import annotations

import os
import sys
from typing import Any

import requests

STEAM_WEB_API_BASE = "https://partner.steam-api.com"

# Steam ELeaderboardSortMethod
SORT_METHOD = {0: "None", 1: "Ascending (düşük iyi)", 2: "Descending (yüksek iyi)"}
# Steam ELeaderboardDisplayType
DISPLAY_TYPE = {0: "None", 1: "Numeric", 2: "TimeSeconds", 3: "TimeMilliSeconds"}
# Steam ELeaderboardUploadScoreMethod
WRITE_TYPE = {
    0: "None (yazma yok!)",
    1: "KeepBest",
    2: "ForceUpdate",
    3: "Trusted (sadece server API)",
}

# result:8'in anlamları
RESULT_CODES = {
    1: "OK",
    2: "Fail",
    8: "InvalidParam — genellikle: Writes!=Trusted veya yanlış steamid/score",
    9: "DuplicateName",
    11: "AccessDenied",
    15: "Expired",
    16: "Duplicate",
    18: "ServiceUnavailable",
    42: "Pending",
}


def _get(endpoint: str, *, key: str, app_id: int, **params: Any) -> dict[str, Any]:
    url = f"{STEAM_WEB_API_BASE}/{endpoint}"
    merged = {"key": key, "appid": app_id, **params}
    resp = requests.get(url, params=merged, timeout=10)
    print(f"  [HTTP {resp.status_code}] GET {endpoint}")
    resp.raise_for_status()
    return resp.json() if resp.content else {}


def _post(endpoint: str, *, key: str, app_id: int, **params: Any) -> dict[str, Any]:
    url = f"{STEAM_WEB_API_BASE}/{endpoint}"
    merged = {"key": key, "appid": app_id, **params}
    resp = requests.post(url, data=merged, timeout=10)
    print(f"  [HTTP {resp.status_code}] POST {endpoint}")
    resp.raise_for_status()
    return resp.json() if resp.content else {}


def _prompt_if_empty(env_name: str, prompt_text: str) -> str:
    value = (os.getenv(env_name, "") or "").strip().strip('"').strip("'").rstrip(",;").strip()
    if value:
        return value
    try:
        value = input(f"{prompt_text}: ").strip()
    except (EOFError, KeyboardInterrupt):
        value = ""
    return value.strip('"').strip("'").rstrip(",;").strip()


def main() -> int:
    app_id_raw = _prompt_if_empty("STEAM_APP_ID", "STEAM_APP_ID (örn: 4428040)")
    key = _prompt_if_empty("STEAM_WEB_API_KEY", "STEAM_WEB_API_KEY (Publisher Key)")

    if not app_id_raw:
        print("[HATA] STEAM_APP_ID boş olamaz.")
        return 1
    if not key:
        print("[HATA] STEAM_WEB_API_KEY boş olamaz.")
        return 1

    try:
        app_id = int(app_id_raw)
    except Exception:
        print("[HATA] STEAM_APP_ID sayı olmalı.")
        return 1

    print(f"\n{'='*55}")
    print(f"  Quadrix Steam Leaderboard Tanısı")
    print(f"  AppID: {app_id}")
    print(f"  Key: {key[:6]}...{key[-4:]}  (gizlendi)")
    print(f"{'='*55}\n")

    # 1. Tüm leaderboard listesi
    print("[1] GetLeaderboardsForGame çağrılıyor...")
    try:
        payload = _get("ISteamLeaderboards/GetLeaderboardsForGame/v2/", key=key, app_id=app_id)
    except Exception as exc:
        print(f"    [HATA] {exc}")
        return 2

    response = payload.get("response", {}) if isinstance(payload, dict) else {}
    boards = response.get("leaderboards", []) if isinstance(response, dict) else []
    print(f"    Toplam leaderboard: {len(boards)}")

    target_names = [
        "quadrix_mystery", "quadrix_classic", "quadrix_sprint",
        "quadrix_ultra", "quadrix_zen", "quadrix_survival",
    ]
    target_boards: dict[str, dict] = {}
    for board in boards:
        name = str(board.get("name", "") or "")
        if name in target_names:
            target_boards[name] = board

    # Ham alanları görmek için ilk boardı yazdır
    if boards:
        print(f"    Ham alan adları (ilk board): {list(boards[0].keys())}")
        print(f"    Ham değerler (ilk board): {boards[0]}")
        print()

    if not target_boards:
        available = sorted(str(b.get("name", "")) for b in boards if b.get("name"))
        print(f"    [UYARI] Hedef leaderboard'lar bulunamadı!")
        print(f"    Bulunan isimler: {', '.join(available[:20])}")

    print()
    for name in target_names:
        board = target_boards.get(name)
        if not board:
            print(f"  ✗ {name:30s} BULUNAMADI")
            continue

        lb_id = board.get("id") or board.get("leaderboardid")
        sort_raw = board.get("sortmethod", "?")
        display_raw = board.get("displaytype", "?")
        only_trusted_writes = board.get("onlytrustedwrites", None)
        only_friends_reads = board.get("onlyfriendsreads", None)
        limit_global = board.get("limitglobaltopentries", 0)

        writes_ok = only_trusted_writes is True
        reads_ok = only_friends_reads is False

        writes_str = "Trusted ✓" if writes_ok else ("Trusted=False ✗ (değiştir!)" if only_trusted_writes is False else f"bilinmiyor({only_trusted_writes})")
        reads_str = "Global ✓" if reads_ok else ("Sadece Arkadaşlar ✗ (değiştir!)" if only_friends_reads is True else f"bilinmiyor({only_friends_reads})")
        limit_str = f"  LimitGlobalTop={limit_global}" if limit_global else ""

        overall_ok = writes_ok and reads_ok
        status = "✓ OK" if overall_ok else "✗ SORUN VAR"
        print(f"  {status} | {name}")
        print(f"           ID={lb_id}  Sort={sort_raw}  Display={display_raw}")
        print(f"           Writes={writes_str}  Reads={reads_str}{limit_str}")

    # 2. quadrix_mystery üzerine FindLeaderboard testi
    print()
    print("[2] FindLeaderboard testi (quadrix_mystery)...")
    try:
        payload2 = _get("ISteamLeaderboards/FindLeaderboard/v1/", key=key, app_id=app_id, name="quadrix_mystery")
        resp2 = payload2.get("response", {}) if isinstance(payload2, dict) else {}
        lb_id2 = resp2.get("leaderboardid") or resp2.get("id")
        print(f"    leaderboardid: {lb_id2}")
        print(f"    Tam cevap: {resp2}")
    except Exception as exc:
        print(f"    [HATA] {exc}")

    # 3. Test yazma denemesi (scoremethond=1=KeepBest)
    print()
    TEST_STEAM_ID = _prompt_if_empty("TEST_STEAM_ID", "Test SteamID64 (senin Steam hesabın, oyunda gözükmeli)")
    if not TEST_STEAM_ID:
        TEST_STEAM_ID = "76561199351154071"
    print(f"[3] SetLeaderboardScore denemesi (steamid={TEST_STEAM_ID}, score=1)...")
    mystery_board = target_boards.get("quadrix_mystery")
    if mystery_board:
        lb_id3 = mystery_board.get("leaderboardid") or mystery_board.get("id")
        try:
            write_payload = _post(
                "ISteamLeaderboards/SetLeaderboardScore/v1/",
                key=key,
                app_id=app_id,
                leaderboardid=lb_id3,
                steamid=TEST_STEAM_ID,
                score=1,
                scoremethod=1,  # 1=KeepBest
            )
            result_obj = write_payload.get("result", {}) if isinstance(write_payload, dict) else {}
            result_code = None
            try:
                result_code = int(result_obj.get("result", -1))
            except Exception:
                pass
            meaning = RESULT_CODES.get(result_code, "bilinmiyor")
            icon = "✓" if result_code == 1 else "✗"
            print(f"    {icon} result={result_code} ({meaning})")
            print(f"    Tam cevap: {result_obj}")
        except Exception as exc:
            print(f"    [HATA] {exc}")
    else:
        print("    quadrix_mystery bulunamadığı için atlandı.")

    # 4. Test okuma denemesi (datarequest=0=Global, rangestart=1, rangeend=5)
    print()
    print("[4] GetLeaderboardEntries denemesi (datarequest=0/Global, range=1-5)...")
    if mystery_board:
        lb_id4 = mystery_board.get("leaderboardid") or mystery_board.get("id")
        for dr_int, dr_name in [(0, "Global"), (1, "AroundUser"), (2, "Friends")]:
            try:
                extra: dict[str, Any] = {}
                if dr_int in (1, 2):
                    extra["steamid"] = TEST_STEAM_ID
                read_payload = _get(
                    "ISteamLeaderboards/GetLeaderboardEntries/v1/",
                    key=key,
                    app_id=app_id,
                    leaderboardid=lb_id4,
                    datarequest=dr_int,
                    rangestart=1,
                    rangeend=5,
                    **extra,
                )
                resp4 = read_payload.get("response", {}) if isinstance(read_payload, dict) else {}
                entry_count = resp4.get("totalleaderboardentries", resp4.get("total", "?"))
                entries = resp4.get("entries") or resp4.get("leaderboardEntries") or []
                print(f"    datarequest={dr_int}({dr_name}): totalEntries={entry_count}, entries={len(entries) if isinstance(entries, list) else entries}")
            except Exception as exc:
                print(f"    datarequest={dr_int}({dr_name}): [HATA] {exc}")
    else:
        print("    quadrix_mystery bulunamadığı için atlandı.")

    print()
    print("="*55)
    print("  GEREKLİ STEAMWORKS AYARLARI (tüm leaderboard'lar için):")
    print("  Leaderboard adı : quadrix_mystery (ve diğerleri)")
    print("  Sort Method     : Descending")
    print("  Display Type    : Numeric")
    print("  Writes          : Trusted  (onlytrustedwrites=True) ← publisher API")
    print("  Reads           : Global   (onlyfriendsreads=False) ← herkese açık")
    print()
    print("  Steamworks → Uygulama 4428040 → Stats & Achievements")
    print("  → Leaderboards → düzenle → 'Okumalar' = Global (boş/-)")
    print("  → Publish Changes")
    print()
    print("  result=8 hâlâ geliyorsa: test SteamID playteste erişimi olmayabilir.")
    print("  Kendi geliştirici SteamID'nle dene.")
    print("="*55)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
