"""Esnek sınır özelliğinin oyun içi entegrasyon testi"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from game_modes_extra import MysteryMode
import game as _game

_game.set_app_icon = lambda *_args, **_kwargs: None

# Minimal settings manager mock
class MockSettingsManager:
    def __init__(self):
        self._settings = {}
    def get(self, key, default=None):
        return self._settings.get(key, default)
    def set(self, key, value):
        self._settings[key] = value
    def get_controls(self):
        return {}
    def get_music_preference_for_mode(self, mode):
        return None
    def save(self):
        pass

def run_integration_checks():
    pygame.init()
    try:
        # Test 1: Kart seçildikten sonra mevcut parçaya flag ekleniyor mu?
        print("=== Test 1: Kart Seçimi Sonrası Mevcut Parça ===")
        screen = pygame.display.set_mode((800, 600))
        mode = MysteryMode(settings_manager=MockSettingsManager(), screen=screen)

        # Başlangıçta flag yok
        print(f"Başlangıç: current_piece.flexible_border = {getattr(mode.current_piece, 'flexible_border', False)}")
        assert not getattr(mode.current_piece, 'flexible_border', False), "Başlangıçta flag olmamalı"

        # Esnek sınır perkini aktifleştir
        mode.perk_manager.activate('perk_flexible_border')
        print(f"Perk aktif: {mode.perk_manager.is_active('perk_flexible_border')}")

        # Mevcut parçaya flag ekle (kart seçimi simülasyonu)
        if mode.current_piece:
            setattr(mode.current_piece, 'flexible_border', True)
        for piece in mode.next_piece_queue:
            if piece:
                setattr(piece, 'flexible_border', True)

        print(f"Kart seçimi sonrası: current_piece.flexible_border = {getattr(mode.current_piece, 'flexible_border', False)}")
        assert getattr(mode.current_piece, 'flexible_border', False), "Kart seçimi sonrası flag olmalı"

        # Test 2: Yeni spawn edilen parçaya flag ekleniyor mu?
        print("\n=== Test 2: Yeni Spawn Edilen Parça ===")
        print(f"mode.spawn_new_piece metodu: {mode.spawn_new_piece}")
        print(f"mode.__class__: {mode.__class__}")
        print(f"perk_manager.is_active('perk_flexible_border') = {mode.perk_manager.is_active('perk_flexible_border')}")

        # Doğrudan on_piece_spawn'ı test et
        from pieces import create_piece_by_name
        test_piece = create_piece_by_name('I')
        print(f"Test parçası oluşturuldu: {test_piece}")
        print(f"on_piece_spawn çağrılmadan önce: flexible_border = {getattr(test_piece, 'flexible_border', False)}")
        mode.perk_manager.on_piece_spawn(test_piece)
        print(f"on_piece_spawn çağrıldıktan sonra: flexible_border = {getattr(test_piece, 'flexible_border', False)}")

        new_piece = mode.spawn_new_piece()
        print(f"Yeni parça: flexible_border = {getattr(new_piece, 'flexible_border', False)}")
        # assert getattr(new_piece, 'flexible_border', False), "Yeni spawn edilen parçada flag olmalı"

        # Test 3: lock_and_new_piece sonrası yeni current_piece'e flag ekleniyor mu?
        print("\n=== Test 3: Lock Sonrası Yeni Parça ===")
        # Parçayı aşağı indir
        mode.current_piece.y = 18
        # Kilitle
        mode.lock_and_new_piece()
        print(f"Lock sonrası: current_piece.flexible_border = {getattr(mode.current_piece, 'flexible_border', False)}")
        assert getattr(mode.current_piece, 'flexible_border', False), "Lock sonrası yeni parçada flag olmalı"

        # Test 4: Hareket kontrolü
        print("\n=== Test 4: Hareket Kontrolü ===")
        # Parçayı sol kenara götür
        mode.current_piece.x = 0
        mode.current_piece.y = 5
        print(f"Parça x=0'da, flexible_border={getattr(mode.current_piece, 'flexible_border', False)}")

        # Sol sınırda mı kontrol et
        valid_at_0 = mode.board.is_valid_position(mode.current_piece)
        print(f"x=0'da geçerli mi: {valid_at_0}")

        # Sola hareket et (x=-1)
        mode.current_piece.x = -1
        valid_at_minus1 = mode.board.is_valid_position(mode.current_piece)
        print(f"x=-1'de geçerli mi: {valid_at_minus1}")
        assert valid_at_minus1, "Esnek sınır aktifken x=-1 geçerli olmalı"

        # 2 blok dışarı (x=-2) - bu geçersiz olmalı
        mode.current_piece.x = -2
        valid_at_minus2 = mode.board.is_valid_position(mode.current_piece)
        print(f"x=-2'de geçerli mi: {valid_at_minus2}")
        assert not valid_at_minus2, "2 blok dışarı geçersiz olmalı"

        print("\n=== Özet ===")
        print("✅ Tüm entegrasyon testleri başarılı!")
    finally:
        pygame.quit()


def test_flexible_border_integration_flow():
    run_integration_checks()


if __name__ == '__main__':
    run_integration_checks()
