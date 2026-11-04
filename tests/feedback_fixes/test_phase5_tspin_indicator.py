import inspect
import pytest
from game import Game

pytestmark = [pytest.mark.quadrix_feedback, pytest.mark.quadrix_phase5]

def test_tspin_indicator_has_1500ms_lifecycle():
    source = inspect.getsource(Game.lock_and_new_piece)
    assert "_tspin_indicator_timer = 1500.0" in source
    update = inspect.getsource(Game.update)
    assert "_tspin_indicator_timer" in update

