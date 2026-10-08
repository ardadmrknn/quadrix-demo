# -*- coding: utf-8 -*-
"""OP-033 asset_manager iki kademeli anahtar sözleşmesi (DALGA C).

load_image isabet yolunda exists/resolve syscall'larından geçmemeli:
ucuz normpath anahtarı cache'lenmiş çözüme bağlanır; MISS'te tam çözüm
bir kez yapılır. MD bölüm 11'de 'dar asset testi YOK' boşluğu kapanır.

Modül importları gövde içinde (koleksiyon-runtime sys.modules kimlik
bölünmesi dersi).
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


def _make_png(tmp_path):
    import pygame

    surf = pygame.Surface((4, 4))
    surf.fill((200, 30, 30))
    png_path = tmp_path / 'op033_probe.png'
    pygame.image.save(surf, str(png_path))
    return png_path


def test_hit_path_skips_resolve_syscalls(monkeypatch, tmp_path):
    import pygame

    import asset_manager as am

    png_path = _make_png(tmp_path)
    try:
        am.clear_image_cache()
        resolve_calls = []
        real_normalize = am._normalize_path

        def _counting_normalize(path):
            resolve_calls.append(str(path))
            return real_normalize(path)

        monkeypatch.setattr(am, '_normalize_path', _counting_normalize)

        # İlk yükleme: MISS → tam çözüm BİR KEZ.
        first = am.load_image(str(png_path))
        assert len(resolve_calls) == 1

        # Isabet yolunda: exists/resolve syscall'ı YOK (ucuz kademe).
        for _ in range(5):
            again = am.load_image(str(png_path))
            assert again is first
        assert len(resolve_calls) == 1, 'isaret yolunda normalize/syscall olmamali'
    finally:
        am.clear_image_cache()
        pygame.quit()


def test_different_spellings_share_raw_cache(tmp_path):
    import pygame

    import asset_manager as am

    png_path = _make_png(tmp_path)
    try:
        am.clear_image_cache()
        abs_str = str(png_path)
        rel_dot = os.path.join('.', os.path.basename(abs_str))

        # Farklı yazımlar: fast-map'te ayrı anahtar (tam çözüm ayrı koşar)
        # ama ham cache ÇÖZÜLMÜŞ anahtarla tek girdi → aynı surface.
        a = am.load_image(abs_str)
        old_cwd = os.getcwd()
        os.chdir(str(tmp_path))
        try:
            b = am.load_image(rel_dot)
        finally:
            os.chdir(old_cwd)
        assert a is b, 'farkli yazimlar ayni cozumlenmis anahtara dusmeli'
    finally:
        am.clear_image_cache()
        pygame.quit()


def test_clear_image_cache_drops_fast_path(monkeypatch, tmp_path):
    import pygame

    import asset_manager as am

    png_path = _make_png(tmp_path)
    try:
        am.clear_image_cache()
        assert am._FAST_PATH_CACHE == {}
        am.load_image(str(png_path))
        assert len(am._FAST_PATH_CACHE) == 1
        am.clear_image_cache()
        assert am._FAST_PATH_CACHE == {}, 'clear fast-path eslemesini de dusmeli'
    finally:
        am.clear_image_cache()
        pygame.quit()
