# 🐭✈️ Somos-Rata — Flight Price Alert Web

Web publica donde cualquier persona deja una **alerta de vuelo** (ruta, fechas,
pasajeros, precio maximo y contacto). El sistema revisa precios periodicamente y
**avisa por email o WhatsApp** cuando encuentra un precio menor o igual al objetivo.

**En vivo**: https://somosrata.streamlit.app/ — funcionando con base de datos,
precios y notificaciones reales (no es una demo).

Proyecto de portafolio de **Data Science / AI / Automation aplicado a negocio**.

---

## ✨ Que demuestra

- App publica y compartible por link (Streamlit Community Cloud), con
  identidad de marca propia (Somos-Rata).
- Uso de una API real de vuelos (Duffel, con Amadeus tambien soportado en el
  codigo) con arquitectura flexible (patron Strategy).
- Integracion con base de datos en la nube (Supabase / PostgreSQL) con
  fallback local a CSV para correr sin credenciales.
- Automatizacion de procesos (GitHub Actions, cron cada 6 horas).
- Envio de alertas reales (SendGrid / Twilio WhatsApp) con control anti-spam
  y HTML de marca para el email.
- Manejo seguro de credenciales (variables de entorno, `st.secrets` y GitHub
  Actions Secrets — nunca hardcodeadas).
- Dashboard ejecutivo protegido por clave, e historico de precios.
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
│   ├── alert_rules.py        # Umbral + anti-spam + texto plano del mensaje
│   ├── branding.py           # Nombre, eslogan, colores, logo, email HTML, texto WhatsApp
│   ├── notifier_email.py     # SendGrid (dry-run sin key; soporta HTML)
│   ├── notifier_whatsapp.py  # Twilio (dry-run sin key; soporta imagen adjunta)
│   └── utils.py              # get_secret dual, validaciones, logging
├── pages/
│   ├── 01_Admin_Dashboard.py # KPIs y tablas (protegido por ADMIN_PASSWORD)
│   └── 02_Price_History.py   # Series de tiempo
├── assets/                   # Logo de marca (somos_rata_logo.png)
├── .streamlit/config.toml    # Identidad visual (tema Somos-Rata)
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
| `SENDGRID_API_KEY` / `SENDGRID_FROM_EMAIL` | Envio de email |
| `TWILIO_*` | Envio de WhatsApp |
| `NOTIFY_COOLDOWN_HOURS` | Ventana anti-spam (default 24) |
| `ADMIN_PASSWORD` | Protege el Admin Dashboard (opcional) |
| `BRAND_LOGO_URL` | URL publica del logo, para email/WhatsApp |
| `BRAND_PRIMARY_COLOR` / `BRAND_SECONDARY_COLOR` / `BRAND_ACCENT_COLOR` / `BRAND_YELLOW` | Colores de marca (tienen defaults) |

---

## 🔒 Seguridad y privacidad

- Sin claves hardcodeadas: todo via entorno / `st.secrets` / GitHub Actions Secrets.
- `.env`, `secrets.toml` y CSV locales estan en `.gitignore`.
- Consentimiento explicito del usuario antes de crear una alerta.
- Control anti-duplicados / anti-spam por alerta.
- Admin Dashboard protegido por clave (`ADMIN_PASSWORD`) antes de compartir el
  link publicamente.
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
