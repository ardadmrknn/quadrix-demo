# -*- coding: utf-8 -*-
"""Build kimliği dosyası yazıcı (G-03).

Derleme script'leri ve manuel akışlar için tek komut:

    python tools/write_build_identity.py --target-dir <çalıştırılabilir dizini> \
        [--repo-root <repo>] [--spec-file <spec>] [--built-by <ad>]

Örnekler:
    # v2 Windows (build_windows_exe.ps1 çağırır):
    py tools/write_build_identity.py --target-dir dist --built-by windows_ps1
    # macOS .app (build_macos_app.sh çağırır):
    python3 tools/write_build_identity.py --target-dir "dist/Quadrix.app/Contents/MacOS" --built-by macos_sh
    # Demo Windows (manuel adım — DERLEME_VE_YAYINLAMA_REHBERI):
    py tools/write_build_identity.py --target-dir dist --built-by demo_manual

Çıktı: quadrix_build_identity.json (çalıştırılabilirin yanında; Steam
ContentRoot'a girer). Kimlik çözümlemesi src/build_identity.py'dedir.
"""
from __future__ import annotations

import argparse
import pathlib
import sys

ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / 'src'
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import build_identity  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description='quadrix_build_identity.json yazar (G-03 build kimligi).')
    parser.add_argument(
        '--target-dir', required=True,
        help='Kimlik dosyasinin yazilacagi dizin (calistirilabilirin yanina).')
    parser.add_argument(
        '--repo-root', default=str(ROOT_DIR),
        help='git HEAD cozumlemesi icin repo koku (varsayilan: bu repo).')
    parser.add_argument(
        '--spec-file', default='',
        help='Derlemede kullanilan spec dosyasi (kayit amaclari).')
    parser.add_argument(
        '--built-by', default='manual',
        help='Kimligi yazan akisin adi (script/manual).')
    args = parser.parse_args(argv)

    path = build_identity.write_identity_file(
        args.target_dir,
        repo_root=args.repo_root,
        spec_file=args.spec_file,
        built_by=args.built_by,
    )
    print(f'[OK] build kimligi yazildi: {path}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
