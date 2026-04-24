#!/usr/bin/env python3
"""
Script de prueba para verificar que el scraping de accesorios funciona.
Uso: python test_accessories_scraper.py
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

def test_accessories_scraper():
    """Prueba el scraper de accesorios."""
    print("🔍 Probando scraper de accesorios...\n")

    try:
        from src.scraper.wom_scraper import WOMScraper

        print("✓ WOMScraper importado")
        print("📦 Iniciando browser (esto puede tardar unos segundos)...\n")

        with WOMScraper(headless=True, timeout=30000) as scraper:
            print("🌐 Scrapeando /accesorios/ de WOM Store...")
            accesorios = scraper.scrape_accessories()

            print(f"\n✓ Scraping completado")
            print(f"📊 Total accesorios encontrados: {len(accesorios)}")

            if not accesorios.empty:
                print("\n📋 Primeros 5 accesorios:\n")
                print(accesorios.head(5)[["name", "price", "url", "modality"]].to_string(index=False))
                print("\n✅ Scraper de accesorios funciona correctamente!")
                return True
            else:
                print("⚠️  No se encontraron accesorios")
                return False

    except ImportError as e:
        print(f"❌ Error de importación: {e}")
        print("\nPosible solución:")
        print("  pip install playwright")
        print("  playwright install chromium")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_accessories_scraper()
    sys.exit(0 if success else 1)
