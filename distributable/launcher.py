#!/usr/bin/env python
"""
Launcher para la aplicación Streamlit de Precios WOM.
Este script inicia la aplicación automáticamente en tu navegador.
"""
import subprocess
import sys
import os
from pathlib import Path

def main():
    project_root = Path(__file__).resolve().parent.parent
    app_path = project_root / "streamlit_app.py"

    if not app_path.exists():
        print(f"❌ Error: No se encontró streamlit_app.py en {project_root}")
        sys.exit(1)

    print("🚀 Iniciando aplicación WOM Precios...")
    print(f"📂 Carpeta: {project_root}")

    try:
        subprocess.run(
            [sys.executable, "-m", "streamlit", "run", str(app_path)],
            cwd=str(project_root),
            check=True
        )
    except KeyboardInterrupt:
        print("\n⏹️  Aplicación detenida.")
    except FileNotFoundError:
        print("❌ Error: Streamlit no está instalado.")
        print("   Ejecuta: pip install -r requirements.txt")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
