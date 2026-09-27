"""Subida directa navegador → almacenamiento.

1. `POST /uploads` valida tipo y tamaño contra el plan y devuelve una URL firmada.
2. El navegador sube el fichero a esa URL (R2 en producción) con progreso.
3. `POST /uploads/{id}/complete` comprueba el fichero y lee su duración.
"""

from __future__ import annotations

from fastapi import APIRouter

from smartcuts.interfaces.api.deps import SessionDep, SettingsDep, StorageDep, UserDep
from smartcuts.interfaces.api.schemas import UploadCreateIn, UploadCreateOut, UploadOut, UploadTarget
from smartcuts.saas import services
from smartcuts.saas.models import Upload

router = APIRouter(prefix="/uploads", tags=["uploads"])


def to_out(upload: Upload) -> UploadOut:
    return UploadOut(
        id=upload.id, filename=upload.filename, status=upload.status, size_bytes=upload.size_bytes,
        duration_seconds=upload.duration_seconds,
        billable_minutes=services.billable_minutes(upload.duration_seconds) if upload.duration_seconds else None,
    )


@router.post("", response_model=UploadCreateOut, status_code=201)
def create_upload(body: UploadCreateIn, user: UserDep, session: SessionDep, storage: StorageDep) -> UploadCreateOut:
    upload, target = services.create_upload(
        session, storage, user, filename=body.filename, size_bytes=body.size_bytes, content_type=body.content_type
    )
    return UploadCreateOut(
        upload_id=upload.id, target=UploadTarget(url=target.url, method=target.method, headers=target.headers)
    )


@router.post("/{upload_id}/complete", response_model=UploadOut)
def complete_upload(
    upload_id: str, user: UserDep, session: SessionDep, storage: StorageDep, settings: SettingsDep
) -> UploadOut:
    upload = services.complete_upload(
        session, storage, user, upload_id, signed_ttl=settings.api.signed_url_ttl_seconds
    )
    return to_out(upload)
