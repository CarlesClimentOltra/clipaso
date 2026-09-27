from __future__ import annotations

from fastapi import APIRouter, Response

from smartcuts.application.pipeline import slugify
from smartcuts.domain.ports import Storage
from smartcuts.interfaces.api.deps import DispatcherDep, SessionDep, SettingsDep, StorageDep, UserDep
from smartcuts.interfaces.api.schemas import ClipOut, JobCreateIn, JobOut, JobSummary
from smartcuts.saas import services
from smartcuts.saas.db import utcnow
from smartcuts.saas.dispatch import dispatch_job
from smartcuts.saas.errors import user_message
from smartcuts.saas.models import Clip, Job

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _clip_out(clip: Clip, job: Job, storage: Storage, ttl: int) -> ClipOut:
    filename = f"{slugify(job.title)}-{clip.rank:02d}-{slugify(clip.title)}.mp4"
    return ClipOut(
        id=clip.id, rank=clip.rank, title=clip.title, reason=clip.reason, start=clip.start, end=clip.end,
        duration=round(clip.end - clip.start, 2), score=clip.score,
        video_url=storage.signed_url(clip.video_key, expires=ttl),
        download_url=storage.signed_url(clip.video_key, expires=ttl, download_name=filename),
        thumbnail_url=storage.signed_url(clip.thumb_key, expires=ttl) if clip.thumb_key else None,
    )


def _summary_fields(job: Job, storage: Storage, ttl: int) -> dict:
    first = next((c for c in job.clips if c.thumb_key), None)
    return dict(
        id=job.id, title=job.title, status=job.status, stage=job.stage, progress=job.progress,
        video_minutes=job.video_minutes, clip_count=len(job.clips),
        thumbnail_url=storage.signed_url(first.thumb_key, expires=ttl) if first else None,
        created_at=job.created_at, finished_at=job.finished_at, expires_at=job.expires_at,
    )


def job_out(job: Job, storage: Storage, ttl: int) -> JobOut:
    return JobOut(
        **_summary_fields(job, storage, ttl),
        error_code=job.error_code,
        error_message=user_message(job.error_code),
        clips=[_clip_out(c, job, storage, ttl) for c in job.clips],
    )


@router.post("", response_model=JobOut, status_code=201)
def create_job(
    body: JobCreateIn, user: UserDep, session: SessionDep, storage: StorageDep,
    settings: SettingsDep, dispatcher: DispatcherDep,
) -> JobOut:
    now = utcnow()
    job = services.create_job(
        session, user, upload_id=body.upload_id, max_clips=body.max_clips, language=body.language, now=now
    )
    session.commit()  # el job debe existir antes de que un worker lo busque
    if dispatch_job(dispatcher, job, now):
        session.commit()
    return job_out(job, storage, settings.api.signed_url_ttl_seconds)


@router.get("", response_model=list[JobSummary])
def list_jobs(user: UserDep, session: SessionDep, storage: StorageDep, settings: SettingsDep) -> list[JobSummary]:
    ttl = settings.api.signed_url_ttl_seconds
    return [JobSummary(**_summary_fields(j, storage, ttl)) for j in services.list_jobs(session, user)]


@router.get("/{job_id}", response_model=JobOut)
def get_job(job_id: str, user: UserDep, session: SessionDep, storage: StorageDep, settings: SettingsDep) -> JobOut:
    return job_out(services.get_job(session, user, job_id), storage, settings.api.signed_url_ttl_seconds)


@router.delete("/{job_id}", status_code=204)
def delete_job(job_id: str, user: UserDep, session: SessionDep, storage: StorageDep) -> Response:
    services.delete_job(session, storage, user, job_id, utcnow())
    return Response(status_code=204)
