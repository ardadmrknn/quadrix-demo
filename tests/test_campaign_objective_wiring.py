import pathlib
import sys


ROOT_DIR = pathlib.Path(__file__).parent.parent
SRC_DIR = ROOT_DIR / 'src'

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from campaign.campaign_mode import CampaignMode
from campaign.objectives import MultiClearObjective, TimeObjective, create_objective


def test_create_objective_maps_multi_clear_to_single_event_objective():
    objective = create_objective('multi_clear', target=3)

    assert isinstance(objective, MultiClearObjective)
    assert objective.target == 1
    assert objective.lines_required == 3


def test_create_objective_maps_time_challenge_to_complete_time_objective():
    objective = create_objective('time_challenge', target=75)

    assert isinstance(objective, TimeObjective)
    assert objective.target == 75
    assert objective.objective_type == 'complete'


def test_time_challenge_completes_when_other_objectives_finish_within_limit():
    time_objective = create_objective('time_challenge', target=75)
    lines_objective = create_objective('clear_lines', target=2)

    class _Game:
        objectives = [lines_objective, time_objective]

    lines_objective.update(_Game, 'lines_cleared', {'lines': 2})
    time_objective.update(_Game, 'time_update', {'elapsed': 60.0})

    assert lines_objective.completed is True
    assert time_objective.completed is True


def test_campaign_star_move_limit_uses_completed_run_move_count():
    mode = object.__new__(CampaignMode)
    mode.level_complete = True
    mode.moves_count = 27
    mode.elapsed_time = 40.0
    mode.board = type('Board', (), {'score': 0})()
    mode.objectives = []
    mode.total_combos = 0
    mode.double_count = 0
    mode.triple_count = 0
    mode.tetris_count = 0
    mode.max_combo_chain = 0

    assert mode._is_star_condition_met({'type': 'move_limit', 'value': 28}) is True
    assert mode._is_star_condition_met({'type': 'move_limit', 'value': 26}) is False