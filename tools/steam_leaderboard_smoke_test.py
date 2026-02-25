"""Secure leaderboard backend bağlantı testi.

Kullanım:
    python tools/steam_leaderboard_smoke_test.py

Gerekli ortam değişkenleri:
    LEADERBOARD_BACKEND_URL

Opsiyonel:
    LEADERBOARD_CLIENT_TOKEN
    LEADERBOARD_SESSION_TOKEN (friends testi için)
"""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from steam_leaderboards import DEFAULT_MODE_TO_LEADERBOARD, SteamLeaderboardService


def main() -> int:
    service = SteamLeaderboardService()
    if not service.is_configured():
        print("[HATA] LEADERBOARD_BACKEND_URL tanımlı değil.")
        return 1

    print(f"[OK] Backend: {service.backend_base_url}")
    print("[INFO] Desteklenen mod sayısı:", len(DEFAULT_MODE_TO_LEADERBOARD))

    modes = [
        "classic", "sprint", "ultra", "zen", "mystery",
        "survival", "cascade", "wide", "hardcore", "daily", "tetris2",
    ]
    scores = service.fetch_all_mode_highscores(modes, limit=3)

    for mode in modes:
        print(f"\n=== {mode.upper()} ===")
        entries = scores.get(mode, [])
        if not entries:
            if service.last_error:
                print(f"(veri yok) neden: {service.last_error}")
            else:
                print("(veri yok)")
            continue

        for entry in entries:
            rank = entry.get("rank", "-")
            score = entry.get("score", 0)
            steam_id = entry.get("steam_id", "")
            print(f"#{rank}  score={score}  steamid={steam_id}")

    print("\n=== FRIENDS / MYSTERY ===")
    friend_entries = service.fetch_mode_friend_highscores("mystery", limit=3)
    if not friend_entries:
        print(f"(veri yok) neden: {service.last_error or 'oturum veya veri yok'}")
    else:
        for entry in friend_entries:
            print(f"#{entry.get('rank')}  score={entry.get('score')}  steamid={entry.get('steam_id')}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
