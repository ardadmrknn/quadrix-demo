# -*- coding: utf-8 -*-
"""G-03: build kimliği sözleşmesi (G dalgası).

`src/build_identity.py` frozen ve kaynak koşular için tek kimlik kaynağıdır:
frozen → çalıştırılabilirin yanındaki `quadrix_build_identity.json`;
kaynak → repo kökünde git HEAD; ikisi de yoksa unknown. `record_startup`
payload'ı kimlik alanlarını taşır (frozen JSONL kaydı commit/build ile
ilişkilendirilebilir — rapor §10'un "commit/build kimliği yok" sınırı).

Modül importları gövde içinde (koleksiyon-runtime sys.modules kimlik bölünmesi
dersi).
"""
from __future__ import annotations

import os
import pathlib
import subprocess
import sys
import tempfile

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / 'src'
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


def _git_head(repo_root: str) -> str:
    proc = subprocess.run(
        ['git', 'rev-parse', 'HEAD'],
        cwd=repo_root, capture_output=True, text=True, timeout=10,
    )
    return proc.stdout.strip()


def test_write_and_resolve_file_identity():
    """Yazılan kimlik dosyası frozen çözümlemede 'file' kaynağıyla döner."""
    import build_identity

    with tempfile.TemporaryDirectory(prefix='quadrix_g03_file_') as target:
        path = build_identity.write_identity_file(
            target, repo_root=str(ROOT_DIR),
            spec_file='packaging/specs/tetris.spec',
            built_by='tests',
        )
        assert os.path.isfile(path)
        assert os.path.basename(path) == 'quadrix_build_identity.json'

        identity = build_identity.resolve_identity(exe_dir=target)
        assert identity['identity_source'] == 'file'
        assert identity['git_commit'] == _git_head(str(ROOT_DIR))
        assert identity['app_version'] == '1.0.48'
        assert identity['build_number'] == '48'
        assert identity['build_time']  # boş olmayan ISO damga
        assert identity['git_commit_time']


def test_resolve_git_source_from_explicit_repo():
    """Kaynak koşu: kimlik dosyası yoksa git HEAD'ten çözülür."""
    import build_identity

    with tempfile.TemporaryDirectory(prefix='quadrix_g03_git_') as gitrepo, \
            tempfile.TemporaryDirectory(prefix='quadrix_g03_empty_') as empty:
        subprocess.run(['git', 'init', '-q'], cwd=gitrepo, check=True,
                       capture_output=True, timeout=10)
        subprocess.run(
            ['git', '-c', 'user.email=t@t', '-c', 'user.name=t',
             'commit', '--allow-empty', '-m', 'g03', '-q'],
            cwd=gitrepo, check=True, capture_output=True, timeout=10,
        )
        # exe_dir boş (kimlik dosyası yok) → git kaynağı.
        identity = build_identity.resolve_identity(
            exe_dir=empty, repo_root=gitrepo)
        assert identity['identity_source'] == 'git'
        assert identity['git_commit'] == _git_head(gitrepo)
        assert identity['app_version'] == '1.0.48'


def test_resolve_unknown_without_sources():
    """Ne dosya ne git: tüm alanlar unknown, kaynak unknown."""
    import build_identity

    with tempfile.TemporaryDirectory(prefix='quadrix_g03_none_') as empty:
        identity = build_identity.resolve_identity(
            exe_dir=empty, repo_root=empty)
        assert identity['identity_source'] == 'unknown'
        assert identity['git_commit'] == 'unknown'
        assert identity['git_commit_time'] == 'unknown'


def test_record_startup_includes_identity_fields():
    """record_startup payload'ı kimlik alanlarını taşır (kaynak koşu → git)."""
    import build_identity
    import perf_telemetry as pt

    captured = {}

    def _capture(event):
        captured.update(event)

    build_identity._identity_cache = None
    # Demo telemetrisi opt-in: record_startup kapıda is_enabled'e takılır —
    # test izolasyonu için cache'i açık stub'la (v2'de bu kapı yoktur).
    _saved_enabled = getattr(pt, '_enabled_cache', None)
    pt._enabled_cache = True
    pt._write_event = _capture
    try:
        pt.record_startup(backend='test')
    finally:
        pt._write_event = None
        del pt._write_event
        pt._enabled_cache = _saved_enabled
        build_identity._identity_cache = None

    assert captured.get('type') == 'startup'
    assert captured.get('identity_source') == 'git'
    assert len(str(captured.get('git_commit', ''))) == 40
    assert captured.get('app_version') == '1.0.48'
    assert 'build_number' in captured
    assert 'build_time' in captured
    assert 'git_commit_time' in captured


def test_get_identity_survives_resolver_failure_and_caches():
    """resolve çökse bile get_identity unknown döner; sonuç cache'lenir."""
    import build_identity

    calls = {'n': 0}

    def _exploding():
        calls['n'] += 1
        raise RuntimeError('boom')

    build_identity._identity_cache = None
    saved = build_identity.resolve_identity
    build_identity.resolve_identity = _exploding
    try:
        first = build_identity.get_identity()
        second = build_identity.get_identity()
    finally:
        build_identity.resolve_identity = saved
        build_identity._identity_cache = None

    assert first['identity_source'] == 'unknown'
    assert second == first
    assert calls['n'] == 1, "kimlik bir kez cozulup cache'lenmeli"
