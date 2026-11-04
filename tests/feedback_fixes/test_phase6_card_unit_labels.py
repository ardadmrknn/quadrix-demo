from __future__ import annotations

import pathlib
import sys

import pytest

ROOT_DIR = pathlib.Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from game_modes_extra import _get_card_type_label
from localization import set_language


pytestmark = [pytest.mark.quadrix_feedback, pytest.mark.quadrix_phase6]


def test_timed_buff_uses_seconds_unit():
    set_language("tr")
    assert _get_card_type_label({"timed_buff": True, "value": 25}) == "25 sn"


def test_limited_card_keeps_usage_unit():
    set_language("tr")
    assert _get_card_type_label({"limited": True, "value": 3}) == "3 Hak"


def test_timed_label_has_localized_non_turkish_unit():
    set_language("en")
    assert _get_card_type_label({"timed_buff": True, "value": 25}) == "25 sec"
    set_language("tr")
