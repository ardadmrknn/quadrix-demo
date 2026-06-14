import sys
import os
import pygame
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, repo_root)
# Add src directory as well for top-level relative imports
sys.path.insert(0, os.path.join(repo_root, 'src'))
from src.game_modes_extra import MysteryMode
from src.game import Game
from src.user_manager import UserManager

class SimpleSettings:
    def get(self, key, default=None):
        if key == 'bg_transparency':
            return 0.3
        if key == 'resolution':
            return 'auto'
        if key == 'fullscreen':
            return False
        if key == 'debug_mode':
            return True
        return default
    def get_controls(self):
        return {'single_player': {}}
    def get_music_preference_for_mode(self, mode):
        return 'Quadrix'

users_file = 'tools/debug_users.json'
um = UserManager(users_file)
um.create_user('tester')
um.select_user('tester')
settings = SimpleSettings()
mode = MysteryMode(user_manager=um, settings_manager=settings, sound_enabled=False, effects_enabled=False)
print('initial last_enqueued:', mode.last_enqueued_level, 'board.level:', mode.board.level)

# Patch Game.update to bump level after original update
original_update = Game.update

def patched_update(self, dt):
    try:
        original_update(self, dt)
    except Exception:
        pass
    self.board.level += 1

Game.update = patched_update
mode.update(16)
print('post update pending_level_ups:', mode.pending_level_ups)
print('pending_choices len:', len(mode.card_manager.pending_choices))
print('card_selection_active:', mode.card_selection_active)

# Trigger prepare_selection by clearing lines
from src.board import Board
mode.board.level += 1
mode.update(16)
print('after bump 2 pending_level_ups:', mode.pending_level_ups)
print('pending_choices len:', len(mode.card_manager.pending_choices))
print('card_selection_active:', mode.card_selection_active)

pygame.quit()
