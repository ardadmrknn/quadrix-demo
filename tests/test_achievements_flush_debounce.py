# -*- coding: utf-8 -*-
"""OP-003 achievements dirty/debounce sözleşmesi (DALGA C).

update_stats sıcak yolu (satır-temizleme) artık her çağrıda disk + Steam
yazmıyor: yeni başarım varsa ANINDA yazar (toast/unlock anı birebir);
istatistik değişikliğinde `_dirty` işaretler, ana döngüdeki
flush_achievements_if_due ~2 s debounce'la toplu yazar; temiz çıkış /
restart `force=True` ile bypass eder. Bu dosya yol ayrımını kilitler.

AchievementManager __new__ + sentetik state + save/sync sayaçları —
disk/Steam'e dokunmaz.

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
    import achievements as ach_mod

    am = ach_mod.AchievementManager.__new__(ach_mod.AchievementManager)
    am.stats = {'total_games': 0, 'total_lines': 0, 'max_lines': 0}
    am.unlocked = {}
    am.claimed_rewards = set()
    am.new_achievements = []
    am.user_manager = None
    am._dirty = False
    am._last_change_monotonic = time.monotonic()
    am._flush_debounce_seconds = 2.0
    am.save_calls = 0
    am.sync_calls = 0

    def _fake_save():
        am.save_calls += 1
        return None

    def _fake_sync():
        am.sync_calls += 1
        return 0

    am.save = _fake_save
    am.sync_stats_to_steam = _fake_sync
    return am


def test_stats_only_change_defers_disk_and_steam():
    """İstatistik değişikliği: anında yazım YOK; dirty + debounce."""
    am = _make_manager()
    am.check_achievements = lambda: None  # yeni başarım yok

    result = am.update_stats(lines=5)
    assert result == []
    assert am.save_calls == 0, 'istatistik-yalnız yol disk yazmamali'
    assert am.sync_calls == 0, 'istatistik-yalnız yol Steam sync yapmamali'
    assert am._dirty is True
    assert am.stats['max_lines'] == 5

    # Debounce penceresi içinde: flush yazmaz.
    assert am.flush_achievements_if_due() is False
    assert am.save_calls == 0

    # Pencere doldu (last_change'i geçmişe çek): toplu yazım.
    am._last_change_monotonic = time.monotonic() - 10.0
    assert am.flush_achievements_if_due() is True
    assert am.save_calls == 1
    assert am.sync_calls == 1
    assert am._dirty is False

    # Yazıldıktan sonra: tekrar flush yazmaz.
    assert am.flush_achievements_if_due() is False
    assert am.save_calls == 1


def test_new_achievement_writes_immediately():
    """Yeni başarım: save + sync ANINDA (toast/unlock anı birebir)."""
    am = _make_manager()

    def _fake_check():
        am.new_achievements.append('test_achievement')

    am.check_achievements = _fake_check

    result = am.update_stats(lines=1)
    assert result == ['test_achievement']
    assert am.save_calls == 1, 'yeni basarim aninda diske yazilmali'
    assert am.sync_calls == 1, 'yeni basarim aninda Steam sync yapmali'
    assert am._dirty is False


def test_force_flush_bypasses_debounce():
    """force=True: dirty varsa debounce beklemeden yazar; yoksa yazmaz."""
    am = _make_manager()
    am.check_achievements = lambda: None

    # Dirty yok: force bile yazmaz (gereksiz save yok).
    assert am.flush_achievements_if_due(force=True) is False
    assert am.save_calls == 0

    # Dirty + pencere dolmamış: force bypass eder.
    am.update_stats(lines=2)
    assert am.flush_achievements_if_due(force=True) is True
    assert am.save_calls == 1
    assert am.sync_calls == 1
