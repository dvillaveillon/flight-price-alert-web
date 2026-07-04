"""
notifier_whatsapp.py
--------------------
Envio de alertas por WhatsApp via Twilio (Sandbox o numero productivo).

Comportamiento seguro (graceful degradation):
  - Si existen credenciales Twilio -> envia el mensaje real.
  - Si NO existen                   -> modo "dry-run": registra en consola.

IMPORTANTE (limitacion del Sandbox de Twilio):
Para RECIBIR mensajes en el Sandbox, cada numero destino debe primero enviar el
codigo de "join" al numero del sandbox. Es una restriccion de Twilio, no del codigo.
Por eso, para demos, el canal confiable es el email; WhatsApp funciona una vez que
el destinatario se une al sandbox.

Requiere (solo en modo real):
    TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_FROM (ej. 'whatsapp:+14155238886')
"""

from __future__ import annotations

from src.utils import get_logger, get_secret

logger = get_logger(__name__)


def send_whatsapp(to_number: str, body: str) -> tuple[bool, str]:
    """
    Envia un mensaje de WhatsApp. Devuelve (exito, detalle).

    En modo dry-run (sin credenciales) devuelve (True, "dry-run").
    """
    sid = get_secret("TWILIO_ACCOUNT_SID")
    token = get_secret("TWILIO_AUTH_TOKEN")
    from_number = get_secret("TWILIO_WHATSAPP_FROM")

    if not to_number:
        return False, "sin_numero_destino"

    if not (sid and token and from_number):
        logger.info("[WHATSAPP dry-run] Para: %s", to_number)
        logger.info("[WHATSAPP dry-run] Cuerpo:\n%s", body)
        return True, "dry-run"

    try:
        from twilio.rest import Client  # import perezoso

        # Normalizamos al formato que exige Twilio: 'whatsapp:+<numero>'
        dest = to_number if to_number.startswith("whatsapp:") else f"whatsapp:{to_number}"

        client = Client(sid, token)
        message = client.messages.create(from_=from_number, to=dest, body=body)
        logger.info("WhatsApp enviado a %s (sid=%s).", to_number, message.sid)
        return True, f"sid={message.sid}"
    except Exception as exc:
        logger.error("Error enviando WhatsApp a %s: %s", to_number, exc)
        return False, str(exc)
