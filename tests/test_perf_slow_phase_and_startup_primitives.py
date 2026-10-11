# -*- coding: utf-8 -*-
"""PERF-1 (PERF-01): telemetri ilkeleri sözleşmesi — demo.

`record_slow_phase`: faz pencere kovasına yazılır; >threshold ms ise olay
düzeyinde de kaydedilir (slow_handler deseninin KÖK FAZ ADLI ikizi — rapor
§9.2 PERF-01: "100 ms üzeri her olay anonim handler yerine kök faz adıyla
görünür"). `record_startup_phase`: startup alt fazları akış boyunca olay
olarak düşer (crash-safe). Demo telemetrisi opt-in/bounded'tır: kapalıyken
ikisi de no-op; test izolasyonu `_enabled_cache` doğrudan açılır.
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

import perf_telemetry as pt  # noqa: E402


class _Kayan:
    """pytest fixture yerine basit toplayıcı (olayları yakalar).

    Gerçek `_write_event`'in `is_enabled()` kapısını aynalar — kapalıyken
    olay yakalanmaz (üretim davranışı: kapı `_write_event` içindedir).
    """

    def __init__(self):
        self.olaylar = []

    def __call__(self, olay):
        if not pt.is_enabled():
            return
        self.olaylar.append(dict(olay))


def _kur(kapali=False):
    """Telemetriyi aç/kapat, _write_event'i yakala, kovaları temizle."""
    kutu = _Kayan()
    pt._enabled_cache = False if kapali else True
    pt._agg.clear()
    orijinal = pt._write_event
    pt._write_event = kutu
    return kutu, orijinal


def _temizle(orijinal):
    pt._write_event = orijinal
    pt._enabled_cache = None
    pt._agg.clear()


def test_record_slow_phase_alt_esik_olay_yok():
    kutu, orijinal = _kur()
    try:
        pt.record_slow_phase('menu', 'launch_game_ms', 42.0)
        kova = pt._agg['menu']['phases_ms']['launch_game_ms']
        assert len(kova) == 1 and abs(kova[0] - 42.0) < 1e-6
        assert kutu.olaylar == [], 'esik alti olay dusmemeli'
    finally:
        _temizle(orijinal)


def test_record_slow_phase_ust_esik_olay_kok_faz_adiyla():
    kutu, orijinal = _kur()
    try:
        pt.record_slow_phase('menu', 'launch_online_coop_ms', 935.4)
        olay = [o for o in kutu.olaylar if o.get('type') == 'slow_phase']
        assert len(olay) == 1
        assert olay[0]['state'] == 'menu'
        assert olay[0]['phase'] == 'launch_online_coop_ms'
        assert olay[0]['ms'] == 935.4
        # Faz kovaya da yazılır (pencere istatistiği kaybolmaz).
        assert len(pt._agg['menu']['phases_ms']['launch_online_coop_ms']) == 1
    finally:
        _temizle(orijinal)


def test_record_slow_phase_ozel_esik_ve_kapali_durum():
    kutu, orijinal = _kur()
    try:
        # Özel eşik: 150 > 120 → olay.
        pt.record_slow_phase('online_coop', 'coop_board_send_ms', 150.0,
                             threshold_ms=120.0)
        assert len([o for o in kutu.olaylar if o.get('type') == 'slow_phase']) == 1
    finally:
        _temizle(orijinal)
    kutu, orijinal = _kur(kapali=True)
    try:
        pt.record_slow_phase('online_coop', 'coop_board_send_ms', 950.0)
        assert kutu.olaylar == []
        assert 'online_coop' not in pt._agg or not pt._agg['online_coop']['phases_ms']
    finally:
        _temizle(orijinal)


def test_record_slow_phase_gecersiz_ms_sessiz():
    kutu, orijinal = _kur()
    try:
        pt.record_slow_phase('menu', 'launch_game_ms', None)
        pt.record_slow_phase('menu', 'launch_game_ms', 'x')
        assert kutu.olaylar == []
    finally:
        _temizle(orijinal)


def test_record_startup_phase_olay_sozlesmesi():
    kutu, orijinal = _kur()
    try:
        pt.record_startup_phase('steam_init', 312.7)
        olay = [o for o in kutu.olaylar if o.get('type') == 'startup_phase']
        assert len(olay) == 1
        assert olay[0]['phase'] == 'steam_init'
        assert olay[0]['ms'] == 312.7
        # Startup fazları kova DEĞİL olay kanalıdır (crash-safe akış).
        assert not pt._agg
    finally:
        _temizle(orijinal)


def test_record_startup_phase_kapali_ve_gecersiz():
    kutu, orijinal = _kur(kapali=True)
    try:
        pt.record_startup_phase('display_init', 99.0)
        assert kutu.olaylar == []
    finally:
        _temizle(orijinal)
    kutu, orijinal = _kur()
    try:
        pt.record_startup_phase('core_init', None)
        pt.record_startup_phase('core_init', 'x')
        assert kutu.olaylar == []
    finally:
        _temizle(orijinal)
