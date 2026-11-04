import inspect
import pytest
from game import Game

pytestmark = [pytest.mark.quadrix_feedback, pytest.mark.quadrix_phase3]

def test_lock_path_defers_spawn_until_clear_fall_completes():
    source = inspect.getsource(Game.lock_and_new_piece)
    assert "line_clear_sweep_active" in source
    assert "_pending_next_piece" in source

