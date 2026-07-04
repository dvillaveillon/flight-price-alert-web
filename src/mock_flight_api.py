"""
mock_flight_api.py
------------------
Proveedor de vuelos SIMULADO. Es el proveedor por defecto del proyecto.

Permite ejecutar y demostrar todo el sistema (formulario, worker, notificaciones,
dashboards) SIN API keys reales y SIN costos.

Genera ofertas pseudo-aleatorias pero reproducibles: el precio depende de la ruta,
las fechas y una pequena variacion temporal, de modo que a veces cae por debajo del
umbral del usuario y dispara la alerta (util para la demo).
"""

from __future__ import annotations

import hashlib
import random
from datetime import datetime, timezone
from typing import Any

_AIRLINES = ["LATAM", "Sky Airline", "Iberia", "Avianca", "JetSMART", "Copa Airlines"]


def _seed_from_params(params: dict[str, Any]) -> int:
    """
    Crea una semilla estable a partir de la ruta+fecha, mezclada con la hora actual
    (redondeada a la hora) para que los precios varien entre corridas del cron pero
    sean coherentes dentro de una misma ejecucion.
    """
    hour_bucket = datetime.now(timezone.utc).strftime("%Y%m%d%H")
    raw = f"{params.get('origin')}-{params.get('destination')}-" \
          f"{params.get('departure_date')}-{hour_bucket}"
    digest = hashlib.md5(raw.encode()).hexdigest()
    return int(digest[:8], 16)


def search_flights(params: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Devuelve una lista de ofertas simuladas para la ruta pedida.

    Cada oferta tiene el mismo esquema que usan los proveedores reales:
      price, currency, airline, departure_time, return_time, stops,
      provider, booking_link
    """
    rng = random.Random(_seed_from_params(params))

    origin = params.get("origin", "SCL")
    destination = params.get("destination", "MAD")
    currency = params.get("currency", "USD")
    direct_only = params.get("direct_only", False)

    # Precio base sintetico influido por la "distancia" (diferencia de letras IATA).
    base = 250 + (abs(hash(origin) - hash(destination)) % 700)

    offers: list[dict[str, Any]] = []
    for _ in range(rng.randint(3, 6)):
        stops = 0 if direct_only else rng.choice([0, 0, 1, 2])
        # Vuelos directos suelen ser mas caros; con escalas, mas baratos.
        price = base + rng.randint(-120, 200) - (stops * 40)
        price = max(60, round(price, 2))

        offers.append({
            "price": price,
            "currency": currency,
            "airline": rng.choice(_AIRLINES),
            "departure_time": f"{params.get('departure_date')}T"
                              f"{rng.randint(6, 22):02d}:{rng.choice(['00', '30'])}:00",
            "return_time": (f"{params.get('return_date')}T"
                            f"{rng.randint(6, 22):02d}:00:00"
                            if params.get("return_date") else ""),
            "stops": stops,
            "provider": "mock",
            "booking_link": f"https://example.com/book?o={origin}&d={destination}",
        })

    # Ordenadas de mas barata a mas cara: la primera es la "mejor oferta".
    offers.sort(key=lambda o: o["price"])
    return offers
