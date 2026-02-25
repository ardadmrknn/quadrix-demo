"""M1/M2 arka butonlarının pygame buton indekslerini tespit et."""
import pygame
import sys

pygame.init()
pygame.joystick.init()
screen = pygame.display.set_mode((500, 250))
pygame.display.set_caption("Buton Testi - M1/M2'ye bas!")

if pygame.joystick.get_count() == 0:
    print("Gamepad bulunamadi!")
    sys.exit(1)

js = pygame.joystick.Joystick(0)
js.init()
print(f"Controller: {js.get_name()}")
print(f"Toplam buton: {js.get_numbuttons()}")
print(f"Toplam eksen: {js.get_numaxes()}")
print(f"Toplam hat:   {js.get_numhats()}")
print()
print("Simdi M1 ve M2 butonlarina bas...")
print("(ESC veya pencereyi kapat ile cik)")
print()

font = pygame.font.SysFont(None, 28)
seen = []
running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        if event.type == pygame.JOYBUTTONDOWN:
            msg = f"BUTON: index={event.button}"
            print(f"  {msg}")
            seen.append(msg)
            if len(seen) > 8:
                seen = seen[-8:]
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            running = False

    screen.fill((30, 30, 40))
    title = font.render("M1 / M2 butonlarina bas!", True, (255, 255, 100))
    screen.blit(title, (20, 10))
    for i, s in enumerate(seen):
        surf = font.render(s, True, (200, 255, 200))
        screen.blit(surf, (20, 50 + i * 24))
    pygame.display.flip()
    pygame.time.wait(16)

pygame.quit()
