# Agent Configuration

## Plan Directory
plans/

## Project Overview
- **Type:** Pygame-based Tetris game with Steam integration
- **Language:** Python 3.12
- **Framework:** Pygame
- **Source Directory:** `src/`
- **Tests:** Root-level `test_*.py` files, run with `pytest`
- **Entry Point:** `main.py`

## Key Subsystems
- **Game Engine:** `src/game.py`, `src/board.py`, `src/pieces.py`
- **Game Modes:** `src/game_modes.py`, `src/game_modes_advanced.py`, `src/game_modes_extra.py`
- **Campaign:** `src/campaign/`
- **UI/Menu:** `src/menu.py`, `src/ui_components.py`, `src/settings_screen_tabbed.py`
- **Rendering:** `src/renderers/`, `src/block_styles.py`, `src/themes.py`
- **Steam:** `src/steam_integration.py`, `src/steam_leaderboards.py`, `backend/`
- **Audio:** `src/sound.py`
- **Localization:** `src/localization.py`
- **User Management:** `src/user_manager.py`, `src/score_manager.py`, `src/achievements.py`

## Conventions
- All source code is in `src/`
- Settings are managed via `src/settings_manager.py` and `settings.txt`
- Tests follow `test_*.py` pattern in root directory
- No web frontend; all UI is Pygame-based (do NOT use Frontend-Engineer-subagent)
- Turkish and English localization supported
