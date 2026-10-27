"""
Animated Sci-Fi Heads-Up Display (HUD) for GestureStrike.
Renders smooth rolling score counter, life pips, shield energy bar,
EMP bomb charges, wave indicators, boss health bar, combo meter,
live webcam video preview, and gesture status indicators.
"""

import math
import pygame
from typing import Dict, Any, Optional
from config import (
    WINDOW_WIDTH,
    WINDOW_HEIGHT,
    PREVIEW_WIDTH,
    PREVIEW_HEIGHT,
    PREVIEW_MARGIN,
    COLOR_PRIMARY_CYAN,
    COLOR_PRIMARY_BLUE,
    COLOR_ACCENT_MAGENTA,
    COLOR_NEON_GREEN,
    COLOR_NEON_YELLOW,
    COLOR_ALERT_RED,
    COLOR_WHITE,
    COLOR_GRAY_LIGHT,
    COLOR_GRAY_DARK,
    SHIELD_MAX_ENERGY
)
from vision.gesture_recognizer import HandGesture


class HUD:
    """Manages all onscreen UI widgets, status bars, and video preview framing."""

    def __init__(self):
        # Rolling animated score
        self.displayed_score = 0
        self.target_score = 0
        self.pulse_timer = 0.0

        # Fonts (Pygame system fonts for instant cross-platform execution)
        pygame.font.init()
        self.font_large = pygame.font.SysFont("consolas", 28, bold=True)
        self.font_mid = pygame.font.SysFont("consolas", 20, bold=True)
        self.font_small = pygame.font.SysFont("consolas", 14, bold=True)
        self.font_tiny = pygame.font.SysFont("consolas", 11)

    def update(self, dt: float, current_score: int):
        """Smoothly interpolates rolling score toward true score."""
        self.target_score = current_score
        self.pulse_timer += dt * 4.0
        diff = self.target_score - self.displayed_score
        if abs(diff) < 2:
            self.displayed_score = self.target_score
        else:
            self.displayed_score += int(diff * min(1.0, 10.0 * dt))

    def draw(
        self,
        surface: pygame.Surface,
        score: int,
        high_score: int,
        lives: int,
        max_lives: int,
        shield_energy: float,
        shield_active: bool,
        bombs: int,
        wave: int,
        combo: int,
        combo_timer: float,
        max_combo_timer: float,
        vision_state: Dict[str, Any],
        keyboard_mode: bool,
        is_muted: bool,
        boss_active: bool = False,
        boss_hp: int = 0,
        boss_max_hp: int = 1
    ):
        """Renders complete HUD layer."""
        self.update(0.016, score)

        # 1. TOP-LEFT: SCORE, HIGH SCORE, COMBO, LIVES
        self._draw_score_panel(surface, high_score)
        self._draw_lives(surface, lives, max_lives)
        if combo > 1 and combo_timer > 0:
            self._draw_combo_badge(surface, combo, combo_timer, max_combo_timer)

        # 2. TOP-CENTER: WAVE BADGE & BOSS HEALTH BAR
        self._draw_wave_badge(surface, wave)
        if boss_active and boss_max_hp > 0:
            self._draw_boss_bar(surface, boss_hp, boss_max_hp)

        # 3. TOP-RIGHT: SHIELD ENERGY, BOMBS, MODE BADGE
        self._draw_status_meters(surface, shield_energy, shield_active, bombs, keyboard_mode, is_muted)

        # 4. BOTTOM-RIGHT: WEBCAM VIDEO PREVIEW & GESTURE STATUS
        self._draw_vision_panel(surface, vision_state, keyboard_mode)

    def _draw_score_panel(self, surface: pygame.Surface, high_score: int):
        """Draws current score and personal best."""
        # Score header
        score_txt = f"{self.displayed_score:07d}"
        s_surf = self.font_large.render(score_txt, True, COLOR_WHITE)
        surface.blit(s_surf, (24, 20))

        # Glowing accent line
        pygame.draw.line(surface, COLOR_PRIMARY_CYAN, (24, 52), (180, 52), 2)

        # High score label
        best_txt = f"BEST: {max(high_score, self.target_score):07d}"
        b_surf = self.font_tiny.render(best_txt, True, COLOR_GRAY_LIGHT)
        surface.blit(b_surf, (24, 56))

    def _draw_lives(self, surface: pygame.Surface, lives: int, max_lives: int):
        """Draws player life starship icons."""
        start_x = 24
        start_y = 80
        for i in range(max_lives):
            x = start_x + i * 26
            y = start_y
            col = COLOR_PRIMARY_CYAN if i < lives else (40, 50, 70)

            # Mini triangle spaceship icon
            pts = [(x + 8, y), (x, y + 16), (x + 8, y + 12), (x + 16, y + 16)]
            pygame.draw.polygon(surface, col, pts)
            if i < lives:
                pygame.draw.polygon(surface, COLOR_WHITE, pts, width=1)

    def _draw_combo_badge(self, surface: pygame.Surface, combo: int, timer: float, max_timer: float):
        """Draws active combo multiplier and decay bar."""
        mult = min(5.0, 1.0 + (combo - 1) * 0.5)
        txt = f"COMBO x{mult:.1f} ({combo})"
        badge_surf = self.font_mid.render(txt, True, COLOR_NEON_YELLOW)
        surface.blit(badge_surf, (24, 108))

        # Decay bar
        bar_w = 140
        bar_h = 4
        pct = max(0.0, timer / max_timer)
        pygame.draw.rect(surface, COLOR_GRAY_DARK, (24, 134, bar_w, bar_h))
        pygame.draw.rect(surface, COLOR_NEON_YELLOW, (24, 134, int(bar_w * pct), bar_h))

    def _draw_wave_badge(self, surface: pygame.Surface, wave: int):
        """Draws wave indicator badge at top center."""
        txt = f"WAVE {wave}"
        w_surf = self.font_mid.render(txt, True, COLOR_PRIMARY_CYAN)
        w_rect = w_surf.get_rect(center=(WINDOW_WIDTH // 2, 28))

        # Hex / pill background banner
        pad_x = 24
        pad_y = 6
        bg_rect = pygame.Rect(w_rect.left - pad_x, w_rect.top - pad_y, w_rect.width + pad_x * 2, w_rect.height + pad_y * 2)
        bg_surf = pygame.Surface((bg_rect.width, bg_rect.height), pygame.SRCALPHA)
        bg_surf.fill((16, 22, 42, 200))
        pygame.draw.rect(bg_surf, COLOR_PRIMARY_CYAN, (0, 0, bg_rect.width, bg_rect.height), width=1)

        surface.blit(bg_surf, bg_rect)
        surface.blit(w_surf, w_rect)

    def _draw_boss_bar(self, surface: pygame.Surface, hp: int, max_hp: int):
        """Draws cinematic Dreadnought boss health bar."""
        bar_w = 520
        bar_h = 16
        bar_x = (WINDOW_WIDTH - bar_w) // 2
        bar_y = 62

        pct = max(0.0, min(1.0, hp / max_hp))

        # Header label
        b_txt = self.font_small.render("DREADNOUGHT FLAGSHIP [HOSTILE]", True, COLOR_ALERT_RED)
        surface.blit(b_txt, (bar_x, bar_y - 20))

        # HP Text percentage
        pct_txt = self.font_small.render(f"{int(pct * 100)}%", True, COLOR_WHITE)
        surface.blit(pct_txt, (bar_x + bar_w - 40, bar_y - 20))

        # Background track
        pygame.draw.rect(surface, (35, 15, 20), (bar_x, bar_y, bar_w, bar_h))
        # Animated health fill
        pygame.draw.rect(surface, COLOR_ALERT_RED, (bar_x, bar_y, int(bar_w * pct), bar_h))
        # White highlight
        if pct > 0.02:
            pygame.draw.rect(surface, (255, 180, 180), (bar_x, bar_y, int(bar_w * pct), 3))
        # Outer neon border
        pygame.draw.rect(surface, COLOR_ALERT_RED, (bar_x, bar_y, bar_w, bar_h), width=2)

    def _draw_status_meters(
        self,
        surface: pygame.Surface,
        shield_energy: float,
        shield_active: bool,
        bombs: int,
        keyboard_mode: bool,
        is_muted: bool
    ):
        """Draws shield bar, bomb charges, and control mode pill."""
        # 1. SHIELD ENERGY BAR
        bar_w = 180
        bar_h = 14
        bar_x = WINDOW_WIDTH - bar_w - 24
        bar_y = 24

        shield_pct = max(0.0, min(1.0, shield_energy / SHIELD_MAX_ENERGY))
        shield_col = COLOR_PRIMARY_CYAN if shield_energy > 20 else COLOR_ALERT_RED

        s_label = self.font_small.render(f"SHIELD: {int(shield_energy)}%", True, shield_col)
        surface.blit(s_label, (bar_x, bar_y - 18))

        # Bar background
        pygame.draw.rect(surface, COLOR_GRAY_DARK, (bar_x, bar_y, bar_w, bar_h))
        # Active shield pulse highlight
        fill_col = COLOR_WHITE if shield_active else shield_col
        pygame.draw.rect(surface, fill_col, (bar_x, bar_y, int(bar_w * shield_pct), bar_h))
        pygame.draw.rect(surface, shield_col, (bar_x, bar_y, bar_w, bar_h), width=1)

        # 2. EMP BOMB COUNTER
        bomb_y = bar_y + 26
        b_label = self.font_small.render("EMP BOMBS:", True, COLOR_PRIMARY_CYAN)
        surface.blit(b_label, (bar_x, bomb_y))

        for b in range(3):
            bx = bar_x + 95 + b * 22
            by = bomb_y + 7
            if b < bombs:
                pygame.draw.circle(surface, COLOR_PRIMARY_CYAN, (bx, by), 7)
                pygame.draw.circle(surface, COLOR_WHITE, (bx, by), 3)
            else:
                pygame.draw.circle(surface, COLOR_GRAY_DARK, (bx, by), 7, width=1)

        # 3. CONTROL MODE PILL
        mode_y = bomb_y + 28
        mode_txt = "MODE: KEYBOARD [K]" if keyboard_mode else "MODE: HAND AI [K]"
        mode_col = COLOR_NEON_YELLOW if keyboard_mode else COLOR_NEON_GREEN
        m_surf = self.font_tiny.render(mode_txt, True, mode_col)
        surface.blit(m_surf, (bar_x, mode_y))

        # Audio mute indicator
        mute_txt = "AUDIO: MUTED [M]" if is_muted else "AUDIO: ON [M]"
        mute_col = COLOR_ALERT_RED if is_muted else COLOR_GRAY_LIGHT
        mute_surf = self.font_tiny.render(mute_txt, True, mute_col)
        surface.blit(mute_surf, (bar_x, mode_y + 16))

    def _draw_vision_panel(self, surface: pygame.Surface, vision_state: Dict[str, Any], keyboard_mode: bool):
        """Draws real-time webcam preview and telemetry debug overlay in bottom-right corner."""
        preview_x = WINDOW_WIDTH - PREVIEW_WIDTH - PREVIEW_MARGIN
        preview_y = WINDOW_HEIGHT - PREVIEW_HEIGHT - PREVIEW_MARGIN - 42  # Raised slightly to accommodate debug bar

        preview_surf = vision_state.get("preview_surface")
        camera_avail = vision_state.get("camera_available", False)
        hand_detected = vision_state.get("hand_detected", False)
        gesture = vision_state.get("gesture", HandGesture.NONE)
        fps = vision_state.get("fps", 0.0)
        norm_x = vision_state.get("norm_x", 0.5)
        norm_y = vision_state.get("norm_y", 0.5)
        screen_x = vision_state.get("screen_x", WINDOW_WIDTH // 2)
        screen_y = vision_state.get("screen_y", WINDOW_HEIGHT - 120)
        cam_idx = vision_state.get("camera_index", 0)
        backend = vision_state.get("backend", "DSHOW")
        metrics = vision_state.get("metrics", {})

        # 1. TOP DEBUG TELEMETRY STRIP
        debug_h = 36
        debug_y = preview_y - debug_h - 4
        debug_bg = pygame.Surface((PREVIEW_WIDTH, debug_h), pygame.SRCALPHA)
        debug_bg.fill((10, 14, 26, 230))
        surface.blit(debug_bg, (preview_x, debug_y))
        pygame.draw.rect(surface, (30, 45, 75), (preview_x, debug_y, PREVIEW_WIDTH, debug_h), width=1)

        # Line 1: Tracking status & FPS
        track_status = "TRACKING: ACTIVE" if hand_detected else ("CAMERA STANDBY" if camera_avail else "CAMERA OFFLINE")
        track_col = COLOR_NEON_GREEN if hand_detected else (COLOR_NEON_YELLOW if camera_avail else COLOR_ALERT_RED)
        t_surf = self.font_tiny.render(track_status, True, track_col)
        fps_surf = self.font_tiny.render(f"{int(fps)} FPS", True, COLOR_WHITE)
        surface.blit(t_surf, (preview_x + 6, debug_y + 3))
        surface.blit(fps_surf, (preview_x + PREVIEW_WIDTH - fps_surf.get_width() - 6, debug_y + 3))

        # Line 2: Palm Pos (X, Y)
        pos_txt = f"PALM: ({screen_x}, {screen_y}) [{norm_x:.2f}, {norm_y:.2f}]"
        pos_surf = self.font_tiny.render(pos_txt, True, COLOR_PRIMARY_CYAN if hand_detected else COLOR_GRAY_LIGHT)
        surface.blit(pos_surf, (preview_x + 6, debug_y + 18))

        # 2. VIDEO FRAME THUMBNAIL
        if preview_surf and camera_avail:
            surface.blit(preview_surf, (preview_x, preview_y))
        else:
            placeholder = pygame.Surface((PREVIEW_WIDTH, PREVIEW_HEIGHT))
            placeholder.fill((14, 18, 30))
            msg = "WEBCAM OFFLINE" if not camera_avail else "STARTING CAMERA..."
            p_surf = self.font_small.render(msg, True, COLOR_GRAY_LIGHT)
            placeholder.blit(p_surf, p_surf.get_rect(center=(PREVIEW_WIDTH // 2, PREVIEW_HEIGHT // 2)))
            surface.blit(placeholder, (preview_x, preview_y))

        # Sci-Fi Corner Crosshairs and Glowing Border
        border_col = COLOR_PRIMARY_CYAN if hand_detected else (
            COLOR_NEON_YELLOW if keyboard_mode else COLOR_ALERT_RED
        )
        pygame.draw.rect(surface, border_col, (preview_x, preview_y, PREVIEW_WIDTH, PREVIEW_HEIGHT), width=2)

        # Corner bracket flourishes
        bracket_len = 12
        pygame.draw.line(surface, COLOR_WHITE, (preview_x, preview_y), (preview_x + bracket_len, preview_y), 3)
        pygame.draw.line(surface, COLOR_WHITE, (preview_x, preview_y), (preview_x, preview_y + bracket_len), 3)
        pygame.draw.line(surface, COLOR_WHITE, (preview_x + PREVIEW_WIDTH, preview_y), (preview_x + PREVIEW_WIDTH - bracket_len, preview_y), 3)
        pygame.draw.line(surface, COLOR_WHITE, (preview_x + PREVIEW_WIDTH, preview_y), (preview_x + PREVIEW_WIDTH, preview_y + bracket_len), 3)
        pygame.draw.line(surface, COLOR_WHITE, (preview_x, preview_y + PREVIEW_HEIGHT), (preview_x + bracket_len, preview_y + PREVIEW_HEIGHT), 3)
        pygame.draw.line(surface, COLOR_WHITE, (preview_x, preview_y + PREVIEW_HEIGHT), (preview_x, preview_y + PREVIEW_HEIGHT - bracket_len), 3)
        pygame.draw.line(surface, COLOR_WHITE, (preview_x + PREVIEW_WIDTH, preview_y + PREVIEW_HEIGHT), (preview_x + PREVIEW_WIDTH - bracket_len, preview_y + PREVIEW_HEIGHT), 3)
        pygame.draw.line(surface, COLOR_WHITE, (preview_x + PREVIEW_WIDTH, preview_y + PREVIEW_HEIGHT), (preview_x + PREVIEW_WIDTH, preview_y + PREVIEW_HEIGHT - bracket_len), 3)

        # 3. GESTURE STATUS BANNER
        status_h = 24
        status_y = preview_y + PREVIEW_HEIGHT + 2
        status_bg = pygame.Surface((PREVIEW_WIDTH, status_h), pygame.SRCALPHA)
        status_bg.fill((12, 16, 28, 230))
        surface.blit(status_bg, (preview_x, status_y))
        pygame.draw.rect(surface, (30, 45, 75), (preview_x, status_y, PREVIEW_WIDTH, status_h), width=1)

        display_gesture = gesture if not keyboard_mode else "KEYBOARD ACTIVE"
        g_col = COLOR_NEON_GREEN if "OPEN PALM" in display_gesture else (
            COLOR_PRIMARY_CYAN if "SHIELD" in display_gesture else (
                COLOR_ACCENT_MAGENTA if "BOMB" in display_gesture else COLOR_GRAY_LIGHT
            )
        )
        if display_gesture == HandGesture.NONE and not keyboard_mode:
            g_col = COLOR_ALERT_RED

        g_surf = self.font_tiny.render(display_gesture, True, g_col)
        surface.blit(g_surf, (preview_x + 6, status_y + 4))

        # Show pinch / curl metric summary
        if metrics and not keyboard_mode and hand_detected:
            p_val = metrics.get("pinch_ratio", 0.0)
            c_val = metrics.get("avg_curl_ratio", 0.0)
            m_txt = f"P:{p_val:.2f} C:{c_val:.2f}"
            m_surf = self.font_tiny.render(m_txt, True, COLOR_GRAY_LIGHT)
            surface.blit(m_surf, (preview_x + PREVIEW_WIDTH - m_surf.get_width() - 6, status_y + 4))

        # 4. LIVE TUNING PARAMETERS STRIP
        tune_h = 20
        tune_y = status_y + status_h + 2
        tune_bg = pygame.Surface((PREVIEW_WIDTH, tune_h), pygame.SRCALPHA)
        tune_bg.fill((8, 12, 22, 230))
        surface.blit(tune_bg, (preview_x, tune_y))
        pygame.draw.rect(surface, (25, 38, 65), (preview_x, tune_y, PREVIEW_WIDTH, tune_h), width=1)

        sens_x = vision_state.get("sensitivity_x", 2.5)
        cutoff = vision_state.get("min_cutoff", 1.0)
        tune_txt = f"SENS:{sens_x:.1f}x [[]]  CUTOFF:{cutoff:.1f} [;'] [F5]"
        tune_surf = self.font_tiny.render(tune_txt, True, COLOR_NEON_YELLOW)
        surface.blit(tune_surf, (preview_x + 5, tune_y + 3))
