from __future__ import annotations

import pathlib
import sys

import pytest

ROOT_DIR = pathlib.Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from campaign.level_data import get_level
from campaign.objectives import MultiClearObjective, create_objective


pytestmark = [pytest.mark.quadrix_feedback, pytest.mark.quadrix_phase6]
LANGS = ("tr", "en", "de", "fr", "es", "it", "pt", "ru", "ja", "zh", "ko")


def test_multi_clear_uses_canonical_localization_without_raw_template_tokens():
    for required in (2, 3, 4, 5):
        objective = MultiClearObjective(required)
        for lang in LANGS:
            text = objective.get_description(lang)
            assert text
            assert "{" not in text and "}" not in text, (required, lang, text)


def test_all_campaign_objective_descriptions_are_placeholder_free():
    for level_number in range(1, 101):
        level = get_level(level_number)
        assert level is not None
        for definition in level.objectives:
            objective = create_objective(definition.get("type", "clear_lines"), **definition)
            for lang in LANGS:
                text = objective.get_description(lang)
                assert "{" not in text and "}" not in text, (
                    level_number,
                    definition,
                    lang,
                    text,
                )
