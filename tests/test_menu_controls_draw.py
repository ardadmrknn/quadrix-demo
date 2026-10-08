"""Kontroller paneli (ControlSettingsScreen) çizim yolu için regresyon kapsamı.

OP-023 panel/sekme/satır zemin önbelleği hiçbir mevcut testle çizilmiyordu;
bu dosya o yolu çalıştırır: çok kare draw + sekme geçişi + seçim değişimi
(farklı tab_bg/row_bg anahtarları). Kurulum deseni
test_menu_mode_music_highscore_containment.py ile aynı (stub + dummy sürücü).
"""
from __future__ import annotations

import os
import pathlib
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


def _nested_config(tab_keys) -> dict:
    """'pvp.player1' gibi noktalı sekme anahtarları için iç içe sözlük."""
    cfg: dict = {}
    for tab_key in tab_keys:
        node = cfg
        parts = tab_key.split(".")
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = {}
    return cfg


def test_control_settings_screen_draw_multiple_frames():
    pygame.init()
    try:
        from menu import ControlSettingsScreen, get_control_tabs

        control_config = _nested_config(key for key, _ in get_control_tabs())

        class _SettingsManagerStub:
            def get_controls(self):
                return control_config

        surface = pygame.Surface((1280, 720), pygame.SRCALPHA)
        screen = ControlSettingsScreen(surface, _SettingsManagerStub())

        for _ in range(3):
            screen.draw()
        cache = getattr(screen, "_controls_surface_cache", None)
        assert cache, "kontrol paneli yuzey onbellegi kurulmali"
        entry_count = len(cache)

        # Sekme geçişi (gamepad olmayan) + seçim değişimi: farklı
        # tab_bg/row_bg anahtarları hatasız üretilmeli.
        next_tab = next(
            (i for i, (key, _) in enumerate(get_control_tabs()) if key != "gamepad" and i != 0),
            None,
        )
        if next_tab is not None:
            screen.active_tab = next_tab
        screen.selected_action = 1
        for _ in range(3):
            screen.draw()
        assert len(screen._controls_surface_cache) >= entry_count
    finally:
        pygame.quit()
