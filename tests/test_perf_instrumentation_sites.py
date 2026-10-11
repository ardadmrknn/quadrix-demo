# -*- coding: utf-8 -*-
"""PERF-1: enstrümantasyon noktaları kaynak-sözleşmesi (demo).

main.py startup alt fazları, geçiş (launch) fazları ve online_coop_game.py
coop ağ fazları telemetri çağrılarıyla işaretlenmiş olmalı. Bunlar davranış
DEĞİŞTİRMEZ — yalnızca ölçüm noktasıdır (rapor §9.2 PERF-01/PERF-04).
Kural: faz adları leaf kalır (`_total_` YOK — G-04 parent kuralı); launch
maliyeti ÇAĞRI-ANDAKİ state'e atfedilir. Demo, v2-only derin host-profiler
kanalını TAŞIMAZ (ölçüm kanalı perf_telemetry'dir, opt-in/bounded).
"""
from __future__ import annotations

import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
MAIN_SRC = (ROOT / 'src' / 'main.py').read_text(encoding='utf-8')
COOP_SRC = (ROOT / 'src' / 'online_coop_game.py').read_text(encoding='utf-8')

STARTUP_PHASES = (
    'settings_init', 'core_init', 'display_init', 'steam_init', 'views_init',
    'menu_construct', 'prewarm', 'splash', 'music_start', 'first_frame',
)
LAUNCH_PHASES = (
    'launch_game_ms', 'launch_pvp_ms', 'launch_coop_ms',
    'launch_online_coop_ms', 'launch_online_pvp_ms',
)
COOP_PHASES = (
    'coop_board_send_ms', 'coop_piece_send_ms', 'coop_board_apply_ms',
    'coop_piece_apply_ms', 'coop_draw_ms',
)
COOP_METRICS = (
    'coop_net_send_bytes_est', 'coop_board_send_full', 'coop_input_ack_count',
)


def test_startup_alt_fazlari_kayitli():
    """10 startup alt fazı record_startup_phase çağrısıyla işaretli."""
    for name in STARTUP_PHASES:
        assert f"record_startup_phase('{name}'" in MAIN_SRC, name


def test_launch_fazlari_cagri_noktalarinda():
    """Launch fazları çağrı-andaki state'e atfedilir: record_slow_phase(state,...)."""
    for name in LAUNCH_PHASES:
        assert f"record_slow_phase(state, '{name}'" in MAIN_SRC, name


def test_launch_cagri_noktasi_adetleri():
    """Kurulum blokları: game×2, pvp×2, coop×1, online_coop×1, online_pvp×2."""
    assert MAIN_SRC.count("'launch_game_ms'") == 2, 'menü + ekstralar classic'
    assert MAIN_SRC.count("'launch_pvp_ms'") == 2, 'menü + ekstralar pvp'
    assert MAIN_SRC.count("'launch_coop_ms'") == 1
    assert MAIN_SRC.count("'launch_online_coop_ms'") == 1
    assert MAIN_SRC.count("'launch_online_pvp_ms'") == 2, 'menü + ekstralar'


def test_first_frame_tek_seferlik_bayrakla():
    """first_frame tek seferlik: bayrak + tek kayıt (ilk çizilen kare)."""
    assert '_first_frame_done' in MAIN_SRC
    assert MAIN_SRC.count("record_startup_phase('first_frame'") == 1


def test_coop_ag_fazlari_ve_sayaclari():
    """PERF-04/R-09: coop ağ fazları + byte/full/ack sayaçları işaretli."""
    for name in COOP_PHASES:
        assert name in COOP_SRC, name
    for metric in COOP_METRICS:
        assert metric in COOP_SRC, metric


def test_faz_adlari_leaf_kalir():
    """G-04: hiçbir yeni faz adı `_total_` taşımaz (parent kuralına çarpmaz)."""
    for name in (*STARTUP_PHASES, *LAUNCH_PHASES, *COOP_PHASES):
        assert '_total_' not in name and not name.endswith('_total_ms')


def test_demo_profiler_kanali_tasimaz():
    """Demo, v2-only QUADRIX_COOP_HOST_PROFILE derin kanalını taşımaz;
    ölçüm kanalı perf_telemetry'dir (import noktada mevcut)."""
    assert 'import perf_telemetry' in COOP_SRC
    assert 'QUADRIX_COOP_HOST_PROFILE' not in COOP_SRC
    assert '_get_host_profiler' not in COOP_SRC
