"""
Visual Effects and Particle System for GestureStrike.
Includes sparks, engine thruster trails, shockwave blast rings,
floating combat text, screen shake, and 3-layer parallax starfield.
"""

import math
import random
import pygame
from typing import List, Tuple, Dict, Any
from config import (
    WINDOW_WIDTH,
    WINDOW_HEIGHT,
    COLOR_PRIMARY_CYAN,
    COLOR_NEON_ORANGE,
    COLOR_NEON_YELLOW,
    COLOR_ACCENT_MAGENTA,
    COLOR_WHITE,
    STARFIELD_LAYERS
)


class Particle:
    """A single physics-driven glowing spark or smoke particle."""

    def __init__(
        self,
        x: float,
        y: float,
        vx: float,
        vy: float,
        color: Tuple[int, int, int],
        size: float,
        lifetime: float,
        drag: float = 0.96,
        fade_speed: float = 1.0
    ):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.color = color
        self.initial_size = size
        self.size = size
        self.lifetime = lifetime
        self.max_lifetime = lifetime
        self.drag = drag
        self.fade_speed = fade_speed

    def update(self, dt: float) -> bool:
        """Updates particle physics. Returns False when particle expires."""
        self.lifetime -= dt * self.fade_speed
        if self.lifetime <= 0:
            return False

        self.x += self.vx * (dt * 60.0)
        self.y += self.vy * (dt * 60.0)
        self.vx *= self.drag
        self.vy *= self.drag

        progress = max(0.0, self.lifetime / self.max_lifetime)
        self.size = self.initial_size * progress
        return True

    def draw(self, surface: pygame.Surface):
        """Draws glowing particle with soft alpha falloff."""
        if self.size < 0.5:
            return
        progress = max(0.0, min(1.0, self.lifetime / self.max_lifetime))
        alpha = int(255 * progress)

        # Glow radius
        r = int(self.size)
        glow_surf = pygame.Surface((r * 4 + 2, r * 4 + 2), pygame.SRCALPHA)
        center = (r * 2 + 1, r * 2 + 1)

        # Soft outer halo
        pygame.draw.circle(glow_surf, (*self.color, alpha // 3), center, r * 2)
        # Bright core
        pygame.draw.circle(glow_surf, (*self.color, alpha), center, r)
        # White hot center
        if r >= 2:
            pygame.draw.circle(glow_surf, (255, 255, 255, alpha), center, max(1, r // 2))

        surface.blit(glow_surf, (int(self.x) - r * 2 - 1, int(self.y) - r * 2 - 1), special_flags=pygame.BLEND_ADD)


class Shockwave:
    """Expanding neon shockwave ring emitted by bomb or boss explosion."""

    def __init__(
        self,
        x: float,
        y: float,
        color: Tuple[int, int, int] = COLOR_PRIMARY_CYAN,
        max_radius: float = 240.0,
        speed: float = 400.0,
        width: int = 4
    ):
        self.x = x
        self.y = y
        self.color = color
        self.radius = 4.0
        self.max_radius = max_radius
        self.speed = speed
        self.width = width

    def update(self, dt: float) -> bool:
        """Expands radius. Returns False when maximum radius reached."""
        self.radius += self.speed * dt
        return self.radius < self.max_radius

    def draw(self, surface: pygame.Surface):
        """Draws shockwave ring with alpha transparency."""
        progress = self.radius / self.max_radius
        alpha = int(255 * (1.0 - progress))
        if alpha <= 0 or self.radius < 2:
            return

        r = int(self.radius)
        surf_dim = r * 2 + 8
        ring_surf = pygame.Surface((surf_dim, surf_dim), pygame.SRCALPHA)
        center = (r + 4, r + 4)

        current_width = max(1, int(self.width * (1.0 - progress * 0.5)))
        pygame.draw.circle(ring_surf, (*self.color, alpha), center, r, width=current_width)
        surface.blit(ring_surf, (int(self.x) - r - 4, int(self.y) - r - 4), special_flags=pygame.BLEND_ADD)


class FloatingText:
    """Floating animated text for score popups and combos."""

    def __init__(
        self,
        text: str,
        x: float,
        y: float,
        font: pygame.font.Font,
        color: Tuple[int, int, int] = COLOR_NEON_YELLOW,
        duration: float = 1.0,
        vy: float = -45.0
    ):
        self.text = text
        self.x = x
        self.y = y
        self.font = font
        self.color = color
        self.lifetime = duration
        self.max_lifetime = duration
        self.vy = vy

    def update(self, dt: float) -> bool:
        """Moves text upward and fades out."""
        self.lifetime -= dt
        self.y += self.vy * dt
        return self.lifetime > 0

    def draw(self, surface: pygame.Surface):
        """Draws fading text."""
        progress = max(0.0, self.lifetime / self.max_lifetime)
        alpha = int(255 * progress)
        rendered = self.font.render(self.text, True, self.color)
        rendered.set_alpha(alpha)
        rect = rendered.get_rect(center=(int(self.x), int(self.y)))
        surface.blit(rendered, rect)


class ScreenShake:
    """Trauma-based screen shake for cinematic impacts."""

    def __init__(self):
        self.trauma = 0.0
        self.max_offset = 18.0
        self.decay = 2.4

    def add_trauma(self, amount: float):
        """Adds trauma (0.0 to 1.0)."""
        self.trauma = min(1.0, self.trauma + amount)

    def update(self, dt: float) -> Tuple[int, int]:
        """Calculates current shake offset and decays trauma."""
        if self.trauma <= 0.001:
            self.trauma = 0.0
            return 0, 0

        self.trauma = max(0.0, self.trauma - self.decay * dt)
        shake_mag = (self.trauma ** 2) * self.max_offset
        ox = int(random.uniform(-shake_mag, shake_mag))
        oy = int(random.uniform(-shake_mag, shake_mag))
        return ox, oy


class ParallaxStarfield:
    """3-layer starfield background with smooth parallax scrolling."""

    def __init__(self, width: int = WINDOW_WIDTH, height: int = WINDOW_HEIGHT):
        self.width = width
        self.height = height
        self.warp_multiplier = 1.0
        self.layers: List[Dict[str, Any]] = []

        for layer_cfg in STARFIELD_LAYERS:
            stars = []
            for _ in range(layer_cfg["count"]):
                stars.append({
                    "x": random.uniform(0, width),
                    "y": random.uniform(0, height),
                    "speed": layer_cfg["speed"],
                    "size": layer_cfg["size"],
                    "color": layer_cfg["color"]
                })
            self.layers.append({"config": layer_cfg, "stars": stars})

    def update(self, dt: float, warp: bool = False):
        """Updates star positions."""
        target_warp = 4.5 if warp else 1.0
        self.warp_multiplier += (target_warp - self.warp_multiplier) * (dt * 4.0)

        for layer in self.layers:
            for star in layer["stars"]:
                star["y"] += star["speed"] * self.warp_multiplier * (dt * 60.0)
                if star["y"] > self.height:
                    star["y"] = 0
                    star["x"] = random.uniform(0, self.width)

    def draw(self, surface: pygame.Surface):
        """Draws all starfield layers."""
        for layer in self.layers:
            for star in layer["stars"]:
                x = int(star["x"])
                y = int(star["y"])
                size = star["size"]
                color = star["color"]

                if self.warp_multiplier > 1.8:
                    # Draw warp stretch streak
                    trail_len = int(size * self.warp_multiplier * 2.2)
                    pygame.draw.line(surface, color, (x, y), (x, min(self.height, y + trail_len)), int(size))
                else:
                    if size <= 1.5:
                        surface.set_at((x, y), color)
                    else:
                        pygame.draw.circle(surface, color, (x, y), int(size))


class ParticleManager:
    """Central container and updater for all particle effects and shockwaves."""

    def __init__(self):
        self.particles: List[Particle] = []
        self.shockwaves: List[Shockwave] = []
        self.floating_texts: List[FloatingText] = []

    def clear(self):
        """Clears all active particles and effects."""
        self.particles.clear()
        self.shockwaves.clear()
        self.floating_texts.clear()

    def spawn_engine_trail(self, x: float, y: float, color: Tuple[int, int, int] = COLOR_PRIMARY_CYAN):
        """Spawns small flickering engine flame particle."""
        vx = random.uniform(-0.6, 0.6)
        vy = random.uniform(2.5, 4.5)
        size = random.uniform(2.5, 4.5)
        lifetime = random.uniform(0.18, 0.32)
        self.particles.append(Particle(x, y, vx, vy, color, size, lifetime, drag=0.94))

    def spawn_explosion(self, x: float, y: float, count: int = 24, colors=None, speed_scale: float = 1.0):
        """Spawns explosive spark burst."""
        if colors is None:
            colors = [COLOR_NEON_ORANGE, COLOR_NEON_YELLOW, COLOR_WHITE, COLOR_ACCENT_MAGENTA]

        for _ in range(count):
            angle = random.uniform(0, 2 * math.pi)
            speed = random.uniform(2.0, 7.5) * speed_scale
            vx = math.cos(angle) * speed
            vy = math.sin(angle) * speed
            col = random.choice(colors)
            size = random.uniform(2.0, 5.0)
            lifetime = random.uniform(0.25, 0.55)
            self.particles.append(Particle(x, y, vx, vy, col, size, lifetime, drag=0.92))

    def spawn_shockwave(self, x: float, y: float, color=COLOR_PRIMARY_CYAN, max_radius=220.0):
        """Spawns expanding shockwave ring."""
        self.shockwaves.append(Shockwave(x, y, color=color, max_radius=max_radius))

    def spawn_floating_text(self, text: str, x: float, y: float, font: pygame.font.Font, color=COLOR_NEON_YELLOW):
        """Spawns combat popup text."""
        self.floating_texts.append(FloatingText(text, x, y, font, color=color))

    def update(self, dt: float):
        """Updates all particles, shockwaves, and texts."""
        self.particles = [p for p in self.particles if p.update(dt)]
        self.shockwaves = [s for s in self.shockwaves if s.update(dt)]
        self.floating_texts = [t for t in self.floating_texts if t.update(dt)]

    def draw(self, surface: pygame.Surface):
        """Draws all shockwaves, particles, and floating texts."""
        for s in self.shockwaves:
            s.draw(surface)
        for p in self.particles:
            p.draw(surface)
        for t in self.floating_texts:
            t.draw(surface)
