@echo off
title Compile OTA Checklist

REM ── Locate Python (same logic as launch.bat) ──────────────────────────────
set PYTHON_CMD=

if exist "%~dp0python\python.exe" (
    set PYTHON_CMD="%~dp0python\python.exe"
    goto :compile
)

where py >nul 2>&1
if %errorlevel%==0 (
    set PYTHON_CMD=py
    goto :compile
)

where python >nul 2>&1
if %errorlevel%==0 (
    set PYTHON_CMD=python
    goto :compile
)

echo.
echo  Python was not found. Cannot compile.
echo.
pause
goto :end

:compile
echo.
echo  Compiling broadcast_checklist.py to broadcast_checklist.pyc...
echo.
%PYTHON_CMD% -c "import py_compile; py_compile.compile(r'%~dp0broadcast_checklist.py', r'%~dp0broadcast_checklist.pyc')"

if %errorlevel%==0 (
    echo  Done^^!  broadcast_checklist.pyc is ready.
) else (
    echo  Compilation failed. Check broadcast_checklist.py for syntax errors.
)
echo.
pause

:end
