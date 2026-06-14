import sys
import os
import pygame
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

# Set to 4
mode.board.lines_cleared = 4
mode.board.level = (mode.board.lines_cleared // 5) + 1
mode.card_manager.progress = mode.card_manager.threshold - 1
print('Starting level:', mode.board.level, 'progress', mode.card_manager.progress, 'pending', mode.pending_level_ups)

# Simulate call to notify - which should detect delta and set pending_level_ups
mode.board.lines_cleared += 1
mode.board.level = (mode.board.lines_cleared // 5) + 1
mode.card_manager.notify_lines_cleared(1)
print('After first notify: level', mode.board.level, 'progress', mode.card_manager.progress, 'pending', mode.pending_level_ups, 'last_enqueued', getattr(mode, 'last_enqueued_level', 'n/a'))

# Simulate second notify called (should not increment pending again)
mode.card_manager.notify_lines_cleared(0)
print('After second notify: level', mode.board.level, 'progress', mode.card_manager.progress, 'pending', mode.pending_level_ups, 'last_enqueued', getattr(mode, 'last_enqueued_level', 'n/a'))

# Now run update - overlay should open
mode.update(16)
print('After update: card_selection_active', mode.card_selection_active, 'pending', mode.pending_level_ups)

if mode.card_selection_active:
    mode._select_card(0)
    mode._finalize_pending_card_selection()
    print('After finalize: card_selection_active', mode.card_selection_active, 'pending', mode.pending_level_ups)

pygame.display.quit()