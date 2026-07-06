"""
notifier_email.py
-----------------
Envio de alertas por email via SendGrid.

Comportamiento seguro (graceful degradation):
  - Si SENDGRID_API_KEY existe -> envia el correo real.
  - Si NO existe               -> modo "dry-run": registra en consola lo que
    se habria enviado, sin fallar. Esto permite correr la demo completa sin
    credenciales.

Requiere (solo en modo real):
    SENDGRID_API_KEY, SENDGRID_FROM_EMAIL
"""

from __future__ import annotations

from src.utils import get_logger, get_secret

logger = get_logger(__name__)


def send_email(to_email: str, subject: str, body: str,
               html_body: str | None = None) -> tuple[bool, str]:
    """
    Envia un email. Devuelve (exito, detalle).

    `html_body` es opcional: si se pasa, el correo se envia como multipart
    (texto plano + HTML). Si se omite, se manda solo el texto plano (igual
    que antes).

    En modo dry-run (sin API key) devuelve (True, "dry-run") para que el flujo
    de la demo continue y quede registrado en la tabla notifications.
    """
    api_key = get_secret("SENDGRID_API_KEY")
    from_email = get_secret("SENDGRID_FROM_EMAIL", "alertas@flight-price-alert.dev")

    if not api_key:
        logger.info("[EMAIL dry-run] Para: %s | Asunto: %s", to_email, subject)
        logger.info("[EMAIL dry-run] Cuerpo:\n%s", body)
        return True, "dry-run"

    try:
        from sendgrid import SendGridAPIClient  # import perezoso
        from sendgrid.helpers.mail import Mail

        mail_kwargs = dict(
            from_email=from_email,
            to_emails=to_email,
            subject=subject,
            plain_text_content=body,
        )
        if html_body:
            mail_kwargs["html_content"] = html_body
        message = Mail(**mail_kwargs)
        client = SendGridAPIClient(api_key)
        response = client.send(message)
        ok = 200 <= response.status_code < 300
        detail = f"status={response.status_code}"
        if ok:
            logger.info("Email enviado a %s (%s).", to_email, detail)
        else:
            logger.warning("SendGrid respondio %s para %s.", detail, to_email)
        return ok, detail
    except Exception as exc:
        logger.error("Error enviando email a %s: %s", to_email, exc)
        return False, str(exc)
