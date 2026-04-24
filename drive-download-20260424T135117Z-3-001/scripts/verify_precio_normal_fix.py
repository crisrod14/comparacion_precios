"""Verifica que precio_normal use el valor correcto tras la corrección."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml
from src.scraper.wom_api_client import fetch_products_from_api

cfg = yaml.safe_load((Path(__file__).parent.parent / "config/config.yaml").read_text(encoding="utf-8"))
skus_str = cfg.get("website", {}).get("api", {}).get("skus", "")
skus = [s.strip() for s in skus_str.split(",") if s.strip()]

df = fetch_products_from_api(
    skus,
    ["precio_normal"],
    cfg.get("website", {}).get("api", {}).get("base_url", "https://store-srv.wom.cl/rest/V1/content"),
)

redmi = df[df["name"].str.contains("Redmi", case=False, na=False)]
iphone = df[df["name"].str.contains("iPhone 15", case=False, na=False)]

print("=== PRECIO NORMAL - Productos Redmi (corregidos) ===")
for _, r in redmi.iterrows():
    print(f"  {r['name']}: {r['price']}")

print("\n=== PRECIO NORMAL - iPhone 15 (debe seguir igual) ===")
for _, r in iphone.head(2).iterrows():
    print(f"  {r['name']}: {r['price']}")
