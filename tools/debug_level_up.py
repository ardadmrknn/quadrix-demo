import pygame
from src.game_modes_extra import MysteryMode
from src.user_manager import UserManager

# Minimal settings
class SimpleSettings:
    def get(self, key, default=None):
        if key == 'bg_transparency':
            return 0.3
        if key == 'resolution':
            return 'auto'
        if key == 'fullscreen':
            return False
        if key == 'card_mode_debug':
            return False
        return default

settings = SimpleSettings()
# Use temporary in-memory user manager but since constructor requires path, use default users.json
um = UserManager('src/users.json')
ok, _ = um.create_user('debug')
um.select_user('debug')
pygame.display.init()
pygame.display.set_mode((1, 1))
mode = MysteryMode(user_manager=um, settings_manager=settings)
mode.restart()

print('Initial level:', mode.board.level)
# Simulate lines_cleared at 4, increase by 1 to cause level-up
mode.board.lines_cleared = 4
mode.board.level = (mode.board.lines_cleared // 5) + 1
print('Set lines cleared to', mode.board.lines_cleared, 'level now', mode.board.level)
# Now increment lines to create level-up
mode.board.lines_cleared += 1
mode.board.level = (mode.board.lines_cleared // 5) + 1
print('Incremented lines to', mode.board.lines_cleared, 'level now', mode.board.level)
# Run update to trigger overlay
mode.update(16)
print('After update: card_selection_active:', mode.card_selection_active)
pygame.display.quit()