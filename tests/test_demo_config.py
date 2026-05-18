from __future__ import annotations

import importlib.util
import runpy
import sys
import types
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
WRITER_PATH = ROOT_DIR / 'scripts' / 'build' / 'write_demo_config.py'
HOOK_PATH = ROOT_DIR / 'packaging' / 'pyinstaller' / 'hooks' / 'pyi_rth_quadrix_data.py'


def _load_module_from_path(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise AssertionError(f'module could not be loaded: {path}')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_write_demo_config_generates_demo_and_full_variants(tmp_path) -> None:
    writer = _load_module_from_path('write_demo_config_test', WRITER_PATH)
    output_path = tmp_path / 'demo_config.py'

    writer.write_demo_config(output_path=output_path, mode='demo')
    demo_source = output_path.read_text(encoding='utf-8')
    assert 'IS_DEMO = True' in demo_source
    assert 'DEMO_STEAM_APP_ID = "4635310"' in demo_source
    assert 'DEMO_STEAM_STORE_URL = "https://store.steampowered.com/app/4414520/Quadrix/"' in demo_source
    assert 'get_card_selection_level_interval' not in demo_source
    assert 'DEMO_CARD_SELECTION_LEVEL_INTERVAL' not in demo_source
    assert compile(demo_source, str(output_path), 'exec')

    writer.write_demo_config(output_path=output_path, mode='full')
    full_source = output_path.read_text(encoding='utf-8')
    assert 'IS_DEMO = False' in full_source
    assert 'get_card_selection_level_interval' not in full_source
    assert 'DEMO_CARD_SELECTION_LEVEL_INTERVAL' not in full_source
    assert compile(full_source, str(output_path), 'exec')


def test_generated_demo_config_applies_demo_app_name(tmp_path) -> None:
    writer = _load_module_from_path('write_demo_config_runtime', WRITER_PATH)
    output_path = tmp_path / 'demo_config.py'
    writer.write_demo_config(output_path=output_path, mode='demo')

    demo_config = _load_module_from_path('generated_demo_config', output_path)
    env = {}

    applied = demo_config.apply_runtime_environment(env)

    assert applied == 'quadrix_demo'
    assert env['QUADRIX_APP_NAME'] == 'quadrix_demo'
    assert not hasattr(demo_config, 'get_card_selection_level_interval')
    assert not hasattr(demo_config, 'DEMO_CARD_SELECTION_LEVEL_INTERVAL')


def test_generated_full_config_applies_full_app_name(tmp_path) -> None:
    writer = _load_module_from_path('write_full_config_runtime', WRITER_PATH)
    output_path = tmp_path / 'demo_config.py'
    writer.write_demo_config(output_path=output_path, mode='full')

    demo_config = _load_module_from_path('generated_full_config', output_path)
    env = {}

    applied = demo_config.apply_runtime_environment(env)

    assert applied == 'quadrix_full'
    assert env['QUADRIX_APP_NAME'] == 'quadrix_full'
    assert not hasattr(demo_config, 'get_card_selection_level_interval')
    assert not hasattr(demo_config, 'DEMO_CARD_SELECTION_LEVEL_INTERVAL')


def test_runtime_hook_uses_demo_app_name_when_demo_module_is_present(monkeypatch) -> None:
    fake_demo_config = types.SimpleNamespace(
        IS_DEMO=True,
        DEMO_APP_NAME='quadrix_demo',
        FULL_APP_NAME='quadrix_full',
        get_runtime_app_name=lambda: 'quadrix_demo',
    )

    monkeypatch.delenv('QUADRIX_APP_NAME', raising=False)
    monkeypatch.delenv('TETRIS_APP_NAME', raising=False)
    monkeypatch.setitem(sys.modules, 'demo_config', fake_demo_config)
    monkeypatch.delitem(sys.modules, 'src.demo_config', raising=False)

    runpy.run_path(str(HOOK_PATH), run_name='__main__')

    assert 'demo_config' in sys.modules
    assert sys.modules['demo_config'] is fake_demo_config
    assert sys.modules['demo_config'].DEMO_APP_NAME == 'quadrix_demo'
    assert __import__('os').environ['QUADRIX_APP_NAME'] == 'quadrix_demo'


def test_runtime_hook_uses_full_app_name_when_full_module_is_present(monkeypatch) -> None:
    fake_demo_config = types.SimpleNamespace(
        IS_DEMO=False,
        DEMO_APP_NAME='quadrix_demo',
        FULL_APP_NAME='quadrix_full',
        get_runtime_app_name=lambda: 'quadrix_full',
    )

    monkeypatch.delenv('QUADRIX_APP_NAME', raising=False)
    monkeypatch.delenv('TETRIS_APP_NAME', raising=False)
    monkeypatch.setitem(sys.modules, 'demo_config', fake_demo_config)
    monkeypatch.delitem(sys.modules, 'src.demo_config', raising=False)

    runpy.run_path(str(HOOK_PATH), run_name='__main__')

    assert __import__('os').environ['QUADRIX_APP_NAME'] == 'quadrix_full'
