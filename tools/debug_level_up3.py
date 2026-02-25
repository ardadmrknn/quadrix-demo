import sys
import os
import pygame
# Add src directory to sys.path for module imports
repo_root = os.path.dirname(os.path.dirname(__file__))
src_path = os.path.join(repo_root, 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)
from game_modes_extra import MysteryMode
from user_manager import UserManager
from game import Game

class SimpleSettings:
    def get(self, key, default=None):
        if key == 'card_mode_debug':
            return False
        if key == 'bg_transparency':
            return 0.3
        if key == 'resolution':
            return 'auto'
        if key == 'fullscreen':
            return False
        return default
    def get_controls(self):
        return {'single_player': {}}
    def get_music_preference_for_mode(self, mode):
        return 'Quadrix'

users_file = os.path.join(src_path, 'users.json')
um = UserManager(users_file)
ok, _ = um.create_user('debug')
um.select_user('debug')

pygame.display.init()
pygame.display.set_mode((1,1))
mode = MysteryMode(user_manager=um, settings_manager=SimpleSettings())
mode.restart()

# Set board to 4 cleared lines so one more will level us up
mode.board.lines_cleared = 4
mode.board.level = (mode.board.lines_cleared // 5) + 1
print('Starting level:', mode.board.level, 'lines:', mode.board.lines_cleared)

orig_lock = Game.lock_and_new_piece

def patched_lock_and_new_piece(self):
    try:
        # Simulate a line clear during this lock
        self.board.lines_cleared += 1
        # Ensure level recalc
        self.board.level = (self.board.lines_cleared // 5) + 1
    except Exception as e:
        print('patch error', e)
    # Call original functionality to avoid breaking further logic
    try:
        orig_lock(self)
    except Exception:
        pass

Game.lock_and_new_piece = patched_lock_and_new_piece

# now call update which will call patched lock inside the normal flow
mode.update(16)
print('After update: level:', mode.board.level, 'pending_level_ups:', getattr(mode, 'pending_level_ups', 'N/A'), 'card_selection_active:', mode.card_selection_active)
pygame.display.quit()