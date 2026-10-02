"""Contratos de la API (lo que ve el frontend). El cliente TypeScript se genera a partir de aquí."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from clipaso.saas.presets import (
    BrandingPrefs,
    CaptionPreset,
    CaptionStyle,
    CleanPaceT,
    DurationT,
    FormatT,
    HexColor,
    ModeT,
    ReframeFitT,
    TrailerSecondsT,
)
from clipaso.saas.styles import UserStyle


class ErrorBody(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorBody


class SignupCheckIn(BaseModel):
    email: str = Field(max_length=320)


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
    watermark: bool = Field(description="Los vídeos llevan la marca de agua de Clipaso.")
    max_export_quality: str = Field(description="Calidad máxima de descarga (1080p o 2160p).")
    daily_thumbnails: int = Field(description="Miniaturas sin subir el vídeo por día.")
    price_eur_cents_yearly: int = Field(0, description="Precio del pago anual (0 si no hay).")
    daily_renders: int = Field(description="Ediciones de clip (volver a renderizar) por día.")
    daily_more_clips: int = Field(description="Peticiones de «Más clips» por día.")
    daily_exports: int = Field(description="Descargas en otra calidad por día.")
    daily_covers: int = Field(description="Portadas nuevas con IA por día.")
    unlimited: bool = Field(False, description="Cuenta de desarrollo: sin cuota ni límites.")
    max_clips_per_project: int = Field(0, description="Clips por proyecto contando «Más clips».")

    @model_validator(mode="after")
    def _clips_per_project(self) -> PlanOut:
        from clipaso.saas.editing import MORE_CLIPS_FACTOR

        self.max_clips_per_project = self.max_clips_per_job * MORE_CLIPS_FACTOR
        return self


class UsageOut(BaseModel):
    period: str
    used_minutes: float
    limit_minutes: int
    remaining_minutes: float


class BillingOut(BaseModel):
    status: str | None = Field(description="Estado de la suscripción en Paddle (active, past_due, canceled…).")
    interval: Literal["month", "year"] | None
    renews_at: datetime | None = Field(description="Próximo cobro.")
    cancels_at: datetime | None = Field(description="Si está cancelada, cuándo termina (hasta entonces sigue activa).")
    can_manage: bool = Field(description="Puede abrir el portal de Paddle (tarjeta, facturas, cancelar).")


class BillingConfigOut(BaseModel):
    enabled: bool
    environment: Literal["sandbox", "production"]
    client_token: str
    prices: dict[str, str] = Field(description='Precio de Paddle por plan y periodo ("pro_month": "pri_…").')


class ChangePlanIn(BaseModel):
    plan: Literal["pro", "ultra"]
    interval: Literal["month", "year"]


class PortalOut(BaseModel):
    url: str


class MeOut(BaseModel):
    id: str
    email: str
    locale: Literal["es", "en"] | None = Field(description="Idioma elegido; null si aún no se ha fijado.")
    plan: PlanOut
    usage: UsageOut
    is_admin: bool = Field(False, description="Cuenta de desarrollo: ve el panel de costes.")
    billing: BillingOut | None = None


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
                                             "entero con subtítulos · clean: el vídeo entero sin silencios ni "
                                             "muletillas · reframe: el vídeo entero en otro formato · trailer: "
                                             "un resumen corto con los mejores momentos.")
    subtitle_language: str | None = Field(None, pattern=r"^[a-z]{2}$",
                                          description="Vídeo entero: traducir los subtítulos a este idioma.")
    clean_pace: CleanPaceT = Field("normal", description="Sin silencios: natural (solo pausas largas), normal "
                                                          "o fast (ritmo rápido, estilo YouTube).")
    clean_fillers: bool = Field(True, description="Sin silencios: quitar también «eh», «em», «mmm»…")
    trailer_seconds: TrailerSecondsT = Field(60, description="Tráiler: duración aproximada en segundos.")
    audiogram_title: str = Field("", max_length=90, description="Audiograma: título que se ve arriba (opcional).")
    audiogram_color: HexColor = Field("0F172A", description="Audiograma: color del fondo si no hay imagen.")
    audiogram_accent: HexColor = Field("B6E34A", description="Audiograma: color de la onda.")
    reframe_fit: ReframeFitT = Field("auto", description="Cambiar formato: auto (sigue a quien habla), blur_pad "
                                                          "(imagen completa con fondo desenfocado) o center "
                                                          "(rellenar recortando).")
    format: FormatT = "vertical"
    duration: DurationT = "auto"
    topic: str = Field("", max_length=200, description="Tema opcional: «momentos donde hablo de dinero».")
    keep_source: bool = Field(True, description="Obsoleto: el original se conserva siempre (salvo en «text»); "
                                                "este valor se ignora al crear el proyecto.")
    branding: bool = Field(True, description="Añadir la marca personal del usuario (si la tiene).")
    caption_style: CaptionStyle | None = Field(None, description="Si falta, el estilo por defecto del usuario.")


class ThumbnailFrameIn(BaseModel):
    time: float = Field(ge=0, description="Segundo del vídeo del que sale el fotograma.")
    image: str = Field(max_length=1_200_000, description="JPEG en base64.")


class ThumbnailIn(BaseModel):
    """Miniatura sin subir el vídeo: el navegador envía unos fotogramas."""

    filename: str = Field(max_length=255)
    topic: str = Field("", max_length=300, description="De qué trata el vídeo (opcional; mejora el texto).")
    language: str = Field("es", pattern=r"^[a-z]{2}$")
    branding: bool = True
    frames: list[ThumbnailFrameIn] = Field(min_length=1, max_length=24)


class JobCreateIn(JobOptions):
    upload_id: str
    max_clips: int = Field(3, ge=1, le=50)
    language: str = Field("es", pattern=r"^(auto|[a-z]{2})$")
    trim_start: float | None = Field(None, ge=0, description="Usar solo un tramo del vídeo (si no se recortó "
                                                             "ya en el navegador): inicio en segundos.")
    trim_end: float | None = Field(None, gt=0)
    audiogram_image: str | None = Field(None, max_length=4_000_000,
                                        description="Audiograma: imagen de fondo (JPEG o PNG en base64).")


ClipStatusT = Literal["ready", "rendering", "failed"]
CoverTemplateT = Literal["impacto", "caja", "titular", "limpia"]


class CoverOut(BaseModel):
    """Portada del clip: 9:16 (TikTok, Reels, Shorts) y 16:9 (YouTube)."""

    text: str
    highlight: int | None = Field(description="Palabra del texto resaltada (índice), o ninguna.")
    template: CoverTemplateT
    time: float = Field(description="Segundo del vídeo original del que sale el fotograma.")
    candidates: list[float] = Field(description="Otros momentos que propuso la IA.")
    candidate_images: list[str | None] = Field(
        default_factory=list, description="Imagen de cada momento propuesto (miniaturas hechas sin subir el vídeo).")
    # Solo las que usa el proyecto: 9:16 (TikTok, Reels, Shorts), 16:9 (YouTube) o ambas.
    vertical_url: str | None = None
    horizontal_url: str | None = None
    vertical_download_url: str | None = None
    horizontal_download_url: str | None = None
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
    status: Literal["ready", "pending", "failed", "available", "locked"] = Field(
        description="ready: se puede descargar · pending: generándose · available: se puede pedir · "
                    "locked: la incluye un plan superior")
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
    mode: ModeT = "clips"
    status: JobStatusT
    stage: str | None
    progress: float
    video_minutes: float
    clip_count: int
    thumbnail_url: str | None
    created_at: datetime
    finished_at: datetime | None
    expires_at: datetime | None


class CleanStatsOut(BaseModel):
    """Lo que se quitó en el modo «sin silencios»."""

    original_seconds: float
    removed_seconds: float
    pauses: int
    fillers: int


class TrailerStatsOut(BaseModel):
    """De qué se hizo el tráiler."""

    original_seconds: float
    trailer_seconds: float
    moments: int


class ChapterOut(BaseModel):
    start: float
    title: str


class TextResultsOut(BaseModel):
    """Del vídeo al texto: lo que escribió la IA a partir de la transcripción."""

    language: str
    summary: str
    key_points: list[str]
    chapters: list[ChapterOut]
    chapters_text: str = Field(description="Los capítulos listos para pegar en la descripción de YouTube.")
    blog_title: str
    blog_markdown: str
    linkedin: str
    thread: list[str]
    seo_title: str
    seo_description: str
    seo_tags: list[str]


class JobOut(JobSummary):
    error_code: str | None
    error_message: str | None
    options: JobOptions
    clean_stats: CleanStatsOut | None = None
    trailer_stats: TrailerStatsOut | None = None
    text_results: TextResultsOut | None = None
    frame: Literal["vertical", "square", "horizontal"] = Field(
        description="Encuadre de los clips (en el formato «original», el del vídeo).")
    can_edit: bool = Field(description="Se conserva el original: se puede editar y pedir más clips.")
    more_clips_available: int
    more_clips_task: TaskOut | None
    clips: list[ClipOut]


class AdminModeOut(BaseModel):
    mode: str
    jobs: int
    measured: int = Field(description="Proyectos con consumo medido (los anteriores a la medición no lo tienen).")
    minutes: float
    worker_s: float
    compute_usd: float
    llm_usd: float
    source_mb: float
    usd_per_minute: float | None = Field(description="Coste medio (cómputo + IA) por minuto de vídeo.")


class AdminJobOut(BaseModel):
    id: str
    created_at: datetime
    user: str
    mode: str
    status: str
    title: str
    minutes: float
    source_mb: float | None
    source_res: str | None
    worker_s: float | None
    cpu_s: float | None
    compute_usd: float | None
    llm_usd: float
    stages: dict[str, float]


class AdminDuplicateOut(BaseModel):
    title: str
    minutes: float
    users: list[str] = Field(description="Cuentas gratis que han procesado el mismo vídeo.")
    jobs: int
    last_at: datetime


class AdminUsageOut(BaseModel):
    days: int
    jobs: int
    tasks: int
    compute_usd: float
    llm_usd: float
    task_compute_usd: float
    modes: list[AdminModeOut]
    recent: list[AdminJobOut]
    duplicates: list[AdminDuplicateOut] = Field(default_factory=list)
    rates: dict
