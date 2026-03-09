from __future__ import annotations

import sys
from pathlib import Path

from tools.bridge_artifacts import get_bridge_binaries


def _touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b'dummy')


def test_get_bridge_binaries_finds_current_legacy_and_build_outputs(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(sys, 'platform', 'win32')

    current = tmp_path / 'local_artifacts' / 'bridge' / 'steam_net_bridge.cp312-win_amd64.pyd'
    legacy_root = tmp_path / 'steam_net_bridge.cp312-win_amd64.pyd'
    build_output = tmp_path / 'steamworks' / 'steam_net_bridge' / 'build_win64' / 'Release' / 'steam_net_bridge.cp312-win_amd64.pyd'

    _touch(current)
    _touch(legacy_root)
    _touch(build_output)

    results = get_bridge_binaries(tmp_path)

    assert str(current) in results
    assert str(legacy_root) in results
    assert str(build_output) in results
