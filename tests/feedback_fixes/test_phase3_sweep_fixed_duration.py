import pytest
from sweep_effects import compute_line_sweep_progress_speed

pytestmark = [pytest.mark.quadrix_feedback, pytest.mark.quadrix_phase3]

@pytest.mark.parametrize("travel", [640.0, 960.0, 1920.0])
def test_sweep_duration_is_resolution_independent(travel):
    speed = compute_line_sweep_progress_speed(0.12, travel, level=1)
    duration = 1.0 / speed
    assert duration == pytest.approx(0.18, abs=0.005)

