"""Smoke test: tüm temel modülleri import et ve hızlı kontrol yap."""
import sys, os
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

errors = []

# 1) Settings Manager
print("=== 1. Settings Manager ===")
try:
    import settings_manager
    sm = settings_manager.SettingsManager.__init__
    print("  OK")
except SyntaxError as e:
    errors.append(f"settings_manager SYNTAX: {e}")
    print(f"  SYNTAX ERROR: {e}")
except Exception as e:
    errors.append(f"settings_manager: {e}")
    print(f"  ERROR: {e}")

# 2) Board
print("=== 2. Board ===")
try:
    from board import Board
    b = Board()
    assert b.width == 10 and b.height == 20, f"Unexpected size {b.width}x{b.height}"
    print(f"  OK: {b.width}x{b.height}")
except Exception as e:
    errors.append(f"board: {e}")
    print(f"  ERROR: {e}")

# 3) Pieces
print("=== 3. Pieces ===")
try:
    from pieces import create_piece_by_name, SHAPE_NAMES
    for name in SHAPE_NAMES:
        p = create_piece_by_name(name)
        cells = p.get_cells()
        assert len(cells) > 0, f"{name} has 0 cells"
    print(f"  OK: {len(SHAPE_NAMES)} shapes")
except Exception as e:
    errors.append(f"pieces: {e}")
    print(f"  ERROR: {e}")

# 4) Board logic: line clearing
print("=== 4. Line Clearing ===")
try:
    from board import Board
    from constants import BLACK
    b2 = Board(width=10, height=20)
    # Tüm en alt satırı doldur
    for x in range(10):
        b2.occupancy[19][x] = True
        b2.grid[19][x] = (255, 0, 0)
    cleared = b2.clear_lines()
    assert cleared == 1, f"Expected 1 line cleared, got {cleared}"
    # Sonra alt satır boş olmalı
    assert not any(b2.occupancy[19]), "Bottom row should be clear after clearing"
    print(f"  OK: {cleared} line cleared")
except Exception as e:
    errors.append(f"line_clearing: {e}")
    print(f"  ERROR: {e}")

# 5) Board logic: is_valid_position
print("=== 5. Position Validation ===")
try:
    from board import Board
    from pieces import create_piece_by_name
    b3 = Board(width=10, height=20)
    
    # Normal parça, sınır içinde = OK
    p1 = create_piece_by_name('T')
    p1.x, p1.y = 3, 0
    assert b3.is_valid_position(p1), "T at (3,0) should be valid"
    
    # Normal parça, sol sınır dışı = FAIL
    p2 = create_piece_by_name('I')
    p2.x, p2.y = -1, 0
    assert not b3.is_valid_position(p2), "I at (-1,0) should be invalid"
    
    # Esnek sınırlı parça, sol sınır 1 blok dışı = OK
    p3 = create_piece_by_name('I')
    p3.x, p3.y = -1, 0
    p3.flexible_border = True
    assert b3.is_valid_position(p3), "I at (-1,0) with flexible_border should be valid"
    
    print("  OK: all position checks passed")
except Exception as e:
    errors.append(f"position_validation: {e}")
    print(f"  ERROR: {e}")

# 6) Score calculation
print("=== 6. Scoring ===")
try:
    from board import Board
    b4 = Board(width=10, height=20)
    b4.level = 1
    # 4 satır doldur (tetris)
    for row in range(16, 20):
        for x in range(10):
            b4.occupancy[row][x] = True
            b4.grid[row][x] = (0, 255, 0)
    cleared = b4.clear_lines()
    assert cleared == 4, f"Expected 4, got {cleared}"
    assert b4.score == 800, f"Expected 800 (tetris at level 1), got {b4.score}"
    assert b4.tetrises == 1, f"Expected 1 tetris, got {b4.tetrises}"
    print(f"  OK: score={b4.score}, tetrises={b4.tetrises}")
except Exception as e:
    errors.append(f"scoring: {e}")
    print(f"  ERROR: {e}")

# 7) Game modes import
print("=== 7. Game Modes ===")
for mod_name in ['game_modes', 'game_modes_extra', 'game_modes_advanced']:
    try:
        __import__(mod_name)
        print(f"  {mod_name}: OK")
    except Exception as e:
        errors.append(f"{mod_name}: {e}")
        print(f"  {mod_name}: ERROR - {e}")

# 8) Localization
print("=== 8. Localization ===")
try:
    from localization import set_language, t, get_language
    set_language('tr')
    assert get_language() == 'tr'
    tr_val = t('mode_classic')
    set_language('en')
    en_val = t('mode_classic')
    print(f"  TR: '{tr_val}', EN: '{en_val}'")
    assert tr_val and en_val, "Translation keys missing"
    print("  OK")
except Exception as e:
    errors.append(f"localization: {e}")
    print(f"  ERROR: {e}")

# 9) Sound manager
print("=== 9. Sound ===")
try:
    import pygame
    pygame.init()
    from sound import SoundManager
    sm = SoundManager()
    print(f"  OK: enabled={sm.enabled}")
except Exception as e:
    errors.append(f"sound: {e}")
    print(f"  ERROR: {e}")

# 10) Score manager
print("=== 10. Score Manager ===")
try:
    from score_manager import ScoreManager
    print("  OK")
except Exception as e:
    errors.append(f"score_manager: {e}")
    print(f"  ERROR: {e}")

# 11) Constants sanity
print("=== 11. Constants ===")
try:
    from constants import BOARD_WIDTH, BOARD_HEIGHT, COLORS, BLACK
    assert BOARD_WIDTH == 10, f"BOARD_WIDTH={BOARD_WIDTH}"
    assert BOARD_HEIGHT == 20, f"BOARD_HEIGHT={BOARD_HEIGHT}"
    assert len(COLORS) >= 7, f"Only {len(COLORS)} colors"
    print(f"  OK: {BOARD_WIDTH}x{BOARD_HEIGHT}, {len(COLORS)} colors")
except Exception as e:
    errors.append(f"constants: {e}")
    print(f"  ERROR: {e}")

# 12) Combo / B2B logic
print("=== 12. Combo & Back-to-Back ===")
try:
    from board import Board
    b5 = Board(width=10, height=20)
    b5.level = 1
    # İlk satır temizle
    for x in range(10):
        b5.occupancy[19][x] = True
        b5.grid[19][x] = (255, 0, 0)
    b5.clear_lines()
    assert b5.combo == 1, f"Combo should be 1 after first clear, got {b5.combo}"
    
    # İkinci satır temizle (combo devam)
    for x in range(10):
        b5.occupancy[19][x] = True
        b5.grid[19][x] = (0, 255, 0)
    b5.clear_lines()
    assert b5.combo == 2, f"Combo should be 2 after second clear, got {b5.combo}"
    
    # Boş temizle (combo sıfırlanmalı)
    b5.clear_lines()
    assert b5.combo == 0, f"Combo should reset to 0, got {b5.combo}"
    print(f"  OK: combo chain works")
except Exception as e:
    errors.append(f"combo: {e}")
    print(f"  ERROR: {e}")

# 13) Campaign import
print("=== 13. Campaign ===")
try:
    from campaign import CampaignMode, CampaignLevelSelect
    print("  OK")
except Exception as e:
    errors.append(f"campaign: {e}")
    print(f"  ERROR: {e}")

# SUMMARY
print("\n" + "=" * 50)
if errors:
    print(f"SONUÇ: {len(errors)} HATA BULUNDU!")
    for e in errors:
        print(f"  ❌ {e}")
else:
    print("SONUÇ: TÜM TESTLER GEÇTİ ✅")
print("=" * 50)
