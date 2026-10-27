@echo off
title GestureStrike Web Portal & Dashboard
cd /d "%~dp0"
echo ========================================================
echo    GESTURESTRIKE WEB DASHBOARD & LOCALHOST PORTAL
echo ========================================================
echo Starting web server on http://localhost:5000/login ...
start http://localhost:5000/login
.\venv\Scripts\python.exe web_app.py
pause
