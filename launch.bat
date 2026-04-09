@echo off
title Broadcast Checklist

REM ── Try Python Launcher (installed with Python for Windows) ──────────────────
where py >nul 2>&1
if %errorlevel%==0 (
    py "%~dp0broadcast_checklist.py"
    goto :end
)

REM ── Try python on PATH ────────────────────────────────────────────────────────
where python >nul 2>&1
if %errorlevel%==0 (
    python "%~dp0broadcast_checklist.py"
    goto :end
)

REM ── Python not found ─────────────────────────────────────────────────────────
echo.
echo  Python was not found on this computer.
echo.
echo  To run this app you have two options:
echo.
echo  Option 1 - Install Python (free):
echo    https://www.python.org/downloads/
echo    Check "Add Python to PATH" during installation, then re-run this file.
echo.
echo  Option 2 - Build a standalone .exe (no Python required on target machine):
echo    On a computer that has Python, run build_exe.bat
echo    Then copy the generated dist\Broadcast Checklist.exe anywhere you like.
echo.
pause

:end
