import pytest

from pieces import SHAPE_NAMES

pytestmark = [pytest.mark.quadrix_feedback, pytest.mark.quadrix_phase4]


def test_standard_bag_is_single_copy_and_each_block_has_one_of_each_type(game_factory):
    game = game_factory({})
    game._bag_copies = 1
    sequence = [game.spawn_new_piece().name for _ in range(70)]
    expected = set(SHAPE_NAMES)
    assert all(set(sequence[i:i + 7]) == expected for i in range(0, 70, 7))

