# -*- coding: utf-8 -*-
"""Kullanıcı seçim kartları çizim yolu için regresyon kapsamı (OP-025).

_draw_user_card/_draw_add_card zemin+glow önbellekleri hiçbir mevcut testle
çizilmiyordu (test_phase4_ui_scaling select-screen'i stub'luyor). Bu dosya
kart fonksiyonlarını doğrudan çok kare çizer: önbellek kurulmalı ve sıcak
karede isabet almalı. Kalıp: SDL dummy env pygame importundan ÖNCE + SRC
yolu + __new__ bare-instance idyomu (init'siz, çizim bağımlılıkları
enjekte edilir — test_user_screens_modal_profile_budget deseni).
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

from user_screens import UserSelectionScreen

if not pygame.font.get_init():
    pygame.font.init()


USER_DATA = {
    "avatar": "__default__",
    "avatar_color": (100, 150, 255),
    "total_games": 42,
    "total_score": 123456,
}


def _make_screen():
    scr = UserSelectionScreen.__new__(UserSelectionScreen)
    scr.screen = pygame.Surface((1280, 720), pygame.SRCALPHA)
    scr._sx = lambda v, minimum=1, scale=None: max(minimum, int(v))
    scr._hovered_index = -1
    scr.card_targets = []
    # v2 font_normal_size/font_small_size (render_fit_text) kullanır;
    # quadrix-demo kart gövdesi font_normal/font_small Font nesneleri
    # kullanır — iki repo ortak testte ikisi de enjekte edilir.
    scr.font_normal_size = 18
    scr.font_small_size = 14
    # Aynı oturumda önce koşan bir test pygame.quit() yapmışsa font modülü
    # kapanır; Font() "font not initialized" verir. init idempotent'tir.
    pygame.font.init()
    scr.font_normal = pygame.font.Font(None, 18)
    scr.font_small = pygame.font.Font(None, 14)
    scr._should_use_steam_avatar_for_user = lambda user_data, is_active: False
    scr._get_steam_avatar_surface = lambda size: None
    scr._get_avatar_surface = lambda avatar, size: pygame.Surface((size, size), pygame.SRCALPHA)
    return scr


def test_user_card_surface_caches_hit_on_warm_frames():
    scr = _make_screen()
    rect = pygame.Rect(100, 100, 360, 96)

    # Isınma kareleri: zemin/glow önbellekleri kurulmalı.
    scr._draw_user_card(rect, "Arda", USER_DATA, selected=True, is_active=True, index=0)
    scr._draw_user_card(rect, "Arda", USER_DATA, selected=True, is_active=True, index=0)
    solid_cache = getattr(scr, "_solid_alpha_surface_cache", None)
    rounded_cache = getattr(scr, "_rounded_rect_surface_cache", None)
    assert solid_cache, "kart zemin onbellegi kurulmali"
    assert rounded_cache, "kart glow onbellegi kurulmali"

    solid_count = len(solid_cache)
    rounded_count = len(rounded_cache)

    # Sıcak kare: aynı durumlar isabet almalı (yeni girdi yok).
    scr._draw_user_card(rect, "Arda", USER_DATA, selected=True, is_active=True, index=0)
    assert len(scr._solid_alpha_surface_cache) == solid_count
    assert len(scr._rounded_rect_surface_cache) == rounded_count

    # Farklı durumlar (hover / seçili değil) hatasız yeni anahtar üretmeli.
    scr._hovered_index = 1
    scr._draw_user_card(rect, "Arda", USER_DATA, selected=False, is_active=False, index=1)
    assert len(scr._rounded_rect_surface_cache) > rounded_count


def test_add_card_surface_caches():
    scr = _make_screen()
    rect = pygame.Rect(100, 220, 360, 96)

    scr._draw_add_card(rect, selected=True, index=2)
    scr._draw_add_card(rect, selected=True, index=2)
    solid_cache = getattr(scr, "_solid_alpha_surface_cache", None)
    rounded_cache = getattr(scr, "_rounded_rect_surface_cache", None)
    assert solid_cache, "ekle-karti zemin onbellegi kurulmali"
    assert rounded_cache, "ekle-karti glow onbellegi kurulmali"

    solid_count = len(solid_cache)
    rounded_count = len(rounded_cache)

    scr._draw_add_card(rect, selected=True, index=2)
    assert len(scr._solid_alpha_surface_cache) == solid_count
    assert len(scr._rounded_rect_surface_cache) == rounded_count
