"""Almacenamiento en disco para desarrollo.

Imita el comportamiento de R2: las URLs de subida y descarga van firmadas
(HMAC + caducidad) y las sirve la propia API en `/dev-storage/...`. Las subidas
multiparte guardan cada parte en `.multipart/<id>/` y se unen al completar.
"""

from __future__ import annotations

import hashlib
import hmac
import shutil
import time
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode

from smartcuts.domain.errors import ConfigurationError
from smartcuts.domain.ports import UploadedPart
from smartcuts.infra.registry import register


def sign(secret: str, method: str, key: str, expires_at: int, extra: str = "") -> str:
    msg = f"{method}\n{key}\n{expires_at}\n{extra}".encode()
    return hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()


def verify(secret: str, method: str, key: str, expires_at: int, signature: str, extra: str = "") -> bool:
    if expires_at < time.time():
        return False
    return hmac.compare_digest(sign(secret, method, key, expires_at, extra), signature)


def safe_key(key: str) -> str:
    parts = [p for p in key.replace("\\", "/").split("/") if p]
    if not parts or any(p in (".", "..") for p in parts):
        raise ConfigurationError(f"Clave de almacenamiento no válida: {key!r}")
    return "/".join(parts)


@register("storage", "local")
class LocalStorage:
    name = "local"

    def __init__(self, root: Path, public_url: str, secret_key: str, **_: Any) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.base = public_url.rstrip("/") + "/dev-storage"
        self.secret = secret_key

    def _path(self, key: str) -> Path:
        return self.root / safe_key(key)

    def put_file(self, key: str, path: Path, content_type: str) -> None:
        dest = self._path(key)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, dest)

    def put_bytes(self, key: str, data: bytes, content_type: str) -> None:
        dest = self._path(key)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)

    def read_bytes(self, key: str) -> bytes | None:
        p = self._path(key)
        return p.read_bytes() if p.is_file() else None

    def download_to(self, key: str, dest: Path) -> Path:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(self._path(key), dest)
        return dest

    def size(self, key: str) -> int | None:
        p = self._path(key)
        return p.stat().st_size if p.is_file() else None

    def delete_prefix(self, prefix: str) -> int:
        target = self._path(prefix)
        if target.is_file():
            target.unlink()
            return 1
        if not target.is_dir():
            return 0
        count = sum(1 for p in target.rglob("*") if p.is_file())
        shutil.rmtree(target)
        return count

    def signed_url(self, key: str, *, expires: int = 3600, download_name: str | None = None) -> str:
        key = safe_key(key)
        exp = int(time.time()) + expires
        dl = download_name or ""
        params = {"exp": exp, "sig": sign(self.secret, "GET", key, exp, dl)}
        if dl:
            params["dl"] = dl
        return f"{self.base}/{quote(key)}?{urlencode(params)}"

    def local_path(self, key: str) -> Path | None:
        return self._path(key)

    # --- subida multiparte -------------------------------------------------------------

    def _parts_dir(self, upload_id: str) -> Path:
        if not upload_id.isalnum():
            raise ConfigurationError("Identificador de subida no válido")
        return self.root / ".multipart" / upload_id

    def part_path(self, upload_id: str, part_number: int) -> Path:
        return self._parts_dir(upload_id) / f"{part_number:05d}.part"

    def create_multipart(self, key: str, content_type: str) -> str:
        upload_id = uuid.uuid4().hex
        self._parts_dir(upload_id).mkdir(parents=True)
        (self._parts_dir(upload_id) / "key").write_text(safe_key(key), encoding="utf-8")
        return upload_id

    def presign_part(self, key: str, upload_id: str, part_number: int, *, max_bytes: int, expires: int = 3600) -> str:
        exp = int(time.time()) + expires
        ref = f"{upload_id}/{part_number}"
        params = {"exp": exp, "max": max_bytes, "sig": sign(self.secret, "PART", ref, exp, str(max_bytes))}
        return f"{self.base}/_parts/{ref}?{urlencode(params)}"

    def list_parts(self, key: str, upload_id: str) -> list[UploadedPart]:
        folder = self._parts_dir(upload_id)
        if not folder.is_dir():
            return []
        return [
            UploadedPart(int(f.stem), f'"{hashlib.md5(f.read_bytes()).hexdigest()}"', f.stat().st_size)
            for f in sorted(folder.glob("*.part"))
        ]

    def complete_multipart(self, key: str, upload_id: str, parts: list[UploadedPart]) -> None:
        stored = {p.part_number: p for p in self.list_parts(key, upload_id)}
        dest = self._path(key)
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open("wb") as out:
            for part in sorted(parts, key=lambda p: p.part_number):
                have = stored.get(part.part_number)
                if have is None or have.etag.strip('"') != part.etag.strip('"'):
                    out.close()
                    dest.unlink(missing_ok=True)
                    raise ConfigurationError(f"La parte {part.part_number} no coincide con la subida")
                with self.part_path(upload_id, part.part_number).open("rb") as src:
                    shutil.copyfileobj(src, out, 8 * 1024 * 1024)
        shutil.rmtree(self._parts_dir(upload_id), ignore_errors=True)

    def abort_multipart(self, key: str, upload_id: str) -> None:
        shutil.rmtree(self._parts_dir(upload_id), ignore_errors=True)
