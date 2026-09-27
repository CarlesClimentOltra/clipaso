"""Contratos de la API (lo que ve el frontend). El cliente TypeScript se genera a partir de aquí."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


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
    plan: PlanOut
    usage: UsageOut


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


class JobCreateIn(BaseModel):
    upload_id: str
    max_clips: int = Field(3, ge=1, le=50)
    language: str = Field("es", pattern=r"^(auto|[a-z]{2})$")


class ClipOut(BaseModel):
    id: str
    rank: int
    title: str
    reason: str
    start: float
    end: float
    duration: float
    score: float
    video_url: str
    download_url: str
    thumbnail_url: str | None


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
    clips: list[ClipOut]
