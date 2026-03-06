"""User data paths and legacy migration.

Goal: keep user-writable persistence files (settings/users/highscores/achievements)
under a single, stable directory regardless of current working directory.

This module also supports one-time migration from legacy locations.
"""

from __future__ import annotations

import os
import shutil
import sys
from typing import Iterable


_APP_DIR_ENV = "QUADRIX_DATA_DIR"
_LEGACY_APP_DIR_ENV = "TETRIS_DATA_DIR"
_APP_NAME_ENV = "QUADRIX_APP_NAME"
_LEGACY_APP_NAME_ENV = "TETRIS_APP_NAME"
_DEFAULT_APP_NAME = "quadrix_full"
_LEGACY_APP_NAMES = ("tetris_full_edition",)
_CLOUD_DIRNAME = "cloud"
_LOCAL_DIRNAME = "local"
_PROFILES_DIRNAME = "profiles"


def _get_env_override(*names: str) -> str | None:
    for name in names:
        raw = os.getenv(name)
        if not isinstance(raw, str):
            continue
        value = raw.strip()
        if value:
            return value
    return None


def _normalize_app_name(value: str | None) -> str:
    if not isinstance(value, str):
        return _DEFAULT_APP_NAME
    normalized = value.strip()
    return normalized or _DEFAULT_APP_NAME


def _get_legacy_env_app_name() -> str | None:
    legacy_name = _get_env_override(_LEGACY_APP_NAME_ENV)
    if not legacy_name:
        return None
    if _normalize_app_name(legacy_name) in _LEGACY_APP_NAMES:
        return None
    return legacy_name


def get_effective_app_name(app_name: str | None = None) -> str:
    normalized_arg = _normalize_app_name(app_name)
    env_name = _get_env_override(_APP_NAME_ENV) or _get_legacy_env_app_name()

    if env_name and (app_name is None or normalized_arg == _DEFAULT_APP_NAME):
        return _normalize_app_name(env_name)

    return normalized_arg


def _get_platform_data_base_dir() -> str:
    if sys.platform == "win32":
        return os.getenv("APPDATA") or os.getenv("LOCALAPPDATA") or os.path.expanduser("~")
    if sys.platform == "darwin":
        return os.path.expanduser("~/Library/Application Support")
    return os.getenv("XDG_DATA_HOME") or os.path.join(os.path.expanduser("~"), ".local", "share")


def _iter_legacy_app_roots() -> list[str]:
    override = _get_env_override(_APP_DIR_ENV, _LEGACY_APP_DIR_ENV)
    if override:
        return []

    base_dir = _get_platform_data_base_dir()
    candidates: list[str] = []
    for legacy_name in _LEGACY_APP_NAMES:
        normalized = _normalize_app_name(legacy_name)
        if normalized == _DEFAULT_APP_NAME:
            continue
        candidates.append(os.path.join(base_dir, normalized))
    return candidates


def _migrate_legacy_app_root(target_path: str, legacy_roots: Iterable[str]) -> None:
    try:
        if os.path.exists(target_path):
            return
    except Exception:
        return

    target_abs = os.path.abspath(target_path)
    os.makedirs(os.path.dirname(target_abs), exist_ok=True)

    for legacy_root in legacy_roots:
        if not legacy_root:
            continue
        try:
            legacy_abs = os.path.abspath(legacy_root)
            if legacy_abs == target_abs or not os.path.isdir(legacy_abs):
                continue
        except Exception:
            continue

        try:
            os.replace(legacy_abs, target_abs)
            return
        except OSError:
            try:
                shutil.copytree(legacy_abs, target_abs)
                shutil.rmtree(legacy_abs)
                return
            except OSError:
                continue


def get_user_data_dir(app_name: str = _DEFAULT_APP_NAME) -> str:
    override = _get_env_override(_APP_DIR_ENV, _LEGACY_APP_DIR_ENV)
    if override:
        path = os.path.abspath(os.path.expanduser(override))
        os.makedirs(path, exist_ok=True)
        return path

    app_name = get_effective_app_name(app_name)

    base = _get_platform_data_base_dir()
    path = os.path.join(base, app_name)

    if app_name == _DEFAULT_APP_NAME:
        _migrate_legacy_app_root(path, _iter_legacy_app_roots())

    os.makedirs(path, exist_ok=True)
    return path


def get_cloud_data_dir(app_name: str = _DEFAULT_APP_NAME) -> str:
    path = os.path.join(get_user_data_dir(app_name=app_name), _CLOUD_DIRNAME)
    os.makedirs(path, exist_ok=True)
    return path


def get_local_data_dir(app_name: str = _DEFAULT_APP_NAME) -> str:
    path = os.path.join(get_user_data_dir(app_name=app_name), _LOCAL_DIRNAME)
    os.makedirs(path, exist_ok=True)
    return path


def get_profiles_data_dir(app_name: str = _DEFAULT_APP_NAME) -> str:
    path = os.path.join(get_cloud_data_dir(app_name=app_name), _PROFILES_DIRNAME)
    os.makedirs(path, exist_ok=True)
    return path


def get_profile_data_dir(profile_id: str, app_name: str = _DEFAULT_APP_NAME) -> str:
    if not isinstance(profile_id, str) or not profile_id.strip():
        raise ValueError("profile_id is required")
    path = os.path.join(get_profiles_data_dir(app_name=app_name), profile_id.strip())
    os.makedirs(path, exist_ok=True)
    return path


def _resolve_scoped_path(filename: str, base_dir: str) -> str:
    if not isinstance(filename, str) or not filename:
        return filename
    if os.path.isabs(filename) or os.path.dirname(filename):
        return filename
    os.makedirs(base_dir, exist_ok=True)
    return os.path.join(base_dir, filename)


def resolve_cloud_path(filename: str, app_name: str = _DEFAULT_APP_NAME) -> str:
    return _resolve_scoped_path(filename, get_cloud_data_dir(app_name=app_name))


def resolve_local_path(filename: str, app_name: str = _DEFAULT_APP_NAME) -> str:
    return _resolve_scoped_path(filename, get_local_data_dir(app_name=app_name))


def resolve_profile_path(profile_id: str, filename: str, app_name: str = _DEFAULT_APP_NAME) -> str:
    return _resolve_scoped_path(filename, get_profile_data_dir(profile_id, app_name=app_name))


def resolve_data_path(filename: str, app_name: str = _DEFAULT_APP_NAME) -> str:
    """Resolve a bare filename into the unified user data directory.

    If filename is absolute or already contains a directory component, it is
    returned unchanged.
    """
    return resolve_cloud_path(filename, app_name=app_name)


def iter_legacy_paths(bare_filename: str) -> list[str]:
    """Return a best-effort ordered list of legacy locations to check."""
    candidates: list[str] = []

    # Current working directory
    try:
        candidates.append(os.path.abspath(bare_filename))
    except Exception:
        pass

    # Previous unified app-data root (pre cloud/local split)
    try:
        candidates.append(os.path.join(get_user_data_dir(), bare_filename))
    except Exception:
        pass

    legacy_root_candidates = _iter_legacy_app_roots()
    for legacy_root in legacy_root_candidates:
        try:
            candidates.append(os.path.join(legacy_root, bare_filename))
            candidates.append(os.path.join(legacy_root, _CLOUD_DIRNAME, bare_filename))
            candidates.append(os.path.join(legacy_root, _LOCAL_DIRNAME, bare_filename))
        except Exception:
            continue

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
