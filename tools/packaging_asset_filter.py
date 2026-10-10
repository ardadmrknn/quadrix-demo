# -*- coding: utf-8 -*-
"""PyInstaller spec'leri için runtime-dışı asset süzgeci (paket boyutu düşürme).

Ölçüm kanıtı (2026-10-10 kod-uyum denetim turu, v2 @4f554cc / demo @f42f018):
- ``assets/gamepad_icon/promptfont/`` 29,2 MB'lık upstream PromptFont
  dağıtımıdır; oyunun runtime'ı yalnız üç dosyayı okur:
  ``promptfont.ttf`` (src/promptfont_support.py:27 — font render),
  ``promptfont.py`` (:31 — importlib modül yüklemesi, glif tablosu) ve
  ``LICENSE.txt`` (telif uyumu). Kalan ~28,9 MB (promptfont.exe 13,3 MB,
  promptfont.run 13,2 MB, 9 programlama-dili glif bağlaması, web editörü,
  otf/woff/woff2 font varyantları, ``__pycache__``, README/tags/glyphs.json/
  preview.png) yalnız geliştirici dağıtımıdır; pakete girmesi tesadüfi
  assets-ağacı toplu kopyasıdır.
- ``assets/Tetris.icns`` (2,4 MB) v2'de hiçbir spec/src referansı taşımaz
  (v2 spec'leri ve platform_utils.py:584/678 ``quadrix_icon.icns``
  kullanır). Demo'da bu dosya macOS spec'lerinin ``icon=`` parametresinde
  canlıdır; bu yüzden demo spec'leri ``drop_dead_icns=False`` ile çağırır.

Süzgeç, Analysis'ten SONRA ``a.datas`` TOC'sine uygulanır; kaynak ağaç
değişmez — repo dosyaları yerinde kalır, yalnız paket içine girmeleri
engellenir. ``assets`` ağacındaki PNG'ler ve müzik zaten optimize
edilmiştir (PNG yeniden sıkıştırma örneklemede 4/5 dosyada PIL ile
BÜYÜDÜ; müzik 96 kbps — kalite kararı kullanıcıya aittir).
"""

from __future__ import annotations

import os

# promptfont dizininden pakette kalacak runtime seti
PROMPTFONT_RUNTIME_KEEP = frozenset({
    'promptfont.ttf',   # font render — promptfont_support.py
    'promptfont.py',    # glif tablosu — importlib modül yüklemesi
    'LICENSE.txt',      # PromptFont telif uyumu
})

_PROMPTFONT_DEST_PREFIX = 'assets/gamepad_icon/promptfont/'

# v2: referanssız ölü ikon. Demo: macOS spec icon= parametresinde canlı.
_V2_DEAD_ICNS_DEST = 'assets/Tetris.icns'


def filter_datas(entries, drop_dead_icns: bool = False):
    """PyInstaller TOC girdilerini ``(dest, src, tür)`` sırasına göre süz.

    Saf fonksiyondur: girdi listesini değiştirmez; ``(kalan_girdiler,
    düşen_bayt, düşen_adlar)`` döndürür. Boyut ``os.path.getsize(src)``
    ile okunur; kaynak bulunamazsa 0 sayılır (istisna yutmaz).
    """
    kept = []
    dropped_bytes = 0
    dropped_names = []
    for entry in entries:
        dest = entry[0]
        drop = False
        if dest == _V2_DEAD_ICNS_DEST:
            drop = drop_dead_icns
        elif dest.startswith(_PROMPTFONT_DEST_PREFIX):
            leaf = dest[len(_PROMPTFONT_DEST_PREFIX):]
            drop = leaf not in PROMPTFONT_RUNTIME_KEEP
        if not drop:
            kept.append(entry)
            continue
        dropped_names.append(dest)
        try:
            dropped_bytes += os.path.getsize(entry[1])
        except OSError:
            pass
    return kept, dropped_bytes, dropped_names


def apply_runtime_asset_filter(analysis, drop_dead_icns: bool = False) -> int:
    """Spec gövdesinde ``a = Analysis(...)`` bloğundan sonra çağır.

    ``a.datas``'ı yerinde süzer (``TOC`` liste alt sınıfıdır; dilim ataması
    mevcut referansları korur). Düşürülen toplam baytı döndürür; özet
    satırı spec build log'una basılır — kazanç her derlemede görünür kanıt
    olur (ölçümsüz kazanım yazılmaz ilkesi).
    """
    entries = list(analysis.datas)
    kept, dropped_bytes, dropped_names = filter_datas(entries, drop_dead_icns)
    if dropped_names:
        analysis.datas[:] = kept
        summary = ', '.join(dropped_names[:4])
        if len(dropped_names) > 4:
            summary += f' (+{len(dropped_names) - 4} dosya daha)'
        print(f'[spec] asset süzgeci: {len(dropped_names)} runtime-dışı girdi '
              f'düşürüldü ({dropped_bytes / (1024 * 1024):.1f} MB) — '
              f'{summary}')
    return dropped_bytes
