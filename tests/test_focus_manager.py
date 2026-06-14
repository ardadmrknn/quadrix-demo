"""Tests for FocusManager — Faz 2 shared navigation abstraction."""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
import pygame
pygame.init()

from focus_manager import FocusManager, FocusTarget, GamepadAction, key_to_action


def _rect(x, y, w=100, h=40):
    return pygame.Rect(x, y, w, h)


class TestNavigation:
    def test_nav_down_moves_to_nearest_below(self):
        fm = FocusManager()
        fm.register([
            FocusTarget(rect=_rect(50, 0), id='a'),
            FocusTarget(rect=_rect(50, 50), id='b'),
            FocusTarget(rect=_rect(50, 100), id='c'),
        ])
        assert fm.focused_id == 'a'
        fm.handle_action(GamepadAction.NAV_DOWN)
        assert fm.focused_id == 'b'
        fm.handle_action(GamepadAction.NAV_DOWN)
        assert fm.focused_id == 'c'

    def test_nav_up_moves_to_nearest_above(self):
        fm = FocusManager()
        fm.register([
            FocusTarget(rect=_rect(50, 0), id='a'),
            FocusTarget(rect=_rect(50, 50), id='b'),
        ])
        fm.focused_index = 1
        fm.handle_action(GamepadAction.NAV_UP)
        assert fm.focused_id == 'a'

    def test_nav_right_moves_horizontally(self):
        fm = FocusManager()
        fm.register([
            FocusTarget(rect=_rect(0, 50), id='left'),
            FocusTarget(rect=_rect(150, 50), id='right'),
        ])
        fm.handle_action(GamepadAction.NAV_RIGHT)
        assert fm.focused_id == 'right'

    def test_nav_does_not_move_when_no_target_in_direction(self):
        fm = FocusManager()
        fm.register([
            FocusTarget(rect=_rect(50, 50), id='only'),
        ])
        fm.handle_action(GamepadAction.NAV_DOWN)
        assert fm.focused_id == 'only'

    def test_wrap_mode_wraps_around(self):
        fm = FocusManager(wrap=True)
        fm.register([
            FocusTarget(rect=_rect(50, 0), id='a'),
            FocusTarget(rect=_rect(50, 50), id='b'),
            FocusTarget(rect=_rect(50, 100), id='c'),
        ])
        fm.focused_index = 2
        fm.handle_action(GamepadAction.NAV_DOWN)
        assert fm.focused_id == 'a'

    def test_no_wrap_stays_at_edge(self):
        fm = FocusManager(wrap=False)
        fm.register([
            FocusTarget(rect=_rect(50, 0), id='a'),
            FocusTarget(rect=_rect(50, 50), id='b'),
        ])
        fm.focused_index = 1
        fm.handle_action(GamepadAction.NAV_DOWN)
        assert fm.focused_id == 'b'


class TestConfirmBack:
    def test_confirm_calls_callback(self):
        results = []
        fm = FocusManager()
        fm.register([
            FocusTarget(rect=_rect(0, 0), id='btn', on_confirm=lambda: results.append('ok')),
        ])
        fm.handle_action(GamepadAction.CONFIRM)
        assert results == ['ok']

    def test_back_calls_callback(self):
        results = []
        fm = FocusManager()
        fm.register([
            FocusTarget(rect=_rect(0, 0), id='btn', on_back=lambda: results.append('back')),
        ])
        fm.handle_action(GamepadAction.BACK)
        assert results == ['back']

    def test_confirm_without_callback_returns_string(self):
        fm = FocusManager()
        fm.register([FocusTarget(rect=_rect(0, 0), id='btn')])
        result = fm.handle_action(GamepadAction.CONFIRM)
        assert result == 'confirm'


class TestKeyToAction:
    def test_return_maps_to_confirm(self):
        assert key_to_action(pygame.K_RETURN) == GamepadAction.CONFIRM

    def test_escape_maps_to_back(self):
        assert key_to_action(pygame.K_ESCAPE) == GamepadAction.BACK

    def test_arrows_map_to_nav(self):
        assert key_to_action(pygame.K_UP) == GamepadAction.NAV_UP
        assert key_to_action(pygame.K_DOWN) == GamepadAction.NAV_DOWN
        assert key_to_action(pygame.K_LEFT) == GamepadAction.NAV_LEFT
        assert key_to_action(pygame.K_RIGHT) == GamepadAction.NAV_RIGHT

    def test_brackets_map_to_tabs(self):
        assert key_to_action(pygame.K_RIGHTBRACKET) == GamepadAction.TAB_NEXT
        assert key_to_action(pygame.K_LEFTBRACKET) == GamepadAction.TAB_PREV

    def test_unknown_key_returns_none(self):
        assert key_to_action(pygame.K_z) is None


class TestHandleKey:
    def test_handle_key_dispatches_to_action(self):
        fm = FocusManager()
        fm.register([
            FocusTarget(rect=_rect(50, 0), id='a'),
            FocusTarget(rect=_rect(50, 50), id='b'),
        ])
        fm.handle_key(pygame.K_DOWN)
        assert fm.focused_id == 'b'

    def test_handle_key_unknown_does_nothing(self):
        fm = FocusManager()
        fm.register([FocusTarget(rect=_rect(50, 0), id='a')])
        result = fm.handle_key(pygame.K_z)
        assert result is None
        assert fm.focused_id == 'a'


class TestExplicitNeighbors:
    def test_explicit_neighbor_overrides_nearest(self):
        fm = FocusManager()
        fm.register([
            FocusTarget(rect=_rect(50, 0), id='a', neighbor_down='c'),
            FocusTarget(rect=_rect(50, 50), id='b'),
            FocusTarget(rect=_rect(50, 100), id='c'),
        ])
        fm.handle_action(GamepadAction.NAV_DOWN)
        # 'a' → explicit neighbor_down='c' (skip 'b')
        assert fm.focused_id == 'c'


class TestUpdateRects:
    def test_update_rects_changes_target_positions(self):
        fm = FocusManager()
        fm.register([
            FocusTarget(rect=_rect(0, 0), id='a'),
            FocusTarget(rect=_rect(0, 100), id='b'),
        ])
        fm.update_rects({'a': _rect(0, 200), 'b': _rect(0, 0)})
        # Now 'b' is above 'a'
        fm.focused_index = 0  # 'a' at y=200
        fm.handle_action(GamepadAction.NAV_UP)
        assert fm.focused_id == 'b'
