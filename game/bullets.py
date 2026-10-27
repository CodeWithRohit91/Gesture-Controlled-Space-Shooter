"""
Bullet and Projectile System for GestureStrike.
Renders procedural neon laser bolts, plasma orbs, boss energy beams,
and screen-clearing EMP smart bombs.
"""

import math
import pygame
from typing import Tuple, List, Optional
from config import (
    WINDOW_WIDTH,
    WINDOW_HEIGHT,
    COLOR_PRIMARY_CYAN,
    COLOR_PRIMARY_BLUE,
    COLOR_ACCENT_MAGENTA,
    COLOR_ALERT_RED,
    COLOR_WHITE,
    COLOR_NEON_YELLOW
)


class Bullet:
    """Base class for all projectile types."""

    def __init__(
        self,
        x: float,
        y: float,
        vx: float,
        vy: float,
        damage: int = 25,
        radius: float = 4.0,
        color: Tuple[int, int, int] = COLOR_PRIMARY_CYAN
    ):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.damage = damage
        self.radius = radius
        self.color = color
        self.alive = True

    @property
    def rect(self) -> pygame.Rect:
        r = int(self.radius)
        return pygame.Rect(int(self.x) - r, int(self.y) - r, r * 2, r * 2)

    def update(self, dt: float) -> bool:
        """Updates bullet movement. Returns False if out of screen bounds."""
        self.x += self.vx * (dt * 60.0)
        self.y += self.vy * (dt * 60.0)

        # Check bounds with margin
        margin = 30
        if (self.x < -margin or self.x > WINDOW_WIDTH + margin or
            self.y < -margin or self.y > WINDOW_HEIGHT + margin):
            self.alive = False
            return False
        return True

    def draw(self, surface: pygame.Surface):
        """Draws glowing procedural projectile."""
        r = int(self.radius)
        glow_size = r * 3 + 2
        glow_surf = pygame.Surface((glow_size * 2, glow_size * 2), pygame.SRCALPHA)
        center = (glow_size, glow_size)

        # Soft halo
        pygame.draw.circle(glow_surf, (*self.color, 70), center, glow_size)
        # Inner plasma
        pygame.draw.circle(glow_surf, (*self.color, 200), center, r + 2)
        # Hot core
        pygame.draw.circle(glow_surf, (255, 255, 255, 255), center, max(1, r - 1))

        surface.blit(glow_surf, (int(self.x) - glow_size, int(self.y) - glow_size), special_flags=pygame.BLEND_ADD)


class PlayerBullet(Bullet):
    """Sleek vertical/angled plasma bolt fired from player's cannons."""

    def __init__(
        self,
        x: float,
        y: float,
        vx: float = 0.0,
        vy: float = -18.0,
        damage: int = 30,
        color: Tuple[int, int, int] = COLOR_PRIMARY_CYAN
    ):
        super().__init__(x, y, vx, vy, damage=damage, radius=4.5, color=color)
        self.length = 14.0

    def draw(self, surface: pygame.Surface):
        """Draws aerodynamic stretched plasma bolt with neon bloom."""
        angle = math.atan2(self.vy, self.vx)
        p1 = (self.x, self.y)
        p2 = (self.x - math.cos(angle) * self.length, self.y - math.sin(angle) * self.length)

        # Bloom glow lines
        for width, alpha in [(8, 50), (4, 140), (2, 255)]:
            col = (255, 255, 255) if width == 2 else self.color
            pygame.draw.line(surface, col, p1, p2, width)


class EnemyBullet(Bullet):
    """Hostile plasma orb fired by enemy drones and gunners."""

    def __init__(
        self,
        x: float,
        y: float,
        vx: float,
        vy: float,
        damage: int = 1,
        color: Tuple[int, int, int] = COLOR_ALERT_RED
    ):
        super().__init__(x, y, vx, vy, damage=damage, radius=5.0, color=color)
        self.pulse_phase = 0.0

    def update(self, dt: float) -> bool:
        self.pulse_phase += dt * 12.0
        return super().update(dt)

    def draw(self, surface: pygame.Surface):
        pulse = 1.0 + 0.2 * math.sin(self.pulse_phase)
        r = int(self.radius * pulse)
        glow_size = r * 3 + 2
        glow_surf = pygame.Surface((glow_size * 2, glow_size * 2), pygame.SRCALPHA)
        center = (glow_size, glow_size)

        pygame.draw.circle(glow_surf, (*self.color, 80), center, glow_size)
        pygame.draw.circle(glow_surf, (*self.color, 210), center, r + 1)
        pygame.draw.circle(glow_surf, (255, 255, 200, 255), center, max(1, r - 2))

        surface.blit(glow_surf, (int(self.x) - glow_size, int(self.y) - glow_size), special_flags=pygame.BLEND_ADD)


class BossLaserBeam:
    """Broad vertical laser beam charged and fired during boss rage phases."""

    def __init__(
        self,
        x: float,
        y: float,
        width: float = 38.0,
        charge_time: float = 0.8,
        active_time: float = 1.2
    ):
        self.x = x
        self.y = y
        self.width = width
        self.charge_time = charge_time
        self.active_time = active_time
        self.timer = 0.0
        self.alive = True
        self.is_firing = False

    @property
    def rect(self) -> pygame.Rect:
        if not self.is_firing:
            return pygame.Rect(0, 0, 0, 0)
        w = int(self.width)
        return pygame.Rect(int(self.x - w / 2), int(self.y), w, WINDOW_HEIGHT)

    def update(self, dt: float) -> bool:
        self.timer += dt
        if self.timer < self.charge_time:
            self.is_firing = False
        elif self.timer < self.charge_time + self.active_time:
            self.is_firing = True
        else:
            self.alive = False
            return False
        return True

    def draw(self, surface: pygame.Surface):
        if not self.alive:
            return

        w = int(self.width)
        if not self.is_firing:
            # Draw warning indicator laser line
            charge_progress = self.timer / self.charge_time
            alpha = int(140 + 115 * math.sin(self.timer * 35.0))
            line_surf = pygame.Surface((4, WINDOW_HEIGHT), pygame.SRCALPHA)
            line_surf.fill((*COLOR_ALERT_RED, alpha))
            surface.blit(line_surf, (int(self.x - 2), int(self.y)))
        else:
            # Active full-power destructive energy beam
            beam_surf = pygame.Surface((w * 2, WINDOW_HEIGHT), pygame.SRCALPHA)
            center_x = w

            # Outer glow
            pygame.draw.rect(beam_surf, (*COLOR_ACCENT_MAGENTA, 90), (center_x - w, 0, w * 2, WINDOW_HEIGHT))
            # Mid core
            pygame.draw.rect(beam_surf, (*COLOR_ALERT_RED, 200), (center_x - w // 2, 0, w, WINDOW_HEIGHT))
            # White-hot plasma core
            pygame.draw.rect(beam_surf, (255, 255, 255, 255), (center_x - w // 4, 0, w // 2, WINDOW_HEIGHT))

            surface.blit(beam_surf, (int(self.x - w), int(self.y)), special_flags=pygame.BLEND_ADD)


class SmartBombWave:
    """Expanding EMP blast that clears bullets and damages all enemies."""

    def __init__(self, x: float, y: float, max_radius: float = 900.0, speed: float = 950.0):
        self.x = x
        self.y = y
        self.radius = 10.0
        self.max_radius = max_radius
        self.speed = speed
        self.alive = True

    def update(self, dt: float) -> bool:
        self.radius += self.speed * dt
        if self.radius >= self.max_radius:
            self.alive = False
            return False
        return True

    def draw(self, surface: pygame.Surface):
        if not self.alive:
            return
        progress = self.radius / self.max_radius
        alpha = int(220 * (1.0 - progress))
        if alpha <= 0:
            return

        r = int(self.radius)
        dim = r * 2 + 8
        s = pygame.Surface((dim, dim), pygame.SRCALPHA)
        center = (r + 4, r + 4)

        # Concentric glowing energy waves
        pygame.draw.circle(s, (*COLOR_PRIMARY_CYAN, alpha), center, r, width=6)
        if r > 30:
            pygame.draw.circle(s, (*COLOR_WHITE, alpha // 2), center, r - 15, width=3)
        surface.blit(s, (int(self.x) - r - 4, int(self.y) - r - 4), special_flags=pygame.BLEND_ADD)
