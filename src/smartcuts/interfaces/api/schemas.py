"""Contratos de la API (lo que ve el frontend). El cliente TypeScript se genera a partir de aquí."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from smartcuts.saas.presets import BrandingPrefs, CaptionPreset, CaptionStyle, DurationT, FormatT


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


ClipStatusT = Literal["ready", "rendering", "failed"]


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


class EditorOut(BaseModel):
    clip: ClipOut
    project_title: str
    format: FormatT
    source_duration: float
    window_start: float
    window_end: float
    preview_url: str | None = Field(description="Vídeo ligero del original para previsualizar el corte.")
    words: list[EditorWordOut]
    caption_style: CaptionStyle
    can_render: bool


class RenderIn(BaseModel):
    start: float = Field(ge=0)
    end: float = Field(gt=0)
    word_edits: dict[str, str] = Field(default_factory=dict, max_length=5000)
    caption_style: CaptionStyle | None = None


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
    caption_style: CaptionStyle
    branding: BrandingPrefs
    logo_url: str | None


class PreferencesIn(BaseModel):
    caption_style: CaptionStyle
    branding: BrandingPrefs


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
    can_edit: bool = Field(description="Se conserva el original: se puede editar y pedir más clips.")
    more_clips_available: int
    more_clips_task: TaskOut | None
    clips: list[ClipOut]
