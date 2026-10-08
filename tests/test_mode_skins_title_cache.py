# -*- coding: utf-8 -*-
"""mode_skins başlık/alt başlık dil-anahtarlı cache sözleşmesi (OP-029).

get_localized_skin_title/subtitle (dil, skin.key) anahtarlı modül cache'i
kullanıyor; bu dosya isabet yolunu ve dil-değişimi invalidasyonunu kilitler.
"""
from __future__ import annotations

import os
import pathlib
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import mode_skins
from mode_skins import get_mode_skin, get_localized_skin_title, get_localized_skin_subtitle


def test_skin_title_cache_hit_and_language_invalidation():
    skin = get_mode_skin("classic")

    first = get_localized_skin_title(skin)
    assert isinstance(first, str) and first

    cache = mode_skins._LOCALIZED_SKIN_TITLE_CACHE
    cache_len = len(cache)
    assert cache_len >= 1

    # Isabet: ikinci çağrı aynı sonucu verir, yeni girdi eklemez.
    second = get_localized_skin_title(skin)
    assert second == first
    assert len(cache) == cache_len

    # Alt başlık da aynı cache'e girer; boş subtitle erken döner.
    subtitle = get_localized_skin_subtitle(skin)
    assert isinstance(subtitle, str)


def test_skin_title_language_switch_creates_new_cache_entry():
    from localization import get_language, set_language

    skin = get_mode_skin("classic")
    original_lang = str(get_language() or "en")
    # Test izolasyonu: önceki testlerin cache girdilerini temizle.
    mode_skins._LOCALIZED_SKIN_TITLE_CACHE.clear()
    try:
        set_language("en")
        title_en = get_localized_skin_title(skin)
        entries_en = len(mode_skins._LOCALIZED_SKIN_TITLE_CACHE)

        set_language("tr")
        title_tr = get_localized_skin_title(skin)
        # Dil değişimi yeni anahtar üretmeli: girdi sayısı artar.
        assert len(mode_skins._LOCALIZED_SKIN_TITLE_CACHE) > entries_en
        # Her iki dil de TÜR olarak string döner (değer dillere göre
        # çeviri tablosuna bağlı; birebir eşitlik iddia edilmez).
        assert isinstance(title_en, str) and isinstance(title_tr, str)
    finally:
        set_language(original_lang)
