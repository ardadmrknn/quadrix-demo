from __future__ import annotations

import importlib
import json
import sys

import pytest


def test_projected_scale_cache_is_bounded_and_invalidated(monkeypatch):
    module = importlib.import_module('ui_scaling')
    module._PROJECTED_SCALE_CACHE.clear()
    monkeypatch.setattr(module, '_get_effective_projection_ratio', lambda *args, **kwargs: 1.0)
    monkeypatch.setattr(module, 'resolve_ui_scale_size', lambda *args, **kwargs: (1920, 1080))

    for index in range(module._PROJECTED_SCALE_CACHE_MAX + 8):
        module.get_projected_effective_scale(
            (1920 + index, 1080),
            min_scale=0.68,
            max_scale=1.20,
            reference_size=(1920.0, 1080.0),
        )
    assert len(module._PROJECTED_SCALE_CACHE) == module._PROJECTED_SCALE_CACHE_MAX

    module.set_ui_scale_preset('large')
    assert not module._PROJECTED_SCALE_CACHE
    module.set_ui_scale_preset('normal')


def test_overlay_metrics_keep_panel_and_buttons_inside_surface():
    pygame = pytest.importorskip('pygame')
    module = importlib.import_module('ui_scaling')
    metrics = module.calculate_overlay_metrics((640, 360), 1.0, 8)
    panel = metrics['panel_rect']
    assert panel.left >= 0 and panel.top >= 0
    assert panel.right <= 640 and panel.bottom <= 360
    assert len(metrics['button_rects']) == 8
    assert all(panel.contains(rect) for rect in metrics['button_rects'])


def test_overlay_metrics_keep_every_button_inside_tiny_surfaces():
    pygame = pytest.importorskip('pygame')
    module = importlib.import_module('ui_scaling')
    for size in ((160, 100), (240, 160), (320, 240)):
        metrics = module.calculate_overlay_metrics(size, 1.0, 8)
        panel = metrics['panel_rect']
        assert panel.left >= 0 and panel.top >= 0
        assert panel.right <= size[0] and panel.bottom <= size[1]
        assert all(panel.contains(rect) for rect in metrics['button_rects'])


def test_telemetry_disabled_path_does_not_create_file(monkeypatch, tmp_path):
    monkeypatch.delenv('QUADRIX_PERF_TELEMETRY', raising=False)
    monkeypatch.setenv('QUADRIX_DATA_DIR', str(tmp_path))
    sys.modules.pop('perf_telemetry', None)
    module = importlib.import_module('perf_telemetry')
    assert module.is_enabled() is False
    module.record_startup()
    module.begin_frame('menu', clock_ms=16, fps_limit=60)
    module.end_frame('menu', did_draw=True)
    assert not list(tmp_path.rglob('*.jsonl'))


def test_telemetry_enabled_path_is_local_and_bounded(monkeypatch, tmp_path):
    monkeypatch.setenv('QUADRIX_PERF_TELEMETRY', '1')
    monkeypatch.setenv('QUADRIX_DATA_DIR', str(tmp_path))
    sys.modules.pop('perf_telemetry', None)
    module = importlib.import_module('perf_telemetry')
    assert module.is_enabled() is True
    module.record_startup()
    module.begin_frame('menu', clock_ms=16, fps_limit=60)
    module.record_phase('menu', 'handler_ms', 1.5)
    module.end_frame('menu', did_draw=True)
    module.flush_all('test')
    path = module.telemetry_path()
    assert str(tmp_path) in path
    records = [json.loads(line) for line in open(path, encoding='utf-8') if line.strip()]
    assert records
    assert all('cwd' not in item and 'telemetry_path' not in item for item in records)
