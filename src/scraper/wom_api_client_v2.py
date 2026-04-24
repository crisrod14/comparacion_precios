"""
Cliente API v2 para store-srv.wom.cl usando getList en lugar de getGraphqlDataFromSkus.
Obtiene precios por modalidad de forma más confiable.
"""
import time
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import pandas as pd
import requests


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
    """Obtiene JSON con reintentos."""
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
        f"Error al llamar API WOM tras {retries} intentos: {last_err}"
    ) from last_err


def _build_getlist_url(sku: str, base_url: str = "https://store-srv.wom.cl/rest/V1/content") -> str:
    """Construye URL para getList con un SKU específico."""
    params = {
        "searchCriteria[filterGroups][0][filters][0][field]": "attribute_set_id",
        "searchCriteria[filterGroups][0][filters][0][value]": "11",
        "searchCriteria[filterGroups][1][filters][0][field]": "type_id",
        "searchCriteria[filterGroups][1][filters][0][value]": "configurable",
        "searchCriteria[filterGroups][2][filters][0][field]": "sku",
        "searchCriteria[filterGroups][2][filters][0][value]": sku,
        "searchCriteria[filterGroups][2][filters][0][condition_type]": "eq",
        "searchCriteria[pageSize]": "1",
        "searchCriteria[currentPage]": "1",
        "searchCriteria[sortOrders][0][direction]": "DESC",
        "searchCriteria[filterGroups][10][filters][0][field]": "status",
        "searchCriteria[filterGroups][10][filters][0][value]": "1,2",
        "searchCriteria[filterGroups][10][filters][0][condition_type]": "in",
    }
    return f"{base_url}/getList?{urlencode(params)}"


def fetch_products_from_api(
    skus: list[str],
    modalities: list[str],
    base_url: str = "https://store-srv.wom.cl/rest/V1/content",
    connect_timeout: float = 90.0,
    read_timeout: float = 180.0,
    batch_size: int = 1,
    retries: int = 5,
) -> pd.DataFrame:
    """
    Obtiene precios desde getList para cada SKU.
    Devuelve DataFrame con precios por modalidad.
    """
    clean = [s.strip() for s in skus if s and str(s).strip()]
    if not clean:
        return pd.DataFrame(
            columns=["sku", "name", "price", "modality", "url"]
        )

    rows = []

    for sku in clean:
        try:
            url = _build_getlist_url(sku, base_url)
            data = _get_json_with_retries(
                url,
                connect_timeout=connect_timeout,
                read_timeout=read_timeout,
                retries=retries,
            )

            if isinstance(data, dict) and "items" in data and data["items"]:
                item = data["items"][0]

                # Obtener información básica
                name = item.get("name", "")
                parent_sku = item.get("sku", sku)
                url_key = item.get("url_key", "")

                # Obtener precios
                prices_array = item.get("prices_array", {})

                # Mapeo de modalidades
                modality_map = {
                    "renovacion": "renewal",
                    "portabilidad": "portability",
                    "linea_nueva": "newLine",
                    "prepago": "prepaid",
                    "precio_normal": "full_price",
                }

                for modality in modalities:
                    price_key = modality_map.get(modality)

                    if not price_key or not prices_array:
                        continue

                    # Obtener precio según modalidad
                    if price_key == "full_price":
                        price_val = prices_array.get("full_price")
                    else:
                        price_obj = prices_array.get(price_key, {})
                        price_val = price_obj.get("value") if isinstance(price_obj, dict) else price_obj

                    if price_val and float(price_val) > 0:
                        rows.append({
                            "sku": parent_sku,
                            "name": name,
                            "price": float(price_val),
                            "modality": modality,
                            "url": f"https://store.wom.cl/equipos/{parent_sku}/{url_key}" if url_key else "",
                        })

                # También procesar child SKUs si existen
                childs = item.get("child", [])
                for child in childs:
                    child_sku = child.get("sku")
                    if child_sku and child_sku != parent_sku:
                        # Los child SKUs heredan los precios del parent
                        for modality in modalities:
                            price_key = modality_map.get(modality)
                            if not price_key or not prices_array:
                                continue

                            if price_key == "full_price":
                                price_val = prices_array.get("full_price")
                            else:
                                price_obj = prices_array.get(price_key, {})
                                price_val = price_obj.get("value") if isinstance(price_obj, dict) else price_obj

                            if price_val and float(price_val) > 0:
                                rows.append({
                                    "sku": child_sku,
                                    "name": name,
                                    "price": float(price_val),
                                    "modality": modality,
                                    "url": f"https://store.wom.cl/equipos/{parent_sku}/{url_key}" if url_key else "",
                                })

        except Exception as e:
            print(f"Error procesando SKU {sku}: {e}")
            continue

    if not rows:
        return pd.DataFrame(
            columns=["sku", "name", "price", "modality", "url"]
        )

    return pd.DataFrame(rows)
