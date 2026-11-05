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
        self.hidden_rows = 2
        self.grid: List[List[Tuple[int, int, int]]] = [[BLACK for _ in range(self.width)] for _ in range(self.height)]
        self.texture_grid: List[List[object | None]] = [[None for _ in range(self.width)] for _ in range(self.height)]
        self.owners: List[List[str | None]] = [[None for _ in range(self.width)] for _ in range(self.height)]
        self.hidden_occupancy: List[List[bool]] = [[False for _ in range(self.width)] for _ in range(self.hidden_rows)]
        self.hidden_grid: List[List[Tuple[int, int, int]]] = [[BLACK for _ in range(self.width)] for _ in range(self.hidden_rows)]
        self.hidden_texture_grid: List[List[object | None]] = [[None for _ in range(self.width)] for _ in range(self.hidden_rows)]
        self.hidden_gold: List[List[bool]] = [[False for _ in range(self.width)] for _ in range(self.hidden_rows)]
        self.hidden_owners: List[List[str | None]] = [[None for _ in range(self.width)] for _ in range(self.hidden_rows)]
        self.occupancy: List[List[bool]] = [[False for _ in range(self.width)] for _ in range(self.height)]
        self.gold: List[List[bool]] = [[False for _ in range(self.width)] for _ in range(self.height)]
        self.score = 0
        self.lines_cleared = 0
        # Lines that contribute to level progression. Some card/ability effects may
        # intentionally increment `lines_cleared` for stats/achievements without
        # allowing farming level-ups.
        self.level_lines_cleared = 0
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
        return self._is_valid_cells(piece.get_cells(), dx, dy, piece)

    def _is_valid_cells(self, cells, dx: int = 0, dy: int = 0, piece=None) -> bool:
        """is_valid_position'ın hücre-listesi kardeşi.

        Sınır/occupancy/perk semantiğinin TEK kaynağı burasıdır;
        `is_valid_position` bu metodu parça hücreleriyle çağırır.
        `get_ghost_y` drop simülasyonu (game.py, OP-018/D10) hücre
        listesini bir kez hesaplayıp dy adımlarını buraya sorar —
        get_cells her iterasyonda yeniden üretilmez.
        """
        # Esnek sınır: Board'daki flag VEYA parçadaki flag aktifse genişletilmiş sınır
        # SADECE sol ve sağ kenarlar için geçerli, alt/üst normal
        flexible_border = self.flexible_border_active or getattr(piece, 'flexible_border', False)
        border_extend = 1 if flexible_border else 0

        for px, py in cells:
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
                hidden_index = py + self.hidden_rows
                if hidden_index < 0:
                    return False
                if 0 <= px < self.width and self.hidden_occupancy[hidden_index][px]:
                    return False
                continue
            # Eğer hücre tahta dışındaysa (esnek sınır sayesinde) occupancy kontrolü yapma
            if px < 0 or px >= self.width:
                continue
            # If piece has tunneling/drilling active, ignore occupancy checks so it can pass through blocks
            if self._cell_filled(px, py) and not (getattr(piece, 'tunnel', False) or getattr(piece, 'drill', False)):
                return False
        return True

    def lock_piece(self, piece, *, track_game_over: bool = True, t_spin: str | None = None) -> int:
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
        # Gizli tamponda kalan hücreleri fiziksel olarak koru. Kısmi gizli kilit
        # tek başına lock-out değildir; yalnız parça tamamen görünmez alanda
        # kilitlenirse Guideline lock-out uygulanır.
        _overflow_top = False
        visible_cells = 0
        hidden_cells = 0
        total_cells = sum(1 for row in piece.shape for cell in row if cell)
        for ly, row in enumerate(piece.shape):
            for lx, c in enumerate(row):
                if not c:
                    continue
                x = piece.x + lx + lock_dx
                y = piece.y + ly
                if y < 0:
                    hidden_index = y + self.hidden_rows
                    if 0 <= x < self.width and 0 <= hidden_index < self.hidden_rows:
                        cell_color = piece.color
                        if color_matrix is not None:
                            try:
                                cm_val = color_matrix[ly][lx]
                                if cm_val is not None:
                                    cell_color = cm_val
                            except Exception:
                                pass
                        self.hidden_occupancy[hidden_index][x] = True
                        self.hidden_grid[hidden_index][x] = cell_color
                        self.hidden_gold[hidden_index][x] = getattr(piece, 'is_gold', False)
                        self.hidden_owners[hidden_index][x] = getattr(piece, 'name', None)
                        if style_name and callable(TextureSlice):
                            self.hidden_texture_grid[hidden_index][x] = TextureSlice(
                                str(style_name), rel_x=lx, rel_y=ly,
                                width=piece_w or 1, height=piece_h or 1,
                                rotation=getattr(piece, 'rotation_state', 0),
                            )
                        hidden_cells += 1
                    else:
                        _overflow_top = True
                    continue
                if 0 <= x < self.width and y < self.height:
                    visible_cells += 1
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

        cleared = self.clear_lines(t_spin=t_spin)

        # Guideline lock-out: row 0'da kısmi doluluk ölüm değildir. Yalnızca
        # parçanın tüm hücreleri görünür alanın üstünde kilitlenirse veya iki
        # gizli satırlık fiziksel tamponun dışına taşarsa lock-out oluşur.
        full_hidden_lock = total_cells > 0 and visible_cells == 0 and (hidden_cells > 0 or _overflow_top)
        if full_hidden_lock:
            self._last_lock_out = True
            if track_game_over:
                self._locked_out = True

        return cleared

    def clear_lines(self, source: str = "player", t_spin: str | None = None) -> int:
        """Clear full rows, resolving every cascade wave as one scoring event."""
        total_lines = 0
        all_cleared_rows: List[int] = []
        cascade_colors: dict[int, List[Tuple[int, int, int]]] = {}
        waves: list[tuple[int, int, int, str | None]] = []
        while True:
            lines_to_clear = [y for y in range(self.height) if all(self._cell_filled(x, y) for x in range(self.width))]
            if not lines_to_clear:
                break
            wave_lines = len(lines_to_clear)
            wave_gold = 0
            wave_units = 0
            for y in lines_to_clear:
                if any(self.gold[y][x] for x in range(self.width)):
                    wave_gold += 1
                for x in range(self.width):
                    if self.occupancy[y][x]:
                        owner = self.owners[y][x]
                        if owner:
                            wave_units += BLOCK_UNIT_POINTS.get(owner, 1)
                cascade_colors.setdefault(y, [self.grid[y][x] for x in range(self.width)])
            all_cleared_rows.extend(lines_to_clear)
            total_lines += wave_lines
            waves.append((wave_lines, wave_gold, wave_units, t_spin if not waves else None))
            combined = [
                self.hidden_grid + self.grid,
                self.hidden_texture_grid + self.texture_grid,
                self.hidden_occupancy + self.occupancy,
                self.hidden_gold + self.gold,
                self.hidden_owners + self.owners,
            ]
            for y in sorted(lines_to_clear, reverse=True):
                combined_index = self.hidden_rows + y
                for grid in combined:
                    del grid[combined_index]
            empty_rows = [
                [BLACK for _ in range(self.width)], [None for _ in range(self.width)],
                [False for _ in range(self.width)], [False for _ in range(self.width)],
                [None for _ in range(self.width)],
            ]
            for _ in range(wave_lines):
                for grid, empty in zip(combined, empty_rows):
                    grid.insert(0, empty[:])
            self.hidden_grid, self.grid = combined[0][:self.hidden_rows], combined[0][self.hidden_rows:]
            self.hidden_texture_grid, self.texture_grid = combined[1][:self.hidden_rows], combined[1][self.hidden_rows:]
            self.hidden_occupancy, self.occupancy = combined[2][:self.hidden_rows], combined[2][self.hidden_rows:]
            self.hidden_gold, self.gold = combined[3][:self.hidden_rows], combined[3][self.hidden_rows:]
            self.hidden_owners, self.owners = combined[4][:self.hidden_rows], combined[4][self.hidden_rows:]
        self.last_cleared_lines = all_cleared_rows
        if total_lines:
            self.last_cleared_colors = cascade_colors
        player_source = str(source).lower() in {"player", "normal"}
        for wave_lines, wave_gold, wave_units, wave_t_spin in waves:
            level = int(getattr(self, 'level', 1) or 1)
            if wave_t_spin == 'mini':
                base_score = [100, 200, 400][min(wave_lines, 2)] * level
            elif wave_t_spin == 'full':
                base_score = [400, 800, 1200, 1600][min(wave_lines, 3)] * level
            else:
                base_score = [0, 100, 300, 500, 800][min(wave_lines, 4)] * level
            combo_bonus = self.combo * 50 * level if self.combo > 0 else 0
            self.combo += 1
            b2b_action = (wave_t_spin is not None and wave_lines > 0) or wave_lines >= 4
            if b2b_action:
                if self.back_to_back:
                    base_score = int(base_score * 1.5)
                self.back_to_back = True
            else:
                self.back_to_back = False
            if all(not any(row) for row in self.occupancy):
                base_score += 3000 * level
            self.tetrises += 1 if wave_lines >= 4 else 0
            per_line = base_score / wave_lines
            extra = int(per_line * 4 * wave_gold) if wave_gold else 0
            self.score += base_score + combo_bonus + extra + int(wave_units * level)
            self.lines_cleared += wave_lines
            if player_source:
                self.level_lines_cleared += wave_lines
                self.level = (int(self.level_lines_cleared) // max(1, int(getattr(self, 'level_lines_per_level', 5) or 5))) + 1
        if not waves and t_spin is not None and player_source:
            level = int(getattr(self, 'level', 1) or 1)
            self.score += (100 if t_spin == 'mini' else 400) * level
            self.combo = 0
        elif not waves and player_source:
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
        self.hidden_occupancy = [[False for _ in range(self.width)] for _ in range(self.hidden_rows)]
        self.hidden_grid = [[BLACK for _ in range(self.width)] for _ in range(self.hidden_rows)]
        self.hidden_texture_grid = [[None for _ in range(self.width)] for _ in range(self.hidden_rows)]
        self.hidden_gold = [[False for _ in range(self.width)] for _ in range(self.hidden_rows)]
        self.hidden_owners = [[None for _ in range(self.width)] for _ in range(self.hidden_rows)]
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
