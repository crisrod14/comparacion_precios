"""
Reader para CSV de accesorios - WOM price reference data.
"""
from pathlib import Path
from typing import Optional, Union
import pandas as pd
import re


def normalize_price(value) -> Optional[float]:
    """Convert price string/number to float. Handles Chilean format ($599.990)."""
    if pd.isna(value):
        return None
    if isinstance(value, (int, float)):
        return float(value) if value > 0 else None
    if isinstance(value, str):
        value = value.strip()
        if value.upper() in ('N/A', 'NA', '-', ''):
            return None
        cleaned = re.sub(r'[^\d.,\-]', '', value.replace(' ', ''))
        cleaned = cleaned.replace('.', '').replace(',', '.')
        try:
            result = float(cleaned)
            return result if result > 0 else None
        except ValueError:
            return None
    return None


def normalize_descuento_pct(value) -> Optional[float]:
    """Convierte descriptor a float porcentaje (0-100)."""
    if pd.isna(value):
        return None
    if isinstance(value, (int, float)):
        v = float(value)
    elif isinstance(value, str):
        cleaned = re.sub(r'[^\d.,\-]', '', value.strip().replace(',', '.'))
        try:
            v = float(cleaned)
        except ValueError:
            return None
    else:
        return None

    # Formato decimal (-1 a 0): -0.40 -> 40%
    if -1 <= v <= 0:
        return round(abs(v) * 100, 2)
    # Formato decimal (0 a 1): 0.40 -> 40%
    if 0 < v <= 1:
        return round(v * 100, 2)
    # Ya es porcentaje (0-100)
    if 0 <= v <= 100:
        return round(v, 2)
    return None


def read_csv_accessories(
    file_path: Union[str, Path],
    modelo_col: str = "Modelo",
    sku_col: str = "SKU",
    precio_col: str = "Precio",
    precio_normal_col: Optional[str] = "Precio Normal",
    descuento_col: Optional[str] = "% Descuento",
) -> pd.DataFrame:
    """
    Lee CSV de accesorios y retorna DataFrame normalizado.
    Retorna DataFrame con columnas: sku, name, price, modality, descuento_pct_ref
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Archivo no encontrado: {file_path}")

    # Leer CSV con separador por punto y coma
    df = pd.read_csv(path, sep=';', dtype=str)

    result_rows = []
    for _, row in df.iterrows():
        sku = str(row.get(sku_col, '')).strip() if sku_col in df.columns else ''
        name = str(row.get(modelo_col, '')).strip() if modelo_col in df.columns else sku
        price_raw = row.get(precio_col, '') if precio_col in df.columns else None
        precio_normal_raw = row.get(precio_normal_col, '') if precio_normal_col in df.columns else None
        descuento_raw = row.get(descuento_col, '') if descuento_col in df.columns else None

        if not sku or sku == 'nan' or not name:
            continue

        price = normalize_price(price_raw)
        if price is None or price <= 0:
            continue

        row_data = {
            'sku': sku,
            'name': name,
            'price': price,
            'modality': 'accesorios',
        }

        # Precio normal (sin descuento)
        precio_normal = normalize_price(precio_normal_raw)
        if precio_normal is not None and precio_normal > 0:
            row_data['precio_normal'] = precio_normal

        # Descuento porcentaje
        descuento_pct = normalize_descuento_pct(descuento_raw)
        if descuento_pct is not None:
            row_data['descuento_pct_ref'] = descuento_pct

        result_rows.append(row_data)

    result = pd.DataFrame(result_rows)
    return result


def get_csv_accessories(file_path: Union[str, Path]) -> pd.DataFrame:
    """Lee accesorios desde CSV o Excel."""
    path = Path(file_path)
    if not path.exists():
        return pd.DataFrame(columns=['sku', 'name', 'price', 'modality'])

    # Detectar si es Excel o CSV
    if str(path).lower().endswith(('.xlsx', '.xls')):
        try:
            df = pd.read_excel(path)
        except Exception:
            return pd.DataFrame(columns=['sku', 'name', 'price', 'modality'])
    else:
        try:
            return read_csv_accessories(file_path)
        except Exception:
            return pd.DataFrame(columns=['sku', 'name', 'price', 'modality'])

    # Procesar Excel igual que CSV
    result_rows = []
    for _, row in df.iterrows():
        sku = str(row.get('SKU', '')).strip() if 'SKU' in df.columns else ''
        name = str(row.get('Modelo', '')).strip() if 'Modelo' in df.columns else sku
        precio_raw = row.get('Precio', '')
        precio_normal_raw = row.get('Precio Normal', '')
        descuento_raw = row.get('% Descuento', '')

        if not sku or sku == 'nan' or not name:
            continue

        price = normalize_price(precio_raw)
        if price is None or price <= 0:
            continue

        row_data = {
            'sku': sku,
            'name': name,
            'price': price,
            'modality': 'accesorios',
        }

        precio_normal = normalize_price(precio_normal_raw)
        if precio_normal is not None and precio_normal > 0:
            row_data['precio_normal'] = precio_normal

        descuento_pct = normalize_descuento_pct(descuento_raw)
        if descuento_pct is not None:
            row_data['descuento_pct_ref'] = descuento_pct

        result_rows.append(row_data)

    result = pd.DataFrame(result_rows)
    return result if not result.empty else pd.DataFrame(columns=['sku', 'name', 'price', 'modality'])
