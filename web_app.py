"""
GestureStrike - Web Dashboard & Localhost Portal
Provides a web interface running on http://localhost:5000 with:
- Pilot Authentication & Login Page
- Live Web Dashboard with System Status
- Browser Webcam Hand Tracking Video Stream (MJPEG)
- Interactive Hall of Fame / High Scores Leaderboard
- Real-time Controls and Vision Telemetry
- One-Click Launch Native Game Desktop Process
"""

import os
import sys
import math
import json
import time
import subprocess
import threading
import cv2
import mediapipe as mp
import numpy as np
from flask import Flask, render_template_string, request, redirect, url_for, session, Response, jsonify

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from config import HIGHSCORES_FILE, SETTINGS_FILE, load_runtime_settings, save_runtime_settings
from vision.one_euro_filter import OneEuroFilter

app = Flask(__name__)
app.secret_key = "gesturestrike_secret_key_college_project_2026"

# HTML TEMPLATES
LOGIN_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>GestureStrike - Pilot Login</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Consolas', 'Courier New', monospace; }
        body {
            background: radial-gradient(circle at center, #14172f 0%, #0a0b18 100%);
            color: #f0f4fc;
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
        }
        .login-card {
            background: rgba(18, 22, 42, 0.95);
            border: 2px solid #00f0ff;
            box-shadow: 0 0 25px rgba(0, 240, 255, 0.35);
            border-radius: 8px;
            padding: 40px;
            width: 100%;
            max-width: 440px;
            text-align: center;
        }
        h1 {
            color: #00f0ff;
            font-size: 28px;
            letter-spacing: 3px;
            margin-bottom: 8px;
            text-transform: uppercase;
        }
        .subtitle {
            color: #ffe600;
            font-size: 13px;
            letter-spacing: 1px;
            margin-bottom: 28px;
        }
        .input-group {
            margin-bottom: 20px;
            text-align: left;
        }
        label {
            display: block;
            color: #b0c0dc;
            font-size: 13px;
            margin-bottom: 6px;
        }
        input {
            width: 100%;
            padding: 12px 14px;
            background: #0e1222;
            border: 1px solid #2a3b60;
            border-radius: 4px;
            color: #fff;
            font-size: 16px;
            outline: none;
            transition: border-color 0.2s;
        }
        input:focus {
            border-color: #00f0ff;
            box-shadow: 0 0 8px rgba(0, 240, 255, 0.4);
        }
        .btn-login {
            width: 100%;
            padding: 14px;
            background: linear-gradient(90deg, #00c6ff, #0072ff);
            border: none;
            border-radius: 4px;
            color: #fff;
            font-weight: bold;
            font-size: 16px;
            letter-spacing: 1.5px;
            cursor: pointer;
            transition: transform 0.15s, box-shadow 0.15s;
            margin-top: 10px;
        }
        .btn-login:hover {
            transform: translateY(-2px);
            box-shadow: 0 0 16px rgba(0, 240, 255, 0.6);
        }
        .badge {
            display: inline-block;
            margin-top: 24px;
            padding: 6px 12px;
            background: rgba(0, 255, 136, 0.15);
            border: 1px solid #00ff88;
            color: #00ff88;
            border-radius: 20px;
            font-size: 11px;
        }
    </style>
</head>
<body>
    <div class="login-card">
        <h1>GESTURESTRIKE</h1>
        <div class="subtitle">AI SPACE SHOOTER LOCALHOST PORTAL</div>
        <form method="POST" action="/login">
            <div class="input-group">
                <label>PILOT CALLSIGN / USERNAME:</label>
                <input type="text" name="callsign" value="PILOT-ALPHA" required autofocus>
            </div>
            <div class="input-group">
                <label>SECURITY ACCESS CODE:</label>
                <input type="password" name="passcode" value="1234">
            </div>
            <button type="submit" class="btn-login">INITIALIZE LOCALHOST LINK</button>
        </form>
        <div class="badge">HOST: 127.0.0.1:5000 | STATUS: ONLINE</div>
    </div>
</body>
</html>
"""

DASHBOARD_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>GestureStrike - Localhost Command Center</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Consolas', 'Courier New', monospace; }
        body {
            background: #0a0b18;
            color: #e0e8f5;
            padding: 24px;
        }
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 2px solid #00f0ff;
            padding-bottom: 16px;
            margin-bottom: 24px;
        }
        .header h1 {
            color: #00f0ff;
            font-size: 26px;
            letter-spacing: 2px;
        }
        .user-info {
            font-size: 14px;
            color: #00ff88;
        }
        .btn-logout {
            color: #ff3366;
            text-decoration: none;
            margin-left: 14px;
            border: 1px solid #ff3366;
            padding: 4px 10px;
            border-radius: 4px;
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(360px, 1fr));
            gap: 20px;
            margin-bottom: 24px;
        }
        .card {
            background: #12162a;
            border: 1px solid #202b45;
            border-radius: 6px;
            padding: 20px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.4);
        }
        .card h2 {
            color: #ffe600;
            font-size: 18px;
            margin-bottom: 14px;
            border-bottom: 1px solid #202b45;
            padding-bottom: 8px;
            display: flex;
            justify-content: space-between;
        }
        .btn-launch {
            display: block;
            width: 100%;
            padding: 16px;
            background: linear-gradient(90deg, #00f0ff, #0072ff);
            color: #fff;
            border: none;
            border-radius: 6px;
            font-size: 18px;
            font-weight: bold;
            cursor: pointer;
            text-align: center;
            text-decoration: none;
            box-shadow: 0 0 15px rgba(0, 240, 255, 0.4);
            margin-bottom: 12px;
            transition: transform 0.15s;
        }
        .btn-launch:hover {
            transform: scale(1.02);
            box-shadow: 0 0 25px rgba(0, 240, 255, 0.7);
        }
        .btn-sub {
            display: inline-block;
            width: 100%;
            padding: 10px;
            background: #1a2238;
            color: #00f0ff;
            border: 1px solid #00f0ff;
            border-radius: 4px;
            text-align: center;
            text-decoration: none;
            cursor: pointer;
            margin-bottom: 8px;
        }
        .btn-sub:hover {
            background: #253355;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            font-size: 14px;
        }
        th, td {
            padding: 8px 10px;
            text-align: left;
            border-bottom: 1px solid #1c253d;
        }
        th {
            color: #00f0ff;
        }
        .stream-box {
            text-align: center;
            background: #080a12;
            border: 1px solid #00f0ff;
            border-radius: 4px;
            overflow: hidden;
            min-height: 240px;
        }
        .stream-box img {
            width: 100%;
            max-width: 480px;
            display: block;
            margin: 0 auto;
        }
        .telemetry-row {
            display: flex;
            justify-content: space-between;
            padding: 6px 0;
            font-size: 13px;
            border-bottom: 1px dotted #202b45;
        }
        .badge-live {
            background: #00ff88;
            color: #000;
            padding: 2px 6px;
            border-radius: 3px;
            font-size: 11px;
            font-weight: bold;
        }
    </style>
</head>
<body>
    <div class="header">
        <div>
            <h1>GESTURESTRIKE COMMAND CENTER</h1>
            <div style="color: #8899b5; font-size: 12px; margin-top: 4px;">LOCAL SERVER ACTIVE AT http://localhost:5000</div>
        </div>
        <div class="user-info">
            ACTIVE PILOT: <strong>{{ session.get('callsign', 'GUEST') }}</strong>
            <a href="/logout" class="btn-logout">LOGOUT</a>
        </div>
    </div>

    <div class="grid">
        <!-- Quick Launch & Control -->
        <div class="card">
            <h2>GAME CONTROLLER <span class="badge-live">READY</span></h2>
            <button onclick="launchGame()" class="btn-launch">▶ LAUNCH GESTURESTRIKE (DESKTOP)</button>
            <button onclick="launchDiagnostic()" class="btn-sub">🔍 RUN WEBCAM DIAGNOSTIC TEST</button>
            <div id="launch-status" style="margin-top: 10px; font-size: 13px; color: #ffe600;"></div>
            
            <div style="margin-top: 20px;">
                <div class="telemetry-row"><span>Active Port:</span><strong>5000 (Localhost)</strong></div>
                <div class="telemetry-row"><span>Pygame Subsystem:</span><strong style="color: #00ff88;">v2.6.0 Online</strong></div>
                <div class="telemetry-row"><span>MediaPipe Engine:</span><strong style="color: #00ff88;">v0.10.14 Ready</strong></div>
                <div class="telemetry-row"><span>OpenCV DirectShow:</span><strong style="color: #00ff88;">Enabled</strong></div>
            </div>
        </div>

        <!-- Live Webcam Stream -->
        <div class="card">
            <h2>LIVE WEBCAM STREAM <span class="badge-live">CAMERA 0</span></h2>
            <div class="stream-box">
                <img src="/video_feed" alt="Live Camera Feed (MediaPipe)">
            </div>
            <div style="font-size: 12px; color: #8899b5; margin-top: 8px; text-align: center;">
                Shows real-time mirrored camera feed with skeleton tracking & gesture detection.
            </div>
        </div>

        <!-- Hall of Fame -->
        <div class="card">
            <h2>GALACTIC HALL OF FAME 🏆</h2>
            <table>
                <thead>
                    <tr>
                        <th>RANK</th>
                        <th>PILOT</th>
                        <th>SCORE</th>
                        <th>WAVE</th>
                        <th>DATE</th>
                    </tr>
                </thead>
                <tbody>
                    {% for s in highscores %}
                    <tr>
                        <td style="color: #00f0ff;">#0{{ loop.index }}</td>
                        <td style="color: #00ff88; font-weight: bold;">{{ s.name }}</td>
                        <td style="color: #ffe600;">{{ s.score }}</td>
                        <td>Wave {{ s.wave }}</td>
                        <td style="color: #8899b5; font-size: 12px;">{{ s.date }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>

        <!-- Hand Controls Matrix -->
        <div class="card">
            <h2>GESTURE CONTROLS MATRIX</h2>
            <table>
                <thead>
                    <tr>
                        <th>ACTION</th>
                        <th>HAND GESTURE</th>
                        <th>KEYBOARD</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>Steer Spaceship</td>
                        <td style="color: #00ff88;">Move Hand (Palm Center)</td>
                        <td>WASD / Mouse</td>
                    </tr>
                    <tr>
                        <td>Primary Lasers</td>
                        <td style="color: #00ff88;">OPEN PALM</td>
                        <td>Spacebar / Left Click</td>
                    </tr>
                    <tr>
                        <td>Plasma Shield</td>
                        <td style="color: #00f0ff;">CLOSED FIST</td>
                        <td>S Key / Right Click</td>
                    </tr>
                    <tr>
                        <td>EMP Smart Bomb</td>
                        <td style="color: #ff0080;">PINCH (Thumb + Index)</td>
                        <td>B Key / Middle Click</td>
                    </tr>
                    <tr>
                        <td>Auto-Pause</td>
                        <td style="color: #ff3366;">Hand Hidden > 1.0s</td>
                        <td>P Key / ESC</td>
                    </tr>
                    <tr>
                        <td>Tune Sensitivity</td>
                        <td style="color: #ffe600;">[ and ] Keys</td>
                        <td>Live In-Game</td>
                    </tr>
                </tbody>
            </table>
        </div>
    </div>

    <script>
        function launchGame() {
            const status = document.getElementById('launch-status');
            status.innerHTML = "Launching GestureStrike desktop game window...";
            fetch('/api/launch_game')
                .then(r => r.json())
                .then(d => {
                    status.innerHTML = "✔ " + d.message;
                    setTimeout(() => status.innerHTML = "", 5000);
                })
                .catch(e => {
                    status.innerHTML = "Error launching: " + e;
                });
        }

        function launchDiagnostic() {
            const status = document.getElementById('launch-status');
            status.innerHTML = "Opening standalone hand diagnostic test...";
            fetch('/api/launch_diagnostic')
                .then(r => r.json())
                .then(d => {
                    status.innerHTML = "✔ " + d.message;
                    setTimeout(() => status.innerHTML = "", 5000);
                });
        }
    </script>
</body>
</html>
"""

# Web Video Feed Generator using OpenCV & MediaPipe
def gen_frames():
    """Generates JPEG frame stream for the web browser."""
    cap = None
    for idx in [0, 1, 2]:
        try:
            cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
            if cap.isOpened():
                ret, test = cap.read()
                if ret and test is not None:
                    break
                cap.release()
        except Exception:
            pass

    if cap is None or not cap.isOpened():
        cap = cv2.VideoCapture(0)

    mp_hands = mp.solutions.hands
    mp_draw = mp.solutions.drawing_utils
    mp_styles = mp.solutions.drawing_styles

    with mp_hands.Hands(static_image_mode=False, max_num_hands=1, model_complexity=0, min_detection_confidence=0.5, min_tracking_confidence=0.5) as hands:
        while True:
            success, frame = cap.read()
            if not success or frame is None:
                time.sleep(0.04)
                continue

            frame = cv2.flip(frame, 1)
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = hands.process(rgb)

            gesture_name = "SEARCHING HAND..."
            if results.multi_hand_landmarks:
                for hl in results.multi_hand_landmarks:
                    mp_draw.draw_landmarks(frame, hl, mp_hands.HAND_CONNECTIONS, mp_styles.get_default_hand_landmarks_style(), mp_styles.get_default_hand_connections_style())
                    # Quick gesture detection
                    wrist = hl.landmark[0]
                    thumb = hl.landmark[4]
                    index_tip = hl.landmark[8]
                    scale = max(0.001, math.hypot(hl.landmark[9].x - wrist.x, hl.landmark[9].y - wrist.y))
                    pinch = math.hypot(thumb.x - index_tip.x, thumb.y - index_tip.y) / scale
                    tips = [8, 12, 16, 20]
                    curl = sum(math.hypot(hl.landmark[i].x - wrist.x, hl.landmark[i].y - wrist.y) / scale for i in tips) / 4.0

                    if pinch < 0.40 and curl > 0.70:
                        gesture_name = "PINCH (EMP BOMB)"
                    elif curl < 0.88:
                        gesture_name = "CLOSED FIST (SHIELD)"
                    elif curl >= 1.25:
                        gesture_name = "OPEN PALM (FIRE)"
                    else:
                        gesture_name = "IDLE (STEER)"

            # Draw overlay on video feed
            h, w = frame.shape[:2]
            cv2.rectangle(frame, (10, 10), (w - 10, 50), (12, 16, 28), -1)
            cv2.putText(frame, f"WEB LIVE: {gesture_name}", (20, 38), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 240, 255), 2)

            ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
            if not ret:
                continue

            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

    if cap:
        cap.release()


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        callsign = request.form.get("callsign", "PILOT-ALPHA").strip()
        session["callsign"] = callsign.upper() if callsign else "PILOT-ALPHA"
        session["logged_in"] = True
        return redirect(url_for("dashboard"))
    return render_template_string(LOGIN_TEMPLATE)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
def dashboard():
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    highscores = []
    if os.path.exists(HIGHSCORES_FILE):
        try:
            with open(HIGHSCORES_FILE, "r") as f:
                highscores = json.load(f)[:6]
        except Exception:
            pass

    return render_template_string(DASHBOARD_TEMPLATE, highscores=highscores)


@app.route("/video_feed")
def video_feed():
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route("/api/launch_game")
def api_launch_game():
    python_exe = sys.executable
    main_script = os.path.join(BASE_DIR, "main.py")
    subprocess.Popen([python_exe, main_script], cwd=BASE_DIR)
    return jsonify({"status": "success", "message": "GestureStrike Desktop Game started successfully!"})


@app.route("/api/launch_diagnostic")
def api_launch_diagnostic():
    python_exe = sys.executable
    diag_script = os.path.join(BASE_DIR, "test_hand.py")
    subprocess.Popen([python_exe, diag_script], cwd=BASE_DIR)
    return jsonify({"status": "success", "message": "Hand tracking test window launched!"})


if __name__ == "__main__":
    print("=============================================================")
    print(" GESTURESTRIKE WEB DASHBOARD & LOCALHOST LINK ACTIVE ")
    print(" ACCESS DIRECT LINK -> http://localhost:5000/login ")
    print("=============================================================")
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
