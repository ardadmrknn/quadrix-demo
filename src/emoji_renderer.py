"""Merkezi emoji PNG yükleyici.

Unicode emoji karakterleri yerine Apple emoji PNG dosyalarını
kullanarak platformdan bağımsız, tutarlı emoji görüntüleme sağlar.

Kullanım:
    from emoji_renderer import emoji_surface, EMOJI_MAP

    # Emoji surface al (cache'li, boyutlandırılmış)
    surf = emoji_surface('🏆', 32)
    if surf:
        screen.blit(surf, (x, y))
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

import pygame


# Unicode emoji -> PNG dosya adı eşlemesi
EMOJI_MAP: dict[str, str] = {
    # --- Başarı sistemi ---
    '🎮': 'gamepad',
    '📏': 'direct_hit',   # ruler → fallback direct_hit
    '💎': 'gem',
    '🌟': 'glowing_star',
    '⭐': 'star',
    '🌠': 'shooting_star',
    '💫': 'sparkles',      # dizzy → sparkles
    '🧹': 'tornado',       # broom → tornado fallback
    '🌪️': 'tornado',
    '🌪': 'tornado',
    '🤖': 'robot',
    '⚡': 'collision',     # high voltage → collision fallback
    '🎯': 'direct_hit',
    '👑': 'crown',
    '🚀': 'rocket',
    '💨': 'wind',
    '✨': 'sparkles',
    '🏆': 'trophy',
    '🔥': 'fire',
    '💯': 'hundred',
    '👌': 'ok_hand',
    '⚔️': 'swords',
    '⚔': 'swords',
    '🛡️': 'shield',
    '🛡': 'shield',

    # --- Kart modu ---
    '✂️': 'scissors',
    '✂': 'scissors',
    '💥': 'collision',
    '👻': 'ghost',
    '💣': 'bomb',
    '🔄': 'arrows_cycle',
    '🔗': 'link',
    '🎒': 'backpack',
    '🌀': 'cyclone',
    '🎲': 'dice',

    # --- Oyun modları ---
    '🧭': 'compass',
    '⏱️': 'timer',
    '⏱': 'timer',
    '🧘': 'sparkles',      # meditation → sparkles
    '🧩': 'puzzle',
    '🃏': 'joker',
    '↔️': 'arrows_cycle',  # left-right → cycle arrows
    '❤️': 'heart',
    '❤': 'heart',
    '🌊': 'wave',
    '💀': 'skull',

    # --- UI ---
    '🎵': 'music_notes',
    '🖼️': 'palette',       # frame → palette fallback
    '🖼': 'palette',
    '🎨': 'palette',
    '🧱': 'puzzle',         # brick → puzzle fallback
    '📦': 'package',
    '📐': 'direct_hit',     # triangular ruler → direct_hit

    # --- Lokalizasyon metin emojileri ---
    '✅': 'check_mark',
    '❌': 'collision',      # cross mark → collision
    '⏳': 'hourglass',
    '🔢': 'dice',           # input numbers → dice
    '❄️': 'snowflake',
    '❄': 'snowflake',
    '⏸️': 'timer',          # pause → timer
    '⏸': 'timer',

    # --- Parti / kutlama ---
    '🎉': 'party',
    '🎊': 'confetti',
    '🎆': 'fireworks',

    '😀': 'star',
    '😎': 'crown',

    # --- Madalyalar ---
    '🥇': 'medal_gold',
    '🥈': 'medal_silver',
    '🥉': 'medal_bronze',
    '🏅': 'medal_sports',
    '🎖️': 'medal_military',
    '🎖': 'medal_military',

    # --- Ses ---
    '🔊': 'sound',
    '🔇': 'mute',

    # --- Diğer ---
    '⚠️': 'warning',
    '⚠': 'warning',
    '🎁': 'gift',
    '💙': 'blue_heart',
    '🪄': 'magic_wand',
    '⚙️': 'gear',
    '⚙': 'gear',
    '📖': 'book',
    '📕': 'book',
    '👤': 'person',
    '↘': 'resize_arrow',
    '↘️': 'resize_arrow',
}


def _get_base_dir() -> Path:
    """Proje kök dizinini döndür."""
    if getattr(sys, 'frozen', False):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent


# Yüklenen emoji surface cache'i: (dosya_adi, boyut) -> Surface
_cache: dict[tuple[str, int], pygame.Surface] = {}

# Başarısız yüklemeleri takip et (tekrar denemeyi önle)
_failed: set[str] = set()


def emoji_surface(
    emoji_char: str,
    size: int,
    *,
    fallback_font: Optional[pygame.font.Font] = None,
) -> Optional[pygame.Surface]:
    """Unicode emoji karakteri için PNG surface döndür.

    Args:
        emoji_char: Unicode emoji karakteri (örn. '🏆')
        size: Hedef kare boyut (piksel)
        fallback_font: PNG bulunamazsa bu fontle unicode render dene

    Returns:
        pygame.Surface veya None (bulunamazsa ve fallback yoksa)
    """
    # Boşlukları ve variation selector'ları temizle
    clean = emoji_char.strip()

    name = EMOJI_MAP.get(clean)
    if name is None:
        # Variation selector olmadan dene
        stripped = clean.replace('\ufe0f', '').replace('\u200d', '')
        name = EMOJI_MAP.get(stripped)

    if name and name not in _failed:
        key = (name, size)
        if key in _cache:
            return _cache[key]

        try:
            path = _get_base_dir() / 'assets' / 'emoji' / f'{name}.png'
            if path.exists():
                if not pygame.display.get_init():
                    img = pygame.image.load(str(path))
                else:
                    img = pygame.image.load(str(path)).convert_alpha()
                img = pygame.transform.smoothscale(img, (size, size))
                _cache[key] = img
                return img
            else:
                _failed.add(name)
        except Exception:
            _failed.add(name)

    # PNG bulunamadı — fallback font render
    if fallback_font:
        try:
            glyph = fallback_font.render(clean, True, (255, 255, 255))
            surf = pygame.Surface((size, size), pygame.SRCALPHA)
            rect = glyph.get_rect(center=(size // 2, size // 2))
            surf.blit(glyph, rect)
            return surf
        except Exception:
            pass

    return None


def clear_cache() -> None:
    """Emoji cache'ini temizle (tema/çözünürlük değişikliğinde)."""
    _cache.clear()
    _failed.clear()
