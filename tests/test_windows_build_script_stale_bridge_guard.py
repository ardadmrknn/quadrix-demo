from __future__ import annotations

import pathlib


ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
SCRIPT_PATH = ROOT_DIR / 'scripts' / 'build' / 'build_windows_exe.ps1'


def test_windows_build_script_detects_stale_bridge_sources() -> None:
    content = SCRIPT_PATH.read_text(encoding='utf-8')

    assert 'function Test-BridgeArtifactsStale' in content
    assert "steamworks\\steam_net_bridge\\steam_net_bridge.cpp" in content
    assert "steamworks\\steam_net_bridge\\build.bat" in content
    assert 'if (-not $RebuildBridge -and $bridgeExists -and (Test-BridgeArtifactsStale))' in content
    assert 'Bridge kaynak dosyalari artefactlerden daha yeni, rebuild zorlanacak...' in content