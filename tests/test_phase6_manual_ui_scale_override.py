from __future__ import annotations

import importlib
import json
import sys


def _import_real_module(module_name: str):
    sys.modules.pop(module_name, None)
    return importlib.import_module(module_name)


def test_settings_manager_syncs_ui_scale_preset_with_stored_default_and_user_choice(tmp_path):
    """Preset sözleşmesi (76cb8c6 4K niyeti): SettingsManager preset'i
    compact'a ZORLAMAZ. Kayıtlı değer yoksa default ('normal') kullanılır ve
    runtime değerine senkronlanır (drift düzelir); geçerli kullanıcı seçimi
    aynen kalıcılaşır ve anında runtime'a uygulanır; geçersiz değer
    default'a normalize edilir."""
    ui_scaling_module = _import_real_module('ui_scaling')
    settings_module = _import_real_module('settings_manager')
    settings_file = tmp_path / 'settings.json'
    previous = ui_scaling_module.get_ui_scale_preset()

    try:
        # Runtime drift: başka bir kaynak preset'i değiştirmiş olsun.
        ui_scaling_module.set_ui_scale_preset('large')
        sm = settings_module.SettingsManager(filename=str(settings_file))

        # Taze profil (dosya yok): kayıtlı değer yok -> default 'normal';
        # __init__'teki _sync_ui_scale_preset runtime'ı depoya çeker.
        assert sm.get('ui_scale_preset') == 'normal'
        assert ui_scaling_module.get_ui_scale_preset() == 'normal'

        sm.set('ui_scale_preset', 'large')

        # Geçerli preset aynen kalıcılaşır ve runtime'a anında senkronlanır.
        assert sm.get('ui_scale_preset') == 'large'
        assert ui_scaling_module.get_ui_scale_preset() == 'large'

        # Geçersiz preset normalize edilir: default'a döner.
        sm.set('ui_scale_preset', 'bogus')
        assert sm.get('ui_scale_preset') == 'normal'
        assert ui_scaling_module.get_ui_scale_preset() == 'normal'
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

    # ui_scale_preset LOCAL_SETTINGS_KEYS üyesidir: cihaza bağlı görünüm
    # tercihi buluta taşınmaz, yerel payload'da kullanıcının seçtiği değerle
    # durur ('compact'a zorlanmaz).
    assert 'ui_scale_preset' not in cloud_payload
    assert local_payload['ui_scale_preset'] == 'large'
