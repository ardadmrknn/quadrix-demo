"""Frozen ve kaynak koşular için tek build kimliği kaynağı (G-03).

Frozen paketlerde telemetri JSONL kayıtları hangi commit/build'den
üretildiğini taşımalı (rapor §10: "frozen JSONL kayıtlarında commit/build
kimliği yok"). Bu modül o kimliği çözer:

- Frozen: çalıştırılabilirin yanındaki ``quadrix_build_identity.json``
  (derleme script'leri / ``tools/write_build_identity.py`` yazar).
- Kaynak koşu: repo kökünde git HEAD (tek, timeout'lu subprocess).
- İkisi de yoksa: ``unknown`` değerler.

Yalnız stdlib kullanır; pygame/data_paths gibi ağır importlar YASAK (startup
maliyeti ve import zinciri riski). Hiçbir yol istisna fırlatmaz — telemetri
kaydı kimlik yüzünden asla düşmez.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time

_IDENTITY_FILENAME = "quadrix_build_identity.json"
_UNKNOWN = "unknown"
_GIT_TIMEOUT_S = 2.0

_identity_cache: dict | None = None


def _unknown_identity() -> dict:
    return {
        "git_commit": _UNKNOWN,
        "git_commit_time": _UNKNOWN,
        "build_time": _UNKNOWN,
        "app_version": _UNKNOWN,
        "build_number": _UNKNOWN,
        "identity_source": _UNKNOWN,
    }


def _read_identity_file(exe_dir: str) -> dict | None:
    path = os.path.join(exe_dir, _IDENTITY_FILENAME)
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return None


def _git_identity(repo_root: str) -> dict:
    """repo_root'ta HEAD commit hash'i ve commit zamanı (ISO)."""
    try:
        proc = subprocess.run(
            ["git", "log", "-1", "--format=%H%n%cI"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT_S,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            lines = proc.stdout.strip().splitlines()
            commit = lines[0].strip()
            commit_time = lines[1].strip() if len(lines) > 1 else _UNKNOWN
            if commit:
                return {"git_commit": commit, "git_commit_time": commit_time}
    except Exception:
        pass
    return {"git_commit": _UNKNOWN, "git_commit_time": _UNKNOWN}


def _version_info() -> tuple[str, str]:
    try:
        import version_base
        return (
            str(getattr(version_base, "VERSION", _UNKNOWN)),
            str(getattr(version_base, "BUILD_NUMBER", _UNKNOWN)),
        )
    except Exception:
        return (_UNKNOWN, _UNKNOWN)


def _default_repo_root() -> str | None:
    try:
        # Bu dosya <repo>/src/build_identity.py konumundadır.
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    except Exception:
        return None


def resolve_identity(
    exe_dir: str | None = None,
    repo_root: str | None = None,
) -> dict:
    """Build kimliğini çöz (test edilebilir açık parametrelerle).

    ``exe_dir`` verilmezse frozen koşuda çalıştırılabilir dizini kullanılır.
    ``repo_root`` verilmezse kaynak koşuda bu modülün repo kökü kullanılır.
    """
    try:
        if exe_dir is None and getattr(sys, "frozen", False):
            exe_dir = os.path.dirname(sys.executable)
        if repo_root is None and not getattr(sys, "frozen", False):
            repo_root = _default_repo_root()

        if exe_dir:
            data = _read_identity_file(exe_dir)
            if data is not None:
                app_version, build_number = _version_info()
                return {
                    "git_commit": str(data.get("git_commit", _UNKNOWN) or _UNKNOWN),
                    "git_commit_time": str(data.get("git_commit_time", _UNKNOWN) or _UNKNOWN),
                    "build_time": str(data.get("build_time", _UNKNOWN) or _UNKNOWN),
                    "app_version": str(data.get("app_version", app_version) or app_version),
                    "build_number": str(data.get("build_number", build_number) or build_number),
                    "identity_source": "file",
                }

        if repo_root and os.path.isdir(repo_root):
            git = _git_identity(repo_root)
            if git["git_commit"] != _UNKNOWN:
                app_version, build_number = _version_info()
                return {
                    "git_commit": git["git_commit"],
                    "git_commit_time": git["git_commit_time"],
                    "build_time": _UNKNOWN,
                    "app_version": app_version,
                    "build_number": build_number,
                    "identity_source": "git",
                }
    except Exception:
        pass
    return _unknown_identity()


def write_identity_file(
    target_dir: str,
    *,
    repo_root: str | None = None,
    spec_file: str = "",
    built_by: str = "",
) -> str:
    """Kimlik dosyasını hedef dizine yaz ve yolunu döndür.

    Derleme script'leri (PS1/sh) ve manuel akış (demo Windows) bu fonksiyonu
    ``tools/write_build_identity.py`` üzerinden çağırır — tek yazma kaynağı.
    """
    if repo_root is None:
        repo_root = _default_repo_root()
    git = _git_identity(repo_root) if repo_root else {
        "git_commit": _UNKNOWN,
        "git_commit_time": _UNKNOWN,
    }
    app_version, build_number = _version_info()
    payload = {
        "schema": 1,
        "git_commit": git["git_commit"],
        "git_commit_time": git["git_commit_time"],
        "build_time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "app_version": app_version,
        "build_number": build_number,
        "spec_file": str(spec_file or ""),
        "built_by": str(built_by or ""),
    }
    os.makedirs(target_dir, exist_ok=True)
    path = os.path.join(target_dir, _IDENTITY_FILENAME)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False, sort_keys=True)
        fh.write("\n")
    return path


def get_identity() -> dict:
    """Cache'lenmiş kimlik (record_startup bir kez çözer, sonra sıfır maliyet)."""
    global _identity_cache
    if _identity_cache is None:
        try:
            _identity_cache = resolve_identity()
        except Exception:
            _identity_cache = _unknown_identity()
    return dict(_identity_cache)
