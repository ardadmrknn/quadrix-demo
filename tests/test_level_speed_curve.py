from constants import get_level_fall_speed_ms


def test_level_speed_curve_hits_requested_anchors_for_800_start():
    assert get_level_fall_speed_ms(1, initial_speed=800) == 800
    assert get_level_fall_speed_ms(20, initial_speed=800) == 150
    assert get_level_fall_speed_ms(30, initial_speed=800) == 125


def test_level_speed_curve_hits_requested_anchors_for_900_start():
    assert get_level_fall_speed_ms(1, initial_speed=900) == 900
    assert get_level_fall_speed_ms(20, initial_speed=900) == 150
    assert get_level_fall_speed_ms(30, initial_speed=900) == 125


def test_level_speed_curve_is_monotonic_non_increasing():
    speeds = [get_level_fall_speed_ms(level, initial_speed=900) for level in range(1, 80)]
    for prev, nxt in zip(speeds, speeds[1:]):
        assert nxt <= prev


def test_level_speed_curve_post_l30_step_and_floor():
    assert get_level_fall_speed_ms(31, initial_speed=900) == 124
    assert get_level_fall_speed_ms(55, initial_speed=900) == 100
    assert get_level_fall_speed_ms(80, initial_speed=900) == 100
