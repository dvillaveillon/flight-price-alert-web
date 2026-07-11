"""
city_resolver.py
-----------------
Traduce nombres de ciudad (espanol/ingles, con o sin tildes) a codigos IATA
de ciudad, para que el usuario no tenga que saber el codigo de memoria.

Duffel (proveedor de precios activo) acepta codigos de CIUDAD IATA (ej. PAR,
LON, NYC) ademas de codigos de aeropuerto: al recibir un codigo de ciudad,
Duffel ya busca en todos los aeropuertos de esa ciudad. Por eso no hace falta
logica de busqueda multi-aeropuerto aca: solo traducir el nombre al codigo y
dejar que Duffel (o el mock) haga el resto igual que siempre.

Agregar una ciudad nueva = una linea nueva en _CITY_ALIASES.
"""

from __future__ import annotations

import unicodedata

from src.utils import is_valid_iata, normalize_iata

# alias normalizado (minusculas, sin tildes) -> codigo IATA de ciudad.
_CITY_ALIASES: dict[str, str] = {
    "santiago": "SCL",
    "santiago de chile": "SCL",
    "madrid": "MAD",
    "paris": "PAR",
    "londres": "LON",
    "london": "LON",
    "nueva york": "NYC",
    "new york": "NYC",
    "barcelona": "BCN",
    "buenos aires": "BUE",
    "lima": "LIM",
    "bogota": "BOG",
    "ciudad de mexico": "MEX",
    "mexico city": "MEX",
    "sao paulo": "SAO",
    "roma": "ROM",
    "rome": "ROM",
    "miami": "MIA",
    "frankfurt": "FRA",

    # --- Chile (ciudades con aeropuerto comercial) ---
    "arica": "ARI",
    "iquique": "IQQ",
    "antofagasta": "ANF",
    "calama": "CJC",
    "copiapo": "CPO",
    "la serena": "LSC",
    "concepcion": "CCP",
    "conce": "CCP",
    "temuco": "ZCO",
    "valdivia": "ZAL",
    "osorno": "ZOS",
    "puerto montt": "PMC",
    "castro": "MHC",
    "chiloe": "MHC",
    "balmaceda": "BBA",
    "coyhaique": "BBA",
    "punta arenas": "PUQ",

    # --- Capitales de Latinoamerica ---
    "montevideo": "MVD",
    "asuncion": "ASU",
    "la paz": "LPB",
    "quito": "UIO",
    "caracas": "CCS",
    "san jose": "SJO",
    "san jose de costa rica": "SJO",
    "panama": "PTY",
    "ciudad de panama": "PTY",
    "panama city": "PTY",
    "rio de janeiro": "RIO",
    "rio": "RIO",
    "brasilia": "BSB",

    # --- Destinos turisticos de playa ---
    "punta cana": "PUJ",
    "cancun": "CUN",
}


def _normalize_text(text: str) -> str:
    """Minusculas, sin tildes/diacriticos, sin espacios de sobra."""
    text = (text or "").strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return text


def resolve_city(texto: str) -> str | None:
    """Busca el texto en el diccionario de ciudades. None si no esta."""
    return _CITY_ALIASES.get(_normalize_text(texto))


def resolve_location(texto: str) -> str | None:
    """
    Resuelve lo que haya escrito el usuario a un codigo IATA.

    Primero intenta como nombre de ciudad conocido; si no matchea, acepta un
    codigo IATA de 3 letras escrito directamente (respaldo para usuarios
    avanzados). None si no se puede resolver de ninguna forma.
    """
    city_code = resolve_city(texto)
    if city_code:
        return city_code
    if is_valid_iata(texto):
        return normalize_iata(texto)
    return None


def describe_location(texto: str) -> str | None:
    """Texto para mostrarle al usuario que codigo se va a usar. None si no se reconoce."""
    city_code = resolve_city(texto)
    if city_code:
        return (f"{texto.strip().title()} → {city_code} "
                "(código de ciudad: incluye todos sus aeropuertos)")
    if is_valid_iata(texto):
        return f"{normalize_iata(texto)} (código IATA)"
    return None


def city_label_for_code(code: str) -> str:
    """
    Camino inverso: dado un codigo IATA (ej. "PAR"), devuelve un nombre de
    ciudad legible (ej. "Paris") para usar en links de busqueda (hoteles).

    Si el codigo no esta en _CITY_ALIASES (ej. aeropuerto puntual no listado),
    devuelve el codigo tal cual: sigue siendo un query valido para Google.
    """
    if not code:
        return code
    code_norm = code.strip().upper()
    for alias, iata in _CITY_ALIASES.items():
        if iata == code_norm:
            return alias.title()
    return code_norm
