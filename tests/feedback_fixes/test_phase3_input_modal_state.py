import inspect
import pytest
from game import Game

pytestmark = [pytest.mark.quadrix_feedback, pytest.mark.quadrix_phase3]

def test_are_buffers_rotate_hold_and_drop_inputs():
    source = open(Game.handle_input.__code__.co_filename, encoding="utf-8").read()
    assert "_pending_rotate" in source
    assert "_pending_hold" in source
    assert "_pending_drop" in source

