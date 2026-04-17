import pathlib
import sys
import types


ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / 'src'

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import board as board_module
import game as game_module


class _SoundStub:
    def __init__(self):
        self.music_enabled = True
        self.stop_music_calls = 0
        self.unduck_calls = 0

    def stop_music(self):
        self.stop_music_calls += 1

    def unduck_music(self):
        self.unduck_calls += 1


class _BoardStub:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.grid = [[object() for _ in range(width)] for _ in range(height)]
        self.texture_grid = [[object() for _ in range(width)] for _ in range(height)]
        self.occupancy = [[True for _ in range(width)] for _ in range(height)]


def _build_game_for_restart():
    game = game_module.Game.__new__(game_module.Game)
    game.board_width = 4
    game.board_height = 6
    game.spawn_new_piece = lambda: types.SimpleNamespace(x=0, y=0)
    game._skip_hidden_rows = lambda piece: None
    game.get_initial_speed = lambda: 123
    game.apply_theme_to_pieces = lambda: None
    game.create_ambient_particles = lambda: None
    game.sound = _SoundStub()
    game.sound_enabled = False
    game.effects_enabled = False
    game.game_over_warning = 'warn'
    game.game_over_warning_timer = 4.2
    game._piece_bag = [1]
    game._last_piece_identity = 'I'
    game._last_piece_streak = 2
    game.held_piece = object()
    game.second_held_piece = object()
    game.can_hold = False
    game.can_hold2 = False
    game.discard_held_uses = 0
    game.game_over = True
    game.paused = True
    game.fall_time = 8
    game.game_time = 16
    game.line_clear_animation = 1
    game.combo_message = 'combo'
    game.combo_message_time = 5
    game.particles = [object()]
    game.achievement_notifications = [object()]
    game.current_music_track = 'old-track'
    game.line_clear_sweep_rows = [1]
    game.line_clear_sweep_progress = 0.5
    game.line_clear_sweep_active = True
    game.line_clear_pending_rows = [1]
    game.line_clear_pending_colors = {1: ['x']}
    game.falling_block_animations = [object()]
    game.drop_trails = [object()]
    game._game_over_active = True
    game._game_over_pending = True
    game._game_over_peek_active = True
    game._game_over_peek_rect = object()
    game._game_over_click_targets = {'restart': object()}
    game._game_over_start_time = 99
    game._final_score = 10
    game._final_lines = 2
    game._final_level = 3
    game._final_tetrises = 1
    game._final_time = 77
    game._earned_stars = 2.0
    game._last_star_sound = 1
    game._displayed_score = 9
    game._confetti_particles = [object()]
    game._confetti_active = True
    game._game_over_fade_alpha = 255
    game._is_new_record = True
    game._start_music_playlist_calls = []
    game._start_music_playlist = lambda force=False: game._start_music_playlist_calls.append(force)
    return game


def test_restart_restarts_music_when_sfx_disabled(monkeypatch):
    game = _build_game_for_restart()

    monkeypatch.setattr(board_module, 'Board', _BoardStub)

    game.restart()

    assert game.sound.unduck_calls == 1
    assert game.sound.stop_music_calls == 1
    assert game._start_music_playlist_calls == [True]
