"""Wrapper to run the src/main.py from repository root.

PyInstaller uyumluluğu için giriş noktası modül importu ile çalıştırılır;
böylece bağımlılıklar analiz sırasında doğru tespit edilir.
Run from repo root with: py -3 main.py
"""
import os
import sys


os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")


if __name__ == "__main__":
    # Repo root dizinine git (bat/sh ile aynı davranış)
    repo_root = os.path.dirname(os.path.abspath(__file__))
    os.chdir(repo_root)  # CWD'yi repo root'a değiştir

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
