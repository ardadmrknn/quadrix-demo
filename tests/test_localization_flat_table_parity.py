# -*- coding: utf-8 -*-
"""OP-011 flat-tablo get_text parite sözleşmesi (DALGA C).

Eski iç içe .get zinciri ile yeni flat-tablo araması TUM anahtar x dil
matrisinde birebir aynı sonucu uretmeli (MD'nin dump-diff kanıtının test
biçimi — daha guclu: her anahtar x her dil x default varyantı). Ek olarak:
iki düşüş yolunun AYRIMI (anahtar hiç yok → kwargs UYGULANMAZ; anahtar var
ama lang/en/tr yok → kwargs uygulanır), boş-string VARLIK semantiği,
hot-reload yeniden bağlama invalidasyonu ve cache isareti kilitlenir.

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


def _legacy_get_text(mod, key, default=None, **kwargs):
    """Eski (pre-OP-011) iç içe .get zincirinin bağımsız kopyası."""
    translations = mod.TRANSLATIONS
    lang = mod._current_language
    if key in translations:
        entry = translations[key]
        text = entry.get(
            lang,
            entry.get('en', entry.get('tr', default or key))
        )
        if kwargs:
            try:
                text = text.format(**kwargs)
            except (KeyError, ValueError):
                pass
        return text
    return default or key


def _with_module():
    import localization as mod
    return mod


def test_full_matrix_parity_with_legacy_chain():
    """Her dil x her anahtar x default varyantı: flat == eski zincir."""
    mod = _with_module()
    original_lang = str(mod.get_language() or 'en')
    try:
        for lang in mod.SUPPORTED_LANGUAGES:
            mod.set_language(lang)
            assert mod._current_language == lang
            for key in mod.TRANSLATIONS:
                new = mod.get_text(key)
                old = _legacy_get_text(mod, key)
                assert new == old, f'{lang}:{key} (default=None): {new!r} != {old!r}'
                new_d = mod.get_text(key, default='__DSTR__')
                old_d = _legacy_get_text(mod, key, default='__DSTR__')
                assert new_d == old_d, f'{lang}:{key} (default=__DSTR__): {new_d!r} != {old_d!r}'
                new_e = mod.get_text(key, default='')
                old_e = _legacy_get_text(mod, key, default='')
                assert new_e == old_e, f'{lang}:{key} (default=""): {new_e!r} != {old_e!r}'
            # Flat tablo isareti: aynı dil → AYNI tablo nesnesi.
            assert mod._get_flat_text_table(lang) is mod._get_flat_text_table(lang)
    finally:
        mod.set_language(original_lang)


def test_fallback_path_semantics_split():
    """İki düşüş yolu ayrımı: yok → kwargs'sız; var-ama-dil-yok → kwargs'lı."""
    mod = _with_module()
    original_lang = str(mod.get_language() or 'en')
    original_table = mod.TRANSLATIONS
    try:
        mod.set_language('en')
        synthetic = {
            'k_nolang': {'fr': 'fr-deger'},      # en/tr yok → iç düşüş
            'k_empty': {'en': ''},                # boş string DEĞER
            'k_plain': {'en': 'EN', 'tr': 'TR'},  # normal isabet
        }
        mod.TRANSLATIONS = synthetic

        # Anahtar hiç yok: kwargs UYGULANMAZ (eski `return default or key`).
        assert mod.get_text('k_hic_yok', default='D {v}', v=1) == 'D {v}'

        # Anahtar var ama en/tr yok: default-or-key + kwargs UYGULANIR.
        assert mod.get_text('k_nolang', default='D {v}', v=1) == 'D 1'

        # Boş string VARLIK semantiği: default'a DÜŞMEZ.
        assert mod.get_text('k_empty', default='DOLGUN') == ''

        # Normal isaret.
        assert mod.get_text('k_plain') == 'EN'
        assert mod.get_text('k_plain', default='D') == 'EN'
    finally:
        mod.TRANSLATIONS = original_table
        mod._flat_text_tables = {}
        mod._flat_text_tables_source = None
        mod.set_language(original_lang)


def test_hot_reload_rebind_invalidates_flat_tables():
    """TRANSLATIONS yeniden bağlanınca flat tablolar düşer (kimlik kapısı)."""
    mod = _with_module()
    original_lang = str(mod.get_language() or 'en')
    original_table = mod.TRANSLATIONS
    try:
        mod.set_language('en')
        first = mod.get_text('k_probe', default='ILK')
        assert first == 'ILK'
        before = mod._get_flat_text_table(mod._current_language)

        # Hot-reload simülasyonu: YENİ dict nesnesi (yeniden bağlama) —
        # aynı anahtar artık farklı değer döndürmeli.
        rebound = dict(original_table)
        rebound['k_probe'] = {'en': 'YENI', 'tr': 'YENI_TR'}
        mod.TRANSLATIONS = rebound
        assert mod.get_text('k_probe', default='ILK') == 'YENI'
        after = mod._get_flat_text_table(mod._current_language)
        assert after is not before, 'yeniden bağlama → yeni tablo nesnesi'

        # Aynı nesnede isaret: tablo kalıcı.
        assert mod._get_flat_text_table(mod._current_language) is after
    finally:
        mod.TRANSLATIONS = original_table
        mod._flat_text_tables = {}
        mod._flat_text_tables_source = None
        mod.set_language(original_lang)
