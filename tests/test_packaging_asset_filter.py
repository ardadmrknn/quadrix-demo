# -*- coding: utf-8 -*-
"""tools/packaging_asset_filter.py süzgeci ve demo spec'lerine takılışı.

Demo farkı: ``assets/Tetris.icns`` demo macOS spec'lerinin ``icon=``
parametresinde canlı olduğundan demo spec'leri ``drop_dead_icns=False``
ile çağırır — yalnız promptfont geliştirici dağıtımı (~28,9 MB) düşer.
Kanıt satırları: src/promptfont_support.py:27/:31.
"""

from __future__ import annotations

from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))

from packaging_asset_filter import (  # noqa: E402
    PROMPTFONT_RUNTIME_KEEP,
    filter_datas,
)

ASSETS = ROOT / 'assets'
DEMO_SPECS = [
    'packaging/specs/tetris.spec',
    'packaging/specs/tetris_en.spec',
    'packaging/specs/tetris_playtest.spec',
    'packaging/specs/tetris_macos.spec',
    'packaging/specs/tetris_macos_allinone.spec',
    'packaging/specs/tetris_demo.spec',
    'packaging/specs/tetris_demo_macos_allinone.spec',
]


def _entry(dest: str, src: str = '/nonexistent'):
    return (dest, src, 'd')


def test_promptfont_runtime_seti_pakette_kalir():
    entries = [
        _entry('assets/gamepad_icon/promptfont/promptfont.ttf'),
        _entry('assets/gamepad_icon/promptfont/promptfont.py'),
        _entry('assets/gamepad_icon/promptfont/LICENSE.txt'),
    ]
    kept, _, dropped = filter_datas(entries, drop_dead_icns=False)
    assert kept == entries and dropped == []


def test_promptfont_gelistirici_dagilimi_duser():
    dropped_names = [
        'assets/gamepad_icon/promptfont/promptfont.exe',
        'assets/gamepad_icon/promptfont/promptfont.run',
        'assets/gamepad_icon/promptfont/promptfont.otf',
        'assets/gamepad_icon/promptfont/promptfont.woff',
        'assets/gamepad_icon/promptfont/promptfont.woff2',
        'assets/gamepad_icon/promptfont/editor.js',
        'assets/gamepad_icon/promptfont/index.html',
        'assets/gamepad_icon/promptfont/glyphs.json',
        'assets/gamepad_icon/promptfont/README.md',
        'assets/gamepad_icon/promptfont/tags.txt',
        'assets/gamepad_icon/promptfont/__pycache__/promptfont.cpython-312.pyc',
    ]
    entries = [_entry(n) for n in dropped_names]
    kept, _, dropped = filter_datas(entries, drop_dead_icns=False)
    assert kept == [] and dropped == dropped_names


def test_tetris_icns_demo_modunda_dusmez():
    entries = [_entry('assets/Tetris.icns')]
    kept, _, dropped = filter_datas(entries, drop_dead_icns=False)
    assert kept == entries and dropped == []


def test_gercek_assets_agacinda_olculen_kazanc_araligi():
    entries = []
    for path in sorted(ASSETS.rglob('*')):
        if path.is_file():
            rel = path.relative_to(ROOT).as_posix()  # 'assets/...' — TOC dest yolu
            entries.append((rel, str(path), 'd'))
    for name in PROMPTFONT_RUNTIME_KEEP:
        assert (ASSETS / 'gamepad_icon' / 'promptfont' / name).is_file(), (
            f'runtime seti eksik: {name}'
        )
    kept, dropped_bytes, dropped = filter_datas(entries, drop_dead_icns=False)
    mb = dropped_bytes / (1024 * 1024)
    assert 25.0 < mb < 32.0, f'beklenmedik kazanç bandı: {mb:.1f} MB'
    assert 'assets/Tetris.icns' not in dropped  # demo: icon= parametresinde canlı
    assert all(
        d.startswith('assets/gamepad_icon/promptfont/')
        and d.rsplit('/', 1)[1] not in PROMPTFONT_RUNTIME_KEEP
        for d in dropped
    )
    assert len(kept) == len(entries) - len(dropped)


def test_tum_demo_specleri_suzgeci_cagiriyor():
    for spec_rel in DEMO_SPECS:
        content = (ROOT / spec_rel).read_text(encoding='utf-8')
        assert 'apply_runtime_asset_filter(a, drop_dead_icns=False)' in content, (
            f'{spec_rel}: süzgeç çağrısı yok'
        )
        assert 'tools.packaging_asset_filter' in content
