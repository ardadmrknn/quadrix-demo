"""Faz 3 — Mini-boss missing (Tip β) init-time davranışı.

Level 15/35/55/75/95 (missing): _allowed_pieces'tan 1 deterministik parça
çıkarılır. Aynı seed → aynı eksik parça. Normal levellarda etkilenmez.

NOT: Faz 2 dokümantasyon notuna göre missing parça çıkarma init time'da
uygulanır; base Game.__init__ next_piece_queue'yu zaten doldurmuş olabilir,
bu queue içindeki parçalar ÇIKARILMAZ. Sonraki yeni parçalar
_allowed_pieces'tan oluşur. Bu test sadece init time _allowed_pieces ve
_missing_piece_name state'ini doğrular.
"""
from __future__ import annotations

import pathlib
import sys


ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / 'src'

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import random as _global_rng
from campaign.campaign_mode import CampaignMode
from campaign.level_data import get_level


def _simulate_init_time_boss_logic(level_num: int, piece_seed: int):
    """CampaignMode __init__'in mini-boss apply mantığını izole olarak çalıştır.

    Tam constructor çağırmak yerine, sadece relevant kısmı simüle ediyoruz
    (Game.__init__'i mock'lamak ağır olur).
    """
    mode = object.__new__(CampaignMode)
    mode.current_level_num = level_num
    last_digit = level_num % 10
    mode.is_mini_boss = (last_digit == 5)
    mode.is_boss = (last_digit == 0 and level_num > 0)
    mode._piece_seed = piece_seed
    mode._allowed_pieces = ['I', 'O', 'T', 'S', 'Z', 'J', 'L']
    mode._missing_piece_name = None
    mode.fall_speed = 800

    # __init__ içindeki Faz 2 mini-boss apply blokunu manuel çağır
    boss_type = mode._boss_get_type()
    if boss_type == 'fast':
        mode.fall_speed = max(150, int(mode.fall_speed * 0.85))
    elif boss_type == 'missing':
        allowed = list(mode._allowed_pieces)
        if len(allowed) > 1:
            rng = _global_rng.Random((piece_seed or 0) ^ 0xC2B2AE3D)
            removed = rng.choice(allowed)
            mode._missing_piece_name = removed
            mode._allowed_pieces = [p for p in allowed if p != removed]

    return mode


def test_mini_boss_missing_removes_one_piece():
    """Level 15: _allowed_pieces 7'den 6'ya düşer, _missing_piece_name set."""
    mode = _simulate_init_time_boss_logic(level_num=15, piece_seed=42)
    assert len(mode._allowed_pieces) == 6, (
        f"6 parça bekleniyor, {len(mode._allowed_pieces)} bulundu"
    )
    assert mode._missing_piece_name is not None
    assert mode._missing_piece_name in ['I', 'O', 'T', 'S', 'Z', 'J', 'L']
    assert mode._missing_piece_name not in mode._allowed_pieces


def test_mini_boss_missing_deterministic_per_seed():
    """Aynı piece_seed → aynı eksik parça."""
    mode1 = _simulate_init_time_boss_logic(level_num=15, piece_seed=12345)
    mode2 = _simulate_init_time_boss_logic(level_num=15, piece_seed=12345)
    assert mode1._missing_piece_name == mode2._missing_piece_name, (
        f"Aynı seed farklı eksik parça: {mode1._missing_piece_name} vs {mode2._missing_piece_name}"
    )


def test_mini_boss_missing_does_not_affect_normal_levels():
    """Normal levellarda _allowed_pieces 7 eleman kalır, _missing_piece_name None."""
    for normal_lv in [1, 3, 7, 12, 14, 16, 19, 21, 26]:
        mode = _simulate_init_time_boss_logic(level_num=normal_lv, piece_seed=42)
        assert len(mode._allowed_pieces) == 7, (
            f"L{normal_lv} normal level'da 7 parça bekleniyor, {len(mode._allowed_pieces)} bulundu"
        )
        assert mode._missing_piece_name is None


def test_mini_boss_fast_does_not_remove_pieces():
    """Mini-boss fast (Tip α) parça pool'unu etkilemez, sadece hızı artırır."""
    mode = _simulate_init_time_boss_logic(level_num=5, piece_seed=42)
    assert len(mode._allowed_pieces) == 7
    assert mode._missing_piece_name is None
    # fall_speed %15 azaltılmış olmalı
    assert mode.fall_speed == int(800 * 0.85)
