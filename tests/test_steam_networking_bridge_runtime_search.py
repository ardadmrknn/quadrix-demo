from __future__ import annotations

import os
import sys
from pathlib import Path


def _unload_steam_modules() -> None:
    to_remove = [name for name in sys.modules if 'steam_networking' in name or name == 'steam_net_bridge']
    for name in to_remove:
        del sys.modules[name]


def test_try_import_bridge_finds_build_release_candidate(monkeypatch, tmp_path: Path):
    build_release = tmp_path / 'steamworks' / 'steam_net_bridge' / 'build_win64' / 'Release'
    build_release.mkdir(parents=True, exist_ok=True)
    (build_release / 'steam_net_bridge.py').write_text(
        'class SteamNetBridge:\n'
        '    def init(self):\n'
        '        return True\n'
        '    def get_my_steam_id(self):\n'
        '        return 123\n',
        encoding='utf-8',
    )

    _unload_steam_modules()
    import src.steam_networking as sn

    monkeypatch.setattr(sn, '_get_bridge_search_roots', lambda: [str(tmp_path)])
    monkeypatch.setattr(sn, '_bridge', None)
    monkeypatch.setattr(sn, '_bridge_available', False)
    monkeypatch.setattr(sn, '_bridge_import_attempted', False)

    if sys.platform == 'win32' and hasattr(sn.os, 'add_dll_directory'):
        monkeypatch.setattr(sn.os, 'add_dll_directory', lambda path: object())

    assert sn._try_import_bridge() is True
    assert sn._bridge_available is True

    _unload_steam_modules()


def test_bridge_candidate_dirs_prefer_fresh_current_build_over_stale_cache(monkeypatch, tmp_path: Path):
    stale_cache = tmp_path / 'local_artifacts' / 'bridge'
    fresh_build = tmp_path / 'steamworks' / 'steam_net_bridge' / 'build_win64' / 'Release'
    stale_cache.mkdir(parents=True, exist_ok=True)
    fresh_build.mkdir(parents=True, exist_ok=True)

    bridge_name = f'steam_net_bridge.cp{sys.version_info.major}{sys.version_info.minor}-win_amd64.pyd'
    stale_bridge = stale_cache / bridge_name
    fresh_bridge = fresh_build / bridge_name
    stale_bridge.write_bytes(b'stale')
    fresh_bridge.write_bytes(b'fresh')

    stale_time = 1_700_000_000
    fresh_time = stale_time + 3600
    os.utime(stale_bridge, (stale_time, stale_time))
    os.utime(fresh_bridge, (fresh_time, fresh_time))

    _unload_steam_modules()
    import src.steam_networking as sn

    monkeypatch.setattr(sn, '_get_bridge_search_roots', lambda: [str(tmp_path)])

    candidates = sn._get_bridge_candidate_dirs()

    assert candidates.index(str(fresh_build)) < candidates.index(str(stale_cache))
