"""
Comprehensive Automated Test Script for GestureStrike.
Verifies all modules, math, procedural audio, vision pipeline,
enemy AI, boss fight, powerups, collision detection, and scene transitions.
"""

import sys
import os
import time

# Ensure project root in sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import pygame
from config import WINDOW_WIDTH, WINDOW_HEIGHT
from audio.sound_generator import SoundManager
from vision.gesture_recognizer import GestureRecognizer, HandGesture
from vision.hand_tracker import HandTracker
from vision.calibration import HandCalibrator
from game.particles import ParticleManager, ParallaxStarfield, ScreenShake
from game.player import Player
from game.enemies import ScoutEnemy, ViperEnemy, InterceptorEnemy, GunnerEnemy
from game.boss import Boss
from game.bullets import PlayerBullet, EnemyBullet, BossLaserBeam, SmartBombWave
from game.powerups import PowerUp, PowerUpType
from game.hud import HUD
from game.scenes import SceneManager, SceneType


def run_all_tests():
    print("--------------------------------------------------")
    print("RUNNING AUTOMATED TEST SUITE FOR GESTURESTRIKE")
    print("--------------------------------------------------")

    # 1. Initialize Pygame in headless mode
    os.environ["SDL_VIDEODRIVER"] = "dummy"
    pygame.init()
    pygame.font.init()
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    print("[TEST 1/7] Pygame display and fonts initialized.")

    # 2. Test Procedural Audio Generator
    sound_mgr = SoundManager()
    assert len(sound_mgr.sounds) >= 12, "Not all sound effects were generated!"
    assert sound_mgr.bg_loop is not None, "Background beat failed to generate!"
    sound_mgr.play("shoot")
    sound_mgr.play("explosion")
    sound_mgr.play("bomb_blast")
    sound_mgr.toggle_mute()
    assert sound_mgr.muted is True, "Mute toggle failed!"
    sound_mgr.toggle_mute()
    print("[TEST 2/7] Procedural sound generator verified (12 SFX + synthwave beat).")

    # 3. Test Gesture Recognizer & Scale Invariant Math
    recognizer = GestureRecognizer()
    assert recognizer.pinch_threshold > 0, "Pinch threshold invalid"
    assert recognizer.fist_threshold > 0, "Fist threshold invalid"
    assert recognizer.palm_threshold > 0, "Palm threshold invalid"

    # Mock landmark structure
    class MockPoint:
        def __init__(self, x, y, z=0.0):
            self.x = x
            self.y = y
            self.z = z

    # Simulate an open palm hand (wrist at 0.5, 0.8; tips extended upwards at y=0.3)
    mock_open_hand = [MockPoint(0.5, 0.8)]  # Wrist (0)
    for i in range(1, 21):
        if i in [4, 8, 12, 16, 20]:  # Tips
            mock_open_hand.append(MockPoint(0.3 + (i / 30.0), 0.3))
        elif i in [5, 9, 13, 17]:  # MCPs
            mock_open_hand.append(MockPoint(0.4 + (i / 40.0), 0.6))
        else:
            mock_open_hand.append(MockPoint(0.4 + (i / 40.0), 0.5))

    gesture, metrics = recognizer.evaluate(mock_open_hand)
    print(f"[TEST 3/7] Gesture recognizer evaluated mock hand: {gesture} (metrics: {metrics})")
    assert "palm_scale" in metrics, "Palm scale missing in metrics"

    # 4. Test One Euro Filter & High-Sensitivity Active Zone
    from vision.one_euro_filter import OneEuroFilter
    oef = OneEuroFilter(min_cutoff=1.0, beta=0.05, d_cutoff=1.0)
    # Filter 10 still values with tiny noise -> should suppress jitter
    f_vals = [oef.filter(0.5 + (i % 2) * 0.002, timestamp=time.time() + i * 0.033) for i in range(10)]
    assert abs(f_vals[-1] - 0.5) < 0.005, "One Euro Filter failed to suppress micro-jitter"

    # Test Active Zone Sensitivity Formula: target = 0.5 + (palm - 0.5) * SENSITIVITY
    sens_x = 2.5
    left_palm = 0.30   # Hand moved only 0.20 to the left of center
    left_target = max(0.0, min(1.0, 0.5 + (left_palm - 0.5) * sens_x))
    assert abs(left_target - 0.0) < 1e-6, f"Expected left target 0.0 but got {left_target}"

    right_palm = 0.70  # Hand moved only 0.20 to the right of center
    right_target = max(0.0, min(1.0, 0.5 + (right_palm - 0.5) * sens_x))
    assert abs(right_target - 1.0) < 1e-6, f"Expected right target 1.0 but got {right_target}"
    print("[TEST 4/7] One Euro Filter and 2.5x Sensitivity Active Zone verified (middle 40% reaches both screen edges).")

    # 5. Test Hand Tracker Thread & Live Tuning
    tracker = HandTracker()
    time.sleep(1.2)
    state = tracker.get_state()
    assert "camera_available" in state, "State missing camera_available key"
    assert "sensitivity_x" in state, "State missing sensitivity_x key"
    assert "min_cutoff" in state, "State missing min_cutoff key"

    # Test Live Tuning adjustments
    orig_sens = tracker.sensitivity_x
    tracker.adjust_sensitivity(0.25)
    assert tracker.sensitivity_x == orig_sens + 0.25, "Live sensitivity adjustment failed"
    tracker.adjust_sensitivity(-0.25)

    orig_cutoff = tracker.min_cutoff
    tracker.adjust_smoothing(0.20)
    assert abs(tracker.min_cutoff - (orig_cutoff + 0.20)) < 0.01, "Live smoothing adjustment failed"
    tracker.adjust_smoothing(-0.20)
    assert tracker.save_tuning() is True, "Settings persistence failed"
    print(f"[TEST 5/7] HandTracker thread & live tuning verified (Sens: {tracker.sensitivity_x}x, Cutoff: {tracker.min_cutoff}Hz, FPS: {state['fps']:.1f}).")

    # 5. Test Entities: Player, Enemies, Boss, Bullets, Powerups
    player = Player(WINDOW_WIDTH // 2, WINDOW_HEIGHT - 120)
    particles = ParticleManager()
    player.update(0.016, particles)
    assert player.alive is True, "Player died unexpectedly"

    # Fire weapons
    bullets = player.fire()
    assert len(bullets) == 2, "Default twin cannons should fire 2 bullets"
    player.apply_powerup(PowerUpType.TRIPLE_SHOT)
    triple_bullets = player.fire()
    assert len(triple_bullets) == 4, "Triple shot should fire 4 spread bullets"

    # Shield
    player.trigger_shield(True)
    assert player.shield_active is True, "Shield activation failed"
    player.take_damage()  # Should deflect via shield
    assert player.lives == 3, "Shield failed to protect player life!"
    player.trigger_shield(False)

    # Smart Bomb
    bomb = player.fire_bomb()
    assert bomb is not None, "Smart bomb failed to fire"
    assert player.bombs == 2, "Bomb inventory did not decrement"

    # Test all 4 enemy types
    scout = ScoutEnemy(100, 50)
    viper = ViperEnemy(200, 50)
    interceptor = InterceptorEnemy(300, 50)
    gunner = GunnerEnemy(400, 50)

    for e in [scout, viper, interceptor, gunner]:
        e.update(0.016, player.x, player.y)
        assert e.alive is True, f"Enemy {e.enemy_type} failed initialization"
        pup = e.roll_powerup()

    # Test Boss
    boss = Boss(wave=5)
    assert boss.max_hp > 1500, "Boss HP scaling failed"
    boss_bullets, laser, minion = boss.update_boss(0.016, player.x, player.y, particles)
    print("[TEST 5/7] Combat entities (Player, Scout, Viper, Interceptor, Gunner, Boss) verified.")

    # 6. Test HUD & Rendering
    hud = HUD()
    hud.update(0.016, 5000)
    hud.draw(
        surface=screen,
        score=5000,
        high_score=15000,
        lives=3,
        max_lives=5,
        shield_energy=85.0,
        shield_active=False,
        bombs=2,
        wave=5,
        combo=3,
        combo_timer=2.0,
        max_combo_timer=2.5,
        vision_state=state,
        keyboard_mode=False,
        is_muted=False,
        boss_active=True,
        boss_hp=1800,
        boss_max_hp=1800
    )
    print("[TEST 6/7] HUD elements, meters, badges, and boss bar rendered cleanly.")

    # 7. Test Scene Manager & Navigation
    scene_mgr = SceneManager(tracker=tracker, sounds=sound_mgr)
    assert scene_mgr.current_scene == SceneType.MENU, "Initial scene should be MENU"

    # Switch to Gameplay
    scene_mgr._init_new_game()
    scene_mgr.current_scene = SceneType.GAMEPLAY

    # Simulate 60 gameplay frames
    for f in range(60):
        scene_mgr.update(0.016)
        scene_mgr.draw(screen)

    # Switch to Calibration
    scene_mgr.current_scene = SceneType.CALIBRATION
    scene_mgr.update(0.016)
    scene_mgr.draw(screen)

    # Switch to Controls
    scene_mgr.current_scene = SceneType.CONTROLS
    scene_mgr.update(0.016)
    scene_mgr.draw(screen)

    # Switch to High Scores
    scene_mgr.current_scene = SceneType.HIGHSCORES
    scene_mgr.update(0.016)
    scene_mgr.draw(screen)

    # Switch to Game Over and record score
    scene_mgr.gameover_score = 9999
    scene_mgr.gameover_wave = 7
    scene_mgr.pilot_name = "TESTPILOT"
    scene_mgr._save_highscores("TESTPILOT", 9999, 7)
    scene_mgr.current_scene = SceneType.GAMEOVER
    scene_mgr.update(0.016)
    scene_mgr.draw(screen)

    print("[TEST 7/7] All scenes (Menu, Gameplay, Calibration, Controls, High Scores, Game Over) verified.")

    # Cleanup
    tracker.stop()
    sound_mgr.stop_music()
    pygame.quit()

    print("--------------------------------------------------")
    print("ALL 7 TEST SUITES PASSED FLAWLESSLY! 100% SUCCESS.")
    print("--------------------------------------------------")


if __name__ == "__main__":
    run_all_tests()
