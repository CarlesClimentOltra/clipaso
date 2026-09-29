"""Puertos (interfaces) del dominio.

El pipeline solo conoce estos contratos. Cada implementación concreta vive en
`clipaso.adapters` y se registra por nombre en `clipaso.infra.registry`,
de modo que añadir una fuente, un transcriptor o una estrategia nueva no
requiere tocar el core.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from clipaso.domain.models import (
    Branding,
    ClipCandidate,
    OutputProfile,
    Selection,
    Signal,
    SignalSet,
    SourceVideo,
    Transcript,
)


@runtime_checkable
class VideoSource(Protocol):
    """Obtiene un vídeo (URL, ruta…) y lo deja en disco."""

    name: str

    def can_handle(self, uri: str) -> bool: ...

    def source_id(self, uri: str) -> str:
        """Id estable y barato de calcular (sin descargar) para la caché."""
        ...

    def fetch(self, uri: str, dest_dir: Path) -> SourceVideo: ...


@runtime_checkable
class Transcriber(Protocol):
    name: str

    def transcribe(
        self, audio_path: Path, language: str | None, on_progress: Callable[[float], None] | None = None
    ) -> Transcript: ...


@dataclass
class AnalysisContext:
    """Todo lo que un extractor de señales puede necesitar."""

    source: SourceVideo
    audio_path: Path
    transcript: Transcript


@runtime_checkable
class SignalExtractor(Protocol):
    name: str

    def extract(self, ctx: AnalysisContext) -> Signal | None:
        """Devuelve None si la señal no está disponible para este vídeo."""
        ...


@dataclass
class SelectionRequest:
    source: SourceVideo
    transcript: Transcript
    signals: SignalSet
    profile: OutputProfile
    max_clips: int
    language: str = "es"
    # topic: tema pedido por el usuario; exclude: [(inicio, fin)] de clips ya existentes.
    extra: dict[str, Any] = field(default_factory=dict)

    def excluded_ranges(self) -> list[tuple[float, float]]:
        return [(float(a), float(b)) for a, b in self.extra.get("exclude", [])]


@runtime_checkable
class ClipSelector(Protocol):
    """Motor de "inteligencia": decide qué fragmentos merecen ser clip."""

    name: str

    def select(self, request: SelectionRequest) -> Selection: ...


@dataclass
class LLMUsage:
    model: str
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    billable: bool = True  # False si va contra una suscripción (sin coste por uso)


@dataclass
class LLMResponse:
    data: dict[str, Any]
    usage: LLMUsage
    request_id: str | None = None


@runtime_checkable
class LLMClient(Protocol):
    """Cliente LLM agnóstico del proveedor, orientado a salidas JSON."""

    name: str
    model: str
    billable: bool

    def complete_json(
        self, *, system: str, user: str, schema: dict[str, Any], max_tokens: int = 16000
    ) -> LLMResponse: ...

    def estimate_input_tokens(self, text: str) -> int: ...


@dataclass
class ReframePlan:
    """Cómo convertir el encuadre original al del perfil.

    `filter_complex` recibe el vídeo en `[0:v]` y debe producir `[vout]`.
    `sendcmd` es el contenido opcional de un fichero de comandos de ffmpeg
    (movimientos de cámara a lo largo del clip).
    """

    mode: str
    filter_complex: str
    sendcmd: str | None = None
    notes: list[str] = field(default_factory=list)


@runtime_checkable
class Reframer(Protocol):
    name: str

    def plan(self, source: SourceVideo, clip: ClipCandidate, profile: OutputProfile) -> ReframePlan: ...


@dataclass
class ExportRequest:
    source: SourceVideo
    clip: ClipCandidate
    rank: int
    profile: OutputProfile
    reframe: ReframePlan
    transcript: Transcript
    output_path: Path
    work_dir: Path
    branding: Branding | None = None


@runtime_checkable
class Exporter(Protocol):
    name: str

    def export(self, request: ExportRequest) -> Path: ...


@dataclass(frozen=True)
class UploadedPart:
    part_number: int
    etag: str
    size: int = 0


@runtime_checkable
class Storage(Protocol):
    """Almacenamiento de ficheros por clave (`uploads/<user>/<id>.mp4`, `clips/...`).

    Las subidas del navegador usan el protocolo multiparte de S3: el fichero se trocea,
    cada trozo va directo al almacenamiento con su URL firmada y, si algo falla, solo
    se repiten los trozos que faltan (subida reanudable).
    """

    name: str

    def put_file(self, key: str, path: Path, content_type: str) -> None: ...

    def put_bytes(self, key: str, data: bytes, content_type: str) -> None: ...

    def read_bytes(self, key: str) -> bytes | None:
        """Contenido de un objeto pequeño (JSON, imágenes), o None si no existe."""
        ...

    def download_to(self, key: str, dest: Path) -> Path: ...

    def iter_bytes(self, key: str, chunk_size: int = 1024 * 1024) -> Iterator[bytes]:
        """Lee un objeto por trozos (descargas en streaming sin cargarlo en memoria)."""
        ...

    def size(self, key: str) -> int | None:
        """Tamaño en bytes, o None si no existe."""
        ...

    def delete_prefix(self, prefix: str) -> int: ...

    def signed_url(self, key: str, *, expires: int = 3600, download_name: str | None = None) -> str: ...

    def local_path(self, key: str) -> Path | None:
        """Ruta en disco si el backend es local (evita copias); None en backends remotos."""
        ...

    # --- subida multiparte -----------------------------------------------------------

    def create_multipart(self, key: str, content_type: str) -> str:
        """Inicia una subida por partes y devuelve su identificador."""
        ...

    def presign_part(self, key: str, upload_id: str, part_number: int, *, max_bytes: int, expires: int = 3600) -> str:
        ...

    def list_parts(self, key: str, upload_id: str) -> list[UploadedPart]: ...

    def complete_multipart(self, key: str, upload_id: str, parts: list[UploadedPart]) -> None: ...

    def abort_multipart(self, key: str, upload_id: str) -> None: ...
