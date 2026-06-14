"""settings_manager.py — parçacık efekt seviyesi normalizasyonu ve yardımcıları."""

from settings_manager import PARTICLE_EFFECT_MULTIPLIERS, SettingsManager


def test_particle_effect_values_normalize_legacy_inputs():
    assert SettingsManager.normalize_particle_effects_value(False) == 'off'
    assert SettingsManager.normalize_particle_effects_value(True) == 'medium'
    assert SettingsManager.normalize_particle_effects_value(1) == 'low'
    assert SettingsManager.normalize_particle_effects_value(2) == 'medium'
    assert SettingsManager.normalize_particle_effects_value(3) == 'high'
    assert SettingsManager.normalize_particle_effects_value('az') == 'low'
    assert SettingsManager.normalize_particle_effects_value('çok') == 'high'
    assert SettingsManager.normalize_particle_effects_value('') == 'medium'


def test_particle_effect_slider_helpers_roundtrip_levels():
    expected = {0: 'off', 1: 'low', 2: 'medium', 3: 'high'}

    for slider_value, level in expected.items():
        assert SettingsManager.particle_effects_level_from_slider(slider_value) == level
        assert SettingsManager.particle_effects_slider_value(level) == slider_value

    assert SettingsManager.particle_effects_multiplier_for_value('off') == PARTICLE_EFFECT_MULTIPLIERS['off']
    assert SettingsManager.particle_effects_multiplier_for_value('high') == PARTICLE_EFFECT_MULTIPLIERS['high']
    assert SettingsManager.particle_effects_enabled_for_value('off') is False
    assert SettingsManager.particle_effects_enabled_for_value('low') is True


def test_normalize_display_settings_migrates_legacy_particle_boolean():
    sm = SettingsManager.__new__(SettingsManager)
    sm.default_settings = {
        'particle_effects': 'medium',
        'ui_scale_preset': 'normal',
    }

    true_payload = {'particle_effects': True}
    false_payload = {'particle_effects': False}

    assert sm._normalize_display_settings_inplace(true_payload) is True
    assert true_payload['particle_effects'] == 'medium'

    assert sm._normalize_display_settings_inplace(false_payload) is True
    assert false_payload['particle_effects'] == 'off'


def test_instance_particle_effect_helpers_use_normalized_setting():
    sm = SettingsManager.__new__(SettingsManager)
    sm.default_settings = {'particle_effects': 'medium'}
    sm.settings = {'particle_effects': 'çok'}

    assert sm.get_particle_effects_level() == 'high'
    assert sm.get_particle_effects_multiplier() == PARTICLE_EFFECT_MULTIPLIERS['high']
    assert sm.particle_effects_enabled() is True