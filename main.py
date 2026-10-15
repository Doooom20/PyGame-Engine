import pygame_widgets
import pygame
from pygame_widgets.button import Button
from pygame_widgets.dropdown import Dropdown

# pygame setup
pygame.init()
screen = pygame.display.set_mode((1280, 720), pygame.RESIZABLE)
clock = pygame.time.Clock()
running = True
my_font = pygame.font.SysFont('Arial', 15) 

playerPos = pygame.Vector2(screen.get_width(), screen.get_height())

dt = 1
fps = 0

fpsDropdown = Dropdown(
    screen, 120, 10, 100, 50, name="FPS",
    choices=['20', '30', '60'],
    borderRadius=3, colour=pygame.Color('green'), values=[20, 30, 60], direction='down', textHAlign='left'
)

while running:
    # poll for events
    # pygame.QUIT event means the user clicked X to close your window
    events = pygame.event.get()
    for event in events:
        if event.type == pygame.QUIT:
            running = False

    # fill the screen with a color to wipe away anything from last frame
    screen.fill("black")

    pygame_widgets.update(events)

    keys = pygame.key.get_pressed()

    pygame.display.flip()

    dt = clock.tick(fpsDropdown) / 1000
    print("Running At: " + str(fpsDropdown))

pygame.quit()