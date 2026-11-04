import inspect
import pytest
from game import Game

pytestmark = [pytest.mark.quadrix_feedback, pytest.mark.quadrix_phase3]

def test_gravity_pause_contract_mentions_animation_and_soft_drop_override():
    doc = inspect.getdoc(Game._automatic_gravity_paused) or ""
    assert "soft drop" in doc.lower()
    assert "animasyon" in doc.lower()

