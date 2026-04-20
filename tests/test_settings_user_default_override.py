from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path


def _import_real_module(module_name: str):
    sys.modules.pop(module_name, None)
    return importlib.import_module(module_name)


def test_user_default_override_applies_in_split_mode(tmp_path, monkeypatch):
    settings_module = _import_real_module('settings_manager')
    SettingsManager = settings_module.SettingsManager

    data_dir = tmp_path / 'userdata'
    monkeypatch.setenv('QUADRIX_DATA_DIR', str(data_dir))

    override_path = data_dir / 'cloud' / settings_module.DEFAULT_SETTINGS_OVERRIDE_FILENAME
    override_path.parent.mkdir(parents=True, exist_ok=True)
    override_payload = {
        'das_repeat': 91,
        'ui_scale_preset': 'compact',
        'controls': {
            'single_player': {
                'move_left': {'primary': 'j', 'secondary': 'a'},
            },
            'gamepad': {
                'enabled': False,
            },
        },
    }
    override_path.write_text(json.dumps(override_payload, ensure_ascii=False, indent=2), encoding='utf-8')

    sm = SettingsManager()

    assert sm.default_settings['das_repeat'] == 91
    assert sm.default_settings['ui_scale_preset'] == 'compact'
    controls = sm.default_settings['controls']
    assert controls['single_player']['move_left']['primary'] == 'j'
    assert controls['single_player']['move_right']['primary'] == 'right'
    assert controls['gamepad']['enabled'] is False


def test_save_current_as_defaults_writes_override_snapshot(tmp_path, monkeypatch):
    settings_module = _import_real_module('settings_manager')
    SettingsManager = settings_module.SettingsManager

    data_dir = tmp_path / 'userdata'
    monkeypatch.setenv('QUADRIX_DATA_DIR', str(data_dir))

    sm = SettingsManager()
    sm.set('ui_scale_preset', 'large')
    sm.set('das_repeat', 88)

    path = sm.save_current_as_defaults()

    assert path is not None
    override_path = Path(path)
    assert override_path.exists()

    payload = json.loads(override_path.read_text(encoding='utf-8'))
    assert payload['ui_scale_preset'] == 'large'
    assert payload['das_repeat'] == 88

    sm_reloaded = SettingsManager()
    assert sm_reloaded.default_settings['ui_scale_preset'] == 'large'
    assert sm_reloaded.default_settings['das_repeat'] == 88
