"""Sirve el almacenamiento local en desarrollo imitando las URLs firmadas de R2.

Solo se monta cuando `storage.backend == "local"`; en producción los ficheros
van directamente entre el navegador y R2.
"""

from __future__ import annotations

import hashlib
from urllib.parse import quote

from fastapi import APIRouter, Query, Request
from fastapi.responses import FileResponse, Response

from clipaso.adapters.storage.local import LocalStorage, safe_key, verify
from clipaso.interfaces.api.deps import SettingsDep, StorageDep
from clipaso.saas.errors import AppError

router = APIRouter(prefix="/dev-storage", tags=["dev"], include_in_schema=False)

CHUNK = 1024 * 1024


@router.put("/_parts/{upload_id}/{part_number}")
async def put_part(
    upload_id: str, part_number: int, request: Request, storage: StorageDep, settings: SettingsDep,
    exp: int = Query(...), max: int = Query(...), sig: str = Query(...),
) -> Response:
    """Recibe una parte de una subida multiparte (equivalente a UploadPart de S3/R2)."""
    ref = f"{upload_id}/{part_number}"
    if not isinstance(storage, LocalStorage) or not verify(settings.api.secret_key, "PART", ref, exp, sig, str(max)):
        raise AppError("auth_required", 403)
    path = storage.part_path(upload_id, part_number)
    if not path.parent.is_dir():
        raise AppError("upload_incomplete", 404)
    tmp = path.with_suffix(".tmp")
    digest = hashlib.md5()
    written = 0
    with tmp.open("wb") as f:
        async for chunk in request.stream():
            written += len(chunk)
            if written > max:
                f.close()
                tmp.unlink(missing_ok=True)
                raise AppError("upload_too_large", 413)
            digest.update(chunk)
            f.write(chunk)
    tmp.replace(path)
    return Response(status_code=200, headers={"ETag": f'"{digest.hexdigest()}"'})


@router.get("/{key:path}")
def get_object(
    key: str, storage: StorageDep, settings: SettingsDep,
    exp: int = Query(...), sig: str = Query(...), dl: str = Query(""),
) -> FileResponse:
    if not isinstance(storage, LocalStorage) or not verify(settings.api.secret_key, "GET", key, exp, sig, dl):
        raise AppError("auth_required", 403)
    path = storage.local_path(safe_key(key))
    if path is None or not path.is_file():
        raise AppError("not_found", 404)
    media = "video/mp4" if path.suffix == ".mp4" else "image/jpeg" if path.suffix == ".jpg" else None
    headers = {"Content-Disposition": f"attachment; filename*=UTF-8''{quote(dl)}"} if dl else None
    return FileResponse(path, media_type=media, headers=headers)
