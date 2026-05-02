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


def _get_current_python_bridge_tags() -> tuple[str, ...]:
    major = sys.version_info.major
    minor = sys.version_info.minor
    return (
        f'cp{major}{minor}',
        f'cpython-{major}{minor}',
    )


def _bridge_binary_mtime(path: str) -> float:
    try:
        return Path(path).stat().st_mtime
    except OSError:
        return 0.0


def _bridge_binary_sort_key(path: str, candidate_dirs: list[str]) -> tuple[int, float, int, str]:
    normalized_path = os.path.normpath(path)
    parent_dir = os.path.normpath(str(Path(normalized_path).parent))
    try:
        candidate_index = candidate_dirs.index(parent_dir)
    except ValueError:
        candidate_index = len(candidate_dirs)

    file_name = Path(normalized_path).name.lower()
    current_python_tags = _get_current_python_bridge_tags()
    python_tag_priority = 0 if any(tag in file_name for tag in current_python_tags) else 1
    # Prefer a fresh current-Python bridge over a stale cached local artifact.
    # local_artifacts/bridge is still the tie-breaker when timestamps match.
    return (python_tag_priority, -_bridge_binary_mtime(path), candidate_index, file_name)


def get_bridge_binaries(repo_root: str | Path) -> list[str]:
    candidate_dirs = _iter_bridge_candidate_dirs(repo_root)
    matches: list[str] = []
    for pattern in get_bridge_binary_patterns(repo_root):
        matches.extend(glob.glob(pattern))

    matches = [os.path.normpath(path) for path in matches]
    matches = sorted(set(matches), key=lambda path: _bridge_binary_sort_key(path, candidate_dirs))
    return matches
