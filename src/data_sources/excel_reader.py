"""
Reader for Excel files - WOM price reference data.
Supports multiple sheets, config-based column mapping, and auto-detection.
"""
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import pandas as pd


def normalize_descuento_pct(value: Any) -> Optional[float]:
    """
    Convierte descriptor a float porcentaje (0-100).
    Acepta:
    - Formato decimal: -0,399899998 (coma decimal) -> 39.99%
    - Formato porcentaje: 28, '28%', '28' -> 28.0
    """
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


def normalize_price(value: Any) -> Optional[float]:
    """Convert price string/number to float. Handles Chilean format ($599.990)."""
    if pd.isna(value):
        return None
    if isinstance(value, (int, float)):
        return float(value) if value > 0 else None
    if isinstance(value, str):
        value = value.strip()
        if value.upper() in ('N/A', 'NA', '-', ''):
            return None
        # Remove currency symbols, spaces, and keep digits, comma, dot, minus
        cleaned = re.sub(r'[^\d.,\-]', '', value.replace(' ', ''))
        cleaned = cleaned.replace('.', '').replace(',', '.')
        try:
            result = float(cleaned)
            return result if result > 0 else None
        except ValueError:
            return None
    return None


def detect_columns(df: pd.DataFrame) -> Dict[str, Optional[str]]:
    """
    Auto-detect column names for SKU, name, and price.
    Returns dict with keys: sku, name, price
    """
    columns_lower = {str(c).lower(): c for c in df.columns}
    result = {'sku': None, 'name': None, 'price': None}

    sku_keywords = [
        'sku', 'código', 'codigo', 'modelo', 'model', 'referencia', 'articulo',
        'cod'  # "cod" for partial match
    ]
    name_keywords = [
        'nombre', 'producto', 'equipo', 'descripción', 'descripcion', 'titulo',
        'modelo'  # Modelo can be name too
    ]
    price_keywords = [
        'precio', 'price', 'valor', 'pvp', 'venta', 'costo', 'normal',
        'precio normal', 'precio de venta'
    ]

    for col_name, col in columns_lower.items():
        for kw in sku_keywords:
            if kw in col_name and result['sku'] is None:
                if col_name == 'modelo' and result['name'] is None:
                    continue  # Prefer modelo for name if we have SKU
                result['sku'] = col
                break
        for kw in name_keywords:
            if kw in col_name and result['name'] is None:
                result['name'] = col
                break
        for kw in price_keywords:
            if kw in col_name and result['price'] is None:
                result['price'] = col
                break

    return result


def detect_descuento_column(df: pd.DataFrame, hint: Optional[str] = None) -> Optional[str]:
    """Detecta columna de % descuento. Prioriza hint si existe en df.columns."""
    if hint and hint in df.columns:
        return hint
    for col in df.columns:
        cl = str(col).lower()
        if any(kw in cl for kw in ("dcto", "descuento", "discount", "%")):
            return col
    return None


def _read_sheet(
    path: Path,
    sheet_name: str,
    sku_col: Optional[str] = None,
    name_col: Optional[str] = None,
    price_col: Optional[str] = None,
    modalities: Optional[List[Dict]] = None,
    estado_comercial: Optional[Dict] = None,
    descuento_pct_col: Optional[str] = None,
) -> pd.DataFrame:
    """
    Read a single sheet and return normalized DataFrame.
    If modalities is provided, reads one row per (sku, modality) with price per modality.
    estado_comercial: {"column": "Estado Comercial", "include": ["En Oferta", "Lanzamiento"]}
    - Excluye "End of Life" y cualquier valor distinto a los estados incluidos.
    """
    df = pd.read_excel(path, sheet_name=sheet_name)
    cols = detect_columns(df)

    # Filtrar por Estado Comercial si está configurado
    if estado_comercial:
        col_name = estado_comercial.get("column", "Estado Comercial")
        include_list = estado_comercial.get("include") or []
        if col_name in df.columns and include_list:
            include_set = {str(s).strip() for s in include_list}
            df = df[df[col_name].fillna("").astype(str).str.strip().isin(include_set)]

    sku_col = sku_col or cols['sku']
    name_col = name_col or cols['name']
    price_col = price_col or cols['price']
    descuento_pct_col = detect_descuento_column(df, descuento_pct_col)

    result = pd.DataFrame()
    if sku_col and sku_col in df.columns:
        result['sku'] = df[sku_col].fillna('').astype(str).str.strip()
    else:
        result['sku'] = df.index.astype(str)

    if name_col and name_col in df.columns:
        result['name'] = df[name_col].fillna('').astype(str).str.strip()
    else:
        result['name'] = result['sku']

    if modalities:
        rows = []
        for _, row in df.iterrows():
            sku = str(row[sku_col]).strip() if sku_col in df.columns else ''
            name = str(row.get(name_col, '')).strip() if name_col in df.columns else sku
            if not sku or sku == 'nan':
                continue
            for mod in modalities:
                excel_col = mod.get("excel_column")
                mod_id = mod.get("id", excel_col)
                if excel_col and excel_col in df.columns:
                    price = normalize_price(row[excel_col])
                    if price and price > 0:
                        row_data = {
                            'sku': sku,
                            'name': name,
                            'modality': mod_id,
                            'price': price,
                        }
                        # Descuento por modalidad (excel_column_descuento) o global (descuento_pct_col)
                        desc_col = mod.get("excel_column_descuento") or descuento_pct_col
                        if desc_col and desc_col in df.columns:
                            desc = normalize_descuento_pct(row.get(desc_col))
                            if desc is not None:
                                row_data['descuento_pct_ref'] = desc
                        elif descuento_pct_col and descuento_pct_col in df.columns:
                            desc = normalize_descuento_pct(row.get(descuento_pct_col))
                            if desc is not None:
                                row_data['descuento_pct_ref'] = desc
                        rows.append(row_data)
        result = pd.DataFrame(rows)
    else:
        if price_col and price_col in df.columns:
            result['price'] = df[price_col].apply(normalize_price)
        else:
            result['price'] = None
        result['modality'] = 'accesorios'  # Hoja sin modalidades (ej. Accesorios)
        result = result.dropna(subset=['price'])
        result = result[result['price'].notna() & (result['price'] > 0)]

    result = result[result['sku'].str.len() > 0]
    result = result.reset_index(drop=True)
    return result


def _read_csv_equipment(
    file_path: Path,
    sku_col: Optional[str] = None,
    name_col: Optional[str] = None,
    price_col: Optional[str] = None,
    modalities: Optional[List[Dict]] = None,
) -> pd.DataFrame:
    """Lee CSV de equipos (similar a read_csv_accessories pero con soporte a modalidades)."""
    try:
        df = pd.read_csv(file_path, sep=';', dtype=str)
    except:
        df = pd.read_csv(file_path, dtype=str)

    cols = detect_columns(df)
    sku_col = sku_col or cols['sku']
    name_col = name_col or cols['name']
    price_col = price_col or cols['price']

    result_rows = []
    for _, row in df.iterrows():
        sku = str(row.get(sku_col, '')).strip() if sku_col in df.columns else ''
        name = str(row.get(name_col, '')).strip() if name_col in df.columns else sku
        if not sku or sku == 'nan':
            continue

        if modalities:
            for mod in modalities:
                excel_col = mod.get("excel_column")
                mod_id = mod.get("id", excel_col)
                if excel_col and excel_col in df.columns:
                    price = normalize_price(row[excel_col])
                    if price and price > 0:
                        row_data = {
                            'sku': sku,
                            'name': name,
                            'modality': mod_id,
                            'price': price,
                        }
                        result_rows.append(row_data)
        else:
            price = normalize_price(row.get(price_col, '')) if price_col in df.columns else None
            if price and price > 0:
                result_rows.append({
                    'sku': sku,
                    'name': name,
                    'price': price,
                })

    return pd.DataFrame(result_rows)


def read_excel_reference(
    file_path: Union[str, Path],
    sheet_name: Optional[str] = None,
    sku_col: Optional[str] = None,
    name_col: Optional[str] = None,
    price_col: Optional[str] = None,
    sheet_configs: Optional[List[Dict]] = None,
    estado_comercial: Optional[Dict] = None,
) -> pd.DataFrame:
    """
    Read Excel or CSV file and return normalized product reference data.
    Returns DataFrame with columns: sku, name, price

    If sheet_configs is provided (from config), reads multiple sheets and combines.
    Each config: {"name": "SheetName", "sku": "Col", "name": "Col", "price": "Col"}
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Archivo no encontrado: {file_path}")

    # Detectar si es CSV o Excel
    if str(path).lower().endswith('.csv'):
        if sheet_configs:
            # Para CSV, usar el primer sheet_config
            sheet_cfg = sheet_configs[0] if sheet_configs else {}
            return _read_csv_equipment(
                path,
                sku_col=sheet_cfg.get("sku"),
                name_col=sheet_cfg.get("name"),
                price_col=sheet_cfg.get("price"),
                modalities=sheet_cfg.get("modalities"),
            )
        else:
            return _read_csv_equipment(path, sku_col, name_col, price_col)

    if sheet_configs:
        dfs = []
        for sheet_cfg in sheet_configs:
            sheet_name_cfg = sheet_cfg.get("sheet") or sheet_cfg.get("name")
            if not sheet_name_cfg:
                continue
            modalities = sheet_cfg.get("modalities")
            df = _read_sheet(
                path,
                sheet_name=sheet_name_cfg,
                sku_col=sheet_cfg.get("sku"),
                name_col=sheet_cfg.get("name"),
                price_col=sheet_cfg.get("price"),
                modalities=modalities,
                estado_comercial=estado_comercial,
                descuento_pct_col=sheet_cfg.get("descuento_pct"),
            )
            if not df.empty:
                dfs.append(df)
        if not dfs:
            raise ValueError("No se pudieron leer hojas desde la configuración")
        combined = pd.concat(dfs, ignore_index=True)
        if "modality" in combined.columns and combined["modality"].notna().any():
            combined = combined.drop_duplicates(subset=["sku", "modality"], keep="first")
        else:
            combined = combined.drop_duplicates(subset=["sku"], keep="first")
        return combined

    if sheet_name and sheet_name != "auto-detect":
        return _read_sheet(path, sheet_name, sku_col, name_col, price_col)

    xl = pd.ExcelFile(path)
    df = pd.read_excel(path, sheet_name=xl.sheet_names[0])
    cols = detect_columns(df)
    return _read_sheet(
        path,
        xl.sheet_names[0],
        sku_col or cols['sku'],
        name_col or cols['name'],
        price_col or cols['price'],
    )


def get_excel_sheets(file_path: Union[str, Path]) -> List[str]:
    """Get list of sheet names from Excel file."""
    return pd.ExcelFile(file_path).sheet_names
