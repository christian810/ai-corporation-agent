@echo off
cd /d "%~dp0"
if exist "%LOCALAPPDATA%\AI Corporation Agent\update_supervisor.py" (
  python "%LOCALAPPDATA%\AI Corporation Agent\update_supervisor.py" --tool request_gui.py
  exit /b
)
python "%~dp0request_gui.py"
if errorlevel 1 pause
