"""User data paths and legacy migration.

Goal: keep user-writable persistence files (settings/users/highscores/achievements)
under a single, stable directory regardless of current working directory.

This module also supports one-time migration from legacy locations.
"""

from __future__ import annotations

import os
import sys
from typing import Iterable


_APP_DIR_ENV = "TETRIS_DATA_DIR"
_DEFAULT_APP_NAME = "tetris_full_edition"


def get_user_data_dir(app_name: str = _DEFAULT_APP_NAME) -> str:
    override = os.getenv(_APP_DIR_ENV)
    if override:
        path = os.path.abspath(os.path.expanduser(override))
        os.makedirs(path, exist_ok=True)
        return path

    if sys.platform == "win32":
        base = os.getenv("APPDATA") or os.getenv("LOCALAPPDATA") or os.path.expanduser("~")
        path = os.path.join(base, app_name)
    elif sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
        path = os.path.join(base, app_name)
    else:
        base = os.getenv("XDG_DATA_HOME") or os.path.join(os.path.expanduser("~"), ".local", "share")
        path = os.path.join(base, app_name)

    os.makedirs(path, exist_ok=True)
    return path


def resolve_data_path(filename: str, app_name: str = _DEFAULT_APP_NAME) -> str:
    """Resolve a bare filename into the unified user data directory.

    If filename is absolute or already contains a directory component, it is
    returned unchanged.
    """
    if not isinstance(filename, str) or not filename:
        return filename
    if os.path.isabs(filename) or os.path.dirname(filename):
        return filename
    return os.path.join(get_user_data_dir(app_name=app_name), filename)


def iter_legacy_paths(bare_filename: str) -> list[str]:
    """Return a best-effort ordered list of legacy locations to check."""
    candidates: list[str] = []

    # Current working directory
    try:
        candidates.append(os.path.abspath(bare_filename))
    except Exception:
        pass

    # Project root (parent of src/) when running from source
    try:
        src_dir = os.path.dirname(__file__)
        project_root = os.path.abspath(os.path.join(src_dir, os.pardir))
        candidates.append(os.path.join(project_root, bare_filename))
        candidates.append(os.path.join(project_root, "src", bare_filename))
    except Exception:
        pass

    # PyInstaller: historical behavior stored next to the executable
    try:
        if getattr(sys, "frozen", False):
            exe_dir = os.path.dirname(sys.executable)
            candidates.append(os.path.join(exe_dir, bare_filename))
    except Exception:
        pass

    # De-dup while preserving order
    seen: set[str] = set()
    out: list[str] = []
    for p in candidates:
        if p and p not in seen:
            seen.add(p)
            out.append(p)
    return out


def migrate_legacy_file(target_path: str, legacy_paths: Iterable[str]) -> bool:
    """Move/copy a legacy file into target_path if target doesn't exist.

    Returns True if migration occurred.
    """
    try:
        if os.path.exists(target_path):
            return False
    except Exception:
        return False

    for legacy in legacy_paths:
        if not legacy:
            continue
        try:
            if not os.path.exists(legacy):
                continue
        except Exception:
            continue

        os.makedirs(os.path.dirname(os.path.abspath(target_path)), exist_ok=True)
        try:
            os.replace(legacy, target_path)
            return True
        except OSError:
            # Cross-device move or permission differences; fall back to copy+remove.
            try:
                import shutil

                shutil.copy2(legacy, target_path)
                try:
                    os.remove(legacy)
                except OSError:
                    pass
                return True
            except OSError:
                return False

    return False
