
from settings_manager import SettingsManager


def test_display_defaults_match_requested_values(tmp_path) -> None:
    manager = SettingsManager(filename=str(tmp_path / 'settings.json'))

    assert manager.default_settings['bg_transparency'] == 0.7
    assert manager.default_settings['effects_opacity'] == 1.0
    assert manager.default_settings['menu_transparency'] == 1.0
    assert manager.default_settings['particle_effects'] == 'medium'
