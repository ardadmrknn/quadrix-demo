"""Guide ekranı çizim yolu için regresyon kapsamı.

OP-022 iskelet önbelleği (sekme glow/zemin + maskot paneli + buton
glow/zemin) hiçbir mevcut testle çizilmiyordu; bu dosya o yolu çalıştırır:
çok kare draw + sekme geçişi + hover durumu. Kurulum deseni
test_store_card_preview.py ile aynı (runtime import + dummy sürücü).
"""
from __future__ import annotations

import os

import pygame

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')


def test_guide_draw_multiple_frames_tab_switch_and_hover():
    pygame.init()
    try:
        from guide_screen import GuideScreen

        surface = pygame.Surface((1280, 720), pygame.SRCALPHA)
        guide = GuideScreen(surface)

        # Isınma + sıcak kareler: iskelet önbelleği kurulmalı ve isabet almalı.
        for _ in range(3):
            guide.draw()
        cache = getattr(guide, '_skeleton_surface_cache', None)
        assert cache, 'iskelet onbellegi kurulmali'
        entry_count = len(cache)

        # Sekme geçişi: farklı durum yüzeyleri hatasız üretilmeli.
        guide.selected_tab = 1
        for _ in range(3):
            guide.draw()

        # Hover durumu da çizilmeli (farklı zemin/glow anahtarları).
        guide.tab_hover = 2
        guide.draw()
        assert len(guide._skeleton_surface_cache) >= entry_count
    finally:
        pygame.quit()
