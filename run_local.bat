@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Install Python 3.11+ and run: py -m venv .venv
  echo Then run: .venv\Scripts\python.exe -m pip install -e .
  pause
  exit /b 1
)
echo Open http://127.0.0.1:8002 in your browser.
echo Closing this server stops operation. The screen may turn off during use.
".venv\Scripts\python.exe" -m uvicorn well24.app:app --host 127.0.0.1 --port 8002
pause
