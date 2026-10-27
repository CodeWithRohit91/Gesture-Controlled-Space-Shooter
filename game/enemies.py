"""
Enemy Squadron System for GestureStrike.
Features 4 distinct tactical enemy classes:
1. Scout: Fast vertical dive bomber.
2. Viper: Sinusoidal zigzag flanker.
3. Interceptor: Player-tracking homing pursuit craft.
4. Gunner: Heavy armored drone that aims and fires plasma orbs.
All rendered with procedural neon sci-fi vector graphics.
"""

import math
import random
import pygame
from typing import List, Tuple, Optional
from config import (
    WINDOW_WIDTH,
    WINDOW_HEIGHT,
    COLOR_NEON_ORANGE,
    COLOR_ACCENT_MAGENTA,
    COLOR_NEON_YELLOW,
    COLOR_ALERT_RED,
    COLOR_WHITE
)
from game.bullets import EnemyBullet
from game.powerups import PowerUp, PowerUpType
from game.particles import ParticleManager


class EnemyType:
    SCOUT = "SCOUT"
    VIPER = "VIPER"
    INTERCEPTOR = "INTERCEPTOR"
    GUNNER = "GUNNER"


class Enemy:
    """Base class for all enemy starships."""

    def __init__(
        self,
        x: float,
        y: float,
        enemy_type: str,
        hp: int,
        score_value: int,
        color: Tuple[int, int, int]
    ):
        self.x = x
        self.y = y
        self.enemy_type = enemy_type
        self.max_hp = hp
        self.hp = hp
        self.score_value = score_value
        self.color = color
        self.alive = True
        self.width = 38
        self.height = 38
        self.phase = random.uniform(0, 2 * math.pi)
        self.hit_flash_timer = 0.0

    @property
    def rect(self) -> pygame.Rect:
        w = int(self.width * 0.8)
        h = int(self.height * 0.8)
        return pygame.Rect(int(self.x - w / 2), int(self.y - h / 2), w, h)

    def take_damage(self, amount: int) -> bool:
        """Applies damage. Returns True if destroyed."""
        self.hp -= amount
        self.hit_flash_timer = 0.08
        if self.hp <= 0:
            self.alive = False
            return True
        return False

    def roll_powerup(self) -> Optional[PowerUp]:
        """Rolls random chance to drop a power-up upon defeat."""
        # 18% base chance to drop a power-up
        if random.random() < 0.18:
            ptype = random.choices(
                [PowerUpType.RAPID_FIRE, PowerUpType.TRIPLE_SHOT, PowerUpType.EXTRA_LIFE, PowerUpType.SCORE_MULTIPLIER],
                weights=[30, 25, 20, 25]
            )[0]
            return PowerUp(self.x, self.y, ptype)
        return None

    def update(self, dt: float, player_x: float, player_y: float) -> List[EnemyBullet]:
        """Updates movement and AI. Returns fired bullets."""
        if self.hit_flash_timer > 0:
            self.hit_flash_timer -= dt
        return []

    def draw(self, surface: pygame.Surface):
        """Draws procedural hull geometry."""
        pass


class ScoutEnemy(Enemy):
    """Fast dive-bomber that streaks straight down with rocket thrust."""

    def __init__(self, x: float, y: float, speed_scale: float = 1.0):
        super().__init__(x, y, EnemyType.SCOUT, hp=30, score_value=100, color=COLOR_NEON_ORANGE)
        self.vy = random.uniform(5.0, 7.2) * speed_scale
        self.width = 32
        self.height = 36

    def update(self, dt: float, player_x: float, player_y: float) -> List[EnemyBullet]:
        super().update(dt, player_x, player_y)
        self.y += self.vy * (dt * 60.0)
        if self.y > WINDOW_HEIGHT + 50:
            self.alive = False
        return []

    def draw(self, surface: pygame.Surface):
        x = int(self.x)
        y = int(self.y)
        col = COLOR_WHITE if self.hit_flash_timer > 0 else self.color

        pts = [
            (x, y + 18),        # Forward nose
            (x - 16, y - 14),   # Left wing
            (x - 6, y - 8),     # Left thruster
            (x + 6, y - 8),     # Right thruster
            (x + 16, y - 14)    # Right wing
        ]
        pygame.draw.polygon(surface, (30, 18, 15), pts)
        pygame.draw.polygon(surface, col, pts, width=2)
        # Eye / sensor
        pygame.draw.circle(surface, COLOR_WHITE, (x, y + 4), 2)


class ViperEnemy(Enemy):
    """S-curving stealth predator that sways sinusoidally across screen."""

    def __init__(self, x: float, y: float, speed_scale: float = 1.0):
        super().__init__(x, y, EnemyType.VIPER, hp=60, score_value=200, color=COLOR_ACCENT_MAGENTA)
        self.base_x = x
        self.amplitude = random.uniform(90.0, 160.0)
        self.frequency = random.uniform(1.8, 2.6)
        self.vy = random.uniform(3.0, 4.2) * speed_scale
        self.width = 42
        self.height = 38

    def update(self, dt: float, player_x: float, player_y: float) -> List[EnemyBullet]:
        super().update(dt, player_x, player_y)
        self.phase += dt * self.frequency
        self.x = self.base_x + math.sin(self.phase) * self.amplitude
        self.x = max(30, min(WINDOW_WIDTH - 30, self.x))
        self.y += self.vy * (dt * 60.0)

        if self.y > WINDOW_HEIGHT + 50:
            self.alive = False
        return []

    def draw(self, surface: pygame.Surface):
        x = int(self.x)
        y = int(self.y)
        col = COLOR_WHITE if self.hit_flash_timer > 0 else self.color

        pts = [
            (x, y + 16),
            (x - 20, y - 4),
            (x - 14, y - 16),
            (x, y - 8),
            (x + 14, y - 16),
            (x + 20, y - 4)
        ]
        pygame.draw.polygon(surface, (32, 12, 30), pts)
        pygame.draw.polygon(surface, col, pts, width=2)
        pygame.draw.line(surface, col, (x - 10, y), (x + 10, y), 2)


class InterceptorEnemy(Enemy):
    """Heavy assault drone that tracks the player's horizontal position."""

    def __init__(self, x: float, y: float, speed_scale: float = 1.0):
        super().__init__(x, y, EnemyType.INTERCEPTOR, hp=90, score_value=300, color=COLOR_NEON_YELLOW)
        self.vy = random.uniform(2.6, 3.6) * speed_scale
        self.vx = 0.0
        self.turn_speed = 4.5 * speed_scale
        self.width = 46
        self.height = 44

    def update(self, dt: float, player_x: float, player_y: float) -> List[EnemyBullet]:
        super().update(dt, player_x, player_y)
        # Steer toward player X
        diff_x = player_x - self.x
        if abs(diff_x) > 6:
            self.vx += math.copysign(self.turn_speed, diff_x) * dt * 15.0
            self.vx = max(-5.0, min(5.0, self.vx))
        else:
            self.vx *= 0.9

        self.x += self.vx * (dt * 60.0)
        self.y += self.vy * (dt * 60.0)
        self.x = max(30, min(WINDOW_WIDTH - 30, self.x))

        if self.y > WINDOW_HEIGHT + 50:
            self.alive = False
        return []

    def draw(self, surface: pygame.Surface):
        x = int(self.x)
        y = int(self.y)
        col = COLOR_WHITE if self.hit_flash_timer > 0 else self.color

        pts = [
            (x, y + 20),
            (x - 22, y + 4),
            (x - 18, y - 18),
            (x - 6, y - 12),
            (x + 6, y - 12),
            (x + 18, y - 18),
            (x + 22, y + 4)
        ]
        pygame.draw.polygon(surface, (30, 28, 12), pts)
        pygame.draw.polygon(surface, col, pts, width=2)
        pygame.draw.circle(surface, col, (x, y - 2), 4)


class GunnerEnemy(Enemy):
    """Armored platform that enters the field, hovers laterally, and shoots plasma bolts."""

    def __init__(self, x: float, y: float, speed_scale: float = 1.0):
        super().__init__(x, y, EnemyType.GUNNER, hp=130, score_value=450, color=COLOR_ALERT_RED)
        self.target_y = random.uniform(100.0, 240.0)
        self.vx = random.choice([-2.4, 2.4]) * speed_scale
        self.fire_cooldown = random.uniform(1.4, 2.2)
        self.width = 54
        self.height = 42

    def update(self, dt: float, player_x: float, player_y: float) -> List[EnemyBullet]:
        super().update(dt, player_x, player_y)
        bullets = []

        # Descend to holding altitude
        if self.y < self.target_y:
            self.y += 2.8 * (dt * 60.0)
        else:
            # Patrol horizontally
            self.x += self.vx * (dt * 60.0)
            if self.x < 60:
                self.x = 60
                self.vx = abs(self.vx)
            elif self.x > WINDOW_WIDTH - 60:
                self.x = WINDOW_WIDTH - 60
                self.vx = -abs(self.vx)

        # Shooting AI
        self.fire_cooldown -= dt
        if self.fire_cooldown <= 0:
            self.fire_cooldown = random.uniform(1.6, 2.4)
            # Aim bullet toward player
            angle = math.atan2(player_y - self.y, player_x - self.x)
            b_speed = 6.5
            b_vx = math.cos(angle) * b_speed
            b_vy = math.sin(angle) * b_speed
            bullets.append(EnemyBullet(self.x, self.y + 18, vx=b_vx, vy=b_vy))

        return bullets

    def draw(self, surface: pygame.Surface):
        x = int(self.x)
        y = int(self.y)
        col = COLOR_WHITE if self.hit_flash_timer > 0 else self.color

        # Hexagonal armored fortress
        pts = [
            (x - 26, y - 8),
            (x - 14, y + 18),
            (x + 14, y + 18),
            (x + 26, y - 8),
            (x + 14, y - 18),
            (x - 14, y - 18)
        ]
        pygame.draw.polygon(surface, (36, 14, 18), pts)
        pygame.draw.polygon(surface, col, pts, width=2)
        # Heavy cannon barrel
        pygame.draw.rect(surface, col, (x - 4, y + 12, 8, 12))
        # Ominous glowing eye
        pygame.draw.circle(surface, (255, 100, 100), (x, y - 2), 5)
