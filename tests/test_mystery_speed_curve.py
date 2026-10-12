from __future__ import annotations

import sys
from types import SimpleNamespace

import pygame
import pytest

_platform_utils = sys.modules.get('platform_utils')
if _platform_utils is not None and not hasattr(_platform_utils, 'get_display_scale_factor'):
    _platform_utils.get_display_scale_factor = lambda: 1.0


def _import_mystery_symbols():
    if not hasattr(pygame, 'K_c'):
        pytest.skip('pygame stub environment: MysteryMode import skipped')
    import game_modes_extra as extra

    return extra, extra.MysteryMode


def _make_mode(MysteryMode, *, board_level: int, card_level: int = 1, card_xp: int = 0):
    mode = MysteryMode.__new__(MysteryMode)
    mode.board = SimpleNamespace(level=int(board_level))
    mode.card_manager = SimpleNamespace(card_level=int(card_level), card_xp=int(card_xp))
    mode.speed_effect_timer = 0.0
    mode.speed_effect_multiplier = 1.0
    mode._speed_burst_speed_mult = 1.0
    return mode


@pytest.mark.parametrize(
    ('level', 'expected_ms'),
    [
        (1, 850),
        (5, 700),
        (10, 500),
        (15, 300),
        (20, 150),
        (30, 125),
        (31, 124),
        (55, 100),
    ],
)
def test_mystery_speed_curve_anchor_targets(level, expected_ms):
    extra, MysteryMode = _import_mystery_symbols()
    mode = _make_mode(MysteryMode, board_level=level)

    assert extra.get_mystery_level_fall_speed_ms(level) == expected_ms
    assert mode.get_initial_speed() == expected_ms
    assert mode.get_current_speed() == expected_ms


@pytest.mark.parametrize(
    ('level', 'expected_ms'),
    [
        (3, 775),
        (12, 420),
        (25, 138),
    ],
)
def test_mystery_speed_curve_interpolates_between_anchors(level, expected_ms):
    extra, _ = _import_mystery_symbols()

    assert extra.get_mystery_level_fall_speed_ms(level) == expected_ms


def test_mystery_speed_effects_apply_on_top_of_base_curve_in_order():
    _, MysteryMode = _import_mystery_symbols()
    mode = _make_mode(MysteryMode, board_level=10)
    base_speed = mode.get_current_speed()

    mode.speed_effect_timer = 5.0
    mode.speed_effect_multiplier = 0.5
    slowed_speed = mode.get_current_speed()

    mode.speed_effect_timer = 0.0
    mode.speed_effect_multiplier = 1.0
    mode._speed_burst_speed_mult = 1.6
    burst_speed = mode.get_current_speed()

    mode.speed_effect_timer = 5.0
    mode.speed_effect_multiplier = 0.5
    combined_speed = mode.get_current_speed()

    assert base_speed == 500
    assert slowed_speed > base_speed
    assert burst_speed < base_speed
    assert combined_speed == int(int(base_speed / 0.5) / 1.6)


def test_mystery_speed_uses_board_level_not_card_progression():
    _, MysteryMode = _import_mystery_symbols()
    mode = _make_mode(MysteryMode, board_level=10, card_level=99, card_xp=9999)

    assert mode.get_current_speed() == 500

    mode.card_manager.card_level = 250
    mode.card_manager.card_xp = 100000
    assert mode.get_current_speed() == 500

    mode.board.level = 15
    assert mode.get_current_speed() == 300

def test_speed_burst_effect_floor_allows_faster_than_base_floor():
    """speed_burst çarpanı temel eğri tabanının (100 ms) altına inebilir;
    etki tabanı 16 ms'dir (v2 paritesi).

    Eski davranış `max(MYSTERY_LEVEL_SPEED_MIN_MS, ...)` temel eğri
    tabanına sıkıştırıyordu: L55+ seviyelerde taban zaten 100 ms olduğundan
    kartın hız vaadi fiilen çalışmıyordu (yalnız satır-çarpanı etkisi
    kalıyordu)."""
    extra, MysteryMode = _import_mystery_symbols()
    mode = _make_mode(MysteryMode, board_level=60)

    # Demo taban eğrisi L55+ seviyelerde 100 ms yatayındadır.
    base_speed = mode.get_current_speed()
    assert base_speed == 100

    # Hız Patlaması (legendary 1.75x): 100 / 1.75 = 57 ms.
    mode._speed_burst_speed_mult = 1.75
    assert mode.get_current_speed() == 57

    # Aşırı çarpan bile 16 ms etki tabanının altına inmez (kare güvenliği).
    mode._speed_burst_speed_mult = 100.0
    assert mode.get_current_speed() == 16
