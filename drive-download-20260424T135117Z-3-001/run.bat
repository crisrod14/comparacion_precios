@echo off
chcp 65001 >nul
echo Iniciando sistema de comparacion de precios WOM...
echo.

if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
) else (
    echo Creando entorno virtual...
    python -m venv venv
    call venv\Scripts\activate.bat
)

echo Instalando dependencias...
pip install -r requirements.txt -q
playwright install chromium 2>nul

echo.
echo Iniciando dashboard en http://localhost:5000
echo Presiona Ctrl+C para detener.
echo.
python main.py
