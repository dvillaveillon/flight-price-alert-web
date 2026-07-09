"""
chart_generator.py
-------------------
Genera una imagen PNG con el historico de precios de una alerta, para
adjuntarla a la notificacion (email + WhatsApp) que recibe el usuario
dueno de la alerta.

Importante: price_history solo guarda UN precio por revision (el total
que devuelve el proveedor para el itinerario completo). Si la alerta es
ida y vuelta, ese precio ya es el total combinado -- no existen columnas
separadas de ida/vuelta en el modelo de datos, asi que este grafico NUNCA
dibuja dos series inventadas; dibuja la unica serie real y aclara en el
titulo que es el total del itinerario.
"""

from __future__ import annotations

import io
from typing import Any

import matplotlib

matplotlib.use("Agg")  # backend sin display: requerido para correr en GitHub Actions

import matplotlib.dates as mdates
import matplotlib.pyplot as plt

from src.branding import get_colors


def _is_round_trip(alert: dict[str, Any]) -> bool:
    return_date = alert.get("return_date")
    return isinstance(return_date, str) and return_date.strip() not in ("", "nan", "None")


def generate_price_chart_png(alert: dict[str, Any],
                             price_points: list[dict[str, Any]]) -> bytes | None:
    """
    Dibuja el historico de precios de una alerta y devuelve los bytes PNG.

    Devuelve None si no hay suficientes datos para graficar (nunca lanza
    excepcion: la notificacion debe seguir su curso sin grafico si algo falla).
    """
    import pandas as pd

    if not price_points:
        return None

    df = pd.DataFrame(price_points)
    if "checked_at" not in df.columns or "price" not in df.columns:
        return None

    df["checked_at"] = pd.to_datetime(df["checked_at"], errors="coerce")
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    df = df.dropna(subset=["checked_at", "price"]).sort_values("checked_at")
    if df.empty:
        return None

    colors = get_colors()
    round_trip = _is_round_trip(alert)

    fig, ax = plt.subplots(figsize=(7, 4), dpi=150)
    ax.plot(df["checked_at"], df["price"], marker="o", linewidth=2,
            color=colors["primary"], label="Precio observado")

    max_price = alert.get("max_price")
    try:
        max_price = float(max_price) if max_price not in (None, "") else None
    except (TypeError, ValueError):
        max_price = None
    if max_price is not None:
        ax.axhline(max_price, color=colors["accent"], linestyle="--",
                   linewidth=1.5, label="Precio objetivo")

    origin = alert.get("origin", "")
    destination = alert.get("destination", "")
    if round_trip:
        title = f"Precio TOTAL ida y vuelta: {origin} → {destination}"
        subtitle = ("Este valor corresponde al precio total del itinerario, "
                    "no a cada tramo por separado.")
    else:
        title = f"Precio del vuelo (solo ida): {origin} → {destination}"
        subtitle = ""

    if subtitle:
        fig.suptitle(title, fontsize=12, fontweight="bold", color=colors["secondary"], y=0.99)
        ax.set_title(subtitle, fontsize=8, color="#666666", pad=6)
    else:
        ax.set_title(title, fontsize=12, fontweight="bold", color=colors["secondary"])

    ax.set_ylabel(f"Precio ({alert.get('currency', 'USD')})")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d-%b"))
    fig.autofmt_xdate()
    ax.legend(loc="best", fontsize=8)
    ax.grid(True, alpha=0.3)
    fig.tight_layout(rect=(0, 0, 1, 0.94) if subtitle else (0, 0, 1, 1))

    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()
