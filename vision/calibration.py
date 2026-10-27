"""
Calibration Module for GestureStrike.
Collects landmark samples for Open Palm and Closed Fist gestures
to compute customized, adaptive thresholds for any player's hands.
"""

from typing import List, Dict, Any, Optional
from config import (
    DEFAULT_PINCH_THRESHOLD,
    DEFAULT_FIST_THRESHOLD,
    DEFAULT_PALM_THRESHOLD
)
from vision.gesture_recognizer import GestureRecognizer, HandGesture


class HandCalibrator:
    """
    State machine that walks the user through Open Palm and Closed Fist calibration.
    """

    STEP_INTRO = 0
    STEP_OPEN_PALM = 1
    STEP_CLOSED_FIST = 2
    STEP_COMPLETE = 3

    SAMPLES_NEEDED = 40

    def __init__(self, recognizer: GestureRecognizer):
        self.recognizer = recognizer
        self.step = self.STEP_INTRO
        self.open_samples: List[Dict[str, float]] = []
        self.fist_samples: List[Dict[str, float]] = []
        self.status_message = "Press SPACE or Click to Begin Calibration"
        self.progress = 0.0

    def reset(self):
        """Resets calibration state machine."""
        self.step = self.STEP_INTRO
        self.open_samples.clear()
        self.fist_samples.clear()
        self.status_message = "Press SPACE or Click to Begin Calibration"
        self.progress = 0.0

    def start(self):
        """Begins calibration sequence."""
        self.step = self.STEP_OPEN_PALM
        self.open_samples.clear()
        self.fist_samples.clear()
        self.status_message = "Hold your hand OPEN with fingers spread wide..."

    def feed_frame(self, landmarks: Optional[List[Any]]) -> bool:
        """
        Feeds landmarks from the current frame to the calibrator.
        Returns True when calibration step completes.
        """
        if not landmarks or len(landmarks) < 21:
            return False

        _, metrics = self.recognizer.evaluate(landmarks)
        if not metrics:
            return False

        if self.step == self.STEP_OPEN_PALM:
            self.open_samples.append(metrics)
            self.progress = len(self.open_samples) / self.SAMPLES_NEEDED
            self.status_message = f"Calibrating Open Palm... {int(self.progress * 100)}%"

            if len(self.open_samples) >= self.SAMPLES_NEEDED:
                self.step = self.STEP_CLOSED_FIST
                self.progress = 0.0
                self.status_message = "Great! Now make a tight CLOSED FIST..."
                return True

        elif self.step == self.STEP_CLOSED_FIST:
            self.fist_samples.append(metrics)
            self.progress = len(self.fist_samples) / self.SAMPLES_NEEDED
            self.status_message = f"Calibrating Closed Fist... {int(self.progress * 100)}%"

            if len(self.fist_samples) >= self.SAMPLES_NEEDED:
                self._compute_and_save()
                self.step = self.STEP_COMPLETE
                self.progress = 1.0
                self.status_message = "Calibration Complete! Thresholds saved."
                return True

        return False

    def _compute_and_save(self):
        """Calculates adapted thresholds from gathered samples and saves them."""
        avg_open_curl = sum(s["avg_curl_ratio"] for s in self.open_samples) / len(self.open_samples)
        avg_fist_curl = sum(s["avg_curl_ratio"] for s in self.fist_samples) / len(self.fist_samples)

        # The fist threshold is set halfway between fist curl and open curl
        # but biased toward fist for reliable activation
        adapted_fist = avg_fist_curl + (avg_open_curl - avg_fist_curl) * 0.35
        adapted_palm = avg_open_curl * 0.85
        adapted_pinch = DEFAULT_PINCH_THRESHOLD

        self.recognizer.save_calibration(
            pinch_thresh=round(adapted_pinch, 3),
            fist_thresh=round(adapted_fist, 3),
            palm_thresh=round(adapted_palm, 3)
        )
