"""Font glyph kapsam (coverage) tespiti.

Bir font dosyasının hangi Unicode kod noktalarını gerçekten içerdiğini
(cmap tablosuna göre) belirler. Bu, eksik glyph'lerin ".notdef" kutusu
(tofu) olarak çizilmesini önlemek için yedek (fallback) font seçiminde
kullanılır.

Tespit önceliği:
  1) fontTools (varsa) — en güvenilir.
  2) Dahili minimal cmap ayrıştırıcı (format 4 ve 12) — bağımlılık gerektirmez.

Kapsam belirlenemezse None döner; çağıran taraf bunu "kapsanıyor varsay"
olarak ele alır (gereksiz fallback'i önlemek için).
"""

from __future__ import annotations

import os
import struct
import threading

# path -> (mtime, frozenset[int] | None)
_COVERAGE_CACHE: dict[str, tuple[float, frozenset | None]] = {}
_LOCK = threading.Lock()


def _coverage_via_fonttools(path: str) -> frozenset | None:
    try:
        from fontTools.ttLib import TTFont
    except Exception:
        return None
    try:
        font = TTFont(path, lazy=True, fontNumber=0)
        try:
            best = font.getBestCmap()  # {codepoint: glyphName}
            if best:
                return frozenset(best.keys())
            # getBestCmap bazı fontlarda boş dönebilir; tüm cmap tablolarını birleştir
            cps: set[int] = set()
            for table in font["cmap"].tables:
                try:
                    if table.isUnicode():
                        cps.update(table.cmap.keys())
                except Exception:
                    continue
            return frozenset(cps) if cps else None
        finally:
            font.close()
    except Exception:
        return None


def _read_u16(data: bytes, off: int) -> int:
    return struct.unpack_from(">H", data, off)[0]


def _read_u32(data: bytes, off: int) -> int:
    return struct.unpack_from(">I", data, off)[0]


def _parse_format4(data: bytes, off: int, out: set[int]) -> None:
    seg_x2 = _read_u16(data, off + 6)
    seg_count = seg_x2 // 2
    end_off = off + 14
    start_off = end_off + seg_x2 + 2  # +2 reservedPad
    delta_off = start_off + seg_x2
    range_off = delta_off + seg_x2
    for i in range(seg_count):
        end_code = _read_u16(data, end_off + i * 2)
        start_code = _read_u16(data, start_off + i * 2)
        if start_code > end_code:
            continue
        id_delta = _read_u16(data, delta_off + i * 2)
        id_range_offset = _read_u16(data, range_off + i * 2)
        for c in range(start_code, end_code + 1):
            if c == 0xFFFF:
                continue
            if id_range_offset == 0:
                gid = (c + id_delta) & 0xFFFF
            else:
                glyph_index_off = range_off + i * 2 + id_range_offset + (c - start_code) * 2
                if glyph_index_off + 2 > len(data):
                    continue
                gid = _read_u16(data, glyph_index_off)
                if gid != 0:
                    gid = (gid + id_delta) & 0xFFFF
            if gid != 0:
                out.add(c)


def _parse_format12(data: bytes, off: int, out: set[int]) -> None:
    n_groups = _read_u32(data, off + 12)
    grp_off = off + 16
    for g in range(n_groups):
        base = grp_off + g * 12
        if base + 12 > len(data):
            break
        start_char = _read_u32(data, base)
        end_char = _read_u32(data, base + 4)
        if start_char > end_char or (end_char - start_char) > 0x110000:
            continue
        for c in range(start_char, end_char + 1):
            out.add(c)


def _coverage_via_manual(path: str) -> frozenset | None:
    try:
        with open(path, "rb") as handle:
            data = handle.read()
    except Exception:
        return None
    try:
        if len(data) < 12:
            return None
        tag = data[:4]
        # TrueType Collection: ilk fontun offset tablosuna git
        if tag == b"ttcf":
            first_off = _read_u32(data, 12)
        else:
            first_off = 0

        num_tables = _read_u16(data, first_off + 4)
        record_off = first_off + 12
        cmap_off = None
        for i in range(num_tables):
            rec = record_off + i * 16
            if data[rec:rec + 4] == b"cmap":
                cmap_off = _read_u32(data, rec + 8)
                break
        if cmap_off is None:
            return None

        sub_count = _read_u16(data, cmap_off + 2)
        # Unicode alt tabloları topla; format 12 > format 4 önceliği
        candidates: list[tuple[int, int]] = []  # (priority, subtable_offset)
        for i in range(sub_count):
            rec = cmap_off + 4 + i * 8
            platform_id = _read_u16(data, rec)
            encoding_id = _read_u16(data, rec + 2)
            sub_off = cmap_off + _read_u32(data, rec + 4)
            if sub_off + 2 > len(data):
                continue
            is_unicode = (
                platform_id == 0
                or (platform_id == 3 and encoding_id in (1, 10))
            )
            if not is_unicode:
                continue
            fmt = _read_u16(data, sub_off)
            if fmt == 12:
                candidates.append((2, sub_off))
            elif fmt == 4:
                candidates.append((1, sub_off))

        if not candidates:
            return None

        out: set[int] = set()
        for _prio, sub_off in sorted(candidates, key=lambda t: t[0], reverse=True):
            fmt = _read_u16(data, sub_off)
            if fmt == 12:
                _parse_format12(data, sub_off, out)
            elif fmt == 4:
                _parse_format4(data, sub_off, out)
            if out:
                break
        return frozenset(out) if out else None
    except Exception:
        return None


def supported_codepoints(path: str) -> frozenset | None:
    """Font dosyasının desteklediği kod noktaları kümesi (cache'li).

    Belirlenemezse None döner.
    """
    if not path:
        return None
    try:
        mtime = os.path.getmtime(path)
    except Exception:
        mtime = 0.0
    with _LOCK:
        cached = _COVERAGE_CACHE.get(path)
        if cached is not None and cached[0] == mtime:
            return cached[1]
    cps = _coverage_via_fonttools(path)
    if cps is None:
        cps = _coverage_via_manual(path)
    with _LOCK:
        _COVERAGE_CACHE[path] = (mtime, cps)
    return cps


def font_covers(path: str, codepoint: int) -> bool:
    """Font verilen kod noktasını içeriyor mu?

    Kapsam belirlenemezse True döner (gereksiz fallback'i önlemek için).
    """
    cps = supported_codepoints(path)
    if cps is None:
        return True
    return codepoint in cps
