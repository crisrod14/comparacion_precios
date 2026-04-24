"""
Script para analizar la estructura del archivo Excel de WOM.
Identifica hojas, columnas, identificadores y precios.
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    import pandas as pd
except ImportError:
    print("Instalando pandas y openpyxl...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pandas", "openpyxl"])
    import pandas as pd


def analyze_excel(file_path: str) -> None:
    """Analiza la estructura del archivo Excel."""
    path = Path(file_path)
    if not path.exists():
        print(f"ERROR: Archivo no encontrado: {file_path}")
        return

    print("=" * 80)
    print("ANÁLISIS DEL ARCHIVO EXCEL - WOM")
    print("=" * 80)
    print(f"Archivo: {path.name}\n")

    xl = pd.ExcelFile(path)
    sheets = xl.sheet_names

    print("1. HOJAS DEL ARCHIVO")
    print("-" * 40)
    for i, sheet in enumerate(sheets, 1):
        print(f"  {i}. {sheet}")
    print()

    for sheet_name in sheets:
        print("=" * 80)
        print(f"2. HOJA: '{sheet_name}'")
        print("=" * 80)

        df = pd.read_excel(path, sheet_name=sheet_name)
        columns = df.columns.tolist()

        print(f"\nColumnas ({len(columns)}):")
        for j, col in enumerate(columns, 1):
            non_null = df[col].notna().sum()
            print(f"  {j:2}. {col} (valores: {non_null})")

        print(f"\nPrimeros 5 registros:")
        print("-" * 80)
        print(df.head().to_string())

        # Identificadores potenciales
        id_keywords = [
            'sku', 'código', 'codigo', 'id', 'modelo', 'model', 'referencia',
            'articulo', 'producto', 'equipo', 'nombre', 'descripción', 'descripcion'
        ]
        print(f"\nColumnas como identificadores:")
        for col in columns:
            col_lower = str(col).lower()
            if any(kw in col_lower for kw in id_keywords):
                nunique = df[col].nunique()
                print(f"  - {col}: {nunique} valores únicos")

        # Columnas de precios
        price_keywords = ['precio', 'price', 'valor', 'costo', 'pvp', 'venta']
        print(f"\nColumnas de precios:")
        for col in columns:
            col_lower = str(col).lower()
            if any(kw in col_lower for kw in price_keywords):
                sample = df[col].dropna().head(3).tolist()
                print(f"  - {col}: ejemplos = {sample}")
        print("\n")


if __name__ == "__main__":
    default_path = project_root / "Precios depurados.xlsx"
    if not default_path.exists():
        default_path = project_root / "2026_02_10 Resumen Oferta de Equipos y Accesorios WOM v26.2.1v2.xlsx"
    file_path = sys.argv[1] if len(sys.argv) > 1 else str(default_path)
    analyze_excel(file_path)
