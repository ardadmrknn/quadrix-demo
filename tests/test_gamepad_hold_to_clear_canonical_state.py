"""GP-004 + GP-005 — Hold-to-clear per-frame driver ve canonical held-state testleri.

İade nedenleri:
- GP-004: `TabbedSettingsScreen.update()` (hold-to-clear sürücüsü) HİÇBİR
  yerden çağrılmıyordu — main.py ayarlar döngüsü yalnızca event loop + draw
  yapıyordu; "basılı tutarak temizle" özelliği tamamen ölüydü.
- GP-005: `_check_hold_to_clear_progress` hangi butonun basılı kaldığını
  SDL joystick'lerinden RAW indeksle okuyordu; capture imzası ise CANONICAL
  indeksti. Cihaza göre indeks kayması tutma kontrolünü yanıltıyordu.

Bu testler: (1) main.py ayarlar döngüsünde event loop SONRASI draw ÖNCESİ
tam bir kez `settings_screen.update(delta_ms)` çağrısını; (2) GamepadManager
üzerinde imza tabanlı canonical `is_capture_input_held` sorgusunu; (3) uçtan
uca hold-to-clear akışını doğrular.
"""

from __future__ import annotations

import os
import sys

import pytest


def _ensure_src_on_path() -> None:
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    src_path = os.path.join(repo_root, 'src')
    if src_path not in sys.path:
        sys.path.insert(0, src_path)


_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


def test_main_settings_loop_calls_update_once_per_frame():
    """GP-004: _handle_settings, event loop'tan sonra draw'dan önce update() çağırmalı."""
    main_py = os.path.join(_REPO_ROOT, 'src', 'main.py')
    with open(main_py, encoding='utf-8') as fh:
        src = fh.read()

    start = src.index('def _handle_settings(delta_ms):')
    end = src.index('\n    def ', start + 10)
    body = src[start:end]

    loop_i = body.index('for event in pygame.event.get()')
    update_i = body.index('settings_screen.update(delta_ms)')
    draw_i = body.index('settings_screen.draw()')

    assert loop_i < update_i < draw_i, (
        'settings_screen.update(delta_ms) event loop SONRASI ve draw ÖNCESİ '
        'çağrılmalı (frame başına tam bir kez)'
    )
    assert body.count('settings_screen.update(delta_ms)') == 1, (
        'update() frame başına tam bir kez çağrılmalı'
    )


@pytest.fixture(scope='module')
def live_screen():
    """Tek bir display ve TabbedSettingsScreen instance hazırlar.

    Dönen gamepad_manager modülü, sst'nin import ettiği AYNI modül
    kimliğidir: demo conftest'inin src.*/flat alias senkronu sst modülünü
    sys.modules'ten koparabildiği için, test sst ile aynı singleton'a
    ancak bu yakalanmış referans üzerinden güvenle erişir.
    """
    os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
    _ensure_src_on_path()

    for mod in [
        'settings_screen_tabbed', 'constants', 'retro_style',
        'platform_utils', 'background_effects', 'localization',
        'ui_language_profile', 'menu', 'gamepad_manager',
        'promptfont_support', 'ui_scaling', 'settings_manager',
    ]:
        sys.modules.pop(mod, None)

    import pygame
    if not hasattr(pygame, 'K_h'):
        pytest.skip('pygame stub environment')

    pygame.init()
    pygame.display.set_mode((1280, 720))

    import settings_screen_tabbed as sst
    import gamepad_manager as gm_mod  # sst'nin kullandığı AYNI modül kimliği
    from settings_manager import SettingsManager

    sm = SettingsManager()
    screen = pygame.display.get_surface()
    inst = sst.TabbedSettingsScreen(screen, None, sm)
    inst.current_tab = 3  # Kontroller
    inst._rebuild_tab_content()
    inst._persist_controls = lambda: None
    return pygame, inst, gm_mod


def test_is_capture_input_held_canonical_button_query():
    """GP-005: ('btn', i) imzası bağlı gamepad'lerin CANONICAL buton durumunu sorgulamalı."""
    _ensure_src_on_path()
    os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
    os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

    import pygame
    if not hasattr(pygame, 'K_h'):
        pytest.skip('pygame stub environment')
    pygame.init()

    import gamepad_manager as gm_mod

    gpm = gm_mod.GamepadManager()
    gpm._check_connections = lambda: None

    assert hasattr(gpm, 'is_capture_input_held'), \
        'GamepadManager.is_capture_input_held(signature) tanımlı olmalı'

    gp = gm_mod.GamepadState(device_index=0)
    gp.buttons[3] = True
    gpm.gamepads[0] = gp
    try:
        assert gpm.is_capture_input_held(('btn', 3)) is True
        assert gpm.is_capture_input_held(('btn', 5)) is False
        assert gpm.is_capture_input_held(('btn', 'x')) is False
    finally:
        gpm.gamepads.pop(0, None)

    # Cihaz yoksa (disconnect) False dönmeli
    assert gpm.is_capture_input_held(('btn', 3)) is False
    assert gpm.is_capture_input_held(('key', pygame.K_a)) is False, \
        'dummy sürücüde basılı tuş yok; klavye sorgusu False dönmeli'
    assert gpm.is_capture_input_held(()) is False


def test_hold_to_clear_clears_gamepad_slot_via_update_driver(live_screen, monkeypatch):
    """GP-004+GP-005 uçtan uca: capture + buton basılı tutma → update() slot'u temizlemeli."""
    pygame, inst, gm_mod = live_screen

    gamepad_cfg = inst._control_config.setdefault('gamepad', {})
    if not isinstance(gamepad_cfg.get('hard_drop'), dict):
        gamepad_cfg['hard_drop'] = {'primary': -1, 'secondary': -1}
    gamepad_cfg['hard_drop']['primary'] = 10

    fake_ms = [10000]
    monkeypatch.setattr(pygame.time, 'get_ticks', lambda: fake_ms[0])

    # Capture'ı aç ve CANONICAL buton 3'ün basılı başlangıcını kaydet
    inst._waiting_for_key = True
    inst._pending_keybind_item = {
        'type': 'keybind', 'section': 'gamepad.ingame', 'action_key': 'hard_drop',
    }
    inst._pending_keybind_slot = 'primary'
    inst._capture_started_by_gamepad_click = False
    inst._swallow_next_keydown = False
    inst._swallow_next_gamepad_click = False
    inst._reset_hold_to_clear_state()

    inst.handle_input(pygame.event.Event(pygame.CONTROLLERBUTTONDOWN, button=3))
    assert inst._hold_to_clear_pressed_signature == ('btn', 3)

    # Mock gamepad: canonical buton 3 basılı tutuluyor. Singleton, sst'nin
    # bağlı olduğu gamepad_manager modülünden alınır (modül kimliği garantisi).
    gpm = gm_mod.get_gamepad_manager()
    gpm._check_connections = lambda: None
    mock_gp = gm_mod.GamepadState(device_index=0)
    mock_gp.buttons[3] = True
    gpm.gamepads[0] = mock_gp
    try:
        # Eşiğin altında: henüz temizlememeli
        fake_ms[0] = 10000 + 800
        inst.update(16.0)
        assert inst._waiting_for_key is True
        assert gamepad_cfg['hard_drop']['primary'] == 10

        # Eşiğin üstünde ve hâlâ basılı: slot temizlenmeli, capture kapanmalı
        fake_ms[0] = 10000 + 1600
        inst.update(16.0)
        assert inst._waiting_for_key is False, 'hold-to-clear capture\'ı kapatmalı'
        assert gamepad_cfg['hard_drop']['primary'] == -1, 'primary slot unbound (-1) olmalı'
    finally:
        gpm.gamepads.pop(0, None)
