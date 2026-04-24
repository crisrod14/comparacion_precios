#!/usr/bin/env python3
"""
Script de debug para inspeccionar la estructura de /accesorios/
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

def debug_accessories_page():
    """Inspecciona la estructura de la página de accesorios."""
    print("🔍 Inspeccionando estructura de /accesorios/...\n")

    try:
        from src.scraper.wom_scraper import WOMScraper

        with WOMScraper(headless=True, timeout=30000) as scraper:
            print("📄 Obteniendo HTML de /accesorios/...")
            page = scraper._browser.new_page()
            page.set_default_timeout(30000)
            page.set_viewport_size({"width": 1920, "height": 1080})

            page.goto("https://store.wom.cl/accesorios/", wait_until="load")
            print("✓ Página cargada")

            # Scroll
            page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
            import time
            time.sleep(3)

            # Extraer info
            debug_info = page.evaluate("""
                () => {
                    const info = {
                        title: document.title,
                        links: [],
                        cards: [],
                        prices: [],
                    };

                    // Links a accesorios
                    const accessoryLinks = Array.from(document.querySelectorAll('a[href*="/accesorios/"]')).slice(0, 10);
                    for (const a of accessoryLinks) {
                        info.links.push({
                            href: a.getAttribute('href'),
                            text: (a.innerText || '').slice(0, 50),
                        });
                    }

                    // Cards (varios selectores)
                    const selectors = [
                        'article',
                        '[class*="card"]',
                        '[class*="product"]',
                        'li[class*="product"]',
                    ];
                    for (const sel of selectors) {
                        const cards = document.querySelectorAll(sel);
                        info.cards.push({
                            selector: sel,
                            count: cards.length,
                        });
                    }

                    // Precios
                    const prices = Array.from(document.querySelectorAll('*')).filter(el =>
                        el.innerText && /\$\s*[\d.,]+/.test(el.innerText)
                    ).slice(0, 5);
                    for (const p of prices) {
                        info.prices.push({
                            tag: p.tagName,
                            text: (p.innerText || '').slice(0, 60),
                        });
                    }

                    return info;
                }
            """)

            print("\n📋 Información de la página:\n")
            print(f"Título: {debug_info['title']}")

            print(f"\n🔗 Links a accesorios encontrados: {len(debug_info['links'])}")
            for link in debug_info['links'][:3]:
                print(f"   - {link['href']}")
                print(f"     Texto: {link['text']}")

            print(f"\n📦 Cards por selector:")
            for card_info in debug_info['cards']:
                print(f"   - {card_info['selector']}: {card_info['count']} elementos")

            print(f"\n💰 Precios encontrados: {len(debug_info['prices'])}")
            for price in debug_info['prices'][:3]:
                print(f"   - {price['tag']}: {price['text']}")

            # HTML snippet
            print("\n📄 HTML snippet (primeros 1000 chars):")
            html = page.content()
            print(html[:1000])

            page.close()

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    debug_accessories_page()
