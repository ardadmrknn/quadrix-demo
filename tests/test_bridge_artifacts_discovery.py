from __future__ import annotations

import os
import sys
from pathlib import Path

from tools.bridge_artifacts import get_bridge_binaries


def _bridge_filename(python_tag: str | None = None) -> str:
    tag = python_tag or f'cp{sys.version_info.major}{sys.version_info.minor}'
    return f'steam_net_bridge.{tag}-win_amd64.pyd'


def _other_python_tag() -> str:
    current = f'cp{sys.version_info.major}{sys.version_info.minor}'
    return 'cp310' if current != 'cp310' else 'cp311'


def _touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b'dummy')


def test_get_bridge_binaries_finds_current_legacy_and_build_outputs(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(sys, 'platform', 'win32')

    current = tmp_path / 'local_artifacts' / 'bridge' / _bridge_filename()
    legacy_root = tmp_path / _bridge_filename()
    build_output = tmp_path / 'steamworks' / 'steam_net_bridge' / 'build_win64' / 'Release' / _bridge_filename()

    _touch(current)
    _touch(legacy_root)
    _touch(build_output)
    same_time = 1_700_000_000
    for path in (current, legacy_root, build_output):
        os.utime(path, (same_time, same_time))

    results = get_bridge_binaries(tmp_path)

    assert results[0] == str(current)
    assert str(legacy_root) in results
    assert str(build_output) in results


def test_get_bridge_binaries_prefers_current_python_tag_before_legacy_builds(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(sys, 'platform', 'win32')

    current = tmp_path / 'local_artifacts' / 'bridge' / _bridge_filename()
    wrong_python = tmp_path / 'local_artifacts' / 'bridge' / _bridge_filename(_other_python_tag())
    stale_build = tmp_path / 'steamworks' / 'steam_net_bridge' / 'build_win64' / 'Release' / _bridge_filename()

    _touch(wrong_python)
    _touch(stale_build)
    _touch(current)

    results = get_bridge_binaries(tmp_path)

    assert results[0] == str(current)
    assert results.index(str(current)) < results.index(str(stale_build))
    assert results.index(str(current)) < results.index(str(wrong_python))


def test_get_bridge_binaries_prefers_fresh_build_over_stale_local_cache(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(sys, 'platform', 'win32')

    stale_local = tmp_path / 'local_artifacts' / 'bridge' / _bridge_filename()
    fresh_build = tmp_path / 'steamworks' / 'steam_net_bridge' / 'build_win64' / 'Release' / _bridge_filename()

    _touch(stale_local)
    _touch(fresh_build)
    # Make the cache artifact clearly older than the build output.
    stale_time = 1_700_000_000
    fresh_time = stale_time + 3600
    os.utime(stale_local, (stale_time, stale_time))
    os.utime(fresh_build, (fresh_time, fresh_time))

    results = get_bridge_binaries(tmp_path)

    assert results[0] == str(fresh_build)
    assert results.index(str(fresh_build)) < results.index(str(stale_local))
