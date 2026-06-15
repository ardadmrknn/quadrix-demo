"""Quadrix parçalarını (Tetromino) tanımlar"""
import random
from constants import COLORS

# Tetromino şekilleri (I, O, T, S, Z, J, L)
SHAPES = [
    # I (4x4 kutu içinde, merkezden dönme için)
    [[0, 0, 0, 0],
     [1, 1, 1, 1],
     [0, 0, 0, 0],
     [0, 0, 0, 0]],
    # O (2x2)
    [[1, 1],
     [1, 1]],
    # T (3x3 kutu içinde, merkez: [1,1])
    [[0, 1, 0],
     [1, 1, 1],
     [0, 0, 0]],
    # S (3x3)
    [[0, 1, 1],
     [1, 1, 0],
     [0, 0, 0]],
    # Z (3x3)
    [[1, 1, 0],
     [0, 1, 1],
     [0, 0, 0]],
    # J (3x3)
    [[1, 0, 0],
     [1, 1, 1],
     [0, 0, 0]],
    # L (3x3)
    [[0, 0, 1],
     [1, 1, 1],
     [0, 0, 0]]
]

# Quadrix 2 için EKSTRA parçalar
EXTRA_SHAPES = [
    [[0, 1, 0], [1, 1, 1], [0, 1, 0]],  # Plus (+) - 5 blok
    [[1, 0, 1], [1, 1, 1], [0, 1, 0]],  # Y-Shape (compact) - 6 blok
    [[1, 1], [0, 0]],  # Domino - 2 blok (2x2 kutu içinde, merkezden dönme için)
    [[1, 1, 1], [1, 1, 1], [1, 1, 1]]  # Big Square - 9 blok (TAM DOLU 3x3)
]

EXTRA_COLORS = [
    (255, 0, 255),    # Plus (+) - Magenta/Pembe parlak
    (0, 255, 255),    # Y - Cyan/Turkuaz
    (255, 128, 0),    # Domino - Turuncu
    (255, 215, 0)     # BigSquare (3x3) - Altın
]
# J, L, S, Z, T parçaları için SRS Kicks (Pygame koordinat sistemine göre -y yukarıdır)
SRS_KICKS_NORMAL = {
    # (eski_durum, yeni_durum): [(dx, dy), (dx, dy), (dx, dy), (dx, dy), (dx, dy)]
    (0, 1): [(0, 0), (-1, 0), (-1, -1), (0, 2), (-1, 2)],
    (1, 0): [(0, 0), (1, 0), (1, 1), (0, -2), (1, -2)],
    (1, 2): [(0, 0), (1, 0), (1, 1), (0, -2), (1, -2)],
    (2, 1): [(0, 0), (-1, 0), (-1, -1), (0, 2), (-1, 2)],
    (2, 3): [(0, 0), (1, 0), (1, -1), (0, 2), (1, 2)],
    (3, 2): [(0, 0), (-1, 0), (-1, 1), (0, -2), (-1, -2)],
    (3, 0): [(0, 0), (-1, 0), (-1, 1), (0, -2), (-1, -2)],
    (0, 3): [(0, 0), (1, 0), (1, -1), (0, 2), (1, 2)],
}

# I parçası için SRS Kicks (Pygame koordinat sistemine göre -y yukarıdır)
SRS_KICKS_I = {
    (0, 1): [(0, 0), (-2, 0), (1, 0), (-2, 1), (1, -2)],
    (1, 0): [(0, 0), (2, 0), (-1, 0), (2, -1), (-1, 2)],
    (1, 2): [(0, 0), (-1, 0), (2, 0), (-1, -2), (2, 1)],
    (2, 1): [(0, 0), (1, 0), (-2, 0), (1, 2), (-2, -1)],
    (2, 3): [(0, 0), (2, 0), (-1, 0), (2, -1), (-1, 2)],
    (3, 2): [(0, 0), (-2, 0), (1, 0), (-2, 1), (1, -2)],
    (3, 0): [(0, 0), (1, 0), (-2, 0), (1, 2), (-2, -1)],
    (0, 3): [(0, 0), (-1, 0), (2, 0), (-1, -2), (2, 1)],
}

# J, L, T, S, Z parçaları için SRS+ 180 Kicks
SRS_KICKS_180_NORMAL = {
    (0, 2): [(0, 0), (0, 1), (1, 0), (-1, 0), (1, 1), (-1, 1), (0, -1)],
    (2, 0): [(0, 0), (0, -1), (-1, 0), (1, 0), (-1, -1), (1, -1), (0, 1)],
    (1, 3): [(0, 0), (1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 0)],
    (3, 1): [(0, 0), (-1, 0), (0, 1), (0, -1), (-1, 1), (-1, -1), (1, 0)],
}

# I parçası için SRS+ 180 Kicks
SRS_KICKS_180_I = {
    (0, 2): [(0, 0), (-1, 0), (1, 0), (-2, 0), (2, 0), (0, 1), (0, -1)],
    (2, 0): [(0, 0), (1, 0), (-1, 0), (2, 0), (-2, 0), (0, -1), (0, 1)],
    (1, 3): [(0, 0), (0, 1), (0, -1), (0, 2), (0, -2), (-1, 0), (1, 0)],
    (3, 1): [(0, 0), (0, -1), (0, 1), (0, -2), (0, 2), (1, 0), (-1, 0)],
}

SHAPE_NAMES = ['I', 'O', 'T', 'S', 'Z', 'J', 'L']
EXTRA_SHAPE_NAMES = ['Plus', 'Y', 'Domino', 'BigSquare']
HIDDEN_SPAWN_ROWS = 2


def get_piece_top_filled_row(piece_or_shape) -> int:
    """Return the first row index that contains a filled cell."""
    shape = getattr(piece_or_shape, 'shape', None)
    if shape is None:
        shape = piece_or_shape
    if not shape:
        return 0
    try:
        for row_index, row in enumerate(shape):
            if any(row):
                return row_index
    except TypeError:
        return 0
    return 0


def get_piece_spawn_y(piece_or_shape, hidden_rows: int = HIDDEN_SPAWN_ROWS) -> int:
    """Spawn pieces in a small hidden buffer above the visible board."""
    return -(get_piece_top_filled_row(piece_or_shape) + max(0, int(hidden_rows or 0)))


def skip_hidden_rows(piece, board) -> None:
    """Instantly drop *piece* through hidden spawn rows for immediate visibility.

    After a piece is placed at its spawn position (negative y), this moves it
    down through the hidden zone until it either becomes visible (y >= 0) or
    can no longer move without overlapping existing blocks.
    """
    if piece is None or board is None:
        return
    cur_y = getattr(piece, 'y', 0)
    if cur_y >= 0:
        return
    try:
        while piece.y < 0 and board.is_valid_position(piece, dy=1):
            piece.y += 1
    except (AttributeError, TypeError):
        pass


class Piece:
    """Bir Quadrix parçasını temsil eder"""
    
    def __init__(self, x=3, y=0, shape_index=None):
        """
        Yeni bir parça oluştur
        
        Args:
            x: Başlangıç x pozisyonu
            y: Başlangıç y pozisyonu
            shape_index: Belirli bir şekil indeksi (None ise rastgele)
        """
        self.x = x
        self.y = y
        if shape_index is None:
            shape_index = random.randint(0, len(SHAPES) - 1)
        self.shape_index = shape_index
        self.shape = [row[:] for row in SHAPES[shape_index]]
        self.color = COLORS[shape_index]
        self.name = SHAPE_NAMES[shape_index]
        self.texture_path = None
        self.texture_surface = None
        self.texture_surface_original = None
        self.rotation_state = 0  # 0,1,2,3 -> saat yönü
    
    def rotate(self, direction=1):
        """Parçayı döndür. direction=1 saat yönü, direction=-1 ters yön."""
        # Normalize: -1 yön = 3 kez saat yönü dönüş
        steps = direction % 4
        for _ in range(steps):
            # Clockwise dönüş
            self.shape = [[self.shape[y][x] for y in range(len(self.shape) - 1, -1, -1)]
                          for x in range(len(self.shape[0]))]
            # Rotate optional per-cell color matrix in lock-step with shape.
            if hasattr(self, 'color_matrix') and getattr(self, 'color_matrix', None) is not None:
                try:
                    cm = self.color_matrix
                    self.color_matrix = [[cm[y][x] for y in range(len(cm) - 1, -1, -1)]
                                         for x in range(len(cm[0]))]
                except Exception:
                    # If matrix is malformed, drop it rather than breaking rotation.
                    self.color_matrix = None
            self.rotation_state = (self.rotation_state + 1) % 4
    
    def try_rotate_srs(self, board, direction: int = 1, check_func=None) -> bool:
        """
        SRS (Super Rotation System) kurallarına göre parçayı döndürmeyi dener.
        Başarılıysa parçanın konumunu ve rotation_state'ini güncelleyip True döner.
        Başarısızsa tüm değişiklikleri geri alıp False döner.
        
        Args:
            board: Oyun tahtası
            direction: 1 (Saat yönü), -1 (Saat yönünün tersi)
            check_func: Özel konum kontrol fonksiyonu (örn: co-op'taki oyuncu bazlı sınırlar için)
        """
        original_x = self.x
        original_y = self.y
        original_state = self.rotation_state
        self.last_kick_index = 0
        
        if check_func is None:
            check_func = lambda p: board.is_valid_position(p)
            
        # O parçası wall kick yapmaz, sadece döndürme testi yapılır
        if self.name == 'O':
            self.rotate(direction)
            if check_func(self):
                return True
            self.rotate(-direction)
            return False
            
        # Parçayı geçici olarak döndür
        self.rotate(direction)
        new_state = self.rotation_state
        
        # Parça tipine göre kick tablosunu seç
        if self.name == 'I':
            kicks = SRS_KICKS_I
        else:
            # Diğer standart parçalar ve Quadrix 2 ekstra parçaları (Plus, Y, Domino, BigSquare)
            # NORMAL kick tablosunu fallback olarak kullanır
            kicks = SRS_KICKS_NORMAL
            
        transition = (original_state, new_state)
        test_vectors = kicks.get(transition, [(0, 0)])
        
        for test_idx, (dx, dy) in enumerate(test_vectors):
            self.x = original_x + dx
            self.y = original_y + dy
            if check_func(self):
                self.last_kick_index = test_idx
                return True
                
        # Hiçbir test geçmedi, değişiklikleri geri al
        self.x = original_x
        self.y = original_y
        self.rotate(-direction)
        return False

    def try_rotate_180(self, board, check_func=None) -> bool:
        """
        180 derece döndürmeyi dener.
        Başarılıysa parçanın konumunu ve rotation_state'ini güncelleyip True döner.
        Başarısızsa tüm değişiklikleri geri alıp False döner.
        """
        original_x = self.x
        original_y = self.y
        original_state = self.rotation_state
        self.last_kick_index = 0
        
        if check_func is None:
            check_func = lambda p: board.is_valid_position(p)
            
        # O parçası wall kick yapmaz, sadece döndürme testi yapılır
        if self.name == 'O':
            self.rotate(2)
            if check_func(self):
                return True
            self.rotate(-2)
            return False
            
        # Parçayı geçici olarak 180 derece döndür
        self.rotate(2)
        new_state = self.rotation_state
        
        # Parça tipine göre 180 derece kick tablosunu seç
        if self.name == 'I':
            kicks = SRS_KICKS_180_I
        else:
            kicks = SRS_KICKS_180_NORMAL
            
        transition = (original_state, new_state)
        test_vectors = kicks.get(transition, [(0, 0)])
        
        for test_idx, (dx, dy) in enumerate(test_vectors):
            self.x = original_x + dx
            self.y = original_y + dy
            if check_func(self):
                self.last_kick_index = test_idx
                return True
                
        # Hiçbir test geçmedi, değişiklikleri geri al
        self.x = original_x
        self.y = original_y
        self.rotate(-2)
        return False

    def get_shape(self):
        """Parçanın mevcut şekil matrisini döndür."""
        return self.shape

    def get_cells(self):
        """
        Parçanın kapladığı tüm hücrelerin koordinatlarını döndür
        
        Returns:
            list: (x, y) koordinat listesi
        """
        cells = []
        for y, row in enumerate(self.shape):
            for x, cell in enumerate(row):
                if cell:
                    cells.append((self.x + x, self.y + y))
        return cells
    
    def get_width(self):
        """Parçanın genişliğini döndür"""
        return len(self.shape[0]) if self.shape else 0
    
    def get_height(self):
        """Parçanın yüksekliğini döndür"""
        return len(self.shape)
    
    def copy(self):
        """Parçanın bir kopyasını oluştur"""
        # Extra parça ise özel kopyalama
        if hasattr(self, 'name') and self.name in ['Plus', 'Y', 'Domino', 'BigSquare']:
            new_piece = Piece(self.x, self.y, 0)  # Dummy piece
            new_piece.shape = [row[:] for row in self.shape]
            new_piece.color = self.color
            new_piece.name = self.name
            new_piece.shape_index = self.shape_index
            new_piece.texture_path = self.texture_path
            new_piece.texture_surface = self.texture_surface
            new_piece.texture_surface_original = self.texture_surface_original
            new_piece.rotation_state = self.rotation_state
            if hasattr(self, 'is_workshop_piece'):
                new_piece.is_workshop_piece = getattr(self, 'is_workshop_piece')
            if hasattr(self, 'workshop_block_id'):
                new_piece.workshop_block_id = getattr(self, 'workshop_block_id')
            if hasattr(self, 'color_matrix'):
                cm = getattr(self, 'color_matrix', None)
                new_piece.color_matrix = [row[:] for row in cm] if cm is not None else None
            # Perk bayrakları: ghost/önizleme gibi tüketiciler is_valid_position'ı
            # doğru değerlendirsin diye taşı (varsa).
            for _flag in ('flexible_border', 'tunnel', 'drill'):
                if hasattr(self, _flag):
                    setattr(new_piece, _flag, getattr(self, _flag))
            return new_piece
        else:
            # Normal parça
            new_piece = Piece(self.x, self.y, self.shape_index)
            new_piece.shape = [row[:] for row in self.shape]
            new_piece.color = self.color
            new_piece.texture_path = self.texture_path
            new_piece.texture_surface = self.texture_surface
            new_piece.texture_surface_original = self.texture_surface_original
            new_piece.rotation_state = self.rotation_state
            if hasattr(self, 'is_workshop_piece'):
                new_piece.is_workshop_piece = getattr(self, 'is_workshop_piece')
            if hasattr(self, 'workshop_block_id'):
                new_piece.workshop_block_id = getattr(self, 'workshop_block_id')
            if hasattr(self, 'color_matrix'):
                cm = getattr(self, 'color_matrix', None)
                new_piece.color_matrix = [row[:] for row in cm] if cm is not None else None
            # Perk bayrakları: ghost/önizleme gibi tüketiciler is_valid_position'ı
            # doğru değerlendirsin diye taşı (varsa).
            for _flag in ('flexible_border', 'tunnel', 'drill'):
                if hasattr(self, _flag):
                    setattr(new_piece, _flag, getattr(self, _flag))
            return new_piece


def create_random_piece(x=3, y=0):
    """Rastgele bir parça oluştur"""
    return Piece(x, y)


def create_random_tetris2_piece(x=3, y=0):
    """Quadrix 2 için rastgele parça - TÜM 11 PARÇA EŞİT ŞANS (her biri %9.09)"""
    # Toplam 11 parça: 0-6 klasik, 7-10 extra
    piece_index = random.randint(0, 10)
    
    if piece_index < 7:
        # KLASİK PARÇA (0-6): I, O, T, S, Z, J, L
        return Piece(x, y, piece_index)
    else:
        # EXTRA PARÇA (7-10): Plus, Y, Domino, BigSquare
        extra_index = piece_index - 7  # 0-3 arası
        piece = create_extra_piece(extra_index, x=x, y=0)
        color_names = ['MAGENTA', 'CYAN', 'TURUNCU', 'ALTIN']
        print(f"🎲 EXTRA PARÇA: {piece.name} ({color_names[extra_index]})")
        return piece


def create_piece_by_index(index, x=3, y=0):
    """Belirli indeksteki parçayı oluştur"""
    return Piece(x, y, index)


def create_extra_piece(extra_index, x=3, y=0):
    """Belirli ekstra parçayı oluştur."""
    extra_index = max(0, min(extra_index, len(EXTRA_SHAPES) - 1))
    piece = Piece(x, y, 0)
    piece.shape = [row[:] for row in EXTRA_SHAPES[extra_index]]
    piece.shape_index = 7 + extra_index
    piece.name = EXTRA_SHAPE_NAMES[extra_index]
    piece.color = EXTRA_COLORS[extra_index]
    piece.texture_path = None
    piece.texture_surface = None
    piece.texture_surface_original = None
    return piece


def create_piece_by_name(name, x=3, y=0):
    """Üçüncü parti çağrılar için isimden parça üret."""
    if name in SHAPE_NAMES:
        return Piece(x, y, SHAPE_NAMES.index(name))
    if name in EXTRA_SHAPE_NAMES:
        return create_extra_piece(EXTRA_SHAPE_NAMES.index(name), x, y)
    raise ValueError(f"Bilinmeyen parça adı: {name}")
