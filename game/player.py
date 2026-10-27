"""
Player Spaceship Controller for GestureStrike.
Handles movement interpolation, primary plasma blasters, triple spread cannons,
energy defensive shield, EMP smart bombs, invulnerability states, and procedural graphics.
"""

import math
import random
import pygame
from typing import List, Tuple, Optional
from config import (
    WINDOW_WIDTH,
    WINDOW_HEIGHT,
    COLOR_PRIMARY_CYAN,
    COLOR_PRIMARY_BLUE,
    COLOR_ACCENT_MAGENTA,
    COLOR_WHITE,
    COLOR_NEON_YELLOW,
    COLOR_ALERT_RED,
    PLAYER_SPEED,
    PLAYER_START_LIVES,
    PLAYER_MAX_LIVES,
    PLAYER_INVULN_TIME,
    FIRE_COOLDOWN_NORMAL,
    FIRE_COOLDOWN_RAPID,
    TRIPLE_SHOT_ANGLE,
    SHIELD_MAX_ENERGY,
    SHIELD_DRAIN_RATE,
    SHIELD_RECHARGE_RATE,
    SHIELD_COOLDOWN,
    MAX_BOMBS,
    FOLLOW_SPEED
)
from game.bullets import PlayerBullet, SmartBombWave
from game.powerups import PowerUpType
from game.particles import ParticleManager


class Player:
    """The player's starship entity."""

    def __init__(self, x: float = WINDOW_WIDTH // 2, y: float = WINDOW_HEIGHT - 120):
        self.x = x
        self.y = y
        self.vx = 0.0
        self.vy = 0.0
        self.target_x = x
        self.target_y = y

        self.width = 52
        self.height = 64
        self.lives = PLAYER_START_LIVES
        self.max_lives = PLAYER_MAX_LIVES
        self.invulnerable_timer = 0.0
        self.alive = True

        # Weapons
        self.fire_timer = 0.0
        self.has_rapid_fire = False
        self.rapid_fire_timer = 0.0
        self.has_triple_shot = False
        self.triple_shot_timer = 0.0

        # Shield
        self.shield_active = False
        self.shield_energy = SHIELD_MAX_ENERGY
        self.shield_cooldown_timer = 0.0
        self.shield_pulse = 0.0

        # Smart EMP Bombs
        self.bombs = MAX_BOMBS
        self.bomb_cooldown = 0.0

        # Score Multiplier Power-up
        self.score_multiplier = 1.0
        self.multiplier_timer = 0.0

        # Engine animation
        self.engine_phase = 0.0

    @property
    def rect(self) -> pygame.Rect:
        """Collision hitbox (slightly smaller than visual hull for forgiving dodging)."""
        w = 34
        h = 42
        return pygame.Rect(int(self.x - w / 2), int(self.y - h / 2), w, h)

    @property
    def shield_rect(self) -> pygame.Rect:
        """Expanded defensive barrier hitbox."""
        r = 54
        return pygame.Rect(int(self.x - r), int(self.y - r), r * 2, r * 2)

    def set_target(self, target_x: float, target_y: float):
        """Sets target position from hand tracking or mouse input."""
        margin_x = self.width // 2 + 10
        margin_y = self.height // 2 + 10
        self.target_x = max(margin_x, min(WINDOW_WIDTH - margin_x, target_x))
        self.target_y = max(margin_y, min(WINDOW_HEIGHT - margin_y, target_y))

    def move_keyboard(self, dx: float, dy: float, dt: float):
        """Moves player using keyboard directional inputs."""
        speed = 520.0
        self.target_x += dx * speed * dt
        self.target_y += dy * speed * dt
        margin_x = self.width // 2 + 10
        margin_y = self.height // 2 + 10
        self.target_x = max(margin_x, min(WINDOW_WIDTH - margin_x, self.target_x))
        self.target_y = max(margin_y, min(WINDOW_HEIGHT - margin_y, self.target_y))

    def update(self, dt: float, particles: ParticleManager):
        """Updates player physics, timers, shields, and thruster particles."""
        # Frame-rate independent exponential following toward filtered hand target
        factor = 1.0 - math.exp(-FOLLOW_SPEED * dt)
        self.x += (self.target_x - self.x) * factor
        self.y += (self.target_y - self.y) * factor

        # Timers
        if self.invulnerable_timer > 0:
            self.invulnerable_timer = max(0.0, self.invulnerable_timer - dt)

        if self.fire_timer > 0:
            self.fire_timer = max(0.0, self.fire_timer - dt)

        if self.bomb_cooldown > 0:
            self.bomb_cooldown = max(0.0, self.bomb_cooldown - dt)

        # Power-up expiration
        if self.has_rapid_fire:
            self.rapid_fire_timer -= dt
            if self.rapid_fire_timer <= 0:
                self.has_rapid_fire = False

        if self.has_triple_shot:
            self.triple_shot_timer -= dt
            if self.triple_shot_timer <= 0:
                self.has_triple_shot = False

        if self.multiplier_timer > 0:
            self.multiplier_timer -= dt
            if self.multiplier_timer <= 0:
                self.score_multiplier = 1.0

        # Shield Mechanics
        if self.shield_active:
            self.shield_pulse += dt * 10.0
            self.shield_energy -= SHIELD_DRAIN_RATE * dt
            if self.shield_energy <= 0.0:
                self.shield_energy = 0.0
                self.shield_active = False
                self.shield_cooldown_timer = SHIELD_COOLDOWN
        else:
            if self.shield_cooldown_timer > 0:
                self.shield_cooldown_timer -= dt
            else:
                self.shield_energy = min(SHIELD_MAX_ENERGY, self.shield_energy + SHIELD_RECHARGE_RATE * dt)

        # Engine particle emitter
        self.engine_phase += dt * 25.0
        # Left and right thruster nozzles
        thrust_y = self.y + 26
        particles.spawn_engine_trail(self.x - 14, thrust_y, COLOR_PRIMARY_CYAN)
        particles.spawn_engine_trail(self.x + 14, thrust_y, COLOR_PRIMARY_CYAN)

    def trigger_shield(self, activate: bool) -> bool:
        """
        Requests shield activation. Returns True if shield is actively shielding.
        """
        if activate and self.shield_energy > 10.0 and self.shield_cooldown_timer <= 0:
            self.shield_active = True
            return True
        else:
            self.shield_active = False
            return False

    def can_fire(self) -> bool:
        """Returns True if blaster cannons are off cooldown."""
        return self.fire_timer <= 0

    def fire(self) -> List[PlayerBullet]:
        """Fires plasma projectiles based on current active weapon buffs."""
        bullets = []
        cooldown = FIRE_COOLDOWN_RAPID if self.has_rapid_fire else FIRE_COOLDOWN_NORMAL
        self.fire_timer = cooldown

        # Left and right wing cannons
        c_left = self.x - 16
        c_right = self.x + 16
        c_y = self.y - 12

        if self.has_triple_shot:
            # Center dual bolts
            bullets.append(PlayerBullet(c_left, c_y, vx=0.0, vy=-18.0, color=COLOR_ACCENT_MAGENTA))
            bullets.append(PlayerBullet(c_right, c_y, vx=0.0, vy=-18.0, color=COLOR_ACCENT_MAGENTA))

            # Angled spread bolts
            angle_rad = math.radians(TRIPLE_SHOT_ANGLE)
            speed = 18.0
            vx_left = -math.sin(angle_rad) * speed
            vy_left = -math.cos(angle_rad) * speed
            vx_right = math.sin(angle_rad) * speed
            vy_right = -math.cos(angle_rad) * speed

            bullets.append(PlayerBullet(c_left - 4, c_y, vx=vx_left, vy=vy_left, color=COLOR_ACCENT_MAGENTA))
            bullets.append(PlayerBullet(c_right + 4, c_y, vx=vx_right, vy=vy_right, color=COLOR_ACCENT_MAGENTA))
        else:
            # Standard twin cyan plasma cannons
            bullets.append(PlayerBullet(c_left, c_y, vx=0.0, vy=-18.0, color=COLOR_PRIMARY_CYAN))
            bullets.append(PlayerBullet(c_right, c_y, vx=0.0, vy=-18.0, color=COLOR_PRIMARY_CYAN))

        return bullets

    def fire_bomb(self) -> Optional[SmartBombWave]:
        """Fires an EMP screen-clearing smart bomb if charges remain."""
        if self.bombs > 0 and self.bomb_cooldown <= 0:
            self.bombs -= 1
            self.bomb_cooldown = 1.2
            return SmartBombWave(self.x, self.y)
        return None

    def apply_powerup(self, ptype: str):
        """Applies collected power-up buff."""
        if ptype == PowerUpType.RAPID_FIRE:
            self.has_rapid_fire = True
            self.rapid_fire_timer = 10.0
        elif ptype == PowerUpType.TRIPLE_SHOT:
            self.has_triple_shot = True
            self.triple_shot_timer = 12.0
        elif ptype == PowerUpType.EXTRA_LIFE:
            self.lives = min(self.max_lives, self.lives + 1)
        elif ptype == PowerUpType.SCORE_MULTIPLIER:
            self.score_multiplier = 2.0
            self.multiplier_timer = 15.0

    def take_damage(self) -> bool:
        """
        Applies damage if not invulnerable and shield is down.
        Returns True if player actually took damage, False if protected.
        """
        if self.shield_active:
            # Shield absorbed hit!
            self.shield_energy = max(0.0, self.shield_energy - 25.0)
            if self.shield_energy <= 0.0:
                self.shield_active = False
                self.shield_cooldown_timer = SHIELD_COOLDOWN
            return False

        if self.invulnerable_timer > 0:
            return False

        self.lives -= 1
        self.invulnerable_timer = PLAYER_INVULN_TIME
        if self.lives <= 0:
            self.alive = False
        return True

    def draw(self, surface: pygame.Surface):
        """Renders the player ship with vector geometry, lighting, and shields."""
        # Flicker visibility while invulnerable
        if self.invulnerable_timer > 0:
            if int(self.invulnerable_timer * 14) % 2 == 1:
                return

        x = int(self.x)
        y = int(self.y)

        # 1. SHIP HULL POLYGON POINTS
        # Nose tip
        nose = (x, y - 28)
        # Left wing
        wing_left_outer = (x - 26, y + 16)
        wing_left_inner = (x - 14, y + 26)
        engine_left = (x - 14, y + 22)
        center_engine = (x, y + 18)
        engine_right = (x + 14, y + 22)
        wing_right_inner = (x + 14, y + 26)
        wing_right_outer = (x + 26, y + 16)

        hull_pts = [nose, wing_left_outer, wing_left_inner, engine_left, center_engine, engine_right, wing_right_inner, wing_right_outer]

        # Draw dark inner armor
        pygame.draw.polygon(surface, (20, 26, 48), hull_pts)

        # Draw glowing neon cyan border lines
        border_col = COLOR_ACCENT_MAGENTA if self.has_triple_shot else COLOR_PRIMARY_CYAN
        pygame.draw.polygon(surface, border_col, hull_pts, width=2)

        # Wing cannon barrels
        pygame.draw.line(surface, border_col, (x - 16, y + 4), (x - 16, y - 14), 3)
        pygame.draw.line(surface, border_col, (x + 16, y + 4), (x + 16, y - 14), 3)

        # Glowing Cockpit Canopy
        cockpit_pts = [(x, y - 14), (x - 5, y + 2), (x + 5, y + 2)]
        pygame.draw.polygon(surface, (180, 240, 255), cockpit_pts)
        pygame.draw.polygon(surface, COLOR_WHITE, cockpit_pts, width=1)

        # 2. SHIELD BUBBLE (if active)
        if self.shield_active:
            r = 52
            pulse = 1.0 + 0.08 * math.sin(self.shield_pulse)
            cur_r = int(r * pulse)
            shield_surf = pygame.Surface((cur_r * 2 + 8, cur_r * 2 + 8), pygame.SRCALPHA)
            center = (cur_r + 4, cur_r + 4)

            # Outer aura
            pygame.draw.circle(shield_surf, (*COLOR_PRIMARY_CYAN, 40), center, cur_r + 4)
            # Energy perimeter
            pygame.draw.circle(shield_surf, (*COLOR_PRIMARY_CYAN, 190), center, cur_r, width=3)
            # Hexagonal interior arc
            for a in range(6):
                ang = a * (math.pi / 3) + self.shield_pulse * 0.4
                px = center[0] + math.cos(ang) * (cur_r - 6)
                py = center[1] + math.sin(ang) * (cur_r - 6)
                pygame.draw.circle(shield_surf, (255, 255, 255, 180), (int(px), int(py)), 3)

            surface.blit(shield_surf, (x - cur_r - 4, y - cur_r - 4), special_flags=pygame.BLEND_ADD)
