# -*- coding: utf-8 -*-
"""OP-009 letterbox fill cache-MISS sözleşmesi (DALGA C).

_blit_canvas_to_display'taki siyah bant fill'leri yalnız geometri
cache-MISS dalında çalışır (resize / canvas swap / display recovery
sonrası bir kez); isarette bant pikselleri kalıcıdır. Bu dosya: MISS →
4 fill, isabet → 0 yeni fill, geometri değişimi → yeniden fill
sözleşmesini kilitler (kapsama dersi: mevcut geometri testleri fill
sayısını assert etmiyordu).

Modül importları gövde içinde (koleksiyon-runtime sys.modules kimlik
bölünmesi dersi). Gerçek display gerekmez: _real_display_surface vekil
nesneyle enjekte edilir, _orig_flip no-op'a bağlanır.
"""
from __future__ import annotations

import os
import pathlib
import sys

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / 'src'
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


class _CountingDisplayProxy:
    """Gerçek display yüzeyi yerine sayan vekil.

    subsurface bilinçli Exception fırlatır → _blit_canvas_to_display
    fallback blit yoluna düşer (transform.scale vekille çalışmaz); blit
    no-op. Test yalnız bant fill davranışını sayar.
    """

    def __init__(self, size):
        self._size = size
        self.fill_calls = 0

    def get_size(self):
        return self._size

    def subsurface(self, rect):
        raise Exception('proxy: subsurface desteklenmiyor')

    def fill(self, color, rect):
        self.fill_calls += 1

    def blit(self, source, dest):
        pass


def test_letterbox_fills_run_only_on_cache_miss():
    import pygame
    import platform_utils

    pygame.init()
    try:
        saved = (
            getattr(platform_utils, '_software_canvas', None),
            getattr(platform_utils, '_real_display_surface', None),
            getattr(platform_utils, '_blit_letterbox_cache', None),
            getattr(platform_utils, '_orig_flip', None),
            getattr(platform_utils, '_virtual_blit_rect', None),
        )
        no_flip = lambda: None
        try:
            platform_utils._orig_flip = no_flip
            platform_utils._blit_letterbox_cache = (None,) * 6

            # 400x250 canvas → 800x600 display (en-boy farkı): ölçek
            # daraltan eksen genişlik → yatay TAM dolar, dikeyde bant
            # (üst+alt = 2 fill). Letterbox'ta tek eksen bant üretebilir.
            platform_utils._software_canvas = pygame.Surface((400, 250))
            proxy = _CountingDisplayProxy((800, 600))
            platform_utils._real_display_surface = proxy

            platform_utils._blit_canvas_to_display()
            assert proxy.fill_calls == 2, 'MISS: üst+alt bant fill beklenir'

            # Cache isabeti: aynı anahtar → bant fill'leri tekrar koşMAZ
            # (OP-009: fill'ler geometri değişmedikçe bant piksellerine
            # dokunmaz — band pikselleri flip'ler arasında kalıcıdır).
            platform_utils._blit_canvas_to_display()
            assert proxy.fill_calls == 2, 'isabet: yeni fill OLMAMALI'

            # Geometri değişimi (canvas swap): yeni anahtar → MISS →
            # bantlar yeniden bir kez doldurulur.
            platform_utils._software_canvas = pygame.Surface((250, 400))
            platform_utils._blit_canvas_to_display()
            assert proxy.fill_calls == 4, 'geometri değişince yeniden bant fill'

            # Bant yoksa (canvas en-boyu display ile aynı): fill koşmaz.
            platform_utils._blit_letterbox_cache = (None,) * 6
            platform_utils._software_canvas = pygame.Surface((800, 600))
            platform_utils._blit_canvas_to_display()
            assert proxy.fill_calls == 4, 'bant yok → fill yok'
        finally:
            (
                platform_utils._software_canvas,
                platform_utils._real_display_surface,
                platform_utils._blit_letterbox_cache,
                platform_utils._orig_flip,
                platform_utils._virtual_blit_rect,
            ) = saved
    finally:
        pygame.quit()
