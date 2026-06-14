"""Faz 4 — Mini-boss missing queue purge testleri.

_purge_missing_piece_from_queue helper'ı next_piece_queue ve current_piece'tan
missing parçayı yeni filtreden parçalarla değiştirir. Bu test helper'ın
davranışını izole edilmiş ortamda doğrular.
"""
from __future__ import annotations

import pathlib
import sys


ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / 'src'

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from campaign.campaign_mode import CampaignMode


class _FakePiece:
    def __init__(self, name):
        self.name = name


def _make_mode_with_queue(queue_names, current_name=None, missing_name='I'):
    mode = object.__new__(CampaignMode)
    mode._missing_piece_name = missing_name
    mode.next_piece_queue = [_FakePiece(n) for n in queue_names]
    mode.current_piece = _FakePiece(current_name) if current_name else None

    # spawn_new_piece stub: _allowed_pieces'tan ilkini döndür (filtreli)
    mode._allowed_pieces = ['O', 'T', 'S', 'Z', 'J', 'L']  # I missing
    spawn_counter = {'i': 0}

    def fake_spawn():
        # Filter sonrası _allowed_pieces'tan deterministik döndür
        idx = spawn_counter['i'] % len(mode._allowed_pieces)
        spawn_counter['i'] += 1
        return _FakePiece(mode._allowed_pieces[idx])

    mode.spawn_new_piece = fake_spawn
    return mode


def test_purge_replaces_missing_piece_in_queue():
    """next_piece_queue'da missing parça olursa filtreden parça ile değişir."""
    mode = _make_mode_with_queue(queue_names=['I', 'O', 'I', 'T'], missing_name='I')
    CampaignMode._purge_missing_piece_from_queue(mode)
    queue_names = [p.name for p in mode.next_piece_queue]
    assert 'I' not in queue_names, f"Queue'da hâlâ 'I' var: {queue_names}"
    assert len(queue_names) == 4, "Queue uzunluğu korunmalı"


def test_purge_replaces_missing_piece_in_current_piece():
    """current_piece missing ise yeni parça ile değişir."""
    mode = _make_mode_with_queue(queue_names=['O', 'T'], current_name='I', missing_name='I')
    # _position_piece_at_spawn yoksa pas geç (defansif)
    CampaignMode._purge_missing_piece_from_queue(mode)
    assert mode.current_piece is not None
    assert mode.current_piece.name != 'I', (
        f"current_piece hâlâ missing: {mode.current_piece.name}"
    )


def test_purge_does_not_modify_clean_queue():
    """Queue'da missing yoksa değişmemeli."""
    mode = _make_mode_with_queue(queue_names=['O', 'T', 'S'], missing_name='I')
    original = [p.name for p in mode.next_piece_queue]
    CampaignMode._purge_missing_piece_from_queue(mode)
    final = [p.name for p in mode.next_piece_queue]
    assert original == final, f"Temiz queue değişti: {original} → {final}"


def test_purge_helper_handles_missing_piece_name_none():
    """missing_piece_name None ise helper sessizce çıkar."""
    mode = object.__new__(CampaignMode)
    mode._missing_piece_name = None
    mode.next_piece_queue = []
    # Exception fırlatmaz
    CampaignMode._purge_missing_piece_from_queue(mode)


def test_purge_helper_handles_empty_queue():
    """next_piece_queue boşsa helper sessizce çıkar."""
    mode = object.__new__(CampaignMode)
    mode._missing_piece_name = 'I'
    mode.next_piece_queue = []
    # Exception fırlatmaz
    CampaignMode._purge_missing_piece_from_queue(mode)
