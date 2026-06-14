import importlib
import sys


def test_gamepad_manager_module_aliases_to_singleton_module():
    sys.modules.pop('gamepad_manager', None)
    sys.modules.pop('src.gamepad_manager', None)

    package_mod = importlib.import_module('src.gamepad_manager')
    top_level_mod = importlib.import_module('gamepad_manager')

    assert package_mod is top_level_mod
    assert sys.modules['src.gamepad_manager'] is sys.modules['gamepad_manager']


def test_card_freeze_action_is_registered_in_gamepad_defaults():
    gamepad_mod = importlib.import_module('gamepad_manager')

    assert 'card_freeze' in gamepad_mod.DEFAULT_GAMEPAD_BINDINGS
    assert gamepad_mod.DEFAULT_GAMEPAD_BINDINGS['card_freeze']['button'] == 1
    assert gamepad_mod.ACTION_TO_KEY['card_freeze'] == gamepad_mod.pygame.K_f
