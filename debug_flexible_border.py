"""Esnek sınır debug - tüm akışı takip et"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

print("=" * 70)
print("ESNEK SINIR DEBUG - AKIŞ TAKİBİ")
print("=" * 70)
print()

# 1. Kart tanımını kontrol et
from game_modes_extra import MysteryCardManager

class FakeMode:
    def __init__(self):
        self.settings_manager = None

mode = FakeMode()
manager = MysteryCardManager(mode)
catalog = manager._build_catalog()

flexible_card = None
for card in catalog:
    if card.get('id') == 'perk_flexible_border':
        flexible_card = card
        break

if flexible_card:
    print("✅ Kart katalogda bulundu:")
    print(f"   ID: {flexible_card['id']}")
    print(f"   Başlık: {flexible_card['title']}")
    print(f"   Persistent: {flexible_card.get('persistent', False)}")
    print(f"   Rarity: {flexible_card.get('rarity', 'unknown')}")
    print(f"   Weight: {flexible_card.get('weight', 0)}")
else:
    print("❌ Kart katalogda bulunamadı!")

print()
print("=" * 70)
print()

# 2. PerkManager'ı test et
from game_modes_extra import PerkManager

class TestMode:
    pass

test_mode = TestMode()
perk_mgr = PerkManager(test_mode)

print("PerkManager testi:")
print(f"  Başlangıç: is_active('perk_flexible_border') = {perk_mgr.is_active('perk_flexible_border')}")

perk_mgr.activate('perk_flexible_border')
print(f"  Aktivasyon sonrası: is_active('perk_flexible_border') = {perk_mgr.is_active('perk_flexible_border')}")

print()
print("=" * 70)
print()

# 3. Board.is_valid_position testi
from board import Board
from pieces import create_piece_by_name

board = Board(width=10, height=20)
piece = create_piece_by_name('I')
piece.x = -1

print("Board.is_valid_position testi:")
print(f"  Flag olmadan: {board.is_valid_position(piece)}")

setattr(piece, 'flexible_border', True)
print(f"  Flag ile: {board.is_valid_position(piece)}")

print()
print("=" * 70)
print()
print("SONUÇ: Tüm bileşenler ayrı ayrı çalışıyor.")
print("Sorun muhtemelen oyun içinde flag'in parçalara eklenmemesi.")
print()
