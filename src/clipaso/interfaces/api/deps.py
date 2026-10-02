"""Dependencias de FastAPI: configuración, sesión de BD, almacenamiento y usuario actual."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from clipaso.domain.ports import Storage
from clipaso.infra.config import Settings
from clipaso.interfaces.api.auth import verify_token
from clipaso.saas import abuse, services
from clipaso.saas.db import utcnow
from clipaso.saas.dispatch import JobDispatcher
from clipaso.saas.errors import AppError
from clipaso.saas.models import User
from clipaso.saas.notifications import Notifier


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_storage(request: Request) -> Storage:
    return request.app.state.storage


def get_dispatcher(request: Request) -> JobDispatcher:
    return request.app.state.dispatcher


def get_notifier(request: Request) -> Notifier:
    return request.app.state.notifier


def get_session(request: Request) -> Iterator[Session]:
    session: Session = request.app.state.sessions()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


SettingsDep = Annotated[Settings, Depends(get_settings)]
StorageDep = Annotated[Storage, Depends(get_storage)]
SessionDep = Annotated[Session, Depends(get_session)]
DispatcherDep = Annotated[JobDispatcher, Depends(get_dispatcher)]
NotifierDep = Annotated[Notifier, Depends(get_notifier)]


def current_user(request: Request, session: SessionDep, settings: SettingsDep) -> User:
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise AppError("auth_required", 401)
    identity = verify_token(token.strip(), settings.auth)
    signup_ip = None
    if session.get(User, identity.subject) is None:  # cuenta nueva: filtros antiabuso (salvo desarrollo)
        signup_ip = abuse.ip_fingerprint(abuse.client_ip(request.headers, request.client and request.client.host),
                                         settings.api.secret_key)
        if not services.is_admin_email(identity.email, settings.admin_emails):
            abuse.check_signup(session, identity.email, signup_ip, settings.abuse, utcnow())
    user = services.get_or_create_user(session, identity.subject, identity.email, signup_ip=signup_ip)
    services.apply_admin(session, user, settings.admin_emails)
    return user


UserDep = Annotated[User, Depends(current_user)]


def optional_user(request: Request, session: SessionDep, settings: SettingsDep) -> User | None:
    """El usuario si la petición trae sesión (p. ej. el formulario de contacto, que también es público)."""
    if not request.headers.get("authorization"):
        return None
    return current_user(request, session, settings)


OptionalUserDep = Annotated[User | None, Depends(optional_user)]
