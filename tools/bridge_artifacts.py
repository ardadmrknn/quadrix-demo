from __future__ import annotations

import glob
import os
import sys
from pathlib import Path


def _dedupe_paths(paths: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for path in paths:
        normalized = os.path.normpath(str(path))
        if normalized in seen:
            continue
        seen.add(normalized)
        out.append(normalized)
    return out


def _iter_bridge_candidate_dirs(repo_root: str | Path) -> list[str]:
    repo_root = Path(repo_root)
    steam_bridge_dir = repo_root / 'steamworks' / 'steam_net_bridge'

    candidates: list[str] = [
        str(repo_root / 'local_artifacts' / 'bridge'),
        str(repo_root),
        str(repo_root / 'dist'),
    ]

    try:
        candidates.extend(
            str(path)
            for path in sorted(steam_bridge_dir.glob('build*/Release'))
        )
    except Exception:
        pass

    return _dedupe_paths(candidates)


def get_bridge_binary_patterns(repo_root: str | Path) -> list[str]:
    bridge_dirs = _iter_bridge_candidate_dirs(repo_root)
    if sys.platform == 'win32':
        suffixes = ('*.pyd',)
    elif sys.platform == 'darwin':
        suffixes = ('*.so',)
    else:
        suffixes = ('*.pyd', '*.so')

    patterns: list[str] = []
    for bridge_dir in bridge_dirs:
        for suffix in suffixes:
            patterns.append(str(Path(bridge_dir) / f'steam_net_bridge{suffix}'))
    return _dedupe_paths(patterns)


def get_bridge_binaries(repo_root: str | Path) -> list[str]:
    matches: list[str] = []
    for pattern in get_bridge_binary_patterns(repo_root):
        matches.extend(glob.glob(pattern))

    matches = [os.path.normpath(path) for path in matches]
    matches = sorted(set(matches))
    return matches