"""
Web scraper for store.wom.cl - extracts product prices.
Uses Playwright for JavaScript-rendered content.
PLP: Product Listing Page. Modalidad = segmento de URL (equipos/renovacion, equipos/prepago, etc).
"""
import re
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
from urllib.parse import urlparse

import pandas as pd


def normalize_price(value: str) -> Optional[float]:
    """Convert Chilean price string to float."""
    if not value:
        return None
    cleaned = re.sub(r'[^\d.,\-]', '', str(value).replace(' ', ''))
    cleaned = cleaned.replace('.', '').replace(',', '.')
    try:
        return float(cleaned)
    except ValueError:
        return None


def _infer_modality_from_path(category_path: str) -> str:
    """Inferir modalidad desde la URL: /equipos/renovacion -> renovacion, /equipos/linea-nueva -> linea_nueva."""
    path = category_path.strip('/')
    parts = [p for p in path.split('/') if p]
    if len(parts) >= 2 and parts[0] == 'equipos':
        slug = parts[1].replace('-', '_')
        return slug
    if len(parts) == 1 and parts[0] == 'equipos':
        return 'precio_normal'
    return ''


def extract_sku_from_url(url: str) -> Optional[str]:
    """Extract SKU/code from WOM product URL: /equipos/SKU/Name or /accesorios/..."""
    match = re.search(r'/equipos/([^/]+)/|/accesorios/([^/]+)/', url)
    if match:
        return match.group(1) or match.group(2)
    return None


def _extract_prices_from_card(link, modality: str) -> Tuple[Optional[str], Optional[str], bool]:
    """
    Extrae ambos precios de la tarjeta PLP cuando estén disponibles.
    - precio_descuento: precio grande/destacado (con descuento de la modalidad)
    - precio_normal: precio tachado ("Precio normal") cuando se muestra
    - precio_normal_sin_precio: True si "Precio normal" muestra "Sin precio" (error)

    Retorna (precio_descuento_str, precio_normal_str, precio_normal_sin_precio).
    """
    precio_descuento = None
    precio_normal = None
    precio_normal_sin_precio = False
    try:
        card_text = link.inner_text() or ''
        all_prices = re.findall(r'\$\s*([\d.,]+)', card_text)

        # Detectar "Precio normal: Sin precio" (error en la web)
        if re.search(r'precio\s+normal[:\s]*sin\s+precio', card_text, re.IGNORECASE):
            precio_normal_sin_precio = True

        for el in link.query_selector_all('[class*="price"], .price, [class*="Price"], span, div') or []:
            txt = (el.inner_text() or '').strip()
            if not txt or len(txt) > 80:
                continue
            has_precio_normal = 'precio normal' in txt.lower()
            has_sin_precio = 'sin precio' in txt.lower()
            if has_precio_normal and has_sin_precio:
                precio_normal_sin_precio = True
            if '$' not in txt:
                continue
            m = re.search(r'\$\s*[\d.,]+', txt)
            if not m:
                continue
            price_str = m.group()
            is_struck = bool(el.query_selector('s, del, strike'))

            if has_precio_normal or is_struck:
                if not has_sin_precio:
                    precio_normal = price_str
            else:
                precio_descuento = price_str

        if not precio_descuento and not precio_normal:
            struck = link.query_selector('s, del, strike, [style*="line-through"]')
            if struck:
                struck_txt = struck.inner_text() or ''
                if 'sin precio' in struck_txt.lower():
                    precio_normal_sin_precio = True
                else:
                    m = re.search(r'\$\s*[\d.,]+', struck_txt)
                    if m:
                        precio_normal = m.group()
            for sel in ['[class*="price"]', '.price', '[class*="Price"]']:
                for el in link.query_selector_all(sel) or []:
                    txt = el.inner_text() if el else ''
                    if re.search(r'\$[\d.,]+', txt) and 'precio normal' not in txt.lower():
                        precio_descuento = re.search(r'\$\s*[\d.,]+', txt).group()
                        break
                if precio_descuento:
                    break
        if not precio_descuento and not precio_normal and all_prices:
            p = f'${all_prices[-1]}' if not all_prices[-1].startswith('$') else all_prices[-1]
            precio_descuento = p
        # Si no hay precio tachado (y no es "Sin precio") → el precio grande ES el normal
        if not precio_normal and not precio_normal_sin_precio and precio_descuento:
            precio_normal = precio_descuento
    except Exception:
        pass
    return (precio_descuento, precio_normal, precio_normal_sin_precio)


def _get_product_card_element(link) -> "ElementHandle":
    """
    Busca el contenedor de la tarjeta de producto.
    El link puede ser solo el botón; el precio está en el card padre.
    """
    try:
        current = link
        for _ in range(8):
            try:
                parent_handle = current.evaluate_handle("el => el.parentElement")
                if not parent_handle:
                    break
                parent = parent_handle.as_element()
                txt = (parent.inner_text() or '')[:600]
                if txt and '$' in txt and re.search(r'\$[\d.,]+', txt):
                    return parent
                current = parent
            except Exception:
                break
        return link
    except Exception:
        return link


def extract_name_from_url(url: str) -> str:
    """Extract product name from URL slug: /equipos/XXX/Samsung-Galaxy-A54-5G/ -> Samsung Galaxy A54 5G"""
    match = re.search(r'/(?:equipos|accesorios)/[^/]+/([^/?#]+)', url)
    if match:
        return match.group(1).replace('-', ' ').strip()
    return ''


def extract_sku_from_pdp(html: str) -> Optional[str]:
    """Extract WOM SKU from PDP content. El SKU está en la página (ej: 'SKU 001.002.2861'), no en la URL."""
    match = re.search(r'SKU\s*(\d{3}\.\d{3}\.\d{4})', html, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    match = re.search(r'SKU[:\s]*([\d.]+)', html, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return None


def extract_struck_through_price(html: str) -> Optional[float]:
    """Extract Precio Normal (precio tachado) from PDP. Es el precio sin descuento."""
    struck_patterns = [
        r'<s[^>]*>\s*\$?\s*([\d.,]+)\s*</s>',
        r'<del[^>]*>\s*\$?\s*([\d.,]+)\s*</del>',
        r'<strike[^>]*>\s*\$?\s*([\d.,]+)\s*</strike>',
        r'line-through[^>]*>[\s\S]*?\$?\s*([\d.,]+)',
        r'text-decoration:\s*line-through[^>]*>[\s\S]*?\$?\s*([\d.,]+)',
    ]
    for pat in struck_patterns:
        match = re.search(pat, html, re.IGNORECASE | re.DOTALL)
        if match:
            p = normalize_price(match.group(1))
            if p and p > 100:
                return p
    return None


class WOMScraper:
    """Scraper for store.wom.cl product pages."""

    def __init__(
        self,
        base_url: str = "https://store.wom.cl",
        headless: bool = True,
        timeout: int = 60000,
        delay: float = 2.0,
    ):
        self.base_url = base_url.rstrip('/')
        self.headless = headless
        self.timeout = timeout
        self.delay = delay
        self._browser = None
        self._playwright = None

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

    def start(self) -> None:
        """Initialize Playwright browser."""
        try:
            from playwright.sync_api import sync_playwright
            self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.launch(headless=self.headless)
        except ImportError:
            raise ImportError(
                "Playwright no está instalado. Ejecuta: pip install playwright && playwright install chromium"
            )

    def stop(self) -> None:
        """Close browser."""
        if self._browser:
            self._browser.close()
        if self._playwright:
            self._playwright.stop()

    def scrape_category(
        self, category_path: str, modality: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Scrape PLP (Product Listing Page) - product cards.
        Modalidad = segmento de URL (equipos/renovacion, equipos/prepago, etc).
        """
        if not self._browser:
            self.start()

        modality = modality or _infer_modality_from_path(category_path)
        url = f"{self.base_url}{category_path.rstrip('/')}"
        page = self._browser.new_page()
        page.set_default_timeout(self.timeout)
        page.set_viewport_size({"width": 1920, "height": 1080})
        page.set_extra_http_headers({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "es-CL,es;q=0.9",
        })

        products = []
        try:
            page.goto(url, wait_until="load", timeout=self.timeout)
            time.sleep(4)

            # Esperar que carguen los product links (carga dinámica)
            try:
                page.wait_for_function("""
                    () => {
                        const links = document.querySelectorAll('a[href*="/equipos/"]');
                        for (const a of links) {
                            const path = (a.getAttribute('href') || '').split('?')[0];
                            const parts = path.split('/').filter(p => p);
                            if (parts.length >= 3 && parts[0] === 'equipos' &&
                                !['portabilidad','renovacion','linea-nueva','prepago'].includes(parts[1])) {
                                return true;
                            }
                        }
                        return false;
                    }
                """, timeout=25000)
            except Exception:
                pass
            time.sleep(2)

            # Scroll para lazy-load
            for _ in range(4):
                try:
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(1.5)
                except Exception:
                    pass
            try:
                page.evaluate("window.scrollTo(0, 0);")
                time.sleep(0.5)
            except Exception:
                pass

            # Estrategia 1: Product cards como contenedor
            card_selectors = [
                '[class*="ProductCard"]',
                '[class*="product-card"]',
                'article[class*="product"]',
                '[class*="product"][class*="card"]',
                'article',
            ]
            cards = []
            for sel in card_selectors:
                found = page.query_selector_all(sel)
                valid = [c for c in found if c.query_selector('a[href*="/equipos/"]') and (
                    '$' in (c.inner_text() or '') or c.query_selector('[class*="price"], [class*="Price"]')
                )]
                if len(valid) >= 2:
                    cards = valid
                    break

            if cards:
                products = self._extract_from_cards(cards, modality)
            if not products:
                products = self._extract_from_links(page, modality)

        finally:
            page.close()

        df = pd.DataFrame(products)
        expected_cols = [
            'sku', 'name', 'price', 'precio_descuento', 'precio_normal',
            'precio_normal_sin_precio', 'url', 'modality'
        ]
        for col in expected_cols:
            if col not in df.columns:
                df[col] = None
        return df

    def scrape_accessories(self) -> pd.DataFrame:
        """
        Scrape accesorios desde /accesorios/ de WOM Store.
        Extrae datos del DOM renderizado con JavaScript.
        Retorna DataFrame con accesorios encontrados.
        """
        if not self._browser:
            self.start()

        url = "https://store.wom.cl/accesorios/"
        page = self._browser.new_page()
        page.set_default_timeout(max(self.timeout, 60000))
        page.set_viewport_size({"width": 1920, "height": 1080})
        page.set_extra_http_headers({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "es-CL,es;q=0.9",
        })

        products = []
        try:
            try:
                page.goto(url, wait_until="networkidle", timeout=60000)
            except Exception:
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=45000)
                except Exception:
                    page.goto(url, timeout=30000)

            # Esperar a que carguen los productos
            time.sleep(5)

            # Hacer scroll para asegurar que todo está cargado
            for i in range(3):
                try:
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(1)
                except Exception:
                    pass

            time.sleep(2)

            # Extraer productos usando JavaScript (después del render)
            products = self._extract_accessories_via_js(page)

        finally:
            page.close()

        df = pd.DataFrame(products)
        expected_cols = [
            'sku', 'name', 'price', 'precio_descuento', 'precio_normal',
            'precio_normal_sin_precio', 'url', 'modality'
        ]
        for col in expected_cols:
            if col not in df.columns:
                df[col] = None
        return df

    def _extract_accessories_via_js(self, page) -> list:
        """Extrae accesorios usando JavaScript para acceder al DOM renderizado."""
        try:
            data = page.evaluate("""
                () => {
                    const products = [];
                    const seen = new Set();

                    // Buscar todos los enlaces a accesorios
                    const links = document.querySelectorAll('a[href*="/accesorios/"]');

                    for (const link of links) {
                        const href = link.getAttribute('href');
                        if (!href || seen.has(href)) continue;

                        // Filtrar solo enlaces de productos (no navegación)
                        if (href.includes('?sku=') || /\\/accesorios\\/[A-Za-z].*-[A-Za-z0-9]/.test(href)) {
                            seen.add(href);

                            // Extraer nombre de la URL
                            const nameMatch = href.match(/\\/accesorios\\/([^?]+)/);
                            if (!nameMatch) continue;

                            let name = nameMatch[1]
                                .replace(/[?#].*/,'')
                                .replace(/-/g, ' ')
                                .trim();

                            // Extraer SKU
                            const skuMatch = href.match(/sku=([^&]+)/);
                            const sku = skuMatch ? skuMatch[1] : '';

                            // Obtener precio desde el card más cercano
                            let price = null;
                            let priceDescuento = null;
                            let priceNormal = null;

                            // Buscar el card contenedor
                            let card = link.closest('article, [class*="card"], [class*="product"], li, div[role]');
                            if (!card) card = link.parentElement;

                            if (card) {
                                const text = card.innerText || '';
                                const priceMatches = text.match(/\\$\\s*[\\d.,]+/g);

                                if (priceMatches && priceMatches.length > 0) {
                                    // Convertir precio a número
                                    const getPriceValue = (str) => {
                                        const match = str.match(/[\\d.,]+/);
                                        if (!match) return null;
                                        let val = match[0].replace(/\\./g, '').replace(',', '.');
                                        return parseFloat(val);
                                    };

                                    if (priceMatches.length >= 2) {
                                        priceNormal = getPriceValue(priceMatches[0]);
                                        priceDescuento = getPriceValue(priceMatches[1]);
                                        price = priceDescuento || priceNormal;
                                    } else {
                                        price = getPriceValue(priceMatches[0]);
                                        priceNormal = price;
                                    }
                                }
                            }

                            if (price !== null) {
                                products.push({
                                    sku: sku,
                                    name: name,
                                    price: price,
                                    precio_descuento: priceDescuento,
                                    precio_normal: priceNormal,
                                    url: href.startsWith('http') ? href : 'https://store.wom.cl' + href,
                                    modality: 'accesorios',
                                });
                            }
                        }
                    }

                    return products;
                }
            """)

            return data if data else []
        except Exception:
            return []

    def _extract_from_json_schema(self, page) -> list:
        """Extrae accesorios del JSON Schema (structured data) de la página."""
        try:
            import json
            html = page.content()
            schema_items = []

            # Buscar JSON Schema en tags <script type="application/ld+json">
            import re
            patterns = re.findall(
                r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
                html,
                re.DOTALL | re.IGNORECASE
            )

            for pattern in patterns:
                try:
                    data = json.loads(pattern)
                    # Buscar ItemList
                    if isinstance(data, dict):
                        if data.get("@type") == "ItemList":
                            items = data.get("itemListElement", [])
                            schema_items.extend(items)
                        elif data.get("@type") == "ListItem" and "url" in data:
                            schema_items.append(data)
                    elif isinstance(data, list):
                        for item in data:
                            if isinstance(item, dict) and item.get("@type") == "ItemList":
                                items = item.get("itemListElement", [])
                                schema_items.extend(items)
                except (json.JSONDecodeError, TypeError):
                    continue

            # Extraer precios del texto visible
            body_text = page.inner_text() or ""
            price_data = self._extract_prices_from_text(body_text)

            products = []
            seen = set()
            for item in schema_items:
                try:
                    if not isinstance(item, dict):
                        continue
                    name = item.get("name", "").strip()
                    url = item.get("url", "").strip()
                    if not name or not url:
                        continue
                    if url in seen:
                        continue
                    seen.add(url)

                    # Extraer SKU de la URL si existe
                    sku_match = re.search(r'sku=([^&]+)', url)
                    sku = sku_match.group(1) if sku_match else ""

                    # Obtener precio del diccionario de precios por nombre
                    price_info = price_data.get(name, {})

                    products.append({
                        'sku': sku,
                        'name': name,
                        'price': price_info.get('price'),
                        'precio_descuento': price_info.get('precio_descuento'),
                        'precio_normal': price_info.get('precio_normal'),
                        'precio_normal_sin_precio': False,
                        'url': url,
                        'modality': 'accesorios',
                    })
                except Exception:
                    continue

            return products
        except Exception:
            return []

    def _extract_prices_from_text(self, text: str) -> dict:
        """
        Extrae precios del texto de la página.
        Retorna dict {nombre_producto: {price, precio_descuento, precio_normal}}
        """
        import re
        prices_by_product = {}

        # Patrón: nombre producto seguido de precios
        # Ejemplo: "Samsung Galaxy Tab A11 64GB\n$139.990"
        lines = text.split('\n')
        for i, line in enumerate(lines):
            line = line.strip()
            # Si es un nombre de producto (línea con 3+ palabras y sin dinero)
            if (len(line) > 5 and
                not re.search(r'\$', line) and
                line[0].isupper() and
                (i + 1 < len(lines))):

                # Buscar precios en las siguientes líneas
                prices_found = []
                for j in range(i + 1, min(i + 5, len(lines))):
                    next_line = lines[j].strip()
                    if re.search(r'\$\s*[\d.,]+', next_line):
                        price_match = re.search(r'\$\s*([\d.,]+)', next_line)
                        if price_match:
                            price_str = price_match.group(1)
                            try:
                                price = normalize_price(f"${price_str}")
                                if price:
                                    prices_found.append(price)
                            except:
                                pass
                    elif re.search(r'\d+\s*%\s*DCTO', next_line, re.IGNORECASE):
                        # Descuento encontrado
                        continue
                    elif next_line and not next_line[0].isupper():
                        # Otra metadata
                        continue
                    else:
                        break

                if prices_found:
                    # Si hay 2 precios, el primero es normal, el segundo es descuento
                    if len(prices_found) >= 2:
                        prices_by_product[line] = {
                            'precio_normal': prices_found[0],
                            'precio_descuento': prices_found[1],
                            'price': prices_found[1],  # El precio principal es el descuento
                        }
                    elif len(prices_found) == 1:
                        prices_by_product[line] = {
                            'precio_normal': prices_found[0],
                            'precio_descuento': None,
                            'price': prices_found[0],
                        }

        return prices_by_product

    def _extract_accessories_from_cards(self, cards: list) -> list:
        """Extrae datos de cada product card de accesorios."""
        products = []
        seen = set()
        for card in cards:
            try:
                link = card.query_selector('a[href*="/accesorios/"]')
                if not link:
                    continue
                href = link.get_attribute('href')
                if not href:
                    continue
                path_key = href.rstrip('/')
                if path_key in seen:
                    continue
                seen.add(path_key)

                full_url = href if href.startswith('http') else f"{self.base_url}{href}"
                name_elem = card.query_selector('h3, h2, [class*="title"], [class*="name"], [class*="Title"]') or link
                name = (name_elem.inner_text() if name_elem else '').strip()
                if not name or len(name) < 3:
                    name = extract_name_from_url(href)

                precio_descuento_str, precio_normal_str, precio_normal_sin_precio = _extract_prices_from_card(card, 'accesorios')
                price_raw = precio_descuento_str or precio_normal_str
                price = normalize_price(price_raw) if price_raw else None
                if price is None:
                    continue

                products.append({
                    'sku': extract_sku_from_url(href) or '',
                    'name': name,
                    'price': price,
                    'precio_descuento': normalize_price(precio_descuento_str) if precio_descuento_str else None,
                    'precio_normal': normalize_price(precio_normal_str) if precio_normal_str else None,
                    'precio_normal_sin_precio': precio_normal_sin_precio,
                    'url': full_url,
                    'modality': 'accesorios',
                })
            except Exception:
                continue
        return products

    def _extract_accessories_from_links(self, page) -> list:
        """Fallback: extraer accesorios desde enlaces."""
        products = []
        links = page.query_selector_all('a[href*="/accesorios/"]')
        seen = set()

        for link in links:
            try:
                href = link.get_attribute('href')
                if not href:
                    continue
                path_key = href.rstrip('/')
                if path_key in seen:
                    continue
                seen.add(path_key)

                full_url = href if href.startswith('http') else f"{self.base_url}{href}"
                card = _get_product_card_element(link)
                name_elem = card.query_selector('h3, h2, [class*="title"], [class*="name"]') or link
                name = (name_elem.inner_text() if name_elem else '').strip()
                if not name or len(name) < 3:
                    name = extract_name_from_url(href)

                precio_descuento_str, precio_normal_str, precio_normal_sin_precio = _extract_prices_from_card(card, 'accesorios')
                price_raw = precio_descuento_str or precio_normal_str
                price = normalize_price(price_raw) if price_raw else None
                if price is None:
                    continue

                products.append({
                    'sku': extract_sku_from_url(href) or '',
                    'name': name,
                    'price': price,
                    'precio_descuento': normalize_price(precio_descuento_str) if precio_descuento_str else None,
                    'precio_normal': normalize_price(precio_normal_str) if precio_normal_str else None,
                    'precio_normal_sin_precio': precio_normal_sin_precio,
                    'url': full_url,
                    'modality': 'accesorios',
                })
            except Exception:
                continue
        return products

    def _extract_from_cards(self, cards: list, modality: str) -> list:
        """Extrae datos de cada product card."""
        products = []
        seen = set()
        for card in cards:
            try:
                link = card.query_selector('a[href*="/equipos/"]')
                if not link:
                    continue
                href = link.get_attribute('href')
                if not href:
                    continue
                parsed = urlparse(href)
                path = parsed.path
                parts = [p for p in path.split('/') if p]
                if len(parts) < 3:
                    continue
                if parts[0] != 'equipos' or (len(parts) == 2 and parts[1] in ('portabilidad', 'renovacion', 'linea-nueva', 'prepago')):
                    continue
                path_key = path.rstrip('/')
                if path_key in seen:
                    continue
                seen.add(path_key)

                full_url = href if href.startswith('http') else f"{self.base_url}{href}"
                name_elem = card.query_selector('h3, h2, [class*="title"], [class*="name"], [class*="Title"]') or link
                name = (name_elem.inner_text() if name_elem else '').strip()
                if not name or len(name) < 5:
                    name = extract_name_from_url(href)

                precio_descuento_str, precio_normal_str, precio_normal_sin_precio = _extract_prices_from_card(card, modality)
                if modality == 'precio_normal':
                    price_raw = precio_normal_str or precio_descuento_str
                else:
                    price_raw = precio_descuento_str or precio_normal_str
                price = normalize_price(price_raw) if price_raw else None
                if price is None:
                    continue

                products.append({
                    'sku': extract_sku_from_url(href) or '',
                    'name': name,
                    'price': price,
                    'precio_descuento': normalize_price(precio_descuento_str) if precio_descuento_str else None,
                    'precio_normal': normalize_price(precio_normal_str) if precio_normal_str else None,
                    'precio_normal_sin_precio': precio_normal_sin_precio,
                    'url': full_url,
                    'modality': modality or '',
                })
            except Exception:
                continue
        return products

    def _extract_from_links(self, page, modality: str) -> list:
        """Fallback: extraer desde enlaces de producto."""
        products = []
        links = page.query_selector_all('a[href*="/equipos/"]')
        seen = set()
        modality_slugs = ('portabilidad', 'renovacion', 'linea-nueva', 'prepago')

        for link in links:
            try:
                href = link.get_attribute('href')
                if not href:
                    continue
                parsed = urlparse(href)
                path = parsed.path
                parts = [p for p in path.split('/') if p]
                if len(parts) < 3:
                    continue
                if parts[0] != 'equipos' or (len(parts) == 2 and parts[1] in modality_slugs):
                    continue
                path_key = path.rstrip('/')
                if path_key in seen:
                    continue
                seen.add(path_key)

                full_url = href if href.startswith('http') else f"{self.base_url}{href}"
                card = _get_product_card_element(link)
                name_elem = card.query_selector('h3, h2, [class*="title"], [class*="name"]') or link
                name = (name_elem.inner_text() if name_elem else '').strip()
                if not name or len(name) < 5:
                    name = extract_name_from_url(href)

                precio_descuento_str, precio_normal_str, precio_normal_sin_precio = _extract_prices_from_card(card, modality)
                if modality == 'precio_normal':
                    price_raw = precio_normal_str or precio_descuento_str
                else:
                    price_raw = precio_descuento_str or precio_normal_str
                price = normalize_price(price_raw) if price_raw else None
                if price is None:
                    continue

                products.append({
                    'sku': extract_sku_from_url(href) or '',
                    'name': name,
                    'price': price,
                    'precio_descuento': normalize_price(precio_descuento_str) if precio_descuento_str else None,
                    'precio_normal': normalize_price(precio_normal_str) if precio_normal_str else None,
                    'precio_normal_sin_precio': precio_normal_sin_precio,
                    'url': full_url,
                    'modality': modality or '',
                })
            except Exception:
                continue
        return products

    def debug_category_links(self, category_path: str) -> dict:
        """
        Debug: inspeccionar estructura de la PLP.
        Devuelve TODOS los <a> con su href y un pequeño snippet de texto/clases
        del card padre, para poder ver cómo están armados los product cards.
        """
        if not self._browser:
            self.start()

        url = f"{self.base_url}{category_path.rstrip('/')}"
        page = self._browser.new_page()
        page.set_default_timeout(self.timeout)
        page.set_viewport_size({"width": 1920, "height": 1080})
        page.set_extra_http_headers({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "es-CL,es;q=0.9",
        })

        try:
            page.goto(url, wait_until="load", timeout=self.timeout)
            time.sleep(3)
            try:
                page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(1.5)
                page.evaluate("window.scrollTo(0, 0);")
            except Exception:
                pass

            debug = page.evaluate(
                """
                () => {
                    const allLinks = Array.from(document.querySelectorAll('a[href]'));
                    const links = [];
                    for (const a of allLinks) {
                        const href = a.getAttribute('href') || '';
                        const parent = a.closest('article, [class*="product"], [class*="Product"], [class*="card"], li, div');
                        const parentClass = parent && parent.className ? String(parent.className) : '';
                        const parentText = parent && parent.innerText ? parent.innerText.trim().slice(0, 260) : '';
                        links.push({
                            href,
                            linkText: (a.innerText || '').trim().slice(0, 80),
                            parentClass,
                            parentTextSample: parentText,
                        });
                        if (links.length >= 60) break;
                    }
                    return {
                        totalLinks: allLinks.length,
                        links,
                    };
                }
                """
            )
            debug["url"] = url
            return debug
        finally:
            page.close()

    def _scrape_fallback(
        self, page, url: str, modality: Optional[str] = None
    ) -> list:
        """Fallback: scrape individual product links from page."""
        products = []
        links = page.query_selector_all('a[href*="/equipos/"], a[href*="/accesorios/"]')
        seen = set()

        for link in links[:30]:
            href = link.get_attribute('href')
            if not href or href in seen or href.count('/') < 3:
                continue
            seen.add(href)
            full_url = href if href.startswith('http') else f"{self.base_url}{href}"
            prod = self.scrape_product_page(full_url, modality)
            if prod:
                products.append(prod)
            time.sleep(self.delay)

        return products

    def scrape_product_page(
        self, url: str, modality: Optional[str] = None
    ) -> Optional[dict]:
        """
        Scrape PDP: SKU desde la página (no URL), Precio Normal = precio tachado.
        El precio tachado es el sin descuento; el precio destacado es el con descuento.
        """
        if not self._browser:
            self.start()

        page = self._browser.new_page()
        page.set_default_timeout(self.timeout)
        try:
            page.goto(url, wait_until="load", timeout=self.timeout)
            time.sleep(self.delay + 1)

            html = page.content()

            sku = extract_sku_from_pdp(html)
            if not sku:
                sku = extract_sku_from_url(url) or ''

            name_sel = page.query_selector('h1, [class*="product-title"], [class*="ProductTitle"]')
            name = (name_sel.inner_text() if name_sel else '').strip() or extract_name_from_url(url)

            price = None
            if modality == 'precio_normal' or not modality:
                price = extract_struck_through_price(html)
            if price is None:
                price_sel = page.query_selector(
                    's, del, strike, [style*="line-through"], [class*="line-through"]'
                )
                if price_sel:
                    price = normalize_price(price_sel.inner_text())
            if price is None:
                price_sel = page.query_selector(
                    '[class*="price"], [class*="Price"], [data-price], .precio'
                )
                price_str = price_sel.inner_text() if price_sel else ''
                if not price_str:
                    price_match = re.search(r'\$\s*[\d.,]+', html)
                    if price_match:
                        price_str = price_match.group()
                price = normalize_price(price_str)

            return {
                'sku': sku,
                'name': name,
                'price': price,
                'url': url,
                'modality': modality or 'precio_normal',
            }
        except Exception:
            return None
        finally:
            page.close()

    def scrape_all_modalities(
        self,
        modalities: List[Dict],
        use_api: bool = False,
        api_skus: Optional[List[str]] = None,
        api_config: Optional[Dict] = None,
    ) -> pd.DataFrame:
        """
        Scrape equipos. Si use_api=True y api_skus, usa getGraphqlDataFromSkus.
        Si no, usa Playwright (DOM).
        """
        if use_api and api_skus:
            return self._scrape_via_api(api_skus, modalities, api_config or {})

        dfs = []
        for mod in modalities:
            url = mod.get("url")
            mod_id = mod.get("id", "")
            if not url or (isinstance(url, str) and url.lower() == "null"):
                continue
            df = self.scrape_category(url, modality=mod_id)
            dfs.append(df)
            time.sleep(self.delay)

        if not dfs:
            return pd.DataFrame(
                columns=[
                    'sku', 'name', 'price', 'precio_descuento', 'precio_normal',
                    'precio_normal_sin_precio', 'url', 'modality'
                ]
            )

        combined = pd.concat(dfs, ignore_index=True)

        # Derivar filas precio_normal: no hay URL propia, viene del tachado (o grande si no hay descuento)
        precio_normal_rows = []
        seen = set()
        for _, row in combined.iterrows():
            pn = row.get("precio_normal")
            if pn is not None and pd.notna(pn) and float(pn) > 0:
                key = (str(row.get("name", "")).strip(), "precio_normal")
                if key not in seen:
                    seen.add(key)
                    precio_normal_rows.append({
                        "sku": row.get("sku", ""),
                        "name": row.get("name", ""),
                        "price": float(pn),
                        "precio_descuento": None,
                        "precio_normal": float(pn),
                        "precio_normal_sin_precio": row.get("precio_normal_sin_precio", False),
                        "url": row.get("url", ""),
                        "modality": "precio_normal",
                    })
        if precio_normal_rows:
            combined = pd.concat([combined, pd.DataFrame(precio_normal_rows)], ignore_index=True)
        return combined

    def _scrape_via_api(
        self, skus: List[str], modalities: List[Dict], api_config: Dict
    ) -> pd.DataFrame:
        """Usa la API getGraphqlDataFromSkus para obtener precios por modalidad."""
        from src.scraper.wom_api_client import fetch_products_from_api

        mod_ids = [m.get("id", "") for m in modalities if m.get("id")]
        mod_ids = [m for m in mod_ids if m and m != "accesorios"]
        if "precio_normal" not in mod_ids:
            mod_ids.append("precio_normal")

        base_url = api_config.get("base_url", "https://store-srv.wom.cl/rest/V1/content")

        return fetch_products_from_api(
            skus=skus,
            modalities=mod_ids,
            base_url=base_url,
            connect_timeout=float(api_config.get("connect_timeout", 90)),
            read_timeout=float(api_config.get("read_timeout", 180)),
            batch_size=int(api_config.get("batch_size", 10)),
            retries=int(api_config.get("retries", 5)),
        )

    def scrape_all_from_excel(
        self, excel_path: Union[str, Path], sku_col: str = "sku", url_col: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Scrape prices for products listed in Excel.
        If url_col exists, use URLs directly. Else build from SKU.
        """
        df = pd.read_excel(excel_path, sheet_name=0)
        products = []

        has_url = url_col and url_col in df.columns
        sku_col = sku_col if sku_col in df.columns else df.columns[0]

        for _, row in df.iterrows():
            if has_url:
                url = row[url_col]
                if pd.notna(url) and str(url).startswith('http'):
                    prod = self.scrape_product_page(url)
                    if prod:
                        products.append(prod)
            else:
                sku = str(row[sku_col]).strip()
                if sku and sku != 'nan':
                    url = f"{self.base_url}/equipos/{sku}/"
                    prod = self.scrape_product_page(url)
                    if prod:
                        products.append(prod)
            time.sleep(self.delay)

        return pd.DataFrame(products)
