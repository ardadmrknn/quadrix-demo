from __future__ import annotations

import pathlib


ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
SPECS_DIR = ROOT_DIR / 'packaging' / 'specs'
SCRIPTS_DIR = ROOT_DIR / 'scripts' / 'build'


def _read_text(path: pathlib.Path) -> str:
    return path.read_text(encoding='utf-8')


def test_windows_demo_spec_contains_demo_artifact_and_runtime_appid() -> None:
    content = _read_text(SPECS_DIR / 'tetris_demo.spec')

    assert "os.environ.setdefault('STEAM_APP_ID', '4635310')" in content
    assert 'steam_appid_demo.txt' in content
    assert "name='QuadrixDemo'" in content
    assert 'pyi_rth_quadrix_data.py' in content
    assert 'libsteam_api.dylib' in content
    compile(content, 'tetris_demo.spec', 'exec')


def test_macos_demo_spec_contains_demo_bundle_identity() -> None:
    content = _read_text(SPECS_DIR / 'tetris_demo_macos_allinone.spec')

    assert "os.environ.setdefault('STEAM_APP_ID', '4635310')" in content
    assert 'steam_appid_demo.txt' in content
    assert "name='Quadrix Demo.app'" in content
    assert "bundle_identifier='com.burakyasayan.quadrix.demo'" in content
    assert "'CFBundleDisplayName': 'Quadrix Demo'" in content
    assert "'CFBundleExecutable': 'QuadrixDemo'" in content
    assert 'libsteam_api.dylib' in content
    compile(content, 'tetris_demo_macos_allinone.spec', 'exec')


def test_windows_demo_wrapper_restores_full_config_and_targets_demo_spec() -> None:
    content = _read_text(SCRIPTS_DIR / 'build_windows_demo.ps1')

    assert "scripts/build/write_demo_config.py' --mode demo" in content
    assert "scripts/build/write_demo_config.py' --mode full" in content
    assert 'packaging/specs/tetris_demo.spec' in content
    assert 'QuadrixDemo.exe' in content


def test_macos_demo_wrapper_targets_demo_spec_and_restores_full_config() -> None:
    content = _read_text(SCRIPTS_DIR / 'build_macos_demo_app.sh')

    assert 'write_demo_config.py" --mode demo' in content or 'write_demo_config.py --mode demo' in content
    assert 'write_demo_config.py" --mode full' in content or 'write_demo_config.py --mode full' in content
    assert '--spec packaging/specs/tetris_demo_macos_allinone.spec' in content
    assert '--app-name "Quadrix Demo"' in content
    assert 'trap restore_full_config EXIT' in content


def test_macos_build_script_accepts_spec_and_app_name_parameters() -> None:
    content = _read_text(SCRIPTS_DIR / 'build_macos_app.sh')

    assert '--spec' in content
    assert '--app-name' in content
    assert 'SPEC_FILE="$2"' in content
    assert 'APP_NAME="$2"' in content