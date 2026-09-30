"""Subida directa navegador → almacenamiento, por partes y reanudable.

1. `POST /uploads` valida tipo y tamaño contra el plan e inicia la subida por partes.
2. `POST /uploads/{id}/parts` devuelve URLs firmadas para subir cada parte (a R2 en producción).
3. `GET /uploads/{id}/parts` lista las partes ya subidas: permite reanudar tras un corte.
4. `POST /uploads/{id}/complete` une las partes, comprueba el fichero y lee su duración.
5. `DELETE /uploads/{id}` cancela una subida en curso.
"""

from __future__ import annotations

from fastapi import APIRouter, Response

from clipaso.domain.ports import UploadedPart
from clipaso.interfaces.api.deps import SessionDep, SettingsDep, StorageDep, UserDep
from clipaso.interfaces.api.schemas import (
    PartUrl,
    PartUrlsIn,
    PartUrlsOut,
    UploadCompleteIn,
    UploadCreateIn,
    UploadCreateOut,
    UploadedPartOut,
    UploadedPartsOut,
    UploadOut,
)
from clipaso.saas import services
from clipaso.saas.models import Upload

router = APIRouter(prefix="/uploads", tags=["uploads"])


def to_out(upload: Upload) -> UploadOut:
    return UploadOut(
        id=upload.id, filename=upload.filename, status=upload.status, size_bytes=upload.size_bytes,
        duration_seconds=upload.duration_seconds,
        billable_minutes=services.billable_minutes(upload.duration_seconds) * services.minutes_factor(upload)
        if upload.duration_seconds else None,
    )


@router.post("", response_model=UploadCreateOut, status_code=201)
def create_upload(body: UploadCreateIn, user: UserDep, session: SessionDep, storage: StorageDep) -> UploadCreateOut:
    upload = services.create_upload(
        session, storage, user, filename=body.filename, size_bytes=body.size_bytes, content_type=body.content_type
    )
    return UploadCreateOut(upload_id=upload.id, part_size=upload.part_size, part_count=services.part_count(upload))


@router.post("/{upload_id}/parts", response_model=PartUrlsOut)
def part_urls(
    upload_id: str, body: PartUrlsIn, user: UserDep, session: SessionDep, storage: StorageDep, settings: SettingsDep
) -> PartUrlsOut:
    urls = services.presign_parts(
        session, storage, user, upload_id, body.part_numbers, ttl=settings.api.signed_url_ttl_seconds
    )
    return PartUrlsOut(urls=[PartUrl(part_number=n, url=u) for n, u in urls.items()])


@router.get("/{upload_id}/parts", response_model=UploadedPartsOut)
def list_parts(upload_id: str, user: UserDep, session: SessionDep, storage: StorageDep) -> UploadedPartsOut:
    parts = services.uploaded_parts(session, storage, user, upload_id)
    return UploadedPartsOut(
        parts=[UploadedPartOut(part_number=p.part_number, etag=p.etag, size=p.size) for p in parts]
    )


@router.post("/{upload_id}/complete", response_model=UploadOut)
def complete_upload(
    upload_id: str, body: UploadCompleteIn, user: UserDep, session: SessionDep, storage: StorageDep,
    settings: SettingsDep,
) -> UploadOut:
    parts = [UploadedPart(p.part_number, p.etag) for p in body.parts]
    upload = services.complete_upload(
        session, storage, user, upload_id, parts, signed_ttl=settings.api.signed_url_ttl_seconds
    )
    return to_out(upload)


@router.delete("/{upload_id}", status_code=204)
def abort_upload(upload_id: str, user: UserDep, session: SessionDep, storage: StorageDep) -> Response:
    services.abort_upload(session, storage, user, upload_id)
    return Response(status_code=204)
