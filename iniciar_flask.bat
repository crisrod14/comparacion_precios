@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist "venv\Scripts\python.exe" (
    echo No se encontro venv.
    pause
    exit /b 1
)
echo Iniciando dashboard Flask en http://localhost:5000
start "" "http://localhost:5000"
"venv\Scripts\python.exe" -m src.dashboard.app
pause
