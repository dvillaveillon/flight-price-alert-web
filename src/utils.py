"""
utils.py
--------
Funciones auxiliares transversales del proyecto Flight Price Alert Web.

Contiene:
- get_secret(): lectura de credenciales desde DOS contextos (Streamlit y worker/cron).
- get_logger(): logger estandarizado para todos los modulos.
- Validaciones simples (IATA, email, fechas).

Nota de arquitectura:
El worker de precios (check_prices.py) corre en GitHub Actions / Render, un contexto
donde NO existe st.secrets. La web (Streamlit) corre en otro contexto donde st.secrets
si existe. Por eso get_secret() intenta ambas fuentes en orden: primero st.secrets
(si estamos dentro de Streamlit) y luego las variables de entorno del sistema operativo.
"""

from __future__ import annotations

import logging
import os
import re
from datetime import date

# --- python-dotenv es opcional: si no esta instalado, no rompemos nada. ---
try:
    from dotenv import load_dotenv

    load_dotenv()  # carga variables desde un archivo .env local si existe
except Exception:  # pragma: no cover
    pass


# ---------------------------------------------------------------------------
# Manejo de secretos (dual: Streamlit + entorno)
# ---------------------------------------------------------------------------
def get_secret(key: str, default=None):
    """
    Obtiene una credencial/config buscando en dos fuentes, en este orden:
      1. st.secrets  -> cuando el codigo corre dentro de Streamlit Cloud/local.
      2. os.environ  -> cuando corre en el worker (GitHub Actions, Render, CLI).

    Nunca lanza excepcion si Streamlit no esta disponible: simplemente cae al entorno.
    """
    # 1) Intentar st.secrets (solo funciona si estamos ejecutando en Streamlit).
    try:
        import streamlit as st  # import local para no obligar a Streamlit en el worker

        if key in st.secrets:
            return st.secrets[key]
    except Exception:
        # Fuera de Streamlit, st.secrets no existe o falla: seguimos al entorno.
        pass

    # 2) Variables de entorno del sistema operativo.
    return os.environ.get(key, default)


# ---------------------------------------------------------------------------
# Logging estandarizado
# ---------------------------------------------------------------------------
def get_logger(name: str = "flight-price-alert") -> logging.Logger:
    """Devuelve un logger con formato uniforme para todo el proyecto."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


# ---------------------------------------------------------------------------
# Validaciones simples de entrada del formulario
# ---------------------------------------------------------------------------
_IATA_RE = re.compile(r"^[A-Za-z]{3}$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def is_valid_iata(code: str) -> bool:
    """Valida un codigo IATA de 3 letras (ej. SCL, MAD, JFK)."""
    return bool(code) and bool(_IATA_RE.match(code.strip()))


def is_valid_email(email: str) -> bool:
    """Validacion basica de formato de email."""
    return bool(email) and bool(_EMAIL_RE.match(email.strip()))


def normalize_iata(code: str) -> str:
    """Normaliza un codigo IATA a mayusculas sin espacios."""
    return (code or "").strip().upper()


def dates_are_coherent(departure: date, return_: date | None) -> bool:
    """La fecha de vuelta (si existe) no puede ser anterior a la de ida."""
    if return_ is None:
        return True
    return return_ >= departure


# ---------------------------------------------------------------------------
# Configuracion de negocio (con defaults sensatos, sobreescribibles por entorno)
# ---------------------------------------------------------------------------
def get_cooldown_hours() -> int:
    """Ventana anti-spam en horas entre dos notificaciones de la misma alerta."""
    try:
        return int(get_secret("NOTIFY_COOLDOWN_HOURS", 24))
    except (TypeError, ValueError):
        return 24


def get_flight_provider() -> str:
    """Proveedor de vuelos activo: 'mock' (default), 'amadeus' o 'duffel'."""
    return (get_secret("FLIGHT_PROVIDER", "mock") or "mock").strip().lower()


# ---------------------------------------------------------------------------
# Acceso de administrador (paginas de Streamlit)
# ---------------------------------------------------------------------------
def require_admin_access(prompt: str = "Clave de acceso") -> None:
    """
    Protege el resto de la pagina de Streamlit con la clave ADMIN_PASSWORD.

    Si la variable no esta configurada, no bloquea nada (modo demo, igual
    que el comportamiento historico del Admin Dashboard). Si esta
    configurada, pide la clave y corta la ejecucion de la pagina
    (st.stop()) hasta que coincida. Unico mecanismo de clave admin del
    proyecto: no crear una variable ni un flujo de autenticacion distinto.
    """
    import streamlit as st  # import local: esta funcion solo se usa en paginas

    admin_pass = get_secret("ADMIN_PASSWORD")
    if not admin_pass:
        return
    entered = st.text_input(prompt, type="password")
    if entered != admin_pass:
        st.stop()


# ---------------------------------------------------------------------------
# Enmascarado de datos personales para logs
# ---------------------------------------------------------------------------
def mask_contact(value: str | None) -> str:
    """
    Enmascara un email o telefono para que no quede PII legible en logs.

    Email: 'daniel@dominio.com' -> 'da***@dominio.com'.
    Telefono/otros: '+56981361946' -> '***1946' (ultimos 4 digitos visibles).
    """
    if not isinstance(value, str) or not value.strip():
        return "-"
    value = value.strip()
    if "@" in value:
        local, _, domain = value.partition("@")
        visible = local[:2] if len(local) > 2 else local[:1]
        return f"{visible}***@{domain}"
    return f"***{value[-4:]}" if len(value) > 4 else "***"
