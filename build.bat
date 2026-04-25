@echo off
cd /d "%~dp0"
title Aria - Build

echo.
echo   ★  Aria Build Script
echo   ================================
echo.

echo [1/4] Installing build dependencies...
pip install flask mutagen pyinstaller -q
if %errorlevel% neq 0 (
    echo   ERROR: pip failed. Make sure Python is installed and on PATH.
    pause & exit /b 1
)

echo [2/4] Cleaning previous build...
if exist "build"   rmdir /s /q "build"
if exist "dist"    rmdir /s /q "dist"
if exist "Aria.spec" del /q "Aria.spec"

echo [3/4] Building Aria.exe...
pyinstaller --clean --noconfirm ^
  --onedir ^
  --name "Aria" ^
  --add-data "templates;templates" ^
  --hidden-import mutagen ^
  --hidden-import mutagen.mp3 ^
  --hidden-import mutagen.id3 ^
  --hidden-import mutagen.asf ^
  --hidden-import mutagen.flac ^
  --hidden-import mutagen.mp4 ^
  --hidden-import mutagen.oggvorbis ^
  --hidden-import mutagen.wave ^
  --hidden-import flask ^
  --hidden-import jinja2 ^
  --hidden-import werkzeug ^
  app.py

if %errorlevel% neq 0 (
    echo.
    echo   ERROR: PyInstaller build failed. See output above.
    pause & exit /b 1
)

echo [4/4] Packaging release...
if exist "release" rmdir /s /q "release"
mkdir "release\Aria"
xcopy "dist\Aria\*" "release\Aria\" /E /I /Q

echo.
echo   ================================
echo   ✓  Build complete!
echo.
echo   Your distributable is in:  release\Aria\
echo.
echo   To ship:
echo     1. Copy your music files into  release\Aria\
echo     2. Zip the release\Aria folder
echo     3. Upload to GitHub Releases
echo.
pause
