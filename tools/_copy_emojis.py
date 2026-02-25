#!/usr/bin/env python3
"""Apple emoji PNG dosyalarini assets/ui/emoji/ klasorune kopyalar."""
import os, shutil

BASE = os.path.join(os.path.dirname(__file__), '..', 'apple_emojis')
DEST = os.path.join(os.path.dirname(__file__), '..', 'assets', 'ui', 'emoji')
os.makedirs(DEST, exist_ok=True)

# Unicode emoji -> apple_emojis dosya adi -> hedef isim
EMOJI_MAP = {
    # Basari sistemi + UI emojileri
    'video-oyun.png': 'gamepad.png',
    'trophy.png': 'trophy.png',
    'elmas.png': 'gem.png',
    'parlayan-y\u0131ld\u0131z.png': 'glowing_star.png',
    'y\u0131ld\u0131z.png': 'star.png',
    'akan-y\u0131ld\u0131z.png': 'shooting_star.png',
    'par\u0131lt\u0131lar.png': 'sparkles.png',
    'ate\u015f.png': 'fire.png',
    'roket.png': 'rocket.png',
    'crown.png': 'crown.png',
    'dart.png': 'direct_hit.png',
    'robot-y\u00fcz.png': 'robot.png',
    'hundred-points-symbol.png': 'hundred.png',
    'bomb.png': 'bomb.png',
    'ghost.png': 'ghost.png',
    'skull.png': 'skull.png',
    'party-popper.png': 'party.png',
    'confetti-top.png': 'confetti.png',
    '\u00e7arp\u0131\u015fma-symbol.png': 'collision.png',
    'oyun-die.png': 'dice.png',
    'joker.png': 'joker.png',
    'compass.png': 'compass.png',
    'kas\u0131rga.png': 'cyclone.png',
    'dalga.png': 'wave.png',
    'k\u0131l\u0131\u00e7lar-varyasyon-2694-fe0f.png': 'swords.png',
    'kalkan-varyasyon-1f6e1-fe0f.png': 'shield.png',
    'siyah-makas.png': 'scissors.png',
    'jigsaw-puzzle-piece.png': 'puzzle.png',
    'artist-palette.png': 'palette.png',
    'package.png': 'package.png',
    'school-satchel.png': 'backpack.png',
    'k\u0131rm\u0131z\u0131-kalp-varyasyon-2764-fe0f.png': 'heart.png',
    'mavi-kalp.png': 'blue_heart.png',
    'ok-el-i\u015faret.png': 'ok_hand.png',
    'magic-wand.png': 'magic_wand.png',
    'sparkle.png': 'sparkle.png',
    'hourglass-ile-flowing-sand.png': 'hourglass.png',
    'timer-clock.png': 'timer.png',
    'kar-tanesi-varyasyon-2744-fe0f.png': 'snowflake.png',
    'tornado-varyasyon-1f32a-fe0f.png': 'tornado.png',
    'saat-y\u00f6n\u00fc-rightwards-and-leftwards-a\u00e7\u0131k-daire-oklar.png': 'arrows_cycle.png',
    'ba\u011flant\u0131-symbol.png': 'link.png',
    'beyaz-heavy-check-i\u015faret.png': 'check_mark.png',
    'heavy-check-i\u015faret.png': 'check_heavy.png',
    'multiple-musical-notes.png': 'music_notes.png',
    'musical-note.png': 'music_note.png',
    'ilk-place-medal.png': 'medal_gold.png',
    'second-place-medal.png': 'medal_silver.png',
    'third-place-medal.png': 'medal_bronze.png',
    'sports-medal.png': 'medal_sports.png',
    'military-medal.png': 'medal_military.png',
    'warning-i\u015faret.png': 'warning.png',
    'speaker.png': 'speaker.png',
    'speaker-ile-cancellation-stroke.png': 'mute.png',
    'speaker-ile-three-sound-waves.png': 'speaker_loud.png',
    'wrapped-present.png': 'gift.png',
    'fireworks.png': 'fireworks.png',
    # Ek emojiler
    'r\u00fczgar-varyasyon-1f32c-fe0f.png': 'wind.png',
    'chains.png': 'chains.png',
}

copied = 0
missing = 0
for src_name, dst_name in sorted(EMOJI_MAP.items()):
    src = os.path.join(BASE, src_name)
    dst = os.path.join(DEST, dst_name)
    if os.path.exists(src):
        shutil.copy2(src, dst)
        copied += 1
    else:
        print(f"  BULUNAMADI: {src_name}")
        missing += 1

print(f"\nSonuc: {copied} kopyalandi, {missing} bulunamadi")
print(f"Hedef klasor: {os.path.abspath(DEST)}")
print(f"Dosyalar:")
for f in sorted(os.listdir(DEST)):
    size = os.path.getsize(os.path.join(DEST, f))
    print(f"  {f} ({size//1024}KB)")
