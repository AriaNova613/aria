@echo off
cd /d "%~dp0"
title Aria

echo.
echo   ★  Aria
echo   ================================
echo.

echo [1/2] Checking dependencies...
pip install flask mutagen -q

where ffmpeg >nul 2>&1
if %errorlevel% neq 0 (
    echo   FFmpeg not found — attempting install...
    winget install --id Gyan.FFmpeg -e --silent --accept-source-agreements --accept-package-agreements
    if %errorlevel% neq 0 (
        echo.
        echo   FFmpeg could not be installed automatically.
        echo   WMA and AAC files will not play until it is installed.
        echo   Run:  winget install --id Gyan.FFmpeg -e
        echo.
    )
)

echo [2/2] Starting Aria...
python app.py
