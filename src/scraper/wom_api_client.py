"""
Cliente API para store-srv.wom.cl - getGraphqlDataFromSkus.
Obtiene precios por modalidad sin depender del DOM.
"""
import re
import time
from typing import Any, Dict, Optional

import pandas as pd
import requests


# Colores a quitar del final del nombre para la URL PDP (la URL no incluye el color)
_URL_COLORS = (
    "black", "blue", "white", "red", "green", "gold", "silver", "pink", "purple",
    "grey", "gray", "negro", "azul", "blanco", "rojo", "verde", "dorado",
    "plateado", "rose", "midnight", "starlight", "natural", "yellow", "amarillo",
    "space",  # "Space Black" -> quitar "Black" y "Space"
)


def _slugify_for_url(name: str) -> str:
    """Slug para URL PDP: /equipos/{sku}/{Apple-iPhone-15-5G-128GB} - sin color al final."""
    s = str(name).strip()
    # Quitar color al final (ej. "Apple iPhone 15 5G 128GB Black" -> "Apple iPhone 15 5G 128GB")
    words = s.split()
    while words and words[-1].lower() in _URL_COLORS:
        words.pop()
    s = " ".join(words)
    s = re.sub(r'[\s]+', '-', s)
    s = re.sub(r'[^\w\-]', '', s, flags=re.IGNORECASE)
    return s.strip('-') or "producto"

# Mapeo API salesScenario -> id modalidad en config
SCENARIO_TO_MODALITY = {
    "renew": "renovacion",
    "portIn": "portabilidad",
    "newConnection": "linea_nueva",
    "prepago": "prepago",
    "standard": "precio_normal",
}


def _offer_has_base_price(offer: Optional[dict]) -> bool:
    """True si el offer tiene priceType 'price' (precio base/tachado)."""
    if not offer:
        return False
    for rp in offer.get("relatedPrice", []) or []:
        pt = (rp.get("priceType") or "").lower()
        if "installment" in pt:
            continue
        if pt == "price":
            val = (rp.get("price") or {}).get("value")
            if val is not None and float(val) > 0:
                return True
    return False


def _extract_prices_from_scenario(offer: Optional[dict]) -> tuple[Optional[float], Optional[float]]:
    """
    Extrae (precio_descuento, precio_normal) usando priceType de la API.
    - salesPrice = precio principal (PLP)
    - price = precio normal (tachado)
    - initialPrice = oferta especial (no usar como principal)
    """
    if not offer:
        return None, None

    sales_price = None
    price_normal = None
    initial_price = None
    for rp in offer.get("relatedPrice", []) or []:
        pt = (rp.get("priceType") or "").lower()
        if "installment" in pt:
            continue
        val = (rp.get("price") or {}).get("value")
        if val is None or float(val) <= 0:
            continue
        val = float(val)
        if "salesprice" in pt or pt == "salesprice":
            sales_price = val
        elif pt == "price":
            price_normal = val
        elif "initialprice" in pt or pt == "initialprice":
            initial_price = val

    # Precio principal: salesPrice si existe, sino price (portIn/newConnection usan price)
    precio_descuento = sales_price or price_normal
    # Precio normal (tachado): price cuando es el mayor (base)
    precio_normal_val = price_normal or sales_price or initial_price
    if precio_descuento is None and initial_price is not None:
        precio_descuento = initial_price
    if precio_normal_val is None:
        precio_normal_val = precio_descuento
    return precio_descuento, precio_normal_val


def _parse_child(child: dict, modality_id: str, parent_item: Optional[dict] = None) -> Optional[dict]:
    """Parsea un child del JSON de la API y extrae datos para la modalidad."""
    try:
        gd = child.get("graphql_data") or {}
        inner = gd.get("graphql_data") or {}
        name = inner.get("name") or gd.get("name") or ""
        sku = child.get("child_sku") or inner.get("offerCode") or ""
        parent_sku = (
            child.get("parent_sku")
            or (parent_item or {}).get("parent_sku")
            or (parent_item or {}).get("sku")
            or sku
        )

        product_offering = inner.get("productOfferingPrice") or {}
        scenario_key = None
        for scenario, mod in SCENARIO_TO_MODALITY.items():
            if mod == modality_id:
                scenario_key = scenario
                break

        if modality_id == "prepago" and not product_offering.get("prepago"):
            scenario_key = "standard"

        # Para precio_normal: usar "renew" si tiene price (tachado), sino "standard"
        # En iPhone renew tiene price=999990; en Redmi renew solo tiene salesPrice (228000)
        # y no price tachado, por eso usamos standard que tiene el precio base correcto.
        if modality_id == "precio_normal":
            renew_offer = product_offering.get("renew")
            standard_offer = product_offering.get("standard")
            if renew_offer and _offer_has_base_price(renew_offer):
                scenario_key = "renew"
            elif standard_offer:
                scenario_key = "standard"
            else:
                scenario_key = "renew"

        offer = product_offering.get(scenario_key) if scenario_key else None
        precio_descuento, precio_normal = _extract_prices_from_scenario(offer)

        # Para precio_normal: la API tiene graphql_data.price = precio base (349990, 999990)
        # que es lo que muestra la web. Los escenarios pueden tener valores distintos.
        root_price = gd.get("price") or inner.get("price")
        if modality_id == "precio_normal" and root_price is not None:
            try:
                p = float(root_price)
                if p > 0:
                    price = p
                    precio_normal_web = p
                    precio_descuento_web = precio_descuento
                else:
                    price = precio_normal or precio_descuento
                    precio_normal_web = precio_normal
                    precio_descuento_web = precio_descuento
            except (TypeError, ValueError):
                price = precio_normal or precio_descuento
                precio_normal_web = precio_normal
                precio_descuento_web = precio_descuento
        elif modality_id == "precio_normal":
            price = precio_normal or precio_descuento
            precio_normal_web = precio_normal
            precio_descuento_web = precio_descuento
        else:
            price = precio_descuento or precio_normal
            precio_descuento_web = precio_descuento
            precio_normal_web = precio_normal

        if not name or (price is None or price <= 0):
            return None

        return {
            "sku": sku,
            "parent_sku": parent_sku,
            "name": name,
            "price": price,
            "precio_descuento": precio_descuento_web,
            "precio_normal": precio_normal_web,
            "precio_normal_sin_precio": False,
            "url": f"https://store.wom.cl/equipos/{parent_sku}/{_slugify_for_url(name)}",
            "modality": modality_id,
        }
    except Exception:
        return None


def _api_headers() -> Dict[str, str]:
    return {
        "accept": "*/*",
        "accept-language": "es-419,es;q=0.9",
        "origin": "https://store.wom.cl",
        "referer": "https://store.wom.cl/",
        "user-agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }


def _get_json_with_retries(
    url: str,
    *,
    connect_timeout: float,
    read_timeout: float,
    retries: int,
) -> Any:
    timeout_tuple = (connect_timeout, read_timeout)
    last_err: Optional[Exception] = None
    for attempt in range(max(1, retries)):
        try:
            resp = requests.get(url, headers=_api_headers(), timeout=timeout_tuple)
            resp.raise_for_status()
            return resp.json()
        except (
            requests.exceptions.ConnectTimeout,
            requests.exceptions.ConnectionError,
            requests.exceptions.ReadTimeout,
        ) as e:
            last_err = e
            if attempt + 1 < retries:
                time.sleep(min(2 ** attempt, 16))
            continue
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Error al llamar API WOM: {e}") from e
    raise RuntimeError(
        f"Error al llamar API WOM tras {retries} intentos: {last_err}. "
        "Comprueba firewall/VPN o prueba desde otra red (datos móviles)."
    ) from last_err


def fetch_products_from_api(
    skus: list[str],
    modalities: list[str],
    base_url: str = "https://store-srv.wom.cl/rest/V1/content",
    connect_timeout: float = 90.0,
    read_timeout: float = 180.0,
    batch_size: int = 10,
    retries: int = 5,
) -> pd.DataFrame:
    """
    Llama a getGraphqlDataFromSkus y devuelve DataFrame con productos por modalidad.
    Parte la lista de SKUs en lotes (menos carga por petición) y reintenta en timeout.

    skus: lista de parent_sku (ej. A3517-512GB, 25080RABDG)
    modalities: ids (renovacion, portabilidad, linea_nueva, prepago, precio_normal)
    """
    clean = [s.strip() for s in skus if s and str(s).strip()]
    if not clean:
        return pd.DataFrame(
            columns=[
                "sku", "name", "price", "precio_descuento", "precio_normal",
                "precio_normal_sin_precio", "url", "modality"
            ]
        )

    bs = max(1, int(batch_size))
    data: list = []
    for i in range(0, len(clean), bs):
        chunk = clean[i : i + bs]
        sku_str = ",".join(chunk)
        url = f"{base_url.rstrip('/')}/getGraphqlDataFromSkus?skus={sku_str}"
        part = _get_json_with_retries(
            url,
            connect_timeout=connect_timeout,
            read_timeout=read_timeout,
            retries=retries,
        )
        if isinstance(part, list):
            data.extend(part)
        else:
            raise RuntimeError("La API WOM no devolvió una lista JSON")

    if not isinstance(data, list):
        return pd.DataFrame(
            columns=[
                "sku", "name", "price", "precio_descuento", "precio_normal",
                "precio_normal_sin_precio", "url", "modality"
            ]
        )

    rows = []
    for item in data:
        childs = item.get("childs")
        if not childs and (item.get("graphql_data") or item.get("child_sku")):
            childs = [item]
        childs = childs or [item]
        for child in childs:
            for mod_id in modalities:
                parsed = _parse_child(child, mod_id, parent_item=item)
                if parsed:
                    rows.append(parsed)

    if not rows:
        return pd.DataFrame(
            columns=[
                "sku", "name", "price", "precio_descuento", "precio_normal",
                "precio_normal_sin_precio", "url", "modality"
            ]
        )

    return pd.DataFrame(rows)
