# -*- coding: utf-8 -*-
import os
import json
import tempfile
import pygame
import pytest

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')

from achievements import AchievementManager, ACHIEVEMENT_REWARDS
from user_manager import UserManager
from store_screen import StoreScreen

# Define a clean mock or temporary user manager configuration
class DummyUserManager:
    def __init__(self, fragments=500):
        self.fragments = fragments
        self.profile = {
            'neural_fragments': fragments,
            'owned_cards': ['clear_rows'],
            'card_tiers': {'clear_rows': 3},  # Tier 3 (Epic)
        }
        self.achievements_unlocked = set()

    def get_current_user(self):
        return 'Arda'

    def get_user_data(self, username=None):
        return self.profile

    def get_fragments(self, username=None):
        return self.fragments

    def add_fragments(self, amount, username=None):
        self.fragments += amount
        self.profile['neural_fragments'] = self.fragments

    def owns_card(self, card_id, username=None):
        return card_id in self.profile['owned_cards']

    def get_card_tier(self, card_id, username=None):
        return self.profile['card_tiers'].get(card_id, 0)

    def is_achievement_unlocked(self, achievement_id, username=None):
        return achievement_id in self.achievements_unlocked

    def upgrade_card(self, card_id, price, max_tier, username=None):
        if card_id == 'clear_rows' and self.profile['card_tiers']['clear_rows'] == 3:
            # upgrading to legendary (4)
            if 'lines_200' not in self.achievements_unlocked:
                return False
        self.profile['card_tiers'][card_id] += 1
        self.fragments -= price
        self.profile['neural_fragments'] = self.fragments
        return True


def test_achievement_rewards_granting():
    """Ödüller artık manuel claim_reward() ile verilir; unlock otomatik vermez."""
    pygame.init()
    try:
        dummy_um = DummyUserManager(fragments=0)
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            tmp_path = tmp.name
        
        try:
            # Create an achievement manager with a fresh json file and user manager
            am = AchievementManager(filename=tmp_path, user_manager=dummy_um)
            
            # Initially, unlocked should be empty, and claimed_rewards should be empty
            assert len(am.unlocked) == 0
            assert len(am.claimed_rewards) == 0
            
            # Unlock first_game (100 Lunar). Unlock NO LONGER auto-grants.
            success = am.unlock('first_game')
            assert success is True
            assert 'first_game' in am.unlocked
            assert 'first_game' not in am.claimed_rewards
            assert dummy_um.fragments == 0
            assert am.is_reward_claimable('first_game') is True
            
            # Manuel talep: bakiye artar, çift talep 0 döner.
            assert am.claim_reward('first_game') == 100
            assert 'first_game' in am.claimed_rewards
            assert dummy_um.fragments == 100
            assert am.claim_reward('first_game') == 0
            assert dummy_um.fragments == 100
            
            # Legendary: lines_200 (1000 Lunar) — yine manuel.
            success = am.unlock('lines_200')
            assert success is True
            assert 'lines_200' in am.unlocked
            assert 'lines_200' not in am.claimed_rewards
            assert dummy_um.fragments == 100
            assert am.claim_reward('lines_200') == 1000
            assert dummy_um.fragments == 1100
            
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
    finally:
        pygame.quit()


def test_retroactive_achievement_claims():
    """Geriye dönük otomatik ödül kaldırıldı: açık ama talep edilmemiş başarımlar
    cüzdana otomatik yazılmaz, yalnızca claim_reward() ile alınır."""
    pygame.init()
    try:
        dummy_um = DummyUserManager(fragments=50)
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            tmp_path = tmp.name
        
        # Write pre-existing achievements file with no claimed_rewards field
        initial_data = {
            'unlocked': {
                'first_game': '2026-06-15 12:00',
                'lines_10': '2026-06-15 12:05'
            },
            'stats': {}
        }
        with open(tmp_path, 'w', encoding='utf-8') as f:
            json.dump(initial_data, f)
            
        try:
            # Önceden açık başarımlar tespit edilir ama otomatik verilmez.
            am = AchievementManager(filename=tmp_path, user_manager=dummy_um)
            
            assert 'first_game' not in am.claimed_rewards
            assert 'lines_10' not in am.claimed_rewards
            assert dummy_um.fragments == 50
            assert am.is_reward_claimable('first_game') is True
            assert am.is_reward_claimable('lines_10') is True
            # Manuel talep edilince eklenir (100 + 150 = 250 -> toplam 300).
            am.claim_reward('first_game')
            am.claim_reward('lines_10')
            assert dummy_um.fragments == 300
            
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
    finally:
        pygame.quit()


def test_legendary_card_upgrade_locked_state():
    """Test that legendary card upgrades are locked if the achievement is not unlocked, and unlock when it is."""
    pygame.init()
    try:
        dummy_um = DummyUserManager(fragments=2000)
        
        # StoreScreen instance
        store = StoreScreen(pygame.Surface((1280, 720), pygame.SRCALPHA), user_manager=dummy_um)
        
        # Find product index for 'clear_rows'
        clear_rows_idx = None
        for i, p in enumerate(store.products):
            if getattr(p, 'card_family', None) == 'clear_rows':
                clear_rows_idx = i
                break
        
        assert clear_rows_idx is not None
        store.selected_index = clear_rows_idx
        product = store.products[clear_rows_idx]
        
        # Case 1: Achievement 'lines_200' not unlocked
        state = store._resolve_ownership_state(product)
        assert state == 'achievement_locked'
        
        # Label should reflect locked status
        lbl = store._ownership_label(product)
        assert "rozet" in lbl or "badge" in lbl.lower()
        
        # Case 2: Unlock achievement 'lines_200'
        dummy_um.achievements_unlocked.add('lines_200')
        state = store._resolve_ownership_state(product)
        assert state == 'upgrade'  # Now it's upgradeable!
        
    finally:
        pygame.quit()
