@echo off
cd /d "%~dp0"
python --version >nul 2>&1
if errorlevel 1 (
  echo Instala Python 3.12 o posterior desde python.org y activa Add Python to PATH.
  pause
  exit /b 1
)
python -c "import sys, tkinter; sys.exit(0 if sys.version_info >= (3,12) else 1)"
if errorlevel 1 (
  echo Se requiere Python 3.12 o posterior con Tcl/Tk instalado.
  pause
  exit /b 1
)
python "%~dp0setup_gui.py"
if errorlevel 1 pause
