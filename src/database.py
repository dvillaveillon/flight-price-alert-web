"""
database.py
-----------
Capa de persistencia con DOS backends intercambiables:

  1. Supabase (PostgreSQL) -> si existen SUPABASE_URL y SUPABASE_KEY.
  2. Fallback CSV local     -> si NO hay credenciales (modo demo).

El resto del sistema NUNCA sabe cual backend esta activo: usa siempre la misma
interfaz (la clase Database). Esto permite:
  - Clonar el repo y ejecutarlo sin credenciales (modo demo con CSV).
  - Pasar a produccion con Supabase cambiando solo variables de entorno.

Tablas replicadas en ambos backends:
  users, alerts, price_history, notifications
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any

import pandas as pd

from src.utils import get_logger, get_secret

logger = get_logger(__name__)

# Carpeta donde viven los CSV en modo demo.
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")

# Definicion de columnas por tabla (fuente unica de verdad del esquema CSV).
SCHEMAS: dict[str, list[str]] = {
    "users": [
        "user_id", "name", "email", "whatsapp", "consent_accepted", "created_at",
    ],
    "alerts": [
        "alert_id", "user_id", "origin", "destination", "departure_date",
        "return_date", "passengers", "max_price", "currency", "direct_only",
        "accepts_connections", "flexible_days", "cabin", "baggage_required",
        "status", "created_at", "last_checked_at", "last_notified_at",
    ],
    "price_history": [
        "price_id", "alert_id", "checked_at", "price", "currency", "airline",
        "departure_time", "return_time", "stops", "provider", "booking_link",
    ],
    "notifications": [
        "notification_id", "alert_id", "sent_at", "channel", "message",
        "status", "price_at_notification",
    ],
}


def _now() -> str:
    """Timestamp UTC en formato ISO-8601 (uniforme para ambos backends)."""
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    """Genera un identificador unico (uuid4 como string)."""
    return str(uuid.uuid4())


def _supabase_row(row: dict[str, Any]) -> dict[str, Any]:
    """
    Convierte cadenas vacias a NULL antes de insertar en Postgres.

    El backend CSV usa "" para representar "sin valor" (funciona bien en texto
    plano), pero Postgres rechaza "" para columnas timestamptz/date/numeric.
    """
    return {k: (None if v == "" else v) for k, v in row.items()}


class Database:
    """
    Fachada de persistencia. Detecta automaticamente el backend en __init__.

    Uso:
        db = Database()
        db.backend  -> 'supabase' o 'csv'
    """

    def __init__(self) -> None:
        self.supabase_url = get_secret("SUPABASE_URL")
        self.supabase_key = get_secret("SUPABASE_KEY")
        self._client = None

        if self.supabase_url and self.supabase_key:
            try:
                from supabase import create_client  # import perezoso

                self._client = create_client(self.supabase_url, self.supabase_key)
                self.backend = "supabase"
                logger.info("Backend de datos: Supabase (PostgreSQL).")
            except Exception as exc:  # si falla la lib, caemos a CSV
                logger.warning("No se pudo iniciar Supabase (%s). Usando CSV.", exc)
                self.backend = "csv"
        else:
            self.backend = "csv"
            logger.info("Backend de datos: CSV local (modo demo, sin credenciales).")

        if self.backend == "csv":
            self._ensure_csv_files()

    # ------------------------------------------------------------------ #
    # Utilidades internas del backend CSV
    # ------------------------------------------------------------------ #
    def _csv_path(self, table: str) -> str:
        return os.path.join(DATA_DIR, f"{table}.csv")

    def _ensure_csv_files(self) -> None:
        """Crea la carpeta data/ y los CSV vacios con cabeceras si no existen."""
        os.makedirs(DATA_DIR, exist_ok=True)
        for table, cols in SCHEMAS.items():
            path = self._csv_path(table)
            if not os.path.exists(path):
                pd.DataFrame(columns=cols).to_csv(path, index=False)

    def _csv_read(self, table: str) -> pd.DataFrame:
        path = self._csv_path(table)
        if not os.path.exists(path):
            return pd.DataFrame(columns=SCHEMAS[table])
        return pd.read_csv(path, dtype=str).fillna("")

    def _csv_append(self, table: str, row: dict[str, Any]) -> None:
        df = self._csv_read(table)
        df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
        df.to_csv(self._csv_path(table), index=False)

    def _csv_update(self, table: str, id_col: str, id_val: str, changes: dict) -> None:
        df = self._csv_read(table)
        if df.empty:
            return
        mask = df[id_col] == str(id_val)
        for k, v in changes.items():
            df.loc[mask, k] = "" if v is None else str(v)
        df.to_csv(self._csv_path(table), index=False)

    # ------------------------------------------------------------------ #
    # USERS
    # ------------------------------------------------------------------ #
    def upsert_user(self, name: str, email: str, whatsapp: str | None,
                    consent: bool) -> str:
        """
        Crea el usuario o reutiliza el existente (dedupe por email).
        Devuelve el user_id.
        """
        email = email.strip().lower()

        if self.backend == "supabase":
            existing = (
                self._client.table("users").select("user_id")
                .eq("email", email).limit(1).execute()
            )
            if existing.data:
                return existing.data[0]["user_id"]
            user_id = _new_id()
            self._client.table("users").insert({
                "user_id": user_id, "name": name, "email": email,
                "whatsapp": whatsapp, "consent_accepted": consent,
                "created_at": _now(),
            }).execute()
            return user_id

        # --- CSV ---
        df = self._csv_read("users")
        if not df.empty and (df["email"] == email).any():
            return df.loc[df["email"] == email, "user_id"].iloc[0]
        user_id = _new_id()
        self._csv_append("users", {
            "user_id": user_id, "name": name, "email": email,
            "whatsapp": whatsapp or "", "consent_accepted": consent,
            "created_at": _now(),
        })
        return user_id

    # ------------------------------------------------------------------ #
    # ALERTS
    # ------------------------------------------------------------------ #
    def insert_alert(self, user_id: str, data: dict[str, Any]) -> str:
        """Inserta una alerta nueva en estado 'active'. Devuelve alert_id."""
        alert_id = _new_id()
        row = {
            "alert_id": alert_id,
            "user_id": user_id,
            "origin": data["origin"],
            "destination": data["destination"],
            "departure_date": str(data["departure_date"]),
            "return_date": str(data["return_date"]) if data.get("return_date") else "",
            "passengers": data.get("passengers", 1),
            "max_price": data["max_price"],
            "currency": data.get("currency", "USD"),
            "direct_only": data.get("direct_only", False),
            "accepts_connections": data.get("accepts_connections", True),
            "flexible_days": data.get("flexible_days", 0),
            "cabin": data.get("cabin", "economy"),
            "baggage_required": data.get("baggage_required", False),
            "status": "active",
            "created_at": _now(),
            "last_checked_at": "",
            "last_notified_at": "",
        }
        if self.backend == "supabase":
            self._client.table("alerts").insert(_supabase_row(row)).execute()
        else:
            self._csv_append("alerts", row)
        return alert_id

    def get_active_alerts(self) -> list[dict[str, Any]]:
        """Devuelve todas las alertas en estado 'active'."""
        if self.backend == "supabase":
            res = self._client.table("alerts").select("*").eq("status", "active").execute()
            return res.data or []
        df = self._csv_read("alerts")
        if df.empty:
            return []
        return df[df["status"] == "active"].to_dict("records")

    def get_all_alerts(self) -> list[dict[str, Any]]:
        if self.backend == "supabase":
            return self._client.table("alerts").select("*").execute().data or []
        return self._csv_read("alerts").to_dict("records")

    def touch_alert_checked(self, alert_id: str) -> None:
        """Actualiza last_checked_at al momento actual."""
        changes = {"last_checked_at": _now()}
        if self.backend == "supabase":
            self._client.table("alerts").update(changes).eq("alert_id", alert_id).execute()
        else:
            self._csv_update("alerts", "alert_id", alert_id, changes)

    def touch_alert_notified(self, alert_id: str) -> None:
        """Actualiza last_notified_at (clave para la logica anti-spam)."""
        changes = {"last_notified_at": _now()}
        if self.backend == "supabase":
            self._client.table("alerts").update(changes).eq("alert_id", alert_id).execute()
        else:
            self._csv_update("alerts", "alert_id", alert_id, changes)

    # ------------------------------------------------------------------ #
    # PRICE_HISTORY
    # ------------------------------------------------------------------ #
    def insert_price(self, alert_id: str, offer: dict[str, Any],
                     checked_at: str | None = None) -> str:
        """
        Registra una oferta observada en el historico de precios.

        checked_at es opcional: por defecto usa el momento actual. Se permite
        pasarlo explicitamente para sembrar historico de demo con fechas pasadas.
        """
        price_id = _new_id()
        row = {
            "price_id": price_id,
            "alert_id": alert_id,
            "checked_at": checked_at or _now(),
            "price": offer.get("price"),
            "currency": offer.get("currency", "USD"),
            "airline": offer.get("airline", ""),
            "departure_time": offer.get("departure_time", ""),
            "return_time": offer.get("return_time", ""),
            "stops": offer.get("stops", 0),
            "provider": offer.get("provider", "mock"),
            "booking_link": offer.get("booking_link", ""),
        }
        if self.backend == "supabase":
            self._client.table("price_history").insert(_supabase_row(row)).execute()
        else:
            self._csv_append("price_history", row)
        return price_id

    def get_price_history(self, alert_id: str | None = None) -> list[dict[str, Any]]:
        if self.backend == "supabase":
            q = self._client.table("price_history").select("*")
            if alert_id:
                q = q.eq("alert_id", alert_id)
            return q.execute().data or []
        df = self._csv_read("price_history")
        if df.empty:
            return []
        if alert_id:
            df = df[df["alert_id"] == alert_id]
        return df.to_dict("records")

    # ------------------------------------------------------------------ #
    # NOTIFICATIONS
    # ------------------------------------------------------------------ #
    def insert_notification(self, alert_id: str, channel: str, message: str,
                            status: str, price: float | None = None) -> str:
        """Registra una notificacion enviada (o fallida) para auditoria."""
        notification_id = _new_id()
        row = {
            "notification_id": notification_id,
            "alert_id": alert_id,
            "sent_at": _now(),
            "channel": channel,
            "message": message,
            "status": status,
            "price_at_notification": price if price is not None else "",
        }
        if self.backend == "supabase":
            self._client.table("notifications").insert(_supabase_row(row)).execute()
        else:
            self._csv_append("notifications", row)
        return notification_id

    def get_notifications(self) -> list[dict[str, Any]]:
        if self.backend == "supabase":
            return self._client.table("notifications").select("*").execute().data or []
        return self._csv_read("notifications").to_dict("records")
