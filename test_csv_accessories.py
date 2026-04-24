#!/usr/bin/env python3
"""
Test para verificar que los accesorios del CSV se leen correctamente.
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

def test_csv():
    print("🔍 Probando lectura de CSV de accesorios...\n")

    from src.data_sources.csv_reader import get_csv_accessories

    csv_path = PROJECT_ROOT / "Precios MOM Days Accesorios.csv"

    if not csv_path.exists():
        print(f"❌ Archivo no encontrado: {csv_path}")
        return False

    print(f"📂 Leyendo: {csv_path}\n")

    accesorios = get_csv_accessories(csv_path)

    print(f"✓ Lectura completada\n")
    print(f"📊 Total accesorios: {len(accesorios)}")
    print(f"📋 Columnas: {list(accesorios.columns)}\n")

    print("📝 Primeros 10 accesorios:\n")
    print(accesorios.head(10)[["sku", "name", "price", "modality"]].to_string(index=False))

    print(f"\n✅ CSV de accesorios se lee correctamente!")
    return True


if __name__ == "__main__":
    success = test_csv()
    sys.exit(0 if success else 1)
