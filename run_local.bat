@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Install Python 3.11+ and run: py -m venv .venv
  echo Then run: .venv\Scripts\python.exe -m pip install -e .
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m well24.launcher
if errorlevel 1 pause
