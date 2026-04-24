"""
Streamlit app para comparación de precios WOM Store.
Desplegable gratuitamente en Streamlit Community Cloud.
"""
from io import BytesIO
from pathlib import Path
import sys
import tempfile

import pandas as pd
import streamlit as st
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.data_sources.excel_reader import read_excel_reference
from src.comparator.price_comparator import compare_prices, to_distinct_by_sku
from src.scraper.wom_api_client import fetch_products_from_api


def update_config_with_excel_skus(excel_path: Path, config_path: Path):
    """Actualiza config.yaml con SKUs nuevos del Excel."""
    try:
        # Leer SKUs del Excel
        df = pd.read_excel(excel_path, sheet_name="Equipos")
        excel_skus = set(df['SKU'].dropna().unique())
        excel_skus = {str(s).strip() for s in excel_skus if s}

        # Leer config actual
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        existing_skus = set(
            s.strip() for s in config['website']['api']['skus'].split(',') if s.strip()
        )

        # Encontrar nuevos SKUs
        new_skus = excel_skus - existing_skus
        if new_skus:
            # Actualizar config
            combined_skus = sorted(list(existing_skus | excel_skus))
            config['website']['api']['skus'] = ','.join(combined_skus)

            with open(config_path, 'w', encoding='utf-8') as f:
                yaml.dump(config, f, allow_unicode=True, sort_keys=False)

            return len(new_skus)
        return 0
    except Exception as e:
        st.warning(f"No se pudo actualizar config.yaml: {e}")
        return 0

USAGE_MD = """
### Dónde va el archivo

| Modo | Qué hacer |
|------|-----------|
| **Streamlit (esta página)** | Sube el Excel con el cuadro de abajo. No hace falta copiarlo a ninguna carpeta. |
| **Flask (puerto 5000)** | Pon el archivo en la **carpeta raíz del proyecto** como `Precios depurados.xlsx` (o el nombre en `config.yaml` → `file_path`). |

### Formato del Excel

Según `config/config.yaml`, el libro debe tener:

- **Hoja `Equipos`**: `SKU`, `Modelo`, `Estado Comercial` (solo filas **En Oferta** y **Lanzamiento**).
- Columnas de precio: **Equipo con Portabilidad**, **Equipo en Renovacion**, **Equipo con Nuevo Numero**, **Prepago Exclusivo wom.cl**, **Precio Normal**, y los **% Descuento** si aplica.

Si cambian los nombres de columnas, edita `data_source.excel.sheets` en `config.yaml`.

### Qué hace la app

1. Lee tus precios del Excel.
2. Consulta la API de WOM (lista de SKUs en `website.api.skus`).
3. Compara y muestra el resultado.
"""


def get_config():
    config_path = PROJECT_ROOT / "config" / "config.yaml"
    if config_path.exists():
        with open(config_path, encoding="utf-8") as f:
            return yaml.safe_load(f)
    return {}


def run_comparison(excel_path: Path, config: dict) -> tuple[pd.DataFrame, dict]:
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
    ref_df = ref_df[ref_df["modality"] != "accesorios"].copy()

    # Actualizar config.yaml con SKUs nuevos del Excel
    config_path = PROJECT_ROOT / "config" / "config.yaml"
    new_skus_count = update_config_with_excel_skus(excel_path, config_path)
    if new_skus_count > 0:
        # Recargar config con los SKUs actualizados
        with open(config_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)
        api_cfg = config.get("website", {}).get("api", {})
        api_skus = [s.strip() for s in str(api_cfg.get("skus", "")).split(",") if s.strip()]

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

    uploaded = st.file_uploader(
        "1. Sube tu Excel de precios (.xlsx)",
        type=["xlsx", "xls"],
        help="Misma estructura que Precios depurados: hoja Equipos con SKU, Modelo y columnas por modalidad",
    )

    col1, col2 = st.columns([1, 1])
    with col1:
        run_clicked = st.button("🚀 2. Ejecutar comparación", type="primary", use_container_width=True)
    with col2:
        if st.button("🗑️ Limpiar resultados", use_container_width=True):
            st.session_state.comparison_results = None
            st.session_state.comparison_stats = None
            st.session_state.comparison_error = None
            st.rerun()

    if run_clicked:
        if not uploaded:
            st.session_state.comparison_error = "Primero sube un archivo Excel."
            st.session_state.comparison_results = None
            st.session_state.comparison_stats = None
        else:
            st.session_state.comparison_error = None
            suffix = ".xlsx" if uploaded.name.lower().endswith(".xlsx") else ".xls"
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                    tmp.write(uploaded.getvalue())
                    excel_path = Path(tmp.name)
                try:
                    with st.spinner("Consultando API de WOM y comparando con tu Excel…"):
                        results_df, stats = run_comparison(excel_path, config)
                    st.session_state.comparison_results = results_df
                    st.session_state.comparison_stats = stats
                finally:
                    excel_path.unlink(missing_ok=True)
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
        if uploaded is None:
            st.info("👆 Sube tu Excel y pulsa **Ejecutar comparación**.")
        elif not st.session_state.comparison_error:
            st.info("Excel cargado. Pulsa **Ejecutar comparación**.")


if __name__ == "__main__":
    main()
