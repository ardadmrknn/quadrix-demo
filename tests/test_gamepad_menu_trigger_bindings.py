"""GP-003 — Oyun dışı (menü) aksiyonlarına trigger atama reddi testleri.

İade nedeni: LT/RT tetikleyicileri oyun DIŞI aksiyonlara (menu_confirm,
menu_back, ...) capture ile atanabiliyor ancak menü bağlamında trigger edge
eventi HİÇ üretilmiyor — binding kaydediliyor ama runtime'da çalışmıyor
(ölü binding).

ÜRÜN KARARI (Seçenek B, en küçük etki alanı): menü aksiyonlarına trigger
ataması UI'da AÇIKÇA REDDEDİLİR; yerelleştirilmiş uyarı gösterilir, capture
açık kalır. Oyun içi aksiyonlara trigger ataması meşrudir (slot_5/slot_6
varsayılanı zaten trigger'dır) ve çalışmaya devam eder.
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
    # Testler gerçek ayar dosyasına yazmasın: persist çağrılarını kes.
    inst._persist_controls = lambda: None
    return pygame, inst


def _open_capture(inst, section: str, action_key: str) -> None:
    inst._waiting_for_key = True
    inst._pending_keybind_item = {
        'type': 'keybind',
        'section': section,
        'action_key': action_key,
    }
    inst._pending_keybind_slot = 'primary'
    inst._capture_started_by_gamepad_click = False
    inst._swallow_next_keydown = False
    inst._swallow_next_gamepad_click = False


def _left_trigger_press(pygame):
    """LT'yi tam bastıran controller axis event'i (trigger token 100)."""
    return pygame.event.Event(
        pygame.CONTROLLERAXISMOTION,
        axis=pygame.CONTROLLER_AXIS_TRIGGERLEFT,
        value=1.0,
    )


def test_outgame_trigger_capture_rejected(live_screen):
    """Oyun dışı aksiyon capture'ında LT basımı: atama REDDEDİLMELİ, capture açık kalmalı."""
    pygame, inst = live_screen
    gamepad_cfg = inst._control_config.setdefault('gamepad', {})
    before = dict(gamepad_cfg.get('menu_confirm', {})) if isinstance(gamepad_cfg.get('menu_confirm'), dict) else gamepad_cfg.get('menu_confirm')

    _open_capture(inst, 'gamepad.outgame', 'menu_confirm')
    inst.handle_input(_left_trigger_press(pygame))

    assert inst._waiting_for_key is True, 'reddedilen atama capture\'ı kapatmamalı'
    assert inst._pending_keybind_item is not None
    after = gamepad_cfg.get('menu_confirm', {})
    if isinstance(before, dict):
        assert after.get('primary') == before.get('primary'), 'menu_confirm primary slot değişmemeli'
    warn_until = getattr(inst, '_capture_trigger_reject_warning_until_ms', 0)
    assert warn_until > 0, 'reddedilen atama yerelleştirilmiş uyarı zamanlayıcısını kurmalı'


def test_ingame_trigger_capture_accepted(live_screen):
    """Oyun içi aksiyon capture'ında LT basımı: atama UYGULANMALI (primary=100)."""
    pygame, inst = live_screen
    gamepad_cfg = inst._control_config.setdefault('gamepad', {})
    if not isinstance(gamepad_cfg.get('hard_drop'), dict):
        gamepad_cfg['hard_drop'] = {'primary': -1, 'secondary': -1}
    gamepad_cfg['hard_drop']['primary'] = -1

    _open_capture(inst, 'gamepad.ingame', 'hard_drop')
    inst.handle_input(_left_trigger_press(pygame))

    assert inst._waiting_for_key is False, 'geçerli atama capture\'ı kapatmalı'
    assert gamepad_cfg['hard_drop']['primary'] == 100, 'LT (token 100) primary slota yazılmalı'
    # Temizlik: başka testlerin varsayılanını bozmasın
    gamepad_cfg['hard_drop']['primary'] = -1


def test_apply_captured_button_rejects_trigger_token_for_outgame(live_screen):
    """Savunma derinliği: _apply_captured_gamepad_button outgame + 100/101 token'ını yazmamalı."""
    pygame, inst = live_screen
    gamepad_cfg = inst._control_config.setdefault('gamepad', {})
    if not isinstance(gamepad_cfg.get('menu_back'), dict):
        gamepad_cfg['menu_back'] = {'primary': -1, 'secondary': -1}
    gamepad_cfg['menu_back']['primary'] = -1

    _open_capture(inst, 'gamepad.outgame', 'menu_back')
    inst._apply_captured_gamepad_button(100)
    inst._apply_captured_gamepad_button(101)

    assert gamepad_cfg['menu_back']['primary'] == -1, 'trigger token\'ı outgame aksiyona yazılmamalı'


def test_real_keyboard_escape_still_cancels_after_trigger_reject(live_screen):
    """Trigger reddinden sonra gerçek Escape hâlâ capture'ı iptal edebilmeli."""
    pygame, inst = live_screen
    _open_capture(inst, 'gamepad.outgame', 'menu_confirm')
    inst.handle_input(_left_trigger_press(pygame))
    assert inst._waiting_for_key is True

    inst.handle_input(pygame.event.Event(
        pygame.KEYDOWN, key=pygame.K_ESCAPE, mod=0, unicode='',
    ))
    assert inst._waiting_for_key is False
