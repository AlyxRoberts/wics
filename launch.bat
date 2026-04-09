@echo off
title Broadcast Checklist

REM ── Bundled Python (preferred) ────────────────────────────────────────────────
REM Place a full Python installation in a folder named "python" next to this file.
REM The embeddable zip from python.org will NOT work here because it lacks tkinter.
REM Use the standard Windows installer and point it at that folder, or copy an
REM existing Python installation into it.
if exist "%~dp0python\python.exe" (
    "%~dp0python\python.exe" "%~dp0broadcast_checklist.py"
    goto :end
)

REM ── System Python Launcher ────────────────────────────────────────────────────
where py >nul 2>&1
if %errorlevel%==0 (
    py "%~dp0broadcast_checklist.py"
    goto :end
)

REM ── System python on PATH ─────────────────────────────────────────────────────
where python >nul 2>&1
if %errorlevel%==0 (
    python "%~dp0broadcast_checklist.py"
    goto :end
)

REM ── Nothing found ─────────────────────────────────────────────────────────────
echo.
echo  Python was not found.
echo.
echo  To fix this, place a full Python installation in a folder named "python"
echo  next to this .bat file so the folder structure looks like:
echo.
echo    Broadcast Checklist\
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

:end
