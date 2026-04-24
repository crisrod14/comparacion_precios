"""
Flask dashboard for price comparison - WOM Store.
"""
import math
from datetime import datetime
from pathlib import Path

import pandas as pd
from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS

from src.data_sources.excel_reader import read_excel_reference, get_excel_sheets
from src.comparator.price_comparator import compare_prices, to_distinct_by_sku
from src.scraper.wom_scraper import WOMScraper

app = Flask(__name__)
CORS(app)

# app.py está en src/dashboard/ -> parent.parent = src, parent.parent.parent = raíz del proyecto
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
REPORTS_DIR = PROJECT_ROOT / "reports"
REPORTS_DIR.mkdir(exist_ok=True)
DATA_DIR.mkdir(exist_ok=True)


def get_config():
    """Load config from YAML."""
    try:
        import yaml
        config_path = PROJECT_ROOT / "config" / "config.yaml"
        if config_path.exists():
            with open(config_path, encoding="utf-8") as f:
                return yaml.safe_load(f)
    except Exception:
        pass
    return {}


def get_excel_path() -> Path:
    """Get Excel file path from config or default."""
    config = get_config()
    path = config.get("data_source", {}).get("excel", {}).get("file_path", "")
    if path:
        full = PROJECT_ROOT / Path(path).name
        if full.exists():
            return full
        if (PROJECT_ROOT / path).exists():
            return PROJECT_ROOT / path
    # Priorizar Precios depurados.xlsx si existe
    depurados = PROJECT_ROOT / "Precios depurados.xlsx"
    if depurados.exists():
        return depurados
    # Buscar cualquier .xlsx en la raíz del proyecto
    for f in PROJECT_ROOT.glob("*.xlsx"):
        if f.is_file():
            return f
    return PROJECT_ROOT / "Precios depurados.xlsx"


@app.route("/")
def index():
    """Dashboard home."""
    return render_template("index.html")


@app.route("/api/sheets")
def api_sheets():
    """Get Excel sheet names."""
    try:
        path = get_excel_path()
        if not path.exists():
            return jsonify({"error": "Excel no encontrado"}), 404
        sheets = get_excel_sheets(path)
        return jsonify({"sheets": sheets})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/analyze")
def api_analyze():
    """Analyze Excel structure: raw columns + transformed data for comparison."""
    try:
        path = get_excel_path()
        if not path.exists():
            return jsonify({"error": "Excel no encontrado"}), 404
        config = get_config()
        excel_cfg = config.get("data_source", {}).get("excel", {})
        sheet_configs = excel_cfg.get("sheets")

        # 1. Estructura CRUDA del Excel (hoja Equipos)
        raw_info = {}
        xl = pd.ExcelFile(path)
        equipos_sheet = None
        for cfg in (sheet_configs or []):
            sh = cfg.get("sheet") or cfg.get("name")
            if sh == "Equipos":
                equipos_sheet = sh
                break
        if not equipos_sheet and "Equipos" in xl.sheet_names:
            equipos_sheet = "Equipos"
        if not equipos_sheet and xl.sheet_names:
            equipos_sheet = xl.sheet_names[0]
        if equipos_sheet and equipos_sheet in xl.sheet_names:
            raw_df = pd.read_excel(path, sheet_name=equipos_sheet)
            raw_sample = raw_df.head(5).to_dict(orient="records")
            for r in raw_sample:
                for k, v in list(r.items()):
                    if v is not None and isinstance(v, float) and math.isnan(v):
                        r[k] = None
            raw_info = {
                "sheet": equipos_sheet,
                "columns": list(raw_df.columns),
                "rows_raw": len(raw_df),
                "sample_raw": raw_sample,
            }

        # 2. Datos transformados (para comparación)
        df = read_excel_reference(
            path,
            sheet_configs=sheet_configs,
            estado_comercial=excel_cfg.get("estado_comercial"),
        )
        df_equipos = df[df["modality"] != "accesorios"].copy() if "modality" in df.columns else df
        sample = df_equipos.head(15).to_dict(orient="records") if not df_equipos.empty else []
        for r in sample:
            for k, v in list(r.items()):
                if v is not None and isinstance(v, float) and math.isnan(v):
                    r[k] = None

        # 3. Mapeo de columnas Excel -> modalidad
        modality_map = []
        for cfg in (sheet_configs or []):
            for mod in (cfg.get("modalities") or []):
                modality_map.append({
                    "excel_column": mod.get("excel_column"),
                    "modality_id": mod.get("id"),
                })

        return jsonify({
            "raw": raw_info,
            "transformed": {
                "rows": len(df_equipos),
                "columns": list(df.columns),
                "modalities_used": (
                    [str(m) for m in df_equipos["modality"].unique().tolist()]
                    if "modality" in df_equipos.columns and not df_equipos.empty
                    else []
                ),
                "sample": sample,
            },
            "modality_map": modality_map,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/run", methods=["POST"])
def api_run():
    """Run full comparison: scrape website + compare with Excel."""
    try:
        config = get_config()
        excel_path = get_excel_path()
        if not excel_path.exists():
            return jsonify({"error": "Excel no encontrado"}), 404

        excel_cfg = config.get("data_source", {}).get("excel", {})
        sheet_configs = excel_cfg.get("sheets")
        ref_df = read_excel_reference(
            excel_path,
            sheet_configs=sheet_configs,
            estado_comercial=excel_cfg.get("estado_comercial"),
        )
        tolerance = config.get("comparison", {}).get("tolerance_percent", 1.0)

        website_cfg = config.get("website", {})
        scraping_cfg = website_cfg.get("scraping", {})
        api_cfg = website_cfg.get("api", {})
        use_api = (scraping_cfg.get("method") or "api").lower() == "api"
        api_skus = None
        if use_api and api_cfg.get("skus"):
            api_skus = [s.strip() for s in str(api_cfg["skus"]).split(",") if s.strip()]

        with WOMScraper(
            headless=scraping_cfg.get("headless", True),
            delay=scraping_cfg.get("delay_between_requests", 2),
        ) as scraper:
            equipos_modalities = website_cfg.get("equipos_modalities", [])
            if not equipos_modalities:
                equipos_modalities = [
                    {"id": "renovacion", "url": "/equipos/renovacion"},
                ]
            web_df = scraper.scrape_all_modalities(
                equipos_modalities,
                use_api=use_api and bool(api_skus),
                api_skus=api_skus,
                api_config=api_cfg,
            )
            ref_df = ref_df[ref_df["modality"] != "accesorios"].copy()
            # Priorizar SKU para dedup cuando la API lo entrega
            subset = ["sku", "modality"] if "sku" in web_df.columns and web_df["sku"].notna().any() and (web_df["sku"] != "").any() else ["name", "modality"]
            web_df = web_df.drop_duplicates(subset=subset, keep="first")

        results_df = compare_prices(ref_df, web_df, tolerance_percent=tolerance)
        results_distinct = to_distinct_by_sku(results_df)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = REPORTS_DIR / f"comparison_{timestamp}.xlsx"
        results_distinct.to_excel(report_path, index=False)

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

        # Reemplazar NaN por None para que JSON sea válido (NaN no es válido en JSON)
        results_records = results_distinct.to_dict(orient="records")
        for r in results_records:
            for k, v in r.items():
                if v is not None and isinstance(v, float) and math.isnan(v):
                    r[k] = None

        return jsonify({
            "success": True,
            "stats": stats,
            "results": results_records,
            "report_path": str(report_path),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/debug-api-raw")
def api_debug_raw():
    """Devuelve la respuesta cruda de la API para un SKU (ej. ?sku=A3090-128GB)."""
    try:
        import requests
        config = get_config()
        api_cfg = config.get("website", {}).get("api", {})
        sku = request.args.get("sku", "A3090-128GB")
        base_url = api_cfg.get("base_url", "https://store-srv.wom.cl/rest/V1/content")
        url = f"{base_url}/getGraphqlDataFromSkus?skus={sku}"
        headers = {
            "accept": "*/*",
            "origin": "https://store.wom.cl",
            "referer": "https://store.wom.cl/",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0",
        }
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return jsonify({"url": url, "data": data})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/debug-scrape")
def api_debug_scrape():
    """Debug: usa API si está configurada, sino Playwright."""
    try:
        config = get_config()
        website_cfg = config.get("website", {})
        api_cfg = website_cfg.get("api", {})
        api_skus = None
        if api_cfg.get("skus"):
            api_skus = [s.strip() for s in str(api_cfg["skus"]).split(",") if s.strip()]

        if api_skus:
            from src.scraper.wom_api_client import fetch_products_from_api

            modalities = ["renovacion", "portabilidad", "linea_nueva", "prepago", "precio_normal"]
            df = fetch_products_from_api(
                skus=api_skus[:20],
                modalities=modalities,
                base_url=api_cfg.get("base_url", "https://store-srv.wom.cl/rest/V1/content"),
                connect_timeout=float(api_cfg.get("connect_timeout", 90)),
                read_timeout=float(api_cfg.get("read_timeout", 180)),
                batch_size=int(api_cfg.get("batch_size", 10)),
                retries=int(api_cfg.get("retries", 5)),
            )
            sample = df.head(20).to_dict(orient="records") if not df.empty else []
            for r in sample:
                for k, v in list(r.items()):
                    if v is not None and isinstance(v, float) and math.isnan(v):
                        r[k] = None
            return jsonify({
                "source": "api",
                "rows": len(df),
                "columns": list(df.columns),
                "sample": sample,
            })

        headless = request.args.get("headless", "1") != "0"
        with WOMScraper(headless=headless, delay=1.5) as scraper:
            debug = scraper.debug_category_links("/equipos/renovacion")
        return jsonify(debug)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/download/<filename>")
def api_download(filename):
    """Download report file."""
    path = REPORTS_DIR / filename
    if not path.exists():
        return jsonify({"error": "Archivo no encontrado"}), 404
    return send_file(path, as_attachment=True, download_name=filename)


def main():
    """Run the Flask app."""
    app.run(debug=True, port=5000, host="0.0.0.0")


if __name__ == "__main__":
    main()
