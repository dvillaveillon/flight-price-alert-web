# Arquitectura — Flight Price Alert Web

## Vision general

El sistema se divide en tres planos independientes, unidos unicamente por la base
de datos (fuente unica de verdad).

```
PLANO 1 — WEB PUBLICA (Streamlit)
  app_streamlit.py + pages/  ──► escribe/lee ──►  BASE DE DATOS

PLANO 2 — PERSISTENCIA
  Supabase (PostgreSQL)  ó  Fallback CSV local
  tablas: users, alerts, price_history, notifications

PLANO 3 — WORKER ASINCRONO (cron)
  check_prices.py ──► flight_api (mock/amadeus/duffel)
                 ──► alert_rules (umbral + anti-spam)
                 ──► notifier_email (SendGrid) / notifier_whatsapp (Twilio)
```

## Decision clave: worker independiente de la web

Streamlit Community Cloud "duerme" la app tras inactividad. Si el chequeo de
precios dependiera de que la web este despierta, fallaria. Por eso el worker
corre en su propio contexto (GitHub Actions / Render) y lee credenciales tanto de
`st.secrets` como de `os.environ` mediante `get_secret()`.

## Patron Strategy para vuelos

`flight_api.search_flights(params)` es el unico punto de entrada. La variable
`FLIGHT_PROVIDER` (mock | amadeus | duffel) decide la implementacion. Todos los
proveedores devuelven el mismo contrato de oferta, asi que el resto del sistema
no cambia al cambiar de proveedor. `mock` es el default (sin costos, sin keys).

## Anti-spam

Centralizado en `alert_rules.evaluate()`. Notifica solo si:
1. mejor oferta <= `max_price`, y
2. `last_notified_at` esta fuera de la ventana de enfriamiento (default 24 h).

## Degradacion elegante

- Sin credenciales de DB → CSV local.
- Sin key de SendGrid/Twilio → modo dry-run (registra en consola, no falla).
- Sin key de proveedor real → cae a mock.

Esto permite clonar el repo y ver el sistema completo funcionando sin configurar nada.
