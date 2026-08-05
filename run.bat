@echo off
rem ============================================================
rem  AutoCaption Studio - Windows launcher
rem  Usage:  run.bat        (or double-click in Explorer)
rem ============================================================
setlocal
cd /d "%~dp0"

rem Prefer a project-local venv, then the known short-path venv.
set "VENV_PY=%~dp0.venv\Scripts\python.exe"
if not exist "%VENV_PY%" set "VENV_PY=C:\Users\tech\acstudio-venv\Scripts\python.exe"

if not exist "%VENV_PY%" (
    echo [AutoCaption] Venv python not found.
    echo   Create it once with:
    echo     python -m venv C:\Users\tech\acstudio-venv
    echo     C:\Users\tech\acstudio-venv\Scripts\python -m pip install -r requirements.txt
    echo     C:\Users\tech\acstudio-venv\Scripts\python -m pip install pytest
    pause
    exit /b 1
)

"%VENV_PY%" app.py
