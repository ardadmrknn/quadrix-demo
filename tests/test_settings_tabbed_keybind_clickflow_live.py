"""Live integration test for keybind mouse click flow.

Stub yok — gerçek `pygame`, `settings_screen_tabbed`, `settings_manager`
yüklenir. Doğrulanan davranış:
- Slot rect ile reset rect birbirinden tamamen ayrı (no overlap).
- single_player slot click -> capture açılır, doğru slot.
- single_player label click -> capture açılır (varsayılan primary).
- pvp.player1 slot/label click -> capture açılır.
- Reset rect click -> capture açılmaz.
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
    return pygame, inst


def _scroll_to_item(inst, item_idx: int) -> int:
    sel_idx = inst._selectable_indices.index(item_idx)
    metrics = inst._layout_metrics()
    row_h = int(metrics['row_height'])
    section_h = int(metrics['section_height'])
    y = 0
    for j, it in enumerate(inst._tab_items):
        if j == item_idx:
            break
        y += section_h if it.get('type') == 'section' else row_h
    inst.scroll_offset = max(0, y - row_h)
    inst.selected = sel_idx
    inst.draw()
    return sel_idx


def _cancel_capture(pygame, inst):
    if inst._waiting_for_key:
        inst.handle_input(pygame.event.Event(
            pygame.KEYDOWN, key=pygame.K_ESCAPE, mod=0, unicode='',
        ))


def test_single_player_slot_and_reset_isolation(live_screen):
    pygame, inst = live_screen
    sp_idx = next(
        i for i, it in enumerate(inst._tab_items)
        if it.get('type') == 'keybind' and it.get('section') == 'single_player'
    )
    sel_idx = _scroll_to_item(inst, sp_idx)
    slot_rects = inst._keybind_slot_rects[sel_idx]
    reset_rect = inst._keybind_row_reset_rects[sp_idx]

    assert isinstance(slot_rects, dict)
    assert reset_rect is not None
    primary_rect = slot_rects['primary']
    secondary_rect = slot_rects['secondary']

    # Reset rect ve slot rect'leri çakışmamalı
    assert not reset_rect.colliderect(primary_rect)
    assert not reset_rect.colliderect(secondary_rect)

    # Primary slot içine tıklama
    inst._waiting_for_key = False
    inst._pending_keybind_item = None
    inst.handle_input(pygame.event.Event(
        pygame.MOUSEBUTTONDOWN, button=1,
        pos=(primary_rect.centerx, primary_rect.centery),
    ))
    assert inst._waiting_for_key is True
    assert inst._pending_keybind_slot == 'primary'
    _cancel_capture(pygame, inst)

    # Secondary slot tıklama
    inst.handle_input(pygame.event.Event(
        pygame.MOUSEBUTTONDOWN, button=1,
        pos=(secondary_rect.centerx, secondary_rect.centery),
    ))
    assert inst._waiting_for_key is True
    assert inst._pending_keybind_slot == 'secondary'
    _cancel_capture(pygame, inst)

    # Reset rect tıklama -> capture açılmaz
    inst.handle_input(pygame.event.Event(
        pygame.MOUSEBUTTONDOWN, button=1,
        pos=(reset_rect.centerx, reset_rect.centery),
    ))
    assert inst._waiting_for_key is False


def test_single_player_label_click_opens_capture(live_screen):
    pygame, inst = live_screen
    sp_idx = next(
        i for i, it in enumerate(inst._tab_items)
        if it.get('type') == 'keybind' and it.get('section') == 'single_player'
    )
    sel_idx = _scroll_to_item(inst, sp_idx)
    row_rect = inst.option_rects[sel_idx]

    inst._waiting_for_key = False
    inst._pending_keybind_item = None
    inst.handle_input(pygame.event.Event(
        pygame.MOUSEBUTTONDOWN, button=1,
        pos=(row_rect.x + 50, row_rect.centery),
    ))
    assert inst._waiting_for_key is True
    assert inst._pending_keybind_item is not None
    _cancel_capture(pygame, inst)


def test_pvp_player1_label_and_slot_click_opens_capture(live_screen):
    pygame, inst = live_screen
    pvp_idx = next(
        (i for i, it in enumerate(inst._tab_items)
         if it.get('type') == 'keybind' and it.get('section') == 'pvp.player1'),
        None,
    )
    if pvp_idx is None:
        pytest.skip('pvp.player1 keybind row yok')

    sel_idx = _scroll_to_item(inst, pvp_idx)
    row_rect = inst.option_rects[sel_idx]
    item = inst._tab_items[pvp_idx]

    # Label tarafına tıklama
    inst._waiting_for_key = False
    inst._pending_keybind_item = None
    inst.handle_input(pygame.event.Event(
        pygame.MOUSEBUTTONDOWN, button=1,
        pos=(row_rect.x + 50, row_rect.centery),
    ))
    assert inst._waiting_for_key is True
    assert inst._pending_keybind_item.get('action_key') == item.get('action_key')
    _cancel_capture(pygame, inst)

    # Slot içine tıklama
    slot_rects = inst._keybind_slot_rects[sel_idx]
    assert isinstance(slot_rects, dict)
    primary_rect = slot_rects['primary']
    inst.handle_input(pygame.event.Event(
        pygame.MOUSEBUTTONDOWN, button=1,
        pos=(primary_rect.centerx, primary_rect.centery),
    ))
    assert inst._waiting_for_key is True
    _cancel_capture(pygame, inst)


def test_pvp_player2_label_click_opens_capture(live_screen):
    pygame, inst = live_screen
    pvp_idx = next(
        (i for i, it in enumerate(inst._tab_items)
         if it.get('type') == 'keybind' and it.get('section') == 'pvp.player2'),
        None,
    )
    if pvp_idx is None:
        pytest.skip('pvp.player2 keybind row yok')

    sel_idx = _scroll_to_item(inst, pvp_idx)
    row_rect = inst.option_rects[sel_idx]
    item = inst._tab_items[pvp_idx]

    inst._waiting_for_key = False
    inst._pending_keybind_item = None
    inst.handle_input(pygame.event.Event(
        pygame.MOUSEBUTTONDOWN, button=1,
        pos=(row_rect.x + 50, row_rect.centery),
    ))
    assert inst._waiting_for_key is True
    assert inst._pending_keybind_item.get('action_key') == item.get('action_key')
    _cancel_capture(pygame, inst)



def test_mouse_motion_over_slot_updates_focus_slot(live_screen):
    """Mouse hareketi single_player keybind row'unda secondary slot'un
    üstüne gelince `_single_player_bind_slot` 'secondary'ye güncellenmeli;
    primary slot'a dönünce 'primary'ye geri dönmeli."""
    pygame, inst = live_screen
    sp_idx = next(
        i for i, it in enumerate(inst._tab_items)
        if it.get('type') == 'keybind' and it.get('section') == 'single_player'
    )
    sel_idx = _scroll_to_item(inst, sp_idx)
    slot_rects = inst._keybind_slot_rects[sel_idx]
    primary_rect = slot_rects['primary']
    secondary_rect = slot_rects['secondary']

    # Başlangıç: primary
    inst._single_player_bind_slot = 'primary'

    # Mouse'u secondary slot'un üstüne taşı -> focus secondary olmalı
    inst.handle_input(pygame.event.Event(
        pygame.MOUSEMOTION,
        pos=(secondary_rect.centerx, secondary_rect.centery),
        rel=(0, 0), buttons=(0, 0, 0),
    ))
    assert inst._single_player_bind_slot == 'secondary', \
        'mouse secondary üstündeyken slot focus secondary olmalı'

    # Mouse'u primary slot'un üstüne döndür -> focus primary
    inst.handle_input(pygame.event.Event(
        pygame.MOUSEMOTION,
        pos=(primary_rect.centerx, primary_rect.centery),
        rel=(0, 0), buttons=(0, 0, 0),
    ))
    assert inst._single_player_bind_slot == 'primary', \
        'mouse primary üstündeyken slot focus primary olmalı'


def test_mouse_motion_over_gamepad_slot_updates_gamepad_focus(live_screen):
    """Aynı davranış gamepad section'ı için de geçerli olmalı."""
    pygame, inst = live_screen
    gp_idx = next(
        (i for i, it in enumerate(inst._tab_items)
         if it.get('type') == 'keybind' and it.get('section') == 'gamepad.ingame'),
        None,
    )
    if gp_idx is None:
        pytest.skip('gamepad.ingame keybind row yok')

    sel_idx = _scroll_to_item(inst, gp_idx)
    slot_rects = inst._keybind_slot_rects[sel_idx]
    primary_rect = slot_rects['primary']
    secondary_rect = slot_rects['secondary']

    inst._gamepad_bind_slot = 'primary'
    inst.handle_input(pygame.event.Event(
        pygame.MOUSEMOTION,
        pos=(secondary_rect.centerx, secondary_rect.centery),
        rel=(0, 0), buttons=(0, 0, 0),
    ))
    assert inst._gamepad_bind_slot == 'secondary'

    inst.handle_input(pygame.event.Event(
        pygame.MOUSEMOTION,
        pos=(primary_rect.centerx, primary_rect.centery),
        rel=(0, 0), buttons=(0, 0, 0),
    ))
    assert inst._gamepad_bind_slot == 'primary'
