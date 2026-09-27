"""Dependencias de FastAPI: configuración, sesión de BD, almacenamiento y usuario actual."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from smartcuts.domain.ports import Storage
from smartcuts.infra.config import Settings
from smartcuts.interfaces.api.auth import verify_token
from smartcuts.saas import services
from smartcuts.saas.dispatch import JobDispatcher
from smartcuts.saas.errors import AppError
from smartcuts.saas.models import User


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_storage(request: Request) -> Storage:
    return request.app.state.storage


def get_dispatcher(request: Request) -> JobDispatcher:
    return request.app.state.dispatcher


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


def current_user(request: Request, session: SessionDep, settings: SettingsDep) -> User:
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise AppError("auth_required", 401)
    identity = verify_token(token.strip(), settings.auth)
    return services.get_or_create_user(session, identity.subject, identity.email)


UserDep = Annotated[User, Depends(current_user)]
