from __future__ import annotations

import importlib.util
import pathlib
import sys
import tempfile


ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from tools.versioning import bump_platform_version


def _load_module(file_path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(file_path.stem, file_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_bump_platform_version_creates_local_windows_override():
    with tempfile.TemporaryDirectory() as tmp:
        repo_root = pathlib.Path(tmp)
        src_dir = repo_root / 'src'
        src_dir.mkdir(parents=True, exist_ok=True)
        (src_dir / 'version_base.py').write_text(
            'VERSION = "1.0.48"\nBUILD_NUMBER = 48\n',
            encoding='utf-8',
        )

        version, build_number, local_file = bump_platform_version(repo_root, 'windows')
        local_module = _load_module(local_file)

        assert local_file.name == 'version_local_windows.py'
        assert version == '1.0.49'
        assert build_number == 49
        assert local_module.VERSION == '1.0.49'
        assert local_module.BUILD_NUMBER == 49
        assert local_module.PLATFORM == 'windows'


def test_bump_platform_version_resets_to_newer_base_when_local_is_older():
    with tempfile.TemporaryDirectory() as tmp:
        repo_root = pathlib.Path(tmp)
        src_dir = repo_root / 'src'
        src_dir.mkdir(parents=True, exist_ok=True)
        (src_dir / 'version_base.py').write_text(
            'VERSION = "1.0.60"\nBUILD_NUMBER = 60\n',
            encoding='utf-8',
        )
        (src_dir / 'version_local_windows.py').write_text(
            'PLATFORM = "windows"\nVERSION = "1.0.55"\nBUILD_NUMBER = 55\n',
            encoding='utf-8',
        )

        version, build_number, local_file = bump_platform_version(repo_root, 'windows')
        local_module = _load_module(local_file)

        assert version == '1.0.61'
        assert build_number == 61
        assert local_module.VERSION == '1.0.61'
        assert local_module.BUILD_NUMBER == 61
        assert local_module.PLATFORM == 'windows'

        local_text = local_file.read_text(encoding='utf-8')
        assert 'build sirasinda lokal olarak guncellenir.' in local_text
        assert 'git update-index --skip-worktree' not in local_text
        assert 'Git reposuna eklenmez; platforma ozel build numarasi burada tutulur.' in local_text


def test_bump_platform_version_rejects_unsupported_platform():
    with tempfile.TemporaryDirectory() as tmp:
        repo_root = pathlib.Path(tmp)
        src_dir = repo_root / 'src'
        src_dir.mkdir(parents=True, exist_ok=True)
        (src_dir / 'version_base.py').write_text(
            'VERSION = "1.0.48"\nBUILD_NUMBER = 48\n',
            encoding='utf-8',
        )

        try:
            bump_platform_version(repo_root, 'macos')
        except ValueError as exc:
            assert 'Desteklenmeyen platform anahtari' in str(exc)
        else:
            raise AssertionError('macos artik desteklenmemeli')
