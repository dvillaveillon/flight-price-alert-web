"""
01_Admin_Dashboard.py
---------------------
Dashboard ejecutivo (aparece automaticamente en la barra lateral de Streamlit).

Muestra una vista operativa del sistema:
  - KPIs: alertas totales, activas, notificaciones enviadas, precio promedio observado.
  - Tabla de alertas.
  - Tabla de notificaciones recientes.

Protegido por clave si se define la variable ADMIN_PASSWORD (ver bloque abajo).
Sin esa variable, el panel queda abierto (modo demo).
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.branding import BRAND_NAME, get_logo_local_path
from src.database import Database
from src.notifier_whatsapp import hours_since_last_join
from src.utils import get_secret

logo_path = get_logo_local_path()
st.set_page_config(page_title=f"{BRAND_NAME} · Admin", page_icon=logo_path or "🐭", layout="wide")

# --- Proteccion basica por clave (ADMIN_PASSWORD). Sin esta variable definida,
# el panel queda abierto (comportamiento de modo demo). ---
admin_pass = get_secret("ADMIN_PASSWORD")
if admin_pass:
    entered = st.text_input("Clave de acceso", type="password")
    if entered != admin_pass:
        st.stop()

st.caption(BRAND_NAME)
st.title("📊 Panel de administracion")
st.caption("Vista operativa de alertas, precios y notificaciones.")

db = Database()
alerts = pd.DataFrame(db.get_all_alerts())
users_df = pd.DataFrame(db.get_all_users())
notifications = pd.DataFrame(db.get_notifications())
prices = pd.DataFrame(db.get_price_history())

# Alertas con los datos de contacto de quien las creo, para identificar de un
# vistazo quien esta detras de cada fila (join por user_id).
if not alerts.empty and not users_df.empty and "user_id" in alerts.columns:
    contact_cols = users_df[["user_id", "name", "email", "whatsapp"]].rename(
        columns={"name": "Nombre", "email": "Email", "whatsapp": "WhatsApp"}
    )
    alerts = alerts.merge(contact_cols, on="user_id", how="left")

# --------------------------------------------------------------------------- #
# KPIs
# --------------------------------------------------------------------------- #
k1, k2, k3, k4 = st.columns(4)

total_alerts = len(alerts)
active_alerts = int((alerts["status"] == "active").sum()) if not alerts.empty else 0
sent_notifs = int((notifications["status"] == "sent").sum()) if not notifications.empty else 0

avg_price = "-"
if not prices.empty:
    prices["price_num"] = pd.to_numeric(prices["price"], errors="coerce")
    if prices["price_num"].notna().any():
        avg_price = f"{prices['price_num'].mean():.0f}"

k1.metric("Alertas totales", total_alerts)
k2.metric("Alertas activas", active_alerts)
k3.metric("Notificaciones enviadas", sent_notifs)
k4.metric("Precio promedio observado", avg_price)

st.caption(f"Backend de datos: **{db.backend}**")
st.divider()

# --------------------------------------------------------------------------- #
# Tabla de alertas
# --------------------------------------------------------------------------- #
st.subheader("Alertas")
if alerts.empty:
    st.info("Aun no hay alertas. Crea una desde la pagina principal.")
else:
    cols = [c for c in [
        "alert_id", "Nombre", "Email", "WhatsApp", "origin", "destination",
        "departure_date", "return_date", "max_price", "currency", "cabin",
        "status", "last_checked_at", "last_notified_at",
    ] if c in alerts.columns]
    st.dataframe(alerts[cols], use_container_width=True, hide_index=True)

# --------------------------------------------------------------------------- #
# Usuarios con alertas activas y estado de conexion de WhatsApp
# --------------------------------------------------------------------------- #
st.subheader("Usuarios con alertas activas")


@st.cache_data(ttl=300, show_spinner=False)
def _cached_hours_since_join(whatsapp: str) -> float | None:
    """Cachea la consulta a Twilio 5 minutos para no golpearlo en cada rerun."""
    return hours_since_last_join(whatsapp)


def _whatsapp_status(whatsapp: str | None) -> str:
    if not isinstance(whatsapp, str) or not whatsapp.strip():
        return "Sin WhatsApp"
    hours = _cached_hours_since_join(whatsapp)
    if hours is None:
        return "⚠️ Nunca hizo join"
    if hours < 18:
        return "✅ Conectado"
    if hours < 24:
        return "🟡 Por vencer (<6h)"
    return "🔴 Desconectado — pedir join"


active_only = alerts[alerts["status"] == "active"] if not alerts.empty else alerts

if active_only.empty or users_df.empty:
    st.info("Aun no hay usuarios con alertas activas.")
else:
    rows = []
    for user_id, group in active_only.groupby("user_id"):
        match = users_df[users_df["user_id"] == user_id]
        if match.empty:
            continue
        u = match.iloc[0]
        notified = (
            group["last_notified_at"].astype(str).str.strip()
            .replace({"nan": "", "None": ""}).ne("").any()
        )
        whatsapp_val = u.get("whatsapp")
        whatsapp_val = whatsapp_val if isinstance(whatsapp_val, str) and whatsapp_val.strip() else None
        rows.append({
            "Nombre": u.get("name", ""),
            "Email": u.get("email", ""),
            "WhatsApp": whatsapp_val or "-",
            "Alertas activas": len(group),
            "¿Ya recibio alerta?": "Si" if notified else "No",
            "Estado WhatsApp": _whatsapp_status(whatsapp_val),
        })
    users_table = pd.DataFrame(rows).sort_values("Nombre")
    st.dataframe(users_table, use_container_width=True, hide_index=True)
    st.caption(
        "El estado de WhatsApp se consulta en vivo contra Twilio (se cachea 5 min). "
        "'Desconectado' o 'Nunca hizo join' significa que hay que pedirle que mande "
        "**join these-garden** al +1 415 523 8886 para seguir recibiendo alertas ahi."
    )

# --------------------------------------------------------------------------- #
# Tabla de notificaciones
# --------------------------------------------------------------------------- #
st.subheader("Notificaciones recientes")
if notifications.empty:
    st.info("Aun no se han enviado notificaciones.")
else:
    cols = [c for c in [
        "sent_at", "alert_id", "channel", "status", "price_at_notification",
    ] if c in notifications.columns]
    df = notifications[cols].sort_values("sent_at", ascending=False) \
        if "sent_at" in notifications.columns else notifications[cols]
    st.dataframe(df, use_container_width=True, hide_index=True)
