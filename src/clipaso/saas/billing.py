"""Cobros con Paddle Billing (Merchant of Record: Paddle cobra el IVA de cada país y factura al cliente).

Flujo:
- La web abre el pago de Paddle (Paddle.js) con el precio del plan y `custom_data.user_id`.
- Paddle avisa al webhook (`POST /billing/paddle/webhook`) de cada cambio de la suscripción y aquí se
  aplica: el plan del usuario sigue a la suscripción (activa → su plan; cancelada → Gratis).
- Con una suscripción activa, cambiar de plan o de periodo se hace por la API (con prorrateo) y la
  gestión (tarjeta, facturas, cancelar) en el portal del cliente de Paddle.
"""

from __future__ import annotations

import hashlib
import hmac
import time
from dataclasses import dataclass
from datetime import datetime

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from clipaso.infra.config import BillingSettings
from clipaso.infra.logging import get_logger
from clipaso.saas.errors import AppError
from clipaso.saas.models import User
from clipaso.saas.plans import DEFAULT_PLAN, DEV_PLAN

log = get_logger(__name__)

INTERVALS = ("month", "year")
PAID_PLANS = ("pro", "ultra")
# Estados en los que el usuario conserva su plan de pago (en past_due Paddle sigue reintentando el cobro).
KEEPS_PLAN = ("active", "trialing", "past_due")
SIGNATURE_TOLERANCE_S = 300


def enabled(settings: BillingSettings) -> bool:
    return settings.provider == "paddle" and bool(settings.paddle_prices)


def price_id(settings: BillingSettings, plan: str, interval: str) -> str | None:
    return settings.paddle_prices.get(f"{plan}_{interval}")


def plan_for_price(settings: BillingSettings, price: str) -> tuple[str, str] | None:
    for key, value in settings.paddle_prices.items():
        if value == price and "_" in key:
            plan, interval = key.rsplit("_", 1)
            return plan, interval
    return None


def verify_signature(header: str, body: bytes, secret: str, now: float | None = None) -> bool:
    """Cabecera `Paddle-Signature: ts=…;h1=…`: HMAC-SHA256 de `ts:cuerpo` con el secreto del webhook."""
    if not header or not secret:
        return False
    parts = dict(p.split("=", 1) for p in header.split(";") if "=" in p)
    ts, signature = parts.get("ts", ""), parts.get("h1", "")
    if not ts.isdigit() or not signature:
        return False
    if abs((now if now is not None else time.time()) - int(ts)) > SIGNATURE_TOLERANCE_S:
        return False  # evita reenviar una notificación antigua capturada
    expected = hmac.new(secret.encode(), f"{ts}:".encode() + body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def _dt(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None


def _find_user(session: Session, data: dict) -> User | None:
    user_id = (data.get("custom_data") or {}).get("user_id")
    if user_id and (user := session.get(User, user_id)):
        return user
    for column, value in ((User.billing_subscription_id, data.get("id")),
                          (User.billing_customer_id, data.get("customer_id"))):
        if value and (user := session.scalars(select(User).where(column == value)).first()):
            return user
    return None


def apply_subscription(session: Session, settings: BillingSettings, data: dict, occurred_at: datetime) -> User | None:
    """Aplica el estado de una suscripción de Paddle (evento `subscription.*` o respuesta de su API)."""
    user = _find_user(session, data)
    if user is None:
        log.warning("billing.unknown_user", subscription=data.get("id"), customer=data.get("customer_id"))
        return None
    if user.billing_event_at and occurred_at < user.billing_event_at:
        return user  # Paddle no garantiza el orden: un evento más antiguo no deshace uno nuevo
    if (user.billing_subscription_id and data.get("id") != user.billing_subscription_id
            and user.billing_status in KEEPS_PLAN and data.get("status") not in KEEPS_PLAN):
        return user  # el fin de una suscripción vieja no quita el plan de la nueva
    items = data.get("items") or []
    match = plan_for_price(settings, ((items[0].get("price") or {}).get("id")) if items else "")
    status = data.get("status")
    scheduled = data.get("scheduled_change") or {}
    user.billing_customer_id = data.get("customer_id") or user.billing_customer_id
    user.billing_subscription_id = data.get("id")
    user.billing_status = status
    user.billing_interval = match[1] if match else None
    user.billing_renews_at = _dt(data.get("next_billed_at"))
    user.billing_cancels_at = _dt(scheduled.get("effective_at")) if scheduled.get("action") == "cancel" else None
    user.billing_event_at = occurred_at
    if user.plan_code != DEV_PLAN:  # la cuenta de desarrollo nunca cambia de plan
        plan = match[0] if match and status in KEEPS_PLAN else DEFAULT_PLAN
        if plan != user.plan_code:
            log.info("billing.plan_changed", user_id=user.id, plan=plan, status=status)
        user.plan_code = plan
        session.flush()
        session.expire(user, ["plan"])
    return user


def handle_event(session: Session, settings: BillingSettings, event: dict) -> None:
    kind = event.get("event_type", "")
    if kind.startswith("subscription."):
        occurred = _dt(event.get("occurred_at")) or datetime.now().astimezone()
        apply_subscription(session, settings, event.get("data") or {}, occurred)


# --------------------------------------------------------------------------- API de Paddle


@dataclass
class Paddle:
    settings: BillingSettings

    @property
    def base(self) -> str:
        return "https://api.paddle.com" if self.settings.paddle_environment == "production" \
            else "https://sandbox-api.paddle.com"

    def _call(self, method: str, path: str, json: dict | None = None) -> dict:
        if not self.settings.paddle_api_key:
            raise AppError("billing_unavailable", 503)
        try:
            r = httpx.request(method, self.base + path, json=json, timeout=20,
                              headers={"Authorization": f"Bearer {self.settings.paddle_api_key}"})
        except httpx.HTTPError as exc:
            raise AppError("billing_unavailable", 503, detail=str(exc)) from exc
        if r.status_code >= 400:
            raise AppError("billing_unavailable", 502, detail=f"{r.status_code} {r.text[:300]}")
        return r.json().get("data") or {}

    def portal_url(self, customer_id: str, subscription_id: str | None) -> str:
        body = {"subscription_ids": [subscription_id]} if subscription_id else {}
        urls = self._call("POST", f"/customers/{customer_id}/portal-sessions", body).get("urls") or {}
        return (urls.get("general") or {}).get("overview", "")

    def change_price(self, subscription_id: str, price: str) -> dict:
        return self._call("PATCH", f"/subscriptions/{subscription_id}", {
            "items": [{"price_id": price, "quantity": 1}],
            "proration_billing_mode": "prorated_immediately",  # cobra o abona la diferencia al momento
        })

    def cancel_now(self, subscription_id: str) -> None:
        self._call("POST", f"/subscriptions/{subscription_id}/cancel", {"effective_from": "immediately"})


def has_active_subscription(user: User) -> bool:
    return bool(user.billing_subscription_id) and user.billing_status in KEEPS_PLAN


def change_plan(session: Session, settings: BillingSettings, user: User, plan: str, interval: str) -> None:
    """Cambia el plan o el periodo de una suscripción activa (el pago nuevo lo abre la web con Paddle.js)."""
    if plan not in PAID_PLANS or interval not in INTERVALS:
        raise AppError("validation_error")
    price = price_id(settings, plan, interval)
    if not enabled(settings) or not price:
        raise AppError("billing_unavailable", 503)
    if not has_active_subscription(user):
        raise AppError("validation_error", 409, key="no_subscription")
    data = Paddle(settings).change_price(user.billing_subscription_id, price)
    apply_subscription(session, settings, data, datetime.now().astimezone())


def cancel_for_deletion(settings: BillingSettings, user: User) -> None:
    """Al borrar la cuenta se cancela la suscripción al momento: no se puede seguir cobrando a nadie."""
    if has_active_subscription(user):
        Paddle(settings).cancel_now(user.billing_subscription_id)
