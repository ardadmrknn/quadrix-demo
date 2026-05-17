"""External (card/ability) line clear behavior in MysteryMode.

These tests pin down the anti-farm rule: external clears must NOT award
card XP and must NOT open the reward overlay on their own. Card-level
progression is driven exclusively by player-source line clears so that
chained card effects cannot generate free reward levels.
"""

import os
import sys
from types import SimpleNamespace


sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from game_modes_extra import MysteryMode


def _make_mode_with_card_manager(notify_return_value):
    """Helper to construct a MysteryMode stub wired to a fake card manager."""
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

    notify_calls = []

    def fake_notify(cleared, *, source='player', **kwargs):
        notify_calls.append({'cleared': cleared, 'source': source, **kwargs})
        return notify_return_value

    mode.card_manager = SimpleNamespace(
        pending_choices=[{'id': 'reward'}],
        notify_lines_cleared=fake_notify,
    )
    return mode, open_calls, notify_calls


def test_external_line_clear_forwards_source_to_card_manager():
    """The mode must propagate the non-player source so card_manager can
    apply the anti-farm rule and skip XP gain."""
    mode, _, notify_calls = _make_mode_with_card_manager(notify_return_value=False)

    mode._post_external_line_clear(2, award_energy=False, score_delta=None, source='ability')

    assert notify_calls == [{'cleared': 2, 'source': 'ability'}]


def test_external_line_clear_does_not_open_reward_overlay_even_if_pending_choices_exist():
    """Even if the manager has pending_choices ready, external clears must not
    open the reward overlay on their own. Reward overlays are opened only by
    pending_level_ups queued from real (player-source) card-level gains."""
    # Some other system might have pre-populated pending_choices; that should
    # not trigger an overlay from an external clear path.
    mode, open_calls, _ = _make_mode_with_card_manager(notify_return_value=False)

    mode._post_external_line_clear(4, award_energy=False, score_delta=None, source='card')

    assert open_calls == []
    assert mode.pending_level_ups == 0


def test_external_line_clear_does_not_increment_pending_level_ups():
    """Sweep / Alt Süpür / patlama / gravity collapse / workshop sources must
    not bump pending_level_ups regardless of how many lines they wipe out."""
    mode, _, _ = _make_mode_with_card_manager(notify_return_value=False)

    for src in ('card', 'ability', 'workshop', 'gravity'):
        mode._post_external_line_clear(4, award_energy=False, score_delta=None, source=src)

    assert mode.pending_level_ups == 0
