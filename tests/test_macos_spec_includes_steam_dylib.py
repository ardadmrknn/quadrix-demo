"""
tests/test_macos_spec_includes_steam_dylib.py
---------------------------------------------
Spec dosyalarının Steam binary'lerini doğru şekilde içerdiğini doğrular:
  - macOS spec'leri: libsteam_api.dylib referansı
  - Windows spec'leri: steam_api64.dll / dll/win64 referansı
  - Tüm spec'ler: Python olarak parse edilebilir (syntax hatası yok)
"""

import pathlib
import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent


def _read_spec(name: str) -> str:
    path = REPO_ROOT / 'packaging' / 'specs' / name
    return path.read_text(encoding="utf-8")


# ── macOS spec'leri: libsteam_api.dylib ─────────────────────────────────────

def test_tetris_macos_spec_includes_steam_dylib():
    """tetris_macos.spec, libsteam_api.dylib içermeli."""
    content = _read_spec("tetris_macos.spec")
    assert "libsteam_api.dylib" in content, (
        "tetris_macos.spec 'libsteam_api.dylib' referansı içermiyor"
    )


def test_tetris_macos_allinone_spec_includes_steam_dylib():
    """tetris_macos_allinone.spec, libsteam_api.dylib içermeli."""
    content = _read_spec("tetris_macos_allinone.spec")
    assert "libsteam_api.dylib" in content, (
        "tetris_macos_allinone.spec 'libsteam_api.dylib' referansı içermiyor"
    )


def test_tetris_playtest_spec_includes_steam_dylib():
    """tetris_playtest.spec, libsteam_api.dylib içermeli (cross-platform build)."""
    content = _read_spec("tetris_playtest.spec")
    assert "libsteam_api.dylib" in content, (
        "tetris_playtest.spec 'libsteam_api.dylib' referansı içermiyor; "
        "macOS playtest build'i için dll/osx/libsteam_api.dylib binaries'e eklenmiş olmalı"
    )


# ── Windows spec'leri: steam_api64.dll / dll/win64 ──────────────────────────

def test_windows_spec_references_steam_dll():
    """tetris.spec, steam_api64.dll veya dll/win64 referansı içermeli."""
    content = _read_spec("tetris.spec")
    assert "steam_api64.dll" in content or "dll/win64" in content, (
        "tetris.spec 'steam_api64.dll' veya 'dll/win64' referansı içermiyor"
    )


def test_tetris_en_spec_references_steam_dll():
    """tetris_en.spec, steam_api64.dll veya dll/win64 referansı içermeli."""
    content = _read_spec("tetris_en.spec")
    assert "steam_api64.dll" in content or "dll/win64" in content, (
        "tetris_en.spec 'steam_api64.dll' veya 'dll/win64' referansı içermiyor"
    )


# ── Syntax kontrolü: tüm spec'ler Python olarak parse edilebilmeli ───────────

SPEC_FILES = [
    "tetris_macos.spec",
    "tetris_macos_allinone.spec",
    "tetris_playtest.spec",
    "tetris.spec",
    "tetris_en.spec",
]


@pytest.mark.parametrize("spec_name", SPEC_FILES)
def test_specs_include_quadrix_data_runtime_hook(spec_name):
    content = _read_spec(spec_name)
    assert "pyi_rth_quadrix_data.py" in content, (
        f"{spec_name} quadrix save-path runtime hook'unu icermiyor"
    )


@pytest.mark.parametrize("spec_name", SPEC_FILES)
def test_specs_are_parseable_python(spec_name):
    """Her spec dosyası compile() ile syntax hatası olmadan parse edilebilmeli."""
    path = REPO_ROOT / 'packaging' / 'specs' / spec_name
    source = path.read_text(encoding="utf-8")
    try:
        compile(source, spec_name, "exec")
    except SyntaxError as exc:
        pytest.fail(
            f"{spec_name} Python olarak parse edilemedi: {exc}"
        )
