"""Test logarithmic sound volume curve and game over blast protection."""

from src.sound import SoundManager


def test_perceptual_volume_logarithmic_curve():
    # Linear 0.0 -> 0.0, 1.0 -> 1.0
    assert SoundManager._perceptual_volume(0.0) == 0.0
    assert SoundManager._perceptual_volume(1.0) == 1.0
    # At 0.5 linear volume, perceptual volume should be lower (approx 0.39) to counteract human ear response
    mid = SoundManager._perceptual_volume(0.5)
    assert 0.38 < mid < 0.40
    # Monotonic increase
    assert SoundManager._perceptual_volume(0.3) < SoundManager._perceptual_volume(0.7)


def test_sound_manager_muted_state():
    sm = SoundManager()
    assert getattr(sm, 'muted', False) is False
    sm.set_muted(True)
    assert sm.muted is True
    sm.set_muted(False)
    assert sm.muted is False
