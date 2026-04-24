"""
Script para inspeccionar precios de productos Redmi en la API.
Verifica por qué precio_normal sale 228000 en vez de 349990.
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
    skus_str = cfg.get("website", {}).get("api", {}).get("skus", "")
    skus = [s.strip() for s in skus_str.split(",") if s.strip()]

    # Productos Redmi que el usuario mencionó
    redmi_keywords = ["Redmi Note 15", "Redmi A5"]
    url = f"{base_url}/getGraphqlDataFromSkus?skus={','.join(skus)}"
    headers = {
        "accept": "*/*",
        "origin": "https://store.wom.cl",
        "referer": "https://store.wom.cl/",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0",
    }
    print("Fetching API...")
    resp = requests.get(url, headers=headers, timeout=60)
    resp.raise_for_status()
    data = resp.json()

    # Guardar JSON para inspección
    out_path = project_root / "data" / "api_response_redmi.json"
    out_path.parent.mkdir(exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Guardado en {out_path}\n")

    if not isinstance(data, list):
        print("Respuesta no es lista:", type(data))
        return

    scenario_map = {
        "renew": "renovacion",
        "portIn": "portabilidad",
        "newConnection": "linea_nueva",
        "prepago": "prepago",
        "standard": "precio_normal (standard)",
    }

    for item in data:
        childs = item.get("childs") or [item]
        for child in childs:
            gd = child.get("graphql_data") or {}
            inner = gd.get("graphql_data") or {}
            name = inner.get("name") or gd.get("name") or "?"
            if not any(kw in name for kw in redmi_keywords):
                continue
            pop = inner.get("productOfferingPrice") or {}
            # Precio a nivel raíz (como en iPhone graphql_data.price = 999990)
            root_price_gd = gd.get("price")
            root_price_inner = inner.get("price")
            print("\n" + "=" * 70)
            print(f"PRODUCTO: {name}")
            print(f"SKU: {child.get('child_sku')} / parent: {child.get('parent_sku')}")
            print(f">>> PRECIO RAÍZ: graphql_data.price={root_price_gd}, inner.price={root_price_inner}")
            print("=" * 70)
            for scenario, mod in scenario_map.items():
                offer = pop.get(scenario)
                if not offer:
                    print(f"  {mod}: (sin dato)")
                    continue
                rps = offer.get("relatedPrice") or []
                print(f"  {mod} ({scenario}):")
                for rp in rps:
                    pt = rp.get("priceType", "")
                    if "installment" in (pt or "").lower():
                        continue
                    pval = (rp.get("price") or {}).get("value")
                    print(f"    - priceType: {pt!r}  value: {pval}")
            print()


if __name__ == "__main__":
    main()
