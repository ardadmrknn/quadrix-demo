"""Co-op Board: 20 sütunlu ortak tahta.

Board sınıfından miras alır. P1 (sütun 0-9) ve P2 (sütun 10-19) bölgelerini
yönetir. Orta çizgi sert duvar olarak davranır — parçalar karşı tarafa geçemez.
"""

from board import Board
from pieces import Piece


class CoopBoard(Board):
    """20×20 ortak co-op tahtası."""

    MIDLINE = 10  # P2 bölgesinin başlangıç sütunu

    def __init__(self):
        super().__init__(width=20, height=20)
        # Son clear işlemindeki katkı bilgisi
        self.last_clear_p1_cells = 0
        self.last_clear_p2_cells = 0
        # Son clear işlemindeki satır renkleri (sweep animasyonu için)
        self.last_clear_row_colors: dict[int, list] = {}

    # ------------------------------------------------------------------
    # Bölge yardımcıları
    # ------------------------------------------------------------------

    @staticmethod
    def _player_columns(player: str) -> range:
        """Oyuncunun sahip olduğu sütun aralığını döndür."""
        if player == "P1":
            return range(0, CoopBoard.MIDLINE)
        return range(CoopBoard.MIDLINE, 20)

    # ------------------------------------------------------------------
    # Pozisyon / spawn kontrolleri
    # ------------------------------------------------------------------

    def is_valid_position_for_player(self, piece: Piece, player: str,
                                     dx: int = 0, dy: int = 0) -> bool:
        """Parçanın board sınırları + dolu hücre + oyuncu bölge kontrolü."""
        cols = self._player_columns(player)
        for px, py in piece.get_cells():
            px += dx
            py += dy
            # Board alt/üst sınır
            if py >= self.height:
                return False
            if py < 0:
                continue
            # Oyuncu bölgesi kontrolü (orta çizgi sert duvar)
            if px not in cols:
                return False
            # Dolu hücre kontrolü
            if self.occupancy[py][px]:
                return False
        return True

    def get_spawn_position(self, player: str) -> tuple[int, int]:
        """Oyuncunun parça spawn koordinatını döndür."""
        if player == "P1":
            return (3, 0)
        return (13, 0)  # 10 + 3

    def can_spawn(self, piece: Piece, player: str) -> bool:
        """Spawn pozisyonunda parça yerleştirilebilir mi?"""
        sx, sy = self.get_spawn_position(player)
        piece.x = sx
        piece.y = sy
        return self.is_valid_position_for_player(piece, player)

    # ------------------------------------------------------------------
    # Parça kilitleme (owner = "P1" / "P2")
    # ------------------------------------------------------------------

    def lock_piece_for_player(self, piece: Piece, player: str) -> int:
        """Parçayı kilitle ve owners grid'ine oyuncu bilgisi yaz.

        Board.lock_piece() çağrılır, ardından owners grid'i oyuncu bazlı
        güncellenir. Dönüş: temizlenen satır sayısı.
        """
        # Kilitleme öncesi owners'ı geçici olarak patch'le:
        # Board.lock_piece piece.name yazar; biz player string'i istiyoruz.
        original_name = piece.name
        piece.name = player  # "P1" veya "P2"
        cleared = super().lock_piece(piece)
        piece.name = original_name  # Orijinal parça ismini geri yükle
        return cleared

    # ------------------------------------------------------------------
    # Satır temizleme — katkı hesaplaması
    # ------------------------------------------------------------------

    def clear_lines(self, source: str = "player") -> int:
        """Dolu satırları temizle ve katkı bilgisini güncelle.

        Temizlemeden ÖNCE her dolu satırdaki P1/P2 hücre sayısını sayar,
        sonra Board.clear_lines()'ı çağırır.
        """
        # Temizlenecek satırları tespit et (Board ile aynı mantık)
        p1_cells = 0
        p2_cells = 0
        row_colors: dict[int, list] = {}
        for y in range(self.height):
            if all(self.occupancy[y][x] for x in range(self.width)):
                # Satır renklerini sil işleminden ÖNCE kaydet
                row_colors[y] = [self.grid[y][x] for x in range(self.width)]
                for x in range(self.width):
                    owner = self.owners[y][x]
                    if owner == "P1":
                        p1_cells += 1
                    elif owner == "P2":
                        p2_cells += 1

        self.last_clear_p1_cells = p1_cells
        self.last_clear_p2_cells = p2_cells
        self.last_clear_row_colors = row_colors

        return super().clear_lines(source)
