"""
Script para inspeccionar la respuesta cruda de la API y ver la estructura de precios.
Ejecutar: python scripts/debug_api_prices.py
"""
import json
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

def main():
    import yaml
    import requests

    cfg = yaml.safe_load((project_root / "config/config.yaml").read_text(encoding="utf-8"))
    base_url = cfg.get("website", {}).get("api", {}).get("base_url", "https://store-srv.wom.cl/rest/V1/content")
    sku = "A3090-128GB"  # iPhone 15
    url = f"{base_url}/getGraphqlDataFromSkus?skus={sku}"
    headers = {
        "accept": "*/*",
        "origin": "https://store.wom.cl",
        "referer": "https://store.wom.cl/",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0",
    }
    print("Fetching:", url)
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    # Guardar JSON completo
    out_path = project_root / "data" / "api_response_A3090.json"
    out_path.parent.mkdir(exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Guardado en {out_path}")

    # Extraer y mostrar estructura de precios por modalidad
    print("\n" + "="*60)
    print("ESTRUCTURA DE PRECIOS POR MODALIDAD")
    print("="*60)
    scenario_map = {"renew": "renovacion", "portIn": "portabilidad", "newConnection": "linea_nueva", "prepago": "prepago", "standard": "precio_normal"}
    for item in data:
        childs = item.get("childs") or [item]
        for child in childs:
            gd = child.get("graphql_data") or {}
            inner = gd.get("graphql_data") or {}
            name = inner.get("name") or gd.get("name") or "?"
            pop = inner.get("productOfferingPrice") or {}
            print(f"\nProducto: {name}")
            for scenario, mod in scenario_map.items():
                offer = pop.get(scenario)
                if not offer:
                    print(f"  {mod}: (sin dato)")
                    continue
                rps = offer.get("relatedPrice") or []
                print(f"  {mod}:")
                for rp in rps:
                    pt = rp.get("priceType", "")
                    pval = (rp.get("price") or {}).get("value")
                    print(f"    - priceType: {pt!r}  value: {pval}")
            break  # solo primer child
        break  # solo primer item

if __name__ == "__main__":
    main()
