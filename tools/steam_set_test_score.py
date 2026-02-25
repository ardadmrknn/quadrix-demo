"""Steam leaderboard'a test skoru yazmak için hızlı yardımcı script.

Kullanım (PowerShell):
  $env:STEAM_APP_ID="123456"
  $env:STEAM_WEB_API_KEY="PUBLISHER_KEY"
  py tools/steam_set_test_score.py --mode mystery --steamid 7656119XXXXXXXXXX --score 12345

Not:
- Bu script publisher key kullanır, sadece geliştirici ortamında çalıştırılmalıdır.
- Leaderboard write ayarı Trusted ise server-side yazım için uygundur.
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import requests

STEAM_WEB_API_BASE = "https://partner.steam-api.com"

MODE_TO_LEADERBOARD = {
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


def _require_env(name: str) -> str:
    value = (os.getenv(name, "") or "").strip()
    if not value:
        print(f"[HATA] {name} tanımlı değil.")
        sys.exit(1)
    return value


def _sanitize_url(url: str) -> str:
    try:
        parts = urlsplit(url)
        query = parse_qsl(parts.query, keep_blank_values=True)
        sanitized = []
        for key, value in query:
            if key.lower() == "key":
                sanitized.append((key, "***"))
            else:
                sanitized.append((key, value))
        return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(sanitized), parts.fragment))
    except Exception:
        return url


def _get(endpoint: str, *, key: str, app_id: int, timeout: float = 8.0, **params: Any) -> dict[str, Any]:
    url = f"{STEAM_WEB_API_BASE}/{endpoint}"
    merged = {"key": key, "appid": app_id, **params}
    response = requests.get(url, params=merged, timeout=timeout)
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        safe_url = _sanitize_url(response.url or url)
        code = response.status_code
        if code == 403:
            raise RuntimeError(
                "Steam API 403 Forbidden. Olası nedenler: "
                "(1) STEAM_WEB_API_KEY publisher key değil, "
                "(2) key bu AppID için yetkili değil, "
                "(3) AppID yanlış. "
                f"URL={safe_url}"
            ) from exc
        raise RuntimeError(f"Steam API HTTP {code}: {safe_url}") from exc
    payload = response.json() if response.content else {}
    return payload if isinstance(payload, dict) else {}


def _post(endpoint: str, *, key: str, app_id: int, timeout: float = 8.0, **params: Any) -> dict[str, Any]:
    url = f"{STEAM_WEB_API_BASE}/{endpoint}"
    merged = {"key": key, "appid": app_id, **params}
    response = requests.post(url, data=merged, timeout=timeout)
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        safe_url = _sanitize_url(response.url or url)
        code = response.status_code
        if code == 403:
            raise RuntimeError(
                "Steam API 403 Forbidden. Olası nedenler: "
                "(1) STEAM_WEB_API_KEY publisher key değil, "
                "(2) key bu AppID için yetkili değil, "
                "(3) AppID yanlış. "
                f"URL={safe_url}"
            ) from exc
        raise RuntimeError(f"Steam API HTTP {code}: {safe_url}") from exc
    payload = response.json() if response.content else {}
    return payload if isinstance(payload, dict) else {}


def _extract_leaderboard_id(raw: Any) -> int | None:
    candidates: list[Any] = []
    if isinstance(raw, dict):
        candidates.extend(
            [
                raw.get("leaderboardid"),
                raw.get("leaderboard_id"),
                raw.get("id"),
            ]
        )
    else:
        candidates.append(raw)

    for value in candidates:
        try:
            if value is None:
                continue
            return int(value)
        except Exception:
            continue
    return None


def _find_leaderboard_id(*, key: str, app_id: int, leaderboard_name: str) -> int | None:
    payload = _get(
        "ISteamLeaderboards/FindLeaderboard/v1/",
        key=key,
        app_id=app_id,
        name=leaderboard_name,
    )
    response = payload.get("response", {}) if isinstance(payload, dict) else {}
    if not isinstance(response, dict):
        return None

    direct_id = _extract_leaderboard_id(response)
    if direct_id is not None:
        return direct_id

    nested = response.get("leaderboard")
    return _extract_leaderboard_id(nested)


def _load_leaderboard_id(*, key: str, app_id: int, mode: str) -> int:
    mode_key = mode.strip().lower()
    lb_name = MODE_TO_LEADERBOARD.get(mode_key)
    if not lb_name:
        raise RuntimeError(f"Desteklenmeyen mod: {mode}")

    payload = _get("ISteamLeaderboards/GetLeaderboardsForGame/v2/", key=key, app_id=app_id)
    response = payload.get("response", {}) if isinstance(payload, dict) else {}
    boards = response.get("leaderboards", []) if isinstance(response, dict) else []

    available_names: list[str] = []
    matched_invalid_ids: list[str] = []
    for board in boards:
        if not isinstance(board, dict):
            continue
        name = str(board.get("name", "") or "").strip()
        if name:
            available_names.append(name)
        if name != lb_name:
            continue
        lb_id = _extract_leaderboard_id(board)
        if lb_id is not None:
            return lb_id
        matched_invalid_ids.append(str(board.get("leaderboardid")))

    fallback_id = _find_leaderboard_id(key=key, app_id=app_id, leaderboard_name=lb_name)
    if fallback_id is not None:
        return fallback_id

    if matched_invalid_ids:
        raise RuntimeError(
            f"Steam leaderboard bulundu ama leaderboardid geçersiz: {lb_name}. "
            f"Dönen değer(ler): {', '.join(matched_invalid_ids)}"
        )

    preview = ", ".join(sorted(set(available_names))[:20])
    if preview:
        raise RuntimeError(
            f"Steam leaderboard bulunamadı: {lb_name}. "
            f"Bu AppID ({app_id}) için bulunan isimler: {preview}"
        )
    raise RuntimeError(
        f"Steam leaderboard bulunamadı: {lb_name}. "
        f"Bu AppID ({app_id}) için hiç leaderboard dönmedi."
    )


def _read_app_id_from_file() -> str:
    try:
        from pathlib import Path
        p = Path(__file__).resolve().parents[1] / "steam_appid.txt"
        if p.exists():
            return p.read_text(encoding="utf-8").strip()
    except Exception:
        pass
    return ""


def main() -> int:
    parser = argparse.ArgumentParser(description="Steam leaderboard test score yaz")
    parser.add_argument("--mode", default="mystery", help="Mod adı (varsayılan: mystery)")
    parser.add_argument("--steamid", default="76561199351154071", help="Skor yazılacak SteamID64")
    parser.add_argument("--score", type=int, default=99999, help="Yazılacak skor (varsayılan: 99999)")
    parser.add_argument(
        "--scoremethod",
        default="KeepBest",
        choices=["KeepBest", "ForceUpdate"],
        help="Steam güncelleme yöntemi",
    )
    parser.add_argument("--show-top", type=int, default=5, help="Yazım sonrası gösterilecek top N")
    args = parser.parse_args()

    # App ID: steam_appid.txt'den veya env'den oku
    app_id_raw = (os.getenv("STEAM_APP_ID", "") or "").strip() or _read_app_id_from_file()
    if not app_id_raw:
        app_id_raw = input("STEAM_APP_ID (örn: 4428040): ").strip()
    try:
        app_id = int(app_id_raw)
    except Exception:
        print(f"[HATA] Geçersiz STEAM_APP_ID: {app_id_raw!r}")
        return 1

    # Key: her zaman interaktif sor
    key = input("STEAM_WEB_API_KEY (Publisher Key): ").strip().strip('"').strip("'").rstrip(",;").strip()
    if not key:
        print("[HATA] STEAM_WEB_API_KEY boş olamaz.")
        return 1

    try:
        leaderboard_id = _load_leaderboard_id(key=key, app_id=app_id, mode=args.mode)
    except Exception as exc:
        print(f"[HATA] {exc}")
        return 2

    try:
        # Steam Web API scoremethod parametresini STRING olarak bekler: "KeepBest" / "ForceUpdate"
        result = _post(
            "ISteamLeaderboards/SetLeaderboardScore/v1/",
            key=key,
            app_id=app_id,
            leaderboardid=leaderboard_id,
            steamid=str(args.steamid).strip(),
            score=int(args.score),
            scoremethod=args.scoremethod,
        )
        response_obj = result.get("result", {}) if isinstance(result, dict) else {}
        if not isinstance(response_obj, dict):
            response_obj = {}
        raw_result_code = response_obj.get("result")
        result_code = None
        try:
            result_code = int(raw_result_code)
        except Exception:
            pass

        if result_code is not None and result_code != 1:
            print("[HATA] Skor yazma Steam tarafından reddedildi.")
            print(result)
            return 4

        print("[OK] Skor yazma çağrısı gönderildi.")
        print(result)
    except Exception as exc:
        print(f"[HATA] Skor yazılamadı: {exc}")
        return 3

    try:
        top_n = max(1, min(int(args.show_top), 20))
        payload = _get(
            "ISteamLeaderboards/GetLeaderboardEntries/v1/",
            key=key,
            app_id=app_id,
            leaderboardid=leaderboard_id,
            datarequest=0,  # 0=RequestGlobal (integer)
            rangestart=1,
            rangeend=top_n,
        )
        response = payload.get("response", {}) if isinstance(payload, dict) else {}
        entries = []
        if isinstance(response, dict):
            entries = response.get("entries") or response.get("leaderboardEntries") or []

        if not entries:
            try:
                payload = _get(
                    "ISteamLeaderboards/GetLeaderboardEntries/v1/",
                    key=key,
                    app_id=app_id,
                    leaderboardid=leaderboard_id,
                    datarequest=0,  # 0=RequestGlobal (integer)
                    rangestart=1,
                    rangeend=top_n,
                )
                response = payload.get("response", {}) if isinstance(payload, dict) else {}
                if isinstance(response, dict):
                    entries = response.get("entries") or response.get("leaderboardEntries") or []
            except Exception:
                pass

        if not isinstance(entries, list):
            entries = []
        print(f"[TOP {top_n}] {args.mode}:")
        for e in entries:
            rank = e.get("rank")
            score = e.get("score")
            steam_id = e.get("steamid") or e.get("steam_id")
            print(f"  #{rank}  score={score}  steamid={steam_id}")
    except Exception as exc:
        print(f"[UYARI] Top skor okunamadı: {exc}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
