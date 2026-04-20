from __future__ import annotations

import os
import sys

import pygame


SRC_DIR = os.path.join(os.path.dirname(__file__), '..', 'src')
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

import menu as menu_module
from menu import Menu


def _make_menu_stub() -> Menu:
    return Menu.__new__(Menu)


def test_sos_mascot_candidates_follow_selected_language(monkeypatch):
    menu = _make_menu_stub()

    monkeypatch.setattr(menu_module, 'get_language', lambda: 'tr')
    tr_candidates = menu._get_sos_mascot_candidate_paths()
    assert tr_candidates[0].name == 'sos_maskot.png'

    monkeypatch.setattr(menu_module, 'get_language', lambda: 'en')
    en_candidates = menu._get_sos_mascot_candidate_paths()
    assert en_candidates[0].name == 'sos_maskot_ingilizce.png'

    monkeypatch.setattr(menu_module, 'get_language', lambda: 'de')
    de_candidates = menu._get_sos_mascot_candidate_paths()
    assert de_candidates[0].name == 'sos_maskot_almanca.png'


def test_sos_mascot_load_resets_cached_scaled_surface_when_language_changes(monkeypatch):
    menu = _make_menu_stub()
    tr_surface = pygame.Surface((120, 120), pygame.SRCALPHA)
    en_surface = pygame.Surface((120, 120), pygame.SRCALPHA)
    loaded_paths: list[str] = []

    def _fake_load_image(path, convert_alpha=True):
        loaded_paths.append(path)
        if path.endswith('sos_maskot_ingilizce.png'):
            return en_surface
        if path.endswith('sos_maskot.png'):
            return tr_surface
        return None

    monkeypatch.setattr(menu_module, 'load_image', _fake_load_image)

    monkeypatch.setattr(menu_module, 'get_language', lambda: 'tr')
    image_tr, token_tr = menu._load_sos_mascot_image()

    menu._sos_mascot_scaled = object()
    menu._sos_mascot_scaled_key = (token_tr, 200, 200)

    monkeypatch.setattr(menu_module, 'get_language', lambda: 'en')
    image_en, token_en = menu._load_sos_mascot_image()

    assert image_tr is tr_surface
    assert image_en is en_surface
    assert token_tr.endswith('sos_maskot.png')
    assert token_en.endswith('sos_maskot_ingilizce.png')
    assert token_tr != token_en
    assert getattr(menu, '_sos_mascot_scaled', None) is None
    assert getattr(menu, '_sos_mascot_scaled_key', None) is None
    assert any(path.endswith('sos_maskot.png') for path in loaded_paths)
    assert any(path.endswith('sos_maskot_ingilizce.png') for path in loaded_paths)