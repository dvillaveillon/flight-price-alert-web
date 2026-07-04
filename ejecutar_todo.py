"""
ejecutar_todo.py
----------------
Script de conveniencia para la DEMO LOCAL.

Genera de una sola vez todo lo necesario para que los dashboards tengan contenido
al abrir la web, sin tener que llenar el formulario a mano:

  1. Siembra usuarios y alertas de ejemplo.
  2. Genera un historico de precios simulado (varios puntos en el tiempo) para que
     el grafico de "Price History" se vea con una curva real.
  3. Ejecuta una pasada real del worker (check_prices) para demostrar el flujo
     completo, incluidas las notificaciones en modo dry-run.

Uso:
    python ejecutar_todo.py

Luego abre el dashboard con:
    python -m streamlit run app_streamlit.py

Nota: en modo demo (CSV local) este script REINICIA los datos de ejemplo cada vez
que se ejecuta, para que la demo sea limpia y repetible. No toca Supabase.
"""

from __future__ import annotations

import os
import random
from datetime import date, datetime, timedelta, timezone

from src.database import DATA_DIR, SCHEMAS, Database
from src.mock_flight_api import search_flights
from src.utils import get_logger
import check_prices

logger = get_logger("ejecutar_todo")


# --------------------------------------------------------------------------- #
# Alertas de ejemplo (variadas para que la demo sea interesante)
# --------------------------------------------------------------------------- #
DEMO_USER = {
    "name": "Daniel (demo)",
    "email": "demo@flight-price-alert.dev",
    "whatsapp": "+56900000000",
}

DEMO_ALERTS = [
    # max_price alto -> muy probable que dispare notificacion
    {"origin": "SCL", "destination": "MAD", "max_price": 1500.0, "currency": "USD",
     "direct_only": False, "cabin": "economy"},
    # max_price medio -> depende del mock
    {"origin": "SCL", "destination": "LIM", "max_price": 300.0, "currency": "USD",
     "direct_only": False, "cabin": "economy"},
    # max_price bajo -> probablemente NO dispara (sirve para ver el otro caso)
    {"origin": "SCL", "destination": "JFK", "max_price": 200.0, "currency": "USD",
     "direct_only": True, "cabin": "business"},
]


def _reset_csv_demo() -> None:
    """Borra los CSV de demo para una corrida limpia (solo backend CSV)."""
    os.makedirs(DATA_DIR, exist_ok=True)
    for table in SCHEMAS:
        path = os.path.join(DATA_DIR, f"{table}.csv")
        if os.path.exists(path):
            os.remove(path)
    logger.info("Datos de demo (CSV) reiniciados.")


def _seed_price_history(db: Database, alert_id: str, alert_params: dict,
                        n_points: int = 8) -> None:
    """
    Inserta n puntos de precio con fechas hacia atras (cada 6 h) y una leve
    tendencia a la baja + ruido, para que el grafico tenga forma de serie de tiempo.
    """
    now = datetime.now(timezone.utc)
    # Precio base tomado del proveedor mock (mejor oferta de referencia).
    base_offers = search_flights(alert_params)
    base = base_offers[0]["price"] if base_offers else 600.0

    for i in range(n_points):
        # De mas antiguo (i=0) a mas reciente (i=n-1).
        ts = (now - timedelta(hours=6 * (n_points - 1 - i))).isoformat()
        # Tendencia a la baja suave + ruido aleatorio.
        trend = base * (1.15 - 0.05 * i)
        price = max(60.0, round(trend + random.uniform(-40, 40), 2))
        offer = {
            "price": price,
            "currency": alert_params.get("currency", "USD"),
            "airline": random.choice(["LATAM", "Iberia", "Avianca", "Sky Airline"]),
            "departure_time": "",
            "return_time": "",
            "stops": random.choice([0, 1]),
            "provider": "mock",
            "booking_link": "https://example.com/book",
        }
        db.insert_price(alert_id, offer, checked_at=ts)


def main() -> None:
    logger.info("=== EJECUTAR TODO: preparando demo local ===")
    db = Database()
    logger.info("Backend activo: %s", db.backend)

    # 1) Reset limpio solo si estamos en modo CSV (nunca borra Supabase).
    if db.backend == "csv":
        _reset_csv_demo()
        db = Database()  # recrea CSVs vacios

    # 2) Usuario de demo.
    user_id = db.upsert_user(
        DEMO_USER["name"], DEMO_USER["email"], DEMO_USER["whatsapp"], True
    )
    logger.info("Usuario de demo creado.")

    # 3) Alertas + historico de precios sembrado.
    today = date.today()
    for spec in DEMO_ALERTS:
        alert_id = db.insert_alert(user_id, {
            "origin": spec["origin"],
            "destination": spec["destination"],
            "departure_date": today + timedelta(days=30),
            "return_date": today + timedelta(days=37),
            "passengers": 1,
            "max_price": spec["max_price"],
            "currency": spec["currency"],
            "direct_only": spec["direct_only"],
            "accepts_connections": True,
            "flexible_days": 3,
            "cabin": spec["cabin"],
            "baggage_required": False,
        })
        _seed_price_history(db, alert_id, {
            "origin": spec["origin"],
            "destination": spec["destination"],
            "departure_date": today + timedelta(days=30),
            "return_date": today + timedelta(days=37),
            "currency": spec["currency"],
            "direct_only": spec["direct_only"],
        })
        logger.info("Alerta de demo %s -> %s lista (historico sembrado).",
                    spec["origin"], spec["destination"])

    # 4) Pasada real del worker (demuestra busqueda + reglas + notificacion).
    logger.info("Ejecutando una pasada real del worker (check_prices)...")
    check_prices.main()

    logger.info("=== DEMO LISTA ===")
    print("\n" + "=" * 60)
    print(" Datos de demo generados correctamente.")
    print(" Ahora abre el dashboard con:")
    print("     python -m streamlit run app_streamlit.py")
    print(" y revisa en la barra lateral: Admin Dashboard y Price History.")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
