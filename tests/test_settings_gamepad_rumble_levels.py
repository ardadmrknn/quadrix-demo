"""settings_manager.py — gamepad rumble seviye normalizasyonu ve yardımcıları."""

from settings_manager import GAMEPAD_RUMBLE_MULTIPLIERS, SettingsManager


def test_gamepad_rumble_values_normalize_legacy_inputs():
    assert SettingsManager.normalize_gamepad_rumble_value(False) == 'off'
    assert SettingsManager.normalize_gamepad_rumble_value(True) == 'high'
    assert SettingsManager.normalize_gamepad_rumble_value(1) == 'low'
    assert SettingsManager.normalize_gamepad_rumble_value(2) == 'medium'
    assert SettingsManager.normalize_gamepad_rumble_value(3) == 'high'
    assert SettingsManager.normalize_gamepad_rumble_value('yok') == 'off'
    assert SettingsManager.normalize_gamepad_rumble_value('az') == 'low'
    assert SettingsManager.normalize_gamepad_rumble_value('orta') == 'medium'
    assert SettingsManager.normalize_gamepad_rumble_value('çok') == 'high'
    assert SettingsManager.normalize_gamepad_rumble_value('') == 'high'


def test_gamepad_rumble_slider_helpers_roundtrip_levels():
    expected = {0: 'off', 1: 'low', 2: 'medium', 3: 'high'}

    for slider_value, level in expected.items():
        assert SettingsManager.gamepad_rumble_level_from_slider(slider_value) == level
        assert SettingsManager.gamepad_rumble_slider_value(level) == slider_value

    assert SettingsManager.gamepad_rumble_multiplier_for_value('off') == GAMEPAD_RUMBLE_MULTIPLIERS['off']
    assert SettingsManager.gamepad_rumble_multiplier_for_value('medium') == GAMEPAD_RUMBLE_MULTIPLIERS['medium']
    assert SettingsManager.gamepad_rumble_enabled_for_value('off') is False
    assert SettingsManager.gamepad_rumble_enabled_for_value('low') is True


def test_merge_controls_normalizes_legacy_gamepad_rumble_values():
    sm = SettingsManager.__new__(SettingsManager)

    merged_true = sm._merge_controls({'gamepad': {'rumble': True}})
    merged_false = sm._merge_controls({'gamepad': {'rumble': False}})
    merged_text = sm._merge_controls({'gamepad': {'rumble': 'orta'}})

    assert merged_true['gamepad']['rumble'] == 'high'
    assert merged_false['gamepad']['rumble'] == 'off'
    assert merged_text['gamepad']['rumble'] == 'medium'


def test_instance_gamepad_rumble_helpers_use_normalized_controls():
    sm = SettingsManager.__new__(SettingsManager)
    sm.settings = {'controls': {'gamepad': {'rumble': 'az'}}}

    assert sm.get_gamepad_rumble_level() == 'low'
    assert sm.get_gamepad_rumble_multiplier() == GAMEPAD_RUMBLE_MULTIPLIERS['low']
    assert sm.gamepad_rumble_enabled() is True
