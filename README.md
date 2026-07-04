# ✈️ Flight Price Alert Web

Web publica donde cualquier persona deja una **alerta de vuelo** (ruta, fechas,
pasajeros, precio maximo y contacto). El sistema revisa precios periodicamente y
**avisa por email o WhatsApp** cuando encuentra un precio menor o igual al objetivo.

Proyecto de portafolio de **Data Science / AI / Automation aplicado a negocio**.

---

## ✨ Que demuestra

- App publica y compartible por link (Streamlit).
- Uso de APIs reales de vuelos (Amadeus / Duffel) con arquitectura flexible.
- Integracion con base de datos (Supabase / PostgreSQL) con fallback local.
- Automatizacion de procesos (GitHub Actions / Render Cron).
- Envio de alertas (SendGrid / Twilio) con control anti-spam.
- Manejo seguro de credenciales (variables de entorno y `st.secrets`).
- Dashboard ejecutivo y historico de precios.
- Diseno de producto MVP y codigo listo para portafolio.

---

## 🚀 Ejecutar en local (modo demo, sin credenciales)

Funciona **sin ninguna API key**: usa un proveedor de vuelos simulado (`mock`) y
guarda todo en CSV local.

```bash
# 1. Clonar e instalar
git clone <tu-repo>
cd flight-price-alert-web
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 2. Levantar la web publica
streamlit run app_streamlit.py
# Abre http://localhost:8501 y crea una alerta.

# 3. (En otra terminal) ejecutar el worker de precios
python check_prices.py
# Revisa precios, guarda historico y "notifica" en modo dry-run (por consola).
```

Vuelve a la web y abre en la barra lateral **Admin Dashboard** y **Price History**
para ver KPIs, alertas, notificaciones y la evolucion de precios.

---

## 🏗️ Arquitectura

Tres planos independientes unidos por la base de datos:

```
WEB (Streamlit)  ──►  BASE DE DATOS  ◄──  WORKER (cron)
app_streamlit.py      Supabase / CSV      check_prices.py
   pages/                                  flight_api · alert_rules
                                           notifier_email · notifier_whatsapp
```

Detalle completo en [`docs/architecture.md`](docs/architecture.md).

---

## 📂 Estructura

```
flight-price-alert-web/
├── app_streamlit.py          # Web publica (formulario)
├── check_prices.py           # Worker: revisa precios y notifica
├── src/
│   ├── flight_api.py         # Strategy: mock / amadeus / duffel
│   ├── mock_flight_api.py    # Proveedor simulado (default)
│   ├── database.py           # Supabase + fallback CSV
│   ├── alert_rules.py        # Umbral + anti-spam
│   ├── notifier_email.py     # SendGrid (dry-run sin key)
│   ├── notifier_whatsapp.py  # Twilio (dry-run sin key)
│   └── utils.py              # get_secret dual, validaciones, logging
├── pages/
│   ├── 01_Admin_Dashboard.py # KPIs y tablas
│   └── 02_Price_History.py   # Series de tiempo
├── .streamlit/config.toml    # Identidad visual
├── .github/workflows/check_prices.yml  # Cron cada 6 h
└── docs/                     # architecture · data_model · deployment_guide
```

---

## ⚙️ Configuracion (modo real)

Copia `.env.example` a `.env` y completa solo lo que uses. Guias paso a paso de
Supabase, SendGrid, Twilio y despliegue en
[`docs/deployment_guide.md`](docs/deployment_guide.md).

| Variable | Para que |
|---|---|
| `FLIGHT_PROVIDER` | `mock` (default), `amadeus` o `duffel` |
| `SUPABASE_URL` / `SUPABASE_KEY` | Base de datos en la nube |
| `SENDGRID_API_KEY` | Envio de email |
| `TWILIO_*` | Envio de WhatsApp |
| `NOTIFY_COOLDOWN_HOURS` | Ventana anti-spam (default 24) |

---

## 🔒 Seguridad y privacidad

- Sin claves hardcodeadas: todo via entorno / `st.secrets`.
- `.env`, `secrets.toml` y CSV locales estan en `.gitignore`.
- Consentimiento explicito del usuario antes de crear una alerta.
- Control anti-duplicados / anti-spam por alerta.
- Sin scraping: solo APIs oficiales con permiso.

---

## 🔮 Mejoras futuras

- Prediccion de precios (serie de tiempo / ML).
- Recomendacion "comprar ahora vs esperar".
- Deteccion de oportunidades y tendencias por ruta.
- Monetizacion: links de afiliados, plan premium, alertas priorizadas.

---

## ⚠️ Aviso

Proyecto educativo / de portafolio. Verifica siempre disponibilidad y condiciones
en el sitio de la aerolinea o agencia antes de comprar.
