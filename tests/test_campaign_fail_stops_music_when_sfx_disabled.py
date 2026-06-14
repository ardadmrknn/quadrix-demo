import pathlib
import sys


ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / 'src'

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from campaign import campaign_mode as campaign_mode_module


class _SoundStub:
    def __init__(self):
        self.game_over_sequence_calls = 0

    def play_game_over_sequence(self):
        self.game_over_sequence_calls += 1


def test_campaign_fail_triggers_game_over_sequence_when_sfx_disabled(monkeypatch):
    mode = campaign_mode_module.CampaignMode.__new__(campaign_mode_module.CampaignMode)
    mode.level_failed = False
    mode.fail_reason = ""
    mode.sound_enabled = False
    mode.sound = _SoundStub()

    started_reasons = []
    monkeypatch.setattr(
        campaign_mode_module.campaign_ui_effects,
        'start_level_failed',
        lambda reason: started_reasons.append(reason),
    )

    mode._handle_level_failed('block limit reached')

    assert mode.level_failed is True
    assert mode.fail_reason == 'block limit reached'
    assert started_reasons == ['block limit reached']
    assert mode.sound.game_over_sequence_calls == 1


def test_campaign_fail_skip_sound_keeps_sequence_silent(monkeypatch):
    mode = campaign_mode_module.CampaignMode.__new__(campaign_mode_module.CampaignMode)
    mode.level_failed = False
    mode.fail_reason = ""
    mode.sound_enabled = False
    mode.sound = _SoundStub()

    monkeypatch.setattr(campaign_mode_module.campaign_ui_effects, 'start_level_failed', lambda reason: None)

    mode._handle_level_failed('board overflow', skip_sound=True)

    assert mode.level_failed is True
    assert mode.sound.game_over_sequence_calls == 0