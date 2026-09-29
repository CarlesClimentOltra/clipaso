"""Fuente de archivo local: el vídeo no se copia, se lee in situ."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from clipaso.domain.errors import SourceUnavailableError
from clipaso.domain.models import SourceVideo
from clipaso.infra import ffmpeg
from clipaso.infra.registry import register

VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}
_CHUNK = 4 * 1024 * 1024


def _as_path(uri: str) -> Path:
    return Path(uri.removeprefix("file://")).expanduser().resolve()


@register("sources", "local")
class LocalFileSource:
    name = "local"

    def __init__(self, **_: Any) -> None:
        pass

    def can_handle(self, uri: str) -> bool:
        path = _as_path(uri)
        return path.suffix.lower() in VIDEO_EXTENSIONS and path.is_file()

    def source_id(self, uri: str) -> str:
        """Huella del contenido (tamaño + primeros y últimos 4 MB): mismo vídeo ⇒ mismo id,
        aunque lo suban usuarios distintos o cambie de nombre. Barato incluso para ficheros grandes."""
        path = _as_path(uri)
        size = path.stat().st_size
        h = hashlib.sha256(str(size).encode())
        with path.open("rb") as f:
            h.update(f.read(_CHUNK))
            if size > 2 * _CHUNK:
                f.seek(-_CHUNK, 2)
                h.update(f.read(_CHUNK))
        return f"file-{h.hexdigest()[:20]}"

    def fetch(self, uri: str, dest_dir: Path) -> SourceVideo:
        path = _as_path(uri)
        if not path.is_file():
            raise SourceUnavailableError(f"No existe el archivo {path}")
        width, height, fps, duration = ffmpeg.video_info(path)
        return SourceVideo(
            source_id=self.source_id(uri),
            provider=self.name,
            uri=str(path),
            path=path,
            title=path.stem,
            duration=duration,
            width=width,
            height=height,
            fps=fps,
        )
