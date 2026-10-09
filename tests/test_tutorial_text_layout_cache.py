# -*- coding: utf-8 -*-
"""Tutorial metin yerleşim memo'ları — OP-019 / DALGA D5 regresyon testleri.

Kapsam kovuğu (DALGA C dersi): düzenlemeden önce _wrap_text /
_fit_wrapped_text_block'ın gerçek kare yolu (_draw_tutorial_overlay +
_draw_inline_howto_hint) hiçbir testle sürülmüyordu. Bu dosya:
  1) memo hit kimliği + hit yolunda önbelleğin büyümemesi,
  2) clear_text_cache nesil artışının eski anahtarları ıskalaması
     (font profili / dil değişimi invalidasyon kancası),
  3) soğuk (miss) ve sıcak (hit) çizimlerin kare-kare ekran digest
     birebirliği (önbellekteki listelerin mutasyona uğramaması kovuğu)
kapsar. Render yüzeyleri PatchedFont global LRU'sundan gelir; burada
test edilen YERLEŞİM memo'larıdır (satır listesi + font + ölçüler).
"""

from __future__ import annotations

import hashlib
import importlib
import os
import sys
import unittest


ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
SRC_DIR = os.path.join(ROOT_DIR, 'src')
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)


def _ensure_real_module(module_name: str):
    existing = sys.modules.get(module_name)
    module_path = getattr(existing, '__file__', '') if existing is not None else ''
    if existing is not None and (not module_path or os.path.abspath(module_path).startswith(os.path.abspath(SRC_DIR)) is False):
        sys.modules.pop(module_name, None)
    return importlib.import_module(module_name)


tutorial_module = _ensure_real_module('tutorial')
TutorialMode = tutorial_module.TutorialMode
text_cache_module = _ensure_real_module('text_cache')

import pygame  # noqa: E402  (SRC_DIR yol kurulumundan sonra)

# duz010 LAYOUT_MATRIX 1280x720 (gerçek layout motoru çıktısı).
BX, BY, CELL = 490, 35, 30
SIZE = (1280, 720)

OVERLAY_MSG = "Yön tuşlariyla parçayi sola ve saga tasiyarak hedef sutuna yerlestir"
SUB_MSG = "Parcayi tam ortadaki cukura birak — hareket ederken dikey hizayi koru"
HOWTO_MSG = (
    "Sol ve sag yön tuslariyla parçayi hareket ettir; parça ilk tusa "
    "basana kadar beklemede kalir. Asagi tusuyla hizli dususe gecebilirsin"
)


class TestTutorialTextLayoutCache(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.font.init()

    def setUp(self):
        self._clear_layout_caches()

    @staticmethod
    def _clear_layout_caches():
        for name in ("_WRAP_LAYOUT_CACHE", "_FIT_BLOCK_CACHE", "_FITTING_FONT_CACHE"):
            cache = getattr(tutorial_module, name, None)
            if isinstance(cache, dict):
                cache.clear()
        for name in ("_WRAP_LAYOUT_CACHE_ORDER", "_FIT_BLOCK_CACHE_ORDER",
                     "_FITTING_FONT_CACHE_ORDER"):
            order = getattr(tutorial_module, name, None)
            if isinstance(order, list):
                del order[:]

    @staticmethod
    def _make_tutorial():
        t = TutorialMode.__new__(TutorialMode)
        t.screen = pygame.Surface(SIZE)
        t.game_over = False
        t.show_exit_prompt = False
        t.hub_active = False
        t.briefing_active = False
        t.progress_panel_active = False
        t.lesson_result_active = False
        t.lesson_result = None
        t.waiting_for_enter = False
        t.in_transition = False
        t.active_lesson = {'id': 'das_move_3', 'type': 'drill'}
        t.active_lesson_id = 'das_move_3'
        t.lesson_catalog = [{'id': f'das_move_{i}'} for i in range(1, 13)]
        t.next_lesson_id = None
        t.overlay_message = OVERLAY_MSG
        t.sub_message = SUB_MSG
        t.tip_message = ""
        t.step = 1
        t.step_target = 3
        t.step_move_left_count = 1
        t.step_move_right_count = 1
        t.step_rotate_count = 0
        t.soft_drop_counter = 0
        t.board_width = 10
        t.board_height = 20
        t.get_cell_size = lambda: CELL
        t.get_board_offset = lambda: (BX, BY)
        t._active_ui_size = lambda: SIZE
        t.inline_howto_active = True
        t.inline_howto_text = HOWTO_MSG
        t.inline_howto_pulse = 0.0
        return t

    def test_fit_block_cache_hit_identity_and_no_growth(self):
        t = self._make_tutorial()
        args = dict(base_size=26, max_width=200, max_height=90,
                    bold=True, min_size=12, max_lines=4)
        first = t._fit_wrapped_text_block(OVERLAY_MSG, **args)
        self.assertEqual(len(tutorial_module._FIT_BLOCK_CACHE), 1)
        second = t._fit_wrapped_text_block(OVERLAY_MSG, **args)
        # Hit: aynı yerleşim nesneleri (font + satır listesi) döner...
        self.assertIs(first[0], second[0])
        self.assertIs(first[1], second[1])
        # ...ve hit önbelleği büyütmez.
        self.assertEqual(len(tutorial_module._FIT_BLOCK_CACHE), 1)
        self.assertEqual(first[3], second[3])

    def test_fit_cache_key_varies_with_geometry(self):
        t = self._make_tutorial()
        t._fit_wrapped_text_block(OVERLAY_MSG, base_size=26, max_width=200,
                                  max_height=90, bold=True, min_size=12, max_lines=4)
        t._fit_wrapped_text_block(OVERLAY_MSG, base_size=26, max_width=220,
                                  max_height=90, bold=True, min_size=12, max_lines=4)
        # Farklı geometri = farklı anahtar = yeni hesap.
        self.assertEqual(len(tutorial_module._FIT_BLOCK_CACHE), 2)

    def test_wrap_text_cache_hit_identity(self):
        t = self._make_tutorial()
        font = tutorial_module.retro_style.get_font(16, bold=False)
        first = t._wrap_text(HOWTO_MSG, font, 180)
        self.assertEqual(len(tutorial_module._WRAP_LAYOUT_CACHE), 1)
        second = t._wrap_text(HOWTO_MSG, font, 180)
        self.assertIs(first, second)
        self.assertEqual(len(tutorial_module._WRAP_LAYOUT_CACHE), 1)
        # Farklı genişlik yeni sarma ister (liste nesnesi farklı).
        wider = t._wrap_text(HOWTO_MSG, font, 340)
        self.assertIsNot(first, wider)
        self.assertEqual(len(tutorial_module._WRAP_LAYOUT_CACHE), 2)

    def test_fitting_font_cache_identity(self):
        t = self._make_tutorial()
        first = t._get_fitting_font('DERS 3/12', 18, 150, bold=True, min_size=10)
        self.assertEqual(len(tutorial_module._FITTING_FONT_CACHE), 1)
        second = t._get_fitting_font('DERS 3/12', 18, 150, bold=True, min_size=10)
        self.assertIs(first, second)
        self.assertEqual(len(tutorial_module._FITTING_FONT_CACHE), 1)

    def test_clear_text_cache_invalidates_layout_memos(self):
        t = self._make_tutorial()
        args = dict(base_size=16, max_width=200, max_height=60,
                    bold=False, min_size=11, max_lines=3)
        first = t._fit_wrapped_text_block(SUB_MSG, **args)
        self.assertEqual(len(tutorial_module._FIT_BLOCK_CACHE), 1)
        # Font profili / dil değişimi kancası: nesil artışı eski anahtarı
        # ıskalar (aynı girdi yeniden hesaplanır, önbellek yeni nesle yazılır).
        text_cache_module.clear_text_cache()
        second = t._fit_wrapped_text_block(SUB_MSG, **args)
        self.assertIsNot(first[1], second[1])
        self.assertEqual(first, second)  # sonuç içerik olarak özdeş kalır
        self.assertEqual(len(tutorial_module._FIT_BLOCK_CACHE), 2)

    def _digest(self, t):
        # Pulse rengi kare ilerledikçe değişir; soğuk/sıcak aynı çizsin diye
        # her ölçüm öncesi sabitlenir (memo'lar pulse'tan bağımsızdır).
        t.inline_howto_pulse = 3.0
        t.screen.fill((0, 0, 0))
        t._draw_tutorial_overlay()
        t._draw_inline_howto_hint()
        return hashlib.sha256(pygame.image.tobytes(t.screen, "RGB")).hexdigest()

    def test_overlay_and_howto_pixel_parity_cold_vs_warm(self):
        t = self._make_tutorial()
        cold = self._digest(t)
        for _ in range(60):
            t._draw_tutorial_overlay()
            t._draw_inline_howto_hint()
        warm = self._digest(t)
        self.assertEqual(cold, warm)

        # Sıcak çevrimde hiçbir memo büyümez (hit yolu).
        def _total():
            return (len(tutorial_module._FIT_BLOCK_CACHE)
                    + len(tutorial_module._WRAP_LAYOUT_CACHE)
                    + len(tutorial_module._FITTING_FONT_CACHE))
        before = _total()
        for _ in range(40):
            t._draw_tutorial_overlay()
            t._draw_inline_howto_hint()
        self.assertEqual(_total(), before)


if __name__ == '__main__':
    unittest.main()
