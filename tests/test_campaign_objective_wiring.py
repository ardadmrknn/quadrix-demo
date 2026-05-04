import pathlib
import sys


ROOT_DIR = pathlib.Path(__file__).parent.parent
SRC_DIR = ROOT_DIR / 'src'

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from campaign.campaign_mode import CampaignMode
from campaign.objectives import MultiClearObjective, SpecialBlockObjective, TimeObjective, create_objective
import campaign.campaign_mode as campaign_mode_module
import game as game_module
from ui_theme import UIColors


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


def test_campaign_block_limit_hud_shows_infinity_when_unlimited():
    count_text, color, fill_ratio = CampaignMode._get_block_limit_hud_state(None, 12)

    assert count_text == '∞'
    assert color == UIColors.NEON_GREEN
    assert fill_ratio == 1.0


def test_campaign_block_limit_hud_keeps_finite_remaining_display():
    count_text, color, fill_ratio = CampaignMode._get_block_limit_hud_state(20, 4)

    assert count_text == '16/20'
    assert color == UIColors.NEON_GREEN
    assert fill_ratio == 0.8


def test_special_block_objective_accepts_legacy_type_payload_key():
    objective = create_objective('special_block', target=2, block_type='ice')

    assert isinstance(objective, SpecialBlockObjective)

    objective.update(None, 'special_block_cleared', {'type': 'ice', 'count': 2})

    assert objective.progress == 2
    assert objective.completed is True


def test_campaign_special_block_clear_deltas_emit_block_type_events():
    mode = object.__new__(CampaignMode)
    emitted = []

    class _Manager:
        def __init__(self):
            self.counts = {
                'ice': 2,
                'locked': 0,
                'bomb': 1,
                'star': 0,
                'timer': 0,
            }

        def get_cleared_count(self, block_type):
            return self.counts.get(block_type, 0)

    mode.special_block_manager = _Manager()
    mode._special_block_clear_counts = {
        'ice': 1,
        'locked': 0,
        'bomb': 0,
        'star': 0,
        'timer': 0,
    }
    mode.objectives = []
    mode._emit_event = lambda event_type, event_data: emitted.append((event_type, event_data))

    CampaignMode._emit_special_block_clear_deltas(mode)

    assert emitted == [
        ('special_block_cleared', {'block_type': 'ice', 'count': 1}),
        ('special_block_cleared', {'block_type': 'bomb', 'count': 1}),
    ]
    assert mode._special_block_clear_counts == {
        'ice': 2,
        'locked': 0,
        'bomb': 1,
        'star': 0,
        'timer': 0,
    }


def test_campaign_restart_refreshes_piece_seed_before_base_restart(monkeypatch):
    mode = object.__new__(CampaignMode)
    mode._piece_seed = 111
    mode._quick_retry_seed = 111
    mode._piece_rng_seed = 111

    calls = []

    monkeypatch.setattr(campaign_mode_module.random, 'randint', lambda a, b: 222)
    monkeypatch.setattr(game_module.Game, 'restart', lambda self: calls.append(self._piece_rng_seed))
    mode._reset_level_state = lambda: calls.append('reset')

    CampaignMode.restart(mode)

    assert mode._piece_seed == 222
    assert mode._quick_retry_seed == 222
    assert mode._piece_rng_seed == 222
    assert calls == [222, 'reset']


def test_campaign_quick_restart_reuses_quick_retry_seed_before_base_restart(monkeypatch):
    mode = object.__new__(CampaignMode)
    mode._quick_retry_seed = 333
    mode._piece_rng_seed = 111

    calls = []

    monkeypatch.setattr(game_module.Game, 'restart', lambda self: calls.append(self._piece_rng_seed))
    mode._reset_level_state = lambda: calls.append('reset')

    CampaignMode.quick_restart(mode)

    assert mode._piece_rng_seed == 333
    assert calls == [333, 'reset']


def test_campaign_constructor_exposes_allowed_pieces_before_base_game_init(monkeypatch):
    captured = {}

    def _fake_game_init(self, *args, **kwargs):
        factories = self._get_base_piece_factories()
        captured['factory_names'] = [factory.__defaults__[0] for factory in factories]
        captured['piece_rng_seed'] = kwargs.get('piece_rng_seed')
        self.board = type('Board', (), {'score': 0, 'lines_cleared': 0, 'combo': 0, 'tetrises': 0, 'level': 1})()
        self.window_width = 1280
        self.window_height = 720
        self.sound = None
        self.sound_enabled = False
        self.effects_enabled = False
        self.screen = None
        self.fullscreen = False
        self.settings_manager = None
        self.user_manager = None
        self._game_over_click_targets = {}

    monkeypatch.setattr(game_module.Game, '__init__', _fake_game_init)
    monkeypatch.setattr(campaign_mode_module.random, 'randint', lambda a, b: 0)
    monkeypatch.setattr(CampaignMode, '_init_special_blocks', lambda self: None)
    monkeypatch.setattr(CampaignMode, '_place_garbage_blocks', lambda self: None)
    monkeypatch.setattr(CampaignMode, '_init_campaign_fonts', lambda self: None)

    mode = CampaignMode(current_level=1, settings_manager=None, user_manager=None)

    assert mode._allowed_pieces == ['I', 'O', 'T']
    assert captured['factory_names'] == ['I', 'O', 'T']
    assert captured['piece_rng_seed'] == 0
