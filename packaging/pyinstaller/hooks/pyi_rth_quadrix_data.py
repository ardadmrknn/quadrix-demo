"""PyInstaller runtime hook: normalize bundled save root env vars."""

from __future__ import annotations

import os


_DEFAULT_APP_NAME = "quadrix_full"
_LEGACY_DEFAULT_APP_NAME = "tetris_full_edition"


def _get_env(name: str) -> str:
    value = os.environ.get(name, "")
    return value.strip() if isinstance(value, str) else ""


def _resolve_default_app_name() -> str:
    for module_name in ("demo_config", "src.demo_config"):
        try:
            module = __import__(module_name, fromlist=["*"])
        except Exception:
            continue

        runtime_name_getter = getattr(module, "get_runtime_app_name", None)
        if callable(runtime_name_getter):
            try:
                resolved = str(runtime_name_getter() or "").strip()
            except Exception:
                resolved = ""
            if resolved:
                return resolved

        if getattr(module, "IS_DEMO", False):
            return str(getattr(module, "DEMO_APP_NAME", _DEFAULT_APP_NAME))

        full_name = str(getattr(module, "FULL_APP_NAME", "") or "").strip()
        if full_name:
            return full_name

    return _DEFAULT_APP_NAME


if not _get_env("QUADRIX_APP_NAME"):
    legacy_name = _get_env("TETRIS_APP_NAME")
    if legacy_name and legacy_name != _LEGACY_DEFAULT_APP_NAME:
        os.environ["QUADRIX_APP_NAME"] = legacy_name
    else:
        os.environ["QUADRIX_APP_NAME"] = _resolve_default_app_name()

if not _get_env("QUADRIX_DATA_DIR"):
    legacy_data_dir = _get_env("TETRIS_DATA_DIR")
    if legacy_data_dir:
        os.environ["QUADRIX_DATA_DIR"] = legacy_data_dir