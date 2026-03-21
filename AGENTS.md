# Agent Configuration

## Plan Directory
plans/

## Project Overview
- **Type:** Pygame-based Tetris game (Quadrix) with Steam integration
- **Language:** Python 3.12
- **Framework:** Pygame 2.x
- **Source Directory:** `src/`
- **Tests:** `tests/` altındaki `test_*.py` dosyaları, `pytest` veya `scripts/test/run_tests.sh` ile çalıştırılır
- **Entry Point:** `main.py` (Turkish), `src/main_en.py` (English fallback)
- **Build:** `scripts/build/build_macos_app.sh`, spec files `packaging/specs/` altında

## Key Subsystems

### Core Game Engine
- **Game Loop:** `src/game.py`, `src/board.py`, `src/pieces.py`
- **PvP Mode:** `src/pvp_game.py`
- **Game Modes:** `src/game_modes.py`, `src/game_modes_advanced.py`, `src/game_modes_extra.py`
- **Gameplay Settings:** `src/gameplay_settings.py`
- **Constants:** `src/constants.py`

### Campaign System
- **Entry:** `src/campaign/campaign_mode.py` — in-game loop, objective/star tracking
- **Level Select:** `src/campaign/level_select.py` — font scale: `max(0.72, min(1.0, w/1400, h/900))`
- **Level Data:** `src/campaign/level_data.py`
- **Objectives:** `src/campaign/objectives.py`
- **Power-ups:** `src/campaign/power_ups.py`
- **Special Blocks:** `src/campaign/special_blocks.py`
- **Campaign UI:** `src/campaign/campaign_ui.py`

### UI / Menu
- **Main Menu:** `src/menu.py` — dashboard tiles, `_menu_panel_content_scale()` (ref: 1920×1080), `_draw_main_dashboard_tile()`
- **Extras / Game Modes Screen:** `src/extras_menu.py` — `_extras_ui_scale()`, mod kartları
- **Guide / Kılavuz Screen:** `src/guide_screen.py` — oyun modları kılavuzu, kart galerisi
- **Settings:** `src/settings_screen_tabbed.py`
- **Graphics Menu:** `src/graphics_menu.py`
- **UI Components:** `src/ui_components.py`
- **UI Theme:** `src/ui_theme.py` — `UIFonts`, `UIColors`, `UIStyle`
- **Retro Style:** `src/retro_style.py` — `get_font()`, `draw_glass_panel()`, `get_fitting_font()`
- **Splash Screen:** `src/splash_screen.py`, `src/splashscreen/`
- **Menu Layout:** `src/menu_layout_embedded.py`

### Rendering & Visuals
- **Renderers:** `src/renderers/jelly_renderer.py`
- **Block Styles:** `src/block_styles.py`
- **Themes:** `src/themes.py`
- **Mode Skins:** `src/mode_skins.py`
- **Background Effects:** `src/background_effects.py`, `src/background.py`
- **Emoji Renderer:** `src/emoji_renderer.py`
- **Text Cache:** `src/text_cache.py`

### User & Profile
- **User Management:** `src/user_manager.py`
- **User Screens:** `src/user_screens.py` — avatar `_circle_crop_surface()` (center-crop)
- **Avatar Editor:** `src/avatar_editor.py`, `src/avatar_presets.py`
- **Score Manager:** `src/score_manager.py`
- **Achievements:** `src/achievements.py` — 6 kampanya yıldız başarımı dahil

### Audio
- **Sound:** `src/sound.py` — `set_music_playlist(shuffle=False)` ile shuffle desteği

### Steam & Backend
- **Steam Integration:** `src/steam_integration.py`
- **Steam Leaderboards:** `src/steam_leaderboards.py`
- **Backend Proxy:** `backend/steam_leaderboard_proxy.py`

### Localization & Language
- **Localization:** `src/localization.py` — `t()` fonksiyonu
- **UI Language Profile:** `src/ui_language_profile.py` — CJK font desteği
- **Desteklenen diller:** TR, EN, DE, FR, ES, IT, PT, RU, JA, ZH, KO

### Input & Platform
- **Gamepad:** `src/gamepad_manager.py`
- **Platform Utils:** `src/platform_utils.py`
- **File Dialog:** `src/file_dialog.py`
- **Tk Compat:** `src/tk_compat.py`

### Misc
- **Asset Manager:** `src/asset_manager.py`
- **Atomic IO:** `src/atomic_io.py`
- **Data Paths:** `src/data_paths.py`
- **Version:** `src/version.py`
- **Piece Workshop:** `src/piece_workshop.py`, `src/workshop_blocks.py`
- **Tutorial:** `src/tutorial.py`
- **Color Picker:** `src/color_picker.py`
- **Timer Window:** `src/timer_window.py`

## Conventions
- Tüm kaynak kod `src/` altında; `src/campaign/` alt paketi kampanya sistemine aittir
- Ayarlar `src/settings_manager.py` ve `settings.txt` üzerinden yönetilir
- Testler `tests/` altında `test_*.py` deseniyle; `pytest` veya `./scripts/test/run_tests.sh -q` ile çalıştırılır
- Web frontend yok; tüm UI Pygame tabanlıdır (Frontend-Engineer-subagent KULLANILMAZ)
- Font ölçekleme: `menu.py` → `_menu_panel_content_scale()` (1920×1080 ref), `level_select.py` → `max(0.72, min(1.0, w/1400, h/900))`, `extras_menu.py` → `_extras_ui_scale()` (base_window_size ref)
- `UIFonts` sınıfı (`src/ui_theme.py`) tüm in-game UI fontlarının tek kaynağıdır
- Müzik shuffle: `settings_manager` → `music_shuffle` key; `sound.set_music_playlist(shuffle=...)` ile aktif edilir
- Başarım tetikleme: `src/campaign/campaign_mode.py` `_save_progress()` sonunda çağrılır
