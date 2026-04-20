from __future__ import annotations

import importlib
import json
import sys


def _import_real_module(module_name: str):
    sys.modules.pop(module_name, None)
    return importlib.import_module(module_name)


def test_settings_manager_forces_ui_scale_preset_to_compact_and_syncs_runtime(tmp_path):
    ui_scaling_module = _import_real_module('ui_scaling')
    settings_module = _import_real_module('settings_manager')
    settings_file = tmp_path / 'settings.json'
    previous = ui_scaling_module.get_ui_scale_preset()

    try:
        ui_scaling_module.set_ui_scale_preset('large')
        sm = settings_module.SettingsManager(filename=str(settings_file))

        assert sm.get('ui_scale_preset') == 'compact'
        assert ui_scaling_module.get_ui_scale_preset() == 'compact'

        sm.set('ui_scale_preset', 'large')

        assert sm.get('ui_scale_preset') == 'compact'
        assert ui_scaling_module.get_ui_scale_preset() == 'compact'
    finally:
        ui_scaling_module.set_ui_scale_preset(previous)


def test_ui_scale_preset_is_persisted_in_local_settings_payload(tmp_path, monkeypatch):
    SettingsManager = _import_real_module('settings_manager').SettingsManager
    data_dir = tmp_path / 'userdata'
    monkeypatch.setenv('QUADRIX_DATA_DIR', str(data_dir))

    sm = SettingsManager()
    sm.set('ui_scale_preset', 'large')

    cloud_path = data_dir / 'cloud' / 'settings_cloud.json'
    local_path = data_dir / 'local' / 'settings_local.json'

    cloud_payload = json.loads(cloud_path.read_text(encoding='utf-8'))
    local_payload = json.loads(local_path.read_text(encoding='utf-8'))

    assert 'ui_scale_preset' not in cloud_payload
    assert local_payload['ui_scale_preset'] == 'compact'