"""Contratos de la API (lo que ve el frontend). El cliente TypeScript se genera a partir de aquí."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from clipaso.saas.presets import BrandingPrefs, CaptionPreset, CaptionStyle, DurationT, FormatT, ModeT
from clipaso.saas.styles import UserStyle


class ErrorBody(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorBody


class PlanOut(BaseModel):
    code: str
    name: str
    price_eur_cents: int
    monthly_minutes: int
    max_video_minutes: int
    max_clips_per_job: int
    max_concurrent_jobs: int
    max_upload_mb: int
    retention_days: int


class UsageOut(BaseModel):
    period: str
    used_minutes: float
    limit_minutes: int
    remaining_minutes: float


class MeOut(BaseModel):
    id: str
    email: str
    locale: Literal["es", "en"] | None = Field(description="Idioma elegido; null si aún no se ha fijado.")
    plan: PlanOut
    usage: UsageOut


class LocaleIn(BaseModel):
    locale: Literal["es", "en"]


class UploadCreateIn(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    size_bytes: int = Field(gt=0)
    content_type: str = ""


class UploadCreateOut(BaseModel):
    upload_id: str
    part_size: int
    part_count: int


class PartUrlsIn(BaseModel):
    part_numbers: list[int] = Field(min_length=1, max_length=100)


class PartUrl(BaseModel):
    part_number: int
    url: str


class PartUrlsOut(BaseModel):
    urls: list[PartUrl]


class UploadedPartOut(BaseModel):
    part_number: int
    etag: str
    size: int


class UploadedPartsOut(BaseModel):
    parts: list[UploadedPartOut]


class CompletedPart(BaseModel):
    part_number: int = Field(ge=1)
    etag: str = Field(min_length=1, max_length=128)


class UploadCompleteIn(BaseModel):
    parts: list[CompletedPart] = Field(min_length=1, max_length=10000)


class UploadOut(BaseModel):
    id: str
    filename: str
    status: str
    size_bytes: int
    duration_seconds: float | None
    billable_minutes: float | None


class JobOptions(BaseModel):
    """Cómo quiere el usuario sus clips."""

    mode: ModeT = Field("clips", description="clips: la IA elige los mejores momentos · subtitle: el vídeo "
                                             "entero con subtítulos.")
    subtitle_language: str | None = Field(None, pattern=r"^[a-z]{2}$",
                                          description="Solo subtitular: traducir los subtítulos a este idioma.")
    format: FormatT = "vertical"
    duration: DurationT = "auto"
    topic: str = Field("", max_length=200, description="Tema opcional: «momentos donde hablo de dinero».")
    keep_source: bool = Field(True, description="Conservar el original para editar clips y pedir más.")
    branding: bool = Field(True, description="Añadir la marca personal del usuario (si la tiene).")
    caption_style: CaptionStyle | None = Field(None, description="Si falta, el estilo por defecto del usuario.")


class JobCreateIn(JobOptions):
    upload_id: str
    max_clips: int = Field(3, ge=1, le=50)
    language: str = Field("es", pattern=r"^(auto|[a-z]{2})$")
    trim_start: float | None = Field(None, ge=0, description="Usar solo un tramo del vídeo (si no se recortó "
                                                             "ya en el navegador): inicio en segundos.")
    trim_end: float | None = Field(None, gt=0)


ClipStatusT = Literal["ready", "rendering", "failed"]
CoverTemplateT = Literal["impacto", "caja", "titular", "limpia"]


class CoverOut(BaseModel):
    """Portada del clip: 9:16 (TikTok, Reels, Shorts) y 16:9 (YouTube)."""

    text: str
    highlight: int | None = Field(description="Palabra del texto resaltada (índice), o ninguna.")
    template: CoverTemplateT
    time: float = Field(description="Segundo del vídeo original del que sale el fotograma.")
    candidates: list[float] = Field(description="Otros momentos que propuso la IA.")
    vertical_url: str
    horizontal_url: str
    vertical_download_url: str
    horizontal_download_url: str
    pending: bool = Field(description="Se está generando una nueva propuesta con IA.")


class CoverIn(BaseModel):
    text: str | None = Field(None, max_length=60)
    highlight: int | None = Field(None, ge=-1, le=20, description="-1 = sin palabra resaltada.")
    template: CoverTemplateT | None = None
    time: float | None = Field(None, ge=0, description="Otro fotograma (segundo del vídeo original).")


class ClipOut(BaseModel):
    id: str
    rank: int
    title: str
    reason: str
    description: str
    hashtags: list[str]
    rating: int | None
    start: float
    end: float
    duration: float
    score: float
    status: ClipStatusT
    render_error: str | None
    version: int
    video_url: str
    download_url: str
    thumbnail_url: str | None
    cover: CoverOut | None = None


class ClipUpdateIn(BaseModel):
    title: str | None = Field(None, max_length=255)
    description: str | None = Field(None, max_length=2000)
    hashtags: list[str] | None = Field(None, max_length=15)


class RatingIn(BaseModel):
    value: Literal[-1, 0, 1]


class EditorWordOut(BaseModel):
    key: str
    start: float
    end: float
    text: str
    original: str
    brk: Literal["split", "join"] | None = Field(None, description="Corte de línea elegido tras esta palabra.")


FrameT = Literal["vertical", "square", "horizontal"]


class EditorOut(BaseModel):
    clip: ClipOut
    project_title: str
    format: FrameT = Field(description="Encuadre del clip (en el formato «original», el del vídeo).")
    source_duration: float
    window_start: float
    window_end: float
    preview_url: str | None = Field(description="Vídeo ligero del original para previsualizar el corte.")
    words: list[EditorWordOut]
    caption_style: CaptionStyle
    can_render: bool
    energy: list[float] = Field(default_factory=list, description="Volumen del audio (0-1) desde window_start.")
    energy_step: float = Field(0.5, description="Segundos entre valores de `energy`.")


class RenderIn(BaseModel):
    start: float = Field(ge=0)
    end: float = Field(gt=0)
    word_edits: dict[str, str] = Field(default_factory=dict, max_length=5000)
    caption_style: CaptionStyle | None = None


QualityT = Literal["480p", "720p", "1080p", "2160p"]


class ExportOut(BaseModel):
    format: Literal["mp4", "mp3"]
    quality: QualityT | None
    status: Literal["ready", "pending", "failed", "available"] = Field(
        description="ready: se puede descargar · pending: generándose · available: se puede pedir")
    url: str | None = None
    size_bytes: int | None = None
    error_message: str | None = None


class ExportsOut(BaseModel):
    items: list[ExportOut]


class ExportIn(BaseModel):
    format: Literal["mp4", "mp3"]
    quality: QualityT | None = None


class MoreClipsIn(BaseModel):
    count: int = Field(3, ge=1, le=15)
    topic: str = Field("", max_length=200)


class TaskOut(BaseModel):
    status: Literal["queued", "running", "done", "failed"]
    error_message: str | None


class ArchiveOut(BaseModel):
    url: str


class OptionItem(BaseModel):
    id: str
    label: str
    hint: str


class OptionsOut(BaseModel):
    formats: list[OptionItem]
    durations: list[OptionItem]
    presets: list[CaptionPreset]
    fonts: list[str]


class PreferencesOut(BaseModel):
    caption_style: CaptionStyle = Field(description="El estilo por defecto (ver /me/styles).")
    branding: BrandingPrefs
    logo_url: str | None


class PreferencesIn(BaseModel):
    branding: BrandingPrefs


class StylesOut(BaseModel):
    styles: list[UserStyle]
    default_id: str
    max_custom: int


class StyleIn(BaseModel):
    name: str = Field(max_length=40)
    style: CaptionStyle


class StyleUpdateIn(BaseModel):
    name: str | None = Field(None, max_length=40)
    style: CaptionStyle


class DefaultStyleIn(BaseModel):
    id: str = Field(max_length=40)


JobStatusT = Literal["queued", "running", "done", "failed", "expired"]


class JobSummary(BaseModel):
    id: str
    title: str
    status: JobStatusT
    stage: str | None
    progress: float
    video_minutes: float
    clip_count: int
    thumbnail_url: str | None
    created_at: datetime
    finished_at: datetime | None
    expires_at: datetime | None


class JobOut(JobSummary):
    error_code: str | None
    error_message: str | None
    options: JobOptions
    frame: Literal["vertical", "square", "horizontal"] = Field(
        description="Encuadre de los clips (en el formato «original», el del vídeo).")
    can_edit: bool = Field(description="Se conserva el original: se puede editar y pedir más clips.")
    more_clips_available: int
    more_clips_task: TaskOut | None
    clips: list[ClipOut]
