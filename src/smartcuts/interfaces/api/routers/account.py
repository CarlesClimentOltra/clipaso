from __future__ import annotations

from fastapi import APIRouter, Response
from sqlalchemy import select

from smartcuts.interfaces.api.auth import delete_identity
from smartcuts.interfaces.api.deps import SessionDep, SettingsDep, StorageDep, UserDep
from smartcuts.interfaces.api.schemas import MeOut, PlanOut, UsageOut
from smartcuts.saas import services
from smartcuts.saas.db import utcnow
from smartcuts.saas.models import Plan

router = APIRouter(tags=["account"])


@router.get("/plans", response_model=list[PlanOut])
def list_plans(session: SessionDep) -> list[Plan]:
    """Planes públicos (página de precios)."""
    return list(session.scalars(select(Plan).where(Plan.is_public).order_by(Plan.sort_order)))


@router.get("/me", response_model=MeOut)
def me(user: UserDep, session: SessionDep) -> MeOut:
    usage = services.usage_for(session, user, utcnow())
    return MeOut(
        id=user.id,
        email=user.email,
        plan=PlanOut.model_validate(user.plan, from_attributes=True),
        usage=UsageOut(period=usage.period, used_minutes=usage.used_minutes,
                       limit_minutes=usage.limit_minutes, remaining_minutes=usage.remaining_minutes),
    )


@router.delete("/me", status_code=204)
def delete_me(user: UserDep, session: SessionDep, storage: StorageDep, settings: SettingsDep) -> Response:
    """Elimina la cuenta: vídeos, clips, historial y consumo, y después el usuario de Supabase Auth."""
    subject = user.id
    services.delete_account(session, storage, user)
    session.commit()  # los datos primero: si falla Supabase, se puede reintentar
    delete_identity(subject, settings.auth)
    return Response(status_code=204)
