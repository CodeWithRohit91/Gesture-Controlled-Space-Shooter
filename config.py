"""
GestureStrike - Game Configuration and Constants
Defines display resolution, colors, gameplay parameters, audio settings,
and default vision thresholds.
"""

import os

# Base paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DOCS_DIR = os.path.join(BASE_DIR, "docs")
HIGHSCORES_FILE = os.path.join(DATA_DIR, "highscores.json")
CALIBRATION_FILE = os.path.join(DATA_DIR, "calibration.json")
SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")

# Ensure required directories exist
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(DOCS_DIR, exist_ok=True)

# Window & Display
WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 720
FPS = 60
WINDOW_TITLE = "GestureStrike - AI Hand-Controlled Space Shooter"

# Color Palette (Dark Neon Sci-Fi Theme)
COLOR_BG_DARK = (10, 11, 24)        # Deep space obsidian/navy
COLOR_BG_DEEP = (16, 18, 38)
COLOR_PRIMARY_CYAN = (0, 240, 255)   # Neon cyan (player / shields)
COLOR_PRIMARY_BLUE = (30, 144, 255)
COLOR_ACCENT_MAGENTA = (255, 0, 128) # Neon magenta (special weapons / boss)
COLOR_ACCENT_PURPLE = (170, 0, 255)
COLOR_NEON_GREEN = (0, 255, 136)     # Power-ups / health / active indicators
COLOR_NEON_YELLOW = (255, 230, 0)    # Warning / score multipliers
COLOR_NEON_ORANGE = (255, 120, 0)    # Explosions / elite enemies
COLOR_ALERT_RED = (255, 45, 65)      # Boss health / damage / warning
COLOR_WHITE = (245, 250, 255)
COLOR_GRAY_LIGHT = (180, 190, 205)
COLOR_GRAY_DARK = (40, 45, 65)
COLOR_OVERLAY_DARK = (10, 12, 22, 210)

# Hand Tracking & Vision Settings
CAMERA_INDEX = 0
WEBCAM_WIDTH = 640
WEBCAM_HEIGHT = 480
PREVIEW_WIDTH = 220
PREVIEW_HEIGHT = 165
PREVIEW_MARGIN = 16

# Sensitivity and Active Zone (Middle portion of camera frame reaches full screen)
SENSITIVITY_X = 2.5          # Default horizontal palm sensitivity (target = 0.5 + (palm-0.5)*SENS)
SENSITIVITY_Y = 2.0          # Default vertical palm sensitivity
DEAD_ZONE_RADIUS = 0.005     # 0.5% normalized dead zone to eliminate resting hand micro-jitter
HAND_LOST_TIMEOUT = 1.0      # Auto-pause after 1.0 second of no hand detected

# One Euro Filter Parameters (Adaptive velocity-based low-pass smoothing)
ONE_EURO_MIN_CUTOFF = 1.0    # Lower = smoother when holding still (default: 1.0 Hz)
ONE_EURO_BETA = 0.05         # Higher = faster cutoff ramp when moving fast (zero lag)
ONE_EURO_D_CUTOFF = 1.0      # Derivative cutoff frequency (1.0 Hz)

# Frame-rate Independent Exponential Pursuit
FOLLOW_SPEED = 18.0          # Ship position interpolation rate: ship += (target - ship) * (1 - exp(-FOLLOW_SPEED * dt))

# MediaPipe Confidence Thresholds
MIN_DETECTION_CONFIDENCE = 0.5
MIN_TRACKING_CONFIDENCE = 0.5
MODEL_COMPLEXITY = 0         # 0 = Fastest, ultra-low latency model for hand landmarks

# Gesture Recognition Thresholds (Normalized by palm scale: distance between Wrist and Middle Knuckle)
DEFAULT_PINCH_THRESHOLD = 0.40   # Distance(Thumb Tip, Index Tip) / Palm Scale (< 0.40 = Pinch)
DEFAULT_FIST_THRESHOLD = 0.88    # Average Distance(Fingertips, Wrist) / Palm Scale (< 0.88 = Fist)
DEFAULT_PALM_THRESHOLD = 1.25    # Average Distance(Fingertips, Wrist) / Palm Scale (>= 1.25 = Open Palm)

# Player Configuration
PLAYER_SPEED = 12.0              # Max tracking move speed when mapped or keyboard
PLAYER_START_LIVES = 3
PLAYER_MAX_LIVES = 5
PLAYER_INVULN_TIME = 2.0         # Seconds of invulnerability after being hit
PLAYER_WIDTH = 54
PLAYER_HEIGHT = 62

# Player Weapons & Shield
FIRE_COOLDOWN_NORMAL = 0.16      # Seconds between shots in normal fire
FIRE_COOLDOWN_RAPID = 0.08       # Rapid fire powerup cooldown
TRIPLE_SHOT_ANGLE = 15           # Spread angle in degrees for triple shot
SHIELD_MAX_ENERGY = 100.0        # Max shield energy pool
SHIELD_DRAIN_RATE = 28.0         # Energy drained per second while shield active
SHIELD_RECHARGE_RATE = 18.0      # Energy recharged per second while inactive
SHIELD_COOLDOWN = 1.2            # Cooldown delay before recharging starts
MAX_BOMBS = 3                    # Starting and max EMP bombs

# Parallax Starfield
STARFIELD_LAYERS = [
    {"count": 75, "speed": 0.6, "size": 1.2, "color": (100, 115, 150)}, # Distant faint stars
    {"count": 45, "speed": 1.6, "size": 2.0, "color": (160, 190, 230)}, # Mid stars
    {"count": 25, "speed": 3.2, "size": 2.8, "color": (210, 240, 255)}  # Foreground bright stars
]

# Audio Settings
AUDIO_SAMPLE_RATE = 44100
AUDIO_CHANNELS = 2
AUDIO_BUFFER = 512
DEFAULT_SFX_VOLUME = 0.75
DEFAULT_MUSIC_VOLUME = 0.50

# Game Balance
ENEMY_WAVE_BASE_COUNT = 8
ENEMY_WAVE_INCREMENT = 3
BOSS_WAVE_INTERVAL = 5           # Boss appears every 5 waves (Wave 5, 10, 15...)
COMBO_TIMEOUT = 2.5              # Seconds without a kill before combo resets
MAX_COMBO_MULTIPLIER = 5.0

# Dynamic Settings Persistence Helpers
def load_runtime_settings():
    """Loads custom sensitivity and filter settings from data/settings.json if present."""
    import json
    settings = {
        "sensitivity_x": SENSITIVITY_X,
        "sensitivity_y": SENSITIVITY_Y,
        "min_cutoff": ONE_EURO_MIN_CUTOFF,
        "beta": ONE_EURO_BETA,
        "follow_speed": FOLLOW_SPEED
    }
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r") as f:
                data = json.load(f)
                settings["sensitivity_x"] = float(data.get("sensitivity_x", SENSITIVITY_X))
                settings["sensitivity_y"] = float(data.get("sensitivity_y", SENSITIVITY_Y))
                settings["min_cutoff"] = float(data.get("min_cutoff", ONE_EURO_MIN_CUTOFF))
                settings["beta"] = float(data.get("beta", ONE_EURO_BETA))
                settings["follow_speed"] = float(data.get("follow_speed", FOLLOW_SPEED))
        except Exception as e:
            print(f"[Config] Error loading settings.json: {e}")
    return settings


def save_runtime_settings(settings):
    """Saves live-tuned parameters to data/settings.json."""
    import json
    try:
        with open(SETTINGS_FILE, "w") as f:
            json.dump(settings, f, indent=2)
        print(f"[Config] Settings saved to {SETTINGS_FILE}: {settings}")
        return True
    except Exception as e:
        print(f"[Config] Error saving settings: {e}")
        return False

