from __future__ import annotations

import copy
import pathlib
import sys

import pytest

ROOT_DIR = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from campaign.level_data import get_levels
from tools.campaign_solvability_scan import scan_campaign

pytestmark = [pytest.mark.quadrix_feedback, pytest.mark.quadrix_phase7]


def test_scan_does_not_mutate_level_data():
    before = copy.deepcopy(get_levels())
    scan_campaign(100)
    after = get_levels()
    assert after == before

