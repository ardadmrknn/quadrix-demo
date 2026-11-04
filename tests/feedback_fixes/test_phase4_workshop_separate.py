import inspect
import pytest

from game import Game

pytestmark = [pytest.mark.quadrix_feedback, pytest.mark.quadrix_phase4]


def test_workshop_pool_is_reported_separately_without_live_ratio_guess():
    source = inspect.getsource(Game._refill_piece_bag)
    assert "workshop" in source.lower()
    assert "_bag_copies" in source or "copies = 1" in source
