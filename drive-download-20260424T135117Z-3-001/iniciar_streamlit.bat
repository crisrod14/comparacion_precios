@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist "venv\Scripts\python.exe" (
    echo No se encontro venv. Crea el entorno: python -m venv venv
    pause
    exit /b 1
)
echo Iniciando Revisión de Precios WOM...
echo Abre el navegador en: http://localhost:8501
start "" "http://localhost:8501"
"venv\Scripts\python.exe" -m streamlit run streamlit_app.py
pause
