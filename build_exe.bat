@echo off
title Build Standalone Executable
echo.
echo  This will create a standalone Broadcast Checklist.exe that runs on any
echo  Windows machine without needing Python installed.
echo.
echo  Requirements: Python must be installed on THIS computer to build.
echo.
pause

REM ── Install / upgrade PyInstaller ────────────────────────────────────────────
echo Installing PyInstaller...
pip install --upgrade pyinstaller
if %errorlevel% neq 0 (
    echo.
    echo  ERROR: pip failed. Make sure Python is installed and on your PATH.
    pause
    exit /b 1
)

REM ── Build the executable ─────────────────────────────────────────────────────
echo.
echo Building executable...
pyinstaller ^
    --onefile ^
    --windowed ^
    --name "Broadcast Checklist" ^
    "%~dp0broadcast_checklist.py"

if %errorlevel% neq 0 (
    echo.
    echo  ERROR: Build failed. Check the output above for details.
    pause
    exit /b 1
)

echo.
echo  Build complete!
echo.
echo  Your standalone executable is at:
echo    %~dp0dist\Broadcast Checklist.exe
echo.
echo  Copy that .exe (and nothing else) to any Windows machine.
echo  The database (broadcast_log.db) will be created automatically
echo  next to the .exe the first time it is launched.
echo.
pause
