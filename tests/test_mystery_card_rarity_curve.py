"""Tests for the level-driven rarity bucket sampling in MysteryCardManager.

These verify the new mimari:
- rarity bucket weights interpolate smoothly between anchors (no hard breakpoints)
- legendary share scales monotonically with card_level
- card adedi (kart sayısı) per rarity does NOT skew probabilities
- _group_id varyantları aynı seçim setinde tekrar etmez
- card_mode_debug full-catalog yolunu bozmaz
- bos bucket'lar kalan ağırlıkları renormalize eder
- persistent/single_use filtreleri korunur
"""

from __future__ import annotations

import os
import random
import sys
from collections import Counter
from types import SimpleNamespace

ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
SRC_DIR = os.path.join(ROOT_DIR, 'src')
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from game_modes_extra import MysteryCardManager


def _make_manager(card_level: int = 1, *, debug: bool = False):
    mgr = MysteryCardManager.__new__(MysteryCardManager)
    mgr.catalog = []
    mgr.force_piece_queue = []
    mgr.pending_choices = []
    mgr.active_cards = []
    mgr.used_card_ids = set()
    mgr._debug_lines_progress = 0
    mgr.card_xp = 0
    mgr.card_level = int(card_level)
    mgr.card_xp_to_next = MysteryCardManager._compute_xp_to_next(card_level)
    mgr.progress = 0
    mgr.threshold = mgr.card_xp_to_next
    mgr.mode = SimpleNamespace(
        pending_level_ups=0,
        last_enqueued_level=0,
        settings_manager=SimpleNamespace(get=lambda _key, default=False: debug if _key == 'card_mode_debug' else default),
    )
    return mgr


def _stub_card(card_id: str, rarity: str, *, group: str | None = None,
               persistent: bool = False, single_use: bool = False) -> dict:
    return {
        'id': card_id,
        'rarity': rarity,
        'title': card_id,
        'description': '',
        'tag': rarity.title(),
        'icon': '?',
        'base': 1,
        'weight': 50,  # legacy field; new sampler ignores it
        '_group_id': group,
        'persistent': persistent,
        'single_use': single_use,
    }


# ---------------------------------------------------------------------------
# Anchor interpolation
# ---------------------------------------------------------------------------

def test_rarity_weights_match_anchor_levels_exactly():
    anchors = MysteryCardManager.RARITY_WEIGHT_ANCHORS
    for level, expected in anchors.items():
        weights = MysteryCardManager._rarity_weights_for_level(level)
        for rarity, weight in expected.items():
            assert weights[rarity] == weight, f"level {level} rarity {rarity}"


def test_rarity_weights_interpolate_between_anchors():
    """Level 3 should sit between anchor 1 and anchor 5."""
    anchors = MysteryCardManager.RARITY_WEIGHT_ANCHORS
    weights = MysteryCardManager._rarity_weights_for_level(3)
    # t = (3 - 1) / (5 - 1) = 0.5
    expected_legendary = anchors[1]['legendary'] * 0.5 + anchors[5]['legendary'] * 0.5
    expected_common = anchors[1]['common'] * 0.5 + anchors[5]['common'] * 0.5
    assert abs(weights['legendary'] - expected_legendary) < 1e-9
    assert abs(weights['common'] - expected_common) < 1e-9


def test_rarity_weights_clamp_below_first_and_above_last_anchor():
    anchors = MysteryCardManager.RARITY_WEIGHT_ANCHORS
    first_key = min(anchors)
    last_key = max(anchors)
    assert MysteryCardManager._rarity_weights_for_level(0) == anchors[first_key]
    assert MysteryCardManager._rarity_weights_for_level(-5) == anchors[first_key]
    assert MysteryCardManager._rarity_weights_for_level(last_key + 5) == anchors[last_key]
    assert MysteryCardManager._rarity_weights_for_level(999) == anchors[last_key]


def test_rarity_weights_legendary_share_grows_monotonically():
    legendary_history = []
    for lvl in (1, 3, 5, 8, 10, 15, 20, 30):
        w = MysteryCardManager._rarity_weights_for_level(lvl)
        legendary_history.append(w['legendary'])
    for prev, cur in zip(legendary_history, legendary_history[1:]):
        assert cur >= prev, f"legendary monotonik artmıyor: {legendary_history}"
    assert legendary_history[-1] > legendary_history[0]


# ---------------------------------------------------------------------------
# Sampling: bucket-first behavior
# ---------------------------------------------------------------------------

def _build_balanced_catalog():
    """Her rarity için bir kart; adetler eşit olduğunda olasılıklar
    doğrudan bucket ağırlıklarını yansıtmalıdır."""
    return [
        _stub_card('c1', 'common'),
        _stub_card('u1', 'uncommon'),
        _stub_card('r1', 'rare'),
        _stub_card('e1', 'epic'),
        _stub_card('l1', 'legendary'),
    ]


def _build_unbalanced_catalog():
    """common = 1 kart, legendary = 10 kart. Eski ağırlık tabanlı sistemde
    legendary olasılığı yapay olarak şişerdi; yeni sistemde bucket'tan
    seçildiği için tek-tek kart adedi olasılığı **bozmamalı**."""
    cards = [_stub_card('c1', 'common')]
    cards += [_stub_card(f'u{i}', 'uncommon') for i in range(2)]
    cards += [_stub_card(f'r{i}', 'rare') for i in range(3)]
    cards += [_stub_card(f'e{i}', 'epic') for i in range(4)]
    cards += [_stub_card(f'l{i}', 'legendary') for i in range(10)]
    return cards


def test_sampling_bucket_share_matches_anchor_at_level_1():
    random.seed(2026)
    mgr = _make_manager(card_level=1)
    catalog = _build_balanced_catalog()
    counts = Counter()
    iterations = 5000
    for _ in range(iterations):
        picked = mgr._weighted_sample(catalog, 1)
        assert len(picked) == 1
        counts[mgr._normalize_rarity(picked[0]['rarity'])] += 1
    # Level 1 anchors: common 70, uncommon 22, rare 7, epic 0.9, legendary 0.1
    legendary_share = counts['legendary'] / iterations
    epic_share = counts['epic'] / iterations
    common_share = counts['common'] / iterations
    assert legendary_share < 0.01, f"legendary share too high at lvl1: {legendary_share}"
    assert epic_share < 0.025, f"epic share too high at lvl1: {epic_share}"
    assert common_share > 0.6, f"common share too low at lvl1: {common_share}"


def test_sampling_legendary_share_grows_at_level_20():
    random.seed(2026)
    mgr = _make_manager(card_level=20)
    catalog = _build_balanced_catalog()
    counts = Counter()
    iterations = 5000
    for _ in range(iterations):
        picked = mgr._weighted_sample(catalog, 1)
        counts[mgr._normalize_rarity(picked[0]['rarity'])] += 1
    legendary_share = counts['legendary'] / iterations
    epic_share = counts['epic'] / iterations
    # Anchor 20: legendary 10%, epic 13%
    assert legendary_share > 0.05, f"legendary share too low at lvl20: {legendary_share}"
    assert epic_share > 0.08, f"epic share too low at lvl20: {epic_share}"


def test_sampling_rarity_share_independent_of_per_bucket_card_count():
    """Aynı bucket içinde 1 kart vs 10 kart olması bucket'ın çıkma
    olasılığını DEĞİŞTİRMEMELİ. (Eski weight-tabanlı sistemde bu kural
    sağlanmıyordu.)"""
    random.seed(2026)
    mgr = _make_manager(card_level=20)
    catalog = _build_unbalanced_catalog()  # legendary 10 kart, common 1 kart
    counts = Counter()
    iterations = 5000
    for _ in range(iterations):
        picked = mgr._weighted_sample(catalog, 1)
        counts[mgr._normalize_rarity(picked[0]['rarity'])] += 1
    legendary_share = counts['legendary'] / iterations
    common_share = counts['common'] / iterations
    # Anchor 20: legendary 10%, common 30%. Bucket içi adetler 10 vs 1
    # olduğu halde olasılık anchor'a yakın kalmalı.
    assert 0.06 < legendary_share < 0.16, f"legendary skew detected: {legendary_share}"
    assert 0.20 < common_share < 0.40, f"common skew detected: {common_share}"


def test_featured_common_offer_weight_biases_demo_showcase_cards_early():
    random.seed(2026)
    mgr = _make_manager(card_level=1)
    featured = _stub_card('mirror_hold', 'common')
    featured['offer_weight'] = 2.0
    featured['offer_weight_until_level'] = 8
    catalog = [
        featured,
        _stub_card('mini_bomb', 'common'),
        _stub_card('row_shuffle', 'common'),
    ]
    counts = Counter()
    iterations = 4000
    for _ in range(iterations):
        picked = mgr._weighted_sample(catalog, 1)
        counts[picked[0]['id']] += 1
    assert counts['mirror_hold'] / iterations > 0.45


def test_featured_common_offer_weight_expires_after_showcase_window():
    random.seed(2026)
    mgr = _make_manager(card_level=20)
    featured = _stub_card('mirror_hold', 'common')
    featured['offer_weight'] = 2.0
    featured['offer_weight_until_level'] = 8
    catalog = [
        featured,
        _stub_card('mini_bomb', 'common'),
        _stub_card('row_shuffle', 'common'),
    ]
    counts = Counter()
    iterations = 4000
    for _ in range(iterations):
        picked = mgr._weighted_sample(catalog, 1)
        counts[picked[0]['id']] += 1
    share = counts['mirror_hold'] / iterations
    assert 0.25 < share < 0.42


# ---------------------------------------------------------------------------
# Constraints
# ---------------------------------------------------------------------------

def test_group_id_variants_dont_repeat_in_one_selection():
    random.seed(7)
    mgr = _make_manager(card_level=10)
    catalog = [
        _stub_card('speed_burst_rare',      'rare',      group='speed_burst'),
        _stub_card('speed_burst_epic',      'epic',      group='speed_burst'),
        _stub_card('speed_burst_legendary', 'legendary', group='speed_burst'),
        _stub_card('c1', 'common'),
        _stub_card('u1', 'uncommon'),
    ]
    for _ in range(200):
        picked = mgr._weighted_sample(catalog, 3)
        groups = [c.get('_group_id') for c in picked if c.get('_group_id')]
        assert len(groups) == len(set(groups)), f"_group_id duplicate: {picked}"


def test_card_mode_debug_returns_full_catalog():
    """Debug açıkken prepare_selection tüm kataloğu (rarity sample bypass)
    göstermeli; bucket sampling atlanmalı."""
    random.seed(0)
    mgr = _make_manager(card_level=5, debug=True)
    mgr.catalog = [
        _stub_card('c1', 'common'),
        _stub_card('u1', 'uncommon'),
        _stub_card('r1', 'rare'),
        _stub_card('e1', 'epic'),
        _stub_card('l1', 'legendary'),
    ]
    choices = mgr.prepare_selection()
    chosen_ids = {c['id'] for c in choices}
    assert chosen_ids == {'c1', 'u1', 'r1', 'e1', 'l1'}


def test_card_mode_debug_still_filters_used_and_active_cards():
    random.seed(0)
    mgr = _make_manager(card_level=5, debug=True)
    persistent = _stub_card('perk_keep', 'rare', persistent=True)
    used_variant = _stub_card('hold_destroyer_rare', 'epic', group='hold_destroyer', single_use=True)
    fresh = _stub_card('fresh', 'common')
    mgr.catalog = [persistent, used_variant, fresh]
    mgr.active_cards = [{'id': 'perk_keep'}]
    mgr.used_card_ids.add('hold_destroyer')

    choices = mgr.prepare_selection()

    assert [c['id'] for c in choices] == ['fresh']


def test_persistent_already_active_card_filtered_out():
    random.seed(0)
    mgr = _make_manager(card_level=10)
    common = _stub_card('c1', 'common', persistent=True)
    rare = _stub_card('r1', 'rare')
    mgr.catalog = [common, rare]
    mgr.active_cards = [{'id': 'c1'}]
    choices = mgr.prepare_selection()
    chosen_ids = {c['id'] for c in choices}
    assert 'c1' not in chosen_ids
    assert 'r1' in chosen_ids


def test_single_use_card_after_use_excluded_from_pool():
    random.seed(0)
    mgr = _make_manager(card_level=10)
    used = _stub_card('e1', 'epic', single_use=True)
    fresh = _stub_card('r1', 'rare')
    mgr.catalog = [used, fresh]
    mgr.used_card_ids.add('e1')
    choices = mgr.prepare_selection()
    chosen_ids = {c['id'] for c in choices}
    assert 'e1' not in chosen_ids
    assert 'r1' in chosen_ids


def test_empty_bucket_renormalizes_remaining_weights():
    """Tüm legendary kartlar kullanılınca: bucket sampling legendary'yi
    'aktif' saymadan diğer rarity'lere düşmeli."""
    random.seed(2026)
    mgr = _make_manager(card_level=20)
    catalog = [
        _stub_card('c1', 'common'),
        _stub_card('u1', 'uncommon'),
        _stub_card('r1', 'rare'),
        _stub_card('e1', 'epic'),
        # legendary kart yok
    ]
    counts = Counter()
    iterations = 1000
    for _ in range(iterations):
        picked = mgr._weighted_sample(catalog, 1)
        counts[mgr._normalize_rarity(picked[0]['rarity'])] += 1
    assert counts['legendary'] == 0
    # Diğerleri toplam = iterations olmalı
    assert counts['common'] + counts['uncommon'] + counts['rare'] + counts['epic'] == iterations


def test_sampler_returns_count_when_pool_smaller_than_count():
    random.seed(0)
    mgr = _make_manager(card_level=3)
    catalog = [_stub_card('c1', 'common'), _stub_card('r1', 'rare')]
    picked = mgr._weighted_sample(catalog, 5)
    assert len(picked) == 2
    ids = {c['id'] for c in picked}
    assert ids == {'c1', 'r1'}


def test_sampler_handles_empty_input():
    mgr = _make_manager(card_level=10)
    assert mgr._weighted_sample([], 3) == []
    assert mgr._weighted_sample([_stub_card('c1', 'common')], 0) == []


def test_unknown_rarity_falls_back_to_common_bucket():
    random.seed(0)
    mgr = _make_manager(card_level=20)
    catalog = [_stub_card('mystery', 'mythic')]  # bilinmeyen rarity
    picked = mgr._weighted_sample(catalog, 1)
    assert len(picked) == 1
    assert picked[0]['id'] == 'mystery'
