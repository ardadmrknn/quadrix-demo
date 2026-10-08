# -*- coding: utf-8 -*-
"""OP-006 (kalan iki bileşen): combo popup + pending garbage render önbelleği.

- _draw_combo_message_overlay: eski davranış popup görünürken her kare 2 ham
  ``Font.render`` (+ koşullu set_alpha) üretiyordu — CLAUDE.md "ana döngüde
  font render yasağı" ihlali. Yeni davranış game/coop ``_combo_popup_cache``
  deseni (DUZ-010 / OP-016): mesaj başına BİR render, kare içinde yalnız
  ucuz set_alpha; ``.copy()`` yüzeyi paylaşımlı font önbelleğinden
  (PatchedFont LRU / HybridFont) fade alfası için izole eder.
- _draw_pending_garbage_indicator: etiket artık render_text (text_cache)
  yolundan. Not: ONLINE_PVP_GARBAGE_ENABLED üretimde False — gösterge bugün
  ölü koddur; desen flag açıldığında hazırdır (testler flag'i kendisi açar).

Sözleşmeler:
- ikinci karede _combo_popup_cache yüzeyleri AYNI obje kalır (kimlik);
- yeni mesaj yeni yüzey üretir;
- bayat alfa: fade kuyruğunda alfa<255 kalan yüzey, aynı mesaj tazelendiğinde
  koşulsuz set_alpha ile 255'e döner (eski koşullu desen bunu kaçırırdı);
- garbage etiketi render_text'e '4' metni + NEON_RED ile gelir, sıfırken
  hiç çizilmez.

Kalıp: test_online_pvp_ghost_surface_cache draw idyomu (dummy sürücüler +
``__new__`` bare instance + blit kaydeden ekran stub'ı).
"""
from __future__ import annotations

import os
import pathlib
import sys

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

import pygame

if not pygame.get_init():
    pygame.init()
if not pygame.display.get_init():
    pygame.display.init()
pygame.display.set_mode((320, 240))
if not pygame.font.get_init():
    pygame.font.init()

ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / 'src'
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import online_pvp_game as pvp


class _ScreenStub:
    def __init__(self):
        self.blit_calls = []

    def blit(self, source, dest, *args, **kwargs):
        self.blit_calls.append((source, tuple(dest)))


def _make_game(screen):
    game = pvp.OnlinePvPGame.__new__(pvp.OnlinePvPGame)
    game.screen = screen
    # Bare instance: pencere projeksiyonu yok — sabit 1.0 ölçek.
    game._ui_scale = lambda *a, **k: 1.0
    game.my_combo_message = ''
    game.my_combo_message_time = 0
    game.pending_garbage = 0
    return game


def _draw_popup(game, message, time_left):
    game.my_combo_message = message
    game.my_combo_message_time = time_left
    game._draw_combo_message_overlay(40, 40, 300, 600)


def _stub_draw_rect(monkeypatch):
    monkeypatch.setattr(
        pygame.draw, 'rect',
        lambda surface, color, rect, width=0, *a, **k: pygame.Rect(rect),
    )


def test_popup_surfaces_shared_across_frames():
    screen = _ScreenStub()
    game = _make_game(screen)
    _draw_popup(game, 'QUADRIX x3 Combo', 90)
    assert len(screen.blit_calls) == 2, 'gölge + metin blit'
    first_shadow = game._combo_popup_cache[1]
    first_txt = game._combo_popup_cache[2]

    _draw_popup(game, 'QUADRIX x3 Combo', 89)
    assert game._combo_popup_cache[1] is first_shadow, 'gölge yüzeyi paylaşımlı'
    assert game._combo_popup_cache[2] is first_txt, 'metin yüzeyi paylaşımlı'
    assert len(screen.blit_calls) == 4, 'ikinci kare de blit etmeli'


def test_popup_new_message_renders_new_surfaces():
    game = _make_game(_ScreenStub())
    _draw_popup(game, 'COMBO x3', 90)
    first_txt = game._combo_popup_cache[2]
    _draw_popup(game, 'QUADRIX!', 90)
    assert game._combo_popup_cache[2] is not first_txt, 'yeni mesaj yeni yüzey'


def test_popup_unconditional_set_alpha_resets_stale_alpha():
    game = _make_game(_ScreenStub())
    _draw_popup(game, 'TRIPLE!', 10)  # fade bölgesi: alfa 85
    txt = game._combo_popup_cache[2]
    assert txt.get_alpha() == 85
    _draw_popup(game, 'TRIPLE!', 90)  # aynı mesaj tazelendi: alfa 255
    assert txt.get_alpha() == 255, 'koşulsuz set_alpha bayat alfa sıfırlamalı'


def _wrap_render_text(monkeypatch):
    calls = []
    real = pvp.render_text

    def counting_render_text(font, text, aa, color):
        calls.append((text, aa, color))
        return real(font, text, aa, color)

    monkeypatch.setattr(pvp, 'render_text', counting_render_text)
    return calls


def test_pending_garbage_label_uses_render_text_path(monkeypatch):
    monkeypatch.setattr(pvp, 'ONLINE_PVP_GARBAGE_ENABLED', True)
    _stub_draw_rect(monkeypatch)
    calls = _wrap_render_text(monkeypatch)

    screen = _ScreenStub()
    game = _make_game(screen)
    game.pending_garbage = 4
    game._draw_pending_garbage_indicator(40, 40, 600, 24)
    assert calls == [('4', True, pvp.UIColors.NEON_RED)], (
        'etiket render_text yolundan sayı metniyle gelmeli'
    )
    assert len(screen.blit_calls) == 1


def test_pending_garbage_hidden_when_zero(monkeypatch):
    monkeypatch.setattr(pvp, 'ONLINE_PVP_GARBAGE_ENABLED', True)
    calls = _wrap_render_text(monkeypatch)

    screen = _ScreenStub()
    game = _make_game(screen)
    game._draw_pending_garbage_indicator(40, 40, 600, 24)
    assert calls == [], 'sıfır çöp etiket render etmemeli'
    assert screen.blit_calls == []
