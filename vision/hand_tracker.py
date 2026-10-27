"""
Multithreaded Hand Tracking Engine for GestureStrike.
Runs OpenCV video capture and MediaPipe Hands in an asynchronous worker thread
to ensure zero frame-drops in Pygame's 60 FPS game loop.
Features exponential moving average smoothing, dead-zone filtering,
hand-loss auto-pause detection, and HUD video preview generation.
"""

import time
import threading
import math
import cv2
import mediapipe as mp
import pygame
import numpy as np
from typing import Tuple, Optional, List, Dict, Any

from config import (
    CAMERA_INDEX,
    WEBCAM_WIDTH,
    WEBCAM_HEIGHT,
    PREVIEW_WIDTH,
    PREVIEW_HEIGHT,
    DEAD_ZONE_RADIUS,
    HAND_LOST_TIMEOUT,
    SENSITIVITY_X,
    SENSITIVITY_Y,
    ONE_EURO_MIN_CUTOFF,
    ONE_EURO_BETA,
    ONE_EURO_D_CUTOFF,
    FOLLOW_SPEED,
    MIN_DETECTION_CONFIDENCE,
    MIN_TRACKING_CONFIDENCE,
    MODEL_COMPLEXITY,
    WINDOW_WIDTH,
    WINDOW_HEIGHT,
    load_runtime_settings,
    save_runtime_settings
)
from vision.gesture_recognizer import GestureRecognizer, HandGesture
from vision.one_euro_filter import OneEuroFilter


class HandTracker:
    """
    Spawns and manages a background thread running MediaPipe Hands on live webcam feed.
    Provides thread-safe getters for smoothed screen coordinates and detected gestures.
    Implements 1€ Filter for adaptive jitter-free low-latency tracking.
    """

    def __init__(self, camera_index: int = CAMERA_INDEX, recognizer: Optional[GestureRecognizer] = None):
        self.camera_index = camera_index
        self.active_camera_index = -1
        self.backend_name = "NONE"
        self.recognizer = recognizer if recognizer else GestureRecognizer()

        # Load persistent runtime settings
        settings = load_runtime_settings()
        self.sensitivity_x = settings.get("sensitivity_x", SENSITIVITY_X)
        self.sensitivity_y = settings.get("sensitivity_y", SENSITIVITY_Y)
        self.min_cutoff = settings.get("min_cutoff", ONE_EURO_MIN_CUTOFF)
        self.beta = settings.get("beta", ONE_EURO_BETA)
        self.follow_speed = settings.get("follow_speed", FOLLOW_SPEED)

        # Separate One Euro Filter instances for X and Y coordinates
        self.filter_x = OneEuroFilter(min_cutoff=self.min_cutoff, beta=self.beta, d_cutoff=ONE_EURO_D_CUTOFF)
        self.filter_y = OneEuroFilter(min_cutoff=self.min_cutoff, beta=self.beta, d_cutoff=ONE_EURO_D_CUTOFF)

        # Thread synchronization lock
        self.lock = threading.Lock()
        self.running = False
        self.thread: Optional[threading.Thread] = None

        # State flags
        self.camera_available = False
        self.hand_detected = False
        self.is_hand_lost = False
        self.last_seen_timestamp = time.time()
        self.fps = 0.0

        # Raw & Smoothed Coordinates (Stored in screen & normalized space)
        self.raw_x = 0.5
        self.raw_y = 0.5
        self.smoothed_x = 0.5
        self.smoothed_y = 0.5
        self.screen_x = WINDOW_WIDTH // 2
        self.screen_y = WINDOW_HEIGHT - 120

        # Gesture & Landmarks
        self.current_gesture = HandGesture.NONE
        self.current_metrics: Dict[str, float] = {}
        self.raw_landmarks: Optional[List[Any]] = None

        # HUD Preview Surface
        self.preview_surface: Optional[pygame.Surface] = None

        # MediaPipe initialization components
        self.mp_hands = mp.solutions.hands
        self.mp_draw = mp.solutions.drawing_utils
        self.mp_drawing_styles = mp.solutions.drawing_styles

        # Start tracking thread
        self.start()

    def start(self):
        """Starts the background hand tracking thread."""
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.thread.start()

    def stop(self):
        """Stops the worker thread and releases resources."""
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.5)

    def _open_camera_auto(self) -> Tuple[Optional[cv2.VideoCapture], int, str]:
        """
        Attempts to open camera indexes 0, 1, and 2 using DirectShow on Windows,
        falling back to default backend. Verifies cap.isOpened() and valid frame read.
        """
        print("[HandTracker] Auto-detecting camera on indexes 0, 1, 2...", flush=True)
        candidates = []
        for idx in [self.camera_index, 0, 1, 2]:
            if (idx, cv2.CAP_DSHOW, "CAP_DSHOW") not in candidates:
                candidates.append((idx, cv2.CAP_DSHOW, "CAP_DSHOW"))
            if (idx, None, "DEFAULT") not in candidates:
                candidates.append((idx, None, "DEFAULT"))

        for idx, backend, name in candidates:
            try:
                cap = cv2.VideoCapture(idx, backend) if backend is not None else cv2.VideoCapture(idx)
                if cap.isOpened():
                    ret, test_frame = cap.read()
                    if ret and test_frame is not None and test_frame.size > 0:
                        h, w = test_frame.shape[:2]
                        print(f"[HandTracker] Successfully opened Camera index {idx} with {name} ({w}x{h}).", flush=True)
                        return cap, idx, name
                    else:
                        cap.release()
                else:
                    cap.release()
            except Exception:
                pass

        print("[HandTracker] ERROR: No working camera detected on indexes 0, 1, 2! Falling back to Keyboard Mode.", flush=True)
        return None, -1, "NONE"

    def _worker_loop(self):
        """Dedicated background thread loop for webcam and hand landmark inference."""
        cap = None
        try:
            cap, active_idx, b_name = self._open_camera_auto()

            if cap is None or not cap.isOpened():
                with self.lock:
                    self.camera_available = False
                return

            with self.lock:
                self.camera_available = True
                self.active_camera_index = active_idx
                self.backend_name = b_name

            # Configure low-latency camera properties
            try:
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            except Exception:
                pass
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, WEBCAM_WIDTH)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, WEBCAM_HEIGHT)
            cap.set(cv2.CAP_PROP_FPS, 30)

            # Initialize MediaPipe Hands solution with ultra-fast model_complexity=0
            with self.mp_hands.Hands(
                static_image_mode=False,
                max_num_hands=1,
                model_complexity=MODEL_COMPLEXITY,
                min_detection_confidence=MIN_DETECTION_CONFIDENCE,
                min_tracking_confidence=MIN_TRACKING_CONFIDENCE
            ) as hands:
                prev_time = time.time()

                while self.running:
                    # Drop stale buffer frames to guarantee lowest possible latency
                    cap.grab()
                    success, frame = cap.read()
                    if not success or frame is None:
                        time.sleep(0.005)
                        continue

                    # Mirror the webcam image horizontally so motion feels intuitive (like a mirror)
                    frame = cv2.flip(frame, 1)

                    # Calculate capture FPS
                    curr_time = time.time()
                    dt = curr_time - prev_time
                    prev_time = curr_time
                    fps_val = 1.0 / dt if dt > 0 else 30.0

                    # Convert BGR to RGB for MediaPipe
                    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    results = hands.process(rgb_frame)

                    hand_found = False
                    landmarks_list = None
                    gesture = HandGesture.NONE
                    metrics = {}
                    palm_nx = self.smoothed_x
                    palm_ny = self.smoothed_y

                    if results.multi_hand_landmarks:
                        hand_found = True
                        hand_landmarks = results.multi_hand_landmarks[0]
                        landmarks_list = hand_landmarks.landmark

                        # Calculate palm center (Centroid of Wrist [0] and MCP Knuckles [5, 9, 13, 17])
                        palm_nx, palm_ny = self.recognizer.calculate_palm_center(landmarks_list)

                        # Classify gesture
                        gesture, metrics = self.recognizer.evaluate(landmarks_list)

                        # Draw landmarks and connections on preview frame
                        self.mp_draw.draw_landmarks(
                            frame,
                            hand_landmarks,
                            self.mp_hands.HAND_CONNECTIONS,
                            self.mp_drawing_styles.get_default_hand_landmarks_style(),
                            self.mp_drawing_styles.get_default_hand_connections_style()
                        )

                    # Resize frame for HUD preview thumbnail
                    preview_bgr = cv2.resize(frame, (PREVIEW_WIDTH, PREVIEW_HEIGHT))
                    preview_rgb = cv2.cvtColor(preview_bgr, cv2.COLOR_BGR2RGB)
                    preview_surf = pygame.surfarray.make_surface(np.rot90(preview_rgb))

                    # Update thread-safe variables
                    now = time.time()
                    with self.lock:
                        self.fps = fps_val
                        self.raw_landmarks = landmarks_list
                        self.current_gesture = gesture
                        self.current_metrics = metrics
                        self.preview_surface = preview_surf

                        if hand_found:
                            self.hand_detected = True
                            self.last_seen_timestamp = now
                            self.is_hand_lost = False

                            # 1. Apply One Euro Filter to raw palm center
                            fx = self.filter_x.filter(palm_nx, now)
                            fy = self.filter_y.filter(palm_ny, now)

                            # 2. Dead Zone Filtering (0.5% threshold prevents resting micro-jitter)
                            dx = fx - self.smoothed_x
                            dy = fy - self.smoothed_y
                            if math.hypot(dx, dy) > DEAD_ZONE_RADIUS:
                                self.smoothed_x = fx
                                self.smoothed_y = fy

                            self.raw_x = palm_nx
                            self.raw_y = palm_ny

                            # 3. High-Sensitivity Mapping:
                            # target = 0.5 + (palm - 0.5) * SENSITIVITY, then clamp 0..1
                            target_norm_x = np.clip(0.5 + (self.smoothed_x - 0.5) * self.sensitivity_x, 0.0, 1.0)
                            target_norm_y = np.clip(0.5 + (self.smoothed_y - 0.5) * self.sensitivity_y, 0.0, 1.0)

                            self.screen_x = int(target_norm_x * WINDOW_WIDTH)
                            self.screen_y = int(target_norm_y * WINDOW_HEIGHT)

                        else:
                            self.hand_detected = False
                            if now - self.last_seen_timestamp > HAND_LOST_TIMEOUT:
                                self.is_hand_lost = True
                            # CRITICAL: Keep screen_x and screen_y at their last positions
                            # (Never snap to center when hand is lost!)

                    time.sleep(0.003)

        except Exception as e:
            print(f"[HandTracker] Error in tracker thread: {e}")
            with self.lock:
                self.camera_available = False
        finally:
            if cap is not None:
                cap.release()
            print("[HandTracker] Background thread stopped and camera released.")

    def adjust_sensitivity(self, delta: float):
        """Increases or decreases sensitivity live."""
        with self.lock:
            self.sensitivity_x = round(max(1.0, min(5.0, self.sensitivity_x + delta)), 2)
            self.sensitivity_y = round(max(1.0, min(5.0, self.sensitivity_y + delta * 0.8)), 2)
            print(f"[HandTracker] Sensitivity adjusted -> X: {self.sensitivity_x:.2f}, Y: {self.sensitivity_y:.2f}")

    def adjust_smoothing(self, delta_cutoff: float):
        """Increases or decreases One Euro Filter min_cutoff live."""
        with self.lock:
            self.min_cutoff = round(max(0.2, min(5.0, self.min_cutoff + delta_cutoff)), 2)
            self.filter_x.set_parameters(min_cutoff=self.min_cutoff)
            self.filter_y.set_parameters(min_cutoff=self.min_cutoff)
            print(f"[HandTracker] Smoothing min_cutoff adjusted -> {self.min_cutoff:.2f} Hz")

    def save_tuning(self) -> bool:
        """Saves current live-tuned settings to disk."""
        with self.lock:
            settings = {
                "sensitivity_x": self.sensitivity_x,
                "sensitivity_y": self.sensitivity_y,
                "min_cutoff": self.min_cutoff,
                "beta": self.beta,
                "follow_speed": self.follow_speed
            }
        return save_runtime_settings(settings)

    def get_state(self) -> Dict[str, Any]:
        """
        Thread-safe snapshot of all tracking state variables.
        Called once per frame in Pygame's main game loop.
        """
        with self.lock:
            return {
                "camera_available": self.camera_available,
                "camera_index": self.active_camera_index,
                "backend": self.backend_name,
                "hand_detected": self.hand_detected,
                "is_hand_lost": self.is_hand_lost,
                "screen_x": self.screen_x,
                "screen_y": self.screen_y,
                "norm_x": self.smoothed_x,
                "norm_y": self.smoothed_y,
                "gesture": self.current_gesture,
                "metrics": self.current_metrics.copy(),
                "landmarks": self.raw_landmarks,
                "fps": self.fps,
                "preview_surface": self.preview_surface,
                "sensitivity_x": self.sensitivity_x,
                "sensitivity_y": self.sensitivity_y,
                "min_cutoff": self.min_cutoff,
                "beta": self.beta,
                "follow_speed": self.follow_speed
            }
