from __future__ import annotations

from campaign import level_select as solo_level_select
from campaign import coop_level_select


def test_demo_solo_campaign_limits_block_world_and_level(monkeypatch) -> None:
    prompt_calls: list[str] = []

    monkeypatch.setattr(solo_level_select.demo_config, 'IS_DEMO', True)
    monkeypatch.setattr(solo_level_select, 'show_demo_partial_lock_prompt', lambda _prompt: prompt_calls.append('solo'))

    selector = solo_level_select.CampaignLevelSelect.__new__(solo_level_select.CampaignLevelSelect)
    selector.debug_unlock_all = False
    selector.progress = {
        'completed_levels': {str(level): {'completed': True} for level in range(1, 20)},
    }
    selector._demo_upgrade_prompt = object()
    selector.current_world = 1
    selector.previous_world = 1
    selector.target_world = 1
    selector.world_transition_active = False
    selector.world_transition_progress = 0.0
    selector.hovered_level = None
    selector._update_selection_for_world = lambda: None

    assert selector._is_level_unlocked(20) is True
    assert selector._is_level_unlocked(21) is False

    selector._start_world_transition(2)

    assert selector.current_world == 1
    assert prompt_calls == ['solo']


def test_demo_coop_campaign_limits_block_world_and_level(monkeypatch) -> None:
    prompt_calls: list[str] = []

    monkeypatch.setattr(coop_level_select.demo_config, 'IS_DEMO', True)
    monkeypatch.setattr(coop_level_select, 'show_demo_partial_lock_prompt', lambda _prompt: prompt_calls.append('coop'))

    selector = coop_level_select.CoopLevelSelect.__new__(coop_level_select.CoopLevelSelect)
    selector.progress = {
        'completed_levels': {str(level): {'completed': True} for level in range(1, 10)},
    }
    selector._demo_upgrade_prompt = object()

    assert selector._is_level_unlocked(10) is True
    assert selector._is_level_unlocked(11) is False

    assert selector._maybe_handle_demo_world_lock(2) is True
    assert prompt_calls == ['coop']