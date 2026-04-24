"""
Price comparison logic: Excel/DB reference vs website scraped prices.
Supports modality-specific comparison (portabilidad, renovación, línea nueva, etc).
Matches by name when SKU formats differ (Excel: 001.002.2393, Web: SM-A546E-256GB).
"""
import re
import unicodedata
from typing import Optional

import pandas as pd


def normalize_name_for_match(name: str) -> str:
    """Normaliza nombre para matching: minúsculas, sin acentos, sin espacios extras."""
    if not name or pd.isna(name):
        return ""
    s = str(name).lower().strip()
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def names_match(name_ref: str, name_web: str, min_len: int = 5) -> bool:
    """True si los nombres ref y web coinciden (normalizados, contiene o es contenido)."""
    n_ref = normalize_name_for_match(name_ref)
    n_web = normalize_name_for_match(name_web)
    if not n_ref or not n_web:
        return False
    if len(n_ref) < min_len and len(n_web) < min_len:
        return False
    return n_ref in n_web or n_web in n_ref


def compare_prices(
    reference_df: pd.DataFrame,
    website_df: pd.DataFrame,
    tolerance_percent: float = 1.0,
    match_by_sku: bool = True,
) -> pd.DataFrame:
    """
    Compare reference prices with website prices.
    When modality is present, matches by (sku, modality).
    Returns DataFrame with: sku, name, modality, price_reference, price_website,
    difference, diff_percent, status, url
    """
    ref = reference_df.copy()
    web = website_df.copy()

    # Asegurar columnas necesarias (evita KeyError si DataFrame vacío o estructura inesperada)
    for col in ['sku', 'name', 'modality', 'price']:
        if col not in ref.columns:
            ref[col] = '' if col in ('sku', 'name', 'modality') else None
        if col not in web.columns:
            web[col] = '' if col in ('sku', 'name', 'modality') else None

    def normalize_sku(s):
        """Normaliza SKU: mayúsculas, elimina espacios pero preserva puntos."""
        s = str(s).strip().upper()
        s = re.sub(r'\s+', '', s)  # Solo elimina espacios, no puntos
        return s

    ref['sku'] = ref['sku'].astype(str).apply(normalize_sku)
    web['sku'] = web['sku'].fillna('').astype(str).apply(normalize_sku)
    if 'parent_sku' in web.columns:
        web['parent_sku'] = web['parent_sku'].fillna('').astype(str).str.strip().str.upper().str.replace(' ', '')
    else:
        web['parent_sku'] = web['sku']
    if 'name' not in web.columns:
        web['name'] = web['sku']
    if 'modality' not in ref.columns:
        ref['modality'] = None
    if 'modality' not in web.columns:
        web['modality'] = None

    ref = ref.dropna(subset=['price'])
    ref = ref[ref['price'] > 0]

    results = []
    use_modality = (
        ref['modality'].notna().any() and ref['modality'].ne('').any()
        and web['modality'].notna().any() and web['modality'].ne('').any()
    )

    web_mod = web['modality'].fillna('') if 'modality' in web.columns else pd.Series([''] * len(web))

    for _, row in ref.iterrows():
        sku = row['sku']
        name = row.get('name', sku)
        modality = row.get('modality') or ''
        price_ref = float(row['price'])
        descuento_pct_ref = row.get('descuento_pct_ref')
        if descuento_pct_ref is not None and pd.notna(descuento_pct_ref):
            descuento_pct_ref = float(descuento_pct_ref)
        else:
            descuento_pct_ref = None

        candidatos = web[web_mod == modality] if (use_modality and modality) else web

        # Priorizar SKU cuando la API lo entrega: sku o parent_sku
        match = candidatos.iloc[0:0]
        if sku:
            match = candidatos[candidatos['sku'] == sku]
            if match.empty and 'parent_sku' in candidatos.columns:
                match = candidatos[candidatos['parent_sku'] == sku]
        if match.empty and name:
            for idx, wrow in candidatos.iterrows():
                if names_match(name, str(wrow.get('name', ''))):
                    match = candidatos.loc[[idx]]
                    break
        if match.empty and match_by_sku and sku:
            match = candidatos[candidatos['name'].str.upper().str.contains(sku[:8], na=False)]
        if match.shape[0] > 1:
            match = match.head(1)

        if match.empty:
            r = {
                'sku': sku,
                'name': name,
                'modality': modality or None,
                'price_reference': price_ref,
                'price_website': None,
                'precio_normal_web': None,
                'precio_descuento_web': None,
                'precio_normal_sin_precio': False,
                'difference': None,
                'diff_percent': None,
                'status': 'NO_ENCONTRADO',
                'url': None,
            }
            if descuento_pct_ref is not None:
                r['descuento_pct_ref'] = descuento_pct_ref
            results.append(r)
            continue

        match_row = match.iloc[0]
        price_web = float(match_row['price'])
        url = match_row.get('url', '')
        precio_normal_web = match_row.get('precio_normal')
        precio_descuento_web = match_row.get('precio_descuento')
        precio_normal_sin_precio = bool(match_row.get('precio_normal_sin_precio', False))
        if precio_normal_web is not None and pd.notna(precio_normal_web):
            precio_normal_web = float(precio_normal_web)
        else:
            precio_normal_web = None
        if precio_descuento_web is not None and pd.notna(precio_descuento_web):
            precio_descuento_web = float(precio_descuento_web)
        else:
            precio_descuento_web = None

        if price_web is None or price_web <= 0:
            r = {
                'sku': sku,
                'name': name,
                'modality': modality or None,
                'price_reference': price_ref,
                'price_website': None,
                'precio_normal_web': precio_normal_web,
                'precio_descuento_web': precio_descuento_web,
                'precio_normal_sin_precio': precio_normal_sin_precio,
                'difference': None,
                'diff_percent': None,
                'status': 'SIN_PRECIO_WEB',
                'url': url,
            }
            if descuento_pct_ref is not None:
                r['descuento_pct_ref'] = descuento_pct_ref
            results.append(r)
            continue

        diff = price_web - price_ref
        diff_pct = (diff / price_ref * 100) if price_ref else 0

        if abs(diff_pct) <= tolerance_percent:
            status = 'OK'
        elif abs(diff_pct) <= 5:
            status = 'MODERADA'
        else:
            status = 'CRITICA'

        # Si "Precio normal" muestra "Sin precio" en la web, es error crítico
        if precio_normal_sin_precio:
            status = 'PRECIO_NORMAL_SIN_PRECIO'
        r = {
            'sku': sku,
            'name': name,
            'modality': modality or None,
            'price_reference': price_ref,
            'price_website': price_web,
            'precio_normal_web': precio_normal_web,
            'precio_descuento_web': precio_descuento_web,
            'precio_normal_sin_precio': precio_normal_sin_precio,
            'difference': diff,
            'diff_percent': round(diff_pct, 2),
            'status': status,
            'url': url,
        }
        if descuento_pct_ref is not None:
            r['descuento_pct_ref'] = descuento_pct_ref
        results.append(r)

    ref_keys = set(
        (str(r.get('name', '')).strip().upper(), r.get('modality') or '')
        for r in results
    )
    for _, row in web.iterrows():
        name_w = str(row.get('name', '')).strip()
        mod = str(row.get('modality', '')).strip()
        key = (name_w.upper(), mod)
        if name_w and key not in ref_keys:
            ref_keys.add(key)
            pn_val = row.get('precio_normal')
            pd_val = row.get('precio_descuento')
            pn_val = float(pn_val) if pn_val is not None and pd.notna(pn_val) else None
            pd_val = float(pd_val) if pd_val is not None and pd.notna(pd_val) else None
            pn_sin = bool(row.get('precio_normal_sin_precio', False))
            status_nuevo = 'PRECIO_NORMAL_SIN_PRECIO' if pn_sin else 'NUEVO_EN_WEB'
            results.append({
                'sku': row.get('sku', ''),
                'name': row.get('name', ''),
                'modality': mod or None,
                'price_reference': None,
                'price_website': float(row['price']) if row['price'] else None,
                'precio_normal_web': pn_val,
                'precio_descuento_web': pd_val,
                'precio_normal_sin_precio': pn_sin,
                'difference': None,
                'diff_percent': None,
                'status': status_nuevo,
                'url': row.get('url', ''),
            })

    return pd.DataFrame(results)


def to_distinct_by_sku(results_df: pd.DataFrame) -> pd.DataFrame:
    """
    Agrupa resultados por SKU único: una fila por producto, modalidades como columnas.
    Evita SKUs repetidos en el informe.
    """
    if results_df.empty:
        return results_df

    df = results_df.copy()
    df["name"] = df["name"].fillna("").astype(str)
    df["sku"] = df["sku"].fillna("").astype(str)
    # Orden de severidad para resumen (peor primero)
    severity = {
        "PRECIO_NORMAL_SIN_PRECIO": 5,
        "CRITICA": 4,
        "SIN_PRECIO_WEB": 3,
        "MODERADA": 2,
        "NO_ENCONTRADO": 2,
        "NUEVO_EN_WEB": 1,
        "OK": 0,
    }

    def _cell_summary(row) -> str:
        """Formato compacto: Ref/Web y estado."""
        ref = row.get("price_reference")
        web = row.get("price_website")
        status = row.get("status", "")
        try:
            ref_val = float(ref) if ref is not None and pd.notna(ref) else None
        except (TypeError, ValueError):
            ref_val = None
        try:
            web_val = float(web) if web is not None and pd.notna(web) else None
        except (TypeError, ValueError):
            web_val = None
        ref_str = f"${ref_val:,.0f}" if ref_val and ref_val > 0 else "-"
        web_str = f"${web_val:,.0f}" if web_val and web_val > 0 else "-"
        short = {
            "OK": "OK",
            "CRITICA": "CR",
            "MODERADA": "MOD",
            "NO_ENCONTRADO": "No enc",
            "NUEVO_EN_WEB": "Nuevo",
            "SIN_PRECIO_WEB": "Sin precio",
            "PRECIO_NORMAL_SIN_PRECIO": "Sin precio N",
        }.get(status, status[:6] if status else "")
        return f"{ref_str} / {web_str} ({short})"

    modalities = df["modality"].dropna().unique().tolist()
    modalities = [m for m in modalities if str(m).strip()]

    rows_distinct = []
    for (sku, name), group in df.groupby(["sku", "name"]):
        group = group.fillna("")
        row_out = {"sku": sku, "producto": name, "url": ""}
        status_counts = {}
        worst_status = "OK"
        worst_sev = -1

        for _, r in group.iterrows():
            mod = r.get("modality") or ""
            if mod:
                row_out[f"mod_{mod}"] = _cell_summary(r)
                st = r.get("status", "")
                status_counts[st] = status_counts.get(st, 0) + 1
                sev = severity.get(st, 0)
                if sev > worst_sev:
                    worst_sev = sev
                    worst_status = st

            url = r.get("url") or ""
            if url and not row_out["url"]:
                row_out["url"] = url

            if "descuento_pct_ref" not in row_out or row_out.get("descuento_pct_ref") is None:
                dct = r.get("descuento_pct_ref")
                if dct is not None and pd.notna(dct) and dct != "":
                    try:
                        row_out["descuento_pct_ref"] = float(dct)
                    except (TypeError, ValueError):
                        pass

        resumen = ", ".join(f"{c} {s}" for s, c in sorted(status_counts.items(), key=lambda x: -severity.get(x[0], 0)))
        row_out["resumen"] = resumen
        row_out["peor_estado"] = worst_status

        rows_distinct.append(row_out)

    out = pd.DataFrame(rows_distinct)
    # Ordenar columnas: sku, producto, mod_*, resumen, peor_estado, url
    mod_cols = [c for c in out.columns if c.startswith("mod_")]
    order = ["sku", "producto", "descuento_pct_ref"] + sorted(mod_cols) + ["resumen", "peor_estado", "url"]
    order = [c for c in order if c in out.columns]
    return out[[c for c in order if c in out.columns]]
