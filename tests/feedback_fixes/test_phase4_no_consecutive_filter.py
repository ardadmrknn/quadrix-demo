import inspect
import pytest

from game import Game

pytestmark = [pytest.mark.quadrix_feedback, pytest.mark.quadrix_phase4]


def test_repeat_filter_is_not_used_by_piece_bag():
    source = inspect.getsource(Game._choose_piece_from_factories)
    assert "_would_exceed_max_consecutive" not in source
    assert "_bag_copies" not in source or "7-bag" in source

