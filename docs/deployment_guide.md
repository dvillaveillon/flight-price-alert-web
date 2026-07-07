# Guia de despliegue y configuracion

## 1. Desplegar la web en Streamlit Community Cloud

1. Sube el repo a GitHub (publico o privado).
2. Entra a https://share.streamlit.io e inicia sesion con GitHub.
3. "New app" → elige tu repo, rama `main`, y archivo principal `app_streamlit.py`.
4. Deploy. En 1–2 minutos tendras una URL publica del tipo
   `https://<tu-app>.streamlit.app`.

## 2. Configurar secrets en Streamlit

En el panel de tu app: **Settings → Secrets**. Pega en formato TOML solo lo que
uses (no hace falta nada para el modo demo):

```toml
FLIGHT_PROVIDER = "duffel"
SUPABASE_URL = "https://xxxx.supabase.co"
SUPABASE_KEY = "xxxx"
SENDGRID_API_KEY = "SG.xxxx"
SENDGRID_FROM_EMAIL = "alertas@tudominio.com"
TWILIO_ACCOUNT_SID = "ACxxxx"
TWILIO_AUTH_TOKEN = "xxxx"
TWILIO_WHATSAPP_FROM = "whatsapp:+14155238886"
NOTIFY_COOLDOWN_HOURS = "24"
ADMIN_PASSWORD = "elige-una-clave"
```

Streamlit expone esto como `st.secrets`, que `get_secret()` lee automaticamente.
`ADMIN_PASSWORD` protege la pagina "Admin Dashboard" (pide clave antes de
mostrar datos); si se omite, el panel queda abierto (modo demo).

## 3. Configurar Supabase

1. Crea un proyecto en https://supabase.com (tier gratuito).
2. En **SQL Editor**, pega y ejecuta el DDL de `docs/data_model.md`.
3. En **Settings → API**, copia el `Project URL` (→ `SUPABASE_URL`) y la
   `anon/public key` o `service_role key` (→ `SUPABASE_KEY`).
4. Define esas variables en Streamlit Secrets y en GitHub Secrets.

## 4. Configurar SendGrid (email)

1. Crea cuenta en https://sendgrid.com.
2. **Settings → API Keys → Create API Key** (permiso "Mail Send"). → `SENDGRID_API_KEY`.
3. Verifica un remitente en **Settings → Sender Authentication** (Single Sender).
   Ese correo va en `SENDGRID_FROM_EMAIL`.

## 4b. Configurar el proveedor de precios de vuelos (Duffel)

Se eligio **Duffel** en vez de Amadeus: el portal self-service gratuito de
Amadeus for Developers fue decomisionado (aviso de julio 2026) y ya no permite
registro de cuentas nuevas. Duffel tiene un entorno de test gratuito y estable.

1. Crea cuenta en https://app.duffel.com/join.
2. **Developers → Access tokens**, con el toggle **"Test mode"** activo.
3. Copia el token (empieza con `duffel_test_...`) → `DUFFEL_ACCESS_TOKEN`.
4. Define `FLIGHT_PROVIDER = "duffel"`.

`src/flight_api.py` ya tiene tambien una implementacion lista para Amadeus
(`_search_amadeus`) por si en el futuro vuelve a estar disponible o se usa otra
cuenta empresarial — solo hay que definir `AMADEUS_CLIENT_ID` /
`AMADEUS_CLIENT_SECRET` y cambiar `FLIGHT_PROVIDER` a `"amadeus"`.

## 5. Configurar Twilio WhatsApp Sandbox

1. Crea cuenta en https://twilio.com.
2. **Messaging → Try it out → Send a WhatsApp message** (Sandbox).
3. Copia `Account SID` (→ `TWILIO_ACCOUNT_SID`) y `Auth Token` (→ `TWILIO_AUTH_TOKEN`).
4. El numero del sandbox va en `TWILIO_WHATSAPP_FROM` (ej. `whatsapp:+14155238886`).
5. **Importante:** cada destinatario debe enviar el codigo `join <palabra>` al
   numero del sandbox antes de poder recibir mensajes. Es una regla de Twilio.

## 6. Automatizacion cada 6 horas

### Opcion A — GitHub Actions (incluida)

Ya viene `.github/workflows/check_prices.yml`. Solo define los secrets en
**Settings → Secrets and variables → Actions**. Puedes lanzarlo manualmente desde
la pestana **Actions → check-prices → Run workflow**.

> Nota: en Actions el CSV no persiste entre corridas. Para persistencia usa Supabase.

### Opcion B — Render Cron Job (alternativa)

1. Crea cuenta en https://render.com.
2. **New → Cron Job**. Conecta el repo.
3. Schedule: `0 */6 * * *`.
4. Build command: `pip install -r requirements.txt`
5. Command: `python check_prices.py`
6. En **Environment**, agrega las mismas variables del `.env.example`.

## 7. Compartir el link publico

Tu URL de Streamlit (`https://<tu-app>.streamlit.app`) ya es publica y responsive.
Compartela por correo, WhatsApp o QR. Cualquier persona puede crear una alerta
desde el celular o el computador sin instalar nada.

## 8. Branding Somos-Rata

1. **Logo**: sube el archivo del logo al repo en la ruta `assets/somos_rata_logo.png`.
   Streamlit lo toma automaticamente desde ahi (cabecera de la web y favicon). Si
   el archivo no existe todavia, la app sigue funcionando igual, solo sin logo
   (usa un emoji como respaldo).
2. **Logo en email y WhatsApp**: SendGrid y Twilio necesitan una **URL publica**
   del logo (no un archivo local) para poder mostrarlo. Como el repo es
   privado, se uso **GitHub Pages** (gratis) para publicar solo el logo sin
   hacer publico el codigo:
   ```
   gh api -X POST /repos/<usuario>/<repo>/pages -f "source[branch]=main" -f "source[path]=/"
   ```
   Esto publica el contenido del repo (incluida la carpeta `assets/`) en
   `https://<usuario>.github.io/<repo>/`, manteniendo el codigo fuente
   privado. La URL final del logo queda como
   `https://<usuario>.github.io/<repo>/assets/somos_rata_logo.png`. Define esa
   URL como la variable `BRAND_LOGO_URL` en **GitHub Actions Secrets** (es lo
   unico que la usa: el email y el WhatsApp los manda el cron, no la web de
   Streamlit). Si no la defines, el email se manda igual sin logo, y el
   WhatsApp se manda solo con texto (sin imagen adjunta) — nunca se rompe el
   envio.
3. **Colores**: los colores de marca tienen defaults ya aplicados (turquesa,
   azul oscuro, coral, amarillo). Se pueden sobreescribir con
   `BRAND_PRIMARY_COLOR`, `BRAND_SECONDARY_COLOR`, `BRAND_ACCENT_COLOR` y
   `BRAND_YELLOW` si mas adelante cambia la paleta.
4. **Limitacion del Sandbox de Twilio**: mientras uses el Sandbox, el remitente
   de WhatsApp siempre se ve como "Twilio Sandbox" (no se puede personalizar
   nombre ni foto de perfil), y cada destinatario debe escribir `join <palabra>`
   antes de poder recibir mensajes. Para que **cualquier usuario** reciba
   WhatsApp con el remitente "Somos-Rata" (nombre, foto, sin el paso de "join"),
   hay que migrar a un numero de **WhatsApp Business API aprobado por Meta**
   (proceso de verificacion de negocio, toma dias y tiene costo asociado).

## 9. Estado de este despliegue

Referencia del despliegue en vivo (julio 2026):

- **Web publica**: https://somosrata.streamlit.app/
- **Repo**: GitHub privado (`dvillaveillon/flight-price-alert-web`).
- **Base de datos**: Supabase (PostgreSQL), 4 tablas, sin RLS (aceptable porque
  solo el backend de la app usa la key, nunca el navegador del usuario final).
- **Proveedor de precios**: Duffel, entorno test (`FLIGHT_PROVIDER=duffel`).
- **Email**: SendGrid, remitente verificado por Single Sender (sin
  autenticacion de dominio DNS todavia — los primeros correos pueden caer en
  spam).
- **WhatsApp**: Twilio Sandbox (requiere `join these-garden` antes de recibir).
- **Automatizacion**: GitHub Actions, cron cada 6 horas (`0 */6 * * *`).
- **Admin Dashboard**: protegido con `ADMIN_PASSWORD`.
- **Logo publico**: servido via GitHub Pages
  (`https://dvillaveillon.github.io/flight-price-alert-web/assets/somos_rata_logo.png`),
  repo fuente sigue privado.

### Pendientes conocidos (no bloquean el uso, son mejoras futuras)

- Migrar de Twilio Sandbox a WhatsApp Business API aprobado por Meta (elimina
  el paso de "join" y personaliza nombre/foto del remitente).
- Autenticar el dominio de envio en SendGrid para mejorar entregabilidad
  (reduce que los correos caigan en spam).
- Evaluar si conviene activar Row Level Security (RLS) en Supabase si mas
  adelante se expone la API a otros clientes ademas del backend propio.
