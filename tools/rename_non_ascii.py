#!/usr/bin/env python3
"""Tüm proje dosya adlarında non-ASCII karakterleri ASCII-safe karşılıklarına çevirir.

Hedef klasörler: assets/, apple_emojis/
Türkçe karakter dönüşüm tablosu uygulanır.
Bozuk (garbled) dosya adları elle eşleme ile düzeltilir.
"""
import os
import sys
import unicodedata
import json

# Windows konsolunda UTF-8 sorunlarını önle
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Türkçe → ASCII dönüşüm tablosu
TR_MAP = str.maketrans({
    'ö': 'o', 'Ö': 'O',
    'ü': 'u', 'Ü': 'U',
    'ğ': 'g', 'Ğ': 'G',
    'ş': 's', 'Ş': 'S',
    'ç': 'c', 'Ç': 'C',
    'ı': 'i', 'İ': 'I',
    'â': 'a', 'Â': 'A',
    'î': 'i', 'Î': 'I',
    'û': 'u', 'Û': 'U',
    'é': 'e', 'É': 'E',
    'è': 'e', 'È': 'E',
    'ê': 'e', 'Ê': 'E',
    'à': 'a', 'À': 'A',
    'ā': 'a',
    'ō': 'o',
    'ū': 'u',
    'ñ': 'n',
})


def has_non_ascii(name: str) -> bool:
    return any(ord(c) > 127 for c in name)


def transliterate(name: str) -> str:
    """Türkçe karakterleri ASCII'ye çevir, kalan non-ASCII'leri Unicode decompose et."""
    result = name.translate(TR_MAP)
    # Kalan non-ASCII → NFD decompose → ASCII base letter al
    cleaned = []
    for ch in result:
        if ord(ch) <= 127:
            cleaned.append(ch)
        else:
            decomposed = unicodedata.normalize('NFD', ch)
            ascii_part = ''.join(c for c in decomposed if ord(c) <= 127)
            if ascii_part:
                cleaned.append(ascii_part)
            else:
                # Tamamen haritalanamayanlar → kaldır
                cleaned.append('')
    return ''.join(cleaned)


def rename_tree(base_dir: str, dry_run: bool = False) -> list[tuple[str, str]]:
    """Klasör ağacında bottomup dolaşıp non-ASCII adları ASCII'ye çevirir.
    
    Returns: list of (old_path, new_path) tuples for renames performed.
    """
    renames = []
    
    # Bottom-up: önce dosyalar, sonra alt klasörler, en son üst klasörler
    for dirpath, dirnames, filenames in os.walk(base_dir, topdown=False):
        # Dosyaları yeniden adlandır
        for fname in filenames:
            if not has_non_ascii(fname):
                continue
            new_name = transliterate(fname)
            if not new_name or new_name == fname:
                continue
            
            old_path = os.path.join(dirpath, fname)
            new_path = os.path.join(dirpath, new_name)
            
            # Çakışma kontrolü
            if os.path.exists(new_path):
                print(f"  SKIP (exists): {old_path} → {new_name}")
                continue
            
            if dry_run:
                print(f"  [DRY] {fname} → {new_name}")
            else:
                os.rename(old_path, new_path)
                print(f"  RENAMED: {fname} → {new_name}")
            renames.append((old_path, new_path))
        
        # Klasörleri yeniden adlandır
        for dname in dirnames:
            if not has_non_ascii(dname):
                continue
            new_name = transliterate(dname)
            if not new_name or new_name == dname:
                continue
            
            old_path = os.path.join(dirpath, dname)
            new_path = os.path.join(dirpath, new_name)
            
            if os.path.exists(new_path):
                print(f"  SKIP (exists): {old_path} → {new_name}")
                continue
            
            if dry_run:
                print(f"  [DRY] {dname}/ → {new_name}/")
            else:
                os.rename(old_path, new_path)
                print(f"  RENAMED: {dname}/ → {new_name}/")
            renames.append((old_path, new_path))
    
    return renames


def main():
    dry_run = '--dry-run' in sys.argv
    
    if dry_run:
        print("=== DRY RUN MODE ===\n")
    
    dirs_to_process = [
        os.path.join(REPO_ROOT, 'assets'),
        os.path.join(REPO_ROOT, 'apple_emojis'),
    ]
    
    all_renames = []
    for d in dirs_to_process:
        if not os.path.isdir(d):
            print(f"SKIP (not found): {d}")
            continue
        print(f"\n{'='*60}")
        print(f"Processing: {d}")
        print(f"{'='*60}")
        renames = rename_tree(d, dry_run=dry_run)
        all_renames.extend(renames)
    
    print(f"\n{'='*60}")
    print(f"Total renames: {len(all_renames)}")
    
    # Eşleme raporunu JSON olarak kaydet
    if all_renames and not dry_run:
        mapping = {}
        for old_p, new_p in all_renames:
            old_rel = os.path.relpath(old_p, REPO_ROOT)
            new_rel = os.path.relpath(new_p, REPO_ROOT)
            mapping[old_rel] = new_rel
        report_path = os.path.join(REPO_ROOT, 'tools', '_rename_report.json')
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(mapping, f, indent=2, ensure_ascii=False)
        print(f"Report saved: {report_path}")


if __name__ == '__main__':
    main()
