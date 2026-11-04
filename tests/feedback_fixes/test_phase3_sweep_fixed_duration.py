import pytest
from pathlib import Path
from sweep_effects import compute_line_sweep_progress_speed

pytestmark = [pytest.mark.quadrix_feedback, pytest.mark.quadrix_phase3]

@pytest.mark.parametrize("travel", [640.0, 960.0, 1920.0])
def test_sweep_duration_is_resolution_independent(travel):
    speed = compute_line_sweep_progress_speed(0.12, travel, level=1)
    duration = 1.0 / speed
    assert duration == pytest.approx(0.18, abs=0.005)


def test_game_import_fallback_preserves_fixed_duration_contract():
    source = (Path(__file__).parents[2] / "src" / "game.py").read_text(encoding="utf-8")
    fallback = source.split("except Exception:\n    def _compute_line_sweep_progress_speed", 1)[1]
    fallback = fallback.split("from ui_scaling", 1)[0]
    assert "base_duration = 0.18" in fallback
    assert "travel_px / (block_speed * 3600.0)" not in fallback

