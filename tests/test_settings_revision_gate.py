# -*- coding: utf-8 -*-
"""OP-001 SettingsManager ayar-revizyon sayacı sözleşmesi (DALGA C).

Ana döngü kare-başı sync_from_settings_manager çağrısı artık revizyon
kapısına bağlı: yalnız İÇERİK değişimi (set/update/reset/playlist set*
+ main.py cheat-yolu bump) sync tetikler. Bu dosya sözleşmeyi kilitler:
- mutasyon yollarının TAMAMI sayacı artırır (eksik bump → bayat ayar
  görüntüsü — MD risk maddesi);
- get yollarındaki idempotent normalizasyon yazmaları (get_controls,
  lazy playlist/override normalize) ve disk yazımı (save_settings,
  flush_if_due) sayacı ARTIRMAZ — her kare çift deepcopy geri gelmez.

SettingsManager __new__ + sentetik attribute'larla kurulur (save_settings
stub'lı) — test gerçek ayar dosyasına dokunmaz.

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


def _make_manager():
    """__new__ + sentetik state — disk/IO'suz izole instance."""
    import settings_manager as sm_mod

    sm = sm_mod.SettingsManager.__new__(sm_mod.SettingsManager)
    sm.settings = {
        'ui_scale_preset': 'auto',
        'particle_effects': 'medium',
        'music_volume': 0.5,
        'controls': {},
        'mode_music_overrides': {'classic': 'klasik_1'},
        'mode_music_playlists': {'classic': ['klasik_1']},
    }
    sm.default_settings = {'ui_scale_preset': 'auto', 'particle_effects': 'medium'}
    sm._debounced_keys = {'music_volume'}
    sm._dirty = False
    sm._last_change_monotonic = 0.0
    sm._save_debounce_seconds = 0.5
    sm._last_save_monotonic = 0.0
    sm.save_calls = 0

    def _fake_save():
        sm.save_calls += 1
        return True

    sm.save_settings = _fake_save
    # __init__ sözleşmesi: sayaç 1'den başlar.
    sm.settings_revision = 1
    return sm, sm_mod


def _restore_ui_scale_preset():
    """_sync_ui_scale_preset'in ui_scaling globalinde yarattığı etkiyi geri al."""
    try:
        import ui_scaling
        ui_scaling.set_ui_scale_preset('auto')
    except Exception:
        pass


def test_mutation_paths_bump_revision():
    sm, _ = _make_manager()
    try:
        # set — normal anahtar (save dalı).
        rev0 = sm.settings_revision
        sm.set('particle_effects', 'high')
        assert sm.settings_revision == rev0 + 1

        # set — debounced anahtar (early-return dalı; bump ÖNCE koşmalı).
        rev1 = sm.settings_revision
        sm.set('music_volume', 0.7)
        assert sm.settings_revision == rev1 + 1
        assert sm._dirty is True

        # update.
        rev2 = sm.settings_revision
        sm.update(sfx_volume=0.3)
        assert sm.settings_revision == rev2 + 1

        # reset_to_defaults.
        rev3 = sm.settings_revision
        sm.reset_to_defaults()
        assert sm.settings_revision == rev3 + 1

        # Müzik set* ailesi.
        for bump_call in (
            lambda: sm.set_mode_music_override('zen', 'zen_1'),
            lambda: sm.set_menu_music_playlist(['main_1']),
            lambda: sm.set_game_music_playlist(['klasik_1']),
            lambda: sm.set_campaign_music_playlist(['klasik_1']),
            lambda: sm.set_mode_music_playlist('classic', ['klasik_2']),
        ):
            rev_before = sm.settings_revision
            bump_call()
            assert sm.settings_revision == rev_before + 1

        # bump helper doğrudan (cheat-yolu deseni: dict yazımı + elle bump).
        rev_final = sm.settings_revision
        sm.settings['show_debug_settings'] = True
        sm.bump_settings_revision()
        assert sm.settings_revision == rev_final + 1
    finally:
        _restore_ui_scale_preset()


def test_read_and_save_paths_do_not_bump():
    sm, _ = _make_manager()
    try:
        # get_controls: idempotent normalizasyon YAZMASI (settings['controls']
        # = normalize) sayaç ARTIRMAMALI — her kare deepcopy geri gelmez.
        rev0 = sm.settings_revision
        for _ in range(2):
            controls = sm.get_controls()
            assert isinstance(controls, dict)
        assert sm.settings_revision == rev0

        # Lazy normalizasyon yazmaları get yollarında (override/playlists).
        sm.settings['mode_music_overrides'] = None
        sm.settings['mode_music_playlists'] = None
        sm.get_mode_music_overrides()
        sm.get_mode_music_playlists()
        sm.get_mode_music_playlist('classic')
        assert sm.settings_revision == rev0

        # Basit get.
        assert sm.get('music_volume') == 0.5
        assert sm.settings_revision == rev0

        # Disk yazımı (save_settings / flush_if_due) içerik değişimi değil.
        sm.save_settings()
        assert sm.settings_revision == rev0
        sm._dirty = True
        sm._last_change_monotonic = 0.0  # debounce penceresi dolmuş
        import time
        sm._last_change_monotonic = time.monotonic() - 10.0
        assert sm.flush_if_due() is True
        assert sm.save_calls >= 1
        assert sm.settings_revision == rev0, 'flush_if_due revizyonu artirmamali'
    finally:
        _restore_ui_scale_preset()


def test_bump_helper_survives_missing_counter():
    """__init__ koşmamış instance'da bump getattr default'undan 1 türetir."""
    sm, _ = _make_manager()
    del sm.settings_revision
    sm.bump_settings_revision()
    assert sm.settings_revision == 1
    sm.bump_settings_revision()
    assert sm.settings_revision == 2
