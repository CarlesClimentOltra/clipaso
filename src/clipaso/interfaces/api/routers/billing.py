"""Cobros con Paddle: configuración para la web, webhook, portal del cliente y cambio de plan."""

from __future__ import annotations

import json

from fastapi import APIRouter, Request, Response

from clipaso.interfaces.api.deps import SessionDep, SettingsDep, UserDep
from clipaso.interfaces.api.schemas import BillingConfigOut, ChangePlanIn, PortalOut
from clipaso.saas import billing
from clipaso.saas.errors import AppError

router = APIRouter(prefix="/billing", tags=["billing"])


@router.get("/config", response_model=BillingConfigOut)
def config(settings: SettingsDep) -> BillingConfigOut:
    """Lo que necesita Paddle.js en la web (todo público: token de cliente e ids de precio)."""
    b = settings.billing
    return BillingConfigOut(enabled=billing.enabled(b), environment=b.paddle_environment,
                            client_token=b.paddle_client_token, prices=b.paddle_prices)


@router.post("/paddle/webhook", status_code=200, include_in_schema=False)
async def paddle_webhook(request: Request, session: SessionDep, settings: SettingsDep) -> Response:
    body = await request.body()
    if not billing.verify_signature(request.headers.get("paddle-signature", ""), body,
                                    settings.billing.paddle_webhook_secret):
        raise AppError("auth_required", 401)
    billing.handle_event(session, settings.billing, json.loads(body))
    return Response(status_code=200)


@router.post("/portal", response_model=PortalOut)
def portal(user: UserDep, settings: SettingsDep) -> PortalOut:
    """Enlace al portal de Paddle: tarjeta, facturas y cancelar la suscripción."""
    if not user.billing_customer_id:
        raise AppError("validation_error", 409, key="no_subscription")
    return PortalOut(url=billing.Paddle(settings.billing).portal_url(user.billing_customer_id,
                                                                      user.billing_subscription_id))


@router.post("/change-plan", status_code=204)
def change_plan(body: ChangePlanIn, user: UserDep, session: SessionDep, settings: SettingsDep) -> Response:
    billing.change_plan(session, settings.billing, user, body.plan, body.interval)
    return Response(status_code=204)
