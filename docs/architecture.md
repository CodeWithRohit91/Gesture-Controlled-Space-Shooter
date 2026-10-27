# GestureStrike - Technical Architecture & Dataflow

## 1. High-Level System Architecture

GestureStrike is designed with a strict multi-layered architecture separating **Computer Vision**, **Procedural Audio**, **Game Physics/Simulation**, and **User Interface/Rendering**.

To guarantee a stable 60 FPS in Pygame without stutter, webcam video acquisition and MediaPipe neural inference are isolated into a dedicated background worker thread, communicating with Pygame through thread-safe locks and atomic state snapshots.

```
+-----------------------------------------------------------------------------------------+
|                                    WEBCAM HARDWARE                                      |
+-----------------------------------------------------------------------------------------+
                                             |
                                             v (30 FPS raw BGR frames)
+-----------------------------------------------------------------------------------------+
|                              BACKGROUND TRACKER THREAD                                  |
|                                                                                         |
|  +---------------------+        +--------------------+        +----------------------+  |
|  |   OpenCV Capture    | -----> |  MediaPipe Hands   | -----> |  Gesture Recognizer  |  |
|  | cv2.flip(frame, 1)  |        | 21 3D Landmarks    |        | Feature Extraction   |  |
|  +---------------------+        +--------------------+        +----------------------+  |
|                                                                           |             |
|                                                                           v             |
|                                      +-----------------------------------------------+  |
|                                      |   Signal Smoothing & Dead Zone Filtering      |  |
|                                      |  - Exponential Moving Average (EMA, alpha=0.28)|  |
|                                      |  - Dead zone radius filter (delta < 0.012)     |  |
|                                      |  - Hand-loss timer (> 1.0s -> Auto-Pause)     |  |
|                                      +-----------------------------------------------+  |
+-----------------------------------------------------------------------------------------+
                                             |
                                             | Thread-Safe State Snapshot (threading.Lock)
                                             v
+-----------------------------------------------------------------------------------------+
|                                MAIN GAME LOOP (60 FPS)                                  |
|                                                                                         |
|  +---------------------+        +--------------------+        +----------------------+  |
|  |     Event Pump      | -----> |  Scene Controller  | -----> |   Pygame Rendering   |  |
|  | Keyboard/Mouse/Quit |        | - Player Physics   |        | - Parallax Stars (3L)|  |
|  +---------------------+        | - Enemy Waves      |        | - Glowing Polygons   |  |
|                                 | - Boss AI Phases   |        | - Particles & Shakes |  |
|                                 | - Bullets & Bombs  |        | - Heads-Up Display   |  |
|                                 +--------------------+        +----------------------+  |
|                                            |                              |             |
|                                            v                              v             |
|                               +-------------------------+    +-----------------------+  |
|                               |  NumPy Audio Synthesizer|    |  Display Window (1280)|  |
|                               |  Procedural SFX & Beats |    |  Back-Buffer Double   |  |
|                               +-------------------------+    +-----------------------+  |
+-----------------------------------------------------------------------------------------+
```

---

## 2. Detailed Data Flow Diagram

```
[Webcam Stream (640x480)]
        |
        v
[OpenCV VideoCapture] -- (Horizontal Flip for Natural Mirroring)
        |
        v
[MediaPipe Hands 3D Landmark Model]
        |
        v
[21 Normalized Landmarks (x, y, z)]
        |
        +---> [Calculate Palm Scale] = dist(WRIST[0], MIDDLE_MCP[9])
        |
        +---> [Calculate Palm Center] = Centroid([WRIST, INDEX_MCP, MIDDLE_MCP, RING_MCP, PINKY_MCP])
        |
        +---> [Calculate Pinch Ratio] = dist(THUMB_TIP[4], INDEX_TIP[8]) / Palm Scale
        |
        +---> [Calculate Finger Curl] = Avg(dist(TIP[i], WRIST[0]) / Palm Scale for i in [8,12,16,20])
        |
        v
[Decision Tree Classifier]
        |
        +---> If Pinch Ratio < Threshold: GESTURE = PINCH (EMP BOMB)
        +---> Else If Curl Ratio < Fist Threshold: GESTURE = CLOSED_FIST (SHIELD)
        +---> Else If Curl Ratio > Palm Threshold: GESTURE = OPEN_PALM (FIRE & MOVE)
        +---> Else: GESTURE = IDLE
        |
        v
[Exponential Moving Average (EMA)]
        Smoothed_X = Alpha * Raw_X + (1 - Alpha) * Prev_X
        Smoothed_Y = Alpha * Raw_Y + (1 - Alpha) * Prev_Y
        |
        v
[Dead Zone Thresholding]
        If hypot(dx, dy) < DEAD_ZONE_RADIUS:
            Suppress movement jitter
        |
        v
[Thread-Safe State Buffer (Shared Lock)]
        |
        v
[Game Controller / Player Entity]
        - Steers spaceship towards mapped screen coordinates
        - Fires dual/triple plasma cannons when OPEN_PALM
        - Activates plasma shield and energy drain when CLOSED_FIST
        - Detonates screen-clearing EMP bomb when PINCH
        - Auto-pauses if no hand detected for > 1.0 second
        |
        v
[Pygame 60 FPS Double Buffer Display]
```

---

## 3. Mathematical Foundations

### 3.1. Scale-Invariant Hand Geometry
Because users can sit near or far from the webcam, raw pixel distances vary widely. To solve this, we compute a stable hand scale reference $S_{palm}$ defined as the Euclidean distance between the wrist ($L_0$) and the middle finger metacarpophalangeal knuckle ($L_9$):

$$S_{palm} = \sqrt{(x_9 - x_0)^2 + (y_9 - y_0)^2 + (z_9 - z_0)^2}$$

All distances (pinch distance, finger extension lengths) are normalized by dividing by $S_{palm}$:

$$R_{pinch} = \frac{\sqrt{(x_8 - x_4)^2 + (y_8 - y_4)^2 + (z_8 - z_4)^2}}{S_{palm}}$$

$$R_{curl} = \frac{1}{4} \sum_{i \in \{8, 12, 16, 20\}} \frac{\sqrt{(x_i - x_0)^2 + (y_i - y_0)^2}}{S_{palm}}$$

This makes gesture detection robust regardless of hand size or camera distance.

### 3.2. One Euro Filter (Adaptive Velocity-Based Smoothing)
To eliminate high-frequency hand tremors while maintaining instantaneous response during fast movements, we implement a **One Euro Filter** (Casiez et al., CHI '12):

1. **Velocity Low-Pass Filter**:
   $$dx = \frac{x(t) - x(t - \Delta t)}{\Delta t}$$
   $$\widehat{dx} = \text{LowPass}(\alpha_d, dx, \widehat{dx}_{prev}), \quad \alpha_d = \frac{1}{1 + \frac{1}{2 \pi \cdot f_{c,d} \cdot \Delta t}}$$

2. **Dynamic Cutoff Frequency Adaptation**:
   $$f_c = f_{c,min} + \beta \cdot |\widehat{dx}|$$
   $$\alpha = \frac{1}{1 + \frac{1}{2 \pi \cdot f_c \cdot \Delta t}}$$

3. **Position Filtering**:
   $$\hat{x} = \alpha \cdot x + (1 - \alpha) \cdot \hat{x}_{prev}$$

When the hand is held still ($|\widehat{dx}| \approx 0$), $f_c = 1.0\text{ Hz}$, eliminating all jitter. When moving rapidly, $f_c$ scales automatically with velocity ($\beta = 0.05$), eliminating tracking lag.

### 3.3. High-Sensitivity Active Zone Mapping
To allow the ship to reach the full screen boundaries without forcing the player to move their hand out of the camera's view, we apply active-zone sensitivity scaling centered around the frame midpoint:

$$\text{Target}_{norm} = \text{clamp}\left(0.5 + (P_{filtered} - 0.5) \cdot \text{SENSITIVITY}, 0.0, 1.0\right)$$

With $\text{SENSITIVITY}_X = 2.5$ and $\text{SENSITIVITY}_Y = 2.0$, moving the hand within the central $\sim 40\%$ of the webcam view spans $100\%$ of the game window.

### 3.4. Frame-Rate Independent Exponential Pursuit
The spaceship tracks the filtered target position smoothly across any display refresh rate using exponential decay:

$$P_{ship}(t + \Delta t) = P_{ship}(t) + \left(P_{target} - P_{ship}(t)\right) \cdot \left(1 - e^{-\text{FOLLOW\_SPEED} \cdot \Delta t}\right)$$

Where $\text{FOLLOW\_SPEED} = 18.0$. If hand tracking is momentarily lost, the target coordinates are locked in place, preventing the ship from jumping or snapping to center.

---

## 4. Audio Synthesis Architecture

The game uses **zero external audio files**, synthesizing all audio on-the-fly with NumPy waveforms:
- **Blaster Fire**: Logarithmic frequency sweep $f(t) = f_{start} \cdot (f_{end}/f_{start})^{t/D}$ with an exponential decay envelope.
- **EMP Bomb Explosion**: Low-frequency sinusoidal sub-bass sweep combined with uniform white noise and 440 Hz resonant ring.
- **Procedural Beat**: A 4-bar 124 BPM synthwave rhythm consisting of a synthesized 808 kick drum, snappy snare, 16th-note hi-hat clicks, and an A-minor rolling bassline.
