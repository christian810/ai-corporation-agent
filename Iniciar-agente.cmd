@echo off
cd /d "%~dp0"
if exist "%LOCALAPPDATA%\AI Corporation Agent\update_supervisor.py" (
  python "%LOCALAPPDATA%\AI Corporation Agent\update_supervisor.py"
  exit /b
)
echo Iniciando agente actualizado. Cierra esta ventana para detenerlo.
echo Usa este inicio despues de reiniciar Windows para evitar otro agente ya abierto.
python "%~dp0agent.py" --config "%LOCALAPPDATA%\AI Corporation Agent\config.json"
pause
