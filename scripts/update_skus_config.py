"""
Script para leer SKUs del Excel y actualizar config.yaml automáticamente.
Ejecución: python scripts/update_skus_config.py [excel_file]
"""
import sys
from pathlib import Path
import pandas as pd
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent

def read_excel_skus(excel_path: str) -> set:
    """Lee todos los SKUs únicos del Excel de equipos."""
    try:
        df = pd.read_excel(excel_path, sheet_name="Equipos")
        skus = set(df['SKU'].dropna().unique())
        skus = {str(s).strip() for s in skus if s}
        return skus
    except Exception as e:
        print(f"Error leyendo Excel: {e}")
        return set()

def update_config_skus(skus: set):
    """Actualiza config.yaml con los SKUs nuevos."""
    config_path = PROJECT_ROOT / "config" / "config.yaml"

    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    # Leer SKUs existentes en config
    existing_skus = set(
        s.strip()
        for s in config['website']['api']['skus'].split(',')
        if s.strip()
    )

    # Combinar: mantener existentes + agregar nuevos
    combined_skus = sorted(list(existing_skus | skus))

    # Actualizar config
    config['website']['api']['skus'] = ','.join(combined_skus)

    # Guardar
    with open(config_path, 'w', encoding='utf-8') as f:
        yaml.dump(config, f, allow_unicode=True, sort_keys=False)

    print(f"✅ Config actualizado: {len(combined_skus)} SKUs totales")
    print(f"   {len(skus - existing_skus)} SKUs nuevos agregados")

if __name__ == "__main__":
    excel_file = sys.argv[1] if len(sys.argv) > 1 else "Precios depurados.xlsx"
    excel_path = PROJECT_ROOT / excel_file

    if not excel_path.exists():
        print(f"❌ Archivo no encontrado: {excel_path}")
        sys.exit(1)

    print(f"📖 Leyendo SKUs de: {excel_file}")
    skus = read_excel_skus(str(excel_path))

    if not skus:
        print("❌ No se encontraron SKUs en el Excel")
        sys.exit(1)

    print(f"📊 {len(skus)} SKUs únicos encontrados")
    update_config_skus(skus)
