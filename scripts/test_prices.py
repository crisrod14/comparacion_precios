import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.scraper.wom_api_client import fetch_products_from_api

df = fetch_products_from_api(
    ["A3090-128GB"],
    ["renovacion", "portabilidad", "linea_nueva", "precio_normal"],
    "https://store-srv.wom.cl/rest/V1/content",
)
for _, r in df.iterrows():
    print(f"{r['modality']}: price={r['price']} desc={r['precio_descuento']} normal={r['precio_normal']}")
