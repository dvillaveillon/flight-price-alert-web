"""
app_streamlit.py
----------------
Web publica del proyecto (pantalla principal).

Muestra la propuesta de valor y el formulario de alerta. Al enviar:
  1. Valida los campos.
  2. Crea/reutiliza el usuario y guarda la alerta en la base de datos.
  3. Muestra el mensaje de confirmacion.

Diseno: responsive (usa st.columns), identidad visual institucional definida en
.streamlit/config.toml. Este archivo es la home; las paginas del dashboard viven
en la carpeta pages/ y aparecen solas en la barra lateral.
"""

from __future__ import annotations

from datetime import date, timedelta

import streamlit as st

from src.branding import BRAND_NAME, BRAND_SLOGAN, get_colors, get_logo_local_path
from src.database import Database
from src.notifier_whatsapp import send_whatsapp
from src.utils import (
    dates_are_coherent,
    is_valid_email,
    is_valid_iata,
    normalize_iata,
)

colors = get_colors()
logo_path = get_logo_local_path()

# --------------------------------------------------------------------------- #
# Configuracion de pagina
# --------------------------------------------------------------------------- #
st.set_page_config(
    page_title=BRAND_NAME,
    page_icon=logo_path or "🐭",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# Estilos puntuales complementarios al tema de config.toml.
st.markdown(
    f"""
    <style>
      .hero-title {{ font-size: 1.7rem; font-weight: 700; color: {colors['secondary']};
                    margin-bottom: 0.2rem; }}
      .hero-sub   {{ font-size: 1.05rem; color: #444; margin-bottom: 1.2rem; }}
      .badge      {{ display: inline-block; background: {colors['primary']}; color: #fff;
                    padding: 2px 10px; border-radius: 12px; font-size: 0.8rem; }}
      .ok-box     {{ border-left: 5px solid {colors['accent']}; padding: 12px 16px;
                    background: #F8FAFC; border-radius: 6px; }}
    </style>
    """,
    unsafe_allow_html=True,
)


# --------------------------------------------------------------------------- #
# Cabecera de marca
# --------------------------------------------------------------------------- #
# El logo ya incluye el nombre y el eslogan, asi que si esta disponible se
# muestra solo (mas grande); si no, se usa texto de respaldo.
if logo_path:
    _, logo_col, _ = st.columns([1, 2, 1])
    with logo_col:
        st.image(logo_path, use_container_width=True)
else:
    st.markdown(
        f'<h1 style="text-align:center;color:{colors["secondary"]};margin-bottom:0;">{BRAND_NAME}</h1>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<p style="text-align:center;color:{colors["primary"]};font-weight:600;'
        f'font-size:1.05rem;margin-top:0.2rem;">{BRAND_SLOGAN}</p>',
        unsafe_allow_html=True,
    )

# --------------------------------------------------------------------------- #
# Cabecera / propuesta de valor
# --------------------------------------------------------------------------- #
st.markdown('<span class="badge">Alertas de vuelos</span>', unsafe_allow_html=True)
st.markdown('<div class="hero-title">¿Donde quieres viajar y cuanto quieres pagar?</div>',
            unsafe_allow_html=True)
st.markdown(
    '<div class="hero-sub">Dinos tu ruta, fecha y precio ideal. '
    'Nosotros revisamos los precios y te avisamos cuando encontremos una oportunidad.</div>',
    unsafe_allow_html=True,
)


# --------------------------------------------------------------------------- #
# Formulario de alerta
# --------------------------------------------------------------------------- #
with st.form("alert_form", clear_on_submit=False):
    st.subheader("Tus datos de contacto")
    c1, c2 = st.columns(2)
    with c1:
        name = st.text_input("Nombre *", placeholder="Tu nombre")
        email = st.text_input("Email *", placeholder="tucorreo@ejemplo.com")
    with c2:
        whatsapp = st.text_input("WhatsApp (opcional)", placeholder="+56912345678")

    st.subheader("Tu ruta")
    c3, c4 = st.columns(2)
    with c3:
        origin = st.text_input("Origen (IATA) *", placeholder="SCL", max_chars=3)
    with c4:
        destination = st.text_input("Destino (IATA) *", placeholder="MAD", max_chars=3)

    st.subheader("Fechas y pasajeros")
    c5, c6, c7 = st.columns(3)
    with c5:
        departure_date = st.date_input("Fecha de ida *",
                                       value=date.today() + timedelta(days=30),
                                       min_value=date.today())
    with c6:
        has_return = st.checkbox("¿Ida y vuelta?", value=True)
        return_date = st.date_input("Fecha de vuelta",
                                    value=date.today() + timedelta(days=37),
                                    min_value=date.today(),
                                    disabled=not has_return)
    with c7:
        passengers = st.number_input("Pasajeros *", min_value=1, max_value=9, value=1)

    st.subheader("Preferencias de vuelo")
    c8, c9, c10 = st.columns(3)
    with c8:
        currency = st.selectbox("Moneda", ["USD", "EUR", "CLP"], index=0)
        cabin = st.selectbox("Cabina",
                             ["economy", "premium_economy", "business"], index=0)
    with c9:
        direct_only = st.radio("¿Solo vuelo directo?", ["No", "Si"], horizontal=True) == "Si"
        accepts_connections = st.radio("¿Acepta conexiones?",
                                       ["Si", "No"], horizontal=True) == "Si"
    with c10:
        baggage_required = st.radio("¿Equipaje requerido?",
                                    ["No", "Si"], horizontal=True) == "Si"
        flex_label = st.selectbox("Flexibilidad de fechas",
                                  ["Exactas", "±3 dias", "±7 dias"], index=0)

    st.subheader("Precio objetivo")
    max_price = st.number_input(
        f"Precio maximo que estas dispuesto a pagar ({currency}) *",
        min_value=1.0, value=500.0, step=10.0,
    )

    consent = st.checkbox(
        "Acepto recibir alertas por email y/o WhatsApp sobre esta busqueda. *"
    )

    submitted = st.form_submit_button("Crear mi alerta", type="primary",
                                      use_container_width=True)


# --------------------------------------------------------------------------- #
# Procesamiento del envio
# --------------------------------------------------------------------------- #
def _flex_to_days(label: str) -> int:
    return {"Exactas": 0, "±3 dias": 3, "±7 dias": 7}.get(label, 0)


if submitted:
    # --- Validaciones ---
    errors = []
    if not name.strip():
        errors.append("El nombre es obligatorio.")
    if not is_valid_email(email):
        errors.append("El email no tiene un formato valido.")
    if not is_valid_iata(origin):
        errors.append("El origen debe ser un codigo IATA de 3 letras (ej. SCL).")
    if not is_valid_iata(destination):
        errors.append("El destino debe ser un codigo IATA de 3 letras (ej. MAD).")
    ret = return_date if has_return else None
    if not dates_are_coherent(departure_date, ret):
        errors.append("La fecha de vuelta no puede ser anterior a la de ida.")
    if max_price <= 0:
        errors.append("El precio maximo debe ser mayor que cero.")
    if not consent:
        errors.append("Debes aceptar el consentimiento para recibir alertas.")

    if errors:
        for e in errors:
            st.error(e)
    else:
        try:
            db = Database()
            user_id = db.upsert_user(
                name=name.strip(),
                email=email.strip().lower(),
                whatsapp=whatsapp.strip() or None,
                consent=True,
            )
            db.insert_alert(user_id, {
                "origin": normalize_iata(origin),
                "destination": normalize_iata(destination),
                "departure_date": departure_date,
                "return_date": ret,
                "passengers": int(passengers),
                "max_price": float(max_price),
                "currency": currency,
                "direct_only": direct_only,
                "accepts_connections": accepts_connections,
                "flexible_days": _flex_to_days(flex_label),
                "cabin": cabin,
                "baggage_required": baggage_required,
            })

            st.markdown(
                '<div class="ok-box"><b>Tu alerta fue creada correctamente.</b><br>'
                'Revisaremos precios periodicamente y te avisaremos si encontramos '
                'un vuelo igual o menor a tu precio objetivo.</div>',
                unsafe_allow_html=True,
            )

            # Confirmacion inmediata por WhatsApp (no depende de la respuesta
            # automatica del Sandbox de Twilio, que es poco confiable). Si el
            # numero aun no hizo "join" al sandbox, este envio simplemente
            # fallara en silencio: no rompe la creacion de la alerta.
            if whatsapp.strip():
                try:
                    send_whatsapp(
                        whatsapp.strip(),
                        f"Hola {name.strip()}! Soy {BRAND_NAME}. Tu alerta "
                        f"{normalize_iata(origin)} -> {normalize_iata(destination)} "
                        "quedo creada y tu WhatsApp esta conectado. Te avisamos "
                        "aqui cuando encontremos un precio que calce.",
                    )
                except Exception:
                    pass
                st.caption("Si agregaste WhatsApp, revisa que te haya llegado "
                           "un mensaje de confirmacion (puede tardar unos segundos).")

            st.caption(f"Backend de datos activo: {db.backend} "
                       "(en modo demo se guarda en CSV local).")
            st.balloons()
        except Exception as exc:
            st.error(f"Ocurrio un problema al guardar tu alerta: {exc}")


st.divider()
st.caption("Proyecto de portafolio · Data Science / AI / Automation aplicado a negocio.")
