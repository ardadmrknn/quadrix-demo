"""GP-002 — Capture sırasında sentetik gamepad Escape izolasyonu testleri.

İade nedeni: gamepad'in `menu_back` (B/Circle) sentetik event'i
`pygame.KEYDOWN, key=K_ESCAPE, from_gamepad=True` üretir. Ayarlar ekranında
gamepad binding capture açıkken bu sentetik event GERÇEK klavye Escape'iyle
ayrılamıyor ve capture'ı iptal ediyordu: kullanıcı B'yi yeni binding olarak
kaydetmeye çalıştığı an capture kapanıyordu. Aynı sentetik event klavye
keybind capture'ını da iptal edebiliyordu.

Bu testler `from_gamepad=True` işaretli sentetik Escape'in capture iptal
ETMEMESİNİ, gerçek klavye Escape'inin iptal ETMESİNİ doğrular.
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


@pytest.fixture(scope='module')
def live_screen():
    """Tek bir display ve TabbedSettingsScreen instance hazırlar."""
    os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
    _ensure_src_on_path()

    # Önceki testler stub modüller yüklemiş olabilir; gerçek modüllere
    # zorlamak için ilgili anahtarları temizle. pygame'i silMEzdik:
    # submodülleri yarı yüklü kalıp circular import'a yol açıyor.
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
    from settings_manager import SettingsManager

    sm = SettingsManager()
    screen = pygame.display.get_surface()
    inst = sst.TabbedSettingsScreen(screen, None, sm)
    inst.current_tab = 3  # Kontroller
    inst._rebuild_tab_content()
    # Testler gerçek ayar dosyasına yazmasın (diğer yeni gamepad test
    # dosyalarıyla aynı kalıp); binding tamamlayan testler var.
    inst._persist_controls = lambda: None
    return pygame, inst


def _open_capture(inst, section: str) -> None:
    """Capture modunu simüle et: verilen section için binding beklemeye başla."""
    inst._waiting_for_key = True
    inst._pending_keybind_item = {
        'type': 'keybind',
        'section': section,
        'action_key': 'hard_drop' if section.startswith('gamepad') else 'move_left',
    }
    inst._pending_keybind_slot = 'primary'
    inst._capture_started_by_gamepad_click = False
    inst._swallow_next_keydown = False
    inst._swallow_next_gamepad_click = False


def _synthetic_menu_back_escape(pygame):
    """GamepadManager'ın ürettiği sentetik menu_back event'inin birebir kopyası."""
    return pygame.event.Event(
        pygame.KEYDOWN, key=pygame.K_ESCAPE, mod=0, unicode='',
        scancode=0, from_gamepad=True, device_index=0, action='menu_back',
    )


def test_synthetic_gamepad_escape_does_not_cancel_gamepad_capture(live_screen):
    """B/Circle sentetik K_ESCAPE, gamepad capture açıkken capture'ı İPTAL ETMEMELİ."""
    pygame, inst = live_screen
    _open_capture(inst, 'gamepad.ingame')

    inst.handle_input(_synthetic_menu_back_escape(pygame))
    assert inst._waiting_for_key is True, \
        'from_gamepad=True sentetik Escape capture\'ı iptal etmemeli'
    assert inst._pending_keybind_item is not None

    # KEYUP pulse'u da aynı şekilde etkisiz olmalı
    inst.handle_input(pygame.event.Event(
        pygame.KEYUP, key=pygame.K_ESCAPE, mod=0,
        from_gamepad=True, device_index=0, action='menu_back',
    ))
    assert inst._waiting_for_key is True


def test_real_keyboard_escape_cancels_gamepad_capture(live_screen):
    """Gerçek klavye Escape'i gamepad capture'ını iptal etmeyi sürdürmeli."""
    pygame, inst = live_screen
    _open_capture(inst, 'gamepad.ingame')

    inst.handle_input(pygame.event.Event(
        pygame.KEYDOWN, key=pygame.K_ESCAPE, mod=0, unicode='',
    ))
    assert inst._waiting_for_key is False, 'gerçek Escape capture\'ı iptal etmeli'
    assert inst._pending_keybind_item is None


def test_synthetic_gamepad_escape_does_not_cancel_keyboard_capture(live_screen):
    """Sentetik K_ESCAPE, klavye keybind capture açıkken de capture'ı İPTAL ETMEMELİ."""
    pygame, inst = live_screen
    _open_capture(inst, 'single_player')

    inst.handle_input(_synthetic_menu_back_escape(pygame))
    assert inst._waiting_for_key is True, \
        'from_gamepad=True sentetik Escape klavye capture\'ını da iptal etmemeli'


def test_real_keyboard_escape_cancels_keyboard_capture(live_screen):
    """Gerçek klavye Escape'i klavye capture'ını iptal etmeyi sürdürmeli."""
    pygame, inst = live_screen
    _open_capture(inst, 'single_player')

    inst.handle_input(pygame.event.Event(
        pygame.KEYDOWN, key=pygame.K_ESCAPE, mod=0, unicode='',
    ))
    assert inst._waiting_for_key is False
    assert inst._pending_keybind_item is None


def _synthetic_menu_confirm_return(pygame):
    """GamepadManager'ın ürettiği sentetik menu_confirm K_RETURN'unun birebir kopyası."""
    return pygame.event.Event(
        pygame.KEYDOWN, key=pygame.K_RETURN, mod=0, unicode='',
        scancode=0, from_gamepad=True, device_index=0, action='menu_confirm',
    )


def test_synthetic_gamepad_keydown_is_not_captured_as_keyboard_binding(live_screen):
    """GP-002 (eksik kapsam): sentetik gamepad KEYDOWN'ları klavye keybind
    capture'ında GERÇEK tuş gibi YAKALANMAMALI.

    Escape iptal yolu kapatılırken yakalama/yazma yolu açık kalmıştı:
    klavye capture açıkken gamepad A'ya basılırsa menü bağlamında üretilen
    sentetik K_RETURN ('key', 13) imzası kurulup bırakışta klavye slotuna
    'return' yazılıyordu — kullanıcı klavyeye hiç dokunmamışken.
    """
    pygame, inst = live_screen
    _open_capture(inst, 'single_player')
    inst._reset_hold_to_clear_state()

    inst.handle_input(_synthetic_menu_confirm_return(pygame))
    assert inst._hold_to_clear_pressed_signature is None, \
        'sentetik gamepad KEYDOWN klavye capture imzası kurmamalı'
    assert inst._waiting_for_key is True

    # Sentetik KEYUP da apply tetiklememeli.
    inst.handle_input(pygame.event.Event(
        pygame.KEYUP, key=pygame.K_RETURN, mod=0,
        from_gamepad=True, device_index=0, action='menu_confirm',
    ))
    assert inst._waiting_for_key is True, \
        'sentetik gamepad KEYUP capture\'ı tamamlamamalı'
    assert inst._pending_keybind_item is not None


def test_real_keyboard_keydown_still_captured_in_keyboard_binding(live_screen):
    """Yan etki kontrolü: GERÇEK klavye KEYDOWN/KEYUP yakalama sürdürülmeli.

    GP-002 guard'ı yalnızca from_gamepad=True event'leri yok sayar;
    gerçek tuşların bas→imza, bırak→apply zinciri değişmemeli.
    """
    pygame, inst = live_screen
    _open_capture(inst, 'single_player')
    inst._reset_hold_to_clear_state()
    sp_cfg = inst._control_config.setdefault('single_player', {})
    orig_binding = sp_cfg.get('move_left')

    try:
        inst.handle_input(pygame.event.Event(
            pygame.KEYDOWN, key=pygame.K_a, mod=0, unicode='a',
        ))
        assert inst._hold_to_clear_pressed_signature == ('key', pygame.K_a), \
            'gerçek klavye KEYDOWN imza kurmalı'

        inst.handle_input(pygame.event.Event(pygame.KEYUP, key=pygame.K_a, mod=0))
        assert inst._waiting_for_key is False, \
            'gerçek klavye KEYUP capture\'ı tamamlamalı'
    finally:
        sp_cfg['move_left'] = orig_binding
        inst._reset_hold_to_clear_state()
        inst._waiting_for_key = False
        inst._pending_keybind_item = None
