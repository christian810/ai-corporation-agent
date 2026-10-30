@echo off
cd /d "%~dp0"
python "%~dp0update_setup.py"
if errorlevel 1 pause
