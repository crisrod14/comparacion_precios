#!/usr/bin/env python3
"""
Ver la estructura HTML actual de los productos
"""
import sys
from pathlib import Path
import re

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

def debug_html():
    print("🔍 Analizando estructura HTML real...\n")

    try:
        from src.scraper.wom_scraper import WOMScraper
        import time

        with WOMScraper(headless=True, timeout=30000) as scraper:
            page = scraper._browser.new_page()
            page.set_default_timeout(30000)
            page.set_viewport_size({"width": 1920, "height": 1080})

            print("📄 Cargando página...")
            page.goto("https://store.wom.cl/accesorios/", wait_until="load")
            time.sleep(5)

            # Scroll
            for i in range(10):
                page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(0.3)
            time.sleep(2)

            # Obtener HTML completo
            html = page.content()

            # Buscar patrones de productos
            print("📋 Buscando patrones de productos en HTML...\n")

            # Buscar divs con clases que contengan producto
            product_divs = re.findall(r'<div[^>]*class="[^"]*product[^"]*"[^>]*>.*?</div>', html[:50000], re.IGNORECASE | re.DOTALL)
            print(f"Divs con 'product': {len(product_divs)}")

            # Buscar botones "LO QUIERO"
            lo_quiero_count = html.count("LO QUIERO")
            print(f"Botones 'LO QUIERO': {lo_quiero_count}")

            # Buscar links que NO sean a /accesorios/
            all_hrefs = re.findall(r'href="([^"]*)"', html)
            print(f"\nTodos los hrefs únicos:")
            unique_hrefs = set(all_hrefs)
            for href in sorted(unique_hrefs)[:30]:
                print(f"  {href}")

            # Buscar estructura alrededor de precios
            price_pattern = r'(\$[\d.,]+.*?.{0,200}?href[^>]*(?:/accesorios/)?[^>]*>)'
            prices_with_links = re.findall(price_pattern, html[:50000], re.DOTALL | re.IGNORECASE)
            print(f"\nPatrones precio+link: {len(prices_with_links)}")
            if prices_with_links:
                print("Primer patrón:")
                print(prices_with_links[0][:300])

            # Obtener un snippet donde está "Samsung Galaxy Tab"
            idx = html.find("Samsung Galaxy Tab")
            if idx > 0:
                print(f"\n📍 Contexto de 'Samsung Galaxy Tab':")
                snippet = html[max(0, idx-500):min(len(html), idx+1000)]
                print(snippet)

            page.close()

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    debug_html()
