@echo off
REM Script para generar el ejecutable de la aplicación WOM Precios
REM Requiere: Python 3.8+ instalado

setlocal enabledelayedexpansion

echo.
echo ========================================
echo  Generador de Ejecutable - WOM Precios
echo ========================================
echo.

REM Verificar si Python está instalado
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python no está instalado o no está en PATH
    echo Descarga Python desde: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [OK] Python detectado
echo.

REM Instalar PyInstaller si no existe
echo Verificando PyInstaller...
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo Instalando PyInstaller...
    pip install pyinstaller
)

echo.
echo Instalando dependencias del proyecto...
pip install -r requirements.txt

echo.
echo Generando ejecutable...
echo.

REM Crear el ejecutable
pyinstaller --onefile ^
    --windowed ^
    --name "WOM_Precios" ^
    --icon launcher.ico ^
    --add-data "../streamlit_app.py:." ^
    --add-data "../src:src" ^
    --add-data "../config:config" ^
    --add-data "../data:data" ^
    launcher.py

if errorlevel 1 (
    echo.
    echo [ERROR] Hubo un problema al generar el ejecutable
    pause
    exit /b 1
)

echo.
echo ========================================
echo [EXITO] Ejecutable creado
echo ========================================
echo.
echo El archivo se encuentra en:
echo   distributable\dist\WOM_Precios.exe
echo.
echo Para compartirlo:
echo   1. Copia "WOM_Precios.exe" a una carpeta
echo   2. Envíalo por email o crea un ZIP
echo.
pause
