#!/usr/bin/env python3
"""
Ver el HTML completo y buscar dónde están los datos
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

def debug():
    print("🔍 Analizando HTML completo...\n")

    try:
        from src.scraper.wom_scraper import WOMScraper
        import time

        with WOMScraper(headless=True, timeout=60000) as scraper:
            page = scraper._browser.new_page()
            page.set_default_timeout(60000)

            print("📄 Cargando página...")
            try:
                page.goto("https://store.wom.cl/accesorios/", wait_until="domcontentloaded", timeout=45000)
            except:
                page.goto("https://store.wom.cl/accesorios/", timeout=45000)

            # Esperar más
            print("⏳ Esperando carga completa...")
            time.sleep(5)

            html = page.content()

            print(f"📊 Tamaño HTML: {len(html)} bytes\n")

            # Buscar patrones de datos
            patterns = [
                ("JSON-LD", '{"@type":"ItemList"'),
                ("Precios", '$'),
                ("Samsung Galaxy Tab", 'Samsung Galaxy Tab'),
                ("itemListElement", 'itemListElement'),
                ("store.wom.cl/accesorios", 'store.wom.cl/accesorios/'),
            ]

            for name, pattern in patterns:
                count = html.count(pattern)
                print(f"{name:.<30} {'✓' if count > 0 else '❌'} ({count})")

            # Guardar HTML para inspección
            with open('/tmp/accesorios_page.html', 'w') as f:
                f.write(html[:100000])  # Primeros 100KB
            print("\n📄 HTML guardado en /tmp/accesorios_page.html")

            # Buscar Samsung Galaxy Tab en el HTML
            idx = html.find("Samsung Galaxy Tab")
            if idx > 0:
                print(f"\n📍 Contexto de 'Samsung Galaxy Tab' (posición {idx}):")
                print(html[max(0, idx-300):min(len(html), idx+500)])
            else:
                print("\n❌ 'Samsung Galaxy Tab' NO encontrado en HTML")

            page.close()

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    debug()
