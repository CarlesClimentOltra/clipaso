"""Modelo de datos del producto: usuarios, planes, subidas, jobs, clips, tareas y consumo."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import JSON, BigInteger, DateTime, Float, ForeignKey, Index, Integer, String, Text, TypeDecorator
from sqlalchemy.orm import Mapped, mapped_column, relationship

from clipaso.saas.db import Base, utcnow


def new_id() -> str:
    return str(uuid.uuid4())


class UTCDateTime(TypeDecorator[datetime]):
    """Fechas siempre con zona UTC, también en SQLite (que no guarda zona horaria)."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_result_value(self, value, dialect):
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    EXPIRED = "expired"  # superó la retención del plan: clips borrados, queda el registro


class ClipStatus(StrEnum):
    READY = "ready"
    RENDERING = "rendering"  # se está volviendo a exportar tras editarlo
    FAILED = "failed"  # falló el último re-render; el vídeo anterior sigue disponible


class TaskKind(StrEnum):
    RENDER_CLIP = "render_clip"  # volver a exportar un clip editado
    MORE_CLIPS = "more_clips"  # buscar y exportar más clips del mismo vídeo
    EXPORT_CLIP = "export_clip"  # el clip en otra calidad (480p, 720p, 4K)


class TaskStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class UploadStatus(StrEnum):
    PENDING = "pending"
    READY = "ready"
    REJECTED = "rejected"
    PURGED = "purged"  # original borrado tras procesarlo (solo se conservan los clips)


class Plan(Base):
    """Límites de cada plan. `stripe_price_id` queda listo para la fase de cobros."""

    __tablename__ = "plans"

    code: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(64))
    monthly_minutes: Mapped[int] = mapped_column(Integer)
    max_video_minutes: Mapped[int] = mapped_column(Integer)
    max_clips_per_job: Mapped[int] = mapped_column(Integer)
    max_concurrent_jobs: Mapped[int] = mapped_column(Integer)
    max_upload_mb: Mapped[int] = mapped_column(Integer)
    retention_days: Mapped[int] = mapped_column(Integer)
    price_eur_cents: Mapped[int] = mapped_column(Integer, default=0)
    is_public: Mapped[bool] = mapped_column(default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    stripe_price_id: Mapped[str | None] = mapped_column(String(128))


class User(Base):
    """Perfil de producto. El id es el `sub` del proveedor de autenticación (Supabase)."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    email: Mapped[str] = mapped_column(String(320), index=True)
    plan_code: Mapped[str] = mapped_column(ForeignKey("plans.code"), default="free")
    stripe_customer_id: Mapped[str | None] = mapped_column(String(128))
    # Estilo de subtítulos por defecto y marca personal (ver saas/presets.py).
    preferences: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    plan: Mapped[Plan] = relationship(lazy="joined")


class Upload(Base):
    __tablename__ = "uploads"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    storage_key: Mapped[str] = mapped_column(String(512))
    multipart_id: Mapped[str | None] = mapped_column(String(1024))  # subida por partes en curso
    part_size: Mapped[int | None] = mapped_column(BigInteger)
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(128))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(16), default=UploadStatus.PENDING)
    duration_seconds: Mapped[float | None] = mapped_column(Float)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (Index("ix_jobs_status_created", "status", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    upload_id: Mapped[str | None] = mapped_column(ForeignKey("uploads.id", ondelete="SET NULL"))
    title: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(16), default=JobStatus.QUEUED)
    stage: Mapped[str | None] = mapped_column(String(32))
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_detail: Mapped[str | None] = mapped_column(Text)  # interno: nunca se muestra al usuario
    video_minutes: Mapped[float] = mapped_column(Float)
    max_clips: Mapped[int] = mapped_column(Integer)
    profile: Mapped[str] = mapped_column(String(64), default="vertical_9x16")
    options: Mapped[dict] = mapped_column(JSON, default=dict)
    llm_cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    heartbeat_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    # Último envío a un worker remoto (Modal); si se pierde, el barrido lo reenvía.
    dispatched_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime)  # retención según plan

    clips: Mapped[list[Clip]] = relationship(
        back_populates="job", cascade="all, delete-orphan", order_by="Clip.rank", lazy="selectin"
    )


class Clip(Base):
    __tablename__ = "clips"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    rank: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(255))
    reason: Mapped[str] = mapped_column(Text, default="")
    start: Mapped[float] = mapped_column(Float)
    end: Mapped[float] = mapped_column(Float)
    score: Mapped[float] = mapped_column(Float)
    video_key: Mapped[str] = mapped_column(String(512))
    thumb_key: Mapped[str | None] = mapped_column(String(512))
    size_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    # Textos para publicar (los propone la IA; el usuario puede editarlos).
    description: Mapped[str] = mapped_column(Text, default="")
    hashtags: Mapped[list] = mapped_column(JSON, default=list)
    rating: Mapped[int | None] = mapped_column(Integer)  # 1 👍, -1 👎
    # Editor: palabras corregidas {milisegundo de inicio: texto} y estilo propio del clip.
    word_edits: Mapped[dict] = mapped_column(JSON, default=dict)
    caption_style: Mapped[dict | None] = mapped_column(JSON)
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(16), default=ClipStatus.READY)
    render_error: Mapped[str | None] = mapped_column(String(255))
    # Otras versiones descargables: {"720p": {"version": 2, "key": …, "size": …}, "mp3": {…}}.
    exports: Mapped[dict] = mapped_column(JSON, default=dict)

    job: Mapped[Job] = relationship(back_populates="clips")


class Task(Base):
    """Trabajo secundario de un proyecto ya procesado (re-render de un clip, más clips).

    Se reclama y reenvía igual que los jobs: la tabla hace de cola.
    """

    __tablename__ = "tasks"
    __table_args__ = (Index("ix_tasks_status_created", "status", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    clip_id: Mapped[str | None] = mapped_column(ForeignKey("clips.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16), default=TaskStatus.QUEUED)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_detail: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    heartbeat_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    dispatched_at: Mapped[datetime | None] = mapped_column(UTCDateTime)


class UsageEvent(Base):
    """Libro de consumo en minutos. Uso del periodo = suma de `minutes` (reservas +, devoluciones −)."""

    __tablename__ = "usage_events"
    __table_args__ = (Index("ix_usage_user_period", "user_id", "period"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    job_id: Mapped[str | None] = mapped_column(ForeignKey("jobs.id", ondelete="SET NULL"))
    kind: Mapped[str] = mapped_column(String(16))  # reserve | refund | adjust
    minutes: Mapped[float] = mapped_column(Float)
    period: Mapped[str] = mapped_column(String(7))  # YYYY-MM
    note: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
