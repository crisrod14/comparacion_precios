"""
Punto de entrada principal - Sistema de Comparación de Precios WOM.
Ejecuta el dashboard web.
"""
import sys
from pathlib import Path

# Asegurar que el proyecto root está en el path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.dashboard.app import main

if __name__ == "__main__":
    main()
