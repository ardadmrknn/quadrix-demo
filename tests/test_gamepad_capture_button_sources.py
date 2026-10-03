"""Gamepad binding capture girdi kaynakları testleri (v2 + demo paritesi).

Gamepad_Iade_Nedeni_Cozum_Proje_Referansi.md 10.4 — B/Circle capture
tablosunun HAM SDL event yolu ve ek kaynak senaryoları:

- Kaynak sözleşme: capture YALNIZ gerçek pygame event'lerinden beslenir
  (CONTROLLERBUTTONDOWN/UP + JOYBUTTONDOWN/UP, trigger eksenleri,
  JOYHATMOTION, gerçek KEYDOWN/KEYUP); GP-002 — from_gamepad=True
  sentetik KEY event'leri capture'da reddedilir.
- Buton: BUTTONDOWN imzayı kurar ('btn', i), EŞLEŞEN BUTTONUP binding'i
  yazar; capture açılmadan önce basılmış butonun bırakışı imza
  uyuşmazlığından apply ETMEZ.
- Trigger (LT/RT token 100/101) ve hat (11-14) anında uygulanır (imza
  yok); analog stick eksenleri HİÇBİR durumda binding yazmaz.
- Yazım tek seferlik: apply sonrası capture kapanır, tekrar gelen
  BUTTONUP ikinci yazım yapamaz.
- Binding yazımından sonra _swallow_next_keydown bir sonraki KEYDOWN'u
  (capture'ı kapatan butonun sentetik menü repeat'i) tek seferlik yutar.
- Pointer modunda _should_swallow_post_capture_gamepad_click yalnızca
  menü+pointer aktifken menü-confirm/R3 bırakışını yutacak şekilde
  kurulur; capture bir gamepad tıklamasıyla AÇILDIYSA bu yutma devre
  dışıdır (kullanıcı kendi A bırakışını yutarız yanılsaması).
- İkinci cihazın butonu kurulmuş imzayı ÇALMAZ (capture girdisi
  cihaz-agnostik, imza ilk basışta kurulur).

Mevcut kapsamın boşlukları bu dosyada kapatılır: gerçek girdi noktası
(_start_keybind_capture sözleşmesi + GP-006 bayat kenar dreyni), RAW
buton zinciri, tek-kez yazım, secondary slot, pointer/swallow etkileşimi,
iki cihaz, hat + stick kayıtsızlığı. (Sentetik Escape/klavye iptali
test_gamepad_capture_escape_isolation.py'de, Steam kenar zinciri
test_gamepad_steam_capture_edges.py'de, trigger kabul/red
test_gamepad_menu_trigger_bindings.py'de zaten kapsanır.)

Desen referansı: tests/test_gamepad_hold_to_clear_canonical_state.py
(live_screen fixture — sst ile AYNI modül kimliğinde gamepad_manager).
"""

from __future__ import annotations

import os
import sys

import pytest

_SRC_DIR_STR = os.path.join(os.path.dirname(__file__), '..', 'src')
if _SRC_DIR_STR not in sys.path:
    sys.path.insert(0, _SRC_DIR_STR)


@pytest.fixture(scope='module')
def live_screen():
    """Tek display + TabbedSettingsScreen; dönen gamepad_manager modülü,
    settings_screen_tabbed'ın import ettiği AYNI modül kimliğidir."""
    os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
    os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

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
    import gamepad_manager as gm_mod
    from settings_manager import SettingsManager

    sm = SettingsManager()
    screen = pygame.display.get_surface()
    inst = sst.TabbedSettingsScreen(screen, None, sm)
    inst.current_tab = 3  # Kontroller
    inst._rebuild_tab_content()
    inst._persist_controls = lambda: None
    return pygame, inst, gm_mod


def _gamepad_cfg(inst, action_key='hard_drop'):
    """Testin yazacağı gamepad binding slot'unu hazırlar."""
    cfg = inst._control_config.setdefault('gamepad', {})
    raw = cfg.get(action_key)
    if not isinstance(raw, dict):
        raw = {'primary': -1, 'secondary': -1}
        cfg[action_key] = raw
    raw['primary'] = -1
    raw['secondary'] = -1
    return raw


def _start_capture(inst, action_key='hard_drop', section='gamepad.ingame', slot='primary', by_click=False):
    """Gerçek girdi noktası: _start_keybind_capture (UI click/ENTER buraya
    düşer). Elle durum set etmek yerine kaynak API'yi çağırır."""
    item = {'type': 'keybind', 'section': section, 'action_key': action_key}
    inst._start_keybind_capture(item, slot, by_click)
    return item


def _controller(pygame, event_type, button):
    return pygame.event.Event(event_type, button=button)


def _synthetic_menu_back(pygame):
    """Menü bağlamında B/Circle'ın ürettiği sentetik menu_back Escape (GP-002)."""
    return pygame.event.Event(
        pygame.KEYDOWN, key=pygame.K_ESCAPE, mod=0, unicode='', scancode=0,
        from_gamepad=True, device_index=0, action='menu_back',
    )


# ---------------------------------------------------------------------------
# Girdi noktası sözleşmesi
# ---------------------------------------------------------------------------

def test_start_keybind_capture_sets_state_and_drains_stale_edges(live_screen):
    """_start_keybind_capture: dört durum değişkenini kurar, hold-to-clear'i
    sıfırlar ve GP-006 — açılış anına kadar birikmiş Steam kenarlarını
    dreyn eder (capture'ı AÇAN basışın kenarı aynı karede tekrar-oynatmaz)."""
    pygame, inst, gm_mod = live_screen
    gpm = gm_mod.get_gamepad_manager()
    gpm._check_connections = lambda: None
    _gamepad_cfg(inst)

    gpm._capture_edges.append(('steam-pad', 5, True, 1.0))
    gpm._capture_edges.append(('steam-pad', 100, False, 2.0))
    try:
        item = _start_capture(inst, by_click=True)

        assert inst._waiting_for_key is True
        assert inst._pending_keybind_item == item
        assert inst._pending_keybind_slot == 'primary'
        assert inst._capture_started_by_gamepad_click is True
        assert inst._hold_to_clear_pressed_signature is None
        assert inst._hold_to_clear_pressed_at_ms is None
        assert list(gpm._capture_edges) == [], (
            'capture açılışı bayat kenarları dreyn etmeli (GP-006)'
        )
    finally:
        gpm._capture_edges.clear()
        inst._waiting_for_key = False
        inst._pending_keybind_item = None


# ---------------------------------------------------------------------------
# 10.4 B/Circle capture tablosu — HAM SDL event zinciri
# ---------------------------------------------------------------------------

def test_b_circle_capture_full_chain_raw_events(live_screen):
    """10.4 tam zincir (ham SDL yolu): (1) A click capture'ı açar →
    (2) fiziksel B (buton 1) down imzayı kurar → (3) sentetik menu_back
    Escape capture'ı İPTAL ETMEZ → (4) B up binding'i yazar → capture
    kapanır, bir sonraki sentetik KEYDOWN yutulmak üzere işaretlenir."""
    pygame, inst, gm_mod = live_screen
    gpm = gm_mod.get_gamepad_manager()
    gpm._check_connections = lambda: None
    raw = _gamepad_cfg(inst)

    _start_capture(inst, by_click=True)

    # (2) Fiziksel B down → hold-to-clear imzası.
    inst.handle_input(_controller(pygame, pygame.CONTROLLERBUTTONDOWN, 1))
    assert inst._hold_to_clear_pressed_signature == ('btn', 1)
    assert inst._waiting_for_key is True

    # (3) B menu_back'e bağlı → sentetik Escape'i gelir; GP-002: iptal YOK.
    inst.handle_input(_synthetic_menu_back(pygame))
    assert inst._waiting_for_key is True, 'sentetik menu_back capture\'ı iptal etmemeli'
    assert inst._hold_to_clear_pressed_signature == ('btn', 1)

    # (4) B up → binding yazılır.
    inst.handle_input(_controller(pygame, pygame.CONTROLLERBUTTONUP, 1))

    assert raw['primary'] == 1
    assert inst._waiting_for_key is False
    assert inst._pending_keybind_item is None
    assert inst._swallow_next_keydown is True


def test_capture_opened_after_press_ignores_that_release(live_screen):
    """Capture'ı açan A (buton 0) BASILIYKEN açıldıysa (kenar capture'dan
    önce geçti): A'nın bırakışı imza uyuşmazlığından binding YAZMAZ —
    capture yeni (farklı) bir girdi beklemeye devam eder."""
    pygame, inst, gm_mod = live_screen
    gpm = gm_mod.get_gamepad_manager()
    gpm._check_connections = lambda: None
    raw = _gamepad_cfg(inst)

    # A down capture'dan ÖNCE (menü tıklamasını tetikleyen basış).
    inst.handle_input(_controller(pygame, pygame.CONTROLLERBUTTONDOWN, 0))
    # Şimdi capture açılır (imza hâlâ None — açılış kenarları dreyn etti).
    _start_capture(inst, by_click=True)
    assert inst._hold_to_clear_pressed_signature is None

    inst.handle_input(_controller(pygame, pygame.CONTROLLERBUTTONUP, 0))

    assert inst._waiting_for_key is True, 'capture açan butonun bırakışı apply etmemeli'
    assert raw['primary'] == -1
    assert inst._hold_to_clear_pressed_signature is None


def test_binding_written_exactly_once_on_duplicate_release(live_screen):
    """Binding TEK SEFER yazılır: apply sonrası capture kapanır; tekrar
    gelen BUTTONUP ikinci bir yazım yapamaz (capture bloğundan çıkar)."""
    pygame, inst, gm_mod = live_screen
    gpm = gm_mod.get_gamepad_manager()
    gpm._check_connections = lambda: None
    raw = _gamepad_cfg(inst)

    _start_capture(inst)
    inst.handle_input(_controller(pygame, pygame.CONTROLLERBUTTONDOWN, 1))
    inst.handle_input(_controller(pygame, pygame.CONTROLLERBUTTONUP, 1))
    assert raw['primary'] == 1

    # Bırakış tekrarlanır (çift up / SDL tekrarı).
    inst.handle_input(_controller(pygame, pygame.CONTROLLERBUTTONUP, 1))

    assert raw['primary'] == 1
    assert inst._waiting_for_key is False


def test_secondary_slot_capture_writes_secondary_slot(live_screen):
    """Secondary slot capture'ı YALNIZ secondary alanını yazar."""
    pygame, inst, gm_mod = live_screen
    gpm = gm_mod.get_gamepad_manager()
    gpm._check_connections = lambda: None
    raw = _gamepad_cfg(inst)
    raw['primary'] = 7

    _start_capture(inst, slot='secondary')
    inst.handle_input(_controller(pygame, pygame.CONTROLLERBUTTONDOWN, 2))
    inst.handle_input(_controller(pygame, pygame.CONTROLLERBUTTONUP, 2))

    assert raw['secondary'] == 2
    assert raw['primary'] == 7, "primary slot'a dokunulmamalı"


# ---------------------------------------------------------------------------
# Yutma bayrakları (sentetik repeat + pointer modu)
# ---------------------------------------------------------------------------

def test_swallow_next_keydown_eats_first_synthetic_menu_keydown_once(live_screen):
    """Binding yazımından sonra gelen ilk KEYDOWN (capture'ı kapatan
    butonun sentetik menü repeat'i) tek seferlik yutulur; ikincisi artık
    yutulmaz."""
    pygame, inst, gm_mod = live_screen
    gpm = gm_mod.get_gamepad_manager()
    gpm._check_connections = lambda: None
    _gamepad_cfg(inst)

    _start_capture(inst)
    inst.handle_input(_controller(pygame, pygame.CONTROLLERBUTTONDOWN, 1))
    inst.handle_input(_controller(pygame, pygame.CONTROLLERBUTTONUP, 1))
    assert inst._swallow_next_keydown is True

    inst.handle_input(_synthetic_menu_back(pygame))
    assert inst._swallow_next_keydown is False, 'yutma tek seferlik olmalı'

    # İkinci sentetik KEYDOWN artık yutulmaz (bayrak tüketildi).
    inst.handle_input(_synthetic_menu_back(pygame))
    assert inst._swallow_next_keydown is False


def test_capture_opened_by_gamepad_click_suppresses_post_capture_click_swallow(live_screen):
    """Pointer modunda capture bir gamepad tıklamasıyla AÇILDIYSA, capture'ı
    kapatan butonun bırakışı menü-click yutması KURULMAZ (kullanıcının kendi
    A bırakışı yutulurdu — yanlışlık)."""
    pygame, inst, gm_mod = live_screen
    gpm = gm_mod.get_gamepad_manager()
    gpm._check_connections = lambda: None
    _gamepad_cfg(inst)

    gpm.set_context(gm_mod.GamepadManager.CONTEXT_MENU)
    gpm._menu_pointer_active = True
    try:
        _start_capture(inst, by_click=True)
        inst.handle_input(_controller(pygame, pygame.CONTROLLERBUTTONDOWN, 0))
        inst.handle_input(_controller(pygame, pygame.CONTROLLERBUTTONUP, 0))

        assert inst._waiting_for_key is False
        assert inst._swallow_next_gamepad_click is False, (
            'gamepad tıklamasıyla açılan capture sonrası menü-click yutma '
            'kurulmamalı'
        )
    finally:
        gpm._menu_pointer_active = False


def test_pointer_mode_post_capture_click_swallowed_when_opened_by_keyboard(live_screen):
    """Pointer modu aktif + capture klavyeyle açıldıysa: menü-confirm (A)
    bırakışı sonrası yutma kurulur ve bir sonraki sentetik sol-tık
    (MOUSEBUTTONDOWN from_gamepad) yutulur."""
    pygame, inst, gm_mod = live_screen
    gpm = gm_mod.get_gamepad_manager()
    gpm._check_connections = lambda: None
    _gamepad_cfg(inst)

    gpm.set_context(gm_mod.GamepadManager.CONTEXT_MENU)
    gpm._menu_pointer_active = True
    try:
        _start_capture(inst, by_click=False)
        inst.handle_input(_controller(pygame, pygame.CONTROLLERBUTTONDOWN, 0))
        inst.handle_input(_controller(pygame, pygame.CONTROLLERBUTTONUP, 0))

        assert inst._swallow_next_gamepad_click is True
        assert inst._swallow_next_gamepad_click_deadline_ms > 0

        synthetic_click = pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, button=1, pos=(2000, 2000),
            from_gamepad=True,
        )
        inst.handle_input(synthetic_click)
        assert inst._swallow_next_gamepad_click is False, 'yutma tek seferlik'
    finally:
        gpm._menu_pointer_active = False


# ---------------------------------------------------------------------------
# Çoklu cihaz + binding yazmayan kaynaklar
# ---------------------------------------------------------------------------

def test_second_gamepad_button_does_not_steal_signature(live_screen):
    """İkinci cihazın buton basışı KURULMUŞ imzayı değiştirmez: capture
    girdisi cihaz-agnostik olsa da imza İLK basışta kurulur ve farklı
    butonun basışı onu ezmez; eşleşen bırakış binding'i yazar."""
    pygame, inst, gm_mod = live_screen
    gpm = gm_mod.get_gamepad_manager()
    gpm._check_connections = lambda: None
    raw = _gamepad_cfg(inst)

    pad_a = gm_mod.GamepadState(device_index=0, instance_id=111)
    pad_b = gm_mod.GamepadState(device_index=1, instance_id=222)
    gpm.gamepads[0] = pad_a
    gpm.gamepads[1] = pad_b
    try:
        _start_capture(inst)

        # Cihaz A'dan buton 1 basışı (imzayı kurar).
        inst.handle_input(_controller(pygame, pygame.CONTROLLERBUTTONDOWN, 1))
        assert inst._hold_to_clear_pressed_signature == ('btn', 1)

        # Cihaz B'den FARKLI buton (2) basışı — imza ezilmemeli.
        inst.handle_input(_controller(pygame, pygame.CONTROLLERBUTTONDOWN, 2))
        assert inst._hold_to_clear_pressed_signature == ('btn', 1), (
            'ikinci cihazın farklı butonu imzayı çalmamalı'
        )

        # Eşleşen bırakış (cihaz A'dan buton 1) binding'i yazar.
        inst.handle_input(_controller(pygame, pygame.CONTROLLERBUTTONUP, 1))
        assert raw['primary'] == 1
        assert inst._waiting_for_key is False
    finally:
        gpm.gamepads.pop(0, None)
        gpm.gamepads.pop(1, None)


def test_outgame_hat_capture_applies_direction_and_stick_axis_is_inert(live_screen):
    """Hat yönü anında uygulanır (canonical 11=Up); analog stick eksenleri
    hiçbir durumda binding yazmaz."""
    pygame, inst, gm_mod = live_screen
    gpm = gm_mod.get_gamepad_manager()
    gpm._check_connections = lambda: None
    raw = _gamepad_cfg(inst)

    _start_capture(inst, section='gamepad.outgame')
    inst.handle_input(pygame.event.Event(pygame.JOYHATMOTION, hat=0, value=(0, 1)))

    assert raw['primary'] == 11, 'D-pad Up hat yönü canonical 11 olarak yazılmalı'
    assert inst._waiting_for_key is False

    # Analog stick ekseni binding YAZMAZ; capture açık kalır.
    raw2 = _gamepad_cfg(inst, action_key='rotate')
    _start_capture(inst, action_key='rotate')
    inst.handle_input(pygame.event.Event(
        pygame.CONTROLLERAXISMOTION, axis=0, value=1.0,
    ))
    assert inst._waiting_for_key is True, 'stick ekseni capture\'ı kapatmamalı'
    assert raw2['primary'] == -1, 'stick ekseni binding yazmamalı'
    assert inst._hold_to_clear_pressed_signature is None
