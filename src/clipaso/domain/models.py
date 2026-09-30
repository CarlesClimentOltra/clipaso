"""Modelos del dominio.

Son pydantic para poder persistirlos como JSON entre etapas del pipeline
(caché en disco) y, en el futuro, devolverlos directamente desde la API.
No dependen de ninguna librería de procesamiento.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

# --------------------------------------------------------------------------- fuente


class Chapter(BaseModel):
    title: str
    start: float
    end: float


class SourceVideo(BaseModel):
    """Vídeo ya disponible en disco, sea cual sea su origen."""

    source_id: str = Field(description="Identificador estable; se usa como clave de caché.")
    provider: str
    uri: str
    path: Path
    title: str = ""
    duration: float
    width: int
    height: int
    fps: float
    chapters: list[Chapter] = Field(default_factory=list)


# --------------------------------------------------------------------------- transcripción


class Word(BaseModel):
    text: str
    start: float
    end: float
    probability: float = 1.0
    # Corte de subtítulo elegido por el usuario tras esta palabra: "split" (nueva línea) o "join" (seguir).
    brk: Literal["split", "join"] | None = None


class Sentence(BaseModel):
    """Unidad mínima de corte: un clip siempre empieza y acaba en frontera de frase."""

    index: int
    start: float
    end: float
    text: str
    words: list[Word]

    @property
    def duration(self) -> float:
        return self.end - self.start


class Transcript(BaseModel):
    language: str
    duration: float
    sentences: list[Sentence]

    def words_between(self, start: float, end: float) -> list[Word]:
        return [
            w for s in self.sentences for w in s.words if w.start >= start - 0.01 and w.end <= end + 0.01
        ]


# --------------------------------------------------------------------------- señales


class Signal(BaseModel):
    """Serie temporal normalizada 0..1 (1 = más interesante)."""

    name: str
    step: float = Field(description="Segundos entre muestras.")
    values: list[float]

    def mean_between(self, start: float, end: float) -> float | None:
        if not self.values or end <= start:
            return None
        i0 = max(0, int(start / self.step))
        i1 = min(len(self.values), max(i0 + 1, int(end / self.step)))
        chunk = self.values[i0:i1]
        return sum(chunk) / len(chunk) if chunk else None


class SignalSet(BaseModel):
    signals: dict[str, Signal] = Field(default_factory=dict)


# --------------------------------------------------------------------------- selección


class ClipCandidate(BaseModel):
    """Clip propuesto por una estrategia de selección."""

    start: float
    end: float
    first_sentence: int
    last_sentence: int
    score: float = Field(ge=0.0, le=1.0)
    title: str = ""
    reason: str = ""
    hook: str = ""
    description: str = Field("", description="Texto para publicar junto al clip.")
    hashtags: list[str] = Field(default_factory=list)
    scores: dict[str, float] = Field(default_factory=dict, description="Desglose por señal.")

    @property
    def duration(self) -> float:
        return self.end - self.start

    def overlaps(self, other: ClipCandidate, tolerance: float = 0.0) -> bool:
        return self.start < other.end - tolerance and other.start < self.end - tolerance


class Selection(BaseModel):
    strategy: str
    clips: list[ClipCandidate]
    notes: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------- salida


class ReframeMode(StrEnum):
    AUTO = "auto"  # seguimiento de cara si es fiable; si no, fondo desenfocado
    FACE = "face"
    BLUR_PAD = "blur_pad"
    CENTER = "center"


class SubtitleStyle(BaseModel):
    enabled: bool = True
    font: str = "Arial"
    font_size_ratio: float = Field(0.045, description="Tamaño relativo a la altura del vídeo.")
    primary_color: str = "FFFFFF"
    highlight_color: str = "00E5FF"
    outline_color: str = "000000"
    outline_ratio: float = 0.004
    shadow_ratio: float = 0.002
    position: Literal["bottom", "middle", "top"] = "bottom"
    margin_v_ratio: float = Field(0.28, description="Distancia al borde (abajo o arriba; evita la UI de la app).")
    pos_y: float | None = Field(None, description="Centro del texto, relativo a la altura; manda sobre `position`.")
    box: bool = Field(False, description="Texto sobre una caja de color en vez de con contorno.")
    box_color: str = "000000"
    box_opacity: int = 100
    animation: Literal["highlight", "pop", "karaoke", "appear", "none"] = "highlight"
    max_words: int = 3
    max_chunk_seconds: float = 1.6
    uppercase: bool = True


class Branding(BaseModel):
    """Marca personal que se añade a los clips."""

    handle: str = Field("", description="Texto fijo, p. ej. @usuario.")
    logo_path: Path | None = None
    position: Literal["top-left", "top-right", "bottom-left", "bottom-right"] = "top-right"
    watermark: bool = Field(False, description="Marca de agua de Clipaso (según el plan del usuario).")

    @property
    def active(self) -> bool:
        """Hay marca personal (logo o @usuario); la marca de agua va aparte."""
        return bool(self.handle.strip() or self.logo_path)


class VideoEncoding(BaseModel):
    codec: str = Field("auto", description="auto | h264_nvenc | libx264")
    crf: int = 20
    preset: str = "medium"
    audio_bitrate: str = "160k"
    loudnorm: bool = True


class OutputProfile(BaseModel):
    """Formato de salida. Añadir un formato nuevo = añadir un YAML, no código."""

    name: str
    width: int
    height: int
    fps: int = 30
    min_duration: float = 20.0
    max_duration: float = 60.0
    target_duration: float = 40.0
    reframe: ReframeMode = ReframeMode.AUTO
    subtitles: SubtitleStyle = Field(default_factory=SubtitleStyle)
    encoding: VideoEncoding = Field(default_factory=VideoEncoding)
    exporter: str = "ffmpeg"

    @property
    def aspect(self) -> float:
        return self.width / self.height


class ExportedClip(BaseModel):
    rank: int
    path: Path
    thumbnail: Path | None = None
    start: float
    end: float
    score: float
    title: str
    reason: str = ""
    description: str = ""
    hashtags: list[str] = Field(default_factory=list)
    reframe_mode: str
    profile: str


class JobResult(BaseModel):
    source: SourceVideo
    selection: Selection
    exports: list[ExportedClip]
    cost_usd: float = 0.0
    # Para guardarlos junto al proyecto (editor, más clips); no van al manifest.
    transcript: Transcript | None = Field(None, exclude=True)
    signals: SignalSet | None = Field(None, exclude=True)
