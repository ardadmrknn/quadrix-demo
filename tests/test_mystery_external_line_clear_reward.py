import os
import sys
from types import SimpleNamespace


sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from game_modes_extra import MysteryMode


def test_post_external_line_clear_opens_reward_overlay_when_threshold_triggers_without_level_queue():
    mode = MysteryMode.__new__(MysteryMode)
    mode.board = SimpleNamespace(score=0)
    mode.energy = 0
    mode.energy_max = 100
    mode.pending_level_ups = 0
    mode.card_selection_active = False
    mode.game_over = False
    mode.paused = False
    mode._apply_line_bonus_reward = lambda cleared: None
    mode.perk_manager = SimpleNamespace(notify_lines_cleared=lambda cleared, source='card': None)

    open_calls = []
    mode._open_card_selection = lambda: open_calls.append('open')
    mode.card_manager = SimpleNamespace(
        pending_choices=[{'id': 'reward'}],
        notify_lines_cleared=lambda cleared, **_kwargs: True,
    )

    mode._post_external_line_clear(2, award_energy=False, score_delta=None, source='ability')

    assert open_calls == ['open']