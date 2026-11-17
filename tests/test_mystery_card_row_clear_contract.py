"""Regression contracts for row-cleaning card tiers and descriptions."""
from __future__ import annotations

import os
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "src"))

import game_modes_extra as extra
from game_modes_extra import MysteryMode, get_card_description
from localization import TRANSLATIONS


def test_clear_rows_family_has_exact_non_overlapping_tier_values():
    tiers = extra.CARD_UPGRADE_FAMILIES["clear_rows"]
    assert [(tier["rarity"], tier["value_range"]) for tier in tiers] == [
        ("uncommon", (2, 2)),
        ("rare", (3, 3)),
        ("epic", (4, 4)),
        ("legendary", (5, 5)),
    ]
    previous_high = 0
    for tier in tiers:
        low, high = tier["value_range"]
        assert low <= high
        assert low > previous_high
        previous_high = high


def test_clear_rows_catalog_values_are_sourced_from_family_metadata():
    manager = extra.MysteryCardManager.__new__(extra.MysteryCardManager)
    catalog = {str(card.get("id")): card for card in manager._build_catalog()}
    for tier in extra.CARD_UPGRADE_FAMILIES["clear_rows"]:
        card = catalog[tier["id"]]
        assert card["value_range"] == tier["value_range"]
        assert card["base"] == tier["value_range"][0]
        assert card["_group_id"] == "clear_rows"


def test_bomb_master_tier_value_is_runtime_charge_target():
    mode = MysteryMode.__new__(MysteryMode)
    mode.effects_enabled = False
    mode.sound_enabled = False
    mode.card_manager = SimpleNamespace(active_slots=[], used_card_ids=set())
    mode._local_bomb_master_charges = 0
    mode._set_localized_card_message = lambda *_args, **_kwargs: ""
    mode._remember_effect_visual = lambda *_args, **_kwargs: None
    mode._sync_active_cards = lambda: None
    mode._spawn_card_particles = lambda *_args, **_kwargs: None

    mode._apply_card_effect({
        "id": "bomb_master_leg",
        "_group_id": "bomb_master",
        "value": 5,
        "color": (255, 90, 60),
    })

    assert mode.bomb_master_charges == 5
    assert [tier["value_range"][0] for tier in extra.CARD_UPGRADE_FAMILIES["bomb_master"]] == [3, 4, 5]


@pytest.mark.parametrize("language, required", [
    ("tr", ("Kademeye", "kullan", "temas")),
    ("en", ("tier", "uses", "touch")),
])
def test_bomb_master_description_explains_tiered_uses(language, required):
    text = TRANSLATIONS["card_bomb_master_desc"][language]
    assert all(fragment.lower() in text.lower() for fragment in required)


def test_color_cleanse_description_is_bounded_by_available_colors():
    assert "{value}" in TRANSLATIONS["card_color_cleanse_desc"]["tr"]
    assert "en fazla" in TRANSLATIONS["card_color_cleanse_desc"]["tr"].lower()
    assert "mevcut" in TRANSLATIONS["card_color_cleanse_desc"]["tr"].lower()
    assert "{value}" in TRANSLATIONS["card_color_cleanse_desc"]["en"]
    assert "up to" in TRANSLATIONS["card_color_cleanse_desc"]["en"].lower()
    assert "available" in TRANSLATIONS["card_color_cleanse_desc"]["en"].lower()


def test_guide_descriptions_match_clear_rows_and_nova_tiers():
    clear_tr = TRANSLATIONS["guide_card_clear_rows_desc"]["tr"]
    clear_en = TRANSLATIONS["guide_card_clear_rows_desc"]["en"]
    assert "1-3" not in clear_tr and "1-3" not in clear_en
    for value in ("2", "3", "4", "5"):
        assert value in clear_tr
        assert value in clear_en

    nova_tr = TRANSLATIONS["guide_card_nova_desc"]["tr"]
    nova_en = TRANSLATIONS["guide_card_nova_desc"]["en"]
    assert "2-4" not in nova_tr and "2-4" not in nova_en
    for area in ("3x3", "4x4", "5x5"):
        assert area in nova_tr
        assert area in nova_en


def test_catalog_fallback_descriptions_name_indirect_line_clear_behavior():
    manager = extra.MysteryCardManager.__new__(extra.MysteryCardManager)
    catalog = {str(card.get("id")): card for card in manager._build_catalog()}
    assert "dolu satır" in catalog["block_magnet"]["description"].lower()
    assert "dolu satır" in catalog["row_shuffle"]["description"].lower()
    nova_description = catalog["nova_burst"]["description"].lower()
    assert "tam satır" in nova_description or "dolu satır" in nova_description
    assert "doğrudan" in catalog["sniper_shot"]["description"].lower()
    assert "en fazla" in catalog["color_cleanse"]["description"].lower()
    assert "mevcut" in catalog["color_cleanse"]["description"].lower()


def test_color_cleanse_never_selects_more_colors_than_exist(monkeypatch):
    from board import Board

    mode = MysteryMode.__new__(MysteryMode)
    mode.board = Board(width=4, height=6)
    mode.sound_enabled = False
    mode._set_localized_card_message = lambda *_args, **_kwargs: ""
    red = (255, 0, 0)
    mode.board.grid[5][0] = red
    mode.board.occupancy[5][0] = True
    choices = []
    monkeypatch.setattr(extra.random, "choice", lambda values: choices.append(tuple(values)) or red)

    mode._apply_color_cleanse(colors_to_clear=3)

    assert len(choices) == 1
    assert mode.board.occupancy[5][0] is False
