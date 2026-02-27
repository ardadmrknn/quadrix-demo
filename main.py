"""Wrapper to run the src/main.py from repository root.

PyInstaller uyumluluğu için giriş noktası modül importu ile çalıştırılır;
böylece bağımlılıklar analiz sırasında doğru tespit edilir.
Run from repo root with: py -3 main.py
"""
import os
import sys


os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")


def _apply_leaderboard_cli_overrides(argv: list[str]) -> None:
    """Apply leaderboard proxy configuration from CLI.

    Steamworks Launch Options üzerinden tüm oyunculara dağıtmak için kullanılır.

    Supported:
    - --leaderboard-backend-url=<url>
    - --leaderboard-backend-url <url>
    - --leaderboard-client-token=<token>
    - --leaderboard-client-token <token>
    """

    def _clean_value(value: str) -> str:
        raw = str(value or "").strip()
        if (raw.startswith('"') and raw.endswith('"')) or (raw.startswith("'") and raw.endswith("'")):
            raw = raw[1:-1].strip()
        return raw

    def _pop_value(i: int) -> tuple[str, int]:
        if i + 1 < len(argv):
            return argv[i + 1], 2
        return "", 1

    i = 0
    while i < len(argv):
        raw = str(argv[i] or "").strip()
        if raw.startswith("--leaderboard-backend-url="):
            value = _clean_value(raw.split("=", 1)[1])
            if value and not value.startswith("--"):
                os.environ["LEADERBOARD_BACKEND_URL"] = value
        elif raw == "--leaderboard-backend-url":
            value, consumed = _pop_value(i)
            value = _clean_value(value)
            if value and not value.startswith("--"):
                os.environ["LEADERBOARD_BACKEND_URL"] = value
            i += consumed - 1
        elif raw.startswith("--leaderboard-client-token="):
            value = _clean_value(raw.split("=", 1)[1])
            if value and not value.startswith("--"):
                os.environ["LEADERBOARD_CLIENT_TOKEN"] = value
        elif raw == "--leaderboard-client-token":
            value, consumed = _pop_value(i)
            value = _clean_value(value)
            if value and not value.startswith("--"):
                os.environ["LEADERBOARD_CLIENT_TOKEN"] = value
            i += consumed - 1
        i += 1


if __name__ == "__main__":
    # Repo root dizinine git (bat/sh ile aynı davranış)
    repo_root = os.path.dirname(os.path.abspath(__file__))
    os.chdir(repo_root)  # CWD'yi repo root'a değiştir

    # Steam Launch Options ile proxy adresi/token verildiyse env'e uygula.
    # Not: Bu satır import'lardan önce olmalı ki tüm alt modüller env'i görsün.
    try:
        _apply_leaderboard_cli_overrides(sys.argv[1:])
    except Exception:
        pass

    # Ensure repo root is on the Python path so "src" package resolves.
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    try:
        from src.main import main as game_main

        game_main()
    except KeyboardInterrupt:
        # Ctrl+C ile çıkış: traceback yerine temiz kapanış
        try:
            import pygame
            pygame.quit()
        except Exception:
            pass
        print("\n[EXIT] KeyboardInterrupt (Ctrl+C) - temiz çıkış.")
        raise SystemExit(0)
