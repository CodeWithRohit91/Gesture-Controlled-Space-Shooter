"""
Power-Up System for GestureStrike.
Features Rapid Fire, Triple Shot, Extra Life, and Score Multipliers.
Rendered entirely with procedural glowing vector badges.
"""

import math
import random
import pygame
from typing import Tuple
from config import (
    WINDOW_HEIGHT,
    COLOR_PRIMARY_CYAN,
    COLOR_NEON_GREEN,
    COLOR_NEON_YELLOW,
    COLOR_ACCENT_MAGENTA,
    COLOR_WHITE
)


class PowerUpType:
    RAPID_FIRE = "RAPID_FIRE"
    TRIPLE_SHOT = "TRIPLE_SHOT"
    EXTRA_LIFE = "EXTRA_LIFE"
    SCORE_MULTIPLIER = "SCORE_MULTIPLIER"


class PowerUp:
    """Floating collectible dropped by defeated enemies."""

    CONFIGS = {
        PowerUpType.RAPID_FIRE: {
            "name": "RAPID FIRE",
            "color": COLOR_PRIMARY_CYAN,
            "symbol": "R",
            "duration": 10.0
        },
        PowerUpType.TRIPLE_SHOT: {
            "name": "TRIPLE SHOT",
            "color": COLOR_ACCENT_MAGENTA,
            "symbol": "3X",
            "duration": 12.0
        },
        PowerUpType.EXTRA_LIFE: {
            "name": "EXTRA LIFE",
            "color": COLOR_NEON_GREEN,
            "symbol": "+1",
            "duration": 0.0  # Instant restore
        },
        PowerUpType.SCORE_MULTIPLIER: {
            "name": "2X SCORE",
            "color": COLOR_NEON_YELLOW,
            "symbol": "2X",
            "duration": 15.0
        }
    }

    def __init__(self, x: float, y: float, ptype: str):
        self.x = x
        self.y = y
        self.ptype = ptype
        self.config = self.CONFIGS.get(ptype, self.CONFIGS[PowerUpType.RAPID_FIRE])
        self.color = self.config["color"]
        self.symbol = self.config["symbol"]
        self.radius = 16.0
        self.vy = 2.2
        self.phase = random.uniform(0, 2 * math.pi)
        self.alive = True

    @property
    def rect(self) -> pygame.Rect:
        r = int(self.radius)
        return pygame.Rect(int(self.x) - r, int(self.y) - r, r * 2, r * 2)

    def update(self, dt: float) -> bool:
        """Drifts downward with subtle horizontal swaying."""
        self.phase += dt * 3.5
        self.y += self.vy * (dt * 60.0)
        self.x += math.sin(self.phase) * 1.2

        if self.y > WINDOW_HEIGHT + 40:
            self.alive = False
            return False
        return True

    def draw(self, surface: pygame.Surface, font: pygame.font.Font):
        """Draws pulsing glowing capsule with symbol."""
        r = int(self.radius)
        glow_size = r * 3
        s = pygame.Surface((glow_size * 2, glow_size * 2), pygame.SRCALPHA)
        center = (glow_size, glow_size)

        pulse = 1.0 + 0.15 * math.sin(self.phase * 2)
        cur_r = int(r * pulse)

        # Outer soft glow
        pygame.draw.circle(s, (*self.color, 65), center, cur_r + 8)
        # Inner shield ring
        pygame.draw.circle(s, (*self.color, 210), center, cur_r, width=3)
        # Dark tech core
        pygame.draw.circle(s, (15, 20, 35, 220), center, cur_r - 2)

        surface.blit(s, (int(self.x) - glow_size, int(self.y) - glow_size), special_flags=pygame.BLEND_ADD)

        # Symbol text in center
        text_surf = font.render(self.symbol, True, self.color)
        t_rect = text_surf.get_rect(center=(int(self.x), int(self.y)))
        surface.blit(text_surf, t_rect)
