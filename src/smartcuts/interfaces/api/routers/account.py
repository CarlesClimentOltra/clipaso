from __future__ import annotations

from fastapi import APIRouter, Request, Response
from sqlalchemy import select

from smartcuts.interfaces.api.auth import delete_identity
from smartcuts.interfaces.api.deps import SessionDep, SettingsDep, StorageDep, UserDep
from smartcuts.interfaces.api.schemas import (
    MeOut,
    OptionItem,
    OptionsOut,
    PlanOut,
    PreferencesIn,
    PreferencesOut,
    UsageOut,
)
from smartcuts.saas import editing, services
from smartcuts.saas.artifacts import logo_key
from smartcuts.saas.db import utcnow
from smartcuts.saas.errors import AppError
from smartcuts.saas.models import Plan, User
from smartcuts.saas.presets import DURATIONS, FONTS, FORMATS, PRESETS

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


@router.get("/options", response_model=OptionsOut)
def clip_options() -> OptionsOut:
    """Formatos, duraciones y estilos de subtítulos disponibles (los pinta la web)."""
    return OptionsOut(
        formats=[OptionItem(id=k, label=v["label"], hint=v["hint"]) for k, v in FORMATS.items()],
        durations=[OptionItem(id=k, label=v["label"], hint=v["hint"]) for k, v in DURATIONS.items()],
        presets=PRESETS,
        fonts=list(FONTS),
    )


def _preferences_out(user: User, storage, ttl: int) -> PreferencesOut:
    style, branding = editing.get_preferences(user)
    logo_url = storage.signed_url(logo_key(user.id), expires=ttl) if branding.has_logo else None
    return PreferencesOut(caption_style=style, branding=branding, logo_url=logo_url)


@router.get("/me/preferences", response_model=PreferencesOut)
def get_preferences(user: UserDep, storage: StorageDep, settings: SettingsDep) -> PreferencesOut:
    return _preferences_out(user, storage, settings.api.signed_url_ttl_seconds)


@router.put("/me/preferences", response_model=PreferencesOut)
def put_preferences(body: PreferencesIn, user: UserDep, storage: StorageDep, settings: SettingsDep) -> PreferencesOut:
    """Estilo de subtítulos por defecto y marca personal para los próximos vídeos."""
    editing.save_preferences(user, body.caption_style, body.branding)
    return _preferences_out(user, storage, settings.api.signed_url_ttl_seconds)


@router.put(
    "/me/logo", response_model=PreferencesOut,
    openapi_extra={"requestBody": {"content": {"image/png": {"schema": {"type": "string", "format": "binary"}},
                                                "image/jpeg": {"schema": {"type": "string", "format": "binary"}}},
                                   "required": True}},
)
async def put_logo(request: Request, user: UserDep, storage: StorageDep, settings: SettingsDep) -> PreferencesOut:
    """Sube el logo (PNG o JPG, máx. 1 MB) como cuerpo de la petición."""
    if int(request.headers.get("content-length") or 0) > editing.LOGO_MAX_BYTES:
        raise AppError("validation_error", 413, message="El logo debe ocupar 1 MB como máximo.")
    editing.save_logo(storage, user, await request.body())
    return _preferences_out(user, storage, settings.api.signed_url_ttl_seconds)


@router.delete("/me/logo", response_model=PreferencesOut)
def remove_logo(user: UserDep, storage: StorageDep, settings: SettingsDep) -> PreferencesOut:
    editing.delete_logo(storage, user)
    return _preferences_out(user, storage, settings.api.signed_url_ttl_seconds)
