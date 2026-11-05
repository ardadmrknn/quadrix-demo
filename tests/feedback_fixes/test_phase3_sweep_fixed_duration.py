import pytest
from pathlib import Path
from sweep_effects import compute_line_sweep_progress_speed

pytestmark = [pytest.mark.quadrix_feedback, pytest.mark.quadrix_phase3]

# Kullanıcı geri bildirimi (2026-11-05): 180 ms "çok hızlı" bulundu; TGM/
# tetr.io hissine yakın orta hız 240 ms seçildi. Seviye bozunumu korunur.
SWEEP_BASE_DURATION_MS = 240.0


@pytest.mark.parametrize("travel", [640.0, 960.0, 1920.0])
def test_sweep_duration_is_resolution_independent(travel):
    speed = compute_line_sweep_progress_speed(0.12, travel, level=1)
    duration_ms = (1.0 / speed) * 1000.0
    assert duration_ms == pytest.approx(SWEEP_BASE_DURATION_MS, abs=5.0)


def test_sweep_duration_is_slower_than_the_rejected_180ms():
    """Regresyon kilidi: reddedilen 180 ms değerine geri dönülmemeli."""
    speed = compute_line_sweep_progress_speed(0.12, 960.0, level=1)
    assert (1.0 / speed) * 1000.0 > 200.0


def test_game_import_fallback_matches_sweep_effects_contract():
    """Import yedeği ana modülle AYNI süreyi üretmeli."""
    source = (Path(__file__).parents[2] / "src" / "game.py").read_text(encoding="utf-8")
    fallback = source.split("except Exception:\n    def _compute_line_sweep_progress_speed", 1)[1]
    fallback = fallback.split("from ui_scaling", 1)[0]
    assert "base_duration = 0.24" in fallback
    assert "travel_px / (block_speed * 3600.0)" not in fallback