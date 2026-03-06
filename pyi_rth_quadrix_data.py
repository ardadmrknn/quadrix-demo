"""PyInstaller runtime hook: normalize bundled save root env vars."""

from __future__ import annotations

import os


_DEFAULT_APP_NAME = "quadrix_full"
_LEGACY_DEFAULT_APP_NAME = "tetris_full_edition"


def _get_env(name: str) -> str:
    value = os.environ.get(name, "")
    return value.strip() if isinstance(value, str) else ""


if not _get_env("QUADRIX_APP_NAME"):
    legacy_name = _get_env("TETRIS_APP_NAME")
    if legacy_name and legacy_name != _LEGACY_DEFAULT_APP_NAME:
        os.environ["QUADRIX_APP_NAME"] = legacy_name
    else:
        os.environ["QUADRIX_APP_NAME"] = _DEFAULT_APP_NAME

if not _get_env("QUADRIX_DATA_DIR"):
    legacy_data_dir = _get_env("TETRIS_DATA_DIR")
    if legacy_data_dir:
        os.environ["QUADRIX_DATA_DIR"] = legacy_data_dir