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
notifications = pd.DataFrame(db.get_notifications())
prices = pd.DataFrame(db.get_price_history())

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
        "alert_id", "origin", "destination", "departure_date", "return_date",
        "max_price", "currency", "cabin", "status", "last_checked_at",
        "last_notified_at",
    ] if c in alerts.columns]
    st.dataframe(alerts[cols], use_container_width=True, hide_index=True)

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
