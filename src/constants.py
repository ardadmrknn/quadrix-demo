# Quadrix Oyunu Sabitleri

# Debug modu (oyun başlangıcında settings'ten yüklenecek)
DEBUG_MODE = False

# Pencere boyutları (başlangıç)
MIN_WINDOW_WIDTH = 800
MIN_WINDOW_HEIGHT = 600
DEFAULT_WINDOW_WIDTH = 500
DEFAULT_WINDOW_HEIGHT = 750

# Oyun tahtası boyutları
BOARD_WIDTH = 10
BOARD_HEIGHT = 20

# Quadrix 2 için genişletilmiş tahta
BOARD_WIDTH_T2 = 15  # Quadrix 2 için 15 blok genişlik
BOARD_HEIGHT_T2 = 20

# Panel oranları
INFO_PANEL_HEIGHT = 120  # Bilgi paneli için alt alan
SIDE_PANEL_WIDTH = 180   # Sağ panel için alan

# Renkler (RGB)
BLACK = (5, 5, 20)  # deep background for neon glow
WHITE = (255, 255, 255)
GRAY = (50, 50, 50)
DARK_GRAY = (20, 20, 20)

# Neon palette (Cyberpunk / Neon Arcade look)
NEON_CYAN = (0, 255, 221)
NEON_MAGENTA = (255, 0, 255)
NEON_ORANGE = (255, 165, 0)
NEON_LIME = (80, 255, 100)
NEON_BLUE = (112, 160, 255)

# Backwards-compatible names used through the code
CYAN = NEON_CYAN
MAGENTA = NEON_MAGENTA
ORANGE = NEON_ORANGE
BLUE = NEON_BLUE
GREEN = NEON_LIME
RED = (255, 50, 80)
YELLOW = (255, 200, 40)
PURPLE = (190, 80, 255)

# Tetromino renkleri (I, O, T, S, Z, J, L)
COLORS = [CYAN, YELLOW, PURPLE, GREEN, RED, BLUE, ORANGE]

# Oyun hızı (milisaniye)
INITIAL_FALL_SPEED = 800
FAST_FALL_SPEED = 50
DEFAULT_LOCK_DELAY = 500  # Ms cinsinden yere değdikten sonra kilitlenme süresi
SPEED_INCREASE_PER_LEVEL = 50

# Seviye bazli hiz egri capalari (ms)
# L20 -> 150ms, L30 -> 125ms
LEVEL_SPEED_TARGET_L20_MS = 150
LEVEL_SPEED_TARGET_L30_MS = 125
LEVEL_SPEED_MIN_MS = 100
LEVEL_SPEED_POST_L30_STEP_MS = 1


def get_level_fall_speed_ms(
    level,
    *,
    initial_speed=INITIAL_FALL_SPEED,
    level20_speed=LEVEL_SPEED_TARGET_L20_MS,
    level30_speed=LEVEL_SPEED_TARGET_L30_MS,
    min_speed=LEVEL_SPEED_MIN_MS,
    post_l30_step=LEVEL_SPEED_POST_L30_STEP_MS,
):
    """Hesaplanan dusus araligini (ms) seviyeye gore dondur.

    Ortak egri:
    - Level 1  -> initial_speed
    - Level 20 -> level20_speed
    - Level 30 -> level30_speed
    - 30+      -> her seviyede post_l30_step kadar azalir (min_speed'e kadar)
    """
    try:
        lvl = int(level)
    except Exception:
        lvl = 1
    lvl = max(1, lvl)

    initial = max(1, int(initial_speed))
    l20 = max(1, int(level20_speed))
    l30 = max(1, int(level30_speed))
    floor = max(1, int(min_speed))
    step = max(0, int(post_l30_step))

    # Monotonik hizlanma (ms degeri dusmeli) garantisi.
    l20 = min(l20, initial)
    l30 = min(l30, l20)

    if lvl <= 1:
        speed = float(initial)
    elif lvl <= 20:
        ratio = float(lvl - 1) / 19.0
        speed = float(initial) + (float(l20) - float(initial)) * ratio
    elif lvl <= 30:
        ratio = float(lvl - 20) / 10.0
        speed = float(l20) + (float(l30) - float(l20)) * ratio
    else:
        speed = float(l30 - (lvl - 30) * step)

    return max(floor, int(round(speed)))

# DAS (Delayed Auto Shift) - Yatay hareket için basılı tutma sistemi
DAS_DELAY = 200  # İlk hareket sonrası bekleme süresi (ms)
DAS_REPEAT = 200  # Tekrar hızı (ms) - ne kadar düşükse o kadar hızlı

# Font boyutları
FONT_SIZE_LARGE = 36
FONT_SIZE_MEDIUM = 28
FONT_SIZE_SMALL = 20

# Per-unit block score values used when calculating line-clear bonuses
# Assign integer scores per block type (units). These are tunable.
BLOCK_UNIT_POINTS = {
	'I': 5,
	'O': 4,
	'T': 4,
	'S': 3,
	'Z': 3,
	'J': 3,
	'L': 3,
	# Extras used in Tetris2
	'Plus': 6,
	'Y': 4,
	'Domino': 2,
	'BigSquare': 9,
}
