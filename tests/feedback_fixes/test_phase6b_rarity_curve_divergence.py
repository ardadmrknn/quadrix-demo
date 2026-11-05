"""Faz 6b / I-50 (a) — Demo nadirlik eğrisi BİLİNÇLİ olarak v2'den farklıdır.

Kılavuz F6b.5(a) kararı: iki deponun Mystery eğrisi farklıdır ve bu fark
**korunur**; v2'nin L150'ye uzanan eğrisi demo'ya TAŞINMAZ. Gerekçe:
`DEMO_MYSTERY_SCORE_CAP = 1000000` uzun koşuyu zaten kesiyor, dolayısıyla
L150+ davranışı demo için erişilemez bölgedir.

Bu dosya koda dokunmaz; demo'nun MEVCUT değerlerini kilitler. Amaç iki yönlü:
  1. Demo eğrisinin farkı belgelenir (executable doküman).
  2. v2 eğrisinin yanlışlıkla demo'ya kopyalanması test kırmızısı olarak
     yakalanır — sessiz sürüklenme olmaz.
"""

import os
import sys

import pytest

SRC_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

pytestmark = pytest.mark.quadrix_feedback

from game_modes_extra import MysteryCardManager  # noqa: E402


# Demo'nun kilitli degerleri (2026-11-05 itibariyla). v2'den FARKLI olmasi
# bilinclidir; bkz. F6b.5(a).
DEMO_ANCHORS = {
    1:  {'common': 70.0, 'uncommon': 25.0, 'rare':  5.0, 'epic':  0.0, 'legendary': 0.0},
    5:  {'common': 62.5, 'uncommon': 25.0, 'rare': 10.0, 'epic':  2.5, 'legendary': 0.0},
    10: {'common': 55.0, 'uncommon': 25.0, 'rare': 15.0, 'epic':  5.0, 'legendary': 0.0},
    13: {'common': 45.0, 'uncommon': 25.0, 'rare': 18.0, 'epic': 10.0, 'legendary': 2.0},
    17: {'common': 35.0, 'uncommon': 25.0, 'rare': 20.0, 'epic': 13.0, 'legendary': 7.0},
    20: {'common': 30.0, 'uncommon': 25.0, 'rare': 20.0, 'epic': 15.0, 'legendary': 10.0},
}

RARITIES = ('common', 'uncommon', 'rare', 'epic', 'legendary')


@pytest.mark.quadrix_phase6b
def test_demo_anchors_match_locked_values():
    anchors = MysteryCardManager.RARITY_WEIGHT_ANCHORS
    assert set(anchors) == set(DEMO_ANCHORS), 'demo ankraj kumesi degismis'
    for level, expected in DEMO_ANCHORS.items():
        assert anchors[level] == expected, f'L{level} demo ankraji degismis'


@pytest.mark.quadrix_phase6b
def test_demo_anchor_weights_sum_to_one_hundred():
    for level, weights in MysteryCardManager.RARITY_WEIGHT_ANCHORS.items():
        total = sum(weights.values())
        assert abs(total - 100.0) < 1e-6, f'L{level} agirlik toplami {total}'


@pytest.mark.quadrix_phase6b
def test_demo_curve_plateaus_after_last_anchor():
    """Demo eğrisi L20'de durur; v2'nin L150 uzatmasi buraya tasinmadi."""
    w20 = MysteryCardManager._rarity_weights_for_level(20)
    for far in (30, 55, 150, 1000):
        assert MysteryCardManager._rarity_weights_for_level(far) == w20


@pytest.mark.quadrix_phase6b
def test_demo_does_not_carry_v2_late_anchors():
    """v2'ye ozgu gec-oyun ankrajlari demo'da OLMAMALI (bilincli sapma)."""
    anchors = MysteryCardManager.RARITY_WEIGHT_ANCHORS
    for level in (55, 75, 100, 125, 150):
        assert level not in anchors, (
            f'L{level} ankraji demo\'ya sizmis — F6b.5(a) bu farki KORUMAYI '
            f'sart kosuyor'
        )


@pytest.mark.quadrix_phase6b
def test_demo_score_cap_justifies_the_shorter_curve():
    """Eğri kısaltmasının gerekçesi kodda hâlâ geçerli olmalı."""
    import demo_config

    assert hasattr(demo_config, 'DEMO_MYSTERY_SCORE_CAP')
    assert demo_config.DEMO_MYSTERY_SCORE_CAP == 1000000