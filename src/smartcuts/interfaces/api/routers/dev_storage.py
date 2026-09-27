"""Sirve el almacenamiento local en desarrollo imitando las URLs firmadas de R2.

Solo se monta cuando `storage.backend == "local"`; en producción los ficheros
van directamente entre el navegador y R2.
"""

from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Query, Request
from fastapi.responses import FileResponse, Response

from smartcuts.adapters.storage.local import LocalStorage, safe_key, verify
from smartcuts.interfaces.api.deps import SettingsDep, StorageDep
from smartcuts.saas.errors import AppError

router = APIRouter(prefix="/dev-storage", tags=["dev"], include_in_schema=False)

CHUNK = 1024 * 1024


@router.put("/{key:path}")
async def put_object(
    key: str, request: Request, storage: StorageDep, settings: SettingsDep,
    exp: int = Query(...), max: int = Query(...), sig: str = Query(...),
) -> Response:
    if not isinstance(storage, LocalStorage) or not verify(settings.api.secret_key, "PUT", key, exp, sig, str(max)):
        raise AppError("auth_required", 403)
    path = storage.local_path(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".part")
    written = 0
    with tmp.open("wb") as f:
        async for chunk in request.stream():
            written += len(chunk)
            if written > max:
                f.close()
                tmp.unlink(missing_ok=True)
                raise AppError("upload_too_large", 413)
            f.write(chunk)
    tmp.replace(path)
    return Response(status_code=200)


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
