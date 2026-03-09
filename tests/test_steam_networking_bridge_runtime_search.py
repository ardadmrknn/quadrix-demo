from __future__ import annotations

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

    monkeypatch.setattr(sn, '_bridge', None)
    monkeypatch.setattr(sn, '_bridge_available', False)
    monkeypatch.setattr(sn, '_bridge_import_attempted', False)
    monkeypatch.setattr(sn, '_get_bridge_search_roots', lambda: [str(tmp_path)])

    if sys.platform == 'win32' and hasattr(sn.os, 'add_dll_directory'):
        monkeypatch.setattr(sn.os, 'add_dll_directory', lambda path: object())

    assert sn._try_import_bridge() is True
    assert sn._bridge_available is True

    _unload_steam_modules()