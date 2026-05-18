"""
Parça Atölyesi (Piece Workshop) - Özel Quadrix Parçaları Oluşturma

Yeni mantık:
- En fazla 7 blok yerleştirilebilir
- Bir seferde sadece tek parça oluşturulur
- Her parça ayrı kaydedilir
- Bloklar birbirine bağlı olmalı (flood-fill kontrolü)
"""

import pygame
import sys
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Any
from retro_style import retro_style
from block_styles import ALL_PIECE_NAMES
from platform_utils import is_fullscreen_toggle, is_primary_modifier, get_modifier_key_name, normalize_mouse_pos, get_mouse_pos
from workshop_blocks import WORKSHOP_MODES, WORKSHOP_MODE_KEYS
from renderers.jelly_renderer import draw_jelly_block
from background_effects import get_shared_falling_blocks_layer
from localization import t
from ui_scaling import get_projected_effective_scale


def _resolve_root_dir() -> Path:
    meipass = getattr(sys, '_MEIPASS', None)
    if isinstance(meipass, str) and meipass:
        return Path(meipass)
    return Path(__file__).resolve().parent.parent


ROOT_DIR = _resolve_root_dir()


class PieceWorkshopScreen:
    """Özel Quadrix parçaları oluşturma ekranı - Modern tasarım"""
    
    # Maksimum blok sayısı ve grid boyutu
    MAX_BLOCKS = 7
    GRID_SIZE = 7  # 7x7 grid
    
    def __init__(self, screen, settings_manager, theme_manager):
        self.screen = screen
        self.settings_manager = settings_manager
        self.theme_manager = theme_manager

        # Arka plan efektleri (ayarlar ekranı ile tutarlı düşen bloklar)
        self.background_fx = get_shared_falling_blocks_layer('default')
        
        # Grid (7x7)
        self.grid = self._empty_grid()
        
        # Cursor
        self.cursor_x = self.GRID_SIZE // 2
        self.cursor_y = self.GRID_SIZE // 2
        
        # Seçili renk
        self.current_color = (0, 255, 255)  # Cyan default
        self.color_palette = [
            (0, 255, 255),    # Cyan
            (255, 165, 0),    # Orange
            (255, 0, 255),    # Magenta
            (0, 255, 0),      # Green
            (255, 255, 0),    # Yellow
            (138, 43, 226),   # Purple
            (255, 80, 80),    # Red
            (100, 200, 255),  # Light Blue
            (50, 50, 255),    # Blue
            (255, 255, 255),  # White
            (128, 128, 128),  # Gray
            (50, 205, 50),    # Lime
        ]
        self.selected_color_idx = 0
        self.custom_color = None
        self.palette_swatch_rects: List[tuple[pygame.Rect, int]] = []
        self.custom_color_button_rect = pygame.Rect(0, 0, 0, 0)
        self.save_button_rect = pygame.Rect(0, 0, 0, 0)
        self.delete_button_rect = pygame.Rect(0, 0, 0, 0)
        self.block_styles_card_rect = pygame.Rect(0, 0, 0, 0)
        self.palette_rect = pygame.Rect(0, 0, 0, 0)
        self._last_custom_click_ms: int = 0
        
        # Kayıtlı parçalar
        self.custom_pieces: List[Dict[str, Any]] = []
        self._load_pieces_from_settings()

        # Load last used custom color
        saved_color = self.settings_manager.get('workshop_last_custom_color')
        if saved_color and isinstance(saved_color, (list, tuple)) and len(saved_color) >= 3:
            self.custom_color = tuple(int(v) for v in saved_color[:3])
            # If loaded, make it active immediately? Maybe not, start with palette default or let user pick.
            # But user requested "en son seçilen özel rengin kaydını tutup en son ne seçildiyse o kalmaya devam etsin"
            # So if we have a custom color, we might want to start with it?
            # Let's just restore the value. Selection logic remains.
        
        # UI state
        self.message = ''
        self.message_timer = 0
        self.last_grid_rect = pygame.Rect(0, 0, 0, 0)
        self.last_cell_size = 40
        
        # Pieces list UI
        self.pieces_scroll = 0
        self.selected_piece_idx = -1
        self.editing_piece_id = None
        self.piece_item_rects = []
        self.mode_tag_rects = []
        self.mode_focus = 0
        self.last_pieces_panel_rect = pygame.Rect(0, 0, 0, 0)
        self.last_piece_list_y = 0
        self.last_piece_item_height = 50
        self.last_piece_item_gap = 6
        self.last_piece_item_cols = 1

    # ── Responsive ölçek ──

    def _ui_scale(self) -> float:
        try:
            return get_projected_effective_scale(
                self.screen,
                min_scale=0.68,
                max_scale=1.24,
                reference_size=(1366.0, 768.0),
            )
        except Exception:
            return 1.0

    def _s(self, value: int | float, minimum: int = 1) -> int:
        return max(minimum, int(round(float(value) * self._ui_scale())))

    def _default_modes(self) -> List[str]:
        # Yeni parça kaydında başlangıçta hiçbir mod seçili olmasın.
        return []

    def _normalize_modes(self, modes: Any) -> List[str]:
        # Not: boş liste geçerlidir (hiçbir mod seçili değil).
        if isinstance(modes, list):
            return [m for m in WORKSHOP_MODE_KEYS if m in modes]
        # Geriye dönük uyumluluk: modes yoksa/bozuksa eskisi gibi tüm modlar.
        return WORKSHOP_MODE_KEYS[:]

    def _get_piece_by_id(self, piece_id: str) -> Optional[Dict[str, Any]]:
        if not piece_id:
            return None
        for piece in self.custom_pieces:
            if piece.get('id') == piece_id:
                return piece
        return None

    def _set_selected_piece_index(self, index: int) -> None:
        if not self.custom_pieces:
            self.selected_piece_idx = -1
            return
        self.selected_piece_idx = max(0, min(index, len(self.custom_pieces) - 1))
        self._ensure_selected_piece_visible()

    def _ensure_selected_piece_visible(self) -> None:
        if not self.custom_pieces or self.selected_piece_idx < 0:
            return
        panel = self.last_pieces_panel_rect
        if not panel or panel.width <= 0:
            return
        list_y = self.last_piece_list_y
        item_h = self.last_piece_item_height
        gap = self.last_piece_item_gap
        cols = max(1, getattr(self, 'last_piece_item_cols', 1))
        if item_h <= 0:
            return

        # Visible bounds inside the panel
        top = list_y
        bottom = panel.bottom - 10
        idx = self.selected_piece_idx
        row = idx // cols
        item_top = top + row * (item_h + gap) - self.pieces_scroll
        item_bottom = item_top + item_h
        if item_top < top:
            self.pieces_scroll = row * (item_h + gap)
        elif item_bottom > bottom:
            self.pieces_scroll = row * (item_h + gap) - max(0, (bottom - top) - item_h)
        self.pieces_scroll = max(0, self.pieces_scroll)

    def _toggle_piece_mode(self, piece_id: str, mode_index: int) -> None:
        piece = self._get_piece_by_id(piece_id)
        if not piece or mode_index < 0 or mode_index >= len(WORKSHOP_MODES):
            return
        mode_key = WORKSHOP_MODES[mode_index][0]
        modes = self._normalize_modes(piece.get('modes'))
        if mode_key in modes:
            # Toggle: seçili modu kaldır (tümü kaldırılabilir)
            modes = [m for m in modes if m != mode_key]
        else:
            modes.append(mode_key)
        piece['modes'] = self._normalize_modes(modes)
        self._persist_pieces()
        self._set_message(t('piece_workshop_modes_updated'))

    def _active_mode_piece_id(self) -> Optional[str]:
        if self.editing_piece_id:
            return self.editing_piece_id
        if 0 <= self.selected_piece_idx < len(self.custom_pieces):
            pid = self.custom_pieces[self.selected_piece_idx].get('id')
            return pid if isinstance(pid, str) and pid else None
        return None

    def _toggle_focused_mode(self) -> None:
        piece_id = self._active_mode_piece_id()
        if not piece_id:
            return
        self._toggle_piece_mode(piece_id, self.mode_focus)
    
    def _empty_grid(self) -> List[List[Optional[Dict]]]:
        """Boş grid oluştur"""
        return [[None for _ in range(self.GRID_SIZE)] for _ in range(self.GRID_SIZE)]
    
    def _count_blocks(self) -> int:
        """Grid'deki blok sayısını say"""
        count = 0
        for row in self.grid:
            for cell in row:
                if cell is not None:
                    count += 1
        return count
    
    def _get_block_positions(self) -> List[tuple]:
        """Tüm blok pozisyonlarını al"""
        positions = []
        for y in range(self.GRID_SIZE):
            for x in range(self.GRID_SIZE):
                if self.grid[y][x] is not None:
                    positions.append((x, y))
        return positions
    
    def _is_connected(self) -> bool:
        """Tüm blokların birbirine bağlı olup olmadığını kontrol et (flood-fill)"""
        positions = self._get_block_positions()
        if len(positions) <= 1:
            return True
        
        visited = set()
        to_visit = [positions[0]]
        
        while to_visit:
            x, y = to_visit.pop()
            if (x, y) in visited:
                continue
            visited.add((x, y))
            
            # Komşuları kontrol et
            for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nx, ny = x + dx, y + dy
                if (nx, ny) in positions and (nx, ny) not in visited:
                    to_visit.append((nx, ny))
        
        return len(visited) == len(positions)
    
    def _normalize_shape(self, positions: List[tuple]) -> List[tuple]:
        """Şekli (0,0)'dan başlayacak şekilde normalize et"""
        if not positions:
            return []
        min_x = min(x for x, y in positions)
        min_y = min(y for x, y in positions)
        return sorted([(x - min_x, y - min_y) for x, y in positions])
    
    def _generate_piece_id(self) -> str:
        """Benzersiz parça ID'si oluştur"""
        return f"custom_{uuid.uuid4().hex[:8]}"
    
    def _set_message(self, msg: str, duration: int = 120, *, is_error: bool = False):
        """Durum mesajı göster"""
        self.message = msg
        self.message_timer = duration
        self.message_is_error = bool(is_error)
    
    def _paint_cell(self, x: int, y: int):
        """Hücreyi boya"""
        if self.grid[y][x] is not None:
            # Zaten dolu, renk değiştir
            self.grid[y][x]['color'] = self.current_color
            self._set_message(t('piece_workshop_color_changed'))
            return
        
        # Yeni blok ekle
        current_count = self._count_blocks()
        if current_count >= self.MAX_BLOCKS:
            self._set_message(t('piece_workshop_max_blocks', max_blocks=self.MAX_BLOCKS), is_error=True)
            return
        
        # Blok ekle
        self.grid[y][x] = {'color': self.current_color}
        
        # Bağlantı kontrolü (ilk blok hariç)
        if current_count > 0 and not self._is_connected():
            # Bağlı değil, geri al
            self.grid[y][x] = None
            self._set_message(t('piece_workshop_blocks_connected_required'), is_error=True)
            return
        
        remaining = self.MAX_BLOCKS - current_count - 1
        self._set_message(t('piece_workshop_block_added', remaining=remaining))
    
    def _erase_cell(self, x: int, y: int):
        """Hücreyi sil"""
        if self.grid[y][x] is None:
            return
        
        # Silme sonrası bağlantı kontrolü
        temp = self.grid[y][x]
        self.grid[y][x] = None
        
        if self._count_blocks() > 0 and not self._is_connected():
            # Silme yapılamaz, bağlantı kopuyor
            self.grid[y][x] = temp
            self._set_message(t('piece_workshop_cannot_delete_breaks'), is_error=True)
            return
        
        self._set_message(t('piece_workshop_block_deleted'))
    
    def _clear_grid(self, *, silent: bool = False):
        """Grid'i temizle"""
        self.grid = self._empty_grid()
        self.editing_piece_id = None
        if not silent:
            self._set_message(t('piece_workshop_grid_cleared'))
    
    def _save_current_piece(self):
        """Mevcut parçayı kaydet"""
        positions = self._get_block_positions()
        if len(positions) < 2:
            self._set_message(t('piece_workshop_min_blocks'), is_error=True)
            return
        
        if not self._is_connected():
            self._set_message(t('piece_workshop_blocks_not_connected'), is_error=True)
            return
        
        # Renkleri topla
        colors = {}
        for x, y in positions:
            colors[(x, y)] = self.grid[y][x]['color']
        
        # Normalize et
        shape = self._normalize_shape(positions)
        normalized_colors = []
        min_x = min(x for x, y in positions)
        min_y = min(y for x, y in positions)
        for x, y in positions:
            normalized_colors.append({
                'pos': (x - min_x, y - min_y),
                'color': colors[(x, y)]
            })
        
        # Yeni veya güncelleme
        if self.editing_piece_id:
            # Mevcut parçayı güncelle (edit modunda kal; grid'i temizleme)
            for piece in self.custom_pieces:
                if piece['id'] == self.editing_piece_id:
                    piece['shape'] = shape
                    piece['cells'] = normalized_colors
                    # Preserve modes selection if present
                    piece['modes'] = self._normalize_modes(piece.get('modes'))
                    break
            self._persist_pieces()
            self._set_message(t('piece_workshop_piece_updated'))
            return
        else:
            # Yeni parça oluştur
            piece_id = self._generate_piece_id()
            new_piece = {
                'id': piece_id,
                'name': t('piece_workshop_custom_name', index=len(self.custom_pieces) + 1),
                'shape': shape,
                'cells': normalized_colors,
                'modes': self._default_modes(),
            }
            self.custom_pieces.append(new_piece)
            self.selected_piece_idx = len(self.custom_pieces) - 1
            self._set_message(t('piece_workshop_piece_saved'))

        self._persist_pieces()
        # New piece saved: reset to make it easy to create another one.
        # Keep the save message visible; don't overwrite it with "Grid temizlendi".
        self._clear_grid(silent=True)
    
    def _load_piece_to_grid(self, piece: Dict):
        """Parçayı grid'e yükle (düzenleme için)"""
        self._clear_grid()
        self.editing_piece_id = piece['id']
        
        # Parçayı ortala
        cells = piece.get('cells', [])
        if not cells:
            return
        
        # Merkeze yerleştir
        offset_x = (self.GRID_SIZE - max(c['pos'][0] for c in cells) - 1) // 2
        offset_y = (self.GRID_SIZE - max(c['pos'][1] for c in cells) - 1) // 2
        
        for cell in cells:
            px, py = cell['pos']
            gx, gy = px + offset_x, py + offset_y
            if 0 <= gx < self.GRID_SIZE and 0 <= gy < self.GRID_SIZE:
                self.grid[gy][gx] = {'color': tuple(cell['color'])}
        
        self._set_message(t('piece_workshop_editing', name=piece['name']))
        # Keep selection in sync for keyboard navigation
        try:
            for idx, entry in enumerate(self.custom_pieces):
                if entry.get('id') == piece.get('id'):
                    self._set_selected_piece_index(idx)
                    break
        except Exception:
            pass
    
    def _delete_piece(self, piece_id: str):
        """Parçayı sil"""
        if not piece_id:
            return

        # Keep current selection position when possible
        prev_selected_id = None
        if 0 <= self.selected_piece_idx < len(self.custom_pieces):
            prev_selected_id = self.custom_pieces[self.selected_piece_idx].get('id')

        self.custom_pieces = [p for p in self.custom_pieces if p.get('id') != piece_id]
        self._persist_pieces()
        if self.editing_piece_id == piece_id:
            self._clear_grid(silent=True)
            self.editing_piece_id = None

        # Recompute selection index
        if not self.custom_pieces:
            self.selected_piece_idx = -1
        else:
            # Prefer staying on the next item; if deleted item was selected, keep same index.
            if prev_selected_id and prev_selected_id != piece_id:
                for idx, p in enumerate(self.custom_pieces):
                    if p.get('id') == prev_selected_id:
                        self.selected_piece_idx = idx
                        break
                else:
                    self.selected_piece_idx = min(self.selected_piece_idx, len(self.custom_pieces) - 1)
            else:
                self.selected_piece_idx = min(self.selected_piece_idx, len(self.custom_pieces) - 1)

        # Clamp scroll so list doesn't jump to empty space
        self.pieces_scroll = max(0, self.pieces_scroll)
        self._set_message(t('piece_workshop_piece_deleted'))

    def _max_pieces_scroll(self) -> int:
        panel = self.last_pieces_panel_rect
        if not panel or panel.width <= 0:
            return 0
        list_y = self.last_piece_list_y
        item_h = self.last_piece_item_height
        gap = self.last_piece_item_gap
        cols = max(1, getattr(self, 'last_piece_item_cols', 1))
        if item_h <= 0:
            return 0
        visible_h = max(0, (panel.bottom - 10) - list_y)
        rows = (len(self.custom_pieces) + cols - 1) // cols
        total_h = rows * (item_h + gap)
        return max(0, total_h - max(visible_h, 0))

    def _clamp_pieces_scroll(self) -> None:
        self.pieces_scroll = max(0, min(self.pieces_scroll, self._max_pieces_scroll()))
    
    def _persist_pieces(self):
        """Parçaları ayarlara kaydet"""
        if not self.settings_manager:
            return
        
        payload = []
        for piece in self.custom_pieces:
            payload.append({
                'id': piece['id'],
                'name': piece['name'],
                'shape': piece['shape'],
                'cells': piece['cells'],
                'modes': self._normalize_modes(piece.get('modes')),
            })
        self.settings_manager.set('custom_workshop_pieces', payload)
    
    def _load_pieces_from_settings(self):
        """Parçaları ayarlardan yükle"""
        if not self.settings_manager:
            return
        
        raw = self.settings_manager.get('custom_workshop_pieces', [])
        if not isinstance(raw, list):
            return
        
        self.custom_pieces = []
        for entry in raw:
            if isinstance(entry, dict) and 'id' in entry and 'shape' in entry:
                entry['modes'] = self._normalize_modes(entry.get('modes'))
                self.custom_pieces.append(entry)
    
    def handle_input(self, event) -> Optional[str]:
        """Input işle"""
        if event.type == pygame.KEYDOWN:
            mods = getattr(event, 'mod', pygame.key.get_mods())
            
            if event.key == pygame.K_ESCAPE:
                return 'back'
            elif is_fullscreen_toggle(event.key, getattr(event, 'mod', 0)):
                return 'toggle_fullscreen'

            # Accessibility: keyboard control for saved pieces + modes (Ctrl/Cmd combos)
            if is_primary_modifier(mods):
                # Delete active/selected saved piece
                if event.key in (pygame.K_DELETE, pygame.K_BACKSPACE, pygame.K_d):
                    pid = self._active_mode_piece_id()
                    if pid:
                        self._delete_piece(pid)
                        self._clamp_pieces_scroll()
                    return None
                if event.key == pygame.K_UP:
                    if self.custom_pieces:
                        next_idx = (self.selected_piece_idx if self.selected_piece_idx >= 0 else 0) - 1
                        self._set_selected_piece_index(next_idx)
                    return None
                if event.key == pygame.K_DOWN:
                    if self.custom_pieces:
                        next_idx = (self.selected_piece_idx if self.selected_piece_idx >= 0 else -1) + 1
                        self._set_selected_piece_index(next_idx)
                    return None
                if event.key == pygame.K_RETURN:
                    if self.custom_pieces:
                        idx = self.selected_piece_idx if self.selected_piece_idx >= 0 else 0
                        idx = max(0, min(idx, len(self.custom_pieces) - 1))
                        self._load_piece_to_grid(self.custom_pieces[idx])
                    return None
                if self._active_mode_piece_id():
                    if event.key == pygame.K_LEFT:
                        self.mode_focus = max(0, self.mode_focus - 1)
                        return None
                    if event.key == pygame.K_RIGHT:
                        self.mode_focus = min(len(WORKSHOP_MODES) - 1, self.mode_focus + 1)
                        return None
                    if event.key == pygame.K_SPACE:
                        self._toggle_focused_mode()
                        return None
                    if pygame.K_1 <= event.key <= pygame.K_9:
                        idx = event.key - pygame.K_1
                        if idx < len(WORKSHOP_MODES):
                            self.mode_focus = idx
                            self._toggle_focused_mode()
                        return None
                    if event.key == pygame.K_0:
                        idx = 9
                        if idx < len(WORKSHOP_MODES):
                            self.mode_focus = idx
                            self._toggle_focused_mode()
                        return None

            # Kaydet (Ctrl/Cmd+S) must be checked BEFORE movement, because 'S' is also "down".
            if event.key == pygame.K_s and is_primary_modifier(mods):
                self._save_current_piece()
                return None
            
            # Cursor hareketi
            if event.key in (pygame.K_LEFT, pygame.K_a):
                self.cursor_x = max(0, self.cursor_x - 1)
            elif event.key in (pygame.K_RIGHT, pygame.K_d):
                self.cursor_x = min(self.GRID_SIZE - 1, self.cursor_x + 1)
            elif event.key in (pygame.K_UP, pygame.K_w):
                self.cursor_y = max(0, self.cursor_y - 1)
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                # Ctrl/Cmd+S is handled above; plain S moves down.
                self.cursor_y = min(self.GRID_SIZE - 1, self.cursor_y + 1)
            
            # Boya/Sil
            elif event.key in (pygame.K_SPACE, pygame.K_RETURN):
                self._paint_cell(self.cursor_x, self.cursor_y)
            elif event.key in (pygame.K_BACKSPACE, pygame.K_x):
                # Backspace veya X (gamepad editor_secondary) → seçili hücreyi sil
                self._erase_cell(self.cursor_x, self.cursor_y)
            elif event.key in (pygame.K_DELETE, pygame.K_c):
                self._clear_grid()
            
            # Renk değiştir
            # TAB ile renk değiştirme kaldırıldı (mouse ile seçim).
            
            # Gamepad-friendly aksiyonlar (Ctrl gerektirmeyen yollar):
            # LB (bracket left) → saved pieces listesinde yukarı
            # RB (bracket right) → saved pieces listesinde aşağı
            # Bunlar aynı zamanda tab_prev/tab_next olarak da çalışır;
            # piece workshop'ta tab yok, bu yüzden güvenle kullanılabilir.
            elif event.key == pygame.K_LEFTBRACKET:
                # Saved pieces listesinde yukarı (veya save current piece)
                if self.custom_pieces:
                    next_idx = (self.selected_piece_idx if self.selected_piece_idx >= 0 else 0) - 1
                    self._set_selected_piece_index(next_idx)
                else:
                    self._save_current_piece()
            elif event.key == pygame.K_RIGHTBRACKET:
                # Saved pieces listesinde aşağı (veya save current piece)
                if self.custom_pieces:
                    next_idx = (self.selected_piece_idx if self.selected_piece_idx >= 0 else -1) + 1
                    self._set_selected_piece_index(next_idx)
                else:
                    self._save_current_piece()
            

        
        elif event.type == pygame.MOUSEBUTTONDOWN:
            pos = normalize_mouse_pos(getattr(event, 'pos', None)) or event.pos
            if event.button == 1:
                # Grid altındaki Kaydet butonu
                if self.save_button_rect and self.save_button_rect.collidepoint(pos):
                    self._save_current_piece()
                    return None

                # Grid altındaki Sil butonu (parça seçiliyken aktif)
                if self.delete_button_rect and self.delete_button_rect.collidepoint(pos):
                    pid = self._active_mode_piece_id()
                    if pid:
                        self._delete_piece(pid)
                        self._clamp_pieces_scroll()
                    return None

                if self.block_styles_card_rect and self.block_styles_card_rect.collidepoint(pos):
                    return 'block_styles'

                # Palette interactions (color selection)
                if self._handle_palette_click(pos):
                    return None
            cell = self._pos_to_cell(pos)
            if cell:
                self.cursor_x, self.cursor_y = cell
                if event.button == 1:
                    self._paint_cell(*cell)
                elif event.button == 3:
                    self._erase_cell(*cell)
            elif event.button in (1, 3):
                # Clicks on the saved pieces panel (select/edit + mode toggles)
                if event.button == 1 and self._handle_pieces_panel_click(pos):
                    return None
                # Right click on a saved piece deletes it
                if event.button == 3:
                    for idx, (rect, piece_id) in enumerate(self.piece_item_rects):
                        if rect.collidepoint(pos):
                            self._set_selected_piece_index(idx)
                            self._delete_piece(piece_id)
                            self._clamp_pieces_scroll()
                            return None
                    return None
                # Click on empty space exits edit mode and clears the grid
                if event.button == 1 and self._handle_empty_space_click(pos):
                    return None

        elif event.type == pygame.MOUSEWHEEL:
            # Scroll saved pieces list when the mouse is over that panel
            mx, my = get_mouse_pos()
            if self.last_pieces_panel_rect and self.last_pieces_panel_rect.collidepoint((mx, my)):
                step = (self.last_piece_item_height + self.last_piece_item_gap)
                self.pieces_scroll = max(0, self.pieces_scroll - int(event.y) * step)
                self._clamp_pieces_scroll()
                return None
        
        elif event.type == pygame.MOUSEMOTION:
            pos = normalize_mouse_pos(getattr(event, 'pos', None)) or event.pos
            if event.buttons[0] or event.buttons[2]:
                cell = self._pos_to_cell(pos)
                if cell:
                    self.cursor_x, self.cursor_y = cell
                    if event.buttons[0]:
                        self._paint_cell(*cell)
                    elif event.buttons[2]:
                        self._erase_cell(*cell)
        
        return None

    def _handle_palette_click(self, pos: tuple[int, int]) -> bool:
        if not self.palette_rect or self.palette_rect.width <= 0:
            return False
        if not self.palette_rect or self.palette_rect.width <= 0:
            return False
            
        # Check swatch clicks
        for rect, idx in self.palette_swatch_rects:
            if rect.collidepoint(pos):
                self.selected_color_idx = idx
                self.current_color = self.color_palette[idx]
                self._set_message(t('piece_workshop_color_selected'))
                return True

        if self.custom_color_button_rect and self.custom_color_button_rect.collidepoint(pos):
            now_ms = 0
            try:
                now_ms = int(pygame.time.get_ticks())
            except Exception:
                now_ms = 0

            is_double = (now_ms - int(getattr(self, '_last_custom_click_ms', 0) or 0)) <= 350
            self._last_custom_click_ms = now_ms

            # Tek tık: özel rengi aktif et (blok koymada kullan)
            if self.custom_color is None:
                # İlk kez özel renge geçiliyorsa mevcut rengi seed et
                self.custom_color = tuple(int(v) for v in self.current_color[:3])
            self.current_color = self.custom_color
            self.selected_color_idx = -1

            # Çift tık: özel rengi değiştir (renk seçici)
            if is_double:
                chosen = self._prompt_color_choice(self.custom_color or self.current_color)
                if chosen:
                    self.custom_color = chosen
                    self.current_color = chosen
                    self.selected_color_idx = -1
                    self._set_message(t('piece_workshop_custom_color_changed'))
                else:
                    self._set_message(t('piece_workshop_custom_color_cancelled'))
            else:
                self._set_message(t('piece_workshop_custom_color_active'))
            
            # Persist custom color choice
            if self.custom_color:
                self.settings_manager.set('workshop_last_custom_color', self.custom_color)
            return True
        return False

    def _prompt_color_choice(self, fallback_color, piece_name="") -> Optional[tuple[int, int, int]]:
        from color_picker import pygame_color_picker
        initial = tuple(int(v) for v in fallback_color[:3])
        chosen = pygame_color_picker(self.screen, initial_color=initial, piece_name=piece_name)
        return chosen

    def _handle_pieces_panel_click(self, pos: tuple) -> bool:
        if not self.last_pieces_panel_rect or self.last_pieces_panel_rect.width <= 0:
            return False
        if not self.last_pieces_panel_rect.collidepoint(pos):
            return False

        # First: mode tags (when a piece is selected or editing)
        for idx, rect in enumerate(self.mode_tag_rects):
            if rect.collidepoint(pos) and self._active_mode_piece_id():
                self.mode_focus = idx
                self._toggle_focused_mode()
                return True

        # Then: piece list items (single click selects; double click edits)
        for idx, (rect, piece_id) in enumerate(self.piece_item_rects):
            if rect.collidepoint(pos):
                # Single click: open for editing
                self._set_selected_piece_index(idx)
                piece = self._get_piece_by_id(piece_id)
                if piece:
                    self._load_piece_to_grid(piece)
                return True
        return False

    def _handle_empty_space_click(self, pos: tuple) -> bool:
        """If editing, clicking on empty UI space exits edit mode and clears the grid."""
        if not self.editing_piece_id:
            return False

        # Don't cancel edit when interacting with the grid
        if self.last_grid_rect and self.last_grid_rect.collidepoint(pos):
            return False

        # Don't cancel edit when clicking inside the saved pieces panel
        # (items/modes are handled separately)
        if self.last_pieces_panel_rect and self.last_pieces_panel_rect.collidepoint(pos):
            # If it's inside the panel but not on an actionable rect, treat it as empty space.
            for rect, _ in self.piece_item_rects:
                if rect.collidepoint(pos):
                    return False
            for rect in self.mode_tag_rects:
                if rect.collidepoint(pos):
                    return False

        # Exit edit mode and clear
        self.editing_piece_id = None
        self.selected_piece_idx = -1
        self._clear_grid(silent=True)
        self._set_message(t('piece_workshop_edit_closed'))
        return True
    
    def _pos_to_cell(self, pos: tuple) -> Optional[tuple]:
        """Ekran pozisyonunu grid hücresine çevir"""
        if not self.last_grid_rect.collidepoint(pos):
            return None
        rel_x = (pos[0] - self.last_grid_rect.x) // self.last_cell_size
        rel_y = (pos[1] - self.last_grid_rect.y) // self.last_cell_size
        if 0 <= rel_x < self.GRID_SIZE and 0 <= rel_y < self.GRID_SIZE:
            return int(rel_x), int(rel_y)
        return None

    def _draw_rounded_panel(
        self,
        rect: pygame.Rect,
        fill_color: tuple,
        border_color: Optional[tuple] = None,
        border_width: int = 1,
        radius: Optional[int] = None,
        glow_color: Optional[tuple] = None,
        glow_alpha: int = 0,
        top_highlight_alpha: int = 0,
        inner_border_color: Optional[tuple] = None,
    ) -> None:
        """Yuvarlatılmış köşeli panel çiz."""
        if rect.width <= 0 or rect.height <= 0:
            return

        _s = self._s
        corner_radius = max(2, radius if radius is not None else _s(12))

        if glow_color is not None and glow_alpha > 0:
            glow_rect = rect.inflate(_s(6), _s(6))
            glow_surf = pygame.Surface(glow_rect.size, pygame.SRCALPHA)
            pygame.draw.rect(
                glow_surf,
                (*glow_color[:3], glow_alpha),
                glow_surf.get_rect(),
                border_radius=max(2, corner_radius + _s(2)),
            )
            self.screen.blit(glow_surf, glow_rect.topleft)

        panel_surf = pygame.Surface(rect.size, pygame.SRCALPHA)
        panel_bounds = panel_surf.get_rect()
        pygame.draw.rect(panel_surf, fill_color, panel_bounds, border_radius=corner_radius)

        if top_highlight_alpha > 0:
            highlight_rect = pygame.Rect(
                _s(2),
                _s(2),
                max(1, panel_bounds.width - _s(4)),
                max(2, min(panel_bounds.height // 2, _s(16))),
            )
            pygame.draw.rect(
                panel_surf,
                (255, 255, 255, top_highlight_alpha),
                highlight_rect,
                border_radius=max(2, corner_radius - _s(2)),
            )

        if inner_border_color is not None:
            inner_rect = panel_bounds.inflate(-_s(4), -_s(4))
            if inner_rect.width > 0 and inner_rect.height > 0:
                pygame.draw.rect(
                    panel_surf,
                    inner_border_color,
                    inner_rect,
                    1,
                    border_radius=max(2, corner_radius - _s(2)),
                )

        self.screen.blit(panel_surf, rect.topleft)

        if border_color is not None and border_width > 0:
            pygame.draw.rect(self.screen, border_color[:3], rect, border_width, border_radius=corner_radius)
    
    def draw(self):
        """Modern Parça Atölyesi UI çiz"""
        width, height = self.screen.get_size()
        _s = self._s
        retro_style.draw_background(self.screen)
        self.background_fx.update(self.screen)
        self.background_fx.draw(self.screen)
        
        # Başlık
        title_rect = retro_style.draw_title(self.screen, t('piece_workshop_title'), (width // 2, _s(55)), emoji='🧩')

        # Grid alanı
        grid_top = title_rect.bottom + _s(26)
        mirrored_grid_height_limit = (height - grid_top - _s(120)) // (self.GRID_SIZE * 2)
        cell_size = min(_s(45), mirrored_grid_height_limit, (width - _s(300)) // self.GRID_SIZE)
        cell_size = max(_s(30), cell_size)
        self.last_cell_size = cell_size
        
        grid_pixel_size = cell_size * self.GRID_SIZE
        grid_x = _s(60)
        grid_y = grid_top + _s(10)
        grid_rect = pygame.Rect(grid_x, grid_y, grid_pixel_size, grid_pixel_size)
        self.last_grid_rect = grid_rect
        
        # Grid container
        container_rect = grid_rect.inflate(_s(24), _s(24))
        retro_style.draw_glass_panel(self.screen, container_rect, alpha=160, border_color=(60, 90, 140))
        
        # Blok sayısı göstergesi
        block_count = self._count_blocks()
        counter_font = retro_style.get_font(_s(16), bold=True)
        counter_color = retro_style.primary if block_count < self.MAX_BLOCKS else (255, 100, 100)
        counter_text = t('piece_workshop_counter', count=block_count, max_blocks=self.MAX_BLOCKS)
        counter_surf = counter_font.render(counter_text, True, counter_color)
        self.screen.blit(counter_surf, (container_rect.x + _s(10), container_rect.y - _s(22)))
        
        # Grid çiz
        self._draw_grid(grid_rect, cell_size)
        self._draw_cursor(grid_rect, cell_size)

        # Grid altına butonlar
        btn_h = _s(42)
        btn_gap = _s(8)
        total_w = container_rect.width
        btn_y = container_rect.bottom + _s(10)
        
        # Parça seçili mi kontrol et (SİL butonu için)
        has_selected_piece = self._active_mode_piece_id() is not None
        
        # Butonlar her zaman yan yana - aynı genişlikte
        btn_w = (total_w - btn_gap) // 2
        self.save_button_rect = pygame.Rect(container_rect.x, btn_y, btn_w, btn_h)
        self.delete_button_rect = pygame.Rect(container_rect.x + btn_w + btn_gap, btn_y, btn_w, btn_h)
        
        # KAYDET butonu (yeşil)
        self._draw_action_button(
            self.save_button_rect,
            t('piece_workshop_save_button', modifier=get_modifier_key_name()),
            (55, 140, 90)  # Yeşil
        )
        
        # SİL butonu - parça seçiliyse kırmızı, değilse deaktif (gri)
        if has_selected_piece:
            self._draw_action_button(
                self.delete_button_rect,
                t('piece_workshop_delete_button', modifier=get_modifier_key_name()),
                (210, 80, 80)  # Kırmızı
            )
        else:
            # Deaktif SİL butonu (gri)
            self._draw_action_button(
                self.delete_button_rect,
                t('piece_workshop_delete_button', modifier=get_modifier_key_name()),
                (60, 65, 75)  # Gri (deaktif)
            )

        panel_start_x = grid_rect.right + _s(30)

        card_gap = _s(18)
        card_bottom_margin = _s(28)
        card_top_limit = self.save_button_rect.bottom + card_gap
        card_bottom_limit = height - card_bottom_margin
        desired_card_size = int(round(grid_pixel_size * 1.20))
        card_size = max(1, min(desired_card_size, panel_start_x - _s(18), card_bottom_limit - card_top_limit))
        card_x = int(round(container_rect.centerx - (card_size / 2)))
        card_x = max(_s(18), min(card_x, panel_start_x - card_size))
        card_y = card_top_limit + max(0, (card_bottom_limit - card_top_limit - card_size) // 2)
        self.block_styles_card_rect = pygame.Rect(card_x, card_y, card_size, card_size)
        self._draw_block_styles_card(self.block_styles_card_rect)


        
        # --- SAĞ PANEL (Palette + Custom Color + Pieces) ---
        
        panel_y = grid_y
        available_height = height - grid_y - _s(20)
        
        # 1. Renk Paleti (Sol kısım)
        # Önce çizim yaparak rect'i güncellememiz lazım, ama _draw_color_palette çizim yapıyor.
        # Bu yüzden burada koordinatı verip çizdireceğiz.
        
        self._draw_color_palette(panel_start_x, panel_y, available_height)
        
        # 2. Özel Renk Butonu (Paletin altına)
        # Palet rect güncellendi (`self.palette_rect`)
        if self.palette_rect.width > 0:
            custom_btn_y = self.palette_rect.bottom + _s(12)
            custom_btn_w = self.palette_rect.width
            custom_btn_h = _s(74)
            
            self.custom_color_button_rect = pygame.Rect(
                self.palette_rect.x, 
                custom_btn_y, 
                custom_btn_w, 
                custom_btn_h
            )
            self._draw_custom_color_button(self.custom_color_button_rect)
            
            # 3. Kayıtlı Parçalar Paneli (Sağ kısım - Sarı alan)
            # Palet ve butonun sağından başla
            pieces_x = self.palette_rect.right + _s(20)
            pieces_w = width - pieces_x - _s(30)
            
            if pieces_w > 120:
                self._draw_pieces_panel(pieces_x, panel_y, pieces_w, available_height)
        
        # Mesaj
        if self.message_timer > 0:
            msg_font = retro_style.get_font(_s(17), bold=True)
            msg_color = (255, 100, 100) if getattr(self, 'message_is_error', False) else retro_style.accent
            msg_surf = msg_font.render(self.message, True, msg_color)
            self.screen.blit(msg_surf, msg_surf.get_rect(center=(width // 2, height - _s(26))))
            self.message_timer -= 1
    
    def _draw_custom_color_button(self, rect: pygame.Rect):
        selected = (self.selected_color_idx < 0)
        
        fill_color = self.custom_color or self.current_color
        base = tuple(int(c) for c in fill_color[:3])
        
        # 1. Çerçeve (Konteyner)
        # Cam panel görünümü
        if selected:
             border_c = base
        else:
             border_c = (70, 90, 110)

        retro_style.draw_glass_panel(
            self.screen, 
            rect, 
            alpha=180 if selected else 140, 
            border_color=border_c
        )
        
        if selected:
            # Dışa ekstra glow - seçili renk ile (base + alpha)
            glow = rect.inflate(4, 4)
            # base rengine alpha ekle
            glow_color = (*base, 150)
            pygame.draw.rect(self.screen, glow_color, glow, 2, border_radius=14)

        # 2. Renk Butonu (Swatch) - Üstte ortalı
        _s = self._s
        swatch_size = _s(32)
        swatch_x = rect.centerx - swatch_size // 2
        swatch_y = rect.y + _s(8)
        swatch_rect = pygame.Rect(swatch_x, swatch_y, swatch_size, swatch_size)
        
        # Swatch çizimi
        pygame.draw.rect(self.screen, base, swatch_rect, border_radius=_s(6))
        
        # Swatch çerçevesi
        swatch_border = (255, 255, 255) if selected else (255, 255, 255, 100)
        pygame.draw.rect(self.screen, swatch_border, swatch_rect, 2, border_radius=_s(6))
        
        # 3. Yazı - Altta ortalı
        text_color = (200, 220, 255) if selected else (140, 150, 170)
        font = retro_style.get_font(_s(13), bold=selected)
        label = font.render(t('piece_workshop_custom_color'), True, text_color)
        self.screen.blit(label, label.get_rect(center=(rect.centerx, rect.bottom - _s(12))))

    def _draw_grid(self, grid_rect: pygame.Rect, cell_size: int):
        """Grid'i çiz"""
        for y in range(self.GRID_SIZE):
            for x in range(self.GRID_SIZE):
                rect = pygame.Rect(grid_rect.x + x * cell_size, grid_rect.y + y * cell_size, cell_size, cell_size)
                
                # Grid arka plan
                pygame.draw.rect(self.screen, (20, 28, 48), rect)
                pygame.draw.rect(self.screen, (35, 45, 70), rect, 1)
                
                cell = self.grid[y][x]
                if cell:
                    inner = rect.inflate(-4, -4)
                    color = cell['color']
                    self._draw_block_effect(inner, color, glow_alpha=0)

    def _draw_block_effect(self, rect: pygame.Rect, color, glow_alpha: int = 55) -> None:
        """Atölye bloklarını oyundaki gibi 3D + parlama ile çiz."""
        if rect.width <= 2 or rect.height <= 2:
            return

        size = max(2, min(rect.width, rect.height))
        x = rect.x + (rect.width - size) // 2
        y = rect.y + (rect.height - size) // 2
        color3 = tuple(color[:3])

        # Subtle outer glow (alpha blend). Additive blending can look harsh for
        # highly saturated colors (e.g., magenta/pink) due to channel clipping.
        if glow_alpha and glow_alpha > 0:
            glow_rect = pygame.Rect(x, y, size, size).inflate(10, 10)
            glow_surf = pygame.Surface(glow_rect.size, pygame.SRCALPHA)
            glow_rgb = tuple(min(255, int(c * 0.75 + 255 * 0.25)) for c in color3)
            pygame.draw.rect(glow_surf, (*glow_rgb, int(max(0, min(255, glow_alpha)))), glow_surf.get_rect(), border_radius=max(4, size // 5))
            self.screen.blit(glow_surf, glow_rect.topleft)

        # 3D jelly block (includes internal shine/highlights)
        draw_jelly_block(self.screen, x, y, size, color3)
    
    def _draw_cursor(self, grid_rect: pygame.Rect, cell_size: int):
        """Cursor çiz"""
        rect = pygame.Rect(
            grid_rect.x + self.cursor_x * cell_size,
            grid_rect.y + self.cursor_y * cell_size,
            cell_size, cell_size
        )
        
        # Glow
        _s = self._s
        glow_rect = rect.inflate(_s(6), _s(6))
        glow_surf = pygame.Surface(glow_rect.size, pygame.SRCALPHA)
        pygame.draw.rect(glow_surf, (*self.current_color, 60), glow_surf.get_rect(), border_radius=_s(4))
        self.screen.blit(glow_surf, glow_rect.topleft)
        
        # Border
        pygame.draw.rect(self.screen, self.current_color, rect, max(1, _s(3)), border_radius=_s(3))
    
    def _draw_color_palette(self, x: int, y: int, max_height: int):
        """Renk paleti çiz"""
        _s = self._s
        swatch_size = _s(28)
        spacing = _s(6)
        per_row = 3  # 3x4 layout
        
        # Palette container
        rows = (len(self.color_palette) + per_row - 1) // per_row
        palette_h = rows * (swatch_size + spacing) + _s(30) + _s(10)
        palette_w = per_row * (swatch_size + spacing) + _s(16)
        palette_rect = pygame.Rect(x, y, palette_w, min(palette_h, max_height))
        self.palette_rect = palette_rect
        self.palette_swatch_rects = []
        
        retro_style.draw_glass_panel(self.screen, palette_rect, alpha=150, border_color=(60, 80, 120))
        
        # Başlık
        title_font = retro_style.get_font(_s(12), bold=True)
        title = title_font.render(t('piece_workshop_palette_title'), True, (180, 195, 220))
        self.screen.blit(title, (palette_rect.x + _s(10), palette_rect.y + _s(6)))
        
        # Swatchlar
        for idx, color in enumerate(self.color_palette):
            col = idx % per_row
            row = idx // per_row
            sx = palette_rect.x + _s(10) + col * (swatch_size + spacing)
            sy = palette_rect.y + _s(26) + row * (swatch_size + spacing)
            
            swatch_rect = pygame.Rect(sx, sy, swatch_size, swatch_size)
            pygame.draw.rect(self.screen, color, swatch_rect, border_radius=_s(4))
            self.palette_swatch_rects.append((swatch_rect, idx))
            
            if idx == self.selected_color_idx:
                pygame.draw.rect(self.screen, (255, 255, 255), swatch_rect, 2, border_radius=_s(4))

            if idx == self.selected_color_idx:
                pygame.draw.rect(self.screen, (255, 255, 255), swatch_rect, 2, border_radius=_s(4))

        # Custom color button eski yeri (kaldırıldı)
    
    def _draw_pieces_panel(self, x: int, y: int, w: int, h: int):
        """Kayıtlı parçalar paneli"""
        _s = self._s
        panel_rect = pygame.Rect(x, y, w, h)
        retro_style.draw_glass_panel(
            self.screen,
            panel_rect,
            alpha=170,
            border_color=retro_style.primary,
            top_highlight=False,
        )
        self.last_pieces_panel_rect = panel_rect

        header_rect = pygame.Rect(panel_rect.x + _s(10), panel_rect.y + _s(10), panel_rect.width - _s(20), _s(30))
        self._draw_rounded_panel(
            header_rect,
            (16, 24, 48, 165),
            border_color=(78, 110, 160),
            radius=_s(11),
            top_highlight_alpha=12,
            inner_border_color=(255, 255, 255, 12),
        )

        # Başlık
        title_font = retro_style.get_font(_s(16), bold=True)
        title = title_font.render(t('piece_workshop_saved_pieces_title'), True, retro_style.primary)
        self.screen.blit(title, title.get_rect(midleft=(header_rect.x + _s(12), header_rect.centery)))
        count_font = retro_style.get_font(_s(12), bold=False)
        count_text = count_font.render(t('piece_workshop_piece_count', count=len(self.custom_pieces)), True, (150, 170, 200))
        self.screen.blit(count_text, count_text.get_rect(midright=(header_rect.right - _s(12), header_rect.centery)))

        self.piece_item_rects = []
        self.mode_tag_rects = []

        if not self.custom_pieces:
            empty_font = retro_style.get_font(14, bold=False)
            empty = empty_font.render(t('piece_workshop_no_pieces'), True, (140, 155, 180))
            self.screen.blit(empty, empty.get_rect(center=(panel_rect.centerx, panel_rect.centery)))
            return

        # Mode selector (for selected piece; if editing, it targets the editing piece)
        active_mode_piece_id = self._active_mode_piece_id()
        list_y = header_rect.bottom + _s(10)
        if active_mode_piece_id:
            piece = self._get_piece_by_id(active_mode_piece_id)
            if piece:
                raw_modes = piece.get('modes')
                modes = self._normalize_modes(raw_modes)
                cols = 3
                tag_w = (panel_rect.width - _s(44) - (cols - 1) * _s(8)) // cols
                tag_h = _s(28)
                mode_panel_h = _s(14) + _s(16) + ((len(WORKSHOP_MODES) + cols - 1) // cols) * (tag_h + _s(6)) + _s(12)
                mode_panel_rect = pygame.Rect(panel_rect.x + _s(10), header_rect.bottom + _s(8), panel_rect.width - _s(20), mode_panel_h)
                retro_style.draw_glass_panel(
                    self.screen,
                    mode_panel_rect,
                    alpha=120,
                    border_color=(70, 90, 120),
                    top_highlight=False,
                )

                mode_title_font = retro_style.get_font(_s(12), bold=True)
                mode_title = mode_title_font.render(t('piece_workshop_modes_title'), True, (185, 205, 235))
                self.screen.blit(mode_title, (mode_panel_rect.x + _s(10), mode_panel_rect.y + _s(6)))

                note_font = retro_style.get_font(_s(11), bold=False)
                if isinstance(raw_modes, list) and len(modes) == 0:
                    note_text = t('piece_workshop_modes_note_none')
                    note_color = (255, 170, 90)
                else:
                    note_text = t('piece_workshop_modes_note_selected')
                    note_color = (160, 180, 210)
                note = note_font.render(note_text, True, note_color)
                self.screen.blit(note, (mode_panel_rect.x + _s(10), mode_panel_rect.y + _s(24)))

                start_x = mode_panel_rect.x + _s(10)
                start_y = mode_panel_rect.y + _s(42)
                for idx, (mode_key, mode_label_key) in enumerate(WORKSHOP_MODES):
                    col = idx % cols
                    row = idx // cols
                    tag_rect = pygame.Rect(
                        start_x + col * (tag_w + _s(8)),
                        start_y + row * (tag_h + _s(6)),
                        tag_w,
                        tag_h,
                    )
                    enabled = mode_key in modes
                    fill = (52, 110, 86, 215) if enabled else (22, 30, 50, 180)
                    if idx == self.mode_focus:
                        border = retro_style.accent
                        glow_color = retro_style.accent
                        glow_alpha = 34
                    elif enabled:
                        border = (112, 188, 150)
                        glow_color = border
                        glow_alpha = 16
                    else:
                        border = (84, 98, 128)
                        glow_color = None
                        glow_alpha = 0

                    self._draw_rounded_panel(
                        tag_rect,
                        fill,
                        border_color=border,
                        border_width=2,
                        radius=_s(12),
                        glow_color=glow_color,
                        glow_alpha=glow_alpha,
                        top_highlight_alpha=18 if enabled else 8,
                        inner_border_color=(255, 255, 255, 18 if enabled else 10),
                    )

                    mode_label = t(mode_label_key)
                    label = retro_style.render_fit_text(
                        mode_label,
                        (235, 243, 255),
                        tag_rect.width - _s(22),
                        _s(12),
                        bold=True,
                        min_size=max(9, _s(9)),
                    )
                    self.screen.blit(label, label.get_rect(center=tag_rect.center))
                    if enabled:
                        dot_rect = pygame.Rect(tag_rect.width - _s(11), _s(6), _s(5), _s(5))
                        dot_rect.move_ip(tag_rect.x, tag_rect.y)
                        pygame.draw.rect(self.screen, (150, 255, 210), dot_rect, border_radius=_s(3))
                    self.mode_tag_rects.append(tag_rect)

                list_y = mode_panel_rect.bottom + _s(10)

        card_gap = _s(10)
        card_height = _s(92)
        # Liste alanı
        list_area_rect = pygame.Rect(panel_rect.x + _s(10), list_y, panel_rect.width - _s(20), panel_rect.bottom - list_y - _s(10))
        if list_area_rect.height > 20:
            retro_style.draw_glass_panel(
                self.screen,
                list_area_rect,
                alpha=110,
                border_color=(55, 70, 105),
                top_highlight=False,
            )

        list_padding = _s(10)
        max_row_width = min(list_area_rect.width - list_padding * 2, _s(720))
        list_left = list_area_rect.x + (list_area_rect.width - max_row_width) // 2
        list_top = list_area_rect.y + list_padding

        self.last_piece_list_y = list_top
        self.last_piece_item_height = card_height
        self.last_piece_item_gap = card_gap

        # Keep scroll within bounds every frame (panel height can change)
        self._clamp_pieces_scroll()
        
        # Parça listesi - kart düzeni
        available_w = max_row_width
        cols = 2 if available_w >= 520 else 1
        self.last_piece_item_cols = cols
        card_width = (available_w - (cols - 1) * card_gap) // cols

        for idx, piece in enumerate(self.custom_pieces):
            row = idx // cols
            col = idx % cols
            item_x = list_left + col * (card_width + card_gap)
            item_y = list_top + row * (card_height + card_gap) - self.pieces_scroll
            if item_y < list_area_rect.y + 2 or item_y > list_area_rect.bottom - card_height - 2:
                continue

            item_rect = pygame.Rect(item_x, item_y, card_width, card_height)
            self.piece_item_rects.append((item_rect, piece['id']))

            # Arka plan
            is_editing = piece['id'] == self.editing_piece_id
            is_selected = idx == self.selected_piece_idx
            if is_editing:
                bg_color = (44, 64, 94, 225)
                border_col = retro_style.accent
                glow_color = retro_style.accent
                border_w = 2
            elif is_selected:
                bg_color = (32, 54, 86, 215)
                border_col = retro_style.primary
                glow_color = retro_style.primary
                border_w = 2
            else:
                bg_color = (22, 32, 55, 190)
                border_col = (55, 70, 105)
                glow_color = None
                border_w = 1

            self._draw_rounded_panel(
                item_rect,
                bg_color,
                border_color=border_col,
                border_width=border_w,
                radius=_s(12),
                glow_color=glow_color,
                glow_alpha=28 if glow_color else 0,
                top_highlight_alpha=16 if glow_color else 8,
                inner_border_color=(255, 255, 255, 14 if glow_color else 8),
            )

            # Parça önizleme (mini)
            preview_size = min(_s(62), card_height - _s(22))
            preview_rect = pygame.Rect(item_rect.x + _s(12), item_rect.y + _s(12), preview_size, preview_size)
            self._draw_rounded_panel(
                preview_rect,
                (16, 24, 42, 225),
                border_color=border_col if glow_color else (56, 72, 106),
                radius=_s(8),
                top_highlight_alpha=10,
                inner_border_color=(255, 255, 255, 10),
            )
            self._draw_mini_piece(preview_rect, piece)

            # İsim
            text_x = preview_rect.right + _s(12)
            text_max_w = max(_s(70), item_rect.right - text_x - _s(12))
            name = retro_style.render_fit_text(
                piece['name'],
                (225, 235, 250),
                text_max_w,
                _s(14),
                bold=True,
                min_size=max(10, _s(10)),
            )
            name_y = item_rect.y + _s(12)
            self.screen.blit(name, (text_x, name_y))

            # Blok sayısı
            cells = piece.get('cells') or []
            block_count = len(cells) if cells else len(piece.get('shape', []))
            info = retro_style.render_fit_text(
                t('piece_workshop_block_count', count=block_count),
                (145, 165, 190),
                text_max_w,
                _s(12),
                bold=False,
                min_size=max(9, _s(9)),
            )
            info_y = name_y + name.get_height() + _s(8)
            self.screen.blit(info, (text_x, info_y))

            # Mod etiketi (özet)
            modes = self._normalize_modes(piece.get('modes'))
            mode_text = (
                t('piece_workshop_all_modes')
                if len(modes) == len(WORKSHOP_MODES)
                else (t('piece_workshop_no_modes') if len(modes) == 0 else t('piece_workshop_mode_count', count=len(modes)))
            )
            mode_color = (130, 228, 182) if len(modes) > 0 else (205, 160, 140)
            mode_chip = retro_style.render_fit_text(
                mode_text,
                mode_color,
                text_max_w - _s(14),
                _s(11),
                bold=True,
                min_size=max(9, _s(9)),
            )
            mode_chip_rect = pygame.Rect(
                text_x,
                item_rect.bottom - _s(28),
                min(text_max_w, mode_chip.get_width() + _s(16)),
                _s(20),
            )
            self._draw_rounded_panel(
                mode_chip_rect,
                (20, 38, 58, 195) if len(modes) > 0 else (42, 30, 30, 185),
                border_color=(86, 162, 132) if len(modes) > 0 else (148, 108, 92),
                radius=_s(9),
                top_highlight_alpha=8,
                inner_border_color=(255, 255, 255, 10),
            )
            self.screen.blit(mode_chip, mode_chip.get_rect(center=mode_chip_rect.center))
    
    def _draw_mini_piece(self, rect: pygame.Rect, piece: Dict):
        """Mini parça önizleme - grid görünümüyle birebir aynı stil"""
        cells = piece.get('cells', [])
        if not cells:
            shape = piece.get('shape', [])
            if shape:
                cells = [{'pos': pos, 'color': self.current_color} for pos in shape]
        if not cells:
            return
        
        # Parça boyutlarını hesapla
        xs = [c['pos'][0] for c in cells]
        ys = [c['pos'][1] for c in cells]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        piece_w = max_x - min_x + 1
        piece_h = max_y - min_y + 1
        
        # Oyun tahtasındaki gibi: her hücrede 1px iç boşluk, bloklar cell_size-2
        cell_size = min(rect.width // max(piece_w, 1), rect.height // max(piece_h, 1))
        cell_size = max(10, min(cell_size, 20))
        
        # Parçayı merkeze al
        total_w = piece_w * cell_size
        total_h = piece_h * cell_size
        offset_x = rect.x + (rect.width - total_w) // 2
        offset_y = rect.y + (rect.height - total_h) // 2
        
        for cell in cells:
            px, py = cell['pos']
            raw_color = cell.get('color') if isinstance(cell, dict) else None
            color = tuple((raw_color or self.current_color)[:3])
            
            # Normalize pozisyon (min'e göre)
            nx = px - min_x
            ny = py - min_y
            
            block_rect = pygame.Rect(
                offset_x + nx * cell_size + 1,
                offset_y + ny * cell_size + 1,
                max(6, cell_size - 2),
                max(6, cell_size - 2),
            )
            self._draw_block_effect(block_rect, color, glow_alpha=20)

    def _draw_action_button(self, rect: pygame.Rect, label: str, color: tuple):
        """Kullanıcı ekranı stilinde buton çiz"""
        if rect.width <= 0 or rect.height <= 0:
            return
        _s = self._s
        # Arka plan
        pygame.draw.rect(self.screen, color, rect, border_radius=_s(12))
        # Beyaz kenar
        pygame.draw.rect(self.screen, (255, 255, 255, 100), rect, 2, border_radius=_s(12))
        # Metin
        font = retro_style.get_font(_s(14), bold=False)
        text = font.render(label, True, (255, 255, 255))
        self.screen.blit(text, text.get_rect(center=rect.center))

    def _draw_block_styles_card(self, rect: pygame.Rect) -> None:
        """Parça Atölyesi içinde Blok Görünümleri kısayol kartı çiz."""
        if rect.width <= 0 or rect.height <= 0:
            return

        mouse_pos = get_mouse_pos()
        hovered = rect.collidepoint(mouse_pos)
        accent = (190, 120, 255)
        panel_scale = max(0.82, min(1.12, min(rect.width / 300.0, rect.height / 290.0)))
        s = lambda v, minimum=1: max(minimum, int(round(v * panel_scale)))

        retro_style.draw_glass_panel(
            self.screen,
            rect,
            alpha=210 if hovered else 182,
            border_color=accent,
        )
        pygame.draw.rect(self.screen, (*accent, 180 if hovered else 130), rect, 2 if hovered else 1, border_radius=14)

        if hovered:
            glow_rect = rect.inflate(8, 8)
            glow = pygame.Surface(glow_rect.size, pygame.SRCALPHA)
            pygame.draw.rect(glow, (*accent, 36), glow.get_rect(), border_radius=18)
            self.screen.blit(glow, glow_rect.topleft)

        title_area = pygame.Rect(rect.x + s(14), rect.y + s(12), rect.width - s(28), max(s(34), int(rect.height * 0.17)))
        title_font = retro_style.get_font(max(16, s(18)), bold=True)
        title_surf = title_font.render(t('block_styles'), True, accent)

        title_bg_w = min(rect.width - s(10), title_surf.get_width() + s(26))
        title_bg_h = title_surf.get_height() + s(18)
        title_bg = pygame.Surface((title_bg_w, title_bg_h), pygame.SRCALPHA)
        pygame.draw.rect(title_bg, (8, 12, 30, 210), title_bg.get_rect(), border_top_left_radius=14, border_top_right_radius=14, border_bottom_left_radius=8, border_bottom_right_radius=8)
        pygame.draw.rect(title_bg, (*accent, 110), title_bg.get_rect(), 1, border_top_left_radius=14, border_top_right_radius=14, border_bottom_left_radius=8, border_bottom_right_radius=8)
        inner_rect = rect.inflate(-s(2), -s(2))
        image_top = inner_rect.y
        image_bottom = inner_rect.bottom
        image_rect = pygame.Rect(
            inner_rect.x,
            image_top,
            inner_rect.width,
            max(s(144), image_bottom - image_top),
        )

        bg_path = ROOT_DIR / 'assets' / 'main_theme' / 'blok_gorunum.png'
        bg_image = getattr(self, '_block_styles_card_bg', None)
        bg_failed = getattr(self, '_block_styles_card_bg_failed', False)
        if bg_image is None and not bg_failed:
            try:
                bg_image = pygame.image.load(str(bg_path)).convert_alpha()
                self._block_styles_card_bg = bg_image
            except Exception:
                self._block_styles_card_bg_failed = True
                bg_image = None

        image_panel = pygame.Surface(image_rect.size, pygame.SRCALPHA)
        pygame.draw.rect(image_panel, (12, 18, 36, 120), image_panel.get_rect(), border_radius=12)
        self.screen.blit(image_panel, image_rect.topleft)

        if bg_image is not None:
            src_w, src_h = bg_image.get_size()
            if src_w > 0 and src_h > 0:
                zoom = 1.18 if hovered else 1.12
                scale = max(
                    (image_rect.width * zoom) / max(1, src_w),
                    (image_rect.height * zoom) / max(1, src_h),
                )
                cover_w = max(1, int(src_w * scale))
                cover_h = max(1, int(src_h * scale))
                scaled = pygame.transform.smoothscale(bg_image, (cover_w, cover_h))
                focus_x = 0.50
                focus_y = 0.54
                draw_x = image_rect.x - int((cover_w - image_rect.width) * focus_x)
                draw_y = image_rect.y - int((cover_h - image_rect.height) * focus_y)
                prev_clip = self.screen.get_clip()
                self.screen.set_clip(image_rect)
                self.screen.blit(scaled, (draw_x, draw_y))
                overlay = pygame.Surface(image_rect.size, pygame.SRCALPHA)
                overlay.fill((0, 0, 0, 96 if hovered else 108))
                self.screen.blit(overlay, image_rect.topleft)
                self.screen.set_clip(prev_clip)
        else:
            preview_colors = [
                (0, 255, 255),
                (255, 165, 0),
                (255, 0, 255),
                (100, 200, 255),
                (50, 205, 50),
            ]
            block_size = max(18, min(34, image_rect.width // 8, image_rect.height // 5))
            origin_x = image_rect.x + max(14, image_rect.width // 5)
            origin_y = image_rect.y + max(16, image_rect.height // 3)
            block_offsets = [(0, 0), (1, 0), (0, 1), (3, 1), (4, 1)]
            for color, (ox, oy) in zip(preview_colors, block_offsets):
                block_rect = pygame.Rect(
                    origin_x + ox * (block_size + 6),
                    origin_y + oy * (block_size + 6),
                    block_size,
                    block_size,
                )
                self._draw_block_effect(block_rect, color, glow_alpha=28 if hovered else 18)

        self.screen.blit(title_bg, (rect.x + s(8), rect.y + s(4)))
        self.screen.blit(title_surf, (rect.x + s(18), rect.y + s(12)))

        subtitle = t('block_styles_showcase_desc')
        sub_pad_x = s(14)
        sub_pad_y = s(7)
        sub_max_w = rect.width - s(28)
        font_size = max(12, s(13))
        sub_font = retro_style.get_font(font_size, bold=True)
        sub_lines = retro_style.wrap_text(subtitle, sub_font, max(s(60), sub_max_w - sub_pad_x * 2))[:1]
        line_h = sub_font.get_linesize()
        sub_bg_h = line_h + sub_pad_y * 2
        sub_bg_w = min(sub_max_w, max(sub_font.size(sub_lines[0])[0] + sub_pad_x * 2 + 8, s(150))) if sub_lines else s(150)
        sub_bg_x = rect.x + s(14)
        sub_bg_y = rect.bottom - s(14) - sub_bg_h
        sub_bg = pygame.Surface((sub_bg_w, sub_bg_h), pygame.SRCALPHA)
        pygame.draw.rect(sub_bg, (12, 20, 45, 210), sub_bg.get_rect(), border_radius=9)
        pygame.draw.rect(sub_bg, (*accent, 160), sub_bg.get_rect(), 2 if hovered else 1, border_radius=9)
        self.screen.blit(sub_bg, (sub_bg_x, sub_bg_y))
        if sub_lines:
            sub_surf = sub_font.render(sub_lines[0], True, (235, 243, 255))
            text_y = sub_bg_y + (sub_bg_h - sub_surf.get_height()) // 2
            self.screen.blit(sub_surf, (sub_bg_x + sub_pad_x, text_y))
