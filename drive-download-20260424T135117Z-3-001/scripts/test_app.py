"""Quick test of app components."""
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

def list_excel_columns():
    """List all columns from Equipos sheet."""
    import pandas as pd
    for f in ["Precios depurados.xlsx", "2026_02_10 Resumen Oferta de Equipos y Accesorios WOM v26.2.1v2.xlsx"]:
        p = project_root / f
        if p.exists():
            df = pd.read_excel(p, sheet_name="Equipos", nrows=1)
            print(f"\n{f} - Equipos columns:")
            for i, c in enumerate(df.columns):
                print(f"  {i+1}. {repr(c)}")
            break

def main():
    import yaml
    from src.data_sources.excel_reader import read_excel_reference
    from src.comparator.price_comparator import compare_prices, to_distinct_by_sku

    cfg = yaml.safe_load((project_root / "config/config.yaml").read_text(encoding="utf-8"))
    exc = cfg["data_source"]["excel"]
    excel_path = project_root / exc["file_path"].split("/")[-1]
    if not excel_path.exists():
        excel_path = project_root / "Precios depurados.xlsx"
    ref = read_excel_reference(
        excel_path,
        sheet_configs=exc["sheets"],
        estado_comercial=exc.get("estado_comercial"),
    )
    ref = ref[ref["modality"] != "accesorios"] if "modality" in ref.columns else ref
    print("Ref rows:", len(ref))
    print("Columns:", list(ref.columns))
    if "descuento_pct_ref" in ref.columns:
        print("Sample descuento_pct_ref:", ref["descuento_pct_ref"].dropna().head(3).tolist())
    if len(ref) > 0:
        print("Sample:", ref.head(2).to_dict("records"))

    # Test API
    from src.scraper.wom_api_client import fetch_products_from_api
    api_cfg = cfg.get("website", {}).get("api", {})
    skus = [s.strip() for s in str(api_cfg.get("skus", "")).split(",") if s.strip()][:3]
    modalities = ["renovacion", "portabilidad"]
    web = fetch_products_from_api(skus, modalities, api_cfg.get("base_url", "https://store-srv.wom.cl/rest/V1/content"))
    print("\nWeb rows:", len(web))
    if len(web) > 0:
        print("Web sample:", web.head(2).to_dict("records"))

    # Test compare
    results = compare_prices(ref.head(50), web, tolerance_percent=1.0)
    print("\nCompare results:", len(results))
    distinct = to_distinct_by_sku(results)
    print("Distinct:", len(distinct))
    if len(distinct) > 0:
        print("Distinct cols:", list(distinct.columns))


if __name__ == "__main__":
    main()
