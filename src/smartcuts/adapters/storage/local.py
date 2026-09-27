"""Almacenamiento en disco para desarrollo.

Imita el comportamiento de R2: las URLs de subida y descarga van firmadas
(HMAC + caducidad) y las sirve la propia API en `/dev-storage/...`.
"""

from __future__ import annotations

import hashlib
import hmac
import shutil
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode

from smartcuts.domain.errors import ConfigurationError
from smartcuts.domain.ports import PresignedUpload
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

    def presign_upload(self, key: str, content_type: str, *, max_bytes: int, expires: int = 3600) -> PresignedUpload:
        key = safe_key(key)
        exp = int(time.time()) + expires
        params = {"exp": exp, "max": max_bytes, "sig": sign(self.secret, "PUT", key, exp, str(max_bytes))}
        return PresignedUpload(
            url=f"{self.base}/{quote(key)}?{urlencode(params)}",
            method="PUT",
            headers={"Content-Type": content_type},
        )

    def local_path(self, key: str) -> Path | None:
        return self._path(key)
