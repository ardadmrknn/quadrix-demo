# -*- coding: utf-8 -*-
"""OP-034 GL-modu revizyon cache'i + PrintScreen alt-örnekleme (DALGA C).

- _get_steam_overlay_gl_mode: her kare env+ayar+normalize tekrarı YOK;
  (settings_manager kimligi, OP-001 revizyon sayaci, env degeri) anahtarli
  cache. set('steam_overlay_gl') OP-001 sayacini artirir → cache duser.
- _maybe_recover_windows_display: get_pressed (~512B dizi tahsisi) her
  kare degil ~120 ms alt-ornekleme; 220 ms debounce penceresi icinde
  ornek; ara karelerde son ornek degeri korunur (was_down erken dusmez).

RAM DERSI (2026-10-08, VDS 7.9 GiB OOM, exit 137): bu dosyanin eski
fake'i ``[False] * (int(k_prtsc) + 8)`` idi; ``pygame.K_PRINTSCREEN``
bir SDL2 KEYCODE'dur (1073741894 = 0x40000046) → dev liste ~8.6 GiB →
tek-surec paket koşumları OOM kill yiyordu. Gercek ``get_pressed()``
donuşu pgScancodeWrapper'dir: K_* keycode indeksleri
``SDL_GetScancodeFromKey`` ile scancode'a cevrilir; ``len()``=512
scancode sayisidir, keycode ile kiyaslanamaz. Bu yuzden (a) fake wrapper
semantigini taklit eder, (b) kaynaktaki ``0 <= k < len(keys)`` guard'i
KALDIRILDI — guard K_PRINTSCREEN'i her zaman reddedip OP-034 prtsc
algilamayi oluyordu (game_modes_extra'daki ``keys[kc]`` once-dene deseni
zaten dogruydu).

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


class _FakePressedKeys:
    """pgScancodeWrapper taklidi: K_* keycode indekslerini kabul eder.

    Gerçek get_pressed() 512 scancode'lu durum demetini sarmalar ve
    ``keys[keycode]`` sorgusunu SDL_GetScancodeFromKey ile scancode
    yuvasına çevirir. Düz liste taklidi RAM bombasıydı (bkz. modül
    docstring'i); bu sınıf keycode kümesiyle üyelik döndürür.
    """

    _SCANCODE_COUNT = 512  # SDL_NUM_SCANCODES (SDL2 ABI)

    def __init__(self, pressed_keycodes=()):
        self._pressed = {int(k) for k in pressed_keycodes}

    def __getitem__(self, keycode):
        return int(keycode) in self._pressed

    def __len__(self):
        return self._SCANCODE_COUNT


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
        return _FakePressedKeys([k_prtsc] if key_down[0] else ())

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


def test_real_get_pressed_accepts_keycode_index():
    """Sözleşme kilidi: gerçek get_pressed K_* keycode indeksini kabul eder.

    prtsc algılama, pgScancodeWrapper'ın keycode→scancode dönüşümüne
    dayanır. pygame bir gün bu dönüşümü kaldırırsa (IndexError başlar),
    algılamanın event tabanına taşınması gerekir — bu test o kopuşu
    bağırır.
    """
    import pygame

    if not pygame.get_init():
        pygame.init()
    if not pygame.display.get_init():
        pygame.display.init()
    if pygame.display.get_surface() is None:
        pygame.display.set_mode((320, 240))

    keys = pygame.key.get_pressed()
    assert keys is not None, 'get_pressed dummy sürücüde çalışmalı'
    assert len(keys) == 512, 'SDL2 scancode tablosu 512 girişli olmalı'
    k_prtsc = int(pygame.K_PRINTSCREEN)
    assert k_prtsc >= 512, 'K_PRINTSCREEN keycode scancode aralığına sığmamalı'
    # KeyCode indeksi wrapper tarafından scancode'a çevrilmeli: IndexError yok.
    assert keys[k_prtsc] in (0, 1), 'keycode indeksi IndexError atmamalı (kopuş-algılama kanarya)'


def test_recover_event_deferred_when_limiter_budget_busy(monkeypatch):
    """Limiter bloklarken recover olayı düşmez — bütçe açılınca tekrar kurulur.

    İnceleme bulgusu (DALGA C, 2026-10-08): prtsc recover t=300'de set_mode
    yaptıktan sonra 900 ms içinde gelen Alt+Tab focus-recover'ı, pending
    tüketimi limiter kararından ÖNCE yapıldığı için sessizce yutuluyordu
    (drop). Artık last+901'e ertelenir; bütçe açıldığı karede set_mode ve
    pencere-öne-getirme gerçekten çalışır.
    """
    import pygame

    main = _load_src_main()

    monkeypatch.setattr(main, 'current_platform', 'Windows')
    monkeypatch.setattr(pygame.display, 'get_active', lambda: True)
    monkeypatch.setattr(main, '_active_overlay_module', lambda: None)

    clock = [0]
    monkeypatch.setattr(pygame.time, 'get_ticks', lambda: clock[0])
    monkeypatch.setattr(pygame.key, 'get_pressed', lambda: _FakePressedKeys())

    create_calls = [0]
    focus_calls = [0]

    class _ScreenStub:
        def get_width(self):
            return 1280

        def get_height(self):
            return 720

        def get_flags(self):
            return 0

    def _fake_create_display(*args, **kwargs):
        create_calls[0] += 1
        return _ScreenStub()

    def _fake_focus():
        focus_calls[0] += 1

    monkeypatch.setattr(main, 'create_display', _fake_create_display)
    monkeypatch.setattr(main, 'request_window_focus', _fake_focus)

    screen = _ScreenStub()

    # Temiz state.
    if hasattr(main._maybe_recover_windows_display, '_state'):
        delattr(main._maybe_recover_windows_display, '_state')
    try:
        # t=0: ilk çağrı — state kurulur, olay yok.
        assert main._maybe_recover_windows_display(screen) is screen
        state = main._maybe_recover_windows_display._state
        # Senaryo: prtsc recover t=300'de set_mode yaptı → 900 ms bütçesi
        # t=1201'e kadar meşgul.
        state['last_display_recover_ms'] = 300

        # t=900: Alt+Tab dönüş kenarı → pending focus recover t=1120'ye.
        state['display_was_inactive'] = True
        clock[0] = 900
        main._maybe_recover_windows_display(screen)
        state = main._maybe_recover_windows_display._state
        assert state['pending_focus_recover_ms'] == 1120, 'focus kenarı: now+220'

        # t=1120: pending tüketilir ama 1120-300=820 < 900 → ESKİ davranış
        # olayı burada yutardı. YENİ davranış: last+901=1201'e ertelenir.
        clock[0] = 1120
        result = main._maybe_recover_windows_display(screen)
        state = main._maybe_recover_windows_display._state
        assert result is screen, 'limiter bloklarken set_mode çağrılmamalı'
        assert create_calls[0] == 0
        assert state['pending_focus_recover_ms'] == 1201, 'defer: last+901'

        # t=1201: bütçe açık → set_mode + pencere-öne-getirme çalışır.
        clock[0] = 1201
        result = main._maybe_recover_windows_display(screen)
        state = main._maybe_recover_windows_display._state
        assert result is not screen, 'bütçe açılınca yeni display dönmeli'
        assert create_calls[0] == 1
        assert focus_calls[0] == 1, 'focus kaynaklı recover pencereyi öne getirir'
        assert state['pending_focus_recover_ms'] == -1
    finally:
        if hasattr(main._maybe_recover_windows_display, '_state'):
            delattr(main._maybe_recover_windows_display, '_state')
