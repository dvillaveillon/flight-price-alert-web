"""
alert_rules.py
--------------
Reglas de negocio para decidir SI se debe notificar una alerta.

Dos condiciones deben cumplirse para enviar:
  1. UMBRAL DE PRECIO: la mejor oferta encontrada <= max_price del usuario.
  2. ANTI-SPAM (cooldown): no haber notificado esa misma alerta dentro de la
     ventana de enfriamiento (por defecto 24 h).

La logica esta centralizada aqui (no dispersa por el worker) para que sea
facil de testear y auditar.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from src.utils import get_cooldown_hours, get_logger

logger = get_logger(__name__)


@dataclass
class Decision:
    """Resultado de evaluar una alerta contra una oferta."""
    should_notify: bool
    reason: str
    price: float | None = None


def _parse_ts(value: str | None) -> datetime | None:
    """Parsea un timestamp ISO a datetime aware (UTC). Devuelve None si vacio."""
    if not value or str(value).strip() == "":
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


def evaluate(alert: dict[str, Any], best_offer: dict[str, Any] | None,
             cooldown_hours: int | None = None) -> Decision:
    """
    Evalua una alerta frente a la mejor oferta disponible.

    Parametros:
        alert         -> fila de la tabla alerts (dict).
        best_offer    -> mejor oferta encontrada (dict) o None.
        cooldown_hours-> ventana anti-spam; si None usa la config global.

    Devuelve un Decision con should_notify + motivo legible.
    """
    if cooldown_hours is None:
        cooldown_hours = get_cooldown_hours()

    # Sin ofertas no hay nada que notificar.
    if not best_offer:
        return Decision(False, "sin_ofertas")

    try:
        current_price = float(best_offer.get("price"))
        max_price = float(alert.get("max_price"))
    except (TypeError, ValueError):
        return Decision(False, "datos_precio_invalidos")

    # Condicion 0: el proveedor puede devolver una moneda distinta a la que
    # eligio el usuario (ej. el proveedor solo entrega EUR en su entorno de
    # test). Sin conversion de moneda, comparar numeros de monedas distintas
    # da falsos positivos/negativos, asi que si no coinciden NO se notifica.
    offer_currency = str(best_offer.get("currency") or "").strip().upper()
    alert_currency = str(alert.get("currency") or "").strip().upper()
    if offer_currency and alert_currency and offer_currency != alert_currency:
        return Decision(False, "moneda_no_coincide", price=current_price)

    # Condicion 1: el precio debe cumplir el umbral (<=).
    if current_price > max_price:
        return Decision(False, "precio_sobre_umbral", price=current_price)

    # Condicion 2: respetar la ventana anti-spam.
    last_notified = _parse_ts(alert.get("last_notified_at"))
    if last_notified is not None:
        elapsed = datetime.now(timezone.utc) - last_notified
        if elapsed < timedelta(hours=cooldown_hours):
            return Decision(False, "en_ventana_cooldown", price=current_price)

    # Ambas condiciones cumplidas: se debe notificar.
    return Decision(True, "precio_bajo_umbral", price=current_price)


def build_message(alert: dict[str, Any], offer: dict[str, Any]) -> str:
    """
    Construye el texto de la notificacion en tono institucional y claro.
    Se usa tanto para email como para WhatsApp.
    """
    ruta = f"{alert.get('origin')} -> {alert.get('destination')}"
    precio = offer.get("price")
    moneda = offer.get("currency", alert.get("currency", "USD"))
    aerolinea = offer.get("airline", "")
    escalas = offer.get("stops", 0)
    escalas_txt = "directo" if escalas == 0 else f"{escalas} escala(s)"
    link = offer.get("booking_link", "")

    return (
        f"Encontramos una oportunidad para tu ruta {ruta}.\n"
        f"Precio: {precio} {moneda} ({aerolinea}, {escalas_txt}).\n"
        f"Tu precio objetivo era {alert.get('max_price')} {moneda}.\n"
        f"Salida: {alert.get('departure_date')}"
        + (f" | Regreso: {alert.get('return_date')}" if alert.get("return_date") else "")
        + (f"\nEnlace de referencia: {link}" if link else "")
        + "\n\nEste es un aviso automatico. Verifica disponibilidad y condiciones "
          "antes de comprar."
    )
