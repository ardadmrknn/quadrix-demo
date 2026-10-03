# -*- coding: utf-8 -*-
"""DUZ-010 — oyun içi overlay (milestone / combo / achievement toast) containment.

Iade_Duzeltme_Plani.md DUZ-010 kabul ölçütlerinin test ayağı:
  1. Milestone firework paneli board (cell) çapasıyla ölçeklenir; board
     playfield'ı ve yan HUD paneliyle KESİŞMEZ, aktif alan içinde kalır
     (board üstü → tahta altı şerit önceliği; sıkışık ekranda orantılı
     küçültme; ≤1080p'de spawn satırlarını örten eski ekran-merkez
     yerleşimi kapanır).
  2. Combo popup metni board genişliğine yatay sığar (dar pencerede sağ
     HUD paneline taşma yok), mesaj başına tek render cache'i kullanılır
     (kare-başı font render tahsisi yok) ve rect kaydı tutulur.
  3. Achievement toast şeridi board/HUD panel altından başlar: HUD panel,
     board ve aktif alan ile kesişmez; şeride sığmayan bildirimler sıraya
     girer (yaşlanmaz, ilk çizimde zamanları sıfırlanır); rect'ler
     kaydı `self._achievement_toast_rects` üzerinden tutulur.
  4. Milestone paneli şeridi kapladığında toast kuyruğa girer; panel
     kaybolunca gösterilir. 4K'da milestone board üstünde, toast şeritte —
     ikisi aynı karede çizilebilir ve disjoint kalır.

Geometri sabitleri gerçek compute_single_player_layout ölçümünden gelir
(duz010_layout_probe, 2026-10-03; board_width=10, board_height=20,
info_panel_height=120). test_p0_screen_containment deseni izlenir:
set_mode çağrılmaz (offscreen Surface), retro_style stub/ölü-font mayınına
karşı skip guard kullanılır.

Steam overlay görsel etkisi (kart maddesi 5) MANUEL kullanıcı kapısıdır —
burada otomatik test edilmez.
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

import game as game_module
from game import Game
from ui_theme import UIFonts
from constants import FONT_SIZE_LARGE


# ---------------------------------------------------------------------------
# Ölçüm matrisi (gerçek layout motoru çıktısı)
# ---------------------------------------------------------------------------
# size: (board_x, board_y, board_w, board_h, cell, panel_x, panel_y, panel_w, panel_h)
LAYOUT_MATRIX = {
    (500, 750): (113, 120, 230, 460, 23, 368, 130, 120, 460),
    (960, 540): (375, 35, 210, 420, 21, 610, 45, 220, 420),
    (1024, 768): (352, 39, 320, 640, 32, 697, 49, 220, 640),
    (1152, 864): (391, 37, 370, 740, 37, 786, 47, 220, 740),
    (1280, 720): (490, 35, 300, 600, 30, 815, 45, 220, 600),
    (1280, 800): (470, 35, 340, 680, 34, 835, 45, 220, 680),
    (1366, 768): (523, 39, 320, 640, 32, 868, 49, 220, 640),
    (1600, 900): (605, 34, 390, 780, 39, 1021, 45, 235, 780),
    (1920, 1080): (730, 53, 460, 920, 46, 1218, 64, 257, 920),
    (2560, 1440): (1020, 170, 520, 1040, 52, 1572, 183, 299, 1040),
    (3840, 2160): (1640, 488, 560, 1120, 56, 2234, 501, 320, 1120),
}


def _init_pygame() -> None:
    """Font/temel alt sistemleri hazırla; display surface AÇMA (p0 deseni)."""
    pygame.init()
    pygame.font.init()
    if not pygame.display.get_init():
        pygame.display.init()


def _retro_style_is_real(draw_module) -> bool:
    """Tam paket mayınına karşı koruma (test_p0 deseni): game modülünün
    retro_style'i gerçek ve fontları canlı mı? Stub/ölü font → skip."""
    candidate = getattr(draw_module, 'retro_style', None)
    if not hasattr(candidate, 'wrap_text'):
        return False
    try:
        for _probe_font in list(getattr(candidate, 'font_cache', {}).values()):
            _probe_font.size('')
            break
    except Exception:
        return False
    return True


def _make_game(size):
    """Game.__new__ + matris enjeksiyonu (p0 __new__ deseni; set_mode yok)."""
    _init_pygame()
    bx, by, bw, bh, cell, px, py, pw, ph = LAYOUT_MATRIX[size]
    game = Game.__new__(Game)
    game.screen = pygame.Surface(size)
    game.effects_enabled = False
    game.combo_message = ""
    game.combo_message_time = 0
    game.firework_active = False
    game.firework_time = 0
    game.game_over = False
    game.board_width = 10
    game.board_height = 20
    game.last_milestone_score = 2000
    # Matris ölçümleri gerçek layout çıktısı: metrik yöntemleri doğrudan
    # enjekte edilir (draw yolu tam olarak bu değerleri okur).
    game.get_cell_size = lambda: cell
    game.get_board_offset = lambda: (bx, by)
    game._active_ui_size = lambda: size
    game._get_right_hud_panel_metrics = (
        lambda ox, oy, w, h: {'rect': pygame.Rect(px, py, pw, ph)}
    )
    game.font_large = UIFonts.get(FONT_SIZE_LARGE)
    game._font_large_size = FONT_SIZE_LARGE
    game.achievement_notifications = []
    game._achievement_notif_surface_cache = {}
    game._achievement_notif_icon_cache = {}
    return game


def _make_notification(name="Test Achievement", ms_old=400):
    """Gerik uyumlu bildirim sözlüğü ('shown' anahtarı opsiyoneldir)."""
    return {
        'achievement': {
            'id': 'duz010_test',
            'name': name,
            'description': 'Kapsam testi açıklaması',
        },
        'time': pygame.time.get_ticks() - ms_old,
        'alpha': 255,
    }


def _require_real_retro_style():
    import pytest
    if not _retro_style_is_real(game_module):
        pytest.skip("retro_style stub kirliliği (tam paket mayını)")


# ---------------------------------------------------------------------------
# Bölüm A — Milestone (firework) panel containment
# ---------------------------------------------------------------------------
class TestMilestoneContainment:
    """Alt iş 1: panel board çapasıyla ölçeklenir, board+HUD ile disjoint."""

    def _run(self, size):
        game = _make_game(size)
        game.firework_active = True
        game.firework_time = 100  # pulse deterministik: (100 % 20 - 10)/10 = 1.0
        game._draw_base_scene_effects(None)
        return game

    def test_rect_off_board_and_hud_inside_screen_all_sizes(self):
        _require_real_retro_style()
        for size, row in LAYOUT_MATRIX.items():
            game = self._run(size)
            rect = game._milestone_panel_rect
            assert rect is not None, f"{size}: milestone rect kaydedilmeli"
            bx, by, bw, bh, cell, px, py, pw, ph = row
            screen = pygame.Rect(0, 0, *size)
            board = pygame.Rect(bx, by, bw, bh)
            hud = pygame.Rect(px, py, pw, ph)
            assert screen.contains(rect), f"{size}: ekran dışı {rect}"
            assert not rect.colliderect(board), (
                f"{size}: milestone board'u örtüyor {rect} vs {board}"
            )
            assert not rect.colliderect(hud), (
                f"{size}: milestone HUD panelini örtüyor {rect} vs {hud}"
            )

    def test_4k_places_panel_above_board(self):
        # Geniş üst alan: özgün 'YUKARIDA' niyeti korunur.
        _require_real_retro_style()
        game = self._run((3840, 2160))
        bx, by = LAYOUT_MATRIX[(3840, 2160)][:2]
        assert game._milestone_panel_rect.bottom <= by + 1

    def test_1080p_shrinks_into_strip_below_board(self):
        # Board üstü 53px sığmaz → tahta altı şeride orantılı küçültülür.
        _require_real_retro_style()
        game = self._run((1920, 1080))
        bx, by, bw, bh = LAYOUT_MATRIX[(1920, 1080)][:4]
        rect = game._milestone_panel_rect
        assert rect.top >= by + bh
        assert rect.bottom <= 1080

    def test_rect_record_cleared_when_firework_inactive(self):
        _require_real_retro_style()
        game = _make_game((1280, 720))
        game._draw_base_scene_effects(None)
        assert game._milestone_panel_rect is None


# ---------------------------------------------------------------------------
# Bölüm B — Combo popup containment + render cache
# ---------------------------------------------------------------------------
class TestComboPopupContainment:
    """Alt iş 2: metin board genişliğine sığar; mesaj başına tek render."""

    def _run(self, size, message="QUADRIX x9 Combo"):
        game = _make_game(size)
        game.combo_message = message
        game.combo_message_time = 90  # alpha 255 (fade son 30 karede)
        game._draw_base_scene_effects(None)
        return game

    def test_text_fits_board_width_all_sizes(self):
        _require_real_retro_style()
        for size, row in LAYOUT_MATRIX.items():
            game = self._run(size)
            rect = game._combo_popup_rect
            assert rect is not None, f"{size}: combo rect kaydedilmeli"
            bx, by, bw, bh, cell = row[:5]
            board = pygame.Rect(bx, by, bw, bh)
            assert board.contains(rect), (
                f"{size}: combo metni board dışına taşıyor {rect} vs {board}"
            )
            assert rect.width <= bw - 2 * cell, (
                f"{size}: fit marji aşıldı {rect.width} > {bw - 2 * cell}"
            )

    def test_message_rendered_once_and_cached(self):
        _require_real_retro_style()
        game = self._run((1280, 720), "COMBO x3")
        first_shadow, first_txt = game._combo_popup_cache[1], game._combo_popup_cache[2]
        game.combo_message_time = 90
        game._draw_base_scene_effects(None)
        assert game._combo_popup_cache[1] is first_shadow
        assert game._combo_popup_cache[2] is first_txt

    def test_new_message_renders_new_surfaces(self):
        _require_real_retro_style()
        game = self._run((1280, 720), "COMBO x3")
        first_txt = game._combo_popup_cache[2]
        game.combo_message = "QUADRIX x9"
        game.combo_message_time = 90
        game._draw_base_scene_effects(None)
        assert game._combo_popup_cache[2] is not first_txt


# ---------------------------------------------------------------------------
# Bölüm C — Achievement toast şerit containment + sıra disiplini
# ---------------------------------------------------------------------------
class TestAchievementToastContainment:
    """Alt iş 3: toast şeridi board/HUD altında; sıra + rect kaydı."""

    def _run(self, size, count=3):
        game = _make_game(size)
        for i in range(count):
            game.achievement_notifications.append(_make_notification(f"Başarım {i}"))
        game.draw_achievement_notifications()
        return game

    def test_toasts_off_board_and_hud_inside_screen_all_sizes(self):
        _require_real_retro_style()
        for size, row in LAYOUT_MATRIX.items():
            game = self._run(size)
            rects = game._achievement_toast_rects
            assert rects, f"{size}: en az bir toast çizilmeli"
            bx, by, bw, bh, cell, px, py, pw, ph = row
            screen = pygame.Rect(0, 0, *size)
            board = pygame.Rect(bx, by, bw, bh)
            hud = pygame.Rect(px, py, pw, ph)
            for rect in rects:
                assert screen.contains(rect), f"{size}: ekran dışı {rect}"
                assert not rect.colliderect(board), (
                    f"{size}: toast board'u örtüyor {rect} vs {board}"
                )
                assert not rect.colliderect(hud), (
                    f"{size}: toast HUD panelini örtüyor {rect} vs {hud}"
                )

    def test_strip_overflow_queues_without_aging(self):
        # 1280x720 şeridi tek kutu alır: 3 bildirimden 1'i çizilir; diğerleri
        # sıradadır (alpha 255 kalır, listeden düşmez, yaşlanmaz).
        _require_real_retro_style()
        game = self._run((1280, 720), count=3)
        assert len(game._achievement_toast_rects) == 1
        assert len(game.achievement_notifications) == 3
        for notification in game.achievement_notifications:
            assert notification['alpha'] == 255

    def test_scaled_panel_uses_own_cache_key(self):
        # Küçültülmüş kutu (222x~58) baz 392x104 anahtarını paylaşmaz; sanat
        # baz boyutta üretilip hedefe smoothscale edilir.
        _require_real_retro_style()
        game = self._run((1280, 720), count=1)
        keys = list(game._achievement_notif_surface_cache.keys())
        assert keys, "panel yüzeyi cache'lenmeli"
        assert (392, 104) not in keys

    def test_stacked_rects_do_not_overlap(self):
        _require_real_retro_style()
        game = self._run((3840, 2160), count=4)
        rects = game._achievement_toast_rects
        assert len(rects) >= 2, "4K şeridi en az iki kutu almalı"
        for i in range(len(rects)):
            for j in range(i + 1, len(rects)):
                assert not rects[i].colliderect(rects[j])

    def test_milestone_blocks_strip_then_frees(self):
        _require_real_retro_style()
        game = _make_game((1024, 768))
        game.firework_active = True
        game.firework_time = 100
        game.achievement_notifications.append(_make_notification("Bekleyen"))
        game._draw_base_scene_effects(None)
        assert game._milestone_panel_rect is not None
        game.draw_achievement_notifications()
        # Milestone şeridi kaplar → toast sıraya girer, çizilmez, yaşlanmaz.
        assert game._achievement_toast_rects == []
        assert len(game.achievement_notifications) == 1
        assert game.achievement_notifications[0]['alpha'] == 255
        # Milestone bitti → rect None → toast gösterilir (zaman sıfırlanır).
        game.firework_active = False
        game._draw_base_scene_effects(None)
        assert game._milestone_panel_rect is None
        game.draw_achievement_notifications()
        assert len(game._achievement_toast_rects) == 1
        assert game.achievement_notifications[0].get('shown') is True

    def test_milestone_and_toast_coexist_disjoint_at_4k(self):
        # 4K'da milestone board üstünde, toast şeritte: aynı karede ikisi de
        # çizilir ve kesişmez.
        _require_real_retro_style()
        game = _make_game((3840, 2160))
        game.firework_active = True
        game.firework_time = 100
        game.achievement_notifications.append(_make_notification("4K"))
        game._draw_base_scene_effects(None)
        game.draw_achievement_notifications()
        assert game._milestone_panel_rect is not None
        assert len(game._achievement_toast_rects) == 1
        assert not game._milestone_panel_rect.colliderect(
            game._achievement_toast_rects[0])

    def test_notification_time_resets_on_first_draw(self):
        # Kuyruğa giren bildirim ilk çiziminde tam 5 s alır: zaman, çizildiği
        # ana sıfırlanır (eski unlock zamanına değil).
        _require_real_retro_style()
        game = _make_game((1280, 720))
        notification = _make_notification("Sıra", ms_old=8000)
        game.achievement_notifications.append(notification)
        game.draw_achievement_notifications()
        assert notification['shown'] is True
        assert pygame.time.get_ticks() - notification['time'] < 1000
        # Yaşlanma yok (yeniden çizimde alpha korunur).
        game.draw_achievement_notifications()
        assert notification['alpha'] == 255
