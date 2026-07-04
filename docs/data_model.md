# Modelo de datos — Flight Price Alert Web

Cuatro tablas. Un `user` tiene N `alerts`; una `alert` tiene N `price_history` y
N `notifications`. En modo demo se replican como cuatro CSV en `data/`.

## DDL para Supabase / PostgreSQL

Copia y ejecuta esto en el SQL Editor de Supabase.

```sql
-- USERS
create table if not exists users (
  user_id           uuid primary key default gen_random_uuid(),
  name              text,
  email             text not null unique,
  whatsapp          text,
  consent_accepted  boolean not null default false,
  created_at        timestamptz not null default now()
);

-- ALERTS
create table if not exists alerts (
  alert_id            uuid primary key default gen_random_uuid(),
  user_id             uuid references users(user_id),
  origin              text not null,
  destination         text not null,
  departure_date      date not null,
  return_date         date,
  passengers          int not null default 1,
  max_price           numeric(10,2) not null,
  currency            text not null default 'USD',
  direct_only         boolean not null default false,
  accepts_connections boolean not null default true,
  flexible_days       int not null default 0,
  cabin               text not null default 'economy',
  baggage_required    boolean not null default false,
  status              text not null default 'active',
  created_at          timestamptz not null default now(),
  last_checked_at     timestamptz,
  last_notified_at    timestamptz
);
create index if not exists idx_alerts_status on alerts(status);
create index if not exists idx_alerts_status_checked on alerts(status, last_checked_at);

-- PRICE_HISTORY
create table if not exists price_history (
  price_id       uuid primary key default gen_random_uuid(),
  alert_id       uuid references alerts(alert_id),
  checked_at     timestamptz not null default now(),
  price          numeric(10,2),
  currency       text,
  airline        text,
  departure_time timestamptz,
  return_time    timestamptz,
  stops          int,
  provider       text,
  booking_link   text
);
create index if not exists idx_price_alert_time on price_history(alert_id, checked_at);

-- NOTIFICATIONS
create table if not exists notifications (
  notification_id       uuid primary key default gen_random_uuid(),
  alert_id              uuid references alerts(alert_id),
  sent_at               timestamptz not null default now(),
  channel               text,
  message               text,
  status                text,
  price_at_notification numeric(10,2)
);
```

## Notas de tipos

- `numeric(10,2)` para dinero (nunca `float`).
- `timestamptz` para todas las marcas de tiempo (se guardan en UTC).
- `flexible_days`: 0, 3 o 7.
- `status`: `active`, `paused`, `expired`.
- `channel`: `email`, `whatsapp`. `status` de notificacion: `sent`, `failed`.
