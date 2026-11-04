from __future__ import annotations

import pathlib
import sys

import pytest

ROOT_DIR = pathlib.Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from localization import SUPPORTED_LANGUAGES, TRANSLATIONS


pytestmark = [pytest.mark.quadrix_feedback, pytest.mark.quadrix_phase6]


def test_phase6_added_keys_have_all_supported_languages_and_matching_placeholders():
    for key in ("card_type_timed", "card_type_timed_dynamic"):
        entry = TRANSLATIONS[key]
        assert set(SUPPORTED_LANGUAGES).issubset(entry)
        for lang in SUPPORTED_LANGUAGES:
            assert entry[lang]
        if key.endswith("dynamic"):
            assert all("{value}" in entry[lang] for lang in SUPPORTED_LANGUAGES)
