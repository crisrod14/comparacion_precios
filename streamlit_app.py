"""
Streamlit app para comparación de precios WOM Store.
Desplegable gratuitamente en Streamlit Community Cloud.
"""
from io import BytesIO
from pathlib import Path
import sys
import tempfile
from typing import Optional

import pandas as pd
import streamlit as st
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.data_sources.excel_reader import read_excel_reference
from src.data_sources.csv_reader import get_csv_accessories
from src.comparator.price_comparator import compare_prices, to_distinct_by_sku
from src.scraper.wom_api_client import fetch_products_from_api

USAGE_MD = """
### Cómo usar

1. **📋 Equipos**: Sube tu Excel o CSV con equipos (SKU, Modelo, precios por modalidad)
2. **🎧 Accesorios**: Sube tu Excel o CSV con accesorios (SKU, Modelo, Precio) — **opcional**
3. Presiona **Ejecutar comparación**

### Formato del archivo de Equipos

Según `config/config.yaml`, debe tener:
- **Columna SKU**
- **Columna Modelo**
- **Columnas de precio** (por modalidad: Portabilidad, Renovación, etc.)
- **Columna Estado Comercial** (solo En Oferta y Lanzamiento se incluyen)

Puedes subir `.xlsx`, `.xls` o `.csv` (con separador `;`)

### Formato del archivo de Accesorios (opcional)

- **SKU**: Identificador único
- **Modelo**: Nombre del accesorio
- **Precio**: Precio actual
- **Precio Normal** (opcional): Precio sin descuento
- **% Descuento** (opcional): Porcentaje de descuento

### Qué hace la app

1. Lee equipos y accesorios (si los cargas)
2. Consulta la API de WOM
3. Compara precios y muestra discrepancias
4. Descarga los resultados en Excel
"""


def get_config():
    config_path = PROJECT_ROOT / "config" / "config.yaml"
    if config_path.exists():
        with open(config_path, encoding="utf-8") as f:
            return yaml.safe_load(f)
    return {}


def run_comparison(excel_path: Path, config: dict, accessories_path: Optional[Path] = None) -> tuple[pd.DataFrame, dict]:
    excel_cfg = config.get("data_source", {}).get("excel", {})
    sheet_configs = excel_cfg.get("sheets")
    estado_comercial = excel_cfg.get("estado_comercial")
    tolerance = config.get("comparison", {}).get("tolerance_percent", 1.0)
    api_cfg = config.get("website", {}).get("api", {})
    api_skus = [s.strip() for s in str(api_cfg.get("skus", "")).split(",") if s.strip()]

    ref_df = read_excel_reference(
        excel_path,
        sheet_configs=sheet_configs,
        estado_comercial=estado_comercial,
    )

    # Agregar accesorios
    if accessories_path and accessories_path.exists():
        csv_accesorios = get_csv_accessories(accessories_path)
        if not csv_accesorios.empty:
            ref_df = pd.concat([ref_df, csv_accesorios], ignore_index=True)
            # Agregar SKUs únicos de accesorios a la consulta API (evitar duplicados)
            accessory_skus = csv_accesorios['sku'].unique().tolist()
            api_skus.extend([sku for sku in accessory_skus if sku not in api_skus])
    else:
        # Intentar leer desde archivo por defecto (backwards compatibility)
        project_root = Path(__file__).resolve().parent
        csv_accessories_path = project_root / "Precios MOM Days Accesorios.csv"
        if csv_accessories_path.exists():
            csv_accesorios = get_csv_accessories(csv_accessories_path)
            if not csv_accesorios.empty:
                ref_df = pd.concat([ref_df, csv_accesorios], ignore_index=True)
                # Agregar SKUs únicos de accesorios a la consulta API (evitar duplicados)
                accessory_skus = csv_accesorios['sku'].unique().tolist()
                api_skus.extend([sku for sku in accessory_skus if sku not in api_skus])

    modalities = ["renovacion", "portabilidad", "linea_nueva", "prepago", "precio_normal"]
    web_df = fetch_products_from_api(
        skus=api_skus,
        modalities=modalities,
        base_url=api_cfg.get("base_url", "https://store-srv.wom.cl/rest/V1/content"),
        connect_timeout=float(api_cfg.get("connect_timeout", 90)),
        read_timeout=float(api_cfg.get("read_timeout", 180)),
        batch_size=int(api_cfg.get("batch_size", 10)),
        retries=int(api_cfg.get("retries", 5)),
    )

    subset = (
        ["sku", "modality"]
        if "sku" in web_df.columns and web_df["sku"].notna().any()
        else ["name", "modality"]
    )
    web_df = web_df.drop_duplicates(subset=subset, keep="first")

    results_df = compare_prices(ref_df, web_df, tolerance_percent=tolerance)
    results_distinct = to_distinct_by_sku(results_df)

    stats = {
        "total": len(results_df),
        "skus_unicos": len(results_distinct),
        "ok": len(results_df[results_df["status"] == "OK"]),
        "critica": len(results_df[results_df["status"] == "CRITICA"]),
        "moderada": len(results_df[results_df["status"] == "MODERADA"]),
        "no_encontrado": len(results_df[results_df["status"] == "NO_ENCONTRADO"]),
        "nuevo": len(results_df[results_df["status"] == "NUEVO_EN_WEB"]),
        "precio_normal_sin_precio": len(
            results_df[results_df["status"] == "PRECIO_NORMAL_SIN_PRECIO"]
        ),
    }
    return results_distinct, stats


def main():
    st.set_page_config(
        page_title="Revisión Precios WOM",
        page_icon="📊",
        layout="wide",
    )

    for key, default in (
        ("comparison_results", None),
        ("comparison_stats", None),
        ("comparison_error", None),
    ):
        if key not in st.session_state:
            st.session_state[key] = default

    st.title("📊 Revisión de Precios WOM Store")
    st.caption("Compara precios de store.wom.cl con tu Excel de referencia")

    with st.expander("📌 Cómo usar el Excel (léeme)", expanded=False):
        st.markdown(USAGE_MD)

    config = get_config()
    if not config:
        st.error("Falta `config/config.yaml` en el proyecto.")
        return

    col_equip, col_acces = st.columns([1, 1])

    with col_equip:
        uploaded_equipos = st.file_uploader(
            "1️⃣ Sube Equipos (.xlsx, .csv)",
            type=["xlsx", "xls", "csv"],
            key="equipos_uploader",
            help="Excel o CSV con SKU, Modelo y columnas por modalidad",
        )

    with col_acces:
        uploaded_accesorios = st.file_uploader(
            "2️⃣ Sube Accesorios (.xlsx, .csv)",
            type=["xlsx", "xls", "csv"],
            key="accesorios_uploader",
            help="Excel o CSV con SKU, Modelo, Precio (opcional para incluir accesorios)",
        )

    col1, col2 = st.columns([1, 1])
    with col1:
        run_clicked = st.button("🚀 3. Ejecutar comparación", type="primary", use_container_width=True)
    with col2:
        if st.button("🗑️ Limpiar resultados", use_container_width=True):
            st.session_state.comparison_results = None
            st.session_state.comparison_stats = None
            st.session_state.comparison_error = None
            st.rerun()

    if run_clicked:
        if not uploaded_equipos:
            st.session_state.comparison_error = "Primero sube un archivo de Equipos."
            st.session_state.comparison_results = None
            st.session_state.comparison_stats = None
        else:
            st.session_state.comparison_error = None
            try:
                # Procesar equipos
                suffix_equip = ".xlsx" if uploaded_equipos.name.lower().endswith(".xlsx") else (".xls" if uploaded_equipos.name.lower().endswith(".xls") else ".csv")
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix_equip) as tmp_equip:
                    tmp_equip.write(uploaded_equipos.getvalue())
                    equipos_path = Path(tmp_equip.name)

                # Procesar accesorios (si se cargaron)
                accesorios_path = None
                if uploaded_accesorios:
                    suffix_acces = ".xlsx" if uploaded_accesorios.name.lower().endswith(".xlsx") else (".xls" if uploaded_accesorios.name.lower().endswith(".xls") else ".csv")
                    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix_acces) as tmp_acces:
                        tmp_acces.write(uploaded_accesorios.getvalue())
                        accesorios_path = Path(tmp_acces.name)

                try:
                    with st.spinner("Consultando API de WOM y comparando con tus archivos…"):
                        results_df, stats = run_comparison(equipos_path, config, accessories_path=accesorios_path)
                    st.session_state.comparison_results = results_df
                    st.session_state.comparison_stats = stats
                finally:
                    equipos_path.unlink(missing_ok=True)
                    if accesorios_path:
                        accesorios_path.unlink(missing_ok=True)
            except Exception as e:
                st.session_state.comparison_results = None
                st.session_state.comparison_stats = None
                st.session_state.comparison_error = str(e)

    if st.session_state.comparison_error:
        st.error(st.session_state.comparison_error)

    if st.session_state.comparison_results is not None and st.session_state.comparison_stats is not None:
        stats = st.session_state.comparison_stats
        results_df = st.session_state.comparison_results

        st.success(
            "Comparación lista. Los resultados se mantienen hasta **Limpiar** o una nueva ejecución."
        )

        cols = st.columns(7)
        cols[0].metric("SKUs", stats["skus_unicos"])
        cols[1].metric("OK", stats["ok"])
        cols[2].metric("Críticas", stats["critica"])
        cols[3].metric("Moderadas", stats["moderada"])
        cols[4].metric("No encontrado", stats["no_encontrado"])
        cols[5].metric("Nuevos", stats["nuevo"])
        cols[6].metric("Sin precio N", stats["precio_normal_sin_precio"])

        st.subheader("Resultados")
        df_display = results_df.copy()
        for col in df_display.columns:
            if df_display[col].dtype == object:
                df_display[col] = df_display[col].fillna("").astype(str)
        st.dataframe(df_display, use_container_width=True, height=420)

        buffer = BytesIO()
        results_df.to_excel(buffer, index=False)
        buffer.seek(0)
        st.download_button(
            "📥 Descargar Excel de resultados",
            data=buffer.getvalue(),
            file_name="comparacion_precios.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
    elif st.session_state.comparison_results is None:
        if uploaded_equipos is None:
            st.info("👆 Sube tu Excel y pulsa **Ejecutar comparación**.")
        elif not st.session_state.comparison_error:
            st.info("Excel cargado. Pulsa **Ejecutar comparación**.")


if __name__ == "__main__":
    main()
