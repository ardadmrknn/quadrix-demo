"""HiDPI diagnosis script - test which display flags enable Retina."""
import os
os.environ['SDL_VIDEO_HIGHDPI_DISABLED'] = '0'
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'

import pygame
pygame.init()

tests = [
    ("SCALED | RESIZABLE", pygame.SCALED | pygame.RESIZABLE),
    ("RESIZABLE (current)", pygame.RESIZABLE),
    ("NOFRAME", pygame.NOFRAME),
    ("NOFRAME | DOUBLEBUF", pygame.NOFRAME | pygame.DOUBLEBUF),
]

for name, flags in tests:
    try:
        pygame.display.quit()
        pygame.display.init()
        screen = pygame.display.set_mode((800, 600), flags)
        surf = screen.get_size()
        win = pygame.display.get_window_size()
        scale = surf[0] / win[0] if win[0] > 0 else 0
        hidpi = "YES" if surf != win else "no"
        print(f"[{hidpi:3s}] {name:30s}  surface={surf}  window={win}  scale={scale:.1f}x")
    except Exception as e:
        print(f"[ERR] {name:30s}  {e}")

print()
print(f"pygame {pygame.ver} (SDL {'.'.join(map(str, pygame.get_sdl_version()))})")
print(f"SDL_VIDEO_HIGHDPI_DISABLED = {os.environ.get('SDL_VIDEO_HIGHDPI_DISABLED')}")

# Check _sdl2
try:
    import pygame._sdl2
    print(f"pygame._sdl2 available: {True}")
except Exception:
    print(f"pygame._sdl2 available: {False}")

pygame.quit()
