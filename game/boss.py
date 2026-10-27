"""
Dreadnought Boss Encounter System for GestureStrike.
Encountered every 5 waves. Features multi-phase attack choreography:
Phase 1: Dual plasma broadsides and spread volleys.
Phase 2: Spiral reactor barrage and escort drone deployment.
Phase 3: Enraged high-speed sweep with charging apocalyptic laser beam.
All rendered with procedural neon sci-fi vector graphics.
"""

import math
import random
import pygame
from typing import List, Tuple, Optional
from config import (
    WINDOW_WIDTH,
    WINDOW_HEIGHT,
    COLOR_ALERT_RED,
    COLOR_ACCENT_MAGENTA,
    COLOR_NEON_YELLOW,
    COLOR_PRIMARY_CYAN,
    COLOR_WHITE
)
from game.bullets import EnemyBullet, BossLaserBeam
from game.enemies import Enemy, ScoutEnemy, ViperEnemy
from game.particles import ParticleManager


class Boss(Enemy):
    """The Dreadnought Flagship Boss."""

    def __init__(self, wave: int):
        hp = 1800 + (wave // 5 - 1) * 600
        super().__init__(
            x=WINDOW_WIDTH // 2,
            y=-120,
            enemy_type="BOSS",
            hp=hp,
            score_value=5000 + wave * 500,
            color=COLOR_ACCENT_MAGENTA
        )
        self.wave = wave
        self.width = 190
        self.height = 110
        self.target_y = 110.0
        self.is_entering = True

        # Movement AI
        self.vx = 2.4 + (wave // 5) * 0.4
        self.phase_time = 0.0

        # Weapon timers
        self.attack_timer = 2.0
        self.spiral_angle = 0.0
        self.drone_spawn_timer = 6.0
        self.active_laser: Optional[BossLaserBeam] = None

        # Defeat explosion state
        self.dying = False
        self.death_timer = 0.0

    @property
    def rect(self) -> pygame.Rect:
        w = int(self.width * 0.85)
        h = int(self.height * 0.85)
        return pygame.Rect(int(self.x - w / 2), int(self.y - h / 2), w, h)

    @property
    def current_phase(self) -> int:
        """Returns 1, 2, or 3 based on remaining health percentage."""
        pct = self.hp / self.max_hp
        if pct > 0.65:
            return 1
        elif pct > 0.30:
            return 2
        else:
            return 3

    def update_boss(
        self,
        dt: float,
        player_x: float,
        player_y: float,
        particles: ParticleManager
    ) -> Tuple[List[EnemyBullet], Optional[BossLaserBeam], Optional[Enemy]]:
        """
        Updates boss AI, movement, and attacks.
        Returns (bullets, optional_laser, optional_escort_drone).
        """
        if self.hit_flash_timer > 0:
            self.hit_flash_timer -= dt

        bullets: List[EnemyBullet] = []
        laser = None
        new_minion = None

        # Entrance cinematic descent
        if self.is_entering:
            self.y += 2.0 * (dt * 60.0)
            if self.y >= self.target_y:
                self.y = self.target_y
                self.is_entering = False
            return bullets, laser, new_minion

        self.phase_time += dt

        # Lateral patrol movement
        speed_mult = 1.6 if self.current_phase == 3 else 1.0
        self.x += self.vx * speed_mult * (dt * 60.0)
        margin = self.width // 2 + 40
        if self.x < margin:
            self.x = margin
            self.vx = abs(self.vx)
        elif self.x > WINDOW_WIDTH - margin:
            self.x = WINDOW_WIDTH - margin
            self.vx = -abs(self.vx)

        # Damage smoke and spark effects when damaged
        if self.hp < self.max_hp * 0.5:
            if random.random() < 0.4:
                particles.spawn_explosion(
                    self.x + random.uniform(-60, 60),
                    self.y + random.uniform(-30, 30),
                    count=2,
                    speed_scale=0.4
                )

        # ----------------------------------------------------
        # ATTACK PATTERNS BY PHASE
        # ----------------------------------------------------
        self.attack_timer -= dt

        # PHASE 1: Broadside twin volleys + 5-shot spread
        if self.current_phase == 1:
            if self.attack_timer <= 0:
                self.attack_timer = 1.3
                # Twin wing cannons
                wing_offset = 64
                bullets.append(EnemyBullet(self.x - wing_offset, self.y + 40, vx=0.0, vy=5.5))
                bullets.append(EnemyBullet(self.x + wing_offset, self.y + 40, vx=0.0, vy=5.5))

                # Periodically fire 5-shot spread
                if int(self.phase_time) % 3 == 0:
                    for angle_deg in [-30, -15, 0, 15, 30]:
                        rad = math.radians(angle_deg + 90)
                        speed = 5.0
                        bullets.append(EnemyBullet(
                            self.x, self.y + 45,
                            vx=math.cos(rad) * speed,
                            vy=math.sin(rad) * speed,
                            color=COLOR_ALERT_RED
                        ))

        # PHASE 2: Spiral reactor burst + escort drone spawn
        elif self.current_phase == 2:
            if self.attack_timer <= 0:
                self.attack_timer = 0.22  # Rapid spiral stream
                self.spiral_angle += 0.38
                speed = 5.2
                vx = math.cos(self.spiral_angle) * speed
                vy = math.sin(self.spiral_angle) * speed
                bullets.append(EnemyBullet(self.x, self.y + 30, vx=vx, vy=max(1.5, vy), color=COLOR_NEON_YELLOW))

            # Escort drone deployment
            self.drone_spawn_timer -= dt
            if self.drone_spawn_timer <= 0:
                self.drone_spawn_timer = 5.5
                drone_cls = random.choice([ScoutEnemy, ViperEnemy])
                spawn_x = self.x + random.choice([-80, 80])
                new_minion = drone_cls(spawn_x, self.y + 20)

        # PHASE 3: Enraged desperate assault with apocalyptic center laser
        elif self.current_phase == 3:
            # Active laser maintenance
            if self.active_laser and self.active_laser.alive:
                self.active_laser.x = self.x
                self.active_laser.y = self.y + 45
            else:
                # Trigger laser attack every 5 seconds
                if self.attack_timer <= 0:
                    self.attack_timer = 4.8
                    self.active_laser = BossLaserBeam(self.x, self.y + 45, width=44.0, charge_time=0.9, active_time=1.4)
                    laser = self.active_laser

            # High-speed targeted burst fire from wing turrets
            if int(self.phase_time * 5) % 3 == 0 and random.random() < 0.25:
                angle = math.atan2(player_y - self.y, player_x - self.x)
                speed = 7.2
                bullets.append(EnemyBullet(
                    self.x + random.choice([-50, 50]),
                    self.y + 35,
                    vx=math.cos(angle) * speed,
                    vy=math.sin(angle) * speed,
                    color=COLOR_ALERT_RED
                ))

        return bullets, laser, new_minion

    def draw(self, surface: pygame.Surface):
        x = int(self.x)
        y = int(self.y)

        # Hull flash on hit
        is_flash = self.hit_flash_timer > 0
        hull_color = COLOR_WHITE if is_flash else (
            COLOR_ALERT_RED if self.current_phase == 3 else COLOR_ACCENT_MAGENTA
        )
        armor_color = (25, 12, 28)

        # Heavy Dreadnought Polygon Blueprint
        pts = [
            (x, y + 48),          # Front ramming prow
            (x - 30, y + 42),
            (x - 70, y + 24),     # Left mid cannon pod
            (x - 90, y - 8),      # Left outer wing tip
            (x - 75, y - 38),     # Left rear engine
            (x - 35, y - 48),     # Left upper reactor
            (x + 35, y - 48),     # Right upper reactor
            (x + 75, y - 38),     # Right rear engine
            (x + 90, y - 8),      # Right outer wing tip
            (x + 70, y + 24),     # Right mid cannon pod
            (x + 30, y + 42)
        ]

        # Draw dark reinforced armor plates
        pygame.draw.polygon(surface, armor_color, pts)
        pygame.draw.polygon(surface, hull_color, pts, width=3)

        # Central glowing reactor core
        core_r = 18 if self.current_phase != 2 else int(22 + 4 * math.sin(self.phase_time * 12))
        core_col = COLOR_ALERT_RED if self.current_phase == 3 else COLOR_NEON_YELLOW
        pygame.draw.circle(surface, core_col, (x, y), core_r)
        pygame.draw.circle(surface, COLOR_WHITE, (x, y), core_r // 2)

        # Wing cannon turrets
        pygame.draw.rect(surface, hull_color, (x - 72, y + 20, 10, 24))
        pygame.draw.rect(surface, hull_color, (x + 62, y + 20, 10, 24))

        # Heavy command bridge
        bridge_pts = [(x, y - 18), (x - 16, y - 2), (x + 16, y - 2)]
        pygame.draw.polygon(surface, COLOR_PRIMARY_CYAN, bridge_pts)
        pygame.draw.polygon(surface, COLOR_WHITE, bridge_pts, width=1)
