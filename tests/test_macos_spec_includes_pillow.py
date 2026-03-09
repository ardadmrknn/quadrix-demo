"""
Test: tetris_macos_allinone.spec excludes listesinde PIL/Pillow olmamalı
"""
import pathlib
import re


SPEC_PATH = pathlib.Path(__file__).parent.parent / 'packaging' / 'specs' / 'tetris_macos_allinone.spec'


def _parse_excludes(text: str) -> list[str]:
    """spec dosyasındaki excludes=[...] bloğunu parse et."""
    # excludes=[ ... ] bloğunu bul
    match = re.search(r'excludes\s*=\s*\[([^\]]*)\]', text, re.DOTALL)
    if not match:
        return []
    block = match.group(1)
    # Her 'item' veya "item" satırını bul
    items = re.findall(r"['\"]([^'\"]+)['\"]", block)
    return items


def test_pil_not_in_excludes():
    text = SPEC_PATH.read_text(encoding='utf-8')
    excludes = _parse_excludes(text)
    assert 'PIL' not in excludes, f"'PIL' hâlâ excludes içinde: {excludes}"


def test_pillow_not_in_excludes():
    text = SPEC_PATH.read_text(encoding='utf-8')
    excludes = _parse_excludes(text)
    assert 'Pillow' not in excludes, f"'Pillow' hâlâ excludes içinde: {excludes}"