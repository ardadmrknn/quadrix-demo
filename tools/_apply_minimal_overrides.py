"""_LEVEL_OVERRIDES bloğunu minimal versiyonla değiştir."""
import sys

with open('src/campaign/level_data.py', 'r', encoding='utf-8') as f:
    content = f.read()

MARKER_START = '\n# ──────────────────────────────────────────────────────────────────────────────\n# TAM SEVİYE OVERRIDE TABLOSU'
# End marker: iki boş satır + def _generate_level (kapanış '}' dahil)
MARKER_END = '\n}\n\n\ndef _generate_level(level: int)'

idx_start = content.find(MARKER_START)
idx_end = content.find(MARKER_END)

if idx_start == -1 or idx_end == -1:
    print(f"HATA: Başlangıç={idx_start}, Bitiş={idx_end}")
    sys.exit(1)

# idx_end sonrası '\n}\n\n\ndef...' olduğundan son '}' content[idx_end:]'de var.
# NEW_BLOCK son '}' olmadan biter; content[idx_end:] onu sağlar.
print(f"Blok bulundu: satır ~{content[:idx_start].count(chr(10))+1} - satır ~{content[:idx_end].count(chr(10))+1}")
print(f"Blok boyutu: {idx_end - idx_start} karakter")

NEW_BLOCK = '''
# ──────────────────────────────────────────────────────────────────────────────
# LEVEL OVERRIDE TABLOSU
# Sadece auto-gen'den FARKLI olan alanlar belirtilmiştir.
# 'move_limit': None → limit yok | int → o limit | anahtar yoksa auto-calc
# 'time_limit': None → süresiz  | int → saniye   | anahtar yoksa auto-calc
# ──────────────────────────────────────────────────────────────────────────────
_LEVEL_OVERRIDES: Dict[int, Dict[str, Any]] = {
    # ─── DÜNYA 1: BAŞLANGIÇ VADİSİ ────────────────────
    1:   {'objectives': [_obj_lines(3)], 'move_limit': None, 'stars': {1: _cs(), 2: _mc(2), 3: _ct(110)}},
    2:   {'objectives': [_obj_lines(4)], 'move_limit': 19, 'stars': {1: _cs(), 2: _cm(1), 3: _ct(110)}},
    3:   {'objectives': [_obj_lines(5)], 'stars': {1: _cs(), 2: _mc(2), 3: _cm(1)}},
    4:   {'move_limit': None, 'time_limit': 100, 'stars': {1: _cs(), 2: _cm(1), 3: _mv(21)}},
    5:   {'stars': {1: _cs(), 2: _mc(2), 3: _ct(100)}},
    6:   {'move_limit': 24, 'stars': {1: _cs(), 2: _cm(1), 3: _cm(2)}},
    7:   {'objectives': [_obj_score(2100)], 'move_limit': 34, 'stars': {1: _cs(), 2: _mc(2), 3: _ct(90)}},
    8:   {'move_limit': 24, 'stars': {1: _cs(), 2: _cm(1), 3: _ct(80)}},
    9:   {'objectives': [_obj_lines(8)], 'move_limit': None, 'time_limit': 120, 'stars': {1: _cs(), 2: _mc(2), 3: _cm(2)}},
    10:  {'move_limit': 39, 'stars': {1: _cs(), 2: _cm(2), 3: _ct(75)}},            # BOSS
    11:  {'objectives': [_obj_score(2300)], 'move_limit': 42, 'stars': {1: _cs(), 2: _cm(2), 3: _ct(80)}},
    12:  {'objectives': [_obj_multi_clear(3)], 'move_limit': 35, 'stars': {1: _cs(), 2: _cm(1), 3: _ct(100)}},
    13:  {'move_limit': 42, 'garbage_rows': 2, 'stars': {1: _cs(), 2: _cm(2), 3: _ct(75)}},
    14:  {'move_limit': 42, 'stars': {1: _cs(), 2: _mv(28), 3: _ct(80)}},
    15:  {'objectives': [_obj_lines(13)], 'move_limit': 39, 'stars': {1: _cs(), 2: _mc(3), 3: _cm(2)}},
    16:  {'objectives': [_obj_score(3000)], 'move_limit': 39, 'stars': {1: _cs(), 2: _cm(2), 3: _ct(75)}},
    17:  {'objectives': [_obj_tetris(1)], 'move_limit': None, 'stars': {1: _cs(), 2: _mv(28), 3: _ct(85)}},
    18:  {'move_limit': 34, 'stars': {1: _cs(), 2: _mc(3), 3: _cm(2)}},
    19:  {'move_limit': None, 'time_limit': 75, 'stars': {1: _cs(), 2: _mv(26), 3: _ct(55)}},
    20:  {'move_limit': 60, 'time_limit': 90, 'stars': {1: _cs(), 2: _cm(2), 3: _ct(75)}},  # BOSS
    # ─── DÜNYA 2: BUZ DİYARI ──────────────────────────
    21:  {'objectives': [_obj_lines(14)], 'move_limit': 36, 'stars': {1: _cs(), 2: _mc(3), 3: _cm(2)}},
    22:  {'objectives': [_obj_score(3500)], 'move_limit': 60, 'time_limit': 70, 'stars': {1: _cs(), 2: _cm(2), 3: _ct(60)}},
    23:  {'objectives': [_obj_tetris(1)], 'move_limit': 30, 'stars': {1: _cs(), 2: _ct(90), 3: _ct(75)}},
    24:  {'move_limit': 40, 'stars': {1: _cs(), 2: _mc(3), 3: _cm(2)}},
    25:  {'stars': {1: _cs(), 2: _mv(50), 3: _ct(80)}},
    26:  {'objectives': [_obj_lines(15)], 'move_limit': 60, 'stars': {1: _cs(), 2: _cm(2), 3: _ct(85)}},
    27:  {'objectives': [_obj_score(7000)], 'stars': {1: _cs(), 2: _mc(3), 3: _cm(2)}},
    28:  {'objectives': [_obj_lines(6)], 'move_limit': None, 'time_limit': 30, 'garbage_rows': 0, 'stars': {1: _cs(), 2: _mc(2), 3: _ct(25)}},
    29:  {'objectives': [_obj_score(3000)], 'move_limit': None, 'time_limit': 50, 'stars': {1: _cs(), 2: _cm(1), 3: _ct(40)}},
    30:  {'objectives': [_obj_tetris(2)], 'move_limit': 80, 'time_limit': 150, 'stars': {1: _cs(), 2: _cm(1), 3: _ct(120)}},  # BOSS
    # ─── DÜNYA 2 (devam) ──────────────────────────────
    31:  {'garbage_rows': 4, 'stars': {1: _cs(), 2: _cm(2), 3: _ct(60)}},
    32:  {'objectives': [_obj_combo(3), _obj_special_block(4)]},
    33:  {'stars': {1: _cs(), 2: _cm(3), 3: _cm(3)}},
    34:  {'stars': {1: _cs(), 2: _cm(3), 3: _ct(58)}},
    35:  {'stars': {1: _cs(), 2: _cm(3), 3: _ct(58)}},
    36:  {'objectives': [_obj_score(4600), _obj_special_block(5)], 'stars': {1: _cs(), 2: _qx(), 3: _cm(3)}},
    37:  {'stars': {1: _cs(), 2: _cm(3), 3: _ct(57)}},
    38:  {'stars': {1: _cs(), 2: _cm(3), 3: _ct(56)}},
    39:  {'stars': {1: _cs(), 2: _cm(3), 3: _cm(3)}},
    40:  {'objectives': [_obj_lines(32), _obj_special_block(5)]},  # BOSS
    # ─── DÜNYA 3: LAV MAĞARASI ────────────────────────
    41:  {'stars': {1: _cs(), 2: _cm(3), 3: _ct(55)}},
    42:  {'stars': {1: _cs(), 2: _cm(3), 3: _cm(3)}},
    43:  {'stars': {1: _cs(), 2: _cm(3), 3: _ct(54)}},
    # L44: auto-gen ile aynı, override yok
    45:  {'objectives': [_obj_garbage(), _obj_special_block(2)], 'stars': {1: _cs(), 2: _cm(3), 3: _cm(3)}},
    46:  {'stars': {1: _cs(), 2: _cm(3), 3: _ct(52)}},
    47:  {'stars': {1: _cs(), 2: _cm(3), 3: _ct(52)}},
    48:  {'stars': {1: _cs(), 2: _qx(), 3: _cm(3)}},
    49:  {'stars': {1: _cs(), 2: _cm(3), 3: _ct(51)}},
    50:  {'objectives': [_obj_score(9000), _obj_special_block(3)], 'stars': {1: _cs(), 2: _cm(3), 3: _ct(50)}},  # BOSS
    51:  {'stars': {1: _cs(), 2: _cm(3), 3: _cm(3)}},
    # L52: auto-gen ile aynı, override yok
    53:  {'stars': {1: _cs(), 2: _cm(3), 3: _ct(49)}},
    54:  {'stars': {1: _cs(), 2: _cm(3), 3: _cm(3)}},
    55:  {'objectives': [_obj_survival(170), _obj_special_block(3)], 'stars': {1: _cs(), 2: _cm(3), 3: _ct(48)}},
    # L56: auto-gen ile aynı, override yok
    57:  {'stars': {1: _cs(), 2: _cm(3), 3: _cm(3)}},
    58:  {'stars': {1: _cs(), 2: _cm(3), 3: _ct(46)}},
    59:  {'stars': {1: _cs(), 2: _cm(3), 3: _ct(46)}},
    60:  {'objectives': [_obj_tetris(6), _obj_special_block(4)], 'stars': {1: _cs(), 2: _qx(), 3: _cm(3)}},  # BOSS
    # ─── DÜNYA 4: FIRTINA KALESİ ──────────────────────
    61:  {'stars': {1: _cs(), 2: _cm(4), 3: _ct(45)}},
    62:  {'stars': {1: _cs(), 2: _cm(4), 3: _ct(45)}},
    63:  {'stars': {1: _cs(), 2: _cm(4), 3: _cm(3)}},
    64:  {'stars': {1: _cs(), 2: _cm(4), 3: _ct(44)}},
    65:  {'stars': {1: _cs(), 2: _qx(2), 3: _ct(44)}},
    66:  {'stars': {1: _cs(), 2: _cm(4), 3: _cm(3)}},
    67:  {'stars': {1: _cs(), 2: _cm(4), 3: _ct(44)}},
    68:  {'stars': {1: _cs(), 2: _cm(4), 3: _ct(43)}},
    69:  {'stars': {1: _cs(), 2: _cm(4), 3: _cm(3)}},
    70:  {'stars': {1: _cs(), 2: _qx(2), 3: _ct(43)}},  # BOSS
    71:  {'stars': {1: _cs(), 2: _cm(4), 3: _ct(43)}},
    72:  {'stars': {1: _cs(), 2: _cm(4), 3: _cm(3)}},
    73:  {'stars': {1: _cs(), 2: _cm(4), 3: _ct(42)}},
    74:  {'stars': {1: _cs(), 2: _cm(4), 3: _ct(42)}},
    75:  {'stars': {1: _cs(), 2: _qx(2), 3: _cm(3)}},
    76:  {'stars': {1: _cs(), 2: _cm(4), 3: _ct(41)}},
    77:  {'stars': {1: _cs(), 2: _cm(4), 3: _ct(41)}},
    78:  {'stars': {1: _cs(), 2: _cm(4), 3: _cm(3)}},
    79:  {'stars': {1: _cs(), 2: _cm(4), 3: _ct(41)}},
    80:  {'stars': {1: _cs(), 2: _qx(2), 3: _ct(40)}},  # BOSS
    # ─── DÜNYA 5: YILDIZ KULESİ ───────────────────────
    81:  {'stars': {1: _cs(), 2: _cm(4), 3: _cm(3)}},
    82:  {'stars': {1: _cs(), 2: _cm(4), 3: _ct(40)}},
    83:  {'stars': {1: _cs(), 2: _cm(4), 3: _ct(40)}},
    84:  {'stars': {1: _cs(), 2: _cm(4), 3: _cm(3)}},
    85:  {'stars': {1: _cs(), 2: _qx(2), 3: _ct(39)}},
    86:  {'stars': {1: _cs(), 2: _cm(4), 3: _ct(39)}},
    87:  {'stars': {1: _cs(), 2: _cm(4), 3: _cm(3)}},
    88:  {'stars': {1: _cs(), 2: _cm(4), 3: _ct(38)}},
    89:  {'stars': {1: _cs(), 2: _cm(4), 3: _ct(38)}},
    90:  {'stars': {1: _cs(), 2: _qx(2), 3: _cm(3)}},  # BOSS
    91:  {'stars': {1: _cs(), 2: _cm(4), 3: _ct(38)}},
    92:  {'stars': {1: _cs(), 2: _cm(4), 3: _ct(37)}},
    93:  {'stars': {1: _cs(), 2: _cm(4), 3: _cm(3)}},
    94:  {'stars': {1: _cs(), 2: _cm(4), 3: _ct(37)}},
    95:  {'stars': {1: _cs(), 2: _qx(2), 3: _ct(37)}},
    96:  {'stars': {1: _cs(), 2: _cm(4), 3: _cm(3)}},
    97:  {'stars': {1: _cs(), 2: _cm(4), 3: _ct(36)}},
    98:  {'stars': {1: _cs(), 2: _cm(4), 3: _ct(36)}},
    99:  {'stars': {1: _cs(), 2: _cm(4), 3: _cm(3)}},
    100: {'stars': {1: _cs(), 2: _qx(2), 3: _ct(35)}},  # BOSS
'''

new_content = content[:idx_start] + NEW_BLOCK + content[idx_end:]

with open('src/campaign/level_data.py', 'w', encoding='utf-8') as f:
    f.write(new_content)

print("Dosya güncellendi.")
print(f"Eski boyut: {len(content)} karakter")
print(f"Yeni boyut: {len(new_content)} karakter")
print(f"Azalma: {len(content) - len(new_content)} karakter")
