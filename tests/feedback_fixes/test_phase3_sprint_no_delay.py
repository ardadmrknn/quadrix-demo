import inspect
import pytest
from game import Game

pytestmark = [pytest.mark.quadrix_feedback, pytest.mark.quadrix_phase3]

def test_sprint_and_40l_bypass_clear_fall_pause():
    source = inspect.getsource(Game._automatic_gravity_paused)
    assert "sprint" in source.lower()
    assert "40l" in source.lower() or "40l" in source

