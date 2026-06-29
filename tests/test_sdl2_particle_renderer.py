import os
import sys


SRC_DIR = os.path.join(os.path.dirname(__file__), '..', 'src')
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

import sdl2_particle_renderer as renderer


def test_build_overlay_particle_batch_matches_cpu_particle_layers():
    batch = renderer.build_overlay_particle_batch(
        [{'x': 10, 'y': 20, 'life': 10, 'max_life': 10, 'size': 4, 'color': (100, 120, 140), 'glow': True}],
        (1920, 1080),
        board_left=0,
        board_right=100,
        board_bottom=100,
    )

    assert len(batch) == 5
    assert batch[0].radius == 8
    assert batch[-1].radius == 1


def test_queue_overlay_particles_falls_back_when_sdl2_unavailable(monkeypatch):
    monkeypatch.setattr(renderer, 'is_available', lambda: False)
    monkeypatch.setattr(renderer, '_pending_batch', (object(),))

    assert renderer.queue_overlay_particles([], (1920, 1080)) is False
    assert renderer._pending_batch == ()
    assert renderer.get_last_queue_stats()['queued'] is False


def test_queue_overlay_particles_falls_back_when_registration_fails(monkeypatch):
    monkeypatch.setattr(renderer, 'is_available', lambda: True)
    monkeypatch.setattr(renderer, '_registered', False)
    monkeypatch.setattr(renderer, '_pending_batch', (object(),))
    monkeypatch.setattr(renderer, '_ensure_registered', lambda: None)

    assert renderer.queue_overlay_particles([], (1920, 1080)) is False
    assert renderer._pending_batch == ()
    assert renderer.get_last_queue_stats()['queued'] is False
