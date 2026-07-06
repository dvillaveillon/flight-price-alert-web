"""
check_prices.py
---------------
Worker asincrono. Es el corazon de la automatizacion.

Lo ejecuta un scheduler (GitHub Actions cada 6 h, o Render Cron Job) de forma
INDEPENDIENTE de la web. Sus pasos:

  1. Lee todas las alertas activas.
  2. Para cada alerta, consulta el proveedor de vuelos (mock/amadeus/duffel).
  3. Guarda la mejor oferta en price_history.
  4. Evalua las reglas (umbral de precio + anti-spam).
  5. Si corresponde, notifica por email y/o WhatsApp y registra la notificacion.
  6. Actualiza last_checked_at (siempre) y last_notified_at (si notifico).

Se puede ejecutar directamente:  python check_prices.py
"""

from __future__ import annotations

from src.alert_rules import build_message, evaluate
from src.branding import BRAND_NAME, build_email_html, build_whatsapp_message, get_logo_url
from src.database import Database
from src.flight_api import get_best_offer
from src.notifier_email import send_email
from src.notifier_whatsapp import send_whatsapp
from src.utils import get_logger

logger = get_logger("check_prices")


def _alert_to_params(alert: dict) -> dict:
    """Traduce una fila de alerts a los parametros que espera el buscador."""
    return {
        "origin": alert.get("origin"),
        "destination": alert.get("destination"),
        "departure_date": alert.get("departure_date"),
        "return_date": alert.get("return_date") or None,
        "passengers": int(float(alert.get("passengers", 1) or 1)),
        "currency": alert.get("currency", "USD"),
        "direct_only": str(alert.get("direct_only")).lower() in ("true", "1", "yes"),
        "cabin": alert.get("cabin", "economy"),
    }


def _lookup_user_contact(db: Database, user_id: str) -> dict:
    """Recupera nombre/email/whatsapp del usuario dueno de la alerta."""
    if db.backend == "supabase":
        res = db._client.table("users").select("*").eq("user_id", user_id).limit(1).execute()
        return (res.data or [{}])[0]
    import pandas as pd  # local

    df = db._csv_read("users")
    if df.empty:
        return {}
    match = df[df["user_id"] == user_id]
    return match.iloc[0].to_dict() if not match.empty else {}


def process_alert(db: Database, alert: dict) -> None:
    """Procesa una unica alerta de principio a fin."""
    alert_id = alert.get("alert_id")
    logger.info("Procesando alerta %s (%s -> %s).",
                alert_id, alert.get("origin"), alert.get("destination"))

    # 1) Consultar proveedor y obtener la mejor oferta.
    params = _alert_to_params(alert)
    best = get_best_offer(params)

    # 2) Registrar en el historico (aunque no dispare notificacion).
    if best:
        db.insert_price(alert_id, best)

    # 3) Marcar la alerta como revisada.
    db.touch_alert_checked(alert_id)

    # 4) Evaluar reglas (umbral + anti-spam).
    decision = evaluate(alert, best)
    logger.info("Decision alerta %s: %s (precio=%s).",
                alert_id, decision.reason, decision.price)

    if not decision.should_notify:
        return

    # 5) Notificar. Recuperamos contacto del usuario.
    user = _lookup_user_contact(db, alert.get("user_id"))
    message = build_message(alert, best)
    subject = f"{BRAND_NAME}: oportunidad de vuelo {alert.get('origin')} -> {alert.get('destination')}"

    notified_any = False

    # 5a) Email (canal confiable).
    email = user.get("email")
    if email:
        html_body = build_email_html(alert, best)
        ok, detail = send_email(email, subject, message, html_body=html_body)
        db.insert_notification(
            alert_id, "email", message,
            "sent" if ok else "failed", decision.price,
        )
        notified_any = notified_any or ok

    # 5b) WhatsApp (opcional; requiere join al sandbox de Twilio).
    whatsapp = user.get("whatsapp")
    if whatsapp:
        whatsapp_text = build_whatsapp_message(alert, best)
        ok, detail = send_whatsapp(whatsapp, whatsapp_text, media_url=get_logo_url())
        db.insert_notification(
            alert_id, "whatsapp", whatsapp_text,
            "sent" if ok else "failed", decision.price,
        )
        notified_any = notified_any or ok

    # 6) Si algun canal funciono, actualizamos last_notified_at (anti-spam).
    if notified_any:
        db.touch_alert_notified(alert_id)
        logger.info("Alerta %s notificada correctamente.", alert_id)


def main() -> None:
    """Punto de entrada del worker."""
    logger.info("=== Inicio de revision de precios ===")
    db = Database()
    logger.info("Backend activo: %s", db.backend)

    alerts = db.get_active_alerts()
    logger.info("Alertas activas encontradas: %d", len(alerts))

    for alert in alerts:
        try:
            process_alert(db, alert)
        except Exception as exc:  # una alerta fallida no debe frenar el resto
            logger.error("Fallo procesando alerta %s: %s",
                         alert.get("alert_id"), exc)

    logger.info("=== Fin de revision de precios ===")


if __name__ == "__main__":
    main()
