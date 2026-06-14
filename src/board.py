"""Clean Board implementation for the repository.

Provides a single canonical Board class supporting the following features used
by Mystery Mode and unit tests:
- occupancy and texture grids
- per-cell gold flags (Alchemist perk)
- cascade gravity (apply_gravity)
- clearing top rows (ghost echo)
- converting random cells to gold (convert_to_gold)
"""
from typing import List, Tuple
import os
from block_styles import TextureSlice
from constants import BOARD_WIDTH, BOARD_HEIGHT, BLACK, BLOCK_UNIT_POINTS


_DEBUG_CLEAR_LINES = os.environ.get("TETRIS_DEBUG_CLEAR_LINES", "0") == "1"


class Board:
    def __init__(self, width: int | None = None, height: int | None = None):
        self.width = width or BOARD_WIDTH
        self.height = height or BOARD_HEIGHT
        self.grid: List[List[Tuple[int, int, int]]] = [[BLACK for _ in range(self.width)] for _ in range(self.height)]
        self.texture_grid: List[List[object | None]] = [[None for _ in range(self.width)] for _ in range(self.height)]
        self.owners: List[List[str | None]] = [[None for _ in range(self.width)] for _ in range(self.height)]
        self.occupancy: List[List[bool]] = [[False for _ in range(self.width)] for _ in range(self.height)]
        self.gold: List[List[bool]] = [[False for _ in range(self.width)] for _ in range(self.height)]
        self.score = 0
        self.lines_cleared = 0
        # Lines that contribute to level progression. Some card/ability effects may
        # intentionally increment `lines_cleared` for stats/achievements without
        # allowing farming level-ups.
        self.level_lines_cleared = 0
        self.level_lines_per_level = 5
        self.level = 1
        self.combo = 0
        self.tetrises = 0
        self.last_cleared_lines: List[int] = []
        self.last_cleared_colors: dict[int, List[Tuple[int, int, int]]] = {}  # {row: [colors...]}
        # Esnek Sınır perk'i aktif mi? (kalıcı perk)
        self.flexible_border_active: bool = False
        # Quadrix scoring state
        self.back_to_back = False
        # Lock-out state: sticky game-over flag + last lock result.
        self._locked_out: bool = False
        self._last_lock_out: bool = False

    def _cell_filled(self, x: int, y: int) -> bool:
        return self.occupancy[y][x]

    def is_valid_position(self, piece, dx: int = 0, dy: int = 0) -> bool:
        # Esnek sınır: Board'daki flag VEYA parçadaki flag aktifse genişletilmiş sınır
        # SADECE sol ve sağ kenarlar için geçerli, alt/üst normal
        flexible_border = self.flexible_border_active or getattr(piece, 'flexible_border', False)
        border_extend = 1 if flexible_border else 0
        
        for px, py in piece.get_cells():
            px += dx
            py += dy
            # Sol ve sağ sınır kontrolü (esnek sınır ile genişletilmiş)
            if px < -border_extend or px >= self.width + border_extend:
                return False
            # Alt sınır kontrolü (NORMAL - esnek sınır UYGULANMAZ)
            if py >= self.height:
                return False
            # Üst sınır kontrolü (negatif y'ye izin verme)
            if py < 0:
                continue
            # Eğer hücre tahta dışındaysa (esnek sınır sayesinde) occupancy kontrolü yapma
            if px < 0 or px >= self.width:
                continue
            # If piece has tunneling/drilling active, ignore occupancy checks so it can pass through blocks
            if self._cell_filled(px, py) and not (getattr(piece, 'tunnel', False) or getattr(piece, 'drill', False)):
                return False
        return True

    def lock_piece(self, piece, *, track_game_over: bool = True) -> int:
        self._last_lock_out = False

        # Esnek Sınır artık lock anında yatay snap yapmaz. Tahta dışında kalan
        # hücreler görünmez alanda bırakılır; yalnızca görünür alana düşen hücreler yazılır.
        lock_dx = 0

        piece_w = len(piece.shape[0]) if piece.shape else 0
        piece_h = len(piece.shape) if piece.shape else 0
        color_matrix = getattr(piece, 'color_matrix', None)
        style_name = (
            getattr(piece, 'style_key', None)
            or getattr(piece, '_board_style_name', None)
            or getattr(piece, 'name', None)
        )
        # Görünür alanın üstünde (y < 0) yazılamayan dolu hücre kaldı mı? (top-out)
        _overflow_top = False
        for ly, row in enumerate(piece.shape):
            for lx, c in enumerate(row):
                if not c:
                    continue
                x = piece.x + lx + lock_dx
                y = piece.y + ly
                if y < 0:
                    # Tepe taşması: hücre yazılamaz (silinmez de — top-out sinyali).
                    _overflow_top = True
                    continue
                if 0 <= x < self.width and y < self.height:
                    cell_color = piece.color
                    if color_matrix is not None:
                        try:
                            cm_val = color_matrix[ly][lx]
                            if cm_val is not None:
                                cell_color = cm_val
                        except Exception:
                            pass
                    self.grid[y][x] = cell_color
                    self.occupancy[y][x] = True
                    self.gold[y][x] = getattr(piece, 'is_gold', False)
                    # record piece owner for per-block scoring
                    self.owners[y][x] = getattr(piece, 'name', None)
                    if style_name and callable(TextureSlice):
                        self.texture_grid[y][x] = TextureSlice(
                            str(style_name),
                            rel_x=lx,
                            rel_y=ly,
                            width=piece_w or 1,
                            height=piece_h or 1,
                            rotation=getattr(piece, 'rotation_state', 0),
                        )
                    else:
                        self.texture_grid[y][x] = None
        
        cleared = self.clear_lines()

        # Lock-out kuralı: satır temizlikleri bittikten sonra en üst GÖRÜNÜR satırda
        # (row 0) dolu hücre kaldıysa game-over. Ek olarak, görünür alanın üstüne
        # taşıp yazılamayan hücre (top-out) varsa da game-over. Negatif/gizli satır
        # "dokunma" mantığı kaldırıldı (haksız ölümü önlemek için kural net biçimde
        # görünür row 0'a bağlandı).
        if _overflow_top or any(self._cell_filled(x, 0) for x in range(self.width)):
            self._last_lock_out = True
            if track_game_over:
                self._locked_out = True

        return cleared

    def clear_lines(self, source: str = "player") -> int:
        """Tüm dolu satırları tek seferde sil (cascade dahil).

        `source`:
        - "player": normal oyun akışı (level ilerlemesi ve combo reset davranışı uygulanır)
        - "card" / "ability" / diğer: dış kaynaklı temizlik (level ilerlemesini tetiklemez; satır yoksa combo resetlenmez)
        """
        # Optional debug logging (disabled by default; expensive when enabled)
        if _DEBUG_CLEAR_LINES:
            try:
                import traceback
                _debug_has_full_row = any(
                    all(self._cell_filled(x, y) for x in range(self.width))
                    for y in range(self.height)
                )
                if _debug_has_full_row:
                    print("\n" + "=" * 60)
                    print("[DEBUG] clear_lines(): full row detected")
                    print("Call Stack (last 5):")
                    for line in traceback.format_stack()[-6:-1]:
                        print(line.strip())
                    print("=" * 60 + "\n")
            except Exception:
                pass
        
        total_lines = 0
        all_cleared_rows: List[int] = []
        all_gold_lines: dict[int, bool] = {}
        all_unit_points: dict[int, int] = {}
        # Cascade boyunca temizlenen satır renkleri (efekt için). Bu çağrıya özel
        # yerel birikimdir; cascade turları arası aynı row indeksi tekrar
        # temizlenirse ilk turun renkleri korunur (setdefault).
        cascade_colors: dict[int, List[Tuple[int, int, int]]] = {}
        
        # CASCADE LOOP: Satır silindikten sonra yeni dolu satırlar oluşabilir, onları da sil
        while True:
            lines_to_clear: List[int] = []
            for y in range(self.height):
                if all(self._cell_filled(x, y) for x in range(self.width)):
                    lines_to_clear.append(y)
            
            if not lines_to_clear:
                break  # Artık silinecek satır yok
            
            # Gold ve unit point bilgilerini topla
            for y in lines_to_clear:
                all_gold_lines[y] = any(self.gold[y][x] for x in range(self.width))
                unit_total = 0
                for x in range(self.width):
                    if self.occupancy[y][x]:
                        owner = self.owners[y][x]
                        if owner:
                            unit_total += BLOCK_UNIT_POINTS.get(owner, 1)
                all_unit_points[y] = unit_total
            
            all_cleared_rows.extend(lines_to_clear)
            total_lines += len(lines_to_clear)
            
            # Satır renklerini efekt için kaydet (silmeden ÖNCE)
            # Cascade'in ardışık turlarında satırlar yukarı kaydığından aynı row
            # indeksi birden çok turda temizlenebilir. İlk turda kaydedilen renkleri
            # koru (üzerine yazma) ki cascade boyunca temizlenen satır renkleri
            # kaybolmasın.
            for y in lines_to_clear:
                cascade_colors.setdefault(
                    y, [self.grid[y][x] for x in range(self.width)]
                )
            
            # Satırları sil (üstten alta doğru - reverse=True ile indeks kayması önlenir)
            # ÖNEMLİ: Önce tüm satırları sil, SONRA boş satırları ekle!
            # Böylece del/insert döngüsünde indeks kayması olmaz.
            num_to_clear = len(lines_to_clear)
            for y in sorted(lines_to_clear, reverse=True):
                del self.grid[y]
                del self.texture_grid[y]
                del self.occupancy[y]
                del self.gold[y]
                del self.owners[y]
            
            # Silinen satır sayısı kadar üste boş satır ekle
            for _ in range(num_to_clear):
                self.grid.insert(0, [BLACK for _ in range(self.width)])
                self.texture_grid.insert(0, [None for _ in range(self.width)])
                self.occupancy.insert(0, [False for _ in range(self.width)])
                self.gold.insert(0, [False for _ in range(self.width)])
                self.owners.insert(0, [None for _ in range(self.width)])
        
        self.last_cleared_lines = all_cleared_rows
        if total_lines > 0:
            self.last_cleared_colors = cascade_colors
        
        # Puan hesaplama
        # Puan hesaplama
        if total_lines > 0:
            self.lines_cleared += total_lines
            
            # --- SCORING RULES ---
            # 1. Base Points (Nintendo Guideline-ish)
            # 1: 100, 2: 300, 3: 500, 4: 800
            points = [0, 100, 300, 500, 800]
            base_score = points[min(total_lines, 4)] * self.level
            
            # 2. Combo Bonus (Scaled by Level)
            # Old: (combo - 1) * 50
            # New: combo * 50 * level (rewards chaining more)
            if self.combo > 0:
                combo_bonus = self.combo * 50 * self.level
            else:
                combo_bonus = 0
            self.combo += 1  # Increment combo for NEXT clear
            
            # 3. Back-to-Back Bonus (Quadrix only)
            if total_lines >= 4:
                self.tetrises += 1
                if self.back_to_back:
                    # B2B Quadrix: 1.5x base score
                    base_score = int(base_score * 1.5)
                    # print(f"🔥 Back-to-Back Quadrix! (+{base_score})")
                self.back_to_back = True
            else:
                # Clear B2B if it wasn't a Quadrix (unless we add T-Spins later)
                self.back_to_back = False

            # 4. Perfect Clear Bonus
            # Check if grid is empty
            if all(not any(row) for row in self.occupancy):
                 # print("✨ PERFECT CLEAR!")
                 base_score += 3000 * self.level

            # 5. Gold & Unit Points (Mode specific)
            per_line = base_score / total_lines if total_lines > 0 else 0
            gold_count = sum(1 for y in all_cleared_rows if all_gold_lines.get(y, False))
            extra = int(per_line * 4 * gold_count) if gold_count > 0 else 0
            unit_points_total = sum(all_unit_points.get(y, 0) for y in all_cleared_rows)
            
            # Final Score Summation
            self.score += base_score + combo_bonus + extra + int(unit_points_total * self.level)
            
            if str(source).lower() in {"player", "normal"}:
                try:
                    self.level_lines_cleared += total_lines
                except Exception:
                    self.level_lines_cleared = int(getattr(self, 'level_lines_cleared', 0) or 0) + int(total_lines)
                try:
                    lines_per_level = max(1, int(getattr(self, 'level_lines_per_level', 5) or 5))
                except Exception:
                    lines_per_level = 5
                self.level = (int(getattr(self, 'level_lines_cleared', self.lines_cleared)) // lines_per_level) + 1
        else:
            # Dış kaynaklı temizlikler combo'yu bozmasın.
            if str(source).lower() in {"player", "normal"}:
                self.combo = 0
        return total_lines

    def apply_gravity(self) -> None:
        # Collapse floating blocks downward per column
        for x in range(self.width):
            write = self.height - 1
            for read in range(self.height - 1, -1, -1):
                if self.occupancy[read][x]:
                    if read != write:
                        self.grid[write][x] = self.grid[read][x]
                        self.texture_grid[write][x] = self.texture_grid[read][x]
                        self.occupancy[write][x] = True
                        self.gold[write][x] = self.gold[read][x]
                        self.owners[write][x] = self.owners[read][x]
                        self.grid[read][x] = BLACK
                        self.texture_grid[read][x] = None
                        self.occupancy[read][x] = False
                        self.gold[read][x] = False
                        self.owners[read][x] = None
                    write -= 1

    def compute_tunnel_target(self, piece) -> int | None:
        """Compute the final y coordinate for a tunneled piece.

        Finds the row where the piece would come to rest if it fell straight down
        ignoring intermediate occupancy (i.e., tunneling through blocks). Returns
        the integer y position of the piece (top-left y) where it should land,
        or None if no suitable landing position is found.
        """
        try:
            offsets = [(lx, ly) for ly, row in enumerate(piece.shape) for lx, c in enumerate(row) if c]
            if not offsets:
                return None
            # For each local column in the piece, determine its bottom-most cell
            columns: dict[int, int] = {}
            for ox, oy in offsets:
                columns[ox] = max(columns.get(ox, -999), oy)
            candidates = []
            # For every covered column, compute where the piece would land
            for ox, bottom_local in columns.items():
                board_x = piece.x + ox
                # If out of board horizontally, abort
                if board_x < 0 or board_x >= self.width:
                    return None
                search_y = piece.y + bottom_local + 1
                found = None
                # Guard against negative indexing when the piece is above the visible board.
                for y in range(max(0, int(search_y)), self.height):
                    if self.occupancy[y][board_x]:
                        found = y
                        break
                if found is None:
                    # no block found - floor is at self.height - 1
                    landing = (self.height - 1) - bottom_local
                else:
                    landing = (found - 1) - bottom_local
                # Never "teleport" upwards as part of tunneling; only allow landing
                # at or below the current top-left y.
                landing = max(int(landing), int(getattr(piece, 'y', 0) or 0), 0)
                candidates.append(landing)
            # The final y must be the minimal landing (so that all columns don't overlap)
            dest_y = min(candidates)
            return dest_y
        except Exception:
            return None
        

    def clear_top_rows(self, n: int = 6) -> None:
        n = max(0, min(n, self.height))
        for y in range(n):
            for x in range(self.width):
                self.grid[y][x] = BLACK
                self.texture_grid[y][x] = None
                self.occupancy[y][x] = False
                self.gold[y][x] = False
                self.owners[y][x] = None

    def convert_to_gold(self, count: int = 3) -> None:
        candidates = [(x, y) for y in range(self.height) for x in range(self.width) if self.occupancy[y][x] and not self.gold[y][x]]
        # Prefer lower rows to make gold blocks more likely to appear in future clears
        candidates.sort(key=lambda p: p[1], reverse=True)
        if not candidates:
            return
        import random
        chosen = []
        for y_group in range(0, len(candidates), max(1, len(candidates)//5)):
            chosen.extend(candidates[y_group:y_group+max(1, len(candidates)//5)])
        chosen = chosen[:len(candidates)]
        for x, y in random.sample(chosen, min(count, len(chosen))):
            self.gold[y][x] = True
            self.grid[y][x] = (212, 175, 55)  # gold-like color

    def is_game_over(self) -> bool:
        """Tetris Guideline lock-out: True when a piece locked at or above top row."""
        return self._locked_out

    def consume_last_lock_out(self) -> bool:
        """Return whether the most recent lock produced a lock-out and clear that event."""
        last_lock_out = self._last_lock_out
        self._last_lock_out = False
        return last_lock_out

    def clear_lock_out(self) -> None:
        """Clear both sticky and per-lock lock-out flags."""
        self._locked_out = False
        self._last_lock_out = False

    def mark_locked_out(self) -> None:
        """Force the board into a lock-out state for modes that resolve it manually."""
        self._locked_out = True
        self._last_lock_out = True

    def get_grid_state(self) -> List[List[int]]:
        return [[1 if c else 0 for c in row] for row in self.occupancy]

    def reset(self) -> None:
        self.grid = [[BLACK for _ in range(self.width)] for _ in range(self.height)]
        self.texture_grid = [[None for _ in range(self.width)] for _ in range(self.height)]
        self.occupancy = [[False for _ in range(self.width)] for _ in range(self.height)]
        self.gold = [[False for _ in range(self.width)] for _ in range(self.height)]
        self.owners = [[None for _ in range(self.width)] for _ in range(self.height)]
        self.score = 0
        self.lines_cleared = 0
        self.level_lines_cleared = 0
        self.level = 1
        self.combo = 0
        self.tetrises = 0
        self.last_cleared_lines = []
        self.last_cleared_colors = {}
        self.flexible_border_active = False
        self.back_to_back = False
        self.clear_lock_out()
