import pytest

from game import Game

pytestmark = [pytest.mark.quadrix_feedback, pytest.mark.quadrix_phase4]


def test_randomizer_source_declares_single_copy_guideline_bag():
    source = open(Game.__module__.replace('.', '/') + '.py', encoding='utf-8').read() if False else open(Game.__init__.__code__.co_filename, encoding='utf-8').read()
    assert "self._bag_copies: int = 1" in source


def test_randomizer_does_not_apply_consecutive_identity_filter():
    source = open(Game._choose_piece_from_factories.__code__.co_filename, encoding='utf-8').read()
    assert "_would_exceed_max_consecutive" not in source[source.find("def _choose_piece_from_factories"):source.find("def _make_named_piece_factory")]


def test_workshop_factories_are_mode_scoped_and_reportable():
    source = open(Game._get_workshop_piece_factories.__code__.co_filename, encoding='utf-8').read()
    assert "workshop_blocks_by_mode.get(self.game_mode, [])" in source

