# -*- coding: utf-8 -*-
"""OP-015 (D4) — milestone panel glow/gradyan/metin LRU'ları smoke testi.

Kapsam kovuğu (C2/C3 dersi): D4 öncesi demo milestone çizimi her kare 4 glow
SRCALPHA + panel gradyan SRCALPHA (~satır satır draw.line) + 3 font.render
üretiyordu; duz010 yalnız rect/containment assert ediyordu. Bu test
_draw_base_scene_effects'in gerçek draw yolunu sürer ve D4 önbellek
sözleşmelerini kilitler:

  1. Pulse çevrimi (firework 119→100, 11 farklı pulse) boyunca soğuk (miss)
     ve sıcak (hit) çizimlerin kare-kare ekran digest'i birebir eşittir —
     önbellekteki yüzeyler kareler arasında mutasyona uğramaz.
  2. Hit çevriminde cache'ler büyümez (tüm look-up'lar isabet).
  3. Panel gradyan yüzeyi MASKESİZ/kare köşelidir (v2'nin BLEND_RGBA_MULT
     maskeli yuvarlak-köşe panelinden bilinçli ayrışım) ve satır alfası
     210 + int(30·i/h) eğrisini korur.
  4. Glow yüzeyleri _get_rounded_rect_surface'tan gelir (border_radius=16).
  5. Metin yüzeyi LRU'su aynı anahtarla aynı nesneyi döndürür; gölge alfası
     (150) üretimde bir kez set_alpha ile pişirilir.

test_p0/duz010 desenleri: set_mode çağrılmaz (offscreen Surface),
retro_style stub mayınına karşı skip guard.
"""

from __future__ import annotations

import hashlib
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

import game as game_module
from game import Game
from ui_theme import UIFonts
from constants import FONT_SIZE_LARGE

# duz010 LAYOUT_MATRIX 1280x720 satırı (gerçek layout motoru çıktısı).
_BX, _BY, _BW, _BH, _CELL = 490, 35, 300, 600, 30
_SIZE = (1280, 720)

# Firework penceresi: 119→100 (gerçek update() akışı), 11 farklı pulse.
_FIREWORK_TIMES = [119.0 - i for i in range(20)]


def _init_pygame() -> None:
    """Font/temel alt sistemleri hazırla; display surface AÇMA (p0 deseni)."""
    pygame.init()
    pygame.font.init()
    if not pygame.display.get_init():
        pygame.display.init()


def _retro_style_is_real() -> bool:
    """Tam paket mayınına karşı koruma (test_p0 deseni)."""
    candidate = getattr(game_module, 'retro_style', None)
    if not hasattr(candidate, 'wrap_text'):
        return False
    try:
        for _probe_font in list(getattr(candidate, 'font_cache', {}).values()):
            _probe_font.size('')
            break
    except Exception:
        return False
    return True


def _require_real_retro_style():
    import pytest
    if not _retro_style_is_real():
        pytest.skip("retro_style stub kirliliği (tam paket mayını)")


def _make_game():
    """Game.__new__ + metrik enjeksiyonu (duz010 deseni; set_mode yok)."""
    _init_pygame()
    game = Game.__new__(Game)
    game.screen = pygame.Surface(_SIZE)
    game.effects_enabled = False
    game.combo_message = ""
    game.combo_message_time = 0
    game.firework_active = True
    game.game_over = False
    game.board_width = 10
    game.board_height = 20
    game.last_milestone_score = 2000
    game.get_cell_size = lambda: _CELL
    game.get_board_offset = lambda: (_BX, _BY)
    game._active_ui_size = lambda: _SIZE
    game._get_right_hud_panel_metrics = (
        lambda ox, oy, w, h: {'rect': pygame.Rect(815, 45, 220, 600)}
    )
    game.font_large = UIFonts.get(FONT_SIZE_LARGE)
    game._font_large_size = FONT_SIZE_LARGE
    game.achievement_notifications = []
    game._achievement_notif_surface_cache = {}
    game._achievement_notif_icon_cache = {}
    return game


def _draw_digest(game, firework_time):
    """Ekranı temizle, verilen pulse durumunda milestone çiz, digest döndür."""
    game.screen.fill((0, 0, 0))
    game.firework_time = firework_time
    game._draw_base_scene_effects(None)
    return hashlib.sha256(pygame.image.tobytes(game.screen, "RGB")).hexdigest()


class TestMilestonePulseCaches:
    """D4: pulse'lı demo milestone çiziminin LRU sözleşmeleri."""

    def test_pulse_cycle_pixel_parity_cold_vs_warm(self):
        _require_real_retro_style()
        game = _make_game()
        # Soğuk çevrim: pulse boyut/alfa varyantları üretilir.
        cold = [_draw_digest(game, ft) for ft in _FIREWORK_TIMES]
        panel_count = len(game._milestone_panel_surface_cache)
        glow_count = len(game._rounded_rect_surface_cache)
        text_count = len(game._milestone_text_surface_cache)
        assert panel_count >= 2, "pulse çevrimi birden çok panel boyutu üretmeli"
        assert text_count >= 2, "pulse çevrimi birden çok skor rengi üretmeli"
        # Sıcak çevrim: tüm look-up'lar isabet — cache'ler büyümez.
        warm = [_draw_digest(game, ft) for ft in _FIREWORK_TIMES]
        assert len(game._milestone_panel_surface_cache) == panel_count
        assert len(game._rounded_rect_surface_cache) == glow_count
        assert len(game._milestone_text_surface_cache) == text_count
        assert cold == warm, (
            "hit yolu soğuk çevrimden farklı piksel üretti — önbellek yüzeyi "
            "kareler arasında mutasyona uğramış olabilir"
        )

    def test_panel_surface_square_unmasked_with_gradient(self):
        _require_real_retro_style()
        game = _make_game()
        surf = game._get_milestone_panel_surface((60, 40), (255, 215, 0))
        # Kare köşe: maske yok — köşe pikselleri de gradyanın parçası.
        # (v2 sürümü BLEND_RGBA_MULT maskesiyle köşeleri transparan yapar;
        # demo görselinde bu bilinçli olarak KORUNUR.)
        assert surf.get_at((0, 0)).a == 210, "ilk satır alfası 210 olmalı"
        assert surf.get_at((59, 0)).a == 210
        assert surf.get_at((0, 39)).a == 210 + int(30 * (39 / 40)), (
            "son satır alfası 210 + int(30·i/h) eğrisini korumalı"
        )
        assert surf.get_at((30, 20)).a > 0, "panel içi dolu olmalı"

    def test_glow_surfaces_come_from_rounded_rect_cache(self):
        _require_real_retro_style()
        game = _make_game()
        game.firework_time = 100.0
        game._draw_base_scene_effects(None)
        radii = {
            key[3] for key in game._rounded_rect_surface_cache
            if isinstance(key, tuple) and len(key) == 5
        }
        assert 16 in radii, "glow yüzeyleri border_radius=16 anahtarıyla cache'lenmeli"

    def test_text_surface_cache_identity_and_baked_alpha(self):
        _require_real_retro_style()
        game = _make_game()
        shadow = game._get_milestone_text_surface("2.000", 42, (0, 0, 0), alpha=150)
        assert shadow.get_alpha() == 150, "gölge alfası üretimde pişirilmeli"
        again = game._get_milestone_text_surface("2.000", 42, (0, 0, 0), alpha=150)
        assert again is shadow, "aynı anahtar aynı yüzey nesnesini döndürmeli"
        score = game._get_milestone_text_surface("2.000", 42, (255, 215, 0))
        assert score is not shadow, "farklı anahtar farklı yüzey üretmeli"
        assert game._get_milestone_text_surface("2.000", 42, (255, 215, 0)) is score
        assert len(game._milestone_text_surface_cache) == 2
