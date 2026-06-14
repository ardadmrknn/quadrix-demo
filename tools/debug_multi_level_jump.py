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

# Scenario: jump from level 1 to level 3 by adding 10 lines
mode.board.lines_cleared = 0
mode.board.level = (mode.board.lines_cleared // 5) + 1
mode.last_enqueued_level = mode.board.level
print('Initial:', 'board.level', mode.board.level, 'pending', mode.pending_level_ups, 'last_enqueued', mode.last_enqueued_level)
# Add 10 lines
mode.board.lines_cleared += 10
mode.board.level = (mode.board.lines_cleared // 5) + 1
# Notify the manager (in game this happens from lock_and_new_piece)
mode.card_manager.notify_lines_cleared(10)
print('After notify: board.level', mode.board.level, 'pending', mode.pending_level_ups, 'last_enqueued', mode.last_enqueued_level)
# Now run update so overlay opens sequentially
mode.update(16)
print('After update 1: card_selection_active?', mode.card_selection_active, 'pending', mode.pending_level_ups)
if mode.card_selection_active:
    # finalize first selection
    mode._select_card(0)
    mode._finalize_pending_card_selection()
    print('After finalize 1: card_selection_active', mode.card_selection_active, 'pending', mode.pending_level_ups)
# next update should open next overlay if pending
mode.update(16)
print('After update 2: card_selection_active?', mode.card_selection_active, 'pending', mode.pending_level_ups)
if mode.card_selection_active:
    mode._select_card(0)
    mode._finalize_pending_card_selection()
    print('After finalize 2: card_selection_active', mode.card_selection_active, 'pending', mode.pending_level_ups)
pygame.display.quit()