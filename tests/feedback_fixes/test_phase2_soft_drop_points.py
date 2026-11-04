import pytest

from game import Game


pytestmark = [pytest.mark.quadrix_feedback, pytest.mark.quadrix_phase2]


def test_soft_drop_scoring_is_gated_to_successful_moves_and_not_keydown_events():
    source = Game.handle_input.__code__.co_filename
    text = open(source, encoding="utf-8").read()
    assert "self.board.score += 1" not in text[text.find("def handle_input"):text.find("def handle_input") + 3000]
    update_text = text[text.find("def update(self, delta_time)"):]
    assert "self.board.score += 1" in update_text
    assert "if getattr(self, '_soft_drop_held', False):" in update_text

