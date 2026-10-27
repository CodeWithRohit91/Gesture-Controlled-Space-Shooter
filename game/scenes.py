"""
Scene Management and UI States for GestureStrike.
Contains Main Menu, Calibration, Controls Guide, High Scores,
Active Gameplay (with Pause & Hand-Lost Auto-Pause overlays),
and Game Over with High Score entry.
"""

import os
import json
import time
import random
import pygame
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime

from config import (
    WINDOW_WIDTH,
    WINDOW_HEIGHT,
    COLOR_BG_DARK,
    COLOR_PRIMARY_CYAN,
    COLOR_PRIMARY_BLUE,
    COLOR_ACCENT_MAGENTA,
    COLOR_NEON_GREEN,
    COLOR_NEON_YELLOW,
    COLOR_ALERT_RED,
    COLOR_WHITE,
    COLOR_GRAY_LIGHT,
    COLOR_GRAY_DARK,
    COLOR_OVERLAY_DARK,
    HIGHSCORES_FILE,
    ENEMY_WAVE_BASE_COUNT,
    ENEMY_WAVE_INCREMENT,
    BOSS_WAVE_INTERVAL,
    COMBO_TIMEOUT
)
from vision.gesture_recognizer import HandGesture
from vision.calibration import HandCalibrator
from vision.hand_tracker import HandTracker
from audio.sound_generator import SoundManager

from game.particles import ParticleManager, ParallaxStarfield, ScreenShake
from game.player import Player
from game.enemies import Enemy, ScoutEnemy, ViperEnemy, InterceptorEnemy, GunnerEnemy
from game.boss import Boss
from game.bullets import Bullet, PlayerBullet, EnemyBullet, BossLaserBeam, SmartBombWave
from game.powerups import PowerUp
from game.hud import HUD


class SceneType:
    MENU = "MENU"
    CALIBRATION = "CALIBRATION"
    CONTROLS = "CONTROLS"
    HIGHSCORES = "HIGHSCORES"
    GAMEPLAY = "GAMEPLAY"
    GAMEOVER = "GAMEOVER"


class TransitionManager:
    """Handles smooth alpha fade-in and fade-out transitions between scenes."""

    def __init__(self):
        self.alpha = 255.0
        self.fade_direction = -1  # -1 = fading in from black, +1 = fading out to black
        self.fade_speed = 550.0   # Alpha change per second
        self.next_scene: Optional[str] = None
        self.is_transitioning = False

    def fade_to(self, scene_name: str):
        """Starts fade out toward target scene."""
        self.next_scene = scene_name
        self.fade_direction = 1
        self.is_transitioning = True

    def update(self, dt: float) -> Optional[str]:
        """Updates transition alpha. Returns new scene name upon full blackout."""
        target_scene = None
        self.alpha += self.fade_direction * self.fade_speed * dt

        if self.fade_direction == 1 and self.alpha >= 255.0:
            self.alpha = 255.0
            target_scene = self.next_scene
            self.fade_direction = -1  # Begin fade-in on new scene
        elif self.fade_direction == -1 and self.alpha <= 0.0:
            self.alpha = 0.0
            self.is_transitioning = False

        return target_scene

    def draw(self, surface: pygame.Surface):
        """Draws blackout overlay with current alpha."""
        if self.alpha > 1:
            overlay = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT))
            overlay.fill((0, 0, 0))
            overlay.set_alpha(int(self.alpha))
            surface.blit(overlay, (0, 0))


class SceneManager:
    """Master controller managing active scene, transitions, input routing, and shared state."""

    def __init__(self, tracker: HandTracker, sounds: SoundManager):
        self.tracker = tracker
        self.sounds = sounds
        self.current_scene = SceneType.MENU
        self.transition = TransitionManager()

        # Shared Starfield and UI fonts
        self.starfield = ParallaxStarfield()
        self.font_title = pygame.font.SysFont("consolas", 46, bold=True)
        self.font_header = pygame.font.SysFont("consolas", 30, bold=True)
        self.font_body = pygame.font.SysFont("consolas", 20, bold=True)
        self.font_small = pygame.font.SysFont("consolas", 15)
        self.font_tiny = pygame.font.SysFont("consolas", 12)

        # High scores cache
        self.highscores = self._load_highscores()

        # Control Mode State: Defaults to False so Gesture Mode is active when camera opens
        self.keyboard_mode = False
        self.user_toggled_keyboard = False
        self.camera_check_timer = 0.0

        # Calibrator instance
        self.calibrator = HandCalibrator(self.tracker.recognizer)

        # Active Gameplay state
        self.game_state: Optional[Dict[str, Any]] = None

        # Game over inputs
        self.gameover_score = 0
        self.gameover_wave = 1
        self.pilot_name = "PILOT"
        self.name_entered = False

        # Start ambient music
        self.sounds.start_music()

    def _load_highscores(self) -> List[Dict[str, Any]]:
        """Loads persistent scores from data/highscores.json."""
        if os.path.exists(HIGHSCORES_FILE):
            try:
                with open(HIGHSCORES_FILE, "r") as f:
                    scores = json.load(f)
                    scores.sort(key=lambda s: s.get("score", 0), reverse=True)
                    return scores[:10]
            except Exception as e:
                print(f"[SceneManager] Error loading highscores: {e}")
        return []

    def _save_highscores(self, name: str, score: int, wave: int):
        """Saves a new score entry."""
        new_entry = {
            "name": name.strip()[:8].upper() or "PILOT",
            "score": score,
            "wave": wave,
            "date": datetime.now().strftime("%Y-%m-%d")
        }
        self.highscores.append(new_entry)
        self.highscores.sort(key=lambda s: s.get("score", 0), reverse=True)
        self.highscores = self.highscores[:10]

        try:
            with open(HIGHSCORES_FILE, "w") as f:
                json.dump(self.highscores, f, indent=2)
            print("[SceneManager] High scores saved successfully.")
        except Exception as e:
            print(f"[SceneManager] Error saving highscores: {e}")

    def change_scene(self, target_scene: str):
        """Triggers scene fade transition."""
        self.sounds.play("ui_blip")
        self.transition.fade_to(target_scene)

    def handle_event(self, event: pygame.event.Event):
        """Global event dispatcher."""
        # Global hotkey 'M' toggles audio mute
        if event.type == pygame.KEYDOWN and event.key == pygame.K_m:
            self.sounds.toggle_mute()

        # Global hotkey 'K' toggles keyboard/mouse fallback mode
        if event.type == pygame.KEYDOWN and event.key == pygame.K_k:
            self.user_toggled_keyboard = True
            self.keyboard_mode = not self.keyboard_mode
            self.sounds.play("ui_blip")

        # Route to active scene handler
        if self.current_scene == SceneType.MENU:
            self._handle_menu_events(event)
        elif self.current_scene == SceneType.CALIBRATION:
            self._handle_calibration_events(event)
        elif self.current_scene == SceneType.CONTROLS:
            self._handle_controls_events(event)
        elif self.current_scene == SceneType.HIGHSCORES:
            self._handle_highscores_events(event)
        elif self.current_scene == SceneType.GAMEPLAY:
            self._handle_gameplay_events(event)
        elif self.current_scene == SceneType.GAMEOVER:
            self._handle_gameover_events(event)

    def update(self, dt: float):
        """Updates game simulation, starfield, and active scene logic."""
        # Update transition
        new_scene = self.transition.update(dt)
        if new_scene:
            self.current_scene = new_scene
            if new_scene == SceneType.GAMEPLAY and self.game_state is None:
                self._init_new_game()

        # Update starfield parallax
        is_warp = False
        if self.current_scene == SceneType.GAMEPLAY and self.game_state:
            is_warp = self.game_state.get("is_wave_transition", False)
        self.starfield.update(dt, warp=is_warp)

        # Update active scene
        if self.current_scene == SceneType.CALIBRATION:
            self._update_calibration(dt)
        elif self.current_scene == SceneType.GAMEPLAY:
            self._update_gameplay(dt)

    def draw(self, surface: pygame.Surface):
        """Renders the current active scene."""
        surface.fill(COLOR_BG_DARK)
        self.starfield.draw(surface)

        if self.current_scene == SceneType.MENU:
            self._draw_menu(surface)
        elif self.current_scene == SceneType.CALIBRATION:
            self._draw_calibration(surface)
        elif self.current_scene == SceneType.CONTROLS:
            self._draw_controls(surface)
        elif self.current_scene == SceneType.HIGHSCORES:
            self._draw_highscores(surface)
        elif self.current_scene == SceneType.GAMEPLAY:
            self._draw_gameplay(surface)
        elif self.current_scene == SceneType.GAMEOVER:
            self._draw_gameover(surface)

        # Screen transition fade overlay
        self.transition.draw(surface)

    # ----------------------------------------------------
    # SCENE: MAIN MENU
    # ----------------------------------------------------
    def _draw_menu(self, surface: pygame.Surface):
        # Title Glow Banner
        title_txt = "GESTURESTRIKE"
        t_surf = self.font_title.render(title_txt, True, COLOR_PRIMARY_CYAN)
        t_rect = t_surf.get_rect(center=(WINDOW_WIDTH // 2, 130))

        # Subtitle
        sub_txt = "AI HAND-CONTROLLED SPACE SHOOTER"
        sub_surf = self.font_small.render(sub_txt, True, COLOR_NEON_YELLOW)
        sub_rect = sub_surf.get_rect(center=(WINDOW_WIDTH // 2, 175))

        surface.blit(t_surf, t_rect)
        surface.blit(sub_surf, sub_rect)

        # Menu Options
        options = [
            ("1. START GAME", SceneType.GAMEPLAY),
            ("2. CALIBRATION", SceneType.CALIBRATION),
            ("3. CONTROLS GUIDE", SceneType.CONTROLS),
            ("4. HIGH SCORES", SceneType.HIGHSCORES),
            ("5. QUIT", "QUIT")
        ]

        mx, my = pygame.mouse.get_pos()
        start_y = 250
        for i, (label, target) in enumerate(options):
            y = start_y + i * 58
            btn_rect = pygame.Rect(WINDOW_WIDTH // 2 - 160, y - 6, 320, 44)
            is_hover = btn_rect.collidepoint(mx, my)

            col = COLOR_WHITE if is_hover else COLOR_GRAY_LIGHT
            border_col = COLOR_PRIMARY_CYAN if is_hover else (35, 45, 70)
            bg_col = (20, 30, 55, 180) if is_hover else (12, 16, 30, 140)

            # Draw cyber button plate
            b_surf = pygame.Surface((btn_rect.width, btn_rect.height), pygame.SRCALPHA)
            b_surf.fill(bg_col)
            pygame.draw.rect(b_surf, border_col, (0, 0, btn_rect.width, btn_rect.height), width=2 if is_hover else 1)
            surface.blit(b_surf, btn_rect)

            txt_surf = self.font_body.render(label, True, col)
            surface.blit(txt_surf, txt_surf.get_rect(center=btn_rect.center))

        # Bottom Tip
        tip = "Steer with your hand via webcam! Press [K] for Keyboard/Mouse mode | [M] Mute"
        tip_surf = self.font_small.render(tip, True, COLOR_GRAY_LIGHT)
        surface.blit(tip_surf, tip_surf.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT - 45)))

    def _handle_menu_events(self, event: pygame.event.Event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos
            start_y = 250
            targets = [SceneType.GAMEPLAY, SceneType.CALIBRATION, SceneType.CONTROLS, SceneType.HIGHSCORES, "QUIT"]
            for i, target in enumerate(targets):
                btn_rect = pygame.Rect(WINDOW_WIDTH // 2 - 160, start_y + i * 58 - 6, 320, 44)
                if btn_rect.collidepoint(mx, my):
                    if target == "QUIT":
                        pygame.event.post(pygame.event.Event(pygame.QUIT))
                    else:
                        if target == SceneType.GAMEPLAY:
                            self._init_new_game()
                        self.change_scene(target)
                    break

        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_1:
                self._init_new_game()
                self.change_scene(SceneType.GAMEPLAY)
            elif event.key == pygame.K_2:
                self.change_scene(SceneType.CALIBRATION)
            elif event.key == pygame.K_3:
                self.change_scene(SceneType.CONTROLS)
            elif event.key == pygame.K_4:
                self.change_scene(SceneType.HIGHSCORES)
            elif event.key == pygame.K_5 or event.key == pygame.K_ESCAPE:
                pygame.event.post(pygame.event.Event(pygame.QUIT))

    # ----------------------------------------------------
    # SCENE: CALIBRATION
    # ----------------------------------------------------
    def _update_calibration(self, dt: float):
        v_state = self.tracker.get_state()
        landmarks = v_state.get("landmarks")
        if self.calibrator.step in [HandCalibrator.STEP_OPEN_PALM, HandCalibrator.STEP_CLOSED_FIST]:
            self.calibrator.feed_frame(landmarks)

    def _draw_calibration(self, surface: pygame.Surface):
        # Header
        h_surf = self.font_header.render("HAND GESTURE CALIBRATION", True, COLOR_PRIMARY_CYAN)
        surface.blit(h_surf, h_surf.get_rect(center=(WINDOW_WIDTH // 2, 70)))

        # Subtitle instructions
        inst = "Calibrate Open Palm and Closed Fist to optimize detection for your hand and webcam lighting."
        inst_surf = self.font_small.render(inst, True, COLOR_GRAY_LIGHT)
        surface.blit(inst_surf, inst_surf.get_rect(center=(WINDOW_WIDTH // 2, 110)))

        # Status Box
        box_rect = pygame.Rect(WINDOW_WIDTH // 2 - 280, 160, 560, 260)
        pygame.draw.rect(surface, (16, 22, 40), box_rect)
        pygame.draw.rect(surface, COLOR_PRIMARY_CYAN, box_rect, width=2)

        # Step indicator
        step_str = f"STEP: {self.calibrator.step} / 3"
        step_surf = self.font_body.render(step_str, True, COLOR_NEON_YELLOW)
        surface.blit(step_surf, (box_rect.left + 30, box_rect.top + 25))

        # Status message
        msg_surf = self.font_body.render(self.calibrator.status_message, True, COLOR_WHITE)
        surface.blit(msg_surf, (box_rect.left + 30, box_rect.top + 75))

        # Progress bar
        bar_w = 500
        bar_h = 20
        bx = box_rect.left + 30
        by = box_rect.top + 130
        pygame.draw.rect(surface, COLOR_GRAY_DARK, (bx, by, bar_w, bar_h))
        pygame.draw.rect(surface, COLOR_NEON_GREEN, (bx, by, int(bar_w * self.calibrator.progress), bar_h))
        pygame.draw.rect(surface, COLOR_WHITE, (bx, by, bar_w, bar_h), width=1)

        # Threshold readouts
        rec = self.tracker.recognizer
        thresh_txt = f"Current Thresholds -> Pinch: {rec.pinch_threshold:.2f} | Fist: {rec.fist_threshold:.2f} | Palm: {rec.palm_threshold:.2f}"
        t_surf = self.font_tiny.render(thresh_txt, True, COLOR_GRAY_LIGHT)
        surface.blit(t_surf, (box_rect.left + 30, box_rect.top + 180))

        # Buttons
        mx, my = pygame.mouse.get_pos()
        btn_start = pygame.Rect(WINDOW_WIDTH // 2 - 220, 460, 200, 45)
        btn_back = pygame.Rect(WINDOW_WIDTH // 2 + 20, 460, 200, 45)

        for rect, label in [(btn_start, "START CALIBRATION"), (btn_back, "BACK TO MENU")]:
            is_hover = rect.collidepoint(mx, my)
            pygame.draw.rect(surface, (20, 30, 60) if is_hover else (12, 16, 32), rect)
            pygame.draw.rect(surface, COLOR_PRIMARY_CYAN if is_hover else (40, 50, 80), rect, width=2 if is_hover else 1)
            t = self.font_body.render(label, True, COLOR_WHITE if is_hover else COLOR_GRAY_LIGHT)
            surface.blit(t, t.get_rect(center=rect.center))

    def _handle_calibration_events(self, event: pygame.event.Event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos
            btn_start = pygame.Rect(WINDOW_WIDTH // 2 - 220, 460, 200, 45)
            btn_back = pygame.Rect(WINDOW_WIDTH // 2 + 20, 460, 200, 45)

            if btn_start.collidepoint(mx, my):
                self.calibrator.start()
                self.sounds.play("ui_blip")
            elif btn_back.collidepoint(mx, my):
                self.change_scene(SceneType.MENU)

        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_SPACE:
                self.calibrator.start()
                self.sounds.play("ui_blip")
            elif event.key == pygame.K_ESCAPE:
                self.change_scene(SceneType.MENU)

    # ----------------------------------------------------
    # SCENE: CONTROLS GUIDE
    # ----------------------------------------------------
    def _draw_controls(self, surface: pygame.Surface):
        h_surf = self.font_header.render("GESTURE & KEYBOARD CONTROLS", True, COLOR_PRIMARY_CYAN)
        surface.blit(h_surf, h_surf.get_rect(center=(WINDOW_WIDTH // 2, 60)))

        # Controls Table Container
        table_rect = pygame.Rect(140, 110, WINDOW_WIDTH - 280, 480)
        pygame.draw.rect(surface, (14, 20, 36, 210), table_rect)
        pygame.draw.rect(surface, COLOR_PRIMARY_CYAN, table_rect, width=2)

        # Table rows: Action, Hand Gesture, Keyboard Fallback
        headers = ["ACTION / FUNCTION", "HAND GESTURE (WEBCAM)", "KEYBOARD / MOUSE FALLBACK"]
        y = table_rect.top + 20

        # Header columns
        col_x = [table_rect.left + 30, table_rect.left + 300, table_rect.left + 640]
        for idx, head in enumerate(headers):
            surf = self.font_body.render(head, True, COLOR_NEON_YELLOW)
            surface.blit(surf, (col_x[idx], y))

        pygame.draw.line(surface, COLOR_PRIMARY_CYAN, (table_rect.left + 20, y + 32), (table_rect.right - 20, y + 32), 2)
        y += 45

        rows = [
            ("Steer Spaceship", "Move Hand across camera frame", "WASD / Arrow Keys or Mouse"),
            ("Primary Lasers", "OPEN PALM (Auto-fires while moving)", "SPACEBAR or Left Mouse Click"),
            ("Plasma Shield", "CLOSED FIST (Hold to block lasers)", "S Key or Right Mouse Click"),
            ("EMP Smart Bomb", "PINCH (Thumb tip touch Index tip)", "B Key or Middle Mouse Click"),
            ("Auto-Pause", "Hand hidden > 1 sec pauses game", "P Key / ESC Key to Pause"),
            ("Toggle Controls", "Press [K] anytime to toggle mode", "Press [K] to toggle"),
            ("Toggle Audio", "Press [M] to mute/unmute beat", "Press [M] to mute/unmute")
        ]

        for action, hand, kb in rows:
            a_surf = self.font_small.render(action, True, COLOR_WHITE)
            h_surf = self.font_small.render(hand, True, COLOR_NEON_GREEN)
            k_surf = self.font_small.render(kb, True, COLOR_PRIMARY_CYAN)

            surface.blit(a_surf, (col_x[0], y))
            surface.blit(h_surf, (col_x[1], y))
            surface.blit(k_surf, (col_x[2], y))
            y += 44

        # Back Button
        mx, my = pygame.mouse.get_pos()
        btn_back = pygame.Rect(WINDOW_WIDTH // 2 - 100, WINDOW_HEIGHT - 90, 200, 44)
        is_hover = btn_back.collidepoint(mx, my)
        pygame.draw.rect(surface, (20, 30, 60) if is_hover else (12, 16, 32), btn_back)
        pygame.draw.rect(surface, COLOR_PRIMARY_CYAN if is_hover else (40, 50, 80), btn_back, width=2 if is_hover else 1)
        b_txt = self.font_body.render("BACK TO MENU", True, COLOR_WHITE if is_hover else COLOR_GRAY_LIGHT)
        surface.blit(b_txt, b_txt.get_rect(center=btn_back.center))

    def _handle_controls_events(self, event: pygame.event.Event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos
            btn_back = pygame.Rect(WINDOW_WIDTH // 2 - 100, WINDOW_HEIGHT - 90, 200, 44)
            if btn_back.collidepoint(mx, my):
                self.change_scene(SceneType.MENU)
        elif event.type == pygame.KEYDOWN and (event.key == pygame.K_ESCAPE or event.key == pygame.K_SPACE):
            self.change_scene(SceneType.MENU)

    # ----------------------------------------------------
    # SCENE: HIGH SCORES
    # ----------------------------------------------------
    def _draw_highscores(self, surface: pygame.Surface):
        h_surf = self.font_header.render("GALACTIC PILOT HALL OF FAME", True, COLOR_PRIMARY_CYAN)
        surface.blit(h_surf, h_surf.get_rect(center=(WINDOW_WIDTH // 2, 70)))

        # Board Container
        board_rect = pygame.Rect(200, 130, WINDOW_WIDTH - 400, 450)
        pygame.draw.rect(surface, (14, 20, 36, 210), board_rect)
        pygame.draw.rect(surface, COLOR_PRIMARY_CYAN, board_rect, width=2)

        # Header Columns: RANK, PILOT NAME, SCORE, WAVE, DATE
        col_x = [board_rect.left + 35, board_rect.left + 120, board_rect.left + 340, board_rect.left + 540, board_rect.left + 680]
        headers = ["RANK", "PILOT", "SCORE", "WAVE", "DATE"]
        y = board_rect.top + 20
        for idx, head in enumerate(headers):
            surf = self.font_body.render(head, True, COLOR_NEON_YELLOW)
            surface.blit(surf, (col_x[idx], y))

        pygame.draw.line(surface, COLOR_PRIMARY_CYAN, (board_rect.left + 20, y + 30), (board_rect.right - 20, y + 30), 2)
        y += 42

        # Draw up to 8 top entries
        for i, entry in enumerate(self.highscores[:8]):
            rank = f"#{i+1:02d}"
            name = entry.get("name", "PILOT")
            score = f"{entry.get('score', 0):,}"
            wave = f"WAVE {entry.get('wave', 1)}"
            date = entry.get("date", "---")

            col = COLOR_NEON_GREEN if i == 0 else COLOR_WHITE
            surface.blit(self.font_small.render(rank, True, COLOR_PRIMARY_CYAN), (col_x[0], y))
            surface.blit(self.font_small.render(name, True, col), (col_x[1], y))
            surface.blit(self.font_small.render(score, True, COLOR_NEON_YELLOW), (col_x[2], y))
            surface.blit(self.font_small.render(wave, True, COLOR_WHITE), (col_x[3], y))
            surface.blit(self.font_small.render(date, True, COLOR_GRAY_LIGHT), (col_x[4], y))
            y += 42

        # Back Button
        mx, my = pygame.mouse.get_pos()
        btn_back = pygame.Rect(WINDOW_WIDTH // 2 - 100, WINDOW_HEIGHT - 90, 200, 44)
        is_hover = btn_back.collidepoint(mx, my)
        pygame.draw.rect(surface, (20, 30, 60) if is_hover else (12, 16, 32), btn_back)
        pygame.draw.rect(surface, COLOR_PRIMARY_CYAN if is_hover else (40, 50, 80), btn_back, width=2 if is_hover else 1)
        b_txt = self.font_body.render("BACK TO MENU", True, COLOR_WHITE if is_hover else COLOR_GRAY_LIGHT)
        surface.blit(b_txt, b_txt.get_rect(center=btn_back.center))

    def _handle_highscores_events(self, event: pygame.event.Event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos
            btn_back = pygame.Rect(WINDOW_WIDTH // 2 - 100, WINDOW_HEIGHT - 90, 200, 44)
            if btn_back.collidepoint(mx, my):
                self.change_scene(SceneType.MENU)
        elif event.type == pygame.KEYDOWN and (event.key == pygame.K_ESCAPE or event.key == pygame.K_SPACE):
            self.change_scene(SceneType.MENU)

    # ----------------------------------------------------
    # SCENE: GAMEPLAY
    # ----------------------------------------------------
    def _init_new_game(self):
        """Initializes a brand-new run of GestureStrike."""
        self.game_state = {
            "player": Player(WINDOW_WIDTH // 2, WINDOW_HEIGHT - 120),
            "particles": ParticleManager(),
            "shake": ScreenShake(),
            "hud": HUD(),
            "player_bullets": [],
            "enemy_bullets": [],
            "enemies": [],
            "powerups": [],
            "smart_bombs": [],
            "active_laser": None,
            "boss": None,
            "wave": 1,
            "score": 0,
            "combo": 0,
            "combo_timer": 0.0,
            "enemies_to_spawn": ENEMY_WAVE_BASE_COUNT,
            "spawn_timer": 1.0,
            "is_wave_transition": False,
            "wave_transition_timer": 0.0,
            "is_paused": False,
            "auto_paused": False
        }
        self.name_entered = False

    def _handle_gameplay_events(self, event: pygame.event.Event):
        if not self.game_state:
            return

        # Toggle Manual Pause with ESC or P
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_ESCAPE, pygame.K_p):
                self.game_state["is_paused"] = not self.game_state["is_paused"]
                self.sounds.play("ui_blip")
            # Live Tuning Hotkeys
            elif event.key == pygame.K_LEFTBRACKET:
                self.tracker.adjust_sensitivity(-0.25)
                self.sounds.play("ui_blip")
                self.game_state["particles"].spawn_floating_text(
                    f"SENSITIVITY: {self.tracker.sensitivity_x:.1f}x",
                    WINDOW_WIDTH - 120, WINDOW_HEIGHT - 240, self.font_small, COLOR_NEON_YELLOW
                )
            elif event.key == pygame.K_RIGHTBRACKET:
                self.tracker.adjust_sensitivity(+0.25)
                self.sounds.play("ui_blip")
                self.game_state["particles"].spawn_floating_text(
                    f"SENSITIVITY: {self.tracker.sensitivity_x:.1f}x",
                    WINDOW_WIDTH - 120, WINDOW_HEIGHT - 240, self.font_small, COLOR_NEON_YELLOW
                )
            elif event.key == pygame.K_SEMICOLON:
                self.tracker.adjust_smoothing(-0.2)
                self.sounds.play("ui_blip")
                self.game_state["particles"].spawn_floating_text(
                    f"CUTOFF: {self.tracker.min_cutoff:.1f}Hz",
                    WINDOW_WIDTH - 120, WINDOW_HEIGHT - 240, self.font_small, COLOR_PRIMARY_CYAN
                )
            elif event.key == pygame.K_QUOTE:
                self.tracker.adjust_smoothing(+0.2)
                self.sounds.play("ui_blip")
                self.game_state["particles"].spawn_floating_text(
                    f"CUTOFF: {self.tracker.min_cutoff:.1f}Hz",
                    WINDOW_WIDTH - 120, WINDOW_HEIGHT - 240, self.font_small, COLOR_PRIMARY_CYAN
                )
            elif event.key == pygame.K_F5:
                self.tracker.save_tuning()
                self.sounds.play("powerup")
                self.game_state["particles"].spawn_floating_text(
                    "SETTINGS SAVED [F5]!",
                    WINDOW_WIDTH - 120, WINDOW_HEIGHT - 240, self.font_body, COLOR_NEON_GREEN
                )

        # Handle pause modal clicks
        if self.game_state["is_paused"] or self.game_state["auto_paused"]:
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mx, my = event.pos
                cx = WINDOW_WIDTH // 2
                cy = WINDOW_HEIGHT // 2
                btn_resume = pygame.Rect(cx - 130, cy + 10, 260, 42)
                btn_restart = pygame.Rect(cx - 130, cy + 62, 260, 42)
                btn_menu = pygame.Rect(cx - 130, cy + 114, 260, 42)

                if btn_resume.collidepoint(mx, my):
                    self.game_state["is_paused"] = False
                    self.game_state["auto_paused"] = False
                    self.sounds.play("ui_blip")
                elif btn_restart.collidepoint(mx, my):
                    self._init_new_game()
                    self.sounds.play("ui_blip")
                elif btn_menu.collidepoint(mx, my):
                    self.change_scene(SceneType.MENU)
            return

        # Keyboard & Mouse manual fire/bomb controls
        if self.keyboard_mode:
            player: Player = self.game_state["player"]
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_b:
                    bomb = player.fire_bomb()
                    if bomb:
                        self.game_state["smart_bombs"].append(bomb)
                        self.game_state["shake"].add_trauma(0.8)
                        self.sounds.play("bomb_blast")
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 3:  # Right click shield
                    player.trigger_shield(True)
                elif event.button == 2:  # Middle click bomb
                    bomb = player.fire_bomb()
                    if bomb:
                        self.game_state["smart_bombs"].append(bomb)
                        self.game_state["shake"].add_trauma(0.8)
                        self.sounds.play("bomb_blast")
            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 3:
                    player.trigger_shield(False)

    def _update_gameplay(self, dt: float):
        if not self.game_state:
            return

        v_state = self.tracker.get_state()
        player: Player = self.game_state["player"]
        particles: ParticleManager = self.game_state["particles"]
        shake: ScreenShake = self.game_state["shake"]

        # Dynamically ensure Gesture Mode starts when camera opens
        if not self.user_toggled_keyboard:
            if v_state.get("camera_available", False):
                self.keyboard_mode = False
            else:
                self.camera_check_timer += dt
                if self.camera_check_timer > 3.0:
                    self.keyboard_mode = True

        # 1. AUTO-PAUSE LOGIC (Hand lost > 1.0 second while in Hand mode)
        if not self.keyboard_mode:
            if v_state.get("is_hand_lost", False):
                self.game_state["auto_paused"] = True
            else:
                if self.game_state["auto_paused"] and v_state.get("hand_detected", False):
                    # Hand returned! Automatically unpause
                    self.game_state["auto_paused"] = False

        if self.game_state["is_paused"] or self.game_state["auto_paused"]:
            return

        # 2. CONTROLS DISPATCH (Hand vs Keyboard/Mouse)
        if not self.keyboard_mode:
            # Map Hand Position (Mirrored, 1€-filtered, and Sensitivity-scaled)
            if v_state.get("hand_detected", False):
                screen_x = v_state.get("screen_x", player.target_x)
                screen_y = v_state.get("screen_y", player.target_y)
                player.set_target(screen_x, screen_y)
            # If hand is lost: HOLD SHIP at last valid position (never snap to center)

            # Gesture Evaluation
            gesture = v_state.get("gesture", HandGesture.NONE)

            # GESTURE: OPEN PALM -> Auto-fire
            if gesture == HandGesture.OPEN_PALM:
                player.trigger_shield(False)
                if player.can_fire():
                    new_bullets = player.fire()
                    self.game_state["player_bullets"].extend(new_bullets)
                    s_name = "triple_shoot" if player.has_triple_shot else "shoot"
                    self.sounds.play(s_name)

            # GESTURE: CLOSED FIST -> Shield
            elif gesture == HandGesture.CLOSED_FIST:
                if player.trigger_shield(True):
                    self.sounds.play("shield_activate")

            # GESTURE: PINCH -> EMP Smart Bomb
            elif gesture == HandGesture.PINCH:
                player.trigger_shield(False)
                bomb = player.fire_bomb()
                if bomb:
                    self.game_state["smart_bombs"].append(bomb)
                    shake.add_trauma(0.8)
                    self.sounds.play("bomb_blast")

            else:
                player.trigger_shield(False)

        else:
            # KEYBOARD & MOUSE CONTROLS
            keys = pygame.key.get_pressed()
            dx = (keys[pygame.K_RIGHT] or keys[pygame.K_d]) - (keys[pygame.K_LEFT] or keys[pygame.K_a])
            dy = (keys[pygame.K_DOWN] or keys[pygame.K_s]) - (keys[pygame.K_UP] or keys[pygame.K_w])
            if dx != 0 or dy != 0:
                player.move_keyboard(dx, dy, dt)
            else:
                # Follow mouse pointer smoothly
                mx, my = pygame.mouse.get_pos()
                player.set_target(mx, my)

            # Fire on SPACE or Left Mouse
            mouse_buttons = pygame.mouse.get_pressed()
            if keys[pygame.K_SPACE] or mouse_buttons[0]:
                if player.can_fire():
                    new_bullets = player.fire()
                    self.game_state["player_bullets"].extend(new_bullets)
                    s_name = "triple_shoot" if player.has_triple_shot else "shoot"
                    self.sounds.play(s_name)

            # Shield on S Key (if not moving down) or Right Mouse
            if mouse_buttons[2]:
                player.trigger_shield(True)
            elif not mouse_buttons[2]:
                player.trigger_shield(False)

        # 3. UPDATE PLAYER & PARTICLES
        player.update(dt, particles)
        particles.update(dt)

        # Combo timer decay
        if self.game_state["combo_timer"] > 0:
            self.game_state["combo_timer"] -= dt
            if self.game_state["combo_timer"] <= 0:
                self.game_state["combo"] = 0

        # Check Player Death
        if not player.alive:
            particles.spawn_explosion(player.x, player.y, count=40, speed_scale=2.0)
            shake.add_trauma(0.9)
            self.sounds.play("explosion")
            self.gameover_score = self.game_state["score"]
            self.gameover_wave = self.game_state["wave"]
            self.change_scene(SceneType.GAMEOVER)
            return

        # 4. UPDATE SMART BOMBS
        for bomb in self.game_state["smart_bombs"]:
            bomb.update(dt)
            # Clear all active enemy bullets
            self.game_state["enemy_bullets"].clear()
            # Damage all active enemies
            for e in self.game_state["enemies"]:
                if e.take_damage(280):
                    self._on_enemy_killed(e)
            # Damage boss if present
            if self.game_state["boss"]:
                if self.game_state["boss"].take_damage(350):
                    self._on_boss_killed()

        self.game_state["smart_bombs"] = [b for b in self.game_state["smart_bombs"] if b.alive]

        # 5. SPAWN WAVE ENEMIES & BOSS
        wave = self.game_state["wave"]
        is_boss_wave = (wave % BOSS_WAVE_INTERVAL == 0)

        if is_boss_wave and self.game_state["boss"] is None and len(self.game_state["enemies"]) == 0:
            # Spawn Boss!
            self.game_state["boss"] = Boss(wave)
            self.sounds.play("boss_warning")
            shake.add_trauma(0.7)

        elif not is_boss_wave and self.game_state["enemies_to_spawn"] > 0:
            self.game_state["spawn_timer"] -= dt
            if self.game_state["spawn_timer"] <= 0:
                self.game_state["spawn_timer"] = random.uniform(0.7, 1.4)
                self._spawn_wave_enemy()
                self.game_state["enemies_to_spawn"] -= 1

        # Check Wave Completion
        if not is_boss_wave and self.game_state["enemies_to_spawn"] <= 0 and len(self.game_state["enemies"]) == 0:
            if not self.game_state["is_wave_transition"]:
                self.game_state["is_wave_transition"] = True
                self.game_state["wave_transition_timer"] = 2.4
                particles.spawn_floating_text(f"WAVE {wave} CLEARED!", WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2 - 40, self.font_header, COLOR_NEON_GREEN)
                self.sounds.play("powerup")

        if self.game_state["is_wave_transition"]:
            self.game_state["wave_transition_timer"] -= dt
            if self.game_state["wave_transition_timer"] <= 0:
                self.game_state["is_wave_transition"] = False
                self.game_state["wave"] += 1
                new_wave = self.game_state["wave"]
                self.game_state["enemies_to_spawn"] = ENEMY_WAVE_BASE_COUNT + (new_wave - 1) * ENEMY_WAVE_INCREMENT
                self.game_state["spawn_timer"] = 1.0

        # 6. UPDATE BOSS (if active)
        if self.game_state["boss"]:
            boss: Boss = self.game_state["boss"]
            b_bullets, b_laser, minion = boss.update_boss(dt, player.x, player.y, particles)
            self.game_state["enemy_bullets"].extend(b_bullets)
            if b_laser:
                self.game_state["active_laser"] = b_laser
                self.sounds.play("boss_hit")
            if minion:
                self.game_state["enemies"].append(minion)

            # Boss collision with player bullets
            for b in self.game_state["player_bullets"]:
                if b.alive and boss.rect.colliderect(b.rect):
                    b.alive = False
                    particles.spawn_explosion(b.x, b.y, count=3, speed_scale=0.5)
                    self.sounds.play("boss_hit")
                    if boss.take_damage(b.damage):
                        self._on_boss_killed()
                        break

            # Boss collision with player
            if boss.alive and boss.rect.colliderect(player.rect):
                if player.take_damage():
                    shake.add_trauma(0.6)
                    self.sounds.play("player_hit")
                    particles.spawn_explosion(player.x, player.y, count=16)

        # 7. UPDATE ACTIVE BOSS LASER
        if self.game_state["active_laser"]:
            laser: BossLaserBeam = self.game_state["active_laser"]
            if laser.update(dt):
                if laser.is_firing and laser.rect.colliderect(player.rect):
                    if player.take_damage():
                        shake.add_trauma(0.7)
                        self.sounds.play("player_hit")
            else:
                self.game_state["active_laser"] = None

        # 8. UPDATE ENEMIES
        for enemy in self.game_state["enemies"]:
            fired = enemy.update(dt, player.x, player.y)
            self.game_state["enemy_bullets"].extend(fired)

            # Collision with player bullets
            for b in self.game_state["player_bullets"]:
                if b.alive and enemy.rect.colliderect(b.rect):
                    b.alive = False
                    particles.spawn_explosion(b.x, b.y, count=4, speed_scale=0.6)
                    self.sounds.play("enemy_hit")
                    if enemy.take_damage(b.damage):
                        self._on_enemy_killed(enemy)
                        break

            # Collision with player
            if enemy.alive and enemy.rect.colliderect(player.rect):
                enemy.alive = False
                particles.spawn_explosion(enemy.x, enemy.y, count=16)
                if player.take_damage():
                    shake.add_trauma(0.5)
                    self.sounds.play("player_hit")
                else:
                    self.sounds.play("shield_hit")

        self.game_state["enemies"] = [e for e in self.game_state["enemies"] if e.alive]

        # 9. UPDATE BULLETS
        for pb in self.game_state["player_bullets"]:
            pb.update(dt)
        self.game_state["player_bullets"] = [b for b in self.game_state["player_bullets"] if b.alive]

        for eb in self.game_state["enemy_bullets"]:
            eb.update(dt)
            # Collision with player shield or hull
            if player.shield_active and eb.alive and player.shield_rect.colliderect(eb.rect):
                eb.alive = False
                player.take_damage()  # Absorb via shield
                self.sounds.play("shield_hit")
                particles.spawn_explosion(eb.x, eb.y, count=4, speed_scale=0.6)

            elif eb.alive and player.rect.colliderect(eb.rect):
                eb.alive = False
                particles.spawn_explosion(player.x, player.y, count=12)
                if player.take_damage():
                    shake.add_trauma(0.5)
                    self.sounds.play("player_hit")

        self.game_state["enemy_bullets"] = [b for b in self.game_state["enemy_bullets"] if b.alive]

        # 10. UPDATE POWER-UPS
        for pup in self.game_state["powerups"]:
            pup.update(dt)
            if pup.rect.colliderect(player.rect):
                pup.alive = False
                player.apply_powerup(pup.ptype)
                self.sounds.play("powerup")
                particles.spawn_floating_text(pup.config["name"], pup.x, pup.y, self.font_body, pup.color)
        self.game_state["powerups"] = [p for p in self.game_state["powerups"] if p.alive]

    def _spawn_wave_enemy(self):
        """Spawns an enemy variant based on wave difficulty."""
        wave = self.game_state["wave"]
        spawn_x = random.uniform(60, WINDOW_WIDTH - 60)
        spawn_y = -40

        # Unlock enemy types progressively
        speed_scale = 1.0 + min(0.6, (wave - 1) * 0.08)
        choices = [ScoutEnemy]
        weights = [60]

        if wave >= 2:
            choices.append(ViperEnemy)
            weights.append(35)
        if wave >= 3:
            choices.append(InterceptorEnemy)
            weights.append(25)
        if wave >= 4:
            choices.append(GunnerEnemy)
            weights.append(20)

        enemy_cls = random.choices(choices, weights=weights)[0]
        self.game_state["enemies"].append(enemy_cls(spawn_x, spawn_y, speed_scale=speed_scale))

    def _on_enemy_killed(self, enemy: Enemy):
        """Handles score, combo calculation, and effects when an enemy is destroyed."""
        player: Player = self.game_state["player"]
        particles: ParticleManager = self.game_state["particles"]

        # Increment combo
        self.game_state["combo"] += 1
        self.game_state["combo_timer"] = COMBO_TIMEOUT
        combo_mult = min(5.0, 1.0 + (self.game_state["combo"] - 1) * 0.5)

        points = int(enemy.score_value * combo_mult * player.score_multiplier)
        self.game_state["score"] += points

        # Explosion and floating text
        particles.spawn_explosion(enemy.x, enemy.y, count=18)
        self.sounds.play("explosion")
        particles.spawn_floating_text(f"+{points}", enemy.x, enemy.y, self.font_small, COLOR_NEON_YELLOW)

        # Power-up drop roll
        pup = enemy.roll_powerup()
        if pup:
            self.game_state["powerups"].append(pup)

    def _on_boss_killed(self):
        """Handles epic multi-explosion sequence upon Dreadnought boss defeat."""
        boss: Boss = self.game_state["boss"]
        particles: ParticleManager = self.game_state["particles"]
        shake: ScreenShake = self.game_state["shake"]

        points = boss.score_value
        self.game_state["score"] += points
        shake.add_trauma(1.0)
        self.sounds.play("bomb_blast")

        # Multi-stage explosions
        for _ in range(5):
            ox = random.uniform(-70, 70)
            oy = random.uniform(-40, 40)
            particles.spawn_explosion(boss.x + ox, boss.y + oy, count=30, speed_scale=1.8)
            particles.spawn_shockwave(boss.x + ox, boss.y + oy, color=COLOR_ACCENT_MAGENTA, max_radius=280.0)

        particles.spawn_floating_text(f"DREADNOUGHT DESTROYED! +{points}", WINDOW_WIDTH // 2, 160, self.font_header, COLOR_NEON_YELLOW)
        self.game_state["boss"] = None
        self.game_state["active_laser"] = None

        # Guarantee multiple power-ups
        for i, ptype in enumerate(["RAPID_FIRE", "TRIPLE_SHOT", "EXTRA_LIFE"]):
            self.game_state["powerups"].append(PowerUp(boss.x - 60 + i * 60, boss.y, ptype))

        # Trigger wave transition
        self.game_state["is_wave_transition"] = True
        self.game_state["wave_transition_timer"] = 3.5

    def _draw_gameplay(self, surface: pygame.Surface):
        if not self.game_state:
            return

        shake: ScreenShake = self.game_state["shake"]
        ox, oy = shake.update(0.016)

        # Render gameplay layer onto game surface (with camera shake)
        game_surf = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)

        # 1. Particles and Trails
        self.game_state["particles"].draw(game_surf)

        # 2. Smart Bomb Waves
        for b in self.game_state["smart_bombs"]:
            b.draw(game_surf)

        # 3. Power-ups
        for p in self.game_state["powerups"]:
            p.draw(game_surf, self.font_small)

        # 4. Active Boss Laser Beam
        if self.game_state["active_laser"]:
            self.game_state["active_laser"].draw(game_surf)

        # 5. Enemies and Boss
        for e in self.game_state["enemies"]:
            e.draw(game_surf)
        if self.game_state["boss"]:
            self.game_state["boss"].draw(game_surf)

        # 6. Bullets
        for pb in self.game_state["player_bullets"]:
            pb.draw(game_surf)
        for eb in self.game_state["enemy_bullets"]:
            eb.draw(game_surf)

        # 7. Player Starship
        player: Player = self.game_state["player"]
        player.draw(game_surf)

        # Blit game surface with shake offset
        surface.blit(game_surf, (ox, oy))

        # 8. HUD LAYER (Always steady, zero camera shake)
        hud: HUD = self.game_state["hud"]
        v_state = self.tracker.get_state()
        boss_active = self.game_state["boss"] is not None
        boss_hp = self.game_state["boss"].hp if boss_active else 0
        boss_max_hp = self.game_state["boss"].max_hp if boss_active else 1
        high_score = self.highscores[0]["score"] if self.highscores else 15000

        hud.draw(
            surface=surface,
            score=self.game_state["score"],
            high_score=high_score,
            lives=player.lives,
            max_lives=player.max_lives,
            shield_energy=player.shield_energy,
            shield_active=player.shield_active,
            bombs=player.bombs,
            wave=self.game_state["wave"],
            combo=self.game_state["combo"],
            combo_timer=self.game_state["combo_timer"],
            max_combo_timer=COMBO_TIMEOUT,
            vision_state=v_state,
            keyboard_mode=self.keyboard_mode,
            is_muted=self.sounds.muted,
            boss_active=boss_active,
            boss_hp=boss_hp,
            boss_max_hp=boss_max_hp
        )

        # 9. PAUSE & AUTO-PAUSE MODALS
        if self.game_state["auto_paused"]:
            self._draw_auto_pause_modal(surface)
        elif self.game_state["is_paused"]:
            self._draw_pause_modal(surface)

    def _draw_pause_modal(self, surface: pygame.Surface):
        """Draws manual pause screen."""
        overlay = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
        overlay.fill((8, 12, 24, 210))
        surface.blit(overlay, (0, 0))

        cx = WINDOW_WIDTH // 2
        cy = WINDOW_HEIGHT // 2

        t_surf = self.font_header.render("SYSTEM PAUSED", True, COLOR_PRIMARY_CYAN)
        surface.blit(t_surf, t_surf.get_rect(center=(cx, cy - 70)))

        mx, my = pygame.mouse.get_pos()
        buttons = [
            (pygame.Rect(cx - 130, cy + 10, 260, 42), "RESUME [ESC]"),
            (pygame.Rect(cx - 130, cy + 62, 260, 42), "RESTART"),
            (pygame.Rect(cx - 130, cy + 114, 260, 42), "MAIN MENU")
        ]

        for rect, label in buttons:
            is_hover = rect.collidepoint(mx, my)
            pygame.draw.rect(surface, (20, 30, 60) if is_hover else (12, 16, 32), rect)
            pygame.draw.rect(surface, COLOR_PRIMARY_CYAN if is_hover else (40, 50, 80), rect, width=2 if is_hover else 1)
            txt = self.font_body.render(label, True, COLOR_WHITE if is_hover else COLOR_GRAY_LIGHT)
            surface.blit(txt, txt.get_rect(center=rect.center))

    def _draw_auto_pause_modal(self, surface: pygame.Surface):
        """Draws Hand Lost Auto-Pause banner."""
        overlay = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
        overlay.fill((10, 10, 20, 220))
        surface.blit(overlay, (0, 0))

        cx = WINDOW_WIDTH // 2
        cy = WINDOW_HEIGHT // 2

        w_surf = self.font_header.render("HAND LOST - AUTO-PAUSED", True, COLOR_ALERT_RED)
        sub_surf = self.font_body.render("Show your hand to camera to continue playing...", True, COLOR_WHITE)
        tip_surf = self.font_small.render("Or press [K] to switch to Keyboard/Mouse Mode", True, COLOR_NEON_YELLOW)

        surface.blit(w_surf, w_surf.get_rect(center=(cx, cy - 40)))
        surface.blit(sub_surf, sub_surf.get_rect(center=(cx, cy + 10)))
        surface.blit(tip_surf, tip_surf.get_rect(center=(cx, cy + 50)))

    # ----------------------------------------------------
    # SCENE: GAME OVER
    # ----------------------------------------------------
    def _draw_gameover(self, surface: pygame.Surface):
        cx = WINDOW_WIDTH // 2
        cy = WINDOW_HEIGHT // 2

        # Header
        h_surf = self.font_title.render("MISSION FAILED", True, COLOR_ALERT_RED)
        surface.blit(h_surf, h_surf.get_rect(center=(cx, 130)))

        # Score Summary Card
        card_rect = pygame.Rect(cx - 220, 180, 440, 280)
        pygame.draw.rect(surface, (14, 20, 36), card_rect)
        pygame.draw.rect(surface, COLOR_ALERT_RED, card_rect, width=2)

        # Stats
        s1 = self.font_body.render(f"FINAL SCORE: {self.gameover_score:,}", True, COLOR_WHITE)
        s2 = self.font_body.render(f"WAVE REACHED: {self.gameover_wave}", True, COLOR_NEON_YELLOW)
        surface.blit(s1, (card_rect.left + 35, card_rect.top + 30))
        surface.blit(s2, (card_rect.left + 35, card_rect.top + 70))

        # Pilot Name Input
        name_prompt = "ENTER PILOT INITIALS:" if not self.name_entered else "SCORE RECORDED!"
        surface.blit(self.font_small.render(name_prompt, True, COLOR_PRIMARY_CYAN), (card_rect.left + 35, card_rect.top + 130))

        input_box = pygame.Rect(card_rect.left + 35, card_rect.top + 160, 240, 40)
        pygame.draw.rect(surface, (25, 35, 60), input_box)
        pygame.draw.rect(surface, COLOR_PRIMARY_CYAN if not self.name_entered else COLOR_NEON_GREEN, input_box, width=2)
        name_surf = self.font_body.render(self.pilot_name + ("_" if int(time.time() * 2) % 2 == 0 and not self.name_entered else ""), True, COLOR_WHITE)
        surface.blit(name_surf, (input_box.left + 12, input_box.top + 8))

        submit_btn = pygame.Rect(input_box.right + 15, input_box.top, 115, 40)
        mx, my = pygame.mouse.get_pos()
        is_sub_hover = submit_btn.collidepoint(mx, my) and not self.name_entered
        pygame.draw.rect(surface, (20, 50, 80) if is_sub_hover else (15, 25, 45), submit_btn)
        pygame.draw.rect(surface, COLOR_PRIMARY_CYAN, submit_btn, width=1)
        btn_txt = self.font_small.render("SAVE", True, COLOR_WHITE)
        surface.blit(btn_txt, btn_txt.get_rect(center=submit_btn.center))

        # Bottom Buttons: PLAY AGAIN and MAIN MENU
        btn_again = pygame.Rect(cx - 220, 490, 210, 48)
        btn_menu = pygame.Rect(cx + 10, 490, 210, 48)

        for rect, label in [(btn_again, "PLAY AGAIN"), (btn_menu, "MAIN MENU")]:
            is_hover = rect.collidepoint(mx, my)
            pygame.draw.rect(surface, (20, 30, 60) if is_hover else (12, 16, 32), rect)
            pygame.draw.rect(surface, COLOR_PRIMARY_CYAN if is_hover else (40, 50, 80), rect, width=2 if is_hover else 1)
            t = self.font_body.render(label, True, COLOR_WHITE if is_hover else COLOR_GRAY_LIGHT)
            surface.blit(t, t.get_rect(center=rect.center))

    def _handle_gameover_events(self, event: pygame.event.Event):
        cx = WINDOW_WIDTH // 2
        card_rect = pygame.Rect(cx - 220, 180, 440, 280)
        input_box = pygame.Rect(card_rect.left + 35, card_rect.top + 160, 240, 40)
        submit_btn = pygame.Rect(input_box.right + 15, input_box.top, 115, 40)

        btn_again = pygame.Rect(cx - 220, 490, 210, 48)
        btn_menu = pygame.Rect(cx + 10, 490, 210, 48)

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos
            if submit_btn.collidepoint(mx, my) and not self.name_entered:
                self._save_highscores(self.pilot_name, self.gameover_score, self.gameover_wave)
                self.name_entered = True
                self.sounds.play("powerup")
            elif btn_again.collidepoint(mx, my):
                if not self.name_entered:
                    self._save_highscores(self.pilot_name, self.gameover_score, self.gameover_wave)
                self._init_new_game()
                self.change_scene(SceneType.GAMEPLAY)
            elif btn_menu.collidepoint(mx, my):
                if not self.name_entered:
                    self._save_highscores(self.pilot_name, self.gameover_score, self.gameover_wave)
                self.change_scene(SceneType.MENU)

        elif event.type == pygame.KEYDOWN:
            if not self.name_entered:
                if event.key == pygame.K_RETURN:
                    self._save_highscores(self.pilot_name, self.gameover_score, self.gameover_wave)
                    self.name_entered = True
                    self.sounds.play("powerup")
                elif event.key == pygame.K_BACKSPACE:
                    self.pilot_name = self.pilot_name[:-1]
                else:
                    if len(self.pilot_name) < 8 and (event.unicode.isalnum() or event.unicode in "-_"):
                        self.pilot_name += event.unicode.upper()
