@echo off
title Mount Everest Higher Secondary School - Certificate Printing System
cd /d "%~dp0"

REM Try launching silently via pythonw if available (zero console window)
where pythonw >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    start "" pythonw app.py
    exit /b 0
)

REM Fallback to standard python (app.py auto-hides launcher console to tray on startup)
start "" python app.py
exit /b 0
