from __future__ import annotations

import importlib.util
import re
from pathlib import Path


LOCAL_VERSION_FILES = {
    'windows': 'version_local_windows.py',
}


def _load_module_from_path(module_name: str, file_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f'Modul yuklenemedi: {file_path}')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _parse_version(version: str) -> tuple[int, int, int]:
    match = re.fullmatch(r'(\d+)\.(\d+)\.(\d+)', str(version).strip())
    if not match:
        raise ValueError(f'Gecersiz surum formati: {version!r}')
    return tuple(int(part) for part in match.groups())


def _select_seed_version(
    base_version: str,
    base_build: int,
    local_version: str | None,
    local_build: int | None,
) -> tuple[str, int]:
    if not local_version or local_build is None:
        return base_version, base_build

    if _parse_version(local_version) < _parse_version(base_version):
        return base_version, base_build

    return local_version, local_build


def _render_version_module(version: str, build_number: int, platform_name: str) -> str:
    header = (
        '# Bu dosya build sirasinda lokal olarak guncellenir.\n'
        '# Git reposuna eklenmez; platforma ozel build numarasi burada tutulur.\n\n'
    )

    return (
        header
        + f'PLATFORM = "{platform_name}"\n'
        + f'VERSION = "{version}"\n'
        + f'BUILD_NUMBER = {build_number}\n'
    )


def bump_platform_version(repo_root: str | Path, platform_name: str) -> tuple[str, int, Path]:
    repo_root = Path(repo_root)
    src_dir = repo_root / 'src'
    base_module = _load_module_from_path('version_base_build', src_dir / 'version_base.py')

    base_version = str(getattr(base_module, 'VERSION'))
    base_build = int(getattr(base_module, 'BUILD_NUMBER'))

    try:
        local_filename = LOCAL_VERSION_FILES[platform_name]
    except KeyError as exc:
        raise ValueError(f'Desteklenmeyen platform anahtari: {platform_name}') from exc

    local_path = src_dir / local_filename
    local_version = None
    local_build = None
    if local_path.exists():
        local_module = _load_module_from_path(f'{platform_name}_local_version', local_path)
        local_version = str(getattr(local_module, 'VERSION', ''))
        try:
            local_build = int(getattr(local_module, 'BUILD_NUMBER'))
        except (TypeError, ValueError):
            local_build = None

    seed_version, seed_build = _select_seed_version(
        base_version,
        base_build,
        local_version,
        local_build,
    )

    major, minor, patch = _parse_version(seed_version)
    new_patch = patch + 1
    new_build = max(seed_build, patch) + 1
    new_version = f'{major}.{minor}.{new_patch}'

    local_path.write_text(
        _render_version_module(new_version, new_build, platform_name),
        encoding='utf-8',
    )
    return new_version, new_build, local_path