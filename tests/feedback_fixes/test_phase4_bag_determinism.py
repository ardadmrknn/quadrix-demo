import pytest

pytestmark = [pytest.mark.quadrix_feedback, pytest.mark.quadrix_phase4]


def test_same_seed_produces_same_standard_bag_sequence(seeded_game):
    first = seeded_game(2026)
    second = seeded_game(2026)
    assert [first.spawn_new_piece().name for _ in range(70)] == [second.spawn_new_piece().name for _ in range(70)]

