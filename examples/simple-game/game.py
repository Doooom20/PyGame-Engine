
import pygame
import random
import sys

# Initialize Pygame
pygame.init()

# Window settings
WIDTH, HEIGHT = 800, 500
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Pong")

# Colors
BLACK = (15, 15, 20)
WHITE = (240, 240, 240)

# Game settings
PADDLE_WIDTH = 12
PADDLE_HEIGHT = 90
BALL_SIZE = 14
PADDLE_SPEED = 6
BALL_SPEED = 5

# Paddles
left_paddle = pygame.Rect(
    30, HEIGHT // 2 - PADDLE_HEIGHT // 2,
    PADDLE_WIDTH, PADDLE_HEIGHT
)
right_paddle = pygame.Rect(
    WIDTH - 30 - PADDLE_WIDTH,
    HEIGHT // 2 - PADDLE_HEIGHT // 2,
    PADDLE_WIDTH, PADDLE_HEIGHT
)

# Ball
ball = pygame.Rect(
    WIDTH // 2 - BALL_SIZE // 2,
    HEIGHT // 2 - BALL_SIZE // 2,
    BALL_SIZE, BALL_SIZE
)
ball_dx = random.choice([-BALL_SPEED, BALL_SPEED])
ball_dy = random.choice([-3, 3])

# Scores and font
left_score = 0
right_score = 0
font = pygame.font.Font(None, 64)
small_font = pygame.font.Font(None, 28)

# Clock
clock = pygame.time.Clock()


def reset_ball(direction):
    global ball_dx, ball_dy

    ball.center = (WIDTH // 2, HEIGHT // 2)
    ball_dx = BALL_SPEED * direction
    ball_dy = random.choice([-3, -2, 2, 3])


def draw():
    screen.fill(BLACK)

    # Center line
    for y in range(0, HEIGHT, 30):
        pygame.draw.rect(
            screen, WHITE,
            (WIDTH // 2 - 2, y, 4, 15)
        )

    # Paddles and ball
    pygame.draw.rect(screen, WHITE, left_paddle)
    pygame.draw.rect(screen, WHITE, right_paddle)
    pygame.draw.ellipse(screen, WHITE, ball)

    # Scores
    left_text = font.render(str(left_score), True, WHITE)
    right_text = font.render(str(right_score), True, WHITE)

    screen.blit(left_text, (WIDTH // 4, 30))
    screen.blit(right_text, (3 * WIDTH // 4, 30))

    # Controls
    controls = small_font.render(
        "Player 1: W/S     Player 2: UP/DOWN     ESC: Quit",
        True, WHITE
    )
    screen.blit(
        controls,
        (WIDTH // 2 - controls.get_width() // 2, HEIGHT - 30)
    )

    pygame.display.flip()


# Main game loop
running = True

while running:
    clock.tick(60)

    # Handle events
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                running = False

    keys = pygame.key.get_pressed()

    # Move left paddle
    if keys[pygame.K_w]:
        left_paddle.y -= PADDLE_SPEED
    if keys[pygame.K_s]:
        left_paddle.y += PADDLE_SPEED

    # Move right paddle
    if keys[pygame.K_UP]:
        right_paddle.y -= PADDLE_SPEED
    if keys[pygame.K_DOWN]:
        right_paddle.y += PADDLE_SPEED

    # Keep paddles inside the screen
    left_paddle.clamp_ip(screen.get_rect())
    right_paddle.clamp_ip(screen.get_rect())

    # Move ball
    ball.x += ball_dx
    ball.y += ball_dy

    # Bounce off top and bottom
    if ball.top <= 0 or ball.bottom >= HEIGHT:
        ball_dy *= -1

    # Bounce off paddles
    if ball.colliderect(left_paddle) and ball_dx < 0:
        ball.left = left_paddle.right
        ball_dx = abs(ball_dx) + 0.3

    if ball.colliderect(right_paddle) and ball_dx > 0:
        ball.right = right_paddle.left
        ball_dx = -abs(ball_dx) - 0.3

    # Score when ball leaves the screen
    if ball.right < 0:
        right_score += 1
        reset_ball(1)

    elif ball.left > WIDTH:
        left_score += 1
        reset_ball(-1)

    # Draw everything
    draw()

pygame.quit()
sys.exit()
