"""
branding.py
-----------
Configuracion e identidad visual de marca (Somos-Rata). Centraliza nombre,
eslogan, colores y logo para que la web, el email y el WhatsApp usen siempre
los mismos valores, y para construir el contenido (HTML de email, texto de
WhatsApp) que lleva esa marca.

Los colores tienen defaults de marca; se pueden sobreescribir con las
variables BRAND_PRIMARY_COLOR, BRAND_SECONDARY_COLOR, BRAND_ACCENT_COLOR y
BRAND_YELLOW. El logo requiere una URL publica (BRAND_LOGO_URL) para usarse
en email/WhatsApp; en Streamlit tambien se puede mostrar desde el archivo
local assets/somos_rata_logo.png.
"""

from __future__ import annotations

import os
from typing import Any
from urllib.parse import quote

from src.utils import get_secret

BRAND_NAME = "Somos-Rata"
BRAND_SLOGAN = "Dinos tu precio. Nosotros te avisamos."

_LOGO_LOCAL_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "assets", "somos_rata_logo.png"
)


def get_logo_url() -> str | None:
    """URL publica del logo (para email/WhatsApp). None si no esta configurada."""
    return get_secret("BRAND_LOGO_URL") or None


def get_logo_local_path() -> str | None:
    """Ruta local del logo (para Streamlit). None si el archivo no existe todavia."""
    return _LOGO_LOCAL_PATH if os.path.exists(_LOGO_LOCAL_PATH) else None


def get_colors() -> dict[str, str]:
    """Colores de marca, con defaults de Somos-Rata si no hay overrides por entorno."""
    return {
        "primary": get_secret("BRAND_PRIMARY_COLOR", "#16B8B8"),
        "secondary": get_secret("BRAND_SECONDARY_COLOR", "#0B1F3A"),
        "accent": get_secret("BRAND_ACCENT_COLOR", "#FF6B5F"),
        "yellow": get_secret("BRAND_YELLOW", "#FFC84D"),
    }


# Codigos de aeropuerto puntuales que se agrupan bajo el codigo de ciudad para
# elegir imagen (ej. si el usuario escribio el aeropuerto exacto en vez del
# codigo de ciudad). Solo afecta la eleccion de imagen, no la busqueda de vuelos.
_AIRPORT_TO_CITY_IMAGE = {
    "JFK": "NYC", "EWR": "NYC", "LGA": "NYC",
    "CDG": "PAR", "ORY": "PAR",
    "LHR": "LON", "LGW": "LON", "LTN": "LON",
}

# Imagen referencial por destino (codigo de ciudad IATA). URLs de Wikimedia
# Commons via Special:FilePath: ese endpoint redirige siempre al archivo
# vigente (no se rompe si el archivo se renombra o se mueve de resolucion).
# Lista corta a proposito: se agrega un destino nuevo solo cuando hace falta.
_DESTINATION_IMAGES = {
    "PUJ": "Punta Cana, Dominican Republic (Resort).jpg",
    "CUN": "Cancun Beach.jpg",
    "MAD": "Gran Vía - 01.jpg",
    "PAR": "Paris - The Eiffel Tower in spring - 2307.jpg",
    "NYC": "Long Island City New York May 2015 panorama 3.jpg",
    "LON": "Big Ben at sunset - 2014-10-27 17-30.jpg",
    "BCN": "Sagrada Familia March 2015-19bw.jpg",
    "BUE": "Parte superior del Obelisco de Buenos Aires.jpg",
    "ROM": "Colosseum in Rome-April 2007-1- copie 2B.jpg",
    "MIA": "Miami skyline from the ocean.jpg",
}


def get_destination_image_url(destination: str | None) -> str | None:
    """
    Imagen referencial del destino, para el "card" de la alerta. None si no
    hay una imagen curada para ese destino (el llamador debe caer a otro
    fallback, ej. el logo de marca). Nunca lanza excepcion.
    """
    if not destination:
        return None
    code = destination.strip().upper()
    code = _AIRPORT_TO_CITY_IMAGE.get(code, code)
    filename = _DESTINATION_IMAGES.get(code)
    if not filename:
        return None
    return f"https://commons.wikimedia.org/wiki/Special:FilePath/{quote(filename)}?width=800"


def build_whatsapp_message(alert: dict[str, Any], offer: dict[str, Any]) -> str:
    """
    Texto de marca para la notificacion de WhatsApp. Formato simple original:
    el link de vuelo ya trae la fecha de vuelta correcta cuando aplica (ver
    _reference_link en flight_api.py), aunque el texto no la repita aparte.
    """
    origen = alert.get("origin")
    destino = alert.get("destination")
    moneda = offer.get("currency", alert.get("currency", "USD"))
    precio_encontrado = offer.get("price")
    precio_objetivo = alert.get("max_price")
    link = offer.get("booking_link", "")

    text = (
        f"🐭✈️ {BRAND_NAME} encontro un vuelo para ti\n\n"
        "Encontramos un precio que calza con tu alerta.\n\n"
        f"Origen: {origen}\n"
        f"Destino: {destino}\n"
        f"Precio encontrado: {precio_encontrado} {moneda}\n"
        f"Tu precio objetivo: {precio_objetivo} {moneda}\n\n"
        f"{BRAND_SLOGAN}"
    )
    if link:
        text += f"\n\nRevisa tu vuelo aqui:\n{link}"
    return text


def build_email_html(alert: dict[str, Any], offer: dict[str, Any],
                     chart_url: str | None = None) -> str:
    """
    Email HTML con branding de Somos-Rata. Usa tablas y estilos inline (sin CSS
    externo ni flex/grid) para verse bien tanto en Gmail como en Outlook.

    chart_url es opcional: si se pasa, se agrega el grafico de historico de
    precios de la alerta (propio del usuario) debajo del boton "Ver vuelo".
    """
    colors = get_colors()
    logo_url = get_logo_url()

    origen = alert.get("origin")
    destino = alert.get("destination")
    moneda = offer.get("currency", alert.get("currency", "USD"))
    precio_encontrado = offer.get("price")
    precio_objetivo = alert.get("max_price")
    aerolinea = offer.get("airline") or ""
    salida = alert.get("departure_date")
    vuelta = alert.get("return_date")
    link = offer.get("booking_link", "")

    # Si hay logo, se muestra solo por si solo (ya incluye nombre y eslogan
    # dentro de la imagen); si no esta configurado, se usa texto de respaldo.
    if logo_url:
        header_html = (
            f'<img src="{logo_url}" alt="{BRAND_NAME}" width="220" '
            'style="display:block;margin:0 auto;border:0;" />'
        )
    else:
        header_html = (
            f'<div style="color:#ffffff;font-size:22px;font-weight:800;">{BRAND_NAME}</div>'
            f'<div style="color:{colors["yellow"]};font-size:13px;font-weight:600;margin-top:4px;">'
            f'{BRAND_SLOGAN}</div>'
        )

    rows = [("Origen", origen), ("Destino", destino), ("Fecha de ida", salida)]
    if vuelta:
        rows.append(("Fecha de vuelta", vuelta))
    rows.append(("Precio encontrado", f"{precio_encontrado} {moneda}"))
    rows.append(("Tu precio objetivo", f"{precio_objetivo} {moneda}"))
    if aerolinea:
        rows.append(("Aerolinea", aerolinea))

    rows_html = "".join(
        '<tr>'
        f'<td style="padding:6px 12px;color:#555555;font-size:14px;">{label}</td>'
        f'<td style="padding:6px 12px;color:{colors["secondary"]};font-size:14px;'
        f'font-weight:600;text-align:right;">{value}</td>'
        '</tr>'
        for label, value in rows
    )

    button_html = (
        '<tr><td align="center" style="padding:20px 0;">'
        f'<a href="{link}" target="_blank" '
        f'style="background-color:{colors["primary"]};color:#ffffff;text-decoration:none;'
        'padding:12px 28px;border-radius:6px;font-weight:600;font-size:15px;'
        'display:inline-block;">Ver vuelo</a></td></tr>'
        if link else ""
    )

    chart_html = ""
    if chart_url:
        chart_note = (
            '<p style="font-size:11px;color:#888888;margin:8px 0 0 0;text-align:center;">'
            'Precio total del itinerario ida y vuelta (no por tramo separado).</p>'
            if vuelta else ""
        )
        chart_html = (
            '<tr><td style="padding:0 24px 20px 24px;text-align:center;">'
            f'<img src="{chart_url}" alt="Historico de precio" width="480" '
            'style="max-width:100%;display:block;margin:0 auto;border-radius:6px;border:1px solid #E5E9F0;" />'
            f'{chart_note}</td></tr>'
        )
    else:
        # Sin grafico disponible (alerta nueva o fallo puntual de subida):
        # mostramos una imagen referencial del destino en su lugar, si hay una
        # curada para este destino. Si no hay, se omite (sin romper el email).
        dest_image = get_destination_image_url(destino)
        if dest_image:
            chart_html = (
                '<tr><td style="padding:0 24px 20px 24px;text-align:center;">'
                f'<img src="{dest_image}" alt="{destino}" width="480" '
                'style="max-width:100%;display:block;margin:0 auto;border-radius:6px;" />'
                '</td></tr>'
            )

    return f"""\
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"
       style="background-color:#F1F5F9;padding:24px 0;font-family:Arial,Helvetica,sans-serif;">
  <tr>
    <td align="center">
      <table role="presentation" width="480" cellpadding="0" cellspacing="0"
             style="background-color:#ffffff;border-radius:10px;overflow:hidden;">
        <tr>
          <td style="background-color:{colors['secondary']};padding:24px;text-align:center;">
            {header_html}
          </td>
        </tr>
        <tr>
          <td style="padding:24px;">
            <p style="font-size:16px;color:#222222;margin:0 0 16px 0;">
              Encontramos un vuelo <b>igual o menor</b> a tu precio objetivo para tu ruta
              <b>{origen} &rarr; {destino}</b>.
            </p>
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
                   style="border:1px solid #E5E9F0;border-radius:8px;">
              {rows_html}
            </table>
          </td>
        </tr>
        {button_html}
        {chart_html}
        <tr>
          <td style="padding:16px 24px;background-color:#F8FAFC;border-top:1px solid #E5E9F0;">
            <p style="font-size:12px;color:#888888;margin:0;text-align:center;">
              Recibiste este aviso porque creaste una alerta en {BRAND_NAME}.
            </p>
          </td>
        </tr>
      </table>
    </td>
  </tr>
</table>
"""
