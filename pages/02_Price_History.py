"""
02_Price_History.py
-------------------
Historico de precios por alerta (serie de tiempo).

Permite seleccionar una alerta y ver la evolucion de los precios observados por
el worker a lo largo del tiempo. Marca visualmente el precio objetivo del usuario
para ver cuando la oferta cae por debajo del umbral.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.branding import BRAND_NAME, get_logo_local_path
from src.database import Database
from src.utils import require_admin_access

logo_path = get_logo_local_path()
st.set_page_config(page_title=f"{BRAND_NAME} · Historico", page_icon=logo_path or "🐭", layout="wide")

# --- Esta pagina expone nombre/email/WhatsApp y el historico de precios de
# TODOS los usuarios: debe quedar detras de la misma clave que el Admin
# Dashboard (ADMIN_PASSWORD). Sin esa variable configurada, queda abierta
# (modo demo, igual que el resto del proyecto). ---
require_admin_access()

st.caption(BRAND_NAME)
st.title("📈 Historico de precios")
st.caption("Evolucion de precios observados por el sistema para cada alerta.")

db = Database()
alerts = pd.DataFrame(db.get_all_alerts())
users_df = pd.DataFrame(db.get_all_users())
prices = pd.DataFrame(db.get_price_history())

if alerts.empty:
    st.info("Aun no hay alertas. Crea una desde la pagina principal.")
    st.stop()

if prices.empty:
    st.info("Aun no hay precios registrados. Ejecuta el worker: `python check_prices.py`.")
    st.stop()

# Contacto de quien creo cada alerta, para identificarla en el selector.
if not users_df.empty and "user_id" in alerts.columns:
    contact_cols = users_df[["user_id", "name", "email", "whatsapp"]].rename(
        columns={"name": "Nombre", "email": "Email", "whatsapp": "WhatsApp"}
    )
    alerts = alerts.merge(contact_cols, on="user_id", how="left")

# --------------------------------------------------------------------------- #
# Selector de alerta (etiqueta legible: quien la creo + ruta + fecha)
# --------------------------------------------------------------------------- #
def _label(row: pd.Series) -> str:
    nombre = row.get("Nombre") or "Sin nombre"
    email = row.get("Email") or "sin email"
    whatsapp = row.get("WhatsApp") or "sin WhatsApp"
    return (f"{nombre} · {email} · {whatsapp} — "
            f"{row.get('origin')} -> {row.get('destination')} "
            f"| ida {row.get('departure_date')} "
            f"| max {row.get('max_price')} {row.get('currency')}")

alerts["label"] = alerts.apply(_label, axis=1)
label_to_id = dict(zip(alerts["label"], alerts["alert_id"]))

selected_label = st.selectbox("Selecciona una alerta", list(label_to_id.keys()))
selected_id = label_to_id[selected_label]

selected_alert_row = alerts[alerts["alert_id"] == selected_id].iloc[0]
st.caption(
    f"👤 **{selected_alert_row.get('Nombre') or 'Sin nombre'}** &middot; "
    f"{selected_alert_row.get('Email') or 'sin email'} &middot; "
    f"{selected_alert_row.get('WhatsApp') or 'sin WhatsApp'}"
)

# --------------------------------------------------------------------------- #
# Preparacion de la serie de tiempo
# --------------------------------------------------------------------------- #
serie = prices[prices["alert_id"] == selected_id].copy()
if serie.empty:
    st.warning("Esta alerta aun no tiene precios registrados.")
    st.stop()

serie["checked_at"] = pd.to_datetime(serie["checked_at"], errors="coerce")
serie["price"] = pd.to_numeric(serie["price"], errors="coerce")
serie = serie.dropna(subset=["checked_at", "price"]).sort_values("checked_at")

# Precio objetivo de la alerta seleccionada (linea de referencia).
max_price = pd.to_numeric(selected_alert_row.get("max_price"), errors="coerce")

# --------------------------------------------------------------------------- #
# KPIs de la serie
# --------------------------------------------------------------------------- #
c1, c2, c3, c4 = st.columns(4)
c1.metric("Precio minimo", f"{serie['price'].min():.0f}")
c2.metric("Precio maximo", f"{serie['price'].max():.0f}")
c3.metric("Precio actual", f"{serie['price'].iloc[-1]:.0f}")
c4.metric("Precio objetivo", f"{max_price:.0f}" if pd.notna(max_price) else "-")

# --------------------------------------------------------------------------- #
# Grafico (line chart nativo de Streamlit)
# --------------------------------------------------------------------------- #
return_date = selected_alert_row.get("return_date")
is_round_trip = isinstance(return_date, str) and return_date.strip() not in ("", "nan", "None")

if is_round_trip:
    st.caption(
        "📊 **Historico de precio total del viaje ida y vuelta.** "
        "Este valor corresponde al precio total del itinerario seleccionado, "
        "no a cada tramo por separado (Duffel entrega un unico precio para "
        "todo el itinerario, no un precio de ida y otro de vuelta)."
    )
else:
    st.caption("📊 Historico de precio del vuelo (solo ida).")

chart_df = serie[["checked_at", "price"]].set_index("checked_at").rename(
    columns={"price": "Precio observado"}
)
if pd.notna(max_price):
    chart_df["Precio objetivo"] = max_price

st.line_chart(chart_df, use_container_width=True)

with st.expander("Ver datos crudos"):
    cols = [c for c in ["checked_at", "price", "currency", "airline", "stops",
                        "provider"] if c in serie.columns]
    st.dataframe(serie[cols], use_container_width=True, hide_index=True)
