from __future__ import annotations

import glob
import os
import sys
from pathlib import Path


def get_bridge_binary_patterns(repo_root: str | Path) -> list[str]:
    repo_root = Path(repo_root)
    bridge_dir = repo_root / 'local_artifacts' / 'bridge'
    if sys.platform == 'win32':
        return [str(bridge_dir / 'steam_net_bridge*.pyd')]
    if sys.platform == 'darwin':
        return [str(bridge_dir / 'steam_net_bridge*.so')]
    return [
        str(bridge_dir / 'steam_net_bridge*.pyd'),
        str(bridge_dir / 'steam_net_bridge*.so'),
    ]


def get_bridge_binaries(repo_root: str | Path) -> list[str]:
    matches: list[str] = []
    for pattern in get_bridge_binary_patterns(repo_root):
        matches.extend(glob.glob(pattern))

    matches = [os.path.normpath(path) for path in matches]
    matches = sorted(set(matches))
    return matches