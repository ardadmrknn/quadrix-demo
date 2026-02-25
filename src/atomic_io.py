"""Atomic, crash-safe file writes.

Primarily used for JSON persistence to avoid corrupted files on partial writes.

Implementation notes:
- Writes to a temporary file in the same directory, then replaces via os.replace.
- On Windows and POSIX, os.replace is atomic w.r.t. the target path.
"""

from __future__ import annotations

import json
import os
import tempfile
from typing import Any


def atomic_write_text(path: str, text: str, *, encoding: str = "utf-8") -> None:
    directory = os.path.dirname(os.path.abspath(path))
    if directory:
        os.makedirs(directory, exist_ok=True)

    base = os.path.basename(path)
    fd = None
    tmp_path = None
    try:
        fd, tmp_path = tempfile.mkstemp(prefix=f".{base}.", suffix=".tmp", dir=directory)
        with os.fdopen(fd, "w", encoding=encoding, newline="\n") as tmp_file:
            fd = None
            tmp_file.write(text)
            tmp_file.flush()
            try:
                os.fsync(tmp_file.fileno())
            except OSError:
                # Some platforms/filesystems may not support fsync.
                pass
        os.replace(tmp_path, path)
        tmp_path = None
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass
        if tmp_path is not None:
            try:
                os.remove(tmp_path)
            except OSError:
                pass


def atomic_write_json(
    path: str,
    data: Any,
    *,
    indent: int | None = 2,
    ensure_ascii: bool = False,
    sort_keys: bool = False,
    encoding: str = "utf-8",
) -> None:
    text = json.dumps(data, indent=indent, ensure_ascii=ensure_ascii, sort_keys=sort_keys)
    # Keep trailing newline like typical json.dump usage.
    atomic_write_text(path, text + "\n", encoding=encoding)
