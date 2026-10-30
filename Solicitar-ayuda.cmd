@echo off
cd /d "%~dp0"
python "%~dp0request_gui.py"
if errorlevel 1 pause
