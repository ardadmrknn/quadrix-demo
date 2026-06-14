from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
DEMO_CONFIG_PATH = ROOT_DIR / 'src' / 'demo_config.py'


def _load_demo_config(module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, DEMO_CONFIG_PATH)
    if spec is None or spec.loader is None:
        raise AssertionError(f'module could not be loaded: {DEMO_CONFIG_PATH}')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_env_override_enables_demo_mode(monkeypatch) -> None:
    monkeypatch.setenv('QUADRIX_DEMO_MODE', '1')
    demo_config = _load_demo_config('repo_demo_config_env')

    env: dict[str, str] = {}
    applied = demo_config.apply_runtime_environment(env)

    assert demo_config.IS_DEMO is True
    assert applied == 'quadrix_demo'
    assert env['QUADRIX_APP_NAME'] == 'quadrix_demo'
    assert env['QUADRIX_DEMO_MODE'] == '1'


def test_without_env_stays_full_mode(monkeypatch) -> None:
    monkeypatch.delenv('QUADRIX_DEMO_MODE', raising=False)
    demo_config = _load_demo_config('repo_demo_config_full')

    env: dict[str, str] = {}
    applied = demo_config.apply_runtime_environment(env)

    assert demo_config.IS_DEMO is False
    assert applied == 'quadrix_full'
    assert env['QUADRIX_APP_NAME'] == 'quadrix_full'
    assert 'QUADRIX_DEMO_MODE' not in env