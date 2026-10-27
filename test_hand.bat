@echo off
title GestureStrike Hand Tracking Diagnostic
echo Starting Standalone Hand Tracking Diagnostic Tool...
cd /d "%~dp0"
.\venv\Scripts\python.exe test_hand.py
pause
