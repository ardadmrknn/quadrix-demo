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

print('Initial board level:', mode.board.level, 'lines_cleared:', mode.board.lines_cleared)
mode.board.lines_cleared = 4
mode.board.level = (mode.board.lines_cleared // 5) + 1
print('Set lines_cleared to 4 -> level:', mode.board.level)
# Now simulate 1 line gained during a lock
mode.board.lines_cleared += 1
mode.board.level = (mode.board.lines_cleared // 5) + 1
print('After increment lines_cleared:', mode.board.lines_cleared, 'level:', mode.board.level)
mode.update(16)
print('After update: card_selection_active:', mode.card_selection_active, 'pending_level_ups:', getattr(mode, 'pending_level_ups', 'N/A'))
pygame.display.quit()
