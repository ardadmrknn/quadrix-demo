# -*- coding: utf-8 -*-
"""OP-034 GL-modu revizyon cache'i + PrintScreen alt-örnekleme (DALGA C).

- _get_steam_overlay_gl_mode: her kare env+ayar+normalize tekrarı YOK;
  (settings_manager kimligi, OP-001 revizyon sayaci, env degeri) anahtarli
  cache. set('steam_overlay_gl') OP-001 sayacini artirir → cache duser.
- _maybe_recover_windows_display: get_pressed (~512B dizi tahsisi) her
  kare degil ~120 ms alt-ornekleme; 220 ms debounce penceresi icinde
  ornek; ara karelerde son ornek degeri korunur (was_down erken dusmez).

Modül importları gövde içinde; main importu SDL dummy altında güvenli
(modül düzeyi display kurmuyor — doğrulandı).
"""
from __future__ import annotations

import os
import pathlib
import sys

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / 'src'
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


def _load_src_main():
    """src/main.py'yi dosya konumundan yükle.

    Repo kökünde de bir main.py olduğundan düz `import main` yanlış
    modülü yakalar (çift modül kimliği dersi).
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location('main_op034', SRC_DIR / 'main.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules.pop('main_op034', None)
    sys.modules['main_op034'] = module
    spec.loader.exec_module(module)
    return module


class _FakeSettingsManager:
    def __init__(self, value='auto'):
        self.settings_revision = 1
        self._value = value
        self.get_calls = 0

    def get(self, key, default=None):
        self.get_calls += 1
        if key == 'steam_overlay_gl':
            return self._value
        return default


def test_gl_mode_cache_hits_skip_lookup(monkeypatch):
    main = _load_src_main()

    monkeypatch.delenv('QUADRIX_STEAM_OVERLAY_GL', raising=False)
    # Modül-düzeyi cache'i testler arası sıfırla.
    monkeypatch.setattr(main, '_GL_MODE_CACHE', {'sm_id': None, 'rev': None, 'env': None, 'mode': 'auto'})

    sm = _FakeSettingsManager('force')
    assert main._get_steam_overlay_gl_mode(sm) == 'force'
    assert sm.get_calls == 1, 'MISS: ayar okuma bir kez'

    # Isabet: ayar okuma/normalize tekrarı YOK.
    for _ in range(5):
        assert main._get_steam_overlay_gl_mode(sm) == 'force'
    assert sm.get_calls == 1

    # OP-001 revizyon artisi → cache duser → yeni deger okunur.
    sm._value = 'off'
    sm.settings_revision += 1
    assert main._get_steam_overlay_gl_mode(sm) == 'off'
    assert sm.get_calls == 2

    # Env degisimi → cache duser (ayar okumadan env kazanir).
    monkeypatch.setenv('QUADRIX_STEAM_OVERLAY_GL', '1')
    assert main._get_steam_overlay_gl_mode(sm) == 'force'
    assert sm.get_calls == 2, 'env katarina ayar okunmaz'

    # Env kalkinca → settings'e doner (env anahtari degisti).
    monkeypatch.delenv('QUADRIX_STEAM_OVERLAY_GL', raising=False)
    assert main._get_steam_overlay_gl_mode(sm) == 'off'
    assert sm.get_calls == 3


def test_prtsc_probe_is_subsampled_and_edge_survives(monkeypatch):
    import pygame

    main = _load_src_main()

    monkeypatch.setattr(main, 'current_platform', 'Windows')
    monkeypatch.setattr(pygame.display, 'get_active', lambda: True)
    monkeypatch.setattr(main, '_active_overlay_module', lambda: None)

    clock = [0]
    monkeypatch.setattr(pygame.time, 'get_ticks', lambda: clock[0])

    k_prtsc = getattr(pygame, 'K_PRINTSCREEN', None)
    assert k_prtsc is not None, 'pygame-ce K_PRINTSCREEN bekleniyor'
    probe_calls = [0]
    key_down = [False]

    def _fake_get_pressed():
        probe_calls[0] += 1
        keys = [False] * (int(k_prtsc) + 8)
        keys[int(k_prtsc)] = key_down[0]
        return keys

    monkeypatch.setattr(pygame.key, 'get_pressed', _fake_get_pressed)

    class _ScreenStub:
        pass

    # Temiz state.
    if hasattr(main._maybe_recover_windows_display, '_state'):
        delattr(main._maybe_recover_windows_display, '_state')
    try:
        # t=0: ilk ornekleme → get_pressed BIR kez.
        main._maybe_recover_windows_display(_ScreenStub(), settings_manager=None)
        assert probe_calls[0] == 1

        # Ayni 120 ms penceresi icinde 10 kare → ek ornekleme YOK.
        for _ in range(10):
            main._maybe_recover_windows_display(_ScreenStub(), settings_manager=None)
        assert probe_calls[0] == 1, 'alt-ornekleme: pencere icinde probe olmamali'

        # Pencere doldu → yeni ornek.
        clock[0] = 200
        main._maybe_recover_windows_display(_ScreenStub(), settings_manager=None)
        assert probe_calls[0] == 2

        # PrintScreen basin kenari: pending 220 ms sonrasina kurulur.
        key_down[0] = True
        clock[0] = 400
        main._maybe_recover_windows_display(_ScreenStub(), settings_manager=None)
        state = main._maybe_recover_windows_display._state
        assert state['pending_prtsc_recover_ms'] == 620, 'edge: now+220'
        assert state['prtsc_was_down'] is True

        # Ara kare (500-400=100 ms < 120): ornekleme YOK, was_down KORUNUR
        # — pending erken tetiklenmez (recover yalniz birakma ornegini bekler).
        # Not: 3. probe t=400'teki kenar ornegiydi; 500'de YENI ornek olmamali.
        clock[0] = 500
        main._maybe_recover_windows_display(_ScreenStub(), settings_manager=None)
        assert probe_calls[0] == 3, '100 ms < 120 → yeni probe olmamali'
        state = main._maybe_recover_windows_display._state
        assert state['prtsc_was_down'] is True, 'ara karede son ornek korunmali'
        assert state['pending_prtsc_recover_ms'] == 620
    finally:
        if hasattr(main._maybe_recover_windows_display, '_state'):
            delattr(main._maybe_recover_windows_display, '_state')
