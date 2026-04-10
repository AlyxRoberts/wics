@echo off
title OTA Checklist

REM ── Locate Python ─────────────────────────────────────────────────────────────
set PYTHON_CMD=

if exist "%~dp0python\python.exe" (
    set PYTHON_CMD="%~dp0python\python.exe"
    goto :launch
)

where py >nul 2>&1
if %errorlevel%==0 (
    set PYTHON_CMD=py
    goto :launch
)

where python >nul 2>&1
if %errorlevel%==0 (
    set PYTHON_CMD=python
    goto :launch
)

REM ── Python not found ─────────────────────────────────────────────────────────
echo.
echo  Python was not found on this computer.
echo.
echo  To fix this, place a full Python installation in a folder named "python"
echo  next to this .bat file so the folder structure looks like:
echo.
echo    OTA Checklist\
echo      launch.bat
echo      broadcast_checklist.py
echo      python\
echo        python.exe
echo        ...
echo.
echo  Download Python from: https://www.python.org/downloads/
echo  During installation choose "Customize installation" and set the
echo  destination folder to the "python" subfolder shown above.
echo.
echo  NOTE: Do NOT use the embeddable zip package -- it is missing tkinter,
echo  which this application requires.
echo.
pause
goto :end

:launch
echo.
echo  +----------------------------------------------------------+
echo  ^|                    OTA Checklist                       ^|
echo  ^|                                                        ^|
echo  ^|  The application is running in the background.         ^|
echo  ^|                                                        ^|
echo  ^|  DO NOT CLOSE THIS WINDOW.                             ^|
echo  ^|  Closing it will immediately exit the application.     ^|
echo  +----------------------------------------------------------+
echo.

%PYTHON_CMD% "%~dp0broadcast_checklist.py"

:end
