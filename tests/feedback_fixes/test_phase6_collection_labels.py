from __future__ import annotations

import pathlib
import sys

import pytest

ROOT_DIR = pathlib.Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from localization import t, set_language


pytestmark = [pytest.mark.quadrix_feedback, pytest.mark.quadrix_phase6]


def test_collection_default_and_equipped_labels_are_distinct():
    set_language("tr")
    assert t("store_default_label") == "Varsayılan"
    assert t("store_owned_equipped") == "Takılı"
    assert t("store_default_label") != t("store_owned_equipped")
