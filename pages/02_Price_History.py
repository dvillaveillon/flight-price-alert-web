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

from src.database import Database

st.set_page_config(page_title="Historico de precios", page_icon="📈", layout="wide")

st.title("📈 Historico de precios")
st.caption("Evolucion de precios observados por el sistema para cada alerta.")

db = Database()
alerts = pd.DataFrame(db.get_all_alerts())
prices = pd.DataFrame(db.get_price_history())

if alerts.empty:
    st.info("Aun no hay alertas. Crea una desde la pagina principal.")
    st.stop()

if prices.empty:
    st.info("Aun no hay precios registrados. Ejecuta el worker: `python check_prices.py`.")
    st.stop()

# --------------------------------------------------------------------------- #
# Selector de alerta (etiqueta legible: ruta + fecha)
# --------------------------------------------------------------------------- #
def _label(row: pd.Series) -> str:
    return (f"{row.get('origin')} -> {row.get('destination')} "
            f"| ida {row.get('departure_date')} "
            f"| max {row.get('max_price')} {row.get('currency')}")

alerts["label"] = alerts.apply(_label, axis=1)
label_to_id = dict(zip(alerts["label"], alerts["alert_id"]))

selected_label = st.selectbox("Selecciona una alerta", list(label_to_id.keys()))
selected_id = label_to_id[selected_label]

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
alert_row = alerts[alerts["alert_id"] == selected_id].iloc[0]
max_price = pd.to_numeric(alert_row.get("max_price"), errors="coerce")

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
