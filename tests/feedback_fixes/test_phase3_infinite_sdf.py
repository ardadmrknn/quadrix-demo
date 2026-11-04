import inspect
import pytest
from game import Game

pytestmark = [pytest.mark.quadrix_feedback, pytest.mark.quadrix_phase3]

def test_infinite_sdf_has_single_press_instant_drop_path():
    source = inspect.getsource(Game.update)
    assert "get_soft_drop_speed() == 0.0" in source
    assert "while self.board.is_valid_position(self.current_piece, dy=1)" in source

