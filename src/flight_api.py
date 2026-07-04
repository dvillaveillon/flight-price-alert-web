"""
flight_api.py
-------------
Punto de entrada UNICO para buscar vuelos, con arquitectura flexible (patron Strategy).

Una sola variable de entorno decide el proveedor:
    FLIGHT_PROVIDER = mock (default) | amadeus | duffel

El resto del sistema llama SIEMPRE a `search_flights(params)` sin saber ni importarle
cual proveedor esta activo. Cambiar de mock a real es cambiar una variable, nada mas.

Contrato comun de una oferta (dict):
    price (float), currency (str), airline (str), departure_time (str ISO),
    return_time (str ISO | ""), stops (int), provider (str), booking_link (str)
"""

from __future__ import annotations

from typing import Any

from src.utils import get_flight_provider, get_logger, get_secret
from src import mock_flight_api

logger = get_logger(__name__)


# --------------------------------------------------------------------------- #
# Proveedor: AMADEUS (Flight Offers Search)
# --------------------------------------------------------------------------- #
def _search_amadeus(params: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Implementacion preparada para Amadeus Flight Offers Search.

    Requiere:
        AMADEUS_CLIENT_ID, AMADEUS_CLIENT_SECRET
    Docs: https://developers.amadeus.com/

    Se deja el esqueleto listo. Para activarlo:
      1) Instala el SDK:  pip install amadeus
      2) Define las credenciales como variables de entorno / secrets.
      3) FLIGHT_PROVIDER=amadeus
    """
    client_id = get_secret("AMADEUS_CLIENT_ID")
    client_secret = get_secret("AMADEUS_CLIENT_SECRET")
    if not client_id or not client_secret:
        logger.warning("Faltan credenciales Amadeus. Cayendo a mock.")
        return mock_flight_api.search_flights(params)

    try:
        from amadeus import Client  # import perezoso

        amadeus = Client(client_id=client_id, client_secret=client_secret)
        response = amadeus.shopping.flight_offers_search.get(
            originLocationCode=params["origin"],
            destinationLocationCode=params["destination"],
            departureDate=str(params["departure_date"]),
            returnDate=str(params["return_date"]) if params.get("return_date") else None,
            adults=int(params.get("passengers", 1)),
            currencyCode=params.get("currency", "USD"),
            nonStop="true" if params.get("direct_only") else "false",
            max=10,
        )
        return [_normalize_amadeus(o) for o in response.data]
    except Exception as exc:  # ante cualquier fallo real, no rompemos el worker
        logger.error("Error consultando Amadeus (%s). Cayendo a mock.", exc)
        return mock_flight_api.search_flights(params)


def _normalize_amadeus(offer: dict) -> dict[str, Any]:
    """Traduce una oferta cruda de Amadeus al contrato comun."""
    itineraries = offer.get("itineraries", [])
    outbound = itineraries[0]["segments"] if itineraries else []
    inbound = itineraries[1]["segments"] if len(itineraries) > 1 else []
    return {
        "price": float(offer["price"]["grandTotal"]),
        "currency": offer["price"].get("currency", "USD"),
        "airline": offer.get("validatingAirlineCodes", [""])[0],
        "departure_time": outbound[0]["departure"]["at"] if outbound else "",
        "return_time": inbound[0]["departure"]["at"] if inbound else "",
        "stops": max(len(outbound) - 1, 0),
        "provider": "amadeus",
        "booking_link": "",
    }


# --------------------------------------------------------------------------- #
# Proveedor: DUFFEL (Offers API)
# --------------------------------------------------------------------------- #
def _search_duffel(params: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Implementacion preparada para Duffel Offers API (via REST).

    Requiere:
        DUFFEL_ACCESS_TOKEN
    Docs: https://duffel.com/docs/api/offers

    Para activarlo:
      1) Define DUFFEL_ACCESS_TOKEN como secret.
      2) FLIGHT_PROVIDER=duffel
    """
    token = get_secret("DUFFEL_ACCESS_TOKEN")
    if not token:
        logger.warning("Falta DUFFEL_ACCESS_TOKEN. Cayendo a mock.")
        return mock_flight_api.search_flights(params)

    try:
        import requests  # import perezoso

        slices = [{
            "origin": params["origin"],
            "destination": params["destination"],
            "departure_date": str(params["departure_date"]),
        }]
        if params.get("return_date"):
            slices.append({
                "origin": params["destination"],
                "destination": params["origin"],
                "departure_date": str(params["return_date"]),
            })

        payload = {
            "data": {
                "slices": slices,
                "passengers": [{"type": "adult"}] * int(params.get("passengers", 1)),
                "cabin_class": params.get("cabin", "economy"),
            }
        }
        headers = {
            "Authorization": f"Bearer {token}",
            "Duffel-Version": "v2",
            "Content-Type": "application/json",
        }
        resp = requests.post(
            "https://api.duffel.com/air/offer_requests?return_offers=true",
            json=payload, headers=headers, timeout=30,
        )
        resp.raise_for_status()
        offers = resp.json().get("data", {}).get("offers", [])
        return [_normalize_duffel(o) for o in offers]
    except Exception as exc:
        logger.error("Error consultando Duffel (%s). Cayendo a mock.", exc)
        return mock_flight_api.search_flights(params)


def _normalize_duffel(offer: dict) -> dict[str, Any]:
    """Traduce una oferta cruda de Duffel al contrato comun."""
    slices = offer.get("slices", [])
    out_seg = slices[0]["segments"] if slices else []
    in_seg = slices[1]["segments"] if len(slices) > 1 else []
    return {
        "price": float(offer.get("total_amount", 0)),
        "currency": offer.get("total_currency", "USD"),
        "airline": (offer.get("owner") or {}).get("name", ""),
        "departure_time": out_seg[0]["departing_at"] if out_seg else "",
        "return_time": in_seg[0]["departing_at"] if in_seg else "",
        "stops": max(len(out_seg) - 1, 0),
        "provider": "duffel",
        "booking_link": "",
    }


# --------------------------------------------------------------------------- #
# Dispatcher (Strategy)
# --------------------------------------------------------------------------- #
_PROVIDERS = {
    "mock": mock_flight_api.search_flights,
    "amadeus": _search_amadeus,
    "duffel": _search_duffel,
}


def search_flights(params: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Busca vuelos usando el proveedor configurado en FLIGHT_PROVIDER.
    Devuelve una lista de ofertas ordenadas de mas barata a mas cara.
    """
    provider = get_flight_provider()
    fn = _PROVIDERS.get(provider, mock_flight_api.search_flights)
    logger.info("Buscando vuelos con proveedor='%s' (%s -> %s).",
                provider, params.get("origin"), params.get("destination"))
    offers = fn(params)
    offers.sort(key=lambda o: o.get("price", float("inf")))
    return offers


def get_best_offer(params: dict[str, Any]) -> dict[str, Any] | None:
    """Devuelve la oferta mas barata encontrada, o None si no hay resultados."""
    offers = search_flights(params)
    return offers[0] if offers else None
