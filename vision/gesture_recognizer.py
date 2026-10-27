"""
Gesture Recognition Module for GestureStrike.

This module analyzes MediaPipe Hand landmarks to classify real-time hand poses:
1. OPEN_PALM: Steers spaceship and auto-fires primary blasters.
2. CLOSED_FIST: Activates energy defensive shield.
3. PINCH: Fires screen-clearing EMP smart bomb.
4. IDLE: Neutral hand position (steers without firing).

MediaPipe Hand Landmark Topology Reference (21 3D points):
  WRIST = 0
  THUMB:  CMC=1,  MCP=2,  IP=3,  TIP=4
  INDEX:  MCP=5,  PIP=6,  DIP=7, TIP=8
  MIDDLE: MCP=9,  PIP=10, DIP=11,TIP=12
  RING:   MCP=13, PIP=14, DIP=15,TIP=16
  PINKY:  MCP=17, PIP=18, DIP=19,TIP=20

Why these specific landmarks are selected:
- Palm Center:
  Calculated as the centroid of [WRIST (0), INDEX_MCP (5), MIDDLE_MCP (9), RING_MCP (13), PINKY_MCP (17)].
  Using the metacarpophalangeal (MCP) base knuckles guarantees a stable tracking center that
  does not drift or twitch when the player flexes, curls, or opens their fingers.
- Palm Scale (Normalization Factor):
  Euclidean distance between WRIST (0) and MIDDLE_MCP (9).
  Normalizing all geometric distances by this scale makes gesture recognition scale-invariant,
  functioning identically whether the player sits 0.5m or 2m from the webcam, and across
  different hand sizes.
- Pinch Distance:
  Euclidean distance between THUMB_TIP (4) and INDEX_TIP (8), divided by palm scale.
- Finger Extension Ratio:
  Distance from fingertip to wrist divided by palm scale. An extended finger has tip-to-wrist
  ratio > 1.3, while a curled finger has ratio < 0.9.
"""

import math
import json
import os
from typing import List, Dict, Any, Tuple, Optional
from config import (
    DEFAULT_PINCH_THRESHOLD,
    DEFAULT_FIST_THRESHOLD,
    DEFAULT_PALM_THRESHOLD,
    CALIBRATION_FILE
)


class HandGesture:
    """Enumeration of recognized hand gestures."""
    NONE = "NO HAND"
    IDLE = "IDLE"
    OPEN_PALM = "OPEN PALM (FIRE)"
    CLOSED_FIST = "CLOSED FIST (SHIELD)"
    PINCH = "PINCH (EMP BOMB)"


class GestureRecognizer:
    """
    Evaluates 21 MediaPipe hand landmarks and classifies the active gesture.
    Supports user calibration to adapt thresholds to individual hand anatomy.
    """

    def __init__(self, calibration_file: str = CALIBRATION_FILE):
        self.calibration_file = calibration_file
        self.pinch_threshold = DEFAULT_PINCH_THRESHOLD
        self.fist_threshold = DEFAULT_FIST_THRESHOLD
        self.palm_threshold = DEFAULT_PALM_THRESHOLD
        self.load_calibration()

    def load_calibration(self):
        """Loads custom calibrated thresholds from disk if available."""
        if os.path.exists(self.calibration_file):
            try:
                with open(self.calibration_file, "r") as f:
                    data = json.load(f)
                    self.pinch_threshold = data.get("pinch_threshold", DEFAULT_PINCH_THRESHOLD)
                    self.fist_threshold = data.get("fist_threshold", DEFAULT_FIST_THRESHOLD)
                    self.palm_threshold = data.get("palm_threshold", DEFAULT_PALM_THRESHOLD)
                    print(f"[GestureRecognizer] Loaded custom calibration: Pinch={self.pinch_threshold:.2f}, Fist={self.fist_threshold:.2f}")
            except Exception as e:
                print(f"[GestureRecognizer] Failed to load calibration ({e}). Using defaults.")

    def save_calibration(self, pinch_thresh: float, fist_thresh: float, palm_thresh: float):
        """Saves updated thresholds to disk."""
        self.pinch_threshold = pinch_thresh
        self.fist_threshold = fist_thresh
        self.palm_threshold = palm_thresh
        try:
            with open(self.calibration_file, "w") as f:
                json.dump({
                    "pinch_threshold": pinch_thresh,
                    "fist_threshold": fist_thresh,
                    "palm_threshold": palm_thresh
                }, f, indent=2)
            print("[GestureRecognizer] Calibration saved successfully.")
        except Exception as e:
            print(f"[GestureRecognizer] Error saving calibration: {e}")

    @staticmethod
    def _dist(p1: Any, p2: Any) -> float:
        """Calculates 2D/3D Euclidean distance between two landmarks."""
        dx = p1.x - p2.x
        dy = p1.y - p2.y
        dz = getattr(p1, 'z', 0.0) - getattr(p2, 'z', 0.0)
        return math.sqrt(dx * dx + dy * dy + dz * dz)

    def calculate_palm_center(self, landmarks: List[Any]) -> Tuple[float, float]:
        """
        Calculates the normalized (x, y) coordinates of the palm center.
        Uses the centroid of the wrist and 4 base finger MCP joints.
        """
        # Wrist(0), Index MCP(5), Middle MCP(9), Ring MCP(13), Pinky MCP(17)
        indices = [0, 5, 9, 13, 17]
        avg_x = sum(landmarks[i].x for i in indices) / len(indices)
        avg_y = sum(landmarks[i].y for i in indices) / len(indices)
        return avg_x, avg_y

    def calculate_palm_scale(self, landmarks: List[Any]) -> float:
        """
        Calculates palm reference scale: distance from WRIST (0) to MIDDLE_MCP (9).
        Guaranteed to remain roughly constant during finger gestures.
        """
        scale = self._dist(landmarks[0], landmarks[9])
        return max(scale, 0.001)  # Prevent division by zero

    def evaluate(self, landmarks: Optional[List[Any]]) -> Tuple[str, Dict[str, float]]:
        """
        Analyzes hand landmarks and returns (gesture_name, metrics_dict).
        
        Metrics returned include:
        - pinch_ratio: thumb-to-index distance / palm_scale
        - avg_curl_ratio: average fingertip-to-wrist distance / palm_scale
        - palm_scale: absolute palm reference size
        """
        if not landmarks or len(landmarks) < 21:
            return HandGesture.NONE, {}

        wrist = landmarks[0]
        thumb_tip = landmarks[4]
        index_tip = landmarks[8]
        middle_tip = landmarks[12]
        ring_tip = landmarks[16]
        pinky_tip = landmarks[20]

        index_pip = landmarks[6]
        middle_pip = landmarks[10]
        ring_pip = landmarks[14]
        pinky_pip = landmarks[18]

        palm_scale = self.calculate_palm_scale(landmarks)

        # 1. Calculate Pinch Ratio (Thumb Tip to Index Tip)
        pinch_dist = self._dist(thumb_tip, index_tip)
        pinch_ratio = pinch_dist / palm_scale

        # 2. Calculate Finger Extension / Curl Ratios
        # Distance from each fingertip to wrist, normalized by palm scale
        fingertip_indices = [8, 12, 16, 20]
        tip_dists = [self._dist(landmarks[idx], wrist) / palm_scale for idx in fingertip_indices]
        avg_curl_ratio = sum(tip_dists) / len(tip_dists)

        # Check if individual fingers are extended (Tip further from wrist than PIP joint)
        index_open = self._dist(index_tip, wrist) > self._dist(index_pip, wrist)
        middle_open = self._dist(middle_tip, wrist) > self._dist(middle_pip, wrist)
        ring_open = self._dist(ring_tip, wrist) > self._dist(ring_pip, wrist)
        pinky_open = self._dist(pinky_tip, wrist) > self._dist(pinky_pip, wrist)

        open_finger_count = sum([index_open, middle_open, ring_open, pinky_open])

        metrics = {
            "pinch_ratio": pinch_ratio,
            "avg_curl_ratio": avg_curl_ratio,
            "palm_scale": palm_scale,
            "open_finger_count": float(open_finger_count)
        }

        # Decision Tree for Gesture Classification:
        # Priority 1: PINCH (Thumb and Index tips touching)
        # Allows player to trigger screen-clearing bomb even while hand is otherwise extended
        if pinch_ratio < self.pinch_threshold and avg_curl_ratio > 0.70:
            return HandGesture.PINCH, metrics

        # Priority 2: CLOSED FIST (All fingers curled into palm)
        # Activates defensive energy shield
        if avg_curl_ratio < self.fist_threshold or open_finger_count <= 1:
            return HandGesture.CLOSED_FIST, metrics

        # Priority 3: OPEN PALM (Fingers spread wide)
        # Auto-fires plasma blasters and steers ship
        if open_finger_count >= 3 and avg_curl_ratio >= self.palm_threshold:
            return HandGesture.OPEN_PALM, metrics

        # Priority 4: IDLE
        # Allows peaceful navigation without shooting or shielding
        return HandGesture.IDLE, metrics
