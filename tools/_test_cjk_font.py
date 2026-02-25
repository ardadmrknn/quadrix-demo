#!/usr/bin/env python3
"""CJK font rendering test - kare sorunu fix dogrulama."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'

import pygame
pygame.init()
screen = pygame.display.set_mode((100, 100))

from ui_language_profile import get_font_for_language, _resolve_font_path, _PROFILE_BY_LANG

print("=== CJK Font Test ===\n")

# Test 1: CJK fontlari dogru yukleniyor mu?
cjk_names = {'ja': '\u65e5\u672c\u8a9e', 'zh': '\u4e2d\u6587', 'ko': '\ud55c\uad6d\uc5b4'}
for lang in ['ja', 'zh', 'ko']:
    font = get_font_for_language(lang, 20)
    if font:
        name = cjk_names[lang]
        surf = font.render(name, True, (255, 255, 255))
        print(f"  {lang}: PASS - font yuklendi, '{name}' render boyut={surf.get_size()}")
    else:
        path = _resolve_font_path(_PROFILE_BY_LANG[lang]['font_path'])
        exists = os.path.exists(path) if path else False
        print(f"  {lang}: FAIL - font yuklenemedi! path={path} exists={exists}")

# Test 2: Latin diller None donmeli
print()
for lang in ['tr', 'en', 'de', 'fr', 'es', 'it', 'pt']:
    font = get_font_for_language(lang, 20)
    status = "PASS (None)" if font is None else "FAIL (font dondu)"
    print(f"  {lang}: {status}")

# Test 3: Cache calisiyor mu?
print()
f1 = get_font_for_language('ja', 20)
f2 = get_font_for_language('ja', 20)
print(f"  Cache: {'PASS' if f1 is f2 else 'FAIL'} (ayni nesne: {f1 is f2})")

# Test 4: Farkli boyutlar
f3 = get_font_for_language('ja', 24)
print(f"  Farkli boyut: {'PASS' if f3 is not f1 and f3 is not None else 'FAIL'}")

print("\n=== Test Tamamlandi ===")
pygame.quit()
