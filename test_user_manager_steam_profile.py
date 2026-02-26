# -*- coding: utf-8 -*-
"""Birim testleri: UserManager Steam profil entegrasyonu.

Kapsamı:
- create_user(..., steam_id=...) steam_id'yi profile yazar.
- get_user_by_steam_id() doğru username döndürür.
- set_steam_id() alanı günceller.
- Persona adı çakışması durumunda unique username üretimi.
"""
from __future__ import annotations

import os
import sys
import json
import tempfile
import unittest

# src/ klasörünü sys.path'e ekle
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from user_manager import UserManager


def _make_manager() -> UserManager:
    """Geçici dosya ile yeni bir UserManager örneği oluştur."""
    fd, path = tempfile.mkstemp(suffix='.json', prefix='um_test_')
    os.close(fd)
    os.unlink(path)  # Dosyayı sil; UserManager yoksa users={} ile başlar
    return UserManager(users_file=path)


class TestCreateUserWithSteamId(unittest.TestCase):
    """create_user() steam_id parametresini profile yazmalı."""

    def setUp(self):
        self.um = _make_manager()

    def test_create_user_with_steam_id_stores_it(self):
        """create_user(..., steam_id='765...') profile içine steam_id yazar."""
        ok, msg = self.um.create_user('TestPlayer', steam_id='76561199351154071')
        self.assertTrue(ok, msg)
        profile = self.um.users['TestPlayer']
        self.assertEqual(profile.get('steam_id'), '76561199351154071')

    def test_create_user_without_steam_id_stores_none(self):
        """create_user() steam_id vermeden çağrılsa profile steam_id=None yazar."""
        ok, _ = self.um.create_user('PlayerNoSteam')
        self.assertTrue(ok)
        profile = self.um.users['PlayerNoSteam']
        self.assertIsNone(profile.get('steam_id'))

    def test_create_user_steam_id_empty_string_stores_none(self):
        """create_user(..., steam_id='')  →  steam_id=None."""
        ok, _ = self.um.create_user('EmptySteamId', steam_id='')
        self.assertTrue(ok)
        profile = self.um.users['EmptySteamId']
        self.assertIsNone(profile.get('steam_id'))

    def test_create_user_steam_id_whitespace_stores_none(self):
        """create_user(..., steam_id='   ')  →  steam_id=None."""
        ok, _ = self.um.create_user('WsPlayer', steam_id='   ')
        self.assertTrue(ok)
        profile = self.um.users['WsPlayer']
        self.assertIsNone(profile.get('steam_id'))


class TestGetUserBySteamId(unittest.TestCase):
    """get_user_by_steam_id() SteamID ile username bulur."""

    def setUp(self):
        self.um = _make_manager()
        self.um.create_user('SteamAlice', steam_id='76561199000000001')
        self.um.create_user('SteamBob', steam_id='76561199000000002')

    def test_finds_existing_steam_user(self):
        result = self.um.get_user_by_steam_id('76561199000000001')
        self.assertEqual(result, 'SteamAlice')

    def test_finds_second_steam_user(self):
        result = self.um.get_user_by_steam_id('76561199000000002')
        self.assertEqual(result, 'SteamBob')

    def test_returns_none_for_unknown_steam_id(self):
        result = self.um.get_user_by_steam_id('76561199999999999')
        self.assertIsNone(result)

    def test_returns_none_for_empty_steam_id(self):
        result = self.um.get_user_by_steam_id('')
        self.assertIsNone(result)

    def test_returns_none_for_none_steam_id(self):
        result = self.um.get_user_by_steam_id(None)
        self.assertIsNone(result)


class TestSetSteamId(unittest.TestCase):
    """set_steam_id() mevcut profile steam_id bağlar."""

    def setUp(self):
        self.um = _make_manager()
        self.um.create_user('LatePlayer')

    def test_set_steam_id_updates_profile(self):
        self.um.set_steam_id('LatePlayer', '76561199111111111')
        profile = self.um.users['LatePlayer']
        self.assertEqual(profile.get('steam_id'), '76561199111111111')

    def test_set_steam_id_then_get_user_by_steam_id(self):
        self.um.set_steam_id('LatePlayer', '76561199222222222')
        found = self.um.get_user_by_steam_id('76561199222222222')
        self.assertEqual(found, 'LatePlayer')

    def test_set_steam_id_none_clears_field(self):
        self.um.set_steam_id('LatePlayer', '76561199333333333')
        self.um.set_steam_id('LatePlayer', None)
        profile = self.um.users['LatePlayer']
        self.assertIsNone(profile.get('steam_id'))


class TestSteamAutoProfileScenario(unittest.TestCase):
    """main.py Steam init akışını simüle eder:
    SteamID ile bak → yoksa persona ile bak → yoksa oluştur.
    """

    def setUp(self):
        self.um = _make_manager()

    def test_create_then_find_by_steam_id(self):
        """Steam'den ilk kez başlatılınca: oluştur → sonraki seferde SteamID ile bul."""
        steam_id = '76561199351154072'
        persona = 'TestersChoice'

        # İlk çalıştırma: henüz profil yok
        existing = self.um.get_user_by_steam_id(steam_id)
        self.assertIsNone(existing)

        # Yeni profil oluştur
        ok, _ = self.um.create_user(persona, avatar='🎮', steam_id=steam_id)
        self.assertTrue(ok)
        self.um.select_user(persona)

        # İkinci çalıştırma: SteamID ile bul
        found = self.um.get_user_by_steam_id(steam_id)
        self.assertEqual(found, persona)

    def test_persona_collision_use_steamid_suffix(self):
        """'arda' adıyla başka biri daha önce profile oluşturduysa SteamID eki kullanılır."""
        # Önceden 'arda' adlı bir profil var (steam_id yok)
        self.um.create_user('arda')

        steam_id = '76561199351190001'
        persona = 'arda'

        # SteamID ile arama: None (steam_id bağlı değil)
        found_by_sid = self.um.get_user_by_steam_id(steam_id)
        self.assertIsNone(found_by_sid)

        # Persona adı zaten var ve farklı steam_id → unique username üret
        existing_by_name = self.um.users.get(persona)
        self.assertIsNotNone(existing_by_name)
        existing_steam_id = existing_by_name.get('steam_id') if existing_by_name else None

        if existing_steam_id and existing_steam_id != steam_id:
            # Çakışma: unique username üret
            unique_name = (persona[:16] + '_' + steam_id[-4:])[:20]
        elif not existing_by_name:
            unique_name = persona
        else:
            # Persona adı var ama steam_id yok → bağla
            unique_name = persona

        if unique_name not in self.um.users:
            ok, _ = self.um.create_user(unique_name, avatar='🎮', steam_id=steam_id)
            self.assertTrue(ok)
        else:
            self.um.set_steam_id(unique_name, steam_id)

        # Artık SteamID ile bulunabilmeli
        found = self.um.get_user_by_steam_id(steam_id)
        self.assertEqual(found, unique_name)

    def test_create_user_steam_id_persisted_after_reload(self):
        """create_user ile yazılan steam_id, kayıt/yükleme sonrası da korunur."""
        import tempfile, os
        fd, path = tempfile.mkstemp(suffix='.json', prefix='um_persist_')
        os.close(fd)
        try:
            um = UserManager(users_file=path)
            um.create_user('PersistMe', steam_id='76561199888888888')
            # Yeni instance ile yüklendikten sonra
            um2 = UserManager(users_file=path)
            found = um2.get_user_by_steam_id('76561199888888888')
            self.assertEqual(found, 'PersistMe')
        finally:
            if os.path.exists(path):
                os.unlink(path)


if __name__ == '__main__':
    unittest.main()
