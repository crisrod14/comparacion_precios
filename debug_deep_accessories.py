#!/usr/bin/env python3
"""
Debug profundo: mostrar TODOS los links y elementos de /accesorios/
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

def debug_all_content():
    print("🔍 Debug profundo de /accesorios/...\n")

    try:
        from src.scraper.wom_scraper import WOMScraper
        import time

        with WOMScraper(headless=True, timeout=30000) as scraper:
            page = scraper._browser.new_page()
            page.set_default_timeout(30000)
            page.set_viewport_size({"width": 1920, "height": 1080})

            print("📄 Cargando https://store.wom.cl/accesorios/...")
            page.goto("https://store.wom.cl/accesorios/", wait_until="load")
            time.sleep(5)

            # Scroll agresivo
            for i in range(10):
                page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(0.5)

            time.sleep(3)

            # Extraer TODOS los datos
            all_data = page.evaluate("""
                () => {
                    const data = {
                        allLinks: [],
                        allText: document.body.innerText.slice(0, 2000),
                        allPrices: [],
                        allElements: [],
                    };

                    // TODOS los links
                    const links = Array.from(document.querySelectorAll('a[href]'));
                    for (const a of links) {
                        const href = a.getAttribute('href');
                        if (href.includes('accesorios') || href.includes('producto')) {
                            data.allLinks.push({
                                href: href,
                                text: (a.innerText || '').slice(0, 80),
                            });
                        }
                    }

                    // TODOS los precios
                    const pricePattern = /\$\s*[\d.,]+/g;
                    const bodyText = document.body.innerText;
                    const matches = bodyText.match(pricePattern);
                    if (matches) {
                        data.allPrices = matches.slice(0, 10);
                    }

                    // Elementos con clase "product" o similar
                    const productElements = document.querySelectorAll('[class*="product"], [data-testid*="product"]');
                    for (const el of Array.from(productElements).slice(0, 5)) {
                        data.allElements.push({
                            tag: el.tagName,
                            class: el.className,
                            text: (el.innerText || '').slice(0, 100),
                        });
                    }

                    return data;
                }
            """)

            print(f"\n✓ Análisis completado\n")
            print(f"📎 Links encontrados: {len(all_data['allLinks'])}")
            for link in all_data['allLinks'][:10]:
                print(f"   {link['href']}")
                print(f"   → {link['text']}\n")

            print(f"💰 Precios encontrados: {all_data['allPrices']}")

            print(f"\n📦 Elementos con 'product': {len(all_data['allElements'])}")
            for el in all_data['allElements']:
                print(f"   {el['tag']} class='{el['class']}'")
                print(f"   → {el['text']}\n")

            print(f"📝 Primeros 2000 chars del body:")
            print(all_data['allText'])

            page.close()

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    debug_all_content()
