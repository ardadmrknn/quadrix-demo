from __future__ import annotations

import pathlib
import sys

import pytest

ROOT_DIR = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from tools.campaign_solvability_scan import scan_campaign

pytestmark = [pytest.mark.quadrix_feedback, pytest.mark.quadrix_phase7]


def test_scan_covers_all_levels_and_seed_count():
    rows = scan_campaign(100)
    assert len(rows) == 100
    assert {row["level"] for row in rows} == set(range(1, 101))
    assert all(row["seed_count"] == 100 for row in rows)

