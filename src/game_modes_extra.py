"""Ekstra oyun modları: Quadrix Extra (tetris2), Kart Ustalığı (mystery), Wide Mode."""

from __future__ import annotations

import math
import os
import sys
import random
from typing import Any, Dict, List

import pygame

try:
    from PIL import Image, ImageSequence
except Exception:
    Image = None  # type: ignore
    ImageSequence = None  # type: ignore

from platform_utils import normalize_mouse_pos, get_mouse_pos, get_display_scale_factor

from asset_manager import load_image
from localization import t, get_language
from gamepad_manager import get_gamepad_manager, is_gamepad_connected
try:
    from .retro_style import retro_style  # type: ignore
except Exception:
    from retro_style import retro_style

try:
    from .ui_theme import UIColors  # type: ignore
except Exception:
    from ui_theme import UIColors

from constants import BLACK, BOARD_WIDTH, BOARD_HEIGHT, FAST_FALL_SPEED, SPEED_INCREASE_PER_LEVEL, SIDE_PANEL_WIDTH, INFO_PANEL_HEIGHT
from block_styles import TextureSlice

# Optional rare-bug tracer (writes JSON dumps when enabled)
try:
    from ghost_bug_tracer import GhostBugTracer
    from data_paths import get_user_data_dir
except Exception:
    GhostBugTracer = None  # type: ignore
    get_user_data_dir = None  # type: ignore


def _get_ui_icon_dir() -> str:
    """PyInstaller uyumlu UI ikon dizini."""
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return os.path.normpath(os.path.join(sys._MEIPASS, 'assets', 'ui'))
    return os.path.normpath(os.path.join(os.path.dirname(__file__), '..', 'assets', 'ui'))


UI_ICON_DIR = _get_ui_icon_dir()


def _get_card_assets_dir() -> str:
    """PyInstaller uyumlu kart PNG dizini (assets/cards)."""
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return os.path.normpath(os.path.join(sys._MEIPASS, 'assets', 'cards'))
    return os.path.normpath(os.path.join(os.path.dirname(__file__), '..', 'assets', 'cards'))


CARD_ASSET_DIR = _get_card_assets_dir()


def _get_card_effects_dir() -> str:
    """PyInstaller uyumlu kart efekt dizini (assets/cards_effect)."""
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return os.path.normpath(os.path.join(sys._MEIPASS, 'assets', 'cards_effect'))
    return os.path.normpath(os.path.join(os.path.dirname(__file__), '..', 'assets', 'cards_effect'))


CARD_EFFECTS_DIR = _get_card_effects_dir()


def _get_animate_effects_dir() -> str:
    """PyInstaller uyumlu animasyon efekt dizini (assets/animate_effect)."""
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return os.path.normpath(os.path.join(sys._MEIPASS, 'assets', 'animate_effect'))
    return os.path.normpath(os.path.join(os.path.dirname(__file__), '..', 'assets', 'animate_effect'))


ANIMATE_EFFECTS_DIR = _get_animate_effects_dir()
SNIPER_EXPLOSION_SPEED_MULTIPLIER = 1.2


def _dt_to_seconds(dt: float) -> float:
    """Milisaniye cinsinden gelen dt'yi saniyeye dönüştürür.

    Oyun döngüsü dt'yi milisaniye olarak geçirir (pygame.Clock.tick).
    Bu yardımcı fonksiyon tutarlı bir şekilde saniyeye çevirir.
    Eğer dt zaten saniye cinsindeyse (< 1.0 gibi küçük değerler), olduğu gibi bırakır.
    """
    s = float(dt)
    # pygame.Clock.tick() tipik olarak 8-33 ms arası döndürür (30-120 FPS).
    # 1.0'dan büyükse milisaniye kabul et.
    if s > 1.0:
        return s / 1000.0
    return s


def get_card_title(card_id: str, fallback: str = "") -> str:
    """Kart başlığını yerelleştirilmiş olarak döndürür."""
    key = f"card_{card_id}_title"
    translated = t(key)
    # t() anahtar bulunamazsa anahtarı döndürür
    return translated if translated != key else fallback


def get_card_description(card_id: str, value: Any = None, fallback: str = "") -> str:
    """Kart açıklamasını yerelleştirilmiş olarak döndürür, {value} placeholder'ını doldurur."""
    key = f"card_{card_id}_desc"
    translated = t(key)
    if translated == key:
        return fallback
    if value is not None and '{value}' in translated:
        return translated.format(value=value)
    return translated


try:
    # When imported as package (e.g. in tests: `import src.game_modes_extra`),
    # use the package-relative Game so monkeypatching `src.game.Game` works.
    from .game import Game  # type: ignore
except Exception:
    # Fallback for running modules as scripts / non-package imports.
    from game import Game
from pieces import Piece, EXTRA_SHAPE_NAMES


def _ui_safe_icon_text(value: object, *, fallback: str = "*") -> str:
    """Return a UI-safe icon string.

    Emoji/symbol glyphs often render as tofu (square boxes) on some Windows setups
    with pygame's default font. For UI labels we keep ASCII-only text.
    """
    if value is None:
        return ""
    text = str(value)
    if not text:
        return ""
    return text if all(ord(ch) < 128 for ch in text) else fallback


def _card_type_label_key(card: Dict[str, Any]) -> str:
    """Kartın davranışına göre doğru tür etiketi anahtarını döndürür.

    Öncelik:
    1) Kalıcı perk
    2) Sınırlı kullanım (hak/süre/timer/charges)
    3) Tek kullanım (anında bir kere etki)
    """
    if bool(card.get('persistent', False)):
        return 'card_type_persistent'

    card_id = str(card.get('id') or '').strip().lower()
    limited_ids = {
        'quantum_tunneling',
        'hammer',
        'bomb_master',
        'rewind_power',
        'perk_phase',
        'sniper_shot',
        'time_capsule',
        'hold_destroyer',
        'hold_destroyer_2',
        'hold_destroyer_3',
        'hold_destroyer_4',
        'hold_destroyer_5',
        'freeze_drop_rare',
        'freeze_drop_epic',
        'freeze_drop_legendary',
    }
    if card_id in limited_ids:
        return 'card_type_limited'

    if bool(card.get('limited', False)) or bool(card.get('timed_buff', False)) or bool(card.get('charges', False)):
        return 'card_type_limited'

    desc = str(card.get('description') or '').lower()
    status = str(card.get('status') or '').lower()
    if ('hak' in desc) or ('hak' in status) or (' sn' in status) or status.endswith('s'):
        return 'card_type_limited'

    if bool(card.get('single_use', False)):
        return 'card_type_single_use'
    return 'card_type_limited'


class Tetris2Mode(Game):
    """Klasik Quadrix'e ekstra parçalar ekleyen mod."""

    def __init__(
        self,
        difficulty: str = "Normal",
        sound_enabled: bool = True,
        effects_enabled: bool = True,
        achievement_manager=None,
        theme_manager=None,
        screen=None,
        fullscreen: bool = False,
        settings_manager=None,
        user_manager=None,
        game_mode: str = "tetris2",
        score_manager=None,
    ) -> None:
        self.extra_piece_count = 0
        # BigSquare (3x3) Quadrix Extra'da havuza dahil edilmez; her 15 parçada 1 gelir.
        self._spawns_since_big_square = 0
        super().__init__(
            difficulty,
            sound_enabled,
            effects_enabled,
            achievement_manager,
            theme_manager,
            screen,
            fullscreen,
            settings_manager,
            user_manager,
            game_mode,
            score_manager=score_manager,
        )
        self.mode_name = "QUADRIX EXTRA"
        self.tetris2_font_large = retro_style.get_font(48, bold=False)
        self.tetris2_font_medium = retro_style.get_font(36, bold=False)
        print("🎮 QUADRIX EXTRA MODE aktif. Ekstra parçalar devrede.")

    def _get_base_piece_factories(self):
        factories = super()._get_base_piece_factories()
        # BigSquare'ı (3x3) normal random havuzundan çıkar.
        # WideMode benzeri şekilde düşük frekansta ayrı olarak spawn edeceğiz.
        factories.extend(
            self._make_named_piece_factory(name)
            for name in EXTRA_SHAPE_NAMES
            if name != 'BigSquare'
        )
        return factories

    def spawn_new_piece(self) -> Piece:
        # BigSquare: her 15 parçada 1 (random havuza dahil değil)
        self._spawns_since_big_square = int(getattr(self, '_spawns_since_big_square', 0) or 0) + 1
        if self._spawns_since_big_square >= 15:
            # Üst üste 3 aynı parça kuralını bozacaksa BigSquare'ı bir sonraki spawna ertele.
            identity = 'name:BigSquare'
            try:
                if hasattr(self, '_would_exceed_max_consecutive') and self._would_exceed_max_consecutive(identity):
                    piece = super().spawn_new_piece()
                else:
                    piece = self._create_named_piece('BigSquare')
                    self._apply_block_style(piece)
                    if hasattr(self, '_note_piece_spawn'):
                        self._note_piece_spawn(identity)
                    self._spawns_since_big_square = 0
            except Exception:
                piece = super().spawn_new_piece()
        else:
            piece = super().spawn_new_piece()

        if getattr(piece, "name", "") in EXTRA_SHAPE_NAMES:
            self.extra_piece_count += 1
            print(f"✨ EXTRA PARÇA #{self.extra_piece_count}: {piece.name}")
        return piece

    def update(self, dt: float) -> None:
        super().update(dt)

    def restart(self):
        """Ensure Tetris2 extra counters are reset when restarting"""
        super().restart()
        self.extra_piece_count = 0
        self._spawns_since_big_square = 0

    def apply_theme_to_pieces(self) -> None:
        # Use the shared theme + block style pipeline for every piece,
        # including EXTRA_SHAPE_NAMES, to keep visuals consistent across modes.
        super().apply_theme_to_pieces()


class MysteryCardManager:
    """Kartların veri ve tetik yönetimini üstlenen bağımsız katman."""

    def __init__(self, mode: "MysteryMode") -> None:
        self.mode = mode
        self.catalog = self._build_catalog()
        self.force_piece_queue: List[str] = []
        self.pending_choices: List[Dict[str, Any]] = []
        self.active_cards: List[Dict] = []
        # Track one-time used card ids to avoid re-offering them
        self.used_card_ids: set[str] = set()
        # Debug cadence: extra selection trigger every 2 cleared lines
        self._debug_lines_progress = 0
        # Align manager threshold with board level-up (5 lines per level)
        self.progress = 0
        self.threshold = 5

    def reset(self) -> None:
        self.force_piece_queue.clear()
        self.pending_choices.clear()
        self.active_cards.clear()
        self.used_card_ids.clear()
        self._debug_lines_progress = 0
        self.progress = 0
        self.threshold = 5

    def notify_lines_cleared(self, cleared: int) -> bool:
        """Satır ilerlemesini günceller, gerekirse yeni kart seçimini hazırlar."""
        if cleared <= 0:
            return False
        # NOTE: Keep the main system intact (threshold=5 aligned to level-up).
        # When card_mode_debug is enabled, we ADD an extra trigger every 2 cleared lines
        # without modifying progress/threshold behavior.
        card_mode_debug = False
        try:
            card_mode_debug = bool(self.mode.settings_manager.get('card_mode_debug', False))
        except Exception:
            card_mode_debug = False

        if card_mode_debug:
            try:
                self._debug_lines_progress = int(getattr(self, '_debug_lines_progress', 0) or 0) + int(cleared)
            except Exception:
                self._debug_lines_progress = (getattr(self, '_debug_lines_progress', 0) or 0) + cleared
            debug_triggers = 0
            while self._debug_lines_progress >= 2:
                self._debug_lines_progress -= 2
                debug_triggers += 1
            if debug_triggers > 0:
                try:
                    if getattr(self, 'mode', None) is not None:
                        self.mode.pending_level_ups = getattr(self.mode, 'pending_level_ups', 0) + int(debug_triggers)
                except Exception:
                    pass

        self.progress += cleared
        triggered = False
        while self.progress >= self.threshold:
            self.progress -= self.threshold
            triggered = True
        # DO NOT prepare the selection here; preparation and overlay opening
        # must be driven by the higher-level MysteryMode on level-up so the
        # UI and internal logic stay synchronized. Return whether the threshold
        # was exceeded so the caller may take additional actions if needed.
        if triggered:
            # Debug notice and enqueue a pending level-up on the mode so the overlay
            # will be opened either immediately or on the next update check.
            try:
                print(f"[MysteryCardManager] Threshold reached: progress={self.progress}, threshold={self.threshold}")
            except Exception:
                pass
            try:
                # Always prepare a selection now so tests and callers using the manager
                # directly get a populated pending_choices when threshold triggers.
                try:
                    self.prepare_selection()
                except Exception:
                    pass
                if getattr(self, 'mode', None) is not None:
                    mode = self.mode
                    # Deduplicate using last_enqueued_level: enqueue for every level above it
                    current_level = getattr(mode.board, 'level', 0)
                    last = getattr(mode, 'last_enqueued_level', 0)
                    if current_level > last:
                        delta = int(current_level - last)
                        mode.pending_level_ups = getattr(mode, 'pending_level_ups', 0) + delta
                        mode.last_enqueued_level = current_level
            except Exception:
                pass
        return triggered

    def prepare_selection(self) -> List[Dict[str, Any]]:
        # Build a filtered pool excluding persistent perks that are already active
        self.pending_choices = []
        # If card mode debug setting is enabled, show the full catalog for debugging
        card_mode_debug = False
        try:
            card_mode_debug = bool(self.mode.settings_manager.get('card_mode_debug', False))
        except Exception:
            card_mode_debug = False
        if card_mode_debug:
            available = list(self.catalog)
            pool_size = len(available)
        else:
            # Exclude persistent perks already active and single-use cards already used
            # Also exclude cards in the same group (e.g., hold_destroyer variants)
            def _is_used(c):
                cid = c.get("id", "")
                group = c.get("_group_id", cid)
                if (c.get("single_use") or c.get("persistent")) and (cid in self.used_card_ids or group in self.used_card_ids):
                    return True
                return False

            available = [
                c for c in self.catalog
                if not (c.get("persistent") and any(ac.get("id") == c.get("id") for ac in self.active_cards))
                and not _is_used(c)
            ]
            # If for whatever reason the filter removes all cards (e.g., all single-use are used),
            # fall back to the full catalog so the player still receives card choices on level-up.
            if not available:
                available = list(self.catalog)
            pool_size = min(3, len(available))
        # Ensure we always present at least one card by falling back to full catalog
        if not available:
            available = list(self.catalog)
        if not available:
            # Give up and return empty pending choices
            self.pending_choices = []
            return self.pending_choices
        
        # === AĞIRLIKLI SEÇİM SİSTEMİ ===
        # Her kartın weight değerine göre seçim yap
        selected_cards = self._weighted_sample(available, pool_size)
        
        for card in selected_cards:
            value = self._roll_value(card)
            rarity = card.get("rarity", "common")
            self.pending_choices.append(
                {
                    "id": card["id"],
                    "title": card["title"],
                    "value": value,
                    "description": card["description"].format(value=value, freeze_duration=card.get("freeze_duration", "")),
                    "color": card["color"],
                    "bg": card.get("bg", (34, 34, 46)),
                    "icon": card.get("icon", "*"),
                    "tag": card.get("tag", "Bonus"),
                    "style": card.get("style", {}),
                    "icon_image": card.get("icon_image"),
                    "persistent": card.get("persistent", False),
                    "payload": card.get("payload", {}),
                    "rarity": rarity,
                    "single_use": card.get("single_use", False),
                    "_group_id": card.get("_group_id"),
                }
            )
        return self.pending_choices
    
    def _weighted_sample(self, cards: List[Dict], count: int) -> List[Dict]:
        """Ağırlıklı rastgele kart seçimi - nadir kartlar daha az çıkar"""
        if not cards:
            return []
        
        # Her kart için ağırlık hesapla
        weights = []
        for card in cards:
            weight = card.get("weight", 50)  # Varsayılan ağırlık: 50
            weights.append(weight)
        
        # Normalize weights
        total_weight = sum(weights)
        if total_weight == 0:
            return random.sample(cards, min(count, len(cards)))
        
        # Ağırlıklı seçim
        selected = []
        available_cards = list(cards)
        available_weights = list(weights)
        
        for _ in range(min(count, len(cards))):
            if not available_cards:
                break
            
            # Ağırlıklı rastgele seçim
            total = sum(available_weights)
            if total <= 0:
                break
            
            r = random.uniform(0, total)
            cumulative = 0
            selected_idx = 0
            
            for i, w in enumerate(available_weights):
                cumulative += w
                if r <= cumulative:
                    selected_idx = i
                    break
            
            selected.append(available_cards[selected_idx])
            # Remove selected card and any cards in the same group
            removed_group = available_cards[selected_idx].get('_group_id')
            if removed_group:
                # Remove all cards with the same _group_id
                indices_to_remove = [i for i, c in enumerate(available_cards) if c.get('_group_id') == removed_group]
                for i in reversed(indices_to_remove):
                    available_cards.pop(i)
                    available_weights.pop(i)
            else:
                available_cards.pop(selected_idx)
                available_weights.pop(selected_idx)
        
        return selected

    def _roll_value(self, card: Dict[str, Any]) -> int:
        if "value_range" in card:
            low, high = card["value_range"]
            return random.randint(low, high)
        return int(card.get("base", 1))

    def select_card(self, index: int) -> Dict | None:
        if not (0 <= index < len(self.pending_choices)):
            return None
        card = dict(self.pending_choices[index])
        self.pending_choices = []
        # Mark single-use and persistent cards as used so they won't be shown again
        if card.get('single_use') or card.get('persistent'):
            self.used_card_ids.add(card.get('id'))
            # Also mark group_id so all variants are excluded
            group = card.get('_group_id')
            if group:
                self.used_card_ids.add(group)
        return card

    def pop_forced_piece(self) -> str | None:
        if self.force_piece_queue:
            return self.force_piece_queue.pop(0)
        return None

    def queue_force_piece(self, name: str) -> None:
        self.force_piece_queue.append(name)

    def get_status(self) -> Dict[str, Any]:
        return {
            "progress": self.progress,
            "threshold": self.threshold,
            "hint": t('card_hint_equal'),
        }

    def get_selection_hint(self) -> str:
        return t('card_hint_random')

    def _build_catalog(self) -> List[Dict]:
        # === NADİRLİK SİSTEMİ (Güncellenmiş) ===
        # common=50-60    -> Basit, anında etkili, sık çıkan
        # uncommon=40-50  -> Orta güçte, koşullu etkili
        # rare=25-35      -> Güçlü, stratejik önemli
        # epic=12-20      -> Çok güçlü, oyun değiştirici
        # legendary=5-10  -> En güçlü, nadiren çıkar
        # 
        # === KART TÜRLERİ ===
        # single_use=True  -> Anında etki, bir kez kullanılır
        # charges=True     -> Belirli sayıda hak (tuş ile kullanım)
        # timed_buff=True  -> Süreli etki (timer ile biter)
        # persistent=True  -> Oyun boyunca kalıcı perk

        cards = [
            # ==================== COMMON KARTLAR (Ağırlık: 50-60) ====================
            # Basit, anında etkili, sık çıkan kartlar
            {
                "id": "clear_rows",
                "title": "Alt Süpür",
                "base": 2,
                "value_range": (1, 3),
                "description": "En alttaki {value} satırı temizler. Bloklar aşağı oturur.",
                "color": (120, 230, 255),
                "bg": (12, 26, 58),
                "icon": "🧹",
                "tag": "Uncommon",
                "rarity": "uncommon",
                "weight": 60,
                "icon_image": os.path.join(UI_ICON_DIR, "icon_clean_sweep.png"),
                "style": {
                    "gradient": [(32, 90, 140), (10, 24, 38)],
                    "border": (170, 235, 255),
                    "corner": 24,
                    "pattern": "wave",
                    "icon_bg": (28, 72, 120),
                },
                "single_use": True,
            },
            {
                "id": "block_magnet",
                "title": "Blok Manyetiği",
                "base": 1,
                "value_range": (1, 1),
                "description": "Tüm boşluklar kapanır! Bloklar birbirine yapışır ve boşluklar yok olur.",
                "color": (255, 140, 100),
                "bg": (48, 20, 12),
                "icon": "M",
                "tag": "Epic",
                "rarity": "legendary",
                "weight": 12,
                "icon_image": os.path.join(UI_ICON_DIR, "icon_block_magnet.png"),
                "style": {
                    "gradient": [(255, 120, 80), (100, 30, 20)],
                    "border": (255, 170, 130),
                    "corner": 20,
                    "pattern": "wave",
                    "icon_bg": (120, 40, 25),
                },
                "single_use": True,
            },
            {
                "id": "peak_sculpt",
                "title": "Tepe Kesici",
                "base": 3,
                "value_range": (2, 4),
                "description": "En yüksek {value} bloğu keser, tahtayı düzleştirir.",
                "color": (140, 255, 210),
                "bg": (12, 36, 28),
                "icon": "✂️",
                "tag": "Uncommon",
                "rarity": "uncommon",
                "weight": 55,
                "icon_image": os.path.join(UI_ICON_DIR, "icon_peak_cutter.png"),
                "single_use": True,
                "style": {
                    "gradient": [(0, 255, 255), (41, 121, 255)],
                    "border": (150, 255, 255),
                    "corner": 22,
                    "pattern": "laser",
                    "icon_bg": (10, 60, 80),
                },
            },
            {
                "id": "nova_burst",
                "title": "Nova Patlaması",
                "base": 3,
                "value_range": (2, 4),
                "description": "Sonraki {value} kilitte merkezde 3x3 alan patlar.",
                "color": (255, 120, 196),
                "bg": (46, 10, 30),
                "icon": "💥",
                "tag": "Epic",
                "rarity": "epic",
                "weight": 18,
                "icon_image": os.path.join(UI_ICON_DIR, "icon_nova_burst.png"),
                "style": {
                    "gradient": [(140, 12, 60), (44, 10, 28)],
                    "border": (255, 170, 220),
                    "corner": 30,
                    "pattern": "spark",
                    "icon_bg": (80, 16, 38),
                },
                "single_use": True,
            },
            {
                "id": "mini_bomb",
                "title": "Mini Bomba",
                "base": 1,
                "value_range": (1, 1),
                "description": "Mevcut parça kilitlenince kendi hücreleri + temas ettiği komşu blokları patlatır.",
                "color": (255, 110, 80),
                "bg": (50, 12, 10),
                "icon": "B",
                "tag": "Common",
                "rarity": "common",
                "weight": 40,
                "icon_image": os.path.join(UI_ICON_DIR, "icon_mini_bomb.png"),
                "style": {"border": (255, 170, 120)},
                "single_use": True,
            },
            # ==================== HIZ PATLAMASI (Enderlik Sistemi) ====================
            {
                "id": "speed_burst_rare",
                "_group_id": "speed_burst",
                "title": "Hız Patlaması",
                "base": 20,
                "value_range": (18, 22),
                "description": "{value} saniye boyunca %25 hızlı düşüş + temizlenen her satır için 1.3x puan!",
                "color": (255, 200, 80),
                "bg": (50, 38, 12),
                "icon": "⚡",
                "tag": "Rare",
                "rarity": "rare",
                "weight": 35,
                "icon_image": os.path.join(UI_ICON_DIR, "icon_speed_burst.png"),
                "style": {
                    "gradient": [(255, 210, 100), (190, 120, 30)],
                    "border": (255, 220, 120),
                    "corner": 22,
                    "pattern": "spark",
                    "icon_bg": (200, 150, 50),
                },
                "timed_buff": True,
                "payload": {"speed_multiplier": 1.25, "line_multiplier": 1.3},
            },
            {
                "id": "speed_burst_epic",
                "_group_id": "speed_burst",
                "title": "Hız Patlaması",
                "base": 30,
                "value_range": (25, 35),
                "description": "{value} saniye boyunca %40 hızlı düşüş + temizlenen her satır için 1.5x puan!",
                "color": (255, 180, 50),
                "bg": (50, 35, 10),
                "icon": "⚡",
                "tag": "Epic",
                "rarity": "epic",
                "weight": 20,
                "icon_image": os.path.join(UI_ICON_DIR, "icon_speed_burst.png"),
                "style": {
                    "gradient": [(255, 190, 60), (170, 90, 15)],
                    "border": (255, 200, 100),
                    "corner": 24,
                    "pattern": "spark",
                    "icon_bg": (190, 130, 35),
                },
                "timed_buff": True,
                "payload": {"speed_multiplier": 1.4, "line_multiplier": 1.5},
            },
            {
                "id": "speed_burst_legendary",
                "_group_id": "speed_burst",
                "title": "Hız Patlaması",
                "base": 40,
                "value_range": (35, 45),
                "description": "{value} saniye boyunca %60 hızlı düşüş + temizlenen her satır için 1.75x puan!",
                "color": (255, 160, 30),
                "bg": (48, 30, 8),
                "icon": "⚡",
                "tag": "Legendary",
                "rarity": "legendary",
                "weight": 8,
                "icon_image": os.path.join(UI_ICON_DIR, "icon_speed_burst.png"),
                "style": {
                    "gradient": [(255, 170, 40), (160, 80, 10)],
                    "border": (255, 190, 80),
                    "corner": 26,
                    "pattern": "spark",
                    "icon_bg": (180, 120, 25),
                },
                "timed_buff": True,
                "payload": {"speed_multiplier": 1.6, "line_multiplier": 1.75},
            },
            {
                "id": "quantum_tunneling",
                "title": "Hayalet Parça",
                "base": 3,
                "value_range": (3, 3),
                "description": "3 hak: G ile istediğin parçayı hayalet yap; blokların içinden geçer.",
                "color": (180, 200, 255),
                "bg": (14, 14, 30),
                "icon": "👻",
                "tag": "Epic",
                "rarity": "epic",
                "weight": 25,
                "icon_image": os.path.join(UI_ICON_DIR, "icon_quantum_tunnel.png"),
                "style": {"border": (160, 180, 255)},
                "limited": True,
                "single_use": True,
            },
            {
                "id": "hammer",
                "title": "Zip Dosyası",
                "base": 3,
                "value_range": (3, 3),
                "description": "3 hak: H ile mevcut düşen parçayı anlık 1x1 bloğa dönüştür.",
                "color": (230, 210, 140),
                "bg": (32, 22, 12),
                "icon": "H",
                "tag": "Rare",
                "rarity": "rare",
                "weight": 35,
                "icon_image": os.path.join(UI_ICON_DIR, "icon_hammer.png"),
                "style": {"border": (255, 236, 190)},
                "limited": True,
                "single_use": True,
            },
            # ==================== PERKLER (Kalıcı yetenekler) ====================
            {
                "id": "bomb_master",
                "title": "Bomba Ustası",
                "base": 3,
                "value_range": (3, 3),
                "description": "3 hak: M tuşuyla mevcut parçayı mini bomba yap. Kilitlenince temas ettiği blokları patlatır.",
                "color": (255, 90, 60),
                "bg": (50, 12, 10),
                "icon": "💣",
                "tag": "Rare",
                "rarity": "rare",
                "weight": 30,
                "limited": True,
                "single_use": True,
                "style": {"border": (255, 120, 80)},
                "icon_image": os.path.join(UI_ICON_DIR, "icon_perk_explosive.png"),
            },
            {
                "id": "rewind_power",
                "title": "Geri Sarma",
                "base": 3,
                "value_range": (3, 3),
                "description": "3 hak: U tuşuyla son parçayı geri sar.",
                "color": (255, 200, 255),
                "bg": (38, 12, 38),
                "icon": "RW",
                "tag": "Rare",
                "rarity": "rare",
                "weight": 18,
                "limited": True,
                "style": {"border": (255, 150, 255)},
                "icon_image": os.path.join(UI_ICON_DIR, "icon_perk_rewind.png"),
            },
            {
                "id": "perk_phase",
                "title": "Şekil Değiştirici",
                "base": 3,
                "value_range": (3, 3),
                "description": "3 hak: LSHIFT ile parçayı karşıtına dönüştür (L↔J, Z↔S).",
                "color": (255, 200, 255),
                "bg": (24, 12, 34),
                "icon": "🔄",
                "tag": "Epic",
                "rarity": "epic",
                "weight": 18,
                "limited": True,
                "style": {"border": (220, 140, 255)},
                "icon_image": os.path.join(UI_ICON_DIR, "icon_perk_phase.png"),
            },
            {
                "id": "perk_synergy",
                "title": "Sinerji Bonus",
                "base": 1,
                "value_range": (1, 1),
                "description": "PERK: Her aktif kart için +%10 skor bonusu.",
                "color": (255, 220, 140),
                "bg": (32, 18, 12),
                "icon": "🔗",
                "tag": "Rare",
                "rarity": "rare",
                "weight": 25,
                "persistent": True,
                "style": {"border": (255, 200, 120)},
                "icon_image": os.path.join(UI_ICON_DIR, "icon_perk_synergy.png"),
            },
            {
                "id": "perk_second_pocket",
                "title": "Ekstra Cep",
                "base": 1,
                "value_range": (1, 1),
                "description": "PERK: V tuşuyla ikinci bir parça saklayabilirsin.",
                "color": (200, 200, 255),
                "bg": (18, 18, 40),
                "icon": "🎒",
                "tag": "Legendary",
                "rarity": "legendary",
                "weight": 18,
                "persistent": True,
                "style": {"border": (180, 180, 255)},
                "icon_image": os.path.join(UI_ICON_DIR, "icon_perk_second_pocket.png"),
            },
            {
                "id": "perk_flexible_border",
                "title": "Esnek Sınır",
                "base": 1,
                "value_range": (1, 1),
                "description": "PERK: Parçalar tahtanın kenarlarından 1 blok dışına çıkabilir.",
                "color": (255, 200, 100),
                "bg": (50, 30, 8),
                "icon": "⬌",
                "tag": "Legendary",
                "rarity": "legendary",
                "weight": 8,
                "persistent": True,
                "style": {
                    "gradient": [(255, 190, 60), (120, 60, 10)],
                    "border": (255, 220, 120),
                    "corner": 28,
                    "pattern": "spark",
                    "icon_bg": (140, 80, 20),
                },
                "icon_image": os.path.join(UI_ICON_DIR, "icon_perk_flexible_border.png"),
            },
            {
                "id": "gravity_well",
                "title": "Yerçekimi Dalgası",
                "base": 1,
                "value_range": (1, 1),
                "description": "Bloklar aşağı çöker, oluşan tüm dolu satırlar temizlenir.",
                "color": (120, 160, 255),
                "bg": (8, 12, 32),
                "icon": "🌀",
                "tag": "Epic",
                "rarity": "epic",
                "weight": 18,
                "icon_image": os.path.join(UI_ICON_DIR, "icon_gravity_well.png"),
                "style": {"border": (140, 180, 255)},
                "single_use": True,
            },
            {
                "id": "ghost_echo",
                "title": "İkinci Şans",
                "base": 6,
                "value_range": (6, 6),
                "description": "Ölümden Dönüş: Oyun bitecekken üst yarıyı temizler, devam edersin.",
                "color": (200, 200, 255),
                "bg": (10, 8, 30),
                "icon": "👻",
                "tag": "Legendary",
                "rarity": "legendary",
                "weight": 12,
                "icon_image": os.path.join(UI_ICON_DIR, "icon_ghost_echo.png"),
                "single_use": True,
                "style": {"border": (220, 220, 255)},
            },
            # ==================== YARDIMCI KARTLAR ====================
            {
                "id": "row_shuffle",
                "title": "Blok Karıştırıcı",
                "base": 3,
                "value_range": (2, 4),
                "description": "Alt {value} satırdaki blokları karıştırır, şansını dene!",
                "color": (120, 200, 255),
                "bg": (10, 24, 46),
                "icon": "🎲",
                "tag": "Common",
                "rarity": "common",
                "weight": 55,
                "icon_image": os.path.join(UI_ICON_DIR, "icon_row_shuffle.png"),
                "style": {
                    "gradient": [(80, 170, 240), (18, 44, 88)],
                    "border": (170, 210, 240),
                    "corner": 22,
                    "pattern": "wave",
                    "icon_bg": (26, 74, 128),
                },
                "single_use": True,
            },
            {
                "id": "laser_drill",
                "title": "Delici Parça",
                "base": 1,
                "value_range": (1, 1),
                "description": "Mevcut parça düşerken önündeki blokları eritir.",
                "color": (255, 50, 150),
                "bg": (40, 5, 25),
                "icon": "🔥",
                "tag": "Rare",
                "rarity": "rare",
                "weight": 25,
                "icon_image": os.path.join(UI_ICON_DIR, "icon_laser_drill.png"),
                "style": {
                    "gradient": [(255, 30, 120), (100, 10, 50)],
                    "border": (255, 100, 180),
                    "corner": 24,
                    "pattern": "laser",
                    "icon_bg": (150, 20, 80),
                },
                "single_use": True,
            },
            {
                "id": "sniper_shot",
                "title": "Keskin Nişancı",
                "base": 3,  # 3 hak ver
                "value_range": (3, 3),  # Sabit 3 hak
                "description": "3 hak: Tahtada istediğin bir bloğu tıklayarak patlat.",
                "color": (255, 80, 80),
                "bg": (50, 10, 10),
                "icon": "N",
                "tag": "Uncommon",
                "rarity": "uncommon",
                "weight": 35,
                "icon_image": os.path.join(UI_ICON_DIR, "icon_sniper_shot.png"),
                "style": {
                    "gradient": [(180, 30, 30), (60, 10, 10)],
                    "border": (255, 100, 100),
                    "corner": 22,
                    "pattern": "spark",
                    "icon_bg": (120, 20, 20),
                },
                "limited": True,
                "single_use": True,
            },
            {
                "id": "time_capsule",
                "title": "Zaman Kapsülü",
                "base": 1,
                "value_range": (1, 1),
                "description": "R ile zaman kapsülünü kullan: ilk basışta kaydet, ikinci basışta geri dön.",
                "color": (120, 255, 200),
                "bg": (10, 40, 30),
                "icon": "T",
                "tag": "Legendary",
                "rarity": "legendary",
                "weight": 8,
                "icon_image": os.path.join(UI_ICON_DIR, "icon_time_capsule.png"),
                "style": {
                    "gradient": [(80, 200, 160), (20, 60, 50)],
                    "border": (150, 255, 220),
                    "corner": 28,
                    "pattern": "wave",
                    "icon_bg": (40, 120, 90),
                },
                "limited": True,
                "single_use": True,
            },
            {
                "id": "future_changer",
                "title": "Geleceği Değiştiren",
                "base": 2,
                "value_range": (2, 2),
                "description": "Sonraki 2 parçayı kendin seç! Bir popup açılır ve istediğin parçaları seçersin.",
                "color": (180, 100, 255),
                "bg": (30, 15, 50),
                "icon": "F",
                "tag": "Epic",
                "rarity": "epic",
                "weight": 15,
                "icon_image": os.path.join(UI_ICON_DIR, "icon_future_changer.png"),
                "style": {
                    "gradient": [(140, 60, 200), (40, 20, 80)],
                    "border": (200, 140, 255),
                    "corner": 24,
                    "pattern": "spark",
                    "icon_bg": (80, 40, 120),
                },
                "single_use": True,
            },
            # ==================== YENİ KARTLAR ====================
            {
                "id": "block_workshop_card",
                "title": "Blok Atölyesi",
                "base": 1,
                "value_range": (1, 1),
                "description": "Popup bir atölye açılır ve tek seferlik maks 7 blokluk özel parça oluşturursun!",
                "color": (255, 200, 100),
                "bg": (50, 35, 10),
                "icon": "W",
                "tag": "Legendary",
                "rarity": "legendary",
                "weight": 8,
                "icon_image": os.path.join(UI_ICON_DIR, "icon_block_workshop.png"),
                "style": {
                    "gradient": [(255, 180, 60), (120, 60, 10)],
                    "border": (255, 220, 120),
                    "corner": 28,
                    "pattern": "spark",
                    "icon_bg": (140, 80, 20),
                },
                "single_use": True,
            },
            {
                "id": "gambler_dice",
                "title": "Kumarbazın Zarı",
                "base": 1,
                "value_range": (1, 1),
                "description": "Zar at! %50 şansla tüm tahta temizlenir ya da tahtanın yarısı rastgele blokla dolar.",
                "color": (255, 50, 50),
                "bg": (50, 5, 5),
                "icon": "D",
                "tag": "Legendary",
                "rarity": "legendary",
                "weight": 8,
                "icon_image": os.path.join(UI_ICON_DIR, "icon_gambler_dice.png"),
                "style": {
                    "gradient": [(220, 30, 30), (80, 10, 10)],
                    "border": (255, 80, 80),
                    "corner": 26,
                    "pattern": "spark",
                    "icon_bg": (130, 20, 20),
                },
                "single_use": True,
            },
            {
                "id": "color_cleanse",
                "title": "Renk Temizleme",
                "base": 1,
                "value_range": (1, 1),
                "description": "Rastgele bir renkteki tüm blokları temizler. Üstteki bloklar aşağıya düşer.",
                "color": (100, 255, 200),
                "bg": (10, 40, 30),
                "icon": "C",
                "tag": "Epic",
                "rarity": "epic",
                "weight": 18,
                "icon_image": os.path.join(UI_ICON_DIR, "icon_color_fix.png"),
                "style": {
                    "gradient": [(60, 220, 160), (15, 60, 45)],
                    "border": (120, 255, 210),
                    "corner": 24,
                    "pattern": "wave",
                    "icon_bg": (30, 110, 80),
                },
                "single_use": True,
            },
            {
                "id": "hold_destroyer",
                "_group_id": "hold_destroyer",
                "title": "Tuttuğunu Koparan",
                "base": 1,
                "value_range": (1, 1),
                "description": "{value} hak: Saklanan parçayı silme gücü! B tuşuyla kullan.",
                "color": (200, 200, 210),
                "bg": (30, 30, 35),
                "icon": "X",
                "tag": "Common",
                "rarity": "common",
                "weight": 55,
                "icon_image": os.path.join(UI_ICON_DIR, "icon_hold_destroyer.png"),
                "style": {
                    "gradient": [(180, 180, 195), (60, 60, 70)],
                    "border": (210, 210, 220),
                    "corner": 22,
                    "pattern": "wave",
                    "icon_bg": (90, 90, 100),
                },
                "limited": True,
                "single_use": True,
            },
            {
                "id": "hold_destroyer_2",
                "_group_id": "hold_destroyer",
                "title": "Tuttuğunu Koparan",
                "base": 2,
                "value_range": (2, 2),
                "description": "{value} hak: Saklanan parçayı silme gücü! B tuşuyla kullan.",
                "color": (100, 230, 150),
                "bg": (12, 36, 22),
                "icon": "X",
                "tag": "Uncommon",
                "rarity": "uncommon",
                "weight": 45,
                "icon_image": os.path.join(UI_ICON_DIR, "icon_hold_destroyer.png"),
                "style": {
                    "gradient": [(80, 200, 130), (20, 60, 40)],
                    "border": (130, 255, 180),
                    "corner": 22,
                    "pattern": "wave",
                    "icon_bg": (40, 100, 60),
                },
                "limited": True,
                "single_use": True,
            },
            {
                "id": "hold_destroyer_3",
                "_group_id": "hold_destroyer",
                "title": "Tuttuğunu Koparan",
                "base": 3,
                "value_range": (3, 3),
                "description": "{value} hak: Saklanan parçayı silme gücü! B tuşuyla kullan.",
                "color": (80, 170, 255),
                "bg": (10, 20, 40),
                "icon": "X",
                "tag": "Rare",
                "rarity": "rare",
                "weight": 30,
                "icon_image": os.path.join(UI_ICON_DIR, "icon_hold_destroyer.png"),
                "style": {
                    "gradient": [(60, 140, 220), (15, 40, 90)],
                    "border": (120, 200, 255),
                    "corner": 24,
                    "pattern": "wave",
                    "icon_bg": (30, 70, 130),
                },
                "limited": True,
                "single_use": True,
            },
            {
                "id": "hold_destroyer_4",
                "_group_id": "hold_destroyer",
                "title": "Tuttuğunu Koparan",
                "base": 4,
                "value_range": (4, 4),
                "description": "{value} hak: Saklanan parçayı silme gücü! B tuşuyla kullan.",
                "color": (200, 100, 255),
                "bg": (30, 12, 50),
                "icon": "X",
                "tag": "Epic",
                "rarity": "epic",
                "weight": 18,
                "icon_image": os.path.join(UI_ICON_DIR, "icon_hold_destroyer.png"),
                "style": {
                    "gradient": [(170, 70, 220), (50, 20, 80)],
                    "border": (220, 140, 255),
                    "corner": 26,
                    "pattern": "spark",
                    "icon_bg": (90, 35, 130),
                },
                "limited": True,
                "single_use": True,
            },
            {
                "id": "hold_destroyer_5",
                "_group_id": "hold_destroyer",
                "title": "Tuttuğunu Koparan",
                "base": 5,
                "value_range": (5, 5),
                "description": "{value} hak: Saklanan parçayı silme gücü! B tuşuyla kullan.",
                "color": (255, 200, 60),
                "bg": (50, 35, 8),
                "icon": "X",
                "tag": "Legendary",
                "rarity": "legendary",
                "weight": 8,
                "icon_image": os.path.join(UI_ICON_DIR, "icon_hold_destroyer.png"),
                "style": {
                    "gradient": [(255, 180, 40), (120, 70, 10)],
                    "border": (255, 220, 100),
                    "corner": 28,
                    "pattern": "spark",
                    "icon_bg": (140, 90, 20),
                },
                "limited": True,
                "single_use": True,
            },
            # ==================== SON DÜŞÜŞ (Blok Dondurma) ====================
            {
                "id": "freeze_drop_rare",
                "_group_id": "freeze_drop",
                "title": "Son Düşüş",
                "base": 3,
                "value_range": (3, 3),
                "description": "3 hak: F ile bloğu {freeze_duration}sn dondur! Sadece sağ-sol ve sert düşüş çalışır.",
                "color": (140, 220, 255),
                "bg": (10, 24, 50),
                "icon": "❄️",
                "tag": "Rare",
                "rarity": "rare",
                "weight": 30,
                "freeze_duration": 6,
                "icon_image": os.path.join(UI_ICON_DIR, "icon_freeze_drop.png"),
                "style": {
                    "gradient": [(100, 200, 255), (20, 60, 120)],
                    "border": (160, 230, 255),
                    "corner": 24,
                    "pattern": "wave",
                    "icon_bg": (30, 80, 140),
                },
                "limited": True,
                "single_use": True,
            },
            {
                "id": "freeze_drop_epic",
                "_group_id": "freeze_drop",
                "title": "Son Düşüş",
                "base": 3,
                "value_range": (3, 3),
                "description": "3 hak: F ile bloğu {freeze_duration}sn dondur! Sadece sağ-sol ve sert düşüş çalışır.",
                "color": (100, 180, 255),
                "bg": (8, 18, 44),
                "icon": "❄️",
                "tag": "Epic",
                "rarity": "epic",
                "weight": 18,
                "freeze_duration": 10,
                "icon_image": os.path.join(UI_ICON_DIR, "icon_freeze_drop.png"),
                "style": {
                    "gradient": [(70, 160, 240), (15, 40, 100)],
                    "border": (130, 200, 255),
                    "corner": 26,
                    "pattern": "wave",
                    "icon_bg": (25, 60, 120),
                },
                "limited": True,
                "single_use": True,
            },
            {
                "id": "freeze_drop_legendary",
                "_group_id": "freeze_drop",
                "title": "Son Düşüş",
                "base": 3,
                "value_range": (3, 3),
                "description": "3 hak: F ile bloğu {freeze_duration}sn dondur! Sadece sağ-sol ve sert düşüş çalışır.",
                "color": (60, 150, 255),
                "bg": (5, 12, 38),
                "icon": "❄️",
                "tag": "Legendary",
                "rarity": "legendary",
                "weight": 8,
                "freeze_duration": 15,
                "icon_image": os.path.join(UI_ICON_DIR, "icon_freeze_drop.png"),
                "style": {
                    "gradient": [(40, 120, 220), (10, 30, 80)],
                    "border": (100, 180, 255),
                    "corner": 28,
                    "pattern": "spark",
                    "icon_bg": (20, 50, 100),
                },
                "limited": True,
                "single_use": True,
            },
        ]
        return cards


class MysteryCardUI:
    """Kart seçimi ekranının çizim ve etkileşimlerinden sorumlu arayüz."""

    def __init__(self) -> None:
        self.fade_alpha = 0.0
        self.card_rects: List[pygame.Rect] = []
        self.hover_index = -1
        self.pulse_time = 0.0
        self.pause_scroll_offset = 0
        self.selection_flash = 0.0
        self.selection_flash_duration = 0.22
        self.selection_index = -1
        self.interaction_locked = False
        self.icon_cache: Dict[str, pygame.Surface] = {}
        # Grid debug scroll state (pixels)
        self.randomize_pill_rect = None
        self.grid_scroll = 0
        self.grid_max_scroll = 0
        self._mouse_is_pressed = False
        # Widget list of UICard instances used to render the cards
        self.card_widgets: List['UICard'] = []
        self.skip_button_rect: pygame.Rect | None = None
        self.reroll_button_rect: pygame.Rect | None = None
        # Göz atma (peek) butonu - oyun alanını görmek için
        self.peek_button_rect: pygame.Rect | None = None
        self.peek_mode_active = False  # True olunca kart seçimi gizlenip oyun alanı gösterilir
        self._reveal_sfx_callback = None
        self._overlay_base_size: tuple[int, int] | None = None
        # Kart seçim ekranı için okunabilirlik tabanlı minimum referans boyut
        # (pencere bu boyutlara yakınken kartlar hala rahat okunur kalır)
        self._overlay_readable_min_size: tuple[int, int] = (1180, 760)

    def reset(self) -> None:
        self.card_rects = []
        self.hover_index = -1
        self.fade_alpha = 0.0
        self.pulse_time = 0.0
        self.clear_selection_feedback()
        self.randomize_pill_rect = None
        self.card_widgets = []
        self.skip_button_rect = None
        self.reroll_button_rect = None
        self.peek_button_rect = None
        self.peek_mode_active = False

    def set_reveal_sfx_callback(self, callback) -> None:
        self._reveal_sfx_callback = callback

    def set_overlay_reference_size(self, width: int, height: int) -> None:
        """Kart seçim overlay'i için fullscreen referans boyutunu ayarla."""
        w = max(1, int(width))
        h = max(1, int(height))
        self._overlay_base_size = (w, h)

    def update(self, dt: float, overlay_active: bool) -> None:
        # dt gelebilir: ms (oyun döngüsünden) veya saniye. Tutarlı dönüşüm.
        seconds = _dt_to_seconds(dt)
        self._last_dt = dt  # Diğer çizim metodları için sakla
        target = 220 if overlay_active else 0
        # fade_speed is in alpha units per millisecond, but we pass ms; keep it fine
        fade_speed = 300 * seconds
        if self.fade_alpha < target:
            self.fade_alpha = min(target, self.fade_alpha + fade_speed)
        elif self.fade_alpha > target:
            self.fade_alpha = max(target, self.fade_alpha - fade_speed)

        if overlay_active:
            tau = math.tau if hasattr(math, "tau") else 2 * math.pi
            self.pulse_time = (self.pulse_time + seconds * 2.0) % tau
        else:
            self.pulse_time = 0.0

        if self.selection_flash > 0:
            self.selection_flash = max(0.0, self.selection_flash - seconds)
            if self.selection_flash == 0:
                self.interaction_locked = False

    def trigger_selection_feedback(self, index: int) -> None:
        self.selection_index = index
        self.selection_flash = self.selection_flash_duration
        self.interaction_locked = True

    def is_selection_animating(self) -> bool:
        return self.selection_flash > 0

    def clear_selection_feedback(self) -> None:
        self.selection_index = -1
        self.selection_flash = 0.0
        self.interaction_locked = False

    # Moved to MysteryCardUI class; UICard does not need vignette helper

    # Note: `_fit_icon_cover` intentionally does not exist on `UICard` anymore.
    # The icon sizing helper is implemented on `MysteryCardUI` because icon loading
    # is performed there. `UICard` simply uses the `icon_getter` callable provided
    # by `MysteryCardUI` which performs fitting.

    def is_interaction_locked(self) -> bool:
        return self.interaction_locked or self.is_flip_animating()

    def is_flip_animating(self) -> bool:
        """Herhangi bir kart hala dönme animasyonundaysa True."""
        for w in self.card_widgets:
            if not w.is_revealed:
                return True
        return False

    def _get_overlay_scale(self, window_width: int, window_height: int, *, min_scale: float = 0.62, max_scale: float = 1.0) -> float:
        """Kart seçim overlay'i için fullscreen bazlı ölçek.

        Referans olarak görülen en büyük pencere boyutu tutulur; böylece
        fullscreen görünüm baz alınır ve pencere küçülünce orantılı küçülür.
        Ayrıca okunabilirlik için, mutlak pencere boyutuna bağlı yumuşak
        bir alt sınır uygulanır (kart metin/ikonları aşırı küçülmesin).
        """
        w = max(1, int(window_width))
        h = max(1, int(window_height))

        if self._overlay_base_size is None:
            self._overlay_base_size = (w, h)
        else:
            bw, bh = self._overlay_base_size
            self._overlay_base_size = (max(bw, w), max(bh, h))

        bw, bh = self._overlay_base_size
        ratio = min(w / float(max(1, bw)), h / float(max(1, bh)))

        rw, rh = self._overlay_readable_min_size
        readable_floor = min(1.0, min(w / float(max(1, rw)), h / float(max(1, rh))))

        effective_min_scale = max(min_scale, readable_floor)
        return max(effective_min_scale, min(max_scale, ratio))

    def draw_selection_overlay(
        self,
        screen: pygame.Surface,
        window_width: int,
        window_height: int,
        fonts: Dict[str, pygame.font.Font],
        cards: List[Dict],
        hint_text: str,
        card_mode_debug: bool = False,
    ) -> None:
        alpha = int(max(0, min(255, self.fade_alpha)))
        if alpha <= 0 or not cards:
            return

        ui_scale = self._get_overlay_scale(window_width, window_height)
        s = lambda v, minimum=1: max(minimum, int(round(v * ui_scale)))

        # Peek modu aktifse sadece göz butonunu göster (sağ alt köşe)
        if self.peek_mode_active:
            # Göz butonu - sağ alt köşede sabit
            peek_btn_size = s(48)
            peek_btn_x = window_width - peek_btn_size - s(20)
            peek_btn_y = window_height - peek_btn_size - s(20)
            self.peek_button_rect = pygame.Rect(peek_btn_x, peek_btn_y, peek_btn_size, peek_btn_size)
            
            # Yuvarlak beyaz arka plan çiz
            center = self.peek_button_rect.center
            radius = peek_btn_size // 2
            pygame.draw.circle(screen, (255, 255, 255), center, radius)  # Beyaz daire
            pygame.draw.circle(screen, (100, 200, 255), center, radius, 2)  # Mavi kenarlık
            
            # Göz kapalı ikonu (kart seçimine dön) - PNG ikon kullan
            peek_icon_path = os.path.join(os.path.dirname(__file__), '..', 'assets', 'kart_secim_sagust.png')
            if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
                peek_icon_path = os.path.join(sys._MEIPASS, 'assets', 'kart_secim_sagust.png')
            try:
                peek_icon = load_image(peek_icon_path)
                icon_size = max(12, int(peek_btn_size * 0.65))
                peek_icon = pygame.transform.smoothscale(peek_icon, (icon_size, icon_size))
                icon_rect = peek_icon.get_rect(center=self.peek_button_rect.center)
                screen.blit(peek_icon, icon_rect)
            except Exception:
                # Fallback: metin göster
                eye_font = fonts.get('medium', fonts.get('small'))
                eye_surf = eye_font.render("X", True, (100, 200, 255))
                screen.blit(eye_surf, eye_surf.get_rect(center=self.peek_button_rect.center))
            return

        # Arka plan overlay: genel UI (panel) temasıyla uyumlu.
        overlay = pygame.Surface((window_width, window_height), pygame.SRCALPHA)
        overlay.fill(UIColors.BG_OVERLAY)
        screen.blit(overlay, (0, 0))

        card_count = len(cards)
        # Use denser grid when debugging with the 'card_mode_debug' flag
        if card_mode_debug:
            card_width = s(220)
            card_height = s(300)
            spacing = s(20)
        else:
            card_width = s(300)
            card_height = s(380)
            spacing = s(48)
        total_width = card_count * card_width + (card_count - 1) * spacing
        panel_width = min(total_width + s(120), window_width - s(40))
        panel_x = max(s(20), window_width // 2 - panel_width // 2)
        panel_rect = pygame.Rect(panel_x, s(60), panel_width, card_height + s(220))
        retro_style.draw_glass_panel(
            screen,
            panel_rect,
            alpha=170,
            border_color=retro_style.glass_border[:3],
            glow=False,
        )

        # Göz butonu - panelin sağ üst köşesinde
        peek_btn_size = s(40)
        peek_btn_x = panel_rect.right - peek_btn_size - s(16)
        peek_btn_y = panel_rect.y + s(16)
        self.peek_button_rect = pygame.Rect(peek_btn_x, peek_btn_y, peek_btn_size, peek_btn_size)
        
        # Göz butonu arka planı - Yuvarlak beyaz
        mouse_pos = get_mouse_pos() if pygame.mouse.get_focused() else None
        peek_hovered = mouse_pos and self.peek_button_rect.collidepoint(mouse_pos)
        center = self.peek_button_rect.center
        radius = peek_btn_size // 2
        pygame.draw.circle(screen, (255, 255, 255), center, radius)  # Beyaz daire
        border_color = (100, 200, 255) if peek_hovered else (180, 180, 200)
        pygame.draw.circle(screen, border_color, center, radius, 2)  # Kenarlık
        
        # Göz ikonu - PNG ikon kullan
        peek_icon_path = os.path.join(os.path.dirname(__file__), '..', 'assets', 'kart_secim_sagust.png')
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            peek_icon_path = os.path.join(sys._MEIPASS, 'assets', 'kart_secim_sagust.png')
        try:
            peek_icon = load_image(peek_icon_path)
            icon_size = int(peek_btn_size * 0.65)
            peek_icon = pygame.transform.smoothscale(peek_icon, (icon_size, icon_size))
            icon_rect = peek_icon.get_rect(center=self.peek_button_rect.center)
            screen.blit(peek_icon, icon_rect)
        except Exception:
            # Fallback: metin göster
            eye_font = fonts.get('small')
            eye_surf = eye_font.render("O", True, (100, 200, 255) if peek_hovered else (180, 180, 200))
            screen.blit(eye_surf, eye_surf.get_rect(center=self.peek_button_rect.center))

        header_x = panel_rect.x + s(40)
        header_y = panel_rect.y + s(28)
        # (Removed) Selection hint text like "1 / 2 / 3 ... seç"
        # (Kaldırıldı) Sağ üst "Tamamen rastgele" butonu
        self.randomize_pill_rect = None

        # Compute start_x and top for grid vs single row layout
        top = panel_rect.y + s(120)
        if card_mode_debug:
            # Compute number of columns that fit comfortably
            # Allow a dynamic count up to 4 columns based on panel width
            available = max(1, panel_rect.width - s(40))
            max_cols_fit = max(1, (available + spacing) // (card_width + spacing))
            cols = max(1, min(4, max_cols_fit))
            cols = min(cols, card_count)
            # Resize card width if we can fit more columns while keeping padding
            fit_width = (panel_rect.width - s(40) - (cols - 1) * spacing) // cols
            if fit_width < card_width:
                card_width = max(s(120), fit_width)
            rows = (card_count + cols - 1) // cols
            # Resize panel rect height to fit rows
            desired_height = s(120) + rows * (card_height + spacing) + s(80)
            panel_rect.height = min(desired_height, window_height - s(120))
            retro_style.draw_glass_panel(
                screen,
                panel_rect,
                alpha=170,
                border_color=retro_style.glass_border[:3],
                glow=False,
            )
            # center a grid of cols columns and respect grid_scroll (vertical)
            total_grid_width = cols * card_width + (cols - 1) * spacing
            start_x = panel_rect.x + max(s(20), (panel_rect.width - total_grid_width) // 2)
            # compute the visible area and max scroll
            visible_height = panel_rect.height - (top - panel_rect.y) - 40
            total_grid_height = rows * (card_height + spacing)
            self.grid_max_scroll = max(0, total_grid_height - visible_height)
            # clamp current scroll
            self.grid_scroll = max(0, min(self.grid_scroll, self.grid_max_scroll))
            # scrollbar drawing params
            scrollbar_track_x = panel_rect.right - s(20)
            scrollbar_track_y = top
            scrollbar_track_w = s(10)
            scrollbar_track_h = visible_height
            if self.grid_max_scroll > 0:
                thumb_h = max(s(24), int(scrollbar_track_h * (visible_height / max(1, total_grid_height))))
                # compute thumb top position between 0 and scrollbar_track_h - thumb_h
                scroll_ratio = self.grid_scroll / max(1, self.grid_max_scroll)
                thumb_top = scrollbar_track_y + int(scroll_ratio * (scrollbar_track_h - thumb_h))
            else:
                thumb_h = scrollbar_track_h
                thumb_top = scrollbar_track_y
        else:
            start_x = panel_rect.x + (panel_rect.width - total_width) // 2

        mouse_pos = get_mouse_pos() if pygame.mouse.get_focused() else None
        self.card_rects = []
        self.hover_index = -1
        # Ensure card widget count matches cards
        if len(self.card_widgets) != len(cards):
            # Recreate widgets
            self.card_widgets = [UICard(cards[i], pygame.Rect(0, 0, card_width, card_height), i, fonts, self._get_icon_surface, self._reveal_sfx_callback) for i in range(len(cards))]
        for idx, card in enumerate(cards):
            if card_mode_debug:
                col = idx % cols
                row = idx // cols
                rect = pygame.Rect(start_x + col * (card_width + spacing), top + row * (card_height + spacing) - self.grid_scroll, card_width, card_height)
            else:
                rect = pygame.Rect(start_x + idx * (card_width + spacing), top, card_width, card_height)
            # update/assign rect to widget
            widget = self.card_widgets[idx]
            widget.base_rect = rect
            widget.update(dt=self._last_dt if hasattr(self, '_last_dt') else 16.0, mouse_pos=mouse_pos)
            self.card_rects.append(rect)
            hovering_allowed = not self.is_interaction_locked()
            hovered = widget.hover if hovering_allowed else idx == self.selection_index
            if hovered and hovering_allowed:
                self.hover_index = idx
            dimmed = False
            if self.selection_index != -1 and idx != self.selection_index:
                dimmed = True
            elif self.hover_index != -1 and idx != self.hover_index and hovering_allowed:
                dimmed = True
            # Render via UICard
            self.card_widgets[idx].render(screen, debug=card_mode_debug)

        # Alt aksiyon: Kart almadan devam et + Yeniden Çek
        btn_font = fonts.get('small')
        btn_h = s(44)
        btn_y = panel_rect.bottom - btn_h - s(26)
        total_btn_area_w = min(s(660), panel_rect.width - s(80))
        gap = s(12)
        each_w = (total_btn_area_w - gap) // 2
        start_x = panel_rect.centerx - total_btn_area_w // 2
        # Skip butonu (sol)
        self.skip_button_rect = pygame.Rect(start_x, btn_y, each_w, btn_h)
        retro_style.draw_glass_panel(
            screen,
            self.skip_button_rect,
            alpha=155,
            border_color=retro_style.glass_border[:3],
            glow=False,
        )
        skip_label = btn_font.render(t('card_skip_selection'), True, retro_style.text_primary)
        screen.blit(skip_label, skip_label.get_rect(center=self.skip_button_rect.center))
        # Reroll butonu (sağ)
        reroll_x = start_x + each_w + gap
        self.reroll_button_rect = pygame.Rect(reroll_x, btn_y, each_w, btn_h)
        retro_style.draw_glass_panel(
            screen,
            self.reroll_button_rect,
            alpha=175,
            border_color=(220, 170, 40),
            glow=False,
        )
        reroll_label = btn_font.render(t('card_reroll_selection'), True, (255, 215, 80))
        screen.blit(reroll_label, reroll_label.get_rect(center=self.reroll_button_rect.center))

        # Draw a scrollbar thumb in debug grid mode to indicate scroll position
        if card_mode_debug and self.grid_max_scroll > 0:
            track_rect = pygame.Rect(scrollbar_track_x, scrollbar_track_y, scrollbar_track_w, scrollbar_track_h)
            thumb_rect = pygame.Rect(scrollbar_track_x + 2, thumb_top, scrollbar_track_w - 4, thumb_h)
            pygame.draw.rect(screen, (30, 30, 40, 160), track_rect, border_radius=6)
            pygame.draw.rect(screen, (200, 200, 220, 200), thumb_rect, border_radius=6)
            # debug helper: small scroll instructions
            dbg_font = fonts.get('small')
            dbg_help = dbg_font.render('Scroll: Mouse Wheel', True, (200, 200, 200))
            screen.blit(dbg_help, (scrollbar_track_x - dbg_help.get_width() - s(10), scrollbar_track_y + scrollbar_track_h - dbg_help.get_height() - s(6)))
        # Reset randomize pill rect if overlay is closed
        if not cards:
            self.randomize_pill_rect = None

    def draw_active_cards_panel(
        self,
        screen: pygame.Surface,
        cards: List[Dict],
        fonts: Dict[str, pygame.font.Font],
        x: int,
        y: int,
        width: int = 260,
        *,
        max_display: int = 6,
        placeholder_text: str | None = None,
        columns: int = 1,
    ) -> int:
        font_small = fonts.get("small")
        font_desc = fonts.get("desc")
        tag_font = fonts.get("tag")
        card_title_font = fonts.get("card_title", font_small)
        icon_font = fonts.get("icon", font_small)
        width = max(180, width)

        if not cards:
            if placeholder_text is None:
                placeholder_text = t('card_placeholder_empty')
            placeholder = font_small.render(str(placeholder_text), True, (180, 180, 180))
            screen.blit(placeholder, (x, y))
            return placeholder.get_height()

        def _compact_text(value: str, max_len: int = 14) -> str:
            text = str(value or '').strip()
            if len(text) <= max_len:
                return text
            return f"{text[:max(3, max_len - 3)]}..."

        def _parse_status(raw_status: str) -> tuple[str, str]:
            status = str(raw_status or '').strip()
            if not status:
                return 'aktif', 'Aktif'
            low = status.lower()
            if 'bekle' in low or 'cooldown' in low:
                return 'beklemede', _compact_text(status, 12)
            if low.endswith('s') or ' sn' in low or 'sn ' in low:
                return 'sureli', _compact_text(status, 10)
            if 'hak' in low:
                return 'hazir', _compact_text(status, 12)
            if 'aktif' in low:
                return 'aktif', 'Aktif'
            return 'durum', _compact_text(status, 12)

        def _badge_palette(state_label: str) -> tuple[tuple[int, int, int, int], tuple[int, int, int, int]]:
            label = str(state_label or '').lower()
            if label == 'aktif' or label == 'hazir':
                return (36, 130, 86, 190), (110, 225, 170, 220)
            if label == 'beklemede' or label == 'sureli':
                return (62, 70, 84, 190), (168, 178, 196, 220)
            return (56, 72, 102, 190), (132, 176, 238, 220)

        def _row_border_rgba(card: Dict[str, Any]) -> tuple[int, int, int, int]:
            rarity_map = {
                'legendary': UIColors.RARITY_LEGENDARY,
                'epic': UIColors.RARITY_EPIC,
                'rare': UIColors.RARITY_RARE,
                'uncommon': UIColors.RARITY_UNCOMMON,
                'common': UIColors.RARITY_COMMON,
            }
            rarity = str(card.get('rarity', '') or '').strip().lower()
            if not rarity:
                tag = str(card.get('tag', '') or '').strip().lower()
                if tag in rarity_map:
                    rarity = tag
                elif tag == 'perk':
                    rarity = 'legendary'
            base = rarity_map.get(rarity)
            if base is None:
                try:
                    style_border = tuple((card.get('style', {}) or {}).get('border', ()))
                    if len(style_border) >= 3:
                        base = (int(style_border[0]), int(style_border[1]), int(style_border[2]))
                except Exception:
                    base = None
            if base is None:
                return (138, 154, 188, 100)
            return (int(base[0]), int(base[1]), int(base[2]), 165)

        # Compact Mode: Fixed height bars
        row_height = 46
        row_gap = 6
        col_gap = 8
        icon_size = 30
        content_padding = 8
        
        md = max(1, int(max_display))
        displayed = cards[-md:]
        
        # İki sütun hesaplaması
        cols = max(1, int(columns))
        if cols > 1:
            col_width = max(120, (width - col_gap * (cols - 1)) // cols)
        else:
            col_width = width
        
        current_y = y
        total_rows = (len(displayed) + cols - 1) // cols
        total_height = total_rows * row_height + max(0, total_rows - 1) * row_gap

        for idx, card in enumerate(displayed):
            col = idx % cols
            row = idx // cols
            card_x = x + col * (col_width + col_gap)
            card_y = y + row * (row_height + row_gap)
            # Background
            panel_color = (14, 18, 34, 186)
            
            # Create a surface for the row to handle alpha transparency properly
            row_surface = pygame.Surface((col_width, row_height), pygame.SRCALPHA)
            row_rect_local = row_surface.get_rect()
            row_border_color = _row_border_rgba(card)
            
            # Glass effect background
            pygame.draw.rect(row_surface, panel_color, row_rect_local, border_radius=6)
            pygame.draw.rect(row_surface, row_border_color, row_rect_local, 1, border_radius=6)
            
            # Icon (Left) - Local coordinates
            icon_rect_local = pygame.Rect(content_padding, (row_height - icon_size) // 2, icon_size, icon_size)
            
            # Icon placeholder/image
            try:
                icon_image = self._get_icon_surface(card.get('icon_image'), (icon_size, icon_size))
                if icon_image:
                    row_surface.blit(icon_image, icon_rect_local)
                else:
                    # Text icon fallback (ASCII only)
                    txt_icon = str(card.get('icon', '*') or '*')
                    safe_icon = ''.join(ch for ch in txt_icon if ch.isascii() and ch.isalnum())[:2]
                    if not safe_icon:
                        safe_icon = '*'
                    icon_surf = font_small.render(safe_icon, True, card['color'])
                    icon_pos = icon_surf.get_rect(center=icon_rect_local.center)
                    row_surface.blit(icon_surf, icon_pos)
            except Exception:
                pass
            try:
                icon_border = pygame.Rect(icon_rect_local.x - 1, icon_rect_local.y - 1, icon_rect_local.w + 2, icon_rect_local.h + 2)
                pygame.draw.rect(row_surface, (170, 185, 215, 110), icon_border, 1, border_radius=6)
            except Exception:
                pass

            # Title (Left center)
            title_local_x = icon_rect_local.right + 10
            title_text = get_card_title(card.get("id", ""), card.get("title", "???"))
            status_label, status_value = _parse_status(card.get("status", ""))
            badge_text = status_value

            badge_font = tag_font if tag_font else font_small
            max_badge_w = max(52, col_width - title_local_x - 6)
            badge_text_surf = badge_font.render(badge_text, True, (232, 238, 248))
            badge_w = badge_text_surf.get_width() + 12
            if badge_w > max_badge_w:
                compact = badge_text
                guard = 0
                while badge_w > max_badge_w and len(compact) > 2 and guard < 40:
                    compact = compact[:-2].rstrip() + "..."
                    badge_text_surf = badge_font.render(compact, True, (232, 238, 248))
                    badge_w = badge_text_surf.get_width() + 12
                    guard += 1
            badge_h = max(24, badge_text_surf.get_height() + 6)
            badge_right = col_width - content_padding
            badge_left = max(title_local_x + 36, badge_right - badge_w)
            max_title_w = max(18, badge_left - title_local_x - 8)
            
            try:
                title_surf = card_title_font.render(title_text, True, (238, 242, 250))
                if title_surf.get_width() > max_title_w and max_title_w > 20:
                    truncated = title_text
                    truncate_count = 0
                    while title_surf.get_width() > max_title_w and len(truncated) > 2 and truncate_count < 50:
                        truncated = truncated[:-2].rstrip() + "..."
                        title_surf = card_title_font.render(truncated, True, (238, 242, 250))
                        truncate_count += 1
                
                title_local_y = (row_height - title_surf.get_height()) // 2
                row_surface.blit(title_surf, (title_local_x, title_local_y))
            except Exception:
                pass
            
            # Status Badge (Right)
            try:
                badge_bg, badge_border = _badge_palette(status_label)
                status_local_x = badge_left
                status_local_y = (row_height - badge_h) // 2
                st_bg_rect = pygame.Rect(status_local_x, status_local_y, badge_w, badge_h)
                pygame.draw.rect(row_surface, badge_bg, st_bg_rect, border_radius=9)
                pygame.draw.rect(row_surface, badge_border, st_bg_rect, 1, border_radius=9)
                row_surface.blit(badge_text_surf, badge_text_surf.get_rect(center=st_bg_rect.center))
            except Exception:
                pass

            # Blit the composed row onto the main screen
            screen.blit(row_surface, (card_x, card_y))

        return total_height

    def handle_mouse_click(self, pos: tuple[int, int]) -> int | str | None:
        # Peek butonu kontrolü
        if getattr(self, 'peek_button_rect', None) and self.peek_button_rect.collidepoint(pos):
            self.peek_mode_active = not self.peek_mode_active
            return 'PEEK'
        
        # Peek modundayken kart seçimi yapılamaz
        if self.peek_mode_active:
            return None
            
        for idx, rect in enumerate(self.card_rects):
            if rect.collidepoint(pos):
                return idx
        # Yeniden Çek
        if getattr(self, 'reroll_button_rect', None) and self.reroll_button_rect.collidepoint(pos):
            return 'REROLL'
        # Kart almadan devam et
        if getattr(self, 'skip_button_rect', None) and self.skip_button_rect.collidepoint(pos):
            return 'SKIP'
        return None

    def handle_mouse_wheel(self, delta: int) -> None:
        """Scroll the grid up/down in debug grid mode (delta is positive up, negative down)"""
        step = 40
        self.grid_scroll = max(0, min(self.grid_scroll - delta * step, getattr(self, 'grid_max_scroll', 0)))

    def handle_mouse_move(self, pos: tuple[int, int]) -> None:
        """Update hover_index based on mouse position (works with scrolled grid)."""
        if not self.card_rects:
            self.hover_index = -1
            return
        for idx, rect in enumerate(self.card_rects):
            if rect.collidepoint(pos):
                self.hover_index = idx
                return
        self.hover_index = -1

    def _draw_card(
        self,
        card: Dict,
        idx: int,
        rect: pygame.Rect,
        hovered: bool,
        dimmed: bool,
        screen: pygame.Surface,
        fonts: Dict[str, pygame.font.Font],
        debug: bool = False,
    ) -> None:
        style = card.get("style", {})
        corner = style.get("corner", 26)
        accent = card["color"]
        gradient_colors = style.get("gradient", [card.get("bg", (34, 34, 46)), accent])
        border_color = style.get("border", accent)
        icon_bg = style.get("icon_bg", (40, 40, 50))

        shadow = pygame.Surface((rect.width + 26, rect.height + 26), pygame.SRCALPHA)
        pygame.draw.rect(shadow, (0, 0, 0, 160), (13, 13, rect.width, rect.height), border_radius=corner + 6)
        screen.blit(shadow, (rect.x - 13, rect.y - 6))

        card_surface = pygame.Surface(rect.size, pygame.SRCALPHA)
        self._paint_card_body(card_surface, gradient_colors, corner)
        card_key = card.get("id") or card.get("title", str(idx))
        self._apply_card_pattern(card_surface, style, accent, corner, card_key)

        top_rect = pygame.Rect(0, 0, rect.width, 140)
        top_overlay = pygame.Surface(top_rect.size, pygame.SRCALPHA)
        pygame.draw.rect(top_overlay, (*accent, 45), top_overlay.get_rect(), border_radius=corner)
        card_surface.blit(top_overlay, (0, 0))

        # Pulse used for subtle floating and hover animations
        pulse_base = (math.sin(self.pulse_time * 2.0 + idx * 0.63) + 1) * 0.5
        pulse = (pulse_base * 0.7 + 0.3) if hovered else (pulse_base * 0.35 + 0.65)
        glow_factor = 0.9 + 0.15 * pulse
        glow_color = tuple(min(255, int(c * glow_factor)) for c in border_color)
        pygame.draw.rect(
            card_surface,
            glow_color,
            card_surface.get_rect(),
            width=3 if hovered else 2,
            border_radius=corner,
        )

        icon_rect = pygame.Rect(22, 20, 96, 96)
        icon_holder = pygame.Surface(icon_rect.size, pygame.SRCALPHA)
        # Icon holder with soft inner gradient and border
        icon_holder_grad = pygame.Surface(icon_holder.get_size(), pygame.SRCALPHA)
        self._fill_gradient(icon_holder_grad, (*icon_bg, 240), (min(255, icon_bg[0]+40), min(255, icon_bg[1]+40), min(255, icon_bg[2]+40), 230))
        mask = pygame.Surface(icon_holder.get_size(), pygame.SRCALPHA)
        pygame.draw.rect(mask, (255, 255, 255, 255), mask.get_rect(), border_radius=18)
        icon_holder_grad.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        icon_holder.blit(icon_holder_grad, (0, 0))
        pygame.draw.rect(icon_holder, glow_color, icon_holder.get_rect(), width=2 if hovered else 1, border_radius=18)
        # Ensure the inner icon image is slightly smaller than the holder border so
        # the icon never draws over the holder's rounded border.
        inner_padding = 2
        inner_size = (icon_rect.width - inner_padding * 2, icon_rect.height - inner_padding * 2)
        icon_image = self._get_icon_surface(card.get("icon_image"), inner_size)
        if icon_image:
            # center icon inside the holder
            ix = (icon_rect.width - inner_size[0]) // 2
            iy = (icon_rect.height - inner_size[1]) // 2
            icon_holder.blit(icon_image, (ix, iy))
        else:
            from emoji_renderer import emoji_surface
            _emoji_ic = emoji_surface(card.get("icon", ""), min(inner_size))
            if _emoji_ic:
                ix = (icon_rect.width - _emoji_ic.get_width()) // 2
                iy = (icon_rect.height - _emoji_ic.get_height()) // 2
                icon_holder.blit(_emoji_ic, (ix, iy))
            else:
                icon_glyph = fonts["icon"].render(_ui_safe_icon_text(card.get("icon", "??"), fallback="??"), True, (12, 12, 18))
                icon_holder.blit(icon_glyph, icon_glyph.get_rect(center=(icon_rect.width // 2, icon_rect.height // 2)))
        card_surface.blit(icon_holder, icon_rect.topleft)

        tag_text = card.get("tag", "Bonus").upper()
        tag_label = fonts["tag"].render(tag_text, True, (240, 240, 255))
        tag_bg = pygame.Surface((tag_label.get_width() + 18, tag_label.get_height() + 6), pygame.SRCALPHA)
        # tag background gets a neon halo when hovered
        halo = pygame.Surface(tag_bg.get_size(), pygame.SRCALPHA)
        pygame.draw.rect(halo, (*glow_color[:3], 40 if hovered else 20), halo.get_rect(), border_radius=12)
        tag_bg.blit(halo, (0, 0))
        pygame.draw.rect(tag_bg, glow_color, tag_bg.get_rect(), border_radius=12)
        tag_bg.blit(tag_label, (9, 3))
        card_surface.blit(tag_bg, (rect.width - tag_bg.get_width() - 20, 28))

            # Prepare title text
        card_title_text = get_card_title(card.get("id", ""), card.get("title", ""))
        title_text = f"{idx + 1}. {card_title_text}"
        # If title is longer than available area, trim with ellipsis
        title_font = fonts.get("card_title")
        title_max_width = rect.width - 48
        if title_font.size(title_text)[0] > title_max_width:
            short = title_text
            while title_font.size(short + "...")[0] > title_max_width and len(short) > 0:
                short = short[:-1]
            title_text = short.rstrip() + "..."
        title_surface = title_font.render(title_text, True, (250, 250, 255))
        # Make title background stronger for readability in debug grid
        title_bg_color = (*accent, 200) if debug else (*accent, 120)
        self._blit_text_with_bg(card_surface, title_surface, (24, 120), title_bg_color)

        # Replace the large numeric value badge with a type label:
        # - Kalıcı: persistent perks
        # - Tek Kullanım: single-use cards
        # - Sınırlı: timed/charged/limited effects
        type_label = t(_card_type_label_key(card))
        type_font = fonts.get("tag") or fonts.get("desc") or fonts.get("small")
        type_surface = type_font.render(type_label, True, (255, 255, 255))
        type_bg_color = (*accent, 100)
        value_rect = self._blit_text_with_bg(
            card_surface,
            type_surface,
            (rect.width // 2 - (type_surface.get_width() // 2) - 12, 170),
            type_bg_color,
            padding=(16, 6),
            radius=18,
        )

        # Wrap description with available width and reduce max cols in debug
        desc_wrap_width = 30 if not debug else 28
        card_desc_text = get_card_description(card.get("id", ""), card.get("value"), card.get("description", ""))
        desc_lines = self._wrap_text(card_desc_text, desc_wrap_width)
        # Cap description lines in overlay to avoid oversizing the card
        max_desc_lines_overlay = 3
        if len(desc_lines) > max_desc_lines_overlay:
            desc_lines = desc_lines[:max_desc_lines_overlay]
            last = desc_lines[-1]
            ellipsis = '...'
            desc_width_avail = rect.width - 48
            while fonts["desc"].size(last + ellipsis)[0] > desc_width_avail and len(last) > 0:
                last = last[:-1]
            desc_lines[-1] = last.rstrip() + ellipsis
        line_height_overlay = fonts["desc"].get_linesize()
        desc_height = len(desc_lines) * line_height_overlay + 18
        desc_surface = pygame.Surface((rect.width - 48, desc_height), pygame.SRCALPHA)
        # Use a slightly stronger background on debug mode for better readability
        desc_bg_alpha = 220 if debug else 140
        pygame.draw.rect(desc_surface, (3, 3, 10, desc_bg_alpha), desc_surface.get_rect(), border_radius=14)
        for i, line in enumerate(desc_lines):
            desc_text = fonts["desc"].render(line, True, (230, 230, 240))
            desc_surface.blit(desc_text, (12, 8 + i * 24))
        card_surface.blit(desc_surface, (24, value_rect.bottom + 20))

        # Add a small index bubble in the top-left like on the screenshot, subtle and readable
        idx_circle_r = 20
        idx_bg = pygame.Surface((idx_circle_r * 2, idx_circle_r * 2), pygame.SRCALPHA)
        pygame.draw.ellipse(idx_bg, (255, 255, 255, 230), idx_bg.get_rect())
        pygame.draw.ellipse(idx_bg, (160, 140, 220, 180), idx_bg.get_rect(), width=2)
        idx_font = fonts.get('card_title')
        idx_text = idx_font.render(str(idx + 1), True, (18, 18, 22))
        idx_bg.blit(idx_text, ((idx_bg.get_width() - idx_text.get_width()) // 2, (idx_bg.get_height() - idx_text.get_height()) // 2 - 1))
        card_surface.blit(idx_bg, (12, 12))

        if dimmed:
            dim_surface = pygame.Surface(card_surface.get_size(), pygame.SRCALPHA)
            dim_surface.fill((5, 5, 20, 140))
            card_surface.blit(dim_surface, (0, 0))

        press_ratio = 0.0
        if self.selection_index == idx and self.selection_flash_duration > 0:
            progress = 1.0 - (self.selection_flash / self.selection_flash_duration)
            press_ratio = max(0.0, min(1.0, progress))
            flash_overlay = pygame.Surface(card_surface.get_size(), pygame.SRCALPHA)
            flash_alpha = int(120 * (1 - progress))
            pygame.draw.rect(flash_overlay, (*glow_color[:3], flash_alpha), flash_overlay.get_rect(), border_radius=corner)
            card_surface.blit(flash_overlay, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)

        # Floating and hover lift animations
        scale = 1.0
        lift = 0.0
        bob = int(6 * (pulse_base - 0.5)) if not hovered else 0
        if hovered and not dimmed:
            scale += 0.10
            lift = 12.0
        if press_ratio > 0:
            scale *= 1.0 - 0.05 * press_ratio
            lift -= 4.0 * press_ratio

        output_surface = card_surface
        if abs(scale - 1.0) > 0.01 or bob != 0:
            new_size = (
                max(1, int(rect.width * scale)),
                max(1, int(rect.height * scale)),
            )
            output_surface = pygame.transform.smoothscale(card_surface, new_size)

        dest_x = rect.centerx - output_surface.get_width() // 2
        dest_y = rect.centery - output_surface.get_height() // 2 - int(lift) + bob
        # Hover halo (blit behind the card for a soft neon outline)
        if hovered and not dimmed:
            halo_w = output_surface.get_width() + 34
            halo_h = output_surface.get_height() + 34
            halo = pygame.Surface((halo_w, halo_h), pygame.SRCALPHA)
            for i in range(6, 0, -1):
                a = int(32 * (i / 6))
                c = (*accent, a)
                pygame.draw.rect(halo, c, (6 - i, 6 - i, halo_w - (6 - i) * 2, halo_h - (6 - i) * 2), border_radius=corner + 16)
            screen.blit(halo, (dest_x - 17, dest_y - 17), special_flags=pygame.BLEND_RGBA_ADD)
        screen.blit(output_surface, (dest_x, dest_y))
        # Render debug overlay box if requested
        if debug:
            dbg_font = fonts.get('small')
            debug_text = f"id={card.get('id')} p={card.get('persistent', False)}"
            dbg_surface = dbg_font.render(debug_text, True, (200, 200, 200))
            dbg_rect = dbg_surface.get_rect(topleft=(rect.x + 8, rect.y + 8))
            # draw small rounded background for debug label for readability
            dbg_bg = pygame.Surface((dbg_rect.width + 12, dbg_rect.height + 8), pygame.SRCALPHA)
            pygame.draw.rect(dbg_bg, (10, 10, 20, 190), dbg_bg.get_rect(), border_radius=6)
            screen.blit(dbg_bg, (dbg_rect.x - 6, dbg_rect.y - 4))
            screen.blit(dbg_surface, dbg_rect)
            # Draw a large index bubble in the top-left to make cards easier to locate
            idx_font = fonts.get('card_title')
            idx_text = str(idx + 1)
            idx_surface = idx_font.render(idx_text, True, (20, 20, 24))
            idx_bg_w = idx_surface.get_width() + 12
            idx_bg_h = idx_surface.get_height() + 8
            idx_bg = pygame.Surface((idx_bg_w, idx_bg_h), pygame.SRCALPHA)
            pygame.draw.ellipse(idx_bg, (255, 255, 255, 220), idx_bg.get_rect())
            pygame.draw.ellipse(idx_bg, (140, 120, 220, 200), idx_bg.get_rect(), width=2)
            bg_x = rect.x + 12
            bg_y = rect.y + 12
            screen.blit(idx_bg, (bg_x, bg_y))
            screen.blit(idx_surface, (bg_x + (idx_bg_w - idx_surface.get_width()) // 2, bg_y + (idx_bg_h - idx_surface.get_height()) // 2 - 1))

    def _paint_card_body(self, surface: pygame.Surface, gradient_colors: List[tuple[int, int, int]], corner: int) -> None:
        if not gradient_colors:
            gradient_colors = [(34, 34, 46), (48, 48, 60)]
        if len(gradient_colors) == 1:
            gradient_colors = [gradient_colors[0], gradient_colors[0]]
        grad_surface = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        start = (*gradient_colors[0], 255)
        end = (*gradient_colors[-1], 255)
        self._fill_gradient(grad_surface, start, end)
        mask = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        pygame.draw.rect(mask, (255, 255, 255, 255), mask.get_rect(), border_radius=corner)
        grad_surface.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        surface.blit(grad_surface, (0, 0))

    def _apply_card_pattern(
        self,
        surface: pygame.Surface,
        style: Dict,
        accent: tuple[int, int, int],
        corner: int,
        seed_key: str,
    ) -> None:
        pattern = style.get("pattern")
        if not pattern:
            return
        pattern_surface = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        color = (*accent, 28)
        width, height = surface.get_size()
        rng = random.Random(seed_key)
        if pattern == "grid":
            spacing = 18
            for x in range(0, width, spacing):
                pygame.draw.line(pattern_surface, color, (x, 0), (x, height), 1)
            for y in range(0, height, spacing):
                pygame.draw.line(pattern_surface, color, (0, y), (width, y), 1)
        elif pattern == "laser":
            spacing = 26
            for offset in range(-height, width, spacing):
                start = (offset, 0)
                end = (offset + height, height)
                pygame.draw.line(pattern_surface, (*accent, 36), start, end, 3)
        elif pattern == "spark":
            for i in range(10):
                radius = 6 + i % 3
                pos = (rng.randint(20, width - 20), rng.randint(40, height - 40))
                pygame.draw.circle(pattern_surface, (*accent, 30), pos, radius, 0)
        elif pattern == "wave":
            for y in range(0, height, 20):
                points = []
                for x in range(0, width, 10):
                    offset = math.sin((x + y * 3) * 0.08) * 6
                    points.append((x, y + offset))
                if len(points) > 1:
                    pygame.draw.lines(pattern_surface, (*accent, 26), False, points, 2)
        mask = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        pygame.draw.rect(mask, (255, 255, 255, 255), mask.get_rect(), border_radius=corner)
        pattern_surface.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        surface.blit(pattern_surface, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)

    def _fit_icon_cover(self, image: pygame.Surface, size: tuple[int, int]) -> pygame.Surface:
        """Scale and crop the icon image so it fully covers the given size.

        This trims transparent borders, scales to cover (preserving aspect ratio),
        and center-crops to the final size.
        """
        if not image:
            return image
        # Try bounding rect based on alpha to trim transparent padding
        try:
            bounds = image.get_bounding_rect()
            if bounds.width > 0 and bounds.height > 0 and (bounds.width != image.get_width() or bounds.height != image.get_height()):
                try:
                    image = image.subsurface(bounds).copy()
                except Exception:
                    pass
        except Exception:
            pass
        iw, ih = image.get_size()
        tw, th = size
        if iw == tw and ih == th:
            return image
        # Scale to cover
        scale = max(tw / iw, th / ih)
        new_w = max(1, int(iw * scale))
        new_h = max(1, int(ih * scale))
        try:
            scaled = pygame.transform.smoothscale(image, (new_w, new_h))
        except Exception:
            scaled = pygame.transform.scale(image, (new_w, new_h))
        # Crop center
        cx = max(0, (new_w - tw) // 2)
        cy = max(0, (new_h - th) // 2)
        try:
            cropped = scaled.subsurface((cx, cy, tw, th)).copy()
            return cropped
        except Exception:
            return pygame.transform.smoothscale(scaled, (tw, th))

    def _get_icon_surface(self, image_path: str | None, size: tuple[int, int]) -> pygame.Surface | None:
        if not image_path:
            return None
        cache_key = (image_path, size)
        if cache_key in self.icon_cache:
            return self.icon_cache[cache_key]
        if not os.path.exists(image_path):
            return None
        try:
            image = load_image(image_path, convert_alpha=True)
            image = self._fit_icon_cover(image, size)
            self.icon_cache[cache_key] = image
            return image
        except Exception as exc:  # pylint: disable=broad-except
            print(f"⚠️ Kart ikonu yüklenemedi ({image_path}): {exc}")
            return None


# ==================== SOFT GLOW TEXTURE CACHE ====================
# Profesyonel parçacık efektleri için önceden işlenmiş
# radyal gradyan (soft blob) texture'ları - Balatro/Slay the Spire kalitesinde
class _GlowCache:
    """Radyal gradyan glow texture'larını cache'ler. Her boyut için
    piksel piksel hesaplamak yerine bir kez oluşturur, sonra tint+alpha
    ile blit eder. Bu teknik AAA kart oyunlarında standart."""
    _base_cache: Dict[int, pygame.Surface] = {}
    _tinted_cache: Dict[tuple, pygame.Surface] = {}
    _MAX_TINTED = 256  # Max tinted cache boyutu

    @classmethod
    def get(cls, radius: int) -> pygame.Surface:
        """Beyaz radyal gradyan daire döndürür (SRCALPHA).
        Merkezde alpha=255, kenarda alpha=0, Gaussian benzeri eğri."""
        radius = max(2, min(radius, 64))  # Boyut sınırla
        if radius in cls._base_cache:
            return cls._base_cache[radius]
        size = radius * 2
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        # Radyal gradyan: Gaussian falloff
        r_sq_inv = 1.0 / (radius * radius) if radius > 0 else 1.0
        for y in range(size):
            dy = y - radius + 0.5
            dy2 = dy * dy
            for x in range(size):
                dx = x - radius + 0.5
                dist_sq = (dx * dx + dy2) * r_sq_inv
                if dist_sq > 1.0:
                    continue
                # Smooth Gaussian-like falloff: exp(-3 * dist^2)
                alpha = int(255 * math.exp(-3.0 * dist_sq))
                if alpha > 0:
                    surf.set_at((x, y), (255, 255, 255, alpha))
        cls._base_cache[radius] = surf
        return surf

    @classmethod
    def get_tinted(cls, radius: int, color: tuple, alpha_mult: float = 1.0) -> pygame.Surface:
        """Renklendirilmiş glow texture döndürür.
        Sonuçlar cache'lenir — aynı (radius, color, alpha_bucket) tekrar hesaplanmaz."""
        radius = max(2, min(radius, 64))
        # Alpha'yı 16 adıma kuantize et (cache hit'i artırır)
        a_bucket = max(0, min(15, int(alpha_mult * 15.9)))
        cache_key = (radius, color[0], color[1], color[2], a_bucket)
        if cache_key in cls._tinted_cache:
            return cls._tinted_cache[cache_key]

        base = cls.get(radius).copy()
        # Renk tint uygula
        tint = pygame.Surface(base.get_size(), pygame.SRCALPHA)
        effective_alpha = int(255 * (a_bucket / 15.0))
        tint.fill((color[0], color[1], color[2], effective_alpha))
        base.blit(tint, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)

        # Cache boyutunu sınırla
        if len(cls._tinted_cache) >= cls._MAX_TINTED:
            # En eski %25'i sil
            keys = list(cls._tinted_cache.keys())
            for k in keys[:len(keys) // 4]:
                del cls._tinted_cache[k]

        cls._tinted_cache[cache_key] = base
        return base


# ==================== GRADIENT CACHE ====================
_gradient_cache: Dict[tuple, pygame.Surface] = {}
_GRADIENT_CACHE_MAX = 64


def _get_cached_gradient(size: tuple[int, int], start_color: tuple, end_color: tuple) -> pygame.Surface:
    """Dikey gradyan surface'ini cache'leyerek tekrar hesaplamayı önler.
    Aynı boyut ve renk kombinasyonu için surface bir kez oluşturulur,
    sonraki çağrılarda cache'den döner."""
    key = (size, start_color, end_color)
    if key in _gradient_cache:
        return _gradient_cache[key]
    surf = pygame.Surface(size, pygame.SRCALPHA)
    width, height = size
    sc_len = len(start_color)
    for y in range(height):
        ratio = y / max(1, height - 1)
        color = tuple(
            int(start_color[i] + (end_color[i] - start_color[i]) * ratio)
            for i in range(sc_len)
        )
        pygame.draw.line(surf, color, (0, y), (width, y))
    if len(_gradient_cache) >= _GRADIENT_CACHE_MAX:
        keys = list(_gradient_cache.keys())
        for k in keys[:len(keys) // 4]:
            del _gradient_cache[k]
    _gradient_cache[key] = surf
    return surf


class UICard:
    """UI widget for a single card in the Mystery/Cards overlay.

    Responsibilities:
    - Render its own rounded glass card with border, glow according to rarity
    - Manage hover/scale animation and hit testing
    - Render title, value, description, icon placeholder and hotkey indicator
    """

    RARITY_COLORS = {
        'legendary': UIColors.RARITY_LEGENDARY,
        'epic': UIColors.RARITY_EPIC,
        'rare': UIColors.RARITY_RARE,
        'uncommon': UIColors.RARITY_UNCOMMON,
        'common': UIColors.RARITY_COMMON,
    }

    # Nadirlik bazlı animasyon süreleri (saniye) - daha dramatik
    RARITY_FLIP_DURATION = {
        'common': 0.40,
        'uncommon': 0.50,
        'rare': 0.60,
        'epic': 0.75,
        'legendary': 0.90,
    }

    # Nadirlik bazlı kart açılma gecikmesi
    # Sıradan İLK döner → Efsanevi EN SON döner (heyecan artar!)
    RARITY_FLIP_BASE_DELAY = {
        'common': 0.15,
        'uncommon': 0.55,
        'rare': 0.95,
        'epic': 1.40,
        'legendary': 1.90,
    }

    _EPIC_SCROLL_IMAGE: pygame.Surface | None = None
    _EPIC_SCROLL_IMAGE_LOADED = False
    _EPIC_SCROLL_SPEED_PX_PER_SEC = 22.0
    _EPIC_SCROLL_ALPHA_HOVER = 155
    _EPIC_SCROLL_ALPHA_IDLE = 130
    _COMMON_SCROLL_IMAGE: pygame.Surface | None = None
    _COMMON_SCROLL_IMAGE_LOADED = False
    _COMMON_SCROLL_SPEED_PX_PER_SEC = 18.0
    _COMMON_SCROLL_ALPHA_HOVER = 150
    _COMMON_SCROLL_ALPHA_IDLE = 130
    _RARE_SCROLL_IMAGE: pygame.Surface | None = None
    _RARE_SCROLL_IMAGE_LOADED = False
    _RARE_SCROLL_SPEED_PX_PER_SEC = 18.0
    _RARE_SCROLL_ALPHA_HOVER = 150
    _RARE_SCROLL_ALPHA_IDLE = 130
    _UNCOMMON_SCROLL_IMAGE: pygame.Surface | None = None
    _UNCOMMON_SCROLL_IMAGE_LOADED = False
    _UNCOMMON_SCROLL_SPEED_PX_PER_SEC = 18.0
    _UNCOMMON_SCROLL_ALPHA_HOVER = 150
    _UNCOMMON_SCROLL_ALPHA_IDLE = 130

    @staticmethod
    def _mix_rgb(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
        tt = max(0.0, min(1.0, float(t)))
        return (
            int(a[0] + (b[0] - a[0]) * tt),
            int(a[1] + (b[1] - a[1]) * tt),
            int(a[2] + (b[2] - a[2]) * tt),
        )

    @staticmethod
    def _blit_shadowed(surface: pygame.Surface, text: pygame.Surface, pos: tuple[int, int], *, shadow_alpha: int = 160) -> None:
        shadow = text.copy()
        shadow.fill((0, 0, 0, 255), special_flags=pygame.BLEND_RGBA_MULT)
        shadow.set_alpha(max(0, min(255, shadow_alpha)))
        surface.blit(shadow, (pos[0] + 1, pos[1] + 1))
        surface.blit(text, pos)

    @staticmethod
    def _match_hover_corner(base_corner: int, width: int, height: int) -> int:
        """Kart görsel köşelerini hover ovalliğiyle hizala (corner + 8)."""
        c = max(8, int(base_corner) + 8)
        return min(c, max(8, min(int(width), int(height)) // 2))

    def _get_card_face_image(self, face: str, size: tuple[int, int]) -> pygame.Surface | None:
        """Kart PNG arka/ön yüzünü yükle (assets/cards)."""
        rarity = self._get_rarity()
        filename = f"{rarity}_{face}.png"
        path = os.path.join(CARD_ASSET_DIR, filename)
        try:
            return load_image(path, convert_alpha=True, size=size)
        except Exception:
            return None

    def __init__(self, card: Dict, rect: pygame.Rect, idx: int, fonts: Dict[str, pygame.font.Font], icon_getter, reveal_sfx_callback=None):
        self.card = card
        self.base_rect = rect
        self.index = idx
        self.fonts = fonts
        self.icon_getter = icon_getter
        self._reveal_sfx_callback = reveal_sfx_callback
        self.rect = rect.copy()
        self.hover = False
        self.scale = 1.0
        self.target_scale = 1.0
        self.pulse = 0.0

        # --- Kart Dönme Animasyonu ---
        rarity = self._get_rarity()
        self.flip_duration = self.RARITY_FLIP_DURATION.get(rarity, 0.5)
        # Delay: nadirlik bazlı + küçük index offset (aynı nadirlik aynı anda dönmesin)
        self.flip_delay = self.RARITY_FLIP_BASE_DELAY.get(rarity, 0.3) + self.index * 0.08
        self.flip_timer = 0.0  # elapsed time since card selection opened
        self.flip_progress = 0.0  # 0.0 = face down, 1.0 = face up
        self.is_revealed = False  # True after flip completes fully
        self.reveal_burst_done = False  # True after reveal burst particles spawned
        self._flip_sfx_played = False

        # --- Giriş Animasyonu ---
        self.entry_progress = 0.0  # 0→1, aşağıdan yukarı slide
        self.entry_duration = 0.35 + self.index * 0.1  # Sıralı giriş
        self.entry_done = False
        self.entry_offset_y = 80  # Başlangıç offset (aşağıdan gelir)

        # --- Açılış Sonrası Efekt Parçacıkları ---
        self.rarity_particles: List[Dict] = []
        self._continuous_particle_timer = 0.0
        self._continuous_particle_interval = self._get_particle_interval(rarity)

        # --- Legendary alev formu için sabit tohumlar ---
        seed_source = sum(ord(c) for c in str(self.card.get('id', ''))) + self.index * 131
        rng = random.Random(seed_source)
        self._flame_seeds = [
            {
                'x': rng.random(),
                'phase': rng.random() * math.pi * 2,
                'amp': rng.uniform(0.7, 1.1),
                'w': rng.uniform(0.10, 0.22),
            }
            for _ in range(7)
        ]

        # --- Reveal shake (legendary/epic için) ---
        self._shake_timer = 0.0
        self._shake_intensity = 0.0
        self._epic_sheet_time = 0.0

        # --- Baked Face Cache (statik kart yüzünü tek seferde çiz) ---
        self._baked_face_bg: pygame.Surface | None = None
        self._baked_face_fg: pygame.Surface | None = None
        self._baked_face_key: tuple | None = None

        # --- Shimmer Pre-compute Cache ---
        self._shimmer_band: pygame.Surface | None = None
        self._shimmer_mask: pygame.Surface | None = None
        self._shimmer_work: pygame.Surface | None = None
        self._shimmer_w: int = 0
        self._shimmer_cache_key: tuple | None = None
        self._scroll_scaled_cache: dict[str, tuple[tuple[int, int, int], pygame.Surface]] = {}

    def update(self, dt: float, mouse_pos: tuple[int, int] | None):
        # dt gelebilir: ms (oyun döngüsünden) veya saniye. Tutarlı dönüşüm.
        seconds = _dt_to_seconds(dt)

        # --- Giriş Animasyonu (aşağıdan yukarı slide) ---
        if not self.entry_done:
            self.entry_progress += seconds / self.entry_duration
            if self.entry_progress >= 1.0:
                self.entry_progress = 1.0
                self.entry_done = True

        # --- Kart Dönme Animasyonu ---
        self.flip_timer += seconds
        if self.flip_timer >= self.flip_delay and self.entry_done:
            if not self._flip_sfx_played:
                self._flip_sfx_played = True
                if self._reveal_sfx_callback:
                    try:
                        self._reveal_sfx_callback()
                    except Exception:
                        pass
            elapsed_in_flip = self.flip_timer - self.flip_delay
            raw_progress = min(1.0, elapsed_in_flip / self.flip_duration)
            # Ease-out expo: hızlı başla yavaşça bitir
            self.flip_progress = 1.0 - (1.0 - raw_progress) ** 2.5

            if self.flip_progress >= 0.99:
                self.flip_progress = 1.0
                if not self.is_revealed:
                    self.is_revealed = True
                    # Reveal anında shake başlat (epic/legendary)
                    rarity = self._get_rarity()
                    if rarity == 'legendary':
                        self._shake_intensity = 6.0
                        self._shake_timer = 0.4
        else:
            self.flip_progress = 0.0

        # --- Shake güncelleme ---
        if self._shake_timer > 0:
            self._shake_timer -= seconds
            if self._shake_timer <= 0:
                self._shake_timer = 0
                self._shake_intensity = 0

        # --- Hover ve Scale ---
        if self.is_revealed:
            if mouse_pos and self.base_rect.collidepoint(mouse_pos):
                self.hover = True
                self.target_scale = 1.06
            else:
                self.hover = False
                self.target_scale = 1.0
        else:
            self.hover = False
            self.target_scale = 1.0

        t = min(1.0, seconds * 12.0)
        self.scale += (self.target_scale - self.scale) * t
        self.pulse = (self.pulse + seconds * 3.5) % (2 * math.pi)

        # --- Sürekli Parçacık ---
        if self.is_revealed:
            if self._get_rarity() in ('epic', 'rare', 'uncommon', 'common'):
                self._epic_sheet_time += seconds
            rarity = self._get_rarity()
            if rarity == 'legendary':
                self._continuous_particle_timer += seconds
                if self._continuous_particle_timer >= self._continuous_particle_interval:
                    self._continuous_particle_timer = 0.0
                    self._spawn_continuous_particles(rarity)
        elif self._get_rarity() in ('epic', 'rare', 'uncommon', 'common'):
            self._epic_sheet_time = 0.0

        if self._get_rarity() == 'legendary':
            self._update_particles(seconds)

    def _get_rarity(self) -> str:
        """Kartın nadirlik seviyesini döndürür."""
        rarity = str(self.card.get('rarity', '')).lower()
        if rarity in ('legendary', 'epic', 'rare', 'uncommon', 'common'):
            return rarity
        tag = str(self.card.get('tag', '')).lower()
        if 'legend' in tag:
            return 'legendary'
        if 'epic' in tag:
            return 'epic'
        if 'rare' in tag:
            return 'rare'
        if 'uncommon' in tag:
            return 'uncommon'
        return 'common'

    def _get_particle_interval(self, rarity: str) -> float:
        """Nadirliğe göre sürekli parçacık oluşturma aralığı."""
        return {
            'legendary': 0.05,
            'epic': 0.06,
            'rare': 0.10,
            'uncommon': 0.16,
            'common': 0.25,
        }.get(rarity, 0.2)

    def rarity_color(self):
        rarity = self._get_rarity()
        return self.RARITY_COLORS.get(rarity, self.RARITY_COLORS['common'])

    # ==================== PARÇACIK SİSTEMİ (Gelişmiş) ====================

    def _spawn_reveal_burst(self, rarity: str) -> None:
        """Kart açılma anında patlama efekti - daha az parçacık,
        daha büyük ve yumuşak glow blob'larla profesyonel görünüm."""
        if rarity == 'legendary':
            return
        cx = self.base_rect.centerx
        cy = self.base_rect.centery

        burst_configs = {
            'legendary': {'count': 30, 'speed': 280, 'size_range': (4, 12), 'life': 1.4, 'glow': True,
                          'trail': True, 'ring': True,
                          'colors': [(255, 220, 80), (255, 190, 40), (255, 255, 180)]},
            'epic':      {'count': 22, 'speed': 230, 'size_range': (3, 10), 'life': 1.1, 'glow': True,
                          'trail': True, 'ring': True,
                          'colors': [(210, 110, 255), (180, 70, 255), (240, 180, 255)]},
            'rare':      {'count': 16, 'speed': 180, 'size_range': (3, 8), 'life': 0.9, 'glow': True,
                          'trail': False, 'ring': True,
                          'colors': [(80, 180, 255), (130, 210, 255), (190, 230, 255)]},
            'uncommon':  {'count': 10, 'speed': 130, 'size_range': (2, 6), 'life': 0.7, 'glow': True,
                          'trail': False, 'ring': False,
                          'colors': [(100, 230, 150), (140, 255, 185)]},
            'common':    {'count': 6, 'speed': 90, 'size_range': (2, 4), 'life': 0.4, 'glow': True,
                          'trail': False, 'ring': False,
                          'colors': [(190, 195, 210), (210, 215, 225)]},
        }
        cfg = burst_configs.get(rarity, burst_configs['common'])

        # Ana patlama parçacıkları
        for _ in range(cfg['count']):
            angle = random.uniform(0, 2 * math.pi)
            speed = random.uniform(cfg['speed'] * 0.25, cfg['speed'])
            size = random.uniform(cfg['size_range'][0], cfg['size_range'][1])
            color = random.choice(cfg['colors'])
            life = random.uniform(cfg['life'] * 0.5, cfg['life'])
            self.rarity_particles.append({
                'x': cx + random.uniform(-5, 5),
                'y': cy + random.uniform(-5, 5),
                'vx': math.cos(angle) * speed,
                'vy': math.sin(angle) * speed,
                'size': size, 'max_size': size,
                'life': life, 'max_life': life,
                'color': color, 'glow': cfg['glow'],
                'trail': cfg.get('trail', False),
                'trail_positions': [], 'type': 'burst',
            })

        # Halka efekti (düzgün dağılımlı ring)
        if cfg.get('ring'):
            ring_count = 18 if rarity == 'legendary' else 12
            for i in range(ring_count):
                angle = (2 * math.pi / ring_count) * i
                speed = cfg['speed'] * 0.6
                self.rarity_particles.append({
                    'x': cx, 'y': cy,
                    'vx': math.cos(angle) * speed,
                    'vy': math.sin(angle) * speed,
                    'size': 3.0, 'max_size': 3.0,
                    'life': 0.7, 'max_life': 0.7,
                    'color': cfg['colors'][0], 'glow': True,
                    'trail': True, 'trail_positions': [], 'type': 'ring',
                })

        # Legendary: altın yıldız kıvılcımları (lens flare kuyruğu ile)
        if rarity == 'legendary':
            for _ in range(5):
                angle = random.uniform(0, 2 * math.pi)
                speed = random.uniform(40, 120)
                self.rarity_particles.append({
                    'x': cx, 'y': cy,
                    'vx': math.cos(angle) * speed,
                    'vy': math.sin(angle) * speed - 30,
                    'size': random.uniform(5, 9),
                    'max_size': 9,
                    'life': 1.6, 'max_life': 1.6,
                    'color': (255, 255, 200),
                    'glow': True, 'trail': True,
                    'trail_positions': [], 'type': 'star',
                })

    def _spawn_continuous_particles(self, rarity: str) -> None:
        """Kart açıldıktan sonra sürekli profesyonel kalite efektler.
        Daha az parçacık ama daha büyük ve yumuşak glow blob'larla
        Balatro/Hearthstone tarzı temiz görünüm."""
        rect = self.base_rect

        if rarity == 'legendary':
            # --- Yukarı fırlayan üçgen/dalga alevleri ---
            for _ in range(2):
                x = rect.x + random.uniform(14, rect.width - 14)
                y = rect.bottom + random.uniform(-3, 3)
                height = random.uniform(18, 32)
                width = random.uniform(8, 16)
                self.rarity_particles.append({
                    'x': x, 'y': y,
                    'vx': random.uniform(-8, 8),
                    'vy': random.uniform(-130, -90),
                    'size': random.uniform(3.0, 5.0),
                    'max_size': 5.0,
                    'life': random.uniform(0.6, 0.9),
                    'max_life': 0.9,
                    'color': random.choice([(255, 170, 60), (255, 130, 45), (255, 210, 120)]),
                    'glow': True, 'trail': False, 'trail_positions': [],
                    'type': 'flame_spike',
                    'height': height,
                    'width': width,
                    'phase': random.uniform(0, math.pi * 2),
                })
            # Küçük sıcak merkez parçacıkları (daha parlak, daha az)
            if random.random() < 0.25:
                x = rect.x + random.uniform(18, rect.width - 18)
                y = rect.bottom + random.uniform(-2, 2)
                self.rarity_particles.append({
                    'x': x, 'y': y,
                    'vx': random.uniform(-10, 10),
                    'vy': random.uniform(-120, -70),
                    'size': random.uniform(1.8, 2.8),
                    'max_size': 2.8,
                    'life': random.uniform(0.4, 0.6),
                    'max_life': 0.6,
                    'color': (255, 235, 200),
                    'glow': True, 'trail': False, 'trail_positions': [],
                    'type': 'flame_core',
                })
            # Yavaşça yükselen kıvılcım (kenarlardan, az)
            if random.random() < 0.2:
                side_x = random.choice([rect.left - 3, rect.right + 3])
                y = rect.y + random.uniform(rect.height * 0.3, rect.height)
                self.rarity_particles.append({
                    'x': side_x, 'y': y,
                    'vx': random.uniform(-4, 4),
                    'vy': random.uniform(-45, -22),
                    'size': random.uniform(1.6, 2.6),
                    'max_size': 2.6,
                    'life': random.uniform(0.5, 0.85),
                    'max_life': 0.85,
                    'color': random.choice([(255, 180, 70), (255, 210, 130)]),
                    'glow': True, 'trail': False, 'trail_positions': [],
                    'type': 'ember',
                })

        elif rarity == 'epic':
            # --- Mor enerji yay (kartın etrafında dönen) ---
            angle = self.pulse * 2.0 + random.uniform(-0.2, 0.2)
            rx = rect.width * 0.52
            ry = rect.height * 0.52
            ox = rect.centerx + math.cos(angle) * rx
            oy = rect.centery + math.sin(angle) * ry * 0.65
            self.rarity_particles.append({
                'x': ox, 'y': oy,
                'vx': random.uniform(-6, 6),
                'vy': random.uniform(-6, 6),
                'size': random.uniform(3, 6),
                'max_size': 6,
                'life': random.uniform(0.6, 1.0),
                'max_life': 1.0,
                'color': random.choice([(200, 100, 255), (170, 60, 255), (230, 140, 255)]),
                'glow': True, 'trail': True, 'trail_positions': [],
                'type': 'orbit',
            })
            # Kenardan çıkan kıvılcım
            if random.random() < 0.25:
                is_h = random.random() < 0.5
                if is_h:
                    x = random.choice([rect.left, rect.right])
                    y = rect.y + random.uniform(10, rect.height - 10)
                else:
                    x = rect.x + random.uniform(10, rect.width - 10)
                    y = random.choice([rect.top, rect.bottom])
                self.rarity_particles.append({
                    'x': x, 'y': y,
                    'vx': random.uniform(-20, 20),
                    'vy': random.uniform(-30, -10),
                    'size': random.uniform(2, 4),
                    'max_size': 4,
                    'life': 0.5,
                    'max_life': 0.5,
                    'color': (240, 180, 255),
                    'glow': True, 'trail': False, 'trail_positions': [],
                    'type': 'energy_spark',
                })

        elif rarity == 'rare':
            # --- Mavi kristal parıltı (yumuşak, yüzen noktalar) ---
            x = rect.x + random.uniform(5, rect.width - 5)
            y = rect.bottom + random.uniform(-5, 5)
            self.rarity_particles.append({
                'x': x, 'y': y,
                'vx': random.uniform(-10, 10),
                'vy': random.uniform(-45, -18),
                'size': random.uniform(2, 5),
                'max_size': 5,
                'life': random.uniform(0.6, 1.0),
                'max_life': 1.0,
                'color': random.choice([(80, 170, 255), (120, 200, 255), (170, 220, 255)]),
                'glow': True, 'trail': False, 'trail_positions': [],
                'type': 'crystal',
            })

        elif rarity == 'uncommon':
            # --- Yeşil yumuşak ışık noktaları ---
            if random.random() < 0.5:
                x = rect.x + random.uniform(8, rect.width - 8)
                y = rect.y + random.uniform(8, rect.height - 8)
                self.rarity_particles.append({
                    'x': x, 'y': y,
                    'vx': random.uniform(-5, 5),
                    'vy': random.uniform(-20, -8),
                    'size': random.uniform(2, 4),
                    'max_size': 4,
                    'life': random.uniform(0.5, 0.8),
                    'max_life': 0.8,
                    'color': random.choice([(100, 220, 150), (130, 250, 180)]),
                    'glow': True, 'trail': False, 'trail_positions': [],
                    'type': 'nature_glow',
                })

        else:  # common
            # --- Çok hafif toz (az ve zarif) ---
            if random.random() < 0.25:
                x = rect.x + random.uniform(15, rect.width - 15)
                y = rect.y + random.uniform(15, rect.height - 15)
                self.rarity_particles.append({
                    'x': x, 'y': y,
                    'vx': random.uniform(-3, 3),
                    'vy': random.uniform(-10, -3),
                    'size': random.uniform(1, 2.5),
                    'max_size': 2.5,
                    'life': 0.5,
                    'max_life': 0.5,
                    'color': (190, 190, 205),
                    'glow': False, 'trail': False, 'trail_positions': [],
                    'type': 'dust',
                })

    def _update_particles(self, dt: float) -> None:
        """Gelişmiş parçacık fiziği - iz bırakma, türe göre davranış."""
        to_remove = []
        for i, p in enumerate(self.rarity_particles):
            # İz kaydet (trail parçacıkları için)
            if p.get('trail'):
                trail = p.get('trail_positions', [])
                trail.append((p['x'], p['y'], p['size']))
                if len(trail) > 8:
                    trail.pop(0)
                p['trail_positions'] = trail

            p['x'] += p['vx'] * dt
            p['y'] += p['vy'] * dt
            p['life'] -= dt

            ptype = p.get('type', 'burst')
            if ptype in ('fire', 'fire_inner', 'flame_tongue', 'flame_core', 'flame_spike'):
                # Alev: yukarı hareket, yanlara salınım
                p['vy'] -= 26 * dt
                p['vx'] += math.sin(p['life'] * 10) * 12 * dt
                # Boyut: başta büyük, sonra küçülür
                ratio = max(0, p['life'] / p['max_life'])
                flicker = 0.9 + 0.2 * math.sin(p['life'] * 18)
                p['size'] = p['max_size'] * (0.3 + 0.7 * ratio) * flicker
            elif ptype == 'orbit':
                # Orbit: merkeze doğru hafif çekim
                p['vy'] += 8 * dt
            elif ptype == 'star':
                # Yıldız: yavaş düşüş, yanıp sönme
                p['vy'] += 15 * dt
                p['vx'] *= (1.0 - 1.0 * dt)
            elif ptype == 'ember':
                # Kor: yukarı + hafif yerçekimi
                p['vy'] += 20 * dt
                p['vx'] *= (1.0 - 1.5 * dt)
            elif ptype == 'crystal':
                # Kristal: yukarı + hafif salınım
                p['vx'] += math.sin(p['life'] * 10) * 8 * dt
            elif ptype == 'nature_glow':
                # Doğa: yavaş yüzen
                p['vx'] += math.sin(p['life'] * 6) * 5 * dt
                p['vy'] -= 5 * dt
            elif ptype in ('burst', 'ring'):
                # Patlama: hızlı yavaşlama + hafif yerçekimi
                p['vx'] *= (1.0 - 3.0 * dt)
                p['vy'] *= (1.0 - 3.0 * dt)
                p['vy'] += 40 * dt
                ratio = max(0, p['life'] / p['max_life'])
                p['size'] = p.get('max_size', p['size']) * (0.2 + 0.8 * ratio)
            else:
                # Varsayılan: hafif yerçekimi + yavaşlama
                p['vy'] += 30 * dt
                p['vx'] *= (1.0 - 2.0 * dt)

            if p['life'] <= 0:
                to_remove.append(i)

        for i in reversed(to_remove):
            self.rarity_particles.pop(i)

    def _draw_particles(self, surface: pygame.Surface, *, offset: tuple[int, int] = (0, 0),
                        only_types: set[str] | None = None, exclude_types: set[str] | None = None) -> None:
        """Profesyonel parçacık çizimi - yumuşak radyal gradyan glow blob'lar.
        Sert kenarlı daireler yerine önceden işlenmiş Gaussian gradyan kullanır.
        Teknik: Balatro/Hearthstone tarzı soft-particle rendering."""
        for p in self.rarity_particles:
            alpha_ratio = max(0, p['life'] / p['max_life'])
            color = p['color']
            ptype = p.get('type', 'burst')
            if only_types is not None and ptype not in only_types:
                continue
            if exclude_types is not None and ptype in exclude_types:
                continue
            x = int(p['x'] - offset[0])
            y = int(p['y'] - offset[1])
            size = max(0.5, p['size'])

            # --- Trail (iz) çizimi - yumuşak gradyan ile ---
            if p.get('trail') and p.get('trail_positions'):
                trail = p['trail_positions']
                trail_len = len(trail)
                for ti, (tx, ty, ts) in enumerate(trail):
                    t_ratio = (ti + 1) / trail_len
                    t_alpha = t_ratio * alpha_ratio * 0.35
                    t_radius = max(2, int(ts * t_ratio * 1.2))
                    if t_alpha > 0.02:
                        glow = _GlowCache.get_tinted(t_radius, color, t_alpha)
                        surface.blit(glow, (int(tx - offset[0]) - t_radius, int(ty - offset[1]) - t_radius),
                                     special_flags=pygame.BLEND_RGBA_ADD)

            # --- Dış glow katmanı (büyük, yumuşak, atmosferik) ---
            if p.get('glow') and size > 1:
                is_flame = ptype in ('fire', 'fire_inner', 'flame_tongue', 'flame_core', 'flame_spike')
                outer_r = max(3, int(size * (2.6 if is_flame else 3.5)))
                outer_alpha = alpha_ratio * (0.12 if is_flame else 0.2)
                if outer_alpha > 0.015:
                    outer = _GlowCache.get_tinted(outer_r, color, outer_alpha)
                    surface.blit(outer, (x - outer_r, y - outer_r),
                                 special_flags=pygame.BLEND_RGBA_ADD)

            # --- Üçgen/dalga alev çizimi ---
            if ptype == 'flame_spike':
                ratio = max(0, p['life'] / p['max_life'])
                h = p.get('height', 24) * (0.35 + 0.65 * ratio)
                w = p.get('width', 12) * (0.40 + 0.60 * ratio)
                sway = math.sin(self.pulse * 2.6 + p.get('phase', 0.0)) * 7
                wobble = math.sin(self.pulse * 4.4 + p.get('phase', 0.0)) * 3
                base_y = y + int(h * 0.55)
                tip_y = y - int(h * 0.55)
                mid_y = y - int(h * 0.1)
                a = int(110 * alpha_ratio)
                outer_col = self._mix_rgb((255, 90, 30), (255, 160, 70), 0.35 + 0.4 * ratio)
                inner_col = self._mix_rgb((255, 180, 90), (255, 235, 170), 0.45 + 0.4 * ratio)
                outer = [
                    (int(x - w + sway), base_y),
                    (int(x + w + sway), base_y),
                    (int(x + w * 0.55 + sway + wobble), mid_y),
                    (int(x + sway * 0.6), tip_y),
                    (int(x - w * 0.55 + sway - wobble), mid_y),
                ]
                pygame.draw.polygon(surface, (*outer_col, a), outer)
                inner = [
                    (int(x - w * 0.45 + sway), base_y),
                    (int(x + w * 0.45 + sway), base_y),
                    (int(x + w * 0.2 + sway + wobble), mid_y),
                    (int(x + sway * 0.4), tip_y + int(h * 0.2)),
                    (int(x - w * 0.2 + sway - wobble), mid_y),
                ]
                pygame.draw.polygon(surface, (*inner_col, int(a * 0.75)), inner)

            # --- Yıldız: 4-ışın lens flare efekti ---
            if ptype == 'star' and size > 2:
                star_alpha = max(0, min(255, int(alpha_ratio * 140)))
                ray_len = int(size * 3)
                # Her ışın için ince gradyan çizgi
                for angle_offset in [0, math.pi / 2]:
                    for thickness in [3, 1]:
                        dx = math.cos(angle_offset) * ray_len
                        dy = math.sin(angle_offset) * ray_len
                        surf_w = int(abs(dx) * 2) + 6
                        surf_h = int(abs(dy) * 2) + 6
                        sc = max(surf_w, surf_h)
                        ray_surf = pygame.Surface((sc, sc), pygame.SRCALPHA)
                        cx2, cy2 = sc // 2, sc // 2
                        a = max(0, min(255, int(star_alpha * (0.4 if thickness == 3 else 1.0))))
                        pygame.draw.line(ray_surf, (*color[:3], a),
                                         (cx2 - int(dx), cy2 - int(dy)),
                                         (cx2 + int(dx), cy2 + int(dy)), thickness)
                        surface.blit(ray_surf, (x - sc // 2, y - sc // 2),
                                     special_flags=pygame.BLEND_RGBA_ADD)

            # --- İç glow + çekirdek: tek yumuşak blob ---
            core_r = max(2, int(size * 1.5))
            # Çekirdeğe yakın parlaklık daha yüksek
            core_alpha = min(1.0, alpha_ratio ** 0.5 * 0.9)
            if core_alpha > 0.02:
                core = _GlowCache.get_tinted(core_r, color, core_alpha)
                surface.blit(core, (x - core_r, y - core_r),
                             special_flags=pygame.BLEND_RGBA_ADD)

            # --- Alev parçacıkları: ekstra sıcak merkez (beyaza yakın) ---
            if ptype in ('fire', 'fire_inner', 'flame_tongue', 'flame_core') and size > 1.5:
                hot_r = max(2, int(size * 0.7))
                hot_color = (255, 255, 240)  # beyaza yakın = çok sıcak
                hot_alpha = alpha_ratio ** 0.7 * 0.35
                if hot_alpha > 0.03:
                    hot = _GlowCache.get_tinted(hot_r, hot_color, hot_alpha)
                    surface.blit(hot, (x - hot_r, y - hot_r),
                                 special_flags=pygame.BLEND_RGBA_ADD)

    def _draw_legendary_flame_base(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
        """Legendary kart tabanında yumuşak alev bandı."""
        band_h = max(22, int(rect.height * 0.20))
        flame = pygame.Surface((rect.width, band_h), pygame.SRCALPHA)

        # Alev dilleri (şekli ateşe benzeten ana form)
        pulse = self.pulse
        for seed in self._flame_seeds:
            base_x = int(seed['x'] * rect.width)
            sway = math.sin(pulse * 2.0 + seed['phase']) * 8
            height = band_h * (0.55 + 0.35 * math.sin(pulse * 1.8 + seed['phase'])) * seed['amp']
            width = max(10, int(rect.width * seed['w']))
            tip_y = max(4, int(band_h - height))
            mid_y = int((band_h + tip_y) * 0.5)

            # Dış alev
            outer_color = (255, 110, 40, 130)
            outer = [
                (base_x - width, band_h - 1),
                (base_x + width, band_h - 1),
                (base_x + int(width * 0.45) + int(sway), mid_y),
                (base_x + int(sway * 0.6), tip_y),
                (base_x - int(width * 0.45) + int(sway), mid_y),
            ]
            pygame.draw.polygon(flame, outer_color, outer)

            # İç alev (daha sıcak)
            inner_w = int(width * 0.55)
            inner_tip = max(2, int(tip_y + (band_h - tip_y) * 0.25))
            inner_color = (255, 210, 120, 150)
            inner = [
                (base_x - inner_w, band_h - 2),
                (base_x + inner_w, band_h - 2),
                (base_x + int(inner_w * 0.35) + int(sway * 0.6), int((band_h + inner_tip) * 0.55)),
                (base_x + int(sway * 0.4), inner_tip),
                (base_x - int(inner_w * 0.35) + int(sway * 0.6), int((band_h + inner_tip) * 0.55)),
            ]
            pygame.draw.polygon(flame, inner_color, inner)

            # Uç parıltısı
            tip_r = max(3, int(width * 0.18))
            glow = _GlowCache.get_tinted(tip_r, (255, 210, 120), 0.35)
            flame.blit(glow, (base_x - tip_r, tip_y - tip_r), special_flags=pygame.BLEND_RGBA_ADD)

        # Taban glow'ları (alev kümeleri)
        pulse2 = (math.sin(self.pulse * 4.2) + 1.0) * 0.5
        for i in range(6):
            px = int((i + 0.5) / 6 * rect.width + math.sin(self.pulse * 1.6 + i) * 6)
            r = int(10 + 7 * pulse2 + (i % 2) * 2)
            glow = _GlowCache.get_tinted(r, (255, 150, 50), 0.28 + 0.12 * pulse2)
            flame.blit(glow, (px - r, band_h - r - 2), special_flags=pygame.BLEND_RGBA_ADD)

        surface.blit(flame, (rect.x, rect.bottom - band_h), special_flags=pygame.BLEND_RGBA_ADD)

    @classmethod
    def _get_epic_scroll_image(cls) -> pygame.Surface | None:
        """Epic kaydırmalı efekt görselini yükle (tek PNG)."""
        if cls._EPIC_SCROLL_IMAGE_LOADED:
            return cls._EPIC_SCROLL_IMAGE

        path = os.path.join(CARD_EFFECTS_DIR, 'epic_effect.png')
        try:
            if os.path.exists(path):
                epic_img = load_image(path, convert_alpha=True)
                epic_img.set_colorkey((0, 0, 0))
                cls._EPIC_SCROLL_IMAGE = epic_img
            else:
                cls._EPIC_SCROLL_IMAGE = None
        except Exception:
            cls._EPIC_SCROLL_IMAGE = None

        cls._EPIC_SCROLL_IMAGE_LOADED = True
        return cls._EPIC_SCROLL_IMAGE

    @classmethod
    def _get_common_scroll_image(cls) -> pygame.Surface | None:
        """Eski epic yıldız kaydırmalı görseli common rarity için yükle."""
        if cls._COMMON_SCROLL_IMAGE_LOADED:
            return cls._COMMON_SCROLL_IMAGE

        path = os.path.join(CARD_EFFECTS_DIR, 'deneme_epicv2.png')
        try:
            if os.path.exists(path):
                common_img = load_image(path, convert_alpha=True)
                common_img.set_colorkey((0, 0, 0))
                cls._COMMON_SCROLL_IMAGE = common_img
            else:
                cls._COMMON_SCROLL_IMAGE = None
        except Exception:
            cls._COMMON_SCROLL_IMAGE = None

        cls._COMMON_SCROLL_IMAGE_LOADED = True
        return cls._COMMON_SCROLL_IMAGE

    def _draw_common_sheet_fx(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
        """Eski epic yıldız sheet efektini common rarity'de kullan."""
        if self._get_rarity() != 'common' or not self.is_revealed:
            return

        base_image = self._get_common_scroll_image()
        if base_image is None:
            return

        target_w = max(1, int(rect.width * 1.05))
        target_h = max(1, int(rect.height * 1.05))
        scaled = self._get_scaled_scroll_surface('common', base_image, target_w, target_h)

        scroll_y = int((self._epic_sheet_time * self._COMMON_SCROLL_SPEED_PX_PER_SEC) % target_h)
        fx = pygame.Surface((target_w, target_h), pygame.SRCALPHA)
        fx.blit(scaled, (0, scroll_y - target_h))
        fx.blit(scaled, (0, scroll_y))

        fx.set_alpha(self._COMMON_SCROLL_ALPHA_HOVER if self.hover else self._COMMON_SCROLL_ALPHA_IDLE)
        fx_rect = fx.get_rect(center=rect.center)

        clip_corner = self._match_hover_corner(int(self.card.get('style', {}).get('corner', 15) or 15), rect.width, rect.height)
        clip = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        clip.blit(fx, (rect.x - fx_rect.x, rect.y - fx_rect.y))
        mask = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        pygame.draw.rect(mask, (255, 255, 255, 255), mask.get_rect(), border_radius=clip_corner)
        clip.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        surface.blit(clip, rect.topleft)

    def _draw_epic_sheet_fx(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
        """Epic rarity için PNG overlay'i yukarıdan aşağı sonsuz döngüyle çizer."""
        if self._get_rarity() != 'epic' or not self.is_revealed:
            return

        base_image = self._get_epic_scroll_image()
        if base_image is None:
            return

        target_w = max(1, int(rect.width * 1.05))
        target_h = max(1, int(rect.height * 1.05))
        scaled = self._get_scaled_scroll_surface('epic', base_image, target_w, target_h)

        scroll_y = int((self._epic_sheet_time * self._EPIC_SCROLL_SPEED_PX_PER_SEC) % target_h)
        fx = pygame.Surface((target_w, target_h), pygame.SRCALPHA)
        fx.blit(scaled, (0, scroll_y - target_h))
        fx.blit(scaled, (0, scroll_y))
        fx.set_alpha(self._EPIC_SCROLL_ALPHA_HOVER if self.hover else self._EPIC_SCROLL_ALPHA_IDLE)

        fx_rect = fx.get_rect(center=rect.center)

        clip_corner = self._match_hover_corner(int(self.card.get('style', {}).get('corner', 15) or 15), rect.width, rect.height)
        clip = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        crop_x = max(0, (target_w - rect.width) // 2)
        crop_y = max(0, (target_h - rect.height) // 2)
        clip.blit(fx, (-crop_x, -crop_y))
        mask = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        pygame.draw.rect(mask, (255, 255, 255, 255), mask.get_rect(), border_radius=clip_corner)
        clip.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        surface.blit(clip, rect.topleft)

    def _get_scaled_scroll_surface(self, rarity_key: str, base_image: pygame.Surface, target_w: int, target_h: int) -> pygame.Surface:
        cache_key = (id(base_image), target_w, target_h)
        cached = self._scroll_scaled_cache.get(rarity_key)
        if cached is not None and cached[0] == cache_key:
            return cached[1]

        try:
            scaled = pygame.transform.smoothscale(base_image, (target_w, target_h))
        except Exception:
            scaled = pygame.transform.scale(base_image, (target_w, target_h))

        self._scroll_scaled_cache[rarity_key] = (cache_key, scaled)
        return scaled

    @classmethod
    def _get_rare_scroll_image(cls) -> pygame.Surface | None:
        """Rare kaydırmalı efekt görselini yükle (tek PNG)."""
        if cls._RARE_SCROLL_IMAGE_LOADED:
            return cls._RARE_SCROLL_IMAGE

        path = os.path.join(CARD_EFFECTS_DIR, 'rare_effect.png')
        try:
            if os.path.exists(path):
                rare_img = load_image(path, convert_alpha=True)
                rare_img.set_colorkey((0, 0, 0))
                cls._RARE_SCROLL_IMAGE = rare_img
            else:
                cls._RARE_SCROLL_IMAGE = None
        except Exception:
            cls._RARE_SCROLL_IMAGE = None

        cls._RARE_SCROLL_IMAGE_LOADED = True
        return cls._RARE_SCROLL_IMAGE

    def _draw_rare_sheet_fx(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
        """Rare rarity için yıldız overlay'ini sağdan sola döngüyle çizer."""
        if self._get_rarity() != 'rare' or not self.is_revealed:
            return

        base_image = self._get_rare_scroll_image()
        if base_image is None:
            return

        target_w = max(1, int(rect.width * 1.05))
        target_h = max(1, int(rect.height * 1.05))
        scaled = self._get_scaled_scroll_surface('rare', base_image, target_w, target_h)

        scroll_x = int((self._epic_sheet_time * self._RARE_SCROLL_SPEED_PX_PER_SEC) % target_w)
        fx = pygame.Surface((target_w, target_h), pygame.SRCALPHA)
        fx.blit(scaled, (-scroll_x, 0))
        fx.blit(scaled, (target_w - scroll_x, 0))

        fx.set_alpha(self._RARE_SCROLL_ALPHA_HOVER if self.hover else self._RARE_SCROLL_ALPHA_IDLE)
        fx_rect = fx.get_rect(center=rect.center)

        clip_corner = self._match_hover_corner(int(self.card.get('style', {}).get('corner', 15) or 15), rect.width, rect.height)
        clip = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        clip.blit(fx, (rect.x - fx_rect.x, rect.y - fx_rect.y))
        mask = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        pygame.draw.rect(mask, (255, 255, 255, 255), mask.get_rect(), border_radius=clip_corner)
        clip.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        surface.blit(clip, rect.topleft)

    @classmethod
    def _get_uncommon_scroll_image(cls) -> pygame.Surface | None:
        """Uncommon kaydırmalı efekt görselini yükle (tek PNG)."""
        if cls._UNCOMMON_SCROLL_IMAGE_LOADED:
            return cls._UNCOMMON_SCROLL_IMAGE

        path = os.path.join(CARD_EFFECTS_DIR, 'uncommon_effect.png')
        try:
            if os.path.exists(path):
                uncommon_img = load_image(path, convert_alpha=True)
                uncommon_img.set_colorkey((0, 0, 0))
                cls._UNCOMMON_SCROLL_IMAGE = uncommon_img
            else:
                cls._UNCOMMON_SCROLL_IMAGE = None
        except Exception:
            cls._UNCOMMON_SCROLL_IMAGE = None

        cls._UNCOMMON_SCROLL_IMAGE_LOADED = True
        return cls._UNCOMMON_SCROLL_IMAGE

    def _draw_uncommon_sheet_fx(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
        """Uncommon rarity için overlay'i yukarıdan aşağı döngüyle çizer."""
        if self._get_rarity() != 'uncommon' or not self.is_revealed:
            return

        base_image = self._get_uncommon_scroll_image()
        if base_image is None:
            return

        target_w = max(1, int(rect.width * 1.05))
        target_h = max(1, int(rect.height * 1.05))
        scaled = self._get_scaled_scroll_surface('uncommon', base_image, target_w, target_h)

        scroll_y = int((self._epic_sheet_time * self._UNCOMMON_SCROLL_SPEED_PX_PER_SEC) % target_h)
        fx = pygame.Surface((target_w, target_h), pygame.SRCALPHA)
        fx.blit(scaled, (0, scroll_y - target_h))
        fx.blit(scaled, (0, scroll_y))

        fx.set_alpha(self._UNCOMMON_SCROLL_ALPHA_HOVER if self.hover else self._UNCOMMON_SCROLL_ALPHA_IDLE)
        fx_rect = fx.get_rect(center=rect.center)

        clip_corner = self._match_hover_corner(int(self.card.get('style', {}).get('corner', 15) or 15), rect.width, rect.height)
        clip = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        crop_x = max(0, (target_w - rect.width) // 2)
        crop_y = max(0, (target_h - rect.height) // 2)
        clip.blit(fx, (-crop_x, -crop_y))
        mask = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        pygame.draw.rect(mask, (255, 255, 255, 255), mask.get_rect(), border_radius=clip_corner)
        clip.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        surface.blit(clip, rect.topleft)

    def _draw_card_back(self, surface: pygame.Surface) -> None:
        """Kartın arka yüzünü çiz - nadirlik rengiyle gizemli tasarım."""
        rarity = self._get_rarity()
        rc = self.rarity_color()
        rect = self.rect

        # PNG kart arka yüzü varsa önce onu kullan
        png_back = self._get_card_face_image("back", (rect.width, rect.height))
        if png_back is not None:
            body = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
            body.blit(png_back, (0, 0))
            base_corner = int(self.card.get('style', {}).get('corner', 15) or 15)
            corner = self._match_hover_corner(base_corner, rect.width, rect.height)
            mask = pygame.Surface(body.get_size(), pygame.SRCALPHA)
            pygame.draw.rect(mask, (255, 255, 255, 255), mask.get_rect(), border_radius=corner)
            body.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)

            pulse_val = (math.sin(self.pulse * 2) + 1.0) * 0.5
            border_alpha = 80 + int(70 * pulse_val)
            pygame.draw.rect(body, (*rc[:3], border_alpha), body.get_rect(), width=2, border_radius=corner)

            surface.blit(body, (rect.x, rect.y))
            return

        body = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)

        # Koyu arka plan gradientı
        dark_top = (15, 15, 35, 240)
        dark_bot = (8, 8, 22, 240)
        self._fill_gradient(body, dark_top, dark_bot)

        # Köşe maskesi
        mask = pygame.Surface(body.get_size(), pygame.SRCALPHA)
        base_corner = int(self.card.get('style', {}).get('corner', 15) or 15)
        corner = self._match_hover_corner(base_corner, rect.width, rect.height)
        pygame.draw.rect(mask, (255, 255, 255, 255), mask.get_rect(), border_radius=corner)
        body.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)

        # Nadirlik renginde kenarlık
        pulse_val = (math.sin(self.pulse * 2) + 1.0) * 0.5
        border_alpha = 100 + int(80 * pulse_val)
        pygame.draw.rect(body, (*rc[:3], border_alpha), body.get_rect(), width=2, border_radius=corner)

        # Merkez soru işareti / gizemli sembol
        cw, ch = rect.width, rect.height
        # İç desen - nadirliğe göre farklı
        pattern_surf = pygame.Surface((cw, ch), pygame.SRCALPHA)

        if rarity == 'legendary':
            # Altın mandala deseni
            cx, cy = cw // 2, ch // 2
            for i in range(6):
                angle = i * math.pi / 3 + self.pulse * 0.5
                r = min(cw, ch) * 0.25
                x2 = cx + math.cos(angle) * r
                y2 = cy + math.sin(angle) * r
                pygame.draw.line(pattern_surf, (*rc[:3], 60), (cx, cy), (int(x2), int(y2)), 2)
                pygame.draw.circle(pattern_surf, (*rc[:3], 80), (int(x2), int(y2)), 4)
            pygame.draw.circle(pattern_surf, (*rc[:3], 50), (cx, cy), int(r * 0.6), 2)
            pygame.draw.circle(pattern_surf, (*rc[:3], 30), (cx, cy), int(r * 0.9), 1)

        elif rarity == 'epic':
            # Mor girdap deseni
            cx, cy = cw // 2, ch // 2
            for i in range(20):
                angle = i * 0.4 + self.pulse * 0.3
                r = 15 + i * 4
                x2 = cx + math.cos(angle) * r
                y2 = cy + math.sin(angle) * r
                alpha = max(20, 80 - i * 3)
                pygame.draw.circle(pattern_surf, (*rc[:3], alpha), (int(x2), int(y2)), 3)

        elif rarity == 'rare':
            # Mavi kristal deseni
            cx, cy = cw // 2, ch // 2
            for i in range(4):
                angle = i * math.pi / 2 + math.pi / 4
                r = min(cw, ch) * 0.2
                points = [
                    (cx, cy - r),
                    (cx + r * 0.3, cy),
                    (cx, cy + r),
                    (cx - r * 0.3, cy),
                ]
                rotated = []
                for px, py in points:
                    dx, dy = px - cx, py - cy
                    rx = dx * math.cos(angle) - dy * math.sin(angle) + cx
                    ry = dx * math.sin(angle) + dy * math.cos(angle) + cy
                    rotated.append((int(rx), int(ry)))
                pygame.draw.polygon(pattern_surf, (*rc[:3], 40), rotated, 1)

        elif rarity == 'uncommon':
            # Yeşil yaprak deseni
            cx, cy = cw // 2, ch // 2
            for i in range(3):
                angle = i * (2 * math.pi / 3) + self.pulse * 0.2
                r = min(cw, ch) * 0.15
                ex = cx + math.cos(angle) * r
                ey = cy + math.sin(angle) * r
                pygame.draw.circle(pattern_surf, (*rc[:3], 40), (int(ex), int(ey)), 8, 1)

        else:  # common
            # Basit ızgara deseni
            for x in range(0, cw, 20):
                pygame.draw.line(pattern_surf, (120, 120, 140, 20), (x, 0), (x, ch), 1)
            for y in range(0, ch, 20):
                pygame.draw.line(pattern_surf, (120, 120, 140, 20), (0, y), (cw, y), 1)

        body.blit(pattern_surf, (0, 0))

        # Büyük soru işareti
        q_font = self.fonts.get('large') or self.fonts.get('card_title')
        q_text = q_font.render("?", True, (*rc[:3],))
        q_alpha_surf = q_text.copy()
        q_alpha_surf.set_alpha(120 + int(60 * pulse_val))
        body.blit(q_alpha_surf, q_alpha_surf.get_rect(center=(cw // 2, ch // 2)))

        surface.blit(body, (rect.x, rect.y))

    def render(self, surface: pygame.Surface, debug: bool = False):
        # --- Giriş animasyonu (aşağıdan yukarı spring) ---
        entry_t = self.entry_progress
        # Ease-out back (overshoot ile yumuşak giriş)
        if entry_t < 1.0:
            s = 1.70158
            t1 = entry_t - 1.0
            entry_ease = t1 * t1 * ((s + 1) * t1 + s) + 1.0
        else:
            entry_ease = 1.0
        entry_y_offset = int(self.entry_offset_y * (1.0 - entry_ease))
        entry_alpha = max(0, min(255, int(255 * min(1.0, entry_t * 2.5))))

        # Compute scaled rect with entry offset
        sw = int(self.base_rect.width * self.scale)
        sh = int(self.base_rect.height * self.scale)
        dx = self.base_rect.centerx - sw // 2
        dy = self.base_rect.centery - sh // 2 + entry_y_offset

        # Shake offset
        shake_ox, shake_oy = 0, 0
        if self._shake_timer > 0 and self._shake_intensity > 0:
            shake_decay = self._shake_timer / 0.4
            intensity = self._shake_intensity * shake_decay
            shake_ox = int(random.uniform(-intensity, intensity))
            shake_oy = int(random.uniform(-intensity, intensity))
            dx += shake_ox
            dy += shake_oy

        self.rect = pygame.Rect(dx, dy, sw, sh)

        style = self.card.get('style', {})
        corner = style.get('corner', 15)
        rc = self.rarity_color()
        rarity = self._get_rarity()

        # Giriş animasyonu opacity
        if entry_alpha < 255 and not self.entry_done:
            # Henüz tam visible değil - erken çık eğer çok şeffaf
            if entry_alpha < 10:
                return

        # ==================== KART DÖNME ANİMASYONU ====================
        if self.flip_progress < 1.0:
            if self.flip_progress <= 0.0:
                # Arka yüzü göster (giriş animasyonuyla)
                temp = pygame.Surface((self.rect.width, self.rect.height), pygame.SRCALPHA)
                old_rect = self.rect
                self.rect = pygame.Rect(0, 0, self.rect.width, self.rect.height)
                self._draw_card_back(temp)
                self.rect = old_rect
                if entry_alpha < 255:
                    temp.set_alpha(entry_alpha)
                surface.blit(temp, (self.rect.x, self.rect.y))
                return

            # Dönme açısı: 0→π
            flip_angle = self.flip_progress * math.pi
            width_scale = abs(math.cos(flip_angle))
            if width_scale < 0.015:
                width_scale = 0.015

            showing_front = self.flip_progress > 0.5

            actual_width = max(3, int(self.rect.width * width_scale))
            # Perspektif: yükseklik hafif uzar daralınca
            height_stretch = 1.0 + (1.0 - width_scale) * 0.04
            actual_height = min(int(self.rect.height * height_stretch), self.rect.height + 20)

            temp_rect = pygame.Rect(0, 0, self.rect.width, self.rect.height)
            temp_surface = pygame.Surface((self.rect.width, self.rect.height), pygame.SRCALPHA)

            if showing_front:
                self._render_card_face(temp_surface, temp_rect, corner, rc, debug)
            else:
                old_rect = self.rect
                self.rect = temp_rect
                self._draw_card_back(temp_surface)
                self.rect = old_rect

            # Sıkıştır
            try:
                squeezed = pygame.transform.smoothscale(temp_surface, (actual_width, actual_height))
            except Exception:
                squeezed = pygame.transform.scale(temp_surface, (actual_width, actual_height))

            if entry_alpha < 255:
                squeezed.set_alpha(entry_alpha)

            # Merkeze hizala
            bx = self.rect.centerx - actual_width // 2
            by = self.rect.centery - actual_height // 2

            # Kenar ışığı efekti (dönme sırasında - yumuşak gradyan)
            edge_intensity = 1.0 - width_scale
            if rarity == 'legendary' and edge_intensity > 0.08:
                # Sol ve sağ kenarda yumuşak glow (3 nokta yeterli)
                bar_glow_r = max(5, int(14 * edge_intensity))
                bar_alpha = edge_intensity * 0.55
                # Üst, orta, alt — 3 blob yeterli, performanslı
                for gy_pct in [0.2, 0.5, 0.8]:
                    gy = int(actual_height * gy_pct)
                    # Merkeze yakınlık
                    center_ratio = 1.0 - abs(gy_pct - 0.5) * 2
                    a = bar_alpha * (0.4 + 0.6 * center_ratio)
                    g = _GlowCache.get_tinted(bar_glow_r, rc[:3], a)
                    surface.blit(g, (bx - bar_glow_r, by + gy - bar_glow_r),
                                 special_flags=pygame.BLEND_RGBA_ADD)
                    surface.blit(g, (bx + actual_width - bar_glow_r, by + gy - bar_glow_r),
                                 special_flags=pygame.BLEND_RGBA_ADD)

            surface.blit(squeezed, (bx, by))

            # Geçiş anı parlama (yumuşak radyal flash)
            if rarity == 'legendary' and 0.42 <= self.flip_progress <= 0.58:
                flash_t = 1.0 - abs(self.flip_progress - 0.5) / 0.08
                flash_t = max(0, min(1, flash_t))
                r_mult = {'legendary': 1.5, 'epic': 1.3, 'rare': 1.0, 'uncommon': 0.7, 'common': 0.4}
                flash_alpha = flash_t * r_mult.get(rarity, 0.6) * 0.5
                if flash_alpha > 0.03:
                    flash_r = max(self.rect.width, self.rect.height) // 2 + 20
                    flash_glow = _GlowCache.get_tinted(flash_r, rc[:3], flash_alpha)
                    surface.blit(flash_glow,
                                 (self.rect.centerx - flash_r, self.rect.centery - flash_r),
                                 special_flags=pygame.BLEND_RGBA_ADD)

            if rarity == 'legendary':
                self._draw_particles(surface)
            return

        # ==================== AÇILMIŞ KART ÇİZİMİ ====================
        if not self.reveal_burst_done:
            self.reveal_burst_done = True
            if rarity == 'legendary':
                self._spawn_reveal_burst(rarity)

        # Hover glow (yumuşak radyal gradyan ile)
        if self.hover:
            glow = pygame.Surface((self.rect.width + 24, self.rect.height + 24), pygame.SRCALPHA)
            glow_alpha = 40 + int(15 * (math.sin(self.pulse * 2) + 1) * 0.5)
            pygame.draw.rect(glow, (*rc[:3], glow_alpha), glow.get_rect(), border_radius=corner + 8)
            surface.blit(glow, (self.rect.x - 12, self.rect.y - 12), special_flags=pygame.BLEND_RGBA_ADD)

        # --- BALATRO TARZI SHIMMER / AURA OVERLAY (Pre-computed) ---
        # Bell curve band ve mask bir kez hesaplanır, her frame sadece blit edilir.
        if rarity == 'legendary' and self._ensure_shimmer_cache(corner):
            shimmer_speed = 1.2
            shimmer_pos = (math.sin(self.pulse * shimmer_speed) + 1.0) * 0.5
            shimmer_x = int(shimmer_pos * (self.rect.width + self._shimmer_w)) - self._shimmer_w
            self._shimmer_work.fill((0, 0, 0, 0))
            self._shimmer_work.blit(self._shimmer_band, (shimmer_x, 0))
            self._shimmer_work.blit(self._shimmer_mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            surface.blit(self._shimmer_work, (self.rect.x, self.rect.y), special_flags=pygame.BLEND_RGBA_ADD)

        # Nadirlik dış aura (minimal, yumuşak)
        if rarity == 'legendary':
            pulse_v = (math.sin(self.pulse * 1.2) + 1.0) * 0.5
            a1 = int(18 + 14 * pulse_v)
            g1 = pygame.Surface((self.rect.width + 28, self.rect.height + 28), pygame.SRCALPHA)
            pygame.draw.rect(g1, (*rc[:3], a1), g1.get_rect(), border_radius=corner + 10)
            surface.blit(g1, (self.rect.x - 14, self.rect.y - 14), special_flags=pygame.BLEND_RGBA_ADD)

        # Ön yüzü çiz (epic efekt katmanı card face içinde arka plan ile içerik arasında çizilir)
        self._render_card_face(surface, self.rect, corner, rc, debug)

        # Parçacıkları çiz (kartın üstünde)
        if rarity == 'legendary':
            flame_types = {'fire', 'fire_inner', 'flame_tongue', 'flame_core', 'flame_spike', 'ember'}
            self._draw_particles(surface, exclude_types=flame_types)

    # ==================== SHIMMER PRE-COMPUTE ====================

    def _ensure_shimmer_cache(self, corner: int) -> bool:
        """Shimmer efekti için bell-curve band ve rounded-rect mask'i
        önceden hesapla. Boyut değişmedikçe tekrar hesaplanmaz."""
        rarity = self._get_rarity()
        if rarity not in ('legendary', 'epic', 'rare'):
            return False
        cache_key = (self.rect.width, self.rect.height, rarity)
        if self._shimmer_cache_key == cache_key:
            return True
        shimmer_width_pct = {'legendary': 0.35, 'epic': 0.25, 'rare': 0.18}[rarity]
        shimmer_alpha = {'legendary': 45, 'epic': 35, 'rare': 22}[rarity]
        rc = self.rarity_color()
        shimmer_w = max(1, int(self.rect.width * shimmer_width_pct))
        h = self.rect.height
        w = self.rect.width
        corner = self._match_hover_corner(corner, w, h)
        # Bell curve band — tek sefer hesapla
        band = pygame.Surface((shimmer_w, h), pygame.SRCALPHA)
        for sx in range(shimmer_w):
            local_t = sx / max(1, shimmer_w)
            intensity = math.exp(-8.0 * (local_t - 0.5) ** 2)
            a = int(shimmer_alpha * intensity)
            if a > 1:
                pygame.draw.line(band, (*rc[:3], a), (sx, 0), (sx, h - 1))
        # Rounded rect mask — tek sefer
        mask = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(mask, (255, 255, 255, 255), mask.get_rect(), border_radius=corner)
        # Reusable work surface (her frame .fill + blit ile tekrar kullanılır)
        work = pygame.Surface((w, h), pygame.SRCALPHA)
        self._shimmer_band = band
        self._shimmer_mask = mask
        self._shimmer_work = work
        self._shimmer_w = shimmer_w
        self._shimmer_cache_key = cache_key
        return True

    # ==================== BAKED FACE CACHE ====================

    def _ensure_baked_face(self, rect: pygame.Rect, corner: int, rc: tuple, debug: bool) -> tuple[pygame.Surface, pygame.Surface]:
        """Statik kart yüzünü iki katman halinde cache'le.
        İlk katman: arka plan, ikinci katman: ikon + metin + etiketler.
        Böylece epic efekt bu iki katmanın arasına yerleşebilir."""
        cache_key = (rect.width, rect.height, debug)
        if self._baked_face_bg is not None and self._baked_face_fg is not None and self._baked_face_key == cache_key:
            return self._baked_face_bg, self._baked_face_fg

        bg_layer = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        fg_layer = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        png_front = self._get_card_face_image("front", (rect.width, rect.height))
        if png_front is not None:
            bg_layer.blit(png_front, (0, 0))
            corner = self._match_hover_corner(corner, rect.width, rect.height)
            mask = pygame.Surface(bg_layer.get_size(), pygame.SRCALPHA)
            pygame.draw.rect(mask, (255, 255, 255, 255), mask.get_rect(), border_radius=corner)
            bg_layer.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        else:
            base_top = UIColors.BG_MEDIUM
            base_bot = UIColors.BG_LIGHT
            accent = rc
            t_top = self._mix_rgb(base_top, accent, 0.10)
            t_bot = self._mix_rgb(base_bot, accent, 0.18)
            grad_surface = pygame.Surface(bg_layer.get_size(), pygame.SRCALPHA)
            self._fill_gradient(grad_surface, (*t_top, 220), (*t_bot, 220))
            corner = self._match_hover_corner(corner, rect.width, rect.height)
            mask = pygame.Surface(bg_layer.get_size(), pygame.SRCALPHA)
            pygame.draw.rect(mask, (255, 255, 255, 255), mask.get_rect(), border_radius=corner)
            grad_surface.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            bg_layer.blit(grad_surface, (0, 0))

        # Frosted iç katman
        inner = pygame.Surface((rect.width - 6, rect.height - 6), pygame.SRCALPHA)
        pygame.draw.rect(inner, (255, 255, 255, 8), inner.get_rect(), border_radius=max(8, corner - 6))
        bg_layer.blit(inner, (3, 3))

        # Icon placeholder (top center)
        ic_w = min(88, rect.width - 40)
        icon_rect = pygame.Rect((rect.width - ic_w) // 2, 14, ic_w, ic_w)
        base_border_color = self.rarity_color()
        icon_bg = UIColors.BG_LIGHT
        icon_holder = pygame.Surface((icon_rect.width, icon_rect.height), pygame.SRCALPHA)
        grad_bg = pygame.Surface(icon_holder.get_size(), pygame.SRCALPHA)
        start_bg = (*icon_bg, 240)
        end_bg = (min(255, icon_bg[0] + 20), min(255, icon_bg[1] + 20), min(255, icon_bg[2] + 20), 230)
        self._fill_gradient(grad_bg, start_bg, end_bg)
        mask_holder = pygame.Surface(icon_holder.get_size(), pygame.SRCALPHA)
        pygame.draw.rect(mask_holder, (255, 255, 255, 255), mask_holder.get_rect(), border_radius=12)
        grad_bg.blit(mask_holder, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        icon_holder.blit(grad_bg, (0, 0))
        pygame.draw.rect(icon_holder, (255, 255, 255, 18), icon_holder.get_rect(), width=1, border_radius=12)
        pygame.draw.rect(icon_holder, (*base_border_color[:3], 70), icon_holder.get_rect(), width=1, border_radius=12)
        # border inside icon
        icon_image = self.icon_getter(self.card.get('icon_image'), (ic_w - 8, ic_w - 8))
        if icon_image:
            icon_holder.blit(icon_image, ((icon_rect.width - (ic_w - 8)) // 2, (icon_rect.height - (ic_w - 8)) // 2))
        else:
            from emoji_renderer import emoji_surface
            _emoji_ic = emoji_surface(self.card.get('icon', ''), ic_w - 8)
            if _emoji_ic:
                icon_holder.blit(_emoji_ic, ((icon_rect.width - _emoji_ic.get_width()) // 2, (icon_rect.height - _emoji_ic.get_height()) // 2))
            else:
                glyph = self.fonts['icon'].render(_ui_safe_icon_text(self.card.get('icon', ''), fallback='*'), True, UIColors.TEXT_SECONDARY)
                icon_holder.blit(glyph, glyph.get_rect(center=(icon_rect.width // 2, icon_rect.height // 2)))
        fg_layer.blit(icon_holder, icon_rect.topleft)

        # Title
        title_font = self.fonts.get('card_title')
        card_title_text = get_card_title(self.card.get('id', ''), self.card.get('title', ''))
        title_surface = title_font.render(card_title_text, True, UIColors.TEXT_PRIMARY)
        title_pos = (16, icon_rect.bottom + 12)
        self._blit_shadowed(fg_layer, title_surface, title_pos, shadow_alpha=170)

        # Type badge
        type_label = t(_card_type_label_key(self.card))
        type_font = self.fonts.get('tag') or self.fonts.get('desc') or self.fonts.get('small') or self.fonts['value']
        type_surf = type_font.render(type_label, True, UIColors.TEXT_PRIMARY)
        type_bg = pygame.Surface((type_surf.get_width() + 28, type_surf.get_height() + 16), pygame.SRCALPHA)
        pygame.draw.rect(type_bg, (*base_border_color, 120), type_bg.get_rect(), border_radius=18)
        pygame.draw.rect(type_bg, (255, 255, 255, 18), type_bg.get_rect(), width=1, border_radius=18)
        type_x = (rect.width - type_bg.get_width()) // 2
        fg_layer.blit(type_bg, (type_x, icon_rect.bottom + 42))
        self._blit_shadowed(
            fg_layer,
            type_surf,
            (type_x + (type_bg.get_width() - type_surf.get_width()) // 2, icon_rect.bottom + 50),
            shadow_alpha=140,
        )

        # Description text wrap
        desc_font = self.fonts.get('desc')
        wrap_limit_pixels = rect.width - 48
        lines = []
        raw_desc = get_card_description(
            self.card.get('id', ''),
            value=self.card.get('value'),
            fallback=self.card.get('description', '')
        )
        words = str(raw_desc).split()
        cur = ''
        for w in words:
            cand = (cur + ' ' + w).strip()
            if desc_font.size(cand)[0] <= wrap_limit_pixels:
                cur = cand
            else:
                if cur:
                    lines.append(cur)
                cur = w
        if cur:
            lines.append(cur)
        desc_lines = lines[:3]
        desc_y = icon_rect.bottom + 100
        if desc_lines:
            desc_line_h = desc_font.get_linesize()
            desc_pad_x = 12
            desc_pad_y = 8
            desc_bg_x = 16
            desc_bg_w = rect.width - 32
            desc_bg_h = desc_pad_y * 2 + len(desc_lines) * desc_line_h
            desc_bg = pygame.Surface((desc_bg_w, desc_bg_h), pygame.SRCALPHA)
            pygame.draw.rect(desc_bg, (0, 0, 0, 72), desc_bg.get_rect(), border_radius=12)
            fg_layer.blit(desc_bg, (desc_bg_x, max(0, desc_y - desc_pad_y)))

            text_x = desc_bg_x + desc_pad_x
            text_y = desc_y
            for i, l in enumerate(desc_lines):
                d = desc_font.render(l, True, UIColors.TEXT_PRIMARY)
                self._blit_shadowed(fg_layer, d, (text_x, text_y + i * desc_line_h), shadow_alpha=180)

        # Hotkey bottom-right small label
        hk = f"[{self.index + 1}]"
        hk_surf = self.fonts['small'].render(hk, True, UIColors.TEXT_MUTED)
        hk_pos = (rect.width - hk_surf.get_width() - 12, rect.height - hk_surf.get_height() - 10)
        self._blit_shadowed(fg_layer, hk_surf, hk_pos, shadow_alpha=160)

        # Debug overlay
        if debug:
            idx_font = self.fonts.get('card_title')
            idx_text = str(self.index + 1)
            idx_surface = idx_font.render(idx_text, True, (30, 30, 40))
            idx_bg_w = idx_surface.get_width() + 12
            idx_bg_h = idx_surface.get_height() + 8
            idx_bg = pygame.Surface((idx_bg_w, idx_bg_h), pygame.SRCALPHA)
            pygame.draw.ellipse(idx_bg, (255, 255, 255, 220), idx_bg.get_rect())
            idx_bg.blit(idx_surface, ((idx_bg_w - idx_surface.get_width()) // 2, (idx_bg_h - idx_surface.get_height()) // 2))
            fg_layer.blit(idx_bg, (12, 12))

        self._baked_face_bg = bg_layer
        self._baked_face_fg = fg_layer
        self._baked_face_key = cache_key
        return bg_layer, fg_layer

    def _render_card_face(self, surface: pygame.Surface, rect: pygame.Rect, corner: int, rc: tuple, debug: bool = False):
        """Kartın ön yüzünü çiz — baked cache + animasyonlu katmanlar.
        Statik içerik (gradient, ikon, metin) cache'den gelir;
        sadece pulse border ve legendary alevler her frame çizilir."""
        baked_bg, baked_fg = self._ensure_baked_face(rect, corner, rc, debug)
        body = baked_bg.copy()
        card_corner = self._match_hover_corner(corner, rect.width, rect.height)

        rarity = self._get_rarity()
        if rarity == 'epic':
            local_rect = pygame.Rect(0, 0, rect.width, rect.height)
            self._draw_epic_sheet_fx(body, local_rect)
        elif rarity == 'common':
            local_rect = pygame.Rect(0, 0, rect.width, rect.height)
            self._draw_common_sheet_fx(body, local_rect)
        elif rarity == 'rare':
            local_rect = pygame.Rect(0, 0, rect.width, rect.height)
            self._draw_rare_sheet_fx(body, local_rect)
        elif rarity == 'uncommon':
            local_rect = pygame.Rect(0, 0, rect.width, rect.height)
            self._draw_uncommon_sheet_fx(body, local_rect)

        body.blit(baked_fg, (0, 0))

        # Animasyonlu border pulse
        base_border_color = self.rarity_color()
        pulse_val = (math.sin(self.pulse) + 1.0) * 0.5
        border_alpha = 120 + int(60 * pulse_val)
        border_color_pulse = (*base_border_color[:3], border_alpha)
        pygame.draw.rect(body, border_color_pulse, body.get_rect(), width=2, border_radius=card_corner)

        # Legendary: animasyonlu alev katmanı + alev parçacıkları
        if self._get_rarity() == 'legendary':
            local_rect = pygame.Rect(0, 0, rect.width, rect.height)
            self._draw_legendary_flame_base(body, local_rect)
            flame_types = {'fire', 'fire_inner', 'flame_tongue', 'flame_core', 'flame_spike', 'ember'}
            self._draw_particles(body, offset=(self.rect.x, self.rect.y), only_types=flame_types)

        surface.blit(body, (rect.x, rect.y))

    @staticmethod
    def _fill_gradient(surface: pygame.Surface, start_color: tuple[int, int, int, int], end_color: tuple[int, int, int, int]) -> None:
        """Gradient çizimi — cache destekli. Aynı boyut+renk tekrar hesaplanmaz."""
        cached = _get_cached_gradient(surface.get_size(), start_color, end_color)
        surface.blit(cached, (0, 0))



class PerkManager:
    """Simple Perk manager tied to a MysteryMode instance.

    Perks are boolean toggles for now and handle counters and flags.
    """
    def __init__(self, mode: 'MysteryMode') -> None:
        self.mode = mode
        self.active: dict[str, bool] = {}
        self.next_piece_bomb = False
        self.lines_since_chrono = 0
        self.chrono_freeze_timer = 0.0
        self.rewind_uses = 0  # Geri Sarma kullanım hakkı
        # 'phase_shift' is now a shape-mutation perk; state is per piece and handled on the piece object.

    def activate(self, key: str) -> None:
        # Normalize older/alternate perk ids to the internal keys used by the mode.
        key_map = {
            # Historical/test id -> internal id
            'alchemist_touch': 'perk_alchemist',
        }
        normalized = key_map.get(key, key)
        self.active[normalized] = True
        # Note: phase_shift uses are now set from card value in _apply_card_effect,
        # not here. This allows different card values to grant different uses.

    def deactivate(self, key: str) -> None:
        self.active[key] = False

    def is_active(self, key: str) -> bool:
        return bool(self.active.get(key, False))

    def notify_lines_cleared(self, lines: int, source: str = "player") -> None:
        if not lines:
            return
        # Explosive Protocol: if 2 lines cleared -> next piece is a bomb
        # Trigger bomb only if exactly 2 lines cleared simultaneously while the perk is active
        # Prevent farming via card/ability clears: only player clears should arm bombs.
        if self.is_active('explosive_protocol') and lines == 2 and str(source).lower() in {"player", "normal"}:
            self.next_piece_bomb = True
            # Player feedback: make it clear this is the PLUS-shaped bomb perk.
            try:
                self.mode.card_message = "Bomba Ustası: Sonraki parça BOMBA (+)"
                self.mode.card_message_timer = 1.1
            except Exception:
                pass
        # Chrono Lock counter
        if self.is_active('chrono_lock'):
            self.lines_since_chrono += lines
            if self.lines_since_chrono >= 10:
                self.lines_since_chrono = 0
                self.chrono_freeze_timer = 3.0
        # Backwards-compatible Alchemist trigger:
        # Tests and older behavior expect a Quadrix (4 lines) to trigger without
        # needing piece context.
        if self.is_active('perk_alchemist') and int(lines) == 4:
            try:
                self.mode.board.convert_to_gold(5)
            except Exception:
                pass
        # NOTE: T-parça 2/3 satır tetikleri piece context ile `maybe_trigger_alchemist` üzerinden gelir.
        return

    def maybe_trigger_alchemist(self, piece, lines: int) -> None:
        if not self.is_active('perk_alchemist') or not lines:
            return
        try:
            name = getattr(piece, 'name', None)
        except Exception:
            name = None
        # Approximation (no full T-Spin detector exists):
        # - Quadrix (4 lines) always triggers
        # - T piece clearing 2 or 3 lines is treated as T-Spin Double/Triple-like
        is_tetris = int(lines) == 4
        is_t_like_spin = (str(name) == 'T' and int(lines) in (2, 3))
        if not (is_tetris or is_t_like_spin):
            return
        # Midas touch: convert 5 random blocks to gold
        try:
            self.mode.board.convert_to_gold(5)
        except Exception:
            pass

    def on_piece_spawn(self, piece) -> None:
        # Esnek Sinir: perk aktifse tum yeni parcalara flag ekle
        if self.is_active('perk_flexible_border'):
            setattr(piece, 'flexible_border', True)
        
        # For phase shift (shape mutation), there's no per-piece auto-reset. We leave
        # the per-piece flag on the piece object itself and the Game will check it.
        # If explosive next piece, mark piece property
        if self.next_piece_bomb:
            # Mark the piece as a bomb: keep its shape but color it red and set a flag
            setattr(piece, 'is_bomb', True)
            # Keep the original color for UI preview while forcing bomb color in-game
            setattr(piece, '_original_color', getattr(piece, 'color', None))
            BOMB_COLOR = (221, 0, 5)
            piece.color = BOMB_COLOR
            # Preserve this forced color across theme reapplications
            setattr(piece, '_force_color', BOMB_COLOR)
            self.next_piece_bomb = False

    def on_piece_locked(self, piece, locked_cells:list[tuple[int,int]]):
        # Reset tunneling and ghost visuals when a tunneled piece locks
        if getattr(piece, 'tunnel', False):
            try:
                setattr(piece, 'tunnel', False)
                if getattr(piece, '_original_color', None) is not None:
                    piece.color = getattr(piece, '_original_color')
            except Exception:
                pass
        
        # Bomba patlaması artık MysteryMode.lock_and_new_piece içinde yapılıyor
        # Burada tekrar yapmıyoruz, aksi halde çift patlama olur
        return

    def get_multiplier(self) -> float:
        """Sinerji çekirdeği: aktif her perk %10 skor çarpanı verir"""
        base = 1.0
        active_count = sum(1 for v in self.active.values() if v)
        
        # Sinerji Çekirdeği aktifse çarpan hesapla
        if self.is_active('synergy_core'):
            return base + (active_count * 0.10)
        return base
    
    def can_rewind(self) -> bool:
        """Geri Sarma: kullanılabilir mi kontrol et"""
        return self.is_active('rewind_power') and self.rewind_uses > 0
    
    def use_rewind(self) -> bool:
        """Geri Sarma kullan - başarılı ise True döner"""
        if self.can_rewind():
            self.rewind_uses -= 1
            if self.rewind_uses <= 0:
                self.deactivate('rewind_power')
            return True
        return False


class MysteryMode(Game):
    """Kart yöneticisi + UI ayrımıyla yeniden ele alınan Mystery Mode."""

    def _card_ui_scale(self) -> float:
        """Kart modu HUD/font ölçeği."""
        try:
            ref_w, ref_h = getattr(self, '_card_ui_reference_size', (1366, 768))
            ref_w = max(1, int(ref_w))
            ref_h = max(1, int(ref_h))
            w = max(1, int(self.window_width))
            h = max(1, int(self.window_height))
            scale = min(float(w) / float(ref_w), float(h) / float(ref_h))

            rw, rh = getattr(self, '_card_ui_readable_min_size', (1180, 760))
            readable_floor = min(1.0, min(float(w) / max(1.0, float(rw)), float(h) / max(1.0, float(rh))))
            effective_min = max(0.62, readable_floor)
        except Exception:
            scale = 1.0
            effective_min = 0.62
        return max(effective_min, min(1.08, scale))

    def _get_card_ui_reference_size(self) -> tuple[int, int]:
        """Kart UI için fullscreen baz referans çözünürlüğünü döndür."""
        try:
            info = pygame.display.Info()
            ref_w = int(getattr(info, 'current_w', 0) or 0)
            ref_h = int(getattr(info, 'current_h', 0) or 0)
        except Exception:
            ref_w, ref_h = 0, 0

        if ref_w <= 0 or ref_h <= 0:
            ref_w = int(getattr(self, 'window_width', 1366) or 1366)
            ref_h = int(getattr(self, 'window_height', 768) or 768)

        return max(1, ref_w), max(1, ref_h)

    def _get_side_panel_widths(self, board_pixel_width: int | None = None) -> tuple[int, int]:
        """Mystery mode için sol/sağ panel genişliklerini pencereye göre hesapla."""
        window_width = int(self.window_width)

        if board_pixel_width is None:
            board_area_h = max(240, int(self.window_height) - INFO_PANEL_HEIGHT)
            est_cell_h = max(12, min(40, board_area_h // max(1, int(self.board_height))))
            board_pixel_width = int(self.board_width) * est_cell_h

        scale = max(0.80, min(1.20, window_width / 1366.0))

        left_max = int(getattr(self, 'left_panel_max_width', 420) or 420)
        left_pref = min(left_max, max(220, int(320 * scale)))
        right_pref = max(150, min(220, int(190 * scale)))

        max_total = max(300, window_width - int(board_pixel_width) - 60)
        total_pref = left_pref + right_pref

        if total_pref > max_total:
            ratio = max_total / float(max(1, total_pref))
            left_w = max(170, int(left_pref * ratio))
            right_w = max(120, int(right_pref * ratio))
        else:
            left_w = left_pref
            right_w = right_pref

        # Son güvenlik: toplam halen fazla ise önce soldan, sonra sağdan kıs.
        overflow = (left_w + right_w) - max_total
        if overflow > 0:
            cut_left = min(max(0, left_w - 160), overflow)
            left_w -= cut_left
            overflow -= cut_left
            if overflow > 0:
                right_w = max(110, right_w - overflow)

        return left_w, right_w

    def _make_card_ui_font(self, size: int, *, bold: bool = False) -> pygame.font.Font:
        """Kart UI fontunu mevcut dile göre seç.

        CJK (ja/zh/ko) dillerinde get_font_for_language() ile doğrudan
        HybridFont oluşturur — retro_style._font_path global durumundan
        bağımsızdır.  Diğer dillerde retro_style.get_font() kullanılır.
        """
        try:
            lang = get_language()
        except Exception:
            lang = None

        if lang in {"ja", "jp", "zh", "ko"}:
            try:
                from ui_language_profile import get_font_for_language
                effective_lang = "ja" if lang == "jp" else lang
                font = get_font_for_language(effective_lang, size)
                if font is not None:
                    return font
            except Exception:
                pass

        return retro_style.get_font(size, bold=bold)

    def _refresh_card_ui_fonts(self) -> None:
        """Kart UI fontlarını mevcut dile göre yeniden üret."""
        try:
            self._card_ui_lang = get_language()
        except Exception:
            self._card_ui_lang = None

        ui_scale = self._card_ui_scale()

        def s(base: int, min_size: int) -> int:
            return max(min_size, int(round(base * ui_scale)))

        self.mystery_font_large = self._make_card_ui_font(s(48, 26))
        self.mystery_font_medium = self._make_card_ui_font(s(36, 20))
        self.mystery_font_small = self._make_card_ui_font(s(24, 12))
        self.card_font = self._make_card_ui_font(s(28, 14))
        self.card_value_font = self._make_card_ui_font(s(56, 26))
        self.card_icon_font = self._make_card_ui_font(s(84, 34))
        self.card_tag_font = self._make_card_ui_font(s(24, 12))
        self.card_desc_font = self._make_card_ui_font(s(26, 13))

        self._card_ui_font_signature = (
            self._card_ui_lang,
            int(self.window_width),
            int(self.window_height),
        )

    def _ensure_card_ui_fonts(self) -> None:
        """Dil veya pencere boyutu değiştiyse kart fontlarını tazele."""
        try:
            lang = get_language()
        except Exception:
            lang = None

        signature = (lang, int(self.window_width), int(self.window_height))
        if getattr(self, "_card_ui_font_signature", None) != signature:
            self._refresh_card_ui_fonts()

    def _fit_text_to_width(self, font: pygame.font.Font, text: str, max_width: int) -> str:
        """Metni verilen genişliğe sığacak şekilde kısalt."""
        value = str(text or "")
        if max_width <= 0 or font.size(value)[0] <= max_width:
            return value

        suffix = "..."
        while value and font.size(value + suffix)[0] > max_width:
            value = value[:-1]
        return (value + suffix) if value else suffix

    def _play_card_reveal_sfx(self) -> None:
        if not self.sound_enabled:
            return
        try:
            self.sound.play_sound('card_reveal')
        except Exception:
            pass

    def wants_mouse_visible(self) -> bool:
        # Kart seçimi, parça seçimi veya atölye popup gibi overlay'lerde mouse görünür olmalı.
        if getattr(self, '_piece_selection_active', False):
            return True
        if getattr(self, '_card_workshop_active', False):
            return True
        return bool(getattr(self, 'card_selection_active', False)) or super().wants_mouse_visible()

    def __init__(
        self,
        difficulty: str = "Normal",
        sound_enabled: bool = True,
        effects_enabled: bool = True,
        achievement_manager=None,
        theme_manager=None,
        screen=None,
        fullscreen: bool = False,
        settings_manager=None,
        user_manager=None,
        game_mode: str = "mystery",
        score_manager=None,
    ) -> None:
        # spawn_new_piece içinde kullanılacağı için önce manager yaratılır
        self.card_manager = MysteryCardManager(self)
        self.card_ui = MysteryCardUI()
        self.card_selection_active = False
        self.card_message = ""
        self.card_message_timer = 0.0
        self.card_selection_rects: List[pygame.Rect] = []
        self._pending_card_choice_index: int | None = None
        # Queue of pending level-up card selections, and dedup tracker
        self.pending_level_ups = 0
        self.last_enqueued_level = 0

        super().__init__(
            difficulty,
            sound_enabled,
            effects_enabled,
            achievement_manager,
            theme_manager,
            screen,
            fullscreen,
            settings_manager,
            user_manager,
            game_mode,
            score_manager=score_manager,
        )
        self.mode_name = t('mode_label_card_mastery')
        self._card_ui_reference_size = self._get_card_ui_reference_size()
        self._card_ui_readable_min_size = (1180, 760)
        try:
            self.card_ui.set_overlay_reference_size(*self._card_ui_reference_size)
        except Exception:
            pass
        self._card_ui_lang = None
        self._refresh_card_ui_fonts()
        self.card_ui.set_reveal_sfx_callback(self._play_card_reveal_sfx)

        self.left_panel_max_width = 420
        self._left_panel_frame = (10, 20, 400)
        self._left_panel_cards_y = 120
        # Ensure last_enqueued_level initialized after board is created
        self.last_enqueued_level = getattr(self.board, 'level', 0)

        # Kart efekt durumları
        self.speed_effect_timer = 0.0
        self.speed_effect_multiplier = 1.0
        self.line_bonus_remaining = 0
        
        # Zaman Kapsulu durumu
        self.time_capsule_saved = False
        self.time_capsule_data = None
        self.time_capsule_available = False
        self.line_bonus_amount = 0
        self.combo_aura_timer = 0.0
        self.combo_aura_bonus = 0
        
        # Geleceği Değiştiren (future_changer) durumu
        self._future_changer_remaining = 0
        self._future_changer_card = None
        self._piece_selection_active = False
        self._piece_selection_rects: List[pygame.Rect] = []
        self._piece_selection_hover = -1
        
        # Juicy scoring / experimental revamps
        self._score_multiplier_timer = 0.0
        self._score_multiplier_value = 1.0
        self._line_clear_multiplier_remaining = 0
        self._line_clear_multiplier_value = 1.0
        self._armed_nova_clusters = 0
        self._bomb_countdown_timer = 0.0
        self._bomb_countdown_last_int = 0
        self._score_color_override = None
        self._drill_last_cleanup_y = None
        self._active_effect_visuals: Dict[str, Dict] = {}

        # Quantum tunneling (Hayalet Parça) charges: player chooses per-piece via G.
        self.tunnel_charges_remaining = 0

        # Hammer charges: player can turn the CURRENT falling piece into a 1x1 block via H.
        self.hammer_charges_remaining = 0

        # Son Düşüş (Freeze Drop): F tuşuyla bloğu dondur, sadece sağ-sol ve sert düşüş çalışır.
        self._freeze_drop_charges = 0
        self._freeze_drop_duration = 0  # Aktif dondurma süresi (saniye, nadirlğe bağlı)
        self._freeze_drop_timer = 0.0  # Kalan dondurma süresi (saniye)
        self._freeze_drop_active = False  # Şu an bir parça donuk mu?

        # Keep a short history of picked cards so the left panel can show
        # "seçilen bütün kartlar" (not only currently-active effects).
        self.selected_cards_log: List[Dict[str, Any]] = []

        # Sniper patlama efekti (GIF) cache/runtime
        self._sniper_explosion_frames: List[pygame.Surface] = []
        self._sniper_explosion_frame_durations_ms: List[int] = []
        self._sniper_explosion_total_duration_ms = 0
        self._sniper_explosion_ready = False
        self._active_sniper_explosions: List[Dict[str, Any]] = []
        
        # Geri Sarma durumu
        self._rewind_available = False
        self._last_placed_piece = None  # Son yerleştirilen parça bilgisi

        print("🎮 Kart Ustalığı kart pipeline'ı aktif: manager + UI ayrımı tamam.")

        # Initialize per-mode runtime variables early so update() / spawn hooks
        # won't throw if called before restart() (main loop calls update quickly)
        self.perk_manager = PerkManager(self)
        self.energy = 0
        self.energy_max = 100
        self.time_warp_timer = 0.0
        self.gravity_freeze_timer = 0.0
        self.phase_used_for_piece = False
        self._last_ability_keys = {'z': False, 'x': False, 'g': False, 'h': False, 'm': False, 'c': False, 'rotate': False, 'lshift': False, 'v': False, 'b': False, 'f': False}
        # Bomba Ustası: M tuşuyla mini bomba yapma hakları
        self.bomb_master_charges = 0
        # Tuttuğunu Koparan: B tuşuyla hold silme hakları (kart seçilene kadar 0)
        self._hold_destroyer_charges = 0
        # Mystery modunda base game's sabit B hakkı kullanılmaz.
        self.discard_held_uses = 0
        # Score-based speed: Başlangıç hız seviyesi 10, her 500 puanda +1
        self.speed_level = 10  # Başlangıç hız seviyesi

        # Score-based speed multiplier: her 1000 puanda düşüş aralığı %15 azalır (multiplikatif)
        self.score_speed_multiplier = 1.0
        self._last_score_speed_milestone = 0
        self._last_speed_milestone = 0  # Son hız artışı skoru
        # Smooth only speed-ups so score milestones don't feel like a jump.
        # Slowdowns (time_slow/time_warp/chrono) should remain snappy.
        self._speedup_smooth_time = 0.8

        # === Shape mutation cooldown ===
        self._shape_mutation_cooldown = 0.0

        # === Rare bug tracer (ghost/tunnel related unexpected clears) ===
        self._ghost_bug_tracer = None
        self._ghost_bug_dumped_this_run = False
        try:
            env_on = str(os.getenv('TETRIS_TRACE_GHOST_BUG', '')).strip().lower() in {'1', 'true', 'yes', 'on'}
        except Exception:
            env_on = False
        try:
            settings_on = bool(getattr(self, 'settings_manager', None) and self.settings_manager.get('trace_ghost_bug', False))
        except Exception:
            settings_on = False
        try:
            debug_on = bool(getattr(self, 'settings_manager', None) and self.settings_manager.get('debug_mode', False))
        except Exception:
            debug_on = False
        tracer_enabled = bool(env_on or settings_on or debug_on)
        try:
            if tracer_enabled and GhostBugTracer is not None and get_user_data_dir is not None:
                dump_dir = os.path.join(get_user_data_dir(), 'debug_ghost_bug')
                self._ghost_bug_tracer = GhostBugTracer(enabled=True, dump_dir=dump_dir)
        except Exception:
            self._ghost_bug_tracer = None

        # Aktif kartları sync et (tüm değişkenler tanımlandıktan sonra)
        self._sync_active_cards()

    def get_board_offset(self):
        """Tahtanın ekrandaki pozisyonunu hesapla - sol ve sağ panelleri dikkate alarak ortala.
        
        Kart modunda:
        - Sol panel: 320px (left_panel_max_width)
        - Sağ panel: SIDE_PANEL_WIDTH (220px default)
        - Oyun alanı bu iki panel arasında ortalanmalı
        """
        current_size = (self.window_width, self.window_height)
        if not hasattr(self, '_cached_offset_key') or self._cached_offset_key != current_size:
            cell_size = self.get_cell_size()
            board_width = self.board_width * cell_size
            board_height = self.board_height * cell_size

            left_panel_width, right_panel_width = self._get_side_panel_widths(board_width)
            self._mystery_left_panel_width = left_panel_width
            self._mystery_right_panel_width = right_panel_width

            usable_left = left_panel_width + 14
            usable_right = int(self.window_width) - right_panel_width - 14
            usable_width = max(0, usable_right - usable_left)

            # Tahtayı iki panel arasındaki bantta ortala.
            offset_x = usable_left + max(0, (usable_width - board_width) // 2)
            offset_x = max(8, min(offset_x, int(self.window_width) - board_width - 8))

            # Dikeyde ortala.
            offset_y = (int(self.window_height) - board_height) // 2
            
            self._cached_offset = (offset_x, offset_y)
            self._cached_offset_key = current_size
        
        return self._cached_offset

    def get_cell_size(self):
        """Mystery mode için hücre boyutunu iki yan paneli de dikkate alarak hesapla."""
        current_size = (self.window_width, self.window_height, int(self.board_width), int(self.board_height))
        if not hasattr(self, '_cached_cell_size_key') or self._cached_cell_size_key != current_size:
            left_panel_width, right_panel_width = self._get_side_panel_widths()
            self._mystery_left_panel_width = left_panel_width
            self._mystery_right_panel_width = right_panel_width

            board_area_width = int(self.window_width) - left_panel_width - right_panel_width - 40
            board_area_height = int(self.window_height) - INFO_PANEL_HEIGHT

            cell_width = max(8, board_area_width // max(1, int(self.board_width)))
            cell_height = max(8, board_area_height // max(1, int(self.board_height)))

            self._cached_cell_size = max(14, min(cell_width, cell_height, 40))
            self._cached_cell_size_key = current_size

        return self._cached_cell_size

    def _trace_ghost_bug_clear(
        self,
        *,
        now_ms: int | None,
        clear_kind: str,
        cleared_cells: int,
        coords: list[tuple[int, int]] | None = None,
        piece=None,
        note: str | None = None,
    ) -> None:
        tracer = getattr(self, '_ghost_bug_tracer', None)
        if tracer is None:
            return
        try:
            tracer.record_clear(
                now_ms=now_ms,
                clear_kind=str(clear_kind),
                cleared_cells=int(cleared_cells),
                coords=coords,
                piece=piece,
                note=note,
            )
        except Exception:
            return

        if getattr(self, '_ghost_bug_dumped_this_run', False):
            return

        try:
            ms_since_g = tracer.ms_since_g(int(now_ms or 0)) if now_ms is not None else None
        except Exception:
            ms_since_g = None

        # If we clear arbitrary cells shortly after pressing G, dump once.
        # Window is intentionally generous to catch delayed/edge-case clears.
        if ms_since_g is None or ms_since_g > 15000 or int(cleared_cells or 0) <= 0:
            return

        try:
            path = tracer.maybe_dump(
                now_ms=now_ms,
                trigger=f"clear:{clear_kind}",
                board=getattr(self, 'board', None),
                current_piece=getattr(self, 'current_piece', None),
                extra={
                    'ms_since_g': int(ms_since_g),
                    'cleared_cells': int(cleared_cells),
                    'clear_kind': str(clear_kind),
                    'note': note,
                },
            )
        except Exception:
            path = None

        if path:
            self._ghost_bug_dumped_this_run = True
            try:
                print(f"[GhostBugTracer] Dump written: {path}")
            except Exception:
                pass
            # Debug overlay text (only when tracer is enabled anyway)
            try:
                self.card_message = f"[Debug] Ghost dump: {os.path.basename(path)}"
                self.card_message_timer = 2.0
            except Exception:
                pass

    def _hammer_current_piece_to_unit(self) -> bool:
        """Turn the CURRENT falling piece into a 1x1 block.

        Returns True if the piece was updated.
        """
        piece = getattr(self, 'current_piece', None)
        if piece is None:
            return False

        try:
            old_cells = list(piece.get_cells())
        except Exception:
            old_cells = []

        anchor = None
        for x, y in old_cells:
            if y >= 0:
                anchor = (int(x), int(y))
                break
        if anchor is None and old_cells:
            x, y = old_cells[0]
            anchor = (int(x), int(y))
        if anchor is None:
            anchor = (int(getattr(piece, 'x', 0) or 0), int(getattr(piece, 'y', 0) or 0))

        # Preserve the piece's existing color/style. Only shrink its shape.
        try:
            piece.shape = [[1]]
        except Exception:
            return False
        try:
            piece.rotation_state = 0
        except Exception:
            pass
        try:
            if hasattr(piece, 'color_matrix'):
                piece.color_matrix = [[getattr(piece, 'color', None)]]
        except Exception:
            pass

        # Anchor the new 1x1 on a previously occupied cell for intuitive behavior.
        try:
            piece.x, piece.y = anchor
        except Exception:
            pass
        try:
            piece.x = max(0, min(int(piece.x), int(getattr(self.board, 'width', BOARD_WIDTH)) - 1))
        except Exception:
            pass
        try:
            if getattr(self, 'board', None) is not None and not self.board.is_valid_position(piece):
                for dy in range(0, 4):
                    if self.board.is_valid_position(piece, dy=-dy):
                        piece.y = int(piece.y) - dy
                        break
        except Exception:
            pass

        try:
            setattr(piece, 'hammered', True)
        except Exception:
            pass
        return True

    def _record_selected_card(self, card: Dict[str, Any]) -> None:
        if not card:
            return
        try:
            entry = {
                'id': card.get('id'),
                'title': card.get('title', ''),
                'description': card.get('description', ''),
                'tag': card.get('tag', ''),
                'color': card.get('color', (180, 180, 180)),
                'icon': card.get('icon', ''),
                'icon_image': card.get('icon_image'),
                'persistent': bool(card.get('persistent', False)),
            }
            self.selected_cards_log.append(entry)
            # Keep the panel readable and avoid unbounded growth.
            if len(self.selected_cards_log) > 30:
                self.selected_cards_log = self.selected_cards_log[-30:]
            # Kalıcı kart kullanım istatistiği
            if self.user_manager and card.get('id'):
                try:
                    self.user_manager.record_card_usage(str(card['id']), str(card.get('title', '')))
                except Exception:
                    pass
        except Exception:
            return

    @staticmethod
    def _key_label(keycode: int) -> str:
        try:
            name = pygame.key.name(int(keycode))
            if not name:
                return '?'
            return name.upper() if len(name) <= 2 else name
        except Exception:
            return str(keycode)

    def spawn_new_piece(self) -> Piece:
        forced = self.card_manager.pop_forced_piece()
        if forced:
            piece = self._create_named_piece(forced)
            identity = self._piece_identity(piece)
            # Aynı parça 3 kere üst üste geldiyse forced parçayı tüketme; sonraya ertele.
            if self._would_exceed_max_consecutive(identity):
                try:
                    self.card_manager.force_piece_queue.insert(0, forced)
                except Exception:
                    pass
            else:
                self._apply_block_style(piece)
                self._note_piece_spawn(identity)
                try:
                    # Keep UI in sync when forced-piece queue is consumed.
                    if hasattr(self, '_active_effect_visuals'):
                        self._sync_active_cards()
                except Exception:
                    pass
                # Perk manager'ı forced piece için de çağır (Esnek Sınır vb.)
                try:
                    self.perk_manager.on_piece_spawn(piece)
                except Exception:
                    pass
                return piece
        piece = super().spawn_new_piece()
        # Let perk manager adjust the newly spawned piece (bombs, phase)
        try:
            self.perk_manager.on_piece_spawn(piece)
        except Exception:
            pass

        # Auto-activate Ghost Echo if we would immediately game-over with this spawn
        try:
            if not self.board.is_valid_position(piece):
                # Find active ghost_echo card
                for ac in list(self.card_manager.active_cards):
                    if ac.get('id') == 'ghost_echo':
                        # "Second chance shield": clear the top N rows (matches card text)
                        try:
                            rows = int(ac.get('value', ac.get('base', 6)) or 6)
                        except Exception:
                            rows = 6
                        rows = max(1, min(rows, int(getattr(self.board, 'height', BOARD_HEIGHT) or BOARD_HEIGHT)))
                        try:
                            if hasattr(self.board, 'clear_top_rows'):
                                self.board.clear_top_rows(rows)
                            else:
                                for y in range(rows):
                                    for x in range(self.board.width):
                                        self.board.grid[y][x] = BLACK
                                        self.board.texture_grid[y][x] = None
                                        self.board.occupancy[y][x] = False
                                        try:
                                            self.board.gold[y][x] = False
                                        except Exception:
                                            pass
                                        try:
                                            self.board.owners[y][x] = None
                                        except Exception:
                                            pass
                        except Exception:
                            pass
                        # Remove used card from active cards
                        try:
                            self.card_manager.active_cards.remove(ac)
                        except Exception:
                            pass
                        # Also clear the visual entry so it no longer appears
                        try:
                            self._active_effect_visuals.pop('ghost_echo', None)
                        except Exception:
                            pass
                        # Sync UI visuals and break
                        try:
                            self.card_message = "Ölümden döndün!"
                            self.card_message_timer = 2.0
                        except Exception:
                            pass
                        self._sync_active_cards()
                        break
        except Exception:
            pass
        return piece

    def _save_last_placed_piece(self, piece=None) -> None:
        """Geri Sarma için son yerleştirilen parçanın bilgilerini kaydet."""
        import copy
        try:
            p = piece if piece is not None else self.current_piece
            if p:
                # Parçanın kilitlendiği hücreleri kaydet
                cells = [(x, y) for x, y in p.get_cells() if y >= 0]
                self._last_placed_piece = {
                    'piece': copy.deepcopy(p),
                    'cells': cells,
                    'color': getattr(p, 'color', None),
                }
        except Exception as e:
            print(f"[Rewind] Parça kaydetme hatası: {e}")
            self._last_placed_piece = None

    def _do_rewind(self) -> bool:
        """Geri Sarma kullan - son parçayı board'dan kaldır ve tekrar düşür."""
        if not getattr(self, '_last_placed_piece', None):
            self.card_message = "Geri alınacak parça yok!"
            self.card_message_timer = 1.0
            return False
        
        if not self.perk_manager.is_active('rewind_power') or self.perk_manager.rewind_uses <= 0:
            self.card_message = "Geri sarma hakkın kalmadı!"
            self.card_message_timer = 1.0
            return False
        
        try:
            import copy
            last = self._last_placed_piece
            
            # Son parçanın hücrelerini board'dan sil (grid, occupancy ve texture_grid)
            for x, y in last['cells']:
                if 0 <= y < self.board.height and 0 <= x < self.board.width:
                    self.board.grid[y][x] = None
                    self.board.occupancy[y][x] = False
                    if hasattr(self.board, 'texture_grid'):
                        self.board.texture_grid[y][x] = None
            
            # Mevcut parçayı kuyruğun başına ekle.
            # NOT: Parçayı olduğu gibi geri koyarsak, daha sonra tekrar geldiğinde
            # eski x/y konumundan düşmeye devam eder. Bu yüzden spawn konumuna resetle.
            queued_piece = self.current_piece
            try:
                if queued_piece is not None:
                    queued_piece.x = self._compute_spawn_x(queued_piece.get_width())
                    queued_piece.y = 0
            except Exception:
                pass
            self.next_piece_queue.insert(0, queued_piece)
            
            # Son parçayı tekrar aktif parça yap
            restored_piece = copy.deepcopy(last['piece'])
            restored_piece.x = 3  # Başlangıç X pozisyonu
            restored_piece.y = 0  # Yukarıdan başla
            # Rengi koru
            if last.get('color'):
                restored_piece.color = last['color']
            self.current_piece = restored_piece
            
            # Tema renklerini uygula
            self.apply_theme_to_pieces()
            
            # Kullanım hakkını düşür
            self.perk_manager.rewind_uses -= 1
            
            # Kalan hakkı göster
            remaining = self.perk_manager.rewind_uses
            if remaining <= 0:
                self.perk_manager.deactivate('rewind_power')
                self._rewind_available = False
                self.card_message = "Geri Sarma kullanıldı! (Son hak)"
            else:
                self.card_message = f"Geri Sarma! ({remaining} hak kaldı)"
            self.card_message_timer = 1.5
            
            # Son parça bilgisini temizle (aynı parçayı tekrar geri alamaz)
            self._last_placed_piece = None
            
            # Ses çal
            try:
                self.sound.play('rotate')
            except:
                pass
            
            self._sync_active_cards()
            return True
        except Exception as e:
            print(f"[Rewind] Geri sarma hatası: {e}")
            return False

    def lock_and_new_piece(self) -> None:
        before_piece_ref = self.current_piece
        before = self.board.lines_cleared
        previous_combo = getattr(self.board, "combo", 0)
        # locked cells (for explosive handling)
        # capture the piece that was locked (current_piece will be replaced by super().lock_and_new_piece())
        locked_piece = self.current_piece
        locked_cells = [(x, y) for x, y in locked_piece.get_cells() if y >= 0]
        # measure previous score to apply synergy multiplier to added points
        prev_score = self.board.score
        # If chrono freeze active, set fall_speed high to 'pause' gravity
        if getattr(self.perk_manager, 'chrono_freeze_timer', 0) > 0:
            self.gravity_freeze_timer = self.perk_manager.chrono_freeze_timer
            self.perk_manager.chrono_freeze_timer = 0.0
        # Son Düşüş: parça kilitlendiğinde dondurma sona erer
        if getattr(self, '_freeze_drop_active', False):
            self._freeze_drop_active = False
            self._freeze_drop_timer = 0.0
        super().lock_and_new_piece()

        # If the underlying Game ignored the lock (e.g., tunneled hard-drop pressed
        # while not touching), do not run post-lock bookkeeping.
        if self.current_piece is before_piece_ref:
            return

        # Consume one tunneling charge only when the tunneled piece actually locked.
        try:
            if getattr(locked_piece, 'tunnel', False) and getattr(locked_piece, '_tunnel_charge_pending', False):
                self.tunnel_charges_remaining = max(0, int(getattr(self, 'tunnel_charges_remaining', 0) or 0) - 1)
                try:
                    delattr(locked_piece, '_tunnel_charge_pending')
                except Exception:
                    setattr(locked_piece, '_tunnel_charge_pending', False)
        except Exception:
            pass

        # Lines cleared by this lock (before any card/explosion secondary clears).
        gained = self.board.lines_cleared - before

        # Save rewind snapshot only after a successful lock so the saved cell
        # positions reflect any last-moment adjustments (including tunneling snap).
        if getattr(self, '_rewind_available', False):
            try:
                # If this placed piece cleared any line(s) (incl. Quadrix), rewind must be disabled.
                if gained > 0:
                    self._last_placed_piece = None
                else:
                    self._save_last_placed_piece(locked_piece)
            except Exception:
                pass

        # Apply post-scoring multipliers (synergy_core, timed score multiplier, line-clear multiplier)
        try:
            base_delta = int(self.board.score - prev_score)
        except Exception:
            base_delta = 0
        multiplier = self.perk_manager.get_multiplier() if getattr(self, 'perk_manager', None) else 1.0
        if multiplier != 1.0 and base_delta > 0:
            self.board.score += int(base_delta * (multiplier - 1.0))
        try:
            delta_after_synergy = int(self.board.score - prev_score)
        except Exception:
            delta_after_synergy = 0
        try:
            self.board.score += self._apply_score_multiplier_to_delta(delta_after_synergy)
        except Exception:
            pass
        # Quantum tunneling is now a multi-charge effect; do not clear its HUD entry on lock.
        try:
            self._sync_active_cards()
        except Exception:
            pass
        try:
            delta_after_timed = int(self.board.score - prev_score)
            self.board.score += self._apply_line_clear_multiplier_to_delta(gained, delta_after_timed)
        except Exception:
            pass
        # Energy gain for Mystery Mode: +10 energy per cleared line
        if getattr(self, 'energy', None) is not None and gained > 0:
            try:
                self.energy = min(self.energy_max, int(self.energy + gained * 10))
            except Exception:
                self.energy = min(getattr(self, 'energy_max', 100), getattr(self, 'energy', 0) + (gained * 10))
        # Explosive Protocol: if the locked piece is a bomb, explode.
        if getattr(locked_piece, 'is_bomb', False):
            width = len(self.board.grid[0])
            height = len(self.board.grid)
            cleared_cells = 0
            cleared_coords: list[tuple[int, int]] = []
            now_ms = None
            try:
                now_ms = int(pygame.time.get_ticks())
            except Exception:
                now_ms = None
            if locked_cells:
                cx = int(round(sum(x for x, _ in locked_cells) / len(locked_cells)))
                cy = int(round(sum(y for _, y in locked_cells) / len(locked_cells)))

                bomb_cells = {(int(sx), int(sy)) for sx, sy in locked_cells}

                # Mini bomb: clear only blocks the bomb footprint touches (4-neighborhood).
                if getattr(locked_piece, '_bomb_contact', False):
                    targets = set(bomb_cells)
                    for sx, sy in bomb_cells:
                        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                            nx, ny = sx + dx, sy + dy
                            if 0 <= nx < width and 0 <= ny < height:
                                if self.board.occupancy[ny][nx] and (nx, ny) not in bomb_cells:
                                    targets.add((nx, ny))
                else:
                    # Default bomb behavior: a small + around the lock center.
                    targets = {(cx, cy), (cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)}

                for x, y in targets:
                    if 0 <= x < width and 0 <= y < height and self.board.occupancy[y][x]:
                        self.board.occupancy[y][x] = False
                        self.board.grid[y][x] = BLACK
                        self.board.texture_grid[y][x] = None
                        try:
                            self.board.gold[y][x] = False
                        except Exception:
                            pass
                        try:
                            self.board.owners[y][x] = None
                        except Exception:
                            pass
                        cleared_cells += 1
                        cleared_coords.append((int(x), int(y)))
            if cleared_cells > 0:
                try:
                    self._trace_ghost_bug_clear(
                        now_ms=now_ms,
                        clear_kind='bomb',
                        cleared_cells=cleared_cells,
                        coords=cleared_coords,
                        piece=locked_piece,
                        note=f"bomb_contact={bool(getattr(locked_piece, '_bomb_contact', False))}",
                    )
                except Exception:
                    pass
                if self.sound_enabled:
                    self.sound.play_sound('clear')
                self.board.score += cleared_cells * 40
                if self.effects_enabled and locked_cells:
                    offset_x = (self.window_width - BOARD_WIDTH * 25) // 2
                    offset_y = (self.window_height - BOARD_HEIGHT * 25) // 2
                    px = offset_x + int(cx * 25) + 12
                    py = offset_y + int(cy * 25) + 12
                    self.create_power_particles(px, py, (255, 100, 50), count=60)
                # clear any new full rows created by explosion
                prev_score_ex = int(getattr(self.board, 'score', 0))
                extra_cleared = int(self.board.clear_lines(source='card'))
                if extra_cleared:
                    try:
                        delta_ex = int(getattr(self.board, 'score', 0)) - prev_score_ex
                    except Exception:
                        delta_ex = None
                    self._post_external_line_clear(extra_cleared, award_energy=True, score_delta=delta_ex, source='card')
                    gained += extra_cleared

        # Alchemist perk trigger with piece context (T-like spins or Quadrix)
        try:
            self.perk_manager.maybe_trigger_alchemist(locked_piece, gained)
        except Exception:
            pass

        # Armed Nova Burst: after lock, explode a 3x3 around the locked piece center
        try:
            charges = int(getattr(self, '_armed_nova_clusters', 0) or 0)
        except Exception:
            charges = 0
        if charges > 0 and locked_cells:
            prev_score_nova = int(getattr(self.board, 'score', 0))
            width = len(self.board.grid[0])
            height = len(self.board.grid)
            cx = int(round(sum(x for x, _ in locked_cells) / len(locked_cells)))
            cy = int(round(sum(y for _, y in locked_cells) / len(locked_cells)))
            cleared_cells = 0
            cleared_coords: list[tuple[int, int]] = []
            now_ms = None
            try:
                now_ms = int(pygame.time.get_ticks())
            except Exception:
                now_ms = None
            for y in range(max(0, cy - 1), min(height, cy + 2)):
                for x in range(max(0, cx - 1), min(width, cx + 2)):
                    if self.board.occupancy[y][x]:
                        self.board.occupancy[y][x] = False
                        self.board.grid[y][x] = BLACK
                        self.board.texture_grid[y][x] = None
                        try:
                            self.board.gold[y][x] = False
                        except Exception:
                            pass
                        try:
                            self.board.owners[y][x] = None
                        except Exception:
                            pass
                        cleared_cells += 1
                        cleared_coords.append((int(x), int(y)))
            if cleared_cells:
                try:
                    self._trace_ghost_bug_clear(
                        now_ms=now_ms,
                        clear_kind='nova_armed',
                        cleared_cells=cleared_cells,
                        coords=cleared_coords,
                        piece=locked_piece,
                    )
                except Exception:
                    pass
                self.board.score += cleared_cells * 40
                if self.sound_enabled:
                    self.sound.play_sound('clear')
                if self.effects_enabled:
                    offset_x = (self.window_width - BOARD_WIDTH * 25) // 2
                    offset_y = (self.window_height - BOARD_HEIGHT * 25) // 2
                    px = offset_x + int(cx * 25) + 12
                    py = offset_y + int(cy * 25) + 12
                    self.create_power_particles(px, py, self.mode_skin.accent, count=80)
                cleared_lines = int(self.board.clear_lines(source='card'))
                if cleared_lines > 0:
                    try:
                        delta = int(getattr(self.board, 'score', 0)) - prev_score_nova
                    except Exception:
                        delta = None
                    self._post_external_line_clear(cleared_lines, award_energy=True, score_delta=delta, source='card')
            self._armed_nova_clusters = max(0, charges - 1)
            self._sync_active_cards()
        if gained > 0:
            self._apply_line_bonus_reward(gained)
            # Spawn XP homing particles for Cascade Protocol (Mystery Mode)
            if self.effects_enabled:
                board_width = BOARD_WIDTH * 25
                board_height = BOARD_HEIGHT * 25
                offset_x = (self.window_width - board_width) // 2
                offset_y = (self.window_height - board_height) // 2
                xp_bar_x = self.window_width - 120
                xp_bar_y = offset_y + 40
                for row in self.board.last_cleared_lines:
                    for col in range(self.board_width):
                        cell_x = offset_x + col * 25 + 12
                        cell_y = offset_y + row * 25 + 12
                        for _ in range(2):
                            particle = {
                                'x': float(cell_x),
                                'y': float(cell_y),
                                'vx': random.uniform(-2, 2),
                                'vy': random.uniform(-2, -1),
                                'life': random.randint(40, 80),
                                'max_life': 100,
                                'color': self.mode_skin.accent,
                                'size': 3,
                                'target': (xp_bar_x, xp_bar_y),
                                'speed_override': 8
                            }
                            self.particles.append(particle)
        self._apply_combo_aura_on_lock(gained, previous_combo)
        # Line-based notification retained to update internal progress, but we no longer
        # open the card selection overlay from gained lines; selection now happens on level-up.
        try:
            try:
                if getattr(self, 'settings_manager', None) and self.settings_manager.get('debug_mode', False):
                    print(f"[MysteryMode] lock_and_new_piece: gained={gained}, board.level={self.board.level}, progress={self.card_manager.progress}")
            except Exception:
                pass
            triggered = self.card_manager.notify_lines_cleared(gained)
            # Note: `notify_lines_cleared` will enqueue pending_level_ups via
            # the mode.last_enqueued_level dedup logic; don't enqueue here to
            # avoid double-counting.
        except Exception:
            pass
        # Perk manager: trigger per-line events
        try:
            self.perk_manager.notify_lines_cleared(gained, source='player')
        except Exception:
            pass
        # Notify perk manager that a piece was locked
        try:
            self.perk_manager.on_piece_locked(self.current_piece, locked_cells)
        except Exception:
            pass

    def update(self, dt: float) -> None:
        # dt gelebilir: ms (oyun döngüsünden) veya saniye. Tutarlı dönüşüm.
        seconds = _dt_to_seconds(dt)
        self.card_message_timer = max(0, self.card_message_timer - seconds)
        self._update_effect_timers(dt)
        
        # Parça seçim popup'ı açıkken oyunu durdur
        if getattr(self, '_piece_selection_active', False):
            self.update_screen_shake()
            return

        # Blok atölyesi kartı popup'ı açıkken oyunu durdur
        if getattr(self, '_card_workshop_active', False):
            # Atölye mesaj timer'ını güncelle
            if getattr(self, '_card_workshop_message_timer', 0) > 0:
                self._card_workshop_message_timer = max(0, self._card_workshop_message_timer - seconds)
            self.update_screen_shake()
            return
        
        if self.card_selection_active:
            # Kart ekranı açıkken oyun alanı CANLI görünmeli.
            # Parça kontrolü kapalı, ama animasyonlar ve düşüş devam eder.
            self.card_ui.update(dt, True)
            if self._pending_card_choice_index is not None and not self.card_ui.is_selection_animating():
                self._finalize_pending_card_selection()

            prev_allow_auto_lock = getattr(self, 'allow_auto_lock', True)
            prev_fall_speed = getattr(self, 'fall_speed', None)
            try:
                # Yeni parça doğmasın: otomatik kilitlemeyi kapat.
                self.allow_auto_lock = False
                # Kart seçiminde blok düşmesin: fall_speed'i çok yükselt.
                if prev_fall_speed is not None:
                    self.fall_speed = max(10**9, int(prev_fall_speed))
                super().update(dt)
            finally:
                self.allow_auto_lock = prev_allow_auto_lock
                if prev_fall_speed is not None:
                    self.fall_speed = prev_fall_speed
            return
        
        # Keskin Nişancı overlay aktifken oyun alanını dondur (zaman durur)
        if getattr(self, '_sniper_overlay_active', False):
            # Sadece ekran sarsıntısı ve UI güncellemelerine izin ver
            self.update_screen_shake()
            return
        
        # Save previous level before running engine update so we can detect level-up
        prev_level = self.board.level
        super().update(dt)

        # Drill piece: continuously delete overlapped blocks while falling
        try:
            self._cleanup_drill_overlaps()
        except Exception:
            pass

        # Bomb piece countdown: show 3-2-1 as it falls
        try:
            piece = getattr(self, 'current_piece', None)
            if piece and getattr(piece, 'is_bomb', False):
                bomb_seconds = _dt_to_seconds(dt)
                if getattr(self, '_bomb_countdown_timer', 0.0) <= 0:
                    self._bomb_countdown_timer = 3.0
                    self._bomb_countdown_last_int = 0
                else:
                    self._bomb_countdown_timer = max(0.0, float(self._bomb_countdown_timer) - bomb_seconds)
                cur = int(math.ceil(max(0.0, float(self._bomb_countdown_timer))))
                last = int(getattr(self, '_bomb_countdown_last_int', 0) or 0)
                if cur != last and cur > 0:
                    self._bomb_countdown_last_int = cur
                    self.card_message = f"BOMBA: {cur}"
                    self.card_message_timer = 0.6
        except Exception:
            pass
        # Detect level up and open card selection when the player levels up
        self.card_ui.update(dt, False)
        # --- Active abilities via keyboard state (Z/X/C) ---
        if not self.card_selection_active and not self.game_over:
            keys = pygame.key.get_pressed()
            # Gamepad buton durumunu da kontrol et (pygame.key.get_pressed sentetik olayları algılamaz)
            try:
                _gpm = get_gamepad_manager()
                _gp_connected = _gpm.is_connected()
            except Exception:
                _gpm = None
                _gp_connected = False

            def _pressed(keycode: int) -> bool:
                """Robust key state check.

                pygame.key.get_pressed() (pygame 2) returns a wrapper that can
                be indexed by pygame keycodes (event.key). Some environments
                may behave like a plain sequence; keep a fallback.
                """
                try:
                    kc = int(keycode)
                except Exception:
                    return False
                try:
                    # Prefer keycode indexing (matches event.key and control bindings).
                    return bool(keys[kc])
                except Exception:
                    pass

                # Fallback: if keys behaves like a plain sequence, allow
                # small keycodes.
                try:
                    if 0 <= kc < len(keys):
                        return bool(keys[kc])
                except Exception:
                    pass

                # Last-resort fallback: attempt keycode -> scancode mapping.
                try:
                    if hasattr(pygame.key, 'get_scancode_from_key'):
                        sc = pygame.key.get_scancode_from_key(kc)
                        if sc is not None:
                            return bool(keys[int(sc)])
                except Exception:
                    pass
                return False
            # Ground Sweep (Z) - cost 40
            if keys[pygame.K_z] and not self._last_ability_keys['z']:
                if self.energy >= 40:
                    self.energy = max(0, self.energy - 40)
                    prev_score = int(getattr(self.board, 'score', 0))
                    self._clear_rows(1)
                    try:
                        delta = int(getattr(self.board, 'score', 0)) - prev_score
                    except Exception:
                        delta = None
                    self._post_external_line_clear(1, award_energy=False, score_delta=delta, source='ability')
                    if self.effects_enabled:
                        self.create_power_particles(self.window_width - 120, 60, self.mode_skin.accent)
            self._last_ability_keys['z'] = bool(keys[pygame.K_z])

            # Hayalet Parça (G): Mevcut parçayı hayalet yap - blokların içinden geçebilir.
            # SPACE ile istenen yerde kilitlenir (komşu blok varsa).
            # Hak, parça kilitlenince harcanır.
            _g_pressed = keys[pygame.K_g] or (_gp_connected and _gpm.is_action_pressed('card_ghost'))
            if _g_pressed and not self._last_ability_keys.get('g', False):
                now_ms = None
                try:
                    now_ms = int(pygame.time.get_ticks())
                except Exception:
                    now_ms = None
                try:
                    if self._ghost_bug_tracer is not None:
                        self._ghost_bug_tracer.mark_g_pressed(int(now_ms or 0))
                        self._ghost_bug_tracer.event(
                            'key_g_pressed',
                            now_ms=now_ms,
                            tunnel_charges=int(getattr(self, 'tunnel_charges_remaining', 0) or 0),
                            piece=self._ghost_bug_tracer.snapshot_piece(getattr(self, 'current_piece', None)),
                        )
                except Exception:
                    pass
                try:
                    charges = int(getattr(self, 'tunnel_charges_remaining', 0) or 0)
                except Exception:
                    charges = 0
                piece = getattr(self, 'current_piece', None)
                if charges > 0 and piece and not getattr(piece, 'tunnel', False):
                    try:
                        try:
                            if self._ghost_bug_tracer is not None:
                                self._ghost_bug_tracer.event(
                                    'tunnel_arm_before',
                                    now_ms=now_ms,
                                    piece=self._ghost_bug_tracer.snapshot_piece(piece),
                                )
                        except Exception:
                            pass
                        setattr(piece, 'tunnel', True)
                        setattr(piece, '_tunnel_charge_pending', True)
                        # Görsel: parçayı yarı saydam yap
                        setattr(piece, '_original_color', getattr(piece, 'color', None))
                        try:
                            piece.color = tuple(int(c * 0.45) for c in getattr(piece, '_original_color'))
                        except Exception:
                            pass
                        try:
                            self.card_message = f"Hayalet aktif! SPACE ile kilitle. Kalan: {int(charges)}"
                            self.card_message_timer = 1.2
                        except Exception:
                            pass
                        self._sync_active_cards()
                        try:
                            if self._ghost_bug_tracer is not None:
                                self._ghost_bug_tracer.event(
                                    'tunnel_arm_after',
                                    now_ms=now_ms,
                                    piece=self._ghost_bug_tracer.snapshot_piece(piece),
                                )
                        except Exception:
                            pass
                    except Exception:
                        pass
            self._last_ability_keys['g'] = bool(_g_pressed)

            # Çekiç (H): mevcut düşen parçayı 1x1 bloğa dönüştür (3 hak)
            _h_pressed = keys[pygame.K_h] or (_gp_connected and _gpm.is_action_pressed('card_hammer'))
            if _h_pressed and not self._last_ability_keys.get('h', False):
                try:
                    charges = int(getattr(self, 'hammer_charges_remaining', 0) or 0)
                except Exception:
                    charges = 0
                if charges > 0:
                    if self._hammer_current_piece_to_unit():
                        self.hammer_charges_remaining = max(0, charges - 1)
                        try:
                            left = int(getattr(self, 'hammer_charges_remaining', 0) or 0)
                            self.card_message = f"Çekiç! Mevcut parça 1x1. Kalan: {left}"
                            self.card_message_timer = 1.1
                        except Exception:
                            pass
                        try:
                            self._sync_active_cards()
                        except Exception:
                            pass
                        try:
                            if self.sound_enabled:
                                self.sound.play_sound('rotate')
                        except Exception:
                            pass
            self._last_ability_keys['h'] = bool(_h_pressed)

            # Bomba Ustası (M): mevcut parçayı mini bomba yap (3 hak)
            _m_pressed = keys[pygame.K_m] or (_gp_connected and _gpm.is_action_pressed('card_bomb'))
            if _m_pressed and not self._last_ability_keys.get('m', False):
                try:
                    charges = int(getattr(self, 'bomb_master_charges', 0) or 0)
                except Exception:
                    charges = 0
                if charges > 0:
                    piece = getattr(self, 'current_piece', None)
                    if piece is not None and not getattr(piece, 'is_bomb', False):
                        try:
                            # Mini bomba mantığı: parçayı bomba yap
                            setattr(piece, 'is_bomb', True)
                            # Mini bomb sadece temas ettiği blokları patlatır
                            setattr(piece, '_bomb_contact', True)
                            # Orijinal rengi sakla
                            if getattr(piece, '_original_color', None) is None:
                                setattr(piece, '_original_color', getattr(piece, 'color', None))
                            # Bomba rengi: kırmızı
                            BOMB_COLOR = (221, 0, 5)
                            piece.color = BOMB_COLOR
                            setattr(piece, '_force_color', BOMB_COLOR)
                            # Hakkı düşür
                            self.bomb_master_charges = max(0, charges - 1)
                            left = int(self.bomb_master_charges)
                            self.card_message = f"Mini Bomba! Parça kilitlenince patlayacak. Kalan: {left}"
                            self.card_message_timer = 1.2
                            self._sync_active_cards()
                            if self.sound_enabled:
                                self.sound.play_sound('rotate')
                        except Exception:
                            pass
                    elif piece is not None and getattr(piece, 'is_bomb', False):
                        self.card_message = "Bu parça zaten bomba!"
                        self.card_message_timer = 0.9
                    else:
                        self.card_message = "Bomba Ustası: Parça yok!"
                        self.card_message_timer = 0.9
            self._last_ability_keys['m'] = bool(_m_pressed)

            # Tuttuğunu Koparan (B): hold'daki parçayı sil (hak varsa)
            _b_pressed = keys[pygame.K_b] or (_gp_connected and _gpm.is_action_pressed('discard_held'))
            if _b_pressed and not self._last_ability_keys.get('b', False):
                try:
                    hd_charges = int(getattr(self, '_hold_destroyer_charges', 0) or 0)
                except Exception:
                    hd_charges = 0
                if hd_charges > 0 and getattr(self, 'held_piece', None) is not None:
                    self.held_piece = None
                    self._hold_destroyer_charges = max(0, hd_charges - 1)
                    self.can_hold = True
                    # HUD gösterimi için sync
                    self.discard_held_uses = self._hold_destroyer_charges
                    try:
                        left = int(self._hold_destroyer_charges)
                        self.card_message = f"Saklanan parca silindi! Kalan: {left}"
                        self.card_message_timer = 1.2
                    except Exception:
                        pass
                    try:
                        self._sync_active_cards()
                    except Exception:
                        pass
                    if self.sound_enabled:
                        try:
                            self.sound.play_sound('clear')
                        except Exception:
                            pass
                elif hd_charges > 0:
                    self.card_message = "Saklanan parca yok!"
                    self.card_message_timer = 0.9
                # hd_charges == 0 ise sessiz kal (B tuşu aktif kart yok)
            self._last_ability_keys['b'] = bool(_b_pressed)

            # Son Düşüş (F): mevcut düşen bloğu dondur (3 hak)
            _f_pressed = keys[pygame.K_f]
            if _f_pressed and not self._last_ability_keys.get('f', False):
                try:
                    charges = int(getattr(self, '_freeze_drop_charges', 0) or 0)
                except Exception:
                    charges = 0
                if charges > 0 and not getattr(self, '_freeze_drop_active', False):
                    piece = getattr(self, 'current_piece', None)
                    if piece is not None:
                        try:
                            self._freeze_drop_active = True
                            dur = int(getattr(self, '_freeze_drop_duration', 6) or 6)
                            self._freeze_drop_timer = float(dur)
                            self._freeze_drop_charges = max(0, charges - 1)
                            # Parçayı buz rengine boya
                            if getattr(piece, '_original_color', None) is None:
                                setattr(piece, '_original_color', getattr(piece, 'color', None))
                            ICE_COLOR = (140, 220, 255)
                            piece.color = ICE_COLOR
                            setattr(piece, '_force_color', ICE_COLOR)
                            setattr(piece, '_frozen', True)
                            left = int(self._freeze_drop_charges)
                            self.card_message = f"❄️ Blok dondu! {dur}sn. Kalan: {left}"
                            self.card_message_timer = 1.4
                            self._sync_active_cards()
                            if self.sound_enabled:
                                self.sound.play_sound('rotate')
                        except Exception:
                            pass
            self._last_ability_keys['f'] = bool(_f_pressed)

            # Time Warp (X) - cost 60
            if keys[pygame.K_x] and not self._last_ability_keys['x']:
                if self.energy >= 60 and self.time_warp_timer <= 0:
                    self.energy = max(0, self.energy - 60)
                    self.time_warp_timer = 3.5
                    # Derive the slow-fall target from the mode's base speed curve,
                    # not from the current fall_speed (which may be affected by soft drop).
                    try:
                        base_ms = int(self.get_current_speed())
                    except Exception:
                        base_ms = int(getattr(self, 'fall_speed', 300) or 300)
                    self._timewarp_old_speed = int(getattr(self, 'fall_speed', base_ms) or base_ms)
                    self.fall_speed = max(100, int(base_ms * 3))
            self._last_ability_keys['x'] = bool(keys[pygame.K_x])
            # Phase Shift was previously bound to teleport; now replaced by Shape Mutation
            # Shape Mutation is activated via LSHIFT in the input handler (see Game.handle_input)
            # The rotation key should only perform regular rotation (handled by input events).
            rot_key = self.control_bindings.get('rotate', pygame.K_UP)
            # Keep the _last_ability_keys updated for the rotate binding
            # (no teleport/phase behavior handled here anymore)
            self._last_ability_keys['rotate'] = bool(keys[rot_key])

            # Kart Modu: skora bağlı hızlanma KAPALI.
            # Yalnızca seviye (board.level) bazlı hızlanma kullanılır.
            self.score_speed_multiplier = 1.0
            self._last_score_speed_milestone = 0

            # Smooth score-based acceleration so milestone jumps feel gradual.
            # Do not interfere with soft drop or explicit gravity overrides.
            try:
                soft_key = int(self.control_bindings.get('soft_drop', pygame.K_DOWN))
                # WASD desteği: ayardaki soft_drop'a ek olarak S da her zaman soft drop alternatifi.
                soft_drop_active = _pressed(soft_key) or _pressed(pygame.K_s)
                if not soft_drop_active:
                    try:
                        from gamepad_manager import get_gamepad_manager
                        if get_gamepad_manager().is_direction_held('down'):
                            soft_drop_active = True
                    except Exception:
                        pass
            except Exception:
                soft_drop_active = False

            # Soft drop must work reliably even if KEYDOWN was swallowed by
            # an overlay (e.g., card selection). Use key state as source of truth.
            # Son Düşüş aktifken soft drop engellenir — parça sadece sağ-sol ve sert düşüş yapabilir.
            if getattr(self, '_freeze_drop_active', False):
                soft_drop_active = False
            if soft_drop_active and getattr(self, 'gravity_freeze_timer', 0.0) <= 0:
                try:
                    soft_ms = int(self.settings_manager.get('soft_drop_speed', FAST_FALL_SPEED)) if self.settings_manager else int(FAST_FALL_SPEED)
                except Exception:
                    soft_ms = int(FAST_FALL_SPEED)
                # Keep within sane bounds; smaller = faster.
                soft_ms = max(20, min(1000, soft_ms))
                try:
                    current_ms = int(getattr(self, 'fall_speed', soft_ms) or soft_ms)
                except Exception:
                    current_ms = soft_ms
                self.fall_speed = min(current_ms, soft_ms)

            if (not soft_drop_active
                    and getattr(self, 'time_warp_timer', 0.0) <= 0
                    and getattr(self, 'gravity_freeze_timer', 0.0) <= 0):
                try:
                    target_speed = int(self.get_current_speed())
                    self._smooth_fall_speed_towards_target(target_speed, seconds)
                except Exception:
                    pass
            # Check for level-up after the main update has run. If we increased the board level,
            # prepare a selection and open the overlay.
            try:
                # Enqueue level ups that occurred during this update based on last_enqueued_level
                # so we do not double-count when notify_lines_cleared already enqueued.
                current_level = getattr(self.board, 'level', 0)
                last = getattr(self, 'last_enqueued_level', 0)
                # debug: show level detection values when debug mode enabled
                try:
                    if getattr(self, 'settings_manager', None) and self.settings_manager.get('debug_mode', False):
                        print(f"[MysteryMode] prev_level={prev_level}, current_level={current_level}, last_enqueued={last}, pending_level_ups={self.pending_level_ups}")
                except Exception:
                    pass
                lvl_delta = max(0, current_level - last)
                # Also account for level increases during this update (fallback)
                # FIX: Fallback removed because it causes double-counting when notify_lines_cleared
                # already handled the level up via last_enqueued_level updates.
                # if current_level > prev_level:
                #     fallback_delta = current_level - prev_level
                #     lvl_delta = max(lvl_delta, fallback_delta)
                if lvl_delta > 0:
                    self.pending_level_ups += lvl_delta
                    self.last_enqueued_level = current_level
                    try:
                        if self.settings_manager and self.settings_manager.get('debug_mode', False):
                            print(f"[MysteryMode] Detected level delta via update={lvl_delta}; pending_level_ups={self.pending_level_ups} (board.level={self.board.level}, last_enqueued_level={last})")
                    except Exception:
                        pass
                # If we have queued level-ups (or we detected an immediate level-up), and no selection active, prepare and open one overlay
                if not self.card_selection_active and (self.pending_level_ups > 0 or current_level > prev_level):
                    try:
                        if getattr(self, 'settings_manager', None) and self.settings_manager.get('debug_mode', False):
                            print(f"[MysteryMode] Attempting selection: pending_level_ups={self.pending_level_ups}, card_selection_active={self.card_selection_active}, game_over={self.game_over}")
                    except Exception:
                        pass
                    self.card_manager.prepare_selection()
                    try:
                        if getattr(self, 'settings_manager', None) and self.settings_manager.get('debug_mode', False):
                            print(f"[MysteryMode] prepare_selection produced {len(self.card_manager.pending_choices)} choices")
                    except Exception:
                        pass
                    if self.card_manager.pending_choices:
                        self._open_card_selection()
                    else:
                        # Nothing could be prepared - clear one pending level to avoid blocking
                        try:
                            if getattr(self, 'settings_manager', None) and self.settings_manager.get('debug_mode', False):
                                print("[MysteryMode] prepare_selection returned empty; decrementing pending_level_ups")
                        except Exception:
                            pass
                        self.pending_level_ups = max(0, self.pending_level_ups - 1)
            except Exception:
                pass

    def _update_effect_timers(self, dt: float) -> None:
        timers_changed = False
        # dt is milliseconds; convert to seconds for timer math
        seconds = dt / 1000.0
        if getattr(self, '_score_multiplier_timer', 0.0) > 0:
            self._score_multiplier_timer = max(0.0, float(self._score_multiplier_timer) - seconds)
            timers_changed = True
            if self._score_multiplier_timer == 0:
                self._score_multiplier_value = 1.0
        if self.speed_effect_timer > 0:
            self.speed_effect_timer = max(0.0, self.speed_effect_timer - seconds)
            timers_changed = True
            if self.speed_effect_timer == 0:
                self.speed_effect_multiplier = 1.0
                self.fall_speed = self.get_current_speed()
        if self.combo_aura_timer > 0:
            self.combo_aura_timer = max(0.0, self.combo_aura_timer - seconds)
            timers_changed = True
            if self.combo_aura_timer == 0:
                self.combo_aura_bonus = 0
        if timers_changed:
            self._sync_active_cards()
        # Time warp timer (slow effect) - dt is ms
        if self.time_warp_timer > 0:
            self.time_warp_timer = max(0.0, self.time_warp_timer - seconds)
            if self.time_warp_timer == 0 and hasattr(self, '_timewarp_old_speed'):
                self.fall_speed = self._timewarp_old_speed
        # Gravity freeze (chrono lock)
        if self.gravity_freeze_timer > 0:
            self.gravity_freeze_timer = max(0.0, self.gravity_freeze_timer - seconds)
            if self.gravity_freeze_timer > 0:
                self.fall_speed = int(1e9)
            else:
                self.fall_speed = self.get_current_speed()
            self._sync_active_cards()
        
        # Speed Burst timer (Hız Patlaması)
        speed_burst_timer = getattr(self, '_speed_burst_timer', 0)
        if speed_burst_timer > 0:
            self._speed_burst_timer = max(0.0, speed_burst_timer - seconds)
            if self._speed_burst_timer == 0:
                # Timer bitti, çarpanları sıfırla
                self._speed_burst_speed_mult = 1.0
                self._speed_burst_line_mult = 1.0
                self.fall_speed = self.get_current_speed()
                # Aktif efekt görselini kaldır
                try:
                    if hasattr(self, '_active_effect_visuals'):
                        self._active_effect_visuals = [
                            v for v in self._active_effect_visuals 
                            if not (v.get('id', '') or '').startswith('speed_burst')
                        ]
                except Exception:
                    pass
                self._sync_active_cards()

        # Son Düşüş (Freeze Drop) timer
        if getattr(self, '_freeze_drop_active', False) and getattr(self, '_freeze_drop_timer', 0.0) > 0:
            self._freeze_drop_timer = max(0.0, self._freeze_drop_timer - seconds)
            if self._freeze_drop_timer > 0:
                # Yerçekimini durdur — parça düşmez
                self.fall_speed = int(1e9)
            else:
                # Süre doldu, donma biter
                self._freeze_drop_active = False
                piece = getattr(self, 'current_piece', None)
                if piece is not None:
                    setattr(piece, '_frozen', False)
                    orig = getattr(piece, '_original_color', None)
                    if orig:
                        piece.color = orig
                        try:
                            delattr(piece, '_force_color')
                        except Exception:
                            pass
                self.fall_speed = self.get_current_speed()
                try:
                    self.card_message = "❄️ Dondurma süresi doldu!"
                    self.card_message_timer = 1.0
                except Exception:
                    pass
            self._sync_active_cards()

    def handle_input(self) -> bool:
        if self.card_selection_active:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return False
                # Handle mousewheel for scrolling while selection is active
                if event.type == pygame.MOUSEWHEEL:
                    try:
                        self.card_ui.handle_mouse_wheel(event.y)
                    except Exception:
                        pass
                if event.type == pygame.MOUSEMOTION:
                    # update hover states using the card_ui helper
                    try:
                        pos = normalize_mouse_pos(getattr(event, 'pos', None)) or event.pos
                        self.card_ui.handle_mouse_move(pos)
                    except Exception:
                        pass
                if event.type == pygame.KEYDOWN:
                    # ESC: continue without taking a card (same as clicking SKIP)
                    if event.key == pygame.K_ESCAPE:
                        try:
                            self.card_manager.pending_choices = []
                        except Exception:
                            pass
                        self._close_card_selection()
                    # Navigation in debug mode: more selections via numbers 1..9 and scrolling
                    elif self.settings_manager and self.settings_manager.get('card_mode_debug', False):
                        # Page up/down or arrow keys can scroll the grid
                        if event.key in (pygame.K_PAGEUP, pygame.K_UP):
                            try:
                                self.card_ui.handle_mouse_wheel(1)
                            except Exception:
                                pass
                            continue
                        elif event.key in (pygame.K_PAGEDOWN, pygame.K_DOWN):
                            try:
                                self.card_ui.handle_mouse_wheel(-1)
                            except Exception:
                                pass
                            continue
                        for n in range(1, 10):
                            key = getattr(pygame, f'K_{n}')
                            kp = getattr(pygame, f'K_KP{n}') if hasattr(pygame, f'K_KP{n}') else None
                            if event.key in (key, kp):
                                self._select_card(n - 1)
                                break
                    else:
                        # Press 'R' to pick a random pending card
                        if event.key == pygame.K_r:
                            if self.card_manager.pending_choices:
                                idx = random.randint(0, len(self.card_manager.pending_choices) - 1)
                                self._select_card(idx)
                            continue
                        if event.key in (pygame.K_1, pygame.K_KP1):
                            self._select_card(0)
                        elif event.key in (pygame.K_2, pygame.K_KP2):
                            self._select_card(1)
                        elif event.key in (pygame.K_3, pygame.K_KP3):
                            self._select_card(2)
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    pos = normalize_mouse_pos(getattr(event, 'pos', None)) or event.pos
                    choice = self.card_ui.handle_mouse_click(pos)
                    if choice is not None:
                        if choice == 'SKIP':
                            # Kart seçmeden devam: seçim UI'yi kapat ve seçenekleri temizle.
                            try:
                                self.card_manager.pending_choices = []
                            except Exception:
                                pass
                            self._close_card_selection()
                        elif choice == 'REROLL':
                            # Kart havuzunu yeniden çek; overlay açık kalır.
                            try:
                                self.card_manager.prepare_selection()
                            except Exception:
                                pass
                            self.card_ui.reset()
                        elif choice == 'PEEK':
                            # Peek moduna geçiş/çıkış - sadece UI durumu değişir, burada ek işlem yok
                            pass
                        elif choice == 'RANDOM':
                            # Random selection among pending choices
                            if self.card_manager.pending_choices:
                                idx = random.randint(0, len(self.card_manager.pending_choices) - 1)
                                self._select_card(idx)
                        else:
                            self._select_card(choice)
                elif event.type == pygame.MOUSEMOTION:
                    # update hover states even when grid scrolled
                    # this ballot uses the card_rects set by draw_selection_overlay
                    pass
            return True
        
        # === PARÇA SEÇİM POPUP: Geleceği Değiştiren kartı için ===
        if getattr(self, '_piece_selection_active', False):
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return False
                
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    # ESC ile popup'ı kapat (kalan haklar kaybolur)
                    self._close_piece_selection_popup()
                    self._future_changer_remaining = 0
                    try:
                        self.card_message = "Parça seçimi iptal edildi."
                        self.card_message_timer = 1.0
                    except Exception:
                        pass
                    continue
                
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    pos = normalize_mouse_pos(getattr(event, 'pos', None)) or event.pos
                    if self._handle_piece_selection_click(pos):
                        continue
            return True

        # === BLOK ATÖLYESİ KARTI POPUP ===
        if getattr(self, '_card_workshop_active', False):
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return False
                if self._handle_card_workshop_input(event):
                    continue
            return True
        
        # === SNIPER OVERLAY MODE: Gelişmiş blok seçim sistemi ===
        if getattr(self, '_sniper_overlay_active', False):
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return False
                    
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    # ESC ile overlay'i kapat (hak harcanmaz)
                    self._close_sniper_overlay()
                    continue
                    
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    # Sol tık - blok patlatma
                    pos = normalize_mouse_pos(getattr(event, 'pos', None)) or event.pos
                    cell = self._sniper_screen_to_cell(pos)
                    
                    if cell:
                        cx, cy = cell
                        # Tıklanan hücrede blok var mı kontrol et
                        if self.board.occupancy[cy][cx]:
                            self._execute_sniper_shot(cx, cy)
                        else:
                            try:
                                self.card_message = "Bos hucre! Dolu bir bloga tikla."
                                self.card_message_timer = 1.5
                                # Hata sesi
                                if self.sound_enabled:
                                    self.sound.play_sound("deny")
                            except Exception:
                                pass
                    else:
                        try:
                            self.card_message = "Oyun alani disinda! Tahta icindeki bloklari hedefleyin."
                            self.card_message_timer = 1.5
                            # Hata sesi
                            if self.sound_enabled:
                                self.sound.play_sound("deny")
                        except Exception:
                            pass
                    continue
                    
                # Mouse hareket takibi artık draw fonksiyonunda yapılıyor
                # Bu daha smooth cursor hareketi sağlıyor
                    
            return True
        
        # NERF: Drill parça kilitliyken döndürme tuşunu engelle
        drill_locked = getattr(self, '_drill_movement_locked', False)
        piece = getattr(self, 'current_piece', None)
        is_drill_piece = piece and getattr(piece, 'drill', False)
        
        # Geri Sarma tuşu kontrolü (U tuşu) - normal gameplay sırasında
        for event in pygame.event.get():
            # Drill parça kilitliyken döndürme tuşunu tüket (engelle)
            if drill_locked and is_drill_piece:
                if event.type == pygame.KEYDOWN:
                    rotate_key = self.control_bindings.get('rotate', pygame.K_UP)
                    if event.key == rotate_key:
                        # Döndürme engellendi, event'i yutuyoruz
                        continue
            
            # B tuşunu yut - MysteryMode B'yi kendi update() metodunda yönetiyor
            if event.type == pygame.KEYDOWN and event.key == pygame.K_b:
                # Base game'in B handler'ına geçirme
                continue
            
            # Event'i tekrar kuyruğa koy ki super().handle_input() işlesin
            pygame.event.post(event)
            if event.type == pygame.KEYDOWN and event.key == pygame.K_u:
                if not self.game_over and not self.paused:
                    if self._do_rewind():
                        # Rewind başarılı, event'i tüket
                        continue
            # N tuşu: Keskin Nişancı overlay'ini aç
            if event.type == pygame.KEYDOWN and event.key == pygame.K_n:
                if not self.game_over and not self.paused:
                    if self._open_sniper_overlay():
                        continue
            # T tuşu: Zaman Kapsulu kaydet
            # R tuşu: Zaman Kapsulu toggle (ilk basış kaydet, ikinci basış geri yükle)
            if event.type == pygame.KEYDOWN and event.key == pygame.K_r:
                if not self.game_over and not self.paused and not self.card_selection_active:
                    if self._toggle_time_capsule():
                        continue
        
        # Gamepad action kontrolü (event loop dışında)
        if not self.game_over and not self.paused:
            try:
                from gamepad_manager import gamepad_manager
                if gamepad_manager and gamepad_manager.enabled:
                    # Zaman Kapsulu Toggle: save/restore actionlarından biri tetiklenirse tek akış çalışır
                    if not self.card_selection_active:
                        tc_pressed = (
                            gamepad_manager.was_action_just_pressed('card_time_capsule_save')
                            or gamepad_manager.was_action_just_pressed('card_time_capsule_restore')
                        )
                        if tc_pressed:
                            self._toggle_time_capsule()
                            return True
            except Exception:
                pass
        
        # Normal gameplay input handling
        return super().handle_input()

    def restart(self):
        """Reset Mystery mode specific state on restart."""
        # ÖNEMLİ: perk_manager'ı super().restart()'tan ÖNCE sıfırla!
        # Çünkü super().restart() → spawn_new_piece() → perk_manager.on_piece_spawn()
        # çağırır ve eski perk_manager'daki aktif perkler (ör: flexible_border) 
        # yeni parçalara uygulanır.
        self.perk_manager = PerkManager(self)
        # card_manager'ı da ÖNCE sıfırla (forced piece queue eski oyundan kalmasın)
        self.card_manager.reset()
        # Esnek sınır kartını sıfırla (board flag - super().restart() yeni board yaratmadan önce)
        if hasattr(self, 'board') and self.board is not None:
            self.board.flexible_border_active = False
        super().restart()
        # Reset remaining state
        self.selected_cards_log = []
        self.card_selection_active = False
        self.card_message = ""
        self.card_message_timer = 0.0
        self.card_selection_rects = []
        self._pending_card_choice_index = None
        self.pending_level_ups = 0
        self.last_enqueued_level = getattr(self.board, 'level', 0)
        # Reset effect timers and visuals
        self.speed_effect_timer = 0.0
        self.speed_effect_multiplier = 1.0
        self.line_bonus_remaining = 0
        self.line_bonus_amount = 0
        self.combo_aura_timer = 0.0
        self.combo_aura_bonus = 0
        self._active_effect_visuals = {}
        self.tunnel_charges_remaining = 0
        self.hammer_charges_remaining = 0
        # Son Düşüş sıfırla
        self._freeze_drop_charges = 0
        self._freeze_drop_duration = 0
        self._freeze_drop_timer = 0.0
        self._freeze_drop_active = False
        
        # Zaman Kapsulu sifirla
        self.time_capsule_saved = False
        self.time_capsule_data = None
        self.time_capsule_available = False
        self.bomb_master_charges = 0  # Bomba Ustası M tuşu hakları
        self._hold_destroyer_charges = 0  # Tuttuğunu Koparan B tuşu hakları
        # Mystery modunda B tuşu kartlara bağlı, base game'in 5 hakkını devre dışı bırak
        self.discard_held_uses = 0
        # Blok Atölyesi popup sıfırla
        self._card_workshop_active = False
        self._card_workshop_grid = None
        self._card_workshop_cursor_x = 0
        self._card_workshop_cursor_y = 0
        # Geri Sarma state'i sıfırla
        self._rewind_available = False
        self._last_placed_piece = None
        self._sync_active_cards()
        # Perk manager
        self.perk_manager = PerkManager(self)
        self.gravity_freeze_timer = 0.0
        self.phase_used_for_piece = False
        # Phase shift (shape mutation) per-run usage limit
        self.phase_shift_uses_remaining = 0
        self._last_ability_keys = {'z': False, 'x': False, 'g': False, 'h': False, 'm': False, 'c': False, 'v': False, 'rotate': False, 'lshift': False, 'b': False, 'f': False}
        # Shape mutation cooldown
        self._shape_mutation_cooldown = 0.0
        # Hız seviyesi
        self.speed_level = 10
        self._last_speed_milestone = 0
        self.score_speed_multiplier = 1.0
        self._last_score_speed_milestone = 0
        self._speedup_smooth_time = 0.8
        # Drill hareket kilidi sıfırla
        self._drill_movement_locked = False
        # Sniper modu sıfırla
        self._sniper_charges = 0
        self._sniper_overlay_active = False
        self._sniper_card = None
        self._sniper_hover_pos = None
        self._active_sniper_explosions = []

    def _try_move_left(self):
        """Sola hareket - Drill parça kilitliyse engelle"""
        # NERF: Drill parça bloğa değdiyse hareket engellenir
        if getattr(self, '_drill_movement_locked', False):
            piece = getattr(self, 'current_piece', None)
            if piece and getattr(piece, 'drill', False):
                return False
        return super()._try_move_left()

    def _try_move_right(self):
        """Sağa hareket - Drill parça kilitliyse engelle"""
        # NERF: Drill parça bloğa değdiyse hareket engellenir
        if getattr(self, '_drill_movement_locked', False):
            piece = getattr(self, 'current_piece', None)
            if piece and getattr(piece, 'drill', False):
                return False
        return super()._try_move_right()

    def _smooth_fall_speed_towards_target(self, target_ms: int, seconds: float) -> None:
        if seconds <= 0:
            return
        try:
            target = int(target_ms)
        except Exception:
            return
        try:
            current = int(getattr(self, 'fall_speed', target) or target)
        except Exception:
            current = target

        # Only smooth speed-ups (smaller interval => faster). Slowdowns can snap.
        if target >= current:
            try:
                self.fall_speed = target
            except Exception:
                pass
            return

        try:
            smooth_time = float(getattr(self, '_speedup_smooth_time', 0.8) or 0.8)
        except Exception:
            smooth_time = 0.8
        smooth_time = max(0.05, smooth_time)
        alpha = min(1.0, float(seconds) / smooth_time)
        next_val = int(round(current + (target - current) * alpha))
        # Guard against overshoot due to rounding.
        next_val = max(target, min(current, next_val))
        try:
            self.fall_speed = next_val
        except Exception:
            pass

    def draw_mode_overlay(self) -> None:
        self._ensure_card_ui_fonts()
        # Card selection overlay should be visually clean: hide the status panel
        # (it reads like an extra black overlay/band above the selection UI).
        if not self.card_selection_active:
            self._draw_status_panel()
            # Base Game.draw() only calls draw_mode_overlay().
            # To ensure the left-panel active cards are always visible in gameplay,
            # draw them from here as the single render entry-point.
            try:
                self.draw_mode_info(0, 0)
                self._draw_persistent_cards_icon_panel()
            except Exception as exc:
                try:
                    if getattr(self, 'settings_manager', None) and self.settings_manager.get('debug_mode', False):
                        print(f"[MysteryMode] draw_mode_info failed: {exc!r}")
                except Exception:
                    pass
        
        if self.card_selection_active:
            # Kart seçimi ekranı açıldığında da sol panel (aktif kartlar/perkler)
            # görünür kalmalı.
            try:
                self.draw_mode_info(0, 0)
                self._draw_persistent_cards_icon_panel()
            except Exception as exc:
                try:
                    if getattr(self, 'settings_manager', None) and self.settings_manager.get('debug_mode', False):
                        print(f"[MysteryMode] draw_mode_info failed (overlay): {exc!r}")
                except Exception:
                    pass
            fonts = {
                "large": self.mystery_font_large,
                "medium": self.mystery_font_medium,
                "small": self.mystery_font_small,
                "card_title": self.card_font,
                "desc": self.card_desc_font,
                "value": self.card_value_font,
                "icon": self.card_icon_font,
                "tag": self.card_tag_font,
            }
            self.card_ui.draw_selection_overlay(
                self.screen,
                self.window_width,
                self.window_height,
                fonts,
                self.card_manager.pending_choices,
                self.card_manager.get_selection_hint(),
                bool(self.settings_manager.get('card_mode_debug', False)),
            )
        elif self.card_message and self.card_message_timer > 0 and not getattr(self, '_sniper_overlay_active', False):
            max_width = max(220, int(self.window_width - 48))
            message = retro_style.render_fit_text(
                self.card_message,
                (255, 255, 255),
                max_width,
                22,
                bold=True,
            )
            rect = message.get_rect(center=(self.window_width // 2, 44))
            self.screen.blit(message, rect)
        
        # === SNIPER OVERLAY: Oyun alanı üzerinde blok seçim modu ===
        if getattr(self, '_sniper_overlay_active', False):
            self._draw_sniper_board_overlay()

        # Sniper ile patlatılan blokların bulunduğu hücrede GIF patlama efekti
        self._draw_sniper_explosion_effects()
        
        # === PARÇA SEÇİM POPUP: Geleceği Değiştiren kartı için ===
        if getattr(self, '_piece_selection_active', False):
            self._draw_piece_selection_popup()
        
        # === BLOK ATÖLYESİ POPUP: Blok Atölyesi kartı için ===
        if getattr(self, '_card_workshop_active', False):
            self._draw_card_workshop_popup()
    
    def _draw_sniper_board_overlay(self) -> None:
        """Sniper modu için gelişmiş blok seçim overlay'i."""
        try:
            # Mevcut tahta parametreleri
            board_x, board_y = self.get_board_offset()
            cell_size = self.get_cell_size()
            
            # === MOUSE SINIRLANDIRMA ===
            # Mouse'u oyun alanı içinde tut
            board_width = self.board.width * cell_size
            board_height = self.board.height * cell_size
            
            # Normalize: fiziksel piksel uzayında çalış (board koordinatları fiziksel)
            mouse_x, mouse_y = get_mouse_pos()
            clamped_x = max(board_x, min(mouse_x, board_x + board_width - 1))
            clamped_y = max(board_y, min(mouse_y, board_y + board_height - 1))
            
            if mouse_x != clamped_x or mouse_y != clamped_y:
                # set_pos logical space bekler — fiziksel → logical çevir
                scale = get_display_scale_factor()
                pygame.mouse.set_pos(int(clamped_x / scale), int(clamped_y / scale))
            
            mouse_pos = (clamped_x, clamped_y)
            self._sniper_hover_pos = mouse_pos
            
            # === FULL SCREEN DARK OVERLAY ===
            dim_overlay = pygame.Surface((self.window_width, self.window_height), pygame.SRCALPHA)
            dim_overlay.fill((0, 0, 0, 120))
            self.screen.blit(dim_overlay, (0, 0))
            
            # === BOARD HIGHLIGHT FRAME ===
            board_rect = pygame.Rect(
                board_x - 6, 
                board_y - 6, 
                board_width + 12, 
                board_height + 12
            )
            
            # Animated glow effect
            import time
            glow_intensity = int(abs(math.sin(time.time() * 3)) * 50 + 100)
            
            # Multi-layer glow using retro style colors
            for i in range(3):
                glow_rect = board_rect.inflate(i * 4, i * 4)
                glow_color = (*retro_style.primary, 80 - i * 20)
                pygame.draw.rect(self.screen, glow_color, glow_rect, 2, border_radius=4)
            
            # Main border using retro style
            pygame.draw.rect(self.screen, retro_style.primary, board_rect, 3, border_radius=2)
            
            # === GRID OVERLAY FOR BETTER TARGETING ===
            grid_color = (*retro_style.grid_color, 60)
            for x in range(self.board.width + 1):
                line_x = board_x + x * cell_size
                pygame.draw.line(self.screen, grid_color, 
                               (line_x, board_y), 
                               (line_x, board_y + board_height), 1)
            
            for y in range(self.board.height + 1):
                line_y = board_y + y * cell_size
                pygame.draw.line(self.screen, grid_color, 
                               (board_x, line_y), 
                               (board_x + board_width, line_y), 1)
            
            # === TARGET CELL HIGHLIGHTING ===
            cell = self._sniper_screen_to_cell(mouse_pos)
            target_valid = False
            
            if cell:
                cx, cy = cell
                screen_x = board_x + cx * cell_size
                screen_y = board_y + cy * cell_size
                target_rect = pygame.Rect(screen_x, screen_y, cell_size, cell_size)
                
                if self.board.occupancy[cy][cx]:
                    target_valid = True
                    # === VALID TARGET: ANIMATED HIGHLIGHT ===
                    
                    # Pulsing glow effect
                    pulse = abs(math.sin(time.time() * 4)) * 0.5 + 0.5
                    glow_alpha = int(100 + pulse * 100)
                    
                    # Outer glow (expanding)
                    glow_size = int(cell_size + 8 + pulse * 8)
                    glow_surf = pygame.Surface((glow_size, glow_size), pygame.SRCALPHA)
                    glow_center = glow_size // 2
                    
                    # Radial gradient glow using accent color
                    for r in range(glow_center, 0, -2):
                        alpha = int(glow_alpha * (1 - r / glow_center) * 0.8)
                        if alpha > 0:
                            pygame.draw.circle(glow_surf, (*retro_style.accent, alpha), 
                                             (glow_center, glow_center), r)
                    
                    glow_x = screen_x - (glow_size - cell_size) // 2
                    glow_y = screen_y - (glow_size - cell_size) // 2
                    self.screen.blit(glow_surf, (glow_x, glow_y))
                    
                    # Target highlight
                    highlight = pygame.Surface((cell_size, cell_size), pygame.SRCALPHA)
                    highlight.fill((*retro_style.accent, int(150 + pulse * 50)))
                    self.screen.blit(highlight, target_rect.topleft)
                    
                    # Animated border
                    border_width = int(3 + pulse * 2)
                    pygame.draw.rect(self.screen, retro_style.text_primary, target_rect, border_width)
                    
                    # Professional crosshair
                    center_x = screen_x + cell_size // 2
                    center_y = screen_y + cell_size // 2
                    
                    # Crosshair arms
                    arm_length = cell_size // 2 + 6
                    line_width = 3
                    
                    # Horizontal line with gap in center
                    gap = 8
                    pygame.draw.line(self.screen, retro_style.text_primary, 
                                   (center_x - arm_length, center_y), 
                                   (center_x - gap, center_y), line_width)
                    pygame.draw.line(self.screen, retro_style.text_primary, 
                                   (center_x + gap, center_y), 
                                   (center_x + arm_length, center_y), line_width)
                    
                    # Vertical line with gap in center
                    pygame.draw.line(self.screen, retro_style.text_primary, 
                                   (center_x, center_y - arm_length), 
                                   (center_x, center_y - gap), line_width)
                    pygame.draw.line(self.screen, retro_style.text_primary, 
                                   (center_x, center_y + gap), 
                                   (center_x, center_y + arm_length), line_width)
                    
                    # Center dot
                    pygame.draw.circle(self.screen, retro_style.secondary, (center_x, center_y), 6)
                    pygame.draw.circle(self.screen, retro_style.text_primary, (center_x, center_y), 6, 2)
                    pygame.draw.circle(self.screen, retro_style.secondary, (center_x, center_y), 2)
                    
                else:
                    # === INVALID TARGET: SUBTLE INDICATION ===
                    pygame.draw.rect(self.screen, (*retro_style.text_muted, 100), target_rect)
                    pygame.draw.rect(self.screen, retro_style.text_muted, target_rect, 2)
            
            # === CUSTOM CURSOR ===
            # Hide system cursor and draw custom one
            pygame.mouse.set_visible(False)
            
            # Draw custom crosshair cursor
            cursor_x, cursor_y = mouse_pos
            cursor_color = retro_style.primary if target_valid else retro_style.text_secondary
            cursor_size = 20
            
            # Cursor crosshair
            pygame.draw.line(self.screen, cursor_color, 
                           (cursor_x - cursor_size, cursor_y), 
                           (cursor_x + cursor_size, cursor_y), 2)
            pygame.draw.line(self.screen, cursor_color, 
                           (cursor_x, cursor_y - cursor_size), 
                           (cursor_x, cursor_y + cursor_size), 2)
            
            # Cursor center dot
            pygame.draw.circle(self.screen, cursor_color, (cursor_x, cursor_y), 3)
            pygame.draw.circle(self.screen, retro_style.bg_color, (cursor_x, cursor_y), 3, 1)
            
            # === INSTRUCTION PANEL ===
            self._draw_sniper_instructions(board_x, board_y, cell_size, target_valid)
                
        except Exception as e:
            try:
                if getattr(self, 'settings_manager', None) and self.settings_manager.get('debug_mode', False):
                    print(f"[Sniper Overlay Error] {e}")
            except Exception:
                pass
    
    def _draw_sniper_instructions(self, board_x: int, board_y: int, cell_size: int, target_valid: bool) -> None:
        """Sniper modu için ana UI temasına uygun talimat paneli çizer."""
        try:
            # Sağ HUD panelinin stats kutusunun altındaki boş alana yerleştir
            # _hud_mode_info_area = (x, y, w, h) — Kombo/Stats paneli bittikten sonraki alan
            mode_area = getattr(self, '_hud_mode_info_area', None)
            if mode_area and mode_area[3] >= 60:
                area_x, area_y, area_w, area_h = mode_area
                panel_x = area_x
                # Ekran sağ kenarına kadar genişlet
                panel_width = int(self.window_width) - area_x - 8
                # İçeriğe sıkı fit: 3 satır metin + üst/alt padding + aralar
                desired_panel_h = 120
                panel_y = area_y + 4
            else:
                # Fallback: tahtanın altı
                board_pixel_h = self.board.height * cell_size
                panel_y = board_y + board_pixel_h + 10
                panel_x = board_x
                panel_width = self.board.width * cell_size
                desired_panel_h = 110
                panel_y = max(8, min(panel_y, self.window_height - desired_panel_h - 8))

            panel_height = desired_panel_h
            
            # Panel rect
            panel_rect = pygame.Rect(panel_x, panel_y, panel_width, panel_height)
            
            # Opak (saydam olmayan) koyu arka plan
            pygame.draw.rect(self.screen, (18, 22, 38), panel_rect, border_radius=10)
            border_col = retro_style.primary if hasattr(retro_style, 'primary') else (80, 120, 220)
            pygame.draw.rect(self.screen, border_col, panel_rect, 2, border_radius=10)
            
            # Instructions text — büyük fontlar
            font = retro_style.get_font(26, bold=True)
            small_font = retro_style.get_font(22)
            
            if target_valid:
                main_text = "SOL TIKLAYARAK BLOGU PATLAT"
                main_color = retro_style.success
                sub_text = "Hedef kilitlendi! Tikla ve yok et."
                sub_color = retro_style.text_primary
            else:
                main_text = "DOLU BIR BLOGA NISAN AL"
                main_color = retro_style.accent
                sub_text = "Mouse'u dolu bloklarin uzerine getir"
                sub_color = retro_style.text_secondary
            
            # Charges remaining (sağ üst köşe)
            charges = int(getattr(self, '_sniper_charges', 0) or 0)
            charge_bg_rect = None
            charge_rect = None
            if charges > 0:
                charge_text = f"Kalan: {charges}"
                charge_surf = small_font.render(charge_text, True, retro_style.primary)
                charge_rect = charge_surf.get_rect(right=panel_rect.right - 15, y=panel_rect.y + 12)
                
                # Charge indicator background
                charge_bg_rect = charge_rect.inflate(14, 8)
                charge_bg_surf = pygame.Surface(charge_bg_rect.size, pygame.SRCALPHA)
                charge_bg_surf.fill((*retro_style.primary, 40))
                pygame.draw.rect(charge_bg_surf, retro_style.primary, charge_bg_surf.get_rect(), 1, border_radius=8)
                self.screen.blit(charge_bg_surf, charge_bg_rect.topleft)
                
                self.screen.blit(charge_surf, charge_rect)

            # Metin alanı: sağdaki "Kalan" rozetiyle çakışmasın
            text_left = panel_rect.x + 14
            text_right = panel_rect.right - 14
            if charge_bg_rect is not None:
                text_right = min(text_right, charge_bg_rect.left - 10)
            text_max_width = max(140, text_right - text_left)
            text_center_x = text_left + text_max_width // 2

            # Main instruction
            main_surf = retro_style.render_fit_text(main_text, main_color, text_max_width, 26, bold=True)
            main_rect = main_surf.get_rect(centerx=text_center_x, y=panel_rect.y + 12)
            self.screen.blit(main_surf, main_rect)

            # Sub instruction
            sub_surf = retro_style.render_fit_text(sub_text, sub_color, text_max_width, 21, bold=False)
            sub_rect = sub_surf.get_rect(centerx=text_center_x, y=main_rect.bottom + 8)
            self.screen.blit(sub_surf, sub_rect)

            # Cancel instruction
            cancel_text = "ESC: Iptal Et"
            cancel_surf = retro_style.render_fit_text(cancel_text, retro_style.text_muted, text_max_width, 19, bold=False)
            cancel_rect = cancel_surf.get_rect(centerx=text_center_x, y=sub_rect.bottom + 8)
            self.screen.blit(cancel_surf, cancel_rect)
                
        except Exception:
            pass

    def _ensure_sniper_explosion_assets(self) -> bool:
        """Sniper patlama GIF frame'lerini bir kez yükler."""
        if getattr(self, '_sniper_explosion_ready', False):
            return bool(getattr(self, '_sniper_explosion_frames', []))

        self._sniper_explosion_ready = True
        self._sniper_explosion_frames = []
        self._sniper_explosion_frame_durations_ms = []
        self._sniper_explosion_total_duration_ms = 0

        gif_path = os.path.join(ANIMATE_EFFECTS_DIR, 'sniper_effect.gif')
        if not os.path.exists(gif_path):
            return False

        if Image is None or ImageSequence is None:
            return False

        try:
            with Image.open(gif_path) as gif:
                for frame in ImageSequence.Iterator(gif):
                    rgba = frame.convert('RGBA')
                    duration = int(frame.info.get('duration', 50) or 50)
                    if duration <= 0:
                        duration = 50
                    duration = max(20, int(duration / SNIPER_EXPLOSION_SPEED_MULTIPLIER))
                    surf = pygame.image.fromstring(rgba.tobytes(), rgba.size, 'RGBA').convert_alpha()
                    self._sniper_explosion_frames.append(surf)
                    self._sniper_explosion_frame_durations_ms.append(duration)
        except Exception:
            self._sniper_explosion_frames = []
            self._sniper_explosion_frame_durations_ms = []
            self._sniper_explosion_total_duration_ms = 0
            return False

        self._sniper_explosion_total_duration_ms = int(sum(self._sniper_explosion_frame_durations_ms))
        return bool(self._sniper_explosion_frames) and self._sniper_explosion_total_duration_ms > 0

    def _spawn_sniper_explosion(self, cx: int, cy: int) -> None:
        """Belirtilen hücrede sniper patlama animasyonunu başlatır."""
        if not self._ensure_sniper_explosion_assets():
            return
        try:
            self._active_sniper_explosions.append({
                'cx': int(cx),
                'cy': int(cy),
                'start_ms': int(pygame.time.get_ticks()),
            })
        except Exception:
            pass

    def _draw_sniper_explosion_effects(self) -> None:
        """Aktif sniper patlama efektlerini patlayan blok konumunda çizer."""
        if not getattr(self, '_active_sniper_explosions', None):
            return
        if not self._ensure_sniper_explosion_assets():
            self._active_sniper_explosions = []
            return

        frames = getattr(self, '_sniper_explosion_frames', [])
        durations = getattr(self, '_sniper_explosion_frame_durations_ms', [])
        total = int(getattr(self, '_sniper_explosion_total_duration_ms', 0) or 0)
        if not frames or not durations or total <= 0:
            self._active_sniper_explosions = []
            return

        now_ms = int(pygame.time.get_ticks())
        board_x, board_y = self.get_board_offset()
        cell_size = self.get_cell_size()
        alive: List[Dict[str, Any]] = []

        for fx in self._active_sniper_explosions:
            try:
                elapsed = now_ms - int(fx.get('start_ms', now_ms))
                if elapsed < 0 or elapsed >= total:
                    continue

                acc = 0
                frame_idx = 0
                for i, d in enumerate(durations):
                    acc += int(d)
                    if elapsed < acc:
                        frame_idx = i
                        break

                src = frames[min(frame_idx, len(frames) - 1)]
                target_size = max(12, int(cell_size * 1.8))
                if src.get_width() != target_size or src.get_height() != target_size:
                    frame = pygame.transform.smoothscale(src, (target_size, target_size))
                else:
                    frame = src

                cx = int(fx.get('cx', 0))
                cy = int(fx.get('cy', 0))
                center_x = board_x + cx * cell_size + cell_size // 2
                center_y = board_y + cy * cell_size + cell_size // 2
                draw_x = center_x - frame.get_width() // 2
                draw_y = center_y - frame.get_height() // 2
                self.screen.blit(frame, (draw_x, draw_y))

                alive.append(fx)
            except Exception:
                continue

        self._active_sniper_explosions = alive
    
    def draw_mode_info(self, info_x: int, info_y: int) -> int:
        # Ensure active cards list is up-to-date for the HUD panel.
        try:
            self._sync_active_cards()
        except Exception:
            pass
        panel_x, _, panel_width = self._left_panel_frame
        cards_y = getattr(self, "_left_panel_cards_y", info_y)
        cards_x = getattr(self, "_left_panel_content_x", panel_x + 16)
        cards_width = getattr(self, "_left_panel_content_width", panel_width - 32)
        # Ensure title and cards y do not overlap with top panel
        min_cards_y = getattr(self, "_left_panel_cards_y", info_y)
        if cards_y < min_cards_y:
            cards_y = min_cards_y
        active_cards = list(getattr(self.card_manager, 'active_cards', []) or [])
        # Limited cards should only show while they are active.
        effects = [c for c in active_cards if not bool(c.get('persistent', False))]

        fonts = {
            "small": self.mystery_font_small,
            "desc": self.card_desc_font,
            "tag": self.card_tag_font,
            "card_title": self.card_font,
            "icon": self.card_icon_font,
        }

        ui_scale = self._card_ui_scale()

        # Draw a container panel for the "selected/active cards" area.
        # This shares the same glass-panel base as the level box and right HUD.
        pad_x = max(10, int(15 * ui_scale))
        pad_top = max(8, int(12 * ui_scale))
        pad_bottom = max(8, int(12 * ui_scale))
        hud_panel = getattr(self, '_hud_panel_rect', None)
        if hud_panel is not None:
            try:
                target_bottom = int(getattr(hud_panel, 'bottom', self.window_height - 30))
            except Exception:
                target_bottom = self.window_height - 30
        else:
            target_bottom = self.window_height - 30
        panel_h = max(0, int(target_bottom - cards_y))
        cards_panel_rect = pygame.Rect(panel_x, cards_y, panel_width, panel_h)
        try:
            self._draw_hud_glass_panel(cards_panel_rect)
        except Exception:
            retro_style.draw_glass_panel(self.screen, cards_panel_rect, alpha=90, border_color=(60, 70, 90))

        inner_x = panel_x + pad_x
        inner_w = max(160, panel_width - pad_x * 2)
        y_cursor = cards_panel_rect.y + pad_top
        height = cards_panel_rect.height

        header = self.mystery_font_small.render(t('cards'), True, (220, 230, 255))
        self.screen.blit(header, (inner_x, y_cursor))
        y_cursor += header.get_height() + max(6, int(10 * ui_scale))

        label_fx = self.mystery_font_small.render(t('card_type_limited'), True, (180, 200, 220))
        self.screen.blit(label_fx, (inner_x, y_cursor))
        y_cursor += label_fx.get_height() + max(5, int(8 * ui_scale))
        effects_h = self.card_ui.draw_active_cards_panel(
            self.screen,
            effects,
            fonts,
            inner_x,
            y_cursor,
            inner_w,
            max_display=10,
            placeholder_text=t('card_placeholder_no_limited'),
            columns=1,
        )
        y_cursor += effects_h + max(8, int(12 * ui_scale))

        # Draw level progress bar (segmented for 5 lines)
        bar_x = inner_x
        bar_y = y_cursor
        bar_width = inner_w
        bar_height = max(8, int(12 * ui_scale))
        
        # Progress calculation for level up (5 lines per level)
        progress = int(getattr(self.card_manager, 'progress', 0))
        threshold = int(getattr(self.card_manager, 'threshold', 5))
        if threshold < 1: threshold = 5
        
        # Calculate segment geometry
        gap = 3
        total_gaps = max(0, (threshold - 1) * gap)
        segment_w = max(4, (bar_width - total_gaps) // threshold)
        
        # Draw segments
        for i in range(threshold):
            seg_x = bar_x + i * (segment_w + gap)
            # Background for segment
            pygame.draw.rect(self.screen, (30, 30, 30), (seg_x, bar_y, segment_w, bar_height), border_radius=4)
            
            # Fill if completed/active
            if i < progress:
                # Fill with accent color
                pygame.draw.rect(self.screen, self.mode_skin.accent, (seg_x + 1, bar_y + 1, segment_w - 2, bar_height - 2), border_radius=3)
        
        height += bar_height + 12
        return height

    def _draw_persistent_cards_icon_panel(self) -> None:
        active_cards = list(getattr(self.card_manager, 'active_cards', []) or [])
        history_cards = list(getattr(self, 'selected_cards_log', []) or [])
        ui_scale = self._card_ui_scale()
        s = lambda v, minimum=1: max(minimum, int(round(v * ui_scale)))

        active_by_id: Dict[str, Dict[str, Any]] = {}
        for card in active_cards:
            card_id = str(card.get('id') or '')
            if card_id and bool(card.get('persistent', False)):
                active_by_id[card_id] = card

        perks: List[Dict[str, Any]] = []
        seen: set[str] = set()
        for card in history_cards:
            card_id = str(card.get('id') or '')
            if not card_id or card_id in seen or not bool(card.get('persistent', False)):
                continue
            perks.append(active_by_id.get(card_id, card))
            seen.add(card_id)
        for card in active_cards:
            card_id = str(card.get('id') or '')
            if not card_id or card_id in seen or not bool(card.get('persistent', False)):
                continue
            perks.append(card)
            seen.add(card_id)

        board_x, board_y = self.get_board_offset()
        cell_size = self.get_cell_size()
        board_w = self.board_width * cell_size
        board_h = self.board_height * cell_size

        panel_gap_top = s(12)
        panel_gap_bottom = s(10)
        panel_h_max = s(66)
        panel_h_min = s(42)
        available_below = int(self.window_height - (board_y + board_h) - panel_gap_top - panel_gap_bottom)
        if available_below < panel_h_min:
            return

        desired_w = int(board_w + s(260))
        panel_w = max(int(board_w), min(desired_w, int(self.window_width - s(16))))
        panel_h = min(panel_h_max, available_below)
        panel_x = int(board_x + (board_w - panel_w) // 2)
        panel_x = max(s(8), min(panel_x, self.window_width - panel_w - s(8)))
        panel_y = int(board_y + board_h + panel_gap_top)
        panel_rect = pygame.Rect(panel_x, panel_y, panel_w, panel_h)

        try:
            self._draw_hud_glass_panel(panel_rect)
        except Exception:
            retro_style.draw_glass_panel(self.screen, panel_rect, alpha=90, border_color=(60, 70, 90))

        if not perks:
            return

        item_h = max(s(38), panel_h - s(16))
        icon_size = s(28)
        item_w = s(162)
        spacing = s(10)
        available_w = max(s(60), panel_w - s(20))
        max_items_fit = max(1, (available_w + spacing) // (item_w + spacing))
        shown = perks[-max_items_fit:]
        total_w = len(shown) * item_w + max(0, len(shown) - 1) * spacing
        start_x = panel_rect.x + max(s(10), (panel_w - total_w) // 2)
        item_y = panel_rect.y + (panel_h - item_h) // 2
        title_font = self.mystery_font_small

        def _trim_text(text: str, max_w: int) -> str:
            value = str(text or '').strip()
            if value == '':
                return ''
            if title_font.size(value)[0] <= max_w:
                return value
            cut = value
            while len(cut) > 1 and title_font.size(cut + '...')[0] > max_w:
                cut = cut[:-1]
            return (cut + '...') if cut else value

        for idx, card in enumerate(shown):
            item_x = start_x + idx * (item_w + spacing)
            item_rect = pygame.Rect(item_x, item_y, item_w, item_h)
            pygame.draw.rect(self.screen, (14, 18, 34, 190), item_rect, border_radius=9)
            pygame.draw.rect(self.screen, (160, 176, 210, 110), item_rect, 1, border_radius=9)

            icon_rect = pygame.Rect(item_rect.x + s(7), item_rect.y + (item_rect.h - icon_size) // 2, icon_size, icon_size)
            try:
                icon_img = self.card_ui._get_icon_surface(card.get('icon_image'), (icon_rect.w, icon_rect.h))
            except Exception:
                icon_img = None

            if icon_img is not None:
                self.screen.blit(icon_img, icon_img.get_rect(center=icon_rect.center))
            else:
                txt_icon = str(card.get('icon', '*') or '*')
                safe_icon = ''.join(ch for ch in txt_icon if ch.isascii() and ch.isalnum())[:2]
                if not safe_icon:
                    safe_icon = '*'
                glyph = self.mystery_font_small.render(safe_icon, True, card.get('color', (220, 235, 255)))
                self.screen.blit(glyph, glyph.get_rect(center=icon_rect.center))

            text_x = icon_rect.right + s(8)
            text_w = max(s(34), item_rect.right - s(8) - text_x)
            card_title = get_card_title(card.get('id', ''), card.get('title', ''))
            card_title = _trim_text(card_title, text_w)
            title_surf = title_font.render(card_title, True, (224, 234, 252))
            title_rect = title_surf.get_rect()
            title_rect.x = text_x
            title_rect.centery = item_rect.centery
            self.screen.blit(title_surf, title_rect)

    def _get_left_panel_frame(self) -> tuple[int, int, int]:
        ui_scale = self._card_ui_scale()
        board_x, board_y = self.get_board_offset()
        available_space = max(int(170 * ui_scale), board_x - int(16 * ui_scale))
        width = min(self.left_panel_max_width, available_space)
        x = max(int(8 * ui_scale), board_x - width - int(12 * ui_scale))
        # Align vertical inset with the right HUD panel when available.
        hud_panel = getattr(self, '_hud_panel_rect', None)
        if hud_panel is not None:
            try:
                y = int(getattr(hud_panel, 'y', board_y + 10))
            except Exception:
                y = board_y + 10
        else:
            y = max(int(12 * ui_scale), board_y - int(20 * ui_scale))
        return x, y, width

    def get_current_speed(self) -> int:
        # Kart Modu (Mystery): düşüş hızı SADECE seviye (board.level) ile artar.
        # Skora bağlı hızlanma devre dışıdır.
        base_interval = 900
        min_interval = 200

        level = int(getattr(getattr(self, 'board', None), 'level', 1) or 1)
        level = max(1, level)
        base_interval = int(base_interval - (level - 1) * SPEED_INCREASE_PER_LEVEL)

        # Zaman yavaşlatma kartı aktifse: speed_effect_multiplier < 1 => interval artar (daha yavaş düşüş)
        if self.speed_effect_timer > 0 and self.speed_effect_multiplier > 0:
            base_interval = int(base_interval / self.speed_effect_multiplier)
        
        # Hız Patlaması aktifse: speed_burst_speed_mult > 1 => interval düşer (daha hızlı düşüş)
        speed_burst_mult = getattr(self, '_speed_burst_speed_mult', 1.0)
        if speed_burst_mult > 1.0:
            base_interval = int(base_interval / speed_burst_mult)

        return max(min_interval, int(base_interval))

    def _draw_status_panel(self) -> None:
        status = self.card_manager.get_status()
        ui_scale = self._card_ui_scale()
        panel_x, panel_y, panel_width = self._get_left_panel_frame()
        self._left_panel_frame = (panel_x, panel_y, panel_width)

        # Üstte: Mevcut seviye ve seviye içi ilerleme
        level = getattr(self.board, 'level', 1)
        # Seviye içindeki satır sayısı: use card manager threshold to stay consistent
        lines_needed = int(getattr(self.card_manager, 'threshold', 5))
        lines_in_level = int(self.board.lines_cleared % lines_needed)
        # Sağdaki standart HUD paneli ile aynı stil: glass panel (alpha=90)
        pad_x = max(10, int(15 * ui_scale))
        pad_top = max(8, int(12 * ui_scale))
        pad_bottom = max(8, int(12 * ui_scale))
        inner_x = panel_x + pad_x
        inner_w = max(160, panel_width - pad_x * 2)

        header_surface = self.mystery_font_medium.render(f"{t('level')}: {level}", True, (230, 235, 245))
        info_line_1 = t('card_level_progress', current=lines_in_level, needed=lines_needed)
        info_line_2 = t('card_pool_label', hint=status['hint'])
        info_line_1 = self._fit_text_to_width(self.mystery_font_small, info_line_1, inner_w)
        info_line_2 = self._fit_text_to_width(self.mystery_font_small, info_line_2, inner_w)
        info_texts = [
            self.mystery_font_small.render(info_line_1, True, (180, 200, 220)),
            self.mystery_font_small.render(info_line_2, True, (180, 200, 220)),
        ]

        progress_h = max(8, int(12 * ui_scale))
        line_gap = max(2, int(4 * ui_scale))
        content_h = pad_top + header_surface.get_height() + max(4, int(6 * ui_scale))
        content_h += sum(s.get_height() + line_gap for s in info_texts)
        content_h += max(6, int(10 * ui_scale)) + progress_h + pad_bottom

        panel_rect = pygame.Rect(panel_x, panel_y, panel_width, content_h)
        try:
            self._draw_hud_glass_panel(panel_rect)
        except Exception:
            retro_style.draw_glass_panel(self.screen, panel_rect, alpha=90, border_color=(60, 70, 90))

        cursor = panel_rect.y + pad_top
        self.screen.blit(header_surface, (inner_x, cursor))
        cursor += header_surface.get_height() + max(4, int(6 * ui_scale))
        for line_surface in info_texts:
            self.screen.blit(line_surface, (inner_x, cursor))
            cursor += line_surface.get_height() + line_gap

        cursor += max(4, int(6 * ui_scale))
        cursor += max(4, int(6 * ui_scale))
        # Progress bar removed on user request
        # progress_rect = pygame.Rect(inner_x, cursor, inner_w, progress_h)
        # pygame.draw.rect(self.screen, (255, 255, 255, 22), progress_rect, border_radius=8)
        # fill_w = int(inner_w * (lines_in_level / max(1, lines_needed)))
        # if fill_w > 0:
        #     pygame.draw.rect(self.screen, self.mode_skin.accent, (inner_x, cursor, fill_w, progress_h), border_radius=8)
        # pygame.draw.rect(self.screen, (255, 255, 255, 40), progress_rect, 1, border_radius=8)

        self._left_panel_cards_y = panel_rect.bottom + max(10, int(18 * ui_scale))
        self._left_panel_content_x = panel_x + pad_x
        self._left_panel_content_width = inner_w

    def _open_card_selection(self) -> None:
        self.card_selection_active = True
        self.card_ui.reset()
        self._pending_card_choice_index = None
        # Kart seçimi açıkken satır temizleme flash/dalga efektlerini çizme.
        # Böylece altta "yarım kalmış" animasyonlar görünmez.
        try:
            self.suppress_line_clear_effects = True
        except Exception:
            pass
        # While the overlay is active we consume events; KEYUP events for left/right
        # may never reach the base Game handler. Reset DAS to avoid "stuck" drift.
        try:
            self.das_direction = 0
            self.das_timer = 0
            self.das_repeat_timer = 0
            self.das_charged = False
        except Exception:
            pass
        if self.sound_enabled:
            self.sound.play_sound("pause")
        # Debug log about overlay opening and the number of pending choices (if debug mode set)
        try:
            if getattr(self, 'settings_manager', None) and self.settings_manager.get('debug_mode', False):
                print(f"[MysteryMode] Opening card selection overlay: {len(self.card_manager.pending_choices)} choices, pending_level_ups={getattr(self, 'pending_level_ups', 0)}")
        except Exception:
            pass

    def _close_card_selection(self) -> None:
        self.card_selection_active = False
        self.card_ui.clear_selection_feedback()
        self._pending_card_choice_index = None
        try:
            self.suppress_line_clear_effects = False
        except Exception:
            pass
        # Same reason as above: ensure gameplay resumes with a clean horizontal
        # repeat state even if KEYUP was consumed during overlay.
        try:
            self.das_direction = 0
            self.das_timer = 0
            self.das_repeat_timer = 0
            self.das_charged = False
        except Exception:
            pass
        # If a pending level-up was queued and a selection UI closes
        # (either by cancel or after finalize), decrement the queue so
        # next queued level opens a new overlay as intended.
        if getattr(self, 'pending_level_ups', 0) > 0:
            try:
                self.pending_level_ups = max(0, self.pending_level_ups - 1)
            except Exception:
                pass

    def _select_card(self, index: int) -> None:
        if self._pending_card_choice_index is not None or self.card_ui.is_selection_animating():
            return
        # Kart dönme animasyonu devam ediyorsa seçimi engelle
        if self.card_ui.is_flip_animating():
            return
        if not (0 <= index < len(self.card_manager.pending_choices)):
            return
        self._pending_card_choice_index = index
        self.card_ui.trigger_selection_feedback(index)

    def _finalize_pending_card_selection(self) -> None:
        if self._pending_card_choice_index is None:
            return
        card = self.card_manager.select_card(self._pending_card_choice_index)
        self._pending_card_choice_index = None
        if not card:
            self._close_card_selection()
            # If a level-up was pending but we couldn't select a card, clear one pending
            if getattr(self, 'pending_level_ups', 0) > 0:
                self.pending_level_ups = max(0, self.pending_level_ups - 1)
            return
        # Record selection for left panel history before applying effects.
        try:
            self._record_selected_card(card)
        except Exception:
            pass
        self._apply_card_effect(card)
        card_title_text = get_card_title(card.get('id', ''), card.get('title', ''))
        self.card_message = t('card_selected').format(title=card_title_text)
        self.card_message_timer = 3
        self._close_card_selection()
        # Note: pending_level_ups is now decremented by _close_card_selection(),
        # which is always called when the UI closes (finalize or cancel).

    def _apply_score_multiplier_to_delta(self, delta: int) -> int:
        if delta <= 0:
            return 0
        mult = float(getattr(self, '_score_multiplier_value', 1.0))
        if getattr(self, '_score_multiplier_timer', 0.0) <= 0 or mult <= 1.0:
            return 0
        return int(delta * (mult - 1.0))

    def _apply_line_clear_multiplier_to_delta(self, cleared: int, delta_score: int) -> int:
        if cleared <= 0 or delta_score <= 0:
            return 0
        
        total_extra = 0
        
        # Mevcut line_clear_multiplier sistemi
        remaining = int(getattr(self, '_line_clear_multiplier_remaining', 0))
        mult = float(getattr(self, '_line_clear_multiplier_value', 1.0))
        if remaining > 0 and mult > 1.0:
            applied = min(cleared, remaining)
            per_line = float(delta_score) / max(1, int(cleared))
            extra = int(per_line * applied * (mult - 1.0))
            self._line_clear_multiplier_remaining = max(0, remaining - applied)
            total_extra += max(0, extra)
        
        # Hız Patlaması bonus çarpanı
        speed_burst_timer = getattr(self, '_speed_burst_timer', 0)
        speed_burst_line_mult = getattr(self, '_speed_burst_line_mult', 1.0)
        if speed_burst_timer > 0 and speed_burst_line_mult > 1.0:
            # Tüm satırlar için çarpan uygula
            extra_speed = int(delta_score * (speed_burst_line_mult - 1.0))
            total_extra += max(0, extra_speed)
        
        return total_extra

    def _get_smart_phase_shift_target_name(self, current_name: str) -> str | None:
        """Mode hook for perk_phase.

        Must stay compatible with the canonical shape-mutation mapping used by
        Game.swap_current_piece_shape().
        """
        mapping = {'L': 'J', 'J': 'L', 'Z': 'S', 'S': 'Z', 'I': 'O', 'O': 'I', 'T': 'T'}
        return mapping.get(str(current_name or ''), None)

    def _evaluate_occupancy(self, occ: list[list[bool]]) -> tuple[int, int, int, int]:
        """Return (holes, bumpiness, agg_height, full_lines)."""
        if not occ or not occ[0]:
            return 0, 0, 0, 0
        h = len(occ)
        w = len(occ[0])
        heights = [0] * w
        holes = 0
        full_lines = 0
        for x in range(w):
            top = None
            for y in range(h):
                if occ[y][x]:
                    top = y
                    break
            if top is None:
                continue
            heights[x] = h - top
            for y in range(top + 1, h):
                if not occ[y][x]:
                    holes += 1
        for y in range(h):
            if all(occ[y][x] for x in range(w)):
                full_lines += 1
        bump = sum(abs(heights[i] - heights[i + 1]) for i in range(w - 1)) if w > 1 else 0
        agg = sum(heights)
        return holes, bump, agg, full_lines

    def _apply_block_magnet(self) -> None:
        """Blok Manyetigi: Tum bosluklar kapanir, bloklar sola kayar."""
        try:
            # Her satir icin bloklar sola kayar
            for y in range(self.board.height):
                # Mevcut satirda dolu bloklar ve ozellikleri topla
                blocks = []
                textures = []
                golds = []
                owners = []
                
                for x in range(self.board.width):
                    if self.board.occupancy[y][x]:
                        blocks.append(self.board.grid[y][x])
                        textures.append(self.board.texture_grid[y][x])
                        golds.append(self.board.gold[y][x])
                        owners.append(self.board.owners[y][x])
                
                # Satiri temizle
                for x in range(self.board.width):
                    self.board.grid[y][x] = None
                    self.board.occupancy[y][x] = False
                    self.board.texture_grid[y][x] = None
                    self.board.gold[y][x] = False
                    self.board.owners[y][x] = None
                
                # Bloklar sola yaslanacak sekilde yerlestir
                for i, block in enumerate(blocks):
                    if i < self.board.width:
                        self.board.grid[y][i] = block
                        self.board.occupancy[y][i] = True
                        if i < len(textures):
                            self.board.texture_grid[y][i] = textures[i]
                        if i < len(golds):
                            self.board.gold[y][i] = golds[i]
                        if i < len(owners):
                            self.board.owners[y][i] = owners[i]
            
            # Ses efekti
            if self.sound_enabled:
                try:
                    self.sound.play_sound("move")
                except Exception:
                    pass
                    
        except Exception:
            pass

    def _post_external_line_clear(
        self,
        cleared: int,
        *,
        award_energy: bool = True,
        score_delta: int | None = None,
        source: str = 'card',
    ) -> None:
        """Apply MysteryMode-specific bookkeeping after a non-lock line clear.

        Some cards/abilities can clear lines without going through the normal
        `lock_and_new_piece()` pipeline. Keep energy/perk/card-progress/bonus
        consistent by routing those clears here.
        """
        if cleared <= 0:
            return

        # Apply post-scoring multipliers for non-lock clears (board.clear_lines() already adds score)
        if score_delta is not None:
            try:
                delta0 = int(score_delta)
            except Exception:
                delta0 = 0
            if delta0 > 0:
                try:
                    mult = self.perk_manager.get_multiplier() if getattr(self, 'perk_manager', None) else 1.0
                    if mult != 1.0:
                        self.board.score += int(delta0 * (mult - 1.0))
                        delta0 = int(delta0 + (delta0 * (mult - 1.0)))
                except Exception:
                    pass
                try:
                    extra = self._apply_score_multiplier_to_delta(delta0)
                    if extra:
                        self.board.score += extra
                        delta0 += int(extra)
                except Exception:
                    pass
                try:
                    extra_lines = self._apply_line_clear_multiplier_to_delta(cleared, delta0)
                    if extra_lines:
                        self.board.score += extra_lines
                except Exception:
                    pass

        # Energy gain for Mystery Mode:
        # - card clears: +5/line by default (prevents farming)
        if award_energy and getattr(self, 'energy', None) is not None:
            try:
                per_line = 10 if source == 'player' else 5
                self.energy = min(self.energy_max, int(self.energy + cleared * per_line))
            except Exception:
                per_line = 10 if source == 'player' else 5
                self.energy = min(getattr(self, 'energy_max', 100), getattr(self, 'energy', 0) + (cleared * per_line))

        # Apply line bonus reward, if enabled
        try:
            self._apply_line_bonus_reward(cleared)
        except Exception:
            pass

        # Keep card progress in sync (selection opening is still driven by level-up)
        try:
            self.card_manager.notify_lines_cleared(cleared)
        except Exception:
            pass

        # Perk manager per-line triggers
        try:
            self.perk_manager.notify_lines_cleared(cleared, source=source)
        except Exception:
            pass

    def _apply_card_effect(self, card: Dict) -> None:
        cid = card["id"]
        value = card["value"]
        color = card["color"]
        effect_triggered = False

        # Some tests (and potential future callers) apply effects directly without
        # going through MysteryCardManager.select_card(). Ensure one-time
        # persistent perks are still marked as used so they won't be re-offered.
        try:
            if bool(card.get('persistent')):
                self.card_manager.used_card_ids.add(str(cid))
        except Exception:
            pass

        if cid == "score":
            # Basit skor patlaması - anında puan ekle
            base = int(value)
            # Synergy çarpanı uygula
            mult = 1.0
            try:
                mult = self.perk_manager.get_multiplier() if getattr(self, 'perk_manager', None) else 1.0
            except Exception:
                pass
            total = int(base * mult)
            self.board.score += total
            self.card_message = f"+{total} puan!"
            self.card_message_timer = 1.2
            effect_triggered = True
        elif cid == "clear_rows":
            self._clear_rows(value)
            # After collapsing, full rows may appear; clear them as proper line clears.
            # The sweep itself should not be treated as "N lines cleared" for perks/energy.
            try:
                prev_score_after_sweep = int(getattr(self.board, 'score', 0))
            except Exception:
                prev_score_after_sweep = 0
            try:
                cleared = int(self.board.clear_lines(source='card'))
            except Exception:
                cleared = 0
            if cleared > 0:
                try:
                    delta = int(getattr(self.board, 'score', 0)) - prev_score_after_sweep
                except Exception:
                    delta = None
                self._post_external_line_clear(cleared, award_energy=True, score_delta=delta, source='card')
            try:
                n = max(1, int(value))
                self.card_message = f"Alt Süpür: -{n} satır"
                self.card_message_timer = 0.9
            except Exception:
                pass
            effect_triggered = True
        elif cid == "force_piece":
            self._queue_force_pieces(value)
            try:
                # This effect is delayed (applies to upcoming spawns) so keep a visual.
                self._remember_effect_visual("force_piece", card)
                self._sync_active_cards()
            except Exception:
                pass
            effect_triggered = True
        elif cid == "column_cleanse":
            # Rastgele sütun temizle
            n_cols = max(1, int(value))
            self._clear_columns(n_cols)
            self.card_message = f"{n_cols} sütun temizlendi!"
            self.card_message_timer = 1.0
            effect_triggered = True
        elif cid == "combo_boost":
            self._apply_combo_aura(value, card)
            effect_triggered = True
        elif cid == "time_slow":
            self._apply_time_slow(value, card)
            effect_triggered = True
        elif cid == 'bomb_master':
            # Bomba Ustası: M tuşuyla mini bomba yapma hakları (sınırlı kart)
            # Sınırlı kartlar: tekrar seçilince hak EKLEME.
            # Kalan hak 1/2 ise 3'e tamamla; 3+ ise dokunma.
            try:
                cur = int(getattr(self, 'bomb_master_charges', 0) or 0)
            except Exception:
                cur = 0
            if cur in (0, 1, 2):
                self.bomb_master_charges = 3
            try:
                self.card_message = f"Bomba Ustası! M ile mini bomba ({int(self.bomb_master_charges)} hak)"
                self.card_message_timer = 1.4
            except Exception:
                pass
            try:
                self._remember_effect_visual('bomb_master', card)
                self._sync_active_cards()
            except Exception:
                pass
            effect_triggered = True
        elif cid == 'rewind_power':
            self.perk_manager.activate('rewind_power')
            # Sınırlı kartlar: tekrar seçilince hak EKLEME.
            # Kalan hak 1/2 ise 3'e tamamla; 3+ ise dokunma.
            try:
                cur = int(getattr(self.perk_manager, 'rewind_uses', 0) or 0)
            except Exception:
                cur = 0
            if cur in (0, 1, 2):
                self.perk_manager.rewind_uses = 3
            self._rewind_available = True
            self._last_placed_piece = None
            try:
                self._sync_active_cards()
            except Exception:
                pass
            effect_triggered = True
        elif cid == 'perk_chrono':
            self.perk_manager.activate('chrono_lock')
            try:
                self._sync_active_cards()
            except Exception:
                pass
            effect_triggered = True
        elif cid == 'perk_phase':
            # Şekil Değiştirici: sınırlı kullanımlı (3 hak)
            self.perk_manager.activate('phase_shift')
            # Sınırlı kartlar: tekrar seçilince hak EKLEME.
            # Kalan hak 1/2 ise 3'e tamamla; 3+ ise dokunma.
            try:
                cur = int(getattr(self, 'phase_shift_uses_remaining', 0) or 0)
            except Exception:
                cur = 0
            if cur in (0, 1, 2):
                self.phase_shift_uses_remaining = 3
            try:
                self._remember_effect_visual('perk_phase', card)
                self._sync_active_cards()
            except Exception:
                pass
            effect_triggered = True
        elif cid == 'perk_synergy':
            self.perk_manager.activate('synergy_core')
            try:
                self._sync_active_cards()
            except Exception:
                pass
            effect_triggered = True
        elif cid == 'perk_second_pocket':
            # Enable the second hold pocket
            self.perk_manager.activate('second_pocket')
            try:
                self._sync_active_cards()
            except Exception:
                pass
            effect_triggered = True
        elif cid == "line_bonus":
            # Sonraki N satır temizlemede 2x puan
            multiplier = card.get("payload", {}).get("multiplier", 2.0)
            self._enable_line_multiplier(value, multiplier, card)
            self.card_message = f"Sonraki {value} satır: {multiplier:.0f}x puan!"
            self.card_message_timer = 1.2
            effect_triggered = True
        elif cid == "quantum_tunneling":
            # Grant charges so the player can choose which upcoming pieces become tunneled.
            # Sınırlı kartlar: tekrar seçilince hak EKLEME.
            # Kalan hak 1/2 ise 3'e tamamla; 3+ ise dokunma.
            try:
                cur = int(getattr(self, 'tunnel_charges_remaining', 0) or 0)
            except Exception:
                cur = 0
            if cur in (0, 1, 2):
                self.tunnel_charges_remaining = 3
            try:
                self.card_message = f"Hayalet Parça: {int(self.tunnel_charges_remaining)} hak (G ile etkinleştir)"
                self.card_message_timer = 1.4
            except Exception:
                pass
            # Show a visual in active effects while charges remain
            try:
                self._remember_effect_visual('quantum_tunneling', card)
                self._sync_active_cards()
            except Exception:
                pass
            effect_triggered = True
        elif cid == "mini_bomb":
            # Arm the CURRENT piece as a bomb so it explodes when it locks
            # (either via SPACE hard drop or natural fall).
            piece = getattr(self, 'current_piece', None)
            if piece is not None:
                try:
                    setattr(piece, 'is_bomb', True)
                except Exception:
                    pass
                # Mini bomb should only clear blocks it touches (not a generic AoE).
                try:
                    setattr(piece, '_bomb_contact', True)
                except Exception:
                    pass
                # Keep original color and preserve across theme reapplications.
                try:
                    if getattr(piece, '_original_color', None) is None:
                        setattr(piece, '_original_color', getattr(piece, 'color', None))
                except Exception:
                    pass
                try:
                    # Bomba rengi: kırmızı
                    BOMB_COLOR = (221, 0, 5)
                    piece.color = BOMB_COLOR
                    setattr(piece, '_force_color', BOMB_COLOR)
                except Exception:
                    pass
                try:
                    self.card_message = "Mini Bomba: Bu parça kilitlenince patlayacak!"
                    self.card_message_timer = 1.2
                except Exception:
                    pass
                effect_triggered = True
            else:
                # Parça yokken kartı harcama
                try:
                    self.card_message = "Mini Bomba: Parça yok!"
                    self.card_message_timer = 0.9
                except Exception:
                    pass
                effect_triggered = False
        elif cid == "hammer":
            # Grant charges so the player can choose which upcoming piece becomes 1x1.
            # Sınırlı kartlar: tekrar seçilince hak EKLEME.
            # Kalan hak 1/2 ise 3'e tamamla; 3+ ise dokunma.
            try:
                cur = int(getattr(self, 'hammer_charges_remaining', 0) or 0)
            except Exception:
                cur = 0
            if cur in (0, 1, 2):
                self.hammer_charges_remaining = 3
            try:
                self.card_message = f"Çekiç: {int(self.hammer_charges_remaining)} hak (H ile kullan)"
                self.card_message_timer = 1.4
            except Exception:
                pass
            try:
                self._remember_effect_visual('hammer', card)
                self._sync_active_cards()
            except Exception:
                pass
            effect_triggered = True
        elif cid == "gravity_well":
            # Zincirleme reaksiyon: gravity -> clear -> gravity ...
            total_lines = 0
            try:
                while True:
                    self.board.apply_gravity()
                    prev_score = int(getattr(self.board, 'score', 0))
                    lines = int(self.board.clear_lines(source='card'))
                    if lines <= 0:
                        break
                    total_lines += int(lines)
                    try:
                        delta = int(getattr(self.board, 'score', 0)) - prev_score
                    except Exception:
                        delta = None
                    self._post_external_line_clear(lines, award_energy=True, score_delta=delta, source='card')
            except Exception:
                pass
            if total_lines > 0:
                try:
                    self.card_message = f"Gravity Well: {total_lines} satır"
                    self.card_message_timer = 0.9
                except Exception:
                    pass
            # Gravity Well is a one-shot card; do not persist in active cards
            effect_triggered = True
        elif cid == "ghost_echo":
            # Arm Ghost Echo: do NOT clear immediately; keep in active visuals until
            # an invalid spawn occurs (then spawn_new_piece will auto-trigger it).
            try:
                # store it in _active_effect_visuals so it shows in the UI and is easy to remove
                self._remember_effect_visual('ghost_echo', card)
                self._sync_active_cards()
            except Exception:
                pass
            # mark one-time usage so it's not offered again
            try:
                if card.get('single_use'):
                    self.card_manager.used_card_ids.add(card.get('id'))
            except Exception:
                pass
            # Do not schedule TTL removal -- this will persist (single-use) until consumed
            effect_triggered = True
        elif cid == 'perk_alchemist':
            self.perk_manager.activate('perk_alchemist')
            try:
                self._sync_active_cards()
            except Exception:
                pass
            effect_triggered = True
        elif cid == 'perk_flexible_border':
            # Esnek Sınır: Parçalar tahtanın kenarlarından 1 blok dışına çıkabilir
            # Görsel değişiklik yok, sadece hareket sınırları genişliyor
            self.perk_manager.activate('perk_flexible_border')
            # Board'a kalıcı flag ekle - tüm parçalar bu özellikten yararlanır
            try:
                self.board.flexible_border_active = True
            except Exception:
                pass
            try:
                self.card_message = "Esnek Sınır aktif! Parçalar kenarlara taşabilir."
                self.card_message_timer = 1.5
            except Exception:
                pass
            try:
                self._sync_active_cards()
            except Exception:
                pass
            effect_triggered = True
        elif cid in ("speed_burst_rare", "speed_burst_epic", "speed_burst_legendary", "speed_burst"):
            # Hız Patlaması: Belirli süre hızlı düşüş + satır temizleme bonusu
            duration = int(value)
            speed_mult = card.get("payload", {}).get("speed_multiplier", 1.5)
            line_mult = card.get("payload", {}).get("line_multiplier", 1.5)
            
            # Timer ve çarpanları ayarla
            self._speed_burst_timer = duration
            self._speed_burst_speed_mult = speed_mult
            self._speed_burst_line_mult = line_mult
            
            # Hızı hemen güncelle
            self.fall_speed = self.get_current_speed()
            
            try:
                self.card_message = f"Hız Patlaması! {duration}s boyunca hızlı düşüş + {line_mult}x puan!"
                self.card_message_timer = 1.5
            except Exception:
                pass
            
            try:
                # Aktif kart olarak göster (TTL ile)
                card_copy = dict(card)
                card_copy['ttl'] = float(duration)
                self._remember_effect_visual('speed_burst', card_copy)
                self._sync_active_cards()
            except Exception:
                pass
            effect_triggered = True
        elif cid == "peak_sculpt":
            removed = 0
            try:
                removed = int(self._level_peaks(value))
            except Exception:
                removed = 0
            if removed > 0:
                try:
                    bonus = min(300, removed * 15)
                    mult = 1.0
                    try:
                        mult = self.perk_manager.get_multiplier() if getattr(self, 'perk_manager', None) else 1.0
                    except Exception:
                        mult = 1.0
                    self.board.score += int(bonus * mult)
                except Exception:
                    pass
                try:
                    self.card_message = f"Tepe Dilimleyici: -{removed} blok"
                    self.card_message_timer = 0.9
                except Exception:
                    pass
            else:
                try:
                    self.card_message = "Tepe Dilimleyici: zaten dengeli"
                    self.card_message_timer = 0.9
                except Exception:
                    pass
            effect_triggered = True
        elif cid == "nova_burst":
            # Arm targeted explosion(s) for upcoming locks
            self._arm_nova_burst(value, card)
            effect_triggered = True
        # === YENİ KART EFEKTLERİ ===
        elif cid == "block_magnet":
            # Blok Manyetigi: Tum bosluklar kapanir, bloklar sola kayar
            self._apply_block_magnet()
            try:
                self.card_message = "Blok Manyetigi: bosluklar kapandi!"
                self.card_message_timer = 1.2
            except Exception:
                pass
            effect_triggered = True
        elif cid == "row_shuffle":
            # Satır Karıştırıcı: en alttaki N satırdaki blokları karıştır
            self._shuffle_bottom_rows(value)
            try:
                n = max(1, int(value))
                self.card_message = f"Satır Karıştırıcı: alt {n} satır"
                self.card_message_timer = 0.9
            except Exception:
                pass
            effect_triggered = True
        elif cid == "laser_drill":
            # Aktif Delici Parça: oyun durmaz; parça kırmızı olur ve temas ettiği blokları yok eder
            self._activate_drill_piece()
            try:
                self._remember_effect_visual('laser_drill', card)
                self._sync_active_cards()
            except Exception:
                pass
            effect_triggered = True
        elif cid == "sniper_shot":
            # Keskin Nişancı: N tuşuyla aktifleştir, overlay'de blok seç
            # Artık sınırlı kullanım - kart değeri kadar hak ver
            charges = int(card.get('value', 3))  # Varsayılan 3 hak
            self._sniper_charges = charges
            self._sniper_card = card
            try:
                self.card_message = f"Keskin Nisanci hazir! N tusuna bas. ({charges} hak)"
                self.card_message_timer = 3.0
            except Exception:
                pass
            # Görsel efekt için kaydet
            try:
                self._remember_effect_visual('sniper_shot', card)
                self._sync_active_cards()
            except Exception:
                pass
            effect_triggered = True
        elif cid == "time_capsule":
            # Zaman Kapsulu: T ile kaydet, R ile geri don
            self.time_capsule_available = True
            self.time_capsule_saved = False
            self.time_capsule_data = None
            try:
                self.card_message = "Zaman Kapsulu aktif! T ile kaydet, R ile geri don."
                self.card_message_timer = 3.0
            except Exception:
                pass
            # Görsel efekt için kaydet
            try:
                self._remember_effect_visual('time_capsule', card)
                self._sync_active_cards()
            except Exception:
                pass
            effect_triggered = True
        elif cid == "future_changer":
            # Geleceği Değiştiren: Sonraki 2 parçayı oyuncu seçer
            self._future_changer_remaining = 2
            self._future_changer_card = card
            self._open_piece_selection_popup()
            effect_triggered = True

        # === SON DÜŞÜŞ (Blok Dondurma) ===
        elif cid in ("freeze_drop_rare", "freeze_drop_epic", "freeze_drop_legendary"):
            freeze_dur = int(card.get('freeze_duration', 6))
            try:
                cur = int(getattr(self, '_freeze_drop_charges', 0) or 0)
            except Exception:
                cur = 0
            if cur in (0, 1, 2):
                self._freeze_drop_charges = 3
            self._freeze_drop_duration = freeze_dur
            try:
                self.card_message = f"Son Düşüş! F ile dondur ({int(self._freeze_drop_charges)} hak, {freeze_dur}sn)"
                self.card_message_timer = 1.5
            except Exception:
                pass
            try:
                self._remember_effect_visual('freeze_drop', card)
                self._sync_active_cards()
            except Exception:
                pass
            effect_triggered = True

        # === BLOK ATÖLYESİ KARTI ===
        elif cid == "block_workshop_card":
            # Popup blok atölyesi aç - tek seferlik parça oluştur
            self._open_card_workshop_popup()
            effect_triggered = True

        # === KUMARBAZIN ZARI ===
        elif cid == "gambler_dice":
            import random as _rng
            roll = _rng.random()
            if roll < 0.5:
                # Tüm tahtayı temizle
                total_cleared = 0
                try:
                    for y in range(self.board.height):
                        for x in range(self.board.width):
                            if self.board.occupancy[y][x]:
                                self.board.grid[y][x] = (0, 0, 0)
                                self.board.occupancy[y][x] = False
                                self.board.texture_grid[y][x] = None
                                self.board.gold[y][x] = False
                                self.board.owners[y][x] = None
                                total_cleared += 1
                except Exception:
                    pass
                try:
                    bonus = total_cleared * 50
                    self.board.score += bonus
                    self.card_message = f"🎲 JACKPOT! Tum tahta temizlendi! +{bonus} puan"
                    self.card_message_timer = 2.0
                except Exception:
                    pass
            else:
                # Kötü şans: Mevcut blokları yerlerinden koparıp rastgele yerlere dağıt (üst 5 satır hariç)
                try:
                    # Tahtadaki tüm blokları topla
                    existing_blocks = []
                    for y in range(self.board.height):
                        for x in range(self.board.width):
                            if self.board.occupancy[y][x]:
                                existing_blocks.append({
                                    'color': self.board.grid[y][x],
                                    'texture': self.board.texture_grid[y][x],
                                    'gold': self.board.gold[y][x],
                                    'owner': self.board.owners[y][x],
                                })
                    
                    if existing_blocks:
                        # Tahtayı komple temizle
                        for y in range(self.board.height):
                            for x in range(self.board.width):
                                self.board.grid[y][x] = (0, 0, 0)
                                self.board.occupancy[y][x] = False
                                self.board.texture_grid[y][x] = None
                                self.board.gold[y][x] = False
                                self.board.owners[y][x] = None
                        
                        # Üst 5 satır hariç boş hücreleri bul
                        available_cells = []
                        for y in range(5, self.board.height):
                            for x in range(self.board.width):
                                available_cells.append((x, y))
                        
                        # Blokları rastgele yerlere dağıt
                        _rng.shuffle(available_cells)
                        placed = 0
                        for i, block in enumerate(existing_blocks):
                            if i < len(available_cells):
                                x, y = available_cells[i]
                                self.board.grid[y][x] = block['color']
                                self.board.occupancy[y][x] = True
                                self.board.texture_grid[y][x] = block['texture']
                                self.board.gold[y][x] = block['gold']
                                self.board.owners[y][x] = block['owner']
                                placed += 1
                        # Yerçekimi uygula - bloklar havada kalmasın
                        self.board.apply_gravity()
                        self.card_message = f"🎲 Sansina kusura bakma! {placed} blok karistirildi!"
                    else:
                        self.card_message = "🎲 Tahta bos, sansin kotu ama zararsiz!"
                    self.card_message_timer = 2.0
                except Exception:
                    pass
            effect_triggered = True

        # === RENK TEMİZLEME ===
        elif cid == "color_cleanse":
            self._apply_color_cleanse()
            effect_triggered = True

        # === TUTTUĞUNU KOPARAN (hold_destroyer variants) ===
        elif cid.startswith("hold_destroyer"):
            # B tuşuyla saklanan parçayı silme hakkı ver
            charges = int(card.get('value', 1))
            try:
                existing = int(getattr(self, '_hold_destroyer_charges', 0) or 0)
                self._hold_destroyer_charges = existing + charges
            except Exception:
                self._hold_destroyer_charges = charges
            # HUD gösterimi için sync
            self.discard_held_uses = int(getattr(self, '_hold_destroyer_charges', charges))
            try:
                total = int(getattr(self, '_hold_destroyer_charges', charges))
                self.card_message = f"Tuttugunu Koparan! B ile hold sil ({total} hak)"
                self.card_message_timer = 1.5
            except Exception:
                pass
            try:
                self._remember_effect_visual('hold_destroyer', card)
                self._sync_active_cards()
            except Exception:
                pass
            effect_triggered = True

        if effect_triggered:
            self._spawn_card_particles(color)

        if self.sound_enabled:
            self.sound.play_sound("levelup")

    # === SNIPER SHOT YARDIMCI METODLARI ===
    def _open_sniper_overlay(self) -> bool:
        """N tuşuyla sniper overlay'ini açar."""
        charges = int(getattr(self, '_sniper_charges', 0) or 0)
        if charges <= 0:
            try:
                self.card_message = "Keskin Nişancı hakkın yok!"
                self.card_message_timer = 0.8
            except Exception:
                pass
            return False
        
        # Overlay'i aç
        self._sniper_overlay_active = True
        self._sniper_hover_pos = None
        try:
            charges = int(getattr(self, '_sniper_charges', 0) or 0)
            self.card_message = f"Patlatmak istedigin bloga tikla! (ESC: Iptal) - Kalan: {charges}"
            self.card_message_timer = 10.0
        except Exception:
            pass
        return True

    def _close_sniper_overlay(self) -> None:
        """Sniper overlay'ini kapatır (hak harcanmaz)."""
        self._sniper_overlay_active = False
        self._sniper_hover_pos = None
        
        # Mouse cursor'ı tekrar görünür yap
        pygame.mouse.set_visible(True)
        
        try:
            charges = int(getattr(self, '_sniper_charges', 0) or 0)
            self.card_message = f"Keskin Nisanci iptal edildi (Kalan hak: {charges})"
            self.card_message_timer = 1.2
        except Exception:
            pass

    def _sniper_screen_to_cell(self, pos: tuple[int, int]) -> tuple[int, int] | None:
        """Mouse pozisyonunu mevcut tahta hücresine çevirir."""
        try:
            mx, my = pos
            
            # Mevcut tahta parametreleri - doğru koordinatları al
            board_x, board_y = self.get_board_offset()
            cell_size = self.get_cell_size()
            
            # Tahta sınırları içinde mi kontrol et
            if mx < board_x or my < board_y:
                return None
            
            board_pixel_w = self.board.width * cell_size
            board_pixel_h = self.board.height * cell_size
            
            if mx >= board_x + board_pixel_w or my >= board_y + board_pixel_h:
                return None
            
            cx = int((mx - board_x) // cell_size)
            cy = int((my - board_y) // cell_size)
            
            # Tahta boyutları içinde mi kontrol et
            if 0 <= cx < self.board.width and 0 <= cy < self.board.height:
                return (cx, cy)
            return None
        except Exception:
            return None

    def _execute_sniper_shot(self, cx: int, cy: int) -> None:
        """Belirtilen hücredeki bloğu yok eder (puan vermez)."""
        try:
            # Patlama efektini yok edilen hücrede başlat
            self._spawn_sniper_explosion(cx, cy)

            # Bloğu temizle
            from constants import BLACK
            self.board.grid[cy][cx] = BLACK
            self.board.occupancy[cy][cx] = False
            self.board.texture_grid[cy][cx] = None
            self.board.gold[cy][cx] = False
            self.board.owners[cy][cx] = None
            
            # Hakkı düş
            self._sniper_charges = max(0, int(getattr(self, '_sniper_charges', 0) or 0) - 1)
            remaining = int(getattr(self, '_sniper_charges', 0) or 0)
            
            # Mesaj göster
            try:
                if remaining > 0:
                    self.card_message = f"Blok yok edildi! Kalan hak: {remaining}"
                else:
                    self.card_message = "Blok yok edildi! Keskin Nisanci tukendi."
                self.card_message_timer = 1.5
            except Exception:
                pass
            
            # Ses efekti
            if self.sound_enabled:
                try:
                    self.sound.play_sound("sniper_shot")  # Özel sniper sesi
                except Exception:
                    pass
            
        except Exception:
            pass
        finally:
            # Mouse cursor'ı tekrar görünür yap
            pygame.mouse.set_visible(True)
            
            # Overlay'i kapat
            self._sniper_overlay_active = False
            self._sniper_hover_pos = None
            
            # Hak bittiyse aktif efektlerden kaldır
            if int(getattr(self, '_sniper_charges', 0) or 0) <= 0:
                self._sniper_card = None
                self._active_effect_visuals.pop('sniper_shot', None)
            self._sync_active_cards()

    # === ZAMAN KAPSULU YARDIMCI METODLARI ===
    def _toggle_time_capsule(self) -> bool:
        """R tuşu ile zaman kapsülünü toggle et: önce kaydet, sonra geri yükle."""
        if not getattr(self, 'time_capsule_saved', False):
            return self._save_time_capsule()
        return self._restore_time_capsule()

    def _save_time_capsule(self) -> bool:
        """R tuşunun ilk basışında mevcut oyun durumunu kaydet."""
        if not getattr(self, 'time_capsule_available', False):
            try:
                self.card_message = "Zaman Kapsulu yok!"
                self.card_message_timer = 0.8
            except Exception:
                pass
            return False
        
        try:
            # Mevcut oyun durumunu kaydet
            import copy
            self.time_capsule_data = {
                'board_grid': copy.deepcopy(self.board.grid),
                'board_occupancy': copy.deepcopy(self.board.occupancy),
                'board_texture_grid': copy.deepcopy(self.board.texture_grid),
                'board_gold': copy.deepcopy(self.board.gold),
                'board_owners': copy.deepcopy(self.board.owners),
                'board_score': self.board.score,
                'board_lines_cleared': self.board.lines_cleared,
                'board_level': self.board.level,
                'current_piece': copy.deepcopy(self.current_piece) if self.current_piece else None,
                'next_piece_queue': copy.deepcopy(self.next_piece_queue),
                'held_piece': copy.deepcopy(self.held_piece) if self.held_piece else None,
                'can_hold': self.can_hold,
                'combo': getattr(self.board, 'combo', 0),
                # Parca akisini deterministik geri almak icin torba + RNG state
                '_piece_bag': copy.deepcopy(getattr(self, '_piece_bag', [])),
                '_piece_rng_state': getattr(getattr(self, '_piece_rng', None), 'getstate', lambda: None)(),
                '_last_piece_identity': getattr(self, '_last_piece_identity', None),
                '_last_piece_streak': getattr(self, '_last_piece_streak', 0),
                # Kart efekt durumlarini kaydet
                'tunnel_charges_remaining': getattr(self, 'tunnel_charges_remaining', 0),
                'hammer_charges_remaining': getattr(self, 'hammer_charges_remaining', 0),
                'bomb_master_charges': getattr(self, 'bomb_master_charges', 0),
                '_sniper_charges': getattr(self, '_sniper_charges', 0),
                'speed_effect_timer': getattr(self, 'speed_effect_timer', 0.0),
                'speed_effect_multiplier': getattr(self, 'speed_effect_multiplier', 1.0),
                'combo_aura_timer': getattr(self, 'combo_aura_timer', 0.0),
                'combo_aura_bonus': getattr(self, 'combo_aura_bonus', 0),
                'line_bonus_remaining': getattr(self, 'line_bonus_remaining', 0),
                'line_bonus_amount': getattr(self, 'line_bonus_amount', 0),
                '_line_clear_multiplier_remaining': getattr(self, '_line_clear_multiplier_remaining', 0),
                '_line_clear_multiplier_value': getattr(self, '_line_clear_multiplier_value', 1.0),
                'gravity_freeze_timer': getattr(self, 'gravity_freeze_timer', 0.0),
                'time_warp_timer': getattr(self, 'time_warp_timer', 0.0),
                '_armed_nova_clusters': getattr(self, '_armed_nova_clusters', 0),
                # Perk durumlarini kaydet
                'perk_manager_active': copy.deepcopy(getattr(self.perk_manager, 'active', {})) if hasattr(self, 'perk_manager') else {},
                'phase_shift_uses_remaining': getattr(self, 'phase_shift_uses_remaining', 0)
            }
            self.time_capsule_saved = True
            
            try:
                self.card_message = "Zaman Kapsulu kaydedildi! R ile geri don."
                self.card_message_timer = 2.0
            except Exception:
                pass
            
            # Ses efekti
            if self.sound_enabled:
                try:
                    self.sound.play_sound("confirm")
                except Exception:
                    pass
            
            self._sync_active_cards()
            return True
            
        except Exception as e:
            try:
                self.card_message = "Zaman Kapsulu kaydetme hatasi!"
                self.card_message_timer = 1.0
            except Exception:
                pass
            return False
    
    def _restore_time_capsule(self) -> bool:
        """R tuşunun ikinci basışında kaydedilen duruma geri don."""
        if not getattr(self, 'time_capsule_available', False):
            try:
                self.card_message = "Zaman Kapsulu yok!"
                self.card_message_timer = 0.8
            except Exception:
                pass
            return False
        
        if not getattr(self, 'time_capsule_saved', False) or not self.time_capsule_data:
            try:
                self.card_message = "Kaydedilmis durum yok! Once R ile kaydet."
                self.card_message_timer = 1.5
            except Exception:
                pass
            return False
        
        try:
            # Kaydedilen durumu geri yukle
            data = self.time_capsule_data
            
            self.board.grid = data['board_grid']
            self.board.occupancy = data['board_occupancy']
            self.board.texture_grid = data['board_texture_grid']
            self.board.gold = data['board_gold']
            self.board.owners = data['board_owners']
            self.board.score = data['board_score']
            self.board.lines_cleared = data['board_lines_cleared']
            self.board.level = data['board_level']
            self.current_piece = data['current_piece']
            self.next_piece_queue = data['next_piece_queue']
            self.held_piece = data['held_piece']
            self.can_hold = data['can_hold']
            if hasattr(self.board, 'combo'):
                self.board.combo = data['combo']

            # Parca akisini birebir geri yukle
            self._piece_bag = data.get('_piece_bag', [])
            self._last_piece_identity = data.get('_last_piece_identity', None)
            self._last_piece_streak = int(data.get('_last_piece_streak', 0) or 0)
            piece_rng_state = data.get('_piece_rng_state', None)
            if piece_rng_state is not None and hasattr(self, '_piece_rng') and hasattr(self._piece_rng, 'setstate'):
                try:
                    self._piece_rng.setstate(piece_rng_state)
                except Exception:
                    pass
            
            # Kart efekt durumlarini geri yukle
            self.tunnel_charges_remaining = data.get('tunnel_charges_remaining', 0)
            self.hammer_charges_remaining = data.get('hammer_charges_remaining', 0)
            self.bomb_master_charges = data.get('bomb_master_charges', 0)
            self._sniper_charges = data.get('_sniper_charges', 0)
            self.speed_effect_timer = data.get('speed_effect_timer', 0.0)
            self.speed_effect_multiplier = data.get('speed_effect_multiplier', 1.0)
            self.combo_aura_timer = data.get('combo_aura_timer', 0.0)
            self.combo_aura_bonus = data.get('combo_aura_bonus', 0)
            self.line_bonus_remaining = data.get('line_bonus_remaining', 0)
            self.line_bonus_amount = data.get('line_bonus_amount', 0)
            self._line_clear_multiplier_remaining = data.get('_line_clear_multiplier_remaining', 0)
            self._line_clear_multiplier_value = data.get('_line_clear_multiplier_value', 1.0)
            self.gravity_freeze_timer = data.get('gravity_freeze_timer', 0.0)
            self.time_warp_timer = data.get('time_warp_timer', 0.0)
            self._armed_nova_clusters = data.get('_armed_nova_clusters', 0)
            
            # Perk durumlarini geri yukle
            if hasattr(self, 'perk_manager') and 'perk_manager_active' in data:
                self.perk_manager.active = data['perk_manager_active']
            self.phase_shift_uses_remaining = data.get('phase_shift_uses_remaining', 0)
            
            # Parçalara tema uygula
            if self.current_piece:
                self.apply_theme_to_pieces()
            
            # Zaman kapsulunu tüket (tek kullanım)
            self.time_capsule_available = False
            self.time_capsule_saved = False
            self.time_capsule_data = None
            self._active_effect_visuals.pop('time_capsule', None)
            
            # Aktif efekt görsellerini yeniden olustur
            self._rebuild_active_effect_visuals()
            
            try:
                self.card_message = "Zaman Kapsulu kullanildi! Gecmise donuldu."
                self.card_message_timer = 2.0
            except Exception:
                pass
            
            # Ses efekti
            if self.sound_enabled:
                try:
                    self.sound.play_sound("levelup")
                except Exception:
                    pass
            
            self._sync_active_cards()
            return True
            
        except Exception as e:
            try:
                self.card_message = "Zaman Kapsulu geri yukleme hatasi!"
                self.card_message_timer = 1.0
            except Exception:
                pass
            return False

    def _rebuild_active_effect_visuals(self) -> None:
        """Aktif efektlerin görsel durumunu yeniden olustur."""
        try:
            # Mevcut görsel efektleri temizle
            self._active_effect_visuals.clear()
            
            # Aktif kartlari yeniden tara ve görsel efektleri olustur
            catalog = getattr(self.card_manager, 'catalog', []) or []
            
            # Tunnel charges varsa quantum_tunneling efektini ekle
            if getattr(self, 'tunnel_charges_remaining', 0) > 0:
                card = next((c for c in catalog if c.get('id') == 'quantum_tunneling'), None)
                if card:
                    self._remember_effect_visual('quantum_tunneling', card)
            
            # Hammer charges varsa hammer efektini ekle
            if getattr(self, 'hammer_charges_remaining', 0) > 0:
                card = next((c for c in catalog if c.get('id') == 'hammer'), None)
                if card:
                    self._remember_effect_visual('hammer', card)
            
            # Bomb master charges varsa bomb_master efektini ekle
            if getattr(self, 'bomb_master_charges', 0) > 0:
                card = next((c for c in catalog if c.get('id') == 'bomb_master'), None)
                if card:
                    self._remember_effect_visual('bomb_master', card)

            # Hold destroyer charges varsa hold_destroyer efektini ekle
            if getattr(self, '_hold_destroyer_charges', 0) > 0:
                card = next((c for c in catalog if str(c.get('id', '')).startswith('hold_destroyer')), None)
                if card:
                    self._remember_effect_visual('hold_destroyer', card)
            
            # Sniper charges varsa sniper_shot efektini ekle
            if getattr(self, '_sniper_charges', 0) > 0:
                card = next((c for c in catalog if c.get('id') == 'sniper_shot'), None)
                if card:
                    self._remember_effect_visual('sniper_shot', card)
            
            # Nova clusters varsa nova_burst efektini ekle
            if getattr(self, '_armed_nova_clusters', 0) > 0:
                card = next((c for c in catalog if c.get('id') == 'nova_burst'), None)
                if card:
                    self._remember_effect_visual('nova_burst', card)
            
            # Speed Burst timer varsa speed_burst efektini ekle
            if getattr(self, '_speed_burst_timer', 0) > 0:
                card = next((c for c in catalog if c.get('id') == 'speed_burst'), None)
                if card:
                    self._remember_effect_visual('speed_burst', card)
            
        except Exception:
            pass

    def _apply_time_slow(self, duration: int, card: Dict) -> None:
        seconds = max(3, int(duration))
        payload = card.get("payload", {})
        multiplier = float(payload.get("speed_multiplier", 0.6))
        # Smaller multiplier => slower fall (interval increases via division in get_current_speed)
        multiplier = max(0.2, min(multiplier, 0.95))

        if getattr(self, 'speed_effect_timer', 0.0) > 0:
            self.speed_effect_timer = min(20.0, float(self.speed_effect_timer) + float(seconds))
            self.speed_effect_multiplier = min(float(getattr(self, 'speed_effect_multiplier', 1.0) or 1.0), multiplier)
        else:
            self.speed_effect_timer = float(seconds)
            self.speed_effect_multiplier = multiplier
        self.fall_speed = self.get_current_speed()
        self._remember_effect_visual("time_slow", card)
        self._sync_active_cards()

    def _enable_line_bonus(self, lines: int, bonus: int, card: Dict) -> None:
        self.line_bonus_remaining += max(1, lines)
        self.line_bonus_amount = max(50, bonus)
        self._remember_effect_visual("line_bonus", card)
        self._sync_active_cards()

    def _enable_line_multiplier(self, lines: int, multiplier: float, card: Dict) -> None:
        n = max(1, int(lines))
        self._line_clear_multiplier_remaining = int(getattr(self, '_line_clear_multiplier_remaining', 0) or 0) + n
        self._line_clear_multiplier_value = max(1.0, float(multiplier))
        # Visual: score text turns gold while charges remain
        self._score_color_override = (255, 210, 75) if self._line_clear_multiplier_remaining > 0 else None
        self._remember_effect_visual("line_bonus", card)
        self._sync_active_cards()

    def _apply_line_bonus_reward(self, cleared: int) -> None:
        if cleared <= 0 or self.line_bonus_remaining <= 0:
            return
        applied = min(cleared, self.line_bonus_remaining)
        bonus = applied * self.line_bonus_amount
        self.board.score += bonus
        self.line_bonus_remaining -= applied
        self._sync_active_cards()

    def _apply_combo_aura(self, duration: int, card: Dict) -> None:
        seconds = max(3, duration)
        payload = card.get("payload", {})
        self.combo_aura_bonus = max(1, int(payload.get("combo_bonus", 1)))
        self.combo_aura_timer = float(seconds)
        self._remember_effect_visual("combo_boost", card)
        self._sync_active_cards()

    def _apply_combo_aura_on_lock(self, gained: int, previous_combo: int) -> None:
        if self.combo_aura_timer <= 0:
            return
        bonus = max(1, self.combo_aura_bonus)
        if gained > 0:
            self.board.combo = max(1, self.board.combo + bonus)
            self.board.score += gained * 75 * bonus
        else:
            self.board.combo = max(previous_combo, 1)
        self._sync_active_cards()

    def _remember_effect_visual(self, effect_id: str, card: Dict) -> None:
        self._active_effect_visuals[effect_id] = {
            "title": card["title"],
            "color": card["color"],
            "icon": card.get("icon", "*"),
            "tag": card.get("tag", "Etki"),
            "rarity": card.get("rarity", "common"),
            "style": card.get("style", {}),
            "icon_image": card.get("icon_image"),
            "value": card.get("value", card.get("base")),
            "payload": card.get("payload", {}),
        }

    def _sync_active_cards(self) -> None:
        # keep score color override in sync with global line multiplier charges
        try:
            if int(getattr(self, '_line_clear_multiplier_remaining', 0) or 0) <= 0:
                self._score_color_override = None
        except Exception:
            pass

        # Gamepad bağlıyken kart buton etiketlerini gamepad buton adıyla göster
        try:
            _gpm = get_gamepad_manager()
            _gp_on = _gpm.is_connected()
        except Exception:
            _gpm = None
            _gp_on = False

        def _card_key(keyboard_label: str, gp_action: str) -> str:
            """Gamepad bağlıysa gamepad buton adı, değilse klavye tuşu döndür."""
            if _gp_on and _gpm:
                try:
                    lbl = _gpm.get_button_label(gp_action)
                    if lbl and lbl != '?':
                        return lbl
                except Exception:
                    pass
            return keyboard_label

        cards: List[Dict] = []

        def add(effect_id: str, description: str, status: str = "") -> None:
            viz = self._active_effect_visuals.get(effect_id)
            if not viz:
                return
            entry = {
                "id": effect_id,
                "title": viz["title"],
                "description": description,
                "status": status,  # New compact status field
                "color": viz["color"],
                "icon": viz.get("icon", "*"),
                "tag": viz.get("tag", "Etki"),
                "rarity": viz.get("rarity", "common"),
                "style": viz.get("style", {}),
                "icon_image": viz.get("icon_image"),
                "value": viz.get("value"),
                "payload": viz.get("payload"),
            }
            cards.append(entry)

        if self.speed_effect_timer > 0:
            add("time_slow", f"{self.speed_effect_timer:.1f} sn boyunca düşüş yavaş.", status=f"{self.speed_effect_timer:.1f}s")
        else:
            self._active_effect_visuals.pop("time_slow", None)

        # Hız Patlaması (Speed Burst) görselini güncelle
        # Timer check: self._speed_burst_timer
        burst_timer = getattr(self, '_speed_burst_timer', 0)
        if burst_timer > 0:
            mult = getattr(self, '_speed_burst_line_mult', 1.5)
            if "speed_burst" not in self._active_effect_visuals:
                try:
                    c = next((x for x in (getattr(self.card_manager, 'catalog', []) or []) if str(x.get('id', '')).startswith('speed_burst')), None)
                    if c:
                        self._remember_effect_visual('speed_burst', c)
                except Exception:
                    pass
            add("speed_burst", f"{burst_timer:.1f}s: Hızlı Düşüş + {mult}x Puan!", status=f"{burst_timer:.1f}s")
        else:
            self._active_effect_visuals.pop("speed_burst", None)

        # Global line multiplier (replaces old fixed +score line bonus)
        if int(getattr(self, '_line_clear_multiplier_remaining', 0) or 0) > 0 and float(getattr(self, '_line_clear_multiplier_value', 1.0)) > 1.0:
            rem = int(getattr(self, '_line_clear_multiplier_remaining', 0) or 0)
            mult = float(getattr(self, '_line_clear_multiplier_value', 1.0))
            add("line_bonus", f"Sonraki {rem} satır: {mult:.0f}x PUAN.", status=f"{rem} Satır")
        elif self.line_bonus_remaining > 0:
            add("line_bonus", f"Sonraki {self.line_bonus_remaining} satır +{self.line_bonus_amount} puan.", status=f"{self.line_bonus_remaining} Satır")
        else:
            self._active_effect_visuals.pop("line_bonus", None)

        if self.combo_aura_timer > 0:
            bonus = max(0, int(getattr(self, 'combo_aura_bonus', 0) or 0))
            if bonus > 0:
                add("combo_boost", f"{self.combo_aura_timer:.1f} sn combon korunuyor (+{bonus}).", status=f"{self.combo_aura_timer:.1f}s")
            else:
                add("combo_boost", f"{self.combo_aura_timer:.1f} sn combon korunuyor.", status=f"{self.combo_aura_timer:.1f}s")
        else:
            self._active_effect_visuals.pop("combo_boost", None)

        # Dynamic score window
        if getattr(self, '_score_multiplier_timer', 0.0) > 0 and float(getattr(self, '_score_multiplier_value', 1.0)) > 1.0:
            add("score", f"{float(self._score_multiplier_timer):.1f} sn: {float(self._score_multiplier_value):.0f}x skor penceresi.", status=f"{float(self._score_multiplier_timer):.1f}s")
        else:
            self._active_effect_visuals.pop("score", None)

        # Forced upcoming pieces
        try:
            q = list(getattr(self.card_manager, 'force_piece_queue', []) or [])
        except Exception:
            q = []
        if q:
            preview = ", ".join(str(x) for x in q[:3])
            suffix = "" if len(q) <= 3 else "..."
            add("force_piece", f"Sonraki {len(q)} parça: {preview}{suffix}", status=f"{len(q)} Prc")
        else:
            self._active_effect_visuals.pop("force_piece", None)

        # Armed nova burst
        if int(getattr(self, '_armed_nova_clusters', 0) or 0) > 0:
            add("nova_burst", f"Armalı Nova: {int(self._armed_nova_clusters)} kilitte 3x3 patlama.", status=f"{int(self._armed_nova_clusters)} Kilit")
        else:
            self._active_effect_visuals.pop("nova_burst", None)

        # Quantum Tunneling (Hayalet Parça): visible while charges remain or a piece is currently tunneled.
        try:
            charges = int(getattr(self, 'tunnel_charges_remaining', 0) or 0)
        except Exception:
            charges = 0
        try:
            is_tunneled = bool(getattr(getattr(self, 'current_piece', None), 'tunnel', False))
        except Exception:
            is_tunneled = False
        if charges > 0 or is_tunneled:
            # Robustness: if visuals were cleared for any reason, rebuild from catalog
            # so the left panel always shows remaining charges.
            if "quantum_tunneling" not in self._active_effect_visuals:
                try:
                    card = next((c for c in (getattr(self.card_manager, 'catalog', []) or []) if c.get('id') == 'quantum_tunneling'), None)
                except Exception:
                    card = None
                if card:
                    try:
                        self._remember_effect_visual('quantum_tunneling', card)
                    except Exception:
                        pass

        if (charges > 0 or is_tunneled) and "quantum_tunneling" in self._active_effect_visuals:
            _g_lbl = _card_key('G', 'card_ghost')
            if is_tunneled:
                add("quantum_tunneling", f"Aktif hayalet parça. ({_g_lbl}) Kalan hak: {charges}", status=f"{_g_lbl}: {charges} Hak")
            else:
                add("quantum_tunneling", f"{_g_lbl} ile istediğin parçayı hayalet yap. Kalan hak: {charges}", status=f"{_g_lbl}: {charges} Hak")
        else:
            self._active_effect_visuals.pop("quantum_tunneling", None)

        # Hammer (Çekiç): visible while charges remain.
        try:
            h_charges = int(getattr(self, 'hammer_charges_remaining', 0) or 0)
        except Exception:
            h_charges = 0
        if h_charges > 0:
            if "hammer" not in self._active_effect_visuals:
                try:
                    card = next((c for c in (getattr(self.card_manager, 'catalog', []) or []) if c.get('id') == 'hammer'), None)
                except Exception:
                    card = None
                if card:
                    try:
                        self._remember_effect_visual('hammer', card)
                    except Exception:
                        pass
        if h_charges > 0 and "hammer" in self._active_effect_visuals:
            _h_lbl = _card_key('H', 'card_hammer')
            add("hammer", f"{_h_lbl} ile mevcut parçayı 1x1 yap. Kalan hak: {h_charges}", status=f"{_h_lbl}: {h_charges} Hak")
        else:
            self._active_effect_visuals.pop("hammer", None)

        # Bomba Ustası (M tuşu): visible while charges remain.
        try:
            b_charges = int(getattr(self, 'bomb_master_charges', 0) or 0)
        except Exception:
            b_charges = 0
        if b_charges > 0:
            if "bomb_master" not in self._active_effect_visuals:
                try:
                    card = next((c for c in (getattr(self.card_manager, 'catalog', []) or []) if c.get('id') == 'bomb_master'), None)
                except Exception:
                    card = None
                if card:
                    try:
                        self._remember_effect_visual('bomb_master', card)
                    except Exception:
                        pass
        if b_charges > 0 and "bomb_master" in self._active_effect_visuals:
            _b_lbl = _card_key('M', 'card_bomb')
            add("bomb_master", f"{_b_lbl} ile mevcut parçayı mini bomba yap. Kalan hak: {b_charges}", status=f"{_b_lbl}: {b_charges} Hak")
        else:
            self._active_effect_visuals.pop("bomb_master", None)

        # Tuttuğunu Koparan (B tuşu): visible while charges remain.
        try:
            hd_charges = int(getattr(self, '_hold_destroyer_charges', 0) or 0)
        except Exception:
            hd_charges = 0
        if hd_charges > 0:
            if "hold_destroyer" not in self._active_effect_visuals:
                try:
                    card = next((c for c in (getattr(self.card_manager, 'catalog', []) or []) if str(c.get('id', '')).startswith('hold_destroyer')), None)
                except Exception:
                    card = None
                if card:
                    try:
                        self._remember_effect_visual('hold_destroyer', card)
                    except Exception:
                        pass
        if hd_charges > 0 and "hold_destroyer" in self._active_effect_visuals:
            _b_lbl = _card_key('B', 'discard_held')
            add("hold_destroyer", f"{_b_lbl} ile saklanan parçayı sil. Kalan hak: {hd_charges}", status=f"{_b_lbl}: {hd_charges} Hak")
        else:
            self._active_effect_visuals.pop("hold_destroyer", None)

        # Son Düşüş (F tuşu): visible while charges remain or freeze is active.
        try:
            fd_charges = int(getattr(self, '_freeze_drop_charges', 0) or 0)
        except Exception:
            fd_charges = 0
        fd_active = bool(getattr(self, '_freeze_drop_active', False))
        if fd_charges > 0 or fd_active:
            if "freeze_drop" not in self._active_effect_visuals:
                try:
                    card = next((c for c in (getattr(self.card_manager, 'catalog', []) or []) if str(c.get('id', '')).startswith('freeze_drop')), None)
                except Exception:
                    card = None
                if card:
                    try:
                        self._remember_effect_visual('freeze_drop', card)
                    except Exception:
                        pass
        if (fd_charges > 0 or fd_active) and "freeze_drop" in self._active_effect_visuals:
            _f_lbl = _card_key('F', 'card_freeze')
            if fd_active:
                fd_timer = getattr(self, '_freeze_drop_timer', 0.0)
                add("freeze_drop", f"❄️ Blok dondu! {fd_timer:.1f}s kaldı. Kalan hak: {fd_charges}", status=f"{fd_timer:.1f}s | {fd_charges} Hak")
            else:
                add("freeze_drop", f"{_f_lbl} ile bloğu dondur. Kalan hak: {fd_charges}", status=f"{_f_lbl}: {fd_charges} Hak")
        else:
            self._active_effect_visuals.pop("freeze_drop", None)

        # Laser Drill: active only while the current piece is drill-enabled
        try:
            is_drill = bool(getattr(getattr(self, 'current_piece', None), 'drill', False))
        except Exception:
            is_drill = False
        if is_drill and "laser_drill" in self._active_effect_visuals:
            add("laser_drill", "Parça delici: temas ettiği blokları siler.", status="Aktif")
        else:
            self._active_effect_visuals.pop("laser_drill", None)
        
        # Sniper Shot: N tuşuyla aktifleşir
        try:
            sniper_charges = int(getattr(self, '_sniper_charges', 0) or 0)
        except Exception:
            sniper_charges = 0
        if sniper_charges > 0:
            if "sniper_shot" not in self._active_effect_visuals:
                try:
                    card = next((c for c in (getattr(self.card_manager, 'catalog', []) or []) if c.get('id') == 'sniper_shot'), None)
                except Exception:
                    card = None
                if card:
                    try:
                        self._remember_effect_visual('sniper_shot', card)
                    except Exception:
                        pass
        if sniper_charges > 0 and "sniper_shot" in self._active_effect_visuals:
            _n_lbl = _card_key('N', 'card_sniper')
            add("sniper_shot", f"{_n_lbl} ile blok sec ve patlat. Kalan hak: {sniper_charges}", status=f"{_n_lbl}: {sniper_charges} Hak")
        else:
            self._active_effect_visuals.pop("sniper_shot", None)
        
        # Zaman Kapsulu: R ile toggle (ilk basis kaydet, ikinci basis geri don)
        if getattr(self, 'time_capsule_available', False):
            if "time_capsule" not in self._active_effect_visuals:
                try:
                    card = next((c for c in (getattr(self.card_manager, 'catalog', []) or []) if c.get('id') == 'time_capsule'), None)
                except Exception:
                    card = None
                if card:
                    try:
                        self._remember_effect_visual('time_capsule', card)
                    except Exception:
                        pass
            
            if "time_capsule" in self._active_effect_visuals:
                _r_lbl = _card_key('R', 'card_time_capsule_restore')
                if getattr(self, 'time_capsule_saved', False):
                    add("time_capsule", f"{_r_lbl}: Geri Don (Kayit Hazir)", status=f"{_r_lbl}: Geri Don")
                else:
                    add("time_capsule", f"{_r_lbl}: Kaydet", status=f"{_r_lbl}: Kaydet")
        else:
            self._active_effect_visuals.pop("time_capsule", None)
        
        # Gravity Freeze (Krono Kilidi aktifken)
        if self.gravity_freeze_timer > 0:
            cards.append({
                'id': 'gravity_freeze_active',
                'title': 'Graviteden Muaf',
                'description': f'{self.gravity_freeze_timer:.1f} sn yerçekimi durdu',
                'color': (120, 220, 255),
                'icon': 'GF',
                'tag': 'Aktif',
                'style': {},
            })

        # Ghost Echo: active only when armed; display the number of rows it clears
        if "ghost_echo" in self._active_effect_visuals:
            viz = self._active_effect_visuals.get("ghost_echo")
            rows = int(viz.get("value", viz.get("base", 6)))
            add("ghost_echo", f"Oyun-sonu olursa üst {rows} satırı temizler.", status=f"{rows} Satır")
        else:
            self._active_effect_visuals.pop("ghost_echo", None)
        
        # === KALİCİ PERK KARTLARI ===
        # Perkler aktif olduğunda sol panelde göster
        # Map perk runtime ids to the corresponding catalog card ids so we can
        # reuse the same icon_image that the selection UI uses.
        try:
            catalog_by_id = {str(c.get('id')): c for c in (getattr(self.card_manager, 'catalog', []) or [])}
        except Exception:
            catalog_by_id = {}
        perk_to_card_id = {
            'chrono_lock': 'perk_chrono',
            'synergy_core': 'perk_synergy',
            'second_pocket': 'perk_second_pocket',
            'perk_alchemist': 'perk_alchemist',
        }
        # Only truly persistent perks (no usage limits) go here
        perk_defs = {
            'second_pocket': {
                'title': 'Ekstra Cep',
                'description': f'{_card_key("V", "hold2")} tuşu ile 2. hold',
                'status': f'{_card_key("V", "hold2")} Tuşu',
                'color': (200, 200, 255),
                'icon': '🎒',
                'tag': 'Perk'
            },
            'chrono_lock': {
                'title': 'Zaman Durdurucu',
                'description': 'Her 10 satır = 3 sn yerçekimi durur',
                'status': 'Aktif',
                'color': (120, 220, 255),
                'icon': '⏸️',
                'tag': 'Perk'
            },
            'synergy_core': {
                'title': 'Sinerji Bonus',
                'description': f'Perk başına +10% skor ({self.perk_manager.get_multiplier():.2f}x)',
                'status': f'{getattr(self.perk_manager, "get_multiplier", lambda: 1.0)():.2f}x',
                'color': (255, 220, 140),
                'icon': '🔗',
                'tag': 'Perk'
            },
            'perk_alchemist': {
                'title': 'Altın Dokunuş',
                'description': 'Quadrix = rastgele bloklar altına döner',
                'status': 'Altın',
                'color': (255, 210, 75),
                'icon': '✨',
                'tag': 'Perk'
            },
        }
        
        if hasattr(self, 'perk_manager'):
            for perk_id, perk_def in perk_defs.items():
                if self.perk_manager.is_active(perk_id):
                    card_id = perk_to_card_id.get(perk_id)
                    icon_image = None
                    try:
                        if card_id:
                            icon_image = catalog_by_id.get(card_id, {}).get('icon_image')
                    except Exception:
                        icon_image = None

                    # Use the catalog card id when possible so the left-panel history
                    # merge can dedupe properly (prevents showing the same perk twice).
                    # Fallback to a unique runtime id only if mapping is missing.
                    entry_id = str(card_id) if card_id else f'perk_{perk_id}'
                    cards.append({
                        'id': entry_id,
                        'title': perk_def['title'],
                        'description': perk_def['description'],
                        'status': perk_def.get('status', 'Aktif'),
                        'color': perk_def['color'],
                        'icon': perk_def['icon'],
                        'icon_image': icon_image,
                        'tag': perk_def['tag'],
                        'style': {},
                        'persistent': True,
                    })

        # Rewind is a limited ability (not a persistent perk): show under limited effects.
        try:
            uses = int(getattr(self.perk_manager, 'rewind_uses', 0) or 0)
        except Exception:
            uses = 0
        try:
            rewind_active = bool(getattr(self.perk_manager, 'is_active', lambda _k: False)('rewind_power'))
        except Exception:
            rewind_active = False
        if rewind_active and uses > 0:
            icon_image = None
            try:
                icon_image = catalog_by_id.get('rewind_power', {}).get('icon_image')
            except Exception:
                icon_image = None
            cards.append({
                'id': 'rewind_power',
                'title': 'Geri Sarma',
                'description': f'{_card_key("U", "card_rewind")} tuşu ({uses} kalan)',
                'status': f'{_card_key("U", "card_rewind")}: {uses} Hak',
                'color': (255, 200, 255),
                'icon': 'RW',
                'icon_image': icon_image,
                'tag': 'Epic',
                'style': {},
                'persistent': False,
            })

        # Şekil Değiştirici is a limited ability (3 uses): show under limited effects.
        try:
            phase_uses = int(getattr(self, 'phase_shift_uses_remaining', 0) or 0)
        except Exception:
            phase_uses = 0
        try:
            phase_active = bool(getattr(self.perk_manager, 'is_active', lambda _k: False)('phase_shift'))
        except Exception:
            phase_active = False
        if phase_active and phase_uses > 0:
            icon_image = None
            try:
                icon_image = catalog_by_id.get('perk_phase', {}).get('icon_image')
            except Exception:
                icon_image = None
            cards.append({
                'id': 'perk_phase',
                'title': 'Şekil Değiştirici',
                'description': f'{_card_key("LSHIFT", "card_phase_shift")} ({phase_uses} kalan)',
                'status': f'{_card_key("LSHIFT", "card_phase_shift")}: {phase_uses} Hak',
                'color': (255, 200, 255),
                'icon': '🔄',
                'icon_image': icon_image,
                'tag': 'Epic',
                'style': {},
                'persistent': False,
            })

        self.card_manager.active_cards = cards

    def _nova_burst(self, clusters: int) -> None:
        width = len(self.board.grid[0])
        height = len(self.board.grid)
        cleared_cells = 0
        cleared_coords: list[tuple[int, int]] = []
        now_ms = None
        try:
            now_ms = int(pygame.time.get_ticks())
        except Exception:
            now_ms = None
        for _ in range(max(1, clusters)):
            cx = random.randrange(width)
            cy = random.randrange(height)
            for y in range(max(0, cy - 1), min(height, cy + 2)):
                for x in range(max(0, cx - 1), min(width, cx + 2)):
                    if self.board.occupancy[y][x] or self.board.grid[y][x] != BLACK:
                        self.board.grid[y][x] = BLACK
                        self.board.texture_grid[y][x] = None
                        self.board.occupancy[y][x] = False
                        try:
                            self.board.gold[y][x] = False
                        except Exception:
                            pass
                        try:
                            self.board.owners[y][x] = None
                        except Exception:
                            pass
                        cleared_cells += 1
                        cleared_coords.append((int(x), int(y)))
        if cleared_cells:
            try:
                self._trace_ghost_bug_clear(
                    now_ms=now_ms,
                    clear_kind='nova_random',
                    cleared_cells=cleared_cells,
                    coords=cleared_coords,
                    piece=getattr(self, 'current_piece', None),
                    note=f"clusters={int(clusters)}",
                )
            except Exception:
                pass
        if cleared_cells and self.sound_enabled:
            self.sound.play_sound("clear")
        self.board.score += cleared_cells * 40
        # spawn particles for nova
        if self.effects_enabled:
            board_width = BOARD_WIDTH * 25
            board_height = BOARD_HEIGHT * 25
            offset_x = (self.window_width - board_width) // 2
            offset_y = (self.window_height - board_height) // 2
            for _ in range(min(10, clusters * 2)):
                cx = random.randint(0, BOARD_WIDTH - 1)
                cy = random.randint(0, BOARD_HEIGHT - 1)
                x = offset_x + cx * 25 + 12
                y = offset_y + cy * 25 + 12
                self.create_power_particles(x, y, self.mode_skin.accent, count=8)

    def _shave_peaks(self, layers: int) -> None:
        width = len(self.board.grid[0])
        height = len(self.board.grid)
        removed = 0
        for _ in range(max(1, layers)):
            for col in range(width):
                for row in range(height):
                    if self.board.occupancy[row][col]:
                        self.board.grid[row][col] = BLACK
                        self.board.texture_grid[row][col] = None
                        self.board.occupancy[row][col] = False
                        try:
                            self.board.gold[row][col] = False
                        except Exception:
                            pass
                        try:
                            self.board.owners[row][col] = None
                        except Exception:
                            pass
                        removed += 1
                        break
        if removed and self.sound_enabled:
            self.sound.play_sound("clear")

    def _shuffle_bottom_rows(self, row_count: int) -> None:
        """Satır Karıştırıcı: En alt satırlardaki blokları rastgele karıştır"""
        width = len(self.board.grid[0])
        height = len(self.board.grid)
        row_count = max(1, min(row_count, height))
        
        # Alt bölgedeki hücreleri (dolu/boş dahil) topla ve karıştır.
        # Böylece "karıştırma" boşlukları sıkıştırmaz; dolu/boş sayısı korunur.
        cells: list[tuple[bool, object, object, bool, object]] = []
        for row in range(height - row_count, height):
            for col in range(width):
                occ = bool(self.board.occupancy[row][col])
                if occ:
                    try:
                        gold = bool(self.board.gold[row][col])
                    except Exception:
                        gold = False
                    try:
                        owner = self.board.owners[row][col]
                    except Exception:
                        owner = None
                    cells.append((True, self.board.grid[row][col], self.board.texture_grid[row][col], gold, owner))
                else:
                    cells.append((False, BLACK, None, False, None))

        random.shuffle(cells)

        idx = 0
        for row in range(height - row_count, height):
            for col in range(width):
                occ, colr, tex, gold, owner = cells[idx]
                idx += 1
                if occ:
                    self.board.grid[row][col] = colr
                    self.board.texture_grid[row][col] = tex
                    self.board.occupancy[row][col] = True
                    try:
                        self.board.gold[row][col] = bool(gold)
                    except Exception:
                        pass
                    try:
                        self.board.owners[row][col] = owner
                    except Exception:
                        pass
                else:
                    self.board.grid[row][col] = BLACK
                    self.board.texture_grid[row][col] = None
                    self.board.occupancy[row][col] = False
                    try:
                        self.board.gold[row][col] = False
                    except Exception:
                        pass
                    try:
                        self.board.owners[row][col] = None
                    except Exception:
                        pass
        
        # Satır temizleme kontrolü
        prev_score = int(getattr(self.board, 'score', 0))
        cleared = self.board.clear_lines(source='card')
        if cleared > 0:
            try:
                delta = int(getattr(self.board, 'score', 0)) - prev_score
            except Exception:
                delta = None
            self._post_external_line_clear(cleared, award_energy=True, score_delta=delta, source='card')
        
        if self.sound_enabled:
            self.sound.play_sound("clear")
    
    def _spawn_card_particles(self, color: tuple[int, int, int]) -> None:
        if not self.effects_enabled:
            return
        center_x = self.window_width // 2
        center_y = self.window_height // 2
        self.create_particles(count=30, x=center_x, y=center_y, colors=[color], speed=6)

    def _clear_rows(self, count: int) -> None:
        width = len(self.board.grid[0])
        count = max(1, min(count, len(self.board.grid)))
        prev_combo = int(getattr(self.board, 'combo', 0) or 0)
        prev_level = int(getattr(self.board, 'level', 1) or 1)
        for _ in range(count):
            self.board.grid.pop()
            self.board.grid.insert(0, [BLACK] * width)
            self.board.texture_grid.pop()
            self.board.texture_grid.insert(0, [None] * width)
            self.board.occupancy.pop()
            self.board.occupancy.insert(0, [False] * width)
            try:
                if hasattr(self.board, 'gold'):
                    self.board.gold.pop()
                    self.board.gold.insert(0, [False] * width)
            except Exception:
                pass
            try:
                if hasattr(self.board, 'owners'):
                    self.board.owners.pop()
                    self.board.owners.insert(0, [None] * width)
            except Exception:
                pass
        # Physically settle blocks (fill holes) after removing the floor
        try:
            self.board.apply_gravity()
        except Exception:
            pass
        # Update stats lines but do NOT contribute to level progression (anti-farm)
        self.board.lines_cleared += count
        try:
            self.board.level = prev_level
        except Exception:
            pass
        # Keep combo alive
        self.board.combo = prev_combo
        self.board.score += count * 150
        if self.sound_enabled:
            self.sound.play_sound("clear")

    def _queue_force_pieces(self, count: int) -> None:
        preferred = ["I", "T", "O", "L"]
        for _ in range(max(1, count)):
            self.card_manager.queue_force_piece(random.choice(preferred))

    def _clear_columns(self, count: int) -> None:
        width = len(self.board.grid[0])
        height = len(self.board.grid)
        for _ in range(max(1, count)):
            column = random.randrange(width)
            for row in range(height):
                self.board.grid[row][column] = BLACK
                self.board.texture_grid[row][column] = None
                self.board.occupancy[row][column] = False
                try:
                    self.board.gold[row][column] = False
                except Exception:
                    pass
                try:
                    self.board.owners[row][column] = None
                except Exception:
                    pass
        if self.sound_enabled:
            self.sound.play_sound("clear")

    def _clear_columns_for_current_piece(self) -> int:
        if not getattr(self, 'current_piece', None):
            return 0
        width = len(self.board.grid[0])
        height = len(self.board.grid)
        cols = sorted({x for x, y in self.current_piece.get_cells() if 0 <= x < width})
        if not cols:
            return 0
        cleared_cells = 0
        for column in cols:
            for row in range(height):
                if self.board.occupancy[row][column] or self.board.grid[row][column] != BLACK:
                    cleared_cells += 1
                self.board.grid[row][column] = BLACK
                self.board.texture_grid[row][column] = None
                self.board.occupancy[row][column] = False
                try:
                    self.board.gold[row][column] = False
                except Exception:
                    pass
                try:
                    self.board.owners[row][column] = None
                except Exception:
                    pass
        if self.sound_enabled:
            self.sound.play_sound('clear')
        return cleared_cells

    def _sedimentation_collapse(self) -> None:
        """Deprem/Sedimentation: tüm kolonları aşağı sıkıştır."""
        prev_score = int(getattr(self.board, 'score', 0))
        try:
            self.board.apply_gravity()
        except Exception:
            pass
        try:
            cleared = int(self.board.clear_lines(source='card'))
        except Exception:
            cleared = 0
        if cleared > 0:
            try:
                delta = int(getattr(self.board, 'score', 0)) - prev_score
            except Exception:
                delta = None
            self._post_external_line_clear(cleared, award_energy=True, score_delta=delta, source='card')

    def _arm_nova_burst(self, charges: int, card: Dict) -> None:
        n = max(1, int(charges))
        total = int(getattr(self, '_armed_nova_clusters', 0) or 0) + n
        self._armed_nova_clusters = total
        self._remember_effect_visual('nova_burst', card)
        try:
            self.card_message = f"Nova Patlaması: +{n} şarj (toplam {total})"
            self.card_message_timer = 0.9
        except Exception:
            pass
        self._sync_active_cards()

    def _activate_drill_piece(self) -> None:
        if not getattr(self, 'current_piece', None):
            return
        setattr(self.current_piece, 'drill', True)
        try:
            setattr(self.current_piece, '_original_color', getattr(self.current_piece, 'color', None))
        except Exception:
            pass
        # Kırmızı vurgu
        try:
            self.current_piece.color = (255, 70, 70)
        except Exception:
            pass
        self._drill_last_cleanup_y = getattr(self.current_piece, 'y', None)
        # NERF: Hareket kilidi başlangıçta kapalı
        self._drill_movement_locked = False

    def _cleanup_drill_overlaps(self) -> None:
        piece = getattr(self, 'current_piece', None)
        if not piece or not getattr(piece, 'drill', False):
            return
        width = int(getattr(self.board, 'width', BOARD_WIDTH))
        height = int(getattr(self.board, 'height', BOARD_HEIGHT))
        cleared_cells = 0
        cleared_coords: list[tuple[int, int]] = []
        now_ms = None
        try:
            now_ms = int(pygame.time.get_ticks())
        except Exception:
            now_ms = None
        for x, y in piece.get_cells():
            if 0 <= x < width and 0 <= y < height and self.board.occupancy[y][x]:
                self.board.occupancy[y][x] = False
                self.board.grid[y][x] = BLACK
                self.board.texture_grid[y][x] = None
                try:
                    self.board.gold[y][x] = False
                except Exception:
                    pass
                try:
                    self.board.owners[y][x] = None
                except Exception:
                    pass
                cleared_cells += 1
                cleared_coords.append((int(x), int(y)))
        if cleared_cells:
            try:
                self._trace_ghost_bug_clear(
                    now_ms=now_ms,
                    clear_kind='drill',
                    cleared_cells=cleared_cells,
                    coords=cleared_coords,
                    piece=piece,
                )
            except Exception:
                pass
            self.board.score += cleared_cells * 20
            if self.sound_enabled:
                self.sound.play_sound('clear')
            # NERF: İlk bloğa değdikten sonra hareket kilitlenir
            self._drill_movement_locked = True

    def _level_peaks(self, steps: int) -> int:
        """Tepe Dilimleyici (Leveler): sivri tepeleri keserek max-min farkını azalt."""
        width = len(self.board.grid[0])
        height = len(self.board.grid)
        steps = max(1, int(steps))

        def col_height(x: int) -> int:
            for y in range(height):
                if self.board.occupancy[y][x]:
                    return height - y
            return 0

        removed = 0
        for _ in range(steps):
            heights = [col_height(x) for x in range(width)]
            if not heights:
                break
            max_h = max(heights)
            min_h = min(heights)
            if max_h <= 0 or (max_h - min_h) <= 1:
                break
            x = heights.index(max_h)
            # Remove the top-most block of the tallest column
            for y in range(height):
                if self.board.occupancy[y][x]:
                    self.board.grid[y][x] = BLACK
                    self.board.texture_grid[y][x] = None
                    self.board.occupancy[y][x] = False
                    try:
                        self.board.gold[y][x] = False
                    except Exception:
                        pass
                    try:
                        self.board.owners[y][x] = None
                    except Exception:
                        pass
                    removed += 1
                    break
        if removed and self.sound_enabled:
            self.sound.play_sound('clear')
        return int(removed)

    def finalize_run(self, playtime: int | None = None) -> None:
        """Extend finalize_run to add XP and fragments for Mystery Mode."""
        # Run base finalize
        super().finalize_run(playtime)
        # Add XP and fragments for the current user
        if self.user_manager:
            xp_award = int(self.board.score / 10)
            self.user_manager.add_xp('mystery', xp_award)
            fragments = int((self.board.score / 100) + (self.board.level * 20) + (self.board.lines_cleared * 5))
            self.user_manager.add_fragments(fragments)

    def draw_textured_block(self, x, y, size, color, texture_surface=None, texture_slice: TextureSlice | None = None):
        """Draw the block and, if Cyberpunk theme is active, add neon glow."""
        super().draw_textured_block(x, y, size, color, texture_surface, texture_slice)
        if self.theme_manager and getattr(self.theme_manager, 'theme_name', '').lower() == 'cyberpunk':
            glow = pygame.Surface((size + 8, size + 8), pygame.SRCALPHA)
            glow_color = tuple(min(255, int(c * 1.4)) for c in color[:3])
            pygame.draw.rect(glow, (*glow_color, 35), (0, 0, size + 8, size + 8), border_radius=8)
            self.screen.blit(glow, (x - 4, y - 4), special_flags=pygame.BLEND_ADD)

    # === BLOK ATÖLYESİ KARTI METODLARI ===

    def _open_card_workshop_popup(self) -> None:
        """Kart modu içi mini blok atölyesi popup'ını açar."""
        self._card_workshop_active = True
        self._card_workshop_grid = [[None for _ in range(7)] for _ in range(7)]
        self._card_workshop_cursor_x = 3
        self._card_workshop_cursor_y = 3
        self._card_workshop_color = (0, 255, 255)
        self._card_workshop_message = "Blok atolyesi! Maks 7 blok. ENTER ile tamamla."
        self._card_workshop_message_timer = 5.0
        pygame.mouse.set_visible(True)
        try:
            self.card_message = "Blok Atolyesi acildi! Parca olustur ve ENTER ile tamamla."
            self.card_message_timer = 3.0
        except Exception:
            pass

    def _close_card_workshop_popup(self) -> None:
        """Blok atölyesi popup'ını kapatır."""
        self._card_workshop_active = False
        self._card_workshop_grid = None
        self._card_workshop_cursor_x = 0
        self._card_workshop_cursor_y = 0
        self._card_workshop_message = ""
        self._card_workshop_message_timer = 0

    def _card_workshop_count_blocks(self) -> int:
        """Atölye grid'indeki blok sayısını say."""
        if not self._card_workshop_grid:
            return 0
        count = 0
        for row in self._card_workshop_grid:
            for cell in row:
                if cell is not None:
                    count += 1
        return count

    def _card_workshop_get_positions(self) -> list:
        """Grid'deki tüm blok pozisyonlarını döndür."""
        positions = []
        if not self._card_workshop_grid:
            return positions
        for y in range(7):
            for x in range(7):
                if self._card_workshop_grid[y][x] is not None:
                    positions.append((x, y))
        return positions

    def _card_workshop_is_connected(self) -> bool:
        """Blokların birbirine bağlı olup olmadığını kontrol et."""
        positions = self._card_workshop_get_positions()
        if len(positions) <= 1:
            return True
        pos_set = set(positions)
        visited = set()
        to_visit = [positions[0]]
        while to_visit:
            x, y = to_visit.pop()
            if (x, y) in visited:
                continue
            visited.add((x, y))
            for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nx, ny = x + dx, y + dy
                if (nx, ny) in pos_set and (nx, ny) not in visited:
                    to_visit.append((nx, ny))
        return len(visited) == len(positions)

    def _card_workshop_finish(self) -> None:
        """Atölye parçasını tamamla ve oyuna ekle."""
        positions = self._card_workshop_get_positions()
        if len(positions) < 2:
            self._card_workshop_message = "En az 2 blok gerekli!"
            self._card_workshop_message_timer = 2.0
            return
        if not self._card_workshop_is_connected():
            self._card_workshop_message = "Bloklar birbirine bagli olmali!"
            self._card_workshop_message_timer = 2.0
            return

        # Normalize shape 
        min_x = min(x for x, y in positions)
        min_y = min(y for x, y in positions)
        normalized = [(x - min_x, y - min_y) for x, y in positions]

        # Renkleri topla
        colors = {}
        for x, y in positions:
            colors[(x - min_x, y - min_y)] = self._card_workshop_grid[y][x]['color']

        # shape matris oluştur
        max_x = max(x for x, y in normalized)
        max_y = max(y for x, y in normalized)
        shape = [[0 for _ in range(max_x + 1)] for _ in range(max_y + 1)]
        for x, y in normalized:
            shape[y][x] = 1

        # color_matrix oluştur
        color_matrix = [[None for _ in range(max_x + 1)] for _ in range(max_y + 1)]
        for (x, y), col in colors.items():
            color_matrix[y][x] = col

        # Piece oluştur - custom shape ile
        piece = Piece(x=max(0, (self.board.width - len(shape[0])) // 2), y=0, shape_index=0)
        # Shape'i ve rengi manuel override et
        piece.shape = shape
        piece.color = self._card_workshop_color
        piece.name = "Workshop_Card"
        piece.shape_index = -1  # Custom parça
        piece.is_workshop_piece = True
        piece.color_matrix = color_matrix
        piece._force_color = None

        # Mevcut parçayı değiştir
        try:
            self.current_piece = piece
            self.apply_theme_to_pieces()
        except Exception:
            pass

        self._close_card_workshop_popup()
        try:
            self.card_message = "Atolye parcasi hazirlandi! Hemen kullanabilirsin."
            self.card_message_timer = 2.0
        except Exception:
            pass
        if self.sound_enabled:
            try:
                self.sound.play_sound('levelup')
            except Exception:
                pass

    def _handle_card_workshop_input(self, event) -> bool:
        """Kart atölyesi popup'ının input'larını işler. True dönerse event tüketildi."""
        if not getattr(self, '_card_workshop_active', False):
            return False

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self._close_card_workshop_popup()
                return True
            elif event.key == pygame.K_RETURN:
                self._card_workshop_finish()
                return True
            elif event.key == pygame.K_UP:
                self._card_workshop_cursor_y = max(0, self._card_workshop_cursor_y - 1)
                return True
            elif event.key == pygame.K_DOWN:
                self._card_workshop_cursor_y = min(6, self._card_workshop_cursor_y + 1)
                return True
            elif event.key == pygame.K_LEFT:
                self._card_workshop_cursor_x = max(0, self._card_workshop_cursor_x - 1)
                return True
            elif event.key == pygame.K_RIGHT:
                self._card_workshop_cursor_x = min(6, self._card_workshop_cursor_x + 1)
                return True
            elif event.key == pygame.K_SPACE:
                # Blok yerleştir / sil
                cx, cy = self._card_workshop_cursor_x, self._card_workshop_cursor_y
                if self._card_workshop_grid[cy][cx] is not None:
                    # Sil
                    temp = self._card_workshop_grid[cy][cx]
                    self._card_workshop_grid[cy][cx] = None
                    if self._card_workshop_count_blocks() > 0 and not self._card_workshop_is_connected():
                        self._card_workshop_grid[cy][cx] = temp
                        self._card_workshop_message = "Silme baglantıyı koparir!"
                        self._card_workshop_message_timer = 1.5
                    else:
                        self._card_workshop_message = "Blok silindi."
                        self._card_workshop_message_timer = 1.0
                else:
                    # Yerleştir
                    if self._card_workshop_count_blocks() >= 7:
                        self._card_workshop_message = "Maks 7 blok!"
                        self._card_workshop_message_timer = 1.5
                    else:
                        self._card_workshop_grid[cy][cx] = {'color': self._card_workshop_color}
                        if self._card_workshop_count_blocks() > 1 and not self._card_workshop_is_connected():
                            self._card_workshop_grid[cy][cx] = None
                            self._card_workshop_message = "Bloklar birbirine bagli olmali!"
                            self._card_workshop_message_timer = 1.5
                        else:
                            remaining = 7 - self._card_workshop_count_blocks()
                            self._card_workshop_message = f"Blok eklendi. Kalan: {remaining}"
                            self._card_workshop_message_timer = 1.0
                return True
        elif event.type == pygame.MOUSEBUTTONDOWN:
            # Mouse ile tıklanabilir grid
            pos = getattr(event, 'pos', None)
            if pos and hasattr(self, '_card_workshop_grid_rect'):
                gr = self._card_workshop_grid_rect
                if gr.collidepoint(pos):
                    cell_size = gr.width // 7
                    mx = (pos[0] - gr.x) // cell_size
                    my = (pos[1] - gr.y) // cell_size
                    if 0 <= mx < 7 and 0 <= my < 7:
                        self._card_workshop_cursor_x = mx
                        self._card_workshop_cursor_y = my
                        # Sol tık = yerleştir, sağ tık = sil
                        if event.button == 1:
                            if self._card_workshop_grid[my][mx] is None:
                                if self._card_workshop_count_blocks() < 7:
                                    self._card_workshop_grid[my][mx] = {'color': self._card_workshop_color}
                                    if self._card_workshop_count_blocks() > 1 and not self._card_workshop_is_connected():
                                        self._card_workshop_grid[my][mx] = None
                                        self._card_workshop_message = "Bloklar birbirine bagli olmali!"
                                        self._card_workshop_message_timer = 1.5
                                    else:
                                        remaining = 7 - self._card_workshop_count_blocks()
                                        self._card_workshop_message = f"Blok eklendi. Kalan: {remaining}"
                                        self._card_workshop_message_timer = 1.0
                                else:
                                    self._card_workshop_message = "Maks 7 blok!"
                                    self._card_workshop_message_timer = 1.5
                            else:
                                # Zaten blok var, sil
                                temp = self._card_workshop_grid[my][mx]
                                self._card_workshop_grid[my][mx] = None
                                if self._card_workshop_count_blocks() > 0 and not self._card_workshop_is_connected():
                                    self._card_workshop_grid[my][mx] = temp
                                    self._card_workshop_message = "Silme baglantıyı koparir!"
                                    self._card_workshop_message_timer = 1.5
                                else:
                                    self._card_workshop_message = "Blok silindi."
                                    self._card_workshop_message_timer = 1.0
                        elif event.button == 3:
                            if self._card_workshop_grid[my][mx] is not None:
                                temp = self._card_workshop_grid[my][mx]
                                self._card_workshop_grid[my][mx] = None
                                if self._card_workshop_count_blocks() > 0 and not self._card_workshop_is_connected():
                                    self._card_workshop_grid[my][mx] = temp
                                    self._card_workshop_message = "Silme baglantıyı koparir!"
                                    self._card_workshop_message_timer = 1.5
                                else:
                                    self._card_workshop_message = "Blok silindi."
                                    self._card_workshop_message_timer = 1.0
                    return True
        return False

    def _draw_card_workshop_popup(self) -> None:
        """Kart modundaki mini blok atölyesi popup'ını çizer."""
        if not getattr(self, '_card_workshop_active', False):
            return

        # Popup boyutları
        popup_width = 500
        popup_height = 520
        popup_x = (self.window_width - popup_width) // 2
        popup_y = (self.window_height - popup_height) // 2

        # Arka plan overlay
        overlay = pygame.Surface((self.window_width, self.window_height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 200))
        self.screen.blit(overlay, (0, 0))

        # Dış glow
        glow_rect = pygame.Rect(popup_x - 15, popup_y - 15, popup_width + 30, popup_height + 30)
        glow_surf = pygame.Surface((glow_rect.width, glow_rect.height), pygame.SRCALPHA)
        pygame.draw.rect(glow_surf, (255, 200, 80, 40), glow_surf.get_rect(), border_radius=20)
        self.screen.blit(glow_surf, glow_rect.topleft)

        # Panel
        popup_rect = pygame.Rect(popup_x, popup_y, popup_width, popup_height)
        retro_style.draw_glass_panel(self.screen, popup_rect, alpha=240, border_color=(255, 200, 80), glow=True)

        # Başlık
        title_font = self.mystery_font_large
        title_surf = title_font.render("Blok Atolyesi", True, (255, 220, 100))
        self.screen.blit(title_surf, (popup_x + (popup_width - title_surf.get_width()) // 2, popup_y + 12))

        # Ayırıcı çizgi
        pygame.draw.line(self.screen, (255, 200, 80, 150), (popup_x + 20, popup_y + 48), (popup_x + popup_width - 20, popup_y + 48), 2)

        # Grid
        cell_size = 48
        grid_width = 7 * cell_size
        grid_x = popup_x + (popup_width - grid_width) // 2
        grid_y = popup_y + 60
        self._card_workshop_grid_rect = pygame.Rect(grid_x, grid_y, grid_width, grid_width)

        # Grid arka planı
        grid_bg = pygame.Surface((grid_width + 4, grid_width + 4), pygame.SRCALPHA)
        pygame.draw.rect(grid_bg, (20, 20, 30, 200), grid_bg.get_rect(), border_radius=8)
        self.screen.blit(grid_bg, (grid_x - 2, grid_y - 2))

        # Hücreleri çiz
        for gy in range(7):
            for gx in range(7):
                cx = grid_x + gx * cell_size
                cy = grid_y + gy * cell_size
                cell_rect = pygame.Rect(cx, cy, cell_size - 1, cell_size - 1)

                if self._card_workshop_grid[gy][gx] is not None:
                    color = self._card_workshop_grid[gy][gx]['color']
                    pygame.draw.rect(self.screen, color, cell_rect, border_radius=4)
                    # 3D efekt
                    lighter = tuple(min(255, int(c * 1.4)) for c in color[:3])
                    darker = tuple(max(0, int(c * 0.4)) for c in color[:3])
                    pygame.draw.line(self.screen, lighter, (cx, cy), (cx + cell_size - 2, cy), 2)
                    pygame.draw.line(self.screen, lighter, (cx, cy), (cx, cy + cell_size - 2), 2)
                    pygame.draw.line(self.screen, darker, (cx + 1, cy + cell_size - 2), (cx + cell_size - 2, cy + cell_size - 2), 2)
                    pygame.draw.line(self.screen, darker, (cx + cell_size - 2, cy + 1), (cx + cell_size - 2, cy + cell_size - 2), 2)
                else:
                    pygame.draw.rect(self.screen, (40, 40, 50), cell_rect, border_radius=2)
                    pygame.draw.rect(self.screen, (60, 60, 70), cell_rect, width=1, border_radius=2)

                # Cursor
                if gx == self._card_workshop_cursor_x and gy == self._card_workshop_cursor_y:
                    pygame.draw.rect(self.screen, (255, 255, 255), cell_rect, width=2, border_radius=4)

        # Bilgi alanı
        info_y = grid_y + grid_width + 12
        block_count = self._card_workshop_count_blocks()
        info_font = self.mystery_font_small
        
        # Blok sayısı
        count_text = f"Blok: {block_count}/7"
        count_surf = info_font.render(count_text, True, (200, 200, 210))
        self.screen.blit(count_surf, (popup_x + 20, info_y))

        # Mesaj
        msg_timer = getattr(self, '_card_workshop_message_timer', 0)
        if msg_timer > 0:
            msg = getattr(self, '_card_workshop_message', '')
            msg_surf = info_font.render(msg, True, (255, 220, 100))
            self.screen.blit(msg_surf, (popup_x + (popup_width - msg_surf.get_width()) // 2, info_y + 30))

        # Kontroller
        controls_y = info_y + 60
        controls = [
            "Yön tuslari: Hareket | SPACE: Yerlestir/Sil",
            "ENTER: Tamamla | ESC: Iptal",
            "Mouse: Sol tik yerlestir/sil",
        ]
        for i, line in enumerate(controls):
            ctrl_surf = info_font.render(line, True, (140, 140, 155))
            self.screen.blit(ctrl_surf, (popup_x + (popup_width - ctrl_surf.get_width()) // 2, controls_y + i * 20))

    # === RENK TEMİZLEME KARTI METODU ===

    def _apply_color_cleanse(self) -> None:
        """Rastgele bir renkteki tüm blokları temizler, gravity uygular."""
        # Tahtadaki tüm benzersiz renkleri topla
        color_map = {}
        for y in range(self.board.height):
            for x in range(self.board.width):
                if self.board.occupancy[y][x]:
                    color = self.board.grid[y][x]
                    if color and color != (0, 0, 0):
                        key = color[:3]
                        if key not in color_map:
                            color_map[key] = []
                        color_map[key].append((x, y))

        if not color_map:
            self.card_message = "Renk Temizleme: Tahta bos!"
            self.card_message_timer = 1.0
            return

        # Rastgele bir renk seç
        import random as _rng
        target_color = _rng.choice(list(color_map.keys()))
        cells = color_map[target_color]

        # O renkteki tüm blokları temizle
        removed = 0
        for x, y in cells:
            self.board.grid[y][x] = (0, 0, 0)
            self.board.occupancy[y][x] = False
            self.board.texture_grid[y][x] = None
            self.board.gold[y][x] = False
            try:
                self.board.owners[y][x] = None
            except Exception:
                pass
            removed += 1

        # Gravity uygula - üstteki bloklar aşağı düşsün
        self.board.apply_gravity()

        # Gravity sonrası oluşan tam satırları temizle
        try:
            prev_score = int(getattr(self.board, 'score', 0))
            cleared = int(self.board.clear_lines(source='card'))
            if cleared > 0:
                delta = int(getattr(self.board, 'score', 0)) - prev_score
                self._post_external_line_clear(cleared, award_energy=True, score_delta=delta, source='card')
        except Exception:
            pass

        # Skor bonus
        try:
            bonus = removed * 25
            self.board.score += bonus
        except Exception:
            pass

        r, g, b = target_color
        self.card_message = f"Renk Temizleme: {removed} blok temizlendi! (RGB:{r},{g},{b})"
        self.card_message_timer = 1.5

        if self.sound_enabled:
            try:
                self.sound.play_sound('clear')
            except Exception:
                pass

    # === GELECEGI DEGISTIREN (FUTURE CHANGER) METODLARI ===
    def _open_piece_selection_popup(self) -> None:
        """Parça seçim popup'ını açar ve oyunu duraklatır."""
        self._piece_selection_active = True
        self._piece_selection_hover = -1
        self._piece_selection_rects = []
        # Hangi sıradaki parçayı değiştiriyoruz (0 = ilk, 1 = ikinci)
        self._future_changer_target_index = 0
        # Mouse'u görünür yap
        pygame.mouse.set_visible(True)
        try:
            self.card_message = "1. sıradaki parçayı seç!"
            self.card_message_timer = 10.0
        except Exception:
            pass

    def _close_piece_selection_popup(self) -> None:
        """Parça seçim popup'ını kapatır."""
        self._piece_selection_active = False
        self._piece_selection_hover = -1
        self._piece_selection_rects = []
        self._future_changer_target_index = 0

    def _select_future_piece(self, piece_name: str) -> None:
        """Seçilen parçayı sıradaki parçaların yerine koyar."""
        remaining = int(getattr(self, '_future_changer_remaining', 0) or 0)
        if remaining <= 0:
            self._close_piece_selection_popup()
            return
        
        # Hangi sıradaki parçayı değiştiriyoruz
        target_idx = getattr(self, '_future_changer_target_index', 0)
        
        # Yeni parça oluştur
        try:
            new_piece = self._create_named_piece(piece_name)
            self._apply_block_style(new_piece)
            
            # next_piece_queue'daki parçayı değiştir
            if hasattr(self, 'next_piece_queue') and len(self.next_piece_queue) > target_idx:
                self.next_piece_queue[target_idx] = new_piece
            elif hasattr(self, 'next_piece_queue'):
                # Kuyruk yeterli uzunlukta değilse ekle
                while len(self.next_piece_queue) <= target_idx:
                    self.next_piece_queue.append(self.spawn_new_piece())
                self.next_piece_queue[target_idx] = new_piece
        except Exception as e:
            print(f"[FutureChanger] Parça değiştirme hatası: {e}")
        
        self._future_changer_remaining = remaining - 1
        self._future_changer_target_index = target_idx + 1
        
        if self.sound_enabled:
            try:
                self.sound.play_sound('rotate')
            except Exception:
                pass
        
        # Hala seçim hakkı varsa popup'ı açık tut
        if self._future_changer_remaining > 0:
            try:
                self.card_message = f"{piece_name} seçildi! 2. sıradaki parçayı seç!"
                self.card_message_timer = 10.0
            except Exception:
                pass
        else:
            # Tüm seçimler yapıldı
            self._close_piece_selection_popup()
            try:
                self.card_message = f"{piece_name} seçildi! Sıradaki parçalar değiştirildi."
                self.card_message_timer = 2.0
            except Exception:
                pass

    def _draw_piece_selection_popup(self) -> None:
        """Parça seçim popup'ını çizer."""
        if not getattr(self, '_piece_selection_active', False):
            return
        
        # Mouse'u görünür yap (her frame'de)
        pygame.mouse.set_visible(True)
        
        # 7 standart Quadrix parçası
        piece_names = ['I', 'O', 'T', 'S', 'Z', 'J', 'L']
        
        # Popup boyutları (daha büyük)
        popup_width = 700
        popup_height = 220
        popup_x = (self.window_width - popup_width) // 2
        popup_y = (self.window_height - popup_height) // 2
        
        # Arka plan overlay - daha koyu
        overlay = pygame.Surface((self.window_width, self.window_height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 200))
        self.screen.blit(overlay, (0, 0))
        
        # Dış glow efekti
        glow_rect = pygame.Rect(popup_x - 15, popup_y - 15, popup_width + 30, popup_height + 30)
        glow_surf = pygame.Surface((glow_rect.width, glow_rect.height), pygame.SRCALPHA)
        pygame.draw.rect(glow_surf, (180, 100, 255, 40), glow_surf.get_rect(), border_radius=20)
        self.screen.blit(glow_surf, glow_rect.topleft)
        
        # Popup paneli
        popup_rect = pygame.Rect(popup_x, popup_y, popup_width, popup_height)
        retro_style.draw_glass_panel(
            self.screen,
            popup_rect,
            alpha=240,
            border_color=(180, 100, 255),
            glow=True,
        )
        
        # Üst dekoratif çizgi
        line_y = popup_y + 50
        pygame.draw.line(self.screen, (180, 100, 255, 150), (popup_x + 30, line_y), (popup_x + popup_width - 30, line_y), 2)
        
        # Başlık - hangi sıradaki parçayı seçtiğini göster
        target_idx = getattr(self, '_future_changer_target_index', 0)
        title_font = self.mystery_font_large
        title_text = f"{target_idx + 1}. Sıradaki Parçayı Seç"
        title_surf = title_font.render(title_text, True, (255, 255, 255))
        title_x = popup_x + (popup_width - title_surf.get_width()) // 2
        self.screen.blit(title_surf, (title_x, popup_y + 12))
        
        # Parça butonları (daha büyük)
        button_size = 80
        button_spacing = 18
        total_buttons_width = len(piece_names) * button_size + (len(piece_names) - 1) * button_spacing
        start_x = popup_x + (popup_width - total_buttons_width) // 2
        button_y = popup_y + 65
        
        mouse_pos = get_mouse_pos() if pygame.mouse.get_focused() else None
        self._piece_selection_rects = []
        self._piece_selection_hover = -1
        
        for idx, name in enumerate(piece_names):
            btn_x = start_x + idx * (button_size + button_spacing)
            btn_rect = pygame.Rect(btn_x, button_y, button_size, button_size)
            self._piece_selection_rects.append((btn_rect, name))
            
            # Hover kontrolü
            hovered = mouse_pos and btn_rect.collidepoint(mouse_pos)
            if hovered:
                self._piece_selection_hover = idx
            
            # Buton arka planı - yarı saydam koyu
            btn_bg = pygame.Surface((button_size, button_size), pygame.SRCALPHA)
            if hovered:
                pygame.draw.rect(btn_bg, (60, 40, 80, 200), btn_bg.get_rect(), border_radius=12)
            else:
                pygame.draw.rect(btn_bg, (30, 20, 50, 180), btn_bg.get_rect(), border_radius=12)
            self.screen.blit(btn_bg, btn_rect.topleft)
            
            # Hover'da glow efekti
            if hovered:
                glow_surf = pygame.Surface((button_size + 16, button_size + 16), pygame.SRCALPHA)
                pygame.draw.rect(glow_surf, (180, 100, 255, 80), glow_surf.get_rect(), border_radius=14)
                self.screen.blit(glow_surf, (btn_x - 8, button_y - 8))
                # İç border
                pygame.draw.rect(self.screen, (200, 150, 255), btn_rect, 2, border_radius=12)
            else:
                # Normal border
                pygame.draw.rect(self.screen, (80, 60, 100), btn_rect, 1, border_radius=12)
            
            # Parça şeklini oyun içi bloklarla çiz
            self._draw_game_piece_preview(btn_rect, name, hovered)
        
        # Alt dekoratif çizgi
        line_y2 = popup_y + popup_height - 40
        pygame.draw.line(self.screen, (180, 100, 255, 100), (popup_x + 30, line_y2), (popup_x + popup_width - 30, line_y2), 1)
        
        # İptal butonu - daha şık
        cancel_font = self.mystery_font_small
        cancel_text = "ESC: Iptal"
        cancel_surf = cancel_font.render(cancel_text, True, (150, 130, 170))
        cancel_x = popup_x + (popup_width - cancel_surf.get_width()) // 2
        self.screen.blit(cancel_surf, (cancel_x, popup_y + popup_height - 30))

    def _draw_game_piece_preview(self, rect: pygame.Rect, piece_name: str, hovered: bool = False) -> None:
        """Oyun içi blok stilini kullanarak parça önizlemesi çizer."""
        # Parça şekilleri (4x4 grid içinde)
        shapes = {
            'I': [(0, 1), (1, 1), (2, 1), (3, 1)],
            'O': [(1, 1), (2, 1), (1, 2), (2, 2)],
            'T': [(0, 1), (1, 1), (2, 1), (1, 2)],
            'S': [(1, 1), (2, 1), (0, 2), (1, 2)],
            'Z': [(0, 1), (1, 1), (1, 2), (2, 2)],
            'J': [(0, 1), (0, 2), (1, 2), (2, 2)],
            'L': [(2, 1), (0, 2), (1, 2), (2, 2)],
        }
        
        cells = shapes.get(piece_name, [])
        if not cells:
            return
        
        # Parça rengini tema'dan al (eğer varsa)
        color = None
        try:
            if hasattr(self, 'theme_manager') and self.theme_manager:
                colors = getattr(self.theme_manager, 'piece_colors', None)
                if colors and piece_name in colors:
                    color = colors[piece_name]
        except Exception:
            pass
        
        # Tema rengi yoksa varsayılan renkler
        if not color:
            default_colors = {
                'I': (0, 240, 240),
                'O': (240, 240, 0),
                'T': (160, 0, 240),
                'S': (0, 240, 0),
                'Z': (240, 0, 0),
                'J': (0, 0, 240),
                'L': (240, 160, 0),
            }
            color = default_colors.get(piece_name, (150, 150, 150))
        
        # Mini blok boyutu (daha büyük)
        mini_size = 16
        
        # Şekli buton içinde ortala
        min_x = min(c[0] for c in cells)
        max_x = max(c[0] for c in cells)
        min_y = min(c[1] for c in cells)
        max_y = max(c[1] for c in cells)
        shape_width = (max_x - min_x + 1) * mini_size
        shape_height = (max_y - min_y + 1) * mini_size
        
        offset_x = rect.x + (rect.width - shape_width) // 2 - min_x * mini_size
        offset_y = rect.y + (rect.height - shape_height) // 2 - min_y * mini_size
        
        # Hover'da parlaklık artır
        if hovered:
            color = tuple(min(255, int(c * 1.3)) for c in color[:3])
        
        # Blokları oyun içi stilde çiz
        for cx, cy in cells:
            bx = offset_x + cx * mini_size
            by = offset_y + cy * mini_size
            
            # Ana blok
            block_rect = pygame.Rect(bx, by, mini_size - 1, mini_size - 1)
            
            # Oyun içi blok stili: gradient efekti
            lighter = tuple(min(255, int(c * 1.4)) for c in color[:3])
            darker = tuple(max(0, int(c * 0.4)) for c in color[:3])
            
            # Ana renk
            pygame.draw.rect(self.screen, color, block_rect)
            
            # Üst ve sol kenar (açık) - daha kalın
            pygame.draw.line(self.screen, lighter, (bx, by), (bx + mini_size - 2, by), 2)
            pygame.draw.line(self.screen, lighter, (bx, by), (bx, by + mini_size - 2), 2)
            
            # Alt ve sağ kenar (koyu) - daha kalın
            pygame.draw.line(self.screen, darker, (bx + 1, by + mini_size - 2), (bx + mini_size - 2, by + mini_size - 2), 2)
            pygame.draw.line(self.screen, darker, (bx + mini_size - 2, by + 1), (bx + mini_size - 2, by + mini_size - 2), 2)
            
            # İç parlaklık (hover'da)
            if hovered:
                inner_glow = pygame.Surface((mini_size - 4, mini_size - 4), pygame.SRCALPHA)
                inner_glow.fill((*lighter, 60))
                self.screen.blit(inner_glow, (bx + 2, by + 2))

    def _handle_piece_selection_click(self, pos: tuple[int, int]) -> bool:
        """Parça seçim popup'ında tıklama işler. True dönerse event tüketildi."""
        if not getattr(self, '_piece_selection_active', False):
            return False
        
        for rect, name in getattr(self, '_piece_selection_rects', []):
            if rect.collidepoint(pos):
                self._select_future_piece(name)
                return True
        
        return False


class WideMode(Game):
    """15 sütun genişliğinde özel tahta kullanan mod."""

    def __init__(
        self,
        difficulty: str = "Normal",
        sound_enabled: bool = True,
        effects_enabled: bool = True,
        achievement_manager=None,
        theme_manager=None,
        screen=None,
        fullscreen: bool = False,
        settings_manager=None,
        user_manager=None,
        game_mode: str = "wide",
        score_manager=None,
    ) -> None:
        self.board_width = 15
        self.board_height = 23
        self.extra_piece_count = 0
        # BigSquare is intentionally rare in Wide Mode (hard piece).
        # Count spawns since the last BigSquare so we can throttle it.
        self._spawns_since_big_square = 0
        super().__init__(
            difficulty,
            sound_enabled,
            effects_enabled,
            achievement_manager,
            theme_manager,
            screen,
            fullscreen,
            settings_manager,
            user_manager,
            game_mode,
            score_manager=score_manager,
        )
        self.mode_name = "WIDE MODE"

        # Wide Mode'da üst köşe overlay'leri temiz kalsın.
        # (Genel FPS overlay'i Game tarafından çiziliyor; bu modda kapatıyoruz.)
        self.show_fps = False

        from background import BackgroundManager

        self.wide_background = BackgroundManager()
        if settings_manager:
            transparency = settings_manager.get("bg_transparency", 0.3)
            self.wide_background.set_transparency(transparency)
        self._load_wide_background()

        self.wide_font_large = retro_style.get_font(48, bold=False)
        self.wide_font_medium = retro_style.get_font(36, bold=False)

        print("🎮 WIDE MODE aktif. Tahta genişliği 15 sütuna çıktı.")

    def _load_wide_background(self) -> None:
        custom_bg = self.settings_manager.get("bg_wide") if self.settings_manager else None
        if custom_bg and os.path.exists(custom_bg) and self.wide_background.load_image(custom_bg):
            print(f"✨ Özel Wide Mode arka planı yüklendi: {os.path.basename(custom_bg)}")
            return

        default_path = os.path.join("backgrounds", "wide_background.png")
        if os.path.exists(default_path) and self.wide_background.load_image(default_path):
            print("✨ Wide Mode arka planı bulundu ve yüklendi.")
        else:
            print("⚠️ Wide Mode arka planı yok, varsayılan kullanılacak.")

    def restart(self):
        """Clear Wide mode-specific counters on restart."""
        super().restart()
        self.extra_piece_count = 0
        self._spawns_since_big_square = 0
        # Wide mode-specific reset can include background transparency adjustments if required

    def _get_base_piece_factories(self):
        factories = super()._get_base_piece_factories()
        # Keep BigSquare out of the regular pool; it is spawned separately at a low frequency.
        for name in EXTRA_SHAPE_NAMES:
            if name == 'BigSquare':
                continue
            factories.append(self._make_named_piece_factory(name))
        return factories

    def spawn_new_piece(self) -> Piece:
        # Spawn BigSquare roughly once per 15 pieces to keep difficulty reasonable.
        self._spawns_since_big_square += 1
        if self._spawns_since_big_square >= 15:
            piece = self._create_named_piece('BigSquare')
            identity = self._piece_identity(piece)
            # Üst üste 3 BigSquare (veya aynı kimlik) oluştuysa BigSquare'ı ertele.
            if self._would_exceed_max_consecutive(identity):
                piece = super().spawn_new_piece()
                # counter'ı resetleme: bir sonraki spawn'da tekrar denensin.
            else:
                self._apply_block_style(piece)
                self._note_piece_spawn(identity)
                self._spawns_since_big_square = 0
        else:
            piece = super().spawn_new_piece()
        if getattr(piece, "name", "") in EXTRA_SHAPE_NAMES:
            self.extra_piece_count += 1
            print(f"✨ Wide Mode ekstra parça #{self.extra_piece_count}: {piece.name}")
        return piece

    def apply_theme_to_pieces(self) -> None:
        # Use the shared theme + block style pipeline for every piece,
        # including EXTRA_SHAPE_NAMES, to keep visuals consistent across modes.
        super().apply_theme_to_pieces()

    def update(self, dt: float) -> None:
        super().update(dt)
        self._update_ghost()

    def move(self, dx: int) -> None:
        super().move(dx)
        self._update_ghost()

    def rotate(self) -> None:
        super().rotate()
        self._update_ghost()

    def hard_drop(self) -> None:
        super().hard_drop()
        if not self.game_over:
            self._update_ghost()

    def _update_ghost(self) -> None:
        if not self.current_piece:
            return
        self.ghost_piece = self.current_piece.copy()
        while self.board.is_valid_position(self.ghost_piece):
            self.ghost_piece.y += 1
        self.ghost_piece.y -= 1

    def draw_mode_overlay(self) -> None:
        # Wide Mode: üst köşelerde metin/etiket gösterme.
        return

    def draw_board_background(self, offset_x, offset_y, board_width, board_height):  # type: ignore[override]
        if self.wide_background.is_loaded():
            self.wide_background.draw(self.screen, (offset_x, offset_y, board_width, board_height))
        else:
            super().draw_board_background(offset_x, offset_y, board_width, board_height)

    def lock_piece(self) -> None:
        super().lock_piece()
        name = self.current_piece.name if hasattr(self.current_piece, "name") else "Klasik"
        print(f"🔒 Wide Mode parçası kilitlendi: {name}")



