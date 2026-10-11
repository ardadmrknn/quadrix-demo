# -*- coding: utf-8 -*-
"""G-01/G-02: save başarısızlık retry + debounce üst-sınır sözleşmesi (G dalgası).

G-01: achievement `save()` başarısız olduğunda `_dirty` korunur, debounce
saati yeniden kurulur (kare-başı sonsuz deneme döngüsü YOK, ~2 s aralıklı
kontrollü retry), Steam sync YALNIZ başarılı yazımda çağrılır. user_manager
ikizi aynı semantiği dirty post-check ile taşır.

G-02: iki ikizde de trailing debounce'a "ilk bekleyen değişiklikten en çok
2 s" üst sınırı eklenir — sürekli stat/hold akışında yazım sonsuza ertelenmez.

Manager __new__ + sentetik state (DALGA C deseni) — diske dokunmaz; yalnız
gerçek save hata yolu (A1) geçersiz dizinle gerçek atomic_io'yu çalıştırır.
Modül importları gövde içinde (koleksiyon-runtime sys.modules kimlik bölünmesi
dersi).
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


def _make_achievement_manager():
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
        return True

    def _fake_sync():
        am.sync_calls += 1
        return 0

    am.save = _fake_save
    am.sync_stats_to_steam = _fake_sync
    return am


def _make_user_manager():
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
        # sıfırlar (başarılı yazım varsayımı).
        um._users_dirty = False

    um.save_users = _fake_save_users
    return um


# ── G-01: achievement save() bool sözleşmesi ─────────────────────────────

def test_save_returns_false_on_real_write_failure():
    """Gerçek yazım hatası: save() False döner (hata yutulmaz).

    Hedef yol bir DİZİN — atomic_write_json'ın os.replace adımı
    IsADirectoryError fırlatır (temp yazımı dizinde başarılıdır, hedefe
    takas edilemez).
    """
    import achievements as ach_mod
    import tempfile

    am = ach_mod.AchievementManager.__new__(ach_mod.AchievementManager)
    am.stats = {'total_lines': 1}
    am.unlocked = {}
    am.claimed_rewards = set()
    am.new_achievements = []
    am.user_manager = None
    am.filename = tempfile.mkdtemp(prefix='quadrix_g01_')
    try:
        assert am.save() is False
    finally:
        os.rmdir(am.filename)


def test_flush_keeps_dirty_and_rearms_on_failed_save():
    """Başarısız flush: dirty KALIR, sync çağrılmaz, saat yeniden kurulur."""
    am = _make_achievement_manager()
    am.save = lambda: (setattr(am, 'save_calls', am.save_calls + 1), False)[1]
    am.check_achievements = lambda: None

    am.update_stats(lines=5)
    am._last_change_monotonic = time.monotonic() - 10.0  # trailing doldu

    assert am.flush_achievements_if_due() is False
    assert am.save_calls == 1
    assert am._dirty is True, 'basarisiz yazmada dirty korunmali (G-01)'
    assert am.sync_calls == 0, 'Steam sync yalniz basarili yazimda (G-01)'

    # Saat yeniden kuruldu: hemen ardındaki kare flush'ı YENİDEN denememeli.
    assert am.flush_achievements_if_due() is False
    assert am.save_calls == 1, 'kare-basi yeniden deneme dongusu olmamali'

    # Debounce doldu: tek deneme daha (kontrollü retry).
    am._last_change_monotonic = time.monotonic() - 10.0
    assert am.flush_achievements_if_due() is False
    assert am.save_calls == 2


def test_flush_recovers_and_syncs_once_after_retry():
    """Retry başarılı olursa: bir kez yazar, dirty düşer, sync bir kez."""
    am = _make_achievement_manager()
    am.check_achievements = lambda: None
    am.update_stats(lines=5)
    am._last_change_monotonic = time.monotonic() - 10.0

    _fail = {'now': True}

    def _flaky_save():
        am.save_calls += 1
        if _fail['now']:
            _fail['now'] = False
            return False
        return True

    am.save = _flaky_save
    assert am.flush_achievements_if_due() is False

    am._last_change_monotonic = time.monotonic() - 10.0
    assert am.flush_achievements_if_due() is True
    assert am.save_calls == 2
    assert am.sync_calls == 1
    assert am._dirty is False


def test_update_stats_new_achievement_gates_sync_on_save_success():
    """Yeni başarım anında save başarısızsa: sync ATLANIR, dirty işaretlenir."""
    am = _make_achievement_manager()

    def _fake_check():
        am.new_achievements.append('test_achievement')

    am.check_achievements = _fake_check
    am.save = lambda: (setattr(am, 'save_calls', am.save_calls + 1), False)[1]

    result = am.update_stats(lines=1)
    assert result == ['test_achievement']
    assert am.save_calls == 1
    assert am.sync_calls == 0, 'sync basarisiz yazimda cagrilmamali'
    assert am._dirty is True, 'basarisiz aninda yazim dirty ile retry tailine dusmeli'


def test_unlock_marks_dirty_when_save_fails():
    """unlock() doğrudan save başarısızlığında dirty işaretler.

    'test_achievement' STEAM_ACHIEVEMENT_MAP'te yok — Steam bildirim
    dalına hiç girilmez, yalnız yerel yazım sözleşmesi ölçülür.
    """
    am = _make_achievement_manager()
    am.save = lambda: (setattr(am, 'save_calls', am.save_calls + 1), False)[1]
    am.new_achievements = []

    assert am.unlock('test_achievement') is True
    assert am.save_calls == 1
    assert am._dirty is True


def test_force_flush_on_failure_keeps_dirty_for_close_path():
    """force=True başarısız olursa dirty kalır — kapanış yeniden deneyebilir."""
    am = _make_achievement_manager()
    am.save = lambda: (setattr(am, 'save_calls', am.save_calls + 1), False)[1]
    am.check_achievements = lambda: None

    am.update_stats(lines=5)
    assert am.flush_achievements_if_due(force=True) is False
    assert am._dirty is True
    assert am.save_calls == 1


# ── G-02: üst-sınır (max-wait) — achievements ────────────────────────────

def test_continuous_changes_flush_within_maxwait():
    """Sürekli değişim: trailing hiç dolmasa da ilk pending'den ≤2 s'de yaz."""
    am = _make_achievement_manager()
    am.check_achievements = lambda: None
    am.update_stats(lines=5)  # first_pending = t0

    # Sürekli akış: her 0,5 s'de değişiklik — trailing (2 s) hiç dolmuyor.
    am._first_pending_monotonic = time.monotonic() - 2.1
    am._last_change_monotonic = time.monotonic() - 0.5

    assert am.flush_achievements_if_due() is True, 'max-wait (2 s) dolmali'
    assert am.save_calls == 1
    assert am._dirty is False


def test_first_pending_resets_after_successful_write():
    """Başarılı yazım first_pending'i sıfırlar — yeni epoch yeni ölçer."""
    am = _make_achievement_manager()
    am.check_achievements = lambda: None

    am.update_stats(lines=5)
    am._last_change_monotonic = time.monotonic() - 10.0
    assert am.flush_achievements_if_due() is True
    assert getattr(am, '_first_pending_monotonic', None) is None

    # Yeni değişiklik: taze epoch — eski first_pending taşımaz.
    am.update_stats(lines=7)
    am._last_change_monotonic = time.monotonic() - 0.5
    assert am.flush_achievements_if_due() is False
    assert am.save_calls == 1


# ── G-01/G-02: user_manager ikizi ────────────────────────────────────────

def test_users_flush_keeps_dirty_on_failed_save_and_rearms():
    """Başarısız users.json yazımı: dirty kalır, saat kurulur, tek retry."""
    um = _make_user_manager()

    def _failing_save():
        um.save_calls += 1
        # Başarısızlık izdüşümü: dirty SIFIRLANMAZ (gerçek save_users'ın
        # except yolu).

    um.save_users = _failing_save
    um.record_hold_piece('I')
    um._users_last_change = time.monotonic() - 10.0

    assert um.flush_users_if_due() is False
    assert um.save_calls == 1
    assert um._users_dirty is True, 'basarisiz yazimda dirty korunmali (G-01)'

    # Yeniden kurulan saat: ardışık kare çağrıları yeniden denememeli.
    assert um.flush_users_if_due() is False
    assert um.save_calls == 1

    # Debounce sonrası kontrollü retry.
    um._users_last_change = time.monotonic() - 10.0
    assert um.flush_users_if_due() is False
    assert um.save_calls == 2


def test_users_continuous_changes_flush_within_maxwait():
    """Sürekli hold akışı: ilk pending'den ≤2 s'de toplu yazım."""
    um = _make_user_manager()
    um.record_hold_piece('I')

    um._users_first_pending = time.monotonic() - 2.1
    um._users_last_change = time.monotonic() - 0.5

    assert um.flush_users_if_due() is True
    assert um.save_calls == 1
    assert um._users_dirty is False
