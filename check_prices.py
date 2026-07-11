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

from datetime import datetime, timezone

from src.alert_rules import build_message, evaluate
from src.branding import (
    BRAND_NAME, build_email_html, build_whatsapp_message,
    get_destination_image_url, get_logo_url,
)
from src.chart_generator import generate_price_chart_png
from src.database import Database
from src.flight_api import get_best_offer
from src.notifier_email import send_email
from src.notifier_whatsapp import hours_since_last_join, send_whatsapp
from src.utils import get_logger, mask_contact

logger = get_logger("check_prices")

# Ventana en la que se manda el recordatorio de reconexion de WhatsApp: se
# calcula sobre las horas transcurridas desde el ultimo mensaje que el
# usuario le mando al sandbox de Twilio (su "join"). El sandbox corta la
# posibilidad de mandarle mensajes 24h despues de eso, asi que el
# recordatorio se manda ANTES de esa hora, mientras todavia se le puede
# escribir. El ancho de la ventana (6h) coincide con la frecuencia del cron,
# para garantizar que alguna corrida siempre caiga dentro.
REMINDER_WINDOW_MIN_HOURS = 18
REMINDER_WINDOW_MAX_HOURS = 24
REMINDER_DEDUPE_HOURS = 20  # no reenviar si ya se mando uno hace menos de esto


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


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

    # 5.1) Grafico de historico de precios propio de esta alerta (si se puede
    # generar y subir). Nunca frena el envio si algo falla aca.
    chart_url = None
    try:
        history = db.get_price_history(alert_id)
        png_bytes = generate_price_chart_png(alert, history)
        if png_bytes:
            chart_url = db.upload_chart(alert_id, png_bytes)
    except Exception as exc:
        logger.warning("No se pudo generar/subir el grafico de la alerta %s: %s", alert_id, exc)

    notified_any = False

    # 5a) Email (canal confiable).
    email = user.get("email")
    if email:
        html_body = build_email_html(alert, best, chart_url=chart_url)
        ok, detail = send_email(email, subject, message, html_body=html_body)
        db.insert_notification(
            alert_id, "email", message,
            "sent" if ok else "failed", decision.price,
        )
        notified_any = notified_any or ok

    # 5b) WhatsApp (opcional; requiere join al sandbox de Twilio). Se manda
    # el grafico de esta alerta como adjunto; si no hay grafico disponible,
    # cae a una imagen referencial del destino; si tampoco hay, al logo.
    whatsapp = user.get("whatsapp")
    if whatsapp:
        whatsapp_text = build_whatsapp_message(alert, best)
        media_url = (
            chart_url
            or get_destination_image_url(alert.get("destination"))
            or get_logo_url()
        )
        ok, detail = send_whatsapp(whatsapp, whatsapp_text, media_url=media_url)
        db.insert_notification(
            alert_id, "whatsapp", whatsapp_text,
            "sent" if ok else "failed", decision.price,
        )
        notified_any = notified_any or ok

    # 6) Si algun canal funciono, actualizamos last_notified_at (anti-spam).
    if notified_any:
        db.touch_alert_notified(alert_id)
        logger.info("Alerta %s notificada correctamente.", alert_id)


def send_whatsapp_keepalive_reminders(db: Database) -> None:
    """
    A los usuarios con alertas activas y WhatsApp configurado, cuya ventana
    de 24h con el sandbox de Twilio esta por cerrarse, se les manda un
    recordatorio amistoso para que reenvien "join these-garden" y no se les
    corten las alertas. Se manda mientras la ventana sigue abierta (por eso
    llega a tiempo). Cualquier fallo aca no debe frenar el resto del cron.
    """
    alerts = db.get_active_alerts()
    users_by_id: dict[str, dict] = {}
    anchor_alert_by_user: dict[str, str] = {}
    for alert in alerts:
        user_id = alert.get("user_id")
        if user_id in users_by_id:
            continue
        user = _lookup_user_contact(db, user_id)
        if user.get("whatsapp"):
            users_by_id[user_id] = user
            anchor_alert_by_user[user_id] = alert.get("alert_id")

    for user_id, user in users_by_id.items():
        whatsapp = user["whatsapp"]
        try:
            hours = hours_since_last_join(whatsapp)
        except Exception as exc:
            logger.warning("Error consultando el ultimo join de %s: %s", mask_contact(whatsapp), exc)
            continue

        if hours is None or not (REMINDER_WINDOW_MIN_HOURS <= hours < REMINDER_WINDOW_MAX_HOURS):
            continue

        anchor_alert_id = anchor_alert_by_user[user_id]
        recent = (
            db._client.table("notifications").select("sent_at")
            .eq("alert_id", anchor_alert_id).eq("channel", "whatsapp_reminder")
            .order("sent_at", desc=True).limit(1).execute().data
        )
        if recent:
            last_reminder = _parse_dt(recent[0]["sent_at"])
            if last_reminder and (datetime.now(timezone.utc) - last_reminder).total_seconds() / 3600 < REMINDER_DEDUPE_HOURS:
                continue  # ya se le recordo hace poco, no insistir

        text = (
            f"🐭💬 Hola {(user.get('name') or '').strip() or 'de nuevo'}! Soy SomosRata.\n\n"
            "Tu conexión para seguir recibiendo alertas de viajes está por vencer.\n\n"
            "Si quieres seguir recibiendo tus alertas, envíanos el siguiente texto "
            "a este WhatsApp:\n\n"
            "join these-garden\n\n"
            "Este paso es necesario porque estamos en modo prueba y WhatsApp pide "
            "reactivar la conexión cada 24 horas.\n\n"
            "Gracias por usar SomosRata."
        )
        ok, detail = send_whatsapp(whatsapp, text)
        db.insert_notification(anchor_alert_id, "whatsapp_reminder", text,
                               "sent" if ok else "failed", None)
        logger.info("Recordatorio de reconexion WhatsApp a %s: ok=%s detail=%s",
                    mask_contact(whatsapp), ok, detail)


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

    try:
        send_whatsapp_keepalive_reminders(db)
    except Exception as exc:  # un fallo aca no debe invalidar la corrida
        logger.error("Fallo enviando recordatorios de reconexion WhatsApp: %s", exc)

    logger.info("=== Fin de revision de precios ===")


if __name__ == "__main__":
    main()
