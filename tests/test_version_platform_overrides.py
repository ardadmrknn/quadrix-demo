from __future__ import annotations

import pathlib
import sys
import types
from unittest.mock import patch


ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / 'src'

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import version as version_module
import version_base


def test_version_falls_back_to_base_when_override_missing():
    with patch.object(version_module.sys, 'platform', 'win32'):
        with patch.object(version_module.importlib, 'import_module', side_effect=ImportError):
            version, build_number, source = version_module._load_platform_override()

    assert version == version_base.VERSION
    assert build_number == version_base.BUILD_NUMBER
    assert source == 'version_base'


def test_version_uses_windows_platform_override_module_when_present():
    fake_module = types.SimpleNamespace(VERSION='9.9.9', BUILD_NUMBER=999)

    with patch.object(version_module.sys, 'platform', 'win32'):
        with patch.object(version_module.importlib, 'import_module', return_value=fake_module):
            version, build_number, source = version_module._load_platform_override()

    assert version == '9.9.9'
    assert build_number == 999
    assert source == 'version_local_windows'


def test_version_uses_base_on_macos_without_override_module():
    with patch.object(version_module.sys, 'platform', 'darwin'):
        version, build_number, source = version_module._load_platform_override()

    assert version == version_base.VERSION
    assert build_number == version_base.BUILD_NUMBER
    assert source == 'version_base'