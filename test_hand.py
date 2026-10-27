"""
Standalone Hand Tracking & Gesture Diagnostic Tool for GestureStrike.
Tests camera discovery (indexes 0, 1, 2 with CAP_DSHOW), MediaPipe Hands pipeline,
mirroring, palm position tracking, FPS, and live gesture classification:
- OPEN PALM
- CLOSED FIST
- PINCH
- IDLE / NO HAND
"""

import sys
import time
import math
import cv2
import mediapipe as mp
import numpy as np

from vision.one_euro_filter import OneEuroFilter
from config import (
    SENSITIVITY_X,
    SENSITIVITY_Y,
    ONE_EURO_MIN_CUTOFF,
    ONE_EURO_BETA,
    ONE_EURO_D_CUTOFF,
    DEAD_ZONE_RADIUS,
    MODEL_COMPLEXITY
)

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(line_buffering=True)


def open_working_camera():
    """
    Tries camera indexes 0, 1, and 2 with cv2.CAP_DSHOW on Windows,
    falling back to default backend. Verifies cap.isOpened() and valid frames.
    Returns (cap, camera_index, backend_name).
    """
    print("[Camera Probe] Searching for available camera devices (indexes 0, 1, 2)...", flush=True)
    
    candidates = []
    # Test DSHOW first (standard on Windows for fast DirectShow access)
    for idx in [0, 1, 2]:
        candidates.append((idx, cv2.CAP_DSHOW, "CAP_DSHOW"))
        candidates.append((idx, None, "DEFAULT"))

    for idx, backend, name in candidates:
        try:
            if backend is not None:
                cap = cv2.VideoCapture(idx, backend)
            else:
                cap = cv2.VideoCapture(idx)

            if cap.isOpened():
                # Read a test frame to ensure driver isn't returning blank/None
                ret, frame = cap.read()
                if ret and frame is not None and frame.size > 0:
                    h, w = frame.shape[:2]
                    print(f"[Camera Probe] SUCCESS -> Opened Camera {idx} using {name} ({w}x{h}).")
                    return cap, idx, name
                else:
                    cap.release()
            else:
                cap.release()
        except Exception as e:
            pass

    print("[Camera Probe] ERROR: No working webcam found on indexes 0, 1, or 2!")
    return None, -1, "NONE"


def dist(p1, p2):
    """Euclidean distance between two landmarks (x, y, z)."""
    dx = p1.x - p2.x
    dy = p1.y - p2.y
    dz = getattr(p1, 'z', 0.0) - getattr(p2, 'z', 0.0)
    return math.sqrt(dx * dx + dy * dy + dz * dz)


def classify_gesture(landmarks):
    """
    Biomechanical gesture classification normalized by palm scale.
    Palm scale = Euclidean distance between WRIST (0) and MIDDLE_MCP (9).
    """
    if not landmarks or len(landmarks) < 21:
        return "NO HAND", 0.0, 0.0, (0.5, 0.5)

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

    # 1. Palm Scale (Distance from Wrist to Middle MCP)
    palm_scale = max(dist(wrist, landmarks[9]), 0.001)

    # 2. Palm Centroid (Centroid of Wrist and Base Knuckles)
    palm_indices = [0, 5, 9, 13, 17]
    palm_x = sum(landmarks[i].x for i in palm_indices) / len(palm_indices)
    palm_y = sum(landmarks[i].y for i in palm_indices) / len(palm_indices)

    # 3. Pinch Ratio: Thumb Tip to Index Tip normalized by palm scale
    pinch_dist = dist(thumb_tip, index_tip)
    pinch_ratio = pinch_dist / palm_scale

    # 4. Finger Curl: Average distance of 4 fingertips to wrist normalized by palm scale
    tips = [index_tip, middle_tip, ring_tip, pinky_tip]
    tip_dists = [dist(t, wrist) / palm_scale for t in tips]
    avg_curl_ratio = sum(tip_dists) / len(tip_dists)

    # Check individual finger extensions (tip further from wrist than PIP knuckle)
    open_fingers = sum([
        dist(index_tip, wrist) > dist(index_pip, wrist),
        dist(middle_tip, wrist) > dist(middle_pip, wrist),
        dist(ring_tip, wrist) > dist(ring_pip, wrist),
        dist(pinky_tip, wrist) > dist(pinky_pip, wrist)
    ])

    # Gesture Rules
    # PINCH: Thumb & Index touching, not full fist
    if pinch_ratio < 0.40 and avg_curl_ratio > 0.70:
        gesture = "PINCH (EMP BOMB)"
    # CLOSED FIST: All fingers curled or average curl ratio very low
    elif avg_curl_ratio < 0.88 or open_fingers <= 1:
        gesture = "CLOSED FIST (SHIELD)"
    # OPEN PALM: At least 3 fingers extended and curl ratio high
    elif open_fingers >= 3 and avg_curl_ratio >= 1.25:
        gesture = "OPEN PALM (FIRE)"
    else:
        gesture = "IDLE (STEER)"

    return gesture, pinch_ratio, avg_curl_ratio, (palm_x, palm_y)


def run_test(max_frames=None, show_window=True):
    """Runs live webcam hand test with 1€ Filter and active sensitivity zone."""
    cap, cam_idx, backend_name = open_working_camera()
    if cap is None:
        print("[test_hand] Failed to open any camera. Please check camera connection or permissions.")
        return False

    try:
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    except Exception:
        pass
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    # Initialize 1€ Filters
    filter_x = OneEuroFilter(min_cutoff=ONE_EURO_MIN_CUTOFF, beta=ONE_EURO_BETA, d_cutoff=ONE_EURO_D_CUTOFF)
    filter_y = OneEuroFilter(min_cutoff=ONE_EURO_MIN_CUTOFF, beta=ONE_EURO_BETA, d_cutoff=ONE_EURO_D_CUTOFF)
    smoothed_palm = [0.5, 0.5]

    # Initialize MediaPipe Hands with ultra-fast model complexity 0
    mp_hands = mp.solutions.hands
    mp_draw = mp.solutions.drawing_utils
    mp_drawing_styles = mp.solutions.drawing_styles

    hands = mp_hands.Hands(
        static_image_mode=False,
        max_num_hands=1,
        model_complexity=MODEL_COMPLEXITY,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5
    )

    print("\n--------------------------------------------------------------")
    print(" LIVE HAND TRACKING & SENSITIVITY TEST (1€ FILTER)")
    print(f" Sensitivity: X={SENSITIVITY_X}x, Y={SENSITIVITY_Y}x | Min Cutoff: {ONE_EURO_MIN_CUTOFF}Hz")
    print(" Gestures: OPEN PALM, CLOSED FIST, PINCH, IDLE")
    print(" Press 'q' or ESC in the preview window to exit.")
    print("--------------------------------------------------------------\n")

    prev_time = time.time()
    frame_count = 0
    success_detections = 0

    try:
        while True:
            # Drain buffer to guarantee lowest latency
            cap.grab()
            ret, frame = cap.read()
            if not ret or frame is None:
                time.sleep(0.005)
                continue

            # Step 1: Mirror horizontally for natural interaction
            frame = cv2.flip(frame, 1)

            # Step 2: Convert BGR to RGB for MediaPipe
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            # Step 3: Run inference
            results = hands.process(rgb_frame)

            # Calculate FPS
            now = time.time()
            dt = now - prev_time
            prev_time = now
            fps = 1.0 / dt if dt > 0 else 30.0

            hand_detected = False
            gesture = "NO HAND"
            pinch_val = 0.0
            curl_val = 0.0
            palm_pos = (0.5, 0.5)
            target_pos = (0.5, 0.5)

            if results.multi_hand_landmarks:
                hand_detected = True
                success_detections += 1
                hand_landmarks = results.multi_hand_landmarks[0]

                # Draw skeleton landmarks on frame
                mp_draw.draw_landmarks(
                    frame,
                    hand_landmarks,
                    mp_hands.HAND_CONNECTIONS,
                    mp_drawing_styles.get_default_hand_landmarks_style(),
                    mp_drawing_styles.get_default_hand_connections_style()
                )

                # Classify gesture and raw palm center
                gesture, pinch_val, curl_val, raw_palm = classify_gesture(hand_landmarks.landmark)

                # Apply One Euro Filter
                fx = filter_x.filter(raw_palm[0], now)
                fy = filter_y.filter(raw_palm[1], now)

                # Dead zone check
                dx = fx - smoothed_palm[0]
                dy = fy - smoothed_palm[1]
                if math.hypot(dx, dy) > DEAD_ZONE_RADIUS:
                    smoothed_palm[0] = fx
                    smoothed_palm[1] = fy

                palm_pos = (smoothed_palm[0], smoothed_palm[1])

                # High-Sensitivity Active Zone Mapping:
                # target = 0.5 + (palm - 0.5) * SENSITIVITY, then clamp to 0..1
                tx = max(0.0, min(1.0, 0.5 + (palm_pos[0] - 0.5) * SENSITIVITY_X))
                ty = max(0.0, min(1.0, 0.5 + (palm_pos[1] - 0.5) * SENSITIVITY_Y))
                target_pos = (tx, ty)

                # Draw raw palm center (Yellow) and mapped target (Cyan)
                h, w = frame.shape[:2]
                px = int(palm_pos[0] * w)
                py = int(palm_pos[1] * h)
                cv2.circle(frame, (px, py), 8, (0, 255, 255), -1)

                tx_px = int(target_pos[0] * w)
                ty_px = int(target_pos[1] * h)
                cv2.circle(frame, (tx_px, ty_px), 12, (255, 255, 0), 2)
                cv2.putText(frame, "TARGET", (tx_px + 14, ty_px + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)

            # On-screen HUD text overlays
            h, w = frame.shape[:2]
            cv2.rectangle(frame, (10, 10), (w - 10, 140), (15, 15, 25), -1)
            cv2.rectangle(frame, (10, 10), (w - 10, 140), (0, 240, 255), 2)

            det_color = (0, 255, 120) if hand_detected else (0, 60, 255)
            cv2.putText(frame, f"HAND: {'DETECTED (1e Filter)' if hand_detected else 'SEARCHING...'}", (24, 36), cv2.FONT_HERSHEY_SIMPLEX, 0.7, det_color, 2)
            cv2.putText(frame, f"GESTURE: {gesture}", (24, 64), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 255, 255), 2)
            cv2.putText(frame, f"PALM NORM: ({palm_pos[0]:.2f}, {palm_pos[1]:.2f}) -> SCREEN TARGET: ({target_pos[0]:.2f}, {target_pos[1]:.2f})", (24, 92), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (220, 220, 220), 1)
            cv2.putText(frame, f"SENS: X={SENSITIVITY_X}x Y={SENSITIVITY_Y}x | Pinch: {pinch_val:.2f} | FPS: {int(fps)}", (24, 118), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (180, 180, 180), 1)

            # Console output every 15 frames
            if frame_count % 15 == 0:
                print(f"[Frame {frame_count:04d}] Hand: {'YES' if hand_detected else 'NO'} | Gesture: {gesture:<20} | Palm: ({palm_pos[0]:.2f}, {palm_pos[1]:.2f}) -> Target: ({target_pos[0]:.2f}, {target_pos[1]:.2f}) | FPS: {fps:.1f}")

            frame_count += 1

            if show_window:
                cv2.imshow("GestureStrike - Hand Tracking Test", frame)
                key = cv2.waitKey(1) & 0xFF
                if key in [ord('q'), 27]:  # 'q' or ESC
                    break

            if max_frames and frame_count >= max_frames:
                break

    except KeyboardInterrupt:
        print("\n[test_hand] User stopped tracking test.")
    finally:
        cap.release()
        hands.close()
        if show_window:
            cv2.destroyAllWindows()
        print(f"\n[test_hand] Diagnostic complete. Processed {frame_count} frames ({success_detections} hand detections).")
        return True


if __name__ == "__main__":
    max_f = None
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        max_f = int(sys.argv[1])
    run_test(max_frames=max_f, show_window=True)
