"""GP-006 — Steam Input fallback cihazlarının capture kenar kuyruğu testleri.

v2 paritesi (P0-1): v2'deki test_gamepad_steam_capture_edges.py'nin demo
deposuna birebir taşıması. İade nedeni: Steam Input sanal gamepad'leri
SDL'ye GÖRÜNMEZ; raw JOYBUTTONDOWN/UP ve CONTROLLERAXISMOTION event'i hiç
üretilmez. Ayarlar ekranındaki binding capture'ı yalnızca raw pygame
event'lerinden beslendiği için Steam Input fallback cihazların
buton/trigger basışlarını HİÇ görmüyordu — capture ekranında bu cihazla
binding yapılamıyordu.

Bu testler şunları doğrular:
- GamepadManager, _SteamInputJoystick cihazlarının prev→now buton/trigger
  geçişlerini _capture_edges kuyruğuna yazar (kenar: device_key,
  canonical_index, pressed, timestamp_ms).
- consume_capture_edges() kuyruğu döndürür VE temizler.
- SDL cihazları için kuyruğa YAZILMAZ (raw event zaten var; çift kayıt
  engellenir).
- Ayarlar ekranı update() sürücüsü kenarları tüketip binding uygular.
- Capture'ı AÇAN Steam Input basışı kendine bağlanmaz (aktivasyon kenarı
  capture açılışında atılır).
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


def _make_steam_gamepad(gm_mod):
    """Sahte _SteamInputJoystick cihazı ve GamepadState'i kurar."""
    handle = 4242
    key = -1000000 - handle
    joystick = gm_mod._SteamInputJoystick({'handle': handle, 'buttons': {}}, key)
    gp = gm_mod.GamepadState(
        joystick=joystick,
        controller=joystick,
        gamepad_type=gm_mod.GamepadType.XBOX,
        name=joystick.get_name(),
        guid=joystick.get_guid(),
        instance_id=key,
        device_index=key,
    )
    return key, joystick, gp


@pytest.fixture()
def steam_gpm():
    """Singleton GamepadManager'ı test boyunca sahte Steam cihazıyla kurar."""
    os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
    os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
    _ensure_src_on_path()

    import pygame
    if not hasattr(pygame, 'K_h'):
        pytest.skip('pygame stub environment')
    pygame.init()
    pygame.joystick.init()

    import gamepad_manager as gm_mod

    gpm = gm_mod.get_gamepad_manager()
    orig_check = gpm._check_connections
    orig_sync = gpm._sync_steam_input_gamepads
    gpm._check_connections = lambda: None
    gpm._sync_steam_input_gamepads = lambda: None
    gpm.enabled = True

    key, joystick, gp = _make_steam_gamepad(gm_mod)
    gpm.gamepads[key] = gp
    try:
        yield gpm, gm_mod, key, joystick, gp
    finally:
        gpm.gamepads.pop(key, None)
        gpm._check_connections = orig_check
        gpm._sync_steam_input_gamepads = orig_sync
        if hasattr(gpm, 'consume_capture_edges'):
            gpm.consume_capture_edges()


def test_update_records_steam_input_button_edges(steam_gpm):
    """Steam cihazında buton basışı/bırakışı kuyruğa kenar yazmalı."""
    gpm, gm_mod, key, joystick, gp = steam_gpm

    assert hasattr(gpm, 'consume_capture_edges'), \
        'GamepadManager.consume_capture_edges() tanımlı olmalı'

    # Kalibrasyon frame'i: boş snapshot
    gpm.update(16.0)
    gpm.consume_capture_edges()

    # 'a' (canonical 0) basıldı
    joystick.update_snapshot({'handle': 4242, 'buttons': {'a': True}})
    gpm.update(16.0)
    edges = gpm.consume_capture_edges()
    down_edges = [e for e in edges if e[1] == 0 and e[2] is True]
    assert down_edges, 'buton basış kenarı kuyruğa yazılmalı'
    dev_key, _, pressed, ts = down_edges[0]
    assert dev_key == key, 'kenar cihaz anahtarını taşımalı'
    assert isinstance(ts, int)

    # Kuyruk tüketildi: tekrar consume boş dönmeli
    assert gpm.consume_capture_edges() == []

    # 'a' bırakıldı
    joystick.update_snapshot({'handle': 4242, 'buttons': {}})
    gpm.update(16.0)
    edges = gpm.consume_capture_edges()
    up_edges = [e for e in edges if e[1] == 0 and e[2] is False]
    assert up_edges, 'buton bırakış kenarı kuyruğa yazılmalı'


def test_update_records_steam_input_trigger_edges(steam_gpm):
    """Steam cihazında LT (100) basışı kuyruğa kenar yazmalı."""
    gpm, gm_mod, key, joystick, gp = steam_gpm

    gpm.update(16.0)
    gpm.consume_capture_edges()

    joystick.update_snapshot({'handle': 4242, 'buttons': {'left_trigger': True}})
    gpm.update(16.0)
    edges = gpm.consume_capture_edges()
    lt_down = [e for e in edges if e[1] == 100 and e[2] is True]
    assert lt_down, 'LT (pseudo-index 100) basış kenarı yazılmalı'


def test_sdl_devices_do_not_queue_capture_edges(steam_gpm):
    """SDL cihazları kenar kuyruğuna yazILMAMALI (raw event zaten var; çift kayıt önlenir)."""
    gpm, gm_mod, key, joystick, gp = steam_gpm

    class MockSdlJoystick:
        def get_init(self): return True
        def get_name(self): return "Mock SDL"
        def get_numaxes(self): return 6
        def get_axis(self, idx): return 0.0
        def get_numhats(self): return 1
        def get_hat(self, idx): return (0, 0)

    sdl_gp = gm_mod.GamepadState(
        joystick=MockSdlJoystick(), controller=None,
        instance_id=7, device_index=7,
    )
    gpm.gamepads[7] = sdl_gp
    try:
        # SDL cihazında geçiş VAR (prev False → now True); kayıt yine
        # yazılmamalı çünkü SDL cihazları zaten raw pygame event'i üretir.
        sdl_gp.prev_buttons[2] = False
        sdl_gp.buttons[2] = True
        assert hasattr(gpm, '_record_capture_edges'), \
            'GamepadManager._record_capture_edges() tanımlı olmalı'
        gpm._record_capture_edges(sdl_gp)
        edges = gpm.consume_capture_edges()
        assert all(e[0] != 7 for e in edges), \
            'SDL cihazı kenar kuyruğuna yazılmamalı (çift kayıt önlenir)'
    finally:
        gpm.gamepads.pop(7, None)


@pytest.fixture(scope='module')
def live_screen():
    """GP-006 tüketicisi: gerçek TabbedSettingsScreen instance'ı.

    Dönen gamepad_manager modülü, sst'nin import ettiği AYNI modül
    kimliğidir: conftest'in src.*/flat alias senkronu sst modülünü
    sys.modules'ten koparabildiği için, uçtan uca test sst ile aynı
    singleton'a ancak bu yakalanmış referans üzerinden güvenle erişir.
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


def test_settings_update_consumes_steam_edges_to_bind(live_screen):
    """Uçtan uca: Steam cihazı basış/bırakış → kenar kuyruğu → capture binding.

    Kurulum, sst instance'ının bağlı olduğu gamepad_manager modülünün
    singleton'ı üzerinden yapılır: conftest alias senkronu sst'yi
    sys.modules'ten koparsa bile kimlik uyumu bozulmaz.
    """
    pygame, inst, gm_mod = live_screen

    gpm = gm_mod.get_gamepad_manager()
    orig_check = gpm._check_connections
    orig_sync = gpm._sync_steam_input_gamepads
    gpm._check_connections = lambda: None
    gpm._sync_steam_input_gamepads = lambda: None
    gpm.enabled = True

    key, joystick, gp = _make_steam_gamepad(gm_mod)
    gpm.gamepads[key] = gp
    try:
        gamepad_cfg = inst._control_config.setdefault('gamepad', {})
        if not isinstance(gamepad_cfg.get('hard_drop'), dict):
            gamepad_cfg['hard_drop'] = {'primary': -1, 'secondary': -1}
        gamepad_cfg['hard_drop']['primary'] = 10

        inst._waiting_for_key = True
        inst._pending_keybind_item = {
            'type': 'keybind', 'section': 'gamepad.ingame', 'action_key': 'hard_drop',
        }
        inst._pending_keybind_slot = 'primary'
        inst._capture_started_by_gamepad_click = False
        inst._swallow_next_keydown = False
        inst._swallow_next_gamepad_click = False
        inst._reset_hold_to_clear_state()

        # Kalibrasyon frame'i
        gpm.update(16.0)
        gpm.consume_capture_edges()

        # 'a' basıldı → kenar → settings update() → CONTROLLERBUTTONDOWN eşdeğeri
        joystick.update_snapshot({'handle': 4242, 'buttons': {'a': True}})
        gpm.update(16.0)
        inst.update(16.0)
        assert inst._hold_to_clear_pressed_signature == ('btn', 0), \
            'Steam basış kenarı capture imzası kurmalı'
        assert inst._waiting_for_key is True

        # 'a' bırakıldı → kenar → settings update() → binding uygulanmalı
        joystick.update_snapshot({'handle': 4242, 'buttons': {}})
        gpm.update(16.0)
        inst.update(16.0)
        assert inst._waiting_for_key is False, 'bırakış kenarı capture\'ı tamamlaymalı'
        assert gamepad_cfg['hard_drop']['primary'] == 0, \
            'Steam cihazının canonical buton 0 primary slota yazılmalı'
        # Temizlik
        gamepad_cfg['hard_drop']['primary'] = -1
    finally:
        gpm.gamepads.pop(key, None)
        gpm._check_connections = orig_check
        gpm._sync_steam_input_gamepads = orig_sync
        if hasattr(gpm, 'consume_capture_edges'):
            gpm.consume_capture_edges()


def test_capture_opening_discards_activation_press_edge(live_screen):
    """GP-006 (kritik): capture'ı AÇAN Steam Input basışı kendine bağlanmamalı.

    Gerçek zamanlama: Steam Input cihazında keybind satırını aşan A basışı
    gamepad_mgr.update() içinde HEM kenar kuyruğuna yazılır HEM menu_confirm
    sentetik K_RETURN'ü üretir; K_RETURN satırı aktive edip capture'ı AÇAR
    (settings_screen_tabbed.py keybind satırı aktive etme yolu ->
    _start_keybind_capture). Aynı karedeki kenar tekrar-oynatması bu basışı
    yakalarsa bırakışta aksiyon A'ya bağlanır — kullanıcı yeni buton
    bağlayamaz. Düzeltme: capture açılışı, açılış anına kadar kayıtlı
    kenarları atar; yalnızca SONRAKİ basışlar bağlanır.
    """
    pygame, inst, gm_mod = live_screen

    gpm = gm_mod.get_gamepad_manager()
    orig_check = gpm._check_connections
    orig_sync = gpm._sync_steam_input_gamepads
    gpm._check_connections = lambda: None
    gpm._sync_steam_input_gamepads = lambda: None
    gpm.enabled = True

    key, joystick, gp = _make_steam_gamepad(gm_mod)
    gpm.gamepads[key] = gp
    try:
        gamepad_cfg = inst._control_config.setdefault('gamepad', {})
        if not isinstance(gamepad_cfg.get('hard_drop'), dict):
            gamepad_cfg['hard_drop'] = {'primary': -1, 'secondary': -1}
        gamepad_cfg['hard_drop']['primary'] = 10

        # Kalibrasyon frame'i: boş snapshot, kuyruk temiz.
        gpm.update(16.0)
        gpm.consume_capture_edges()

        # 1) A basıldı: kenar KAYDEDİLDİ (henüz capture yok — gerçek
        #    senaryoda sentetik K_RETURN henüz işlenmedi).
        joystick.update_snapshot({'handle': 4242, 'buttons': {'a': True}})
        gpm.update(16.0)
        assert any(e[1] == 0 and e[2] is True for e in gpm._capture_edges), \
            'aktivasyon basışının kenarı kuyrukta durmalı'

        # 2) Aynı kare: sentetik menu_confirm keybind satırını aktive etti
        #    -> _start_keybind_capture çağrıldı (gerçek giriş noktasıyla
        #    birebir aynı çağrı).
        inst._start_keybind_capture(
            {'type': 'keybind', 'section': 'gamepad.ingame', 'action_key': 'hard_drop'},
            slot='primary',
        )
        assert inst._waiting_for_key is True
        assert not any(e[1] == 0 for e in gpm._capture_edges), \
            'capture açılışı, açan basışın kenarını atmalı (GP-006 düzeltmesi)'

        # 3) Aynı karede settings update(): tekrar-oynatma OLMAMALI.
        inst.update(16.0)
        assert inst._hold_to_clear_pressed_signature is None, \
            'capture\'ı açan basış imza kurmamalı (kendine bağlanma)'

        # 4) A bırakıldı: up kenarı tekrar-oynatılır ama imza yok ->
        #    apply EDİLMEMELİ, capture açık kalmalı.
        joystick.update_snapshot({'handle': 4242, 'buttons': {}})
        gpm.update(16.0)
        inst.update(16.0)
        assert inst._waiting_for_key is True, \
            'aktivasyon butonunun bırakışı capture\'ı kapatmamalı'
        assert gamepad_cfg['hard_drop']['primary'] == 10, \
            'binding değişmemeli (A kendine bağlanmamalı)'

        # 5) Kullanıcı YENİ buton (B, canonical 1) basar -> O bağlanmalı.
        joystick.update_snapshot({'handle': 4242, 'buttons': {'b': True}})
        gpm.update(16.0)
        inst.update(16.0)
        assert inst._hold_to_clear_pressed_signature == ('btn', 1), \
            'capture sonrası yeni basış imza kurmalı'
        joystick.update_snapshot({'handle': 4242, 'buttons': {}})
        gpm.update(16.0)
        inst.update(16.0)
        assert inst._waiting_for_key is False, \
            'yeni butonun bırakışı capture\'ı tamamlamalı'
        assert gamepad_cfg['hard_drop']['primary'] == 1, \
            'yeni buton (B=1) primary slota yazılmalı'
        # Temizlik
        gamepad_cfg['hard_drop']['primary'] = -1
    finally:
        gpm.gamepads.pop(key, None)
        gpm._check_connections = orig_check
        gpm._sync_steam_input_gamepads = orig_sync
        if hasattr(gpm, 'consume_capture_edges'):
            gpm.consume_capture_edges()
