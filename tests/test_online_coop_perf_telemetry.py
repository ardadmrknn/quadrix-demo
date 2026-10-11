# -*- coding: utf-8 -*-
"""PERF-04/R-09: online_coop ağ telemetrisi davranış sözleşmesi (demo).

`_send_board_state` heartbeat'i her zaman ölçüm kanalına yazar: süre fazı
(coop_board_send_ms) + byte tahmini (coop_net_send_bytes_est) + tam anlık
görüntü sayacı (coop_board_send_full — desync toparlama vekili). Ack
ilerlemesi coop_input_ack_count olarak sayılır. Demo telemetrisi opt-in
olduğundan ölçüm çağrıları kayıt kapısına takılmadan spy'lanır.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import perf_telemetry  # noqa: E402
import online_coop_game as coop_module  # noqa: E402


class _FakeNet:
    def __init__(self):
        self.sent = []

    def send(self, data, reliable=True, channel=0):
        self.sent.append((data, reliable, channel))
        return True


def _make_host_game(net):
    game = coop_module.OnlineCoopGame.__new__(coop_module.OnlineCoopGame)
    game.net = net
    game.role = 'host'
    game.coop_game = SimpleNamespace(
        team_score=10, total_lines_cleared=3, level=1, fall_speed=500.0,
        p1_frozen=False, p2_frozen=True,
    )
    game._board_state_seq = 0
    game._last_input_ack_seq = 5
    game._last_guest_piece_state_seq = 2
    game._last_sent_board_cells = None
    # __new__ ile kurulan oyunda gerçek board yok — hücre yakalama/serileştirme
    # tarafı stub'lanır (ölçümlenen nokta telemetri çağrılarıdır).
    game._capture_semantic_board_cells = lambda: {(0, 1): ('T', 3)}
    game._serialize_semantic_board_cells = lambda items: [[0, 1, 'T', 3]]
    game._build_authoritative_gameplay_config = lambda: {}
    return game


def _telemetry_spies(monkeypatch):
    slow = Mock()
    metric = Mock()
    monkeypatch.setattr(perf_telemetry, 'record_slow_phase', slow)
    monkeypatch.setattr(perf_telemetry, 'record_metric', metric)
    return slow, metric


def test_send_board_state_full_snapshot_telemetri_yazar(monkeypatch):
    slow, metric = _telemetry_spies(monkeypatch)
    net = _FakeNet()
    game = _make_host_game(net)

    game._send_board_state()

    assert len(net.sent) == 1
    data, reliable, channel = net.sent[0]
    assert data['full'] is True, 'ilk gönderim tam anlık görüntüdür'
    assert reliable is False and channel == coop_module.CHANNEL_STATE
    slow.assert_called_once()
    assert slow.call_args.args[:2] == ('online_coop', 'coop_board_send_ms')
    metric_calls = {c.args[:2] for c in metric.call_args_list}
    assert ('online_coop', 'coop_net_send_bytes_est') in metric_calls
    assert ('online_coop', 'coop_board_send_full') in metric_calls
    # Byte tahmini profiler formülüyle aynı: hücre×32 + 256.
    bytes_calls = [c for c in metric.call_args_list
                   if c.args[:2] == ('online_coop', 'coop_net_send_bytes_est')]
    assert bytes_calls[0].args[2] == 1 * 32 + 256


def test_send_board_state_delta_full_sayac_yazmaz(monkeypatch):
    slow, metric = _telemetry_spies(monkeypatch)
    net = _FakeNet()
    game = _make_host_game(net)
    # Önceki gönderimle aynı hücreler → semantic delta, full snapshot YOK.
    game._last_sent_board_cells = {(0, 1): ('T', 3)}

    game._send_board_state()

    assert len(net.sent) == 1
    assert net.sent[0][0]['full'] is False
    slow.assert_called_once()
    full_calls = [c for c in metric.call_args_list
                  if c.args[:2] == ('online_coop', 'coop_board_send_full')]
    assert full_calls == [], 'delta gönderiminde full sayacı artmamalı'


def test_consume_guest_input_ack_ilerleme_sayac(monkeypatch):
    slow, metric = _telemetry_spies(monkeypatch)
    game = coop_module.OnlineCoopGame.__new__(coop_module.OnlineCoopGame)
    game._last_input_ack_seq = 4
    game._guest_pending_inputs = []

    game._consume_guest_input_ack(7)
    ack_calls = [c for c in metric.call_args_list
                 if c.args[:2] == ('online_coop', 'coop_input_ack_count')]
    assert len(ack_calls) == 1 and ack_calls[0].args[2] == 1
    assert game._last_input_ack_seq == 7

    # İlerlemeyen ack sayaç yazmaz (heartbeat tekrarı sessiz kalır).
    metric.reset_mock()
    game._consume_guest_input_ack(7)
    ack_calls = [c for c in metric.call_args_list
                 if c.args[:2] == ('online_coop', 'coop_input_ack_count')]
    assert ack_calls == []
