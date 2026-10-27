# GestureStrike 🚀
### AI-Powered Hand-Controlled Space Shooter

[![Python](https://img.shields.io/badge/Python-3.10%20--%203.12-blue.svg)](https://www.python.org/)
[![Pygame](https://img.shields.io/badge/Pygame-2.6.0-green.svg)](https://www.pygame.org/)
[![MediaPipe](https://img.shields.io/badge/MediaPipe-0.10.14-orange.svg)](https://mediapipe.dev/)
[![OpenCV](https://img.shields.io/badge/OpenCV-4.10.0-red.svg)](https://opencv.org/)
[![NumPy](https://img.shields.io/badge/NumPy-1.26.4-lightblue.svg)](https://numpy.org/)

**GestureStrike** is a modern, polished arcade space combat shooter built in Python where the player steers the spaceship and activates special weapons live through hand gestures captured by their webcam.

Designed as an exemplary college computer science / AI & computer vision engineering project, GestureStrike demonstrates **real-time computer vision**, **multithreaded 60 FPS asynchronous processing**, **signal filtering (EMA + Dead Zones)**, **procedural vector graphics**, and **100% procedural mathematical audio synthesis with NumPy** (zero external image or sound files required!).

---

## 📸 Visual Showcase & UI Overview

```
+-----------------------------------------------------------------------------------------+
| [0015400]                     WAVE 05 - BOSS ENCOUNTER               SHIELD: 85% [====] |
| BEST: 0024800                                                        EMP BOMBS: (3)     |
| <^> <^> <^>                                                          MODE: HAND AI [K]  |
| COMBO x2.5 [====  ]                                                  AUDIO: ON [M]      |
|                                                                                         |
|                    [==== DREADNOUGHT FLAGSHIP [HOSTILE] 74% ====]                       |
|                                                                                         |
|                                      / \                                                |
|                                    <| o |>   (Boss Flagship)                            |
|                                     \---/                                               |
|                                       |                                                 |
|                                    |  |  |   (Boss Laser & Spiral Barrage)              |
|                                                                                         |
|                                                                                         |
|                      | |   | |               +-----------------------+                  |
|                      | |   | |               | [ WEBCAM LIVE HUD ]   |                  |
|                                              |                       |                  |
|                                              |   (Hand Skeleton)     |                  |
|                                              |                       |                  |
|                            / \               +-----------------------+                  |
|                           /---\              | OPEN PALM (FIRE) 30FPS|                  |
|                     (Player Spaceship)       +-----------------------+                  |
+-----------------------------------------------------------------------------------------+
```

---

## 🌟 Key Features

1. **Live Webcam AI Hand Control**:
   - Palm center mapped directly to screen coordinates with automatic horizontal mirroring.
   - **Exponential Moving Average (EMA)** smoothing filter eliminates tracking trembling.
   - **Dead Zone Filtering** prevents micro-jitter when holding the hand steady.
   - **Auto-Pause**: If the hand is lost for more than 1.0 second, the game auto-pauses with the prompt *"Show your hand to continue"*.

2. **Multithreaded Decoupled Vision Architecture**:
   - Webcam capture and MediaPipe neural inference run in an isolated worker thread.
   - The Pygame rendering loop stays locked at a silky-smooth **60 FPS**.

3. **100% Self-Contained (Zero External Assets)**:
   - All graphics are drawn with Pygame geometric vector shapes, glow gradients, additive blend halos, and particle emitters.
   - All sound effects (lasers, explosions, EMP blasts, boss siren, power-ups) and a looping 124 BPM electronic synthwave beat are procedurally synthesized using NumPy mathematical functions.

4. **Tactical Enemy Wave System**:
   - **Scout**: High-speed straight dive-bomber.
   - **Viper**: Sinusoidal zigzag flanker.
   - **Interceptor**: Player-homing pursuit assault craft.
   - **Gunner**: Armored heavy platform that aims and fires plasma bolts.
   - **Dreadnought Flagship Boss** every 5 waves with a dedicated health bar and 3 distinct attack phases (twin broadside cannons, spiral reactor burst + drone escort, and charged apocalyptic laser beam).

5. **Power-Ups & Combo Multiplier**:
   - Drops: Rapid Fire, Triple Shot, Extra Life, and 2X Score Multipliers.
   - Chaining enemy kills without getting hit builds up to a **5.0x Combo Multiplier**.

6. **Interactive Calibration & Hall of Fame**:
   - In-game Calibration screen samples your Open Palm and Closed Fist to customize detection thresholds for your hand size and room lighting.
   - Local JSON-backed High Scores leaderboard (`data/highscores.json`) with pilot initial entry.

7. **Fail-Safe Fallback**:
   - Press **`K`** anytime to toggle Keyboard & Mouse mode if no webcam is available or if camera is busy.

---

## 🎮 Controls Reference

| Action | Hand Gesture (Webcam) | Keyboard & Mouse Fallback |
| :--- | :--- | :--- |
| **Steer Spaceship** | Move hand across camera frame | **WASD** / **Arrow Keys** or **Mouse** |
| **Primary Lasers** | **OPEN PALM** (Fingers spread open) | **SPACEBAR** or **Left Mouse Click** |
| **Plasma Shield** | **CLOSED FIST** (Fingers curled into fist) | **S Key** or **Right Mouse Click** |
| **EMP Smart Bomb** | **PINCH** (Thumb tip touching Index tip) | **B Key** or **Middle Mouse Click** |
| **Auto-Pause** | Hide hand for > 1 second | **P Key** or **ESC Key** to pause |
| **Toggle Controls** | Press **`K`** | Press **`K`** |
| **Toggle Audio** | Press **`M`** | Press **`M`** |
| **Live Sensitivity Tuning** | Press **`[`** / **`]`** (Decrease / Increase) | Press **`[`** / **`]`** |
| **Live Smoothing Tuning** | Press **`;`** / **`'`** (Decrease / Increase Cutoff) | Press **`;`** / **`'`** |
| **Save Settings** | Press **`F5`** (Persists to `data/settings.json`) | Press **`F5`** |

---

## 🔬 How the Gesture Recognition Works

MediaPipe Hands outputs 21 3D landmarks ($L_0$ to $L_{20}$). GestureStrike classifies gestures using scale-invariant biomechanical geometry:

```
                  [8] INDEX_TIP        [12] MIDDLE_TIP
                     \                     /
            [7] DIP   \                   /   [16] RING_TIP
                \      \                 /        /
         [6] PIP \      \               /        /   [20] PINKY_TIP
                  \      \             /        /        /
            [5] MCP -------\----------/--------/-------/
                            \        /
       [4] THUMB_TIP         \      /
             |                \    /
       [3] THUMB_IP            \  /
             |                  \/
       [2] THUMB_MCP       [0] WRIST
             |
       [1] THUMB_CMC
```

1. **Palm Center Tracking**:
   Instead of using a single knuckle that moves when fingers flex, the tracking center is the centroid of the base knuckles:
   $$\text{Palm Center} = \frac{1}{5} \sum_{i \in \{0, 5, 9, 13, 17\}} L_i$$

2. **Hand Scale Normalization ($S_{palm}$)**:
   The Euclidean distance between the Wrist ($L_0$) and Middle Knuckle ($L_9$) defines the palm scale:
   $$S_{palm} = \|L_9 - L_0\|$$
   Dividing all measured distances by $S_{palm}$ ensures gestures work identically whether you sit close or far from the webcam.

3. **Gesture Classification Decision Tree**:
   - **PINCH (EMP Bomb)**: Normalized distance between Thumb Tip ($L_4$) and Index Tip ($L_8$) drops below threshold ($R_{pinch} < 0.38$).
   - **CLOSED FIST (Shield)**: Average distance from fingertips ($L_8, L_{12}, L_{16}, L_{20}$) to the wrist drops below fist threshold ($R_{curl} < 0.85$).
   - **OPEN PALM (Fire & Steer)**: At least 3 fingers are extended ($Tip$ distance to wrist > $PIP$ distance) and $R_{curl} \ge 1.35$.
   - **IDLE**: Neutral hand posture steers without firing.

---

## 📦 Project Structure

```
gesturestrike/
├── main.py                  # Main application entry point & 60 FPS game loop
├── config.py                # Global configurations, speeds, colors, and balance
├── requirements.txt         # Pinned production dependencies
├── README.md                # Project documentation & presentation guide
├── docs/
│   └── architecture.md      # Technical architecture & text flow diagrams
├── data/
│   ├── highscores.json      # Persistent galactic pilot leaderboard
│   └── calibration.json     # Saved user-calibrated gesture thresholds
├── audio/
│   ├── __init__.py
│   └── sound_generator.py   # Procedural NumPy audio synthesizer & synthwave beat
├── vision/
│   ├── __init__.py
│   ├── hand_tracker.py      # Background worker thread & OpenCV video pipeline
│   ├── gesture_recognizer.py# Landmark biomechanical classifier & math
│   └── calibration.py       # Interactive user calibration state machine
└── game/
    ├── __init__.py
    ├── player.py            # Spaceship entity, shields, cannons, and thrusters
    ├── enemies.py           # Scout, Viper, Interceptor, and Gunner enemy AI
    ├── boss.py              # Multi-phase Dreadnought Flagship encounter
    ├── bullets.py           # Glowing plasma bolts, laser beams, and EMP waves
    ├── powerups.py          # Collectible drop system
    ├── particles.py         # Particle explosions, engine smoke, starfield, shake
    ├── hud.py               # Heads-up display & live webcam preview framing
    └── scenes.py            # Menu, Calibration, Controls, High Scores, Game Loop
```

---

## 🚀 Installation & Running

### Prerequisites
- Python **3.10 to 3.12** installed (Tested and verified on Python 3.11.9).
- A standard USB webcam or built-in laptop camera.

### Step-by-Step Setup

1. **Clone or Download the Repository**:
   ```bash
   cd "c:\Users\HP\OneDrive\Desktop\python project"
   ```

2. **Create and Activate a Virtual Environment** (Recommended):
   ```bash
   # Windows PowerShell
   py -3.11 -m venv venv
   .\venv\Scripts\Activate.ps1
   ```

3. **Install Pinned Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Launch GestureStrike**:
   ```bash
   python main.py
   ```

*(You can also run directly from the package folder: `python gesturestrike/main.py`)*

---

## 🎓 College Project Presentation Points

When explaining this project to professors, evaluators, or classmates:

1. **Concurrency & Threading**:
   - Explain how video capture is CPU/IO-bound while Pygame rendering is GPU/display-bound.
   - Point to `vision/hand_tracker.py` to show how `threading.Lock` protects the shared state without blocking either thread.
2. **Signal Processing & Filter Theory**:
   - Discuss **Exponential Moving Average (EMA)** smoothing vs simple averaging.
   - Discuss **Dead Zone Thresholding** and how it prevents quantization noise from moving the spaceship.
3. **Biomechanical Normalization**:
   - Explain why raw pixel distances fail when players move closer or further from the camera, and how normalizing by the distance between Wrist ($L_0$) and Middle Knuckle ($L_9$) makes the system robust and scale-invariant.
4. **Procedural Media Generation**:
   - Highlight that zero downloaded sprites, WAV, or MP3 files are used.
   - Explain how trigonometric sine waves, white noise generators, and frequency modulations in NumPy generate genuine 80s arcade blasters and synthwave drum tracks.

---

## 📄 License
GestureStrike is open source and distributed under the MIT License.
Built with ❤️ for collegiate software engineering and computer vision demonstrations.
