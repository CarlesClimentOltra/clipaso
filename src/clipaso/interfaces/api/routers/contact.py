"""Formulario de contacto (público: también para quien aún no tiene cuenta)."""

from __future__ import annotations

from fastapi import APIRouter, Request, Response

from clipaso.interfaces.api.deps import NotifierDep, OptionalUserDep, SessionDep, SettingsDep, StorageDep
from clipaso.interfaces.api.schemas import ContactIn
from clipaso.saas import abuse, support
from clipaso.saas.db import utcnow
from clipaso.saas.errors import request_lang

router = APIRouter(tags=["contact"])


@router.post("/contact", status_code=204)
def contact(body: ContactIn, request: Request, user: OptionalUserDep, session: SessionDep, storage: StorageDep,
            notifier: NotifierDep, settings: SettingsDep) -> Response:
    if body.website:  # campo trampa invisible: solo lo rellenan los bots
        return Response(status_code=204)
    ip_hash = abuse.ip_fingerprint(abuse.client_ip(request.headers, request.client and request.client.host),
                                   settings.api.secret_key)
    support.create_message(
        session, storage, notifier, settings.notifications, user=user, email=body.email, kind=body.kind,
        message=body.message, context=body.context, attachment=body.attachment, ip_hash=ip_hash,
        lang=request_lang.get(), now=utcnow(),
    )
    return Response(status_code=204)
