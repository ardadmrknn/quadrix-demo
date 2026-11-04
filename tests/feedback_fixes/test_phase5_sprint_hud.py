import inspect
import pytest
from game import Game

pytestmark = [pytest.mark.quadrix_feedback, pytest.mark.quadrix_phase5]

def test_sprint_hud_omits_score_row():
    source = open(Game.__init__.__code__.co_filename, encoding='utf-8').read()
    assert "sprint_mode" in source
    assert "stat_row_defs = [] if sprint_mode" in source
