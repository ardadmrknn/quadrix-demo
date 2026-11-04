import inspect
import pytest
from game import Game

pytestmark = [pytest.mark.quadrix_feedback, pytest.mark.quadrix_phase5]

def test_ghost_render_is_settings_gated():
    source = open(Game.get_ghost_y.__code__.co_filename, encoding='utf-8').read()
    assert "show_ghost" in source
    assert "and show_ghost" in source

