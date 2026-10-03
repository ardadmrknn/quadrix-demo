# -*- coding: utf-8 -*-
"""P0-4 — tutorial_cards gerçek katalog memo'sunun hata sonrası iyileşmesi.

Uygulama_Denetimi_Iade_4K_Gamepad_Raporu.md P0-4 (sıra bağımlılığı sınıfı):
Bulgu: _ensure_real_card_helpers() başarısız bir import penceresinde
{} sentinel'ini KALICI olarak bırakıyordu; tek seferlik kirli bir pencere
(test stub'ları) sürecin geri kalanında tutorial fallback değerlerinin
kullanılmasına yol açıyordu (örn. freeze_drop_rare value 6, gerçek 3).

Düzeltme: except dalında memo None'a döner → bir sonraki çağrı yeniden
dener; _REAL_CARD_HELPERS_MAX_ATTEMPTS ile üst sınır korunur.

DİKKAT (P0-4): bu dosya modül-seviyesinde sys.path insert veya oyun modülü
importu YAPMAZ — collection-time yan etkiler tam pakette başka testlerin
(localization durumu) kirlenmesine yol açıyordu. Tüm importlar test
gövdesine ertelenmiştir; src yolu conftest'ten gelir.
"""

from __future__ import annotations

import sys
import types

import pytest


def test_failed_real_catalog_import_recovers_on_next_call(monkeypatch):
    """Gerçek import başarısızlığı (kirli pencere) kalıcı fallback bırakmaz.

    {} sentinel'i tasarım gereği 'işlemde' anlamına gelir ve guard erken
    döner; kalıcı kirlilik yalnızca except dalının {}'yi bırakmasından
    doğuyordu. Bu test gerçek mekanizmayı tetikler: kırık bir
    game_modes_extra penceresi → None → temiz pencerede iyileşme.
    """
    import tutorial_cards as tc

    healthy = tc.get_card_preview("freeze_drop_rare")
    healthy_lib = tc._REAL_CARD_LIBRARY
    if not healthy_lib:
        pytest.skip("test ortamında gerçek katalog yüklenemiyor")
    healthy_value = healthy["value"]
    saved_attempts = tc._real_card_helpers_attempts

    class _BrokenModule(types.ModuleType):
        def __getattr__(self, name):
            raise ImportError(f"broken stub for {name!r}")

    # P0-4: tam pakette tutorial_cards 'src.tutorial_cards' olarak çözümlenir
    # ve _ensure önce RELATIVE 'src.game_modes_extra' yolunu dener; izole
    # koşuda absolute 'game_modes_extra' yoluna düşer. Kırık pencere her iki
    # çözümleme modunda da tetiklensin diye iki anahtar da stub'lanır.
    monkeypatch.setitem(sys.modules, "game_modes_extra", _BrokenModule("game_modes_extra"))
    monkeypatch.setitem(
        sys.modules, "src.game_modes_extra", _BrokenModule("src.game_modes_extra"))

    try:
        tc._REAL_CARD_LIBRARY = None
        tc._real_card_helpers_attempts = 0

        # Kirli pencere: import başarısız olmalı ve memo None kalmalı.
        tc._ensure_real_card_helpers()
        assert tc._REAL_CARD_LIBRARY is None, (
            "başarısız import sonrası memo None kalmalı (eski davranışta "
            "kalıcı {}'ye düşüp bir daha denenmiyordu)"
        )
        assert tc._real_card_helpers_attempts == 1

        # Pencere temizlendi (stub sys.modules'ten çıkacak) → iyileşme.
        monkeypatch.undo()
        recovered = tc.get_card_preview("freeze_drop_rare")

        assert recovered is not None
        assert recovered["value"] == healthy_value, (
            "kirli pencere sonrası çağrı fallback değerine DÖNMEMELİ; "
            "gerçek katalog yeniden yüklenmeli"
        )
        assert tc._REAL_CARD_LIBRARY, "kütüphane yeniden doldurulmalı"
    finally:
        if tc._REAL_CARD_LIBRARY is None:
            tc._REAL_CARD_LIBRARY = healthy_lib
        tc._real_card_helpers_attempts = saved_attempts


def test_real_card_helpers_attempts_are_bounded():
    """Deneme bütçesi tükenince kalıcı fallback (eski davranış) korunur."""
    import tutorial_cards as tc

    saved_lib = tc._REAL_CARD_LIBRARY
    saved_attempts = tc._real_card_helpers_attempts

    tc._REAL_CARD_LIBRARY = None
    tc._real_card_helpers_attempts = tc._REAL_CARD_HELPERS_MAX_ATTEMPTS
    try:
        # _ensure erken dönmeli: kütüphane boş kalır, deneme sayısı artmaz.
        tc._ensure_real_card_helpers()

        assert tc._REAL_CARD_LIBRARY is None
        assert tc._real_card_helpers_attempts == tc._REAL_CARD_HELPERS_MAX_ATTEMPTS
    finally:
        tc._REAL_CARD_LIBRARY = saved_lib
        tc._real_card_helpers_attempts = saved_attempts
