#!/usr/bin/env python3
"""
Debug de extracción de JSON Schema
"""
import sys
import json
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

def debug_json():
    print("🔍 Debug de extracción JSON Schema...\n")

    try:
        from src.scraper.wom_scraper import WOMScraper
        import time

        with WOMScraper(headless=True, timeout=60000) as scraper:
            page = scraper._browser.new_page()
            page.set_default_timeout(60000)
            page.set_viewport_size({"width": 1920, "height": 1080})

            print("📄 Cargando página...")
            try:
                page.goto("https://store.wom.cl/accesorios/", wait_until="domcontentloaded", timeout=45000)
            except:
                page.goto("https://store.wom.cl/accesorios/", wait_until="networkidle", timeout=45000)
            time.sleep(2)

            html = page.content()

            # Buscar JSON Schemas
            patterns = re.findall(
                r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
                html,
                re.DOTALL | re.IGNORECASE
            )

            print(f"Encontrados {len(patterns)} scripts JSON-LD\n")

            item_count = 0
            for idx, pattern in enumerate(patterns):
                try:
                    data = json.loads(pattern)
                    print(f"Script #{idx + 1}:")
                    print(f"  Type: {data.get('@type', 'N/A')}")

                    if isinstance(data, dict) and data.get("@type") == "ItemList":
                        items = data.get("itemListElement", [])
                        print(f"  ItemList con {len(items)} items")
                        for item in items[:3]:
                            print(f"    - {item.get('name', 'N/A')}: {item.get('url', 'N/A')}")
                        item_count += len(items)
                        print()
                except json.JSONDecodeError as e:
                    print(f"  ❌ JSON inválido: {str(e)[:100]}\n")

            print(f"✓ Total items en ItemLists: {item_count}")

            # Extraer inner_text
            try:
                inner_text = page.inner_text('body')
            except:
                inner_text = page.evaluate("document.body.innerText")

            print(f"\n📝 Primeras líneas del texto visible:")
            lines = inner_text.split('\n')[:30] if inner_text else []
            for line in lines[:30]:
                if line.strip():
                    print(f"  {line}")

            page.close()

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    debug_json()
