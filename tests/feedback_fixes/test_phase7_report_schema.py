from __future__ import annotations

import pathlib
import sys

import pytest

ROOT_DIR = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from tools.campaign_solvability_scan import render_report, scan_campaign

pytestmark = [pytest.mark.quadrix_feedback, pytest.mark.quadrix_phase7]


def test_report_contains_required_schema_and_all_levels():
    report = render_report(scan_campaign(100), generated="2026-11-05")
    assert "Generated: 2026-11-05" in report
    assert "level_data` değerleri değiştirilmedi" in report
    assert "Seed" in report and "Başarı oranı" in report
    assert report.count("| ") >= 100
    assert "| 1 |" in report and "| 100 |" in report
