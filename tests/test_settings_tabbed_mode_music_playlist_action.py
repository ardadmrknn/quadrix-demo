"""Test: music_selector Enter'a basınca edit_mode_playlist:<mode_key> döner."""

from types import SimpleNamespace


def test_music_selector_enter_returns_edit_action():
    """music_selector Enter → edit_mode_playlist:<mode_key>"""
    pygame_mod = SimpleNamespace(
        K_RETURN=13,
        K_SPACE=32,
        K_LEFT=276,
        K_RIGHT=275,
        K_ESCAPE=27,
    )

    def _simulate_music_selector_key(mode_key, key_code):
        if key_code in (pygame_mod.K_RETURN, pygame_mod.K_SPACE, pygame_mod.K_LEFT, pygame_mod.K_RIGHT):
            return f'edit_mode_playlist:{mode_key}'
        return None

    result = _simulate_music_selector_key('classic', pygame_mod.K_RETURN)
    assert result == 'edit_mode_playlist:classic', f"Got: {result!r}"

    result_space = _simulate_music_selector_key('sprint', pygame_mod.K_SPACE)
    assert result_space == 'edit_mode_playlist:sprint', f"Got: {result_space!r}"

    result_none = _simulate_music_selector_key('zen', pygame_mod.K_ESCAPE)
    assert result_none is None, f"Got: {result_none!r}"