# -*- coding: utf-8 -*-
"""OP-004 users.json hold-yazımı dirty/debounce sözleşmesi (DALGA C).

record_hold_piece sıcak yolu (üst düzey oyunda saniyede birden çok) tüm
profil veritabanını her seferinde diske yazmıyor: bellek içi sayaç anında
güncel (okuyanlar aynı değeri görür), disk kalıcılığı ana döngüdeki
flush_users_if_due ~2 s debounce'la toplu yazılır; oyun sonu
update_user_stats (save_users) ve kapanış/restart force flush nihai
yazımı garanti eder.

UserManager __new__ + sentetik state + save_users sayaç stub'ı (stub,
gerçek save_users'ın OP-004 satırını yansıtacak şekilde dirty'yi
sıfırlar) — diske dokunmaz.

Modül importları gövde içinde (koleksiyon-runtime sys.modules kimlik
bölünmesi dersi).
"""
from __future__ import annotations

import os
import pathlib
import sys
import time

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / 'src'
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


def _make_manager():
    import user_manager as um_mod

    um = um_mod.UserManager.__new__(um_mod.UserManager)
    um.users = {'testuser': {'hold_piece_counts': {}}}
    um.current_user = 'testuser'
    um._users_dirty = False
    um._users_last_change = time.monotonic()
    um._users_flush_debounce_seconds = 2.0
    um.save_calls = 0

    def _fake_save_users():
        um.save_calls += 1
        # Gerçek save_users'ın OP-004 satırının izdüşümü: yazım dirty'yi
        # sıfırlar (çifte yazım önlenir).
        um._users_dirty = False

    um.save_users = _fake_save_users
    return um


def test_record_hold_updates_memory_and_defers_disk():
    um = _make_manager()
    um.record_hold_piece('I')
    um.record_hold_piece('I')
    um.record_hold_piece('T')

    # Bellek içi sayaç anında güncel — okuyanlar aynı değeri görür.
    counts = um.users['testuser']['hold_piece_counts']
    assert counts['I'] == 2
    assert counts['T'] == 1

    # Disk yazımı ERTELENDİ: sıcak yolda save çağrılmaz.
    assert um.save_calls == 0, 'hold sıcak yolu users.json yazmamali'
    assert um._users_dirty is True


def test_flush_respects_debounce_window():
    um = _make_manager()
    um.record_hold_piece('I')

    # Debounce penceresi içinde: flush yazmaz.
    assert um.flush_users_if_due() is False
    assert um.save_calls == 0

    # Pencere doldu (last_change'i geçmişe çek): toplu yazım + dirty sıfır.
    um._users_last_change = time.monotonic() - 10.0
    assert um.flush_users_if_due() is True
    assert um.save_calls == 1
    assert um._users_dirty is False

    # Yazıldıktan sonra tekrar flush yazmaz.
    assert um.flush_users_if_due() is False
    assert um.save_calls == 1


def test_force_flush_bypasses_debounce():
    um = _make_manager()

    # Dirty yok: force bile yazmaz.
    assert um.flush_users_if_due(force=True) is False
    assert um.save_calls == 0

    # Dirty + pencere dolmamış: force bypass eder.
    um.record_hold_piece('L')
    assert um.flush_users_if_due(force=True) is True
    assert um.save_calls == 1
