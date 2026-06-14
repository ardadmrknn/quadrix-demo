import sys
import os
import pygame
# Add src directory to sys.path
repo_root = os.path.dirname(os.path.dirname(__file__))
src_path = os.path.join(repo_root, 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)
from game_modes_extra import MysteryMode
from user_manager import UserManager

class SimpleSettings:
    def get(self, key, default=None):
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

# Set progress to threshold-1
mode.card_manager.progress = mode.card_manager.threshold - 1
print('progress before:', mode.card_manager.progress, 'threshold:', mode.card_manager.threshold)
# Now trigger a single line clear
mode.card_manager.notify_lines_cleared(1)
print('progress now:', mode.card_manager.progress, 'pending_level_ups (initial):', getattr(mode, 'pending_level_ups', 'n/a'))
# Now call update to allow the game to enqueue/open overlay
mode.update(16)
print('after update: pending_level_ups:', getattr(mode, 'pending_level_ups', 'n/a'))
# Force prepare to open overlay
if getattr(mode, 'pending_level_ups', 0) > 0:
    mode.card_manager.prepare_selection()
    if mode.card_manager.pending_choices:
        mode._open_card_selection()
        print('Overlay opened: card_selection_active=', mode.card_selection_active)
pygame.display.quit()
